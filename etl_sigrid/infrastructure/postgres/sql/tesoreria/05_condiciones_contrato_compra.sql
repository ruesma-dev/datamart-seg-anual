-- etl_sigrid/infrastructure/postgres/sql/tesoreria/05_condiciones_contrato_compra.sql
-- ============================================================================
-- F-140 · SCHEMA tesoreria (6/9): tesoreria.condiciones_contrato_compra, LO
-- PACTADO CON EL PROVEEDOR (R10)
--
-- GRANO: una fila por contrato de compra de `raw.ctr` (19.170 el 2026-10-24).
-- SALVO los de un tercero EMPLEADO (`con.tip = 43`): no se publican aqui (R10,
-- R18; medido: 0). El filtro es `IS DISTINCT FROM`, asi que un contrato sin
-- tercero se publica.
--
-- QUE TRAE: obra, empresa, proveedor, estado (traducido con el tipo 44 del
-- contrato), importe base e IVA de la cabecera (`totbas`, `totiva`, tal cual),
-- la forma de pago con su formula leida (las columnas de
-- `tesoreria.plazos_forma_pago`), los dias fijos de pago y los meses sin pago
-- del PROVEEDOR tal cual (`prv.pagdia` «15,30», `prv.pagmes` «8,12», D11-A) y
-- la RETENCION DE GARANTIA: el recargo del contrato (`raw.ctrrec`) de clase 4
-- o 5 (D8-A, el criterio de F-128; el `RETESP` es clase 1 y no entra), el de
-- menor `pos` si hubiera dos. `valpor` viene en tanto por uno y se publica en
-- tanto por cien. El plazo de devolucion NO esta en el contrato
-- (`rec.diavto = -99` en todas): es la `NR` de la formula o el fin de obra de
-- `retenciones.fin_obra` (hipotesis H07).
--
-- La forma de pago es la del catalogo (`auxpag`); `ctr.pagfor` copia su
-- formula en 19.151 de 19.161 contratos.
--
-- No lee `compras` (se construye despues y se dropea): `raw` directo, como
-- `compras.contratos`, con quien comparte `contrato_id`.
--
-- `TRUNCATE` + `INSERT` en una transaccion: si falla, queda la de ayer.
--
-- Lee de: raw.ctr, raw.con, raw.conest, raw.prv, raw.auxpag, raw.auxefp,
--         raw.ctrrec.
-- Escribe en: tesoreria.condiciones_contrato_compra.
-- ============================================================================

TRUNCATE tesoreria.condiciones_contrato_compra;

INSERT INTO tesoreria.condiciones_contrato_compra (
    contrato_id, codigo_contrato, empresa_id, obra_id, codigo_obra,
    proveedor_id, proveedor_nombre, estado_id, estado, importe_base,
    importe_iva, forma_pago_id, forma_pago_codigo, forma_pago, medio_pago,
    plazo_formula, dias_vencimientos, num_vencimientos, dias_retencion,
    formula_reconocida, proveedor_dias_fijos_pago, proveedor_meses_sin_pago,
    retencion_garantia_porcentaje, retencion_garantia_concepto,
    retencion_garantia_clase
)
SELECT
    c.ide                                                    AS contrato_id,
    con.cod                                                  AS codigo_contrato,
    con.emp                                                  AS empresa_id,
    NULLIF(c.obride, 0)                                      AS obra_id,
    obr.cod                                                  AS codigo_obra,
    NULLIF(c.entide, 0)                                      AS proveedor_id,
    t.res                                                    AS proveedor_nombre,
    con.est                                                  AS estado_id,
    ce.res                                                   AS estado,
    c.totbas::NUMERIC(18, 2)                                 AS importe_base,
    c.totiva::NUMERIC(18, 2)                                 AS importe_iva,
    NULLIF(c.pagide, 0)                                      AS forma_pago_id,
    f.cod                                                    AS forma_pago_codigo,
    f.res                                                    AS forma_pago,
    m.res                                                    AS medio_pago,
    f.formul                                                 AS plazo_formula,
    tesoreria.fn_plazo_dias(f.formul)                        AS dias_vencimientos,
    cardinality(tesoreria.fn_plazo_dias(f.formul))           AS num_vencimientos,
    tesoreria.fn_plazo_dias_retencion(f.formul)              AS dias_retencion,
    tesoreria.fn_plazo_reconocido(f.formul)                  AS formula_reconocida,
    NULLIF(btrim(prv.pagdia), '')                            AS proveedor_dias_fijos_pago,
    NULLIF(btrim(prv.pagmes), '')                            AS proveedor_meses_sin_pago,
    ret.porcentaje                                           AS retencion_garantia_porcentaje,
    ret.concepto                                             AS retencion_garantia_concepto,
    ret.clase                                                AS retencion_garantia_clase
FROM raw.ctr c
-- OBLIGATORIO: el contrato es un documento; su codigo, empresa y estado
-- estan en su fila de `raw.con`.
JOIN raw.con con           ON con.ide = c.ide
LEFT JOIN raw.con obr      ON obr.ide = NULLIF(c.obride, 0)
LEFT JOIN raw.con t ON t.ide = NULLIF(c.entide, 0)
LEFT JOIN raw.prv prv ON prv.ide = NULLIF(c.entide, 0)
LEFT JOIN raw.conest ce ON ce.tip = 44 AND ce.est = con.est
LEFT JOIN raw.auxpag f ON f.ide = NULLIF(c.pagide, 0)
LEFT JOIN raw.auxefp m ON m.ide = NULLIF(f.efeide, 0)
-- La garantia: clase 4 o 5, la de menor `pos` (guarda de grano).
LEFT JOIN LATERAL (
    SELECT ROUND((r.valpor * 100)::NUMERIC, 4) AS porcentaje,
           x.res                               AS concepto,
           r.reccla::INTEGER                   AS clase
    FROM raw.ctrrec r
    LEFT JOIN raw.con x ON x.ide = r.recide
    WHERE r.docide = c.ide AND r.reccla IN (4, 5) ORDER BY r.pos, r.ide LIMIT 1
) ret ON TRUE
WHERE t.tip IS DISTINCT FROM 43;

COMMENT ON TABLE tesoreria.condiciones_contrato_compra IS
'F-140. Lo pactado en cada contrato de compra (raw.ctr): obra, proveedor, estado, importe base e IVA, forma de pago con su formula leida (dias de cada vencimiento y de la retencion), dias fijos de pago y meses sin pago del proveedor tal cual, y retencion de garantia (clase 4 o 5, en tanto por cien). Sin los contratos de un tercero empleado. Es un ingrediente: ningun plazo se aplica a ninguna fecha. Clave: contrato_id, la de compras.contratos.';
