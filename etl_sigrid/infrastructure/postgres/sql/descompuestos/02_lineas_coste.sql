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
-- LOS DOS ORIGENES DE COSTE, que son las dos pestanas del ambito 3. Coste
-- fase 0 es la FASE VIVA: el presupuesto de coste que el jefe de obra
-- evoluciona dia a dia; su descompuesto es la planificacion de compras.
--
--   ESTUDIO    la «Descomposicion» (ambito 3 fase 0), SOLO en las obras SIN
--              master 0 (F-123: sin version 0 cargada en
--              `_versiones_cargadas`; donde la hay, Estudios es MASTER_ESTUDIO
--              y lo publica 03) y SOLO de las partidas SIN ningun registro
--              enlazado a la planificacion (D1): en 7.866 de las 42.958
--              partidas con `des` ese texto es copia de su `dncpro` y ya no es
--              Estudios. Esas salen en el cuadre como
--              SUSTITUIDO_POR_PLANIFICACION (05).
--   PLANIF_JO  la «Planificacion compras»: las lineas de `dncpro` de la
--              necesidad de la obra (`obr.dncide`), con partida, en el orden de
--              la pestana (`pos`, `ide`), y con lo que solo ella tiene:
--              proveedor recomendado, contrato y linea adjudicados, fecha
--              maxima, grupo, nivel (D6, D10). Su `precio` es el ADJUDICADO
--              (aviso de F-038).
--
-- Los dos se reconstruyen ENTEROS cada noche (R21): 120.373 registros y
-- ~287.000 lineas, segundos.
--
-- EL FACTOR (F-120). `lineas.factor` es el FACTOR de la Descomposicion de
-- Sigrid: 1 si la linea no tiene, NULL si no hay campo. ESTUDIO lo trae de
-- `fn_trocear` (el campo 14 es «factor x rendimiento»); PLANIF_JO, de
-- `dncpro`, que lo guarda aparte: `factip` 1 -> `faccan`, 0 -> 1, cualquier
-- otro (un 646 medido) -> NULL y sin importe unitario. `canren` es el
-- rendimiento limpio y `can` ya lleva el factor, asi que solo cambia el
-- importe unitario. La columna va AL FINAL (D8): la tabla persiste entre
-- noches y en una base que ya la tiene la anade el `ALTER TABLE`, que es solo
-- catalogo; sin DEFAULT, las filas del master aun no retroceadas quedan NULL.
--
-- EL CAMBIO DE NOMBRE DEL MASTER 0 (F-123). Las dos tablas persisten y
-- `CREATE TABLE IF NOT EXISTS` no cambia un `CHECK` ya instalado: el bloque
-- `DO` de detras de los `CREATE`, antes de cualquier `DELETE` o `INSERT`,
-- traduce el origen de F-097 del master 0 a MASTER_ESTUDIO y cambia los dos
-- `CHECK`, sin `DROP` ni `TRUNCATE` de las tablas. Solo actua la primera vez:
-- despues el `CHECK` ya no nombra el origen viejo. El `UPDATE` hace falta aunque
-- el sello retrocee: sin el, el `ADD CONSTRAINT` fallaria sobre las versiones
-- aun no retroceadas.
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
    factor                    NUMERIC,
    CONSTRAINT ck_lineas_origen CHECK (origen IN ('ESTUDIO', 'PLANIF_JO', 'MASTER_ESTUDIO', 'MASTER_PRE_ABC', 'MASTER_PLANIF_JO')),
    CONSTRAINT pk_lineas PRIMARY KEY (origen, obra_id, partida_id, ambito_id, fase_num, orden)
);

-- La tabla de F-097 no tenia `factor`: se anade sin DROP (F-120, R17).
ALTER TABLE descompuestos.lineas ADD COLUMN IF NOT EXISTS factor NUMERIC;

CREATE INDEX IF NOT EXISTS ix_lineas_version ON descompuestos.lineas (obra_id, ambito_id, fase_num);
CREATE INDEX IF NOT EXISTS ix_lineas_partida ON descompuestos.lineas (partida_id);

COMMENT ON TABLE descompuestos.lineas IS
'F-097. Una fila por linea de descompuesto de cada partida, con su origen (ESTUDIO, PLANIF_JO, MASTER_ESTUDIO, MASTER_PRE_ABC, MASTER_PLANIF_JO). Nunca se suman origenes distintos: R-DESCOMPUESTO-ORIGEN.';

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
    CONSTRAINT ck_cuadre_origen CHECK (origen IN ('ESTUDIO', 'PLANIF_JO', 'MASTER_ESTUDIO', 'MASTER_PRE_ABC', 'MASTER_PLANIF_JO')),
    CONSTRAINT ck_cuadre_estado CHECK (estado IN ('CUADRA', 'NO_CUADRA', 'SIN_DESCOMPUESTO', 'SUSTITUIDO_POR_PLANIFICACION')),
    CONSTRAINT pk_cuadre_partida PRIMARY KEY (origen, partida_id, ambito_id, fase_num)
);

CREATE INDEX IF NOT EXISTS ix_cuadre_version ON descompuestos.cuadre_partida (obra_id, ambito_id, fase_num);

COMMENT ON TABLE descompuestos.cuadre_partida IS
'F-097. Una fila por (origen, partida hoja con precio, ambito, fase): la suma del descompuesto por unidad frente al precio de la partida, y su estado.';

