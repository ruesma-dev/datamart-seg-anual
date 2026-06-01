-- etl_sigrid/infrastructure/postgres/sql/cierre/03_views.sql
--
-- Vistas Power BI del cierre.
--
-- TANDA 4 — Porcentajes redefinidos según la lógica del Excel:
--   Para cada columna (ORIGEN/ANTERIOR/MES/PENDIENTE/FINAL), el % de
--   cualquier concepto se calcula contra la VENTA de ESA MISMA columna
--   y MISMO mes. Excepto:
--     · VENTA FINAL %  = VENTA_FINAL / PRESUPUESTO_APROBADO_VENTA
--
-- Ejemplo (obra de la imagen):
--   INDIRECTOS MES % = INDIRECTOS_MES / VENTA_MES = 77.964,95 / 571.473,05 = 13,64%
--   INDIRECTOS FINAL % = INDIRECTOS_FINAL / VENTA_FINAL = 1.579.836,17 / 9.620.299,18 = 16,42%
--
-- El presupuesto_aprobado_venta viene de cierre.v_pbi_cierre_cabecera
-- (que por defecto = presupuesto_inicial_venta).

DROP VIEW IF EXISTS cierre.v_pbi_cierre_resumen CASCADE;
DROP VIEW IF EXISTS cierre.v_pbi_dim_concepto   CASCADE;

-- ---------------------------------------------------------------------------
-- Dimensión: conceptos
-- ---------------------------------------------------------------------------
CREATE VIEW cierre.v_pbi_dim_concepto AS
SELECT * FROM (VALUES
    ('VENTA',      1, 'Producción / Venta'),
    ('GASTOS',     2, 'Gastos totales'),
    ('INDIRECTOS', 3, 'Costes Indirectos'),
    ('DIRECTOS',   4, 'Costes Directos'),
    ('GENERALES',  5, 'Costes Generales (Proporcionales)'),
    ('BENEFICIO',  6, 'Beneficio')
) AS t(concepto, orden, descripcion);

-- ---------------------------------------------------------------------------
-- Vista principal: 6 filas por (obra × mes) con todas las métricas € y %.
-- ---------------------------------------------------------------------------
CREATE VIEW cierre.v_pbi_cierre_resumen AS
WITH
base AS (
    SELECT
        obra_id, codigo_obra, nombre_obra,
        anio_mes, anio, mes, nombre_mes,
        concepto, orden_concepto,
        ejecutado_origen, ejecutado_anterior, ejecutado_mes,
        final_importe, final_anterior, pendiente_importe, variacion_importe,
        final_fuente, final_version_master, final_version_tex,
        fase_numero, fase_nombre_mes
    FROM cierre.fact_cierre_mensual
),

gastos AS (
    SELECT
        obra_id, codigo_obra, nombre_obra,
        anio_mes, anio, mes, nombre_mes,
        'GASTOS'::VARCHAR AS concepto,
        2::INT             AS orden_concepto,
        SUM(ejecutado_origen)  ::NUMERIC(18,2) AS ejecutado_origen,
        SUM(ejecutado_anterior)::NUMERIC(18,2) AS ejecutado_anterior,
        SUM(ejecutado_mes)     ::NUMERIC(18,2) AS ejecutado_mes,
        SUM(final_importe)     ::NUMERIC(18,2) AS final_importe,
        CASE WHEN BOOL_AND(final_anterior IS NULL) THEN NULL
             ELSE SUM(COALESCE(final_anterior, 0))::NUMERIC(18,2) END AS final_anterior,
        SUM(pendiente_importe) ::NUMERIC(18,2) AS pendiente_importe,
        CASE WHEN BOOL_AND(variacion_importe IS NULL) THEN NULL
             ELSE SUM(COALESCE(variacion_importe, 0))::NUMERIC(18,2) END AS variacion_importe,
        CASE
            WHEN BOOL_OR(final_fuente = 'sin_dato') THEN 'sin_dato'
            WHEN BOOL_OR(final_fuente = 'fase_0')   THEN 'fase_0'
            ELSE                                          'master'
        END                                       AS final_fuente,
        NULL::INT          AS final_version_master,
        NULL::TEXT         AS final_version_tex,
        NULL::INT          AS fase_numero,
        NULL::VARCHAR(48)  AS fase_nombre_mes
    FROM base
    WHERE concepto IN ('INDIRECTOS', 'DIRECTOS', 'GENERALES')
    GROUP BY obra_id, codigo_obra, nombre_obra, anio_mes, anio, mes, nombre_mes
),

