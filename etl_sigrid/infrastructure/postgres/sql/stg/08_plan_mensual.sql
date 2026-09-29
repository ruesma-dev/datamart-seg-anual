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
-- EL MES DE UN CIERRE REAL LO DA SU TEXTO (F-051, absorbida en F-118)
--
-- `anio_mes` de cada fila real es `stg.fn_mes_de_fase` sobre la fase: manda el
-- texto que escribe el jefe de obra («Agosto 2026», «Enero 2020-Abril 2020» →
-- abril); si no se lee, la fecha fin, la de inicio y el `ano`/`mes` archivado,
-- por ese orden (decisión del humano del 2026-09-22). `mart` y `cierre` leen
-- este mes sin recalcularlo, así que las tres capas coinciden por construcción.
--
-- UN SOLO CIERRE POR MES (F-042, decisión de Negocio del 2026-08-28), sobre el
-- mes del texto: si dos fases de una obra y ámbito caen en el mismo mes, manda
-- la de mayor `mes_fase_num` ENTRE LAS QUE NO TIENEN EL ACUMULADO A CERO. El
-- matiz del cero no es cosmético: la obra 0606 PUY DU FOU tiene su fase 16 de
-- feb-2021 entera a cero y quedarse con ella publicaría 0 € donde hay
-- 9.053.263,61 € buenos en la fase 14. La perdedora sigue en `raw` y en
-- `stg.fases`; lo que no tiene es fila en `plan_mensual`.
--
-- RELLENO (F-051): una fase de RANGO (mes de su fecha fin posterior al de su
-- fecha de inicio) cuyo texto cae después de su primer mes lleva todo el
-- dinero al mes del texto, y los meses desde el de inicio hasta el anterior al
-- del texto reciben filas de relleno: movimiento 0 y el acumulado del cierre
-- anterior. Nunca en un mes con cierre vigente propio, nunca después del mes del
-- texto, y un mes que quieren dos fases lo rellena la que cierra antes.
--
-- LA SERIE REAL ES DENSA (F-118): `importe_mes` es el acumulado del mes menos
-- el del mes anterior DE LA SERIE DE LA PARTIDA, y esa serie no tiene huecos.
-- Antes solo se restaba si la fila anterior era de la fase consecutiva y, si
-- no, se publicaba el acumulado entero; eso rompía dos casos:
--   - la partida que DESAPARECE de un cierre (correo de Juan Romero del
--     2026-09-29): la 0709, partida 417031, tenía −58.000 en julio, ninguna
--     fila en agosto y 0 en septiembre; agosto salía 319.492,30 € donde el
--     cierre da 377.492,30 €;
--   - el número de fase que Sigrid SE SALTA (F-103, absorbida): la 0371 pasa de
--     la f27 a la f29 y la f29 publicaba +4.293.905,89 € en vez de −441.229,31.
-- Ahora, desde el alta de la partida, cada mes del ámbito tiene su valor. En un
-- cierre, la fila de Sigrid o, si ya no está, acumulado 0: la partida se
-- DESHACE (se anula el acumulado anterior) en una fila marcada `es_deshacer`, y
-- si vuelve se calcula contra ese 0. En un relleno, el acumulado anterior. Una
-- fase de la obra sin ninguna fila de ese ámbito no es cierre de ese ámbito y
-- no deshace nada (Sigrid no abrió esa fase de venta en 11 obras de 2010-2020).
-- La suma de `importe_mes` de cada partida es así el acumulado del último cierre
-- del ámbito, sin excepciones (R21), que es lo que ya calcula `cierre`.
--
-- `version` sigue siendo el número ORIGINAL de la fase de Sigrid (la generadora
-- en el relleno, la del cierre donde falta en el deshacer): seis JOIN de
-- `cierre/` cruzan `pm.version` contra `stg.fases.numero_fase`.
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
-- una lista que EMPIEZA por obra_id: (obra_id, partida_id, ambito_id, ...) en
-- la serie de los reales. Los `DISTINCT ON` y el `NOT EXISTS` del relleno
-- también son por (obra, ámbito). Por eso el resultado por tramos es, por
-- construcción, idéntico al de una pasada única, sin marcador nuevo. Quien
-- añada una ventana a este fichero tiene que respetar la misma condición: lo
-- comprueba `tests/test_f042_sql.py::test_f042_ninguna_ventana_del_fichero_cruza_obras`,
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
        f.fecha_inicio,
        f.fecha_fin,
        f.nombre_mes,
        f.anio,
        f.mes
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
-- Una fila por (obra, ámbito, fase): miles, no millones. Aquí se decide el mes,
-- una llamada por fase y no por partida. `COALESCE` porque una fase sin ningún
-- importe daría SUM = NULL, y `NULL <> 0` no es cierto: en el ORDER BY de
-- `reales_vigente` los nulos van PRIMERO y esa fase sin dato ganaría el mes.
reales_cierres AS (
    SELECT
        f.obra_id, f.ambito_id, f.mes_fase_num, f.acumulado,
        f.nombre_mes                               AS res_descripcion,
        stg.fn_mes_de_fase(f.fecha_inicio, f.nombre_mes, f.fecha_fin,
                           make_date(f.anio, f.mes, 1)) AS anio_mes,
        date_trunc('month', f.fecha_inicio)::DATE  AS mes_ini_fase,
        COALESCE(date_trunc('month', f.fecha_fin)
                 > date_trunc('month', f.fecha_inicio), FALSE) AS es_rango
    FROM (
        SELECT obra_id, ambito_id, mes_fase_num,
               fecha_inicio, fecha_fin, nombre_mes, anio, mes,
               COALESCE(SUM(importe_origen_round), 0) AS acumulado
        FROM reales_base
        GROUP BY obra_id, ambito_id, mes_fase_num,
                 fecha_inicio, fecha_fin, nombre_mes, anio, mes
    ) f
),
-- F-042 sobre el mes del texto (R8): manda el más moderno DE ENTRE LOS QUE NO
-- ESTÁN A CERO. El orden de las dos claves ES la regla: invertirlas deja a PUY
-- DU FOU publicando 0 € en feb-2021. Si todos los del mes están a cero, gana el
-- mayor, que es lo que hace el segundo criterio cuando el primero empata.
reales_vigente AS (
    SELECT DISTINCT ON (obra_id, ambito_id, anio_mes)
           obra_id, ambito_id, anio_mes, mes_fase_num,
           res_descripcion, mes_ini_fase, es_rango
    FROM reales_cierres
    WHERE anio_mes IS NOT NULL
    ORDER BY obra_id, ambito_id, anio_mes,
             (acumulado <> 0) DESC, mes_fase_num DESC
),
-- Los meses de relleno (F-051 R10, R11, R14): de cada fase vigente de rango,
-- desde su primer mes hasta el anterior al del texto, sin pisar un mes con
-- cierre vigente propio. Si dos fases quieren el mismo mes, lo rellena la de
-- mes del texto más cercano (la que cierra antes): un mes, una fila.
reales_relleno AS (
    SELECT DISTINCT ON (v.obra_id, v.ambito_id, gs.mes)
           v.obra_id, v.ambito_id, gs.mes::DATE AS anio_mes,
           v.anio_mes AS mes_generador, v.mes_fase_num, v.res_descripcion
    FROM reales_vigente v
    CROSS JOIN LATERAL generate_series(
        v.mes_ini_fase::TIMESTAMP,
        (v.anio_mes - INTERVAL '1 month')::TIMESTAMP,
        INTERVAL '1 month'
    ) AS gs(mes)
    WHERE v.es_rango
      AND v.anio_mes > v.mes_ini_fase
      AND NOT EXISTS (
          SELECT 1 FROM reales_vigente o
          WHERE o.obra_id   = v.obra_id
            AND o.ambito_id = v.ambito_id
            AND o.anio_mes  = gs.mes::DATE
      )
    ORDER BY v.obra_id, v.ambito_id, gs.mes, v.anio_mes
),
-- Los meses de cada (obra, ámbito): sus cierres vigentes y sus meses de
-- relleno. Una fase sin filas del ámbito no está aquí (R34): no es cierre de
-- ese ámbito. `mes_generador` es el mes del cierre que genera el relleno (el
-- propio mes en un cierre).
reales_meses AS (
    SELECT obra_id, ambito_id, anio_mes, anio_mes AS mes_generador,
           mes_fase_num, res_descripcion, FALSE AS es_relleno
    FROM reales_vigente
    UNION ALL
    SELECT obra_id, ambito_id, anio_mes, mes_generador,
           mes_fase_num, res_descripcion, TRUE
    FROM reales_relleno
),
-- Cada cierre vigente con el primer mes que genera: el suyo o el primero de su
-- relleno. Es el alta de una partida que nace en él (D3 de F-051).
reales_vigente_alta AS (
    SELECT obra_id, ambito_id, mes_fase_num, mes_generador AS anio_mes,
           MIN(anio_mes) AS mes_alta_cierre
    FROM reales_meses
    GROUP BY obra_id, ambito_id, mes_fase_num, mes_generador
),
-- Las filas de Sigrid de los cierres que viven, ya en el mes de su texto.
reales_filas AS (
    SELECT b.presupuesto_id, b.obra_id, b.partida_id, b.ambito_id, v.anio_mes,
           v.mes_alta_cierre,
           b.cantidad, b.precio,
           b.importe_origen_round, b.importe_origen_raw, b.total_incurrido_raw
    FROM reales_base b
    JOIN reales_vigente_alta v
        ON v.obra_id      = b.obra_id
       AND v.ambito_id    = b.ambito_id
       AND v.mes_fase_num = b.mes_fase_num
),
-- El alta de cada partida: su primer cierre con fila de Sigrid o, si nace en
-- una fase de rango, el primer mes de su relleno. Sin JOIN: sale de las filas.
reales_alta AS (
    SELECT obra_id, ambito_id, partida_id, MIN(mes_alta_cierre) AS mes_alta
    FROM reales_filas
    GROUP BY obra_id, ambito_id, partida_id
),
-- La rejilla: cada partida en cada mes de su (obra, ámbito) desde su alta.
-- Es un JOIN entre dos conjuntos pequeños (partidas y meses del tramo).
reales_rejilla AS (
    SELECT a.obra_id, a.ambito_id, a.partida_id,
           m.anio_mes, m.mes_generador, m.mes_fase_num, m.res_descripcion,
           m.es_relleno
    FROM reales_alta a
    JOIN reales_meses m
        ON m.obra_id   = a.obra_id
       AND m.ambito_id = a.ambito_id
       AND m.anio_mes >= a.mes_alta
),
-- La serie sin huecos: la rejilla con la fila de Sigrid de cada mes cuando la
-- hay. Se une con UNION ALL y GROUP BY, no con un LEFT JOIN: el optimizador no
-- tiene estadísticas de estas CTE y un JOIN mal estimado se convertía en un
-- bucle anidado sobre millones de filas (medido en local: 28 s para 11.000).
reales_esqueleto AS (
    SELECT obra_id, ambito_id, partida_id, anio_mes,
           MAX(mes_generador)                    AS mes_generador,
           MAX(mes_fase_num)                     AS mes_fase_num,
           MAX(res_descripcion)                  AS res_descripcion,
           bool_or(es_relleno)                   AS es_relleno,
           (COUNT(presupuesto_id) > 0)           AS tiene_fila,
           MAX(presupuesto_id)                   AS presupuesto_id,
           MAX(precio)                           AS precio,
           MAX(cantidad)                         AS cantidad,
           MAX(importe_origen_round)             AS importe_origen_round,
           MAX(importe_origen_raw)               AS importe_origen_raw,
           MAX(total_incurrido_raw)              AS total_incurrido_raw
    FROM (
        SELECT obra_id, ambito_id, partida_id, anio_mes,
               mes_generador, mes_fase_num, res_descripcion, es_relleno,
               NULL::BIGINT AS presupuesto_id, NULL::NUMERIC AS precio,
               NULL::NUMERIC AS cantidad, NULL::NUMERIC AS importe_origen_round,
               NULL::NUMERIC AS importe_origen_raw, NULL::NUMERIC AS total_incurrido_raw
        FROM reales_rejilla
        UNION ALL
        SELECT obra_id, ambito_id, partida_id, anio_mes,
               NULL::DATE, NULL::INTEGER, NULL::TEXT, NULL::BOOLEAN,
               presupuesto_id, precio,
               cantidad, importe_origen_round,
               importe_origen_raw, total_incurrido_raw
        FROM reales_filas
    ) u
    GROUP BY obra_id, ambito_id, partida_id, anio_mes
),
-- El acumulado de cada hueco, primera mitad. En un cierre: la fila de Sigrid
-- o, si la partida ya no está, 0 (se deshace, R29-R30). En un relleno, NULL
-- aquí y el arrastre abajo. `grupo_cierre` numera los cierres de la serie:
-- cada relleno comparte grupo con el último cierre anterior (el truco de la
-- rama master, `COUNT(x) OVER` + `MAX() OVER (..., grupo)`), y el grupo 0 son
-- los rellenos anteriores a todo cierre de la partida. `grupo_fila` hace lo
-- mismo con las filas de Sigrid, para dar al deshacer la última de ellas (R31).
reales_grupos AS (
    SELECT
        obra_id, ambito_id, partida_id, anio_mes, mes_generador,
        mes_fase_num, res_descripcion, es_relleno, tiene_fila,
        presupuesto_id, precio,
        CASE WHEN es_relleno THEN NULL WHEN tiene_fila THEN importe_origen_round ELSE 0 END
            AS c_importe_origen_round,
        CASE WHEN es_relleno THEN NULL WHEN tiene_fila THEN importe_origen_raw ELSE 0 END
            AS c_importe_origen_raw,
        CASE WHEN es_relleno THEN NULL WHEN tiene_fila THEN cantidad ELSE 0 END
            AS c_cantidad,
        CASE WHEN es_relleno THEN NULL WHEN tiene_fila THEN total_incurrido_raw ELSE 0 END
            AS c_total_incurrido_raw,
        COUNT(CASE WHEN NOT es_relleno THEN 1 END) OVER w AS grupo_cierre,
        COUNT(presupuesto_id) OVER w                      AS grupo_fila
    FROM reales_esqueleto
    WINDOW w AS (PARTITION BY obra_id, partida_id, ambito_id ORDER BY anio_mes ROWS UNBOUNDED PRECEDING)
),
-- El acumulado de cada hueco, segunda mitad: el relleno arrastra el del último
-- cierre, ya deshecho si lo estaba (R33); sin cierre anterior, 0 (F-051 R12).
reales_serie AS (
    SELECT
        obra_id, ambito_id, partida_id, anio_mes, mes_generador,
        mes_fase_num, res_descripcion, es_relleno, tiene_fila,
        presupuesto_id, precio,
        CASE WHEN NOT es_relleno THEN c_importe_origen_round
             WHEN grupo_cierre = 0 THEN 0
             ELSE MAX(c_importe_origen_round) OVER g END  AS importe_origen_round,
        CASE WHEN NOT es_relleno THEN c_importe_origen_raw
             WHEN grupo_cierre = 0 THEN 0
             ELSE MAX(c_importe_origen_raw) OVER g END    AS importe_origen_raw,
        CASE WHEN NOT es_relleno THEN c_cantidad
             WHEN grupo_cierre = 0 THEN 0
             ELSE MAX(c_cantidad) OVER g END              AS cantidad,
        CASE WHEN NOT es_relleno THEN c_total_incurrido_raw
             WHEN grupo_cierre = 0 THEN 0
             ELSE MAX(c_total_incurrido_raw) OVER g END   AS total_incurrido_raw,
        MAX(presupuesto_id) OVER f                         AS presupuesto_previo,
        MAX(precio) OVER f                                 AS precio_previo
    FROM reales_grupos
    WINDOW g AS (PARTITION BY obra_id, partida_id, ambito_id, grupo_cierre),
           f AS (PARTITION BY obra_id, partida_id, ambito_id, grupo_fila)
),
-- El movimiento (R9): diferencia con el mes anterior DE LA SERIE, que ya no
-- tiene huecos. El primero, el acumulado entero. Sin comprobar si la fase
-- anterior es la consecutiva: esa comprobación era el defecto.
reales_con_lag AS (
    SELECT
        obra_id, ambito_id, partida_id, anio_mes, mes_generador,
        mes_fase_num, res_descripcion, es_relleno, tiene_fila,
        presupuesto_id, precio, presupuesto_previo, precio_previo,
        importe_origen_round, importe_origen_raw, cantidad, total_incurrido_raw,
        cantidad - COALESCE(LAG(cantidad) OVER w, 0)                         AS cantidad_mes,
        importe_origen_round - COALESCE(LAG(importe_origen_round) OVER w, 0) AS importe_mes_round,
        importe_origen_raw - COALESCE(LAG(importe_origen_raw) OVER w, 0)     AS importe_mes_raw,
        total_incurrido_raw - COALESCE(LAG(total_incurrido_raw) OVER w, 0)   AS total_incurrido_mes_calc
    FROM reales_serie
    WINDOW w AS (
        PARTITION BY obra_id, partida_id, ambito_id
        ORDER BY anio_mes
    )
),
-- Lo que la partida mueve con fila de Sigrid en el cierre que genera cada
-- relleno (D3 de F-051; un deshacer ahí no cuenta: la partida no está en esa
-- fase) y esa fila, que da presupuesto y precio al relleno.
reales_generador AS (
    SELECT
        l.*,
        MAX(CASE WHEN tiene_fila THEN importe_mes_round END) OVER gen     AS mov_generador,
        MAX(CASE WHEN tiene_fila THEN presupuesto_id END) OVER gen        AS presupuesto_generador,
        MAX(CASE WHEN tiene_fila THEN precio END) OVER gen                AS precio_generador
    FROM reales_con_lag l
    WINDOW gen AS (PARTITION BY obra_id, partida_id, ambito_id, mes_generador)
),
-- Lo que se publica: (a) las filas de Sigrid; (b) el relleno cuyo acumulado
-- no es 0 o que se mueve con fila en su fase generadora (D3); (c) el
-- cierre sin fila que mueve algo: la fila de deshacer, una sola (R29, R32). Lo
-- que se descarta tiene movimiento 0, así que la suma no cambia (R21).
reales_final AS (
    SELECT
        CASE WHEN es_relleno THEN COALESCE(presupuesto_generador, presupuesto_previo)
             ELSE presupuesto_previo END           AS presupuesto_id,
        obra_id, partida_id, ambito_id,
        mes_fase_num,
        res_descripcion,
        anio_mes,
        CASE WHEN es_relleno THEN COALESCE(precio_generador, precio_previo)
             ELSE precio_previo END                AS precio,
        cantidad,
        cantidad_mes,
        importe_origen_round,
        importe_mes_round,
        importe_origen_raw,
        importe_mes_raw,
        total_incurrido_raw,
        total_incurrido_mes_calc,
        es_relleno,
        (NOT es_relleno AND NOT tiene_fila)        AS es_deshacer
    FROM reales_generador
    WHERE tiene_fila
       OR (es_relleno AND (importe_origen_round <> 0 OR COALESCE(mov_generador, 0) <> 0))
       OR (NOT es_relleno AND NOT tiene_fila AND (
               importe_mes_round <> 0 OR importe_mes_raw <> 0
            OR cantidad_mes <> 0 OR total_incurrido_mes_calc <> 0))
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
    total_incurrido, total_incurrido_mes,
    es_relleno, es_deshacer
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
    NULL::NUMERIC                                             AS total_incurrido_mes,
    NULL::BOOLEAN                                             AS es_relleno,
    NULL::BOOLEAN                                             AS es_deshacer
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
    ROUND(total_incurrido_mes_calc::NUMERIC, 2)               AS total_incurrido_mes,
    es_relleno,
    es_deshacer
FROM reales_final;
