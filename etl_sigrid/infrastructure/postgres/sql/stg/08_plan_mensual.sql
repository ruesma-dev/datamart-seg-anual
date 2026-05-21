-- etl_sigrid/infrastructure/postgres/sql/stg/08_plan_mensual.sql
--
-- Materializa stg.plan_mensual con DOS RAMAS de lógica según el ámbito,
-- escribiendo en el mismo schema de tabla.
--
-- ===========================================================================
-- BRANCH A: MASTER (amb=8 master coste, amb=11 master venta)
-- ===========================================================================
-- En master, `fas` es VERSIÓN del master. Cada versión tiene un planif
-- "v1|v2|...|vN" con porcentajes acumulados por mes a partir de plafec.
-- Mecánica: explosión del planif en filas mensuales.
--
--   obrparpre.fas         = versión (2, 3, 4, ... = ABC, Cuatrim 1, Cuatrim 2...)
--   obrfasamb.plafec      = ancla mes 1 de la planificación
--   obrfasamb.fec         = fecha en que se creó la versión
--   obrfasamb.res         = "Versión N (DD/MM/YYYY)"
--
-- ===========================================================================
-- BRANCH B: REALES (amb=3 coste real, amb=7 venta real)
-- ===========================================================================
-- En reales, `fas` es MES de cierre mensual del seguimiento.
--   fas=0  = "Previsto" (snapshot vivo actual, NO es un cierre histórico → EXCLUIR)
--   fas=1  = primer cierre mensual
--   fas=2  = segundo cierre
--   fas=N  = N-ésimo cierre
--
-- Los nombres del mes ("Octubre 2025", "Enero 2026"...) viven en raw.obrfas
-- (no en obrfasamb, que para reales tiene res vacío o literal genérico).
--   obrfas.fasnum  = mismo número que obrparpre.fas
--   obrfas.res     = "Octubre 2025"
--   obrfas.ano     = 2025
--   obrfas.mes     = 10
--
-- Cálculos:
--   importe_origen = can * pre                    (acumulado a ese cierre)
--   importe_mes    = importe_origen − prev_origen
--                    donde prev_origen = importe_origen de fas=(N-1) si existe,
--                                        0 si no existe (LAG estricto M-1)
--   anio_mes       = make_date(obrfas.ano, obrfas.mes, 1)
--
-- IMPORTANTE — LAG estricto M-1 (Opción B):
--   El LAG no busca "la última fila previa disponible", sino "la fila
--   inmediatamente anterior en numeración de fas".
--   Esto replica el comportamiento de Sigrid en su columna "Importe Parcial",
--   donde un cierre sin fila previa (fas anterior NO existe) se imputa por
--   completo al mes actual en lugar de generar un estorno.
--
--   Caso 1 - cierre consecutivo: fas=8 existe, fas=9 existe
--     → importe_mes(9) = origen(9) - origen(8)  [como antes]
--
--   Caso 2 - estorno con cierre previo: fas=8 con totinc=0, fas=9 con totinc=419
--     → importe_mes(9) = 419 - 0 = 419  [funciona, fas=8 existe aunque sea 0]
--
--   Caso 3 - estorno con cierre previo en 0 (CI.03A.8 obra 0675):
--     fas=1=183, fas=2=0, fas=3=419
--     → importe_mes(2) = 0 - 183 = -183   [estorno legítimo, fas=1 existe]
--     → importe_mes(3) = 419 - 0 = 419    [correcto, fas=2 existe]
--
--   Caso 4 - cierre con HUECO previo (SISTEMA MEDICION obra 0696):
--     fas=3..7=95.20, fas=8 NO EXISTE, fas=9=0
--     → importe_mes(9) = 0 - 0 = 0    [Opción B: fas=8 no existe → prev=0]
--     (antes este caso daba -95.20 porque el LAG saltaba a fas=7)
--
-- NOTA: para reales NO se explosiona planif. La columna planif que aparece
-- en obrparpre amb=3 fas=0 es un eco/prevision; no la usamos.
--
-- IMPORTANTE: en reales, una partida solo aparece en `fas=N` desde el mes
-- en que empieza a tener coste/venta real. Por eso si fas=3 es la primera
-- fila para una partida, importe_mes = importe_origen entero (no había
-- nada antes).

