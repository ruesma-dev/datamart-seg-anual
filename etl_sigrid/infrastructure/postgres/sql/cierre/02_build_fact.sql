-- etl_sigrid/infrastructure/postgres/sql/cierre/02_build_fact.sql
--
-- =========================================================================
-- Carga cierre.fact_cierre_mensual (F-118: la venta final SIN coeficientes)
-- =========================================================================
--
-- F-118 (correo de Juan Romero del 2026-09-29, decisión del humano D6): el
-- FINAL de la venta se suma con `stg.presupuesto.importe`, SIN coeficientes,
-- como el ejecutado y como el coste. Hasta F-118 sumaba `importe_oficial` (el
-- `impcoe` de Sigrid, con los coeficientes del contrato con el cliente: 1,19 en
-- casi todas, 1,2574 en la 0702) y restaba contra él un ejecutado que no los
-- lleva: el cierre de agosto de 2026 daba a la 0702 un beneficio final de
-- +1.695.571,87 € donde la hoja de cierre de Juan prevé −790.718,46 €.
-- De `final_importe` salen, sin tocar nada más, el pendiente, la variación, los
-- % y el beneficio (R39). La venta CON coeficientes, que es lo que se factura,
-- se publica ADEMÁS en `final_importe_con_coeficientes` (R41): suma de
-- `importe_oficial` del mismo master, solo en VENTA con fuente master; NULL en
-- el coste y con respaldo de fase 0, porque la venta real no guarda
-- coeficientes (D10). No entra en ningún cálculo (R43). El coeficiente es del
-- contrato y no se reconstruye: el desglose por contrato es F-099 (R44).
--
-- Historia de la fuente del FINAL:
--   Tanda 1.4: sumaba stg.plan_mensual.importe_origen de TODOS los meses del
--     master (acumulado por mes): un múltiplo (≈9x) del importe real.
--   Tanda 1.5: lee stg.presupuesto, UNA fila por (obra × partida × ámbito ×
--     versión) con `importe = can × pre`.
--   Tanda 1.6-1.7: la venta pasó a `importe_oficial` (con coeficientes) para
--     cuadrar con la pantalla de Sigrid; F-118 lo deshace (arriba).
--
-- Las versiones master CIERRE (texto, fec_creacion) siguen viniendo de
-- stg.plan_mensual (que las clasifica con version_tex y version_fec_creacion),
-- pero los importes los sacamos de stg.presupuesto.
--
-- EJECUTADO desde stg.plan_mensual amb 3/7 fas>=1, en el mes de `stg` (F-118).
--
-- =========================================================================
-- Mapping concepto → fuentes:
--   VENTA      ← ejec: plan_mensual amb=7  fas>=1
--                final master: pres.importe         amb=11 fase=<v_cierre>
--                  (con coeficientes, aparte: pres.importe_oficial)
--                fb fase 0:    pres.importe         amb=7  fase=0
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
    final_importe_con_coeficientes,
    final_fuente, final_version_master, final_version_tex,
    fase_id, fase_numero, fase_fecha_inicio, fase_nombre_mes,
    es_relleno
)
WITH
-- =========================================================================
-- A) EJECUTADO ORIGEN por (obra × mes × concepto)
--    Fuente: stg.plan_mensual amb 3/7, donde cada (partida, mes) tiene su
--    acumulado a origen.
--
--    F-118 (F-051 absorbida): el mes es `pm.anio_mes`, el que decide `stg`
--    con el TEXTO de la fase y su relleno. `cierre` ya no lo recalcula con
--    `fn_mes_de_fase`: las tres capas publican el mismo mes por construcción
--    (R16). Un mes de relleno suma el acumulado arrastrado (`es_relleno`); una
--    fila de deshacer suma 0, que es justo lo que la partida vale ese mes.
-- =========================================================================
ejecutado_base AS (
    SELECT
        pm.obra_id, pm.anio_mes AS mes_cierre, 'VENTA'::VARCHAR AS concepto,
        SUM(pm.importe_origen)::NUMERIC(18,2) AS ejecutado_origen,
        MAX(pm.version)                       AS fase_numero,
        bool_and(pm.es_relleno)               AS es_relleno
    FROM stg.plan_mensual pm
    WHERE pm.ambito_id = 7
      AND pm.version >= 1
    GROUP BY pm.obra_id, pm.anio_mes

    UNION ALL
    SELECT
        pm.obra_id, pm.anio_mes, 'INDIRECTOS'::VARCHAR,
        SUM(pm.importe_origen)::NUMERIC(18,2),
        MAX(pm.version), bool_and(pm.es_relleno)
    FROM stg.plan_mensual pm
    JOIN stg.partidas p ON p.partida_id = pm.partida_id
    WHERE pm.ambito_id = 3 AND p.categoria = 'CI'
      AND pm.version >= 1
    GROUP BY pm.obra_id, pm.anio_mes

    UNION ALL
    SELECT
        pm.obra_id, pm.anio_mes, 'DIRECTOS'::VARCHAR,
        SUM(pm.importe_origen)::NUMERIC(18,2),
        MAX(pm.version), bool_and(pm.es_relleno)
    FROM stg.plan_mensual pm
    JOIN stg.partidas p ON p.partida_id = pm.partida_id
    WHERE pm.ambito_id = 3 AND p.categoria = 'CD'
      AND pm.version >= 1
    GROUP BY pm.obra_id, pm.anio_mes

    UNION ALL
    SELECT
        pm.obra_id, pm.anio_mes, 'GENERALES'::VARCHAR,
        SUM(pm.importe_origen)::NUMERIC(18,2),
        MAX(pm.version), bool_and(pm.es_relleno)
    FROM stg.plan_mensual pm
    JOIN stg.partidas p ON p.partida_id = pm.partida_id
    WHERE pm.ambito_id = 3 AND p.categoria = 'CP'
      AND pm.version >= 1
    GROUP BY pm.obra_id, pm.anio_mes
),

