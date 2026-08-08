"""
scripts/refresh_presupuesto.py

Refresca SOLO stg.presupuesto desde raw.obrparpre, sin tocar el resto del
schema stg. Útil cuando se cambia la lógica de stg.presupuesto (p.ej. al
añadir la columna importe_oficial) y no se quiere correr `python main.py
stage` entero (~3h30).

Uso:
    python scripts/refresh_presupuesto.py

Lo que hace:
    1) Aplica 01_ddl.sql completo (idempotente; CREATE TABLE IF NOT EXISTS
       y los bloques de migración defensiva añaden la columna importe_oficial
       si no existe).
    2) Aplica 06_presupuesto.sql (TRUNCATE + INSERT con importe_oficial).

Cero impacto en el resto de stg: el DDL es idempotente y el INSERT solo
afecta a stg.presupuesto.
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

# Hack para importar config desde la raíz del proyecto sin instalar paquete
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import get_settings  # noqa: E402
from etl_sigrid.infrastructure.postgres.client_factory import build_postgres_client  # noqa: E402


def main() -> None:
    settings = get_settings()
    pg = build_postgres_client(settings)

    sql_dir = (
        Path(__file__).resolve().parents[1]
        / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "stg"
    )

    archivos = [
        ("01_ddl.sql",
         "DDL stg (idempotente; añade columna importe_oficial si no existe)"),
        ("06_presupuesto.sql",
         "Re-popular stg.presupuesto con importe_oficial = "
         "COALESCE(impcoe, can*pre)"),
    ]

    for nombre, descripcion in archivos:
        path = sql_dir / nombre
        if not path.exists():
            print(f"[ERROR] No existe: {path}")
            sys.exit(1)

        print(f"\n→ {nombre}  ({descripcion})")
        t0 = datetime.utcnow()
        try:
            pg.execute_sql_file(path)
        except Exception as e:  # noqa: BLE001
            print(f"[ERROR] {nombre} falló: {e}")
            sys.exit(1)
        dur = (datetime.utcnow() - t0).total_seconds()
        print(f"  OK ({dur:.2f}s)")

    # Verificación final: contar filas y confirmar columna
    filas = pg.count_rows("stg", "presupuesto")
    print(f"\nstg.presupuesto: {filas:,} filas")

    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='stg' AND table_name='presupuesto' "
            "  AND column_name='importe_oficial'"
        )
        exists = cur.fetchone() is not None

        if exists:
            cur.execute(
                "SELECT COUNT(*) FILTER (WHERE importe <> importe_oficial), "
                "       COUNT(*) "
                "FROM stg.presupuesto "
                "WHERE ambito_id IN (7, 11)"
            )
            diff, total = cur.fetchone()
            print(f"Columna importe_oficial: EXISTE")
            print(f"En VENTA (amb 7/11): {diff:,} filas con impcoe distinto de "
                  f"can*pre, sobre {total:,} totales "
                  f"({100*diff/max(total,1):.1f}%)")
        else:
            print("[ERROR] La columna importe_oficial NO se ha creado.")
            sys.exit(1)

    print("\n✓ Listo. Ahora puedes lanzar:")
    print("    python main.py reset-cierre")
    print("    python main.py build-cierre")


if __name__ == "__main__":
    main()