TRUNCATE TABLE stg.plan_mensual;

-- ===========================================================================
-- BRANCH A: MASTER (amb 8, 11) — mismo SQL que la versión anterior
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
        op.planif,
        date_trunc('month', fa.plafec_date)::DATE AS mes_ancla,
        fa.fec_creacion,
        fa.res_descripcion,
        fa.tex_descripcion
    FROM stg.presupuesto pp
    JOIN raw.obrparpre op ON op.ide = pp.presupuesto_id
    JOIN (
        -- Subconsulta: obtenemos los datos de obrfasamb + propagamos `tex` del
        -- master coste (amb=8) al master venta (amb=11) por (obride, fas).
        -- El JO solo rellena `tex` en el master coste, pero el tipo de versión
        -- aplica también al venta del mismo número de versión.
        SELECT
            fa.obride                            AS obra_id,
            fa.amb                               AS ambito_id,
            fa.fas                               AS version_master,
            stg.fn_sigrid_date_to_date(fa.plafec) AS plafec_date,
            stg.fn_sigrid_date_to_date(fa.fec)   AS fec_creacion,
            COALESCE(
                NULLIF(TRIM(fa.res), ''),
                CASE fa.amb
                    WHEN 8  THEN 'Master coste sin descripción'
                    WHEN 11 THEN 'Master venta sin descripción'
                    ELSE NULL
                END
            )                                    AS res_descripcion,
            -- Propagación: si la fila es amb=11 y tex está vacío,
            -- traemos el tex del mismo (obride, fas) en amb=8.
            COALESCE(
                NULLIF(TRIM(fa.tex), ''),
                NULLIF(TRIM(fa_coste.tex), '')
            )                                    AS tex_descripcion
        FROM raw.obrfasamb fa
        LEFT JOIN raw.obrfasamb fa_coste
            ON fa_coste.obride = fa.obride
           AND fa_coste.fas    = fa.fas
           AND fa_coste.amb    = 8
           AND fa.amb          = 11   -- propagación solo aplica para amb=11
        WHERE fa.plafec IS NOT NULL AND fa.plafec > 0
    ) fa
        ON fa.obra_id        = pp.obra_id
       AND fa.ambito_id      = pp.ambito_id
       AND fa.version_master = pp.fase_num
    WHERE pp.ambito_id IN (8, 11)
      AND op.planif IS NOT NULL
      AND length(trim(op.planif)) >= 1
      AND fa.plafec_date IS NOT NULL
),
master_explosion AS (
    SELECT
        pp.presupuesto_id, pp.obra_id, pp.partida_id, pp.ambito_id,
        pp.version_master, pp.cantidad, pp.precio, pp.importe,
        pp.mes_ancla, pp.fec_creacion, pp.res_descripcion, pp.tex_descripcion,
        u.position::INTEGER AS posicion_mes,
        CASE
            WHEN u.valor ~ '^-?\d+([.,]\d+)?$'
                THEN replace(u.valor, ',', '.')::NUMERIC(18,6)
            ELSE NULL
        END AS pct_acumulado
    FROM master_planif pp
    CROSS JOIN LATERAL unnest(string_to_array(pp.planif, '|'))
        WITH ORDINALITY AS u(valor, position)
    WHERE u.valor IS NOT NULL AND length(trim(u.valor)) > 0
),
master_con_pct_mes AS (
    SELECT
        presupuesto_id, obra_id, partida_id, ambito_id, version_master,
        cantidad, precio, importe, mes_ancla, fec_creacion, res_descripcion, tex_descripcion,
        posicion_mes, pct_acumulado,
        pct_acumulado - COALESCE(
            LAG(pct_acumulado) OVER (
                PARTITION BY presupuesto_id ORDER BY posicion_mes
            ),
            0
        ) AS pct_mes
    FROM master_explosion
    WHERE pct_acumulado IS NOT NULL
),

