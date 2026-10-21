-- infra/sql/02_roles.sql
--
-- Roles de aplicación de sigrid_dm, sus contraseñas y sus permisos iniciales.
--
-- QUIÉN LO EJECUTA: el humano, a mano, con el usuario administrador del
-- Flexible Server, conectado YA a sigrid_dm (01_create_database.sql primero).
-- Procedimiento completo, con la carga desde Key Vault: runbook §12 (y §13 para
-- el perfil restringido de F-141).
--
--   $env:APP_PWD / $env:MCP_PWD / $env:TOTAL_PWD   (desde Key Vault, opcionales)
--   $env:RESTRINGIDO_PWD                           (F-141, desde Key Vault, opcional)
--   psql -X -v ON_ERROR_STOP=1 -f infra/sql/02_roles.sql $dsn
--
-- LAS OPCIONES VAN SIEMPRE ANTES DE LA CADENA DE CONEXIÓN, que es lo último. En
-- Windows `psql` deja de leer opciones en cuanto encuentra la cadena: las que
-- vayan detrás las ignora y las imprime. Así se expusieron dos contraseñas el
-- 2026-10-12 (F-136), que entonces viajaban con `-v`.
--
-- LAS CONTRASEÑAS NO ESTÁN EN ESTE FICHERO NI PUEDEN ESTARLO, y tampoco viajan
-- ya en la línea de órdenes (que se ve en la lista de procesos). El fichero las
-- lee con `\getenv` (psql 15 o posterior) de las variables de entorno APP_PWD,
-- MCP_PWD, TOTAL_PWD y RESTRINGIDO_PWD de la sesión del humano, cargadas desde Key Vault. Cada
-- una es OPCIONAL: la que no esté definida deja la contraseña de su login SIN
-- CAMBIOS, de modo que reejecutar el fichero para dar un permiso no obliga a
-- manejar secretos. Solo hace falta la de un login que aún no existe; si
-- falta, el fichero para ANTES de crear o cambiar nada.
--
-- MODELO DE ROLES (plan B: sin autenticación Entra, decisión del humano de
-- 2026-08-08, porque habilitarla es una operación de SERVIDOR y afectaría a
-- albaranes y partes):
--
--   sigrid_dm_etl      NOLOGIN, propietario de la base y de todos los objetos
--     └── sigrid_dm_app    LOGIN, contraseña en Key Vault. Lo usa el ETL, tanto
--                          desde el puesto del humano como desde el job de F-003
--   mcp_sigrid_dm_ro   LOGIN, contraseña en Key Vault. Solo lectura, para el MCP
--                      (y hoy también Power BI). Es el rol GENERAL (estándar):
--                      desde F-135 NO lee `raw` ni `contabilidad_restringida`
--   sigrid_dm_autorizado_ro  NOLOGIN, sin contraseña (F-135). El rol AUTORIZADO:
--                      lee la contabilidad COMPLETA, con los apuntes de personal
--                      (nóminas, cuentas de trabajadores, embargos). Es un GRUPO:
--                      sus miembros los decide Negocio (Juan Romero) y se dan
--                      con `GRANT sigrid_dm_autorizado_ro TO <login>`
--   mcp_sigrid_dm_total  LOGIN, contraseña SOLO en el vault del MCP (F-136). El
--                      acceso TOTAL del MCP: miembro del general y del
--                      autorizado (punto 5 quater), lee lo de los dos y NUNCA
--                      `raw` («siempre fuera», decisión del humano del
--                      2026-10-12). Ningún GRANT propio: todo por pertenencia.
--                      Quién conecta con él lo decide la F-008 de `mcp-bbdd`
--   sigrid_dm_perfil_restringido_ro  NOLOGIN, sin contraseña (F-141). El perfil
--                      RESTRINGIDO (administrativos), que ve MENOS que el
--                      estándar: lo de este menos `contabilidad` entera
--                      (F-146; antes, solo el mayor y sus saldos), `personal` y
--                      `tesoreria` (y nunca `raw` ni las `*_restringida`).
--                      Lleva los permisos (punto 5 quinquies)
--     └── mcp_sigrid_dm_restringido  LOGIN, contraseña SOLO en el vault del MCP
--                      (F-141, RESTRINGIDO_PWD). Miembro solo de su grupo, sin
--                      GRANT propio. Quién conecta con él lo decide `mcp-bbdd`
--
-- F-141 RENOMBRÓ el grupo autorizado a `sigrid_dm_autorizado_ro` (punto 0 bis):
-- su nombre anterior decía «restringido» y es justo lo que ve MÁS. El renombre
-- conserva OID, GRANT y pertenencias. La imagen del ETL con F-141 y este
-- fichero se aplican el MISMO día, entre dos nocturnas (runbook §13).
--
-- Por qué un grupo y no un solo rol: los objetos los crea siempre
-- sigrid_dm_etl gracias a PG_SET_ROLE, así que si mañana entra un segundo
-- principal (la identidad gestionada del job, o la cuenta del operador) puede
-- recrear las vistas del primero. Sin eso, el segundo no podría hacer DROP
-- sobre lo que creó el primero, y las vistas se recrean en cada ejecución.

