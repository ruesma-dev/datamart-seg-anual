-- etl_sigrid/infrastructure/postgres/sql/stg/08_plan_mensual.sql
--
-- Materializa stg.plan_mensual con DOS RAMAS de lógica según el ámbito.
--
-- ===========================================================================
-- BRANCH A: MASTER (amb=8 master coste, amb=11 master venta)
-- ===========================================================================
-- Mecánica: explosión del planif "v1|v2|...|vN" en filas mensuales.
--
-- ===========================================================================
-- INTERPRETACIÓN DEL PLANIF (validada empíricamente contra Sigrid V22 obra 0696)
-- ===========================================================================
-- El planif raw es PCT_ACUM LITERAL mes a mes (no pct_mes individual).
-- Cada posición = pct acumulado declarado por el JO en ese mes.
--
-- Posiciones VACÍAS al final del string (separadores "||" sin valor) =
-- fuera del horizonte del planif (la partida no aporta nada en esas pos).
--
-- Posiciones con "0" antes de cualquier valor positivo (la partida aún no
-- empieza): pct_acum_efectivo = 0.
--
-- Posiciones con "0" DESPUÉS de un valor positivo: lo único que decide el
-- trato de Sigrid es si el 0 es FINAL (no hay NINGÚN positivo en posiciones
-- posteriores) o INTERMEDIO (hay actividad después). NO interviene el % máximo
-- alcanzado (no hay umbral).
--
--    Caso A — "0" FINAL tras un positivo (partida cerrada):
--      → FORWARD FILL del ÚLTIMO VALOR POSITIVO declarado (no del máximo),
--        sea cual sea ese % (100 %, 93 %, 50 %...). "Ya no se mueve más".
--      Caso real 0696 V22 P4.04.01.10 (último pos=1.00001): pos 16+ = 0
--      finales → se mantiene en 1.00001.
--      Caso real 0677 V34 40.04.04 (REVISIÓN MUROS, planif ...|0.93|0|0):
--      llega al 93 % en ene-26 y los ceros de feb/mar son FINALES → se
--      mantiene en 0,93 (Sigrid lo arrastra; NO lo estorna). Es lo que
--      cerraba el descuadre de producción 0677 feb (−2.324,96).
--      (El ffill al ÚLTIMO POSITIVO y no al máximo evita el pseudo-incremento
--       espurio en partidas con sobrepaso, ej. P4.03.06 último=1.0 con max=1.054.)
--
--    Caso B — "0" INTERMEDIO (hay un positivo en posiciones posteriores):
--      → 0 LITERAL ese mes (estorno). Un 0 con plan después no es "cerrada":
--        es una bajada planificada de ese tramo.
--      Caso real 0696 V22 P5.19.04.01 (...|0.501|0.501|0.501|0|0|0|0|0|0|
--      0.2|0.4|0.7|1|...): los ceros de feb-jul 26 son INTERMEDIOS (reaparece
--      0,2 en ago-26) → estorno a 0 en feb (−0.501). NO baja por ser 50 %,
--      baja por ser intermedio.
--      Caso real 0677 V34 cap. 08.06 (08.06.19/41/42, patrón 100→0→50→100):
--      el 0 intermedio se respeta → 08.06 feb cuadra (−10.469,22 €) y CD feb
--      0677 → 867.483,31. Confirmado en 0705 V11 (CD +560,34).
--
--    "0" de pre-arranque (sin ningún positivo antes) → 0.
--
-- Regla final aplicada (validada al céntimo contra Sigrid: 0696 V22
-- feb/mar/abr 2026 y 0677/0705 feb 2026):
--    Si pct_acum_raw > 0:
--        pct_efectivo = pct_acum_raw                    (literal positivo)
--    Si pct_acum_raw = 0:
--        Si hay un positivo en posiciones POSTERIORES (0 intermedio):
--            pct_efectivo = 0                           (estorno literal)
--        Si NO lo hay pero SÍ hubo un positivo antes (0 final):
--            pct_efectivo = ultimo_valor_positivo       (ffill, partida cerrada)
--        Si no hubo ningún positivo antes (pre-arranque):
--            pct_efectivo = 0
--    pct_mes = pct_efectivo - LAG(pct_efectivo)
--
-- Validación cuantitativa V22 obra 0696 (importe mensual CD):
--    Feb 26:  Sigrid 812.508,66  vs  Regla 812.508,63   diff -0,03 ✓
--    Mar 26:  Sigrid 1.049.475,54 vs Regla 1.049.475,55  diff +0,01 ✓
--    Abr 26:  Sigrid 1.542.255,23 vs Regla 1.542.255,24  diff +0,01 ✓
--
-- ===========================================================================
-- FECHA EFECTIVA DE LA VERSIÓN
-- ===========================================================================
-- Para cada versión se calcula además fec_efectiva = stg.fn_master_fecha_efectiva.
-- Es igual a fec_creacion en el caso general. Solo difiere cuando se cumple
-- todo lo siguiente:
--   - la versión es cuatrimestral (tex contiene CUATRIM o VALORADA)
--   - el tex o el res parsean un mes representado
--   - mes parseado ≠ mes de fec_creacion
--   - mes de fec_creacion ∉ {2, 6, 10} (meses cuatrimestrales oficiales)
-- En ese caso fec_efectiva = primer día (año, mes parseado).
-- Caso real obra 0704 V11 "_CUAT FEB-26" creada 04/03/2026
--   → fec_efectiva = 2026-02-01 (en lugar de 2026-03-04).
-- Esto es lo que usa 02_build_fact.sql para seleccionar la versión vigente.
--
-- ===========================================================================
-- BRANCH B: REALES (amb=3 coste real, amb=7 venta real)
-- ===========================================================================
-- UN SOLO CIERRE POR MES (F-042, decisión de Negocio del 2026-08-28)
--
-- Veintidós obras tienen dos fases que Sigrid guarda con el mismo año y el
-- mismo mes (dos cierres de quincena, o una fase plurimensual archivada en su
-- mes de arranque). Al proyectarlas al mismo `anio_mes` salían dos filas
-- indistinguibles: 8.778 claves duplicadas en mart.fact_seguimiento_mensual y
-- 30.425.881,56 € de acumulado a origen contados dos veces.
--
-- La regla: manda el cierre de mayor `mes_fase_num` del mes ENTRE LOS QUE NO
-- TIENEN EL ACUMULADO A CERO. El matiz del cero no es cosmético: la obra 0606
-- PUY DU FOU tiene su fase 16 de feb-2021 entera a cero y quedarse con ella
-- publicaría 0 € donde hay 9.053.263,61 € buenos en la fase 14.
--
-- Y NO BASTA CON DESCARTAR LA FILA: `importe_mes` de los reales lo calcula
-- este fichero como `importe_origen - LAG(importe_origen)`, y solo si la fase
-- anterior es la INMEDIATAMENTE CONSECUTIVA. Descartar la fase 20 de la 0499
-- sin más dejaría a la 21 sin LAG consecutivo y el movimiento de feb-2018
-- pasaría de 975.249,98 € a 5.688.073,92 €. Por eso se renumera el orden
-- INTERNO (`orden_fase`), que es lo único que mira el LAG.
--
-- El desplazamiento cuenta SOLO descartes, nunca `dense_rank()`: cerrar todos
-- los huecos movería también los que Sigrid ya trae, y con ellos el
-- `importe_mes` de obras que hoy están bien.
--
-- `version` sigue siendo `mes_fase_num`, el número ORIGINAL de Sigrid, con los
-- huecos que deja la regla: seis JOIN de `cierre/` cruzan `pm.version` contra
-- `stg.fases.numero_fase`. La fase descartada sigue existiendo en `raw` y en
-- `stg.fases`; lo que no tiene es fila en `plan_mensual`.
--
-- ===========================================================================
-- EJECUCIÓN POR TRAMOS DE OBRAS (F-019, incidente del 2026-08-09)
-- ===========================================================================
-- Este fichero YA NO SE EJECUTA TAL CUAL: `build_stg_step` sustituye el
-- marcador de filtro (el comentario F019_FILTRO_OBRAS que hay más abajo, en
-- las dos ramas) por la lista de obras del tramo y lo lanza una vez por
-- tramo, cada uno en su propia transacción. El VACIADO de la tabla lo ejecuta
-- el step UNA sola vez, antes del primer tramo: si siguiera aquí, cada tramo
-- borraría lo insertado por el anterior y solo sobreviviría el último.
--
-- El corte es por obra porque NINGUNA ventana de este fichero cruza obras:
-- todas particionan por presupuesto_id (que pertenece a una única obra) o por
-- una lista que EMPIEZA por obra_id — (obra_id, partida_id, ambito_id) en el
-- LAG de los reales y (obra_id, ambito_id) en el desplazamiento de F-042. Por
-- eso el resultado por tramos es, por construcción, idéntico al de una pasada
-- única.
--
-- F-042 no necesita marcador nuevo, y esto no es una intuición: las tres CTE
-- que añade agregan y ordenan dentro de una obra, así que un tramo no puede
-- ver ni descartar el cierre de otra. `build_stg_step.py` sigue con el único
-- marcador de F-019 y sin una línea de cambio. Quien añada una ventana a este
-- fichero tiene que respetar la misma condición: lo comprueba
-- `tests/test_f042_sql.py::test_f042_ninguna_ventana_del_fichero_cruza_obras`,
-- que lee TODOS los `PARTITION BY` del fichero, no una lista escrita a mano.
--
-- El filtro va en las DOS ramas. Filtrar solo una duplicaría las filas de la
-- otra en cada tramo. Ni una línea de la lógica de negocio cambia.
-- ===========================================================================

