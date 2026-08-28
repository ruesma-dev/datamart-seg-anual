# etl_sigrid/application/steps/build_retenciones_step.py
"""
Step que materializa el schema `retenciones` (garantías retenidas y de cliente).

Encadena los archivos SQL en orden:
    00_setup.sql        - schema, función de fechas, catálogo de tipos y las dos
                          vistas fuente (`v_src_lineas_*`, creadas con SQL
                          dinámico según lo que exista en `raw`)
    01_movimientos.sql  - un registro por efecto de retención (ambos sentidos)
    02_views.sql        - vistas de saldo por entidad, obra, vivas y vencidas

Solo lee de `raw.*` (cob, pag, rec). No necesita `stg` ni `mart`.

POR QUÉ EXISTE ESTE FICHERO (F-047, absorbe F-044). Igual que `compras`:
`build-retenciones` ejecutaba su SQL en línea, sin step, así que **no dejaba
fila en `_meta.etl_runs`** y su frescura no era consultable por SQL. El aviso
del diccionario mandaba citar una fecha de build que nadie podía obtener.
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


#: Los tres ficheros SQL, EN ORDEN, y de qué tabla se cuentan filas.
#:
#: Vive fuera de `run()` por lo mismo que en `build_compras_step`: es DATO, y
#: sustituirla en un test es lo único que permite ejercitar el guardián de
#: `target_schema`/`target_table`.
SUB_PASOS: tuple[_SubStep, ...] = (
    _SubStep(
        name="setup",
        sql_file="00_setup.sql",
        target_schema="retenciones",
        target_table="tipos",
    ),
    _SubStep(
        name="movimientos",
        sql_file="01_movimientos.sql",
        target_schema="retenciones",
        target_table="movimientos",
    ),
    _SubStep(name="views", sql_file="02_views.sql"),
)


class BuildRetencionesStep(PipelineStep):
    """Construye el schema `retenciones` (movimientos y vistas de saldo)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def name(self) -> str:
        return "build_retenciones"

    @property
    def stage(self) -> str:
        return "build_retenciones"

    @property
    def depends_on(self) -> list[str]:
        # Solo necesita raw.* (la ingesta). No depende de stage ni mart.
        return ["ingest_raw"]

    def run(self) -> StepResult:
        result = self._new_result()
        pg = build_postgres_client(self._settings)

        sql_dir = (
            Path(__file__).resolve().parents[2]
            / "infrastructure" / "postgres" / "sql" / "retenciones"
        )

        total_rows = 0
        for sub in SUB_PASOS:
            sql_path = sql_dir / sub.sql_file
            if not sql_path.exists():
                result.status = StepStatus.FAILED
                result.error_message = f"SQL file no encontrado: {sql_path}"
                result.finished_at = datetime.utcnow()
                return result

            t0 = datetime.utcnow()
            try:
                pg.execute_sql_file(sql_path)
            except Exception as e:  # captura amplia a proposito:
                # cualquier fallo del SQL tiene que salir con el nombre
                # del sub-paso, no como traza cruda a las tres de la manana
                duration = (datetime.utcnow() - t0).total_seconds()
                logger.error(
                    "retenciones_substep_failed",
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
                "retenciones_substep_done",
                sub_step=sub.name, rows=rows,
                duration_s=round((datetime.utcnow() - t0).total_seconds(), 2),
            )

        result.status = StepStatus.SUCCESS
        result.rows_processed = total_rows
        result.finished_at = datetime.utcnow()
        return result
