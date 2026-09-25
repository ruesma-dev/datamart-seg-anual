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

# F-016 · Refuerzo de tests para los huecos de riesgo alto de F-005 (cerrada 2026-08-10)

**APPROVED** (`progress/review_F-016.md`), rigor `estandar`, `sdd=false`.
Tests nuevos `test_f016_*` que fijan los 6 huecos de riesgo ALTO de la línea
base de mutación de F-005: default de `auto_create_db` (settings y cliente),
autocommit de la conexión administrativa, igualdad/clasificación FALLO de
`fingerprint.py` y detección de paso fallido en `main.py`. Además, afinado el
barrido de secretos de `test_f005_r21` (adiós al falso positivo de rutas
largas), conservando un test-del-test que demuestra que sigue cazando.

La prueba que cierra el círculo de F-015: campaña de mutación relanzada
sobre el alcance de F-005 → **de 55 supervivientes a 47, con CERO de riesgo
ALTO** (los 6 muertos, más 2 MEDIO de propina). El reviewer cotejó los 6 uno
a uno por cálculo puro. La línea base histórica quedó intacta; los 47
restantes (MEDIO/BAJO), contabilizados como deuda consciente. Ni una línea
de código de producción tocada.

---

# F-019 · Build de stg.plan_mensual por tramos (done 2026-08-17)

**El problema**: el build monolítico de `stg.plan_mensual` (29,4 M filas)
llenó el disco del servidor compartido `psql-albaranes-rs9k2` el
2026-08-09 (93,4 %, solo-lectura ~10 min) y bloqueaba el job nocturno de
F-003. **La solución**: planner puro de tramos por obra
(`domain/tramos.py`, ≤1 M filas de peso por tramo, determinista), filtro
`/*F019_FILTRO_OBRAS*/` en las dos ramas del SQL sin tocar una línea de
negocio, transacción por tramo, y puerta de disco fail-safe antes de cada
tramo (mide TODAS las bases; si falla la medición o supera el 80 %,
aborta dejando la tabla VACÍA y FAILED en `_meta`).

**Verificado de verdad**: 60/60 tramos contra Azure sin un aborto, pico
46,55 % (frente al 93,4 % del incidente), stage 1 h 54 en el B1ms —
veredicto del paso 9 de F-005: el SKU aguanta. La equivalencia funcional
cayó dos veces del lado incómodo y las dos se investigó hasta la causa
raíz antes de enmendar: R13 (checksum distinto → versiones master
duplicadas preexistentes, empates en ventanas; equivalencia semántica
probada con EXCEPT ALL; caso documentado en docs/referencia/05 y
desempate diferido a F-022) y R15 (tres iteraciones de huella que
destaparon 3 defectos reales — esquema legado del raw local, nombre_mes
dependiente de lc_time vía TMMonth, claves sustitutas no deterministas en
la huella — corregidos con rigor completo; los 5 fallos residuales,
probados fila a fila como UNA edición real del Previsto en Sigrid).
Enmiendas decididas por el humano por escrito (opciones C y A).

Evidencias: 398 tests; núcleo 458 líneas / 41 mutantes / 0
supervivientes + fixes 4 líneas / 1 mutante / 0 supervivientes, ambos
verificados de forma independiente por el reviewer; dos pasadas de
review (APPROVED Fase B 2026-08-10; APROBADO final 2026-08-17 tras 3
arreglos documentales). Desbloquea la tanda 2 de F-003 (T23-T26).


## F-024 · Coherencia del datamart ante cargas truncadas — `done` (2026-08-19)

Nació de una muerte real: la primera carga desde el job (2026-08-18) murió por
`DeadlineExceeded` a las 2 h justas, en el tramo 39/60. No hubo daño, pero
destapó tres huecos: una muerte externa dejaba filas `RUNNING` huérfanas para
siempre y `timings` mentía; nada impedía construir `stg`/`mart` sobre un `raw`
mezclado de dos ejecuciones; y el consumidor no tenía forma de saber si lo que
veía era de esta noche o de hace tres días.

**Lo que entrega**: `batch_id` por ejecución; huérfanas `RUNNING` → `ABORTED`
con motivo al arrancar cualquier comando que escriba; puerta de coherencia
antes de `build_stg` y antes de `build_mart`, con `--sin-puerta` registrado
como `SKIPPED`; vistas `_meta.v_raw_state` y `_meta.v_frescura`; comandos
`check-coherencia` y `check-frescura`; y una alerta de frescura en Azure.

**Lo que la valida, y no lo podía dar ningún test**: se mató el job a propósito
a mitad de la ingesta. La tabla `obrparpre` quedó con **4.865.000 filas de
13.809.350** —DA-8 medida, no deducida: la ingesta commitea por página—, la
huérfana se cerró sola con el `batch_id` de quien la cerró, la puerta se negó
en 5,2 s **sin tocar `stg`** y `check-frescura` siguió en FRESCO porque `mart`
no se tocó. La carga murió sin dañar el dato publicado, que era la tesis
entera.

**Dos defectos encontrados durante la propia verificación**, los dos ajenos al
código de la feature y los dos arreglados o fichados:

- La alerta **no se podía crear**: Azure no admite ventana de 30 h. DA-4 se
  mantiene (el criterio sigue siendo 30 h) pero se expresa con ventana de 48 h
  —la menor granularidad admitida que la contiene— y el criterio dentro de la
  KQL. Lo que lo dejó pasar fue un comentario que decía «confirmado con
  `--help`»: `--help` valida la forma, no el valor.
- La **campaña de mutación mentía**: 108/108/0 en paralelo frente a 108/106/2
  en serie. Ficha F-029, encargo en `arnes-base`.

**Evidencias**: 617 tests, cobertura 100 % de 372 líneas cambiadas, mutación
108/106/2 con los dos supervivientes (`bold` de cabeceras) aceptados como
equivalentes, y las cuatro verificaciones manuales con sus salidas reales en
`progress/manual_F-024_fase_c.md`. Tres reviews: Fase B, arreglo de la ventana
y cierre.

**Queda abierto**: D9, el `Deactivated` de la alerta, con fecha y criterio.


## F-003 · Infra: despliegue como Container Apps Job diario — `done` (2026-08-19)

Empezó como «completar `infra/`» y acabó siendo el despliegue entero: Container
Apps Job programado a las 02:00 UTC, imagen en el ACR compartido, identidad
gestionada, secretos en su propio Key Vault, Log Analytics y alerta de fallo.
Estuvo `blocked` desde el 2026-08-17 esperando su cierre operativo, que era
F-023.

**Lo que costó de verdad no fue crear el job, fue hacerlo cargar.** Tres muertes
seguidas, cada una con su arreglo: la noche del 18 por un `timeout_seconds` de
300 contra el techo de 230 s de `sigrid-api` (fix `193fc3c`, y de ahí sale el
`SIGRID_API_TIMEOUT_MAX_S` que valida al arrancar); a las 10:08 del 18 por
`DeadlineExceeded` a las dos horas justas en el tramo 39/60 (fix `1a09f63`,
`replicaTimeoutSeconds` de 7200 a 18000); y el episodio del 9 de agosto en que
una carga llenó el disco y dejó el servidor compartido en solo lectura diez
minutos, que fue lo que motivó F-019.

**Al cerrar aparecieron dos cosas que llevaban días escritas y no funcionaban**,
las dos en comandos copiables que alguien iba a ejecutar: el comando de regla de
firewall pasaba el servidor en `-n` y la regla en `--rule-name`, que **no existe**
en esta CLI —estaba mal en el README, en R23, en el runbook de Postgres y en la
spec de F-005—, y la ficha F-026, a la que apuntaba el defecto del RBAC sin
propagar, **no existía en `features.json`**. Un puntero a una ficha inexistente
dentro de la evidencia de cierre de una feature `critico`.

El reviewer produjo además, en un worktree aislado, la **fase RED que faltaba**
del commit `193fc3c`, que nunca tuvo informe: tres tests en rojo contra el código
anterior al fix, incluido un `DID NOT RAISE ValidationError` que demuestra que el
test discrimina de verdad el techo.

## F-023 · Cierre operativo de F-003: las verificaciones de F-004 — `done` (2026-08-19)

