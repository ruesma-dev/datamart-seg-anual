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
