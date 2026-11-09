-- etl_sigrid/infrastructure/postgres/sql/ventas/04_enlace.sql
-- ============================================================================
-- F-040 · VENTAS (5/8): ventas.certificacion_factura y ventas.cobertura_enlace
-- (R16, R20).
--
-- EL ENLACE certificacion -> factura (R16) es `raw.cerprodes`: los destinos de
-- las lineas de certificacion. Con `docdestip` = 11 el destino es una factura
-- de venta; el 100 % de las 4.349 filas el 2026-11-06. `cer.idefac` y
-- `cer.feccob` estan a 0 en todas y NO sirven. Es N:M (268 facturas de dos
-- certificaciones, 71 certificaciones con dos facturas...): una fila por PAR,
-- con el numero de lineas y la cantidad pasada, SIN repartir importes. El
-- `JOIN raw.dvf` descarta un destino que no existe.
--
-- LA COBERTURA (R20): por noche y eslabon, cuantos documentos tienen el
-- siguiente y por cuanto importe. Tres eslabones:
--   CERTIFICACION_FACTURA: certificaciones que CUENTAN (estados 2-4) con factura.
--   FACTURA_EFECTO: facturas con algun efecto de cobro (`raw.cob.conide`).
--   EFECTO_FACTURA: efectos de cobro que apuntan a una factura. Lo que no
--     (los agrupados `AGR`, las divisiones `DIV`) no se atribuye: lo explicara
--     F-104.
-- El eslabon de efectos lee `raw.cob` y no `tesoreria.efectos`: no espera a
-- otro paso.
--
-- Importes de `raw` en `double precision`: se castean a NUMERIC (sin ROUND).
--
-- Lee de: raw.cerprodes, raw.cerpro, raw.dvf, raw.cob, ventas.certificaciones
--         y ventas.facturas.
-- Escribe en: ventas.certificacion_factura, ventas.cobertura_enlace.
-- ============================================================================

DROP TABLE IF EXISTS ventas.cobertura_enlace CASCADE;
DROP TABLE IF EXISTS ventas.certificacion_factura CASCADE;

CREATE TABLE ventas.certificacion_factura AS
SELECT
    p.docide                                                AS certificacion_id,
    d.docdeside                                             AS factura_id,
    count(*)                                                AS num_lineas,
    SUM(COALESCE(d.can, 0)::NUMERIC(18, 4))                 AS cantidad
FROM raw.cerprodes d
JOIN raw.cerpro p ON p.ide = d.docproide
JOIN raw.dvf f ON f.ide = d.docdeside
WHERE d.docdestip = 11
GROUP BY p.docide, d.docdeside;

ALTER TABLE ventas.certificacion_factura ADD PRIMARY KEY (certificacion_id, factura_id);
CREATE INDEX IF NOT EXISTS idx_ven_cf_factura ON ventas.certificacion_factura (factura_id);

COMMENT ON TABLE ventas.certificacion_factura IS
'F-040. Una fila por par (certificacion, factura de venta) de raw.cerprodes con docdestip = 11: el numero de lineas de la certificacion que pasaron a esa factura y la cantidad pasada. Es N:M: no reparte importes; sumar lo facturado o lo cobrado por certificacion cuenta dos veces una factura compartida. Clave: certificacion_id, factura_id.';

CREATE TABLE ventas.cobertura_enlace AS
WITH certificaciones_enlazadas AS (
    SELECT DISTINCT cf.certificacion_id FROM ventas.certificacion_factura cf
)
, facturas_con_efecto AS (
    SELECT DISTINCT c.conide AS factura_id FROM raw.cob c WHERE COALESCE(c.conide, 0) <> 0
)
, eslabones AS (
    SELECT 1 AS orden, 'CERTIFICACION_FACTURA'::VARCHAR(24) AS eslabon,
           count(*) AS total, count(e.certificacion_id) AS enlazados,
           SUM(k.base) AS importe_total,
           SUM(k.base) FILTER (WHERE e.certificacion_id IS NOT NULL) AS importe_enlazado
    FROM ventas.certificaciones k
    LEFT JOIN certificaciones_enlazadas e ON e.certificacion_id = k.certificacion_id
    WHERE k.cuenta
    UNION ALL
    SELECT 2, 'FACTURA_EFECTO'::VARCHAR(24),
           count(*), count(e.factura_id),
           SUM(f.base),
           SUM(f.base) FILTER (WHERE e.factura_id IS NOT NULL)
    FROM ventas.facturas f
    LEFT JOIN facturas_con_efecto e ON e.factura_id = f.factura_id
    UNION ALL
    SELECT 3, 'EFECTO_FACTURA'::VARCHAR(24),
           count(*), count(f.ide),
           SUM(COALESCE(c.tot, 0)::NUMERIC(18, 2)),
           SUM(COALESCE(c.tot, 0)::NUMERIC(18, 2)) FILTER (WHERE f.ide IS NOT NULL)
    FROM raw.cob c
    LEFT JOIN raw.dvf f ON f.ide = NULLIF(c.conide, 0)
)
SELECT
    s.eslabon                                               AS eslabon,
    s.total                                                 AS total,
    s.enlazados                                             AS enlazados,
    COALESCE(s.importe_total, 0)::NUMERIC(18, 2)            AS importe_total,
    COALESCE(s.importe_enlazado, 0)::NUMERIC(18, 2)         AS importe_enlazado,
    now()                                                   AS calculado_en
FROM eslabones s
ORDER BY s.orden;

ALTER TABLE ventas.cobertura_enlace ADD PRIMARY KEY (eslabon);

COMMENT ON TABLE ventas.cobertura_enlace IS
'F-040. La cobertura del enlace certificacion -> factura -> cobro de la ultima noche, una fila por eslabon: CERTIFICACION_FACTURA (certificaciones que cuentan, estados 2-4, con factura), FACTURA_EFECTO (facturas con efecto de cobro) y EFECTO_FACTURA (efectos de cobro con factura; los agrupados AGR no). Total, enlazados, importe total y enlazado (base, o importe del efecto) y el momento del calculo. Clave: eslabon.';
