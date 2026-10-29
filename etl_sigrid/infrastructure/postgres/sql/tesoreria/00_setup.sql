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

-- F-140 (D10-A): por que via se asigno la obra (CENTRO, CONTRATO,
-- FACTURA_CABECERA, FACTURA_LINEAS). Con ALTER, como F-101: queda AL FINAL en
-- la base de hoy y en una nueva, y `compras.vencimientos` no la ve.
ALTER TABLE tesoreria_restringida.efectos ADD COLUMN IF NOT EXISTS obra_via VARCHAR(16);


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

-- F-140 (D10-A): la misma columna, al final, copiada de la completa por `02`.
ALTER TABLE tesoreria.efectos ADD COLUMN IF NOT EXISTS obra_via VARCHAR(16);


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
-- Los coeficientes del contrato con el cliente (`raw.obrctr.coestr`): F-150, R7, R8
--
-- Una LINEA por concepto (`\r\n`), cada una `CODIGO|etiqueta|valor||base`; se
-- lee POR CODIGO (campo 1) y el valor es el campo 3. GG y BI van a sus clases,
-- control de calidad y seguridad y salud a `otros`, la baja de adjudicacion a
-- `baja` y las retenciones `RET*` a `retencion`, que NO es coeficiente. Lo que
-- no se entiende (un codigo desconocido, un valor no numerico) da NULL entero:
-- falla cerrado y la partida cae al master. Vacio o NULL: NULL (sin dato).
-- Mismos literales que `etl_sigrid/domain/proyeccion_caja.py`
-- (`SEPARADOR_LINEAS`, `SEPARADOR_CAMPOS`, `REGEX_PORCENTAJE_COEF`,
-- `CLASE_POR_CODIGO`); `tests/test_f150_sql.py` los compara.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION tesoreria.fn_coeficientes(f TEXT)
RETURNS NUMERIC[]
LANGUAGE sql IMMUTABLE AS $$
    WITH lineas AS (
        SELECT split_part(l.t, '|', 1) AS codigo,
               btrim(split_part(l.t, '|', 3)) AS valor
        FROM unnest(regexp_split_to_array(f, '\r?\n')) AS u(t0)
        CROSS JOIN LATERAL (SELECT btrim(u.t0) AS t) AS l
        WHERE btrim(u.t0) <> ''
    ),
    clasificadas AS (
        SELECT CASE codigo
                   WHEN 'COEF_RECGG' THEN 'gg'
                   WHEN 'COEF_RECBI' THEN 'bi'
                   WHEN 'COEF_RECCC' THEN 'otros'
                   WHEN 'COEF_RECSYS' THEN 'otros'
                   WHEN 'COEF_DESADJ' THEN 'baja'
                   WHEN 'RETN' THEN 'retencion'
                   WHEN 'RETESP' THEN 'retencion'
                   WHEN 'RETNT' THEN 'retencion'
               END AS clase,
               CASE WHEN valor ~ '^-?[0-9]+(\.[0-9]+)?$' THEN valor::NUMERIC END AS v
        FROM lineas
    )
    SELECT CASE WHEN count(*) > 0 AND count(*) = count(clase) AND count(*) = count(v)
                THEN ARRAY[
                    sum(v) FILTER (WHERE clase = 'gg'),
                    sum(v) FILTER (WHERE clase = 'bi'),
                    sum(v) FILTER (WHERE clase = 'otros'),
                    sum(v) FILTER (WHERE clase = 'baja'),
                    sum(v) FILTER (WHERE clase = 'retencion')
                ] END
    FROM clasificadas;
$$;

COMMENT ON FUNCTION tesoreria.fn_coeficientes(TEXT) IS
'F-150. Los coeficientes de coestr de un contrato con el cliente, en puntos: {gg, bi, otros, baja, retencion}, cada uno la suma de sus lineas o NULL si no tiene. Una linea por concepto (CODIGO|etiqueta|valor||base), leida por codigo. NULL entero si un codigo es desconocido, un valor no es numero, o coestr esta vacio o es NULL: falla cerrado.';

-- Cierto si `coestr` se entiende entero (y tiene alguna linea).
CREATE OR REPLACE FUNCTION tesoreria.fn_coeficientes_reconocidos(f TEXT)
RETURNS BOOLEAN
LANGUAGE sql IMMUTABLE AS $$
    SELECT tesoreria.fn_coeficientes(f) IS NOT NULL;
$$;

COMMENT ON FUNCTION tesoreria.fn_coeficientes_reconocidos(TEXT) IS
'F-150. Cierto si el coestr de un contrato con el cliente se reconoce entero: todas sus lineas con un codigo conocido y un valor numerico. Vacio, NULL, un codigo desconocido o un valor no numerico: falso.';


