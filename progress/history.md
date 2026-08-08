<!-- progress/history.md -->
# Histórico del arnés

Registro append-only. El líder mueve aquí el resumen de cada feature terminada.

---

## F-001 — Comando 'version' en el CLI · 2026-08-08

Rama `feature/F-001-cli-version` (desde `dev` en b979b82). `sdd=false`.
Veredicto APROBADO, detalle en `progress/review_F-001.md`.

`python main.py version` imprime versión, tag de imagen, fecha de build y
versión de Python, y sale con 0. `ETL_VERSION` y `get_build_info()` viven en
`config/settings.py`; el tag y la fecha llegan por `IMAGE_TAG`/`BUILD_DATE`
y valen `local` fuera de un contenedor. El `Dockerfile` los recibe como
`ARG` al final del fichero e `infra/20_build_image.ps1` los inyecta en el
build, de modo que la imagen desplegada dice qué build es.

Decisión: `version` se salta `get_settings()` mediante
`ctx.invoked_subcommand`, porque la configuración aborta sin `SIGRID_API_*`
y este es justo el comando que hace falta cuando el contenedor arranca mal
configurado. Verificado que el resto de comandos siguen configurándose.

Commits: e617309 (T0 backlog + arranque), 83730e3 (T1 comando),
cfbdd1b (T2 tests), e37a6b7 (T3 sellado de imagen).
Tests: 15 → 22.

Pendientes anotados, fuera de alcance: `.ps1` en LF frente a la convención
CRLF (llevar a F-003), `ruff` configurado pero no instalado ni ejecutado por
`init.sh`.

---

## F-008 · Documentación de referencia: tablas de Sigrid, landing zone de acens y sigrid-api

Cerrada el 2026-08-08. `sdd=false`. Rama
`feature/F-008-docs-referencia-sigrid-acens`. APROBADA en segunda revisión
(`progress/review_F-008.md`).

Tres documentos que vivían fuera del repositorio entran como Markdown en
`docs/referencia/`:

- `01_sigrid_tablas.md` — Autodocumentador de la BBDD de Sigrid v.20240618,
  380 páginas, ~22.000 líneas. Diccionario de tablas, campos, tipos e
  índices del sistema origen. Salida literal de `markitdown`, sin retoques,
  para que la conversión sea reproducible; los artefactos de extracción
  (cabecera de página repetida, columnas pegadas) quedan advertidos en su
  cabecera.
- `02_azure_landing_zone_acens.md` — diseño de la Landing Zone. Redactado:
  fuera rangos de red y correos personales; la confidencialidad de acens,
  citada en cabecera.
- `03_sigrid_api.md` — microservicio `sigrid-api`, único punto de acceso a la
  BBDD de Sigrid y a quien llama `etl_sigrid/infrastructure/sigrid/`. Llegó
  ya en Markdown, sin conversión. Redactado: fuera el ID de suscripción y el
  host del SQL on-prem; los nombres de recursos se mantienen porque ya
  estaban en `infra/` y en el `README.md`.

Decisión de método: el reviewer ejecuta su propio barrido de datos sensibles
en vez de fiarse del informe del implementer. Salió limpio (cero correos,
cero GUID, cero IPs internas, cero valores de credencial) y esa práctica se
eleva a checkpoint en C3 bis.

Cambios de arnés incluidos en la feature:

- Regla de las **dos paradas con el humano** (proponer y esperar confirmación
  antes de implementar; resumir después), en `CLAUDE.md`, enganchada al flujo
  de `.claude/agents/leader.md` como PARADA 1 y PARADA 2, y reflejada en
  `.claude/agents/implementer.md`.
- Las cinco propuestas de automejora del review, aplicadas: `.gitignore`
  blinda los originales en PDF y ofimática (P1); `CHECKPOINTS.md` explica
  cómo revisar features `sdd=false` (P2) y añade **C3 bis** para documentos
  que entran de fuera (P5); `CLAUDE.md` aclara que la autorización de
  subagentes no exime de la PARADA 1 (P3); `docs/referencia/README.md`
  recoge las variantes de cabecera y el bloque de redacción (P4).

Backlog: alta de **F-009** (inventario del entorno Azure, prioridad 2, solo
lectura) y **F-010** (carga de los Excels auxiliares, prioridad 9). **D5**
parcialmente cerrada: los Excels van a Azure; falta la storage account y
quién los mantiene.

Commits: e8cd88e, c8e90ea, f8864a7, f61512c, 38cde59 y el de cierre.

---

## F-009 · Inventario del entorno Azure existente

Cerrada el 2026-08-08. `sdd=false`, solo lectura. Rama
`feature/F-009-inventario-azure`. APROBADA en segunda revisión
(`progress/review_F-009.md`).

Entregable: `docs/referencia/04_azure_inventario_dev.md`, inventario de los
99 recursos de los 17 resource groups de la suscripción «Ruesma», redactado
y contrastado contra el diseño de la landing zone de acens.

### Hallazgos que cambiaron el plan

- **`rg-sigridetl-dev-data` es un intento anterior de este mismo ETL**,
  abandonado: Azure Functions + Azure SQL, los diez recursos creados el
  2026-04-17 en cuatro minutos, Function App sin funciones desplegadas y base
  pausada desde el 2026-04-18. Nunca pasó de la ingesta —sin capa `mart`, sin
  vistas ni procedimientos— y su catálogo giraba en torno a mano de obra
  (`hmo`, `hmores`, `res`, `tar`), no al seguimiento económico: solo 6 de sus
  20 tablas coinciden con `config/tables_sigrid.yaml`. **No se hereda nada
  técnico**: los datos son un volcado regenerable desde Sigrid. Abre **D7**.
- **Existe ya un PostgreSQL Flexible Server compartido**,
  `psql-albaranes-rs9k2` (PG 16, `Standard_B1ms`, 32 GB), sirviendo a
  `albaranes` y `partes`. Un servidor, varias bases, cada proyecto en su
  propio resource group. Es el patrón de la casa y el precedente directo de
  D1: la opción A —endpoint público con reglas de firewall— ya está en uso.
- **`infra/00_vars.ps1` apunta a recursos que no existen**:
  `rg-seguimiento-dev`, `cae-seguimiento-dev` y `caj-datamart-seg`. No hay
  ningún Container Apps Job en la suscripción.
- **D2 resuelta**: `acralbaranesdev` es el único ACR, con usuario admin
  deshabilitado.
- **Riesgo de datos personales**: `stg.age` contiene cuentas bancarias de
  terceros y `stg.res` correos e identificadores de acceso, en una base con
  acceso público y sin cifrado de columna, etiquetada `acens-compliance=gdpr`.

### Excepción declarada

El criterio `acceptance` nº 1 prohíbe cualquier `create`. Para leer el esquema
de `sqldb-sigrid-ruesma-etl` se creó **una regla de firewall** acotada a la IP
del puesto, ejecutada por el líder con autorización expresa y repetida del
humano. Queda declarada en el documento y en el informe, y verificada por el
reviewer contra Azure. **La regla sigue puesta**: el humano decide si la
retira.

Salvedad: conectarse reanudó automáticamente la base *serverless*. No se
escribió nada en ella; los datos forenses se capturaron antes de conectar.

Commits: ca1146c, 32a59ec, 27e2e57, 047c450, más los del esquema y ff5a434.

---
