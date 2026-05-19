-- etl_sigrid/infrastructure/postgres/sql/mart/02_build_fact.sql
--
-- Materializa mart.fact_seguimiento_mensual.
--
-- =========================================================================
-- ALGORITMO CORREGIDO (versión vigente independiente de tener dato)
-- =========================================================================
-- IMPORTANTE: la "versión vigente del master" para un mes NO se calcula
-- entre las versiones que tienen fila en plan_mensual para ese mes. Se
-- calcula entre TODAS las versiones del master de esa obra/ámbito, eligiendo
-- la más reciente con fec_creacion <= primer_día_del_mes_siguiente. Luego se
-- busca el dato mensual en plan_mensual: si existe, se usa; si no, importes = 0.
--
-- Esto cubre el caso: una versión creada en feb 2026 cuyo planif acaba en
-- enero (último mes con %>0) DEBE seguir siendo la vigente en feb, aunque
-- ese mes no tenga importe.
--
-- Pasos:
--   1) `versiones_master`: catálogo (obra × ámbito × versión × fec_creacion
--      × descripción) de TODAS las versiones del master para amb 8 y 11.
--   2) `meses_objetivo`: el conjunto de meses para los que tenemos algún
--      dato en plan_mensual (reales o master). Sobre estos meses se proyecta
--      el planificado.
--   3) `version_vigente_por_mes`: por cada (obra, ámbito, mes) escoge la
--      versión cuya fec_creacion es la más reciente ≤ último día del mes.
--   4) `master_proyectado`: LEFT JOIN entre versión vigente y plan_mensual
--      por (obra, partida, ámbito, versión, mes). Si no hay fila → 0.
--      Trae también can_origen / importe_origen / etc. cuando existen.
--   5) Etiqueta `tipo_master` (Inicial / ABC / Cuatrimestral / Otra).
--   6) UNION ALL: 2 escenarios reales (directo) + 2 escenarios planif
--      (a partir de master_proyectado).

TRUNCATE TABLE mart.fact_seguimiento_mensual;

