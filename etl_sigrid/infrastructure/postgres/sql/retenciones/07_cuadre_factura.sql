-- etl_sigrid/infrastructure/postgres/sql/retenciones/07_cuadre_factura.sql
-- ============================================================================
-- F-128 · EL CUADRE DE LA RETENCIÓN DE GARANTÍA POR FACTURA
--
-- Construye:
--   retenciones.retencion_factura      una fila por factura con garantía o con
--                                      apunte de retención enlazado
--   retenciones.v_cuadre_factura_obra  el mismo cuadre por (proveedor, obra)
--
-- Lee SOLO `raw` (`dcf`, `dcfrec`, `con`) y `retenciones` (`apuntes_contables`,
-- `movimientos`, `saldo_contable`, de este mismo paso). NUNCA `compras`: el
-- cuadre no puede depender de `build_compras` ni caerse con un `DROP ...
-- CASCADE` de ese esquema; por eso la retención de la factura se recalcula
-- aquí desde `raw.dcfrec` con `retenciones.fn_es_retencion_garantia` (copia de
-- la de `compras`, R19).
--
-- LOS TRES LADOS DE UNA MISMA RETENCIÓN
-- ---------------------------------------------------------------------------
--   retencion_factura  Σ cuota de los recargos de garantía de la factura
--                      (clases 4 y 5, D2-B), agregada ANTES de unir
--   retencion_contable Σ importe de los apuntes ALTA/BAJA de
--                      `apuntes_contables` cuyo documento (vía `rac`) es ella
--   efectos_generados  Σ importe de los efectos PROVEEDOR de esa factura en
--                      `movimientos`, sin los BAJA salvo el estado 14 (el
--                      AGRUPADO: es BAJA pero su dinero sigue vivo en el AGR;
--                      sin él solo cuadraban 7.793 en vez de 22.729)
--   efectos_vivos      los de estado VIVA
--
-- Medido el 2026-10-17 con D2-B sobre 167.488 facturas: 27.002 facturas,
-- 24,04 M € en factura frente a 24,54 M € contabilizados. Contabilidad: 26.762
-- CUADRA (99,1 %), 58 SIN_APUNTE, 175 SOLO_CONTABLE (42 de ellas con `RETESP`,
-- que D2-B no cuenta como garantía: salen aquí a propósito, sin caso especial),
-- 7 DIFIERE. Efectos: 22.729 CUADRA (84,2 %), 4.229 SIN_EFECTOS, 44 DIFIERE.
-- Los efectos AGR (agrupadores) no tienen factura: 2.454 efectos, 0,82 M €
-- vivos que ningún cuadre por factura puede atribuir (es el descuadre que queda
-- en `v_cuadre_proveedor`).
--
-- La OBRA es la de CABECERA de la factura (`dcf.obride`), no la cascada de
-- F-095: coinciden en el 99,8 % de las facturas enlazadas y es la que
-- Administración ve en la factura. Por (proveedor, obra): 6.109 pares, 5.304
-- cuadran (86,8 %).
-- ============================================================================

