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
