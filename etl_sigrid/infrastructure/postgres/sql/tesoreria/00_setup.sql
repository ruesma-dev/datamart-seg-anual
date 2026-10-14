-- etl_sigrid/infrastructure/postgres/sql/tesoreria/00_setup.sql
-- ============================================================================
-- F-037 · SCHEMA tesoreria (1/4): los dos esquemas, sus funciones y sus tablas
--
-- LA CARTERA DE COBROS Y PAGOS (fase 1): una fila por EFECTO de `raw.pag`
-- (sentido PAGO) y de `raw.cob` (sentido COBRO), tal cual. Es un HECHO de
-- Sigrid, no un calculo: la fase 2 (devengo pendiente, plazos, retenciones de
-- contrato) y cualquier conversion devengo -> caja quedan FUERA.
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
