-- etl_sigrid/infrastructure/postgres/sql/postventa/06_adjuntos.sql
-- ============================================================================
-- F-156 · `postventa.documento_adjuntos` (R19-R21): EL ÍNDICE DE LOS FICHEROS
-- ADJUNTOS de unidades, incidencias y tareas (los «Gráficos asociados» de
-- Sigrid), con el mismo mecanismo que el índice de compras (F-090).
--
-- UNA FILA POR ENLACE de `raw.rcg` (clave `adjunto_id` = `rcg.ide`, única
-- también frente al índice de compras: es la misma tabla de Sigrid) cuyo
-- documento es de tipo 707, 708 o 47 y cuyo gráfico está en `raw.gra` (JOIN).
-- 15.986 enlaces el 2026-11-03, todos de la empresa 1.
--
-- FAMILIA (R20, `familia_adjunto` del dominio):
--   UNIDAD      documento 707 (sobre todo PV006, ficha del inmueble)
--   TAREA       documento 47 (PV004, informes)
--   REPARACION  documento 708 con clase de gráfico 35 (PV002 «Fotos
--               Reparaciones»): el PARTE FIRMADO por el cliente, con su DNI
--               MANUSCRITO dentro. `abrir_adjunto` del MCP lo ata a
--               `postventa_restringida`: solo lo abren el perfil postventa y
--               el total (D9). Las FILAS de este índice sí las ven todos.
--   INCIDENCIA  el resto de 708 (PV001 fotos de incidencias, sin clase...)
--
-- `extension` y `clase_fichero` son EXACTAMENTE las expresiones del índice de
-- compras (un test lo compara). `empresa_repositorio` sale de `g.emp` ENTERA:
-- es el contrato con `abrir_adjunto` (F-145). EL BINARIO NO ESTÁ AQUÍ: lo
-- sirve `sigrid-api` por la pareja (empresa_repositorio, cod_repositorio).
--
-- DATO PERSONAL: `subido_por` es el LOGIN de quien subió el fichero.
-- Lee `raw.rcg`, `raw.gra`, `raw.con`, `raw.auxgra`, `raw.rcp` y `raw.tar`.
-- ============================================================================

-- R21 · La guarda de huérfanos (como F-090 R15): `gra` se ingiere DETRÁS de
-- `rcg`; si más del 1 % de los enlaces de postventa no tienen su gráfico, una
-- de las dos ingestas ha quedado a medias. Falla con la cifra.
DO $$
DECLARE
    v_huerf BIGINT;
    v_total BIGINT;
BEGIN
    SELECT count(*) FILTER (WHERE g.ide IS NULL), count(*)
      INTO v_huerf, v_total
    FROM      raw.rcg r
    JOIN      raw.con c ON c.ide = r.con AND c.tip IN (47, 707, 708)
    LEFT JOIN raw.gra g ON g.ide = r.gra;
    IF v_total > 0 AND v_huerf > v_total * 0.01 THEN
        RAISE EXCEPTION 'F-156 R21: % de % enlaces de raw.rcg de postventa no tienen su grafico en raw.gra (mas del uno por ciento). La ingesta de gra o de rcg ha quedado a medias: reingerir las dos (rcg primero) antes de reconstruir postventa.documento_adjuntos.', v_huerf, v_total;
    END IF;
END $$;

