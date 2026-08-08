-- etl_sigrid/infrastructure/postgres/sql/compras/00_setup.sql
-- ============================================================================
-- SCHEMA compras — Tanda C1/C2
-- Módulo independiente: solo lee de raw.*. No toca stg/mart/cierre.
-- Todo importe es SIN IVA (dcapro.tot / dcfpro.tot / ctrpro.tot); la cuota
-- IVA se conserva como columna informativa donde aplica.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS compras;

-- Función local para no depender del schema stg (modularidad).
CREATE OR REPLACE FUNCTION compras.fn_sigrid_date(d BIGINT)
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

-- Serie documental = prefijo alfabético del código ('AC26/21188' → 'AC',
-- 'PROF26/00926' → 'PROF', 'FRGG26/1860' → 'FRGG').
CREATE OR REPLACE FUNCTION compras.fn_serie(cod TEXT)
RETURNS TEXT
LANGUAGE sql IMMUTABLE AS $$
    SELECT UPPER(COALESCE(substring(cod FROM '^[A-Za-z]+'), ''));
$$;

-- Tipo de documento de negocio a partir de (con.tip, serie).
CREATE OR REPLACE FUNCTION compras.fn_tipo_documento(tip INT, serie TEXT)
RETURNS TEXT
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN tip = 14 AND serie = 'AC'              THEN 'ALBARAN'
        WHEN tip = 14 AND serie = 'PROF'            THEN 'PROFORMA'
        WHEN tip = 14 AND serie = 'NTC'             THEN 'NOTA'
        WHEN tip = 14                               THEN 'OTRO'
        WHEN tip = 15 AND serie IN ('FR', 'FRGG')   THEN 'FACTURA'
        WHEN tip = 15 AND serie IN ('AB', 'ABGG')   THEN 'ABONO'
        WHEN tip = 15                               THEN 'OTRO'
        WHEN tip = 44                               THEN 'CONTRATO'
        ELSE 'OTRO'
    END;
$$;
