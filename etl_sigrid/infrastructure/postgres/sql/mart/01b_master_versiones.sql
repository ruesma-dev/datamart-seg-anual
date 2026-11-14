-- etl_sigrid/infrastructure/postgres/sql/mart/01b_master_versiones.sql
--
-- El catálogo de versiones master y lo que cuelga de él sin tocar la parte
-- temporal (F-161). Lee de stg.master_versiones, stg.v_master_lineas,
-- stg.partidas y stg.obras. Construye:
--
--   1) mart.master_versiones_tipadas (tabla) y su vista
--      mart.v_master_versiones_tipadas: el ÚNICO catálogo, con el tipo.
--   2) mart.v_master_version_partida (vista): el coste/venta de cada versión
--      por partida, tenga reparto o no.
--   3) mart.master_importe_mensual (tabla): por obra, ámbito y mes, la versión
--      del ÚLTIMO CIERRE (el planificado de IMPORTE) al lado de la TEMPORAL y
--      su diferencia, sin reescalar.
--
-- ===========================================================================
-- EL ÚNICO CATÁLOGO (D11)
-- ===========================================================================
-- Hasta F-161 había DOS: `06_cp_tipologia.sql` (sección 1) y las CTE
-- `versiones_master`/`versiones_tipadas` de `02_build_fact.sql`, las dos un
-- `SELECT DISTINCT` sobre `stg.plan_mensual` con la misma cascada del tipo
-- copiada. Ahora la cascada vive SOLO aquí, y lo leen:
--   - 02_build_fact.sql            (la versión vigente de cada mes)
--   - 06_cp_tipologia.sql          (mart.master_vigente_anual)
--   - retenciones/05_fin_obra.sql  (la última Cuatrimestral)
--   - tesoreria/07_devengo_pendiente.sql (el tipo y la fecha de una versión
--                                   que sale del hecho)
-- Por eso va ANTES de 02_build_fact.sql en build_mart (sub-paso
-- `master_versiones`, entre `ddl` y `build_fact`).
--
-- EL GRANO CAMBIA, LA PARTE TEMPORAL NO (D4). El catálogo tiene TODAS las
-- versiones con líneas (y las de reparto, aunque no tengan líneas), no solo las
-- que dejan filas en stg.plan_mensual. Solo las de `tiene_reparto` rigen el
-- mensual: los tres consumidores temporales filtran esa columna, y con ella ven
-- exactamente las filas de antes (R11, `master_versiones_sql.py`).
--
-- EL TIPO, deducido del texto libre `tex` (obrfasamb.tex) que escribe el jefe
-- de obra. Textos reales observados en Ruesma:
--   "CIERRE INICIAL_ESTUDIO"            → fase v0 (Cierre mensual)
--   "CIERRE INICIAL_OBRA"               → fase v1 (Cierre mensual)
--   "PLANIFICACION VALORADA INICIAL"    → Planif Inicial (al arranque)
--   "PLANIFICACION VALORADA OCT-25"     → Cuatrimestral (formato JO de Oct/Feb/Jun)
--   "PLANIFICACION CUATRIMESTRAL FEB-26"→ Cuatrimestral (formato explícito)
--   "CIERRE DICIEMBRE-25/ ABC"          → ABC (puede ir combinado con cierre)
--   "CIERRE ENERO-26"                   → Cierre mensual (revisión)
--   "" o NULL                           → Sin clasificar
-- Prioridad estricta, la primera que casa gana:
--   1. ABC              → contiene "ABC"
--   2. Planif Inicial   → contiene "INICIAL" Y "VALORADA"
--   3. Cuatrimestral    → contiene "CUATRIM" O "VALORADA" (el JO no siempre
--                         escribe "CUATRIMESTRAL")
--   4. Cierre mensual   → contiene "CIERRE" (sin ABC)
--   5. Sin clasificar   → resto
-- Solo Planif Inicial, ABC y Cuatrimestral rigen el mensual: los cierres son
-- revisiones de control que no reemplazan al plan (R-VERSION-MASTER).
--
-- Todo el fichero va en UNA transacción (`execute_sql_file` lo manda entero):
-- o se rehace o no se toca nada.

-- ===========================================================================
-- 0) Limpieza, en orden de dependencia inverso. El DROP de la tabla con
--    CASCADE se llevaría la vista; se dropea antes y se recrea abajo.
-- ===========================================================================
DROP VIEW  IF EXISTS mart.v_master_version_partida   CASCADE;
DROP VIEW  IF EXISTS mart.v_master_versiones_tipadas CASCADE;
DROP TABLE IF EXISTS mart.master_importe_mensual     CASCADE;
DROP TABLE IF EXISTS mart.master_versiones_tipadas   CASCADE;


