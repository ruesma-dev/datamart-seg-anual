-- etl_sigrid/infrastructure/postgres/sql/ventas/06b_retencion_cliente.sql
-- ============================================================================
-- F-104 · LA RETENCION DE CLIENTE, FACTURA A FACTURA (D10 = b, 2026-11-16).
-- En `ventas` (F-040) porque lee `ventas.facturas`; va antes de la guarda de
-- 07_guardas.sql, que asi ve tambien sus columnas.
--
-- `retenciones.v_cuadre_cliente` dice CUANTO descuadra cada cuenta de
-- retencion de cliente (manda la contabilidad); esto dice POR QUE:
--   ventas.retencion_factura   una fila por factura con retencion o efectos
--   ventas.retencion_cuenta    una fila por cuenta: el cuadre y su explicacion
--   ventas.v_retencion_cliente una fila por cliente (vista sobre las dos)
--
-- LA RETENCION DE LA FACTURA (D12 = a): la suma de sus recargos de
-- `raw.dvfrec` cuya cuenta (`cueide`) es de retencion de cliente
-- (`retenciones.cuentas_cliente`), SEA CUAL SEA SU CLASE: lo que ve la
-- contabilidad. Los tres grandes descuadres (ESPACIO 0686, LEVITT, MK MADRID
-- II) llevan la retencion como RETESP, no como garantia. La garantia y el
-- RETESP de `ventas.facturas` (clasificados por la funcion de clase de recargo
-- de 00_setup.sql, unico punto de la D4 de F-040) se copian como dos columnas
-- informativas: este fichero no clasifica recargos. Ningun recargo reparte
-- entre dos cuentas (medido el 2026-11-16): la cuenta de la factura es la de
-- su recargo y, sin recargo, la de su efecto.
--
-- LOS EFECTOS DE LA FACTURA: los de `retenciones.movimientos` CLIENTE con
-- `documento_id` = la factura, de los dos origenes de F-104, repartidos por su
-- `estado` (que aqui solo se lee). Lo BAJA va a `efectos_agrupada`: su dinero
-- cuenta en un AGR o un DIV sin documento, que NO se atribuye a la factura
-- (D11): se explica por cuenta, en `viva_sin_factura`.
--
-- `motivo`, en este orden: SIN_EFECTO, EFECTO_SIN_RETENCION, CUADRA
-- (|diferencia| < 0,01), DIFIERE y SIN_CUENTA_RETENCION (solo garantia o
-- RETESP que van a otra cuenta).
--
-- `diferencia_sin_explicar` de una cuenta = diferencia - (retencion de sus
-- facturas sin efecto - efectos vivos sin factura); NULL en CUADRA, donde las
-- facturas antiguas sin efecto, cobradas por asiento, no explican nada.
--
-- SON TABLAS, NO VISTAS (R34): `retenciones/01_movimientos.sql` tira cada
-- noche su tabla con CASCADE, y una vista de aqui encima desapareceria hasta el
-- siguiente `build_ventas`. `build_ventas` corre DESPUES de
-- `build_retenciones` en `run-all` (por posicion: el `depends_on` sigue siendo
-- `ingest_raw`). Si `retenciones` fallo esa noche, se lee la de la anterior.
--
-- Importes de `raw` en `double precision`: se castean a NUMERIC (sin redondear).
-- Sin columnas personales: ni el CIF ni prefijos de `ventas_restringida`.
--
-- Lee de: raw.dvfrec, raw.con, ventas.facturas, retenciones.cuentas_cliente,
--         retenciones.movimientos, retenciones.v_cuadre_cliente,
--         information_schema.columns.
-- Escribe en: ventas.retencion_factura, ventas.retencion_cuenta,
--             ventas.v_retencion_cliente.
-- ============================================================================

-- R33 · la guarda: lo que `build_retenciones` tiene que haber dejado, ANTES de
-- tirar nada de lo de la noche anterior
DO $$
BEGIN
    IF to_regclass('retenciones.v_cuadre_cliente') IS NULL
       OR NOT EXISTS (SELECT 1 FROM information_schema.columns
                      WHERE table_schema = 'retenciones' AND table_name = 'movimientos'
                        AND column_name = 'origen_retencion') THEN
        RAISE EXCEPTION 'F-104 R33: faltan retenciones.v_cuadre_cliente o la columna origen_retencion de retenciones.movimientos (build_retenciones de F-104 no ha corrido)';
    END IF;
END $$;

