-- etl_sigrid/infrastructure/postgres/sql/stg/06_presupuesto.sql
--
-- Materializa stg.presupuesto a partir de raw.obrparpre.
--
-- Filtros: solo obride NOT NULL (preservamos cierres con valor 0 = estornos).
--
-- DEDUPLICACIÓN: DISTINCT ON por clave de negocio (obra, partida, amb, fase)
-- quedándonos con el `ide` MAYOR (la corrección más reciente de Sigrid).
--
-- PRECISIÓN (ambas columnas NUMERIC(20,6)):
--   - precio: raw.obrparpre.pre tiene hasta 6 decimales reales (ej. 115.294961)
--   - cantidad: raw.obrparpre.can para CP* contiene porcentajes con hasta
--     6 decimales (ej. 0.00025 para CP.4 AVALES). Truncar a 4 decimales
--     causa gap material en el Plan (caso real 0696 mayo 2025: +83,71 €).

TRUNCATE TABLE stg.presupuesto;

INSERT INTO stg.presupuesto (
    presupuesto_id,
    obra_id,
    partida_id,
    ambito_id,
    fase_num,
    cantidad,
    precio,
    importe,
    _source_tiemod
)
SELECT DISTINCT ON (pp.obride, pp.paride, pp.amb, COALESCE(pp.fas, 0))
    pp.ide                                            AS presupuesto_id,
    pp.obride                                         AS obra_id,
    pp.paride                                         AS partida_id,
    pp.amb                                            AS ambito_id,
    COALESCE(pp.fas, 0)                               AS fase_num,
    pp.can::NUMERIC(20,6)                             AS cantidad,
    pp.pre::NUMERIC(20,6)                             AS precio,
    ROUND((pp.can::NUMERIC(20,6) * pp.pre::NUMERIC(20,6))::NUMERIC, 2) AS importe,
    pp._source_tiemod
FROM raw.obrparpre pp
WHERE pp.obride IS NOT NULL
ORDER BY pp.obride, pp.paride, pp.amb, COALESCE(pp.fas, 0), pp.ide DESC;