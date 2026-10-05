-- etl_sigrid/infrastructure/postgres/sql/compras/08_comparativos.sql
-- ============================================================================
-- F-038 (2026-10-04) · EL COMPARATIVO DE OFERTAS, Fase 1.
--
-- Construye:
--   · compras.comparativo_ofertas — una fila por oferta INVITADA (raw.comprv,
--     cuyo docide es único), incluidas las FICTICIAS marcadas como tales.
--   · compras.comparativos        — una fila por comparativo (raw.com), con
--     las cuatro magnitudes de importe, el ahorro del concurso, el contrato,
--     el estado, la actividad y la fecha de aprobación.
--
-- Lee de: raw.com, raw.comlin, raw.comprv, raw.dco, raw.dcopro, raw.con,
--         raw.confir, raw.auxpronat, raw.conest (vía fn_estado_documento),
--         compras.contrato_lineas (01_documentos.sql, este mismo paso) y
--         maestro.v_obra_fichas (build_maestros, como 03_views.sql).
--
-- LO QUE COSTÓ DESCUBRIR, y por eso está escrito aquí (progress/spec_F-038.md):
--   · EL PROVEEDOR DE LA OFERTA ES `dco.entide`, informado al 99,86 %. El
--     campo del invitado en `comprv` solo está al 18 %: unir por él pierde el
--     82 % de las ofertas. Este fichero no lo nombra (lo vigila un test).
--   · LOS IMPORTES SON SIN IVA: el documento de oferta es `dco.totbas`. El
--     total del documento lleva IVA (R-COMPRAS-SIN-IVA) y el «no cuadran» de
--     la medición de septiembre era, sobre todo, ese IVA.
--   · LAS CUATRO MAGNITUDES, cada una con su nombre y ninguna `importe` a
--     secas («quiero todos, no uno», humano 2026-09-18): ofertado por
--     documento (A), ofertado por líneas (B), adjudicado (C) y contratado (D).
--     Cuadre medido de la ganadora: A=B 99,6 %, A=C 89,8 %, A=D 41 %.
--   · EL CONTRATO SALE DE `comlin.ctride` (18.633 comparativos), no de la
--     cabecera del contrato (56 %): un contrato sale de varios comparativos
--     (3.960 contratos), así que el enlace bueno es N:1 desde el comparativo.
--     Ningún comparativo tiene dos contratos (0): la guarda de abajo lo exige.
--   · LA FECHA DE APROBACIÓN solo existe en los estados de firma: es la de la
--     última firma cuando `con.est` es el estado final (`estfin`) de su
--     circuito; en EN ELABORACIÓN o PROPUESTO no existe y se publica NULL.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- GUARDA R21 · un comparativo, un contrato. LO PRIMERO DEL FICHERO: si salta,
-- no se ha tirado ninguna tabla y la de anoche sigue publicada. Sin ella, el
-- `MAX(NULLIF(ctride, 0))` de `compras.comparativos` elegiría uno de los dos
-- contratos en silencio. Hoy 0 casos (medido el 2026-10-04).
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    v_casos BIGINT;
BEGIN
    SELECT count(*) INTO v_casos
    FROM (
        SELECT l.comide
        FROM raw.comlin l
        WHERE l.ctride > 0
        GROUP BY l.comide
        HAVING count(DISTINCT l.ctride) > 1
    ) dobles;
    IF v_casos > 0 THEN
        RAISE EXCEPTION 'F-038 R21: % comparativo(s) de raw.comlin tienen lineas adjudicadas a mas de un contrato (ctride). compras.comparativos publica UN contrato por comparativo y no elige uno en silencio: hay que revisar el modelo (specs/F-038-comparativos) antes de reconstruir.', v_casos;
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- OFERTAS · una fila por oferta invitada, TODAS, con la ficticia marcada.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS compras.comparativo_ofertas CASCADE;
CREATE TABLE compras.comparativo_ofertas AS
SELECT d.ide AS oferta_id,
    p.ide                                   AS invitacion_id,
    p.comide                                AS comparativo_id,
    p.pos                                   AS posicion,
    c.cod                                   AS codigo_oferta,
    compras.fn_sigrid_date(c.fec)           AS fecha_oferta,
    NULLIF(d.entide, 0)                     AS proveedor_id,
    NULLIF(TRIM(d.entcod), '')              AS proveedor_codigo,
    NULLIF(TRIM(d.entres), '')              AS proveedor_nombre,
    NULLIF(TRIM(d.entcif), '')              AS proveedor_cif,
    -- La regla de la ficticia vive en `etl_sigrid/domain/comparativos.py` y
    -- la ejecuta `compras.fn_familia_ficticia` (00_setup.sql) con sus mismos
    -- literales. Se llama UNA vez por oferta, en el lateral de abajo.
    ff.familia IS NOT NULL                  AS es_ficticia,
    ff.familia                              AS familia_ficticia,
    c.est                                   AS estado_id,        -- tipo 12: la oferta
    est.codigo_estado                       AS estado_codigo,
    est.nombre_estado                       AS estado,
    -- 6 = «Aceptada definitivamente» en el tipo 12: la GANADORA.
    COALESCE(c.est = 6, FALSE)              AS es_ganadora,
    d.totbas::NUMERIC(18, 2)                AS importe_ofertado_documento,   -- A, sin IVA
    li.importe_lineas                       AS importe_ofertado_lineas,      -- B, NULL sin líneas
    COALESCE(li.n_lineas, 0)                AS n_lineas