\set ON_ERROR_STOP on
-- F-136: silencio ANTES de tocar una contraseña. ECHO none: no se repite
-- ninguna sentencia aunque se lance con -e o -a. VERBOSITY terse y
-- SHOW_CONTEXT never: un error no imprime la línea que lo causó (`LINE 1:`),
-- que en un ALTER ROLE llevaría la contraseña.
\set ECHO none
\set VERBOSITY terse
\set SHOW_CONTEXT never
-- Si la variable de entorno no existe, `\getenv` no toca la de psql: queda sin
-- definir y su contraseña SIN CAMBIOS.
\getenv app_pwd APP_PWD
\getenv mcp_pwd MCP_PWD
\getenv total_pwd TOTAL_PWD
\getenv restringido_pwd RESTRINGIDO_PWD

-- 0. Guarda (F-136, R18): un login que aún no existe necesita su contraseña.
--    Se comprueba ANTES de crear nada, para no dejar un login a medias.
SELECT NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sigrid_dm_app') AS falta_app,
       NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_sigrid_dm_ro') AS falta_mcp,
       NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_sigrid_dm_total') AS falta_total,
       NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_sigrid_dm_restringido') AS falta_restringido
\gset
\if :falta_app
\if :{?app_pwd}
\else
DO $$ BEGIN RAISE EXCEPTION 'F-136: sigrid_dm_app no existe y falta APP_PWD en el entorno (runbook §12)'; END $$;
\endif
\endif
\if :falta_mcp
\if :{?mcp_pwd}
\else
DO $$ BEGIN RAISE EXCEPTION 'F-136: mcp_sigrid_dm_ro no existe y falta MCP_PWD en el entorno (runbook §12)'; END $$;
\endif
\endif
\if :falta_total
\if :{?total_pwd}
\else
DO $$ BEGIN RAISE EXCEPTION 'F-136: mcp_sigrid_dm_total no existe y falta TOTAL_PWD en el entorno (runbook §12)'; END $$;
\endif
\endif
\if :falta_restringido
\if :{?restringido_pwd}
\else
DO $$ BEGIN RAISE EXCEPTION 'F-141: mcp_sigrid_dm_restringido no existe y falta RESTRINGIDO_PWD en el entorno (runbook §13)'; END $$;
\endif
\endif

-- 0 bis. Renombre del grupo autorizado (F-141, D6), ANTES de crear nada: si no,
--    el punto 1 crearía el nombre nuevo y existirían los dos. Solo si existe el
--    viejo y no el nuevo; con los dos, el fichero para aquí, sin haber cambiado
--    nada (las guardas de arriba tampoco han cambiado nada). Con solo el nuevo,
--    o con ninguno (base recién creada), no hay nada que renombrar.
SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sigrid_dm_restringido_ro') AS existe_nombre_viejo,
       EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sigrid_dm_autorizado_ro') AS existe_nombre_nuevo
\gset
\if :existe_nombre_viejo
\if :existe_nombre_nuevo
DO $$ BEGIN RAISE EXCEPTION 'F-141: existen sigrid_dm_restringido_ro y sigrid_dm_autorizado_ro; decide cuál sobra antes de seguir (runbook §13)'; END $$;
\endif
\endif
\if :existe_nombre_viejo
ALTER ROLE sigrid_dm_restringido_ro RENAME TO sigrid_dm_autorizado_ro;
\echo 'F-141: grupo autorizado renombrado (conserva OID, GRANT y pertenencias)'
\else
\echo 'F-141: grupo autorizado sin renombre (ya tiene el nombre nuevo o aún no existe)'
\endif

-- 1. Roles de login. Se crean si faltan; la contraseña se fija solo si su
--    variable está definida, y reejecutar el fichero con ella sirve para rotarla.
SELECT 'CREATE ROLE sigrid_dm_app LOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sigrid_dm_app')
\gexec

SELECT 'CREATE ROLE mcp_sigrid_dm_ro LOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_sigrid_dm_ro')
\gexec

-- F-136: el login de acceso TOTAL del MCP
SELECT 'CREATE ROLE mcp_sigrid_dm_total LOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_sigrid_dm_total')
\gexec

-- F-141: el login del perfil RESTRINGIDO del MCP
SELECT 'CREATE ROLE mcp_sigrid_dm_restringido LOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_sigrid_dm_restringido')
\gexec

