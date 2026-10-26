-- etl_sigrid/infrastructure/postgres/sql/tesoreria/02_efectos_general.sql
-- ============================================================================
-- F-037 · SCHEMA tesoreria (3/4): tesoreria.efectos, LA CARTERA GENERAL
--
-- Las filas de `tesoreria_restringida.efectos` que NO son de personal (R10),
-- con sus mismas columnas en el mismo orden salvo `restringido` y
-- `motivo_restriccion`. Es la que leen el MCP y Power BI, y de ella cuelga la
-- vista `compras.vencimientos` (D1): por eso `TRUNCATE` + `INSERT` y nunca
-- `DROP` (R14).
--
-- LA REMESA MIXTA (R11, D8). Si una remesa lleva algun efecto restringido, su
-- `importe_remesa` sale a NULL en la general: el total de la remesa menos lo
-- visible delataria la nomina que va dentro (1 remesa el 2026-10-13, con 2
-- efectos de nomina). Recalcularla con lo visible daria un numero que no es el
-- de Sigrid con el nombre del de Sigrid.
--
-- LA GUARDA (R12). Al final, en la misma transaccion: 0 filas de la general
-- que cumplan el criterio de personal RECALCULADO DESDE `raw` (naturaleza,
-- cuenta de personal o que no resuelve, tercero empleado, documento de nomina;
-- los literales del dominio, tal cual), y `general + restringidos = completa`.
-- Si no, RAISE: el fichero entero se deshace y queda la tabla de la noche
-- anterior, que ya estaba filtrada.
--
-- Lee de: tesoreria_restringida.efectos y, en la guarda, raw.pag, raw.cob y
--         raw.con. Escribe en: tesoreria.efectos.
-- ============================================================================

TRUNCATE tesoreria.efectos;

INSERT INTO tesoreria.efectos (
    efecto_id, sentido, empresa_id, codigo_efecto, descripcion_efecto,
    serie_efecto, documento_id, codigo_documento, tipo_documento,
    es_factura_compra, tercero_id, tercero_nombre, tercero_cif,
    fecha_emision, fecha_vencimiento, fecha_real, importe, importe_flujo,
    estado_tesoreria, estado_codigo, estado_sigrid, efecto_anulado,
    fecha_anulacion, medio_pago_id, medio_pago, naturaleza_pago_id,
    naturaleza_pago, cuenta_contable_id, cuenta_contable,
    cuenta_contable_nombre, banco_id, banco, sucursal_id, sucursal,
    retencion_id, centro_coste_id, obra_id, codigo_obra, nombre_obra,
    remesa_id, codigo_remesa, fecha_remesa, importe_remesa,
    previsto_antiguo, obra_via
)
SELECT
    r.efecto_id,
    r.sentido,
    r.empresa_id,
    r.codigo_efecto,
    r.descripcion_efecto,
    r.serie_efecto,
    r.documento_id,
    r.codigo_documento,
    r.tipo_documento,
    r.es_factura_compra,
    r.tercero_id,
    r.tercero_nombre,
    r.tercero_cif,
    r.fecha_emision,
    r.fecha_vencimiento,
    r.fecha_real,
    r.importe,
    r.importe_flujo,
    r.estado_tesoreria,
    r.estado_codigo,
    r.estado_sigrid,
    r.efecto_anulado,
    r.fecha_anulacion,
    r.medio_pago_id,
    r.medio_pago,
    r.naturaleza_pago_id,
    r.naturaleza_pago,
    r.cuenta_contable_id,
    r.cuenta_contable,
    r.cuenta_contable_nombre,
    r.banco_id,
    r.banco,
    r.sucursal_id,
    r.sucursal,
    r.retencion_id,
    r.centro_coste_id,
    r.obra_id,
    r.codigo_obra,
    r.nombre_obra,
    r.remesa_id,
    r.codigo_remesa,
    r.fecha_remesa,
    -- R11: la remesa que lleva algun efecto restringido, sin total.
    CASE WHEN r.remesa_id IN (SELECT x.remesa_id
                              FROM tesoreria_restringida.efectos x
                              WHERE x.restringido AND x.remesa_id IS NOT NULL)
         THEN NULL
         ELSE r.importe_remesa END AS importe_remesa,
    r.previsto_antiguo,
    r.obra_via
FROM tesoreria_restringida.efectos r
WHERE NOT r.restringido;

COMMENT ON TABLE tesoreria.efectos IS
'F-037. La cartera GENERAL de cobros y pagos: una fila por efecto de raw.pag (PAGO) y raw.cob (COBRO) SALVO los pagos de personal (nominas, embargos, cuotas), que solo lee el rol autorizado en tesoreria_restringida.efectos; cuantos faltan, en tesoreria.efectos_restringidos_mes. estado_tesoreria: BAJA (no se suma nunca), REALIZADO o PREVISTO; fecha_real vacia NO es pendiente. La cartera de un flujo de caja es estado_tesoreria = PREVISTO AND NOT previsto_antiguo. importe_flujo = +importe en COBRO y -importe en PAGO. Es caja/cartera, no devengo. importe_remesa a NULL si la remesa lleva algun efecto restringido.';

-- R12: ningun efecto de personal en la general, y general + restringidos = completa
DO $$
DECLARE
    v_personal      BIGINT;
    v_general       BIGINT;
    v_completo      BIGINT;
    v_restringidos  BIGINT;
BEGIN
    -- El criterio, RECALCULADO desde `raw` y no leido de la marca de 01: si 01
    -- se equivocara al marcar, esta red lo caza. `x` es el efecto en origen.
    SELECT count(*) INTO v_personal
    FROM tesoreria.efectos g
    JOIN (
        SELECT ide, natide, cueide, entide, conide FROM raw.pag
        UNION ALL
        SELECT ide, natide, cueide, entide, conide FROM raw.cob
    ) x ON x.ide = g.efecto_id
    LEFT JOIN raw.con cue ON cue.ide = NULLIF(x.cueide, 0)
    LEFT JOIN raw.con t   ON t.ide   = NULLIF(x.entide, 0)
    LEFT JOIN raw.con d   ON d.ide   = NULLIF(x.conide, 0)
    WHERE COALESCE(x.natide, 0) <> 0
       OR cue.cod ~ '^(640|641|642|643|644|645|649|465|466|476|460|461|544|4753)'
       OR (NULLIF(x.cueide, 0) IS NOT NULL AND cue.cod IS NULL)
       OR t.tip = 43
       OR d.tip = 306;
    IF v_personal <> 0 THEN
        RAISE EXCEPTION 'efectos_general: tesoreria.efectos tiene % efectos de personal; no se publica', v_personal;
    END IF;

    SELECT count(*) INTO v_general FROM tesoreria.efectos;
    SELECT count(*), count(*) FILTER (WHERE restringido)
    INTO v_completo, v_restringidos
    FROM tesoreria_restringida.efectos;
    IF v_general + v_restringidos <> v_completo THEN
        RAISE EXCEPTION 'efectos_general: % visibles + % restringidos no suman los % de la cartera completa', v_general, v_restringidos, v_completo;
    END IF;
END $$;
