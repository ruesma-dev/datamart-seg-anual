-- etl_sigrid/infrastructure/postgres/sql/compras/12_documento_procesos.sql
-- ============================================================================
-- F-085 · `compras.documento_procesos`: QUIÉN HIZO QUÉ PASO DE CADA DOCUMENTO,
-- DESDE QUÉ ESTADO, A CUÁL Y CUÁNDO.
--
-- LA FUENTE ES `raw.rac`, el registro de PROCESOS de Sigrid (la ventana
-- «Procesos» del documento): una fila por paso, con el proceso (`conproide`,
-- `res`), el estado de ORIGEN (`est1`) y de DESTINO (`est2`), el login (`usu`),
-- la fecha (`fec`, AAAAMMDD) y la hora (`hor`, HHMMSS: la hora local de Madrid
-- que enseña Sigrid). Desde F-085 se ingiere SIN el filtro `asiide <> 0`
-- (D1): con él se tiraban justo los pasos de comprobar y de aprobar.
--
-- UNA FILA POR FILA DE `raw.rac` de las cuatro familias (D2) que declara
-- `etl_sigrid/domain/documento_procesos.py::FAMILIAS`: 15 FACTURA, 44 CONTRATO,
-- 46 COMPARATIVO y 42 OBRA (~1,01 M filas el 2026-10-07). Clave `paso_id`
-- (`rac.ide`). Las 84 filas de `rac` sin documento en `raw.con` no entran
-- (JOIN, no LEFT JOIN: R16).
--
-- ES LA HISTORIA NETA: «Deshacer proceso» BORRA el paso de `rac`. La bruta y
-- la marca de firma digital están en `dbo.log` (F-105), que no se ingiere.
--
-- LOS LITERALES SON LOS DEL DOMINIO y `tests/test_f085_sql.py` lo vigila: las
-- familias (el `IN` y el `CASE`), el orden de la cadena (`fecha NULLS LAST,
-- hora NULLS LAST, paso_id`), el login casado en `UPPER(BTRIM(...))` por los
-- dos lados y la hora HHMMSS válida (`hora_sigrid`).
--
-- Lee: `raw.rac`, `raw.con`, `raw.usu` y `raw.conest` (por
-- `compras.fn_estado_documento`, de `00_setup.sql`: el estado se traduce por
-- la PAREJA tipo-estado, nunca solo por el estado). Se reconstruye cada noche
-- (DROP + CREATE), como el resto de `compras`. NO es la foto de F-067
-- (`11_historial_estados.sql`), que es persistente y no se toca aquí (D7).
--
-- DATOS PERSONALES: el login (`usuario`) y el NOMBRE de quien lanzó el paso
-- (`nombre_usuario`, `usu.res`), decisión D4 del humano del 2026-10-07. El DNI
-- y el enlace al empleado NO están aquí: van solo en `personal.usuarios_sigrid`.
-- ============================================================================

