-- etl_sigrid/infrastructure/postgres/sql/descompuestos/02_lineas_coste.sql
-- ============================================================================
-- F-097 · SCHEMA descompuestos (3/7): las dos tablas publicadas que PERSISTEN
-- entre noches y las lineas de COSTE (ambito 3): ESTUDIO y PLANIF_JO.
--
-- Lee: descompuestos._des_texto, raw.obr, raw.dncpro, raw.con, raw.auxpronat.
--
-- POR QUE `CREATE ... IF NOT EXISTS` Y NO `DROP + CREATE`. Las lineas y el
-- cuadre del master (MASTER_*) se trocean por lotes de versiones (03): lo de
-- las versiones que no se tocan esta noche tiene que seguir ahi. Por eso las
-- dos tablas se crean una vez y cada origen se reconstruye por su cuenta. El
-- cuadre se declara aqui y no en 05 porque 03 lo escribe antes (sus lineas y
-- su cuadre van en la MISMA transaccion por version, R8/R21).
--
-- LA CLAVE LLEVA `obra_id` (desviacion 1 del implementer, 2026-09-28). La spec
-- dice (origen, partida, ambito, fase, orden), pero Sigrid tiene 227 filas con
-- `obride = 0` en la version 26 del master cuyas partidas TAMBIEN estan, con
-- descompuesto, en otra obra: medido en solo lectura, las 227 chocan. El
-- troceado las conserva (lo pide la spec) y el cuadre las deja fuera.
--
-- LOS DOS ORIGENES DE COSTE, que son las dos pestanas del ambito 3:
--
--   ESTUDIO    la «Descomposicion» (ambito 3 fase 0), SOLO de las partidas SIN
--              ningun registro enlazado a la planificacion (D1): en 7.866 de
--              las 42.958 partidas con `des` ese texto es copia de su `dncpro`
--              y ya no es Estudios. Esas salen en el cuadre como
--              SUSTITUIDO_POR_PLANIFICACION (05) y su Estudios original, si
--              existe, esta en la version 0 del master (MASTER_INICIAL).
--   PLANIF_JO  la «Planificacion compras»: las lineas de `dncpro` de la
--              necesidad de la obra (`obr.dncide`), con partida, en el orden de
--              la pestana (`pos`, `ide`), y con lo que solo ella tiene:
--              proveedor recomendado, contrato y linea adjudicados, fecha
--              maxima, grupo, nivel (D6, D10). Su `precio` es el ADJUDICADO
--              (aviso de F-038).
--
-- Los dos se reconstruyen ENTEROS cada noche (R21): 120.373 registros y
-- ~287.000 lineas, segundos.
-- ============================================================================

CREATE TABLE IF NOT EXISTS descompuestos.lineas (
    origen                    TEXT NOT NULL,
    obra_id                   BIGINT NOT NULL,
    partida_id                BIGINT NOT NULL,
    presupuesto_id            BIGINT,
    ambito_id                 INTEGER NOT NULL,
    fase_num                  INTEGER NOT NULL,
    orden                     INTEGER NOT NULL,
    codigo_elemento           TEXT,
    descripcion               TEXT,
    unidad                    TEXT,
    codigo_alternativo        TEXT,
    tipo_elemento_codigo      TEXT,
    tipo_elemento             TEXT NOT NULL,
    naturaleza_codigo         TEXT,
    naturaleza                TEXT,
    rendimiento               NUMERIC,
    precio                    NUMERIC,
    importe_unitario          NUMERIC(18,2),
    cantidad_total            NUMERIC,
    importe_total             NUMERIC(18,2),
    es_porcentaje             BOOLEAN NOT NULL,
    porcentaje                NUMERIC,
    base_porcentaje           NUMERIC,
    dncpro_id                 BIGINT,
    producto_id               BIGINT,
    proveedor_recomendado_id  BIGINT,
    contrato_id               BIGINT,
    contrato_linea_id         BIGINT,
    fecha_maxima              DATE,
    grupo_planificacion_id    BIGINT,
    nivel                     INTEGER,
    es_nivel_padre            BOOLEAN,
    es_version_inicial        BOOLEAN,
    es_primera_abc            BOOLEAN,
    es_vigente                BOOLEAN,
    es_ultima                 BOOLEAN,
    tipo_version              TEXT,
    texto_version             TEXT,
    CONSTRAINT ck_lineas_origen CHECK (origen IN ('ESTUDIO', 'PLANIF_JO', 'MASTER_INICIAL', 'MASTER_PRE_ABC', 'MASTER_PLANIF_JO')),
    CONSTRAINT pk_lineas PRIMARY KEY (origen, obra_id, partida_id, ambito_id, fase_num, orden)
);

