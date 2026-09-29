-- etl_sigrid/infrastructure/postgres/sql/mart/06_cp_tipologia.sql
--
-- Detalle anual de Costes Proporcionales (CP) por tipología, consumido por
-- Power BI en la matriz "Desglose Costes Proporcionales" y por el MCP.
--
-- Granularidad final: obra × año × tipología
-- Columnas de valor: cp_real, cp_planificado, cp_desviacion
--
-- ===========================================================================
-- POR QUÉ ESTO SON TABLAS Y NO VISTAS (F-078)
-- ===========================================================================
-- Hasta el 2026-09-15 los tres objetos eran VISTAS, y `mart.v_pbi_cp_tipologia`
-- era **la única `v_pbi_` sin tabla materializada detrás**: se recalculaba
-- entera en cada consulta. Medido el 2026-09-09 con EXPLAIN contra el Postgres
-- de Azure: **coste estimado 6,6 millones de unidades**, CINCO `Parallel Seq
-- Scan` sobre `stg.plan_mensual` —29,8 M de filas y 11 GB— y un `WindowAgg`
-- sobre **11,8 M de filas intermedias** para resolver la versión master
-- vigente. Power BI se colgaba en el paso de Navegación (que es cuando Power
-- Query lanza el SELECT) y el MCP moría con cualquier pregunta que la tocase.
--
-- Añadir índices se descartó: los scans van por `ambito_id`, que no discrimina
-- (el ámbito 8 son ~5,9 M filas de 29,8 M), ningún índice evita la ventana ni
-- el cruce con la versión vigente, y encima `stg.plan_mensual` se reconstruye
-- entera cada noche.
--
-- LA CLAVE DEL ARREGLO ESTÁ EN `mart.master_vigente_anual`: se calcula contra
-- la TABLA `mart.master_versiones_tipadas`, no contra la vista. Es lo que mata
-- el `WindowAgg`, porque deja de re-escanear `stg.plan_mensual` por debajo.
--
-- **Aquí solo cambia DÓNDE se calcula, no QUÉ se calcula.** La lógica de
-- negocio de más abajo viajó verbatim desde las vistas, y `tests/test_f078_sql.py`
-- la fija cadena a cadena para que un refactor no se la lleve por delante.
--
-- LAS TRES VISTAS SE QUEDAN, con el mismo nombre y las mismas columnas, ahora
-- como envoltorio de su tabla: así el `.pbix` del humano no cambia ni una
-- línea, y tampoco el MCP ni `main.py inspect-cp-tipologia`.
--
-- LO ÚNICO QUE CAMBIA DE SEMÁNTICA, y hay que decirlo: `CURRENT_DATE` deja de
-- evaluarse en cada consulta y se congela en el momento del build. El "año en
-- curso" y el "mes actual" son los de la noche que construyó la tabla, no los
-- de quien pregunta. Con refresco nocturno la diferencia solo se nota el 1 de
-- enero y el día 1 de cada mes, antes de que corra la carga.
--
-- ===========================================================================
-- LÓGICA DE AGREGACIÓN ANUAL
-- ===========================================================================
-- Para cada (obra, año) se determina un CORTE temporal común a Plan y Real, y
-- se suman ambos sobre la MISMA ventana [enero .. mes_corte]:
--
--   * Año PASADO (anio < año_actual):
--       mes_corte = 12 (periodo cerrado completo).
--   * Año EN CURSO (anio = año_actual):
--       mes_corte = último mes con cierre real (ambito_id=3) de esa obra.
--       Si la obra aún no tiene ningún cierre este año, se cae a mes_actual
--       para no dejar el Plan vacío.
--
-- Por qué el corte = último mes con real (y no mes_actual):
--   los cierres llegan con retraso (abril se cierra en mayo, etc.). Si el
--   Plan se cortara en el mes de calendario, incluiría meses futuros aún sin
--   cierre y siempre saldría "por delante" del Real, haciendo la comparación
--   Real-vs-Planif engañosa. Cortando ambos en el último mes con cierre real
--   se comparan periodos homogéneos y cerrados.
--
--   - Plan: SUM(importe_mes) sobre la ventana, escenario Coste Planificado,
--           usando la ÚLTIMA versión CUAT/ABC vigente (master_vigente_anual).
--   - Real: SUM(importe_mes) sobre la ventana, escenario Coste Real.
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
-- 0) Limpieza, EN ORDEN DE DEPENDENCIA INVERSO.
--
--    Las vistas van primero porque hoy existen colgando de `stg.plan_mensual`
--    y hay que sustituirlas por el envoltorio de su tabla. Si no se dropearan
--    aquí, el `DROP TABLE ... CASCADE` de la noche siguiente se las llevaría
--    por delante y nadie las recrearía: es exactamente la avería que
--    `03_agg_categoria.sql` le hizo a `cierre.v_pbi_planif_vs_real`.
--
--    Todo el fichero se ejecuta en UNA transacción (`execute_sql_file` manda
--    el texto entero en una sola llamada), así que o se rehace entero o no se
--    toca nada: no hay ventana en la que Power BI encuentre la vista ausente.
-- ===========================================================================
DROP VIEW  IF EXISTS mart.v_pbi_cp_tipologia         CASCADE;
DROP VIEW  IF EXISTS mart.v_master_vigente_anual     CASCADE;
DROP VIEW  IF EXISTS mart.v_master_versiones_tipadas CASCADE;

