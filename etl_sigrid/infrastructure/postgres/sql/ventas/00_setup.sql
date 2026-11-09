-- etl_sigrid/infrastructure/postgres/sql/ventas/00_setup.sql
-- ============================================================================
-- F-040 · VENTAS (1/8): los dos esquemas y las funciones locales.
--
-- `ventas` es el esquema GENERAL (lo leen el estandar y el total, D5): los
-- clientes con su NOMBRE publico (D2) pero sin el CIF de la persona fisica,
-- las facturas de venta, las certificaciones, su enlace y el seguimiento hasta
-- el cobro. Ni direcciones, ni telefonos, ni correos, ni el CIF ni el nombre
-- de la cabecera de la factura.
-- `ventas_restringida` (D2 y D6 del humano, 2026-11-07) guarda lo personal del
-- cliente: solo la lee el perfil total (`R-PERFILES`, patron de
-- `compras_restringida`, F-138). La crea tambien `infra/sql/02_roles.sql`.
--
-- Las funciones son LOCALES a `ventas`, como `tesoreria.fn_fecha`: el modulo
-- solo lee `raw` (y `maestro.centros_coste`, SQL puro sobre `raw`) y no depende
-- del orden de construccion de otros. Sus literales son los de
-- `etl_sigrid/domain/ventas.py`; `tests/test_f040_sql.py` lo vigila.
--
-- Lee de: nada (solo declara).
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS ventas;
CREATE SCHEMA IF NOT EXISTS ventas_restringida;

-- Fecha de Sigrid (entero AAAAMMDD) a DATE; 0, NULL o imposible = NULL. Es
-- copia LITERAL de `tesoreria.fn_fecha` (un test compara los cuerpos).
CREATE OR REPLACE FUNCTION ventas.fn_fecha(d BIGINT)
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

-- R5 · El CIF normalizado (`normalizar_cif`): mayusculas, sin espacios,
-- puntos ni guiones; vacio = NULL.
CREATE OR REPLACE FUNCTION ventas.fn_cif_normalizado(c TEXT)
RETURNS TEXT
LANGUAGE sql IMMUTABLE AS $$
    SELECT NULLIF(upper(regexp_replace(c, '[\s.-]', '', 'g')), '');
$$;

-- R6 · Persona fisica (`es_persona_fisica`): `perfis` <> 0 o un CIF
-- normalizado con forma de NIF de persona (DNI, NIE o K/L/M).
CREATE OR REPLACE FUNCTION ventas.fn_es_persona_fisica(c TEXT, perfis INT)
RETURNS BOOLEAN
LANGUAGE sql IMMUTABLE AS $$
    SELECT COALESCE(perfis, 0) <> 0
        OR COALESCE(c ~ '^[0-9KLMXYZ][0-9]{7}[A-Z]$', FALSE);
$$;

-- R8 · CIF valido (`cif_valido`): la letra de control en DNI y NIE (X/Y/Z ->
-- 0/1/2); K/L/M y CIF de sociedad solo por forma. Vacio no es valido.
CREATE OR REPLACE FUNCTION ventas.fn_cif_valido(c TEXT)
RETURNS BOOLEAN
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN c IS NULL THEN FALSE
        WHEN c ~ '^[0-9]{8}[A-Z]$'
        THEN substr('TRWAGMYFPDXBNJZSQVHLCKE', (substr(c, 1, 8)::BIGINT % 23)::INT + 1, 1)
             = substr(c, 9, 1)
        WHEN c ~ '^[XYZ][0-9]{7}[A-Z]$'
        THEN substr('TRWAGMYFPDXBNJZSQVHLCKE',
                    ((translate(substr(c, 1, 1), 'XYZ', '012') || substr(c, 2, 7))::BIGINT
                     % 23)::INT + 1, 1)
             = substr(c, 9, 1)
        WHEN c ~ '^[KLM][0-9]{7}[A-Z]$' THEN TRUE
        WHEN c ~ '^[ABCDEFGHJNPQRSUVW][0-9]{7}[0-9A-J]$' THEN TRUE
        ELSE FALSE
    END;
$$;

-- R11-R12 · La columna de un recargo (`clase_recargo`), en este orden:
-- coeficientes, garantia, `RETESP` y otras. **El `IN` de la garantia es el
-- UNICO punto de la decision D4** (provisional, a la espera de Juan Romero):
-- es el literal de `CLASES_GARANTIA` del dominio y un test obliga a igualarlo.
CREATE OR REPLACE FUNCTION ventas.fn_clase_recargo(reccla INT)
RETURNS TEXT
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN reccla = 0 THEN 'COEFICIENTES'
        WHEN reccla IN (4, 5) THEN 'GARANTIA'
        WHEN reccla = 1 THEN 'RETESP'
        ELSE 'OTRAS'
    END;
$$;