CREATE INDEX IF NOT EXISTS ix_lineas_version ON descompuestos.lineas (obra_id, ambito_id, fase_num);
CREATE INDEX IF NOT EXISTS ix_lineas_partida ON descompuestos.lineas (partida_id);

COMMENT ON TABLE descompuestos.lineas IS
'F-097. Una fila por linea de descompuesto de cada partida, con su origen (ESTUDIO, PLANIF_JO, MASTER_INICIAL, MASTER_PRE_ABC, MASTER_PLANIF_JO). Nunca se suman origenes distintos: R-DESCOMPUESTO-ORIGEN.';

CREATE TABLE IF NOT EXISTS descompuestos.cuadre_partida (
    origen             TEXT NOT NULL,
    obra_id            BIGINT NOT NULL,
    partida_id         BIGINT NOT NULL,
    ambito_id          INTEGER NOT NULL,
    fase_num           INTEGER NOT NULL,
    presupuesto_id     BIGINT,
    precio_partida     NUMERIC(18,2),
    suma_descompuesto  NUMERIC(18,2),
    diferencia         NUMERIC(18,2),
    num_lineas         INTEGER NOT NULL,
    estado             TEXT NOT NULL,
    CONSTRAINT ck_cuadre_origen CHECK (origen IN ('ESTUDIO', 'PLANIF_JO', 'MASTER_INICIAL', 'MASTER_PRE_ABC', 'MASTER_PLANIF_JO')),
    CONSTRAINT ck_cuadre_estado CHECK (estado IN ('CUADRA', 'NO_CUADRA', 'SIN_DESCOMPUESTO', 'SUSTITUIDO_POR_PLANIFICACION')),
    CONSTRAINT pk_cuadre_partida PRIMARY KEY (origen, partida_id, ambito_id, fase_num)
);

CREATE INDEX IF NOT EXISTS ix_cuadre_version ON descompuestos.cuadre_partida (obra_id, ambito_id, fase_num);

COMMENT ON TABLE descompuestos.cuadre_partida IS
'F-097. Una fila por (origen, partida hoja con precio, ambito, fase): la suma del descompuesto por unidad frente al precio de la partida, y su estado.';

-- ---------------------------------------------------------------------------
-- ESTUDIO y PLANIF_JO se reconstruyen enteros: fuera lo de anoche.
-- ---------------------------------------------------------------------------
DELETE FROM descompuestos.lineas WHERE origen IN ('ESTUDIO', 'PLANIF_JO');

-- ESTUDIO (R15): el ambito 3 fase 0 de las partidas sin un solo registro
-- enlazado. `enlazadas` son las filas de `obrparpre` cuya «Descomposicion» ya
-- es la planificacion del jefe de obra.
WITH troceado AS (
    SELECT d.presupuesto_id, d.obra_id, d.partida_id, d.ambito_id, d.fase_num, t.*
    FROM descompuestos._des_texto d
    CROSS JOIN LATERAL descompuestos.fn_trocear(d.des) t
    WHERE d.ambito_id = 3 AND d.fase_num = 0
),
enlazadas AS (
    SELECT DISTINCT t.presupuesto_id
    FROM troceado t
    WHERE t.dncpro_id IS NOT NULL
)
INSERT INTO descompuestos.lineas (
    origen, obra_id, partida_id, presupuesto_id, ambito_id, fase_num, orden,
    codigo_elemento, descripcion, unidad, codigo_alternativo,
    tipo_elemento_codigo, tipo_elemento, naturaleza_codigo, naturaleza,
    rendimiento, precio, importe_unitario, cantidad_total, importe_total,
    es_porcentaje, porcentaje, base_porcentaje, dncpro_id, producto_id,
    proveedor_recomendado_id, contrato_id, contrato_linea_id, fecha_maxima,
    grupo_planificacion_id, nivel, es_nivel_padre, es_version_inicial,
    es_primera_abc, es_vigente, es_ultima, tipo_version, texto_version
)
SELECT 'ESTUDIO', t.obra_id, t.partida_id, t.presupuesto_id, t.ambito_id, t.fase_num, t.orden,
       t.codigo_elemento, t.descripcion, t.unidad, t.codigo_alternativo,
       t.tipo_elemento_codigo, t.tipo_elemento, t.naturaleza_codigo, t.naturaleza,
       t.rendimiento, t.precio, t.importe_unitario, t.cantidad_total, t.importe_total,
       t.es_porcentaje, t.porcentaje, t.base_porcentaje,
       -- sin enlaces por construccion: ni linea de necesidad ni producto
       NULL::BIGINT, NULL::BIGINT,
       NULL::BIGINT, NULL::BIGINT, NULL::BIGINT, NULL::DATE,
       NULL::BIGINT, NULL::INTEGER, NULL::BOOLEAN, NULL::BOOLEAN,
       NULL::BOOLEAN, NULL::BOOLEAN, NULL::BOOLEAN, NULL::TEXT, NULL::TEXT
