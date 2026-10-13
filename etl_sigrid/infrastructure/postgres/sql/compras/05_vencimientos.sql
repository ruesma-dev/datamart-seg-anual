-- etl_sigrid/infrastructure/postgres/sql/compras/05_vencimientos.sql
-- ============================================================================
-- Los EFECTOS DE PAGO de la factura de compra (F-080, R7-R12, R38-R41).
-- Es la pestaña «Vencimientos» de la factura, fila a fila.
--
-- DESDE F-037 (D1, 2026-10-13) ES UNA VISTA de `tesoreria.efectos`, la cartera
-- general de cobros y pagos, filtrada a `sentido = 'PAGO'` y
-- `es_factura_compra`. Antes era una tabla con su propio SQL, y F-080 dejo
-- escrita la deuda: cuando llegara F-037, o la absorbia o la leia, pero no se
-- levantaba una segunda tabla de efectos en paralelo. Se absorbe: la logica
-- del efecto vive UNA vez, en `tesoreria/01_efectos_completo.sql`, y esta
-- vista conserva las MISMAS columnas, nombres, orden y tipos que la tabla de
-- F-080 (`tests/test_f080_sql.py` fija la lista). Ningun efecto de factura de
-- compra es de personal (medido el 2026-10-13: 0 de 197.190), asi que la vista
-- sobre la cartera GENERAL no pierde ni una fila.
--
-- LO QUE F-080 APRENDIO Y SIGUE VALIENDO, aunque ya se aplique en 01:
-- **el efecto de pago ES un documento**. `raw.pag` son «Propiedades de `con`»
-- y cada efecto tiene su fila en `raw.con` con `tip = 25`, asi que su codigo,
-- su descripcion, su estado y su marca de baja **se leen** de la superclase.
-- La remesa (`raw.rpa`) y la cuenta contable tampoco guardan su codigo: esta
-- en `raw.con`. Sus aserciones viven en `tests/test_f037_sql.py`.
--
-- GRANO: una fila por efecto de `raw.pag` cuyo documento sea factura de compra
-- (`raw.dcf`). 197.190 el 2026-10-13.
--
-- Su FRESCURA es la de `build_tesoreria`, no la de `build_compras`: la vista
-- lee `tesoreria.efectos` tal como la dejo ese paso. Los indices los lleva esa
-- tabla (efecto, documento, remesa, estado, vencimiento).
--
-- POR QUE UN `DO` QUE MIRA `relkind` Y NO UN `CREATE OR REPLACE VIEW`. La
-- primera noche, `compras.vencimientos` es todavia la TABLA de F-080, y un
-- `CREATE OR REPLACE VIEW` sobre una tabla falla. Las demas noches es una
-- vista. El `DO` borra lo que haya, sea tabla o vista, con CASCADE: se lleva
-- `compras.v_facturas_pago`, que `06_pago_factura.sql` reconstruye detras,
-- como hasta ahora.
--
-- Lee de: tesoreria.efectos. Escribe en: compras.vencimientos (vista).
-- ============================================================================

DO $$
DECLARE
    v_relkind "char";
BEGIN
    SELECT c.relkind INTO v_relkind
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'compras' AND c.relname = 'vencimientos';

    IF v_relkind IN ('r', 'p') THEN
        EXECUTE 'DROP TABLE compras.vencimientos CASCADE';
    ELSIF v_relkind = 'v' THEN
        EXECUTE 'DROP VIEW compras.vencimientos CASCADE';
    END IF;
END $$;

CREATE VIEW compras.vencimientos AS
SELECT
    efecto_id               AS vencimiento_id,
    documento_id            AS factura_id,
    codigo_documento        AS codigo_factura,
    codigo_efecto           AS codigo_efecto,
    descripcion_efecto      AS descripcion_efecto,
    serie_efecto            AS serie_efecto,
    fecha_emision           AS fecha_emision,
    fecha_vencimiento       AS fecha_vencimiento,
    fecha_real              AS fecha_real,
    importe                 AS importe,
    estado_codigo           AS estado_pago_codigo,
    estado_sigrid           AS estado_pago,
    efecto_anulado          AS efecto_anulado,
    fecha_anulacion         AS fecha_anulacion,
    medio_pago_id           AS medio_pago_id,
    medio_pago              AS medio_pago,
    naturaleza_pago_id      AS naturaleza_pago_id,
    naturaleza_pago         AS naturaleza_pago,
    cuenta_contable_id      AS cuenta_contable_id,
    cuenta_contable         AS cuenta_contable,
    cuenta_contable_nombre  AS cuenta_contable_nombre,
    banco_id                AS banco_id,
    banco                   AS banco,
    sucursal_id             AS sucursal_id,
    sucursal                AS sucursal,
    retencion_id            AS retencion_id,
    centro_coste_id         AS centro_coste_id,
    remesa_id               AS remesa_id,
    codigo_remesa           AS codigo_remesa,
    fecha_remesa            AS fecha_remesa,
    importe_remesa          AS importe_remesa
FROM tesoreria.efectos
WHERE sentido = 'PAGO'
  AND es_factura_compra;

-- Dos nombres que NO aparecen en el COMMENT a proposito: la columna que no se
-- publica y el campo vacio del origen. `tests/test_f080_sql.py` prohibe esos
-- literales en el SQL ejecutable, y con razon: quien los lea ahi creera que
-- existen. El aviso para quien consulta vive en la ficha del diccionario.
COMMENT ON VIEW compras.vencimientos IS
'Efectos de pago de la factura de compra (pestaña Vencimientos). Desde F-037 es una VISTA de tesoreria.efectos (sentido PAGO y es_factura_compra), con las mismas columnas que la tabla de F-080; su frescura es la de build_tesoreria. GRANO: uno '
'por fila de raw.pag cuyo documento sea factura de compra; 197.190 efectos '
'el 2026-10-13. '
'TRAMPA 1: SUMAR LOS IMPORTES DE TODOS LOS EFECTOS DE UNA FACTURA DUPLICA. El '
'efecto nace partido en _01 (pago) y _02 (retencion); al dividirlo los hijos '
'van en serie DIV y el original queda ANULADO; al remesarlo se agrupan en '
'AGR. Ciñendose a los de factura, cerca del 39 % estan de baja: sin filtrar, '
'uno de cada tres es un fantasma. Se excluyen con efecto_anulado = false, que '
'es lo que reproduce el numero que Sigrid enseña en la cabecera. El estado NO '
'distingue al anulado. '
'TRAMPA 2: fecha_real vacia NO significa que el efecto este vivo: avisa de la '
'fecha real de pago, no del estado, y desde 2020 el pago por remesa queda '
'Pagado (estado 10) sin fecha real. El estado es estado_pago (leido de '
'raw.conest con tip = 25); la cartera completa, con estado PREVISTO/REALIZADO/'
'BAJA, es tesoreria.efectos. '
'NO SE PUBLICA el enlace del efecto hijo a su efecto de origen: el campo del '
'ERP que lo prometia vale 0 en todos los efectos, asi que esa relacion no '
'existe en el origen.';
