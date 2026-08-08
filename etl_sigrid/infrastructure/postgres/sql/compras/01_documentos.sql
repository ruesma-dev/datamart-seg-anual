-- etl_sigrid/infrastructure/postgres/sql/compras/01_documentos.sql
-- ============================================================================
-- Documentos de compra tipados: contratos, albaranes (AC/PROF/NTC) y
-- facturas (FR/AB), con cabecera + líneas y trazabilidad resuelta.
--
-- Convenciones Sigrid aplicadas:
--   · cod / res / fec del documento viven en con (mismo ide), NO en la
--     extensión (dca/dcf/ctr).
--   · Proveedor: entide (FK a con) en la extensión; nombre via con.res.
--   · Obra y partida vienen EN LA LÍNEA (dcapro.obride/paride,
--     dcfpro.obride/paride). En contrato la obra está en cabecera
--     (ctr.obride) y la partida en línea (ctrpro.paride).
--   · Trazabilidad por línea: linoriide + docoritip
--       44 = la línea origen es de contrato (ctrpro)
--       14 = la línea origen es de albarán (dcapro)
--   · Importes tot = línea SIN IVA. ivacuo aparte.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- CONTRATOS
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS compras.contratos CASCADE;
CREATE TABLE compras.contratos AS
SELECT
    c.ide                                   AS contrato_id,
    con.cod                                 AS codigo_contrato,
    compras.fn_serie(con.cod)               AS serie,
    con.res                                 AS descripcion,
    compras.fn_sigrid_date(con.fec)         AS fecha,
    NULLIF(c.obride, 0)                     AS obra_id,
    obr_con.cod                             AS codigo_obra,
    obr_con.res                             AS nombre_obra,
    NULLIF(c.entide, 0)                     AS proveedor_id,
    prv_con.res                             AS proveedor_nombre,
    NULLIF(TRIM(c.entcif), '')              AS proveedor_cif,
    NULLIF(c.comide, 0)                     AS comparativo_id
FROM raw.ctr c
JOIN raw.con con          ON con.ide = c.ide
LEFT JOIN raw.con obr_con ON obr_con.ide = NULLIF(c.obride, 0)
LEFT JOIN raw.con prv_con ON prv_con.ide = NULLIF(c.entide, 0);

ALTER TABLE compras.contratos ADD PRIMARY KEY (contrato_id);
CREATE INDEX idx_com_ctr_obra ON compras.contratos (obra_id);
CREATE INDEX idx_com_ctr_prv  ON compras.contratos (proveedor_id);

DROP TABLE IF EXISTS compras.contrato_lineas CASCADE;
CREATE TABLE compras.contrato_lineas AS
SELECT
    l.ide                                   AS linea_id,
    l.docide                                AS contrato_id,
    NULLIF(l.proide, 0)                     AS producto_id,
    l.res                                   AS descripcion,
    l.unimed                                AS unidad_medida,
    NULLIF(l.paride, 0)                     AS partida_id,
    NULLIF(l.cenide, 0)                     AS centro_coste_id,
    COALESCE(l.can, 0)::NUMERIC(20, 6)      AS cantidad,
    COALESCE(l.pre, 0)::NUMERIC(20, 6)      AS precio,
    COALESCE(l.tot, 0)::NUMERIC(18, 2)      AS importe,          -- sin IVA
    COALESCE(l.ivacuo, 0)::NUMERIC(18, 2)   AS cuota_iva,
    COALESCE(l.canser, 0)::NUMERIC(20, 6)   AS cantidad_servida
FROM raw.ctrpro l
WHERE EXISTS (SELECT 1 FROM raw.ctr c WHERE c.ide = l.docide);

ALTER TABLE compras.contrato_lineas ADD PRIMARY KEY (linea_id);
CREATE INDEX idx_com_ctrlin_ctr ON compras.contrato_lineas (contrato_id);
CREATE INDEX idx_com_ctrlin_par ON compras.contrato_lineas (partida_id);

