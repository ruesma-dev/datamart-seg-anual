-- etl_sigrid/infrastructure/postgres/sql/stg/00_functions.sql
--
-- Funciones helper del esquema stg. Idempotentes (CREATE OR REPLACE),
-- ejecutables tantas veces como haga falta.

-- ---------------------------------------------------------------------------
-- Convierte una fecha de Sigrid (entero YYYYMMDD) a DATE de Postgres.
-- Devuelve NULL para 0, NULL o fechas inválidas (sin romper la consulta).
-- Ejemplos:
--   stg.fn_sigrid_date_to_date(20240315) → '2024-03-15'::DATE
--   stg.fn_sigrid_date_to_date(0)        → NULL
--   stg.fn_sigrid_date_to_date(NULL)     → NULL
--   stg.fn_sigrid_date_to_date(99999999) → NULL  (fecha inválida)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION stg.fn_sigrid_date_to_date(d INTEGER)
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

COMMENT ON FUNCTION stg.fn_sigrid_date_to_date(INTEGER) IS
'Convierte una fecha entera Sigrid (YYYYMMDD) a DATE. Devuelve NULL para 0, NULL o formato inválido.';
