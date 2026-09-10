-- etl_sigrid/infrastructure/postgres/sql/maestro/05_estados_documento.sql
--
-- DIMENSIÓN de estados de documento (F-073), desde `raw.conest`.
--
-- En Sigrid el estado de un documento es un número dentro de `con.est`, y lo
-- que ese número significa depende del TIPO de documento: 42 es obra, 44
-- contrato, 15 factura, 46 comparativo, 12 oferta. La misma cifra 15 es
-- «EN CURSO» en una obra y otra cosa distinta en un contrato. Por eso esta
-- vista publica el catálogo ENTERO, sin filtrar por tipo: quien traduce un
-- estado tiene que unir por `(tipo_documento, estado_id)`, nunca solo por el
-- estado.
--
-- GRANO: una fila por fila de `raw.conest`. 193 el 2026-09-10, repartidas en
-- 29 tipos de documento; el par `(tip, est)` es único (193 de 193, medido).
--
-- Nombres de columna del origen, MEDIDOS en la T1 de F-073: `tip` es el tipo
-- de documento, `est` el código del estado (es el que casa con `con.est`, y no
-- `cod`, que es texto) y `res` el nombre.
--
-- Consumo típico:
--   SELECT estado FROM maestro.estados_documento
--    WHERE tipo_documento = 42 AND estado_id = 15;   -- 'EN CURSO'

CREATE OR REPLACE VIEW maestro.estados_documento AS
SELECT
    ce.ide  AS estado_documento_id,
    ce.tip  AS tipo_documento,
    ce.est  AS estado_id,
    ce.cod  AS codigo_estado,
    ce.res  AS estado
FROM raw.conest ce;

COMMENT ON VIEW maestro.estados_documento IS
'Catalogo de estados de documento de Sigrid (193 filas). TRAMPA: la traduccion va por TIPO DE DOCUMENTO. El mismo estado_id significa cosas distintas en una obra (tipo 42), un contrato (44) o una factura (15), asi que hay que unir por (tipo_documento, estado_id) y nunca solo por estado_id.';
