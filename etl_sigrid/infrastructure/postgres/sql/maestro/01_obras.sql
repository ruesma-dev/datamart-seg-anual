-- etl_sigrid/infrastructure/postgres/sql/maestro/01_obras.sql
--
-- Maestro de OBRAS para consulta externa.
--
-- Una obra es una entidad `con` (obr.ide = con.ide). Por tanto:
--   - código, nombre, estado y fechas de alta/baja  → raw.con
--   - cliente (entide), dirección y resto de propiedades de obra → raw.obr
--
-- LA CABECERA DE ANTES ERA FALSA (corregida por F-073): daba por hecho que en
-- Sigrid una obra carece de emplazamiento propio. Lo tiene, y vive en
-- `obr.dir1`, `obr.dir2`,
-- `obr.dircpo` y `obr.dir`, y además tienen municipio y provincia en
-- `obr.munide` / `obr.proide`. Lo que pasa es que **está informada en un tercio
-- de las obras**: medido el 2026-09-10 sobre las 921 fichas, `dir1` 305 (33,1 %),
-- `dircpo` 303 (32,9 %), `dir` 272 (29,5 %), municipio 294 (31,9 %), provincia
-- 306 (33,2 %) y `dir2` solo 47 (5,1 %). Para dos de cada tres obras, «no
-- consta» es la respuesta CORRECTA, y así lo declara la ficha del diccionario.
--
-- TRES CAMPOS DE `raw.obr` QUE SUENAN A DIRECCIÓN Y NO LO SON (medido en F-071,
-- confirmado en F-073): el director de obra, su persona de contacto y la
-- dirección del cliente. No se publican aquí, y la suite lo veta por nombre en
-- `tests/test_f073_sql.py` para que nadie los reintroduzca.
--
-- LAS DOS MARCAS leen de `stg`, NO de la capa de hechos: el DDL de esa capa
-- dropea sus tablas con CASCADE cada noche y se llevaría esta vista por delante
-- (es el incidente de F-047). `stg.presupuesto` y `stg.plan_mensual` se crean
-- con `CREATE TABLE IF NOT EXISTS` y no se dropean nunca. Contrapartida
-- declarada: `tiene_seguimiento` es SUPERCONJUNTO del hecho publicado —368
-- obras con plan frente a 349 con hecho, 19 de diferencia y ninguna al revés—.
--
-- EL ESTADO se traduce contra `raw.conest` filtrando el TIPO DE DOCUMENTO DE
-- OBRA (42): la misma cifra significa otra cosa en un contrato o en una
-- factura. El lateral con `ORDER BY` y `LIMIT 1` es la guarda de grano: hoy
-- `(tip, est)` es único (193 de 193) y la vista no puede depender de eso.
--
-- GRANO: una fila por obra. 921 el 2026-09-10, y siguen siendo 921 después de
-- los tres LEFT JOIN nuevos (comprobado en solo lectura antes de escribir esto).
--
-- Consumo típico:
--   SELECT codigo_obra, nombre_obra FROM maestro.obras ORDER BY codigo_obra;
--   SELECT * FROM maestro.obras WHERE codigo_obra = '0404';
--   SELECT municipio, COUNT(*) FROM maestro.obras GROUP BY municipio;

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
    cli.res                        AS nombre_cliente,
    -- A PARTIR DE AQUI, TODO LO QUE ANADE F-073, Y VA AL FINAL POR OBLIGACION:
    -- `CREATE OR REPLACE VIEW` de PostgreSQL solo admite columnas NUEVAS AL
    -- FINAL. Intercalar `estado` entre `estado_id` y `fecha_alta`, que es donde
    -- se lee mejor, hace fallar el replace con «cannot change name of view
    -- column» y se lleva por delante el build entero esa noche.
    es.nombre_estado               AS estado,               -- estado_id ya traducido (tipo 42)
    NULLIF(TRIM(o.dir1), '')       AS dir1,
    NULLIF(TRIM(o.dir2), '')       AS dir2,
    NULLIF(TRIM(o.dircpo), '')     AS codigo_postal,
    NULLIF(TRIM(o.dir), '')        AS direccion_completa,
    NULLIF(o.munide, 0)            AS municipio_id,
    mu.res                         AS municipio,
    NULLIF(o.proide, 0)            AS provincia_id,
    pr.res                         AS provincia,
    EXISTS (SELECT 1 FROM stg.presupuesto sp WHERE sp.obra_id = c.ide) AS tiene_presupuesto,
    EXISTS (SELECT 1 FROM stg.plan_mensual pm WHERE pm.obra_id = c.ide) AS tiene_seguimiento
FROM      raw.obr o
JOIN      raw.con c   ON c.ide   = o.ide                 -- la obra ES un `con`
LEFT JOIN raw.con cli ON cli.ide = o.entide              -- el cliente también es un `con`
LEFT JOIN raw.auxmun mu ON mu.ide = NULLIF(o.munide, 0)  -- 0 es «no consta», no un catálogo
LEFT JOIN raw.auxpro pr ON pr.ide = NULLIF(o.proide, 0)
LEFT JOIN LATERAL (
    SELECT ce.res AS nombre_estado
    FROM   raw.conest ce
    WHERE  ce.tip = 42 AND ce.est = c.est
    ORDER  BY ce.ide
    LIMIT  1
) es ON TRUE;

COMMENT ON VIEW maestro.obras IS
'Maestro de obras (921 filas, una por obra): codigo, nombre, estado con su nombre traducido (tipo de documento 42), fechas de alta y baja, cliente, direccion con el mismo vocabulario que maestro.proveedores, municipio y provincia con su identificador, y las marcas tiene_presupuesto / tiene_seguimiento. OJO: la direccion viene informada en un tercio de las obras (dir1 33,1 %, municipio 31,9 %), asi que "no consta" es la respuesta correcta para dos de cada tres. tiene_seguimiento se mide en stg.plan_mensual y es superconjunto del hecho publicado en 19 obras.';