DROP TABLE IF EXISTS retenciones.retencion_factura CASCADE;
CREATE TABLE retenciones.retencion_factura AS
WITH garantia AS (
    -- Agregada POR FACTURA antes de unir: guarda de grano. Cada cuota se
    -- redondea como en `compras.factura_recargos`, para que los dos cuadren.
    SELECT r.docide AS factura_id, SUM(COALESCE(r.cuo, 0)::NUMERIC(18, 2)) AS retencion
    FROM raw.dcfrec r
    WHERE retenciones.fn_es_retencion_garantia(r.reccla)
    GROUP BY r.docide
),
contable AS (
    SELECT documento_id, SUM(importe) AS importe
    FROM retenciones.apuntes_contables
    WHERE clase IN ('ALTA', 'BAJA') AND documento_id IS NOT NULL
    GROUP BY documento_id
),
efectos AS (
    SELECT documento_id,
           SUM(importe) FILTER (WHERE estado <> 'BAJA' OR estado_sigrid = 14) AS generados,
           SUM(importe) FILTER (WHERE estado = 'VIVA') AS vivos
    FROM retenciones.movimientos
    WHERE sentido = 'PROVEEDOR' AND documento_id IS NOT NULL
    GROUP BY documento_id
),
universo AS (
    SELECT factura_id FROM garantia WHERE ABS(retencion) >= 0.01
    UNION
    SELECT documento_id FROM contable
)
SELECT
    u.factura_id                                         AS factura_id,
    c.cod                                                AS codigo_factura,
    retenciones.fn_sigrid_date(c.fec)                    AS fecha_alta,
    retenciones.fn_sigrid_date(f.fecdoc)                 AS fecha_factura,
    NULLIF(f.entide, 0)                                  AS proveedor_id,
    prv.res                                              AS proveedor_nombre,
    NULLIF(f.obride, 0)                                  AS obra_id,        -- la de CABECERA
    ob.emp                                               AS empresa_id,
    ob.cod                                               AS codigo_obra,
    ob.emp::text || '-' || ob.cod                        AS clave_obra,
    ob.res                                               AS nombre_obra,
    COALESCE(g.retencion, 0)::NUMERIC(18, 2)             AS retencion_factura,
    ct.importe::NUMERIC(18, 2)                           AS retencion_contable,   -- NULL sin apunte
    (COALESCE(g.retencion, 0) - ct.importe)::NUMERIC(18, 2) AS diferencia_contable,
    e.generados::NUMERIC(18, 2)                          AS efectos_generados,    -- NULL sin efecto
    e.vivos::NUMERIC(18, 2)                              AS efectos_vivos,
    (COALESCE(g.retencion, 0) - e.generados)::NUMERIC(18, 2) AS diferencia_efectos,
    CASE WHEN ABS(COALESCE(g.retencion, 0)) < 0.01 THEN 'SOLO_CONTABLE'
         WHEN ct.importe IS NULL THEN 'SIN_APUNTE'
         WHEN ABS(COALESCE(g.retencion, 0) - ct.importe) < 0.01 THEN 'CUADRA'
         ELSE 'DIFIERE' END                              AS categoria_contable,
    CASE WHEN e.generados IS NULL THEN 'SIN_EFECTOS'
         WHEN ABS(COALESCE(g.retencion, 0) - e.generados) < 0.01 THEN 'CUADRA'
         ELSE 'DIFIERE' END                              AS categoria_efectos
FROM universo u
-- JOIN y no LEFT: deja fuera los `documento_id` contables que no son una
-- factura (efectos, AGR). Es el único filtro del universo.
JOIN raw.dcf f            ON f.ide = u.factura_id
JOIN raw.con c            ON c.ide = f.ide
LEFT JOIN garantia g      ON g.factura_id = u.factura_id
LEFT JOIN contable ct     ON ct.documento_id = u.factura_id
LEFT JOIN efectos e       ON e.documento_id = u.factura_id
LEFT JOIN raw.con prv     ON prv.ide = NULLIF(f.entide, 0)
LEFT JOIN raw.con ob      ON ob.ide = NULLIF(f.obride, 0);

ALTER TABLE retenciones.retencion_factura ADD PRIMARY KEY (factura_id);
CREATE INDEX idx_ret_rfa_proveedor ON retenciones.retencion_factura (proveedor_id);
CREATE INDEX idx_ret_rfa_obra ON retenciones.retencion_factura (obra_id);

COMMENT ON TABLE retenciones.retencion_factura IS
'F-128. Cuadre de la retencion de garantia por factura: una fila por factura con '
'garantia distinta de 0 (recargos de clase 4 y 5, D2-B) o con algun apunte ALTA/BAJA '
'de retenciones.apuntes_contables enlazado a ella. retencion_factura frente a '
'retencion_contable (apuntes) y efectos_generados (efectos PROVEEDOR no dados de '
'baja, con el agrupado 14). categoria_contable: SOLO_CONTABLE, SIN_APUNTE, CUADRA, '
'DIFIERE; categoria_efectos: SIN_EFECTOS, CUADRA, DIFIERE (tolerancia 0,01). Obra = la '
'de cabecera de la factura. Las facturas con RETESP y asiento salen SOLO_CONTABLE.';


