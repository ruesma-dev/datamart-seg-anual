-- etl_sigrid/infrastructure/postgres/sql/contabilidad/12_apuntes_analiticos_restringidos_mes.sql
-- ============================================================================
-- F-127 · SCHEMA contabilidad (13/13): CUANTO FALTA EN EL MAYOR ANALITICO GENERAL
--
-- Construye:
--   contabilidad.apuntes_analiticos_restringidos_mes   una fila por empresa,
--                                                      ejercicio y mes con
--                                                      alguna fila restringida
--
-- Lee SOLO de contabilidad_restringida.mayor_analitico (08).
--
-- Para que quien lea `contabilidad.mayor_analitico` sepa que esta recortado y
-- en cuanto (R17). SOLO RECUENTOS (D5 de F-135): ni debe, ni haber, ni
-- importe; el importe restringido por empresa y mes seria la masa salarial.
-- Una columna por motivo; `num_apunte_sin_resolver` distinto de 0 es una fila
-- con un apunte financiero que el mayor completo no conoce (hoy 0).
-- ============================================================================

DROP TABLE IF EXISTS contabilidad.apuntes_analiticos_restringidos_mes CASCADE;
CREATE TABLE contabilidad.apuntes_analiticos_restringidos_mes AS
SELECT
    m.empresa_id,
    m.ejercicio,
    m.mes,
    COUNT(*)                      AS num_apuntes,
    COUNT(DISTINCT m.asiento_id)  AS num_asientos,
    COUNT(*) FILTER (WHERE m.motivo_restriccion = 'CONTRAPARTIDA')       AS num_contrapartida,
    COUNT(*) FILTER (WHERE m.motivo_restriccion = 'APUNTE_RESTRINGIDO')  AS num_apunte_restringido,
    COUNT(*) FILTER (WHERE m.motivo_restriccion = 'ASIENTO_PERSONAL')    AS num_asiento_personal,
    COUNT(*) FILTER (WHERE m.motivo_restriccion = 'APUNTE_SIN_RESOLVER') AS num_apunte_sin_resolver
FROM contabilidad_restringida.mayor_analitico m
WHERE m.restringido
GROUP BY m.empresa_id, m.ejercicio, m.mes;

ALTER TABLE contabilidad.apuntes_analiticos_restringidos_mes ADD PRIMARY KEY (empresa_id, ejercicio, mes);

COMMENT ON TABLE contabilidad.apuntes_analiticos_restringidos_mes IS
'F-127. Cuantas filas y asientos del mayor analitico faltan en contabilidad.mayor_analitico por empresa, ejercicio y mes, y cuantas por motivo (contrapartida, apunte restringido, asiento de personal, apunte sin resolver). Solo recuentos, sin importes. El detalle solo lo lee el rol autorizado en contabilidad_restringida.mayor_analitico.';