Nació con tres bloques y cerró con uno. Los otros dos —las copias de contraseñas
en el vault de *albaranes* y el rastro en el puesto— salieron a **F-032** por
decisión del humano: era limpieza operativa que estaba reteniendo el cierre de
F-003 y, con él, el arranque de la carga incremental y del MCP.

**Lo que quedó y se cumplió**: las tres verificaciones de F-004 sobre los Excels
auxiliares. Y la sorpresa fue que casi todo estaba hecho sin que nadie lo hubiera
anotado: los tres Excels llevaban tiempo en el contenedor `aux`, el job tenía las
URIs de blob y el rol ya estaba concedido. La verificación 2 **ya había ocurrido**
en la carga del día, esperando en los logs a que alguien mirara.

Tres cosas que merece la pena recordar de esta feature:

- **Un `SUCCESS` puede no probar nada.** El primer intento de la verificación 1
  salió en verde leyendo `origen=local`, desde OneDrive: el `.env` del puesto
  conserva rutas locales aunque el job no. Lo que había que mirar era el campo
  `origen`, no el estado.
- **La prueba negativa se hizo sin tocar RBAC**, apuntando a una cuenta sobre la
  que no hay rol en vez de quitando el rol de la propia. El reviewer lo dio por
  mejor que el requisito original: no exige permisos que el puesto no tiene y no
  deja ninguna asignación que devolver, que era un riesgo real de quedarse sin
  acceso a los Excels.
- **El rigor declarado estaba equivocado.** El fichero decía `estandar` cuando el
  humano la había subido a `critico`, y nadie lo había recogido. Se juzgó como
  `critico` y se corrigió el fichero. Un nivel escrito por debajo del real baja
  la vara en silencio para quien lo lea dentro de tres meses.


## F-011 · Carga incremental del datamart — `done` (2026-08-20)

**Cierra sin implementar lo que su título promete, y está bien así.** La spec
definía dos destinos posibles y escribió la rama del NO **antes** de medir:
DA-7 condicionó la ingesta incremental a que el ahorro fuera ≥ 20 min o la
ingesta pesara ≥ 40 % del total, y DA-4 dejó dicho qué hacer si el watermark no
servía.

**Lo medido**: ahorro máximo **2,25 min** y peso de la ingesta **19,9 %**.
Ninguna condición se cumple, y no por poco. El motivo de fondo es que **la marca
de modificación no existe en las 24 tablas que se llevan el 93 % de la
ingesta**: solo 7 de 31 la tienen. Aunque esas 7 costaran cero, la carga bajaría
de 165,2 a 163,0 minutos.

**La sospecha que abrió la feature era falsa.** Se creía que el cuello de
botella era la ingesta; está en `build_stg`, 110,7 min, el 67,0 % de la carga.
Ese es el sitio, y tiene feature propia: F-025.

**Lo que se entrega**: la medición, que es un resultado y no un consuelo — de
dónde se va el tiempo, qué tablas lo consumen, qué marcas existen realmente en
el origen y cuánto se podría ahorrar como techo. Más las herramientas y tests
que la sostienen: 798 tests en la suite, cobertura 100 % de 469 líneas
cambiadas, mutación 189/189/0 reejecutada de forma independiente por el
reviewer con `--workers 1`.

**Lo que hay que recordar**: el atajo de «solo altas» sí llegaría al umbral y
**serviría un plan viejo en silencio**, porque `obrparpre.planif` se edita sin
crear filas. Está clavado en `progress/decisiones_abiertas.md` como **D12**,
fuera de esta feature, porque una feature cerrada deja de leerse.

---

## F-006 · MCP sobre el datamart: la capa semántica en `_meta` · 2026-08-27

Rama `feature/F-006-mcp-azure`. Rigor `critico`. **APROBADA en la 21ª pasada**
del reviewer, tras arrastrar un RECHAZADO desde la 16ª. Detalle en
`progress/review_F-006.md` (+ anexo) e `progress/impl_F-006.md` (+ anexo).

**Qué entrega.** El diccionario semántico del datamart publicado en `_meta`
—qué significa cada objeto y cada columna y qué reglas hay que respetar para
leerlo— para que cualquier agente conectado por MCP construya sus propios casos
de uso. **Versión 9 publicada y verificada** contra la base: 103 objetos, 798
columnas, 16 reglas, cobertura 100 %, hash `72125091cc25`. Lo consume `mcp-bbdd`
por SQL, con el rol de solo lectura `mcp_sigrid_dm_ro`.

**Por qué costó 21 pasadas: no había evidencia, y nadie lo sabía.** Las cuatro
campañas de mutación anteriores (112/112, 132/132, 166/166, 254/254) declaraban
cero supervivientes porque la suite arrancaba ROJA dentro del worktree y
`mutacion.py` contaba cualquier `returncode != 0` como muerto. La causa —el
`.env` no existe en un `git worktree`— se arregló en el **arnés 1.7.7**, y la
campaña midió por primera vez de verdad: **256 mutantes, 204 muertos, 52
supervivientes, 0 timeouts**, 2 h 19 min con 6 workers. Los 52 quedaron
resueltos: **49 muertos** con tests nuevos y **3 equivalentes** aprobados por el
humano con su demostración escrita. La suite pasó de 2.290 a **2.505 tests**.

**Lo que se lleva al backlog:**

- **F-041** — la campaña paralela produce **falsos muertos** (cuarto defecto,
  fichado con su reproducción en `progress/control_mutacion_F-006.md`). Regla
  operativa mientras no se arregle: *lo que una campaña paralela declare muerto
  se reverifica en serie antes de cerrar un `critico`*. El reviewer lo aceptó
  para esta feature y dejó dicho que **no es precedente general**.
- **F-034** — recibe T29-T31 **POR CONSTRUIR**. La spec decía que se entregaban
  «construidos y apagados» y era falso; enmendado. Trampa: el rol
  `mcp_sigrid_dm_ro` **lo comparten hoy el MCP y Power BI**.
- **F-048** — nueva: el guardián de secretos decide por el primer carácter del
  valor, así que `password=%x` o `password=#x` están exentos desde siempre.

**Lo que NO entrega, y conviene no confundirlo con el cierre.** El humano pidió
«un MCP que pueda usar cualquier usuario desde cualquier puesto». Hoy corre en
el puesto de pgris apuntando a Azure. F-006 construyó la capa semántica, que era
el prerrequisito; el despliegue vive en el backlog de `mcp-bbdd` (F-003
transporte, F-004 OAuth con Entra ID, F-006 contenedor).

---

## F-042 · La clave de `mart.fact_seguimiento_mensual`: de 8.778 duplicados a cero · `done` (2026-08-30)

**El defecto.** La tabla central del seguimiento no cumplía la clave que
declaraba: 22 obras tienen dos fases que Sigrid archiva con el mismo año y el
mismo mes, y al proyectarlas al mismo `anio_mes` salían dos filas
indistinguibles. **8.778 combinaciones duplicadas, 17.556 filas.** El daño en
dinero no estaba en el fact sino en el agregado: `SUM(importe_origen)` sobre las
filas gemelas devolvía exactamente el doble, y así se publicaban **30,4 M€ de
más en 35 celdas de 7 obras** a Power BI y al MCP.

**La decisión de Negocio, del humano:** «el mes no se parte en 2, se coge el
cierre más moderno de ese mes», y en el acumulado se ignora el primero. Con el
matiz de PUY DU FOU: se descarta un cierre con acumulado **cero** cuando hay
otro del mismo mes con acumulado positivo. Sin ese matiz, la 0606 habría pasado
de publicar 18,24 M€ correctos a publicar cero.

**El mecanismo: descartar Y RENUMERAR**, en `sql/stg/08_plan_mensual.sql`. No
basta con borrar la fila. `importe_mes` de los reales no viene de Sigrid, lo
calcula el ETL como diferencia con el `LAG` **consecutivo**; sin renumerar, el
movimiento de feb-2018 de la 0499 habría pasado de 975.249,98 a 5.688.073,92.
Se arreglaría el acumulado y se reventaría el movimiento.

