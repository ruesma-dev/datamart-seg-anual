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

-- Traducción del ESTADO de un documento, por la PAREJA (tipo, estado).
--
-- F-084 (2026-09-16). En Sigrid el estado de un documento es un número en
-- `con.est`, y lo que ese número significa DEPENDE DEL TIPO DE DOCUMENTO: el
-- 7 es «Firmado» en un contrato (tip 44) y en el catálogo de la factura
-- (tip 15) es otro estado distinto. Traducir uniendo solo por `est` da un
-- literal equivocado sin romper el build, que es la peor forma de fallar.
--
-- POR QUÉ ES UNA FUNCIÓN Y NO UN LATERAL COPIADO EN CADA BLOQUE (criterio 6
-- de F-084). F-083 escribió esta traducción a mano dentro del bloque
-- FACTURAS. F-084 necesitaba la misma para CONTRATOS, y copiarla habría
-- dejado dos `WHERE` que mantener, dos `LIMIT 1` que recordar y dos sitios
-- donde olvidar el tipo. Factorizada, la ganancia no es de líneas: **el tipo
-- de documento es un argumento obligatorio de la firma**, así que la unión
-- «solo por estado_id» deja de poder escribirse — PostgreSQL falla al
-- construir en vez de publicar el literal de otro documento.
--
-- LA GUARDA DE GRANO VIVE AQUÍ, y por eso protege a los dos que llaman: el
-- `ORDER BY ide LIMIT 1` garantiza como mucho UNA fila aunque el catálogo
-- traiga mañana dos para el mismo par. Hoy `(tip, est)` es único —193 de 193
-- filas, 0 pares repetidos, medido el 2026-09-16— y precisamente por eso un
-- `JOIN` sin guarda parecería inocente.
--
-- Se llama con `LEFT JOIN LATERAL ... ON TRUE`: si el estado no casa con el
-- catálogo no devuelve nada, el documento se publica igual y el literal queda
-- a NULL. Hoy no le pasa a ningún contrato (0 huérfanos de 18.978) ni a
-- ninguna factura (0 de 165.866).
--
-- Local a `compras` a propósito, como `fn_sigrid_date`: este módulo solo lee
-- de `raw.*` y no depende del orden de construcción de `maestro`, que publica
-- el mismo catálogo como dimensión en `maestro.estados_documento` (F-073).
CREATE OR REPLACE FUNCTION compras.fn_estado_documento(p_tip INT, p_est INT)
RETURNS TABLE (codigo_estado TEXT, nombre_estado TEXT)
LANGUAGE sql STABLE AS $$
    SELECT ce.cod::TEXT, ce.res::TEXT
    FROM   raw.conest ce
    WHERE  ce.tip = p_tip AND ce.est = p_est
    ORDER  BY ce.ide
    LIMIT  1;
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
