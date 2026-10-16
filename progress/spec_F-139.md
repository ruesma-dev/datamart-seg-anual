<!-- progress/spec_F-139.md -->
# F-139 · Mediciones de la spec (spec-author, 2026-10-15; rehecha el mismo día)

Todo en SOLO LECTURA: Azure con `filas_solo_lectura` y `_bootstrap_done = True`;
Sigrid por `sigrid-api` (`sql/read`, todas las respuestas `truncated: false`) y
81 llamadas a `documents/read` (+ 6 reintentos). Los ficheros se bajaron al
scratchpad de la sesión, se analizaron en local y **se borraron al terminar**.
Aquí solo hay agregados: ningún código de repositorio, nombre, importe ni NIF.
Spec: `specs/F-139-leer-graficos-asociados/`.

## 1 · El ecosistema ya lee PDF de compras, y no desde un ETL

Leído `azure-apps/` (README, `facturas.md`, `sigrid_api.md`, `mcp_bbdd.md`,
`albaranes.md`, `postventa_incidencias.md`) y el backlog de `facturas`:

- **`facturas` ya hace la mitad de F-139 para las facturas que llegan por correo**:
  extrae el PDF con IA (F-004, F-024 esquema completo, F-039 todas las líneas,
  F-050 el PDF va como PDF, F-053 tabla leída sin IA en proformas), lee Sigrid por
  `sigrid-api` (F-010: albaranes, proforma y líneas `dcapro`) y CONCILIA línea a
  línea con discrepancias, tolerancias y coste medido (F-011, 2026-10-13). Base
  propia `facturas` con `bytea` prohibido. En local, sin desplegar (F-008).
  Lo que NO hace: leer el archivo histórico de `ruesma_rep` ni contrastar contra la
  factura YA REGISTRADA en Sigrid (concilia contra sus orígenes).
- `albaranes` y `postventa-incidencias` también leen documentos con IA (Gemini y
  otros). **Ningún ETL del ecosistema lo hace**; este repositorio no tiene ni una
  librería de PDF ni un SDK de IA.
- `contratos` (local, plugin) lee contratos PDF/Word para su análisis jurídico, no
  para contrastarlos con Sigrid. `descarga-factura` (local, 2026-05) baja PDF de
  facturas por `sigrid-api`; no está en `azure-apps/`.
- `sigrid-api` es pasarela sin lógica de negocio; `mcp-bbdd` solo lee `sigrid_dm`.

## 2 · El índice en Azure (`compras.documento_adjuntos`, 199.432 filas)

| Familia | Ficheros por clase |
|---|---|
| FACTURA | PDF 133.389 · imagen 315 · correo 240 · Excel 38 · Word 33 · otros 32 |
| CONTRATO | PDF 20.289 · Word 17.832 (`.doc` 17.233, `.docx` 599) · otros 48 |
| OFERTA | PDF 20.134 · Excel 1.226 (`.xlsx` 975, `.xls` 250) · Word 394 · correo 234 · otros 86 |

Ficheros por documento (1 / 2 / 3 / 4 / ≥5): facturas 81.010 / **21.906** / 1.459 /
340 / 475; contratos 9.221 / 2.270 / 3.718 / 1.293 / 1.174; ofertas 15.743 / 2.040 /
398 / 136 / 81. **El 22 % de las facturas con adjunto tiene más de un fichero**, y el
nombre no dice cuál es la factura: 112.486 de 133.964 nombres no llevan ni «factura»
ni «albarán»; quien lea tiene que clasificar cada fichero.

Altas por año (factura / contrato / oferta): 2023 17.464 / 4.693 / 2.418 · 2024
19.805 / 4.605 / 2.525 · 2025 19.660 / 4.406 / 2.465 · 2026 (a 15-10) 19.250 / 4.001
/ 1.754. Septiembre de 2026: 1.938 / 579 / 253 → **~130 ficheros por día laborable**.

## 3 · Tamaño del binario (`ruesma_rep`, por `(emp, cod)`), las tres familias

