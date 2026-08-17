-- etl_sigrid/infrastructure/postgres/sql/cierre/04_views_detalle.sql
--
-- =========================================================================
-- TANDA 4 — Detalle CI con nombres POR OBRA + periodificación infraestructura
-- =========================================================================
--
-- CORRECCIÓN respecto a Tanda 2.1: el nombre del capítulo (grupo y
-- subcategoría) se resolvía con MAX(descripcion) GROUP BY codigo_partida
-- GLOBAL, lo que hacía que un código (p.ej. CI.2) tomase el nombre de
-- CUALQUIER obra. Resultado real visto en obra 0664: CI.2 salía como
-- "JEFE OBRA" cuando en esa obra es realmente "INFRAESTRUCTURA".
-- Fix: el JOIN para resolver el nombre se hace POR (obra_id, codigo_partida),
-- nunca global.
--
-- AÑADIDO — periodificación de INFRAESTRUCTURA:
--   Solo para partidas cuyo grupo de nivel 2 se reconoce como INFRAESTRUCTURA
--   (nombre LIKE '%INFRA%'). Para cada partida CI infra y cada mes M:
--
--     importe_fase0     = stg.presupuesto.importe de la partida (amb=3 fas=0)
--                          (Previsto vivo del coste — su importe total
--                           planificado a fecha de hoy)
--     produccion_M      = SUM(plan_mensual.importe_origen) amb=7 fase del mes M
--     produccion_final  = VENTA FINAL del mes M (final_importe en fact_cierre)
--     ratio_M           = produccion_M / produccion_final
--     origen_periodif_M = importe_fase0 × ratio_M
--     mes_periodif_M    = origen_periodif_M − origen_periodif_(M-1)
--
--   Se exponen como columnas adicionales del detalle de indirectos. Para los
--   grupos que NO son infraestructura las columnas vienen NULL.
-- =========================================================================

DROP VIEW IF EXISTS cierre.v_pbi_cierre_indirectos_detalle CASCADE;
DROP VIEW IF EXISTS cierre.v_pbi_cierre_generales_detalle  CASCADE;
DROP VIEW IF EXISTS cierre.v_pbi_dim_subcategoria_ci       CASCADE;
DROP VIEW IF EXISTS cierre.v_pbi_dim_tipologia_cp          CASCADE;


-- =========================================================================
-- Helper: nombres de capítulo POR OBRA (no global)
-- =========================================================================
-- Para cada (obra_id, codigo_partida), la descripcion_corta. Un capítulo
-- intermedio puede llamarse distinto en cada obra; aquí lo respetamos.
-- =========================================================================
-- (No es vista pública; se usa internamente con CTE en cada vista.)


-- =========================================================================
-- DIMENSIÓN CI: catálogo por OBRA (grupo_cod, grupo_nombre, subcategoria_*)
-- =========================================================================
CREATE VIEW cierre.v_pbi_dim_subcategoria_ci AS
WITH
nombres_por_obra AS (
    -- Una fila por (obra_id, codigo_partida) con su descripción de ESA obra
    SELECT
        obra_id,
        codigo_partida,
        MAX(descripcion_corta) AS descripcion_corta
    FROM stg.partidas
    WHERE codigo_partida IS NOT NULL
    GROUP BY obra_id, codigo_partida
),
catalogo AS (
    SELECT DISTINCT
        p.obra_id,
        COALESCE(NULLIF(split_part(p.ruta_capitulos, ' > ', 2), ''), 'CI')           AS grupo_cod,
        COALESCE(NULLIF(split_part(p.ruta_capitulos, ' > ', 3), ''), '(sin detalle)') AS subcategoria_cod
    FROM stg.partidas p
    WHERE p.categoria = 'CI'
)
SELECT
    c.obra_id,
    c.grupo_cod,
    COALESCE(ng.descripcion_corta, c.grupo_cod)                       AS grupo_nombre,
    c.subcategoria_cod,
    CASE WHEN c.subcategoria_cod = '(sin detalle)' THEN '(sin detalle)'
         ELSE COALESCE(ns.descripcion_corta, c.subcategoria_cod) END  AS subcategoria_nombre,
    DENSE_RANK() OVER (
        PARTITION BY c.obra_id
        ORDER BY COALESCE(ng.descripcion_corta, c.grupo_cod)
    )                                                                  AS orden_grupo,
    ROW_NUMBER() OVER (
        PARTITION BY c.obra_id, c.grupo_cod
        ORDER BY CASE WHEN c.subcategoria_cod = '(sin detalle)' THEN 1 ELSE 0 END,
                 COALESCE(ns.descripcion_corta, c.subcategoria_cod)
    )                                                                  AS orden_subcategoria
