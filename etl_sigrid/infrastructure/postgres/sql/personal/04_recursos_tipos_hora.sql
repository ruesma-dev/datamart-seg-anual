-- etl_sigrid/infrastructure/postgres/sql/personal/04_recursos_tipos_hora.sql
-- ============================================================================
-- personal.recursos_tipos_hora — LOS PRECIOS DE LA FICHA del recurso (F-101).
--
-- Una fila por fila de `raw.reshor` (8.968 el 2026-09-23; 2.064 recursos, 58
-- tipos de hora): que tipos de hora tiene definidos cada recurso, a que precio
-- y en que unidad. Lo pidio Juan Romero para comparar lo CONFIGURADO con lo
-- IMPUTADO en los partes (el caso de Jaime Rabadan, MO/0306).
--
-- ---------------------------------------------------------------------------
-- LA CLAVE ES `reshor_id`, NO EL PAR (D-4)
-- ---------------------------------------------------------------------------
-- Hay 17 pares (recurso, tipo de hora) repetidos: 16 con el mismo precio y uno
-- —recurso 947513, tipo 27— con dos precios distintos. Declarar el par como
-- clave pondria `check-unicidad` en rojo la primera noche. Quien una estas filas
-- con las lineas de parte por (recurso, tipo de hora) tiene que saberlo.
--
-- ---------------------------------------------------------------------------
-- SON LOS PRECIOS DE HOY (D-5)
-- ---------------------------------------------------------------------------
-- `reshor` no tiene ninguna columna de fecha ni `tiemod`: Sigrid no guarda
-- historico de precios aqui, asi que no se publica vigencia. Inventarla a
-- partir de las lineas de parte seria una construccion del datamart presentada
-- como dato de origen. El desfase que Juan persigue se ve contra las lineas: de
-- 279.034 lineas comparables, 156.819 (56,2 %) llevan un precio distinto del
-- de la ficha.
--
-- ---------------------------------------------------------------------------
-- LO QUE NO ENTRA
-- ---------------------------------------------------------------------------
-- El precio de NOMINA de `reshor` no se publica: decision expresa del humano
-- del 2026-09-22 (distinto de 0 en 2 filas, que podrian ser nomina real). Lo
-- vigila `test_f101_r22_*` sobre el texto ejecutable. Las columnas de cuenta y
-- de proyecto valen 0 en todas las filas y tampoco suben. `raw.reshor` sigue
-- fuera del rol del MCP por F-068: lo que se abre es este objeto curado.
--
-- LA UNIDAD sale del MISMO `CASE` sobre `auxhor.medide` que
-- `02_partes_lineas.sql`, caracter a caracter (lo compara
-- `test_f101_r19_*`): dos traducciones que divergen son peor que una sola
-- equivocada. El JOIN al catalogo es LEFT: 3 filas apuntan a un tipo de hora
-- que no esta en `auxhor` y salen como 'DESCONOCIDA' en vez de perderse.
--
-- EL TIPO DE HORA POR DEFECTO del recurso esta en `res.horide` (2.035 de
-- 2.618 recursos, 0 huerfanos). `es_por_defecto` lo marca en la fila de ese
-- tipo (D-8, opcion A). En 4 recursos el defecto no tiene fila en `reshor`, asi
-- que ninguna de sus filas lo marca: lo declara la ficha.
-- ============================================================================

TRUNCATE TABLE personal.recursos_tipos_hora;

INSERT INTO personal.recursos_tipos_hora (
    reshor_id, recurso_id, tipo_hora_id,
    codigo_tipo_hora, tipo_hora, unidad,
    precio_coste, precio_venta, cantidad_defecto,
    cuenta_analitica_id, es_por_defecto, orden, tipo_hora_de_baja
)
SELECT
    rh.ide                                  AS reshor_id,
    NULLIF(rh.reside, 0)                    AS recurso_id,
    NULLIF(rh.horide, 0)                    AS tipo_hora_id,
    h.cod                                   AS codigo_tipo_hora,
    h.res                                   AS tipo_hora,
    -- IDENTICO al de `02_partes_lineas.sql`.
    CASE h.medide
        WHEN 1  THEN 'HORA'
        WHEN 2  THEN 'DIA'
        WHEN 3  THEN 'MES'
        WHEN 19 THEN 'UD'
        ELSE 'DESCONOCIDA'
    END::VARCHAR(12)                        AS unidad,
    -- El precio de coste es el que imputa el parte (2.037 filas distintas de 0).
    COALESCE(rh.pre, 0)::NUMERIC(18,4)      AS precio_coste,
    -- Informado en 3 filas: se publica igual (D-9) y la ficha lo avisa.
    COALESCE(rh.preven, 0)::NUMERIC(18,4)   AS precio_venta,
    COALESCE(rh.candef, 0)::NUMERIC(18,4)   AS cantidad_defecto,
    NULLIF(rh.caaide, 0)                    AS cuenta_analitica_id,
    COALESCE(NULLIF(r.horide, 0) = rh.horide, FALSE) AS es_por_defecto,
    rh.pos                                  AS orden,
    -- NULL cuando el tipo de hora no esta en el catalogo (3 filas).
    (h.fecbaj <> 0)                         AS tipo_hora_de_baja
FROM      raw.reshor rh
-- LEFT, y hace falta: 3 filas sin tipo de hora en el catalogo.
LEFT JOIN raw.auxhor h ON h.ide = rh.horide
-- Solo para `es_por_defecto`. `raw.res` tiene clave `ide`: no multiplica.
LEFT JOIN raw.res    r ON r.ide = rh.reside;

COMMENT ON TABLE personal.recursos_tipos_hora IS
'Tipos de hora definidos en la ficha de cada recurso, con su precio de coste y de venta y su unidad (8.968 filas el 2026-09-23). Son los precios de HOY: Sigrid no guarda historico aqui. La clave es reshor_id, no el par (recurso, tipo de hora), que se repite 17 veces. precio_venta solo tiene valor en 3 filas. El precio de nomina NO se publica (decision del humano, 2026-09-22). De 279.034 lineas de parte comparables, el 56,2 % lleva un precio distinto del de la ficha.';
