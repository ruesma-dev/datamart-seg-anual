-- etl_sigrid/infrastructure/postgres/sql/contabilidad/09_saldos_analitica.sql
-- ============================================================================
-- F-127 · SCHEMA contabilidad (10/13): LOS SALDOS ANALITICOS POR MES, COMPLETOS
--
-- Construye:
--   contabilidad_restringida.saldos_cuenta_analitica_mes   una fila por cuenta
--                                                          analitica, centro,
--                                                          empresa, ejercicio y
--                                                          mes con alguna fila
--
-- Lee SOLO de contabilidad_restringida.mayor_analitico (08): aqui no se vuelve
-- a decidir nada.
--
-- SIN COLUMNAS POR CLASE: la analitica no tiene cierres ni aperturas (medido el
-- 2026-11-20), asi que el saldo es `importe` (debe - haber) y su acumulado. Lo
-- contrario que el mayor financiero (03), donde sumar `importe` duplica.
--
-- LA CLAVE es (cuenta_analitica_id, centro_coste_id, empresa_id, ejercicio,
-- mes). Las filas sin cuenta o sin centro se agrupan con 0 (R12). El centro va
-- en la clave porque el reparto lleva filas de una cuenta a otro centro (55 de
-- 722.511 no van al centro de su cuenta): el saldo de la cuenta es la suma de
-- sus centros. `saldo_acumulado` es el de (cuenta, centro, empresa) a FIN DE
-- MES.
-- ============================================================================

DROP TABLE IF EXISTS contabilidad_restringida.saldos_cuenta_analitica_mes CASCADE;
CREATE TABLE contabilidad_restringida.saldos_cuenta_analitica_mes AS
WITH mensual AS (
    SELECT
        COALESCE(m.cuenta_analitica_id, 0)                                    AS cuenta_analitica_id,
        COALESCE(m.centro_coste_id, 0)                                        AS centro_coste_id,
        m.empresa_id,
        m.ejercicio,
        m.mes,
        COUNT(*)                                                              AS num_apuntes,
        SUM(m.debe)::NUMERIC(18, 2)                                           AS debe,
        SUM(m.haber)::NUMERIC(18, 2)                                          AS haber,
        SUM(m.importe)::NUMERIC(18, 2)                                        AS importe
    FROM contabilidad_restringida.mayor_analitico m
    GROUP BY COALESCE(m.cuenta_analitica_id, 0), COALESCE(m.centro_coste_id, 0), m.empresa_id, m.ejercicio, m.mes
)
SELECT
    s.cuenta_analitica_id,
    s.centro_coste_id,
    s.empresa_id,
    s.ejercicio,
    s.mes,
    s.num_apuntes,
    s.debe,
    s.haber,
    s.importe,
    SUM(s.importe) OVER (
        PARTITION BY s.cuenta_analitica_id, s.centro_coste_id, s.empresa_id
        ORDER BY s.ejercicio, s.mes
    )::NUMERIC(18, 2)                                                         AS saldo_acumulado
FROM mensual s;

ALTER TABLE contabilidad_restringida.saldos_cuenta_analitica_mes ADD PRIMARY KEY (cuenta_analitica_id, centro_coste_id, empresa_id, ejercicio, mes);
CREATE INDEX idx_con_sana_empresa_ejercicio ON contabilidad_restringida.saldos_cuenta_analitica_mes (empresa_id, ejercicio, mes);
CREATE INDEX idx_con_sana_centro            ON contabilidad_restringida.saldos_cuenta_analitica_mes (centro_coste_id, ejercicio, mes);

COMMENT ON TABLE contabilidad_restringida.saldos_cuenta_analitica_mes IS
'F-127. Saldos ANALITICOS COMPLETOS, solo para el rol autorizado, por cuenta analitica, centro de coste, empresa, ejercicio y mes, desde contabilidad_restringida.mayor_analitico: num_apuntes, debe, haber, importe (debe - haber) y saldo_acumulado a fin de mes de (cuenta, centro, empresa). Sin cierres ni aperturas: aqui importe si se suma. Filas sin cuenta o sin centro con 0.';