-- ===========================================================================
-- BRANCH B: REALES (amb 3, 7) — sin explosión; una fila por (partida × fas)
-- ===========================================================================
reales_base AS (
    -- Filas reales: una por (paride × fas). Excluimos fas=0 (es el "Previsto"
    -- vivo, no un cierre histórico). JOIN con stg.fases (alimentada desde
    -- obrfas) para obtener nombre del mes, año y mes.
    --
    -- IMPORTANTE: Sigrid usa internamente `pre` redondeado a 2 decimales
    -- para todos los cálculos visibles en la UI. Para que mart cuadre con
    -- Sigrid, calculamos `importe_origen` con ROUND(pre, 2) ("Sigrid-compatible"),
    -- y también `importe_origen_raw` con `pre` crudo (referencia).
    SELECT
        pp.presupuesto_id,
        pp.obra_id,
        pp.partida_id,
        pp.ambito_id,
        pp.fase_num                                AS mes_fase_num,
        pp.cantidad,
        pp.precio,                                                       -- pre crudo (4 dec)
        ROUND(pp.precio::NUMERIC, 2)               AS precio_redondeado,
        -- Importe acumulado con precio redondeado (lo que muestra Sigrid):
        ROUND((pp.cantidad * ROUND(pp.precio::NUMERIC, 2))::NUMERIC, 2)  AS importe_origen_round,
        -- Importe acumulado con precio crudo (referencia):
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
      AND pp.fase_num >= 1          -- excluye fas=0 (Previsto)
      AND f.anio IS NOT NULL
      AND f.mes  IS NOT NULL
),
reales_con_lag AS (
    -- LAG ESTRICTO M-1 (Opción B):
    --
    -- Calculamos LAG(importe_origen) y también LAG(mes_fase_num).
    -- Solo aceptamos el LAG si LAG(mes_fase_num) = mes_fase_num - 1.
    -- Si no, el "valor previo" se considera 0 (no había cierre el mes anterior).
    --
    -- Esto replica el comportamiento de Sigrid en su columna "Importe Parcial":
    -- ante un hueco de cierres, no genera estornos artificiales.
    --
    -- Casos de uso:
    --   fas consecutivos [1,2,3]:     LAG(2)→fas=1, LAG(3)→fas=2  [todo OK]
    --   fas con hueco [1,2,5,9]:
    --     fas=5: LAG(5)→fas=2, pero 2 != 4 → prev=0
    --            ⇒ importe_mes = origen(5) - 0 = origen(5)
    --     fas=9: LAG(9)→fas=5, pero 5 != 8 → prev=0
    --            ⇒ importe_mes = origen(9) - 0 = origen(9)
    --
    -- Cantidad: idéntica lógica.
    SELECT
        presupuesto_id, obra_id, partida_id, ambito_id,
        mes_fase_num,
        cantidad,
        precio,
        precio_redondeado,
        importe_origen_round,
        importe_origen_raw,
        total_incurrido_raw,
        res_descripcion,
        anio_mes,
        -- LAG estricto: solo válido si LAG.mes_fase_num = current.mes_fase_num - 1
        CASE
            WHEN LAG(mes_fase_num) OVER w = mes_fase_num - 1
            THEN cantidad - COALESCE(LAG(cantidad) OVER w, 0)
            ELSE cantidad   -- no había mes previo válido: todo el acumulado a este mes
        END AS cantidad_mes,
        CASE
            WHEN LAG(mes_fase_num) OVER w = mes_fase_num - 1
            THEN importe_origen_round - COALESCE(LAG(importe_origen_round) OVER w, 0)
            ELSE importe_origen_round
        END AS importe_mes_round,
        CASE
            WHEN LAG(mes_fase_num) OVER w = mes_fase_num - 1
            THEN importe_origen_raw - COALESCE(LAG(importe_origen_raw) OVER w, 0)
            ELSE importe_origen_raw
        END AS importe_mes_raw,
        CASE
            WHEN LAG(mes_fase_num) OVER w = mes_fase_num - 1
            THEN total_incurrido_raw - COALESCE(LAG(total_incurrido_raw) OVER w, 0)
            ELSE total_incurrido_raw
        END AS total_incurrido_mes_calc
    FROM reales_base
    WINDOW w AS (
        PARTITION BY obra_id, partida_id, ambito_id
        ORDER BY mes_fase_num
    )
)

