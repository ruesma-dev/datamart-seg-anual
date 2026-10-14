# F-138 · Diseño: las alarmas de los documentos de Sigrid y la marca «liquidatoria»

Mediciones que sostienen cada cifra: `progress/spec_F-138.md`. Decisiones del
humano (2026-10-14): `requirements.md` § Decisiones.

## Encaje y límite del servicio

- **Ingesta**: dos tablas más en `raw` (`conala` filtrada en origen a todas las
  familias menos empleados, `auxala` entera) por la vía de siempre
  (`ingest_raw` + `tables_sigrid.yaml`). Ni paso nuevo ni cliente nuevo:
  `stream_table` ya compone `WHERE [ide] > ? AND (<where>)` y
  `check-raw-recuentos` cuenta con el mismo `where` (patrón F-090).
- **Negocio**: un fichero más en el módulo `compras` (`build_compras`, sub-paso
  15, el último). Lee `raw` y las tablas que construye `01`. No toca `stg`,
  `mart`, `cierre`, `retenciones` ni ningún objeto existente.
- **Límite**: este ETL LEE las alarmas; no las crea ni las corrige (solo
  lecturas de Sigrid). Publicar las alarmas de todos los documentos en `compras`
  es aceptable porque el 86 % son de compras (facturas, contratos, albaranes) y
  el resto son pocas (ventas 4.647, proveedores 470, otras ~1.200); si algún día
  el dato de ventas crece en uso, su sitio natural sería un esquema de ventas.

## Ficheros a crear

| Ruta | Qué |
|---|---|
| `etl_sigrid/domain/liquidatoria.py` | Oráculo puro: familias, `filtro_conala()`, traducción, patrones, `PRECEDENCIA`, `normalizar`, `clasificar`, `marca_documento`, `fecha_hora_creacion` |
| `etl_sigrid/infrastructure/postgres/sql/compras/15_alarmas_liquidatoria.sql` | guarda R16, dos funciones y los cuatro objetos |
| `tests/test_f138_dominio.py` | R5-R12 (casos de R10, precedencia, horas imposibles, idempotencia de `normalizar`, longitudes de la traducción, patrones sin `\b`/`\w`/`(?`) |
| `tests/test_f138_ingesta_sql.py` | R1-R5, R13-R26 sobre el TEXTO del YAML, del SQL y de `SUB_PASOS` (no se ejecuta SQL: Postgres compartido) |
| `tests/test_f138_diccionario.py` | R27-R30 |

## Ficheros a modificar

| Ruta | Cambio |
|---|---|
| `config/tables_sigrid.yaml` | + `conala` y + `auxala` al final, con su comentario (cifras, por qué lista explícita, la 43 fuera, `fec1`/`fec2` vacías, `creusu` es un login) |
| `etl_sigrid/application/steps/build_compras_step.py` | + `_SubStep("alarmas_liquidatoria", "15_alarmas_liquidatoria.sql", "compras", "documento_alarmas")` al final de `SUB_PASOS`, con comentario, y la línea del docstring |
| `config/diccionario/compras.yaml` | fichas `documento_alarmas`, `documento_liquidatoria`, `contrato_liquidacion`, `facturas_tras_liquidacion`, `fn_texto_normalizado`, `fn_clase_liquidacion`; una línea en `relaciones` de `facturas`, `albaranes` y `contratos` |
| `config/diccionario/raw.yaml` | fichas `conala` y `auxala` (capa origen, `consumo_recomendado: false`); «Son 76 tablas» |
| `config/diccionario/00_global.yaml` | `version` +1 con su nota (F-138), «las 76 tablas» (líneas ~522 y ~1130) |
| `docs/ARCHITECTURE.md` | § «Qué se copia de Sigrid»: 76 tablas, `conala` (sin la 43) y `auxala`, F-138 en el título |
| `tests/test_f085_sql.py`, `test_f085_diccionario.py`, `test_f090_diccionario.py`, `test_f090_ingesta_sql.py`, `test_f095_retenciones_contables.py`, `test_f097_ingesta_descompuestos.py` | el censo fijado en 74 pasa a 76 (asserts y textos buscados); nada más |
| `C:\Users\pgris\PycharmProjects\azure-apps\datamart_seg_anual.md` (otro repo, commit propio allí, sin push) | «Qué consume»: 76 tablas, `conala`/`auxala`; «Qué expone»: los cuatro objetos |