-- Las contraseñas: cada una solo si su variable existe, y nunca su valor en la
-- salida. Un ALTER ROLE que FALLE deja su texto en el log del servidor
-- (`log_min_error_statement = error`): por eso la guarda de arriba.
\if :{?app_pwd}
ALTER ROLE sigrid_dm_app WITH LOGIN PASSWORD :'app_pwd';
\echo 'sigrid_dm_app: contraseña fijada'
\else
\echo 'sigrid_dm_app: contraseña SIN CAMBIOS'
\endif
\if :{?mcp_pwd}
ALTER ROLE mcp_sigrid_dm_ro WITH LOGIN PASSWORD :'mcp_pwd';
\echo 'mcp_sigrid_dm_ro: contraseña fijada'
\else
\echo 'mcp_sigrid_dm_ro: contraseña SIN CAMBIOS'
\endif
\if :{?total_pwd}
ALTER ROLE mcp_sigrid_dm_total WITH LOGIN PASSWORD :'total_pwd';
\echo 'mcp_sigrid_dm_total: contraseña fijada'
\else
\echo 'mcp_sigrid_dm_total: contraseña SIN CAMBIOS'
\endif
\if :{?restringido_pwd}
ALTER ROLE mcp_sigrid_dm_restringido WITH LOGIN PASSWORD :'restringido_pwd';
\echo 'mcp_sigrid_dm_restringido: contraseña fijada'
\else
\echo 'mcp_sigrid_dm_restringido: contraseña SIN CAMBIOS'
\endif

-- F-135: el rol AUTORIZADO es un grupo sin login y sin contraseña. Quien lo
-- necesite entra con su propio login, miembro de este grupo.
SELECT 'CREATE ROLE sigrid_dm_autorizado_ro NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sigrid_dm_autorizado_ro')
\gexec

-- F-141: el grupo del perfil RESTRINGIDO, sin login y sin contraseña. Lleva
-- los permisos; su login (arriba) solo es miembro suyo (punto 5 quinquies).
SELECT 'CREATE ROLE sigrid_dm_perfil_restringido_ro NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sigrid_dm_perfil_restringido_ro')
\gexec

-- Ninguno de ellos crea bases ni roles.
--
-- SIN `NOSUPERUSER`, a propósito. En Azure Database for PostgreSQL Flexible
-- Server el administrador NO es superusuario (es miembro de `azure_pg_admin`),
-- y PostgreSQL exige el atributo SUPERUSER para cambiarlo, aunque sea para
-- ponerlo a NO:
--     ERROR: permission denied to alter role
--     DETALLE: Only roles with the SUPERUSER attribute may change the
--              SUPERUSER attribute.
-- No se pierde nada: `CREATE ROLE` ya crea NOSUPERUSER por defecto, y así se
-- verificó contra el servidor real (`rolsuper = f` en los tres roles; la
-- comprobación final del punto 6 lo enseña también para el total, F-136).
-- Contra un PostgreSQL local no fallaba porque allí el admin sí es superusuario:
-- este fichero solo podía romperse contra Azure. Encontrado el 2026-08-09 al
-- ejecutar la Fase 2 del runbook.
ALTER ROLE sigrid_dm_app    WITH NOCREATEDB NOCREATEROLE;
ALTER ROLE mcp_sigrid_dm_ro WITH NOCREATEDB NOCREATEROLE;
ALTER ROLE mcp_sigrid_dm_total WITH LOGIN NOCREATEDB NOCREATEROLE;
ALTER ROLE sigrid_dm_autorizado_ro WITH NOLOGIN NOCREATEDB NOCREATEROLE;
ALTER ROLE mcp_sigrid_dm_restringido WITH LOGIN NOCREATEDB NOCREATEROLE;
ALTER ROLE sigrid_dm_perfil_restringido_ro WITH NOLOGIN NOCREATEDB NOCREATEROLE;

-- 2. El rol del ETL es miembro del grupo propietario.
GRANT sigrid_dm_etl TO sigrid_dm_app;

-- 3. Quién puede conectarse a esta base. 01_create_database.sql revocó el
--    CONNECT que PostgreSQL concede a PUBLIC, así que hay que darlo explícito.
GRANT CONNECT ON DATABASE sigrid_dm TO sigrid_dm_app;
GRANT CONNECT ON DATABASE sigrid_dm TO mcp_sigrid_dm_ro;
-- F-135: lo heredan los futuros miembros del grupo
GRANT CONNECT ON DATABASE sigrid_dm TO sigrid_dm_autorizado_ro;
-- F-141: al GRUPO del perfil restringido; su login lo hereda
GRANT CONNECT ON DATABASE sigrid_dm TO sigrid_dm_perfil_restringido_ro;

