-- etl_sigrid/infrastructure/postgres/sql/ventas/03_certificaciones.sql
-- ============================================================================
-- F-040 · VENTAS (4/8): ventas.certificaciones y ventas.certificacion_recargos
-- (R14-R15).
--
-- GRANO: una fila por certificacion de `raw.cer` (`con` tipo 54, 6.308 el
-- 2026-11-06) y por recargo de `raw.cerrec`. Sin WHERE: los borradores
-- (estado 1, Pendiente de emision) tambien, marcados con `cuenta` = FALSE.
-- `obrcer` esta vacia en Sigrid: la certificacion vive aqui.
--
-- TRES IMPORTES QUE NO SON EL MISMO (R15):
--   * `importe_a_cuenta`: lo certificado en el PERIODO, sin recargos
--     (Σ `cerpro.tot`).
--   * `importe_a_origen` / `importe_anterior`: Σ `cerpro.imporiori` /
--     `imporiant`, lo que Sigrid guarda en la linea (a origen en 5.993 lineas).
--   * `base`: la cabecera `totbas`, que es la linea MAS los recargos de clase 0
--     (coeficientes) en el 85 %. NO se mezcla con el a cuenta.
--   `base_origen_contrato`: la suma acumulada de `base` de su contrato, por
--   (`numero`, `certificacion_id`), SOLO con las certificaciones que cuentan
--   (estados 2, 3 y 4); NULL en las que no cuentan y en las sin contrato.
--
-- LA OBRA: la de la cabecera (`cer.obride`, en el 100 %) y, si no, la del
-- centro de coste. El contrato de venta, de `raw.obrctr`.
-- Las lineas y los recargos se agregan ANTES de unir; los recargos se
-- reparten SOLO por `ventas.fn_clase_recargo` (R11). Importes de `raw` en
-- `double precision`: se castean a NUMERIC (sin ROUND).
--
-- Lee de: raw.cer, raw.cerpro, raw.cerrec, raw.con, raw.conest (tipo 54),
--         raw.obr, raw.obrctr, maestro.centros_coste y ventas.clientes.
-- Escribe en: ventas.certificaciones, ventas.certificacion_recargos.
-- ============================================================================

DROP TABLE IF EXISTS ventas.certificacion_recargos CASCADE;
DROP TABLE IF EXISTS ventas.certificaciones CASCADE;

CREATE TABLE ventas.certificaciones AS
WITH lineas AS (
    SELECT
        p.docide                                            AS certificacion_id,
        count(*)                                            AS num_lineas,
        SUM(COALESCE(p.tot, 0)::NUMERIC(18, 2)) AS importe_a_cuenta,
        SUM(COALESCE(p.imporiori, 0)::NUMERIC(18, 2)) AS importe_a_origen,
        SUM(COALESCE(p.imporiant, 0)::NUMERIC(18, 2)) AS importe_anterior
    FROM raw.cerpro p
    GROUP BY p.docide
)
, recargos AS (
    SELECT
        r.docide AS certificacion_id,
        COALESCE(SUM(r.cuo::NUMERIC(18, 2)) FILTER (WHERE ventas.fn_clase_recargo(r.reccla::INT) = 'COEFICIENTES'), 0) AS importe_coeficientes,
        COALESCE(SUM(r.cuo::NUMERIC(18, 2)) FILTER (WHERE ventas.fn_clase_recargo(r.reccla::INT) = 'GARANTIA'), 0) AS retencion_garantia,
        COALESCE(SUM(r.cuo::NUMERIC(18, 2)) FILTER (WHERE ventas.fn_clase_recargo(r.reccla::INT) = 'RETESP'), 0) AS retencion_retesp,
        COALESCE(SUM(r.cuo::NUMERIC(18, 2)) FILTER (WHERE ventas.fn_clase_recargo(r.reccla::INT) = 'OTRAS'), 0) AS retencion_otras
    FROM raw.cerrec r
    GROUP BY r.docide
)
, base AS (
    SELECT
        k.ide                                               AS certificacion_id,
        c.cod                                               AS codigo_certificacion,
        k.fas                                               AS numero,
        date_trunc('month', ventas.fn_fecha(k.fecdoc))::DATE AS mes,
        ventas.fn_fecha(k.fecdoc)                           AS fecha_certificacion,
        c.emp                                               AS empresa_id,
        COALESCE(ob.ide, cc.obra_id)                        AS obra_id,
        COALESCE(obc.cod, cc.codigo_obra)                   AS codigo_obra,
        NULLIF(k.ctride, 0)                                 AS contrato_id,
        kc.res                                              AS contrato_nombre,
        NULLIF(k.entide, 0)                                 AS cliente_id,
        vc.nombre                                           AS nombre_cliente,
        c.est                                               AS estado_codigo,
        ce.res                                              AS estado_sigrid,
        COALESCE(c.est IN (2, 3, 4), FALSE)                 AS cuenta,
        (COALESCE(k.estfac, 0) <> 0)                        AS facturada,
        NULLIF(k.docoriide, 0)                              AS certificacion_anterior_id,
        COALESCE(ln.importe_a_cuenta, 0)                    AS importe_a_cuenta,
        COALESCE(ln.importe_a_origen, 0)                    AS importe_a_origen,
        COALESCE(ln.importe_anterior, 0)                    AS importe_anterior,
        COALESCE(k.totbas, 0)::NUMERIC(18, 2)               AS base,
        COALESCE(k.totiva, 0)::NUMERIC(18, 2)               AS iva,
        COALESCE(k.totdoc, 0)::NUMERIC(18, 2)               AS total,
        COALESCE(ln.num_lineas, 0)                          AS num_lineas
    FROM raw.cer k
    LEFT JOIN raw.con c ON c.ide = k.ide
    -- Tipo 54: 1 Pendiente de emision, 2 Aprobada por gerencia, 3 Emitida,
    -- 4 Aprobada por propiedad.
    LEFT JOIN raw.conest ce ON ce.tip = 54 AND ce.est = c.est
    LEFT JOIN raw.obr ob ON ob.ide = NULLIF(k.obride, 0)
    LEFT JOIN raw.con obc ON obc.ide = ob.ide
    LEFT JOIN maestro.centros_coste cc ON cc.centro_coste_id = NULLIF(k.cenide, 0)
    LEFT JOIN raw.obrctr oc ON oc.ide = NULLIF(k.ctride, 0)
    LEFT JOIN raw.con kc ON kc.ide = oc.ide
    LEFT JOIN ventas.clientes vc ON vc.cliente_id = NULLIF(k.entide, 0)
    LEFT JOIN lineas ln ON ln.certificacion_id = k.ide
)
SELECT
    b.certificacion_id                                      AS certificacion_id,
    b.codigo_certificacion                                  AS codigo_certificacion,
    b.numero                                                AS numero,
    b.mes                                                   AS mes,
    b.fecha_certificacion                                   AS fecha_certificacion,
    b.empresa_id                                            AS empresa_id,
    b.obra_id                                               AS obra_id,
    b.codigo_obra                                           AS codigo_obra,
    b.contrato_id                                           AS contrato_id,
    b.contrato_nombre                                       AS contrato_nombre,
    b.cliente_id                                            AS cliente_id,
    b.nombre_cliente                                        AS nombre_cliente,
    b.estado_codigo                                         AS estado_codigo,
    b.estado_sigrid                                         AS estado_sigrid,
    b.cuenta                                                AS cuenta,
    b.facturada                                             AS facturada,
    b.certificacion_anterior_id                             AS certificacion_anterior_id,
    b.importe_a_cuenta                                      AS importe_a_cuenta,
    b.importe_a_origen                                      AS importe_a_origen,
    b.importe_anterior                                      AS importe_anterior,
    b.base                                                  AS base,
    b.iva                                                   AS iva,
    b.total                                                 AS total,
    CASE WHEN b.cuenta AND b.contrato_id IS NOT NULL THEN SUM(b.base) FILTER (WHERE b.cuenta) OVER (PARTITION BY b.contrato_id ORDER BY b.numero, b.certificacion_id) END AS base_origen_contrato,
    COALESCE(rc.importe_coeficientes, 0)                    AS importe_coeficientes,
    COALESCE(rc.retencion_garantia, 0)                      AS retencion_garantia,
    COALESCE(rc.retencion_retesp, 0)                        AS retencion_retesp,
    COALESCE(rc.retencion_otras, 0)                         AS retencion_otras,
    b.num_lineas                                            AS num_lineas
