-- etl_sigrid/infrastructure/postgres/sql/contabilidad/07_apuntes_restringidos_mes.sql
-- ============================================================================
-- F-135 · SCHEMA contabilidad (8/8): CUANTO FALTA EN LA CONTABILIDAD GENERAL
--
-- Construye:
--   contabilidad.apuntes_restringidos_mes   una fila por empresa, ejercicio y
--                                           mes con algun apunte restringido
--
-- Lee SOLO de contabilidad_restringida.mayor (02).
--
-- Para que quien lea un saldo de `contabilidad` sepa que esta recortado y en
-- cuanto (R13). SOLO RECUENTOS (D5): ni debe, ni haber, ni importe. El importe
-- restringido por empresa y mes seria la masa salarial mensual, que es justo
-- lo que se protege.
--
-- `num_apuntes_sin_resolver` cuenta aparte los restringidos por FALLAR CERRADO:
-- apuntes cuya cuenta no resuelve en el plan (review de F-135; hoy 0). Si no es
-- 0, hay un apunte de cuenta desconocida que nadie ha clasificado.
-- ============================================================================

DROP TABLE IF EXISTS contabilidad.apuntes_restringidos_mes CASCADE;
CREATE TABLE contabilidad.apuntes_restringidos_mes AS
SELECT
    m.empresa_id,
    m.ejercicio,
    m.mes,
    COUNT(*)                      AS num_apuntes,
    COUNT(DISTINCT m.asiento_id)  AS num_asientos,
    COUNT(*) FILTER (WHERE m.motivo_restriccion = 'CUENTA_SIN_RESOLVER') AS num_apuntes_sin_resolver
FROM contabilidad_restringida.mayor m
WHERE m.restringido
GROUP BY m.empresa_id, m.ejercicio, m.mes;

ALTER TABLE contabilidad.apuntes_restringidos_mes ADD PRIMARY KEY (empresa_id, ejercicio, mes);

COMMENT ON TABLE contabilidad.apuntes_restringidos_mes IS
'F-135. Cuantos apuntes y asientos de PERSONAL faltan en contabilidad.mayor por empresa, ejercicio y mes (solo recuentos, sin importes). El detalle solo lo lee el rol autorizado en contabilidad_restringida.mayor.';
