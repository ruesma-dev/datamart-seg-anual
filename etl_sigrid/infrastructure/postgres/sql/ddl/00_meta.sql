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