FROM base b
LEFT JOIN recargos rc ON rc.certificacion_id = b.certificacion_id;

ALTER TABLE ventas.certificaciones ADD PRIMARY KEY (certificacion_id);
CREATE INDEX IF NOT EXISTS idx_ven_cer_obra     ON ventas.certificaciones (obra_id);
CREATE INDEX IF NOT EXISTS idx_ven_cer_contrato ON ventas.certificaciones (contrato_id);

COMMENT ON TABLE ventas.certificaciones IS
'F-040. Una fila por certificacion de obra (raw.cer, con tipo 54): codigo, numero (fas), mes, fecha, empresa, obra, contrato de venta, cliente, estado (conest tipo 54), cuenta (estados 2, 3 y 4; el 1 es borrador), facturada (estfac) y la anterior del contrato. Importes: a cuenta (lineas del periodo, sin recargos), a origen y anterior (de las lineas), base (cabecera, con los coeficientes), IVA, total, base_origen_contrato (acumulada de las que cuentan) y los recargos en cuatro columnas que no se solapan. Certificado no es facturado ni cobrado (R-VENTAS-TRES-CIFRAS). Clave: certificacion_id.';

CREATE TABLE ventas.certificacion_recargos AS
SELECT
    r.ide                                                   AS recargo_linea_id,
    r.docide                                                AS certificacion_id,
    NULLIF(r.recide, 0)                                     AS recargo_id,
    rc.cod                                                  AS codigo_recargo,
    rc.res                                                  AS nombre_recargo,
    r.reccla                                                AS clase,
    ventas.fn_clase_recargo(r.reccla::INT) AS clase_recargo,
    (ventas.fn_clase_recargo(r.reccla::INT) = 'GARANTIA') AS es_garantia,
    COALESCE(r.bas, 0)::NUMERIC(18, 2)                      AS base,
    COALESCE(r.valpor, 0)::NUMERIC(9, 4)                    AS porcentaje,
    COALESCE(r.cuo, 0)::NUMERIC(18, 2)                      AS importe
FROM raw.cerrec r
LEFT JOIN raw.con rc ON rc.ide = NULLIF(r.recide, 0);

ALTER TABLE ventas.certificacion_recargos ADD PRIMARY KEY (recargo_linea_id);
CREATE INDEX IF NOT EXISTS idx_ven_crec_cert ON ventas.certificacion_recargos (certificacion_id);

COMMENT ON TABLE ventas.certificacion_recargos IS
'F-040. Una fila por recargo de certificacion (raw.cerrec): el recargo (codigo y nombre de raw.con), su clase de Sigrid, clase_recargo (COEFICIENTES, GARANTIA, RETESP u OTRAS) y es_garantia, base, porcentaje e importe (cuota). Clave: recargo_linea_id.';
