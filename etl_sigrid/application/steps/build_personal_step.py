# etl_sigrid/application/steps/build_personal_step.py
"""
Step que materializa el schema `personal` (recursos, partes de trabajo, horas).

Encadena los archivos SQL en orden:
    00_setup.sql          - schema, función de fechas local y las dos tablas
                            con sus índices (`CREATE ... IF NOT EXISTS`)
    01_recursos.sql       - una fila por recurso de Sigrid (2.618)
    02_partes_lineas.sql  - una fila por línea de parte de trabajo (330.638)
    03_views.sql          - `v_pbi_horas_obra_mes`, solo `unidad = 'HORA'`

Lee de `raw.*` (res, con, auxrestip, emp, hmores, auxhor) y de **una** cosa
fuera de `raw`: `stg.obras`, para marcar qué líneas caen dentro del universo
del seguimiento. Eso, y solo eso, es lo que fija `depends_on = ["build_stg"]`.

POR QUÉ ES UN ESQUEMA MÓDULO Y NO PARTE DE `build_stg` (decisión del humano,
2026-09-18). `build_stg` es la puerta de F-024: un fallo del SQL de personal
dentro de `build_stg` dejaría al `mart` sin construir esa noche. Aquí no.
**Ningún paso declara `build_personal` en su `depends_on`**, así que si falla
la nocturna continúa y termina, y `R-FRESCURA` avisa al consumidor de que ese
esquema viene de una noche anterior — igual que `compras` y `retenciones`. El
segundo motivo, que fue el decisivo, es que los permisos se dan POR ESQUEMA:
aquí dentro hay nombre, NIF y DNI, y F-087 necesita poder decir «Power BI sí,
datos de personal no» con un GRANT.
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


#: Los cuatro ficheros SQL, EN ORDEN, y de qué tabla se cuentan filas.
#:
#: Vive fuera de `run()` por lo mismo que en `build_compras_step` y
#: `build_retenciones_step`: es DATO, y sustituirla en un test es lo único que
#: permite ejercitar el guardián de `target_schema`/`target_table`.
#:
#: `setup` no cuenta filas A PROPÓSITO: crea las dos tablas VACÍAS, así que un
#: recuento ahí valdría 0 la primera noche y no distinguiría «recién creada» de
#: «no construida».
SUB_PASOS: tuple[_SubStep, ...] = (
    _SubStep(name="setup", sql_file="00_setup.sql"),
    _SubStep(
        name="recursos",
        sql_file="01_recursos.sql",
        target_schema="personal",
        target_table="recursos",
    ),
    _SubStep(
        name="partes_lineas",
        sql_file="02_partes_lineas.sql",
        target_schema="personal",
        target_table="partes_lineas",
    ),
    _SubStep(name="views", sql_file="03_views.sql"),
)


class BuildPersonalStep(PipelineStep):
    """Construye el schema `personal` (recursos, líneas de parte y la vista)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def name(self) -> str:
        return "build_personal"

    @property
    def stage(self) -> str:
        return "build_aux"

    @property
    def depends_on(self) -> list[str]:
        # `stg.obras` es la única lectura fuera de `raw`: la marca
        # `en_seguimiento` de `partes_lineas`. `build_stg` ya depende de la
        # ingesta, así que declarar `ingest_raw` aquí sería redundante.
        return ["build_stg"]

    def run(self) -> StepResult:
        result = self._new_result()
        pg = build_postgres_client(self._settings)

        sql_dir = (
            Path(__file__).resolve().parents[2]
            / "infrastructure" / "postgres" / "sql" / "personal"
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
                    "personal_substep_failed",
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
                "personal_substep_done",
                sub_step=sub.name, rows=rows,
                duration_s=round((datetime.utcnow() - t0).total_seconds(), 2),
            )

        result.status = StepStatus.SUCCESS
        result.rows_processed = total_rows
        result.finished_at = datetime.utcnow()
        return result
