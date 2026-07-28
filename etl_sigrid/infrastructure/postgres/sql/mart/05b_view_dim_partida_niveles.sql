-- etl_sigrid/infrastructure/postgres/sql/mart/05b_view_dim_partida_niveles.sql
--
-- Dimensión partida CON COLUMNAS POR NIVEL para el visual "Árbol Presupuesto".
-- Superset de mart.v_pbi_dim_partida: añade nivel_1..nivel_6 como "código · nombre"
-- a partir de ruta_capitulos (cadena "CD > 01 > 01.02 > ..."). El nombre de cada
-- código se resuelve con un self-join sobre stg.partidas (cada capítulo/subcapítulo
-- es también una fila con su descripción).
--
-- Profundidad variable: una rama que no llega a nivel_5/6 deja esas columnas NULL;
-- el visual las absorbe (no pinta filas vacías).
--
-- Misma clave que DimPartida (partida_id) → puedes repuntar tu consulta
-- DimPartida a esta vista (Item="v_pbi_dim_partida_niveles") sin tocar relaciones.

DROP VIEW IF EXISTS mart.v_pbi_dim_partida_niveles CASCADE;

CREATE VIEW mart.v_pbi_dim_partida_niveles AS
WITH base AS (
    SELECT
        partida_id, obra_id, codigo_partida, descripcion_corta, unidad_medida,
        categoria, capitulo_raiz_cod, ruta_capitulos, nivel, activa,
        string_to_array(ruta_capitulos, ' > ') AS arr
    FROM stg.partidas
),
nom AS (  -- nombre por (obra, código): cada nodo de la ruta es una partida/capítulo
    SELECT obra_id, codigo_partida AS cod, MAX(descripcion_corta) AS nombre
    FROM   stg.partidas
    WHERE  codigo_partida IS NOT NULL
    GROUP  BY obra_id, codigo_partida
),
cods AS (
    SELECT b.*,
        (b.arr)[1] AS c1, (b.arr)[2] AS c2, (b.arr)[3] AS c3,
        (b.arr)[4] AS c4, (b.arr)[5] AS c5, (b.arr)[6] AS c6
    FROM base b
)
SELECT
    e.partida_id,
    e.obra_id,
    e.codigo_partida,
    e.descripcion_corta            AS descripcion_partida,
    e.unidad_medida,
    e.categoria,
    e.capitulo_raiz_cod,
    e.ruta_capitulos,
    e.nivel,
    e.activa,
    COALESCE(e.codigo_partida, '')
        || CASE WHEN e.descripcion_corta IS NOT NULL
                THEN ' · ' || e.descripcion_corta ELSE '' END   AS partida_label,
    CASE WHEN e.nivel >= 2 OR e.codigo_partida LIKE '%.%'
         THEN TRUE ELSE FALSE END                               AS es_hoja,
    -- Una columna "código · nombre" por nivel (NULL si la rama no llega)
    CASE WHEN e.c1 IS NOT NULL THEN e.c1 || COALESCE(' · ' || n1.nombre, '') END AS nivel_1,
    CASE WHEN e.c2 IS NOT NULL THEN e.c2 || COALESCE(' · ' || n2.nombre, '') END AS nivel_2,
    CASE WHEN e.c3 IS NOT NULL THEN e.c3 || COALESCE(' · ' || n3.nombre, '') END AS nivel_3,
    CASE WHEN e.c4 IS NOT NULL THEN e.c4 || COALESCE(' · ' || n4.nombre, '') END AS nivel_4,
    CASE WHEN e.c5 IS NOT NULL THEN e.c5 || COALESCE(' · ' || n5.nombre, '') END AS nivel_5,
    CASE WHEN e.c6 IS NOT NULL THEN e.c6 || COALESCE(' · ' || n6.nombre, '') END AS nivel_6
FROM      cods e
LEFT JOIN nom n1 ON n1.obra_id = e.obra_id AND n1.cod = e.c1
LEFT JOIN nom n2 ON n2.obra_id = e.obra_id AND n2.cod = e.c2
LEFT JOIN nom n3 ON n3.obra_id = e.obra_id AND n3.cod = e.c3
LEFT JOIN nom n4 ON n4.obra_id = e.obra_id AND n4.cod = e.c4
LEFT JOIN nom n5 ON n5.obra_id = e.obra_id AND n5.cod = e.c5
LEFT JOIN nom n6 ON n6.obra_id = e.obra_id AND n6.cod = e.c6;

COMMENT ON VIEW mart.v_pbi_dim_partida_niveles IS
'DimPartida + nivel_1..nivel_6 ("código · nombre") derivados de ruta_capitulos, para el visual Árbol Presupuesto. Clave: partida_id. Profundidad variable (niveles sobrantes NULL).';
