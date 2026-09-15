-- etl_sigrid/infrastructure/postgres/sql/maestro/04_centros_coste.sql
--
-- EL PUENTE centro de coste -> obra (F-073).
--
-- Un centro de coste es una entidad `con` con propiedades `cen` (mismo ide),
-- igual que una obra es una entidad `con` con propiedades `obr`. Son DOS
-- entidades distintas que comparten empresa y código, y ese par es lo único
-- que las une: `cen.ide -> con(emp, cod)` <-> `con(emp, cod) -> obr.ide`.
--
-- LO QUE NO SIRVE, y está medido el 2026-09-10 (T1 de F-073):
--   - `cen.obride` **está a 0 en las 804 filas**. Parece el puente y no lo es.
--   - la aritmética sobre el `ide` (`obride + 1`) acierta el 64 %: es una
--     coincidencia de cómo Sigrid reparte identificadores, no una relación.
--
-- GRANO: una fila por fila de `raw.cen`. 804 el 2026-09-10, de las cuales 683
-- resuelven a obra y 121 NO (estructura, delegación y servicios generales).
-- Esas 121 se publican igual, con `obra_id` a NULL: aquí no se filtra nada.
--
-- El COMMENT de abajo no NOMBRA ese campo a proposito: el guard de la suite
-- (`test_f073_r3_no_usa_cen_obride`) veta el identificador en todo el fichero,
-- comentarios `--` aparte, para que nadie lo reintroduzca por descuido.
--
-- Consumo típico:
--   SELECT * FROM maestro.centros_coste WHERE obra_id IS NOT NULL;
--   SELECT nombre_obra FROM maestro.centros_coste WHERE centro_coste_id = 12345;

CREATE OR REPLACE VIEW maestro.centros_coste AS
SELECT
    n.ide           AS centro_coste_id,
    cc.cod          AS codigo_centro,
    cc.res          AS nombre_centro,
    cc.emp          AS empresa,
    o.obra_id       AS obra_id,
    o.codigo_obra   AS codigo_obra,
    o.nombre_obra   AS nombre_obra
FROM      raw.cen n
JOIN      raw.con cc ON cc.ide = n.ide          -- código, nombre y empresa del centro
LEFT JOIN LATERAL (
    -- El `JOIN raw.obr` es lo que descarta la propia fila `con` del centro,
    -- que comparte empresa y código pero no tiene ficha de obra.
    --
    -- `ORDER BY` + `LIMIT 1`: hoy el puente es 1:1 sobre los 683 pares y no hay
    -- ambigüedad, pero la vista no puede multiplicar filas el día que el origen
    -- deje de serlo. `centro_coste_id` es único POR CONSTRUCCIÓN, no por suerte.
    SELECT co.ide AS obra_id, co.cod AS codigo_obra, co.res AS nombre_obra
    FROM   raw.con co
    JOIN   raw.obr ob ON ob.ide = co.ide
    WHERE  co.emp = cc.emp AND co.cod = cc.cod
    ORDER  BY co.ide
    LIMIT  1
) o ON TRUE;

COMMENT ON VIEW maestro.centros_coste IS
'Puente centro de coste -> obra. Una fila por centro (804 el 2026-09-10); 683 resuelven a obra y 121 no (estructura, delegacion y servicios generales), que salen con obra_id a NULL. El cruce va por empresa y codigo en raw.con; el campo de obra del propio centro esta a 0 en las 804 filas y no sirve (ficha del diccionario).';
