-- etl_sigrid/infrastructure/postgres/sql/retenciones/08_saldo_cliente.sql
-- ============================================================================
-- F-104 · LA RETENCION DE CLIENTE DESDE LA CONTABILIDAD
--
-- Construye:
--   retenciones.saldo_contable_cliente  una fila por cuenta de retencion de
--                                       cliente con apuntes
--   retenciones.v_cuadre_cliente        contabilidad frente a efectos, por cuenta
--
-- Lee de raw.apu, raw.con y, de este mismo paso, retenciones.cuentas_cliente
-- (01_movimientos.sql) y retenciones.movimientos. Nunca contabilidad.mayor ni
-- ventas: `build_retenciones` corre antes que `build_contabilidad` y
-- `build_ventas`.
--
-- MANDA LA CONTABILIDAD (D4 de F-104, como F-095 en proveedor). Los efectos de
-- `movimientos` son el detalle y el vencimiento; el saldo vivo de cliente es el
-- de sus cuentas de retencion (16.002.697,94 EUR en 169 cuentas el
-- 2026-11-16, igual al centimo que `contabilidad.mayor.importe_saldo` de esas
-- cuentas). La explicacion por FACTURA de cada descuadre esta en
-- `ventas.retencion_factura` y `ventas.retencion_cuenta` (D10 = b).
--
-- EL SALDO (R11)
-- ---------------------------------------------------------------------------
-- `importe = deb - hab`: la cuenta 43x8 es de ACTIVO (lo que el cliente nos
-- debe crece por el debe), al reves que la 4x08 de proveedor de
-- 03_apuntes_contables.sql. La clase del apunte es la de 03, con sus reglas y
-- su orden, REPLICADA (`apuntes_contables` solo tiene cuentas de proveedor):
--   CIERRE, SALDO_INICIAL (apertura sin cierre de la cuenta el ejercicio
--   anterior), APERTURA, ALTA (importe > 0), BAJA (importe <= 0).
--   saldo = ALTA + BAJA + SALDO_INICIAL; CIERRE y APERTURA no suman nunca.
--   saldo_anterior_2016 = la apertura de 2016 (saldo a 31-12-2015).
-- Sin obra: atribuir el saldo contable a obra queda fuera (D5).
--
-- EL CUADRE (R12, R13)
-- ---------------------------------------------------------------------------
-- Por cuenta: el saldo contable frente a los efectos de `movimientos` CLIENTE
-- en estado VIVA (el criterio de F-104 se LEE, no se recalcula). FULL JOIN para
-- no perder ninguna cola; universo, cuentas con saldo o viva >= 1 EUR. La
-- categoria, con el CASE y el orden de `v_cuadre_proveedor`:
--   CUADRA, SIN_EFECTOS_VIVOS, SIN_SALDO_CONTABLE, CONTABILIDAD_MAYOR,
--   EFECTOS_MAYOR.
-- ============================================================================

