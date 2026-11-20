-- etl_sigrid/infrastructure/postgres/sql/contabilidad/11_saldos_analitica_general.sql
-- ============================================================================
-- F-127 · SCHEMA contabilidad (12/13): LOS SALDOS ANALITICOS GENERALES
--
-- Construye:
--   contabilidad.saldos_cuenta_analitica_mes   una fila por cuenta analitica,
--                                              centro, empresa, ejercicio y mes
--                                              con alguna fila VISIBLE
--
-- Lee SOLO de contabilidad_restringida.mayor_analitico (08), con la marca.
--
-- QUE CAMBIA RESPECTO A LOS COMPLETOS (R16), como 06 en el financiero:
-- · Cada agregado de 09 se calcula SOLO sobre lo visible (`FILTER (WHERE NOT
--   restringido)`), y `saldo_acumulado` acumula esos importes.
-- · Se omiten las filas sin nada visible (`HAVING`): las de las cuentas CP,
--   enteras, y los meses en que una cuenta mixta solo tuvo lo restringido.
-- · Dos columnas al final, SOLO RECUENTOS (D5 de F-135):
--     num_apuntes_restringidos  las filas de esa clave que faltan
--     incompleto                num_apuntes_restringidos > 0: el saldo de la
--                               fila esta recortado
--
-- LA CLAVE es la de 09: (cuenta_analitica_id, centro_coste_id, empresa_id,
-- ejercicio, mes), con las filas sin cuenta o sin centro en 0.
-- ============================================================================

DROP TABLE IF EXISTS contabilidad.saldos_cuenta_analitica_mes CASCADE;
CREATE TABLE contabilidad.saldos_cuenta_analitica_mes AS
WITH mensual AS (
    SELECT
        COALESCE(m.cuenta_analitica_id, 0)                                    AS cuenta_analitica_id,
        COALESCE(m.centro_coste_id, 0)                                        AS centro_coste_id,
        m.empresa_id,
        m.ejercicio,
        m.mes,
        COUNT(*) FILTER (WHERE NOT m.restringido)                             AS num_apuntes,
        SUM(m.debe) FILTER (WHERE NOT m.restringido)::NUMERIC(18, 2)          AS debe,
        SUM(m.haber) FILTER (WHERE NOT m.restringido)::NUMERIC(18, 2)         AS haber,
        SUM(m.importe) FILTER (WHERE NOT m.restringido)::NUMERIC(18, 2)       AS importe,
        COUNT(*) FILTER (WHERE m.restringido)                                 AS num_apuntes_restringidos
    FROM contabilidad_restringida.mayor_analitico m
    GROUP BY COALESCE(m.cuenta_analitica_id, 0), COALESCE(m.centro_coste_id, 0), m.empresa_id, m.ejercicio, m.mes
    HAVING COUNT(*) FILTER (WHERE NOT m.restringido) > 0
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
    )::NUMERIC(18, 2)                                                         AS saldo_acumulado,
    s.num_apuntes_restringidos,
    s.num_apuntes_restringidos > 0                                            AS incompleto
FROM mensual s;

ALTER TABLE contabilidad.saldos_cuenta_analitica_mes ADD PRIMARY KEY (cuenta_analitica_id, centro_coste_id, empresa_id, ejercicio, mes);
CREATE INDEX idx_con_sana_empresa_ejercicio ON contabilidad.saldos_cuenta_analitica_mes (empresa_id, ejercicio, mes);
CREATE INDEX idx_con_sana_centro            ON contabilidad.saldos_cuenta_analitica_mes (centro_coste_id, ejercicio, mes);

COMMENT ON TABLE contabilidad.saldos_cuenta_analitica_mes IS
'F-127. Saldos ANALITICOS GENERALES por cuenta analitica, centro de coste, empresa, ejercicio y mes, solo con las filas visibles de contabilidad.mayor_analitico: num_apuntes, debe, haber, importe y saldo_acumulado a fin de mes. num_apuntes_restringidos e incompleto dicen si a la fila le faltan filas restringidas (solo recuentos). Las cuentas de contrapartida no tienen fila.';
