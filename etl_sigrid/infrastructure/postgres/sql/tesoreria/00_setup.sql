-- etl_sigrid/infrastructure/postgres/sql/tesoreria/00_setup.sql
-- ============================================================================
-- F-037 · SCHEMA tesoreria (1/4): los dos esquemas, sus funciones y sus tablas
--
-- LA CARTERA DE COBROS Y PAGOS (fase 1): una fila por EFECTO de `raw.pag`
-- (sentido PAGO) y de `raw.cob` (sentido COBRO), tal cual. Es un HECHO de
-- Sigrid, no un calculo. La fase 2 (F-140: devengo pendiente, plazos y
-- condiciones de contrato, catalogo de hipotesis) va al final de este fichero;
-- la conversion devengo -> caja sigue FUERA: la hace la IA, declarandola.
--
-- Modulo independiente, como `contabilidad`: lee SOLO de `raw.*` y de la vista
-- `maestro.centros_coste` (el puente centro de coste -> obra, SQL puro sobre
-- `raw`). Por eso `build_tesoreria` declara solo `ingest_raw`. Nadie depende de
-- el en `depends_on`: `compras.vencimientos` es una VISTA de `tesoreria.efectos`
-- y solo necesita que la tabla EXISTA (D9).
--
-- DOS ESQUEMAS, patron de F-135. Los pagos de PERSONAL (nominas, embargos,
-- cuotas: decision del humano del 2026-10-13, «los pagos de nominas deben
-- quedar restringidos») viven FISICAMENTE en `tesoreria_restringida`, que el
-- rol estandar nunca recibe; la general, `tesoreria`, no los tiene. El criterio,
-- en `etl_sigrid/domain/tesoreria.py`.
--
-- Tres tablas, en este orden (cada fichero la suya):
--   01_efectos_completo.sql          tesoreria_restringida.efectos       todos, con la marca
--   02_efectos_general.sql           tesoreria.efectos                    sin los de personal
--   03_efectos_restringidos_mes.sql  tesoreria.efectos_restringidos_mes  cuantos faltan, sin importes
--
-- NINGUNA TABLA SE DROPEA (R14): `CREATE TABLE IF NOT EXISTS` aqui y
-- `TRUNCATE` + `INSERT` en cada build, el patron de `personal`. Un `DROP ...
-- CASCADE` de `tesoreria.efectos` se llevaria por delante la vista
-- `compras.vencimientos` y todo lo que cuelga de ella, y los GRANT. Una columna
-- nueva va con `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (precedente F-101).
--
-- Sin `GRANT` ni `ALTER DEFAULT PRIVILEGES`: los permisos son de `apply_grants`,
-- que cada noche concede `tesoreria`, veta `tesoreria_restringida` al rol
-- estandar y la concede al autorizado (F-135, F-136).
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS tesoreria;
-- Lo crea el dueno de los objetos (`sigrid_dm_etl`, por PG_SET_ROLE) y nace sin
-- ninguna concesion al rol estandar: `apply_grants` le revoca USAGE cada noche.
CREATE SCHEMA IF NOT EXISTS tesoreria_restringida;

-- La fecha de Sigrid es un entero AAAAMMDD: 0, NULL o invalida -> NULL. COPIA
-- de `compras.fn_sigrid_date` (un test compara los cuerpos): un modulo no
-- depende de otro que se construye DESPUES (compras lee de este).
CREATE OR REPLACE FUNCTION tesoreria.fn_fecha(d BIGINT)
RETURNS DATE
LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
    IF d IS NULL OR d = 0 THEN
        RETURN NULL;
    END IF;
    RETURN to_date(d::TEXT, 'YYYYMMDD');
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END $$;

COMMENT ON FUNCTION tesoreria.fn_fecha(BIGINT) IS
'Convierte una fecha entera de Sigrid (AAAAMMDD) a DATE. NULL para 0, NULL o invalida. Copia deliberada de compras.fn_sigrid_date: tesoreria no depende de ningun otro esquema construido.';

-- Serie documental = prefijo alfabetico del codigo ('FR26/06051_01' -> 'FR').
-- COPIA de `compras.fn_serie` (R6; un test compara los cuerpos).
CREATE OR REPLACE FUNCTION tesoreria.fn_serie(cod TEXT)
RETURNS TEXT
LANGUAGE sql IMMUTABLE AS $$
    SELECT UPPER(COALESCE(substring(cod FROM '^[A-Za-z]+'), ''));
$$;

COMMENT ON FUNCTION tesoreria.fn_serie(TEXT) IS
'Serie documental: el prefijo alfabetico del codigo, en mayusculas. Copia deliberada de compras.fn_serie.';


-- ---------------------------------------------------------------------------
-- tesoreria_restringida.efectos — LA CARTERA COMPLETA (R5-R9)
--
-- Una fila por efecto de `raw.pag` y `raw.cob` (256.952 + 21.914 el
-- 2026-10-13), con `restringido` y `motivo_restriccion`. La leen el grupo
-- autorizado y el login total; el estandar, nunca. Las columnas que hereda
-- `compras.vencimientos` llevan los TIPOS de la tabla de F-080 (la vista los
-- publica tal cual: un test fija la lista).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tesoreria_restringida.efectos (
    efecto_id               INTEGER       PRIMARY KEY,
    sentido                 VARCHAR(5)    NOT NULL,
    empresa_id              INTEGER,
    codigo_efecto           VARCHAR(24),
    descripcion_efecto      VARCHAR(128),
    serie_efecto            TEXT,
    documento_id            INTEGER,
    codigo_documento        VARCHAR(24),
    tipo_documento          INTEGER,
    es_factura_compra       BOOLEAN       NOT NULL,
    tercero_id              INTEGER,
    tercero_nombre          VARCHAR(128),
    tercero_cif             VARCHAR(24),
    fecha_emision           DATE,
    fecha_vencimiento       DATE,
    fecha_real              DATE,
    importe                 NUMERIC(18,2) NOT NULL,
    importe_flujo           NUMERIC(18,2) NOT NULL,
    estado_tesoreria        VARCHAR(10)   NOT NULL,
    estado_codigo           INTEGER,
    estado_sigrid           VARCHAR(48),
    efecto_anulado          BOOLEAN,
    fecha_anulacion         DATE,
    medio_pago_id           INTEGER,
    medio_pago              VARCHAR(48),
    naturaleza_pago_id      INTEGER,
    naturaleza_pago         VARCHAR(48),
    cuenta_contable_id      INTEGER,
    cuenta_contable         VARCHAR(24),
    cuenta_contable_nombre  VARCHAR(128),
    banco_id                INTEGER,
    banco                   VARCHAR(48),
    sucursal_id             INTEGER,
    sucursal                VARCHAR(48),
    retencion_id            INTEGER,
    centro_coste_id         INTEGER,
    obra_id                 INTEGER,
    codigo_obra             VARCHAR(24),
    nombre_obra             VARCHAR(128),
    remesa_id               INTEGER,
    codigo_remesa           VARCHAR(24),
    fecha_remesa            DATE,
    importe_remesa          NUMERIC,
    previsto_antiguo        BOOLEAN       NOT NULL,
    restringido             BOOLEAN       NOT NULL,
    motivo_restriccion      VARCHAR(24)
);

CREATE INDEX IF NOT EXISTS idx_tesr_efe_sentido   ON tesoreria_restringida.efectos (sentido);
CREATE INDEX IF NOT EXISTS idx_tesr_efe_estado    ON tesoreria_restringida.efectos (estado_tesoreria);
CREATE INDEX IF NOT EXISTS idx_tesr_efe_vto       ON tesoreria_restringida.efectos (fecha_vencimiento);
CREATE INDEX IF NOT EXISTS idx_tesr_efe_tercero   ON tesoreria_restringida.efectos (tercero_id);
CREATE INDEX IF NOT EXISTS idx_tesr_efe_obra      ON tesoreria_restringida.efectos (obra_id);
CREATE INDEX IF NOT EXISTS idx_tesr_efe_documento ON tesoreria_restringida.efectos (documento_id);
CREATE INDEX IF NOT EXISTS idx_tesr_efe_remesa    ON tesoreria_restringida.efectos (remesa_id);


-- ---------------------------------------------------------------------------
-- tesoreria.efectos — LA CARTERA GENERAL (R10, R11)
--
-- Las filas de la completa que NO son de personal, con sus mismas columnas en
-- el mismo orden salvo `restringido` y `motivo_restriccion`. De ella cuelga la
-- vista `compras.vencimientos` (D1): por eso no se dropea nunca.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tesoreria.efectos (
    efecto_id               INTEGER       PRIMARY KEY,
    sentido                 VARCHAR(5)    NOT NULL,
    empresa_id              INTEGER,
    codigo_efecto           VARCHAR(24),
    descripcion_efecto      VARCHAR(128),
    serie_efecto            TEXT,
    documento_id            INTEGER,
    codigo_documento        VARCHAR(24),
    tipo_documento          INTEGER,
    es_factura_compra       BOOLEAN       NOT NULL,
    tercero_id              INTEGER,
    tercero_nombre          VARCHAR(128),
    tercero_cif             VARCHAR(24),
    fecha_emision           DATE,
    fecha_vencimiento       DATE,
    fecha_real              DATE,
    importe                 NUMERIC(18,2) NOT NULL,
    importe_flujo           NUMERIC(18,2) NOT NULL,
    estado_tesoreria        VARCHAR(10)   NOT NULL,
    estado_codigo           INTEGER,
    estado_sigrid           VARCHAR(48),
    efecto_anulado          BOOLEAN,
    fecha_anulacion         DATE,
    medio_pago_id           INTEGER,
    medio_pago              VARCHAR(48),
    naturaleza_pago_id      INTEGER,
    naturaleza_pago         VARCHAR(48),
    cuenta_contable_id      INTEGER,
    cuenta_contable         VARCHAR(24),
    cuenta_contable_nombre  VARCHAR(128),
    banco_id                INTEGER,
    banco                   VARCHAR(48),
    sucursal_id             INTEGER,
    sucursal                VARCHAR(48),
    retencion_id            INTEGER,
    centro_coste_id         INTEGER,
    obra_id                 INTEGER,
    codigo_obra             VARCHAR(24),
    nombre_obra             VARCHAR(128),
    remesa_id               INTEGER,
    codigo_remesa           VARCHAR(24),
    fecha_remesa            DATE,
    importe_remesa          NUMERIC,
    previsto_antiguo        BOOLEAN       NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tes_efe_sentido   ON tesoreria.efectos (sentido);
CREATE INDEX IF NOT EXISTS idx_tes_efe_estado    ON tesoreria.efectos (estado_tesoreria);
CREATE INDEX IF NOT EXISTS idx_tes_efe_vto       ON tesoreria.efectos (fecha_vencimiento);
CREATE INDEX IF NOT EXISTS idx_tes_efe_tercero   ON tesoreria.efectos (tercero_id);
CREATE INDEX IF NOT EXISTS idx_tes_efe_obra      ON tesoreria.efectos (obra_id);
CREATE INDEX IF NOT EXISTS idx_tes_efe_documento ON tesoreria.efectos (documento_id);
CREATE INDEX IF NOT EXISTS idx_tes_efe_remesa    ON tesoreria.efectos (remesa_id);


-- ---------------------------------------------------------------------------
-- tesoreria.efectos_restringidos_mes — CUANTOS faltan, SIN importes (R13, D6)
--
-- Empresa x sentido x anio x mes de vencimiento x estado. Un importe aqui seria
-- la nomina neta mensual, que es lo que se protege. Sin vencimiento (o sin
-- empresa), 0: la clave primaria no admite NULL.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tesoreria.efectos_restringidos_mes (
    empresa_id        INTEGER     NOT NULL,
    sentido           VARCHAR(5)  NOT NULL,
    anio              INTEGER     NOT NULL,
    mes               INTEGER     NOT NULL,
    estado_tesoreria  VARCHAR(10) NOT NULL,
    num_efectos       BIGINT      NOT NULL,
    PRIMARY KEY (empresa_id, sentido, anio, mes, estado_tesoreria)
);


-- ============================================================================
-- F-140 · LA FASE 2: LOS INGREDIENTES PARA PASAR EL DEVENGO A CAJA
--
-- EL DATAMART NO CONVIERTE DEVENGO EN CAJA (regla del humano). Publica los
-- ingredientes -las formas de pago y cobro con su formula leida, las
-- condiciones de los contratos, el devengo pendiente de cada obra descontado
-- lo ejecutado desde su version- y el CATALOGO de hipotesis de conversion con
-- sus valores por defecto y por obra. Ninguna tabla tiene una columna de caja
-- (un plazo, una retencion o un IVA aplicados a un devengo): lo prueba
-- `tests/test_f140_sql.py` con `PATRON_COLUMNA_DE_CAJA` del dominio.
--
-- Mismo patron que la cartera: `CREATE TABLE IF NOT EXISTS` aqui y `TRUNCATE`
-- + `INSERT` en cada build, sin `DROP` ni `GRANT` (el esquema ya lo concede y
-- lo veta entero `apply_grants`).
-- ============================================================================

-- ---------------------------------------------------------------------------
-- La formula de plazo (`auxpag.formul`, `auxcob.formul`): R7, R8
--
-- Tokens separados por blancos; `N` = dias de un vencimiento y `NR` = dias del
-- efecto de RETENCION. Lo que no casa con esa gramatica (un token ajeno, dos
-- `NR`, vacia o NULL) NO se interpreta: falla cerrado. Mismos literales que
-- `etl_sigrid/domain/proyeccion_caja.py` (`REGEX_TOKEN_DIAS`,
-- `REGEX_TOKEN_RETENCION`, `SEPARADOR_TOKENS`); un test los compara.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION tesoreria.fn_plazo_reconocido(f TEXT)
RETURNS BOOLEAN
LANGUAGE sql IMMUTABLE AS $$
    SELECT f IS NOT NULL
       AND btrim(f) <> ''
       AND NOT EXISTS (
           SELECT 1
           FROM unnest(regexp_split_to_array(btrim(f), '\s+')) AS u(t)
           WHERE t !~ '^[0-9]+$' AND t !~ '^[0-9]+R$'
       )
       AND (SELECT count(*)
            FROM unnest(regexp_split_to_array(btrim(f), '\s+')) AS u(t)
            WHERE t ~ '^[0-9]+R$') <= 1;
$$;

COMMENT ON FUNCTION tesoreria.fn_plazo_reconocido(TEXT) IS
'F-140. Cierto si la formula de plazo de Sigrid casa con su gramatica: tokens N (dias de un vencimiento) y como mucho un NR (dias de la retencion). Vacia, NULL, un token ajeno o dos NR: falso (falla cerrado).';

-- Los dias de cada vencimiento, EN EL ORDEN ESCRITO; sin reconocer, vacio.
CREATE OR REPLACE FUNCTION tesoreria.fn_plazo_dias(f TEXT)
RETURNS INT[]
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN tesoreria.fn_plazo_reconocido(f)
                THEN ARRAY(SELECT u.t::INT
                           FROM unnest(regexp_split_to_array(btrim(f), '\s+'))
                                WITH ORDINALITY AS u(t, n)
                           WHERE u.t ~ '^[0-9]+$' ORDER BY u.n)
                ELSE '{}'::INT[] END;
$$;

COMMENT ON FUNCTION tesoreria.fn_plazo_dias(TEXT) IS
'F-140. Los dias de cada vencimiento de una formula de plazo, en el orden escrito ("30 60 90" da {30,60,90}). Vacio si no tiene ninguno o si la formula no se reconoce.';

-- Los dias del efecto de retencion (`NR`); sin `NR` o sin reconocer, NULL.
CREATE OR REPLACE FUNCTION tesoreria.fn_plazo_dias_retencion(f TEXT)
RETURNS INT
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN tesoreria.fn_plazo_reconocido(f)
                THEN (SELECT left(t, -1)::INT
                      FROM unnest(regexp_split_to_array(btrim(f), '\s+')) AS u(t)
                      WHERE t ~ '^[0-9]+R$') END;
$$;

COMMENT ON FUNCTION tesoreria.fn_plazo_dias_retencion(TEXT) IS
'F-140. Los dias del efecto de retencion de una formula de plazo ("120 450R" da 450). NULL si no tiene retencion o si la formula no se reconoce.';


-- ---------------------------------------------------------------------------
-- El catalogo de hipotesis (R1, R4) y los valores por obra del YAML (R3)
--
-- Los carga el sub-paso `hipotesis_carga` (Python) desde
-- `config/hipotesis_caja.yaml`, validado por el dominio, en UNA transaccion.
-- Los valores van en JSONB: una hipotesis es un DIAS, un PORCENTAJE, una
-- OPCION, un BOOLEANO o un MAPA_DIAS.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tesoreria.hipotesis_caja (
    codigo            VARCHAR(3)   PRIMARY KEY,
    sentido           VARCHAR(5)   NOT NULL,
    descripcion       TEXT         NOT NULL,
    unidad            VARCHAR(10)  NOT NULL,
    valor_defecto     JSONB NOT NULL,
    opciones          JSONB,
    fuente_defecto    TEXT         NOT NULL,
    ingrediente       TEXT,
    validado          BOOLEAN      NOT NULL,
    fecha_validacion  DATE,
    admite_obra       BOOLEAN      NOT NULL
);

CREATE TABLE IF NOT EXISTS tesoreria.hipotesis_caja_manual (
    clave_obra  VARCHAR(40)  NOT NULL,
    codigo      VARCHAR(3)   NOT NULL,
    valor       JSONB NOT NULL,
    motivo      TEXT         NOT NULL,
    fecha       DATE         NOT NULL,
    PRIMARY KEY (clave_obra, codigo)
);

-- El valor RESUELTO por obra (R5): MANUAL > SIGRID > DEFECTO.
CREATE TABLE IF NOT EXISTS tesoreria.hipotesis_caja_obra (
    obra_id     INTEGER      NOT NULL,
    empresa_id  INTEGER,
    clave_obra  VARCHAR(40),
    codigo      VARCHAR(3)   NOT NULL,
    valor       JSONB NOT NULL,
    nivel       VARCHAR(7)   NOT NULL,
    fuente      VARCHAR(7)   NOT NULL,
    motivo      TEXT,
    PRIMARY KEY (obra_id, codigo)
);


-- ---------------------------------------------------------------------------
-- Las condiciones pactadas (R10, R11): una fila por contrato
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tesoreria.condiciones_contrato_compra (
    contrato_id                     INTEGER       PRIMARY KEY,
    codigo_contrato                 VARCHAR(24),
    empresa_id                      INTEGER,
    obra_id                         INTEGER,
    codigo_obra                     VARCHAR(24),
    proveedor_id                    INTEGER,
    proveedor_nombre                VARCHAR(128),
    estado_id                       INTEGER,
    estado                          VARCHAR(48),
    importe_base                    NUMERIC(18,2),
    importe_iva                     NUMERIC(18,2),
    forma_pago_id                   INTEGER,
    forma_pago_codigo               VARCHAR(16),
    forma_pago                      VARCHAR(48),
    medio_pago                      VARCHAR(48),
    plazo_formula                   TEXT,
    dias_vencimientos               INT[],
    num_vencimientos                INTEGER,
    dias_retencion                  INTEGER,
    formula_reconocida              BOOLEAN       NOT NULL,
    proveedor_dias_fijos_pago       VARCHAR(24),
    proveedor_meses_sin_pago        VARCHAR(24),
    retencion_garantia_porcentaje   NUMERIC(10,4),
    retencion_garantia_concepto     VARCHAR(128),
    retencion_garantia_clase        INTEGER
);

CREATE INDEX IF NOT EXISTS idx_tes_ccc_obra      ON tesoreria.condiciones_contrato_compra (obra_id);
CREATE INDEX IF NOT EXISTS idx_tes_ccc_proveedor ON tesoreria.condiciones_contrato_compra (proveedor_id);

CREATE TABLE IF NOT EXISTS tesoreria.condiciones_contrato_cliente (
    contrato_cliente_id       INTEGER       PRIMARY KEY,
    codigo_contrato           VARCHAR(24),
    descripcion               VARCHAR(128),
    empresa_id                INTEGER,
    obra_id                   INTEGER,
    codigo_obra               VARCHAR(24),
    cliente_id                INTEGER,
    cliente_nombre            VARCHAR(128),
    forma_cobro_id            INTEGER,
    forma_cobro_codigo        VARCHAR(16),
    forma_cobro               VARCHAR(48),
    medio_cobro               VARCHAR(48),
    plazo_formula             TEXT,
    dias_vencimientos         INT[],
    num_vencimientos          INTEGER,
    dias_retencion            INTEGER,
    formula_reconocida        BOOLEAN       NOT NULL,
    retencion_porcentaje      NUMERIC(10,4),
    retencion_fuente          VARCHAR(16),
    retencion_concepto        VARCHAR(128),
    plazo_retencion_meses     NUMERIC(10,2),
    plazo_garantia_meses      NUMERIC(10,2),
    fecha_inicio_garantia     DATE
);

CREATE INDEX IF NOT EXISTS idx_tes_ccl_obra ON tesoreria.condiciones_contrato_cliente (obra_id);


-- ---------------------------------------------------------------------------
-- El devengo pendiente (R12-R15): por partida, por obra y mes, y su corte
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tesoreria.devengo_pendiente_partida (
    obra_id               INTEGER       NOT NULL,
    empresa_id            INTEGER,
    clave_obra            VARCHAR(40),
    partida_id            INTEGER       NOT NULL,
    codigo_partida        VARCHAR(24),
    concepto              VARCHAR(5)    NOT NULL,
    categoria             VARCHAR(8),
    version_master        INTEGER       NOT NULL,
    tipo_master           VARCHAR(20),
    mes_version           DATE,
    mes_ultimo_cierre     DATE,
    plan_desde_version    NUMERIC(18,2) NOT NULL,
    plan_intervalo        NUMERIC(18,2) NOT NULL,
    ejecutado_intervalo   NUMERIC(18,2) NOT NULL,
    plan_restante         NUMERIC(18,2) NOT NULL,
    pendiente             NUMERIC(18,2) NOT NULL,
    sobre_ejecutado       NUMERIC(18,2) NOT NULL,
    PRIMARY KEY (obra_id, partida_id, concepto)
);

CREATE TABLE IF NOT EXISTS tesoreria.devengo_pendiente_obra_mes (
    obra_id                      INTEGER       NOT NULL,
    empresa_id                   INTEGER,
    clave_obra                   VARCHAR(40),
    anio_mes                     DATE          NOT NULL,
    concepto                     VARCHAR(5)    NOT NULL,
    categoria                    VARCHAR(8)    NOT NULL,
    version_master               INTEGER       NOT NULL,
    mes_ultimo_cierre            DATE,
    importe_plan_restante        NUMERIC(18,2) NOT NULL,
    importe_pendiente            NUMERIC(18,2) NOT NULL,
    importe_retraso_sin_perfil   NUMERIC(18,2) NOT NULL,
    num_partidas                 INTEGER       NOT NULL,
    mes_pasado_sin_cierre        BOOLEAN       NOT NULL,
    PRIMARY KEY (obra_id, anio_mes, concepto, categoria)
);

CREATE TABLE IF NOT EXISTS tesoreria.devengo_corte_obra (
    obra_id                       INTEGER       NOT NULL,
    empresa_id                    INTEGER,
    clave_obra                    VARCHAR(40),
    concepto                      VARCHAR(5)    NOT NULL,
    version_master                INTEGER       NOT NULL,
    tipo_master                   VARCHAR(20),
    mes_version                   DATE,
    mes_ultimo_cierre             DATE,
    primer_mes_pendiente          DATE,
    num_versiones_pendientes      INTEGER       NOT NULL,
    num_partidas                  INTEGER       NOT NULL,
    plan_desde_version            NUMERIC(18,2) NOT NULL,
    plan_intervalo                NUMERIC(18,2) NOT NULL,
    ejecutado_intervalo           NUMERIC(18,2) NOT NULL,
    plan_restante                 NUMERIC(18,2) NOT NULL,
    pendiente                     NUMERIC(18,2) NOT NULL,
    sobre_ejecutado               NUMERIC(18,2) NOT NULL,
    adelantado                    NUMERIC(18,2) NOT NULL,
    retrasado                     NUMERIC(18,2) NOT NULL,
    ejecutado_sin_plan            NUMERIC(18,2) NOT NULL,
    retraso_sin_perfil            NUMERIC(18,2) NOT NULL,
    real_origen_corte             NUMERIC(18,2) NOT NULL,
    plan_total                    NUMERIC(18,2) NOT NULL,
    cartera_viva                  NUMERIC(18,2) NOT NULL,
    cartera_emitida_tras_cierre   NUMERIC(18,2) NOT NULL,
    PRIMARY KEY (obra_id, concepto)
);
