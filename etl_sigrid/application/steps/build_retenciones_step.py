# etl_sigrid/application/steps/build_retenciones_step.py
"""
Step que materializa el schema `retenciones` (garantías retenidas y de cliente).

Encadena los archivos SQL en orden:
    00_setup.sql        - schema, función de fechas, catálogo de tipos y las dos
                          vistas fuente (`v_src_lineas_*`, creadas con SQL
                          dinámico según lo que exista en `raw`)
    01_movimientos.sql  - un registro por efecto de retención (ambos sentidos)
    02_views.sql        - vistas de saldo por entidad, obra, vivas y vencidas
    03_apuntes_contables.sql - F-095: cuentas de retencion de proveedor y sus
                          apuntes contables, con clase y obra
    04_saldo_contable.sql    - F-095: saldo contable por proveedor y obra, la
                          fuente que manda para el saldo vivo
    05_fin_obra.sql     - F-095/F-110: fin de obra, plazo y vencimiento por obra
    06_views_contables.sql   - F-095: cuadre contabilidad-efectos y retencion
                          contable por obra con su vencimiento

Lee de `raw.*` (cob, pag, rec, prv, con, apu, rac, obr, obrctr) y de la vista
`maestro.centros_coste`. El sub-paso `fin_obra` lee ademas tres tablas de
otros pasos:

- desde F-110, `mart.master_versiones_tipadas` (que version es la ultima
  Cuatrimestral) y `stg.plan_mensual` (su ultimo mes con importe planificado):
  sin inicio de garantia, el fin de obra es ese mes + 1. Son de la MISMA noche,
  porque en `run-all` `build_stg` y `build_mart` corren antes;
- desde F-095, `cierre.fact_cierre_mensual`, de la noche anterior
  (`build_cierre` corre despues), solo para la columna informativa
  `ultimo_cierre`: desde F-110 no interviene en el fin de obra, y una tabla del
  cierre vacia ya no hace fallar el paso.

Si falta la tabla de versiones, no tiene ninguna Cuatrimestral, el plan no
tiene filas de los ambitos 8 u 11 o no existe la tabla del cierre, el sub-paso
`fin_obra` falla con su nombre antes de dropear nada (R14 de F-110).

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


#: Los ficheros SQL, EN ORDEN, y de qué tabla se cuentan filas.
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
    # F-095: la retencion desde la contabilidad, en el mismo paso (D1)
    _SubStep(
        name="apuntes",
        sql_file="03_apuntes_contables.sql",
        target_schema="retenciones",
        target_table="apuntes_contables",
    ),
    _SubStep(
        name="saldo",
        sql_file="04_saldo_contable.sql",
        target_schema="retenciones",
        target_table="saldo_contable",
    ),
    _SubStep(
        name="fin_obra",
        sql_file="05_fin_obra.sql",
        target_schema="retenciones",
        target_table="fin_obra",
    ),
    _SubStep(name="views_contables", sql_file="06_views_contables.sql"),
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
        # Necesita raw.* (la ingesta) y, desde F-094, la VISTA
        # `maestro.centros_coste` para traducir centro de coste -> obra. Esa
        # vista es SQL puro sobre `raw` y existe desde F-073; `build_maestros`
        # corre antes por su posición en `build_pipeline_steps`. NO se declara
        # aquí a propósito: `build_maestros` depende de `build_stg`, y
        # declararlo haría que un fallo de `stg` dejara sin construir las
        # retenciones, que hoy sobreviven a eso.
        #
        # F-095 (D7): tampoco se declara `build_cierre`, aunque `05_fin_obra.sql`
        # lee `cierre.fact_cierre_mensual`: usa el cierre de la noche anterior.
        # Desde F-110 esa lectura es solo informativa (`ultimo_cierre`) y una
        # tabla vacia ya no hace fallar el sub-paso.
        #
        # F-110 (D4): `05_fin_obra.sql` lee `mart.master_versiones_tipadas` y
        # `stg.plan_mensual` para el fin de obra. Tampoco se declaran
        # `build_stg` ni `build_mart`: en `build_pipeline_steps` corren antes
        # (misma noche; lo fija `test_f110_r16_orden_topologico`), y si fallan,
        # las retenciones se construyen con sus tablas de la noche anterior en
        # vez de quedarse sin construir.
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