FROM catalogo c
LEFT JOIN nombres_por_obra ng
       ON ng.obra_id = c.obra_id AND ng.codigo_partida = c.grupo_cod
LEFT JOIN nombres_por_obra ns
       ON ns.obra_id = c.obra_id AND ns.codigo_partida = c.subcategoria_cod;

COMMENT ON VIEW cierre.v_pbi_dim_subcategoria_ci IS
'Dimensión de subcategorías CI POR OBRA. Cada (obra, código) resuelve su '
'nombre dentro de la propia obra (no global), evitando que p.ej. CI.2 herede '
'el nombre que otra obra le da.';


-- =========================================================================
-- DIMENSIÓN CP: 6 tipologías fijas (sin cambios)
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
--   + nombres POR OBRA
--   + columnas de periodificación (solo grupo INFRAESTRUCTURA)
-- =========================================================================
CREATE VIEW cierre.v_pbi_cierre_indirectos_detalle AS
WITH
nombres_por_obra AS (
    SELECT obra_id, codigo_partida, MAX(descripcion_corta) AS descripcion_corta
    FROM stg.partidas
    WHERE codigo_partida IS NOT NULL
    GROUP BY obra_id, codigo_partida
),
fases_con_mes AS (
    SELECT
        f.fase_id, f.obra_id, f.numero_fase, f.fecha_inicio, f.nombre_mes,
        cierre.fn_mes_de_fase(f.fecha_inicio, f.nombre_mes) AS mes_canonico
      FROM stg.fases f
     WHERE f.numero_fase >= 1
),

-- A) Partidas CI clasificadas (grupo, subcategoría)
partidas_ci AS (
    SELECT
        p.partida_id, p.obra_id,
        COALESCE(NULLIF(split_part(p.ruta_capitulos, ' > ', 2), ''), 'CI')           AS grupo_cod,
        COALESCE(NULLIF(split_part(p.ruta_capitulos, ' > ', 3), ''), '(sin detalle)') AS subcategoria_cod
    FROM stg.partidas p
    WHERE p.categoria = 'CI'
),

-- B) Agregado base (ejecutado a origen) por (obra × mes × grupo × subcategoría)
agregado AS (
    SELECT
        fm.obra_id,
        fm.mes_canonico                       AS anio_mes,
        pci.grupo_cod,
        pci.subcategoria_cod,
        SUM(pm.importe_origen)::NUMERIC(18,2) AS ejecutado_origen
    FROM stg.plan_mensual pm
    JOIN fases_con_mes fm
        ON fm.obra_id = pm.obra_id AND fm.numero_fase = pm.version
    JOIN partidas_ci pci
        ON pci.partida_id = pm.partida_id
    WHERE pm.ambito_id = 3
      AND fm.mes_canonico IS NOT NULL
    GROUP BY fm.obra_id, fm.mes_canonico, pci.grupo_cod, pci.subcategoria_cod
),

-- C) VENTA por (obra × mes) — para el ratio de periodificación
--    produccion_origen[M] = ejecutado venta a origen del mes M
--    produccion_final[M]  = FINAL venta del mes M (master CIERRE vigente)
venta_por_mes AS (
    SELECT
        obra_id, anio_mes,
        ejecutado_origen AS venta_origen,
        final_importe    AS venta_final
    FROM cierre.fact_cierre_mensual
    WHERE concepto = 'VENTA'
),

-- D) Importe fase 0 amb=3 por partida (Previsto vivo de coste).
--    Es el "importe total planificado de la partida".
fase0_por_partida AS (
    SELECT
        pres.obra_id, pres.partida_id,
        pres.importe AS importe_fase0
    FROM stg.presupuesto pres
    WHERE pres.ambito_id = 3
      AND pres.fase_num  = 0
),

