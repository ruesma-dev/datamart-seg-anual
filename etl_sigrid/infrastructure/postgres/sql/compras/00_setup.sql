-- etl_sigrid/infrastructure/postgres/sql/compras/00_setup.sql
-- ============================================================================
-- SCHEMA compras — Tanda C1/C2
-- Módulo independiente: solo lee de raw.*. No toca stg/mart/cierre.
-- Todo importe es SIN IVA (dcapro.tot / dcfpro.tot / ctrpro.tot); la cuota
-- IVA se conserva como columna informativa donde aplica.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS compras;

-- Función local para no depender del schema stg (modularidad).
CREATE OR REPLACE FUNCTION compras.fn_sigrid_date(d BIGINT)
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

-- Serie documental = prefijo alfabético del código ('AC26/21188' → 'AC',
-- 'PROF26/00926' → 'PROF', 'FRGG26/1860' → 'FRGG').
CREATE OR REPLACE FUNCTION compras.fn_serie(cod TEXT)
RETURNS TEXT
LANGUAGE sql IMMUTABLE AS $$
    SELECT UPPER(COALESCE(substring(cod FROM '^[A-Za-z]+'), ''));
$$;

-- Traducción del ESTADO de un documento, por la PAREJA (tipo, estado).
--
-- F-084 (2026-09-16). En Sigrid el estado de un documento es un número en
-- `con.est`, y lo que ese número significa DEPENDE DEL TIPO DE DOCUMENTO: el
-- 7 es «Firmado» en un contrato (tip 44) y en el catálogo de la factura
-- (tip 15) es otro estado distinto. Traducir uniendo solo por `est` da un
-- literal equivocado sin romper el build, que es la peor forma de fallar.
--
-- POR QUÉ ES UNA FUNCIÓN Y NO UN LATERAL COPIADO EN CADA BLOQUE (criterio 6
-- de F-084). F-083 escribió esta traducción a mano dentro del bloque
-- FACTURAS. F-084 necesitaba la misma para CONTRATOS, y copiarla habría
-- dejado dos `WHERE` que mantener, dos `LIMIT 1` que recordar y dos sitios
-- donde olvidar el tipo. Factorizada, la ganancia no es de líneas: **el tipo
-- de documento es un argumento obligatorio de la firma**, así que la unión
-- «solo por estado_id» deja de poder escribirse — PostgreSQL falla al
-- construir en vez de publicar el literal de otro documento.
--
-- LA GUARDA DE GRANO VIVE AQUÍ, y por eso protege a los dos que llaman: el
-- `ORDER BY ide LIMIT 1` garantiza como mucho UNA fila aunque el catálogo
-- traiga mañana dos para el mismo par. Hoy `(tip, est)` es único —193 de 193
-- filas, 0 pares repetidos, medido el 2026-09-16— y precisamente por eso un
-- `JOIN` sin guarda parecería inocente.
--
-- Se llama con `LEFT JOIN LATERAL ... ON TRUE`: si el estado no casa con el
-- catálogo no devuelve nada, el documento se publica igual y el literal queda
-- a NULL. Hoy no le pasa a ningún contrato (0 huérfanos de 18.978) ni a
-- ninguna factura (0 de 165.866).
--
-- Local a `compras` a propósito, como `fn_sigrid_date`: este módulo solo lee
-- de `raw.*` y no depende del orden de construcción de `maestro`, que publica
-- el mismo catálogo como dimensión en `maestro.estados_documento` (F-073).
CREATE OR REPLACE FUNCTION compras.fn_estado_documento(p_tip INT, p_est INT)
RETURNS TABLE (codigo_estado TEXT, nombre_estado TEXT)
LANGUAGE sql STABLE AS $$
    SELECT ce.cod::TEXT, ce.res::TEXT
    FROM   raw.conest ce
    WHERE  ce.tip = p_tip AND ce.est = p_est
    ORDER  BY ce.ide
    LIMIT  1;
$$;

-- Tipo de documento de negocio a partir de (con.tip, serie).
CREATE OR REPLACE FUNCTION compras.fn_tipo_documento(tip INT, serie TEXT)
RETURNS TEXT
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN tip = 14 AND serie = 'AC'              THEN 'ALBARAN'
        WHEN tip = 14 AND serie = 'PROF'            THEN 'PROFORMA'
        WHEN tip = 14 AND serie = 'NTC'             THEN 'NOTA'
        WHEN tip = 14                               THEN 'OTRO'
        WHEN tip = 15 AND serie IN ('FR', 'FRGG')   THEN 'FACTURA'
        WHEN tip = 15 AND serie IN ('AB', 'ABGG')   THEN 'ABONO'
        WHEN tip = 15                               THEN 'OTRO'
        WHEN tip = 44                               THEN 'CONTRATO'
        ELSE 'OTRO'
    END;
$$;

