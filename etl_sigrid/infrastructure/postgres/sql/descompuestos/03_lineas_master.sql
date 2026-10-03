-- etl_sigrid/infrastructure/postgres/sql/descompuestos/03_lineas_master.sql
-- ============================================================================
-- F-097 · SCHEMA descompuestos (4/7): las lineas y el cuadre del MASTER
-- (ambito 8), POR LOTE DE VERSIONES y en una sola transaccion por lote.
--
-- Lee: descompuestos._des_texto, descompuestos._versiones_cargadas,
--      descompuestos.lineas, raw.obrfasamb, raw.conext, raw.dncpro,
--      raw.obrparpre, raw.obrparpar.
--
-- NO SE EJECUTA TAL CUAL. `build_descompuestos_step.py` sustituye tres
-- marcadores antes de enviarlo (patron de F-019), cada uno UNA vez:
--
--   LOTE        -> `(v.obra_id, v.fase_num) IN ((obra, fase), ...)` con las
--                  versiones de este lote (enteros validados), o `FALSE` si no
--                  hay ninguna: el fichero corre IGUAL una vez por noche,
--                  porque los flags y el borrado de abajo no pueden esperar.
--   SELLO       -> el sello del SQL de troceado ('hex', R11).
--   COD_VIGENTE -> el cod de `conext` de la version vigente (solo digitos, de
--                  `business_rules.yaml`).
--
-- QUE HACE, EN ORDEN:
--   1. `_lote`: las versiones cargadas de este lote.
--   2. `_atributos`: el ORIGEN y los flags de TODAS las versiones cargadas
--      (R17). MASTER_ESTUDIO la version 0 (F-123: el master 0 es Estudios,
--      con la medicion de Estudios); MASTER_PLANIF_JO desde la primera
--      version cuyo `obrfasamb.tex` contiene «ABC» (la regla de mart); el resto,
--      MASTER_PRE_ABC (D13). `tipo_version` es la regla de `mart/02_build_fact.sql`
--      copiada literal. El texto de la version sale de `obrfasamb` SIN
--      DUPLICAR: Sigrid guarda a veces una version dos veces
--      (docs/referencia/05_caso_obrfasamb_version_duplicada.md) y se toma la
--      ultima. La vigente es MAX(`conext.valn`) del cod configurado; la ultima,
--      la mayor fase del master de la obra.
--   3. Borra las lineas y el cuadre del lote, y los reinserta: lineas por
--      `descompuestos.fn_trocear`, con el producto por el enlace a `dncpro` y
--      el factor del campo 14 (F-120: del propio texto de la version, NUNCA de
--      `dncpro`, que es el estado actual y no la foto de la version);
--      cuadre de cada partida hoja con precio de la version (R23).
--   4. Borra las lineas y el cuadre de las versiones que ya no estan cargadas
--      (la ingesta las borro porque Sigrid ya no las tiene).
--   5. Los flags cambian sin que cambie el texto (la vigente se mueve, entra
--      una ABC): se actualizan SOLO las versiones cuya huella de atributos no
--      es la que llevan sus lineas (`atributos_troceado`). Es el UPDATE barato
--      del diseno: sin esto habria que recorrer ~4,5 M lineas cada noche.
--   6. Sella las versiones del lote: sello, fecha y huella de atributos.
-- ============================================================================

-- 1. El lote ------------------------------------------------------------------
CREATE TEMP TABLE _lote ON COMMIT DROP AS
SELECT v.obra_id, v.fase_num
FROM descompuestos._versiones_cargadas v
WHERE /*F097_LOTE*/;

