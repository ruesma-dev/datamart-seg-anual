# patches/main_py_patch_compras.py
# ============================================================================
# TANDA C1/C2 — Comandos del módulo COMPRAS para main.py
#
# INSTRUCCIONES: copia TODO el bloque de abajo (desde "@cli.command" hasta el
# final, SIN incluir esta cabecera) y pégalo en tu main.py real, justo ANTES
# de la línea:      if __name__ == "__main__":
#
# No modifica nada existente: solo añade 5 comandos nuevos.
# Requiere los SQL en etl_sigrid/infrastructure/postgres/sql/compras/.
# ============================================================================


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
