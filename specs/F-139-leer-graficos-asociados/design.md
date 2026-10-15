<!-- specs/F-139-leer-graficos-asociados/design.md -->
# F-139 · Diseño: dónde vive la lectura de los gráficos asociados

Mediciones: `progress/spec_F-139.md` (todo en solo lectura el 2026-10-15). Este diseño
decide primero el LÍMITE DE RESPONSABILIDAD (regla dura de `CLAUDE.md`) y, con la opción
recomendada, deja en este repositorio solo documentación y una guarda.

## 1 · Límite de responsabilidad: cinco sitios posibles

Lo que hay que hacer: bajar el fichero de `ruesma_rep`, saber si es la factura o un anexo,
sacar cabecera y líneas (de PDF con texto, escaneados e imágenes), leer lo registrado en
Sigrid y publicar las discrepancias. Lo medido que pesa en la decisión:

- El 27 % de las facturas PDF de 2025-26 es escaneado (6 de 10 en 2019-21): sin OCR o un
  modelo multimodal no hay contraste para una de cada cuatro.
- En las facturas con texto, la cifra registrada APARECE (base 23/26, total 20/26, líneas
  137/185), pero saber cuál número es cuál exige entender la maqueta de cada proveedor:
  no hay plantilla dominante. Es extracción con IA, no un `regexp`.
- El 22 % de las facturas con adjunto tiene varios ficheros y el nombre no dice cuál es.
- Volumen: ~55 GB de facturas (~15 GB desde 2025); ~130 ficheros por día laborable.

| Opción | A favor | En contra |
|---|---|---|
| **A · Este ETL** | Ya tiene el índice, el cliente de `sigrid-api` y la nocturna | Otro dominio: `ARCHITECTURE.md` lo define como ETL Sigrid → PostgreSQL → Power BI y dice que «no lee `ruesma_rep`». Metería un SDK de IA, una clave y un coste variable y no determinista en una nocturna de 4 h 32 min con tope de 5 h. Repetiría desde cero lo que `facturas` ya aprendió en 50+ features |
| **B · `facturas` (RECOMENDADA)** | Ya extrae facturas de proveedor con IA (F-004, F-024 esquema completo, F-039 todas las líneas, F-050 PDF como PDF), ya lee Sigrid por `sigrid-api` en solo lectura con guardián de AST, ya CONCILIA con discrepancias, tolerancias versionadas y coste medido (F-011), y ya tiene base propia sin binarios y conexión de solo lectura al datamart. Mismo dato (la factura) al mismo proveedor de IA: ninguna exposición nueva | Hoy está en local sin desplegar (su F-008). Su conciliación es contra los ORÍGENES (albaranes, proforma), no contra la factura REGISTRADA: hay que añadir un modo y una fuente nuevos (el archivo de `ruesma_rep`) |
| C · Proyecto nuevo (`documentos-compra`) | Separación limpia, alcance propio | Duplica la extracción de `facturas` (prompts, esquema, correcciones); un octavo inquilino del Postgres compartido; dos equipos de prompts que divergen |
| D · `sigrid-api` | Ya sirve el binario | Es una pasarela sin lógica de negocio; meter IA ahí la convierte en otra cosa y pone su balanceador (230 s) en el camino crítico |
| E · `mcp-bbdd` (herramienta `abrir_adjunto`) | Barato e inmediato: el cliente MCP lee el PDF cuando alguien pregunta por UNA factura | Bajo demanda, no sistemático: no responde «qué facturas descuadran»; sirve binarios con datos personales a cualquier perfil. **Complementaria**, no sustituye |

**Recomendación: B**, empezando solo por facturas (D2) desde 2025 (D4) y con un piloto
antes del histórico. E queda como complemento posible a decidir en `mcp-bbdd`.

## 2 · Cómo encaja la opción B (lo que se entrega al dueño)

```
datamart (este repo)                  facturas (dueño de la lectura)
compras.documento_adjuntos ──P1──▶  lista de facturas con adjunto (desde D4)
                                       │ P2 documents/read (filename_columns: ["cod"])
sigrid-api ◀───────────────────────────┘ P3 tope de tamaño · P4 sin binario guardado
                                       │ P5 incremental por adjunto_id + sha256
                                       │ P6 clasificar fichero · P7 extraer (F-024/F-050)
compras.facturas / factura_lineas ─P8─▶ lo registrado
                                       │ P9 contraste + discrepancias con cifras
                                       ▼ P10 coste y tope por lote · P11 nada nuevo al modelo
                                     base `facturas` (vista de contraste vigente)
```