DROP VIEW IF EXISTS ventas.v_retencion_cliente CASCADE;
DROP TABLE IF EXISTS ventas.retencion_cuenta CASCADE;
DROP TABLE IF EXISTS ventas.retencion_factura CASCADE;

CREATE TABLE ventas.retencion_factura AS
WITH retencion AS (
    -- D12 = a: los recargos que van a una cuenta de retencion de cliente
    SELECT
        r.docide                        AS factura_id,
        SUM(r.cuo::NUMERIC(18, 2))      AS retencion,
        MIN(r.cueide)                   AS cuenta_id
    FROM raw.dvfrec r
    WHERE r.cueide IN (SELECT cuenta_id FROM retenciones.cuentas_cliente)
    GROUP BY r.docide
), efectos AS (
    SELECT
        m.documento_id                  AS factura_id,
        SUM(m.importe)                  AS efectos,
        COUNT(*)                        AS num_efectos,
        COALESCE(SUM(m.importe) FILTER (WHERE m.estado = 'VIVA'), 0) AS efectos_viva,
        COALESCE(SUM(m.importe) FILTER (WHERE m.estado = 'LIQUIDADA'), 0) AS efectos_liquidada,
        COALESCE(SUM(m.importe) FILTER (WHERE m.estado = 'BAJA'), 0) AS efectos_agrupada,
        MIN(m.cuenta_id)                AS cuenta_id
    FROM retenciones.movimientos m
    WHERE m.sentido = 'CLIENTE' AND m.documento_id IS NOT NULL
    GROUP BY m.documento_id
), x AS (
    SELECT
        f.factura_id                                    AS factura_id,
        f.codigo_factura                                AS codigo_factura,
        f.fecha_factura                                 AS fecha_factura,
        f.cliente_id                                    AS cliente_id,
        f.nombre_cliente                                AS nombre_cliente,
        f.obra_id                                       AS obra_id,
        f.codigo_obra                                   AS codigo_obra,
        COALESCE(rt.cuenta_id, ef.cuenta_id)            AS cuenta_id,
        COALESCE(rt.retencion, 0)::NUMERIC(18, 2)       AS retencion,
        f.retencion_garantia                            AS retencion_garantia,
        f.retencion_retesp                              AS retencion_retesp,
        COALESCE(ef.efectos, 0)::NUMERIC(18, 2)         AS efectos,
        COALESCE(ef.num_efectos, 0)                     AS num_efectos,
        COALESCE(ef.efectos_viva, 0)::NUMERIC(18, 2)    AS efectos_viva,
        COALESCE(ef.efectos_liquidada, 0)::NUMERIC(18, 2) AS efectos_liquidada,
        COALESCE(ef.efectos_agrupada, 0)::NUMERIC(18, 2) AS efectos_agrupada
    FROM ventas.facturas f
    LEFT JOIN retencion rt ON rt.factura_id = f.factura_id
    LEFT JOIN efectos ef ON ef.factura_id = f.factura_id
)
SELECT
    x.factura_id                AS factura_id,
    x.codigo_factura            AS codigo_factura,
    x.fecha_factura             AS fecha_factura,
    x.cliente_id                AS cliente_id,
    x.nombre_cliente            AS nombre_cliente,
    x.obra_id                   AS obra_id,
    x.codigo_obra               AS codigo_obra,
    x.cuenta_id                 AS cuenta_id,
    x.retencion                 AS retencion,
    x.retencion_garantia        AS retencion_garantia,
    x.retencion_retesp          AS retencion_retesp,
    x.efectos                   AS efectos,
    x.num_efectos               AS num_efectos,
    x.efectos_viva              AS efectos_viva,
    x.efectos_liquidada         AS efectos_liquidada,
    x.efectos_agrupada          AS efectos_agrupada,
    (x.retencion - x.efectos)::NUMERIC(18, 2) AS diferencia,
    (CASE WHEN x.num_efectos = 0 AND x.retencion <> 0 THEN 'SIN_EFECTO'
          WHEN x.num_efectos > 0 AND x.retencion = 0 THEN 'EFECTO_SIN_RETENCION'
          WHEN x.num_efectos > 0 AND abs(x.retencion - x.efectos) < 0.01 THEN 'CUADRA'
          WHEN x.num_efectos > 0 THEN 'DIFIERE'
          ELSE 'SIN_CUENTA_RETENCION' END)::VARCHAR(24) AS motivo
FROM x
WHERE x.retencion <> 0 OR x.retencion_garantia <> 0 OR x.retencion_retesp <> 0
   OR x.num_efectos > 0;

