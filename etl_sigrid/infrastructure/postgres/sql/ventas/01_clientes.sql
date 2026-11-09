-- etl_sigrid/infrastructure/postgres/sql/ventas/01_clientes.sql
-- ============================================================================
-- F-040 · VENTAS (2/8): ventas.clientes (R5-R8).
--
-- GRANO: una fila por cliente de `raw.cli` (`con` tipo 4), 1.210 el
-- 2026-11-07. Sin WHERE: un cliente sin uso tambien se publica.
--
-- PERSONA FISICA (R6, D2 del humano): `perfis` <> 0 o un CIF con forma de NIF
-- de persona; 572 clientes, la mayoria arrendatarios de garajes y compradores
-- de vivienda. Su NOMBRE es publico (D2: «los diez mayores clientes»), pero su
-- CIF (`cif`, `cif_normalizado`) se publica a NULL: el CIF integro, la
-- direccion, el telefono y el correo viven en
-- `ventas_restringida.clientes_contacto`, que solo lee el perfil total.
-- `cif_valido` y `cif_repetido` se calculan ANTES de anular (R7): dicen algo
-- del dato aunque el CIF no se vea. El CIF de la persona JURIDICA es publico.
--
-- EL CODIGO (`con.cod`, R1-H1 del review): lo escribe quien da de alta al
-- cliente y puede ser su DNI. Se anula si el cliente es persona fisica o si,
-- normalizado como un CIF, tiene forma de NIF de persona
-- (`codigo_cliente_publicado` del dominio); integro, en
-- `ventas_restringida.clientes_contacto`. La guarda lo vigila (R24).
--
-- LOS AGREGADOS (facturas, certificaciones y obras por cliente) se calculan
-- ANTES de unir: cada CTE tiene su GROUP BY y el JOIN es 1:1 por cliente.
-- Los importes de `raw` son `double precision`: se castean a NUMERIC.
--
-- Lee de: raw.cli, raw.con (tipo 4), raw.dvf, raw.cer, raw.obr.
-- Escribe en: ventas.clientes.
-- ============================================================================

DROP TABLE IF EXISTS ventas.clientes CASCADE;

CREATE TABLE ventas.clientes AS
WITH facturas_cliente AS (
    SELECT NULLIF(f.entide, 0)                              AS cliente_id,
           count(*)                                         AS num_facturas,
           SUM(COALESCE(f.totbas, 0)::NUMERIC(18, 2))       AS facturado_base,
           min(ventas.fn_fecha(f.fecdoc))                   AS primera_factura,
           max(ventas.fn_fecha(f.fecdoc))                   AS ultima_factura
    FROM raw.dvf f
    GROUP BY NULLIF(f.entide, 0)
)
, certificaciones_cliente AS (
    SELECT NULLIF(k.entide, 0) AS cliente_id, count(*) AS num_certificaciones
    FROM raw.cer k
    GROUP BY NULLIF(k.entide, 0)
)
, obras_cliente AS (
    SELECT NULLIF(o.entide, 0) AS cliente_id, count(*) AS num_obras
    FROM raw.obr o
    GROUP BY NULLIF(o.entide, 0)
)
, base AS (
    -- Todo lo que se calcula con el CIF a la vista: normalizado, persona,
    -- valido y repetido (R7: antes de anularlo).
    SELECT
        cl.ide                                              AS cliente_id,
        c.cod                                               AS codigo_cliente,
        cl.raz                                              AS nombre,
        cl.cif                                              AS cif,
        ventas.fn_cif_normalizado(cl.cif)                   AS cif_normalizado,
        cl.tipcif                                           AS tipo_documento,
        cl.cifpai                                           AS pais,
        ventas.fn_es_persona_fisica(ventas.fn_cif_normalizado(cl.cif),
                                    cl.perfis::INT)         AS es_persona_fisica,
        ventas.fn_cif_valido(ventas.fn_cif_normalizado(cl.cif)) AS cif_valido,
        CASE WHEN ventas.fn_cif_normalizado(cl.cif) IS NULL THEN FALSE
             ELSE count(*) OVER (PARTITION BY ventas.fn_cif_normalizado(cl.cif)) > 1
        END                                                 AS cif_repetido
    FROM raw.cli cl
    LEFT JOIN raw.con c ON c.ide = cl.ide AND c.tip = 4
)
SELECT
    b.cliente_id                                            AS cliente_id,
    CASE WHEN b.es_persona_fisica OR COALESCE(ventas.fn_cif_normalizado(b.codigo_cliente) ~ '^[0-9KLMXYZ][0-9]{7}[A-Z]$', FALSE) THEN NULL ELSE b.codigo_cliente END AS codigo_cliente,
    b.nombre                                                AS nombre,
    CASE WHEN b.es_persona_fisica THEN NULL ELSE b.cif END  AS cif,
    CASE WHEN b.es_persona_fisica THEN NULL ELSE b.cif_normalizado END AS cif_normalizado,
    b.tipo_documento                                        AS tipo_documento,
    b.pais                                                  AS pais,
    b.es_persona_fisica                                     AS es_persona_fisica,
    b.cif_valido                                            AS cif_valido,
    b.cif_repetido                                          AS cif_repetido,
    COALESCE(oc.num_obras, 0)                               AS num_obras,
    COALESCE(fc.num_facturas, 0)                            AS num_facturas,
    COALESCE(kc.num_certificaciones, 0)                     AS num_certificaciones,
    COALESCE(fc.facturado_base, 0)::NUMERIC(18, 2)          AS facturado_base,
    fc.primera_factura                                      AS primera_factura,
    fc.ultima_factura                                       AS ultima_factura
FROM base b
LEFT JOIN facturas_cliente        fc ON fc.cliente_id = b.cliente_id
LEFT JOIN certificaciones_cliente kc ON kc.cliente_id = b.cliente_id
LEFT JOIN obras_cliente           oc ON oc.cliente_id = b.cliente_id;

ALTER TABLE ventas.clientes ADD PRIMARY KEY (cliente_id);

COMMENT ON TABLE ventas.clientes IS
'F-040. Una fila por cliente de Sigrid (raw.cli): el codigo (NULL en persona fisica o si tiene forma de NIF de persona), nombre (publico tambien en personas fisicas, D2), CIF tal cual y normalizado, tipo y pais, es_persona_fisica (perfis o NIF de persona), cif_valido (letra de control) y cif_repetido, calculados antes de anular; y por cliente, obras, facturas, certificaciones, lo facturado (base) y la primera y ultima factura. El CIF de la persona fisica va a NULL: integro, con el contacto, en ventas_restringida.clientes_contacto (solo perfil total). Clave: cliente_id.';
