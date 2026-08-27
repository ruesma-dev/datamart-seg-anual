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
