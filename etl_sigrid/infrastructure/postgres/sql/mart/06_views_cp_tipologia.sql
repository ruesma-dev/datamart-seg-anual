-- etl_sigrid/infrastructure/postgres/sql/mart/06_views_cp_tipologia.sql
--
-- Vistas para el detalle anual de Costes Proporcionales (CP) por tipología,
-- consumidas por Power BI en la matriz "Desglose Costes Proporcionales".
--
-- Granularidad final: obra × año × tipología
-- Columnas de valor: cp_real, cp_planificado
--
-- ===========================================================================
-- LÓGICA DE AGREGACIÓN ANUAL
-- ===========================================================================
-- Para cada (obra, año) la vista determina:
--
--   1. Si el año es PASADO (anio < año_actual):
--      - Real: SUM(importe_mes) de enero a diciembre, escenario Coste Real.
--      - Plan: SUM(importe_mes) de enero a diciembre, escenario Coste Planificado,
--              usando la ÚLTIMA versión CUAT/ABC con fec_efectiva ≤ 31/12 del año.
--
--   2. Si el año es EN CURSO (anio = año_actual):
--      - Real: SUM(importe_mes) de enero a mes_actual, escenario Coste Real.
--      - Plan: SUM(importe_mes) de enero a mes_actual, escenario Coste Planificado,
--              usando la ÚLTIMA versión CUAT/ABC disponible (fec_efectiva ≤ hoy).
--
-- ===========================================================================
-- MAPPING DE TIPOLOGÍAS
-- ===========================================================================
-- Los códigos estándar de Ruesma para CP son CP.1..CP.14. El JO mantiene la
-- correspondencia subcapítulo → significado en el 95% de las obras. Hay un
-- residuo de obras antiguas (legacy CP1..CP7 sin punto) que no siguen el
-- estándar: para ellas se aplica un fallback por descripción.
--
--   LEVANTAMIENTO    ← CP.9, CP.9_1
--   SEGUROS          ← CP.1 + CP.2 + CP.3
--   AVALES           ← CP.4
--   CONTRATACION     ← CP.6
--   MEDIO AMBIENTE   ← CP.12
--   APORTE GG        ← todo lo demás (CP.5, CP.7, CP.8, CP.10, CP.11, CP.13,
--                      CP.14, legacy, atípicos)
--
-- Para partidas atípicas se cae al fallback por LIKE sobre descripción.

-- ===========================================================================
-- 1) Vista helper: catálogo de versiones master tipadas.
--    Reusable para otras agregaciones que necesiten "versión vigente" en
--    distintos cortes temporales.
-- ===========================================================================
CREATE OR REPLACE VIEW mart.v_master_versiones_tipadas AS
SELECT DISTINCT
    obra_id,
    ambito_id,
    version,
    version_fec_creacion,
    version_fec_efectiva,
    version_descripcion,
    version_tex,
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
FROM stg.plan_mensual
WHERE ambito_id IN (8, 11)
  AND version_fec_efectiva IS NOT NULL;

COMMENT ON VIEW mart.v_master_versiones_tipadas IS
'Catálogo de versiones master con tipo derivado del tex (Planif Inicial / ABC / Cuatrimestral / Cierre mensual / Sin clasificar). Helper reusable para selección de versión vigente.';


-- ===========================================================================
-- 2) Vista helper: versión vigente al cierre anual.
--    Para cada (obra, año, ámbito) elige la última versión CUAT/ABC con
--    fec_efectiva ≤ corte.
--    - corte = 31/12 si el año es pasado.
--    - corte = hoy si el año es en curso.
-- ===========================================================================
CREATE OR REPLACE VIEW mart.v_master_vigente_anual AS
WITH params AS (
    SELECT EXTRACT(YEAR FROM CURRENT_DATE)::INT AS anio_actual,
           CURRENT_DATE                          AS hoy
),
anios_obra AS (
    -- Universo de (obra, año) con datos en plan_mensual (cualquier ámbito)
    SELECT DISTINCT
        obra_id,
        EXTRACT(YEAR FROM anio_mes)::INT AS anio
    FROM stg.plan_mensual
),
candidatos AS (
    SELECT
        ao.obra_id, ao.anio,
        vt.ambito_id, vt.version, vt.version_fec_efectiva,
        vt.version_descripcion, vt.version_tex, vt.tipo_master,
        ROW_NUMBER() OVER (
            PARTITION BY ao.obra_id, ao.anio, vt.ambito_id
            ORDER BY vt.version_fec_efectiva DESC, vt.version DESC
        ) AS rn
    FROM anios_obra ao
    CROSS JOIN params p
    JOIN mart.v_master_versiones_tipadas vt
        ON vt.obra_id = ao.obra_id
       AND vt.tipo_master IN ('Planif Inicial', 'ABC', 'Cuatrimestral')
       AND vt.version_fec_efectiva <= CASE
                WHEN ao.anio < p.anio_actual THEN make_date(ao.anio, 12, 31)
                ELSE p.hoy
            END
)
SELECT obra_id, anio, ambito_id, version, version_fec_efectiva,
       version_descripcion, version_tex, tipo_master
