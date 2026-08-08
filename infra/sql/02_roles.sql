-- infra/sql/02_roles.sql
--
-- Roles de aplicación de sigrid_dm, sus contraseñas y sus permisos iniciales.
--
-- QUIÉN LO EJECUTA: el humano, a mano, con el usuario administrador del
-- Flexible Server, conectado YA a sigrid_dm (01_create_database.sql primero):
--
--   psql "host=<servidor> dbname=sigrid_dm user=<admin> sslmode=require" \
--        -v ON_ERROR_STOP=1 \
--        -v app_pwd="$APP_PWD" -v mcp_pwd="$MCP_PWD" \
--        -f infra/sql/02_roles.sql
--
-- LAS CONTRASEÑAS NO ESTÁN EN ESTE FICHERO NI PUEDEN ESTARLO. Llegan por
-- variables de psql desde variables de entorno de la sesión del humano, se
-- generan con `az keyvault secret set --generate-...` o equivalente, y viven
-- en Key Vault. Ver docs/runbook_postgres_azure.md.
--
-- MODELO DE ROLES (plan B: sin autenticación Entra, decisión del humano de
-- 2026-08-08, porque habilitarla es una operación de SERVIDOR y afectaría a
-- albaranes y partes):
--
--   sigrid_dm_etl      NOLOGIN, propietario de la base y de todos los objetos
--     └── sigrid_dm_app    LOGIN, contraseña en Key Vault. Lo usa el ETL, tanto
--                          desde el puesto del humano como desde el job de F-003
--   mcp_sigrid_dm_ro   LOGIN, contraseña en Key Vault. Solo lectura, para el MCP
--
-- Por qué un grupo y no un solo rol: los objetos los crea siempre
-- sigrid_dm_etl gracias a PG_SET_ROLE, así que si mañana entra un segundo
-- principal (la identidad gestionada del job, o la cuenta del operador) puede
-- recrear las vistas del primero. Sin eso, el segundo no podría hacer DROP
-- sobre lo que creó el primero, y las vistas se recrean en cada ejecución.

\set ON_ERROR_STOP on

-- 1. Roles de login. Se crean si faltan; la contraseña se fija siempre, de
--    modo que reejecutar el fichero sirve para rotarla.
SELECT 'CREATE ROLE sigrid_dm_app LOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sigrid_dm_app')
\gexec

SELECT 'CREATE ROLE mcp_sigrid_dm_ro LOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_sigrid_dm_ro')
\gexec

ALTER ROLE sigrid_dm_app    WITH LOGIN PASSWORD :'app_pwd';
ALTER ROLE mcp_sigrid_dm_ro WITH LOGIN PASSWORD :'mcp_pwd';

-- Ninguno de los dos crea bases ni roles ni hereda nada por su cuenta.
ALTER ROLE sigrid_dm_app    WITH NOSUPERUSER NOCREATEDB NOCREATEROLE;
ALTER ROLE mcp_sigrid_dm_ro WITH NOSUPERUSER NOCREATEDB NOCREATEROLE;

-- 2. El rol del ETL es miembro del grupo propietario.
GRANT sigrid_dm_etl TO sigrid_dm_app;

-- 3. Quién puede conectarse a esta base. 01_create_database.sql revocó el
--    CONNECT que PostgreSQL concede a PUBLIC, así que hay que darlo explícito.
GRANT CONNECT ON DATABASE sigrid_dm TO sigrid_dm_app;
GRANT CONNECT ON DATABASE sigrid_dm TO mcp_sigrid_dm_ro;

-- 4. Esquemas del datamart. Los crea también el auto-bootstrap del ETL, pero
--    dejarlos aquí permite comprobar los nueve nada más provisionar.
SET ROLE sigrid_dm_etl;
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS stg;
CREATE SCHEMA IF NOT EXISTS aux;
CREATE SCHEMA IF NOT EXISTS mart;
CREATE SCHEMA IF NOT EXISTS _meta;
CREATE SCHEMA IF NOT EXISTS cierre;
CREATE SCHEMA IF NOT EXISTS compras;
CREATE SCHEMA IF NOT EXISTS maestro;
CREATE SCHEMA IF NOT EXISTS retenciones;
RESET ROLE;

-- 5. Permisos de lectura del MCP.
--
--    Esto es solo el arranque: los GRANT reales los reaplica el ETL en cada
--    ejecución (`python main.py apply-grants`), porque las vistas se recrean
--    con DROP + CREATE y un DROP se lleva los permisos por delante.
--
--    ALCANCE: por decisión del humano de 2026-08-08 el MCP lee TODOS los
--    esquemas, no solo los cinco de consumo. Se revisará al rediseñar el MCP
--    en F-006. La lista efectiva la manda PG_CONSUMPTION_SCHEMAS.
DO $$
DECLARE
    esquema text;
BEGIN
    FOREACH esquema IN ARRAY ARRAY[
        'mart', 'cierre', 'compras', 'maestro', 'retenciones',
        'raw', 'stg', 'aux', '_meta'
    ]
    LOOP
        EXECUTE format('GRANT USAGE ON SCHEMA %I TO mcp_sigrid_dm_ro', esquema);
        EXECUTE format(
            'GRANT SELECT ON ALL TABLES IN SCHEMA %I TO mcp_sigrid_dm_ro', esquema
        );
        EXECUTE format(
            'ALTER DEFAULT PRIVILEGES FOR ROLE sigrid_dm_etl IN SCHEMA %I '
            'GRANT SELECT ON TABLES TO mcp_sigrid_dm_ro', esquema
        );
    END LOOP;
END
$$;

-- 6. Comprobaciones. Deben salir: los tres roles, sigrid_dm_app dentro de
--    sigrid_dm_etl, y los nueve esquemas.
SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole
FROM pg_roles
WHERE rolname IN ('sigrid_dm_etl', 'sigrid_dm_app', 'mcp_sigrid_dm_ro')
ORDER BY rolname;

SELECT r.rolname AS miembro, g.rolname AS grupo
FROM pg_auth_members AS m
JOIN pg_roles AS r ON r.oid = m.member
JOIN pg_roles AS g ON g.oid = m.roleid
WHERE g.rolname = 'sigrid_dm_etl';

SELECT nspname AS esquema, pg_catalog.pg_get_userbyid(nspowner) AS propietario
FROM pg_namespace
WHERE nspname IN ('raw', 'stg', 'aux', 'mart', '_meta',
                  'cierre', 'compras', 'maestro', 'retenciones')
ORDER BY nspname;
