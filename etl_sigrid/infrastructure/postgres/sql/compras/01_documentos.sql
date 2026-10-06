-- etl_sigrid/infrastructure/postgres/sql/compras/01_documentos.sql
-- ============================================================================
-- Documentos de compra tipados: contratos, albaranes (AC/PROF/NTC) y
-- facturas (FR/AB), con cabecera + líneas y trazabilidad resuelta.
--
-- Convenciones Sigrid aplicadas:
--   · cod / res / fec del documento viven en con (mismo ide), NO en la
--     extensión (dca/dcf/ctr).
--   · Proveedor: entide (FK a con) en la extensión; nombre via con.res.
--   · Obra y partida vienen EN LA LÍNEA (dcapro.obride/paride,
--     dcfpro.obride/paride). En contrato la obra está en cabecera
--     (ctr.obride) y la partida en línea (ctrpro.paride).
--   · Trazabilidad por línea: linoriide + docoritip
--       44 = la línea origen es de contrato (ctrpro)
--       14 = la línea origen es de albarán (dcapro)
--   · Importes tot = línea SIN IVA. ivacuo aparte.
--
-- F-083 (2026-09-16) · LO ÚNICO QUE ESTA FEATURE TOCA AQUÍ, y a propósito lo
-- mínimo, porque este fichero es de F-067 y F-067 lo reescribirá entero: el
-- bloque FACTURAS gana CINCO columnas al final —`estado_id`, `estado_codigo`,
-- `estado`, `fecha_factura` y `fecha_alta`—. Ni una de las diez de siempre se
-- toca, se renombra ni cambia de sitio: `compras.facturas` ya está en
-- producción y la consumen Power BI y el MCP.
--
--   · EL ESTADO DE LA FACTURA NO ES EL ESTADO DEL EFECTO. Lo que
--     `compras.vencimientos` publica como `estado_pago` es el estado del
--     EFECTO de pago (`con.est` con `tip = 25`); esto de aquí es el estado del
--     DOCUMENTO en el circuito de aprobación (CON contabilizada, APJO aprobada
--     por jefe de obra, APRADM aprobada Administración, APR aprobado pago,
--     RECH rechazada). Confundirlos es lo que originó esta feature: un listado
--     de «facturas sin aprobar» hecho con `estado_pago` mide otra cosa.
--   · Y NO ESTÁ EN `dcf`: está en `con.est`, la superclase. Es la lección que
--     F-080 aprendió tres veces por las malas.
--   · La traducción va por la PAREJA (tipo de documento, estado): la misma
--     cifra significa otra cosa en una obra (42) o en un contrato (44). Misma
--     guarda que `maestro.obras` (F-073).
--   · LAS DOS FECHAS, separadas por decisión del humano el 2026-09-16: la de
--     la propia factura (`dcf.fecdoc`, la que el proveedor pone en su
--     documento) y la de alta en Sigrid (`con.fec`). Se separan en el 77,8 %
--     de las facturas. `fecha` se queda intacta y es la de ALTA.
--
-- F-084 (2026-09-16) · EL MISMO TRABAJO PARA EL CONTRATO. El bloque CONTRATOS
-- gana TRES columnas al final —`estado_id`, `estado_codigo` y `estado`—, leídas
-- igualmente de `con.est` y traducidas con `tip = 44`. Ni una de las doce de
-- siempre se toca.
--
--   · LA TRADUCCIÓN YA NO ESTÁ COPIADA. F-083 escribió su lateral a mano aquí;
--     F-084 lo factorizó en `compras.fn_estado_documento(p_tip, p_est)`
--     (`00_setup.sql`) y los DOS bloques la llaman con su tipo. Es el criterio
--     6 de la feature, y lo que se gana no son líneas: el tipo de documento
--     pasa a ser argumento obligatorio, así que la unión «solo por estado_id»
--     ya no se puede escribir.
--   · POR QUÉ HACÍA FALTA, y es el hallazgo caro de F-084. Compras pidió
--     perseguir «los contratos que llevan más de tres semanas enviados y sin
--     firmar». La vía natural parecía el circuito de firma, `raw.confir`, y
--     NO SIRVE: de sus 70.346 firmas hay **CERO de contrato** (son de
--     comparativos, facturas y obras). No es un fallo de la ingesta: en el
--     origen tampoco están. Luego esa pregunta SOLO se puede responder por el
--     ESTADO, y con los 818 contratos en «Enviado» se responde desde hoy.
--   · LO QUE SIGUE SIN PODERSE RESPONDER: cuánto lleva un contrato en su
--     estado. El datamart no guarda cuándo cambió, y `con.tiemod` es la última
--     modificación del DOCUMENTO, no la fecha del cambio de estado. La foto
--     diaria que lo daría de verdad es F-067; por eso F-084 no publica ninguna
--     columna de antigüedad, y la ficha lo dice en vez de insinuar un proxy.
--
-- F-067 (2026-10-06) · LAS CONDICIONES DEL CONTRATO. El bloque CONTRATOS gana
-- CINCO columnas al final —`forma_pago_id`, `forma_pago`,
-- `retencion_garantia_porcentaje`, `retencion_garantia_concepto` y
-- `fecha_ultima_modificacion`— y ni una de las quince de siempre se mueve.
--
--   · LA ANTIGÜEDAD DEL ESTADO YA SE SABE, pero NO aquí: la da la foto diaria
--     (`11_historial_estados.sql`, `compras.v_estado_documentos`) desde el día
--     del despliegue. `fecha_ultima_modificacion` es `con.tiemod`, la última
--     modificación del DOCUMENTO, y NO la fecha del cambio de estado (D2 del
--     humano): medido, la firma no la mueve en el 85 % de los comparativos.
--   · LA PENALIZACIÓN NO ES UN CAMPO de Sigrid (`ctr` no la tiene): solo
--     aparece en el texto del contrato, `compras.documento_texto`, en 9.
--
-- F-067 (con F-125, D3) · EL CÓDIGO 2 Y LA NECESIDAD DE COMPRA. Las TRES
-- tablas de líneas (contrato, albarán, factura) ganan al final
-- `codigo_alternativo` (`cod2`), `necesidad_id` (`dncide`) y
-- `necesidad_linea_id` (`dncproide`). El «código alternativo» de Sigrid es el
-- CÓDIGO 2: lo pone el jefe de obra para agrupar o filtrar sus compras en el
-- documento de planificación de compras (DPC, `raw.dnc`) y viaja de la línea
-- de necesidad al albarán (igual en el 99,9 % de las 295.210 enlazadas). El
-- enlace a la necesidad es DIRECTO por `dncide`/`dncproide`, no por
-- `docoritip`/`linoriide`: 378.010 de 1.162.871 líneas de albarán (32,5 %).
-- ============================================================================

