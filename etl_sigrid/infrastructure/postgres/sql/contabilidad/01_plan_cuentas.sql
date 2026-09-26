-- etl_sigrid/infrastructure/postgres/sql/contabilidad/01_plan_cuentas.sql
-- ============================================================================
-- F-056 · SCHEMA contabilidad (2/4): EL PLAN DE CUENTAS COMO ARBOL
--
-- Construye:
--   contabilidad.plan_cuentas   una fila por nodo del plan FINANCIERO
--
-- Lee de raw.con, raw.cua y raw.auxemp. Nada mas (R2).
--
-- LO QUE EL DATO ES (medido el 2026-09-26; corrige lo que decia F-066)
-- ---------------------------------------------------------------------------
-- · `con.tip = 16` son los GRUPOS del plan: 44.778 filas de las 38 empresas,
--   con codigos de 1 a 4 digitos (321 / 2.673 / 15.017 / 26.767). Son la tabla
--   `cug` de Sigrid, que no se ingiere (D7).
-- · `raw.cua` son las CUENTAS AUXILIARES (`con.tip = 17`, 34.196, todas de 10
--   digitos) y las UNICAS con apuntes. Nivel 5, la unica imputable (R8).
-- · El plan se parte por EMPRESA: el mismo codigo existe una vez por empresa
--   (R-CODIGO-POR-EMPRESA). (empresa_id, codigo_cuenta) es unico (R7).
-- · Todas las empresas y sin filtrar altas ni bajas (R6, D1): `es_activa` es
--   bandera, no filtro.
--
-- EL ARBOL ES DE PREFIJOS, DENTRO DE LA EMPRESA (R9, D7)
-- ---------------------------------------------------------------------------
-- El padre de un grupo de 2-4 digitos es el grupo de su MISMA empresa cuyo
-- codigo es el suyo sin el ultimo digito (el 100 % lo tiene); el de una cuenta
-- auxiliar, el grupo de sus 4 primeros digitos. Nivel 1, o sin ese prefijo ->
-- NULL; nunca un padre de otra empresa (la union lleva la empresa). Sin
-- `WITH RECURSIVE`: la profundidad la fija la longitud del codigo y no hay
-- ciclo posible (el camino de los ciclos de F-052 queda fuera).
-- El padre DECLARADO de la auxiliar (`cua.padide`) se publica aparte (R10):
-- coincide con el prefijo en 33.838, esta a 0 en 352 y DIFIERE en 6 (empresas
-- 12, 17 y 18): `padre_declarado_difiere`.
--
-- LOS ANCESTROS POR NIVEL (R11)
-- ---------------------------------------------------------------------------
-- `grupo_id`, `subgrupo_id`, `cuenta_3_id` y `subcuenta_id` son el grupo de la
-- misma empresa cuyo codigo es el prefijo de 1, 2, 3 y 4 digitos, cuando el
-- nodo es de ese nivel o mas profundo: el nodo de nivel 3 es su propio
-- `cuenta_3_id`, y los niveles por debajo del suyo van a NULL. Es lo que deja
-- agregar el balance por cualquier nivel con un GROUP BY, sin recorrer el
-- arbol. `ruta_codigos` son los codigos de esa cadena ('4 > 43 > 430 > 4308 >
-- 4308000197') y `grupo_pgc` el primer digito.
--
-- Todas las uniones van contra algo UNICO por su clave: `grupos` por
-- (emp, cod) (medido: 44.778 pares para 44.778 filas; si dejara de serlo, la
-- PK de abajo hace fallar el build aqui con su nombre) y `empresas`
-- pre-agregada por `numemp`.
-- ============================================================================

DROP TABLE IF EXISTS contabilidad.plan_cuentas CASCADE;
CREATE TABLE contabilidad.plan_cuentas AS
WITH grupos AS (
    SELECT g.ide, g.emp, g.cod
    FROM raw.con g
    WHERE g.tip = 16
),
empresas AS (
    SELECT e.numemp AS empresa_id, MIN(e.res) AS empresa_nombre
    FROM raw.auxemp e
    GROUP BY e.numemp
),
nodos AS (
    -- los grupos del plan: niveles 1 a 4 por la longitud del codigo
    SELECT
        c.ide                   AS cuenta_id,
        c.emp                   AS empresa_id,
        c.cod                   AS codigo_cuenta,
        c.res                   AS nombre_cuenta,
        c.fecbaj                AS fecbaj,
        LENGTH(c.cod)           AS nivel,
        NULL::INT               AS cuenta_padre_declarada_id
    FROM raw.con c
    WHERE c.tip = 16
    UNION ALL
    -- las cuentas auxiliares: nivel 5, con su padre declarado
    SELECT
        c.ide,
        c.emp,
        c.cod,
        c.res,
        c.fecbaj,
        5,
        NULLIF(cu.padide, 0)
    FROM raw.cua cu
    JOIN raw.con c ON c.ide = cu.ide
)
SELECT
    n.cuenta_id,
    n.empresa_id,
    em.empresa_nombre,
    n.codigo_cuenta,
    n.empresa_id::TEXT || '-' || n.codigo_cuenta AS clave_cuenta,
    n.nombre_cuenta,
    n.nivel,
    CASE n.nivel WHEN 1 THEN 'GRUPO' WHEN 2 THEN 'SUBGRUPO' WHEN 3 THEN 'CUENTA'
                 WHEN 4 THEN 'SUBCUENTA' WHEN 5 THEN 'CUENTA_AUXILIAR' END AS nombre_nivel,
    n.nivel = 5 AS es_imputable,
    LEFT(n.codigo_cuenta, 1) AS grupo_pgc,
    pad.ide AS cuenta_padre_id,
    n.cuenta_padre_declarada_id,
    (n.cuenta_padre_declarada_id IS NOT NULL
        AND n.cuenta_padre_declarada_id IS DISTINCT FROM pad.ide) AS padre_declarado_difiere,
    g1.ide AS grupo_id,
    g2.ide AS subgrupo_id,
    g3.ide AS cuenta_3_id,
    g4.ide AS subcuenta_id,
    CONCAT_WS(' > ', g1.cod, g2.cod, g3.cod, g4.cod,
              CASE WHEN n.nivel = 5 THEN n.codigo_cuenta END) AS ruta_codigos,
    contabilidad.fn_fecha(n.fecbaj) AS fecha_baja,
    COALESCE(n.fecbaj, 0) = 0 AS es_activa
FROM nodos n
LEFT JOIN empresas em ON em.empresa_id = n.empresa_id
LEFT JOIN grupos pad ON pad.emp = n.empresa_id
    AND pad.cod = CASE WHEN n.nivel = 5 THEN LEFT(n.codigo_cuenta, 4)
                       WHEN n.nivel > 1 THEN LEFT(n.codigo_cuenta, n.nivel - 1) END
LEFT JOIN grupos g1 ON g1.emp = n.empresa_id AND g1.cod = LEFT(n.codigo_cuenta, 1)
LEFT JOIN grupos g2 ON g2.emp = n.empresa_id AND n.nivel >= 2 AND g2.cod = LEFT(n.codigo_cuenta, 2)
LEFT JOIN grupos g3 ON g3.emp = n.empresa_id AND n.nivel >= 3 AND g3.cod = LEFT(n.codigo_cuenta, 3)
LEFT JOIN grupos g4 ON g4.emp = n.empresa_id AND n.nivel >= 4 AND g4.cod = LEFT(n.codigo_cuenta, 4);

ALTER TABLE contabilidad.plan_cuentas ADD PRIMARY KEY (cuenta_id);
-- R-CODIGO-POR-EMPRESA: el codigo solo es unico DENTRO de la empresa
CREATE UNIQUE INDEX uq_con_plan_empresa_codigo ON contabilidad.plan_cuentas (empresa_id, codigo_cuenta);
CREATE INDEX idx_con_plan_padre ON contabilidad.plan_cuentas (cuenta_padre_id);

COMMENT ON TABLE contabilidad.plan_cuentas IS
'F-056. El plan de cuentas FINANCIERO como arbol, una fila por nodo de las 38 empresas: grupos de raw.con tip 16 (niveles 1-4 por la longitud del codigo) y cuentas auxiliares de raw.cua (nivel 5, las unicas imputables). El padre es el grupo de la MISMA empresa cuyo codigo es el prefijo inmediato; el declarado de la auxiliar va aparte. (empresa_id, codigo_cuenta) es unico; el codigo solo no lo es. No es el plan analitico de maestro.cuentas_analiticas.';
