-- etl_sigrid/infrastructure/postgres/sql/postventa/04_procesos.sql
-- ============================================================================
-- F-156 · `postventa.incidencia_procesos` (R14): EL HISTÓRICO de unidades,
-- incidencias y tareas: quién cambió el estado, desde cuál, a cuál y cuándo.
--
-- DOS ORÍGENES, en una sola tabla (UNION ALL):
--
--   RAC                 una fila por paso de `raw.rac` (la ventana «Procesos»
--                       de Sigrid) de un documento de tipo 707, 708 o 47: el
--                       proceso, el estado de origen (`est1`) y de destino
--                       (`est2`), el login (`usu`), la fecha y la hora. El
--                       100 % de los pasos trae login (2026-11-03).
--   CIERRE_APLICACION   una fila por línea de `raw.log` con la que la
--                       aplicación `postventa-incidencias` cierra una
--                       incidencia: escribe `con.est` = 9 y esa línea, NO un
--                       paso de `rac` (D8). Sin estado de origen; destino 9.
--                       Se enlaza con el documento por (`tip`, `cod`, `emp`):
--                       `cod` es único en 708.
--
-- Clave `paso_id` = `RAC-<rac.ide>` o `LOG-<log.ide>`. Los estados se
-- traducen por la PAREJA tipo-estado (`postventa.fn_estado`). `usuario` es el
-- LOGIN y `usuario_nombre` el nombre de `raw.usu` (casado en
-- `UPPER(BTRIM(...))`, como `compras.documento_procesos`): NULL si el login ya
-- no está en `usu` (el 3,2 % de los pasos de 708 el 2026-11-03). `es_ultimo`
-- marca el paso más reciente de cada documento, de los dos orígenes.
--
-- ES LA HISTORIA NETA: «Deshacer proceso» borra el paso de `rac`.
-- Lee `raw.rac`, `raw.log`, `raw.con`, `raw.usu` y `raw.conest`.
-- ============================================================================

DROP TABLE IF EXISTS postventa.incidencia_procesos CASCADE;
CREATE TABLE postventa.incidencia_procesos AS
WITH usuarios AS (
    -- Un nombre por login NORMALIZADO: agrupado, el JOIN no multiplica.
    SELECT UPPER(BTRIM(u.cod)) AS login_norm,
           MIN(u.res)          AS nombre
    FROM   raw.usu u
    WHERE  BTRIM(u.cod) <> ''
    GROUP  BY UPPER(BTRIM(u.cod))
),
pasos AS (
    SELECT
        'RAC-' || r.ide                             AS paso_id,
        'RAC' AS origen,
        r.ide::BIGINT                               AS ide_origen,
        r.conide                                    AS documento_id,
        c.tip                                       AS tipo_documento_codigo,
        NULLIF(BTRIM(c.cod), '')                    AS codigo_documento,
        NULLIF(BTRIM(r.res), '')                    AS proceso,
        r.est1                                      AS estado_origen_id,
        r.est2                                      AS estado_destino_id,
        postventa.fn_fecha(r.fec)                   AS fecha,
        postventa.fn_momento(r.fec, r.hor)          AS momento,
        NULLIF(BTRIM(r.usu), '')                    AS usuario
    FROM raw.rac r
    JOIN raw.con c ON c.ide = r.conide AND c.tip IN (47, 707, 708)
    UNION ALL
    SELECT
        'LOG-' || l.ide                             AS paso_id,
        'CIERRE_APLICACION' AS origen,
        l.ide::BIGINT                               AS ide_origen,
        c.ide                                       AS documento_id,
        c.tip                                       AS tipo_documento_codigo,
        NULLIF(BTRIM(c.cod), '')                    AS codigo_documento,
        'Cerrar parte (postventa-incidencias)'      AS proceso,
        NULL::INT                                   AS estado_origen_id,
        9 AS estado_destino_id,
        postventa.fn_fecha(l.fec)                   AS fecha,
        postventa.fn_momento(l.fec, l.hor)          AS momento,
        NULLIF(BTRIM(l.usu), '')                    AS usuario
    FROM raw.log l
    JOIN raw.con c ON c.tip = l.tip AND BTRIM(c.cod) = BTRIM(l.cod) AND c.emp = l.emp
    WHERE l.tab = 'con' AND l.tip = 708
      AND l.tex LIKE 'Cerrar parte (postventa-incidencias)%'
),
ordenados AS (
    SELECT
        b.*,
        ROW_NUMBER() OVER (PARTITION BY b.documento_id
                           ORDER BY b.momento DESC NULLS LAST, b.ide_origen DESC) AS rn
    FROM pasos b
)
SELECT
    p.paso_id                                       AS paso_id,
    p.origen                                        AS origen,
    p.ide_origen                                    AS ide_origen,
    p.documento_id                                  AS documento_id,
    p.tipo_documento_codigo                         AS tipo_documento_codigo,
    p.codigo_documento                              AS codigo_documento,
    p.proceso                                       AS proceso,
    p.estado_origen_id                              AS estado_origen_id,
    eo.codigo_estado                                AS estado_origen_codigo,
    eo.nombre_estado                                AS estado_origen,
    p.estado_destino_id                             AS estado_destino_id,
    ed.codigo_estado                                AS estado_destino_codigo,
    ed.nombre_estado                                AS estado_destino,
    p.fecha                                         AS fecha,
    p.momento                                       AS momento,
    p.usuario                                       AS usuario,
    NULLIF(BTRIM(us.nombre), '')                    AS usuario_nombre,
    (p.rn = 1)                                      AS es_ultimo
FROM      ordenados p
LEFT JOIN usuarios us ON us.login_norm = UPPER(BTRIM(p.usuario))
LEFT JOIN LATERAL postventa.fn_estado(p.tipo_documento_codigo, p.estado_origen_id)  eo ON TRUE
LEFT JOIN LATERAL postventa.fn_estado(p.tipo_documento_codigo, p.estado_destino_id) ed ON TRUE;

ALTER TABLE postventa.incidencia_procesos ADD PRIMARY KEY (paso_id);
CREATE INDEX ix_pv_procesos_documento ON postventa.incidencia_procesos (documento_id, momento);
CREATE INDEX ix_pv_procesos_usuario   ON postventa.incidencia_procesos (usuario);

COMMENT ON TABLE postventa.incidencia_procesos IS
'Historico de unidades, incidencias y tareas de postventa (F-156): una fila por paso de la ventana Procesos de Sigrid (origen RAC) y una por cierre hecho por la aplicacion postventa-incidencias (origen CIERRE_APLICACION, destino 9, sin origen). Con el estado de origen y de destino, la fecha y el momento (hora de Madrid), el login de quien lo cambio y su nombre. Historia NETA: Deshacer borra el paso. El estado actual y desde cuando: postventa.v_estado_incidencias.';