-- ---------------------------------------------------------------------------
-- CONTRATOS
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS compras.contratos CASCADE;
CREATE TABLE compras.contratos AS
SELECT
    c.ide                                   AS contrato_id,
    con.cod                                 AS codigo_contrato,
    compras.fn_serie(con.cod)               AS serie,
    con.res                                 AS descripcion,
    compras.fn_sigrid_date(con.fec)         AS fecha,
    NULLIF(c.obride, 0)                     AS obra_id,
    obr_con.cod                             AS codigo_obra,
    obr_con.res                             AS nombre_obra,
    NULLIF(c.entide, 0)                     AS proveedor_id,
    prv_con.res                             AS proveedor_nombre,
    NULLIF(TRIM(c.entcif), '')              AS proveedor_cif,
    NULLIF(c.comide, 0)                     AS comparativo_id,
    -- A PARTIR DE AQUÍ, TODO LO QUE AÑADE F-084, Y VA AL FINAL A PROPÓSITO:
    -- `compras.contratos` ya está en producción y la consumen Power BI y el
    -- MCP. Intercalar `estado` junto a `descripcion` —que es donde se lee
    -- mejor— reordena las columnas de una tabla viva. Misma disciplina que
    -- F-073 en `maestro.obras` y F-083 en `compras.facturas`.
    con.est                                 AS estado_id,        -- código interno del tipo 44
    est.codigo_estado                       AS estado_codigo,    -- mnemónico: EPF, FIR, TER…
    est.nombre_estado                       AS estado,           -- estado_id ya traducido (tipo 44)
    -- F-067: las CONDICIONES del contrato y su última modificación, también
    -- AL FINAL y por el mismo motivo. Ver la cabecera del fichero.
    NULLIF(c.pagide, 0)                     AS forma_pago_id,    -- ctr.pagide -> auxpag
    pag.res                                 AS forma_pago,       -- nombre de la forma de pago
    ret.porcentaje                          AS retencion_garantia_porcentaje,  -- 5 = 5 %
    ret.concepto                            AS retencion_garantia_concepto,
    compras.fn_sigrid_tiempo(con.tiemod)    AS fecha_ultima_modificacion  -- NO es el cambio de estado
