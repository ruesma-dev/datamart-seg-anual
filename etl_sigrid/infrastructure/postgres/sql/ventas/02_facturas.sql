-- etl_sigrid/infrastructure/postgres/sql/ventas/02_facturas.sql
-- ============================================================================
-- F-040 · VENTAS (3/8): ventas.facturas, ventas.factura_lineas y
-- ventas.factura_recargos (R9-R13).
--
-- GRANO: una fila por factura de venta de `raw.dvf` (`con` tipo 11, 15.734 el
-- 2026-11-07), por linea de `raw.dvfpro` y por recargo de `raw.dvfrec`. Sin
-- WHERE: rectificativas (`cla` 1024, en negativo) y anuladas incluidas; la
-- guarda de `07_guardas.sql` exige el mismo recuento que `raw` y la misma base.
--
-- EL CLIENTE (R9): nombre y CIF de `ventas.clientes`, el ACTUAL (`cli.raz`) y
-- con el CIF de la persona fisica YA anulado (R7). El nombre y el CIF de la
-- CABECERA de la factura (`entres`, `entcif`, distinto en 571 facturas por
-- renombres) y sus direcciones solo estan en
-- `ventas_restringida.factura_cabecera`: este fichero no los lee.
--
-- LA OBRA (R10): la del centro de coste (`maestro.centros_coste`) y, SOLO si
-- la factura no tiene centro, la de su cabecera (`dvf.obride`). Un centro que
-- no es obra deja la factura sin obra, como en `tesoreria.efectos`.
-- `obra_via` dice por donde: CENTRO, OBRA o NULL.
--
-- LOS RECARGOS (R11): se agregan por factura ANTES de unir y se reparten en
-- cuatro columnas que no se solapan, SOLO por `ventas.fn_clase_recargo` (el
-- unico punto de la decision D4): coeficientes (clase 0), garantia (hoy 4 y
-- 5), `RETESP` (clase 1, aparte mientras D4 no diga otra cosa) y otras.
--
-- PERSONA FISICA (R7; R2-b, enmienda del humano, 2026-11-10): la factura cuyo
-- cliente no esta en `raw.cli` (o sin cliente) se trata como persona fisica
-- (`persona_fisica_de_factura` del dominio): sin CIF ni descripcion en
-- `ventas`. Las cuenta `ventas.cobertura_enlace` (FACTURA_CLIENTE).
--
-- LAS LINEAS (R13): la descripcion libre de las de un cliente persona fisica
-- (o de una factura que no existe: falla cerrado) va a NULL; integra, en
-- `ventas_restringida.factura_lineas_persona`. La linea de certificacion de
-- origen exige que `linoriide` sea una linea de `cerpro` del documento de
-- origen `docoriide` (el tipo del destino no lo dice `linoriide`).
--
-- Importes de `raw` en `double precision`: se castean a NUMERIC (sin ROUND).
--
-- Lee de: raw.dvf, raw.dvfpro, raw.dvfrec, raw.con, raw.conest (tipo 11),
--         raw.obr, raw.cerpro, maestro.centros_coste y ventas.clientes.
-- Escribe en: ventas.facturas, ventas.factura_lineas, ventas.factura_recargos.
-- ============================================================================

DROP TABLE IF EXISTS ventas.factura_recargos CASCADE;
DROP TABLE IF EXISTS ventas.factura_lineas CASCADE;
DROP TABLE IF EXISTS ventas.facturas CASCADE;

