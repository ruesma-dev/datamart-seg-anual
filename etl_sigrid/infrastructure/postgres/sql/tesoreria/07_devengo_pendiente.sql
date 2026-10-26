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
-- Las tablas de trabajo son temporales y mueren con la transaccion. Si algo
-- falla, quedan las tablas de ayer. Cada una lleva su `ANALYZE`: sin
-- estadisticas el planificador las cree de una fila y cruza el perfil con las
-- partidas en bucle (medido en solo lectura el 2026-10-25: 875 s frente a
-- ~210 s sin bucles; el paso 1 solo, 70 s).
--
-- Lee de: mart.fact_seguimiento_mensual, mart.master_versiones_tipadas,
--         mart.v_pbi_dim_partida, stg.plan_mensual, maestro.v_obra_fichas,
--         tesoreria.efectos.
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
       OR to_regclass('tesoreria.efectos') IS NULL THEN
        RAISE EXCEPTION 'devengo_pendiente: falta una fuente (mart, stg, maestro o tesoreria.efectos)';
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
-- 4 · la partida: pendiente y sobre-ejecutado
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE _dev_partida ON COMMIT DROP AS
SELECT
    d.*,
    GREATEST(0, d.plan_desde_version - d.ejecutado_intervalo) AS pendiente,
    GREATEST(0, d.ejecutado_intervalo - d.plan_desde_version) AS sobre_ejecutado
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
) d;
ANALYZE _dev_partida;

TRUNCATE tesoreria.devengo_pendiente_partida;

INSERT INTO tesoreria.devengo_pendiente_partida (
    obra_id, empresa_id, clave_obra, partida_id, codigo_partida, concepto,
    categoria, version_master, tipo_master, mes_version, mes_ultimo_cierre,
    plan_desde_version, plan_intervalo, ejecutado_intervalo, plan_restante,
    pendiente, sobre_ejecutado
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
    d.sobre_ejecutado        AS sobre_ejecutado
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
        CASE WHEN r.desde_el_final = 1 THEN r.pendiente - (r.suma_partes - r.parte) ELSE r.parte END AS importe
    FROM (
        SELECT x.*, SUM(x.parte) OVER (PARTITION BY x.obra_id, x.concepto, x.partida_id) AS suma_partes
        FROM partes x
    ) r
)
, sin_perfil AS (
    -- D19-A: sin perfil restante, al primer mes pendiente y marcado.
    SELECT d.obra_id, d.concepto, d.partida_id, v.primer_mes_pendiente AS anio_mes, d.pendiente AS importe, TRUE AS es_retraso
    FROM _dev_partida d
    JOIN _dev_version v ON v.obra_id = d.obra_id AND v.concepto = d.concepto
    WHERE d.pendiente > 0 AND COALESCE(d.total_perfil, 0) <= 0
)
SELECT pr.obra_id, pr.concepto, pr.partida_id, pr.anio_mes,
       pr.importe_mes AS plan_restante, 0::NUMERIC AS pendiente, 0::NUMERIC AS retraso_sin_perfil
FROM perfil pr
UNION ALL
SELECT r.obra_id, r.concepto, r.partida_id, r.anio_mes, 0::NUMERIC, r.importe, 0::NUMERIC
FROM repartido r
UNION ALL
SELECT s.obra_id, s.concepto, s.partida_id, s.anio_mes, 0::NUMERIC, s.importe, s.importe
FROM sin_perfil s;
ANALYZE _dev_reparto;

TRUNCATE tesoreria.devengo_pendiente_obra_mes;

INSERT INTO tesoreria.devengo_pendiente_obra_mes (
    obra_id, empresa_id, clave_obra, anio_mes, concepto, categoria,
    version_master, mes_ultimo_cierre, importe_plan_restante,
    importe_pendiente, importe_retraso_sin_perfil, num_partidas,
    mes_pasado_sin_cierre
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
    x.anio_mes < date_trunc('month', CURRENT_DATE)::DATE AS mes_pasado_sin_cierre
FROM (
    SELECT
        r.obra_id,
        r.concepto,
        r.anio_mes,
        dp.categoria,
        SUM(r.plan_restante) AS importe_plan_restante,
        SUM(r.pendiente) AS importe_pendiente,
        SUM(r.retraso_sin_perfil) AS importe_retraso_sin_perfil,
        COUNT(DISTINCT r.partida_id) AS num_partidas
    FROM _dev_reparto r
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
           m.total AS total_mes
      INTO fallo
      FROM (SELECT obra_id, concepto, SUM(pendiente) AS total
              FROM tesoreria.devengo_pendiente_partida GROUP BY obra_id, concepto) p
      FULL JOIN (SELECT obra_id, concepto, SUM(importe_pendiente) AS total
                   FROM tesoreria.devengo_pendiente_obra_mes GROUP BY obra_id, concepto) m
        ON m.obra_id = p.obra_id AND m.concepto = p.concepto
     WHERE COALESCE(p.total, 0) IS DISTINCT FROM COALESCE(m.total, 0)
     LIMIT 1;
    IF FOUND THEN
        RAISE EXCEPTION 'devengo_pendiente: el reparto de la obra % (%) suma % y la partida %',
            fallo.obra_id, fallo.concepto, fallo.total_mes, fallo.total_partida;
    END IF;
END $$;

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
    cartera_emitida_tras_cierre
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
    COALESCE(c.cartera_emitida_tras_cierre, 0)      AS cartera_emitida_tras_cierre
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
        SUM(e.importe) FILTER (WHERE v.mes_ultimo_cierre IS NULL OR date_trunc('month', e.fecha_emision)::DATE > v.mes_ultimo_cierre) AS cartera_emitida_tras_cierre
    FROM tesoreria.efectos e
    WHERE e.obra_id = v.obra_id
      AND e.sentido = CASE v.concepto WHEN 'COSTE' THEN 'PAGO' WHEN 'VENTA' THEN 'COBRO' END
      AND e.estado_tesoreria <> 'BAJA'
) c ON TRUE;

COMMENT ON TABLE tesoreria.devengo_pendiente_partida IS
'F-140. Por (obra, partida, concepto) con plan en la ultima version master (V): plan desde el mes de V, plan del intervalo (mes de V a ultimo cierre), ejecutado real del intervalo, plan restante tras el cierre, pendiente = max(0, plan desde V - ejecutado) y sobre_ejecutado. Devengo SIN IVA: no es caja. Clave: obra_id, partida_id, concepto.';

COMMENT ON TABLE tesoreria.devengo_pendiente_obra_mes IS
'F-140. El pendiente de cada partida repartido en proporcion a su plan restante (al centimo, el resto al ultimo mes; sin perfil, al primer mes pendiente y en importe_retraso_sin_perfil), por (obra, mes, concepto, categoria), con el plan restante de V. Suma = la de devengo_pendiente_partida. Devengo SIN IVA: no es caja. Clave: obra_id, anio_mes, concepto, categoria.';

COMMENT ON TABLE tesoreria.devengo_corte_obra IS
'F-140. Por (obra, concepto): la version V, su mes, el ultimo cierre, las sumas de devengo_pendiente_partida con lo adelantado, lo retrasado, lo ejecutado sin plan de V y lo pendiente sin perfil, el real a origen hasta el cierre, el plan total de V y la frontera con tesoreria.efectos del sentido del concepto (cartera viva y emitida tras el cierre, CON IVA). Clave: obra_id, concepto.';
