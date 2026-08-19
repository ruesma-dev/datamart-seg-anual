# etl_sigrid/infrastructure/postgres/step_run_recorder.py
"""
Adaptador que persiste el resultado de cada paso en `_meta.etl_runs`.

Implementa el puerto `etl_sigrid.application.ports.StepRunRecorder`. La tabla
ya existía con todas las columnas necesarias (`sql/ddl/00_meta.sql`): esta
feature no cambia su DDL, solo la usa para lo que estaba pensada.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from etl_sigrid.domain.entities import StepResult

if TYPE_CHECKING:  # pragma: no cover - solo para anotaciones
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient


class PostgresStepRunRecorder:
    """Graba en `_meta.etl_runs` una fila por paso terminado."""

    def __init__(self, client: PostgresClient, batch_id: str | None = None) -> None:
        self._client = client
        self._batch_id = batch_id

    def record(self, stage: str, result: StepResult) -> None:
        """Inserta la fila. Quien llama envuelve esto en try/except (R29)."""
        self._client.record_run_completed(
            stage=stage,
            step=result.step_name,
            started_at=result.started_at,
            finished_at=result.finished_at,
            status=result.status.value,
            rows_processed=result.rows_processed,
            error_message=result.error_message,
            metadata=result.metadata or None,
            batch_id=self._batch_id,
        )
