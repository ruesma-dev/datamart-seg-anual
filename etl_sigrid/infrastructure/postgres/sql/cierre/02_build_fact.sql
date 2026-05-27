-- etl_sigrid/infrastructure/postgres/sql/cierre/02_build_fact.sql
--
-- =========================================================================
-- Carga cierre.fact_cierre_mensual (Tanda 1.7 — impcoe SOLO en venta)
-- =========================================================================
--
-- BUG TANDA 1.4: el FINAL del master se calculaba como
-- SUM(stg.plan_mensual.importe_origen), pero plan_mensual distribuye el
-- master en filas mensuales con importe_origen ACUMULADO por mes. Al sumar
-- TODOS los meses, obtenía un múltiplo (≈9x) del importe real.
--
-- FIX TANDA 1.5: para FINAL leer directamente stg.presupuesto, que tiene
-- UNA fila por (obra × partida × ámbito × versión) con `importe = can × pre`
-- (importe total sin distribución), idéntico a lo que Sigrid muestra en
-- pantalla.
--
-- FIX TANDA 1.6: Sigrid aplica coeficientes en el ámbito VENTA. El campo
-- raw.obrparpre.impcoe es el importe oficial con coeficientes aplicados;
-- stg.presupuesto.importe_oficial = COALESCE(impcoe, can*pre) lo encapsula.
--
-- FIX TANDA 1.7: importe_oficial SOLO se aplica a VENTA (amb 7 y 11), que
-- es el único ámbito con coeficientes. Para COSTE (amb 3 y 8) seguimos
-- usando stg.presupuesto.importe (= ROUND(can*pre, 2)) para mantener
-- consistencia con la planificación valorada del mart.
--
-- Las versiones master CIERRE (texto, fec_creacion) siguen viniendo de
-- stg.plan_mensual (que las clasifica con version_tex y version_fec_creacion),
-- pero los importes los sacamos de stg.presupuesto.
--
-- EJECUTADO sigue desde stg.plan_mensual amb 3/7 fas>=1: ahí cada (partida,
-- versión=fase) tiene UNA fila con importe_origen correcto (no distribuido).
--
-- =========================================================================
-- Mapping concepto → fuentes:
--   VENTA      ← ejec: plan_mensual amb=7  fas>=1
--                final master: pres.importe_oficial amb=11 fase=<v_cierre>
--                fb fase 0:    pres.importe_oficial amb=7  fase=0
--   INDIRECTOS ← ejec: plan_mensual amb=3  fas>=1 cat=CI
--                final master: pres.importe         amb=8  fase=<v_cierre>  cat=CI
--                fb fase 0:    pres.importe         amb=3  fase=0           cat=CI
--   DIRECTOS   ← idem cat=CD
--   GENERALES  ← idem cat=CP
-- =========================================================================

TRUNCATE TABLE cierre.fact_cierre_mensual;

INSERT INTO cierre.fact_cierre_mensual (
    obra_id, codigo_obra, nombre_obra,
    anio_mes, anio, mes, nombre_mes,
    concepto, orden_concepto,
    ejecutado_origen, ejecutado_anterior, ejecutado_mes,
    final_importe, final_anterior, pendiente_importe, variacion_importe,
    final_fuente, final_version_master, final_version_tex,
    fase_id, fase_numero, fase_fecha_inicio, fase_nombre_mes
)
WITH
-- =========================================================================
-- A) Fases con mes canónico (excluye fas=0)
-- =========================================================================
fases_con_mes AS (
    SELECT
        f.fase_id, f.obra_id, f.numero_fase,
        f.fecha_inicio, f.nombre_mes,
        cierre.fn_mes_de_fase(f.fecha_inicio, f.nombre_mes) AS mes_canonico
    FROM stg.fases f
    WHERE f.numero_fase >= 1
),

