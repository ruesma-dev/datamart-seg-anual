-- etl_sigrid/infrastructure/postgres/sql/personal/00_setup.sql
-- ============================================================================
-- SCHEMA personal — quién ha trabajado en cada obra y cuántas horas (F-057)
--
-- Módulo independiente. Lee de `raw.*` y de UNA cosa fuera de `raw`:
-- `stg.obras`, para marcar qué líneas caen dentro del universo del seguimiento.
-- Eso, y solo eso, es lo que fija `depends_on = ["build_stg"]` en el step.
--
-- POR QUÉ UN ESQUEMA MÓDULO PROPIO Y NO `stg` (decisión del humano, 2026-09-18)
-- ---------------------------------------------------------------------------
-- 1. NO BLOQUEA. `build_stg` es la puerta de F-024: un fallo del SQL de
--    personal dentro de `build_stg` dejaría al `mart` sin construir esa noche.
--    Un esquema módulo falla solo, la noche continúa y `R-FRESCURA` avisa al
--    consumidor de que ese esquema viene de una noche anterior.
-- 2. LOS PERMISOS SE DAN POR ESQUEMA, y ese fue el argumento decisivo. Aquí
--    dentro hay nombre, NIF y DNI. Con los datos de personal en su esquema,
--    dar o quitar el acceso a un rol es un GRANT; mezclados en `stg` habría
--    que trocear permisos tabla a tabla. POWER BI SÍ VE ESTE ESQUEMA: lo
--    decidió el humano el 2026-09-22, corrigiendo la idea inicial de F-057
--    («Power BI sí, datos de personal no»). El rol propio de F-087 lo incluye.
--
-- LA TRAMPA QUE HACE FALSA UNA SUMA, y va aquí arriba porque es lo primero que
-- hay que saber de este esquema: `hmores.can` **no son horas**. Mezcla HORA,
-- DIA, MES y UD, y el clasificador es `auxhor.medide` —NO `auxhor.ext`, que
-- está a cero en las 60 filas del catálogo y por tanto no clasifica nada—.
-- `SUM(can)` en bruto da 1.837.201,23 sumando horas de albañil con meses de
-- jefe de obra, días de vacaciones y kilómetros. Ver `02_partes_lineas.sql`.
--
-- Todo lo numérico de estos ficheros está MEDIDO contra Sigrid vivo el
-- 2026-09-18 por `sigrid-api` en solo lectura. Nada se supone.
--
-- Idempotente: `CREATE ... IF NOT EXISTS` aquí, `TRUNCATE` + `INSERT` en 01 a
-- 04, `DROP VIEW IF EXISTS` + `CREATE VIEW` en 05. **Aquí no se dropea ninguna
-- tabla**: un DROP se llevaría por delante los GRANT y dejaría al consumidor
-- sin la tabla hasta el siguiente `apply_grants`. Por eso las columnas que se
-- añaden a una tabla que ya existe van con `ALTER TABLE ... ADD COLUMN IF NOT
-- EXISTS` (F-101): `CREATE TABLE IF NOT EXISTS` no toca una tabla ya creada.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS personal;

-- Función local para no depender del schema `stg` al tipar una fecha, igual
-- que `compras.fn_sigrid_date`, `retenciones.fn_sigrid_date` y
-- `maestro.fn_fecha`. La copia es deliberada: es lo que permite construir este
-- esquema aunque `stg` no exista todavía.
CREATE OR REPLACE FUNCTION personal.fn_fecha(d BIGINT)
RETURNS DATE
LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
    IF d IS NULL OR d = 0 THEN
        RETURN NULL;
    END IF;
    RETURN to_date(d::TEXT, 'YYYYMMDD');
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END $$;

COMMENT ON FUNCTION personal.fn_fecha(BIGINT) IS
'Convierte una fecha entera de Sigrid (YYYYMMDD) a DATE. NULL para 0, NULL o invalida. Local al schema personal, como las de compras, retenciones y maestro.';

