-- etl_sigrid/infrastructure/postgres/sql/tesoreria/10_saldo_partida.sql
-- ============================================================================
-- F-150 · SCHEMA tesoreria (10/10): EL SALDO DE PARTIDA DE CADA OBRA (N14,
-- R38)
--
-- QUE ES: la caja que la obra YA movio, el PASO 0 (SALDO) de la receta: lo
-- cobrado y lo pagado REALIZADO hasta el build, CON IVA (los efectos lo
-- llevan), mas el coste del personal de sus partes. Son ingredientes: la
-- cuenta del saldo la hace quien consulta con H28 (con o sin saldo) y H29
-- (los pagares agrupados por sus originales o por el AGR), y la declara.
--
-- LOS PASOS, en una transaccion (este fichero entero):
--   1. `_sal_obra`: el universo, las obras de `tesoreria.devengo_corte_obra`
--      en COSTE (su empresa, su clave y su ultimo cierre).
--   2. `_sal_efecto`: los efectos de esas obras en `tesoreria.efectos` (la
--      cartera general: sin las nominas, que van por el devengo del recurso)
--      que cuentan: REALIZADO (cobros, pagos sin AGR y AGR con obra), los AGR
--      PREVISTO vivos con obra y los ORIGINALES agrupados (PAGO de BAJA con
--      `estado_codigo` 14, Agrupados: H29 rompe `R-TESORERIA-ESTADO` a
--      proposito, con su vencimiento como fecha de pago).
--   3. `_sal_cuota_cp`: la cuota de COSTE PROPORCIONAL (CP) de la factura de
--      cada pago, como en `07` (la categoria de las partidas de `raw.dcfpro`).
--   4. `_sal_personal`: el coste del personal de los partes (`raw.hmores.tot`,
--      el precio de cada parte, sin IVA) de los recursos PERSONA internos
--      (`raw.res.cla` 1, sin proveedor) hasta el ultimo cierre de la obra: lo
--      de despues ya es devengo pendiente y no se cuenta dos veces.
--   5. `_sal_iva_doc` (N15, R43): la fraccion de IVA de cada factura, cuota
--      entre total a pagar (`raw.dcf`) o entre total (`raw.dvf`). El IVA de
--      lo pagado (sin AGR mas los originales vencidos) y de lo cobrado es el
--      importe del efecto por esa fraccion; `_hasta_4t`, lo movido antes del
--      1 de enero del ano del build; `_hasta_4m`, lo movido en un mes 4 o mas
--      meses antes del mes del build. Cual cuenta como ya recuperado lo dice
--      H30 en la receta: este fichero no elige.
--   6. `TRUNCATE` + `INSERT`, una fila por obra.
--
-- Las retenciones son efectos propios: entran al cobrarse o pagarse; las
-- pendientes van en la proyeccion (la cartera viva).
--
-- Lee de: tesoreria.devengo_corte_obra, tesoreria.efectos, raw.dcfpro,
--         mart.v_pbi_dim_partida, raw.hmores, raw.res, raw.dcf, raw.dvf.
-- Escribe en: tesoreria.saldo_partida_obra.
-- ============================================================================

-- Guarda de entrada: sin sus fuentes, falla antes de vaciar nada.
DO $$
BEGIN
    IF to_regclass('tesoreria.devengo_corte_obra') IS NULL
       OR to_regclass('tesoreria.efectos') IS NULL
       OR to_regclass('raw.dcfpro') IS NULL
       OR to_regclass('mart.v_pbi_dim_partida') IS NULL
       OR to_regclass('raw.hmores') IS NULL
       OR to_regclass('raw.res') IS NULL
       OR to_regclass('raw.dcf') IS NULL
       OR to_regclass('raw.dvf') IS NULL THEN
        RAISE EXCEPTION 'saldo_partida: falta una fuente (tesoreria, raw.dcfpro, raw.hmores, raw.res, raw.dcf, raw.dvf o mart.v_pbi_dim_partida)';
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 1 · el universo: las obras de la receta
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE _sal_obra ON COMMIT DROP AS
SELECT k.obra_id, k.empresa_id, k.clave_obra, k.mes_ultimo_cierre
FROM tesoreria.devengo_corte_obra k WHERE k.concepto = 'COSTE';
ANALYZE _sal_obra;