-- ===========================================================================
-- INSERT FINAL: unión de las dos ramas con el mismo schema
-- ===========================================================================
INSERT INTO stg.plan_mensual (
    presupuesto_id, obra_id, partida_id, ambito_id,
    version, version_descripcion, version_tex, version_fec_creacion,
    anio_mes, posicion_mes, pct_acumulado, pct_mes,
    precio_unitario, can_mes, can_origen,
    importe_mes, importe_origen,
    importe_mes_raw, importe_origen_raw,
    total_incurrido, total_incurrido_mes
)
-- ---- master ----
-- Cálculos por mes:
--   can_mes        = cantidad × pct_mes
--   can_origen     = cantidad × pct_acumulado
--   importe_mes        = can_mes    × ROUND(precio, 2)  ← Sigrid-compatible
--   importe_origen     = can_origen × ROUND(precio, 2)  ← Sigrid-compatible
--   importe_mes_raw    = can_mes    × precio_crudo      ← referencia
--   importe_origen_raw = can_origen × precio_crudo      ← referencia
SELECT
    presupuesto_id, obra_id, partida_id, ambito_id,
    version_master                                            AS version,
    res_descripcion                                           AS version_descripcion,
    tex_descripcion                                           AS version_tex,
    fec_creacion                                              AS version_fec_creacion,
    (mes_ancla + ((posicion_mes - 1) * INTERVAL '1 month'))::DATE AS anio_mes,
    posicion_mes,
    pct_acumulado,
    pct_mes,
    precio                                                    AS precio_unitario,
    ROUND((cantidad * pct_mes)::NUMERIC, 4)                   AS can_mes,
    ROUND((cantidad * pct_acumulado)::NUMERIC, 4)             AS can_origen,
    -- Versión Sigrid-compatible (precio redondeado a 2 decimales):
    ROUND((cantidad * pct_mes * ROUND(precio::NUMERIC, 2))::NUMERIC, 2)        AS importe_mes,
    ROUND((cantidad * pct_acumulado * ROUND(precio::NUMERIC, 2))::NUMERIC, 2)  AS importe_origen,
    -- Versión raw (precio sin redondear):
    ROUND((cantidad * pct_mes * precio)::NUMERIC, 2)                           AS importe_mes_raw,
    ROUND((cantidad * pct_acumulado * precio)::NUMERIC, 2)                     AS importe_origen_raw,
    NULL::NUMERIC                                             AS total_incurrido,
    NULL::NUMERIC                                             AS total_incurrido_mes
FROM master_con_pct_mes
WHERE pct_acumulado > 0
  AND pct_mes > 0
  AND pct_acumulado <= 1.5

UNION ALL

-- ---- reales ----
SELECT
    presupuesto_id, obra_id, partida_id, ambito_id,
    mes_fase_num                                              AS version,
    res_descripcion                                           AS version_descripcion,
    NULL::TEXT                                                AS version_tex,
    NULL::DATE                                                AS version_fec_creacion,
    anio_mes,
    mes_fase_num                                              AS posicion_mes,
    NULL::NUMERIC(18,6)                                       AS pct_acumulado,
    NULL::NUMERIC(18,6)                                       AS pct_mes,
    precio                                                    AS precio_unitario,
    ROUND(cantidad_mes::NUMERIC, 4)                           AS can_mes,
    ROUND(cantidad::NUMERIC, 4)                               AS can_origen,
    -- Versión Sigrid-compatible (precio redondeado a 2 decimales):
    ROUND(importe_mes_round::NUMERIC, 2)                      AS importe_mes,
    ROUND(importe_origen_round::NUMERIC, 2)                   AS importe_origen,
    -- Versión raw:
    ROUND(importe_mes_raw::NUMERIC, 2)                        AS importe_mes_raw,
    ROUND(importe_origen_raw::NUMERIC, 2)                     AS importe_origen_raw,
    ROUND(total_incurrido_raw::NUMERIC, 2)                    AS total_incurrido,
    ROUND(total_incurrido_mes_calc::NUMERIC, 2)               AS total_incurrido_mes
FROM reales_con_lag;