-- etl_sigrid/infrastructure/postgres/sql/maestro/00_setup.sql
--
-- Schema `maestro`: catálogos para consulta externa por SQL directo
-- (obras, proveedores, proveedores por obra). Desacoplado del seguimiento
-- y del cierre: solo lee de raw.* y se reconstruye con `build-maestros`.
--
-- Idempotente.

CREATE SCHEMA IF NOT EXISTS maestro;

-- Helper de fecha (entero Sigrid YYYYMMDD → DATE). Copia local de
-- stg.fn_sigrid_date_to_date para que el schema maestro no dependa de stg.
CREATE OR REPLACE FUNCTION maestro.fn_fecha(d INTEGER)
RETURNS DATE
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
    IF d IS NULL OR d <= 0 THEN
        RETURN NULL;
    END IF;
    BEGIN
        RETURN to_date(d::TEXT, 'YYYYMMDD');
    EXCEPTION WHEN OTHERS THEN
        RETURN NULL;
    END;
END;
$$;

COMMENT ON FUNCTION maestro.fn_fecha(INTEGER) IS
'Convierte una fecha entera Sigrid (YYYYMMDD) a DATE. NULL para 0/NULL/inválida. Local al schema maestro.';
