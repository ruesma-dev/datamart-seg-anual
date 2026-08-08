-- infra/sql/01_create_database.sql
--
-- Crea el rol de grupo propietario y la base sigrid_dm dentro del servidor
-- psql-albaranes-rs9k2, que YA sirve a albaranes y partes.
--
-- QUIÉN LO EJECUTA: el humano, a mano, UNA vez, con el usuario administrador
-- del Flexible Server, conectado a la base `postgres`. NO lo ejecuta el ETL.
--
--   psql "host=<servidor> dbname=postgres user=<admin> sslmode=require" \
--        -v ON_ERROR_STOP=1 -f infra/sql/01_create_database.sql
--
-- ALCANCE: solo la base nueva. Este fichero no toca albaranes ni partes, no
-- cambia parámetros del servidor y no reinicia nada.
--
-- IRREVERSIBLE: nada de lo que hay aquí lo es. `DROP DATABASE sigrid_dm`
-- deshace la creación (y el datamart se regenera ejecutando el ETL).
--
-- OJO: este fichero usa bloques `DO $$ ... $$`. Se ejecuta con psql, nunca a
-- través de PostgresClient.execute_sql_file: su troceador de sentencias no
-- sabe manejar `$$`, según su propio docstring.

\set ON_ERROR_STOP on

-- 1. Rol de GRUPO propietario. NOLOGIN: nadie se conecta como él, se hace
--    SET ROLE. Así todos los objetos tienen el mismo dueño conecte quien
--    conecte, y cualquier miembro puede recrear las vistas del otro.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sigrid_dm_etl') THEN
        CREATE ROLE sigrid_dm_etl NOLOGIN;
    END IF;
END
$$;

-- 2. El administrador necesita ser miembro del rol para poder cederle la
--    propiedad de la base. En un Flexible Server el admin no es superusuario.
DO $$
BEGIN
    IF NOT pg_has_role(CURRENT_USER, 'sigrid_dm_etl', 'MEMBER') THEN
        EXECUTE format('GRANT sigrid_dm_etl TO %I', CURRENT_USER);
    END IF;
END
$$;

-- 3. La base. CREATE DATABASE no admite IF NOT EXISTS ni va dentro de una
--    transacción: se genera condicionalmente y se ejecuta con \gexec.
SELECT 'CREATE DATABASE sigrid_dm OWNER sigrid_dm_etl ENCODING ''UTF8'''
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'sigrid_dm')
\gexec

-- 4. Nadie entra en la base nueva por el mero hecho de existir. PostgreSQL
--    concede CONNECT a PUBLIC por defecto; aquí se revoca para que el acceso
--    sea explícito. Solo afecta a sigrid_dm.
REVOKE ALL ON DATABASE sigrid_dm FROM PUBLIC;
GRANT ALL ON DATABASE sigrid_dm TO sigrid_dm_etl;

-- 5. Comprobación: propietario correcto y PUBLIC sin privilegios.
SELECT d.datname,
       pg_catalog.pg_get_userbyid(d.datdba) AS propietario,
       d.datacl
FROM pg_database AS d
WHERE d.datname = 'sigrid_dm';
