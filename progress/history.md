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

## F-005 · Postgres del datamart en Azure (Fase 1)

Cerrada el 2026-08-08. `sdd=true`, spec en `specs/F-005-postgres-azure/`.
Rama `feature/F-005-postgres-azure`. APROBADA en segunda revisión
(`progress/review_F-005.md`). 14 commits. Tests: 22 → **65**.

**Fase 1 (código) completa. Fase 2 (ejecución contra Azure) NO ejecutada**:
queda como runbook para el humano en `progress/impl_F-005.md` §7. Nada se
escribió contra Azure ni contra `psql-albaranes-rs9k2`, que tiene dos bases
en producción; verificado de forma independiente por el reviewer.

### Qué se construyó

- **Base `sigrid_dm` dentro del servidor compartido**, no un servidor nuevo:
  tres ficheros `.sql` de provisión idempotentes, un rol de grupo propietario
  (`NOLOGIN`) con la identidad del job y la cuenta del humano como miembros,
  y un rol de solo lectura para el MCP. El rol de grupo existe para que el
  dueño de los objetos sea siempre el mismo, los cree quien los cree.
- **`apply_grants`** como paso final de `run-all` y como comando suelto, más
  `ALTER DEFAULT PRIVILEGES`. Resuelve que las vistas se reconstruyen con
  `DROP VIEW ... CASCADE` y en PostgreSQL los privilegios mueren con el
  objeto: sin esto, el MCP perdería el acceso cada noche.
- **Telemetría real**: el orquestador deja rastro de cada paso en
  `_meta.etl_runs` —antes solo lo hacían `ingest_raw` y `build_stg`— y un
  comando `timings` con los tiempos por paso. Es la entrada de F-011.
- **Huella de las vistas de consumo** y comparador local ↔ Azure, con
  criterio explícito por bloques (estructura exacta, meses cerrados con
  tolerancia de 0,01 €, bloque vivo solo con avisos).
- **`PG_AUTO_CREATE_DB=false`**: se desactiva el auto-bootstrap que ejecutaba
  `CREATE DATABASE` si la base no existía. Contra un servidor compartido de
  producción era un accidente esperando.
- Autenticación **Entra implementada y probada pero inactiva**, por decisión
  del humano de no tocar el servidor: se usa contraseña en Key Vault, como
  `albaranes` y `partes`. Habilitarla el día de mañana es configuración, no
  código.

### Verificación que merece constar

Los `.sql` de provisión **se ejecutaron de verdad** contra el PostgreSQL
local con los objetos renombrados y borrados al terminar: idempotencia,
`permiso denegado` real del rol de solo lectura al insertar y al crear, y
`ALTER DEFAULT PRIVILEGES` comprobado sobre objetos creados *después* de los
`GRANT`. Encontró así dos errores que habrían reventado delante del humano
contra producción: `pg_database.datowner` no existe (es `datdba`) y
`pg_size_pretty(32 * 1024^3 - ...)` falla por tipo. Y un control negativo del
barrido de secretos: inyectó una contraseña falsa en `.env.example` para
comprobar que la alarma suena.

### El rechazo de la primera revisión

Un **byte NUL** en `infra/00_vars.ps1`, introducido al escribir `.\00_vars.ps1`
en un comentario. No afectaba a la ejecución, pero hacía que git clasificara
el fichero como binario: `infra/00_vars.ps1` desaparecía de los diffs, y es
justo el fichero con el ID de suscripción. El propio reviewer constató que su
primer barrido de GUID sobre el diff salió limpio por ese motivo. La regla
dura «no entran secretos» se estaba volviendo inauditable en silencio.

---

## F-014 · Arnés genérico versionado, reutilizable en cualquier proyecto

Cerrada el 2026-08-09. `sdd=false`, 13 criterios `acceptance`. Rama
`feature/F-014-arnes-generico`. APROBADA en segunda revisión
(`progress/review_F-014.md`). Toca **tres repositorios**.

### Qué se construyó

- **`arnes-base` es ya un repositorio git versionado** (v1.1.0), con el arnés
  genérico separado de lo específico del datamart, `harness/VERSION` que
  `init.sh` imprime, `GUIA_INSTALACION.md` con tres caminos —proyecto nuevo,
  proyecto en marcha, actualizar— e instalador con **modo actualizar que
  enseña el diff** en vez de saltar en silencio lo que ya existe, que era
  justo lo que impedía propagar mejoras.
