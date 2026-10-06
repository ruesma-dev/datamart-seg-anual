-- etl_sigrid/infrastructure/postgres/sql/descompuestos/06_views.sql
-- ============================================================================
-- F-097 · SCHEMA descompuestos (7/7): las cuatro vistas de consumo para Power BI
-- (R24; la cuarta, F-123), CADA UNA CON SU ORIGEN CABLEADO.
--
-- Lee: descompuestos.lineas.
--
-- Existen para que ni Power BI ni un agente puedan mezclar el descompuesto de
-- Estudios con la planificacion del jefe de obra (`R-DESCOMPUESTO-ORIGEN`):
-- quien lee una vista lee un solo origen, sin tener que acordarse del filtro.
-- Cada una publica las columnas que ese origen informa:
--
--   v_pbi_estudio           ESTUDIO: Estudios en las obras SIN master 0 (la
--                           «Descomposicion» de la fase viva, ambito 3).
--   v_pbi_planif_jo         PLANIF_JO: la planificacion de compras del jefe de
--                           obra, con proveedor, contrato y fecha maxima.
--   v_pbi_master_planif_jo  MASTER_PLANIF_JO: el master desde la primera ABC,
--                           TODAS sus versiones con sus marcas (se filtra por
--                           `es_vigente` o por `fase_num` para ver una).
--   v_pbi_master_estudio    MASTER_ESTUDIO (F-123): Estudios en las obras CON
--                           master 0, con las MISMAS columnas y orden que
--                           `v_pbi_estudio`: Estudios entero son las dos
--                           vistas juntas (cada obra esta en una sola).
--
-- `factor` (F-120) va la ULTIMA (D8): `CREATE OR REPLACE VIEW` solo admite
-- columnas nuevas al final. La vista de F-123 va al final del fichero.
--
-- F-067 (con F-125, R20): `necesidad_id`, el DOCUMENTO de necesidades de compra
-- (el DPC de la obra, `compras.necesidades`) de la linea de necesidad, va
-- DETRAS de `factor` en las dos vistas que tienen `dncpro_id` (PLANIF_JO y
-- MASTER_PLANIF_JO). Por SUBCONSULTA ESCALAR a la PK de `raw.dncpro` y no por
-- JOIN, para que el `FROM descompuestos.lineas WHERE origen = ...` (R24) no
-- cambie; y leyendo `raw`, NO `compras.necesidades`, porque `build_compras`
-- hace `DROP ... CASCADE` cada noche y se llevaria estas vistas. Ni la tabla
-- `descompuestos.lineas` ni los ficheros del sello cambian: no retrocea nada.
-- ============================================================================

CREATE OR REPLACE VIEW descompuestos.v_pbi_estudio AS
SELECT
    obra_id, partida_id, presupuesto_id, orden,
    codigo_elemento, descripcion, unidad, codigo_alternativo,
    tipo_elemento_codigo, tipo_elemento, naturaleza_codigo, naturaleza,
    rendimiento, precio, importe_unitario, cantidad_total, importe_total,
    es_porcentaje, porcentaje, base_porcentaje, factor
FROM descompuestos.lineas WHERE origen = 'ESTUDIO';

CREATE OR REPLACE VIEW descompuestos.v_pbi_planif_jo AS
SELECT
    obra_id, partida_id, orden,
    codigo_elemento, descripcion, unidad, codigo_alternativo,
    naturaleza_codigo, naturaleza,
    rendimiento, precio, importe_unitario, cantidad_total, importe_total,
    dncpro_id, producto_id, proveedor_recomendado_id, contrato_id,
    contrato_linea_id, fecha_maxima, grupo_planificacion_id, nivel, es_nivel_padre,
    factor,
    (SELECT NULLIF(n.dncide, 0) FROM raw.dncpro n WHERE n.ide = lineas.dncpro_id) AS necesidad_id
FROM descompuestos.lineas WHERE origen = 'PLANIF_JO';

CREATE OR REPLACE VIEW descompuestos.v_pbi_master_planif_jo AS
SELECT
    obra_id, partida_id, presupuesto_id, fase_num, orden,
    codigo_elemento, descripcion, unidad, codigo_alternativo,
    tipo_elemento_codigo, tipo_elemento, naturaleza_codigo, naturaleza,
    rendimiento, precio, importe_unitario, cantidad_total, importe_total,
    es_porcentaje, porcentaje, base_porcentaje, dncpro_id, producto_id,
    es_primera_abc, es_vigente, es_ultima, tipo_version, texto_version, factor,
    (SELECT NULLIF(n.dncide, 0) FROM raw.dncpro n WHERE n.ide = lineas.dncpro_id) AS necesidad_id
FROM descompuestos.lineas WHERE origen = 'MASTER_PLANIF_JO';

CREATE OR REPLACE VIEW descompuestos.v_pbi_master_estudio AS
SELECT
    obra_id, partida_id, presupuesto_id, orden,
    codigo_elemento, descripcion, unidad, codigo_alternativo,
    tipo_elemento_codigo, tipo_elemento, naturaleza_codigo, naturaleza,
    rendimiento, precio, importe_unitario, cantidad_total, importe_total,
    es_porcentaje, porcentaje, base_porcentaje, factor
FROM descompuestos.lineas WHERE origen = 'MASTER_ESTUDIO';