beneficio AS (
    SELECT
        v.obra_id, v.codigo_obra, v.nombre_obra,
        v.anio_mes, v.anio, v.mes, v.nombre_mes,
        'BENEFICIO'::VARCHAR AS concepto,
        6::INT                AS orden_concepto,
        (v.ejecutado_origen   - g.ejecutado_origen)  ::NUMERIC(18,2) AS ejecutado_origen,
        (v.ejecutado_anterior - g.ejecutado_anterior)::NUMERIC(18,2) AS ejecutado_anterior,
        (v.ejecutado_mes      - g.ejecutado_mes)     ::NUMERIC(18,2) AS ejecutado_mes,
        (v.final_importe      - g.final_importe)     ::NUMERIC(18,2) AS final_importe,
        CASE WHEN v.final_anterior IS NULL OR g.final_anterior IS NULL THEN NULL
             ELSE (v.final_anterior - g.final_anterior)::NUMERIC(18,2) END AS final_anterior,
        (v.pendiente_importe  - g.pendiente_importe) ::NUMERIC(18,2) AS pendiente_importe,
        CASE WHEN v.variacion_importe IS NULL OR g.variacion_importe IS NULL THEN NULL
             ELSE (v.variacion_importe - g.variacion_importe)::NUMERIC(18,2) END AS variacion_importe,
        CASE
            WHEN v.final_fuente = 'sin_dato' OR g.final_fuente = 'sin_dato' THEN 'sin_dato'
            WHEN v.final_fuente = 'fase_0'   OR g.final_fuente = 'fase_0'   THEN 'fase_0'
            ELSE                                                                  'master'
        END                                       AS final_fuente,
        NULL::INT          AS final_version_master,
        NULL::TEXT         AS final_version_tex,
        NULL::INT          AS fase_numero,
        NULL::VARCHAR(48)  AS fase_nombre_mes
    FROM base v
    JOIN gastos g
        ON g.obra_id  = v.obra_id
       AND g.anio_mes = v.anio_mes
    WHERE v.concepto = 'VENTA'
),

-- =======================================================================
-- VENTA por (obra × mes): valores en cada columna que sirven como BASE
-- para calcular los % del resto de conceptos.
-- =======================================================================
venta_por_mes AS (
    SELECT
        obra_id, anio_mes,
        ejecutado_origen   AS venta_origen,
        ejecutado_anterior AS venta_anterior,
        ejecutado_mes      AS venta_mes,
        pendiente_importe  AS venta_pendiente,
        final_importe      AS venta_final
    FROM base
    WHERE concepto = 'VENTA'
),

-- =======================================================================
-- Presupuesto aprobado VENTA (de la cabecera) por obra.
-- Si no existe (caso muy raro), fallback al primer venta_final disponible.
-- =======================================================================
aprobado_por_obra AS (
    SELECT
        obra_id,
        presupuesto_aprobado_venta AS aprobado_venta
    FROM cierre.v_pbi_cierre_cabecera
),