-- F-101. La otra forma de fecha de Sigrid: la FECHA SERIE (dias desde una
-- epoca, con la hora en la parte decimal), que es como viene `con.tiemod`.
-- LA EPOCA ESTA VERIFICADA, NO SUPUESTA, por dos vias (2026-09-22/23, solo
-- lectura): `MAX(con.tiemod)` global = 46287,88 -> 2026-09-22, el dia de la
-- medicion; y el parte mas antiguo, 39784,75 -> 2008-11-21, con
-- `con.fec = 20081130`. Local al esquema por lo mismo que `fn_fecha`.
CREATE OR REPLACE FUNCTION personal.fn_fecha_serie(d DOUBLE PRECISION)
RETURNS DATE
LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
    IF d IS NULL OR d <= 0 THEN
        RETURN NULL;
    END IF;
    RETURN DATE '1899-12-30' + FLOOR(d)::INT;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END $$;

COMMENT ON FUNCTION personal.fn_fecha_serie(DOUBLE PRECISION) IS
'Convierte una fecha serie de Sigrid (dias desde 1899-12-30, hora en la parte decimal) a DATE, descartando la hora. NULL para 0, NULL, negativa o invalida. Epoca verificada: 46287,88 -> 2026-09-22. Local al schema personal.';


-- ---------------------------------------------------------------------------
-- personal.recursos — el MAESTRO, y su grano es el RECURSO, no el empleado
--
-- Una fila por fila de `raw.res` (2.618 el 2026-09-18). **`res` NO es el
-- maestro de personal**: solo el 51,7 % de sus filas son personas (1.354),
-- 1.158 son consumos imputables (móvil, gasoil, kilómetros) y 106 son medios
-- (vehículos, casetas, grúas). Tratarla como plantilla cuenta como personas
-- cosas que no lo son.
--
-- CONTIENE DATOS PERSONALES: nombre, NIF y DNI. Autorizado expresamente por el
-- humano el 2026-09-18 («el dni puede salir, no es un problema»). No sube el
-- resto de la ficha de `emp` —Seguridad Social, banco, domicilio, nacimiento,
-- sexo, estado civil, contacto, credenciales—, y lo vigila una LISTA BLANCA
-- (`test_f057_r8_*`): de `raw.emp` se leen exactamente cinco columnas.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS personal.recursos (
    recurso_id       BIGINT       PRIMARY KEY,
    codigo_recurso   VARCHAR(24),
    nombre_recurso   VARCHAR(255),
    clase            VARCHAR(8),
    tipo_recurso_id  BIGINT,
    tipo_recurso     VARCHAR(64),
    activo           BOOLEAN      NOT NULL DEFAULT TRUE,
    fecha_baja       DATE,
    nif              VARCHAR(24),
    empleado_id      BIGINT,
    dni              VARCHAR(24),
    nombre_pila      VARCHAR(64),
    apellido1        VARCHAR(64),
    apellido2        VARCHAR(64),
    es_externo       BOOLEAN      NOT NULL DEFAULT FALSE,
    proveedor_id     BIGINT,
    _built_at        TIMESTAMP    NOT NULL DEFAULT NOW(),
    empresa_id       INTEGER,
    nombre_empresa   VARCHAR(255),
    clave_recurso    VARCHAR(40),
    centro_coste_contrapartida_id      BIGINT,
    cuenta_analitica_contrapartida_id  BIGINT
);

-- F-102: el recurso es de UNA empresa. En Sigrid el mismo codigo de recurso
-- existe una vez por empresa (61 codigos repetidos, ninguno dentro de una
-- empresa, el 2026-09-23), asi que se publican la empresa (`con.emp`), su
-- nombre (`raw.auxemp`) y la clave legible `clave_recurso` = '<empresa>-<codigo>'
-- (2.618 claves para 2.618 recursos). `CREATE TABLE IF NOT EXISTS` no anade
-- columnas a la tabla que la nocturna ya creo, asi que van tambien aqui, AL
-- FINAL (en una base nueva nacen en el mismo sitio, detras de `_built_at`).
-- Nunca DROP: se llevaria por delante los GRANT.
ALTER TABLE personal.recursos ADD COLUMN IF NOT EXISTS empresa_id INTEGER;
ALTER TABLE personal.recursos ADD COLUMN IF NOT EXISTS nombre_empresa VARCHAR(255);
ALTER TABLE personal.recursos ADD COLUMN IF NOT EXISTS clave_recurso VARCHAR(40);

