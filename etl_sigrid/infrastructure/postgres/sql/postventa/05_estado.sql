-- etl_sigrid/infrastructure/postgres/sql/postventa/05_estado.sql
-- ============================================================================
-- F-156 · `postventa.v_estado_incidencias` (R15-R16): el ESTADO ACTUAL de cada
-- incidencia, desde cuándo está en él, quién la dejó así y cuánto tardó en
-- resolverse.
--
-- `origen_fecha`, en este orden (`etl_sigrid/domain/postventa.py::origen_fecha`):
--
--   PASO               el último paso de `rac` la dejó en su estado: la fecha y
--                      el login son los de ese paso (~19.505 el 2026-11-03).
--   CIERRE_APLICACION  cerrada (9) y la aplicación `postventa-incidencias` la
--                      cerró DESPUÉS del último paso (o sin pasos): la fecha y
--                      el login, los de su línea de `raw.log` (~658).
--   ALTA               sin pasos y en el estado inicial (1 SAT): la fecha de
--                      alta, sin autor de cambio (~2.015).
--   SIN_HISTORIAL      lo demás: un cambio fuera de proceso (borrado con
--                      «Deshacer»): sin fecha ni autor (~1).
--
-- R16: `abierta` (1 SAT o 3 PTE), `fecha_resolucion` (el primer momento en que
-- un paso, de cualquier origen, la llevó a 5, 7 o 9), `dias_hasta_resolucion`,
-- `dias_abierta` (hasta hoy si sigue abierta; si no, hasta la resolución) y
-- `dias_en_estado`. Es VISTA: los días se calculan al consultar, con la fecha
-- de Madrid, como `compras.v_estado_documentos`.
--
-- Lee `postventa.incidencias` y `postventa.incidencia_procesos`.
-- ============================================================================

DROP VIEW IF EXISTS postventa.v_estado_incidencias;
CREATE VIEW postventa.v_estado_incidencias AS
WITH ultimo_paso AS (
    SELECT DISTINCT ON (p.documento_id)
           p.documento_id, p.estado_destino_id, p.momento, p.usuario
    FROM   postventa.incidencia_procesos p
    WHERE  p.origen = 'RAC' AND p.tipo_documento_codigo = 708
    ORDER  BY p.documento_id, p.momento DESC NULLS LAST, p.ide_origen DESC
),
ultimo_cierre AS (
    SELECT DISTINCT ON (p.documento_id)
           p.documento_id, p.momento, p.usuario
    FROM   postventa.incidencia_procesos p
    WHERE  p.origen = 'CIERRE_APLICACION' AND p.tipo_documento_codigo = 708
    ORDER  BY p.documento_id, p.momento DESC NULLS LAST, p.ide_origen DESC
),
resolucion AS (
    SELECT p.documento_id, MIN(p.momento) AS momento
    FROM   postventa.incidencia_procesos p
    WHERE  p.tipo_documento_codigo = 708 AND p.estado_destino_id IN (5, 7, 9)
    GROUP  BY p.documento_id
),
base AS (
    SELECT
        i.incidencia_id, i.empresa_id, i.obra_id, i.codigo_obra, i.unidad_id,
        i.codigo_incidencia, i.estado_id, i.estado_codigo, i.estado, i.fecha_alta,
        i.momento_alta,
        CASE WHEN u.documento_id IS NOT NULL AND u.estado_destino_id = i.estado_id
             THEN 'PASO'
             WHEN i.estado_id = 9 AND k.momento IS NOT NULL
                  AND (u.documento_id IS NULL OR u.momento IS NULL OR k.momento > u.momento)
             THEN 'CIERRE_APLICACION'
             WHEN u.documento_id IS NULL AND i.estado_id = 1
             THEN 'ALTA'
             ELSE 'SIN_HISTORIAL' END AS origen_fecha,
        i.estado_id IN (1, 3) AS abierta,
        u.momento  AS momento_paso,
        u.usuario  AS usuario_paso,
        k.momento  AS momento_cierre,
        k.usuario  AS usuario_cierre,
        r.momento  AS fecha_resolucion
    FROM      postventa.incidencias i
    LEFT JOIN ultimo_paso   u ON u.documento_id = i.incidencia_id
    LEFT JOIN ultimo_cierre k ON k.documento_id = i.incidencia_id
    LEFT JOIN resolucion    r ON r.documento_id = i.incidencia_id
),
fechados AS (
    SELECT
        b.*,
        CASE b.origen_fecha WHEN 'PASO' THEN b.momento_paso
                            WHEN 'CIERRE_APLICACION' THEN b.momento_cierre
                            WHEN 'ALTA' THEN b.momento_alta END AS en_estado_desde,
        CASE b.origen_fecha WHEN 'PASO' THEN b.usuario_paso
                            WHEN 'CIERRE_APLICACION' THEN b.usuario_cierre END AS cambiado_por,
        (now() AT TIME ZONE 'Europe/Madrid')::DATE AS hoy
    FROM base b
)
SELECT
    f.incidencia_id                                 AS incidencia_id,
    f.codigo_incidencia                             AS codigo_incidencia,
    f.empresa_id                                    AS empresa_id,
    f.obra_id                                       AS obra_id,
    f.codigo_obra                                   AS codigo_obra,
    f.unidad_id                                     AS unidad_id,
    f.estado_id                                     AS estado_id,
    f.estado_codigo                                 AS estado_codigo,
    f.estado                                        AS estado,
    f.fecha_alta                                    AS fecha_alta,
    f.en_estado_desde                               AS en_estado_desde,
    f.cambiado_por                                  AS cambiado_por,
    f.origen_fecha::TEXT                            AS origen_fecha,
    f.abierta                                       AS abierta,
    f.fecha_resolucion                              AS fecha_resolucion,
    (f.fecha_resolucion::DATE - f.fecha_alta)       AS dias_hasta_resolucion,
    CASE WHEN f.abierta THEN f.hoy - f.fecha_alta
         ELSE f.fecha_resolucion::DATE - f.fecha_alta END AS dias_abierta,
    (f.hoy - f.en_estado_desde::DATE)               AS dias_en_estado
FROM fechados f;

COMMENT ON VIEW postventa.v_estado_incidencias IS
'Estado actual de cada incidencia de postventa (F-156) y desde cuando esta en el. origen_fecha: PASO (el ultimo paso de rac la dejo asi: fecha y login de ese paso), CIERRE_APLICACION (la cerro la aplicacion postventa-incidencias despues del ultimo paso: fecha y login de su linea de log), ALTA (sin pasos y sin atender: la fecha de alta) o SIN_HISTORIAL (sin fecha). abierta = sin atender o pendiente; fecha_resolucion = primer paso a terminada, no procede o cerrada. Los dias se calculan al consultar (fecha de Madrid).';
