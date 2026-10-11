-- etl_sigrid/infrastructure/postgres/sql/contabilidad/00_setup.sql
-- ============================================================================
-- F-056 · SCHEMA contabilidad (1/8): los esquemas y su conversion de fecha
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
-- F-135 (2026-10-11): DOS ESQUEMAS. La contabilidad COMPLETA vive en
-- `contabilidad_restringida`, que solo lee el grupo `sigrid_dm_restringido_ro`
-- (y el dueno y el administrador); la GENERAL, en `contabilidad`, sin los
-- apuntes de personal (criterio en `etl_sigrid/domain/restriccion_personal.py`)
-- y con solo RECUENTOS de lo que falta. Los permisos van por esquema: lo que el
-- rol general no debe leer esta FISICAMENTE en otro esquema que nunca se le
-- concede (`apply_grants` lo veta y lo verifica cada noche).
--
-- Siete tablas, en este orden (cada fichero la suya):
--   01_plan_cuentas.sql             contabilidad_restringida.plan_cuentas      el plan como arbol
--   02_mayor.sql                    contabilidad_restringida.mayor             una fila por apunte, con la marca
--   03_saldos_cuenta_mes.sql        contabilidad_restringida.saldos_cuenta_mes cuenta x ejercicio x mes
--   04_plan_cuentas_general.sql     contabilidad.plan_cuentas                  con las cuentas CR enmascaradas
--   05_mayor_general.sql            contabilidad.mayor                         solo lo visible
--   06_saldos_general.sql           contabilidad.saldos_cuenta_mes             solo lo visible, con recuento de lo que falta
--   07_apuntes_restringidos_mes.sql contabilidad.apuntes_restringidos_mes      cuanto falta, sin importes
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS contabilidad;
-- Lo crea el dueno de los objetos (`sigrid_dm_etl`, por PG_SET_ROLE) y nace sin
-- ninguna concesion al rol general: aqui no hay ALTER DEFAULT PRIVILEGES para
-- el, y `apply_grants` le revoca USAGE cada noche (F-135, R16).
CREATE SCHEMA IF NOT EXISTS contabilidad_restringida;

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
'Convierte una fecha entera de Sigrid (AAAAMMDD) a DATE. NULL para 0, NULL o invalida. Local al schema contabilidad: la copia es deliberada, como en los otros esquemas modulo.';
