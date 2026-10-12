-- etl_sigrid/infrastructure/postgres/sql/contabilidad/04_plan_cuentas_general.sql
-- ============================================================================
-- F-135 · SCHEMA contabilidad (5/8): EL PLAN DE CUENTAS GENERAL
--
-- Construye:
--   contabilidad.plan_cuentas   una fila por nodo del plan, como el completo,
--                               con los nombres de las cuentas CR enmascarados
--
-- Lee SOLO de contabilidad_restringida.plan_cuentas (01).
--
-- QUE CAMBIA RESPECTO AL COMPLETO (R12, D6)
-- ---------------------------------------------------------------------------
-- · Conserva TODOS los nodos, con sus columnas de F-056 en su orden, y anade
--   al final `restringida`: TRUE en las cuentas auxiliares (nivel 5) cuyo
--   codigo es CR (521 medidas el 2026-10-09). Los grupos de 1 a 4 digitos
--   (640, 4753...) son los epigrafes del PGC y no se enmascaran.
-- · En esas cuentas `nombre_cuenta` vale '(cuenta restringida)': que exista
--   una cuenta de prestamo o de embargo a nombre de alguien ya es el dato. El
--   codigo, la clave y la ruta (solo codigos) se quedan: sin ellos no se puede
--   decir que la cuenta existe y esta restringida.
--
-- La regex de los 14 prefijos es la del dominio, escrita tal cual (R4).
-- ============================================================================

DROP TABLE IF EXISTS contabilidad.plan_cuentas CASCADE;
CREATE TABLE contabilidad.plan_cuentas AS
WITH marcadas AS (
    SELECT
        r.*,
        COALESCE(r.nivel = 5 AND r.codigo_cuenta ~ '^(640|641|642|643|644|645|649|465|466|476|460|461|544|4753)', FALSE) AS restringida
    FROM contabilidad_restringida.plan_cuentas r
)
SELECT
    m.cuenta_id,
    m.empresa_id,
    m.empresa_nombre,
    m.codigo_cuenta,
    m.clave_cuenta,
    CASE WHEN m.restringida THEN '(cuenta restringida)'
         ELSE m.nombre_cuenta END                                AS nombre_cuenta,
    m.nivel,
    m.nombre_nivel,
    m.es_imputable,
    m.grupo_pgc,
    m.cuenta_padre_id,
    m.cuenta_padre_declarada_id,
    m.padre_declarado_difiere,
    m.grupo_id,
    m.subgrupo_id,
    m.cuenta_3_id,
    m.subcuenta_id,
    m.ruta_codigos,
    m.fecha_baja,
    m.es_activa,
    m.restringida
FROM marcadas m;

ALTER TABLE contabilidad.plan_cuentas ADD PRIMARY KEY (cuenta_id);
-- R-CODIGO-POR-EMPRESA: el codigo solo es unico DENTRO de la empresa
CREATE UNIQUE INDEX uq_con_plan_empresa_codigo ON contabilidad.plan_cuentas (empresa_id, codigo_cuenta);
CREATE INDEX idx_con_plan_padre ON contabilidad.plan_cuentas (cuenta_padre_id);

COMMENT ON TABLE contabilidad.plan_cuentas IS
'F-056 y F-135. El plan de cuentas FINANCIERO como arbol, una fila por nodo de las 38 empresas (grupos de niveles 1-4 y cuentas auxiliares de nivel 5, las unicas imputables). Las cuentas auxiliares de PERSONAL (restringida = TRUE) llevan el nombre enmascarado: su detalle solo lo lee el rol autorizado en contabilidad_restringida. (empresa_id, codigo_cuenta) es unico; el codigo solo no lo es. No es el plan analitico de maestro.cuentas_analiticas.';