FROM raw.comprv p
JOIN raw.dco d ON d.ide = p.docide
JOIN raw.con c ON c.ide = d.ide
-- B: solo las líneas de oferta que responden a una línea del comparativo.
-- `tot = can × pre` en las 786.710 líneas: el precio ya es neto.
LEFT JOIN (
    SELECT lp.docide,
           SUM(lp.tot)::NUMERIC(18, 2) AS importe_lineas,
           count(*) AS n_lineas
    FROM raw.dcopro lp
    WHERE lp.comlinide > 0
    GROUP BY lp.docide
) li ON li.docide = d.ide
CROSS JOIN LATERAL (
    SELECT compras.fn_familia_ficticia(d.entcif, d.entres) AS familia
) ff
-- La traducción por la PAREJA (12, est), con su guarda de grano dentro.
LEFT JOIN LATERAL compras.fn_estado_documento(12, c.est) est ON TRUE;

ALTER TABLE compras.comparativo_ofertas ADD PRIMARY KEY (oferta_id);
CREATE INDEX idx_com_cof_cmp ON compras.comparativo_ofertas (comparativo_id);
CREATE INDEX idx_com_cof_prv ON compras.comparativo_ofertas (proveedor_id);
CREATE INDEX idx_com_cof_fam ON compras.comparativo_ofertas (familia_ficticia);

