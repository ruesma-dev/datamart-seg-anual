# main.py
"""
CLI del ETL. Comandos:

    python main.py version            - Versión del ETL e imagen en ejecución
    python main.py check-api          - Smoke test conectividad sigrid-api
    python main.py check-pg           - Smoke test conectividad Postgres
    python main.py bootstrap          - Crear schemas y tabla _meta.etl_runs
    python main.py ingest             - Ingesta Sigrid → raw (incremental)
    python main.py ingest --full      - Ingesta Sigrid → raw (full refresh)
    python main.py ingest --table T   - Ingesta solo la tabla T
    python main.py load-aux           - (pendiente) carga Excels → aux
    python main.py stage              - (pendiente) raw → stg
    python main.py build-mart         - (pendiente) stg → mart
    python main.py run-all            - Pipeline completo
    python main.py status             - Estado de tablas raw y últimos runs

Operación del datamart en Azure (F-005, ver docs/runbook_postgres_azure.md):

    python main.py apply-grants       - Reaplica los permisos del rol de lectura
                                        del MCP. `run-all` ya lo hace al final;
                                        a mano solo hace falta tras lanzar
                                        build-cierre, build-compras,
                                        build-maestros o build-retenciones
                                        sueltos: recrean vistas con DROP +
                                        CREATE y un DROP se lleva los GRANT
    python main.py timings            - Tiempos por paso de _meta.etl_runs
    python main.py fingerprint-views  - Huella de las vistas de consumo a CSV
    python main.py compare-fingerprints LOCAL AZURE
                                      - Compara dos huellas; sale != 0 si hay fallo

Coherencia y frescura (F-024). Los dos son de SOLO LECTURA:

    python main.py check-coherencia   - ¿De qué carga viene cada tabla de raw?
                                        ¿Se puede construir stg y mart encima?
                                        Sale 0 si sí, 1 si no, 2 si no puede leer
    python main.py check-frescura     - ¿Cuánto hace que no hay un build_mart
                                        completo? Sale 0 solo si está FRESCO
    python main.py check-declarados   - ¿Existe en la base todo lo que el SQL
                                        del repositorio declara crear? (F-047)
                                        Corre solo al final de run-all

Un cierre por mes en los ámbitos reales (F-042). Los tres son de SOLO LECTURA:

    python main.py check-cierres      - ¿Publica `stg.plan_mensual` UN cierre
                                        por mes, y el que la regla elige?
                                        Contrasta contra `domain/cierres.py`,
                                        que recompone los candidatos desde
                                        `stg.presupuesto` y no desde la tabla
                                        que audita. Sale != 0 si discrepan
    python main.py huella-obras       - Huella de obra x ambito x mes a CSV,
                                        fuera de la base. Con --propuesta
                                        reejecuta la rama de reales YA
                                        MODIFICADA como SELECT, SIN materializar
    python main.py comparar-huellas ANTES DESPUES --obras-esperadas ...
                                      - Las dos listas completas de lo que
                                        cambia. Sale != 0 si se mueve una obra
                                        que no debia, o algo en los ambitos 8/11

Medición del coste de la carga (F-011). Los tres son de SOLO LECTURA y ninguno
escribe en _meta; el «medir antes de optimizar» de esa feature vive aquí:

    python main.py perfil-carga       - ¿Dónde se va el tiempo? Desglose por
                                        paso y por tabla, techo de mejora y las
                                        tablas que acumulan el 80 % de la ingesta
    python main.py diagnostico-tiemod - ¿Sirve `tiemod` como watermark? Estado
                                        de _source_tiemod por tabla; con
                                        --comparar-con, veredicto SIRVE /
                                        NO SIRVE / SIN EVIDENCIA entre dos cargas
    python main.py bench-sigrid       - ¿Cuánto rinde cada tamaño de página
                                        contra sigrid-api? Lee de producción:
                                        se lanza a mano y en el momento elegido
"""

from __future__ import annotations

import platform
import sys
from datetime import datetime
from pathlib import Path

# Permite ejecutar `python main.py` desde la raíz del proyecto sin instalar el paquete
sys.path.insert(0, str(Path(__file__).resolve().parent))

import click  # noqa: E402

from config.settings import get_build_info, get_settings  # noqa: E402
from etl_sigrid.application.orchestrator import Orchestrator  # noqa: E402
from etl_sigrid.application.steps.apply_grants_step import ApplyGrantsStep
from etl_sigrid.application.steps.publicar_diccionario_step import (
    PublicarDiccionarioStep,
)  # noqa: E402
from etl_sigrid.application.steps.build_cierre_step import BuildCierreStep  # noqa: E402
from etl_sigrid.application.steps.build_compras_step import BuildComprasStep  # noqa: E402
from etl_sigrid.application.steps.build_maestros_step import BuildMaestrosStep  # noqa: E402
from etl_sigrid.application.steps.build_retenciones_step import BuildRetencionesStep  # noqa: E402
from etl_sigrid.application.steps.build_mart_step import BuildMartStep  # noqa: E402
from etl_sigrid.application.steps.build_stg_step import BuildStgStep  # noqa: E402
from etl_sigrid.application.steps.ingest_raw_step import IngestRawStep  # noqa: E402
from etl_sigrid.application.steps.load_excel_aux_step import LoadExcelAuxStep  # noqa: E402
from etl_sigrid.domain.coherencia import (  # noqa: E402
    evaluar_coherencia_raw,
    evaluar_coherencia_stg,
    formatear_veredicto_stg,
)
from etl_sigrid.domain.ejecucion import Ejecucion, nueva_ejecucion  # noqa: E402
from etl_sigrid.domain.entities import StepResult, StepStatus  # noqa: E402
from etl_sigrid.domain.extraccion import (  # noqa: E402
    comparar_cap,
    format_bench,
    resumen_bench,
)
from etl_sigrid.domain.perfil_carga import (  # noqa: E402
    format_perfil,
    perfil_de_carga,
)
from etl_sigrid.domain.tiemod import (  # noqa: E402
    comparar_tiemod,
    escribir_csv_tiemod,
    format_comparacion,
    format_diagnostico,
    leer_csv_tiemod,
)
from etl_sigrid.infrastructure.logging_config import configure_logging, get_logger  # noqa: E402
from etl_sigrid.infrastructure.postgres.conninfo import (  # noqa: E402
    make_admin_conninfo_provider,
    make_conninfo_provider,
)
from etl_sigrid.infrastructure.postgres.fingerprint import (  # noqa: E402
    comparar,
    construir_huella,
    escribir_csv,
    leer_csv,
    mes_a_fecha,
    veredicto,
)
from etl_sigrid.infrastructure.postgres.frescura import (  # noqa: E402
    UMBRAL_FRESCURA_HORAS,
    VEREDICTO_FRESCO,
    format_estado_raw,
    format_frescura,
)
from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient  # noqa: E402
from etl_sigrid.infrastructure.postgres.step_run_recorder import (  # noqa: E402
    PostgresStepRunRecorder,
)
from etl_sigrid.infrastructure.postgres.timings import format_timings  # noqa: E402
from etl_sigrid.infrastructure.sigrid.bench_extraccion import (  # noqa: E402
    barrer_paginas,
    escribir_csv_bench,
)
from etl_sigrid.infrastructure.sigrid.sigrid_api_client import SigridApiClient  # noqa: E402

#: Cap de filas por petición que documenta `azure-apps/sigrid_api.md`. El real
#: son 20.000 (DA-6, dato del humano el 2026-08-18): la divergencia se avisa,
#: pero **este proyecto no edita aquel documento**, que es de `sigrid-api`.
CAP_DOCUMENTADO_SIGRID_API = 1_000


@click.group()
@click.pass_context
def cli(ctx: click.Context) -> None:
    """ETL Sigrid → Postgres → Power BI (data mart seguimiento mensual)."""
    # 'version' se salta la configuración a propósito: get_settings() aborta si
    # faltan SIGRID_API_BASE_URL o SIGRID_API_FUNCTION_KEY, y este comando es
    # justo el que se usa para diagnosticar un contenedor mal configurado.
    if ctx.invoked_subcommand == "version":
        return
    settings = get_settings()
    configure_logging(level=settings.logging.log_level, fmt=settings.logging.log_format)


def _get_pg() -> PostgresClient:
    """
    Construye el cliente Postgres con auto-bootstrap perezoso.

    La cadena de conexión se pasa como proveedor callable, no como cadena: con
    PG_AUTH_MODE=entra el token caduca y hay que resolverlo en cada conexión.
    """
    pg = get_settings().postgres
    return PostgresClient(
        conninfo=make_conninfo_provider(pg),
        admin_conninfo=make_admin_conninfo_provider(pg),
        target_db=pg.db,
        auto_create_db=pg.auto_create_db,
        set_role=pg.set_role,
    )


# ---------------------------------------------------------------------------
# Coherencia ante cargas truncadas (F-024)
#
# `_arrancar_ejecucion` y `_ejecutar_paso` son la ÚNICA puerta de entrada de
# los comandos que escriben. Que estén aquí, y no repetidos en cada comando,
# es lo que hace comprobable la lista de «quién escribe y quién no»: el test
# parametrizado de R4/R5 la recorre entera.
# ---------------------------------------------------------------------------


def _arrancar_ejecucion(pg: PostgresClient) -> Ejecucion:
    """Abre una ejecución y cierra las filas que dejó abiertas un proceso muerto.

    Se llama UNA vez por proceso, antes de construir ningún step. Toda fila
    `RUNNING` que exista al arrancar es de otro proceso por definición: las
    nuestras todavía no existen.

    Un fallo marcando NO tumba la carga (R7): esto es contabilidad, y el paso
    que venga detrás fallará por sí mismo si la BBDD no está. Abortar aquí
    convertiría un problema de permisos sobre `_meta` en una noche sin datos.
    """
    ejecucion = nueva_ejecucion()
    logger = get_logger("ejecucion")

    try:
        huerfanas = pg.abortar_runs_huerfanos(ejecucion.batch_id)
    except Exception as e:  # contabilidad: no puede parar la carga
        logger.warning(
            "huerfanas_no_marcadas", batch_id=ejecucion.batch_id, error=str(e)
        )
        return ejecucion

    for run_id, step, started_at in huerfanas:
        logger.warning(
            "etl_run_huerfana_abortada",
            id=run_id,
            step=step,
            started_at=str(started_at),
            batch_id=ejecucion.batch_id,
        )

    return ejecucion


def _ejecutar_paso(step, pg: PostgresClient, ejecucion: Ejecucion) -> StepResult:
    """Ejecuta un step suelto, lo registra en `_meta.etl_runs` y sale 1 si falló.

    El registro va DESPUÉS de ejecutar y ANTES de salir (R18): un paso que
    falla es justo cuando más falta hace que quede escrito. Y un fallo del
    propio registro no cambia el código de salida, mismo criterio que el
    grabador del orquestador.
    """
    resultado = step.run()

    try:
        PostgresStepRunRecorder(pg, ejecucion.batch_id).record(step.stage, resultado)
    except Exception as e:  # medir nunca rompe el pipeline
        get_logger("ejecucion").warning(
            "step_run_no_registrado", step=resultado.step_name, error=str(e)
        )

    _print_result(resultado)
    if resultado.status == StepStatus.FAILED:
        sys.exit(1)
    return resultado


@cli.command("version")
def version() -> None:
    """
    Imprime la versión del ETL y los metadatos de la imagen en ejecución.

    Es el primer comando a lanzar cuando algo va mal en Azure: dice qué build
    está corriendo realmente. No lee .env ni toca red ni BBDD, así que
    funciona incluso con la configuración rota.
    """
    info = get_build_info()
    click.echo(f"etl-sigrid-seguimiento {info['version']}")
    click.echo(f"image: {info['image_tag']}")
    click.echo(f"build: {info['build_date']}")
    click.echo(f"python: {platform.python_version()}")


@cli.command("check-api")
def check_api() -> None:
    """Smoke test: verifica conectividad con sigrid-api."""
    logger = get_logger("check-api")
    settings = get_settings()
    with SigridApiClient(
        base_url=settings.sigrid_api.base_url,
        function_key=settings.sigrid_api.function_key.get_secret_value(),
        database=settings.sigrid_api.database,
        page_size=settings.sigrid_api.page_size,
        timeout_s=settings.sigrid_api.timeout_s,
        max_retries=1,
    ) as api:
        try:
            r = api.check_connectivity()
            click.secho(
                f"✓ sigrid-api OK. database={settings.sigrid_api.database} "
                f"row_count={r['row_count']}",
                fg="green",
            )
        except Exception as e:
            logger.error("check_api_failed", error=str(e))
            click.secho(f"✗ sigrid-api FAIL: {e}", fg="red", err=True)
            sys.exit(2)


@cli.command("check-pg")
def check_pg() -> None:
    """Smoke test: verifica conectividad con Postgres. Crea la BBDD si no existe."""
    pg = _get_pg()
    try:
        version = pg.check_connectivity()
        click.secho(f"✓ Postgres OK. {version}", fg="green")
    except Exception as e:
        click.secho(f"✗ Postgres FAIL: {e}", fg="red", err=True)
        sys.exit(2)


@cli.command("bootstrap")
def bootstrap() -> None:
    """
    Fuerza el bootstrap (BBDD + schemas + _meta.etl_runs). Es idempotente.
    Normalmente NO hace falta llamarlo: el bootstrap se ejecuta automáticamente
    la primera vez que cualquier comando toca Postgres.
    """
    pg = _get_pg()
    pg.force_bootstrap()
    click.secho("✓ BBDD, schemas y _meta.etl_runs listos (idempotente)", fg="green")


@cli.command("ingest")
@click.option(
    "--table", "table", default=None, help="Solo ingesta esta tabla concreta (ej. obrparpre)"
)
@click.option(
    "--full",
    "full_refresh",
    is_flag=True,
    default=False,
    help="Full refresh: TRUNCATE antes de cargar (no incremental)",
)
@click.option(
    "--stop-on-error",
    is_flag=True,
    default=False,
    help="Aborta el step si una tabla falla. Por defecto continua con las demás.",
)
def ingest(table: str | None, full_refresh: bool, stop_on_error: bool) -> None:
    """Ingesta Sigrid → raw.* (incremental por defecto)."""
    settings = get_settings()
    pg = _get_pg()
    ejecucion = _arrancar_ejecucion(pg)
    _ejecutar_paso(
        IngestRawStep(
            settings,
            only_table=table,
            full_refresh=full_refresh,
            stop_on_error=stop_on_error,
            batch_id=ejecucion.batch_id,
        ),
        pg,
        ejecucion,
    )


@cli.command("load-aux")
def load_aux() -> None:
    """Carga Excels auxiliares → aux.* (pendiente)."""
    settings = get_settings()
    pg = _get_pg()
    ejecucion = _arrancar_ejecucion(pg)
    _ejecutar_paso(LoadExcelAuxStep(settings), pg, ejecucion)


@cli.command("stage")
@click.option(
    "--sin-puerta",
    "sin_puerta",
    is_flag=True,
    default=False,
    help="Construye aunque la puerta de coherencia de raw diga KO. El "
         "veredicto se evalúa y se registra igual, como SKIPPED. NO existe "
         "en run-all.",
)
def stage(sin_puerta: bool) -> None:
    """Materializa stg.* desde raw.* (tipado, derivaciones, sin lógica de negocio).

    Antes de tocar nada comprueba que TODAS las tablas de raw declaradas en
    tables_sigrid.yaml provienen de la misma ejecución terminada en SUCCESS.
    Si no, se niega y dice por qué (`python main.py check-coherencia` da el
    detalle). Con --sin-puerta construye igualmente, y queda escrito.
    """
    settings = get_settings()
    pg = _get_pg()
    ejecucion = _arrancar_ejecucion(pg)
    _ejecutar_paso(
        BuildStgStep(
            settings, batch_id=ejecucion.batch_id, omitir_puerta=sin_puerta
        ),
        pg,
        ejecucion,
    )


@cli.command("build-mart")
@click.option(
    "--sin-puerta",
    "sin_puerta",
    is_flag=True,
    default=False,
    help="Construye aunque el último stage no llegara a terminar. El "
         "veredicto se evalúa y se registra igual, como SKIPPED.",
)
def build_mart(sin_puerta: bool) -> None:
    """
    Materializa mart.fact_seguimiento_mensual desde stg.plan_mensual.

    Produce una fila por (obra × partida × mes × escenario), con cuatro
    escenarios: Coste Real, Venta Real, Coste Planificado, Venta Planificada.

    Para los escenarios planificados, escoge automáticamente la versión del
    master vigente en cada mes (la más reciente con fec_creacion ≤ mes).

    Exige que el último `build_stg` terminara: un stage muerto a medias deja
    stg mezclado (unas tablas de esta noche y otras de ayer) y construir mart
    encima da cuadros que no cuadran sin que nadie se entere.
    """
    settings = get_settings()
    pg = _get_pg()
    ejecucion = _arrancar_ejecucion(pg)
    _ejecutar_paso(
        BuildMartStep(
            settings, batch_id=ejecucion.batch_id, omitir_puerta=sin_puerta
        ),
        pg,
        ejecucion,
    )


def build_pipeline_steps(
    settings,
    full_refresh: bool = False,
    batch_id: str | None = None,
    pg: PostgresClient | None = None,
) -> list:
    """
    Composición del pipeline de `run-all`.

    Está fuera del comando para poder comprobar en un test que `apply_grants`
    forma parte del pipeline y va después de `build_mart`: si algún día alguien
    lo quita, el MCP se queda sin permisos la noche siguiente y nadie se entera
    hasta que alguien pregunta algo.

    `batch_id` (F-024) viaja a los pasos que escriben filas propias en
    `_meta.etl_runs` —la ingesta, por tabla; el stage, por sub-paso y tramo—
    para que TODAS las filas de la noche compartan identidad. Ninguno de los
    dos steps del pipeline recibe `omitir_puerta`: `run-all` no tiene vía de
    escape a propósito.

    F-047 (que absorbe F-044) mete aquí los CUATRO build que se lanzaban a
    mano. El orden dentro de la lista es legible, pero lo que lo GARANTIZA es
    el `depends_on` de cada paso, que es lo que obedece el orden topológico.
    """
    pasos = [
        IngestRawStep(settings, full_refresh=full_refresh, batch_id=batch_id),
        LoadExcelAuxStep(settings),
        BuildStgStep(settings, batch_id=batch_id),
        BuildMartStep(settings, batch_id=batch_id),
        # F-047: los cuatro esquemas que se construían a mano y podían estar
        # arbitrariamente desfasados respecto a `raw` y `stg`. `maestro`,
        # `compras` y `retenciones` solo leen de `raw`; `cierre` lee de `stg` y
        # va DESPUÉS de `build_mart` porque `mart/03_agg_categoria.sql` dropea
        # con CASCADE la tabla de la que cuelga `cierre.v_pbi_planif_vs_real`.
        # Eso lo declara `BuildCierreStep.depends_on`, no esta posición.
        BuildMaestrosStep(settings),
        BuildComprasStep(settings),
        BuildRetencionesStep(settings),
        BuildCierreStep(settings),
        # F-006: entre build_mart y apply_grants, y el orden NO es cosmético.
        # `apply_grants` concede SELECT ON ALL TABLES IN SCHEMA _meta, que es
        # una foto del instante en que corre: publicar después dejaría las tres
        # tablas del diccionario dependiendo solo del ALTER DEFAULT PRIVILEGES.
        # `pg` se pasa cuando el llamante ya tiene cliente abierto: publicar
        # reusa esa conexión en vez de abrir una segunda contra el mismo
        # servidor, que es compartido.
        PublicarDiccionarioStep(
            settings, pasos_nocturnos=(), batch_id=batch_id, client=pg
        ),
        ApplyGrantsStep(settings),
    ]

    # La lista de pasos nocturnos se inyecta DESPUÉS de componer, y no antes,
    # porque es la composición la que la define. Es lo que evita que el
    # validador de frescura (R14) dependa de una copia escrita a mano: el día
    # que `build-cierre` entre en `run-all`, su veredicto cambia solo.
    for paso in pasos:
        if isinstance(paso, PublicarDiccionarioStep):
            paso.pasos_nocturnos = [p.name for p in pasos]
    return pasos


@cli.command("run-all")
@click.option("--full", "full_refresh", is_flag=True, default=False)
def run_all(full_refresh: bool) -> None:
    """
    Ejecuta el pipeline completo: ingest → load_aux → stage → build_mart →
    los cuatro build (maestros, compras, retenciones, cierre) →
    publicar_diccionario → apply_grants.

    Los cuatro esquemas que antes se construían a mano entraron aquí con F-047:
    se quedaban desfasados semanas y, en el caso de `cierre`, la nocturna
    llegaba a DESTRUIR una de sus vistas sin recrearla.

    Al terminar contrasta el SQL del repositorio contra el catálogo real
    (`check-declarados`): si un build no ha creado lo que el repositorio
    declara, `run-all` sale con código 1 en vez de terminar en verde mintiendo.
    """
    settings = get_settings()
    pg = _get_pg()
    ejecucion = _arrancar_ejecucion(pg)
    steps = build_pipeline_steps(
        settings, full_refresh, batch_id=ejecucion.batch_id, pg=pg
    )
    # El grabador deja una fila por paso en _meta.etl_runs: es lo que después
    # leen `python main.py timings` y la vista _meta.v_frescura. Si falla, el
    # orquestador solo lo loguea.
    orchestrator = Orchestrator(
        steps, recorder=PostgresStepRunRecorder(pg, ejecucion.batch_id)
    )
    results = orchestrator.run_all()

    click.echo("")
    click.secho("=== RESUMEN ===", fg="cyan", bold=True)
    for r in results:
        _print_result(r)

    # F-047, EL GUARDIÁN. Va DESPUÉS de todo y no es un step: es una lectura, no
    # una construcción, y meterlo en el DAG lo convertiría en dependencia de
    # `apply_grants` o al revés. La noche del incidente terminó en verde
    # habiendo DESTRUIDO `cierre.v_pbi_planif_vs_real`; con esto, una noche que
    # no deje construido lo que el repositorio declara sale con código 1.
    click.echo("")
    guardian_ok = _guardian_de_lo_declarado(pg)

    # F-052, EL OTRO GUARDIAN. Avisa y NO bloquea (DA-4): su veredicto NO entra
    # en el codigo de salida a proposito. La contrapartida esta declarada y es
    # cara: al terminar la noche en verde, la alerta de fallo existente no se
    # dispara, asi que la regla de infra/96_create_alert_cobertura.ps1 es la
    # UNICA via por la que este hallazgo llega a una persona.
    click.echo("")
    _guardian_de_cobertura(pg)

    failed = sum(1 for r in results if r.status == StepStatus.FAILED)
    if failed or not guardian_ok:
        sys.exit(1)


