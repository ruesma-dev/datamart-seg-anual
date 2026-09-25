-- etl_sigrid/infrastructure/postgres/sql/retenciones/05_fin_obra.sql
-- ============================================================================
-- F-095 · LAS RETENCIONES DE PROVEEDOR DESDE LA CONTABILIDAD (3/4)
-- F-110 · SIN INICIO DE GARANTIA, EL FIN DE OBRA ES EL ULTIMO CUATRIMESTRAL + 1
--
-- Construye:
--   retenciones.fin_obra  una fila por obra de raw.obr
--
-- Lee de raw.obr, raw.obrctr, raw.con, mart.master_versiones_tipadas y
-- stg.plan_mensual (F-110, D4: que version y que meses) y
-- cierre.fact_cierre_mensual (F-095, D7: solo para la columna informativa
-- `ultimo_cierre`). De `cierre`, de `mart` y de `stg`, SOLO esas tablas.
--
-- LAS FECHAS CANDIDATAS, CADA UNA EN SU COLUMNA (R17 de F-095)
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
-- EL ULTIMO CIERRE CON MOVIMIENTO, SOLO INFORMATIVO (R18 de F-095; F-110 D5)
-- ---------------------------------------------------------------------------
--   ultimo_cierre  el mayor `anio_mes` de cierre.fact_cierre_mensual de la obra
--                  con `ejecutado_mes <> 0` en algun concepto: el ultimo cierre
--                  que MOVIO algo, no la ultima fase creada. `anio_mes` ya es
--                  el mes canonico de la fase (cierre.fn_mes_de_fase).
-- DESDE F-110 NO INTERVIENE en fecha_fin_obra, fuente_fin_obra ni
-- fecha_vencimiento: se publica para ver, junto al fin de obra, hasta cuando
-- movio la obra (18 de las 36 obras que toman fecha por cuatrimestral cerraron
-- despues de su ultimo mes planificado). `build_cierre` corre DESPUES de
-- `build_retenciones`: esta columna va con UNA NOCHE DE DESFASE, y no se declara
-- `build_cierre` en `depends_on` (un fallo de otra rama dejaria la noche sin
-- retenciones).
--
-- LA VERSION CUATRIMESTRAL Y SU ULTIMO MES PLANIFICADO (F-110, D1, D2)
-- ---------------------------------------------------------------------------
--   version_cuatrimestral   [D1] la de MAYOR `version` entre las filas de
--                           mart.master_versiones_tipadas de la obra con
--                           tipo_master = 'Cuatrimestral', en cualquiera de los
--                           dos ambitos master (8 y 11). La clasificacion de
--                           versiones es la de F-078: aqui NO se repite su CASE
--                           ni se lee version_tex, y no se usa la marca de Sigrid
--                           (stg.version_master_vigente), que no es la ultima
--                           cuatrimestral en 10 de las 117 obras. Medido el
--                           2026-09-25: en las 117 obras con alguna, la de mayor
--                           numero es tambien la de mayor fecha efectiva y la de
--                           mayor fecha de creacion.
--   ultimo_mes_planificado  [D2] el mayor `anio_mes` de stg.plan_mensual de esa
--                           version, ambitos 8 y 11, con importe_mes <> 0, de
--                           coste o de venta. Los meses finales a cero (la cola
--                           que Sigrid arrastra con el porcentaje congelado) NO
--                           son plan: 15 de las 117 obras la tienen, de 1 a 10
--                           meses. NULL si la version no tiene ningun mes con
--                           importe (0 obras el 2026-09-25).
-- Version, plan y obra se emparejan SOLO por obra_id, la ficha de SU empresa
-- (R-CODIGO-POR-EMPRESA): la UTE 31-0606 tiene sus propias 10 cuatrimestrales y
-- la ficha de Ruesma 1-0606, 2. Las dos tablas son de la MISMA noche: en run-all
-- build_stg y build_mart van antes que build_retenciones (un test lo fija).
--
-- EL FIN DE OBRA [H] (decision del humano del 2026-09-25, cambia H1 de F-095)
-- ---------------------------------------------------------------------------
--   fecha_fin_obra   = fecha_inicio_garantia; si no hay, el ULTIMO DIA DEL MES
--                      SIGUIENTE a ultimo_mes_planificado [D3]; si tampoco, NULL.
--   fuente_fin_obra  INICIO_GARANTIA | ULTIMO_CUATRIMESTRAL_MAS_1_MES | NULL.
-- Ejemplo literal del humano: «el cuatrimestral de junio 26 puede tener
-- planificada la obra hasta marzo 28; entonces el dia a partir del que contar
-- las retenciones seria el 30 de abril» (ultimo_mes_planificado 2028-03-01,
-- fecha_fin_obra 2028-04-30).
-- Sin cuatrimestral no hay fecha [D6]: no se inventa. Medido el 2026-09-25
-- sobre la retencion viva de los efectos con obra (8.247.267,15 EUR, 179
-- obras): garantia 97 obras / 5.026.655,18; cuatrimestral 32 / 2.960.583,38;
-- sin fecha 50 / 260.028,59 (antes, con el ultimo cierre: 97 / 67 / 15).
-- `terminada_sin_fin_obra` marca las que ademas estan terminadas, recibidas o
-- cerradas (con.est 19, 21, 23, 25). Las informativas (fin real, recepcion
-- provisional, fin previsto y ultimo cierre) no entran.
--
-- EL PLAZO Y EL VENCIMIENTO (R22, R23 de F-095) [H2] · F-110 no los toca
-- ---------------------------------------------------------------------------
--   plazo_meses        obrctr.plaret (plazo de retencion del contrato con el
--                      CLIENTE); si no, obrctr.plagar (su plazo de garantia);
--                      si no, 12. El 12 vive en UNA constante (`constantes`).
--                      obr.garpla no interviene. Aplicar el plazo del cliente al
--                      proveedor es un criterio de Negocio (back-to-back), no un
--                      dato de Sigrid: por eso se publica `fuente_plazo`.
--   fuente_plazo       PLAZO_RETENCION_CLIENTE | PLAZO_GARANTIA_CLIENTE |
--                      PLAZO_FIJO_12
--   fecha_vencimiento  = fecha_fin_obra + plazo_meses meses.
-- LA FECHA DE LA FACTURA NO INTERVIENE NUNCA (decision del humano del
-- 2026-09-22): ni la del documento, ni el vencimiento del efecto, ni la de alta
-- del concepto. El vencimiento de Sigrid (factura + 15 meses) sigue en
-- retenciones.movimientos.fecha_prevista_devolucion, intacto (R25).
-- Esta tabla NO lee la fecha de hoy: el estado VENCIDA/PENDIENTE lo calcula la
-- vista v_retencion_contable_obra al consultarla, para no congelarlo en el build.
--
-- LA GUARDA (F-110 R14), ANTES DEL DROP: el sub-paso falla con su nombre si no
-- existe mart.master_versiones_tipadas, si no tiene ninguna version
-- Cuatrimestral, si stg.plan_mensual no tiene filas de los ambitos 8 u 11, o si
-- no existe cierre.fact_cierre_mensual. Una tabla del cierre VACIA ya no lo
-- tumba (sustituye a R21 de F-095): solo deja ultimo_cierre a NULL, que es
-- informativa.
-- ============================================================================

