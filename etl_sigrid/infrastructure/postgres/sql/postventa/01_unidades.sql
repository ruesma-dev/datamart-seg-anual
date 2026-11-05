-- etl_sigrid/infrastructure/postgres/sql/postventa/01_unidades.sql
-- ============================================================================
-- F-156 · `postventa.unidades` y `postventa.oficios_obra`.
--
-- UNIDADES (R6): una fila por unidad postventa de Sigrid (`raw.upv`,
-- propiedades de `con` tipo 707), 1.328 el 2026-11-03 en 18 obras. Código,
-- nombre, empresa y estado salen de su cabecera en `raw.con`; la obra, de
-- `upv.obride`; la tipología, de `raw.prmtpl`. Estado por la pareja (707,
-- `con.est`): 1 PRE «En preventa», 5 GAR «En garantía», 10 TG.
--
-- SIN DATOS DE CONTACTO (R11): ni el propietario (`cliide`), ni la persona de
-- contacto (`peride`), ni el teléfono y el correo de la unidad (`restel`,
-- `resele`). Solo `tiene_propietario`. Todo eso, en
-- `postventa_restringida.contactos_unidad` (`07_restringida.sql`).
--
-- OFICIOS DE OBRA (R9): una fila por oficio de una obra con su proveedor
-- (`raw.obrofc`, 1.084 el 2026-11-03). Es a donde apuntan los intervinientes
-- de una incidencia y el recurso de una tarea.
--
-- Lee solo `raw`. Se reconstruye cada noche (DROP + CREATE).
-- ============================================================================

DROP TABLE IF EXISTS postventa.unidades CASCADE;
CREATE TABLE postventa.unidades AS
SELECT
    u.ide                                           AS unidad_id,
    cu.emp                                          AS empresa_id,
    NULLIF(u.obride, 0)                             AS obra_id,
    NULLIF(BTRIM(co.cod), '')                       AS codigo_obra,
    NULLIF(BTRIM(cu.cod), '')                       AS codigo_unidad,
    NULLIF(BTRIM(cu.res), '')                       AS nombre_unidad,
    cu.est                                          AS estado_id,
    eu.codigo_estado                                AS estado_codigo,
    eu.nombre_estado                                AS estado,
    NULLIF(u.obrtplide, 0)                          AS tipologia_id,
    NULLIF(BTRIM(tp.cod), '')                       AS codigo_tipologia,
    NULLIF(BTRIM(tp.res), '')                       AS tipologia,
    postventa.fn_fecha(u.fecini)                    AS inicio_garantia,
    postventa.fn_fecha(u.fecfin)                    AS fin_garantia,
    postventa.fn_fecha(u.fecfin1)                   AS fin_garantia_vicios,
    postventa.fn_fecha(u.fecini2)                   AS inicio_garantia_habitabilidad,
    postventa.fn_fecha(u.fecfin2)                   AS fin_garantia_habitabilidad,
    postventa.fn_fecha(u.fecini3)                   AS inicio_garantia_estructura,
    postventa.fn_fecha(u.fecesc)                    AS fecha_escrituracion,
    postventa.fn_fecha(u.fecfpl)                    AS fecha_fin_primer_listado,
    postventa.fn_fecha(u.fecvtecpre)                AS fecha_visita_tecnica_prevista,
    postventa.fn_fecha(u.fecvtec)                   AS fecha_visita_tecnica,
    NULLIF(BTRIM(u.espacios), '')                   AS espacios,
    COALESCE(u.cliide, 0) <> 0                      AS tiene_propietario
FROM      raw.upv u JOIN raw.con cu ON cu.ide = u.ide
LEFT JOIN raw.con co ON co.ide = u.obride
LEFT JOIN raw.prmtpl tp ON tp.ide = u.obrtplide
LEFT JOIN LATERAL postventa.fn_estado(707, cu.est) eu ON TRUE;

ALTER TABLE postventa.unidades ADD PRIMARY KEY (unidad_id);
CREATE INDEX ix_pv_unidades_obra ON postventa.unidades (obra_id);

COMMENT ON TABLE postventa.unidades IS
'Unidades postventa de Sigrid (F-156): una fila por unidad (con tipo 707), con su obra, estado, tipologia y fechas de garantia por tramo (vicios o defectos, habitabilidad; estructura solo tiene inicio), escrituracion y visita tecnica. Sin datos de contacto: estan en postventa_restringida.contactos_unidad.';

DROP TABLE IF EXISTS postventa.oficios_obra CASCADE;
CREATE TABLE postventa.oficios_obra AS
SELECT
    o.ide                                           AS oficio_obra_id,
    NULLIF(o.obride, 0)                             AS obra_id,
    NULLIF(BTRIM(co.cod), '')                       AS codigo_obra,
    co.emp                                          AS empresa_id,
    NULLIF(o.ofcide, 0)                             AS oficio_id,
    NULLIF(BTRIM(ao.cod), '')                       AS oficio_codigo,
    NULLIF(BTRIM(ao.res), '')                       AS oficio,
    NULLIF(o.prvide, 0)                             AS proveedor_id,
    NULLIF(BTRIM(cp.res), '')                       AS proveedor,
    postventa.fn_enmascarar(NULLIF(BTRIM(o.coment), '')) AS comentario
FROM      raw.obrofc o
LEFT JOIN raw.con co ON co.ide = o.obride
LEFT JOIN raw.auxofc ao ON ao.ide = o.ofcide
LEFT JOIN raw.con cp ON cp.ide = NULLIF(o.prvide, 0);

ALTER TABLE postventa.oficios_obra ADD PRIMARY KEY (oficio_obra_id);
CREATE INDEX ix_pv_oficios_obra_obra ON postventa.oficios_obra (obra_id);

COMMENT ON TABLE postventa.oficios_obra IS
'Oficios de cada obra con su proveedor (F-156, raw.obrofc): a donde apuntan los intervinientes de una incidencia y el recurso de una tarea. El comentario va con telefonos y correos enmascarados.';
