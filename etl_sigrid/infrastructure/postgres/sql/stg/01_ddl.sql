-- etl_sigrid/infrastructure/postgres/sql/stg/01_ddl.sql
--
-- DDL idempotente de las tablas stg. Se ejecuta en cada build_stg.
-- La primera vez crea las tablas e índices. Las siguientes no hacen nada.
-- Las tablas se llenan después con TRUNCATE + INSERT (ver 03_*..07_*.sql).
--
-- Nota: stg.ambitos NO está aquí: es una VISTA (ver 02_ambitos.sql).

-- ---------------------------------------------------------------------------
-- stg.obras: una fila por obra con código y nombre legibles
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg.obras (
    obra_id      BIGINT       PRIMARY KEY,
    codigo_obra  VARCHAR(24),
    nombre_obra  VARCHAR(255),
    activa       BOOLEAN      NOT NULL DEFAULT TRUE,
    _built_at    TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_obras_codigo ON stg.obras (codigo_obra);


-- ---------------------------------------------------------------------------
-- stg.partidas: una fila por partida de obra (incluye capítulos)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg.partidas (
    partida_id         BIGINT       PRIMARY KEY,
    obra_id            BIGINT       NOT NULL,
    codigo_partida     VARCHAR(24),
    capitulo_padre_id  BIGINT,
    descripcion_corta  VARCHAR(128),
    unidad_medida      VARCHAR(16),
    capitulo_raiz_id   BIGINT,
    capitulo_raiz_cod  VARCHAR(24),
    categoria          VARCHAR(8),
    ruta_capitulos     TEXT,
    nivel              INTEGER,
    activa             BOOLEAN      NOT NULL DEFAULT TRUE,
    _built_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_partidas_obra     ON stg.partidas (obra_id);
CREATE INDEX IF NOT EXISTS idx_partidas_obra_cod ON stg.partidas (obra_id, codigo_partida);


-- ---------------------------------------------------------------------------
-- stg.fases: una fila por fase de obra con fechas tipadas y plazo
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg.fases (
    fase_id        BIGINT       PRIMARY KEY,
    obra_id        BIGINT       NOT NULL,
    numero_fase    INTEGER      NOT NULL,
    fecha_inicio   DATE,
    fecha_fin      DATE,
    plazo_meses    INTEGER,
    anio           INTEGER,
    mes            INTEGER,
    nombre_mes     VARCHAR(48),
    _built_at      TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_fases_obra_num   ON stg.fases (obra_id, numero_fase);
CREATE INDEX IF NOT EXISTS idx_fases_fecha_fin  ON stg.fases (fecha_fin);


-- ---------------------------------------------------------------------------
-- stg.presupuesto: una fila por (obra × partida × ámbito × fase)
--
-- IMPORTANTE - precisión del PRECIO:
--   Sigrid almacena `pre` en double precision con hasta 6 decimales reales
--   (ej: 115.294961). Si guardamos `precio` con menos decimales, el
--   ROUND(precio, 2) posterior puede divergir del ROUND(pre_crudo, 2).
--   Caso real obra 0696 partida P4.04.01.02 (residual 1,70 €).
--
-- IMPORTANTE - precisión de la CANTIDAD:
--   Sigrid usa `can` para porcentajes o coeficientes con hasta 6 decimales
--   (ej: 0.00025 en CP.4 AVALES = 0,025% del presupuesto venta). Si guardamos
--   `cantidad` con NUMERIC(18,4), 0.00025 se redondea a 0.0003 (+20%) y
--   propaga gap a importe_mes / importe_origen.
--   Caso real obra 0696 partida CP.4: gap +83,71 € en plan mes mayo 2025.
--
--   Solución: NUMERIC(20,6) para AMBOS (cantidad y precio).
--   - Escala 6: preserva los 6 decimales reales de Sigrid
--   - Precisión total 20: mantiene 14 dígitos enteros para no overflow.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg.presupuesto (
    presupuesto_id  BIGINT           PRIMARY KEY,
    obra_id         BIGINT           NOT NULL,
    partida_id      BIGINT           NOT NULL,
    ambito_id       INTEGER          NOT NULL,
    fase_num        INTEGER          NOT NULL,
    cantidad        NUMERIC(20,6),                  -- 6 decimales para porcentajes/coeficientes Sigrid
    precio          NUMERIC(20,6),                  -- 6 decimales para precisión Sigrid
    importe         NUMERIC(18,2),
    _source_tiemod  DOUBLE PRECISION,
    _built_at       TIMESTAMP        NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pres_obra_amb         ON stg.presupuesto (obra_id, ambito_id);
CREATE INDEX IF NOT EXISTS idx_pres_obra_part_amb    ON stg.presupuesto (obra_id, partida_id, ambito_id);
CREATE INDEX IF NOT EXISTS idx_pres_obra_part_amb_fa ON stg.presupuesto (obra_id, partida_id, ambito_id, fase_num);

-- Migración defensiva para PRECIO: si tabla ya existía con menos precisión.
DO $$
DECLARE
    v_precision INTEGER;
    v_scale     INTEGER;
BEGIN
    SELECT numeric_precision, numeric_scale
    INTO v_precision, v_scale
    FROM information_schema.columns
    WHERE table_schema = 'stg'
      AND table_name   = 'presupuesto'
      AND column_name  = 'precio';

    IF v_precision IS NOT NULL AND (v_precision < 20 OR v_scale < 6) THEN
        ALTER TABLE stg.presupuesto ALTER COLUMN precio TYPE NUMERIC(20,6);
        RAISE NOTICE 'Migrado stg.presupuesto.precio de NUMERIC(%, %) a NUMERIC(20, 6)',
                     v_precision, v_scale;
    END IF;
END $$;

-- Migración defensiva para CANTIDAD: si tabla ya existía con menos precisión.
DO $$
DECLARE
    v_precision INTEGER;
    v_scale     INTEGER;
BEGIN
    SELECT numeric_precision, numeric_scale
    INTO v_precision, v_scale
    FROM information_schema.columns
    WHERE table_schema = 'stg'
      AND table_name   = 'presupuesto'
      AND column_name  = 'cantidad';

    IF v_precision IS NOT NULL AND (v_precision < 20 OR v_scale < 6) THEN
        ALTER TABLE stg.presupuesto ALTER COLUMN cantidad TYPE NUMERIC(20,6);
        RAISE NOTICE 'Migrado stg.presupuesto.cantidad de NUMERIC(%, %) a NUMERIC(20, 6)',
                     v_precision, v_scale;
    END IF;
END $$;


-- ---------------------------------------------------------------------------
-- stg.version_master_vigente
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg.version_master_vigente (
    obra_id          BIGINT       PRIMARY KEY,
    version_vigente  INTEGER      NOT NULL,
    _built_at        TIMESTAMP    NOT NULL DEFAULT NOW()
);


-- ---------------------------------------------------------------------------
-- stg.plan_mensual: tabla unificada con la distribución mensual de los 4 ámbitos.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg.plan_mensual (
    plan_id              BIGSERIAL    PRIMARY KEY,
    presupuesto_id       BIGINT       NOT NULL,
    obra_id              BIGINT       NOT NULL,
    partida_id           BIGINT       NOT NULL,
    ambito_id            INTEGER      NOT NULL,
    version              INTEGER      NOT NULL,
    version_descripcion  TEXT         NULL,
    version_tex          TEXT         NULL,
    version_fec_creacion DATE         NULL,
    anio_mes             DATE         NOT NULL,
    posicion_mes         INTEGER      NOT NULL,
    pct_acumulado        NUMERIC(18,6) NULL,
    pct_mes              NUMERIC(18,6) NULL,
    precio_unitario      NUMERIC(20,6) NOT NULL,
    can_mes              NUMERIC(20,6) NOT NULL,           -- 6 decimales (porcentajes Sigrid)
    can_origen           NUMERIC(20,6) NOT NULL,           -- 6 decimales (porcentajes Sigrid)
    importe_mes          NUMERIC(18,2) NOT NULL,
    importe_origen       NUMERIC(18,2) NOT NULL,
    importe_mes_raw      NUMERIC(18,2) NULL,
    importe_origen_raw   NUMERIC(18,2) NULL,
    total_incurrido      NUMERIC(18,2) NULL,
    total_incurrido_mes  NUMERIC(18,2) NULL,
    _built_at            TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_plan_mensual_obra_amb        ON stg.plan_mensual (obra_id, ambito_id);
CREATE INDEX IF NOT EXISTS idx_plan_mensual_obra_part_amb_v ON stg.plan_mensual (obra_id, partida_id, ambito_id, version);
CREATE INDEX IF NOT EXISTS idx_plan_mensual_anio_mes        ON stg.plan_mensual (anio_mes);
CREATE INDEX IF NOT EXISTS idx_plan_mensual_presupuesto     ON stg.plan_mensual (presupuesto_id);

-- Migración defensiva para precio_unitario, can_mes, can_origen.
DO $$
DECLARE
    v_precision INTEGER;
    v_scale     INTEGER;
BEGIN
    -- precio_unitario
    SELECT numeric_precision, numeric_scale
    INTO v_precision, v_scale
    FROM information_schema.columns
    WHERE table_schema = 'stg' AND table_name = 'plan_mensual' AND column_name = 'precio_unitario';
    IF v_precision IS NOT NULL AND (v_precision < 20 OR v_scale < 6) THEN
        ALTER TABLE stg.plan_mensual ALTER COLUMN precio_unitario TYPE NUMERIC(20,6);
        RAISE NOTICE 'Migrado stg.plan_mensual.precio_unitario a NUMERIC(20, 6)';
    END IF;

    -- can_mes
    SELECT numeric_precision, numeric_scale
    INTO v_precision, v_scale
    FROM information_schema.columns
    WHERE table_schema = 'stg' AND table_name = 'plan_mensual' AND column_name = 'can_mes';
    IF v_precision IS NOT NULL AND (v_precision < 20 OR v_scale < 6) THEN
        ALTER TABLE stg.plan_mensual ALTER COLUMN can_mes TYPE NUMERIC(20,6);
        RAISE NOTICE 'Migrado stg.plan_mensual.can_mes a NUMERIC(20, 6)';
    END IF;

    -- can_origen
    SELECT numeric_precision, numeric_scale
    INTO v_precision, v_scale
    FROM information_schema.columns
    WHERE table_schema = 'stg' AND table_name = 'plan_mensual' AND column_name = 'can_origen';
    IF v_precision IS NOT NULL AND (v_precision < 20 OR v_scale < 6) THEN
        ALTER TABLE stg.plan_mensual ALTER COLUMN can_origen TYPE NUMERIC(20,6);
        RAISE NOTICE 'Migrado stg.plan_mensual.can_origen a NUMERIC(20, 6)';
    END IF;
END $$;