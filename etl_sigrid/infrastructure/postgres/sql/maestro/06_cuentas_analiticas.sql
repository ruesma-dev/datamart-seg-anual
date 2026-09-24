-- etl_sigrid/infrastructure/postgres/sql/maestro/06_cuentas_analiticas.sql
--
-- EL CATALOGO DE CUENTAS ANALITICAS (F-107). Lee solo de `raw`.
--
-- Lo pidio Juan Romero el 2026-09-23 para traducir las cuentas que traen el
-- recurso y su ficha de tipos de hora (496869, 496923, 496935...) a codigo y
-- descripcion, y poder reproducir el asiento de los partes.
--
-- Una cuenta analitica es un CONCEPTO de Sigrid: `con` con `tip = 19` (las
-- 184.234 de `caa`, medido el 2026-09-24) y sus propiedades en `caa`, mismo
-- `ide`. Codigo, descripcion, empresa y baja salen de `con` (R-SIGRID-CON);
-- de `caa` salen la jerarquia (padre, nivel), el centro de coste y la partida
-- presupuestaria.
--
-- EL CODIGO SOLO ES UNICO DENTRO DE SU EMPRESA (R-CODIGO-POR-EMPRESA): 14.063
-- codigos se repiten entre empresas y ninguno dentro de una. El prefijo del
-- codigo es el del centro de coste ('00000.CIMO02' es la cuenta CIMO02 del
-- centro 00000), por eso son tantas.
--
-- EL PADRE es un grupo analitico (`cag`, 18.499 filas, NO ingerida) y, en 4
-- cuentas de la empresa 18, otra cuenta `caa`. Los dos son conceptos `con`, asi
-- que su codigo y su nombre se leen de `raw.con` sin ingerir `cag`. LEFT: las
-- cuentas de nivel 1 no tienen padre y no se pierden.
--
-- `partida_presupuestaria_id` se publica porque se pidio, pero vale 0 --NULL
-- aqui-- en las 184.234 filas. `deb`, `hab`, `rep` y `prbide` tambien valen 0
-- en todas y no se publican.
--
-- GRANO: una fila por fila de `raw.caa`. Sin WHERE: se publican todas, de alta
-- y de baja. Es una VISTA, como el resto de `maestro`: no se dropea y se
-- consulta por `cuenta_analitica_id` a traves de la clave primaria de `raw.con`.
--
-- VA LA ULTIMA en `build_maestros`: lee `raw.caa`, que crea `ingest_raw`. Un
-- build a mano antes de la primera ingesta con esta version falla aqui, y solo
-- aqui (las otras seis vistas ya estan construidas).
--
-- Consumo tipico:
--   SELECT codigo_cuenta, descripcion_cuenta FROM maestro.cuentas_analiticas
--   WHERE cuenta_analitica_id IN (496869, 496923, 496935);

CREATE OR REPLACE VIEW maestro.cuentas_analiticas AS
SELECT
    a.ide                                   AS cuenta_analitica_id,
    c.emp                                   AS empresa_id,
    c.cod                                   AS codigo_cuenta,
    c.res                                   AS descripcion_cuenta,
    NULLIF(a.padide, 0)                     AS cuenta_padre_id,
    cp.cod                                  AS codigo_cuenta_padre,
    cp.res                                  AS descripcion_cuenta_padre,
    a.niv                                   AS nivel,
    NULLIF(a.cenide, 0)                     AS centro_coste_id,
    NULLIF(a.prpide, 0)                     AS partida_presupuestaria_id,
    maestro.fn_fecha(c.fecbaj)              AS fecha_baja,
    (c.fecbaj IS NULL OR c.fecbaj = 0)      AS es_activa
FROM      raw.caa a
JOIN      raw.con c  ON c.ide = a.ide          -- R-SIGRID-CON: codigo, nombre, empresa
-- El padre por la clave primaria de `raw.con`: no multiplica.
LEFT JOIN raw.con cp ON cp.ide = NULLIF(a.padide, 0);

COMMENT ON VIEW maestro.cuentas_analiticas IS
'Catalogo de cuentas analiticas de Sigrid (184.234 el 2026-09-24): codigo y descripcion (de con, tip 19), empresa, cuenta padre con su codigo y nombre, nivel, centro de coste y partida presupuestaria (vacia en todas). El codigo solo es unico dentro de su empresa. Traduce la contrapartida del recurso (personal.recursos.cuenta_analitica_contrapartida_id) y la cuenta del tipo de hora (personal.recursos_tipos_hora.cuenta_analitica_id). Sin filtrar.';
