-- etl_sigrid/infrastructure/postgres/sql/stg/12_partida_texto.sql
--
-- F-168 · `stg.partida_texto`: el TEXTO LARGO de cada partida (R9, R10), una
-- fila por partida de `raw.obrparpar` con texto limpio.
--
-- Lee: raw.obrparpar (su `tex`, que la ingesta trae cortado a 16000 caracteres
-- y sin NUL), stg.partidas (código y descripción corta de esta noche) y las
-- funciones de stg/11_texto_largo.sql.
--
-- UN TEXTO PARA TODOS LOS ÁMBITOS (R10, medido M7 y M12). `obrparpre.tex` está
-- vacío en los 15 ámbitos (14,3 M filas) y la partida es la misma en coste,
-- venta, fase 0 y cada versión del master (`obrparpre.paride`), así que su texto
-- es `obrparpar.tex` y no se filtra por ámbito, fase ni tipo: una partida que
-- solo tiene venta, o un capítulo con texto, sale igual. Sigrid no guarda
-- historia (D9): un cambio en fase 0 se ve en todos los master; esta tabla
-- publica SOLO el texto vigente.
--
-- POR QUÉ TABLA APARTE Y NO COLUMNA DE `stg.partidas` (D2): casi todos los
-- builds leen `stg.partidas` y ensancharla con ~120 MB de texto encarecería cada
-- lectura. Se une por `partida_id`.
--
-- `LEFT JOIN stg.partidas`: `stg.partidas` no publica todos los nodos (F-052);
-- el código y la descripción corta salen de allí cuando existen, y si no, NULL.
--
-- SE EJECUTA ENTERO cada noche (ni tramos ni ventana de F-025, fuera del sello
-- de stg). DROP + CREATE en la MISMA llamada (`execute_sql_file`, una sola
-- transacción, R23): si algo falla, queda publicada la tabla de anoche.

DROP TABLE IF EXISTS stg.partida_texto CASCADE;
CREATE TABLE stg.partida_texto AS
SELECT
    o.ide                                   AS partida_id,
    o.obride                                AS obra_id,
    p.codigo_partida                        AS codigo_partida,
    p.descripcion_corta                     AS descripcion_corta,
    l.texto                                 AS texto,
    stg.fn_texto_id(l.texto)                AS texto_id,
    octet_length(l.texto)                   AS bytes,
    stg.fn_texto_recortado(o.tex)           AS recortado
FROM raw.obrparpar o
CROSS JOIN LATERAL (SELECT stg.fn_texto_largo(o.tex) AS texto) l
LEFT JOIN stg.partidas p ON p.partida_id = o.ide
WHERE l.texto IS NOT NULL;

ALTER TABLE stg.partida_texto ADD PRIMARY KEY (partida_id);
CREATE INDEX idx_partida_texto_obra ON stg.partida_texto (obra_id);
CREATE INDEX idx_partida_texto_tid  ON stg.partida_texto (texto_id);

COMMENT ON TABLE stg.partida_texto IS
'F-168. El texto largo de cada partida (obrparpar.tex), limpio. Una fila por partida con texto, uno para todos sus ambitos (coste, venta, fase 0 y master). Solo el texto vigente: Sigrid no guarda historia.';
