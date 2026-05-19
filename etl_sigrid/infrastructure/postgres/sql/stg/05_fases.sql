-- etl_sigrid/infrastructure/postgres/sql/stg/05_fases.sql
--
-- Materializa stg.fases. Convierte fechas Sigrid (Entero YYYYMMDD) a DATE
-- usando stg.fn_sigrid_date_to_date, y calcula plazo_meses.
--
-- IMPORTANTE: en raw.obrfas la columna del número de fase se llama `fasnum`,
-- no `fas` como en otras tablas Sigrid (obrparpre, obrparpar). El nombre
-- difiere entre tablas porque obrfas es la tabla maestra de fases (donde
-- viven las fechas) y obrparpre/obrparpar referencian al número de fase como
-- atributo simple. En esta tabla `fasnum` es la "columna primaria" del concepto.
--
-- plazo_meses se cuenta inclusivo: una fase del 2024-03-01 al 2024-05-31 son 3 meses
-- (marzo, abril, mayo). Cálculo: (año_fin - año_ini) × 12 + (mes_fin - mes_ini) + 1.
-- Mínimo 1 mes para fases que empiezan y acaban en el mismo mes.
-- NULL si las fechas son inválidas o el rango es negativo.

TRUNCATE TABLE stg.fases;

WITH parsed AS (
    SELECT
        f.ide                                    AS fase_id,
        f.obride                                 AS obra_id,
        f.fasnum                                 AS numero_fase,
        stg.fn_sigrid_date_to_date(f.fecini)     AS fecha_inicio,
        stg.fn_sigrid_date_to_date(f.fecfin)     AS fecha_fin,
        f.ano                                    AS anio,
        f.mes                                    AS mes,
        NULLIF(TRIM(f.res), '')                  AS nombre_mes
    FROM raw.obrfas f
)
INSERT INTO stg.fases (
    fase_id, obra_id, numero_fase, fecha_inicio, fecha_fin, plazo_meses,
    anio, mes, nombre_mes
)
SELECT
    fase_id,
    obra_id,
    numero_fase,
    fecha_inicio,
    fecha_fin,
    CASE
        WHEN fecha_inicio IS NULL
          OR fecha_fin IS NULL
          OR fecha_fin < fecha_inicio
        THEN NULL
        ELSE GREATEST(
            1,
            (
                (EXTRACT(YEAR  FROM fecha_fin) - EXTRACT(YEAR  FROM fecha_inicio)) * 12
              + (EXTRACT(MONTH FROM fecha_fin) - EXTRACT(MONTH FROM fecha_inicio))
              + 1
            )::INTEGER
        )
    END                                          AS plazo_meses,
    anio,
    mes,
    nombre_mes
FROM parsed;
