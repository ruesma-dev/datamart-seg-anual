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
from datetime import datetime, timedelta

#: Horas que puede llevar una fila en `RUNNING` antes de resultar sospechosa
#: (F-024, R6). Seis, y no tres: el pipeline completo tarda ~3 h 15 en el B1ms
#: y el timeout del job son 5 h. Por debajo de eso se estaría acusando de
#: huérfana a una carga que todavía puede estar trabajando.
UMBRAL_HUERFANA_HORAS = 6

#: El estado que dejan las filas que nadie cerró.
ESTADO_ABIERTO = "RUNNING"


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


def format_timings(
    timings: Sequence[Timing], ahora: datetime | None = None
) -> str:
    """
    Tabla legible, en orden cronológico y con el total al pie.

    Función pura: recibe la lista y devuelve texto. Así se puede comprobar el
    formato sin BBDD. `ahora` se inyecta por la misma razón: el aviso de
    huérfanas de R6 depende del reloj, y un test no puede esperar seis horas.

    El aviso va al PIE y no en una columna nueva (F-024): así no rompe a quien
    parsee la tabla ni a los tests de formato de F-005.
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

    aviso = _aviso_de_huerfanas(ordenados, ahora)
    if aviso:
        lineas.append("")
        lineas.append(aviso)

    return "\n".join(lineas)


def _aviso_de_huerfanas(
    timings: Sequence[Timing], ahora: datetime | None
) -> str:
    """Aviso al pie por las filas `RUNNING` demasiado antiguas (R6).

    `timings` es de SOLO LECTURA y contra Azure no escribe nada (DA-7): aquí
    solo se avisa. Quien las marca `ABORTED` es la siguiente ejecución que
    escriba, y el texto lo dice para que nadie salga a arreglarlo a mano.
    """
    instante = datetime.utcnow() if ahora is None else ahora
    limite = instante - timedelta(hours=UMBRAL_HUERFANA_HORAS)

    sospechosas = [
        t
        for t in timings
        if t.status == ESTADO_ABIERTO
        and t.started_at is not None
        and t.started_at < limite
    ]
    if not sospechosas:
        return ""

    return (
        f"AVISO: {len(sospechosas)} fila(s) {ESTADO_ABIERTO} desde hace más de "
        f"{UMBRAL_HUERFANA_HORAS} h: probablemente huérfanas de un proceso "
        f"muerto; la próxima ejecución que escriba las marcará ABORTED."
    )
