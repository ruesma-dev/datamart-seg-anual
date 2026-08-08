-- etl_sigrid/infrastructure/postgres/sql/retenciones/01_movimientos.sql
-- ============================================================================
-- retenciones.movimientos — un registro por efecto de retención.
--
-- Unifica en una sola tabla las dos direcciones:
--   sentido = 'PROVEEDOR' → la practicamos nosotros (raw.pag). Es dinero
--             nuestro que aún no hemos pagado al subcontratista/suministrador.
--   sentido = 'CLIENTE'   → nos la practica el cliente (raw.cob). Es dinero
--             nuestro que aún no hemos cobrado.
--
-- Estado:
--   VIVA      fecrea = 0  → sigue retenida
--   LIQUIDADA fecrea <> 0 → ya devuelta/cobrada, en esa fecha
--
-- Los importes NEGATIVOS se conservan con su signo (son ajustes o
-- devoluciones registradas como efecto negativo). Por eso se exponen a la vez
-- `importe` (neto, con signo) y las columnas separadas de cargo/abono.
-- ============================================================================

DROP TABLE IF EXISTS retenciones.movimientos CASCADE;
CREATE TABLE retenciones.movimientos AS

-- ---------------------------------------------------------------------------
-- RETENCIONES A PROVEEDOR (raw.pag)
-- ---------------------------------------------------------------------------
WITH obras_doc_compra AS (
    -- Obra(s) del documento origen, sin multiplicar: una fila por factura
    SELECT
        fp.docide                          AS documento_id,
        COUNT(DISTINCT NULLIF(fp.obride, 0)) AS num_obras,
        MIN(NULLIF(fp.obride, 0))          AS obra_unica
    FROM retenciones.v_src_lineas_compra fp
    WHERE NULLIF(fp.obride, 0) IS NOT NULL
    GROUP BY fp.docide
),
obras_doc_venta AS (
    SELECT
        vp.docide                          AS documento_id,
        COUNT(DISTINCT NULLIF(vp.obride, 0)) AS num_obras,
        MIN(NULLIF(vp.obride, 0))          AS obra_unica
    FROM retenciones.v_src_lineas_venta vp
    WHERE NULLIF(vp.obride, 0) IS NOT NULL
    GROUP BY vp.docide
)

SELECT
    'PROVEEDOR'::VARCHAR(10)                AS sentido,
    p.ide                                   AS movimiento_id,
    p.retide                                AS tipo_id,
    tp.descripcion                          AS tipo_descripcion,
    -- Documento origen (factura de compra)
    NULLIF(p.conide, 0)                     AS documento_id,
    doc.cod                                 AS codigo_documento,
    doc.tip                                 AS tipo_documento,
    retenciones.fn_sigrid_date(doc.fec)     AS fecha_documento,
    -- Entidad (proveedor)
    NULLIF(p.entide, 0)                     AS entidad_id,
    ent.res                                 AS entidad_nombre,
    prv.cif                                 AS entidad_cif,
    -- Obra: prioridad al centro de coste del efecto
    COALESCE(NULLIF(p.cenide, 0),
             CASE WHEN od.num_obras = 1 THEN od.obra_unica END) AS obra_id,
    COALESCE(cen_con.cod, obr_con.cod)      AS codigo_obra,
    COALESCE(cen_con.res, obr_con.res)      AS nombre_obra,
    COALESCE(od.num_obras, 0)               AS num_obras_documento,
    -- Importes (con signo)
    COALESCE(p.tot, 0)::NUMERIC(18, 2)      AS importe,
    -- Fechas
    retenciones.fn_sigrid_date(p.fecven)    AS fecha_prevista_devolucion,
    retenciones.fn_sigrid_date(p.fecrea)    AS fecha_devolucion_real,
    -- Estado
    CASE WHEN COALESCE(p.fecrea, 0) = 0
         THEN 'VIVA' ELSE 'LIQUIDADA' END::VARCHAR(10) AS estado,
    -- ¿Vencida y sin devolver?
    CASE WHEN COALESCE(p.fecrea, 0) = 0
          AND retenciones.fn_sigrid_date(p.fecven) IS NOT NULL
          AND retenciones.fn_sigrid_date(p.fecven) < CURRENT_DATE
         THEN TRUE ELSE FALSE END           AS vencida_sin_liquidar,
    (CURRENT_DATE - retenciones.fn_sigrid_date(p.fecven)) AS dias_desde_vencimiento
