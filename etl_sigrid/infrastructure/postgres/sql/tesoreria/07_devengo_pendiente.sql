-- etl_sigrid/infrastructure/postgres/sql/tesoreria/07_devengo_pendiente.sql
-- ============================================================================
-- F-140 · SCHEMA tesoreria (8/9): EL DEVENGO PENDIENTE, DESCONTADO LO
-- EJECUTADO DESDE LA VERSION (R12-R15, D3-A, D5-A, D16-A, D19-A)
--
-- QUE ES: lo que la ultima version master (V) de cada obra todavia espera
-- devengar despues del ultimo mes cerrado, POR PARTIDA. No es caja: es el
-- ingrediente de devengo que luego se convierte con las hipotesis de
-- `tesoreria.hipotesis_caja`. Aqui no se aplica ningun plazo ni ningun IVA.
--
-- EL UNIVERSO: cada (obra, concepto) con algun mes PLANIFICADO en
-- `mart.fact_seguimiento_mensual` posterior a su ultimo mes REAL (el ultimo
-- cierre). Una obra sin ningun real entra, con `mes_ultimo_cierre` vacio.
-- Medido el 2026-10-24: 21 obras en coste y 21 en venta, una sola version cada
-- una.
--
-- LOS PASOS, en una transaccion (este fichero entero):
--   1. `_dev_version`: por (obra, concepto), el ultimo cierre, la version V
--      (la del ultimo mes planificado pendiente), su tipo y su mes efectivo
--      (`date_trunc` de `version_fec_efectiva`), el primer mes pendiente y
--      cuantas versiones distintas planifican lo pendiente.
--   2. `_dev_plan`: el plan de V por partida y mes. UNICO acceso a `stg`, con
--      obra, ambito master (8 coste, 11 venta) y version (R13,
--      `R-VERSION-MASTER`).
--   3. `_dev_ejecutado`: lo REAL de cada partida entre el mes de V y el ultimo
--      cierre, ambos incluidos.
--   4. `_dev_partida` y `tesoreria.devengo_pendiente_partida`: las partidas con
--      plan de V; `pendiente` = max(0, plan desde V - ejecutado) y
--      `sobre_ejecutado` el simetrico (`pendiente_partida` del dominio).
--   5. `tesoreria.devengo_pendiente_obra_mes`: el pendiente de cada partida
--      repartido en proporcion a su plan en los meses posteriores al cierre
--      (los meses a cero no son perfil), redondeado al centimo y con el resto
--      en el ultimo mes (`repartir_pendiente` del dominio). Sin perfil, todo al
--      primer mes pendiente y tambien en `importe_retraso_sin_perfil`. Guarda:
--      la suma por (obra, concepto) iguala la de la partida al centimo.
--   6. `tesoreria.devengo_corte_obra`: las sumas por (obra, concepto), con lo
--      adelantado y lo retrasado del intervalo, lo ejecutado en partidas sin
--      plan de V, el real a origen hasta el cierre, el plan total de V y la
--      frontera con la cartera (D16-A): lo PREVISTO vivo y lo emitido despues
--      del cierre, del sentido del concepto (COSTE -> PAGO, VENTA -> COBRO).
--      Los efectos van con IVA; el devengo, sin el.
--
-- F-150 (la receta de la caja), en VENTA y en la misma transaccion:
--   2 bis. `_dev_real`: lo REAL a origen de cada partida de venta hasta el
--      ultimo cierre (la misma fuente que `real_origen_corte`).
--   2 ter. `_dev_coef`: el coeficiente del MASTER de V de cada partida, de
--      `stg.presupuesto` filtrado por obra, ambitos 9 y 11 y version
--      (`R-VERSION-MASTER`): certificacion (9) si tiene importe y, si no, venta
--      (11); `ROUND(oficial / importe, 6)`, sin oficial = importe.
--   2 quater. `_dev_contrato`: el CONTRATO con el cliente de cada partida
--      (`raw.obrparpar.ctride`, solo si es de la misma obra) con su
--      coeficiente, su IVA y su retencion de `condiciones_contrato_cliente`.
--      `coeficiente_venta` = el del contrato y, si no, el del master (el orden
--      de `coeficiente_venta` del dominio); nunca una media de la obra.
--   4. La partida gana esas columnas y `pendiente_con_coeficientes`; guarda
--      (D6): una partida de venta con pendiente y sin coeficiente tumba el
--      paso, con su recuento, ANTES de vaciar nada.
--   5. El reparto lleva tambien el pendiente con coeficientes (el mismo reparto
--      de `repartir_pendiente`), y la obra-mes, su IVA y su retencion del
--      contrato y las bases que no los tienen (sobre ellas, H12 y H10). La
--      guarda de la suma mira tambien la suma con coeficientes.
--   6 bis. `_dev_hueco`: el hueco de facturacion de H26, NETO POR OBRA (nunca
--      por contrato): lo real a origen x su coeficiente (sin ninguno, x la
--      media ponderada de la obra, MEDIA_OBRA) menos lo facturado
--      (`raw.dvf.totbas` por el centro de coste de la obra, rectificativas
--      incluidas, sin corte de fecha), con suelo 0 y lo facturado por delante
--      aparte; su IVA y su retencion, por el peso de cada contrato.
--   6 ter (N12, 29-10). `_dev_cuota_cp`: la parte de COSTE PROPORCIONAL (CP,
--      estructura: no es caja de la obra) de cada factura de compra de la
--      cartera de las obras en COSTE = Σ `raw.dcfpro.tot` de sus lineas con
--      partida de `categoria` CP / Σ de todas (0 si suman 0; un efecto sin
--      factura, 0). El corte publica, en COSTE, la cartera viva y la emitida
--      tras el cierre por esa cuota, que el paso 7 de la receta resta.
--
-- Las tablas de trabajo son temporales y mueren con la transaccion. Si algo
-- falla, quedan las tablas de ayer. Cada una lleva su `ANALYZE`: sin
-- estadisticas el planificador las cree de una fila y cruza el perfil con las
-- partidas en bucle (medido en solo lectura el 2026-10-25: 875 s frente a
-- ~210 s sin bucles; el paso 1 solo, 70 s).
--
-- Lee de: mart.fact_seguimiento_mensual, mart.master_versiones_tipadas,
--         mart.v_pbi_dim_partida, stg.plan_mensual, stg.presupuesto,
--         maestro.v_obra_fichas, tesoreria.efectos,
--         tesoreria.condiciones_contrato_cliente, raw.obrparpar, raw.obr,
--         raw.dvf, raw.dcfpro.
-- Escribe en: tesoreria.devengo_pendiente_partida,
--             tesoreria.devengo_pendiente_obra_mes,
--             tesoreria.devengo_corte_obra.
-- ============================================================================