DROP TABLE IF EXISTS mart.fact_cp_tipologia          CASCADE;
DROP TABLE IF EXISTS mart.master_vigente_anual       CASCADE;
DROP TABLE IF EXISTS mart.master_versiones_tipadas   CASCADE;


-- ===========================================================================
-- 1) Tabla helper: catálogo de versiones master tipadas.
--    Reusable para otras agregaciones que necesiten "versión vigente" en
--    distintos cortes temporales.
--
--    Es el ÚNICO objeto de este fichero que baja a `stg.plan_mensual` a por
--    las versiones: los otros dos se apoyan en él.
-- ===========================================================================
CREATE TABLE mart.master_versiones_tipadas AS
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

COMMENT ON TABLE mart.master_versiones_tipadas IS
'Catálogo de versiones master con tipo derivado del tex (Planif Inicial / ABC / Cuatrimestral / Cierre mensual / Sin clasificar). Helper reusable para selección de versión vigente. Materializada en F-078.';


-- ===========================================================================
-- 2) Tabla helper: versión vigente al cierre anual.
--    Para cada (obra, año, ámbito) elige la última versión CUAT/ABC con
--    fec_efectiva ≤ corte.
--    - corte = 31/12 si el año es pasado.
--    - corte = hoy (el del BUILD) si el año es en curso.
--
--    AQUÍ ESTÁ EL AHORRO: el `ROW_NUMBER()` corre contra
--    `mart.master_versiones_tipadas`, que son unos pocos miles de filas, y no
--    contra una vista que vuelve a barrer los 29,8 M de `stg.plan_mensual`.
--    El `WindowAgg` baja de 11,8 M de filas intermedias a las que salgan del
--    cruce entre el universo (obra, año) y ese catálogo.
-- ===========================================================================
CREATE TABLE mart.master_vigente_anual AS
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
    JOIN mart.master_versiones_tipadas vt
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

COMMENT ON TABLE mart.master_vigente_anual IS
'Para cada (obra, año, ámbito) la última versión CUAT/ABC vigente al cierre del año (31/12) si es año pasado, o a la fecha del build si es año en curso. Se usa en agregaciones anuales como fact_cp_tipologia. Materializada en F-078.';


-- ===========================================================================
-- 3) Tabla de hecho: detalle anual de CP por tipología.
--    Una fila por (obra, año, tipología) con cp_real, cp_planificado y su
--    desviación. Decenas de miles de filas, frente a los 29,8 M que había que
--    recorrer cinco veces para obtenerlas.
-- ===========================================================================
CREATE TABLE mart.fact_cp_tipologia AS
WITH params AS (
    SELECT EXTRACT(YEAR  FROM CURRENT_DATE)::INT AS anio_actual,
           EXTRACT(MONTH FROM CURRENT_DATE)::INT AS mes_actual
),

-- --------------------------------------------------------------------------
-- 3a) Último mes con coste real cargado (ambito_id=3) por (obra, año).
--     Define el extremo superior de la ventana cerrada para el año en curso.
-- --------------------------------------------------------------------------
ultimo_real AS (
    SELECT
        obra_id,
        EXTRACT(YEAR  FROM anio_mes)::INT      AS anio,
        MAX(EXTRACT(MONTH FROM anio_mes)::INT) AS mes
    FROM stg.plan_mensual
    WHERE ambito_id = 3
    GROUP BY 1, 2
),

-- --------------------------------------------------------------------------
-- 3b) Corte temporal COMÚN a Plan y Real, por (obra, año).
--     Construido sobre el universo (obra, año) de plan_mensual para cubrir
--     también obras con Plan pero sin Real todavía.
--       * año pasado   → 12
--       * año en curso → último mes con cierre real; fallback a mes_actual
--                        si la obra aún no tiene ningún cierre este año.
--       * año futuro   → 0 (no se muestra)
-- --------------------------------------------------------------------------
corte AS (
    SELECT
        ao.obra_id,
        ao.anio,
        CASE
            WHEN ao.anio <  par.anio_actual THEN 12
            WHEN ao.anio =  par.anio_actual THEN COALESCE(ur.mes, par.mes_actual)
            ELSE 0
        END AS mes_corte
    FROM (
        SELECT DISTINCT obra_id, EXTRACT(YEAR FROM anio_mes)::INT AS anio
        FROM stg.plan_mensual
    ) ao
    CROSS JOIN params par
    LEFT JOIN ultimo_real ur
        ON ur.obra_id = ao.obra_id
       AND ur.anio    = ao.anio
),

