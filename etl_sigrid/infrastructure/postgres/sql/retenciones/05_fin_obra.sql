-- etl_sigrid/infrastructure/postgres/sql/retenciones/05_fin_obra.sql
-- ============================================================================
-- F-095 · LAS RETENCIONES DE PROVEEDOR DESDE LA CONTABILIDAD (3/4)
--
-- Construye:
--   retenciones.fin_obra  una fila por obra de raw.obr
--
-- Lee de raw.obr, raw.obrctr, raw.con y cierre.fact_cierre_mensual (D7): de
-- `cierre` SOLO esa tabla de hechos.
--
-- LAS FECHAS CANDIDATAS, CADA UNA EN SU COLUMNA (R17)
-- ---------------------------------------------------------------------------
--   fecha_inicio_garantia        [H1] MAX no nulo de obrctr.fecinigar; si no
--                                hay, obr.garfecini. obrctr manda, como en la
--                                regla de fin real de cierre (13 obras la tienen
--                                en obrctr y 44 en obr el 2026-09-22; las 13
--                                coinciden).
--   fecha_fin_real               INFORMATIVA. La regla de
--                                cierre.v_pbi_cierre_cabecera replicada (D5):
--                                MAX de obrctr.fecreafin; si no, obr.fecfinrea.
--                                Un test vigila que las dos sigan iguales.
--   fecha_recepcion_provisional  INFORMATIVA. MAX de obrctr.fecprorec.
--   fecha_fin_prevista           INFORMATIVA. MAX de obrctr.fecprefin; si no,
--                                obr.fecfinpre (sin el respaldo por el cierre
--                                que usa la cabecera: aqui solo fechas de Sigrid).
-- obrctr tiene varias filas por obra (165 obras con mas de una): se agrega
-- ANTES de unir, una fila por obra.
--
-- EL ULTIMO CIERRE CON MOVIMIENTO (R18, D7)
-- ---------------------------------------------------------------------------
--   ultimo_cierre  el mayor `anio_mes` de cierre.fact_cierre_mensual de la obra
--                  con `ejecutado_mes <> 0` en algun concepto: el ultimo cierre
--                  que MOVIO algo, no la ultima fase creada. 124 de 330 obras
--                  tienen fases vacias despues de su ultimo movimiento (~12
--                  meses de media): tomar la ultima fase alargaria el fin de
--                  obra casi un ano. `anio_mes` ya es el mes canonico de la fase
--                  (cierre.fn_mes_de_fase) y no se reinterpreta aqui.
-- PRECIO ACEPTADO: `build_cierre` corre DESPUES de `build_retenciones`, asi que
-- este respaldo usa el cierre de la noche anterior (una noche de retraso; un
-- fin de obra no cambia de un dia a otro), y solo existe para las obras del
-- seguimiento. No se declara `build_cierre` en `depends_on` por lo mismo que
-- D3: un fallo de otra rama dejaria la noche sin retenciones.
--
-- EL FIN DE OBRA (R19, R20) [H1]
-- ---------------------------------------------------------------------------
--   fecha_fin_obra   = fecha_inicio_garantia; si no hay, el ULTIMO DIA DEL MES
--                      SIGUIENTE a ultimo_cierre; si tampoco, NULL.
--   fuente_fin_obra  INICIO_GARANTIA | ULTIMO_CIERRE_MAS_1_MES | NULL.
-- Cobertura medida el 2026-09-22 sobre el vivo de verdad: 20,9 % + 76,1 % =
-- 97,0 %. Sin ninguna de las dos quedan 17 obras con retencion viva
-- (132.544,84 EUR): NO SE INVENTA una fecha. `terminada_sin_fin_obra` marca las
-- que ademas estan terminadas, recibidas o cerradas (con.est 19, 21, 23, 25).
-- Las informativas (fin real, recepcion provisional, fin previsto) no entran.
--
-- LA GUARDA (R21): si la tabla del cierre no existe o esta VACIA, este fichero
-- falla con el nombre del sub-paso en vez de publicar todas las obras sin
-- fecha de respaldo.
-- ============================================================================

