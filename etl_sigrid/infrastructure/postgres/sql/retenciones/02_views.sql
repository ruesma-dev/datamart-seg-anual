-- etl_sigrid/infrastructure/postgres/sql/retenciones/02_views.sql
-- ============================================================================
-- Vistas de negocio del módulo retenciones (Tanda R1).
--
--   v_pbi_retencion_entidad   → saldo por proveedor / cliente
--   v_pbi_retencion_obra      → saldo por obra, en ambos sentidos
--   v_pbi_retenciones_vivas   → detalle operativo de lo aún retenido
--   v_pbi_retenciones_vencidas→ vencidas y sin liquidar (para reclamar)
--   v_pbi_retencion_resumen   → una fila por sentido: foto global
--
-- SOBRE EL CÁLCULO DEL SALDO
-- ---------------------------------------------------------------------------
-- Se exponen DOS lecturas en paralelo porque conviven dos mecanismos:
--   a) `saldo_vivo`      = suma de los efectos con estado VIVA (fecrea = 0).
--      Es la lectura principal: lo que Sigrid considera aún no liquidado.
--   b) `neto_practicado` = suma de TODOS los efectos (cargos menos abonos).
--      Útil si parte de las devoluciones se registran como efecto negativo
--      en lugar de marcarse con fecrea.
-- Si ambas cifras divergen mucho para una entidad, conviene mirar el detalle:
-- indica que esa retención se liquidó por el otro mecanismo.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- SALDO POR ENTIDAD (proveedor o cliente)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW retenciones.v_pbi_retencion_entidad AS
SELECT
    sentido,
    entidad_id,
    entidad_nombre,
    entidad_cif,
    COUNT(*)                                                AS num_movimientos,
    -- Lectura (a): por estado
    SUM(importe) FILTER (WHERE estado = 'VIVA')             AS saldo_vivo,
    SUM(importe) FILTER (WHERE estado = 'LIQUIDADA')        AS importe_liquidado,
    COUNT(*)     FILTER (WHERE estado = 'VIVA')             AS num_vivas,
    COUNT(*)     FILTER (WHERE estado = 'LIQUIDADA')        AS num_liquidadas,
    -- Lectura (b): por signo
    SUM(importe) FILTER (WHERE importe > 0)                 AS total_cargos,
    SUM(-importe) FILTER (WHERE importe < 0)                AS total_abonos,
    SUM(importe)                                            AS neto_practicado,
    -- Vencidas
    SUM(importe) FILTER (WHERE vencida_sin_liquidar)        AS importe_vencido,
    COUNT(*)     FILTER (WHERE vencida_sin_liquidar)        AS num_vencidas,
    MIN(fecha_prevista_devolucion)                          AS primera_devolucion_prevista,
    MAX(fecha_prevista_devolucion)                          AS ultima_devolucion_prevista
FROM retenciones.movimientos
WHERE entidad_id IS NOT NULL
GROUP BY sentido, entidad_id, entidad_nombre, entidad_cif;

COMMENT ON VIEW retenciones.v_pbi_retencion_entidad IS
'Saldo de retenciones por proveedor (sentido PROVEEDOR) o cliente (CLIENTE). '
'saldo_vivo = aún retenido. importe_vencido = ya debería haberse liquidado.';


-- ---------------------------------------------------------------------------
-- SALDO POR OBRA (las dos direcciones a la vez)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW retenciones.v_pbi_retencion_obra AS
SELECT
    obra_id,
    codigo_obra,
    nombre_obra,
    -- Lo que retenemos a proveedores (dinero nuestro pendiente de pagar)
    SUM(importe) FILTER (WHERE sentido = 'PROVEEDOR' AND estado = 'VIVA')
                                                        AS retenido_a_proveedores,
    COUNT(*)     FILTER (WHERE sentido = 'PROVEEDOR' AND estado = 'VIVA')
                                                        AS num_retenciones_proveedor,
    SUM(importe) FILTER (WHERE sentido = 'PROVEEDOR' AND estado = 'LIQUIDADA')
                                                        AS devuelto_a_proveedores,
    -- Lo que nos retiene el cliente (dinero nuestro pendiente de cobrar)
    SUM(importe) FILTER (WHERE sentido = 'CLIENTE' AND estado = 'VIVA')
                                                        AS retenido_por_cliente,
    COUNT(*)     FILTER (WHERE sentido = 'CLIENTE' AND estado = 'VIVA')
                                                        AS num_retenciones_cliente,
    SUM(importe) FILTER (WHERE sentido = 'CLIENTE' AND estado = 'LIQUIDADA')
                                                        AS cobrado_de_cliente,
    -- Posición neta: positivo = retenemos más de lo que nos retienen
    COALESCE(SUM(importe) FILTER (WHERE sentido = 'PROVEEDOR' AND estado = 'VIVA'), 0)
      - COALESCE(SUM(importe) FILTER (WHERE sentido = 'CLIENTE' AND estado = 'VIVA'), 0)
                                                        AS posicion_neta,
    -- Vencidas
    SUM(importe) FILTER (WHERE vencida_sin_liquidar AND sentido = 'PROVEEDOR')
                                                        AS vencido_proveedores,
    SUM(importe) FILTER (WHERE vencida_sin_liquidar AND sentido = 'CLIENTE')
                                                        AS vencido_cliente
