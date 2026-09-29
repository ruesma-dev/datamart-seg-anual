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
--
-- LA OBRA DE CADA APUNTE (R7): cascada, y `via_obra` dice que salto resolvio.
-- Cada salto termina en un CENTRO DE COSTE que se traduce a obra SIEMPRE por
-- `maestro.centros_coste` (F-073, vista sobre raw); si el centro no es una
-- obra (estructura, delegacion), ese salto no resuelve y se prueba el siguiente.
--   APUNTE              el centro del propio apunte (`apu.cenide`)
--   FACTURA             `apu.asiide` -> `rac.conide` = la factura -> sus
--                       efectos de retencion (`pag.retide <> 0`), SOLO si todos
--                       llevan el mismo centro (uno sin centro cuenta como otro
--                       valor: no se atribuye una factura a medias)
--   EFECTO              `rac.conide` = un efecto de pago -> su `pag.cenide`
--   PROVEEDOR_UNA_OBRA  [H3] el proveedor tiene todos sus efectos de retencion
--                       con centro en UN solo centro
--   SIN_OBRA            ninguna de las anteriores: `obra_id` NULL, y no se
--                       reparte por reglas inventadas (D6, R13)
-- `rac` se pre-agrega por asiento (`MIN(conide)`: 1 fila por asiento, medido
-- en F-091); los efectos, por factura y por proveedor; `raw.pag` solo se une
-- por su `ide`. Ningun salto multiplica (R8). Desde 2016 el alta ya no lleva
-- centro en el apunte: sin `rac`, las altas con obra caerian del 97,2 % al
-- 10,8 % del importe (R9).
-- NUNCA `apu.obr` (142 filas y 2 obras) ni el campo de obra de `cen` (a 0 en
-- las 804 filas): R10.
-- La obra se publica con SU empresa (R-CODIGO-POR-EMPRESA, F-102): `empresa_id`
-- y `clave_obra` = '<empresa>-<codigo>', la misma regla que la vista de fichas
-- de obra de maestro (se replica: no se lee, F-102 R24).
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
-- Las cuentas con cierre en cada ejercicio: una fila por (cuenta, ejercicio),
-- DISTINCT para que el anti-join de la clase no multiplique
cierres_cuenta AS (
    SELECT DISTINCT ap.cuenta_id, ap.ejercicio
    FROM apuntes ap
    WHERE ap.concepto LIKE 'Asiento de cierre%'
),
-- Salto FACTURA / EFECTO: el documento que genero el asiento, uno por asiento
rac_asiento AS (
    SELECT r.asiide AS asiento_id, MIN(r.conide) AS documento_id
    FROM raw.rac r
    WHERE r.asiide <> 0 AND r.conide <> 0
    GROUP BY r.asiide
),
-- Los efectos de retencion de cada factura, y si comparten centro
efectos_factura AS (
    SELECT
        p.conide                             AS documento_id,
        COUNT(DISTINCT COALESCE(p.cenide, 0)) AS num_centros,
        MIN(COALESCE(p.cenide, 0))           AS centro_coste_id
    FROM raw.pag p
    WHERE COALESCE(p.retide, 0) <> 0 AND COALESCE(p.conide, 0) <> 0
    GROUP BY p.conide
),
-- [H3] Proveedores con todos sus efectos de retencion (con centro) en UN centro
proveedor_una_obra AS (
    SELECT p.entide AS proveedor_id, MIN(p.cenide) AS centro_coste_id
    FROM raw.pag p
    WHERE COALESCE(p.retide, 0) <> 0 AND COALESCE(p.cenide, 0) <> 0
    GROUP BY p.entide
    HAVING COUNT(DISTINCT p.cenide) = 1
),
resuelto AS (
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
         -- «no existe cierre de la cuenta el ejercicio anterior», como anti-join:
         -- un NOT EXISTS aqui dentro no se hashea y recorreria los apuntes
         -- una vez por cada apertura
         WHEN ap.concepto LIKE 'Asiento de apertura%' AND cc.cuenta_id IS NULL THEN 'SALDO_INICIAL'
         WHEN ap.concepto LIKE 'Asiento de apertura%' THEN 'APERTURA'
         WHEN ap.importe > 0 THEN 'ALTA'
         ELSE 'BAJA' END AS clase,
    UPPER(COALESCE(ap.concepto, '')) LIKE '%PRESCRI%' AS es_prescripcion,
    ap.centro_coste_id,
    COALESCE(cc_apu.obra_id, cc_fac.obra_id, cc_efe.obra_id, cc_prv.obra_id) AS obra_id,
    CASE WHEN cc_apu.obra_id IS NOT NULL THEN 'APUNTE'
         WHEN cc_fac.obra_id IS NOT NULL THEN 'FACTURA'
         WHEN cc_efe.obra_id IS NOT NULL THEN 'EFECTO'
         WHEN cc_prv.obra_id IS NOT NULL THEN 'PROVEEDOR_UNA_OBRA'
         ELSE 'SIN_OBRA' END AS via_obra,
    ra.documento_id AS documento_id
    FROM apuntes ap
    LEFT JOIN cierres_cuenta cc ON cc.cuenta_id = ap.cuenta_id AND cc.ejercicio = ap.ejercicio - 1
    LEFT JOIN maestro.centros_coste cc_apu ON cc_apu.centro_coste_id = ap.centro_coste_id
    LEFT JOIN rac_asiento ra ON ra.asiento_id = ap.asiento_id
    LEFT JOIN efectos_factura ef ON ef.documento_id = ra.documento_id AND ef.num_centros = 1
    LEFT JOIN maestro.centros_coste cc_fac ON cc_fac.centro_coste_id = NULLIF(ef.centro_coste_id, 0)
    LEFT JOIN raw.pag efe ON efe.ide = ra.documento_id
    LEFT JOIN maestro.centros_coste cc_efe ON cc_efe.centro_coste_id = NULLIF(efe.cenide, 0)
    LEFT JOIN proveedor_una_obra pu ON pu.proveedor_id = ap.proveedor_id
    LEFT JOIN maestro.centros_coste cc_prv ON cc_prv.centro_coste_id = pu.centro_coste_id
)
SELECT
    r.apunte_id,
    r.asiento_id,
    r.fecha,
    r.ejercicio,
    r.cuenta_id,
    r.codigo_cuenta,
    r.proveedor_id,
    r.concepto,
    r.importe_alta,
    r.importe_baja,
    r.importe,
    r.clase,
    r.es_prescripcion,
    r.centro_coste_id,
    r.obra_id,
    ob.emp                             AS empresa_id,
    ob.cod                             AS codigo_obra,
    ob.emp::text || '-' || ob.cod      AS clave_obra,
    ob.res                             AS nombre_obra,
    r.via_obra,
    r.documento_id
FROM resuelto r
LEFT JOIN raw.con ob ON ob.ide = r.obra_id;

ALTER TABLE retenciones.apuntes_contables ADD PRIMARY KEY (apunte_id);
CREATE INDEX idx_ret_apc_proveedor ON retenciones.apuntes_contables (proveedor_id);
CREATE INDEX idx_ret_apc_obra      ON retenciones.apuntes_contables (obra_id);
CREATE INDEX idx_ret_apc_clase     ON retenciones.apuntes_contables (clase);

COMMENT ON TABLE retenciones.apuntes_contables IS
'F-095. Una fila por apunte de raw.apu en las cuentas de retencion de '
'proveedor (retenciones.cuentas_proveedor), sin filtrar ninguno. importe = '
'haber - debe (positivo se retiene, negativo se devuelve o da de baja). clase: '
'CIERRE, APERTURA, SALDO_INICIAL (apertura sin cierre previo de la cuenta), '
'ALTA, BAJA; cierres y aperturas no se suman nunca. obra_id por cascada '
'(via_obra: APUNTE, FACTURA, EFECTO, PROVEEDOR_UNA_OBRA, SIN_OBRA), siempre '
'traducida por maestro.centros_coste, con su empresa y su clave_obra.';
