-- etl_sigrid/infrastructure/postgres/sql/cierre/06_views_planif_vs_real.sql
--
-- =========================================================================
-- TANDA 4.3 — Cuadro PLANIFICADO vs REAL del mes (cuadro adicional cierre)
-- =========================================================================
--
-- Replica el cuadro del Excel del usuario:
--
--   PLANIFICADO vs REAL  |  PLANIFICADO  |  REAL  |  DIFERENCIA  |  %
--   PRODUCCIÓN           |   326.121,91  |  157.150,55  |  -168.971,36  |  -51,81%
--   COSTES DIRECTOS      |   298.892,56  |  149.659,81  |  -149.232,75  |  -49,93%
--   COSTES INDIRECTOS    |    57.108,88  |   77.939,64  |    20.830,76  |   36,48%
--   COSTES PROPORCIONALES|    25.322,71  |   16.736,99  |    -8.585,72  |  -33,91%
--   TOTAL COSTES         |   381.324,15  |  244.336,44  |  -136.987,71  |  -35,92%
--   BENEFICIO            |   -55.202,24  |  -87.185,89  |   -31.983,65  |   57,94%
--
-- Fuente: mart.fact_seguimiento_categoria (importe_mes).
--   PLANIFICADO  = tipo_dato='PLANIFICADO'
--   REAL         = tipo_dato='REAL'
--   PRODUCCIÓN   = concepto='VENTA'  (CD+CI+CP del lado venta = la venta)
--   CD/CI/CP     = concepto='COSTE', categoria=CD/CI/CP
--   TOTAL COSTES = CD + CI + CP
--   BENEFICIO    = PRODUCCIÓN - TOTAL COSTES
--   DIFERENCIA   = REAL - PLANIFICADO
--   DESVIACIÓN % = DIFERENCIA / PLANIFICADO * 100
--
-- =========================================================================

-- =========================================================================
-- F-118 (F-051 absorbida) · EL GRANO DE LA VISTA, BLINDADO
-- =========================================================================
-- Hasta F-118 la vista agrupaba también por `nombre_mes`, que en las filas
-- reales de `mart` era el TEXTO libre de la fase («JUNIO 24», «Enero
-- 2020-Abril 2020») y en las planificadas el nombre del mes: el mismo (obra,
-- mes) salía partido en varias filas y el `JOIN` de `beneficio` las cruzaba
-- entre sí (la 0571 publicaba BENEFICIO ocho veces en 2020-05; 204
-- combinaciones repetidas en `check-unicidad`). Ahora:
--   - `base` agrupa por (obra_id, anio_mes, categoria, concepto) y saca
--     `codigo_obra`, `nombre_obra`, `anio` y `mes` con MAX(): son función de
--     esa clave;
--   - `producc` y `total_costes` agregan por (obra_id, anio_mes) y `beneficio`
--     los une por ese mismo grano;
--   - `nombre_mes` se deriva en la SELECT final de `anio_mes`, sin locale.
-- Las columnas y su orden no cambian: Power BI solo deja de ver filas
-- repetidas.
-- =========================================================================

DROP VIEW IF EXISTS cierre.v_pbi_planif_vs_real CASCADE;

CREATE VIEW cierre.v_pbi_planif_vs_real AS
WITH
-- Pivot: una fila por (obra, mes, categoría, concepto) con planif y real lado a lado
base AS (
    SELECT
        f.obra_id,
        MAX(f.codigo_obra)                 AS codigo_obra,
        MAX(f.nombre_obra)                 AS nombre_obra,
        f.anio_mes,
        MAX(f.anio)                        AS anio,
        MAX(f.mes)                         AS mes,
        f.categoria,                       -- CD / CI / CP
        f.concepto,                        -- COSTE / VENTA
        SUM(CASE WHEN f.tipo_dato = 'PLANIFICADO' THEN f.importe_mes ELSE 0 END)::NUMERIC(18,2) AS planif_mes,
        SUM(CASE WHEN f.tipo_dato = 'REAL'        THEN f.importe_mes ELSE 0 END)::NUMERIC(18,2) AS real_mes
    FROM mart.fact_seguimiento_categoria f
    GROUP BY f.obra_id, f.anio_mes, f.categoria, f.concepto
),

