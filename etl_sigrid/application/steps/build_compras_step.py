# etl_sigrid/application/steps/build_compras_step.py
"""
Step que materializa el schema `compras` (documentos de compra desde `raw`).

Encadena los archivos SQL en orden:
    00_setup.sql       - schema + funciones (serie, fecha, tipo de documento)
    01_documentos.sql  - contratos / albaranes / facturas (cabeceras + líneas)
    02_fact_linea.sql  - hechos unificados a nivel de línea
    03_views.sql       - vistas de negocio (consumo de contrato, proveedores…)

Solo lee de `raw.*`. No necesita `stg` ni `mart`.

POR QUÉ EXISTE ESTE FICHERO (F-047, absorbe F-044). `build-compras` ejecutaba
su SQL **en línea dentro del comando**, sin step, y por eso **no dejaba fila en
`_meta.etl_runs`**: su fecha de build no era consultable por SQL y el aviso de
frescura del diccionario no podía servir de nada —mandaba citar una fecha que
no existía—. Convertirlo en step es lo que hace que la carga nocturna pueda
registrarlo con el `batch_id` de la noche, como los demás.
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


class BuildComprasStep(PipelineStep):
    """Construye el schema `compras` (contratos, albaranes, facturas)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def name(self) -> str:
        return "build_compras"

    @property
    def stage(self) -> str:
        return "build_compras"

    @property
    def depends_on(self) -> list[str]:
        # Solo necesita raw.* (la ingesta). No depende de stage ni mart.
        return ["ingest_raw"]

    def run(self) -> StepResult:
        result = self._new_result()
        pg = build_postgres_client(self._settings)

        sql_dir = (
            Path(__file__).resolve().parents[2]
            / "infrastructure" / "postgres" / "sql" / "compras"
        )

        sub_steps: list[_SubStep] = [
            _SubStep(name="setup", sql_file="00_setup.sql"),
            _SubStep(
                name="documentos",
                sql_file="01_documentos.sql",
                target_schema="compras",
                target_table="contratos",
            ),
            _SubStep(
                name="fact_linea",
                sql_file="02_fact_linea.sql",
                target_schema="compras",
                target_table="fact_compras_linea",
            ),
            _SubStep(name="views", sql_file="03_views.sql"),
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
                    "compras_substep_failed",
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
                "compras_substep_done",
                sub_step=sub.name, rows=rows,
                duration_s=round((datetime.utcnow() - t0).total_seconds(), 2),
            )

        result.status = StepStatus.SUCCESS
        result.rows_processed = total_rows
        result.finished_at = datetime.utcnow()
        return result
