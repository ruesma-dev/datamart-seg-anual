-- etl_sigrid/infrastructure/postgres/sql/compras/15_alarmas_liquidatoria.sql
-- ============================================================================
-- F-138 · LAS ALARMAS DE LOS DOCUMENTOS DE SIGRID Y LA MARCA «LIQUIDATORIA»
--
-- En Sigrid la factura liquidatoria NO es un campo del documento: es una ALARMA
-- de texto libre pegada a él (`raw.conala`, con su tipo en `raw.auxala`). Este
-- fichero publica las alarmas y, sobre ellas, la marca de cada factura,
-- albarán, proforma y nota, y lo que responde para qué la quiere Negocio (D1):
-- si se han TERMINADO las facturas de un contrato, el IVA (ya no se difiere) y
-- el AVISO de una factura que llega DESPUÉS de la liquidatoria.
--
-- Construye, EN ESTE ORDEN (cada uno lee el anterior):
--   compras_restringida.documento_alarmas  todas las alarmas, con recursos y partes
--   compras.documento_alarmas              la general: sin recursos ni partes (D9)
--   compras.documento_liquidatoria         la marca de cada documento 14/15
--   compras.contrato_liquidacion           una fila por contrato: ¿terminado?
--   compras.facturas_tras_liquidacion      las facturas llegadas después del cierre
-- y dos funciones, `compras.fn_texto_normalizado` y `compras.fn_clase_liquidacion`.
--
-- LEE `raw.conala`, `raw.auxala`, `raw.con` y, de `compras`, las funciones de
-- `00_setup.sql` y lo que construye `01_documentos.sql` (contratos, albaranes,
-- facturas y sus líneas). NO TOCA NINGÚN OBJETO EXISTENTE (D7): `compras.facturas`,
-- `compras.albaranes` y `07_texto.sql` quedan como estaban; esto se cruza con
-- ellos por `documento_id`.
--
-- LOS LITERALES SON LOS DEL DOMINIO (`etl_sigrid/domain/liquidatoria.py`) y
-- `tests/test_f138_ingesta_sql.py` lo vigila: las familias (el `CASE` y el
-- `IN`), las restringidas, la traducción de caracteres y los cinco patrones en
-- su orden. Un cambio de la regla se hace allí y aquí, en el mismo commit.
--
-- LOS PATRONES NO LLEVAN `\b` NI `\w`: en PostgreSQL `\b` es RETROCESO, no
-- frontera de palabra. La frontera es `(^| )` sobre el texto normalizado.
--
-- UNA SOLA TRANSACCIÓN (una llamada a `execute_sql_file`): si una guarda
-- salta, se deshace todo y quedan las tablas de la noche anterior.
--
-- DATO PERSONAL: `creada_por` es el LOGIN de quien creó la alarma (D6, como
-- `subido_por` de F-090). Las alarmas de recursos (33) y partes (35) nombran
-- trabajadores y bajas: solo en `compras_restringida`, que el rol estándar no
-- lee (D9, `R-COMPRAS-RESTRINGIDA`).
-- ============================================================================

-- R14 · La guarda de ingesta. Sin ninguna alarma de factura en `raw.conala` la
-- ingesta no se ha hecho o ha fallado, y construir dejaría todas las marcas a
-- FALSE sin que nada avisara: un contrato «sin liquidatoria» no se distinguiría
-- de una tabla vacía. El sub-paso falla y quedan las tablas de ayer.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM raw.conala a
        JOIN raw.con c ON c.ide = a.conide AND c.tip = 15
    ) THEN
        RAISE EXCEPTION 'F-138 R14: raw.conala no tiene ninguna alarma de factura (con.tip = 15). La ingesta de conala no se ha hecho o ha fallado: python main.py ingest --table conala --full antes de reconstruir compras.';
    END IF;
END $$;

