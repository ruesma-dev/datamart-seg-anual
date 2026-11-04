# etl_sigrid/domain/postventa.py
"""
POSTVENTA (F-156): las unidades postventa (`upv`, `con.tip` 707), las
incidencias —la reclamación de Sigrid, `rcp`, `con.tip` 708, el «parte de
reclamación» de Posventa—, sus tareas (`tar`, `con.tip` 47), su histórico, sus
gráficos y el coste de las obras de postventa ligado a la obra de origen.
Mediciones en solo lectura del 2026-11-03: `progress/spec_F-156.md`.

LA REGLA LA EJECUTA SQL (`sql/postventa/`) y la ingesta la filtra en origen
(`config/tables_sigrid.yaml`). Aquí está escrita **una sola vez** como oráculo
puro: tipos, estados, la máscara del texto libre (D10), el origen de la fecha
del estado (R15), las familias de adjuntos (R20) y la obra de origen de una
partida (R25). `tests/test_f156_ingesta_sql.py` comprueba que el YAML y el SQL
llevan LOS MISMOS literales. Mismo patrón que `domain/documento_adjuntos.py`.

Capa `domain`: sin un solo import de infraestructura ni de configuración.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from datetime import date, datetime
from typing import Final

# ---------------------------------------------------------------------------
# Tipos de documento (`con.tip`) y estados (`conest`, por la pareja tipo-estado)
# ---------------------------------------------------------------------------

TIPO_UNIDAD: Final[int] = 707
TIPO_INCIDENCIA: Final[int] = 708
TIPO_TAREA: Final[int] = 47
#: Ordenados: el literal del `IN (...)` del SQL es determinista.
TIPOS_POSTVENTA: Final[tuple[int, ...]] = tuple(sorted((TIPO_UNIDAD, TIPO_INCIDENCIA, TIPO_TAREA)))

#: 708: 1 SAT Sin atender, 3 PTE Pendiente (abiertas); 5 TER Terminada, 7 NPR No
#: procede, 9 CER Cerrada (resueltas).
ESTADO_ALTA: Final[int] = 1
ESTADOS_ABIERTOS: Final[tuple[int, ...]] = (1, 3)
ESTADOS_RESOLUCION: Final[tuple[int, ...]] = (5, 7, 9)
ESTADO_CERRADA: Final[int] = 9

# ---------------------------------------------------------------------------
# R8 · el fin de la garantía que aplica a cada clase de incidencia
# ---------------------------------------------------------------------------

#: Clase de incidencia (`auxrcp.cod`) -> columna de `upv` con el fin de su
#: garantía. 0001 Vicios o defectos -> `fecfin1`; 0002 Habitabilidad /
#: Instalaciones -> `fecfin2`. 0003 Estructura NO tiene fin en Sigrid (solo
#: `fecini3`) y una incidencia sin clase (15.229 de 22.179) tampoco.
CLASE_FIN_GARANTIA: Final[dict[str, str]] = {"0001": "fecfin1", "0002": "fecfin2"}


def fin_garantia(clase: str | None, fecfin1: date | None, fecfin2: date | None) -> date | None:
    """El fin de la garantía de la clase de la incidencia, o None (R8)."""
    columna = CLASE_FIN_GARANTIA.get((clase or "").strip())
    if columna == "fecfin1":
        return fecfin1
    if columna == "fecfin2":
        return fecfin2
    return None


def dentro_garantia(fecha_alta: date | None, fin: date | None) -> bool | None:
    """Cierto si el alta es ANTERIOR O IGUAL al fin; None si falta uno de los dos (R8)."""
    if fecha_alta is None or fin is None:
        return None
    return fecha_alta <= fin


# ---------------------------------------------------------------------------
# R13 · la máscara del texto libre del esquema general (D10)
# ---------------------------------------------------------------------------

MARCA_TELEFONO: Final[str] = "[TELEFONO]"
MARCA_CORREO: Final[str] = "[CORREO]"
#: Los tres patrones, escritos para que valgan IGUAL en Python y en el ARE de
#: PostgreSQL (`[0-9]` y no `\d`, que en Python casa cifras Unicode). El SQL de
#: `postventa.fn_enmascarar` los lleva literales y en este orden: el correo
#: primero, para que un correo con cifras no quede partido.
PATRON_CORREO: Final[str] = r"[^\s@]+@[^\s@]+\.[^\s@]+"
PATRON_TELEFONO: Final[str] = r"[6-9][0-9]{8}"
PATRON_TELEFONO_GRUPOS: Final[str] = r"[6-9][0-9]{2} [0-9]{2} [0-9]{2} [0-9]{2}"

_MASCARA: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (re.compile(PATRON_CORREO), MARCA_CORREO),
    (re.compile(PATRON_TELEFONO), MARCA_TELEFONO),
    (re.compile(PATRON_TELEFONO_GRUPOS), MARCA_TELEFONO),
)


def enmascarar(texto: str | None) -> str | None:
    """El texto con los correos y los teléfonos españoles cambiados por su marca (R13).

    Heurística (D10): nueve cifras que empiezan por 6, 7, 8 o 9, seguidas o en
    grupos 3-2-2-2 separados por un espacio. No toca DNI ni nombres: los nombres
    de quien reclama no están en el texto medido, y por eso viven en
    `postventa_restringida`.
    """
    if texto is None:
        return None
    for patron, marca in _MASCARA:
        texto = patron.sub(marca, texto)
    return texto


# ---------------------------------------------------------------------------
# R15-R16 · desde cuándo está una incidencia en su estado
# ---------------------------------------------------------------------------

#: En el orden en que se deciden (R15).
ORIGENES_FECHA: Final[tuple[str, ...]] = ("PASO", "CIERRE_APLICACION", "ALTA", "SIN_HISTORIAL")

#: El texto con que la aplicación `postventa-incidencias` deja en `dbo.log` sus
#: cierres: escribe `con.est` = 9 y esa línea, NO un paso de `rac` (D8).
TEXTO_CIERRE_APLICACION: Final[str] = "Cerrar parte (postventa-incidencias)"


def origen_fecha(
    estado: int | None,
    destino_ultimo_paso: int | None,
    momento_ultimo_paso: datetime | None,
    momento_cierre_aplicacion: datetime | None,
) -> str:
    """De dónde sale la fecha del estado actual (R15), por este orden.

    `destino_ultimo_paso` es el estado al que llevó el ÚLTIMO paso de `rac` (None
    si no hay pasos) y `momento_cierre_aplicacion` el del último cierre de la
    aplicación (None si no hay).

    - PASO: el último paso dejó la incidencia en su estado.
    - CIERRE_APLICACION: está cerrada y la aplicación la cerró DESPUÉS del último
      paso (o no hay paso, o el paso no tiene momento).
    - ALTA: sin pasos y en el estado inicial.
    - SIN_HISTORIAL: lo demás (un cambio sin proceso: borrado por «Deshacer»).
    """
    if destino_ultimo_paso is not None and destino_ultimo_paso == estado:
        return "PASO"
    if (
        estado == ESTADO_CERRADA
        and momento_cierre_aplicacion is not None
        and (momento_ultimo_paso is None or momento_cierre_aplicacion > momento_ultimo_paso)
    ):
        return "CIERRE_APLICACION"
    if destino_ultimo_paso is None and estado == ESTADO_ALTA:
        return "ALTA"
    return "SIN_HISTORIAL"


def esta_abierta(estado: int | None) -> bool:
    """Cierto si la incidencia está sin atender o pendiente (R16)."""
    return estado in ESTADOS_ABIERTOS


def es_resolucion(estado: int | None) -> bool:
    """Cierto si el estado la resuelve: terminada, no procede o cerrada (R16)."""
    return estado in ESTADOS_RESOLUCION


def dias_abierta(
    fecha_alta: date | None, fecha_resolucion: date | None, abierta: bool, hoy: date,
) -> int | None:
    """Días desde el alta hasta hoy si está abierta, o hasta su resolución (R16)."""
    if fecha_alta is None:
        return None
    if abierta:
        return (hoy - fecha_alta).days
    if fecha_resolucion is None:
        return None
    return (fecha_resolucion - fecha_alta).days


# ---------------------------------------------------------------------------
# R20 · familias de los gráficos (adjuntos)
# ---------------------------------------------------------------------------

#: La clase de gráfico (`auxgra.ide`) PV002 «Fotos Reparaciones»: en una
#: incidencia es el PARTE FIRMADO por el cliente, con su DNI manuscrito (D9).
GRATIPIDE_REPARACION: Final[int] = 35

FAMILIAS_ADJUNTOS: Final[tuple[str, ...]] = ("INCIDENCIA", "REPARACION", "UNIDAD", "TAREA")

#: De qué tabla sale el documento de cada familia para `abrir_adjunto` del MCP
#: (R22). `REPARACION` apunta a `postventa_restringida` a propósito: solo la
#: abren el perfil postventa y el total (D9).
ORIGEN_POR_FAMILIA: Final[dict[str, str]] = {
    "INCIDENCIA": "postventa.incidencias.incidencia_id",
    "UNIDAD": "postventa.unidades.unidad_id",
    "TAREA": "postventa.tareas.tarea_id",
    "REPARACION": "postventa_restringida.contactos_incidencia.incidencia_id",
}


def familia_adjunto(tip: int | None, gratipide: int | None) -> str | None:
    """La familia de un enlace de gráfico de postventa, o None si no lo es (R20)."""
    if tip == TIPO_UNIDAD:
        return "UNIDAD"
    if tip == TIPO_TAREA:
        return "TAREA"
    if tip == TIPO_INCIDENCIA:
        return "REPARACION" if gratipide == GRATIPIDE_REPARACION else "INCIDENCIA"
    return None


# ---------------------------------------------------------------------------
# R25 · la obra de origen de una partida de una obra de postventa (D4)
# ---------------------------------------------------------------------------

LIGAS_COSTE: Final[tuple[str, ...]] = ("PARTIDA", "ANCESTRO", "SIN_OBRA")

#: Tres o cuatro cifras al principio y que no sigan más cifras: `0561 `,
#: `0593B`, `0613-B`, `626`. Vale igual en Python y en el ARE de PostgreSQL
#: (que admite `(?!...)`); el SQL la aplica tras `btrim`.
PATRON_OBRA_PARTIDA: Final[str] = r"^([0-9]{3,4})(?![0-9])"
_RE_OBRA_PARTIDA: Final[re.Pattern[str]] = re.compile(PATRON_OBRA_PARTIDA)


def obra_de_partida(codigo: str | None) -> str | None:
    """El código de obra que lleva el código de una partida, a 4 con ceros, o None."""
    if codigo is None:
        return None
    casa = _RE_OBRA_PARTIDA.search(codigo.strip())
    return casa.group(1).zfill(4) if casa else None


def liga_coste(
    cadena_de_codigos: Sequence[str | None], obras: Collection[str] | None = None,
) -> tuple[str, str | None]:
    """Cómo liga una partida con su obra de origen (R25).

    `cadena_de_codigos` es el código de la partida y los de sus ancestros, del
    más cercano al más lejano. Gana el primero que lleve una obra (y, si se da
    `obras`, una que exista en la empresa): PARTIDA si es la propia partida,
    ANCESTRO si es un antecesor; si ninguno, SIN_OBRA.
    """
    for nivel, codigo in enumerate(cadena_de_codigos):
        obra = obra_de_partida(codigo)
        if obra is not None and (obras is None or obra in obras):
            return ("PARTIDA" if nivel == 0 else "ANCESTRO"), obra
    return "SIN_OBRA", None


# ---------------------------------------------------------------------------
# Ingesta (R1-R3) y datos personales (R11, R24)
# ---------------------------------------------------------------------------

#: Lo ÚNICO que se trae de `per` (R3): la persona, su nombre, sus dos teléfonos y
#: su correo. Solo lo lee `postventa_restringida` (D1 = A, «d1 ok»).
COLUMNAS_PER: Final[tuple[str, ...]] = ("ide", "nom", "tel", "tel2", "ele")

#: Lo que de `per` no entra NUNCA: el DNI, las credenciales de i-Sigrid, las
#: direcciones y las observaciones (R3, R24).
COLUMNAS_PER_PROHIBIDAS: Final[frozenset[str]] = frozenset({
    "dni", "esiglog", "esigpas", "esigips", "esigper", "esigtel", "clamai", "recema",
    "dir", "dir1", "dir2", "dircpo", "dirtex", "munide", "proide", "paiide", "tex",
})

#: Palabras que no pueden aparecer en un nombre de columna del esquema GENERAL
#: `postventa` (R11): eso es de `postventa_restringida`.
PALABRAS_PROHIBIDAS_GENERAL: Final[tuple[str, ...]] = (
    "telefono", "correo", "dni", "reclamante", "contacto", "propietario_nombre",
)


def filtro_tar() -> str:
    """El `where` de `tar`: solo las tareas de una reclamación (R1)."""
    return "rcpide > 0"


def filtro_tarres() -> str:
    """El `where` de `tarres`: el recurso de las tareas de reclamación (R1)."""
    return f"taride IN (SELECT ide FROM dbo.tar WHERE {filtro_tar()})"


def filtro_log() -> str:
    """El `where` de `log`: solo los cierres de la aplicación de Posventa (R2, D8)."""
    return (
        f"tab = 'con' AND tip = {TIPO_INCIDENCIA} "
        f"AND tex LIKE '{TEXTO_CIERRE_APLICACION}%'"
    )


def filtro_per() -> str:
    """El `where` de `per`: solo quien reclama, el contacto y el de la unidad (R3)."""
    return (
        "ide IN (SELECT recide FROM dbo.rcp UNION SELECT cntide FROM dbo.rcp "
        "UNION SELECT peride FROM dbo.upv)"
    )
