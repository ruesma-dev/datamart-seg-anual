-- etl_sigrid/infrastructure/postgres/sql/contabilidad/10_mayor_analitico_general.sql
-- ============================================================================
-- F-127 · SCHEMA contabilidad (11/13): EL MAYOR ANALITICO GENERAL, SOLO LO VISIBLE
--
-- Construye:
--   contabilidad.mayor_analitico   una fila por fila VISIBLE del mayor
--                                  analitico completo
--
-- Lee SOLO de contabilidad_restringida.mayor_analitico (08); la guarda, ademas,
-- de contabilidad_restringida.mayor (02) y de raw (el conjunto CP).
--
-- QUE CAMBIA RESPECTO AL COMPLETO (R14), como el mayor general de F-135 (05):
-- · Solo las filas con `restringido = false` (`restringido` nunca es NULL).
-- · Las columnas del completo, en el mismo orden, SIN `es_contrapartida_recurso`
--   (aqui siempre seria falso) ni la marca (`restringido`,
--   `motivo_restriccion`, `saldo_acumulado_visible`).
-- · `saldo_acumulado` es el acumulado de lo VISIBLE (`saldo_acumulado_visible`
--   del completo): en las cuentas mixtas el acumulado completo delataria el
--   importe restringido.
--
-- Materializada y con los indices del completo salvo el parcial: el MCP
-- consulta con 30 s de ventana.
--
-- LA GUARDA (R15), al final y en la misma transaccion: 0 filas de una cuenta
-- CP (el conjunto recalculado desde raw IGUAL que en 08, con D7-b), 0 filas
-- cuyo apunte financiero no sea un apunte VISIBLE del mayor completo
-- (restringido o sin resolver) y `general + restringidas = completo`. Si no,
-- RAISE: el fichero se deshace y queda la tabla de la noche anterior.
-- ============================================================================

DROP TABLE IF EXISTS contabilidad.mayor_analitico CASCADE;
CREATE TABLE contabilidad.mayor_analitico AS
SELECT
    r.apunte_analitico_id,
    r.asiento_id,
    r.tipo_asiento,
    r.codigo_asiento,
    r.posicion,
    r.fecha,
    r.ejercicio,
    r.mes,
    r.empresa_id,
    r.centro_coste_id,
    r.codigo_centro,
    r.obra_id,
    r.codigo_obra,
    r.clave_obra,
    r.cuenta_analitica_id,
    r.codigo_cuenta_analitica,
    r.descripcion_cuenta_analitica,
    r.concepto,
    r.documento,
    r.punteo,
    r.debe,
    r.haber,
    r.importe,
    r.saldo_acumulado_visible AS saldo_acumulado,
    r.apunte_id,
    r.cuenta_id,
    r.codigo_cuenta,
    r.obra_imputada_id,
    r.clave_obra_imputada
FROM contabilidad_restringida.mayor_analitico r
WHERE NOT r.restringido;

ALTER TABLE contabilidad.mayor_analitico ADD PRIMARY KEY (apunte_analitico_id);
CREATE INDEX idx_con_mana_cuenta_fecha         ON contabilidad.mayor_analitico (cuenta_analitica_id, fecha);
CREATE INDEX idx_con_mana_empresa_cuenta_fecha ON contabilidad.mayor_analitico (empresa_id, codigo_cuenta_analitica, fecha);
CREATE INDEX idx_con_mana_obra                 ON contabilidad.mayor_analitico (obra_id);
CREATE INDEX idx_con_mana_obra_imputada        ON contabilidad.mayor_analitico (obra_imputada_id);
CREATE INDEX idx_con_mana_apunte               ON contabilidad.mayor_analitico (apunte_id);
CREATE INDEX idx_con_mana_asiento              ON contabilidad.mayor_analitico (asiento_id);

COMMENT ON TABLE contabilidad.mayor_analitico IS
'F-127. El mayor ANALITICO GENERAL: una fila por fila de raw.apa SALVO las restringidas (cuentas de contrapartida de los trabajadores, apuntes de personal y sus asientos), que solo lee el rol autorizado en contabilidad_restringida.mayor_analitico. Cuanto falta, en contabilidad.apuntes_analiticos_restringidos_mes. saldo_acumulado es el de lo visible. Cuenta ANALITICA; obra solo por el centro; importe = debe - haber (sin cierres ni aperturas). No se suma con contabilidad.mayor.';

-- R15: ninguna fila de CP, ninguna de un apunte restringido o sin resolver, y
-- general + restringidas = completo
DO $$
DECLARE
    v_cp            BIGINT;
    v_apunte        BIGINT;
    v_general       BIGINT;
    v_completo      BIGINT;
    v_restringidas  BIGINT;
BEGIN
    WITH cp_recurso AS (
        SELECT DISTINCT r.caaconide AS cuenta_analitica_id
        FROM raw.res r
        WHERE r.caaconide <> 0
    ),
    centros_cp AS (
        SELECT DISTINCT caa.cenide AS centro_coste_id
        FROM raw.caa caa
        JOIN cp_recurso c ON c.cuenta_analitica_id = caa.ide
        WHERE caa.cenide <> 0
    ),
    cp AS (
        SELECT c.cuenta_analitica_id
        FROM cp_recurso c
        UNION
        SELECT a.cueide
        FROM raw.apa a
        JOIN raw.con asi ON asi.ide = a.conide
        JOIN raw.caa caa ON caa.ide = a.cueide
        JOIN centros_cp cc ON cc.centro_coste_id = caa.cenide
        WHERE asi.tip = 32 AND COALESCE(a.hab, 0) <> 0
    )
    SELECT count(*) INTO v_cp
    FROM contabilidad.mayor_analitico g
    JOIN cp ON cp.cuenta_analitica_id = g.cuenta_analitica_id;
    IF v_cp <> 0 THEN
        RAISE EXCEPTION 'mayor_analitico_general: contabilidad.mayor_analitico tiene % filas de cuentas de contrapartida; no se publica', v_cp;
    END IF;

    SELECT count(*) INTO v_apunte
    FROM contabilidad.mayor_analitico g
    WHERE g.apunte_id IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM contabilidad_restringida.mayor m
          WHERE m.apunte_id = g.apunte_id AND NOT m.restringido
      );
    IF v_apunte <> 0 THEN
        RAISE EXCEPTION 'mayor_analitico_general: contabilidad.mayor_analitico tiene % filas de apuntes restringidos o sin resolver; no se publica', v_apunte;
    END IF;

    SELECT count(*) INTO v_general FROM contabilidad.mayor_analitico;
    SELECT count(*), count(*) FILTER (WHERE restringido)
    INTO v_completo, v_restringidas
    FROM contabilidad_restringida.mayor_analitico;
    IF v_general + v_restringidas <> v_completo THEN
        RAISE EXCEPTION 'mayor_analitico_general: % visibles + % restringidas no suman las % del mayor analitico completo', v_general, v_restringidas, v_completo;
    END IF;
END $$;
