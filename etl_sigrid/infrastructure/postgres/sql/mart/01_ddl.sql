-- etl_sigrid/infrastructure/postgres/sql/mart/01_ddl.sql
--
-- DDL del data mart de seguimiento mensual.
--
-- =========================================================================
-- TABLA CENTRAL: mart.fact_seguimiento_mensual
-- =========================================================================
-- Granularidad: una fila por (obra × partida × mes × escenario).
--
-- Cuatro escenarios por (obra, partida, mes):
--   - "Coste Real"        ← de stg.plan_mensual amb=3
--   - "Venta Real"        ← de stg.plan_mensual amb=7
--   - "Coste Planificado" ← de stg.plan_mensual amb=8, versión vigente en el mes
--   - "Venta Planificada" ← de stg.plan_mensual amb=11, versión vigente en el mes
--
-- Regla "versión vigente en el mes" para master (amb 8, 11):
--   Por cada mes M, se coge el master de la obra cuya `version_fec_creacion`
--   sea la más reciente con fec_creacion <= primer_día_del_mes_siguiente_a_M.
--   Esto cubre:
--     - Planificación inicial: la primera versión de la obra → rige desde
--       el inicio hasta la siguiente versión.
--     - ABC: vigente desde su creación hasta la siguiente cuatrimestral.
--     - Cuatrimestrales (feb/jun/oct): rigen desde su mes hasta la
--       siguiente cuatrimestral existente.
--   Si en el futuro no hay versión posterior, la última conocida proyecta.
--
-- Para meses futuros (sin real): solo aparecen "Coste Planificado" y
-- "Venta Planificada" (los reales no existen).
-- Para meses pasados sin master (obra arrancó sin master): solo aparecen
-- los reales.
--
-- IMPORTANTE - PRECISIÓN:
--   Los campos can_mes, can_origen y precio_unitario se almacenan en
--   NUMERIC(20,6) — consistente con stg.plan_mensual y stg.presupuesto.
--   Si se usase NUMERIC(18,4), se truncarían los porcentajes Sigrid de las
--   partidas CP (ej. 0.00025 en CP.4 AVALES) reintroduciendo el bug que
--   afecta al cuadre del Plan. Ver detalle en stg/01_ddl.sql.

DROP TABLE IF EXISTS mart.fact_seguimiento_mensual CASCADE;

CREATE TABLE mart.fact_seguimiento_mensual (
    fact_id              BIGSERIAL    PRIMARY KEY,
    -- Dimensiones de obra y partida
    obra_id              BIGINT       NOT NULL,
    codigo_obra          VARCHAR(24),
    nombre_obra          VARCHAR(255),
    partida_id           BIGINT       NOT NULL,
    codigo_partida       VARCHAR(24),
    descripcion_partida  VARCHAR(128),
    unidad_medida        VARCHAR(16),       -- m3, m2, ud, kg... (de obrparpar.unimed)
    categoria            VARCHAR(8),        -- CD / CI / CP / OTRO (derivada del capítulo raíz)
    capitulo_raiz_cod    VARCHAR(24),       -- código real del raíz (informativo)
    ruta_capitulos       TEXT,              -- "CD > 01 > 01.02" para trazabilidad
    -- Dimensión temporal
    anio_mes             DATE         NOT NULL,
    anio                 INTEGER      NOT NULL,
    mes                  INTEGER      NOT NULL,
    nombre_mes           VARCHAR(48),       -- "Octubre 2025"
    -- Dimensión escenario
    escenario            VARCHAR(32)  NOT NULL,  -- "Coste Real" / "Venta Real" / "Coste Planificado" / "Venta Planificada"
    tipo_dato            VARCHAR(16)  NOT NULL,  -- "REAL" / "PLANIFICADO"
    concepto             VARCHAR(16)  NOT NULL,  -- "COSTE" / "VENTA"
    ambito_id            INTEGER      NOT NULL,  -- 3 / 7 / 8 / 11 (trazabilidad)
    -- Métricas (versión Sigrid-compatible: precio redondeado a 2 decimales)
    importe_mes          NUMERIC(18,2) NOT NULL,
    importe_origen       NUMERIC(18,2) NOT NULL,
    -- Métricas de referencia (versión raw: precio sin redondear)
    importe_mes_raw      NUMERIC(18,2),
    importe_origen_raw   NUMERIC(18,2),
    -- Cantidades y precio: 6 decimales para preservar precisión Sigrid
    -- (porcentajes CP con hasta 6 decimales, precios con hasta 6 decimales)
    can_mes              NUMERIC(20,6),
    can_origen           NUMERIC(20,6),
    precio_unitario      NUMERIC(20,6),
    -- Trazabilidad de versión (solo planificado)
    version_master       INTEGER,          -- número de versión (NULL para real)
    version_descripcion  TEXT,             -- "Versión N (DD/MM/YYYY)" / "Octubre 2025"
    version_tex          TEXT,             -- obrfasamb.tex: texto libre JO ("ABC", "PLANIFICACION CUATRIMESTRAL FEB-26"...)
    version_fec_creacion DATE,
    tipo_master          VARCHAR(20),      -- ABC / Planif Inicial / Cuatrimestral / Cierre mensual / Sin clasificar (solo planif)
    -- Extra reales: Sigrid mantiene un cálculo paralelo "incurrido" (totinc)
    -- que normalmente coincide con can*pre pero a veces difiere céntimos.
    -- Capturamos ambas vistas: total a origen y parcial del mes.
    total_incurrido      NUMERIC(18,2),    -- a origen (solo amb=3, columna "Imp. Incurrido" en Sigrid)
    total_incurrido_mes  NUMERIC(18,2),    -- del mes (solo amb=3, columna "Imp. Incurrido Parcial" en Sigrid)
    _built_at            TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_fact_obra_mes        ON mart.fact_seguimiento_mensual (obra_id, anio_mes);
CREATE INDEX idx_fact_obra_part_mes   ON mart.fact_seguimiento_mensual (obra_id, partida_id, anio_mes);
CREATE INDEX idx_fact_escenario       ON mart.fact_seguimiento_mensual (escenario);
CREATE INDEX idx_fact_anio_mes        ON mart.fact_seguimiento_mensual (anio_mes);
CREATE INDEX idx_fact_categoria       ON mart.fact_seguimiento_mensual (obra_id, categoria, anio_mes);