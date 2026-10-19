-- etl_sigrid/infrastructure/postgres/sql/compras/00_setup.sql
-- ============================================================================
-- SCHEMA compras — Tanda C1/C2
-- Módulo independiente: solo lee de raw.*. No toca stg/mart/cierre.
-- Todo importe es SIN IVA (dcapro.tot / dcfpro.tot / ctrpro.tot); la cuota
-- IVA se conserva como columna informativa donde aplica.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS compras;
-- F-138 (D9): las alarmas COMPLETAS de los documentos, con las de recursos y
-- partes de trabajo (nombran trabajadores y bajas). Lo crea el dueño de los
-- objetos (`sigrid_dm_etl`, por PG_SET_ROLE) y nace sin ninguna concesión al
-- rol estándar: `apply_grants` se la revoca cada noche y la concede al
-- autorizado. En Azure lo crea antes `infra/sql/02_roles.sql`; esto es la red
-- para una base local o recién provisionada (patrón de `tesoreria/00_setup.sql`).
CREATE SCHEMA IF NOT EXISTS compras_restringida;

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

-- ---------------------------------------------------------------------------
-- F-128 (2026-10-18) · LA CLASE DE LOS RECARGOS Y RETENCIONES DEL DOCUMENTO.
--
-- `dcfrec.reccla` / `dcarec.reccla` (= `rec.cla` del concepto) dice qué es
-- cada recargo de la cabecera. Medido el 2026-10-17: 0 recargo (→ `imprec`),
-- 1 descuento (→ `impdes`), 3 retención fiscal (IRPF, arrendamientos,
-- notarías), 4 retención de garantía sobre el TOTAL, 5 sobre la BASE. Con eso
-- `totdoc − totpag` = Σ cuota de las clases 3, 4 y 5 en el 100 % de las
-- facturas.
--
-- El `CASE` es `CLASES_RECARGO` de `etl_sigrid/domain/cabecera_compra.py`
-- (lo fija `tests/test_f128_sql.py`). Lo que no está en el mapa es `OTRA`.
--
-- D2-B (humano, 2026-10-17): RETENCIÓN DE GARANTÍA = CLASES 4 Y 5, sin mirar
-- el concepto. El `RETESP` («Retención 5 % garantía (sin IVA)», 44 facturas)
-- es de clase 1 y aquí NO es garantía. Por eso la función tiene UN parámetro.
-- `retenciones.fn_es_retencion_garantia` es COPIA deliberada de esta (R19).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION compras.fn_clase_recargo(reccla INT)
RETURNS TEXT
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE reccla
        WHEN 0 THEN 'RECARGO'
        WHEN 1 THEN 'DESCUENTO'
        WHEN 3 THEN 'RETENCION_FISCAL'
        WHEN 4 THEN 'RETENCION_GARANTIA_TOTAL'
        WHEN 5 THEN 'RETENCION_GARANTIA_BASE'
        ELSE 'OTRA'
    END;
$$;

COMMENT ON FUNCTION compras.fn_clase_recargo(INT) IS
'Clase de un recargo de documento de compra (dcfrec/dcarec.reccla): RECARGO (0), '
'DESCUENTO (1), RETENCION_FISCAL (3), RETENCION_GARANTIA_TOTAL (4), '
'RETENCION_GARANTIA_BASE (5); OTRA para cualquier otro valor o NULL (F-128).';

CREATE OR REPLACE FUNCTION compras.fn_es_retencion_garantia(reccla INT)
RETURNS BOOLEAN
LANGUAGE sql IMMUTABLE AS $$
    SELECT COALESCE(reccla IN (4, 5), FALSE);
$$;

COMMENT ON FUNCTION compras.fn_es_retencion_garantia(INT) IS
'Verdadero SOLO si el recargo es retencion de garantia: clases 4 (sobre total) y 5 '
'(sobre base). Falso para NULL. Decision del 2026-10-17 (D2-B, F-128): el concepto '
'RETESP («Retencion 5 % garantia (sin IVA)», 44 facturas) es de clase 1 (DESCUENTO) y '
'NO cuenta como garantia aunque su asiento vaya a la cuenta de retencion.';
