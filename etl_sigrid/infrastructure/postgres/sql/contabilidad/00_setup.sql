-- etl_sigrid/infrastructure/postgres/sql/contabilidad/00_setup.sql
-- ============================================================================
-- F-056 · SCHEMA contabilidad (1/4): el esquema y su conversion de fecha
--
-- Modulo independiente, como `retenciones` y `personal`: lee SOLO de `raw.*` y
-- de la vista `maestro.centros_coste` (el puente centro de coste -> obra de
-- F-073, SQL puro sobre raw). Nada de stg, mart, cierre, compras, retenciones
-- ni personal (R2). Por eso `build_contabilidad` declara solo `ingest_raw`.
--
-- Es un esquema propio por lo mismo que `personal`: los permisos se dan POR
-- ESQUEMA, y un fallo de su SQL dentro de `build_stg` dejaria sin `mart` la
-- noche. Ningun paso depende de `build_contabilidad` (R5).
--
-- Tres tablas, en este orden (cada fichero la suya):
--   01_plan_cuentas.sql       contabilidad.plan_cuentas      el plan como arbol
--   02_mayor.sql              contabilidad.mayor             una fila por apunte
--   03_saldos_cuenta_mes.sql  contabilidad.saldos_cuenta_mes cuenta x ejercicio x mes
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS contabilidad;

-- La fecha de Sigrid es un entero AAAAMMDD. Misma forma que
-- `retenciones.fn_sigrid_date` y `personal.fn_fecha`: 0, NULL o invalida ->
-- NULL. La copia es deliberada: es lo que permite construir este esquema sin
-- depender de ningun otro.
CREATE OR REPLACE FUNCTION contabilidad.fn_fecha(d BIGINT)
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

COMMENT ON FUNCTION contabilidad.fn_fecha(BIGINT) IS
'Convierte una fecha entera de Sigrid (AAAAMMDD) a DATE. NULL para 0, NULL o invalida. Local al schema contabilidad, como las de compras, retenciones, maestro y personal.';
