-- etl_sigrid/infrastructure/postgres/sql/compras/14_documento_adjuntos.sql
-- ============================================================================
-- F-090 · `compras.documento_adjuntos`: EL ÍNDICE DE LOS FICHEROS ADJUNTOS de
-- facturas, contratos, comparativos, ofertas y albaranes (la pestaña «Gráficos
-- asociados» de Sigrid).
--
-- LA FUENTE: `raw.rcg`, el enlace documento <-> gráfico (`con` el documento,
-- `gra` el gráfico, `pos` la posición), y `raw.gra`, el gráfico (nombre del
-- fichero, descripción, fecha de alta AAAAMMDD, login de quien lo subió y `cod`,
-- la clave del binario). Las dos llegan FILTRADAS EN ORIGEN a las cinco familias
-- de compras (D2): `config/tables_sigrid.yaml`. Lee además `raw.con` (la familia
-- y el código del documento), `raw.comprv` (el comparativo de cada oferta) y
-- `compras.fn_sigrid_date` (de `00_setup.sql`).
--
-- UNA FILA POR ENLACE de `raw.rcg` (clave `adjunto_id` = `rcg.ide`: un mismo
-- gráfico cuelga a veces de varios documentos, 102 medidos) cuyo documento es de
-- una de las familias de `etl_sigrid/domain/documento_adjuntos.py::
-- FAMILIAS_ADJUNTOS` y cuyo gráfico está en `raw.gra` (JOIN, no LEFT JOIN: R11).
-- ~199.042 filas el 2026-10-09.
--
-- EL BINARIO NO ESTÁ AQUÍ NI SE LEE: vive en la base documental `ruesma_rep` de
-- Sigrid y lo sirve `sigrid-api` (`documents/read` con `cod_repositorio`). Este
-- SQL no nombra esa base ni las columnas de binario (`raw.gra` ni las tiene: se
-- excluyen en la ingesta). Compras suma ~81 GB, más que el disco de 64 GB.
--
-- LOS LITERALES SON LOS DEL DOMINIO y `tests/test_f090_ingesta_sql.py` lo
-- vigila: las familias (el `IN` de la guarda y de la tabla, y el `CASE` de
-- `familia`), las extensiones de cada clase (el `CASE` de `clase_fichero`) y la
-- expresión de la extensión (la misma que `extension()`).
--
-- NO TOCA NINGÚN OTRO OBJETO de `compras` (D6): `compras.facturas` y las tablas
-- de F-085/F-132 quedan como estaban; el índice se cruza con ellas por
-- `documento_id` y `comparativo_id`. Se reconstruye cada noche (DROP + CREATE),
-- como el resto de `compras`.
--
-- DATO PERSONAL: `subido_por` (y el sufijo de `cod_repositorio`) es el LOGIN de
-- quien subió el fichero (D3 del humano, 2026-10-09: login sí, nombre no).
-- ============================================================================

-- R15 · La guarda de huérfanos. `gra` se ingiere DETRÁS de `rcg`; si una
-- ingesta se queda a medias, muchos enlaces no encontrarían su gráfico y el JOIN
-- los tiraría en silencio. Por encima del 1 %, el sub-paso falla con la cifra.
DO $$
DECLARE
    v_huerf BIGINT;
    v_total BIGINT;
BEGIN
    SELECT count(*) FILTER (WHERE g.ide IS NULL), count(*)
      INTO v_huerf, v_total
    FROM      raw.rcg r
    JOIN      raw.con c ON c.ide = r.con AND c.tip IN (12, 14, 15, 44, 46)
    LEFT JOIN raw.gra g ON g.ide = r.gra;
    IF v_total > 0 AND v_huerf > v_total * 0.01 THEN
        RAISE EXCEPTION 'F-090 R15: % de % enlaces de raw.rcg de compras no tienen su grafico en raw.gra (mas del uno por ciento). La ingesta de gra o de rcg ha quedado a medias: reingerir las dos (rcg primero) antes de reconstruir compras.documento_adjuntos.', v_huerf, v_total;
    END IF;
END $$;

