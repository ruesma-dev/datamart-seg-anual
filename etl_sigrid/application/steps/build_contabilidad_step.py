# etl_sigrid/application/steps/build_contabilidad_step.py
"""
Step que materializa la contabilidad (F-056): el plan de cuentas como árbol, el
mayor y los saldos por cuenta y mes, en DOS esquemas desde F-135.

* `contabilidad_restringida` — la contabilidad COMPLETA, la de F-056 sin tocar
  una columna ni una cifra, más la marca de lo restringido. Solo la lee el grupo
  `sigrid_dm_autorizado_ro` (y el dueño y el administrador de la base).
* `contabilidad` — la GENERAL, la que leen el MCP y Power BI: sin los apuntes de
  PERSONAL (nóminas, cuentas de trabajadores, embargos; criterio en
  `domain/restriccion_personal.py`), con las cuentas de personal enmascaradas en
  el plan y con solo RECUENTOS de lo que falta, nunca importes.

Encadena los archivos SQL en orden:
    00_setup.sql                     - los dos esquemas y `contabilidad.fn_fecha`
    01_plan_cuentas.sql              - restringida: el plan FINANCIERO como árbol
                                       (grupos de `con.tip = 16` y auxiliares de `cua`)
    02_mayor.sql                     - restringida: una fila por apunte de `raw.apu`,
                                       con `restringido`, `motivo_restriccion`,
                                       `saldo_acumulado_visible` y la guarda que
                                       compara su recuento con el origen
    03_saldos_cuenta_mes.sql         - restringida: cuenta x ejercicio x mes
    04_plan_cuentas_general.sql      - general: el plan con las cuentas CR enmascaradas
    05_mayor_general.sql             - general: solo lo visible, con su guarda (0 CR
                                       y general + restringidos = completo)
    06_saldos_general.sql            - general: saldos de lo visible + recuento de
                                       lo que falta (`incompleto`)
    07_apuntes_restringidos_mes.sql  - general: cuántos apuntes faltan por empresa y
                                       mes, sin importes

Los permisos NO van aquí: los da (y los veta y verifica) `apply_grants` cada
noche. Este paso solo construye.

Lee de `raw.*` (con, cua, auxemp, apu) y de UNA cosa fuera de `raw`: la vista
`maestro.centros_coste`, el puente centro de coste -> obra. Esa vista es SQL
puro sobre `raw` y nunca se dropea, así que `depends_on = ["ingest_raw"]` y no
`build_maestros`: el mismo motivo escrito en `build_retenciones_step.py`.

POR QUÉ ES UN ESQUEMA MÓDULO (spec de F-056, D5). Como `personal`: dentro de
`build_stg` un fallo de este SQL dejaría sin `mart` la noche, y los permisos se
dan POR ESQUEMA. **Ningún paso declara `build_contabilidad` en su
`depends_on`**: si falla, la nocturna continúa y termina, y `R-FRESCURA` avisa
al consumidor de que el esquema viene de una noche anterior.
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


#: Los ocho ficheros SQL, EN ORDEN, y de qué tabla se cuentan filas. Los de la
#: contabilidad general (04-07) van DETRÁS de los del completo: leen de él.
#:
#: Vive fuera de `run()` por lo mismo que en `build_personal_step`: es DATO, y
#: sustituirla en un test es lo que permite ejercitar el fichero que falta.
#: `setup` no cuenta filas: solo crea el esquema y la función.
SUB_PASOS: tuple[_SubStep, ...] = (
    _SubStep(name="setup", sql_file="00_setup.sql"),
    _SubStep(
        name="plan_cuentas",
        sql_file="01_plan_cuentas.sql",
        target_schema="contabilidad_restringida",
        target_table="plan_cuentas",
    ),
    _SubStep(
        name="mayor",
        sql_file="02_mayor.sql",
        target_schema="contabilidad_restringida",
        target_table="mayor",
    ),
    _SubStep(
        name="saldos_cuenta_mes",
        sql_file="03_saldos_cuenta_mes.sql",
        target_schema="contabilidad_restringida",
        target_table="saldos_cuenta_mes",
    ),
    _SubStep(
        name="plan_cuentas_general",
        sql_file="04_plan_cuentas_general.sql",
        target_schema="contabilidad",
        target_table="plan_cuentas",
    ),
    _SubStep(
        name="mayor_general",
        sql_file="05_mayor_general.sql",
        target_schema="contabilidad",
        target_table="mayor",
    ),
    _SubStep(
        name="saldos_general",
        sql_file="06_saldos_general.sql",
        target_schema="contabilidad",
        target_table="saldos_cuenta_mes",
    ),
    _SubStep(
        name="apuntes_restringidos_mes",
        sql_file="07_apuntes_restringidos_mes.sql",
        target_schema="contabilidad",
        target_table="apuntes_restringidos_mes",
    ),
)


class BuildContabilidadStep(PipelineStep):
    """Construye `contabilidad_restringida` (completa) y `contabilidad` (general)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def name(self) -> str:
        return "build_contabilidad"

    @property
    def stage(self) -> str:
        return "build_aux"

    @property
    def depends_on(self) -> list[str]:
        # Solo `raw` y la vista `maestro.centros_coste`, que es SQL puro sobre
        # `raw`: declarar `build_maestros` ataría este esquema a otro sin
        # necesidad.
        return ["ingest_raw"]

    def run(self) -> StepResult:
        result = self._new_result()
        pg = build_postgres_client(self._settings)

        sql_dir = (
            Path(__file__).resolve().parents[2]
            / "infrastructure" / "postgres" / "sql" / "contabilidad"
        )

        total_rows = 0
        for sub in SUB_PASOS:
            sql_path = sql_dir / sub.sql_file
            if not sql_path.exists():
                # R3: el nombre del sub-paso va en el mensaje, como en un fallo
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
                # cualquier fallo del SQL -incluida la guarda de recuento del
                # mayor- tiene que salir con el nombre del sub-paso
                duration = (datetime.utcnow() - t0).total_seconds()
                logger.error(
                    "contabilidad_substep_failed",
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
                "contabilidad_substep_done",
                sub_step=sub.name, rows=rows,
                duration_s=round((datetime.utcnow() - t0).total_seconds(), 2),
            )

        result.status = StepStatus.SUCCESS
        result.rows_processed = total_rows
        result.finished_at = datetime.utcnow()
        return result
