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
-- Idempotente: `CREATE ... IF NOT EXISTS` aquí, `TRUNCATE` + `INSERT` en 01 y
-- 02, `DROP VIEW IF EXISTS` + `CREATE VIEW` en 03. **Aquí no se dropea ninguna
-- tabla**: un DROP se llevaría por delante los GRANT y dejaría al consumidor
-- sin la tabla hasta el siguiente `apply_grants`.
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
    _built_at        TIMESTAMP    NOT NULL DEFAULT NOW()
);

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
    _built_at       TIMESTAMP     NOT NULL DEFAULT NOW()
);

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
