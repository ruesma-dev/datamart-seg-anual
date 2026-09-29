-- etl_sigrid/infrastructure/postgres/sql/descompuestos/04_elementos.sql
-- ============================================================================
-- F-097 · SCHEMA descompuestos (5/7): el catalogo de elementos (R22, D9).
--
-- Lee: descompuestos.lineas, raw.pro, raw.con.
--
-- Una fila por (obra, codigo de elemento). EL GRANO ES LA OBRA porque los
-- codigos de Estudios son LIBRES por obra: 31.726 codigos distintos en el
-- ambito 3 y solo 253 son codigos de producto (medido el 2026-09-27). Lleva
-- la descripcion y la unidad mas frecuentes, el tipo mas frecuente (sin contar
-- SIN_TIPO), cuantas lineas tiene en cada origen y, cuando se puede, el
-- PRODUCTO de compras (`pro.ide`) con el que cruzar lo planificado con lo
-- comprado (F-092, F-038):
--
--   ENLACE_PLANIFICACION     el producto de sus lineas enlazadas a `dncpro`
--                            (la via fiable: el 100 % de los enlazados son
--                            codigo de producto).
--   CODIGO_PRODUCTO_EMPRESA  si no hay enlace, un producto de la MISMA empresa
--                            que la obra con ese codigo (`con.cod`): los codigos
--                            de producto se repiten una vez por empresa.
--
-- Se rehace entero cada noche (DROP + CREATE): es un derivado de `lineas`.
-- ============================================================================

DROP TABLE IF EXISTS descompuestos.elementos;

CREATE TABLE descompuestos.elementos AS
WITH agregado AS (
    SELECT
        obra_id,
        codigo_elemento,
        mode() WITHIN GROUP (ORDER BY descripcion) AS descripcion,
        mode() WITHIN GROUP (ORDER BY unidad) AS unidad,
        mode() WITHIN GROUP (ORDER BY tipo_elemento) FILTER (WHERE tipo_elemento <> 'SIN_TIPO') AS tipo_elemento,
        COUNT(*) AS num_lineas,
        COUNT(*) FILTER (WHERE origen = 'ESTUDIO') AS lineas_estudio,
        COUNT(*) FILTER (WHERE origen = 'PLANIF_JO') AS lineas_planif_jo,
        COUNT(*) FILTER (WHERE origen = 'MASTER_INICIAL') AS lineas_master_inicial,
        COUNT(*) FILTER (WHERE origen = 'MASTER_PRE_ABC') AS lineas_master_pre_abc,
        COUNT(*) FILTER (WHERE origen = 'MASTER_PLANIF_JO') AS lineas_master_planif_jo,
        mode() WITHIN GROUP (ORDER BY producto_id) AS producto_enlazado
    FROM descompuestos.lineas
    WHERE codigo_elemento IS NOT NULL
    GROUP BY obra_id, codigo_elemento
),
producto_empresa AS (
    SELECT c.emp, c.cod, MIN(p.ide) AS producto_id
    FROM raw.pro p JOIN raw.con c ON c.ide = p.ide
    WHERE NULLIF(btrim(c.cod), '') IS NOT NULL
    GROUP BY c.emp, c.cod
)
SELECT
    a.obra_id,
    a.codigo_elemento,
    a.descripcion AS descripcion,
    a.unidad AS unidad,
    COALESCE(a.tipo_elemento, 'SIN_TIPO') AS tipo_elemento,
    a.num_lineas::INTEGER AS num_lineas,
    a.lineas_estudio::INTEGER AS lineas_estudio,
    a.lineas_planif_jo::INTEGER AS lineas_planif_jo,
    a.lineas_master_inicial::INTEGER AS lineas_master_inicial,
    a.lineas_master_pre_abc::INTEGER AS lineas_master_pre_abc,
    a.lineas_master_planif_jo::INTEGER AS lineas_master_planif_jo,
    COALESCE(a.producto_enlazado, pe.producto_id) AS producto_id,
    CASE
        WHEN a.producto_enlazado IS NOT NULL THEN 'ENLACE_PLANIFICACION'
        WHEN pe.producto_id IS NOT NULL THEN 'CODIGO_PRODUCTO_EMPRESA'
    END AS via_producto
FROM agregado a
LEFT JOIN raw.con co ON co.ide = a.obra_id
LEFT JOIN producto_empresa pe ON pe.emp = co.emp AND pe.cod = a.codigo_elemento;

ALTER TABLE descompuestos.elementos ADD PRIMARY KEY (obra_id, codigo_elemento);

COMMENT ON TABLE descompuestos.elementos IS
'F-097. Catalogo de elementos de descompuesto por (obra, codigo), con su producto de compras cuando se conoce (via_producto).';
