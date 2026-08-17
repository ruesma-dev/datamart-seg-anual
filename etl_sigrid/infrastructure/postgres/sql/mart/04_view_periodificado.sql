-- etl_sigrid/infrastructure/postgres/sql/mart/04_view_periodificado.sql
--
-- mart.v_fact_periodificado — vista derivada de mart.fact_seguimiento_mensual
-- que aplica las reglas de aux.periodificacion_partida.
--
-- (ver detalle del algoritmo más abajo)

-- ============================================================================
-- PASO 0: asegurar que la tabla aux.periodificacion_partida existe.
-- ============================================================================
-- Se ejecuta en este SQL (idempotente) para no obligar a un paso aparte. Si
-- la tabla ya existe, IF NOT EXISTS la respeta sin tocar datos.

CREATE TABLE IF NOT EXISTS aux.periodificacion_partida (
    regla_id           BIGSERIAL    PRIMARY KEY,
    obra_id            BIGINT       NULL,
    partida_id         BIGINT       NULL,
    patron_codigo      VARCHAR(64)  NULL,
    activa             BOOLEAN      NOT NULL DEFAULT TRUE,
    metodo             VARCHAR(16)  NOT NULL,
    plazo_meses        INTEGER      NULL,
    fecha_inicio       DATE         NULL,
    descripcion        TEXT,
    creado_por         VARCHAR(64)  NOT NULL DEFAULT current_user,
    _built_at          TIMESTAMP    NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_regla_tipo CHECK (
        (obra_id IS NOT NULL AND partida_id IS NOT NULL AND patron_codigo IS NULL)
        OR
        (obra_id IS NULL AND partida_id IS NULL AND patron_codigo IS NOT NULL)
    ),
    CONSTRAINT chk_lineal_plazo CHECK (
        (metodo = 'LINEAL' AND plazo_meses IS NOT NULL AND plazo_meses > 0)
        OR
        (metodo <> 'LINEAL')
    )
);
CREATE INDEX IF NOT EXISTS idx_per_partida
    ON aux.periodificacion_partida (obra_id, partida_id)
    WHERE obra_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_per_patron
    ON aux.periodificacion_partida (patron_codigo)
    WHERE patron_codigo IS NOT NULL;

-- ============================================================================
-- ALGORITMO DE LA VISTA

DROP VIEW IF EXISTS mart.v_fact_periodificado;

CREATE VIEW mart.v_fact_periodificado AS
WITH
-- Paso 1: para cada fila del fact, resolver qué regla aplica (específica > patrón).
reglas_resueltas AS (
    SELECT
        f.fact_id,
        f.obra_id, f.partida_id, f.codigo_partida, f.escenario, f.concepto,
        f.anio_mes, f.importe_mes, f.importe_origen,
        f.importe_mes_raw, f.importe_origen_raw,
        -- Buscar regla específica primero
        COALESCE(
            (SELECT pp.regla_id
               FROM aux.periodificacion_partida pp
              WHERE pp.activa = TRUE
                AND pp.obra_id = f.obra_id
                AND pp.partida_id = f.partida_id
              LIMIT 1),
            (SELECT pp.regla_id
               FROM aux.periodificacion_partida pp
              WHERE pp.activa = TRUE
                AND pp.patron_codigo IS NOT NULL
                AND f.codigo_partida LIKE pp.patron_codigo
              ORDER BY length(pp.patron_codigo) DESC   -- patrón más específico gana
              LIMIT 1)
        ) AS regla_id
    FROM mart.fact_seguimiento_mensual f
    -- Solo periodificamos costes. La venta pasa siempre directa.
    WHERE f.concepto = 'COSTE'
       OR f.concepto IS NULL
),
-- Paso 2: filas SIN regla → pasan tal cual.
sin_regla AS (
    SELECT
        f.*,
        NULL::BIGINT AS regla_id_aplicada
    FROM mart.fact_seguimiento_mensual f
    LEFT JOIN reglas_resueltas r ON r.fact_id = f.fact_id
    WHERE r.regla_id IS NULL
       OR f.concepto = 'VENTA'           -- venta nunca se periodifica
),
-- Paso 3: filas CON regla → calculamos el importe total a periodificar
-- por (obra, partida, escenario) y lo distribuimos.
con_regla_total AS (
    SELECT
        r.obra_id, r.partida_id, r.escenario,
        r.regla_id,
        pp.metodo, pp.plazo_meses, pp.fecha_inicio,
        SUM(r.importe_mes)        AS importe_total_mes,
        SUM(r.importe_mes_raw)    AS importe_total_mes_raw,
        MIN(r.anio_mes)           AS primer_mes_real,
        -- Tomamos cualquier fila de las que tienen regla para reutilizar metadatos.
        -- (Pendiente: si hay matching parcial entre meses con y sin regla, refinar).
        MAX(r.importe_origen)     AS dummy_origen
    FROM reglas_resueltas r
    JOIN aux.periodificacion_partida pp ON pp.regla_id = r.regla_id
    WHERE r.regla_id IS NOT NULL
    GROUP BY r.obra_id, r.partida_id, r.escenario, r.regla_id,
             pp.metodo, pp.plazo_meses, pp.fecha_inicio
),
-- Paso 4: explosión mensual del importe total según el método.
con_regla_explotado AS (
    SELECT
        crt.obra_id,
        crt.partida_id,
        crt.escenario,
        crt.regla_id,
        (COALESCE(crt.fecha_inicio, crt.primer_mes_real)
            + (gs.idx * INTERVAL '1 month'))::DATE AS anio_mes,
        -- LINEAL: total / plazo
        CASE
            WHEN crt.metodo = 'LINEAL'
                THEN ROUND((crt.importe_total_mes / crt.plazo_meses)::NUMERIC, 2)
            ELSE crt.importe_total_mes
        END AS importe_mes_periodificado,
        CASE
            WHEN crt.metodo = 'LINEAL'
                THEN ROUND((crt.importe_total_mes_raw / crt.plazo_meses)::NUMERIC, 2)
            ELSE crt.importe_total_mes_raw
        END AS importe_mes_raw_periodificado
    FROM con_regla_total crt
    CROSS JOIN generate_series(0, COALESCE(crt.plazo_meses, 1) - 1) AS gs(idx)
)
-- Paso 5: unimos filas sin regla + explotadas con regla, reconstruyendo el
-- schema completo. Para las filas explotadas, recogemos metadata de la fila
-- "modelo" (la primera fila del periodo original) y sustituimos los importes.
SELECT
    -- columnas pass-through
    fact_id, obra_id, codigo_obra, nombre_obra,
    partida_id, codigo_partida, descripcion_partida, unidad_medida,
    categoria, capitulo_raiz_cod, ruta_capitulos,
    anio_mes, anio, mes, nombre_mes,
    escenario, tipo_dato, concepto, ambito_id,
    importe_mes, importe_origen, importe_mes_raw, importe_origen_raw,
    can_mes, can_origen, precio_unitario,
    version_master, version_descripcion, version_tex, version_fec_creacion,
    tipo_master, total_incurrido, total_incurrido_mes,
    regla_id_aplicada,
    'NO_PERIODIFICADO'::TEXT AS marca
