-- etl_sigrid/infrastructure/postgres/sql/tesoreria/01_efectos_completo.sql
-- ============================================================================
-- F-037 · SCHEMA tesoreria (2/4): tesoreria_restringida.efectos, LA CARTERA COMPLETA
--
-- GRANO: una fila por efecto de `raw.pag` (PAGO) y de `raw.cob` (COBRO), SIN
-- WHERE (R5): ni las bajas, ni los de personal, ni nada se filtra. Se publica
-- el hecho con sus marcas, y quien consulta decide. 256.952 pagos + 21.914
-- cobros el 2026-10-13; el `ide` de los dos es un `con.ide`, unico entre ambos.
--
-- EL EFECTO ES UN DOCUMENTO (DA-9 de F-080): `raw.pag` y `raw.cob` son
-- «propiedades de `con`», con su fila en `raw.con` (`tip = 25` y `tip = 24`).
-- Su codigo, descripcion, empresa, estado y baja se LEEN de esa fila (`c`), no
-- se derivan (R6). Quitar el `JOIN raw.con c ON c.ide = p.ide` deja la cartera
-- sin identidad. Las expresiones de las columnas que hereda
-- `compras.vencimientos` son las de F-080, tal cual.
--
-- EL ESTADO (R3, precedencia de F-094, igual en los dos sentidos): BAJA si el
-- efecto tiene fecha de baja o `est` 14/15; si no, REALIZADO si tiene fecha
-- real o `est = 10`; si no, PREVISTO. Desde 2020 el pago por remesa deja
-- `est = 10` SIN fecha real (41.884 pagos y 2.106 cobros): `fecha_real` vacia
-- no es «pendiente». Por eso el estado lee `est`, y las fechas CRUDAS
-- (`fecrea_efecto`, `fecbaj_efecto`), no las tipadas: `fn_fecha` da NULL a una
-- fecha invalida y el estado no puede depender de eso.
--
-- LO DE PERSONAL (R1, R2): `restringido` y `motivo_restriccion`, con el mismo
-- CASE y en el mismo orden que `etl_sigrid/domain/tesoreria.py`, la regex de
-- cuentas de F-135 escrita tal cual y los tipos 43 (empleado) y 306 (nomina);
-- `tests/test_f037_sql.py` los compara con el dominio. Una cuenta que no
-- resuelve FALLA CERRADO (se restringe). Medido: 37.053 pagos, 0 cobros.
--
-- LA OBRA (R8 de F-037; F-140 R17, D10-A): la del centro de coste
-- (`maestro.centros_coste` por `cenide`). Un centro que NO es obra (estructura,
-- delegacion) deja el efecto sin obra: dice que el gasto no es de obra. Solo
-- en los PAGOS SIN centro, la cascada del documento, en el orden de
-- `obra_del_efecto` (`etl_sigrid/domain/tesoreria.py`): la obra UNICA de los
-- contratos de la factura (`dcf.ctride` y los `ctr` de `dcfpro.docoriide`), la
-- de su cabecera (`dcf.obride`) y la UNICA de sus lineas (`dcfpro.obride`); un
-- conjunto con mas de una obra no decide. Solo obras de `raw.obr`. `obra_via`
-- dice por donde (CENTRO, CONTRATO, FACTURA_CABECERA, FACTURA_LINEAS). Medido
-- el 2026-10-24: +113 pagos y 0,23 M EUR (86,87 % -> 86,95 %). Los cobros, solo
-- por el centro: sin documento de venta (F-040) no hay cascada. Las
-- agrupaciones (`AGR`, sin documento) siguen sin obra: Sigrid no guarda el
-- vinculo.
--
-- LO QUE NO SE PUBLICA (R9): la cuenta bancaria del tercero (111.450 pagos la
-- traen) ni los dos enlaces del origen que estan vacios o sin uso. Sus nombres
-- no se escriben aqui a proposito: un test los prohibe en el SQL.
--
-- PREVISTO ANTIGUO (R25 bis, D11-A): PREVISTO con vencimiento anterior a la
-- fecha del build menos 2 anos. Es deuda sin puntear que la contabilidad ya no
-- sostiene (223 cuentas de proveedor cuadran al centimo solo sin ella), no caja.
--
-- `TRUNCATE` + `INSERT` (R14) en una sola transaccion: si algo falla, queda la
-- cartera de la noche anterior.
--
-- Lee de: raw.pag, raw.cob, raw.con, raw.conest, raw.dcf, raw.prv, raw.auxefp,
--         raw.auxnap, raw.auxban, raw.rpa, maestro.centros_coste y, en la
--         cascada de F-140, raw.dcfpro, raw.ctr y raw.obr.
-- Escribe en: tesoreria_restringida.efectos.
-- ============================================================================

