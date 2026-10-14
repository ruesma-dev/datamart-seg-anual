# F-138 · Diseño: las alarmas de los documentos de compra y la marca «liquidatoria»

Mediciones que sostienen cada cifra: `progress/spec_F-138.md`.

## Encaje y límite del servicio

- **Ingesta**: dos tablas más en `raw` (`conala` filtrada en origen, `auxala`
  entera) por la vía de siempre (`ingest_raw` + `tables_sigrid.yaml`). Ni paso
  nuevo ni cliente nuevo: `stream_table` ya compone `WHERE [ide] > ? AND
  (<where>)` y `check-raw-recuentos` cuenta con el mismo `where` (patrón F-090).
- **Negocio**: un fichero más en el módulo `compras` (`build_compras`, sub-paso
  15, el último). Lee `raw` y las tablas de `compras` que construye `01`. No
  toca `stg`, `mart`, `cierre`, `retenciones` ni ningún objeto existente.
- **Límite**: este ETL LEE la alarma; no la crea ni la corrige (eso es Sigrid, y
  desde aquí solo hay lecturas). Dentro del límite: es publicar un dato de
  documentos de compra que ya están en `compras`. Las alarmas de VENTA (tip 11,
  54) también serían de este datamart, pero no de esta feature (D3).

## Ficheros a crear

| Ruta | Qué |
|---|---|
| `etl_sigrid/domain/liquidatoria.py` | Oráculo puro: familias, `filtro_conala()`, traducción, patrones, `normalizar`, `clasificar`, `marca_documento`, `fecha_hora_creacion`, `PRECEDENCIA` |
| `etl_sigrid/infrastructure/postgres/sql/compras/15_alarmas_liquidatoria.sql` | guarda R16, dos funciones, `documento_alarmas`, `documento_liquidatoria`, `contrato_liquidacion` |
| `tests/test_f138_dominio.py` | R6-R12 (casos de R10 y propiedades: idempotencia de `normalizar`, longitudes de la traducción) |
| `tests/test_f138_ingesta_sql.py` | R1-R5, R13-R26 sobre el TEXTO del YAML, del SQL y de `SUB_PASOS` (no se ejecuta SQL: Postgres compartido) |
| `tests/test_f138_diccionario.py` | R27-R31 |

## Ficheros a modificar

| Ruta | Cambio |
|---|---|
| `config/tables_sigrid.yaml` | + `conala` y + `auxala` al final, con su comentario (cifras, filtro, que `fec1`/`fec2` están vacías y que `creusu` es un login) |
| `etl_sigrid/application/steps/build_compras_step.py` | + `_SubStep("alarmas_liquidatoria", "15_alarmas_liquidatoria.sql", "compras", "documento_alarmas")` al final de `SUB_PASOS`, con su comentario, y la línea del docstring |
| `config/diccionario/compras.yaml` | fichas `documento_alarmas`, `documento_liquidatoria`, `contrato_liquidacion`, `fn_texto_normalizado`, `fn_clase_liquidacion`; una línea en `relaciones` de `facturas`, `albaranes` y `contratos` |
| `config/diccionario/raw.yaml` | fichas `conala` y `auxala` (capa origen, `consumo_recomendado: false`); «Son 76 tablas» |
| `config/diccionario/00_global.yaml` | `version` +1 con su nota (F-138), «las 76 tablas» (dos sitios: líneas ~522 y ~1130) |
| `docs/ARCHITECTURE.md` | § «Qué se copia de Sigrid»: 76 tablas, `conala` filtrada y `auxala`, F-138 en el título |
| `tests/test_f085_sql.py`, `test_f085_diccionario.py`, `test_f090_diccionario.py`, `test_f090_ingesta_sql.py`, `test_f095_retenciones_contables.py`, `test_f097_ingesta_descompuestos.py` | el censo fijado en 74 pasa a 76 (asserts y textos buscados); nada más |
| `C:\Users\pgris\PycharmProjects\azure-apps\datamart_seg_anual.md` (otro repo, commit propio allí, sin push) | «Qué consume»: 76 tablas, `conala`/`auxala`; «Qué expone»: los tres objetos |

