-- etl_sigrid/infrastructure/postgres/sql/contabilidad/08_mayor_analitico.sql
-- ============================================================================
-- F-127 · SCHEMA contabilidad (9/13): EL MAYOR ANALITICO COMPLETO
--
-- Construye:
--   contabilidad_restringida.mayor_analitico   una fila por fila de raw.apa
--                                              (el desglose analitico), SIN
--                                              FILTRAR NINGUNA, con la marca
--                                              de lo restringido
--
-- Lee de raw.apa, raw.con (el asiento y la cuenta analitica), raw.res y
-- raw.caa (las cuentas de contrapartida, C3), contabilidad_restringida.mayor
-- (02: el apunte financiero, su cuenta y su marca; C1 y C2) y la vista
-- maestro.centros_coste (centro -> obra). Va DETRAS de 02.
--
-- QUE ES (progress/spec_F-127.md): 722.631 filas el 2026-11-20, 2008-2026.
-- 639.034 cuelgan de un apunte financiero (`con.tip = 20`, el asiento
-- contable); 83.597 son de 5.766 asientos ANALITICOS puros (`con.tip = 32`,
-- codigo `ANA...`, sin apunte), los que imputan los partes a las obras y abonan
-- la cuenta de contrapartida (CP) del trabajador. La cuenta es ANALITICA (la
-- `caa` de `cueide`), no la del plan financiero.
--
-- EL SALDO SI ES `debe - haber`: la analitica no tiene cierres ni aperturas
-- (los 639.034 apuntes enlazados son NORMAL en el mayor). No es partida doble.
--
-- LA OBRA sale SOLO del centro de la fila analitica (`cenide`) por
-- maestro.centros_coste, como en el mayor financiero: ningun campo de obra,
-- origen, canal ni delegacion de la fila se lee (R4).
--
-- LA OBRA IMPUTADA (R6, D4): en un asiento ANALITICO, la UNICA obra a la que
-- cargan sus filas que no son de CP; con ninguna o con varias, NULL. Se publica
-- en todas las filas del asiento: es la obra del abono de la CP (37.202 de las
-- 38.612 filas CP medidas).
--
-- QUE FILA ES RESTRINGIDA (R7-R9; R23 de F-135, criterio V2), con los literales
-- del oraculo `etl_sigrid/domain/restriccion_personal.py` (un test los compara):
--   C1  su apunte financiero es restringido en el mayor completo
--   C2  su asiento es de personal: todos sus apuntes NORMAL y alguno
--       restringido en el mayor completo
--   C3  su cuenta analitica es una CP: la de algun recurso
--       (`raw.res.caaconide`) o, por D7-b, una cuenta del centro de una CP con
--       ABONO en un asiento ANALITICO (las CP de antes que el recurso ya no
--       declara: 7 cuentas, 324 filas). Falla cerrado: restringe DE MAS.
--   FALLA CERRADO (R9): una fila con apunte financiero que no esta en el mayor
--       completo se restringe con motivo APUNTE_SIN_RESOLVER (hoy 0).
-- `motivo_restriccion`, en este orden: CONTRAPARTIDA, APUNTE_SIN_RESOLVER,
-- APUNTE_RESTRINGIDO, ASIENTO_PERSONAL; NULL si es visible. Medido: 178.301
-- restringidas (24,7 %), 995 cuentas, 57 centros.
--
-- LOS ACUMULADOS (R5, R11): `saldo_acumulado` suma `importe` de la cuenta
-- analitica hasta la fila inclusive (fecha, codigo de asiento, posicion, fila);
-- `saldo_acumulado_visible` suma SOLO lo visible y es NULL en lo restringido:
-- es el `saldo_acumulado` del mayor analitico general (en las 106 cuentas
-- mixtas el completo delataria lo restringido).
--
-- UNA FILA POR FILA (R1, R2): `apunte_analitico_id` es clave primaria y nada
-- de lo que se une multiplica: el asiento, la cuenta y el apunte por su clave
-- primaria; las CP, los asientos de personal y la obra imputada son conjuntos
-- DISTINCT o agrupados por su clave. Todo va con LEFT JOIN. Al final, una
-- guarda compara el recuento con `raw.apa` y, si no casa, el fichero entero se
-- deshace (una transaccion) y queda la tabla de la noche anterior.
-- ============================================================================