-- ===========================================================================
-- BRANCH A: MASTER (amb 8, 11)
-- ===========================================================================
WITH master_planif AS (
    SELECT
        pp.presupuesto_id,
        pp.obra_id,
        pp.partida_id,
        pp.ambito_id,
        pp.fase_num            AS version_master,
        pp.cantidad,
        pp.precio,
        pp.importe,
        pp.dec_cantidades,
        pp.dec_precios,
        pp.dec_importes,
        op.planif,
        date_trunc('month', fa.plafec_date)::DATE AS mes_ancla,
        fa.fec_creacion,
        fa.fec_efectiva,
        fa.res_descripcion,
        fa.tex_descripcion
    FROM stg.presupuesto pp
    JOIN raw.obrparpre op ON op.ide = pp.presupuesto_id
    JOIN (
        SELECT
            fa.obride                            AS obra_id,
            fa.amb                               AS ambito_id,
            fa.fas                               AS version_master,
            stg.fn_sigrid_date_to_date(fa.plafec) AS plafec_date,
            stg.fn_sigrid_date_to_date(fa.fec)   AS fec_creacion,
            -- Fecha efectiva: aplica guard rail para CUAT entregadas tarde.
            -- Si el JO crea la versión en un mes no oficial (no feb/jun/oct)
            -- y el texto declara otro mes representado, se usa el mes
            -- parseado del texto. En todos los demás casos devuelve
            -- fec_creacion. Ver stg.fn_master_fecha_efectiva.
            stg.fn_master_fecha_efectiva(
                COALESCE(NULLIF(TRIM(fa.tex), ''), NULLIF(TRIM(fa_coste.tex), '')),
                fa.res,
                stg.fn_sigrid_date_to_date(fa.fec)
            )                                    AS fec_efectiva,
            COALESCE(
                NULLIF(TRIM(fa.res), ''),
                CASE fa.amb
                    WHEN 8  THEN 'Master coste sin descripción'
                    WHEN 11 THEN 'Master venta sin descripción'
                    ELSE NULL
                END
            )                                    AS res_descripcion,
            COALESCE(
                NULLIF(TRIM(fa.tex), ''),
                NULLIF(TRIM(fa_coste.tex), '')
            )                                    AS tex_descripcion
        FROM raw.obrfasamb fa
        LEFT JOIN raw.obrfasamb fa_coste
            ON fa_coste.obride = fa.obride
           AND fa_coste.fas    = fa.fas
           AND fa_coste.amb    = 8
           AND fa.amb          = 11
        WHERE fa.plafec IS NOT NULL AND fa.plafec > 0
    ) fa
        ON fa.obra_id        = pp.obra_id
       AND fa.ambito_id      = pp.ambito_id
       AND fa.version_master = pp.fase_num
    WHERE pp.ambito_id IN (8, 11)
      AND pp.obra_id = ANY (/*F019_FILTRO_OBRAS*/)   -- tramo (F-019)
      AND op.planif IS NOT NULL
      AND length(trim(op.planif)) >= 1
      AND fa.plafec_date IS NOT NULL
),
-- Explosión: parsear cada valor del planif.
-- Solo se conservan posiciones con valor no vacío. Las posiciones vacías
-- al final del string ("|||" trailing) quedan fuera del horizonte de
-- la partida.
master_explosion AS (
    SELECT
        pp.presupuesto_id, pp.obra_id, pp.partida_id, pp.ambito_id,
        pp.version_master, pp.cantidad, pp.precio, pp.importe,
        pp.dec_cantidades, pp.dec_precios, pp.dec_importes,
        pp.mes_ancla, pp.fec_creacion, pp.fec_efectiva,
        pp.res_descripcion, pp.tex_descripcion,
        u.position::INTEGER AS posicion_mes,
        CASE
            WHEN u.valor ~ '^-?\d+([.,]\d+)?$'
                THEN replace(u.valor, ',', '.')::NUMERIC(18,6)
            ELSE NULL
        END AS pct_acumulado_raw
    FROM master_planif pp
    CROSS JOIN LATERAL unnest(string_to_array(pp.planif, '|'))
        WITH ORDINALITY AS u(valor, position)
    WHERE u.valor IS NOT NULL AND length(trim(u.valor)) > 0
),
-- Métricas auxiliares por partida:
--   pct_positivo  : el valor raw solo si > 0 (sirve para encontrar grupos)
--   max_hasta_aqui: máximo histórico acumulativo (para detectar completión)
master_con_metricas AS (
    SELECT
        *,
        CASE WHEN pct_acumulado_raw > 0 THEN pct_acumulado_raw ELSE NULL END
            AS pct_positivo,
        MAX(pct_acumulado_raw) OVER (
            PARTITION BY presupuesto_id
            ORDER BY posicion_mes
            ROWS UNBOUNDED PRECEDING
        ) AS max_hasta_aqui,
        -- max_posterior: máximo de las posiciones POSTERIORES a la actual.
        -- Distingue un "0" FINAL (sin ningún positivo después → partida
        -- cerrada) de un "0" INTERMEDIO (hay un positivo después → caída
        -- planificada literal de ese mes). NULL en la última posición.
        MAX(pct_acumulado_raw) OVER (
            PARTITION BY presupuesto_id
            ORDER BY posicion_mes
            ROWS BETWEEN 1 FOLLOWING AND UNBOUNDED FOLLOWING
        ) AS max_posterior
    FROM master_explosion
),
-- Asignación de grupos para "forward fill al último valor positivo":
-- COUNT(pct_positivo) OVER cuenta el nº de valores positivos vistos hasta
-- la pos actual. Todas las pos con el mismo "count" pertenecen al mismo
-- grupo (= grupo cuyo "líder" es el último valor positivo encontrado).
master_con_grupos AS (
    SELECT
        *,
        COUNT(pct_positivo) OVER (
            PARTITION BY presupuesto_id
            ORDER BY posicion_mes
            ROWS UNBOUNDED PRECEDING
        ) AS grupo_positivo
    FROM master_con_metricas
),
-- Dentro de cada grupo solo existe UN valor positivo (el primero del
-- grupo), por lo que MAX() = ese único valor = "último positivo visto".
master_con_ultimo_positivo AS (
    SELECT
        *,
        MAX(pct_positivo) OVER (
            PARTITION BY presupuesto_id, grupo_positivo
        ) AS ultimo_positivo
    FROM master_con_grupos
),
-- Aplicar la regla de Sigrid:
--   - pct_acum_raw > 0                          → literal positivo
--   - pct_acum_raw = 0 y hay positivo DESPUÉS    → 0 literal (0 intermedio = estorno)
--   - pct_acum_raw = 0, final, hubo positivo antes → ffill al ÚLTIMO POSITIVO (partida cerrada)
--   - pct_acum_raw = 0, sin positivo antes        → 0 (pre-arranque)
-- (Sin umbral: el corte es FINAL vs INTERMEDIO, no el % alcanzado.)
master_pct_efectivo AS (
    SELECT
        presupuesto_id, obra_id, partida_id, ambito_id, version_master,
        cantidad, precio, importe, dec_cantidades, dec_precios, dec_importes,
        mes_ancla, fec_creacion, fec_efectiva,
        res_descripcion, tex_descripcion,
        posicion_mes,
        pct_acumulado_raw,
        max_hasta_aqui,
        ultimo_positivo,
        CASE
            WHEN pct_acumulado_raw IS NOT NULL AND pct_acumulado_raw > 0
                THEN pct_acumulado_raw                  -- literal positivo
            WHEN COALESCE(max_posterior, 0) > 0
                THEN 0                                   -- 0 INTERMEDIO (hay positivo después) -> 0 literal (estorno)
            WHEN ultimo_positivo IS NOT NULL
                THEN ultimo_positivo                     -- 0 FINAL tras un positivo -> arrastra (partida cerrada)
            ELSE 0                                       -- 0 de pre-arranque (sin positivo previo)
        END AS pct_acumulado
    FROM master_con_ultimo_positivo
),
master_con_pct_mes AS (
    SELECT
        presupuesto_id, obra_id, partida_id, ambito_id, version_master,
        cantidad, precio, importe, dec_cantidades, dec_precios, dec_importes,
        mes_ancla, fec_creacion, fec_efectiva,
        res_descripcion, tex_descripcion,
        posicion_mes, pct_acumulado,
        -- pct_mes = pct_acum efectivo actual - pct_acum efectivo mes anterior
        pct_acumulado - COALESCE(
            LAG(pct_acumulado) OVER (
                PARTITION BY presupuesto_id ORDER BY posicion_mes
            ),
            0
        ) AS pct_mes
    FROM master_pct_efectivo
),

