-- etl_sigrid/infrastructure/postgres/sql/postventa/03_tareas.sql
-- ============================================================================
-- F-156 · `postventa.tareas` (R10): una fila por tarea de una incidencia.
--
-- La tarea es `raw.tar` (propiedades de `con` tipo 47, serie `REP2...`),
-- filtrada en la ingesta a las que tienen incidencia (`rcpide > 0`): 13.767 el
-- 2026-11-03. Aquí además tiene que estar su incidencia publicada (JOIN).
-- Estado por la pareja (47, `con.est`): en uso 20 IELA, 21 IENV y 23 IREC.
--
-- El oficio y el proveedor salen del recurso de la tarea (`raw.tarres`, solo
-- `obrofcide` tiene dato), uno por tarea: el primero por posición con oficio
-- si hubiera más. El empleado asignado va como `empleado_id` SIN nombre (el nombre está
-- en `personal`, que el perfil restringido no lee). Coste y venta de `tar`
-- están a 0 en el 100 %: no se publican (el coste, en `v_coste_obra`).
--
-- Texto enmascarado (D10); el íntegro, en `postventa_restringida.textos`.
-- Lee `raw`, `postventa.incidencias` y `postventa.oficios_obra`.
-- ============================================================================

DROP TABLE IF EXISTS postventa.tareas CASCADE;
CREATE TABLE postventa.tareas AS
WITH recurso AS (
    -- El primero, por posición, que tenga oficio de obra.
    SELECT DISTINCT ON (tr.taride) tr.taride, tr.obrofcide AS oficio_obra_id
    FROM   raw.tarres tr
    WHERE  COALESCE(tr.obrofcide, 0) <> 0
    ORDER  BY tr.taride, tr.pos, tr.ide
)
SELECT
    t.ide                                           AS tarea_id,
    t.rcpide                                        AS incidencia_id,
    ct.emp                                          AS empresa_id,
    i.obra_id                                       AS obra_id,
    i.codigo_obra                                   AS codigo_obra,
    NULLIF(BTRIM(ct.cod), '')                       AS codigo_tarea,
    postventa.fn_fecha(ct.fec)                      AS fecha_alta,
    ct.est                                          AS estado_id,
    et.codigo_estado                                AS estado_codigo,
    et.nombre_estado                                AS estado,
    NULLIF(t.empide, 0)                             AS empleado_id,
    rc.oficio_obra_id                               AS oficio_obra_id,
    oo.oficio_id                                    AS oficio_id,
    oo.oficio_codigo                                AS oficio_codigo,
    oo.oficio                                       AS oficio,
    oo.proveedor_id                                 AS proveedor_id,
    oo.proveedor                                    AS proveedor,
    postventa.fn_fecha(t.fecestini)                 AS fecha_inicio_estimada,
    postventa.fn_fecha(t.fecestfin)                 AS fecha_fin_estimada,
    postventa.fn_fecha(t.feclim)                    AS fecha_limite,
    postventa.fn_fecha(t.fecreaini)                 AS fecha_inicio_real,
    postventa.fn_fecha(t.fecreafin)                 AS fecha_fin_real,
    t.priori                                        AS prioridad,
    t.porcen                                        AS porcentaje,
    postventa.fn_enmascarar(ct.res)                 AS descripcion,
    postventa.fn_enmascarar(t.tex)                  AS texto
FROM      raw.tar t
JOIN      raw.con ct ON ct.ide = t.ide AND ct.tip = 47
JOIN      postventa.incidencias i ON i.incidencia_id = t.rcpide
LEFT JOIN recurso rc ON rc.taride = t.ide
LEFT JOIN postventa.oficios_obra oo ON oo.oficio_obra_id = rc.oficio_obra_id
LEFT JOIN LATERAL postventa.fn_estado(47, ct.est) et ON TRUE;

ALTER TABLE postventa.tareas ADD PRIMARY KEY (tarea_id);
CREATE INDEX ix_pv_tareas_incidencia ON postventa.tareas (incidencia_id);

COMMENT ON TABLE postventa.tareas IS
'Tareas de las incidencias de postventa (F-156, tar con tipo 47, serie REP2): su incidencia, estado, empleado asignado (solo el id), oficio y proveedor del recurso, fechas, prioridad, porcentaje y texto enmascarado. Coste y venta de Sigrid a 0: no se publican.';
