<!-- specs/F-023-cierre-operativo-f003/design.md -->
# F-023 · Cierre operativo de F-003 — Diseño técnico

## 1. Naturaleza de la feature: casi nada es código

F-023 no añade capacidad al ETL. Todo lo que hace falta ya existe y está
probado: F-004 construyó la lectura de blobs con `DefaultAzureCredential`,
F-003 creó la cuenta, el contenedor, el vault, la identidad y el job. Lo
que falta es **ejecutar**: poner los ficheros donde el job los espera,
comprobar que se leen de verdad, retirar los duplicados de seguridad que ya
sobran y recoger el andamiaje del puesto.

Por eso el reparto es deliberadamente asimétrico:

| Bloque | Naturaleza | Quién lo ejecuta |
|---|---|---|
| 0 · invariantes (R1–R4) | Tests nuevos, sin red ni BBDD | El implementer |
| 1 · Excels y verificaciones de F-004 (R5–R11) | Operación Azure | **MANUAL (humano)** |
| 2 · secretos duplicados (R12–R15) | Operación Azure destructiva | **MANUAL (humano)**, con OK explícito |
| 3 · limpieza del puesto (R16–R20) | Operación puesto + Azure destructiva | **MANUAL (humano)**, con OK explícito para el firewall (R18) |
| 4 · documentación y cierre (R21–R24) | Markdown y `init.sh` | El implementer |

El implementer **no abre ninguna conexión a Azure, a Postgres ni a
`sigrid-api`**. Escribe tests y documentación, y transcribe a
`progress/impl_F-023.md` los resultados reales que el humano le pase de
cada verificación MANUAL: comando, salida relevante y hora.

## 2. Hallazgo que corrige la premisa de la feature

La `description` de F-023 en `harness/features.json` dice que hay que
«cambiar las `AUX_EXCEL_*` de `infra/env/dev.json` a URIs de blob (hoy
apuntan a rutas locales de OneDrive)». **Leído el árbol, eso no es cierto**:

- `infra/env/dev.json` **no tiene** claves `AUX_EXCEL_*`. Tiene
  `storageAccount`, `auxContainer` y `auxBlobs` (tres nombres de fichero).
- `infra/80_create_job.ps1` §4 compone
  `$baseAux = "https://{0}.blob.core.windows.net/{1}"` y de ahí las tres
  variables del contenedor. El job desplegado el 2026-08-17 se creó con ese
  script.
- Las rutas de OneDrive viven en el **`.env` del puesto** (no versionado),
  corregidas a mano el 2026-08-16 (`progress/current.md`).

**Consecuencia de diseño**: no hay cambio de configuración que hacer en el
repositorio. Lo que sí falta es (a) **verificar** contra Azure que el job
desplegado tiene realmente esas tres variables como URIs de blob, y (b)
**fijar el invariante con tests** para que la premisa no pueda volverse
verdadera por descuido. Si (a) revelara que el job desplegado no las tiene,
se aplica el plan ya decidido en **DA-6** (§9): corregirlas a mano con
`az containerapp job update --set-env-vars`, dejar el comando escrito en
`infra/README.md` y anotar la carencia del guion de despliegue como
backlog. **No se recrea el job** y **no se toca `infra/env/dev.json`**, que
ya declara lo correcto.

## 3. Ficheros a crear

| Ruta | Qué contiene |
|---|---|
| `tests/test_f023_cierre_operativo.py` | Los **cinco** tests de R1–R4 (R1 lleva dos: el positivo y su control negativo). Sin red, sin BBDD, sin Azure: leen `infra/env/dev.json`, `infra/*.ps1` y el árbol del paquete, igual que hace `tests/test_f003_infra.py`. |
| `progress/impl_F-023.md` | Informe del implementer: evidencias, y el **acta de cada verificación MANUAL** con comando, salida real y hora. Es la única evidencia que verá el reviewer de los bloques 1–3. Con rigor `critico` (DA-1) el acta de cada **borrado** debe además citar literalmente el OK del humano, con fecha y hora. |
| `progress/mutacion_F-023.md` | Informe de la campaña de mutación, generado por `python -m harness.mutacion`. Dará **cero mutantes** (§11): el diff no lleva código de producción. Cero es un dato que se ejecuta y se pega. |