todos AS (
    SELECT * FROM base
    UNION ALL SELECT * FROM gastos
    UNION ALL SELECT * FROM beneficio
)
SELECT
    t.obra_id, t.codigo_obra, t.nombre_obra,
    t.anio_mes, t.anio, t.mes, t.nombre_mes,
    t.concepto, t.orden_concepto,
    -- Importes
    t.ejecutado_origen, t.ejecutado_anterior, t.ejecutado_mes,
    t.final_importe, t.final_anterior, t.pendiente_importe, t.variacion_importe,
    -- =================================================================
    -- PORCENTAJES (lógica Excel CONTROL DE GESTIÓN):
    -- Para cada columna, el % se calcula contra la VENTA de la MISMA
    -- columna y MISMO mes. Excepción: VENTA FINAL % va contra el
    -- PRESUPUESTO APROBADO de la obra (de la cabecera).
    -- =================================================================
    CASE
        WHEN t.concepto = 'VENTA' THEN
            CASE WHEN v.venta_final = 0 OR v.venta_final IS NULL THEN NULL
                 ELSE ROUND(t.ejecutado_origen * 100.0 / v.venta_final, 2) END
        ELSE
            CASE WHEN v.venta_origen = 0 OR v.venta_origen IS NULL THEN NULL
                 ELSE ROUND(t.ejecutado_origen * 100.0 / v.venta_origen, 2) END
    END                                       AS ejecutado_origen_pct,

    CASE
        WHEN t.concepto = 'VENTA' THEN
            CASE WHEN v.venta_final = 0 OR v.venta_final IS NULL THEN NULL
                 ELSE ROUND(t.ejecutado_anterior * 100.0 / v.venta_final, 2) END
        ELSE
            CASE WHEN v.venta_anterior = 0 OR v.venta_anterior IS NULL THEN NULL
                 ELSE ROUND(t.ejecutado_anterior * 100.0 / v.venta_anterior, 2) END
    END                                       AS ejecutado_anterior_pct,

    CASE
        WHEN t.concepto = 'VENTA' THEN
            CASE WHEN v.venta_final = 0 OR v.venta_final IS NULL THEN NULL
                 ELSE ROUND(t.ejecutado_mes * 100.0 / v.venta_final, 2) END
        ELSE
            CASE WHEN v.venta_mes = 0 OR v.venta_mes IS NULL THEN NULL
                 ELSE ROUND(t.ejecutado_mes * 100.0 / v.venta_mes, 2) END
    END                                       AS ejecutado_mes_pct,

    CASE
        WHEN t.concepto = 'VENTA' THEN
            CASE WHEN v.venta_final = 0 OR v.venta_final IS NULL THEN NULL
                 ELSE ROUND(t.pendiente_importe * 100.0 / v.venta_final, 2) END
        ELSE
            CASE WHEN v.venta_pendiente = 0 OR v.venta_pendiente IS NULL THEN NULL
                 ELSE ROUND(t.pendiente_importe * 100.0 / v.venta_pendiente, 2) END
    END                                       AS pendiente_pct,

    -- FINAL %:
    --   VENTA FINAL % = VENTA_FINAL / PRESUPUESTO_APROBADO
    --   Resto FINAL % = importe_FINAL / VENTA_FINAL
    CASE
        WHEN t.concepto = 'VENTA' THEN
            CASE WHEN a.aprobado_venta = 0 OR a.aprobado_venta IS NULL THEN NULL
                 ELSE ROUND(t.final_importe * 100.0 / a.aprobado_venta, 2) END
        ELSE
            CASE WHEN v.venta_final = 0 OR v.venta_final IS NULL THEN NULL
                 ELSE ROUND(t.final_importe * 100.0 / v.venta_final, 2) END
    END                                       AS final_pct,

    -- Variación % sobre el FINAL del mes anterior (queda como antes).
    CASE WHEN t.final_anterior IS NULL OR t.final_anterior = 0 THEN NULL
         ELSE ROUND(t.variacion_importe * 100.0 / t.final_anterior, 2) END AS variacion_pct,

    -- Trazabilidad
    t.final_fuente, t.final_version_master, t.final_version_tex,
    t.fase_numero, t.fase_nombre_mes
FROM todos t
LEFT JOIN venta_por_mes     v ON v.obra_id = t.obra_id AND v.anio_mes = t.anio_mes
LEFT JOIN aprobado_por_obra a ON a.obra_id = t.obra_id;

COMMENT ON VIEW cierre.v_pbi_cierre_resumen IS
'Cierre mensual de obra (Tanda 4). Porcentajes según Excel CONTROL DE GESTIÓN: '
'cada columna usa la VENTA de la misma columna como divisor; VENTA FINAL '
'usa presupuesto_aprobado_venta de la cabecera.';
