-- etl_sigrid/infrastructure/postgres/sql/ventas/06_restringida.sql
-- ============================================================================
-- F-040 · VENTAS (7/8): ventas_restringida, LO PERSONAL DEL CLIENTE (R21-R23).
--
-- D2 y D6 del humano (2026-11-07): el NOMBRE del cliente es publico en
-- `ventas`; su NIF si es persona fisica, las direcciones, el telefono, el
-- correo, el CIF y el nombre de la cabecera de la factura y la descripcion de
-- las lineas de las facturas de una persona fisica SOLO estan aqui. Solo lo
-- lee el perfil TOTAL (`R-PERFILES`): `apply_grants` veta el esquema al
-- estandar, al restringido y al postventa (patron de `compras_restringida`,
-- F-138). Se cruza con `ventas` por `cliente_id`, `factura_id` y `linea_id`.
--
-- Los nombres de columna empiezan por `direccion`, `telefono`, `correo`,
-- `cif_cabecera` y `nombre_cabecera` A PROPOSITO: la guarda de
-- `07_guardas.sql` busca esos prefijos en el esquema `ventas` y tumba el paso
-- si aparecen alli.
--
-- Tablas, ninguna vista: solo las lee el total.
--
-- Lee de: raw.cli, raw.dvf, raw.dvfpro y ventas.facturas.
-- Escribe en: ventas_restringida.clientes_contacto, factura_cabecera y
--             factura_lineas_persona.
-- ============================================================================

DROP TABLE IF EXISTS ventas_restringida.factura_lineas_persona CASCADE;
DROP TABLE IF EXISTS ventas_restringida.factura_cabecera CASCADE;
DROP TABLE IF EXISTS ventas_restringida.clientes_contacto CASCADE;

CREATE TABLE ventas_restringida.clientes_contacto AS
SELECT
    cl.ide                                                  AS cliente_id,
    cl.raz                                                  AS nombre,
    cl.cif AS cif,
    ventas.fn_cif_normalizado(cl.cif)                       AS cif_normalizado,
    ventas.fn_es_persona_fisica(ventas.fn_cif_normalizado(cl.cif),
                                cl.perfis::INT)             AS es_persona_fisica,
    cl.dir AS direccion,
    cl.dir1 AS direccion_linea1,
    cl.dir2 AS direccion_linea2,
    cl.dircpo AS codigo_postal,
    cl.tel AS telefono,
    cl.tel2 AS telefono2,
    cl.ele AS correo
FROM raw.cli cl;

ALTER TABLE ventas_restringida.clientes_contacto ADD PRIMARY KEY (cliente_id);

COMMENT ON TABLE ventas_restringida.clientes_contacto IS
'F-040. SOLO PERFIL TOTAL. Una fila por cliente (raw.cli): nombre, el CIF INTEGRO (tambien el de la persona fisica) y normalizado, es_persona_fisica, la direccion completa y en dos lineas, el codigo postal, dos telefonos y el correo. Se cruza con ventas.clientes por cliente_id. Clave: cliente_id.';

CREATE TABLE ventas_restringida.factura_cabecera AS
SELECT
    f.ide                                                   AS factura_id,
    NULLIF(f.entide, 0)                                     AS cliente_id,
    COALESCE(vf.es_persona_fisica, FALSE)                   AS es_persona_fisica,
    f.entres AS nombre_cabecera,
    f.entcif AS cif_cabecera,
    f.diremp1 AS direccion_empresa_1,
    f.dircon1 AS direccion_contacto_1,
    f.dirdir1 AS direccion_completa_1,
    f.diremp2 AS direccion_empresa_2,
    f.dircon2 AS direccion_contacto_2,
    f.dirdir2 AS direccion_completa_2,
    f.diremp3 AS direccion_empresa_3,
    f.dircon3 AS direccion_contacto_3,
    f.dirdir3 AS direccion_completa_3
FROM raw.dvf f
LEFT JOIN ventas.facturas vf ON vf.factura_id = f.ide;

ALTER TABLE ventas_restringida.factura_cabecera ADD PRIMARY KEY (factura_id);

COMMENT ON TABLE ventas_restringida.factura_cabecera IS
'F-040. SOLO PERFIL TOTAL. Una fila por factura de venta (raw.dvf): el cliente, es_persona_fisica, el nombre y el CIF de la CABECERA tal y como se emitio (entres, entcif: el nombre difiere del actual en 571 facturas por renombres) y las nueve direcciones (empresa, contacto y completa, 1 a 3). Se cruza con ventas.facturas por factura_id. Clave: factura_id.';

CREATE TABLE ventas_restringida.factura_lineas_persona AS
SELECT
    l.ide                                                   AS linea_id,
    l.docide                                                AS factura_id,
    f.cliente_id                                            AS cliente_id,
    l.res                                                   AS descripcion
FROM raw.dvfpro l
LEFT JOIN ventas.facturas f ON f.factura_id = l.docide
-- Las mismas lineas que `ventas.factura_lineas` publica sin descripcion:
-- las de un cliente persona fisica y las de una factura que no existe.
WHERE COALESCE(f.es_persona_fisica, TRUE);

ALTER TABLE ventas_restringida.factura_lineas_persona ADD PRIMARY KEY (linea_id);

COMMENT ON TABLE ventas_restringida.factura_lineas_persona IS
'F-040. SOLO PERFIL TOTAL. Una fila por linea de factura de venta cuya descripcion ventas.factura_lineas publica a NULL (cliente persona fisica, o factura inexistente): la descripcion integra. Se cruza con ventas.factura_lineas por linea_id. Clave: linea_id.';
