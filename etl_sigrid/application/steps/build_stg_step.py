# etl_sigrid/application/steps/build_stg_step.py
"""
Step que materializa el esquema stg.* a partir de raw.*.

Flujo:
    1. Asegura schemas y _meta.etl_runs (idempotente).
    2. Ejecuta en orden los archivos SQL de sql/stg/:
        00_functions.sql               - funciones helper (fecha Sigrid → DATE)
        01_ddl.sql                     - CREATE TABLE IF NOT EXISTS de stg.*
        02_ambitos.sql                 - VISTA stg.ambitos (clasificación)
        03_obras.sql                   - TRUNCATE + INSERT stg.obras
        04_partidas.sql                - TRUNCATE + INSERT stg.partidas
        05_fases.sql                   - TRUNCATE + INSERT stg.fases
        06_presupuesto.sql             - TRUNCATE + INSERT stg.presupuesto (el grande)
        07_version_master_vigente.sql  - TRUNCATE + INSERT (parametrizado con cod=15)

Cada sub-step se registra en _meta.etl_runs con su tiempo y filas procesadas.
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
    """Un sub-paso de build_stg: un archivo SQL + tabla destino (para contar filas)."""

    name: str
    sql_file: str
    target_schema: str | None = None
    target_table: str | None = None
    params: dict | tuple | None = None


class BuildStgStep(PipelineStep):
    """Construye el esquema stg desde raw."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def name(self) -> str:
        return "build_stg"

    @property
    def stage(self) -> str:
        return "stage"

    @property
    def depends_on(self) -> list[str]:
        return ["ingest_raw"]

    def run(self) -> StepResult:
        result = self._new_result()
        pg = PostgresClient(
            conninfo=self._settings.postgres.conninfo,
            admin_conninfo=self._settings.postgres.admin_conninfo,
            target_db=self._settings.postgres.db,
        )
        # El auto-bootstrap (CREATE DATABASE/schemas/_meta) se ejecutará lazy en
        # la primera conexión. No hace falta llamada explícita.

        # Pre-flight check: verifica que raw tiene todas las columnas que los
        # SQL de stg van a usar. Si falta alguna, falla con un mensaje claro
        # ANTES de tocar ningún dato.
        try:
            self._preflight_check(pg)
        except ValueError as e:
            result.status = StepStatus.FAILED
            result.error_message = f"Pre-flight check falló: {e}"
            result.finished_at = datetime.utcnow()
            logger.error("preflight_check_failed", error=str(e))
            return result

        sql_dir = (
            Path(__file__).resolve().parent.parent.parent
            / "infrastructure" / "postgres" / "sql" / "stg"
        )

        cod_version_master = self._settings.business_rules["sigrid"]["campos_extendidos"][
            "cod_version_master_vigente"
        ]

        sub_steps: list[_SubStep] = [
            _SubStep("functions",         "00_functions.sql"),
            _SubStep("ddl",               "01_ddl.sql"),
            _SubStep("ambitos_view",      "02_ambitos.sql"),
            _SubStep("build_obras",       "03_obras.sql",       "stg", "obras"),
            _SubStep("build_partidas",    "04_partidas.sql",    "stg", "partidas"),
            _SubStep("build_fases",       "05_fases.sql",       "stg", "fases"),
            _SubStep("build_presupuesto", "06_presupuesto.sql", "stg", "presupuesto"),
            _SubStep(
                "build_version_master_vigente",
                "07_version_master_vigente.sql",
                "stg",
                "version_master_vigente",
                params={"cod": cod_version_master},
            ),
            _SubStep("build_plan_mensual", "08_plan_mensual.sql", "stg", "plan_mensual"),
        ]

        table_stats: dict[str, int] = {}
        total_rows = 0

        for sub in sub_steps:
            sql_path = sql_dir / sub.sql_file
            run_id = pg.record_run_start("stage", f"build_stg.{sub.name}")

            t0 = datetime.utcnow()
            try:
                pg.execute_sql_file(sql_path, params=sub.params)

                rows = 0
                if sub.target_schema and sub.target_table:
                    rows = pg.count_rows(sub.target_schema, sub.target_table)
                    table_stats[f"{sub.target_schema}.{sub.target_table}"] = rows
                    total_rows += rows

                duration = (datetime.utcnow() - t0).total_seconds()
                logger.info(
                    "stg_substep_done",
                    sub_step=sub.name,
                    rows=rows,
                    duration_s=round(duration, 2),
                )
                pg.record_run_end(run_id, "SUCCESS", rows_processed=rows)

            except Exception as e:
                duration = (datetime.utcnow() - t0).total_seconds()
                logger.exception(
                    "stg_substep_failed",
                    sub_step=sub.name,
                    duration_s=round(duration, 2),
                )
                pg.record_run_end(run_id, "FAILED", error_message=str(e))
                result.status = StepStatus.FAILED
                result.error_message = f"Fallo en {sub.name}: {e}"
                result.finished_at = datetime.utcnow()
                result.rows_processed = total_rows
                result.metadata = {"table_stats": table_stats, "failed_at": sub.name}
                return result

        result.status = StepStatus.SUCCESS
        result.rows_processed = total_rows
        result.finished_at = datetime.utcnow()
        result.metadata = {"table_stats": table_stats}
        return result

    # ---------------------------------------------------------------------
    # Pre-flight check
    # ---------------------------------------------------------------------

    def _preflight_check(self, pg: PostgresClient) -> None:
        """
        Verifica que raw.* tiene todas las columnas que los SQL de stg necesitan.

        Recolecta TODOS los errores y los reporta en una única excepción al
        final, para no obligar a iterar arreglando uno a uno. Si tres tablas
        tienen problemas, el mensaje los lista los tres.

        Mantener esta lista actualizada es responsabilidad de quien edita los SQL:
        si añades una columna nueva a un SQL, añádela también aquí.
        """
        required_by_table: dict[tuple[str, str], list[str]] = {
            ("raw", "con"):       ["ide", "cod", "res"],
            ("raw", "obr"):       ["ide", "decc", "decp", "deci"],
            ("raw", "obrctr"):    ["ide", "obride", "fecreaact",
                                   "fecreaini", "fecreafin",
                                   "fecpreini", "fecprefin"],
            # Catálogos para mostrar texto en la cabecera del cierre (Tanda 3.1)
            # OJO: cen NO tiene 'res' propio - hereda de con (Tanda 3.1.1).
            ("raw", "cen"):       ["ide"],
            ("raw", "auxobrtip"): ["ide", "res"],
            ("raw", "auxobrcla"): ["ide", "res"],
            ("raw", "obrparpar"): ["ide", "obride", "padide", "cod", "res", "tipdes", "unimed", "tcaide"],
            ("raw", "obrfas"):    ["ide", "obride", "fasnum", "fecini", "fecfin", "ano", "mes", "res"],
            ("raw", "obrfasamb"): ["ide", "obride", "amb", "fas", "plafec", "fec", "res", "tex"],
            ("raw", "obrparpre"): ["ide", "obride", "paride", "amb", "fas", "can", "pre", "planif", "totinc", "impcoe"],
            ("raw", "conext"):    ["conide", "cod", "valn"],
            ("raw", "auxobramb"): ["ide", "cod", "res"],
            ("raw", "auxobrtca"): ["ide", "cod", "res"],
        }

        errors: list[str] = []
        for (schema, table), cols in required_by_table.items():
            try:
                pg.assert_columns_exist(schema, table, cols)
            except ValueError as e:
                errors.append(str(e))

        if errors:
            # Une todos los errores en un mensaje único, separados por linea en blanco
            joined = "\n\n  · " + "\n\n  · ".join(errors)
            raise ValueError(
                f"Pre-flight detectó {len(errors)} problema(s) en raw.*:{joined}\n\n"
                f"Ejecuta 'python main.py inspect-raw' para ver el esquema completo "
                f"de todas las tablas raw."
            )

        logger.info(
            "preflight_check_passed",
            tables_validated=len(required_by_table),
        )