-- 4. Esquemas del datamart. Los crea también el auto-bootstrap del ETL, pero
--    dejarlos aquí permite comprobar los dieciséis nada más provisionar.
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
-- F-056: el plan de cuentas, el mayor y los saldos por cuenta y mes. Esquema
-- propio por lo mismo que `personal`: su acceso se da o se quita con un GRANT.
CREATE SCHEMA IF NOT EXISTS contabilidad;
-- F-135: la contabilidad COMPLETA, con los apuntes de personal. Solo la lee el
-- rol autorizado; al general se le VETA (punto 5 ter).
CREATE SCHEMA IF NOT EXISTS contabilidad_restringida;
-- F-097: los descompuestos de las partidas. Esquema propio por lo mismo.
CREATE SCHEMA IF NOT EXISTS descompuestos;
-- F-037: la cartera de cobros y pagos. La GENERAL (`tesoreria`, sin los pagos
-- de personal) la lee el rol general; la COMPLETA (`tesoreria_restringida`,
-- con nóminas, embargos y cuotas) solo el autorizado: se le VETA al general
-- (punto 5 ter), como a `contabilidad_restringida`.
CREATE SCHEMA IF NOT EXISTS tesoreria;
CREATE SCHEMA IF NOT EXISTS tesoreria_restringida;
-- F-138: las alarmas COMPLETAS de los documentos de Sigrid, con las de
-- recursos y partes de trabajo (nombran trabajadores y bajas). La general vive
-- en `compras`; esta solo la lee el autorizado: se le VETA al general (punto
-- 5 ter). Tiene que existir ANTES del primer `build-compras`, que escribe en
-- ella: por eso este fichero se ejecuta antes del despliegue.
CREATE SCHEMA IF NOT EXISTS compras_restringida;
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
--    F-135 (2026-10-11): `raw` YA NO ESTÁ en esta lista (D3, variante A): trae
--    el mayor, 37.048 efectos de pago de nómina con la cuenta bancaria del
--    trabajador, los repartos analíticos de personal y las cabeceras de esos
--    asientos. Tampoco `contabilidad_restringida` ni, desde F-037,
--    `tesoreria_restringida`. Los tres están VETADOS y el punto 5 ter se los
--    quita al rol general. La lista es exactamente
--    `DEFAULT_CONSUMPTION_SCHEMAS` de `config/settings.py` (un test lo vigila).
--
--    El punto 5 bis, de F-068, sigue quitando tablas sueltas de `raw` aunque
--    `raw` ya no se conceda: es la red para el día que vuelva (variante B).
--
--    LA TRANSACCIÓN QUE ABRE AQUÍ Y CIERRA TRAS EL 5 QUATER NO ES ADORNO.
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
        'contabilidad', 'tesoreria', 'descompuestos', 'stg', 'aux', '_meta'
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

-- 5 ter. Esquemas VETADOS al rol general y concesiones del rol AUTORIZADO
--    (F-135, 2026-10-11).
--
--    Origen: correo de Juan Romero del 2026-10-09, «hay que limitarla a todos
--    los usuarios salvo a los que tenemos ese rol». La contabilidad completa
--    vive en `contabilidad_restringida` y `raw` trae el mismo dato y más; los
--    dos quedan fuera del rol general. F-037 (2026-10-13) añade
--    `tesoreria_restringida`, la cartera completa con los pagos de nómina
--    («los pagos de nominas deben quedar restringidos», decisión del humano), y
--    F-138 (2026-10-14) `compras_restringida`, las alarmas de recursos y partes
--    («solo para el perfil admin y no el estándar»). La lista es `DEFAULT_VETOED_SCHEMAS` de
--    `config/settings.py` (un test lo vigila) y la sostiene cada noche
--    `apply_grants`, que además COMPRUEBA en el catálogo que el rol general no
--    los lee y falla si los lee.
--
--    DOS CONCEDENTES, como en el 5 bis y por lo mismo: un REVOKE solo quita lo
--    concedido por quien lo ejecuta. Una vez como el administrador que corre
--    este fichero y otra como `sigrid_dm_etl`, que es el dueño y el que concede
--    cada noche. Las tres mitades —tablas, USAGE del esquema y privilegio por
--    defecto— hacen falta: sin USAGE no se llega a ninguna tabla, y la regla
--    por defecto es la que haría legible la tabla que nazca mañana.
--
--    Dentro de la MISMA transacción que el GRANT del punto 5: si el fichero se
--    corta a medias, el servidor deshace todo y no queda `raw` concedido.
DO $$
DECLARE
    vetado text;
    vetado_total text;
