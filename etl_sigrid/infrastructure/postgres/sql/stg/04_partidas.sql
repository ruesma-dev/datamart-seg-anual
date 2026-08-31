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
-- ===========================================================================
-- EL CÓDIGO VACÍO DECIDE QUÉ SE PUBLICA, NO POR DÓNDE SE DESCIENDE (F-052)
-- ===========================================================================
-- En Sigrid **un capítulo puede no tener código**: `cod` es la cadena vacía,
-- no NULL. Hasta el 2026-08-31 la rama recursiva exigía `h.cod <> ''`, así que
-- un capítulo en blanco no sólo no se publicaba: **cortaba el recorrido y
-- amputaba su subárbol entero**. Tres capítulos «FASE …» bajo la raíz CD de la
-- obra 0599 TANATORIO MAJADAHONDA se llevaron por delante 1.323 partidas, con
-- ellas 2.624.793,46 EUR de coste directo y el 100 % de la venta de esa obra:
-- el datamart publicaba un margen del 66,3 % donde el real era del 1,8 %.
--
-- Ahora el filtro baja al final. El capítulo sin código **se atraviesa** y
-- **no se publica** (es el `WHERE publicable` del INSERT), y sus hijos quedan
-- COLAPSADOS contra el ancestro publicado más cercano:
--
--   * `padre_publicado_id` es el padre si el padre publicaba, y si no, el que
--     el padre ya traía heredado. De ahí sale `capitulo_padre_id`, que por
--     tanto NO es siempre el `padide` de Sigrid.
--   * `ruta_capitulos` y `nivel` sólo avanzan en los nodos publicables, lo que
--     mantiene el invariante del que vive mart.v_pbi_dim_partida_niveles:
--       cardinality(string_to_array(ruta_capitulos, ' > ')) = nivel + 1
--     Sin eso saldría 'CD >  > 01.01' y un nivel en blanco en Power BI.
--
-- POR QUÉ COLAPSAR Y NO PUBLICAR EL NODO VACÍO: publicarlo obligaría a darle un
-- codigo_partida nulo o sintético y abriría la puerta al DOBLE CONTEO si ese
-- capítulo tuviera importes propios en stg.plan_mensual. Colapsarlo no añade ni
-- un euro y deja la relación capitulo_padre_id -> partida_id apuntando a una
-- fila que sí existe.
--
-- LA RAÍZ NO SE RELAJA (DA-1): un `padide = 0` con `cod = ''` sigue sin abrir
-- árbol. Los 7 nodos sin código medidos son todos INTERMEDIOS, así que relajar
-- la raíz no recuperaría ni una fila y obligaría a inventar reglas de
-- capitulo_raiz_id sin un caso real que las valide.
--
-- CORTA-CICLOS, OBLIGATORIO (DA-3): raw.obrparpar tiene 12 partidas cuya cadena
-- de `padide` da vueltas —dos auto-bucles y un bucle mutuo en la 0565—, una de
-- ellas en la 0686 VALDEBEBAS, que sigue viva. Hoy no cuelgan el recursivo
-- porque el filtro de código vacío las dejaba fuera por otro camino; relajarlo
-- sin corta-ciclos es un WITH RECURSIVE infinito dentro de una nocturna de
-- 3 h 45. Se corta con DOS mecanismos:
--   * `visitados`, un BIGINT[] que arrastra los `ide` ya pisados. Es exacto.
--   * `nivel_bruto < 40`, tope duro de respaldo. Muerde sobre los SALTOS y no
--     sobre `nivel`, porque una cadena de nodos colapsados en bucle no haría
--     avanzar `nivel` nunca. La profundidad real máxima medida es de 7 niveles,
--     así que deja 33 de margen y no trunca nada legítimo.
-- Esas 12 partidas siguen sin publicarse —no son alcanzables desde ninguna
-- raíz—, pero ya no se pierden en silencio: las denuncia `check-cobertura`.
--
-- La misma regla, ejecutable y probada sin base de datos, está en
-- etl_sigrid/domain/arbol_partidas.py; el texto de este fichero lo fija
-- tests/test_f052_sql.py.
--
-- Filtros:
--   - cod IS NOT NULL: un código nulo nunca formó parte de una ruta.
--   - cod <> '' en la RAÍZ (DA-1) y en el INSERT (qué se publica), nunca en el
--     descenso.
--   - tipdes = 0: partidas activas. Las desactivadas se incluyen con
--     activa=FALSE para no perder histórico.

