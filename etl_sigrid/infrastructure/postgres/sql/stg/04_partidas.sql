-- etl_sigrid/infrastructure/postgres/sql/stg/04_partidas.sql
--
-- Materializa stg.partidas a partir de raw.obrparpar, RECONSTRUYENDO la
-- jerarquía de capítulos para poder agregar luego por CD / CI / CP / OTRO.
--
-- ===========================================================================
-- ALGORITMO DEL ÁRBOL
-- ===========================================================================
-- Cada partida en raw.obrparpar tiene `padide` que apunta a su capítulo padre
-- (también una fila de obrparpar). Las partidas raíz tienen padide = 0.
--
-- En Ruesma los capítulos raíz típicos son:
--   CD = Costes Directos
--   CI = Costes Indirectos
--   CP = Costes Proporcionales
--   34 = OC (Orden de cambio, fuera de los tres grandes)
--
-- Usamos un CTE recursivo arbol_partidas que:
--   1. Arranca con las partidas raíz (padide=0 o NULL).
--   2. Desciende nivel a nivel, propagando el (capitulo_raiz_id, capitulo_raiz_cod)
--      hasta las partidas hoja.
--   3. Construye `ruta_capitulos` concatenando códigos como "CD > 01 > 01.02".
--
-- CATEGORIA: normalizamos el código del capítulo raíz a uno de:
--   "CD"  si el código del raíz contiene 'CD' o si la primera parte del
--         código de partida es numérica pura (los capítulos numéricos típicos
--         son CD: 01, 02, 03... salvo el 34 que es OC).
--   "CI"  si contiene 'CI'.
--   "CP"  si contiene 'CP'.
--   "OTRO" para el resto.
--
-- Filtros:
--   - cod IS NOT NULL: descarta filas estructurales sin código de partida.
--   - tipdes = 0: partidas activas. Las desactivadas se incluyen con
--     activa=FALSE para no perder histórico.

TRUNCATE TABLE stg.partidas;

WITH RECURSIVE
-- Paso 1: raíces — partidas sin padre.
arbol_partidas AS (
    SELECT
        p.ide                            AS partida_id,
        p.obride                         AS obra_id,
        NULLIF(p.padide, 0)              AS capitulo_padre_id,
        p.cod                            AS codigo_partida,
        p.res                            AS descripcion_corta,
        NULLIF(TRIM(p.unimed), '')       AS unidad_medida,
        COALESCE(p.tipdes, 0)            AS tipdes_raw,
        -- En la raíz, ella misma es el raíz
        p.ide                            AS capitulo_raiz_id,
        p.cod                            AS capitulo_raiz_cod,
        p.cod::TEXT                      AS ruta_capitulos,
        0                                AS nivel
    FROM raw.obrparpar p
    WHERE COALESCE(p.padide, 0) = 0      -- raíces
      AND p.cod IS NOT NULL
      AND p.cod <> ''

    UNION ALL

    -- Paso 2: descender, heredando capitulo_raiz_* del padre.
    SELECT
        h.ide                            AS partida_id,
        h.obride                         AS obra_id,
        h.padide                         AS capitulo_padre_id,
        h.cod                            AS codigo_partida,
        h.res                            AS descripcion_corta,
        NULLIF(TRIM(h.unimed), '')       AS unidad_medida,
        COALESCE(h.tipdes, 0)            AS tipdes_raw,
        a.capitulo_raiz_id,
        a.capitulo_raiz_cod,
        (a.ruta_capitulos || ' > ' || h.cod)::TEXT AS ruta_capitulos,
        a.nivel + 1                      AS nivel
    FROM raw.obrparpar h
    JOIN arbol_partidas a ON a.partida_id = h.padide
    WHERE h.cod IS NOT NULL
      AND h.cod <> ''
),
-- Paso 3: ya tenemos el árbol completo. Asignamos categoría.
arbol_categorizado AS (
    SELECT
        ap.*,
        CASE
            -- Si el código raíz contiene 'CD' (también vale 'CD '): Costes Directos
            WHEN UPPER(COALESCE(ap.capitulo_raiz_cod, '')) LIKE '%CD%'  THEN 'CD'
            WHEN UPPER(COALESCE(ap.capitulo_raiz_cod, '')) LIKE '%CI%'  THEN 'CI'
            WHEN UPPER(COALESCE(ap.capitulo_raiz_cod, '')) LIKE '%CP%'  THEN 'CP'
            -- Si el código raíz es numérico puro (01, 02, ..., 34), suele ser CD.
            -- Excepto "34" que en Ruesma es "OC" (Orden de Cambio), lo dejamos OTRO.
            -- Heurística: para capítulos raíz numéricos que NO sean 34, los
            -- consideramos CD (es la práctica habitual en Sigrid: el JO crea
            -- capítulos numéricos colgando de un CD raíz).
            -- NOTA: si el JO de Ruesma tiene un raíz literal "CD COSTES DIRECTOS"
            -- la primera regla lo captura. Esta segunda es defensiva.
            WHEN ap.capitulo_raiz_cod ~ '^[0-9]+$'
              AND ap.capitulo_raiz_cod NOT IN ('34', '99')
                THEN 'CD'
            ELSE 'OTRO'
        END AS categoria
    FROM arbol_partidas ap
)
INSERT INTO stg.partidas (
    partida_id, obra_id, codigo_partida, capitulo_padre_id, descripcion_corta,
    unidad_medida, capitulo_raiz_id, capitulo_raiz_cod, categoria, ruta_capitulos,
    nivel, activa
)
SELECT
    partida_id,
    obra_id,
    codigo_partida,
    capitulo_padre_id,
    descripcion_corta,
    unidad_medida,
    capitulo_raiz_id,
    capitulo_raiz_cod,
    categoria,
    ruta_capitulos,
    nivel,
    CASE WHEN tipdes_raw = 0 THEN TRUE ELSE FALSE END AS activa
FROM arbol_categorizado;
