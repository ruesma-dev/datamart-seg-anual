# etl_sigrid/application/steps/build_mart_step.py
"""
Step que materializa el esquema mart.* a partir de stg.*.

Flujo:
    1. Asegura schema mart (idempotente, vía PostgresClient auto-bootstrap).
    2. Ejecuta en orden los archivos SQL de sql/mart/:
        01_ddl.sql           - DROP + CREATE mart.fact_seguimiento_mensual
        02_build_fact.sql    - TRUNCATE + INSERT con la lógica de comparativa

Cada sub-step se registra en logs con tiempo y filas procesadas.

NOTA: este step depende solo de stg. La integración con aux (Excel de
tipo_partida, etc.) se hará en una iteración posterior cuando carguemos
los Excels de Negocio.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from config.settings import Settings
from etl_sigrid.application.steps.base import PipelineStep
from etl_sigrid.domain.entities import StepResult, StepStatus
from etl_sigrid.infrastructure.logging_config import get_logger
from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

logger = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class _SubStep:
    """Un sub-paso: un archivo SQL + (opcionalmente) la tabla destino para contar filas."""

    name: str
    sql_file: str
    target_schema: str | None = None
    target_table: str | None = None


class BuildMartStep(PipelineStep):
    """Construye el esquema mart desde stg."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def name(self) -> str:
        return "build_mart"

    @property
    def stage(self) -> str:
        return "build_mart"

    @property
    def depends_on(self) -> list[str]:
        return ["build_stg"]

    def run(self) -> StepResult:
        result = self._new_result()
        pg = PostgresClient(
            conninfo=self._settings.postgres.conninfo,
            admin_conninfo=self._settings.postgres.admin_conninfo,
            target_db=self._settings.postgres.db,
        )

        sql_dir = Path(__file__).resolve().parents[2] / "infrastructure" / "postgres" / "sql" / "mart"

        sub_steps: list[_SubStep] = [
            _SubStep(name="ddl", sql_file="01_ddl.sql"),
            _SubStep(
                name="build_fact",
                sql_file="02_build_fact.sql",
                target_schema="mart",
                target_table="fact_seguimiento_mensual",
            ),
            _SubStep(
                name="agg_categoria",
                sql_file="03_agg_categoria.sql",
                target_schema="mart",
                target_table="fact_seguimiento_categoria",
            ),
            _SubStep(
                name="view_periodificado",
                sql_file="04_view_periodificado.sql",
                # No es tabla; no cuenta filas
            ),
            _SubStep(
                name="views_powerbi",
                sql_file="05_views_powerbi.sql",
                # Vistas, no cuenta filas
            ),
        ]

        total_rows = 0
        for sub in sub_steps:
            sql_path = sql_dir / sub.sql_file
            if not sql_path.exists():
                result.status = StepStatus.FAILED
                result.error_message = f"SQL file no encontrado: {sql_path}"
                result.finished_at = datetime.utcnow()
                return result

            t0 = datetime.utcnow()
            try:
                pg.execute_sql_file(sql_path)
            except Exception as e:  # noqa: BLE001
                duration = (datetime.utcnow() - t0).total_seconds()
                logger.error(
                    "mart_substep_failed", sub_step=sub.name, duration_s=duration,
                    exc_info=True,
                )
                result.status = StepStatus.FAILED
                result.error_message = f"Fallo en {sub.name}: {e}"
                result.finished_at = datetime.utcnow()
                return result

            rows = 0
            if sub.target_schema and sub.target_table:
                rows = pg.count_rows(sub.target_schema, sub.target_table)
                total_rows += rows
            logger.info(
                "mart_substep_done",
                sub_step=sub.name,
                rows=rows,
                duration_s=round((datetime.utcnow() - t0).total_seconds(), 2),
            )

        result.status = StepStatus.SUCCESS
        result.rows_processed = total_rows
        result.finished_at = datetime.utcnow()
        return result
