-- etl_sigrid/infrastructure/postgres/sql/retenciones/03_apuntes_contables.sql
-- ============================================================================
-- F-095 · LAS RETENCIONES DE PROVEEDOR DESDE LA CONTABILIDAD (1/4)
--
-- Construye:
--   retenciones.cuentas_proveedor  una fila por proveedor con cuenta de retencion
--
-- Lee de raw.prv y raw.con. Nada de stg, mart ni cierre.
--
-- LAS CUENTAS SE ELIGEN POR `prv.cueretide`, NUNCA POR PREFIJO (R1)
-- ---------------------------------------------------------------------------
-- Cada proveedor declara su cuenta de retencion en `prv.cueretide`, 1:1
-- (2.247 cuentas el 2026-09-22, ninguna compartida). Una lista de prefijos
-- (4008, 4108, 4180) dejaba fuera 4038 (0,90 M EUR) y 4128: aqui entran solas.
-- `familia` son los 4 primeros digitos del codigo, SOLO descriptiva.
-- La cuenta es una fila de raw.con (el plan de cuentas vive en con, tip 16):
-- de ahi su codigo y su nombre.
-- ============================================================================

DROP TABLE IF EXISTS retenciones.cuentas_proveedor CASCADE;
CREATE TABLE retenciones.cuentas_proveedor AS
SELECT
    prv.ide                 AS proveedor_id,
    ent.res                 AS proveedor_nombre,
    prv.cueretide           AS cuenta_id,
    cue.cod                 AS codigo_cuenta,
    cue.res                 AS nombre_cuenta,
    LEFT(cue.cod, 4)        AS familia
FROM raw.prv prv
LEFT JOIN raw.con ent ON ent.ide = prv.ide
LEFT JOIN raw.con cue ON cue.ide = prv.cueretide
WHERE COALESCE(prv.cueretide, 0) <> 0;

ALTER TABLE retenciones.cuentas_proveedor ADD PRIMARY KEY (proveedor_id);
-- 1:1 medido. Si Sigrid llegara a compartir una cuenta entre dos proveedores,
-- el build falla AQUI con su nombre, en vez de duplicar apuntes mas abajo.
CREATE UNIQUE INDEX uq_ret_cuentas_proveedor_cuenta ON retenciones.cuentas_proveedor (cuenta_id);

COMMENT ON TABLE retenciones.cuentas_proveedor IS
'F-095. Una fila por proveedor con cuenta de retencion (prv.cueretide <> 0), '
'con el codigo y el nombre de la cuenta (raw.con) y su familia (4 digitos, '
'descriptiva). Las cuentas se eligen por el proveedor, nunca por prefijo.';
