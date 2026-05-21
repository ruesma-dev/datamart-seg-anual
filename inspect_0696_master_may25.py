"""
Análisis master coste y venta — Obra 0696 KODAK mayo 2025.

Compara el Plan del mart contra los acumulados que se ven en Sigrid.

Ejecutar desde la raíz del proyecto:
    python inspect_0696_master_may25.py
"""
from __future__ import annotations

import psycopg

from config.settings import get_settings


OBRA_ID = 2419057
MES     = "2025-05-01"


def hr(t: str) -> None:
    print(f"\n{'=' * 110}\n  {t}\n{'=' * 110}")


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
    dsn = get_settings().postgres.conninfo

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:

        cur.execute("""
            SELECT codigo_obra, nombre_obra
            FROM mart.v_pbi_dim_obra
            WHERE obra_id = %s;
        """, (OBRA_ID,))
        row = cur.fetchone()
        codigo, nombre = row
        print(f"\nObra: {codigo} · {nombre}  (obra_id={OBRA_ID})")
        print(f"Mes:  {MES}")

        hr("1) Qué versión master se está usando para mayo 2025 (Coste Planificado)")
        query(cur, """
            SELECT 
                escenario,
                categoria,
                COUNT(*)                              AS num_filas,
                COUNT(DISTINCT version_master)        AS num_versiones,
                MIN(version_master)                   AS version_min,
                MAX(version_master)                   AS version_max,
                MIN(tipo_master)                      AS tipo_master,
                MIN(version_fec_creacion)::date       AS fec_creacion_min,
                MAX(version_fec_creacion)::date       AS fec_creacion_max,
                SUM(importe_mes)::numeric(18,2)       AS importe_mes_total,
                SUM(importe_origen)::numeric(18,2)    AS importe_origen_total
            FROM mart.fact_seguimiento_mensual
            WHERE obra_id   = %s
              AND anio_mes  = %s
              AND escenario IN ('Coste Planificado', 'Venta Planificada')
            GROUP BY escenario, categoria
            ORDER BY escenario, categoria;
        """, (OBRA_ID, MES))

        hr("2) Acumulados a origen del Plan en mayo 2025 (para comparar con cabecera Sigrid)")
        query(cur, """
            SELECT 
                escenario,
                categoria,
                SUM(importe_origen)::numeric(18,2)    AS origen_sigrid_compat,
                SUM(importe_origen_raw)::numeric(18,2) AS origen_raw
            FROM mart.fact_seguimiento_mensual
            WHERE obra_id   = %s
              AND anio_mes  = %s
              AND escenario IN ('Coste Planificado', 'Venta Planificada')
            GROUP BY escenario, categoria
            ORDER BY escenario, categoria;
        """, (OBRA_ID, MES))

        hr("3) Top 30 partidas Coste Planificado mayo 2025 (orden por importe_mes)")
        query(cur, """
            SELECT 
                codigo_partida,
                LEFT(descripcion_partida, 35) AS descripcion,
                categoria,
                importe_mes::numeric(18,2)              AS plan_mes,
                importe_origen::numeric(18,2)           AS plan_origen,
                importe_mes_raw::numeric(18,2)          AS plan_mes_raw,
                (importe_mes - importe_mes_raw)::numeric(18,2) AS diff_round
            FROM mart.fact_seguimiento_mensual
            WHERE obra_id   = %s
              AND anio_mes  = %s
              AND escenario = 'Coste Planificado'
              AND importe_mes <> 0
            ORDER BY importe_mes DESC
            LIMIT 30;
        """, (OBRA_ID, MES))

        hr("4) Detalle TODAS las CP de mayo 2025 (para investigar gap de 83,71 €)")
        query(cur, """
            SELECT 
                codigo_partida,
                LEFT(descripcion_partida, 35) AS descripcion,
                version_master,
                tipo_master,
                importe_mes::numeric(18,2)              AS plan_mes,
                importe_origen::numeric(18,2)           AS plan_origen,
                importe_mes_raw::numeric(18,2)          AS plan_mes_raw
            FROM mart.fact_seguimiento_mensual
            WHERE obra_id   = %s
              AND anio_mes  = %s
              AND escenario = 'Coste Planificado'
              AND categoria = 'CP'
            ORDER BY ABS(importe_mes) DESC;
        """, (OBRA_ID, MES))

        hr("5) Acumulados Plan en MESES alrededor (abril/mayo/junio 2025) por categoría")
        query(cur, """
            SELECT 
                anio_mes,
                categoria,
                SUM(importe_mes)::numeric(18,2)       AS plan_mes,
                SUM(importe_origen)::numeric(18,2)    AS plan_acum_origen
            FROM mart.fact_seguimiento_mensual
            WHERE obra_id   = %s
              AND anio_mes  IN ('2025-04-01','2025-05-01','2025-06-01')
              AND escenario = 'Coste Planificado'
            GROUP BY anio_mes, categoria
            ORDER BY anio_mes, categoria;
        """, (OBRA_ID,))

        hr("6) MASTER VENTA — qué versión se aplica en mayo 2025")
        query(cur, """
            SELECT 
                escenario,
                COUNT(*)                              AS num_filas,
                COUNT(DISTINCT version_master)        AS num_versiones,
                MIN(version_master)                   AS version_min,
                MAX(version_master)                   AS version_max,
                MIN(tipo_master)                      AS tipo_master,
                MIN(version_fec_creacion)::date       AS fec_creacion,
                SUM(importe_mes)::numeric(18,2)       AS importe_mes_total
            FROM mart.fact_seguimiento_mensual
            WHERE obra_id   = %s
              AND anio_mes  = %s
              AND escenario = 'Venta Planificada'
            GROUP BY escenario;
        """, (OBRA_ID, MES))

        print("""
  Referencias Sigrid (Image 2: Master COSTE Versión 7 [Feb-25 cuatrimestral]):
    Acumulado mayo 2025 (col 7):
      CD: 3.612.157,51 €
      CI:   949.733,69 €
      CP:   461.383,05 €
    Acumulado abril 2025 (col 6):
      CD: 2.234.923,29 €
      CI:   769.851,77 €
      CP:   282.684,50 €
    Mes mayo 2025 (derivado = col 7 - col 6):
      CD: 1.377.234,22 €  ← cuadra con Power BI 1.377.234,34 € (+0,12 redondeo)
      CI:   179.881,92 €  ← cuadra con Power BI 179.882,03 € (+0,11 redondeo)
      CP:   178.698,55 €  ← gap +83,71 € con Power BI 178.782,26 €

  Referencias Sigrid (Image 3: Master VENTA Versión 12 [Jun-25 cuatrimestral]):
    ATENCIÓN: V12 se creó el 27/06/2025, DESPUÉS de mayo 2025.
    Para mayo 2025 nuestro mart usa la versión vigente entonces (probablemente V7 de venta).
""")


if __name__ == "__main__":
    main()
