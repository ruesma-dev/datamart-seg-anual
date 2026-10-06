-- etl_sigrid/infrastructure/postgres/sql/compras/11_historial_estados.sql
-- ============================================================================
-- F-067 · LA FOTO DIARIA DE ESTADOS de contratos (tip 44) y facturas (tip 15).
--
-- ESTAS DOS TABLAS NO SE RECONSTRUYEN. SON HISTORIA QUE NO EXISTE EN SIGRID Y
-- QUE NO SE PUEDE RECUPERAR: NI DROP, NI TRUNCATE, NI DELETE (lo prohíbe un
-- test). `--full` solo trunca `raw`; el resto de `compras` se rehace con
-- DROP + CREATE cada noche sin tocarlas, porque no dependen de ningún objeto
-- del esquema. Si alguien las borra, la historia empieza de nuevo desde cero.
--
-- POR QUÉ EXISTE. La fecha en que un documento cambia de estado no está en
-- Sigrid: `concam` audita 1,5 M de cambios y ni uno del campo `est`, y
-- `confir` no tiene ni una firma de contrato. Decisión del humano
-- (2026-09-06): construirla aquí como foto diaria, que empieza a contar el día
-- que se despliega. `con.tiemod` NO sirve de atajo (D2): la firma no lo mueve.
--
-- POR TRAMOS (documento, estado, desde, hasta), no una fila por día: la foto
-- de cualquier día D se reconstruye con `desde <= D < COALESCE(hasta, ∞)`.
-- ~186.000 tramos de línea base y < 50.000 filas al año, frente a 68 M filas
-- al año de una fila por documento y día en un disco compartido.
--
-- LOS LITERALES —tipos (44, 15), umbral 0.98, motivos y época— son los de
-- `etl_sigrid/domain/historial_estados.py`, donde la regla está escrita como
-- oráculo y probada caso a caso; `tests/test_f067_sql.py` fija que aquí son
-- LOS MISMOS. Un cambio se hace allí y aquí, en el mismo commit.
--
-- Lee: `raw.con` (`ide`, `tip`, `est`, `_ingested_at`). Escribe solo en sus
-- dos tablas. Corre dentro de `build_compras`, en UNA transacción con el
-- fichero entero (`execute_sql_file`): o se toma la foto completa o nada.
-- ============================================================================

-- Una fila por foto TOMADA. Sirve para saber si la historia tiene huecos:
-- una noche sin fila es una noche en que el cambio no se vio, y el tramo
-- siguiente llevará `observado_antes` de dos noches atrás.
CREATE TABLE IF NOT EXISTS compras.historial_estados_fotos (
    observado_en     TIMESTAMPTZ PRIMARY KEY,           -- max(raw.con._ingested_at)
    tomada_en        TIMESTAMPTZ NOT NULL DEFAULT now(), -- cuándo corrió el build
    es_linea_base    BOOLEAN     NOT NULL,              -- la primera foto
    n_documentos     INTEGER     NOT NULL,              -- documentos de la foto en raw.con
    n_cambios        INTEGER     NOT NULL,              -- tramos cerrados por CAMBIO
    n_altas          INTEGER     NOT NULL,              -- documentos nuevos o que reaparecen
    n_desaparecidos  INTEGER     NOT NULL               -- tramos cerrados por DESAPARECIDO
);

-- Una fila por TRAMO: un documento en un estado entre dos fotos.
CREATE TABLE IF NOT EXISTS compras.historial_estados (
    documento_id          BIGINT      NOT NULL,  -- con.ide
    tipo_documento_codigo INTEGER     NOT NULL,  -- con.tip: 44 contrato, 15 factura
    estado_id             INTEGER,               -- con.est, crudo (se traduce en la vista)
    desde                 TIMESTAMPTZ NOT NULL,  -- primera foto que lo ve en este estado
    hasta                 TIMESTAMPTZ,           -- primera foto que ya no; NULL = vigente
    observado_antes       TIMESTAMPTZ,           -- la foto anterior; NULL en la línea base
    es_linea_base         BOOLEAN     NOT NULL,  -- ya estaba así; desde cuándo, no se sabe
    motivo_cierre         TEXT CHECK (motivo_cierre IN ('CAMBIO', 'DESAPARECIDO')),
    PRIMARY KEY (documento_id, desde)
);

-- Como mucho UN tramo abierto por documento: la guarda de grano de la vista.
CREATE UNIQUE INDEX IF NOT EXISTS ux_hist_est_abierto
    ON compras.historial_estados (documento_id) WHERE hasta IS NULL;

