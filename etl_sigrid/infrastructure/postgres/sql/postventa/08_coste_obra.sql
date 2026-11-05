-- etl_sigrid/infrastructure/postgres/sql/postventa/08_coste_obra.sql
-- ============================================================================
-- F-156 · EL COSTE DE POSTVENTA POR OBRA DE ORIGEN (D4, R25-R26).
--
-- Sigrid NO liga una incidencia con su coste (`tar.costot` 0, `hmores.taride`
-- 0). El coste de postventa se imputa a OBRAS DE POSTVENTA (`POSTV`, `POSTV2`
-- de la empresa 1; `POSTV2` y `0004` de otras), y sus partidas SE LLAMAN COMO
-- LA OBRA DE ORIGEN (`0592`, `0593B`, `0561 `, `626`...). Por ahí se liga.
--
-- `postventa.partida_obra_origen` (R25): una fila por partida de las obras de
-- postventa (tipo 42 con «POSTVENTA» en el nombre o código `POSTV...`), con la
-- obra de origen de SU empresa por el código de la partida (cifras iniciales,
-- 3 o 4, a 4 con ceros: `postventa.fn_obra_de_partida`) o, si no, por el del
-- ancestro más cercano que lo tenga (subiendo por `padide`, con tope de 10
-- niveles: `padide` tiene bucles). `liga` = PARTIDA, ANCESTRO o SIN_OBRA
-- (`liga_coste` del dominio). SIN_OBRA se publica, no se esconde (los
-- capítulos CI y CP de POSTV2: ~537.000 € de facturas el 2026-11-03).
--
-- `postventa.v_coste_obra` (R26): VISTA, el coste de FACTURAS de compra de esas
-- partidas por obra de postventa, obra de origen, `liga` y mes de la factura.
-- Es la ÚNICA lectura fuera de `raw` del módulo: lee `compras` AL CONSULTAR.
-- AVISO: `build-compras` suelto la tira (DROP ... CASCADE); `run-all` la rehace
-- porque `build_postventa` va detrás. Los partes de PERSONAL no entran (el
-- perfil restringido no ve `personal`): la ficha dice cómo cruzarlos.
-- ============================================================================

DROP VIEW IF EXISTS postventa.v_coste_obra;
DROP TABLE IF EXISTS postventa.partida_obra_origen CASCADE;
CREATE TABLE postventa.partida_obra_origen AS
WITH RECURSIVE obras_pv AS (
    SELECT c.ide AS obra_id, c.emp AS empresa_id, BTRIM(c.cod) AS codigo_obra
    FROM   raw.con c
    WHERE  c.tip = 42
      AND (c.res ILIKE '%POSTVENTA%' OR BTRIM(c.cod) ILIKE 'POSTV%')
),
partidas AS (
    SELECT p.ide AS partida_id, p.obride AS obra_id, NULLIF(p.padide, 0) AS padre_id,
           p.cod AS codigo_partida, p.res AS nombre_partida
    FROM   raw.obrparpar p
    JOIN   obras_pv o ON o.obra_id = p.obride
),
cadena AS (
    -- La partida (nivel 0) y sus ancestros, del más cercano al más lejano.
    SELECT pa.partida_id, pa.codigo_partida AS codigo_nodo, pa.padre_id AS siguiente,
           0 AS nivel
    FROM   partidas pa
    UNION ALL
    SELECT ca.partida_id, x.cod, NULLIF(x.padide, 0), ca.nivel + 1
    FROM   cadena ca
    JOIN   raw.obrparpar x ON x.ide = ca.siguiente
    WHERE  ca.nivel < 10
),
obras AS (
    SELECT c.ide, c.emp, BTRIM(c.cod) AS cod
    FROM   raw.con c
    WHERE  c.tip = 42
),
ligadas AS (
    -- El nodo más cercano cuyo código lleva una obra que EXISTE en su empresa.
    SELECT DISTINCT ON (ca.partida_id)
           ca.partida_id, ca.nivel, ob.ide AS obra_origen_id, ob.cod AS codigo_obra_origen
    FROM   cadena ca
    JOIN   partidas pa ON pa.partida_id = ca.partida_id
    JOIN   obras_pv opv ON opv.obra_id = pa.obra_id
    JOIN   obras ob ON ob.emp = opv.empresa_id
                   AND ob.cod = postventa.fn_obra_de_partida(ca.codigo_nodo)
    ORDER  BY ca.partida_id, ca.nivel, ob.ide
)
SELECT
    pa.partida_id                                   AS partida_id,
    opv.empresa_id                                  AS empresa_id,
    opv.obra_id                                     AS obra_postventa_id,
    opv.codigo_obra                                 AS codigo_obra_postventa,
    pa.codigo_partida                               AS codigo_partida,
    pa.nombre_partida                               AS nombre_partida,
    pa.padre_id                                     AS partida_padre_id,
    CASE WHEN lg.partida_id IS NULL THEN 'SIN_OBRA'
         WHEN lg.nivel = 0 THEN 'PARTIDA'
         ELSE 'ANCESTRO' END                        AS liga,
    lg.nivel                                        AS niveles_subidos,
    lg.obra_origen_id                               AS obra_origen_id,
    lg.codigo_obra_origen                           AS codigo_obra_origen
FROM      partidas pa
JOIN      obras_pv opv ON opv.obra_id = pa.obra_id
LEFT JOIN ligadas lg ON lg.partida_id = pa.partida_id;

ALTER TABLE postventa.partida_obra_origen ADD PRIMARY KEY (partida_id);
CREATE INDEX ix_pv_partida_obra_origen_origen ON postventa.partida_obra_origen (obra_origen_id);

COMMENT ON TABLE postventa.partida_obra_origen IS
'Partidas de las obras de postventa (POSTV, POSTV2...) con la obra de origen a la que se refieren (F-156, D4): por el codigo de la partida (cifras iniciales a 4 con ceros) o por el del ancestro mas cercano, contra las obras de SU empresa. liga = PARTIDA, ANCESTRO o SIN_OBRA. Es la llave del coste de postventa por obra (postventa.v_coste_obra).';

CREATE VIEW postventa.v_coste_obra AS
SELECT
    p.empresa_id                                    AS empresa_id,
    p.obra_postventa_id                             AS obra_postventa_id,
    p.codigo_obra_postventa                         AS codigo_obra_postventa,
    p.liga                                          AS liga,
    p.obra_origen_id                                AS obra_origen_id,
    p.codigo_obra_origen                            AS codigo_obra_origen,
    date_trunc('month', f.fecha_factura)::DATE      AS mes,
    SUM(fl.importe)                                 AS importe,
    COUNT(*)                                        AS lineas
FROM compras.factura_lineas fl
JOIN compras.facturas f ON f.factura_id = fl.factura_id
JOIN postventa.partida_obra_origen p ON p.partida_id = fl.partida_id
GROUP BY p.empresa_id, p.obra_postventa_id, p.codigo_obra_postventa, p.liga,
         p.obra_origen_id, p.codigo_obra_origen, date_trunc('month', f.fecha_factura)::DATE;

COMMENT ON VIEW postventa.v_coste_obra IS
'Coste de postventa por obra de origen (F-156, D4): importe SIN IVA de las lineas de FACTURA de compra de las partidas de las obras de postventa, por obra de postventa, obra de origen, liga y mes de la factura. Solo facturas: el coste de los partes de personal no esta (se cruza aparte por la partida). SIN_OBRA es coste de postventa sin obra de origen identificable.';
