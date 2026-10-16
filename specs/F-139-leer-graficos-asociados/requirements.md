<!-- specs/F-139-leer-graficos-asociados/requirements.md -->
# F-139 · Que la IA abra el ORIGINAL de los gráficos asociados (rehecha el 2026-10-15)

Mediciones: `progress/spec_F-139.md`. Diseño y decisiones: `design.md`.
**Objetivo fijado por el humano el 2026-10-15** (sustituye a la versión de contraste): «que la
IA pueda localizar el documento/gráfico y lo pueda des-serializar […] ya se encargará ella de
leer o interpretar, ya sea escaneado o vectorizado». No hay extracción ni contraste.

**Decisiones CERRADAS por el humano (no se reabren):**

- **Dónde vive**: en `mcp-bbdd`, una herramienta `abrir_adjunto` que localiza el adjunto por
  el índice `compras.documento_adjuntos` (F-090) y devuelve el original pedido a `sigrid-api`.
  Descartado `facturas` y el contraste.
- **Sin caché en SharePoint**: medido, abrir cuesta mediana 0,20 s, media 0,41 s, máx. 4,3 s
  (~1 MB/s). Si en producción el tiempo cambia, se revisa.
- **Sin tope de tamaño**, con AVISO a la IA por encima de 20 MB (hoy 17 ficheros de 199.051).
- **Sin conversión**: se entrega el original tal cual; convertir `.doc`/`.xls` es F-142.
- **Permisos**: abre el adjunto quien pueda leer la tabla de origen del documento al que
  cuelga. Hoy estándar y total leen las cinco, así que los dos abren todo; la regla importa
  para el perfil restringido (F-141).
- **HTTP 500 con nombres no ASCII**: sigue como propuesta a `sigrid-api`
  (design §6); mientras, `filename_columns: ["cod"]`.
- **D1 · El índice sigue la misma regla** (humano, 2026-10-15: «el que tenga acceso a la tabla
  puede acceder a la de los gráficos o su cabecera; si no, no»): las filas de
  `compras.documento_adjuntos` de una familia (nombre, quién lo subió…) solo las ve quien lee
  la tabla de origen de esa familia. Hoy no cambia nada; lo implementa F-141.
- **D2 · Tiene que funcionar con ChatGPT** (humano, 2026-10-15): la herramienta no es solo
  para Claude; mismo tratamiento que el resto del datamart, por escrito en el contrato.

Dos bloques: **R** (este repositorio, documental, con tests) y **H** (el pliego de la
herramienta para `mcp-bbdd`: se implementa y se prueba allí; aquí queda escrito en el
contrato de `azure-apps`, R8).

## A · En este repositorio

R1. La ficha de `compras.documento_adjuntos` (`config/diccionario/compras.yaml`) debe decir
que `documents/read` se pide con `filename_columns: ["cod"]` y que sin ello `sigrid-api`
responde HTTP 500 a los nombres documentales no ASCII: 11.262 de 199.032 enlaces (5,7 %),
medido el 2026-10-15.

R2. La ficha debe declarar el límite: el datamart publica el ÍNDICE y no el fichero; la
apertura del original es de `mcp-bbdd` (F-139) y se entrega sin convertir. MIENTRAS esa
herramienta no esté desplegada, la ficha no debe afirmar que exista.

R3. La ficha debe declarar la regla de permisos con la tabla de origen de cada familia:
FACTURA → `compras.facturas.factura_id`, CONTRATO → `compras.contratos.contrato_id`,
COMPARATIVO → `compras.comparativos.comparativo_id`, OFERTA →
`compras.comparativo_ofertas.oferta_id`, ALBARAN → `compras.albaranes.albaran_id`; y la
regla del propio índice (D1): sus filas de una familia solo las ve quien lee la tabla de
origen de esa familia, a aplicar por F-141 (vistas por familia o RLS, lo que ella decida).

R4. La ficha debe declarar los ficheros grandes: 17 pasan de 20 MB (facturas 8, contratos 4,
ofertas 4, comparativos 1), ninguno de 50 MB, máximo 47 MB; y que 305 enlaces de ofertas
(1,4 %) no tienen fila en `compras.comparativo_ofertas`.

R5. CUANDO cambie el diccionario por R1-R4, `version` de `config/diccionario/00_global.yaml`
debe subir en una unidad respecto a la de `main`.

R6. `docs/ARCHITECTURE.md`, en el punto del índice de adjuntos (F-090), debe declarar el
límite (R2), el aviso de `filename_columns` (R1) y la regla de permisos (R3).