CREATE TABLE ventas.facturas AS
WITH recargos AS (
    SELECT
        r.docide AS factura_id,
        COALESCE(SUM(r.cuo::NUMERIC(18, 2)) FILTER (WHERE ventas.fn_clase_recargo(r.reccla::INT) = 'COEFICIENTES'), 0) AS importe_coeficientes,
        COALESCE(SUM(r.cuo::NUMERIC(18, 2)) FILTER (WHERE ventas.fn_clase_recargo(r.reccla::INT) = 'GARANTIA'), 0) AS retencion_garantia,
        COALESCE(SUM(r.cuo::NUMERIC(18, 2)) FILTER (WHERE ventas.fn_clase_recargo(r.reccla::INT) = 'RETESP'), 0) AS retencion_retesp,
        COALESCE(SUM(r.cuo::NUMERIC(18, 2)) FILTER (WHERE ventas.fn_clase_recargo(r.reccla::INT) = 'OTRAS'), 0) AS retencion_otras
    FROM raw.dvfrec r
    GROUP BY r.docide
)
, lineas AS (
    SELECT l.docide AS factura_id, count(*) AS num_lineas
    FROM raw.dvfpro l
    GROUP BY l.docide
)
SELECT
    f.ide                                                   AS factura_id,
    c.cod                                                   AS codigo_factura,
    c.emp                                                   AS empresa_id,
    ventas.fn_fecha(f.fecdoc)                               AS fecha_factura,
    f.cla                                                   AS clase,
    c.est                                                   AS estado_codigo,
    ce.res                                                  AS estado_sigrid,
    (COALESCE(c.fecbaj, 0) <> 0)                            AS anulada,
    NULLIF(f.entide, 0)                                     AS cliente_id,
    vc.nombre                                               AS nombre_cliente,
    vc.cif                                                  AS cif_cliente,
    COALESCE(vc.es_persona_fisica, TRUE)                    AS es_persona_fisica,
    COALESCE(cc.obra_id, ob.ide)                            AS obra_id,
    COALESCE(cc.codigo_obra, obc.cod)                       AS codigo_obra,
    CASE WHEN cc.obra_id IS NOT NULL THEN 'CENTRO'
         WHEN ob.ide IS NOT NULL THEN 'OBRA' END            AS obra_via,
    NULLIF(f.ctride, 0)                                     AS contrato_id,
    kc.res                                                  AS contrato_nombre,
    COALESCE(f.totbas, 0)::NUMERIC(18, 2)                   AS base,
    COALESCE(f.totiva, 0)::NUMERIC(18, 2)                   AS iva,
    COALESCE(f.totdoc, 0)::NUMERIC(18, 2)                   AS total_sin_retencion,
    COALESCE(f.tot, 0)::NUMERIC(18, 2)                      AS total,
    COALESCE(f.totpag, 0)::NUMERIC(18, 2)                   AS a_cobrar,
    COALESCE(rc.importe_coeficientes, 0)                    AS importe_coeficientes,
    COALESCE(rc.retencion_garantia, 0)                      AS retencion_garantia,
    COALESCE(rc.retencion_retesp, 0)                        AS retencion_retesp,
    COALESCE(rc.retencion_otras, 0)                         AS retencion_otras,
    COALESCE(ln.num_lineas, 0)                              AS num_lineas
FROM raw.dvf f
LEFT JOIN raw.con c ON c.ide = f.ide
-- El estado se traduce con el tipo de la factura de venta (11): 1 Pendiente
-- de emision, 2 Emitida, 4 Comprobada, 10 Contabilizada.
LEFT JOIN raw.conest ce ON ce.tip = 11 AND ce.est = c.est
LEFT JOIN ventas.clientes vc ON vc.cliente_id = NULLIF(f.entide, 0)
LEFT JOIN maestro.centros_coste cc ON cc.centro_coste_id = NULLIF(f.cenide, 0)
-- La cabecera solo decide si la factura NO tiene centro de coste (R10).
LEFT JOIN raw.obr ob ON ob.ide = NULLIF(f.obride, 0) AND COALESCE(f.cenide, 0) = 0
LEFT JOIN raw.con obc ON obc.ide = ob.ide
LEFT JOIN raw.con kc ON kc.ide = NULLIF(f.ctride, 0)
LEFT JOIN recargos rc ON rc.factura_id = f.ide
LEFT JOIN lineas ln ON ln.factura_id = f.ide;

ALTER TABLE ventas.facturas ADD PRIMARY KEY (factura_id);
CREATE INDEX IF NOT EXISTS idx_ven_fac_cliente ON ventas.facturas (cliente_id);
CREATE INDEX IF NOT EXISTS idx_ven_fac_obra    ON ventas.facturas (obra_id);

