-- etl_sigrid/infrastructure/postgres/sql/tesoreria/04_plazos_forma_pago.sql
-- ============================================================================
-- F-140 · SCHEMA tesoreria (5/9): tesoreria.plazos_forma_pago, LAS FORMAS DE
-- PAGO Y DE COBRO CON SU FORMULA LEIDA (R9)
--
-- GRANO: una fila por forma de PAGO (`raw.auxpag`, 70) y por forma de COBRO
-- (`raw.auxcob`, 52, D7-A), sin filtro: las de baja se publican con su
-- `fecha_baja`. La clave es (`sentido`, `forma_id`): los dos catalogos tienen
-- su propia numeracion.
--
-- LA FORMULA, TAL CUAL Y LEIDA. `plazo_formula` es el texto de Sigrid VERBATIM
-- (`30 60 90`, `120 450R`); las funciones de `00_setup.sql` la leen en dias de
-- cada vencimiento (en el orden escrito), dias de la retencion (`NR`) y si se
-- reconoce. Una formula que no casa con la gramatica NO se interpreta: falla
-- cerrado (`formula_reconocida` falso, sin dias ni retencion). Medido el
-- 2026-10-24: las 122 casan.
--
-- ES UN INGREDIENTE, NO UNA FECHA DE PAGO: aqui no se suma ningun plazo a
-- ninguna fecha (R16). Aplicarlo es una hipotesis de quien consulta (H02, H05,
-- H15 de `tesoreria.hipotesis_caja`).
--
-- Vista y no tabla: 122 filas de catalogo, se lee siempre al dia.
--
-- Lee de: raw.auxpag, raw.auxefp, raw.auxcob, raw.auxefc.
-- Escribe en: tesoreria.plazos_forma_pago (vista).
-- ============================================================================

CREATE OR REPLACE VIEW tesoreria.plazos_forma_pago AS
SELECT
    'PAGO'::VARCHAR(5)                                       AS sentido,
    f.ide                                                    AS forma_id,
    f.cod                                                    AS codigo,
    f.res                                                    AS nombre,
    NULLIF(f.efeide, 0)                                      AS medio_id,
    m.res                                                    AS medio,
    f.formul                                                 AS plazo_formula,
    tesoreria.fn_plazo_dias(f.formul)                        AS dias_vencimientos,
    cardinality(tesoreria.fn_plazo_dias(f.formul))           AS num_vencimientos,
    tesoreria.fn_plazo_dias_retencion(f.formul)              AS dias_retencion,
    tesoreria.fn_plazo_reconocido(f.formul)                  AS formula_reconocida,
    tesoreria.fn_fecha(f.fecbaj)                             AS fecha_baja
FROM raw.auxpag f
LEFT JOIN raw.auxefp m ON m.ide = NULLIF(f.efeide, 0)

UNION ALL

SELECT
    'COBRO'::VARCHAR(5)                                      AS sentido,
    f.ide                                                    AS forma_id,
    f.cod                                                    AS codigo,
    f.res                                                    AS nombre,
    NULLIF(f.efeide, 0)                                      AS medio_id,
    m.res                                                    AS medio,
    f.formul                                                 AS plazo_formula,
    tesoreria.fn_plazo_dias(f.formul)                        AS dias_vencimientos,
    cardinality(tesoreria.fn_plazo_dias(f.formul))           AS num_vencimientos,
    tesoreria.fn_plazo_dias_retencion(f.formul)              AS dias_retencion,
    tesoreria.fn_plazo_reconocido(f.formul)                  AS formula_reconocida,
    tesoreria.fn_fecha(f.fecbaj)                             AS fecha_baja
FROM raw.auxcob f
LEFT JOIN raw.auxefc m ON m.ide = NULLIF(f.efeide, 0);

COMMENT ON VIEW tesoreria.plazos_forma_pago IS
'F-140. Formas de PAGO (auxpag) y de COBRO (auxcob) con su formula de plazo de Sigrid tal cual (plazo_formula) y leida: dias de cada vencimiento en el orden escrito, dias del efecto de retencion (NR) y si se reconoce. Sin reconocer, sin dias ni retencion. Es un ingrediente: ningun plazo se aplica a ninguna fecha. Clave: sentido + forma_id.';
