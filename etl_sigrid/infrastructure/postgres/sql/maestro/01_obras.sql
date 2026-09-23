-- etl_sigrid/infrastructure/postgres/sql/maestro/01_obras.sql
--
-- Maestro de OBRAS para consulta externa: UNA FILA POR FICHA DE OBRA.
--
-- Una obra es una entidad `con` (obr.ide = con.ide). Por tanto:
--   - código, nombre, estado, fechas de alta/baja y EMPRESA  → raw.con
--   - cliente (entide), dirección y resto de propiedades de obra → raw.obr
--
-- LA OBRA ES DE UNA EMPRESA (F-102, modelo del humano del 2026-09-23). En
-- Sigrid el mismo código de obra existe una vez por empresa —Ruesma (1), Porsan
-- (28), cada UTE— y es la misma obra vista desde cada una, SIN CONSOLIDAR.
-- Medido en solo lectura el 2026-09-23: 922 fichas para 846 códigos, 58 de ellos
-- repetidos; dentro de una empresa el código es único. Por eso el código solo no
-- identifica una obra: se cruza SIEMPRE con `empresa_id`, o por `clave_obra`
-- ('1-0581', '27-0581'), que es única (922 para 922). `obra_id` sigue siendo la
-- clave técnica. Las seis columnas de F-102 salen de `maestro.v_obra_fichas`
-- (`00_setup.sql`), que decide cuál es la ficha de Ruesma de cada código
-- (`es_ficha_principal`) y la publica como referencia (`obra_principal_id`):
-- NO sirve para agregar hechos de otras empresas. `stg.obras` no la usa y
-- difiere de ella en 0581, 0606, 0671 y 0720; eso lo resuelve F-106.
--
-- LA CABECERA DE ANTES ERA FALSA (corregida por F-073): daba por hecho que en
-- Sigrid una obra carece de emplazamiento propio. Lo tiene, y vive en
-- `obr.dir1`, `obr.dir2`,
-- `obr.dircpo` y `obr.dir`, y además tienen municipio y provincia en
-- `obr.munide` / `obr.proide`.
--
-- LA COBERTURA SE MIDE SOBRE LA FICHA DE RUESMA (F-102): contar sobre las 922
-- fichas mezclaba las copias de otras empresas, y las 103 de la empresa 28 no
-- traen ni dirección ni cliente. Medido el 2026-09-23 sobre las 846 fichas
-- principales, `dir1` está en 310 (36,6 %), y escasea en las obras ANTIGUAS:
-- < 0400, 77 de 252; 0400-0599, 93 de 200; 0600-0671, 61 de 74; 0672 en
-- adelante, 49 de 59. De cuatro dígitos desde la 0672: 57 principales, todas de
-- la empresa 1, 48 con `dir1`. `raw.condir` no aporta direcciones de obra: 0 de
-- 922 fichas tienen fila, también en Sigrid.
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
-- GRANO: una fila por FICHA de obra (`obra_id`). 921 el 2026-09-10, 922 el
-- 2026-09-23. Los LEFT JOIN no multiplican: `maestro.v_obra_fichas` tiene una
-- fila por `obra_id` y los dos laterales llevan `ORDER BY` + `LIMIT 1`. No se
-- filtra ninguna ficha: la de otra empresa también es una obra.
--
-- EL NOMBRE DE LA EMPRESA se lee de `raw.auxemp` (38 filas) por `numemp`, que
-- es el número que guarda `con.emp`. Hoy `numemp` es único en Sigrid; el
-- lateral no depende de eso.
--
-- Consumo típico:
--   SELECT clave_obra, nombre_obra, nombre_empresa FROM maestro.obras ORDER BY clave_obra;
--   SELECT * FROM maestro.obras WHERE codigo_obra = '0404' AND empresa_id = 1;
--   SELECT * FROM maestro.obras WHERE clave_obra = '27-0581';
--   SELECT municipio, COUNT(*) FROM maestro.obras WHERE es_ficha_principal GROUP BY municipio;

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
    EXISTS (SELECT 1 FROM stg.plan_mensual pm WHERE pm.obra_id = c.ide) AS tiene_seguimiento,
    -- A PARTIR DE AQUI, F-102, y tambien AL FINAL por la misma razon. Las
    -- marcas se LEEN de `maestro.v_obra_fichas`, no se recalculan: una sola
    -- definicion de cual es la ficha de Ruesma.
    vf.empresa_id                  AS empresa_id,
    em.nombre_empresa              AS nombre_empresa,
    vf.clave_obra                  AS clave_obra,
    vf.num_fichas_codigo           AS num_fichas_codigo,
    vf.es_ficha_principal          AS es_ficha_principal,
    vf.obra_principal_id           AS obra_principal_id
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
) es ON TRUE
LEFT JOIN maestro.v_obra_fichas vf ON vf.obra_id = c.ide
LEFT JOIN LATERAL (
    SELECT ae.res AS nombre_empresa
    FROM   raw.auxemp ae
    WHERE  ae.numemp = c.emp
    ORDER  BY ae.ide
    LIMIT  1
) em ON TRUE;

COMMENT ON VIEW maestro.obras IS
'Maestro de obras (922 filas el 2026-09-23, una por FICHA): codigo, nombre, estado con su nombre traducido (tipo de documento 42), fechas de alta y baja, cliente, direccion con el mismo vocabulario que maestro.proveedores, municipio y provincia, las marcas tiene_presupuesto / tiene_seguimiento y, desde F-102, la empresa de la ficha (empresa_id, nombre_empresa) y su clave legible clave_obra = empresa-codigo. LA OBRA ES DE UNA EMPRESA: el mismo codigo es la misma obra vista desde cada empresa y no se consolida, asi que por codigo_obra se cruza siempre con empresa_id o por clave_obra. es_ficha_principal marca la ficha de Ruesma de cada codigo; obra_principal_id es referencia y no sirve para agregar hechos de otras empresas. Direccion: dir1 en 310 de las 846 fichas principales (2026-09-23), escasa en las obras antiguas; las 103 fichas de la empresa 28 no traen ni direccion ni cliente. tiene_seguimiento se mide en stg.plan_mensual y es superconjunto del hecho publicado.';
