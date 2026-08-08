# etl_sigrid/application/steps/build_maestros_step.py
"""
Step que materializa el schema `maestro` (catálogos para consulta externa).

Encadena los archivos SQL en orden:
    00_setup.sql            - schema maestro + helper de fecha (idempotente)
    01_obras.sql            - vista maestro.obras (código, nombre, cliente)
    02_proveedores.sql      - vista maestro.proveedores (global, con CIF y dir.)
    03_proveedores_obra.sql - vista maestro.proveedores_obra (vía ctr)

INDEPENDIENTE del seguimiento/cierre. Solo lee de raw.* (con, obr, prv, ctr,
condir, auxpro, auxmun). Requiere únicamente que la ingesta (raw) esté hecha;
no necesita stage ni mart. Por eso se ejecuta como comando aparte
(`python main.py build-maestros`) y NO forma parte de run-all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from config.settings import Settings
from etl_sigrid.application.steps.base import PipelineStep
from etl_sigrid.domain.entities import StepResult, StepStatus
from etl_sigrid.infrastructure.logging_config import get_logger
from etl_sigrid.infrastructure.postgres.client_factory import build_postgres_client

logger = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class _SubStep:
    name: str
    sql_file: str
    target_schema: str | None = None
    target_table: str | None = None


class BuildMaestrosStep(PipelineStep):
    """Construye el schema `maestro` (obras / proveedores / proveedores-obra)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def name(self) -> str:
        return "build_maestros"

    @property
    def stage(self) -> str:
        return "build_maestros"

    @property
    def depends_on(self) -> list[str]:
        # Solo necesita raw.* (la ingesta). No depende de stage ni mart.
        return ["ingest_raw"]

    def run(self) -> StepResult:
        result = self._new_result()
        pg = build_postgres_client(self._settings)

        sql_dir = (
            Path(__file__).resolve().parents[2]
            / "infrastructure" / "postgres" / "sql" / "maestro"
        )

        sub_steps: list[_SubStep] = [
            _SubStep(name="setup", sql_file="00_setup.sql"),
            _SubStep(
                name="obras",
                sql_file="01_obras.sql",
                target_schema="maestro",
                target_table="obras",
            ),
            _SubStep(
                name="proveedores",
                sql_file="02_proveedores.sql",
                target_schema="maestro",
                target_table="proveedores",
            ),
            _SubStep(
                name="proveedores_obra",
                sql_file="03_proveedores_obra.sql",
                target_schema="maestro",
                target_table="proveedores_obra",
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
                    "maestros_substep_failed",
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
                "maestros_substep_done",
                sub_step=sub.name, rows=rows,
                duration_s=round((datetime.utcnow() - t0).total_seconds(), 2),
            )

        result.status = StepStatus.SUCCESS
        result.rows_processed = total_rows
        result.finished_at = datetime.utcnow()
        return result
