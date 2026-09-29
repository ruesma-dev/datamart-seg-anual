-- etl_sigrid/infrastructure/postgres/sql/descompuestos/00_setup.sql
-- ============================================================================
-- F-097 · SCHEMA descompuestos (1/7): el esquema, el ESTADO del incremental y
-- las dos funciones de conversion.
--
-- Modulo independiente, como `contabilidad`: su SQL lee SOLO de `raw.*` y de
-- su propio esquema (R26), y ningun paso depende de el. Lo usan DOS pasos:
--
--   ingest_descompuestos  trae de Sigrid el texto `des` de `obrparpre` (ambito
--                         3 entero cada noche; el master, version a version
--                         por huella) a las dos tablas de ESTADO de aqui.
--   build_descompuestos   lo trocea y lo publica (01-06).
--
-- EL ESTADO NO SE DESTRUYE NUNCA (R2). `_des_texto` y `_versiones_cargadas` son
-- las primeras tablas del datamart que NO se reconstruyen de cero: la nocturna
-- es `run-all --full`, que trunca `raw`, y releer los 2,14 GB del master cada
-- noche serian 65-94 minutos. Por eso viven aqui, fuera de `raw`, con
-- `CREATE ... IF NOT EXISTS` y sin un solo `DROP` ni `TRUNCATE` en ningun
-- fichero de esta carpeta. Si se corrompen: vaciar `_versiones_cargadas` y
-- lanzar `ingest-descompuestos --sin-tope` (1,5-2 h), documentado en
-- docs/ARCHITECTURE.md.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS descompuestos;

-- El texto `des` de Sigrid, una fila por fila de `obrparpre` con descompuesto:
-- el ambito 3 fase 0 (la «Descomposicion» de COSTE) y todas las versiones del
-- master (ambito 8) ya cargadas. Lo escribe SOLO `ingest_descompuestos`, y
-- cada version entra o sale entera en una transaccion junto con su fila de
-- `_versiones_cargadas` (R8): nunca hay dos copias ni media version.
CREATE TABLE IF NOT EXISTS descompuestos._des_texto (
    presupuesto_id  BIGINT PRIMARY KEY,
    obra_id         BIGINT NOT NULL,
    partida_id      BIGINT NOT NULL,
    ambito_id       INTEGER NOT NULL,
    fase_num        INTEGER NOT NULL,
    cantidad        NUMERIC,
    precio          NUMERIC,
    haydes          INTEGER,
    des             TEXT NOT NULL,
    batch_id        TEXT
);

CREATE INDEX IF NOT EXISTS ix_des_texto_version ON descompuestos._des_texto (obra_id, ambito_id, fase_num);

COMMENT ON TABLE descompuestos._des_texto IS
'F-097. Estado del incremental: el texto des de obrparpre (ambito 3 fase 0 y las versiones cargadas del master). No se consulta: se trocea en descompuestos.lineas.';

-- Una fila por version del master cargada: la huella que tenia en Sigrid al
-- cargarla (filas, bytes, huella), de que ejecucion viene y con que SQL se
-- troceo (R11). `sello_troceado` a NULL = releida y pendiente de trocear.
-- `atributos_troceado` es la huella de los atributos de version (origen y
-- flags) que llevan sus lineas: si cambia —la vigente se mueve—, el build
-- actualiza esas lineas sin retrocearlas.
CREATE TABLE IF NOT EXISTS descompuestos._versiones_cargadas (
    obra_id             BIGINT NOT NULL,
    fase_num            INTEGER NOT NULL,
    filas               INTEGER NOT NULL,
    bytes               BIGINT NOT NULL,
    huella              BIGINT,
    batch_id            TEXT,
    cargada_at          TIMESTAMP NOT NULL,
    sello_troceado      TEXT,
    troceada_at         TIMESTAMP,
    atributos_troceado  TEXT,
    PRIMARY KEY (obra_id, fase_num)
);

COMMENT ON TABLE descompuestos._versiones_cargadas IS
'F-097. Estado del incremental: una fila por version del master cargada, con su huella de Sigrid, su batch_id y el sello del SQL con que se troceo.';

-- Un campo numerico del `des` que no es un numero se publica NULL y el build no
-- falla (R14). El patron es el MISMO que `PATRON_NUMERO` del dominio
-- (etl_sigrid/domain/descompuestos.py); lo fija un test. SQL puro e IMMUTABLE
-- para que el planificador lo pueda en linea: se llama cuatro veces por cada
-- una de los ~4,9 M lineas.
CREATE OR REPLACE FUNCTION descompuestos.fn_num(t TEXT)
RETURNS NUMERIC
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE
        WHEN btrim(t) ~ '^[-+]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][-+]?[0-9]{1,3})?$' THEN btrim(t)::NUMERIC
    END
$$;

COMMENT ON FUNCTION descompuestos.fn_num(TEXT) IS
'Convierte un campo del des a NUMERIC; lo que no es un numero (vacio, texto, coma decimal) es NULL.';

-- La fecha de Sigrid es un entero AAAAMMDD (`dncpro.fec`). Misma forma que
-- `contabilidad.fn_fecha`: 0, NULL o invalida -> NULL. La copia es deliberada,
-- como en los otros esquemas modulo.
CREATE OR REPLACE FUNCTION descompuestos.fn_fecha(d BIGINT)
RETURNS DATE
LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
    IF d IS NULL OR d = 0 THEN
        RETURN NULL;
    END IF;
    RETURN to_date(d::TEXT, 'YYYYMMDD');
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END $$;

COMMENT ON FUNCTION descompuestos.fn_fecha(BIGINT) IS
'Convierte una fecha entera de Sigrid (AAAAMMDD) a DATE. NULL para 0, NULL o invalida. Local al schema descompuestos.';