WITH
-- =========================================================================
-- 1) Catálogo de versiones del master por (obra, ámbito)
-- =========================================================================
versiones_master AS (
    SELECT DISTINCT
        obra_id,
        ambito_id,
        version,
        version_fec_creacion,
        version_descripcion,
        version_tex
    FROM stg.plan_mensual
    WHERE ambito_id IN (8, 11)
      AND version_fec_creacion IS NOT NULL
),
-- =========================================================================
-- 1b) Tipo de master derivado del texto libre `tex` (obrfasamb.tex)
--
-- El JO escribe en `tex` el propósito de la versión. Los textos reales
-- observados en Ruesma:
--   "CIERRE INICIAL_ESTUDIO"            → fase v0, descartada (plafec=0)
--   "CIERRE INICIAL_OBRA"               → fase v1, descartada (plafec=0)
--   "PLANIFICACION VALORADA INICIAL"    → Planif Inicial (al arranque)
--   "PLANIFICACION VALORADA OCT-25"     → Cuatrimestral
--   "CIERRE DICIEMBRE-25/ ABC"          → ABC (puede ir combinado con cierre)
--   "CIERRE ENERO-26"                   → Revisión / cierre mensual
--   "PLANIFICACION CUATRIMESTRAL FEB-26"→ Cuatrimestral
--   "CIERRE FEBRERO-26"                 → Revisión
--
-- Reglas de matching sobre `tex` (en orden de prioridad).
-- Los textos observados en Ruesma siguen estos patrones:
--   - "PLANIFICACION VALORADA INICIAL"       → Planif Inicial
--   - "PLANIFICACION VALORADA OCT-25"        → Cuatrimestral (formato JO de Oct/Feb/Jun)
--   - "PLANIFICACION CUATRIMESTRAL FEB-26"   → Cuatrimestral (formato explícito)
--   - "CIERRE DICIEMBRE-25/ ABC"             → ABC (puede combinar con cierre)
--   - "CIERRE ENERO-26"                      → Cierre mensual (revisión)
--   - "" o NULL                              → Sin clasificar
--
-- Prioridad estricta — la primera que matchea gana:
--   1. ABC                  → contiene "ABC"
--   2. Planif Inicial       → contiene "INICIAL" Y contiene "VALORADA"
--   3. Cuatrimestral        → contiene "CUATRIM" O contiene "VALORADA"
--                             (PLANIFICACION VALORADA OCT-25 = cuatrimestral
--                              de octubre; el JO no siempre escribe la palabra
--                              "CUATRIMESTRAL")
--   4. Cierre mensual       → contiene "CIERRE" (sin ABC)
--   5. Sin clasificar       → resto
versiones_tipadas AS (
    SELECT
        obra_id, ambito_id, version, version_fec_creacion,
        version_descripcion, version_tex,
        CASE
            WHEN version_tex IS NULL OR length(trim(version_tex)) = 0
                THEN 'Sin clasificar'
            WHEN UPPER(version_tex) LIKE '%ABC%'
                THEN 'ABC'
            WHEN UPPER(version_tex) LIKE '%INICIAL%'
             AND UPPER(version_tex) LIKE '%VALORADA%'
                THEN 'Planif Inicial'
            WHEN UPPER(version_tex) LIKE '%CUATRIM%'
              OR UPPER(version_tex) LIKE '%VALORADA%'
                THEN 'Cuatrimestral'
            WHEN UPPER(version_tex) LIKE '%CIERRE%'
                THEN 'Cierre mensual'
            ELSE 'Sin clasificar'
        END AS tipo_master
    FROM versiones_master
),
-- =========================================================================
-- 2) Universo de meses con datos por (obra, partida, ámbito).
--    Para que el planificado se proyecte sobre los meses correctos, usamos
--    los meses que aparecen en plan_mensual para esa partida/ámbito.
-- =========================================================================
meses_partida_master AS (
    -- Meses donde el master (cualquier versión) tiene dato → universo
    -- de meses planificados conocidos para esa partida.
    SELECT DISTINCT obra_id, partida_id, ambito_id, anio_mes
    FROM stg.plan_mensual
    WHERE ambito_id IN (8, 11)
),
-- =========================================================================
-- 3) Versión vigente por (obra, ámbito, mes).
--    Solo se considera "vigente" un master de tipo:
--       - Planif Inicial
--       - ABC
--       - Cuatrimestral
--    Los "Cierre mensual" y "Sin clasificar" NO son master vigentes —
--    son revisiones de control que no reemplazan al plan oficial.
--    Si una obra solo tiene cierres mensuales en algún mes, ese mes
--    queda SIN master vigente (importe planificado vacío) — eso indica
--    que la obra está mal configurada en Sigrid.
--
--    Predicado temporal: version_fec_creacion < primer_día_del_mes_siguiente.
--    Equivale a fec <= último día del mes (independiente del día exacto).
-- =========================================================================
version_vigente_por_mes AS (
    SELECT *
    FROM (
        SELECT
            mpm.obra_id, mpm.partida_id, mpm.ambito_id, mpm.anio_mes,
            vt.version, vt.version_descripcion, vt.version_tex,
            vt.version_fec_creacion, vt.tipo_master,
            ROW_NUMBER() OVER (
                PARTITION BY mpm.obra_id, mpm.partida_id, mpm.ambito_id, mpm.anio_mes
                ORDER BY vt.version_fec_creacion DESC, vt.version DESC
            ) AS rn
        FROM meses_partida_master mpm
        JOIN versiones_tipadas vt
            ON vt.obra_id   = mpm.obra_id
           AND vt.ambito_id = mpm.ambito_id
        WHERE vt.version_fec_creacion < (mpm.anio_mes + INTERVAL '1 month')
          AND vt.tipo_master IN ('Planif Inicial', 'ABC', 'Cuatrimestral')
    ) sub
    WHERE rn = 1
),
-- =========================================================================
-- 4) Importes proyectados para la versión vigente de cada mes.
--    LEFT JOIN con plan_mensual: si la versión vigente NO tiene fila en
--    ese mes (porque su planif no llegaba ahí), todos los importes = 0
--    pero la versión sigue siendo la vigente.
-- =========================================================================
master_proyectado AS (
    SELECT
        vvm.obra_id, vvm.partida_id, vvm.ambito_id, vvm.anio_mes,
        vvm.version, vvm.version_descripcion, vvm.version_tex,
        vvm.version_fec_creacion, vvm.tipo_master,
        COALESCE(pm.importe_mes,        0)::NUMERIC(18,2) AS importe_mes,
        COALESCE(pm.importe_origen,     0)::NUMERIC(18,2) AS importe_origen,
        COALESCE(pm.importe_mes_raw,    0)::NUMERIC(18,2) AS importe_mes_raw,
        COALESCE(pm.importe_origen_raw, 0)::NUMERIC(18,2) AS importe_origen_raw,
        pm.can_mes, pm.can_origen, pm.precio_unitario
    FROM version_vigente_por_mes vvm
    LEFT JOIN stg.plan_mensual pm
        ON pm.obra_id    = vvm.obra_id
       AND pm.partida_id = vvm.partida_id
       AND pm.ambito_id  = vvm.ambito_id
       AND pm.version    = vvm.version
       AND pm.anio_mes   = vvm.anio_mes
)

