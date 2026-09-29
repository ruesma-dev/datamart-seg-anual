-- etl_sigrid/infrastructure/postgres/sql/ddl/00_meta.sql
--
-- Tabla de tracking de ejecuciones del pipeline.
-- Una fila por (stage, step) ejecutado, con tiempos, status y filas procesadas.
-- Permite ver el histórico, debugging y métricas básicas.

CREATE TABLE IF NOT EXISTS _meta.etl_runs (
    id              BIGSERIAL PRIMARY KEY,
    stage           VARCHAR(50)  NOT NULL,
    step            VARCHAR(100) NOT NULL,
    started_at      TIMESTAMP    NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMP    NULL,
    status          VARCHAR(20)  NOT NULL DEFAULT 'RUNNING',
    rows_processed  BIGINT       NOT NULL DEFAULT 0,
    error_message   TEXT         NULL,
    metadata        JSONB        NULL
);

CREATE INDEX IF NOT EXISTS idx_etl_runs_started_at ON _meta.etl_runs (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_etl_runs_stage_step ON _meta.etl_runs (stage, step, started_at DESC);

-- ===========================================================================
-- F-024 · Coherencia del datamart ante cargas truncadas
--
-- Este fichero lo ejecuta _bootstrap_schemas_and_meta en la PRIMERA conexion
-- de cada proceso. Por eso todo lo de aqui es idempotente, y por eso las dos
-- vistas existen antes de que nadie las consulte.
-- ===========================================================================

-- Identidad de ejecucion. Se ANADE, no se recrea la tabla: el historico de
-- _meta.etl_runs es el unico sitio donde consta cuanto tardo cada carga y que
-- paso las noches que fallaron. Las filas anteriores a F-024 quedan con
-- batch_id NULL y `python main.py timings` sigue funcionando sobre ellas.
ALTER TABLE _meta.etl_runs ADD COLUMN IF NOT EXISTS batch_id TEXT NULL;
CREATE INDEX IF NOT EXISTS idx_etl_runs_batch ON _meta.etl_runs (batch_id);

-- Ultima ingesta de cada tabla de raw. Es lo que lee la puerta de stage,
-- `check-coherencia`, el MCP y Power BI: una sola fuente de verdad para la
-- pregunta "de que carga viene esta tabla".
--
-- Una fila por tabla, la mas reciente manda. El desempate por id DESC no es
-- decorativo: dos ingestas de la misma tabla en el mismo segundo (un reintento
-- inmediato) tienen el mismo started_at, y sin el la vista bailaria.
CREATE OR REPLACE VIEW _meta.v_raw_state AS
SELECT DISTINCT ON (step)
       substr(step, length('ingest_raw.') + 1) AS tabla,
       status                                  AS status,
       batch_id                                AS batch_id,
       started_at                              AS started_at,
       finished_at                             AS finished_at,
       rows_processed                          AS filas,
       id                                      AS run_id
FROM _meta.etl_runs
WHERE step LIKE 'ingest_raw.%'
ORDER BY step, started_at DESC, id DESC;

-- Frescura por paso de pipeline. "Ultimo OK" y "ultimo intento" van por
-- separado a proposito: no son la misma noticia. Un build_mart que fallo esta
-- noche deja mart con lo de ayer, y quien consulta el dato tiene que ver las
-- dos cosas: de cuando es lo que esta viendo, y que lo ultimo que se intento
-- salio mal.
--
-- Solo pasos de nivel de pipeline (step sin punto). Sin ese filtro habria una
-- fila por cada uno de los ~60 tramos de build_plan_mensual y la vista dejaria
-- de ser legible.
--
-- El LEFT JOIN es deliberado: un paso que nunca termino bien sigue saliendo,
-- con ultimo_ok_* a nulo. Un INNER JOIN lo esconderia, que es justo el
-- silencio que esta feature elimina.
CREATE OR REPLACE VIEW _meta.v_frescura AS
WITH pasos AS (
    SELECT * FROM _meta.etl_runs WHERE position('.' IN step) = 0
),
ultimo_ok AS (
    SELECT DISTINCT ON (step) step, finished_at, batch_id, rows_processed
    FROM pasos
    WHERE status = 'SUCCESS'
    ORDER BY step, finished_at DESC NULLS LAST, id DESC
),
ultimo_intento AS (
    SELECT DISTINCT ON (step) step, started_at, status, error_message
    FROM pasos
    ORDER BY step, started_at DESC, id DESC
)
SELECT i.step            AS paso,
       o.finished_at     AS ultimo_ok_finished_at,
       o.batch_id        AS ultimo_ok_batch_id,
       o.rows_processed  AS ultimo_ok_filas,
       -- started_at y finished_at son TIMESTAMP sin zona escritos con
       -- datetime.utcnow(). Comparar contra un now() local daria el desfase
       -- horario de Espana como antiguedad, y en verano son dos horas. Si
       -- algun dia se migra a timestamptz, esta es la unica linea que cambia.
       EXTRACT(EPOCH FROM (now() AT TIME ZONE 'UTC' - o.finished_at)) / 3600.0
                         AS horas_desde_ultimo_ok,
       i.started_at      AS ultimo_intento_started_at,
       i.status          AS ultimo_intento_status,
       i.error_message   AS ultimo_intento_error
FROM ultimo_intento i
LEFT JOIN ultimo_ok o USING (step);

-- ===========================================================================
-- F-025 · La ventana de negocio: de que noche es el dato de cada obra
--
-- Desde F-025 el datamart NO reconstruye todas las obras cada noche: 880 de
-- las 920 estan congeladas por el criterio que decidio el humano el
-- 2026-09-02, y solo 40 se rehacen a diario. Eso convierte "de cuando es este
-- dato" en una pregunta POR OBRA, y estos dos objetos son su respuesta.
--
-- El humano lo pidio con estas palabras: "que no se reconstruyan, pero que no
-- se borren, y que la informacion este CONSULTABLE". Lo tercero es esto.
--
-- Idempotente como todo este fichero: lo ejecuta _bootstrap_schemas_and_meta
-- en la PRIMERA conexion de cada proceso. CREATE TABLE IF NOT EXISTS y
-- CREATE OR REPLACE VIEW, ningun DROP: dropear la tabla borraria de que noche
-- viene cada obra, que es justo lo que no se puede perder.
-- ===========================================================================

CREATE TABLE IF NOT EXISTS _meta.obra_build (
    obra_id         BIGINT    PRIMARY KEY,
    codigo_obra     TEXT      NULL,

    -- LAS DOS FIRMAS SON COLUMNAS DISTINTAS Y NO ES REDUNDANCIA.
    -- `firma_origen` es la que tenia el origen CUANDO SE CONSTRUYO esta obra;
    -- `firma_actual` la que tiene AHORA, y la escribe cada noche el sub-paso
    -- que va tras la ingesta. Comparar las dos es lo que detecta que una obra
    -- congelada ha cambiado en Sigrid. Con una sola columna, la ingesta
    -- pisaria la referencia cada noche y la comparacion no diria nada.
    firma_origen    TEXT      NULL,
    firma_actual    TEXT      NULL,
    firma_actual_at TIMESTAMP NULL,

    -- Sello del SQL con el que se construyo (R17). Si el SQL cambia, esa noche
    -- se reconstruyen TODAS: sin esto, un arreglo como el de F-052 solo
    -- alcanzaria a las 40 obras vivas y las otras 880 seguirian publicando lo
    -- de antes, en silencio.
    sello_sql       TEXT      NULL,

    -- De que ejecucion viene lo construido (R14). `construido_at` solo se
    -- mueve cuando la obra se reconstruye DE VERDAD: una obra congelada
    -- conserva la fecha de su ultima construccion buena, porque mentir aqui
    -- vaciaria de sentido la vista de abajo.
    batch_id        TEXT      NULL,
    construido_at   TIMESTAMP NULL,
    filas           BIGINT    NOT NULL DEFAULT 0,

    -- La decision de la ultima noche y su porque, en el vocabulario cerrado de
    -- domain/ventana.py: completa, sello, sin_filas, firma, ventana.
    congelada       BOOLEAN   NOT NULL DEFAULT FALSE,
    motivo          TEXT      NULL,
    detalle         TEXT      NULL
);

-- Migracion defensiva, por si la tabla se creo con una version anterior de
-- este fichero. Mismo patron que el ALTER de `batch_id` de F-024: se ANADE,
-- no se recrea, porque el historico de que noche viene cada obra no se
-- reconstruye a posteriori.
ALTER TABLE _meta.obra_build ADD COLUMN IF NOT EXISTS firma_actual    TEXT      NULL;
ALTER TABLE _meta.obra_build ADD COLUMN IF NOT EXISTS firma_actual_at TIMESTAMP NULL;
ALTER TABLE _meta.obra_build ADD COLUMN IF NOT EXISTS congelada       BOOLEAN   NOT NULL DEFAULT FALSE;
ALTER TABLE _meta.obra_build ADD COLUMN IF NOT EXISTS detalle         TEXT      NULL;

CREATE INDEX IF NOT EXISTS idx_obra_build_construido
    ON _meta.obra_build (construido_at DESC);
CREATE INDEX IF NOT EXISTS idx_obra_build_congelada
    ON _meta.obra_build (congelada, construido_at DESC);
CREATE INDEX IF NOT EXISTS idx_obra_build_codigo
    ON _meta.obra_build (codigo_obra);

-- Frescura POR OBRA. Hermana de _meta.v_frescura, que responde lo mismo por
-- paso de pipeline; esta lo baja al grano en el que la ventana toma sus
-- decisiones. La leen igual el MCP, Power BI y `check-ventana`.
--
-- `firma_divergente` es la denuncia de la que habla R16: la obra esta
-- congelada y su origen HA CAMBIADO. No se reconstruye por su cuenta -eso
-- contradiria la decision del humano, que congela 8 de las 48 obras con
-- actividad reciente sabiendolo- pero queda NOMBRADA, que es lo contrario del modo de
-- fallo de F-052: un dato que envejece sin que nadie se entere.
--
-- Las dos firmas se comparan solo cuando LAS DOS existen. Con cualquiera a
-- nulo la respuesta es FALSE: no se sabe, y "no se sabe" no es "cambio". Una
-- obra sin registro entra ya por R18, que es un camino mas honesto que
-- inventarse una divergencia.
--
-- `horas_desde_construccion` usa `now() AT TIME ZONE 'UTC'` por la misma razon
-- que _meta.v_frescura: los TIMESTAMP se escriben con datetime.utcnow() y sin
-- zona, asi que restarles un now() local daria el desfase horario de Espana
-- como antiguedad -dos horas en verano-.
CREATE OR REPLACE VIEW _meta.v_frescura_obra AS
SELECT b.obra_id                        AS obra_id,
       b.codigo_obra                    AS codigo_obra,
       b.construido_at                  AS construido_at,
       EXTRACT(EPOCH FROM (now() AT TIME ZONE 'UTC' - b.construido_at)) / 3600.0
                                        AS horas_desde_construccion,
       b.batch_id                       AS batch_id,
       b.filas                          AS filas,
       b.congelada                      AS congelada,
       b.motivo                         AS motivo,
       b.detalle                        AS detalle,
       b.sello_sql                      AS sello_sql,
       (b.firma_origen IS NOT NULL
        AND b.firma_actual IS NOT NULL
        AND b.firma_origen <> b.firma_actual) AS firma_divergente,
       b.firma_actual_at                AS firma_comprobada_at
FROM _meta.obra_build b;