FROM raw.pag p
LEFT JOIN retenciones.tipos tp ON tp.tipo_id = p.retide
LEFT JOIN raw.con doc     ON doc.ide = NULLIF(p.conide, 0)
LEFT JOIN raw.con ent     ON ent.ide = NULLIF(p.entide, 0)
LEFT JOIN raw.prv prv     ON prv.ide = NULLIF(p.entide, 0)
LEFT JOIN raw.con cen_con ON cen_con.ide = NULLIF(p.cenide, 0)
LEFT JOIN obras_doc_compra od ON od.documento_id = NULLIF(p.conide, 0)
LEFT JOIN raw.con obr_con ON obr_con.ide = CASE WHEN od.num_obras = 1
                                                THEN od.obra_unica END
WHERE COALESCE(p.retide, 0) <> 0

UNION ALL

-- ---------------------------------------------------------------------------
-- RETENCIONES DE CLIENTE (raw.cob)
-- ---------------------------------------------------------------------------
SELECT
    'CLIENTE'::VARCHAR(10)                  AS sentido,
    c.ide                                   AS movimiento_id,
    c.retide                                AS tipo_id,
    tp.descripcion                          AS tipo_descripcion,
    NULLIF(c.conide, 0)                     AS documento_id,
    doc.cod                                 AS codigo_documento,
    doc.tip                                 AS tipo_documento,
    retenciones.fn_sigrid_date(doc.fec)     AS fecha_documento,
    NULLIF(c.entide, 0)                     AS entidad_id,
    ent.res                                 AS entidad_nombre,
    NULL::VARCHAR(24)                       AS entidad_cif,
    COALESCE(NULLIF(c.cenide, 0),
             CASE WHEN od.num_obras = 1 THEN od.obra_unica END) AS obra_id,
    COALESCE(cen_con.cod, obr_con.cod)      AS codigo_obra,
    COALESCE(cen_con.res, obr_con.res)      AS nombre_obra,
    COALESCE(od.num_obras, 0)               AS num_obras_documento,
    COALESCE(c.tot, 0)::NUMERIC(18, 2)      AS importe,
    retenciones.fn_sigrid_date(c.fecven)    AS fecha_prevista_devolucion,
    retenciones.fn_sigrid_date(c.fecrea)    AS fecha_devolucion_real,
    CASE WHEN COALESCE(c.fecrea, 0) = 0
         THEN 'VIVA' ELSE 'LIQUIDADA' END::VARCHAR(10) AS estado,
    CASE WHEN COALESCE(c.fecrea, 0) = 0
          AND retenciones.fn_sigrid_date(c.fecven) IS NOT NULL
          AND retenciones.fn_sigrid_date(c.fecven) < CURRENT_DATE
         THEN TRUE ELSE FALSE END           AS vencida_sin_liquidar,
    (CURRENT_DATE - retenciones.fn_sigrid_date(c.fecven)) AS dias_desde_vencimiento
FROM raw.cob c
LEFT JOIN retenciones.tipos tp ON tp.tipo_id = c.retide
LEFT JOIN raw.con doc     ON doc.ide = NULLIF(c.conide, 0)
LEFT JOIN raw.con ent     ON ent.ide = NULLIF(c.entide, 0)
LEFT JOIN raw.con cen_con ON cen_con.ide = NULLIF(c.cenide, 0)
LEFT JOIN obras_doc_venta od ON od.documento_id = NULLIF(c.conide, 0)
LEFT JOIN raw.con obr_con ON obr_con.ide = CASE WHEN od.num_obras = 1
                                                THEN od.obra_unica END
WHERE COALESCE(c.retide, 0) <> 0;

ALTER TABLE retenciones.movimientos ADD PRIMARY KEY (sentido, movimiento_id);
CREATE INDEX idx_ret_mov_sentido  ON retenciones.movimientos (sentido);
CREATE INDEX idx_ret_mov_obra     ON retenciones.movimientos (obra_id);
CREATE INDEX idx_ret_mov_entidad  ON retenciones.movimientos (entidad_id);
CREATE INDEX idx_ret_mov_estado   ON retenciones.movimientos (estado);
CREATE INDEX idx_ret_mov_fecven   ON retenciones.movimientos (fecha_prevista_devolucion);

COMMENT ON TABLE retenciones.movimientos IS
'Un registro por efecto de retención (Tanda R1). sentido PROVEEDOR = la '
'practicamos nosotros (raw.pag); CLIENTE = nos la practican (raw.cob). '
'estado VIVA = fecrea 0 (aún retenida). Importes con signo: los negativos '
'son ajustes/devoluciones. Obra resuelta por cenide del efecto, con fallback '
'a las líneas del documento origen si apuntan a una sola obra.';