-- ---------------------------------------------------------------------------
-- EL CUADRE POR (PROVEEDOR, OBRA): facturas frente a altas contables.
-- `FULL JOIN` con `saldo_contable` (una fila por par, la sin obra incluida, por
-- eso `IS NOT DISTINCT FROM`) para no perder ninguna de las dos colas. Nombres
-- del lado que exista. Categoría, en este orden: CUADRA (|dif| < 1 €),
-- SOLO_FACTURAS, SOLO_CONTABILIDAD, FACTURAS_MAYOR, CONTABILIDAD_MAYOR. Solo
-- pares con algún lado >= 1 €, como `v_cuadre_proveedor`. A diferencia de
-- aquella (contabilidad frente a EFECTOS por proveedor), esta compara la
-- FACTURA con la contabilidad y baja a la obra.
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS retenciones.v_cuadre_factura_obra CASCADE;
CREATE VIEW retenciones.v_cuadre_factura_obra AS
WITH fac AS (
    SELECT
        proveedor_id,
        obra_id,
        MAX(proveedor_nombre)                                   AS proveedor_nombre,
        MAX(empresa_id)                                         AS empresa_id,
        MAX(codigo_obra)                                        AS codigo_obra,
        MAX(clave_obra)                                         AS clave_obra,
        MAX(nombre_obra)                                        AS nombre_obra,
        SUM(retencion_factura)                                  AS retencion_facturas,
        COUNT(*)                                                AS num_facturas,
        COUNT(*) FILTER (WHERE categoria_contable <> 'CUADRA') AS num_facturas_descuadre
    FROM retenciones.retencion_factura
    GROUP BY proveedor_id, obra_id
),
x AS (
    SELECT
        COALESCE(f.proveedor_id, c.proveedor_id)            AS proveedor_id,
        COALESCE(f.proveedor_nombre, c.proveedor_nombre)    AS proveedor_nombre,
        COALESCE(f.obra_id, c.obra_id)                      AS obra_id,
        COALESCE(f.empresa_id, c.empresa_id)                AS empresa_id,
        COALESCE(f.codigo_obra, c.codigo_obra)              AS codigo_obra,
        COALESCE(f.clave_obra, c.clave_obra)                AS clave_obra,
        COALESCE(f.nombre_obra, c.nombre_obra)              AS nombre_obra,
        COALESCE(f.retencion_facturas, 0)::NUMERIC(18, 2)   AS retencion_facturas,
        COALESCE(c.altas, 0)::NUMERIC(18, 2) AS altas_contables,
        COALESCE(f.num_facturas, 0)                         AS num_facturas,
        COALESCE(f.num_facturas_descuadre, 0)               AS num_facturas_descuadre
    FROM fac f
    FULL JOIN retenciones.saldo_contable c ON c.proveedor_id = f.proveedor_id
                                          AND c.obra_id IS NOT DISTINCT FROM f.obra_id
)
SELECT
    x.proveedor_id                                          AS proveedor_id,
    x.proveedor_nombre                                      AS proveedor_nombre,
    x.obra_id                                               AS obra_id,
    x.empresa_id                                            AS empresa_id,
    x.codigo_obra                                           AS codigo_obra,
    x.clave_obra                                            AS clave_obra,
    x.nombre_obra                                           AS nombre_obra,
    x.retencion_facturas                                    AS retencion_facturas,
    x.altas_contables                                       AS altas_contables,
    (x.retencion_facturas - x.altas_contables)::NUMERIC(18, 2) AS diferencia,
    x.num_facturas                                          AS num_facturas,
    x.num_facturas_descuadre                                AS num_facturas_descuadre,
    CASE WHEN ABS(x.retencion_facturas - x.altas_contables) < 1 THEN 'CUADRA'
         WHEN ABS(x.altas_contables) < 1 THEN 'SOLO_FACTURAS'
         WHEN ABS(x.retencion_facturas) < 1 THEN 'SOLO_CONTABILIDAD'
         WHEN x.retencion_facturas > x.altas_contables THEN 'FACTURAS_MAYOR'
         ELSE 'CONTABILIDAD_MAYOR' END                      AS categoria
FROM x
WHERE ABS(x.retencion_facturas) >= 1 OR ABS(x.altas_contables) >= 1;

COMMENT ON VIEW retenciones.v_cuadre_factura_obra IS
'F-128. Cuadre de la retencion de garantia por (proveedor, obra): la retencion de sus '
'facturas (retenciones.retencion_factura) frente a las altas contables '
'(retenciones.saldo_contable), con FULL JOIN. categoria: CUADRA (< 1 EUR), '
'SOLO_FACTURAS, SOLO_CONTABILIDAD, FACTURAS_MAYOR, CONTABILIDAD_MAYOR, en ese orden. '
'Solo pares con algun lado de al menos 1 EUR. num_facturas_descuadre: facturas del par '
'cuya categoria_contable no es CUADRA.';
