-- etl_sigrid/infrastructure/postgres/sql/compras/03_views.sql
-- ============================================================================
-- Vistas de negocio del módulo compras (Tanda C2).
--
--   compras.v_pbi_contrato_consumo       → ¿el contrato se agota?
--   compras.v_pbi_proveedor_obra         → proveedores por obra / año
--   compras.v_pbi_albaranes_sin_facturar → operativa de pendientes
--   compras.v_pbi_partida_coste          → coste incurrido por partida
--
-- Todos los importes SIN IVA. Los ABONOS restan (signo natural).
-- ============================================================================

-- ---------------------------------------------------------------------------
-- CONSUMO DE CONTRATO
--   contratado        = suma de líneas del contrato
--   albaranado        = líneas de albaranes serie AC del contrato
--   certificado_prof  = líneas de proformas (PROF) del contrato
--   consumido         = albaranado + certificado + facturado directo
--   facturado         = facturas cuyo origen (línea de albarán o contrato)
--                       pertenece al contrato
--   pendiente_facturar= importe albaranado aún no facturado (via canfac)
--   disponible        = contratado − consumido
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW compras.v_pbi_contrato_consumo AS
WITH lineas_alb AS (
    SELECT
        COALESCE(a.contrato_id, l.contrato_id_linea) AS contrato_id,
        a.tipo_documento,
        SUM(l.importe)                      AS importe,
        SUM(l.importe_pendiente_facturar)   AS pendiente_facturar
    FROM compras.albaran_lineas l
    JOIN compras.albaranes a ON a.albaran_id = l.albaran_id
    WHERE COALESCE(a.contrato_id, l.contrato_id_linea) IS NOT NULL
    GROUP BY 1, 2
),
alb_pivot AS (
    SELECT
        contrato_id,
        SUM(importe) FILTER (WHERE tipo_documento = 'ALBARAN')  AS albaranado,
        SUM(importe) FILTER (WHERE tipo_documento = 'PROFORMA') AS certificado_proforma,
        SUM(importe) FILTER (WHERE tipo_documento NOT IN ('ALBARAN', 'PROFORMA')) AS otros_docs,
        SUM(pendiente_facturar)                                 AS pendiente_facturar
    FROM lineas_alb
    GROUP BY contrato_id
),
fact_por_ctr AS (
    -- Facturado imputable al contrato: via albarán origen o directo (44)
    SELECT
        COALESCE(fl.contrato_id_directo, alb.contrato_id,
                 alb_l.contrato_id_linea)  AS contrato_id,
        SUM(fl.importe)                    AS facturado,
        SUM(fl.importe) FILTER (WHERE fl.contrato_id_directo IS NOT NULL)
                                           AS facturado_directo
    FROM compras.factura_lineas fl
    LEFT JOIN compras.albaran_lineas alb_l ON alb_l.linea_id = fl.albaran_linea_id
    LEFT JOIN compras.albaranes alb        ON alb.albaran_id = alb_l.albaran_id
    WHERE COALESCE(fl.contrato_id_directo, alb.contrato_id,
                   alb_l.contrato_id_linea) IS NOT NULL
    GROUP BY 1
),
contratado AS (
    SELECT contrato_id, SUM(importe) AS contratado
    FROM compras.contrato_lineas
    GROUP BY contrato_id
)
SELECT
    c.contrato_id,
    c.codigo_contrato,
    c.serie,
    c.fecha,
    c.obra_id,
    c.codigo_obra,
    c.nombre_obra,
    c.proveedor_id,
    c.proveedor_nombre,
    c.proveedor_cif,
    COALESCE(ct.contratado, 0)                       AS importe_contratado,
    COALESCE(ap.albaranado, 0)                       AS importe_albaranado,
    COALESCE(ap.certificado_proforma, 0)             AS importe_certificado_proforma,
    COALESCE(fc.facturado, 0)                        AS importe_facturado,
    COALESCE(fc.facturado_directo, 0)                AS importe_facturado_directo,
    COALESCE(ap.pendiente_facturar, 0)               AS importe_albaranado_sin_facturar,
    -- Consumo total del contrato: lo servido (AC + PROF + otros docs tip14)
    -- más lo facturado directamente contra contrato (sin pasar por albarán).
    COALESCE(ap.albaranado, 0) + COALESCE(ap.certificado_proforma, 0)
      + COALESCE(ap.otros_docs, 0) + COALESCE(fc.facturado_directo, 0)
                                                     AS importe_consumido,
    COALESCE(ct.contratado, 0)
      - (COALESCE(ap.albaranado, 0) + COALESCE(ap.certificado_proforma, 0)
         + COALESCE(ap.otros_docs, 0) + COALESCE(fc.facturado_directo, 0))
                                                     AS importe_disponible,
    CASE WHEN COALESCE(ct.contratado, 0) <> 0 THEN
        ROUND((COALESCE(ap.albaranado, 0) + COALESCE(ap.certificado_proforma, 0)
               + COALESCE(ap.otros_docs, 0) + COALESCE(fc.facturado_directo, 0))
              / ct.contratado * 100, 2)
    END                                              AS pct_consumido
FROM compras.contratos c
LEFT JOIN contratado   ct ON ct.contrato_id = c.contrato_id
LEFT JOIN alb_pivot    ap ON ap.contrato_id = c.contrato_id
LEFT JOIN fact_por_ctr fc ON fc.contrato_id = c.contrato_id;

