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


-- ---------------------------------------------------------------------------
-- fn_master_mes_representado
--
-- Extrae el (año, mes) que pretende representar una versión cuatrimestral
-- a partir de los campos res (descripción) y tex (comentario libre del JO).
--
-- Patrones reconocidos:
--   tex: "PLANIFICACION CUATRIMESTRAL <MES_LARGO>-<YY|YYYY>"
--        Ej: "PLANIFICACION CUATRIMESTRAL FEBRERO-26"
--   tex: "PLANIFICACION CUATRIMESTRAL <MES_LARGO> <YY|YYYY>"
--        (con espacio en vez de guión)
--   res: "<algo>_CUAT <MES_CORTO>-<YY|YYYY>"
--        Ej: "Versión 11 (04/03/2026)_CUAT FEB-26"
--
-- Devuelve NULL si no parsea (indica al pipeline que use fec_creacion).
-- Es IMMUTABLE para que el optimizador pueda inlinar y precomputar.
--
-- Ejemplos:
--   fn_master_mes_representado('PLANIFICACION CUATRIMESTRAL FEBRERO-26', NULL)
--     → '2026-02-01'::DATE
--   fn_master_mes_representado(NULL, 'Versión 11 (04/03/2026)_CUAT FEB-26')
--     → '2026-02-01'::DATE
--   fn_master_mes_representado('CIERRE ENERO-26', NULL)
--     → NULL (los cierres no se procesan aquí)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION stg.fn_master_mes_representado(
    p_tex TEXT,
    p_res TEXT
) RETURNS DATE
LANGUAGE plpgsql IMMUTABLE
AS $$
DECLARE
    v_meses_largo TEXT := 'ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE';
    v_meses_corto TEXT := 'ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC';
    v_match       TEXT[];
    v_mes_num     INTEGER;
    v_anno        INTEGER;
BEGIN
    -- Patrón 1: tex contiene "CUATRIM... <MES_LARGO>-<YY|YYYY>"
    -- (formato "PLANIFICACION CUATRIMESTRAL FEBRERO-26")
    v_match := regexp_match(
        upper(COALESCE(p_tex, '')),
        '(?:CUATRIM\w*)\s+(' || v_meses_largo || ')[-\s]+(\d{2,4})'
    );
    IF v_match IS NOT NULL THEN
        v_mes_num := array_position(
            ARRAY['ENERO','FEBRERO','MARZO','ABRIL','MAYO','JUNIO',
                  'JULIO','AGOSTO','SEPTIEMBRE','OCTUBRE','NOVIEMBRE','DICIEMBRE'],
            v_match[1]
        );
        v_anno := CASE WHEN length(v_match[2]) = 2
                       THEN 2000 + v_match[2]::INTEGER
                       ELSE v_match[2]::INTEGER END;
        RETURN make_date(v_anno, v_mes_num, 1);
    END IF;

    -- Patrón 2: tex contiene "VALORADA <MES_LARGO>-<YY|YYYY>"
    -- (formato "PLANIFICACION VALORADA OCT-25" en versión larga
    --  o "PLANIFICACION VALORADA OCTUBRE-25"). Cubre el caso del JO que
    -- escribe "VALORADA" en vez de "CUATRIMESTRAL".
    v_match := regexp_match(
        upper(COALESCE(p_tex, '')),
        '(?:VALORADA)\s+(' || v_meses_largo || ')[-\s]+(\d{2,4})'
    );
    IF v_match IS NOT NULL THEN
        v_mes_num := array_position(
            ARRAY['ENERO','FEBRERO','MARZO','ABRIL','MAYO','JUNIO',
                  'JULIO','AGOSTO','SEPTIEMBRE','OCTUBRE','NOVIEMBRE','DICIEMBRE'],
            v_match[1]
        );
        v_anno := CASE WHEN length(v_match[2]) = 2
                       THEN 2000 + v_match[2]::INTEGER
                       ELSE v_match[2]::INTEGER END;
        RETURN make_date(v_anno, v_mes_num, 1);
    END IF;

    -- Patrón 3: tex contiene "VALORADA <MES_CORTO>-<YY|YYYY>"
    -- (formato "PLANIFICACION VALORADA OCT-25")
    v_match := regexp_match(
        upper(COALESCE(p_tex, '')),
        '(?:VALORADA)\s+(' || v_meses_corto || ')[-\s]*(\d{2,4})'
    );
    IF v_match IS NOT NULL THEN
        v_mes_num := array_position(
            ARRAY['ENE','FEB','MAR','ABR','MAY','JUN',
                  'JUL','AGO','SEP','OCT','NOV','DIC'],
            v_match[1]
        );
        v_anno := CASE WHEN length(v_match[2]) = 2
                       THEN 2000 + v_match[2]::INTEGER
                       ELSE v_match[2]::INTEGER END;
        RETURN make_date(v_anno, v_mes_num, 1);
    END IF;

    -- Patrón 4: res contiene "_CUAT <MES_CORTO>-<YY|YYYY>"
    -- (formato "Versión 11 (04/03/2026)_CUAT FEB-26")
    v_match := regexp_match(
        upper(COALESCE(p_res, '')),
        '_CUAT\s+(' || v_meses_corto || ')[-\s]*(\d{2,4})'
    );
    IF v_match IS NOT NULL THEN
        v_mes_num := array_position(
            ARRAY['ENE','FEB','MAR','ABR','MAY','JUN',
                  'JUL','AGO','SEP','OCT','NOV','DIC'],
            v_match[1]
        );
        v_anno := CASE WHEN length(v_match[2]) = 2
                       THEN 2000 + v_match[2]::INTEGER
                       ELSE v_match[2]::INTEGER END;
        RETURN make_date(v_anno, v_mes_num, 1);
    END IF;

    RETURN NULL;