DO $$
BEGIN
    IF to_regclass('cierre.fact_cierre_mensual') IS NULL THEN
        RAISE EXCEPTION 'fin_obra: no existe la tabla cierre.fact_cierre_mensual; lanza build-cierre antes de build-retenciones';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM cierre.fact_cierre_mensual) THEN
        RAISE EXCEPTION 'fin_obra: cierre.fact_cierre_mensual esta vacia; sin ella ninguna obra tendria fin de obra de respaldo';
    END IF;
END $$;

DROP TABLE IF EXISTS retenciones.fin_obra CASCADE;
CREATE TABLE retenciones.fin_obra AS
WITH oc AS (
    -- obrctr agregada: una fila por obra
    SELECT
        c.obride                                                  AS obra_id,
        MAX(NULLIF(c.fecinigar, 0))                               AS fec_inicio_garantia,
        retenciones.fn_sigrid_date(MAX(NULLIF(c.fecreafin, 0)))   AS fec_real_fin,
        retenciones.fn_sigrid_date(MAX(NULLIF(c.fecprorec, 0)))   AS fec_recepcion_provisional,
        retenciones.fn_sigrid_date(MAX(NULLIF(c.fecprefin, 0)))   AS fec_prev_fin,
        COUNT(*)                                                  AS num_contratos_obra
    FROM raw.obrctr c GROUP BY c.obride
),
cierres AS (
    -- El ultimo mes que movio algo, por obra
    SELECT f.obra_id, MAX(f.anio_mes) AS ultimo_cierre
    FROM cierre.fact_cierre_mensual f
    WHERE f.ejecutado_mes <> 0
    GROUP BY f.obra_id
),
base AS (
    SELECT
        obr.ide                                    AS obra_id,
        con.emp                                    AS empresa_id,
        con.cod                                    AS codigo_obra,
        con.emp::text || '-' || con.cod            AS clave_obra,
        con.res                                    AS nombre_obra,
        con.est                                    AS estado_obra,
        COALESCE(retenciones.fn_sigrid_date(oc.fec_inicio_garantia),
                 retenciones.fn_sigrid_date(obr.garfecini)) AS fecha_inicio_garantia,
        ci.ultimo_cierre                           AS ultimo_cierre,
        -- Fin real: la regla de cierre.v_pbi_cierre_cabecera (D5)
        COALESCE(
            oc.fec_real_fin,
            retenciones.fn_sigrid_date(obr.fecfinrea)
        )                                          AS fecha_fin_real,
        oc.fec_recepcion_provisional AS fecha_recepcion_provisional,
        COALESCE(
            oc.fec_prev_fin,
            retenciones.fn_sigrid_date(obr.fecfinpre)
        )                                          AS fecha_fin_prevista,
        COALESCE(oc.num_contratos_obra, 0)         AS num_contratos_obra
    FROM raw.obr obr
    LEFT JOIN raw.con con ON con.ide = obr.ide
    LEFT JOIN oc ON oc.obra_id = obr.ide
    LEFT JOIN cierres ci ON ci.obra_id = obr.ide
),
fin AS (
    SELECT
        b.*,
        CASE WHEN b.fecha_inicio_garantia IS NOT NULL THEN b.fecha_inicio_garantia
             WHEN b.ultimo_cierre IS NOT NULL
             THEN (b.ultimo_cierre + INTERVAL '2 months' - INTERVAL '1 day')::DATE
        END AS fecha_fin_obra,
        CASE WHEN b.fecha_inicio_garantia IS NOT NULL THEN 'INICIO_GARANTIA'
             WHEN b.ultimo_cierre IS NOT NULL THEN 'ULTIMO_CIERRE_MAS_1_MES'
        END AS fuente_fin_obra
    FROM base b
)
SELECT
    f.obra_id,
    f.empresa_id,
    f.codigo_obra,
    f.clave_obra,
    f.nombre_obra,
    f.estado_obra,
    f.fecha_inicio_garantia,
    f.ultimo_cierre,
    f.fecha_fin_real,
    f.fecha_recepcion_provisional,
    f.fecha_fin_prevista,
    f.fecha_fin_obra,
    f.fuente_fin_obra,
    (f.fecha_fin_obra IS NULL AND COALESCE(f.estado_obra, 0) IN (19, 21, 23, 25)) AS terminada_sin_fin_obra,
    f.num_contratos_obra
FROM fin f;

ALTER TABLE retenciones.fin_obra ADD PRIMARY KEY (obra_id);
