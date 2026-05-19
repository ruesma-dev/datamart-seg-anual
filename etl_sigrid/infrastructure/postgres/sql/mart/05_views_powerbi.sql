-- etl_sigrid/infrastructure/postgres/sql/mart/05_views_powerbi.sql
--
-- Vistas optimizadas para Power BI. Implementan un modelo en estrella:
--   DimObra → FactPBI ← DimPartida
--                 ↑
--              DimFecha
--              DimEscenario
--
-- Beneficios sobre conectar a las tablas directamente:
--   1. Desacopla Power BI de cambios internos del mart.
--   2. La fact se aligera: solo IDs e importes (no strings que se repiten).
--   3. Las dimensiones se construyen en SQL (más rápido y mantenible).
--   4. Cualquier consumidor (Power BI, Excel, Tableau...) las usa igual.

-- ===========================================================================
-- DIMENSIÓN OBRA
-- ===========================================================================
DROP VIEW IF EXISTS mart.v_pbi_dim_obra CASCADE;
CREATE VIEW mart.v_pbi_dim_obra AS
SELECT
    obra_id,
    codigo_obra,
    nombre_obra,
    -- Texto combinado para visualización compacta en segmentadores
    codigo_obra || ' · ' || COALESCE(nombre_obra, '(sin nombre)') AS obra_label
FROM stg.obras;

COMMENT ON VIEW mart.v_pbi_dim_obra IS
'Dimensión obra para Power BI. Clave: obra_id.';


-- ===========================================================================
-- DIMENSIÓN PARTIDA
-- ===========================================================================
-- Incluye atributos para drill-down jerárquico:
--   categoria → capitulo_raiz_cod → ruta_capitulos → codigo_partida
-- Y campos auxiliares para etiquetas y orden.
DROP VIEW IF EXISTS mart.v_pbi_dim_partida CASCADE;
CREATE VIEW mart.v_pbi_dim_partida AS
SELECT
    partida_id,
    obra_id,                                  -- relación auxiliar (1 partida pertenece a 1 obra)
    codigo_partida,
    descripcion_corta                AS descripcion_partida,
    unidad_medida,
    categoria,
    capitulo_raiz_cod,
    ruta_capitulos,
    nivel,
    activa,
    -- Etiqueta para segmentador / tooltip: "01.02 · EXCAVACION VACIADOS"
    COALESCE(codigo_partida, '')
        || CASE WHEN descripcion_corta IS NOT NULL
                THEN ' · ' || descripcion_corta
                ELSE '' END           AS partida_label,
    -- Sólo partidas hoja (no capítulos) para visuales de detalle.
    -- Útil para filtrar en Power BI si se quiere solo partidas hoja.
    CASE WHEN nivel >= 2 OR codigo_partida LIKE '%.%'
         THEN TRUE ELSE FALSE
    END                                AS es_hoja
FROM stg.partidas;

COMMENT ON VIEW mart.v_pbi_dim_partida IS
'Dimensión partida para Power BI. Clave: partida_id. Incluye categoría y ruta.';


-- ===========================================================================
-- DIMENSIÓN ESCENARIO (estática)
-- ===========================================================================
DROP VIEW IF EXISTS mart.v_pbi_dim_escenario CASCADE;
CREATE VIEW mart.v_pbi_dim_escenario AS
SELECT * FROM (
    VALUES
        ('Coste Real',        'REAL',        'COSTE', 3,  1),
        ('Coste Planificado', 'PLANIFICADO', 'COSTE', 8,  2),
        ('Venta Real',        'REAL',        'VENTA', 7,  3),
        ('Venta Planificada', 'PLANIFICADO', 'VENTA', 11, 4)
) AS t(escenario, tipo_dato, concepto, ambito_id, orden);

COMMENT ON VIEW mart.v_pbi_dim_escenario IS
'Dimensión escenario. Clave: escenario (texto). Sirve para ordenar y filtrar.';