**Cómo se verificó, y esto es lo que el humano fijó como prueba que decide:** no
que los tests pasen, sino que **el dato de las obras no afectadas no se mueva**.
Antes/después sobre el mismo `raw`, los cuatro ámbitos. `comparar-huellas` salió
en código 0 sin escribir una fila: 19 cambios de importe, **−30.424.662,34 €**,
todos a la baja y todos en las 9 obras esperadas.

**El cierre, contra la base ya reconstruida** (job
`caj-datamart-seg-dev-d8y5q10`, imagen `r20260830-0924`, `run-all --full`,
3 h 31 min): `check-unicidad` **0** en `fact_seguimiento_mensual` (eran 8.778),
`check-cierres` **0 discrepancias** en 8.540 cierres y **0** series sin cuadrar
de 254.189, `check-diccionario` biyección **103/103**, `init.sh` código 0 con
2.802 tests y 100 % de 656 líneas cambiadas. El quinto criterio lo verificó el
reviewer en una 3ª pasada con un **oráculo independiente del build**: 17.289
celdas cruzadas con desvío máximo **0,00 €**, cambian **35 celdas de 7 obras** y
ni una más.

**Sin campaña de mutación**, por decisión del humano del 2026-08-29, declarada
N/A en C4 bis. Para un cambio que reescribe datos, la garantía pertinente no es
«mis tests detectan cambios en el código» sino «no cambian datos que no
deberían cambiar». Fase RED y cobertura sí se exigieron y están.

### Lo que esta feature enseñó

1. **Un test puede pasar en verde afirmando lo contrario de la realidad.** El
   fixture de la 0246 tenía los dos importes intercambiados y el test no lo
   notaba, porque la regla decide por número de fase. Lo destapó perseguir una
   brecha de **1.219 €** que se podía haber dado por redondeo.
2. **Un guardián puede mentir justo donde hay que mirar.** `check-cierres`
   clasificaba como hueco de origen los huecos que crea esta misma feature, y
   habría devuelto «0 series rotas» sin mirar ninguna de las 9 obras. El
   arreglo observa el descarte como **hecho**, no repitiendo la regla: si la
   repitiera, un fallo del build y uno de la comprobación se cancelarían.
3. **Tres afirmaciones del líder resultaron falsas y las cazó el reviewer**: la
   causa del único `importe_mes` que se mueve, los «0 cambios en los ámbitos
   master» —tautológicos, porque la herramienta copia esas filas— y que el
   agregado de `stg` fuera idéntico al de `mart` también en los master.
4. **Un veredicto por timeout no es un veredicto.** `check-unicidad` con sus 30 s
   por defecto dejaba en NO COMPROBADO justo el objeto que decidía la feature.
   Hizo falta `--timeout 300`.

### Lo que deja abierto

- **F-051** (nueva): `nombre_mes` de las filas reales trae la descripción del
  cierre en vez del mes, y eso rompe la clave de `cierre.v_pbi_planif_vs_real`.
- El diccionario publicado dice **30.425.881,56 €** retirados y lo retirado son
  **30.424.662,34**: describe la regla exploratoria, no la implantada.
- **1.152 filas de `stg.presupuesto` de la obra 0599** (2,6 M€ en abr-2022) no
  llegan al fact porque su `partida_id` no tiene ficha en `stg.partidas`.
- `check-unicidad` no consigue comprobar `mart.v_master_vigente_anual` ni con
  300 s: su clave sigue sin verificar.

---

## F-025 · Ventana de negocio en el build — `done` (2026-09-08)

Rama `feature/F-025-ventana-negocio-build`, commit de cierre `96bb7b9`. Rigor
`critico`. Veredicto APROBADO en `progress/review_F-025.md`.

El build dejaba de reconstruir cada noche las 920 fichas del censo y pasa a
acotar `plan_mensual` y `presupuesto` a las obras vivas. **Ahorro medido tres
veces, con dos imágenes distintas y en dos días: 71,2 %, 72,2 % y 72,2 % en
`build_stg`** (9.527 s → 2.652 s), y la noche entera baja de **4 h 52 a
3 h 00-3 h 18**. Las cifras, con las tres ejecuciones comparadas, en
`specs/F-025-ventana-negocio-build/mediciones.md`.

**El error que costó la mañana y que quedó en memoria**: se cronometró
`build_mart` —un paso que esta feature no toca— y se declaró la feature fallida
con un 9 %. Había dos ficheros `02_build_fact.sql` en capas distintas. El paso
que mide la feature se verifica antes de creerse un número.

Deja abierto: **T33** (bloat sostenido tras siete noches acotadas) pasa a
**F-065** con dueño y umbral; y el censo destapa **552 obras de ruido**, de las
que 512 siguen vacías después de reconstruirlas, lo que abre **F-071**.

---

## F-068 · Los datos personales de `raw.emp`, fuera del alcance del MCP — `done` (2026-09-08)

Rama `feature/F-068-datos-personales-mcp`, commit de cierre `f94fae6`. Rigor
`critico`. Veredicto APROBADO en `progress/review_F-068.md`.

El rol de solo lectura del MCP deja de poder leer `raw.emp` y `raw.res`, y la
nocturna lo mantiene. **La clave del arreglo**: separar lo *declarado* de lo
*existente*. `ALTER DEFAULT PRIVILEGES` reponía el `GRANT` en cuanto la tabla se
recreaba, así que un `DROP` nocturno devolvía el acceso sin que nadie lo notara;
ahora manda la lista declarada (`PG_EXCLUDED_TABLES`) sobre el catálogo, y el
defecto es el seguro.

**La revocación es TEMPORAL y su reversión está decidida por el humano**: vuelve
en cuanto el MCP tenga control por usuario. Escrito en `config/settings.py`,
`infra/sql/02_roles.sql`, `docs/ARCHITECTURE.md`, el runbook y las fichas del
diccionario, para que dentro de seis meses nadie lo lea como una prohibición
permanente.

Deja abierto: `infra/sql/02_roles.sql` **no lo ejecuta ningún test** —solo se
comprueba su texto— y está corregido en dos sitios que solo prueba `psql`.
Antes de volver a provisionar un rol desde cero, ejecutarlo contra una base de
prueba.

---

## F-066 · Ingesta de las tablas `raw` pendientes — `done` (2026-09-09)

Rama `feature/F-066-ingesta-raw-pendientes`. Rigor `critico`. Veredicto
**APPROVED** en la cuarta pasada del review, `progress/review_F-066.md`.

**La ingesta pasa de 31 a 56 tablas** y las 56 corren cada noche en producción.
La nocturna automática `29815200` (00:00 → 03:13 UTC del 09-sep) terminó
`Succeeded` con los diez pasos, 57 tramos sin un solo no-SUCCESS, 25.497.946
filas y 130/130 objetos declarados. Las decisiones DA-1 a DA-11 viven en
`design.md` §6; las tres que cerró el humano el 06-sep: `emp` y `res` enteras
(con solo 11 exclusiones técnicas), el histórico de estados a **F-067** como
foto diaria porque Sigrid no lo guarda, y `apu` entera con `--full` más `apa`.

**Tres hallazgos que valen más que la feature:**

1. **`check-raw-recuentos` cazó un fallo real el día que nació**: el YAML tenía
   17 entradas duplicadas que la nocturna habría cargado dos veces cada noche.
   Ningún test lo veía porque todos leían la ingesta como un `dict`, que colapsa
   duplicados.
2. **`CREATE TABLE IF NOT EXISTS` no reconcilia columnas.** Una columna nueva en
   el origen (`pagtex` en `raw.dcf`) tumbó dos nocturnas con `UndefinedColumn`.
   Se arregló con `_reconciliar_columnas_raw`, en la misma transacción.
3. **La igualdad exacta contra Sigrid era inalcanzable por diseño** —el ERP está
   vivo y el datamart es una foto—. Se sustituyó por **tolerancia CON
   DIRECCIÓN**: filas de más en Sigrid son deriva y se toleran hasta 0,05 % por
   tabla; **filas de MENOS son alarma sea de una sola**; `ausentes` y `sin_medir`
   siguen siendo fallo. El mismo estado de la base que el 08-sep daba «31
   iguales · 25 distintas» y código 1 ahora sale CONFORME con la peor desviación
   en 0,0080 %: seis veces de margen, y sin tapar ninguna señal grave.