-- ---------------------------------------------------------------------------
-- LA FOTO. Pasos 1-6 del design §3, en este orden; el oráculo es
-- `aplicar_foto` y `resumir_foto` del dominio.
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    v_obs          TIMESTAMPTZ;
    v_ult          TIMESTAMPTZ;
    v_actual       BIGINT;
    v_abiertos     BIGINT;
    v_cambios      BIGINT;
    v_desaparecid  BIGINT;
    v_insertados   BIGINT;
BEGIN
    -- 1 · ¿Hay foto nueva? `_ingested_at` es TIMESTAMP (sin zona) y lo escribe
    -- `NOW()` en la zona de la sesión; se lee con la misma, así que el paso a
    -- TIMESTAMPTZ es el inverso exacto (R7).
    SELECT max(c._ingested_at) INTO v_obs FROM raw.con c;
    SELECT max(f.observado_en) INTO v_ult FROM compras.historial_estados_fotos f;
    IF v_obs IS NULL OR v_obs <= v_ult THEN
        RAISE NOTICE 'F-067: sin foto nueva (raw.con observado en %, ultima foto %): no se escribe nada', v_obs, v_ult;
        RETURN;
    END IF;

    -- 2 · La guarda contra una ingesta a medias (R6): una `raw.con` a medias
    -- cerraría como DESAPARECIDOS miles de documentos vivos, y eso no se
    -- deshace. La excepción revierte el build entero de la noche.
    SELECT count(*) INTO v_actual FROM raw.con c WHERE c.tip IN (44, 15);
    SELECT count(*) INTO v_abiertos FROM compras.historial_estados h WHERE h.hasta IS NULL;
    IF v_abiertos > 0 AND v_actual < 0.98 * v_abiertos THEN
        RAISE EXCEPTION 'F-067: raw.con trae % documentos de contrato y factura y la historia tiene % tramos abiertos (menos del 98 %%): ingesta a medias, no se toma la foto', v_actual, v_abiertos;
    END IF;

    -- 3 · Cerrar los que CAMBIARON de estado (R2). Por `ide` Y `tip`, y con
    -- `IS DISTINCT FROM`: un estado que pasa a NULL o sale de NULL es cambio.
    UPDATE compras.historial_estados h
    SET    hasta = v_obs, motivo_cierre = 'CAMBIO'
    FROM   raw.con c
    WHERE  h.hasta IS NULL
      AND  c.ide = h.documento_id
      AND  c.tip = h.tipo_documento_codigo
      AND  c.est IS DISTINCT FROM h.estado_id;
    GET DIAGNOSTICS v_cambios = ROW_COUNT;

    -- 4 · Cerrar los que DESAPARECIERON (R5): ya no hay fila en `raw.con` con
    -- ese `ide` y ese `tip`. No se abre otro tramo para ellos.
    UPDATE compras.historial_estados h
    SET    hasta = v_obs, motivo_cierre = 'DESAPARECIDO'
    WHERE  h.hasta IS NULL
      AND  NOT EXISTS (
               SELECT 1 FROM raw.con c
               WHERE  c.ide = h.documento_id AND c.tip = h.tipo_documento_codigo
           );
    GET DIAGNOSTICS v_desaparecid = ROW_COUNT;

    -- 5 · Abrir un tramo a cada documento de la foto sin tramo abierto: los que
    -- cambiaron, los nuevos y los que reaparecen (R2-R4). Línea base solo en
    -- la primera foto, y entonces `observado_antes` es NULL.
    INSERT INTO compras.historial_estados (
        documento_id, tipo_documento_codigo, estado_id, desde, hasta,
        observado_antes, es_linea_base, motivo_cierre
    )
    SELECT c.ide, c.tip, c.est, v_obs, NULL, v_ult, (v_ult IS NULL), NULL
    FROM   raw.con c
    WHERE  c.tip IN (44, 15)
      AND  NOT EXISTS (
               SELECT 1 FROM compras.historial_estados h
               WHERE  h.documento_id = c.ide AND h.hasta IS NULL
           );
    GET DIAGNOSTICS v_insertados = ROW_COUNT;

    -- 6 · Registrar la foto (R8). Un CAMBIO cierra y reabre en la misma foto,
    -- así que las altas son los insertados menos los cambios.
    INSERT INTO compras.historial_estados_fotos (
        observado_en, es_linea_base, n_documentos, n_cambios, n_altas, n_desaparecidos
    )
    VALUES (v_obs, (v_ult IS NULL), v_actual, v_cambios, v_insertados - v_cambios, v_desaparecid);
END $$;
