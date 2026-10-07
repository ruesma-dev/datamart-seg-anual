# etl_sigrid/infrastructure/postgres/compras_reset_sql.py
"""
F-067 · El SQL de `python main.py reset-compras`. **Solo construye texto.**

Hasta el 2026-10-06 el comando hacía `DROP SCHEMA ... CASCADE` sobre `compras`,
y eso se habría llevado las dos tablas PERSISTENTES de la foto diaria de
estados (`TABLAS_PERSISTENTES` del dominio): historia que no existe en Sigrid y
no se puede recuperar. Decisión del humano (delegada en el líder, opción a):
`reset-compras` borra TODO lo demás del esquema —vistas, tablas y funciones,
en ese orden y con `CASCADE`— y NUNCA esas dos tablas ni sus índices, que
mueren solo con su tabla. Después, `build-compras` lo reconstruye todo y la
foto sigue donde estaba.

Por qué es seguro el `CASCADE`: las dos tablas no dependen de ningún objeto de
`compras` (ni claves foráneas, ni funciones en sus `CHECK` o `DEFAULT`), así
que borrar los demás no las arrastra. La única vista que las lee,
`compras.v_estado_documentos`, se borra y `build-compras` la recrea.
"""

from __future__ import annotations

from etl_sigrid.domain.historial_estados import TABLAS_PERSISTENTES

_CONSERVADAS = ", ".join(f"'{tabla}'" for tabla in TABLAS_PERSISTENTES)

SQL_RESET_COMPRAS = f"""
DO $$
DECLARE
    r RECORD;
BEGIN
    -- 1 · Las vistas (y materializadas), primero: dependen de las tablas.
    FOR r IN
        SELECT c.relname, c.relkind
        FROM   pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE  n.nspname = 'compras' AND c.relkind IN ('v', 'm')
    LOOP
        EXECUTE format('DROP %s IF EXISTS compras.%I CASCADE',
                       CASE r.relkind WHEN 'v' THEN 'VIEW' ELSE 'MATERIALIZED VIEW' END,
                       r.relname);
    END LOOP;

    -- 2 · Las tablas, MENOS las persistentes de la foto diaria.
    FOR r IN
        SELECT c.relname
        FROM   pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE  n.nspname = 'compras' AND c.relkind IN ('r', 'p')
          AND  c.relname NOT IN ({_CONSERVADAS})
    LOOP
        EXECUTE format('DROP TABLE IF EXISTS compras.%I CASCADE', r.relname);
    END LOOP;

    -- 3 · Las funciones: `build-compras` las recrea en `00_setup.sql`.
    FOR r IN
        SELECT p.oid::regprocedure AS firma
        FROM   pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE  n.nspname = 'compras'
    LOOP
        EXECUTE format('DROP FUNCTION IF EXISTS %s CASCADE', r.firma);
    END LOOP;
END $$;
"""
