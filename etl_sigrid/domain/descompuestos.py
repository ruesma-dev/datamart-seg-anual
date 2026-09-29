# etl_sigrid/domain/descompuestos.py
"""
Los descompuestos de las partidas (F-097), en dominio puro: sin red, sin base de
datos y sin dependencias externas.

Tres piezas:

1. **Que versiones del master se releen de Sigrid** (`planificar_relectura`,
   R5-R7). No hay `tiemod` en `obrparpre` ni marca de cierre util en
   `obrfasamb`, asi que lo nuevo y lo cambiado se detectan por HUELLA: la terna
   `(filas, bytes, huella)` que Sigrid calcula por version en una sola consulta.
   Se relee lo que no esta cargado, la vigente de cada obra —siempre, porque la
   huella es ciega a un cambio en mitad de un `des` de mas de 16.000 bytes— y lo
   de huella distinta; se borra lo que Sigrid ya no tiene; y todo cabe en un
   tope de MB por noche, con lo que no cabe aplazado a la siguiente.
2. **Que versiones se retrocean en el build** (`planificar_troceado`, R21), con
   el mismo tope y partidas en lotes.
3. **El troceado del texto `des`** (`trocear_des`, R13, R14, R19): el ESPEJO en
   Python de `sql/descompuestos/01_troceado.sql`, que es quien trocea de verdad.
   Existe para probar la regla sin base de datos (precedente de F-052,
   `arbol_partidas.py`); que el SQL use las mismas posiciones lo fija un test
   contra `POSICIONES`.

El formato del `des` (medido el 2026-09-27 y el 2026-09-28): registros que
empiezan por `~D|`, separados por salto de linea, con campos separados por `|`.
El texto largo del campo 9 puede traer saltos de linea dentro, por eso se parte
por «salto seguido de `~<letra>|`» y no por cualquier salto. Posiciones base 0.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# ---------------------------------------------------------------------------
# Vocabulario
# ---------------------------------------------------------------------------

#: Un MB, a efectos del tope nocturno: 1024 x 1024 bytes, como `DATALENGTH`.
MB = 1024 * 1024

#: Tamano maximo de un lote de troceado. Un lote es UNA transaccion en
#: Postgres; con el mismo valor que el tope por defecto, una noche normal es un
#: solo lote y la primera carga entera (2,14 GB) unos ocho.
MB_POR_LOTE = 300

#: Los cinco origenes de una linea (D2, D13). El orden es el de la ficha.
ORIGENES = ("ESTUDIO", "PLANIF_JO", "MASTER_INICIAL", "MASTER_PRE_ABC", "MASTER_PLANIF_JO")

#: Los estados del cuadre descompuesto-precio de la partida (R23).
ESTADOS_CUADRE = ("CUADRA", "NO_CUADRA", "SIN_DESCOMPUESTO", "SUSTITUIDO_POR_PLANIFICACION")

#: Por que se relee una version. El orden es la prioridad frente al tope (R6).
MOTIVO_VIGENTE = "vigente"
MOTIVO_CAMBIADA = "cambiada"
MOTIVO_NUEVA = "nueva"
ORDEN_DE_MOTIVOS = (MOTIVO_VIGENTE, MOTIVO_CAMBIADA, MOTIVO_NUEVA)
_PRIORIDAD = {motivo: n for n, motivo in enumerate(ORDEN_DE_MOTIVOS)}

#: Posicion (base 0) de cada campo dentro de un registro del `des` (R13).
POSICIONES = {
    "codigo_elemento": 1,
    "descripcion": 2,
    "precio": 3,
    "cantidad_total": 4,
    "unidad": 5,
    "codigo_alternativo": 7,
    "naturaleza_codigo": 11,
    "rendimiento": 14,
    "tipo_elemento_codigo": 16,
    "naturaleza": 17,
    "dncpro_id": 36,
}

#: Traduccion del tipo de elemento (campo 16), D8. **Los codigos 3 y 11 estan
#: SIN VALIDAR con Negocio**: 3 son lineas de subcontrata de obra completa y 11
#: codigos `SB...`; se publican con esta traduccion y la ficha lo dice.
TIPOS_ELEMENTO = {
    "8": "MANO_OBRA",
    "9": "MAQUINARIA",
    "10": "MATERIAL",
    "11": "SUBCONTRATA",
    "3": "OTROS",
    "4": "PORCENTAJE",
    "13": "MEDIOS_AUXILIARES",
}
TIPO_SIN_TIPO = "SIN_TIPO"
TIPO_DESCONOCIDO = "DESCONOCIDO"

#: Tipos cuyo precio es la BASE y su rendimiento el tanto por uno (0.02 = 2 %).
TIPOS_PORCENTAJE = ("4", "13")

#: Lo que es un numero en un campo del `des`. El MISMO patron que usa
#: `descompuestos.fn_num` en el SQL (lo fija un test): lo que no casa es NULL.
#: El exponente va acotado a tres cifras: `1e99999` no cabe en un NUMERIC y
#: tumbaria el build en vez de salir NULL. Se aplica con `fullmatch`: en Python
#: `$` casa antes de un salto de linea final y en PostgreSQL no (review 1 de
#: F-097).
PATRON_NUMERO = r"^[-+]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][-+]?[0-9]{1,3})?$"
_NUMERO = re.compile(PATRON_NUMERO)
_ENLACE = re.compile(r"^[0-9]{1,18}$")
_SEPARADOR_REGISTROS = re.compile(r"\n(?=~[A-Z]\|)")
_INICIO_REGISTRO = re.compile(r"^~[A-Z]\|")
_COD_VIGENTE = re.compile(r"^[0-9]+$")
_CENTIMO = Decimal("0.01")

#: Tope de un importe publicado: las columnas son NUMERIC(18,2), asi que caben
#: 16 cifras enteras. Lo que tras redondear llega a 1e16 es NULL, igual que en
#: `01_troceado.sql` (review 1 de F-097): un `|` que desplaza campos puede poner
#: un numero enorme donde no toca, y eso no puede tumbar el build.
LIMITE_IMPORTE = Decimal("1e16")


# ---------------------------------------------------------------------------
# El troceado (espejo del SQL)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RegistroDes:
    """Una linea del descompuesto, como la publica `descompuestos.lineas`."""

    orden: int
    codigo_elemento: str | None
    descripcion: str | None
    precio: Decimal | None
    cantidad_total: Decimal | None
    unidad: str | None
    codigo_alternativo: str | None
    naturaleza_codigo: str | None
    rendimiento: Decimal | None
    tipo_elemento_codigo: str | None
    naturaleza: str | None
    dncpro_id: int | None
    tipo_elemento: str
    importe_unitario: Decimal | None
    importe_total: Decimal | None
    es_porcentaje: bool
    porcentaje: Decimal | None
    base_porcentaje: Decimal | None

    @property
    def es_enlazado(self) -> bool:
        """Viene de la planificacion de compras: su campo 36 es un `dncpro.ide`."""
        return self.dncpro_id is not None


def numero(texto: str | None) -> Decimal | None:
    """El valor de un campo numerico, o `None` si no es un numero (R14)."""
    if texto is None:
        return None
    limpio = texto.strip(" ")
    if not _NUMERO.fullmatch(limpio):
        return None
    try:
        return Decimal(limpio)
    except InvalidOperation:  # pragma: no cover - el patron ya lo impide
        return None


def tipo_elemento(codigo: str | None) -> str:
    """La traduccion del campo 16 (D8): vacio es SIN_TIPO y lo raro DESCONOCIDO."""
    if codigo is None or codigo == "":
        return TIPO_SIN_TIPO
    return TIPOS_ELEMENTO.get(codigo, TIPO_DESCONOCIDO)


def _texto(campos: Sequence[str], posicion: int) -> str | None:
    """Campo ausente o vacio es NULL (como `NULLIF(btrim(...), '')`)."""
    if posicion >= len(campos):
        return None
    return campos[posicion].strip(" ") or None


def _redondeo(valor: Decimal | None) -> Decimal | None:
    """`ROUND(x, 2)`, o NULL si no cabe en NUMERIC(18,2) (sin `InvalidOperation`)."""
    if valor is None or abs(valor) >= LIMITE_IMPORTE:
        return None
    redondeado = valor.quantize(_CENTIMO, rounding=ROUND_HALF_UP)
    return None if abs(redondeado) >= LIMITE_IMPORTE else redondeado


def _producto(a: Decimal | None, b: Decimal | None) -> Decimal | None:
    return None if a is None or b is None else a * b


def _enlace(campos: Sequence[str]) -> int | None:
    crudo = campos[POSICIONES["dncpro_id"]] if len(campos) > POSICIONES["dncpro_id"] else ""
    if not _ENLACE.fullmatch(crudo):
        return None
    return int(crudo) or None


def trocear_des(des: str | None) -> tuple[RegistroDes, ...]:
    """Parte el `des` en registros y mapea cada campo por su posicion (R13)."""
    if not des:
        return ()
    registros: list[RegistroDes] = []
    for trozo in _SEPARADOR_REGISTROS.split(des.replace("\r", "")):
        if not _INICIO_REGISTRO.match(trozo):
            continue
        campos = trozo.rstrip("\n").split("|")
        precio = numero(_texto(campos, POSICIONES["precio"]))
        cantidad = numero(_texto(campos, POSICIONES["cantidad_total"]))
        rendimiento = numero(_texto(campos, POSICIONES["rendimiento"]))
        codigo_tipo = _texto(campos, POSICIONES["tipo_elemento_codigo"])
        es_porcentaje = codigo_tipo in TIPOS_PORCENTAJE
        registros.append(
            RegistroDes(
                orden=len(registros) + 1,
                codigo_elemento=_texto(campos, POSICIONES["codigo_elemento"]),
                descripcion=_texto(campos, POSICIONES["descripcion"]),
                precio=precio,
                cantidad_total=cantidad,
                unidad=_texto(campos, POSICIONES["unidad"]),
                codigo_alternativo=_texto(campos, POSICIONES["codigo_alternativo"]),
                naturaleza_codigo=_texto(campos, POSICIONES["naturaleza_codigo"]),
                rendimiento=rendimiento,
                tipo_elemento_codigo=codigo_tipo,
                naturaleza=_texto(campos, POSICIONES["naturaleza"]),
                dncpro_id=_enlace(campos),
                tipo_elemento=tipo_elemento(codigo_tipo),
                importe_unitario=_redondeo(_producto(precio, rendimiento)),
                importe_total=_redondeo(_producto(cantidad, precio)),
                es_porcentaje=es_porcentaje,
                porcentaje=(
                    _producto(rendimiento, Decimal(100)) if es_porcentaje else None
                ),
                base_porcentaje=precio if es_porcentaje else None,
            )
        )
    return tuple(registros)


def cod_version_vigente(business_rules: Mapping) -> str:
    """El `cod` de `conext` que marca la version vigente (`business_rules.yaml`).

    Viaja como LITERAL a un SQL compuesto por texto, asi que solo se admiten
    digitos: nada que venga de un fichero editable llega a concatenarse sin
    blindar.
    """
    cod = business_rules.get("sigrid", {}).get("campos_extendidos", {}).get(
        "cod_version_master_vigente"
    )
    if not isinstance(cod, str) or not _COD_VIGENTE.fullmatch(cod):
        raise ValueError(
            f"cod_version_master_vigente tiene que ser solo digitos y es {cod!r}"
        )
    return cod


# ---------------------------------------------------------------------------
# Que se relee de Sigrid (R5-R7)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class VersionSigrid:
    """Una version del master (ambito 8) con `des` en Sigrid, con su huella."""

    obra_id: int
    fase_num: int
    filas: int
    bytes: int
    huella: int | None

    @property
    def clave(self) -> tuple[int, int]:
        return (self.obra_id, self.fase_num)


@dataclass(frozen=True, slots=True)
class VersionCargada:
    """Una version ya cargada, con la huella que tenia Sigrid al cargarla."""

    obra_id: int
    fase_num: int
    filas: int
    bytes: int
    huella: int | None

    @property
    def clave(self) -> tuple[int, int]:
        return (self.obra_id, self.fase_num)


@dataclass(frozen=True, slots=True)
class Relectura:
    """Una version que hay que releer, y por que."""

    version: VersionSigrid
    motivo: str


@dataclass(frozen=True, slots=True)
class PlanRelectura:
    """Lo que la ingesta hace esta noche con el master."""

    releer: tuple[Relectura, ...]
    aplazadas: tuple[Relectura, ...]
    borrar: tuple[tuple[int, int], ...]

    @property
    def bytes_releer(self) -> int:
        return sum(r.version.bytes for r in self.releer)

    @property
    def bytes_aplazados(self) -> int:
        return sum(r.version.bytes for r in self.aplazadas)


def _recortar(elementos: Sequence, tamano, tope_bytes: int) -> tuple[list, list]:
    """Toma por orden mientras quepa y corta en seco en la primera que no cabe.

    El corte es ESTRICTO (no se salta a una posterior mas pequena) para que la
    convergencia vaya por el orden declarado. Y siempre entra la primera: una
    version mayor que el tope entero no puede atascar la cola para siempre.
    """
    tomados: list = []
    acumulado = 0
    for indice, elemento in enumerate(elementos):
        bytes_ = tamano(elemento)
        if tomados and acumulado + bytes_ > tope_bytes:
            return tomados, list(elementos[indice:])
        tomados.append(elemento)
        acumulado += bytes_
    return tomados, []


def planificar_relectura(
    sigrid: Iterable[VersionSigrid],
    cargadas: Iterable[VersionCargada],
    vigentes: Mapping[int, int],
    presupuesto_mb: float,
    sin_tope: bool = False,
    *,
    bytes_ya_usados: int = 0,
) -> PlanRelectura:
    """Decide que versiones releer, cuales aplazar y cuales borrar (R5-R7).

    - **releer**: las no cargadas (nuevas), la vigente de cada obra y las de
      huella distinta de la guardada, por prioridad vigente > cambiada > nueva y
      dentro de cada una por `(obra_id, fase_num)`.
    - **tope** (R6): `presupuesto_mb` menos lo ya leido esta noche (el ambito
      3, `bytes_ya_usados`); lo que no cabe va a `aplazadas`.
    - **sin_tope** (R7): todo entra; es la primera carga, MANUAL.
    - **borrar**: las cargadas que Sigrid ya no tiene. No gasta presupuesto.
    """
    if not sin_tope and presupuesto_mb <= 0:
        raise ValueError(f"el presupuesto de MB tiene que ser positivo y es {presupuesto_mb}")

    en_sigrid: dict[tuple[int, int], VersionSigrid] = {}
    for version in sigrid:
        if version.clave in en_sigrid:
            raise ValueError(f"version repetida en la huella de Sigrid: {version.clave}")
        en_sigrid[version.clave] = version
    ya_cargadas = {c.clave: c for c in cargadas}

    candidatas: list[Relectura] = []
    for clave, version in en_sigrid.items():
        cargada = ya_cargadas.get(clave)
        if vigentes.get(version.obra_id) == version.fase_num:
            motivo = MOTIVO_VIGENTE
        elif cargada is None:
            motivo = MOTIVO_NUEVA
        elif (cargada.filas, cargada.bytes, cargada.huella) != (
            version.filas, version.bytes, version.huella
        ):
            motivo = MOTIVO_CAMBIADA
        else:
            continue
        candidatas.append(Relectura(version=version, motivo=motivo))

    candidatas.sort(key=lambda r: (_PRIORIDAD[r.motivo], r.version.obra_id, r.version.fase_num))
    borrar = tuple(sorted(clave for clave in ya_cargadas if clave not in en_sigrid))

    if sin_tope:
        return PlanRelectura(releer=tuple(candidatas), aplazadas=(), borrar=borrar)

    tope = int(presupuesto_mb * MB) - bytes_ya_usados
    tomadas, aplazadas = _recortar(candidatas, lambda r: r.version.bytes, tope)
    return PlanRelectura(releer=tuple(tomadas), aplazadas=tuple(aplazadas), borrar=borrar)


# ---------------------------------------------------------------------------
# Que se retrocea en el build (R21)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class VersionPendiente:
    """Una version cargada cuyo troceado no es el del SQL vigente."""

    obra_id: int
    fase_num: int
    bytes: int
    es_vigente: bool

    @property
    def clave(self) -> tuple[int, int]:
        return (self.obra_id, self.fase_num)


@dataclass(frozen=True, slots=True)
class PlanTroceado:
    """Los lotes que el build trocea esta noche, y lo que se deja para manana."""

    lotes: tuple[tuple[tuple[int, int], ...], ...]
    aplazadas: tuple[VersionPendiente, ...]


def planificar_troceado(
    pendientes: Iterable[VersionPendiente],
    presupuesto_mb: float,
    sin_tope: bool = False,
    mb_por_lote: float = MB_POR_LOTE,
) -> PlanTroceado:
    """Ordena (vigentes primero, luego por obra y fase), recorta y parte en lotes."""
    if mb_por_lote <= 0:
        raise ValueError(f"el tamano de lote tiene que ser positivo y es {mb_por_lote}")
    if not sin_tope and presupuesto_mb <= 0:
        raise ValueError(f"el presupuesto de MB tiene que ser positivo y es {presupuesto_mb}")

    ordenadas = sorted(pendientes, key=lambda p: (not p.es_vigente, p.obra_id, p.fase_num))
    if sin_tope:
        tomadas, aplazadas = ordenadas, []
    else:
        tomadas, aplazadas = _recortar(ordenadas, lambda p: p.bytes, int(presupuesto_mb * MB))

    lotes: list[tuple[tuple[int, int], ...]] = []
    actual: list[tuple[int, int]] = []
    acumulado = 0
    limite = int(mb_por_lote * MB)
    for pendiente in tomadas:
        if actual and acumulado + pendiente.bytes > limite:
            lotes.append(tuple(actual))
            actual, acumulado = [], 0
        actual.append(pendiente.clave)
        acumulado += pendiente.bytes
    if actual:
        lotes.append(tuple(actual))
    return PlanTroceado(lotes=tuple(lotes), aplazadas=tuple(aplazadas))
