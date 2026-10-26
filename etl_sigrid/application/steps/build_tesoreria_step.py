# etl_sigrid/application/steps/build_tesoreria_step.py
"""
Step que materializa la cartera de cobros y pagos (F-037, fase 1) en DOS
esquemas, con el patrón de F-135, y los INGREDIENTES de la proyección de caja
(F-140): lo pactado, el devengo pendiente y las hipótesis. Ningún plazo se
aplica aquí a ninguna fecha: convertir devengo en caja lo hace quien consulta,
declarando sus hipótesis (`R-CAJA-HIPOTESIS`).

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
    04_plazos_forma_pago.sql         - F-140: las formas de pago y cobro con su
                                       fórmula leída (vista)
    05_condiciones_contrato_compra.sql - F-140: lo pactado con el proveedor
    06_condiciones_contrato_cliente.sql - F-140: lo pactado con el cliente
    07_devengo_pendiente.sql         - F-140: lo que la última versión master
                                       espera devengar tras el cierre, por
                                       partida, por mes y por obra
    (hipotesis_carga)                - F-140: Python, sin SQL: lee y valida
                                       `config/hipotesis_caja.yaml` y lo carga
                                       en una transacción; con errores, FAILED
                                       con la lista y no escribe
    08_hipotesis_caja_obra.sql       - F-140: el valor de cada hipótesis en cada
                                       obra (MANUAL > SIGRID > DEFECTO)

Cada fichero es su transacción: si `07` falla, quedan las tablas de ayer y la
cartera de hoy ya está hecha.

Los permisos NO van aquí: los da (y los veta y verifica) `apply_grants` cada
noche. Este paso solo construye.

Lee de `raw.*` y de las vistas `maestro.centros_coste` y `maestro.v_obra_fichas`,
SQL puro sobre `raw` que nunca se dropea: `depends_on = ["ingest_raw"]`, el
mismo motivo que en `build_contabilidad_step.py`. Desde F-140 `07` lee además
`stg.plan_mensual` y `mart`, que la nocturna construye ANTES (`build_stg`,
`build_mart`); no se declaran en `depends_on` para no cambiar el orden de la
noche, y la reanudación de F-148 los conoce (`LECTURAS_PARA_REANUDAR`).

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
from etl_sigrid.infrastructure.config.hipotesis_caja_yaml import cargar_hipotesis_caja
from etl_sigrid.infrastructure.logging_config import get_logger
from etl_sigrid.infrastructure.postgres.client_factory import build_postgres_client

logger = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class _SubStep:
    """Un sub-paso. Sin `sql_file` es la carga de hipótesis (Python)."""

    name: str
    sql_file: str | None
    target_schema: str | None = None
    target_table: str | None = None


#: Los sub-pasos, EN ORDEN, y de qué tabla se cuentan filas. La general (02) y
#: los recuentos (03) van detrás de la completa: leen de ella. `07` lee la
#: cartera general (la frontera, D16-A) y `08` lee el corte de `07` y la carga
#: de hipótesis. Es DATO fuera de `run()` para que un test pueda sustituirla.
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
    _SubStep(name="plazos_forma_pago", sql_file="04_plazos_forma_pago.sql"),
    _SubStep(
        name="condiciones_compra",
        sql_file="05_condiciones_contrato_compra.sql",
        target_schema="tesoreria",
        target_table="condiciones_contrato_compra",
    ),
    _SubStep(
        name="condiciones_cliente",
        sql_file="06_condiciones_contrato_cliente.sql",
        target_schema="tesoreria",
        target_table="condiciones_contrato_cliente",
    ),
    _SubStep(
        name="devengo_pendiente",
        sql_file="07_devengo_pendiente.sql",
        target_schema="tesoreria",
        target_table="devengo_pendiente_partida",
    ),
    _SubStep(name="hipotesis_carga", sql_file=None),
    _SubStep(
        name="hipotesis_obra",
        sql_file="08_hipotesis_caja_obra.sql",
        target_schema="tesoreria",
        target_table="hipotesis_caja_obra",
    ),
)


def _cargar_hipotesis(pg) -> int:
    """Lee, valida y carga el YAML de hipótesis (R2-R4). Lanza con la lista.

    Con un solo error no se escribe nada: ni el catálogo ni los valores.
    """
    leidas = cargar_hipotesis_caja()
    if leidas.errores:
        raise ValueError(
            f"{len(leidas.errores)} errores en config/hipotesis_caja.yaml: "
            + "; ".join(leidas.errores)
        )
    return pg.cargar_hipotesis_caja(leidas.catalogo, leidas.obras)


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
            sql_path = None if sub.sql_file is None else sql_dir / sub.sql_file
            if sql_path is not None and not sql_path.exists():
                # R18: el nombre del sub-paso va en el mensaje, como en un fallo
                result.status = StepStatus.FAILED
                result.error_message = (
                    f"Fallo en {sub.name}: SQL file no encontrado: {sql_path}"
                )
                result.finished_at = datetime.utcnow()
                return result

            t0 = datetime.utcnow()
            try:
                if sql_path is None:
                    # F-140: la carga de hipótesis, sin SQL; sus filas son las escritas
                    cargadas = _cargar_hipotesis(pg)
                else:
                    pg.execute_sql_file(sql_path)
            except Exception as e:  # captura amplia a proposito:
                # cualquier fallo del SQL -incluida la guarda de 02- o del YAML
                # de hipótesis tiene que salir con el nombre del sub-paso
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
            if sql_path is None:
                rows = cargadas
                total_rows += rows
            elif sub.target_schema and sub.target_table:
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