| Familia | <100 KB | 100-500 KB | 0,5-2 MB | 2-10 MB | >10 MB | Total |
|---|---|---|---|---|---|---|
| Factura (15) | 35.645 | 73.640 | 21.578 | 2.741 | 360 | ~54,8 GB |
| Contrato (44) | 12.409 | 13.482 | 11.046 | 935 | 90 | ~17,5 GB |
| Oferta (12) | 6.612 | 10.811 | 4.070 | 464 | 31 | ~8,7 GB |

Desde 2025: facturas 38.953 ficheros / ~15 GB; contratos 8.422 / ~4,3 GB; ofertas
4.222 / ~1,9 GB. Ritmo de 2026: facturas ~1.900-2.100 ficheros y ~0,7-1 GB al mes.

## 4 · Descarga de la muestra (81 ficheros, deterministas por `md5(adjunto_id)`)

Muestra: 30 facturas PDF 2025-26, 10 facturas PDF 2019-21, 3 facturas imagen, 12
contratos PDF y 6 Word 2024-26, 15 ofertas PDF 2024-26 y 5 Excel 2022-26.

- 75 a la primera, **6 con HTTP 500**. Los 6 tienen el nombre documental con
  caracteres no ASCII (tildes, eñes) y **ninguno de los 75 buenos los tiene**.
  Con `filename_columns: ["cod"]` los 6 dan 200 con los bytes exactos
  (= `DATALENGTH`). Causa, leída en el código de `sigrid-api`
  (`http_response_factory.binary_file_response`): la cabecera `X-Document-Filename`
  lleva el nombre SIN codificar (el `Content-Disposition` sí va codificado).
  **Alcance: 11.262 de 199.032 enlaces de compras (5,7 %)** — facturas 7.226,
  ofertas 2.365, contratos 1.237, comparativos 421, albaranes 13. La ficha de
  `compras.documento_adjuntos` explica cómo pedir el fichero y no lo avisa.
- Tiempo: media 0,41 s, mediana 0,20 s, máximo 4,3 s; 32,2 MB a **~1 MB/s** en
  serie. A ese ritmo: el día (~130 ficheros, ~50 MB) ≈ 1 min; desde 2025 (~21 GB)
  ≈ 6 h; las tres familias enteras (~81 GB) ≈ 23 h.

## 5 · Qué traen los ficheros (análisis local con `pypdf`, sin red)

| Grupo | Con capa de texto | Escaneado | Otro |
|---|---|---|---|
| Factura PDF 2025-26 (30) | 22 (73 %) | **8 (27 %)** | — |
| Factura PDF 2019-21 (10) | 4 | **6** | — |
| Factura imagen (3) | — | — | 3 JPG/PNG: solo OCR |
| Contrato PDF (12) | 12 | 0 | 5 generados con iText (¿la impresión de Sigrid? sin verificar) |
| Contrato Word (6) | — | — | 6 `.doc` binario de Word 97: hace falta convertidor |
| Oferta PDF (15) | 13 | 1 (+1 mixto) | — |
| Oferta Excel (5) | — | — | 4 `.xlsx` legibles (1-10 hojas, 47-3.414 celdas); 1 `.xls` binario |

Páginas: facturas 1,4 de media (máx. 4); ofertas 3,4 (máx. 13); contratos 4,6 (máx. 20).
Productores: escáneres de oficina (Ricoh, Konica), Microsoft, generadores de ERP de
proveedores; ninguna plantilla domina.

**Contraste de las 26 facturas con texto contra lo registrado** (`compras.facturas` +
`compras.factura_lineas`): ¿aparece en el texto la cifra registrada, en cualquiera de
sus formatos?

| Dato registrado | Aparece |
|---|---|
| Número del proveedor (`referencia_proveedor`, normalizado) | 21 / 26 |
| CIF del proveedor | 18 / 26 |
| Base (Σ `importe`) | 23 / 26 |
| Total (base + Σ `cuota_iva`) | 20 / 26 (base y total a la vez 18; ninguno 1) |
| Importe de cada línea | 137 / 185 líneas; todas las líneas en 19 / 26 facturas |

Es una COTA SUPERIOR: que la cifra esté en el texto no dice cuál de los números es la
base o el total. Sacarlos de forma fiable exige entender la maqueta de cada proveedor
(plantillas por proveedor o un modelo, como hace `facturas`), y además el 27 % de las
recientes es escaneado. Las diferencias (total 6/26, líneas 26 %) mezclan retenciones,
IVA no repercutido, agrupación de líneas y posibles discrepancias reales: separarlas
es justo el trabajo del contraste, y no se puede hacer con búsqueda de cadenas.