-- ===========================================================================
-- 1) El catálogo: las ocho columnas de siempre, en su orden, y detrás las
--    nueve de F-161 (R7).
-- ===========================================================================
CREATE TABLE mart.master_versiones_tipadas AS
SELECT
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
    END AS tipo_master,
    tiene_reparto,
    reparto,
    n_lineas,
    n_lineas_con_reparto,
    importe_total,
    importe_con_reparto,
    importe_sin_reparto,
    tiene_cabecera,
    tiene_ancla
FROM stg.master_versiones
WHERE ambito_id IN (8, 11);

ALTER TABLE mart.master_versiones_tipadas ADD CONSTRAINT pk_master_versiones_tipadas PRIMARY KEY (obra_id, ambito_id, version);

COMMENT ON TABLE mart.master_versiones_tipadas IS
'Catálogo ÚNICO de las versiones master (ámbitos 8 y 11) con su tipo deducido del tex (Planif Inicial / ABC / Cuatrimestral / Cierre mensual / Sin clasificar). Desde F-161 tiene todas las versiones con líneas; solo las de tiene_reparto rigen el mensual. Lo leen 02_build_fact, 06_cp_tipologia, retenciones/05_fin_obra y tesoreria/07.';

CREATE OR REPLACE VIEW mart.v_master_versiones_tipadas AS
SELECT
    obra_id,
    ambito_id,
    version,
    version_fec_creacion,
    version_fec_efectiva,
    version_descripcion,
    version_tex,
    tipo_master,
    tiene_reparto,
    reparto,
    n_lineas,
    n_lineas_con_reparto,
    importe_total,
    importe_con_reparto,
    importe_sin_reparto,
    tiene_cabecera,
    tiene_ancla
FROM mart.master_versiones_tipadas;

COMMENT ON VIEW mart.v_master_versiones_tipadas IS
'Envoltorio de mart.master_versiones_tipadas (F-078): las ocho columnas de siempre en su orden y, detrás, las nueve de F-161.';


-- ===========================================================================
-- 2) El coste (o la venta) de cada versión por partida (R12, D14). No depende
--    del reparto: la v24 de coste de la 0698 sale entera aunque no tenga ni un
--    mes. Ámbitos 8 y 11. Es `importe` sin coeficientes (R-VENTA-COEFICIENTES).
--    Sin filtro de obra recorre las líneas master de stg.presupuesto: se
--    consulta por obra (y versión).
-- ===========================================================================
CREATE OR REPLACE VIEW mart.v_master_version_partida AS
SELECT
    o.empresa_id,
    o.clave_obra,
    l.obra_id,
    l.ambito_id,
    CASE l.ambito_id WHEN 8 THEN 'COSTE' WHEN 11 THEN 'VENTA' END AS concepto,
    l.version,
    vt.tipo_master,
    vt.reparto,
    l.partida_id,
    p.codigo_partida,
    p.descripcion_corta AS descripcion_partida,
    p.categoria,
    p.ruta_capitulos,
    l.cantidad,
    l.precio,
    l.importe,
    l.tiene_reparto
FROM stg.v_master_lineas l
JOIN mart.master_versiones_tipadas vt
    ON vt.obra_id   = l.obra_id
   AND vt.ambito_id = l.ambito_id
   AND vt.version   = l.version
JOIN stg.partidas p ON p.partida_id = l.partida_id
LEFT JOIN stg.obras o ON o.obra_id = l.obra_id;

COMMENT ON VIEW mart.v_master_version_partida IS
'Coste/venta (importe sin coeficientes) de cada versión master por partida, tenga reparto en el tiempo o no (F-161). Consultar filtrando por obra.';


