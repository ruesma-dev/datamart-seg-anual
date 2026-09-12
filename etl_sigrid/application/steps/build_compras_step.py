# etl_sigrid/application/steps/build_compras_step.py
"""
Step que materializa el schema `compras` (documentos de compra desde `raw`).

Encadena los archivos SQL en orden:
    00_setup.sql       - schema + funciones (serie, fecha, tipo de documento)
    01_documentos.sql  - contratos / albaranes / facturas (cabeceras + líneas)
    02_fact_linea.sql  - hechos unificados a nivel de línea
    03_views.sql       - vistas de negocio (consumo de contrato, proveedores…)
    04_formas_pago.sql - dimensión de formas de pago (auxpag + auxefp)
    05_vencimientos.sql- efectos de pago de la factura (F-080)
    06_pago_factura.sql- forma de pago de la factura y control contra contrato
    07_texto.sql       - el memo de la pestaña «Texto», íntegro y partido

Solo lee de `raw.*`. No necesita `stg` ni `mart`.

POR QUÉ EXISTE ESTE FICHERO (F-047, absorbe F-044). `build-compras` ejecutaba
su SQL **en línea dentro del comando**, sin step, y por eso **no dejaba fila en
`_meta.etl_runs`**: su fecha de build no era consultable por SQL y el aviso de
frescura del diccionario no podía servir de nada —mandaba citar una fecha que
no existía—. Convertirlo en step es lo que hace que la carga nocturna pueda
registrarlo con el `batch_id` de la noche, como los demás.
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


#: Los ocho ficheros SQL, EN ORDEN, y de qué tabla se cuentan filas.
#:
#: Vive fuera de `run()` a propósito: es DATO, no lógica. Así se puede leer sin
#: entrar en el bucle y —lo que lo motivó— se puede sustituir en un test para
#: ejercitar el guardián de `target_schema`/`target_table`, que con esta lista
#: cableada no se podía: todos sus sub-pasos declaran los dos campos o ninguno,
#: y por eso el mutante `and -> or` sobrevivía a la campaña.
SUB_PASOS: tuple[_SubStep, ...] = (
    _SubStep(name="setup", sql_file="00_setup.sql"),
    _SubStep(
        name="documentos",
        sql_file="01_documentos.sql",
        target_schema="compras",
        target_table="contratos",
    ),
    _SubStep(
        name="fact_linea",
        sql_file="02_fact_linea.sql",
        target_schema="compras",
        target_table="fact_compras_linea",
    ),
    _SubStep(name="views", sql_file="03_views.sql"),
    # F-073: la dimensión de formas de pago. Ya NO es la última y ya la lee
    # alguien: F-080 la cablea a la factura en `06_pago_factura.sql`, que va
    # detrás por eso. El cableado a `compras.contratos` sigue siendo de F-067.
    _SubStep(
        name="formas_pago",
        sql_file="04_formas_pago.sql",
        target_schema="compras",
        target_table="formas_pago",
    ),
    # F-080: los efectos de pago de la factura, su forma de pago y su texto.
    # EL ORDEN NO ES DECORATIVO: `05` necesita las funciones de `00_setup.sql`
    # y `compras.facturas` (01); `06` agrega `compras.vencimientos` (05) y lee
    # la dimensión `compras.formas_pago` (04, F-073), así que va detrás de las
    # dos. `07` solo necesita `raw.con`.
    _SubStep(
        name="vencimientos",
        sql_file="05_vencimientos.sql",
        target_schema="compras",
        target_table="vencimientos",
    ),
    _SubStep(
        name="pago_factura",
        sql_file="06_pago_factura.sql",
        target_schema="compras",
        target_table="v_facturas_pago",
    ),
    # Construye DOS tablas (`documento_texto` y `documento_comentarios`) y
    # cuenta la de comentarios: es la que puede salir mal sin que nada falle
    # —si el corte del memo no partiera, quedaría una fila por documento en vez
    # de una por comentario— y contarla cubre también a `documento_texto`,
    # porque sin memos no hay comentarios.
    _SubStep(
        name="texto",
        sql_file="07_texto.sql",
        target_schema="compras",
        target_table="documento_comentarios",
    ),
)


class BuildComprasStep(PipelineStep):
    """Construye el schema `compras` (contratos, albaranes, facturas)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def name(self) -> str:
        return "build_compras"

    @property
    def stage(self) -> str:
        return "build_compras"

    @property
    def depends_on(self) -> list[str]:
        # Solo necesita raw.* (la ingesta). No depende de stage ni mart.
        return ["ingest_raw"]

    def run(self) -> StepResult:
        result = self._new_result()
        pg = build_postgres_client(self._settings)

        sql_dir = (
            Path(__file__).resolve().parents[2]
            / "infrastructure" / "postgres" / "sql" / "compras"
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
                    "compras_substep_failed",
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
                "compras_substep_done",
                sub_step=sub.name, rows=rows,
                duration_s=round((datetime.utcnow() - t0).total_seconds(), 2),
            )

        result.status = StepStatus.SUCCESS
        result.rows_processed = total_rows
        result.finished_at = datetime.utcnow()
        return result
