# etl_sigrid/application/steps/build_stg_step.py
"""
Step que materializa el esquema stg.* a partir de raw.*.

Flujo:
    1. Asegura schemas y _meta.etl_runs (idempotente).
    2. Ejecuta en orden los archivos SQL de sql/stg/:
        00_functions.sql               - funciones helper (fecha Sigrid → DATE)
        01_ddl.sql                     - CREATE TABLE IF NOT EXISTS de stg.*
        02_ambitos.sql                 - VISTA stg.ambitos (clasificación)
        03_obras.sql                   - TRUNCATE + INSERT stg.obras
        04_partidas.sql                - TRUNCATE + INSERT stg.partidas
        05_fases.sql                   - TRUNCATE + INSERT stg.fases
        06_presupuesto.sql             - TRUNCATE + INSERT stg.presupuesto (el grande)
        07_version_master_vigente.sql  - TRUNCATE + INSERT (parametrizado con cod=15)

Cada sub-step se registra en _meta.etl_runs con su tiempo y filas procesadas.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from config.settings import Settings
from etl_sigrid.application.steps.base import PipelineStep
from etl_sigrid.domain.coherencia import (
    VeredictoCoherencia,
    evaluar_coherencia_raw,
    formatear_veredicto_raw,
)
from etl_sigrid.domain.entities import StepResult, StepStatus
from etl_sigrid.domain.tramos import planificar_tramos, tramos_sobredimensionados
from etl_sigrid.infrastructure.logging_config import get_logger
from etl_sigrid.infrastructure.postgres.client_factory import build_postgres_client
from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

logger = get_logger(__name__)

# Directorio de los SQL de la capa stg. Constante de módulo para que los tests
# estáticos de F-019 lean EXACTAMENTE el fichero que ejecuta el step.
DIRECTORIO_SQL_STG = (
    Path(__file__).resolve().parent.parent.parent
    / "infrastructure" / "postgres" / "sql" / "stg"
)

# --- Troceo de stg.plan_mensual (F-019) ------------------------------------
# El marcador se sustituye por la lista de obras del tramo (enteros validados)
# justo antes de ejecutar. Va como comentario SQL a propósito: un fichero al
# que le falte la sustitución no es SQL válido —`= ANY ()`— y por tanto no
# puede colarse una ejecución sin filtro por descuido.
MARCADOR_FILTRO_OBRAS = "/*F019_FILTRO_OBRAS*/"

# Las DOS ramas del fichero (master amb 8/11 y reales amb 3/7) llevan filtro.
# Filtrar solo una duplicaría las filas de la otra en cada tramo.
RAMAS_CON_FILTRO = 2

# --- Puerta de coherencia de raw (F-024) ------------------------------------
# La puerta se registra como sub-paso para que aparezca en `timings` con su
# duración (que debe ser de milisegundos: dos SELECT sobre `_meta`) y para que
# quede constancia escrita de su veredicto, incluso cuando se omite.
PASO_PUERTA_RAW = "build_stg.puerta_raw"


class PlanMensualAbortado(RuntimeError):  # noqa: N818 — nombres en español
    """El build por tramos se paró a propósito y dejó la tabla vacía.

    Se distingue de cualquier otro error para que quede claro, al leer el
    fallo, que la parada fue una decisión del guardián de disco (o la limpieza
    tras el fallo de un tramo) y no un error inesperado.
    """


def componer_sql_tramo(sql_texto: str, obras: Sequence[int]) -> str:
    """Sustituye el marcador de filtro por las obras del tramo.

    Composición TEXTUAL y no `%(param)s` a propósito: los comentarios de
    `08_plan_mensual.sql` están llenos de porcentajes literales («llega al
    93 %») y psycopg los tomaría por marcadores de parámetro. El precedente
    parametrizado del proyecto (`07_version_master_vigente.sql`) funciona
    porque ese fichero no tiene ningún `%` suelto.

    Que la composición sea textual obliga a blindar la entrada, y eso es lo
    que hacen las tres comprobaciones de aquí (R7):

    1. Tramo sin obras: no se ejecuta nada (un `ARRAY[]` vacío no filtraría
       nada útil y delata un plan de tramos roto).
    2. Cada obra tiene que ser un entero, y `bool` no cuenta aunque Python lo
       considere subclase de `int`: `ARRAY[True]` no es una lista de obras.
       Nada que venga de fuera puede llegar a concatenarse en el SQL.
    3. El marcador tiene que aparecer una vez por rama. Si alguien lo borra al
       editar el fichero, esto falla ANTES de enviar nada a la BBDD, en vez de
       ejecutar el build entero sin filtro, que es justo el incidente.
    """
    if not obras:
        raise ValueError(
            "Tramo sin obras: no se compone ni se ejecuta nada. "
            "El planificador de tramos no debería producir tramos vacíos."
        )

    for obra in obras:
        # `type(...) is not int` y no `isinstance`: `bool` es subclase de
        # `int`, y `ARRAY[True]` no es una lista de obras.
        if type(obra) is not int:
            raise TypeError(
                f"El filtro de tramo solo admite identificadores de obra "
                f"enteros; llegó {obra!r} ({type(obra).__name__}). No se "
                f"compone SQL con nada que no sea un entero validado."
            )

    apariciones = sql_texto.count(MARCADOR_FILTRO_OBRAS)
    if apariciones != RAMAS_CON_FILTRO:
        raise ValueError(
            f"El SQL de plan_mensual debe contener el marcador "
            f"{MARCADOR_FILTRO_OBRAS} exactamente {RAMAS_CON_FILTRO} veces "
            f"(una por rama) y aparece {apariciones}. Sin las dos "
            f"sustituciones el build se ejecutaría sin filtrar por tramo, o "
            f"filtrando solo una rama y duplicando la otra: no se ejecuta."
        )

    lista = ", ".join(str(obra) for obra in obras)
    return sql_texto.replace(MARCADOR_FILTRO_OBRAS, f"ARRAY[{lista}]::BIGINT[]")


@dataclass(slots=True, frozen=True)
class _SubStep:
    """Un sub-paso de build_stg: un archivo SQL + tabla destino (para contar filas)."""

    name: str
    sql_file: str
    target_schema: str | None = None
    target_table: str | None = None
    params: dict | tuple | None = None
    # Sub-paso que NO se ejecuta de una pasada, sino tramo a tramo con puerta
    # de disco entre medias (F-019). Hoy solo lo es `build_plan_mensual`.
    por_tramos: bool = False


class BuildStgStep(PipelineStep):
    """Construye el esquema stg desde raw."""

    def __init__(
        self,
        settings: Settings,
        batch_id: str | None = None,
        omitir_puerta: bool = False,
    ) -> None:
        self._settings = settings
        self._batch_id = batch_id
        self._omitir_puerta = omitir_puerta

    @property
    def name(self) -> str:
        return "build_stg"

    @property
    def stage(self) -> str:
        return "stage"

    @property
    def depends_on(self) -> list[str]:
        return ["ingest_raw"]

    def run(self) -> StepResult:
        result = self._new_result()
        pg = build_postgres_client(self._settings)
        # El auto-bootstrap (CREATE DATABASE/schemas/_meta) se ejecutará lazy en
        # la primera conexión. No hace falta llamada explícita.

        # Puerta de coherencia de raw (F-024, R10). Va LA PRIMERA, antes
        # incluso del pre-flight: si el raw no acredita una carga completa, no
        # se ejecuta ni una consulta más contra el servidor compartido, y
        # desde luego ni un TRUNCATE. Un `TRUNCATE stg.obras` ya ejecutado no
        # se deshace porque el step devuelva FAILED después.
        veredicto = self._puerta_raw(pg)
        if not veredicto.ok and not self._omitir_puerta:
            result.status = StepStatus.FAILED
            result.error_message = formatear_veredicto_raw(veredicto)
            result.finished_at = datetime.utcnow()
            return result

        # Pre-flight check: verifica que raw tiene todas las columnas que los
        # SQL de stg van a usar. Si falta alguna, falla con un mensaje claro
        # ANTES de tocar ningún dato.
        try:
            self._preflight_check(pg)
        except ValueError as e:
            result.status = StepStatus.FAILED
            result.error_message = f"Pre-flight check falló: {e}"
            result.finished_at = datetime.utcnow()
            logger.error("preflight_check_failed", error=str(e))
            return result

        sql_dir = DIRECTORIO_SQL_STG

        cod_version_master = self._settings.business_rules["sigrid"]["campos_extendidos"][
            "cod_version_master_vigente"
        ]

        sub_steps: list[_SubStep] = [
            _SubStep("functions",         "00_functions.sql"),
            _SubStep("ddl",               "01_ddl.sql"),
            _SubStep("ambitos_view",      "02_ambitos.sql"),
            _SubStep("build_obras",       "03_obras.sql",       "stg", "obras"),
            _SubStep("build_partidas",    "04_partidas.sql",    "stg", "partidas"),
            _SubStep("build_fases",       "05_fases.sql",       "stg", "fases"),
            _SubStep("build_presupuesto", "06_presupuesto.sql", "stg", "presupuesto"),
            _SubStep(
                "build_version_master_vigente",
                "07_version_master_vigente.sql",
                "stg",
                "version_master_vigente",
                params={"cod": cod_version_master},
            ),
            _SubStep(
                "build_plan_mensual",
                "08_plan_mensual.sql",
                "stg",
                "plan_mensual",
                por_tramos=True,
            ),
        ]

        table_stats: dict[str, int] = {}
        total_rows = 0

        for sub in sub_steps:
            sql_path = sql_dir / sub.sql_file
            run_id = pg.record_run_start(
                "stage", f"build_stg.{sub.name}", self._batch_id
            )

            t0 = datetime.utcnow()
            try:
                if sub.por_tramos:
                    self._build_plan_mensual_por_tramos(pg, sql_path)
                else:
                    pg.execute_sql_file(sql_path, params=sub.params)

                rows = 0
                if sub.target_schema and sub.target_table:
                    rows = pg.count_rows(sub.target_schema, sub.target_table)
                    table_stats[f"{sub.target_schema}.{sub.target_table}"] = rows
                    total_rows += rows

                duration = (datetime.utcnow() - t0).total_seconds()
                logger.info(
                    "stg_substep_done",
                    sub_step=sub.name,
                    rows=rows,
                    duration_s=round(duration, 2),
                )
                pg.record_run_end(run_id, "SUCCESS", rows_processed=rows)

            except Exception as e:
                duration = (datetime.utcnow() - t0).total_seconds()
                logger.exception(
                    "stg_substep_failed",
                    sub_step=sub.name,
                    duration_s=round(duration, 2),
                )
                pg.record_run_end(run_id, "FAILED", error_message=str(e))
                result.status = StepStatus.FAILED
                result.error_message = f"Fallo en {sub.name}: {e}"
                result.finished_at = datetime.utcnow()
                result.rows_processed = total_rows
                result.metadata = {"table_stats": table_stats, "failed_at": sub.name}
                return result

        result.status = StepStatus.SUCCESS
        result.rows_processed = total_rows
        result.finished_at = datetime.utcnow()
        result.metadata = {
            "table_stats": table_stats,
            # De qué carga de raw salió este stg. Es lo que permite, tres días
            # después, saber si el cuadro que no cuadra viene de aquí.
            "raw_batch_id": veredicto.batch_id,
        }
        return result

    # ---------------------------------------------------------------------
    # Puerta de coherencia de raw (F-024, R10-R12)
    # ---------------------------------------------------------------------

    def _puerta_raw(self, pg: PostgresClient) -> VeredictoCoherencia:
        """Evalúa si `raw` acredita una carga completa y deja constancia.

        Se evalúa SIEMPRE, también con `--sin-puerta`: la vía de escape sirve
        para construir de todas formas, no para dejar de mirar. El veredicto
        acaba escrito en `_meta.etl_runs` pase lo que pase, que es lo que
        convierte «alguien construyó sobre un raw raro» en un hecho
        consultable en vez de en una sospecha.

        Devolver el veredicto en vez de lanzar es deliberado: quien decide qué
        hacer con un KO es `run()`, según haya `--sin-puerta` o no.
        """
        run_id = pg.record_run_start("stage", PASO_PUERTA_RAW, self._batch_id)

        requeridas = [
            tabla["source_table"]
            for tabla in self._settings.tables_sigrid.get("tables", [])
        ]
        veredicto = evaluar_coherencia_raw(pg.fetch_estado_raw(), requeridas)
        mensaje = formatear_veredicto_raw(veredicto)

        if self._omitir_puerta:
            # SKIPPED aunque el veredicto sea OK: lo que esta fila cuenta es
            # que el build se hizo SIN puerta, no lo que la puerta habría
            # dictaminado. Quien audite `_meta.etl_runs` tiene que poder
            # distinguir un build verificado de uno que no lo fue.
            pg.record_run_end(
                run_id,
                StepStatus.SKIPPED.value,
                error_message=f"puerta omitida por --sin-puerta; veredicto: {mensaje}",
            )
            logger.warning(
                "puerta_omitida",
                veredicto_ok=veredicto.ok,
                motivo=mensaje,
            )
        elif veredicto.ok:
            pg.record_run_end(run_id, StepStatus.SUCCESS.value)
            logger.info(
                "puerta_raw_ok",
                raw_batch_id=veredicto.batch_id,
                tablas=len(requeridas),
            )
        else:
            pg.record_run_end(
                run_id, StepStatus.FAILED.value, error_message=mensaje
            )
            logger.error(
                "puerta_raw_ko",
                faltantes=list(veredicto.faltantes),
                no_exitosas=[e.tabla for e in veredicto.no_exitosas],
                sin_batch=[e.tabla for e in veredicto.sin_batch],
                batches=[b for b, _ in veredicto.batches_distintos],
            )

        return veredicto

    # ---------------------------------------------------------------------
    # Build de stg.plan_mensual por tramos (F-019)
    # ---------------------------------------------------------------------

    def _build_plan_mensual_por_tramos(
        self, pg: PostgresClient, sql_path: Path
    ) -> int:
        """Construye `stg.plan_mensual` tramo a tramo. Devuelve filas insertadas.

        Secuencia, y el porqué de cada paso:

        1. **Pesos por obra** y **plan de tramos** (dominio puro). Las obras
           que no caben ni solas se avisan; no abortan (es el mínimo físico).
        2. **Vaciado inicial**, una sola vez: el fichero SQL ya no lo hace,
           porque hacerlo por tramo dejaría solo el último.
        3. **Por cada tramo**: puerta de disco → SQL compuesto con sus obras →
           una transacción → registro en `_meta.etl_runs` y log estructurado.
        4. **Ante límite superado, medición imposible o tramo fallido**: se
           vacía la tabla y se propaga. Ni ese tramo ni los siguientes.

        Que la tabla quede VACÍA al abortar es deliberado: una tabla a medias
        es indistinguible de una completa para quien la lea, y `build_mart`
        vendría detrás a construir sobre datos parciales.
        """
        max_filas = self._settings.postgres.tramo_max_filas
        total_gb = self._settings.postgres.disco_total_gb
        limite_pct = self._settings.postgres.disco_limite_pct

        sql_plantilla = sql_path.read_text(encoding="utf-8")
        pesos_por_obra = pg.fetch_pesos_plan_mensual()
        tramos = planificar_tramos(pesos_por_obra, max_filas)

        for tramo in tramos_sobredimensionados(tramos, max_filas):
            logger.warning(
                "plan_mensual_tramo_sobredimensionado",
                tramo=tramo.indice,
                obras=list(tramo.obras),
                peso=tramo.peso,
                max_filas=max_filas,
            )

        pg.truncate_table("stg", "plan_mensual")
        logger.info(
            "plan_mensual_plan_de_tramos",
            tramos=len(tramos),
            obras=len(pesos_por_obra),
            peso_total=sum(pesos_por_obra.values()),
            max_filas=max_filas,
        )

        total = len(tramos)
        filas_totales = 0

        for tramo in tramos:
            etiqueta = f"{tramo.indice}/{total}"
            run_id = pg.record_run_start(
                "stage",
                f"build_stg.build_plan_mensual.tramo_{tramo.indice:02d}",
                self._batch_id,
            )
            t0 = datetime.utcnow()

            # --- Puerta de disco, ANTES del tramo (R8, R9, R10) ---
            try:
                ocupacion_pct = pg.medir_ocupacion_disco_pct(total_gb)
            except Exception as error:
                motivo = (
                    f"no se pudo medir la ocupación del disco antes del tramo "
                    f"{etiqueta}: {error}. No se ejecuta a ciegas."
                )
                pg.record_run_end(run_id, "FAILED", error_message=motivo)
                self._abortar_plan_mensual(pg, motivo)

            if ocupacion_pct > limite_pct:
                motivo = (
                    f"ocupación del disco {ocupacion_pct} % por encima del "
                    f"límite {limite_pct} % antes del tramo {etiqueta}: el "
                    f"servidor es compartido y el build para aquí."
                )
                pg.record_run_end(run_id, "FAILED", error_message=motivo)
                self._abortar_plan_mensual(pg, motivo)

            # --- El tramo, en su propia transacción (R11) ---
            try:
                filas = pg.execute_sql_text(
                    componer_sql_tramo(sql_plantilla, tramo.obras)
                )
            except Exception as error:
                motivo = f"falló el tramo {etiqueta}: {error}"
                pg.record_run_end(run_id, "FAILED", error_message=motivo)
                self._abortar_plan_mensual(pg, motivo)

            filas_totales += filas
            pg.record_run_end(run_id, "SUCCESS", rows_processed=filas)
            logger.info(
                "plan_mensual_tramo",
                tramo=etiqueta,
                obras=len(tramo.obras),
                peso=tramo.peso,
                filas=filas,
                duracion_s=(datetime.utcnow() - t0).total_seconds(),
                ocupacion_pct=ocupacion_pct,
            )

        return filas_totales

    def _abortar_plan_mensual(self, pg: PostgresClient, motivo: str) -> None:
        """Vacía `stg.plan_mensual` y propaga. Nunca vuelve."""
        pg.truncate_table("stg", "plan_mensual")
        logger.error("plan_mensual_abortado", motivo=motivo)
        raise PlanMensualAbortado(motivo)

    # ---------------------------------------------------------------------
    # Pre-flight check
    # ---------------------------------------------------------------------

    def _preflight_check(self, pg: PostgresClient) -> None:
        """
        Verifica que raw.* tiene todas las columnas que los SQL de stg necesitan.

        Recolecta TODOS los errores y los reporta en una única excepción al
        final, para no obligar a iterar arreglando uno a uno. Si tres tablas
        tienen problemas, el mensaje los lista los tres.

        Mantener esta lista actualizada es responsabilidad de quien edita los SQL:
        si añades una columna nueva a un SQL, añádela también aquí.
        """
        required_by_table: dict[tuple[str, str], list[str]] = {
            ("raw", "con"):       ["ide", "cod", "res"],
            ("raw", "obr"):       ["ide", "decc", "decp", "deci"],
            ("raw", "obrctr"):    ["ide", "obride", "fecreaact",
                                   "fecreaini", "fecreafin",
                                   "fecpreini", "fecprefin"],
            # Catálogos para mostrar texto en la cabecera del cierre (Tanda 3.1)
            # OJO: cen NO tiene 'res' propio - hereda de con (Tanda 3.1.1).
            ("raw", "cen"):       ["ide"],
            ("raw", "auxobrtip"): ["ide", "res"],
            ("raw", "auxobrcla"): ["ide", "res"],
            ("raw", "obrparpar"): ["ide", "obride", "padide", "cod", "res", "tipdes", "unimed", "tcaide"],
            ("raw", "obrfas"):    ["ide", "obride", "fasnum", "fecini", "fecfin", "ano", "mes", "res"],
            ("raw", "obrfasamb"): ["ide", "obride", "amb", "fas", "plafec", "fec", "res", "tex"],
            ("raw", "obrparpre"): ["ide", "obride", "paride", "amb", "fas", "can", "pre", "planif", "totinc", "impcoe"],
            ("raw", "conext"):    ["conide", "cod", "valn"],
            ("raw", "auxobramb"): ["ide", "cod", "res"],
            ("raw", "auxobrtca"): ["ide", "cod", "res"],
        }

        errors: list[str] = []
        for (schema, table), cols in required_by_table.items():
            try:
                pg.assert_columns_exist(schema, table, cols)
            except ValueError as e:
                errors.append(str(e))

        if errors:
            # Une todos los errores en un mensaje único, separados por linea en blanco
            joined = "\n\n  · " + "\n\n  · ".join(errors)
            raise ValueError(
                f"Pre-flight detectó {len(errors)} problema(s) en raw.*:{joined}\n\n"
                f"Ejecuta 'python main.py inspect-raw' para ver el esquema completo "
                f"de todas las tablas raw."
            )

        logger.info(
            "preflight_check_passed",
            tables_validated=len(required_by_table),
        )