## Ficheros que NO se tocan

- `sql/compras/01_documentos.sql` (`facturas`, `albaranes`): D7. F-128 (P3) y
  F-093 van a añadirles columnas; la marca como columna se añade cuando cierren.
- `sql/compras/07_texto.sql` (`documento_texto` solo publica tip 15 y 44): el
  memo se lee de `raw.con.tex` directamente; ampliar el memo a albaranes es otra
  feature.
- `sql/compras/03_views.sql`: se COPIA su cadena factura -> contrato, no se
  cambia la vista.
- `ingest_raw_step.py`, `sigrid_api_client.py`, `config/settings.py`: el
  `where` basta; `raw` ya está vetado al rol general (F-135), así que `creusu`
  en `raw` no abre nada nuevo.
- `config/objetos_pendientes.yaml`: los objetos nuevos los construye `run-all`.

## Dominio · `etl_sigrid/domain/liquidatoria.py`

```python
TIPOS_DOCUMENTO_ALARMAS: Final[tuple[int, ...]] = (14, 15)
TRADUCCION_ORIGEN: Final[str] = "áàäâéèëêíìïîóòöôúùüûñçÁÀÄÂÉÈËÊÍÌÏÎÓÒÖÔÚÙÜÛÑÇ"
TRADUCCION_DESTINO: Final[str] = "aaaaeeeeiiiioooouuuuncAAAAEEEEIIIIOOOOUUUUNC"
PATRON_MENCION / PATRON_NEGADA / PATRON_DUDOSA / PATRON_REMITE: Final[str]  # R9, literales
PRECEDENCIA: Final[tuple[str, ...]] = ("NEGADA", "LIQUIDATORIA", "DUDOSA", "REMITE")

def filtro_conala() -> str: ...          # "conide IN (SELECT ide FROM dbo.con WHERE tip IN (14, 15))"
def normalizar(texto: str | None) -> str: ...
def clasificar(texto: str | None) -> str | None: ...
def marca_documento(clases: Iterable[str | None]) -> str | None: ...
def fecha_hora_creacion(crefec: int | None, crehor: int | None) -> datetime | None: ...
```

`normalizar` = `str.translate(maketrans(ORIGEN, DESTINO))` -> `re.sub(r"[^A-Za-z0-9]+", " ")`
-> `.upper()` -> `.strip()`. El `upper` va DESPUÉS de dejar solo ASCII a
propósito: así Python y PostgreSQL dan lo mismo con cualquier `LC_CTYPE` (en
`C`, `upper('á')` no cambia; y Python convierte `ß` en `SS`). Mismo patrón que
`domain/documento_adjuntos.py` y `texto_comentarios.py`: la regla vive UNA vez
aquí y los tests comprueban que el SQL y el YAML llevan los mismos literales.

## SQL · `sql/compras/15_alarmas_liquidatoria.sql`

Cabecera: qué construye, de qué lee (`raw.conala`, `raw.auxala`, `raw.con`,
`compras.contratos`, `facturas`, `factura_lineas`, `albaranes`, `albaran_lineas`)
y que los literales son los del dominio. Orden dentro del fichero:

1. **Guarda R16** (`DO`): si no existe ninguna fila de `raw.conala` unida a
   `raw.con` con `tip IN (14, 15)`, `RAISE EXCEPTION 'F-138: ...'`.
