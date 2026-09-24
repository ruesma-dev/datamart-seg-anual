-- etl_sigrid/infrastructure/postgres/sql/personal/02_partes_lineas.sql
-- ============================================================================
-- personal.partes_lineas — una fila por fila de `raw.hmores` (330.638).
--
-- ---------------------------------------------------------------------------
-- LA UNIDAD, QUE ES LO QUE HACE FALSA UNA SUMA
-- ---------------------------------------------------------------------------
-- `hmores.can` **no son horas**. Su unidad la fija el tipo de hora, y el
-- clasificador es `auxhor.medide` (referencia a `auxmed`). Medido el
-- 2026-09-18 sobre las 330.638 lineas:
--
--   medide 1  HORA     241.004 lineas   1.249.038,44 h    24.837.178,20 EUR  25,3 %
--   medide 2  DIA        9.723 lineas       4.225,46 d         1.809,20 EUR   0,0 %
--   medide 3  MES       36.034 lineas      18.009,38 m    70.458.900,29 EUR  71,7 %
--   medide 19 UD        43.867 lineas     565.927,95 ud    2.977.303,43 EUR   3,0 %
--   (sin catalogo)          10 lineas               0                 0 EUR   0,0 %
--
-- `SUM(can)` en bruto da 1.837.201,23 sumando horas de albañil con meses de
-- jefe de obra, dias de vacaciones y kilometros. Con el corte `medide = 1`
-- salen 1.249.038,44 horas, que es la cifra que esta feature existe para
-- publicar. **El 71,7 % del euro esta en las lineas de MES**, no en las de
-- hora: ahi vive el coste de estructura de obra (MES JEFE DE OBRA solo,
-- 18,80 M EUR).
--
-- EL CLASIFICADOR NO ES `auxhor.ext`. Se llama «Extra» y **esta a cero en las
-- 60 filas del catalogo**, asi que quien lo mire concluira que el catalogo no
-- distingue unidades. Ese identificador esta VETADO en este fichero por
-- `test_f057_r16b_no_usa_auxhor_ext`, comentarios aparte, para que nadie lo
-- reintroduzca por descuido.
--
-- `auxmed` (38 filas) NO se ingiere (D5): traducir cuatro literales estables
-- costaria tocar la ingesta, `check-raw-recuentos` y la ficha de `raw`, y esta
-- feature no es de ingesta. El seguro es la rama ELSE: un quinto valor en
-- origen sale como 'DESCONOCIDA' y el test-guarda lo hace visible, en vez de
-- colarse en la cifra de horas.
--
-- ---------------------------------------------------------------------------
-- LA OBRA SALE DE LA LINEA, NO DE LA CABECERA (R12, D2)
-- ---------------------------------------------------------------------------
-- `hmores.obride` esta informado en 329.265 de 330.638 filas (99,58 %) sobre
-- 536 obras. En 769 lineas (0,23 %) la obra de la linea difiere de la de su
-- cabecera `hmo`, y manda la LINEA: es ademas la que lleva la partida. Por eso
-- este fichero **no une `raw.hmo` en absoluto** — un JOIN a la cabecera «solo
-- para mirar» es como se cuela la atribucion equivocada.
--
-- LA TRAMPA DE `apu`/F-045 NO APLICA AQUI, y se deja escrito para que F-045 no
-- herede una respuesta que no es suya: alli la atribucion va por centro de
-- coste porque no hay obra en el dato; aqui el parte TRAE la obra.
-- `maestro.centros_coste` (F-073) no participa, y `res.cenconide` —informado
-- al 75,5 % pero con 9 valores distintos— tampoco. Los dos identificadores
-- estan vetados por `test_f057_r13_no_usa_centro_de_coste`.
--
-- EL CODIGO DEL PARTE SI BAJA A LA LINEA (F-101), y sin romper lo anterior:
-- sale de `raw.con` por `hmores.hmoide` —el concepto del parte, R-SIGRID-CON—,
-- no de `raw.hmo`. Medido el 2026-09-23: 0 de 330.941 lineas apuntan a una
-- cabecera inexistente; el JOIN es LEFT por la misma razon que el resto del
-- fichero. OJO: el codigo NO es unico (569 codigos repetidos en 1.197 partes):
-- para agrupar por parte se usa `parte_id`. La cabecera completa —y su obra, que
-- AUDITA— esta en `personal.partes`.
--
-- EL TEXTO DE LA LINEA (F-101, D-3): `hmores.tex`, que se ingiere desde este
-- hotfix. Informado en 13.390 de 330.941 lineas (4,05 %). Es TEXTO LIBRE y
-- puede llevar nombres de persona (medido: un nombre y dos apellidos en el
-- comentario de una linea), otra razon para que viva en `personal`. La cadena
-- vacia se publica como NULL: no hay texto.
--
-- ---------------------------------------------------------------------------
-- NO SE FILTRA NADA
-- ---------------------------------------------------------------------------
-- El universo de obra (`R-UNIVERSO-OBRA`) se MARCA, no se filtra:
-- `en_seguimiento` sale de un EXISTS contra `stg.obras`, que es la unica
-- lectura de este esquema fuera de `raw` y lo que fija
-- `depends_on = ["build_stg"]`. **No se replican los filtros de
-- `stg/03_obras.sql`**: duplicar esa lista de codigos administrativos es como
-- se desincronizan dos verdades. Medido: 523 obras del seguimiento (318.892
-- lineas, 1.226.158,60 h, 93,24 M EUR = 94,9 % del euro), 12 administrativas
-- (10.373 lineas, 4,93 M EUR) y 1.373 lineas con la obra a cero.
--
-- El importe va con su SIGNO: `tot` cuadra con `round(can * pre, 2)` en
-- 330.596 de 330.638 lineas; 11.036 valen 0 y 9.119 son negativas
-- (correcciones). Un ABS o un `WHERE tot > 0` borraria las correcciones.
--
-- LA CUENTA ANALITICA DE LA LINEA (F-107, ampliacion decidida por el humano el
-- 2026-09-24): `hmores.caaide`, la cuenta de CARGO. Medido en Sigrid en solo
-- lectura: informada en 310.553 de 331.003 lineas (93,8 %), 3.782 cuentas, 0
-- huerfanas contra `caa` y todas de la empresa del recurso. En 309.182 el
-- prefijo del codigo de la cuenta es el codigo de la obra de la linea: es la
-- cuenta del centro de la obra. NO es la contrapartida (esa es del recurso,
-- `personal.recursos`): solo 45 lineas la llevan. Se publica el id con NULLIF
-- 0 y sin JOIN; medido el SELECT en solo lectura: 3,05 s sin ella, 3,1 s con
-- ella.
--
-- DEFECTOS DE CALIDAD MEDIDOS EN ORIGEN, que se declaran y NO se corrigen:
-- 5 lineas con fecha 0, una con fecha del año 3103, 6 con año fuera de
-- 1990-2030 y 5 con mes fuera de 1-12. `personal.fn_fecha` devuelve NULL para
-- el 0; el resto se publica tal cual y la ficha del diccionario lo advierte.
-- ============================================================================

