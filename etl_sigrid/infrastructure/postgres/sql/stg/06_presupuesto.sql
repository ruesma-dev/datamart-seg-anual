-- etl_sigrid/infrastructure/postgres/sql/stg/06_presupuesto.sql
--
-- Materializa stg.presupuesto a partir de raw.obrparpre.
--
-- Filtros: solo obride NOT NULL (preservamos cierres con valor 0 = estornos).
--
-- DEDUPLICACIÓN: DISTINCT ON por clave de negocio (obra, partida, amb, fase)
-- quedándonos con el `ide` MAYOR (la corrección más reciente de Sigrid).
--
-- PRECISIÓN (ambas columnas NUMERIC(20,6)):
--   - precio: raw.obrparpre.pre tiene hasta 6 decimales reales (ej. 115.294961)
--   - cantidad: raw.obrparpre.can para CP* contiene porcentajes con hasta
--     6 decimales (ej. 0.00025 para CP.4 AVALES). Truncar a 4 decimales
--     causa gap material en el Plan (caso real 0696 mayo 2025: +83,71 €).
--
-- COLUMNAS DE IMPORTE (Tanda 1.6):
--   - importe         = ROUND(can*pre, 2). Usado por mart/plan_mensual y toda
--                       la planificación valorada. NO se altera para no
--                       introducir regresión en lo existente.
--   - importe_oficial = COALESCE(NULLIF(impcoe, 0), importe). Usado por el
--                       schema cierre para que el FINAL master cuadre con
--                       la pantalla de Sigrid (que usa impcoe).
--                       Si impcoe está vacío (≈70% de los registros), cae al
--                       importe calculado (comportamiento idéntico al actual).

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
    ROUND((pp.can::NUMERIC(20,6) * pp.pre::NUMERIC(20,6))::NUMERIC, 2) AS importe,
    -- importe_oficial: prioriza impcoe (Sigrid con coeficientes aplicados)
    -- y cae a can*pre si impcoe es NULL o 0 (≈70% de los registros).
    COALESCE(
        NULLIF(pp.impcoe::NUMERIC(18,2), 0),
        ROUND((pp.can::NUMERIC(20,6) * pp.pre::NUMERIC(20,6))::NUMERIC, 2)
    )                                                 AS importe_oficial,
    pp._source_tiemod
FROM raw.obrparpre pp
WHERE pp.obride IS NOT NULL
ORDER BY pp.obride, pp.paride, pp.amb, COALESCE(pp.fas, 0), pp.ide DESC;