-- ---------------------------------------------------------------------------
-- ALBARANES (series AC = albarán, PROF = proforma/cert. subcontrata, NTC…)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS compras.albaranes CASCADE;
CREATE TABLE compras.albaranes AS
SELECT
    a.ide                                   AS albaran_id,
    con.cod                                 AS codigo_albaran,
    compras.fn_serie(con.cod)               AS serie,
    compras.fn_tipo_documento(14, compras.fn_serie(con.cod)) AS tipo_documento,
    con.res                                 AS descripcion,
    compras.fn_sigrid_date(con.fec)         AS fecha,
    NULLIF(a.ctride, 0)                     AS contrato_id,
    NULLIF(a.comide, 0)                     AS comparativo_id,
    NULLIF(a.entide, 0)                     AS proveedor_id,
    prv_con.res                             AS proveedor_nombre,
    NULLIF(TRIM(a.entcif), '')              AS proveedor_cif,
    NULLIF(TRIM(a.entref), '')              AS referencia_proveedor
FROM raw.dca a
JOIN raw.con con          ON con.ide = a.ide
LEFT JOIN raw.con prv_con ON prv_con.ide = NULLIF(a.entide, 0);

ALTER TABLE compras.albaranes ADD PRIMARY KEY (albaran_id);
CREATE INDEX idx_com_alb_ctr ON compras.albaranes (contrato_id);
CREATE INDEX idx_com_alb_prv ON compras.albaranes (proveedor_id);
CREATE INDEX idx_com_alb_tip ON compras.albaranes (tipo_documento);

DROP TABLE IF EXISTS compras.albaran_lineas CASCADE;
CREATE TABLE compras.albaran_lineas AS
SELECT
    l.ide                                   AS linea_id,
    l.docide                                AS albaran_id,
    NULLIF(l.obride, 0)                     AS obra_id,
    NULLIF(l.paride, 0)                     AS partida_id,
    NULLIF(l.proide, 0)                     AS producto_id,
    l.res                                   AS descripcion,
    l.unimed                                AS unidad_medida,
    NULLIF(l.cenide, 0)                     AS centro_coste_id,
    COALESCE(l.can, 0)::NUMERIC(20, 6)      AS cantidad,
    COALESCE(l.pre, 0)::NUMERIC(20, 6)      AS precio,
    COALESCE(l.tot, 0)::NUMERIC(18, 2)      AS importe,          -- sin IVA
    COALESCE(l.ivacuo, 0)::NUMERIC(18, 2)   AS cuota_iva,
    COALESCE(l.canfac, 0)::NUMERIC(20, 6)   AS cantidad_facturada,
    -- Trazabilidad a contrato (docoritip=44)
    CASE WHEN l.docoritip = 44 THEN NULLIF(l.linoriide, 0) END AS contrato_linea_id,
    CASE WHEN l.docoritip = 44 THEN NULLIF(l.docoriide, 0) END AS contrato_id_linea,
    -- Ratio facturado y pendiente de facturar (sin IVA).
    -- can=0: línea replicada no recibida (patrón Sigrid) o ajuste; si además
    -- tot=0, el pendiente es 0. Si canfac cubre can, pendiente 0 o negativo
    -- (sobrefacturación: se conserva el signo como información).
    CASE
        WHEN COALESCE(l.can, 0) = 0 THEN
            CASE WHEN COALESCE(l.canfac, 0) <> 0 THEN 0::NUMERIC(18,2)
                 ELSE COALESCE(l.tot, 0)::NUMERIC(18,2) END
        ELSE
            ROUND((COALESCE(l.tot, 0)
                   * (1 - COALESCE(l.canfac, 0) / l.can))::NUMERIC, 2)
    END                                     AS importe_pendiente_facturar
FROM raw.dcapro l
WHERE EXISTS (SELECT 1 FROM raw.dca a WHERE a.ide = l.docide);

