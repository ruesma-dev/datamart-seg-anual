"""
Suite de validación post-fixes del datamart Sigrid.

Valida que todos los fixes aplicados a lo largo de la sesión están operativos:

  1. Precisión decimal NUMERIC(20,6) en stg.presupuesto, stg.plan_mensual
     y mart.fact_seguimiento_mensual (precio, cantidad y derivados).
  2. Deduplicación con DISTINCT ON ide DESC en 06_presupuesto.sql.
  3. LAG estricto M-1 en reales de 08_plan_mensual.sql.
  4. Filtro pct_mes >= 0 en master de 08_plan_mensual.sql.

Cuadres validados contra Sigrid:
  - Obra 0696 KODAK mayo 2025:
      Real:  CD 557.669,99 | CI 134.818,41 | CP 55.121,36 | VR(CD) 515.152,84
      Plan:  CD 1.377.234,34 | CI 179.882,03 | CP 178.698,55 | VP(CD) 1.673.842,57
      Acum: CD 3.612.157,51 | CI 949.733,69 | CP 461.383,05 | Venta 4.320.708,94
  - Obra 0675 AHORRAMAS enero 2024:
      CD 131.380,11 | CI 43.618,72 | CP 26.522,12 | Total 201.520,95
  - Obra 0675 CI.03A.8 CAMION GRUA diciembre 2023: estorno -183,00 €

Ejecutar desde la raíz del proyecto:
    python validate_all_fixes.py
"""
from __future__ import annotations

import psycopg

from config.settings import get_settings


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def hr(title: str) -> None:
    print(f"\n{'=' * 110}\n  {title}\n{'=' * 110}")


def section(title: str) -> None:
    print(f"\n  {'─' * 100}\n  ▶ {title}\n  {'─' * 100}")


def query(cur, sql, params=None) -> list[tuple]:
    cur.execute(sql, params or ())
    cols = [c.name for c in cur.description]
    rows = cur.fetchall()
    if not rows:
        print("    (sin resultados)")
        return []
    widths = [
        max(len(str(c)), max((len(str(r[i])) for r in rows), default=0))
        for i, c in enumerate(cols)
    ]
    fmt = "    " + "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*cols))
    print("    " + "-" * (sum(widths) + 2 * (len(widths) - 1)))
    for r in rows:
        print(fmt.format(*[str(v) if v is not None else "" for v in r]))
    return rows


def check(label: str, expected, actual, *, tolerance: float = 0.0) -> None:
    """Muestra un OK/FAIL para una comparación numérica con tolerancia."""
    try:
        ok = abs(float(expected) - float(actual)) <= tolerance
    except (TypeError, ValueError):
        ok = expected == actual
    icon = "✅" if ok else "❌"
    print(f"    {icon} {label:<55}  esperado={expected!s:>20}  obtenido={actual!s:>20}")


# --------------------------------------------------------------------------- #
# Validations
# --------------------------------------------------------------------------- #
def v1_schema_precision(cur) -> None:
    """Fix 1: precisión NUMERIC(20,6) en todas las columnas relevantes."""
    hr("FIX 1 · Precisión decimal NUMERIC(20,6) en columnas de stg y mart")

    rows = query(cur, """
        SELECT
            table_schema,
            table_name,
            column_name,
            numeric_precision || ',' || numeric_scale AS precision
        FROM information_schema.columns
        WHERE (table_schema = 'stg'  AND table_name = 'presupuesto'
                AND column_name IN ('cantidad','precio'))
           OR (table_schema = 'stg'  AND table_name = 'plan_mensual'
                AND column_name IN ('can_mes','can_origen','precio_unitario'))
           OR (table_schema = 'mart' AND table_name = 'fact_seguimiento_mensual'
                AND column_name IN ('can_mes','can_origen','precio_unitario'))
        ORDER BY table_schema, table_name, column_name;
    """)

    print()
    expected_cols = 8
    cols_20_6 = sum(1 for r in rows if r[3] == '20,6')
    check("Columnas en NUMERIC(20,6)", f"{expected_cols} (todas)", f"{cols_20_6}/{expected_cols}")


