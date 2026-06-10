-- etl_sigrid/infrastructure/postgres/sql/maestro/03_proveedores_obra.sql
--
-- Proveedores POR OBRA, para consulta externa.
-- Fuente: ctr (Contratos de compra). Cada contrato une obra (ctr.obride) y
-- proveedor (ctr.entide). Se agrega a una fila por (obra, proveedor) con el
-- nº de contratos y el importe total contratado.
--
-- (obrprv, la tabla "Obras: Proveedores" de Sigrid, está vacía en Ruesma;
--  el vínculo real vive en los contratos de compra.)
--
-- Consumo típico:
--   SELECT nombre_proveedor, cif
--   FROM   maestro.proveedores_obra
--   WHERE  codigo_obra = '0404'
--   ORDER  BY nombre_proveedor;

CREATE OR REPLACE VIEW maestro.proveedores_obra AS
WITH dir AS (
    -- Una dirección por entidad (la de menor pos).
    SELECT DISTINCT ON (conide)
        conide, dir1, dir2, dircpo, dir, proide, munide, tel
    FROM   raw.condir
    ORDER  BY conide, pos NULLS LAST, ide
),
contratos AS (
    -- Una fila por (obra, proveedor), sumando todos sus contratos de compra.
    SELECT
        t.obride                       AS obra_id,
        t.entide                       AS proveedor_id,
        COUNT(*)                       AS n_contratos,
        SUM(t.totdoc)::numeric(18,2)   AS importe_contratado
    FROM   raw.ctr t
    WHERE  t.entide IS NOT NULL AND t.entide > 0
      AND  t.obride IS NOT NULL AND t.obride > 0
    GROUP  BY t.obride, t.entide
)
SELECT
    k.obra_id,
    ob.cod                      AS codigo_obra,
    ob.res                      AS nombre_obra,
    k.proveedor_id,
    pc.cod                      AS codigo_proveedor,
    pc.res                      AS nombre_proveedor,
    NULLIF(TRIM(pv.cif), '')    AS cif,
    pv.raz                      AS razon_social,
    (pv.ide IS NOT NULL)        AS es_proveedor,      -- FALSE si el entide no es ficha de proveedor
    d.dir1,
    d.dir2,
    d.dircpo                    AS codigo_postal,
    pr.res                      AS provincia,
    mu.res                      AS municipio,
    d.dir                       AS direccion_completa,
    d.tel                       AS telefono,
    k.n_contratos,
    k.importe_contratado
FROM      contratos  k
JOIN      raw.con    ob ON ob.ide = k.obra_id          -- obra (es un `con`)
JOIN      raw.con    pc ON pc.ide = k.proveedor_id     -- proveedor: código/nombre
LEFT JOIN raw.prv    pv ON pv.ide = k.proveedor_id     -- cif/razón (si es proveedor)
LEFT JOIN dir        d  ON d.conide = k.proveedor_id   -- dirección del proveedor
LEFT JOIN raw.auxpro pr ON pr.ide = d.proide
LEFT JOIN raw.auxmun mu ON mu.ide = d.munide;

COMMENT ON VIEW maestro.proveedores_obra IS
'Proveedores por obra, derivados de ctr (contratos de compra). Una fila por (obra, proveedor) con codigo/nombre/cif del proveedor, su dirección (si existe), nº de contratos e importe contratado. Filtrar por codigo_obra.';
