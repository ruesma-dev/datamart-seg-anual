-- etl_sigrid/infrastructure/postgres/sql/cierre/04_views_detalle.sql
--
-- =========================================================================
-- TANDA 2.1 — Desglose fino de INDIRECTOS y GENERALES con nombres legibles
-- =========================================================================
--
-- Cambio respecto a Tanda 2:
--   En INDIRECTOS detalle, además de los códigos exponemos los NOMBRES
--   legibles desde stg.partidas.descripcion_corta:
--     - grupo_nombre        = descripcion_corta del capítulo de nivel 2
--     - subcategoria_nombre = descripcion_corta del capítulo de nivel 3
--
-- Para Power BI: usar 'grupo_nombre' y 'subcategoria_nombre' como etiquetas
-- visibles, con Sort by Column sobre orden_grupo y orden_subcategoria.
-- Los códigos (grupo_cod, subcategoria_cod) se mantienen para joins,
-- debugging y posibles drill-throughs.
--
-- INDIRECTOS (CI):
--   grupo        = nivel 2 de stg.partidas.ruta_capitulos
--   subcategoria = nivel 3 de ruta_capitulos
--   Niveles 4+ se agrupan bajo su nivel 3; partidas con < nivel 3 caen a
--   subcategoria = "(sin detalle)".
--
-- GENERALES (CP):
--   Tipología en cascada (idéntico a v_pbi_cp_tipologia del mart):
--     1) subcapítulo definitorio (CP.1..CP.4, CP.6, CP.9, CP.12)
--     2) fallback por LIKE sobre descripcion_corta
--     3) resto → APORTE GG
-- =========================================================================

DROP VIEW IF EXISTS cierre.v_pbi_cierre_indirectos_detalle CASCADE;
DROP VIEW IF EXISTS cierre.v_pbi_cierre_generales_detalle  CASCADE;
DROP VIEW IF EXISTS cierre.v_pbi_dim_subcategoria_ci       CASCADE;
DROP VIEW IF EXISTS cierre.v_pbi_dim_tipologia_cp          CASCADE;


-- =========================================================================
-- DIMENSIÓN CI: catálogo (grupo_cod, grupo_nombre, subcategoria_cod,
--               subcategoria_nombre) con orden estable para Power BI.
-- =========================================================================
CREATE VIEW cierre.v_pbi_dim_subcategoria_ci AS
WITH
nombres AS (
    -- Catálogo de nombres por código de capítulo. Cada capítulo intermedio
    -- y cada partida hoja tiene una fila en stg.partidas con codigo_partida
    -- y descripcion_corta. Una obra distinta podría tener distinto nombre
    -- para el mismo código; MAX nos da uno estable.
    SELECT codigo_partida, MAX(descripcion_corta) AS descripcion_corta
      FROM stg.partidas
     WHERE codigo_partida IS NOT NULL
     GROUP BY codigo_partida
),
catalogo AS (
    SELECT DISTINCT
        COALESCE(NULLIF(split_part(p.ruta_capitulos, ' > ', 2), ''), 'CI')           AS grupo_cod,
        COALESCE(NULLIF(split_part(p.ruta_capitulos, ' > ', 3), ''), '(sin detalle)') AS subcategoria_cod
    FROM stg.partidas p
    WHERE p.categoria = 'CI'
)
SELECT
    c.grupo_cod,
    COALESCE(ng.descripcion_corta, c.grupo_cod)                       AS grupo_nombre,
    c.subcategoria_cod,
    CASE WHEN c.subcategoria_cod = '(sin detalle)' THEN '(sin detalle)'
         ELSE COALESCE(ns.descripcion_corta, c.subcategoria_cod) END  AS subcategoria_nombre,
    DENSE_RANK() OVER (
        ORDER BY COALESCE(ng.descripcion_corta, c.grupo_cod)
    )                                                                  AS orden_grupo,
    ROW_NUMBER() OVER (
        PARTITION BY c.grupo_cod
        ORDER BY CASE WHEN c.subcategoria_cod = '(sin detalle)' THEN 1 ELSE 0 END,
                 COALESCE(ns.descripcion_corta, c.subcategoria_cod)
    )                                                                  AS orden_subcategoria
FROM catalogo c
LEFT JOIN nombres ng ON ng.codigo_partida = c.grupo_cod
LEFT JOIN nombres ns ON ns.codigo_partida = c.subcategoria_cod;

COMMENT ON VIEW cierre.v_pbi_dim_subcategoria_ci IS
'Dimensión de subcategorías de INDIRECTOS (CI). Resuelve grupo_nombre y '
'subcategoria_nombre desde stg.partidas.descripcion_corta. Orden alfabético '
'estable por nombre para Sort by Column en Power BI.';