-- R5 · El texto normalizado: traducir vocales acentuadas, ü, ñ y ç; cada tramo
-- que no sea letra ASCII o cifra a UN espacio; mayúsculas; recortar. El `upper`
-- va DESPUÉS de dejar solo ASCII, para que el resultado no dependa de
-- `LC_CTYPE` y coincida con `normalizar()` del dominio.
CREATE OR REPLACE FUNCTION compras.fn_texto_normalizado(t TEXT)
RETURNS TEXT
LANGUAGE sql IMMUTABLE AS $$
    SELECT btrim(upper(regexp_replace(translate(COALESCE(t, ''), 'áéíóúàèìòùâêîôûäëïöüÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÄËÏÖÜñÑçÇ', 'aeiouaeiouaeiouaeiouAEIOUAEIOUAEIOUAEIOUnNcC'), '[^A-Za-z0-9]+', ' ', 'g')));
$$;

COMMENT ON FUNCTION compras.fn_texto_normalizado(TEXT) IS
'Texto normalizado de F-138 (R5): sin acentos, ni enes ni cedillas, todo lo que no es letra ASCII o cifra a un espacio, en mayusculas y recortado. NULL da cadena vacia. Es la base de fn_clase_liquidacion.';

-- R6 · La clase de UNA alarma (o de un memo). Sin mención de `LIQ`: REMITE si
-- remite a otro sitio («VER TEXTO», «MIRAR NOTA»), si no NULL. Con mención: la
-- primera que case de NEGADA, CARTA_LIQUIDACION y DUDOSA; si ninguna,
-- LIQUIDATORIA. Es `clasificar()` del dominio, rama a rama.
CREATE OR REPLACE FUNCTION compras.fn_clase_liquidacion(t TEXT)
RETURNS TEXT
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN x.n !~ '(^| )LIQ' THEN CASE
            WHEN x.n ~ '(^| )(VER|MIRAR) (EL )?(TEXTO|NOTA)( |$)' THEN 'REMITE'
        END
        WHEN x.n ~ '(^| )NO (ES |SERA )?([A-Z0-9]+ )?LIQ' THEN 'NEGADA'
        WHEN x.n ~ '(^| )CARTA (DE )?LIQ' THEN 'CARTA_LIQUIDACION'
        WHEN x.n ~ 'PREVISION|POSTERIOR|TIENE QUE VENIR|QUEDA PENDIENTE|NO SE SI' THEN 'DUDOSA'
        ELSE 'LIQUIDATORIA'
    END
    FROM (SELECT compras.fn_texto_normalizado(t) AS n) x;
$$;

COMMENT ON FUNCTION compras.fn_clase_liquidacion(TEXT) IS
'Clase de liquidacion de un texto libre de Sigrid (F-138, R6): LIQUIDATORIA, NEGADA, CARTA_LIQUIDACION, DUDOSA, REMITE (remite a VER TEXTO o VER NOTA) o NULL si no dice nada de liquidacion. Regla heuristica sobre el texto normalizado (fn_texto_normalizado).';