-- E) Total fase 0 por (obra × grupo × subcategoría) — solo CI
--    Suma los importes fase 0 de TODAS las partidas CI de la subcategoría.
--    Más adelante solo lo aplicamos cuando el grupo sea INFRAESTRUCTURA.
fase0_por_subcat AS (
    SELECT
        pci.obra_id,
        pci.grupo_cod,
        pci.subcategoria_cod,
        SUM(f0.importe_fase0)::NUMERIC(18,2) AS importe_fase0_subcat
    FROM partidas_ci pci
    JOIN fase0_por_partida f0
        ON f0.obra_id    = pci.obra_id
       AND f0.partida_id = pci.partida_id
    GROUP BY pci.obra_id, pci.grupo_cod, pci.subcategoria_cod
),

-- F) Ratio de producción por (obra × mes) y flag si el grupo es infra
--    (lo decidimos por el nombre del capítulo nivel 2 — robusto entre obras).
nombre_grupo AS (
    SELECT
        obra_id,
        codigo_partida AS grupo_cod,
        descripcion_corta AS grupo_nombre
    FROM nombres_por_obra
),

-- F.bis) PLAZO de la obra para la periodificación LINEAL por meses.
--   Inicio: mejor fecha disponible (real > previsto, de obrctr o obr).
--   Fin:    mejor fecha disponible (real > previsto, de obrctr o obr).
--   Las fechas vienen ya combinadas en v_pbi_cierre_cabecera.
--   Plazo total = diferencia de meses CALENDARIO (inclusivo: mes inicial = 1).
--     plazo = (anio_fin*12 + mes_fin) - (anio_ini*12 + mes_ini) + 1
--   Esto es consistente con el numerador del ratio (mismo cálculo).
--   Si fin < inicio o falta una fecha, plazo_total = NULL.
plazo_obra AS (
    SELECT
        cab.obra_id,
        COALESCE(cab.fecha_inicio_real, cab.fecha_inicio_previsto)  AS fecha_inicio,
        COALESCE(cab.fecha_fin_real,    cab.fecha_fin_previsto)     AS fecha_fin,
        CASE
            WHEN COALESCE(cab.fecha_inicio_real, cab.fecha_inicio_previsto) IS NULL THEN NULL
            WHEN COALESCE(cab.fecha_fin_real,    cab.fecha_fin_previsto)    IS NULL THEN NULL
            WHEN COALESCE(cab.fecha_fin_real,    cab.fecha_fin_previsto)
               < COALESCE(cab.fecha_inicio_real, cab.fecha_inicio_previsto) THEN NULL
            ELSE GREATEST(
                ((EXTRACT(YEAR  FROM COALESCE(cab.fecha_fin_real, cab.fecha_fin_previsto))::INT * 12
                + EXTRACT(MONTH FROM COALESCE(cab.fecha_fin_real, cab.fecha_fin_previsto))::INT)
              - (EXTRACT(YEAR  FROM COALESCE(cab.fecha_inicio_real, cab.fecha_inicio_previsto))::INT * 12
                + EXTRACT(MONTH FROM COALESCE(cab.fecha_inicio_real, cab.fecha_inicio_previsto))::INT)
                + 1)::NUMERIC,
                1.0
            )
        END                                                          AS plazo_total_meses
    FROM cierre.v_pbi_cierre_cabecera cab
),

-- G.bis) Primer mes con INCURRIDO real por (obra, grupo, subcategoria).
--   La variante "CON INCURRIDO" de la periodificación arranca solo cuando
--   aparece el primer mes con ejecutado_origen > 0 en esa subcat. Antes,
--   queda en 0 (no se anticipa el periodificado mientras no haya gasto).
primer_mes_incurrido AS (
    SELECT
        obra_id, grupo_cod, subcategoria_cod,
        MIN(anio_mes) AS mes_inicio_incurrido
    FROM agregado
    WHERE ejecutado_origen > 0
    GROUP BY obra_id, grupo_cod, subcategoria_cod
),