-- =========================================================================
-- B) EJECUTADO ORIGEN por (obra × mes × concepto)
--    Fuente: stg.plan_mensual amb 3/7. En este ámbito cada fila por
--    (obra, partida, fase) ya tiene importe_origen correcto.
--    (Esta parte NO ha cambiado vs Tanda 1.4 — funcionaba bien.)
-- =========================================================================
ejecutado_concepto AS (
    SELECT
        fm.obra_id, fm.mes_canonico AS mes_cierre, 'VENTA'::VARCHAR AS concepto,
        SUM(pm.importe_origen)::NUMERIC(18,2) AS ejecutado_origen,
        MAX(fm.fase_id)        AS fase_id,
        MAX(fm.numero_fase)    AS fase_numero,
        MAX(fm.fecha_inicio)   AS fase_fecha_inicio,
        MAX(fm.nombre_mes)     AS fase_nombre_mes
    FROM stg.plan_mensual pm
    JOIN fases_con_mes fm
        ON fm.obra_id = pm.obra_id AND fm.numero_fase = pm.version
    WHERE pm.ambito_id = 7
      AND fm.mes_canonico IS NOT NULL
    GROUP BY fm.obra_id, fm.mes_canonico

    UNION ALL
    SELECT
        fm.obra_id, fm.mes_canonico, 'INDIRECTOS'::VARCHAR,
        SUM(pm.importe_origen)::NUMERIC(18,2),
        MAX(fm.fase_id), MAX(fm.numero_fase),
        MAX(fm.fecha_inicio), MAX(fm.nombre_mes)
    FROM stg.plan_mensual pm
    JOIN fases_con_mes fm
        ON fm.obra_id = pm.obra_id AND fm.numero_fase = pm.version
    JOIN stg.partidas p ON p.partida_id = pm.partida_id
    WHERE pm.ambito_id = 3 AND p.categoria = 'CI'
      AND fm.mes_canonico IS NOT NULL
    GROUP BY fm.obra_id, fm.mes_canonico

    UNION ALL
    SELECT
        fm.obra_id, fm.mes_canonico, 'DIRECTOS'::VARCHAR,
        SUM(pm.importe_origen)::NUMERIC(18,2),
        MAX(fm.fase_id), MAX(fm.numero_fase),
        MAX(fm.fecha_inicio), MAX(fm.nombre_mes)
    FROM stg.plan_mensual pm
    JOIN fases_con_mes fm
        ON fm.obra_id = pm.obra_id AND fm.numero_fase = pm.version
    JOIN stg.partidas p ON p.partida_id = pm.partida_id
    WHERE pm.ambito_id = 3 AND p.categoria = 'CD'
      AND fm.mes_canonico IS NOT NULL
    GROUP BY fm.obra_id, fm.mes_canonico

    UNION ALL
    SELECT
        fm.obra_id, fm.mes_canonico, 'GENERALES'::VARCHAR,
        SUM(pm.importe_origen)::NUMERIC(18,2),
        MAX(fm.fase_id), MAX(fm.numero_fase),
        MAX(fm.fecha_inicio), MAX(fm.nombre_mes)
    FROM stg.plan_mensual pm
    JOIN fases_con_mes fm
        ON fm.obra_id = pm.obra_id AND fm.numero_fase = pm.version
    JOIN stg.partidas p ON p.partida_id = pm.partida_id
    WHERE pm.ambito_id = 3 AND p.categoria = 'CP'
      AND fm.mes_canonico IS NOT NULL
    GROUP BY fm.obra_id, fm.mes_canonico
),

-- =========================================================================
-- C) Catálogo de versiones master CIERRE con su mes parseado
--    Lectura desde stg.plan_mensual (que es donde están enriquecidas con
--    version_tex). NO sumamos importes aquí — solo identificamos qué
--    versión cubre qué mes. Una fila por (obra, ambito, version).
-- =========================================================================
versiones_cierre AS (
    SELECT DISTINCT
        obra_id, ambito_id, version,
        version_tex, version_descripcion,
        cierre.fn_mes_de_version_master(version_tex, version_descripcion) AS mes_master
    FROM stg.plan_mensual
    WHERE ambito_id IN (8, 11)
      AND version_tex IS NOT NULL
      AND UPPER(version_tex) LIKE '%CIERRE%'
      AND UPPER(version_tex) NOT LIKE '%ABC%'
      AND UPPER(version_tex) NOT LIKE '%INICIAL%'
      AND UPPER(version_tex) NOT LIKE '%VALORADA%'
      AND UPPER(version_tex) NOT LIKE '%CUATRIM%'
),
master_vigente_por_mes AS (
    SELECT *
    FROM (
        SELECT
            obra_id, ambito_id, mes_master, version, version_tex,
            ROW_NUMBER() OVER (
                PARTITION BY obra_id, ambito_id, mes_master
                ORDER BY version DESC
            ) AS rn
        FROM versiones_cierre
        WHERE mes_master IS NOT NULL
    ) sub
    WHERE rn = 1
),

