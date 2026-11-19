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
-- CLIENTE (raw.cob), desde F-104 (2026-11-18): LA MISMA PRECEDENCIA.
--   BAJA si con.fecbaj <> 0 OR con.est IN (14, 15); LIQUIDADA si fecrea <> 0
--   OR con.est = 10 («Cobrado», remesas sin fecrea); VIVA el resto.
--   EL MECANISMO, distinto de pag: en cob el original agrupado NO pasa a est 14,
--   se queda en est 1 (Pendiente) con fecbaj = fecha del AGR que lo sustituye.
--   Por eso el criterio por est no casaba y el de fecbaj si. Caso medido
--   (cuenta 4308001150, FUNDACION TERTIO MILLENNIO): los cinco efectos de
--   2016-17, 57.973,72 EUR, tienen fecbaj 2020-03-04 y AGR20/0010 suma
--   exactamente 57.973,72 en la misma cuenta y ese dia; sus DIV se cobran y
--   DIV20/0010, 12.000,00, sigue vivo: el saldo de la cuenta en la contabilidad.
--   EL DINERO AGRUPADO: el AGR y sus DIV llevan retide = 0, asi que la rama
--   CLIENTE entra tambien los efectos de cob cuya cuenta (cueide) es de
--   retencion de cliente (retenciones.cuentas_cliente, al principio de este
--   fichero). `origen_retencion` dice por cual de los dos entra:
--   EFECTO_RETENCION (retide <> 0) o CUENTA_RETENCION (solo por la cuenta, sin
--   tipo: tipo_id NULL). En PROVEEDOR siempre EFECTO_RETENCION.
--   Medido el 2026-11-16: CLIENTE pasa de 2.256 a 3.461 filas y lo VIVA de
--   22,44 M EUR a 10,53 M EUR (347 efectos; 2,40 M con retide). La retencion
--   viva de cliente la MANDA LA CONTABILIDAD (16,00 M EUR):
--   retenciones.saldo_contable_cliente y v_cuadre_cliente (08_saldo_cliente.sql).
--   `entidad_cif` sigue NULL en CLIENTE (D9): el CIF esta en ventas.clientes.
--
-- OBRA (F-094, ampliación H6 aprobada el 2026-09-22: absorbe el resto de F-045)
-- ---------------------------------------------------------------------------
-- `centro_coste_id` = `cenide` del efecto, tal cual. `obra_id` es la OBRA de
-- verdad (el `ide` de `maestro.obras`), y ya no el centro de coste:
--   · con centro  → `maestro.centros_coste` (F-073: centro y obra son dos filas
--                   de `con` con la misma empresa y el mismo código). Si el
--                   centro no es una obra (estructura, delegación) queda NULL:
--                   ese coste no se imputa a ninguna obra.
--   · sin centro  → la obra única de las líneas del documento origen, cuyo
--                   `obride` SÍ es una obra (575 de 575 en raw.obr).
-- Antes era COALESCE(cenide, obra de las líneas): mezclaba el `ide` del centro
-- y el de la obra en la misma columna, y casaba 0 de 262 contra maestro.obras.
-- DEPENDENCIA: lee la VISTA `maestro.centros_coste`, que es SQL puro sobre
-- `raw` y existe desde F-073. `build_maestros` corre antes en `run-all` por su
-- posición; NO se declara en `depends_on` a propósito (ver el step).
--
-- Los importes NEGATIVOS se conservan con su signo (son ajustes o
-- devoluciones registradas como efecto negativo). Por eso se exponen a la vez
-- `importe` (neto, con signo) y las columnas separadas de cargo/abono.
-- ============================================================================

-- ============================================================================
-- retenciones.cuentas_cliente (F-104, D3 = a): las cuentas de retencion de
-- CLIENTE. La UNION de las que declara un cliente (raw.cli.cueretide, 1:1:
-- 211 el 2026-11-16) y las del plan de cuentas con codigo 43x8 (raw.con
-- tip = 17, las imputables; 221). Solo cueretide pierde UNEXUM (su ficha declara
-- 4308001593 y sus 947.835,66 EUR estan en 4338001593); solo el prefijo pierde
-- el cliente y 4 cuentas declaradas fuera de 43x8. criterio_seleccion dice por
-- donde entra: CUERETIDE si la declara un cliente, si no PREFIJO_43X8 (sin
-- cliente). Va aqui y no en 00_setup.sql, que protege la frontera de F-040.
-- GUARDAS (R5): la PK es la de «dos clientes declaran la misma cuenta» (el
-- build falla aqui en vez de duplicar efectos y apuntes); la de vacia, el DO.
-- ============================================================================
DROP TABLE IF EXISTS retenciones.cuentas_cliente CASCADE;
CREATE TABLE retenciones.cuentas_cliente AS
WITH declaradas AS (
    SELECT cl.cueretide::BIGINT AS cuenta_id, cl.ide AS cliente_id
    FROM raw.cli cl
    WHERE COALESCE(cl.cueretide, 0) <> 0
),
prefijo AS (
    SELECT pc.ide::BIGINT AS cuenta_id
    FROM raw.con pc
    WHERE pc.tip = 17 AND pc.cod ~ '^43[0-9]8'
)
SELECT
    COALESCE(d.cuenta_id, p.cuenta_id)  AS cuenta_id,
    d.cliente_id                        AS cliente_id,
    cue.cod                             AS codigo_cuenta,
    cue.res                             AS nombre_cuenta,
    LEFT(cue.cod, 4)                    AS familia,
    (CASE WHEN d.cuenta_id IS NOT NULL THEN 'CUERETIDE' ELSE 'PREFIJO_43X8' END)::VARCHAR(16)
                                        AS criterio_seleccion
