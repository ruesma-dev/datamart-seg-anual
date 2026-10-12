-- etl_sigrid/infrastructure/postgres/sql/contabilidad/06_saldos_general.sql
-- ============================================================================
-- F-135 · SCHEMA contabilidad (7/8): LOS SALDOS GENERALES, SOLO LO VISIBLE
--
-- Construye:
--   contabilidad.saldos_cuenta_mes   una fila por cuenta, empresa, ejercicio y
--                                    mes con algun apunte VISIBLE
--
-- Lee SOLO de contabilidad_restringida.mayor (02), con la marca.
--
-- QUE CAMBIA RESPECTO A LOS COMPLETOS (R11)
-- ---------------------------------------------------------------------------
-- · Cada agregado de F-056 (03) se calcula SOLO sobre los apuntes visibles
--   (`FILTER (WHERE NOT restringido)`), y `saldo_acumulado` acumula esos
--   saldos: es el ultimo `saldo_acumulado` del mes en `contabilidad.mayor`.
-- · Se omiten las filas sin ningun apunte visible (`HAVING`): las de las
--   cuentas CR, enteras, y los meses en que una cuenta mixta solo tuvo apuntes
--   de personal.
-- · Dos columnas al final, SOLO RECUENTOS (D5: el importe restringido por
--   empresa y mes seria la masa salarial):
--     num_apuntes_restringidos  los apuntes de esa cuenta y mes que faltan
--     incompleto                num_apuntes_restringidos > 0: el saldo de la
--                               fila esta recortado (6.063 filas medidas el
--                               2026-10-09)
--
-- LA CLAVE es la de F-056: (cuenta_id, empresa_id, ejercicio, mes), con los
-- apuntes sin cuenta agrupados en `cuenta_id = 0`.
-- ============================================================================

DROP TABLE IF EXISTS contabilidad.saldos_cuenta_mes CASCADE;
CREATE TABLE contabilidad.saldos_cuenta_mes AS
WITH mensual AS (
    SELECT
        COALESCE(m.cuenta_id, 0)                                              AS cuenta_id,
        m.empresa_id,
        m.ejercicio,
        m.mes,
        COUNT(*) FILTER (WHERE NOT m.restringido)                             AS num_apuntes,
        SUM(m.debe) FILTER (WHERE NOT m.restringido)::NUMERIC(18, 2)          AS debe,
        SUM(m.haber) FILTER (WHERE NOT m.restringido)::NUMERIC(18, 2)         AS haber,
        COALESCE(SUM(m.importe) FILTER (WHERE NOT m.restringido AND m.clase_asiento IN ('APERTURA', 'SALDO_INICIAL')), 0)::NUMERIC(18, 2) AS importe_apertura,
        COALESCE(SUM(m.importe) FILTER (WHERE NOT m.restringido AND m.clase_asiento = 'NORMAL'), 0)::NUMERIC(18, 2)                      AS importe_movimiento,
        COALESCE(SUM(m.importe) FILTER (WHERE NOT m.restringido AND m.clase_asiento = 'REGULARIZACION'), 0)::NUMERIC(18, 2)              AS importe_regularizacion,
        COALESCE(SUM(m.importe) FILTER (WHERE NOT m.restringido AND m.clase_asiento = 'CIERRE'), 0)::NUMERIC(18, 2)                      AS importe_cierre,
        SUM(m.importe_saldo) FILTER (WHERE NOT m.restringido)::NUMERIC(18, 2) AS importe_saldo,
        COUNT(*) FILTER (WHERE m.restringido)                                 AS num_apuntes_restringidos
    FROM contabilidad_restringida.mayor m
    GROUP BY COALESCE(m.cuenta_id, 0), m.empresa_id, m.ejercicio, m.mes
    HAVING COUNT(*) FILTER (WHERE NOT m.restringido) > 0
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
    )::NUMERIC(18, 2)                                                         AS saldo_acumulado,
    s.num_apuntes_restringidos,
    s.num_apuntes_restringidos > 0                                            AS incompleto
FROM mensual s;

ALTER TABLE contabilidad.saldos_cuenta_mes ADD PRIMARY KEY (cuenta_id, empresa_id, ejercicio, mes);
CREATE INDEX idx_con_saldos_empresa_ejercicio ON contabilidad.saldos_cuenta_mes (empresa_id, ejercicio, mes);

COMMENT ON TABLE contabilidad.saldos_cuenta_mes IS
'F-056 y F-135. Saldos GENERALES por cuenta, empresa, ejercicio y mes, solo con los apuntes visibles de contabilidad.mayor: debe, haber, el importe partido por clase, importe_saldo (sin CIERRE ni APERTURA) y saldo_acumulado a fin de mes. num_apuntes_restringidos e incompleto dicen si a la fila le faltan apuntes de personal (solo recuentos). Las cuentas de personal no tienen fila. Los apuntes sin cuenta van con cuenta_id = 0.';