DO $$
BEGIN
    IF to_regclass('mart.master_versiones_tipadas') IS NULL THEN
        RAISE EXCEPTION 'fin_obra: no existe la tabla mart.master_versiones_tipadas; lanza build-mart antes de build-retenciones';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM mart.master_versiones_tipadas WHERE tipo_master = 'Cuatrimestral') THEN
        RAISE EXCEPTION 'fin_obra: mart.master_versiones_tipadas no tiene ninguna version Cuatrimestral; sin ella ninguna obra sin garantia tendria fin de obra';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM stg.plan_mensual WHERE ambito_id IN (8, 11)) THEN
        RAISE EXCEPTION 'fin_obra: stg.plan_mensual no tiene filas de los ambitos master 8 u 11; lanza build-stg antes de build-retenciones';
    END IF;
    IF to_regclass('cierre.fact_cierre_mensual') IS NULL THEN
        RAISE EXCEPTION 'fin_obra: no existe la tabla cierre.fact_cierre_mensual; lanza build-cierre antes de build-retenciones';
    END IF;
END $$;

DROP TABLE IF EXISTS retenciones.fin_obra CASCADE;
CREATE TABLE retenciones.fin_obra AS
WITH constantes AS (
    -- [H2] el plazo por defecto, en UN solo sitio
    SELECT 12 AS plazo_fijo_meses
),
oc AS (
    -- obrctr agregada: una fila por obra
    SELECT
        c.obride                                                  AS obra_id,
        MAX(NULLIF(c.fecinigar, 0))                               AS fec_inicio_garantia,
        retenciones.fn_sigrid_date(MAX(NULLIF(c.fecreafin, 0)))   AS fec_real_fin,
        retenciones.fn_sigrid_date(MAX(NULLIF(c.fecprorec, 0)))   AS fec_recepcion_provisional,
        retenciones.fn_sigrid_date(MAX(NULLIF(c.fecprefin, 0)))   AS fec_prev_fin,
        NULLIF(MAX(c.plaret), 0)                                  AS plazo_retencion,
        NULLIF(MAX(c.plagar), 0)                                  AS plazo_garantia,
        COUNT(*)                                                  AS num_contratos_obra
    FROM raw.obrctr c GROUP BY c.obride
),
cierres AS (
    -- El ultimo mes que movio algo, por obra (INFORMATIVO desde F-110)
    SELECT f.obra_id, MAX(f.anio_mes) AS ultimo_cierre
    FROM cierre.fact_cierre_mensual f
    WHERE f.ejecutado_mes <> 0
    GROUP BY f.obra_id
),
cuatrimestral AS (
    -- D1: la ultima Cuatrimestral por numero, en el ambito 8 o en el 11
    SELECT v.obra_id, MAX(v.version) AS version_cuatrimestral
    FROM mart.master_versiones_tipadas v
    WHERE v.tipo_master = 'Cuatrimestral'
    GROUP BY v.obra_id
),
plan AS (
    -- D2: el ultimo mes de esa version con importe planificado (la cola a
    -- cero no cuenta); LEFT JOIN para que una version sin meses quede en NULL
    SELECT c.obra_id, c.version_cuatrimestral,
           MAX(pm.anio_mes) FILTER (WHERE pm.importe_mes <> 0) AS ultimo_mes_planificado
    FROM cuatrimestral c
    LEFT JOIN stg.plan_mensual pm
           ON pm.obra_id = c.obra_id
          AND pm.version = c.version_cuatrimestral
          AND pm.ambito_id IN (8, 11)
    GROUP BY c.obra_id, c.version_cuatrimestral
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
        pl.version_cuatrimestral                   AS version_cuatrimestral,
        pl.ultimo_mes_planificado                  AS ultimo_mes_planificado,
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
        COALESCE(oc.plazo_retencion, oc.plazo_garantia, k.plazo_fijo_meses)::INT AS plazo_meses,
        CASE WHEN oc.plazo_retencion IS NOT NULL THEN 'PLAZO_RETENCION_CLIENTE'
             WHEN oc.plazo_garantia IS NOT NULL THEN 'PLAZO_GARANTIA_CLIENTE'
             ELSE 'PLAZO_FIJO_12' END AS fuente_plazo,
        COALESCE(oc.num_contratos_obra, 0)         AS num_contratos_obra
    FROM raw.obr obr
    LEFT JOIN raw.con con ON con.ide = obr.ide
    LEFT JOIN oc ON oc.obra_id = obr.ide
    LEFT JOIN cierres ci ON ci.obra_id = obr.ide
    LEFT JOIN plan pl ON pl.obra_id = obr.ide
    CROSS JOIN constantes k
),
fin AS (
    -- [H] garantia -> ultimo dia del mes siguiente al ultimo mes planificado
    -- -> NULL. ultimo_cierre no entra (F-110 R10, R12).
    SELECT
        b.*,
        CASE WHEN b.fecha_inicio_garantia IS NOT NULL THEN b.fecha_inicio_garantia
             WHEN b.ultimo_mes_planificado IS NOT NULL
             THEN (b.ultimo_mes_planificado + INTERVAL '2 months' - INTERVAL '1 day')::DATE
        END AS fecha_fin_obra,
        CASE WHEN b.fecha_inicio_garantia IS NOT NULL THEN 'INICIO_GARANTIA'
             WHEN b.ultimo_mes_planificado IS NOT NULL THEN 'ULTIMO_CUATRIMESTRAL_MAS_1_MES'
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
    f.version_cuatrimestral,
    f.ultimo_mes_planificado,
    f.fecha_fin_real,
    f.fecha_recepcion_provisional,
    f.fecha_fin_prevista,
    f.fecha_fin_obra,
    f.fuente_fin_obra,
    (f.fecha_fin_obra IS NULL AND COALESCE(f.estado_obra, 0) IN (19, 21, 23, 25)) AS terminada_sin_fin_obra,
    f.plazo_meses,
    f.fuente_plazo,
    (f.fecha_fin_obra + make_interval(months => f.plazo_meses))::DATE AS fecha_vencimiento,
    f.num_contratos_obra
FROM fin f;

ALTER TABLE retenciones.fin_obra ADD PRIMARY KEY (obra_id);

COMMENT ON TABLE retenciones.fin_obra IS
'F-095 y F-110. Una fila por obra de raw.obr. fecha_fin_obra = inicio de '
'garantia (obrctr.fecinigar, si no obr.garfecini); si no hay, ultimo dia del '
'mes siguiente al ultimo mes con importe planificado de la ultima version '
'Cuatrimestral (ultimo_mes_planificado, version_cuatrimestral); si tampoco, '
'NULL (fuente en fuente_fin_obra). plazo_meses = plaret, plagar del contrato '
'con el cliente o el plazo fijo por defecto (fuente_plazo). fecha_vencimiento '
'= fin de obra + plazo: la fecha de la factura no interviene. ultimo_cierre, '
'fin real, recepcion provisional y fin previsto son solo informativas.';
