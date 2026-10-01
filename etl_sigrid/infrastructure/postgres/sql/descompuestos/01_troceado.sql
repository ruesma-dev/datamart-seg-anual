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
--   11 cod. naturaleza  14 factor x rendimiento (F-120)    16 tipo
--   17 naturaleza       36 enlace: `dncpro.ide` (0 o vacio si no viene de la
--                          planificacion)
--
-- EL CAMPO 14 (F-120, medido el 2026-10-01 en 4,5 M registros) es un NUMERO
-- cuando la linea no tiene factor y `<factor>x<rendimiento>` cuando lo tiene
-- (`1.22x0.003`, `0.99765x-0.15`, `-23.05x`): el FACTOR de la pantalla de
-- Descomposicion de Sigrid. Numero -> factor 1 y ese rendimiento; `a x b` ->
-- factor a, rendimiento b; `a x` -> factor a, rendimiento NULL; vacio o raro
-- (15 registros: `0678.CDMA15`, `1963589xF321886`) -> los dos NULL. El patron
-- es literal `PATRON_FACTOR_RENDIMIENTO` del dominio y cada lado se convierte
-- con `fn_num` (lo fija un test). Un factor 0 es un factor (importe 0).
--
-- Campo ausente o vacio es NULL; un numerico que no es numero es NULL (R14,
-- `fn_num`). El tipo se traduce con la tabla de D8 (los codigos 3 y 11, SIN
-- VALIDAR con Negocio). `importe_unitario` = precio x factor x rendimiento;
-- `importe_total` = cantidad x precio SIN el factor, porque el campo 4 ya lo
-- lleva (1091,5 x 1,00021 x 1 = 1091,729). En los tipos 4 y 13 (porcentajes)
-- el precio es la BASE y el rendimiento el tanto por uno (0.02 = 2 %): el
-- porcentaje es `rendimiento x 100` sin el factor y el importe, con el (D6).
-- Un importe que no cabe en NUMERIC(18,2) sale NULL: el build no se para.
--
-- RIESGO CONOCIDO: un `|` dentro del texto largo desplaza los campos. No se
-- puede arreglar —el formato no escapa el separador—, pero queda a la vista:
-- sin rendimiento no hay importe y el tipo sale SIN_TIPO o DESCONOCIDO.
--
-- EL ESPEJO. `etl_sigrid/domain/descompuestos.py` (`trocear_des`) hace lo mismo
-- en Python para probarlo sin base de datos; un test exige que las posiciones
-- de aqui sean las de `POSICIONES` de alli.
--
-- EL SELLO (R11). El texto de este fichero, el de 00_setup.sql (`fn_num`, F-120)
-- y el de 03_lineas_master.sql forman el sello de troceado: si cambia cualquiera
-- de los tres, el build retrocea TODAS las versiones del master (dentro del
-- tope por noche; de una vez con `build-descompuestos --sin-tope`).
--
-- EL DROP (F-120). `CREATE OR REPLACE` no puede cambiar las columnas de un
-- `RETURNS TABLE`, y F-120 le anade `factor`. Nada depende de la funcion en el
-- catalogo (02, 03 y 05 la llaman en tiempo de ejecucion; ninguna vista la
-- usa), asi que se borra y se crea. ORDEN DE DESPLIEGUE: primero la imagen del
-- job y despues el retroceo; al reves, la imagen vieja fallaria en su `CREATE
-- OR REPLACE` contra esta funcion.
-- ============================================================================

DROP FUNCTION IF EXISTS descompuestos.fn_trocear(TEXT);

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
    base_porcentaje       NUMERIC,
    factor                NUMERIC
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
    -- NUMERIC(18,2): lo que tras redondear no cabe (|x| >= 1e16) es NULL, no un
    -- `numeric field overflow` que tumbe el build (review 1; mismo tope que
    -- `LIMITE_IMPORTE` del espejo).
    -- F-120: con el factor. Sin factor, rendimiento o precio, NULL.
    CASE WHEN abs(ROUND(c.precio * c.factor * c.rendimiento, 2)) < 1e16
        THEN ROUND(c.precio * c.factor * c.rendimiento, 2)::NUMERIC(18,2) END AS importe_unitario,
    CASE WHEN abs(ROUND(c.cantidad_total * c.precio, 2)) < 1e16
        THEN ROUND(c.cantidad_total * c.precio, 2)::NUMERIC(18,2) END AS importe_total,
    COALESCE(c.tipo_elemento_codigo IN ('4', '13'), FALSE) AS es_porcentaje,
    CASE WHEN c.tipo_elemento_codigo IN ('4', '13') THEN c.rendimiento * 100 END AS porcentaje,
    CASE WHEN c.tipo_elemento_codigo IN ('4', '13') THEN c.precio END AS base_porcentaje,
    c.factor
FROM (
    -- El campo 14 partido en factor y rendimiento (F-120). `fn_num` primero: un
    -- numero es factor 1; si no, la forma factor; si tampoco, NULL. `fn_num('')`
    -- es NULL, asi que `a x` deja el rendimiento NULL.
    SELECT
        f.*,
        CASE WHEN descompuestos.fn_num(f.factor_rendimiento) IS NOT NULL THEN 1::NUMERIC
             WHEN f.factor_rendimiento ~ '^[-+]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][-+]?[0-9]{1,3})?x([-+]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][-+]?[0-9]{1,3})?)?$'
                 THEN descompuestos.fn_num(split_part(f.factor_rendimiento, 'x', 1))
        END AS factor,
        CASE WHEN descompuestos.fn_num(f.factor_rendimiento) IS NOT NULL
                 THEN descompuestos.fn_num(f.factor_rendimiento)
             WHEN f.factor_rendimiento ~ '^[-+]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][-+]?[0-9]{1,3})?x([-+]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][-+]?[0-9]{1,3})?)?$'
                 THEN descompuestos.fn_num(split_part(f.factor_rendimiento, 'x', 2))
        END AS rendimiento
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
            NULLIF(btrim(split_part(g.reg, '|', 15)), '') AS factor_rendimiento,
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
    ) f
) c
$$;

COMMENT ON FUNCTION descompuestos.fn_trocear(TEXT) IS
'F-097. Trocea el texto des de obrparpre en una fila por registro, con sus campos por posicion, el tipo traducido (D8) y los importes. El campo 14 es factor x rendimiento (F-120). Una sola definicion para el ambito 3 y el master.';