-- Guarda de entrada: sin sus fuentes, falla antes de vaciar nada.
DO $$
BEGIN
    IF to_regclass('mart.fact_seguimiento_mensual') IS NULL
       OR to_regclass('mart.master_versiones_tipadas') IS NULL
       OR to_regclass('mart.v_pbi_dim_partida') IS NULL
       OR to_regclass('stg.plan_mensual') IS NULL
       OR to_regclass('maestro.v_obra_fichas') IS NULL
       OR to_regclass('tesoreria.efectos') IS NULL
       OR to_regclass('stg.presupuesto') IS NULL
       OR to_regclass('raw.obrparpar') IS NULL
       OR to_regclass('raw.obr') IS NULL
       OR to_regclass('raw.dvf') IS NULL
       OR to_regclass('raw.dcfpro') IS NULL
       OR to_regclass('tesoreria.condiciones_contrato_cliente') IS NULL THEN
        RAISE EXCEPTION 'devengo_pendiente: falta una fuente (mart, stg, maestro, raw o tesoreria)';
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 1 · la version V de cada (obra, concepto)
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE _dev_version ON COMMIT DROP AS
WITH ult AS (
    SELECT f.obra_id, f.concepto, MAX(f.anio_mes) AS mes_ultimo_cierre
    FROM mart.fact_seguimiento_mensual f
    WHERE f.tipo_dato = 'REAL'
    GROUP BY f.obra_id, f.concepto
)
, pendientes AS (
    -- D2-A: V es la version del ULTIMO mes planificado pendiente.
    SELECT
        f.obra_id,
        f.concepto,
        u.mes_ultimo_cierre,
        (array_agg(f.version_master ORDER BY f.anio_mes DESC, f.version_master DESC))[1] AS version_master,
        COUNT(DISTINCT f.version_master) AS num_versiones_pendientes,
        MIN(f.anio_mes) AS primer_mes_pendiente
    FROM mart.fact_seguimiento_mensual f
    LEFT JOIN ult u ON u.obra_id = f.obra_id AND u.concepto = f.concepto
    WHERE f.tipo_dato = 'PLANIFICADO' AND (u.mes_ultimo_cierre IS NULL OR f.anio_mes > u.mes_ultimo_cierre)
    GROUP BY f.obra_id, f.concepto, u.mes_ultimo_cierre
)
, con_ambito AS (
    SELECT p.*, CASE p.concepto WHEN 'COSTE' THEN 8 WHEN 'VENTA' THEN 11 END AS ambito_id
    FROM pendientes p
)
SELECT
    a.obra_id,
    a.concepto,
    a.ambito_id,
    a.version_master,
    t.tipo_master,
    date_trunc('month', t.version_fec_efectiva)::DATE AS mes_version,
    a.mes_ultimo_cierre,
    a.primer_mes_pendiente,
    a.num_versiones_pendientes,
    fo.empresa_id,
    fo.clave_obra
FROM con_ambito a
LEFT JOIN LATERAL (
    SELECT x.tipo_master, x.version_fec_efectiva
    FROM mart.master_versiones_tipadas x
    WHERE x.obra_id = a.obra_id AND x.ambito_id = a.ambito_id AND x.version = a.version_master
    ORDER BY x.version_fec_efectiva DESC NULLS LAST
    LIMIT 1
) t ON TRUE
LEFT JOIN maestro.v_obra_fichas fo ON fo.obra_id = a.obra_id;
ANALYZE _dev_version;

-- Sin el mes de V no hay intervalo que descontar: falla cerrado, no se adivina.
DO $$
DECLARE
    n INTEGER;
BEGIN
    SELECT count(*) INTO n FROM _dev_version WHERE mes_version IS NULL OR version_master IS NULL;
    IF n > 0 THEN
        RAISE EXCEPTION 'devengo_pendiente: % (obra, concepto) sin version master o sin su fecha efectiva', n;
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 2 · el plan de V por partida y mes (unico acceso a stg)
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE _dev_plan ON COMMIT DROP AS
SELECT v.obra_id, v.concepto, pm.partida_id, pm.anio_mes, SUM(pm.importe_mes) AS importe_mes
FROM _dev_version v
JOIN stg.plan_mensual pm ON pm.obra_id = v.obra_id AND pm.ambito_id = v.ambito_id AND pm.version = v.version_master
GROUP BY v.obra_id, v.concepto, pm.partida_id, pm.anio_mes;
ANALYZE _dev_plan;

-- ---------------------------------------------------------------------------
-- 3 · lo ejecutado por partida entre el mes de V y el ultimo cierre
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE _dev_ejecutado ON COMMIT DROP AS
SELECT v.obra_id, v.concepto, f.partida_id, SUM(f.importe_mes) AS ejecutado_intervalo
FROM _dev_version v
JOIN mart.fact_seguimiento_mensual f ON f.obra_id = v.obra_id AND f.concepto = v.concepto AND f.tipo_dato = 'REAL' AND f.anio_mes >= v.mes_version AND f.anio_mes <= v.mes_ultimo_cierre
GROUP BY v.obra_id, v.concepto, f.partida_id;
ANALYZE _dev_ejecutado;

