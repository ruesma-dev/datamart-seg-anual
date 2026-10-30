-- etl_sigrid/infrastructure/postgres/sql/tesoreria/09_albaranes_pendientes.sql
-- ============================================================================
-- F-150 · SCHEMA tesoreria (9/9): LOS ALBARANES PENDIENTES DE FACTURAR, NETOS
-- POR PROVEEDOR (N11, R33-R35)
--
-- QUE ES: lo que de verdad queda por facturar de los albaranes de cada obra de
-- la receta (el paso 7, H20 y H27). `compras.v_pbi_albaranes_sin_facturar` suma
-- solo las lineas con pendiente > 0 (56,9 M EUR en las 21 obras el 29-10), pero
-- 48,2 de esos millones ya estan SOBREFACTURADOS al mismo proveedor en otras
-- lineas (pendiente < 0): lo real es el NETO por (obra, proveedor), con suelo 0
-- (8,76 M EUR). No es caja: es el ingrediente que la receta fecha con H20 y
-- descarta con H27.
--
-- LOS PASOS, en una transaccion (este fichero entero):
--   1. `_alb_obra`: el universo, las obras de `tesoreria.devengo_corte_obra` en
--      COSTE (su empresa, su clave y su ultimo cierre).
--   2. `_alb_linea`: cada linea de albaran (`raw.dcapro`) de esas obras con
--      serie AC o PROF (`SERIES_ALBARAN_PENDIENTE` del dominio), su proveedor,
--      su contrato (el de cabecera y, si no, el de la linea), su fecha y su
--      pendiente de facturar con la formula de `compras/01_documentos.sql`
--      COPIADA letra a letra (un test compara el texto). Fuera las lineas sin
--      pendiente y las de `R-ALBARAN-ABSURDO` (|importe| o |pendiente| >= 1e8,
--      `UMBRAL_IMPORTE_ABSURDO`). Lee `raw` y no `compras`: `compras` se
--      construye DESPUES de `tesoreria` y daria el pendiente de la vispera.
--   3. `_alb_fifo`: FIFO (`neto_fifo` del dominio). Por (obra, proveedor), lo
--      sobrefacturado (Σ |negativos|) compensa las positivas empezando por la
--      mas antigua (orden fecha, linea). Sin proveedor no compensa nada.
--   4. `TRUNCATE` + `INSERT` agrupando por (obra, proveedor, contrato, mes):
--      bruto, sobrefacturado, compensado y neto; la antiguedad en meses hasta el
--      mes del build (sin fecha, NULL) y `tras_cierre` (mes posterior al ultimo
--      cierre, o la obra sin cierre: ya es devengo pendiente).
--   5. Guarda (R35): por (obra, proveedor), Σ neto = max(0, Σ bruto - Σ
--      sobrefacturado) (sin proveedor, Σ bruto), y ninguna linea con lo
--      compensado fuera de [0, bruto]. Si no, falla con el recuento: la
--      transaccion se deshace y quedan las filas de ayer.
--
-- Lee de: raw.dcapro, raw.dca, raw.con, tesoreria.devengo_corte_obra.
-- Escribe en: tesoreria.albaranes_pendientes_neto.
-- ============================================================================

-- Guarda de entrada: sin sus fuentes, falla antes de vaciar nada.
DO $$
BEGIN
    IF to_regclass('raw.dca') IS NULL
       OR to_regclass('raw.dcapro') IS NULL
       OR to_regclass('raw.con') IS NULL
       OR to_regclass('tesoreria.devengo_corte_obra') IS NULL THEN
        RAISE EXCEPTION 'albaranes_pendientes: falta una fuente (raw.dca, raw.dcapro, raw.con o tesoreria.devengo_corte_obra)';
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 1 · el universo: las obras de la receta
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE _alb_obra ON COMMIT DROP AS
SELECT k.obra_id, k.empresa_id, k.clave_obra, k.mes_ultimo_cierre
FROM tesoreria.devengo_corte_obra k WHERE k.concepto = 'COSTE';
ANALYZE _alb_obra;

