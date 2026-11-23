-- etl_sigrid/infrastructure/postgres/sql/stg/11_texto_largo.sql
--
-- F-168 · La limpieza y la identidad del TEXTO LARGO, UNA sola vez para todo el
-- datamart: `stg.partida_texto` (12), `compras.linea_texto` y `compras.textos`
-- (compras/16) y el catalogo de textos de los descompuestos (sql/descompuestos/,
-- ficheros 02 y 03) llaman a estas funciones y a ninguna otra.
--
-- Lee: nada (funciones puras sobre el texto que se les pasa).
--
-- LOS LITERALES NO SE INVENTAN AQUÍ (R7). El tope (16000 caracteres), el patrón
-- de control y lo que se recorta de los extremos viven en
-- `etl_sigrid/domain/texto_largo.py`, que es el espejo en Python donde se
-- prueban; `tests/test_f168_sql.py` comprueba que este fichero usa esos mismos.
-- Si hay que cambiarlos, se cambian allí y aquí a la vez.
--
-- LA LIMPIEZA (R5), en este orden: `\r\n` y `\r` pasan a `\n`; fuera los
-- caracteres de control salvo `\t` y `\n`; fuera espacios, tabuladores y saltos
-- de los extremos; corte al tope; otra vez los extremos (el corte puede dejar un
-- espacio al final); vacío es NULL.
--
-- LA IDENTIDAD (R6): `texto_id = md5(texto limpio)::uuid`. Mismo `texto_id`,
-- mismo texto, en `stg`, `compras` y `descompuestos`. Se pasa SIEMPRE el texto
-- ya limpio: `stg.fn_texto_id(stg.fn_texto_largo(x))`.
--
-- RECORTADO (R8): el texto de `raw` mide el tope o más, es decir, Sigrid lo ha
-- cortado (la ingesta lo pide con `SUBSTRING(..., 1, 16000)`) y puede faltar
-- texto. Se mira sobre el texto de `raw`, no sobre el limpio.
--
-- SOLO FUNCIONES, y es a propósito: este fichero entra en el SELLO del troceado
-- de `descompuestos` (`build_descompuestos_step.FICHEROS_DEL_SELLO`, R22). Si
-- cambia la limpieza, cambia el `texto_id` y el master se retrocea entero.
-- Fuera del sello de `stg` (no cambia ninguna tabla acotada de F-025).

CREATE OR REPLACE FUNCTION stg.fn_texto_largo(t TEXT)
RETURNS TEXT
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
SELECT NULLIF(
    btrim(
        left(
            btrim(
                regexp_replace(
                    replace(replace(t, E'\r\n', E'\n'), E'\r', E'\n'),
                    '[\x01-\x08\x0B\x0C\x0E-\x1F\x7F]', '', 'g'
                ),
                E' \t\n'
            ),
            16000
        ),
        E' \t\n'
    ),
    ''
)
$$;

COMMENT ON FUNCTION stg.fn_texto_largo(TEXT) IS
'F-168. El texto largo limpio: saltos normalizados, sin caracteres de control, sin espacios en los extremos y cortado a 16000 caracteres; NULL si queda vacio. Una sola limpieza para stg, compras y los descompuestos de obra.';

CREATE OR REPLACE FUNCTION stg.fn_texto_id(t TEXT)
RETURNS UUID
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
SELECT md5(t)::uuid
$$;

COMMENT ON FUNCTION stg.fn_texto_id(TEXT) IS
'F-168. La identidad de un texto YA limpio: md5(texto)::uuid. Mismo texto_id, mismo texto, en stg, compras y los descompuestos de obra.';

CREATE OR REPLACE FUNCTION stg.fn_texto_recortado(t TEXT)
RETURNS BOOLEAN
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
SELECT COALESCE(char_length(t) >= 16000, FALSE)
$$;

COMMENT ON FUNCTION stg.fn_texto_recortado(TEXT) IS
'F-168. El texto de raw mide el tope (16000 caracteres) o mas: Sigrid lo ha cortado y puede faltar texto.';