FROM retenciones.movimientos
WHERE obra_id IS NOT NULL
GROUP BY obra_id, codigo_obra, nombre_obra;

COMMENT ON VIEW retenciones.v_pbi_retencion_obra IS
'Retenciones por obra en ambos sentidos. posicion_neta > 0 significa que en '
'esa obra retenemos a proveedores más de lo que el cliente nos retiene.';


-- ---------------------------------------------------------------------------
-- DETALLE DE RETENCIONES VIVAS
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW retenciones.v_pbi_retenciones_vivas AS
SELECT
    sentido,
    movimiento_id,
    codigo_documento,
    fecha_documento,
    entidad_nombre,
    entidad_cif,
    codigo_obra,
    nombre_obra,
    tipo_descripcion,
    importe,
    fecha_prevista_devolucion,
    vencida_sin_liquidar,
    dias_desde_vencimiento,
    num_obras_documento
FROM retenciones.movimientos
WHERE estado = 'VIVA';

COMMENT ON VIEW retenciones.v_pbi_retenciones_vivas IS
'Detalle de cada retención aún no liquidada. num_obras_documento > 1 indica '
'una factura repartida entre varias obras (la obra puede no estar resuelta).';


-- ---------------------------------------------------------------------------
-- VENCIDAS SIN LIQUIDAR (lo accionable)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW retenciones.v_pbi_retenciones_vencidas AS
SELECT
    sentido,
    movimiento_id,
    codigo_documento,
    fecha_documento,
    entidad_nombre,
    entidad_cif,
    codigo_obra,
    nombre_obra,
    importe,
    fecha_prevista_devolucion,
    dias_desde_vencimiento,
    CASE
        WHEN dias_desde_vencimiento >  730 THEN 'Más de 2 años'
        WHEN dias_desde_vencimiento >  365 THEN '1-2 años'
        WHEN dias_desde_vencimiento >  180 THEN '6-12 meses'
        WHEN dias_desde_vencimiento >   90 THEN '3-6 meses'
        ELSE 'Menos de 3 meses'
    END                                     AS antiguedad
FROM retenciones.movimientos
WHERE vencida_sin_liquidar = TRUE;

COMMENT ON VIEW retenciones.v_pbi_retenciones_vencidas IS
'Retenciones cuya fecha prevista de devolución ya pasó y siguen vivas. '
'sentido CLIENTE = reclamar cobro; sentido PROVEEDOR = pendiente de liberar.';


-- ---------------------------------------------------------------------------
-- RESUMEN GLOBAL
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW retenciones.v_pbi_retencion_resumen AS
SELECT
    sentido,
    COUNT(*)                                            AS num_movimientos,
    COUNT(DISTINCT entidad_id)                          AS num_entidades,
    COUNT(DISTINCT obra_id)                             AS num_obras,
    SUM(importe) FILTER (WHERE estado = 'VIVA')         AS saldo_vivo,
    COUNT(*)     FILTER (WHERE estado = 'VIVA')         AS num_vivas,
    SUM(importe) FILTER (WHERE estado = 'LIQUIDADA')    AS importe_liquidado,
    COUNT(*)     FILTER (WHERE estado = 'LIQUIDADA')    AS num_liquidadas,
    SUM(importe) FILTER (WHERE vencida_sin_liquidar)    AS importe_vencido,
    COUNT(*)     FILTER (WHERE vencida_sin_liquidar)    AS num_vencidas,
    SUM(importe)                                        AS neto_practicado,
    COUNT(*) FILTER (WHERE obra_id IS NULL)             AS sin_obra_asignada
FROM retenciones.movimientos
GROUP BY sentido;

COMMENT ON VIEW retenciones.v_pbi_retencion_resumen IS
'Foto global por sentido. sin_obra_asignada permite vigilar la calidad de la '
'atribución a obra (efectos sin cenide y con factura multi-obra).';