-- 2. Origen y flags de cada version cargada -----------------------------------
CREATE TEMP TABLE _atributos ON COMMIT DROP AS
WITH fasamb AS (
    SELECT DISTINCT ON (obride, fas)
        obride AS obra_id,
        fas AS fase_num,
        NULLIF(TRIM(tex), '') AS texto_version
    FROM raw.obrfasamb
    WHERE amb = 8
    ORDER BY obride, fas, ide DESC
),
abc AS (
    SELECT obride AS obra_id, MIN(fas) AS fase_abc
    FROM raw.obrfasamb
    WHERE amb = 8 AND UPPER(tex) LIKE '%ABC%'
    GROUP BY obride
),
vig AS (
    SELECT conide AS obra_id, MAX(valn) AS fase_vigente
    FROM raw.conext
    WHERE cod = /*F097_COD_VIGENTE*/ AND valn IS NOT NULL AND conide IS NOT NULL
    GROUP BY conide
),
ult AS (
    SELECT x.obra_id, MAX(x.fase_num) AS fase_ultima
    FROM (
        SELECT obride AS obra_id, fas AS fase_num FROM raw.obrfasamb WHERE amb = 8
        UNION ALL
        SELECT obra_id, fase_num FROM descompuestos._versiones_cargadas
    ) x
    GROUP BY x.obra_id
),
atributos AS (
    SELECT
        v.obra_id,
        v.fase_num,
        CASE WHEN v.fase_num = 0 THEN 'MASTER_ESTUDIO'
             WHEN abc.fase_abc IS NOT NULL AND v.fase_num >= abc.fase_abc THEN 'MASTER_PLANIF_JO'
             ELSE 'MASTER_PRE_ABC' END AS origen,
        (v.fase_num = 0) AS es_version_inicial,
        COALESCE(v.fase_num = abc.fase_abc, FALSE) AS es_primera_abc,
        COALESCE(v.fase_num = vig.fase_vigente, FALSE) AS es_vigente,
        COALESCE(v.fase_num = ult.fase_ultima, FALSE) AS es_ultima,
        -- La regla de `mart/02_build_fact.sql` (versiones_tipadas), literal.
        CASE
            WHEN fa.texto_version IS NULL OR length(trim(fa.texto_version)) = 0
                THEN 'Sin clasificar'
            WHEN UPPER(fa.texto_version) LIKE '%ABC%'
                THEN 'ABC'
            WHEN UPPER(fa.texto_version) LIKE '%INICIAL%'
             AND UPPER(fa.texto_version) LIKE '%VALORADA%'
                THEN 'Planif Inicial'
            WHEN UPPER(fa.texto_version) LIKE '%CUATRIM%'
              OR UPPER(fa.texto_version) LIKE '%VALORADA%'
                THEN 'Cuatrimestral'
            WHEN UPPER(fa.texto_version) LIKE '%CIERRE%'
                THEN 'Cierre mensual'
            ELSE 'Sin clasificar'
        END AS tipo_version,
        fa.texto_version AS texto_version
    FROM descompuestos._versiones_cargadas v
    LEFT JOIN fasamb fa ON fa.obra_id = v.obra_id AND fa.fase_num = v.fase_num
    LEFT JOIN abc ON abc.obra_id = v.obra_id
    LEFT JOIN vig ON vig.obra_id = v.obra_id
    LEFT JOIN ult ON ult.obra_id = v.obra_id
)
SELECT
    a.*,
    md5(concat_ws('|', a.origen, a.es_version_inicial, a.es_primera_abc, a.es_vigente,
                  a.es_ultima, a.tipo_version, COALESCE(a.texto_version, ''))) AS huella_atributos
FROM atributos a;

-- 3. Las lineas y el cuadre del lote ------------------------------------------
DELETE FROM descompuestos.lineas l
USING _lote t
WHERE l.ambito_id = 8
  AND l.obra_id = t.obra_id
  AND l.fase_num = t.fase_num
  AND l.origen IN ('MASTER_ESTUDIO', 'MASTER_PRE_ABC', 'MASTER_PLANIF_JO');

DELETE FROM descompuestos.cuadre_partida q
USING _lote t
WHERE q.ambito_id = 8
  AND q.obra_id = t.obra_id
  AND q.fase_num = t.fase_num;

INSERT INTO descompuestos.lineas (
    origen, obra_id, partida_id, presupuesto_id, ambito_id, fase_num, orden,
    codigo_elemento, descripcion, unidad, codigo_alternativo,
    tipo_elemento_codigo, tipo_elemento, naturaleza_codigo, naturaleza,
    rendimiento, precio, importe_unitario, cantidad_total, importe_total,
    es_porcentaje, porcentaje, base_porcentaje, dncpro_id, producto_id,
    proveedor_recomendado_id, contrato_id, contrato_linea_id, fecha_maxima,
    grupo_planificacion_id, nivel, es_nivel_padre, es_version_inicial,
    es_primera_abc, es_vigente, es_ultima, tipo_version, texto_version, factor
)
SELECT a.origen, d.obra_id, d.partida_id, d.presupuesto_id, d.ambito_id, d.fase_num, t.orden,
       t.codigo_elemento, t.descripcion, t.unidad, t.codigo_alternativo,
       t.tipo_elemento_codigo, t.tipo_elemento, t.naturaleza_codigo, t.naturaleza,
       t.rendimiento, t.precio, t.importe_unitario, t.cantidad_total, t.importe_total,
       t.es_porcentaje, t.porcentaje, t.base_porcentaje,
       t.dncpro_id, NULLIF(dp.proide, 0),
       NULL::BIGINT, NULL::BIGINT, NULL::BIGINT, NULL::DATE,
       NULL::BIGINT, NULL::INTEGER, NULL::BOOLEAN,
       a.es_version_inicial, a.es_primera_abc, a.es_vigente, a.es_ultima,
       a.tipo_version, a.texto_version, t.factor
FROM descompuestos._des_texto d
JOIN _lote l ON l.obra_id = d.obra_id AND l.fase_num = d.fase_num
JOIN _atributos a ON a.obra_id = d.obra_id AND a.fase_num = d.fase_num
CROSS JOIN LATERAL descompuestos.fn_trocear(d.des) t
LEFT JOIN raw.dncpro dp ON dp.ide = t.dncpro_id
WHERE d.ambito_id = 8;