-- ---------------------------------------------------------------------------
-- 2 · las lineas con pendiente de facturar
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE _alb_linea ON COMMIT DROP AS
SELECT x.linea_id, x.obra_id, x.proveedor_id, x.contrato_id, x.fecha, x.pendiente
FROM (
  SELECT x0.linea_id, x0.obra_id, x0.proveedor_id, x0.contrato_id, x0.fecha,
         x0.tot, x0.importe_pendiente_facturar AS pendiente
  FROM (
    SELECT
        l.ide                                   AS linea_id,
        o.obra_id                               AS obra_id,
        NULLIF(a.entide, 0)                     AS proveedor_id,
        COALESCE(NULLIF(a.ctride, 0), CASE WHEN l.docoritip = 44 THEN NULLIF(l.docoriide, 0) END) AS contrato_id,
        tesoreria.fn_fecha(c.fec)               AS fecha,
        COALESCE(l.tot, 0)                      AS tot,
        -- COPIA de `importe_pendiente_facturar` de `compras/01_documentos.sql`.
        CASE
            WHEN COALESCE(l.can, 0) = 0 THEN
                CASE WHEN COALESCE(l.canfac, 0) <> 0 THEN 0::NUMERIC(18,2)
                     ELSE COALESCE(l.tot, 0)::NUMERIC(18,2) END
            ELSE
                ROUND((COALESCE(l.tot, 0)
                       * (1 - COALESCE(l.canfac, 0) / l.can))::NUMERIC, 2)
        END                                     AS importe_pendiente_facturar
    FROM raw.dcapro l
    JOIN raw.dca a ON a.ide = l.docide
    JOIN raw.con c ON c.ide = a.ide
    JOIN _alb_obra o ON o.obra_id = NULLIF(l.obride, 0)
    WHERE tesoreria.fn_serie(c.cod) IN ('AC', 'PROF')
  ) x0
) x
WHERE x.pendiente <> 0
  AND abs(x.tot) < 1e8
  AND abs(x.pendiente) < 1e8;
ANALYZE _alb_linea;

-- ---------------------------------------------------------------------------
-- 3 · FIFO: lo sobrefacturado compensa primero lo mas antiguo
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE _alb_fifo ON COMMIT DROP AS
SELECT
    y.linea_id,
    y.obra_id,
    y.proveedor_id,
    y.contrato_id,
    y.fecha,
    y.pendiente,
    GREATEST(y.pendiente, 0) AS bruto,
    GREATEST(-y.pendiente, 0) AS sobrefacturado,
    CASE WHEN y.pendiente > 0 THEN LEAST(y.pendiente, GREATEST(0, y.a_compensar - (y.acumulado - y.pendiente))) ELSE 0 END AS compensado
FROM (
    SELECT
        x.*,
        CASE WHEN x.proveedor_id IS NULL THEN 0 ELSE SUM(GREATEST(-x.pendiente, 0)) OVER (PARTITION BY x.obra_id, x.proveedor_id) END AS a_compensar,
        SUM(GREATEST(x.pendiente, 0)) OVER (PARTITION BY x.obra_id, x.proveedor_id ORDER BY x.fecha NULLS FIRST, x.linea_id) AS acumulado
    FROM _alb_linea x
) y;
ANALYZE _alb_fifo;

-- ---------------------------------------------------------------------------
-- 4 · la tabla: por (obra, proveedor, contrato, mes del albaran)
-- ---------------------------------------------------------------------------
TRUNCATE tesoreria.albaranes_pendientes_neto;

