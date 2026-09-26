-- etl_sigrid/infrastructure/postgres/sql/personal/03_partes.sql
-- ============================================================================
-- personal.partes — LA CABECERA del parte de trabajo (F-101, hotfix de F-057).
--
-- Una fila por parte: `raw.hmo` unido a `raw.con`, que es el concepto con
-- `tip = 35` (6.886 el 2026-09-23). Todo lo medido aqui lo fue contra Sigrid
-- vivo el 2026-09-22/23 por `sigrid-api` en solo lectura.
--
-- ---------------------------------------------------------------------------
-- DE DONDE SALE CADA COSA (R-SIGRID-CON)
-- ---------------------------------------------------------------------------
-- `hmo` es «propiedades de con»: codigo, descripcion, fecha, estado, baja y
-- ultima modificacion del parte estan en `raw.con`. De `raw.hmo` solo salen la
-- obra y el centro de coste de CABECERA, el año y el mes. Lo demas que trae
-- `hmo` no se publica porque no aporta nada: la fecha de cierre diario, la
-- clase y la cuenta analitica valen 0 en las 6.886 filas, y el recurso de
-- cabecera esta informado en 6.
--
-- **EL CODIGO NO ES CLAVE.** `con.cod` esta en las 6.886 pero solo hay 6.258
-- distintos: 569 codigos repetidos que afectan a 1.197 partes. El grano es
-- `parte_id` y el indice del codigo no es unico.
--
-- LA DESCRIPCION es `con.res` (6.883 de 6.886). El memo del concepto solo lo
-- traen 3 partes, 660 bytes en total: no es la descripcion del parte.
--
-- ---------------------------------------------------------------------------
-- LA OBRA DE CABECERA AUDITA, LA DE LA LINEA IMPUTA (D-1, patron F-093)
-- ---------------------------------------------------------------------------
-- Por eso se llaman `obra_cabecera_id` y `centro_coste_cabecera_id`, y nunca
-- `obra_id`: la obra que imputa coste es la de `personal.partes_lineas`, y en
-- 615 lineas de 14 partes no coincide con la de su cabecera. Este fichero
-- publica la cabecera; el veto de F-057 sobre `02_partes_lineas.sql` (no unir la
-- cabecera en las lineas) sigue en pie.
--
-- `lineas_en_otra_obra` hace contestable «en cuantos partes discrepan» con un
-- WHERE (D-2). Se cuenta contra `raw.hmores` y no contra
-- `personal.partes_lineas`, para no atar este fichero al orden de los
-- anteriores. Y se cuenta AGREGANDO UNA VEZ por `hmoide`, NO con un LATERAL por
-- parte: `raw.hmores` no tiene indice por `hmoide` (solo la clave `ide`), y un
-- LATERAL con COUNT se planifica como un seq scan de las 330.941 lineas por cada
-- uno de los 6.886 partes (coste estimado 119.752.314 frente a 19.681; EXPLAIN
-- sin ANALYZE, en solo lectura, el 2026-09-23).
--
-- ---------------------------------------------------------------------------
-- NO SE FILTRA NI SE CORRIGE NADA
-- ---------------------------------------------------------------------------
-- Los 218 partes de baja se publican con `activo = FALSE`, igual que en
-- `personal.recursos`. El año trae 27 valores fuera de 1990-2030 (entre ellos
-- 201831 y 11226) y el mes 2 fuera de 1-12: se publican y la ficha lo advierte.
-- Corregir en silencio es peor que publicar el defecto.
--
-- LA FECHA DE MODIFICACION es una FECHA SERIE (`personal.fn_fecha_serie`,
-- epoca 1899-12-30 verificada por dos vias en `00_setup.sql`).
--
-- EL USUARIO QUE CREA EL PARTE NO ESTA AQUI, y no por olvido: no existe en
-- `con` ni en `hmo`. Vive en `dbo.log` (8,47 M filas, no ingerida). Es F-105.
-- ============================================================================

TRUNCATE TABLE personal.partes;

INSERT INTO personal.partes (
    parte_id, codigo_parte, descripcion,
    fecha, anio, mes,
    obra_cabecera_id, centro_coste_cabecera_id,
    estado_id, estado,
    activo, fecha_baja, fecha_modificacion,
    num_lineas, lineas_en_otra_obra
)
SELECT
    h.ide                                   AS parte_id,
    c.cod                                   AS codigo_parte,
    -- La cadena vacia es «sin descripcion» (3 partes): se publica NULL.
    NULLIF(c.res, '')                       AS descripcion,
    personal.fn_fecha(c.fec)                AS fecha,
    h.ano                                   AS anio,
    h.mes                                   AS mes,
    -- AUDITA, no imputa: la obra de coste es la de la linea.
    NULLIF(h.obride, 0)                     AS obra_cabecera_id,
    NULLIF(h.cenide, 0)                     AS centro_coste_cabecera_id,
    c.est                                   AS estado_id,
    es.res                                  AS estado,
    -- El mismo vocabulario que `personal.recursos`: BANDERA, no filtro.
    (COALESCE(c.fecbaj, 0) = 0)             AS activo,
    personal.fn_fecha(c.fecbaj)             AS fecha_baja,
    personal.fn_fecha_serie(c.tiemod)       AS fecha_modificacion,
    COALESCE(ln.n, 0)                       AS num_lineas,
    COALESCE(ln.d, 0)                       AS lineas_en_otra_obra
FROM      raw.hmo h
JOIN      raw.con c ON c.ide = h.ide        -- R-SIGRID-CON: 0 huerfanos medidos
LEFT JOIN LATERAL (
    -- El estado se traduce filtrando el TIPO DE DOCUMENTO del parte (35): la
    -- misma cifra significa otra cosa en una obra o en una factura. Hoy son
    -- 1 REG «En registro» (647), 3 CER «Cerrado» (541) y 10 IMP «Imputado»
    -- (5.698). `ORDER BY` + `LIMIT 1` es la guarda de grano, como en
    -- `maestro/01_obras.sql`.
    SELECT ce.res
    FROM   raw.conest ce
    WHERE  ce.tip = 35 AND ce.est = c.est
    ORDER  BY ce.ide
    LIMIT  1
) es ON TRUE
LEFT JOIN (
    -- Lineas por parte y cuantas imputan a una obra distinta de la de su
    -- cabecera. Una sola pasada agregada (ver la cabecera del fichero).
    SELECT l.hmoide,
           COUNT(*) AS n,
           COUNT(*) FILTER (
               WHERE NULLIF(l.obride, 0) IS NOT NULL
                 AND NULLIF(hc.obride, 0) IS NOT NULL
                 AND l.obride <> hc.obride
           ) AS d
    FROM   raw.hmores l
    JOIN   raw.hmo hc ON hc.ide = l.hmoide
    GROUP  BY l.hmoide
) ln ON ln.hmoide = h.ide;

COMMENT ON TABLE personal.partes IS
'Cabecera de los partes de trabajo (6.886 el 2026-09-23), una fila por parte. La clave es parte_id: el codigo_parte se repite (569 codigos, 1.197 partes). obra_cabecera_id AUDITA y no imputa: la obra de coste es la de personal.partes_lineas, y en 615 lineas de 14 partes no coinciden (lineas_en_otra_obra). No se filtra la baja ni se corrigen anio/mes fuera de rango. El usuario que crea el parte no esta: vive en dbo.log, no ingerida (F-105).';
