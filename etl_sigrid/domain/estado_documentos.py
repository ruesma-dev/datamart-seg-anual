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

LOS ALBARANES (tipo 14, con proformas y notas; F-153) entran en la vista sin
pasos en `compras.documento_procesos` hasta F-133, y `rac` casi nunca registra
el paso a FACTURADO. Dos orígenes más:

- **FACTURACION**: tipo 14, estado 10 y `fecha_facturacion` informada → la fecha
  es ese día a las 00:00 (`dca.fecfac`; de día, y no es la de la factura).
- **SIN_HISTORIAL**: tipo 14 sin un solo paso publicado y sin los casos
  anteriores → no hay fecha ni cota, y no se afirma que el estado cambiase
  fuera de un proceso: el paso puede existir en `rac` (COM y CON).

ES LA HISTORIA NETA (D2 del humano): «Deshacer proceso» BORRA el paso de `rac`,
así que un estado al que se vuelve deshaciendo cuenta desde el paso que llevó a
él la primera vez. La fecha del deshacer está en `dbo.log` (F-105), no aquí.

EL CONTRASTE con la foto diaria de F-067 (`clasificar_cambio`, `contrastar`...)
vivió aquí durante la Fase A: con 2 noches y 0 discrepancias el humano decidió
BORRAR la foto (Fase B, D7, 2026-10-09), y el contraste se fue con ella.

LA REGLA LA EJECUTA SQL (`sql/compras/13_estado_documentos.sql`), y aquí está
escrita **una sola vez** como oráculo puro: los literales —las familias, los
estados iniciales y los cinco orígenes— viven aquí y `tests/test_f132_sql.py`
comprueba que el SQL lleva LOS MISMOS. Mismo patrón que
`domain/documento_procesos.py` (F-085).

Capa `domain`: sin un solo import de infraestructura ni de configuración.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Final

#: Las familias de la vista (`con.tip`) y su nombre publicado (D3 del humano):
#: contrato, factura y comparativo. Las obras no: su estado es de `maestro`.
FAMILIAS_ESTADO: Final[dict[int, str]] = {
    44: "CONTRATO",
    15: "FACTURA",
    46: "COMPARATIVO",
}

#: El tipo de los albaranes (`con.tip`). NO está en `FAMILIAS_ESTADO`: su
#: `tipo_documento` publicado no es uno, sino el de `compras.albaranes` (F-153, D2).
TIPO_ALBARAN: Final[int] = 14

#: FAC, Facturado: el único estado del tipo 14 que fecha `dca.fecfac` (F-153, D1).
ESTADO_FACTURADO_ALBARAN: Final[int] = 10

#: Los valores de `compras.fn_tipo_documento` para el tipo 14.
TIPOS_DOCUMENTO_ALBARAN: Final[tuple[str, ...]] = ("ALBARAN", "PROFORMA", "NOTA", "OTRO")

#: Familias cuyos pasos aún no están en `compras.documento_procesos`. F-133 la
#: vacía; hasta entonces, sus documentos sin paso son SIN_HISTORIAL (F-153, D3).
FAMILIAS_SIN_HISTORIAL: Final[frozenset[int]] = frozenset({TIPO_ALBARAN})

#: Los estados INICIALES de cada familia: medidos el 2026-10-08, son los de
#: TODOS los documentos sin un solo paso en `rac` (factura 1 y 20, contrato 1,
#: comparativo 1, 11 y 100). Un documento sin pasos en otro estado cambió fuera
#: de un proceso. El albarán, medido el 2026-11-02: los 7.689 PDT, 0 con pasos.
ESTADOS_INICIALES: Final[dict[int, frozenset[int]]] = {
    15: frozenset({1, 20}),
    44: frozenset({1}),
    46: frozenset({1, 11, 100}),
    TIPO_ALBARAN: frozenset({1}),
}

#: De dónde sale `en_estado_desde` (R4-R6; F-153 R7), en el orden en que se decide.
ORIGENES_FECHA: Final[tuple[str, ...]] = (
    "PASO",
    "FACTURACION",
    "ALTA",
    "SIN_HISTORIAL",
    "FUERA_DE_PROCESO",
)
_PASO, _FACTURACION, _ALTA, _SIN_HISTORIAL, _FUERA_DE_PROCESO = ORIGENES_FECHA


@dataclass(frozen=True, slots=True)
class PasoEstado:
    """Un paso de `compras.documento_procesos`, lo justo para fechar el estado.

    `momento` va en hora de Madrid sin zona, como `documento_procesos.momento`.
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
    fecha_facturacion: date | None = None,
) -> FechaEstado:
    """Desde cuándo está el documento en `estado`, y de dónde sale (R4-R8).

    `ultimo` es el paso con `es_ultimo` (None si el documento no tiene pasos) y
    `fecha_paso` su día, que manda cuando el paso no tiene hora (el
    `COALESCE(momento, fecha)` del SQL). El destino se compara con el estado
    como `IS NOT DISTINCT FROM`: un nulo explica un nulo. `fecha_facturacion`
    (`dca.fecfac`) solo cuenta en el tipo 14 y el estado 10 (F-153, R7).
    """
    momento = None
    if ultimo is not None:
        momento = ultimo.momento or _a_las_cero(fecha_paso)
        if ultimo.destino == estado:
            return FechaEstado(momento, _PASO, None)
    if (
        tipo == TIPO_ALBARAN
        and estado == ESTADO_FACTURADO_ALBARAN
        and fecha_facturacion is not None
    ):
        return FechaEstado(_a_las_cero(fecha_facturacion), _FACTURACION, None)
    if ultimo is None:
        if estado in ESTADOS_INICIALES.get(tipo, frozenset()):
            return FechaEstado(_a_las_cero(fecha_alta), _ALTA, None)
        if tipo in FAMILIAS_SIN_HISTORIAL:
            return FechaEstado(None, _SIN_HISTORIAL, None)
    return FechaEstado(None, _FUERA_DE_PROCESO, momento)


def dias_en_estado(desde: datetime | None, hoy: date) -> int | None:
    """Días de calendario desde `en_estado_desde` hasta `hoy` (R9).

    La vista lo calcula AL CONSULTAR con la fecha de hoy en Madrid; sin fecha
    (FUERA_DE_PROCESO, SIN_HISTORIAL, o ALTA sin fecha de alta) no hay días.
    """
    if desde is None:
        return None
    return (hoy - desde.date()).days