FROM raw.ctr c
JOIN raw.con con          ON con.ide = c.ide
LEFT JOIN raw.con obr_con ON obr_con.ide = NULLIF(c.obride, 0)
LEFT JOIN raw.con prv_con ON prv_con.ide = NULLIF(c.entide, 0)
-- F-067: de `raw.auxpag` y no de `compras.formas_pago`, que se construye en
-- `04_formas_pago.sql`, después de este fichero. LEFT: 9 de 19.081 contratos
-- no tienen forma de pago (medido el 2026-10-06).
LEFT JOIN raw.auxpag pag  ON pag.ide = NULLIF(c.pagide, 0)
-- La traducción del estado, con su tipo de documento y su guarda de grano,
-- vive UNA sola vez en `compras.fn_estado_documento` (`00_setup.sql`) y la
-- comparten este bloque y el de FACTURAS: es el criterio 6 de F-084.
-- `LEFT ... ON TRUE` porque un contrato cuyo estado no casara con el catálogo
-- se publica igual, con el literal a NULL. Hoy no le pasa a ninguno: 0
-- huérfanos de 18.978, medido el 2026-09-16.
LEFT JOIN LATERAL compras.fn_estado_documento(44, con.est) est ON TRUE
-- F-067 (R13): la RETENCIÓN DE GARANTÍA, de los recargos y retenciones del
-- contrato (`raw.ctrrec`) cuyo concepto tiene código `RET%`: 6.333 contratos
-- (558368 «Retención garantía 5 % (sobre base imponible)» en 6.172). Los demás
-- conceptos de `ctrrec` son IRPF o van sin código y NO son la retención. El
-- `LIMIT 1` con `ORDER BY` es la guarda de grano: hoy UN contrato tiene dos, y
-- gana la de menor `pos`. `valpor` viene en tanto por uno (0,05) y se publica
-- en tanto por cien (5). Va DETRÁS del lateral del estado, que `test_f084_sql`
-- lee como el primero; y sin `WHERE`, porque el FROM externo no puede tenerlo
-- (el universo de contratos no se filtra, F-084): la correlación va en el ON.
LEFT JOIN LATERAL (
    SELECT ROUND((r.valpor * 100)::NUMERIC, 4) AS porcentaje,
           x.res                               AS concepto
    FROM   raw.ctrrec r
    JOIN   raw.con x ON x.ide = r.recide
                    AND r.docide = c.ide
                    AND x.cod LIKE 'RET%'
    ORDER  BY r.pos, r.ide
    LIMIT  1
) ret ON TRUE;

ALTER TABLE compras.contratos ADD PRIMARY KEY (contrato_id);
CREATE INDEX idx_com_ctr_obra ON compras.contratos (obra_id);
CREATE INDEX idx_com_ctr_prv  ON compras.contratos (proveedor_id);
CREATE INDEX idx_com_ctr_est  ON compras.contratos (estado_id);

