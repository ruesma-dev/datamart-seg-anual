-- etl_sigrid/infrastructure/postgres/sql/stg/09_plan_mensual_fase0.sql
--
-- Materializa stg.plan_mensual_fase0 (F-157): el presupuesto vivo de hoy (la
-- fase 0) de coste (ámbito 3) y de venta (ámbito 7), repartido en el tiempo.
-- Es la pantalla de Sigrid «Planificación en el tiempo (por partidas)»: el
-- `planif` de cada partida (% ACUMULADO por mes, separado por `|`) anclado en
-- el `plafec` de la fase 0 de su obra y ámbito.
--
-- LEE: stg.presupuesto (fase_num = 0, ámbitos 3 y 7), raw.obrparpre (planif) y
-- raw.obrfasamb (plafec de la fase 0; si hubiera dos filas para la misma obra y
-- ámbito, la de `ide` mayor). NO lee stg.plan_mensual ni la toca.
--
-- LA REGLA del % es la del master de 08_plan_mensual.sql, en una sola copia:
-- stg.fn_explotar_planif (00_functions.sql). Aquí se aplican, literalmente
-- iguales a las del master, el descarte (pre-arranque sin movimiento y
-- acumulados > 250 %) y las fórmulas de cantidad e importe (cada mes
-- redondeado con los decimales de la obra: el total de una partida puede
-- descuadrar céntimos con su importe, como el master con Sigrid; F-157 D4).
-- Lo vigila tests/test_f157_sql.py.
--
-- Sin reparto no hay filas: una partida sin `planif`, con todo a cero o en una
-- obra sin `plafec` no aparece (el ETL no inventa reparto). Lo que queda sin
-- repartir lo da stg.v_plan_mensual_fase0_cobertura.
--
-- EJECUCIÓN ACOTADA Y DE UNA PASADA (F-025): `build_stg_step` sustituye el
-- marcador de filtro (el comentario F157_FILTRO_OBRAS de la CTE `fa0`, el único)
-- por las obras del plan de la noche y antepone el DELETE de esas mismas obras,
-- en la misma transacción. Por eso aquí no hay TRUNCATE ni DROP. Tampoco hay
-- ventanas: la única está dentro de la función y ve un solo `planif`, así que
-- filtrar por obra da por construcción lo mismo que una pasada entera.
-- ---------------------------------------------------------------------------

WITH fa0 AS (
    SELECT DISTINCT ON (fa.obride, fa.amb)
           fa.obride,
           fa.amb,
           fa.plafec
    FROM raw.obrfasamb fa
    WHERE fa.fas = 0
      AND fa.amb IN (3, 7)
      AND fa.plafec > 0
      AND fa.obride = ANY (/*F157_FILTRO_OBRAS*/)   -- obras del plan (F-025)
    ORDER BY fa.obride, fa.amb, fa.ide DESC
),
base AS (
    SELECT
        pp.presupuesto_id,
        pp.obra_id,
        pp.partida_id,
        pp.ambito_id,
        pp.cantidad,
        pp.precio,
        pp.importe,
        pp.dec_precios,
        pp.dec_importes,
        op.planif,
        date_trunc('month', stg.fn_sigrid_date_to_date(fa0.plafec))::DATE AS mes_inicio
    FROM fa0
    JOIN stg.presupuesto pp
        ON pp.obra_id   = fa0.obride
       AND pp.ambito_id = fa0.amb
    JOIN raw.obrparpre op ON op.ide = pp.presupuesto_id
    WHERE pp.fase_num = 0
      AND pp.ambito_id IN (3, 7)
      AND op.planif IS NOT NULL AND length(trim(op.planif)) >= 1
      -- Un plafec que no es fecha (fn_sigrid_date_to_date da NULL) no ancla nada.
      AND stg.fn_sigrid_date_to_date(fa0.plafec) IS NOT NULL
)
INSERT INTO stg.plan_mensual_fase0 (
    presupuesto_id, obra_id, partida_id, ambito_id,
    mes_inicio, anio_mes, posicion_mes, pct_acumulado, pct_mes,
    precio_unitario, can_mes, can_origen,
    importe_mes, importe_origen,
    importe_mes_raw, importe_origen_raw,
    importe_partida
)
SELECT
    presupuesto_id, obra_id, partida_id, ambito_id,
    mes_inicio,
    (mes_inicio + ((posicion_mes - 1) * INTERVAL '1 month'))::DATE AS anio_mes,
    posicion_mes,
    pct_acumulado,
    pct_mes,
    precio                                                    AS precio_unitario,
    ROUND((cantidad * pct_mes)::NUMERIC, 6)                   AS can_mes,
    ROUND((cantidad * pct_acumulado)::NUMERIC, 6)             AS can_origen,
    -- Las fórmulas de la rama master del 08, sin cambiar una letra.
    ROUND(
        (cantidad * pct_mes) * ROUND(precio::NUMERIC, dec_precios),
        dec_importes
    )                                                          AS importe_mes,
    ROUND(
        (cantidad * pct_acumulado) * ROUND(precio::NUMERIC, dec_precios),
        dec_importes
    )                                                          AS importe_origen,
    ROUND((cantidad * pct_mes * precio)::NUMERIC, 2)           AS importe_mes_raw,
    ROUND((cantidad * pct_acumulado * precio)::NUMERIC, 2)     AS importe_origen_raw,
    importe                                                    AS importe_partida
FROM base b
CROSS JOIN LATERAL stg.fn_explotar_planif(b.planif) e
-- El descarte del master: pre-arranque sin movimiento y acumulados > 250 %.
WHERE NOT (pct_acumulado = 0 AND pct_mes = 0)
  AND pct_acumulado <= 2.5;
