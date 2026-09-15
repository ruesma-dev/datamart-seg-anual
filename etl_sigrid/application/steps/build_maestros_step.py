# etl_sigrid/application/steps/build_maestros_step.py
"""
Step que materializa el schema `maestro` (catálogos para consulta externa).

Encadena los archivos SQL en orden:
    00_setup.sql             - schema maestro + helper de fecha (idempotente)
    01_obras.sql             - vista maestro.obras (código, nombre, cliente,
                               dirección, municipio/provincia, estado con su
                               nombre y las dos marcas de datos)
    02_proveedores.sql       - vista maestro.proveedores (global, CIF y dir.)
    03_proveedores_obra.sql  - vista maestro.proveedores_obra (vía ctr)
    04_centros_coste.sql     - vista maestro.centros_coste (puente centro→obra)
    05_estados_documento.sql - vista maestro.estados_documento (desde conest)

DE DÓNDE LEE, Y LAS DOS AFIRMACIONES QUE ESTE DOCSTRING TENÍA Y ERAN FALSAS.
Afirmaba dos cosas: que este paso se alimentaba únicamente de `raw`, y que
quedaba fuera de la carga nocturna. Lo segundo dejó de ser
cierto en F-047, que metió los cuatro esquemas de negocio en la carga nocturna;
lo primero, en F-073, que publica en `maestro.obras` las marcas
`tiene_presupuesto` y `tiene_seguimiento` sondando `stg.presupuesto` y
`stg.plan_mensual`. Por eso `depends_on` incluye ahora `build_stg`.

POR QUÉ LAS MARCAS LEEN DE `stg` Y NO DE LA CAPA DE HECHOS (F-073, DA-1): el
DDL de `mart` dropea sus tablas con CASCADE cada noche, así que una vista de
`maestro` colgada de ahí la destruiría la nocturna siguiente —el incidente
literal de F-047 con `cierre.v_pbi_planif_vs_real`—. Las dos tablas de `stg`
se crean con `CREATE TABLE IF NOT EXISTS` y no se dropean nunca.

Sigue pudiendo ejecutarse como comando aparte (`python main.py
build-maestros`), y además corre dentro de `run-all`.
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


#: Los seis ficheros SQL, EN ORDEN, y de qué vista se cuentan filas.
#:
#: Vive fuera de `run()` a propósito, igual que en `build_compras_step.py`: es
#: DATO, no lógica, y así se puede comprobar sin ejecutar el step que cada
#: fichero de la carpeta está declarado. Un `.sql` que nadie encadena no se
#: ejecuta solo, y el diccionario lo declara igual: esa es la discrepancia que
#: `check-diccionario` destapó el 2026-09-09.
SUB_PASOS: tuple[_SubStep, ...] = (
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
    _SubStep(
        name="centros_coste",
        sql_file="04_centros_coste.sql",
        target_schema="maestro",
        target_table="centros_coste",
    ),
    _SubStep(
        name="estados_documento",
        sql_file="05_estados_documento.sql",
        target_schema="maestro",
        target_table="estados_documento",
    ),
)


class BuildMaestrosStep(PipelineStep):
    """Construye el schema `maestro`: obras, proveedores, el puente de
    centros de coste y el catálogo de estados de documento."""

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
        # `raw` por todo lo demás y `stg` por las dos marcas de `maestro.obras`
        # (F-073, R27). Coste declarado: si `build_stg` falla, el orquestador
        # marca este paso como SKIPPED, cosa que antes no pasaba. Es asumible
        # porque los seis objetos de `maestro` son VISTAS: saltarlas una noche
        # deja exactamente la definición de ayer, que es idéntica.
        return ["ingest_raw", "build_stg"]

    def run(self) -> StepResult:
        result = self._new_result()
        pg = build_postgres_client(self._settings)

        sql_dir = (
            Path(__file__).resolve().parents[2]
            / "infrastructure" / "postgres" / "sql" / "maestro"
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
