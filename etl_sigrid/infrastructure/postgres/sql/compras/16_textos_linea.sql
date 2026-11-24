-- etl_sigrid/infrastructure/postgres/sql/compras/16_textos_linea.sql
-- ============================================================================
-- F-168 · El TEXTO LARGO de cada línea del flujo de obra (R12-R17):
--
--   · `compras.linea_texto`   — una fila por línea con texto: qué texto lleva
--                               (`texto_id`) y si es el de su partida o el de su
--                               línea de planificación
--   · `compras.textos`        — cada texto UNA vez (catálogo deduplicado)
--   · `compras.v_linea_texto` — las dos unidas: la línea con su texto
--
-- LAS CINCO FUENTES, todas de `raw` y cada una con su `tex` (la ingesta lo trae
-- cortado a 16000 caracteres y sin NUL):
--
--   NECESIDAD  raw.dncpro  la planificación de compras del jefe de obra;
--                          documento `dncide`, obra la de su `raw.dnc`
--   OFERTA     raw.dcopro  cada línea de oferta de un comparativo
--   CONTRATO   raw.ctrpro  líneas de contrato de compra
--   ALBARAN    raw.dcapro  líneas de albarán
--   FACTURA    raw.dcfpro  líneas de factura
--
-- En las cuatro últimas el documento es `docide`, la obra `obride` y la línea
-- de planificación de la que vienen, `dncproide`. La partida es `paride` en
-- todas. Cero es NULL. `linea_id` es el `ide` de su tabla: la clave es
-- (`tipo_linea`, `linea_id`), y con ella se llega desde `compras.contrato_lineas`,
-- `albaran_lineas`, `factura_lineas`, `comparativo_oferta_lineas`
-- (`linea_oferta_id`, tipo OFERTA) y `comparativo_lineas`
-- (`linea_necesidad_id`, tipo NECESIDAD). Las tablas de línea no cambian (D3).
--
-- POR QUÉ UN CATÁLOGO APARTE (D3, medido M3 y M4): el texto se COPIA por el
-- flujo (la oferta copia el 97 % de la planificación, el albarán el 99,9 % del
-- contrato, la factura el 99,6 % del albarán): 1,56 M líneas con texto son
-- ~207.000 textos distintos. Guardarlo una vez son ~152 MB; en cada línea,
-- ~900 MB.
--
-- `igual_a_partida` / `igual_a_necesidad` (R14) comparan el texto LIMPIO por su
-- `texto_id`: verdadero si es el mismo, falso si los dos existen y difieren, y
-- NULL si la línea no tiene partida (o planificación) o esa no tiene texto. Un
-- `CASE` y no un `=` a secas, que daría NULL donde toca falso. NUNCA se compara
-- por `linoriide`: no dice a qué tabla apunta (M3).
--
-- LA LIMPIEZA Y EL TOPE no se escriben aquí: son `stg.fn_texto_largo`,
-- `stg.fn_texto_id` y `stg.fn_texto_recortado` (stg/11_texto_largo.sql, R7).
--
-- Lee: raw.dncpro, raw.dnc, raw.dcopro, raw.ctrpro, raw.dcapro, raw.dcfpro y
-- stg.partida_texto (de esta noche: build_stg va antes en `run-all`; lanzado
-- suelto, lee la de anoche). Escribe: las tres de arriba.
--
-- UNA SOLA TRANSACCIÓN (R23): `execute_sql_file` lo manda en una llamada; si
-- algo falla, siguen publicadas las tablas de anoche.
-- ============================================================================

DROP TABLE IF EXISTS compras.linea_texto CASCADE;
DROP TABLE IF EXISTS compras.textos CASCADE;

-- Las líneas con texto limpio de las cinco fuentes, una vez: de aquí salen el
-- catálogo y las líneas. Temporal de la transacción: no se publica.
CREATE TEMP TABLE _f168_fuentes ON COMMIT DROP AS
WITH crudas AS (
    SELECT 'NECESIDAD'::TEXT AS tipo_linea, n.ide::BIGINT AS linea_id,
           n.dncide::BIGINT AS documento_id, d.obride::BIGINT AS obra_id,
           n.paride::BIGINT AS partida_id, NULL::BIGINT AS linea_necesidad_id, n.tex AS tex
    FROM raw.dncpro n
    LEFT JOIN raw.dnc d ON d.ide = n.dncide
    UNION ALL
    SELECT 'OFERTA'::TEXT AS tipo_linea, o.ide::BIGINT AS linea_id,
           o.docide::BIGINT AS documento_id, o.obride::BIGINT AS obra_id,
           o.paride::BIGINT AS partida_id, o.dncproide::BIGINT AS linea_necesidad_id, o.tex AS tex
    FROM raw.dcopro o
    UNION ALL
    SELECT 'CONTRATO'::TEXT AS tipo_linea, k.ide::BIGINT AS linea_id,
           k.docide::BIGINT AS documento_id, k.obride::BIGINT AS obra_id,
           k.paride::BIGINT AS partida_id, k.dncproide::BIGINT AS linea_necesidad_id, k.tex AS tex
    FROM raw.ctrpro k
    UNION ALL
    SELECT 'ALBARAN'::TEXT AS tipo_linea, a.ide::BIGINT AS linea_id,
           a.docide::BIGINT AS documento_id, a.obride::BIGINT AS obra_id,
           a.paride::BIGINT AS partida_id, a.dncproide::BIGINT AS linea_necesidad_id, a.tex AS tex
    FROM raw.dcapro a
    UNION ALL
    SELECT 'FACTURA'::TEXT AS tipo_linea, f.ide::BIGINT AS linea_id,
           f.docide::BIGINT AS documento_id, f.obride::BIGINT AS obra_id,
           f.paride::BIGINT AS partida_id, f.dncproide::BIGINT AS linea_necesidad_id, f.tex AS tex
    FROM raw.dcfpro f
)
SELECT
    c.tipo_linea                            AS tipo_linea,
    c.linea_id                              AS linea_id,
    c.documento_id                          AS documento_id,
    c.obra_id                               AS obra_id,
    c.partida_id                            AS partida_id,
    c.linea_necesidad_id                    AS linea_necesidad_id,
    x.texto                                 AS texto,
    stg.fn_texto_id(x.texto) AS texto_id,
    stg.fn_texto_recortado(c.tex) AS recortado
