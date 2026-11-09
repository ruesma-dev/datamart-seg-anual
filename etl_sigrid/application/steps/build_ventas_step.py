# etl_sigrid/application/steps/build_ventas_step.py
"""
Step que materializa los esquemas `ventas` y `ventas_restringida` (F-040).

Encadena los archivos SQL en orden:
    00_setup.sql           - los dos esquemas y las funciones locales (fecha,
                             CIF normalizado, persona física, CIF válido y
                             clase de recargo, con los literales del dominio)
    01_clientes.sql        - `clientes` (el CIF de la persona física a NULL)
    02_facturas.sql        - `facturas`, `factura_lineas` y `factura_recargos`
    03_certificaciones.sql - `certificaciones` y `certificacion_recargos`
    04_enlace.sql          - `certificacion_factura` y `cobertura_enlace`
    05_vistas.sql          - las vistas del cobro, el seguimiento y el contraste
    06_restringida.sql     - `ventas_restringida`: lo personal del cliente
    07_guardas.sql         - la guarda R24/R25 (recuentos, base, recargos y
                             nada personal en `ventas`)

Las tablas solo leen `raw` (y `maestro.centros_coste`, una vista de SQL puro
sobre `raw`, y lo que este mismo paso acaba de construir). Las VISTAS de
`05_vistas.sql` leen `tesoreria` en tiempo de consulta: no hace falta que
`build_tesoreria` se haya construido antes, solo que sus tablas existan. Por
eso `depends_on = ["ingest_raw"]`.

POR QUÉ ES UN ESQUEMA MÓDULO (patrón de `postventa` y `contabilidad`): **ningún
paso declara `build_ventas` en su `depends_on`**, así que si falla la nocturna
continúa y termina, y `R-FRESCURA` avisa de que sus dos esquemas vienen de una
noche anterior. Y los permisos se dan POR ESQUEMA: lo personal del cliente
vive en `ventas_restringida` para darlo solo al perfil total (D2, D6).
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

#: Donde viven los ocho SQL del módulo.
DIR_SQL_VENTAS: Path = (
    Path(__file__).resolve().parents[2] / "infrastructure" / "postgres" / "sql" / "ventas"
)


@dataclass(slots=True, frozen=True)
class _SubStep:
    name: str
    sql_file: str
    target_schema: str | None = None
    target_table: str | None = None


#: Los ocho ficheros SQL, EN ORDEN, y de qué tabla se cuentan filas. Es DATO,
#: como en `build_postventa_step`: sustituirlo en un test es lo que permite
#: ejercitar el recuento. `setup`, `vistas` y `guardas` no cuentan filas.
SUB_PASOS: tuple[_SubStep, ...] = (
    _SubStep(name="setup", sql_file="00_setup.sql"),
    _SubStep(name="clientes", sql_file="01_clientes.sql",
             target_schema="ventas", target_table="clientes"),
    _SubStep(name="facturas", sql_file="02_facturas.sql",
             target_schema="ventas", target_table="facturas"),
    _SubStep(name="certificaciones", sql_file="03_certificaciones.sql",
             target_schema="ventas", target_table="certificaciones"),
    _SubStep(name="enlace", sql_file="04_enlace.sql",
             target_schema="ventas", target_table="certificacion_factura"),
    _SubStep(name="vistas", sql_file="05_vistas.sql"),
    _SubStep(name="restringida", sql_file="06_restringida.sql",
             target_schema="ventas_restringida", target_table="clientes_contacto"),
    _SubStep(name="guardas", sql_file="07_guardas.sql"),
)


class BuildVentasStep(PipelineStep):
    """Construye `ventas` (general) y `ventas_restringida` (lo personal del cliente)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def name(self) -> str:
        return "build_ventas"

    @property
    def stage(self) -> str:
        return "build_aux"

    @property
    def depends_on(self) -> list[str]:
        # Las tablas solo leen `raw`; las vistas leen `tesoreria` al consultar.
        return ["ingest_raw"]

    def run(self) -> StepResult:
        result = self._new_result()
        pg = build_postgres_client(self._settings)

        total_rows = 0
        for sub in SUB_PASOS:
            sql_path = DIR_SQL_VENTAS / sub.sql_file
            if not sql_path.exists():
                result.status = StepStatus.FAILED
                result.error_message = f"SQL file no encontrado: {sql_path}"
                result.finished_at = datetime.utcnow()
                return result

            t0 = datetime.utcnow()
            try:
                pg.execute_sql_file(sql_path)
            except Exception as e:  # captura amplia a propósito: el fallo sale
                # con el nombre del sub-paso y la cifra de la guarda (R25)
                duration = (datetime.utcnow() - t0).total_seconds()
                logger.error(
                    "ventas_substep_failed",
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
                "ventas_substep_done",
                sub_step=sub.name, rows=rows,
                duration_s=round((datetime.utcnow() - t0).total_seconds(), 2),
            )

        result.status = StepStatus.SUCCESS
        result.rows_processed = total_rows
        result.finished_at = datetime.utcnow()
        return result