FROM candidatos
WHERE rn = 1;

COMMENT ON VIEW mart.v_master_vigente_anual IS
'Para cada (obra, año, ámbito) la última versión CUAT/ABC vigente al cierre del año (31/12) si es año pasado, o a hoy si es año en curso. Se usa en agregaciones anuales como v_pbi_cp_tipologia.';


-- ===========================================================================
-- 3) Vista final: detalle anual de CP por tipología.
--    Una fila por (obra, año, tipología) con cp_real y cp_planificado.
-- ===========================================================================
CREATE OR REPLACE VIEW mart.v_pbi_cp_tipologia AS
WITH params AS (
    SELECT EXTRACT(YEAR  FROM CURRENT_DATE)::INT AS anio_actual,
           EXTRACT(MONTH FROM CURRENT_DATE)::INT AS mes_actual
),

-- --------------------------------------------------------------------------
-- 3a) REAL anual.
--     Suma importes mensuales de coste real (ambito_id=3) sobre el rango
--     de meses permitido por el año (1-12 si pasado, 1-mes_actual si curso).
-- --------------------------------------------------------------------------
real_anual AS (
    SELECT
        pm.obra_id,
        EXTRACT(YEAR FROM pm.anio_mes)::INT AS anio,
        pm.partida_id,
        p.codigo_partida,
        p.descripcion_corta,
        p.ruta_capitulos,
        SUM(pm.importe_mes)::NUMERIC(18,2)  AS cp_real
    FROM stg.plan_mensual pm
    JOIN stg.partidas p ON p.partida_id = pm.partida_id
    CROSS JOIN params par
    WHERE pm.ambito_id = 3                  -- Coste Real
      AND p.categoria  = 'CP'
      AND (
            EXTRACT(YEAR FROM pm.anio_mes)::INT < par.anio_actual
            OR (
                EXTRACT(YEAR  FROM pm.anio_mes)::INT = par.anio_actual
                AND EXTRACT(MONTH FROM pm.anio_mes)::INT <= par.mes_actual
            )
          )
    GROUP BY 1, 2, 3, 4, 5, 6
),

-- --------------------------------------------------------------------------
-- 3b) PLAN anual.
--     Suma importes mensuales de coste planificado (ambito_id=8) restringido
--     a la versión vigente anual de mart.v_master_vigente_anual.
--     Mismo filtro temporal que real_anual.
-- --------------------------------------------------------------------------
plan_anual AS (
    SELECT
        pm.obra_id,
        EXTRACT(YEAR FROM pm.anio_mes)::INT AS anio,
        pm.partida_id,
        p.codigo_partida,
        p.descripcion_corta,
        p.ruta_capitulos,
        SUM(pm.importe_mes)::NUMERIC(18,2)  AS cp_planificado
    FROM stg.plan_mensual pm
    JOIN stg.partidas p ON p.partida_id = pm.partida_id
    JOIN mart.v_master_vigente_anual va
        ON va.obra_id   = pm.obra_id
       AND va.ambito_id = 8
       AND va.anio      = EXTRACT(YEAR FROM pm.anio_mes)::INT
       AND va.version   = pm.version
    CROSS JOIN params par
    WHERE pm.ambito_id = 8                  -- Coste Planificado
      AND p.categoria  = 'CP'
      AND (
            EXTRACT(YEAR FROM pm.anio_mes)::INT < par.anio_actual
            OR (
                EXTRACT(YEAR  FROM pm.anio_mes)::INT = par.anio_actual
                AND EXTRACT(MONTH FROM pm.anio_mes)::INT <= par.mes_actual
            )
          )
    GROUP BY 1, 2, 3, 4, 5, 6
),