-- ===========================================================================
-- 3) El planificado de IMPORTE al lado del temporal (R14-R17, D1, D3, D8-D10).
--
--    Por (obra, ámbito, mes), desde el mes de la primera versión con fecha
--    hasta el mes del BUILD (D9):
--      - la versión de IMPORTE: la última de CUALQUIER tipo con fecha efectiva
--        anterior al mes siguiente, entre las versiones >= 1 con líneas (D8).
--        Es el «último cierre».
--      - la TEMPORAL: la que elige 02_build_fact.sql para ese mes, con su
--        predicado copiado literal (con reparto, las dos fechas y tipo Planif
--        Inicial, ABC o Cuatrimestral). R16 lo vigila contra el hecho.
--      - las dos diferencias (D10): contra el total de la temporal y contra
--        lo que la temporal reparte. SIN REESCALAR (D3): se ponen al lado, no
--        se combinan.
--    «Hoy» es la fecha del build, congelada como en 06_cp_tipologia.sql (R17).
-- ===========================================================================
CREATE TABLE mart.master_importe_mensual AS
WITH params AS (
    SELECT CURRENT_DATE AS hoy
),
elegibles AS (
    SELECT *
    FROM mart.master_versiones_tipadas
    WHERE version >= 1
      AND n_lineas > 0
      AND version_fec_efectiva IS NOT NULL
),
temporales AS (
    SELECT *
    FROM mart.master_versiones_tipadas
    WHERE tiene_reparto
      AND version_fec_creacion IS NOT NULL
      AND version_fec_efectiva IS NOT NULL
      AND tipo_master IN ('Planif Inicial', 'ABC', 'Cuatrimestral')
),
inicio AS (
    SELECT obra_id, ambito_id,
           MIN(date_trunc('month', version_fec_efectiva))::DATE AS primer_mes
    FROM (
        SELECT obra_id, ambito_id, version_fec_efectiva FROM elegibles
        UNION ALL
        SELECT obra_id, ambito_id, version_fec_efectiva FROM temporales
    ) x
    GROUP BY obra_id, ambito_id
),
meses AS (
    SELECT i.obra_id, i.ambito_id, gs::DATE AS anio_mes
    FROM inicio i
    CROSS JOIN params p
    CROSS JOIN LATERAL generate_series(i.primer_mes, date_trunc('month', p.hoy)::DATE, INTERVAL '1 month') AS gs
),
importe AS (
    SELECT
        m.obra_id, m.ambito_id, m.anio_mes,
        e.version, e.tipo_master, e.version_tex, e.importe_total,
        ROW_NUMBER() OVER (
            PARTITION BY m.obra_id, m.ambito_id, m.anio_mes
            ORDER BY e.version_fec_efectiva DESC, e.version DESC
        ) AS rn
    FROM meses m
    JOIN elegibles e ON e.obra_id = m.obra_id AND e.ambito_id = m.ambito_id
    WHERE e.version_fec_efectiva < (m.anio_mes + INTERVAL '1 month')
),
temporal AS (
    SELECT
        m.obra_id, m.ambito_id, m.anio_mes,
        e.version, e.tipo_master, e.importe_total, e.importe_con_reparto,
        ROW_NUMBER() OVER (
            PARTITION BY m.obra_id, m.ambito_id, m.anio_mes
            ORDER BY e.version_fec_efectiva DESC, e.version DESC
        ) AS rn
    FROM meses m
    JOIN temporales e ON e.obra_id = m.obra_id AND e.ambito_id = m.ambito_id
    WHERE e.version_fec_efectiva < (m.anio_mes + INTERVAL '1 month')
)
SELECT
    m.obra_id,
    o.empresa_id,
    o.clave_obra,
    m.ambito_id,
    CASE m.ambito_id WHEN 8 THEN 'COSTE' WHEN 11 THEN 'VENTA' END AS concepto,
    m.anio_mes,
    i.version AS version_importe,
    i.tipo_master AS tipo_master_importe,
    i.version_tex AS version_tex_importe,
    i.importe_total AS importe_total_importe,
    t.version AS version_temporal,
    t.tipo_master AS tipo_master_temporal,
    t.importe_total AS importe_total_temporal,
    t.importe_con_reparto AS importe_con_reparto_temporal,
    (i.importe_total - t.importe_total)::NUMERIC(18,2) AS diferencia_importe,
    (i.importe_total - t.importe_con_reparto)::NUMERIC(18,2) AS diferencia_importe_con_reparto,
    COALESCE(i.version = t.version, FALSE) AS es_misma_version
FROM meses m
LEFT JOIN importe i
    ON i.obra_id = m.obra_id AND i.ambito_id = m.ambito_id AND i.anio_mes = m.anio_mes AND i.rn = 1
LEFT JOIN temporal t
    ON t.obra_id = m.obra_id AND t.ambito_id = m.ambito_id AND t.anio_mes = m.anio_mes AND t.rn = 1
LEFT JOIN stg.obras o ON o.obra_id = m.obra_id;

ALTER TABLE mart.master_importe_mensual ADD CONSTRAINT pk_master_importe_mensual PRIMARY KEY (obra_id, ambito_id, anio_mes);

COMMENT ON TABLE mart.master_importe_mensual IS
'Por obra, ámbito master y mes (hasta el mes del build): la versión del último cierre (planificado de importe, cualquier tipo) al lado de la temporal que rige el mensual, con sus totales y su diferencia. Sin reescalar: las dos cifras no se suman ni se mezclan (F-161, D3).';
