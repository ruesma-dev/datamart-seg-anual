-- etl_sigrid/infrastructure/postgres/sql/ddl/01_diccionario.sql
--
-- ===========================================================================
-- EL CONTRATO CON `mcp-bbdd` (F-006). LEER ANTES DE TOCAR NADA.
-- ===========================================================================
--
-- Estas CUATRO tablas y esta vista son lo unico que este repositorio le garantiza
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
-- meter ahi las tablas del contrato encareceria el arranque de todos los comandos por
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
-- F-147: `resumen` y `entrega`, AL FINAL (contrato aditivo pactado con
-- `mcp-bbdd` el 2026-10-22). Las siete de arriba no cambian.
-- ---------------------------------------------------------------------------
-- `resumen` es la ORDEN corta que basta sola y que `contexto_bbdd` sirve en
-- lugar de `regla` + `motivo` (el detalle, para `describir_tabla`).
-- `entrega` dice que se sirve: 'resumen' o 'entera'. Las reglas `fuera_mcp`
-- del YAML no llegan a esta tabla.
--
-- POR QUE UN BLOQUE DO Y NO `ADD COLUMN IF NOT EXISTS`: este fichero corre en
-- CADA publicacion, con el MCP leyendo, y `ALTER TABLE` toma `ACCESS
-- EXCLUSIVE` AUNQUE la columna ya exista: bloquearia a los lectores cada noche,
-- justo lo que el vaciado con DELETE de `diccionario_sql.py` evita. Mirando
-- antes el catalogo, cada ALTER corre UNA vez en la vida de la tabla. Con un
-- valor por defecto constante, anadir la columna es un cambio de catalogo
-- (PostgreSQL >= 11): no reescribe la tabla.
--
-- LOS CHECK (peticion A de `mcp-bbdd`: la base garantiza lo que el MCP da por
-- hecho). Se anaden `NOT VALID` porque la tabla ya tiene filas cuando llega
-- este DDL, y con `resumen` a '' (el DEFAULT que exige anadir una columna NOT
-- NULL a una tabla con filas) un CHECK validado fallaria. `NOT VALID` obliga
-- igual a toda fila NUEVA desde ese momento, asi que la primera publicacion ya
-- escribe bajo la restriccion; el `VALIDATE` corre en la publicacion siguiente
-- (la nocturna), cuando ninguna fila la incumple, y solo una vez. `VALIDATE
-- CONSTRAINT` toma `SHARE UPDATE EXCLUSIVE`, que no bloquea a los lectores.
-- El tope de 250 es `RESUMEN_MAX` de `etl_sigrid/domain/diccionario.py`; un
-- test los ata.
--
-- OJO AL DESPLIEGUE: con el CHECK puesto, una imagen ANTERIOR a F-147 ya no
-- puede publicar (su INSERT no trae `resumen` y el DEFAULT '' lo incumple). El
-- job tiene que estar en la imagen nueva ANTES de la primera publicacion.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = '_meta' AND table_name = 'diccionario_reglas'
          AND column_name = 'resumen'
    ) THEN
        ALTER TABLE _meta.diccionario_reglas
            ADD COLUMN resumen TEXT NOT NULL DEFAULT '';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = '_meta' AND table_name = 'diccionario_reglas'
          AND column_name = 'entrega'
    ) THEN
        ALTER TABLE _meta.diccionario_reglas
            ADD COLUMN entrega TEXT NOT NULL DEFAULT 'resumen';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = '_meta.diccionario_reglas'::regclass
          AND conname = 'diccionario_reglas_entrega_check'
    ) THEN
        ALTER TABLE _meta.diccionario_reglas
            ADD CONSTRAINT diccionario_reglas_entrega_check
            CHECK (entrega IN ('resumen', 'entera')) NOT VALID;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = '_meta.diccionario_reglas'::regclass
          AND conname = 'diccionario_reglas_resumen_check'
    ) THEN
        ALTER TABLE _meta.diccionario_reglas
            ADD CONSTRAINT diccionario_reglas_resumen_check
            CHECK (char_length(btrim(resumen)) BETWEEN 1 AND 250) NOT VALID;
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = '_meta.diccionario_reglas'::regclass
          AND conname = 'diccionario_reglas_entrega_check' AND NOT convalidated
    ) AND NOT EXISTS (
        SELECT 1 FROM _meta.diccionario_reglas
        WHERE NOT (entrega IN ('resumen', 'entera'))
    ) THEN
        ALTER TABLE _meta.diccionario_reglas
            VALIDATE CONSTRAINT diccionario_reglas_entrega_check;
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = '_meta.diccionario_reglas'::regclass
          AND conname = 'diccionario_reglas_resumen_check' AND NOT convalidated
    ) AND NOT EXISTS (
        SELECT 1 FROM _meta.diccionario_reglas
        WHERE NOT (char_length(btrim(resumen)) BETWEEN 1 AND 250)
    ) THEN
        ALTER TABLE _meta.diccionario_reglas
            VALIDATE CONSTRAINT diccionario_reglas_resumen_check;
    END IF;