DROP TABLE IF EXISTS retenciones.saldo_contable_cliente CASCADE;
CREATE TABLE retenciones.saldo_contable_cliente AS
WITH apuntes AS (
    SELECT
        a.ide                                                       AS apunte_id,
        retenciones.fn_sigrid_date(a.fec)                           AS fecha,
        EXTRACT(YEAR FROM retenciones.fn_sigrid_date(a.fec))::INT   AS ejercicio,
        a.cueide                                                    AS cuenta_id,
        a.res                                                       AS concepto,
        (COALESCE(a.deb, 0) - COALESCE(a.hab, 0))::NUMERIC(18, 2)   AS importe
    FROM raw.apu a
    JOIN retenciones.cuentas_cliente cc ON cc.cuenta_id = a.cueide
),
-- Las cuentas con cierre en cada ejercicio, DISTINCT para no multiplicar
cierres_cuenta AS (
    SELECT DISTINCT ap.cuenta_id, ap.ejercicio
    FROM apuntes ap
    WHERE ap.concepto LIKE 'Asiento de cierre%'
),
clasificados AS (
    SELECT
        ap.cuenta_id,
        ap.fecha,
        ap.ejercicio,
        ap.importe,
        CASE WHEN ap.concepto LIKE 'Asiento de cierre%' THEN 'CIERRE'
             WHEN ap.concepto LIKE 'Asiento de apertura%' AND cc.cuenta_id IS NULL THEN 'SALDO_INICIAL'
             WHEN ap.concepto LIKE 'Asiento de apertura%' THEN 'APERTURA'
             WHEN ap.importe > 0 THEN 'ALTA'
             ELSE 'BAJA' END AS clase
    FROM apuntes ap
    LEFT JOIN cierres_cuenta cc ON cc.cuenta_id = ap.cuenta_id AND cc.ejercicio = ap.ejercicio - 1
)
SELECT
    k.cuenta_id               AS cuenta_id,
    cu.cliente_id             AS cliente_id,
    cu.codigo_cuenta          AS codigo_cuenta,
    cu.nombre_cuenta          AS nombre_cuenta,
    cu.familia                AS familia,
    cu.criterio_seleccion     AS criterio_seleccion,
    COALESCE(SUM(k.importe) FILTER (WHERE k.clase = 'ALTA'), 0)::NUMERIC(18, 2) AS altas,
    COALESCE(SUM(k.importe) FILTER (WHERE k.clase = 'BAJA'), 0)::NUMERIC(18, 2) AS bajas,
    COALESCE(SUM(k.importe) FILTER (WHERE k.clase = 'SALDO_INICIAL'), 0)::NUMERIC(18, 2) AS saldo_inicial,
    COALESCE(SUM(k.importe) FILTER (WHERE k.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL')), 0)::NUMERIC(18, 2) AS saldo,
    COALESCE(SUM(k.importe) FILTER (WHERE k.clase IN ('APERTURA', 'SALDO_INICIAL') AND k.ejercicio = 2016), 0)::NUMERIC(18, 2) AS saldo_anterior_2016,
    COUNT(*) FILTER (WHERE k.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL')) AS num_apuntes,
    MIN(k.fecha) FILTER (WHERE k.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL')) AS primer_movimiento,
    MAX(k.fecha) FILTER (WHERE k.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL')) AS ultimo_movimiento
FROM clasificados k
JOIN retenciones.cuentas_cliente cu ON cu.cuenta_id = k.cuenta_id
-- La apertura de 2016 entra SOLO para `saldo_anterior_2016`
WHERE k.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL') OR (k.clase = 'APERTURA' AND k.ejercicio = 2016)
GROUP BY k.cuenta_id, cu.cliente_id, cu.codigo_cuenta, cu.nombre_cuenta, cu.familia,
         cu.criterio_seleccion;

ALTER TABLE retenciones.saldo_contable_cliente ADD PRIMARY KEY (cuenta_id);
CREATE INDEX idx_ret_saldo_cli_cliente ON retenciones.saldo_contable_cliente (cliente_id);

COMMENT ON TABLE retenciones.saldo_contable_cliente IS
'F-104. Saldo contable de retencion de CLIENTE por cuenta (retenciones.cuentas_cliente), '
'de raw.apu con importe = debe - haber (cuenta de activo): la fuente que manda para la '
'retencion viva de cliente. saldo = altas + bajas + saldo_inicial; cierres y aperturas '
'no suman nunca (clase de 03_apuntes_contables.sql). Sin obra (D5). '
'saldo_anterior_2016 = apertura de 2016.';


DROP VIEW IF EXISTS retenciones.v_cuadre_cliente CASCADE;
CREATE VIEW retenciones.v_cuadre_cliente AS
WITH efectos AS (
    SELECT
        m.cuenta_id,
        SUM(m.importe) AS viva_efectos,
        COUNT(*)       AS num_efectos_vivos
    FROM retenciones.movimientos m
    WHERE m.sentido = 'CLIENTE' AND m.estado = 'VIVA' AND m.cuenta_id IS NOT NULL
    GROUP BY m.cuenta_id
),
x AS (
    SELECT
        COALESCE(s.cuenta_id, e.cuenta_id)            AS cuenta_id,
        COALESCE(s.saldo, 0)::NUMERIC(18, 2)          AS saldo_contable,
        COALESCE(e.viva_efectos, 0)::NUMERIC(18, 2)   AS viva_efectos,
        COALESCE(e.num_efectos_vivos, 0)              AS num_efectos_vivos
    FROM retenciones.saldo_contable_cliente s
    FULL JOIN efectos e ON e.cuenta_id = s.cuenta_id
)
SELECT
    x.cuenta_id               AS cuenta_id,
    cue.cod                   AS codigo_cuenta,
    cue.res                   AS nombre_cuenta,
    cu.cliente_id             AS cliente_id,
    cu.criterio_seleccion     AS criterio_seleccion,
    x.saldo_contable          AS saldo_contable,
    x.viva_efectos            AS viva_efectos,
    x.num_efectos_vivos       AS num_efectos_vivos,
    (x.saldo_contable - x.viva_efectos)::NUMERIC(18, 2) AS diferencia,
    CASE WHEN ABS(x.saldo_contable - x.viva_efectos) < 1 THEN 'CUADRA'
         WHEN ABS(x.viva_efectos) < 1 THEN 'SIN_EFECTOS_VIVOS'
         WHEN ABS(x.saldo_contable) < 1 THEN 'SIN_SALDO_CONTABLE'
         WHEN x.saldo_contable > x.viva_efectos THEN 'CONTABILIDAD_MAYOR'
         ELSE 'EFECTOS_MAYOR' END AS categoria
FROM x
LEFT JOIN raw.con cue ON cue.ide = x.cuenta_id
LEFT JOIN retenciones.cuentas_cliente cu ON cu.cuenta_id = x.cuenta_id
WHERE ABS(x.saldo_contable) >= 1 OR ABS(x.viva_efectos) >= 1;

COMMENT ON VIEW retenciones.v_cuadre_cliente IS
'F-104. Cuadre por cuenta de retencion de CLIENTE entre el saldo contable '
'(retenciones.saldo_contable_cliente) y los efectos VIVA de retenciones.movimientos '
'(sentido CLIENTE, estado que aqui solo se lee). MANDA LA CONTABILIDAD; la explicacion '
'por factura de cada descuadre esta en ventas.retencion_cuenta. categoria: CUADRA, '
'SIN_EFECTOS_VIVOS, SIN_SALDO_CONTABLE, CONTABILIDAD_MAYOR, EFECTOS_MAYOR, en ese orden. '
'Solo cuentas con saldo o viva de al menos 1 EUR.';
