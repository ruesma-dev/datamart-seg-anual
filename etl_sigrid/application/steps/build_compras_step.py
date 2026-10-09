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
    08_comparativos.sql- el comparativo de ofertas y sus ofertas (F-038)
    09_comparativos_detalle.sql - sus líneas, el objetivo y las firmas (F-038)
    10_necesidades.sql - el documento de necesidades de compra, el DPC (F-067)
    11_historial_estados.sql - la FOTO DIARIA de estados (F-067), PERSISTENTE
    12_documento_procesos.sql - el historial de PROCESOS de `rac` (F-085)
    13_estado_documentos.sql - el estado actual y desde cuándo, de `rac` (F-132)

Lee de `raw.*` y, como `03_views.sql`, de `maestro.v_obra_fichas` (de
`build_maestros`, que corre antes en `run-all`). No necesita `stg` ni `mart`.

`09` lee además `descompuestos.lineas` (la base del coste objetivo), y es el
único SQL fuera de `sql/descompuestos/` que lo hace. `build_descompuestos`
corre DESPUÉS en `run-all` y este paso no lo declara en `depends_on` a
propósito: lee el descompuesto de la noche anterior, y la primera ABC y el
master 0 —las versiones que dan la base— están congeladas (F-038, design §1).

`11` es distinto de todos los demás (F-067): sus dos tablas
(`historial_estados` e `historial_estados_fotos`) NO se reconstruyen. Son la
foto diaria de estados de contratos y facturas, que desde F-132 es el RESPALDO
de `rac` mientras dura el contraste (la antigüedad del estado la publica `13`);
el SQL las crea con `CREATE TABLE IF NOT EXISTS`, nunca las borra ni las vacía,
y cada noche les añade la foto de la ingesta. No depende de nada del esquema; si
un sub-paso anterior falla, esa noche no hay foto y se ve en
`historial_estados_fotos` (un hueco), no se pierde lo ya guardado.

`12` (F-085) va DETRÁS de `11` a propósito: es el más caro de los dos (~1 M de
pasos de `raw.rac` con dos ventanas por documento) y no lo necesita nadie del
esquema, así que si fallara, la foto de esa noche ya está tomada. Lee `raw.rac`,
`raw.con`, `raw.usu` y la función `fn_estado_documento` de `00_setup.sql`.

`13` (F-132) va el ÚLTIMO porque la vista `compras.v_estado_documentos` lee
`compras.documento_procesos`, y el `DROP TABLE ... CASCADE` de `12` se la lleva
cada noche: `13` la vuelve a crear. Lee además las tres cabeceras (`01`, `08`).

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


#: Los ficheros SQL, EN ORDEN, y de qué tabla se cuentan filas.
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
    # detrás por eso. El cableado a `compras.contratos` lo hizo F-067 en `01`,
    # leyendo `raw.auxpag` porque esta dimensión se construye después.
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
    # F-038: `compras.comparativo_ofertas` y `compras.comparativos`. Va al
    # final porque lee `compras.contrato_lineas` (01) y las funciones de
    # `00_setup.sql`. Cuenta `comparativos`, la del grano (una fila por
    # comparativo de `raw.com`): las ofertas no existen sin comparativo. Si la
    # guarda R21 salta (un comparativo con dos contratos), el paso falla con
    # el nombre de este sub-paso y el mensaje de la guarda.
    _SubStep(
        name="comparativos",
        sql_file="08_comparativos.sql",
        target_schema="compras",
        target_table="comparativos",
    ),
    # F-038 Fase 2: las líneas del concurso y de las ofertas (con la base del
    # coste objetivo en el descompuesto), el objetivo y las firmas. Va detrás
    # de `08` porque lee `comparativo_ofertas` y `comparativos`. Cuenta
    # `comparativo_oferta_lineas`, el grueso (~787 k filas) y la que puede
    # salir mal sin que nada falle.
    _SubStep(
        name="comparativos_detalle",
        sql_file="09_comparativos_detalle.sql",
        target_schema="compras",
        target_table="comparativo_oferta_lineas",
    ),
    # F-067 (con F-125): el documento de necesidades de compra (DPC) de cada
    # obra. Solo lee `raw`; cuenta su única tabla (~277 filas).
    _SubStep(
        name="necesidades",
        sql_file="10_necesidades.sql",
        target_schema="compras",
        target_table="necesidades",
    ),
    # F-067: la foto diaria de estados. El ÚLTIMO a propósito: no lee nada de
    # `compras` (solo `raw.con` y sus dos tablas), y sus tablas no se
    # reconstruyen. Cuenta `historial_estados`, los tramos: crecen cada noche
    # con los cambios y nunca bajan; si un día bajaran, alguien las ha borrado.
    # Si la guarda del 98 % salta (ingesta a medias), el paso falla con el
    # nombre de este sub-paso y la foto no se toma.
    _SubStep(
        name="historial_estados",
        sql_file="11_historial_estados.sql",
        target_schema="compras",
        target_table="historial_estados",
    ),
    # F-085: el historial de PROCESOS de `rac` (quién hizo qué paso, desde qué
    # estado, a cuál y cuándo). DETRÁS de la foto: si este falla, la foto de
    # la noche ya está tomada. Cuenta su única tabla (~1,01 M de pasos).
    _SubStep(
        name="documento_procesos",
        sql_file="12_documento_procesos.sql",
        target_schema="compras",
        target_table="documento_procesos",
    ),
    # F-132: `compras.v_estado_documentos`, el estado actual de contratos,
    # facturas y comparativos y desde cuándo, sacado del último paso de `rac`.
    # DETRÁS de `12`, cuyo `DROP ... CASCADE` tira la vista cada noche. Es una
    # VISTA: no declara tabla destino y no se cuentan filas (contarlas la
    # recorrería entera para nada).
    _SubStep(name="estado_documentos", sql_file="13_estado_documentos.sql"),
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
