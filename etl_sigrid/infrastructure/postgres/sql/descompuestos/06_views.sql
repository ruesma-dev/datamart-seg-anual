-- etl_sigrid/infrastructure/postgres/sql/descompuestos/06_views.sql
-- ============================================================================
-- F-097 · SCHEMA descompuestos (7/7): las tres vistas de consumo para Power BI
-- (R24), CADA UNA CON SU ORIGEN CABLEADO.
--
-- Lee: descompuestos.lineas.
--
-- Existen para que ni Power BI ni un agente puedan mezclar el descompuesto de
-- Estudios con la planificacion del jefe de obra (`R-DESCOMPUESTO-ORIGEN`):
-- quien lee una vista lee un solo origen, sin tener que acordarse del filtro.
-- Cada una publica las columnas que ese origen informa:
--
--   v_pbi_estudio           ESTUDIO: la referencia de Estudios (ambito 3).
--   v_pbi_planif_jo         PLANIF_JO: la planificacion de compras del jefe de
--                           obra, con proveedor, contrato y fecha maxima.
--   v_pbi_master_planif_jo  MASTER_PLANIF_JO: el master desde la primera ABC,
--                           TODAS sus versiones con sus marcas (se filtra por
--                           `es_vigente` o por `fase_num` para ver una).
-- ============================================================================

CREATE OR REPLACE VIEW descompuestos.v_pbi_estudio AS
SELECT
    obra_id, partida_id, presupuesto_id, orden,
    codigo_elemento, descripcion, unidad, codigo_alternativo,
    tipo_elemento_codigo, tipo_elemento, naturaleza_codigo, naturaleza,
    rendimiento, precio, importe_unitario, cantidad_total, importe_total,
    es_porcentaje, porcentaje, base_porcentaje
FROM descompuestos.lineas WHERE origen = 'ESTUDIO';

CREATE OR REPLACE VIEW descompuestos.v_pbi_planif_jo AS
SELECT
    obra_id, partida_id, orden,
    codigo_elemento, descripcion, unidad, codigo_alternativo,
    naturaleza_codigo, naturaleza,
    rendimiento, precio, importe_unitario, cantidad_total, importe_total,
    dncpro_id, producto_id, proveedor_recomendado_id, contrato_id,
    contrato_linea_id, fecha_maxima, grupo_planificacion_id, nivel, es_nivel_padre
FROM descompuestos.lineas WHERE origen = 'PLANIF_JO';

CREATE OR REPLACE VIEW descompuestos.v_pbi_master_planif_jo AS
SELECT
    obra_id, partida_id, presupuesto_id, fase_num, orden,
    codigo_elemento, descripcion, unidad, codigo_alternativo,
    tipo_elemento_codigo, tipo_elemento, naturaleza_codigo, naturaleza,
    rendimiento, precio, importe_unitario, cantidad_total, importe_total,
    es_porcentaje, porcentaje, base_porcentaje, dncpro_id, producto_id,
    es_primera_abc, es_vigente, es_ultima, tipo_version, texto_version
FROM descompuestos.lineas WHERE origen = 'MASTER_PLANIF_JO';
