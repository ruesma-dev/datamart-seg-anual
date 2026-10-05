-- etl_sigrid/infrastructure/postgres/sql/compras/09_comparativos_detalle.sql
-- ============================================================================
-- F-038 (2026-10-05) · EL COMPARATIVO DE OFERTAS, Fase 2: el detalle.
--
-- Construye:
--   · compras.comparativo_lineas        — una fila por línea del concurso
--     (raw.comlin), con la partida de su necesidad y lo adjudicado.
--   · compras.comparativo_oferta_lineas — una fila por línea de oferta que
--     responde a una línea del comparativo (raw.dcopro, comlinide > 0), con
--     su descuento y, en las líneas OBJETIVO con porcentaje, su BASE en el
--     descompuesto (D4).
--   · compras.comparativo_objetivo      — una fila por comparativo con oferta
--     OBJETIVO: la más reciente, su importe, su % y cuánto casa con la base.
--   · compras.comparativo_firmas        — una fila por firma (raw.confir) de
--     un comparativo: el circuito escalón a escalón (D3).
--
-- Lee de: raw.comlin, raw.dncpro, raw.dcopro, raw.confir, raw.com,
--         compras.comparativo_ofertas y compras.comparativos (08, este mismo
--         paso), compras.fn_porcentaje_dto (00_setup.sql) y
--         descompuestos.lineas.
--
-- LO QUE HAY QUE SABER ANTES DE TOCAR ESTO:
--   · ES EL PRIMER SQL FUERA DE `sql/descompuestos/` QUE LEE ESE ESQUEMA, y
--     `build_compras` corre ANTES que `build_descompuestos`: la base sale del
--     descompuesto de la NOCHE ANTERIOR. La primera ABC y el master 0 son
--     versiones congeladas, así que el desfase no cambia la base. Si
--     `descompuestos.lineas` no existiera (una base recién creada), este
--     fichero falla con el nombre de su sub-paso y lo de 00-08 queda
--     publicado, como fallaría `03_views.sql` sin `maestro.v_obra_fichas`.
--   · `dcopro.dto` ES TEXTO con coma decimal ('10,08%') y con negativos
--     (recargos). Lo convierte `compras.fn_porcentaje_dto`, con el patrón del
--     dominio. El precio de la línea YA es neto (`tot = can × pre`).
--   · LA BASE DEL OBJETIVO (D4, humano 2026-10-04): el descompuesto de la
--     PRIMERA ABC si casa; si no, la versión ANTERIOR más reciente que case;
--     NUNCA una posterior; en obras sin ABC, solo Estudios. Si no casa, se
--     publica la de la regla con `casa_base` falso. Previsión: casan 24.263 de
--     83.329 líneas (29,1 %). Los literales (orígenes, tolerancia, regla)
--     son los de `etl_sigrid/domain/comparativos.py`; un test lo comprueba.
--   · Todo el fichero es UNA transacción: si algo falla, las tablas de anoche
--     siguen publicadas.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- LÍNEAS DEL CONCURSO · una fila por línea de raw.comlin (R25).
-- La partida es la de la NECESIDAD de la línea (`dncpro.paride`): es la llave
-- hacia el descompuesto. Sumadas por comparativo dan su
-- `importe_adjudicado_lineas` (salvo el redondeo al céntimo de cada línea).
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS compras.comparativo_lineas CASCADE;
CREATE TABLE compras.comparativo_lineas AS
SELECT l.ide AS linea_id,
    l.comide                                AS comparativo_id,
    l.numlin                                AS numero_linea,
    l.pos                                   AS posicion,
    NULLIF(l.ctride, 0)                     AS contrato_id,
    NULLIF(l.dncproide, 0)                  AS linea_necesidad_id,
    NULLIF(n.paride, 0)                     AS partida_id,
    NULLIF(l.dcoproide, 0)                  AS linea_oferta_ganadora_id,
    COALESCE(l.can, 0)::NUMERIC(20, 6)      AS cantidad,
    COALESCE(l.pre, 0)::NUMERIC(20, 6)      AS precio,
    (COALESCE(l.can, 0) * COALESCE(l.pre, 0))::NUMERIC(18, 2) AS importe_adjudicado
FROM raw.comlin l
LEFT JOIN raw.dncpro n ON n.ide = NULLIF(l.dncproide, 0);

ALTER TABLE compras.comparativo_lineas ADD PRIMARY KEY (linea_id);
CREATE INDEX idx_com_cln_cmp ON compras.comparativo_lineas (comparativo_id);
CREATE INDEX idx_com_cln_ctr ON compras.comparativo_lineas (contrato_id);
CREATE INDEX idx_com_cln_par ON compras.comparativo_lineas (partida_id);

