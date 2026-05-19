-- etl_sigrid/infrastructure/postgres/sql/mart/03_agg_categoria.sql
--
-- mart.fact_seguimiento_categoria — tabla agregada por (obra, mes, categoría,
-- escenario). Se construye a partir de mart.fact_seguimiento_mensual sumando
-- todas las partidas que comparten categoría.
--
-- Propósito: Power BI consume esta tabla en los visuales "tarjeta KPI" y
-- "matriz por capítulo" sin tener que agregar 14M filas cada refresh.
--
-- Granularidad: una fila por (obra × mes × categoría × escenario).
--
-- IMPORTANTE: NO sustituye a fact_seguimiento_mensual. Es una vista pre-agregada
-- complementaria. Para visuales drill-down a partida, Power BI sigue usando
-- la tabla detalle. La categoría está disponible en AMBAS tablas con el mismo
-- nombre de columna, lo que permite a Power BI navegar entre las dos.

DROP TABLE IF EXISTS mart.fact_seguimiento_categoria CASCADE;

CREATE TABLE mart.fact_seguimiento_categoria (
    fact_cat_id          BIGSERIAL    PRIMARY KEY,
    obra_id              BIGINT       NOT NULL,
    codigo_obra          VARCHAR(24),
    nombre_obra          VARCHAR(255),
    anio_mes             DATE         NOT NULL,
    anio                 INTEGER      NOT NULL,
    mes                  INTEGER      NOT NULL,
    nombre_mes           VARCHAR(48),
    categoria            VARCHAR(8)   NOT NULL,         -- CD / CI / CP / OTRO
    escenario            VARCHAR(32)  NOT NULL,
    tipo_dato            VARCHAR(16)  NOT NULL,
    concepto             VARCHAR(16)  NOT NULL,
    ambito_id            INTEGER      NOT NULL,
    importe_mes          NUMERIC(18,2) NOT NULL,
    importe_origen       NUMERIC(18,2) NOT NULL,
    importe_mes_raw      NUMERIC(18,2),
    importe_origen_raw   NUMERIC(18,2),
    num_partidas         INTEGER      NOT NULL,         -- cuántas partidas suman aquí
    _built_at            TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_factcat_obra_mes      ON mart.fact_seguimiento_categoria (obra_id, anio_mes);
CREATE INDEX idx_factcat_categoria     ON mart.fact_seguimiento_categoria (categoria);
CREATE INDEX idx_factcat_obra_cat_mes  ON mart.fact_seguimiento_categoria (obra_id, categoria, anio_mes);

TRUNCATE TABLE mart.fact_seguimiento_categoria;

INSERT INTO mart.fact_seguimiento_categoria (
    obra_id, codigo_obra, nombre_obra,
    anio_mes, anio, mes, nombre_mes,
    categoria, escenario, tipo_dato, concepto, ambito_id,
    importe_mes, importe_origen,
    importe_mes_raw, importe_origen_raw,
    num_partidas
)
SELECT
    obra_id,
    MAX(codigo_obra)        AS codigo_obra,
    MAX(nombre_obra)        AS nombre_obra,
    anio_mes,
    anio,
    mes,
    MAX(nombre_mes)         AS nombre_mes,
    categoria,
    escenario,
    tipo_dato,
    concepto,
    ambito_id,
    SUM(importe_mes)        AS importe_mes,
    SUM(importe_origen)     AS importe_origen,
    SUM(importe_mes_raw)    AS importe_mes_raw,
    SUM(importe_origen_raw) AS importe_origen_raw,
    COUNT(DISTINCT partida_id) AS num_partidas
FROM mart.fact_seguimiento_mensual
GROUP BY
    obra_id, anio_mes, anio, mes,
    categoria, escenario, tipo_dato, concepto, ambito_id;