-- ===========================================================================
-- BRANCH B: REALES (amb 3, 7)
-- ===========================================================================
-- Todo lo que hay entre el marcador de INICIO que sigue a este comentario y el
-- de FIN que cierra la rama lo reejecuta TAMBIÉN `python main.py huella-obras
-- --propuesta`, que lo envuelve en su propio WITH y lo agrega SIN
-- MATERIALIZAR para sacar la huella del «después» sin escribir en la base
-- (F-042, R22). Por eso el bloque no puede mencionar ninguna CTE del master ni
-- arrastrar el INSERT: es texto reutilizable, no un fragmento cualquiera.
-- Si mueves los marcadores, `tests/test_f042_sql.py` te lo dice.
/*F042_INICIO_REALES*/
reales_base AS (
    SELECT
        pp.presupuesto_id,
        pp.obra_id,
        pp.partida_id,
        pp.ambito_id,
        pp.fase_num                                AS mes_fase_num,
        pp.cantidad,
        pp.precio,
        pp.dec_cantidades,
        pp.dec_precios,
        pp.dec_importes,
        ROUND(pp.precio::NUMERIC, pp.dec_precios)  AS precio_redondeado,
        -- importe a origen con decimales propios de la obra:
        --   redondea can a decc y pre a decp antes de multiplicar; resultado a deci
        -- cantidad SIN redondear (partidas % necesitan precisión completa);
        -- solo precio a dec_precios, resultado a dec_importes
        ROUND(
            pp.cantidad::NUMERIC * ROUND(pp.precio::NUMERIC, pp.dec_precios),
            pp.dec_importes
        )                                          AS importe_origen_round,
        ROUND((pp.cantidad * pp.precio)::NUMERIC, 2)                     AS importe_origen_raw,
        op.totinc                                  AS total_incurrido_raw,
        f.nombre_mes                               AS res_descripcion,
        make_date(f.anio, f.mes, 1)                AS anio_mes
    FROM stg.presupuesto pp
    JOIN raw.obrparpre op ON op.ide = pp.presupuesto_id
    JOIN stg.fases     f
        ON f.obra_id     = pp.obra_id
       AND f.numero_fase = pp.fase_num
    WHERE pp.ambito_id IN (3, 7)
      AND pp.obra_id = ANY (/*F019_FILTRO_OBRAS*/)   -- tramo (F-019)
      AND pp.fase_num >= 1
      AND f.anio IS NOT NULL
      AND f.mes  IS NOT NULL
),
-- F-042: un cierre por mes. Una fila por (obra, ámbito, fase): miles, no
-- millones. `COALESCE` porque una fase sin ningún importe daría SUM = NULL, y
-- `NULL <> 0` no es cierto: en el ORDER BY de abajo los nulos van PRIMERO y esa
-- fase sin dato ganaría el mes.
reales_cierres AS (
    SELECT obra_id, ambito_id, anio_mes, mes_fase_num,
           COALESCE(SUM(importe_origen_round), 0) AS acumulado
    FROM reales_base
    GROUP BY obra_id, ambito_id, anio_mes, mes_fase_num
),
-- R1 + R2 + R4 + R11: manda el más moderno DE ENTRE LOS QUE NO ESTÁN A CERO.
-- El orden de las dos claves ES la regla: invertirlas deja a PUY DU FOU
-- publicando 0 € en feb-2021. Si todos los del mes están a cero, gana el mayor,
-- que es lo que hace el segundo criterio cuando el primero empata.
reales_vigente AS (
    SELECT DISTINCT ON (obra_id, ambito_id, anio_mes)
           obra_id, ambito_id, anio_mes, mes_fase_num
    FROM reales_cierres
    ORDER BY obra_id, ambito_id, anio_mes,
             (acumulado <> 0) DESC, mes_fase_num DESC
),
-- R5 + R6: desplaza SOLO por los descartes que quedan por debajo; los huecos
-- que ya traía Sigrid se respetan. La ventana particiona por (obra, ámbito), o
-- sea que no cruza obras: el troceo por tramos de F-019 sigue siendo válido por
-- el mismo argumento estructural y sin marcador nuevo.
reales_orden AS (
    SELECT c.obra_id, c.ambito_id, c.mes_fase_num,
           (v.mes_fase_num IS NOT NULL) AS vive,
           c.mes_fase_num - COALESCE(SUM(CASE WHEN v.mes_fase_num IS NULL THEN 1 ELSE 0 END)
               OVER (PARTITION BY c.obra_id, c.ambito_id ORDER BY c.mes_fase_num
                     ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS orden_fase
    FROM reales_cierres c
    LEFT JOIN reales_vigente v USING (obra_id, ambito_id, mes_fase_num)
),
reales_con_lag AS (
    SELECT
        presupuesto_id, obra_id, partida_id, ambito_id,
        mes_fase_num,
        cantidad,
        precio,
        dec_cantidades,
        dec_precios,
        dec_importes,
        precio_redondeado,
        importe_origen_round,
        importe_origen_raw,
        total_incurrido_raw,
        res_descripcion,
        anio_mes,
        -- F-042: los cuatro CASE miran `orden_fase`, el orden INTERNO ya
        -- desplazado por los descartes, no el número de fase de Sigrid. Es lo
        -- que devuelve el LAG a ser consecutivo cuando se descarta un cierre.
        CASE
            WHEN LAG(orden_fase) OVER w = orden_fase - 1
            THEN cantidad - COALESCE(LAG(cantidad) OVER w, 0)
            ELSE cantidad
        END AS cantidad_mes,
        CASE
            WHEN LAG(orden_fase) OVER w = orden_fase - 1
            THEN importe_origen_round - COALESCE(LAG(importe_origen_round) OVER w, 0)
            ELSE importe_origen_round
        END AS importe_mes_round,
        CASE
            WHEN LAG(orden_fase) OVER w = orden_fase - 1
            THEN importe_origen_raw - COALESCE(LAG(importe_origen_raw) OVER w, 0)
            ELSE importe_origen_raw
        END AS importe_mes_raw,
        CASE
            WHEN LAG(orden_fase) OVER w = orden_fase - 1
            THEN total_incurrido_raw - COALESCE(LAG(total_incurrido_raw) OVER w, 0)
            ELSE total_incurrido_raw
        END AS total_incurrido_mes_calc
    -- El JOIN va con USING para que `obra_id`, `ambito_id` y `mes_fase_num`
    -- queden como columnas fusionadas y el resto del bloque siga sin cualificar.
    FROM reales_base
    JOIN reales_orden o USING (obra_id, ambito_id, mes_fase_num)
    WHERE o.vive
    WINDOW w AS (
        PARTITION BY obra_id, partida_id, ambito_id
        ORDER BY orden_fase
    )
)
/*F042_FIN_REALES*/

-- ===========================================================================
-- INSERT FINAL
-- ===========================================================================
INSERT INTO stg.plan_mensual (
    presupuesto_id, obra_id, partida_id, ambito_id,
    version, version_descripcion, version_tex,
    version_fec_creacion, version_fec_efectiva,
    anio_mes, posicion_mes, pct_acumulado, pct_mes,
    precio_unitario, can_mes, can_origen,
    importe_mes, importe_origen,
    importe_mes_raw, importe_origen_raw,
    total_incurrido, total_incurrido_mes
)
-- ---- master ----
SELECT
    presupuesto_id, obra_id, partida_id, ambito_id,
    version_master                                            AS version,
    res_descripcion                                           AS version_descripcion,
    tex_descripcion                                           AS version_tex,
    fec_creacion                                              AS version_fec_creacion,
    fec_efectiva                                              AS version_fec_efectiva,
    (mes_ancla + ((posicion_mes - 1) * INTERVAL '1 month'))::DATE AS anio_mes,
    posicion_mes,
    pct_acumulado,
    pct_mes,
    precio                                                    AS precio_unitario,
    ROUND((cantidad * pct_mes)::NUMERIC, 6)                   AS can_mes,
    ROUND((cantidad * pct_acumulado)::NUMERIC, 6)             AS can_origen,
    -- importe con decimales propios de la obra (decc/decp/deci de stg.presupuesto):
    --   redondea cantidad a decc y precio a decp antes de multiplicar; resultado a deci
    -- La cantidad NO se redondea (ver nota en 06_presupuesto.sql: partidas %).
    -- Solo se redondea el precio a dec_precios; el resultado a dec_importes.
    ROUND(
        (cantidad * pct_mes) * ROUND(precio::NUMERIC, dec_precios),
        dec_importes
    )                                                          AS importe_mes,
    ROUND(
        (cantidad * pct_acumulado) * ROUND(precio::NUMERIC, dec_precios),
        dec_importes
    )                                                          AS importe_origen,
    ROUND((cantidad * pct_mes * precio)::NUMERIC, 2)                           AS importe_mes_raw,
    ROUND((cantidad * pct_acumulado * precio)::NUMERIC, 2)                     AS importe_origen_raw,
    NULL::NUMERIC                                             AS total_incurrido,
    NULL::NUMERIC                                             AS total_incurrido_mes
FROM master_con_pct_mes
-- Conservar:
--   - filas con pct_acumulado > 0 (partida activa en ese mes)
--   - filas con pct_mes != 0 aunque pct_acumulado = 0 (estornos legítimos
--     en partidas no completadas, ej. P5.19.04.01 en obra 0696)
-- Descartar:
--   - filas con pct_acumulado = 0 Y pct_mes = 0 (pre-arranque, sin valor)
-- Sanity check: descartar acumulados extremos > 2.5 (250%) por seguridad
-- ante posibles corrupciones en raw.
WHERE NOT (pct_acumulado = 0 AND pct_mes = 0)
  AND pct_acumulado <= 2.5

UNION ALL

-- ---- reales ----
SELECT
    presupuesto_id, obra_id, partida_id, ambito_id,
    mes_fase_num                                              AS version,
    res_descripcion                                           AS version_descripcion,
    NULL::TEXT                                                AS version_tex,
    NULL::DATE                                                AS version_fec_creacion,
    NULL::DATE                                                AS version_fec_efectiva,
    anio_mes,
    mes_fase_num                                              AS posicion_mes,
    NULL::NUMERIC(18,6)                                       AS pct_acumulado,
    NULL::NUMERIC(18,6)                                       AS pct_mes,
    precio                                                    AS precio_unitario,
    ROUND(cantidad_mes::NUMERIC, 6)                           AS can_mes,
    ROUND(cantidad::NUMERIC, 6)                               AS can_origen,
    ROUND(importe_mes_round::NUMERIC, 2)                      AS importe_mes,
    ROUND(importe_origen_round::NUMERIC, 2)                   AS importe_origen,
    ROUND(importe_mes_raw::NUMERIC, 2)                        AS importe_mes_raw,
    ROUND(importe_origen_raw::NUMERIC, 2)                     AS importe_origen_raw,
    ROUND(total_incurrido_raw::NUMERIC, 2)                    AS total_incurrido,
    ROUND(total_incurrido_mes_calc::NUMERIC, 2)               AS total_incurrido_mes
FROM reales_con_lag;
