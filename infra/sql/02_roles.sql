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

-- Ninguno de los dos crea bases ni roles.
--
-- SIN `NOSUPERUSER`, a propósito. En Azure Database for PostgreSQL Flexible
-- Server el administrador NO es superusuario (es miembro de `azure_pg_admin`),
-- y PostgreSQL exige el atributo SUPERUSER para cambiarlo, aunque sea para
-- ponerlo a NO:
--     ERROR: permission denied to alter role
--     DETALLE: Only roles with the SUPERUSER attribute may change the
--              SUPERUSER attribute.
-- No se pierde nada: `CREATE ROLE` ya crea NOSUPERUSER por defecto, y así se
-- verificó contra el servidor real (`rolsuper = f` en los tres roles).
-- Contra un PostgreSQL local no fallaba porque allí el admin sí es superusuario:
-- este fichero solo podía romperse contra Azure. Encontrado el 2026-08-09 al
-- ejecutar la Fase 2 del runbook.
ALTER ROLE sigrid_dm_app    WITH NOCREATEDB NOCREATEROLE;
ALTER ROLE mcp_sigrid_dm_ro WITH NOCREATEDB NOCREATEROLE;

-- 2. El rol del ETL es miembro del grupo propietario.
GRANT sigrid_dm_etl TO sigrid_dm_app;

-- 3. Quién puede conectarse a esta base. 01_create_database.sql revocó el
--    CONNECT que PostgreSQL concede a PUBLIC, así que hay que darlo explícito.
GRANT CONNECT ON DATABASE sigrid_dm TO sigrid_dm_app;
GRANT CONNECT ON DATABASE sigrid_dm TO mcp_sigrid_dm_ro;

-- 4. Esquemas del datamart. Los crea también el auto-bootstrap del ETL, pero
--    dejarlos aquí permite comprobar los diez nada más provisionar.
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
-- F-057: el único esquema con datos personales (nombre, NIF y DNI, autorizados
-- el 2026-09-18). Es esquema propio para poder darlo o quitarlo con un GRANT.
CREATE SCHEMA IF NOT EXISTS personal;
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
--
--    OJO: este bloque concede `raw` ENTERO, y eso incluye tablas con datos
--    personales. El punto 5 bis, justo debajo, se las quita. No se puede
--    hacer aquí: `GRANT SELECT ON ALL TABLES IN SCHEMA` no admite excepciones.
--
--    LA TRANSACCIÓN QUE ABRE AQUÍ Y CIERRA AL FINAL DEL 5 BIS NO ES ADORNO.
--    Sin `BEGIN` explícito, psql confirma cada `DO` por separado: entre el
--    GRANT de este punto y el primer REVOKE del 5 bis los datos personales
--    quedan legibles, y si el script muere justo ahí con ON_ERROR_STOP quedan
--    legibles Y CONFIRMADOS, sin que nadie lo note. En PostgreSQL GRANT,
--    REVOKE y ALTER DEFAULT PRIVILEGES son transaccionales, así que las dos
--    mitades entran juntas o no entra ninguna. Si aun así el script se corta
--    entre el BEGIN y el COMMIT (se cae la sesión, Ctrl-C), el servidor hace
--    rollback y el rol se queda como estaba: se vuelve a ejecutar el fichero
--    entero, que es reejecutable. Lo que NO se puede hacer es dar por buena
--    una ejecución cortada y seguir.
BEGIN;

DO $$
DECLARE
    esquema text;