**La grieta, dicha en voz alta por el reviewer**: 0,05 % de `obrparpre` son unas
6.940 filas. **Revisar el umbral si baja `page_size` o aparece una tabla mayor.**

**Y una lección de método que ya había costado diez días en agosto**:
`check-diccionario` salió en rojo con el código bien. La imagen en producción
era del mediodía anterior y dos fichas se habían corregido después. **El
repositorio en verde no es producción.** Se resolvió desplegando
`r20260909-0520` y publicando el diccionario a mano, las dos cosas con
autorización expresa del humano.

Deja abierto: **F-069**, dos cegueras del mutador —no muta constantes `float` ni
la división—, y una de ellas es `TOLERANCIA_DERIVA_PCT = 0.05`, el número del
que depende entero el criterio. Están cubiertos por tests (el reviewer los mutó
a mano y mueren), pero eso lo demuestran los tests y no la campaña.

---

## F-072 · El censo semántico de las 31 tablas que nadie consume — `done` (2026-09-09)

Rama `feature/F-072-censo-semantico-raw`. Rigor `documental`. Veredicto
**APROBADO** en la pasada 2, `progress/review_F-072.md`.

Nace el mismo día, al retirar F-071: **«analizar el dato que hay ahora mismo y
los hallazgos, y con eso crear nuevas tablas de datos procesados y enriquecer
las actuales; usa la conexión sigrid-api para entender lo que significan»**. El
hecho que la abre: de las 56 tablas que se ingieren cada noche, **solo 25 las
consume algún build**. Las otras 31 ocupan disco y la IA no las ve.

**Cuatro exploradores en paralelo**, un bloque cada uno, cruzando tres fuentes
por tabla: el diccionario de Sigrid en `azure-apps`, **sigrid-api contra el
Sigrid vivo** y mediciones de solo lectura sobre `raw`. Entregable:
`progress/explore_F-072_catalogo.md` más los cuatro informes de bloque.

**El veredicto**: se construye con 19 tablas, se descartan 6, el resto es
catálogo. **Nueve tablas del origen no se ingieren** y bloquean media
propuesta, lo que abre **F-074**.

**Seis fichas del backlog daban por cierto algo que el censo desmiente**, y se
corrigieron en el mismo trabajo:

1. **F-057**: `res` **no es el maestro de personal**. 1.353 filas son personas,
   1.157 son consumos imputables y 106 son medios. Sumar `hmores` sin cortar por
   `cla` da una cifra falsa, que es lo que la feature habría hecho.
2. **F-045**: el nudo **ya está resuelto**. `cen.obride` está a cero en las 804
   filas, pero centro y obra son dos filas de `con` con la misma empresa y
   código: **683 pares, 0 ambigüedades, 261 de 261** en retenciones. La
   aritmética `+1` que se suponía solo acierta el 63,8 %.
3. **F-061**: deja de estar bloqueada por lo anterior, y el multiplicador que le
   falta se llama `reshor`.
4. **F-038**: el proveedor **no** sale de `comprv.prvide` (18,11 % informado)
   sino de `dco.entide` (99,86 %). Y `comlin` necesita saneado: 14.513 precios a
   0, 4.100 negativos y **una línea de 363 M€ que por sí sola duplica 2020**.
5. **F-036**: su punto 3 **no es implementable**. `auxobrtca` tiene 3 filas y
   `obrparpar.tcaide` está a cero en las 392.207 partidas.
6. **F-055**: `prvcer` es **dato muerto desde 2019**; 2.708 de 2.741
   certificados caducaron antes de 2020.

**Dos hallazgos que no buscaba nadie.** `com`, `comlin` y `comprv` declaran una
`incremental_column` que **no existe en Sigrid**: el ETL degrada en silencio y
esas 287.673 filas se recargan enteras cada noche. Y el APU **no existe como
dato**: `catest`, `catpro` y `obrparres` están vacías y la descomposición vive
dentro de un blob, así que no se puede prometer «de qué está hecho el precio de
una partida».

**El review cazó lo que faltaba**: los hallazgos heredados de F-071 no estaban
medidos. Medidos ahora, **de 921 fichas de obra solo 294 traen municipio
(31,9 %) y 305 traen dirección (33,1 %)**: a «dónde está la obra X», para dos de
cada tres la respuesta correcta es «no consta». Acota lo que F-073 puede
prometer.

Deja abierto: **F-073** (construir), **F-074** (la ingesta de las nueve) y
**F-075**, el defecto del arnés que el reviewer destapó: `harness.alcance`
diffea contra una base vieja, así que **las dos puertas automáticas miden
código de otras features**, y el fallo puede ir en la dirección mala.

---

## F-074 · La ingesta que destapó el censo: nueve tablas, una carga incremental falsa y un campo excluido — `done` (2026-09-09)

Rama `feature/F-074-ingesta-tablas-del-censo`. Rigor `estandar`. Veredicto
**APPROVED** en la pasada 2, `progress/review_F-074.md`.

Da de alta nueve tablas de Sigrid que el censo de F-072 destapó y sin las
cuales media propuesta no se podía escribir: `auxhor`, `auxrestip`, `cet`,
`auxdpt`, `pro`, `reshor`, `emphis`, `dcaprodes` y `ctrprodes`. Las dos de
nómina, `reshor` y `emphis`, quedan **fuera del alcance del rol del MCP** por
el mecanismo de F-068, con el `REVOKE` posterior al `GRANT` verificado por el
reviewer.

**El hallazgo del implementer, que corrige al líder.** La feature se ordenó
sobre una premisa falsa: que seis de las nueve cargarían solo altas por no
tener `tiemod`, y que una fila modificada no volvería a bajar. **No es así.**
El `CMD` del `Dockerfile` arranca `run-all --full`, o sea `TRUNCATE` y recarga
entera de **todas** las tablas cada noche; `incremental_column` **no decide el
modo de carga**, solo si se rellena `_source_tiemod`. No había agujero que
tapar, y no se inventó ningún mecanismo para taparlo. Corregido por escrito en
el YAML, en `ARCHITECTURE.md`, en `current.md` y en el §4 del catálogo de
F-072, que lo insinuaba.

**Dos arreglos y una limpieza** en el mismo paquete: `com`, `comlin` y `comprv`
dejan de declarar una `incremental_column` que no existe en Sigrid; `prvcer`
deja de excluir `tex`, el único campo que dice de qué es cada certificado; y
`obrprv`, con 0 filas en origen, queda decidida con su motivo escrito.

**La campaña de mutación, y la lección de método.** El implementer declaró un
superviviente que no era: dijo `--full` y era `--reconstruir-todo`. **El
reviewer reprodujo la muestra con la semilla declarada y el mutante de `--full`
ni siquiera estaba en ella.** Devuelto, el implementer lo midió en vez de
suponerlo: sin `is_flag`, click infiere `BOOL` y `run-all --reconstruir-todo`
sale con exit 2, mientras la nocturna no se entera. Lo dejan vivo sus propios
tests, que comprueban el `--help` por substring y el cableado por `getsource`
pero **nunca invocan la opción por el parser**. Es código de F-025, ya cerrada,
así que **no se tapó aquí**: salió a ficha propia, **F-077**.

`bash harness/init.sh` en verde con la ejecución del propio reviewer: exit 0,
**4.162 passed**, 168 skipped, 523 s.

Deja abierto: **F-077** (el flag sin test por el parser) y el aviso, ya fichado
como **F-075**, de que la puerta de cobertura sigue midiendo 842 líneas de un
alcance que no es el de esta feature.

---

## F-079 · Lo publicado es para consultarse: `stg` deja de estar desaconsejado — `done` (2026-09-09)

Rama `feature/F-079-todo-lo-publicado-es-consultable`. Rigor `estandar`.
Veredicto **APROBADO**, `progress/review_F-079.md`.

Pedida por el humano: «parece que en el diccionario se indica que no se
recomienda para consulta `stg`, **eso bórralo, todo lo expuesto es para
consulta**». Los **7 objetos de `stg`** que no son funciones pasan a superficie
de consulta y pierden su `motivo_no_consumo`. El diccionario sube a la
**versión 18**.

