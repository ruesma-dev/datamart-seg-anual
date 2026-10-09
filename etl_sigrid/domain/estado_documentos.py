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

EL CONTRASTE con la foto diaria de F-067 (`clasificar_cambio`, `contrastar`...)
vivió aquí durante la Fase A: con 2 noches y 0 discrepancias el humano decidió
BORRAR la foto (Fase B, D7, 2026-10-09), y el contraste se fue con ella.

LA REGLA LA EJECUTA SQL (`sql/compras/13_estado_documentos.sql`), y aquí está
escrita **una sola vez** como oráculo puro: los literales —las familias, los
estados iniciales y los tres orígenes— viven aquí y `tests/test_f132_sql.py`
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