BEGIN
    FOREACH vetado IN ARRAY ARRAY['contabilidad_restringida', 'tesoreria_restringida', 'compras_restringida', 'raw']
    LOOP
        -- en una base recién creada el esquema puede no existir todavía
        IF to_regnamespace(vetado) IS NOT NULL THEN
            EXECUTE format(
                'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA %I FROM mcp_sigrid_dm_ro', vetado
            );
            EXECUTE format(
                'REVOKE ALL PRIVILEGES ON SCHEMA %I FROM mcp_sigrid_dm_ro', vetado
            );
        END IF;
    END LOOP;

    -- F-136: al login TOTAL se le veta SOLO `raw`; lo restringido lo hereda a
    -- propósito. La lista es `DEFAULT_TOTAL_VETOED_SCHEMAS` (un test lo vigila).
    FOREACH vetado_total IN ARRAY ARRAY['raw']
    LOOP
        IF to_regnamespace(vetado_total) IS NOT NULL THEN
            EXECUTE format(
                'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA %I FROM mcp_sigrid_dm_total', vetado_total
            );
            EXECUTE format(
                'REVOKE ALL PRIVILEGES ON SCHEMA %I FROM mcp_sigrid_dm_total', vetado_total
            );
        END IF;
    END LOOP;
END
$$;

SET ROLE sigrid_dm_etl;
-- El rol autorizado lee la contabilidad completa (lo mismo que concede la
-- nocturna; aquí para que el rol nazca ya con su lectura).
GRANT USAGE ON SCHEMA contabilidad_restringida TO sigrid_dm_autorizado_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA contabilidad_restringida TO sigrid_dm_autorizado_ro;
ALTER DEFAULT PRIVILEGES FOR ROLE sigrid_dm_etl IN SCHEMA contabilidad_restringida GRANT SELECT ON TABLES TO sigrid_dm_autorizado_ro;
-- F-037: y la cartera completa de cobros y pagos, igual.
GRANT USAGE ON SCHEMA tesoreria_restringida TO sigrid_dm_autorizado_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA tesoreria_restringida TO sigrid_dm_autorizado_ro;
ALTER DEFAULT PRIVILEGES FOR ROLE sigrid_dm_etl IN SCHEMA tesoreria_restringida GRANT SELECT ON TABLES TO sigrid_dm_autorizado_ro;
-- F-138: y las alarmas completas de los documentos, igual.
GRANT USAGE ON SCHEMA compras_restringida TO sigrid_dm_autorizado_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA compras_restringida TO sigrid_dm_autorizado_ro;
ALTER DEFAULT PRIVILEGES FOR ROLE sigrid_dm_etl IN SCHEMA compras_restringida GRANT SELECT ON TABLES TO sigrid_dm_autorizado_ro;

DO $$
DECLARE
    vetado text;
    vetado_total text;
BEGIN
    FOREACH vetado IN ARRAY ARRAY['contabilidad_restringida', 'tesoreria_restringida', 'compras_restringida', 'raw']
    LOOP
        IF to_regnamespace(vetado) IS NOT NULL THEN
            EXECUTE format(
                'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA %I FROM mcp_sigrid_dm_ro', vetado
            );
            EXECUTE format(
                'REVOKE ALL PRIVILEGES ON SCHEMA %I FROM mcp_sigrid_dm_ro', vetado
            );
            EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE sigrid_dm_etl IN SCHEMA %I '
                'REVOKE ALL ON TABLES FROM mcp_sigrid_dm_ro', vetado
            );
        END IF;
    END LOOP;

    -- F-136: lo mismo para el login TOTAL, como dueño (tablas, USAGE y la
    -- regla por defecto que haría legible la tabla de `raw` que nazca mañana).
    FOREACH vetado_total IN ARRAY ARRAY['raw']
    LOOP
        IF to_regnamespace(vetado_total) IS NOT NULL THEN
            EXECUTE format(
                'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA %I FROM mcp_sigrid_dm_total', vetado_total
            );
            EXECUTE format(
                'REVOKE ALL PRIVILEGES ON SCHEMA %I FROM mcp_sigrid_dm_total', vetado_total
            );
            EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE sigrid_dm_etl IN SCHEMA %I '
                'REVOKE ALL ON TABLES FROM mcp_sigrid_dm_total', vetado_total
            );
        END IF;
    END LOOP;
END
$$;

-- 5 quinquies a) El perfil RESTRINGIDO (F-141, 2026-10-17): su mitad como DUEÑO.
--
--    Reglas del humano: «ven como el estándar, menos el mayor, menos el mayor
--    analítico, menos la cartera de cobros (pero sí a retenciones)» y
--    «personal también quítalo, y saldos cuenta también»; y, desde F-146
--    (2026-10-21), nada de contabilidad: el esquema entero fuera. Es lo mismo
--    que concede la nocturna (`apply_grants`), aquí para que el grupo nazca ya
--    con su lectura: sus nueve esquemas (`DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS`,
--    un test lo vigila), el privilegio por defecto SIEMPRE en REVOKE (lo que
--    nazca no lo lee hasta que la nocturna lo haya mirado) y el veto de todo
--    esquema del CATÁLOGO que no sea suyo (hoy `contabilidad`, `tesoreria`,
--    `personal`, `raw` y las tres `*_restringida`), como la nocturna. Sin
--    objetos excluidos desde F-146 (`DEFAULT_PERFIL_RESTRINGIDO_EXCLUDED_TABLES`
--    vacía): el mayor y sus saldos caen con su esquema.
--
--    COMO `sigrid_dm_etl`, el mismo concedente que la nocturna: así la nocturna
--    puede revocar lo que se conceda aquí (una vista que filtre, un objeto
--    vigilado). Concedido como administrador, sobreviviría a su REVOKE. Va
--    dentro del tramo `SET ROLE` del 5 ter para que las pertenencias del 5
--    quater y del 5 quinquies b) sigan siendo lo único que hace el administrador.
DO $$
DECLARE
    esquema_r text;
    ajeno_r text;
