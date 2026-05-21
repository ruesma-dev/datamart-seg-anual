"""
Análisis obra 0696 KODAK (obra_id=2419057) — mayo 2025.

Compara las TRES versiones del importe que el mart preserva:
  1. importe_mes        = can * ROUND(pre, 2)  con LAG  -- "Sigrid-compatible"
  2. importe_mes_raw    = can * pre            con LAG  -- "raw"
  3. total_incurrido_mes = LAG sobre totinc             -- "campo directo Sigrid"

Ejecutar desde la raíz del proyecto:
    python inspect_0696_may25.py
"""
from __future__ import annotations

import psycopg

from config.settings import get_settings


OBRA_ID = 2419057
MES     = "2025-05-01"


def hr(t: str) -> None:
    print(f"\n{'=' * 100}\n  {t}\n{'=' * 100}")


def query(cur, sql, params=None) -> None:
    cur.execute(sql, params or ())
    cols = [c.name for c in cur.description]
    rows = cur.fetchall()
    if not rows:
        print("  (sin resultados)")
        return
    widths = [
        max(len(str(c)), max((len(str(r[i])) for r in rows), default=0))
        for i, c in enumerate(cols)
    ]
    fmt = "  " + "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*cols))
    print("  " + "-" * (sum(widths) + 2 * (len(widths) - 1)))
    for r in rows:
        print(fmt.format(*[str(v) if v is not None else "" for v in r]))


def main() -> None:
    # DSN viene de Settings().postgres.conninfo (no postgres_dsn)
    dsn = get_settings().postgres.conninfo

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:

        # Confirmar nombre de la obra
        cur.execute("""
            SELECT codigo_obra, nombre_obra
            FROM mart.v_pbi_dim_obra
            WHERE obra_id = %s;
        """, (OBRA_ID,))
        row = cur.fetchone()
        if row:
            codigo, nombre = row
            print(f"\nObra: {codigo} · {nombre}  (obra_id={OBRA_ID})")
        else:
            print(f"\nobra_id={OBRA_ID} no existe en mart.v_pbi_dim_obra")
            return
        print(f"Mes:  {MES}")

        hr("1) Las 3 versiones del importe agregadas por categoría/escenario")
        query(cur, """
            SELECT 
                escenario,
                categoria,
                COUNT(*)                                          AS n_part,
                SUM(importe_mes)::numeric(18,2)                   AS sigrid_compat_mes,
                SUM(importe_mes_raw)::numeric(18,2)               AS raw_mes,
                SUM(total_incurrido_mes)::numeric(18,2)           AS totinc_directo_mes,
                (SUM(importe_mes) - SUM(total_incurrido_mes))::numeric(18,2)
                                                                  AS diff_compat_vs_totinc
            FROM mart.fact_seguimiento_mensual
            WHERE obra_id   = %s
              AND anio_mes  = %s
              AND escenario IN ('Coste Real', 'Venta Real',
                                'Coste Planificado', 'Venta Planificada')
            GROUP BY escenario, categoria
            ORDER BY escenario, categoria;
        """, (OBRA_ID, MES))

        hr("2) Top 30 partidas con mayor diferencia Sigrid-compat vs totinc (Coste Real)")
        query(cur, """
            SELECT 
                codigo_partida,
                LEFT(descripcion_partida, 35) AS descripcion,
                categoria,
                importe_mes::numeric(18,2)                       AS sigrid_compat,
                importe_mes_raw::numeric(18,2)                   AS raw,
                total_incurrido_mes::numeric(18,2)               AS totinc_directo,
                (importe_mes - total_incurrido_mes)::numeric(18,2) AS diff
            FROM mart.fact_seguimiento_mensual
            WHERE obra_id   = %s
              AND anio_mes  = %s
              AND escenario = 'Coste Real'
              AND (importe_mes <> 0 OR total_incurrido_mes <> 0)
            ORDER BY ABS(importe_mes - total_incurrido_mes) DESC
            LIMIT 30;
        """, (OBRA_ID, MES))

        hr("3) Top 30 partidas con mayor diferencia (Venta Real)")
        query(cur, """
            SELECT 
                codigo_partida,
                LEFT(descripcion_partida, 35) AS descripcion,
                categoria,
                importe_mes::numeric(18,2)                       AS sigrid_compat,
                importe_mes_raw::numeric(18,2)                   AS raw,
                total_incurrido_mes::numeric(18,2)               AS totinc_directo,
                (importe_mes - total_incurrido_mes)::numeric(18,2) AS diff
            FROM mart.fact_seguimiento_mensual
            WHERE obra_id   = %s
              AND anio_mes  = %s
              AND escenario = 'Venta Real'
              AND (importe_mes <> 0 OR total_incurrido_mes <> 0)
            ORDER BY ABS(importe_mes - total_incurrido_mes) DESC
            LIMIT 30;
        """, (OBRA_ID, MES))

        hr("4) Total por escenario · qué método cuadra mejor con Sigrid")
        query(cur, """
            SELECT 
                escenario,
                SUM(importe_mes)::numeric(18,2)              AS metodo_sigrid_compat,
                SUM(importe_mes_raw)::numeric(18,2)          AS metodo_raw,
                SUM(total_incurrido_mes)::numeric(18,2)      AS metodo_totinc_directo
            FROM mart.fact_seguimiento_mensual
            WHERE obra_id   = %s
              AND anio_mes  = %s
              AND escenario IN ('Coste Real', 'Venta Real')
            GROUP BY escenario
            ORDER BY escenario;
        """, (OBRA_ID, MES))

        print("""
  Referencias Sigrid (cabecera 'Importe Parcial'):
    Coste Real total:   747.584,00 €
      CD:               557.669,99 €
      CI:               134.818,41 €
      CP:                55.095,60 €
    Venta Real total:   515.152,84 €

  Referencias Sigrid (cabecera 'Imp. Incurrido Pa' = LAG sobre totinc):
    PRESUPUESTO total:  692.487,05 €
      CD:               557.668,50 €
      CI:               134.818,45 €
""")


if __name__ == "__main__":
    main()