-- ---------------------------------------------------------------------------
-- compras_restringida.documento_alarmas — TODAS LAS ALARMAS (R11, R12)
--
-- Una fila por alarma de `raw.conala` cuyo documento está en `raw.con` y es de
-- una familia de `FAMILIAS_ALARMAS` (la ingesta ya filtra con esa lista: el
-- `WHERE` repite el fallo CERRADO aquí, para que una ingesta manual sin filtro
-- no publique alarmas de empleados). ~45.750 filas el 2026-10-14. Con
-- `restringido` y `motivo_restriccion`: recursos (33) y partes (35), D9.
-- `fec1`, `fec2`, `usu` y `rol` NO se publican: vacías o no fiables.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS compras_restringida.documento_alarmas CASCADE;
CREATE TABLE compras_restringida.documento_alarmas AS
WITH b AS (
    SELECT
        a.ide                                   AS alarma_id,
        a.conide                                AS documento_id,
        c.tip                                   AS tipo_documento_codigo,
        CASE c.tip
            WHEN 1 THEN 'INFORME'
            WHEN 4 THEN 'CLIENTE'
            WHEN 5 THEN 'PROVEEDOR'
            WHEN 11 THEN 'FACTURA_VENTA'
            WHEN 12 THEN 'OFERTA'
            WHEN 14 THEN 'ALBARAN'
            WHEN 15 THEN 'FACTURA'
            WHEN 17 THEN 'CUENTA_AUXILIAR'
            WHEN 20 THEN 'ASIENTO'
            WHEN 25 THEN 'EFECTO_PAGO'
            WHEN 33 THEN 'RECURSO'
            WHEN 35 THEN 'PARTE_TRABAJO'
            WHEN 40 THEN 'OTRA'
            WHEN 42 THEN 'OBRA'
            WHEN 44 THEN 'CONTRATO'
            WHEN 46 THEN 'COMPARATIVO'
            WHEN 54 THEN 'CONTRATO_VENTA'
        END::TEXT                               AS familia,
        -- El tipo de negocio solo donde `fn_tipo_documento` sabe darlo
        -- (FACTURA, ABONO, ALBARAN, PROFORMA, NOTA, CONTRATO); NULL en el resto.
        CASE WHEN c.tip IN (14, 15, 44) THEN compras.fn_tipo_documento(c.tip, compras.fn_serie(c.cod)) END
                                                AS tipo_documento,
        c.cod                                   AS codigo_documento,
        x.cod AS tipo_alarma_codigo,
        x.res AS tipo_alarma,
        a.tex AS texto,
        COALESCE(a.tipabr, 0) = 1 AS ver_al_abrir,
        -- R10: AAAAMMDD + HHMMSS. Fecha 0 o imposible (la vuelve NULL
        -- `fn_sigrid_date`) u hora 0 o imposible: NULL, como el oráculo.
        CASE WHEN a.crehor BETWEEN 1 AND 235959
              AND a.crehor % 10000 / 100 < 60
              AND a.crehor % 100 < 60
             THEN compras.fn_sigrid_date(a.crefec)
                  + make_interval(hours => a.crehor / 10000,
                                  mins => a.crehor % 10000 / 100,
                                  secs => a.crehor % 100)
        END AS creada_el,
        NULLIF(btrim(a.creusu), '') AS creada_por,
        compras.fn_clase_liquidacion(a.tex) AS clase_liquidacion,
        c.tip IN (33, 35) AS restringido
    FROM      raw.conala a
    JOIN      raw.con c ON c.ide = a.conide
    LEFT JOIN raw.auxala x ON x.ide = NULLIF(a.alaide, 0)
    WHERE     c.tip IN (1, 4, 5, 11, 12, 14, 15, 17, 20, 25, 33, 35, 40, 42, 44, 46, 54)
)
SELECT
    b.alarma_id,
    b.documento_id,
    b.tipo_documento_codigo,
    b.familia,
    b.tipo_documento,
    b.codigo_documento,
    b.tipo_alarma_codigo,
    b.tipo_alarma,
    b.texto,
    b.ver_al_abrir,
    b.creada_el,
    b.creada_por,
    b.clase_liquidacion,
    b.restringido,
    CASE WHEN b.restringido THEN b.familia END AS motivo_restriccion
FROM b;

ALTER TABLE compras_restringida.documento_alarmas ADD PRIMARY KEY (alarma_id);
CREATE INDEX ix_comr_documento_alarmas_documento ON compras_restringida.documento_alarmas (documento_id);
CREATE INDEX ix_comr_documento_alarmas_familia   ON compras_restringida.documento_alarmas (familia);

COMMENT ON TABLE compras_restringida.documento_alarmas IS
'ACCESO RESTRINGIDO: solo el perfil total del MCP; si no lo tienes, usa compras.documento_alarmas. Todas las alarmas de los documentos de Sigrid (F-138): una fila por alarma de raw.conala, con las de recursos (33) y partes de trabajo (35), que nombran trabajadores y bajas (restringido, motivo_restriccion). Clave alarma_id. No se suma con la general: ya la contiene.';


-- ---------------------------------------------------------------------------
-- compras.documento_alarmas — LA GENERAL (R11, D9)
--
-- La completa SIN las familias restringidas, con sus mismas columnas en el mismo
-- orden salvo `restringido` y `motivo_restriccion`. Es la que leen el MCP
-- estándar y Power BI.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS compras.documento_alarmas CASCADE;
CREATE TABLE compras.documento_alarmas AS
SELECT
    alarma_id,
    documento_id,
    tipo_documento_codigo,
    familia,
    tipo_documento,
    codigo_documento,
    tipo_alarma_codigo,
    tipo_alarma,
    texto,
    ver_al_abrir,
    creada_el,
    creada_por,
    clase_liquidacion
