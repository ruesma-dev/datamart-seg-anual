-- etl_sigrid/infrastructure/postgres/sql/tesoreria/03_efectos_restringidos_mes.sql
-- ============================================================================
-- F-037 · SCHEMA tesoreria (4/4): tesoreria.efectos_restringidos_mes
--
-- CUANTOS efectos de personal le faltan a `tesoreria.efectos`, por empresa,
-- sentido, anio y mes de VENCIMIENTO y estado (R13). SIN IMPORTES (D6): el
-- importe por empresa y mes es la nomina neta mensual, que es justo lo que se
-- protege. Con esto el rol estandar sabe que su cartera esta recortada y
-- cuanto, sin ver lo recortado.
--
-- Sin vencimiento, anio y mes 0 (y sin empresa, empresa 0): la clave primaria
-- no admite NULL. La ficha del diccionario lo dice.
--
-- Lee de: tesoreria_restringida.efectos. Escribe en:
--         tesoreria.efectos_restringidos_mes.
-- ============================================================================

TRUNCATE tesoreria.efectos_restringidos_mes;

INSERT INTO tesoreria.efectos_restringidos_mes (
    empresa_id, sentido, anio, mes, estado_tesoreria, num_efectos
)
SELECT
    COALESCE(r.empresa_id, 0) AS empresa_id,
    r.sentido,
    COALESCE(EXTRACT(YEAR FROM r.fecha_vencimiento)::INT, 0) AS anio,
    COALESCE(EXTRACT(MONTH FROM r.fecha_vencimiento)::INT, 0) AS mes,
    r.estado_tesoreria,
    count(*) AS num_efectos
FROM tesoreria_restringida.efectos r
WHERE r.restringido
GROUP BY 1, 2, 3, 4, 5;

COMMENT ON TABLE tesoreria.efectos_restringidos_mes IS
'F-037. Cuantos efectos de personal (nominas, embargos, cuotas) faltan en tesoreria.efectos, por empresa, sentido, anio y mes de vencimiento y estado_tesoreria. Solo recuentos, nunca cifras de dinero. anio y mes = 0: efecto sin vencimiento; empresa_id = 0: sin empresa.';
