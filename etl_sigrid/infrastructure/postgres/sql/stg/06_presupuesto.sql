-- etl_sigrid/infrastructure/postgres/sql/stg/06_presupuesto.sql
--
-- Materializa stg.presupuesto a partir de raw.obrparpre.
--
-- Filtros: solo obride NOT NULL (preservamos cierres con valor 0 = estornos).
--
-- DEDUPLICACIÓN: DISTINCT ON por clave de negocio (obra, partida, amb, fase)
-- quedándonos con el `ide` MAYOR (la corrección más reciente de Sigrid).
--
-- PRECISIÓN (cantidad y precio en NUMERIC(20,6)):
--   - precio: raw.obrparpre.pre tiene hasta 6 decimales reales.
--   - cantidad: raw.obrparpre.can para CP* contiene porcentajes con hasta
--     6 decimales. Truncar a 4 causa gap material en el Plan.
--   Se guardan SIEMPRE con 6 decimales (precisión máxima). El redondeo por
--   decimales de obra se aplica SOLO al calcular el importe (ver abajo).
--
-- ===========================================================================
-- DECIMALES POR OBRA (decc/decp/deci de raw.obr)
-- ===========================================================================
-- Cada obra define en Sigrid cuántos decimales usa para cantidades (decc),
-- precios (decp) e importes (deci). Sigrid redondea cantidad y precio a esos
-- decimales ANTES de multiplicar, y el resultado a deci. Replicamos esa
-- mecánica para que el importe cuadre al céntimo con la pantalla de Sigrid:
--
--   importe = ROUND( can * ROUND(pre, decp), deci )
--
-- OJO: `decc` NO interviene. La cantidad NO se redondea, por el motivo que
-- explica la NOTA de mas abajo (las partidas tipo porcentaje se inflarian).
-- Este comentario decia `ROUND(can, decc)` y era falso; indujo una ficha
-- equivocada en F-006, que lo copio en vez de leer el codigo.
--
-- Defaults si la obra no los tiene informados: decc=3, decp=2, deci=2.
-- (En Ruesma típicamente decc=3, decp=3, deci=2 — ver pantalla obra 0710.)
--
-- ===========================================================================
-- COLUMNAS DE IMPORTE
-- ===========================================================================
--   - importe         = ROUND(can * ROUND(pre,decp), deci). Sin `decc`.
--                       Decimales propios de la obra. Lo usan mart/plan_mensual
--                       y el cierre (costes).
--   - importe_oficial = COALESCE(NULLIF(impcoe,0), importe). Lo usa el cierre
--                       para VENTA (Sigrid aplica coeficientes solo en venta).
--   - dec_cantidades / dec_precios / dec_importes = decc/decp/deci de la obra,
--                       expuestos para que 08_plan_mensual reaplique el mismo
--                       redondeo al explotar el plan mensual.

TRUNCATE TABLE stg.presupuesto;

INSERT INTO stg.presupuesto (
    presupuesto_id,
    obra_id,
    partida_id,
    ambito_id,
    fase_num,
    cantidad,
    precio,
    importe,
    importe_oficial,
    dec_cantidades,
    dec_precios,
    dec_importes,
    _source_tiemod
)
SELECT DISTINCT ON (pp.obride, pp.paride, pp.amb, COALESCE(pp.fas, 0))
    pp.ide                                            AS presupuesto_id,
    pp.obride                                         AS obra_id,
    pp.paride                                         AS partida_id,
    pp.amb                                            AS ambito_id,
    COALESCE(pp.fas, 0)                               AS fase_num,
    pp.can::NUMERIC(20,6)                             AS cantidad,
    pp.pre::NUMERIC(20,6)                             AS precio,
    -- importe con decimales propios de la obra:
    --   redondea SOLO pre a decp antes de multiplicar; resultado a deci
    -- NOTA: la cantidad NO se redondea. Las partidas tipo porcentaje (CP
    -- avales/seguros) tienen cantidades como 0.0015 (=0.15%) que, redondeadas
    -- a decc=3, se convertirían en 0.002 e inflarían el importe. Sigrid solo
    -- redondea el PRECIO a decp; la cantidad mantiene su precisión completa.
    ROUND(
        pp.can::NUMERIC * ROUND(pp.pre::NUMERIC, COALESCE(o.decp::INT, 2)),
        COALESCE(o.deci::INT, 2)
    )                                                 AS importe,
    -- importe_oficial: prioriza impcoe (Sigrid con coeficientes en venta);
    -- si impcoe es NULL/0 (todo coste, ~70% de filas) cae al importe calculado.
    COALESCE(
        NULLIF(pp.impcoe::NUMERIC(18,2), 0),
        ROUND(
            pp.can::NUMERIC * ROUND(pp.pre::NUMERIC, COALESCE(o.decp::INT, 2)),
            COALESCE(o.deci::INT, 2)
        )
    )                                                 AS importe_oficial,
    COALESCE(o.decc::INT, 3)                          AS dec_cantidades,
    COALESCE(o.decp::INT, 2)                          AS dec_precios,
    COALESCE(o.deci::INT, 2)                          AS dec_importes,
    pp._source_tiemod
FROM raw.obrparpre pp
JOIN raw.obr o ON o.ide = pp.obride       -- decimales propios de la obra
WHERE pp.obride IS NOT NULL
ORDER BY pp.obride, pp.paride, pp.amb, COALESCE(pp.fas, 0), pp.ide DESC;
