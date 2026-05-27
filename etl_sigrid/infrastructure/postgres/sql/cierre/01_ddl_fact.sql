-- etl_sigrid/infrastructure/postgres/sql/cierre/01_ddl_fact.sql
--
-- =========================================================================
-- DDL del fact (se reconstruye en CADA build)
-- =========================================================================

DROP TABLE IF EXISTS cierre.fact_cierre_mensual CASCADE;

CREATE TABLE cierre.fact_cierre_mensual (
    cierre_id              BIGSERIAL    PRIMARY KEY,
    -- Dimensión obra
    obra_id                BIGINT       NOT NULL,
    codigo_obra            VARCHAR(24),
    nombre_obra            VARCHAR(255),
    -- Dimensión temporal (mes canónico de la fase de cierre)
    anio_mes               DATE         NOT NULL,
    anio                   INTEGER      NOT NULL,
    mes                    INTEGER      NOT NULL,
    nombre_mes             VARCHAR(48),
    -- Dimensión concepto
    concepto               VARCHAR(16)  NOT NULL,
    orden_concepto         INTEGER      NOT NULL,
    -- Métricas EJECUTADO (incurrido a origen en la fase del mes — fas>=1)
    ejecutado_origen       NUMERIC(18,2) NOT NULL DEFAULT 0,
    ejecutado_anterior     NUMERIC(18,2) NOT NULL DEFAULT 0,
    ejecutado_mes          NUMERIC(18,2) NOT NULL DEFAULT 0,
    -- Métricas FINAL
    final_importe          NUMERIC(18,2) NOT NULL DEFAULT 0,
    final_anterior         NUMERIC(18,2),
    pendiente_importe      NUMERIC(18,2) NOT NULL DEFAULT 0,
    variacion_importe      NUMERIC(18,2),
    -- Trazabilidad del origen del FINAL
    final_fuente           VARCHAR(16)  NOT NULL DEFAULT 'sin_dato',
                                                       -- 'master'  → versión master CIERRE del mes
                                                       -- 'fase_0'  → mes en curso, sin master aún
                                                       -- 'sin_dato'→ no hay ni master ni fase 0
    final_version_master   INTEGER,                    -- nº de versión usado (si fuente='master')
    final_version_tex      TEXT,                       -- texto de la versión
    -- Trazabilidad de la fase del EJECUTADO
    fase_id                BIGINT,
    fase_numero            INTEGER,
    fase_fecha_inicio      DATE,
    fase_nombre_mes        VARCHAR(48),
    _built_at              TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_cierre_fact_obra_mes      ON cierre.fact_cierre_mensual (obra_id, anio_mes);
CREATE INDEX idx_cierre_fact_obra_concepto ON cierre.fact_cierre_mensual (obra_id, concepto);
CREATE INDEX idx_cierre_fact_anio_mes      ON cierre.fact_cierre_mensual (anio_mes);
CREATE INDEX idx_cierre_fact_codigo_obra   ON cierre.fact_cierre_mensual (codigo_obra);

COMMENT ON TABLE cierre.fact_cierre_mensual IS
'Cierre mensual de obra (Tanda 1.4). Una fila por (obra × mes × concepto). '
'Conceptos base: VENTA/INDIRECTOS/DIRECTOS/GENERALES. GASTOS y BENEFICIO '
'derivados en cierre.v_pbi_cierre_resumen. '
'EJECUTADO viene de stg.plan_mensual amb 3/7 fas>=1 (incurrido a origen). '
'FINAL viene de la versión master CIERRE del mes (amb 8/11) elegida por '
'cierre.fn_mes_de_version_master sobre el texto. Si no hay master para ese '
'mes (mes en curso), fallback a stg.plan_mensual amb 3/7 fas=0 (Previsto).';

COMMENT ON COLUMN cierre.fact_cierre_mensual.final_fuente IS
'Origen del valor FINAL: "master" si hay versión master CIERRE para el mes, '
'"fase_0" si es mes en curso sin master, "sin_dato" si no hay ninguno.';