def _guardian_de_lo_declarado(pg: PostgresClient) -> bool:
    """Contrasta `sql/**` contra el catálogo real e imprime el veredicto.

    Devuelve si está limpio. Un fallo LEYENDO el catálogo no se traga: se
    imprime y cuenta como veredicto negativo. Callarlo dejaría exactamente el
    agujero que esta feature cierra —una noche que termina en verde sin haber
    comprobado nada—, y es el mismo criterio que el `assert` de inventario no
    vacío de la puerta offline.
    """
    from etl_sigrid.domain.diccionario import ESQUEMAS_DEL_DATAMART
    from etl_sigrid.infrastructure.inventario_repositorio import (
        cargar_pendientes_construccion,
        inventario_del_repositorio,
    )
    from etl_sigrid.infrastructure.postgres.catalogo import (
        evaluar_construccion,
        formatear_construccion,
    )

    try:
        informe = evaluar_construccion(
            inventario_del_repositorio(),
            pg.list_objetos_catalogo(list(ESQUEMAS_DEL_DATAMART)),
            cargar_pendientes_construccion(),
        )
    except Exception as e:  # noqa: BLE001
        click.secho(
            f"KO   no se pudo comprobar lo declarado contra la base: {e}",
            fg="red", err=True,
        )
        return False

    click.echo(formatear_construccion(informe))
    return informe.ok


@cli.command("fingerprint-views")
@click.option(
    "--out",
    "salida",
    type=click.Path(dir_okay=False, path_type=Path),
    required=True,
    help="Fichero CSV donde escribir la huella.",
)
@click.option(
    "--periodo-hasta",
    "periodo_hasta",
    type=str,
    default=None,
    help="Último mes CERRADO, AAAA-MM. Activa el bloque de comparación exacta.",
)
@click.option(
    "--schemas",
    "schemas",
    type=str,
    default=None,
    help="Esquemas a fotografiar, separados por comas. Por defecto, "
         "PG_CONSUMPTION_SCHEMAS.",
)
def fingerprint_views(salida: Path, periodo_hasta: str | None, schemas: str | None) -> None:
    """
    Escribe la huella de las vistas de consumo: estructura, agregados de los
    meses cerrados y agregados del periodo vivo.

    Se ejecuta una vez contra el Postgres local y otra contra Azure, con el
    MISMO commit del repositorio a los dos lados, y luego se comparan con
    `compare-fingerprints`.
    """
    settings = get_settings()
    lista = (
        [s.strip() for s in schemas.split(",") if s.strip()]
        if schemas
        else settings.postgres.consumption_schema_list
    )
    hasta = mes_a_fecha(periodo_hasta) if periodo_hasta else None
    if hasta is None:
        click.secho(
            "AVISO: sin --periodo-hasta no se genera el bloque de meses cerrados, "
            "que es el único con criterio de igualdad exacta.",
            fg="yellow",
        )

    metricas = construir_huella(_get_pg(), lista, hasta)
    escribir_csv(metricas, salida)

    vistas = len({(m.esquema, m.vista) for m in metricas})
    click.secho(
        f"✓ Huella escrita en {salida}: {vistas} vistas, {len(metricas)} métricas.",
        fg="green",
    )


