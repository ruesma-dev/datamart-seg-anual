-- etl_sigrid/infrastructure/postgres/sql/cierre/00_setup.sql
--
-- =========================================================================
-- Setup PERSISTENTE del schema 'cierre'. Idempotente.
-- =========================================================================
-- Funciones helper de parseo del mes en textos libres.
-- =========================================================================

-- ---------------------------------------------------------------------------
-- Migración 1.3 → 1.4: eliminar la tabla snapshot (ya no se usa)
-- ---------------------------------------------------------------------------
DROP VIEW  IF EXISTS cierre.v_pbi_snapshot_final  CASCADE;
DROP TABLE IF EXISTS cierre.snapshot_final_diario CASCADE;

-- ---------------------------------------------------------------------------
-- Migración Tanda 1 (mart) — limpia restos si existieran
-- ---------------------------------------------------------------------------
DROP VIEW  IF EXISTS mart.v_pbi_cierre_resumen      CASCADE;
DROP VIEW  IF EXISTS mart.v_pbi_dim_concepto_cierre CASCADE;
DROP TABLE IF EXISTS mart.fact_cierre_mensual       CASCADE;

CREATE SCHEMA IF NOT EXISTS cierre;

COMMENT ON SCHEMA cierre IS
'Cierre mensual de obra. Schema independiente de mart. Lee de stg.plan_mensual '
'(amb 8/11 = versiones master, amb 3/7 = incurrido por fase) y stg.fases.';


-- ===========================================================================
-- fn_parse_mes_fase(texto):
--   Parsea cadenas como "Septiembre 2023", "sep-23", "CIERRE MARZO-25",
--   "PLANIFICACION CUATRIMEST FEB-26"... y devuelve DATE primer día del mes.
--   Acepta mes largo/corto en español, año 2/4 dígitos, orden libre.
--   Devuelve NULL si no encuentra MES y AÑO.
-- ===========================================================================
CREATE OR REPLACE FUNCTION cierre.fn_parse_mes_fase(texto TEXT)
RETURNS DATE
LANGUAGE plpgsql IMMUTABLE
AS $$
DECLARE
    s         TEXT;
    tokens    TEXT[];
    tok       TEXT;
    mes_int   INT := NULL;
    anio_int  INT := NULL;
    tmp       INT;
BEGIN
    IF texto IS NULL THEN RETURN NULL; END IF;
    s := UPPER(TRIM(texto));
    s := translate(s, 'ÁÉÍÓÚÜÑ', 'AEIOUUN');
    s := regexp_replace(s, '[-/._]+', ' ', 'g');
    s := regexp_replace(s, '\s+', ' ', 'g');
    s := TRIM(s);
    IF s = '' THEN RETURN NULL; END IF;
    tokens := string_to_array(s, ' ');

    FOREACH tok IN ARRAY tokens LOOP
        IF tok IS NULL OR tok = '' THEN CONTINUE; END IF;

        IF mes_int IS NULL THEN
            CASE
                WHEN tok LIKE 'ENE%' THEN mes_int := 1;
                WHEN tok LIKE 'FEB%' THEN mes_int := 2;
                WHEN tok LIKE 'MAR%' THEN mes_int := 3;
                WHEN tok LIKE 'ABR%' THEN mes_int := 4;
                WHEN tok LIKE 'MAY%' THEN mes_int := 5;
                WHEN tok LIKE 'JUN%' THEN mes_int := 6;
                WHEN tok LIKE 'JUL%' THEN mes_int := 7;
                WHEN tok LIKE 'AGO%' THEN mes_int := 8;
                WHEN tok IN ('SEP','SEPT','SET')
                  OR tok LIKE 'SEPT%' OR tok LIKE 'SET%' THEN mes_int := 9;
                WHEN tok LIKE 'OCT%' THEN mes_int := 10;
                WHEN tok LIKE 'NOV%' THEN mes_int := 11;
                WHEN tok LIKE 'DIC%' THEN mes_int := 12;
                ELSE NULL;
            END CASE;
            IF mes_int IS NOT NULL THEN CONTINUE; END IF;
        END IF;

        IF tok ~ '^\d+$' THEN
            tmp := tok::INT;
            IF length(tok) = 4 AND tmp BETWEEN 2000 AND 2099 THEN
                IF anio_int IS NULL THEN anio_int := tmp; CONTINUE; END IF;
            END IF;
            IF length(tok) = 2 AND tmp BETWEEN 20 AND 99 THEN
                IF anio_int IS NULL THEN anio_int := 2000 + tmp; CONTINUE; END IF;
            END IF;
            IF tmp BETWEEN 1 AND 12 AND length(tok) <= 2 THEN
                IF mes_int IS NULL THEN mes_int := tmp; CONTINUE; END IF;
            END IF;
        END IF;
    END LOOP;

    IF mes_int IS NULL OR anio_int IS NULL THEN RETURN NULL; END IF;
    RETURN make_date(anio_int, mes_int, 1);
