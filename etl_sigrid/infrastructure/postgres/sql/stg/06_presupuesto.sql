-- etl_sigrid/infrastructure/postgres/sql/stg/06_presupuesto.sql
--
-- Materializa stg.presupuesto a partir de raw.obrparpre.
--
-- IMPORTANTE: esta tabla trae TODOS los ámbitos. La decisión de qué ámbito
-- se usa para qué la toma mart, consultando la columna `uso_seguimiento`
-- de stg.ambitos. Hoy:
--   - mart filtra ambito_id=8  (MASTER COSTE) → CD/CI/CP planificados
--   - mart filtra ambito_id=11 (MASTER VENTA) → Producción planificada
--   - el resto está aquí pero mart no lo consulta (de momento)
--
-- Filtros aplicados:
--   - obride IS NOT NULL: defensa contra filas huérfanas
--   - Sin filtro can*pre <> 0: preservamos cierres con valor 0
--     (estornos / anulaciones legítimas). Necesario para que el LAG mensual
--     en 08_plan_mensual.sql capture los estornos correctamente. Caso real:
--     obra 0675 partida CI.03A.8 con fas=2 totinc=0 (estorno de noviembre).
--
-- ===========================================================================
-- DEDUPLICACIÓN POR CLAVE DE NEGOCIO
-- ===========================================================================
-- raw.obrparpre tiene PK en `ide`, pero la clave de negocio real es
-- (obride, paride, amb, fas) — "un cierre mensual de una partida en un ámbito".
--
-- Sigrid a veces inserta DOS filas para la misma clave de negocio en lugar
-- de actualizar la existente (típicamente cuando hay correcciones manuales).
-- Estas filas tienen `ide` distintos pero idéntica (obride, paride, amb, fas)
-- y pueden tener `can` y `pre` diferentes (la nueva sobrescribe a la antigua
-- en la pantalla de Sigrid, pero en BD conviven ambas).
--
-- Casos reales detectados (todos en fas=último cierre abierto = abril 2026):
--   obra 0686 amb=3 fas=22: 1 par duplicado
--   obra 0686 amb=7 fas=22: 3 pares duplicados
--   obra 0695 amb=3 fas=18: 5 pares duplicados
--   obra 0696 amb=7 fas=20: 2 pares duplicados
--   obra 0712 amb=7 fas=5:  1 par duplicado
--
-- Política: DISTINCT ON por (obra_id, partida_id, ambito_id, fase_num)
-- quedándonos con el `ide` MAYOR (el más reciente cronológicamente, que es
-- el que Sigrid muestra en pantalla como la corrección vigente).
-- ===========================================================================
--
-- ===========================================================================
-- PRECISIÓN DEL PRECIO
-- ===========================================================================
-- raw.obrparpre.pre es double precision (hasta 6 decimales reales: 115.294961).
-- stg.presupuesto.precio se almacena como NUMERIC(20,6) para preservar esa
-- precisión y que el ROUND(precio, 2) downstream coincida con lo que muestra
-- Sigrid en su UI. Ver detalle del bug en 01_ddl.sql.
--
-- Cast explícito a NUMERIC(20,6): aunque la columna ya tiene ese tipo y
-- Postgres haría el cast implícito al INSERT, lo escribimos explícito como
-- defensa documental.
-- ===========================================================================
--
-- Otras transformaciones:
--   - importe = ROUND(can × pre, 2): pre-calculado para que mart no lo recalcule
--   - fase_num: COALESCE a 0 (algunas filas pueden no tener fase asignada)

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
    pp.can::NUMERIC(18,4)                             AS cantidad,
    pp.pre::NUMERIC(20,6)                             AS precio,
    ROUND((pp.can::NUMERIC(18,4) * pp.pre::NUMERIC(20,6))::NUMERIC, 2) AS importe,
    pp._source_tiemod
FROM raw.obrparpre pp
WHERE pp.obride IS NOT NULL
-- Deduplicación: si hay varias filas para la misma clave de negocio,
-- nos quedamos con la de `ide` mayor (la más reciente cronológicamente).
ORDER BY pp.obride, pp.paride, pp.amb, COALESCE(pp.fas, 0), pp.ide DESC;