-- etl_sigrid/infrastructure/postgres/sql/maestro/02_proveedores.sql
--
-- Maestro GLOBAL de proveedores para consulta externa.
-- Un proveedor es una entidad `con` con propiedades `prv` (mismo ide) y, si
-- la tiene cargada, una dirección en `condir` (conide = ide).
--
-- NOTA: no es "proveedores POR obra" (ver 03_proveedores_obra.sql). La tabla
-- `obrprv` de Sigrid está vacía en Ruesma; el vínculo obra↔proveedor vive en
-- los contratos de compra (`ctr`).
--
-- Consumo típico:
--   SELECT codigo, nombre, cif FROM maestro.proveedores ORDER BY nombre;
--   SELECT * FROM maestro.proveedores WHERE cif = 'A28157360';

CREATE OR REPLACE VIEW maestro.proveedores AS
WITH dir AS (
    -- Una dirección por entidad (la de menor pos). Muchos proveedores no
    -- tienen ninguna en condir → los campos de dirección saldrán NULL.
    SELECT DISTINCT ON (conide)
        conide, dir1, dir2, dircpo, dir, proide, munide, tel
    FROM   raw.condir
    ORDER  BY conide, pos NULLS LAST, ide
)
SELECT
    p.ide                       AS proveedor_id,
    c.cod                       AS codigo,
    c.res                       AS nombre,
    NULLIF(TRIM(p.cif), '')     AS cif,
    p.raz                       AS razon_social,
    d.dir1,
    d.dir2,
    d.dircpo                    AS codigo_postal,
    pr.res                      AS provincia,
    mu.res                      AS municipio,
    d.dir                       AS direccion_completa,
    d.tel                       AS telefono
FROM      raw.prv    p
JOIN      raw.con    c  ON c.ide  = p.ide
LEFT JOIN dir        d  ON d.conide = p.ide
LEFT JOIN raw.auxpro pr ON pr.ide = d.proide
LEFT JOIN raw.auxmun mu ON mu.ide = d.munide;

COMMENT ON VIEW maestro.proveedores IS
'Maestro global de proveedores: codigo, nombre, cif, razon_social y dirección (cuando existe en condir; la mayoría no la tiene). NO es proveedores por obra.';