FROM compras_restringida.documento_alarmas
WHERE NOT restringido;

ALTER TABLE compras.documento_alarmas ADD PRIMARY KEY (alarma_id);
CREATE INDEX ix_com_documento_alarmas_documento ON compras.documento_alarmas (documento_id);
CREATE INDEX ix_com_documento_alarmas_familia   ON compras.documento_alarmas (familia);

COMMENT ON TABLE compras.documento_alarmas IS
'Alarmas de los documentos de Sigrid (F-138): una fila por alarma (raw.conala) de facturas, albaranes, contratos, facturas de venta, comparativos y el resto de familias, con su texto libre integro, su tipo (auxala), quien y cuando la creo y su clase de liquidacion. SIN las de recursos y partes de trabajo, que viven en compras_restringida (R-COMPRAS-RESTRINGIDA). Clave alarma_id.';

-- R14 · la guarda de la restricción. Recalcula desde `raw.con` (no desde la
-- columna `restringido`, que podría estar mal calculada) que la general no
-- tiene ninguna alarma de recursos o partes y que general + restringidas =
-- completa. Si no, el sub-paso falla y no se publica nada (patrón R12 de F-037).
DO $$
DECLARE
    v_indebidas    BIGINT;
    v_general      BIGINT;
    v_restringidas BIGINT;
    v_completa     BIGINT;
BEGIN
    SELECT count(*) INTO v_indebidas
    FROM compras.documento_alarmas g
    JOIN raw.con c ON c.ide = g.documento_id
    WHERE c.tip IN (33, 35);

    SELECT count(*) INTO v_general FROM compras.documento_alarmas;

    SELECT count(*) INTO v_restringidas
    FROM compras_restringida.documento_alarmas d
    JOIN raw.con c ON c.ide = d.documento_id
    WHERE c.tip IN (33, 35);

    SELECT count(*) INTO v_completa FROM compras_restringida.documento_alarmas;

    IF v_indebidas > 0 OR v_general + v_restringidas <> v_completa THEN
        RAISE EXCEPTION 'F-138 R14: compras.documento_alarmas tiene % alarmas de recursos o partes, y general (%) + restringidas (%) <> completa (%). No se publica: revisar FAMILIAS_RESTRINGIDAS y el CASE de restringido.', v_indebidas, v_general, v_restringidas, v_completa;
    END IF;
END $$;