ALTER TABLE ventas.retencion_factura ADD PRIMARY KEY (factura_id);
CREATE INDEX IF NOT EXISTS idx_ven_retfac_cuenta  ON ventas.retencion_factura (cuenta_id);
CREATE INDEX IF NOT EXISTS idx_ven_retfac_cliente ON ventas.retencion_factura (cliente_id);

COMMENT ON TABLE ventas.retencion_factura IS
'F-104. Una fila por factura de venta con retencion, garantia o RETESP, o con efectos de retencion de cliente. retencion = recargos de raw.dvfrec a una cuenta de retencion de cliente, sea cual sea su clase (D12 = a; NO es la garantia de ventas.facturas, que va aparte con el RETESP, informativas). efectos: los de retenciones.movimientos CLIENTE de la factura, por estado (BAJA = efectos_agrupada: su dinero cuenta en un AGR o DIV que no se atribuye a la factura, D11). motivo: SIN_EFECTO, EFECTO_SIN_RETENCION, CUADRA, DIFIERE, SIN_CUENTA_RETENCION. Clave: factura_id.';


CREATE TABLE ventas.retencion_cuenta AS
WITH por_factura AS (
    SELECT
        rf.cuenta_id                                    AS cuenta_id,
        SUM(rf.retencion)                               AS retencion_facturas,
        COALESCE(SUM(rf.retencion) FILTER (WHERE rf.motivo = 'SIN_EFECTO'), 0) AS retencion_sin_efecto,
        COUNT(*) FILTER (WHERE rf.motivo = 'SIN_EFECTO') AS num_facturas_sin_efecto
    FROM ventas.retencion_factura rf
    WHERE rf.cuenta_id IS NOT NULL
    GROUP BY rf.cuenta_id
), sin_factura AS (
    -- Lo vivo de la cuenta que no apunta a ninguna factura: AGR, DIV, manuales
    SELECT m.cuenta_id AS cuenta_id, SUM(m.importe) AS viva_sin_factura
    FROM retenciones.movimientos m
    WHERE m.sentido = 'CLIENTE' AND m.estado = 'VIVA' AND m.documento_id IS NULL
      AND m.cuenta_id IS NOT NULL
    GROUP BY m.cuenta_id
), x AS (
    SELECT
        COALESCE(q.cuenta_id, pf.cuenta_id)                 AS cuenta_id,
        COALESCE(q.saldo_contable, 0)::NUMERIC(18, 2)       AS saldo_contable,
        COALESCE(q.viva_efectos, 0)::NUMERIC(18, 2)         AS viva_efectos,
        COALESCE(q.diferencia, 0)::NUMERIC(18, 2)           AS diferencia,
        q.categoria                                         AS categoria,
        COALESCE(pf.retencion_facturas, 0)::NUMERIC(18, 2)  AS retencion_facturas,
        COALESCE(pf.retencion_sin_efecto, 0)::NUMERIC(18, 2) AS retencion_sin_efecto,
        COALESCE(pf.num_facturas_sin_efecto, 0)             AS num_facturas_sin_efecto
    FROM retenciones.v_cuadre_cliente q
    FULL JOIN por_factura pf ON pf.cuenta_id = q.cuenta_id
), y AS (
    SELECT x.*, COALESCE(sf.viva_sin_factura, 0)::NUMERIC(18, 2) AS viva_sin_factura
    FROM x
    LEFT JOIN sin_factura sf ON sf.cuenta_id = x.cuenta_id
)
SELECT
    x.cuenta_id                 AS cuenta_id,
    cue.cod                     AS codigo_cuenta,
    cue.res                     AS nombre_cuenta,
    cc.cliente_id               AS cliente_id,
    cc.criterio_seleccion       AS criterio_seleccion,
    x.saldo_contable            AS saldo_contable,
    x.viva_efectos              AS viva_efectos,
    x.diferencia                AS diferencia,
    x.categoria                 AS categoria,
    x.retencion_facturas        AS retencion_facturas,
    x.retencion_sin_efecto      AS retencion_sin_efecto,
    x.num_facturas_sin_efecto   AS num_facturas_sin_efecto,
    x.viva_sin_factura          AS viva_sin_factura,
    (CASE WHEN x.categoria = 'CUADRA' THEN NULL
          ELSE x.diferencia - (x.retencion_sin_efecto - x.viva_sin_factura) END)::NUMERIC(18, 2)
                                AS diferencia_sin_explicar
