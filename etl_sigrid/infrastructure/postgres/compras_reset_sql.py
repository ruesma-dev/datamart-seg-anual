# etl_sigrid/infrastructure/postgres/compras_reset_sql.py
"""
F-067 · F-132 · El SQL de `python main.py reset-compras`. **Solo construye texto.**

Vacía el esquema `compras` SIN tirarlo: borra sus vistas, tablas y funciones,
en ese orden y con `CASCADE`, y después `build-compras` lo reconstruye todo.

HISTORIA. Hasta el 2026-10-06 el comando hacía `DROP SCHEMA ... CASCADE`. F-067
lo cambió para conservar las dos tablas de la foto diaria de estados, que no se
reconstruían (decisión del humano, delegada en el líder, opción a): borraba
todo lo demás. F-132 (Fase B, rama BORRAR, decisión del humano del 2026-10-09)
retiró la foto y con ella la lista de conservadas (R26): ya no queda en
`compras` ninguna tabla que no se reconstruya, así que se borran TODAS. Se
mantiene el no tirar el esquema (R26: «sin `DROP SCHEMA`»).
"""

from __future__ import annotations

SQL_RESET_COMPRAS = """
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

    -- 2 · Las tablas, TODAS: desde F-132 ninguna de `compras` es persistente.
    FOR r IN
        SELECT c.relname
        FROM   pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE  n.nspname = 'compras' AND c.relkind IN ('r', 'p')
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
