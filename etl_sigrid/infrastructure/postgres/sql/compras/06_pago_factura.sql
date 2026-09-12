-- etl_sigrid/infrastructure/postgres/sql/compras/06_pago_factura.sql
-- ============================================================================
-- La FORMA DE PAGO de la factura de compra y su control contra el contrato
-- (F-080, R16-R19 y R28-R30).
--
-- Dos vistas, y ninguna tabla: lo pesado ya está materializado en
-- `compras.vencimientos` (05) y en `compras.facturas` (01).
--
--   · `compras.v_facturas_pago`      — una fila por FACTURA
--   · `compras.v_control_forma_pago` — una fila por PAR (factura, contrato)
--
-- LA DIMENSIÓN DE FORMAS DE PAGO NO SE DUPLICA: se lee de
-- `compras.formas_pago` (F-073, `04_formas_pago.sql`), que ya resuelve
-- `raw.auxpag` + `raw.auxefp`. Leer `raw.auxpag` aquí otra vez es exactamente
-- lo que F-073 vino a evitar (R16, R20).
--
-- NO se tocan `compras.facturas` ni `compras.contratos` ni sus ficheros
-- (`01_documentos.sql`, `02_fact_linea.sql`, `03_views.sql`): son de F-067,
-- que los reescribe enteros (R21, DA-7). Aquí solo se leen.
--
-- Lee de: compras.facturas, compras.vencimientos, compras.factura_lineas,
--         compras.albaran_lineas, compras.albaranes, compras.contratos,
--         compras.formas_pago, raw.dcf, raw.ctr, raw.con, raw.auxnap,
--         raw.auxefp, raw.auxban.
-- ============================================================================

-- Las dos vistas se tiran antes de crearlas, y en orden inverso al de
-- dependencia: `CREATE OR REPLACE VIEW` falla si la lista de columnas cambia y
-- alguien cuelga de ella, y aquí el control cuelga del pago de la factura.
DROP VIEW IF EXISTS compras.v_control_forma_pago CASCADE;
DROP VIEW IF EXISTS compras.v_facturas_pago CASCADE;

-- ---------------------------------------------------------------------------
-- LA FORMA DE PAGO DE LA FACTURA (R16-R19)
-- ---------------------------------------------------------------------------
--
-- EL RESUMEN DE EFECTOS AGREGA ANTES DE UNIRSE (R19). Unir primero y agregar
-- después multiplicaría la cabecera por sus efectos: una factura con 16 —el
-- máximo medido— saldría 16 veces y cualquier importe de la cabecera se
-- contaría 16 veces con ella.
--
-- Y TODO IMPORTE AGREGADO FILTRA LOS EFECTOS DE BAJA (R39, R40). 76.215 de los
-- 195.510 efectos de factura (39 %) están anulados: el original que se dividió
-- sigue en la tabla junto a sus hijos. Sobre `FR25/04222`, sumar sin filtrar da
-- 288.123,92 en vez de los 92.478,49 que Sigrid enseña en la cabecera, y los
-- dos números parecen igual de plausibles.
CREATE OR REPLACE VIEW compras.v_facturas_pago AS
WITH efectos AS (
    SELECT factura_id,
        COUNT(*)                                        AS num_efectos,
        COUNT(*) FILTER (WHERE efecto_anulado)          AS num_efectos_anulados,
        -- «Pagado» es el estado 10 de `raw.conest` para `tip = 25` (medido:
        -- 106.262 efectos), no «tiene fecha real»: 62 % la tienen a 0 (R11).
        COUNT(*) FILTER (WHERE NOT efecto_anulado AND estado_pago_codigo = 10)
                                                        AS num_efectos_pagados,
        MIN(fecha_vencimiento) FILTER (WHERE NOT efecto_anulado)
                                                        AS primer_vencimiento,
        MAX(fecha_vencimiento) FILTER (WHERE NOT efecto_anulado)
                                                        AS ultimo_vencimiento,
        SUM(importe) FILTER (WHERE NOT efecto_anulado)
                                                        AS importe_efectos_vivos,
        SUM(importe) FILTER (WHERE NOT efecto_anulado AND estado_pago_codigo = 10)
                                                        AS importe_efectos_pagados
    FROM compras.vencimientos
    GROUP BY factura_id
)
SELECT
    fa.factura_id                           AS factura_id,
    fa.codigo_factura                       AS codigo_factura,
    fa.fecha                                AS fecha_factura,
    fa.proveedor_id                         AS proveedor_id,
    fa.proveedor_nombre                     AS proveedor_nombre,
    fp.forma_pago_id                        AS forma_pago_id,
    fp.codigo                               AS codigo_forma_pago,
    fp.nombre                               AS forma_pago,
    -- VERBATIM, y no es un número de días: `30 450R` es un valor real del
    -- catálogo. Quien necesite un plazo numérico lo decide en su feature (R17).
    fp.plazo_formula                        AS plazo_formula,
    -- La fórmula y las condiciones que guarda la PROPIA factura, que pueden no
    -- coincidir con las del catálogo. Van tal cual (R18).
    f.pagfor                                AS formula_pago_documento,
    f.pagtex                                AS condiciones_pago,
    NULLIF(f.efeide, 0)                     AS medio_pago_id,
    ef.res                                  AS medio_pago,
    na.res                                  AS naturaleza_pago,
    cue.cod                                 AS cuenta_contable,
    -- `dcf.banide` se publica SIN resolver: a qué tabla apunta no está medido,
    -- y en esta feature inventar un JOIN por parecido ya salió mal cuatro
    -- veces. El banco y la sucursal sí se resuelven, por la clave que T1 midió
    -- en `pag` (`banban`/`bansuc` -> `auxban.ide`), que `dcf` comparte.
    NULLIF(f.banide, 0)                     AS cuenta_transferencia_id,
    bb.res                                  AS banco,
    bs.res                                  AS sucursal,
    COALESCE(e.num_efectos, 0)              AS num_efectos,
    COALESCE(e.num_efectos_anulados, 0)     AS num_efectos_anulados,
    COALESCE(e.num_efectos_pagados, 0)      AS num_efectos_pagados,
    e.primer_vencimiento                    AS primer_vencimiento,
    e.ultimo_vencimiento                    AS ultimo_vencimiento,
    e.importe_efectos_vivos                 AS importe_efectos_vivos,
    e.importe_efectos_pagados               AS importe_efectos_pagados
