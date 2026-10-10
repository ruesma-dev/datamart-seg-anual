<!-- specs/F-090-documento-adjunto/design.md -->
# F-090 · Diseño: el índice de documentos adjuntos

Mediciones que sostienen cada cifra: `progress/spec_F-090.md`.

## Encaje y límite del servicio

- **Ingesta**: dos tablas más en `raw` (`gra`, `rcg`) por la vía de siempre
  (`ingest_raw` + `tables_sigrid.yaml`), filtradas en origen. Ni paso nuevo ni
  cliente nuevo: `stream_table` ya compone `WHERE [ide] > ? AND (<where>)`, y
  `check-raw-recuentos` cuenta con el mismo `where`.
- **Negocio**: una tabla en el módulo `compras` (`build_compras`, sub-paso 14).
  Solo lee `raw`. No toca `stg`, `mart`, `cierre` ni ningún objeto existente.
- **LÍMITE DE RESPONSABILIDAD**: el datamart publica el ÍNDICE (metadatos). El
  BINARIO vive en `ruesma_rep` y lo sirve `sigrid-api` (`documents/read`); no
  se replica en `psql-albaranes-rs9k2` (compras suma ~81 GB, media ~420 KB,
  máximo 47 MB por fichero; el disco es de 64 GB y el cómputo va justo).
  Abrir el fichero desde el MCP (`mcp-bbdd`) o un portal (`portal`), y poner
  nombre a los 31.720 documentos sin `nom` en el documental (`sigrid-api`), son
  trabajo de esos proyectos y no se diseñan aquí.

## Ficheros a crear

| Ruta | Qué |
|---|---|
| `etl_sigrid/domain/documento_adjuntos.py` | Oráculo puro: familias, clases por extensión, `extension()`, `clase_fichero()`, columnas excluidas de `gra` |
| `etl_sigrid/infrastructure/postgres/sql/compras/14_documento_adjuntos.sql` | `compras.documento_adjuntos` |
| `tests/test_f090_dominio.py` | R7-R10 |
| `tests/test_f090_ingesta_sql.py` | R1-R6, R11-R18 sobre el TEXTO del YAML y del SQL (no se ejecuta SQL: Postgres compartido) |
| `tests/test_f090_diccionario.py` | R19-R25 |

## Ficheros a modificar

| Ruta | Cambio |
|---|---|
| `config/tables_sigrid.yaml` | + `rcg` y + `gra` al final, con su comentario (medición, motivo de cada exclusión, D2) |
| `etl_sigrid/application/steps/build_compras_step.py` | + `_SubStep("documento_adjuntos", "14_documento_adjuntos.sql", "compras", "documento_adjuntos")` detrás de `estado_documentos`, y la línea del docstring |
| `config/diccionario/compras.yaml` | ficha `documento_adjuntos` (R19-R23) y una línea en las relaciones de `facturas`, `contratos`, `comparativos`, `comparativo_ofertas` y `albaranes` que apunte al índice |
| `config/diccionario/raw.yaml` | fichas `gra` y `rcg` (capa origen, `consumo_recomendado: false`); «Son 74 tablas» |
| `config/diccionario/00_global.yaml` | `version: 47` con su nota (F-090), «las 74 tablas»; corregir cualquier frase que diga que el adjunto no existe |
| `docs/ARCHITECTURE.md` | § «Qué se copia de Sigrid»: 74 tablas, `gra`/`rcg` filtradas, y que el binario está en `ruesma_rep` |
| `tests/test_f085_sql.py`, `tests/test_f085_diccionario.py`, `tests/test_f095_retenciones_contables.py` | el censo fijado en 72 pasa a 74 (asserts y textos buscados); nada más |
| `C:\Users\pgris\PycharmProjects\azure-apps\datamart_seg_anual.md` (otro repo, commit propio allí) | «Qué consume»: 74 tablas, `gra`/`rcg`; «Qué expone»: `compras.documento_adjuntos`; abrir = `sigrid-api` |

## Ficheros que NO se tocan

- `sql/compras/01_documentos.sql` (`compras.facturas`, `contratos`, `albaranes`):
  D6. Los consume Power BI y F-132 está trabajando en `compras` en paralelo.
- `sql/compras/08_comparativos.sql`, `11_`, `12_`, `13_`: el índice los cruza
  por `documento_id`/`comparativo_id`, no los cambia.
- `infrastructure/sigrid/sigrid_api_client.py` e `ingest_raw_step.py`: el
  `where` ya basta. Ningún acceso a `ruesma_rep` desde el ETL.
- `config/settings.py` (`PG_EXCLUDED_TABLES`): con el filtro de D2, `raw.gra`
  solo lleva adjuntos de compras y puede leerla el MCP como el resto de `raw`.