DROP TABLE IF EXISTS compras.contrato_lineas CASCADE;
CREATE TABLE compras.contrato_lineas AS
SELECT
    l.ide                                   AS linea_id,
    l.docide                                AS contrato_id,
    NULLIF(l.proide, 0)                     AS producto_id,
    l.res                                   AS descripcion,
    l.unimed                                AS unidad_medida,
    NULLIF(l.paride, 0)                     AS partida_id,
    NULLIF(l.cenide, 0)                     AS centro_coste_id,
    COALESCE(l.can, 0)::NUMERIC(20, 6)      AS cantidad,
    COALESCE(l.pre, 0)::NUMERIC(20, 6)      AS precio,
    COALESCE(l.tot, 0)::NUMERIC(18, 2)      AS importe,          -- sin IVA
    COALESCE(l.ivacuo, 0)::NUMERIC(18, 2)   AS cuota_iva,
    COALESCE(l.canser, 0)::NUMERIC(20, 6)   AS cantidad_servida,
    -- F-067 (D3): el CÓDIGO 2 y la NECESIDAD de compra, AL FINAL. Ver la
    -- cabecera del fichero. Vacío y 0 de Sigrid son NULL.
    NULLIF(btrim(l.cod2), '')               AS codigo_alternativo,  -- «código 2»
    NULLIF(l.dncide, 0)                     AS necesidad_id,        -- dnc: el DPC
    NULLIF(l.dncproide, 0)                  AS necesidad_linea_id   -- dncpro
FROM raw.ctrpro l
WHERE EXISTS (SELECT 1 FROM raw.ctr c WHERE c.ide = l.docide);

ALTER TABLE compras.contrato_lineas ADD PRIMARY KEY (linea_id);
CREATE INDEX idx_com_ctrlin_ctr ON compras.contrato_lineas (contrato_id);
CREATE INDEX idx_com_ctrlin_par ON compras.contrato_lineas (partida_id);

-- ---------------------------------------------------------------------------
-- ALBARANES (series AC = albarán, PROF = proforma/cert. subcontrata, NTC…)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS compras.albaranes CASCADE;
CREATE TABLE compras.albaranes AS
SELECT
    a.ide                                   AS albaran_id,
    con.cod                                 AS codigo_albaran,
    compras.fn_serie(con.cod)               AS serie,
    compras.fn_tipo_documento(14, compras.fn_serie(con.cod)) AS tipo_documento,
    con.res                                 AS descripcion,
    compras.fn_sigrid_date(con.fec)         AS fecha,
    NULLIF(a.ctride, 0)                     AS contrato_id,
    NULLIF(a.comide, 0)                     AS comparativo_id,
    NULLIF(a.entide, 0)                     AS proveedor_id,
    prv_con.res                             AS proveedor_nombre,
    NULLIF(TRIM(a.entcif), '')              AS proveedor_cif,
    NULLIF(TRIM(a.entref), '')              AS referencia_proveedor
FROM raw.dca a
JOIN raw.con con          ON con.ide = a.ide
LEFT JOIN raw.con prv_con ON prv_con.ide = NULLIF(a.entide, 0);

ALTER TABLE compras.albaranes ADD PRIMARY KEY (albaran_id);
CREATE INDEX idx_com_alb_ctr ON compras.albaranes (contrato_id);
CREATE INDEX idx_com_alb_prv ON compras.albaranes (proveedor_id);
CREATE INDEX idx_com_alb_tip ON compras.albaranes (tipo_documento);

DROP TABLE IF EXISTS compras.albaran_lineas CASCADE;
CREATE TABLE compras.albaran_lineas AS
SELECT
    l.ide                                   AS linea_id,
    l.docide                                AS albaran_id,
    NULLIF(l.obride, 0)                     AS obra_id,
    NULLIF(l.paride, 0)                     AS partida_id,
    NULLIF(l.proide, 0)                     AS producto_id,
    l.res                                   AS descripcion,
    l.unimed                                AS unidad_medida,
    NULLIF(l.cenide, 0)                     AS centro_coste_id,
    COALESCE(l.can, 0)::NUMERIC(20, 6)      AS cantidad,
    COALESCE(l.pre, 0)::NUMERIC(20, 6)      AS precio,
    COALESCE(l.tot, 0)::NUMERIC(18, 2)      AS importe,          -- sin IVA
    COALESCE(l.ivacuo, 0)::NUMERIC(18, 2)   AS cuota_iva,
    COALESCE(l.canfac, 0)::NUMERIC(20, 6)   AS cantidad_facturada,
    -- Trazabilidad a contrato (docoritip=44)
    CASE WHEN l.docoritip = 44 THEN NULLIF(l.linoriide, 0) END AS contrato_linea_id,
    CASE WHEN l.docoritip = 44 THEN NULLIF(l.docoriide, 0) END AS contrato_id_linea,
    -- Ratio facturado y pendiente de facturar (sin IVA).
    -- can=0: línea replicada no recibida (patrón Sigrid) o ajuste; si además
    -- tot=0, el pendiente es 0. Si canfac cubre can, pendiente 0 o negativo
    -- (sobrefacturación: se conserva el signo como información).
    CASE
        WHEN COALESCE(l.can, 0) = 0 THEN
            CASE WHEN COALESCE(l.canfac, 0) <> 0 THEN 0::NUMERIC(18,2)
                 ELSE COALESCE(l.tot, 0)::NUMERIC(18,2) END
        ELSE
            ROUND((COALESCE(l.tot, 0)
                   * (1 - COALESCE(l.canfac, 0) / l.can))::NUMERIC, 2)
    END                                     AS importe_pendiente_facturar,
    -- F-067 (D3): el CÓDIGO 2 y la NECESIDAD de compra, AL FINAL. Ver la
    -- cabecera del fichero. Vacío y 0 de Sigrid son NULL.
    NULLIF(btrim(l.cod2), '')               AS codigo_alternativo,  -- «código 2»
    NULLIF(l.dncide, 0)                     AS necesidad_id,        -- dnc: el DPC
    NULLIF(l.dncproide, 0)                  AS necesidad_linea_id   -- dncpro
