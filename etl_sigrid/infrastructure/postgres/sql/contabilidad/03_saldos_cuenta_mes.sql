-- etl_sigrid/infrastructure/postgres/sql/contabilidad/03_saldos_cuenta_mes.sql
-- ============================================================================
-- F-056 · SCHEMA contabilidad (4/4): LOS SALDOS POR CUENTA Y MES
--
-- Construye:
--   contabilidad.saldos_cuenta_mes   una fila por cuenta, ejercicio y mes con
--                                    algun apunte (~400.000)
--
-- Lee SOLO de contabilidad.mayor (R25): la clase, el importe del saldo y la
-- empresa ya estan resueltos alli, y aqui no se vuelve a decidir nada.
--
-- EL IMPORTE, PARTIDO POR CLASE (R25):
--   importe_apertura        APERTURA + SALDO_INICIAL
--   importe_movimiento      NORMAL
--   importe_regularizacion  REGULARIZACION
--   importe_cierre          CIERRE
--   importe_saldo           la suma de `importe_saldo` del mayor: NORMAL +
--                           REGULARIZACION + SALDO_INICIAL (sin CIERRE ni
--                           APERTURA, que duplican)
--   saldo_acumulado         el saldo de la cuenta a FIN DE MES
-- La suma de `importe_saldo` por cuenta iguala la del mayor y el ultimo
-- `saldo_acumulado` el ultimo del mayor (R26).
--
-- LA CLAVE es (cuenta_id, empresa_id, ejercicio, mes). Los 294 apuntes sin
-- cuenta (`cueide = 0`, importe cero) se agrupan con `cuenta_id = 0`, una fila
-- por empresa y mes: caen en dos o tres empresas el mismo mes en 19 meses
-- (medido el 2026-09-26), asi que la empresa tiene que estar en la clave. Para
-- las cuentas reales no cambia nada: su empresa es la del asiento en el 100 %.
-- ============================================================================

DROP TABLE IF EXISTS contabilidad.saldos_cuenta_mes CASCADE;
CREATE TABLE contabilidad.saldos_cuenta_mes AS
WITH mensual AS (
    SELECT
        COALESCE(m.cuenta_id, 0)                                              AS cuenta_id,
        m.empresa_id,
        m.ejercicio,
        m.mes,
        COUNT(*)                                                              AS num_apuntes,
        SUM(m.debe)::NUMERIC(18, 2)                                           AS debe,
        SUM(m.haber)::NUMERIC(18, 2)                                          AS haber,
        COALESCE(SUM(m.importe) FILTER (WHERE m.clase_asiento IN ('APERTURA', 'SALDO_INICIAL')), 0)::NUMERIC(18, 2) AS importe_apertura,
        COALESCE(SUM(m.importe) FILTER (WHERE m.clase_asiento = 'NORMAL'), 0)::NUMERIC(18, 2)                      AS importe_movimiento,
        COALESCE(SUM(m.importe) FILTER (WHERE m.clase_asiento = 'REGULARIZACION'), 0)::NUMERIC(18, 2)              AS importe_regularizacion,
        COALESCE(SUM(m.importe) FILTER (WHERE m.clase_asiento = 'CIERRE'), 0)::NUMERIC(18, 2)                      AS importe_cierre,
        SUM(m.importe_saldo)::NUMERIC(18, 2)                                  AS importe_saldo
    FROM contabilidad.mayor m
    GROUP BY COALESCE(m.cuenta_id, 0), m.empresa_id, m.ejercicio, m.mes
)
SELECT
    s.cuenta_id,
    s.empresa_id,
    s.ejercicio,
    s.mes,
    s.num_apuntes,
    s.debe,
    s.haber,
    s.importe_apertura,
    s.importe_movimiento,
    s.importe_regularizacion,
    s.importe_cierre,
    s.importe_saldo,
    SUM(s.importe_saldo) OVER (
        PARTITION BY s.cuenta_id, s.empresa_id
        ORDER BY s.ejercicio, s.mes
    )::NUMERIC(18, 2)                                                         AS saldo_acumulado
FROM mensual s;

ALTER TABLE contabilidad.saldos_cuenta_mes ADD PRIMARY KEY (cuenta_id, empresa_id, ejercicio, mes);
CREATE INDEX idx_con_saldos_empresa_ejercicio ON contabilidad.saldos_cuenta_mes (empresa_id, ejercicio, mes);

COMMENT ON TABLE contabilidad.saldos_cuenta_mes IS
'F-056. Saldos por cuenta, empresa, ejercicio y mes, desde contabilidad.mayor: debe, haber, el importe partido por clase (apertura, movimiento, regularizacion, cierre), importe_saldo (sin CIERRE ni APERTURA) y saldo_acumulado a fin de mes. Los apuntes sin cuenta van con cuenta_id = 0, una fila por empresa y mes.';
