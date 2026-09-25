-- etl_sigrid/infrastructure/postgres/sql/retenciones/06_views_contables.sql
-- ============================================================================
-- F-095 · LAS RETENCIONES DE PROVEEDOR DESDE LA CONTABILIDAD (4/4)
--
-- Construye:
--   retenciones.v_cuadre_proveedor         contabilidad frente a efectos
--   retenciones.v_retencion_contable_obra  saldo por proveedor y obra con su
--                                          vencimiento desde el fin de obra
--
-- Lee de retenciones.saldo_contable, retenciones.apuntes_contables,
-- retenciones.fin_obra (este mismo paso) y retenciones.movimientos (F-094).
--
-- EL CUADRE (R14, R15, H7)
-- ---------------------------------------------------------------------------
-- Por proveedor: `saldo_contable` (la suma de sus filas de saldo_contable)
-- frente a `viva_efectos` (los efectos de retenciones.movimientos con
-- sentido PROVEEDOR y estado VIVA). El criterio de «viva» es el de F-094 y aqui
-- SE LEE, no se recalcula: nada de las columnas de fecha o estado de Sigrid.
-- FULL JOIN para no perder ninguna de las dos colas. Categoria, en este orden:
--   CUADRA              |diferencia| < 1 EUR
--   SIN_EFECTOS_VIVOS   la contabilidad tiene saldo y no hay efecto vivo
--   SIN_SALDO_CONTABLE  hay efectos vivos y la contabilidad no tiene saldo
--   CONTABILIDAD_MAYOR  saldo contable > viva de los efectos
--   EFECTOS_MAYOR       el resto
-- Universo: proveedores con saldo o viva de al menos 1 EUR (el del reparto
-- medido en H7: 761). MANDA LA CONTABILIDAD; la lista de descuadres es para
-- Administracion.
--
-- EL VENCIMIENTO (R24)
-- ---------------------------------------------------------------------------
-- Cada (proveedor, obra) con saldo contable distinto de 0, con el fin de obra,
-- el plazo y el vencimiento de retenciones.fin_obra. `estado_vencimiento` se
-- calcula AL CONSULTAR (fecha de hoy), no en el build:
--   SIN_OBRA      la fila sin obra del proveedor
--   SIN_FIN_OBRA  la obra no tiene ni inicio de garantia ni cuatrimestral con plan
--                 (F-110; antes de F-110, ni cierre con movimiento)
--   VENCIDA       el vencimiento ya paso
--   PENDIENTE     el resto
-- ============================================================================

DROP VIEW IF EXISTS retenciones.v_cuadre_proveedor CASCADE;
CREATE VIEW retenciones.v_cuadre_proveedor AS
WITH contable AS (
    SELECT
        s.proveedor_id,
        MAX(s.proveedor_nombre)   AS proveedor_nombre,
        SUM(s.saldo)              AS saldo_contable,
        SUM(s.saldo_anterior_2016) AS saldo_anterior_2016
    FROM retenciones.saldo_contable s
    GROUP BY s.proveedor_id
),
prescripciones AS (
    -- Lo dado de baja por prescripcion, en positivo
    SELECT a.proveedor_id, -SUM(a.importe) AS prescrito
    FROM retenciones.apuntes_contables a
    WHERE a.es_prescripcion AND a.clase IN ('ALTA', 'BAJA')
    GROUP BY a.proveedor_id
),
efectos AS (
    SELECT
        entidad_id           AS proveedor_id,
        MAX(entidad_nombre)  AS proveedor_nombre,
        SUM(importe)         AS viva_efectos
    FROM retenciones.movimientos WHERE sentido = 'PROVEEDOR' AND estado = 'VIVA'
      AND entidad_id IS NOT NULL
    GROUP BY entidad_id
),
x AS (
    SELECT
        COALESCE(c.proveedor_id, e.proveedor_id)           AS proveedor_id,
        COALESCE(c.proveedor_nombre, e.proveedor_nombre)   AS proveedor_nombre,
        COALESCE(c.saldo_contable, 0)::NUMERIC(18, 2)      AS saldo_contable,
        COALESCE(e.viva_efectos, 0)::NUMERIC(18, 2)        AS viva_efectos,
        COALESCE(c.saldo_anterior_2016, 0)::NUMERIC(18, 2) AS saldo_anterior_2016
    FROM contable c
    FULL JOIN efectos e ON e.proveedor_id = c.proveedor_id
)
SELECT
    x.proveedor_id,
    x.proveedor_nombre,
    x.saldo_contable,
    x.viva_efectos,
    (x.saldo_contable - x.viva_efectos)::NUMERIC(18, 2) AS diferencia,
    CASE WHEN ABS(x.saldo_contable - x.viva_efectos) < 1 THEN 'CUADRA'
         WHEN ABS(x.viva_efectos) < 1 THEN 'SIN_EFECTOS_VIVOS'
         WHEN ABS(x.saldo_contable) < 1 THEN 'SIN_SALDO_CONTABLE'
         WHEN x.saldo_contable > x.viva_efectos THEN 'CONTABILIDAD_MAYOR'
         ELSE 'EFECTOS_MAYOR' END AS categoria,
    x.saldo_anterior_2016,
    COALESCE(p.prescrito, 0)::NUMERIC(18, 2) AS prescrito