COMMENT ON TABLE ventas.facturas IS
'F-040. Una fila por factura de venta (raw.dvf, con tipo 11): codigo, empresa, fecha, clase (1024 rectificativa, en negativo), estado (conest tipo 11), anulada (fecbaj), el cliente ACTUAL (nombre publico; cif_cliente NULL si es persona fisica), la obra (centro de coste y, sin centro, la cabecera; obra_via), el contrato de venta, base, IVA, total sin retencion, total y a cobrar, y los recargos en cuatro columnas que no se solapan: importe_coeficientes (clase 0), retencion_garantia (clases de garantia, hoy 4 y 5, provisional D4), retencion_retesp (clase 1) y retencion_otras. Sin direcciones ni el CIF de la cabecera: ventas_restringida.factura_cabecera. Clave: factura_id.';

CREATE TABLE ventas.factura_lineas AS
SELECT
    l.ide                                                   AS linea_id,
    l.docide                                                AS factura_id,
    l.pos                                                   AS posicion,
    CASE WHEN COALESCE(f.es_persona_fisica, TRUE) THEN NULL ELSE l.res END AS descripcion,
    COALESCE(l.can, 0)::NUMERIC(18, 4)                      AS cantidad,
    COALESCE(l.pre, 0)::NUMERIC(18, 4)                      AS precio,
    COALESCE(l.tot, 0)::NUMERIC(18, 2)                      AS importe,
    NULLIF(l.ivaide, 0)                                     AS iva_id,
    COALESCE(l.ivacuo, 0)::NUMERIC(18, 2)                   AS iva_cuota,
    NULLIF(l.obride, 0)                                     AS obra_id,
    NULLIF(l.paride, 0)                                     AS partida_id,
    l.unimed                                                AS unidad,
    cp.ide                                                  AS linea_certificacion_id
FROM raw.dvfpro l
LEFT JOIN ventas.facturas f ON f.factura_id = l.docide
LEFT JOIN raw.cerpro cp ON cp.ide = NULLIF(l.linoriide, 0) AND cp.docide = NULLIF(l.docoriide, 0);

ALTER TABLE ventas.factura_lineas ADD PRIMARY KEY (linea_id);
CREATE INDEX IF NOT EXISTS idx_ven_lin_factura ON ventas.factura_lineas (factura_id);

COMMENT ON TABLE ventas.factura_lineas IS
'F-040. Una fila por linea de factura de venta (raw.dvfpro): factura, posicion, descripcion (NULL si el cliente es persona fisica; integra en ventas_restringida.factura_lineas_persona), cantidad, precio, importe sin IVA, IVA, obra, partida, unidad y la linea de certificacion de origen (cerpro). Clave: linea_id.';

CREATE TABLE ventas.factura_recargos AS
SELECT
    r.ide                                                   AS recargo_linea_id,
    r.docide                                                AS factura_id,
    NULLIF(r.recide, 0)                                     AS recargo_id,
    rc.cod                                                  AS codigo_recargo,
    rc.res                                                  AS nombre_recargo,
    r.reccla                                                AS clase,
    ventas.fn_clase_recargo(r.reccla::INT) AS clase_recargo,
    (ventas.fn_clase_recargo(r.reccla::INT) = 'GARANTIA') AS es_garantia,
    COALESCE(r.bas, 0)::NUMERIC(18, 2)                      AS base,
    COALESCE(r.valpor, 0)::NUMERIC(9, 4)                    AS porcentaje,
    COALESCE(r.cuo, 0)::NUMERIC(18, 2)                      AS importe
FROM raw.dvfrec r
LEFT JOIN raw.con rc ON rc.ide = NULLIF(r.recide, 0);

ALTER TABLE ventas.factura_recargos ADD PRIMARY KEY (recargo_linea_id);
CREATE INDEX IF NOT EXISTS idx_ven_rec_factura ON ventas.factura_recargos (factura_id);

COMMENT ON TABLE ventas.factura_recargos IS
'F-040. Una fila por recargo de factura de venta (raw.dvfrec): el recargo (codigo y nombre de raw.con), su clase de Sigrid, clase_recargo (COEFICIENTES, GARANTIA, RETESP u OTRAS, la de ventas.fn_clase_recargo) y es_garantia, base, porcentaje e importe (cuota). Clave: recargo_linea_id.';
