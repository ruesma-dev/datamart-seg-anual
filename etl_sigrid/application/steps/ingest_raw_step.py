# etl_sigrid/application/steps/ingest_raw_step.py
"""
Step que extrae datos de Sigrid (vía sigrid-api) y los vuelca a raw.* en Postgres.

Flujo:
    1. Para cada tabla declarada en config/tables_sigrid.yaml:
       a. Lee INFORMATION_SCHEMA.COLUMNS de Sigrid para esa tabla.
       b. Excluye las columnas marcadas en `exclude_columns` (binarios, blobs).
       c. Crea raw.<target_table> en Postgres si no existe.
       d. Si full_refresh=True: TRUNCATE raw.<target_table>.
          Si full_refresh=False: averigua el MAX(ide) en raw y arranca el cursor desde ahí.
       e. Stream-extract de Sigrid por keyset (WHERE ide > last_id) y COPY a Postgres.
    2. Registra el run en _meta.etl_runs.

Características:
    - Idempotente: ejecutarlo dos veces deja el mismo estado.
    - Incremental por defecto: solo trae filas con ide > MAX(ide) ya cargado.
    - Streaming: no carga toda la tabla en memoria (psycopg COPY + iterador HTTP).
    - Resiliente: si una tabla falla, las demás continúan (configurable).
"""

from __future__ import annotations

from datetime import datetime

from config.settings import Settings
from etl_sigrid.application.steps.base import PipelineStep
from etl_sigrid.domain.entities import StepResult, StepStatus, TableSpec
from etl_sigrid.infrastructure.logging_config import get_logger
from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient
from etl_sigrid.infrastructure.sigrid.sigrid_api_client import (
    SigridApiClient,
    SigridApiError,
    SigridApiPageSizeTooLargeError,
)

logger = get_logger(__name__)