-- --------------------------------------------------------------------------
-- 3c) REAL anual.
--     Suma importes mensuales de coste real (ambito_id=3) sobre la ventana
--     [enero .. mes_corte] de cada (obra, año).
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
    JOIN corte c
        ON c.obra_id = pm.obra_id
       AND c.anio    = EXTRACT(YEAR FROM pm.anio_mes)::INT
    WHERE pm.ambito_id = 3
      AND p.categoria  = 'CP'
      AND EXTRACT(MONTH FROM pm.anio_mes)::INT <= c.mes_corte
    GROUP BY 1, 2, 3, 4, 5, 6
),

-- --------------------------------------------------------------------------
-- 3d) PLAN anual.
--     Suma importes mensuales de coste planificado (ambito_id=8) restringido
--     a la versión vigente anual de mart.master_vigente_anual.
--     MISMA ventana [enero .. mes_corte] que real_anual.
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
    JOIN mart.master_vigente_anual va
        ON va.obra_id   = pm.obra_id
       AND va.ambito_id = 8
       AND va.anio      = EXTRACT(YEAR FROM pm.anio_mes)::INT
       AND va.version   = pm.version
    JOIN corte c
        ON c.obra_id = pm.obra_id
       AND c.anio    = EXTRACT(YEAR FROM pm.anio_mes)::INT
    WHERE pm.ambito_id = 8
      AND p.categoria  = 'CP'
      AND EXTRACT(MONTH FROM pm.anio_mes)::INT <= c.mes_corte
    GROUP BY 1, 2, 3, 4, 5, 6
),

-- --------------------------------------------------------------------------
-- 3e) Outer join entre real y plan para preservar partidas con solo uno
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
-- 3f) Mapping a tipología.
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

COMMENT ON TABLE mart.fact_cp_tipologia IS
'Detalle anual de Costes Proporcionales por tipología agregada. Granularidad: obra × año × tipología. Plan y Real se suman sobre la MISMA ventana [enero .. mes_corte]: 12 para años pasados, último mes con cierre real (ambito_id=3) para el año en curso (fallback mes_actual si no hay cierre aún). Materializada en F-078: antes era la vista v_pbi_cp_tipologia y costaba 6,6 M de unidades por consulta.';


-- ===========================================================================
-- 4) Las tres vistas, con EL MISMO NOMBRE Y LAS MISMAS COLUMNAS de siempre.
--
--    Existen para que nada de lo que ya consume estos datos tenga que
--    cambiar: el `.pbix` del humano (Origen + Navegación a
--    `mart.v_pbi_cp_tipologia`), el MCP y `main.py inspect-cp-tipologia`.
--    Son un `SELECT` de columnas desnudas sobre su tabla: no queda ni un
--    cálculo en tiempo de consulta.
-- ===========================================================================
CREATE OR REPLACE VIEW mart.v_master_versiones_tipadas AS
SELECT
    obra_id,
    ambito_id,
    version,
    version_fec_creacion,
    version_fec_efectiva,
    version_descripcion,
    version_tex,
    tipo_master
FROM mart.master_versiones_tipadas;

COMMENT ON VIEW mart.v_master_versiones_tipadas IS
'Catálogo de versiones master con tipo derivado del tex (Planif Inicial / ABC / Cuatrimestral / Cierre mensual / Sin clasificar). Desde F-078 es el envoltorio de mart.master_versiones_tipadas.';


CREATE OR REPLACE VIEW mart.v_master_vigente_anual AS
SELECT
    obra_id,
    anio,
    ambito_id,
    version,
    version_fec_efectiva,
    version_descripcion,
    version_tex,
    tipo_master
FROM mart.master_vigente_anual;

COMMENT ON VIEW mart.v_master_vigente_anual IS
'Para cada (obra, año, ámbito) la última versión CUAT/ABC vigente al cierre del año. Desde F-078 es el envoltorio de mart.master_vigente_anual y ya se puede consultar sin filtrar por obra.';


CREATE OR REPLACE VIEW mart.v_pbi_cp_tipologia AS
SELECT
    obra_id,
    anio,
    tipologia,
    orden_tipologia,
    cp_real,
    cp_planificado,
    cp_desviacion
FROM mart.fact_cp_tipologia;

COMMENT ON VIEW mart.v_pbi_cp_tipologia IS
'Detalle anual de Costes Proporcionales por tipología agregada. Granularidad: obra × año × tipología. Desde F-078 es el envoltorio de mart.fact_cp_tipologia: el mismo nombre y las mismas columnas de siempre, para que el informe de Power BI no cambie, pero ya sin cálculo en tiempo de consulta.';
