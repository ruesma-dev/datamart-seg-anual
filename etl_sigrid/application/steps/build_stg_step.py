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
        06_presupuesto.sql             - DELETE derivado + INSERT, acotado a las
                                         obras vivas (F-025). El grande.
        07_version_master_vigente.sql  - TRUNCATE + INSERT (parametrizado con cod=15)

        08_plan_mensual.sql            - por tramos (F-019) y acotado (F-025)

Cada sub-step se registra en _meta.etl_runs con su tiempo y filas procesadas.

F-025 metio en medio el sub-paso `plan_ventana`, que decide que obras se
reconstruyen esta noche y cuales conservan su ultima version buena. Va
despues de `05_fases.sql` porque la regla de actividad se mide sobre
`stg.fases`, y antes de `06_presupuesto.sql`, que es el primer acotado.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
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
from etl_sigrid.domain.ventana import (
    MOTIVO_COMPLETA,
    Plan,
    clasificar_obras,
    criterio_desde_reglas,
    sello_sql,
    toca_reconstruccion_completa,
)
from etl_sigrid.infrastructure.logging_config import get_logger
from etl_sigrid.infrastructure.postgres.client_factory import build_postgres_client
from etl_sigrid.infrastructure.postgres.postgres_client import (
    TABLAS_ACOTADAS,
    PostgresClient,
)

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

# --- Ventana de negocio (F-025) --------------------------------------------
# El marcador equivalente en `06_presupuesto.sql`, que con DA-2 pasa también a
# construirse solo para las obras vivas. Se llama distinto que el de F-019 a
# propósito: son dos ficheros con dos formas de filtrar (aquí una sola pasada,
# allí sesenta tramos), y un nombre común invitaría a sustituirlos con el mismo
# código sin mirar cuántas veces aparece cada uno.
MARCADOR_FILTRO_PRESUPUESTO = "/*F025_FILTRO_OBRAS*/"

# `06_presupuesto.sql` no tiene ramas: su `WHERE` es uno solo.
FILTROS_EN_PRESUPUESTO = 1

# Los ficheros cuyo texto entra en el SELLO del SQL (R17). Si cambia cualquiera
# de los dos, esa noche se reconstruyen TODAS las obras: sin esto, un arreglo
# como el de F-052 solo alcanzaría a las 40 obras vivas y las otras 880
# seguirían publicando lo de antes, en silencio.
#
# El orden es significativo (entra en el hash) y es el de ejecución.
FICHEROS_DEL_SELLO = ("06_presupuesto.sql", "08_plan_mensual.sql")

# El sub-paso que compone el plan de la noche. Como la puerta de F-024, se
# registra en `_meta.etl_runs` para que aparezca en `timings` con su duración y
# para que quede escrito qué se decidió esa noche.
PASO_PLAN_VENTANA = "build_stg.plan_ventana"

# EL HITO DE LA RECONSTRUCCIÓN COMPLETA (R25, DA-4). Se escribe en
# `_meta.etl_runs` **solo cuando la noche completa TERMINA BIEN**, y de ahí lo
# lee `toca_reconstruccion_completa` la noche siguiente.
#
# Vive en `_meta.etl_runs` y no en una tabla nueva por dos razones: `python
# main.py timings` lo ve como un paso más, y sobrevive a una obra que aparezca
# o desaparezca del maestro, que es lo que rompería derivar la fecha de un
# `MIN(construido_at)` sobre `_meta.obra_build`.
PASO_RECONSTRUCCION_COMPLETA = "build_stg.reconstruccion_completa"

# --- Puerta de coherencia de raw (F-024) ------------------------------------
# La puerta se registra como sub-paso para que aparezca en `timings` con su
# duración (que debe ser de milisegundos: dos SELECT sobre `_meta`) y para que
# quede constancia escrita de su veredicto, incluso cuando se omite.
PASO_PUERTA_RAW = "build_stg.puerta_raw"