-- ---------------------------------------------------------------------------
-- LA PRIMERA ABC DE CADA OBRA (`es_primera_abc`, F-097), calculada UNA vez
-- para los dos bloques que la usan: la base de cada línea y la regla del
-- comparativo. Una obra sin fila aquí no tiene ABC: su regla es ESTUDIOS (D2).
-- Temporal: vive lo que la transacción de este fichero.
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE _f038_obra_abc ON COMMIT DROP AS
SELECT d.obra_id, MIN(d.fase_num) AS fase_abc
FROM descompuestos.lineas d
WHERE d.es_primera_abc
GROUP BY d.obra_id;

-- ---------------------------------------------------------------------------
-- LÍNEAS DE OFERTA · una fila por línea de oferta de una línea del concurso
-- (R26), de TODAS las ofertas de `compras.comparativo_ofertas`, con la
-- ficticia marcada. Solo las OBJETIVO con porcentaje buscan base (R29, R30).
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS compras.comparativo_oferta_lineas CASCADE;
CREATE TABLE compras.comparativo_oferta_lineas AS
WITH lineas_oferta AS (
    SELECT lp.ide AS linea_oferta_id,
           o.oferta_id AS oferta_id,
           o.comparativo_id AS comparativo_id,
           lp.comlinide AS comparativo_linea_id,
           NULLIF(lp.proide, 0) AS producto_id,
           lp.res AS descripcion,
           lp.unimed AS unidad_medida,
           COALESCE(lp.can, 0)::NUMERIC(20, 6) AS cantidad,
           COALESCE(lp.pre, 0)::NUMERIC(20, 6) AS precio,      -- YA neto
           lp.tot::NUMERIC(18, 2) AS importe_ofertado_linea,   -- = can × pre
           lp.dto AS descuento_texto,                          -- TEXTO, literal
           compras.fn_porcentaje_dto(lp.dto) AS porcentaje_descuento,
           o.es_ficticia AS es_ficticia,
           o.familia_ficticia AS familia_ficticia
    FROM raw.dcopro lp
    JOIN compras.comparativo_ofertas o ON o.oferta_id = lp.docide
    WHERE lp.comlinide > 0
),
objetivo AS (
    -- Las líneas OBJETIVO con porcentaje (83.329 medidas): las únicas que
    -- buscan base. La obra es la del comparativo (`com.obride`); la partida y
    -- el `dncpro_id`, los de la necesidad de su línea del concurso.
    SELECT lo.linea_oferta_id AS linea_oferta_id,
           lo.precio AS precio,
           lo.porcentaje_descuento AS pct,
           cm.obra_id AS obra_id,
           cl.partida_id AS partida_id,
           cl.linea_necesidad_id AS dncpro_id,
           ab.fase_abc AS fase_abc,
           CASE WHEN ab.fase_abc IS NOT NULL THEN 'ABC' ELSE 'ESTUDIOS' END AS base_regla
    FROM lineas_oferta lo
    LEFT JOIN compras.comparativo_lineas cl ON cl.linea_id = lo.comparativo_linea_id
    LEFT JOIN compras.comparativos cm ON cm.comparativo_id = lo.comparativo_id
    LEFT JOIN _f038_obra_abc ab ON ab.obra_id = cm.obra_id
    WHERE lo.familia_ficticia = 'OBJETIVO' AND lo.porcentaje_descuento IS NOT NULL
),
candidatas AS (
    -- Todo elemento del descompuesto de su obra y partida en una versión que
    -- la regla ADMITE (D4). Con ABC: la propia ABC y lo ANTERIOR a ella
    -- (Estudios y las versiones previas a la ABC); el `fase_num <= fase_abc`
    -- garantiza además que NUNCA entra una posterior. Sin ABC: solo Estudios.
    -- «Casa» = base × (1 − %) da el precio con 0,011 € + 0,2 % del precio.
    SELECT ob.linea_oferta_id AS linea_oferta_id,
           d.origen AS origen,
           d.fase_num AS fase_num,
           d.orden AS orden,
           d.precio AS precio,
           d.es_primera_abc AS es_primera_abc,
           COALESCE(d.dncpro_id = ob.dncpro_id, FALSE) AS por_dncpro,
           COALESCE(abs(ob.precio - d.precio * (1 - ob.pct / 100)) <= 0.011 + 0.002 * abs(ob.precio), FALSE) AS casa
    FROM objetivo ob
    JOIN descompuestos.lineas d ON d.obra_id = ob.obra_id AND d.partida_id = ob.partida_id
    WHERE (ob.fase_abc IS NOT NULL AND (d.es_primera_abc OR d.origen IN ('MASTER_ESTUDIO', 'ESTUDIO', 'MASTER_PRE_ABC')) AND d.fase_num <= ob.fase_abc)
       OR (ob.fase_abc IS NULL AND d.origen IN ('MASTER_ESTUDIO', 'ESTUDIO'))
),
elemento AS (
    -- Dentro de cada versión, EL elemento (R29): el de igual `dncpro_id` y,
    -- si no lo hay, el que case. Por producto no se puede: la 0696 usa el
    -- mismo producto para un vallado de 69,70 y una malla de 28,97.
    SELECT DISTINCT ON (c.linea_oferta_id, c.origen, c.fase_num)
           c.linea_oferta_id AS linea_oferta_id,
           c.origen AS origen,
           c.fase_num AS fase_num,
           c.precio AS precio,
           c.es_primera_abc AS es_primera_abc,
           c.casa AS casa
    FROM candidatas c
    WHERE c.por_dncpro OR c.casa
    ORDER BY c.linea_oferta_id, c.origen, c.fase_num, c.por_dncpro DESC, c.casa DESC, c.orden
),
elegida AS (
    -- D4: entre las versiones cuyo elemento casa, la de mayor `fase_num`: la
    -- ABC antes que cualquier anterior y, entre las anteriores, la más
    -- reciente. Si ninguna casa, el elemento de la versión de la REGLA (la
    -- ABC, o Estudios), con `casa` falso; nunca el de otra anterior.
    SELECT DISTINCT ON (e.linea_oferta_id)
           e.linea_oferta_id AS linea_oferta_id,
           e.origen AS origen,
           e.fase_num AS fase_num,
           e.precio AS precio,
           e.es_primera_abc AS es_primera_abc,
           e.casa AS casa
    FROM elemento e
    JOIN objetivo ob ON ob.linea_oferta_id = e.linea_oferta_id
    WHERE e.casa OR e.es_primera_abc OR ob.fase_abc IS NULL
    ORDER BY e.linea_oferta_id, e.casa DESC, e.fase_num DESC, e.origen
),
con_descompuesto AS (
    -- Las líneas cuya partida SÍ tiene descompuesto en alguna versión
    -- admitida: sin él, `casa_base` es NULL y no falso (R30).
    SELECT DISTINCT c.linea_oferta_id FROM candidatas c
)
SELECT lo.linea_oferta_id AS linea_oferta_id,
    lo.oferta_id                            AS oferta_id,
    lo.comparativo_id                       AS comparativo_id,
    lo.comparativo_linea_id                 AS comparativo_linea_id,
    lo.producto_id                          AS producto_id,
    lo.descripcion                          AS descripcion,
    lo.unidad_medida                        AS unidad_medida,
    lo.cantidad                             AS cantidad,
    lo.precio                               AS precio,
    lo.importe_ofertado_linea               AS importe_ofertado_linea,
    lo.descuento_texto                      AS descuento_texto,
    lo.porcentaje_descuento                 AS porcentaje_descuento,
    lo.es_ficticia                          AS es_ficticia,
    lo.familia_ficticia                     AS familia_ficticia,
    ob.base_regla                           AS base_regla,
    el.precio                               AS precio_base,
    -- 'ABC v3', 'MASTER_PRE_ABC v2', 'MASTER_ESTUDIO v0', 'ESTUDIO v0'.
    CASE WHEN el.es_primera_abc THEN 'ABC' ELSE el.origen END || ' v' || el.fase_num AS origen_base,
    CASE WHEN el.casa THEN TRUE WHEN cd.linea_oferta_id IS NOT NULL THEN FALSE END AS casa_base
FROM lineas_oferta lo
LEFT JOIN objetivo ob ON ob.linea_oferta_id = lo.linea_oferta_id
LEFT JOIN elegida el ON el.linea_oferta_id = lo.linea_oferta_id
LEFT JOIN con_descompuesto cd ON cd.linea_oferta_id = lo.linea_oferta_id;

ALTER TABLE compras.comparativo_oferta_lineas ADD PRIMARY KEY (linea_oferta_id);
CREATE INDEX idx_com_col_ofe ON compras.comparativo_oferta_lineas (oferta_id);
CREATE INDEX idx_com_col_cln ON compras.comparativo_oferta_lineas (comparativo_linea_id);