-- ---------------------------------------------------------------------------
-- F-038 (2026-10-04) · LA OFERTA FICTICIA DEL COMPARATIVO
--
-- Dentro de un comparativo hay ofertas de proveedores INVENTADOS: el
-- OBJETIVO, la OFICINA TÉCNICA, la PLANIFICACIÓN (cuatrimestral, fase 0, ABC).
-- Contarlas como reales estropea el número de ofertantes, la oferta más
-- barata y el ahorro del concurso. Medido el 2026-10-04: 32.896 ficticias,
-- 1.298,8 M€ sin IVA, el 45 % del ofertado.
--
-- EL CRITERIO (R8-R10): ficticia = CIF falso, o CIF vacío y nombre de
-- familia; con CIF real, nunca. El CIF falso SOLO cubre el 30 %: 172
-- entidades ficticias tienen el CIF vacío. La familia la dice el NOMBRE DE LA
-- OFERTA (`dco.entres`), normalizado, porque los nombres vienen con y sin
-- tilde, con guion o asteriscos («OBJETIVO-RUESMA», «*OBJETIVO*»).
--
-- LOS LITERALES NO SE CAMBIAN AQUÍ (R11). Viven escritos una sola vez en
-- `etl_sigrid/domain/comparativos.py`, probados con los nombres medidos, y
-- `tests/test_f038_sql.py` comprueba que estas dos funciones llevan LOS
-- MISMOS: patrones en su orden, CIF falsos, exclusiones y normalización.
-- Un nombre de ficticia nuevo se añade allí y aquí, en el mismo commit.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION compras.fn_normalizar_nombre(p_texto TEXT)
RETURNS TEXT
LANGUAGE sql IMMUTABLE AS $$
    SELECT btrim(regexp_replace(translate(upper(COALESCE(p_texto, '')), 'ÁÉÍÓÚÜÑ', 'AEIOUUN'), '[^A-Z0-9]+', ' ', 'g'));
$$;

-- La familia ficticia de una oferta, o NULL si la oferta es REAL. El orden de
-- las ramas es el del dominio: CIF real → real; nombre excluido → real;
-- primera familia que case; si ninguna y el CIF es falso, la de su CIF.
CREATE OR REPLACE FUNCTION compras.fn_familia_ficticia(p_cif TEXT, p_nombre TEXT)
RETURNS TEXT
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN x.c <> '' AND x.c NOT IN ('A99999999', 'A00000000') THEN NULL
        WHEN strpos(x.n, 'PLANIFICACION DE ESPACIOS') > 0 THEN NULL
        WHEN x.n ~ '(^| )OBJE' THEN 'OBJETIVO'
        WHEN x.n ~ 'OFICINA TE' THEN 'OFICINA_TECNICA'
        WHEN x.n ~ 'CUATRIM' THEN 'CUATRIMESTRAL'
        WHEN x.n ~ 'FASE ?0( |$)|PLANIFICACION 0$' THEN 'FASE_0'
        WHEN x.n ~ '(^| )ABC( |$)' THEN 'ABC'
        WHEN x.n ~ 'PLANIF' THEN 'PLANIFICACION'
        WHEN x.c = 'A99999999' THEN 'OBJETIVO'
        WHEN x.c = 'A00000000' THEN 'OFICINA_TECNICA'
    END
    FROM (
        SELECT upper(btrim(COALESCE(p_cif, ''))) AS c,
               compras.fn_normalizar_nombre(p_nombre) AS n
    ) x;
$$;

-- F-038 Fase 2 (R27) · El porcentaje de descuento de una línea de oferta.
-- `dcopro.dto` es TEXTO con coma decimal ('10,08%'), con negativos (recargos):
-- tratarlo como número revienta. El patrón es `PATRON_DTO` de
-- `etl_sigrid/domain/comparativos.py` (lo fija un test). Lo que no casa es
-- NULL, nunca un error ni un cero; sin `EXCEPTION` porque el patrón ya
-- garantiza que el cast no falla. El precio de la línea YA es neto: este
-- porcentaje es el que lo produjo, no uno que haya que volver a aplicar.
CREATE OR REPLACE FUNCTION compras.fn_porcentaje_dto(t TEXT)
RETURNS NUMERIC
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN t ~ '^-?[0-9]+(,[0-9]+)?%$' THEN replace(replace(t, '%', ''), ',', '.')::NUMERIC
    END;
$$;

-- ---------------------------------------------------------------------------
-- F-067 (2026-10-06) · LA FECHA SERIE DE SIGRID, CON SU HORA (`con.tiemod`).
--
-- `tiemod` es un número de DELPHI: días desde 1899-12-30 y la hora en la parte
-- decimal (46300,537627 = 2026-10-05 12:54:10). OJO, MEDIDO: SQL Server, con
-- `CAST(... AS datetime)`, usa la época 1900-01-01 y da DOS DÍAS MÁS —el
-- 2026-10-07, imposible el día de la medición—. La época es `EPOCA_DELPHI` de
-- `etl_sigrid/domain/fecha_delphi.py` (lo fija `tests/test_f067_sql.py`).
-- El 0 de Sigrid es NULL. Es la misma época que `personal.fn_fecha_serie`
-- (F-101), que descarta la hora; esta la conserva.
--
-- `con.tiemod` NO ES LA FECHA DEL CAMBIO DE ESTADO (D2 del humano): es la
-- última modificación del documento, y la firma no la mueve. La antigüedad del
-- estado sale de `rac`: `compras.v_estado_documentos` (F-132,
-- `13_estado_documentos.sql`).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION compras.fn_sigrid_tiempo(v DOUBLE PRECISION)
RETURNS TIMESTAMP
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN v > 0 THEN TIMESTAMP '1899-12-30' + v * INTERVAL '1 day' END;
$$;