class PlanMensualAbortado(RuntimeError):  # noqa: N818 — nombres en español
    """El build por tramos se paró a propósito.

    Se distingue de cualquier otro error para que quede claro, al leer el
    fallo, que la parada fue una decisión del guardián de disco (o el fallo de
    un tramo) y no un error inesperado.

    **Desde F-025 ya NO vacía la tabla.** Hasta entonces sí, porque una tabla a
    medias era indistinguible de una completa; con el borrado derivado lo que
    queda tras un fallo son obras enteras con su última versión buena, y
    vaciarlas destruiría lo congelado. El nombre se conserva porque es el que
    citan los tests y los logs de F-019.
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

    Las dos primeras las hace ahora `_lista_de_obras`, porque F-025 las
    necesita también para el borrado derivado y dos copias de un blindaje
    divergen.
    """
    apariciones = sql_texto.count(MARCADOR_FILTRO_OBRAS)
    if apariciones != RAMAS_CON_FILTRO:
        raise ValueError(
            f"El SQL de plan_mensual debe contener el marcador "
            f"{MARCADOR_FILTRO_OBRAS} exactamente {RAMAS_CON_FILTRO} veces "
            f"(una por rama) y aparece {apariciones}. Sin las dos "
            f"sustituciones el build se ejecutaría sin filtrar por tramo, o "
            f"filtrando solo una rama y duplicando la otra: no se ejecuta."
        )

    lista = _lista_de_obras(obras)
    filtrado = sql_texto.replace(MARCADOR_FILTRO_OBRAS, f"ARRAY[{lista}]::BIGINT[]")

    # EL BORRADO DERIVADO (F-025, R10). Va DELANTE del INSERT y en el mismo
    # texto, así que las dos sentencias comparten transacción: `execute_sql_text`
    # abre una conexión por llamada. Si el proceso muere entre las dos, la
    # transacción no llega a confirmarse y no se ha perdido nada.
    #
    # Y va compuesto con LA MISMA lista de obras, no con otra: el conjunto que
    # se borra ES el que se va a escribir, así que es imposible borrar una obra
    # que luego no se reinserte.
    return componer_borrado_derivado("plan_mensual", obras) + "\n" + filtrado