-- ---------------------------------------------------------------------------
-- 2 bis · lo real a origen de cada partida de venta hasta el cierre (F-150)
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE _dev_real ON COMMIT DROP AS
SELECT v.obra_id, f.partida_id, SUM(f.importe_mes) AS real_origen
FROM _dev_version v
JOIN mart.fact_seguimiento_mensual f ON f.obra_id = v.obra_id AND f.concepto = v.concepto AND f.tipo_dato = 'REAL' AND f.anio_mes <= v.mes_ultimo_cierre WHERE v.concepto = 'VENTA'
GROUP BY v.obra_id, f.partida_id;
ANALYZE _dev_real;

-- ---------------------------------------------------------------------------
-- 2 ter · el coeficiente del master de V por partida de venta (F-150, D3)
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE _dev_coef ON COMMIT DROP AS
SELECT
    m.obra_id,
    m.partida_id,
    CASE WHEN m.importe_cert <> 0 THEN ROUND(COALESCE(m.oficial_cert, m.importe_cert) / m.importe_cert, 6)
         WHEN m.importe_venta <> 0 THEN ROUND(COALESCE(m.oficial_venta, m.importe_venta) / m.importe_venta, 6)
    END AS coeficiente_master,
    CASE WHEN m.importe_cert <> 0 THEN 'MASTER_CERT'
         WHEN m.importe_venta <> 0 THEN 'MASTER_VENTA'
    END AS fuente_master
FROM (
    SELECT
        pp.obra_id,
        pp.partida_id,
        SUM(pp.importe) FILTER (WHERE pp.ambito_id = 9) AS importe_cert,
        SUM(pp.importe_oficial) FILTER (WHERE pp.ambito_id = 9) AS oficial_cert,
        SUM(pp.importe) FILTER (WHERE pp.ambito_id = 11) AS importe_venta,
        SUM(pp.importe_oficial) FILTER (WHERE pp.ambito_id = 11) AS oficial_venta
    FROM _dev_version v
    JOIN stg.presupuesto pp ON pp.obra_id = v.obra_id AND pp.ambito_id IN (9, 11) AND pp.fase_num = v.version_master WHERE v.concepto = 'VENTA'
    GROUP BY pp.obra_id, pp.partida_id
) m;
ANALYZE _dev_coef;

-- ---------------------------------------------------------------------------
-- 2 quater · el contrato con el cliente de cada partida de venta (F-150, N1-N4)
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE _dev_contrato ON COMMIT DROP AS
SELECT
    pv.obra_id,
    pv.partida_id,
    k.contrato_cliente_id,
    COALESCE(k.coeficiente_contrato, m.coeficiente_master) AS coeficiente_venta,
    CASE WHEN k.coeficiente_contrato IS NOT NULL THEN 'CONTRATO'
         WHEN m.coeficiente_master IS NOT NULL THEN m.fuente_master
         ELSE 'SIN'
    END AS fuente_coeficiente,
    m.coeficiente_master,
    k.iva_porcentaje,
    CASE WHEN k.iva_porcentaje IS NOT NULL THEN 'CONTRATO' ELSE 'SIN' END AS fuente_iva,
    k.retencion_porcentaje,
    CASE WHEN k.retencion_porcentaje IS NOT NULL THEN 'CONTRATO' ELSE 'SIN' END AS fuente_retencion
FROM (
    SELECT obra_id, partida_id FROM _dev_plan WHERE concepto = 'VENTA'
    UNION
    SELECT obra_id, partida_id FROM _dev_real
) pv
LEFT JOIN raw.obrparpar op ON op.ide = pv.partida_id
LEFT JOIN tesoreria.condiciones_contrato_cliente k ON k.contrato_cliente_id = NULLIF(op.ctride, 0) AND k.obra_id = pv.obra_id
LEFT JOIN _dev_coef m ON m.obra_id = pv.obra_id AND m.partida_id = pv.partida_id;
ANALYZE _dev_contrato;

-- ---------------------------------------------------------------------------
-- 4 · la partida: pendiente y sobre-ejecutado
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE _dev_partida ON COMMIT DROP AS
SELECT
    d.*,
    GREATEST(0, d.plan_desde_version - d.ejecutado_intervalo) AS pendiente,
    GREATEST(0, d.ejecutado_intervalo - d.plan_desde_version) AS sobre_ejecutado,
    c.contrato_cliente_id,
    c.coeficiente_venta,
    c.fuente_coeficiente,
    c.coeficiente_master,
    ROUND(GREATEST(0, d.plan_desde_version - d.ejecutado_intervalo) * c.coeficiente_venta, 2) AS pendiente_con_coeficientes,
    c.iva_porcentaje,
    c.fuente_iva,
    c.retencion_porcentaje,
    c.fuente_retencion
FROM (
    SELECT
        pl.obra_id,
        pl.concepto,
        pl.partida_id,
        pl.plan_desde_version,
        pl.plan_intervalo,
        pl.plan_restante,
        pl.total_perfil,
        pl.plan_total,
        COALESCE(e.ejecutado_intervalo, 0) AS ejecutado_intervalo
    FROM (
        SELECT
            p.obra_id,
            p.concepto,
            p.partida_id,
            COALESCE(SUM(p.importe_mes) FILTER (WHERE p.anio_mes >= v.mes_version), 0) AS plan_desde_version,
            COALESCE(SUM(p.importe_mes) FILTER (WHERE p.anio_mes >= v.mes_version AND p.anio_mes <= v.mes_ultimo_cierre), 0) AS plan_intervalo,
            COALESCE(SUM(p.importe_mes) FILTER (WHERE p.anio_mes >= v.mes_version AND (v.mes_ultimo_cierre IS NULL OR p.anio_mes > v.mes_ultimo_cierre)), 0) AS plan_restante,
            -- El perfil del reparto: los meses con plan tras el cierre (a cero no cuentan).
            SUM(p.importe_mes) FILTER (WHERE p.anio_mes >= v.mes_version AND (v.mes_ultimo_cierre IS NULL OR p.anio_mes > v.mes_ultimo_cierre) AND p.importe_mes <> 0) AS total_perfil,
            SUM(p.importe_mes) AS plan_total
        FROM _dev_plan p
        JOIN _dev_version v ON v.obra_id = p.obra_id AND v.concepto = p.concepto
        GROUP BY p.obra_id, p.concepto, p.partida_id
    ) pl
    LEFT JOIN _dev_ejecutado e
           ON e.obra_id = pl.obra_id AND e.concepto = pl.concepto AND e.partida_id = pl.partida_id
) d
LEFT JOIN _dev_contrato c ON c.obra_id = d.obra_id AND c.partida_id = d.partida_id AND d.concepto = 'VENTA';
ANALYZE _dev_partida;