-- ---------------------------------------------------------------------------
-- 2 · los efectos que cuentan en el saldo
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE _sal_efecto ON COMMIT DROP AS
SELECT e.*,
       CASE WHEN e.estado_tesoreria = 'REALIZADO' THEN COALESCE(e.fecha_real, e.fecha_vencimiento) ELSE e.fecha_vencimiento END AS fecha_movimiento
FROM tesoreria.efectos e
JOIN _sal_obra o ON o.obra_id = e.obra_id
WHERE e.estado_tesoreria = 'REALIZADO'
   OR (e.sentido = 'PAGO' AND e.estado_tesoreria = 'PREVISTO' AND e.serie_efecto = 'AGR')
   OR (e.sentido = 'PAGO' AND e.estado_tesoreria = 'BAJA' AND e.estado_codigo = 14);
ANALYZE _sal_efecto;

-- ---------------------------------------------------------------------------
-- 3 · la cuota de coste proporcional de cada factura pagada (como en 07)
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE _sal_cuota_cp ON COMMIT DROP AS
WITH dp AS MATERIALIZED (
    SELECT partida_id, categoria FROM mart.v_pbi_dim_partida
)
SELECT
    l.docide AS documento_id,
    COALESCE(SUM(l.tot::NUMERIC(18, 2)) FILTER (WHERE dp.categoria = 'CP') / NULLIF(SUM(l.tot::NUMERIC(18, 2)), 0), 0) AS cuota_cp
FROM raw.dcfpro l
LEFT JOIN dp ON dp.partida_id = NULLIF(l.paride, 0)
WHERE l.docide IN (
    SELECT e.documento_id FROM _sal_efecto e
    WHERE e.sentido = 'PAGO' AND e.documento_id IS NOT NULL
)
GROUP BY l.docide;
ANALYZE _sal_cuota_cp;

-- ---------------------------------------------------------------------------
-- 4 · el personal de los partes, hasta el ultimo cierre
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE _sal_personal ON COMMIT DROP AS
SELECT o.obra_id, SUM(COALESCE(h.tot, 0)::NUMERIC(18, 2)) AS personal_coste_partes
FROM raw.hmores h JOIN raw.res r ON r.ide = h.reside
JOIN _sal_obra o ON o.obra_id = NULLIF(h.obride, 0)
WHERE r.cla = 1 AND COALESCE(r.prvide, 0) = 0
  AND date_trunc('month', tesoreria.fn_fecha(h.fec))::DATE <= o.mes_ultimo_cierre
GROUP BY o.obra_id;
ANALYZE _sal_personal;

-- ---------------------------------------------------------------------------
-- 5 · la fraccion de IVA de cada factura pagada o cobrada (N15)
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE _sal_iva_doc ON COMMIT DROP AS
SELECT f.ide AS documento_id, 'PAGO'::VARCHAR(5) AS sentido, f.totiva::NUMERIC(18, 2) / NULLIF(f.totpag::NUMERIC(18, 2), 0) AS fraccion_iva FROM raw.dcf f
WHERE f.ide IN (SELECT e.documento_id FROM _sal_efecto e WHERE e.sentido = 'PAGO')
UNION ALL
SELECT v.ide AS documento_id, 'COBRO'::VARCHAR(5) AS sentido, v.totiva::NUMERIC(18, 2) / NULLIF(v.totdoc::NUMERIC(18, 2), 0) AS fraccion_iva FROM raw.dvf v
WHERE v.ide IN (SELECT e.documento_id FROM _sal_efecto e WHERE e.sentido = 'COBRO');
ANALYZE _sal_iva_doc;

-- ---------------------------------------------------------------------------
-- 6 · la tabla: una fila por obra
-- ---------------------------------------------------------------------------
TRUNCATE tesoreria.saldo_partida_obra;