-- ---------------------------------------------------------------------------
-- El catalogo de hipotesis (R1, R4) y los valores por obra del YAML (R3)
--
-- Los carga el sub-paso `hipotesis_carga` (Python) desde
-- `config/hipotesis_caja.yaml`, validado por el dominio, en UNA transaccion.
-- Los valores van en JSONB: una hipotesis es un DIAS, un PORCENTAJE, una
-- OPCION, un BOOLEANO, un MAPA_DIAS o un PERFIL_MESES (F-150).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tesoreria.hipotesis_caja (
    codigo            VARCHAR(3)   PRIMARY KEY,
    sentido           VARCHAR(5)   NOT NULL,
    descripcion       TEXT         NOT NULL,
    unidad            VARCHAR(20)  NOT NULL,
    valor_defecto     JSONB NOT NULL,
    opciones          JSONB,
    fuente_defecto    TEXT         NOT NULL,
    ingrediente       TEXT,
    validado          BOOLEAN      NOT NULL,
    fecha_validacion  DATE,
    admite_obra       BOOLEAN      NOT NULL
);

-- F-150 (R27): `unidad` admite PERFIL_MESES (12 caracteres) en la tabla que ya
-- existe con VARCHAR(10). Ensanchar un VARCHAR no reescribe la tabla y repetirlo
-- con el mismo tipo no hace nada: idempotente.
ALTER TABLE tesoreria.hipotesis_caja ALTER COLUMN unidad TYPE VARCHAR(20);
-- F-150 (R1): el paso de la receta en que se aplica cada hipotesis. Admite NULL
-- solo para poder anadirla a la tabla con filas; la carga la llena SIEMPRE (el
-- dominio la exige).
ALTER TABLE tesoreria.hipotesis_caja ADD COLUMN IF NOT EXISTS paso_receta VARCHAR(12);

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

-- F-150 (R8, R18): los coeficientes de `coestr` y el IVA del contrato, al final
-- y con ALTER (la tabla ya existe con filas; precedente F-101).
ALTER TABLE tesoreria.condiciones_contrato_cliente ADD COLUMN IF NOT EXISTS coeficientes_texto TEXT;
ALTER TABLE tesoreria.condiciones_contrato_cliente ADD COLUMN IF NOT EXISTS coeficientes_reconocidos BOOLEAN;
ALTER TABLE tesoreria.condiciones_contrato_cliente ADD COLUMN IF NOT EXISTS coeficiente_gg NUMERIC(9,4);
ALTER TABLE tesoreria.condiciones_contrato_cliente ADD COLUMN IF NOT EXISTS coeficiente_bi NUMERIC(9,4);
ALTER TABLE tesoreria.condiciones_contrato_cliente ADD COLUMN IF NOT EXISTS coeficiente_otros NUMERIC(9,4);
ALTER TABLE tesoreria.condiciones_contrato_cliente ADD COLUMN IF NOT EXISTS coeficiente_baja NUMERIC(9,4);
ALTER TABLE tesoreria.condiciones_contrato_cliente ADD COLUMN IF NOT EXISTS retencion_coestr NUMERIC(9,4);
ALTER TABLE tesoreria.condiciones_contrato_cliente ADD COLUMN IF NOT EXISTS coeficiente_contrato NUMERIC(12,6);
ALTER TABLE tesoreria.condiciones_contrato_cliente ADD COLUMN IF NOT EXISTS iva_id INTEGER;
ALTER TABLE tesoreria.condiciones_contrato_cliente ADD COLUMN IF NOT EXISTS iva_porcentaje NUMERIC(9,4);


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

-- F-150 (R11, R19): el contrato de la partida, su coeficiente de venta y su IVA y
-- retencion. Solo en VENTA; en COSTE, NULL.
ALTER TABLE tesoreria.devengo_pendiente_partida ADD COLUMN IF NOT EXISTS contrato_cliente_id INTEGER;
ALTER TABLE tesoreria.devengo_pendiente_partida ADD COLUMN IF NOT EXISTS coeficiente_venta NUMERIC(12,6);
ALTER TABLE tesoreria.devengo_pendiente_partida ADD COLUMN IF NOT EXISTS fuente_coeficiente VARCHAR(12);
ALTER TABLE tesoreria.devengo_pendiente_partida ADD COLUMN IF NOT EXISTS coeficiente_master NUMERIC(12,6);
ALTER TABLE tesoreria.devengo_pendiente_partida ADD COLUMN IF NOT EXISTS pendiente_con_coeficientes NUMERIC(18,2);
ALTER TABLE tesoreria.devengo_pendiente_partida ADD COLUMN IF NOT EXISTS iva_porcentaje NUMERIC(9,4);
ALTER TABLE tesoreria.devengo_pendiente_partida ADD COLUMN IF NOT EXISTS fuente_iva VARCHAR(8);
ALTER TABLE tesoreria.devengo_pendiente_partida ADD COLUMN IF NOT EXISTS retencion_porcentaje NUMERIC(10,4);
ALTER TABLE tesoreria.devengo_pendiente_partida ADD COLUMN IF NOT EXISTS fuente_retencion VARCHAR(8);

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