-- =========================================================================
-- B) La fase del mes, para la trazabilidad: la vigente de ese cierre o, en un
--    mes de relleno, la que lo genera (es la `version` de sus filas).
-- =========================================================================
ejecutado_concepto AS (
    SELECT
        e.obra_id, e.mes_cierre, e.concepto, e.ejecutado_origen, e.es_relleno,
        f.fase_id,
        e.fase_numero,
        f.fecha_inicio AS fase_fecha_inicio,
        f.nombre_mes   AS fase_nombre_mes
    FROM ejecutado_base e
    LEFT JOIN stg.fases f
        ON f.obra_id     = e.obra_id
       AND f.numero_fase = e.fase_numero
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
--    Columna de importe usada (F-118, D6): `pres.importe` en los cuatro
--    conceptos, SIN coeficientes, como el ejecutado. En VENTA se suma además
--    `pres.importe_oficial` (COALESCE(impcoe, can*pre): con los coeficientes
--    del contrato, lo que muestra la pantalla master de venta de Sigrid) en
--    `final_importe_con_coeficientes`, que no entra en ningún cálculo. El
--    coste no tiene coeficientes: NULL.
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
        SUM(pres.importe)::NUMERIC(18,2) AS final_importe,
        SUM(pres.importe_oficial)::NUMERIC(18,2) AS final_importe_con_coeficientes,
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
        NULL::NUMERIC(18,2),
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
        NULL::NUMERIC(18,2),
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
        NULL::NUMERIC(18,2),
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
--    Columna de importe: pres.importe, SIN coeficientes, en los cuatro
--    conceptos (F-118). Sin venta con coeficientes: la venta real no los
--    guarda, y copiar la sin coeficientes diría que son iguales (D10).
-- =========================================================================
final_fase0 AS (
    -- VENTA fase 0 (amb=7)
    SELECT pres.obra_id, 'VENTA'::VARCHAR AS concepto,
           SUM(pres.importe)::NUMERIC(18,2) AS final_importe
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
        -- Nombre del mes SIN locale: el dato no puede depender de lc_time del
        -- servidor (Azure va en en_US.utf8 y daría "May 2026" en vez de "Mayo 2026").
        (ARRAY['Enero','Febrero','Marzo','Abril','Mayo','Junio',
               'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'])
              [EXTRACT(MONTH FROM g.anio_mes)::INT]
            || ' ' || EXTRACT(YEAR FROM g.anio_mes)::INT AS nombre_mes,
        g.concepto, g.orden_concepto,
        -- NULL si el concepto no tiene filas ese mes: lo resuelve `arrastrado`.
        e.ejecutado_origen                   AS ejecutado_propio,
        e.es_relleno,
        COALESCE(fm.final_importe, ff.final_importe, 0)::NUMERIC(18,2) AS final_importe,
        CASE
            WHEN fm.final_importe IS NOT NULL THEN 'master'
            WHEN ff.final_importe IS NOT NULL THEN 'fase_0'
            ELSE                                    'sin_dato'
        END                                  AS final_fuente,
        fm.final_version_master,
        fm.final_version_tex,
        -- Solo con fuente master (D10): sin fila en final_master, NULL.
        fm.final_importe_con_coeficientes,
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
-- R38 (D5 de F-118): un concepto sin filas en un mes que sí tiene cierre de
-- otro concepto (la obra cerró coste y no abrió la fase de venta, o su venta
-- terminó antes) conserva el ejecutado a origen del último mes con filas. Antes
-- caía a 0 y rebotaba al mes siguiente: 22 obras de venta publicaban un mes con
-- la venta a origen a cero. Sin mes anterior con filas, 0.
con_grupo AS (
    SELECT
        c.*,
        COUNT(ejecutado_propio) OVER (
            PARTITION BY obra_id, concepto ORDER BY anio_mes
            ROWS UNBOUNDED PRECEDING
        ) AS grupo_ejecutado
    FROM combinado c
),
arrastrado AS (
    SELECT
        c.*,
        COALESCE(MAX(ejecutado_propio) OVER (
            PARTITION BY obra_id, concepto, grupo_ejecutado
        ), 0)::NUMERIC(18,2) AS ejecutado_origen
    FROM con_grupo c
),
con_lag AS (
    SELECT
        c.*,
        LAG(c.ejecutado_origen) OVER w AS ejecutado_anterior_lag,
        LAG(c.final_importe)    OVER w AS final_anterior_lag
    FROM arrastrado c
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
    final_importe_con_coeficientes,
    final_fuente, final_version_master, final_version_tex,
    fase_id, fase_numero, fase_fecha_inicio, fase_nombre_mes,
    es_relleno
FROM con_lag;