END;
$$;

COMMENT ON FUNCTION stg.fn_master_mes_representado(TEXT, TEXT) IS
'Devuelve el primer día del mes que una versión cuatrimestral pretende representar (a partir de tex/res). NULL si no parsea.';


-- ---------------------------------------------------------------------------
-- fn_master_fecha_efectiva
--
-- Aplica el guard rail: solo corrige la fec_creacion si hay DOBLE evidencia
-- de que está desplazada respecto al mes que la versión representa.
--
-- Condiciones para corregir (TODAS deben cumplirse):
--   1. La versión es cuatrimestral o "valorada" (heurística del tipo_master
--      del 02_build_fact.sql, simplificada aquí).
--   2. fn_master_mes_representado devuelve una fecha (parsing OK).
--   3. El mes parseado NO coincide con el mes de fec_creacion.
--   4. El mes de fec_creacion NO está en {2, 6, 10}
--      (los meses cuatrimestrales oficiales).
--
-- Si TODAS se cumplen: devuelve primer día (año, mes parseado).
-- Si alguna falla: devuelve fec_creacion (comportamiento heredado).
--
-- Esto cubre el caso real obra 0704 V11 "Versión 11 (04/03/2026)_CUAT FEB-26":
--   - es cuatrimestral (tex contiene CUATRIM)
--   - parsea como febrero 2026
--   - mes parseado (2) ≠ mes fec_creacion (3)
--   - mes fec_creacion (3) ∉ {2, 6, 10}
--   → fec_efectiva = 2026-02-01
--
-- Casos que NO se corrigen:
--   - V6 "_CUAT OCT-25" creada 27/10/2025: mes parseado (10) coincide con
--     mes fec_creacion (10) → mantiene fec_creacion.
--   - Cualquier versión "Cierre mensual" o "ABC": no es cuatrimestral.
--   - V22 "_CUAT FEB-26" creada 27/02/2026: mes fec_creacion (2) ∈ {2,6,10}
--     → mantiene fec_creacion (entrega a tiempo).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION stg.fn_master_fecha_efectiva(
    p_tex          TEXT,
    p_res          TEXT,
    p_fec_creacion DATE
) RETURNS DATE
LANGUAGE plpgsql IMMUTABLE
AS $$
DECLARE
    v_es_cuatrim BOOLEAN;
    v_mes_repr   DATE;
    v_mes_creac  INTEGER;
BEGIN
    -- Si no hay fec_creacion no podemos ni evaluar.
    IF p_fec_creacion IS NULL THEN
        RETURN NULL;
    END IF;

    -- ¿Es cuatrimestral? Misma heurística que se usa en 02_build_fact.sql
    -- (busca CUATRIM o VALORADA en el tex; descarta los Cierres mensuales
    -- y los ABC, que tienen su propia regla y no son cuatrimestrales).
    v_es_cuatrim := upper(COALESCE(p_tex, '')) ~ '(CUATRIM|VALORADA)'
                AND upper(COALESCE(p_tex, '')) !~ 'ABC'
                AND NOT (
                    upper(COALESCE(p_tex, '')) ~ 'INICIAL'
                    AND upper(COALESCE(p_tex, '')) ~ 'VALORADA'
                );

    IF NOT v_es_cuatrim THEN
        RETURN p_fec_creacion;
    END IF;

    -- ¿Parsea el texto?
    v_mes_repr := stg.fn_master_mes_representado(p_tex, p_res);
    IF v_mes_repr IS NULL THEN
        RETURN p_fec_creacion;
    END IF;

    -- ¿Coinciden mes parseado y mes de creación?
    v_mes_creac := EXTRACT(MONTH FROM p_fec_creacion)::INTEGER;
    IF v_mes_creac = EXTRACT(MONTH FROM v_mes_repr)::INTEGER
       AND EXTRACT(YEAR FROM p_fec_creacion) = EXTRACT(YEAR FROM v_mes_repr) THEN
        RETURN p_fec_creacion;
    END IF;

    -- ¿La fec_creacion está en un mes oficial (feb/jun/oct)?
    IF v_mes_creac IN (2, 6, 10) THEN
        RETURN p_fec_creacion;
    END IF;

    -- Todas las guardas pasadas: corregir.
    RETURN v_mes_repr;
END;
$$;

COMMENT ON FUNCTION stg.fn_master_fecha_efectiva(TEXT, TEXT, DATE) IS
'Devuelve la fecha efectiva de una versión master. Igual a fec_creacion excepto cuando hay doble evidencia de que la cuatrimestral fue entregada tarde (mes de creación no oficial y texto que parsea un mes distinto).';
