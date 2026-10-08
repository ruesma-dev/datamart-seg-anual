-- etl_sigrid/infrastructure/postgres/sql/compras/13_estado_documentos.sql
-- ============================================================================
-- F-132 · `compras.v_estado_documentos`: EL ESTADO ACTUAL DE CADA CONTRATO,
-- FACTURA Y COMPARATIVO Y DESDE CUÁNDO ESTÁ EN ÉL.
--
-- LA FECHA SALE DE `rac` (F-085), vía `compras.documento_procesos`: el último
-- paso de la ventana «Procesos» fecha al segundo el estado actual del 99,4 %
-- de los documentos (medido el 2026-10-08). Tres orígenes (`origen_fecha`):
--   PASO              el destino del último paso es el estado de la cabecera:
--                     la fecha es su `momento` (hora de Madrid; sin hora, su
--                     día a las 00:00), con quién lo dio.
--   ALTA              sin un solo paso y en un estado INICIAL de su tipo: la
--                     fecha es el día de alta (`con.fec`, sin hora; sin alta,
--                     NULL).
--   FUERA_DE_PROCESO  cualquier otro caso (el estado cambió sin un paso, ~75
--                     documentos de stock histórico): SIN fecha, y
--                     `cambio_posterior_a` da la cota «cambió después de».
-- Es la historia NETA de `rac`: «Deshacer proceso» BORRA el paso, así que un
-- estado al que se vuelve deshaciendo cuenta desde el paso que llevó a él la
-- primera vez (D2 del humano). La fecha del deshacer está en `dbo.log` (F-105).
--
-- UNA FILA POR DOCUMENTO de `compras.contratos` (44), `compras.facturas` (15)
-- y `compras.comparativos` (46). El estado (`estado_id`, `estado_codigo`,
-- `estado`) es el de la CABECERA, ya traducido por la pareja tipo-estado
-- (F-084), nunca el destino de un paso. `dias_en_estado` se calcula AL
-- CONSULTAR con la fecha de hoy en Madrid: avanza solo.
--
-- Lee: `compras.contratos`, `compras.facturas`, `compras.comparativos` (01, 08)
-- y `compras.documento_procesos` (12). NUNCA la foto diaria de F-067, que
-- sigue construyéndose en `11` como RESPALDO mientras dura el contraste
-- (`python main.py contraste-estados`). `con.tiemod` tampoco entra (D2 de F-067).
--
-- VA DETRÁS DE `12_documento_procesos.sql` porque `12` hace `DROP TABLE ...
-- CASCADE` cada noche y se lleva la vista por delante: aquí se tira (por si
-- quedaba la de F-067, con otras columnas) y se crea de nuevo.
--
-- LOS LITERALES —familias, estados iniciales y orígenes— son los de
-- `etl_sigrid/domain/estado_documentos.py`, donde la regla está escrita como
-- oráculo y probada caso a caso; `tests/test_f132_sql.py` fija que aquí son
-- LOS MISMOS. Un cambio se hace allí y aquí, en el mismo commit.
-- ============================================================================

DROP VIEW IF EXISTS compras.v_estado_documentos;
CREATE VIEW compras.v_estado_documentos AS
WITH documentos AS (
    -- El estado de la CABECERA (R3), uno por documento.
    SELECT 44 AS tipo_documento_codigo, c.contrato_id AS documento_id,
           c.codigo_contrato AS codigo_documento,
           c.estado_id, c.estado_codigo, c.estado, c.fecha AS fecha_alta   -- c.fecha = con.fec
    FROM compras.contratos c
    UNION ALL
    SELECT 15, f.factura_id, f.codigo_factura, f.estado_id, f.estado_codigo, f.estado,
           f.fecha_alta FROM compras.facturas f
    UNION ALL
    SELECT 46, m.comparativo_id, m.codigo_comparativo, m.estado_id, m.estado_codigo,
           m.estado, m.fecha_alta FROM compras.comparativos m
),
con_paso AS (
    -- El ÚLTIMO paso de `rac`: uno por documento como mucho (`es_ultimo`).
    SELECT d.*, u.paso_id, u.proceso, u.usuario, u.nombre_usuario,
           COALESCE(u.momento, u.fecha::TIMESTAMP) AS momento_ultimo,          -- R4
           CASE WHEN u.paso_id IS NOT NULL
                     AND u.estado_destino_id IS NOT DISTINCT FROM d.estado_id
                THEN 'PASO'                                                     -- R4
                WHEN u.paso_id IS NULL
                     AND (d.tipo_documento_codigo, d.estado_id) IN
                         ((15, 1), (15, 20), (44, 1), (46, 1), (46, 11), (46, 100))
                THEN 'ALTA'                                                     -- R5
                ELSE 'FUERA_DE_PROCESO' END AS origen_fecha                     -- R6
    FROM documentos d
    LEFT JOIN compras.documento_procesos u
           ON u.documento_id = d.documento_id AND u.es_ultimo
),
fechados AS (
    SELECT p.*,
           -- R4, R5, R8: FUERA_DE_PROCESO no tiene fecha; ALTA sin alta, tampoco.
           CASE p.origen_fecha WHEN 'PASO' THEN p.momento_ultimo
                               WHEN 'ALTA' THEN p.fecha_alta::TIMESTAMP END AS en_estado_desde
    FROM con_paso p
)
SELECT
    f.documento_id,
    f.tipo_documento_codigo,
    CASE f.tipo_documento_codigo WHEN 44 THEN 'CONTRATO' WHEN 15 THEN 'FACTURA'
         WHEN 46 THEN 'COMPARATIVO' END::TEXT                    AS tipo_documento,
    f.codigo_documento,
    f.estado_id,
    f.estado_codigo,
    f.estado,
    f.en_estado_desde,
    f.origen_fecha::TEXT                                         AS origen_fecha,
    -- R9: al consultar, con la fecha de Madrid; sin fecha, sin días.
    ((now() AT TIME ZONE 'Europe/Madrid')::date - f.en_estado_desde::date) AS dias_en_estado,
    -- R6, R7: la cota, solo cuando el último paso NO explica el estado.
    CASE WHEN f.origen_fecha = 'FUERA_DE_PROCESO' THEN f.momento_ultimo END AS cambio_posterior_a,
    -- Quién dio el paso, solo cuando ese paso explica el estado (R4-R6).
    CASE WHEN f.origen_fecha = 'PASO' THEN f.paso_id END         AS paso_id,
    CASE WHEN f.origen_fecha = 'PASO' THEN f.proceso END         AS proceso,
    CASE WHEN f.origen_fecha = 'PASO' THEN f.usuario END         AS usuario,
    CASE WHEN f.origen_fecha = 'PASO' THEN f.nombre_usuario END  AS nombre_usuario
FROM fechados f;

COMMENT ON VIEW compras.v_estado_documentos IS
'Estado actual de cada contrato, factura y comparativo y desde cuando esta en el (F-132). La fecha sale del ultimo paso de rac (compras.documento_procesos): origen_fecha PASO (al segundo, hora de Madrid, con quien lo dio), ALTA (sin pasos y en estado inicial: el dia de alta) o FUERA_DE_PROCESO (sin fecha, con la cota en cambio_posterior_a). Historia NETA: un paso deshecho no se fecha. dias_en_estado se calcula al consultar.';