-- =========================================================================
-- D) FINAL master por (obra × mes × concepto)
--    *** FIX TANDA 1.5: fuente = stg.presupuesto (NO stg.plan_mensual). ***
--    stg.presupuesto tiene UNA fila por (obra, partida, amb, fase_num) con
-- =========================================================================
-- D) FINAL master por (obra × mes × concepto)
--    Fuente = stg.presupuesto (NO stg.plan_mensual). stg.presupuesto tiene
--    UNA fila por (obra, partida, amb, fase_num) con `importe = can × pre`
--    TOTAL, sin distribución mensual.
--
--    Columna de importe usada:
--      - VENTA (amb=11): pres.importe_oficial
--          → COALESCE(impcoe Sigrid, can*pre).
--          → impcoe lleva los coeficientes que aplica Sigrid en venta.
--          → Cuadra exactamente con la pantalla Sigrid master venta.
--      - INDIRECTOS/DIRECTOS/GENERALES (amb=8): pres.importe
--          → = ROUND(can*pre, 2). Coste no lleva coeficientes en Sigrid,
--            así que importe_oficial sería igual a importe en el 99% de
--            registros. Mantenemos importe para consistencia con
--            mart/plan_mensual.
--
--    El campo `fase_num` de stg.presupuesto corresponde a la VERSIÓN del
--    master en amb 8/11 (NO a un mes). Esto es histórico del modelado de
--    raw.obrparpre (donde fas=número de versión para master, =número de
--    fase=mes para amb 3/7).
-- =========================================================================
final_master AS (
    -- VENTA (amb=11), todas las categorías
    SELECT
        mv.obra_id, mv.mes_master AS mes_cierre, 'VENTA'::VARCHAR AS concepto,
        SUM(pres.importe_oficial)::NUMERIC(18,2) AS final_importe,
        mv.version     AS final_version_master,
        mv.version_tex AS final_version_tex
    FROM master_vigente_por_mes mv
    JOIN stg.presupuesto pres
        ON pres.obra_id   = mv.obra_id
       AND pres.ambito_id = mv.ambito_id
       AND pres.fase_num  = mv.version
    WHERE mv.ambito_id = 11
    GROUP BY mv.obra_id, mv.mes_master, mv.version, mv.version_tex

    UNION ALL
    -- INDIRECTOS (amb=8, categoria=CI)
    SELECT
        mv.obra_id, mv.mes_master, 'INDIRECTOS'::VARCHAR,
        SUM(pres.importe)::NUMERIC(18,2),
        mv.version, mv.version_tex
    FROM master_vigente_por_mes mv
    JOIN stg.presupuesto pres
        ON pres.obra_id = mv.obra_id AND pres.ambito_id = mv.ambito_id
       AND pres.fase_num = mv.version
    JOIN stg.partidas p ON p.partida_id = pres.partida_id
    WHERE mv.ambito_id = 8 AND p.categoria = 'CI'
    GROUP BY mv.obra_id, mv.mes_master, mv.version, mv.version_tex

    UNION ALL
    -- DIRECTOS (amb=8, categoria=CD)
    SELECT
        mv.obra_id, mv.mes_master, 'DIRECTOS'::VARCHAR,
        SUM(pres.importe)::NUMERIC(18,2),
        mv.version, mv.version_tex
    FROM master_vigente_por_mes mv
    JOIN stg.presupuesto pres
        ON pres.obra_id = mv.obra_id AND pres.ambito_id = mv.ambito_id
       AND pres.fase_num = mv.version
    JOIN stg.partidas p ON p.partida_id = pres.partida_id
    WHERE mv.ambito_id = 8 AND p.categoria = 'CD'
    GROUP BY mv.obra_id, mv.mes_master, mv.version, mv.version_tex

    UNION ALL
    -- GENERALES (amb=8, categoria=CP)
    SELECT
        mv.obra_id, mv.mes_master, 'GENERALES'::VARCHAR,
        SUM(pres.importe)::NUMERIC(18,2),
        mv.version, mv.version_tex
    FROM master_vigente_por_mes mv
    JOIN stg.presupuesto pres
        ON pres.obra_id = mv.obra_id AND pres.ambito_id = mv.ambito_id
       AND pres.fase_num = mv.version
    JOIN stg.partidas p ON p.partida_id = pres.partida_id
    WHERE mv.ambito_id = 8 AND p.categoria = 'CP'
    GROUP BY mv.obra_id, mv.mes_master, mv.version, mv.version_tex
),

-- =========================================================================
-- E) FALLBACK fase 0 (Previsto) — para mes en curso sin master CIERRE
--    Fuente: stg.presupuesto amb 3/7 fas=0 ("Previsto" vivo).
--    Columna de importe:
--      - VENTA (amb=7): pres.importe_oficial (con coeficientes)
--      - INDIRECTOS/DIRECTOS/GENERALES (amb=3): pres.importe (sin coef.)
-- =========================================================================
final_fase0 AS (
    -- VENTA fase 0 (amb=7)
    SELECT pres.obra_id, 'VENTA'::VARCHAR AS concepto,
           SUM(pres.importe_oficial)::NUMERIC(18,2) AS final_importe
      FROM stg.presupuesto pres
     WHERE pres.ambito_id = 7 AND pres.fase_num = 0
     GROUP BY pres.obra_id
    UNION ALL
    SELECT pres.obra_id, 'INDIRECTOS'::VARCHAR,
           SUM(pres.importe)::NUMERIC(18,2)
      FROM stg.presupuesto pres
      JOIN stg.partidas p ON p.partida_id = pres.partida_id
     WHERE pres.ambito_id = 3 AND pres.fase_num = 0 AND p.categoria = 'CI'
     GROUP BY pres.obra_id
    UNION ALL
    SELECT pres.obra_id, 'DIRECTOS'::VARCHAR,
           SUM(pres.importe)::NUMERIC(18,2)
      FROM stg.presupuesto pres
      JOIN stg.partidas p ON p.partida_id = pres.partida_id
     WHERE pres.ambito_id = 3 AND pres.fase_num = 0 AND p.categoria = 'CD'
     GROUP BY pres.obra_id
    UNION ALL
    SELECT pres.obra_id, 'GENERALES'::VARCHAR,
           SUM(pres.importe)::NUMERIC(18,2)
      FROM stg.presupuesto pres
      JOIN stg.partidas p ON p.partida_id = pres.partida_id
     WHERE pres.ambito_id = 3 AND pres.fase_num = 0 AND p.categoria = 'CP'
     GROUP BY pres.obra_id
),

