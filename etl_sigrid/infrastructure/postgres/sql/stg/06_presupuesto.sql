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
--   importe = ROUND( ROUND(can, decc) * ROUND(pre, decp), deci )
--
-- Defaults si la obra no los tiene informados: decc=3, decp=2, deci=2.
-- (En Ruesma típicamente decc=3, decp=3, deci=2 — ver pantalla obra 0710.)
--
-- ===========================================================================
-- COLUMNAS DE IMPORTE
-- ===========================================================================
--   - importe         = ROUND(ROUND(can,decc)*ROUND(pre,decp), deci).
--                       Decimales propios de la obra. Lo usan mart/plan_mensual
--                       y el cierre (costes).
--   - importe_oficial = COALESCE(NULLIF(impcoe,0), importe). Lo usa el cierre
--                       para VENTA (Sigrid aplica coeficientes solo en venta).
--   - dec_cantidades / dec_precios / dec_importes = decc/decp/deci de la obra,
--                       expuestos para que 08_plan_mensual reaplique el mismo
--                       redondeo al explotar el plan mensual.

-- ===========================================================================
-- LA VENTANA DE NEGOCIO (F-025, decision DA-2 del humano del 2026-09-02)
-- ===========================================================================
-- ESTE FICHERO YA NO SE EJECUTA TAL CUAL. `build_stg_step` sustituye el
-- marcador F025_FILTRO_OBRAS de abajo por las obras que se reconstruyen esta
-- noche y le antepone el DELETE de esas MISMAS obras, todo en una sola
-- transaccion. Una sola pasada: este fichero no tiene ventanas ni explosion
-- de filas, asi que no necesita los tramos de 08_plan_mensual.sql.
--
-- POR QUE DESAPARECIO EL `TRUNCATE TABLE stg.presupuesto` QUE HABIA AQUI.
-- Desde F-025 solo se reconstruyen 40 obras de 920: truncar habria borrado
-- las otras 880 y dejado la tabla con 40. El humano lo prohibio con estas
-- palabras: "que no se reconstruyan, pero que NO SE BORREN, y que la
-- informacion este consultable". El borrado ahora se DERIVA de lo que se va a
-- escribir -se borran exactamente las obras que se van a reinsertar, en la
-- misma transaccion-, asi que es imposible borrar una obra que luego no se
-- reescriba. No hay dos listas que puedan desincronizarse: es la misma.
--
-- Y REPARA UNA AVERIA DE PASO: si un fallo interrumpe la carga, las obras ya
-- procesadas estan al dia y las demas conservan su ultima version buena. La
-- tabla queda COHERENTE, no truncada. Es lo que le faltaba a la nocturna del
-- 2026-09-02, que murio dejando stg.plan_mensual al 21,6 %.
--
-- EL CORTE POR OBRA ES SEGURO, y no es una intuicion: el DISTINCT ON de abajo
-- empieza por `pp.obride`, asi que la deduplicacion nunca cruza obras y el
-- resultado filtrado es identico al de una pasada entera. Es la misma
-- propiedad estructural que hace seguro el troceado de F-019.
--
-- EL FILTRO VA COMO COMENTARIO SQL A PROPOSITO: un fichero al que le falte la
-- sustitucion NO es SQL valido (`= ANY ()`), asi que no puede colarse una
-- ejecucion sin filtro por descuido. Misma defensa que F019_FILTRO_OBRAS.
--
-- NI UNA LINEA DE LA LOGICA DE NEGOCIO CAMBIA.
-- ===========================================================================

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
    --   redondea can a decc y pre a decp ANTES de multiplicar; resultado a deci
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
  AND pp.obride = ANY (/*F025_FILTRO_OBRAS*/)   -- ventana de negocio (F-025)
ORDER BY pp.obride, pp.paride, pp.amb, COALESCE(pp.fas, 0), pp.ide DESC;