-- ---------------------------------------------------------------------------
-- COMPARATIVOS · una fila por comparativo de raw.com, con cuatro agregados.
--
-- GRANO: los agregados van por comparativo y entran con LEFT JOIN, así que ni
-- multiplican ni pierden filas: un comparativo sin ofertas (319), sin líneas
-- (264) o sin firmas se publica igual, con recuentos a 0 e importes a NULL.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS compras.comparativos CASCADE;
CREATE TABLE compras.comparativos AS
WITH ofertas AS (
    -- 1 · OFERTAS. Las ficticias cuentan en `n_ofertas` y en la mayor oferta
    -- (para juzgar el atípico) pero NUNCA en las reales, la mínima, la
    -- máxima ni el ahorro: el `FILTER` de cada una lo dice.
    SELECT o.comparativo_id,
           count(*) AS n_ofertas,
           count(*) FILTER (WHERE NOT o.es_ficticia) AS n_ofertas_reales,
           count(*) FILTER (WHERE NOT o.es_ficticia AND o.importe_ofertado_documento > 0) AS n_ofertas_reales_con_importe,
           count(*) FILTER (WHERE o.es_ganadora) AS n_ofertas_ganadoras,
           MIN(o.importe_ofertado_documento) FILTER (WHERE NOT o.es_ficticia AND o.importe_ofertado_documento > 0) AS minima_real,
           MAX(o.importe_ofertado_documento) FILTER (WHERE NOT o.es_ficticia AND o.importe_ofertado_documento > 0) AS maxima_real,
           MAX(o.importe_ofertado_documento) AS mayor_oferta
    FROM compras.comparativo_ofertas o
    GROUP BY o.comparativo_id
),
ganadora AS (
    -- La ganadora SOLO si es única (R15): con dos, no se elige una y la
    -- ganadora y sus importes quedan a NULL (`n_ofertas_ganadoras` lo dice).
    SELECT o.comparativo_id, o.oferta_id, o.proveedor_id, o.proveedor_nombre,
           o.importe_ofertado_documento, o.importe_ofertado_lineas
    FROM compras.comparativo_ofertas o
    JOIN ofertas a ON a.comparativo_id = o.comparativo_id AND a.n_ofertas_ganadoras = 1
    WHERE o.es_ganadora
),
lineas AS (
    -- 2 · LÍNEAS DEL CONCURSO: el adjudicado (C) y el contrato. La guarda R21
    -- de arriba ya garantizó un solo `ctride` > 0 por comparativo.
    SELECT l.comide AS comparativo_id,
           SUM(COALESCE(l.can, 0) * COALESCE(l.pre, 0))::NUMERIC(18, 2) AS importe_adjudicado_lineas,
           MAX(NULLIF(l.ctride, 0)) AS contrato_id
    FROM raw.comlin l
    GROUP BY l.comide
),
contratado AS (
    -- 3 · CONTRATADO (D), del CONTRATO: se repite en los comparativos que lo
    -- comparten (3.960 contratos vienen de varios).
    SELECT cl.contrato_id,
           SUM(cl.importe)::NUMERIC(18, 2) AS importe_contratado
    FROM compras.contrato_lineas cl
    GROUP BY cl.contrato_id
),
firmas AS (
    -- 4 · FIRMAS. `fir = 0` es la firma PENDIENTE (y viene sin fecha).
    -- `estado_es_final`: el estado actual del comparativo es el estado final
    -- (`estfin`) de su circuito, o sea, el circuito se cerró.
    SELECT f.conide AS comparativo_id,
           count(*) AS n_firmas,
           count(*) FILTER (WHERE f.fir = 0) AS n_firmas_pendientes,
           bool_or(f.estfin = fc.est) AS estado_es_final
    FROM raw.confir f
    JOIN raw.com fm ON fm.ide = f.conide
    JOIN raw.con fc ON fc.ide = f.conide
    GROUP BY f.conide
),
ultima_firma AS (
    -- La última FIRMADA por fecha y hora; `ide` desempata.
    SELECT DISTINCT ON (f.conide)
           f.conide AS comparativo_id,
           compras.fn_sigrid_date(f.fec) AS fecha,
           f.usu AS usuario
    FROM raw.confir f
    WHERE f.fir <> 0
    ORDER BY f.conide, f.fec DESC NULLS LAST, f.hor DESC NULLS LAST, f.ide DESC
)
SELECT m.ide AS comparativo_id,
    c.cod                                   AS codigo_comparativo,
    c.res                                   AS nombre_comparativo,
    compras.fn_sigrid_date(c.fec)           AS fecha_alta,        -- alta en Sigrid, 100 %
    NULLIF(m.obride, 0)                     AS obra_id,
    ob.cod                                  AS codigo_obra,
    ob.res                                  AS nombre_obra,
    fo.empresa_id                           AS empresa_id,
    fo.clave_obra                           AS clave_obra,
    NULLIF(m.natide, 0)                     AS actividad_id,
    a.res                                   AS actividad,
    c.est                                   AS estado_id,         -- tipo 46: el comparativo
    est.codigo_estado                       AS estado_codigo,
    est.nombre_estado                       AS estado,
    li.contrato_id                          AS contrato_id,
    cc.cod                                  AS codigo_contrato,
    compras.fn_sigrid_date(cc.fec)          AS fecha_contrato,
    COALESCE(oft.n_ofertas, 0)               AS n_ofertas,
    COALESCE(oft.n_ofertas_reales, 0)        AS n_ofertas_reales,
    COALESCE(oft.n_ofertas_reales_con_importe, 0) AS n_ofertas_reales_con_importe,
    COALESCE(oft.n_ofertas_ganadoras, 0)     AS n_ofertas_ganadoras,
    g.oferta_id                             AS oferta_ganadora_id,
    g.proveedor_id                          AS proveedor_ganador_id,
    g.proveedor_nombre                      AS proveedor_ganador_nombre,
    g.importe_ofertado_documento            AS importe_ofertado_documento_ganadora,  -- A
    g.importe_ofertado_lineas               AS importe_ofertado_lineas_ganadora,     -- B
    li.importe_adjudicado_lineas            AS importe_adjudicado_lineas,            -- C
    -- Literales = FACTOR_ATIPICO y MINIMO_ATIPICO del dominio (R16). Sin
    -- `ELSE`: NULL cuando no hay oferta con importe con que comparar.
    CASE WHEN oft.mayor_oferta > 0 THEN li.importe_adjudicado_lineas > 10 * oft.mayor_oferta AND li.importe_adjudicado_lineas > 100000 END AS adjudicado_atipico,
    ct.importe_contratado                   AS importe_contratado,                   -- D
    -- El ahorro del concurso, solo con dos o más ofertas REALES con importe.
    CASE WHEN oft.n_ofertas_reales_con_importe >= 2 THEN oft.minima_real END AS oferta_real_minima,
    CASE WHEN oft.n_ofertas_reales_con_importe >= 2 THEN oft.maxima_real END AS oferta_real_maxima,
    CASE WHEN oft.n_ofertas_reales_con_importe >= 2 THEN oft.maxima_real - oft.minima_real END AS ahorro_concurso,
    COALESCE(fi.n_firmas, 0)                AS n_firmas,
    COALESCE(fi.n_firmas_pendientes, 0)     AS n_firmas_pendientes,
    -- Solo cuando el circuito se cerró: fuera de los estados de firma la
    -- fecha de aprobación NO existe, y quien firmó el último paso de un
    -- comparativo rechazado no lo «aprobó».
    CASE WHEN fi.estado_es_final THEN uf.fecha END AS fecha_aprobacion,
    CASE WHEN fi.estado_es_final THEN uf.usuario END AS aprobado_por