TRUNCATE TABLE stg.partidas;

WITH RECURSIVE
-- Paso 1: raíces — partidas sin padre. Aquí el filtro de código vacío SÍ se
-- mantiene: una raíz sin código no abre árbol (DA-1).
arbol_partidas AS (
    SELECT
        p.ide                            AS partida_id,
        p.obride                         AS obra_id,
        p.cod                            AS codigo_partida,
        p.res                            AS descripcion_corta,
        NULLIF(TRIM(p.unimed), '')       AS unidad_medida,
        COALESCE(p.tipdes, 0)            AS tipdes_raw,
        -- En la raíz, ella misma es el raíz
        p.ide                            AS capitulo_raiz_id,
        p.cod                            AS capitulo_raiz_cod,
        p.cod::TEXT                      AS ruta_capitulos,
        0                                AS nivel,
        -- La raíz siempre publica: el WHERE de abajo lo garantiza.
        (p.cod <> '')                    AS publicable,
        NULL::BIGINT                     AS padre_publicado_id,
        ARRAY[p.ide]::BIGINT[]           AS visitados,
        0                                AS nivel_bruto
    FROM raw.obrparpar p
    WHERE COALESCE(p.padide, 0) = 0      -- raíces
      AND p.cod IS NOT NULL
      AND p.cod <> ''

    UNION ALL

    -- Paso 2: descender, heredando capitulo_raiz_* del padre. Se desciende
    -- también a través de los capítulos sin código (F-052, R1).
    SELECT
        h.ide                            AS partida_id,
        h.obride                         AS obra_id,
        h.cod                            AS codigo_partida,
        h.res                            AS descripcion_corta,
        NULLIF(TRIM(h.unimed), '')       AS unidad_medida,
        COALESCE(h.tipdes, 0)            AS tipdes_raw,
        a.capitulo_raiz_id,
        a.capitulo_raiz_cod,
        (CASE WHEN h.cod <> '' THEN a.ruta_capitulos || ' > ' || h.cod
              ELSE a.ruta_capitulos END)::TEXT        AS ruta_capitulos,
        a.nivel + CASE WHEN h.cod <> '' THEN 1 ELSE 0 END AS nivel,
        (h.cod <> '')                    AS publicable,
        -- El ancestro publicado más cercano (R3).
        CASE WHEN a.publicable THEN a.partida_id
             ELSE a.padre_publicado_id END            AS padre_publicado_id,
        a.visitados || h.ide             AS visitados,
        a.nivel_bruto + 1                AS nivel_bruto
    FROM raw.obrparpar h
    JOIN arbol_partidas a ON a.partida_id = h.padide
    WHERE h.cod IS NOT NULL
      AND NOT (h.ide = ANY (a.visitados))   -- corta-ciclos exacto (DA-3 a)
      AND a.nivel_bruto < 40                -- tope de respaldo (DA-3 b)
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
    -- NO es el `padide` de Sigrid: es el ancestro PUBLICADO más cercano (R3).
    padre_publicado_id AS capitulo_padre_id,
    descripcion_corta,
    unidad_medida,
    capitulo_raiz_id,
    capitulo_raiz_cod,
    categoria,
    ruta_capitulos,
    nivel,
    CASE WHEN tipdes_raw = 0 THEN TRUE ELSE FALSE END AS activa
FROM arbol_categorizado
-- Aquí, y sólo aquí, decide el código vacío: qué se publica (R2).
WHERE publicable;