### Tests, uno por uno

- `test_f023_r1_las_aux_excel_del_job_son_uris_de_blob` — parsea
  `80_create_job.ps1`, localiza las tres asignaciones `AUX_EXCEL_*=` y
  comprueba que cada valor se compone de `$baseAux` y de
  `$CFG.auxBlobs.<clave>`, y que `$baseAux` se construye con
  `$CFG.storageAccount`, `$CFG.auxContainer` y el sufijo
  `blob.core.windows.net`. Reutiliza los ayudantes `_script()` / `_config()`
  de `tests/test_f003_infra.py` (importados, no copiados).
- `test_f023_r1_ninguna_aux_excel_del_job_lleva_ruta_local_ni_sas` — control
  negativo del anterior: ninguna de las tres líneas contiene `:\`, `\\`,
  `~`, `OneDrive` ni `?`.
- `test_f023_r2_los_tres_auxblobs_son_nombres_de_fichero_xlsx` — sobre
  **todos** los ficheros de `infra/env/*.json` (no solo `dev`), los tres
  valores de `auxBlobs` terminan en `.xlsx`, no contienen `/`, `\`, `:`,
  `?` ni `~`, y coinciden con su forma recortada (`strip()`): el espacio
  colado ya rompió las rutas del `.env` el 2026-08-16.
- `test_f023_r3_ni_el_codigo_ni_infra_mencionan_rutas_de_onedrive` — barrido
  de `etl_sigrid/`, `config/`, `main.py` e `infra/` (`*.ps1` y `env/*.json`)
  buscando `OneDrive`, `tablas_auxiliares` y `Documentos`. **Alcance
  acotado a propósito**: `progress/`, `specs/`, `BACKLOG.md` y `docs/`
  quedan fuera porque ahí esas palabras son historia legítima y el test
  sería un falso positivo permanente (la lección de
  `test_f005_r21_barrido_de_secretos`, que se puso rojo por una ruta larga
  en un documento).
- `test_f023_r4_el_job_no_fija_el_tamano_de_pagina_de_la_api` — la lista de
  variables que `80_create_job.ps1` inyecta **no** contiene
  `SIGRID_API_PAGE_SIZE`; reutiliza `_env_vars_del_job()` de
  `test_f003_infra.py`.

## 4. Ficheros a modificar

| Ruta | Qué cambia |
|---|---|
| `infra/README.md` | §«Verificaciones heredadas de F-004»: los comandos exactos de R5–R10 y el resultado (fecha) de cada una. §3 «Paso 8 bis»: el párrafo «las copias viejas no se borran todavía» pasa a decir que **se retiraron** (fecha) y que la vuelta atrás es el soft-delete del vault de origen. §2 «Autorizar la IP del job»: el flag del servidor confirmado con `--help` (defecto anotado en `progress/current.md`) y una subsección nueva **«Volver a autorizar el puesto cuando haga falta»** con el comando de creación completo, la convención de nombre datado y el criterio de borrar la regla al terminar (**DA-2, opción A**: el puesto no conserva ninguna regla fija). Subsección nueva **«Cambiar una variable de entorno de un job vivo»** con `az containerapp job update --set-env-vars` y la advertencia de comprobar después que las referencias a secretos siguen en su sitio (**DA-6, opción A**). |
| `azure-apps/datamart_seg_anual.md` | Fila de «Qué consume» de los Excels: dejan de ser un *stub*; se leen del contenedor `aux` de la cuenta del proyecto por identidad gestionada con `Storage Blob Data Reader`, y sus URIs se componen en `infra/env/dev.json`. Sección nueva **«Dónde viven los secretos»**: solo el Key Vault del proyecto, por **nombre** (jamás un valor), y constancia de que ya no hay copia en el vault de `albaranes`. Corrección del encabezado «Estado: EN LOCAL, sin desplegar» y de las dos frases «hoy no existe ningún Container Apps Job» / «hoy: PostgreSQL local del puesto», que llevan desde el 2026-08-08 contradiciendo la realidad. |
| `specs/F-003-infra-caj/tasks.md` | T23–T26 marcadas `[x]` con su fecha, y las tres verificaciones de F-004 añadidas como tareas marcadas con su resultado (R22). |
| `progress/current.md` | Estado de F-023 y de F-003 al cerrar, las dieciséis verificaciones MANUAL listadas con su comando (C4), los dos defectos que quedan para el backlog (R23) y el puntero al informe. **No quedan decisiones abiertas de F-023**: las siete se cerraron el 2026-08-18 (§9), y el asunto de `SIGRID_API_PAGE_SIZE` no vuelve como pendiente (DA-4). |

**`azure-apps/` es otro repositorio**: se edita en su ruta
(`C:\Users\pgris\PycharmProjects\azure-apps`) y lleva **su propio commit**,
no entra en la rama de esta feature. El humano tiene el remoto de
`azure-apps` en baja prioridad, así que basta con el commit local.

## 5. Ficheros y recursos que NO se tocan

- **La carga de los Excels a `aux.*`: es F-013.** Aquí no se crea ninguna
  tabla `aux.*`, no se escribe ni una fila y no se decide ningún modelo
  destino. `load-aux` **lee y valida**; que su docstring diga «(pendiente)»
  es correcto y se queda como está.
- **`infra/env/dev.json`**: no cambia. Ya declara lo correcto (§2).
  **Tampoco cambia bajo el plan de DA-6**: ese plan corrige el *job
  desplegado* con `az containerapp job update`, no el fichero de entorno,
  que es justamente la fuente de la que se compondrían bien las variables.
- **`etl_sigrid/`, `config/`, `main.py`**: ni una línea de producción. Si
  una verificación MANUAL destapa un defecto de código (caso típico: el
  mensaje de permisos de R11), **no se parchea aquí**: se anota y se abre
  feature.
- **`.env`, `.env.azure.bak`, `.env.local.bak`**: son del humano y están
  prohibidos para los agentes. Las URIs de blob de R7 las escribe él.
- **`harness/features.json`**: el cambio de `sdd`, de `status` y de `rigor`
  (a `critico`, DA-1) lo hace **el líder**, no esta spec ni el implementer.
- **`80_create_job.ps1` y el resto de `infra/*.ps1`**: no se modifican. El
  job desplegado no se recrea ni se reprograma; su `cron`, su
  `replicaTimeoutSeconds` y sus secretos se quedan como están.
- **En `kv-albaranes-rs9k2`, todo lo que no sean los dos secretos del
  datamart.** Ni se listan con detalle ni se leen.
- **En `psql-albaranes-rs9k2`**: nada a nivel de servidor (parámetros,
  autenticación, almacenamiento), y de las reglas de firewall **solo** las
  `datamart-puesto-*`, que se retiran todas (DA-2). La del entorno del job y
  la de servicios de Azure se quedan (R18), y las dos ajenas —`ClientPgris`
  y `FirewallIPAddress_2026-6-16`— **no se tocan** por decisión cerrada
  (DA-3, R19).
- **F-024 Fase C**: no se ejecuta desde aquí. F-023 depende de ella (§7),
  no la sustituye.

## 6. Capa hexagonal y SQL

**Ninguna.** No hay clases ni funciones nuevas, no hay SQL nuevo, no se
crea ni se altera ningún esquema. Lo único que se añade al paquete Python
es un fichero de tests, que no pertenece a `domain`, `application` ni
`infrastructure`: vive en `tests/` y verifica artefactos de despliegue,
igual que `tests/test_f003_infra.py`.

## 7. Orden de ejecución (no es estético: es funcional)

Este orden está **cerrado por DA-7**: el bloque 3 va después de que la Fase C
de F-024 (T17–T20) esté completa. No hay variante «ejecutar F-023 entera
antes y recrear la regla más tarde».

```
   [tests R1–R4]                     (implementer, sin red)
        │
        ▼
   Bloque 1  ── subir Excels → roles → verificación 1 → verificación 2 → verificación 3 (+restaurar rol)
        │        exige: firewall del puesto VIVO (load-aux abre Postgres)
        ▼
   Bloque 2  ── precondiciones → OK del humano → borrado → job sigue OK
        │        exige: ejecución correcta del job (ya la hay, 18-ago)
        ▼
   [F-024 Fase C, T17–T20]           ← se ejecuta desde el puesto
        │
        ▼
   Bloque 3  ── hosts → (esperar) → firewall del puesto → decisión page_size
        │        el firewall va AL FINAL: retirarlo antes deja al humano sin acceso
        ▼
   Bloque 4  ── README + azure-apps + tasks.md de F-003 + init.sh verde
```

Tres dependencias duras que conviene tener escritas porque son fáciles de
romper por prisa:

1. **`load-aux` necesita Postgres**, no solo el blob (abre ejecución en
   `_meta` antes de leer). Sin regla de firewall del puesto, R7 y R10
   fallan por una razón que no tiene nada que ver con lo que se está
   probando.
2. **`load-aux` marca `ABORTED` las filas `RUNNING`** (F-024). Ejecutarlo
   con el job en marcha corrompe la contabilidad de esa ejecución y puede
   cerrar su puerta de coherencia. De ahí la comprobación obligatoria de
   R8.
3. **La verificación 3 retira permisos y hay que devolverlos.** Es el único
   paso de la feature que deja el entorno peor si se interrumpe a la mitad.
   Va emparejado con su restauración en la misma tarea, y la tarea no está
   hecha hasta que `load-aux` vuelve a dar `SUCCESS`.

## 8. Límite de microservicio

Se ha evaluado, porque dos de los tres bloques tocan recursos que **no son
de este proyecto**:

- `kv-albaranes-rs9k2` y `psql-albaranes-rs9k2` son de `albaranes`. Lo que
  F-023 hace ahí es **retirar la huella que este proyecto dejó** (dos
  secretos que nacieron ahí por falta de vault propio, y unas reglas de
  firewall para el puesto). No se añade responsabilidad nueva: se devuelve
  el recurso a su estado. **No procede extraer nada a otro microservicio**;
  procede el protocolo que ya rige el repositorio: autorización expresa del
  humano, recurso a recurso, y él ejecuta.
- El único candidato real a servicio propio que aparece de refilón es
  **subir y mantener los Excels sin pasar por un técnico**, y ya está
  reconocido como **F-010**. F-023 sube los ficheros **a mano y una vez**,
  que es exactamente lo que F-004 declaró suficiente («F-004 no depende de
  F-010: basta con que el ETL lea del blob, aunque el fichero se suba a
  mano»). Nada de lo que se hace aquí prejuzga el diseño de F-010.
- Se comprobó que **ningún documento de `azure-apps/` menciona
  `kv-albaranes-rs9k2`** y que `albaranes.md` no habla de los secretos del
  datamart: por tanto el borrado del bloque 2 **no obliga a actualizar el
  documento de otro proyecto**, solo el propio (R21).

## 9. Decisiones cerradas (2026-08-18, por el humano)

Las siete decisiones que esta spec dejó abiertas fueron respondidas por el
humano el **2026-08-18** con «acepto la recomendación» en las siete. Aquí
quedan como **decididas**: no hay bifurcaciones pendientes en el resto de la
spec, y ninguna tarea puede escudarse en «según DA-x».

### DA-1 · Rigor de la feature — CERRADA 2026-08-18: `critico`

El nivel es **`critico`**, no `estandar`. Motivo, con la definición de
`CHECKPOINTS.md`: «infraestructura compartida, producción, seguridad o
dinero» — los bloques 2 y 3 borran cosas en producción **de otro proyecto**
(`kv-albaranes-rs9k2`, `psql-albaranes-rs9k2`).

Efecto en la spec, según `harness/rigor.json`:

- **Fase RED obligatoria** para los cinco tests nuevos. Como el entregable
  *es* el propio test, la fase RED se demuestra rompiendo deliberadamente
  —en una copia aislada, **nunca en el árbol real**— lo que cada test
  vigila, y pegando la traza real del fallo (§11 y T2).
- **Cobertura de las líneas cambiadas**: la puerta se ejecuta igual; saldrá
  con alcance vacío y se declara con el número real que dé la herramienta.
- **Campaña de mutación**: se ejecuta y se pega la salida. Dará **cero
  mutantes** porque el diff no lleva ni una línea de código de producción.
  `supervivientes_maximos: 0` se cumple trivialmente, pero **no vale
  declararlo «no aplica» sin ejecutar**.
- **Cada borrado necesita su acta**: el OK del humano citado literalmente,
  con fecha y hora, en `progress/impl_F-023.md`. Afecta a R14 (los dos
  secretos de `kv-albaranes-rs9k2`) y a R18 (las reglas de firewall del
  puesto): son las dos escrituras destructivas de la feature.
- **Las dieciséis verificaciones MANUAL** (R5–R20) van listadas con su
  comando exacto y su **resultado real**; sin resultado real no hay
  verificación, y el reviewer las recorre una a una.

El cambio de `rigor` en `harness/features.json` lo hace el líder.

### DA-2 · Acceso del puesto al Postgres — CERRADA 2026-08-18: opción A

Se retiran **todas** las reglas `datamart-puesto-*` de
`psql-albaranes-rs9k2`. El puesto **no conserva ninguna regla fija**: cuando
haga falta acceso, se recrea una bajo demanda con el comando documentado en
`infra/README.md` y se borra al terminar.

Motivo: las direcciones de esas reglas están caducadas (la IP del humano
rota; ya hubo que crear `-2026-08-16`, `-16b` y una de rango el `-08-17`),
así que dejarlas es una puerta abierta que además no sirve.

Comando que **debe quedar escrito** en `infra/README.md`, subsección
«Volver a autorizar el puesto cuando haga falta» (y que R18 reproduce):

```powershell
# 1. Confirmar el flag del servidor que admite la version de az instalada.
#    Defecto anotado en progress/current.md: el README usaba -n y az exige
#    --name / --server-name. Se comprueba, no se supone.
az postgres flexible-server firewall-rule create --help

# 2. IP publica de salida del puesto. NO se escribe en el repositorio:
#    se usa en el comando y se olvida.
(Invoke-RestMethod "https://api.ipify.org?format=json").ip

# 3. Crear la regla con nombre DATADO, para que se vea cuando caduca:
az postgres flexible-server firewall-rule create -g <pgResourceGroup> --name psql-albaranes-rs9k2 `
  --rule-name datamart-puesto-pgris-<AAAA-MM-DD> `
  --start-ip-address <ip> --end-ip-address <ip>

# 4. Comprobar:
az postgres flexible-server firewall-rule list -g <pgResourceGroup> --name psql-albaranes-rs9k2 -o table

# 5. AL TERMINAR EL TRABAJO, borrarla. Es parte del mismo trabajo, no un
#    "ya lo limpiare": la regla caducada es la deuda que F-023 esta cerrando.
az postgres flexible-server firewall-rule delete -g <pgResourceGroup> --name psql-albaranes-rs9k2 `
  --rule-name datamart-puesto-pgris-<AAAA-MM-DD> --yes
```

Nota que el README debe llevar: si el operador del humano rota la IP dentro
de una subred durante el trabajo (pasó el 2026-08-17), se crea **una sola
regla de rango** con el nombre datado y sufijo `-rango`, en vez de ir
añadiendo una regla por dirección. Sigue siendo temporal y se borra igual.

Es una **escritura sobre un recurso de `albaranes`**: autorización expresa
del humano y la ejecuta él, cada vez.

### DA-3 · `ClientPgris` y `FirewallIPAddress_2026-6-16` — CERRADA 2026-08-18: no se borran

**No se tocan.** Son de `albaranes`, anteriores a este proyecto, y este
proyecto no tiene por qué saber quién las usa. Queda escrito **a propósito**:
que sigan ahí después de F-023 no es un olvido de la limpieza, es la
decisión. R19 pasa de «borrarlas si el humano confirma» a «dejarlas y dejar
constancia».

### DA-4 · `SIGRID_API_PAGE_SIZE` — CERRADA 2026-08-18: solo el `.env` del puesto

El job **no** inyecta esa variable (R4, con test), así que la carga nocturna
usa el valor por defecto de `config/settings.py`. Lo que quede en el `.env`
del puesto es cosa del humano y **el `.env` no se versiona**:

- **No se toca `.env.example`**, que refleja el defecto del código. Cambiar
  ese defecto sería otra feature, no esta.
- **Ningún agente edita `.env` ni los `.bak`.**
- Se anota en el informe qué valor deja el humano y por qué (fue un apaño
  para una red inestable), y **el asunto queda cerrado**: no vuelve como
  decisión pendiente a `progress/current.md`.

### DA-5 · Defecto de `60_create_identity.ps1` — CERRADA 2026-08-18: al BACKLOG

**No se arregla en F-023.** No pertenece a ninguno de los tres bloques y
ampliaría el alcance de una feature que es de operación. Lo que sí hace
F-023 es dejar la descripción completa para que el líder pueda **dar de alta
la feature de backlog sin volver a investigarlo** (R23):

> **Defecto · `infra/60_create_identity.ps1` verifica los roles antes de que
> RBAC propague y aborta con un `throw` falso.**
>
> - **Dónde**: bloque «4. Verificacion», líneas ~96–108. Justo después de
>   crear las tres asignaciones (líneas 79–89) lista
>   `az role assignment list --assignee <principalId> --all`, calcula
>   `$faltan` contra los tres roles esperados (`AcrPull`,
>   `Key Vault Secrets User`, `Storage Blob Data Reader`) y, si la lista
>   sale incompleta, hace `throw "faltan permisos por asignar: ..."`.
> - **Por qué falla**: la asignación de roles en Azure RBAC es de
>   **consistencia eventual** — se crea correctamente pero tarda hasta unos
>   minutos en aparecer en las lecturas. El `throw` salta con las tres
>   asignaciones ya creadas: es un **falso negativo** que aborta el guion de
>   despliegue y hace creer al operador que le faltan permisos.
> - **Lo que el script sí hace bien, y por qué despista**: en las líneas
>   52–59 ya espera —hasta 12 intentos de 5 s— a que el **directorio**
>   publique el principal, para evitar `PrincipalNotFound`. Esa espera cubre
>   la publicación de la identidad, **no** la propagación de las
>   asignaciones, que es un problema distinto y posterior.
> - **Arreglo propuesto**: envolver la verificación (96–108) en el mismo
>   patrón de reintento con espera que ya usan las líneas 52–59 —p. ej. 12
>   intentos de 10 s, releyendo `$asignados` en cada vuelta— y hacer `throw`
>   **solo** si tras agotar los reintentos siguen faltando roles. El aviso
>   de permisos «que sobran» (líneas 110–114) se queda como está.
> - **Gravedad**: baja pero engañosa. El script es idempotente, así que
>   repetirlo suele pasar a la segunda; el daño es el tiempo perdido y la
>   desconfianza en un despliegue que en realidad había funcionado.
> - **Verificación del arreglo**: test de artefacto sobre el script (que el
>   bloque de verificación contiene un bucle de reintento y que el `throw`
>   está fuera de la primera pasada), en la línea de `tests/test_f003_infra.py`.

**Mitigación durante F-023**, allí donde la propagación de RBAC importa
(R6 y R10, que asignan y retiran roles de datos de blob al humano):
**esperar un par de minutos y repetir el comando de lectura antes de
concluir nada**. Un `AuthorizationPermissionMismatch` inmediatamente después
de asignar un rol no es un fallo de la feature.

### DA-6 · Si el job desplegado no tuviera las `AUX_EXCEL_*` como URIs — CERRADA 2026-08-18: opción A

Se corrigen **a mano** con `az containerapp job update --set-env-vars`, se
documenta el comando en `infra/README.md` y se anota la carencia del guion
de despliegue como backlog. **No** se borra ni se recrea el job (perdería el
historial de ejecuciones y habría que reprogramar el `cron`).

Carencia que va al backlog, descrita para que el líder no tenga que
reinvestigarla: **`80_create_job.ps1` se niega a correr si el job ya
existe** y **`85_update_job.ps1` solo cambia la imagen**, de modo que hoy
**no hay camino soportado por los guiones para cambiar una variable de
entorno de un job vivo**; la única vía es `az` a mano, fuera del
versionado. Arreglo natural: que `85_update_job.ps1` reconcilie también las
variables de entorno a partir de `infra/env/<entorno>.json`.

Comando que va al README, subsección «Cambiar una variable de entorno de un
job vivo»:

```powershell
az containerapp job update -g <resourceGroup> -n <job> `
  --set-env-vars "AUX_EXCEL_TIPO_PARTIDA=https://<storageAccount>.blob.core.windows.net/<auxContainer>/TipoPartida.xlsx" `
                 "AUX_EXCEL_TIPO_COSTE=https://<storageAccount>.blob.core.windows.net/<auxContainer>/TipoCoste.xlsx" `
                 "AUX_EXCEL_MAPEO_PROPORCIONALES=https://<storageAccount>.blob.core.windows.net/<auxContainer>/mapeo_proporcionales.xlsx"

# Comprobacion OBLIGATORIA despues: que siguen ahi TODAS las demas variables
# y, sobre todo, la referencia a secreto que resuelve PG_PASSWORD.
az containerapp job show -g <resourceGroup> -n <job> `
  --query "properties.template.containers[0].env" -o json
```

Se espera **no** tener que usarlo: R9 y la fotografía de T3 deberían
confirmar que ya son URIs de blob. Si hay que usarlo, la ejecución es
MANUAL del humano y su acta va al informe como cualquier otra.

### DA-7 · Orden respecto a F-024 — CERRADA 2026-08-18: se acepta

El bloque 3 (limpieza del firewall del puesto) va **después** de que la
**Fase C de F-024 (T17–T20)** esté completa, tal y como describe §7.
Desaparece la alternativa de ejecutar F-023 entera antes y recrear la regla
después: R17 y T14 son ahora una **puerta**, no una elección.

## 10. Riesgos, y qué los contiene

| Riesgo | Contención |
|---|---|
| Borrar un secreto de producción y no poder volver atrás | R12 (c) exige soft-delete comprobado **antes**; R13 para la feature si no lo hay; R14 prohíbe `purge` y deja la recuperación documentada |
| El valor de un secreto acaba en pantalla, en el historial o en un fichero | `az keyvault secret show` está **prohibido** sobre esos nombres en toda la feature; toda comprobación es `secret list` (nombres) |
| La verificación 3 se interrumpe y el humano queda sin permisos sobre la cuenta | La restauración es parte de la **misma** tarea; R10 exige contrastar la lista de roles contra la fotografía de R6 y volver a ejecutar `load-aux` |
| Retirar la regla del firewall equivocada y apagar la carga nocturna | R18 nombra explícitamente qué debe **permanecer**; el listado posterior es la evidencia |
| Retirar el firewall del puesto antes de tiempo y bloquear F-024 | R17 como **puerta** (DA-7) y el orden de §7; T14 no se salta |
| Quedarse sin acceso al Postgres desde el puesto tras la limpieza | DA-2 opción A lo asume: el acceso se recrea bajo demanda con el comando del README, que R18 y el propio README dejan escrito y probado |
| Concluir «faltan permisos» cuando lo que falta es que RBAC propague | DA-5: esperar y repetir la lectura antes de concluir nada, en R6 y R10 |
| `load-aux` desde el puesto pisa una ejecución del job | R8: comprobación obligatoria de ejecuciones en `Running` y prohibición de la ventana nocturna |
| Subir un Excel con el nombre mal escrito: el job falla de madrugada | R5 compara el listado del contenedor contra `auxBlobs`; R2 impide que el nombre declarado deje de ser un nombre de fichero |
| Que la feature «se dé por hecha» sin evidencia real | Todo MANUAL lleva comando exacto y su salida real va a `progress/impl_F-023.md`; el reviewer valida contra eso |

## 11. Cómo se satisfacen las puertas de `CHECKPOINTS.md` con rigor `critico`

El nivel es **`critico`** (DA-1, cerrada). Lo que exige ese nivel sale de
`harness/rigor.json`: fase RED, cobertura, mutación, **cero supervivientes**
y las verificaciones `MANUAL (humano)` con comando exacto y resultado real.
Punto por punto, y sin ningún «no aplica» sin ejecutar:

- **Fase RED (C4 bis)**: aplica a los **cinco** tests nuevos. Aquí el
  entregable *es* el test —no hay código de producción cuyo fallo previo
  enseñar—, que es exactamente el caso que `CHECKPOINTS.md` contempla: la
  fase RED se demuestra **rompiendo deliberadamente, en una copia aislada y
  nunca en el árbol real**, lo que cada test vigila, y pegando la traza real
  del fallo. Las cinco roturas, una por test:
  1. `test_f023_r1_..._son_uris_de_blob`: texto de script de prueba en el
     que `AUX_EXCEL_TIPO_PARTIDA` se compone de algo que no es `$baseAux`.
  2. `test_f023_r1_ninguna_..._ruta_local_ni_sas`: el mismo texto con una
     ruta local (`D:\...`) y con una query string (`?sv=...`).
  3. `test_f023_r2_..._nombres_de_fichero_xlsx`: copia temporal del fichero
     de entorno con un `auxBlobs` que lleve carpeta y un espacio final.
  4. `test_f023_r3_ni_el_codigo_ni_infra_...`: fichero temporal, dentro del
     árbol de prueba que barre el test, con la palabra `OneDrive`.
  5. `test_f023_r4_el_job_no_fija_el_tamano_de_pagina`: lista de variables
     de prueba que incluya `SIGRID_API_PAGE_SIZE`.
  Las cinco trazas van a `progress/impl_F-023.md`. **Ninguna de estas
  roturas toca Azure, el `.env`, ni el árbol real del repositorio.**
- **Cobertura de las líneas cambiadas (C4 bis)**: el diff no contiene ni una
  línea de producción (solo tests y Markdown). La puerta de
  `bash harness/init.sh` se ejecuta igual; el alcance saldrá **vacío** y la
  puerta dará `[OK]` con su porcentaje o `N/A` **con el motivo impreso por
  la herramienta**. Se declara el número real, no una estimación.
- **Campaña de mutación (C4 bis)**: se ejecuta `python -m harness.mutacion`
  y se genera `progress/mutacion_F-023.md` con sus totales reales. Dará
  **cero mutantes**, porque sin líneas de producción en el alcance no hay
  nada que mutar. **Cero mutantes es un dato que se ejecuta y se pega**; un
  «no aplica» escrito sin ejecutar la herramienta es motivo de rechazo. El
  reviewer recalcula alcance y número de mutantes por su cuenta con
  `harness.alcance` y `harness.mutacion`, como manda C4 bis.
- **Cero supervivientes (`critico`)**: se cumple con cero mutantes, y por
  tanto **no hay ninguna sección de análisis en `PENDIENTE`** ni ninguna
  justificación que el humano tenga que aceptar.
- **Evidencias (C4 bis)**: el informe trae los cuatro números —tests
  ejecutados y resultado, cobertura de las líneas cambiadas, mutantes
  generados y supervivientes (0 y 0), y tiempo de la suite—.
- **Verificaciones MANUAL (`critico`)**: son el cuerpo de la feature.
  **Dieciséis** requisitos (R5–R20): once traen su comando exacto en
  `requirements.md` y cinco son veredicto o decisión escrita del humano
  sobre la salida de otro (R11, R13, R17, R19, R20). Cada una lleva en el
  informe el comando, la salida real y la hora. Además van listadas en
  `progress/current.md` pendientes de ejecución, como pide C4.
- **Acta de cada borrado (`critico`, DA-1)**: las dos escrituras
  destructivas —los dos secretos de `kv-albaranes-rs9k2` (R14) y las reglas
  `datamart-puesto-*` de `psql-albaranes-rs9k2` (R18)— exigen el **OK del
  humano citado literalmente, con fecha y hora**, antes de la evidencia del
  borrado. Sin acta, el reviewer rechaza aunque el borrado esté hecho.
- **C4 ter (rutas sensibles)**: este repositorio **no** declara
  `harness/rutas_sensibles.json` (solo existe el `.ejemplo.json`), de modo
  que el bloque es **N/A por configuración**, que es el caso mayoritario y
  no exige justificación.
- **C3 (documentación)**: R21 y R22. El reviewer contrasta cada afirmación
  de `infra/README.md` y de `azure-apps/datamart_seg_anual.md` contra las
  actas del informe, y comprueba que no hay ni un valor de secreto, ni una
  IP, ni un ID de suscripción o tenant.