FROM declaradas d
FULL JOIN prefijo p ON p.cuenta_id = d.cuenta_id
LEFT JOIN raw.con cue ON cue.ide = COALESCE(d.cuenta_id, p.cuenta_id);

ALTER TABLE retenciones.cuentas_cliente ADD PRIMARY KEY (cuenta_id);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM retenciones.cuentas_cliente) THEN
        RAISE EXCEPTION 'F-104 R5: retenciones.cuentas_cliente vacia: ni raw.cli.cueretide ni cuentas 43x8 en raw.con (tip 17); movimientos de cliente no se construye';
    END IF;
END $$;

COMMENT ON TABLE retenciones.cuentas_cliente IS
'F-104. Las cuentas de retencion de CLIENTE: la union de las que declara un cliente '
'(raw.cli.cueretide, criterio_seleccion CUERETIDE, con su cliente_id) y las del plan '
'de cuentas con codigo 43x8 (raw.con tip 17, PREFIJO_43X8, sin cliente). familia = 4 '
'primeros digitos, descriptiva. Una cuenta, un cliente (PK cuenta_id).';

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
    -- Obra (F-094): el centro de coste, traducido a OBRA por el puente de
    -- F-073; sin centro, la obra única de las líneas del documento
    NULLIF(p.cenide, 0)                     AS centro_coste_id,
    CASE WHEN NULLIF(p.cenide, 0) IS NOT NULL THEN cc.obra_id
         WHEN od.num_obras = 1 THEN od.obra_unica END AS obra_id,
    CASE WHEN NULLIF(p.cenide, 0) IS NOT NULL THEN cc.codigo_obra
         ELSE obr_con.cod END               AS codigo_obra,
    CASE WHEN NULLIF(p.cenide, 0) IS NOT NULL THEN cc.nombre_obra
         ELSE obr_con.res END               AS nombre_obra,
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
    (CURRENT_DATE - retenciones.fn_sigrid_date(p.fecven)) AS dias_desde_vencimiento,
    -- F-104: al FINAL y en el mismo orden en las dos ramas (UNION ALL por posicion)
    'EFECTO_RETENCION'::VARCHAR(16)         AS origen_retencion,
    NULLIF(p.cueide, 0)                     AS cuenta_id
FROM raw.pag p
LEFT JOIN raw.con efe ON efe.ide = p.ide  -- ficha del EFECTO: est y fecbaj
LEFT JOIN retenciones.tipos tp ON tp.tipo_id = p.retide
LEFT JOIN raw.con doc     ON doc.ide = NULLIF(p.conide, 0)
LEFT JOIN raw.con ent     ON ent.ide = NULLIF(p.entide, 0)
LEFT JOIN raw.prv prv     ON prv.ide = NULLIF(p.entide, 0)
LEFT JOIN maestro.centros_coste cc ON cc.centro_coste_id = NULLIF(p.cenide, 0)
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
    NULLIF(c.retide, 0)                     AS tipo_id,
    tp.descripcion                          AS tipo_descripcion,
    NULLIF(c.conide, 0)                     AS documento_id,
    doc.cod                                 AS codigo_documento,
    doc.tip                                 AS tipo_documento,
    retenciones.fn_sigrid_date(doc.fec)     AS fecha_documento,
    NULLIF(c.entide, 0)                     AS entidad_id,
    ent.res                                 AS entidad_nombre,
    NULL::VARCHAR(24)                       AS entidad_cif,
    NULLIF(c.cenide, 0)                     AS centro_coste_id,
    CASE WHEN NULLIF(c.cenide, 0) IS NOT NULL THEN cc.obra_id
         WHEN od.num_obras = 1 THEN od.obra_unica END AS obra_id,
    CASE WHEN NULLIF(c.cenide, 0) IS NOT NULL THEN cc.codigo_obra
         ELSE obr_con.cod END               AS codigo_obra,
    CASE WHEN NULLIF(c.cenide, 0) IS NOT NULL THEN cc.nombre_obra
         ELSE obr_con.res END               AS nombre_obra,
    COALESCE(od.num_obras, 0)               AS num_obras_documento,
    COALESCE(c.tot, 0)::NUMERIC(18, 2)      AS importe,
    retenciones.fn_sigrid_date(c.fecven)    AS fecha_prevista_devolucion,
    retenciones.fn_sigrid_date(c.fecrea)    AS fecha_devolucion_real,
    -- Estado (F-104): la precedencia de PROVEEDOR; el original agrupado
    -- queda en est 1 con fecbaj, y BAJA manda (ver cabecera: CLIENTE)
    CASE WHEN COALESCE(efe.fecbaj, 0) <> 0 OR efe.est IN (14, 15) THEN 'BAJA'
         WHEN COALESCE(c.fecrea, 0) <> 0 OR efe.est = 10 THEN 'LIQUIDADA'
         ELSE 'VIVA' END::VARCHAR(10) AS estado,
    efe.est                                 AS estado_sigrid,
    retenciones.fn_sigrid_date(efe.fecbaj)  AS fecha_baja,
    CASE WHEN COALESCE(c.fecrea, 0) = 0
          AND COALESCE(efe.fecbaj, 0) = 0
          AND COALESCE(efe.est, 0) NOT IN (10, 14, 15)
          AND retenciones.fn_sigrid_date(c.fecven) IS NOT NULL
          AND retenciones.fn_sigrid_date(c.fecven) < CURRENT_DATE
         THEN TRUE ELSE FALSE END           AS vencida_sin_liquidar,
    (CURRENT_DATE - retenciones.fn_sigrid_date(c.fecven)) AS dias_desde_vencimiento,
    CASE WHEN COALESCE(c.retide, 0) <> 0 THEN 'EFECTO_RETENCION'
         ELSE 'CUENTA_RETENCION' END::VARCHAR(16) AS origen_retencion,
    NULLIF(c.cueide, 0)                     AS cuenta_id