-- Guarda de D6 (F-150): una partida de venta con pendiente necesita su
-- coeficiente (del contrato o del master). Sin el, falla cerrado y con su
-- recuento, ANTES de vaciar las tablas: no se adivina un coeficiente.
DO $$
DECLARE
    n INTEGER;
BEGIN
    SELECT count(*) INTO n
      FROM _dev_partida d
     WHERE d.concepto = 'VENTA' AND d.pendiente > 0 AND d.coeficiente_venta IS NULL;
    IF n > 0 THEN
        RAISE EXCEPTION 'devengo_pendiente: % partidas de venta con pendiente y sin coeficiente (ni del contrato ni del master)', n;
    END IF;
END $$;

TRUNCATE tesoreria.devengo_pendiente_partida;

INSERT INTO tesoreria.devengo_pendiente_partida (
    obra_id, empresa_id, clave_obra, partida_id, codigo_partida, concepto,
    categoria, version_master, tipo_master, mes_version, mes_ultimo_cierre,
    plan_desde_version, plan_intervalo, ejecutado_intervalo, plan_restante,
    pendiente, sobre_ejecutado, contrato_cliente_id, coeficiente_venta,
    fuente_coeficiente, coeficiente_master, pendiente_con_coeficientes,
    iva_porcentaje, fuente_iva, retencion_porcentaje, fuente_retencion
)
SELECT
    d.obra_id                AS obra_id,
    v.empresa_id             AS empresa_id,
    v.clave_obra             AS clave_obra,
    d.partida_id             AS partida_id,
    dp.codigo_partida        AS codigo_partida,
    d.concepto               AS concepto,
    dp.categoria             AS categoria,
    v.version_master         AS version_master,
    v.tipo_master            AS tipo_master,
    v.mes_version            AS mes_version,
    v.mes_ultimo_cierre      AS mes_ultimo_cierre,
    d.plan_desde_version     AS plan_desde_version,
    d.plan_intervalo         AS plan_intervalo,
    d.ejecutado_intervalo    AS ejecutado_intervalo,
    d.plan_restante          AS plan_restante,
    d.pendiente              AS pendiente,
    d.sobre_ejecutado        AS sobre_ejecutado,
    d.contrato_cliente_id    AS contrato_cliente_id,
    d.coeficiente_venta      AS coeficiente_venta,
    d.fuente_coeficiente     AS fuente_coeficiente,
    d.coeficiente_master     AS coeficiente_master,
    d.pendiente_con_coeficientes AS pendiente_con_coeficientes,
    d.iva_porcentaje         AS iva_porcentaje,
    d.fuente_iva             AS fuente_iva,
    d.retencion_porcentaje   AS retencion_porcentaje,
    d.fuente_retencion       AS fuente_retencion
FROM _dev_partida d
JOIN _dev_version v ON v.obra_id = d.obra_id AND v.concepto = d.concepto
LEFT JOIN mart.v_pbi_dim_partida dp ON dp.partida_id = d.partida_id;

-- ---------------------------------------------------------------------------
-- 5 · el reparto del pendiente en los meses (por obra, mes y categoria)
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE _dev_reparto ON COMMIT DROP AS
WITH perfil AS (
    SELECT p.obra_id, p.concepto, p.partida_id, p.anio_mes, p.importe_mes
    FROM _dev_plan p
    JOIN _dev_version v ON v.obra_id = p.obra_id AND v.concepto = p.concepto
    WHERE p.anio_mes >= v.mes_version AND (v.mes_ultimo_cierre IS NULL OR p.anio_mes > v.mes_ultimo_cierre) AND p.importe_mes <> 0
)
, partes AS (
    SELECT
        pr.obra_id,
        pr.concepto,
        pr.partida_id,
        pr.anio_mes,
        d.pendiente,
        ROUND(d.pendiente * pr.importe_mes / d.total_perfil, 2) AS parte,
        d.pendiente_con_coeficientes,
        ROUND(d.pendiente_con_coeficientes * pr.importe_mes / d.total_perfil, 2) AS parte_con_coef,
        ROW_NUMBER() OVER (PARTITION BY pr.obra_id, pr.concepto, pr.partida_id ORDER BY pr.anio_mes DESC) AS desde_el_final
    FROM perfil pr
    JOIN _dev_partida d ON d.obra_id = pr.obra_id AND d.concepto = pr.concepto AND d.partida_id = pr.partida_id
    WHERE d.pendiente > 0 AND d.total_perfil > 0
)
, repartido AS (
    -- El ultimo mes del perfil absorbe el redondeo: la suma es el pendiente.
    SELECT
        r.obra_id,
        r.concepto,
        r.partida_id,
        r.anio_mes,
        CASE WHEN r.desde_el_final = 1 THEN r.pendiente - (r.suma_partes - r.parte) ELSE r.parte END AS importe,
        CASE WHEN r.desde_el_final = 1 THEN r.pendiente_con_coeficientes - (r.suma_partes_con_coef - r.parte_con_coef) ELSE r.parte_con_coef END AS importe_con_coef
    FROM (
        SELECT x.*,
               SUM(x.parte) OVER (PARTITION BY x.obra_id, x.concepto, x.partida_id) AS suma_partes,
               SUM(x.parte_con_coef) OVER (PARTITION BY x.obra_id, x.concepto, x.partida_id) AS suma_partes_con_coef
        FROM partes x
    ) r
)
, sin_perfil AS (
    -- D19-A: sin perfil restante, al primer mes pendiente y marcado.
    SELECT d.obra_id, d.concepto, d.partida_id, v.primer_mes_pendiente AS anio_mes, d.pendiente AS importe,
           d.pendiente_con_coeficientes AS importe_con_coef, TRUE AS es_retraso
    FROM _dev_partida d
    JOIN _dev_version v ON v.obra_id = d.obra_id AND v.concepto = d.concepto
    WHERE d.pendiente > 0 AND COALESCE(d.total_perfil, 0) <= 0
)
SELECT pr.obra_id, pr.concepto, pr.partida_id, pr.anio_mes,
       pr.importe_mes AS plan_restante, 0::NUMERIC AS pendiente, 0::NUMERIC AS retraso_sin_perfil,
       NULL::NUMERIC AS importe_con_coef