DROP TABLE IF EXISTS contabilidad_restringida.mayor_analitico CASCADE;
CREATE TABLE contabilidad_restringida.mayor_analitico AS
WITH cp_recurso AS (
    -- C3: la CP actual de cada recurso
    SELECT DISTINCT r.caaconide AS cuenta_analitica_id
    FROM raw.res r
    WHERE r.caaconide <> 0
),
centros_cp AS (
    -- D7-b: los centros de coste de esas CP
    SELECT DISTINCT caa.cenide AS centro_coste_id
    FROM raw.caa caa
    JOIN cp_recurso c ON c.cuenta_analitica_id = caa.ide
    WHERE caa.cenide <> 0
),
cp AS (
    -- C3 con D7-b: las CP actuales y las cuentas de esos centros con abono en
    -- un asiento ANALITICO. UNION (no ALL): una fila por cuenta
    SELECT c.cuenta_analitica_id
    FROM cp_recurso c
    UNION
    SELECT a.cueide
    FROM raw.apa a
    JOIN raw.con asi ON asi.ide = a.conide
    JOIN raw.caa caa ON caa.ide = a.cueide
    JOIN centros_cp cc ON cc.centro_coste_id = caa.cenide
    WHERE asi.tip = 32 AND COALESCE(a.hab, 0) <> 0
),
asientos_personal AS (
    -- C2: los asientos de personal del mayor completo, una fila por asiento
    SELECT m.asiento_id
    FROM contabilidad_restringida.mayor m
    WHERE m.asiento_id IS NOT NULL
    GROUP BY m.asiento_id
    HAVING bool_and(m.clase_asiento = 'NORMAL') AND bool_or(m.restringido)
),
ana_obra AS (
    -- R6 (D4): la unica obra de las filas no CP de cada asiento ANALITICO
    SELECT
        a.conide                                                 AS asiento_id,
        CASE WHEN COUNT(DISTINCT o.obra_id) = 1 THEN MAX(o.obra_id) END AS obra_imputada_id,
        CASE WHEN COUNT(DISTINCT o.obra_id) = 1 THEN MAX(o.empresa::TEXT || '-' || o.codigo_obra) END AS clave_obra_imputada
    FROM raw.apa a
    JOIN raw.con asi ON asi.ide = a.conide
    LEFT JOIN cp ON cp.cuenta_analitica_id = a.cueide
    LEFT JOIN maestro.centros_coste o ON o.centro_coste_id = NULLIF(a.cenide, 0)
    WHERE asi.tip = 32 AND cp.cuenta_analitica_id IS NULL
    GROUP BY a.conide
),
base AS (
    SELECT
        a.ide                                                    AS apunte_analitico_id,
        NULLIF(a.conide, 0)                                      AS asiento_id,
        asi.tip                                                  AS tipo_con,
        asi.cod                                                  AS codigo_asiento,
        a.pos                                                    AS posicion,
        contabilidad.fn_fecha(a.fec)                             AS fecha,
        EXTRACT(YEAR FROM contabilidad.fn_fecha(a.fec))::INT     AS ejercicio,
        EXTRACT(MONTH FROM contabilidad.fn_fecha(a.fec))::INT    AS mes,
        asi.emp                                                  AS empresa_id,
        NULLIF(a.cenide, 0)                                      AS centro_coste_id,
        NULLIF(a.cueide, 0)                                      AS cuenta_analitica_id,
        a.res                                                    AS concepto,
        a.doc                                                    AS documento,
        a.pun                                                    AS punteo,
        COALESCE(a.deb, 0)::NUMERIC(18, 2)                       AS debe,
        COALESCE(a.hab, 0)::NUMERIC(18, 2)                       AS haber,
        (COALESCE(a.deb, 0) - COALESCE(a.hab, 0))::NUMERIC(18, 2) AS importe,
        NULLIF(a.apuide, 0)                                      AS apunte_id
    FROM raw.apa a
    LEFT JOIN raw.con asi ON asi.ide = a.conide
),
marcados AS (
    SELECT
        b.*,
        ca.cod                                                   AS codigo_cuenta_analitica,
        ca.res                                                   AS descripcion_cuenta_analitica,
        m.cuenta_id,
        m.codigo_cuenta,
        ao.obra_imputada_id,
        ao.clave_obra_imputada,
        (cp.cuenta_analitica_id IS NOT NULL)                     AS es_contrapartida,
        (b.apunte_id IS NOT NULL AND m.apunte_id IS NULL)        AS es_apunte_sin_resolver,
        COALESCE(m.restringido, FALSE)                           AS es_apunte_restringido,
        (ap.asiento_id IS NOT NULL)                              AS es_asiento_personal
    FROM base b
    LEFT JOIN raw.con ca ON ca.ide = b.cuenta_analitica_id
    LEFT JOIN contabilidad_restringida.mayor m ON m.apunte_id = b.apunte_id
    LEFT JOIN cp ON cp.cuenta_analitica_id = b.cuenta_analitica_id
    LEFT JOIN asientos_personal ap ON ap.asiento_id = b.asiento_id
    LEFT JOIN ana_obra ao ON ao.asiento_id = b.asiento_id
),
clasificadas AS (
    SELECT
        mk.*,
        (mk.es_contrapartida OR mk.es_apunte_sin_resolver OR mk.es_apunte_restringido OR mk.es_asiento_personal) AS restringido
    FROM marcados mk
)
SELECT
    s.apunte_analitico_id,
    s.asiento_id,
    CASE WHEN s.tipo_con = 20 THEN 'CONTABLE'
         WHEN s.tipo_con = 32 THEN 'ANALITICO'
         ELSE 'OTRO' END                                         AS tipo_asiento,
    s.codigo_asiento,
    s.posicion,
    s.fecha,
    s.ejercicio,
    s.mes,
    s.empresa_id,
    s.centro_coste_id,
    cc.codigo_centro,
    cc.obra_id,
    cc.codigo_obra,
    cc.empresa::TEXT || '-' || cc.codigo_obra                    AS clave_obra,
    s.cuenta_analitica_id,
    s.codigo_cuenta_analitica,
    s.descripcion_cuenta_analitica,
    s.es_contrapartida                                           AS es_contrapartida_recurso,
    s.concepto,
    s.documento,
    s.punteo,
    s.debe,
    s.haber,
    s.importe,
    SUM(s.importe) OVER (
        PARTITION BY s.cuenta_analitica_id
        ORDER BY s.fecha, s.codigo_asiento, s.posicion, s.apunte_analitico_id
    )::NUMERIC(18, 2)                                            AS saldo_acumulado,
    s.apunte_id,
    s.cuenta_id,
    s.codigo_cuenta,
    s.obra_imputada_id,
    s.clave_obra_imputada,
    s.restringido,
    CASE WHEN s.es_contrapartida THEN 'CONTRAPARTIDA'
         WHEN s.es_apunte_sin_resolver THEN 'APUNTE_SIN_RESOLVER'
         WHEN s.es_apunte_restringido THEN 'APUNTE_RESTRINGIDO'
         WHEN s.es_asiento_personal THEN 'ASIENTO_PERSONAL' END  AS motivo_restriccion,
    CASE WHEN s.restringido THEN NULL
         ELSE SUM(s.importe) FILTER (
                  WHERE NOT s.restringido
              ) OVER (
                  PARTITION BY s.cuenta_analitica_id
                  ORDER BY s.fecha, s.codigo_asiento, s.posicion, s.apunte_analitico_id
              ) END::NUMERIC(18, 2)                              AS saldo_acumulado_visible