TRUNCATE TABLE personal.partes_lineas;

INSERT INTO personal.partes_lineas (
    linea_id, parte_id, codigo_parte, recurso_id, obra_id, en_seguimiento,
    partida_id,
    fecha, anio, mes,
    tipo_hora_id, tipo_hora, unidad,
    cantidad, precio, importe, texto_linea,
    cuenta_analitica_id
)
SELECT
    l.ide                                   AS linea_id,
    NULLIF(l.hmoide, 0)                     AS parte_id,
    c.cod                                   AS codigo_parte,
    NULLIF(l.reside, 0)                     AS recurso_id,
    NULLIF(l.obride, 0)                     AS obra_id,
    -- MARCA, no filtro. El EXISTS pregunta al universo del seguimiento en vez
    -- de reconstruirlo: si `stg/03_obras.sql` cambia sus reglas, esto cambia
    -- con el y no hay dos verdades que mantener.
    EXISTS (
        SELECT 1 FROM stg.obras o WHERE o.obra_id = NULLIF(l.obride, 0)
    )                                       AS en_seguimiento,
    NULLIF(l.paride, 0)                     AS partida_id,
    personal.fn_fecha(l.fec)                AS fecha,
    l.ano                                   AS anio,
    l.mes                                   AS mes,
    NULLIF(l.horide, 0)                     AS tipo_hora_id,
    h.res                                   AS tipo_hora,
    -- EL CORTE QUE EVITA LA CIFRA FALSA. Ver la tabla de la cabecera.
    CASE h.medide
        WHEN 1  THEN 'HORA'
        WHEN 2  THEN 'DIA'
        WHEN 3  THEN 'MES'
        WHEN 19 THEN 'UD'
        ELSE 'DESCONOCIDA'
    END::VARCHAR(12)                        AS unidad,
    COALESCE(l.can, 0)::NUMERIC(18,2)       AS cantidad,
    COALESCE(l.pre, 0)::NUMERIC(18,4)       AS precio,
    COALESCE(l.tot, 0)::NUMERIC(18,2)       AS importe,
    NULLIF(l.tex, '')                       AS texto_linea,
    -- F-107: la cuenta de CARGO de la linea, solo el id (se traduce en
    -- `maestro.cuentas_analiticas` por relacion; aqui no se une nada).
    NULLIF(l.caaide, 0)                     AS cuenta_analitica_id
FROM      raw.hmores l
-- LEFT, y hace falta: 10 lineas apuntan a un tipo de hora que no esta en el
-- catalogo. Con JOIN desaparecerian sin ruido; asi salen como 'DESCONOCIDA'.
LEFT JOIN raw.auxhor h ON h.ide = l.horide
-- El codigo del parte, del CONCEPTO del parte (F-101). Nunca `raw.hmo` (R12).
LEFT JOIN raw.con    c ON c.ide = l.hmoide;

COMMENT ON TABLE personal.partes_lineas IS
'Lineas de parte de trabajo (330.638 el 2026-09-18), una fila por fila de raw.hmores. NUNCA SUMAR `cantidad` SIN FILTRAR `unidad`: mezcla HORA, DIA, MES y UD, y en bruto da 1.837.201,23 de nada. Las horas son unidad = HORA (1.249.038,44 h), pero el 71,7 % del euro esta en las lineas de MES, que son el coste de estructura de obra. La obra sale de la LINEA (hmores.obride), no de la cabecera, y el universo del seguimiento se MARCA en en_seguimiento en vez de filtrarse. cuenta_analitica_id es la cuenta analitica de CARGO de la linea (F-107), no la contrapartida del recurso.';
