-- etl_sigrid/infrastructure/postgres/sql/postventa/02_incidencias.sql
-- ============================================================================
-- F-156 · `postventa.incidencias` y `postventa.incidencia_intervinientes`.
--
-- INCIDENCIAS (R7-R8): una fila por reclamación de Sigrid (`raw.rcp`) CON su
-- cabecera 708 en `raw.con`: 22.179 el 2026-11-03, todas de la empresa 1. Las
-- 1.502 cabeceras 708 sin fila en `rcp` (borradas) no entran. La unidad va por
-- LEFT JOIN: una incidencia cuya unidad no esté publicada no se pierde.
--
-- Código, fecha de la cabecera, estado (708: 1 SAT, 3 PTE, 5 TER, 7 NPR, 9 CER)
-- y descripción corta salen de `raw.con`; el resto, de `rcp` y sus catálogos
-- (`auxrcp` clase, `auxtrcp` tipo, `auxofc` oficio) y de `raw.conext`
-- (`RCPCLI`, la referencia `PVI-...` de la aplicación de Posventa).
-- `forma_comunicacion_codigo` es `rcptip` tal cual: solo el 1 (ESCRITA) tiene
-- nombre documentado.
--
-- TEXTO ENMASCARADO (D10, R13): descripción, descripción larga y motivo pasan
-- por `postventa.fn_enmascarar`. El íntegro, en `postventa_restringida.textos`.
-- Sin propietario, reclamante ni contacto (R11): `postventa_restringida`.
--
-- R8: `fin_garantia_clase` es el fin de la garantía de SU clase (`fecfin1` para
-- la 0001, `fecfin2` para la 0002; NULL para la 0003 Estructura, que no tiene
-- fin en Sigrid, y para las 15.229 sin clase) y `dentro_garantia` compara el
-- alta con él. Literales de `CLASE_FIN_GARANTIA` del dominio.
--
-- INTERVINIENTES (R9): una fila por `raw.rcpint` cuya incidencia está
-- publicada (fuera los 1.499 huérfanos), con su oficio de obra y su proveedor.
--
-- Lee `raw` y `postventa.unidades` / `postventa.oficios_obra` (de `01`).
-- ============================================================================

-- R12 · La guarda: sin incidencias, o con menos del 99 % con su cabecera 708,
-- la ingesta de `rcp` o de `con` ha quedado a medias. Falla con la cifra.
DO $$
DECLARE
    v_total BIGINT;
    v_con   BIGINT;
BEGIN
    SELECT count(*), count(c.ide)
      INTO v_total, v_con
    FROM      raw.rcp r
    LEFT JOIN raw.con c ON c.ide = r.ide AND c.tip = 708;
    IF v_total = 0 OR v_con < v_total * 0.99 THEN
        RAISE EXCEPTION 'F-156 R12: raw.rcp tiene % filas y solo % con su cabecera 708 en raw.con (minimo el 99 por ciento). La ingesta de rcp o de con ha quedado a medias: reingerirlas antes de reconstruir postventa.', v_total, v_con;
    END IF;
END $$;

