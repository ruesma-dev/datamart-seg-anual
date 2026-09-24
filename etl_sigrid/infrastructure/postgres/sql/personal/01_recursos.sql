-- etl_sigrid/infrastructure/postgres/sql/personal/01_recursos.sql
-- ============================================================================
-- personal.recursos — una fila por fila de `raw.res` (2.618 el 2026-09-18).
--
-- EL EJE ES EL RECURSO, NO EL EMPLEADO (D1). El hecho cuelga de
-- `hmores.reside`, así que el maestro tiene que ser el recurso. La relación
-- recurso-empleado **no es 1:1 en ninguna dirección**, medido: 824 de 2.618
-- recursos casan con empleado (31,5 %), 805 de 1.354 empleados casan con
-- recurso, 797 pares recíprocos, 24 empleados sin recurso, 3 discrepantes y
-- **3 recursos comparten `conide`** (821 valores distintos). Hacer de `emp` el
-- maestro dejaría fuera a los 530 recursos-persona sin ficha de empleado y a
-- los 1.264 que ni siquiera son personas.
--
-- QUÉ CLASIFICA Y QUÉ NO. Manda `res.cla`: 1 PERSONA (1.354), 0 CONSUMO
-- (1.158), 2 MEDIO (106). `auxrestip` **no clasifica por sí sola** —hay un
-- JEFE DE GRUPO con `cla = 0` y un CONSUMOS TELEFONO MOVIL con `cla = 2`, y
-- 492 personas y 48 medios no tienen tipo—: aporta el literal descriptivo
-- ('OFIC. 1a ALBAÑIL', 'GRUAS'), y por eso su JOIN es LEFT.
--
-- EL CRITERIO DE JUAN ROMERO ES BANDERA, NO FILTRO (D3). Su correo «RECURSOS
-- PARTES TRABAJO» del 2026-09-03 dice que los recursos en rojo están de baja.
-- «En rojo» se traduce a `con.fecbaj > 0` —`raw.res` NO tiene columna de baja
-- propia: la baja es la del CONCEPTO— y vive en la columna `activo`. Medido:
-- 1.722 de baja y 896 de alta; entre las personas, 1.034 de baja y 320 de alta.
-- **Aquí no se filtra por ella**, y esa es la decisión con más dinero detrás:
-- filtrar el hecho por `activo` borraría 539.774,87 de las 1.249.038,44 horas
-- imputadas (43,2 %), de 287 de los 445 recursos que han imputado horas. El
-- recurso de baja de hoy trabajó ayer.
--
-- Por eso este fichero **no tiene ni un WHERE**, y un test lo vigila.
--
-- CÓDIGO Y NOMBRE SALEN DE `con` (regla dura `R-SIGRID-CON`): `res` es
-- propiedad de `con` 1:1, comparte `ide` y no tiene `cod` ni `res` propios.
--
-- Y LA EMPRESA TAMBIÉN (F-102). El recurso es de UNA empresa: el mismo código
-- existe una vez por empresa —`MO/0009` tiene ficha en la 1, la 18, la 27 y la
-- 28—, así que el código solo no identifica un recurso. Se publican
-- `empresa_id` (`con.emp`), `nombre_empresa` (de `raw.auxemp` por `numemp`, en
-- un lateral `ORDER BY` + `LIMIT 1` que va DETRÁS del de `raw.emp`) y la clave
-- legible `clave_recurso` = '<empresa>-<código>', única: 2.618 para 2.618 el
-- 2026-09-23. No se publica ninguna marca de «misma persona en otra empresa»
-- (decisión del humano, F-102 D5).
--
-- Y LA CONTRAPARTIDA (F-107, pedida por Juan Romero el 2026-09-23). La ficha
-- del recurso declara contra qué centro de coste y qué cuenta analítica se
-- ABONA lo que sus partes CARGAN a la obra: sin ella no se reproduce el
-- asiento. Es del RECURSO (`res.cenconide`, `res.caaconide`), no del tipo de
-- hora. Medido en Sigrid el 2026-09-24: informada en 1.979 de 2.619 recursos,
-- siempre las dos juntas, 8 centros y 847 cuentas, 0 huérfanas. Se publican
-- solo los identificadores, con NULLIF 0 y sin JOIN: no se pierde ni se
-- multiplica ninguna fila.
--
-- DATOS PERSONALES, y con su autorización escrita: se publican **nombre y
-- DNI**. El humano lo autorizó expresamente el 2026-09-18 («el dni puede
-- salir, no es un problema»). No es un descuido ni un pendiente: es una
-- decisión del responsable del dato. Lo que NO sube es el resto de la ficha de
-- `emp` —Seguridad Social, cuenta bancaria, domicilio, fecha de nacimiento,
-- sexo, estado civil, contacto y credenciales—, y eso lo vigila una LISTA
-- BLANCA, no una negra: los `test_f057_r8_*` exigen que `raw.emp` se lea una
-- sola vez, en el lateral, y que se lean EXACTAMENTE `ide`, `dni`, `nomnom`,
-- `nomape1` y `nomape2`. Una lista negra solo protege de lo que alguien se
-- acordó de listar.
-- ============================================================================

TRUNCATE TABLE personal.recursos;