BEGIN
    FOREACH esquema_r IN ARRAY ARRAY[
        'mart', 'cierre', 'compras', 'maestro', 'retenciones', 'descompuestos',
        'stg', 'aux', '_meta'
    ]
    LOOP
        IF to_regnamespace(esquema_r) IS NOT NULL THEN
            EXECUTE format('GRANT USAGE ON SCHEMA %I TO sigrid_dm_perfil_restringido_ro', esquema_r);
            EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO sigrid_dm_perfil_restringido_ro', esquema_r);
            EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE sigrid_dm_etl IN SCHEMA %I '
                'REVOKE SELECT ON TABLES FROM sigrid_dm_perfil_restringido_ro', esquema_r
            );
        END IF;
    END LOOP;

    FOR ajeno_r IN
        SELECT nspname FROM pg_namespace
        WHERE nspname <> ALL (ARRAY[
                  'mart', 'cierre', 'compras', 'maestro', 'retenciones', 'descompuestos',
                  'stg', 'aux', '_meta'])
          AND nspname <> ALL (ARRAY['information_schema', 'public'])
          AND nspname NOT LIKE 'pg\_%'
        ORDER BY 1
    LOOP
        EXECUTE format(
            'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA %I FROM sigrid_dm_perfil_restringido_ro', ajeno_r
        );
        EXECUTE format(
            'REVOKE ALL PRIVILEGES ON SCHEMA %I FROM sigrid_dm_perfil_restringido_ro', ajeno_r
        );
        EXECUTE format(
            'ALTER DEFAULT PRIVILEGES FOR ROLE sigrid_dm_etl IN SCHEMA %I '
            'REVOKE ALL ON TABLES FROM sigrid_dm_perfil_restringido_ro', ajeno_r
        );
    END LOOP;
END
$$;
RESET ROLE;

-- 5 quater. Las pertenencias del login TOTAL (F-136, 2026-10-13).
--
--    Decisión del humano del 2026-10-12: «tenemos que tener rol total [...] el
--    resto el standar», y «total no incluye raw. siempre fuera». El total lee
--    lo que lee el general más la contabilidad completa del autorizado, y lo
--    lee SOLO por pertenencia: ningún GRANT propio (ni CONNECT, que hereda), y
--    la nocturna (`apply_grants`) le veta `raw` y comprueba que no lo lee.
--
--    Como el ADMINISTRADOR, fuera de `SET ROLE`: es quien tiene ADMIN OPTION
--    sobre los dos grupos; `sigrid_dm_etl` y `sigrid_dm_app` no, y por eso la
--    nocturna no puede darlas, solo verificarlas.
--
--    DENTRO de la transacción y DESPUÉS del 5 ter: el total nunca hereda un
--    general que aún leyera `raw`. `INHERIT TRUE`: lee sin cambiar de rol.
--    `SET FALSE`: no puede hacer `SET ROLE` a los grupos (el MCP lo prohíbe y
--    no le hace falta).
GRANT mcp_sigrid_dm_ro TO mcp_sigrid_dm_total WITH INHERIT TRUE, SET FALSE;
GRANT sigrid_dm_autorizado_ro TO mcp_sigrid_dm_total WITH INHERIT TRUE, SET FALSE;

-- 5 quinquies b) El perfil RESTRINGIDO (F-141): su mitad como ADMINISTRADOR.
--
--    El veto de lo ajeno, otra vez con este concedente (DOS CONCEDENTES, como
--    en el 5 bis y el 5 ter: un REVOKE solo quita lo que concedió quien lo
--    ejecuta), y la ÚNICA concesión al login: ser miembro de su grupo. Como
--    el ADMINISTRADOR, fuera de `SET ROLE`, porque es quien tiene ADMIN OPTION
--    sobre el grupo. Dentro de la transacción y DESPUÉS de los vetos: el login
--    nunca hereda un grupo que aún leyera algo ajeno. `INHERIT TRUE`: lee sin
--    cambiar de rol; `SET FALSE`: no puede hacer `SET ROLE` al grupo.
DO $$
DECLARE
    ajeno_r text;