FROM y x
LEFT JOIN raw.con cue ON cue.ide = x.cuenta_id
LEFT JOIN retenciones.cuentas_cliente cc ON cc.cuenta_id = x.cuenta_id;

ALTER TABLE ventas.retencion_cuenta ADD PRIMARY KEY (cuenta_id);
CREATE INDEX IF NOT EXISTS idx_ven_retcue_cliente ON ventas.retencion_cuenta (cliente_id);

COMMENT ON TABLE ventas.retencion_cuenta IS
'F-104. Una fila por cuenta de retencion de cliente de retenciones.v_cuadre_cliente o de ventas.retencion_factura: el cuadre (saldo contable, que manda, frente a efectos vivos; 0 y categoria NULL si la cuenta no esta en el cuadre) y su explicacion por factura: retencion de sus facturas, la de las que no tienen efecto, los efectos vivos sin factura (AGR, DIV, manuales) y diferencia_sin_explicar = diferencia - (retencion_sin_efecto - viva_sin_factura), NULL en CUADRA. Es la lista para Administracion (D8). Clave: cuenta_id.';


CREATE VIEW ventas.v_retencion_cliente AS
WITH fact AS (
    SELECT
        rf.cliente_id                                   AS cliente_id,
        MAX(rf.nombre_cliente)                          AS nombre_cliente,
        COUNT(*)                                        AS num_facturas,
        SUM(rf.retencion)                               AS retencion,
        SUM(rf.efectos)                                 AS efectos,
        COALESCE(SUM(rf.retencion) FILTER (WHERE rf.motivo = 'SIN_EFECTO'), 0) AS retencion_sin_efecto,
        COALESCE(SUM(rf.diferencia) FILTER (WHERE rf.motivo IN ('DIFIERE', 'EFECTO_SIN_RETENCION')), 0) AS diferencia_facturas
    FROM ventas.retencion_factura rf
    WHERE rf.cliente_id IS NOT NULL
    GROUP BY rf.cliente_id
), cta AS (
    SELECT
        rc.cliente_id                                   AS cliente_id,
        SUM(rc.saldo_contable)                          AS saldo_contable,
        SUM(rc.viva_efectos)                            AS viva_efectos,
        SUM(rc.diferencia)                              AS diferencia,
        SUM(rc.viva_sin_factura)                        AS viva_sin_factura,
        SUM(rc.diferencia_sin_explicar)                 AS diferencia_sin_explicar
    FROM ventas.retencion_cuenta rc
    WHERE rc.cliente_id IS NOT NULL
    GROUP BY rc.cliente_id
)
SELECT
    COALESCE(f.cliente_id, c.cliente_id)                AS cliente_id,
    f.nombre_cliente                                    AS nombre_cliente,
    COALESCE(f.num_facturas, 0)                         AS num_facturas,
    COALESCE(f.retencion, 0)::NUMERIC(18, 2)            AS retencion,
    COALESCE(f.efectos, 0)::NUMERIC(18, 2)              AS efectos,
    COALESCE(f.retencion_sin_efecto, 0)::NUMERIC(18, 2) AS retencion_sin_efecto,
    COALESCE(f.diferencia_facturas, 0)::NUMERIC(18, 2)  AS diferencia_facturas,
    COALESCE(c.saldo_contable, 0)::NUMERIC(18, 2)       AS saldo_contable,
    COALESCE(c.viva_efectos, 0)::NUMERIC(18, 2)         AS viva_efectos,
    COALESCE(c.diferencia, 0)::NUMERIC(18, 2)           AS diferencia,
    COALESCE(c.viva_sin_factura, 0)::NUMERIC(18, 2)     AS viva_sin_factura,
    c.diferencia_sin_explicar::NUMERIC(18, 2)           AS diferencia_sin_explicar
FROM fact f
FULL JOIN cta c ON c.cliente_id = f.cliente_id;

COMMENT ON VIEW ventas.v_retencion_cliente IS
'F-104. Una fila por cliente con facturas en ventas.retencion_factura o cuenta en ventas.retencion_cuenta: lo de sus facturas (retencion, efectos, la retencion sin efecto y la diferencia de las que DIFIEREN o no tienen retencion) y la suma de sus cuentas (saldo contable, efectos vivos, diferencia, vivo sin factura y lo sin explicar). Lee solo esas dos tablas. Una cuenta sin cliente (PREFIJO_43X8) solo esta en ventas.retencion_cuenta.';