FROM clasificadas s
LEFT JOIN maestro.centros_coste cc ON cc.centro_coste_id = s.centro_coste_id;

ALTER TABLE contabilidad_restringida.mayor_analitico ADD PRIMARY KEY (apunte_analitico_id);
CREATE INDEX idx_con_mana_cuenta_fecha         ON contabilidad_restringida.mayor_analitico (cuenta_analitica_id, fecha);
CREATE INDEX idx_con_mana_empresa_cuenta_fecha ON contabilidad_restringida.mayor_analitico (empresa_id, codigo_cuenta_analitica, fecha);
CREATE INDEX idx_con_mana_obra                 ON contabilidad_restringida.mayor_analitico (obra_id);
CREATE INDEX idx_con_mana_obra_imputada        ON contabilidad_restringida.mayor_analitico (obra_imputada_id);
CREATE INDEX idx_con_mana_apunte               ON contabilidad_restringida.mayor_analitico (apunte_id);
CREATE INDEX idx_con_mana_asiento              ON contabilidad_restringida.mayor_analitico (asiento_id);
-- las restringidas son ~25 %: el indice parcial las encuentra sin recorrer todo
CREATE INDEX idx_con_mana_restringido          ON contabilidad_restringida.mayor_analitico (restringido) WHERE restringido;

COMMENT ON TABLE contabilidad_restringida.mayor_analitico IS
'F-127. El mayor ANALITICO COMPLETO, solo para el rol autorizado: una fila por fila de raw.apa (el desglose analitico), sin filtrar ninguna. tipo_asiento CONTABLE (cuelga de un apunte financiero, apunte_id) o ANALITICO (asiento ANA sin apunte: imputa los partes a las obras y abona la CP). Cuenta ANALITICA (no la del plan financiero); obra solo por el centro (maestro.centros_coste) y obra_imputada_id la del asiento ANALITICO. importe = debe - haber y saldo_acumulado por cuenta analitica: aqui no hay cierres ni aperturas. restringido, motivo_restriccion (CONTRAPARTIDA, APUNTE_SIN_RESOLVER, APUNTE_RESTRINGIDO, ASIENTO_PERSONAL) y saldo_acumulado_visible. No se suma con contabilidad_restringida.mayor.';

-- R2: el mayor analitico completo tiene EXACTAMENTE las filas de raw.apa, o
-- el build falla y se deshace
DO $$
DECLARE
    v_mayor BIGINT;
    v_apa   BIGINT;
BEGIN
    SELECT count(*) INTO v_mayor FROM contabilidad_restringida.mayor_analitico;
    SELECT count(*) INTO v_apa FROM raw.apa;
    IF v_mayor <> v_apa THEN
        RAISE EXCEPTION 'mayor_analitico: contabilidad_restringida.mayor_analitico tiene % filas y raw.apa tiene %; una fila se ha perdido o multiplicado', v_mayor, v_apa;
    END IF;
END $$;
