-- etl_sigrid/infrastructure/postgres/sql/compras/05_vencimientos.sql
-- ============================================================================
-- Los EFECTOS DE PAGO de la factura de compra (F-080, R7-R12, R38-R41).
-- Es la pestaña «Vencimientos» de la factura, fila a fila.
--
-- EL TITULAR, y lo que la exploración falló dos veces: **el efecto de pago ES
-- un documento**. `raw.pag` son «Propiedades de `con`» y cada efecto tiene su
-- fila en `raw.con` con `tip = 25` (medido: 0 de 255.148 con otro tipo), así
-- que su código (`FR26/06051_01`), su descripción («Pago 1 de 2 …»), su estado
-- y su marca de baja **se leen** de la superclase; no se derivan de nada.
-- Quitar el `JOIN raw.con c ON c.ide = p.ide` deja esta tabla sin identidad.
--
-- La misma trampa, tres veces más: la remesa (`raw.rpa`, `tip = 27`) y la
-- cuenta contable (`raw.cua`, `tip = 17`) tampoco guardan su código; está en
-- `raw.con`. `raw.cua` no tiene ni `cod` ni `res` (medido en T1), así que
-- unirse a ella daría una columna vacía con un nombre convincente.
--
-- GRANO: una fila por fila de `raw.pag` cuyo `conide` sea factura de compra
-- (`raw.dcf`). 195.510 efectos medidos el 2026-09-11 sobre 165.737 facturas.
-- Los efectos de otros documentos y los cobros (`raw.cob`) son F-037.
--
-- TABLA y no vista, con la clave primaria DECLARADA: así el build falla la
-- noche en que el grano se rompa, en vez de dejar que lo descubra
-- `check-unicidad` un mes después con el importe agregado ya falseado.
--
-- Lee de: raw.pag, raw.dcf, raw.con, raw.conest, raw.auxefp, raw.auxnap,
--         raw.auxban, raw.rpa. Escribe en: compras.vencimientos.
-- ============================================================================

DROP TABLE IF EXISTS compras.vencimientos CASCADE;
CREATE TABLE compras.vencimientos AS
SELECT
    p.ide                                   AS vencimiento_id,
    p.conide                                AS factura_id,
    cf.cod                                  AS codigo_factura,
    c.cod                                   AS codigo_efecto,
    c.res                                   AS descripcion_efecto,
    compras.fn_serie(c.cod)                 AS serie_efecto,
    compras.fn_sigrid_date(p.fecreaemi)     AS fecha_emision,
    compras.fn_sigrid_date(p.fecven)        AS fecha_vencimiento,
    compras.fn_sigrid_date(p.fecrea)        AS fecha_real,
    COALESCE(p.tot, 0)::NUMERIC(18, 2)      AS importe,
    c.est                                   AS estado_pago_codigo,
    ce.res                                  AS estado_pago,
    (c.fecbaj <> 0)                         AS efecto_anulado,
    compras.fn_sigrid_date(c.fecbaj)        AS fecha_anulacion,
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
    NULLIF(p.remide, 0)                     AS remesa_id,
    rc.cod                                  AS codigo_remesa,
    compras.fn_sigrid_date(r.fecrem)        AS fecha_remesa,
    r.imptot::NUMERIC                       AS importe_remesa
