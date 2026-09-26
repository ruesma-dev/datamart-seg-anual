-- etl_sigrid/infrastructure/postgres/sql/contabilidad/02_mayor.sql
-- ============================================================================
-- F-056 · SCHEMA contabilidad (3/4): EL MAYOR, UNA FILA POR APUNTE
--
-- Construye:
--   contabilidad.mayor   una fila por fila de raw.apu, SIN FILTRAR NINGUNA
--
-- Lee de raw.apu, raw.con (el asiento y el tercero), contabilidad.plan_cuentas
-- (la cuenta) y la vista maestro.centros_coste (centro -> obra). Nada mas (R2).
--
-- UNA FILA POR APUNTE (R13, R14, R24): 2.166.701 el 2026-09-26. `apunte_id` es
-- clave primaria y nada de lo que se une multiplica: el asiento, el tercero y
-- la cuenta se unen por su clave primaria; el centro, por `centro_coste_id`,
-- unico por construccion en `maestro.centros_coste` (F-073); los cierres, por
-- un conjunto con DISTINCT. El asiento va con LEFT JOIN (hoy 0 apuntes sin
-- asiento): un JOIN seria un filtro. Al final, una guarda compara el recuento
-- con `raw.apu` y hace fallar el build con las dos cifras (R14). El fichero
-- corre en UNA transaccion: si la guarda salta, se deshace entero y queda el
-- mayor de la noche anterior.
--
-- LAS DOS FECHAS (R15, D6): `fecha` es `apu.fec` (el mayor de Sigrid se indexa
-- por cuenta y `apu.fec`) y `fecha_asiento` la del asiento por los dos saltos
-- (`apu.asiide` -> `raw.con.fec`). Coinciden en 2.166.404; las 297 que no, de
-- 2017, llevan el ultimo dia del mes y el asiento el primero: `fecha_difiere`.
-- `ejercicio` y `mes` salen de `fecha`.
--
-- LA EMPRESA (R16) es la del ASIENTO; la de la cuenta coincide en el 100 %.
-- Un `cueide = 0` (294 apuntes, todos de importe cero) deja la cuenta a NULL y
-- el apunte dentro.
--
-- IMPORTE (R17): `importe = debe - haber`, positivo = saldo deudor.
--
-- CLASE DEL ASIENTO (R18), en este orden y sin distinguir mayusculas:
--   CIERRE          `apu.cla = 3` o el concepto empieza por 'asiento de cierre'
--   SALDO_INICIAL   apertura (`cla = -1` o 'asiento de apertura...') de una
--                   cuenta SIN cierre en el ejercicio anterior: 1.433 apuntes
--                   (1.315 de 2008, lo anterior a Sigrid, y los arranques de
--                   empresas nuevas)
--   APERTURA        el resto de aperturas (= el cierre previo: 52.409 pares)
--   REGULARIZACION  `cla = 1` o 'asiento de regulariz...'
--   NORMAL          lo demas
-- `apu.cla` no basta: los cierres de 2020 y aperturas de 2021 (8.960) y 290
-- regularizaciones vienen con 0, y 124 aperturas en mayusculas escapan a un
-- LIKE sensible; de ahi el ILIKE. `asi.ori` NO sirve (0 en 788.326 de
-- 788.328). Los cierres van como anti-join contra un conjunto (cuenta,
-- ejercicio) DISTINCT, como en F-095: un NOT EXISTS correlacionado no se
-- hashea.
--
-- EL SALDO (R19, R20): `importe_saldo` = `importe` en NORMAL, REGULARIZACION y
-- SALDO_INICIAL, y 0 en CIERRE y APERTURA (sumarlos duplica). `saldo_acumulado`
-- es la suma de `importe_saldo` de la cuenta hasta el apunte inclusive, en el
-- orden fecha, codigo de asiento, posicion, apunte.
--
-- LA OBRA (R21) sale SOLO del centro del apunte (`apu.cenide`) traducido por
-- `maestro.centros_coste`. Sin centro, o con un centro que no es obra
-- (estructura, delegacion) -> NULL: no se reparte ni se busca por otra via.
-- El campo de obra del apunte (142 filas) y el de obra del centro (a 0) estan
-- VETADOS. La clave legible de la obra es '<empresa>-<codigo>'
-- (R-CODIGO-POR-EMPRESA; la empresa del centro es la de su obra).
--
-- EL TERCERO (R22): `apu.empide` (47,5 % de los apuntes; 998.686 a un
-- proveedor), con su nombre de `raw.con`.
-- ============================================================================