- `config/objetos_pendientes.yaml`: el objeto nuevo lo construye `run-all`.

## Dominio · `etl_sigrid/domain/documento_adjuntos.py`

```python
FAMILIAS_ADJUNTOS: Final[dict[int, str]] = {
    15: "FACTURA", 44: "CONTRATO", 46: "COMPARATIVO", 12: "OFERTA", 14: "ALBARAN"}
EXTENSIONES_POR_CLASE: Final[dict[str, frozenset[str]]] = {
    "PDF": {"pdf"}, "EXCEL": {"xls","xlsx","xlsm","xlsb","csv"},
    "WORD": {"doc","docx","rtf","odt"}, "CORREO": {"msg","eml"},
    "IMAGEN": {"jpg","jpeg","png","tif","tiff","gif","bmp"}}
CLASE_OTRO, CLASE_SIN_EXTENSION = "OTRO", "SIN_EXTENSION"
COLUMNAS_EXCLUIDAS_GRA: Final[frozenset[str]] = frozenset({"ima","pul","tex","cam"})
def extension(nombre: str | None) -> str | None: ...
def clase_fichero(nombre: str | None) -> str: ...
def filtro_rcg() -> str: ...   # el `where` exacto de rcg, construido de FAMILIAS
def filtro_gra() -> str: ...   # el `where` exacto de gra
```

`filtro_rcg()`/`filtro_gra()` devuelven el literal que debe llevar el YAML; el
test compara `tables_sigrid.yaml` contra ellos (R3). La lista de familias
ordenada (`12, 14, 15, 44, 46`) para que el literal sea determinista.

## Ingesta · `config/tables_sigrid.yaml`

```yaml
  - source_table: rcg
    target_table: rcg
    id_column: ide
    incremental_column: null   # no tiene tiemod
    where: "con IN (SELECT ide FROM dbo.con WHERE tip IN (12, 14, 15, 44, 46))"
    exclude_columns: []
  - source_table: gra
    target_table: gra
    id_column: ide
    incremental_column: null   # no tiene tiemod
    where: "ide IN (SELECT r.gra FROM dbo.rcg r JOIN dbo.con c ON c.ide = r.con WHERE c.tip IN (12, 14, 15, 44, 46))"
    exclude_columns: [ima, pul, tex, cam]   # uno por línea, con su motivo
```

Medido el 2026-10-09 por la pasarela, a 10.000 filas por página: `rcg` 199.042
filas en 20 páginas, **7,2 s**; `gra` 199.042 filas en 20 páginas, **41,5 s**
(~1,6 s por página: la subconsulta se repite en cada una). Unos 46 MB de JSON.
Con la escritura en Postgres, **~1-2 min** sobre una nocturna de 4 h 39 min
(`rac`, 2,5 M filas, cuesta 132 s). `gra` va DETRÁS de `rcg` en el YAML: así un
enlace nuevo durante la noche trae su gráfico (la guarda R15 cubre el resto).

## SQL · `sql/compras/14_documento_adjuntos.sql`

Cabecera: qué construye, de qué lee (`raw.rcg`, `raw.gra`, `raw.con`,
`raw.comprv`, `compras.fn_sigrid_date`), que no hay binario y por qué.

```sql
DO $$ ... -- R15: guarda de huérfanos
  SELECT count(*) FILTER (WHERE g.ide IS NULL), count(*) INTO v_huerf, v_total
  FROM raw.rcg r JOIN raw.con c ON c.ide = r.con AND c.tip IN (12, 14, 15, 44, 46)
  LEFT JOIN raw.gra g ON g.ide = r.gra;
  IF v_total > 0 AND v_huerf > v_total * 0.01 THEN
     RAISE EXCEPTION 'F-090 R15: % de % enlaces de raw.rcg sin su grafico en raw.gra ...', v_huerf, v_total;
$$;
DROP TABLE IF EXISTS compras.documento_adjuntos CASCADE;
CREATE TABLE compras.documento_adjuntos AS
SELECT r.ide AS adjunto_id, r.con AS documento_id, c.tip AS tipo_documento_codigo,
       CASE c.tip WHEN 15 THEN 'FACTURA' ... END AS familia, c.cod AS codigo_documento,
       CASE c.tip WHEN 46 THEN r.con WHEN 12 THEN p.comide END AS comparativo_id,
       g.ide AS grafico_id, g.cod AS cod_repositorio, g.emp AS empresa_repositorio,
       NULLIF(BTRIM(g.nom), '') AS nombre_fichero, <extension> AS extension,
       <CASE por extensión> AS clase_fichero, NULLIF(BTRIM(g.res), '') AS descripcion,
       compras.fn_sigrid_date(g.fec) AS fecha_alta, NULLIF(BTRIM(g.usu), '') AS subido_por,
       r.pos AS posicion
FROM raw.rcg r
JOIN raw.con c ON c.ide = r.con AND c.tip IN (12, 14, 15, 44, 46)
JOIN raw.gra g ON g.ide = r.gra
LEFT JOIN raw.comprv p ON p.docide = r.con AND c.tip = 12;
ALTER TABLE compras.documento_adjuntos ADD PRIMARY KEY (adjunto_id);
CREATE INDEX ON compras.documento_adjuntos (documento_id);
CREATE INDEX ON compras.documento_adjuntos (comparativo_id);
```

