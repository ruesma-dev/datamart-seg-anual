-- etl_sigrid/infrastructure/postgres/sql/compras/10_necesidades.sql
-- ============================================================================
-- F-067 (con F-125) · `compras.necesidades`: el DOCUMENTO DE NECESIDADES DE
-- COMPRA (`raw.dnc`, concepto de tipo 36), que en Ruesma es el documento de
-- planificación de compras (DPC) de cada obra: UNO POR OBRA (271 de los 277 son
-- el `obr.dncide` de su obra, medido el 2026-10-06), con el código y el nombre
-- de la obra. Sus líneas (`raw.dncpro`) son la planificación del jefe de obra
-- que publica `descompuestos.v_pbi_planif_jo`, y de ellas cuelgan las líneas
-- de contrato, albarán y factura (`necesidad_id`, `necesidad_linea_id`).
--
-- NO SE PUBLICA EL ESTADO: los 277 están «En curso» (`E`); un estado que no
-- distingue nada solo invita a filtrar por él.
--
-- Lee: `raw.dnc`, `raw.con`, `raw.obr`, `raw.dncpro`. Se reconstruye cada
-- noche (DROP + CREATE), como el resto de `compras`; las vistas de
-- `descompuestos` NO la leen a propósito (leen `raw.dncpro`), porque este
-- `CASCADE` se las llevaría por delante.
-- ============================================================================

DROP TABLE IF EXISTS compras.necesidades CASCADE;
CREATE TABLE compras.necesidades AS
SELECT
    d.ide                                   AS necesidad_id,
    c.cod                                   AS codigo_necesidad,  -- el de la obra: 0727.0
    c.res                                   AS nombre,            -- el de la obra
    compras.fn_sigrid_date(c.fec)           AS fecha_alta,
    NULLIF(d.obride, 0)                     AS obra_id,
    obr_con.cod                             AS codigo_obra,
    obr_con.res                             AS nombre_obra,
    -- ¿Es EL documento de necesidades de su obra (`obr.dncide`)? 271 de 277.
    COALESCE(o.dncide = d.ide, FALSE)       AS es_la_de_la_obra,
    COALESCE(nl.n, 0)                       AS n_lineas
FROM raw.dnc d
JOIN raw.con c            ON c.ide = d.ide
LEFT JOIN raw.con obr_con ON obr_con.ide = NULLIF(d.obride, 0)
LEFT JOIN raw.obr o       ON o.ide = NULLIF(d.obride, 0)
-- Agregado ANTES de unir: unir las líneas a secas multiplicaría la cabecera.
LEFT JOIN (
    SELECT p.dncide, count(*) AS n
    FROM   raw.dncpro p
    GROUP  BY p.dncide
) nl ON nl.dncide = d.ide;

ALTER TABLE compras.necesidades ADD PRIMARY KEY (necesidad_id);
CREATE INDEX idx_com_nec_obra ON compras.necesidades (obra_id);