-- --------------------------------------------------------------------------
-- 3c) Outer join entre real y plan para preservar partidas con solo uno
--     de los dos lados.
-- --------------------------------------------------------------------------
detalle_partida AS (
    SELECT
        COALESCE(r.obra_id, p.obra_id)                     AS obra_id,
        COALESCE(r.anio, p.anio)                           AS anio,
        COALESCE(r.partida_id, p.partida_id)               AS partida_id,
        COALESCE(r.codigo_partida, p.codigo_partida)       AS codigo_partida,
        COALESCE(r.descripcion_corta, p.descripcion_corta) AS descripcion_corta,
        COALESCE(r.ruta_capitulos, p.ruta_capitulos)       AS ruta_capitulos,
        COALESCE(r.cp_real,        0)::NUMERIC(18,2)       AS cp_real,
        COALESCE(p.cp_planificado, 0)::NUMERIC(18,2)       AS cp_planificado
    FROM      real_anual r
    FULL JOIN plan_anual p
        ON r.obra_id     = p.obra_id
       AND r.anio        = p.anio
       AND r.partida_id  = p.partida_id
),

-- --------------------------------------------------------------------------
-- 3d) Mapping a tipología.
--
-- Lógica en cascada:
--   1) Si el subcapítulo es DEFINITORIO (CP.1..CP.4, CP.6, CP.9, CP.12),
--      la tipología queda fijada por el subcapítulo.
--   2) Si el subcapítulo NO es definitorio (CP.5, CP.7, CP.8, CP.10,
--      CP.11, CP.13, CP.14, atípicos o legacy sin punto), se aplica un
--      fallback por descripción. Esto permite reclasificar partidas
--      donde el JO mete "SEGURO R.C." en CP.5 (Financieros) o "CONTROL
--      CALIDAD" en CP.10 (Otros).
--   3) Lo que no cuadre en ninguna regla → APORTE GG.
--
-- Por diseño, los subcapítulos definitorios mandan: una partida bajo
-- CP.4 con descripción "CONTROL CALIDAD" se clasifica como AVALES (no
-- como MEDIO AMBIENTE). El JO declaró que es AVAL aunque la descripción
-- diga otra cosa.
-- --------------------------------------------------------------------------
con_tipologia AS (
    SELECT
        obra_id, anio,
        cp_real, cp_planificado,
        CASE
            -- 1) Subcapítulos DEFINITORIOS — manda el subcap
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

            -- 2) Subcapítulo NO definitorio — fallback por descripción
            --    (cubre CP.5, CP.7, CP.8, CP.10, CP.11, CP.13, CP.14,
            --     CP.ESCALERAS, CP.VALLADO y obras legacy sin punto)
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

            -- 3) Resto → APORTE GG
            ELSE 'APORTE GG'
        END AS tipologia
    FROM detalle_partida
)

SELECT
    obra_id,
    anio,
    tipologia,
    -- Orden estable de las tipologías en la matriz de Power BI.
    CASE tipologia
        WHEN 'LEVANTAMIENTO'  THEN 1
        WHEN 'SEGUROS'        THEN 2
        WHEN 'AVALES'         THEN 3
        WHEN 'CONTRATACION'   THEN 4
        WHEN 'MEDIO AMBIENTE' THEN 5
        WHEN 'APORTE GG'      THEN 6
        ELSE 9
    END                                  AS orden_tipologia,
    SUM(cp_real)::NUMERIC(18,2)          AS cp_real,
    SUM(cp_planificado)::NUMERIC(18,2)   AS cp_planificado,
    (SUM(cp_real) - SUM(cp_planificado))::NUMERIC(18,2) AS cp_desviacion
FROM con_tipologia
GROUP BY obra_id, anio, tipologia
HAVING SUM(cp_real) <> 0 OR SUM(cp_planificado) <> 0;

COMMENT ON VIEW mart.v_pbi_cp_tipologia IS
'Detalle anual de Costes Proporcionales por tipología agregada. Granularidad: obra × año × tipología. Real: meses 1-12 (año pasado) o 1-mes_actual (año curso). Plan: misma ventana, usando la última versión CUAT/ABC vigente al cierre.';
