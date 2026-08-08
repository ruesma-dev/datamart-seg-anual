# etl_sigrid/infrastructure/postgres/timings.py
"""
Lectura y formato de los tiempos por paso guardados en `_meta.etl_runs`.

Es la respuesta a la pregunta que decide F-011: ¿aguanta `Standard_B1ms`
(1 vCPU, 2 GB) la carga completa, o hay que escalar el SKU? Sin una tabla de
tiempos por paso, esa decisión se toma a ojo.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Timing:
    """Una fila de `_meta.etl_runs` vista como medición."""

    stage: str
    step: str
    started_at: datetime | None
    finished_at: datetime | None
    status: str
    rows_processed: int

    @property
    def duration_seconds(self) -> float:
        """Duración en segundos. 0 si el paso no llegó a cerrarse."""
        if self.started_at is None or self.finished_at is None:
            return 0.0
        return (self.finished_at - self.started_at).total_seconds()


_CABECERA = (
    f"{'etapa':<12} {'paso':<20} {'inicio':<19} "
    f"{'duración_s':>12} {'filas':>12}  estado"
)


def format_timings(timings: Sequence[Timing]) -> str:
    """
    Tabla legible, en orden cronológico y con el total al pie.

    Función pura: recibe la lista y devuelve texto. Así se puede comprobar el
    formato sin BBDD.
    """
    if not timings:
        return (
            "Sin mediciones en _meta.etl_runs. ¿Se ha ejecutado ya "
            "`python main.py run-all`?"
        )

    ordenados = sorted(
        timings,
        key=lambda t: (t.started_at is None, t.started_at or datetime.min),
    )

    lineas = [_CABECERA, "-" * len(_CABECERA)]
    total_s = 0.0
    total_filas = 0

    for t in ordenados:
        inicio = t.started_at.strftime("%Y-%m-%d %H:%M:%S") if t.started_at else "-"
        lineas.append(
            f"{t.stage:<12} {t.step:<20} {inicio:<19} "
            f"{t.duration_seconds:>12.1f} {t.rows_processed:>12,}  {t.status}"
        )
        total_s += t.duration_seconds
        total_filas += t.rows_processed

    lineas.append("-" * len(_CABECERA))
    lineas.append(
        f"{'TOTAL':<12} {'':<20} {'':<19} {total_s:>12.1f} {total_filas:>12,}"
    )
    return "\n".join(lineas)
