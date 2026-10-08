-- etl_sigrid/infrastructure/postgres/sql/personal/06_usuarios_sigrid.sql
-- ============================================================================
-- F-085 · `personal.usuarios_sigrid`: los USUARIOS de Sigrid con su persona.
--
-- Una fila por fila de `raw.usu` (233 el 2026-10-07), clave `usuario_id`
-- (`usu.ide`). Es lo que convierte el login de `compras.documento_procesos`
-- (y de `comparativo_firmas`, `comparativos.aprobado_por`...) en una persona:
-- el login casa en MAYÚSCULAS y sin espacios (`normalizar_login`).
--
-- DATOS PERSONALES, autorizados por el humano: el nombre y el DNI (2026-09-18
-- para el esquema `personal`; 2026-10-07, D4 de F-085, para los usuarios). Por
-- eso esta tabla vive en `personal` y no en `compras`: el acceso se da o se
-- quita con el GRANT del esquema. `compras` solo publica login y nombre.
--
-- LO QUE NO SUBE, y no puede subir porque `raw.usu` no lo trae: las
-- credenciales (`cla`, `fir`, `feccla`, `diascla`, `sid`, `cerid`), el DNI de
-- `usu` (vacío en las 233), el correo (`ele`) y los textos libres (`com`,
-- `resdes`). Las excluye la ingesta (`config/tables_sigrid.yaml`) y un test
-- vigila que este fichero no nombre ninguna.
--
-- EL EMPLEADO (R18, `empleado_de_usuario`): la ficha de empleado (`con` tipo
-- 43) cuyo código es `usu.codemp`. Si hay una, ésa; si hay varias (una por
-- empresa), la ÚNICA de la empresa 1 (`EMPRESA_PREFERENTE`); si no, NULL.
-- Medido el 2026-10-07: 211 usuarios con código, 210 casan, 189 con una sola
-- ficha y 21 con varias, las 21 con una en la empresa 1. Se agrupa por código
-- ANTES de unir, así que nunca multiplica (y lee `raw.con` una vez, no una por
-- usuario). El DNI es `raw.emp.dni` de ese empleado (~204), como en
-- `01_recursos.sql`.
--
-- Idempotente: la tabla la crea `00_setup.sql` (nunca DROP: se llevaría los
-- GRANT); aquí `TRUNCATE` + `INSERT`.
-- ============================================================================

TRUNCATE TABLE personal.usuarios_sigrid;

INSERT INTO personal.usuarios_sigrid (
    usuario_id, login, nombre, desactivado, codigo_empleado, empleado_id, dni
)
WITH empleados AS (
    -- Una fila por código de empleado: la regla de `empleado_de_usuario`.
    SELECT BTRIM(c.cod) AS codigo,
           CASE
               WHEN COUNT(*) = 1 THEN MIN(c.ide)
               WHEN COUNT(*) FILTER (WHERE c.emp = 1) = 1
                   THEN MIN(c.ide) FILTER (WHERE c.emp = 1)
           END          AS empleado_id
    FROM   raw.con c
    WHERE  c.tip = 43
    GROUP  BY BTRIM(c.cod)
)
SELECT
    u.ide                                   AS usuario_id,
    BTRIM(u.cod)                            AS login,
    NULLIF(BTRIM(u.res), '')                AS nombre,
    (COALESCE(u.tipdes, 0) <> 0)            AS desactivado,
    NULLIF(BTRIM(u.codemp), '')             AS codigo_empleado,
    em.empleado_id                          AS empleado_id,
    -- DATO PERSONAL (autorizado): el DNI del empleado, no el de `usu`.
    NULLIF(BTRIM(e.dni), '')                AS dni
FROM      raw.usu u
LEFT JOIN empleados em ON em.codigo = NULLIF(BTRIM(u.codemp), '')
LEFT JOIN raw.emp e    ON e.ide = em.empleado_id;

COMMENT ON TABLE personal.usuarios_sigrid IS
'Usuarios de Sigrid (raw.usu, 233 filas el 2026-10-07) con su persona (F-085): login, nombre, si esta desactivado y, por el codigo de empleado, el empleado (con tipo 43; si hay una ficha por empresa, la de la empresa 1) y su DNI (raw.emp). CONTIENE DATOS PERSONALES (nombre y DNI), autorizados por el responsable del dato (2026-09-18 y 2026-10-07). Sin credenciales ni correo: la ingesta no los trae. El login casa con compras.documento_procesos.usuario en mayusculas y sin espacios.';