-- =========================================================================
-- F) Grid (obra × mes × concepto)
-- =========================================================================
conceptos AS (
    SELECT * FROM (VALUES
        ('VENTA',      1),
        ('INDIRECTOS', 2),
        ('DIRECTOS',   3),
        ('GENERALES',  4)
    ) AS t(concepto, orden_concepto)
),
obras_meses AS (
    SELECT DISTINCT obra_id, mes_cierre AS anio_mes
    FROM ejecutado_concepto
),
grid AS (
    SELECT
        o.obra_id, s_obras.codigo_obra, s_obras.nombre_obra,
        o.anio_mes,
        c.concepto, c.orden_concepto
    FROM obras_meses o
    CROSS JOIN conceptos c
    JOIN stg.obras s_obras ON s_obras.obra_id = o.obra_id
),

-- =========================================================================
-- G) Combinación + LAG para ejecutado_anterior, final_anterior
-- =========================================================================
combinado AS (
    SELECT
        g.obra_id, g.codigo_obra, g.nombre_obra,
        g.anio_mes,
        EXTRACT(YEAR  FROM g.anio_mes)::INT AS anio,
        EXTRACT(MONTH FROM g.anio_mes)::INT AS mes,
        to_char(g.anio_mes, 'TMMonth YYYY') AS nombre_mes,
        g.concepto, g.orden_concepto,
        COALESCE(e.ejecutado_origen, 0)::NUMERIC(18,2) AS ejecutado_origen,
        COALESCE(fm.final_importe, ff.final_importe, 0)::NUMERIC(18,2) AS final_importe,
        CASE
            WHEN fm.final_importe IS NOT NULL THEN 'master'
            WHEN ff.final_importe IS NOT NULL THEN 'fase_0'
            ELSE                                    'sin_dato'
        END                                  AS final_fuente,
        fm.final_version_master,
        fm.final_version_tex,
        e.fase_id, e.fase_numero, e.fase_fecha_inicio, e.fase_nombre_mes
    FROM grid g
    LEFT JOIN ejecutado_concepto e
        ON e.obra_id    = g.obra_id
       AND e.mes_cierre = g.anio_mes
       AND e.concepto   = g.concepto
    LEFT JOIN final_master fm
        ON fm.obra_id    = g.obra_id
       AND fm.mes_cierre = g.anio_mes
       AND fm.concepto   = g.concepto
    LEFT JOIN final_fase0 ff
        ON ff.obra_id  = g.obra_id
       AND ff.concepto = g.concepto
),
con_lag AS (
    SELECT
        c.*,
        LAG(c.ejecutado_origen) OVER w AS ejecutado_anterior_lag,
        LAG(c.final_importe)    OVER w AS final_anterior_lag
    FROM combinado c
    WINDOW w AS (PARTITION BY c.obra_id, c.concepto ORDER BY c.anio_mes)
)
SELECT
    obra_id, codigo_obra, nombre_obra,
    anio_mes, anio, mes, nombre_mes,
    concepto, orden_concepto,
    ejecutado_origen,
    COALESCE(ejecutado_anterior_lag, 0)::NUMERIC(18,2) AS ejecutado_anterior,
    (ejecutado_origen - COALESCE(ejecutado_anterior_lag, 0))::NUMERIC(18,2) AS ejecutado_mes,
    final_importe,
    final_anterior_lag                                  AS final_anterior,
    (final_importe - ejecutado_origen)::NUMERIC(18,2)   AS pendiente_importe,
    CASE WHEN final_anterior_lag IS NULL THEN NULL
         ELSE (final_importe - final_anterior_lag)::NUMERIC(18,2) END AS variacion_importe,
    final_fuente, final_version_master, final_version_tex,
    fase_id, fase_numero, fase_fecha_inicio, fase_nombre_mes
FROM con_lag;