## Ficheros que NO se tocan

- `sql/compras/01_documentos.sql` (`facturas`, `albaranes`): D7. F-128 (P3) y
  F-093 van a añadirles columnas; la marca como columna, cuando cierren.
- `sql/compras/07_texto.sql` (`documento_texto`, solo tip 15 y 44): el memo se
  lee de `raw.con.tex` directamente.
- `sql/compras/03_views.sql`: se COPIA su cadena factura -> contrato.
- `ingest_raw_step.py`, `sigrid_api_client.py`, `config/settings.py`: el
  `where` basta; `raw` ya está vetado al rol general (F-135).
- `config/objetos_pendientes.yaml`: los objetos nuevos los construye `run-all`.

## Dominio · `etl_sigrid/domain/liquidatoria.py`

```python
FAMILIAS_ALARMAS: Final[dict[int, str]] = {1: "INFORME", 4: "CLIENTE", ..., 54: "CONTRATO_VENTA"}  # R6, sin la 43
FAMILIA_EMPLEADOS: Final[int] = 43         # la que no entra nunca (R5)
FAMILIAS_MARCA: Final[tuple[int, ...]] = (14, 15)
TRADUCCION_ORIGEN: Final[str] = "áàäâéèëêíìïîóòöôúùüûñçÁÀÄÂÉÈËÊÍÌÏÎÓÒÖÔÚÙÜÛÑÇ"
TRADUCCION_DESTINO: Final[str] = "aaaaeeeeiiiioooouuuuncAAAAEEEEIIIIOOOOUUUUNC"
PATRON_MENCION, PATRON_NEGADA, PATRON_CARTA, PATRON_DUDOSA, PATRON_REMITE: Final[str]  # R9
PRECEDENCIA: Final[tuple[str, ...]] = (
    "NEGADA", "LIQUIDATORIA", "CARTA_LIQUIDACION", "DUDOSA", "REMITE")
CLASES_CIERRE: Final[frozenset[str]] = frozenset({"LIQUIDATORIA", "CARTA_LIQUIDACION"})

def filtro_conala() -> str: ...   # "conide IN (SELECT ide FROM dbo.con WHERE tip IN (1, 4, 5, ...))"
def normalizar(texto: str | None) -> str: ...
def clasificar(texto: str | None) -> str | None: ...
def marca_documento(clases: Iterable[str | None]) -> str | None: ...
def fecha_hora_creacion(crefec: int | None, crehor: int | None) -> datetime | None: ...
```

`normalizar` = `translate` -> `re.sub(r"[^A-Za-z0-9]+", " ")` -> `.upper()` ->
`.strip()`. El `upper` va DESPUÉS de dejar solo ASCII a propósito: así Python y
PostgreSQL dan lo mismo con cualquier `LC_CTYPE` (en `C`, `upper('á')` no
cambia; Python convierte `ß` en `SS`). Mismo patrón que `documento_adjuntos.py`
y `texto_comentarios.py`: la regla vive UNA vez aquí y los tests comprueban que
el SQL y el YAML llevan los mismos literales.

### Lista explícita y no «todo menos la 43» (D3)

El filtro enumera las 17 familias en vez de `tip <> 43`. Ante una familia NUEVA
con alarmas, la lista falla CERRADA: no entra hasta que alguien la añade, y lo
peor que pasa es que falte un dato. La exclusión fallaría ABIERTA: si mañana
alguien pone una alarma a una nómina (F-090 midió 306 adjuntos de nómina en
otra familia de personal), entraría sola en `raw` y en `compras`, que leen el
MCP y Power BI. La ficha de `raw.conala` deja escrita la consulta de solo
lectura que hace el censo (`SELECT c.tip, COUNT(*) ... GROUP BY c.tip`) para
revisarla cuando se quiera.

### Precedencia

- **Por alarma** (R8): `NEGADA` antes que nada porque la negación es explícita
  («NO ES LIQUIDATORIA»); `CARTA_LIQUIDACION` antes que `DUDOSA` porque Negocio
  dice qué significa (2026-10-14); `DUDOSA` antes que `LIQUIDATORIA` porque
  «PREVISIÓN DE LIQUIDACIÓN» no lo es todavía.