FROM compras.facturas fa
JOIN raw.dcf f ON f.ide = fa.factura_id
LEFT JOIN compras.formas_pago fp ON fp.forma_pago_id = NULLIF(f.pagide, 0)
LEFT JOIN raw.auxefp ef  ON ef.ide  = NULLIF(f.efeide, 0)
LEFT JOIN raw.auxnap na  ON na.ide  = NULLIF(f.cypnatide, 0)
LEFT JOIN raw.con    cue ON cue.ide = NULLIF(f.cueide, 0)
LEFT JOIN raw.auxban bb  ON bb.ide  = NULLIF(f.banban, 0)
LEFT JOIN raw.auxban bs  ON bs.ide  = NULLIF(f.bansuc, 0)
-- LEFT JOIN y no JOIN: una factura sin efectos no se puede perder.
LEFT JOIN efectos e ON e.factura_id = fa.factura_id;

COMMENT ON VIEW compras.v_facturas_pago IS
'Forma de pago de la factura de compra, con el resumen de sus efectos. GRANO: '
'una fila por factura de compra. La forma de pago sale de dcf.pagide resuelto '
'contra compras.formas_pago (F-073); formula_pago_documento y '
'condiciones_pago son lo que guarda la propia factura y pueden no coincidir '
'con el catalogo. '
'TRAMPA 1: plazo_formula NO es un numero de dias, es la formula de Sigrid tal '
'cual -"30 450R" es un valor real-, asi que no se suma ni se compara como '
'cantidad. '
'TRAMPA 2: los importes agregados (importe_efectos_vivos, '
'importe_efectos_pagados) EXCLUYEN los efectos anulados, que son el 39 % de '
'los de factura; num_efectos en cambio los cuenta TODOS y num_efectos_'
'anulados dice cuantos son, para que la resta se pueda hacer. Un importe '
'sumado sobre compras.vencimientos sin ese filtro sale hasta tres veces mas '
'alto. '
'TRAMPA 3: pagado es el estado 10 del efecto (raw.conest, tip = 25), NO que '
'tenga fecha real: el 62 % de los efectos la tiene vacia. '
'cuenta_transferencia_id va sin resolver a proposito: a que tabla apunta '
'dcf.banide no esta medido.';