FROM raw.com m
JOIN raw.con c ON c.ide = m.ide
LEFT JOIN raw.con ob ON ob.ide = NULLIF(m.obride, 0)
LEFT JOIN maestro.v_obra_fichas fo ON fo.obra_id = NULLIF(m.obride, 0)
LEFT JOIN raw.auxpronat a ON a.ide = NULLIF(m.natide, 0)
LEFT JOIN LATERAL compras.fn_estado_documento(46, c.est) est ON TRUE
LEFT JOIN ofertas oft ON oft.comparativo_id = m.ide
LEFT JOIN ganadora g ON g.comparativo_id = m.ide
LEFT JOIN lineas li ON li.comparativo_id = m.ide
LEFT JOIN raw.con cc ON cc.ide = li.contrato_id
LEFT JOIN contratado ct ON ct.contrato_id = li.contrato_id
LEFT JOIN firmas fi ON fi.comparativo_id = m.ide
LEFT JOIN ultima_firma uf ON uf.comparativo_id = m.ide;

ALTER TABLE compras.comparativos ADD PRIMARY KEY (comparativo_id);
CREATE INDEX idx_com_cmp_obra ON compras.comparativos (obra_id);
CREATE INDEX idx_com_cmp_ctr  ON compras.comparativos (contrato_id);
CREATE INDEX idx_com_cmp_act  ON compras.comparativos (actividad_id);
CREATE INDEX idx_com_cmp_est  ON compras.comparativos (estado_id);