INSERT INTO tesoreria.albaranes_pendientes_neto (
    obra_id, empresa_id, clave_obra, proveedor_id, contrato_id, mes_albaran,
    importe_pendiente_bruto, importe_sobrefacturado, importe_compensado,
    importe_pendiente_neto, meses_antiguedad, tras_cierre
)
SELECT
    f.obra_id                                       AS obra_id,
    o.empresa_id                                    AS empresa_id,
    o.clave_obra                                    AS clave_obra,
    f.proveedor_id                                  AS proveedor_id,
    f.contrato_id                                   AS contrato_id,
    date_trunc('month', f.fecha)::DATE AS mes_albaran,
    SUM(f.bruto)                                    AS importe_pendiente_bruto,
    SUM(f.sobrefacturado)                           AS importe_sobrefacturado,
    SUM(f.compensado)                               AS importe_compensado,
    SUM(f.bruto - f.compensado) AS importe_pendiente_neto,
    (date_part('year', age(date_trunc('month', CURRENT_DATE), date_trunc('month', f.fecha))) * 12 + date_part('month', age(date_trunc('month', CURRENT_DATE), date_trunc('month', f.fecha))))::INTEGER AS meses_antiguedad,
    COALESCE(o.mes_ultimo_cierre IS NULL OR date_trunc('month', f.fecha)::DATE > o.mes_ultimo_cierre, FALSE) AS tras_cierre
FROM _alb_fifo f
JOIN _alb_obra o ON o.obra_id = f.obra_id
GROUP BY f.obra_id, o.empresa_id, o.clave_obra, f.proveedor_id, f.contrato_id,
         date_trunc('month', f.fecha), o.mes_ultimo_cierre
HAVING SUM(f.bruto) > 0 OR SUM(f.sobrefacturado) > 0;

-- ---------------------------------------------------------------------------
-- 5 · guarda (R35): el neto por proveedor es max(0, bruto - sobrefacturado)
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    n_pares  INTEGER;
    n_lineas INTEGER;
BEGIN
    SELECT count(*) INTO n_pares
      FROM (
        SELECT t.obra_id, t.proveedor_id,
               SUM(t.importe_pendiente_neto) AS neto,
               SUM(t.importe_pendiente_bruto) AS bruto,
               SUM(t.importe_sobrefacturado) AS sobrefacturado
          FROM tesoreria.albaranes_pendientes_neto t
         GROUP BY t.obra_id, t.proveedor_id
      ) p
     WHERE p.neto <> CASE WHEN p.proveedor_id IS NULL THEN p.bruto ELSE GREATEST(0, p.bruto - p.sobrefacturado) END;
    SELECT count(*) INTO n_lineas
      FROM _alb_fifo f
     WHERE f.compensado < 0 OR f.compensado > f.bruto;
    IF n_pares > 0 OR n_lineas > 0 THEN
        RAISE EXCEPTION 'albaranes_pendientes: % pares (obra, proveedor) con el neto distinto de max(0, bruto - sobrefacturado) y % lineas con lo compensado fuera de [0, bruto]', n_pares, n_lineas;
    END IF;
END $$;

COMMENT ON TABLE tesoreria.albaranes_pendientes_neto IS
'F-150. Los albaranes y proformas (series AC y PROF) pendientes de facturar de las obras de la receta (las de devengo_corte_obra), NETOS por proveedor: por (obra, proveedor), lo sobrefacturado (lineas con pendiente < 0) compensa primero las entregas mas antiguas (FIFO) y el residuo sobrefacturado no se publica como negativo (suelo 0). Pendiente con la formula de compras.albaran_lineas, sin las lineas de R-ALBARAN-ABSURDO. Por fila: bruto (lineas > 0), sobrefacturado, compensado y neto = bruto - compensado, sin IVA; meses_antiguedad hasta el mes del build (para H27) y tras_cierre (mes posterior al ultimo cierre: ya es devengo pendiente). Sin proveedor, la linea no compensa. No es caja. Clave: obra_id, proveedor_id, contrato_id, mes_albaran (NULLS NOT DISTINCT).';
