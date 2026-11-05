-- etl_sigrid/infrastructure/postgres/sql/postventa/00_setup.sql
-- ============================================================================
-- F-156 · POSTVENTA: los dos esquemas y las funciones locales.
--
-- `postventa` es el esquema GENERAL (lo leen el estándar, el total, el
-- restringido y el perfil postventa, D3): unidades, incidencias, tareas, su
-- histórico, sus gráficos y el coste por obra, SIN nombres, teléfonos ni
-- correos de nadie y con el texto libre ENMASCARADO (D10).
-- `postventa_restringida` (D1 = A, «d1 ok» del humano, 2026-11-03) guarda los
-- datos personales de propietarios, reclamantes y contactos: solo la leen el
-- perfil postventa y el total (`apply_grants`, F-156 R28-R30).
--
-- Las funciones son LOCALES a `postventa`, como `compras.fn_sigrid_date`: el
-- módulo solo lee `raw` y no depende del orden de construcción de otros. Sus
-- literales son los de `etl_sigrid/domain/postventa.py` y
-- `tests/test_f156_ingesta_sql.py` lo vigila.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS postventa;
CREATE SCHEMA IF NOT EXISTS postventa_restringida;

-- Fecha de Sigrid (entero AAAAMMDD) a DATE; 0, NULL o imposible = NULL. Es
-- copia LITERAL de `compras.fn_sigrid_date` (un test compara los cuerpos).
CREATE OR REPLACE FUNCTION postventa.fn_fecha(d BIGINT)
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

-- Fecha + hora de Sigrid (HHMMSS, hora local de Madrid) a TIMESTAMP. La regla
-- de la hora es la de `compras/12_documento_procesos.sql` (`hora_sigrid`):
-- entre 1 y 235959 con minutos y segundos por debajo de 60. Sin hora válida,
-- el principio del día; sin fecha, NULL.
CREATE OR REPLACE FUNCTION postventa.fn_momento(fec BIGINT, hor BIGINT)
RETURNS TIMESTAMP
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN postventa.fn_fecha(fec) IS NULL THEN NULL
        WHEN hor BETWEEN 1 AND 235959 AND (hor / 100) % 100 < 60 AND hor % 100 < 60
        THEN postventa.fn_fecha(fec)
             + make_time((hor / 10000)::INT, ((hor / 100) % 100)::INT,
                         (hor % 100)::DOUBLE PRECISION)
        ELSE postventa.fn_fecha(fec)::TIMESTAMP
    END;
$$;

-- Traducción del ESTADO por la PAREJA (tipo, estado): el 5 es «Terminada» en
-- una incidencia (708) y «En garantía» en una unidad (707). Misma regla que
-- `compras.fn_estado_documento` (F-084), local a este módulo.
CREATE OR REPLACE FUNCTION postventa.fn_estado(p_tip INT, p_est INT)
RETURNS TABLE (codigo_estado TEXT, nombre_estado TEXT)
LANGUAGE sql STABLE AS $$
    SELECT ce.cod::TEXT, ce.res::TEXT
    FROM   raw.conest ce
    WHERE  ce.tip = p_tip AND ce.est = p_est
    ORDER  BY ce.ide
    LIMIT  1;
$$;

-- R13 · La máscara del texto libre del esquema general (D10, `enmascarar`):
-- correos -> [CORREO] y, después, teléfonos de nueve cifras que empiezan por
-- 6-9, seguidos o en grupos 3-2-2-2 -> [TELEFONO]. Heurística: lo dice la ficha.
CREATE OR REPLACE FUNCTION postventa.fn_enmascarar(t TEXT)
RETURNS TEXT
LANGUAGE sql IMMUTABLE AS $$
    SELECT regexp_replace(
               regexp_replace(
                   regexp_replace(t, '[^\s@]+@[^\s@]+\.[^\s@]+', '[CORREO]', 'g'),
                   '[6-9][0-9]{8}', '[TELEFONO]', 'g'),
               '[6-9][0-9]{2} [0-9]{2} [0-9]{2} [0-9]{2}', '[TELEFONO]', 'g');
$$;

-- R25 · La obra que lleva el código de una partida de una obra de postventa
-- (`obra_de_partida`): tres o cuatro cifras al principio, sin más cifras
-- detrás, a cuatro con ceros. `0561 ` -> 0561, `0593B` -> 0593, `626` -> 0626,
-- `CI.1.2` -> NULL.
CREATE OR REPLACE FUNCTION postventa.fn_obra_de_partida(cod TEXT)
RETURNS TEXT
LANGUAGE sql IMMUTABLE AS $$
    SELECT lpad(substring(btrim(cod) from '^([0-9]{3,4})(?![0-9])'), 4, '0');
$$;