FROM crudas c
CROSS JOIN LATERAL (SELECT stg.fn_texto_largo(c.tex) AS texto) x
WHERE x.texto IS NOT NULL;

CREATE INDEX ON _f168_fuentes (tipo_linea, linea_id);
ANALYZE _f168_fuentes;

-- ---------------------------------------------------------------------------
-- EL CATÁLOGO (R15): cada texto que usa alguna línea, una vez. Si alguna de
-- sus líneas venía cortada de Sigrid, `recortado` es verdadero.
-- ---------------------------------------------------------------------------
CREATE TABLE compras.textos AS
SELECT DISTINCT ON (f.texto_id)
    f.texto_id                              AS texto_id,
    f.texto                                 AS texto,
    octet_length(f.texto)                   AS bytes,
    f.recortado                             AS recortado
FROM _f168_fuentes f
ORDER BY f.texto_id, f.recortado DESC;

ALTER TABLE compras.textos ADD PRIMARY KEY (texto_id);

-- ---------------------------------------------------------------------------
-- LAS LÍNEAS (R12-R14): sin el texto, con su `texto_id` y las dos igualdades.
-- Cero es NULL aquí, en la proyección publicada (en la temporal los enlaces
-- van tal cual: un 0 no casa con ninguna partida ni línea de planificación).
-- ---------------------------------------------------------------------------
CREATE TABLE compras.linea_texto AS
SELECT
    f.tipo_linea                            AS tipo_linea,
    f.linea_id                              AS linea_id,
    NULLIF(f.documento_id, 0) AS documento_id,
    NULLIF(f.obra_id, 0) AS obra_id,
    NULLIF(f.partida_id, 0) AS partida_id,
    NULLIF(f.linea_necesidad_id, 0) AS linea_necesidad_id,
    f.texto_id                              AS texto_id,
    CASE WHEN pt.texto_id IS NULL THEN NULL ELSE f.texto_id = pt.texto_id END AS igual_a_partida,
    CASE WHEN f.tipo_linea = 'NECESIDAD' OR nec.texto_id IS NULL THEN NULL ELSE f.texto_id = nec.texto_id END AS igual_a_necesidad
FROM _f168_fuentes f
LEFT JOIN stg.partida_texto pt ON pt.partida_id = f.partida_id
LEFT JOIN _f168_fuentes nec ON nec.tipo_linea = 'NECESIDAD' AND nec.linea_id = f.linea_necesidad_id;

ALTER TABLE compras.linea_texto ADD PRIMARY KEY (tipo_linea, linea_id);
CREATE INDEX idx_com_lintex_tid ON compras.linea_texto (texto_id);
CREATE INDEX idx_com_lintex_par ON compras.linea_texto (partida_id);
CREATE INDEX idx_com_lintex_nec ON compras.linea_texto (linea_necesidad_id);
CREATE INDEX idx_com_lintex_doc ON compras.linea_texto (documento_id);

-- ---------------------------------------------------------------------------
-- LA VISTA (R16): cada línea con su texto. `JOIN` y no `LEFT JOIN`: el catálogo
-- sale de las mismas fuentes, así que ninguna línea se queda sin su texto ni
-- se repite (`texto_id` es la clave del catálogo).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW compras.v_linea_texto AS
SELECT
    l.tipo_linea                            AS tipo_linea,
    l.linea_id                              AS linea_id,
    l.documento_id                          AS documento_id,
    l.obra_id                               AS obra_id,
    l.partida_id                            AS partida_id,
    l.linea_necesidad_id                    AS linea_necesidad_id,
    l.texto_id                              AS texto_id,
    l.igual_a_partida                       AS igual_a_partida,
    l.igual_a_necesidad                     AS igual_a_necesidad,
    t.texto                                 AS texto,
    t.bytes                                 AS bytes,
    t.recortado                             AS recortado
FROM compras.linea_texto l
JOIN compras.textos t ON t.texto_id = l.texto_id;

COMMENT ON TABLE compras.linea_texto IS
'F-168. Una fila por linea del flujo de obra con texto largo (NECESIDAD, OFERTA, CONTRATO, ALBARAN, FACTURA): su texto_id y si es el de su partida o el de su linea de planificacion. El texto, en compras.textos o en compras.v_linea_texto.';

COMMENT ON TABLE compras.textos IS
'F-168. Cada texto largo de las lineas del flujo de obra, una sola vez (texto_id = md5 del texto limpio). Se lee uniendo desde compras.linea_texto.';

COMMENT ON VIEW compras.v_linea_texto IS
'F-168. Cada linea del flujo de obra con su texto largo: compras.linea_texto unida a compras.textos.';
