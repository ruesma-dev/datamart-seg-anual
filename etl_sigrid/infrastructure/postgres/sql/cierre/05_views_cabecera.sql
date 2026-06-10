-- etl_sigrid/infrastructure/postgres/sql/cierre/05_views_cabecera.sql
--
-- =========================================================================
-- TANDA 4.3 — Cabecera con TODAS las fechas posibles
-- =========================================================================
--
-- Mejoras sobre Tanda 4.1:
--   - INICIO REAL: prioriza fecreaini (inicio físico de obra) sobre
--                  fecreaact (activación administrativa del contrato).
--   - ADJUDICACIÓN: NUEVO. Cascada de fallback usando fechas reales del
--                   contrato disponibles en obrctr (real adj > real firma
--                   > previsto adj > previsto firma > obr.fecadj).
--   - INICIO PREVISTO: si no hay en obrctr ni obr, fallback al primer mes
--                      con master en el cierre.
--   - FIN PREVISTO: ídem, último mes con master en el cierre.
--
-- =========================================================================

DROP VIEW IF EXISTS cierre.v_pbi_cierre_cabecera CASCADE;

CREATE VIEW cierre.v_pbi_cierre_cabecera AS
WITH
-- Fechas de obrctr agregadas por obra. Una obra puede tener varios contratos
-- (804 principal, 932 modificado vacío…); cogemos el MÍNIMO no-nulo para
-- inicio (contrato más antiguo) y el MÁXIMO no-nulo para fin.
fechas_obrctr AS (
    SELECT
        c.obride AS obra_id,
        stg.fn_sigrid_date_to_date(MIN(NULLIF(c.fecreaact, 0))) AS fec_real_activacion,
        stg.fn_sigrid_date_to_date(MIN(NULLIF(c.fecreaini, 0))) AS fec_real_inicio_obra,
        stg.fn_sigrid_date_to_date(MIN(NULLIF(c.fecpreini, 0))) AS fec_prev_inicio,
        stg.fn_sigrid_date_to_date(MIN(NULLIF(c.fecinipla, 0))) AS fec_inicio_plan,
        stg.fn_sigrid_date_to_date(MAX(NULLIF(c.fecprefin, 0))) AS fec_prev_fin,
        stg.fn_sigrid_date_to_date(MAX(NULLIF(c.fecreafin, 0))) AS fec_real_fin,
        -- Adjudicación / firma (en cascada de prioridad para adjudicación)
        stg.fn_sigrid_date_to_date(MIN(NULLIF(c.fecreaadj, 0))) AS fec_real_adj,
        stg.fn_sigrid_date_to_date(MIN(NULLIF(c.fecpreadj, 0))) AS fec_prev_adj,
        stg.fn_sigrid_date_to_date(MIN(NULLIF(c.fecreafir, 0))) AS fec_real_firma,
        stg.fn_sigrid_date_to_date(MIN(NULLIF(c.fecprefir, 0))) AS fec_prev_firma
    FROM raw.obrctr c
    GROUP BY c.obride
),