BEGIN
    FOREACH esquema IN ARRAY ARRAY[
        'mart', 'cierre', 'compras', 'maestro', 'retenciones', 'personal',
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

-- 5 bis. Tablas que el MCP NO puede leer (F-068, 2026-09-07).
--
--    #################################################################
--    #  ESTO ES TEMPORAL Y SU REVERSIÓN YA ESTÁ DECIDIDA             #
--    #################################################################
--
--    Palabras del humano el 2026-09-07: «de momento quita el permiso. Cuando
--    pongamos límites o guardarraíles por usuario, habrá que volver a ponerlo
--    para algunos usuarios». No es una prohibición permanente: es un tapón
--    mientras el MCP no sepa QUIÉN pregunta. Quien lo lea dentro de seis
--    meses, la pregunta correcta es «¿ya hay control por usuario?».
--
--    F-074 (2026-09-09) añade dos más por el mismo motivo y con el mismo
--    mecanismo: `raw.reshor` es el precio de coste por recurso y tipo de hora
--    (8.949 filas, 2.036 con precio distinto de cero) y `raw.emphis` el
--    histórico de contrato de 1.017 empleados (1.633 filas, de 1989 a 2026).
--    Son datos de nómina. Las cuatro caen el mismo día que el MCP tenga
--    control por usuario, no antes.
--
--    QUÉ ES CADA UNA. `raw.emp` son 1.352 empleados con DNI, número de la
--    Seguridad Social, cuenta bancaria, domicilio, teléfonos y credenciales
--    del portal. `raw.res` son 2.610 recursos con el NIF de la persona en
--    `cif` y las credenciales de acceso a Sigrid. Las trajo enteras F-066, por
--    decisión del humano del 2026-09-06; el rol de lectura del MCP lo usa
--    cualquier cuenta del tenant.
--
--    LAS DOS MITADES, y las dos hacen falta:
--      a) REVOKE sobre la tabla, DESPUÉS del GRANT del punto 5, que la alcanza
--         (`ON ALL TABLES IN SCHEMA` no sabe saltarse una);
--      b) quitar el ALTER DEFAULT PRIVILEGES de `raw`, que es una regla del
--         catálogo: mientras esté puesta, cualquier tabla que nazca en `raw`
--         es legible sin que nadie ejecute un GRANT. Dejar de emitirla no la
--         borra; hay que emitir su REVOKE.
--
--    LA LISTA VIVE EN EL CÓDIGO, no aquí: `DEFAULT_EXCLUDED_TABLES` de
--    `config/settings.py`, parametrizable con PG_EXCLUDED_TABLES. Este fichero
--    solo cubre el arranque, porque la nocturna (`apply_grants`) es quien lo
--    sostiene noche tras noche. Un test comprueba que las dos listas coinciden.
--
--    DOS VECES, Y NO ES UN DESPISTE. En PostgreSQL un REVOKE solo quita la
--    concesión hecha por EL MISMO concedente: la ACL guarda una entrada por
--    cada uno (`mcp=r/admin` y `mcp=r/sigrid_dm_etl` son dos). Y aquí hay dos
--    concedentes reales: el punto 5 de este fichero concede como el
--    ADMINISTRADOR que lo ejecuta, y la nocturna concede como `sigrid_dm_etl`
--    (que es además el propietario, así que es el concedente de lo que nace
--    por privilegio por defecto). Revocar solo con uno deja la tabla legible
--    y sin ningún error a la vista: PostgreSQL avisa con un NOTICE y sigue.
DO $$
DECLARE
    objeto text;
BEGIN
    FOREACH objeto IN ARRAY ARRAY['raw.emp', 'raw.res', 'raw.reshor', 'raw.emphis']
    LOOP
        -- to_regclass devuelve NULL en vez de fallar si la tabla no existe:
        -- este fichero se ejecuta también sobre una base recién creada, antes
        -- de la primera ingesta.
        IF to_regclass(objeto) IS NOT NULL THEN
            EXECUTE format(
                'REVOKE ALL PRIVILEGES ON TABLE %s FROM mcp_sigrid_dm_ro', objeto
            );
        END IF;
    END LOOP;
END
$$;

SET ROLE sigrid_dm_etl;
DO $$
DECLARE
    objeto text;
    esquema text;
BEGIN
    FOREACH objeto IN ARRAY ARRAY['raw.emp', 'raw.res', 'raw.reshor', 'raw.emphis']
    LOOP
        IF to_regclass(objeto) IS NOT NULL THEN
            EXECUTE format(
                'REVOKE ALL PRIVILEGES ON TABLE %s FROM mcp_sigrid_dm_ro', objeto
            );
        END IF;
    END LOOP;

    -- La regla de privilegios por defecto: es lo que haría legible una tabla
    -- recreada sin que nadie ejecutase un GRANT. Se declara POR rol creador,
    -- y el creador es este.
    --
    -- El esquema se DERIVA de la lista, igual que hace `grants.py`: escribir
    -- `raw` a mano funcionaba mientras las dos exclusiones fueran de `raw`,
    -- pero el día que PG_EXCLUDED_TABLES traiga una tabla de otro esquema la
    -- nocturna lo resolvería y este fichero no, y el rol nacería con la regla
    -- puesta sobre ese esquema. Y a diferencia del REVOKE de tabla, esta
    -- regla NO necesita que la tabla exista: se declara sobre el esquema y es
    -- justo lo que protege a la que todavía no ha nacido.
    FOR esquema IN
        -- El alias NO puede llamarse `objeto`: plpgsql daría «column
        -- reference is ambiguous» contra la variable de arriba.
        SELECT DISTINCT split_part(excluida, '.', 1)
        FROM unnest(ARRAY['raw.emp', 'raw.res', 'raw.reshor', 'raw.emphis']) AS excluida
    LOOP
        IF to_regnamespace(esquema) IS NOT NULL THEN
            EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE sigrid_dm_etl IN SCHEMA %I '
                'REVOKE SELECT ON TABLES FROM mcp_sigrid_dm_ro', esquema
            );
        END IF;
    END LOOP;
END
$$;
RESET ROLE;

COMMIT;

-- 6. Comprobaciones. Deben salir: los tres roles, sigrid_dm_app dentro de
--    sigrid_dm_etl, y los diez esquemas.
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
                  'cierre', 'compras', 'maestro', 'retenciones', 'personal')
ORDER BY nspname;

-- F-068: las tablas excluidas NO deben aparecer aquí. CERO filas es el
-- resultado correcto; una fila significa que el MCP las sigue leyendo.
SELECT table_schema, table_name, privilege_type
FROM information_schema.table_privileges
WHERE grantee = 'mcp_sigrid_dm_ro'
  AND table_schema = 'raw'
  AND table_name IN ('emp', 'res')
ORDER BY table_name, privilege_type;