FROM perfil pr
UNION ALL
SELECT r.obra_id, r.concepto, r.partida_id, r.anio_mes, 0::NUMERIC, r.importe, 0::NUMERIC, r.importe_con_coef
FROM repartido r
UNION ALL
SELECT s.obra_id, s.concepto, s.partida_id, s.anio_mes, 0::NUMERIC, s.importe, s.importe, s.importe_con_coef
FROM sin_perfil s;
ANALYZE _dev_reparto;

TRUNCATE tesoreria.devengo_pendiente_obra_mes;

INSERT INTO tesoreria.devengo_pendiente_obra_mes (
    obra_id, empresa_id, clave_obra, anio_mes, concepto, categoria,
    version_master, mes_ultimo_cierre, importe_plan_restante,
    importe_pendiente, importe_retraso_sin_perfil, num_partidas,
    mes_pasado_sin_cierre, importe_pendiente_con_coeficientes, coeficiente_venta,
    importe_iva_contrato, base_sin_iva_contrato, importe_retencion_contrato,
    base_sin_retencion_contrato
)
SELECT
    x.obra_id                         AS obra_id,
    v.empresa_id                      AS empresa_id,
    v.clave_obra                      AS clave_obra,
    x.anio_mes                        AS anio_mes,
    x.concepto                        AS concepto,
    x.categoria                       AS categoria,
    v.version_master                  AS version_master,
    v.mes_ultimo_cierre               AS mes_ultimo_cierre,
    x.importe_plan_restante           AS importe_plan_restante,
    x.importe_pendiente               AS importe_pendiente,
    x.importe_retraso_sin_perfil      AS importe_retraso_sin_perfil,
    x.num_partidas                    AS num_partidas,
    x.anio_mes < date_trunc('month', CURRENT_DATE)::DATE AS mes_pasado_sin_cierre,
    CASE WHEN x.concepto = 'VENTA' THEN COALESCE(x.importe_con_coef, 0) END AS importe_pendiente_con_coeficientes,
    CASE WHEN x.concepto = 'VENTA' AND x.importe_pendiente <> 0 THEN ROUND(x.importe_con_coef / x.importe_pendiente, 6) END AS coeficiente_venta,
    CASE WHEN x.concepto = 'VENTA' THEN ROUND(COALESCE(x.iva_bruto, 0) / 100, 2) END AS importe_iva_contrato,
    CASE WHEN x.concepto = 'VENTA' THEN COALESCE(x.base_sin_iva, 0) END AS base_sin_iva_contrato,
    CASE WHEN x.concepto = 'VENTA' THEN ROUND(COALESCE(x.retencion_bruto, 0) / 100, 2) END AS importe_retencion_contrato,
    CASE WHEN x.concepto = 'VENTA' THEN COALESCE(x.base_sin_retencion, 0) END AS base_sin_retencion_contrato
FROM (
    SELECT
        r.obra_id,
        r.concepto,
        r.anio_mes,
        dp.categoria,
        SUM(r.plan_restante) AS importe_plan_restante,
        SUM(r.pendiente) AS importe_pendiente,
        SUM(r.retraso_sin_perfil) AS importe_retraso_sin_perfil,
        COUNT(DISTINCT r.partida_id) AS num_partidas,
        SUM(r.importe_con_coef) AS importe_con_coef,
        SUM(r.importe_con_coef * r.iva_porcentaje) FILTER (WHERE r.fuente_iva = 'CONTRATO') AS iva_bruto,
        SUM(r.importe_con_coef) FILTER (WHERE r.fuente_iva = 'SIN') AS base_sin_iva,
        SUM(r.importe_con_coef * r.retencion_porcentaje) FILTER (WHERE r.fuente_retencion = 'CONTRATO') AS retencion_bruto,
        SUM(r.importe_con_coef) FILTER (WHERE r.fuente_retencion = 'SIN') AS base_sin_retencion
    FROM (
        SELECT rp.*, d.iva_porcentaje, d.fuente_iva, d.retencion_porcentaje, d.fuente_retencion
        FROM _dev_reparto rp
        JOIN _dev_partida d ON d.obra_id = rp.obra_id AND d.concepto = rp.concepto AND d.partida_id = rp.partida_id
    ) r
    LEFT JOIN mart.v_pbi_dim_partida dp ON dp.partida_id = r.partida_id
    GROUP BY r.obra_id, r.concepto, r.anio_mes, dp.categoria
) x
JOIN _dev_version v ON v.obra_id = x.obra_id AND v.concepto = x.concepto;

-- Guarda de la suma: el reparto no crea ni pierde un centimo (R14).
DO $$
DECLARE
    fallo RECORD;