-- El cuadre de cada partida HOJA con precio de las versiones del lote. Las
-- filas con `obride = 0` quedan fuera (no son de ninguna obra).
INSERT INTO descompuestos.cuadre_partida (
    origen, obra_id, partida_id, ambito_id, fase_num, presupuesto_id,
    precio_partida, suma_descompuesto, diferencia, num_lineas, estado
)
WITH h AS (
    SELECT
        pp.ide AS presupuesto_id,
        pp.obride AS obra_id,
        pp.paride AS partida_id,
        pp.fas AS fase_num,
        ROUND(pp.pre::NUMERIC, 2) AS precio_partida
    FROM raw.obrparpre pp
    JOIN _lote l ON l.obra_id = pp.obride AND l.fase_num = pp.fas
    WHERE pp.amb = 8
      AND COALESCE(pp.pre, 0) <> 0 AND pp.obride <> 0
      AND NOT EXISTS (SELECT 1 FROM raw.obrparpar x WHERE x.padide = pp.paride)
),
s AS (
    SELECT li.obra_id, li.partida_id, li.fase_num,
           COUNT(*) AS num_lineas, SUM(li.importe_unitario) AS suma
    FROM descompuestos.lineas li
    JOIN _lote l ON l.obra_id = li.obra_id AND l.fase_num = li.fase_num
    WHERE li.ambito_id = 8
    GROUP BY li.obra_id, li.partida_id, li.fase_num
)
SELECT a.origen, h.obra_id, h.partida_id, 8, h.fase_num, h.presupuesto_id,
       h.precio_partida,
       COALESCE(s.suma, 0),
       h.precio_partida - COALESCE(s.suma, 0),
       COALESCE(s.num_lineas, 0),
       CASE
           WHEN COALESCE(s.num_lineas, 0) = 0 THEN 'SIN_DESCOMPUESTO'
           WHEN ABS(h.precio_partida - COALESCE(s.suma, 0)) <= 0.01 THEN 'CUADRA'
           ELSE 'NO_CUADRA'
       END
FROM h
JOIN _atributos a ON a.obra_id = h.obra_id AND a.fase_num = h.fase_num
LEFT JOIN s ON s.obra_id = h.obra_id AND s.partida_id = h.partida_id AND s.fase_num = h.fase_num;

-- 4. Lo de las versiones que ya no estan cargadas -----------------------------
DELETE FROM descompuestos.lineas l
USING (
    SELECT DISTINCT obra_id, fase_num FROM descompuestos.lineas WHERE ambito_id = 8
    EXCEPT
    SELECT obra_id, fase_num FROM descompuestos._versiones_cargadas
) h
WHERE l.ambito_id = 8 AND l.obra_id = h.obra_id AND l.fase_num = h.fase_num;

DELETE FROM descompuestos.cuadre_partida q
USING (
    SELECT DISTINCT obra_id, fase_num FROM descompuestos.cuadre_partida WHERE ambito_id = 8
    EXCEPT
    SELECT obra_id, fase_num FROM descompuestos._versiones_cargadas
) h
WHERE q.ambito_id = 8 AND q.obra_id = h.obra_id AND q.fase_num = h.fase_num;

-- 5. Los flags que cambiaron sin que cambiara el texto -------------------------
CREATE TEMP TABLE _cambiadas ON COMMIT DROP AS
SELECT a.*
FROM _atributos a
JOIN descompuestos._versiones_cargadas v ON v.obra_id = a.obra_id AND v.fase_num = a.fase_num
WHERE v.troceada_at IS NOT NULL
  AND v.atributos_troceado IS DISTINCT FROM a.huella_atributos
  AND NOT EXISTS (SELECT 1 FROM _lote l WHERE l.obra_id = a.obra_id AND l.fase_num = a.fase_num);

UPDATE descompuestos.lineas l SET origen = c.origen,
    es_version_inicial = c.es_version_inicial,
    es_primera_abc = c.es_primera_abc,
    es_vigente = c.es_vigente,
    es_ultima = c.es_ultima,
    tipo_version = c.tipo_version,
    texto_version = c.texto_version
FROM _cambiadas c
WHERE l.ambito_id = 8 AND l.obra_id = c.obra_id AND l.fase_num = c.fase_num;

UPDATE descompuestos.cuadre_partida q SET origen = c.origen
FROM _cambiadas c
WHERE q.ambito_id = 8 AND q.obra_id = c.obra_id AND q.fase_num = c.fase_num;

UPDATE descompuestos._versiones_cargadas v SET atributos_troceado = c.huella_atributos
FROM _cambiadas c
WHERE v.obra_id = c.obra_id AND v.fase_num = c.fase_num;

-- 6. El sello de las versiones del lote (R11) ---------------------------------
UPDATE descompuestos._versiones_cargadas v
SET sello_troceado = /*F097_SELLO*/,
    troceada_at = (now() AT TIME ZONE 'UTC'),
    atributos_troceado = a.huella_atributos
FROM _atributos a
WHERE a.obra_id = v.obra_id
  AND a.fase_num = v.fase_num
  AND EXISTS (SELECT 1 FROM _lote l WHERE l.obra_id = v.obra_id AND l.fase_num = v.fase_num);