El pliego P1-P11 está en `requirements.md` §B. Lo que este repositorio garantiza al dueño
es el **contrato del índice**, ya publicado y descrito en su ficha: `adjunto_id`,
`documento_id`, `familia`, `cod_repositorio`, `empresa_repositorio`, `nombre_fichero`,
`extension`, `clase_fichero`, `fecha_alta`, `subido_por`. Si F-139 se implementa allí,
cualquier cambio de esas columnas pasa a romper a un consumidor: hay que anotarlo en
`azure-apps/datamart_seg_anual.md` («qué se rompe si cambia») cuando el consumo exista.

**Carga sobre `sigrid-api` y la ventana**: el día (~130 ficheros, ~50 MB) se baja en ~1 min
en serie; desde 2025 (~21 GB de las tres familias, ~15 GB de facturas) son ~4-6 h a ~1 MB/s.
Se propone que el histórico corra de día, por lotes con tope, y nunca en la ventana de la
nocturna del datamart (comparten la VPN y el SQL Server on-premise). El coste de IA por
factura no se adelanta aquí: lo mide el piloto con los precios de `facturas`
(`config/precios_ia.yaml`), no la memoria de nadie.

## 3 · Ficheros a crear (en este repositorio)

- `tests/test_f139_limite.py` — R1, R2, R4 (texto de la ficha y de `ARCHITECTURE.md`), R3
  (la versión sube respecto a `main`, con el mismo patrón que los tests de diccionario de
  F-090) y R5 (recorre con `ast` los `.py` de `etl_sigrid/` y `main.py` y falla si importan
  una librería de la lista). Sin red ni BBDD.

## 4 · Ficheros a modificar

- `config/diccionario/compras.yaml` — ficha `documento_adjuntos`: en el párrafo «EL FICHERO
  NO ESTA EN EL DATAMART», añadir `filename_columns: ["cod"]` y el 5,7 % (11.262 enlaces)
  que dan HTTP 500 sin él (R1); y una frase de que el contenido se lee fuera, en `facturas`
  (F-139), solo facturas, sin afirmar que ya exista (R2). Sin columnas nuevas.
- `config/diccionario/00_global.yaml` — `version` 52 → 53 (R3).
- `docs/ARCHITECTURE.md` — punto «EL ÍNDICE DE DOCUMENTOS ADJUNTOS…», subpunto «El fichero
  NO se replica»: el límite de F-139 y el aviso de `filename_columns` (R4).
- `harness/features.json` — F-139 a `blocked` con el motivo de R6 (lo hace el líder tras la
  aprobación; `BACKLOG.md` se regenera solo).
- `progress/current.md` — entrada de la spec.
- `C:\Users\pgris\PycharmProjects\azure-apps\datamart_seg_anual.md` — lo de R1 y R4 en el
  párrafo de `documents/read` (R7; otro repositorio, commit local allí).

## 5 · Ficheros que NO se tocan

- Todo el SQL (`etl_sigrid/infrastructure/postgres/sql/`), en particular
  `compras/14_documento_adjuntos.sql`: el índice está bien; el fallo es de quien sirve.
- `config/tables_sigrid.yaml`, `etl_sigrid/domain/documento_adjuntos.py`, los steps y
  `orchestrator.py`: no hay ingesta ni build nuevos.
- `etl_sigrid/infrastructure/sigrid/sigrid_api_client.py`: este ETL no llama a
  `documents/read` y no debe empezar a hacerlo.
- `requirements.txt` / `pyproject.toml`: ninguna dependencia nueva (R5).
- `config/objetos_pendientes.yaml` y la lista de pendientes del diccionario: no hay objeto
  nuevo.
- `azure-apps/sigrid_api.md` y `azure-apps/facturas.md`: sus dueños son esos proyectos.

## 6 · Clases, funciones y SQL

Ninguna clase ni función de producción, ningún SQL. Solo el test de §3. Capa: ninguna.

## 7 · Riesgos