DROP TABLE IF EXISTS compras.documento_procesos CASCADE;
CREATE TABLE compras.documento_procesos AS
WITH usuarios AS (
    -- Un nombre por login NORMALIZADO (R14, `normalizar_login`): agrupado, así
    -- que el JOIN no multiplica aunque Sigrid repitiera un login. Casan así 137
    -- de los 192 logins de estas familias (93,0 % de las filas); exacto, 133.
    SELECT UPPER(BTRIM(u.cod)) AS login_norm,
           MIN(u.res)          AS nombre
    FROM   raw.usu u
    WHERE  BTRIM(u.cod) <> ''
    GROUP  BY UPPER(BTRIM(u.cod))
),
pasos AS (
    SELECT
        r.ide                                   AS paso_id,
        r.conide                                AS documento_id,
        c.tip                                   AS tipo_documento_codigo,
        c.cod                                   AS codigo_documento,
        -- R9: 0 = proceso fuera del catálogo `conpro` (8,6 % de `rac`); el
        -- nombre del proceso viene igual en `rac.res`.
        NULLIF(r.conproide, 0)                  AS proceso_id,
        BTRIM(r.res)                            AS proceso,
        r.est1                                  AS estado_origen_id,
        r.est2                                  AS estado_destino_id,
        r.usu                                   AS usuario,
        NULLIF(BTRIM(us.nombre), '')            AS nombre_usuario,
        compras.fn_sigrid_date(r.fec)           AS fecha,
        -- R10, `hora_sigrid`: HHMMSS entre 1 y 235959 con minutos y segundos
        -- por debajo de 60; si no, NULL (0 = sin hora).
        CASE WHEN r.hor BETWEEN 1 AND 235959
                  AND (r.hor / 100) % 100 < 60
                  AND r.hor % 100 < 60
             THEN make_time((r.hor / 10000)::INT, ((r.hor / 100) % 100)::INT,
                            (r.hor % 100)::DOUBLE PRECISION)
        END                                     AS hora,
        -- R9: el asiento que generó el paso (solo el de contabilizar lo tiene).
        NULLIF(r.asiide, 0)                     AS asiento_id
    FROM      raw.rac r
    JOIN      raw.con c ON c.ide = r.conide                         -- R16
    LEFT JOIN usuarios us ON us.login_norm = UPPER(BTRIM(r.usu))    -- R14
    WHERE     c.tip IN (15, 44, 46, 42)                             -- FAMILIAS
),
ordenados AS (
    SELECT
        p.*,
        p.fecha + p.hora                        AS momento,
        ROW_NUMBER() OVER w                     AS orden,
        COUNT(*) OVER (PARTITION BY p.documento_id) AS n_pasos,
        LAG(p.estado_destino_id) OVER w         AS destino_anterior,
        LAG(p.fecha + p.hora) OVER w            AS momento_anterior
    FROM pasos p
    -- R11, `encadenar`: el orden de la cadena y su desempate.
    WINDOW w AS (PARTITION BY p.documento_id
                 ORDER BY p.fecha NULLS LAST, p.hora NULLS LAST, p.paso_id)
)
SELECT
    o.paso_id,
    o.documento_id,
    o.tipo_documento_codigo,
    CASE o.tipo_documento_codigo
        WHEN 15 THEN 'FACTURA'
        WHEN 44 THEN 'CONTRATO'
        WHEN 46 THEN 'COMPARATIVO'
        WHEN 42 THEN 'OBRA'
    END::TEXT                                   AS familia,
    o.codigo_documento,
    o.proceso_id,
    o.proceso,
    o.estado_origen_id,
    eo.codigo_estado                            AS estado_origen_codigo,
    eo.nombre_estado                            AS estado_origen,
    o.estado_destino_id,
    ed.codigo_estado                            AS estado_destino_codigo,
    ed.nombre_estado                            AS estado_destino,
    o.usuario,
    o.nombre_usuario,
    o.fecha,
    o.hora,
    o.momento,
    o.asiento_id,
    o.orden::INT                                AS orden,
    (o.orden = o.n_pasos)                       AS es_ultimo,
    -- R12: NULL en el primero; falso = cambio de estado fuera de un proceso.
    CASE WHEN o.orden = 1 THEN NULL
         ELSE o.estado_origen_id IS NOT DISTINCT FROM o.destino_anterior
    END                                         AS encaja_con_anterior,
    -- R13: días con dos decimales; NULL en el primero o si falta un momento.
    ROUND(EXTRACT(EPOCH FROM (o.momento - o.momento_anterior))::NUMERIC / 86400, 2)
                                                AS dias_desde_anterior
FROM ordenados o
LEFT JOIN LATERAL compras.fn_estado_documento(o.tipo_documento_codigo, o.estado_origen_id)  eo ON TRUE
LEFT JOIN LATERAL compras.fn_estado_documento(o.tipo_documento_codigo, o.estado_destino_id) ed ON TRUE;

ALTER TABLE compras.documento_procesos ADD PRIMARY KEY (paso_id);
CREATE INDEX ix_documento_procesos_documento ON compras.documento_procesos (documento_id, orden);
CREATE INDEX ix_documento_procesos_usuario   ON compras.documento_procesos (usuario);
CREATE INDEX ix_documento_procesos_fecha     ON compras.documento_procesos (fecha);

COMMENT ON TABLE compras.documento_procesos IS
'Historial de PROCESOS de facturas, contratos, comparativos y obras (F-085): una fila por paso de la ventana Procesos de Sigrid (raw.rac), con el proceso, el estado de origen y de destino, el login y el nombre de quien lo lanzo, la fecha y la hora (local de Madrid). Clave paso_id (rac.ide). Es la historia NETA: Deshacer proceso borra el paso; la bruta y la firma digital estan en dbo.log (F-105). El estado actual es el destino del paso con es_ultimo. El DNI no esta aqui: solo en personal.usuarios_sigrid.';