def v2_dedup_distinct_on(cur) -> None:
    """Fix 2: deduplicación con DISTINCT ON en 06_presupuesto.sql."""
    hr("FIX 2 · Deduplicación DISTINCT ON ide DESC en stg.presupuesto")

    section("Duplicados por clave de negocio en stg.presupuesto (debe ser 0)")
    rows = query(cur, """
        SELECT COUNT(*) AS pares_duplicados FROM (
            SELECT obra_id, partida_id, ambito_id, fase_num
            FROM stg.presupuesto
            GROUP BY obra_id, partida_id, ambito_id, fase_num
            HAVING COUNT(*) > 1
        ) t;
    """)
    check("Sin duplicados en stg.presupuesto", 0, rows[0][0] if rows else None)

    section("Filas en mart de las 12 partidas previamente conflictivas")
    rows = query(cur, """
        SELECT
            o.codigo_obra,
            p.codigo_partida,
            m.escenario,
            m.anio_mes,
            COUNT(*) AS filas_mart,
            SUM(m.importe_origen)::numeric(18,2) AS suma_importe_origen
        FROM mart.fact_seguimiento_mensual m
        JOIN stg.obras    o ON o.obra_id    = m.obra_id
        JOIN stg.partidas p ON p.partida_id = m.partida_id
        WHERE (m.obra_id, m.partida_id) IN (
            (2313811, 369917), (2313811, 391180), (2313811, 398219), (2313811, 398220),
            (2409308, 377648), (2409308, 378364), (2409308, 387575),
            (2409308, 405799), (2409308, 408038),
            (2419057, 380069), (2419057, 380638),
            (2624507, 399400)
        )
          AND m.escenario IN ('Coste Real', 'Venta Real')
        GROUP BY o.codigo_obra, p.codigo_partida, m.escenario, m.anio_mes
        HAVING COUNT(*) > 1;
    """)
    check("Sin partidas duplicadas en mart", 0, len(rows))


def v3_cp4_precision(cur) -> None:
    """Fix 3: la cantidad de CP.4 obra 0696 ya tiene 6 decimales (0.000250)."""
    hr("FIX 3 · Cantidad NUMERIC(20,6) preserva porcentajes Sigrid (CP.4 obra 0696)")

    section("Trazabilidad raw → stg → mart de cantidad CP.4 master coste")
    rows = query(cur, """
        SELECT
            'raw.obrparpre' AS origen,
            rp.can::text   AS valor
        FROM raw.obrparpre rp
        JOIN stg.partidas p ON p.partida_id = rp.paride
        WHERE rp.obride = 2419057
          AND rp.amb    = 8
          AND rp.fas    = 7
          AND p.codigo_partida = 'CP.4'
        UNION ALL
        SELECT
            'stg.presupuesto' AS origen,
            sp.cantidad::text AS valor
        FROM stg.presupuesto sp
        JOIN stg.partidas p ON p.partida_id = sp.partida_id
        WHERE sp.obra_id     = 2419057
          AND sp.ambito_id   = 8
          AND sp.fase_num    = 7
          AND p.codigo_partida = 'CP.4'
        UNION ALL
        SELECT
            'mart.fact (max can_origen)' AS origen,
            MAX(can_origen)::text       AS valor
        FROM mart.fact_seguimiento_mensual m
        JOIN stg.partidas p ON p.partida_id = m.partida_id
        WHERE m.obra_id = 2419057
          AND m.escenario = 'Coste Planificado'
          AND p.codigo_partida = 'CP.4';
    """)

    print()
    stg_value = next((r[1] for r in rows if r[0] == 'stg.presupuesto'), None)
    check("cantidad stg.presupuesto CP.4", "0.000250", stg_value)


def v4_obra_0696_mes_mayo_2025(cur) -> None:
    """Fix 4: obra 0696 mayo 2025 cuadre mensual al céntimo con Sigrid."""
    hr("FIX 4 · Obra 0696 KODAK mayo 2025 — cuadre MENSUAL al céntimo")

    section("Agregado por escenario y categoría")
    rows = query(cur, """
        SELECT
            escenario,
            categoria,
            SUM(importe_mes)::numeric(18,2) AS importe_mes
        FROM mart.fact_seguimiento_mensual
        WHERE obra_id  = 2419057
          AND anio_mes = '2025-05-01'
        GROUP BY escenario, categoria
        ORDER BY escenario, categoria;
    """)

    expected = {
        ("Coste Real",         "CD"): 557669.99,
        ("Coste Real",         "CI"): 134818.41,
        ("Coste Real",         "CP"):  55121.36,
        ("Venta Real",         "CD"): 515152.84,
        ("Coste Planificado",  "CD"): 1377234.34,
        ("Coste Planificado",  "CI"): 179882.03,
        ("Coste Planificado",  "CP"): 178698.55,   # ← FIX cantidad
        ("Venta Planificada",  "CD"): 1673842.57,
    }

    print()
    actual = {(r[0], r[1]): float(r[2]) for r in rows}
    for (esc, cat), exp in expected.items():
        check(f"{esc} {cat} mes mayo 2025", exp, actual.get((esc, cat)), tolerance=0.50)


def v5_obra_0696_acumulado_mayo(cur) -> None:
    """Fix 5: filtro pct_mes >= 0 hace que el acumulado cuadre con columna Sigrid."""
    hr("FIX 5 · Obra 0696 KODAK mayo 2025 — cuadre ACUMULADO con columna Sigrid")

    section("Acumulado a origen del Plan en mayo 2025")
    rows = query(cur, """
        SELECT
            escenario,
            categoria,
            SUM(importe_origen)::numeric(18,2) AS plan_acum_origen
        FROM mart.fact_seguimiento_mensual
        WHERE obra_id   = 2419057
          AND anio_mes  = '2025-05-01'
          AND escenario IN ('Coste Planificado', 'Venta Planificada')
        GROUP BY escenario, categoria
        ORDER BY escenario, categoria;
    """)

    expected = {
        ("Coste Planificado", "CD"): 3612157.51,
        ("Coste Planificado", "CI"):  949733.69,
        ("Coste Planificado", "CP"):  461383.05,
        ("Venta Planificada", "CD"): 4320708.94,
    }

    print()
    actual = {(r[0], r[1]): float(r[2]) for r in rows}
    for (esc, cat), exp in expected.items():
        check(f"{esc} {cat} acum mayo 2025", exp, actual.get((esc, cat)), tolerance=1.00)