**El inventario, que era la mitad del trabajo.** Los 27 objetos marcados fuera
de `raw` no eran lo mismo: **7 de `stg`** con preferencias de enrutado (se
quitan), **10 funciones SQL** que no se consultan sino que se llaman desde el
build (se quedan), y **10 objetos rotos o vacíos** donde el aviso es un hecho y
no una preferencia (se quedan, con el motivo reescrito para que se note la
diferencia). `mart.v_pbi_cp_tipologia` no se tocó: la arregla **F-078**, de otra
sesión.

**El riesgo, y cómo se cerró.** Dentro de los motivos borrados había
**advertencias de corrección** mezcladas con las preferencias. La grave es la de
`stg.plan_mensual`: ahí conviven todas las versiones master y una consulta sin
filtrar versión **multiplica los importes**. El reviewer verificó una por una
que **las cuatro advertencias siguen llegando al agente**, y las dos graves por
tres vías distintas.

`bash harness/init.sh` en verde: **4.215 passed**, cobertura 93,6 %.

**Dos avisos del reviewer que valen para lo siguiente**: lo que el MCP sirve
puede ir por detrás del árbol, así que el número de versión del informe no se da
por bueno sin `check-diccionario`; y **la nocturna republica el diccionario
desde la imagen desplegada**, de modo que una imagen vieja pisaría la 18 con la
suya. Por eso este cierre va seguido de despliegue.

## F-073 · Tablas nuevas y enriquecimiento (cerrada el 2026-09-11, APROBADO)

Rama `feature/F-073-tablas-nuevas-y-enriquecimiento`, 21 tareas, commits
`59a6b36..d203a5a`. Informe: `progress/impl_F-073.md`; review:
`progress/review_F-073.md`; campaña: `progress/mutacion_F-073.md`.

**Qué construyó**, con la regla de frontera que fijó su diseño —*F-073 publica
DIMENSIONES y el MAESTRO DE OBRA; la feature de dominio publica su HECHO y hace
el CABLEADO*—:

* `maestro.centros_coste`, el puente centro de coste -> obra: 804 filas, 683 con
  obra, 1:1 por construcción. Resuelto por empresa y código en `raw.con`, **sin
  usar `cen.obride`** (a 0 en las 804) ni aritmética sobre el `ide`.
* `maestro.obras` enriquecida: dirección, `municipio`/`provincia` con sus dos
  identificadores, las marcas `tiene_presupuesto` y `tiene_seguimiento`, y
  `estado` con su nombre. **921 filas y ninguna columna perdida**: las 10 de
  siempre van primero y en su orden, las 11 nuevas detrás.
* `maestro.estados_documento`, las 193 filas de `conest`.
* `compras.formas_pago`, las 69 de `auxpag` con su medio resuelto.

**Las tres decisiones que aprobó el humano**: la frontera con F-067; que las
marcas lean de `stg` y no de `mart`, con `build_maestros` pasando a depender de
`build_stg`; y publicar la dirección con la cobertura que hay (un tercio),
declarando el porcentaje en la ficha en vez de exigir un mínimo.

**Evidencias del cierre**: `init.sh` exit 0, **4.367 passed / 171 skipped / 0
failed**, cobertura de líneas cambiadas **93,6 % (791/845)**, 288 mutantes
generados y los nueve supervivientes analizados uno a uno. Diccionario del árbol
en **versión 19**.

**Lo intocable siguió intocado**, verificado por `sha256` y no por el informe:
`stg/06_presupuesto.sql`, `stg/08_plan_mensual.sql`, el `rn = 1` de
`stg/03_obras.sql`, `compras/01_documentos.sql` y `sql/retenciones/**`.

**Corrección que salió de aquí**: R23 y el diseño afirmaban que el cableado de
forma de pago y estado a `compras.contratos` **y** `compras.facturas` era el
criterio 1 de F-067. Ese criterio nombra solo los contratos, y ningún criterio
prometía la forma de pago de la **factura**. La reclama **F-080**.

**Tres hallazgos del review que NO bloquearon y esperan decisión del humano**:
dos supervivientes de mutación ajenos a F-073 (`ventana_sql.py:215` y
`build_stg_step.py:732`); que `config/tables_sigrid.yaml` declara el nombre del
medio de pago en `auxefp.est` **y es falso** (está en `res`); y una automejora
de `CHECKPOINTS.md` para las features cuyo entregable es SQL y no generan
mutantes en sus propias líneas.

## F-081 · Las dos deudas del review de F-073 (cerrada el 2026-09-11, APROBADO)

Rama `feature/F-081-deudas-review-F-073`, 8 tareas, commits `87f4d84..d5e484c`.
Informe: `progress/impl_F-081.md`; review: `progress/review_F-081.md`.
Sin spec (`sdd=false`): el contrato fueron sus siete `acceptance`.

**Deuda 1 · la mentira de la configuracion de la ingesta.**
`config/tables_sigrid.yaml` declaraba que el nombre del medio de pago de
`auxefp` esta en `est`. Es falso: `est` viene vacia o nula en las 10 filas y el
nombre esta en `res`. F-073 lo esquivo usando `res` y lo documento, pero no
corrigio el yaml. **F-081 encontro ademas la misma mentira en la entrada de
`cen`**, que nadie habia mirado. Deja un test que falla si alguien vuelve a
declararlo en `est`, para que la correccion no se deshaga en silencio.

**Deuda 2 · los dos supervivientes de mutacion que si eran agujeros de test**,
ninguno de codigo de F-073: `ventana_sql.py:215` y `build_stg_step.py:732`.
**Murieron solo con tests nuevos**, verificado en el diff: ninguno de los dos
ficheros cambia un caracter.

**UNA PREMISA FALSA DE LA FICHA, corregida por el reviewer y que conviene no
propagar**: la ficha de F-081 afirmaba que `build_stg_step.py` es fichero del
SELLO. **No lo es.** `FICHEROS_DEL_SELLO` son solo `stg/06_presupuesto.sql` y
`stg/08_plan_mensual.sql`. La restriccion que se impuso era mas estricta de lo
necesario; no hizo daño, porque tapar un agujero con tests es lo correcto de
todas formas, pero la afirmacion era erronea.

**CHOQUE QUE DEJA VIVO**: F-081 sube el diccionario a la **version 20**, que la
spec de F-080 tenia reservada. **F-080 pasa a la 21**, y su tarea de
«comprobar que el fichero esta en 19» ya no se cumple.

## F-080 · Los vencimientos, la forma de pago y el texto de la factura (cerrada el 2026-09-15, APROBADO)

Rama `feature/F-080-vencimientos-forma-pago-y-texto-factura`, 30 tareas,
commits `b6cfd6e..f9ac2b4`. Nace de dos correos de **Juan Romero** (Dir. Admon
y Control de Costes) del 2026-09-10. Informe: `progress/impl_F-080.md`; review:
`progress/review_F-080.md`; campañas: `progress/mutacion_F-080.md` y
`progress/mutacion_F-080_modulos.md`.

**Que publica**: `compras.vencimientos` (una fila por efecto de la factura de
compra), `compras.v_facturas_pago`, `compras.v_control_forma_pago` (el cruce
que pedia el correo), `compras.documento_texto` (el memo integro) y
`compras.documento_comentarios` (un comentario por fila). Mas la ingesta de
`con.tex` y de tres tablas nuevas —`auxnap`, `auxban` y `rpa`—, de 65 a 68.

**LA LECCION, que esta feature aprendio TRES veces por las malas**: en Sigrid
muchos documentos **extienden `con`**, y antes de concluir que un campo no
existe hay que mirar ahi. Paso con el texto (no esta en `dcf.tex`, 474 de
165.658, sino en `con.tex`, 108.445), con el codigo y el estado del efecto (el
efecto ES un documento, `tip = 25`) y con el codigo de la remesa (tampoco esta
en `rpa`). **La spec se corrigio cuatro veces por esto.**

