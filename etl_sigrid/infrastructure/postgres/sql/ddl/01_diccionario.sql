-- etl_sigrid/infrastructure/postgres/sql/ddl/01_diccionario.sql
--
-- ===========================================================================
-- EL CONTRATO CON `mcp-bbdd` (F-006). LEER ANTES DE TOCAR NADA.
-- ===========================================================================
--
-- Estas tres tablas y esta vista son lo unico que este repositorio le garantiza
-- al servidor MCP: nombres, tipos y una publicacion atomica. El MCP programa
-- contra esto sin poder preguntar, asi que un cambio aqui es un cambio de API.
--
-- QUE SE PUEDE CAMBIAR SIN ROMPER A NADIE:
--   - Anadir columnas AL FINAL de `_meta.v_diccionario`. `CREATE OR REPLACE
--     VIEW` lo admite y los clientes que no las miren siguen funcionando.
--
-- QUE NO:
--   - Quitar o reordenar columnas de la vista. `CREATE OR REPLACE VIEW` no lo
--     permite: hace falta `DROP VIEW`, y **un DROP se lleva por delante los
--     GRANT del rol del MCP**. Quien lo haga tiene que ejecutar
--     `python main.py apply-grants` inmediatamente despues, o el MCP se queda
--     ciego hasta la noche siguiente. Es el mismo problema que ya obliga a
--     reaplicar permisos en cada ejecucion.
--   - Hacer DROP o TRUNCATE de las tablas. Por eso no hay ni uno en este
--     fichero: el contenido se reemplaza con DELETE + INSERT dentro de UNA
--     transaccion (R18), que ademas es lo que hace que un MCP consultando
--     durante la publicacion vea el diccionario anterior completo o el nuevo
--     completo, nunca uno a medias.
--
-- Este fichero es idempotente y lo ejecuta `PublicarDiccionarioStep` en cada
-- publicacion, justo antes de escribir. No va en `00_meta.sql` a proposito:
-- aquel lo ejecuta el bootstrap en la PRIMERA conexion de cada proceso, y
-- meter ahi tres tablas mas encareceria el arranque de todos los comandos por
-- algo que solo necesita un paso.

-- ---------------------------------------------------------------------------
-- Una fila por objeto documentado del datamart.
-- ---------------------------------------------------------------------------
-- `descripcion` y `grano` son columnas de verdad y no viven dentro del JSONB
-- porque el MCP hace exactamente dos cosas: listar objetos (necesita esas dos y
-- las filtra barato) y describir uno (necesita la ficha entera de una vez). Una
-- tabla aparte de columnas obligaria a un JOIN y a mantener dos esquemas para
-- no ganar ninguna consulta que alguien vaya a escribir.
--
-- `n_columnas` tambien sale a columna porque es lo que mide la cobertura y no
-- debe exigir abrir el JSONB.
CREATE TABLE IF NOT EXISTS _meta.diccionario (
    esquema             TEXT    NOT NULL,
    objeto              TEXT    NOT NULL,
    tipo                TEXT    NOT NULL,   -- tabla | vista | funcion
    capa                TEXT    NOT NULL,   -- origen|preparacion|consumo|operacion
    consumo_recomendado BOOLEAN NOT NULL,
    motivo_no_consumo   TEXT    NULL,       -- obligatorio si consumo_recomendado = false
    descripcion         TEXT    NOT NULL,
    grano               TEXT    NULL,       -- no aplica a las funciones
    clave_negocio       TEXT[]  NOT NULL DEFAULT '{}',
    paso_etl            TEXT    NULL,       -- se une con _meta.v_frescura.paso
    refresco            TEXT    NOT NULL,   -- nocturno | manual | estatico
    avisos              TEXT[]  NOT NULL DEFAULT '{}',  -- codigos de regla (R12)
    n_columnas          INTEGER NOT NULL DEFAULT 0,
    ficha               JSONB   NOT NULL,   -- columnas, relaciones, ejemplos
    PRIMARY KEY (esquema, objeto)
);

