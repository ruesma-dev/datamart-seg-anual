-- etl_sigrid/infrastructure/postgres/sql/stg/03_obras.sql
--
-- Materializa stg.obras combinando raw.obr con raw.con: UNA FILA POR FICHA de
-- obra de todas las empresas (F-162), filtrando códigos no válidos y marcando
-- en `es_por_defecto` la ficha por defecto de cada código.
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
-- TODAS LAS FICHAS, CADA UNA CON SU EMPRESA (F-162, 2026-11-11)
-- ===========================================================================
-- En Sigrid la obra es POR EMPRESA: el mismo código existe una vez por empresa
-- (Ruesma 1, Porsan 28, cada UTE) y es la misma obra vista desde cada una, SIN
-- CONSOLIDAR. Modelo del humano: «Debes leer los proyectos en ambas empresas.
-- No tener que elegir: cada uno con su propia empresa, sin cruces entre
-- empresas.» Por eso esta tabla lleva UNA FILA POR FICHA (`obra_id`) y ya no
-- desempata: hasta F-162 se quedaba con una ficha por código (`WHERE rn = 1`
-- sobre la marca `conext` 15, `tiemod` e `ide`) y en la 0721 elegía la copia
-- vacía de PORSAN en vez de la de Ruesma, con 9.165 líneas de presupuesto.
-- Medido el 2026-11-11: 585 -> 634 fichas para 585 códigos.
--
-- Todo lo que cuelga (`mart`, `cierre`, `tesoreria`, `retenciones`,
-- `personal`) va por `obra_id`: cada ficha con lo suyo. El código NO es único
-- aquí; se busca por `clave_obra` o por (`empresa_id`, `codigo_obra`).
--
-- `es_por_defecto` marca UNA ficha por código: la que se lee cuando la pregunta
-- no dice empresa. Criterio del humano («en caso de duda, Construcciones Ruesma
-- por delante, salvo que se diga lo contrario; los datos deciden antes que la
-- duda»), el mismo que `etl_sigrid/domain/ficha_obra.py`, criterio a criterio:
--   1º la ficha de la empresa 1, si el código la tiene;
--   2º más líneas de presupuesto (`raw.obrparpre`);
--   3º `tiemod` más reciente (sin `tiemod`, pierde);
--   4º `ide` mayor, solo como desempate final.
-- La marca de vigente `conext` 15 NO interviene (D2): dice cuál de las fichas
-- duplicadas es «la vigente», que es justo la elección que este modelo deja.
--
-- LAS LÍNEAS SE CUENTAN SOLO DONDE DECIDEN, y antes de unir: `raw.obrparpre`
-- tiene 13,7 M de filas y contarla entera cuesta 48 s. Solo hacen falta en los
-- códigos con varias fichas en los que la empresa 1 no decide sola (ninguna o
-- más de una ficha de Ruesma: `dudosas`). Hoy no hay ninguno.
-- ===========================================================================

TRUNCATE TABLE stg.obras;

INSERT INTO stg.obras (obra_id, codigo_obra, nombre_obra, activa, empresa_id, clave_obra, es_por_defecto)
WITH fichas AS (
    SELECT
        obr.ide                              AS obra_id,
        con.cod                              AS codigo_obra,
        con.res                              AS nombre_obra,
        con.emp                              AS empresa_id,
        con.emp::text || '-' || con.cod      AS clave_obra,
        con.tiemod                           AS tiemod
    FROM raw.obr obr
    JOIN raw.con con ON con.ide = obr.ide
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
),
-- Las fichas de los códigos donde la empresa 1 no decide sola.
dudosas AS (
    SELECT f.obra_id
    FROM fichas f
    WHERE f.codigo_obra IN (
        SELECT codigo_obra FROM fichas
        GROUP BY codigo_obra HAVING count(*) > 1
           AND count(*) FILTER (WHERE empresa_id = 1) <> 1
    )
),
-- Sus líneas de presupuesto, agregadas ANTES de unir.
lineas AS (
    SELECT p.obride, count(*) AS num_lineas
    FROM raw.obrparpre p
    WHERE p.obride IN (SELECT obra_id FROM dudosas)
    GROUP BY p.obride
)
SELECT
    f.obra_id,
    f.codigo_obra,
    f.nombre_obra,
    TRUE AS activa,
    f.empresa_id,
    f.clave_obra,
    ROW_NUMBER() OVER (
        PARTITION BY f.codigo_obra
        ORDER BY
            CASE WHEN f.empresa_id = 1 THEN 0 ELSE 1 END,
            COALESCE(l.num_lineas, 0) DESC,
            f.tiemod DESC NULLS LAST,
            f.obra_id DESC
    ) = 1 AS es_por_defecto
FROM fichas f
LEFT JOIN lineas l ON l.obride = f.obra_id;
