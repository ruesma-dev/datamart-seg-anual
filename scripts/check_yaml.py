# scripts/check_yaml.py
"""
Comprobación rápida del estado del proyecto tras el incidente del corrector.

Verifica dos cosas:
  1. Que config/tables_sigrid.yaml NO excluye columnas esenciales
     (sobre todo obrparpre.planif).
  2. Que raw.obrparpre sigue teniendo la columna planif con datos.

Uso:
    python scripts/check_yaml.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

RAIZ = Path(__file__).resolve().parent.parent
YAML_PATH = RAIZ / "config" / "tables_sigrid.yaml"

# Columnas que JAMÁS deben aparecer en exclude_columns
ESENCIALES = {
    "obrparpre": ["planif", "can", "pre", "amb", "fas", "obride", "paride"],
    "obrfasamb": ["plafec", "tex", "res", "fec"],
    "con":       ["cod", "res", "fec", "tip"],
    "obr":       ["decc", "decp", "deci", "cenide", "entide", "empide"],
    "condir":    ["dir", "dir1", "tel", "ele"],
    "prv":       ["cif", "raz"],
    "obrctr":    ["coegar", "fecreaini", "fecprefin"],
}


def check_yaml() -> bool:
    print("=" * 66)
    print("1. CONFIG — exclude_columns")
    print("=" * 66)
    if not YAML_PATH.exists():
        print(f"   ERROR: no encuentro {YAML_PATH}")
        return False

    doc = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
    por_tabla = {t["source_table"]: list(t.get("exclude_columns") or [])
                 for t in doc["tables"]}
    print(f"   {len(por_tabla)} tablas declaradas\n")

    problemas = []
    for tabla, criticas in ESENCIALES.items():
        excluidas = por_tabla.get(tabla)
        if excluidas is None:
            continue
        malas = [c for c in criticas if c in excluidas]
        if malas:
            problemas.append((tabla, malas))
            print(f"   [MAL]  {tabla:<12} excluye columnas esenciales: "
                  f"{', '.join(malas)}")
        else:
            print(f"   [OK]   {tabla:<12} {len(excluidas)} exclusiones, "
                  f"ninguna esencial")

    print()
    for tabla in ("dca", "dcf", "dcapro", "dcfpro", "ctrpro", "cob", "pag", "rec"):
        if tabla in por_tabla:
            print(f"   {tabla:<12} {len(por_tabla[tabla])} exclusiones")

    if problemas:
        print("\n   >>> El YAML está DAÑADO. Restaura la copia:")
        print("       Copy-Item config\\tables_sigrid.yaml.bak "
              "config\\tables_sigrid.yaml -Force")
        return False

    print("\n   >>> YAML correcto: ninguna columna esencial excluida.")
    return True


def check_raw() -> bool:
    print("\n" + "=" * 66)
    print("2. BASE DE DATOS — raw.obrparpre.planif")
    print("=" * 66)

    if load_dotenv is not None:
        for c in (RAIZ / ".env", Path.cwd() / ".env"):
            if c.exists():
                load_dotenv(c)
                break

    try:
        import psycopg
    except ImportError:
        print("   (psycopg no disponible; omito la comprobación de BBDD)")
        return True

    def env(*n, default=None):
        for x in n:
            v = os.environ.get(x)
            if v:
                return v
        return default

    conninfo = (
        f"host={env('PG_HOST', 'POSTGRES_HOST', default='localhost')} "
        f"port={env('PG_PORT', 'POSTGRES_PORT', default='5432')} "
        f"dbname={env('PG_DB', 'PG_DATABASE', 'POSTGRES_DB', default='seguimiento')} "
        f"user={env('PG_USER', 'POSTGRES_USER', default='postgres')} "
        f"password={env('PG_PASSWORD', 'POSTGRES_PASSWORD', default='')}"
    )

    try:
        with psycopg.connect(conninfo) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema='raw' AND table_name='obrparpre'
                  AND column_name='planif'
                """
            )
            existe = cur.fetchone()[0] > 0
            if not existe:
                print("   [MAL]  raw.obrparpre NO tiene la columna planif.")
                print("\n   >>> Hay que recargarla:")
                print("       python main.py ingest --table obrparpre --full")
                print("       python main.py stage")
                print("       python main.py build-mart")
                print("       python main.py reset-cierre")
                print("       python main.py build-cierre")
                return False

            cur.execute("SELECT COUNT(*) FROM raw.obrparpre")
            total = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM raw.obrparpre "
                "WHERE planif IS NOT NULL AND planif <> ''"
            )
            con_planif = cur.fetchone()[0]
            print(f"   [OK]   columna planif presente")
            print(f"          filas totales     : {total:,}")
            print(f"          filas con planif  : {con_planif:,}")

            if con_planif == 0:
                print("\n   [MAL]  la columna existe pero está vacía. Recarga:")
                print("       python main.py ingest --table obrparpre --full")
                return False

            # Estado de las tablas de los módulos nuevos
            print()
            for t in ("com", "ctrpro", "dca", "dcapro", "dcf", "dcfpro",
                      "cob", "pag", "rec"):
                cur.execute(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema='raw' AND table_name=%s", (t,)
                )
                if cur.fetchone()[0] == 0:
                    print(f"          raw.{t:<10} (aún no ingerida)")
                    continue
                cur.execute(f"SELECT COUNT(*) FROM raw.{t}")
                print(f"          raw.{t:<10} {cur.fetchone()[0]:>10,} filas")

    except Exception as e:  # noqa: BLE001
        print(f"   (no he podido conectar a Postgres: {e})")
        return True

    print("\n   >>> Base de datos correcta.")
    return True


if __name__ == "__main__":
    ok_yaml = check_yaml()
    ok_raw = check_raw()
    print("\n" + "=" * 66)
    if ok_yaml and ok_raw:
        print("TODO CORRECTO. Siguiente paso:")
        print("   python scripts\\fix_exclusiones_yaml.py --dry-run")
    else:
        print("HAY QUE CORREGIR ALGO ANTES DE SEGUIR (ver arriba).")
    print("=" * 66)
    sys.exit(0 if (ok_yaml and ok_raw) else 1)