-- =========================================================================
-- INSERT FINAL: 4 escenarios.
-- =========================================================================
INSERT INTO mart.fact_seguimiento_mensual (
    obra_id, codigo_obra, nombre_obra,
    partida_id, codigo_partida, descripcion_partida, unidad_medida,
    categoria, capitulo_raiz_cod, ruta_capitulos,
    anio_mes, anio, mes, nombre_mes,
    escenario, tipo_dato, concepto, ambito_id,
    importe_mes, importe_origen,
    importe_mes_raw, importe_origen_raw,
    can_mes, can_origen, precio_unitario,
    version_master, version_descripcion, version_tex, version_fec_creacion, tipo_master,
    total_incurrido, total_incurrido_mes
)

-- ---- 1) COSTE REAL ----
SELECT
    pm.obra_id, o.codigo_obra, o.nombre_obra,
    pm.partida_id, p.codigo_partida, p.descripcion_corta, p.unidad_medida,
    p.categoria, p.capitulo_raiz_cod, p.ruta_capitulos,
    pm.anio_mes,
    EXTRACT(YEAR  FROM pm.anio_mes)::INT,
    EXTRACT(MONTH FROM pm.anio_mes)::INT,
    pm.version_descripcion,
    'Coste Real'::VARCHAR  AS escenario,
    'REAL'::VARCHAR        AS tipo_dato,
    'COSTE'::VARCHAR       AS concepto,
    pm.ambito_id,
    pm.importe_mes, pm.importe_origen,
    pm.importe_mes_raw, pm.importe_origen_raw,
    pm.can_mes, pm.can_origen, pm.precio_unitario,
    NULL::INT, pm.version_descripcion, NULL::TEXT, NULL::DATE, NULL::VARCHAR,
    pm.total_incurrido, pm.total_incurrido_mes
FROM stg.plan_mensual pm
JOIN stg.obras    o ON o.obra_id    = pm.obra_id
JOIN stg.partidas p ON p.partida_id = pm.partida_id
WHERE pm.ambito_id = 3

UNION ALL

