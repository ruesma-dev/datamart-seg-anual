-- etl_sigrid/infrastructure/postgres/sql/compras/02_fact_linea.sql
-- ============================================================================
-- compras.fact_compras_linea — hechos unificados de compra a nivel de LÍNEA.
--
-- Grano: una fila por línea de documento (contrato / albarán / proforma /
-- nota / factura / abono). Todos los importes SIN IVA.
--
-- Para contratos la obra viene de la cabecera; para albaranes y facturas,
-- de la propia línea (con fallback a la obra del contrato enlazado).
-- ============================================================================

DROP TABLE IF EXISTS compras.fact_compras_linea CASCADE;
CREATE TABLE compras.fact_compras_linea AS

-- Líneas de CONTRATO
SELECT
    'CONTRATO'::VARCHAR(10)         AS tipo_doc,
    c.serie                         AS serie,
    l.linea_id                      AS linea_id,
    c.contrato_id                   AS documento_id,
    c.codigo_contrato               AS codigo_documento,
    c.fecha                         AS fecha,
    EXTRACT(YEAR FROM c.fecha)::INT AS anio,
    c.obra_id                       AS obra_id,
    c.codigo_obra                   AS codigo_obra,
    c.proveedor_id                  AS proveedor_id,
    c.proveedor_nombre              AS proveedor_nombre,
    c.proveedor_cif                 AS proveedor_cif,
    l.partida_id                    AS partida_id,
    l.producto_id                   AS producto_id,
    l.descripcion                   AS descripcion,
    l.cantidad                      AS cantidad,
    l.precio                        AS precio,
    l.importe                       AS importe,
    NULL::NUMERIC(18,2)             AS importe_pendiente_facturar,
    c.contrato_id                   AS contrato_id,
    c.codigo_contrato               AS codigo_contrato
FROM compras.contrato_lineas l
JOIN compras.contratos c ON c.contrato_id = l.contrato_id

UNION ALL

-- Líneas de ALBARÁN / PROFORMA / NOTA
SELECT
    a.tipo_documento::VARCHAR(10)   AS tipo_doc,
    a.serie,
    l.linea_id,
    a.albaran_id                    AS documento_id,
    a.codigo_albaran                AS codigo_documento,
    a.fecha,
    EXTRACT(YEAR FROM a.fecha)::INT AS anio,
    COALESCE(l.obra_id, ctr.obra_id)        AS obra_id,
    COALESCE(obr_con.cod, ctr.codigo_obra)  AS codigo_obra,
    a.proveedor_id,
    a.proveedor_nombre,
    a.proveedor_cif,
    l.partida_id,
    l.producto_id,
    l.descripcion,
    l.cantidad,
    l.precio,
    l.importe,
    l.importe_pendiente_facturar,
    COALESCE(a.contrato_id, l.contrato_id_linea) AS contrato_id,
    ctr.codigo_contrato
FROM compras.albaran_lineas l
JOIN compras.albaranes a  ON a.albaran_id = l.albaran_id
LEFT JOIN raw.con obr_con ON obr_con.ide = l.obra_id
LEFT JOIN compras.contratos ctr
       ON ctr.contrato_id = COALESCE(a.contrato_id, l.contrato_id_linea)

UNION ALL

-- Líneas de FACTURA / ABONO
SELECT
    f.tipo_documento::VARCHAR(10)   AS tipo_doc,
    f.serie,
    l.linea_id,
    f.factura_id                    AS documento_id,
    f.codigo_factura                AS codigo_documento,
    f.fecha,
    EXTRACT(YEAR FROM f.fecha)::INT AS anio,
    COALESCE(l.obra_id, alb_l.obra_id, ctr.obra_id)       AS obra_id,
    COALESCE(obr_con.cod, obr_con2.cod, ctr.codigo_obra)  AS codigo_obra,
    f.proveedor_id,
    f.proveedor_nombre,
    f.proveedor_cif,
    COALESCE(l.partida_id, alb_l.partida_id)              AS partida_id,
    l.producto_id,
    l.descripcion,
    l.cantidad,
    l.precio,
    l.importe,
    NULL::NUMERIC(18,2)             AS importe_pendiente_facturar,
    -- Contrato: directo (docoritip=44) o heredado del albarán facturado
    COALESCE(l.contrato_id_directo, alb.contrato_id,
             alb_l.contrato_id_linea)                      AS contrato_id,
    ctr.codigo_contrato
FROM compras.factura_lineas l
JOIN compras.facturas f          ON f.factura_id = l.factura_id
LEFT JOIN compras.albaran_lineas alb_l ON alb_l.linea_id = l.albaran_linea_id
LEFT JOIN compras.albaranes alb        ON alb.albaran_id = alb_l.albaran_id
LEFT JOIN raw.con obr_con  ON obr_con.ide  = l.obra_id
LEFT JOIN raw.con obr_con2 ON obr_con2.ide = alb_l.obra_id
LEFT JOIN compras.contratos ctr
       ON ctr.contrato_id = COALESCE(l.contrato_id_directo, alb.contrato_id,
                                     alb_l.contrato_id_linea);

CREATE INDEX idx_fcl_tipo     ON compras.fact_compras_linea (tipo_doc);
CREATE INDEX idx_fcl_obra     ON compras.fact_compras_linea (obra_id);
CREATE INDEX idx_fcl_prv      ON compras.fact_compras_linea (proveedor_id);
CREATE INDEX idx_fcl_partida  ON compras.fact_compras_linea (partida_id);
CREATE INDEX idx_fcl_contrato ON compras.fact_compras_linea (contrato_id);
CREATE INDEX idx_fcl_anio     ON compras.fact_compras_linea (anio);

COMMENT ON TABLE compras.fact_compras_linea IS
'Hechos de compra a nivel de línea (Tanda C2). tipo_doc: CONTRATO / ALBARAN / '
'PROFORMA / NOTA / FACTURA / ABONO / OTRO. Importes SIN IVA. Los abonos entran '
'con su signo natural (negativo). La obra/partida de facturas hereda de la '
'línea de albarán origen cuando la factura no la informa.';
