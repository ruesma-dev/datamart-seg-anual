

# main.py
"""
CLI del ETL. Comandos:

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

import sys
from pathlib import Path

# Permite ejecutar `python main.py` desde la raíz del proyecto sin instalar el paquete
sys.path.insert(0, str(Path(__file__).resolve().parent))

import click  # noqa: E402

from config.settings import get_settings  # noqa: E402
from etl_sigrid.application.orchestrator import Orchestrator  # noqa: E402
from etl_sigrid.application.steps.build_cierre_step import BuildCierreStep  # noqa: E402
from etl_sigrid.application.steps.build_mart_step import BuildMartStep  # noqa: E402
from etl_sigrid.application.steps.build_stg_step import BuildStgStep  # noqa: E402
from etl_sigrid.application.steps.ingest_raw_step import IngestRawStep  # noqa: E402
from etl_sigrid.application.steps.load_excel_aux_step import LoadExcelAuxStep  # noqa: E402
from etl_sigrid.domain.entities import StepStatus  # noqa: E402
from etl_sigrid.infrastructure.logging_config import configure_logging, get_logger  # noqa: E402
from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient  # noqa: E402
from etl_sigrid.infrastructure.sigrid.sigrid_api_client import SigridApiClient  # noqa: E402


@click.group()
def cli() -> None:
    """ETL Sigrid → Postgres → Power BI (data mart seguimiento mensual)."""
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
        pendiente_pct, variacion_pct,
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
        fnum, fnm = r[16], r[17]
        ffuente, fvm, fvt = r[18], r[19], r[20]
        if mes_v not in meta_por_mes and fnum is not None:
            meta_por_mes[mes_v] = (fnum, fnm, ffuente, fvm, fvt)

    last_mes = None
    for r in rows:
        (mes, nm_mes, concepto, _orden,
         eo, ea, em,
         fi, fa, pi_imp, var,
         eo_pct, ea_pct, em_pct, pen_pct, var_pct,
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
                f"{'FINAL':>14}  "
                f"{'VAR MES':>14} {'%':>7}"
            )
            click.echo("  " + "-" * 175)
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
            f"{fmt(fi)}  "
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
def inspect_indirectos_detalle(
    obra_id: int | None, codigo_obra: str | None, anio_mes: str | None
) -> None:
    """
    Muestra el desglose de INDIRECTOS por (grupo CI × subcategoría) para
    una obra y mes. Replica las filas R27-R66 del Excel CONTROL DE GESTIÓN.

    Grupo = nivel 2 de ruta_capitulos (CI.MOI, CI.INFRA, CI.MAQ, CI.CONS).
    Subcategoría = nivel 3 (Jefe de obra, Vallado, Casetas, ...).
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
        ejecutado_origen, ejecutado_anterior, ejecutado_mes
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

    click.secho(
        f"\n=== Detalle INDIRECTOS · obra_id={obra_id} · mes={anio_mes} ===\n",
        fg="cyan", bold=True,
    )
    click.echo(
        f"  {'grupo':<32}  {'subcategoría':<42}  "
        f"{'EJEC MES':>14}  {'EJEC ANT':>14}  {'EJEC ORIG':>14}"
    )
    click.echo("  " + "-" * 124)

    last_grupo = None
    total_origen = 0.0
    for grupo_cod, subcat_cod, grupo_nm, subcat_nm, eo, ea, em in rows:
        if grupo_nm != last_grupo:
            if last_grupo is not None:
                click.echo("")
            last_grupo = grupo_nm
        # Mostrar el nombre principalmente; el código entre paréntesis para
        # trazabilidad en caso de homonimias.
        grupo_label = f"{(grupo_nm or '')[:24]} ({grupo_cod})"
        subcat_label = f"{(subcat_nm or '')[:34]} ({subcat_cod})"
        click.echo(
            f"  {grupo_label:<32}  {subcat_label:<42}  "
            f"{float(em):>14,.2f}  {float(ea):>14,.2f}  {float(eo):>14,.2f}"
        )
        total_origen += float(eo)

    click.echo("  " + "-" * 124)
    click.secho(
        f"  {'TOTAL INDIRECTOS':<76}  {'':>14}  {'':>14}  {total_origen:>14,.2f}",
        fg="cyan", bold=True,
    )
    click.echo("")
    click.echo("Validación: este total debe coincidir EXACTAMENTE con la fila")
    click.echo("INDIRECTOS de `inspect-cierre` (ejecutado origen).")
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


if __name__ == "__main__":
    cli()