END;
$$;


-- ===========================================================================
-- fn_mes_de_fase(fecha_inicio, nombre_mes, fecha_fin, mes_archivado)  (F-118)
--   Envoltorio de `stg.fn_mes_de_fase`: la regla del mes de una fase real vive
--   UNA sola vez, en `stg` (F-051 R1, absorbida en F-118). Manda el texto de la
--   fase; si no se lee, la fecha fin, la de inicio y el ano/mes archivado.
--   `cierre` ya no la usa para agrupar: lee `stg.plan_mensual.anio_mes`, que es
--   este mismo mes (R16). Se conserva para quien la consulte a mano.
--
--   La firma antigua de dos argumentos se borra: convivir con la de cuatro con
--   DEFAULT haría ambigua cualquier llamada de dos. CASCADE porque las vistas
--   de detalle de este esquema la usaban hasta F-118; `04_views_detalle.sql`
--   las recrea en este mismo build, ya sin ella.
-- ===========================================================================
DROP FUNCTION IF EXISTS cierre.fn_mes_de_fase(DATE, TEXT) CASCADE;

CREATE OR REPLACE FUNCTION cierre.fn_mes_de_fase(
    fecha_inicio  DATE,
    nombre_mes    TEXT,
    fecha_fin     DATE DEFAULT NULL,
    mes_archivado DATE DEFAULT NULL
)
RETURNS DATE
LANGUAGE sql IMMUTABLE
AS $$
    SELECT stg.fn_mes_de_fase(fecha_inicio, nombre_mes, fecha_fin, mes_archivado)
$$;


-- ===========================================================================
-- fn_mes_de_version_master(version_tex, version_descripcion):
--   Mes representado por una versión master (ámbito 8/11) de tipo CIERRE.
--   Manda el TEXTO de la versión (regla del JO). Si version_tex no parsea,
--   fallback a version_descripcion. Si ninguno parsea → NULL.
--
--   Ejemplos:
--     "CIERRE MARZO-25"      → 2025-03-01
--     "CIERRE FEBRERO-25"    → 2025-02-01
--     "CIERRE DICIEMBRE-25/ ABC" → 2025-12-01
--     "Versión 4 (19/02/2025)" + "CIERRE ENERO-25" en otro campo → resuelto
-- ===========================================================================
CREATE OR REPLACE FUNCTION cierre.fn_mes_de_version_master(
    version_tex         TEXT,
    version_descripcion TEXT
)
RETURNS DATE
LANGUAGE plpgsql IMMUTABLE
AS $$
DECLARE
    r DATE;
BEGIN
    r := cierre.fn_parse_mes_fase(version_tex);
    IF r IS NOT NULL THEN RETURN r; END IF;
    r := cierre.fn_parse_mes_fase(version_descripcion);
    RETURN r;
END;
$$;