-- G) Construir la salida combinando todo, calculando periodificación SOLO
--    cuando el grupo es INFRAESTRUCTURA y la VENTA tiene datos.
combinado AS (
    SELECT
        a.obra_id, a.anio_mes, a.grupo_cod, a.subcategoria_cod,
        a.ejecutado_origen,
        ng.grupo_nombre,
        UPPER(COALESCE(ng.grupo_nombre, a.grupo_cod)) LIKE '%INFRA%' AS es_infraestructura,
        f0s.importe_fase0_subcat,
        v.venta_origen, v.venta_final,
        -- Ratio y origen periodificado POR PRODUCCIÓN — solo infraestructura
        CASE
            WHEN UPPER(COALESCE(ng.grupo_nombre, a.grupo_cod)) NOT LIKE '%INFRA%' THEN NULL
            WHEN v.venta_final IS NULL OR v.venta_final = 0 THEN NULL
            ELSE v.venta_origen / v.venta_final
        END AS ratio_periodif,
        CASE
            WHEN UPPER(COALESCE(ng.grupo_nombre, a.grupo_cod)) NOT LIKE '%INFRA%' THEN NULL
            WHEN v.venta_final IS NULL OR v.venta_final = 0 THEN NULL
            WHEN f0s.importe_fase0_subcat IS NULL THEN NULL
            ELSE ROUND(
                (f0s.importe_fase0_subcat * v.venta_origen / v.venta_final)::NUMERIC,
                2
            )
        END AS ejecutado_origen_periodif,
        -- VARIANTE PRODUCCIÓN CON INCURRIDO (Tanda 4.2):
        -- Igual que la anterior, pero solo se calcula a partir del primer
        -- mes con incurrido en esa subcategoría. Antes = 0.
        CASE
            WHEN UPPER(COALESCE(ng.grupo_nombre, a.grupo_cod)) NOT LIKE '%INFRA%' THEN NULL
            WHEN v.venta_final IS NULL OR v.venta_final = 0 THEN NULL
            WHEN f0s.importe_fase0_subcat IS NULL THEN NULL
            WHEN pmi.mes_inicio_incurrido IS NULL THEN 0::NUMERIC  -- nunca ha entrado
            WHEN a.anio_mes < pmi.mes_inicio_incurrido    THEN 0::NUMERIC  -- aún no entra
            ELSE ROUND(
                (f0s.importe_fase0_subcat * v.venta_origen / v.venta_final)::NUMERIC,
                2
            )
        END AS ejecutado_origen_periodif_prod_inc,
        -- =================================================================
        -- Periodificación LINEAL POR MESES (NUEVA Tanda 4.1)
        -- =================================================================
        --   ratio_lineal = MIN( mes_actual / plazo_total, 1.0 )
        --     mes_actual = nº de meses transcurridos desde el inicio de obra
        --                  hasta el primer día del mes que estamos calculando.
        --                  Si el mes es ANTERIOR al inicio, ratio = 0.
        --   plazo_total = fecha_fin - fecha_inicio en meses (capa en 1 mínimo).
        --   Solo aplica si grupo es INFRAESTRUCTURA y plazo_total no es NULL.
        --
        --   Como siempre vamos a origen, el parcial de un mes puede salir
        --   negativo si el plazo se ALARGA (el divisor crece y el origen
        --   anterior se calculó con plazo menor). Aceptado.
        po.plazo_total_meses,
        po.fecha_inicio                                          AS fecha_inicio_obra,
        CASE
            WHEN UPPER(COALESCE(ng.grupo_nombre, a.grupo_cod)) NOT LIKE '%INFRA%' THEN NULL
            WHEN po.plazo_total_meses IS NULL THEN NULL
            ELSE GREATEST(
                -- Meses desde inicio (1-indexed: mes del inicio = 1)
                -- SIN CAP al 100%: si el plazo cambia o nos pasamos del fin
                -- previsto, el ratio puede ser >1 (Tanda 4.2). Solo se evita
                -- ratio negativo (meses anteriores al inicio).
                ((EXTRACT(YEAR  FROM a.anio_mes)::INT * 12 + EXTRACT(MONTH FROM a.anio_mes)::INT)
               - (EXTRACT(YEAR  FROM po.fecha_inicio)::INT * 12 + EXTRACT(MONTH FROM po.fecha_inicio)::INT)
               + 1)::NUMERIC / po.plazo_total_meses,
                0::NUMERIC
            )
        END AS ratio_lineal,
        CASE
            WHEN UPPER(COALESCE(ng.grupo_nombre, a.grupo_cod)) NOT LIKE '%INFRA%' THEN NULL
            WHEN po.plazo_total_meses IS NULL THEN NULL
            WHEN f0s.importe_fase0_subcat IS NULL THEN NULL
            ELSE ROUND(
                (f0s.importe_fase0_subcat
               * GREATEST(
                    ((EXTRACT(YEAR  FROM a.anio_mes)::INT * 12 + EXTRACT(MONTH FROM a.anio_mes)::INT)
                   - (EXTRACT(YEAR  FROM po.fecha_inicio)::INT * 12 + EXTRACT(MONTH FROM po.fecha_inicio)::INT)
                   + 1)::NUMERIC / po.plazo_total_meses,
                    0::NUMERIC
                ))::NUMERIC,
                2
            )
        END AS ejecutado_origen_periodif_lineal,
        -- VARIANTE LINEAL CON INCURRIDO (Tanda 4.2):
        -- Igual que la lineal pero solo arranca cuando entra el incurrido.
        CASE
            WHEN UPPER(COALESCE(ng.grupo_nombre, a.grupo_cod)) NOT LIKE '%INFRA%' THEN NULL
            WHEN po.plazo_total_meses IS NULL THEN NULL
            WHEN f0s.importe_fase0_subcat IS NULL THEN NULL
            WHEN pmi.mes_inicio_incurrido IS NULL THEN 0::NUMERIC
            WHEN a.anio_mes < pmi.mes_inicio_incurrido    THEN 0::NUMERIC
            ELSE ROUND(
                (f0s.importe_fase0_subcat
               * GREATEST(
                    ((EXTRACT(YEAR  FROM a.anio_mes)::INT * 12 + EXTRACT(MONTH FROM a.anio_mes)::INT)
                   - (EXTRACT(YEAR  FROM po.fecha_inicio)::INT * 12 + EXTRACT(MONTH FROM po.fecha_inicio)::INT)
                   + 1)::NUMERIC / po.plazo_total_meses,
                    0::NUMERIC
                ))::NUMERIC,
                2
            )
        END AS ejecutado_origen_periodif_lineal_inc
    FROM agregado a
    LEFT JOIN nombre_grupo ng
        ON ng.obra_id = a.obra_id AND ng.grupo_cod = a.grupo_cod
    LEFT JOIN fase0_por_subcat f0s
        ON f0s.obra_id = a.obra_id
       AND f0s.grupo_cod = a.grupo_cod
       AND f0s.subcategoria_cod = a.subcategoria_cod
    LEFT JOIN venta_por_mes v
        ON v.obra_id = a.obra_id AND v.anio_mes = a.anio_mes
    LEFT JOIN plazo_obra po
        ON po.obra_id = a.obra_id
    LEFT JOIN primer_mes_incurrido pmi
        ON pmi.obra_id          = a.obra_id
       AND pmi.grupo_cod        = a.grupo_cod
       AND pmi.subcategoria_cod = a.subcategoria_cod
),

