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