-- ---------------------------------------------------------------------------
-- compras.documento_liquidatoria — LA MARCA DE CADA DOCUMENTO 14/15 (R15, R16)
--
-- Una fila por factura, abono, albarán, proforma o nota cuya marca de alarmas
-- (R9: la clase de mayor precedencia, NEGADA > LIQUIDATORIA > CARTA_LIQUIDACION
-- > DUDOSA > REMITE) o cuya clase del MEMO (`raw.con.tex`, prefiltrado con
-- `ILIKE '%liq%'`) no es NULL. Lee la GENERAL: 14 y 15 no son restringidas.
--
-- `cierra_contrato` = LIQUIDATORIA o CARTA_LIQUIDACION (la carta se pide cuando
-- la última factura no lo decía: cierra igual, pendiente de la carta). La
-- declarada gana a la carta. Los tres booleanos son FALSE, nunca NULL, en el
-- resto. El memo va APARTE (`clase_memo`, D5): no entra en los booleanos.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS compras.documento_liquidatoria CASCADE;
CREATE TABLE compras.documento_liquidatoria AS
WITH al AS (
    SELECT
        documento_id,
        CASE
            WHEN bool_or(clase_liquidacion = 'NEGADA') THEN 'NEGADA'
            WHEN bool_or(clase_liquidacion = 'LIQUIDATORIA') THEN 'LIQUIDATORIA'
            WHEN bool_or(clase_liquidacion = 'CARTA_LIQUIDACION') THEN 'CARTA_LIQUIDACION'
            WHEN bool_or(clase_liquidacion = 'DUDOSA') THEN 'DUDOSA'
            WHEN bool_or(clase_liquidacion = 'REMITE') THEN 'REMITE'
        END AS marca,
        string_agg(texto, ' | ' ORDER BY alarma_id) FILTER (WHERE clase_liquidacion IS NOT NULL) AS texto_alarmas,
        min(creada_el) FILTER (WHERE clase_liquidacion IN ('CARTA_LIQUIDACION', 'LIQUIDATORIA')) AS liquidacion_creada_el
    FROM compras.documento_alarmas
    WHERE tipo_documento_codigo IN (14, 15)
    GROUP BY documento_id
),
memo AS (
    SELECT
        c.ide AS documento_id,
        compras.fn_clase_liquidacion(c.tex) AS clase_memo
    FROM raw.con c
    WHERE c.tip IN (14, 15) AND c.tex ILIKE '%liq%'
),
universo AS (
    SELECT documento_id FROM al WHERE marca IS NOT NULL
    UNION
    SELECT documento_id FROM memo WHERE clase_memo IS NOT NULL
)
SELECT
    u.documento_id AS documento_id,
    c.tip AS tipo_documento_codigo,
    compras.fn_tipo_documento(c.tip, compras.fn_serie(c.cod)) AS tipo_documento,
    c.cod AS codigo_documento,
    compras.fn_sigrid_date(c.fec) AS fecha_alta,
    al.marca AS marca_liquidacion,
    COALESCE(al.marca = 'LIQUIDATORIA', FALSE) AS es_liquidatoria,
    COALESCE(al.marca = 'CARTA_LIQUIDACION', FALSE) AS pendiente_carta_liquidacion,
    COALESCE(al.marca IN ('CARTA_LIQUIDACION', 'LIQUIDATORIA'), FALSE) AS cierra_contrato,
    al.texto_alarmas AS texto_alarmas,
    -- La más antigua de sus alarmas que cierran, y solo si el DOCUMENTO cierra:
    -- con una alarma NEGADA al lado no hay fecha de liquidación que dar.
    CASE WHEN al.marca IN ('CARTA_LIQUIDACION', 'LIQUIDATORIA') THEN al.liquidacion_creada_el END AS liquidacion_creada_el,
    m.clase_memo AS clase_memo
FROM universo u
JOIN      raw.con c ON c.ide = u.documento_id
LEFT JOIN al        ON al.documento_id = u.documento_id
LEFT JOIN memo m    ON m.documento_id = u.documento_id;

ALTER TABLE compras.documento_liquidatoria ADD PRIMARY KEY (documento_id);
CREATE INDEX ix_com_documento_liquidatoria_tipo ON compras.documento_liquidatoria (tipo_documento);

COMMENT ON TABLE compras.documento_liquidatoria IS
'Marca liquidatoria de facturas, abonos, albaranes, proformas y notas (F-138): una fila por documento con alguna alarma o memo que hable de liquidacion. cierra_contrato = liquidatoria declarada o pendiente de carta de liquidacion. Regla heuristica sobre TEXTO LIBRE de una alarma de Sigrid: un documento sin fila no esta marcado, lo que no prueba que no sea liquidatorio (cobertura en el diccionario). Clave documento_id.';