INSERT INTO tesoreria.saldo_partida_obra (
    obra_id, empresa_id, clave_obra, fecha_corte, mes_ultimo_cierre,
    cobrado_realizado, pagado_realizado_sin_agr, pagado_agr_con_obra,
    agrupados_vencidos, agrupados_pendientes, cartera_viva_agr_con_obra,
    pagado_coste_proporcional, agrupados_vencidos_coste_proporcional,
    personal_coste_partes,
    iva_soportado_pagado, iva_repercutido_cobrado,
    iva_soportado_pagado_hasta_4t, iva_repercutido_cobrado_hasta_4t,
    iva_soportado_pagado_hasta_4m, iva_repercutido_cobrado_hasta_4m
)
SELECT
    o.obra_id                                           AS obra_id,
    o.empresa_id                                        AS empresa_id,
    o.clave_obra                                        AS clave_obra,
    CURRENT_DATE AS fecha_corte,
    o.mes_ultimo_cierre                                 AS mes_ultimo_cierre,
    COALESCE(s.cobrado_realizado, 0)                    AS cobrado_realizado,
    COALESCE(s.pagado_realizado_sin_agr, 0)             AS pagado_realizado_sin_agr,
    COALESCE(s.pagado_agr_con_obra, 0)                  AS pagado_agr_con_obra,
    COALESCE(s.agrupados_vencidos, 0)                   AS agrupados_vencidos,
    COALESCE(s.agrupados_pendientes, 0)                 AS agrupados_pendientes,
    COALESCE(s.cartera_viva_agr_con_obra, 0)            AS cartera_viva_agr_con_obra,
    ROUND(COALESCE(s.pagado_cp, 0), 2)                  AS pagado_coste_proporcional,
    ROUND(COALESCE(s.agrupados_vencidos_cp, 0), 2)      AS agrupados_vencidos_coste_proporcional,
    COALESCE(p.personal_coste_partes, 0)                AS personal_coste_partes,
    ROUND(COALESCE(s.iva_soportado_pagado, 0), 2) AS iva_soportado_pagado,
    ROUND(COALESCE(s.iva_repercutido_cobrado, 0), 2) AS iva_repercutido_cobrado,
    ROUND(COALESCE(s.iva_soportado_pagado_hasta_4t, 0), 2) AS iva_soportado_pagado_hasta_4t,
    ROUND(COALESCE(s.iva_repercutido_cobrado_hasta_4t, 0), 2) AS iva_repercutido_cobrado_hasta_4t,
    ROUND(COALESCE(s.iva_soportado_pagado_hasta_4m, 0), 2) AS iva_soportado_pagado_hasta_4m,
    ROUND(COALESCE(s.iva_repercutido_cobrado_hasta_4m, 0), 2) AS iva_repercutido_cobrado_hasta_4m
