-- etl_sigrid/infrastructure/postgres/sql/stg/03_obras.sql
--
-- Materializa stg.obras combinando raw.obr con raw.con.
--
-- Modelo Sigrid: la tabla `obr` hereda de `con` con relación 1:1, igual que
-- `obrx`, `dca`, `dvf` y otras tablas marcadas como "Propiedades de con 1:1" en
-- el autodocumentador. Esto significa que `obr.ide = con.ide`: la obra ES un
-- concepto. Los campos del concepto (cod, res) viven en con; los específicos
-- de obra (centro de coste, fechas) viven en obr.
--
-- Por tanto:
--   - El JOIN es por `con.ide = obr.ide` (NO `obr.cenide`, que es el centro
--     de coste, otra cosa distinta).
--   - El campo del nombre legible es `con.res` (Resumen, varchar). En Sigrid
--     no hay columna llamada `nom`; el patrón estándar es `cod` (código) y
--     `res` (descripción corta/resumen).

TRUNCATE TABLE stg.obras;

INSERT INTO stg.obras (obra_id, codigo_obra, nombre_obra, activa)
SELECT
    obr.ide                              AS obra_id,
    con.cod                              AS codigo_obra,
    con.res                              AS nombre_obra,
    TRUE                                 AS activa
FROM raw.obr obr
JOIN raw.con con ON con.ide = obr.ide;
