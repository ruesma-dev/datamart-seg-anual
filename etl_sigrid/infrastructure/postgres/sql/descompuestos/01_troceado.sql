-- etl_sigrid/infrastructure/postgres/sql/descompuestos/01_troceado.sql
-- ============================================================================
-- F-097 · SCHEMA descompuestos (2/7): el troceado del texto `des`, UNA sola
-- definicion para el ambito 3 (02) y para el master (03, 05).
--
-- Lee: nada (funcion pura sobre el texto que se le pasa).
--
-- EL FORMATO (medido en Sigrid el 2026-09-27 y el 2026-09-28): registros que
-- empiezan por `~D|`, separados por salto de linea, con campos separados por
-- `|`. Variantes de 19 a 38 campos: 38 en la «Descomposicion» sincronizada con
-- la planificacion de compras, 19 en la de Estudios. EL TEXTO LARGO DEL CAMPO 9
-- PUEDE TRAER SALTOS DE LINEA DENTRO, asi que se parte por «salto seguido de
-- `~<letra>|`» y NUNCA por cualquier salto (R13). Posiciones base 0:
--
--    1 codigo            2 descripcion        3 precio (del elemento)
--    4 cantidad total    5 unidad             7 codigo alternativo (= dncpro.cod2)
--   11 cod. naturaleza  14 rendimiento       16 tipo      17 naturaleza
--   36 enlace: `dncpro.ide` (0 o vacio si no viene de la planificacion)
--
-- Campo ausente o vacio es NULL; un numerico que no es numero es NULL (R14,
-- `fn_num`). El tipo se traduce con la tabla de D8 (los codigos 3 y 11, SIN
-- VALIDAR con Negocio). En los tipos 4 y 13 (porcentajes) el precio es la BASE
-- y el rendimiento el tanto por uno (0.02 = 2 %), asi que el importe es el
-- mismo producto que en cualquier otra linea (R19).
--
-- RIESGO CONOCIDO: un `|` dentro del texto largo desplaza los campos. No se
-- puede arreglar —el formato no escapa el separador—, pero queda a la vista:
-- sin rendimiento no hay importe y el tipo sale SIN_TIPO o DESCONOCIDO.
--
-- EL ESPEJO. `etl_sigrid/domain/descompuestos.py` (`trocear_des`) hace lo mismo
-- en Python para probarlo sin base de datos; un test exige que las posiciones
-- de aqui sean las de `POSICIONES` de alli.
--
-- EL SELLO (R11). El texto de este fichero y el de 03_lineas_master.sql forman
-- el sello de troceado: si cambia cualquiera de los dos, el build retrocea
-- TODAS las versiones del master (dentro del tope por noche).
-- ============================================================================

CREATE OR REPLACE FUNCTION descompuestos.fn_trocear(des TEXT)
RETURNS TABLE (
    orden                 INTEGER,
    codigo_elemento       TEXT,
    descripcion           TEXT,
    precio                NUMERIC,
    cantidad_total        NUMERIC,
    unidad                TEXT,
    codigo_alternativo    TEXT,
    naturaleza_codigo     TEXT,
    rendimiento           NUMERIC,
    tipo_elemento_codigo  TEXT,
    naturaleza            TEXT,
    dncpro_id             BIGINT,
    tipo_elemento         TEXT,
    importe_unitario      NUMERIC(18,2),
    importe_total         NUMERIC(18,2),
    es_porcentaje         BOOLEAN,
    porcentaje            NUMERIC,
    base_porcentaje       NUMERIC
)
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
SELECT
    c.orden,
    c.codigo_elemento,
    c.descripcion,
    c.precio,
    c.cantidad_total,
    c.unidad,
    c.codigo_alternativo,
    c.naturaleza_codigo,
    c.rendimiento,
    c.tipo_elemento_codigo,
    c.naturaleza,
    c.dncpro_id,
    CASE
        WHEN c.tipo_elemento_codigo IS NULL THEN 'SIN_TIPO'
        ELSE CASE c.tipo_elemento_codigo
            WHEN '8' THEN 'MANO_OBRA'
            WHEN '9' THEN 'MAQUINARIA'
            WHEN '10' THEN 'MATERIAL'
            WHEN '11' THEN 'SUBCONTRATA'
            WHEN '3' THEN 'OTROS'
            WHEN '4' THEN 'PORCENTAJE'
            WHEN '13' THEN 'MEDIOS_AUXILIARES'
            ELSE 'DESCONOCIDO'
        END
    END AS tipo_elemento,
    ROUND(c.precio * c.rendimiento, 2)::NUMERIC(18,2) AS importe_unitario,
    ROUND(c.cantidad_total * c.precio, 2)::NUMERIC(18,2) AS importe_total,
    COALESCE(c.tipo_elemento_codigo IN ('4', '13'), FALSE) AS es_porcentaje,
    CASE WHEN c.tipo_elemento_codigo IN ('4', '13') THEN c.rendimiento * 100 END AS porcentaje,
    CASE WHEN c.tipo_elemento_codigo IN ('4', '13') THEN c.precio END AS base_porcentaje
FROM (
    -- Un campo por posicion: split_part cuenta desde 1, la posicion desde 0.
    SELECT
        g.orden,
        NULLIF(btrim(split_part(g.reg, '|', 2)), '') AS codigo_elemento,
        NULLIF(btrim(split_part(g.reg, '|', 3)), '') AS descripcion,
        descompuestos.fn_num(split_part(g.reg, '|', 4)) AS precio,
        descompuestos.fn_num(split_part(g.reg, '|', 5)) AS cantidad_total,
        NULLIF(btrim(split_part(g.reg, '|', 6)), '') AS unidad,
        NULLIF(btrim(split_part(g.reg, '|', 8)), '') AS codigo_alternativo,
        NULLIF(btrim(split_part(g.reg, '|', 12)), '') AS naturaleza_codigo,
        descompuestos.fn_num(split_part(g.reg, '|', 15)) AS rendimiento,
        NULLIF(btrim(split_part(g.reg, '|', 17)), '') AS tipo_elemento_codigo,
        NULLIF(btrim(split_part(g.reg, '|', 18)), '') AS naturaleza,
        -- El CASE y no un AND: Postgres no garantiza el orden de un AND y el
        -- cast de un texto que no es numero reventaria el build.
        CASE
            WHEN split_part(g.reg, '|', 37) ~ '^[0-9]{1,18}$'
                THEN NULLIF(split_part(g.reg, '|', 37)::BIGINT, 0)
        END AS dncpro_id
    FROM (
        -- Un registro por fila, numerados desde 1 tras descartar lo que no
        -- empieza por `~<letra>|` (una cabecera suelta no es un registro).
        SELECT
            (row_number() OVER (ORDER BY r.pos))::INTEGER AS orden,
            rtrim(r.reg, E'\n') AS reg
        FROM regexp_split_to_table(replace(des, E'\r', ''), E'\n(?=~[A-Z]\\|)') WITH ORDINALITY AS r(reg, pos)
        WHERE r.reg ~ '^~[A-Z]\|'
    ) g
) c
$$;

COMMENT ON FUNCTION descompuestos.fn_trocear(TEXT) IS
'F-097. Trocea el texto des de obrparpre en una fila por registro, con sus campos por posicion, el tipo traducido (D8) y los importes. Una sola definicion para el ambito 3 y el master.';