BEGIN
    SELECT COALESCE(p.obra_id, m.obra_id) AS obra_id,
           COALESCE(p.concepto, m.concepto) AS concepto,
           p.total AS total_partida,
           m.total AS total_mes,
           p.total_coef AS total_coef_partida,
           m.total_coef AS total_coef_mes
      INTO fallo
      FROM (SELECT obra_id, concepto, SUM(pendiente) AS total,
                   SUM(pendiente_con_coeficientes) AS total_coef
              FROM tesoreria.devengo_pendiente_partida GROUP BY obra_id, concepto) p
      FULL JOIN (SELECT obra_id, concepto, SUM(importe_pendiente) AS total,
                        SUM(importe_pendiente_con_coeficientes) AS total_coef
                   FROM tesoreria.devengo_pendiente_obra_mes GROUP BY obra_id, concepto) m
        ON m.obra_id = p.obra_id AND m.concepto = p.concepto
     WHERE COALESCE(p.total, 0) IS DISTINCT FROM COALESCE(m.total, 0)
        OR COALESCE(p.total_coef, 0) IS DISTINCT FROM COALESCE(m.total_coef, 0)
     LIMIT 1;
    IF FOUND THEN
        RAISE EXCEPTION 'devengo_pendiente: el reparto de la obra % (%) suma % y la partida % (con coeficientes, % y %)',
            fallo.obra_id, fallo.concepto, fallo.total_mes, fallo.total_partida,
            fallo.total_coef_mes, fallo.total_coef_partida;
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 6 bis · el hueco de facturacion de H26, NETO POR OBRA (F-150, N6, N9)
--
-- Por obra de venta: lo real a origen x su coeficiente (`r`); las partidas sin
-- ninguno, x la media ponderada de la obra (`coeficiente_medio` del dominio;
-- sin ninguna en la obra, 1) y declaradas en `venta_real_media_obra`. Menos lo
-- facturado (`f`), con suelo 0 por OBRA. El IVA y la retencion del hueco, por
-- el peso de cada contrato en `r` (sin contrato o sin dato, a la base sin el).
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE _dev_hueco ON COMMIT DROP AS
WITH media AS (
    SELECT r.obra_id,
           COALESCE(ROUND(SUM(r.real_origen * c.coeficiente_venta) FILTER (WHERE c.coeficiente_venta IS NOT NULL) / NULLIF(SUM(r.real_origen) FILTER (WHERE c.coeficiente_venta IS NOT NULL), 0), 6), 1) AS coeficiente_medio
    FROM _dev_real r
    JOIN _dev_contrato c ON c.obra_id = r.obra_id AND c.partida_id = r.partida_id
    GROUP BY r.obra_id
)
, valorado AS (
    SELECT r.obra_id,
           r.real_origen * COALESCE(c.coeficiente_venta, me.coeficiente_medio) AS real_con_coef,
           CASE WHEN c.coeficiente_venta IS NULL THEN r.real_origen * me.coeficiente_medio END AS real_media,
           c.iva_porcentaje, c.fuente_iva, c.retencion_porcentaje, c.fuente_retencion
    FROM _dev_real r
    JOIN _dev_contrato c ON c.obra_id = r.obra_id AND c.partida_id = r.partida_id
    JOIN media me ON me.obra_id = r.obra_id
)
, real_obra AS (
    SELECT obra_id,
           SUM(real_con_coef) AS real_con_coef_bruto,
           ROUND(SUM(real_con_coef), 2) AS venta_real_origen_con_coeficientes,
           ROUND(COALESCE(SUM(real_media), 0), 2) AS venta_real_media_obra,
           SUM(real_con_coef * iva_porcentaje) FILTER (WHERE fuente_iva = 'CONTRATO') AS iva_ponderado,
           SUM(real_con_coef) FILTER (WHERE fuente_iva = 'SIN') AS real_sin_iva,
           SUM(real_con_coef * retencion_porcentaje) FILTER (WHERE fuente_retencion = 'CONTRATO') AS retencion_ponderado,
           SUM(real_con_coef) FILTER (WHERE fuente_retencion = 'SIN') AS real_sin_retencion
    FROM valorado
    GROUP BY obra_id
)
, facturado AS (
    SELECT ob.ide AS obra_id, SUM(fv.totbas::NUMERIC(18, 2)) AS facturado_origen
    FROM raw.dvf fv JOIN raw.obr ob ON ob.cenide = fv.cenide
    WHERE ob.ide IN (SELECT obra_id FROM _dev_version WHERE concepto = 'VENTA')
    GROUP BY ob.ide
)
, h AS (
    SELECT v.obra_id,
           COALESCE(ro.real_con_coef_bruto, 0) AS real_con_coef_bruto,
           COALESCE(ro.venta_real_origen_con_coeficientes, 0) AS venta_real_origen_con_coeficientes,
           COALESCE(ro.venta_real_media_obra, 0) AS venta_real_media_obra,
           ROUND(COALESCE(fa.facturado_origen, 0), 2) AS facturado_origen,
           COALESCE(ro.iva_ponderado, 0) AS iva_ponderado,
           COALESCE(ro.real_sin_iva, 0) AS real_sin_iva,
           COALESCE(ro.retencion_ponderado, 0) AS retencion_ponderado,
           COALESCE(ro.real_sin_retencion, 0) AS real_sin_retencion
    FROM _dev_version v
    LEFT JOIN real_obra ro ON ro.obra_id = v.obra_id
    LEFT JOIN facturado fa ON fa.obra_id = v.obra_id
    WHERE v.concepto = 'VENTA'
)
, neto AS (
    SELECT
        h.*,
        GREATEST(0, h.venta_real_origen_con_coeficientes - h.facturado_origen) AS venta_pendiente_facturar,
        GREATEST(0, h.facturado_origen - h.venta_real_origen_con_coeficientes) AS facturado_por_delante
    FROM h
)
-- El IVA y la retencion del hueco, por el peso de cada contrato en lo real con
-- coeficientes de la obra; sin peso (lo real a 0), todo a la base sin el.
SELECT
    h.*,
    COALESCE(ROUND(h.venta_pendiente_facturar * h.iva_ponderado / 100 / NULLIF(h.real_con_coef_bruto, 0), 2), 0) AS iva_pendiente_facturar_contrato,
    COALESCE(ROUND(h.venta_pendiente_facturar * h.real_sin_iva / NULLIF(h.real_con_coef_bruto, 0), 2), h.venta_pendiente_facturar) AS base_pendiente_facturar_sin_iva_contrato,
    COALESCE(ROUND(h.venta_pendiente_facturar * h.retencion_ponderado / 100 / NULLIF(h.real_con_coef_bruto, 0), 2), 0) AS retencion_pendiente_facturar_contrato,
    COALESCE(ROUND(h.venta_pendiente_facturar * h.real_sin_retencion / NULLIF(h.real_con_coef_bruto, 0), 2), h.venta_pendiente_facturar) AS base_pendiente_facturar_sin_retencion_contrato