-- ===========================================================================
-- DIMENSIÓN FECHA
-- ===========================================================================
-- Calendario mensual desde el mes mínimo del fact hasta el máximo + buffer.
-- Genera UNA fila por mes (no por día) ya que el grano del fact es mensual.
DROP VIEW IF EXISTS mart.v_pbi_dim_fecha CASCADE;
CREATE VIEW mart.v_pbi_dim_fecha AS
WITH rango AS (
    SELECT
        COALESCE(MIN(anio_mes), '2024-01-01'::DATE) AS mes_min,
        COALESCE(MAX(anio_mes), CURRENT_DATE)
            + INTERVAL '12 months'                   AS mes_max
    FROM mart.fact_seguimiento_mensual
),
meses AS (
    SELECT
        generate_series(
            (SELECT mes_min FROM rango),
            (SELECT mes_max FROM rango),
            INTERVAL '1 month'
        )::DATE AS anio_mes
)
SELECT
    anio_mes,
    EXTRACT(YEAR  FROM anio_mes)::INT      AS anio,
    EXTRACT(MONTH FROM anio_mes)::INT      AS mes,
    EXTRACT(QUARTER FROM anio_mes)::INT    AS trimestre,
    -- Nombres en castellano (TM = locale traducido)
    to_char(anio_mes, 'TMMonth')           AS nombre_mes_solo,
    to_char(anio_mes, 'TMMonth YYYY')      AS nombre_mes_anio,
    to_char(anio_mes, 'YYYY-MM')           AS anio_mes_iso,
    'T' || EXTRACT(QUARTER FROM anio_mes)::INT
        || ' ' || EXTRACT(YEAR FROM anio_mes)::INT  AS trimestre_label,
    -- Atributos útiles para análisis
    CASE WHEN anio_mes <= date_trunc('month', CURRENT_DATE)
         THEN TRUE ELSE FALSE
    END                                    AS es_pasado_o_actual,
    CASE WHEN anio_mes = date_trunc('month', CURRENT_DATE)
         THEN TRUE ELSE FALSE
    END                                    AS es_mes_actual
FROM meses;

COMMENT ON VIEW mart.v_pbi_dim_fecha IS
'Calendario mensual. Clave: anio_mes (primer día del mes). Sirve para marcar como Date Table en Power BI.';


-- ===========================================================================
-- FACT ALIGERADA PARA POWER BI
-- ===========================================================================
-- Solo IDs e importes. Sin strings ni metadatos (los pone Power BI vía dims).
-- Esto reduce el tamaño en VertiPaq y acelera filtros.
DROP VIEW IF EXISTS mart.v_pbi_fact CASCADE;
CREATE VIEW mart.v_pbi_fact AS
SELECT
    fact_id,
    -- FKs a las dimensiones
    obra_id,
    partida_id,
    anio_mes,
    escenario,
    -- Métricas (Sigrid-compatible)
    importe_mes,
    importe_origen,
    -- Métricas raw (referencia)
    importe_mes_raw,
    importe_origen_raw,
    -- Cantidades
    can_mes,
    can_origen,
    precio_unitario,
    -- Trazabilidad master (planificado) - útil para drill
    version_master,
    version_descripcion,
    tipo_master,
    -- Incurrido (solo coste real)
    total_incurrido,
    total_incurrido_mes
FROM mart.fact_seguimiento_mensual;

COMMENT ON VIEW mart.v_pbi_fact IS
'Fact aligerada para Power BI. Solo IDs e importes. FKs a v_pbi_dim_*.';


-- ===========================================================================
-- FACT AGREGADA POR CATEGORÍA (versión para Power BI)
-- ===========================================================================
DROP VIEW IF EXISTS mart.v_pbi_fact_categoria CASCADE;
CREATE VIEW mart.v_pbi_fact_categoria AS
SELECT
    fact_cat_id,
    obra_id,
    anio_mes,
    categoria,
    escenario,
    importe_mes,
    importe_origen,
    num_partidas
FROM mart.fact_seguimiento_categoria;

COMMENT ON VIEW mart.v_pbi_fact_categoria IS
'Fact pre-agregada por categoría para visuales rápidos. Grano: (obra,mes,cat,esc).';