**Tres campos que prometen y no cumplen, medidos**: `pag.padide` a 0 en los
255.074 (no hay enlace hijo -> origen), `con.serie` a 0 (la serie se deriva con
`compras.fn_serie`) y, de F-073, `cen.obride` a 0 en las 804.

**LA TRAMPA QUE LA FICHA DECLARA**: sumar los importes de todos los efectos de
una factura **DUPLICA**, porque conviven el anulado y sus hijos. La anulacion es
`con.fecbaj <> 0` —**89.095 de 255.074 efectos, el 34,9 %**— y se comprobo
contra la captura del correo: los tres efectos que la pantalla pinta en rojo con
aspa son exactamente los tres con fecha de baja, y la suma de los vivos
reproduce los dos importes de la cabecera.

**Coste de ventana medido**: el memo añade ~30 s sobre una noche de 3 h 25 min.
34 min de margen frente al presupuesto de referencia de 4 h, que **el humano
dejo como referencia y no como puerta**.

**Evidencias del cierre**: `init.sh` exit 0, **4.677 pasan / 179 saltados / 0
fallos**, cobertura **93,9 %**, dos campañas de mutacion (303 y 27 mutantes)
recalculadas por el reviewer fichero a fichero. Diccionario del arbol en
**version 21**.

**ESTRENA LA NORMA DEL ENCARGO 1.7.11 del arnes**: como casi todo el entregable
es SQL, la campaña canonica no decia nada del codigo de la feature. Se declaro
el cero y se hizo la **prueba de control** (0 mutantes en las 42 lineas
cambiadas de `build_compras_step.py`, **12 en el fichero entero**: el motor sabe
mutarlo, el cero viene del alcance), mas una **segunda campaña dirigida** a los
dos modulos sin muestreo, con los 27 mutantes muertos.

**PROPUESTA DEL REVIEWER, no aplicada**: cinco de los seis supervivientes de la
campaña canonica son de **F-025**, y **dos campañas seguidas los señalan**
(F-073 marco los mismos). Merecen ficha propia, como F-077 y F-081.

**VERIFICACIONES MANUAL PENDIENTES** (T0 bis, T7, T26 y T27), anotadas con su
comando exacto en `progress/current.md`. Ningun agente las ejecuta.

## F-078 · FactCPTipologia deja de colgar Power BI (cerrada el 2026-09-15, APROBADO)

Era la **unica vista `v_pbi_` sin tabla detras**, asi que se recalculaba entera
en cada consulta: cinco recorridos de `stg.plan_mensual` (29,8 M de filas,
11 GB) y un WindowAgg sobre 11,8 M de filas intermedias. Contra Azure **no
terminaba**.

Se materializa en **tres tablas** construidas dentro de `build_mart`, y las tres
vistas conservan nombre, columnas y **tipos**, leyendo de su tabla. Cambia
DONDE se calcula, no QUE se calcula: el reviewer comparo los tres cuerpos del
SQL viejo contra los nuevos tras normalizar y salen identicos salvo la
referencia.

**RECHAZADA EN LA PASADA 1 POR FALTA DE EVIDENCIA, no por defectos**: la spec
exigia medir contra Azure y nadie lo habia hecho. Medido despues con
autorizacion expresa del humano: `build_mart` **2.414,6 s** con el sub-paso
`cp_tipologia` en **1.162,06 s / 1.740 filas**; `build_cierre` **2.943,0 s**;
`check-cp-tipologia` **1.740 filas y CERO diferencias**; y `SELECT *` de la
vista en **0,81 s**, cuando antes no terminaba. Aprobada en la pasada 2.

**LECCION QUE COSTO UNA NOCHE**: no llegamos a desplegar antes del cron de las
00:00 y la nocturna del 16 corrio con la imagen vieja, **deshaciendo F-078**
—las vistas volvieron a su forma cara—. Se rehizo `mart` y `cierre` a mano.
Vale lo que ya dice la memoria: **el repositorio en verde no es produccion**.

**CRITERIO 2 CERRADO POR EL HUMANO el 2026-09-16**, que era lo unico que ningun
comando podia demostrar: «**f78, bi ya funciona perfectamente esta todo
arreglado**». El informe de Power BI carga `FactCPTipologia` **sin tocar una
linea del `.pq`**, que es exactamente lo que la spec exigia: la vista conserva
nombre, columnas y tipos, y solo cambia de donde lee. **F-078 queda cerrada del
todo, sin verificaciones pendientes.**

## F-083 · El estado de la FACTURA, que no es el del efecto (cerrada el 2026-09-16, APROBADO)

Tercera devolucion de un usuario de Negocio sobre el datamart en uso, y la
segunda de Administracion: Juan Romero pedia separar **el estado del EFECTO de
pago** —lo unico que se podia consultar, publicado por F-080 en
`compras.vencimientos`— **del estado de la propia FACTURA**.

El dato no esta en `dcf`: esta en **`con.est`**, la superclase, filtrando
**`tip = 15`**, y se traduce contra `raw.conest` **uniendo por la PAREJA (tipo,
estado)**, nunca solo por `estado_id`, porque el mismo codigo significa cosas
distintas en una obra, un contrato o una factura. Es la cuarta vez que la regla
de oro de Sigrid decide donde vive un campo que pareciamos buscar en la tabla
hija.

**EL HUMANO AMPLIO EL ALCANCE sobre la ficha original**: «la fecha metela, y
separa las 2. luego debe quedar muy claro en el diccionario». Asi que
`compras.facturas` publica **tres fechas separadas y explicadas** en vez de una
columna `fecha` ambigua.

**Evidencias del cierre**: `init.sh` exit 0, **4.879 pasan / 188 saltados**,
cobertura **94,3 %** (901/955), puerta de tamaño OK. El alcance de mutacion
salio **vacio de verdad** (recalculado por el reviewer: `lineas={}`), entregable
casi todo SQL. Diccionario publicado en la **version 23** (hash `cdbbe0996c67`,
153 objetos, 969 columnas) y `check-diccionario` en **codigo 0**.

**EL CRITERIO 6 lo cerro la pregunta que el correo no podia hacer**: de las
facturas vencidas y sin pagar, **5.233 estan en «Aprobado pago» (26,87 M EUR)**,
382 «Fra. GG Contabilizada», 106 «Aprobada Jefe de grupo», 49 «Contabilizada»,
**26 «Rechazada»**, 26 «Recibida», 16 «Aprobada por jefe de obra» y 15
«Aprobada Administracion».

**TRAMPA ANOTADA EN LA FICHA**: `APR`/`APR_DG` se llaman los dos «Aprobado
pago» y `REC`/`REC_ADM` los dos «Recibida». Se filtra **por mnemonico, nunca
por el literal**.

**FRONTERA DECLARADA EN LAS DOS FICHAS**: la **fecha de cambio de estado** se
queda en F-067, porque **no existe en Sigrid** —`concam` audita 1,5 M de
cambios y ni uno del campo `est`— y exige construir la foto diaria.

## F-034 · Power BI deja de leer de local y pasa a leer el datamart de Azure — `done` (2026-09-16)

Cerrada por decision del humano: «**f34 esta cerrada y hecha**». Y lo esta en lo
que se pedia: **Power BI Desktop lee del datamart de Azure y no del Postgres
local**, con **Import y no DirectQuery** —la decision (3) de la ficha, la que
protege a un servidor compartido de una consulta por cada clic—, y desde el
2026-09-16 carga `FactCPTipologia` sin tocar el `.pq`, que era el criterio 10 y
lo resolvio **F-078** bajando ese `SELECT` de «no termina» a **0,81 s**.

**LO QUE NO ESTA HECHO, medido contra la base el mismo dia y sacado a F-087**:
`pg_roles` tiene **un solo rol de lectura, `mcp_sigrid_dm_ro`**, y
**`pbi_sigrid_dm_ro` NO EXISTE**. Power BI se conecta con **el rol del MCP**,
que lee **todos los esquemas, `raw` y `stg` incluidos**. Eso deja abiertos los
criterios 2, 3 y 5: rol propio, contrasena en Key Vault y prueba negativa.

No es teorico: el **incidente 53300 del 2026-09-16** —«remaining connection
slots»— lo provocaron **17 conexiones ociosas de Power BI** que costo
identificar precisamente porque comparten `usename` con el MCP.