DROP TABLE IF EXISTS compras.documento_adjuntos CASCADE;
CREATE TABLE compras.documento_adjuntos AS
WITH base AS (
    SELECT
        r.ide                                   AS adjunto_id,
        r.con                                   AS documento_id,
        c.tip                                   AS tipo_documento_codigo,
        CASE c.tip
            WHEN 15 THEN 'FACTURA'
            WHEN 44 THEN 'CONTRATO'
            WHEN 46 THEN 'COMPARATIVO'
            WHEN 12 THEN 'OFERTA'
            WHEN 14 THEN 'ALBARAN'
        END::TEXT                               AS familia,
        c.cod                                   AS codigo_documento,
        -- R13: el comparativo es el propio documento; la oferta, el de su fila
        -- de `comprv` (`docide` es único: el LEFT JOIN no multiplica), como
        -- `compras.comparativo_ofertas`; NULL en el resto de familias.
        CASE c.tip WHEN 46 THEN r.con WHEN 12 THEN p.comide END
                                                AS comparativo_id,
        g.ide                                   AS grafico_id,
        g.cod                                   AS cod_repositorio,
        g.emp                                   AS empresa_repositorio,
        NULLIF(BTRIM(g.nom), '')                AS nombre_fichero,
        -- R8, `extension()`: el sufijo tras el ÚLTIMO punto, sin puntos ni
        -- espacios; NULL si no hay punto o el nombre acaba en punto.
        lower(substring(btrim(g.nom) from '\.([^.\s]+)$')) AS extension,
        NULLIF(BTRIM(g.res), '')                AS descripcion,
        compras.fn_sigrid_date(g.fec)           AS fecha_alta,
        NULLIF(BTRIM(g.usu), '')                AS subido_por,
        r.pos                                   AS posicion
    FROM      raw.rcg r
    JOIN      raw.con c ON c.ide = r.con AND c.tip IN (12, 14, 15, 44, 46)  -- FAMILIAS_ADJUNTOS
    JOIN      raw.gra g ON g.ide = r.gra                                     -- R11
    LEFT JOIN raw.comprv p ON p.docide = r.con AND c.tip = 12                -- R13
)
SELECT
    b.adjunto_id,
    b.documento_id,
    b.tipo_documento_codigo,
    b.familia,
    b.codigo_documento,
    b.comparativo_id,
    b.grafico_id,
    b.cod_repositorio,
    b.empresa_repositorio,
    b.nombre_fichero,
    b.extension,
    -- R9, `clase_fichero()`: la clase sale de la EXTENSIÓN (`gratipide` = 0 en
    -- el 100 % de compras). Las listas son `EXTENSIONES_POR_CLASE`.
    CASE
        WHEN b.extension IS NULL THEN 'SIN_EXTENSION'
        WHEN b.extension IN ('pdf') THEN 'PDF'
        WHEN b.extension IN ('xls', 'xlsx', 'xlsm', 'xlsb', 'csv') THEN 'EXCEL'
        WHEN b.extension IN ('doc', 'docx', 'rtf', 'odt') THEN 'WORD'
        WHEN b.extension IN ('msg', 'eml') THEN 'CORREO'
        WHEN b.extension IN ('jpg', 'jpeg', 'png', 'tif', 'tiff', 'gif', 'bmp') THEN 'IMAGEN'
        ELSE 'OTRO'
    END::TEXT                                   AS clase_fichero,
    b.descripcion,
    b.fecha_alta,
    b.subido_por,
    b.posicion
FROM base b;

ALTER TABLE compras.documento_adjuntos ADD PRIMARY KEY (adjunto_id);
CREATE INDEX ix_documento_adjuntos_documento   ON compras.documento_adjuntos (documento_id);
CREATE INDEX ix_documento_adjuntos_comparativo ON compras.documento_adjuntos (comparativo_id);

COMMENT ON TABLE compras.documento_adjuntos IS
'Indice de ficheros adjuntos (Graficos asociados de Sigrid) de facturas, contratos, comparativos, ofertas y albaranes (F-090): una fila por enlace documento-fichero (raw.rcg), con el nombre del fichero, su clase por extension, la fecha de alta y el login de quien lo subio. Clave adjunto_id (rcg.ide). El fichero NO esta en el datamart: vive en la base documental ruesma_rep de Sigrid y lo sirve sigrid-api (documents/read) con cod_repositorio. Que un documento no tenga fila es que Sigrid no tiene adjunto para el.';