FROM neto h;
ANALYZE _dev_hueco;

-- ---------------------------------------------------------------------------
-- 6 ter · la cuota de coste proporcional de cada factura de la cartera (N12)
-- ---------------------------------------------------------------------------
-- Solo las facturas de los pagos de las obras en COSTE: la categoria de la
-- partida de cada linea, el mismo criterio que el devengo (la cuenta del efecto
-- es la del proveedor y el nombre del tercero da falsos positivos).
CREATE TEMP TABLE _dev_cuota_cp ON COMMIT DROP AS
SELECT
    l.docide AS documento_id,
    COALESCE(SUM(l.tot::NUMERIC(18, 2)) FILTER (WHERE dp.categoria = 'CP') / NULLIF(SUM(l.tot::NUMERIC(18, 2)), 0), 0) AS cuota_cp
FROM raw.dcfpro l
LEFT JOIN mart.v_pbi_dim_partida dp ON dp.partida_id = NULLIF(l.paride, 0)
WHERE l.docide IN (
    SELECT e.documento_id
    FROM tesoreria.efectos e
    JOIN _dev_version v ON v.obra_id = e.obra_id AND v.concepto = 'COSTE'
    WHERE e.sentido = 'PAGO' AND e.documento_id IS NOT NULL
)
GROUP BY l.docide;
ANALYZE _dev_cuota_cp;

-- ---------------------------------------------------------------------------
-- 6 · el corte por (obra, concepto) y la frontera con la cartera
-- ---------------------------------------------------------------------------
TRUNCATE tesoreria.devengo_corte_obra;

INSERT INTO tesoreria.devengo_corte_obra (
    obra_id, empresa_id, clave_obra, concepto, version_master, tipo_master,
    mes_version, mes_ultimo_cierre, primer_mes_pendiente,
    num_versiones_pendientes, num_partidas, plan_desde_version,
    plan_intervalo, ejecutado_intervalo, plan_restante, pendiente,
    sobre_ejecutado, adelantado, retrasado, ejecutado_sin_plan,
    retraso_sin_perfil, real_origen_corte, plan_total, cartera_viva,
    cartera_emitida_tras_cierre, venta_real_origen_con_coeficientes,
    venta_real_media_obra, facturado_origen, venta_pendiente_facturar,
    facturado_por_delante, iva_pendiente_facturar_contrato,
    base_pendiente_facturar_sin_iva_contrato, retencion_pendiente_facturar_contrato,
    base_pendiente_facturar_sin_retencion_contrato, cartera_viva_coste_proporcional,
    cartera_emitida_tras_cierre_coste_proporcional
)
SELECT
    v.obra_id                                       AS obra_id,
    v.empresa_id                                    AS empresa_id,
    v.clave_obra                                    AS clave_obra,
    v.concepto                                      AS concepto,
    v.version_master                                AS version_master,
    v.tipo_master                                   AS tipo_master,
    v.mes_version                                   AS mes_version,
    v.mes_ultimo_cierre                             AS mes_ultimo_cierre,
    v.primer_mes_pendiente                          AS primer_mes_pendiente,
    v.num_versiones_pendientes                      AS num_versiones_pendientes,
    COALESCE(s.num_partidas, 0)                     AS num_partidas,
    COALESCE(s.plan_desde_version, 0)               AS plan_desde_version,
    COALESCE(s.plan_intervalo, 0)                   AS plan_intervalo,
    COALESCE(s.ejecutado_intervalo, 0)              AS ejecutado_intervalo,
    COALESCE(s.plan_restante, 0)                    AS plan_restante,
    COALESCE(s.pendiente, 0)                        AS pendiente,
    COALESCE(s.sobre_ejecutado, 0)                  AS sobre_ejecutado,
    COALESCE(s.adelantado, 0)                       AS adelantado,
    COALESCE(s.retrasado, 0)                        AS retrasado,
    COALESCE(sp.ejecutado_sin_plan, 0)              AS ejecutado_sin_plan,
    COALESCE(s.retraso_sin_perfil, 0)               AS retraso_sin_perfil,
    COALESCE(ro.real_origen_corte, 0)               AS real_origen_corte,
    COALESCE(s.plan_total, 0)                       AS plan_total,
    COALESCE(c.cartera_viva, 0)                     AS cartera_viva,
    COALESCE(c.cartera_emitida_tras_cierre, 0)      AS cartera_emitida_tras_cierre,
    hu.venta_real_origen_con_coeficientes           AS venta_real_origen_con_coeficientes,
    hu.venta_real_media_obra                        AS venta_real_media_obra,
    hu.facturado_origen                             AS facturado_origen,
    hu.venta_pendiente_facturar                     AS venta_pendiente_facturar,
    hu.facturado_por_delante                        AS facturado_por_delante,
    hu.iva_pendiente_facturar_contrato              AS iva_pendiente_facturar_contrato,
    hu.base_pendiente_facturar_sin_iva_contrato     AS base_pendiente_facturar_sin_iva_contrato,
    hu.retencion_pendiente_facturar_contrato        AS retencion_pendiente_facturar_contrato,
    hu.base_pendiente_facturar_sin_retencion_contrato AS base_pendiente_facturar_sin_retencion_contrato,
    CASE WHEN v.concepto = 'COSTE' THEN ROUND(COALESCE(c.cartera_viva_cp, 0), 2) END AS cartera_viva_coste_proporcional,
    CASE WHEN v.concepto = 'COSTE' THEN ROUND(COALESCE(c.cartera_emitida_tras_cierre_cp, 0), 2) END AS cartera_emitida_tras_cierre_coste_proporcional