FROM sin_regla

UNION ALL

-- Filas explotadas (CON regla)
SELECT
    NULL::BIGINT                       AS fact_id,    -- es derivado, no real
    cre.obra_id,
    MAX(modelo.codigo_obra)             AS codigo_obra,
    MAX(modelo.nombre_obra)             AS nombre_obra,
    cre.partida_id,
    MAX(modelo.codigo_partida)          AS codigo_partida,
    MAX(modelo.descripcion_partida)     AS descripcion_partida,
    MAX(modelo.unidad_medida)           AS unidad_medida,
    MAX(modelo.categoria)               AS categoria,
    MAX(modelo.capitulo_raiz_cod)       AS capitulo_raiz_cod,
    MAX(modelo.ruta_capitulos)          AS ruta_capitulos,
    cre.anio_mes,
    EXTRACT(YEAR  FROM cre.anio_mes)::INT AS anio,
    EXTRACT(MONTH FROM cre.anio_mes)::INT AS mes,
    -- Nombre del mes SIN locale: no puede depender de lc_time del servidor.
    (ARRAY['Enero','Febrero','Marzo','Abril','Mayo','Junio',
           'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'])
          [EXTRACT(MONTH FROM cre.anio_mes)::INT]
        || ' ' || EXTRACT(YEAR FROM cre.anio_mes)::INT AS nombre_mes,
    cre.escenario,
    MAX(modelo.tipo_dato)               AS tipo_dato,
    MAX(modelo.concepto)                AS concepto,
    MAX(modelo.ambito_id)               AS ambito_id,
    cre.importe_mes_periodificado       AS importe_mes,
    -- a origen periodificado: acumular periodos hasta este mes.
    -- Lo simplificamos calculándolo en consumo (Power BI puede acumular).
    cre.importe_mes_periodificado       AS importe_origen,
    cre.importe_mes_raw_periodificado   AS importe_mes_raw,
    cre.importe_mes_raw_periodificado   AS importe_origen_raw,
    NULL::NUMERIC(18,4)                 AS can_mes,
    NULL::NUMERIC(18,4)                 AS can_origen,
    MAX(modelo.precio_unitario)         AS precio_unitario,
    MAX(modelo.version_master)          AS version_master,
    MAX(modelo.version_descripcion)     AS version_descripcion,
    MAX(modelo.version_tex)             AS version_tex,
    MAX(modelo.version_fec_creacion)    AS version_fec_creacion,
    MAX(modelo.tipo_master)             AS tipo_master,
    NULL::NUMERIC(18,2)                 AS total_incurrido,
    NULL::NUMERIC(18,2)                 AS total_incurrido_mes,
    cre.regla_id                        AS regla_id_aplicada,
    'PERIODIFICADO'::TEXT               AS marca
FROM con_regla_explotado cre
-- Modelo: cualquier fila del fact con esta (obra, partida, escenario) sirve
-- para los metadatos. Usamos LATERAL para coger una (la primera por mes).
LEFT JOIN LATERAL (
    SELECT *
    FROM mart.fact_seguimiento_mensual ff
    WHERE ff.obra_id    = cre.obra_id
      AND ff.partida_id = cre.partida_id
      AND ff.escenario  = cre.escenario
    ORDER BY ff.anio_mes
    LIMIT 1
) modelo ON TRUE
GROUP BY cre.obra_id, cre.partida_id, cre.escenario,
         cre.anio_mes, cre.importe_mes_periodificado,
         cre.importe_mes_raw_periodificado, cre.regla_id;
