# scripts/compras_setup.py
"""
================================================================================
COMPRAS — script autónomo de ingesta + construcción del schema
================================================================================

Hace lo mismo que harían `ingest` (para las 9 tablas de compras) y
`build-compras`, pero SIN tocar `config/tables_sigrid.yaml` ni `main.py`.
Así el módulo de compras queda operativo hoy; la integración en el pipeline
oficial se hace después con calma.

Qué hace
--------
  1. Descubre las columnas reales de cada tabla en Sigrid
     (INFORMATION_SCHEMA vía sigrid-api), excluyendo texto largo/binario.
  2. Crea `raw.<tabla>` en Postgres con tipos mapeados y la puebla paginando
     por `ide` (COPY, rápido).
  3. Ejecuta los 4 SQL de etl_sigrid/infrastructure/postgres/sql/compras/.
  4. Muestra conteos de control.

Tablas que ingiere
------------------
  com, comlin, comprv, ctrpro, dca, dcapro, dcf, dcfpro, dcfprodes
  (ctr, prv y con ya los trae tu pipeline normal)

Uso
---
    python scripts/compras_setup.py --check      # solo comprueba conexiones
    python scripts/compras_setup.py --all        # ingesta + build  (recomendado)
    python scripts/compras_setup.py --ingest     # solo ingesta a raw
    python scripts/compras_setup.py --build      # solo los 4 SQL
    python scripts/compras_setup.py --all --tabla dcapro   # una tabla concreta

La primera ejecución completa tarda ~10-15 min (2,9 M de filas).
Es idempotente: cada tabla se recrea desde cero (DROP + CREATE + COPY).

Requisitos
----------
    pip install requests psycopg[binary] python-dotenv
El .env del proyecto debe tener las credenciales de sigrid-api y de Postgres
(el script acepta varios nombres de variable habituales; ver CONFIG).
================================================================================
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

try:
    import psycopg
except ImportError:
    print("ERROR: falta psycopg. pip install 'psycopg[binary]'", file=sys.stderr)
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


# =============================================================================
# CONFIG
# =============================================================================
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
SQL_DIR = (
    RAIZ_PROYECTO / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "compras"
)
SQL_FILES = ["00_setup.sql", "01_documentos.sql", "02_fact_linea.sql", "03_views.sql"]

# Tablas a ingerir: (tabla, page_size, columnas a excluir además de las de texto)
TABLAS: list[tuple[str, int, list[str]]] = [
    ("com",       20000, ["tex"]),
    ("comlin",    20000, []),
    ("comprv",    20000, []),
    ("ctrpro",    10000, ["tex", "desesp", "texcom"]),
    ("dca",       10000, ["tex", "emptex"]),
    ("dcapro",     5000, ["tex", "desesp", "texcom"]),
    ("dcf",       10000, ["tex", "emptex"]),
    ("dcfpro",     5000, ["tex", "desesp", "texcom", "serdesdat"]),
    ("dcfprodes", 20000, []),
]

# Tipos SQL Server cuyo contenido no queremos (texto largo / binario)
TIPOS_EXCLUIDOS = {
    "text", "ntext", "image", "xml", "varbinary", "binary",
    "geography", "geometry", "sql_variant", "timestamp", "rowversion",
}

# Mapeo de tipo SQL Server -> tipo Postgres
TIPOS_ENTEROS = {"int", "bigint", "smallint", "tinyint", "bit"}
TIPOS_REALES = {"float", "real", "decimal", "numeric", "money", "smallmoney"}


def _leer_dotenv() -> None:
    """Carga el .env del proyecto si python-dotenv está disponible."""
    if load_dotenv is None:
        return
    for candidato in (RAIZ_PROYECTO / ".env", Path.cwd() / ".env"):
        if candidato.exists():
            load_dotenv(candidato)
            return


def _env(*nombres: str, default: str | None = None) -> str | None:
    """Devuelve el primer valor de entorno no vacío entre varios nombres."""
    for n in nombres:
        v = os.environ.get(n)
        if v:
            return v
    return default


def cargar_config() -> dict[str, Any]:
    """Config tolerante a distintos nombres de variable en el .env."""
    _leer_dotenv()

    base_url = _env(
        "SIGRID_API_BASE_URL", "SIGRID_API__BASE_URL", "SIGRID_BASE_URL",
    )
    key = _env(
        "SIGRID_API_FUNCTION_KEY", "SIGRID_API__FUNCTION_KEY",
        "SIGRID_FUNCTION_KEY",
    )
    database = _env(
        "SIGRID_API_DATABASE", "SIGRID_API__DATABASE", "SIGRID_DATABASE",
        default="ruesma_rep",
    )

    pg_host = _env("PG_HOST", "POSTGRES_HOST", "POSTGRES__HOST", default="localhost")
    pg_port = _env("PG_PORT", "POSTGRES_PORT", "POSTGRES__PORT", default="5432")
    pg_db = _env("PG_DB", "PG_DATABASE", "POSTGRES_DB", "POSTGRES__DB")
    pg_user = _env("PG_USER", "POSTGRES_USER", "POSTGRES__USER", default="postgres")
    pg_pass = _env("PG_PASSWORD", "POSTGRES_PASSWORD", "POSTGRES__PASSWORD")

    faltan = [
        nombre for nombre, valor in [
            ("SIGRID_API_BASE_URL", base_url),
            ("SIGRID_API_FUNCTION_KEY", key),
            ("PG_DB / POSTGRES_DB", pg_db),
            ("PG_PASSWORD / POSTGRES_PASSWORD", pg_pass),
        ] if not valor
    ]
    if faltan:
        print("ERROR: no encuentro estas variables en el entorno/.env:",
              file=sys.stderr)
        for f in faltan:
            print(f"   - {f}", file=sys.stderr)
        print("\nVariables de entorno detectadas que parecen relevantes:",
              file=sys.stderr)
        for k in sorted(os.environ):
            if any(t in k.upper() for t in ("SIGRID", "PG", "POSTGRES")):
                tapado = "***" if any(
                    s in k.upper() for s in ("KEY", "PASSWORD", "SECRET")
                ) else os.environ[k]
                print(f"   {k} = {tapado}", file=sys.stderr)
        sys.exit(2)

    return {
        "url": base_url.rstrip("/") + "/api/sql/read",
        "headers": {"x-functions-key": key, "Content-Type": "application/json"},
        "database": database,
        "conninfo": (
            f"host={pg_host} port={pg_port} dbname={pg_db} "
            f"user={pg_user} password={pg_pass}"
        ),
        "pg_desc": f"{pg_user}@{pg_host}:{pg_port}/{pg_db}",
    }


# =============================================================================
# CLIENTE SIGRID
# =============================================================================
def sql_read(
    cfg: dict[str, Any], sql: str, params: list[Any] | None = None,
    max_rows: int = 100000, timeout_s: int = 180,
) -> tuple[list[str], list[list[Any]]]:
    """Ejecuta una SELECT contra sigrid-api. Devuelve (columnas, filas)."""
    body = {
        "database": cfg["database"],
        "sql": sql,
        "parameters": params or [],
        "timeout_seconds": timeout_s,
        "max_rows": max_rows,
    }
    resp = requests.post(
        cfg["url"], json=body, headers=cfg["headers"], timeout=timeout_s + 30
    )
    if resp.status_code != 200:
        raise RuntimeError(f"sigrid-api {resp.status_code}: {resp.text[:400]}")
    data = resp.json()
    if not data.get("ok", False):
        raise RuntimeError(f"sigrid-api error: {str(data)[:400]}")
    return data["columns"], data["rows"]


# =============================================================================
# INGESTA
# =============================================================================
def descubrir_columnas(
    cfg: dict[str, Any], tabla: str, excluir_extra: list[str]
) -> list[tuple[str, str]]:
    """
    Devuelve [(columna, tipo_postgres)] de la tabla, descartando texto largo,
    binarios y las columnas indicadas explícitamente.
    """
    cols, rows = sql_read(
        cfg,
        """
        SELECT COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = ?
        ORDER BY ORDINAL_POSITION
        """,
        [tabla],
        max_rows=1000,
    )
    idx_nombre = cols.index("COLUMN_NAME")
    idx_tipo = cols.index("DATA_TYPE")

    excluir = {c.lower() for c in excluir_extra}
    resultado: list[tuple[str, str]] = []
    for r in rows:
        nombre = str(r[idx_nombre])
        tipo = str(r[idx_tipo]).lower()
        if nombre.lower() in excluir or tipo in TIPOS_EXCLUIDOS:
            continue
        if tipo in TIPOS_ENTEROS:
            pg_tipo = "BIGINT"
        elif tipo in TIPOS_REALES:
            pg_tipo = "DOUBLE PRECISION"
        else:
            pg_tipo = "TEXT"
        resultado.append((nombre, pg_tipo))

    if not resultado:
        raise RuntimeError(f"No he podido leer columnas de dbo.{tabla}")
    if not any(c.lower() == "ide" for c, _ in resultado):
        raise RuntimeError(f"dbo.{tabla} no tiene columna 'ide'")
    return resultado


def crear_tabla_raw(
    conn: "psycopg.Connection", tabla: str, columnas: list[tuple[str, str]]
) -> None:
    """Recrea raw.<tabla> desde cero con las columnas descubiertas."""
    defs = ",\n    ".join(f'"{c}" {t}' for c, t in columnas)
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS raw")
        cur.execute(f'DROP TABLE IF EXISTS raw."{tabla}" CASCADE')
        cur.execute(
            f'CREATE TABLE raw."{tabla}" (\n    {defs},\n'
            f'    "_ingested_at" TIMESTAMP NOT NULL DEFAULT NOW()\n)'
        )
        cur.execute(f'CREATE INDEX ON raw."{tabla}" ("ide")')
    conn.commit()


def ingerir_tabla(
    cfg: dict[str, Any], conn: "psycopg.Connection",
    tabla: str, page_size: int, excluir: list[str],
) -> int:
    """Ingiere una tabla completa de Sigrid a raw paginando por ide."""
    t0 = time.monotonic()
    columnas = descubrir_columnas(cfg, tabla, excluir)
    nombres = [c for c, _ in columnas]
    crear_tabla_raw(conn, tabla, columnas)

    lista_cols = ", ".join(f"[{c}]" for c in nombres)
    copy_cols = ", ".join(f'"{c}"' for c in nombres)
    copy_sql = f'COPY raw."{tabla}" ({copy_cols}) FROM STDIN'

    total = 0
    ultimo_ide = -1
    paginas = 0
    while True:
        _, rows = sql_read(
            cfg,
            f"SELECT TOP {page_size} {lista_cols} FROM dbo.[{tabla}] "
            f"WHERE [ide] > ? ORDER BY [ide]",
            [ultimo_ide],
            max_rows=page_size,
        )
        if not rows:
            break

        with conn.cursor() as cur, cur.copy(copy_sql) as cp:
            for fila in rows:
                cp.write_row(fila)
        conn.commit()

        total += len(rows)
        paginas += 1
        idx_ide = nombres.index("ide")
        ultimo_ide = rows[-1][idx_ide]
        print(f"      pag {paginas:>4}  +{len(rows):>6}  total {total:>9,}",
              end="\r", flush=True)
        if len(rows) < page_size:
            break

    dur = time.monotonic() - t0
    print(f"   · raw.{tabla:<12} {total:>10,} filas  "
          f"{len(nombres):>3} cols  {dur:>6.1f}s        ")
    return total


# =============================================================================
# BUILD (los 4 SQL)
# =============================================================================
def construir_schema(conn: "psycopg.Connection") -> None:
    faltan = [f for f in SQL_FILES if not (SQL_DIR / f).exists()]
    if faltan:
        print(f"ERROR: faltan SQL en {SQL_DIR}: {faltan}", file=sys.stderr)
        print("       Copia la carpeta sql/compras/ del ZIP al proyecto.",
              file=sys.stderr)
        sys.exit(2)

    for nombre in SQL_FILES:
        t0 = time.monotonic()
        sql = (SQL_DIR / nombre).read_text(encoding="utf-8")
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
        except Exception as e:  # noqa: BLE001
            conn.rollback()
            print(f"   [FALLO ] {nombre}: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"   [OK     ] {nombre:<22} {time.monotonic() - t0:>7.1f}s")


def conteos(conn: "psycopg.Connection") -> None:
    tablas = ["contratos", "contrato_lineas", "albaranes", "albaran_lineas",
              "facturas", "factura_lineas", "fact_compras_linea"]
    with conn.cursor() as cur:
        for t in tablas:
            cur.execute(f"SELECT COUNT(*) FROM compras.{t}")
            fila = cur.fetchone()
            print(f"   · compras.{t:<20} {fila[0]:>10,} filas")
        # Desglose por tipo de documento, muy informativo
        cur.execute(
            "SELECT tipo_doc, COUNT(*), COALESCE(SUM(importe), 0) "
            "FROM compras.fact_compras_linea GROUP BY 1 ORDER BY 1"
        )
        print()
        print(f"   {'tipo_doc':<10} {'lineas':>10} {'importe (sin IVA)':>20}")
        print("   " + "-" * 42)
        for tipo, n, imp in cur.fetchall():
            print(f"   {tipo:<10} {n:>10,} {float(imp):>20,.2f}")


# =============================================================================
# MAIN
# =============================================================================
def main() -> None:
    ap = argparse.ArgumentParser(
        description="Ingesta y construcción del schema compras (autónomo)."
    )
    ap.add_argument("--check", action="store_true",
                    help="Solo comprueba conexiones y sale")
    ap.add_argument("--ingest", action="store_true", help="Ingesta raw")
    ap.add_argument("--build", action="store_true", help="Ejecuta los 4 SQL")
    ap.add_argument("--all", action="store_true", help="Ingesta + build")
    ap.add_argument("--tabla", default=None,
                    help="Solo esta tabla en la fase de ingesta")
    args = ap.parse_args()

    if not any([args.check, args.ingest, args.build, args.all]):
        ap.print_help()
        sys.exit(0)

    cfg = cargar_config()
    print("=" * 72)
    print("COMPRAS — ingesta + build (script autónomo)")
    print("=" * 72)
    print(f"  Sigrid   : {cfg['database']}")
    print(f"  Postgres : {cfg['pg_desc']}")
    print(f"  SQL dir  : {SQL_DIR}")
    print()

    # Comprobación de conexiones
    try:
        _, filas = sql_read(cfg, "SELECT 1 AS ok", max_rows=1)
        print(f"  [OK] sigrid-api responde ({filas})")
    except Exception as e:  # noqa: BLE001
        print(f"  [FALLO] sigrid-api: {e}", file=sys.stderr)
        sys.exit(2)

    try:
        with psycopg.connect(cfg["conninfo"]) as c, c.cursor() as cur:
            cur.execute("SELECT version()")
            v = cur.fetchone()[0]
        print(f"  [OK] Postgres: {v.split(',')[0]}")
    except Exception as e:  # noqa: BLE001
        print(f"  [FALLO] Postgres: {e}", file=sys.stderr)
        sys.exit(2)

    if args.check:
        print("\nComprobación completada.")
        return

    t_total = time.monotonic()
    with psycopg.connect(cfg["conninfo"]) as conn:
        if args.ingest or args.all:
            print("\n[1/2] Ingesta Sigrid -> raw")
            pendientes = TABLAS
            if args.tabla:
                pendientes = [t for t in TABLAS if t[0] == args.tabla]
                if not pendientes:
                    print(f"   Tabla '{args.tabla}' no está en la lista: "
                          f"{[t[0] for t in TABLAS]}", file=sys.stderr)
                    sys.exit(2)
            total = 0
            for tabla, page, excl in pendientes:
                try:
                    total += ingerir_tabla(cfg, conn, tabla, page, excl)
                except Exception as e:  # noqa: BLE001
                    print(f"   · raw.{tabla:<12} FALLO: {e}", file=sys.stderr)
            print(f"   TOTAL ingerido: {total:,} filas")

        if args.build or args.all:
            print("\n[2/2] Construyendo schema compras")
            construir_schema(conn)
            print()
            conteos(conn)

    print()
    print(f"Completado en {time.monotonic() - t_total:,.1f}s")
    print()
    print("Consultas de ejemplo:")
    print("  -- contratos agotándose")
    print("  SELECT codigo_contrato, codigo_obra, proveedor_nombre,")
    print("         importe_contratado, importe_consumido, pct_consumido")
    print("  FROM compras.v_pbi_contrato_consumo")
    print("  WHERE pct_consumido >= 90 ORDER BY pct_consumido DESC;")
    print()


if __name__ == "__main__":
    main()
