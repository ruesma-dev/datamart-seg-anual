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


-- ============================================================================
--   retenciones.apuntes_contables  una fila por apunte de raw.apu en esas cuentas
--
-- Lee ademas raw.apu.
--
-- UNA FILA POR APUNTE, SIN FILTRAR NINGUNO (R3): 49.505 el 2026-09-22.
-- `importe = hab - deb`: positivo es retencion que se practica (haber de la
-- cuenta), negativo es retencion que se devuelve o se da de baja (debe). Los
-- dos lados van tambien por separado, sin signo, en importe_alta/importe_baja.
-- `apunte_id` es clave primaria: nada de lo que se une aqui multiplica (R8).
--
-- CLASE DEL APUNTE (R4), evaluada en este orden:
--   CIERRE         el concepto empieza por 'Asiento de cierre'
--   SALDO_INICIAL  empieza por 'Asiento de apertura' y ESA CUENTA no tiene
--                  cierre en el ejercicio anterior: es historia anterior a
--                  Sigrid (la apertura de 2008, 642.775,50 EUR el 2026-09-22)
--   APERTURA       apertura con cierre previo de la misma cuenta
--   ALTA           importe > 0
--   BAJA           importe <= 0
-- En el agregado de estas cuentas la apertura de cada ejercicio es exactamente
-- el cierre del anterior (2009-2026, al centimo), asi que sumar ALTA + BAJA +
-- SALDO_INICIAL da el saldo contable sin contar dos veces (R5). Excluir TODAS
-- las aperturas perderia la de 2008. La regla es por cuenta y no por fecha
-- (D4): una cuenta nueva en otra empresa tendria su saldo inicial otro ano.
-- `asi.ori` NO sirve para distinguirlos: vale 0 en todos.
-- `es_prescripcion` MARCA (concepto con 'PRESCRI'), no filtra (R6).
-- ============================================================================

DROP TABLE IF EXISTS retenciones.apuntes_contables CASCADE;
CREATE TABLE retenciones.apuntes_contables AS
WITH apuntes AS (
    SELECT
        a.ide                                                   AS apunte_id,
        NULLIF(a.asiide, 0)                                     AS asiento_id,
        retenciones.fn_sigrid_date(a.fec)                       AS fecha,
        EXTRACT(YEAR FROM retenciones.fn_sigrid_date(a.fec))::INT AS ejercicio,
        a.cueide                                                AS cuenta_id,
        cp.codigo_cuenta                                        AS codigo_cuenta,
        cp.proveedor_id                                         AS proveedor_id,
        a.res                                                   AS concepto,
        COALESCE(a.hab, 0)::NUMERIC(18, 2)                      AS importe_alta,
        COALESCE(a.deb, 0)::NUMERIC(18, 2)                      AS importe_baja,
        (COALESCE(a.hab, 0) - COALESCE(a.deb, 0))::NUMERIC(18, 2) AS importe,
        NULLIF(a.cenide, 0)                                     AS centro_coste_id
    FROM raw.apu a
    JOIN retenciones.cuentas_proveedor cp ON cp.cuenta_id = a.cueide
),
-- Las cuentas con cierre en cada ejercicio: una fila por (cuenta, ejercicio)
cierres_cuenta AS (
    SELECT DISTINCT ap.cuenta_id, ap.ejercicio
    FROM apuntes ap
    WHERE ap.concepto LIKE 'Asiento de cierre%'
)
SELECT
    ap.apunte_id,
    ap.asiento_id,
    ap.fecha,
    ap.ejercicio,
    ap.cuenta_id,
    ap.codigo_cuenta,
    ap.proveedor_id,
    ap.concepto,
    ap.importe_alta,
    ap.importe_baja,
    ap.importe,
    CASE WHEN ap.concepto LIKE 'Asiento de cierre%' THEN 'CIERRE'
         WHEN ap.concepto LIKE 'Asiento de apertura%' AND NOT EXISTS (
              SELECT 1 FROM cierres_cuenta cc
              WHERE cc.cuenta_id = ap.cuenta_id AND cc.ejercicio = ap.ejercicio - 1
         ) THEN 'SALDO_INICIAL'
         WHEN ap.concepto LIKE 'Asiento de apertura%' THEN 'APERTURA'
         WHEN ap.importe > 0 THEN 'ALTA'
         ELSE 'BAJA' END AS clase,
    UPPER(COALESCE(ap.concepto, '')) LIKE '%PRESCRI%' AS es_prescripcion,
    ap.centro_coste_id
FROM apuntes ap;

ALTER TABLE retenciones.apuntes_contables ADD PRIMARY KEY (apunte_id);
CREATE INDEX idx_ret_apc_proveedor ON retenciones.apuntes_contables (proveedor_id);
CREATE INDEX idx_ret_apc_clase     ON retenciones.apuntes_contables (clase);