FROM raw.pag p
-- El filtro a factura de compra: JOIN y no LEFT JOIN. Con LEFT entrarían los
-- efectos de cualquier otro documento, que son de F-037 fase 1 (R7, R15).
JOIN raw.dcf f ON f.ide = p.conide
-- OBLIGATORIO (DA-9): `c` es el documento DEL EFECTO, no la cabecera.
JOIN raw.con c ON c.ide = p.ide
-- `cf` sí es la cabecera de la factura, y solo se usa para su código.
LEFT JOIN raw.con    cf  ON cf.ide  = f.ide
-- El estado se traduce filtrando `tip = 25`: sin el tipo, la misma cifra
-- significa otra cosa en una factura. LEFT JOIN para que un estado fuera de
-- catálogo no haga desaparecer el efecto (R10).
LEFT JOIN raw.conest ce  ON ce.tip  = 25 AND ce.est = c.est
LEFT JOIN raw.auxefp ef  ON ef.ide  = NULLIF(p.efeide, 0)
LEFT JOIN raw.auxnap na  ON na.ide  = NULLIF(p.natide, 0)
LEFT JOIN raw.con    cue ON cue.ide = NULLIF(p.cueide, 0)
-- `pag.banban` y `pag.bansuc` apuntan los DOS al `ide` de `auxban`, en dos
-- uniones distintas (medido en T1: casan 110.460/110.477 y 93.273/93.273).
-- `auxban.tipsuc` separa las 442 entidades de las 1.248 sucursales.
LEFT JOIN raw.auxban bb  ON bb.ide  = NULLIF(p.banban, 0)
LEFT JOIN raw.auxban bs  ON bs.ide  = NULLIF(p.bansuc, 0)
-- La remesa de pago: 40.090 de los 195.510 efectos de factura están en una.
-- El resto sale a NULL y no se pierde. `raw.rco` (cobro) no se toca: F-037.
LEFT JOIN raw.rpa    r   ON r.ide   = NULLIF(p.remide, 0)
LEFT JOIN raw.con    rc  ON rc.ide  = r.ide;

ALTER TABLE compras.vencimientos ADD PRIMARY KEY (vencimiento_id);
CREATE INDEX idx_com_ven_fac ON compras.vencimientos (factura_id);
CREATE INDEX idx_com_ven_rem ON compras.vencimientos (remesa_id);
CREATE INDEX idx_com_ven_est ON compras.vencimientos (estado_pago_codigo);
CREATE INDEX idx_com_ven_vto ON compras.vencimientos (fecha_vencimiento);
CREATE INDEX idx_com_ven_anu ON compras.vencimientos (efecto_anulado);

-- Dos nombres que NO aparecen en el COMMENT a proposito: la columna que no se
-- publica (`efecto_origen_id`) y el campo vacio del origen (`pag.padide`).
-- `tests/test_f080_sql.py` prohibe esos literales en el SQL ejecutable, y con
-- razon: quien los lea ahi creera que existen. El aviso para quien consulta
-- vive en la ficha del diccionario (R40, T20), y el porque, aqui arriba.
COMMENT ON TABLE compras.vencimientos IS
'Efectos de pago de la factura de compra (pestaña Vencimientos). GRANO: uno '
'por fila de raw.pag cuyo documento sea factura de compra; 195.510 efectos '
'sobre 165.737 facturas (2026-09-11). '
'TRAMPA 1: SUMAR LOS IMPORTES DE TODOS LOS EFECTOS DE UNA FACTURA DUPLICA. El '
'efecto nace partido en _01 (pago) y _02 (retencion); al dividirlo los hijos '
'van en serie DIV y el original queda ANULADO; al remesarlo se agrupan en '
'AGR. 89.228 de 255.148 efectos (35 %) estan de baja, y ciñendose a los de '
'factura, 76.215 de 195.510 (39 %): sin filtrar, uno de cada tres es un '
'fantasma. Se excluyen con efecto_anulado = false, que es lo que reproduce el '
'numero que Sigrid enseña en la cabecera (verificado sobre FR25/04222: cinco '
'efectos vivos = 92.478,49, y sin la retencion viva, 87.854,56). El estado NO '
'distingue al anulado: los tres anulados de esa factura estan Aprobado. '
'TRAMPA 2: fecha_real vacia NO significa que el efecto este vivo. Son 120.843 '
'de 195.510 (62 %) sin puntear, frente a los 10.607 pagos de cartera viva que '
'midio F-037; fecha_real avisa de la fecha real de pago, no del estado, y el '
'estado es estado_pago (10 valores leidos de raw.conest con tip = 25). '
'NO SE PUBLICA el enlace del efecto hijo a su efecto de origen: el campo del '
'ERP que lo prometia vale 0 en los 255.148 efectos, asi que esa relacion no '
'existe en el origen y deducirla por importes y fechas seria una '
'reconstruccion, no un dato. '
'Deuda declarada: F-037 fase 1 publicara la cartera completa de cobros y '
'pagos; cuando llegue se decide si absorbe esta tabla o la deja como vista.';
