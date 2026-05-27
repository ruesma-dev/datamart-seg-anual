# etl_sigrid/application/steps/build_cierre_step.py
"""
Step que materializa el schema `cierre` (Tanda 1.4 — FINAL desde master CIERRE).

Encadena los archivos SQL en orden:
    00_setup.sql      - PERSISTENTE: schema + funciones (parseo mes, fase, master)
    01_ddl_fact.sql   - DROP + CREATE de cierre.fact_cierre_mensual
    02_build_fact.sql - INSERT del fact con la lógica:
                          · EJECUTADO desde stg.plan_mensual amb 3/7 fas>=1
                          · FINAL desde versión master CIERRE del mes
                            (amb 8/11), fallback a fase 0 si no hay master
    03_views.sql      - Vistas Power BI

El schema cierre es INDEPENDIENTE de mart. Lee stg.plan_mensual + stg.fases
+ stg.partidas, sin modificar nada del data mart principal.
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
            / "infrastructure"
            / "postgres"
            / "sql"
            / "cierre"
        )

        sub_steps: list[_SubStep] = [
            _SubStep(name="setup",      sql_file="00_setup.sql"),
            _SubStep(name="ddl_fact",   sql_file="01_ddl_fact.sql"),
            _SubStep(
                name="build_fact",
                sql_file="02_build_fact.sql",
                target_schema="cierre",
                target_table="fact_cierre_mensual",
            ),
            _SubStep(name="views",      sql_file="03_views.sql"),
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
                    sub_step=sub.name,
                    duration_s=duration,
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
                "cierre_substep_done",
                sub_step=sub.name,
                rows=rows,
                duration_s=round((datetime.utcnow() - t0).total_seconds(), 2),
            )

        result.status = StepStatus.SUCCESS
        result.rows_processed = total_rows
        result.finished_at = datetime.utcnow()
        return result