-- ---------------------------------------------------------------------------
-- compras.contrato_liquidacion — ¿SE HAN TERMINADO LAS FACTURAS? (R17, R18)
--
-- UNA fila por contrato de `compras.contratos` (los 19.127; FALSE y no NULL los
-- que no tienen cierre). La factura llega al contrato por la MISMA cadena que
-- `fact_por_ctr` de `compras.v_pbi_contrato_consumo` (03_views.sql, copiada y
-- vigilada por un test): línea directa a contrato, o albarán de origen con su
-- contrato, o línea de albarán con contrato. Una factura puede colgar de varios
-- contratos (59 liquidatorias medidas): cuenta en cada uno.
--
-- FACTURA DE CIERRE = la de menor (`fecha`, `factura_id`) con `cierra_contrato`
-- (liquidatoria declarada o pendiente de carta). Desde ella ya no se difiere el
-- IVA y no debería llegar ninguna más: las que llegan son `num_facturas_posteriores`
-- y viven, una a una, en `compras.facturas_tras_liquidacion`.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS compras.contrato_liquidacion CASCADE;
CREATE TABLE compras.contrato_liquidacion AS
WITH fac_ctr AS (
    SELECT DISTINCT
        fl.factura_id,
        COALESCE(fl.contrato_id_directo, alb.contrato_id,
                 alb_l.contrato_id_linea) AS contrato_id
    FROM compras.factura_lineas fl
    LEFT JOIN compras.albaran_lineas alb_l ON alb_l.linea_id = fl.albaran_linea_id
    LEFT JOIN compras.albaranes alb        ON alb.albaran_id = alb_l.albaran_id
    WHERE COALESCE(fl.contrato_id_directo, alb.contrato_id,
                   alb_l.contrato_id_linea) IS NOT NULL
),
fac AS (
    SELECT
        fc.contrato_id,
        fc.factura_id,
        f.codigo_factura,
        f.fecha,
        COALESCE(dl.cierra_contrato, FALSE) AS cierra,
        COALESCE(dl.es_liquidatoria, FALSE) AS es_liquidatoria,
        COALESCE(dl.pendiente_carta_liquidacion, FALSE) AS pendiente_carta
    FROM fac_ctr fc
    JOIN      compras.facturas f ON f.factura_id = fc.factura_id
    LEFT JOIN compras.documento_liquidatoria dl ON dl.documento_id = fc.factura_id
),
cierre AS (
    SELECT DISTINCT ON (contrato_id)
        contrato_id, factura_id, codigo_factura, fecha, es_liquidatoria
    FROM fac
    WHERE cierra
    ORDER BY contrato_id, fecha, factura_id
),
ultima AS (
    SELECT DISTINCT ON (contrato_id)
        contrato_id, cierra
    FROM fac
    ORDER BY contrato_id, fecha DESC NULLS LAST, factura_id DESC
),
cuentas AS (
    SELECT
        contrato_id,
        count(*) FILTER (WHERE es_liquidatoria) AS num_facturas_liquidatorias,
        count(*) FILTER (WHERE pendiente_carta) AS num_facturas_carta_liquidacion
    FROM fac
    GROUP BY contrato_id
),
posteriores AS (
    SELECT f.contrato_id, count(*) AS num_facturas_posteriores
    FROM fac f
    JOIN cierre ci ON ci.contrato_id = f.contrato_id
    WHERE f.fecha > ci.fecha
    GROUP BY f.contrato_id
),
albaranes AS (
    -- Albaranes (AC) y proformas (PROF) liquidatorios del contrato, por la misma
    -- cadena que `lineas_alb` de la vista: cabecera o línea con contrato.
    SELECT x.contrato_id, count(DISTINCT x.albaran_id) AS num_albaranes_liquidatorios
    FROM (
        SELECT a.albaran_id, COALESCE(a.contrato_id, l.contrato_id_linea) AS contrato_id
        FROM compras.albaran_lineas l
        JOIN compras.albaranes a ON a.albaran_id = l.albaran_id
        WHERE a.tipo_documento IN ('ALBARAN', 'PROFORMA')
          AND COALESCE(a.contrato_id, l.contrato_id_linea) IS NOT NULL
    ) x
    JOIN compras.documento_liquidatoria dl
      ON dl.documento_id = x.albaran_id AND dl.es_liquidatoria
    GROUP BY x.contrato_id
)
SELECT
    k.contrato_id AS contrato_id,
    k.codigo_contrato AS codigo_contrato,
    k.obra_id AS obra_id,
    k.codigo_obra AS codigo_obra,
    ci.factura_id IS NOT NULL AS facturas_terminadas,
    CASE WHEN ci.factura_id IS NOT NULL THEN CASE WHEN ci.es_liquidatoria THEN 'LIQUIDATORIA' ELSE 'CARTA_LIQUIDACION' END END AS tipo_cierre,
    ci.factura_id AS factura_cierre_id,
    ci.codigo_factura AS codigo_factura_cierre,
    ci.fecha AS fecha_cierre,
    COALESCE(cu.num_facturas_liquidatorias, 0) AS num_facturas_liquidatorias,
    COALESCE(cu.num_facturas_carta_liquidacion, 0) AS num_facturas_carta_liquidacion,
    COALESCE(al.num_albaranes_liquidatorios, 0) AS num_albaranes_liquidatorios,
    COALESCE(po.num_facturas_posteriores, 0) AS num_facturas_posteriores,
    -- NULL si el contrato no tiene ninguna factura por la cadena.
    ul.cierra AS ultima_factura_cierra