def _lista_de_obras(obras: Sequence[int]) -> str:
    """Valida y rinde las obras como lista para un `ARRAY[...]` (R7).

    La composición del SQL es TEXTUAL —los comentarios de `08_plan_mensual.sql`
    están llenos de porcentajes literales y psycopg los tomaría por marcadores
    de parámetro—, así que la entrada se blinda aquí, en un solo sitio, y lo
    usan tanto el filtro del tramo como el borrado derivado.
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

    return ", ".join(str(obra) for obra in obras)


def componer_borrado_derivado(tabla: str, obras: Sequence[int]) -> str:
    """El `DELETE` de las obras que se van a reinsertar (F-025, R10).

    **Es el corazón de la feature.** El `TRUNCATE` global que había antes
    borraba las 920 obras para reescribirlas todas; con la ventana encendida
    habría borrado 920 y reescrito 40. Aquí lo que se borra se **deriva** de lo
    que se va a escribir, y de ahí salen tres propiedades:

    1. **Autoconsistencia.** No hay dos listas que puedan desincronizarse: es la
       misma lista, compuesta una vez.
    2. **Cada tramo es atómico e idempotente.** Si el proceso muere, las obras
       hechas están al día y las demás conservan el dato de anoche: la tabla
       queda COHERENTE, no truncada.
    3. **Repara la avería del 02-sep**, que dejó `stg.plan_mensual` al 21,6 %.
       Vale por sí solo aunque el acotado no ahorrase nada.

    Va **por índice**: `idx_plan_mensual_obra_amb` e `idx_pres_obra_amb`
    empiezan los dos por `obra_id` (verificado contra `pg_indexes` el
    2026-09-02), así que no barre la tabla.
    """
    if tabla not in TABLAS_ACOTADAS:
        raise ValueError(
            f"tabla no acotada por la ventana: {tabla!r}. Las únicas son "
            f"{', '.join(TABLAS_ACOTADAS)}, y este nombre se interpola en el "
            f"SQL: no puede venir de fuera."
        )
    return (
        f"DELETE FROM stg.{tabla} "
        f"WHERE obra_id = ANY (ARRAY[{_lista_de_obras(obras)}]::BIGINT[]);"
    )


def componer_sql_presupuesto(sql_texto: str, obras: Sequence[int]) -> str:
    """`06_presupuesto.sql` acotado a las obras vivas (DA-2, R6, T11b).

    De **una sola pasada**, sin tramos: este fichero no tiene ventanas ni
    explosión de filas, así que su pico de temporales es proporcional al volumen
    filtrado y no hace falta trocearlo.

    El marcador aparece **una sola vez** —su `WHERE` es uno solo, a diferencia
    de las dos ramas de `08_plan_mensual.sql`— y se comprueba antes de enviar
    nada: si alguien lo borra al editar el fichero, esto falla aquí en vez de
    reconstruir las 920 obras en un servidor sin créditos de CPU.
    """
    apariciones = sql_texto.count(MARCADOR_FILTRO_PRESUPUESTO)
    if apariciones != FILTROS_EN_PRESUPUESTO:
        raise ValueError(
            f"El SQL de presupuesto debe contener el marcador "
            f"{MARCADOR_FILTRO_PRESUPUESTO} exactamente {FILTROS_EN_PRESUPUESTO} "
            f"vez y aparece {apariciones}. Sin la sustitución se ejecutaría sin "
            f"filtrar, reconstruyendo las 920 obras: no se ejecuta."
        )

    lista = _lista_de_obras(obras)
    filtrado = sql_texto.replace(
        MARCADOR_FILTRO_PRESUPUESTO, f"ARRAY[{lista}]::BIGINT[]"
    )
    return componer_borrado_derivado("presupuesto", obras) + "\n" + filtrado


def sello_vigente_del_repositorio(settings) -> str:
    """`sha256` del SQL del build y de sus parámetros (R17).

    Es **función de módulo y no método** a propósito: la necesitan el step, el
    comando `ventana-plan` y el guardián `check-ventana`, y los dos últimos no
    tienen por qué instanciar un step —que abre cliente y arrastra estado— solo
    para leer dos ficheros y hacer un hash. Además, así el guardián sigue
    funcionando en los tests que sustituyen `BuildStgStep` por un doble.
    """
    textos = [
        (DIRECTORIO_SQL_STG / nombre).read_text(encoding="utf-8")
        for nombre in FICHEROS_DEL_SELLO
    ]
    return sello_sql(
        textos,
        {
            "cod_version_master_vigente": settings.business_rules["sigrid"][
                "campos_extendidos"
            ]["cod_version_master_vigente"],
        },
    )


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
    # Sub-paso que compone el plan de la ventana (F-025). No ejecuta SQL de
    # construcción: decide qué obras entran en los dos que vienen detrás.
    es_plan_ventana: bool = False
    # Sub-paso acotado a las obras del plan, de una sola pasada (F-025, DA-2).
    acotado: bool = False


class BuildStgStep(PipelineStep):
    """Construye el esquema stg desde raw."""

    def __init__(
        self,
        settings: Settings,
        batch_id: str | None = None,
        omitir_puerta: bool = False,
        reconstruir_todo: bool = False,
    ) -> None:
        self._settings = settings
        self._batch_id = batch_id
        self._omitir_puerta = omitir_puerta
        # F-025: fuerza la reconstrucción completa esta noche, se mire el
        # calendario o no. Lo enciende `--reconstruir-todo` y lo enciende solo
        # el domingo (R25).
        self._reconstruir_todo = reconstruir_todo
        # El plan de la noche, compuesto por el sub-paso `plan_ventana` y leído
        # por los dos sub-pasos acotados que vienen detrás.
        self._plan: Plan | None = None
        # Firma del origen de esta noche por obra, para registrarla al
        # reconstruir. Sale del censo, que ya la trae.
        self._firmas: dict[int, str | None] = {}
        self._codigos: dict[int, str] = {}

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
            # F-025. Va AQUÍ y no antes por una razón concreta: la regla de
            # actividad se mide sobre `stg.fases`, y componer el plan antes de
            # `05_fases.sql` lo calcularía con las fases de anoche. Y va antes
            # de `06_presupuesto.sql`, que es el primer sub-paso acotado.
            #
            # Tiene su propia fila en `_meta.etl_runs`, como la puerta de
            # F-024: aparece en `timings` con su duración y deja constancia
            # escrita de qué se decidió esa noche.
            _SubStep("plan_ventana", "", es_plan_ventana=True),
            _SubStep(
                "build_presupuesto", "06_presupuesto.sql", "stg", "presupuesto",
                acotado=True,
            ),
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
                if sub.es_plan_ventana:
                    self._componer_plan(pg)
                elif sub.por_tramos:
                    self._build_plan_mensual_por_tramos(pg, sql_path)
                elif sub.acotado:
                    self._build_presupuesto_acotado(pg, sql_path)
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

        # F-025, R25. El hito de la reconstrucción completa se escribe AQUÍ, y
        # solo aquí: cuando la noche completa ha terminado bien de principio a
        # fin. Registrarlo antes —al decidir que tocaba— dejaría las 880 obras
        # congeladas una semana más creyendo que ya se habían puesto al día,
        # que es exactamente el silencio que esta feature elimina.
        self._registrar_hito_de_completa(pg)

        # F-025, T14. El VACUUM va al final del step y FUERA de la lista de
        # sub-pasos: es higiene, no construcción, y su fallo no puede tumbar la
        # noche. Ver `_higiene_de_las_tablas_acotadas`.
        self._higiene_de_las_tablas_acotadas(pg)

        result.status = StepStatus.SUCCESS
        result.rows_processed = total_rows
        result.finished_at = datetime.utcnow()
        result.metadata = {
            "table_stats": table_stats,
            # De qué carga de raw salió este stg. Es lo que permite, tres días
            # después, saber si el cuadro que no cuadra viene de aquí.
            "raw_batch_id": veredicto.batch_id,
            # F-025, R30. Sin estos dos números no se puede medir el ahorro, y
            # medir el ahorro es el criterio por el que existe esta feature.
            "obras_reconstruidas": len(self._plan.reconstruir) if self._plan else 0,
            "obras_congeladas": len(self._plan.congelar) if self._plan else 0,
            "reconstruccion_completa": bool(self._plan and self._plan.completa),
        }
        return result

    # ---------------------------------------------------------------------
    # La ventana de negocio (F-025)
    # ---------------------------------------------------------------------

    def _componer_plan(self, pg: PostgresClient) -> None:
        """Decide qué obras se reconstruyen esta noche y lo deja escrito (R1).

        Tres cosas se resuelven aquí y ninguna en el dominio, que no sabe de
        BBDD ni de reloj:

        1. **El sello del SQL vigente** (R17), leyendo los ficheros del disco.
        2. **Si toca reconstrucción completa** (R25), mirando el registro. El
           `--reconstruir-todo` del humano manda por encima del calendario.
        3. **El censo**, que es la única consulta.

        Con la ventana APAGADA (`PG_VENTANA_ACTIVA=false`, el default de R5) el
        plan es «todas las obras»: el contenido publicado es exactamente el de
        hoy. Lo que no vuelve es el `TRUNCATE`, porque borrar y reescribir
        todas las obras deja el mismo resultado y además sobrevive a un tramo
        que falle.
        """
        opciones = self._settings.postgres
        censo = pg.fetch_censo_de_obras()

        self._firmas = {o.obra_id: o.firma_origen for o in censo}
        self._codigos = {o.obra_id: o.codigo_obra for o in censo}

        sello = self._sello_vigente()
        completa, motivo_completa = self._toca_completa(pg)

        if not opciones.ventana_activa:
            # R5: mientras la ventana esté apagada, se reconstruye todo. Se
            # marca como `completa` para que el registro diga la verdad sobre
            # por qué entró cada obra, y para que el hito quede escrito.
            completa = True
            motivo_completa = "la ventana esta desactivada (PG_VENTANA_ACTIVA=false)"

        plan = clasificar_obras(
            censo,
            criterio_desde_reglas(
                self._settings.business_rules, opciones.ventana_meses
            ),
            datetime.utcnow().date(),
            sello,
            completa=completa,
            rescate=opciones.ventana_rescate,
        )
        self._plan = plan

        logger.info(
            "ventana_plan",
            ventana_activa=opciones.ventana_activa,
            completa=completa,
            motivo_completa=motivo_completa,
            obras_a_reconstruir=len(plan.reconstruir),
            obras_congeladas=len(plan.congelar),
            por_motivo=plan.por_motivo,
            denunciadas=[d.codigo_obra for d in plan.denunciadas],
            sello=sello[:8],
        )

        # Las obras congeladas cuyo origen ha cambiado se NOMBRAN aquí mismo,
        # además de en el guardián: la denuncia no puede depender de que
        # alguien despliegue una regla de alerta (§3.1, R26).
        for decision in plan.denunciadas:
            logger.warning(
                "ventana_obra_congelada_con_origen_cambiado",
                obra_id=decision.obra_id,
                codigo_obra=decision.codigo_obra,
                motivo=decision.detalle,
            )

        # El motivo de cada obra congelada se escribe AHORA y no al final: si
        # el build muere a mitad, queda constancia de qué se decidió. No se
        # tocan `construido_at` ni `filas`, que siguen siendo los de su última
        # construcción buena.
        pg.marcar_obras_congeladas(
            [
                {
                    "obra_id": d.obra_id,
                    "codigo_obra": d.codigo_obra,
                    "motivo": d.motivo,
                    "detalle": d.detalle,
                }
                for d in plan.congelar
            ]
        )

    def _sello_vigente(self) -> str:
        """`sha256` del SQL del build y de sus parámetros (R17)."""
        return sello_vigente_del_repositorio(self._settings)

    def _toca_completa(self, pg: PostgresClient) -> tuple[bool, str]:
        """Si esta noche toca rehacerlo todo, y por qué (R25, DA-4)."""
        if self._reconstruir_todo:
            return True, "--reconstruir-todo"

        return toca_reconstruccion_completa(
            pg.fetch_ultima_reconstruccion_completa(PASO_RECONSTRUCCION_COMPLETA),
            datetime.utcnow(),
            self._settings.postgres.ventana_dia_completa,
        )

    def _obras_a_reconstruir(self) -> tuple[int, ...]:
        """Las obras del plan. Sin plan, ninguna: el sub-paso no toca la tabla.

        Que esto devuelva una tupla vacía en vez de reventar es lo que hace
        posible R9, y que no devuelva «todas» es deliberado: ante la duda, no
        se escribe.
        """
        return self._plan.obras_a_reconstruir if self._plan else ()

    def _registrar_construidas(
        self, pg: PostgresClient, obras: Sequence[int], tabla: str
    ) -> None:
        """Anota en `_meta.obra_build` de qué ejecución viene cada obra (R14).

        Va en llamada aparte y no dentro del SQL del tramo porque
        `execute_sql_text` devuelve el `rowcount` de la ÚLTIMA sentencia, y
        meter aquí el upsert convertiría «filas insertadas» en «obras
        registradas». Si el proceso muere entre el tramo y su registro, la obra
        queda construida y sin registrar, y la noche siguiente entra por R18:
        se reconstruye de más, que es el lado correcto en el que fallar.
        """
        if not self._plan or not obras:
            return

        por_obra = {d.obra_id: d for d in self._plan.reconstruir}
        filas = pg.fetch_filas_por_obra(tabla, obras)
        ahora = datetime.utcnow()

        pg.registrar_obras_construidas(
            [
                {
                    "obra_id": obra_id,
                    "codigo_obra": self._codigos.get(obra_id, ""),
                    # La firma que tenía el origen CUANDO se construyó, que es
                    # lo que hace que la comparación de mañana signifique algo.
                    "firma_origen": self._firmas.get(obra_id),
                    "sello_sql": self._plan.sello_vigente,
                    "batch_id": self._batch_id,
                    "construido_at": ahora,
                    "filas": filas.get(obra_id, 0),
                    "motivo": por_obra[obra_id].motivo,
                    "detalle": por_obra[obra_id].detalle,
                }
                for obra_id in obras
                if obra_id in por_obra
            ]
        )

    def _registrar_hito_de_completa(self, pg: PostgresClient) -> None:
        """Deja constancia de que esta noche se reconstruyó TODO (R25).

        Solo si el plan era completo y el step ha llegado hasta aquí, que es lo
        que significa «terminó bien». De esta fila sale la respuesta a «¿cuánto
        hace que no se rehace todo?», y de ahí el «hasta 6 días» de R3.
        """
        if not (self._plan and self._plan.completa):
            return

        ahora = datetime.utcnow()
        pg.record_run_completed(
            stage="stage",
            step=PASO_RECONSTRUCCION_COMPLETA,
            started_at=ahora,
            finished_at=ahora,
            status=StepStatus.SUCCESS.value,
            rows_processed=len(self._plan.reconstruir),
            metadata={"motivo": MOTIVO_COMPLETA, "obras": len(self._plan.reconstruir)},
            batch_id=self._batch_id,
        )
        logger.info(
            "ventana_reconstruccion_completa_registrada",
            obras=len(self._plan.reconstruir),
        )

    def _higiene_de_las_tablas_acotadas(self, pg: PostgresClient) -> None:
        """`VACUUM (ANALYZE)` de las dos tablas acotadas (T14, §9.1).

        **Avisa y no tumba.** El borrado derivado deja tuplas muertas cada
        noche en un `B1ms` sin créditos, donde el autovacuum llega tarde; pero
        el `VACUUM` es higiene, no producto, y tumbar el step por él dejaría al
        negocio sin datamart una noche entera por no haber podido limpiar
        tuplas muertas.

        Si esto falla de forma sostenida, lo que hay que mirar es el bloat
        (T33) y, si crece, el particionado (§2c). El aviso queda en el log
        para que se pueda ver.
        """
        for tabla in TABLAS_ACOTADAS:
            try:
                pg.vacuum_analyze("stg", tabla)
            except Exception as error:
                logger.warning(
                    "vacuum_fallido",
                    tabla=f"stg.{tabla}",
                    error=str(error),
                    nota=(
                        "el VACUUM es higiene, no producto: la noche sigue. "
                        "Si se repite, mirar el bloat (T33 de F-025)."
                    ),
                )

    def _build_presupuesto_acotado(
        self, pg: PostgresClient, sql_path: Path
    ) -> int:
        """`stg.presupuesto` solo para las obras vivas (DA-2, R6, R9, R10).

        De **una sola pasada**: este fichero no tiene ventanas ni explosión de
        filas, así que su pico de temporales es proporcional al volumen
        filtrado y no necesita los tramos de `08_plan_mensual.sql`.

        Si el conjunto queda vacío **no se ejecuta nada y no se toca la tabla**
        (R9). Un `DELETE` con una lista vacía no borraría nada, pero componerlo
        significaría que el planificador está roto y prefiero que se note.
        """
        obras = self._obras_a_reconstruir()
        if not obras:
            logger.info(
                "presupuesto_sin_obras_que_reconstruir",
                nota="ninguna obra entra esta noche: la tabla no se toca (R9)",
            )
            return 0

        filas = pg.execute_sql_text(
            componer_sql_presupuesto(
                sql_path.read_text(encoding="utf-8"), list(obras)
            )
        )
        logger.info("presupuesto_acotado", obras=len(obras), filas=filas)

        if self._plan and self._plan.completa:
            self._limpiar_obras_sobrantes(pg, "presupuesto", obras)

        self._registrar_construidas(pg, obras, "presupuesto")
        return filas

    def _limpiar_obras_sobrantes(
        self, pg: PostgresClient, tabla: str, obras: Sequence[int]
    ) -> None:
        """Borra las obras que tienen filas y **ya no están en el origen**.

        Es la contrapartida de haber quitado el `TRUNCATE`, y se cubre a
        propósito en vez de aceptarse en silencio: el borrado derivado solo
        alcanza a las obras que se van a reescribir, así que una obra que
        desaparezca de Sigrid conservaría sus filas para siempre.

        **Solo en la reconstrucción completa**, que es la única noche en la que
        el conjunto a reconstruir es el universo entero y por tanto lo que no
        está en él sobra de verdad. En una noche acotada, «no está en el
        conjunto» significa «está congelada», que es lo contrario.

        Lo normal es que no borre nada: es una red, no un paso del pipeline.
        """
        vivas = set(obras)
        sobrantes = sorted(pg.fetch_obras_con_filas(tabla) - vivas)
        if not sobrantes:
            return

        pg.execute_sql_text(componer_borrado_derivado(tabla, sobrantes))
        logger.warning(
            "ventana_obras_sobrantes_borradas",
            tabla=f"stg.{tabla}",
            obras=sobrantes,
            nota=(
                "tenian filas construidas y ya no estan en el origen: se "
                "borran en la reconstruccion completa, que es la unica noche "
                "en la que 'no esta en el conjunto' significa 'ya no existe'"
            ),
        )

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

        1. **Pesos por obra**, **acotados a las obras del plan** (F-025), y
           **plan de tramos** (dominio puro). Las obras que no caben ni solas
           se avisan; no abortan (es el mínimo físico).
        2. **Por cada tramo**: puerta de disco → `DELETE` de sus obras +
           `INSERT` en la MISMA transacción → registro en `_meta.obra_build` y
           en `_meta.etl_runs`.
        3. **Ante límite superado, medición imposible o tramo fallido**: se
           para y se propaga, **sin vaciar nada**. Ni ese tramo ni los
           siguientes.

        **El vaciado inicial ha desaparecido (F-025, R10, R13), y es el cambio
        de fondo de esta feature.** Antes se lanzaba un `TRUNCATE` global antes
        del primer tramo, y con la ventana encendida eso habría borrado las 920
        obras para reescribir 40. Ahora cada tramo borra **exactamente** las
        obras que va a reinsertar, en su misma transacción.

        Eso cambia también la invariante del aborto. La de F-019 era «al
        abortar, la tabla queda VACÍA», porque una tabla a medias era
        indistinguible de una completa. Ya no aplica: lo que queda tras un
        fallo no es media tabla, son **obras enteras con su última versión
        buena**, y vaciarlas destruiría lo congelado, que es justo lo que el
        humano prohibió. Quien vigila que `build_mart` no construya sobre un
        stage a medias es la puerta de F-024, que no se toca.
        """
        max_filas = self._settings.postgres.tramo_max_filas
        total_gb = self._settings.postgres.disco_total_gb
        limite_pct = self._settings.postgres.disco_limite_pct

        obras_del_plan = set(self._obras_a_reconstruir())
        if not obras_del_plan:
            # R9: sin obras que reconstruir el sub-paso termina en SUCCESS sin
            # ejecutar tramos y **sin tocar la tabla**.
            logger.info(
                "plan_mensual_sin_obras_que_reconstruir",
                nota="ninguna obra entra esta noche: la tabla no se toca (R9)",
            )
            return 0

        sql_plantilla = sql_path.read_text(encoding="utf-8")
        pesos_por_obra = {
            obra_id: peso
            for obra_id, peso in pg.fetch_pesos_plan_mensual().items()
            if obra_id in obras_del_plan
        }
        tramos = planificar_tramos(pesos_por_obra, max_filas)

        for tramo in tramos_sobredimensionados(tramos, max_filas):
            logger.warning(
                "plan_mensual_tramo_sobredimensionado",
                tramo=tramo.indice,
                obras=list(tramo.obras),
                peso=tramo.peso,
                max_filas=max_filas,
            )

        if self._plan and self._plan.completa:
            self._limpiar_obras_sobrantes(
                pg, "plan_mensual", sorted(pesos_por_obra)
            )

        logger.info(
            "plan_mensual_plan_de_tramos",
            tramos=len(tramos),
            obras=len(pesos_por_obra),
            peso_total=sum(pesos_por_obra.values()),
            max_filas=max_filas,
        )

        total = len(tramos)
        filas_totales = 0
        # Las obras que ya han quedado reconstruidas. Es lo que permite decir,
        # cuando un tramo falla, QUÉ obras se han quedado con el dato de anoche
        # (R13) en vez de solo que la noche falló.
        hechas: list[int] = []

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
                self._abortar_plan_mensual(motivo, hechas, pesos_por_obra)

            if ocupacion_pct > limite_pct:
                motivo = (
                    f"ocupación del disco {ocupacion_pct} % por encima del "
                    f"límite {limite_pct} % antes del tramo {etiqueta}: el "
                    f"servidor es compartido y el build para aquí."
                )
                pg.record_run_end(run_id, "FAILED", error_message=motivo)
                self._abortar_plan_mensual(motivo, hechas, pesos_por_obra)

            # --- El tramo, en su propia transacción (R11) ---
            try:
                filas = pg.execute_sql_text(
                    componer_sql_tramo(sql_plantilla, tramo.obras)
                )
            except Exception as error:
                motivo = f"falló el tramo {etiqueta}: {error}"
                pg.record_run_end(run_id, "FAILED", error_message=motivo)
                self._abortar_plan_mensual(motivo, hechas, pesos_por_obra)

            filas_totales += filas
            hechas.extend(tramo.obras)
            # El registro va DESPUÉS del tramo confirmado y antes del
            # siguiente: si la noche muere aquí, lo hecho está anotado y lo que
            # falta se reconstruye mañana.
            self._registrar_construidas(pg, tramo.obras, "plan_mensual")

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

    def _abortar_plan_mensual(
        self,
        motivo: str,
        hechas: Sequence[int],
        del_plan: Iterable[int],
    ) -> None:
        """Para el build **sin vaciar nada** y propaga. Nunca vuelve (R13).

        **Ya no trunca**, y ese es el cambio de invariante de F-025. El aborto
        de F-019 hacía `TRUNCATE` + FAILED porque una tabla a medias era
        indistinguible de una completa; con el borrado derivado lo que queda no
        es media tabla, son obras enteras con su última versión buena, y
        vaciarlas destruiría lo congelado.

        Es, además, la reparación de la avería del 2026-09-02: aquella noche
        habría terminado con cinco obras al día y el resto con el dato de
        anoche —coherente— en vez de con `stg.plan_mensual` al 21,6 %
        —truncada—.

        Se registra **qué obras se han quedado sin reconstruir**, que es lo que
        R13 exige y lo que convierte «la noche falló» en «estas obras llevan el
        dato de ayer».
        """
        pendientes = sorted(set(del_plan) - set(hechas))
        logger.error(
            "plan_mensual_abortado",
            motivo=motivo,
            obras_reconstruidas=len(hechas),
            obras_sin_reconstruir=pendientes,
            nota=(
                "la tabla NO se vacia: cada obra conserva su ultima version "
                "buena. Quien impide que build_mart construya sobre un stage a "
                "medias es la puerta de F-024."
            ),
        )
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
