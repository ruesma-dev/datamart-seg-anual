-- etl_sigrid/infrastructure/postgres/sql/retenciones/05_fin_obra.sql
-- ============================================================================
-- F-095 · LAS RETENCIONES DE PROVEEDOR DESDE LA CONTABILIDAD (3/4)
--
-- Construye:
--   retenciones.fin_obra  una fila por obra de raw.obr
--
-- Lee de raw.obr, raw.obrctr y raw.con.
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
-- ============================================================================

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
)
SELECT
    b.obra_id,
    b.empresa_id,
    b.codigo_obra,
    b.clave_obra,
    b.nombre_obra,
    b.estado_obra,
    b.fecha_inicio_garantia,
    b.fecha_fin_real,
    b.fecha_recepcion_provisional,
    b.fecha_fin_prevista,
    b.num_contratos_obra
FROM base b;

ALTER TABLE retenciones.fin_obra ADD PRIMARY KEY (obra_id);