FROM _sal_obra o
LEFT JOIN (
    SELECT
        e.obra_id,
        SUM(e.importe) FILTER (WHERE e.sentido = 'COBRO' AND e.estado_tesoreria = 'REALIZADO') AS cobrado_realizado,
        SUM(e.importe) FILTER (WHERE e.sentido = 'PAGO' AND e.estado_tesoreria = 'REALIZADO' AND e.serie_efecto IS DISTINCT FROM 'AGR') AS pagado_realizado_sin_agr,
        SUM(e.importe) FILTER (WHERE e.sentido = 'PAGO' AND e.estado_tesoreria = 'REALIZADO' AND e.serie_efecto = 'AGR') AS pagado_agr_con_obra,
        SUM(e.importe) FILTER (WHERE e.sentido = 'PAGO' AND e.estado_tesoreria = 'BAJA' AND e.estado_codigo = 14 AND e.fecha_vencimiento < CURRENT_DATE) AS agrupados_vencidos,
        SUM(e.importe) FILTER (WHERE e.sentido = 'PAGO' AND e.estado_tesoreria = 'BAJA' AND e.estado_codigo = 14 AND e.fecha_vencimiento >= CURRENT_DATE) AS agrupados_pendientes,
        SUM(e.importe) FILTER (WHERE e.sentido = 'PAGO' AND e.estado_tesoreria = 'PREVISTO' AND NOT e.previsto_antiguo AND e.serie_efecto = 'AGR') AS cartera_viva_agr_con_obra,
        SUM(e.importe * COALESCE(q.cuota_cp, 0)) FILTER (WHERE e.sentido = 'PAGO' AND e.estado_tesoreria = 'REALIZADO' AND e.serie_efecto IS DISTINCT FROM 'AGR') AS pagado_cp,
        SUM(e.importe * COALESCE(q.cuota_cp, 0)) FILTER (WHERE e.sentido = 'PAGO' AND e.estado_tesoreria = 'BAJA' AND e.estado_codigo = 14 AND e.fecha_vencimiento < CURRENT_DATE) AS agrupados_vencidos_cp,
        SUM(e.importe * COALESCE(d.fraccion_iva, 0)) FILTER (WHERE e.sentido = 'PAGO' AND (e.estado_tesoreria = 'REALIZADO' AND e.serie_efecto IS DISTINCT FROM 'AGR' OR e.estado_tesoreria = 'BAJA' AND e.estado_codigo = 14 AND e.fecha_vencimiento < CURRENT_DATE)) AS iva_soportado_pagado,
        SUM(e.importe * COALESCE(d.fraccion_iva, 0)) FILTER (WHERE e.sentido = 'COBRO' AND e.estado_tesoreria = 'REALIZADO') AS iva_repercutido_cobrado,
        SUM(e.importe * COALESCE(d.fraccion_iva, 0)) FILTER (WHERE e.sentido = 'PAGO' AND (e.estado_tesoreria = 'REALIZADO' AND e.serie_efecto IS DISTINCT FROM 'AGR' OR e.estado_tesoreria = 'BAJA' AND e.estado_codigo = 14 AND e.fecha_vencimiento < CURRENT_DATE) AND e.fecha_movimiento < date_trunc('year', CURRENT_DATE)::DATE) AS iva_soportado_pagado_hasta_4t,
        SUM(e.importe * COALESCE(d.fraccion_iva, 0)) FILTER (WHERE e.sentido = 'COBRO' AND e.estado_tesoreria = 'REALIZADO' AND e.fecha_movimiento < date_trunc('year', CURRENT_DATE)::DATE) AS iva_repercutido_cobrado_hasta_4t,
        SUM(e.importe * COALESCE(d.fraccion_iva, 0)) FILTER (WHERE e.sentido = 'PAGO' AND (e.estado_tesoreria = 'REALIZADO' AND e.serie_efecto IS DISTINCT FROM 'AGR' OR e.estado_tesoreria = 'BAJA' AND e.estado_codigo = 14 AND e.fecha_vencimiento < CURRENT_DATE) AND (date_part('year', CURRENT_DATE) * 12 + date_part('month', CURRENT_DATE)) - (date_part('year', e.fecha_movimiento) * 12 + date_part('month', e.fecha_movimiento)) >= 4) AS iva_soportado_pagado_hasta_4m,
        SUM(e.importe * COALESCE(d.fraccion_iva, 0)) FILTER (WHERE e.sentido = 'COBRO' AND e.estado_tesoreria = 'REALIZADO' AND (date_part('year', CURRENT_DATE) * 12 + date_part('month', CURRENT_DATE)) - (date_part('year', e.fecha_movimiento) * 12 + date_part('month', e.fecha_movimiento)) >= 4) AS iva_repercutido_cobrado_hasta_4m
    FROM _sal_efecto e
    LEFT JOIN _sal_cuota_cp q ON q.documento_id = e.documento_id
    LEFT JOIN _sal_iva_doc d ON d.documento_id = e.documento_id AND d.sentido = e.sentido
    GROUP BY e.obra_id
) s ON s.obra_id = o.obra_id
LEFT JOIN _sal_personal p ON p.obra_id = o.obra_id;

COMMENT ON TABLE tesoreria.saldo_partida_obra IS
'F-150. El saldo de partida (paso 0 de la receta) de cada obra de devengo_corte_obra a fecha_corte (el dia del build), CON IVA: lo cobrado y lo pagado REALIZADO de tesoreria.efectos (sin los pagares agrupados AGR), los AGR realizados y vivos que conservan la obra, los efectos ORIGINALES agrupados (de BAJA con estado 14) vencidos y pendientes, la parte de coste proporcional (CP, no es caja de la obra) de lo pagado y de los originales vencidos, y el coste del personal de sus partes (raw.hmores, recursos PERSONA internos, hasta el ultimo cierre, sin IVA), y el IVA soportado de lo pagado y el repercutido de lo cobrado (por la fraccion de IVA de su factura), en total, antes del 1 de enero (_hasta_4t) y hasta 4 meses antes del mes del build (_hasta_4m). La cuenta la hace la receta con H28, H29 y H30. Clave: obra_id.';