DROP TABLE IF EXISTS postventa.documento_adjuntos CASCADE;
CREATE TABLE postventa.documento_adjuntos AS
WITH base AS (
    SELECT
        r.ide                                   AS adjunto_id,
        r.con                                   AS documento_id,
        c.tip                                   AS tipo_documento_codigo,
        CASE WHEN c.tip = 707 THEN 'UNIDAD'
             WHEN c.tip = 47 THEN 'TAREA'
             WHEN g.gratipide = 35 THEN 'REPARACION'
             ELSE 'INCIDENCIA' END::TEXT        AS familia,
        NULLIF(BTRIM(c.cod), '')                AS codigo_documento,
        CASE c.tip WHEN 708 THEN r.con WHEN 47 THEN NULLIF(t.rcpide, 0) END
                                                AS incidencia_id,
        CASE c.tip WHEN 707 THEN r.con WHEN 708 THEN NULLIF(rc.upvide, 0)
                   WHEN 47 THEN NULLIF(rt.upvide, 0) END
                                                AS unidad_id,
        CASE c.tip WHEN 47 THEN r.con END       AS tarea_id,
        g.ide                                   AS grafico_id,
        g.cod                                   AS cod_repositorio,
        g.emp                                   AS empresa_repositorio,
        NULLIF(BTRIM(g.nom), '')                AS nombre_fichero,
        lower(substring(btrim(g.nom) from '\.([^.\s]+)$')) AS extension,
        NULLIF(g.gratipide, 0)                  AS clase_grafico_id,
        NULLIF(BTRIM(a.cod), '')                AS clase_grafico_codigo,
        NULLIF(BTRIM(a.res), '')                AS clase_grafico,
        NULLIF(BTRIM(g.res), '')                AS descripcion,
        postventa.fn_fecha(g.fec)               AS fecha_alta,
        NULLIF(BTRIM(g.usu), '')                AS subido_por,
        r.pos                                   AS posicion
    FROM      raw.rcg r
    JOIN      raw.con c ON c.ide = r.con AND c.tip IN (47, 707, 708)
    JOIN      raw.gra g ON g.ide = r.gra
    LEFT JOIN raw.auxgra a ON a.ide = g.gratipide
    LEFT JOIN raw.rcp rc ON rc.ide = r.con AND c.tip = 708
    LEFT JOIN raw.tar t ON t.ide = r.con AND c.tip = 47
    LEFT JOIN raw.rcp rt ON rt.ide = t.rcpide
)
SELECT
    b.adjunto_id                                AS adjunto_id,
    b.familia                                   AS familia,
    b.documento_id                              AS documento_id,
    b.tipo_documento_codigo                     AS tipo_documento_codigo,
    b.codigo_documento                          AS codigo_documento,
    b.incidencia_id                             AS incidencia_id,
    b.unidad_id                                 AS unidad_id,
    b.tarea_id                                  AS tarea_id,
    b.grafico_id                                AS grafico_id,
    b.cod_repositorio                           AS cod_repositorio,
    b.empresa_repositorio                       AS empresa_repositorio,
    b.nombre_fichero                            AS nombre_fichero,
    b.extension                                 AS extension,
    CASE
        WHEN b.extension IS NULL THEN 'SIN_EXTENSION'
        WHEN b.extension IN ('pdf') THEN 'PDF'
        WHEN b.extension IN ('xls', 'xlsx', 'xlsm', 'xlsb', 'csv') THEN 'EXCEL'
        WHEN b.extension IN ('doc', 'docx', 'rtf', 'odt') THEN 'WORD'
        WHEN b.extension IN ('msg', 'eml') THEN 'CORREO'
        WHEN b.extension IN ('jpg', 'jpeg', 'png', 'tif', 'tiff', 'gif', 'bmp') THEN 'IMAGEN'
        ELSE 'OTRO'
    END::TEXT                                   AS clase_fichero,
    b.clase_grafico_id                          AS clase_grafico_id,
    b.clase_grafico_codigo                      AS clase_grafico_codigo,
    b.clase_grafico                             AS clase_grafico,
    b.descripcion                               AS descripcion,
    b.fecha_alta                                AS fecha_alta,
    b.subido_por                                AS subido_por,
    b.posicion                                  AS posicion
FROM base b;

ALTER TABLE postventa.documento_adjuntos ADD PRIMARY KEY (adjunto_id);
CREATE INDEX ix_pv_adjuntos_documento  ON postventa.documento_adjuntos (documento_id);
CREATE INDEX ix_pv_adjuntos_incidencia ON postventa.documento_adjuntos (incidencia_id);
CREATE INDEX ix_pv_adjuntos_unidad     ON postventa.documento_adjuntos (unidad_id);

COMMENT ON TABLE postventa.documento_adjuntos IS
'Indice de ficheros adjuntos (Graficos asociados de Sigrid) de unidades, incidencias y tareas de postventa (F-156): una fila por enlace documento-fichero (raw.rcg), familia UNIDAD, INCIDENCIA, REPARACION (parte firmado por el cliente, con su DNI manuscrito: solo lo abren los perfiles postventa y total) o TAREA. Clave adjunto_id (rcg.ide). El fichero NO esta en el datamart: lo sirve sigrid-api con la pareja (empresa_repositorio, cod_repositorio).';