- **La regla de propagación**, escrita en el `CLAUDE.md` de este proyecto y en
  el del directorio padre **antes** de implementar la feature: si una mejora
  del arnés vale para cualquier proyecto, se porta a `arnes-base` en el mismo
  trabajo.
- **El `CLAUDE.md` del directorio padre** era una copia desactualizada del de
  este proyecto y se cargaba en TODOS los repositorios de `PycharmProjects`:
  mandaba ejecutar `harness/init.sh` y leer `.claude/agents/leader.md` en
  proyectos donde eso no existe. Reescrito como fichero transversal.
- **Documento en `azure-apps`** siguiendo su convención.

### Añadido el 2026-08-09, ya iniciada la feature (criterio nº 13)

Petición del humano: que el arnés impida que Windows suspenda el equipo
mientras hay sesión abierta, para no cortar ejecuciones largas.
`scripts/mantener_despierto.ps1` (API `SetThreadExecutionState`) más los
hooks `SessionStart` / `SessionEnd` vía `scripts/despierto_hook.sh`. Cada
sesión gestiona **su** guardián, etiquetado con el `session_id`, y el
arranque es idempotente. Se incorporó como criterio `acceptance` en vez de
colarse sin revisión.

Dos trampas de PowerShell 5.1 encontradas al probarlo, comentadas en el
código: el literal `0x80000000` se parsea como `Int32` negativo, y `-bor`
sobre `[uint32]` promociona a entero con signo. El script de partida las
esquivaba por casualidad y se rompía al añadir una bandera.

### Lo que rechazó la primera revisión

Cuatro cambios, dos de fondo. El arnés genérico **seguía nombrando las capas
`stg`/`mart`/`cierre`** en `spec-author.md`, que es lo que su propio criterio
nº 6 prohíbe; sobrevivió porque el barrido buscaba `stg/` con barra y el
fichero lo escribía entre comillas invertidas. Y `azure-apps/arnes_base.md`
**se quedó en 1.0.0** cuando el arnés subió a 1.1.0: la regla de propagación
incumplida dentro de la propia feature que existe para evitarlo. Es el
argumento vivo de F-015: una regla escrita no basta si nadie comprueba que se
aplicó.

Los otros dos: `current.md` desactualizado y los `.ps1` de energía sin BOM,
contra la convención de PowerShell del proyecto.

Commits: 53d1127, be54b6c, e33d929, 824e23f, f3c151a en este repositorio;
más los suyos en `arnes-base` y `azure-apps`.

---

# F-015 · Verificar que los tests son de verdad (cerrada 2026-08-09)

**APPROVED a la primera** (`progress/review_F-015.md`), rigor `estandar`,
16/16 tareas, `init.sh` en verde. Spec SDD completa (R1–R20) escrita y
aprobada el mismo día con DA-1..DA-6 tal como se propusieron.

Qué añadió al arnés (todo genérico, portado a `arnes-base` **1.2.0**, commit
local `5006ee8` allí):

- `harness/{alcance,mutacion,cobertura,rigor}.py` + `rigor.json`: mutador
  propio (stdlib, `ast`) sobre las líneas del diff contra `dev`, con informe
  `progress/mutacion_F-XXX.md`, restauración garantizada y timeout por
  mutante; puerta de cobertura de líneas cambiadas; niveles de rigor.
- `init.sh` ejecuta pytest bajo `coverage` y **falla** si la cobertura de las
  líneas cambiadas baja del umbral (80 %, en `rigor.json`). Dependencia nueva
  `coverage>=7.4` en `requirements-dev.txt`.
- `CHECKPOINTS.md`: niveles `documental`/`estandar`/`critico` (default el más
  exigente) + C4 bis. `implementer.md`: fase RED con salida real y sección
  «Evidencias». `reviewer.md`: valida contra el nivel declarado.
- Rigor retroactivo declarado en `features.json` (DA-4).

Evidencias: 166 tests en 1,2 s; 97,5 % de cobertura de lo cambiado (538/552);
autoaplicación 175 mutantes → 13 supervivientes tras cerrar 24 huecos que ni
la fase RED ni el 96,7 % de cobertura habían visto; **línea base F-005: 101
mutantes, 55 supervivientes (45,5 %)**, los 55 analizados, 6 huecos de riesgo
alto (el peor: ningún test fija el default de `auto_create_db`). No se
parchearon: eran el objeto de la medición.