-- Meses del cierre con master (fallback para inicio/fin previstos)
venta_meses AS (
    SELECT
        obra_id, anio_mes, final_importe,
        final_version_tex,
        ROW_NUMBER() OVER (PARTITION BY obra_id ORDER BY anio_mes ASC)  AS rn_asc,
        ROW_NUMBER() OVER (PARTITION BY obra_id ORDER BY anio_mes DESC) AS rn_desc
    FROM cierre.fact_cierre_mensual
    WHERE concepto = 'VENTA'
      AND final_fuente = 'master'
),
venta_inicial AS (
    SELECT obra_id, final_importe AS presupuesto_inicial_venta,
           final_version_tex      AS version_inicial,
           anio_mes               AS mes_inicial
    FROM venta_meses WHERE rn_asc = 1
),
venta_vigente AS (
    SELECT obra_id, final_importe AS presupuesto_vigente_venta,
           final_version_tex      AS version_vigente,
           anio_mes               AS mes_vigente
    FROM venta_meses WHERE rn_desc = 1
)
SELECT
    o.obra_id,
    o.codigo_obra,
    o.nombre_obra,
    obr.entide                                                 AS cliente_ide,
    cli.res                                                    AS cliente_nombre,
    NULLIF(obr.empide, 0)                                      AS tecnico_ide,
    tec.res                                                    AS tecnico_responsable,
    NULLIF(obr.cenide, 0)                                      AS centro_coste_ide,
    cenc.res                                                   AS centro_coste_nombre,
    NULLIF(obr.obrtipide, 0)                                   AS tipo_obra_ide,
    ot.res                                                     AS tipo_obra_nombre,
    NULLIF(obr.obrclaide, 0)                                   AS clase_obra_ide,
    oc2.res                                                    AS clase_obra_nombre,

    -- ==========================================================
    -- FECHAS — cascada de prioridad por extremo
    -- ==========================================================
    -- Inicio previsto: obrctr (fecpreini > fecinipla) → obr → primer mes master
    COALESCE(
        oc.fec_prev_inicio,
        oc.fec_inicio_plan,
        stg.fn_sigrid_date_to_date(obr.fecinipre),
        vi.mes_inicial
    )                                                          AS fecha_inicio_previsto,
    -- Fin previsto: obrctr → obr → último mes master
    COALESCE(
        oc.fec_prev_fin,
        stg.fn_sigrid_date_to_date(obr.fecfinpre),
        vv.mes_vigente
    )                                                          AS fecha_fin_previsto,
    -- Inicio real: PRIORIDAD a fecreaini (inicio fisico) sobre fecreaact (activación admin)
    COALESCE(
        oc.fec_real_inicio_obra,
        oc.fec_real_activacion,
        stg.fn_sigrid_date_to_date(obr.fecinirea)
    )                                                          AS fecha_inicio_real,
    -- Fin real: obrctr → obr (las obras vivas no lo tendrán)
    COALESCE(
        oc.fec_real_fin,
        stg.fn_sigrid_date_to_date(obr.fecfinrea)
    )                                                          AS fecha_fin_real,
    -- Adjudicación / firma: cascada amplia
    --   1. Real adj  2. Real firma  3. Previsto adj  4. Previsto firma  5. obr.fecadj
    COALESCE(
        oc.fec_real_adj,
        oc.fec_real_firma,
        oc.fec_prev_adj,
        oc.fec_prev_firma,
        stg.fn_sigrid_date_to_date(obr.fecadj)
    )                                                          AS fecha_adjudicacion,

    -- Plazo en meses: combina la mejor pareja disponible.
    --   1. Inicio real + fin real        (obra acabada)
    --   2. Inicio real + fin previsto    (obra activa)
    --   3. Inicio previsto + fin previsto (sin datos reales)
    CASE
        WHEN COALESCE(oc.fec_real_inicio_obra, oc.fec_real_activacion,
                      stg.fn_sigrid_date_to_date(obr.fecinirea)) IS NOT NULL
         AND COALESCE(oc.fec_real_fin,
                      stg.fn_sigrid_date_to_date(obr.fecfinrea)) IS NOT NULL
        THEN ROUND(
            (COALESCE(oc.fec_real_fin,
                      stg.fn_sigrid_date_to_date(obr.fecfinrea))
           - COALESCE(oc.fec_real_inicio_obra, oc.fec_real_activacion,
                      stg.fn_sigrid_date_to_date(obr.fecinirea)))::NUMERIC / 30.44, 1)
        WHEN COALESCE(oc.fec_real_inicio_obra, oc.fec_real_activacion,
                      stg.fn_sigrid_date_to_date(obr.fecinirea)) IS NOT NULL
         AND COALESCE(oc.fec_prev_fin,
                      stg.fn_sigrid_date_to_date(obr.fecfinpre),
                      vv.mes_vigente) IS NOT NULL
        THEN ROUND(
            (COALESCE(oc.fec_prev_fin,
                      stg.fn_sigrid_date_to_date(obr.fecfinpre),
                      vv.mes_vigente)
           - COALESCE(oc.fec_real_inicio_obra, oc.fec_real_activacion,
                      stg.fn_sigrid_date_to_date(obr.fecinirea)))::NUMERIC / 30.44, 1)
        WHEN COALESCE(oc.fec_prev_inicio, oc.fec_inicio_plan,
                      stg.fn_sigrid_date_to_date(obr.fecinipre),
                      vi.mes_inicial) IS NOT NULL
         AND COALESCE(oc.fec_prev_fin,
                      stg.fn_sigrid_date_to_date(obr.fecfinpre),
                      vv.mes_vigente) IS NOT NULL
        THEN ROUND(
            (COALESCE(oc.fec_prev_fin,
                      stg.fn_sigrid_date_to_date(obr.fecfinpre),
                      vv.mes_vigente)
           - COALESCE(oc.fec_prev_inicio, oc.fec_inicio_plan,
                      stg.fn_sigrid_date_to_date(obr.fecinipre),
                      vi.mes_inicial))::NUMERIC / 30.44, 1)
        ELSE NULL
    END                                                        AS plazo_meses,

    NULLIF(obr.coeind::NUMERIC, 0)                             AS coeficiente_indirectos,
    NULLIF(obr.suptot::NUMERIC, 0)                             AS superficie_total,
    NULLIF(obr.diride, 0)                                      AS director_obra_ide,
    vi.presupuesto_inicial_venta,
    vi.version_inicial,
    vv.presupuesto_vigente_venta,
    vv.version_vigente,
    vi.presupuesto_inicial_venta                               AS presupuesto_aprobado_venta,
    (COALESCE(vv.presupuesto_vigente_venta, 0)
     - COALESCE(vi.presupuesto_inicial_venta, 0))::NUMERIC(18,2) AS modificados_aprobados
FROM stg.obras o
LEFT JOIN raw.obr   obr ON obr.ide   = o.obra_id
LEFT JOIN raw.con   cli ON cli.ide   = obr.entide
LEFT JOIN raw.con   tec ON tec.ide   = NULLIF(obr.empide, 0)
LEFT JOIN raw.cen        cen ON cen.ide  = NULLIF(obr.cenide,    0)
LEFT JOIN raw.con        cenc ON cenc.ide = NULLIF(obr.cenide,   0)
LEFT JOIN raw.auxobrtip  ot  ON ot.ide   = NULLIF(obr.obrtipide, 0)
LEFT JOIN raw.auxobrcla  oc2 ON oc2.ide  = NULLIF(obr.obrclaide, 0)
LEFT JOIN fechas_obrctr oc ON oc.obra_id = o.obra_id
LEFT JOIN venta_inicial vi ON vi.obra_id = o.obra_id
LEFT JOIN venta_vigente vv ON vv.obra_id = o.obra_id;

COMMENT ON VIEW cierre.v_pbi_cierre_cabecera IS
'Cabecera del cierre (Tanda 3.1). Las fechas siguen una cascada de prioridad: '
'inicio real prioriza fecreaini (fisico) sobre fecreaact (admin); adjudicación '
'cae a fecreafir si no hay fecreaadj; inicio/fin previstos caen al primer/último '
'mes con master del cierre cuando obrctr y obr están vacíos. Cliente y técnico '
'salen de con.res via FK. Tanda 3.1: centro de coste, tipo y clase de obra ahora '
'muestran texto via JOIN con cen/auxobrtip/auxobrcla. Presupuesto aprobado = inicial.';