@cli.command("compare-fingerprints")
@click.argument("huella_a", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("huella_b", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def compare_fingerprints(huella_a: Path, huella_b: Path) -> None:
    """
    Compara dos huellas (típicamente local y Azure) y emite el veredicto.

    Estructura y meses cerrados se exigen idénticos; las diferencias del
    periodo vivo se informan como avisos, porque Sigrid sigue cambiando entre
    las dos capturas. Sale con código distinto de 0 si hay algún FALLO.
    """
    diferencias = comparar(leer_csv(huella_a), leer_csv(huella_b))
    codigo, informe = veredicto(diferencias)
    click.echo(informe)
    if codigo:
        sys.exit(codigo)


@cli.command("timings")
@click.option(
    "--last",
    "last",
    type=int,
    default=1,
    help="Cuántas ejecuciones del pipeline mostrar (por defecto la última).",
)
def timings(last: int) -> None:
    """
    Tiempos por paso de las últimas ejecuciones, leídos de _meta.etl_runs.

    Es la entrada del veredicto sobre el SKU del servidor: si build_mart o
    build_cierre se disparan, el dato está aquí y no en una impresión.

    Es de SOLO LECTURA (F-024, DA-7): si ve filas RUNNING demasiado antiguas
    avisa al pie, pero no las marca. Contra Azure, un comando de diagnóstico
    no escribe en la tabla que está diagnosticando.
    """
    pg = _get_pg()
    click.echo(format_timings(pg.fetch_timings(last=last), ahora=datetime.utcnow()))


@cli.command("apply-grants")
def apply_grants() -> None:
    """
    Reaplica los permisos de lectura del rol del MCP (PG_READONLY_ROLE).

    `run-all` ya lo ejecuta como último paso de la noche. A mano hace falta
    tras lanzar `build-cierre`, `build-compras`, `build-maestros` o
    `build-retenciones` SUELTOS: esos comandos recrean vistas con DROP +
    CREATE y un DROP se lleva los GRANT concedidos.
    """
    settings = get_settings()
    pg = _get_pg()
    ejecucion = _arrancar_ejecucion(pg)
    _ejecutar_paso(ApplyGrantsStep(settings), pg, ejecucion)


@cli.command("check-diccionario")
def check_diccionario_cmd() -> None:
    """
    Contrasta el diccionario contra el catalogo REAL de Postgres (R28).

    La puerta que corre en cada `init.sh` es offline y heuristica: deduce lo que
    el repositorio publica leyendo `sql/**`. No puede ver que la BASE vaya por
    detras del repositorio, ni que tenga algo que el repositorio ya no crea.
    Esto si.

    Comprueba TODOS los objetos fichados, en las tres direcciones: publicado sin
    ficha, fichado que no existe, y tipo que no casa. El recuento lo imprime el
    propio comando, que lo cuenta; escribirlo aqui solo servia para que caducara
    —decia 102 y ya eran 103—. Y avisa si lo PUBLICADO en
    `_meta` ya no es lo del arbol.

    Sale con codigo 1 si hay discrepancias.
    """
    import pathlib as _pathlib

    from etl_sigrid.application.steps.publicar_diccionario_step import DIR_DICCIONARIO
    from etl_sigrid.domain.diccionario import ESQUEMAS_DEL_DATAMART
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario
    from etl_sigrid.infrastructure.postgres.catalogo import comparar, formatear

    dicc, hash_arbol = cargar_diccionario(DIR_DICCIONARIO)
    pg = _get_pg()

    catalogo = pg.list_objetos_catalogo(list(ESQUEMAS_DEL_DATAMART))
    informe = comparar(dicc, catalogo)
    click.echo(formatear(informe))
    click.echo("")

    publicado = pg.fetch_hash_publicado()
    desfasado = False
    if publicado is None:
        click.echo("!    no hay nada publicado en `_meta.diccionario_publicacion`")
        desfasado = True
    else:
        version, hash_pub = publicado
        if hash_pub == hash_arbol:
            click.echo(
                f"OK   lo publicado ES lo del arbol (version {version}, "
                f"hash {hash_pub[:12]})"
            )
        else:
            desfasado = True
            click.echo(
                f"KO   LO PUBLICADO NO ES LO DEL ARBOL. `_meta` sirve el hash "
                f"{hash_pub[:12]} (version {version}) y los YAML dan "
                f"{hash_arbol[:12]}. Alguien edito una ficha y no republico, asi "
                f"que el MCP esta leyendo una version anterior. Se arregla con "
                f"`python main.py publicar-diccionario`, subiendo `version` si el "
                f"cambio hay que comunicarlo."
            )

    if not informe.ok or desfasado:
        raise SystemExit(1)


@cli.command("check-declarados")
def check_declarados_cmd() -> None:
    """
    Contrasta lo que el SQL del repositorio DECLARA contra la base (F-047).

    Es la pregunta que no hacia nadie, y por ese hueco se colo F-047. Las otras
    dos puertas miran otra cosa: la de `init.sh` compara el SQL contra las
    FICHAS, y `check-diccionario` compara las FICHAS contra la base. Ninguna
    responde «lo que `sql/**` dice que crea, ¿existe de verdad?».

    Recorre los `CREATE [OR REPLACE] TABLE|VIEW|FUNCTION` de
    `etl_sigrid/infrastructure/postgres/sql/**` mas las tablas de `raw` que
    declara `config/tables_sigrid.yaml`, y comprueba contra `information_schema`
    que cada objeto existe y con su tipo.

    Un objeto que legitimamente aun no toca construir --el cierre no esta
    terminado: F-017 y F-018-- se declara en `config/objetos_pendientes.yaml`.
    Es un trinquete y solo baja: un pendiente ya construido, o uno que el
    repositorio no declara, rompen la puerta.

    Corre solo al final de `run-all`. Sale con codigo 1 si hay discrepancias.
    """
    from etl_sigrid.domain.diccionario import ESQUEMAS_DEL_DATAMART
    from etl_sigrid.infrastructure.inventario_repositorio import (
        cargar_pendientes_construccion,
        inventario_del_repositorio,
    )
    from etl_sigrid.infrastructure.postgres.catalogo import (
        evaluar_construccion,
        formatear_construccion,
    )

    pg = _get_pg()
    informe = evaluar_construccion(
        inventario_del_repositorio(),
        pg.list_objetos_catalogo(list(ESQUEMAS_DEL_DATAMART)),
        cargar_pendientes_construccion(),
    )
    click.echo(formatear_construccion(informe))

    if not informe.ok:
        raise SystemExit(1)


@cli.command("check-unicidad")
@click.option(
    "--todos",
    is_flag=True,
    default=False,
    help="Comprueba TODO objeto con clave, no solo la superficie de consumo.",
)
@click.option(
    "--timeout",
    default=30,
    show_default=True,
    help="Segundos por consulta (SET LOCAL statement_timeout).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Imprime las consultas y NO abre conexion.",
)
def check_unicidad_cmd(todos: bool, timeout: int, dry_run: bool) -> None:
    """
    Comprueba contra la base que cada `clave_negocio` declarada identifica UNA fila.

    Es la mitad del problema que la puerta offline no puede cubrir: sabe si la
    clave nombra columnas de mas, pero no si es demasiado CORTA. Y esa mitad se
    propaga, porque la deteccion de fan-out deriva la unicidad de la clave
    declarada: una clave reducida ademas desarma esa comprobacion.

    Por defecto solo la superficie de consumo, que es donde una clave corta
    produce un numero falso en una respuesta. `--todos` hace la pasada completa;
    piensalo antes, porque `stg.plan_mensual` ronda los 29 millones de filas y
    esto corre contra un servidor compartido con `albaranes` y `partes` EN
    PRODUCCION. Cada consulta lleva su `statement_timeout` y la transaccion va
    `READ ONLY`.

    OJO CON EL VERDE: que no haya duplicados no prueba que la clave sea
    correcta. Prueba que los datos de HOY no la contradicen.
    """
    from etl_sigrid.application.steps.publicar_diccionario_step import DIR_DICCIONARIO
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario
    from etl_sigrid.infrastructure.postgres.unicidad_sql import (
        consultas_de_unicidad,
        interpretar_resultado,
        objetos_saltados,
        veredicto_no_comprobado,
        veredicto_no_existe,
    )

    dicc, _hash = cargar_diccionario(DIR_DICCIONARIO)
    consultas = consultas_de_unicidad(dicc, solo_consumo=not todos)
    saltados = objetos_saltados(dicc, solo_consumo=not todos)

    alcance = "TODO objeto con clave" if todos else "solo la superficie de consumo"
    click.echo(f"Comprobacion de unicidad · {alcance}")
    click.echo(f"  {len(consultas)} objeto(s) a comprobar, {len(saltados)} saltado(s)")
    click.echo(f"  statement_timeout = {timeout}s por consulta, transaccion READ ONLY")
    click.echo("")

    if dry_run:
        for c in consultas:
            click.echo(f"-- {c.objeto}  clave: ({', '.join(c.clave)})")
            click.echo(c.sql + ";")
            click.echo("")
        click.echo(f"-- {len(consultas)} consulta(s). No se ha abierto ninguna conexion.")
        return

    pg = _get_pg()
    fallos = 0
    sin_comprobar = 0
    inexistentes = 0
    for c in consultas:
        resultado = pg.comprobar_unicidad(c, timeout)
        if resultado == "NO_EXISTE":
            inexistentes += 1
            click.echo(veredicto_no_existe(c))
            continue
        if resultado is None:
            sin_comprobar += 1
            click.echo(veredicto_no_comprobado(c, f"timeout de {timeout}s"))
            continue
        duplicadas, filas = resultado
        if duplicadas:
            fallos += 1
        click.echo(interpretar_resultado(c, duplicadas, filas))

    click.echo("")
    click.echo(
        f"Resumen: {len(consultas) - fallos - sin_comprobar - inexistentes} sin "
        f"contradiccion, {fallos} con la clave rota, {sin_comprobar} sin "
        f"comprobar, {inexistentes} fichados que no existen en la base."
    )
    click.echo(
        "Un objeto sin contradiccion NO tiene la clave demostrada: los datos de "
        "hoy no la contradicen, que es otra cosa."
    )
    if fallos or sin_comprobar or inexistentes:
        raise SystemExit(1)


@cli.command("check-relaciones")
@click.option(
    "--todos",
    is_flag=True,
    default=False,
    help="Comprueba TODA relacion declarada, no solo la superficie de consumo.",
)
@click.option(
    "--timeout",
    default=30,
    show_default=True,
    help="Segundos por consulta (SET LOCAL statement_timeout).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Imprime las consultas y NO abre conexion.",
)
def check_relaciones_cmd(todos: bool, timeout: int, dry_run: bool) -> None:
    """
    Comprueba contra la base que cada relacion declarada UNE de verdad (T40).

    Nace de un defecto medido: `retenciones.movimientos.obra_id ->
    maestro.obras.obra_id` casaba **0 de 261** valores porque `obra_id` es ahi
    el `ide` del CENTRO DE COSTE, no el de la obra. Un INNER JOIN por esa
    relacion devuelve cero filas y un LEFT JOIN devuelve todo a NULL, **en
    silencio**. El validador offline no podia verlo: la relacion resolvia
    perfectamente contra el diccionario, y lo que fallaba estaba en los datos.

    Muestrea 500 valores distintos del lado izquierdo y mira cuantos existen en
    el derecho. **Cero casos sale KO**; una cobertura por debajo del 50 % avisa,
    porque un hueco puede ser legitimo (`cierre` solo cubre 583 de 918 obras).

    Como `check-unicidad`: cada consulta lleva su `statement_timeout`, la
    transaccion va `READ ONLY`, y esto corre contra un servidor compartido con
    `albaranes` y `partes` EN PRODUCCION.

    OJO CON EL VERDE: que una relacion una no prueba que sea la correcta.
    Prueba que une.
    """
    from etl_sigrid.application.steps.publicar_diccionario_step import DIR_DICCIONARIO
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario
    from etl_sigrid.infrastructure.postgres.relaciones_sql import (
        consultas_de_relaciones,
        interpretar_relacion,
        relaciones_saltadas,
        veredicto_relacion_no_comprobada,
        veredicto_relacion_no_existe,
    )

    dicc, _hash = cargar_diccionario(DIR_DICCIONARIO)
    consultas = consultas_de_relaciones(dicc, solo_consumo=not todos)
    saltadas = relaciones_saltadas(dicc, solo_consumo=not todos)

    alcance = "TODA relacion declarada" if todos else "solo la superficie de consumo"
    click.echo(f"Comprobacion de relaciones · {alcance}")
    click.echo(
        f"  {len(consultas)} relacion(es) a comprobar, {len(saltadas)} saltada(s)"
    )
    click.echo(f"  statement_timeout = {timeout}s por consulta, transaccion READ ONLY")
    click.echo("")

    if dry_run:
        for c in consultas:
            click.echo(f"-- {c.nombre} -> {c.a}  [{c.cardinalidad}]")
            click.echo(c.sql + ";")
            click.echo("")
        click.echo(f"-- {len(consultas)} consulta(s). No se ha abierto ninguna conexion.")
        return

    pg = _get_pg()
    fallos = 0
    avisos = 0
    sin_comprobar = 0
    inexistentes = 0
    for c in consultas:
        resultado = pg.comprobar_relacion(c, timeout)
        if resultado == "NO_EXISTE":
            inexistentes += 1
            click.echo(veredicto_relacion_no_existe(c))
            continue
        if resultado is None:
            sin_comprobar += 1
            click.echo(veredicto_relacion_no_comprobada(c, f"timeout de {timeout}s"))
            continue
        muestreados, casan = resultado
        veredicto = interpretar_relacion(c, muestreados, casan)
        if veredicto.startswith("KO"):
            fallos += 1
        elif veredicto.startswith("AVISO"):
            avisos += 1
        elif veredicto.startswith("?"):
            sin_comprobar += 1
        click.echo(veredicto)

    for nombre, motivo in saltadas:
        click.echo(f"-    {nombre}: saltada, {motivo}")

    correctas = len(consultas) - fallos - avisos - sin_comprobar - inexistentes
    click.echo("")
    click.echo(
        f"Resumen: {correctas} que unen, {avisos} con cobertura escasa, {fallos} "
        f"que NO unen, {sin_comprobar} sin comprobar, {inexistentes} con un "
        f"extremo que no existe en la base."
    )
    click.echo(
        "Una relacion que une NO esta demostrada: podria unir por la columna "
        "equivocada y coincidir. Prueba que une, que es otra cosa."
    )
    if fallos or sin_comprobar or inexistentes:
        raise SystemExit(1)


@cli.command("check-cierres")
@click.option(
    "--obras",
    "obras",
    type=str,
    default=None,
    help="obra_id separados por comas. Sin esto, todas las obras.",
)
@click.option(
    "--timeout",
    default=300,
    show_default=True,
    help="Segundos por consulta (SET LOCAL statement_timeout).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Imprime las consultas y NO abre conexion.",
)
def check_cierres_cmd(obras: str | None, timeout: int, dry_run: bool) -> None:
    """
    Contrasta `stg.plan_mensual` contra la regla «un cierre por mes» (F-042).

    Obra a obra y ambito a ambito, comprueba tres cosas: que cada mes de los
    ambitos reales publique UN solo cierre, que sea el que la regla elige —el
    mas moderno con acumulado distinto de cero— y que el telescopio
    `SUM(importe_mes) = ultimo importe_origen` se siga cumpliendo.

    Lo que le da valor es que los dos lados son INDEPENDIENTES: los candidatos
    se recomponen desde `stg.presupuesto` y `stg.fases`, que es de donde sale
    `reales_base`, y la decision la toma `domain/cierres.py`, no el SQL que se
    esta auditando. Una discrepancia significa que uno de los dos esta mal.

    SOLO LECTURA: transaccion `READ ONLY` y `statement_timeout` por consulta.
    Sale distinto de 0 si hay cualquier discrepancia, nombrando obra, ambito,
    mes y las fases de los dos lados.
    """
    from etl_sigrid.domain.cierres import agrupar, contrastar
    from etl_sigrid.infrastructure.postgres.cierres_sql import (
        formatear_discrepancias,
        sql_cierres_candidatos,
        sql_cierres_publicados,
        sql_telescopio,
        sql_telescopio_detalle,
    )

    lista = (
        [int(o.strip()) for o in obras.split(",") if o.strip()] if obras else None
    )
    consultas = {
        "candidatos (stg.presupuesto ⨝ stg.fases)": sql_cierres_candidatos(lista),
        "publicado (stg.plan_mensual)": sql_cierres_publicados(lista),
        "telescopio (R16)": sql_telescopio(lista),
    }

    alcance = f"{len(lista)} obra(s)" if lista else "todas las obras"
    click.echo(f"Contraste de cierres · {alcance}, ambitos reales 3 y 7")
    click.echo(f"  statement_timeout = {timeout}s por consulta, transaccion READ ONLY")
    click.echo("")

    if dry_run:
        for nombre, texto in consultas.items():
            click.echo(f"-- {nombre}")
            click.echo(texto + ";")
            click.echo("")
        click.echo("-- 3 consulta(s). No se ha abierto ninguna conexion.")
        return

    pg = _get_pg()
    candidatos = agrupar(pg.filas_solo_lectura(sql_cierres_candidatos(lista), timeout))
    publicados = agrupar(pg.filas_solo_lectura(sql_cierres_publicados(lista), timeout))
    discrepancias = contrastar(candidatos, publicados)

    click.echo(
        f"{sum(len(c) for c in candidatos.values())} cierre(s) candidato(s) en "
        f"{len(candidatos)} par(es) obra/ambito; "
        f"{sum(len(p) for p in publicados.values())} publicado(s)."
    )
    click.echo(formatear_discrepancias(discrepancias))
    click.echo("")

    filas = pg.filas_solo_lectura(sql_telescopio(lista), timeout)
    comprobadas, rotas, con_hueco = (filas[0] if filas else (0, 0, 0))
    click.echo(
        f"Telescopio (R16): {comprobadas} serie(s) consecutiva(s) comprobada(s), "
        f"{rotas} sin cuadrar, {con_hueco} apartada(s) por tener un hueco de "
        f"origen que la regla NO creo (esas nunca telescopearon)."
    )
    if rotas:
        click.secho(
            "SUM(importe_mes) ha dejado de ser el ultimo importe_origen. Para ver "
            f"cuales:\n{sql_telescopio_detalle(lista)}",
            fg="red",
        )

    if discrepancias or rotas:
        raise SystemExit(1)


@cli.command("check-cobertura")
@click.option(
    "--timeout",
    default=300,
    show_default=True,
    help="Segundos por consulta (SET LOCAL statement_timeout).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Imprime las consultas y NO abre conexion.",
)
def check_cobertura_cmd(timeout: int, dry_run: bool) -> None:
    """
    Contrasta lo que entra en `stg` con lo que sale en `mart`, obra a obra (F-052).

    Es la pregunta que no hacia nadie, y por ese hueco la obra 0599 TANATORIO
    MAJADAHONDA llevaba desde 2022 publicando 4.066.989,23 EUR de venta y
    0,00 EUR de coste directo sin que nada chirriara. Las otras puertas miran
    otra cosa: `check-unicidad` mira claves duplicadas, `check-cierres` mira la
    regla de F-042 y `check-declarados` mira que exista lo que el SQL declara.

    Dos preguntas:

    
      * OBRA INVISIBLE  filas en stg.plan_mensual para un ambito y CERO en
                        mart.fact_seguimiento_mensual para ese mismo ambito.
      * FILAS HUERFANAS filas de stg.plan_mensual sin ficha de partida o de
                        obra, que los cuatro INNER JOIN del build borran hoy
                        sin decir nada.

    Los descartes que hoy son correctos se declaran en
    `config/cobertura_excepciones.yaml`, que es un trinquete y SOLO BAJA.

    LANZADO A MANO sale con codigo 1 si algo cae fuera de lo declarado, para
    servir de puerta en una verificacion manual. DENTRO DE `run-all` avisa y NO
    tumba el job (DA-4): registra el marcador y la nocturna termina en verde.

    Solo lectura: la transaccion va READ ONLY con su statement_timeout, porque
    esto corre contra un servidor compartido con `albaranes` y `partes` EN
    PRODUCCION. Las dos consultas barren stg.plan_mensual entera: piensalo antes
    de bajarle el timeout.
    """
    from etl_sigrid.domain.cobertura import formatear, veredicto
    from etl_sigrid.infrastructure.cobertura_excepciones import cargar_excepciones
    from etl_sigrid.infrastructure.postgres.cobertura_sql import (
        consultas_de_cobertura,
        filas_de_cobertura,
    )

    consultas = consultas_de_cobertura(timeout)
    click.echo("Cobertura stg -> mart · SOLO LECTURA, transaccion READ ONLY")
    click.echo(f"  statement_timeout = {timeout}s por consulta")
    click.echo("")

    if dry_run:
        for consulta in consultas:
            click.echo(f"-- {consulta.nombre}")
            click.echo(consulta.sql + ";")
            click.echo("")
        click.echo(
            f"-- {len(consultas)} consulta(s). No se ha abierto ninguna conexion."
        )
        return

    excepciones = cargar_excepciones()
    pg = _get_pg()
    por_nombre = {
        c.nombre: pg.filas_solo_lectura(c.sql, c.timeout_s) for c in consultas
    }
    filas = filas_de_cobertura(
        huerfanas=por_nombre["huerfanas"], invisibles=por_nombre["invisibles"]
    )
    resultado = veredicto(filas, excepciones)

    click.echo(f"{len(excepciones)} excepcion(es) declarada(s) y aceptada(s).")
    click.echo(formatear(resultado))

    if resultado.codigo:
        _emitir_marcador_de_cobertura(resultado)
        raise SystemExit(resultado.codigo)


def _emitir_marcador_de_cobertura(resultado) -> None:
    """Escribe la linea que dispara la alerta, por consola Y por el log (R28).

    Por las dos porque no se sabe cual de las dos mira la regla: en el job la
    salida de `click` y la del logger acaban las dos en
    `ContainerAppConsoleLogs_CL`, y una sola de ellas bastaria... hasta el dia
    que alguien cambie el formato del log a `json` o al reves. El literal es uno
    solo y vive en `domain/cobertura.py`; lo cruza tests/test_f052_marcador.py.
    """
    from etl_sigrid.domain.cobertura import MARCADOR_KO

    click.secho(resultado.marcador, fg="red")
    get_logger("check-cobertura").warning(
        "cobertura_ko",
        marcador=MARCADOR_KO,
        obras_invisibles=resultado.obras_invisibles_distintas,
        filas_huerfanas=resultado.total_huerfanas,
        linea=resultado.marcador,
    )


def _guardian_de_cobertura(pg: PostgresClient):
    """La cobertura al final de `run-all`. **Avisa y NO tumba el job** (DA-4).

    Devuelve el `Veredicto`, o `None` si no se pudo leer. `run-all` NO mira ese
    valor para decidir su codigo de salida, y es una decision consciente con su
    precio declarado: al terminar la noche en verde, la alerta de fallo existente
    (`alert-caj-datamart-seg-dev-failed`) no se dispara, asi que la regla de
    `infra/96_create_alert_cobertura.ps1` pasa a ser la UNICA via por la que este
    guardian se hace oir. **Si no se despliega, el guardian es mudo.**

    Un fallo LEYENDO la base tampoco escala, pero se imprime: callarlo dejaria
    una noche en verde sin haber comprobado nada.
    """
    from etl_sigrid.domain.cobertura import formatear, veredicto
    from etl_sigrid.infrastructure.cobertura_excepciones import cargar_excepciones
    from etl_sigrid.infrastructure.postgres.cobertura_sql import (
        consultas_de_cobertura,
        filas_de_cobertura,
    )

    try:
        por_nombre = {
            c.nombre: pg.filas_solo_lectura(c.sql, c.timeout_s)
            for c in consultas_de_cobertura()
        }
        resultado = veredicto(
            filas_de_cobertura(
                huerfanas=por_nombre["huerfanas"],
                invisibles=por_nombre["invisibles"],
            ),
            cargar_excepciones(),
        )
    except Exception as e:  # noqa: BLE001
        click.secho(
            f"?    no se pudo comprobar la cobertura stg -> mart: {e}. NO es un "
            f"OK: la nocturna sigue, pero esta noche nadie ha mirado si falta "
            f"una obra.",
            fg="yellow", err=True,
        )
        return None

    click.echo(formatear(resultado))
    if resultado.codigo:
        _emitir_marcador_de_cobertura(resultado)
    return resultado


@cli.command("huella-obras")
@click.option(
    "--out",
    "salida",
    type=click.Path(dir_okay=False, path_type=Path),
    required=True,
    help="CSV donde escribir la huella (fuera de la base).",
)
@click.option(
    "--desde",
    type=click.Choice(["stg", "mart"]),
    default="stg",
    show_default=True,
    help="`stg` agrega stg.plan_mensual; `mart`, fact_seguimiento_categoria.",
)
@click.option(
    "--propuesta",
    is_flag=True,
    default=False,
    help="Ejecuta la rama de reales YA MODIFICADA como SELECT, SIN materializar.",
)
@click.option(
    "--timeout",
    default=900,
    show_default=True,
    help="Segundos por consulta (SET LOCAL statement_timeout).",
)
def huella_obras_cmd(salida: Path, desde: str, propuesta: bool, timeout: int) -> None:
    """
    Huella de obra x ambito x mes a CSV, en SOLO LECTURA (F-042, R22).

    Es la mitad de la prueba que decide si esta feature se cierra: el humano
    pidio demostrar que «el mensual y el acumulado de las obras no afectadas no
    cambie», con el mismo `raw` y en los CUATRO ambitos (3, 7, 8 y 11).

    Con `--propuesta` NO se materializa nada: se reejecuta la rama de reales de
    `08_plan_mensual.sql` —el texto literal del fichero, recortado entre sus dos
    marcadores— como `SELECT` agregado. Los ambitos 8 y 11 se copian de la
    huella actual: su rama no se toca y hoy no tiene ni una clave duplicada.

    Va por tramos de obras con la puerta de disco de F-019 delante de cada uno,
    porque las ventanas derraman a temporales sobre un disco compartido con
    `albaranes` y `partes`. Ni una escritura: la transaccion va READ ONLY.

    ORDEN CRITICO: la huella del ANTES se saca antes de reconstruir nada. El
    build pisa `stg.plan_mensual` y no hay vuelta atras.
    """
    from etl_sigrid.application.steps.build_stg_step import DIRECTORIO_SQL_STG
    from etl_sigrid.infrastructure.postgres.huella_obras import (
        construir_huella,
        escribir_csv,
    )

    sql_plan_mensual = (
        (DIRECTORIO_SQL_STG / "08_plan_mensual.sql").read_text(encoding="utf-8")
        if propuesta
        else None
    )

    origen = f"{desde}{' (propuesta, sin materializar)' if propuesta else ''}"
    click.echo(f"Huella de obra x ambito x mes · desde {origen}")
    click.echo("  SOLO LECTURA: transaccion READ ONLY, ninguna escritura")

    filas = construir_huella(
        _get_pg(),
        get_settings(),
        desde=desde,
        propuesta=propuesta,
        sql_plan_mensual=sql_plan_mensual,
        timeout_s=timeout,
    )
    escribir_csv(filas, salida)

    ambitos = sorted({f.ambito_id for f in filas})
    obras = len({f.obra_id for f in filas})
    click.secho(
        f"✓ {len(filas)} celda(s) de {obras} obra(s) en los ambitos "
        f"{', '.join(map(str, ambitos))} escritas en {salida}.",
        fg="green",
    )
    if ambitos != [3, 7, 8, 11]:
        click.secho(
            "AVISO: la huella no trae los cuatro ambitos. `comparar-huellas` la "
            "rechazara, y con razon: probaria menos de lo que dice probar.",
            fg="yellow",
        )


@cli.command("comparar-huellas")
@click.argument("antes", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("despues", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--obras-esperadas",
    "obras_esperadas",
    type=str,
    default="",
    help="Codigos de obra que SI pueden cambiar, separados por comas.",
)
def comparar_huellas_cmd(antes: Path, despues: Path, obras_esperadas: str) -> None:
    """
    Compara dos huellas y dicta el veredicto (F-042, R23 a R25).

    Emite LAS DOS LISTAS COMPLETAS —no una muestra—: las obras cuya numeracion
    de fase cambia y las obras cuyos importes cambian, con ambito, mes y
    diferencia.

    Sale distinto de 0, y entonces la feature NO se cierra, si se mueve una obra
    fuera de `--obras-esperadas`, si se mueve algo en los ambitos master 8 u 11
    —que es el desbordamiento— o si las huellas no traen los cuatro ambitos.
    """
    from etl_sigrid.domain.huella import comparar_huellas, veredicto
    from etl_sigrid.infrastructure.postgres.huella_obras import leer_csv

    esperadas = [o.strip() for o in obras_esperadas.split(",") if o.strip()]
    comparacion = comparar_huellas(leer_csv(antes), leer_csv(despues))
    codigo, informe = veredicto(comparacion, esperadas)

    click.echo(f"ANTES:   {antes}")
    click.echo(f"DESPUES: {despues}")
    click.echo(
        f"Obras que SI pueden cambiar: {', '.join(esperadas) or 'ninguna declarada'}"
    )
    click.echo("")
    click.echo(informe)
    if codigo:
        raise SystemExit(codigo)


@cli.command("publicar-diccionario")
def publicar_diccionario_cmd() -> None:
    """
    Publica el diccionario semántico en `_meta` para que el MCP lo lea por SQL.

    Valida los YAML de `config/diccionario/`, comprueba que cubran todo lo que
    el repositorio publica y reemplaza el contenido de `_meta.diccionario`,
    `_meta.diccionario_reglas` y `_meta.diccionario_publicacion` en UNA
    transacción. Si algo no valida, no escribe nada: el diccionario anterior se
    queda publicado entero.

    Este comando y `run-all` son las DOS únicas vías de publicación (DA-1). Los
    builds manuales (`build-cierre`, `build-compras`, `build-maestros`,
    `build-retenciones`) NO republican: el diccionario no depende de los datos,
    y publicarlo cinco veces no añadiría nada salvo superficie de fallo.
    """
    settings = get_settings()
    pg = _get_pg()
    ejecucion = _arrancar_ejecucion(pg)
    # Los pasos nocturnos salen de la composición REAL del pipeline, no de una
    # lista escrita aquí: el comando suelto tiene que validar con el mismo
    # criterio que la noche, o un diccionario podría publicarse a mano y que
    # `run-all` lo rechazase después, que es peor que rechazarlo ya.
    nocturnos = [p.name for p in build_pipeline_steps(settings)]
    _ejecutar_paso(
        PublicarDiccionarioStep(
            settings,
            pasos_nocturnos=nocturnos,
            batch_id=ejecucion.batch_id,
            client=pg,
        ),
        pg,
        ejecucion,
    )


@cli.command("check-coherencia")
def check_coherencia() -> None:
    """
    ¿De qué carga viene cada tabla de raw, y se puede construir encima?

    SOLO LECTURA: no marca huérfanas ni registra nada. Es el comando que
    responde «¿por qué se negó a construir?» sin abrir una consola de psql.

    Códigos de salida: 0 si raw y stg son coherentes, 1 si alguno no lo es,
    2 si no se puede ni leer. El 2 se distingue del 1 a propósito: «el
    datamart es incoherente» y «no he podido comprobarlo» exigen cosas
    distintas de quien lo lea.
    """
    settings = get_settings()
    pg = _get_pg()

    try:
        estados = pg.fetch_estado_raw()
        ultimo_stg = pg.fetch_ultimo_intento_stg()
    except Exception as e:  # el código 2 es «no se pudo leer»
        click.secho(f"✗ No se pudo leer el estado de _meta: {e}", fg="red", err=True)
        sys.exit(2)

    requeridas = [t["source_table"] for t in settings.tables_sigrid.get("tables", [])]
    veredicto_raw = evaluar_coherencia_raw(estados, requeridas)
    veredicto_stg = evaluar_coherencia_stg(ultimo_stg)

    click.secho("=== Estado de raw por tabla ===", fg="cyan", bold=True)
    click.echo(format_estado_raw(estados, veredicto_raw))
    click.echo("")
    click.secho("=== Estado de stg ===", fg="cyan", bold=True)
    click.echo(formatear_veredicto_stg(veredicto_stg))

    if not veredicto_raw.ok or not veredicto_stg.ok:
        sys.exit(1)


@cli.command("check-frescura")
@click.option(
    "--umbral-horas",
    "umbral_horas",
    type=float,
    default=UMBRAL_FRESCURA_HORAS,
    show_default=True,
    help="Horas sin build correcto a partir de las cuales se considera "
         "caducado. El valor por defecto es el mismo que vigila la alerta de "
         "Azure (infra/env/dev.json: frescuraUmbralHoras).",
)
@click.option(
    "--paso",
    "paso",
    type=str,
    default="build_mart",
    show_default=True,
    help="Paso del pipeline sobre el que se emite el veredicto.",
)
def check_frescura(umbral_horas: float, paso: str) -> None:
    """
    ¿Cuánto hace que no hay un build completo? SOLO LECTURA.

    Imprime `_meta.v_frescura` entera —el diagnóstico de «mart está viejo»
    suele estar en la fila de `ingest_raw`— y emite el veredicto del paso
    pedido. Sale 0 solo si está FRESCO; 1 si CADUCADO o SIN BUILD REGISTRADO;
    2 si no puede leer.
    """
    pg = _get_pg()

    try:
        filas = pg.fetch_frescura()
    except Exception as e:  # el código 2 es «no se pudo leer»
        click.secho(f"✗ No se pudo leer _meta.v_frescura: {e}", fg="red", err=True)
        sys.exit(2)

    texto, veredicto = format_frescura(
        filas, umbral_horas=umbral_horas, paso=paso, ahora=datetime.utcnow()
    )
    click.echo(texto)

    if veredicto != VEREDICTO_FRESCO:
        sys.exit(1)


@cli.command("perfil-carga")
@click.option(
    "--batch",
    "batch_id",
    type=str,
    default=None,
    help="Identidad de ejecución a medir (batch_id). Por defecto, la última "
         "carga registrada en _meta.etl_runs.",
)
def perfil_carga(batch_id: str | None) -> None:
    """
    ¿Dónde se va el tiempo de la carga? SOLO LECTURA (F-011, R1–R3).

    Desglosa una carga completa en pasos de pipeline y en tablas de la ingesta,
    con duración, filas, filas/s y porcentaje del total; imprime el techo de
    mejora por paso (cuánto duraría la carga si ese paso costase cero) y cuántas
    tablas acumulan el 80 % del tiempo de extracción.

    Es el comando que decide si merece la pena una ingesta incremental, y lo
    hace con lo que ya está guardado: no ejecuta ninguna carga nueva ni escribe
    una fila en `_meta` (R25). Sale 2 si no puede leer, igual que
    `check-coherencia`.
    """
    pg = _get_pg()

    try:
        batch_medido, filas = pg.fetch_perfil_carga(batch_id)
    except Exception as e:  # el código 2 es «no se pudo leer»
        click.secho(f"✗ No se pudo leer _meta.etl_runs: {e}", fg="red", err=True)
        sys.exit(2)

    click.echo(format_perfil(perfil_de_carga(filas, batch_id=batch_medido)))


@cli.command("diagnostico-tiemod")
@click.option(
    "--out",
    "salida",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Fichero CSV donde escribir la fotografía. Es lo que después se pasa "
         "a --comparar-con tras la siguiente carga.",
)
@click.option(
    "--comparar-con",
    "anterior",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Fotografía de una carga anterior. Activa el veredicto por tabla.",
)
def diagnostico_tiemod(salida: Path | None, anterior: Path | None) -> None:
    """
    ¿Sirve `tiemod` como watermark? SOLO LECTURA sobre el datamart (R6, R7).

    Sin argumentos, fotografía `_source_tiemod` en cada tabla de `raw`: filas,
    nulos, mínimo, máximo, valores distintos y porcentaje de nulos. Con
    `--comparar-con`, contrasta esa fotografía con la de una carga anterior y
    emite el veredicto de R7 por tabla: `SIRVE`, `NO SIRVE` o `SIN EVIDENCIA`.

    No hace falta volver a leer Sigrid: los valores de su marca de modificación
    ya están dentro del datamart desde la primera carga. Lo que sí hace falta
    son DOS cargas, y por eso el veredicto sin `--comparar-con` no existe.

    Ojo con el coste: recorre cada tabla de `raw` entera (hay 20 M de filas).
    Es un comando de diagnóstico que se lanza a mano, nunca un paso del
    pipeline, y no escribe una sola fila en `_meta` (R25).
    """
    pg = _get_pg()

    # La fotografía anterior se lee UNA vez y antes de tocar la BBDD: un CSV
    # que no es una huella no puede confundirse con «no pude leer raw», que es
    # un problema completamente distinto.
    try:
        previos = [] if anterior is None else leer_csv_tiemod(anterior)
    except (OSError, ValueError) as e:
        click.secho(f"✗ No se pudo leer {anterior}: {e}", fg="red", err=True)
        sys.exit(2)

    try:
        estados = pg.fetch_diagnostico_tiemod()
        avanzadas = _filas_avanzadas(pg, estados, previos)
    except Exception as e:  # el código 2 es «no se pudo leer»
        click.secho(f"✗ No se pudo leer el estado de raw: {e}", fg="red", err=True)
        sys.exit(2)

    if anterior is None:
        click.echo(format_diagnostico(estados))
    else:
        click.echo(format_comparacion(comparar_tiemod(previos, estados, avanzadas)))

    if salida is not None:
        escribir_csv_tiemod(estados, salida)
        click.secho(f"✓ Fotografía escrita en {salida}", fg="green")


def _filas_avanzadas(
    pg: PostgresClient, estados: list, previos: list
) -> dict[str, int]:
    """Filas por tabla cuya marca supera el máximo de la fotografía anterior.

    Es una consulta más por tabla, y solo se lanza cuando hay con qué comparar:
    sin fotografía anterior no hay umbral, y contar «desde el principio» sería
    contar la tabla entera para nada. Una tabla que no estaba en la foto
    anterior —añadida al YAML entre dos cargas— tampoco tiene umbral.
    """
    anteriores = {e.tabla: e for e in previos}
    return {
        e.tabla: pg.fetch_filas_desde_tiemod(e.tabla, anteriores[e.tabla].maximo)
        for e in estados
        if e.tabla in anteriores and anteriores[e.tabla].maximo is not None
    }


@cli.command("bench-sigrid")
@click.option(
    "--tabla",
    "tabla",
    type=str,
    required=True,
    help="Tabla de Sigrid a medir (nombre en el origen, p. ej. obrparpre).",
)
@click.option(
    "--paginas",
    "paginas",
    type=str,
    default="1000,5000,10000,20000",
    show_default=True,
    help="Tamaños de página a barrer, separados por comas. El 20.000 es el cap "
         "real de sigrid-api (DA-6); hoy el ETL trabaja a 10.000.",
)
@click.option(
    "--repeticiones",
    "repeticiones",
    type=int,
    default=1,
    show_default=True,
    help="Páginas consecutivas por tamaño. Avanzan por keyset, no repiten la "
         "misma página: repetirla mediría la caché del SQL Server.",
)
@click.option(
    "--out",
    "salida",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Fichero CSV donde escribir las mediciones.",
)
def bench_sigrid(
    tabla: str, paginas: str, repeticiones: int, salida: Path | None
) -> None:
    """
    ¿Cuánto rinde cada tamaño de página contra sigrid-api? SOLO LECTURA (R4, R5).

    Mide la MISMA consulta que usa la ingesta (keyset por `ide`) con varios
    tamaños de página y responde dos preguntas que no están acreditadas: si
    subir de 10.000 a 20.000 compra tiempo o el coste está en el SQL Server
    (R4), y cuál es el corte real del balanceador —documentado 120 s, en uso
    230— comparando la latencia máxima observada con el timeout configurado
    (R5-bis).

    Si la API rechaza un tamaño, se anota su cap y el barrido continúa (R5).
    No abre conexión con Postgres ni escribe una fila en `_meta` (R25).
    """
    settings = get_settings()
    tamanos = [int(p) for p in paginas.split(",") if p.strip()]
    if not tamanos:
        click.secho("✗ --paginas no trae ningún tamaño.", fg="red", err=True)
        sys.exit(2)

    declarada = next(
        (
            t
            for t in settings.tables_sigrid.get("tables", [])
            if t["source_table"] == tabla
        ),
        None,
    )
    excluidas = set((declarada or {}).get("exclude_columns") or [])

    with SigridApiClient(
        base_url=settings.sigrid_api.base_url,
        function_key=settings.sigrid_api.function_key.get_secret_value(),
        database=settings.sigrid_api.database,
        page_size=settings.sigrid_api.page_size,
        timeout_s=settings.sigrid_api.timeout_s,
        max_retries=settings.sigrid_api.max_retries,
    ) as api:
        # Las mismas columnas que se lleva la ingesta: medir con todas incluiría
        # los blobs que el ETL nunca pide, y el número no serviría para nada.
        columnas = [
            c.name for c in api.fetch_table_schema(tabla) if c.name not in excluidas
        ]
        mediciones = barrer_paginas(
            api,
            tabla,
            columnas=columnas,
            tamanos=tamanos,
            repeticiones=repeticiones,
        )

    resumen = resumen_bench(mediciones)
    click.echo(format_bench(resumen, timeout_s=settings.sigrid_api.timeout_s))

    divergencia = comparar_cap(resumen.cap_medido, CAP_DOCUMENTADO_SIGRID_API)
    if divergencia is not None:
        click.secho(f"AVISO: {divergencia.mensaje}", fg="yellow")

    if salida is not None:
        escribir_csv_bench(mediciones, salida)
        click.secho(f"✓ Mediciones escritas en {salida}", fg="green")


@cli.command("status")
def status() -> None:
    """Muestra estado de tablas raw y últimos runs."""
    settings = get_settings()
    pg = _get_pg()
    tables = settings.tables_sigrid.get("tables", [])

    click.secho("=== Estado tablas raw ===", fg="cyan", bold=True)
    click.echo(f"{'tabla':<30} {'filas':>12} {'MAX(ide)':>12}")
    click.echo("-" * 56)
    for t in tables:
        name = t["target_table"]
        exists = pg.table_exists("raw", name)
        if not exists:
            click.echo(f"{'raw.' + name:<30} {'no creada':>12} {'-':>12}")
            continue
        rows = pg.count_rows("raw", name)
        max_id = pg.get_max_id("raw", name, t.get("id_column", "ide"))
        click.echo(f"{'raw.' + name:<30} {rows:>12,} {max_id:>12,}")


@cli.command("status-stg")
def status_stg() -> None:
    """Muestra el estado de las tablas y vistas del esquema stg."""
    pg = _get_pg()

    stg_tables = [
        "obras",
        "partidas",
        "fases",
        "presupuesto",
        "version_master_vigente",
        "plan_mensual",
    ]
    click.secho("=== Estado tablas stg ===", fg="cyan", bold=True)
    click.echo(f"{'tabla':<35} {'filas':>14}")
    click.echo("-" * 51)
    for t in stg_tables:
        if not pg.table_exists("stg", t):
            click.echo(f"{'stg.' + t:<35} {'no creada':>14}")
            continue
        click.echo(f"{'stg.' + t:<35} {pg.count_rows('stg', t):>14,}")

    # Vista stg.ambitos
    click.echo("")
    click.secho("=== Vista stg.ambitos (clasificación + uso) ===", fg="cyan", bold=True)
    try:
        with pg.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT ambito_id, codigo, descripcion, tipo, uso_seguimiento "
                "FROM stg.ambitos ORDER BY ambito_id"
            )
            rows = cur.fetchall()
        if not rows:
            click.secho("(vacía)", fg="yellow")
            return
        click.echo(
            f"{'id':>4}  {'codigo':<10} {'descripcion':<28} "
            f"{'tipo':<22} {'uso_seguimiento':<22}"
        )
        click.echo("-" * 92)
        for r in rows:
            ambito_id, codigo, descripcion, tipo, uso = r
            # Verde si tiene uso, gris si no
            color = "green" if uso else "white"
            uso_str = uso if uso else "—"
            click.secho(
                f"{ambito_id:>4}  {(codigo or ''):<10} "
                f"{(descripcion or '')[:28]:<28} "
                f"{tipo:<22} {uso_str:<22}",
                fg=color,
            )
    except Exception as e:
        click.secho(f"Vista stg.ambitos no disponible: {e}", fg="yellow")


@cli.command("view-auxobramb")
def view_auxobramb() -> None:
    """Muestra el contenido completo de raw.auxobramb (útil para verificar mapeo)."""
    pg = _get_pg()
    if not pg.table_exists("raw", "auxobramb"):
        click.secho("raw.auxobramb no existe. Ejecuta 'ingest' primero.", fg="red")
        sys.exit(2)

    click.secho("=== Contenido completo de raw.auxobramb ===", fg="cyan", bold=True)
    with pg.connection() as conn, conn.cursor() as cur:
        # Detecta dinámicamente las columnas existentes (sin las técnicas _*)
        cur.execute(
            r"""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='raw' AND table_name='auxobramb'
              AND column_name NOT LIKE '\_%' ESCAPE '\'
            ORDER BY ordinal_position
            """
        )
        cols = [r[0] for r in cur.fetchall()]
        col_list = ", ".join(f'"{c}"' for c in cols)
        cur.execute(f"SELECT {col_list} FROM raw.auxobramb ORDER BY ide")
        rows = cur.fetchall()

    width = max(8, min(20, max((len(c) for c in cols), default=10)))
    click.echo(" | ".join(c[:width].ljust(width) for c in cols))
    click.echo("-" * (width * len(cols) + 3 * (len(cols) - 1)))
    for r in rows:
        click.echo(
            " | ".join(
                (str(v)[:width] if v is not None else "").ljust(width) for v in r
            )
        )


@cli.command("inspect-raw")
def inspect_raw() -> None:
    """
    Lista todas las columnas (con sus tipos) de cada tabla de raw.

    Útil para verificar el esquema real de Sigrid en tu BBDD frente al que
    asume el código. Copia su salida para diagnosticar discrepancias.
    """
    settings = get_settings()
    pg = _get_pg()
    tables = [t["target_table"] for t in settings.tables_sigrid.get("tables", [])]

    click.secho("=== Esquemas de raw.* ===", fg="cyan", bold=True)
    click.echo("")

    for tbl in tables:
        if not pg.table_exists("raw", tbl):
            click.secho(f"raw.{tbl}: no creada", fg="yellow")
            click.echo("")
            continue

        with pg.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name, data_type, character_maximum_length
                FROM information_schema.columns
                WHERE table_schema = 'raw' AND table_name = %s
                ORDER BY ordinal_position
                """,
                (tbl,),
            )
            rows = cur.fetchall()
            cur.execute(f'SELECT COUNT(*) FROM raw."{tbl}"')
            count_row = cur.fetchone()
            n_rows = count_row[0] if count_row else 0

        click.secho(f"raw.{tbl}  ({n_rows:,} filas)", fg="green", bold=True)
        click.echo(f"  {'columna':<25} {'tipo':<20} {'longitud':<10}")
        click.echo("  " + "-" * 60)
        for col_name, data_type, max_len in rows:
            # Saltarse columnas técnicas para reducir ruido
            if col_name.startswith("_"):
                continue
            len_str = str(max_len) if max_len is not None else ""
            click.echo(f"  {col_name:<25} {data_type:<20} {len_str:<10}")
        click.echo("")


@cli.command("list-versions")
@click.option("--obra", "obra_id", type=int, required=True, help="obra_id")
@click.option("--ambito", "ambito_id", type=int, default=None,
              help="ambito_id concreto. Si se omite, muestra los 4 ámbitos.")
def list_versions(obra_id: int, ambito_id: int | None) -> None:
    """
    Lista todas las versiones (fases) de una obra para los 4 ámbitos del
    seguimiento, leyendo directamente raw.obrfasamb + clasificación tipada.

    Útil para diagnosticar:
      - Qué versiones existen en cada ámbito.
      - Cuáles son master vigente (Planif Inicial / ABC / Cuatrimestral) y
        cuáles son revisiones (Cierre mensual).
      - Si el `tex` está bien rellenado por el JO.
      - Diferencias entre coste y venta (debería propagarse el tex).
    """
    pg = _get_pg()

    where = ["fa.obride = %(obra)s", "fa.amb IN (3, 7, 8, 11)"]
    params: dict = {"obra": obra_id}
    if ambito_id is not None:
        where = ["fa.obride = %(obra)s", "fa.amb = %(amb)s"]
        params["amb"] = ambito_id

    # Misma clasificación que en mart/02_build_fact.sql (en sync).
    sql = f"""
    WITH base AS (
        SELECT
            fa.amb,
            CASE fa.amb
                WHEN 3  THEN 'Coste real'
                WHEN 7  THEN 'Venta real'
                WHEN 8  THEN 'Master coste'
                WHEN 11 THEN 'Master venta'
            END AS ambito_desc,
            fa.fas,
            stg.fn_sigrid_date_to_date(fa.plafec) AS plafec,
            stg.fn_sigrid_date_to_date(fa.fec)    AS fec_creacion,
            fa.res,
            -- tex efectivo: propio o, si vacío y soy venta, el del coste por (obra,fas)
            COALESCE(
                NULLIF(TRIM(fa.tex), ''),
                NULLIF(TRIM(fa_coste.tex), '')
            ) AS tex_efectivo
        FROM raw.obrfasamb fa
        LEFT JOIN raw.obrfasamb fa_coste
            ON fa_coste.obride = fa.obride
           AND fa_coste.fas    = fa.fas
           AND fa_coste.amb    = 8
           AND fa.amb          = 11
        WHERE {' AND '.join(where)}
    )
    SELECT
        amb, ambito_desc, fas, plafec, fec_creacion, res, tex_efectivo,
        CASE
            WHEN tex_efectivo IS NULL OR length(trim(tex_efectivo)) = 0
                THEN 'Sin clasificar'
            WHEN UPPER(tex_efectivo) LIKE '%%ABC%%'
                THEN 'ABC'
            WHEN UPPER(tex_efectivo) LIKE '%%INICIAL%%'
             AND UPPER(tex_efectivo) LIKE '%%VALORADA%%'
                THEN 'Planif Inicial'
            WHEN UPPER(tex_efectivo) LIKE '%%CUATRIM%%'
              OR UPPER(tex_efectivo) LIKE '%%VALORADA%%'
                THEN 'Cuatrimestral'
            WHEN UPPER(tex_efectivo) LIKE '%%CIERRE%%'
                THEN 'Cierre mensual'
            ELSE 'Sin clasificar'
        END AS tipo
    FROM base
    ORDER BY amb, fas
    """

    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

        if not rows:
            click.secho(f"No hay versiones para obra={obra_id}.", fg="yellow")
            return

        click.secho(f"=== Versiones obra={obra_id} ===\n", fg="cyan", bold=True)

        last_amb = None
        es_master_vigente_count = {3: 0, 7: 0, 8: 0, 11: 0}
        es_master_vigente_total = {3: 0, 7: 0, 8: 0, 11: 0}

        for r in rows:
            amb, amb_desc, fas, plafec, fec, res, tex_ef, tipo = r

            if amb != last_amb:
                click.secho(
                    f"\n▸ Ámbito {amb} · {amb_desc}",
                    fg="blue", bold=True,
                )
                click.echo(
                    f"  {'fas':>4} {'plafec':<12} {'fec_creac':<12} "
                    f"{'tipo':<16} {'res':<28} {'tex':<40}"
                )
                click.echo("  " + "-" * 130)
                last_amb = amb

            plafec_str = str(plafec) if plafec else "—"
            fec_str    = str(fec)    if fec    else "—"
            res_str    = (res or "")[:28]
            tex_str    = (tex_ef or "(vacío)")[:40]
            es_vigente = tipo in ('Planif Inicial', 'ABC', 'Cuatrimestral')

            es_master_vigente_total[amb] += 1
            if es_vigente:
                es_master_vigente_count[amb] += 1

            # Tipo en colores: verde si master vigente, gris si no
            color = "green" if es_vigente else "white"
            tipo_marcado = f"{'✓ ' if es_vigente else '  '}{tipo}"
            click.echo(
                f"  {fas:>4} {plafec_str:<12} {fec_str:<12} "
                + click.style(f"{tipo_marcado:<16}", fg=color)
                + f" {res_str:<28} {tex_str:<40}"
            )

        click.echo("")
        click.secho("Resumen — master vigentes (Planif Inicial / ABC / Cuatrimestral):", bold=True)
        for amb in (3, 7, 8, 11):
            total = es_master_vigente_total[amb]
            vigentes = es_master_vigente_count[amb]
            if total > 0:
                desc = {3: "Coste real", 7: "Venta real",
                        8: "Master coste", 11: "Master venta"}[amb]
                click.echo(f"  amb={amb} ({desc}): {vigentes} master vigente(s) de {total} versión(es) totales")
        click.echo("")


@cli.command("inspect-mart")
@click.option("--obra", "obra_id", type=int, required=True, help="obra_id")
@click.option("--partida", "partida_id", type=int, default=None,
              help="partida_id (opcional, filtra una sola partida)")
@click.option("--anio-mes-desde", "anio_mes_desde", type=str, default=None,
              help="filtra meses desde esta fecha (formato YYYY-MM-DD, día 1)")
@click.option("--anio-mes-hasta", "anio_mes_hasta", type=str, default=None,
              help="filtra meses hasta esta fecha inclusive (formato YYYY-MM-DD, día 1)")
def inspect_mart(
    obra_id: int, partida_id: int | None,
    anio_mes_desde: str | None, anio_mes_hasta: str | None,
) -> None:
    """
    Muestra la matriz de comparativa mensual de mart.fact_seguimiento_mensual:
    para cada mes, los 4 escenarios (Coste Real, Venta Real, Coste Planif,
    Venta Planif) lado a lado, con las descripciones de versión.

    Si se omite --partida, agrega por obra (suma todas las partidas).
    """
    pg = _get_pg()

    where = ["obra_id = %(obra)s"]
    params: dict = {"obra": obra_id}
    if partida_id is not None:
        where.append("partida_id = %(partida)s")
        params["partida"] = partida_id
    if anio_mes_desde:
        where.append("anio_mes >= %(desde)s")
        params["desde"] = anio_mes_desde
    if anio_mes_hasta:
        where.append("anio_mes <= %(hasta)s")
        params["hasta"] = anio_mes_hasta

    # Una fila por mes con los 4 escenarios pivoteados
    sql = f"""
    WITH base AS (
        SELECT
            anio_mes, escenario,
            SUM(importe_mes)    AS imp_mes,
            SUM(importe_origen) AS imp_orig,
            -- Para el planificado, mostramos qué versión rige (debería ser igual
            -- para todas las partidas del mismo mes y misma obra, pero hacemos
            -- MAX por si hay agregación por obra)
            MAX(version_descripcion) AS version_desc,
            MAX(version_tex)         AS version_tex,
            MAX(tipo_master)         AS tipo_master
        FROM mart.fact_seguimiento_mensual
        WHERE {' AND '.join(where)}
        GROUP BY anio_mes, escenario
    )
    SELECT
        anio_mes,
        MAX(CASE WHEN escenario = 'Coste Real'        THEN imp_mes  END) AS cr_mes,
        MAX(CASE WHEN escenario = 'Coste Real'        THEN imp_orig END) AS cr_orig,
        MAX(CASE WHEN escenario = 'Coste Planificado' THEN imp_mes  END) AS cp_mes,
        MAX(CASE WHEN escenario = 'Coste Planificado' THEN imp_orig END) AS cp_orig,
        MAX(CASE WHEN escenario = 'Venta Real'        THEN imp_mes  END) AS vr_mes,
        MAX(CASE WHEN escenario = 'Venta Real'        THEN imp_orig END) AS vr_orig,
        MAX(CASE WHEN escenario = 'Venta Planificada' THEN imp_mes  END) AS vp_mes,
        MAX(CASE WHEN escenario = 'Venta Planificada' THEN imp_orig END) AS vp_orig,
        MAX(CASE WHEN escenario IN ('Coste Planificado', 'Venta Planificada')
                 THEN version_desc END)                                AS planif_version,
        MAX(CASE WHEN escenario IN ('Coste Planificado', 'Venta Planificada')
                 THEN version_tex END)                                 AS planif_tex,
        MAX(CASE WHEN escenario IN ('Coste Planificado', 'Venta Planificada')
                 THEN tipo_master END)                                 AS planif_tipo
    FROM base
    GROUP BY anio_mes
    ORDER BY anio_mes
    """

    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

        if not rows:
            click.secho(
                f"No hay datos en mart.fact_seguimiento_mensual para obra={obra_id}.",
                fg="yellow",
            )
            return

        titulo = f"Comparativa mensual obra={obra_id}"
        if partida_id is not None:
            titulo += f" partida={partida_id}"
        else:
            titulo += " (agregado por obra)"
        click.secho(f"=== {titulo} ===\n", fg="cyan", bold=True)

        click.echo(
            f"  {'mes':<12} "
            f"{'CR_mes':>12} {'CP_mes':>12} {'desv_C':>10}   "
            f"{'VR_mes':>12} {'VP_mes':>12} {'desv_V':>10}   "
            f"{'master_vigente':<26} {'tipo':<16} {'tex (texto JO)':<40}"
        )
        click.echo("  " + "-" * 175)

        tot_cr = tot_cp = tot_vr = tot_vp = 0.0
        for r in rows:
            (mes, cr_mes, cr_orig, cp_mes, cp_orig,
             vr_mes, vr_orig, vp_mes, vp_orig,
             version_desc, version_tex, tipo_master) = r

            cr_f = float(cr_mes) if cr_mes is not None else 0.0
            cp_f = float(cp_mes) if cp_mes is not None else 0.0
            vr_f = float(vr_mes) if vr_mes is not None else 0.0
            vp_f = float(vp_mes) if vp_mes is not None else 0.0

            tot_cr += cr_f; tot_cp += cp_f; tot_vr += vr_f; tot_vp += vp_f

            desv_c = cr_f - cp_f if (cr_mes is not None and cp_mes is not None) else None
            desv_v = vr_f - vp_f if (vr_mes is not None and vp_mes is not None) else None

            def fmt(v: float | None) -> str:
                return f"{v:>12,.2f}" if v is not None else f"{'-':>12}"

            def fmtdiff(v: float | None) -> str:
                if v is None:
                    return f"{'-':>10}"
                return f"{v:>10,.2f}"

            cr_str = fmt(cr_mes); cp_str = fmt(cp_mes)
            vr_str = fmt(vr_mes); vp_str = fmt(vp_mes)
            vd = (version_desc or "")[:26]
            vt = (version_tex or "")[:40]
            tm = (tipo_master or "")[:16]
            click.echo(
                f"  {mes!s:<12} "
                f"{cr_str} {cp_str} {fmtdiff(desv_c)}   "
                f"{vr_str} {vp_str} {fmtdiff(desv_v)}   "
                f"{vd:<26} {tm:<16} {vt:<40}"
            )

        click.echo("  " + "-" * 175)
        click.echo(
            f"  {'TOTAL':<12} "
            f"{tot_cr:>12,.2f} {tot_cp:>12,.2f} {tot_cr-tot_cp:>10,.2f}   "
            f"{tot_vr:>12,.2f} {tot_vp:>12,.2f} {tot_vr-tot_vp:>10,.2f}"
        )
        click.echo("")
        click.echo(
            f"  Beneficio real     = {tot_vr - tot_cr:>12,.2f}€   "
            f"(Venta Real {tot_vr:,.2f} − Coste Real {tot_cr:,.2f})"
        )
        click.echo(
            f"  Beneficio planif   = {tot_vp - tot_cp:>12,.2f}€   "
            f"(Venta Planif {tot_vp:,.2f} − Coste Planif {tot_cp:,.2f})"
        )
        click.echo(
            f"  Desviación benef.  = {(tot_vr-tot_cr) - (tot_vp-tot_cp):>12,.2f}€   "
            f"(real − planif)"
        )
        click.echo("")


@cli.command("reset-mart")
def reset_mart() -> None:
    """
    Borra mart.fact_seguimiento_mensual. Útil cuando se cambia el DDL.
    Tras esto, lanzar `python main.py build-mart` para regenerarla.
    """
    pg = _get_pg()
    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS mart.fact_seguimiento_mensual CASCADE")
        conn.commit()
    click.secho(
        "mart.fact_seguimiento_mensual eliminada. Lanza `python main.py build-mart`.",
        fg="green",
    )


@cli.command("reset-fases")
def reset_fases() -> None:
    """
    Borra y recrea stg.fases desde cero.

    Necesario cuando el DDL cambia (por ejemplo, se añaden columnas anio/mes/nombre_mes).
    Tras este comando, lanzar `python main.py stage` para regenerarla.
    """
    pg = _get_pg()
    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS stg.fases CASCADE")
        conn.commit()
    click.secho(
        "stg.fases eliminada. Lanza `python main.py stage` para regenerarla.",
        fg="green",
    )


@cli.command("reset-plan-mensual")
def reset_plan_mensual() -> None:
    """
    Borra y recrea stg.plan_mensual desde cero.

    Útil cuando el DDL cambia (por ejemplo, ampliando precisión de columnas).
    `CREATE TABLE IF NOT EXISTS` no aplica cambios de tipo en tablas que ya
    existen, así que hay que dropearla manualmente. Tras este comando, lanzar
    `python main.py stage` para regenerarla con el nuevo esquema.
    """
    pg = _get_pg()
    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS stg.plan_mensual CASCADE")
        conn.commit()
    click.secho(
        "stg.plan_mensual eliminada. Lanza `python main.py stage` para regenerarla.",
        fg="green",
    )


@cli.command("inspect-planif-anomalies")
@click.option("--limit", default=20, help="número máximo de filas a mostrar por categoría")
def inspect_planif_anomalies(limit: int) -> None:
    """
    Diagnostica posibles anomalías en raw.obrparpre.planif:
      - Valores fuera del rango [0, 1] esperado (¿porcentajes 0-100?).
      - Valores con magnitud absoluta enorme (overflow).
      - Cadenas con caracteres no numéricos inesperados.
      - Longitudes muy grandes (>50 valores).

    Solo mira las filas amb IN (8, 11) que son las que usa el seguimiento.
    """
    pg = _get_pg()

    sql_out_of_range = """
        WITH ex AS (
            SELECT op.ide, op.obride, op.paride, op.amb, op.fas,
                   u.position, u.valor
            FROM raw.obrparpre op
            CROSS JOIN LATERAL unnest(string_to_array(op.planif, '|'))
                WITH ORDINALITY AS u(valor, position)
            WHERE op.amb IN (8, 11)
              AND op.planif IS NOT NULL
              AND length(op.planif) > 1
              AND u.valor ~ '^-?\\d+([.,]\\d+)?$'
        )
        SELECT ide, obride, paride, amb, fas, position,
               replace(valor, ',', '.')::NUMERIC AS valor_num
        FROM ex
        WHERE replace(valor, ',', '.')::NUMERIC NOT BETWEEN 0 AND 1
        ORDER BY abs(replace(valor, ',', '.')::NUMERIC) DESC
        LIMIT %(limit)s
    """

    sql_non_numeric = """
        WITH ex AS (
            SELECT op.ide, op.obride, op.paride, op.amb, op.fas,
                   u.position, u.valor
            FROM raw.obrparpre op
            CROSS JOIN LATERAL unnest(string_to_array(op.planif, '|'))
                WITH ORDINALITY AS u(valor, position)
            WHERE op.amb IN (8, 11)
              AND op.planif IS NOT NULL
              AND length(op.planif) > 1
        )
        SELECT ide, obride, paride, amb, fas, position, valor
        FROM ex
        WHERE valor !~ '^-?\\d+([.,]\\d+)?$'
          AND length(trim(valor)) > 0
        LIMIT %(limit)s
    """

    sql_extreme_length = """
        SELECT ide, obride, paride, amb, fas,
               array_length(string_to_array(planif, '|'), 1) AS num_meses,
               length(planif) AS chars
        FROM raw.obrparpre
        WHERE amb IN (8, 11)
          AND planif IS NOT NULL
          AND array_length(string_to_array(planif, '|'), 1) > 50
        ORDER BY array_length(string_to_array(planif, '|'), 1) DESC
        LIMIT %(limit)s
    """

    with pg.connection() as conn, conn.cursor() as cur:
        click.secho(
            "=== Valores fuera del rango [0, 1] (los que rompen NUMERIC(10,6)) ===",
            fg="cyan", bold=True,
        )
        cur.execute(sql_out_of_range, {"limit": limit})
        rows = cur.fetchall()
        if not rows:
            click.secho("  (ninguno — todos los valores numéricos están en rango)", fg="green")
        else:
            click.echo(
                f"  {'ide':>10} {'obride':>10} {'paride':>10} {'amb':>4} "
                f"{'fas':>4} {'pos':>4} {'valor':>15}"
            )
            click.echo("  " + "-" * 70)
            for ide, obride, paride, amb, fas, pos, val in rows:
                click.echo(
                    f"  {ide:>10} {obride:>10} {paride:>10} {amb:>4} "
                    f"{fas:>4} {pos:>4} {float(val):>15,.4f}"
                )

        click.echo("")
        click.secho(
            "=== Valores no numéricos en planif (caracteres extraños) ===",
            fg="cyan", bold=True,
        )
        cur.execute(sql_non_numeric, {"limit": limit})
        rows = cur.fetchall()
        if not rows:
            click.secho("  (ninguno)", fg="green")
        else:
            for ide, obride, paride, amb, fas, pos, val in rows:
                click.echo(
                    f"  ide={ide}  obride={obride}  paride={paride}  "
                    f"amb={amb}  fas={fas}  pos={pos}  valor={val!r}"
                )

        click.echo("")
        click.secho(
            "=== planif con más de 50 valores (cadenas excepcionalmente largas) ===",
            fg="cyan", bold=True,
        )
        cur.execute(sql_extreme_length, {"limit": limit})
        rows = cur.fetchall()
        if not rows:
            click.secho("  (ninguno)", fg="green")
        else:
            for ide, obride, paride, amb, fas, n, chars in rows:
                click.echo(
                    f"  ide={ide}  obride={obride}  paride={paride}  amb={amb}  "
                    f"fas={fas}  num_meses={n}  chars={chars}"
                )


@cli.command("inspect-plan")
@click.option("--obra", "obra_id", type=int, required=True, help="obra_id (stg.obras.obra_id)")
@click.option("--partida", "partida_id", type=int, default=None, help="partida_id (opcional, filtra)")
@click.option("--ambito", "ambito_id", type=int, default=None,
              help="ambito_id concreto. Si se omite, muestra los 4 ámbitos del seguimiento (3, 7, 8, 11).")
@click.option("--limit", default=20, help="máximo de presupuestos distintos a mostrar")
def inspect_plan(
    obra_id: int, partida_id: int | None, ambito_id: int | None, limit: int
) -> None:
    """
    Muestra el contenido original de planif y su explosión en stg.plan_mensual
    para una obra (y opcionalmente partida/ámbito). Útil para validar
    visualmente que el parser hace lo correcto y comparar versiones lado a lado.

    Por defecto muestra los 4 ámbitos del seguimiento agrupados:
      3  COSTE          (real,   distribución del coste ejecutado)
      7  VENTA          (real,   distribución de la producción ejecutada)
      8  MASTER COSTE   (planificado, varias versiones a lo largo de la obra)
      11 MASTER VENTA   (planificado, varias versiones a lo largo de la obra)
    """
    pg = _get_pg()

    where = [
        "pp.obra_id = %(obra)s",
        # En master (8, 11) las filas relevantes tienen planif; en reales
        # (3, 7) tienen planif NULL pero `fas` es número de mes-fase (fas=0
        # es "Previsto", fas>=1 son los cierres mensuales). Mostramos:
        # - Master: cualquier fila con planif
        # - Reales: fas >= 1 (cierres históricos, los que sí entran a plan_mensual)
        "((pp.ambito_id IN (8, 11) "
        "    AND op.planif IS NOT NULL AND length(op.planif) > 5) "
        "  OR (pp.ambito_id IN (3, 7) AND pp.fase_num >= 1))",
    ]
    params: dict = {"obra": obra_id, "limit": limit}
    if partida_id is not None:
        where.append("pp.partida_id = %(partida)s")
        params["partida"] = partida_id
    if ambito_id is not None:
        where.append("pp.ambito_id = %(amb)s")
        params["amb"] = ambito_id
    else:
        # Por defecto: los 4 ámbitos del seguimiento
        where.append("pp.ambito_id IN (3, 7, 8, 11)")

    # Etiquetas de ámbito legibles
    sql_ambitos = """
        SELECT ambito_id, descripcion, tipo, uso_seguimiento
        FROM stg.ambitos WHERE ambito_id IN (3, 7, 8, 11)
    """

    sql_presupuestos = f"""
    SELECT pp.presupuesto_id, pp.partida_id, pp.ambito_id, pp.fase_num,
           pp.cantidad, pp.precio, pp.importe, op.planif
    FROM stg.presupuesto pp
    JOIN raw.obrparpre op ON op.ide = pp.presupuesto_id
    WHERE {' AND '.join(where)}
    ORDER BY pp.partida_id, pp.ambito_id, pp.fase_num
    LIMIT %(limit)s
    """

    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute(sql_ambitos)
        ambitos_meta = {r[0]: (r[1], r[2], r[3]) for r in cur.fetchall()}

        cur.execute(sql_presupuestos, params)
        presupuestos = cur.fetchall()

        if not presupuestos:
            click.secho(
                f"No hay filas planif para obra={obra_id} con los filtros dados.",
                fg="yellow",
            )
            return

        click.secho(
            f"=== Inspección planif para obra_id={obra_id} ===", fg="cyan", bold=True
        )
        click.echo("")

        # Agrupar visualmente por ámbito: imprimir un encabezado cada vez
        # que cambia. presupuestos ya viene ORDER BY partida, ambito, version.
        last_partida = None
        last_ambito = None

        for pres in presupuestos:
            pres_id, part_id, amb, fas, cantidad, precio, importe, planif = pres

            # Cabecera de partida
            if part_id != last_partida:
                click.echo("")
                click.secho(
                    f"━━━ Partida {part_id} ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                    fg="magenta", bold=True,
                )
                last_partida = part_id
                last_ambito = None

            # Cabecera de ámbito (dentro de la partida)
            if amb != last_ambito:
                amb_desc, amb_tipo, amb_uso = ambitos_meta.get(
                    amb, ("?", "?", None)
                )
                # Etiqueta de uso en el seguimiento mensual:
                if amb_uso:
                    uso_label = f"  [{amb_uso}]"
                elif amb in (3, 7):
                    # Reales (procesados en stg.plan_mensual aunque sin uso_seguimiento)
                    uso_label = "  [REAL]"
                else:
                    uso_label = "  [no usado en seguimiento]"
                click.secho(
                    f"\n  ▸ Ámbito {amb} · {amb_desc} ({amb_tipo}){uso_label}",
                    fg="blue", bold=True,
                )
                last_ambito = amb

            # Recuperar descripción de la versión desde stg.plan_mensual.
            # Para ámbitos no procesados (3, 7) será NULL y mostramos eso.
            cur.execute(
                """
                SELECT version_descripcion, version_tex, version_fec_creacion
                FROM stg.plan_mensual
                WHERE presupuesto_id = %s LIMIT 1
                """,
                (pres_id,),
            )
            meta = cur.fetchone()
            if meta and meta[0]:
                desc = meta[0]
                tex = meta[1] or "(sin tex)"
                fec_creac = str(meta[2]) if meta[2] else "?"
            else:
                # Buscar en raw.obrfasamb (porque para amb=3/7 plan_mensual no tiene datos)
                cur.execute(
                    """
                    SELECT res, tex, fec FROM raw.obrfasamb
                    WHERE obride = %s AND amb = %s AND fas = %s
                    """,
                    (obra_id, amb, fas),
                )
                meta_raw = cur.fetchone()
                if meta_raw:
                    desc = meta_raw[0] or "(sin descripción)"
                    tex = meta_raw[1] or "(sin tex)"
                    fec_raw = meta_raw[2]
                    fec_creac = (
                        f"{fec_raw // 10000:04d}-{(fec_raw // 100) % 100:02d}-{fec_raw % 100:02d}"
                        if fec_raw and fec_raw > 0 else "?"
                    )
                else:
                    desc = "(no hay fila en obrfasamb)"
                    tex = "(sin tex)"
                    fec_creac = "?"

            click.secho(
                f"\n    presupuesto_id={pres_id}  version={fas}  "
                f"cantidad={float(cantidad):,.4f}  precio={float(precio):,.4f}€/ud  "
                f"importe={float(importe):,.2f}€",
                fg="green", bold=True,
            )
            click.echo(f"    descripción (res): {desc}   creada: {fec_creac}")
            click.echo(f"    texto libre (tex): {tex}")
            click.echo(f"    planif crudo: {planif}")

            # Mostrar los meses explosionados
            cur.execute(
                """
                SELECT posicion_mes, anio_mes, pct_acumulado, pct_mes,
                       precio_unitario, can_mes, can_origen,
                       importe_mes, importe_origen, total_incurrido
                FROM stg.plan_mensual
                WHERE presupuesto_id = %s
                ORDER BY posicion_mes
                """,
                (pres_id,),
            )
            mensual = cur.fetchall()

            if not mensual:
                click.secho(
                    "    (sin filas en stg.plan_mensual — revisar "
                    "obrfasamb.plafec o planif vacío para este presupuesto)",
                    fg="yellow",
                )
            else:
                # Para reales pct_acum/pct_mes son NULL → ajustamos cabecera
                tiene_pct = any(r[2] is not None for r in mensual)
                tiene_totinc = any(r[9] is not None for r in mensual)

                if tiene_pct:
                    click.echo(
                        f"      {'pos':>4} {'mes':<12} "
                        f"{'pct_acum':>9} {'pct_mes':>8} {'precio_ud':>10} "
                        f"{'can_mes':>12} {'can_orig':>12} "
                        f"{'imp_mes':>14} {'imp_orig':>14}"
                    )
                    click.echo("      " + "-" * 106)
                else:
                    # Reales: en vez de pct mostramos totinc al final si aplica
                    extra = "  totinc" if tiene_totinc else ""
                    click.echo(
                        f"      {'fas':>4} {'mes':<12} "
                        f"{'precio_ud':>10} "
                        f"{'can_mes':>12} {'can_orig':>12} "
                        f"{'imp_mes':>14} {'imp_orig':>14}"
                        f"{(' ' + 'totinc'.rjust(14)) if tiene_totinc else ''}"
                    )
                    click.echo("      " + "-" * (88 + (15 if tiene_totinc else 0)))

                suma = 0.0
                for row in mensual:
                    pos, mes, acum, pmes, prec, cmes, corig, imes, iorig, totinc = row
                    suma += float(imes)
                    if tiene_pct:
                        click.echo(
                            f"      {pos:>4} {mes!s:<12} "
                            f"{float(acum):>9.4f} {float(pmes):>8.4f} {float(prec):>10.4f} "
                            f"{float(cmes):>12,.4f} {float(corig):>12,.4f} "
                            f"{float(imes):>14,.2f} {float(iorig):>14,.2f}"
                        )
                    else:
                        totinc_str = f" {float(totinc):>14,.2f}" if totinc is not None else ""
                        click.echo(
                            f"      {pos:>4} {mes!s:<12} "
                            f"{float(prec):>10.4f} "
                            f"{float(cmes):>12,.4f} {float(corig):>12,.4f} "
                            f"{float(imes):>14,.2f} {float(iorig):>14,.2f}"
                            f"{totinc_str}"
                        )
                click.echo("      " + "-" * (106 if tiene_pct else 88 + (15 if tiene_totinc else 0)))
                tot_check = "✓" if abs(suma - float(importe)) < 1.0 else "≠"
                if tiene_pct:
                    click.echo(
                        f"      suma importes mensuales: {suma:,.2f}€   "
                        f"(vs importe total {float(importe):,.2f}€) {tot_check}"
                    )
                else:
                    # En reales el importe a origen final es el último, no la suma
                    ultimo = mensual[-1]
                    last_orig = float(ultimo[8])  # importe_origen
                    click.echo(
                        f"      suma importes mensuales: {suma:,.2f}€   "
                        f"último a origen: {last_orig:,.2f}€   "
                        f"(can*pre actual {float(importe):,.2f}€)"
                    )

        click.echo("")


def _print_result(r) -> None:
    color = {
        StepStatus.SUCCESS: "green",
        StepStatus.SKIPPED: "yellow",
        StepStatus.FAILED: "red",
    }.get(r.status, "white")
    msg = (
        f"[{r.status.value:<7}] {r.step_name:<25} "
        f"rows={r.rows_processed:>9,} duration={r.duration_seconds:>6.1f}s"
    )
    click.secho(msg, fg=color)
    if r.error_message:
        click.secho(f"   ↳ {r.error_message}", fg=color)
    # Estadísticas por tabla (ambos formatos: ingest y build_stg)
    stats = r.metadata.get("per_table_stats") or r.metadata.get("table_stats") or {}
    for tbl, rows in stats.items():
        click.echo(f"   · {tbl}: {rows:,} filas")


@cli.command("inspect-tree")
@click.option("--obra", "obra_id", type=int, required=True, help="obra_id")
@click.option("--top", type=int, default=40,
              help="máximo de partidas a mostrar (por código).")
def inspect_tree(obra_id: int, top: int) -> None:
    """
    Muestra cómo se ha reconstruido el árbol jerárquico de partidas.
    Útil para validar que la clasificación en CD/CI/CP es correcta.
    """
    pg = _get_pg()
    sql = """
    SELECT
        nivel, codigo_partida, capitulo_raiz_cod, categoria,
        descripcion_corta, ruta_capitulos
    FROM stg.partidas
    WHERE obra_id = %(obra)s
    ORDER BY ruta_capitulos
    LIMIT %(top)s
    """
    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, {"obra": obra_id, "top": top})
        rows = cur.fetchall()

        if not rows:
            click.secho(f"No hay partidas para obra={obra_id}.", fg="yellow")
            return

        click.secho(f"\n=== Árbol de partidas · obra={obra_id} ===\n", fg="cyan", bold=True)
        click.echo(
            f"  {'nivel':>5} {'código':<14} {'raíz':<8} {'cat':<6} "
            f"{'descripción':<40} {'ruta':<60}"
        )
        click.echo("  " + "-" * 145)

        cat_counts: dict[str, int] = {}
        for nivel, cod, raiz, cat, desc, ruta in rows:
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
            indent = "  " * (nivel or 0)
            c = (cod or "")[:14]
            r = (raiz or "")[:8]
            ca = (cat or "")[:6]
            de = (desc or "")[:40]
            ru = (ruta or "")[:60]
            click.echo(
                f"  {nivel:>5} {indent}{c:<14} {r:<8} {ca:<6} {de:<40} {ru:<60}"
            )

        click.echo("")
        click.secho("Conteo por categoría:", bold=True)
        for cat, cnt in sorted(cat_counts.items()):
            click.echo(f"  {cat:<6}: {cnt} partidas en el top {top}")
        click.echo("")


@cli.command("inspect-categoria")
@click.option("--obra", "obra_id", type=int, required=True, help="obra_id")
@click.option("--mes", "anio_mes", type=str, default=None,
              help="filtrar por un mes concreto YYYY-MM-DD. Si se omite, muestra todos los meses.")
def inspect_categoria(obra_id: int, anio_mes: str | None) -> None:
    """
    Muestra el agregado por categoría (CD/CI/CP/OTRO) de
    mart.fact_seguimiento_categoria. Útil para validar que las partidas
    se han clasificado correctamente y para Power BI.
    """
    pg = _get_pg()

    where = ["obra_id = %(obra)s"]
    params: dict = {"obra": obra_id}
    if anio_mes:
        where.append("anio_mes = %(mes)s")
        params["mes"] = anio_mes

    sql = f"""
    WITH pivot AS (
        SELECT
            anio_mes, categoria,
            SUM(CASE WHEN escenario = 'Coste Real'        THEN importe_mes END) AS cr_mes,
            SUM(CASE WHEN escenario = 'Coste Planificado' THEN importe_mes END) AS cp_mes,
            SUM(CASE WHEN escenario = 'Venta Real'        THEN importe_mes END) AS vr_mes,
            SUM(CASE WHEN escenario = 'Venta Planificada' THEN importe_mes END) AS vp_mes,
            MAX(num_partidas) AS num_partidas
        FROM mart.fact_seguimiento_categoria
        WHERE {' AND '.join(where)}
        GROUP BY anio_mes, categoria
    )
    SELECT anio_mes, categoria, cr_mes, cp_mes, vr_mes, vp_mes, num_partidas
    FROM pivot
    ORDER BY anio_mes, categoria
    """

    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

        if not rows:
            click.secho(
                f"No hay datos en mart.fact_seguimiento_categoria para "
                f"obra={obra_id}.",
                fg="yellow",
            )
            return

        titulo = f"Agregado por categoría · obra={obra_id}"
        if anio_mes:
            titulo += f" · mes={anio_mes}"
        click.secho(f"\n=== {titulo} ===\n", fg="cyan", bold=True)

        click.echo(
            f"  {'mes':<12} {'cat':<6} "
            f"{'CR_mes':>14} {'CP_mes':>14}   "
            f"{'VR_mes':>14} {'VP_mes':>14}  {'#part':>6}"
        )
        click.echo("  " + "-" * 100)

        def fmt(v):
            if v is None:
                return f"{'-':>14}"
            return f"{float(v):>14,.2f}"

        last_mes = None
        for r in rows:
            mes, cat, crm, cpm, vrm, vpm, num = r
            if mes != last_mes and last_mes is not None:
                click.echo("")  # separador entre meses
            last_mes = mes
            click.echo(
                f"  {mes!s:<12} {cat:<6} "
                f"{fmt(crm)} {fmt(cpm)}   "
                f"{fmt(vrm)} {fmt(vpm)}  {num:>6}"
            )
        click.echo("")


@cli.command("inspect-month")
@click.option("--obra", "obra_id", type=int, required=True, help="obra_id (stg.obras.obra_id)")
@click.option("--mes", "anio_mes", type=str, required=True,
              help="mes concreto, formato YYYY-MM-DD (día 1). Ej: 2026-01-01")
@click.option("--top", type=int, default=20,
              help="número máximo de partidas a mostrar (ordenadas por |coste real|).")
@click.option("--ambito", type=click.Choice(["coste", "venta", "todos"]), default="todos",
              help="qué ámbito mostrar (default: todos).")
def inspect_month(obra_id: int, anio_mes: str, top: int, ambito: str) -> None:
    """
    Muestra todas las partidas de una obra para un mes concreto, con los 4
    escenarios (Coste Real, Coste Planificado, Venta Real, Venta Planificada)
    partida por partida.

    Para CADA escenario muestra DOS columnas en paralelo:
      - importe (Sigrid-compatible, precio redondeado a 2 dec)
      - importe_raw (cálculo crudo, sin redondear precio)

    Con esto se puede contrastar contra Sigrid (la versión Sigrid-compatible
    debe cuadrar al céntimo) y también ver el cálculo puro (para auditoría).

    Útil para validar contra la captura de Sigrid donde se ve la fase
    de un ámbito desglosada por partida.
    """
    pg = _get_pg()

    sql = """
    WITH pivot AS (
        SELECT
            partida_id,
            MAX(codigo_partida)       AS codigo_partida,
            MAX(descripcion_partida)  AS descripcion,
            MAX(unidad_medida)        AS um,
            -- Coste real: mes + origen, en versión Sigrid-compatible y raw
            SUM(CASE WHEN escenario = 'Coste Real'        THEN importe_mes        END) AS cr_mes,
            SUM(CASE WHEN escenario = 'Coste Real'        THEN importe_origen     END) AS cr_orig,
            SUM(CASE WHEN escenario = 'Coste Real'        THEN importe_mes_raw    END) AS cr_mes_raw,
            SUM(CASE WHEN escenario = 'Coste Real'        THEN importe_origen_raw END) AS cr_orig_raw,
            -- Coste planificado
            SUM(CASE WHEN escenario = 'Coste Planificado' THEN importe_mes        END) AS cp_mes,
            SUM(CASE WHEN escenario = 'Coste Planificado' THEN importe_origen     END) AS cp_orig,
            SUM(CASE WHEN escenario = 'Coste Planificado' THEN importe_mes_raw    END) AS cp_mes_raw,
            SUM(CASE WHEN escenario = 'Coste Planificado' THEN importe_origen_raw END) AS cp_orig_raw,
            -- Venta real
            SUM(CASE WHEN escenario = 'Venta Real'        THEN importe_mes        END) AS vr_mes,
            SUM(CASE WHEN escenario = 'Venta Real'        THEN importe_origen     END) AS vr_orig,
            SUM(CASE WHEN escenario = 'Venta Real'        THEN importe_mes_raw    END) AS vr_mes_raw,
            SUM(CASE WHEN escenario = 'Venta Real'        THEN importe_origen_raw END) AS vr_orig_raw,
            -- Venta planificada
            SUM(CASE WHEN escenario = 'Venta Planificada' THEN importe_mes        END) AS vp_mes,
            SUM(CASE WHEN escenario = 'Venta Planificada' THEN importe_origen     END) AS vp_orig,
            SUM(CASE WHEN escenario = 'Venta Planificada' THEN importe_mes_raw    END) AS vp_mes_raw,
            SUM(CASE WHEN escenario = 'Venta Planificada' THEN importe_origen_raw END) AS vp_orig_raw
        FROM mart.fact_seguimiento_mensual
        WHERE obra_id  = %(obra)s
          AND anio_mes = %(mes)s
        GROUP BY partida_id
    )
    SELECT * FROM pivot
    WHERE GREATEST(
        COALESCE(ABS(cr_mes), 0),
        COALESCE(ABS(cp_mes), 0),
        COALESCE(ABS(vr_mes), 0),
        COALESCE(ABS(vp_mes), 0)
    ) > 0
    ORDER BY COALESCE(ABS(cr_mes), 0) + COALESCE(ABS(cp_mes), 0) +
             COALESCE(ABS(vr_mes), 0) + COALESCE(ABS(vp_mes), 0) DESC
    LIMIT %(top)s
    """

    sql_totales = """
    SELECT
        escenario,
        SUM(importe_mes)        AS total_mes,
        SUM(importe_origen)     AS total_orig,
        SUM(importe_mes_raw)    AS total_mes_raw,
        SUM(importe_origen_raw) AS total_orig_raw,
        COUNT(*)                AS num_partidas
    FROM mart.fact_seguimiento_mensual
    WHERE obra_id  = %(obra)s
      AND anio_mes = %(mes)s
    GROUP BY escenario
    ORDER BY escenario
    """

    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, {"obra": obra_id, "mes": anio_mes, "top": top})
        rows = cur.fetchall()

        if not rows:
            click.secho(
                f"No hay datos en mart.fact_seguimiento_mensual para "
                f"obra={obra_id} y mes={anio_mes}.",
                fg="yellow",
            )
            return

        click.secho(
            f"\n=== Detalle por partida · obra={obra_id} · mes={anio_mes} ===\n",
            fg="cyan", bold=True,
        )
        click.echo(
            "Cada métrica se muestra en dos versiones:"
        )
        click.echo(
            "  - sin sufijo: importe Sigrid-compatible (precio redondeado a 2 dec)"
        )
        click.echo(
            "  - sufijo _R:  importe raw (cálculo puro, sin redondear precio)"
        )
        click.echo("")

        def fmt(v):
            if v is None:
                return f"{'-':>12}"
            return f"{float(v):>12,.2f}"

        # Dos secciones: coste (CR/CP) y venta (VR/VP). Imprimo según --ambito
        if ambito in ("coste", "todos"):
            click.secho("--- COSTE (Real vs Planificado) ---", fg="magenta", bold=True)
            click.echo(
                f"  {'partida':<10} {'UM':<5} {'descripción':<28} "
                f"{'CR_mes':>12} {'CR_mes_R':>12}   "
                f"{'CR_orig':>12} {'CR_orig_R':>12}   "
                f"{'CP_mes':>12} {'CP_mes_R':>12}   "
                f"{'CP_orig':>12} {'CP_orig_R':>12}"
            )
            click.echo("  " + "-" * 175)
            for r in rows:
                (part_id, codigo, desc, um,
                 cr_m, cr_o, cr_mR, cr_oR,
                 cp_m, cp_o, cp_mR, cp_oR,
                 vr_m, vr_o, vr_mR, vr_oR,
                 vp_m, vp_o, vp_mR, vp_oR) = r
                cod = (codigo or "")[:10]
                u   = (um or "")[:5]
                de  = (desc or "")[:28]
                click.echo(
                    f"  {cod:<10} {u:<5} {de:<28} "
                    f"{fmt(cr_m)} {fmt(cr_mR)}   "
                    f"{fmt(cr_o)} {fmt(cr_oR)}   "
                    f"{fmt(cp_m)} {fmt(cp_mR)}   "
                    f"{fmt(cp_o)} {fmt(cp_oR)}"
                )
            click.echo("")

        if ambito in ("venta", "todos"):
            click.secho("--- VENTA (Real vs Planificada) ---", fg="magenta", bold=True)
            click.echo(
                f"  {'partida':<10} {'UM':<5} {'descripción':<28} "
                f"{'VR_mes':>12} {'VR_mes_R':>12}   "
                f"{'VR_orig':>12} {'VR_orig_R':>12}   "
                f"{'VP_mes':>12} {'VP_mes_R':>12}   "
                f"{'VP_orig':>12} {'VP_orig_R':>12}"
            )
            click.echo("  " + "-" * 175)
            for r in rows:
                (part_id, codigo, desc, um,
                 cr_m, cr_o, cr_mR, cr_oR,
                 cp_m, cp_o, cp_mR, cp_oR,
                 vr_m, vr_o, vr_mR, vr_oR,
                 vp_m, vp_o, vp_mR, vp_oR) = r
                cod = (codigo or "")[:10]
                u   = (um or "")[:5]
                de  = (desc or "")[:28]
                click.echo(
                    f"  {cod:<10} {u:<5} {de:<28} "
                    f"{fmt(vr_m)} {fmt(vr_mR)}   "
                    f"{fmt(vr_o)} {fmt(vr_oR)}   "
                    f"{fmt(vp_m)} {fmt(vp_mR)}   "
                    f"{fmt(vp_o)} {fmt(vp_oR)}"
                )
            click.echo("")

        # Totales
        cur.execute(sql_totales, {"obra": obra_id, "mes": anio_mes})
        tot_rows = cur.fetchall()

        click.secho(f"TOTALES (todas las partidas de la obra):", bold=True)
        click.echo(
            f"  {'escenario':<22}  "
            f"{'mes (Sigrid)':>16}  {'mes (raw)':>16}  {'diff':>10}     "
            f"{'orig (Sigrid)':>16}  {'orig (raw)':>16}  {'diff':>10}  "
            f"({'#part':>6})"
        )
        click.echo("  " + "-" * 130)
        for esc, tot_mes, tot_orig, tot_mes_raw, tot_orig_raw, num_part in tot_rows:
            tm  = float(tot_mes)      if tot_mes is not None else 0.0
            tmR = float(tot_mes_raw)  if tot_mes_raw is not None else 0.0
            to  = float(tot_orig)     if tot_orig is not None else 0.0
            toR = float(tot_orig_raw) if tot_orig_raw is not None else 0.0
            click.echo(
                f"  {esc:<22}  "
                f"{tm:>16,.2f}  {tmR:>16,.2f}  {tm-tmR:>10,.2f}     "
                f"{to:>16,.2f}  {toR:>16,.2f}  {to-toR:>10,.2f}  "
                f"({num_part:>6})"
            )

        # Cálculos derivados (usa la versión Sigrid-compatible)
        tot = {esc: (float(m), float(o)) for esc, m, o, _, _, _ in tot_rows}
        cr_m = tot.get("Coste Real",        (0, 0))[0]
        cp_m = tot.get("Coste Planificado", (0, 0))[0]
        vr_m = tot.get("Venta Real",        (0, 0))[0]
        vp_m = tot.get("Venta Planificada", (0, 0))[0]
        cr_o = tot.get("Coste Real",        (0, 0))[1]
        cp_o = tot.get("Coste Planificado", (0, 0))[1]
        vr_o = tot.get("Venta Real",        (0, 0))[1]
        vp_o = tot.get("Venta Planificada", (0, 0))[1]

        click.echo("")
        click.secho("Comparativas del mes (usando versión Sigrid-compatible):", bold=True)
        click.echo(f"  Desviación coste     = CR_mes - CP_mes = {cr_m - cp_m:>14,.2f}€")
        click.echo(f"  Desviación venta     = VR_mes - VP_mes = {vr_m - vp_m:>14,.2f}€")
        click.echo(f"  Beneficio real mes   = VR_mes - CR_mes = {vr_m - cr_m:>14,.2f}€")
        click.echo(f"  Beneficio planif mes = VP_mes - CP_mes = {vp_m - cp_m:>14,.2f}€")
        click.echo("")
        click.secho("Comparativas a origen (acumulado hasta este mes):", bold=True)
        click.echo(f"  Desviación coste     = CR_orig - CP_orig = {cr_o - cp_o:>14,.2f}€")
        click.echo(f"  Desviación venta     = VR_orig - VP_orig = {vr_o - vp_o:>14,.2f}€")
        click.echo(f"  Beneficio real orig  = VR_orig - CR_orig = {vr_o - cr_o:>14,.2f}€")
        click.echo(f"  Beneficio planif org = VP_orig - CP_orig = {vp_o - cp_o:>14,.2f}€")
        click.echo("")
        click.secho(
            "Validación contra Sigrid:", bold=True,
        )
        click.echo("  - Las columnas SIN sufijo (CR_mes, VR_mes...) deben cuadrar")
        click.echo("    al céntimo con la cabecera de Sigrid (Importe Parcial/Origen).")
        click.echo("  - Las columnas con sufijo _R (CR_mes_R...) son el cálculo crudo")
        click.echo("    sin redondear pre. Útiles para auditoría.")
        click.echo("  - La columna 'diff' al pie muestra el ajuste por redondeo (∑ Sigrid − ∑ raw).")
        click.echo("")


@cli.command("inspect-cp-tipologia")
@click.option("--obra", "obra_id", type=int, default=None,
              help="obra_id; si se omite muestra todas las obras.")
@click.option("--anio", type=int, default=None,
              help="año concreto (ej. 2025); si se omite muestra todos los años.")
def inspect_cp_tipologia(obra_id: int | None, anio: int | None) -> None:
    """
    Muestra el detalle anual de Costes Proporcionales por tipología desde
    mart.v_pbi_cp_tipologia. Útil para validar el mapping CP.x → tipología
    antes/después de actualizar el visual de Power BI.

    Salida pivotada por tipología con columnas Plan / Real / Desviación.
    """
    pg = _get_pg()

    where: list[str] = []
    params: dict = {}
    if obra_id is not None:
        where.append("obra_id = %(obra)s")
        params["obra"] = obra_id
    if anio is not None:
        where.append("anio = %(anio)s")
        params["anio"] = anio

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
        SELECT obra_id, anio, tipologia, orden_tipologia,
               cp_real, cp_planificado, cp_desviacion
          FROM mart.v_pbi_cp_tipologia
        {where_sql}
         ORDER BY obra_id, anio, orden_tipologia
    """

    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

        if not rows:
            click.secho(
                "No hay datos en mart.v_pbi_cp_tipologia para el filtro indicado.",
                fg="yellow",
            )
            return

        titulo = "Detalle anual CP por tipología"
        if obra_id is not None:
            titulo += f" · obra={obra_id}"
        if anio is not None:
            titulo += f" · año={anio}"
        click.secho(f"\n=== {titulo} ===\n", fg="cyan", bold=True)

        click.echo(
            f"  {'obra':>10}  {'año':>6}  {'tipologia':<16}  "
            f"{'CP_plan':>14}  {'CP_real':>14}  {'desviacion':>14}"
        )
        click.echo("  " + "-" * 84)

        def fmt(v):
            if v is None:
                return f"{'-':>14}"
            return f"{float(v):>14,.2f}"

        last_key = None
        sub_real = sub_plan = sub_desv = 0.0
        totals: dict[tuple[int, int], dict[str, float]] = {}

        for r in rows:
            o_id, an, tip, _orden, cpr, cpp, cpd = r
            key = (o_id, an)

            # Inserta separador y subtotal cuando cambiamos de (obra, año)
            if last_key is not None and key != last_key:
                click.echo(
                    f"  {'':>10}  {'':>6}  {'TOTAL OBRA-AÑO':<16}  "
                    f"{fmt(sub_plan)}  {fmt(sub_real)}  {fmt(sub_desv)}"
                )
                click.echo("")
                sub_real = sub_plan = sub_desv = 0.0

            click.echo(
                f"  {o_id:>10}  {an:>6}  {tip:<16}  "
                f"{fmt(cpp)}  {fmt(cpr)}  {fmt(cpd)}"
            )
            sub_plan += float(cpp or 0)
            sub_real += float(cpr or 0)
            sub_desv += float(cpd or 0)
            totals[key] = {"plan": sub_plan, "real": sub_real, "desv": sub_desv}
            last_key = key

        # Subtotal del último grupo
        if last_key is not None:
            click.echo(
                f"  {'':>10}  {'':>6}  {'TOTAL OBRA-AÑO':<16}  "
                f"{fmt(sub_plan)}  {fmt(sub_real)}  {fmt(sub_desv)}"
            )
            click.echo("")

        click.secho(
            "Notas:\n"
            "  - Año pasado:   suma enero-diciembre + última versión CUAT/ABC ≤ 31/12.\n"
            "  - Año en curso: suma enero-mes_actual + última versión CUAT/ABC ≤ hoy.\n"
            "  - Para auditar el mapping CP.x → tipología partida por partida usa\n"
            "    la consulta de auditoría descrita en docs/MODELO_BI.md.",
            fg="white",
        )
        click.echo("")


@cli.command("build-cierre")
def build_cierre() -> None:
    """
    Materializa el schema `cierre` (cierre mensual de obra).

    Lógica (Tanda 1.4):
      EJECUTADO ← stg.plan_mensual amb 3/7 fas>=1
      FINAL    ← versión master CIERRE del mes (amb 8/11) parseando el
                  texto de la versión; fallback a fase 0 si mes en curso
                  sin master.

    INDEPENDIENTE del mart principal. Solo lee de stg.*.
    """
    settings = get_settings()
    pg = _get_pg()
    ejecucion = _arrancar_ejecucion(pg)
    _ejecutar_paso(BuildCierreStep(settings), pg, ejecucion)


@cli.command("build-maestros")
def build_maestros() -> None:
    """
    Materializa el schema `maestro` (catálogos para consulta externa):
    maestro.obras, maestro.proveedores y maestro.proveedores_obra.

    INDEPENDIENTE del seguimiento/cierre. Solo lee de raw.*. Requiere que la
    ingesta (raw) esté hecha; no necesita stage ni mart.
    """
    settings = get_settings()
    pg = _get_pg()
    ejecucion = _arrancar_ejecucion(pg)
    _ejecutar_paso(BuildMaestrosStep(settings), pg, ejecucion)


@cli.command("reset-cierre")
def reset_cierre() -> None:
    """
    Borra todo el schema `cierre`. Limpia también restos previos en `mart`
    de entregas anteriores. Tras esto, lanzar `build-cierre`.

    Tanda 1.4 NO usa tabla histórica (snapshot eliminado): reset y build
    pueden hacerse libremente sin perder nada irrecuperable.
    """
    pg = _get_pg()
    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute("DROP VIEW  IF EXISTS mart.v_pbi_cierre_resumen      CASCADE")
        cur.execute("DROP VIEW  IF EXISTS mart.v_pbi_dim_concepto_cierre CASCADE")
        cur.execute("DROP TABLE IF EXISTS mart.fact_cierre_mensual       CASCADE")
        cur.execute("DROP SCHEMA IF EXISTS cierre CASCADE")
        conn.commit()
    click.secho(
        "Schema cierre eliminado. Lanza `python main.py build-cierre`.",
        fg="green",
    )


@cli.command("find-obra")
@click.option("--codigo", "codigo", type=str, default=None,
              help="codigo_obra a buscar (p.ej. '0664'). Si se omite, lista todas.")
@click.option("--nombre", "nombre", type=str, default=None,
              help="filtra por nombre_obra (LIKE %nombre%).")
def find_obra(codigo: str | None, nombre: str | None) -> None:
    """Busca obras en stg.obras por codigo_obra o nombre_obra."""
    pg = _get_pg()
    where: list[str] = []
    params: dict = {}
    if codigo:
        where.append("codigo_obra LIKE %(cod)s")
        params["cod"] = f"%{codigo}%"
    if nombre:
        where.append("UPPER(nombre_obra) LIKE UPPER(%(nom)s)")
        params["nom"] = f"%{nombre}%"
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
        SELECT obra_id, codigo_obra, nombre_obra
          FROM stg.obras
        {where_sql}
         ORDER BY codigo_obra NULLS LAST, obra_id
    """
    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    if not rows:
        click.secho("No se encontró ninguna obra con esos filtros.", fg="yellow")
        return

    click.secho(f"=== Obras encontradas ({len(rows)}) ===\n", fg="cyan", bold=True)
    click.echo(f"  {'obra_id':>12}  {'codigo':<10}  {'nombre'}")
    click.echo("  " + "-" * 90)
    for obra_id, cod, nom in rows:
        click.echo(f"  {obra_id:>12}  {(cod or ''):<10}  {(nom or '')[:80]}")
    click.echo("")


@cli.command("list-master-cierre")
@click.option("--codigo", "codigo_obra", type=str, default=None)
@click.option("--obra", "obra_id", type=int, default=None)
def list_master_cierre(codigo_obra: str | None, obra_id: int | None) -> None:
    """
    Lista las versiones master CIERRE de una obra, mostrando el mes que
    parsea cada una con cierre.fn_mes_de_version_master(version_tex, descripcion).

    Útil para diagnosticar por qué un mes resuelve a 'fase_0' o 'sin_dato'
    en vez de 'master'.
    """
    pg = _get_pg()
    if codigo_obra and obra_id is None:
        with pg.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT obra_id FROM stg.obras WHERE codigo_obra = %s",
                (codigo_obra,),
            )
            row = cur.fetchone()
            if not row:
                click.secho(f"No existe obra con codigo='{codigo_obra}'",
                            fg="red", err=True)
                sys.exit(2)
            obra_id = row[0]
    if obra_id is None:
        click.secho("Debes pasar --obra o --codigo.", fg="red", err=True)
        sys.exit(2)

    sql = """
        SELECT DISTINCT
            ambito_id, version, version_tex, version_descripcion,
            cierre.fn_mes_de_version_master(version_tex, version_descripcion) AS mes_parseado,
            version_fec_creacion
          FROM stg.plan_mensual
         WHERE obra_id = %s
           AND ambito_id IN (8, 11)
           AND version_tex IS NOT NULL
           AND UPPER(version_tex) LIKE '%%CIERRE%%'
           AND UPPER(version_tex) NOT LIKE '%%ABC%%'
           AND UPPER(version_tex) NOT LIKE '%%INICIAL%%'
           AND UPPER(version_tex) NOT LIKE '%%VALORADA%%'
           AND UPPER(version_tex) NOT LIKE '%%CUATRIM%%'
         ORDER BY ambito_id, version DESC
    """
    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (obra_id,))
        rows = cur.fetchall()

    if not rows:
        click.secho(
            f"No hay versiones master CIERRE para obra_id={obra_id}.",
            fg="yellow",
        )
        return

    click.secho(f"\n=== Versiones master CIERRE · obra_id={obra_id} ===\n",
                fg="cyan", bold=True)
    click.echo(f"  {'amb':>4}  {'v':>4}  {'mes_parseado':<14}  "
               f"{'fec_creac':<12}  {'tex':<50}")
    click.echo("  " + "-" * 110)
    for amb, ver, tex, desc, mes_p, fec_c in rows:
        amb_lbl = {8: 'coste', 11: 'venta'}.get(amb, str(amb))
        mes_lbl = mes_p.isoformat() if mes_p else click.style('NO PARSEA', fg='red')
        fec_lbl = fec_c.isoformat() if fec_c else '-'
        click.echo(f"  {amb_lbl:>4}  {ver:>4}  {mes_lbl:<14}  "
                   f"{fec_lbl:<12}  {(tex or '')[:50]}")
    click.echo("")


@cli.command("inspect-cierre")
@click.option("--obra", "obra_id", type=int, default=None)
@click.option("--codigo", "codigo_obra", type=str, default=None)
@click.option("--mes", "anio_mes", type=str, default=None,
              help="YYYY-MM-DD. Si se omite, muestra todos.")
def inspect_cierre(
    obra_id: int | None, codigo_obra: str | None, anio_mes: str | None
) -> None:
    """
    Muestra el resumen ejecutivo del cierre con trazabilidad del FINAL.
    Cabecera de cada mes incluye: fase del ejecutado, fuente del FINAL
    (master/fase_0/sin_dato) y, si es master, el texto de la versión.
    """
    if obra_id is None and not codigo_obra:
        click.secho("Debes pasar --obra <id> o --codigo <codigo_obra>.",
                    fg="red", err=True)
        sys.exit(2)

    pg = _get_pg()

    if codigo_obra:
        with pg.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT obra_id, nombre_obra FROM stg.obras WHERE codigo_obra = %s",
                (codigo_obra,),
            )
            row = cur.fetchone()
        if not row:
            click.secho(f"No existe obra '{codigo_obra}'", fg="red", err=True)
            sys.exit(2)
        obra_id, _nom = row
        click.secho(
            f"obra '{codigo_obra}' → obra_id={obra_id} ({_nom})",
            fg="white", dim=True,
        )

    where = ["obra_id = %(obra)s"]
    params: dict = {"obra": obra_id}
    if anio_mes:
        where.append("anio_mes = %(mes)s")
        params["mes"] = anio_mes

    sql = f"""
    SELECT
        anio_mes, nombre_mes, concepto, orden_concepto,
        ejecutado_origen, ejecutado_anterior, ejecutado_mes,
        final_importe, final_anterior, pendiente_importe, variacion_importe,
        ejecutado_origen_pct, ejecutado_anterior_pct, ejecutado_mes_pct,
        pendiente_pct, final_pct, variacion_pct,
        fase_numero, fase_nombre_mes,
        final_fuente, final_version_master, final_version_tex
      FROM cierre.v_pbi_cierre_resumen
     WHERE {' AND '.join(where)}
     ORDER BY anio_mes, orden_concepto
    """

    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    if not rows:
        click.secho(
            f"No hay datos para obra_id={obra_id}.", fg="yellow",
        )
        return

    titulo = f"Cierre mensual · obra_id={obra_id}"
    if anio_mes:
        titulo += f" · mes={anio_mes}"
    click.secho(f"\n=== {titulo} ===\n", fg="cyan", bold=True)

    def fmt(v):
        return f"{'-':>14}" if v is None else f"{float(v):>14,.2f}"

    def fpct(v):
        return f"{'-':>7}" if v is None else f"{float(v):>7,.2f}"

    # Localiza la metadata de cada mes desde una fila de COSTE (no derivada)
    meta_por_mes: dict = {}
    for r in rows:
        mes_v = r[0]
        fnum, fnm = r[17], r[18]
        ffuente, fvm, fvt = r[19], r[20], r[21]
        if mes_v not in meta_por_mes and fnum is not None:
            meta_por_mes[mes_v] = (fnum, fnm, ffuente, fvm, fvt)

    last_mes = None
    for r in rows:
        (mes, nm_mes, concepto, _orden,
         eo, ea, em,
         fi, fa, pi_imp, var,
         eo_pct, ea_pct, em_pct, pen_pct, fi_pct, var_pct,
         _fase_num, _fase_nm,
         _ffuente, _fvm, _fvt) = r

        if mes != last_mes:
            if last_mes is not None:
                click.echo("")
            meta = meta_por_mes.get(mes, (None, None, None, None, None))
            fnum_show, fnm_show, ffuente_show, fvm_show, fvt_show = meta
            fase_info = (
                f"fase {fnum_show} · {fnm_show}"
                if fnum_show is not None else "fase: -"
            )
            if ffuente_show == 'master':
                final_info = (
                    f"FINAL: master v{fvm_show} ({(fvt_show or '')[:35]})"
                )
                fuente_color = "green"
            elif ffuente_show == 'fase_0':
                final_info = "FINAL: fase_0 (mes en curso, sin master)"
                fuente_color = "yellow"
            else:
                final_info = "FINAL: sin_dato"
                fuente_color = "red"
            click.secho(f"\n▸ {nm_mes}  ({fase_info})", fg="blue", bold=True)
            click.secho(f"   {final_info}", fg=fuente_color, dim=True)
            click.echo(
                f"  {'concepto':<12}  "
                f"{'EJEC MES':>14} {'%':>7}  "
                f"{'EJEC ANT':>14} {'%':>7}  "
                f"{'EJEC ORIG':>14} {'%':>7}  "
                f"{'PENDIENTE':>14} {'%':>7}  "
                f"{'FINAL':>14} {'%':>7}  "
                f"{'VAR MES':>14} {'%':>7}"
            )
            click.echo("  " + "-" * 184)
            last_mes = mes

        color = None
        if concepto == "BENEFICIO":
            color = "red" if (eo is not None and float(eo) < 0) else "green"

        line = (
            f"  {concepto:<12}  "
            f"{fmt(em)} {fpct(em_pct)}  "
            f"{fmt(ea)} {fpct(ea_pct)}  "
            f"{fmt(eo)} {fpct(eo_pct)}  "
            f"{fmt(pi_imp)} {fpct(pen_pct)}  "
            f"{fmt(fi)} {fpct(fi_pct)}  "
            f"{fmt(var)} {fpct(var_pct)}"
        )
        if color:
            click.secho(line, fg=color,
                        bold=(concepto in ("VENTA", "GASTOS", "BENEFICIO")))
        else:
            click.echo(line)

    click.echo("")
    click.secho("Leyenda:", bold=True)
    click.echo("  - FINAL: master v<N> (<tex>)  → versión master CIERRE del mes")
    click.echo("  - FINAL: fase_0               → mes en curso sin master; usa Previsto vivo")
    click.echo("  - FINAL: sin_dato             → ni master ni fase 0 para ese mes")
    click.echo("")
    click.secho("Mapping al Excel CONTROL DE GESTIÓN:", bold=True)
    click.echo("  R20 VENTA  | R22 INDIRECTOS | R23 DIRECTOS | R24 GENERALES")
    click.echo("  R21 GASTOS (=I+D+G) | R25 BENEFICIO (=VENTA-GASTOS)")
    click.echo("")


@cli.command("inspect-indirectos-detalle")
@click.option("--obra", "obra_id", type=int, default=None)
@click.option("--codigo", "codigo_obra", type=str, default=None)
@click.option("--mes", "anio_mes", type=str, default=None,
              help="YYYY-MM-DD. Si se omite, último mes con datos.")
@click.option("--variante", "variante",
              type=click.Choice(["prod", "prod_inc", "lineal", "lineal_inc"]),
              default="prod",
              help="Variante de periodificación a mostrar: prod (producción), "
                   "prod_inc (producción con incurrido), lineal (meses), "
                   "lineal_inc (lineal con incurrido). Default: prod.")
@click.option("--todas", is_flag=True, default=False,
              help="Mostrar las 4 variantes lado a lado (output ancho).")
def inspect_indirectos_detalle(
    obra_id: int | None, codigo_obra: str | None,
    anio_mes: str | None, variante: str, todas: bool,
) -> None:
    """
    Muestra el desglose de INDIRECTOS por (grupo CI × subcategoría).

    Cuatro variantes de periodificación (Tanda 4.2), solo para INFRAESTRUCTURA:

    \b
      prod         = fase0 × (venta_origen / venta_final)
      prod_inc     = igual pero solo desde el primer mes con incurrido
      lineal       = fase0 × (mes_actual / plazo_total)    [sin cap al 100%]
      lineal_inc   = lineal pero solo desde el primer mes con incurrido

    El PARCIAL de cada variante = origen_periodif[M] − ejecutado_origen[M−1]
    (Ruesma ajusta el ejecutado_origen anterior en Sigrid al periodif del
    cierre previo, para que el parcial sea el delta del ratio del mes).
    """
    if obra_id is None and not codigo_obra:
        click.secho("Debes pasar --obra <id> o --codigo <codigo_obra>.",
                    fg="red", err=True)
        sys.exit(2)

    pg = _get_pg()

    if codigo_obra:
        with pg.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT obra_id, nombre_obra FROM stg.obras WHERE codigo_obra = %s",
                (codigo_obra,),
            )
            row = cur.fetchone()
        if not row:
            click.secho(f"No existe obra '{codigo_obra}'", fg="red", err=True)
            sys.exit(2)
        obra_id, _nom = row
        click.secho(
            f"obra '{codigo_obra}' → obra_id={obra_id} ({_nom})",
            fg="white", dim=True,
        )

    # Si no se da mes, tomar el último con datos
    if not anio_mes:
        with pg.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT MAX(anio_mes) FROM cierre.v_pbi_cierre_indirectos_detalle "
                "WHERE obra_id = %s",
                (obra_id,),
            )
            row = cur.fetchone()
            if row and row[0]:
                anio_mes = row[0].isoformat()
            else:
                click.secho("No hay datos de detalle INDIRECTOS para esta obra.",
                            fg="yellow")
                return

    sql = """
    SELECT
        grupo_cod, subcategoria_cod,
        grupo_nombre, subcategoria_nombre,
        ejecutado_origen, ejecutado_anterior, ejecutado_mes,
        es_infraestructura, importe_fase0, plazo_total_meses,
        -- Var 1: prod
        ratio_periodif, pct_periodificacion,
        ejecutado_origen_periodif, ejecutado_mes_periodif,
        -- Var 2: prod_inc
        ejecutado_origen_periodif_inc, ejecutado_mes_periodif_inc,
        -- Var 3: lineal
        ratio_lineal, pct_periodificacion_lineal,
        ejecutado_origen_periodif_lineal, ejecutado_mes_periodif_lineal,
        -- Var 4: lineal_inc
        ejecutado_origen_periodif_lineal_inc, ejecutado_mes_periodif_lineal_inc
      FROM cierre.v_pbi_cierre_indirectos_detalle
     WHERE obra_id = %(obra)s AND anio_mes = %(mes)s
     ORDER BY grupo_nombre, subcategoria_nombre
    """
    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, {"obra": obra_id, "mes": anio_mes})
        rows = cur.fetchall()

    if not rows:
        click.secho(f"No hay datos para obra={obra_id} mes={anio_mes}",
                    fg="yellow")
        return

    plazo_info = next((r[9] for r in rows if r[9] is not None), None)

    # Selección de columnas según variante / todas
    # Mapeo (variante → índice en row de origen, índice de parcial, índice de %)
    VAR_INFO = {
        "prod":       ("PROD",       12, 13, 11),   # origen, mes, pct
        "prod_inc":   ("PROD INC",   14, 15, None),
        "lineal":     ("LINEAL",     18, 19, 17),
        "lineal_inc": ("LINEAL INC", 20, 21, None),
    }
    VAR_DESC = {
        "prod":       "fase0 × (venta_origen / venta_final)",
        "prod_inc":   "PROD pero solo desde el primer mes con incurrido",
        "lineal":     "fase0 × (mes_actual / plazo_total)  [sin cap al 100%]",
        "lineal_inc": "LINEAL pero solo desde el primer mes con incurrido",
    }

    click.secho(
        f"\n=== Detalle INDIRECTOS · obra_id={obra_id} · mes={anio_mes} ===\n",
        fg="cyan", bold=True,
    )
    if plazo_info is not None:
        click.secho(
            f"  Plazo total de la obra: {float(plazo_info):,.1f} meses",
            fg="white", dim=True,
        )

    def f12(v): return f"{'-':>12}" if v is None else f"{float(v):>12,.2f}"
    def f7(v):  return f"{'-':>7}"  if v is None else f"{float(v):>6,.2f}%"
    def f14(v): return f"{'-':>14}" if v is None else f"{float(v):>14,.2f}"
    def f8(v):  return f"{'-':>8}"  if v is None else f"{float(v):>7,.2f}%"

    if todas:
        # 4 variantes lado a lado: muy ancho
        click.echo(
            f"  {'grupo':<26}  {'subcategoría':<36}  "
            f"{'EJEC MES':>11}  {'EJEC ORIG':>11}  "
            f"{'PROD':>11}  {'P_INC':>11}  "
            f"{'LIN':>11}  {'L_INC':>11}"
        )
        click.echo("  " + "-" * 154)
    else:
        var_label = VAR_INFO[variante][0]
        click.echo(
            f"  {'grupo':<30}  {'subcategoría':<40}  "
            f"{'EJEC MES':>14}  {'EJEC ANT':>14}  {'EJEC ORIG':>14}  "
            f"{var_label+' ORIG':>14}  {var_label+' MES':>14}  {'% '+var_label:>10}"
        )
        click.echo("  " + "-" * 170)

    last_grupo = None
    total_origen = 0.0
    totales_periodif = {"prod_orig": 0.0, "prod_mes": 0.0,
                        "pi_orig": 0.0, "pi_mes": 0.0,
                        "lin_orig": 0.0, "lin_mes": 0.0,
                        "li_orig": 0.0, "li_mes": 0.0}

    for r in rows:
        (grupo_cod, subcat_cod, grupo_nm, subcat_nm,
         eo, ea, em,
         es_infra, imp_f0, _plazo,
         _r_p, pct_p, eo_p, em_p,
         eo_pi, em_pi,
         _r_l, pct_l, eo_l, em_l,
         eo_li, em_li) = r

        if grupo_nm != last_grupo:
            if last_grupo is not None:
                click.echo("")
            last_grupo = grupo_nm

        if todas:
            grupo_label = f"{(grupo_nm or '')[:18]} ({grupo_cod})"
            subcat_label = f"{(subcat_nm or '')[:28]} ({subcat_cod})"
            click.echo(
                f"  {grupo_label:<26}  {subcat_label:<36}  "
                f"{f12(em)}  {f12(eo)}  "
                f"{f12(eo_p)}  {f12(eo_pi)}  "
                f"{f12(eo_l)}  {f12(eo_li)}"
            )
            if es_infra:
                if eo_p is not None: totales_periodif["prod_orig"] += float(eo_p)
                if em_p is not None: totales_periodif["prod_mes"]  += float(em_p)
                if eo_pi is not None: totales_periodif["pi_orig"] += float(eo_pi)
                if em_pi is not None: totales_periodif["pi_mes"]  += float(em_pi)
                if eo_l is not None: totales_periodif["lin_orig"] += float(eo_l)
                if em_l is not None: totales_periodif["lin_mes"]  += float(em_l)
                if eo_li is not None: totales_periodif["li_orig"] += float(eo_li)
                if em_li is not None: totales_periodif["li_mes"]  += float(em_li)
        else:
            # Una sola variante
            _, idx_o, idx_m, idx_pct = VAR_INFO[variante]
            v_o = r[idx_o]
            v_m = r[idx_m]
            v_pct = r[idx_pct] if idx_pct is not None else None
            grupo_label = f"{(grupo_nm or '')[:22]} ({grupo_cod})"
            subcat_label = f"{(subcat_nm or '')[:32]} ({subcat_cod})"
            if es_infra and v_o is not None:
                p_orig_s = f14(v_o)
                p_mes_s  = f14(v_m)
                p_pct_s  = f"{'-':>10}" if v_pct is None else f"{float(v_pct):>9,.2f}%"
                totales_periodif["prod_orig"] += float(v_o)
                totales_periodif["prod_mes"]  += float(v_m or 0)
            else:
                p_orig_s = f"{'-':>14}"
                p_mes_s  = f"{'-':>14}"
                p_pct_s  = f"{'-':>10}"
            click.echo(
                f"  {grupo_label:<30}  {subcat_label:<40}  "
                f"{float(em):>14,.2f}  {float(ea):>14,.2f}  {float(eo):>14,.2f}  "
                f"{p_orig_s}  {p_mes_s}  {p_pct_s}"
            )
        total_origen += float(eo)

    sep_len = 154 if todas else 170
    click.echo("  " + "-" * sep_len)

    if todas:
        click.secho(
            f"  {'TOTAL INDIRECTOS':<66}  "
            f"{'':>11}  {total_origen:>11,.2f}  "
            f"{'':>11}  {'':>11}  {'':>11}  {'':>11}",
            fg="cyan", bold=True,
        )
        if any(v > 0 for v in totales_periodif.values()):
            click.secho(
                f"  {'  INFRAESTRUCTURA (origen)':<66}  "
                f"{'':>11}  {'':>11}  "
                f"{totales_periodif['prod_orig']:>11,.2f}  "
                f"{totales_periodif['pi_orig']:>11,.2f}  "
                f"{totales_periodif['lin_orig']:>11,.2f}  "
                f"{totales_periodif['li_orig']:>11,.2f}",
                fg="white", dim=True,
            )
            click.secho(
                f"  {'  INFRAESTRUCTURA (mes)':<66}  "
                f"{'':>11}  {'':>11}  "
                f"{totales_periodif['prod_mes']:>11,.2f}  "
                f"{totales_periodif['pi_mes']:>11,.2f}  "
                f"{totales_periodif['lin_mes']:>11,.2f}  "
                f"{totales_periodif['li_mes']:>11,.2f}",
                fg="white", dim=True,
            )
    else:
        var_label = VAR_INFO[variante][0]
        click.secho(
            f"  {'TOTAL INDIRECTOS':<74}  {'':>14}  {'':>14}  {total_origen:>14,.2f}  "
            f"{'':>14}  {'':>14}",
            fg="cyan", bold=True,
        )
        if totales_periodif["prod_orig"] > 0:
            click.secho(
                f"  {f'  INFRAESTRUCTURA ({var_label})':<74}  "
                f"{'':>14}  {'':>14}  {'':>14}  "
                f"{totales_periodif['prod_orig']:>14,.2f}  "
                f"{totales_periodif['prod_mes']:>14,.2f}",
                fg="white", dim=True,
            )

    click.echo("")
    click.echo("Notas:")
    click.echo("  - EJEC = incurrido real (leído de plan_mensual amb=3).")
    if todas:
        click.echo("  - PROD   = fase0 × (venta_origen / venta_final).")
        click.echo("  - P_INC  = PROD pero solo desde el primer mes con incurrido.")
        click.echo("  - LIN    = fase0 × (mes_actual / plazo_total)  [sin cap].")
        click.echo("  - L_INC  = LIN pero solo desde el primer mes con incurrido.")
    else:
        click.echo(f"  - {VAR_INFO[variante][0]:<10} = {VAR_DESC[variante]}")
        click.echo("  - Usa --todas para ver las 4 variantes a la vez.")
        click.echo("    O --variante prod_inc|lineal|lineal_inc.")
    click.echo("  - Parcial de cada variante = origen[M] − ejecutado_origen[M−1].")
    click.echo("    Ruesma ajusta ejec_origen[M−1] en Sigrid al periodif previo.")
    click.echo("")



@cli.command("inspect-generales-detalle")
@click.option("--obra", "obra_id", type=int, default=None)
@click.option("--codigo", "codigo_obra", type=str, default=None)
@click.option("--mes", "anio_mes", type=str, default=None,
              help="YYYY-MM-DD. Si se omite, último mes con datos.")
def inspect_generales_detalle(
    obra_id: int | None, codigo_obra: str | None, anio_mes: str | None
) -> None:
    """
    Muestra el desglose de GENERALES por tipología (Levantamiento, Seguros,
    Avales, Contratación, Medio Ambiente, Aporte GG).
    """
    if obra_id is None and not codigo_obra:
        click.secho("Debes pasar --obra <id> o --codigo <codigo_obra>.",
                    fg="red", err=True)
        sys.exit(2)

    pg = _get_pg()

    if codigo_obra:
        with pg.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT obra_id, nombre_obra FROM stg.obras WHERE codigo_obra = %s",
                (codigo_obra,),
            )
            row = cur.fetchone()
        if not row:
            click.secho(f"No existe obra '{codigo_obra}'", fg="red", err=True)
            sys.exit(2)
        obra_id, _nom = row
        click.secho(
            f"obra '{codigo_obra}' → obra_id={obra_id} ({_nom})",
            fg="white", dim=True,
        )

    if not anio_mes:
        with pg.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT MAX(anio_mes) FROM cierre.v_pbi_cierre_generales_detalle "
                "WHERE obra_id = %s",
                (obra_id,),
            )
            row = cur.fetchone()
            if row and row[0]:
                anio_mes = row[0].isoformat()
            else:
                click.secho("No hay datos de detalle GENERALES para esta obra.",
                            fg="yellow")
                return

    sql = """
    SELECT
        tipologia, orden_tipologia,
        ejecutado_origen, ejecutado_anterior, ejecutado_mes
      FROM cierre.v_pbi_cierre_generales_detalle
     WHERE obra_id = %(obra)s AND anio_mes = %(mes)s
     ORDER BY orden_tipologia
    """
    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, {"obra": obra_id, "mes": anio_mes})
        rows = cur.fetchall()

    if not rows:
        click.secho(f"No hay datos para obra={obra_id} mes={anio_mes}",
                    fg="yellow")
        return

    click.secho(
        f"\n=== Detalle GENERALES · obra_id={obra_id} · mes={anio_mes} ===\n",
        fg="cyan", bold=True,
    )
    click.echo(
        f"  {'tipología':<18}  "
        f"{'EJEC MES':>14}  {'EJEC ANT':>14}  {'EJEC ORIG':>14}"
    )
    click.echo("  " + "-" * 72)

    total_origen = 0.0
    for tipo, _orden, eo, ea, em in rows:
        click.echo(
            f"  {tipo:<18}  "
            f"{float(em):>14,.2f}  {float(ea):>14,.2f}  {float(eo):>14,.2f}"
        )
        total_origen += float(eo)

    click.echo("  " + "-" * 72)
    click.secho(
        f"  {'TOTAL GENERALES':<18}  {'':>14}  {'':>14}  {total_origen:>14,.2f}",
        fg="cyan", bold=True,
    )
    click.echo("")
    click.echo("Validación: este total debe coincidir EXACTAMENTE con la fila")
    click.echo("GENERALES de `inspect-cierre` (ejecutado origen).")
    click.echo("")


@cli.command("inspect-cabecera")
@click.option("--obra", "obra_id", type=int, default=None)
@click.option("--codigo", "codigo_obra", type=str, default=None)
def inspect_cabecera(obra_id: int | None, codigo_obra: str | None) -> None:
    """
    Muestra la cabecera del cierre (parte superior del Excel CONTROL DE
    GESTIÓN): identificación de la obra, cliente, técnico responsable,
    fechas, plazo y presupuestos inicial/vigente.

    Marca los campos vacíos en Sigrid como "(no disponible)".
    """
    if obra_id is None and not codigo_obra:
        click.secho("Debes pasar --obra <id> o --codigo <codigo_obra>.",
                    fg="red", err=True)
        sys.exit(2)

    pg = _get_pg()

    if codigo_obra:
        with pg.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT obra_id FROM stg.obras WHERE codigo_obra = %s",
                (codigo_obra,),
            )
            row = cur.fetchone()
        if not row:
            click.secho(f"No existe obra '{codigo_obra}'", fg="red", err=True)
            sys.exit(2)
        obra_id = row[0]

    sql = """
    SELECT
        codigo_obra, nombre_obra,
        cliente_nombre, tecnico_responsable,
        centro_coste_ide, centro_coste_nombre,
        tipo_obra_ide, tipo_obra_nombre,
        clase_obra_ide, clase_obra_nombre,
        fecha_inicio_previsto, fecha_fin_previsto,
        fecha_inicio_real, fecha_fin_real, fecha_adjudicacion,
        plazo_meses, coeficiente_indirectos, superficie_total,
        presupuesto_inicial_venta, version_inicial,
        presupuesto_vigente_venta, version_vigente,
        presupuesto_aprobado_venta,
        modificados_aprobados
      FROM cierre.v_pbi_cierre_cabecera
     WHERE obra_id = %s
    """
    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (obra_id,))
        row = cur.fetchone()

    if not row:
        click.secho(f"No hay cabecera para obra_id={obra_id}.", fg="yellow")
        return

    (codigo, nombre, cliente, tecnico,
     cc_ide, cc_nom, tipo_ide, tipo_nom, clase_ide, clase_nom,
     fini_p, ffin_p, fini_r, ffin_r, fadj,
     plazo, coef, sup,
     pres_ini, ver_ini, pres_vig, ver_vig, pres_aprob, modif) = row

    def show(v, fmt=None):
        if v is None:
            return click.style("(no disponible)", fg="yellow", dim=True)
        if fmt == "money":
            return f"{float(v):,.2f} €"
        if fmt == "date":
            return v.isoformat()
        if fmt == "num":
            return f"{float(v):,.2f}"
        return str(v)

    click.secho(f"\n=== Cabecera · {codigo} · {nombre} ===\n",
                fg="cyan", bold=True)

    click.secho("IDENTIFICACIÓN", bold=True)
    click.echo(f"  Código obra ........... {codigo}")
    click.echo(f"  Nombre ................ {nombre}")
    click.echo(f"  Cliente ............... {show(cliente)}")
    click.echo(f"  Técnico responsable ... {show(tecnico)}")
    def show_with_id(nombre, ide):
        """Muestra '<nombre>  (id: N)' si hay nombre, '(no disponible)' si no."""
        if nombre is None and ide is None:
            return click.style("(no disponible)", fg="yellow", dim=True)
        if nombre is None:
            return f"(id={ide}, sin texto en catálogo)"
        return f"{nombre}  (id: {ide})"

    click.echo(f"  Centro de coste ....... {show_with_id(cc_nom, cc_ide)}")
    click.echo(f"  Tipo de obra .......... {show_with_id(tipo_nom, tipo_ide)}")
    click.echo(f"  Clase de obra ......... {show_with_id(clase_nom, clase_ide)}")
    click.echo("")

    click.secho("PLAZOS", bold=True)
    click.echo(f"  Inicio previsto ....... {show(fini_p, 'date')}")
    click.echo(f"  Fin previsto .......... {show(ffin_p, 'date')}")
    click.echo(f"  Inicio real ........... {show(fini_r, 'date')}")
    click.echo(f"  Fin real .............. {show(ffin_r, 'date')}")
    click.echo(f"  Adjudicación .......... {show(fadj, 'date')}")
    click.echo(f"  Plazo (meses) ......... {show(plazo, 'num')}")
    click.echo("")

    click.secho("CARACTERÍSTICAS", bold=True)
    click.echo(f"  Coef. indirectos ...... {show(coef, 'num')}")
    click.echo(f"  Superficie total ...... {show(sup, 'num')}")
    click.echo("")

    click.secho("PRESUPUESTO (VENTA, de master CIERRE)", bold=True)
    click.echo(f"  Inicial ............... {show(pres_ini, 'money')}"
               + (f"   [{ver_ini}]" if ver_ini else ""))
    click.echo(f"  Vigente ............... {show(pres_vig, 'money')}"
               + (f"   [{ver_vig}]" if ver_vig else ""))
    click.echo(f"  APROBADO .............. {show(pres_aprob, 'money')}   "
               f"(divisor de VENTA FINAL %; por defecto = inicial)")
    click.echo(f"  Modificados aprobados . {show(modif, 'money')}")
    click.echo("")

    click.secho("Notas:", bold=True)
    click.echo("  - (no disponible) = el campo viene vacío/0 en Sigrid.")
    click.echo("  - (id=N, sin texto en catálogo) = el ID existe pero no tiene")
    click.echo("    fila correspondiente en cen/auxobrtip/auxobrcla.")
    click.echo("")


@cli.command("inspect-planif-vs-real")
@click.option("--obra", "obra_id", type=int, default=None)
@click.option("--codigo", "codigo_obra", type=str, default=None)
@click.option("--mes", "anio_mes", type=str, default=None,
              help="YYYY-MM-DD. Si se omite, último mes con datos.")
def inspect_planif_vs_real(
    obra_id: int | None, codigo_obra: str | None, anio_mes: str | None,
) -> None:
    """
    Muestra el cuadro PLANIFICADO vs REAL del mes para una obra.

    Replica el cuadro del Excel: 6 conceptos (PRODUCCIÓN, COSTES DIRECTOS /
    INDIRECTOS / PROPORCIONALES, TOTAL COSTES, BENEFICIO) con planificado,
    real, diferencia (= Real − Planificado) y % desviación (= Diff / Planif).

    Importes DEL MES (parcial), no a origen. Fuente: mart de planificación.
    """
    if obra_id is None and not codigo_obra:
        click.secho("Debes pasar --obra <id> o --codigo <codigo_obra>.",
                    fg="red", err=True)
        sys.exit(2)

    pg = _get_pg()

    # Resolver obra_id desde código si toca
    if codigo_obra:
        with pg.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT obra_id, nombre_obra FROM stg.obras WHERE codigo_obra = %s",
                (codigo_obra,),
            )
            row = cur.fetchone()
        if not row:
            click.secho(f"No existe obra '{codigo_obra}'", fg="red", err=True)
            sys.exit(2)
        obra_id, nombre = row
        click.echo(f"obra '{codigo_obra}' → obra_id={obra_id} ({nombre})")

    # Resolver mes si no se ha pasado
    if not anio_mes:
        with pg.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT MAX(anio_mes) FROM cierre.v_pbi_planif_vs_real WHERE obra_id = %s",
                (obra_id,),
            )
            r = cur.fetchone()
        if not r or not r[0]:
            click.secho(f"No hay datos planif vs real para obra_id={obra_id}",
                        fg="yellow")
            return
        anio_mes = r[0].isoformat()
        click.secho(f"Mes no especificado, usando el último disponible: {anio_mes}",
                    fg="white", dim=True)

    sql = """
    SELECT
        concepto_cuadro, planificado, real, diferencia, desviacion_pct
      FROM cierre.v_pbi_planif_vs_real
     WHERE obra_id = %(obra)s AND anio_mes = %(mes)s
     ORDER BY orden_concepto
    """
    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, {"obra": obra_id, "mes": anio_mes})
        rows = cur.fetchall()

    if not rows:
        click.secho(f"No hay datos para obra={obra_id} mes={anio_mes}",
                    fg="yellow")
        return

    click.secho(
        f"\n=== PLANIFICADO vs REAL · obra_id={obra_id} · mes={anio_mes} ===\n",
        fg="cyan", bold=True,
    )

    click.echo(
        f"  {'concepto':<24}  "
        f"{'PLANIFICADO':>16}  {'REAL':>16}  "
        f"{'DIFERENCIA':>16}  {'DESVIACIÓN':>12}"
    )
    click.echo("  " + "-" * 92)

    def fmt(v):
        return "-" if v is None else f"{float(v):>16,.2f}"

    def fmt_pct(v):
        if v is None:
            return f"{'-':>12}"
        return f"{float(v):>11,.2f}%"

    for concepto, planif, real, diff, desv in rows:
        # Color: rojo si Real es peor que Planif (diff negativa en producción/beneficio,
        # o diff positiva en costes). Simplificación: rojo si desv > 10% en módulo.
        line = (
            f"  {concepto:<24}  "
            f"{fmt(planif):>16}  {fmt(real):>16}  "
            f"{fmt(diff):>16}  {fmt_pct(desv):>12}"
        )
        # Negrita para TOTAL COSTES y BENEFICIO
        if concepto in ("TOTAL COSTES", "BENEFICIO"):
            click.secho(line, bold=True)
        else:
            click.echo(line)

    click.echo("")
    click.echo("Notas:")
    click.echo("  - Importes DEL MES (parcial), no a origen.")
    click.echo("  - Fuente: mart.fact_seguimiento_categoria (mart de planificación).")
    click.echo("  - PRODUCCIÓN = VENTA (mart). TOTAL COSTES = CD + CI + CP.")
    click.echo("  - BENEFICIO = PRODUCCIÓN − TOTAL COSTES.")
    click.echo("  - DIFERENCIA = Real − Planificado.")
    click.echo("  - DESVIACIÓN % = Diferencia / Planificado × 100.")
    click.echo("")


# =============================================================================
# MÓDULO COMPRAS (Tandas C1/C2): proveedores, contratos, albaranes, facturas
# =============================================================================
@cli.command("build-compras")
def build_compras() -> None:
    """
    Construye el schema compras desde raw.* (documentos de compra).

    Ejecuta en orden los SQL de etl_sigrid/infrastructure/postgres/sql/compras:
      00_setup.sql       schema + funciones
      01_documentos.sql  contratos / albaranes / facturas (cabeceras + líneas)
      02_fact_linea.sql  hechos unificados a nivel de línea
      03_views.sql       vistas de negocio (consumo contrato, proveedores…)

    Requiere haber ingerido antes las tablas de compras (ingest tras añadir
    el bloque de config/tables_sigrid_compras_snippet.yaml al YAML).

    F-047: desde que `compras` entra en la carga nocturna esto es un STEP, y
    por eso deja fila en `_meta.etl_runs`. Antes ejecutaba el SQL en línea y su
    fecha de build no era consultable por SQL. Los conteos de control que este
    comando imprimía a mano viven ahora en `inspect-contrato-consumo` y en el
    propio `_meta.etl_runs`, que es donde alguien los puede volver a mirar.
    """
    settings = get_settings()
    pg = _get_pg()
    ejecucion = _arrancar_ejecucion(pg)
    _ejecutar_paso(BuildComprasStep(settings), pg, ejecucion)


@cli.command("reset-compras")
def reset_compras() -> None:
    """Elimina el schema compras. Lanza después `build-compras`."""
    pg = _get_pg()
    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS compras CASCADE")
        conn.commit()
    click.secho("Schema compras eliminado. Lanza `python main.py build-compras`.",
                fg="green")


@cli.command("inspect-contrato-consumo")
@click.option("--codigo", "codigo_contrato", type=str, default=None,
              help="Código de contrato (ej. CTSB25/0709)")
@click.option("--obra", "codigo_obra", type=str, default=None,
              help="Código de obra: muestra todos sus contratos")
@click.option("--umbral", type=float, default=None,
              help="Solo contratos con pct_consumido >= umbral (ej. 90)")
@click.option("--top", type=int, default=30, help="Máximo de filas")
def inspect_contrato_consumo(
    codigo_contrato: str | None, codigo_obra: str | None,
    umbral: float | None, top: int,
) -> None:
    """
    Consumo de contratos: contratado vs albaranado + proforma + facturado.

    \b
      python main.py inspect-contrato-consumo --codigo CTSB25/0709
      python main.py inspect-contrato-consumo --obra 0707
      python main.py inspect-contrato-consumo --umbral 90     # agotándose
    """
    pg = _get_pg()

    where, params = [], {}
    if codigo_contrato:
        where.append("codigo_contrato = %(ctr)s")
        params["ctr"] = codigo_contrato
    if codigo_obra:
        where.append("codigo_obra = %(obra)s")
        params["obra"] = codigo_obra
    if umbral is not None:
        where.append("pct_consumido >= %(umbral)s")
        params["umbral"] = umbral
    params["top"] = top
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
        SELECT codigo_contrato, codigo_obra, proveedor_nombre,
               importe_contratado, importe_albaranado,
               importe_certificado_proforma, importe_facturado,
               importe_albaranado_sin_facturar,
               importe_consumido, importe_disponible, pct_consumido
        FROM compras.v_pbi_contrato_consumo
        {where_sql}
        ORDER BY pct_consumido DESC NULLS LAST
        LIMIT %(top)s
    """
    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    if not rows:
        click.secho("Sin contratos para el filtro indicado.", fg="yellow")
        return

    click.secho("\n=== Consumo de contratos (importes sin IVA) ===\n",
                fg="cyan", bold=True)
    click.echo(
        f"  {'contrato':<14} {'obra':<6} {'proveedor':<26} "
        f"{'contratado':>13} {'albaranado':>13} {'proforma':>12} "
        f"{'facturado':>13} {'pdte.fact':>12} {'disponible':>13} {'%cons':>7}"
    )
    click.echo("  " + "-" * 135)

    def fmt(v):
        return f"{float(v):>13,.2f}" if v is not None else f"{'-':>13}"

    for r in rows:
        (ctr, obra, prv, contratado, alb, prof, fact,
         pdte, consumido, disp, pct) = r
        pct_str = f"{float(pct):>6.1f}%" if pct is not None else f"{'-':>7}"
        color = "red" if (pct is not None and float(pct) >= 90) else None
        linea = (
            f"  {(ctr or ''):<14} {(obra or ''):<6} {(prv or '')[:26]:<26} "
            f"{fmt(contratado)} {fmt(alb)} {fmt(prof)[:12]:>12} "
            f"{fmt(fact)} {fmt(pdte)[:12]:>12} {fmt(disp)} {pct_str}"
        )
        click.secho(linea, fg=color)
    click.echo("")


@cli.command("inspect-proveedores-obra")
@click.option("--obra", "codigo_obra", type=str, required=True,
              help="Código de obra (ej. 0707)")
@click.option("--anio", type=int, default=None, help="Año concreto")
@click.option("--top", type=int, default=20, help="Máximo de proveedores")
def inspect_proveedores_obra(
    codigo_obra: str, anio: int | None, top: int
) -> None:
    """
    Proveedores de una obra ordenados por facturación (sin IVA).

    \b
      python main.py inspect-proveedores-obra --obra 0707
      python main.py inspect-proveedores-obra --obra 0707 --anio 2026
    """
    pg = _get_pg()

    where = ["codigo_obra = %(obra)s"]
    params: dict = {"obra": codigo_obra, "top": top}
    if anio is not None:
        where.append("anio = %(anio)s")
        params["anio"] = anio

    sql = f"""
        SELECT proveedor_nombre, proveedor_cif, anio,
               facturado, albaranado, certificado_proforma,
               num_facturas, num_albaranes, num_contratos
        FROM compras.v_pbi_proveedor_obra
        WHERE {' AND '.join(where)}
        ORDER BY COALESCE(facturado, 0) DESC
        LIMIT %(top)s
    """
    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    if not rows:
        click.secho(f"Sin datos de compras para obra {codigo_obra}.", fg="yellow")
        return

    titulo = f"Proveedores de la obra {codigo_obra}"
    if anio:
        titulo += f" · año {anio}"
    click.secho(f"\n=== {titulo} (sin IVA, por facturación) ===\n",
                fg="cyan", bold=True)
    click.echo(
        f"  {'proveedor':<34} {'cif':<12} {'año':>5} "
        f"{'facturado':>14} {'albaranado':>14} {'proforma':>13} "
        f"{'#fac':>5} {'#alb':>5} {'#ctr':>5}"
    )
    click.echo("  " + "-" * 120)
    for r in rows:
        prv, cif, an, fac, alb, prof, nfac, nalb, nctr = r

        def fmt(v):
            return f"{float(v):>14,.2f}" if v is not None else f"{'-':>14}"

        click.echo(
            f"  {(prv or '')[:34]:<34} {(cif or ''):<12} {an or '':>5} "
            f"{fmt(fac)} {fmt(alb)} {fmt(prof)[:13]:>13} "
            f"{nfac or 0:>5} {nalb or 0:>5} {nctr or 0:>5}"
        )
    click.echo("")


@cli.command("inspect-albaranes-sin-facturar")
@click.option("--obra", "codigo_obra", type=str, default=None,
              help="Filtrar por código de obra")
@click.option("--proveedor", type=str, default=None,
              help="Filtrar por nombre de proveedor (LIKE)")
@click.option("--top", type=int, default=30, help="Máximo de líneas")
def inspect_albaranes_sin_facturar(
    codigo_obra: str | None, proveedor: str | None, top: int
) -> None:
    """
    Líneas de albarán/proforma con importe pendiente de facturar.

    \b
      python main.py inspect-albaranes-sin-facturar
      python main.py inspect-albaranes-sin-facturar --obra 0707
    """
    pg = _get_pg()

    where, params = [], {"top": top}
    if codigo_obra:
        where.append("codigo_obra = %(obra)s")
        params["obra"] = codigo_obra
    if proveedor:
        where.append("proveedor_nombre ILIKE %(prv)s")
        params["prv"] = f"%{proveedor}%"
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
        SELECT codigo_albaran, tipo_documento, fecha, codigo_obra,
               proveedor_nombre, codigo_contrato,
               importe, importe_pendiente_facturar, dias_desde_albaran
        FROM compras.v_pbi_albaranes_sin_facturar
        {where_sql}
        ORDER BY importe_pendiente_facturar DESC
        LIMIT %(top)s
    """
    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

        # Total pendiente con los mismos filtros (sin LIMIT)
        cur.execute(
            f"""
            SELECT COUNT(*), COALESCE(SUM(importe_pendiente_facturar), 0)
            FROM compras.v_pbi_albaranes_sin_facturar
            {where_sql}
            """,
            {k: v for k, v in params.items() if k != "top"},
        )
        n_total, suma_total = cur.fetchone()

    if not rows:
        click.secho("No hay líneas pendientes de facturar con ese filtro.",
                    fg="green")
        return

    click.secho("\n=== Albaranado sin facturar (sin IVA) ===\n",
                fg="cyan", bold=True)
    click.echo(
        f"  {'albarán':<14} {'tipo':<9} {'fecha':<11} {'obra':<6} "
        f"{'proveedor':<28} {'contrato':<14} "
        f"{'importe':>12} {'pendiente':>12} {'días':>5}"
    )
    click.echo("  " + "-" * 122)
    for r in rows:
        cod, tipo, fecha, obra, prv, ctr, imp, pdte, dias = r
        click.echo(
            f"  {(cod or ''):<14} {(tipo or ''):<9} {fecha!s:<11} "
            f"{(obra or ''):<6} {(prv or '')[:28]:<28} {(ctr or ''):<14} "
            f"{float(imp):>12,.2f} {float(pdte):>12,.2f} {dias or 0:>5}"
        )
    click.echo("  " + "-" * 122)
    click.echo(
        f"  TOTAL pendiente (todos los que cumplen el filtro): "
        f"{float(suma_total):,.2f} €  en {n_total:,} líneas"
    )
    click.echo("")


# =============================================================================
# MÓDULO RETENCIONES (Tanda R1): garantías retenidas a proveedores y de clientes
# =============================================================================
@cli.command("build-retenciones")
def build_retenciones() -> None:
    """
    Construye el schema retenciones desde raw.* (efectos pag/cob con retide).

    Ejecuta en orden los SQL de sql/retenciones:
      00_setup.sql        schema, función de fechas y catálogo de tipos
      01_movimientos.sql  un registro por efecto de retención (ambos sentidos)
      02_views.sql        vistas de saldo por entidad, obra, vivas y vencidas

    Requiere haber ingerido antes cob, pag y rec.

    F-047: igual que `build-compras`, ahora es un STEP y deja fila en
    `_meta.etl_runs`. El resumen por sentido que imprimía a mano se consulta
    con `inspect-retenciones`.
    """
    settings = get_settings()
    pg = _get_pg()
    ejecucion = _arrancar_ejecucion(pg)
    _ejecutar_paso(BuildRetencionesStep(settings), pg, ejecucion)


@cli.command("reset-retenciones")
def reset_retenciones() -> None:
    """Elimina el schema retenciones. Lanza después `build-retenciones`."""
    pg = _get_pg()
    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS retenciones CASCADE")
        conn.commit()
    click.secho(
        "Schema retenciones eliminado. Lanza `python main.py build-retenciones`.",
        fg="green",
    )


@cli.command("inspect-retenciones")
@click.option("--sentido", type=click.Choice(["PROVEEDOR", "CLIENTE"]),
              default=None, help="Filtrar por dirección de la retención")
@click.option("--obra", "codigo_obra", type=str, default=None,
              help="Código de obra (ej. 0707)")
@click.option("--entidad", type=str, default=None,
              help="Nombre de proveedor/cliente (búsqueda parcial)")
@click.option("--top", type=int, default=25, help="Máximo de filas")
def inspect_retenciones(
    sentido: str | None, codigo_obra: str | None,
    entidad: str | None, top: int,
) -> None:
    """
    Saldo de retenciones por entidad (proveedor o cliente).

    \b
      python main.py inspect-retenciones --sentido PROVEEDOR
      python main.py inspect-retenciones --entidad GARSAN
      python main.py inspect-retenciones --obra 0707
    """
    pg = _get_pg()

    if codigo_obra:
        # Vista por obra
        sql = """
            SELECT codigo_obra, nombre_obra,
                   retenido_a_proveedores, num_retenciones_proveedor,
                   retenido_por_cliente, num_retenciones_cliente,
                   posicion_neta
            FROM retenciones.v_pbi_retencion_obra
            WHERE codigo_obra = %(obra)s
        """
        with pg.connection() as conn, conn.cursor() as cur:
            cur.execute(sql, {"obra": codigo_obra})
            row = cur.fetchone()
        if not row:
            click.secho(f"Sin retenciones para la obra {codigo_obra}.", fg="yellow")
            return
        cod, nom, rp, nrp, rc, nrc, neta = row
        click.secho(f"\n=== Retenciones de la obra {cod} · {nom} ===\n",
                    fg="cyan", bold=True)
        click.echo(f"   Retenido a proveedores : {float(rp or 0):>16,.2f} € "
                   f"({nrp or 0} retenciones vivas)")
        click.echo(f"   Retenido por el cliente: {float(rc or 0):>16,.2f} € "
                   f"({nrc or 0} retenciones vivas)")
        click.echo("   " + "-" * 52)
        color = "green" if float(neta or 0) >= 0 else "red"
        click.secho(f"   Posición neta          : {float(neta or 0):>16,.2f} €",
                    fg=color, bold=True)
        click.echo("")
        return

    where, params = [], {"top": top}
    if sentido:
        where.append("sentido = %(sentido)s")
        params["sentido"] = sentido
    if entidad:
        where.append("entidad_nombre ILIKE %(ent)s")
        params["ent"] = f"%{entidad}%"
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
        SELECT sentido, entidad_nombre, entidad_cif,
               saldo_vivo, num_vivas, importe_liquidado,
               importe_vencido, num_vencidas
        FROM retenciones.v_pbi_retencion_entidad
        {where_sql}
        ORDER BY COALESCE(saldo_vivo, 0) DESC
        LIMIT %(top)s
    """
    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    if not rows:
        click.secho("Sin retenciones para el filtro indicado.", fg="yellow")
        return

    click.secho("\n=== Saldo de retenciones por entidad ===\n", fg="cyan", bold=True)
    click.echo(
        f"  {'sentido':<10} {'entidad':<34} {'cif':<12} "
        f"{'saldo vivo':>15} {'nº':>5} {'liquidado':>14} {'vencido':>14} {'nº':>4}"
    )
    click.echo("  " + "-" * 118)
    for s, ent, cif, sv, nv, liq, ven, nven in rows:
        color = "red" if (ven and float(ven) > 0) else None
        click.secho(
            f"  {s:<10} {(ent or '')[:34]:<34} {(cif or ''):<12} "
            f"{float(sv or 0):>15,.2f} {nv or 0:>5} {float(liq or 0):>14,.2f} "
            f"{float(ven or 0):>14,.2f} {nven or 0:>4}",
            fg=color,
        )
    click.echo("")


@cli.command("inspect-retenciones-vencidas")
@click.option("--sentido", type=click.Choice(["PROVEEDOR", "CLIENTE"]),
              default=None, help="Filtrar por dirección")
@click.option("--obra", "codigo_obra", type=str, default=None, help="Código de obra")
@click.option("--top", type=int, default=30, help="Máximo de filas")
def inspect_retenciones_vencidas(
    sentido: str | None, codigo_obra: str | None, top: int
) -> None:
    """
    Retenciones cuya fecha prevista de devolución ya pasó y siguen vivas.

    \b
      python main.py inspect-retenciones-vencidas --sentido CLIENTE
      python main.py inspect-retenciones-vencidas --obra 0707
    """
    pg = _get_pg()

    where, params = [], {"top": top}
    if sentido:
        where.append("sentido = %(sentido)s")
        params["sentido"] = sentido
    if codigo_obra:
        where.append("codigo_obra = %(obra)s")
        params["obra"] = codigo_obra
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT sentido, codigo_documento, fecha_documento, entidad_nombre,
                   codigo_obra, importe, fecha_prevista_devolucion,
                   dias_desde_vencimiento, antiguedad
            FROM retenciones.v_pbi_retenciones_vencidas
            {where_sql}
            ORDER BY importe DESC
            LIMIT %(top)s
            """, params)
        rows = cur.fetchall()

        cur.execute(
            f"""
            SELECT COUNT(*), COALESCE(SUM(importe), 0)
            FROM retenciones.v_pbi_retenciones_vencidas
            {where_sql}
            """, {k: v for k, v in params.items() if k != "top"})
        n_total, suma = cur.fetchone()

    if not rows:
        click.secho("No hay retenciones vencidas con ese filtro.", fg="green")
        return

    click.secho("\n=== Retenciones vencidas sin liquidar ===\n", fg="cyan", bold=True)
    click.echo(
        f"  {'sentido':<10} {'documento':<14} {'fecha':<11} {'entidad':<28} "
        f"{'obra':<7} {'importe':>13} {'prev.dev.':<11} {'antigüedad':<17}"
    )
    click.echo("  " + "-" * 120)
    for s, doc, fdoc, ent, obra, imp, fprev, dias, ant in rows:
        click.echo(
            f"  {s:<10} {(doc or ''):<14} {fdoc!s:<11} {(ent or '')[:28]:<28} "
            f"{(obra or ''):<7} {float(imp):>13,.2f} {fprev!s:<11} {ant:<17}"
        )
    click.echo("  " + "-" * 120)
    click.echo(f"  TOTAL vencido: {float(suma):,.2f} €  en {n_total:,} retenciones")
    click.echo("")


if __name__ == "__main__":
    cli()