DROP TABLE IF EXISTS contabilidad.mayor CASCADE;
CREATE TABLE contabilidad.mayor AS
WITH apuntes AS (
    SELECT
        a.ide                                                    AS apunte_id,
        a.asiide                                                 AS asiento_id,
        asi.cod                                                  AS codigo_asiento,
        a.pos                                                    AS posicion,
        contabilidad.fn_fecha(a.fec)                             AS fecha,
        contabilidad.fn_fecha(asi.fec)                           AS fecha_asiento,
        asi.emp                                                  AS empresa_id,
        NULLIF(a.cueide, 0)                                      AS cuenta_id,
        a.res                                                    AS concepto,
        a.doc                                                    AS documento,
        a.pun                                                    AS punteo,
        a.cla                                                    AS clase_origen,
        COALESCE(a.deb, 0)::NUMERIC(18, 2)                       AS debe,
        COALESCE(a.hab, 0)::NUMERIC(18, 2)                       AS haber,
        (COALESCE(a.deb, 0) - COALESCE(a.hab, 0))::NUMERIC(18, 2) AS importe,
        CASE WHEN a.cla = 3 OR a.res ILIKE 'asiento de cierre%' THEN 'CIERRE'
             WHEN a.cla = -1 OR a.res ILIKE 'asiento de apertura%' THEN 'APERTURA'
             WHEN a.cla = 1 OR a.res ILIKE 'asiento de regulariz%' THEN 'REGULARIZACION'
             ELSE 'NORMAL' END                                   AS clase_bruta,
        NULLIF(a.cenide, 0)                                      AS centro_coste_id,
        NULLIF(a.empide, 0)                                      AS tercero_id
    FROM raw.apu a
    LEFT JOIN raw.con asi ON asi.ide = a.asiide
),
fechados AS (
    SELECT
        ap.*,
        EXTRACT(YEAR FROM ap.fecha)::INT                         AS ejercicio,
        EXTRACT(MONTH FROM ap.fecha)::INT                        AS mes
    FROM apuntes ap
),
-- Las cuentas con cierre en cada ejercicio: una fila por (cuenta, ejercicio),
-- DISTINCT para que el anti-join de SALDO_INICIAL no multiplique
cierres AS (
    SELECT DISTINCT f.cuenta_id, f.ejercicio
    FROM fechados f
    WHERE f.clase_bruta = 'CIERRE'
),
clasificados AS (
    SELECT
        f.*,
        CASE WHEN f.clase_bruta = 'APERTURA' AND ci.cuenta_id IS NULL THEN 'SALDO_INICIAL'
             ELSE f.clase_bruta END                              AS clase_asiento
    FROM fechados f
    LEFT JOIN cierres ci ON ci.cuenta_id = f.cuenta_id AND ci.ejercicio = f.ejercicio - 1
),
saldos AS (
    SELECT
        c.*,
        CASE WHEN c.clase_asiento IN ('CIERRE', 'APERTURA') THEN 0::NUMERIC(18, 2)
             ELSE c.importe END                                  AS importe_saldo
    FROM clasificados c
)
SELECT
    s.apunte_id,
    s.asiento_id,
    s.codigo_asiento,
    s.posicion,
    s.fecha,
    s.fecha_asiento,
    (s.fecha IS DISTINCT FROM s.fecha_asiento)                   AS fecha_difiere,
    s.ejercicio,
    s.mes,
    s.empresa_id,
    s.cuenta_id,
    pc.codigo_cuenta,
    pc.nombre_cuenta,
    pc.clave_cuenta,
    s.concepto,
    s.documento,
    s.punteo,
    s.clase_origen,
    s.clase_asiento,
    s.debe,
    s.haber,
    s.importe,
    s.importe_saldo,
    SUM(s.importe_saldo) OVER (
        PARTITION BY s.cuenta_id
        ORDER BY s.fecha, s.codigo_asiento, s.posicion, s.apunte_id
    )::NUMERIC(18, 2)                                            AS saldo_acumulado,
    s.centro_coste_id,
    cc.obra_id,
    cc.codigo_obra,
    cc.empresa::TEXT || '-' || cc.codigo_obra                    AS clave_obra,
    s.tercero_id,
    ter.res                                                      AS tercero_nombre
FROM saldos s
LEFT JOIN contabilidad.plan_cuentas pc ON pc.cuenta_id = s.cuenta_id
LEFT JOIN maestro.centros_coste cc ON cc.centro_coste_id = s.centro_coste_id
LEFT JOIN raw.con ter ON ter.ide = s.tercero_id;

ALTER TABLE contabilidad.mayor ADD PRIMARY KEY (apunte_id);
CREATE INDEX idx_con_mayor_empresa_cuenta_fecha ON contabilidad.mayor (empresa_id, codigo_cuenta, fecha);
CREATE INDEX idx_con_mayor_cuenta_fecha         ON contabilidad.mayor (cuenta_id, fecha);
CREATE INDEX idx_con_mayor_asiento              ON contabilidad.mayor (asiento_id);
CREATE INDEX idx_con_mayor_obra                 ON contabilidad.mayor (obra_id);
CREATE INDEX idx_con_mayor_tercero              ON contabilidad.mayor (tercero_id);

COMMENT ON TABLE contabilidad.mayor IS
'F-056. El mayor contable: una fila por apunte de raw.apu, sin filtrar ninguno. fecha = la del apunte (apu.fec) y fecha_asiento la del asiento (difieren en 297); empresa del asiento; cuenta de contabilidad.plan_cuentas; importe = debe - haber. clase_asiento: CIERRE, SALDO_INICIAL, APERTURA, REGULARIZACION, NORMAL. El saldo es importe_saldo (0 en CIERRE y APERTURA) y saldo_acumulado; sumar importe sin filtrar la clase duplica. obra_id solo por el centro del apunte (maestro.centros_coste).';

-- R14: el mayor tiene EXACTAMENTE las filas de raw.apu, o el build falla
DO $$
DECLARE
    v_mayor BIGINT;
    v_apu   BIGINT;
BEGIN
    SELECT count(*) INTO v_mayor FROM contabilidad.mayor;
    SELECT count(*) INTO v_apu FROM raw.apu;
    IF v_mayor <> v_apu THEN
        RAISE EXCEPTION 'mayor: contabilidad.mayor tiene % filas y raw.apu tiene %; un apunte se ha perdido o multiplicado', v_mayor, v_apu;
    END IF;
END $$;
