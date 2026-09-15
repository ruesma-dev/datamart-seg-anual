-- etl_sigrid/infrastructure/postgres/sql/compras/07_texto.sql
-- ============================================================================
-- La pestaña «TEXTO» del documento de compra, en dos tablas (F-080, R22-R26):
--
--   · `compras.documento_texto`        — el memo ÍNTEGRO, tal y como llega
--   · `compras.documento_comentarios`  — un comentario por fila, ya partido
--
-- LA PESTAÑA SE PINTA DESDE `con.tex`, NO DESDE `dcf.tex` (R2, medido): 65,5 %
-- de las facturas tienen memo en la superclase (108.527 de 165.759) y solo el
-- 0,3 % en el campo homónimo de su propia tabla. Es la misma trampa que el
-- resto de esta feature: el dato vive en `con`.
--
-- LAS DOS SON TABLAS, y ninguna es una vista (R22, R23, DA-6). El memo se lee
-- muchas veces y filtrar `raw.con` (2,18 M de filas) en cada consulta es caro;
-- partir ~110.000 memos en cada lectura, peor. Se materializan en la nocturna,
-- cada una con su clave primaria declarada.
--
-- EL SEPARADOR Y EL SELLO NO ESTÁN ESCRITOS AQUÍ (R24, DA-1). Viven UNA SOLA
-- VEZ en `etl_sigrid/domain/texto_comentarios.py`, que es donde se prueban
-- sobre fixtures, y `tests/test_f080_sql.py` comprueba que este fichero usa
-- esos mismos literales. Son regex POSIX a propósito: sin lookarounds, que el
-- motor de Postgres no tiene. Si hay que cambiarlos, se cambian allí.
--
-- NADA DE LO QUE NO CASA SE PIERDE (R25, R26, DA-2). El sello solo AÑADE
-- columnas: el bloque sale entero pase lo que pase —texto escrito a mano, la
-- línea automática de la aplicación, un sello a medias— con la autoría a NULL
-- y `sello_reconocido` en falso. Y se publica el bloque íntegro aparte del
-- cuerpo, que es lo que permite la prueba reconstructiva de R26.
--
-- Lee de: raw.con. Escribe en: compras.documento_texto,
--         compras.documento_comentarios.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- EL MEMO ÍNTEGRO (R22)
-- ---------------------------------------------------------------------------
--
-- `num_comentarios` se rellena más abajo, DESPUÉS de partir los bloques, para
-- que sea exactamente el número de filas que la otra tabla publica de este
-- documento y no una segunda cuenta que pueda divergir de ella. Ese es también
-- el motivo de que el separador no aparezca aquí: se usa una sola vez.
DROP TABLE IF EXISTS compras.documento_texto CASCADE;
CREATE TABLE compras.documento_texto AS
SELECT
    c.ide                                   AS documento_id,
    c.tip                                   AS tipo_documento_codigo,
    compras.fn_tipo_documento(c.tip, compras.fn_serie(c.cod))
                                            AS tipo_documento,
    c.cod                                   AS codigo_documento,
    c.tex                                   AS texto,
    octet_length(c.tex)                     AS bytes,
    0::INT                                  AS num_comentarios
FROM raw.con c
WHERE c.tip IN (15, 44)
  AND c.tex IS NOT NULL
  AND btrim(c.tex, E' \t\r\n') <> '';

ALTER TABLE compras.documento_texto ADD PRIMARY KEY (documento_id);
CREATE INDEX idx_com_doctex_tip ON compras.documento_texto (tipo_documento);