INSERT INTO personal.recursos (
    recurso_id, codigo_recurso, nombre_recurso,
    clase, tipo_recurso_id, tipo_recurso,
    activo, fecha_baja,
    nif, empleado_id, dni, nombre_pila, apellido1, apellido2,
    es_externo, proveedor_id,
    empresa_id, nombre_empresa, clave_recurso,
    centro_coste_contrapartida_id, cuenta_analitica_contrapartida_id
)
SELECT
    r.ide                                   AS recurso_id,
    c.cod                                   AS codigo_recurso,
    c.res                                   AS nombre_recurso,
    -- Manda `cla`. El `ELSE` existe para que una cuarta clase en origen salga
    -- con nombre propio en vez de como NULL silencioso.
    CASE r.cla
        WHEN 1 THEN 'PERSONA'
        WHEN 0 THEN 'CONSUMO'
        WHEN 2 THEN 'MEDIO'
        ELSE 'OTRO'
    END::VARCHAR(8)                         AS clase,
    NULLIF(r.restipide, 0)                  AS tipo_recurso_id,
    t.res                                   AS tipo_recurso,
    -- El criterio de Juan Romero, sobre el CONCEPTO: `res` no tiene baja propia.
    (COALESCE(c.fecbaj, 0) = 0)             AS activo,
    personal.fn_fecha(c.fecbaj)             AS fecha_baja,
    -- DATO PERSONAL (autorizado 2026-09-18): NIF del recurso, informado en 629
    -- de las 1.354 personas.
    NULLIF(r.cif, '')                       AS nif,
    e.ide                                   AS empleado_id,
    NULLIF(e.dni, '')                       AS dni,
    NULLIF(e.nomnom, '')                    AS nombre_pila,
    NULLIF(e.nomape1, '')                   AS apellido1,
    NULLIF(e.nomape2, '')                   AS apellido2,
    (COALESCE(r.prvide, 0) <> 0)            AS es_externo,
    NULLIF(r.prvide, 0)                     AS proveedor_id,
    c.emp                                   AS empresa_id,
    em.nombre_empresa                       AS nombre_empresa,
    c.emp::text || '-' || c.cod             AS clave_recurso,
    -- F-107. La contrapartida es del RECURSO, no del tipo de hora. Solo los
    -- identificadores: el nombre del centro y de la cuenta se resuelven en
    -- `maestro.centros_coste` y `maestro.cuentas_analiticas` por relacion,
    -- sin JOIN aqui (una fila por `raw.res`, como siempre). NO es la obra:
    -- el centro es 'CP' CENTRO PERSONAL en 1.875 de los 1.979 recursos.
    NULLIF(r.cenconide, 0)                  AS centro_coste_contrapartida_id,
    NULLIF(r.caaconide, 0)                  AS cuenta_analitica_contrapartida_id
FROM      raw.res r
JOIN      raw.con c ON c.ide = r.ide        -- R-SIGRID-CON: código y nombre
LEFT JOIN raw.auxrestip t ON t.ide = r.restipide
LEFT JOIN LATERAL (
    -- El empleado es un ATRIBUTO OPCIONAL del recurso, nunca el grano ni un
    -- filtro: 1.794 de los 2.618 recursos no tienen ficha de empleado.
    --
    -- `ORDER BY` + `LIMIT 1` es defensa en profundidad, no una necesidad de
    -- hoy: `raw.emp` SÍ tiene `PRIMARY KEY (ide)` —toda tabla de `raw` se
    -- ingiere con `ide` como clave (`ensure_raw_table`, y por eso `raw` está en
    -- `unicidad_sql.ESQUEMAS_CON_CLAVE_GARANTIZADA`)—, así que hoy el motor ya
    -- impide dos empleados con el mismo `ide`. El `LIMIT 1` fija el grano —una
    -- fila por `raw.res`— en el propio SQL, sin depender de cómo se ingiera
    -- `raw` mañana (que 3 recursos compartan `conide` no multiplica: es el
    -- lado del recurso). Mismo patrón que `maestro/04_centros_coste.sql`.
    --
    -- SOLO CINCO COLUMNAS, y esta lista es el límite de lo autorizado (R8):
    -- el identificador, el DNI y el nombre estructurado. Nada más de las 152
    -- columnas de `raw.emp` entra en el datamart curado.
    SELECT emp.ide, emp.dni, emp.nomnom, emp.nomape1, emp.nomape2
    FROM   raw.emp emp
    WHERE  emp.ide = r.conide
    ORDER  BY emp.ide
    LIMIT  1
) e ON TRUE
LEFT JOIN LATERAL (
    -- El nombre de la empresa del recurso (F-102). Detras del lateral de
    -- `raw.emp` a proposito: los guardas de la lista blanca buscan aquel.
    SELECT ae.res AS nombre_empresa
    FROM   raw.auxemp ae
    WHERE  ae.numemp = c.emp
    ORDER  BY ae.ide
    LIMIT  1
) em ON TRUE;

COMMENT ON TABLE personal.recursos IS
'Maestro de RECURSOS de Sigrid (2.618 filas el 2026-09-18), no de personal: solo 1.354 son personas, 1.158 consumos imputables y 106 medios. CONTIENE DATOS PERSONALES (nombre, NIF y DNI), autorizados por el responsable del dato el 2026-09-18. `activo` es el criterio de Juan Romero (con.fecbaj = 0) y es BANDERA, no filtro: filtrar por el borra el 43,2 % de las horas imputadas, porque el recurso de baja de hoy trabajo ayer. El recurso es de UNA empresa (F-102): el codigo se repite entre empresas, y la clave legible unica es clave_recurso = empresa-codigo. La contrapartida (centro de coste y cuenta analitica contra los que se abona lo que el parte carga a la obra) es del RECURSO, no del tipo de hora (F-107).';