def v6_obra_0675_no_regresion(cur) -> None:
    """Fix 6: obra 0675 enero 2024 no ha regresado, estorno preservado."""
    hr("FIX 6 · Obra 0675 AHORRAMAS — no regresión y estorno preservado")

    section("Enero 2024 — cuadre Sigrid")
    rows = query(cur, """
        SELECT
            categoria,
            SUM(importe_mes)::numeric(18,2) AS importe_mes
        FROM mart.fact_seguimiento_mensual
        WHERE obra_id   = 2224835
          AND anio_mes  = '2024-01-01'
          AND escenario = 'Coste Real'
        GROUP BY categoria
        ORDER BY categoria;
    """)

    expected = {"CD": 131380.11, "CI": 43618.72, "CP": 26522.12}
    print()
    actual = {r[0]: float(r[1]) for r in rows}
    for cat, exp in expected.items():
        check(f"Coste Real {cat} enero 2024", exp, actual.get(cat), tolerance=0.50)

    section("Diciembre 2023 — estorno CI.03A.8 CAMION GRUA preservado")
    rows = query(cur, """
        SELECT
            p.codigo_partida,
            m.importe_mes::numeric(18,2) AS importe_mes,
            m.importe_origen::numeric(18,2) AS importe_origen
        FROM mart.fact_seguimiento_mensual m
        JOIN stg.partidas p ON p.partida_id = m.partida_id
        WHERE m.obra_id   = 2224835
          AND m.anio_mes  = '2023-12-01'
          AND m.escenario = 'Coste Real'
          AND p.codigo_partida = 'CI.03A.8';
    """)

    print()
    importe_mes = float(rows[0][1]) if rows else None
    check("Estorno CI.03A.8 dic 2023", -183.00, importe_mes, tolerance=0.01)


def v7_lag_estricto_huecos(cur) -> None:
    """Fix 7: LAG estricto M-1 — no hay estornos artificiales por huecos."""
    hr("FIX 7 · LAG estricto M-1 — sin estornos artificiales en huecos de cierres")

    section("Obra 0696 partidas SISTEMA MEDICION venta — caso del hueco fas=8")
    rows = query(cur, """
        SELECT
            p.codigo_partida,
            m.anio_mes,
            m.importe_mes::numeric(18,2) AS importe_mes
        FROM mart.fact_seguimiento_mensual m
        JOIN stg.partidas p ON p.partida_id = m.partida_id
        WHERE m.obra_id   = 2419057
          AND m.escenario = 'Venta Real'
          AND p.codigo_partida IN ('P4.19.04.01','P5.19.04.01')
          AND m.anio_mes BETWEEN '2025-04-01' AND '2025-06-01'
        ORDER BY p.codigo_partida, m.anio_mes;
    """)

    section("Si hay filas con importe_mes ≈ -95,20€, el LAG estricto NO está aplicado")
    estornos_artificiales = sum(
        1 for r in rows if abs(float(r[2]) + 95.20) < 0.01
    )
    print()
    check("Sin estornos artificiales de -95,20€", 0, estornos_artificiales)


def v8_powerbi_view_check(cur) -> None:
    """Las vistas Power BI siguen funcionando tras el rebuild."""
    hr("FIX 8 · Vistas Power BI operativas tras rebuild")

    rows = query(cur, """
        SELECT
            table_name,
            (SELECT COUNT(*)
             FROM information_schema.columns ic
             WHERE ic.table_schema = v.table_schema
               AND ic.table_name   = v.table_name) AS num_cols
        FROM information_schema.views v
        WHERE table_schema = 'mart'
          AND table_name LIKE 'v_pbi_%'
        ORDER BY table_name;
    """)

    print()
    check("Hay vistas v_pbi_ disponibles", True, len(rows) > 0)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    dsn = get_settings().postgres.conninfo

    print("\n" + "=" * 110)
    print("  SUITE DE VALIDACIÓN POST-FIXES — datamart Sigrid")
    print("=" * 110)

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        v1_schema_precision(cur)
        v2_dedup_distinct_on(cur)
        v3_cp4_precision(cur)
        v4_obra_0696_mes_mayo_2025(cur)
        v5_obra_0696_acumulado_mayo(cur)
        v6_obra_0675_no_regresion(cur)
        v7_lag_estricto_huecos(cur)
        v8_powerbi_view_check(cur)

    print(f"\n{'=' * 110}\n  ✓ FIN DE LA VALIDACIÓN\n{'=' * 110}\n")


if __name__ == "__main__":
    main()