-- ---------------------------------------------------------------------------
-- EL CONTROL CONTRA EL CONTRATO (R28-R30)
-- ---------------------------------------------------------------------------
--
-- EL GRANO ES EL PAR (factura, contrato) Y NO LA FACTURA: una factura puede
-- tener líneas de varios contratos. El `DISTINCT` es lo que baja de la línea
-- al par; sin él saldría una fila por línea de factura (R28).
--
-- EL ENLACE factura -> contrato NO SE INVENTA: es la MISMA expresión
-- `COALESCE(fl.contrato_id_directo, alb.contrato_id, alb_l.contrato_id_linea)`
-- que ya usa `compras.v_pbi_contrato_consumo` en `03_views.sql`. Dos reglas
-- para la misma cosa divergen, y la segunda se descubre cuando las dos cifras
-- ya están en un informe (R28).
--
-- Y NO SE FILTRA POR DISCREPANCIA (R29): las que cuadran también salen, porque
-- «cuántas no cuadran» sin el denominador no significa nada.
CREATE OR REPLACE VIEW compras.v_control_forma_pago AS
WITH pares AS (
    SELECT DISTINCT fl.factura_id,
        COALESCE(fl.contrato_id_directo, alb.contrato_id,
                 alb_l.contrato_id_linea)  AS contrato_id
    FROM compras.factura_lineas fl
    LEFT JOIN compras.albaran_lineas alb_l ON alb_l.linea_id = fl.albaran_linea_id
    LEFT JOIN compras.albaranes alb        ON alb.albaran_id = alb_l.albaran_id
    WHERE COALESCE(fl.contrato_id_directo, alb.contrato_id,
                   alb_l.contrato_id_linea) IS NOT NULL
)
SELECT
    pa.factura_id                           AS factura_id,
    vf.codigo_factura                       AS codigo_factura,
    vf.fecha_factura                        AS fecha_factura,
    pa.contrato_id                          AS contrato_id,
    ct.codigo_contrato                      AS codigo_contrato,
    ct.obra_id                              AS obra_id,
    ct.codigo_obra                          AS codigo_obra,
    vf.proveedor_id                         AS proveedor_id,
    vf.proveedor_nombre                     AS proveedor_nombre,
    vf.forma_pago_id                        AS forma_pago_factura_id,
    vf.forma_pago                           AS forma_pago_factura,
    vf.plazo_formula                        AS plazo_formula_factura,
    fpc.forma_pago_id                       AS forma_pago_contrato_id,
    fpc.nombre                              AS forma_pago_contrato,
    fpc.plazo_formula                       AS plazo_formula_contrato,
    -- Comparable solo si las DOS partes declaran forma de pago; si falta una,
    -- no hay discrepancia que afirmar, y decir que coinciden seria mentir.
    (vf.forma_pago_id IS NOT NULL AND fpc.forma_pago_id IS NOT NULL)
                                            AS forma_pago_comparable,
    (vf.forma_pago_id IS NOT NULL AND fpc.forma_pago_id IS NOT NULL
     AND vf.forma_pago_id = fpc.forma_pago_id)
                                            AS forma_pago_coincide
FROM pares pa
JOIN compras.v_facturas_pago vf ON vf.factura_id = pa.factura_id
JOIN compras.contratos ct       ON ct.contrato_id = pa.contrato_id
-- La forma de pago del contrato se lee de `raw.ctr.pagide`: `compras.contratos`
-- no la publica todavia, y publicarla ahi es F-067 (R21, R28).
LEFT JOIN raw.ctr ctr           ON ctr.ide = pa.contrato_id
LEFT JOIN compras.formas_pago fpc ON fpc.forma_pago_id = NULLIF(ctr.pagide, 0);

COMMENT ON VIEW compras.v_control_forma_pago IS
'Forma de pago de la factura de compra enfrentada a la de su contrato. GRANO: '
'una fila por PAR (factura, contrato), y NO por factura: una factura con '
'lineas de dos contratos sale dos veces, asi que contar filas no cuenta '
'facturas. '
'El enlace factura -> contrato es el mismo que usa v_pbi_contrato_consumo '
'(linea directa al contrato, o via el albaran de origen). '
'NO FILTRA: las que cuadran salen igual, con forma_pago_coincide en cierto. '
'forma_pago_comparable dice si las dos partes declaran forma de pago; cuando '
'es falso, forma_pago_coincide es falso por falta de dato y no por conflicto. '
'FACTURAS FUERA: 85.324 de 165.759 facturas de compra (51,5 %, medido el '
'2026-09-11) no cuelgan de ningun contrato y por lo tanto NO aparecen aqui. '
'Esta vista no sirve para contar facturas de compra ni para juzgar cobertura '
'de contratacion: solo compara las que si tienen contrato.';