class IngestRawStep(PipelineStep):
    """Extrae tablas de Sigrid a raw.* en Postgres."""

    def __init__(
        self,
        settings: Settings,
        *,
        only_table: str | None = None,
        full_refresh: bool = False,
        stop_on_error: bool = False,
    ) -> None:
        self._settings = settings
        self._only_table = only_table
        self._full_refresh = full_refresh
        self._stop_on_error = stop_on_error

    @property
    def name(self) -> str:
        return "ingest_raw"

    @property
    def stage(self) -> str:
        return "ingest"

    def run(self) -> StepResult:
        result = self._new_result()
        tables_cfg = self._settings.tables_sigrid.get("tables", [])
        specs = [self._build_table_spec(t) for t in tables_cfg]

        if self._only_table:
            specs = [s for s in specs if s.source_table == self._only_table]
            if not specs:
                result.status = StepStatus.FAILED
                result.error_message = f"Tabla '{self._only_table}' no declarada en tables_sigrid.yaml"
                result.finished_at = datetime.utcnow()
                return result

        pg = PostgresClient(
            conninfo=self._settings.postgres.conninfo,
            admin_conninfo=self._settings.postgres.admin_conninfo,
            target_db=self._settings.postgres.db,
        )
        # El auto-bootstrap se ejecutará lazy en la primera conexión.
        # No hace falta llamada explícita.

        total_rows = 0
        failed_tables: list[str] = []
        per_table_stats: dict[str, int] = {}

        with SigridApiClient(
            base_url=self._settings.sigrid_api.base_url,
            function_key=self._settings.sigrid_api.function_key.get_secret_value(),
            database=self._settings.sigrid_api.database,
            page_size=self._settings.sigrid_api.page_size,
            timeout_s=self._settings.sigrid_api.timeout_s,
            max_retries=self._settings.sigrid_api.max_retries,
        ) as api:
            for spec in specs:
                try:
                    rows = self._ingest_one_table(spec, api, pg)
                    per_table_stats[spec.source_table] = rows
                    total_rows += rows
                except SigridApiPageSizeTooLargeError as e:
                    # Error de configuración global: abortar el step entero,
                    # no tiene sentido probar el resto de tablas porque van
                    # a fallar todas con el mismo motivo.
                    logger.error(
                        "ingest_aborted_page_size_too_large",
                        requested=e.requested,
                        api_cap=e.cap,
                    )
                    result.status = StepStatus.FAILED
                    result.error_message = str(e)
                    result.rows_processed = total_rows
                    result.finished_at = datetime.utcnow()
                    result.metadata = {
                        "per_table_stats": per_table_stats,
                        "failed_tables": failed_tables,
                        "api_cap": e.cap,
                    }
                    return result
                except SigridApiError as e:
                    logger.error(
                        "ingest_table_failed",
                        table=spec.source_table,
                        error=str(e),
                    )
                    failed_tables.append(spec.source_table)
                    if self._stop_on_error:
                        result.status = StepStatus.FAILED
                        result.error_message = f"Fallo en {spec.source_table}: {e}"
                        result.rows_processed = total_rows
                        result.finished_at = datetime.utcnow()
                        result.metadata = {
                            "per_table_stats": per_table_stats,
                            "failed_tables": failed_tables,
                        }
                        return result

        result.status = StepStatus.FAILED if failed_tables else StepStatus.SUCCESS
        result.rows_processed = total_rows
        result.finished_at = datetime.utcnow()
        result.metadata = {
            "per_table_stats": per_table_stats,
            "failed_tables": failed_tables,
            "full_refresh": self._full_refresh,
        }
        if failed_tables:
            result.error_message = f"Fallaron: {', '.join(failed_tables)}"
        return result

    # ---------------------------------------------------------------------
    # Internos
    # ---------------------------------------------------------------------

    def _build_table_spec(self, raw_cfg: dict) -> TableSpec:
        return TableSpec(
            source_table=raw_cfg["source_table"],
            target_table=raw_cfg["target_table"],
            id_column=raw_cfg.get("id_column", "ide"),
            incremental_column=raw_cfg.get("incremental_column"),
            where=raw_cfg.get("where"),
            exclude_columns=raw_cfg.get("exclude_columns") or [],
            page_size_override=raw_cfg.get("page_size"),
        )

    def _ingest_one_table(
        self,
        spec: TableSpec,
        api: SigridApiClient,
        pg: PostgresClient,
    ) -> int:
        """Ingesta una tabla. Devuelve el número de filas insertadas."""
        run_id = pg.record_run_start("ingest", f"ingest_raw.{spec.source_table}")

        try:
            # 1. Schema desde Sigrid
            all_cols = api.fetch_table_schema(spec.source_table)
            excluded = set(spec.exclude_columns)
            kept_cols = [c for c in all_cols if c.name not in excluded]
            if not kept_cols:
                raise SigridApiError(
                    f"Sin columnas tras excluir {excluded} en {spec.source_table}"
                )

            logger.info(
                "ingest_table_start",
                table=spec.source_table,
                kept_cols=len(kept_cols),
                excluded_cols=sorted(excluded),
                page_size=spec.page_size_override or self._settings.sigrid_api.page_size,
            )

            # 2. Crear tabla destino si no existe
            pg.ensure_raw_table(spec.target_table, kept_cols, primary_key=spec.id_column)

            # 3. Determinar cursor de arranque
            if self._full_refresh:
                pg.truncate_table("raw", spec.target_table)
                last_id_already = 0
            else:
                last_id_already = pg.get_max_id("raw", spec.target_table, spec.id_column)

            # 4. Stream Sigrid → COPY Postgres
            col_names = [c.name for c in kept_cols]
            tiemod_col = spec.incremental_column if spec.incremental_column in col_names else None

            total = 0
            for batch in api.stream_table(
                spec.source_table,
                columns=col_names,
                id_column=spec.id_column,
                where=spec.where,
                start_id=last_id_already,
                page_size=spec.page_size_override,
            ):
                if not batch:
                    continue
                inserted = pg.copy_rows(
                    schema="raw",
                    table=spec.target_table,
                    columns=col_names,
                    rows=batch,
                    tiemod_column=tiemod_col,
                )
                total += inserted

            logger.info(
                "ingest_table_done",
                table=spec.source_table,
                rows_inserted=total,
                full_refresh=self._full_refresh,
                cursor_start=last_id_already,
            )
            pg.record_run_end(run_id, "SUCCESS", rows_processed=total)
            return total

        except Exception as e:
            pg.record_run_end(run_id, "FAILED", error_message=str(e))
            raise