-- Cada uno de los 6 renglones del cuadro
producc AS (
    SELECT
        obra_id,
        MAX(codigo_obra)           AS codigo_obra,
        MAX(nombre_obra)           AS nombre_obra,
        anio_mes,
        MAX(anio)                  AS anio,
        MAX(mes)                   AS mes,
        'PRODUCCIÓN'::VARCHAR     AS concepto_cuadro,
        1::INT                     AS orden_concepto,
        SUM(planif_mes)::NUMERIC(18,2) AS planificado,
        SUM(real_mes)::NUMERIC(18,2)   AS real
    FROM base
    WHERE concepto = 'VENTA'
    GROUP BY obra_id, anio_mes
),
costes AS (
    SELECT
        obra_id, codigo_obra, nombre_obra, anio_mes, anio, mes,
        CASE categoria
            WHEN 'CD' THEN 'COSTES DIRECTOS'
            WHEN 'CI' THEN 'COSTES INDIRECTOS'
            WHEN 'CP' THEN 'COSTES PROPORCIONALES'
            ELSE          'OTROS'
        END                        AS concepto_cuadro,
        CASE categoria
            WHEN 'CD' THEN 2
            WHEN 'CI' THEN 3
            WHEN 'CP' THEN 4
            ELSE          9
        END                        AS orden_concepto,
        planif_mes                 AS planificado,
        real_mes                   AS real
    FROM base
    WHERE concepto = 'COSTE'
      AND categoria IN ('CD', 'CI', 'CP')
),
total_costes AS (
    SELECT
        obra_id,
        MAX(codigo_obra)           AS codigo_obra,
        MAX(nombre_obra)           AS nombre_obra,
        anio_mes,
        MAX(anio)                  AS anio,
        MAX(mes)                   AS mes,
        'TOTAL COSTES'::VARCHAR    AS concepto_cuadro,
        5::INT                      AS orden_concepto,
        SUM(planificado)::NUMERIC(18,2) AS planificado,
        SUM(real)::NUMERIC(18,2)        AS real
    FROM costes
    GROUP BY obra_id, anio_mes
),
beneficio AS (
    SELECT
        p.obra_id, p.codigo_obra, p.nombre_obra, p.anio_mes,
        p.anio, p.mes,
        'BENEFICIO'::VARCHAR       AS concepto_cuadro,
        6::INT                      AS orden_concepto,
        (p.planificado - tc.planificado)::NUMERIC(18,2) AS planificado,
        (p.real        - tc.real)::NUMERIC(18,2)        AS real
    FROM producc p
    JOIN total_costes tc
        ON tc.obra_id  = p.obra_id
       AND tc.anio_mes = p.anio_mes
),
todos AS (
    SELECT * FROM producc
    UNION ALL SELECT * FROM costes
    UNION ALL SELECT * FROM total_costes
    UNION ALL SELECT * FROM beneficio
)
SELECT
    obra_id, codigo_obra, nombre_obra,
    anio_mes, anio, mes,
    -- Nombre del mes SIN locale, derivado de anio_mes (R18).
    ((ARRAY['Enero','Febrero','Marzo','Abril','Mayo','Junio',
            'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'])
           [EXTRACT(MONTH FROM anio_mes)::INT]
         || ' ' || EXTRACT(YEAR FROM anio_mes)::INT)::VARCHAR(48) AS nombre_mes,
    concepto_cuadro, orden_concepto,
    planificado,
    real,
    (real - planificado)::NUMERIC(18,2)                                       AS diferencia,
    CASE WHEN planificado IS NULL OR planificado = 0 THEN NULL
         ELSE ROUND((real - planificado) * 100.0 / planificado, 2)
    END                                                                       AS desviacion_pct
FROM todos;

COMMENT ON VIEW cierre.v_pbi_planif_vs_real IS
'Cuadro PLANIFICADO vs REAL por (obra × mes × concepto). Importes del mes '
'(parcial, no a origen) desde mart.fact_seguimiento_categoria. 6 conceptos: '
'PRODUCCIÓN, COSTES DIRECTOS, INDIRECTOS, PROPORCIONALES, TOTAL COSTES, BENEFICIO. '
'Diferencia = Real - Planificado. Desviación % = Diferencia / Planificado. '
'Grano (obra_id, anio_mes, concepto_cuadro): una fila (F-118).';