ALTER TABLE compras.albaran_lineas ADD PRIMARY KEY (linea_id);
CREATE INDEX idx_com_alblin_alb ON compras.albaran_lineas (albaran_id);
CREATE INDEX idx_com_alblin_obr ON compras.albaran_lineas (obra_id);
CREATE INDEX idx_com_alblin_par ON compras.albaran_lineas (partida_id);
CREATE INDEX idx_com_alblin_ctl ON compras.albaran_lineas (contrato_linea_id);

-- ---------------------------------------------------------------------------
-- FACTURAS (series FR/FRGG = factura, AB/ABGG = abono)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS compras.facturas CASCADE;
CREATE TABLE compras.facturas AS
SELECT
    f.ide                                   AS factura_id,
    con.cod                                 AS codigo_factura,
    compras.fn_serie(con.cod)               AS serie,
    compras.fn_tipo_documento(15, compras.fn_serie(con.cod)) AS tipo_documento,
    con.res                                 AS descripcion,
    compras.fn_sigrid_date(con.fec)         AS fecha,
    NULLIF(f.entide, 0)                     AS proveedor_id,
    prv_con.res                             AS proveedor_nombre,
    NULLIF(TRIM(f.entcif), '')              AS proveedor_cif,
    NULLIF(TRIM(f.entref), '')              AS referencia_proveedor
FROM raw.dcf f
JOIN raw.con con          ON con.ide = f.ide
LEFT JOIN raw.con prv_con ON prv_con.ide = NULLIF(f.entide, 0);

ALTER TABLE compras.facturas ADD PRIMARY KEY (factura_id);
CREATE INDEX idx_com_fac_prv ON compras.facturas (proveedor_id);
CREATE INDEX idx_com_fac_tip ON compras.facturas (tipo_documento);

DROP TABLE IF EXISTS compras.factura_lineas CASCADE;
CREATE TABLE compras.factura_lineas AS
SELECT
    l.ide                                   AS linea_id,
    l.docide                                AS factura_id,
    NULLIF(l.obride, 0)                     AS obra_id,
    NULLIF(l.paride, 0)                     AS partida_id,
    NULLIF(l.proide, 0)                     AS producto_id,
    l.res                                   AS descripcion,
    l.unimed                                AS unidad_medida,
    NULLIF(l.cenide, 0)                     AS centro_coste_id,
    COALESCE(l.can, 0)::NUMERIC(20, 6)      AS cantidad,
    COALESCE(l.pre, 0)::NUMERIC(20, 6)      AS precio,
    COALESCE(l.tot, 0)::NUMERIC(18, 2)      AS importe,          -- sin IVA
    COALESCE(l.ivacuo, 0)::NUMERIC(18, 2)   AS cuota_iva,
    -- Trazabilidad: a albarán (14) o directa a contrato (44)
    CASE WHEN l.docoritip = 14 THEN NULLIF(l.linoriide, 0) END AS albaran_linea_id,
    CASE WHEN l.docoritip = 14 THEN NULLIF(l.docoriide, 0) END AS albaran_id,
    CASE WHEN l.docoritip = 44 THEN NULLIF(l.linoriide, 0) END AS contrato_linea_id,
    CASE WHEN l.docoritip = 44 THEN NULLIF(l.docoriide, 0) END AS contrato_id_directo
FROM raw.dcfpro l
WHERE EXISTS (SELECT 1 FROM raw.dcf f WHERE f.ide = l.docide);

ALTER TABLE compras.factura_lineas ADD PRIMARY KEY (linea_id);
CREATE INDEX idx_com_faclin_fac ON compras.factura_lineas (factura_id);
CREATE INDEX idx_com_faclin_obr ON compras.factura_lineas (obra_id);
CREATE INDEX idx_com_faclin_par ON compras.factura_lineas (partida_id);
CREATE INDEX idx_com_faclin_alb ON compras.factura_lineas (albaran_linea_id);
CREATE INDEX idx_com_faclin_ctl ON compras.factura_lineas (contrato_linea_id);