FROM raw.cob c
LEFT JOIN raw.con efe ON efe.ide = c.ide  -- ficha del EFECTO: est y fecbaj (F-104)
LEFT JOIN retenciones.tipos tp ON tp.tipo_id = c.retide
LEFT JOIN raw.con doc     ON doc.ide = NULLIF(c.conide, 0)
LEFT JOIN raw.con ent     ON ent.ide = NULLIF(c.entide, 0)
LEFT JOIN maestro.centros_coste cc ON cc.centro_coste_id = NULLIF(c.cenide, 0)
LEFT JOIN obras_doc_venta od ON od.documento_id = NULLIF(c.conide, 0)
LEFT JOIN raw.con obr_con ON obr_con.ide = CASE WHEN od.num_obras = 1
                                                THEN od.obra_unica END
-- F-104 (R6): los efectos con tipo de retencion Y los de las cuentas de
-- retencion de cliente (AGR, DIV y sin tipo, retide = 0)
WHERE COALESCE(c.retide, 0) <> 0
   OR c.cueide IN (SELECT cuenta_id FROM retenciones.cuentas_cliente);

ALTER TABLE retenciones.movimientos ADD PRIMARY KEY (sentido, movimiento_id);
CREATE INDEX idx_ret_mov_sentido  ON retenciones.movimientos (sentido);
CREATE INDEX idx_ret_mov_obra     ON retenciones.movimientos (obra_id);
CREATE INDEX idx_ret_mov_entidad  ON retenciones.movimientos (entidad_id);
CREATE INDEX idx_ret_mov_estado   ON retenciones.movimientos (estado);
CREATE INDEX idx_ret_mov_fecven   ON retenciones.movimientos (fecha_prevista_devolucion);
CREATE INDEX idx_ret_mov_cuenta   ON retenciones.movimientos (sentido, cuenta_id);

COMMENT ON TABLE retenciones.movimientos IS
'Un registro por efecto de retención (Tanda R1). sentido PROVEEDOR = la '
'practicamos nosotros (raw.pag); CLIENTE = nos la practican (raw.cob). '
'estado (F-094): en PROVEEDOR, BAJA si el efecto tiene fecbaj o est 14/15 '
'(agrupado, dividido o anulado: su dinero cuenta en otro efecto), LIQUIDADA '
'si tiene fecrea o est 10 (Pagado o Cobrado), VIVA el resto; desde F-104 '
'igual en CLIENTE, donde el original agrupado queda en est 1 con fecbaj. '
'CLIENTE incluye tambien los efectos de las cuentas de retencion de cliente '
'(AGR, DIV, sin tipo): origen_retencion EFECTO_RETENCION o CUENTA_RETENCION; '
'cuenta_id = cueide del efecto. La retencion viva de cliente la manda la '
'contabilidad (retenciones.v_cuadre_cliente). '
'Ninguna lectura suma BAJA. Importes con signo: los negativos '
'son ajustes/devoluciones. obra_id es la obra de maestro.obras (F-094): el '
'cenide del efecto (publicado en centro_coste_id) traducido por '
'maestro.centros_coste, con fallback a las líneas del documento origen si '
'no hay centro y apuntan a una sola obra.';