DROP TABLE IF EXISTS postventa.incidencias CASCADE;
CREATE TABLE postventa.incidencias AS
WITH referencia AS (
    -- `RCPCLI`: la referencia externa `PVI-...` (5.099 el 2026-11-03). Una por
    -- incidencia como mucho: la primera si Sigrid repitiera el campo.
    SELECT DISTINCT ON (x.conide) x.conide, NULLIF(BTRIM(x.valt), '') AS valor
    FROM   raw.conext x
    WHERE  x.cod = 'RCPCLI'
    ORDER  BY x.conide, x.ide
)
SELECT
    r.ide                                           AS incidencia_id,
    c.emp                                           AS empresa_id,
    un.obra_id                                      AS obra_id,
    un.codigo_obra                                  AS codigo_obra,
    NULLIF(r.upvide, 0)                             AS unidad_id,
    un.codigo_unidad                                AS codigo_unidad,
    NULLIF(BTRIM(c.cod), '')                        AS codigo_incidencia,
    COALESCE(postventa.fn_fecha(r.fec), postventa.fn_fecha(c.fec)) AS fecha_alta,
    COALESCE(postventa.fn_momento(r.fec, r.hor), postventa.fn_fecha(c.fec)::TIMESTAMP)
                                                    AS momento_alta,
    c.est                                           AS estado_id,
    ei.codigo_estado                                AS estado_codigo,
    ei.nombre_estado                                AS estado,
    NULLIF(r.rcpide, 0)                             AS clase_id,
    NULLIF(BTRIM(cl.cod), '')                       AS clase_codigo,
    NULLIF(BTRIM(cl.res), '')                       AS clase,
    NULLIF(r.trcpide, 0)                            AS tipo_id,
    NULLIF(BTRIM(ti.cod), '')                       AS tipo_codigo,
    NULLIF(BTRIM(ti.res), '')                       AS tipo,
    NULLIF(r.ofcide, 0)                             AS oficio_id,
    NULLIF(BTRIM(ofi.cod), '')                      AS oficio_codigo,
    NULLIF(BTRIM(ofi.res), '')                      AS oficio,
    postventa.fn_enmascarar(NULLIF(BTRIM(r.motrcp), '')) AS motivo,
    r.rcptip                                        AS forma_comunicacion_codigo,
    NULLIF(BTRIM(r.texurg), '')                     AS urgencia,
    NULLIF(BTRIM(r.resubi), '')                     AS ubicacion,
    postventa.fn_enmascarar(c.res)                  AS descripcion,
    postventa.fn_enmascarar(r.tex)                  AS descripcion_larga,
    rf.valor                                        AS referencia_externa,
    CASE BTRIM(cl.cod)
        WHEN '0001' THEN postventa.fn_fecha(u.fecfin1)
        WHEN '0002' THEN postventa.fn_fecha(u.fecfin2)
    END                                             AS fin_garantia_clase,
    COALESCE(postventa.fn_fecha(r.fec), postventa.fn_fecha(c.fec))
        <= CASE BTRIM(cl.cod)
               WHEN '0001' THEN postventa.fn_fecha(u.fecfin1)
               WHEN '0002' THEN postventa.fn_fecha(u.fecfin2)
           END                                      AS dentro_garantia
FROM      raw.rcp r JOIN raw.con c ON c.ide = r.ide AND c.tip = 708
LEFT JOIN postventa.unidades un ON un.unidad_id = r.upvide
LEFT JOIN raw.upv u ON u.ide = r.upvide
LEFT JOIN raw.auxrcp cl ON cl.ide = r.rcpide
LEFT JOIN raw.auxtrcp ti ON ti.ide = r.trcpide
LEFT JOIN raw.auxofc ofi ON ofi.ide = r.ofcide
LEFT JOIN referencia rf ON rf.conide = r.ide
LEFT JOIN LATERAL postventa.fn_estado(708, c.est) ei ON TRUE;

ALTER TABLE postventa.incidencias ADD PRIMARY KEY (incidencia_id);
CREATE INDEX ix_pv_incidencias_unidad ON postventa.incidencias (unidad_id);
CREATE INDEX ix_pv_incidencias_obra   ON postventa.incidencias (obra_id);
CREATE INDEX ix_pv_incidencias_codigo ON postventa.incidencias (codigo_incidencia);

COMMENT ON TABLE postventa.incidencias IS
'Incidencias de postventa (F-156): una fila por reclamacion de Sigrid (rcp, con tipo 708, el parte de reclamacion de Posventa) con su unidad, obra, estado, clase, tipo, oficio, motivo, urgencia y ubicacion, y el fin de la garantia de su clase. Texto libre con telefonos y correos enmascarados; el integro y las personas, en postventa_restringida. Desde cuando esta en su estado: postventa.v_estado_incidencias.';

DROP TABLE IF EXISTS postventa.incidencia_intervinientes CASCADE;
CREATE TABLE postventa.incidencia_intervinientes AS
SELECT
    ri.ide                                          AS interviniente_id,
    ri.rcpide                                       AS incidencia_id,
    ri.pos                                          AS posicion,
    NULLIF(ri.obrofcide, 0)                         AS oficio_obra_id,
    oo.oficio_id                                    AS oficio_id,
    oo.oficio_codigo                                AS oficio_codigo,
    oo.oficio                                       AS oficio,
    oo.proveedor_id                                 AS proveedor_id,
    oo.proveedor                                    AS proveedor,
    COALESCE(ri.cauave <> 0, FALSE)                 AS causante
FROM      raw.rcpint ri
JOIN      postventa.incidencias i ON i.incidencia_id = ri.rcpide
LEFT JOIN postventa.oficios_obra oo ON oo.oficio_obra_id = ri.obrofcide;

ALTER TABLE postventa.incidencia_intervinientes ADD PRIMARY KEY (interviniente_id);
CREATE INDEX ix_pv_intervinientes_incidencia ON postventa.incidencia_intervinientes (incidencia_id);

COMMENT ON TABLE postventa.incidencia_intervinientes IS
'Intervinientes de cada incidencia (F-156, raw.rcpint): el oficio de la obra que interviene, su proveedor y si es causante. Sin los 1.499 huerfanos de incidencias borradas.';