BEGIN
    FOR ajeno_r IN
        SELECT nspname FROM pg_namespace
        WHERE nspname <> ALL (ARRAY[
                  'mart', 'cierre', 'compras', 'maestro', 'retenciones', 'descompuestos',
                  'stg', 'aux', '_meta'])
          AND nspname <> ALL (ARRAY['information_schema', 'public'])
          AND nspname NOT LIKE 'pg\_%'
        ORDER BY 1
    LOOP
        EXECUTE format(
            'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA %I FROM sigrid_dm_perfil_restringido_ro', ajeno_r
        );
        EXECUTE format(
            'REVOKE ALL PRIVILEGES ON SCHEMA %I FROM sigrid_dm_perfil_restringido_ro', ajeno_r
        );
    END LOOP;
END
$$;
GRANT sigrid_dm_perfil_restringido_ro TO mcp_sigrid_dm_restringido WITH INHERIT TRUE, SET FALSE;

COMMIT;

-- 6. Comprobaciones. Deben salir: los siete roles (`rolsuper = f` en todos;
--    los dos del perfil restringido desde F-141), sigrid_dm_app dentro de
--    sigrid_dm_etl, y los dieciséis esquemas.
SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole
FROM pg_roles
WHERE rolname IN ('sigrid_dm_etl', 'sigrid_dm_app', 'mcp_sigrid_dm_ro',
                  'sigrid_dm_autorizado_ro', 'mcp_sigrid_dm_total',
                  'sigrid_dm_perfil_restringido_ro', 'mcp_sigrid_dm_restringido')
ORDER BY rolname;

SELECT r.rolname AS miembro, g.rolname AS grupo
FROM pg_auth_members AS m
JOIN pg_roles AS r ON r.oid = m.member
JOIN pg_roles AS g ON g.oid = m.roleid
WHERE g.rolname = 'sigrid_dm_etl';

SELECT nspname AS esquema, pg_catalog.pg_get_userbyid(nspowner) AS propietario
FROM pg_namespace
WHERE nspname IN ('raw', 'stg', 'aux', 'mart', '_meta',
                  'cierre', 'compras', 'maestro', 'retenciones', 'personal',
                  'contabilidad', 'contabilidad_restringida', 'descompuestos',
                  'tesoreria', 'tesoreria_restringida', 'compras_restringida')
ORDER BY nspname;

-- F-068: las tablas excluidas NO deben aparecer aquí. CERO filas es el
-- resultado correcto; una fila significa que el MCP las sigue leyendo.
SELECT table_schema, table_name, privilege_type
FROM information_schema.table_privileges
WHERE grantee = 'mcp_sigrid_dm_ro'
  AND table_schema = 'raw'
  AND table_name IN ('emp', 'res')
ORDER BY table_name, privilege_type;

-- F-135: el rol GENERAL no lee ningún esquema vetado. CERO filas en la primera
-- consulta y `lee = f` en las cuatro filas de la segunda es el resultado
-- correcto (`compras_restringida` desde F-138).
SELECT table_schema, table_name, privilege_type
FROM information_schema.table_privileges
WHERE grantee = 'mcp_sigrid_dm_ro'
  AND table_schema IN ('contabilidad_restringida', 'tesoreria_restringida', 'compras_restringida', 'raw')
ORDER BY table_schema, table_name, privilege_type;

SELECT nspname, has_schema_privilege('mcp_sigrid_dm_ro', nspname, 'USAGE') AS lee
FROM pg_namespace
WHERE nspname IN ('contabilidad_restringida', 'tesoreria_restringida', 'compras_restringida', 'raw')
ORDER BY nspname;

-- F-136: el login TOTAL. Deben salir EXACTAMENTE dos pertenencias
-- (`mcp_sigrid_dm_ro` y `sigrid_dm_autorizado_ro`, hereda = t, set_role = f);
-- `raw = f`, `contabilidad_restringida = t`, `contabilidad = t`,
-- `tesoreria_restringida = t` (F-037), `compras_restringida = t` (F-138) y
-- `conecta = t`;
-- y CERO filas en la última: no tiene ninguna concesión propia.
SELECT g.rolname AS grupo, m.inherit_option AS hereda, m.set_option AS set_role,
       m.admin_option AS admin
FROM pg_auth_members AS m
JOIN pg_roles AS r ON r.oid = m.member
JOIN pg_roles AS g ON g.oid = m.roleid
WHERE r.rolname = 'mcp_sigrid_dm_total'
ORDER BY grupo;