FROM _dev_version v
LEFT JOIN (
    SELECT
        d.obra_id,
        d.concepto,
        COUNT(*) AS num_partidas,
        SUM(d.plan_desde_version) AS plan_desde_version,
        SUM(d.plan_intervalo) AS plan_intervalo,
        SUM(d.ejecutado_intervalo) AS ejecutado_intervalo,
        SUM(d.plan_restante) AS plan_restante,
        SUM(d.pendiente) AS pendiente,
        SUM(d.sobre_ejecutado) AS sobre_ejecutado,
        SUM(GREATEST(0, d.ejecutado_intervalo - d.plan_intervalo)) AS adelantado,
        SUM(GREATEST(0, d.plan_intervalo - d.ejecutado_intervalo)) AS retrasado,
        SUM(d.pendiente) FILTER (WHERE COALESCE(d.total_perfil, 0) <= 0) AS retraso_sin_perfil,
        SUM(d.plan_total) AS plan_total
    FROM _dev_partida d
    GROUP BY d.obra_id, d.concepto
) s ON s.obra_id = v.obra_id AND s.concepto = v.concepto
LEFT JOIN (
    -- Lo ejecutado en partidas que V no planifica: no tiene pendiente.
    SELECT r.obra_id, r.concepto, SUM(r.ejecutado_intervalo) AS ejecutado_sin_plan
    FROM _dev_ejecutado r
    WHERE NOT EXISTS (SELECT 1 FROM _dev_partida d WHERE d.obra_id = r.obra_id AND d.concepto = r.concepto AND d.partida_id = r.partida_id)
    GROUP BY r.obra_id, r.concepto
) sp ON sp.obra_id = v.obra_id AND sp.concepto = v.concepto
LEFT JOIN LATERAL (
    SELECT SUM(f.importe_mes) AS real_origen_corte
    FROM mart.fact_seguimiento_mensual f
    WHERE f.obra_id = v.obra_id AND f.concepto = v.concepto AND f.tipo_dato = 'REAL' AND f.anio_mes <= v.mes_ultimo_cierre
) ro ON TRUE
LEFT JOIN LATERAL (
    -- D16-A: la cartera del sentido del concepto, sin las bajas.
    SELECT
        SUM(e.importe) FILTER (WHERE e.estado_tesoreria = 'PREVISTO' AND NOT e.previsto_antiguo) AS cartera_viva,
        SUM(e.importe) FILTER (WHERE v.mes_ultimo_cierre IS NULL OR date_trunc('month', e.fecha_emision)::DATE > v.mes_ultimo_cierre) AS cartera_emitida_tras_cierre,
        -- N12: la parte CP de cada efecto, por la cuota de su factura (VENTA: no se publica).
        SUM(e.importe * COALESCE(q.cuota_cp, 0)) FILTER (WHERE e.estado_tesoreria = 'PREVISTO' AND NOT e.previsto_antiguo) AS cartera_viva_cp,
        SUM(e.importe * COALESCE(q.cuota_cp, 0)) FILTER (WHERE v.mes_ultimo_cierre IS NULL OR date_trunc('month', e.fecha_emision)::DATE > v.mes_ultimo_cierre) AS cartera_emitida_tras_cierre_cp
    FROM tesoreria.efectos e
    LEFT JOIN _dev_cuota_cp q ON q.documento_id = e.documento_id
    WHERE e.obra_id = v.obra_id
      AND e.sentido = CASE v.concepto WHEN 'COSTE' THEN 'PAGO' WHEN 'VENTA' THEN 'COBRO' END
      AND e.estado_tesoreria <> 'BAJA'
) c ON TRUE
LEFT JOIN _dev_hueco hu ON hu.obra_id = v.obra_id AND v.concepto = 'VENTA';

COMMENT ON TABLE tesoreria.devengo_pendiente_partida IS
'F-140. Por (obra, partida, concepto) con plan en la ultima version master (V): plan desde el mes de V, plan del intervalo (mes de V a ultimo cierre), ejecutado real del intervalo, plan restante tras el cierre, pendiente = max(0, plan desde V - ejecutado) y sobre_ejecutado. F-150, solo en VENTA: el contrato con el cliente de la partida (de la misma obra), su coeficiente de venta (el del contrato y, si no, el del master de V: certificacion 9 o venta 11; nunca una media de obra) con su fuente y el del master aparte, pendiente_con_coeficientes, y el IVA y la retencion del contrato con su fuente (CONTRATO o SIN). Devengo SIN IVA: no es caja. Clave: obra_id, partida_id, concepto.';

COMMENT ON TABLE tesoreria.devengo_pendiente_obra_mes IS
'F-140. El pendiente de cada partida repartido en proporcion a su plan restante (al centimo, el resto al ultimo mes; sin perfil, al primer mes pendiente y en importe_retraso_sin_perfil), por (obra, mes, concepto, categoria), con el plan restante de V. Suma = la de devengo_pendiente_partida. F-150, solo en VENTA: el pendiente con coeficientes repartido igual (y su cociente, solo para leer), el IVA y la retencion del contrato de cada partida sobre esa parte (redondeados al final) y las bases sin ellos, sobre las que van H12 y H10. Lo que lleva coeficientes no se suma con el coste ni con la venta sin ellos. Devengo SIN IVA: no es caja. Clave: obra_id, anio_mes, concepto, categoria.';

COMMENT ON TABLE tesoreria.devengo_corte_obra IS
'F-140. Por (obra, concepto): la version V, su mes, el ultimo cierre, las sumas de devengo_pendiente_partida con lo adelantado, lo retrasado, lo ejecutado sin plan de V y lo pendiente sin perfil, el real a origen hasta el cierre, el plan total de V y la frontera con tesoreria.efectos del sentido del concepto (cartera viva y emitida tras el cierre, CON IVA). F-150, solo en VENTA: el hueco de facturacion de H26, NETO POR OBRA: la venta real a origen con coeficientes (la de partidas sin coeficiente, con la media de la obra, declarada aparte) menos lo facturado (raw.dvf), con suelo 0, lo facturado por delante (que no se cobra) y el IVA y la retencion del hueco por el peso de cada contrato. F-150, solo en COSTE: la parte de coste proporcional (CP, estructura) de la cartera viva y de la emitida tras el cierre, por la categoria de las partidas de la factura de cada efecto; el CP no es caja de la obra y se resta. Clave: obra_id, concepto.';
