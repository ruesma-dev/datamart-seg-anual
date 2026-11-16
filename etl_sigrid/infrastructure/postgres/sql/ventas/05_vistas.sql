-- etl_sigrid/infrastructure/postgres/sql/ventas/05_vistas.sql
-- ============================================================================
-- F-040 · VENTAS (6/8): las tres vistas del seguimiento hasta el cobro
-- (R17-R19).
--
-- Son VISTAS, no tablas, porque leen `tesoreria` en tiempo de consulta: no
-- hace falta que `build_tesoreria` se haya construido antes, solo que sus
-- tablas existan (`tesoreria.efectos` y `tesoreria.devengo_corte_obra` no se
-- dropean nunca: TRUNCATE + INSERT, R14 de F-037). Mismo patron que
-- `compras.vencimientos` y `postventa.v_coste_obra`.
--
-- v_factura_cobro (R17): por factura, lo emitido, cobrado (REALIZADO) y
--   pendiente (PREVISTO) de sus efectos de COBRO con `documento_id` = factura.
--   BAJA no suma nunca (`R-TESORERIA-ESTADO`). Lo cobrado por un agrupado
--   (`AGR`, sin documento) NO se atribuye: F-104.
-- v_seguimiento_certificacion (R18): por certificacion, sus facturas (N:M),
--   lo facturado y lo cobrado de ESAS facturas, `factura_compartida` (alguna
--   de sus facturas es de mas de una certificacion: no sumar lo cobrado entre
--   certificaciones) y el estado, con la PRECEDENCIA de
--   `etl_sigrid/domain/ventas.py::estado_seguimiento`.
-- v_contraste_certificado_obra (R19): solo las obras VENTA de
--   `tesoreria.devengo_corte_obra` (las de la receta de la caja): la venta
--   real a origen con coeficientes, lo certificado (estados 2-4, `base`) y lo
--   facturado (`base`), y las dos diferencias CON SIGNO (sin suelo). El
--   contraste de todas las obras es de F-160.
--
-- Lee de: ventas.facturas, ventas.certificaciones, ventas.certificacion_factura,
--         tesoreria.efectos, tesoreria.devengo_corte_obra y raw.con.
-- Escribe en: las tres vistas.
-- ============================================================================

DROP VIEW IF EXISTS ventas.v_contraste_certificado_obra CASCADE;
DROP VIEW IF EXISTS ventas.v_seguimiento_certificacion CASCADE;
DROP VIEW IF EXISTS ventas.v_factura_cobro CASCADE;

CREATE VIEW ventas.v_factura_cobro AS
WITH cobros AS (
    SELECT
        e.documento_id                                      AS factura_id,
        SUM(e.importe)                                      AS emitido,
        SUM(e.importe) FILTER (WHERE e.estado_tesoreria = 'REALIZADO') AS cobrado,
        SUM(e.importe) FILTER (WHERE e.estado_tesoreria = 'PREVISTO') AS pendiente,
        count(*)                                            AS num_efectos,
        max(e.fecha_real) FILTER (WHERE e.estado_tesoreria = 'REALIZADO') AS ultima_fecha_cobro
    FROM tesoreria.efectos e
    WHERE e.sentido = 'COBRO' AND e.estado_tesoreria <> 'BAJA'
    GROUP BY e.documento_id
)
SELECT
    f.factura_id                                            AS factura_id,
    COALESCE(c.emitido, 0)::NUMERIC(18, 2)                  AS emitido,
    COALESCE(c.cobrado, 0)::NUMERIC(18, 2)                  AS cobrado,
    COALESCE(c.pendiente, 0)::NUMERIC(18, 2)                AS pendiente,
    COALESCE(c.num_efectos, 0)                              AS num_efectos,
    c.ultima_fecha_cobro                                    AS ultima_fecha_cobro
FROM ventas.facturas f
LEFT JOIN cobros c ON c.factura_id = f.factura_id;

COMMENT ON VIEW ventas.v_factura_cobro IS
'F-040. Una fila por factura de venta: lo emitido, cobrado (REALIZADO) y pendiente (PREVISTO) de sus efectos de COBRO de tesoreria.efectos (documento_id = factura), el numero de efectos y el ultimo cobro. BAJA no suma (R-TESORERIA-ESTADO). Lo cobrado por un agrupado AGR no se atribuye a la factura.';