FROM x
LEFT JOIN prescripciones p ON p.proveedor_id = x.proveedor_id
WHERE ABS(x.saldo_contable) >= 1 OR ABS(x.viva_efectos) >= 1;

COMMENT ON VIEW retenciones.v_cuadre_proveedor IS
'F-095. Cuadre por proveedor entre el saldo contable de retencion '
'(retenciones.saldo_contable, la fuente que manda) y la retencion viva de los '
'efectos (retenciones.movimientos, estado VIVA de F-094, que aqui solo se '
'lee). categoria: CUADRA, SIN_EFECTOS_VIVOS, SIN_SALDO_CONTABLE, '
'CONTABILIDAD_MAYOR, EFECTOS_MAYOR, en ese orden. Solo proveedores con saldo '
'o viva de al menos 1 EUR.';


DROP VIEW IF EXISTS retenciones.v_retencion_contable_obra CASCADE;
CREATE VIEW retenciones.v_retencion_contable_obra AS
SELECT
    s.proveedor_id,
    s.proveedor_nombre,
    s.obra_id,
    s.empresa_id,
    s.codigo_obra,
    s.clave_obra,
    s.nombre_obra,
    s.saldo,
    s.ultimo_movimiento,
    f.fecha_fin_obra,
    f.fuente_fin_obra,
    f.plazo_meses,
    f.fuente_plazo,
    f.fecha_vencimiento,
    CASE WHEN s.obra_id IS NULL THEN 'SIN_OBRA'
         WHEN f.fecha_vencimiento IS NULL THEN 'SIN_FIN_OBRA'
         WHEN f.fecha_vencimiento < CURRENT_DATE THEN 'VENCIDA'
         ELSE 'PENDIENTE' END AS estado_vencimiento,
    (f.fecha_vencimiento - CURRENT_DATE) AS dias_hasta_vencimiento,
    f.terminada_sin_fin_obra
FROM retenciones.saldo_contable s
LEFT JOIN retenciones.fin_obra f ON f.obra_id = s.obra_id
WHERE s.saldo <> 0;

COMMENT ON VIEW retenciones.v_retencion_contable_obra IS
'F-095. Retencion contable viva por (proveedor, obra) con su vencimiento: fin '
'de obra (fuente_fin_obra) + plazo (fuente_plazo). La fecha de la factura no '
'interviene. estado_vencimiento (SIN_OBRA, SIN_FIN_OBRA, VENCIDA, PENDIENTE) '
'y dias_hasta_vencimiento se calculan al consultar, contra la fecha de hoy.';