2. **Funciones** (`CREATE OR REPLACE`, `IMMUTABLE`):
   - `compras.fn_texto_normalizado(t TEXT) RETURNS TEXT` =
     `btrim(upper(regexp_replace(translate(COALESCE(t, ''), '<ORIGEN>', '<DESTINO>'), '[^A-Za-z0-9]+', ' ', 'g')))`.
   - `compras.fn_clase_liquidacion(t TEXT) RETURNS TEXT`: `CASE` sobre el
     normalizado, en el orden de R8 (`!~ MENCION` -> `REMITE`/NULL; `~ NEGADA`;
     `~ DUDOSA`; `LIQUIDATORIA`).
   Van en este fichero y no en `00_setup.sql` para que F-138 quede en una pieza;
   `00` corre antes y no las necesita.
3. **`compras.documento_alarmas`** (R13-R14): `raw.conala a JOIN raw.con c ON
   c.ide = a.conide AND c.tip IN (14, 15) LEFT JOIN raw.auxala x ON x.ide =
   NULLIF(a.alaide, 0)`. `creada_el` = `compras.fn_sigrid_date(a.crefec) +
   make_interval(hours => crehor / 10000, mins => crehor / 100 % 100, secs =>
   crehor % 100)` dentro de un `CASE` que deja NULL las horas imposibles
   (mismo criterio que el oráculo R12). `ver_al_abrir` = `a.tipabr = 1`.
   `creada_por` = `NULLIF(btrim(a.creusu), '')`. PK `alarma_id`; índices
   `documento_id` y `clase_liquidacion`.
4. **`compras.documento_liquidatoria`** (R17-R20):
   - CTE `al`: por `documento_id` desde `documento_alarmas`, `marca` con un
     `CASE WHEN bool_or(clase = 'NEGADA') ... 'LIQUIDATORIA' ... 'DUDOSA' ...
     'REMITE'` en el orden de `PRECEDENCIA` (un test comprueba el orden de los
     literales), `string_agg(texto, ' | ' ORDER BY alarma_id) FILTER (WHERE
     clase IS NOT NULL)` y `min(creada_el) FILTER (WHERE clase = 'LIQUIDATORIA')`.
   - CTE `memo`: `raw.con` con `tip IN (14, 15) AND tex ILIKE '%liq%'` y
     `fn_clase_liquidacion(tex)`.
   - Universo: `al.marca IS NOT NULL` UNION `memo.clase IS NOT NULL`, unido a
     `raw.con` para código, tipo y `fecha_alta` (`fn_sigrid_date(con.fec)`).
   - `es_liquidatoria` = `COALESCE(al.marca = 'LIQUIDATORIA', FALSE)`.
   - PK `documento_id`; índices `tipo_documento`, `es_liquidatoria`.
5. **`compras.contrato_liquidacion`** (R21-R22):
   - CTE `fac_ctr`: `DISTINCT factura_id, COALESCE(fl.contrato_id_directo,
     alb.contrato_id, alb_l.contrato_id_linea)` con los mismos `LEFT JOIN`
     (por `albaran_linea_id`) que `fact_por_ctr` de `v_pbi_contrato_consumo`.
   - CTE `alb_ctr`: `DISTINCT albaran_id, COALESCE(a.contrato_id,
     l.contrato_id_linea)` de `albaranes` + `albaran_lineas`, solo `tipo_documento
     IN ('ALBARAN', 'PROFORMA')`.
   - Facturas liquidatorias = `documento_liquidatoria` con `es_liquidatoria` y
     `tipo_documento_codigo = 15`; primera = menor `(fecha, factura_id)` de
     `compras.facturas`; posteriores = facturas del contrato con `fecha` >
     esa; última es liquidatoria = la factura de mayor `(fecha, factura_id)`
     del contrato tiene `es_liquidatoria`.
   - `JOIN compras.contratos` para código y obra. PK `contrato_id`; índice
     `obra_id`.
   - Si D1 la deja fuera, se borra este bloque, su ficha y R21-R23: nada más
     depende de él.