-- =========================================================================
-- DIMENSIÓN CP: 6 tipologías fijas
-- =========================================================================
CREATE VIEW cierre.v_pbi_dim_tipologia_cp AS
SELECT * FROM (VALUES
    ('LEVANTAMIENTO',  1, 'Levantamiento topográfico'),
    ('SEGUROS',        2, 'Seguros (TRC, etc.)'),
    ('AVALES',         3, 'Avales y garantías'),
    ('CONTRATACION',   4, 'Contratación'),
    ('MEDIO AMBIENTE', 5, 'Medio ambiente / Calidad'),
    ('APORTE GG',      6, 'Aporte a Gastos Generales')
) AS t(tipologia, orden_tipologia, descripcion);


-- =========================================================================
-- VISTA: detalle INDIRECTOS por (obra × mes × grupo × subcategoria)
-- =========================================================================
CREATE VIEW cierre.v_pbi_cierre_indirectos_detalle AS
WITH
nombres AS (
    SELECT codigo_partida, MAX(descripcion_corta) AS descripcion_corta
      FROM stg.partidas
     WHERE codigo_partida IS NOT NULL
     GROUP BY codigo_partida
),
fases_con_mes AS (
    SELECT
        f.fase_id, f.obra_id, f.numero_fase, f.fecha_inicio, f.nombre_mes,
        cierre.fn_mes_de_fase(f.fecha_inicio, f.nombre_mes) AS mes_canonico
      FROM stg.fases f
     WHERE f.numero_fase >= 1
),
agregado AS (
    SELECT
        fm.obra_id,
        fm.mes_canonico                                     AS anio_mes,
        COALESCE(NULLIF(split_part(p.ruta_capitulos, ' > ', 2), ''), 'CI')           AS grupo_cod,
        COALESCE(NULLIF(split_part(p.ruta_capitulos, ' > ', 3), ''), '(sin detalle)') AS subcategoria_cod,
        SUM(pm.importe_origen)::NUMERIC(18,2)               AS ejecutado_origen
    FROM stg.plan_mensual pm
    JOIN fases_con_mes  fm ON fm.obra_id = pm.obra_id
                          AND fm.numero_fase = pm.version
    JOIN stg.partidas   p  ON p.partida_id = pm.partida_id
    WHERE pm.ambito_id = 3
      AND p.categoria  = 'CI'
      AND fm.mes_canonico IS NOT NULL
    GROUP BY fm.obra_id, fm.mes_canonico, grupo_cod, subcategoria_cod
),
con_lag AS (
    SELECT
        a.*,
        LAG(a.ejecutado_origen) OVER (
            PARTITION BY a.obra_id, a.grupo_cod, a.subcategoria_cod
            ORDER BY a.anio_mes
        ) AS ejecutado_anterior_lag
    FROM agregado a
)
SELECT
    cl.obra_id,
    o.codigo_obra,
    o.nombre_obra,
    cl.anio_mes,
    EXTRACT(YEAR  FROM cl.anio_mes)::INT                              AS anio,
    EXTRACT(MONTH FROM cl.anio_mes)::INT                              AS mes,
    to_char(cl.anio_mes, 'TMMonth YYYY')                              AS nombre_mes,
    -- CÓDIGOS (para joins y debugging)
    cl.grupo_cod,
    cl.subcategoria_cod,
    -- NOMBRES (etiquetas Power BI)
    COALESCE(ng.descripcion_corta, cl.grupo_cod)                       AS grupo_nombre,
    CASE WHEN cl.subcategoria_cod = '(sin detalle)' THEN '(sin detalle)'
         ELSE COALESCE(ns.descripcion_corta, cl.subcategoria_cod) END  AS subcategoria_nombre,
    -- IMPORTES
    cl.ejecutado_origen,
    COALESCE(cl.ejecutado_anterior_lag, 0)::NUMERIC(18,2)              AS ejecutado_anterior,
    (cl.ejecutado_origen - COALESCE(cl.ejecutado_anterior_lag, 0))::NUMERIC(18,2)
                                                                        AS ejecutado_mes
FROM con_lag cl
JOIN stg.obras o ON o.obra_id = cl.obra_id
LEFT JOIN nombres ng ON ng.codigo_partida = cl.grupo_cod
LEFT JOIN nombres ns ON ns.codigo_partida = cl.subcategoria_cod;

COMMENT ON VIEW cierre.v_pbi_cierre_indirectos_detalle IS
'Detalle INDIRECTOS por (obra × mes × grupo × subcategoria) con nombres '
'legibles (grupo_nombre, subcategoria_nombre) además de los códigos. '
'Grupo = nivel 2 de ruta_capitulos; subcategoria = nivel 3; niveles 4+ se '
'agregan bajo nivel 3. EJECUTADO solamente.';


