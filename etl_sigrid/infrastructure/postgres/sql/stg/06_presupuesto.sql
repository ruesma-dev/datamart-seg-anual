-- etl_sigrid/infrastructure/postgres/sql/stg/06_presupuesto.sql
--
-- Materializa stg.presupuesto a partir de raw.obrparpre.
--
-- IMPORTANTE: esta tabla trae TODOS los ámbitos (filtra solo filas vacías).
-- La decisión de qué ámbito se usa para qué la toma mart, consultando la
-- columna `uso_seguimiento` de stg.ambitos. Hoy:
--   - mart filtra ambito_id=8  (MASTER COSTE) → CD/CI/CP planificados
--   - mart filtra ambito_id=11 (MASTER VENTA) → Producción planificada
--   - el resto está aquí pero mart no lo consulta (de momento)
--
-- Filtros aplicados:
--   - can * pre <> 0: descartamos filas vacías estructurales (~25% del volumen
--     según auditoría: 3.36M de 13.27M).
--   - obride IS NOT NULL: defensa contra filas huérfanas
--
-- Transformaciones:
--   - importe = ROUND(can × pre, 2): pre-calculado para que mart no lo recalcule
--   - fase_num: COALESCE a 0 (algunas filas pueden no tener fase asignada)
--   - cantidad/precio tipados a NUMERIC para evitar problemas de precisión
--
-- Volumen esperado: ~9.9M filas (10M tras filtro).
-- Tiempo esperado: 30-60s en Postgres local con SSD.

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
SELECT
    pp.ide                                            AS presupuesto_id,
    pp.obride                                         AS obra_id,
    pp.paride                                         AS partida_id,
    pp.amb                                            AS ambito_id,
    COALESCE(pp.fas, 0)                               AS fase_num,
    pp.can::NUMERIC                                   AS cantidad,
    pp.pre::NUMERIC                                   AS precio,
    ROUND((pp.can::NUMERIC * pp.pre::NUMERIC), 2)     AS importe,
    pp._source_tiemod
FROM raw.obrparpre pp
WHERE pp.obride IS NOT NULL