FROM raw.dcapro l
WHERE EXISTS (SELECT 1 FROM raw.dca a WHERE a.ide = l.docide);

ALTER TABLE compras.albaran_lineas ADD PRIMARY KEY (linea_id);
CREATE INDEX idx_com_alblin_alb ON compras.albaran_lineas (albaran_id);
CREATE INDEX idx_com_alblin_obr ON compras.albaran_lineas (obra_id);
CREATE INDEX idx_com_alblin_par ON compras.albaran_lineas (partida_id);
CREATE INDEX idx_com_alblin_ctl ON compras.albaran_lineas (contrato_linea_id);
-- F-067: el albarán se cruza con su línea de necesidad (`descompuestos`, PLANIF_JO).
CREATE INDEX idx_com_alblin_ncl ON compras.albaran_lineas (necesidad_linea_id);

-- ---------------------------------------------------------------------------
-- FACTURAS (series FR/FRGG = factura, AB/ABGG = abono)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS compras.facturas CASCADE;
CREATE TABLE compras.facturas AS
SELECT
    f.ide                                   AS factura_id,
    con.cod                                 AS codigo_factura,
    compras.fn_serie(con.cod)               AS serie,
    compras.fn_tipo_documento(15, compras.fn_serie(con.cod)) AS tipo_documento,
    con.res                                 AS descripcion,
    compras.fn_sigrid_date(con.fec)         AS fecha,
    NULLIF(f.entide, 0)                     AS proveedor_id,
    prv_con.res                             AS proveedor_nombre,
    NULLIF(TRIM(f.entcif), '')              AS proveedor_cif,
    NULLIF(TRIM(f.entref), '')              AS referencia_proveedor,
    -- A PARTIR DE AQUÍ, TODO LO QUE AÑADE F-083, Y VA AL FINAL A PROPÓSITO.
    -- Esto es una tabla y PostgreSQL no obligaría, pero el consumidor sí:
    -- intercalar `estado` entre `tipo_documento` y `descripcion` —que es donde
    -- se lee mejor— reordena las columnas de una tabla que ya está en
    -- producción. Misma disciplina que F-073 en `maestro.obras`.
    con.est                                 AS estado_id,        -- código interno del tipo 15
    est.codigo_estado                       AS estado_codigo,    -- mnemónico: APR, CON, APJO…
    est.nombre_estado                       AS estado,           -- estado_id ya traducido (tipo 15)
    compras.fn_sigrid_date(f.fecdoc)        AS fecha_factura,    -- la del documento del proveedor
    compras.fn_sigrid_date(con.fec)         AS fecha_alta        -- la de alta en Sigrid (= `fecha`)