Coste esperado: `documento_alarmas` ~23.800 filas y `documento_liquidatoria`
~18.000; `contrato_liquidacion` agrega `factura_lineas` entera una vez (lo mismo
que hace la vista de consumo en cada lectura). Segundos, no minutos.

## Ingesta · `config/tables_sigrid.yaml`

```yaml
  - source_table: conala
    target_table: conala
    id_column: ide
    incremental_column: null   # medido 2026-10-14: `conala` no tiene tiemod
    where: "conide IN (SELECT ide FROM dbo.con WHERE tip IN (14, 15))"
    exclude_columns: []
  - source_table: auxala
    target_table: auxala
    id_column: ide
    incremental_column: tiemod
    where: null
    exclude_columns: []
```

Coste medido: 23.833 filas y 643 KB en 1,1 s, una petición; `auxala`, 4 filas.
`conala` va DETRÁS de `con` en la lista (ya lo está al ir al final).

## Diccionario (resumen de lo que dicen las fichas)

- `documento_alarmas`: una fila por alarma de factura o albarán (AC, PROF,
  NTC); la alarma es TEXTO LIBRE que alguien escribe a mano en Sigrid, no un
  campo; `tipo_alarma` 03 INFORMATIVA en el 99,6 %; `creada_el`/`creada_por`
  son el «Creada por … -> fecha hora» de la ventana; `fec1`/`fec2` no se
  publican (1 de 23.833 informada); `clase_liquidacion` y su regla.
- `documento_liquidatoria`: la marca, su regla en palabras, la precedencia, la
  cobertura de R28 y lo que queda fuera (R29); «no tener fila» = «ninguna
  alarma ni memo lo menciona»; `clase_memo` es indicio, no marca (D5); para la
  obra de una factura, `factura_lineas.obra_id` (la de imputación).
- `contrato_liquidacion`: grano, la cadena, que la «fecha» es la de alta
  (`con.fec`) y que `num_facturas_posteriores > 0` es lo que hay que mirar.
- `ejemplos_preguntas` con las tres de R33.

## Riesgos y decisiones

- **La regla es heurística sobre texto libre** (697 variantes). Se mitiga
  publicando el texto íntegro y la clase de cada alarma: quien dude puede leer
  el texto. Los casos raros conocidos (p. ej. «UNICA Y LIQUIDATORIA, TRABAJOS
  POSTERIORES A LA LIQUIDACION» -> DUDOSA) quedan escritos en la ficha.
- **`\b` en PostgreSQL es RETROCESO, no frontera de palabra**: por eso los
  patrones usan `(^| )` sobre el texto ya normalizado. Un test prohíbe `\b`,
  `\w` y `(?` en las constantes.
- **El prefiltro `ILIKE '%liq%'` del memo** no ve «LÍQ…» con tilde; ninguna
  variante medida lo lleva. Declarado.
- **Descartado**: columna en `compras.facturas`/`albaranes` (D7); ingerir
  `conala` entera (46.242: trae alarmas de empleados a `raw`, D3); vista en vez
  de tabla para `contrato_liquidacion` (agrega `factura_lineas` entera en cada
  consulta: pasaría de los 30 s del MCP).
- **Versión del diccionario**: la siguiente libre al implementar (hoy 51 -> 52);
  F-128 puede subirla antes.

## Verificación MANUAL (tras desplegar la imagen)

- `python main.py ingest --table conala --full`, `... --table auxala --full`
  (o la nocturna), `python main.py build-compras`, `python main.py
  check-raw-recuentos`; recuentos de R32 y R23 por SQL de solo lectura.
- `publicar-diccionario` (lo autoriza el humano), reiniciar el MCP (cachea el
  diccionario) y las tres preguntas de R33. `compras` ya está en la lista blanca
  de `mcp-bbdd`: no hace falta tocarla.
- Primera nocturna: segundos de `ingest_raw.conala`, `ingest_raw.auxala` y del
  sub-paso (`python main.py timings`), anotados en `progress/` (R34).
