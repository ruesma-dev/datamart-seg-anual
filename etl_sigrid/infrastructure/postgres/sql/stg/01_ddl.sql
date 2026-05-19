-- etl_sigrid/infrastructure/postgres/sql/stg/01_ddl.sql
--
-- DDL idempotente de las tablas stg. Se ejecuta en cada build_stg.
-- La primera vez crea las tablas e índices. Las siguientes no hacen nada.
-- Las tablas se llenan después con TRUNCATE + INSERT (ver 03_*..07_*.sql).
--
-- Nota: stg.ambitos NO está aquí: es una VISTA (ver 02_ambitos.sql).

-- ---------------------------------------------------------------------------
-- stg.obras: una fila por obra con código y nombre legibles
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg.obras (
    obra_id      BIGINT       PRIMARY KEY,
    codigo_obra  VARCHAR(24),
    nombre_obra  VARCHAR(255),
    activa       BOOLEAN      NOT NULL DEFAULT TRUE,
    _built_at    TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_obras_codigo ON stg.obras (codigo_obra);


-- ---------------------------------------------------------------------------
-- stg.partidas: una fila por partida de obra (incluye capítulos)
-- ---------------------------------------------------------------------------
-- Sigrid organiza el presupuesto en un árbol: cada partida tiene `padide`
-- apuntando al capítulo padre (puede ser 0 si es raíz). Los capítulos raíz
-- típicos en Ruesma son CD (Costes Directos), CI (Costes Indirectos),
-- CP (Costes Proporcionales).
--
-- Calculamos:
--   - capitulo_raiz_cod : código del capítulo raíz (CD / CI / CP / OTRO)
--   - capitulo_raiz_id  : ide del capítulo raíz
--   - categoria         : CD / CI / CP / OTRO  (derivada del raíz)
--   - ruta_capitulos    : "CD > 01 > 01.02" (legibilidad)
--   - nivel             : profundidad en el árbol (0=raíz, 1, 2...)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg.partidas (
    partida_id         BIGINT       PRIMARY KEY,
    obra_id            BIGINT       NOT NULL,
    codigo_partida     VARCHAR(24),
    capitulo_padre_id  BIGINT,
    descripcion_corta  VARCHAR(128),
    unidad_medida      VARCHAR(16),                -- m3, m2, ud, kg... (obrparpar.unimed)
    capitulo_raiz_id   BIGINT,                     -- ide del capítulo raíz (CD/CI/CP)
    capitulo_raiz_cod  VARCHAR(24),                -- código del raíz: "CD", "CI", "CP", o el que sea
    categoria          VARCHAR(8),                 -- CD / CI / CP / OTRO (normalizado)
    ruta_capitulos     TEXT,                       -- "CD > 01 > 01.02 EXCAVACION VACIADOS"
    nivel              INTEGER,                    -- 0 = raíz, 1, 2...
    activa             BOOLEAN      NOT NULL DEFAULT TRUE,
    _built_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_partidas_obra     ON stg.partidas (obra_id);
CREATE INDEX IF NOT EXISTS idx_partidas_obra_cod ON stg.partidas (obra_id, codigo_partida);


-- ---------------------------------------------------------------------------
-- stg.fases: una fila por fase de obra con fechas tipadas y plazo
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg.fases (
    fase_id        BIGINT       PRIMARY KEY,
    obra_id        BIGINT       NOT NULL,
    numero_fase    INTEGER      NOT NULL,
    fecha_inicio   DATE,
    fecha_fin      DATE,
    plazo_meses    INTEGER,
    anio           INTEGER,                            -- obrfas.ano  (ej: 2025)
    mes            INTEGER,                            -- obrfas.mes  (1..12)
    nombre_mes     VARCHAR(48),                        -- obrfas.res  (ej: "Octubre 2025")
    _built_at      TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_fases_obra_num   ON stg.fases (obra_id, numero_fase);
CREATE INDEX IF NOT EXISTS idx_fases_fecha_fin  ON stg.fases (fecha_fin);


-- ---------------------------------------------------------------------------
-- stg.presupuesto: una fila por (obra × partida × ámbito × fase)
-- Solo con importe efectivo (can * pre <> 0). Importe pre-calculado.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg.presupuesto (
    presupuesto_id  BIGINT           PRIMARY KEY,
    obra_id         BIGINT           NOT NULL,
    partida_id      BIGINT           NOT NULL,
    ambito_id       INTEGER          NOT NULL,
    fase_num        INTEGER          NOT NULL,
    cantidad        NUMERIC(18,4),
    precio          NUMERIC(18,4),
    importe         NUMERIC(18,2),
    _source_tiemod  DOUBLE PRECISION,
    _built_at       TIMESTAMP        NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pres_obra_amb         ON stg.presupuesto (obra_id, ambito_id);
CREATE INDEX IF NOT EXISTS idx_pres_obra_part_amb    ON stg.presupuesto (obra_id, partida_id, ambito_id);
CREATE INDEX IF NOT EXISTS idx_pres_obra_part_amb_fa ON stg.presupuesto (obra_id, partida_id, ambito_id, fase_num);


-- ---------------------------------------------------------------------------
-- stg.version_master_vigente: una fila por obra con su versión "oficial".
--
-- Origen: raw.conext WHERE cod = '15' (campo extendido de Sigrid).
--
-- IMPORTANTE: este campo guarda la versión que el jefe de obra ha marcado
-- como "vigente" para la comparación actual. NO sirve para reconstruir
-- el histórico de seguimiento (donde cada mes se compara contra la
-- versión que estaba activa entonces). Para eso se usa la fecha de
-- creación de cada versión (obrfasamb.fec) y se reconstruye en mart.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg.version_master_vigente (
    obra_id          BIGINT       PRIMARY KEY,
    version_vigente  INTEGER      NOT NULL,
    _built_at        TIMESTAMP    NOT NULL DEFAULT NOW()
);


-- ---------------------------------------------------------------------------
-- stg.plan_mensual: tabla unificada con la distribución mensual de los 4 ámbitos
-- del seguimiento (3 coste real, 7 venta real, 8 master coste, 11 master venta).
--
-- Se alimenta con DOS RAMAS de lógica:
--
-- MASTER (amb 8, 11):
--   - Una fila por (obra × partida × ámbito × VERSIÓN × mes).
--   - Múltiples versiones por obra (fas = 2, 3, 4...) = planif inicial, ABC,
--     Cuatrim 1, Cuatrim 2... Trae TODAS las versiones para que mart pueda
--     reconstruir, mes a mes, contra qué versión se compara cada periodo.
--   - pct_acumulado/pct_mes vienen del split de obrparpre.planif.
--   - version_descripcion = obrfasamb.res ("Versión N (DD/MM/YYYY)").
--   - version_fec_creacion = obrfasamb.fec (cuándo se hizo la versión).
--   - total_incurrido = NULL (no aplica al master).
--
-- REALES (amb 3, 7):
--   - Una fila por (obra × partida × ámbito × MES_FASE).
--   - `version` aquí guarda el número de fase mensual (1=Agosto, 2=Sept...).
--   - version_descripcion = stg.fases.nombre_mes ("Octubre 2025"...).
--   - version_fec_creacion = NULL.
--   - pct_acumulado / pct_mes = NULL (no se explosiona planif).
--   - importe_origen = can*ROUND(pre,2); importe_mes = diff vs cierre anterior.
--   - total_incurrido = obrparpre.totinc (acumulado calculado por Sigrid, ≠ can*pre).
--
-- IMPORTANTE - REDONDEO DEL PRECIO:
--   Sigrid almacena `pre` con 4 decimales (ej: 18.8085) pero internamente
--   redondea a 2 decimales para todos los cálculos visibles en la UI de
--   Seguimiento (18,81). Para que nuestro mart cuadre con Sigrid céntimo
--   a céntimo, guardamos:
--     - importe_mes / importe_origen     : usan can × ROUND(pre, 2). Cuadran con Sigrid.
--     - importe_mes_raw / importe_origen_raw : usan can × pre. Referencia (sin redondeo).
--   El campo precio_unitario se guarda CRUDO (4 decimales) para trazabilidad.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg.plan_mensual (
    plan_id              BIGSERIAL    PRIMARY KEY,
    presupuesto_id       BIGINT       NOT NULL,
    obra_id              BIGINT       NOT NULL,
    partida_id           BIGINT       NOT NULL,
    ambito_id            INTEGER      NOT NULL,
    version              INTEGER      NOT NULL,    -- versión master (8,11) o mes-fase (3,7)
    version_descripcion  TEXT         NULL,        -- res: "Versión 6 (06/03/2026)" | "Octubre 2025"
    version_tex          TEXT         NULL,        -- tex: texto libre JO ("ABC", "PLANIFICACION CUATRIMESTRAL FEB-26"...)
    version_fec_creacion DATE         NULL,        -- solo master (cuándo se generó la versión)
    anio_mes             DATE         NOT NULL,    -- siempre día 1 del mes
    posicion_mes         INTEGER      NOT NULL,    -- master: 1..N en planif; reales: mismo que version
    pct_acumulado        NUMERIC(18,6) NULL,       -- solo master
    pct_mes              NUMERIC(18,6) NULL,       -- solo master
    precio_unitario      NUMERIC(18,4) NOT NULL,           -- pre crudo de obrparpre
    can_mes              NUMERIC(18,4) NOT NULL,
    can_origen           NUMERIC(18,4) NOT NULL,
    importe_mes          NUMERIC(18,2) NOT NULL,           -- can_mes × ROUND(pre, 2) — cuadra con Sigrid
    importe_origen       NUMERIC(18,2) NOT NULL,           -- can_origen × ROUND(pre, 2) — cuadra con Sigrid
    importe_mes_raw      NUMERIC(18,2) NULL,               -- can_mes × pre (sin redondear precio) — referencia
    importe_origen_raw   NUMERIC(18,2) NULL,               -- can_origen × pre (sin redondear precio) — referencia
    total_incurrido      NUMERIC(18,2) NULL,               -- obrparpre.totinc (solo reales) - a origen
    total_incurrido_mes  NUMERIC(18,2) NULL,               -- diff con fase anterior (solo reales) - del mes
    _built_at            TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_plan_mensual_obra_amb        ON stg.plan_mensual (obra_id, ambito_id);
CREATE INDEX IF NOT EXISTS idx_plan_mensual_obra_part_amb_v ON stg.plan_mensual (obra_id, partida_id, ambito_id, version);
CREATE INDEX IF NOT EXISTS idx_plan_mensual_anio_mes        ON stg.plan_mensual (anio_mes);
CREATE INDEX IF NOT EXISTS idx_plan_mensual_presupuesto     ON stg.plan_mensual (presupuesto_id);