**Se cierra en vez de dejarla abierta a medias, y la deuda va a ficha propia con
su medicion**, que es lo que este arnes hace desde F-077 y F-081. Sigue fuera de
alcance **Power BI Service**, que exige gateway o abrir IP en un Postgres
compartido con albaranes y partes: no es decision de este proyecto en solitario.

## F-084 · El estado del CONTRATO (cerrada el 2026-09-17, APROBADO en pasada 1)

Mismo trabajo que F-083 pero para el contrato: el estado se lee de **`con.est`**
con **`tip = 44`** y se traduce contra `raw.conest` **por la PAREJA (tipo,
estado)**. Responde la pregunta que **Compras pidio en F-067** y que el circuito
de firma **no puede contestar**: cuales estan enviados y sin firmar.

**LO QUE APORTA DE NUEVO, y es lo que el criterio 6 pedia**: la traduccion se
**factoriza** en `compras.fn_estado_documento(p_tip, p_est)`, dentro de
`compras/00_setup.sql`. Lo que se gana no son las siete lineas del lateral: es
que **el tipo de documento pasa a ser argumento obligatorio de la firma**, y la
guarda anti-multiplicacion (`ORDER BY ide LIMIT 1`) se escribe una vez y protege
a **`contratos` y `facturas`** a la vez. La proyeccion de F-083 no cambia una
letra.

**EL REVIEWER ROMPIO EL SQL NUEVE VECES** para ver si los tests lo cazaban: las
nueve en ROJO (quitar el tipo del `WHERE`, quitarlo de la firma, recopiar el
lateral a mano, borrar una columna, renombrar otra, intercalar `estado_id`,
traducir el contrato con el `15`, quitar el `ORDER BY`, `STABLE` -> `IMMUTABLE`).
**Y corrigio al implementer en un punto que hay que retener**: la firma solo
impide **OMITIR** el tipo. Recopiar el lateral o pasar el tipo equivocado **si
compilarian**; eso lo cazan los tests, no la base. Que nadie los retire.

**Evidencias**: `init.sh` exit 0, **4.938 pasan / 188 saltados**, 57 tests
nuevos, `PUERTA TAMAÑO [OK]`. Mutacion **N/A con alcance vacio de verdad**
—`lineas={}`, ni un `.py` de produccion en el diff— y **prueba de control del
ENCARGO 1.7.11**: el generador da **136 mutantes** si se le ignora la exclusion,
luego el cero es por diseno y no por un motor roto.

**VERIFICADO EN LA BASE POR EL HUMANO**: `build-compras` exit 0 en 233,9 s —la
unica validacion real del CUERPO de la funcion—, **18.994 filas / 18.994
`contrato_id` / 100 % con estado**, los siete estados sumando exacto, y
diccionario en la **version 24**. Reparto: FIR 13.475, TER 3.179, **EPF 808**,
PFP 576, RFP 548, COMD 232, RES 176.

**LA DECISION MAS PENSADA: no se publica ninguna columna de antiguedad.**
`con.tiemod` existe —de los 808 enviados, casi todos llevan mas de 21 dias— pero
esta en epoca Delphi, vive en `raw` (que el MCP no ve) y, sobre todo, publicarlo
invita al «lleva X dias enviado», que **no es lo que significa**. La ficha dice
las tres cosas: que los ENVIADOS si se listan, que el «cuanto llevan» **no se
puede saber** hoy, y que eso es de **F-067** con su foto diaria.

**Y confirmo por tercera vez el cero que ya sabiamos**: de las 70.346 firmas de
`confir`, **ninguna es de contrato**, por las dos vias (`docide` y `conide`).

**DE PASO SALIERON TRES FICHAS**: **F-088** (el guardian de recuentos de F-006
acertaba por casualidad, y la guarda del catalogo falta en `05_vencimientos`) y
**F-089** (el MCP sirve un diccionario cacheado y llevaba catorce dias
desfasado), mas la correccion de una frase caducada de `current.md`.

## F-057 · El coste de personal por obra: el esquema `personal` (cerrada el 2026-09-22, APROBADO en pasada 4)

Por primera vez el datamart sabe **quien ha trabajado en una obra y cuantas horas**,
no solo lo que cuesta en material y subcontrata. Pedida por el humano y confirmada
con Juan Romero el 2026-09-03; subida a **prioridad 1** el 2026-09-17.

**UN ESQUEMA MODULO PROPIO, `personal`, y NO `stg`, por decision del humano**:
`build_stg` es puerta bloqueante —si falla, el `mart` no se construye esa noche— y
un esquema propio permite dar o quitar el acceso con un `GRANT`, que es lo que
necesitara **F-087**. Publica `personal.recursos`, `personal.partes_lineas` y la
vista `personal.v_pbi_horas_obra_mes`. Construido en **7,2 s**.

**LA TRAMPA QUE JUSTIFICA LA FEATURE**: `hmores.can` **no son horas**. Mezcla HORA,
DIA, MES y UD, y el clasificador es `auxhor.medide` —no `auxhor.ext`, a cero en las
60 filas—. Sumado en bruto da **1.837.201**, una cifra falsa; el **71,7 % del euro
esta en lineas de MES** (estructura de obra). La vista lleva `unidad = 'HORA'`
cableado. Tres decisiones mas, todas medidas: el eje es el **recurso** y no el
empleado (no es 1:1 en ninguna direccion); la obra la trae **la linea del parte**
(99,58 %), asi que la trampa del centro de coste no aplica; y «en rojo» es
**bandera y no filtro**, porque filtrar borraria el **43,2 %** de las horas.

**DATOS PERSONALES**: se publican **nombre y DNI**, con la autorizacion del humano
citada en el requisito («el dni puede salir, no es un problema», 2026-09-18). **Nada
mas** de la ficha del empleado.

**CUATRO PASADAS DE REVIEW, y merece contarse por que**:
* **Pasada 1, RECHAZO serio**: el SQL era correcto, pero **las dos guardas que
  justifican la feature no vigilaban nada**. La de datos personales era una **lista
  negra con 14 de 19 columnas inventadas**; con la Seguridad Social y el banco
  metidos en el SQL, **la suite pasaba 45 de 45**. Y la de la unidad no caia si
  una regla convertia los MESES en horas. Arreglado con **lista blanca**: el lateral
  lee exactamente cinco columnas del empleado, y el reviewer intento colar la
  Seguridad Social de cinco maneras sin conseguirlo.
* **Pasadas 2, 3 y 4**: siempre lo mismo, **frases que decian «nueve esquemas»**
  cuando con `personal` son diez. La primera estaba en lo que **se publica al MCP**.
  La 3 vio por que se escapaban: se buscaba la frase «nueve esquemas» y no el
  numero solo. Donde se pudo, **se quito el numero en vez de corregirlo**.

**Evidencias**: `init.sh` exit 0, **5.027 pasan**, cobertura **94,7 %**. Dos campanas
de mutacion con 4 workers; tres supervivientes equivalentes justificados.

**VERIFICADO EN LA BASE**: 2.618 recursos, **330.853 lineas**, `check-declarados`
158/158, las seis relaciones unen, diccionario en la **version 25**, y
`apply-grants` con `personal` y las cuatro tablas crudas de personal excluidas.

**LO QUE QUEDA FUERA**: el servidor MCP tiene su propia lista blanca de esquemas y
no incluye `personal`; eso no vive en este repositorio. Pasar de horas a euros con
el precio por recurso es **F-061**.

**DOS MEJORAS DEL ARNES QUE SALEN DE AQUI**, validas para cualquier proyecto: para
cerrar un conjunto, **lista blanca** —una negra solo protege de lo que alguien se
acordo de listar—; y si una feature cambia **cuantos** elementos tiene algo, se
busca **el numero viejo solo**, no la frase que lo acompana.

## F-094 · Retenciones infladas 4,3 veces: el estado VIVA y la obra real (cerrada el 2026-09-22, APROBADO en pasada 2)

Rama `feature/F-094-retenciones-estado-vivo`, `sdd=false`, rigor `estandar`.
Informe `progress/impl_F-094.md`; review `progress/review_F-094.md`.

