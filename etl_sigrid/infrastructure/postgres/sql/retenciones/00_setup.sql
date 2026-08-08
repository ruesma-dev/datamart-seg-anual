-- etl_sigrid/infrastructure/postgres/sql/retenciones/00_setup.sql
-- ============================================================================
-- SCHEMA retenciones — Tanda R1
--
-- Módulo independiente: solo lee de raw.*. No toca stg/mart/cierre/compras.
--
-- MODELO (confirmado por diagnóstico contra Sigrid, julio 2026)
-- ---------------------------------------------------------------------------
-- Una retención de garantía se materializa como un EFECTO con `retide` <> 0:
--
--   · raw.pag  → retención que NOSOTROS practicamos a un PROVEEDOR
--                (nace de una factura de compra, con.tip = 15)
--   · raw.cob  → retención que un CLIENTE nos practica a NOSOTROS
--                (nace de una factura de venta, con.tip = 11)
--
-- Campos del efecto:
--   tot     importe retenido (puede ser NEGATIVO: ajustes/devoluciones)
--   fecven  fecha PREVISTA de devolución/cobro de la retención
--   fecrea  fecha REAL: 0 = aún no devuelta (VIVA); <> 0 = ya liquidada
--   conide  documento origen (factura) → raw.con
--   entide  proveedor / cliente        → raw.con
--   cenide  centro de coste = OBRA en Ruesma (informado en el 98 % de casos)
--   retide  tipo de retención          → raw.rec (extiende con: nombre en con.res)
--   padide  SIEMPRE 0 en Ruesma: la devolución NO encadena efectos
--
-- La regla contractual vive en raw.obrctr.coegar (5.0 = 5 %) para el cliente.
--
-- ATRIBUCIÓN A OBRA — dos vías, en este orden de prioridad:
--   1. efecto.cenide → la obra (en Ruesma cada obra es su propio centro).
--   2. líneas del documento origen (dcfpro/dvfpro), SOLO si todas apuntan a
--      la misma obra. Si la factura reparte entre varias, se deja NULL y se
--      informa en `num_obras_documento` para poder detectarlo.
--   NUNCA sumar por join directo a las líneas: multiplica el importe por el
--   número de líneas de la factura (doble conteo masivo).
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS retenciones;

CREATE OR REPLACE FUNCTION retenciones.fn_sigrid_date(d BIGINT)
RETURNS DATE
LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
    IF d IS NULL OR d = 0 THEN
        RETURN NULL;
    END IF;
    RETURN to_date(d::TEXT, 'YYYYMMDD');
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END $$;


-- ---------------------------------------------------------------------------
-- CATÁLOGO DE TIPOS DE RETENCIÓN (raw.rec, que extiende raw.con)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS retenciones.tipos CASCADE;
CREATE TABLE retenciones.tipos AS
SELECT
    r.ide                                   AS tipo_id,
    con.cod                                 AS codigo,
    con.res                                 AS descripcion,
    r.cla                                   AS clase,
    COALESCE(r.valpor, 0)::NUMERIC(12, 4)   AS porcentaje,
    COALESCE(r.valcan, 0)::NUMERIC(18, 2)   AS importe_fijo,
    r.tipdev                                AS tipo_devolucion,
    r.diavto                                AS dias_vencimiento
FROM raw.rec r
LEFT JOIN raw.con con ON con.ide = r.ide;

ALTER TABLE retenciones.tipos ADD PRIMARY KEY (tipo_id);

COMMENT ON TABLE retenciones.tipos IS
'Tipos de retención (raw.rec + nombre desde raw.con). El tipo dominante en '
'Ruesma es el 558368 (97 % de los efectos): retención de garantía estándar.';


-- ---------------------------------------------------------------------------
-- VISTAS FUENTE DEFENSIVAS
--
-- La obra de un efecto se toma de su `cenide`; como respaldo se mira la obra
-- de las líneas del documento origen (dcfpro para compras, dvfpro para
-- ventas). Esas tablas pueden no estar ingeridas todavía, así que aquí se
-- crea una vista por cada una: si la tabla existe, es un pasarela; si no,
-- una vista vacía con la misma forma. Así el módulo se construye igual y solo
-- pierde el respaldo (la atribución por `cenide` cubre ~98 % de los casos).
--
-- Cuando se ingieran dvf/dvfpro basta relanzar `build-retenciones` para que el
-- respaldo entre en juego automáticamente.
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    v_existe BOOLEAN;
BEGIN
    -- Líneas de factura de COMPRA (respaldo para retenciones a proveedor)
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'raw' AND table_name = 'dcfpro'
    ) INTO v_existe;

    DROP VIEW IF EXISTS retenciones.v_src_lineas_compra CASCADE;
    IF v_existe THEN
        EXECUTE 'CREATE VIEW retenciones.v_src_lineas_compra AS
                 SELECT docide::BIGINT AS docide, obride::BIGINT AS obride
                 FROM raw.dcfpro';
        RAISE NOTICE 'retenciones: respaldo de obra por dcfpro ACTIVO';
    ELSE
        EXECUTE 'CREATE VIEW retenciones.v_src_lineas_compra AS
                 SELECT NULL::BIGINT AS docide, NULL::BIGINT AS obride
                 WHERE FALSE';
        RAISE NOTICE 'retenciones: raw.dcfpro no existe; respaldo de obra '
                     'para PROVEEDOR desactivado (solo cenide)';
    END IF;

    -- Líneas de factura de VENTA (respaldo para retenciones de cliente)
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'raw' AND table_name = 'dvfpro'
    ) INTO v_existe;

    DROP VIEW IF EXISTS retenciones.v_src_lineas_venta CASCADE;
    IF v_existe THEN
        EXECUTE 'CREATE VIEW retenciones.v_src_lineas_venta AS
                 SELECT docide::BIGINT AS docide, obride::BIGINT AS obride
                 FROM raw.dvfpro';
        RAISE NOTICE 'retenciones: respaldo de obra por dvfpro ACTIVO';
    ELSE
        EXECUTE 'CREATE VIEW retenciones.v_src_lineas_venta AS
                 SELECT NULL::BIGINT AS docide, NULL::BIGINT AS obride
                 WHERE FALSE';
        RAISE NOTICE 'retenciones: raw.dvfpro no existe; respaldo de obra '
                     'para CLIENTE desactivado (solo cenide)';
    END IF;
END $$;
