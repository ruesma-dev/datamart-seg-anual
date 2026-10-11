-- etl_sigrid/infrastructure/postgres/sql/contabilidad/05_mayor_general.sql
-- ============================================================================
-- F-135 · SCHEMA contabilidad (6/8): EL MAYOR GENERAL, SOLO LO VISIBLE
--
-- Construye:
--   contabilidad.mayor   una fila por apunte VISIBLE del mayor completo
--
-- Lee SOLO de contabilidad_restringida.mayor (02).
--
-- QUE CAMBIA RESPECTO AL COMPLETO (R8, R9)
-- ---------------------------------------------------------------------------
-- · Solo los apuntes con `restringido = false`: fuera los de las cuentas CR y
--   los de los asientos de personal enteros (55.504 apuntes, el 2,55 %, medido
--   el 2026-10-09). `restringido` nunca es NULL (02 hace COALESCE).
-- · Las columnas son las de F-056, con el mismo nombre y en el mismo orden: un
--   consumidor de hoy no nota nada salvo las filas que faltan.
-- · `saldo_acumulado` es el acumulado de lo VISIBLE (`saldo_acumulado_visible`
--   del completo), no el del mayor completo: en las cuentas mixtas (bancos,
--   IVA, proveedores: 71 prefijos) la diferencia entre dos acumulados
--   consecutivos menos el importe visible delataria el importe restringido.
-- · `nombre_cuenta` es el del plan completo: las cuentas CR, que son las
--   unicas enmascaradas en el plan general, no tienen aqui ni un apunte.
--
-- Materializada y con los indices de hoy (R14): el MCP consulta con 30 s de
-- ventana, el motivo de F-056 para no usar vistas.
--
-- LA GUARDA (R10). Al final, en la misma transaccion: 0 apuntes de cuentas CR
-- (la regex del dominio, tal cual) y `general + restringidos = completo`. Si
-- no, RAISE: el fichero entero se deshace y queda la tabla de la noche
-- anterior, que ya estaba filtrada.
-- ============================================================================

DROP TABLE IF EXISTS contabilidad.mayor CASCADE;
CREATE TABLE contabilidad.mayor AS
SELECT
    r.apunte_id,
    r.asiento_id,
    r.codigo_asiento,
    r.posicion,
    r.fecha,
    r.fecha_asiento,
    r.fecha_difiere,
    r.ejercicio,
    r.mes,
    r.empresa_id,
    r.cuenta_id,
    r.codigo_cuenta,
    r.nombre_cuenta,
    r.clave_cuenta,
    r.concepto,
    r.documento,
    r.punteo,
    r.clase_origen,
    r.clase_asiento,
    r.debe,
    r.haber,
    r.importe,
    r.importe_saldo,
    r.saldo_acumulado_visible AS saldo_acumulado,
    r.centro_coste_id,
    r.obra_id,
    r.codigo_obra,
    r.clave_obra,
    r.tercero_id,
    r.tercero_nombre
FROM contabilidad_restringida.mayor r
WHERE NOT r.restringido;

ALTER TABLE contabilidad.mayor ADD PRIMARY KEY (apunte_id);
CREATE INDEX idx_con_mayor_empresa_cuenta_fecha ON contabilidad.mayor (empresa_id, codigo_cuenta, fecha);
CREATE INDEX idx_con_mayor_cuenta_fecha         ON contabilidad.mayor (cuenta_id, fecha);
CREATE INDEX idx_con_mayor_asiento              ON contabilidad.mayor (asiento_id);
CREATE INDEX idx_con_mayor_obra                 ON contabilidad.mayor (obra_id);
CREATE INDEX idx_con_mayor_tercero              ON contabilidad.mayor (tercero_id);

COMMENT ON TABLE contabilidad.mayor IS
'F-056 y F-135. El mayor contable GENERAL: una fila por apunte de raw.apu SALVO los de personal (cuentas CR y asientos de personal enteros), que solo lee el rol autorizado en contabilidad_restringida.mayor. Cuanto falta, en contabilidad.apuntes_restringidos_mes. saldo_acumulado es el de lo visible. fecha = la del apunte y fecha_asiento la del asiento; empresa del asiento; importe = debe - haber. clase_asiento: CIERRE, SALDO_INICIAL, APERTURA, REGULARIZACION, NORMAL. El saldo es importe_saldo (0 en CIERRE y APERTURA) y saldo_acumulado; sumar importe sin filtrar la clase duplica. obra_id solo por el centro del apunte (maestro.centros_coste).';

-- R10: ningun apunte de cuenta CR, y general + restringidos = completo
DO $$
DECLARE
    v_cr            BIGINT;
    v_general       BIGINT;
    v_completo      BIGINT;
    v_restringidos  BIGINT;
BEGIN
    SELECT count(*) INTO v_cr
    FROM contabilidad.mayor
    WHERE codigo_cuenta ~ '^(640|641|642|643|644|645|649|465|466|476|460|461|544|4753)';
    IF v_cr <> 0 THEN
        RAISE EXCEPTION 'mayor_general: contabilidad.mayor tiene % apuntes de cuentas restringidas; no se publica', v_cr;
    END IF;

    SELECT count(*) INTO v_general FROM contabilidad.mayor;
    SELECT count(*), count(*) FILTER (WHERE restringido)
    INTO v_completo, v_restringidos
    FROM contabilidad_restringida.mayor;
    IF v_general + v_restringidos <> v_completo THEN
        RAISE EXCEPTION 'mayor_general: % visibles + % restringidos no suman los % del mayor completo', v_general, v_restringidos, v_completo;
    END IF;
END $$;