-- =====================================================================
-- CON_LAG: calcula el valor del MES ANTERIOR para todos los conceptos.
-- =====================================================================
-- IMPORTANTE (Tanda 4.2): el PARCIAL de cada periodificación se calcula
-- restando contra `ejecutado_origen` del mes anterior (el INCURRIDO REAL
-- leído de plan_mensual, que Ruesma ajustará manualmente en Sigrid para
-- que refleje el periodif del mes anterior). NO se usa LAG sobre el propio
-- periodif calculado, porque ese se recalcularía con el plazo actual y
-- perderíamos la realidad del cierre del mes anterior.
--
-- Comportamiento:
--   parcial_periodif[M] = origen_periodif[M] - ejecutado_origen[M-1]
--   Si el mes anterior tenía valor distinto al periodif (porque no se
--   ajustó), el parcial mostrará la diferencia entre lo planificado por
--   ratio y lo realmente acumulado. Si Ruesma ajustó el cierre anterior
--   al periodif, el parcial será el "delta del ratio" del mes.
con_lag AS (
    SELECT
        c.*,
        LAG(c.ejecutado_origen) OVER (
            PARTITION BY c.obra_id, c.grupo_cod, c.subcategoria_cod
            ORDER BY c.anio_mes
        ) AS ejecutado_origen_anterior
    FROM combinado c
),
sub_nombres AS (
    SELECT obra_id, codigo_partida AS subcategoria_cod, descripcion_corta AS subcategoria_nombre
    FROM nombres_por_obra
)
-- =====================================================================
-- SELECT FINAL: Tanda 4.2
-- =====================================================================
-- 4 variantes de periodificación, cada una con su origen, parcial y %:
--   1) PROD      = producción (venta_origen/venta_final) × fase0
--   2) PROD_INC  = igual pero solo desde el primer mes con incurrido
--   3) LINEAL    = (mes_actual/plazo_total) × fase0  (sin cap)
--   4) LINEAL_INC= igual pero solo desde el primer mes con incurrido
--
-- El PARCIAL de las 4 se calcula contra `ejecutado_origen_anterior`
-- (= incurrido del mes anterior leído de plan_mensual, que Ruesma habrá
-- ajustado manualmente en Sigrid para reflejar el periodif).
SELECT
    cl.obra_id,
    o.codigo_obra,
    o.nombre_obra,
    cl.anio_mes,
    EXTRACT(YEAR  FROM cl.anio_mes)::INT                              AS anio,
    EXTRACT(MONTH FROM cl.anio_mes)::INT                              AS mes,
    -- Nombre del mes SIN locale: no puede depender de lc_time del servidor.
    (ARRAY['Enero','Febrero','Marzo','Abril','Mayo','Junio',
           'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'])
          [EXTRACT(MONTH FROM cl.anio_mes)::INT]
        || ' ' || EXTRACT(YEAR FROM cl.anio_mes)::INT                 AS nombre_mes,
    -- CÓDIGOS y NOMBRES
    cl.grupo_cod,
    cl.subcategoria_cod,
    COALESCE(cl.grupo_nombre, cl.grupo_cod)                            AS grupo_nombre,
    CASE WHEN cl.subcategoria_cod = '(sin detalle)' THEN '(sin detalle)'
         ELSE COALESCE(sn.subcategoria_nombre, cl.subcategoria_cod) END AS subcategoria_nombre,
    -- EJECUTADO REAL
    cl.ejecutado_origen,
    COALESCE(cl.ejecutado_origen_anterior, 0)::NUMERIC(18,2)           AS ejecutado_anterior,
    (cl.ejecutado_origen - COALESCE(cl.ejecutado_origen_anterior, 0))::NUMERIC(18,2)
                                                                        AS ejecutado_mes,
    -- Información de la subcategoría (para todas las variantes periodif)
    cl.es_infraestructura,
    cl.importe_fase0_subcat                                            AS importe_fase0,
    cl.plazo_total_meses,

    -- ===================================================================
    -- VARIANTE 1: PERIODIFICACIÓN POR PRODUCCIÓN (sin filtro de incurrido)
    -- ===================================================================
    cl.ratio_periodif,
    CASE WHEN cl.ratio_periodif IS NULL THEN NULL
         ELSE ROUND(cl.ratio_periodif * 100.0, 2) END                  AS pct_periodificacion,
    cl.ejecutado_origen_periodif,
    -- Parcial: origen_periodif[M] - ejecutado_origen[M-1]  (incurrido anterior)
    CASE WHEN cl.ejecutado_origen_periodif IS NULL THEN NULL
         ELSE (cl.ejecutado_origen_periodif
               - COALESCE(cl.ejecutado_origen_anterior, 0))::NUMERIC(18,2)
    END                                                                AS ejecutado_mes_periodif,

    -- ===================================================================
    -- VARIANTE 2: PERIODIFICACIÓN POR PRODUCCIÓN CON INCURRIDO (Tanda 4.2)
    -- ===================================================================
    cl.ejecutado_origen_periodif_prod_inc                              AS ejecutado_origen_periodif_inc,
    CASE WHEN cl.ejecutado_origen_periodif_prod_inc IS NULL THEN NULL
         ELSE (cl.ejecutado_origen_periodif_prod_inc
               - COALESCE(cl.ejecutado_origen_anterior, 0))::NUMERIC(18,2)
    END                                                                AS ejecutado_mes_periodif_inc,

    -- ===================================================================
    -- VARIANTE 3: PERIODIFICACIÓN LINEAL POR MESES (sin cap, Tanda 4.2)
    -- ===================================================================
    cl.ratio_lineal,
    CASE WHEN cl.ratio_lineal IS NULL THEN NULL
         ELSE ROUND(cl.ratio_lineal * 100.0, 2) END                    AS pct_periodificacion_lineal,
    cl.ejecutado_origen_periodif_lineal,
    CASE WHEN cl.ejecutado_origen_periodif_lineal IS NULL THEN NULL
         ELSE (cl.ejecutado_origen_periodif_lineal
               - COALESCE(cl.ejecutado_origen_anterior, 0))::NUMERIC(18,2)
    END                                                                AS ejecutado_mes_periodif_lineal,

    -- ===================================================================
    -- VARIANTE 4: PERIODIFICACIÓN LINEAL CON INCURRIDO (Tanda 4.2)
    -- ===================================================================
    cl.ejecutado_origen_periodif_lineal_inc,
    CASE WHEN cl.ejecutado_origen_periodif_lineal_inc IS NULL THEN NULL
         ELSE (cl.ejecutado_origen_periodif_lineal_inc
               - COALESCE(cl.ejecutado_origen_anterior, 0))::NUMERIC(18,2)
    END                                                                AS ejecutado_mes_periodif_lineal_inc