END
$$;

COMMENT ON COLUMN _meta.diccionario_reglas.resumen IS
'F-147. La orden corta (1-250 caracteres) que basta sola. contexto_bbdd la '
'sirve en lugar de regla + motivo, que son el detalle.';

COMMENT ON COLUMN _meta.diccionario_reglas.entrega IS
'F-147. Que se sirve de la regla: resumen (el resumen; el detalle con '
'describir_tabla) o entera (siempre entera). Las fuera_mcp no se publican.';

-- ---------------------------------------------------------------------------
-- El CONTEXTO global: convenciones, ordenes de magnitud, ejes y esquemas.
-- ---------------------------------------------------------------------------
-- ENMIENDA DEL CONTRATO, 2026-08-22. Nace porque al implementar el proveedor de
-- `mcp-bbdd` se vio que `_meta` publicaba los objetos y las reglas pero NO el
-- resto del bloque global, asi que el MCP en cloud habria respondido PEOR que el
-- prototipo local, que lo servia entero.
--
-- UNA FILA POR ENTRADA, igual que `diccionario_reglas`, y no columnas nuevas en
-- `diccionario_publicacion`: asi el contrato crece anadiendo FILAS y nunca rompe
-- a quien ya lee. Es el mismo criterio que puso `motivo_no_consumo` al final de
-- la vista en vez de en medio.
--
-- `texto` va siempre y es lo que el agente inyecta tal cual. `datos` lleva la
-- entrada entera en JSONB para quien necesite los campos sueltos —el valor
-- numerico de un orden de magnitud, por ejemplo— sin parsear prosa.
CREATE TABLE IF NOT EXISTS _meta.diccionario_contexto (
    bloque  TEXT    NOT NULL,   -- convenciones|ordenes_de_magnitud|ejes|esquemas
    clave   TEXT    NOT NULL,   -- moneda | <concepto> | magnitud | mart ...
    orden   INTEGER NOT NULL DEFAULT 0,
    texto   TEXT    NOT NULL,
    datos   JSONB   NOT NULL,
    PRIMARY KEY (bloque, clave)
);

COMMENT ON TABLE _meta.diccionario_contexto IS
'Contexto global que el agente necesita ANTES de consultar: convenciones de '
'moneda/IVA/fecha, ordenes de magnitud para detectar una cifra absurda, los '
'literales exactos de escenario y para que sirve cada esquema. Crece anadiendo '
'filas, nunca columnas.';

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
       p.publicado_en   AS diccionario_publicado_en,
       -- AL FINAL, y no junto a `consumo_recomendado`, que es donde tendria
       -- sentido leerla: las 18 columnas anteriores son el contrato publicado
       -- en design.md §4.2 y meter una por el medio corre de posicion a todas
       -- las que van detras. Quien desempaquete por indice se encontraria los
       -- campos cambiados sin que nada fallase. Anadir al final es la unica
       -- forma compatible de crecer, y es la regla que este mismo fichero
       -- declara en su cabecera.
       d.motivo_no_consumo
FROM _meta.diccionario AS d
LEFT JOIN _meta.v_frescura AS f ON f.paso = d.paso_etl
LEFT JOIN _meta.diccionario_publicacion AS p ON TRUE;

COMMENT ON COLUMN _meta.diccionario_publicacion.version IS
'Numero de version manual del diccionario. Lo sube una persona al cambiar el '
'contenido y sirve para COMUNICAR el cambio. NO es la identidad: la identidad '
'es hash_fuente, que cambia solo con cualquier edicion. Para invalidar una '
'cache hay que mirar hash_fuente, no esto.';

COMMENT ON COLUMN _meta.diccionario_publicacion.n_columnas IS
'Total de columnas documentadas, en TODAS las fichas.';

COMMENT ON COLUMN _meta.diccionario_publicacion.cobertura_cols IS
'Porcentaje de columnas con significado dentro de la superficie de consumo '
'(consumo_recomendado = true) y SOLO de ella. OJO: NO comparte denominador con '
'n_columnas, asi que n_columnas * cobertura_cols / 100 no es el numero de '
'columnas descritas. Son dos medidas de cosas distintas: una es volumen y la '
'otra es completitud de lo que se recomienda consultar.';

COMMENT ON VIEW _meta.v_diccionario IS
'Punto de entrada del MCP: significado, grano, trampas y fecha de build de cada '
'objeto en una sola consulta. Los dos JOIN son LEFT a proposito. Anadir columnas '
'al final es compatible; quitarlas o reordenarlas exige DROP VIEW y, acto '
'seguido, python main.py apply-grants.';