- **Por documento** (R11): `NEGADA` > `LIQUIDATORIA` > `CARTA_LIQUIDACION` >
  `DUDOSA` > `REMITE`. La declarada gana a la carta porque la carta se pide
  justamente cuando la factura NO lo decía: si otra alarma del mismo documento
  sí lo dice, el documento es liquidatoria declarada. Las dos CIERRAN el
  contrato (`cierra_contrato`); `pendiente_carta_liquidacion` las distingue.

## SQL · `sql/compras/15_alarmas_liquidatoria.sql`

Cabecera: qué construye, de qué lee (`raw.conala`, `raw.auxala`, `raw.con`,
`compras.contratos`, `facturas`, `factura_lineas`, `albaranes`,
`albaran_lineas`) y que los literales son los del dominio. Orden:

1. **Guarda R16** (`DO`): sin ninguna alarma de factura (`tip = 15`) en
   `raw.conala`, `RAISE EXCEPTION 'F-138: ...'` (ingesta ausente o a medias).
2. **Funciones** (`CREATE OR REPLACE`, `IMMUTABLE`): `compras.fn_texto_normalizado(t)` =
   `btrim(upper(regexp_replace(translate(COALESCE(t, ''), '<ORIGEN>', '<DESTINO>'), '[^A-Za-z0-9]+', ' ', 'g')))`;
   `compras.fn_clase_liquidacion(t)` = `CASE` sobre el normalizado en el orden
   de R8. Aquí y no en `00_setup.sql` para que F-138 quede en una pieza.
3. **`compras.documento_alarmas`** (R13-R14): `raw.conala a JOIN raw.con c ON
   c.ide = a.conide LEFT JOIN raw.auxala x ON x.ide = NULLIF(a.alaide, 0)`.
   `familia` = `CASE c.tip WHEN 1 THEN 'INFORME' ... END` con las parejas de R6.
   `creada_el` = `fn_sigrid_date(crefec) + make_interval(hours => crehor /
   10000, mins => crehor / 100 % 100, secs => crehor % 100)` dentro de un
   `CASE` que deja NULL las horas imposibles (oráculo R12). `creada_por` =
   `NULLIF(btrim(a.creusu), '')`. PK `alarma_id`; índices `documento_id`,
   `familia`.
4. **`compras.documento_liquidatoria`** (R17-R20): CTE `al` por `documento_id`
   desde `documento_alarmas` con `tipo_documento_codigo IN (14, 15)`: `marca` =
   `CASE WHEN bool_or(clase = 'NEGADA') ...` en el orden de `PRECEDENCIA` (un
   test comprueba el orden de los literales), `string_agg(texto, ' | ' ORDER BY
   alarma_id) FILTER (WHERE clase IS NOT NULL)`, `min(creada_el) FILTER (WHERE
   clase IN ('LIQUIDATORIA', 'CARTA_LIQUIDACION'))`. CTE `memo`: `raw.con` con
   `tip IN (14, 15) AND tex ILIKE '%liq%'`. Universo = `al.marca` no nula UNION
   `memo.clase` no nula, unido a `raw.con`. Booleanos con `COALESCE(..., FALSE)`.
   PK `documento_id`; índices `tipo_documento`, `cierra_contrato`.
5. **`compras.contrato_liquidacion`** (R21-R22): CTE `fac_ctr` = `DISTINCT
   factura_id, COALESCE(fl.contrato_id_directo, alb.contrato_id,
   alb_l.contrato_id_linea)` con los mismos `LEFT JOIN` (por `albaran_linea_id`)
   que `fact_por_ctr` de `v_pbi_contrato_consumo`; CTE `alb_ctr` = `DISTINCT
   albaran_id, COALESCE(a.contrato_id, l.contrato_id_linea)` solo `ALBARAN` y
   `PROFORMA`. Factura de cierre por contrato con `DISTINCT ON (contrato_id)
   ... ORDER BY fecha, factura_id` entre las de `cierra_contrato`; última factura
   igual con `ORDER BY fecha DESC, factura_id DESC`. Base: `compras.contratos`
   con LEFT JOIN, para que los 19.127 estén y `facturas_terminadas` sea FALSE
   (no NULL) en los que no tienen cierre. PK `contrato_id`; índice `obra_id`.
6. **`compras.facturas_tras_liquidacion`** (R23): `fac_ctr` JOIN
   `contrato_liquidacion` (con cierre) JOIN `compras.facturas` con `f.fecha >
   fecha_cierre`. PK (`contrato_id`, `factura_id`); índices `obra_id`,
   `proveedor_id`. ~1.170 filas. Es el AVISO (c): «facturas llegadas después de
   la liquidatoria», consultable sin cruzar nada.