TRUNCATE tesoreria_restringida.efectos;

INSERT INTO tesoreria_restringida.efectos (
    efecto_id, sentido, empresa_id, codigo_efecto, descripcion_efecto,
    serie_efecto, documento_id, codigo_documento, tipo_documento,
    es_factura_compra, tercero_id, tercero_nombre, tercero_cif,
    fecha_emision, fecha_vencimiento, fecha_real, importe, importe_flujo,
    estado_tesoreria, estado_codigo, estado_sigrid, efecto_anulado,
    fecha_anulacion, medio_pago_id, medio_pago, naturaleza_pago_id,
    naturaleza_pago, cuenta_contable_id, cuenta_contable,
    cuenta_contable_nombre, banco_id, banco, sucursal_id, sucursal,
    retencion_id, centro_coste_id, obra_id, codigo_obra, nombre_obra,
    remesa_id, codigo_remesa, fecha_remesa, importe_remesa,
    previsto_antiguo, restringido, motivo_restriccion, obra_via
)
WITH facturas_sin_centro AS (
    -- F-140 (D10-A): las facturas de compra de los pagos SIN centro de coste.
    -- Las condiciones van en el ON: este fichero no filtra filas con WHERE.
    -- La columna se llama `factura_id` y no `documento_id` a proposito: el
    -- guardian de nulos del diccionario lee la PRIMERA proyeccion de cada
    -- nombre, y la de esta CTE (sin NULLIF, por el JOIN) no es la publicada.
    SELECT DISTINCT
        fc.ide                                  AS factura_id,
        NULLIF(fc.ctride, 0)                    AS contrato_id,
        ob.ide                                  AS obra_cabecera
    FROM raw.pag p
    JOIN raw.dcf fc ON fc.ide = p.conide AND COALESCE(p.cenide, 0) = 0
    LEFT JOIN raw.obr ob ON ob.ide = NULLIF(fc.obride, 0)
)
, obras_contrato AS (
    -- La obra de los contratos de la factura: el de su cabecera y los de sus
    -- lineas (`docoriide` que es un `ctr`). Si son varias, NULL: no decide.
    SELECT
        f.factura_id,
        CASE WHEN count(DISTINCT ob.ide) = 1 THEN min(ob.ide) END AS obra_id
    FROM facturas_sin_centro f
    LEFT JOIN raw.dcfpro l ON l.docide = f.factura_id
    JOIN raw.ctr k ON k.ide = f.contrato_id OR k.ide = l.docoriide
    JOIN raw.obr ob ON ob.ide = NULLIF(k.obride, 0)
    GROUP BY f.factura_id
)
, obras_lineas AS (
    -- La obra de las lineas de la factura. Si son varias, NULL: no decide.
    SELECT
        f.factura_id,
        CASE WHEN count(DISTINCT ob.ide) = 1 THEN min(ob.ide) END AS obra_id
    FROM facturas_sin_centro f
    JOIN raw.dcfpro l ON l.docide = f.factura_id
    JOIN raw.obr ob ON ob.ide = NULLIF(l.obride, 0)
    GROUP BY f.factura_id
)
, obra_documento AS (
    -- La cascada, en el orden del dominio: contrato, cabecera, lineas.
    SELECT
        f.factura_id,
        CASE WHEN oc.obra_id IS NOT NULL THEN oc.obra_id
             WHEN f.obra_cabecera IS NOT NULL THEN f.obra_cabecera
             WHEN ol.obra_id IS NOT NULL THEN ol.obra_id END AS obra_id,
        CASE WHEN oc.obra_id IS NOT NULL THEN 'CONTRATO'
             WHEN f.obra_cabecera IS NOT NULL THEN 'FACTURA_CABECERA'
             WHEN ol.obra_id IS NOT NULL THEN 'FACTURA_LINEAS' END AS obra_via
    FROM facturas_sin_centro f
    LEFT JOIN obras_contrato oc ON oc.factura_id = f.factura_id
    LEFT JOIN obras_lineas   ol ON ol.factura_id = f.factura_id
)
, efectos AS (
    -- -----------------------------------------------------------------------
    -- PAGO: raw.pag (`p` es el efecto, en las dos ramas)
    -- -----------------------------------------------------------------------
    SELECT
        p.ide                                   AS efecto_id,
        'PAGO'::VARCHAR(5)                      AS sentido,
        c.emp                                   AS empresa_id,
        c.cod                                   AS codigo_efecto,
        c.res                                   AS descripcion_efecto,
        tesoreria.fn_serie(c.cod)               AS serie_efecto,
        NULLIF(p.conide, 0)                     AS documento_id,
        d.cod                                   AS codigo_documento,
        d.tip                                   AS tipo_documento,
        EXISTS (SELECT 1 FROM raw.dcf f WHERE f.ide = p.conide) AS es_factura_compra,
        NULLIF(p.entide, 0)                     AS tercero_id,
        t.res                                   AS tercero_nombre,
        t.tip                                   AS tip_tercero,
        prv.cif                                 AS tercero_cif,
        tesoreria.fn_fecha(p.fecreaemi)         AS fecha_emision,
        tesoreria.fn_fecha(p.fecven)            AS fecha_vencimiento,
        tesoreria.fn_fecha(p.fecrea)            AS fecha_real,
        p.fecrea                                AS fecrea_efecto,
        COALESCE(p.tot, 0)::NUMERIC(18, 2)      AS importe,
        c.est                                   AS estado_codigo,
        ce.res                                  AS estado_sigrid,
        (c.fecbaj <> 0)                         AS efecto_anulado,
        c.fecbaj                                AS fecbaj_efecto,
        tesoreria.fn_fecha(c.fecbaj)            AS fecha_anulacion,
        NULLIF(p.efeide, 0)                     AS medio_pago_id,
        ef.res                                  AS medio_pago,
        NULLIF(p.natide, 0)                     AS naturaleza_pago_id,
        na.res                                  AS naturaleza_pago,
        NULLIF(p.cueide, 0)                     AS cuenta_contable_id,
        cue.cod                                 AS cuenta_contable,
        cue.res                                 AS cuenta_contable_nombre,
        NULLIF(p.banban, 0)                     AS banco_id,
        bb.res                                  AS banco,
        NULLIF(p.bansuc, 0)                     AS sucursal_id,
        bs.res                                  AS sucursal,
        NULLIF(p.retide, 0)                     AS retencion_id,
        NULLIF(p.cenide, 0)                     AS centro_coste_id,
        COALESCE(cc.obra_id, od.obra_id)        AS obra_id,
        COALESCE(cc.codigo_obra, obc.cod)       AS codigo_obra,
        COALESCE(cc.nombre_obra, obc.res)       AS nombre_obra,
        NULLIF(p.remide, 0)                     AS remesa_id,
        rc.cod                                  AS codigo_remesa,
        tesoreria.fn_fecha(r.fecrem)            AS fecha_remesa,
        r.imptot::NUMERIC                       AS importe_remesa,
        CASE WHEN cc.obra_id IS NOT NULL THEN 'CENTRO' ELSE od.obra_via END AS obra_via
    FROM raw.pag p
    -- OBLIGATORIO (DA-9): `c` es el documento DEL EFECTO.
    JOIN raw.con c ON c.ide = p.ide
    -- El documento origen (factura de compra, nomina...) y el tercero.
    LEFT JOIN raw.con    d   ON d.ide   = NULLIF(p.conide, 0)
    LEFT JOIN raw.con    t   ON t.ide   = NULLIF(p.entide, 0)
    LEFT JOIN raw.prv    prv ON prv.ide = NULLIF(p.entide, 0)
    -- El estado se traduce con el `tip` del efecto de pago (25): sin el tipo,
    -- la misma cifra significa otra cosa. LEFT JOIN: un estado fuera de
    -- catalogo no hace desaparecer el efecto.
    LEFT JOIN raw.conest ce  ON ce.tip = 25 AND ce.est = c.est
    LEFT JOIN raw.auxefp ef  ON ef.ide  = NULLIF(p.efeide, 0)
    LEFT JOIN raw.auxnap na  ON na.ide  = NULLIF(p.natide, 0)
    -- La cuenta contable: su codigo esta en `raw.con` (`raw.cua` no lo tiene).
    LEFT JOIN raw.con    cue ON cue.ide = NULLIF(p.cueide, 0)
    -- `banban` y `bansuc` apuntan los dos al `ide` de `auxban`.
    LEFT JOIN raw.auxban bb  ON bb.ide  = NULLIF(p.banban, 0)
    LEFT JOIN raw.auxban bs  ON bs.ide  = NULLIF(p.bansuc, 0)
    LEFT JOIN maestro.centros_coste cc ON cc.centro_coste_id = NULLIF(p.cenide, 0)
    -- La remesa de pago: fecha e importe de `raw.rpa`, codigo de `raw.con`.
    LEFT JOIN raw.rpa    r   ON r.ide   = NULLIF(p.remide, 0)
    LEFT JOIN raw.con    rc  ON rc.ide  = r.ide
    -- F-140 (D10-A): la cascada, solo si el efecto NO tiene centro.
    LEFT JOIN obra_documento od ON od.factura_id = NULLIF(p.conide, 0)
                               AND COALESCE(p.cenide, 0) = 0
    LEFT JOIN raw.con    obc ON obc.ide = od.obra_id

    UNION ALL

    -- -----------------------------------------------------------------------
    -- COBRO: raw.cob. Sin documento de venta (F-040), sin CIF del cliente y
    -- con la remesa solo por su codigo: `raw.rco` no se ingiere.
    -- -----------------------------------------------------------------------
    SELECT
        p.ide                                   AS efecto_id,
        'COBRO'::VARCHAR(5)                     AS sentido,
        c.emp                                   AS empresa_id,
        c.cod                                   AS codigo_efecto,
        c.res                                   AS descripcion_efecto,
        tesoreria.fn_serie(c.cod)               AS serie_efecto,
        NULLIF(p.conide, 0)                     AS documento_id,
        d.cod                                   AS codigo_documento,
        d.tip                                   AS tipo_documento,
        FALSE                                   AS es_factura_compra,
        NULLIF(p.entide, 0)                     AS tercero_id,
        t.res                                   AS tercero_nombre,
        t.tip                                   AS tip_tercero,
        NULL::VARCHAR(24)                       AS tercero_cif,
        tesoreria.fn_fecha(p.fecreaemi)         AS fecha_emision,
        tesoreria.fn_fecha(p.fecven)            AS fecha_vencimiento,
        tesoreria.fn_fecha(p.fecrea)            AS fecha_real,
        p.fecrea                                AS fecrea_efecto,
        COALESCE(p.tot, 0)::NUMERIC(18, 2)      AS importe,
        c.est                                   AS estado_codigo,
        ce.res                                  AS estado_sigrid,
        (c.fecbaj <> 0)                         AS efecto_anulado,
        c.fecbaj                                AS fecbaj_efecto,
        tesoreria.fn_fecha(c.fecbaj)            AS fecha_anulacion,
        NULLIF(p.efeide, 0)                     AS medio_pago_id,
        ef.res                                  AS medio_pago,
        NULLIF(p.natide, 0)                     AS naturaleza_pago_id,
        na.res                                  AS naturaleza_pago,
        NULLIF(p.cueide, 0)                     AS cuenta_contable_id,
        cue.cod                                 AS cuenta_contable,
        cue.res                                 AS cuenta_contable_nombre,
        NULLIF(p.banban, 0)                     AS banco_id,
        bb.res                                  AS banco,
        NULLIF(p.bansuc, 0)                     AS sucursal_id,
        bs.res                                  AS sucursal,
        NULLIF(p.retide, 0)                     AS retencion_id,
        NULLIF(p.cenide, 0)                     AS centro_coste_id,
        cc.obra_id                              AS obra_id,
        cc.codigo_obra                          AS codigo_obra,
        cc.nombre_obra                          AS nombre_obra,
        NULLIF(p.remide, 0)                     AS remesa_id,
        rc.cod                                  AS codigo_remesa,
        NULL::DATE                              AS fecha_remesa,
        NULL::NUMERIC                           AS importe_remesa,
        CASE WHEN cc.obra_id IS NOT NULL THEN 'CENTRO' END AS obra_via
    FROM raw.cob p
    JOIN raw.con c ON c.ide = p.ide
    LEFT JOIN raw.con    d   ON d.ide   = NULLIF(p.conide, 0)
    LEFT JOIN raw.con    t   ON t.ide   = NULLIF(p.entide, 0)
    -- El estado del efecto de cobro se traduce con su propio `tip` (24).
    LEFT JOIN raw.conest ce  ON ce.tip = 24 AND ce.est = c.est
    LEFT JOIN raw.auxefp ef  ON ef.ide  = NULLIF(p.efeide, 0)
    LEFT JOIN raw.auxnap na  ON na.ide  = NULLIF(p.natide, 0)
    LEFT JOIN raw.con    cue ON cue.ide = NULLIF(p.cueide, 0)
    LEFT JOIN raw.auxban bb  ON bb.ide  = NULLIF(p.banban, 0)
    LEFT JOIN raw.auxban bs  ON bs.ide  = NULLIF(p.bansuc, 0)
    LEFT JOIN maestro.centros_coste cc ON cc.centro_coste_id = NULLIF(p.cenide, 0)
    LEFT JOIN raw.con    rc  ON rc.ide  = NULLIF(p.remide, 0)
)
, marcados AS (
    -- Las dos clasificaciones, UNA vez: `previsto_antiguo` lee el estado y
    -- `restringido` lee el motivo, y asi no pueden discrepar de ellos.
    SELECT
        e.*,
        -- R3: el estado, con la precedencia del dominio.
        CASE WHEN COALESCE(e.fecbaj_efecto, 0) <> 0 OR e.estado_codigo IN (14, 15) THEN 'BAJA'
             WHEN COALESCE(e.fecrea_efecto, 0) <> 0 OR e.estado_codigo = 10 THEN 'REALIZADO'
             ELSE 'PREVISTO' END AS estado_tesoreria,
        -- R1/R2: el primer motivo de personal que casa, en el orden del dominio.
        -- Sin ELSE: sin motivo es NULL, visible.
        CASE WHEN e.naturaleza_pago_id IS NOT NULL THEN 'NATURALEZA'
             WHEN e.cuenta_contable ~ '^(640|641|642|643|644|645|649|465|466|476|460|461|544|4753)' THEN 'CUENTA'
             WHEN e.cuenta_contable_id IS NOT NULL AND e.cuenta_contable IS NULL THEN 'CUENTA_SIN_RESOLVER'
             WHEN e.tip_tercero = 43 THEN 'TERCERO_EMPLEADO'
             WHEN e.tipo_documento = 306 THEN 'DOCUMENTO_NOMINA'
        END AS motivo_restriccion
    FROM efectos e
)
SELECT
    m.efecto_id,
    m.sentido,
    m.empresa_id,
    m.codigo_efecto,
    m.descripcion_efecto,
    m.serie_efecto,
    m.documento_id,
    m.codigo_documento,
    m.tipo_documento,
    m.es_factura_compra,
    m.tercero_id,
    m.tercero_nombre,
    m.tercero_cif,
    m.fecha_emision,
    m.fecha_vencimiento,
    m.fecha_real,
    m.importe,
    -- R4: + en COBRO, - en PAGO. Sin ELSE: un sentido desconocido da NULL y
    -- la columna NOT NULL tumba el build (el dominio lanza ValueError).
    CASE m.sentido WHEN 'COBRO' THEN m.importe
                   WHEN 'PAGO' THEN -m.importe END AS importe_flujo,
    m.estado_tesoreria,
    m.estado_codigo,
    m.estado_sigrid,
    m.efecto_anulado,
    m.fecha_anulacion,
    m.medio_pago_id,
    m.medio_pago,
    m.naturaleza_pago_id,
    m.naturaleza_pago,
    m.cuenta_contable_id,
    m.cuenta_contable,
    m.cuenta_contable_nombre,
    m.banco_id,
    m.banco,
    m.sucursal_id,
    m.sucursal,
    m.retencion_id,
    m.centro_coste_id,
    m.obra_id,
    m.codigo_obra,
    m.nombre_obra,
    m.remesa_id,
    m.codigo_remesa,
    m.fecha_remesa,
    m.importe_remesa,
    -- R25 bis (D11-A): PREVISTO vencido hace mas de 2 anos. Sin vencimiento,
    -- FALSE: no se puede decir que sea antiguo.
    (m.estado_tesoreria = 'PREVISTO'
     AND COALESCE(m.fecha_vencimiento < (CURRENT_DATE - INTERVAL '2 years')::DATE, FALSE)) AS previsto_antiguo,
    (m.motivo_restriccion IS NOT NULL) AS restringido,
    m.motivo_restriccion,
    m.obra_via
FROM marcados m;

COMMENT ON TABLE tesoreria_restringida.efectos IS
'F-037. La cartera COMPLETA de cobros y pagos: una fila por efecto de raw.pag (PAGO) y raw.cob (COBRO), sin filtrar nada, con restringido y motivo_restriccion (pagos de personal: naturaleza NOMINAS/EMBARGO/CUOTAS, cuenta de personal, tercero empleado o documento de nomina). Solo la leen el rol autorizado y el login total. La general, sin los de personal, es tesoreria.efectos. estado_tesoreria: BAJA (no se suma nunca), REALIZADO o PREVISTO; previsto_antiguo marca el PREVISTO vencido hace mas de 2 anos. importe_flujo = +importe en COBRO y -importe en PAGO. Es caja/cartera, no devengo.';
