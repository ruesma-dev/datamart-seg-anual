# etl_sigrid/application/steps/build_tesoreria_step.py
"""
Step que materializa la cartera de cobros y pagos (F-037, fase 1) en DOS
esquemas, con el patrón de F-135.

* `tesoreria_restringida` — la cartera COMPLETA: una fila por efecto de
  `raw.pag` y `raw.cob`, con `restringido` y `motivo_restriccion`. Solo la leen
  el grupo `sigrid_dm_autorizado_ro` y el login total (y el dueño).
* `tesoreria` — la GENERAL, la que leen el MCP y Power BI: sin los pagos de
  PERSONAL (nóminas, embargos, cuotas; criterio en `domain/tesoreria.py`), y
  con solo RECUENTOS de lo que falta, nunca importes.

Encadena los archivos SQL en orden:
    00_setup.sql                     - los dos esquemas, `fn_fecha`, `fn_serie` y
                                       las tres tablas (`IF NOT EXISTS`: no se
                                       dropean, de la general cuelga la vista
                                       `compras.vencimientos`)
    01_efectos_completo.sql          - restringida: todos los efectos, con la marca
    02_efectos_general.sql           - general: solo lo visible, con su guarda (0 de
                                       personal recalculado desde `raw` y general +
                                       restringidos = completa)
    03_efectos_restringidos_mes.sql  - general: cuántos faltan, sin importes

Los permisos NO van aquí: los da (y los veta y verifica) `apply_grants` cada
noche. Este paso solo construye.

Lee de `raw.*` y de la vista `maestro.centros_coste`, que es SQL puro sobre
`raw` y nunca se dropea: `depends_on = ["ingest_raw"]`, el mismo motivo que en
`build_contabilidad_step.py`.

**Ningún paso declara `build_tesoreria` en su `depends_on`** (D9), tampoco
`build_compras`, aunque su `compras.vencimientos` sea una vista de
`tesoreria.efectos`: la vista solo necesita que la tabla EXISTA, y existe desde
el primer build. Si una noche este paso falla, su `TRUNCATE` se deshace con la
transacción y compras sigue leyendo la cartera de ayer. Va DELANTE de compras
en la lista para que, la noche buena, compras lea la de hoy.
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


#: Los cuatro ficheros SQL, EN ORDEN, y de qué tabla se cuentan filas. La
#: general (02) y los recuentos (03) van detrás de la completa: leen de ella.
#: Es DATO fuera de `run()` para que un test pueda sustituirla.
SUB_PASOS: tuple[_SubStep, ...] = (
    _SubStep(name="setup", sql_file="00_setup.sql"),
    _SubStep(
        name="efectos_completo",
        sql_file="01_efectos_completo.sql",
        target_schema="tesoreria_restringida",
        target_table="efectos",
    ),
    _SubStep(
        name="efectos_general",
        sql_file="02_efectos_general.sql",
        target_schema="tesoreria",
        target_table="efectos",
    ),
    _SubStep(
        name="efectos_restringidos_mes",
        sql_file="03_efectos_restringidos_mes.sql",
        target_schema="tesoreria",
        target_table="efectos_restringidos_mes",
    ),
)


class BuildTesoreriaStep(PipelineStep):
    """Construye `tesoreria_restringida` (completa) y `tesoreria` (general)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def name(self) -> str:
        return "build_tesoreria"

    @property
    def stage(self) -> str:
        return "build_aux"

    @property
    def depends_on(self) -> list[str]:
        # Solo `raw` y la vista `maestro.centros_coste` (SQL puro sobre `raw`).
        return ["ingest_raw"]

    def run(self) -> StepResult:
        result = self._new_result()
        pg = build_postgres_client(self._settings)

        sql_dir = (
            Path(__file__).resolve().parents[2]
            / "infrastructure" / "postgres" / "sql" / "tesoreria"
        )

        total_rows = 0
        for sub in SUB_PASOS:
            sql_path = sql_dir / sub.sql_file
            if not sql_path.exists():
                # R18: el nombre del sub-paso va en el mensaje, como en un fallo
                result.status = StepStatus.FAILED
                result.error_message = (
                    f"Fallo en {sub.name}: SQL file no encontrado: {sql_path}"
                )
                result.finished_at = datetime.utcnow()
                return result

            t0 = datetime.utcnow()
            try:
                pg.execute_sql_file(sql_path)
            except Exception as e:  # captura amplia a proposito:
                # cualquier fallo del SQL -incluida la guarda de 02- tiene que
                # salir con el nombre del sub-paso
                duration = (datetime.utcnow() - t0).total_seconds()
                logger.error(
                    "tesoreria_substep_failed",
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
                "tesoreria_substep_done",
                sub_step=sub.name, rows=rows,
                duration_s=round((datetime.utcnow() - t0).total_seconds(), 2),
            )

        result.status = StepStatus.SUCCESS
        result.rows_processed = total_rows
        result.finished_at = datetime.utcnow()
        return result
