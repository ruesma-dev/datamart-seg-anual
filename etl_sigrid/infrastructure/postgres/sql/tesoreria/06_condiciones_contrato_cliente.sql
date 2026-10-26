-- etl_sigrid/infrastructure/postgres/sql/tesoreria/06_condiciones_contrato_cliente.sql
-- ============================================================================
-- F-140 · SCHEMA tesoreria (7/9): tesoreria.condiciones_contrato_cliente, LO
-- PACTADO CON EL CLIENTE (R11, D7-A)
--
-- GRANO: una fila por contrato con el cliente de `raw.obrctr` (970 contratos
-- de 450 obras el 2026-10-24), sin filtro.
--
-- QUE TRAE: obra, empresa (la de la obra: `obrctr` no la tiene), cliente, la
-- forma de COBRO (`raw.auxcob`, ingerida por F-140) con su formula leida (las
-- columnas de `tesoreria.plazos_forma_pago`) y la RETENCION que nos hace el
-- cliente: `coegar` (en tanto por cien: 5, 10) y, si no tiene, el porcentaje
-- del recargo `retide` (`raw.rec.valpor`, en tanto por uno, x 100), con
-- `retencion_fuente` (COEGAR o RECARGO) y el concepto del recargo. Medido: en
-- 492 contratos estan los dos y discrepan en 7; manda `coegar`. Y los plazos
-- de retencion y de garantia del contrato (`plaret`, `plagar`; 0 es «sin
-- plazo» y se publica NULL) y el inicio de garantia (`fecinigar`), tal cual.
-- `cobmeses` y `cobporret` estan a 0 en todos y no se publican.
--
-- De aqui lee `08_hipotesis_caja_obra.sql` los valores SIGRID de H09-H11
-- (D18-A), solo cuando los contratos de la obra dan uno solo.
--
-- `TRUNCATE` + `INSERT` en una transaccion: si falla, queda la de ayer.
--
-- Lee de: raw.obrctr, raw.con, raw.auxcob, raw.auxefc, raw.rec.
-- Escribe en: tesoreria.condiciones_contrato_cliente.
-- ============================================================================

TRUNCATE tesoreria.condiciones_contrato_cliente;

INSERT INTO tesoreria.condiciones_contrato_cliente (
    contrato_cliente_id, codigo_contrato, descripcion, empresa_id, obra_id,
    codigo_obra, cliente_id, cliente_nombre, forma_cobro_id,
    forma_cobro_codigo, forma_cobro, medio_cobro, plazo_formula,
    dias_vencimientos, num_vencimientos, dias_retencion, formula_reconocida,
    retencion_porcentaje, retencion_fuente, retencion_concepto,
    plazo_retencion_meses, plazo_garantia_meses, fecha_inicio_garantia
)
SELECT
    o.ide                                                    AS contrato_cliente_id,
    o.cod                                                    AS codigo_contrato,
    o.res                                                    AS descripcion,
    obr.emp                                                  AS empresa_id,
    NULLIF(o.obride, 0)                                      AS obra_id,
    obr.cod                                                  AS codigo_obra,
    NULLIF(o.cliide, 0)                                      AS cliente_id,
    cli.res                                                  AS cliente_nombre,
    NULLIF(o.pagide, 0)                                      AS forma_cobro_id,
    f.cod                                                    AS forma_cobro_codigo,
    f.res                                                    AS forma_cobro,
    m.res                                                    AS medio_cobro,
    f.formul                                                 AS plazo_formula,
    tesoreria.fn_plazo_dias(f.formul)                        AS dias_vencimientos,
    cardinality(tesoreria.fn_plazo_dias(f.formul))           AS num_vencimientos,
    tesoreria.fn_plazo_dias_retencion(f.formul)              AS dias_retencion,
    tesoreria.fn_plazo_reconocido(f.formul)                  AS formula_reconocida,
    CASE WHEN COALESCE(o.coegar, 0) <> 0 THEN ROUND(o.coegar::NUMERIC, 4)
         WHEN r.ide IS NOT NULL THEN ROUND((r.valpor * 100)::NUMERIC, 4)
    END                                                      AS retencion_porcentaje,
    CASE WHEN COALESCE(o.coegar, 0) <> 0 THEN 'COEGAR'
         WHEN r.ide IS NOT NULL THEN 'RECARGO'
    END                                                      AS retencion_fuente,
    x.res                                                    AS retencion_concepto,
    NULLIF(o.plaret, 0)                                      AS plazo_retencion_meses,
    NULLIF(o.plagar, 0)                                      AS plazo_garantia_meses,
    tesoreria.fn_fecha(o.fecinigar)                          AS fecha_inicio_garantia
FROM raw.obrctr o
LEFT JOIN raw.con obr ON obr.ide = NULLIF(o.obride, 0)
LEFT JOIN raw.con cli ON cli.ide = NULLIF(o.cliide, 0)
LEFT JOIN raw.auxcob f ON f.ide = NULLIF(o.pagide, 0)
LEFT JOIN raw.auxefc m ON m.ide = NULLIF(f.efeide, 0)
LEFT JOIN raw.rec r ON r.ide = NULLIF(o.retide, 0)
LEFT JOIN raw.con x ON x.ide = NULLIF(o.retide, 0);

COMMENT ON TABLE tesoreria.condiciones_contrato_cliente IS
'F-140. Lo pactado en cada contrato con el cliente (raw.obrctr): obra, cliente, forma de cobro con su formula leida, retencion que nos hace el cliente (coegar o, si no, el recargo retide; en tanto por cien, con su fuente), plazos de retencion y de garantia (0 es NULL) e inicio de garantia. Es un ingrediente: ningun plazo se aplica a ninguna fecha. Clave: contrato_cliente_id (obrctr.ide).';
