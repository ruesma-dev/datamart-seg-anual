-- etl_sigrid/infrastructure/postgres/sql/personal/03_views.sql
-- ============================================================================
-- personal.v_pbi_horas_obra_mes — LAS HORAS, y solo las horas.
--
-- Grano: obra x año x mes x tipo de recurso x interno/externo.
--
-- `WHERE unidad = 'HORA'` va CABLEADO, y ese es el motivo de existir de esta
-- vista. No es un filtro por defecto que el consumidor pueda quitar: es lo que
-- hace que la trampa de la unidad **no se pueda cometer desde aqui**. Sumar
-- `cantidad` sin ese corte mezcla horas de albañil con meses de jefe de obra,
-- dias de vacaciones y kilometros, y da 1.837.201,23 de nada. Con el corte
-- salen 1.249.038,44 horas, sobre 369 obras y 445 recursos, todos de
-- `clase = 'PERSONA'`.
--
-- LO QUE ESTA VISTA NO RESPONDE, y hay que decirlo (D8): el coste de personal
-- por obra COMPLETO no es su `SUM(importe)`. El 71,7 % del euro esta en las
-- lineas de MES —el coste de estructura de obra—, que aqui no entran. El euro
-- total por obra sale de `personal.partes_lineas` sin filtrar unidad, y eso lo
-- dice la ficha del diccionario.
--
-- NO LLEVA NOMBRE NI DNI. No por privacidad —estan autorizados desde el
-- 2026-09-18 y viven en `personal.recursos`— sino porque esto es un AGREGADO:
-- el nombre a este grano solo produce filas de una persona disfrazadas de
-- agregado. Si alguien necesita saber quien trabajo en una obra, cruza
-- `personal.partes_lineas` con `personal.recursos`, que es para lo que estan.
--
-- POR QUE EL CODIGO Y EL NOMBRE DE OBRA SALEN DE `raw.con` Y NO DE
-- `maestro.obras`: este esquema declara `depends_on = ["build_stg"]` y nada
-- mas. Colgar la vista de `maestro` añadiria una dependencia de otro modulo
-- —que se construye en el mismo tramo de la noche— para traer dos literales
-- que `raw.con` ya tiene. `personal` falla solo, y esa es su razon de ser.
-- ============================================================================

DROP VIEW IF EXISTS personal.v_pbi_horas_obra_mes CASCADE;

CREATE VIEW personal.v_pbi_horas_obra_mes AS
SELECT
    pl.obra_id                          AS obra_id,
    co.cod                              AS codigo_obra,
    co.res                              AS nombre_obra,
    pl.anio                             AS anio,
    pl.mes                              AS mes,
    r.tipo_recurso                      AS tipo_recurso,
    r.es_externo                        AS es_externo,
    COUNT(DISTINCT pl.recurso_id)       AS recursos,
    SUM(pl.cantidad)::NUMERIC(18,2)     AS horas,
    SUM(pl.importe)::NUMERIC(18,2)      AS importe
FROM      personal.partes_lineas pl
-- LEFT los dos: 10 lineas no tienen recurso y 1.373 no tienen obra. Con INNER
-- desaparecerian del agregado sin ruido, que es como se pierde dato sin
-- enterarse.
LEFT JOIN personal.recursos r ON r.recurso_id = pl.recurso_id
LEFT JOIN raw.con           co ON co.ide      = pl.obra_id
WHERE pl.unidad = 'HORA'
GROUP BY
    pl.obra_id, co.cod, co.res, pl.anio, pl.mes,
    r.tipo_recurso, r.es_externo;

COMMENT ON VIEW personal.v_pbi_horas_obra_mes IS
'Horas imputadas por obra, año, mes y tipo de recurso. Construida SOLO con unidad = HORA (1.249.038,44 h sobre 369 obras), y ese corte va cableado para que la trampa de la unidad no se pueda cometer desde aqui. NO es el coste de personal completo: el 71,7 % del euro esta en las lineas de MES (estructura de obra) y aqui no entran; para eso, personal.partes_lineas sin filtrar unidad. No lleva nombre ni DNI porque es un agregado: quien trabajo en una obra se responde cruzando partes_lineas con personal.recursos.';
