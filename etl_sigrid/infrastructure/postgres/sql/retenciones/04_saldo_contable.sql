-- etl_sigrid/infrastructure/postgres/sql/retenciones/04_saldo_contable.sql
-- ============================================================================
-- F-095 · LAS RETENCIONES DE PROVEEDOR DESDE LA CONTABILIDAD (2/4)
--
-- Construye:
--   retenciones.saldo_contable  una fila por (proveedor, obra)
--
-- Lee de retenciones.apuntes_contables y retenciones.cuentas_proveedor
-- (03_apuntes_contables.sql, mismo paso).
--
-- EL SALDO VIVO A PROVEEDOR LO MANDA LA CONTABILIDAD (R12). `movimientos` (los
-- efectos, F-094) es el detalle; el cuadre entre los dos esta en
-- `retenciones.v_cuadre_proveedor`.
--
-- QUE SUMA (R11)
-- ---------------------------------------------------------------------------
--   altas          clase ALTA            (positivo: retencion practicada)
--   bajas          clase BAJA            (negativo: devuelta o dada de baja)
--   saldo_inicial  clase SALDO_INICIAL   (la historia anterior a Sigrid)
--   saldo          = altas + bajas + saldo_inicial
-- CIERRE y APERTURA NO SUMAN NUNCA: la apertura de cada ejercicio es el cierre
-- del anterior y sumarlas multiplica (~57 M EUR por lado).
--   saldo_anterior_2016  la apertura de 2016, es decir el saldo a 31-12-2015:
--                  la historia anterior a los efectos que publica el datamart.
--
-- LA FILA SIN OBRA (R11, R13, D6): lo que la cascada no atribuye (via_obra
-- SIN_OBRA) va a la fila `obra_id` NULL de cada proveedor, SIN REPARTIR. Es una
-- fila, no un hueco: repartirla por reglas inventadas publicaria un dato que
-- Sigrid no tiene. La clave (proveedor_id, obra_id) es unica con NULLS NOT
-- DISTINCT: una sola fila sin obra por proveedor.
-- ============================================================================

DROP TABLE IF EXISTS retenciones.saldo_contable CASCADE;
CREATE TABLE retenciones.saldo_contable AS
SELECT
    a.proveedor_id,
    cp.proveedor_nombre,
    a.obra_id,
    a.empresa_id,
    a.codigo_obra,
    a.clave_obra,
    a.nombre_obra,
    COALESCE(SUM(a.importe) FILTER (WHERE a.clase = 'ALTA'), 0)::NUMERIC(18, 2) AS altas,
    COALESCE(SUM(a.importe) FILTER (WHERE a.clase = 'BAJA'), 0)::NUMERIC(18, 2) AS bajas,
    COALESCE(SUM(a.importe) FILTER (WHERE a.clase = 'SALDO_INICIAL'), 0)::NUMERIC(18, 2) AS saldo_inicial,
    COALESCE(SUM(a.importe) FILTER (WHERE a.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL')), 0)::NUMERIC(18, 2) AS saldo,
    COALESCE(SUM(a.importe) FILTER (WHERE a.clase IN ('APERTURA', 'SALDO_INICIAL') AND a.ejercicio = 2016), 0)::NUMERIC(18, 2) AS saldo_anterior_2016,
    COUNT(*) FILTER (WHERE a.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL')) AS num_apuntes,
    MIN(a.fecha) FILTER (WHERE a.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL')) AS primer_movimiento,
    MAX(a.fecha) FILTER (WHERE a.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL')) AS ultimo_movimiento
FROM retenciones.apuntes_contables a
JOIN retenciones.cuentas_proveedor cp ON cp.proveedor_id = a.proveedor_id
-- La apertura de 2016 entra SOLO para `saldo_anterior_2016`; el resto de
-- aperturas y todos los cierres se quedan fuera
WHERE a.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL') OR (a.clase = 'APERTURA' AND a.ejercicio = 2016)
GROUP BY a.proveedor_id, cp.proveedor_nombre, a.obra_id, a.empresa_id,
         a.codigo_obra, a.clave_obra, a.nombre_obra;

CREATE UNIQUE INDEX uq_ret_saldo_contable ON retenciones.saldo_contable (proveedor_id, obra_id) NULLS NOT DISTINCT;
CREATE INDEX idx_ret_saldo_obra ON retenciones.saldo_contable (obra_id);

COMMENT ON TABLE retenciones.saldo_contable IS
'F-095. Saldo contable de retencion por (proveedor, obra): la fuente que manda '
'para el saldo vivo a proveedor. saldo = altas + bajas + saldo_inicial; '
'cierres y aperturas no suman nunca. obra_id NULL es la fila sin obra del '
'proveedor, sin repartir. saldo_anterior_2016 = apertura de 2016.';
