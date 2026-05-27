-- etl_sigrid/infrastructure/postgres/sql/cierre/03_views.sql
--
-- Vistas Power BI del cierre (Tanda 1.4).

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
-- Vista principal: 6 filas por (obra × mes) con todas las métricas € y %
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
        -- Si todos los costes son master/fase_0/sin_dato igual, se mantiene;
        -- si hay mezcla, gana la fuente "peor" (sin_dato > fase_0 > master).
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

todos AS (
    SELECT * FROM base
    UNION ALL SELECT * FROM gastos
    UNION ALL SELECT * FROM beneficio
)
SELECT
    obra_id, codigo_obra, nombre_obra,
    anio_mes, anio, mes, nombre_mes,
    concepto, orden_concepto,
    ejecutado_origen, ejecutado_anterior, ejecutado_mes,
    final_importe, final_anterior, pendiente_importe, variacion_importe,
    CASE WHEN final_importe = 0 THEN NULL
         ELSE ROUND(ejecutado_origen   * 100.0 / final_importe, 2) END AS ejecutado_origen_pct,
    CASE WHEN final_importe = 0 THEN NULL
         ELSE ROUND(ejecutado_anterior * 100.0 / final_importe, 2) END AS ejecutado_anterior_pct,
    CASE WHEN final_importe = 0 THEN NULL
         ELSE ROUND(ejecutado_mes      * 100.0 / final_importe, 2) END AS ejecutado_mes_pct,
    CASE WHEN final_importe = 0 THEN NULL
         ELSE ROUND(pendiente_importe  * 100.0 / final_importe, 2) END AS pendiente_pct,
    CASE WHEN final_anterior IS NULL OR final_anterior = 0 THEN NULL
         ELSE ROUND(variacion_importe  * 100.0 / final_anterior, 2) END AS variacion_pct,
    final_fuente, final_version_master, final_version_tex,
    fase_numero, fase_nombre_mes
FROM todos;

COMMENT ON VIEW cierre.v_pbi_cierre_resumen IS
'Cierre mensual de obra (Tanda 1.4). 6 conceptos × (obra × mes) con '
'importes y %. final_fuente: master | fase_0 | sin_dato.';