-- ---------------------------------------------------------------------------
-- Las reglas duras: las trampas del modelo, escritas como orden y con su
-- porque. Se sirven enteras al agente en su primera llamada.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS _meta.diccionario_reglas (
    codigo    TEXT    PRIMARY KEY,
    titulo    TEXT    NOT NULL,
    severidad TEXT    NOT NULL,             -- bloqueante | aviso
    ambito    TEXT[]  NOT NULL,             -- esquemas y/u objetos alcanzados
    regla     TEXT    NOT NULL,
    motivo    TEXT    NOT NULL,
    orden     INTEGER NOT NULL DEFAULT 0
);

-- ---------------------------------------------------------------------------
-- Que version del diccionario esta publicada. UNA sola fila, siempre.
-- ---------------------------------------------------------------------------
-- El `CHECK (id = 1)` la convierte en un singleton: no hay forma de que queden
-- dos versiones publicadas a la vez. Responde sin salir de SQL a la pregunta
-- "el diccionario que estas leyendo es el del repositorio?", comparando
-- `hash_fuente` con el que calcula el cargador.
--
-- `publicado_en` es TIMESTAMP sin zona, UTC, como todo lo demas de `_meta`:
-- mezclar aqui un TIMESTAMPTZ haria que esta fecha y la de `v_frescura` no
-- fueran comparables, que es justo lo que la vista de abajo hace.
CREATE TABLE IF NOT EXISTS _meta.diccionario_publicacion (
    id             SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    version        TEXT         NOT NULL,
    hash_fuente    TEXT         NOT NULL,   -- SHA-256 de los YAML en orden
    publicado_en   TIMESTAMP    NOT NULL,   -- UTC sin zona
    batch_id       TEXT         NULL,       -- la ejecucion que lo publico
    n_objetos      INTEGER      NOT NULL,
    n_reglas       INTEGER      NOT NULL,
    n_columnas     INTEGER      NOT NULL,
    cobertura_cols NUMERIC(5,2) NOT NULL
);

-- ---------------------------------------------------------------------------
-- EL PUNTO DE ENTRADA UNICO del MCP: significado y fecha de build de una vez.
-- ---------------------------------------------------------------------------
-- Los dos JOIN son LEFT y por motivos distintos:
--
--   - `v_frescura`: un objeto cuyo paso nunca termino bien tiene que SEGUIR
--     saliendo, con la frescura a nulo. Esconderlo seria exactamente el
--     silencio que F-024 elimino.
--   - `diccionario_publicacion`: es un LEFT JOIN ... ON TRUE y no un CROSS
--     JOIN porque con la tabla vacia un CROSS JOIN devolveria CERO filas, y la
--     vista mentiria diciendo que no hay diccionario cuando lo que no hay es
--     registro de publicacion.
CREATE OR REPLACE VIEW _meta.v_diccionario AS
SELECT d.esquema,
       d.objeto,
       d.tipo,
       d.capa,
       d.consumo_recomendado,
       d.motivo_no_consumo,
       d.descripcion,
       d.grano,
       d.clave_negocio,
       d.refresco,
       d.avisos,
       d.n_columnas,
       d.ficha,
       d.paso_etl,
       f.ultimo_ok_finished_at,
       f.horas_desde_ultimo_ok,
       f.ultimo_intento_status,
       p.version        AS diccionario_version,
       p.publicado_en   AS diccionario_publicado_en
FROM _meta.diccionario AS d
LEFT JOIN _meta.v_frescura AS f ON f.paso = d.paso_etl
LEFT JOIN _meta.diccionario_publicacion AS p ON TRUE;

COMMENT ON VIEW _meta.v_diccionario IS
'Punto de entrada del MCP: significado, grano, trampas y fecha de build de cada '
'objeto en una sola consulta. Los dos JOIN son LEFT a proposito. Anadir columnas '
'al final es compatible; quitarlas o reordenarlas exige DROP VIEW y, acto '
'seguido, python main.py apply-grants.';