| Riesgo | Medida | Tratamiento |
|---|---|---|
| HTTP 500 de `documents/read` con nombres no ASCII | 5,7 % de los enlaces; 6/6 fallos con tilde o eñe, 0/75 éxitos | R1 (aviso en la ficha) y D6 (arreglo en `sigrid-api`: `X-Document-Filename` va sin codificar) |
| Volumen | ~81 GB las tres familias; máx. 157 MB un fichero | Nada de binario en el Postgres compartido (P4); tope de tamaño (P3); histórico por lotes |
| Ventana nocturna (4 h 32 min de 5 h) | — | Con B no la toca: el contraste corre en `facturas`, fuera de la ventana |
| Carga sobre `sigrid-api` | ~1 MB/s en serie, mediana 0,2 s por fichero | Serie, plazo < 230 s, histórico de día y por lotes (P2) |
| Escaneados | 27 % recientes, 60 % en 2019-21 | Extracción multimodal de `facturas` (P7); un histórico anterior a 2019 rinde poco (D4) |
| Fichero equivocado | 22 % de facturas con varios ficheros | Clasificación previa y estado `SIN_ORIGINAL` (P6) |
| Datos personales | NIF de firmantes en 3/12 contratos; IBAN en 11/26 facturas | Contratos fuera (D2); a la IA solo lo que ya viaja hoy (P11) |
| Falsa precisión | La aparición en texto es una cota superior | El piloto mide acierto real contra una revisión humana antes del histórico (D4) |
| Cambio del índice rompe a `facturas` | — | Anotarlo en «qué se rompe si cambia» de `datamart_seg_anual.md` cuando el consumo exista |

Alternativas descartadas dentro de B: leer lo registrado directamente de Sigrid por
`sql/read` (D3, alternativa) duplica la semántica que el datamart ya resolvió (signo de
abonos, `linea_id` no único en `fact_compras_linea`); usar `descarga-factura` (local, sin
desplegar, sin documento en `azure-apps`) añadiría un tercer actor sin necesidad.

## 8 · Decisiones para el humano

- **D1 · Dónde vive.** Recomendada **B, `facturas`**. Alternativas: A (este ETL), C
  (proyecto nuevo), D (`sigrid-api`), E (`mcp-bbdd`, como complemento). Con A o C esta spec
  se rehace entera.
- **D2 · Alcance de la primera fase.** Recomendada: **solo facturas**. Contratos fuera (47 %
  Word 97 binario, PDF en buena parte impresos por una aplicación, NIF de firmantes; su
  lectura jurídica ya es de `contratos`). Ofertas fuera hasta F-129 (el Excel del
  concurso: 4 de 5 `.xlsx` legibles sin IA, pero sin formato común).
- **D3 · De dónde lee `facturas` lo registrado.** Recomendada: **del datamart**
  (`compras.facturas` + `compras.factura_lineas`, ya con su semántica). Alternativa: Sigrid
  por `sql/read` (más fresco, semántica a rehacer).
- **D4 · Desde cuándo.** Recomendada: **piloto de ~200 facturas de 2026** (o la obra 0696,
  donde Juan ya encontró las 41 mal imputadas) con revisión humana del acierto y coste
  medido; después **desde 2025-01-01** (~39.000 ficheros, ~15 GB). Alternativas: desde 2019
  (96,1 % de cobertura) o todo.
- **D5 · ¿Vuelve el resultado al datamart y al MCP?** Recomendada: **no en esta fase**; se
  consulta en `facturas` (su front, F-057). Si Negocio lo pide por el MCP, feature posterior
  aquí o en `mcp-bbdd` con su spec.
- **D6 · El HTTP 500 de `sigrid-api`.** Recomendada: **proponer una feature en `sigrid-api`**
  (codificar `X-Document-Filename` como ya se codifica `Content-Disposition`). Mientras, los
  consumidores usan `filename_columns: ["cod"]` (R1). Cualquier consumidor que use el nombre
  por defecto (`nomori`, `nom`) cae en el 5,7 %.
- **D7 · Qué se hace con F-139.** Recomendada: aprobar → R1-R5 y R7 en una **feature pequeña
  propia** (documental, este repositorio; los tests llevan el prefijo `test_f139_`) y F-139
  pasa a **`blocked`** de inmediato con la propuesta (R6). Alternativa: hacer R1-R5 y R7
  dentro de F-139, pasar el reviewer y DESPUÉS dejarla `blocked`.