-- ---- 2) VENTA REAL ----
SELECT
    pm.obra_id, o.codigo_obra, o.nombre_obra,
    pm.partida_id, p.codigo_partida, p.descripcion_corta, p.unidad_medida,
    p.categoria, p.capitulo_raiz_cod, p.ruta_capitulos,
    pm.anio_mes,
    EXTRACT(YEAR  FROM pm.anio_mes)::INT,
    EXTRACT(MONTH FROM pm.anio_mes)::INT,
    pm.version_descripcion,
    'Venta Real'::VARCHAR  AS escenario,
    'REAL'::VARCHAR        AS tipo_dato,
    'VENTA'::VARCHAR       AS concepto,
    pm.ambito_id,
    pm.importe_mes, pm.importe_origen,
    pm.importe_mes_raw, pm.importe_origen_raw,
    pm.can_mes, pm.can_origen, pm.precio_unitario,
    NULL::INT, pm.version_descripcion, NULL::TEXT, NULL::DATE, NULL::VARCHAR,
    pm.total_incurrido, pm.total_incurrido_mes
FROM stg.plan_mensual pm
JOIN stg.obras    o ON o.obra_id    = pm.obra_id
JOIN stg.partidas p ON p.partida_id = pm.partida_id
WHERE pm.ambito_id = 7

UNION ALL

-- ---- 3) COSTE PLANIFICADO ----
SELECT
    mp.obra_id, o.codigo_obra, o.nombre_obra,
    mp.partida_id, p.codigo_partida, p.descripcion_corta, p.unidad_medida,
    p.categoria, p.capitulo_raiz_cod, p.ruta_capitulos,
    mp.anio_mes,
    EXTRACT(YEAR  FROM mp.anio_mes)::INT,
    EXTRACT(MONTH FROM mp.anio_mes)::INT,
    to_char(mp.anio_mes, 'TMMonth YYYY')   AS nombre_mes,
    'Coste Planificado'::VARCHAR           AS escenario,
    'PLANIFICADO'::VARCHAR                 AS tipo_dato,
    'COSTE'::VARCHAR                       AS concepto,
    mp.ambito_id,
    mp.importe_mes, mp.importe_origen,
    mp.importe_mes_raw, mp.importe_origen_raw,
    mp.can_mes, mp.can_origen, mp.precio_unitario,
    mp.version, mp.version_descripcion, mp.version_tex, mp.version_fec_creacion,
    mp.tipo_master,
    NULL::NUMERIC(18,2), NULL::NUMERIC(18,2)
FROM master_proyectado mp
JOIN stg.obras    o ON o.obra_id    = mp.obra_id
JOIN stg.partidas p ON p.partida_id = mp.partida_id
WHERE mp.ambito_id = 8

UNION ALL

-- ---- 4) VENTA PLANIFICADA ----
SELECT
    mp.obra_id, o.codigo_obra, o.nombre_obra,
    mp.partida_id, p.codigo_partida, p.descripcion_corta, p.unidad_medida,
    p.categoria, p.capitulo_raiz_cod, p.ruta_capitulos,
    mp.anio_mes,
    EXTRACT(YEAR  FROM mp.anio_mes)::INT,
    EXTRACT(MONTH FROM mp.anio_mes)::INT,
    to_char(mp.anio_mes, 'TMMonth YYYY')   AS nombre_mes,
    'Venta Planificada'::VARCHAR           AS escenario,
    'PLANIFICADO'::VARCHAR                 AS tipo_dato,
    'VENTA'::VARCHAR                       AS concepto,
    mp.ambito_id,
    mp.importe_mes, mp.importe_origen,
    mp.importe_mes_raw, mp.importe_origen_raw,
    mp.can_mes, mp.can_origen, mp.precio_unitario,
    mp.version, mp.version_descripcion, mp.version_tex, mp.version_fec_creacion,
    mp.tipo_master,
    NULL::NUMERIC(18,2), NULL::NUMERIC(18,2)
FROM master_proyectado mp
JOIN stg.obras    o ON o.obra_id    = mp.obra_id
JOIN stg.partidas p ON p.partida_id = mp.partida_id
WHERE mp.ambito_id = 11;