`fac_ctr` se calcula una vez en una tabla `TEMP` (o CTE repetido) que usan 5 y
6. Coste esperado: `documento_alarmas` ~45.700 filas; el resto, decenas de miles
como mucho; segundos.

## Ingesta · `config/tables_sigrid.yaml`

```yaml
  - source_table: conala
    target_table: conala
    id_column: ide
    incremental_column: null   # medido 2026-10-14: `conala` no tiene tiemod
    where: "conide IN (SELECT ide FROM dbo.con WHERE tip IN (1, 4, 5, 11, 12, 14, 15, 17, 20, 25, 33, 35, 40, 42, 44, 46, 54))"
    exclude_columns: []
  - source_table: auxala
    target_table: auxala
    id_column: ide
    incremental_column: tiemod
    where: null
    exclude_columns: []
```

Coste medido: 45.747 filas y 1,79 MB leídos en ~2 s en una petición (a 10.000
filas por página, 5 páginas; la subconsulta del filtro se repite en cada una,
como en `gra`: estimado < 15 s). `auxala`, 4 filas.

## Diccionario (resumen)

- `documento_alarmas`: una fila por alarma de cualquier documento salvo
  empleados; TEXTO LIBRE escrito a mano en Sigrid; 03 INFORMATIVA en el ~98 %;
  `creada_el`/`creada_por` son el «Creada por … -> fecha hora» de la ventana;
  `fec1`/`fec2` no se publican; `clase_liquidacion` en todas las familias (las
  marcas de ventas, contratos y comparativos se leen aquí).
- `documento_liquidatoria`: la regla en palabras, la precedencia, la carta, la
  cobertura (R28); «no tener fila» = «ninguna alarma ni memo lo menciona»;
  `clase_memo` es indicio, no marca (D5); la obra de una factura es
  `factura_lineas.obra_id`.
- `contrato_liquidacion`: el para qué (a)-(c); que `fecha_cierre` es la de alta
  (`con.fec`) de la factura de cierre y que, según Control de Costes, desde ella
  el IVA ya no se difiere; `tipo_cierre` CARTA_LIQUIDACION = falta pedir la
  carta; `facturas_terminadas` FALSE no prueba que falten facturas (≈ 5 % de las
  facturas llevan la marca).
- `facturas_tras_liquidacion`: el aviso (c) y cómo leerlo.
- `ejemplos_preguntas` con las cuatro de R33.

## Riesgos y decisiones

- **Regla heurística sobre texto libre** (697 variantes): se publica el texto
  íntegro y la clase de cada alarma; los casos raros conocidos van en la ficha.
- **`\b` en PostgreSQL es RETROCESO, no frontera de palabra**: por eso
  `(^| )` sobre el texto ya normalizado. Un test lo prohíbe en las constantes.
- **El prefiltro `ILIKE '%liq%'` del memo** no ve «LÍQ…»: ninguna variante medida.
- **Datos personales (D9, abierta)**: con D3, 27 alarmas de recursos y partes con
  nombres de trabajadores y sus bajas llegan a `compras`. Si el humano acepta
  D9, se quitan 33 y 35 de `FAMILIAS_ALARMAS` y del `where`; nada más cambia.
- **Descartado**: columna en `facturas`/`albaranes` (D7); vistas en vez de tablas
  para los objetos de contrato (agregan `factura_lineas` entera en cada lectura:
  pasarían de los 30 s del MCP).
- **Versión del diccionario**: la siguiente libre al implementar (hoy 51 -> 52).

## Verificación MANUAL (tras desplegar la imagen)

- `python main.py ingest --table conala --full`, `... --table auxala --full`
  (o la nocturna), `python main.py build-compras`, `python main.py
  check-raw-recuentos`; recuentos de R31-R32 por SQL de solo lectura.
- `publicar-diccionario` (lo autoriza el humano), reiniciar el MCP (cachea el
  diccionario) y las cuatro preguntas de R33. `compras` ya está en la lista
  blanca de `mcp-bbdd`.
- Primera nocturna: segundos de `ingest_raw.conala`, `ingest_raw.auxala` y del
  sub-paso (`python main.py timings`), anotados en `progress/` (R34).
