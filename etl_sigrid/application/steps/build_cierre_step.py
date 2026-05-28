# etl_sigrid/application/steps/build_cierre_step.py
"""
Step que materializa el schema `cierre` (Tanda 2 — añade detalle fino).

Encadena los archivos SQL en orden:
    00_setup.sql          - schema + funciones helper (idempotente)
    01_ddl_fact.sql       - DROP + CREATE cierre.fact_cierre_mensual
    02_build_fact.sql     - INSERT del fact con EJECUTADO + FINAL master/fase0
    03_views.sql          - Vista principal v_pbi_cierre_resumen
    04_views_detalle.sql  - (NUEVO) Vistas de detalle:
                              · v_pbi_cierre_indirectos_detalle
                              · v_pbi_cierre_generales_detalle
                              · v_pbi_dim_subcategoria_ci
                              · v_pbi_dim_tipologia_cp

INDEPENDIENTE del mart principal. Solo lee de stg.*.
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
    name: str
    sql_file: str
    target_schema: str | None = None
    target_table: str | None = None


class BuildCierreStep(PipelineStep):
    """Construye el schema `cierre` (visual cierre mensual de obra)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def name(self) -> str:
        return "build_cierre"

    @property
    def stage(self) -> str:
        return "build_cierre"

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

        sql_dir = (
            Path(__file__).resolve().parents[2]
            / "infrastructure" / "postgres" / "sql" / "cierre"
        )

        sub_steps: list[_SubStep] = [
            _SubStep(name="setup",         sql_file="00_setup.sql"),
            _SubStep(name="ddl_fact",      sql_file="01_ddl_fact.sql"),
            _SubStep(
                name="build_fact",
                sql_file="02_build_fact.sql",
                target_schema="cierre",
                target_table="fact_cierre_mensual",
            ),
            _SubStep(name="views",         sql_file="03_views.sql"),
            _SubStep(name="views_detalle", sql_file="04_views_detalle.sql"),
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
                    "cierre_substep_failed",
                    sub_step=sub.name, duration_s=duration, exc_info=True,
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
                "cierre_substep_done",
                sub_step=sub.name, rows=rows,
                duration_s=round((datetime.utcnow() - t0).total_seconds(), 2),
            )

        result.status = StepStatus.SUCCESS
        result.rows_processed = total_rows
        result.finished_at = datetime.utcnow()
        return result