- `<extension>`: `lower(substring(btrim(g.nom) from '\.([^.\s]+)$'))`, el mismo
  criterio que `extension()` del dominio (último punto; nada si acaba en punto).
- `<CASE>`: `WHEN ext IN ('pdf') THEN 'PDF' WHEN ext IN ('xls', ...) THEN
  'EXCEL' ... WHEN ext IS NULL THEN 'SIN_EXTENSION' ELSE 'OTRO'`. El test extrae
  cada lista del texto y la compara con `EXTENSIONES_POR_CLASE`.
- **Unión a `comprv`**: `docide` es único en `comprv` (medido: 0 repetidos),
  así que el `LEFT JOIN` no multiplica. El grano lo defiende la PK.
- **Usar `raw.rcg.ide` como clave y no `(documento, gráfico)`**: 102 gráficos
  cuelgan de varios documentos; el enlace sí es único.
- `fecha_alta` es la de `gra.fec` (AAAAMMDD): `rcg.fecalt` está a 0 en el
  99,98 % de los enlaces de compras y no sirve.

## Diccionario

Ficha `compras.documento_adjuntos` con el patrón de `documento_procesos`
(`tipo`, `capa: consumo`, `consumo_recomendado: true`, `descripcion`, `grano`,
`clave_negocio: [adjunto_id]`, `paso_etl: build_compras`, `refresco: nocturno`,
`columnas`, `relaciones`, `ejemplos_preguntas`). La descripción lleva, en este
orden: qué es (el índice de «Gráficos asociados»), la cobertura por familia
(R19) y la regla de la ausencia (R20), dónde está el fichero y cómo se pide
(R21: `ruesma_rep`; `cod_repositorio` es la clave de `documents/read`), la
clase por extensión (R22) y el dato personal (R23). Sin procedimientos de
negocio (CONVENTIONS: el diccionario dice lo que el dato ES).
`ejemplos_preguntas` cubre las tres de R27. Fichas `raw.gra` y `raw.rcg` con el
formato de `raw.rac` (motivo de no consumo, filtro, exclusiones, puntero a
`azure-apps/sigrid_tablas.md`).

## Riesgos y decisiones

- **Filtrar en origen (D2)**. Sin filtro, `raw` traería 90.409 enlaces más, de
  ellos 44.398 de personal (`con.tip` 43 empleados y 306 nóminas: clases «DNI»,
  «Nómina», «EMBARGOS», «JUZGADO FAMILIA») a una capa que el MCP lee. Alternativa
  descartada salvo que el humano la elija: traerlas enteras y revocarlas con
  `PG_EXCLUDED_TABLES` (F-068). El filtro encarece cada página de `gra` (la
  subconsulta se repite: ~1,6 s por página frente a 0,4 s de `rcg`).
- **Sin `auxgra` (D4)**: `gratipide` = 0 en los 199.042 enlaces de compras; el
  «tipo» que pide Juan es la clase por extensión. Su catálogo es de RR. HH.
- **Sin marca de binario (D5)**: 461 enlaces de compras (0,23 %) no tienen fila
  en `ruesma_rep`. Comprobarlo exigiría leer otra base cada noche; se declara.
- **`cod` duplicado**: en `ruesma.gra` hay 1 `cod` en dos empresas; en
  `ruesma_rep.gra` el `cod` es único (364.906 / 364.906). Se publican los dos
  campos (`cod_repositorio`, `empresa_repositorio`) y la ficha dice que el
  documental casa por la pareja.
- **Fechas imposibles**: 2 enlaces con `fec` en 2250; `fn_sigrid_date` las
  convierte (son fechas válidas). Se declaran, no se corrigen.
- **Conflicto con F-132**: F-132 (fase B) puede tocar `build_compras_step.py`,
  `00_global.yaml` (versión) y los tests del censo. Al integrar, el que llegue
  segundo rebasa y re-numera la `version`; el sub-paso 14 no choca con sus
  ficheros (F-132 no crea `14_`).
- **Coste**: ~1-2 min por noche; la nocturna ya va 39 min por encima de las 4 h.
  Se mide en la primera noche (R28).