FROM raw.dcf f
JOIN raw.con con          ON con.ide = f.ide
LEFT JOIN raw.con prv_con ON prv_con.ide = NULLIF(f.entide, 0)
-- LEFT y no JOIN: una factura cuyo estado no casara con el catálogo se
-- publica igual, con el literal a NULL. Hoy no hay ninguna (0 huérfanas de
-- 165.866, medido el 2026-09-16), y por eso mismo un JOIN parecería inocente.
-- El `LIMIT 1` con `ORDER BY` es la guarda de grano: `(tip, est)` es único hoy
-- —21 de 21 en el tipo 15, ni un par repetido en las 193 filas del catálogo— y
-- esta tabla no puede depender de un dato de origen que nadie controla.
--
-- F-084 (2026-09-16): este lateral estaba escrito a mano aquí desde F-083, y
-- CONTRATOS necesitaba el mismo con otro tipo. En vez de copiarlo, la
-- traducción se factorizó en `compras.fn_estado_documento` (`00_setup.sql`),
-- que conserva el LEFT, el `ORDER BY` y el `LIMIT 1` intactos y además
-- convierte el tipo de documento en argumento obligatorio. La proyección de
-- arriba no cambia ni una letra: la función devuelve `codigo_estado` y
-- `nombre_estado`, los mismos nombres que tenía el lateral.
LEFT JOIN LATERAL compras.fn_estado_documento(15, con.est) est ON TRUE;

ALTER TABLE compras.facturas ADD PRIMARY KEY (factura_id);
CREATE INDEX idx_com_fac_est ON compras.facturas (estado_id);
CREATE INDEX idx_com_fac_prv ON compras.facturas (proveedor_id);
CREATE INDEX idx_com_fac_tip ON compras.facturas (tipo_documento);

DROP TABLE IF EXISTS compras.factura_lineas CASCADE;
CREATE TABLE compras.factura_lineas AS
SELECT
    l.ide                                   AS linea_id,
    l.docide                                AS factura_id,
    NULLIF(l.obride, 0)                     AS obra_id,
    NULLIF(l.paride, 0)                     AS partida_id,
    NULLIF(l.proide, 0)                     AS producto_id,
    l.res                                   AS descripcion,
    l.unimed                                AS unidad_medida,
    NULLIF(l.cenide, 0)                     AS centro_coste_id,
    COALESCE(l.can, 0)::NUMERIC(20, 6)      AS cantidad,
    COALESCE(l.pre, 0)::NUMERIC(20, 6)      AS precio,
    COALESCE(l.tot, 0)::NUMERIC(18, 2)      AS importe,          -- sin IVA
    COALESCE(l.ivacuo, 0)::NUMERIC(18, 2)   AS cuota_iva,
    -- Trazabilidad: a albarán (14) o directa a contrato (44)
    CASE WHEN l.docoritip = 14 THEN NULLIF(l.linoriide, 0) END AS albaran_linea_id,
    CASE WHEN l.docoritip = 14 THEN NULLIF(l.docoriide, 0) END AS albaran_id,
    CASE WHEN l.docoritip = 44 THEN NULLIF(l.linoriide, 0) END AS contrato_linea_id,
    CASE WHEN l.docoritip = 44 THEN NULLIF(l.docoriide, 0) END AS contrato_id_directo,
    -- F-067 (D3): el CÓDIGO 2 y la NECESIDAD de compra, AL FINAL. Ver la
    -- cabecera del fichero. Vacío y 0 de Sigrid son NULL.
    NULLIF(btrim(l.cod2), '')               AS codigo_alternativo,  -- «código 2»
    NULLIF(l.dncide, 0)                     AS necesidad_id,        -- dnc: el DPC
    NULLIF(l.dncproide, 0)                  AS necesidad_linea_id   -- dncpro
FROM raw.dcfpro l
WHERE EXISTS (SELECT 1 FROM raw.dcf f WHERE f.ide = l.docide);

ALTER TABLE compras.factura_lineas ADD PRIMARY KEY (linea_id);
CREATE INDEX idx_com_faclin_fac ON compras.factura_lineas (factura_id);
CREATE INDEX idx_com_faclin_obr ON compras.factura_lineas (obra_id);
CREATE INDEX idx_com_faclin_par ON compras.factura_lineas (partida_id);
CREATE INDEX idx_com_faclin_alb ON compras.factura_lineas (albaran_linea_id);
CREATE INDEX idx_com_faclin_ctl ON compras.factura_lineas (contrato_linea_id);
