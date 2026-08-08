

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
"""

from __future__ import annotations

import platform
import sys
from pathlib import Path

# Permite ejecutar `python main.py` desde la raíz del proyecto sin instalar el paquete
sys.path.insert(0, str(Path(__file__).resolve().parent))

import click  # noqa: E402

from config.settings import get_build_info, get_settings  # noqa: E402
from etl_sigrid.application.orchestrator import Orchestrator  # noqa: E402
from etl_sigrid.application.steps.build_cierre_step import BuildCierreStep  # noqa: E402
from etl_sigrid.application.steps.build_maestros_step import BuildMaestrosStep  # noqa: E402
from etl_sigrid.application.steps.build_mart_step import BuildMartStep  # noqa: E402
from etl_sigrid.application.steps.build_stg_step import BuildStgStep  # noqa: E402
from etl_sigrid.application.steps.ingest_raw_step import IngestRawStep  # noqa: E402
from etl_sigrid.application.steps.load_excel_aux_step import LoadExcelAuxStep  # noqa: E402
from etl_sigrid.domain.entities import StepStatus  # noqa: E402
from etl_sigrid.infrastructure.logging_config import configure_logging, get_logger  # noqa: E402
from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient  # noqa: E402
from etl_sigrid.infrastructure.sigrid.sigrid_api_client import SigridApiClient  # noqa: E402


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
    """Construye el cliente Postgres con auto-bootstrap perezoso."""
    settings = get_settings()
    return PostgresClient(
        conninfo=settings.postgres.conninfo,
        admin_conninfo=settings.postgres.admin_conninfo,
        target_db=settings.postgres.db,
    )


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
    step = IngestRawStep(
        settings,
        only_table=table,
        full_refresh=full_refresh,
        stop_on_error=stop_on_error,
    )
    result = step.run()
    _print_result(result)
    if result.status == StepStatus.FAILED:
        sys.exit(1)


@cli.command("load-aux")
def load_aux() -> None:
    """Carga Excels auxiliares → aux.* (pendiente)."""
    settings = get_settings()
    result = LoadExcelAuxStep(settings).run()
    _print_result(result)


@cli.command("stage")
def stage() -> None:
    """Materializa stg.* desde raw.* (tipado, derivaciones, sin lógica de negocio)."""
    settings = get_settings()
    result = BuildStgStep(settings).run()
    _print_result(result)
    if result.status == StepStatus.FAILED:
        sys.exit(1)


@cli.command("build-mart")
def build_mart() -> None:
    """
    Materializa mart.fact_seguimiento_mensual desde stg.plan_mensual.

    Produce una fila por (obra × partida × mes × escenario), con cuatro
    escenarios: Coste Real, Venta Real, Coste Planificado, Venta Planificada.

    Para los escenarios planificados, escoge automáticamente la versión del
    master vigente en cada mes (la más reciente con fec_creacion ≤ mes).
    """
    settings = get_settings()
    result = BuildMartStep(settings).run()
    _print_result(result)
    if result.status == StepStatus.FAILED:
        sys.exit(1)


@cli.command("run-all")
@click.option("--full", "full_refresh", is_flag=True, default=False)
def run_all(full_refresh: bool) -> None:
    """Ejecuta el pipeline completo en orden: ingest → load_aux → stage → build_mart."""
    settings = get_settings()
    steps = [
        IngestRawStep(settings, full_refresh=full_refresh),
        LoadExcelAuxStep(settings),
        BuildStgStep(settings),
        BuildMartStep(settings),
    ]
    orchestrator = Orchestrator(steps)
    results = orchestrator.run_all()

    click.echo("")
    click.secho("=== RESUMEN ===", fg="cyan", bold=True)
    for r in results:
        _print_result(r)

    failed = sum(1 for r in results if r.status == StepStatus.FAILED)
    if failed:
        sys.exit(1)


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
    result = BuildCierreStep(settings).run()
    _print_result(result)
    if result.status == StepStatus.FAILED:
        sys.exit(1)


@cli.command("build-maestros")
def build_maestros() -> None:
    """
    Materializa el schema `maestro` (catálogos para consulta externa):
    maestro.obras, maestro.proveedores y maestro.proveedores_obra.

    INDEPENDIENTE del seguimiento/cierre. Solo lee de raw.*. Requiere que la
    ingesta (raw) esté hecha; no necesita stage ni mart.
    """
    settings = get_settings()
    result = BuildMaestrosStep(settings).run()
    _print_result(result)
    if result.status == StepStatus.FAILED:
        sys.exit(1)


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
    """
    import time as _time

    pg = _get_pg()
    sql_dir = (
        Path(__file__).resolve().parent
        / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "compras"
    )
    archivos = [
        "00_setup.sql",
        "01_documentos.sql",
        "02_fact_linea.sql",
        "03_views.sql",
    ]

    faltan = [f for f in archivos if not (sql_dir / f).exists()]
    if faltan:
        click.secho(f"Faltan archivos SQL en {sql_dir}: {faltan}", fg="red", err=True)
        sys.exit(2)

    total_t0 = _time.monotonic()
    for nombre in archivos:
        t0 = _time.monotonic()
        sql = (sql_dir / nombre).read_text(encoding="utf-8")
        try:
            with pg.connection() as conn, conn.cursor() as cur:
                cur.execute(sql)
                conn.commit()
        except Exception as e:  # noqa: BLE001
            click.secho(f"[FALLO ] {nombre}: {e}", fg="red", err=True)
            sys.exit(1)
        click.secho(
            f"[OK     ] {nombre:<22} {_time.monotonic() - t0:>7.1f}s", fg="green"
        )

    # Conteos de control
    with pg.connection() as conn, conn.cursor() as cur:
        for tabla in ("contratos", "contrato_lineas", "albaranes",
                      "albaran_lineas", "facturas", "factura_lineas",
                      "fact_compras_linea"):
            cur.execute(f"SELECT COUNT(*) FROM compras.{tabla}")
            row = cur.fetchone()
            click.echo(f"   · compras.{tabla}: {row[0]:,} filas")

    click.secho(
        f"build-compras completado en {_time.monotonic() - total_t0:,.1f}s",
        fg="green", bold=True,
    )


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
    """
    import time as _time

    pg = _get_pg()
    sql_dir = (
        Path(__file__).resolve().parent
        / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "retenciones"
    )
    archivos = ["00_setup.sql", "01_movimientos.sql", "02_views.sql"]

    faltan = [f for f in archivos if not (sql_dir / f).exists()]
    if faltan:
        click.secho(f"Faltan archivos SQL en {sql_dir}: {faltan}", fg="red", err=True)
        sys.exit(2)

    total_t0 = _time.monotonic()
    for nombre in archivos:
        t0 = _time.monotonic()
        sql = (sql_dir / nombre).read_text(encoding="utf-8")
        try:
            with pg.connection() as conn, conn.cursor() as cur:
                cur.execute(sql)
                conn.commit()
        except Exception as e:  # noqa: BLE001
            click.secho(f"[FALLO ] {nombre}: {e}", fg="red", err=True)
            sys.exit(1)
        click.secho(
            f"[OK     ] {nombre:<22} {_time.monotonic() - t0:>7.1f}s", fg="green"
        )

    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM retenciones.tipos")
        click.echo(f"   · retenciones.tipos: {cur.fetchone()[0]:,} filas")
        cur.execute("SELECT COUNT(*) FROM retenciones.movimientos")
        click.echo(f"   · retenciones.movimientos: {cur.fetchone()[0]:,} filas")
        cur.execute(
            """
            SELECT sentido, num_vivas, saldo_vivo, num_vencidas,
                   importe_vencido, sin_obra_asignada
            FROM retenciones.v_pbi_retencion_resumen ORDER BY sentido
            """
        )
        click.echo("")
        click.echo(f"   {'sentido':<10} {'vivas':>8} {'saldo vivo':>16} "
                   f"{'vencidas':>9} {'imp.vencido':>16} {'sin obra':>9}")
        click.echo("   " + "-" * 72)
        for s, nv, sv, nven, iven, so in cur.fetchall():
            click.echo(
                f"   {s:<10} {nv or 0:>8,} {float(sv or 0):>16,.2f} "
                f"{nven or 0:>9,} {float(iven or 0):>16,.2f} {so or 0:>9,}"
            )

    click.secho(
        f"\nbuild-retenciones completado en {_time.monotonic() - total_t0:,.1f}s",
        fg="green", bold=True,
    )


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
