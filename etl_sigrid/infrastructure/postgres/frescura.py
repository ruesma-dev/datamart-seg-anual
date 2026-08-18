# etl_sigrid/infrastructure/postgres/frescura.py
"""
Frescura del datamart: la forma de una fila de `_meta.v_frescura` y el formato
con el que se enseña (F-024).

Responde a la pregunta que hoy no tiene respuesta desde fuera del ETL: lo que
estoy viendo en Power BI, ¿es de esta noche o de hace tres días?

Mismo patrón que `timings.py`: puro, sin BBDD. El cliente lee las filas; aquí
solo se les da forma y se emite el veredicto.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class FilaFrescura:
    """Una fila de `_meta.v_frescura`.

    «Último OK» y «último intento» van por separado a propósito: un
    `build_mart` que falló esta noche deja `mart` con lo de ayer, y quien lo
    consulta necesita las dos noticias, no una.
    """

    paso: str
    ultimo_ok_finished_at: datetime | None
    ultimo_ok_batch_id: str | None
    ultimo_ok_filas: int | None
    horas_desde_ultimo_ok: float | None
    ultimo_intento_started_at: datetime | None
    ultimo_intento_status: str | None
    ultimo_intento_error: str | None
