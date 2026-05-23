"""
Diagnóstico master vigente febrero 2026 — obras 0696 KODAK y 0704 SIROCO.

Reportado por el usuario:
  - 0696 mes febrero 2026: CD/Producción no cuadran, CI/CP sí cuadran con V22
  - 0704 mes febrero 2026: no cuadra (V11 CUAT FEB-26 se creó 04/03/2026, después del mes)
  - Resto de meses cuadran perfectamente

Hipótesis:
  - 0704: el pipeline aplica V6 CUAT OCT-25 para febrero porque V11 quedó
    fuera del filtro (fec_creacion > primer día del mes siguiente).
  - 0696: V22 CUAT FEB-26 (creada 27/02/2026) sí entra en el filtro, pero hay
    otra causa para el gap en CD/P (no en CI/CP).
"""
from __future__ import annotations

import psycopg

from config.settings import get_settings


OBRAS = [
    (2419057, "0696", "KODAK — 88+88 viv. Las Rozas"),
    (2537303, "0704", "SIROCO — 84 viv. Tomares Sevilla"),
]
MES_ANALISIS = "2026-02-01"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def hr(t: str) -> None:
    print(f"\n{'=' * 110}\n  {t}\n{'=' * 110}")


def section(t: str) -> None:
    print(f"\n  {'─' * 100}\n  ▶ {t}\n  {'─' * 100}")


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


# --------------------------------------------------------------------------- #
# Análisis por obra
# --------------------------------------------------------------------------- #
def analizar_obra(cur, obra_id: int, codigo: str, nombre: str) -> None:
    hr(f"OBRA {codigo} · {nombre} (obra_id={obra_id})")

    # 1) Versiones master COSTE
    section("Versiones master COSTE (amb=8) — todas, ordenadas descendente")
    query(cur, """
        SELECT
            fa.fas                                              AS version,
            stg.fn_sigrid_date_to_date(fa.fec)::text             AS fec_creacion,
            stg.fn_sigrid_date_to_date(fa.plafec)::text          AS plafec,
            COALESCE(NULLIF(TRIM(fa.tex), ''), '')              AS tex,
            COALESCE(NULLIF(TRIM(fa.res), ''), '')              AS res
        FROM raw.obrfasamb fa
        WHERE fa.obride = %s
          AND fa.amb    = 8
        ORDER BY fa.fas DESC;
    """, (obra_id,))

    # 2) Versiones master VENTA
    section("Versiones master VENTA (amb=11) — todas, ordenadas descendente")
    query(cur, """
        SELECT
            fa.fas                                              AS version,
            stg.fn_sigrid_date_to_date(fa.fec)::text             AS fec_creacion,
            stg.fn_sigrid_date_to_date(fa.plafec)::text          AS plafec,
            COALESCE(NULLIF(TRIM(fa.tex), ''), '')              AS tex,
            COALESCE(NULLIF(TRIM(fa.res), ''), '')              AS res
        FROM raw.obrfasamb fa
        WHERE fa.obride = %s
          AND fa.amb    = 11
        ORDER BY fa.fas DESC;
    """, (obra_id,))

    # 3) ¿Qué versión usa el MART para febrero 2026?
    section(f"¿Qué versión master usa el MART para {MES_ANALISIS}?")
    query(cur, """
        SELECT
            escenario,
            categoria,
            MIN(version_master)             AS version_min,
            MAX(version_master)             AS version_max,
            COUNT(DISTINCT version_master)  AS num_versiones_distintas,
            MIN(version_fec_creacion)::text AS fec_creacion_min,
            MAX(version_fec_creacion)::text AS fec_creacion_max,
            MIN(tipo_master)                AS tipo_master,
            COUNT(*)                        AS num_filas_mart
        FROM mart.fact_seguimiento_mensual
        WHERE obra_id   = %s
          AND anio_mes  = %s
          AND escenario IN ('Coste Planificado','Venta Planificada')
        GROUP BY escenario, categoria
        ORDER BY escenario, categoria;
    """, (obra_id, MES_ANALISIS))

    # 4) Importes mes febrero 2026
    section(f"Importes MES {MES_ANALISIS} en mart (por escenario × categoría)")
    query(cur, """
        SELECT
            escenario,
            categoria,
            SUM(importe_mes)::numeric(18,2)    AS importe_mes,
            SUM(importe_origen)::numeric(18,2) AS importe_acum_origen
        FROM mart.fact_seguimiento_mensual
        WHERE obra_id  = %s
          AND anio_mes = %s
        GROUP BY escenario, categoria
        ORDER BY escenario, categoria;
    """, (obra_id, MES_ANALISIS))

    # 5) Importes enero 2026 (mes anterior)
    section("Importes acumulados a ENERO 2026 (para poder derivar mes feb)")
    query(cur, """
        SELECT
            escenario,
            categoria,
            SUM(importe_mes)::numeric(18,2)    AS importe_mes_enero,
            SUM(importe_origen)::numeric(18,2) AS acum_origen_enero
        FROM mart.fact_seguimiento_mensual
        WHERE obra_id  = %s
          AND anio_mes = '2026-01-01'
          AND escenario IN ('Coste Planificado','Venta Planificada')
        GROUP BY escenario, categoria
        ORDER BY escenario, categoria;
    """, (obra_id,))

    # 6) Importes marzo 2026 (mes posterior, ya con V22/V11)
    section("Importes MES de marzo 2026 (ya con V22/V11 aplicada en pleno)")
    query(cur, """
        SELECT
            escenario,
            categoria,
            MIN(version_master)             AS version,
            MIN(version_fec_creacion)::text AS fec_creacion,
            SUM(importe_mes)::numeric(18,2) AS importe_mes_marzo
        FROM mart.fact_seguimiento_mensual
        WHERE obra_id  = %s
          AND anio_mes = '2026-03-01'
          AND escenario IN ('Coste Planificado','Venta Planificada')
        GROUP BY escenario, categoria
        ORDER BY escenario, categoria;
    """, (obra_id,))

    # 7) Buscar versiones cuyo `tex` contiene FEB-26
    section("Versiones cuyo comentario tex menciona FEB-26")
    query(cur, """
        SELECT
            fa.amb,
            fa.fas                                              AS version,
            stg.fn_sigrid_date_to_date(fa.fec)::text             AS fec_creacion,
            COALESCE(NULLIF(TRIM(fa.tex), ''), '')              AS tex
        FROM raw.obrfasamb fa
        WHERE fa.obride = %s
          AND fa.amb    IN (8, 11)
          AND fa.tex ILIKE %s
        ORDER BY fa.amb, fa.fas DESC;
    """, (obra_id, '%FEB-26%'))


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    dsn = get_settings().postgres.conninfo

    print("\n" + "=" * 110)
    print(f"  DIAGNÓSTICO MASTER VIGENTE FEBRERO 2026")
    print("=" * 110)

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        for obra_id, codigo, nombre in OBRAS:
            analizar_obra(cur, obra_id, codigo, nombre)

    print(f"\n{'=' * 110}")
    print("  ✓ FIN DEL DIAGNÓSTICO")
    print(f"{'=' * 110}\n")


if __name__ == "__main__":
    main()