FROM con_lag cl
JOIN stg.obras o ON o.obra_id = cl.obra_id
LEFT JOIN sub_nombres sn
       ON sn.obra_id = cl.obra_id AND sn.subcategoria_cod = cl.subcategoria_cod;

COMMENT ON VIEW cierre.v_pbi_cierre_indirectos_detalle IS
'Detalle INDIRECTOS POR OBRA por (obra × mes × grupo × subcategoria). 4 variantes '
'de periodificación (solo grupos cuyo nombre contiene "INFRA"): '
'(1) PROD = fase0 × venta_origen/venta_final; '
'(2) PROD_INC = igual pero solo desde el primer mes con incurrido; '
'(3) LINEAL = fase0 × mes_actual/plazo_total (sin cap al 100%); '
'(4) LINEAL_INC = igual pero solo desde el primer mes con incurrido. '
'Tanda 4.2: el PARCIAL de cada variante se calcula restando contra el '
'ejecutado_origen del mes anterior (incurrido leído de Sigrid; Ruesma ajusta '
'manualmente ese valor al periodif para que el parcial sea el delta del ratio).';


-- =========================================================================
-- VISTA: detalle GENERALES por (obra × mes × tipología) — SIN CAMBIOS
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
            WHEN UPPER(descripcion_corta) LIKE '%LEVANTAM%' THEN 'LEVANTAMIENTO'
            WHEN UPPER(descripcion_corta) LIKE '%SEGURO%' THEN 'SEGUROS'
            WHEN UPPER(descripcion_corta) LIKE '%AVAL%'
              OR UPPER(descripcion_corta) LIKE '%GARANTIA%' THEN 'AVALES'
            WHEN UPPER(descripcion_corta) LIKE '%CONTRATAC%' THEN 'CONTRATACION'
            WHEN UPPER(descripcion_corta) LIKE '%CALIDAD%'
              OR UPPER(descripcion_corta) LIKE '%MEDIO AMB%' THEN 'MEDIO AMBIENTE'
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
    o.codigo_obra, o.nombre_obra,
    cl.anio_mes,
    EXTRACT(YEAR FROM cl.anio_mes)::INT  AS anio,
    EXTRACT(MONTH FROM cl.anio_mes)::INT AS mes,
    -- Nombre del mes SIN locale: no puede depender de lc_time del servidor.
    (ARRAY['Enero','Febrero','Marzo','Abril','Mayo','Junio',
           'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'])
          [EXTRACT(MONTH FROM cl.anio_mes)::INT]
        || ' ' || EXTRACT(YEAR FROM cl.anio_mes)::INT AS nombre_mes,
    cl.tipologia,
    CASE cl.tipologia
        WHEN 'LEVANTAMIENTO'  THEN 1 WHEN 'SEGUROS' THEN 2 WHEN 'AVALES' THEN 3
        WHEN 'CONTRATACION'   THEN 4 WHEN 'MEDIO AMBIENTE' THEN 5
        WHEN 'APORTE GG'      THEN 6 ELSE 9
    END AS orden_tipologia,
    cl.ejecutado_origen,
    COALESCE(cl.ejecutado_anterior_lag, 0)::NUMERIC(18,2) AS ejecutado_anterior,
    (cl.ejecutado_origen - COALESCE(cl.ejecutado_anterior_lag, 0))::NUMERIC(18,2) AS ejecutado_mes
FROM con_lag cl
JOIN stg.obras o ON o.obra_id = cl.obra_id;