-- F-107: la CONTRAPARTIDA de la ficha del recurso --el centro de coste y la
-- cuenta analitica contra los que se abona lo que el parte carga a la obra--.
-- Es del RECURSO (`res.cenconide`, `res.caaconide`), no del tipo de hora:
-- `reshor` no tiene contrapartida. Mismo patron que F-102: al final, con
-- `ADD COLUMN IF NOT EXISTS`, nunca DROP.
ALTER TABLE personal.recursos ADD COLUMN IF NOT EXISTS centro_coste_contrapartida_id BIGINT;
ALTER TABLE personal.recursos ADD COLUMN IF NOT EXISTS cuenta_analitica_contrapartida_id BIGINT;

-- Los dos cortes que se piden de verdad: «las personas de alta» y «el recurso
-- de este empleado».
CREATE INDEX IF NOT EXISTS idx_personal_recursos_clase
    ON personal.recursos (clase, activo);
CREATE INDEX IF NOT EXISTS idx_personal_recursos_empleado
    ON personal.recursos (empleado_id);


-- ---------------------------------------------------------------------------
-- personal.partes_lineas — EL HECHO
--
-- Una fila por fila de `raw.hmores` (330.638 el 2026-09-18). Las horas no
-- están en `hmo`, que son 6.850 cabeceras de parte: están en la LÍNEA, que es
-- además la que trae la obra y la partida.
--
-- No se filtra nada: ni el universo de obra (`R-UNIVERSO-OBRA`), ni las líneas
-- de recursos de baja, ni los importes negativos. Todo eso se publica con su
-- marca y su signo, y quien consulte decide. Filtrar aquí es irreversible;
-- marcar, no.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS personal.partes_lineas (
    linea_id        BIGINT        PRIMARY KEY,
    parte_id        BIGINT,
    codigo_parte    VARCHAR(24),
    recurso_id      BIGINT,
    obra_id         BIGINT,
    en_seguimiento  BOOLEAN       NOT NULL DEFAULT FALSE,
    partida_id      BIGINT,
    fecha           DATE,
    anio            INTEGER,
    mes             INTEGER,
    tipo_hora_id    BIGINT,
    tipo_hora       VARCHAR(64),
    unidad          VARCHAR(12),
    cantidad        NUMERIC(18,2),
    precio          NUMERIC(18,4),
    importe         NUMERIC(18,2),
    texto_linea     TEXT,
    _built_at       TIMESTAMP     NOT NULL DEFAULT NOW()
);

-- F-101: el codigo del parte en cada linea. `CREATE TABLE IF NOT EXISTS` no
-- anade columnas a la tabla que la nocturna ya creo, asi que va tambien aqui.
ALTER TABLE personal.partes_lineas ADD COLUMN IF NOT EXISTS codigo_parte VARCHAR(24);
-- F-101 (D-3): el texto libre de la linea. Puede llevar nombres de persona.
ALTER TABLE personal.partes_lineas ADD COLUMN IF NOT EXISTS texto_linea TEXT;

-- `(unidad)` no es decorativo: es el índice del filtro que evita la cifra
-- falsa, y el que sirve la vista de consumo.
CREATE INDEX IF NOT EXISTS idx_personal_partes_obra_mes
    ON personal.partes_lineas (obra_id, anio, mes);
CREATE INDEX IF NOT EXISTS idx_personal_partes_recurso
    ON personal.partes_lineas (recurso_id);
CREATE INDEX IF NOT EXISTS idx_personal_partes_partida
    ON personal.partes_lineas (partida_id);
