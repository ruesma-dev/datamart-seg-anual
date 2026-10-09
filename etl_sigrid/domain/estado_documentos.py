# etl_sigrid/domain/estado_documentos.py
"""
DESDE CUÁNDO está cada documento de compras en su estado actual (F-132).

LA FUENTE ES `rac`, vía `compras.documento_procesos` (F-085): el último paso de
la ventana «Procesos» de Sigrid fecha al segundo el estado actual del 99,4 % de
contratos, facturas y comparativos (medido el 2026-10-08). Lo que queda:

- **PASO**: el destino del último paso es el estado actual de la cabecera →
  la fecha es el `momento` de ese paso (hora de Madrid; si el paso no tiene
  hora, su día a las 00:00).
- **ALTA**: el documento no tiene ningún paso y está en un estado INICIAL de
  su tipo → la fecha es el día de alta (`con.fec`, sin hora: Sigrid no la
  guarda). Sin fecha de alta (`con.fec` = 0), sin fecha.
- **FUERA_DE_PROCESO**: cualquier otro caso (el estado cambió sin un paso:
  75 documentos de stock histórico). NO hay fecha; se da la cota
  `cambio_posterior_a` = el `momento` del último paso, si lo hay.

ES LA HISTORIA NETA (D2 del humano): «Deshacer proceso» BORRA el paso de `rac`,
así que un estado al que se vuelve deshaciendo cuenta desde el paso que llevó a
él la primera vez. La fecha del deshacer está en `dbo.log` (F-105), no aquí.

EL CONTRASTE con la foto diaria de F-067 (`clasificar_cambio`,
`clasificar_no_visto`) vive también aquí: es lo que decide si la foto se puede
retirar (Fase B, D7 del humano).

LA REGLA LA EJECUTA SQL (`sql/compras/13_estado_documentos.sql`), y aquí está
escrita **una sola vez** como oráculo puro: los literales —las familias, los
estados iniciales y los tres orígenes— viven aquí y `tests/test_f132_sql.py`
comprueba que el SQL lleva LOS MISMOS. Mismo patrón que
`domain/documento_procesos.py` (F-085) y que el oráculo de la foto de F-067.

Capa `domain`: sin un solo import de infraestructura ni de configuración.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Final

#: Las familias de la vista (`con.tip`) y su nombre publicado (D3 del humano):
#: contrato, factura y comparativo. Las obras no: su estado es de `maestro`.
FAMILIAS_ESTADO: Final[dict[int, str]] = {
    44: "CONTRATO",
    15: "FACTURA",
    46: "COMPARATIVO",
}

#: Los estados INICIALES de cada familia: medidos el 2026-10-08, son los de
#: TODOS los documentos sin un solo paso en `rac` (factura 1 y 20, contrato 1,
#: comparativo 1, 11 y 100). Un documento sin pasos en otro estado cambió fuera
#: de un proceso.
ESTADOS_INICIALES: Final[dict[int, frozenset[int]]] = {
    15: frozenset({1, 20}),
    44: frozenset({1}),
    46: frozenset({1, 11, 100}),
}

#: De dónde sale `en_estado_desde` (R4-R6), en el orden en que se decide.
ORIGENES_FECHA: Final[tuple[str, ...]] = ("PASO", "ALTA", "FUERA_DE_PROCESO")
_PASO, _ALTA, _FUERA_DE_PROCESO = ORIGENES_FECHA

#: Cómo se explica cada cambio que vio la foto (R13), en ORDEN DE PRIORIDAD:
#: la primera que se cumple es la clase.
CLASES_CAMBIO: Final[tuple[str, ...]] = (
    "PASO",
    "DESHECHO",
    "VUELTA_AL_INICIAL",
    "FUERA_DE_PROCESO",
    "DISCREPANCIA",
)
#: Cómo se explica un documento con pasos en la ventana que la foto NO vio
#: cambiar (R14), también en orden de prioridad.
CLASES_NO_VISTO: Final[tuple[str, ...]] = ("ALTA", "IDA_Y_VUELTA", "DISCREPANCIA")
_DESHECHO, _VUELTA_AL_INICIAL, _DISCREPANCIA = (
    CLASES_CAMBIO[1],
    CLASES_CAMBIO[2],
    CLASES_CAMBIO[4],
)
_IDA_Y_VUELTA = CLASES_NO_VISTO[1]


@dataclass(frozen=True, slots=True)
class PasoEstado:
    """Un paso de `compras.documento_procesos`, lo justo para fechar el estado.

    `momento` va en hora de Madrid sin zona en el oráculo de la vista, y con
    zona (UTC) en el del contraste, que lo compara con las fotos.
    """

    orden: int
    destino: int | None
    momento: datetime | None


@dataclass(frozen=True, slots=True)
class FechaEstado:
    """Lo que la vista publica sobre la antigüedad del estado (R4-R8)."""

    en_estado_desde: datetime | None
    origen: str
    cambio_posterior_a: datetime | None


def _a_las_cero(dia: date | None) -> datetime | None:
    return None if dia is None else datetime.combine(dia, time())


def fecha_estado(
    tipo: int,
    estado: int | None,
    ultimo: PasoEstado | None,
    fecha_paso: date | None,
    fecha_alta: date | None,
) -> FechaEstado:
    """Desde cuándo está el documento en `estado`, y de dónde sale (R4-R8).

    `ultimo` es el paso con `es_ultimo` (None si el documento no tiene pasos) y
    `fecha_paso` su día, que manda cuando el paso no tiene hora (el
    `COALESCE(momento, fecha)` del SQL). El destino se compara con el estado
    como `IS NOT DISTINCT FROM`: un nulo explica un nulo.
    """
    if ultimo is not None:
        momento = ultimo.momento or _a_las_cero(fecha_paso)
        if ultimo.destino == estado:
            return FechaEstado(momento, _PASO, None)
        return FechaEstado(None, _FUERA_DE_PROCESO, momento)
    if estado in ESTADOS_INICIALES.get(tipo, frozenset()):
        return FechaEstado(_a_las_cero(fecha_alta), _ALTA, None)
    return FechaEstado(None, _FUERA_DE_PROCESO, None)


def dias_en_estado(desde: datetime | None, hoy: date) -> int | None:
    """Días de calendario desde `en_estado_desde` hasta `hoy` (R9).

    La vista lo calcula AL CONSULTAR con la fecha de hoy en Madrid; sin fecha
    (FUERA_DE_PROCESO, o ALTA sin fecha de alta) no hay días.
    """
    if desde is None:
        return None
    return (hoy - desde.date()).days


# ---------------------------------------------------------------------------
# El contraste con la foto diaria de F-067 (R13, R14). Aquí `momento` va con
# zona (UTC), como las fotos: el SQL del contraste ya entrega
# `momento AT TIME ZONE 'Europe/Madrid'`. Un paso SIN momento (uno solo en
# toda `documento_procesos` el 2026-10-08) no cae en ninguna ventana: no se
# sabe si fue antes o después de una foto.
# ---------------------------------------------------------------------------


def _hasta(pasos: Sequence[PasoEstado], fin: datetime) -> list[PasoEstado]:
    """Los pasos con `momento <= fin`, en el orden de su cadena."""
    return sorted(
        (p for p in pasos if p.momento is not None and p.momento <= fin),
        key=lambda p: p.orden,
    )


def clasificar_cambio(
    tipo: int,
    estado_nuevo: int | None,
    inicio: datetime,
    fin: datetime,
    pasos: Sequence[PasoEstado],
) -> str:
    """Cómo explica `rac` un cambio que vio la foto (R13).

    La ventana del cambio es (`inicio`, `fin`] = (`observado_antes`, `desde`]
    del tramo nuevo. En este orden:

    - PASO: un paso con destino `estado_nuevo` y `momento` dentro de la ventana.
    - DESHECHO: el último paso con `momento <= fin` ya lleva a `estado_nuevo`
      (se deshicieron los posteriores: la historia NETA de `rac`).
    - VUELTA_AL_INICIAL: ningún paso `<= fin` y `estado_nuevo` inicial del tipo.
    - FUERA_DE_PROCESO: el último paso `<= fin` lleva a otro estado y ningún
      paso posterior a `fin` lleva a `estado_nuevo`.
    - DISCREPANCIA: cualquier otro caso (p. ej. el paso existe, pero DESPUÉS
      de la foto que ya vio el estado: reloj o zona horaria).
    """
    if any(
        p.destino == estado_nuevo and p.momento is not None and inicio < p.momento <= fin
        for p in pasos
    ):
        return _PASO
    previos = _hasta(pasos, fin)
    if previos and previos[-1].destino == estado_nuevo:
        return _DESHECHO
    if not previos:
        if estado_nuevo in ESTADOS_INICIALES.get(tipo, frozenset()):
            return _VUELTA_AL_INICIAL
        return _DISCREPANCIA
    if any(
        p.destino == estado_nuevo and p.momento is not None and p.momento > fin
        for p in pasos
    ):
        return _DISCREPANCIA
    return _FUERA_DE_PROCESO


def clasificar_no_visto(
    estado_foto: int | None,
    abierto_en_la_foto: bool,
    fin: datetime,
    pasos: Sequence[PasoEstado],
) -> str:
    """Cómo explica `rac` los pasos de la ventana que la foto NO vio (R14).

    - ALTA: la foto de `fin` le abrió tramo (no de línea base): lo vio nacer
      ya en su estado.
    - IDA_Y_VUELTA: el último paso con `momento <= fin` deja el documento en
      `estado_foto` (se deshizo y se rehízo entre dos fotos).
    - DISCREPANCIA: cualquier otro caso.
    """
    if abierto_en_la_foto:
        return CLASES_NO_VISTO[0]
    previos = _hasta(pasos, fin)
    if previos and previos[-1].destino == estado_foto:
        return _IDA_Y_VUELTA
    return _DISCREPANCIA


# ---------------------------------------------------------------------------
# El informe del contraste (R15): una fila por noche, tipo, grupo y clase.
# ---------------------------------------------------------------------------

#: Los dos grupos del informe: lo que la foto VIO cambiar (R13) y los pasos de
#: la ventana que NO vio (R14). Comparten DISCREPANCIA, y por eso se separan.
GRUPOS_CONTRASTE: Final[tuple[str, ...]] = ("CAMBIO", "NO VISTO")

#: Los `documento_id` de DISCREPANCIA que se imprimen por noche, como mucho.
MAX_DISCREPANCIAS_POR_NOCHE: Final[int] = 50


@dataclass(frozen=True, slots=True)
class Contrastado:
    """Un documento de una noche del contraste, ya clasificado."""

    observado_en: datetime
    tipo: int
    grupo: str
    clase: str
    documento_id: int


def contrastar(
    cambios: Iterable[tuple[int, int, int | None, datetime, datetime]],
    no_vistos: Iterable[tuple[int, int, int | None, bool, datetime]],
    pasos: Mapping[int, Sequence[PasoEstado]],
) -> list[Contrastado]:
    """Clasifica cada cambio y cada no visto con sus pasos (R13, R14).

    `cambios` son `(documento_id, tipo, estado_nuevo, inicio, fin)` y
    `no_vistos`, `(documento_id, tipo, estado_foto, abierto_en_la_foto, fin)`:
    las filas de `SQL_CAMBIOS` y `SQL_NO_VISTOS`. La noche es `fin`.
    """
    resultado = [
        Contrastado(
            fin, tipo, GRUPOS_CONTRASTE[0],
            clasificar_cambio(tipo, estado, inicio, fin, pasos.get(ide, ())), ide,
        )
        for ide, tipo, estado, inicio, fin in cambios
    ]
    resultado += [
        Contrastado(
            fin, tipo, GRUPOS_CONTRASTE[1],
            clasificar_no_visto(estado, abierto, fin, pasos.get(ide, ())), ide,
        )
        for ide, tipo, estado, abierto, fin in no_vistos
    ]
    return resultado


def _utc(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _orden_clase(grupo: str, clase: str) -> int:
    clases = CLASES_CAMBIO if grupo == GRUPOS_CONTRASTE[0] else CLASES_NO_VISTO
    return clases.index(clase)


def discrepancias(contrastados: Sequence[Contrastado]) -> int:
    """Cuántos documentos quedan sin explicar: el código de salida es 1 si > 0."""
    return sum(1 for c in contrastados if c.clase == _DISCREPANCIA)


def formatear_contraste(
    contrastados: Sequence[Contrastado], noches: Sequence[datetime]
) -> str:
    """La tabla del contraste por noche (UTC), tipo, grupo y clase (R15).

    `noches` son las fotos posteriores a la línea base: una noche sin nada que
    contrastar se dice, no se omite. Detrás, los `documento_id` de cada
    DISCREPANCIA (como mucho `MAX_DISCREPANCIAS_POR_NOCHE` por noche) y el total.
    """
    cuenta = Counter(
        (c.observado_en, FAMILIAS_ESTADO.get(c.tipo, str(c.tipo)), c.grupo, c.clase)
        for c in contrastados
    )
    lineas = ["observado_en (UTC)  | tipo        | grupo    | clase             | documentos"]
    for noche in sorted(set(noches) | {c.observado_en for c in contrastados}):
        filas = sorted(
            (k for k in cuenta if k[0] == noche),
            key=lambda k: (k[1], GRUPOS_CONTRASTE.index(k[2]), _orden_clase(k[2], k[3])),
        )
        if not filas:
            lineas.append(f"{_utc(noche)} | sin cambios ni pasos que contrastar")
        for clave in filas:
            _, tipo, grupo, clase = clave
            lineas.append(
                f"{_utc(noche)} | {tipo:<11} | {grupo:<8} | {clase:<17} | {cuenta[clave]}"
            )
    discrepantes: dict[datetime, list[int]] = {}
    for c in contrastados:
        if c.clase == _DISCREPANCIA:
            discrepantes.setdefault(c.observado_en, []).append(c.documento_id)
    for noche in sorted(discrepantes):
        ids = sorted(discrepantes[noche])
        texto = ", ".join(str(i) for i in ids[:MAX_DISCREPANCIAS_POR_NOCHE])
        resto = len(ids) - MAX_DISCREPANCIAS_POR_NOCHE
        lineas.append(
            f"DISCREPANCIA {_utc(noche)}: {texto}" + (f" (y {resto} más)" if resto > 0 else "")
        )
    lineas.append(f"Resultado: {discrepancias(contrastados)} DISCREPANCIA sin explicar.")
    return "\n".join(lineas)