-- ---------------------------------------------------------------------------
-- LOS COMENTARIOS, UNO POR FILA (R23, R25, R26)
-- ---------------------------------------------------------------------------
--
-- `orden` 1 ES EL MÁS RECIENTE: Sigrid concatena en descendente y el corte
-- conserva ese orden, así que no hay nada que ordenar —y por eso no hay ni un
-- `DESC` en este fichero: invertirlo pondría el comentario de alta como si
-- fuera el último estado del documento—.
--
-- Y `orden` SE RENUMERA sobre el orden del corte. `WITH ORDINALITY` numera
-- ANTES de que el `WHERE` tire los trozos vacíos, así que un memo que empieza
-- por un separador dejaría su primer comentario real en el 2 y este documento
-- no tendría ningún `orden` 1. El oráculo (`partir_memo`) numera después de
-- filtrar, y las dos implementaciones tienen que coincidir o compararlas no
-- vale de nada.
DROP TABLE IF EXISTS compras.documento_comentarios CASCADE;
CREATE TABLE compras.documento_comentarios AS
WITH bloques AS (
    SELECT
        t.documento_id,
        b.orden_corte,
        b.bloque
    FROM compras.documento_texto t
    CROSS JOIN LATERAL regexp_split_to_table(
        t.texto, '\r?\n *-{3,} *\r?\n'
    ) WITH ORDINALITY AS b(bloque, orden_corte)
    WHERE btrim(b.bloque, E' \t\r\n') <> ''
),
sellados AS (
    SELECT
        b.documento_id,
        (row_number() OVER (PARTITION BY b.documento_id
                            ORDER BY b.orden_corte))::INT  AS orden,
        b.bloque,
        regexp_match(
            b.bloque,
            '\[([0-9]{2}/[0-9]{2}/[0-9]{4}) +([0-9]{2}:[0-9]{2}:[0-9]{2}) +Usuario: *([^]]*)\]'
        )                                                AS sello
    FROM bloques b
),
fechados AS (
    -- La fecha del sello, pasada por `fn_sigrid_date`, que ya devuelve NULL
    -- ante cualquier sorpresa en vez de tumbar el build de la noche.
    SELECT
        s.documento_id,
        s.orden,
        s.bloque,
        s.sello,
        compras.fn_sigrid_date(
            (right(s.sello[1], 4) || substr(s.sello[1], 4, 2)
             || left(s.sello[1], 2))::BIGINT
        )                                                AS fecha_sello
    FROM sellados s
),
validados AS (
    -- LA COMPROBACIÓN DE IDA Y VUELTA. `31/02/2026` casa con el patrón y no es
    -- una fecha: `to_date` la normalizaría a marzo y publicaríamos un día que
    -- nadie escribió. Si la fecha no vuelve idéntica, el sello NO cuenta como
    -- reconocido, igual que hace el `strptime` del oráculo.
    SELECT
        f.documento_id,
        f.orden,
        f.bloque,
        f.sello,
        f.fecha_sello,
        (f.fecha_sello IS NOT NULL
         AND to_char(f.fecha_sello, 'DD/MM/YYYY') = f.sello[1])
                                                         AS sello_ok
    FROM fechados f
),
publicados AS (
    -- Las ramas del sello se resuelven AQUÍ y no en la proyección final, y no
    -- es cosmética: el guardián de F-006 (`test_f006_r26_..._se_dejan_leer`)
    -- lee la proyección del último `SELECT` contando paréntesis, y los
    -- corchetes de una expresión regular dentro de ella la vuelven ilegible.
    -- Un objeto cuya proyección no se deja leer deja de estar vigilado, así
    -- que el `SELECT` final se queda en una lista de columnas desnudas.
    SELECT
        v.documento_id                       AS documento_id,
        v.orden                              AS orden,
        v.sello_ok                           AS sello_reconocido,
        CASE WHEN v.sello_ok THEN v.fecha_sello END
                                             AS fecha,
        CASE WHEN v.sello_ok THEN v.sello[2] END
                                             AS hora,
        CASE WHEN v.sello_ok THEN v.sello[3] END
                                             AS usuario,
        -- Con sello, el cuerpo es el bloque sin él; sin sello, el bloque
        -- ENTERO (R25). El sello no recorta: se va del cuerpo pero sigue
        -- estando en `bloque`.
        CASE WHEN v.sello_ok
             THEN btrim(
                      regexp_replace(
                          v.bloque,
                          '\[([0-9]{2}/[0-9]{2}/[0-9]{4}) +([0-9]{2}:[0-9]{2}:[0-9]{2}) +Usuario: *([^]]*)\]',
                          ''
                      ),
                      E' \t\r\n'
                  )
             ELSE v.bloque END               AS cuerpo,
        v.bloque                             AS bloque,
        octet_length(v.bloque)               AS bytes
    FROM validados v
)
SELECT
    p.documento_id                          AS documento_id,
    p.orden                                 AS orden,
    p.sello_reconocido                      AS sello_reconocido,
    p.fecha                                 AS fecha,
    p.hora                                  AS hora,
    p.usuario                               AS usuario,
    p.cuerpo                                AS cuerpo,
    p.bloque                                AS bloque,
    p.bytes                                 AS bytes
FROM publicados p;

ALTER TABLE compras.documento_comentarios
    ADD PRIMARY KEY (documento_id, orden);
CREATE INDEX idx_com_doccom_usr ON compras.documento_comentarios (usuario);
CREATE INDEX idx_com_doccom_fec ON compras.documento_comentarios (fecha);

-- Y ahora el recuento, que es el número de filas realmente publicadas.
UPDATE compras.documento_texto t
SET num_comentarios = n.filas
FROM (
    SELECT documento_id, COUNT(*)::INT AS filas
    FROM compras.documento_comentarios
    GROUP BY documento_id
) n
WHERE n.documento_id = t.documento_id;

COMMENT ON TABLE compras.documento_texto IS
'El memo de la pestana Texto del documento de compra, INTEGRO y tal y como '
'llega. GRANO: una fila por documento con texto; solo facturas (tip 15) y '
'contratos (tip 44). 108.527 de 165.759 facturas tienen memo (65,5 %) y 1.614 '
'de 18.965 contratos (8,5 %); los documentos sin memo NO salen. '
'El texto sale de con.tex, la superclase, y NO de dcf.tex ni ctr.tex, que '
'estan informados en el 0,3 % y el 3,9 %: quien busque el texto ahi concluira '
'que las facturas no tienen comentarios. '
'texto es texto libre acumulado por personas: sirve para leerlo y buscar en '
'el, no para decidir con el sin leerlo. Partido en comentarios esta en '
'compras.documento_comentarios, y num_comentarios es exactamente cuantas '
'filas tiene alli este documento.';

COMMENT ON TABLE compras.documento_comentarios IS
'El memo partido en comentarios, uno por fila. GRANO: (documento_id, orden), '
'declarado como clave. '
'orden 1 es el comentario MAS RECIENTE, porque Sigrid apila en descendente: '
'el orden mas alto es el mas ANTIGUO, normalmente el alta del documento. '
'Pedir el ultimo comentario es pedir orden = 1. '
'sello_reconocido dice si el bloque cerraba con el sello [dd/mm/aaaa hh:mm:ss '
'Usuario: login]. Cuando es falso -texto escrito a mano, la linea automatica '
'que anade la aplicacion, o un sello incompleto- fecha, hora y usuario van a '
'NULL y el cuerpo es el bloque entero: NADA se descarta por no casar, y el '
'comentario mas interesante suele ser justo el que alguien escribio fuera del '
'formulario. Una fecha imposible dentro del sello tampoco cuenta como '
'reconocida, para no publicar un dia que nadie escribio. '
'cuerpo es el bloque sin el sello; bloque es el trozo INTEGRO, y unir los '
'bloques de un documento por su separador reproduce el memo original sin '
'perder un caracter.';