**El defecto**: `retenciones.movimientos` decidia el estado solo con `pag.fecrea`
y no leia la ficha `con` del propio efecto, asi que contaba como VIVA los
originales agrupados, el agrupador AGR ya pagado y los anulados. El mismo dinero
contaba dos veces. Lo destapo Juan Romero con FERMALUX.

**El arreglo, sin borrar filas**: tres estados leidos de `raw.con` del efecto,
BAJA (`fecbaj` o `est` 14 Agrupados / 15 Divididos) > LIQUIDADA (`fecrea` o
`est` 10) > VIVA. Lo vivo a proveedor pasa de **35.544.786,07 a 8.345.506,03 EUR**
(7.752 efectos); **FERMALUX 64.201,96**, igual que su cuenta contable; 27.869
filas antes y despues. Las vistas no suman BAJA en neto ni cargos/abonos.

**Absorbe el resto de F-045** (decision H6 de F-095): `obra_id` es la obra real
traducida con `maestro.centros_coste` y el centro va en `centro_coste_id`;
**262 de 262** casan con `maestro.obras` (antes 0). F-045 se retira del backlog.
**Rompe** a quien una por el centro de coste (Power BI): ahora se une por `obra_id`.

**Lado cliente sin tocar, a proposito**: sus 19,9 M EUR con baja estan en estado
1 (Pendiente) y el criterio de proveedor dejaria 2,12 M frente a 13,81 M en
contabilidad. Queda para una feature propia (H5 de F-095).

**Diccionario version 26**: fuera los 34,7 M EUR de los ordenes de magnitud,
dentro 8,35 M; cliente marcado sin verificar. `init.sh` exit 0, 5.043 pasan,
cobertura 94,7 %. Mutacion N/A justificado (0 mutantes: el Python tocado son
comentarios; 16 tests fijan el texto exacto de cada CASE).

**Pendiente del humano**, en `current.md`: `build-retenciones` → `check-unicidad`
→ `check-relaciones` (antes del build sale KO por la relacion nueva) →
`publicar-diccionario`, reiniciar el MCP por su cache (F-089) y el parrafo para
`azure-apps/datamart_seg_anual.md`.

## F-101 · HOTFIX de F-057: cabecera del parte, codigo y texto de linea, tipos de hora y precios del recurso (cerrada el 2026-09-23, APROBADO en pasada 2)

Correo de Juan Romero del 22-09. Entran `personal.partes` (6.886 cabeceras,
estado En registro/Cerrado/Imputado, obra y centro de cabecera sufijados
`_cabecera_id`, `lineas_en_otra_obra`: 615 lineas en 14 partes) y
`personal.recursos_tipos_hora` (precios de la ficha, `es_por_defecto`, sin
`prenom`); `partes_lineas` gana `codigo_parte` y `texto_linea` (`hmores.tex`
pasa a ingerirse). Diccionario version 28. Hallazgo: el 56,2 % de las lineas
comparables lleva un precio distinto del de la ficha, que solo guarda el de hoy.
Fuera: el usuario creador del parte, en `dbo.log` (F-105). Pasada 1 RECHAZADA
por dos temas de datos personales, resueltos por el humano: exposicion de
`hmores.tex` en `raw.hmores` ACEPTADA por escrito, y nombre redactado con un
commit nuevo sin reescribir historial. Detalle: `progress/impl_F-101.md`,
`progress/review_F-101.md`, `progress/spec_F-101.md`.

## F-102 · HOTFIX 2: identificadores por empresa para obras y recursos (cerrada el 2026-09-24, APROBADO en pasada 2)

Correos de Juan Romero del 22-09 (obra dada de alta en la empresa 1 y en la 28)
y del 23-09 (`codigo_recurso` no unico). Modelo del humano: las obras son POR
EMPRESA y no se consolidan. `maestro.obras` gana `empresa_id`, `nombre_empresa`
(se ingiere `auxemp`), `clave_obra` ('<empresa>-<codigo>'), `num_fichas_codigo`,
`es_ficha_principal` (la de Ruesma) y `obra_principal_id` (solo aqui, con aviso
de no agregar hechos de otras empresas); `personal.recursos` gana `empresa_id`,
`nombre_empresa` y `clave_recurso`; las vistas de consumo de `compras` publican
`empresa_id` y `clave_obra`. Regla `R-CODIGO-POR-EMPRESA`, diccionario version
29. `stg.obras` NO cambia (difiere de la ficha de Ruesma en 0581, 0606, 0671 y
0720): lo resuelve F-106. Pasada 1 rechazada solo por papeleo; desviacion 6
declarada (`check-unicidad` no vigila las claves nuevas). Detalle:
`progress/impl_F-102.md`, `progress/review_F-102.md`, `progress/spec_F-102.md`.

## F-107 · Contrapartidas del recurso y catalogo de cuentas analiticas (cerrada el 2026-09-24, APROBADO en pasada 2)

Correo de Juan Romero del 23-09 18:02. La contrapartida es del RECURSO
(`res.cenconide`, `res.caaconide`), no de `reshor`: `personal.recursos` gana
`centro_coste_contrapartida_id` y `cuenta_analitica_contrapartida_id`. Se
ingiere `caa` (184.234 cuentas) y se publica `maestro.cuentas_analiticas`
(codigo, descripcion, empresa, padre con su codigo y nombre, nivel, centro,
partida). Ampliada por el humano: `personal.partes_lineas.cuenta_analitica_id`
(`hmores.caaide`, 93,8 % de las lineas, 0 huerfanas), que es la cuenta de CARGO
del centro de la obra. Diccionario version 30. Pasada 1 rechazada por una frase
ambigua de la ficha y el formato de la mutacion. Detalle:
`progress/impl_F-107.md`, `progress/review_F-107.md`.

## F-095 · Retenciones desde la contabilidad, cuadradas con los efectos, por obra y con vencimiento desde el fin de obra (cerrada el 2026-09-25, APROBADO en pasada 2)

Rigor `critico`. Cuatro sub-pasos nuevos en `retenciones` (`03`-`06`): cuentas
de retencion por `prv.cueretide`, un apunte contable por fila (se ingiere `rac`,
71 tablas), saldo por proveedor y obra con el saldo inicial de 2008 y la
apertura de 2016 exactos (8,78 M EUR el 24-09), obra por cascada APUNTE ->
FACTURA -> EFECTO -> PROVEEDOR_UNA_OBRA, fin de obra (H1: inicio de garantia;
si no, ultimo cierre + 1 mes) y plazo (`plaret` -> `plagar` -> 12 meses), y el
cuadre contra la VIVA de los efectos de F-094 en 5 categorias. Diccionario
version 31. Pasada 1 RECHAZADA por la mutacion (11 de 16 mutantes del reviewer
sobrevivian, el nucleo del cuadre entre ellos); pasada 2: contrato del SQL
expresion a expresion y campana sistematica de 264 mutantes, 0 supervivientes.
**F-059 retirada** («las retenciones son ciegas antes de 2016»): absorbida por
F-095, decision H6 del humano. Detalle: `progress/impl_F-095.md`,
`progress/review_F-095.md`, `progress/mutacion_F-095.md`.

## F-108 · Claves alternativas en el diccionario y en `check-unicidad` (cerrada el 2026-09-25, APROBADO)

Opcion B del humano (desviacion 6 de F-102): las fichas declaran
`claves_alternativas`; `check-unicidad` las comprueba (NULL excluidos, sale con
1 si una se rompe; no esta en `run-all`) y el validador de F-006 acepta una
alternativa de una columna como lado 1, asi que las cinco relaciones de
`compras` por `clave_obra` pasan a N:1. Seis claves declaradas
(`maestro.obras.clave_obra`, `personal.recursos.clave_recurso`,
`maestro.v_obra_fichas.clave_obra`, `maestro.cuentas_analiticas (empresa_id,
codigo_cuenta)`, `maestro.centros_coste (empresa, codigo_centro)`,
`stg.obras.codigo_obra`). Diccionario version 33. Servir las claves al agente es
cosa de `mcp-bbdd` (D4). Detalle: `progress/impl_F-108.md`,
`progress/review_F-108.md`.