Desviación aceptada por el reviewer: la campaña F-005 corrió en un
`git worktree` aparte (había un `run-all --full` contra Azure en el árbol
vivo); se añadió `--raiz` a la CLI y quedó documentado como práctica
recomendada en la guía de `arnes-base`.

Pendientes elevados al humano (ver `current.md`): MANUAL R20, ¿feature de
refuerzo para los huecos de F-005?, `rigor` de las 9 features sin abrir, y la
automejora del reviewer propuesta en `review_F-015.md` § 6.

Commits: `7ad2e0f` (spec), `8dfa63f` (aprobación), `F-015 T1..T16` (14
commits del implementer), cierre; `5006ee8` en `arnes-base`.

---

# F-004 · Ejecutar el ETL en Azure sin dependencias locales (cerrada 2026-08-09)

**APPROVED sin condiciones a la primera** (`progress/review_F-004.md`), rigor
`estandar`, 11/11 tareas, primera feature del ETL bajo el régimen completo de
F-015. Solo código: no aprovisiona nada en Azure.

Qué hace ahora el ETL: el step `load_excel_aux` (antes un stub SKIPPED)
resuelve los tres Excels auxiliares desde ruta local o URI de blob
(`https://<cuenta>.blob.core.windows.net/...`), autentica con
`DefaultAzureCredential` —sin claves ni SAS; las URIs con query string se
rechazan sin filtrar el token—, lee en memoria sin temporales, valida con
openpyxl y reporta origen/tamaño/hojas. No carga a `aux.*` (eso es F-013).
Arquitectura hexagonal: puerto `AuxFileSource` + adaptadores local y blob en
`infrastructure/excel/`; el step no importa el SDK de Azure. Auditoría R15/R16:
nada en la imagen depende de rutas absolutas; SQL y YAML viajan en la imagen.

Evidencias: 221 tests (55 nuevos) en ~2 s; cobertura de líneas cambiadas
98,2 % (164/167); mutación 27 mutantes → 2 supervivientes (92,6 %), ambos
equivalentes por construcción. El reviewer verificó los totales de forma
INDEPENDIENTE (alcance 527 líneas y 27 mutantes recalculados, coincidencia
exacta) y comprobó a mano que el rechazo de SAS no filtra el token — estreno
del protocolo 1.2.1 del arnés.

Queda vivo en current.md: 3 verificaciones MANUAL bloqueadas hasta F-003,
dependencia AZURE_CLIENT_ID hacia F-003, hallazgo del barrido de secretos
para F-016, y dos afinados de protocolo propuestos por el reviewer.

Dependencia nueva en la imagen: `azure-storage-blob>=12.20.0`.
Commits: `de8db29` (apertura), `F-004 T1..T11`, cierre del líder.

---

# F-020 · Arnés multi-servicio para monorepos (cerrada 2026-08-10)

**APPROVED** (`progress/review_F-020.md`), rigor `estandar`, 11/11 tareas.
El arnés funciona ahora en monorepos de varios servicios: declaración
opcional en `harness/servicios.json` (sin fichero, comportamiento
mono-proyecto idéntico — retrocompatibilidad verificada por el reviewer con
la suite completa previa), `init.sh` valida cada servicio con su venv y su
suite, la cobertura fusiona el coverage de cada servicio y la mutación juzga
cada mutante con la suite de su servicio (DA-5: un servicio sin tests deja a
sus mutantes sobrevivir, visible). Venv declarado inexistente = KO (DA-6).

Probado de verdad contra un monorepo temporal de fixture (T8, salida real en
el informe). Portado a **`arnes-base` 1.3.0** (commit local allí) con la
sección «monorepo multi-servicio» en su guía; anotado en
`azure-apps/arnes_base.md`. Es el prerrequisito de la migración de
albaranes/partes/portal a monorepos por app.

Evidencias: 342 tests (80 nuevos), cobertura de lo cambiado 99,4 %
(167/168), mutación **46/46 muertos, 0 supervivientes** (4 en primera
pasada, cerrados con tests). Totales verificados de forma independiente por
el reviewer. Incidencias de higiene declaradas: un `git add -A` en T8
arrastró la spec de F-019 (inofensivo, historia no reescrita) y un artefacto
de test se retiró en commit propio. Tres reinicios del proceso anfitrión
durante la feature; el trabajo se retomó de transcripción sin pérdidas.

---
