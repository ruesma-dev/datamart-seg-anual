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
--   tex: "PLANIFICACION CUATRIMESTRAL <MES_CORTO>-<YY|YYYY>"
--        Ej: "PLANIFICACION CUATRIMESTRAL FEB-26"   (obra 0676-B V17)
--   tex: "PLANIFICACION VALORADA <MES_LARGO|MES_CORTO>-<YY|YYYY>"
--        Ej: "PLANIFICACION VALORADA JUN-25"
--   res: "<algo>_CUAT <MES_CORTO>-<YY|YYYY>"
--        Ej: "Versión 11 (04/03/2026)_CUAT FEB-26"   (obra 0704 V11)
--
-- Devuelve NULL si no parsea (indica al pipeline que use fec_creacion).
-- Es IMMUTABLE para que el optimizador pueda inlinar y precomputar.
--
-- IMPORTANTE: los patrones de "mes largo" se evalúan ANTES que los de
-- "mes corto" para evitar que un mes corto (p.ej. "MAY") muerda dentro de
-- un mes largo ("MAYO"). El orden de los bloques es deliberado.
--
-- Ejemplos:
--   fn_master_mes_representado('PLANIFICACION CUATRIMESTRAL FEBRERO-26', NULL)
--     → '2026-02-01'::DATE
--   fn_master_mes_representado('PLANIFICACION CUATRIMESTRAL FEB-26', NULL)
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

    -- Patrón 1b: tex contiene "CUATRIM... <MES_CORTO>-<YY|YYYY>"
    -- (formato "PLANIFICACION CUATRIMESTRAL FEB-26": palabra larga +
    --  abreviatura de mes. Caso real obra 0676-B V17, cuya versión NO lleva
    --  el sufijo "_CUAT" en el res, por lo que el Patrón 4 no lo cubre.)
    -- Va DESPUÉS del Patrón 1 a propósito: si fuese mes largo, ya habría
    -- retornado arriba.
    v_match := regexp_match(
        upper(COALESCE(p_tex, '')),
        '(?:CUATRIM\w*)\s+(' || v_meses_corto || ')[-\s]*(\d{2,4})'
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
'Devuelve el primer día del mes que una versión cuatrimestral pretende representar (a partir de tex/res). Cubre CUATRIM/VALORADA con mes largo o corto en tex, y _CUAT con mes corto en res. NULL si no parsea.';


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
-- También cubre obra 0676-B V17 "PLANIFICACION CUATRIMESTRAL FEB-26"
-- (creada 02/03/2026), gracias al nuevo Patrón 1b de
-- fn_master_mes_representado:
--   - es cuatrimestral
--   - parsea como febrero 2026 (mes corto en tex)
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

-- ---------------------------------------------------------------------------
-- fn_parse_mes_texto (F-118, F-051 absorbida)
--
-- El mes que nombra el TEXTO de una fase real (`stg.fases.nombre_mes`, que es
-- `raw.obrfas.res`). Parte del parser de `cierre.fn_parse_mes_fase` con tres
-- cambios, y NO lo sustituye: aquel decide también el mes de las versiones
-- master de cierre, que F-118 no toca (R5).
--
--   1. Punto de millar en un año suelto: «Abril 2.013» → 2013 (R4).
--   2. Letras y cifras pegadas se separan: «AGOSTO17» → «AGOSTO 17» (R4).
--   3. Se recorren TODOS los tokens: cada nombre de mes sustituye al anterior
--      y cada año también, así que un rango se lee por su ÚLTIMO mes (R3):
--      «Enero 2020-Abril 2020» → 2020-04; «DICIEMBRE 09 A FEBRERO 2010» →
--      2010-02; «SEPTIEMBRE-DICIEMBRE» → NULL (no hay año).
--
-- Reglas del año: cuatro cifras 2000-2099; dos cifras justo detrás de un
-- nombre de mes («Mayo-17», «DICIEMBRE-13»); dos cifras 20-99 si aún no hay
-- año (lo que ya hacía `cierre`). Un 1-12 sin mes todavía es el mes.
--
-- Es, token a token, el oráculo `etl_sigrid/domain/mes_fase.py`
-- (`parse_mes_fase`): `tests/test_f118_sql.py` comprueba que los patrones y los
-- prefijos son los mismos y `python main.py check-mes-fase` compara los dos
-- lados contra todas las fases de la base.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION stg.fn_parse_mes_texto(texto TEXT)
RETURNS DATE
LANGUAGE plpgsql IMMUTABLE
AS $$
DECLARE
    s        TEXT;
    tok      TEXT;
    mes_int  INT := NULL;
    anio_int INT := NULL;
    mes_tok  INT;
    tras_mes BOOLEAN := FALSE;
    tmp      INT;
BEGIN
    IF texto IS NULL THEN RETURN NULL; END IF;
    -- Mayúsculas y sin tildes; las minúsculas acentuadas se traducen también
    -- por si el servidor no las pasa a mayúsculas (locale C).
    s := translate(UPPER(texto), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNAEIOUUN');
    s := regexp_replace(s, '(?<![0-9.])([0-9])\.([0-9]{3})(?![0-9])', '\1\2', 'g');
    s := regexp_replace(s, '([A-Z])([0-9])', '\1 \2', 'g');
    s := regexp_replace(s, '([0-9])([A-Z])', '\1 \2', 'g');
    s := TRIM(regexp_replace(s, '[^A-Z0-9]+', ' ', 'g'));
    IF s = '' THEN RETURN NULL; END IF;

    FOREACH tok IN ARRAY string_to_array(s, ' ') LOOP
        mes_tok := NULL;
        IF tok = 'SEP' OR tok LIKE 'SEPT%' OR tok LIKE 'SET%' THEN
            mes_tok := 9;
        ELSE
            CASE
                WHEN tok LIKE 'ENE%' THEN mes_tok := 1;
                WHEN tok LIKE 'FEB%' THEN mes_tok := 2;
                WHEN tok LIKE 'MAR%' THEN mes_tok := 3;
                WHEN tok LIKE 'ABR%' THEN mes_tok := 4;
                WHEN tok LIKE 'MAY%' THEN mes_tok := 5;
                WHEN tok LIKE 'JUN%' THEN mes_tok := 6;
                WHEN tok LIKE 'JUL%' THEN mes_tok := 7;
                WHEN tok LIKE 'AGO%' THEN mes_tok := 8;
                WHEN tok LIKE 'OCT%' THEN mes_tok := 10;
                WHEN tok LIKE 'NOV%' THEN mes_tok := 11;
                WHEN tok LIKE 'DIC%' THEN mes_tok := 12;
                ELSE NULL;
            END CASE;
        END IF;

        IF mes_tok IS NOT NULL THEN
            mes_int  := mes_tok;
            tras_mes := TRUE;
            CONTINUE;
        END IF;

        -- Más de cuatro cifras no es mes ni año (y no cabría en un INT).
        IF tok ~ '^[0-9]+$' AND length(tok) <= 4 THEN
            tmp := tok::INT;
            IF length(tok) = 4 AND tmp BETWEEN 2000 AND 2099 THEN
                anio_int := tmp;
            ELSIF length(tok) = 2 AND tras_mes THEN
                anio_int := 2000 + tmp;
            ELSIF length(tok) = 2 AND tmp >= 20 AND anio_int IS NULL THEN
                anio_int := 2000 + tmp;
            ELSIF length(tok) <= 2 AND tmp BETWEEN 1 AND 12 AND mes_int IS NULL THEN
                mes_int := tmp;
            END IF;
        END IF;
        tras_mes := FALSE;
    END LOOP;

    IF mes_int IS NULL OR anio_int IS NULL THEN RETURN NULL; END IF;
    RETURN make_date(anio_int, mes_int, 1);
END;
$$;

COMMENT ON FUNCTION stg.fn_parse_mes_texto(TEXT) IS
'F-118: primer día del mes que nombra el texto de una fase real (obrfas.res). Lee rangos por su último mes, años de dos cifras tras el mes y el punto de millar. NULL si no hay mes y año. No es el parser de las versiones master (cierre.fn_parse_mes_fase).';


-- ---------------------------------------------------------------------------
-- fn_mes_de_fase (F-118, F-051 absorbida)
--
-- El mes de una fase real, en cascada (decisión del humano del 2026-09-22):
--   1. el mes del TEXTO, si se lee (R2: manda aunque discrepe de las fechas,
--      también en fases de un solo mes y aunque caiga fuera de ellas);
--   2. si no, el mes de la fecha FIN (D5: la fase termina donde termina);
--   3. si no, el de la fecha de INICIO;
--   4. si no, el `ano`/`mes` que archiva `raw.obrfas`.
--
-- Es la ÚNICA implementación de la regla: `cierre.fn_mes_de_fase` la envuelve
-- y `stg.plan_mensual.anio_mes` la aplica una vez, así que `mart` y `cierre`
-- leen el mes sin recalcularlo (R16).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION stg.fn_mes_de_fase(
    fecha_inicio  DATE,
    nombre_mes    TEXT,
    fecha_fin     DATE DEFAULT NULL,
    mes_archivado DATE DEFAULT NULL
) RETURNS DATE
LANGUAGE plpgsql IMMUTABLE
AS $$
BEGIN
    RETURN COALESCE(
        stg.fn_parse_mes_texto(nombre_mes),
        date_trunc('month', fecha_fin)::DATE,
        date_trunc('month', fecha_inicio)::DATE,
        date_trunc('month', mes_archivado)::DATE
    );
END;
$$;

COMMENT ON FUNCTION stg.fn_mes_de_fase(DATE, TEXT, DATE, DATE) IS
'F-118: mes de una fase real. Manda el texto (stg.fn_parse_mes_texto); si no se lee, el mes de la fecha fin, luego el de la de inicio y por último el ano/mes archivado. Es el anio_mes de las filas reales de stg.plan_mensual.';
