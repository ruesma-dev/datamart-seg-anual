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
-- ESTADO (F-094, 2026-09-22) — distinto en cada sentido, a propósito
-- ---------------------------------------------------------------------------
-- El efecto de pago/cobro ES un documento: `raw.pag`/`raw.cob` son propiedades
-- de `raw.con` (tip 25 / 24), y su estado (`con.est`) y su baja (`con.fecbaj`)
-- viven en la ficha `raw.con` DEL PROPIO EFECTO (`con.ide = p.ide`), no en la
-- del documento origen (`p.conide`), que es la única que se unía antes.
--
-- PROVEEDOR (raw.pag). Tres valores, en este orden de precedencia:
--   BAJA      con.fecbaj <> 0 OR con.est IN (14, 15)
--             El efecto se sustituyó por otro y SU DINERO YA CUENTA ALLÍ:
--             14 = «Agrupados» (el original, con fecbaj = fecha del efecto
--             agrupador AGR, que lleva la suma), 15 = «Divididos» (el padre de
--             una división, sustituido por sus hijos) y los anulados. Catálogo
--             de estados del tip 25 leído en raw.conest el 2026-09-22.
--   LIQUIDADA fecrea <> 0 OR con.est = 10 («Pagado»)
--             Incluye los agrupadores AGR ya pagados en remesa, que Sigrid
--             deja con fecrea = 0.
--   VIVA      el resto: fecrea = 0 AND fecbaj = 0 AND est NOT IN (10, 14, 15)
--
--   PRECEDENCIA: BAJA manda sobre LIQUIDADA. Medido el 2026-09-22: solo 2
--   efectos (1.000,84 €) tienen a la vez fecbaj y fecrea, ninguno est 10 tiene
--   fecbaj y ningún est 14 tiene fecrea. Si una baja con fecrea contara como
--   LIQUIDADA, su importe se sumaría a lo liquidado junto al del efecto que la
--   sustituye: el mismo dinero dos veces. Como BAJA no suma en ninguna lectura.
--
--   Antes de F-094 el estado salía SOLO de fecrea y publicaba 35,54 M€ vivos
--   a proveedor; con este criterio son 8,35 M€ (7.752 efectos), y FERMALUX
--   (entidad 1958815) da 64.201,96 €, igual que el saldo de su cuenta 4108.
--   NO SE BORRA NINGUNA FILA: se reclasifican. Detalle: progress/impl_F-094.md.
--
-- CLIENTE (raw.cob). SIGUE: VIVA fecrea = 0, LIQUIDADA fecrea <> 0.
--   El criterio de proveedor NO vale aquí: los ~19,9 M€ de cob con fecbaj <> 0
--   están en est 1 (Pendiente), no en 14/15, y aplicarlo deja 2,12 M€ frente a
--   13,81 M€ de su contabilidad. Queda para una feature propia; mientras,
--   `estado_sigrid` y `fecha_baja` se publican también aquí, solo informativos.
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
    -- Estado (F-094): ficha del propio efecto; BAJA manda, ver cabecera
    CASE WHEN COALESCE(efe.fecbaj, 0) <> 0 OR efe.est IN (14, 15) THEN 'BAJA'
         WHEN COALESCE(p.fecrea, 0) <> 0 OR efe.est = 10 THEN 'LIQUIDADA'
         ELSE 'VIVA' END::VARCHAR(10) AS estado,
    efe.est                                 AS estado_sigrid,
    retenciones.fn_sigrid_date(efe.fecbaj)  AS fecha_baja,
    -- ¿Vencida y sin devolver? Solo una VIVA puede estarlo
    CASE WHEN COALESCE(p.fecrea, 0) = 0
          AND COALESCE(efe.fecbaj, 0) = 0
          AND COALESCE(efe.est, 0) NOT IN (10, 14, 15)
          AND retenciones.fn_sigrid_date(p.fecven) IS NOT NULL
          AND retenciones.fn_sigrid_date(p.fecven) < CURRENT_DATE
         THEN TRUE ELSE FALSE END           AS vencida_sin_liquidar,
    (CURRENT_DATE - retenciones.fn_sigrid_date(p.fecven)) AS dias_desde_vencimiento
FROM raw.pag p
LEFT JOIN raw.con efe ON efe.ide = p.ide  -- ficha del EFECTO: est y fecbaj
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
    -- Estado: SOLO fecrea, sin cambios en F-094 (ver cabecera: CLIENTE)
    CASE WHEN COALESCE(c.fecrea, 0) = 0
         THEN 'VIVA' ELSE 'LIQUIDADA' END::VARCHAR(10) AS estado,
    efe.est                                 AS estado_sigrid,
    retenciones.fn_sigrid_date(efe.fecbaj)  AS fecha_baja,
    CASE WHEN COALESCE(c.fecrea, 0) = 0
          AND retenciones.fn_sigrid_date(c.fecven) IS NOT NULL
          AND retenciones.fn_sigrid_date(c.fecven) < CURRENT_DATE
         THEN TRUE ELSE FALSE END           AS vencida_sin_liquidar,
    (CURRENT_DATE - retenciones.fn_sigrid_date(c.fecven)) AS dias_desde_vencimiento
FROM raw.cob c
LEFT JOIN raw.con efe ON efe.ide = c.ide  -- ficha del EFECTO: solo informativa
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
'estado (F-094): en PROVEEDOR, BAJA si el efecto tiene fecbaj o est 14/15 '
'(agrupado, dividido o anulado: su dinero cuenta en otro efecto), LIQUIDADA '
'si tiene fecrea o est 10 (Pagado), VIVA el resto; en CLIENTE, VIVA = '
'fecrea 0. Ninguna lectura suma BAJA. Importes con signo: los negativos '
'son ajustes/devoluciones. Obra resuelta por cenide del efecto, con fallback '
'a las líneas del documento origen si apuntan a una sola obra.';