COMMENT ON VIEW compras.v_pbi_contrato_consumo IS
'Consumo por contrato de compra (Tanda C2). pct_consumido cerca de 100 = '
'contrato agotándose. importe_albaranado_sin_facturar sale de dcapro.canfac '
'(pendiente = tot × (1 − canfac/can)). Importes sin IVA.';

-- ---------------------------------------------------------------------------
-- PROVEEDORES POR OBRA / AÑO
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW compras.v_pbi_proveedor_obra AS
SELECT
    obra_id,
    codigo_obra,
    proveedor_id,
    proveedor_nombre,
    proveedor_cif,
    anio,
    SUM(importe) FILTER (WHERE tipo_doc IN ('FACTURA', 'ABONO'))
                                            AS facturado,
    SUM(importe) FILTER (WHERE tipo_doc = 'ALBARAN')
                                            AS albaranado,
    SUM(importe) FILTER (WHERE tipo_doc = 'PROFORMA')
                                            AS certificado_proforma,
    SUM(importe) FILTER (WHERE tipo_doc = 'CONTRATO')
                                            AS contratado,
    COUNT(DISTINCT documento_id) FILTER (WHERE tipo_doc IN ('FACTURA', 'ABONO'))
                                            AS num_facturas,
    COUNT(DISTINCT documento_id) FILTER (WHERE tipo_doc IN ('ALBARAN', 'PROFORMA'))
                                            AS num_albaranes,
    COUNT(DISTINCT contrato_id)             AS num_contratos
FROM compras.fact_compras_linea
WHERE proveedor_id IS NOT NULL
GROUP BY obra_id, codigo_obra, proveedor_id, proveedor_nombre,
         proveedor_cif, anio;

COMMENT ON VIEW compras.v_pbi_proveedor_obra IS
'Agregado proveedor × obra × año (Tanda C2). "Proveedores con más facturación '
'de la obra X en el año Y": filtrar y ordenar por facturado DESC. '
'Los abonos restan del facturado. Importes sin IVA.';

-- ---------------------------------------------------------------------------
-- ALBARANES SIN FACTURAR (operativa)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW compras.v_pbi_albaranes_sin_facturar AS
SELECT
    a.albaran_id,
    a.codigo_albaran,
    a.serie,
    a.tipo_documento,
    a.fecha,
    a.proveedor_id,
    a.proveedor_nombre,
    a.proveedor_cif,
    a.contrato_id,
    ctr.codigo_contrato,
    l.obra_id,
    obr_con.cod                             AS codigo_obra,
    l.partida_id,
    l.linea_id,
    l.descripcion,
    l.cantidad,
    l.cantidad_facturada,
    l.importe,
    l.importe_pendiente_facturar,
    (CURRENT_DATE - a.fecha)                AS dias_desde_albaran
FROM compras.albaran_lineas l
JOIN compras.albaranes a  ON a.albaran_id = l.albaran_id
LEFT JOIN raw.con obr_con ON obr_con.ide = l.obra_id
LEFT JOIN compras.contratos ctr
       ON ctr.contrato_id = COALESCE(a.contrato_id, l.contrato_id_linea)
WHERE l.importe_pendiente_facturar > 0
  AND a.tipo_documento IN ('ALBARAN', 'PROFORMA');

COMMENT ON VIEW compras.v_pbi_albaranes_sin_facturar IS
'Líneas de albarán/proforma con importe pendiente de facturar > 0 (Tanda C2). '
'Basado en dcapro.canfac. dias_desde_albaran para priorizar antigüedad.';

-- ---------------------------------------------------------------------------
-- COSTE INCURRIDO POR PARTIDA (albaranado + facturado)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW compras.v_pbi_partida_coste AS
SELECT
    f.obra_id,
    f.codigo_obra,
    f.partida_id,
    par.cod                                 AS codigo_partida,
    par.res                                 AS descripcion_partida,
    SUM(f.importe) FILTER (WHERE f.tipo_doc = 'ALBARAN')
                                            AS albaranado,
    SUM(f.importe) FILTER (WHERE f.tipo_doc = 'PROFORMA')
                                            AS certificado_proforma,
    SUM(f.importe) FILTER (WHERE f.tipo_doc IN ('FACTURA', 'ABONO'))
                                            AS facturado,
    SUM(f.importe) FILTER (WHERE f.tipo_doc = 'CONTRATO')
                                            AS contratado,
    COUNT(*) FILTER (WHERE f.tipo_doc IN ('ALBARAN', 'PROFORMA'))
                                            AS num_lineas_albaran,
    COUNT(*) FILTER (WHERE f.tipo_doc IN ('FACTURA', 'ABONO'))
                                            AS num_lineas_factura
FROM compras.fact_compras_linea f
LEFT JOIN raw.obrparpar par ON par.ide = f.partida_id
WHERE f.partida_id IS NOT NULL
GROUP BY f.obra_id, f.codigo_obra, f.partida_id, par.cod, par.res;

COMMENT ON VIEW compras.v_pbi_partida_coste IS
'Coste incurrido por partida (Tanda C2): albaranado (AC), certificado (PROF) '
'y facturado (FR−AB), sin IVA. Comparable con el coste real del seguimiento.';