FROM compras.contratos k
LEFT JOIN cierre ci ON ci.contrato_id = k.contrato_id
LEFT JOIN ultima ul ON ul.contrato_id = k.contrato_id
LEFT JOIN cuentas cu ON cu.contrato_id = k.contrato_id
LEFT JOIN posteriores po ON po.contrato_id = k.contrato_id
LEFT JOIN albaranes al ON al.contrato_id = k.contrato_id;

ALTER TABLE compras.contrato_liquidacion ADD PRIMARY KEY (contrato_id);
CREATE INDEX ix_com_contrato_liquidacion_obra ON compras.contrato_liquidacion (obra_id);

COMMENT ON TABLE compras.contrato_liquidacion IS
'Si se han terminado las facturas de cada contrato de compra (F-138): una fila por contrato de compras.contratos, con su factura de cierre (la primera liquidatoria o pendiente de carta de liquidacion por la cadena factura-contrato de v_pbi_contrato_consumo), cuantas facturas liquidatorias y albaranes o proformas liquidatorios tiene y cuantas facturas han llegado despues del cierre. facturas_terminadas nunca es NULL. Clave contrato_id.';


-- ---------------------------------------------------------------------------
-- compras.facturas_tras_liquidacion — EL AVISO (R19, D1 c)
--
-- UNA fila por (contrato, factura) con fecha de alta POSTERIOR a la de la
-- factura de cierre del contrato: lo que no debería haber llegado. ~1.170
-- filas el 2026-10-14. Se consulta sin cruzar nada.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS compras.facturas_tras_liquidacion CASCADE;
CREATE TABLE compras.facturas_tras_liquidacion AS
WITH fac_ctr AS (
    SELECT DISTINCT
        fl.factura_id,
        COALESCE(fl.contrato_id_directo, alb.contrato_id,
                 alb_l.contrato_id_linea) AS contrato_id
    FROM compras.factura_lineas fl
    LEFT JOIN compras.albaran_lineas alb_l ON alb_l.linea_id = fl.albaran_linea_id
    LEFT JOIN compras.albaranes alb        ON alb.albaran_id = alb_l.albaran_id
    WHERE COALESCE(fl.contrato_id_directo, alb.contrato_id,
                   alb_l.contrato_id_linea) IS NOT NULL
)
SELECT
    cl.contrato_id AS contrato_id,
    cl.codigo_contrato AS codigo_contrato,
    cl.obra_id AS obra_id,
    cl.codigo_obra AS codigo_obra,
    f.factura_id AS factura_id,
    f.codigo_factura AS codigo_factura,
    f.fecha AS fecha,
    f.fecha_factura AS fecha_factura,
    f.proveedor_id AS proveedor_id,
    f.proveedor_nombre AS proveedor_nombre,
    cl.factura_cierre_id AS factura_cierre_id,
    cl.codigo_factura_cierre AS codigo_factura_cierre,
    cl.fecha_cierre AS fecha_cierre,
    f.fecha - cl.fecha_cierre AS dias_tras_cierre,
    COALESCE(dl.cierra_contrato, FALSE) AS cierra_contrato
FROM fac_ctr fc
JOIN      compras.contrato_liquidacion cl ON cl.contrato_id = fc.contrato_id AND cl.facturas_terminadas
JOIN      compras.facturas f ON f.factura_id = fc.factura_id AND f.fecha > cl.fecha_cierre
LEFT JOIN compras.documento_liquidatoria dl ON dl.documento_id = f.factura_id;

ALTER TABLE compras.facturas_tras_liquidacion ADD PRIMARY KEY (contrato_id, factura_id);
CREATE INDEX ix_com_facturas_tras_liquidacion_obra ON compras.facturas_tras_liquidacion (obra_id);

COMMENT ON TABLE compras.facturas_tras_liquidacion IS
'Aviso de facturas llegadas despues de la liquidatoria (F-138): una fila por contrato y factura cuya fecha de alta es posterior a la de la factura de cierre del contrato (compras.contrato_liquidacion). dias_tras_cierre en dias naturales. Clave (contrato_id, factura_id).';
