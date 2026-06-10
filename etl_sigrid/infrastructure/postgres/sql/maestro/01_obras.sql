-- etl_sigrid/infrastructure/postgres/sql/maestro/01_obras.sql
--
-- Maestro de OBRAS para consulta externa.
--
-- Una obra es una entidad `con` (obr.ide = con.ide). Por tanto:
--   - código, nombre, estado y fechas de alta/baja  → raw.con
--   - cliente (entide) y resto de propiedades de obra → raw.obr
--
-- SIN dirección de emplazamiento: en Sigrid las obras no tienen dirección
-- propia (no aparecen en condir) y `obr.entdiride` viene a 0, así que tampoco
-- hay dirección de cliente asociada. Se exponen código + nombre + cliente.
--
-- Consumo típico:
--   SELECT codigo_obra, nombre_obra FROM maestro.obras ORDER BY codigo_obra;
--   SELECT * FROM maestro.obras WHERE codigo_obra = '0404';

CREATE OR REPLACE VIEW maestro.obras AS
SELECT
    c.ide                          AS obra_id,
    c.cod                          AS codigo_obra,
    c.res                          AS nombre_obra,
    c.est                          AS estado_id,            -- código interno (p.ej. 15 = EN CURSO)
    maestro.fn_fecha(c.fec)        AS fecha_alta,
    maestro.fn_fecha(c.fecbaj)     AS fecha_baja,
    (c.fecbaj IS NULL OR c.fecbaj = 0) AS es_activa,
    o.entide                       AS cliente_id,
    cli.cod                        AS codigo_cliente,
    cli.res                        AS nombre_cliente
FROM      raw.obr o
JOIN      raw.con c   ON c.ide   = o.ide        -- la obra ES un `con`
LEFT JOIN raw.con cli ON cli.ide = o.entide;    -- el cliente también es un `con`

COMMENT ON VIEW maestro.obras IS
'Maestro de obras: obra_id, codigo_obra, nombre_obra, estado (código), fechas alta/baja, y cliente (id/código/nombre). Una fila por obra. Sin dirección: las obras no la tienen en Sigrid.';
