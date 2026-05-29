-- etl_sigrid/infrastructure/postgres/sql/cierre/05_views_cabecera.sql
--
-- =========================================================================
-- TANDA 3 — Cabecera del cierre (datos identificativos de la obra)
-- =========================================================================
--
-- Replica la parte superior del Excel CONTROL DE GESTIÓN: identificación de
-- la obra, cliente, técnico responsable, fechas, plazo y presupuestos.
--
-- FUENTES:
--   - stg.obras       → obra_id VIGENTE (ya deduplicado por conext.cod='15'),
--                       codigo_obra, nombre_obra. CRÍTICO partir de aquí y NO
--                       de raw.obr directo, porque hay duplicados (mismo cod,
--                       distinto ide) y uno suele venir vacío.
--   - raw.obr         → campos de obra: fechas, FKs (entide, empide, cenide…),
--                       coeind, suptot. Unido por obr.ide = stg.obras.obra_id.
--   - raw.con (cli)   → nombre del cliente vía obr.entide → con.res.
--   - raw.con (tec)   → nombre del técnico responsable vía obr.empide → con.res.
--   - cierre.fact_cierre_mensual → presupuesto VENTA inicial y vigente
--                       (FINAL del primer y último mes con master).
--
-- PARSEO DE FECHAS: las fechas de raw.obr vienen como entero YYYYMMDD.
-- stg.fn_sigrid_date_to_date las convierte correctamente (0 → NULL).
--
-- CAMPOS QUE EN RUESMA SUELEN VENIR VACÍOS (se exponen igual, quedan NULL):
--   coeind, suptot, diride (director de obra), fecadj.
-- No se inventan: si Sigrid los tiene a 0, la vista devuelve NULL.
-- =========================================================================

DROP VIEW IF EXISTS cierre.v_pbi_cierre_cabecera CASCADE;

CREATE VIEW cierre.v_pbi_cierre_cabecera AS
WITH
-- Presupuesto VENTA inicial (primer mes con FINAL de master) y vigente
-- (último mes con FINAL de master) por obra, desde el fact ya construido.
venta_meses AS (
    SELECT
        obra_id,
        anio_mes,
        final_importe,
        final_version_tex,
        ROW_NUMBER() OVER (PARTITION BY obra_id ORDER BY anio_mes ASC)  AS rn_asc,
        ROW_NUMBER() OVER (PARTITION BY obra_id ORDER BY anio_mes DESC) AS rn_desc
    FROM cierre.fact_cierre_mensual
    WHERE concepto = 'VENTA'
      AND final_fuente = 'master'      -- solo meses con master real (no fase_0)
),
venta_inicial AS (
    SELECT obra_id, final_importe AS presupuesto_inicial_venta,
           final_version_tex AS version_inicial
    FROM venta_meses WHERE rn_asc = 1
),
venta_vigente AS (
    SELECT obra_id, final_importe AS presupuesto_vigente_venta,
           final_version_tex AS version_vigente
    FROM venta_meses WHERE rn_desc = 1
)
SELECT
    o.obra_id,
    o.codigo_obra,
    o.nombre_obra,
    -- Cliente (vía obr.entide → con.res)
    obr.entide                                       AS cliente_ide,
    cli.res                                          AS cliente_nombre,
    -- Técnico responsable (vía obr.empide → con.res)
    NULLIF(obr.empide, 0)                            AS tecnico_ide,
    tec.res                                          AS tecnico_responsable,
    -- Centro de coste (FK; texto pendiente de ingestar cen)
    NULLIF(obr.cenide, 0)                            AS centro_coste_ide,
    -- Tipo y clase de obra (FK; texto pendiente de ingestar auxobrtip/cla)
    NULLIF(obr.obrtipide, 0)                         AS tipo_obra_ide,
    NULLIF(obr.obrclaide, 0)                         AS clase_obra_ide,
    -- Fechas (entero YYYYMMDD → date; 0 → NULL)
    stg.fn_sigrid_date_to_date(obr.fecinipre)        AS fecha_inicio_previsto,
    stg.fn_sigrid_date_to_date(obr.fecfinpre)        AS fecha_fin_previsto,
    stg.fn_sigrid_date_to_date(obr.fecinirea)        AS fecha_inicio_real,
    stg.fn_sigrid_date_to_date(obr.fecfinrea)        AS fecha_fin_real,
    stg.fn_sigrid_date_to_date(obr.fecadj)           AS fecha_adjudicacion,
    -- Plazo en meses (preferir real; si no, previsto). NULL si faltan fechas.
    CASE
        WHEN stg.fn_sigrid_date_to_date(obr.fecinirea) IS NOT NULL
         AND stg.fn_sigrid_date_to_date(obr.fecfinrea) IS NOT NULL
        THEN ROUND(
            (stg.fn_sigrid_date_to_date(obr.fecfinrea)
           - stg.fn_sigrid_date_to_date(obr.fecinirea))::NUMERIC / 30.44, 1)
        WHEN stg.fn_sigrid_date_to_date(obr.fecinipre) IS NOT NULL
         AND stg.fn_sigrid_date_to_date(obr.fecfinpre) IS NOT NULL
        THEN ROUND(
            (stg.fn_sigrid_date_to_date(obr.fecfinpre)
           - stg.fn_sigrid_date_to_date(obr.fecinipre))::NUMERIC / 30.44, 1)
        ELSE NULL
    END                                              AS plazo_meses,
    -- Coeficiente indirectos y superficie (en Ruesma suelen venir 0 → NULL)
    NULLIF(obr.coeind::NUMERIC, 0)                   AS coeficiente_indirectos,
    NULLIF(obr.suptot::NUMERIC, 0)                   AS superficie_total,
    -- Director de obra (en Ruesma suele venir 0 → NULL)
    NULLIF(obr.diride, 0)                            AS director_obra_ide,
    -- Presupuestos VENTA (de master CIERRE: inicial = primer mes, vigente = último)
    vi.presupuesto_inicial_venta,
    vi.version_inicial,
    vv.presupuesto_vigente_venta,
    vv.version_vigente,
    -- Modificados aprobados = vigente − inicial
    (COALESCE(vv.presupuesto_vigente_venta, 0)
     - COALESCE(vi.presupuesto_inicial_venta, 0))::NUMERIC(18,2) AS modificados_aprobados
FROM stg.obras o
LEFT JOIN raw.obr obr  ON obr.ide = o.obra_id
LEFT JOIN raw.con cli  ON cli.ide = obr.entide
LEFT JOIN raw.con tec  ON tec.ide = NULLIF(obr.empide, 0)
LEFT JOIN venta_inicial vi ON vi.obra_id = o.obra_id
LEFT JOIN venta_vigente vv ON vv.obra_id = o.obra_id;

COMMENT ON VIEW cierre.v_pbi_cierre_cabecera IS
'Cabecera del cierre (parte superior del Excel CONTROL DE GESTIÓN). '
'Parte de stg.obras (ide vigente deduplicado) y cruza con raw.obr/raw.con. '
'Cliente y técnico salen de con.res vía FK. Presupuesto inicial/vigente del '
'master CIERRE (primer/último mes). Campos coeind, suptot, diride suelen venir '
'vacíos en Ruesma (NULL). Tipo/clase/centro quedan como FK numérico hasta '
'ingestar los catálogos auxobrtip/auxobrcla/cen.';
