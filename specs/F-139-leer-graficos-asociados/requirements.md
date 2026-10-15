<!-- specs/F-139-leer-graficos-asociados/requirements.md -->
# F-139 · Leer el contenido de los gráficos asociados (facturas, ofertas, contratos)

**Spec de DECISIÓN.** Mediciones: `progress/spec_F-139.md`. Diseño, opciones y D1-D7:
`design.md` (§1 y §8). **Los requisitos siguen la opción recomendada**: la lectura y el
contraste NO viven en este ETL sino en el proyecto `facturas` (opción B), empezando solo
por facturas desde 2025 y con un piloto. Si el humano elige otra opción en D1, esta spec se
rehace; no se adelanta trabajo de ninguna.

Tres bloques:

- **R1-R6**: lo que SÍ se hace en este repositorio (dejar escrito el límite, corregir lo
  que la medición destapó en la ficha y dejar la feature `blocked` con la propuesta).
- **P1-P11**: la PROPUESTA para el dueño (`facturas`). No se implementan ni se prueban
  aquí: son el pliego que el humano lleva a ese repositorio, en EARS para que su
  spec-author los pueda adoptar tal cual.
- **Fuera de alcance**, al final.

## A · En este repositorio

R1. La ficha de `compras.documento_adjuntos` (`config/diccionario/compras.yaml`) debe
decir que `documents/read` se pide con `filename_columns: ["cod"]` y que, sin ello,
`sigrid-api` responde **HTTP 500** a los ficheros cuyo nombre documental tiene caracteres
no ASCII: **11.262 de 199.032 enlaces de compras (5,7 %)** medidos el 2026-10-15.

R2. La ficha de `compras.documento_adjuntos` debe declarar, en su descripción, que el
CONTENIDO de los ficheros no se lee en el datamart y dónde vive su lectura según lo que
decida D1 (por defecto, el proyecto `facturas`), sin afirmar nada que no esté hecho.

R3. CUANDO cambie el contenido del diccionario por R1-R2, `version` de
`config/diccionario/00_global.yaml` debe subir en una unidad respecto a la de `main`.

R4. `docs/ARCHITECTURE.md`, en el punto del índice de adjuntos (F-090), debe declarar el
límite: este ETL publica el ÍNDICE y no lee ni el binario ni su contenido; la lectura del
contenido es de otro proyecto (F-139, D1), y el aviso de `filename_columns`.

R5. Ningún módulo de `etl_sigrid/` ni `main.py` debe importar una librería de lectura de
documentos o de IA (`pypdf`, `pdfplumber`, `fitz`, `pdfminer`, `openpyxl`, `docx`,
`pytesseract`, `anthropic`, `openai`, `google.genai`, `google.generativeai`): es la guarda
ejecutable del límite. SI alguno lo importa, ENTONCES el test debe fallar nombrando el
módulo y la librería.

R6. CUANDO el humano apruebe la spec con D1 = B, `harness/features.json` debe dejar F-139
en `blocked` con el motivo «vive en `facturas`: propuesta P1-P11 en
`specs/F-139-leer-graficos-asociados/requirements.md`», sin cambiar su `acceptance`.

R7. El documento de este proyecto en `azure-apps` (`datamart_seg_anual.md`, del que somos
dueños) debe recoger R1 y R4 en el mismo trabajo (verificación MANUAL: es otro
repositorio; commit local allí, sin push).

## B · Propuesta para `facturas` (P1-P11; se prueban allí, no aquí)

P1. El sistema debe tomar la lista de facturas a contrastar del ÍNDICE publicado por el
datamart (`compras.documento_adjuntos`, `familia = 'FACTURA'`), en una consulta agregada
de solo lectura como la que ya hace contra `maestro.obras`, limitada a `fecha_alta` desde
la fecha que fije D4.

P2. CUANDO descargue un fichero, el sistema debe pedirlo a `sigrid-api` con
`documents/read` (`database: ruesma_rep`, `table: gra`, `id_column: cod`,
`id_value = cod_repositorio`, `blob_column: ima`, `filename_columns: ["cod"]`), en serie,
con un plazo por petición por debajo de los 230 s del balanceador.

P3. SI el fichero supera el tope de tamaño configurado (propuesto 10 MB: deja fuera 360
de 133.964 ficheros de factura), ENTONCES el sistema no debe descargarlo y debe dejarlo
anotado como `FUERA_DE_TOPE`.

P4. El sistema no debe guardar el binario en ninguna base (su guardián de DDL ya prohíbe
`bytea` y `oid`) ni dejarlo en disco al terminar cada fichero.

P5. CUANDO un adjunto (`adjunto_id`) ya tenga un contraste vigente con la misma huella
`sha256` del fichero, el sistema no debe volver a leerlo ni volver a pagar la IA
(incremental).

P6. CUANDO una factura tenga varios ficheros (el 22 % de las que tienen adjunto), el
sistema debe clasificar cada uno (factura, albarán u otro) antes de contrastar, y SI
ninguno es la factura, ENTONCES debe marcarla `SIN_ORIGINAL` en vez de contrastar otro
documento.

P7. El sistema debe extraer cabecera y líneas con su cadena actual (F-024, F-050), igual
para PDF con texto que para escaneados e imágenes (27 % de las facturas PDF de 2025-26
son escaneadas).

P8. El sistema debe leer lo REGISTRADO de cada factura (número del proveedor, CIF, fecha,
base, cuota de IVA, total y líneas con cantidad, precio e importe), por la fuente que
decida D3 (recomendada: `compras.facturas` y `compras.factura_lineas` del datamart,
respetando que los abonos ya van con signo negativo).

P9. El sistema debe publicar, por factura, el contraste original contra registrado con
cada discrepancia: campo, cifra leída, cifra registrada, diferencia y tolerancia aplicada
(versionada), y un estado (`CUADRA`, `DESCUADRA`, `SIN_ORIGINAL`, `ILEGIBLE`,
`FUERA_DE_TOPE`, `FALLO_PROVEEDOR`); sin decidir cuáles son legítimas.

P10. MIENTRAS `IA_DRY_RUN` esté activo, el sistema no debe llamar a ningún modelo; en
todo caso debe registrar el coste estimado y el medido por factura y por lote, con un
tope de facturas por ejecución.

P11. El sistema no debe enviar al modelo más de lo que ya envía hoy en la extracción
(F-004): el PDF de la factura. Los contratos (NIF de firmantes en 3 de 12 de la muestra)
quedan fuera mientras D2 no los incluya.

## C · Fuera de alcance (escrito para que nadie lo dé por hecho)

- Leer contenido en este ETL, replicar binarios en el Postgres compartido o ingerir aquí
  el resultado del contraste: si Negocio lo quiere por el MCP, es una feature posterior
  (D5) con su propia spec.
- Contratos y ofertas: fuera en esta fase (D2). Los contratos son 47 % Word 97 binario y
  sus PDF salen en buena parte de una impresión de aplicación; el Excel del concurso de las
  ofertas va con F-129.
- Arreglar el HTTP 500 de `documents/read` con nombres no ASCII: es de `sigrid-api`
  (D6); aquí solo se avisa en la ficha (R1).
- Abrir el fichero desde el MCP o el portal (ya fuera desde F-090).
