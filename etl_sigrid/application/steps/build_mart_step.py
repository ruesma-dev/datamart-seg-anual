# etl_sigrid/application/steps/build_mart_step.py
"""
Step que materializa el esquema mart.* a partir de stg.*.

Flujo:
    1. Asegura schema mart (idempotente, vía PostgresClient auto-bootstrap).
    2. Ejecuta en orden los archivos SQL de sql/mart/:
        01_ddl.sql                       - DROP + CREATE mart.fact_seguimiento_mensual
        02_build_fact.sql                - TRUNCATE + INSERT con la lógica de comparativa
        03_agg_categoria.sql             - Pre-agregado CD/CI/CP por obra × mes × escenario
        04_view_periodificado.sql        - Tabla aux.periodificacion_partida + vista
                                           mart.v_fact_periodificado (placeholder)
        05_views_powerbi.sql             - Vistas v_pbi_* consumidas por Power BI
        05b_view_dim_partida_niveles.sql - Vista mart.v_pbi_dim_partida_niveles
                                           (DimPartida + nivel_1..6 para el visual árbol)
        06_views_cp_tipologia.sql        - Vistas para el detalle anual CP por tipología
                                           (helpers + v_pbi_cp_tipologia)

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
from etl_sigrid.domain.coherencia import (
    VeredictoCoherencia,
    evaluar_coherencia_stg,
    formatear_veredicto_stg,
)
from etl_sigrid.domain.entities import StepResult, StepStatus
from etl_sigrid.infrastructure.logging_config import get_logger
from etl_sigrid.infrastructure.postgres.client_factory import build_postgres_client
from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

logger = get_logger(__name__)

# --- Puerta de coherencia de stg (F-024, DA-5) ------------------------------
# Se registra como sub-paso, igual que la de raw, para que su veredicto quede
# consultable en `timings` y en `_meta.etl_runs`.
PASO_PUERTA_STG = "build_mart.puerta_stg"


@dataclass(slots=True, frozen=True)
class _SubStep:
    """Un sub-paso: un archivo SQL + (opcionalmente) la tabla destino para contar filas."""

    name: str
    sql_file: str
    target_schema: str | None = None
    target_table: str | None = None


class BuildMartStep(PipelineStep):
    """Construye el esquema mart desde stg."""

    def __init__(
        self,
        settings: Settings,
        batch_id: str | None = None,
        omitir_puerta: bool = False,
    ) -> None:
        self._settings = settings
        self._batch_id = batch_id
        self._omitir_puerta = omitir_puerta

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
        pg = build_postgres_client(self._settings)

        # Puerta de coherencia de stg (F-024, DA-5). Antes del primer fichero,
        # porque `01_ddl.sql` empieza con un DROP + CREATE de la tabla de
        # hechos: evaluarla después ya se habría llevado por delante el `mart`
        # bueno de la noche anterior, que es justo lo que salvó la situación
        # el 2026-08-18.
        veredicto = self._puerta_stg(pg)
        if not veredicto.ok and not self._omitir_puerta:
            result.status = StepStatus.FAILED
            result.error_message = formatear_veredicto_stg(veredicto)
            result.finished_at = datetime.utcnow()
            return result

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
            _SubStep(
                name="dim_partida_niveles",
                sql_file="05b_view_dim_partida_niveles.sql",
                # Vista (DimPartida + nivel_1..6 para el visual árbol), no cuenta filas
            ),
            _SubStep(
                name="views_cp_tipologia",
                sql_file="06_views_cp_tipologia.sql",
                # Vistas (helpers + v_pbi_cp_tipologia), no cuenta filas
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
        result.metadata = {"stg_batch_id": veredicto.batch_id}
        return result

    # ---------------------------------------------------------------------
    # Puerta de coherencia de stg (F-024, R15)
    # ---------------------------------------------------------------------

    def _puerta_stg(self, pg: PostgresClient) -> VeredictoCoherencia:
        """Comprueba que el último `build_stg` llegó a terminar.

        Un `stage` muerto a medias deja `stg` MEZCLADO: los ficheros `03..07`
        son atómicos cada uno, pero entre sí no, así que puede quedar
        `stg.obras` de esta noche y `stg.presupuesto` de ayer. Construir `mart`
        encima produce cuadros que no cuadran sin que nadie se entere, que es
        exactamente lo que esta feature viene a impedir.

        Mismo trato que la puerta de `raw`: se evalúa siempre y se registra
        siempre, incluso cuando se omite.
        """
        run_id = pg.record_run_start("build_mart", PASO_PUERTA_STG, self._batch_id)

        veredicto = evaluar_coherencia_stg(pg.fetch_ultimo_intento_stg())
        mensaje = formatear_veredicto_stg(veredicto)

        if self._omitir_puerta:
            pg.record_run_end(
                run_id,
                StepStatus.SKIPPED.value,
                error_message=f"puerta omitida por --sin-puerta; veredicto: {mensaje}",
            )
            logger.warning("puerta_omitida", veredicto_ok=veredicto.ok, motivo=mensaje)
        elif veredicto.ok:
            pg.record_run_end(run_id, StepStatus.SUCCESS.value)
            logger.info("puerta_stg_ok", stg_batch_id=veredicto.batch_id)
        else:
            pg.record_run_end(run_id, StepStatus.FAILED.value, error_message=mensaje)
            ultimo = veredicto.ultimo_paso
            logger.error(
                "puerta_stg_ko",
                ultimo_step=ultimo.step if ultimo else None,
                ultimo_status=ultimo.status if ultimo else None,
            )

        return veredicto