SELECT has_schema_privilege('mcp_sigrid_dm_total', 'raw', 'USAGE') AS raw,
       has_schema_privilege('mcp_sigrid_dm_total', 'contabilidad_restringida', 'USAGE')
           AS contabilidad_restringida,
       has_schema_privilege('mcp_sigrid_dm_total', 'contabilidad', 'USAGE') AS contabilidad,
       has_schema_privilege('mcp_sigrid_dm_total', 'tesoreria_restringida', 'USAGE')
           AS tesoreria_restringida,
       has_schema_privilege('mcp_sigrid_dm_total', 'compras_restringida', 'USAGE')
           AS compras_restringida,
       has_database_privilege('mcp_sigrid_dm_total', current_database(), 'CONNECT') AS conecta;

SELECT table_schema, table_name, privilege_type
FROM information_schema.table_privileges
WHERE grantee = 'mcp_sigrid_dm_total'
ORDER BY table_schema, table_name, privilege_type;

-- F-141: el login del perfil RESTRINGIDO. Debe salir EXACTAMENTE una
-- pertenencia (`sigrid_dm_perfil_restringido_ro`, hereda = t, set_role = f).
-- Luego `t` en sus nueve esquemas y `f` en `contabilidad` (F-146), `tesoreria`,
-- `personal`, `raw` y las tres `*_restringida`; `f` en las cuatro tablas de
-- `contabilidad` y `t` en `compras.vencimientos` (vacío si el objeto aún no
-- existe: base recién creada); `conecta = t`; y CERO filas en la última: el
-- login no tiene ninguna concesión propia.
SELECT g.rolname AS grupo, m.inherit_option AS hereda, m.set_option AS set_role,
       m.admin_option AS admin
FROM pg_auth_members AS m
JOIN pg_roles AS r ON r.oid = m.member
JOIN pg_roles AS g ON g.oid = m.roleid
WHERE r.rolname = 'mcp_sigrid_dm_restringido'
ORDER BY grupo;

SELECT has_schema_privilege('mcp_sigrid_dm_restringido', 'mart', 'USAGE') AS mart,
       has_schema_privilege('mcp_sigrid_dm_restringido', 'cierre', 'USAGE') AS cierre,
       has_schema_privilege('mcp_sigrid_dm_restringido', 'compras', 'USAGE') AS compras,
       has_schema_privilege('mcp_sigrid_dm_restringido', 'maestro', 'USAGE') AS maestro,
       has_schema_privilege('mcp_sigrid_dm_restringido', 'retenciones', 'USAGE') AS retenciones,
       has_schema_privilege('mcp_sigrid_dm_restringido', 'descompuestos', 'USAGE') AS descompuestos,
       has_schema_privilege('mcp_sigrid_dm_restringido', 'stg', 'USAGE') AS stg,
       has_schema_privilege('mcp_sigrid_dm_restringido', 'aux', 'USAGE') AS aux,
       has_schema_privilege('mcp_sigrid_dm_restringido', '_meta', 'USAGE') AS meta;

SELECT has_schema_privilege('mcp_sigrid_dm_restringido', 'tesoreria', 'USAGE') AS tesoreria,
       has_schema_privilege('mcp_sigrid_dm_restringido', 'contabilidad', 'USAGE') AS contabilidad,
       has_schema_privilege('mcp_sigrid_dm_restringido', 'personal', 'USAGE') AS personal,
       has_schema_privilege('mcp_sigrid_dm_restringido', 'raw', 'USAGE') AS raw,
       has_schema_privilege('mcp_sigrid_dm_restringido', 'contabilidad_restringida', 'USAGE')
           AS contabilidad_restringida,
       has_schema_privilege('mcp_sigrid_dm_restringido', 'tesoreria_restringida', 'USAGE')
           AS tesoreria_restringida,
       has_schema_privilege('mcp_sigrid_dm_restringido', 'compras_restringida', 'USAGE')
           AS compras_restringida;

SELECT has_table_privilege('mcp_sigrid_dm_restringido', to_regclass('contabilidad.mayor'), 'SELECT')
           AS mayor,
       has_table_privilege('mcp_sigrid_dm_restringido', to_regclass('contabilidad.saldos_cuenta_mes'), 'SELECT')
           AS saldos_cuenta_mes,
       has_table_privilege('mcp_sigrid_dm_restringido', to_regclass('contabilidad.plan_cuentas'), 'SELECT')
           AS plan_cuentas,
       has_table_privilege('mcp_sigrid_dm_restringido', to_regclass('contabilidad.apuntes_restringidos_mes'), 'SELECT')
           AS apuntes_restringidos_mes,
       has_table_privilege('mcp_sigrid_dm_restringido', to_regclass('compras.vencimientos'), 'SELECT')
           AS vencimientos,
       has_database_privilege('mcp_sigrid_dm_restringido', current_database(), 'CONNECT') AS conecta;

SELECT table_schema, table_name, privilege_type
FROM information_schema.table_privileges
WHERE grantee = 'mcp_sigrid_dm_restringido'
ORDER BY table_schema, table_name, privilege_type;