-- ---------------------------------------------------------------------------
-- F-123: la migracion del nombre del master 0 (R15, R16), una vez por tabla.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    -- El unico sitio del SQL donde sigue escrito el origen de F-097: solo
    -- actua si el `CHECK` instalado aun lo admite (MASTER_INICIAL).
    IF EXISTS (SELECT 1 FROM pg_constraint
               WHERE conname = 'ck_lineas_origen'
                 AND conrelid = 'descompuestos.lineas'::regclass
                 AND pg_get_constraintdef(oid) LIKE '%MASTER_INICIAL%') THEN
        ALTER TABLE descompuestos.lineas DROP CONSTRAINT ck_lineas_origen;
        UPDATE descompuestos.lineas SET origen = 'MASTER_ESTUDIO' WHERE origen = 'MASTER_INICIAL';
        ALTER TABLE descompuestos.lineas ADD CONSTRAINT ck_lineas_origen
            CHECK (origen IN ('ESTUDIO', 'PLANIF_JO', 'MASTER_ESTUDIO', 'MASTER_PRE_ABC', 'MASTER_PLANIF_JO'));
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint
               WHERE conname = 'ck_cuadre_origen'
                 AND conrelid = 'descompuestos.cuadre_partida'::regclass
                 AND pg_get_constraintdef(oid) LIKE '%MASTER_INICIAL%') THEN
        ALTER TABLE descompuestos.cuadre_partida DROP CONSTRAINT ck_cuadre_origen;
        UPDATE descompuestos.cuadre_partida SET origen = 'MASTER_ESTUDIO' WHERE origen = 'MASTER_INICIAL';
        ALTER TABLE descompuestos.cuadre_partida ADD CONSTRAINT ck_cuadre_origen
            CHECK (origen IN ('ESTUDIO', 'PLANIF_JO', 'MASTER_ESTUDIO', 'MASTER_PRE_ABC', 'MASTER_PLANIF_JO'));
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- ESTUDIO y PLANIF_JO se reconstruyen enteros: fuera lo de anoche.
-- ---------------------------------------------------------------------------
DELETE FROM descompuestos.lineas WHERE origen IN ('ESTUDIO', 'PLANIF_JO');

-- ESTUDIO (R15): el ambito 3 fase 0 de las partidas sin un solo registro
-- enlazado. `enlazadas` son las filas de `obrparpre` cuya «Descomposicion» ya
-- es la planificacion del jefe de obra. F-123: solo en las obras SIN master 0,
-- decidido contra `_versiones_cargadas` y no contra `lineas` porque 02 corre
-- ANTES que 03 (una version 0 cargada esta noche aun no tendria lineas). Asi
-- ninguna partida tiene a la vez MASTER_ESTUDIO y ESTUDIO.
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
    es_primera_abc, es_vigente, es_ultima, tipo_version, texto_version, factor
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
       NULL::BOOLEAN, NULL::BOOLEAN, NULL::BOOLEAN, NULL::TEXT, NULL::TEXT,
       t.factor
FROM troceado t
WHERE NOT EXISTS (SELECT 1 FROM enlazadas e WHERE e.presupuesto_id = t.presupuesto_id)
  AND NOT EXISTS (SELECT 1 FROM descompuestos._versiones_cargadas v
                  WHERE v.obra_id = t.obra_id AND v.fase_num = 0);

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
    es_primera_abc, es_vigente, es_ultima, tipo_version, texto_version, factor
)
SELECT 'PLANIF_JO', o.ide, p.paride, NULL::BIGINT, 3, 0,
       (row_number() OVER (PARTITION BY o.ide, p.paride ORDER BY p.pos, p.ide))::INTEGER,
       NULLIF(btrim(c.cod), ''), NULLIF(btrim(p.res), ''), NULLIF(btrim(p.unimed), ''),
       NULLIF(btrim(p.cod2), ''),
       NULL::TEXT, 'SIN_TIPO', NULLIF(btrim(n.cod), ''), NULLIF(btrim(n.res), ''),
       p.canren::NUMERIC, p.pre::NUMERIC,
       -- lo que no cabe en NUMERIC(18,2) es NULL, como en fn_trocear (review
       -- 1); con el factor de `dncpro` (F-120)
       CASE WHEN abs(ROUND(p.pre::NUMERIC * f.factor * p.canren::NUMERIC, 2)) < 1e16
           THEN ROUND(p.pre::NUMERIC * f.factor * p.canren::NUMERIC, 2) END,
       p.can::NUMERIC,
       CASE WHEN abs(ROUND(p.can::NUMERIC * p.pre::NUMERIC, 2)) < 1e16
           THEN ROUND(p.can::NUMERIC * p.pre::NUMERIC, 2) END,
       FALSE, NULL::NUMERIC, NULL::NUMERIC,
       p.ide, NULLIF(p.proide, 0),
       NULLIF(p.entide, 0), NULLIF(p.adjctride, 0), NULLIF(p.adjctrlin, 0),
       descompuestos.fn_fecha(p.fec),
       NULLIF(p.gpcide, 0), p.niv, COALESCE(p.nivpad, 0) <> 0,
       NULL::BOOLEAN, NULL::BOOLEAN, NULL::BOOLEAN, NULL::BOOLEAN, NULL::TEXT, NULL::TEXT,
       f.factor
FROM raw.obr o
JOIN raw.dncpro p ON p.dncide = o.dncide
LEFT JOIN raw.con c ON c.ide = p.proide
LEFT JOIN raw.auxpronat n ON n.ide = p.natide
-- El factor de la linea (F-120, D5): sin ELSE, un `factip` raro es NULL.
CROSS JOIN LATERAL (SELECT CASE p.factip WHEN 1 THEN p.faccan::NUMERIC
                                          WHEN 0 THEN 1::NUMERIC END AS factor) f
WHERE COALESCE(o.dncide, 0) <> 0 AND COALESCE(p.paride, 0) <> 0;