FROM troceado t
WHERE NOT EXISTS (SELECT 1 FROM enlazadas e WHERE e.presupuesto_id = t.presupuesto_id);

-- PLANIF_JO (R16): `dncpro` de la necesidad de la obra, con partida. Se
-- publica con ambito 3 y fase 0 (en `dncpro`, `ambide` y `fas` estan siempre a
-- 0) y sin `presupuesto_id`: no sale de `obrparpre`. No tiene tipo de elemento
-- (SIN_TIPO); su clasificacion es la naturaleza del producto (`auxpronat`).
INSERT INTO descompuestos.lineas (
    origen, obra_id, partida_id, presupuesto_id, ambito_id, fase_num, orden,
    codigo_elemento, descripcion, unidad, codigo_alternativo,
    tipo_elemento_codigo, tipo_elemento, naturaleza_codigo, naturaleza,
    rendimiento, precio, importe_unitario, cantidad_total, importe_total,
    es_porcentaje, porcentaje, base_porcentaje, dncpro_id, producto_id,
    proveedor_recomendado_id, contrato_id, contrato_linea_id, fecha_maxima,
    grupo_planificacion_id, nivel, es_nivel_padre, es_version_inicial,
    es_primera_abc, es_vigente, es_ultima, tipo_version, texto_version
)
SELECT 'PLANIF_JO', o.ide, p.paride, NULL::BIGINT, 3, 0,
       (row_number() OVER (PARTITION BY o.ide, p.paride ORDER BY p.pos, p.ide))::INTEGER,
       NULLIF(btrim(c.cod), ''), NULLIF(btrim(p.res), ''), NULLIF(btrim(p.unimed), ''),
       NULLIF(btrim(p.cod2), ''),
       NULL::TEXT, 'SIN_TIPO', NULLIF(btrim(n.cod), ''), NULLIF(btrim(n.res), ''),
       p.canren::NUMERIC, p.pre::NUMERIC,
       -- lo que no cabe en NUMERIC(18,2) es NULL, como en fn_trocear (review 1)
       CASE WHEN abs(ROUND(p.pre::NUMERIC * p.canren::NUMERIC, 2)) < 1e16
           THEN ROUND(p.pre::NUMERIC * p.canren::NUMERIC, 2) END,
       p.can::NUMERIC,
       CASE WHEN abs(ROUND(p.can::NUMERIC * p.pre::NUMERIC, 2)) < 1e16
           THEN ROUND(p.can::NUMERIC * p.pre::NUMERIC, 2) END,
       FALSE, NULL::NUMERIC, NULL::NUMERIC,
       p.ide, NULLIF(p.proide, 0),
       NULLIF(p.entide, 0), NULLIF(p.adjctride, 0), NULLIF(p.adjctrlin, 0),
       descompuestos.fn_fecha(p.fec),
       NULLIF(p.gpcide, 0), p.niv, COALESCE(p.nivpad, 0) <> 0,
       NULL::BOOLEAN, NULL::BOOLEAN, NULL::BOOLEAN, NULL::BOOLEAN, NULL::TEXT, NULL::TEXT
FROM raw.obr o
JOIN raw.dncpro p ON p.dncide = o.dncide
LEFT JOIN raw.con c ON c.ide = p.proide
LEFT JOIN raw.auxpronat n ON n.ide = p.natide
WHERE COALESCE(o.dncide, 0) <> 0 AND COALESCE(p.paride, 0) <> 0;
