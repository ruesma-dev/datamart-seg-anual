-- infra/sql/03_diagnostico.sql
--
-- SOLO LECTURA. No crea, no borra y no modifica nada. Se puede ejecutar
-- cuantas veces haga falta y contra un servidor en producción.
--
--   psql "host=<servidor> dbname=postgres user=<admin> sslmode=require" \
--        -f infra/sql/03_diagnostico.sql
--
-- Responde a tres preguntas del runbook:
--   1. ¿Cuánto espacio queda de los 32 GB compartidos? (puerta de T13: si
--      quedan menos de 14 GB libres, la carga inicial NO empieza)
--   2. ¿Quién puede conectarse a cada base?
--   3. ¿Cómo ha crecido sigrid_dm, por esquema? (medición de T19)
--
-- Los bloques 3 y 4 solo devuelven algo si se ejecuta CONECTADO a sigrid_dm.

\echo '== 1. Tamaño por base y total del servidor =========================='
SELECT datname AS base,
       pg_size_pretty(pg_database_size(datname)) AS tamano,
       pg_database_size(datname) AS bytes
FROM pg_database
WHERE datistemplate = false
ORDER BY pg_database_size(datname) DESC;

-- 32 GB es el almacenamiento contratado del Flexible Server. El hueco real es
-- menor que este cálculo (WAL, índices en construcción, ficheros temporales),
-- por eso la puerta de T13 exige 14 GB libres y no 12.
SELECT pg_size_pretty(SUM(pg_database_size(datname))::numeric) AS total_ocupado,
       pg_size_pretty(
           32::numeric * 1024 * 1024 * 1024 - SUM(pg_database_size(datname))::numeric
       ) AS libre_aprox
FROM pg_database
WHERE datistemplate = false;

\echo '== 2. Quién puede conectarse a cada base ==========================='
-- datacl NULL significa "los privilegios por defecto", y el defecto incluye
-- CONNECT para PUBLIC: cualquier rol con login puede abrir sesión y leer el
-- catálogo (nombres de tablas y columnas), aunque no los datos.
SELECT datname AS base,
       pg_catalog.pg_get_userbyid(datdba) AS propietario,
       datacl,
       CASE WHEN datacl IS NULL THEN 'CONNECT abierto a PUBLIC (defecto)'
            ELSE 'ACL explícita'
       END AS lectura
FROM pg_database
WHERE datistemplate = false
ORDER BY datname;

\echo '== 3. Roles del datamart y sus pertenencias ========================'
SELECT r.rolname,
       r.rolcanlogin AS puede_login,
       r.rolsuper    AS superusuario,
       ARRAY(
           SELECT g.rolname
           FROM pg_auth_members AS m
           JOIN pg_roles AS g ON g.oid = m.roleid
           WHERE m.member = r.oid
       ) AS miembro_de
FROM pg_roles AS r
WHERE r.rolname LIKE 'sigrid_dm%' OR r.rolname LIKE 'mcp_%'
ORDER BY r.rolname;

\echo '== 4. Tamaño por esquema (ejecutar conectado a sigrid_dm) =========='
SELECT n.nspname AS esquema,
       COUNT(*) FILTER (WHERE c.relkind IN ('r', 'p')) AS tablas,
       COUNT(*) FILTER (WHERE c.relkind = 'v')         AS vistas,
       pg_size_pretty(SUM(pg_total_relation_size(c.oid))) AS tamano
FROM pg_class AS c
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND n.nspname NOT LIKE 'pg_toast%'
GROUP BY n.nspname
ORDER BY SUM(pg_total_relation_size(c.oid)) DESC;