CREATE VIEW ventas.v_seguimiento_certificacion AS
WITH facturas_compartidas AS (
    SELECT cf.factura_id, count(*) AS num_certificaciones
    FROM ventas.certificacion_factura cf
    GROUP BY cf.factura_id
)
, por_certificacion AS (
    SELECT
        cf.certificacion_id,
        count(*)                                            AS num_facturas,
        SUM(f.base)                                         AS facturado,
        SUM(c.emitido)                                      AS emitido,
        SUM(c.cobrado)                                      AS cobrado,
        SUM(c.pendiente)                                    AS pendiente,
        SUM(c.num_efectos)                                  AS num_efectos,
        bool_or(fc.num_certificaciones > 1)                 AS factura_compartida
    FROM ventas.certificacion_factura cf
    JOIN ventas.facturas f ON f.factura_id = cf.factura_id
    JOIN ventas.v_factura_cobro c ON c.factura_id = cf.factura_id
    JOIN facturas_compartidas fc ON fc.factura_id = cf.factura_id
    GROUP BY cf.certificacion_id
)
SELECT
    k.certificacion_id                                      AS certificacion_id,
    COALESCE(p.num_facturas, 0)                             AS num_facturas,
    COALESCE(p.facturado, 0)::NUMERIC(18, 2)                AS facturado,
    COALESCE(p.emitido, 0)::NUMERIC(18, 2)                  AS emitido,
    COALESCE(p.cobrado, 0)::NUMERIC(18, 2)                  AS cobrado,
    COALESCE(p.pendiente, 0)::NUMERIC(18, 2)                AS pendiente,
    COALESCE(p.factura_compartida, FALSE)                   AS factura_compartida,
    CASE WHEN NOT k.cuenta THEN 'BORRADOR'
         WHEN COALESCE(p.num_facturas, 0) = 0 THEN 'SIN_FACTURA'
         WHEN COALESCE(p.num_efectos, 0) = 0 THEN 'FACTURADA_SIN_EFECTO'
         WHEN COALESCE(p.cobrado, 0) <= 0 THEN 'PENDIENTE_COBRO'
         WHEN COALESCE(p.cobrado, 0) < COALESCE(p.emitido, 0) - 0.01 THEN 'COBRADA_PARCIAL'
         ELSE 'COBRADA' END AS estado_seguimiento
FROM ventas.certificaciones k
LEFT JOIN por_certificacion p ON p.certificacion_id = k.certificacion_id;

COMMENT ON VIEW ventas.v_seguimiento_certificacion IS
'F-040. Una fila por certificacion: cuantas facturas tiene (cerprodes, N:M), lo facturado (base) y lo emitido, cobrado y pendiente de esas facturas (v_factura_cobro), factura_compartida (alguna factura es de mas de una certificacion: no sumar lo cobrado entre certificaciones) y estado_seguimiento: BORRADOR, SIN_FACTURA, FACTURADA_SIN_EFECTO, PENDIENTE_COBRO, COBRADA_PARCIAL o COBRADA (a menos de 0,01 de lo emitido).';

CREATE VIEW ventas.v_contraste_certificado_obra AS
WITH certificado AS (
    SELECT k.obra_id, SUM(k.base) AS certificado_origen
    FROM ventas.certificaciones k
    WHERE k.cuenta
    GROUP BY k.obra_id
)
, facturado AS (
    SELECT f.obra_id, SUM(f.base) AS facturado_origen
    FROM ventas.facturas f
    GROUP BY f.obra_id
)
SELECT
    d.obra_id                                               AS obra_id,
    o.cod                                                   AS codigo_obra,
    COALESCE(d.venta_real_origen_con_coeficientes, 0)       AS venta_real_origen_con_coeficientes,
    COALESCE(c.certificado_origen, 0)::NUMERIC(18, 2)       AS certificado_origen,
    COALESCE(fa.facturado_origen, 0)::NUMERIC(18, 2)        AS facturado_origen,
    (COALESCE(d.venta_real_origen_con_coeficientes, 0)
     - COALESCE(c.certificado_origen, 0))::NUMERIC(18, 2)   AS pendiente_certificar,
    (COALESCE(c.certificado_origen, 0)
     - COALESCE(fa.facturado_origen, 0))::NUMERIC(18, 2)    AS certificado_sin_facturar
FROM tesoreria.devengo_corte_obra d
LEFT JOIN raw.con o ON o.ide = d.obra_id
LEFT JOIN certificado c ON c.obra_id = d.obra_id
LEFT JOIN facturado fa ON fa.obra_id = d.obra_id
WHERE d.concepto = 'VENTA';

COMMENT ON VIEW ventas.v_contraste_certificado_obra IS
'F-040. Una fila por obra VENTA de tesoreria.devengo_corte_obra (las de la receta de la caja, no todas): la venta real a origen con coeficientes, lo certificado a origen (estados 2-4, base), lo facturado a origen (base), pendiente_certificar (venta real - certificado) y certificado_sin_facturar (certificado - facturado), con signo. El contraste de todas las obras y los conceptos fuera de coeficiente: F-160.';