## 6 · Datos personales (solo recuentos sobre los PDF con texto)

Contratos: 3 de 12 con un NIF de persona física y la palabra «DNI» (firmantes,
autónomos). Facturas: IBAN en 11 de 26; un «DNI» en 1. Ofertas: «DNI» en 2 de 14.
Las facturas ya viajan hoy a un proveedor de IA en `facturas` (mismo tipo de dato);
los contratos serían una categoría nueva.

## 7 · Conclusión de la PRIMERA versión (descartada por el humano el 2026-10-15)

La primera versión (commit `52ac5bf`) recomendaba contrastar en `facturas`. El humano cambió
el objetivo: la IA abre el ORIGINAL por `mcp-bbdd` y lo interpreta ella; sin extracción, sin
contraste, sin conversión. Las §1, §2, §5 y §6 siguen siendo mediciones válidas; la §5
(contraste) queda solo como dato de por qué el contenido lo interpreta la IA.

## 8 · Mediciones de la versión rehecha (2026-10-15, solo lectura)

**Ficheros de más de 20 MB** (`ruesma_rep`, por `(emp, cod)`, cinco familias de compras):

| Familia | Enlaces | > 20 MB | > 50 MB | Máx. MB | > 20 MB desde 2025 |
|---|---|---|---|---|---|
| Oferta (12) | 21.988 | 4 | 0 | 24 | 1 |
| Albarán (14) | 690 | 0 | 0 | 2 | 0 |
| Factura (15) | 133.980 | 8 | 0 | 32 | 4 |
| Contrato (44) | 37.965 | 4 | 0 | 47 | 0 |
| Comparativo (46) | 4.428 | 1 | 0 | 45 | 1 |

**17 de 199.051 (0,009 %)**. El máximo de 157 MB de `ruesma_rep` (F-090) no es de compras.
Al ritmo medido (~1 MB/s) el mayor tarda ~47 s: dentro de los 230 s del balanceador.

**Tiempo de apertura** (de §4): mediana 0,20 s, media 0,41 s, máx. 4,3 s. Base de la
decisión de no cachear en SharePoint.

**Enlaces del índice sin fila en su tabla de origen** (Azure): FACTURA 0 de 134.047 en
`compras.facturas`; CONTRATO 0 de 38.169; COMPARATIVO 0 de 4.452; ALBARAN 0 de 690;
**OFERTA 305 de 22.074 (1,4 %) sin fila en `compras.comparativo_ofertas`**. Por eso la
comprobación de permiso es un `LEFT JOIN` (design §2), no un `INNER`.

**Permisos de hoy**: `SELECT` directo de `mcp_sigrid_dm_ro` (estándar) y `sigrid_dm_etl` sobre
`compras.documento_adjuntos` y `compras.facturas`; el total los hereda por pertenencia. Hoy
los dos perfiles abrirían todo.

**`mcp-bbdd` hoy** (`azure-apps/mcp_bbdd.md`, 2026-10-14): siete herramientas, `grafico`
devuelve PNG (las imágenes como resultado ya llegan al modelo); **no consume `sigrid-api`**;
elige el login por perfil y deja que PostgreSQL niegue (`PERMISO_DENEGADO`).

## 9 · Decisiones (todas cerradas; spec APROBADA por el humano el 2026-10-15)

Dónde vive (`mcp-bbdd`), sin caché, sin tope con aviso > 20 MB, sin conversión (F-142),
permisos por tabla de origen, el 500 como propuesta a `sigrid-api`. Y:

- **D1**: «el que tenga acceso a la tabla puede acceder a la de los gráficos o su cabecera; si
  no, no». Las filas del índice de una familia solo las ve quien lee su tabla de origen. Hoy no
  cambia nada; lo aplica F-141 (vistas por familia o RLS).
- **D2**: «tiene que poder funcionar con ChatGPT». Mismo tratamiento que el resto del datamart;
  H13 se verifica también con ChatGPT y, si el base64 incrustado no vale, `mcp-bbdd` lo resuelve.