CREATE INDEX IF NOT EXISTS idx_personal_partes_unidad
    ON personal.partes_lineas (unidad);


-- ---------------------------------------------------------------------------
-- personal.partes — LA CABECERA del parte de trabajo (F-101)
--
-- Una fila por parte: `raw.hmo` = `raw.con` con `tip = 35`, 6.886 el
-- 2026-09-23. **El grano es `parte_id`, no el codigo**: `con.cod` se repite en
-- 569 valores que afectan a 1.197 partes, asi que el indice del codigo NO es
-- unico.
--
-- La obra y el centro de coste llevan el sufijo `_cabecera_` A PROPOSITO (D-1,
-- patron F-093): la obra que IMPUTA coste es la de la LINEA
-- (`partes_lineas.obra_id`); la de cabecera sirve para AUDITAR, y en 615
-- lineas de 14 partes no coinciden. Un `obra_id` aqui seria la forma de que
-- alguien las confunda.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS personal.partes (
    parte_id                  BIGINT        PRIMARY KEY,
    codigo_parte              VARCHAR(24),
    descripcion               VARCHAR(128),
    fecha                     DATE,
    anio                      INTEGER,
    mes                       INTEGER,
    obra_cabecera_id          BIGINT,
    centro_coste_cabecera_id  BIGINT,
    estado_id                 INTEGER,
    estado                    VARCHAR(128),
    activo                    BOOLEAN       NOT NULL DEFAULT TRUE,
    fecha_baja                DATE,
    fecha_modificacion        DATE,
    num_lineas                INTEGER       NOT NULL DEFAULT 0,
    lineas_en_otra_obra       INTEGER       NOT NULL DEFAULT 0,
    _built_at                 TIMESTAMP     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_personal_cabecera_obra_mes
    ON personal.partes (obra_cabecera_id, anio, mes);
-- NO es UNIQUE: 569 codigos repetidos.
CREATE INDEX IF NOT EXISTS idx_personal_cabecera_codigo
    ON personal.partes (codigo_parte);
CREATE INDEX IF NOT EXISTS idx_personal_cabecera_estado
    ON personal.partes (estado_id);


-- ---------------------------------------------------------------------------
-- personal.recursos_tipos_hora — los PRECIOS DE LA FICHA del recurso (F-101)
--
-- Una fila por fila de `raw.reshor` (8.968 el 2026-09-23, 2.064 recursos, 58
-- tipos de hora). La clave es `reshor_id` y NO el par (recurso, tipo de hora):
-- hay 17 pares repetidos, uno de ellos con dos precios distintos (D-4).
--
-- `reshor` no tiene ninguna fecha ni `tiemod`: son los precios de HOY, sin
-- vigencia (D-5). Y de sus columnas de precio solo entran el de coste y el de
-- venta: el precio de nomina queda fuera por decision del humano del
-- 2026-09-22, y las dos columnas que valen 0 en todas las filas tampoco suben.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS personal.recursos_tipos_hora (
    reshor_id            BIGINT         PRIMARY KEY,
    recurso_id           BIGINT,
    tipo_hora_id         BIGINT,
    codigo_tipo_hora     VARCHAR(16),
    tipo_hora            VARCHAR(64),
    unidad               VARCHAR(12),
    precio_coste         NUMERIC(18,4),
    precio_venta         NUMERIC(18,4),
    cantidad_defecto     NUMERIC(18,4),
    cuenta_analitica_id  BIGINT,
    es_por_defecto       BOOLEAN        NOT NULL DEFAULT FALSE,
    orden                INTEGER,
    tipo_hora_de_baja    BOOLEAN,
    _built_at            TIMESTAMP      NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_personal_tipos_hora_recurso
    ON personal.recursos_tipos_hora (recurso_id);
CREATE INDEX IF NOT EXISTS idx_personal_tipos_hora_tipo
    ON personal.recursos_tipos_hora (tipo_hora_id);