R7. Ningún módulo de `etl_sigrid/` ni `main.py` debe importar una librería de lectura de
documentos o de IA (`pypdf`, `pdfplumber`, `fitz`, `pdfminer`, `openpyxl`, `docx`,
`pytesseract`, `anthropic`, `openai`, `google.genai`, `google.generativeai`). SI alguno lo
importa, ENTONCES el test debe fallar nombrando módulo y librería. **Excepción única (humano,
2026-10-15, opción A)**: `etl_sigrid/application/steps/load_excel_aux_step.py` puede importar
`openpyxl` (F-004: los Excels de configuración de Negocio, no adjuntos); SI ese fichero
desaparece o deja de importarla, ENTONCES un test de control debe fallar diciendo que sobra.

R8. El documento de este proyecto en `azure-apps` (`datamart_seg_anual.md`) debe recoger el
contrato con `mcp-bbdd` (H1-H13, la regla de R3 y «qué se rompe si cambia»: las columnas del
índice y las cinco tablas y claves de origen). Verificación MANUAL: otro repositorio, commit
local allí.

R9. Las cinco tablas y columnas de origen de R3 deben existir en el diccionario y figurar en
`relaciones` de la ficha del índice. SI se renombra una, ENTONCES el test debe fallar
recordando que rompe el contrato de R8.

R10. CUANDO R1-R9 estén aprobados por el reviewer, `harness/features.json` debe dejar F-139
en `blocked` con el motivo «la herramienta vive en `mcp-bbdd`: pliego H1-H13 en
`azure-apps/datamart_seg_anual.md`».

## B · Pliego de la herramienta para `mcp-bbdd` (H1-H13; se prueban allí)

H1. El servidor debe exponer `abrir_adjunto(adjunto_id)`; el `adjunto_id` lo localiza la IA
antes con `consultar` sobre `compras.documento_adjuntos`.

H2. CUANDO se llame, el servidor debe leer la fila del índice con el login del perfil de
quien pregunta; SI no existe, ENTONCES debe responder `NO_ENCONTRADO` sin llamar a
`sigrid-api`.

H3. Antes de pedir el fichero, el servidor debe consultar, con el login del perfil, la tabla
de origen de la familia (R3) con un `LEFT JOIN` que lea una columna suya (para que el
planificador no lo elimine); SI PostgreSQL deniega, ENTONCES debe responder
`PERMISO_DENEGADO` sin llamar a `sigrid-api`. El permiso lo decide la base, no el servidor.

H4. SI el documento no tiene fila en su tabla de origen (las 305 ofertas) y el perfil sí lee
esa tabla, ENTONCES el servidor debe entregar el fichero con un aviso.

H5. El servidor debe pedir el fichero con `documents/read` (`database: ruesma_rep`,
`table: gra`, `id_column: cod`, `id_value` = `cod_repositorio`, `blob_column: ima`,
`filename_columns: ["cod"]`), con plazo por debajo de los 230 s del balanceador.

H6. El servidor debe entregar el ORIGINAL sin convertir: las imágenes como contenido de imagen
y el resto como recurso incrustado con su tipo MIME (por la extensión cuando `sigrid-api`
devuelva `application/octet-stream`), más un texto con familia, documento, nombre,
extensión y tamaño.

H7. SI el fichero pasa de 20 MB, ENTONCES el servidor debe entregarlo igual y avisar a la IA
del tamaño.

H8. SI la extensión es de un formato binario antiguo (`.doc`, `.xls`, `.msg`), ENTONCES el
servidor debe avisar de que la IA puede no leerlo y de que la conversión es F-142.

H9. SI `sigrid-api` no devuelve binario (0,23 % de los enlaces) o no responde, ENTONCES el
servidor debe responder `SIN_BINARIO` u `ORIGEN_NO_DISPONIBLE`, nunca un fichero vacío.

H10. Cada apertura debe quedar en la traza: identidad, perfil, `adjunto_id`, familia, bytes y
resultado; nunca el contenido.

H11. El servidor no debe guardar el binario en disco, base ni caché más allá de la respuesta.

H12. La clave de `sigrid-api` debe ir al vault de `mcp-bbdd` por referencia, y la herramienta
solo debe usar `documents/read`.

H13. Antes de desplegar, `mcp-bbdd` debe verificar, con claude.ai Y con ChatGPT (y Codex),
que el cliente entrega al modelo el original devuelto por la herramienta (PDF e imagen); SI
el recurso incrustado en base64 no vale para alguno, ENTONCES `mcp-bbdd` debe resolverlo
(p. ej. un enlace temporal) y llevar la solución al humano: la herramienta no puede quedar
solo para Claude (D2).

## C · Fuera de alcance

Extraer o contrastar el contenido; convertir formatos (F-142); caché en SharePoint; el perfil
restringido (F-141); arreglar el 500 en `sigrid-api`; abrir desde el portal.