-- =========================================================================
-- VISTA: detalle GENERALES por (obra × mes × tipología)
-- =========================================================================
CREATE VIEW cierre.v_pbi_cierre_generales_detalle AS
WITH
fases_con_mes AS (
    SELECT
        f.fase_id, f.obra_id, f.numero_fase, f.fecha_inicio, f.nombre_mes,
        cierre.fn_mes_de_fase(f.fecha_inicio, f.nombre_mes) AS mes_canonico
      FROM stg.fases f
     WHERE f.numero_fase >= 1
),
detalle_partida AS (
    SELECT
        fm.obra_id,
        fm.mes_canonico                       AS anio_mes,
        pm.partida_id,
        p.descripcion_corta,
        p.ruta_capitulos,
        SUM(pm.importe_origen)::NUMERIC(18,2) AS ejecutado_origen
    FROM stg.plan_mensual pm
    JOIN fases_con_mes  fm ON fm.obra_id = pm.obra_id
                          AND fm.numero_fase = pm.version
    JOIN stg.partidas   p  ON p.partida_id = pm.partida_id
    WHERE pm.ambito_id = 3
      AND p.categoria  = 'CP'
      AND fm.mes_canonico IS NOT NULL
    GROUP BY fm.obra_id, fm.mes_canonico, pm.partida_id,
             p.descripcion_corta, p.ruta_capitulos
),
con_tipologia AS (
    SELECT
        obra_id, anio_mes, ejecutado_origen,
        CASE
            WHEN split_part(ruta_capitulos, ' > ', 2) IN ('CP.9', 'CP.9_1')
                THEN 'LEVANTAMIENTO'
            WHEN split_part(ruta_capitulos, ' > ', 2) IN ('CP.1', 'CP.2', 'CP.3')
                THEN 'SEGUROS'
            WHEN split_part(ruta_capitulos, ' > ', 2) = 'CP.4'
                THEN 'AVALES'
            WHEN split_part(ruta_capitulos, ' > ', 2) = 'CP.6'
                THEN 'CONTRATACION'
            WHEN split_part(ruta_capitulos, ' > ', 2) = 'CP.12'
                THEN 'MEDIO AMBIENTE'
            WHEN UPPER(descripcion_corta) LIKE '%LEVANTAM%'
                THEN 'LEVANTAMIENTO'
            WHEN UPPER(descripcion_corta) LIKE '%SEGURO%'
                THEN 'SEGUROS'
            WHEN UPPER(descripcion_corta) LIKE '%AVAL%'
              OR UPPER(descripcion_corta) LIKE '%GARANTIA%'
                THEN 'AVALES'
            WHEN UPPER(descripcion_corta) LIKE '%CONTRATAC%'
                THEN 'CONTRATACION'
            WHEN UPPER(descripcion_corta) LIKE '%CALIDAD%'
              OR UPPER(descripcion_corta) LIKE '%MEDIO AMB%'
                THEN 'MEDIO AMBIENTE'
            ELSE 'APORTE GG'
        END AS tipologia
    FROM detalle_partida
),
agregado AS (
    SELECT obra_id, anio_mes, tipologia,
           SUM(ejecutado_origen)::NUMERIC(18,2) AS ejecutado_origen
      FROM con_tipologia
     GROUP BY obra_id, anio_mes, tipologia
),
con_lag AS (
    SELECT
        a.*,
        LAG(a.ejecutado_origen) OVER (
            PARTITION BY a.obra_id, a.tipologia ORDER BY a.anio_mes
        ) AS ejecutado_anterior_lag
    FROM agregado a
)
SELECT
    cl.obra_id,
    o.codigo_obra,
    o.nombre_obra,
    cl.anio_mes,
    EXTRACT(YEAR  FROM cl.anio_mes)::INT  AS anio,
    EXTRACT(MONTH FROM cl.anio_mes)::INT  AS mes,
    to_char(cl.anio_mes, 'TMMonth YYYY')  AS nombre_mes,
    cl.tipologia,
    CASE cl.tipologia
        WHEN 'LEVANTAMIENTO'  THEN 1
        WHEN 'SEGUROS'        THEN 2
        WHEN 'AVALES'         THEN 3
        WHEN 'CONTRATACION'   THEN 4
        WHEN 'MEDIO AMBIENTE' THEN 5
        WHEN 'APORTE GG'      THEN 6
        ELSE 9
    END                                    AS orden_tipologia,
    cl.ejecutado_origen,
    COALESCE(cl.ejecutado_anterior_lag, 0)::NUMERIC(18,2)               AS ejecutado_anterior,
    (cl.ejecutado_origen - COALESCE(cl.ejecutado_anterior_lag, 0))::NUMERIC(18,2)
                                                                        AS ejecutado_mes
FROM con_lag cl
JOIN stg.obras o ON o.obra_id = cl.obra_id;
