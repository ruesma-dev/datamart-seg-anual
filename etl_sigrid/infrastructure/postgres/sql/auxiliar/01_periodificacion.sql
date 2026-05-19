-- etl_sigrid/infrastructure/postgres/sql/aux/01_periodificacion.sql
--
-- ===========================================================================
-- ARCHIVO DE REFERENCIA — NO se ejecuta automáticamente por el pipeline.
-- ===========================================================================
-- La tabla aux.periodificacion_partida se crea desde
-- mart/04_view_periodificado.sql (idempotente con IF NOT EXISTS).
--
-- Este archivo está aquí como documentación de la estructura y como plantilla
-- para INSERTs de Negocio. Cuando Negocio defina reglas, ejecutarlo a mano
-- o vía un script auxiliar.

-- aux.periodificacion_partida — reglas de periodificación de costes.
--
-- Cuándo se usa:
--   Algunas partidas (típicamente CI infraestructura: montaje de grúa,
--   instalación de obra, licencias iniciales) tienen un coste que se imputa
--   contablemente en un momento concreto (cuando se factura / monta), pero
--   que ECONÓMICAMENTE aporta valor durante varios meses de la obra.
--
--   El JO suele querer ver la comparativa "real vs planificado" con esa
--   periodificación aplicada (porque tanto el coste real como el master
--   se cargan PUNTUALMENTE en Sigrid, no distribuidos).
--
-- Cómo se usa:
--   - Esta tabla guarda qué partidas se periodifican y cómo.
--   - El mart.v_fact_periodificado aplica las reglas y reescribe la
--     distribución mensual de los importes para esas partidas (tanto
--     Coste Real como Coste Planificado).
--   - El resto (partidas sin regla) van directo, sin tocar.
--
-- Granularidad de la regla:
--   - Si obra_id IS NOT NULL: regla específica para una partida de una obra.
--   - Si obra_id IS NULL pero patron_codigo IS NOT NULL: regla genérica que
--     aplica a TODAS las partidas cuyo código case con el patrón LIKE.
--     Ej: patron_codigo = 'CI.2.%' aplica a CI.2.1, CI.2.2... (instalación obra).
--   - Las reglas específicas (obra+partida) tienen prioridad sobre las
--     genéricas (patrón).
--
-- ESTADO ACTUAL: la tabla se crea VACÍA. Hasta que Negocio defina reglas
-- concretas, ninguna partida se periodifica. Para activar:
--    INSERT INTO aux.periodificacion_partida (...) VALUES (...);
--    python main.py build-mart
--
-- Métodos soportados:
--   LINEAL    : importe / plazo_meses, repetido cada mes durante plazo_meses.
--   AL_FINAL  : todo el importe en el último mes (= no periodificar).
--   FUTURO: S_CURVA, ACELERADA...

CREATE TABLE IF NOT EXISTS aux.periodificacion_partida (
    regla_id           BIGSERIAL    PRIMARY KEY,
    -- Identificación de la regla
    obra_id            BIGINT       NULL,                -- NULL = regla genérica por patrón
    partida_id         BIGINT       NULL,                -- NULL = regla genérica por patrón
    patron_codigo      VARCHAR(64)  NULL,                -- LIKE pattern: 'CI.2.%'
    -- Parámetros de periodificación
    activa             BOOLEAN      NOT NULL DEFAULT TRUE,
    metodo             VARCHAR(16)  NOT NULL,            -- LINEAL / AL_FINAL
    plazo_meses        INTEGER      NULL,                -- nº de meses para LINEAL
    fecha_inicio       DATE         NULL,                -- opcional: forzar inicio en mes concreto
    -- Trazabilidad
    descripcion        TEXT,                             -- por qué se periodifica (opcional)
    creado_por         VARCHAR(64)  NOT NULL DEFAULT current_user,
    _built_at          TIMESTAMP    NOT NULL DEFAULT NOW(),

    -- Una regla específica (obra+partida) o una genérica (patrón) —
    -- no puede ser las dos a la vez:
    CONSTRAINT chk_regla_tipo CHECK (
        (obra_id IS NOT NULL AND partida_id IS NOT NULL AND patron_codigo IS NULL)
        OR
        (obra_id IS NULL AND partida_id IS NULL AND patron_codigo IS NOT NULL)
    ),
    -- LINEAL requiere plazo:
    CONSTRAINT chk_lineal_plazo CHECK (
        (metodo = 'LINEAL' AND plazo_meses IS NOT NULL AND plazo_meses > 0)
        OR
        (metodo <> 'LINEAL')
    )
);
CREATE INDEX IF NOT EXISTS idx_per_partida ON aux.periodificacion_partida (obra_id, partida_id) WHERE obra_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_per_patron  ON aux.periodificacion_partida (patron_codigo) WHERE patron_codigo IS NOT NULL;

-- ============================================================================
-- EJEMPLO de regla (comentado; descomentar y ajustar cuando Negocio defina):
-- ============================================================================
--
-- INSERT INTO aux.periodificacion_partida (patron_codigo, metodo, plazo_meses, descripcion)
-- VALUES
--   ('CI.2.%',     'LINEAL', 12, 'Instalación de obra: amortizar en 12 meses'),
--   ('CI.1.16',    'LINEAL', 24, 'Técnico prevención: contrato anual periodificado');
