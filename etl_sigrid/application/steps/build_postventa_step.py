# etl_sigrid/application/steps/build_postventa_step.py
"""
Step que materializa los esquemas `postventa` y `postventa_restringida` (F-156).

Encadena los archivos SQL en orden:
    00_setup.sql        - los dos esquemas y las funciones locales (fecha,
                          momento, estado por la pareja tipo-estado, máscara
                          del texto y obra de una partida)
    01_unidades.sql     - `unidades` (707) y `oficios_obra`
    02_incidencias.sql  - guarda R12, `incidencias` (708) e `incidencia_intervinientes`
    03_tareas.sql       - `tareas` (47) de las incidencias
    04_procesos.sql     - `incidencia_procesos`: el histórico de `rac` y los
                          cierres de la aplicación de Posventa (`raw.log`)
    05_estado.sql       - la vista `v_estado_incidencias`
    06_adjuntos.sql     - guarda R21 y `documento_adjuntos` (los gráficos)
    07_restringida.sql  - `postventa_restringida`: contactos y textos íntegros
    08_coste_obra.sql   - `partida_obra_origen` y la vista `v_coste_obra`

Las tablas solo leen `raw` (y lo que este mismo paso acaba de construir). La
única excepción es la VISTA `v_coste_obra`, que lee `compras` en tiempo de
consulta: no hace falta que `compras` se haya construido antes, solo que sus
tablas existan. Por eso `depends_on = ["ingest_raw"]`.

POR QUÉ ES UN ESQUEMA MÓDULO (patrón de `personal` y `contabilidad`): **ningún
paso declara `build_postventa` en su `depends_on`**, así que si falla la
nocturna continúa y termina, y `R-FRESCURA` avisa de que sus dos esquemas
vienen de una noche anterior. Y los permisos se dan POR ESQUEMA: los datos
personales de los clientes viven en `postventa_restringida` para poder darlos
solo al perfil postventa y al total con un GRANT (D1 = A).
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


#: Los nueve ficheros SQL, EN ORDEN, y de qué tabla se cuentan filas. Es DATO,
#: como en `build_personal_step`: sustituirlo en un test es lo que permite
#: ejercitar el recuento. `setup` y `estado` (una vista) no cuentan filas.
SUB_PASOS: tuple[_SubStep, ...] = (
    _SubStep(name="setup", sql_file="00_setup.sql"),
    _SubStep(name="unidades", sql_file="01_unidades.sql",
             target_schema="postventa", target_table="unidades"),
    _SubStep(name="incidencias", sql_file="02_incidencias.sql",
             target_schema="postventa", target_table="incidencias"),
    _SubStep(name="tareas", sql_file="03_tareas.sql",
             target_schema="postventa", target_table="tareas"),
    _SubStep(name="procesos", sql_file="04_procesos.sql",
             target_schema="postventa", target_table="incidencia_procesos"),
    _SubStep(name="estado", sql_file="05_estado.sql"),
    _SubStep(name="adjuntos", sql_file="06_adjuntos.sql",
             target_schema="postventa", target_table="documento_adjuntos"),
    _SubStep(name="restringida", sql_file="07_restringida.sql",
             target_schema="postventa_restringida", target_table="contactos_incidencia"),
    _SubStep(name="coste_obra", sql_file="08_coste_obra.sql",
             target_schema="postventa", target_table="partida_obra_origen"),
)


class BuildPostventaStep(PipelineStep):
    """Construye `postventa` (general) y `postventa_restringida` (datos personales)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def name(self) -> str:
        return "build_postventa"

    @property
    def stage(self) -> str:
        return "build_aux"

    @property
    def depends_on(self) -> list[str]:
        # Las tablas solo leen `raw`; la vista de coste lee `compras` al consultar.
        return ["ingest_raw"]

    def run(self) -> StepResult:
        result = self._new_result()
        pg = build_postgres_client(self._settings)

        sql_dir = (
            Path(__file__).resolve().parents[2]
            / "infrastructure" / "postgres" / "sql" / "postventa"
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
            except Exception as e:  # captura amplia a propósito: el fallo sale
                # con el nombre del sub-paso (las guardas R12 y R21 lo usan)
                duration = (datetime.utcnow() - t0).total_seconds()
                logger.error(
                    "postventa_substep_failed",
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
                "postventa_substep_done",
                sub_step=sub.name, rows=rows,
                duration_s=round((datetime.utcnow() - t0).total_seconds(), 2),
            )

        result.status = StepStatus.SUCCESS
        result.rows_processed = total_rows
        result.finished_at = datetime.utcnow()
        return result