-- F-150 (R14, R20): el pendiente con coeficientes de cada mes, su cociente, y el
-- IVA y la retencion del contrato con las bases que no lo tienen. Solo VENTA.
ALTER TABLE tesoreria.devengo_pendiente_obra_mes ADD COLUMN IF NOT EXISTS importe_pendiente_con_coeficientes NUMERIC(18,2);
ALTER TABLE tesoreria.devengo_pendiente_obra_mes ADD COLUMN IF NOT EXISTS coeficiente_venta NUMERIC(12,6);
ALTER TABLE tesoreria.devengo_pendiente_obra_mes ADD COLUMN IF NOT EXISTS importe_iva_contrato NUMERIC(18,2);
ALTER TABLE tesoreria.devengo_pendiente_obra_mes ADD COLUMN IF NOT EXISTS base_sin_iva_contrato NUMERIC(18,2);
ALTER TABLE tesoreria.devengo_pendiente_obra_mes ADD COLUMN IF NOT EXISTS importe_retencion_contrato NUMERIC(18,2);
ALTER TABLE tesoreria.devengo_pendiente_obra_mes ADD COLUMN IF NOT EXISTS base_sin_retencion_contrato NUMERIC(18,2);

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

-- F-150 (R23, N9): el hueco de facturacion de H26, NETO POR OBRA. Solo VENTA.
ALTER TABLE tesoreria.devengo_corte_obra ADD COLUMN IF NOT EXISTS venta_real_origen_con_coeficientes NUMERIC(18,2);
ALTER TABLE tesoreria.devengo_corte_obra ADD COLUMN IF NOT EXISTS venta_real_media_obra NUMERIC(18,2);
ALTER TABLE tesoreria.devengo_corte_obra ADD COLUMN IF NOT EXISTS facturado_origen NUMERIC(18,2);
ALTER TABLE tesoreria.devengo_corte_obra ADD COLUMN IF NOT EXISTS venta_pendiente_facturar NUMERIC(18,2);
ALTER TABLE tesoreria.devengo_corte_obra ADD COLUMN IF NOT EXISTS facturado_por_delante NUMERIC(18,2);
ALTER TABLE tesoreria.devengo_corte_obra ADD COLUMN IF NOT EXISTS iva_pendiente_facturar_contrato NUMERIC(18,2);
ALTER TABLE tesoreria.devengo_corte_obra ADD COLUMN IF NOT EXISTS base_pendiente_facturar_sin_iva_contrato NUMERIC(18,2);
ALTER TABLE tesoreria.devengo_corte_obra ADD COLUMN IF NOT EXISTS retencion_pendiente_facturar_contrato NUMERIC(18,2);
ALTER TABLE tesoreria.devengo_corte_obra ADD COLUMN IF NOT EXISTS base_pendiente_facturar_sin_retencion_contrato NUMERIC(18,2);


-- ---------------------------------------------------------------------------
-- F-150 (N11, R34): los albaranes pendientes de facturar, NETOS por proveedor
--
-- Una fila por (obra, proveedor, contrato, mes del albaran) de las obras de la
-- receta; la llena `09_albaranes_pendientes.sql`. Sin proveedor, sin contrato o
-- sin fecha son claves validas: `NULLS NOT DISTINCT` (precedente
-- `retenciones.saldo_contable`), por eso un indice unico y no una clave primaria.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tesoreria.albaranes_pendientes_neto (
    obra_id                  INTEGER       NOT NULL,
    empresa_id               INTEGER,
    clave_obra               VARCHAR(40),
    proveedor_id             INTEGER,
    contrato_id              INTEGER,
    mes_albaran              DATE,
    importe_pendiente_bruto  NUMERIC(18,2) NOT NULL,
    importe_sobrefacturado   NUMERIC(18,2) NOT NULL,
    importe_compensado       NUMERIC(18,2) NOT NULL,
    importe_pendiente_neto   NUMERIC(18,2) NOT NULL,
    meses_antiguedad         INTEGER,
    tras_cierre              BOOLEAN       NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_tes_albaranes_pendientes_neto ON tesoreria.albaranes_pendientes_neto (obra_id, proveedor_id, contrato_id, mes_albaran) NULLS NOT DISTINCT;
