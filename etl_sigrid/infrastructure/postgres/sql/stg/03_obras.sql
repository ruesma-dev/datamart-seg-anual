-- etl_sigrid/infrastructure/postgres/sql/stg/03_obras.sql
--
-- Materializa stg.obras combinando raw.obr con raw.con, deduplicando por
-- el mecanismo de Sigrid `conext.cod='15'` y filtrando códigos no válidos.
--
-- ===========================================================================
-- Modelo Sigrid
-- ===========================================================================
-- La tabla `obr` hereda de `con` con relación 1:1, igual que `obrx`, `dca`,
-- `dvf` y otras tablas marcadas como "Propiedades de con 1:1" en el
-- autodocumentador. Esto significa que `obr.ide = con.ide`: la obra ES un
-- concepto. Los campos del concepto (cod, res) viven en con; los específicos
-- de obra (centro de coste, fechas) viven en obr.
--
-- Por tanto:
--   - El JOIN es por `con.ide = obr.ide` (NO `obr.cenide`, que es el centro
--     de coste, otra cosa distinta).
--   - El campo del nombre legible es `con.res` (Resumen, varchar). En Sigrid
--     no hay columna llamada `nom`; el patrón estándar es `cod` (código) y
--     `res` (descripción corta/resumen).
--
-- ===========================================================================
-- FILTROS APLICADOS
-- ===========================================================================
--
-- 1) Códigos administrativos EXCLUIDOS.
--    Son "papeleras" de Sigrid (centros de personal, gastos generales, etc.),
--    no obras reales del negocio. Lista cerrada y revisada:
--      0001-0005, CM, CP, GG, VAR, POSTV*, BD*, GGD, GINT, OT
--
-- 2) Códigos con secuencia numérica de 5+ dígitos EXCLUIDOS.
--    Convención de Ruesma: el número de obra es de 4 dígitos. Sufijos
--    alfabéticos o separadores son válidos (0675, 0675B, 0675-B), pero
--    códigos como 02586A o 065879 son errores de captura o legacy mal
--    catalogado y no deben entrar al mart.
--    Regex aplicada: `con.cod !~ '[0-9]{5,}'` (no debe contener 5+
--    dígitos consecutivos en ninguna posición del código).
--
--    Casos:
--      '0675'      → OK (4 dígitos)
--      '0675B'     → OK (4 dígitos + letra)
--      '0675-B'    → OK (separador)
--      '0675/2'    → OK (4 dígitos + 1 dígito tras separador)
--      '02586A'    → FUERA (5 dígitos)
--      '065879'    → FUERA (6 dígitos)
--      '12345-9'   → FUERA (5 dígitos)
--
-- ===========================================================================
-- DEDUPLICACIÓN POR conext.cod='15'
-- ===========================================================================
-- En Sigrid puede haber múltiples ide para el mismo cod de obra (53 códigos
-- duplicados detectados en Ruesma). El mecanismo de Sigrid para marcar cuál
-- es la vigente es la tabla raw.conext con cod='15' (igual mecanismo que
-- para versiones master en 07_version_master_vigente.sql).
--
-- Hallazgo empírico: en el Caso 1 (66% de duplicados) el ide vigente según
-- conext es siempre el MÁS ANTIGUO (ide más bajo). Esto es opuesto al patrón
-- de tablas detalle de Sigrid donde una edición añade una línea nueva.
--
-- Tres casos detectados al analizar Ruesma:
--
--   Caso 1 (66%, 35 obras): conext marca un único ide como vigente.
--     → ese es el bueno (lo elige automáticamente el ranking).
--
--   Caso 2 (32%, 17 obras): ningún ide marcado en conext. Dos subcasos:
--     2A: códigos administrativos → ya excluidos por el WHERE de arriba.
--     2B: obras antiguas legítimas pre-conext. Fallback automático:
--         MAX(tiemod), el registro modificado más recientemente.
--
--   Caso 3 (2%, solo 0606 = PUY DU FOU): múltiples ides marcados como
--     vigentes en conext. Desempate automático por tiemod DESC, ide DESC.
--     Si en algún momento negocio decide cuál es el correcto, marcar en
--     Sigrid (quitar el cx15 del incorrecto) y rebuild.
--
-- Ranking aplicado:
--   1º vigente en conext (0) vs no vigente (1) → vigentes primero
--   2º tiemod DESC                              → entre iguales, el más reciente
--   3º obr.ide DESC                             → desempate final
-- ===========================================================================

TRUNCATE TABLE stg.obras;

INSERT INTO stg.obras (obra_id, codigo_obra, nombre_obra, activa)
WITH ranked AS (
    SELECT
        obr.ide                              AS obra_id,
        con.cod                              AS codigo_obra,
        con.res                              AS nombre_obra,
        con.tiemod                           AS con_tiemod,
        ROW_NUMBER() OVER (
            PARTITION BY con.cod
            ORDER BY
                -- 1º vigentes en conext primero
                CASE WHEN cx15.conide IS NOT NULL THEN 0 ELSE 1 END,
                -- 2º más recientes primero (fallback Caso 2B)
                con.tiemod DESC NULLS LAST,
                -- 3º desempate final por ide DESC
                obr.ide DESC
        ) AS rn
    FROM raw.obr obr
    JOIN raw.con con ON con.ide = obr.ide
    LEFT JOIN raw.conext cx15
           ON cx15.conide = obr.ide
          AND cx15.cod = '15'
    -- Excluir códigos administrativos (papeleras, no obras reales)
    WHERE con.cod NOT IN (
        '0001','0002','0003','0004','0005',
        'CM','CP','GG','VAR','POSTV','POSTV2',
        'BD','BD1','BD2','BDS',
        'BDDIAMAD','BDDIASUR','BDDIANORTE','BDDIAGRANADA',
        'GGD','GINT','OT'
    )
    -- Excluir códigos con 5+ dígitos consecutivos (numeración inválida)
    AND con.cod !~ '[0-9]{5,}'
    -- Excluir códigos NULL o vacíos por sanidad
    AND con.cod IS NOT NULL
    AND length(trim(con.cod)) > 0
)
SELECT
    obra_id,
    codigo_obra,
    nombre_obra,
    TRUE AS activa
FROM ranked
WHERE rn = 1;
