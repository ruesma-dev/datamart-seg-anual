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

-- ---------------------------------------------------------------------------
-- maestro.v_obra_fichas (F-102) — UNA FILA POR FICHA DE OBRA, y cual es la de
-- Ruesma dentro de su codigo.
--
-- EL MODELO (humano, 2026-09-23): las obras son POR EMPRESA. El mismo codigo es
-- la misma obra vista desde cada empresa —Ruesma (1), Porsan (28), cada UTE— y
-- NO se consolida. Medido en solo lectura el 2026-09-23: 922 fichas, 846
-- codigos, 58 repetidos; dentro de una empresa el codigo es unico. Por eso la
-- clave legible es `clave_obra` = '<empresa>-<codigo>' ('1-0581', '27-0581'):
-- 922 claves para 922 fichas. `empresa_id` es entero, asi que todo lo anterior
-- al primer '-' es la empresa y la clave no puede colisionar.
--
-- LA FICHA DE RUESMA (`es_ficha_principal`) es la primera de su codigo por este
-- orden, y solo este: (1) empresa 1 antes que cualquier otra; (2) marcada en
-- `raw.conext` con cod = '15'; (3) mas cierres (`raw.obrfas`); (4) `tiemod` mas
-- reciente; (5) `ide` DESC, solo como desempate. NINGUNA regla elige por
-- `obra_id` menor: falla en la 0680, donde la copia de la 28 tiene el menor.
-- Un codigo sin ficha de la empresa 1 (0001-0005) decide con (2)-(5).
-- `obra_principal_id` sale de la MISMA ventana: la ficha de la 1 del codigo, o
-- la propia si el codigo no la tiene. Es REFERENCIA: sumar hechos por ella
-- meteria las facturas de la UTE en la obra de Ruesma, que no se consolida.
--
-- POR QUE VIVE AQUI Y NO EN `01_obras.sql`: `maestro.obras` la lee, asi que
-- tiene que existir antes, y los guardas de F-073 leen las columnas de
-- `maestro.obras` del primer `CREATE OR REPLACE VIEW` de `01_obras.sql`. Este
-- fichero corre antes en el mismo paso. Lee SOLO `raw`: `compras` la lee sin
-- depender de `stg`, y no se dropea nunca (patron de `maestro.centros_coste`,
-- que `retenciones` lee desde F-094). Sus columnas nuevas, solo AL FINAL.
--
-- `stg.obras` NO la usa (F-102, R7): sigue eligiendo como hasta hoy y difiere de
-- esta marca en 0581, 0606, 0671 y 0720. Pasar el seguimiento a la ficha de
-- Ruesma, y traer las demas empresas como obras propias, es F-106.
--
-- LOS CIERRES SE CUENTAN ANTES DE UNIR: agregar `raw.obrfas` por obra y unirlo
-- da el mismo numero que una subconsulta por ficha, y en solo lectura tarda 22
-- ms frente a 529 ms. Importa porque la leen las vistas de `compras` en cada
-- consulta. La marca de `conext` es un EXISTS: una ficha con dos filas cod 15 no
-- se multiplica.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW maestro.v_obra_fichas AS
WITH cierres AS (
    SELECT f.obride, count(*) AS num_cierres
    FROM   raw.obrfas f
    GROUP  BY f.obride
),
base AS (
    SELECT
        o.ide                              AS obra_id,
        c.cod                              AS codigo_obra,
        c.emp                              AS empresa_id,
        c.tiemod                           AS tiemod,
        c.emp::text || '-' || c.cod        AS clave_obra,
        EXISTS (SELECT 1 FROM raw.conext x
                WHERE x.conide = o.ide AND x.cod = '15') AS marcada_vigente,
        COALESCE(ci.num_cierres, 0)        AS num_cierres
    FROM      raw.obr o
    JOIN      raw.con c   ON c.ide = o.ide
    LEFT JOIN cierres ci  ON ci.obride = o.ide
),
ranking AS (
    SELECT
        b.*,
        count(*) OVER (PARTITION BY codigo_obra)               AS num_fichas_codigo,
        bool_or(empresa_id = 1) OVER (PARTITION BY codigo_obra) AS hay_ruesma,
        ROW_NUMBER() OVER w AS rango_ficha,
        first_value(obra_id) OVER w AS primera
    FROM base b
    WINDOW w AS (
        PARTITION BY codigo_obra
        -- (1) Ruesma primero, (2) conext cod 15, (3) mas cierres,
        -- (4) mas reciente, (5) desempate por ide DESC.
        ORDER BY
            CASE WHEN empresa_id = 1 THEN 0 ELSE 1 END,
            CASE WHEN marcada_vigente THEN 0 ELSE 1 END,
            num_cierres DESC,
            tiemod DESC NULLS LAST,
            obra_id DESC
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    )
)
SELECT
    obra_id,
    codigo_obra,
    empresa_id,
    clave_obra,
    marcada_vigente,
    num_cierres::int                                     AS num_cierres,
    num_fichas_codigo::int                               AS num_fichas_codigo,
    rango_ficha::int                                     AS rango_ficha,
    (rango_ficha = 1)                                    AS es_ficha_principal,
    CASE WHEN hay_ruesma THEN primera ELSE obra_id END   AS obra_principal_id
FROM ranking;

COMMENT ON VIEW maestro.v_obra_fichas IS
'Una fila por ficha de obra (922 el 2026-09-23) con su empresa y su clave legible clave_obra = empresa-codigo (unica). Las obras son POR EMPRESA y no se consolidan: el mismo codigo es la misma obra vista desde cada empresa. es_ficha_principal marca la ficha de Ruesma (empresa 1) de cada codigo, o la primera del ranking si el codigo no la tiene; obra_principal_id es REFERENCIA y no sirve para agregar hechos de otras empresas. stg.obras NO la usa (F-106).';
