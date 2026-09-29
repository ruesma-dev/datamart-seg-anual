-- etl_sigrid/infrastructure/postgres/sql/descompuestos/05_cuadre.sql
-- ============================================================================
-- F-097 · SCHEMA descompuestos (6/7): el cuadre descompuesto-precio de las
-- partidas del AMBITO 3 (R23), para ESTUDIO y para PLANIF_JO.
--
-- Lee: raw.obrparpre, raw.obrparpar, descompuestos.lineas,
--      descompuestos._des_texto.
--
-- El cuadre del MASTER no esta aqui: lo escribe 03 junto con las lineas de
-- cada lote de versiones, en la misma transaccion (R8, R21). Este fichero
-- reconstruye cada noche solo lo del ambito 3 fase 0.
--
-- UNA FILA POR PARTIDA HOJA CON PRECIO Y POR ORIGEN: cada partida del ambito 3
-- fase 0 sin hijos en `obrparpar` y con `pre <> 0` sale DOS veces, una como
-- ESTUDIO y otra como PLANIF_JO. El estado:
--
--   SUSTITUIDO_POR_PLANIFICACION  (solo ESTUDIO) su «Descomposicion» tiene
--                                 algun registro enlazado a `dncpro`: ya no es
--                                 Estudios sino copia de la planificacion (D1).
--   SIN_DESCOMPUESTO              ninguna linea de ese origen (tanto alzado si
--                                 lo es en los dos).
--   CUADRA / NO_CUADRA            la suma de `importe_unitario` frente al precio
--                                 de la partida redondeado a 2 decimales, con
--                                 0,01 de tolerancia.
--
-- Las filas con `obride = 0` quedan fuera: no son de ninguna obra.
-- ============================================================================

DELETE FROM descompuestos.cuadre_partida WHERE origen IN ('ESTUDIO', 'PLANIF_JO');

WITH h AS (
    SELECT
        pp.ide AS presupuesto_id,
        pp.obride AS obra_id,
        pp.paride AS partida_id,
        ROUND(pp.pre::NUMERIC, 2) AS precio_partida
    FROM raw.obrparpre pp
    WHERE pp.amb = 3 AND pp.fas = 0
      AND COALESCE(pp.pre, 0) <> 0 AND pp.obride <> 0
      AND NOT EXISTS (SELECT 1 FROM raw.obrparpar x WHERE x.padide = pp.paride)
),
s AS (
    SELECT origen, obra_id, partida_id, COUNT(*) AS num_lineas, SUM(importe_unitario) AS suma
    FROM descompuestos.lineas
    WHERE origen IN ('ESTUDIO', 'PLANIF_JO')
    GROUP BY origen, obra_id, partida_id
),
su AS (
    SELECT DISTINCT d.obra_id, d.partida_id
    FROM descompuestos._des_texto d
    CROSS JOIN LATERAL descompuestos.fn_trocear(d.des) t
    WHERE d.ambito_id = 3 AND d.fase_num = 0 AND t.dncpro_id IS NOT NULL
)
INSERT INTO descompuestos.cuadre_partida (
    origen, obra_id, partida_id, ambito_id, fase_num, presupuesto_id,
    precio_partida, suma_descompuesto, diferencia, num_lineas, estado
)
SELECT o.origen, h.obra_id, h.partida_id, 3, 0, h.presupuesto_id,
       h.precio_partida,
       COALESCE(s.suma, 0),
       h.precio_partida - COALESCE(s.suma, 0),
       COALESCE(s.num_lineas, 0),
       CASE
           WHEN o.origen = 'ESTUDIO' AND su.partida_id IS NOT NULL THEN 'SUSTITUIDO_POR_PLANIFICACION'
           WHEN COALESCE(s.num_lineas, 0) = 0 THEN 'SIN_DESCOMPUESTO'
           WHEN ABS(h.precio_partida - COALESCE(s.suma, 0)) <= 0.01 THEN 'CUADRA'
           ELSE 'NO_CUADRA'
       END
FROM h
CROSS JOIN (VALUES ('ESTUDIO'), ('PLANIF_JO')) o(origen)
LEFT JOIN s ON s.origen = o.origen AND s.obra_id = h.obra_id AND s.partida_id = h.partida_id
LEFT JOIN su ON su.obra_id = h.obra_id AND su.partida_id = h.partida_id;
