-- etl_sigrid/infrastructure/postgres/sql/stg/02_ambitos.sql
--
-- stg.ambitos: vista (no tabla) que clasifica los ámbitos de raw.auxobramb
-- en tipos lógicos del seguimiento Y marca cuál tiene uso real en el data mart.
--
-- Dos columnas clave:
--   - `tipo`            : categorización semántica (VENTA, COSTE, MASTER_COSTE, etc.)
--   - `uso_seguimiento` : si este ámbito alimenta el seguimiento mensual,
--                         qué papel juega. NULL si no se usa.
--
-- REGLA CRÍTICA DEL DATA MART DE SEGUIMIENTO (NO TOCAR SIN HABLAR CON NEGOCIO):
--   En esta primera iteración del seguimiento mensual usamos SOLO DOS ámbitos:
--     amb = 8  (MASTER COSTE) → CD, CI, CP PLANIFICADOS (diferenciados por
--                               aux.tipo_partida).
--     amb = 11 (MASTER VENTA) → Producción PLANIFICADA.
--   Los demás ámbitos (incluidos los REALES: amb=3 COSTE, amb=7 VENTA,
--   amb=5 CERTIFICACION, etc.) están clasificados en `tipo` para reconocerlos,
--   pero su `uso_seguimiento` es NULL hasta que en iteraciones posteriores se
--   añada el escenario REAL.
--
-- Cómo lo consume mart:
--   SELECT * FROM stg.presupuesto p
--   JOIN stg.ambitos a ON a.ambito_id = p.ambito_id
--   WHERE a.uso_seguimiento = 'PLANIFICADO_COSTES'   -- amb=8
--      OR a.uso_seguimiento = 'PLANIFICADO_VENTA'    -- amb=11
--
-- Clasificación tipo: basada en `res` (descripción), NO en `cod` (nemónico).
-- En Sigrid el cod y res no siempre concuerdan. Ejemplo: amb=7 cod="PROD"
-- res="VENTA" → es VENTA. El significado vive en res.

-- Drop antes de Create porque CREATE OR REPLACE VIEW no permite cambiar
-- nombres/orden de columnas existentes.
DROP VIEW IF EXISTS stg.ambitos;

CREATE VIEW stg.ambitos AS
SELECT
    a.ide                                AS ambito_id,
    a.cod                                AS codigo,
    a.res                                AS descripcion,
    a.ambcla                             AS clase_sigrid,

    -- Tipo lógico (categorización descriptiva, NO determina uso)
    CASE
        WHEN UPPER(TRIM(a.res)) = 'VENTA'                       THEN 'VENTA'
        WHEN UPPER(TRIM(a.res)) = 'PRODUCCIÓN REAL'             THEN 'PRODUCCION_REAL'
        WHEN UPPER(TRIM(a.res)) = 'COSTE'                       THEN 'COSTE'
        WHEN UPPER(TRIM(a.res)) = 'COSTE PENDIENTE'             THEN 'COSTE'
        WHEN UPPER(TRIM(a.res)) = 'MASTER COSTE'                THEN 'MASTER_COSTE'
        WHEN UPPER(TRIM(a.res)) = 'MASTER VENTA'                THEN 'MASTER_VENTA'
        WHEN UPPER(TRIM(a.res)) LIKE 'MASTER CERTIFICACI%'      THEN 'MASTER_CERTIFICACION'
        WHEN UPPER(TRIM(a.res)) LIKE 'CERTIFICACI%'             THEN 'CERTIFICACION'
        ELSE 'OTRO'
    END                                  AS tipo,

    -- Uso real en el seguimiento mensual (filtro que aplicará mart).
    -- AÑADIR aquí cuando incorporemos el escenario REAL en futuras iteraciones.
    CASE
        WHEN a.ide = 8  THEN 'PLANIFICADO_COSTES'   -- master coste → CD/CI/CP plan
        WHEN a.ide = 11 THEN 'PLANIFICADO_VENTA'    -- master venta → producción plan
        ELSE NULL                                   -- no usado por seguimiento (aún)
    END                                  AS uso_seguimiento

FROM raw.auxobramb a;

COMMENT ON VIEW stg.ambitos IS
'Clasificación de los 14 ámbitos de Sigrid. tipo = categoría semántica (informativa); uso_seguimiento = papel en el data mart de seguimiento (NULL si no se usa).';
