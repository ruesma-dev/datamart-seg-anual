<!-- specs/F-003-infra-caj/design.md -->
# F-003 · Infra: despliegue como Container Apps Job diario — Diseño

## 1. Idea central

`infra/` se **reescribe**. Lo que hay hoy son cuatro scripts que dan por
existentes tres recursos que no existen, con dos `TODO_` y el ID de suscripción
en claro. El diseño nuevo separa **datos** (nombres de recursos, por entorno) de
**procedimiento** (scripts idempotentes, iguales para todos los entornos), que
es lo que exige D3: crear `sta` o `pro` debe ser añadir un fichero, no duplicar
scripts.

```
infra/
  env/dev.json          <- datos del entorno: los únicos nombres del despliegue
  00_vars.ps1           <- cargador + validador; ningún nombre literal
  NN_*.ps1              <- procedimiento; leen todo de $CFG
  README.md             <- orden de ejecución, KQL de logs, pasos con autorización
```

Regla dura del diseño: **si un `.ps1` contiene el nombre de un recurso o la
cadena `dev`, está mal**. R1 y R2 lo verifican con pytest.

## 2. Topología que se crea (entorno `dev`)

Todo en `spaincentral`, resource group nuevo `rg-datamart-seg-dev`.

| Recurso | Nombre (dev) | Notas |
|---|---|---|
| Resource group | `rg-datamart-seg-dev` | tags `acens-*` |
| Log Analytics | `log-datamart-seg-dev` | retención 30 d, como el estándar de la LZ |
| Container Apps env | `cae-datamart-seg-dev` | **sin VNet**, logs → LAW |
| Container Apps Job | `caj-datamart-seg-dev` | Schedule `0 2 * * *` UTC |
| Storage account | `stdatamartsegdev` | contenedor `aux` (D5) |
| Key Vault | `kv-datamart-seg-dev` | RBAC, secreto `SIGRID-API-FUNCTION-KEY` |
| Identidad gestionada | `id-datamart-seg-dev` | user-assigned; ver §4 |
| Alerta | `alert-caj-datamart-seg-dev-failed` | métrica de ejecuciones fallidas |
| Action group | reutilizar el de la landing zone | si no existe, `ag-datamart-seg-dev` |

Se **reutilizan**, sin crearse aquí: `acralbaranesdev` (D2) y
`psql-albaranes-rs9k2` con la base `sigrid_dm` de F-005.

Nombres de storage account y Key Vault son **globalmente únicos**: si
`stdatamartsegdev` o `kv-datamart-seg-dev` están tomados, se ajusta el valor en
`infra/env/dev.json` y no se toca ningún script. Esa es exactamente la
flexibilidad que da separar datos de procedimiento.

### Por qué el entorno NO se integra en la VNet

1. **Precedente**: los dos Container Apps environments existentes
   (`cae-albaranes-dev`, `cae-partes-dev`) corren sobre la red gestionada de
   Azure (§5.2 del inventario). Igualar el patrón evita ser el único caso raro.
2. **No aporta nada hoy**: el acceso al Postgres es por endpoint público con
   reglas de firewall (D1, opción A) y no hay ni un private endpoint ni una zona
   DNS privada en toda la suscripción (§3.5). Integrar en VNet no acercaría el
   despliegue a Private Link; solo añadiría una subred /27 delegada nueva en el
   spoke DEV.
3. **A cambio se gana lo que se necesita**: un entorno externo tiene **IP pública
   de salida estática** (`properties.staticIp`), que es justo lo que hace falta
   para la regla de firewall del Postgres (R23) y lo que un entorno integrado en
   VNet complicaría (saldría por el firewall del hub, que hoy no filtra el
   tráfico de casi ninguna aplicación real, §6.2 punto 3).

Si algún día se decide meter todo el tráfico por el hub, es una decisión de la
landing zone completa, no de esta feature.

## 3. Ficheros a crear

### `infra/env/dev.json`
Único sitio con nombres. Sin secretos, sin ID de suscripción, sin correos.
Claves obligatorias (el validador de `00_vars.ps1` las exige no vacías y sin
`TODO`):

```
environment, location,
resourceGroup, logAnalytics, containerAppsEnv, job,
storageAccount, auxContainer, keyVault, sigridSecretName,
managedIdentity,
acrName, acrResourceGroup, imageRepository,
cron, replicaTimeoutSeconds, replicaRetryLimit, cpu, memory,
sigridApiBaseUrl,
pgHost, pgPort, pgDatabase, pgUser, pgAuthMode,
alertName, alertActionGroupName, alertActionGroupResourceGroup,
tags { acens-project, acens-environment, acens-customer,
       acens-costcenter, acens-compliance, acens-responsable-iac,
       acens-support }
```

> ⚠ **ENMIENDA 2026-08-10 (DA-4 opción B).** El fichero de entorno lleva además
> `pgSecretName`, `pgJobSecretName` y `pgReadonlySecretName`: los **nombres**
> (nunca los valores) de los secretos de Postgres en el Key Vault del proyecto.
> Y `pgAuthMode` vale **`password`**, no `entra`. Ver
> `requirements.md` §Enmiendas.

Valores de `dev` a fijar en la implementación según la tabla de §2, con
`cron = "0 2 * * *"`, ~~`pgAuthMode = "entra"`~~ → **`pgAuthMode = "password"`
(enmienda)**, `acrName = "acralbaranesdev"`,
`acrResourceGroup = "rg-albaranes-dev"`, `acens-compliance = "gdpr"` (el
datamart carga `prv`/`con`/`age`, con CIF y datos de terceros; se etiqueta como
el resto de recursos que tocan datos de Sigrid).

`pgHost`, `pgDatabase` y `pgUser` los produce **F-005**, que va por delante en
el backlog. Si al implementar F-003 no están disponibles, la feature se marca
`blocked` en vez de inventarlos (R3 obliga a abortar).

JSON y no `.psd1` a propósito: PowerShell lo lee con `ConvertFrom-Json` y pytest
lo valida con `json.load`, sin ejecutar PowerShell. Es lo que hace verificables
R1, R3, R7 y R9 sin tocar Azure.

### `infra/00_vars.ps1` (reescritura completa)
Cargador y validador. Responsabilidades:

- `param([string]$Entorno)`; resuelve `$Entorno` → `$env:DATAMART_ENV` → `dev`.
- Carga `infra/env/$Entorno.json` en `$CFG`. Si el fichero no existe: aborta.
- **Valida** la lista de claves obligatorias: vacío, ausente o `TODO` ⇒
  `throw` antes de cualquier `az` (R3).
- Suscripción: `$env:AZ_SUBSCRIPTION_ID` si está definida; si no, la del
  contexto actual de `az account show`. **Nunca literal en el repositorio** (R4).
- Deriva `$TAG = "r{0}" -f (Get-Date -Format 'yyyyMMdd-HHmm')` y
  `$IMG = "$($CFG.acrName).azurecr.io/$($CFG.imageRepository):$TAG"`.
- Imprime un resumen sin secretos.

### Scripts de aprovisionamiento (todos idempotentes, todos dot-sourcean `00_vars.ps1`)

| Script | Qué hace |
|---|---|
| `05_check_prereqs.ps1` | **Solo lectura.** Verifica sesión de `az`, suscripción, extensión `containerapp` instalada, que existe `acralbaranesdev`, que el servidor de Postgres de F-005 responde, y que la cuenta tiene permiso para crear asignaciones de rol. Aborta con diagnóstico si algo falta. |
| `10_create_rg.ps1` | Resource group + tags. |
| `20_create_observability.ps1` | Log Analytics workspace. |
| `30_create_env.ps1` | Container Apps environment ligado al LAW. Imprime `staticIp` (entrada de R23). |
| `40_create_storage.ps1` | Storage account (`--allow-blob-public-access false`, `--allow-shared-key-access false`, `--min-tls-version TLS1_2`) + contenedor `aux` con `--auth-mode login`. |
| `50_create_keyvault.ps1` | Key Vault con `--enable-rbac-authorization true`. **No** carga el secreto. |
| `60_create_identity.ps1` | Identidad gestionada + las tres asignaciones de rol de R19. |
| `70_build_image.ps1` | `az acr build` con `--build-arg IMAGE_TAG/BUILD_DATE` contra `$CFG.acrResourceGroup`. |
| `80_create_job.ps1` | Crea el job (primera vez). Ver §5. |
| `85_update_job.ps1` | Actualiza el job a una imagen nueva (despliegue habitual). |
| `90_create_alert.ps1` | Action group (reutiliza el existente si lo hay) + alerta de fallo. Ver §6. |

Numeración con hueco deliberado: si mañana hace falta un paso entre dos, entra
sin renumerar los demás.

### `infra/README.md`
Orden de ejecución, idempotencia, qué exige autorización del humano (la regla de
firewall de R23 y la carga del secreto), la consulta KQL de logs (R24) y **cómo
se añade un entorno nuevo**: copiar `env/dev.json` a `env/pro.json`, ajustar
nombres, ejecutar con `-Entorno pro`. Nada más.

### Tests
- `tests/test_f003_infra.py` — R1..R11 y R26. Lee ficheros del repositorio; no
  ejecuta PowerShell, no toca red.
- `tests/test_f003_pg_entra_auth.py` — R12..R14, con el proveedor de token
  mockeado.

## 4. Identidad: por qué *user-assigned* y no *system-assigned*

Con identidad asignada por el sistema hay un problema de huevo y gallina: la
identidad no existe hasta que el job existe, pero el job no se puede crear si no
puede tirar la imagen del ACR, y para eso necesita `AcrPull` **ya asignado**. La
identidad asignada por el usuario se crea antes, se le dan los tres roles, y el
job nace con ella.

Además:

- **Sobrevive al job.** Recrear o borrar el job no destruye las asignaciones de
  rol ni el rol de base de datos que F-005 crea en PostgreSQL para esta
  identidad. Con *system-assigned*, recrear el job obliga a rehacerlo todo.
- **F-005 puede ir por delante**: crea el rol Entra en la base contra un
  principal que ya existe.

Ámbitos mínimos, nunca la suscripción:

| Rol | Ámbito |
|---|---|
| `AcrPull` | el ACR `acralbaranesdev` (recurso, en `rg-albaranes-dev`) |
| `Key Vault Secrets User` | el Key Vault del proyecto |
| `Storage Blob Data Reader` | la storage account del proyecto |

`Storage Blob Data Reader` se incluye aquí aunque quien lo consume sea F-004: es
parte de la identidad y sin él la cuenta creada en R17 es inútil. Lectura, no
escritura: quien sube los Excels es una persona (F-010), no el job.

## 5. El job

```
az containerapp job create -g <rg> -n <job> --environment <cae> \
  --trigger-type Schedule --cron-expression "0 2 * * *" \
  --replica-timeout 7200 --replica-retry-limit 1 \
  --parallelism 1 --replica-completion-count 1 \
  --image <img> --cpu 1.0 --memory 2.0Gi \
  --mi-user-assigned <uami-id> \
  --registry-server acralbaranesdev.azurecr.io --registry-identity <uami-id> \
  --secrets "sigrid-api-key=keyvaultref:<uri-del-secreto>,identityref:<uami-id>" \
  --env-vars "SIGRID_API_BASE_URL=…" "SIGRID_API_FUNCTION_KEY=secretref:sigrid-api-key" \
             "PG_HOST=…" "PG_PORT=…" "PG_DB=…" "PG_USER=…" "PG_AUTH_MODE=entra" \
             "LOG_LEVEL=INFO" "LOG_FORMAT=json"
```

> ⚠ **ENMIENDA 2026-08-10 (DA-4 opción B).** La llamada real lleva **dos**
> secretos y una variable más. El segundo secreto es la contraseña de Postgres,
> con el mismo mecanismo que la clave de la API —referencia al vault resuelta
> por la identidad—, y `PG_AUTH_MODE` vale `password`:
>
> ```
>   --secrets "sigrid-api-key=keyvaultref:<uri-clave-api>,identityref:<uami-id>" \
>             "pg-password=keyvaultref:<uri-contrasena>,identityref:<uami-id>" \
>   --env-vars … "PG_AUTH_MODE=password" "PG_PASSWORD=secretref:pg-password" …
> ```
>
> Sigue sin aparecer **ningún valor**: solo nombres y URIs de secreto. En modo
> `entra` el segundo secreto y `PG_PASSWORD` no se generan; el script construye
> las dos listas antes de llamar a `az`.

Decisiones:

- **Sin `--command` ni `--args`** (R8): el `--full` nocturno vive en el `CMD` del
  `Dockerfile`, que ya lo documenta. Un solo sitio donde está escrito el alcance.
- `--replica-retry-limit 1`: la carga es `--full` y por tanto idempotente
  (reconstruye desde cero), así que un reintento absorbe un corte transitorio de
  `sigrid-api` sin dejar el datamart a medias. Más de uno no: si falla dos
  veces, hay que mirarlo, y para eso está la alerta.
- `--replica-timeout 7200`: 2 h por réplica. La carga completa nunca se ha
  medido en Azure; es el número del script anterior y se revisa con datos en
  F-011.
- `LOG_FORMAT=json` porque `docs/CONVENTIONS.md` reserva ese formato para
  producción y porque Log Analytics parsea mejor JSON que la salida de consola.
- Variables `AUX_EXCEL_*`: **las define F-004**, que conserva los tres nombres
  actuales (`AUX_EXCEL_TIPO_PARTIDA`, `AUX_EXCEL_TIPO_COSTE`,
  `AUX_EXCEL_MAPEO_PROPORCIONALES`) y admite como valor una ruta local **o** una
  URI de blob. En el job se pasan como URI:
  `https://<storageAccount>.blob.core.windows.net/aux/<fichero>.xlsx`, con la
  cuenta y el contenedor tomados de `env/<entorno>.json` — no escritos a mano.
  R7 verifica por introspección que los nombres existen en `AuxExcelSettings`,
  de modo que un nombre inventado rompe el test en vez de romper la carga
  nocturna. Si F-004 aún no ha aterrizado cuando se implemente F-003, el job se
  crea sin ellas y queda anotado en `progress/current.md`.

## 6. Alerta de fallo (D6)

**Primaria — alerta de métrica.** Los Container Apps Jobs publican
`JobExecutionCount` con dimensión `Status`:

```
az monitor metrics alert create -g <rg> -n <alertName> \
  --scopes <job-resource-id> \
  --condition "total JobExecutionCount > 0 where Status includes Failed" \
  --window-size 5m --evaluation-frequency 5m --severity 1 \
  --action <action-group-id> \
  --description "El job nocturno del datamart ha fallado"
```

Se elige métrica y no consulta de log porque no depende de parsear texto ni de
que el esquema de la tabla `_CL` cambie, y porque la latencia es de minutos.

**Comprobación previa, obligatoria**, antes de escribir el script:

```
az monitor metrics list-definitions --resource <job-resource-id> -o table
```

**Alternativa acotada** si esa métrica o su dimensión no están disponibles en
`spaincentral`: regla de consulta programada sobre los logs del sistema.

```
az monitor scheduled-query create -g <rg> -n <alertName> \
  --scopes <law-resource-id> --condition "count > 0" \
  --condition-query "ContainerAppSystemLogs_CL | where JobName_s == '<job>' | where Reason_s in ('JobExecutionFailed','BackoffLimitExceeded')" \
  --evaluation-frequency 15m --window-size 15m --severity 1 --action-groups <ag-id>
```

Esto **no es improvisar un workaround**: son dos caminos previstos, con el
comando que decide cuál se usa. Cualquier tercer camino ⇒ `blocked`.

**Canal de correo.** `90_create_alert.ps1` busca primero un action group
existente en la suscripción (el que usan el budget y Defender, §5.1.1/§5.1.2 de
la landing zone) por el nombre que indique `alertActionGroupName` /
`alertActionGroupResourceGroup` del fichero de entorno, y lo reutiliza. Solo si
no existe crea uno propio, y entonces los destinatarios llegan por parámetro
`-AlertEmail` en la línea de ejecución. **Ninguna dirección de correo entra en el
repositorio** (R26): los correos de la landing zone están redactados incluso en
`docs/referencia/`.

## 7. Cambios en el código de la aplicación (bloque C)

Mínimos y acotados. Sin ellos el job se despliega y falla al conectar.

### `config/settings.py` — modificar
En `PostgresSettings`, dos campos nuevos y una resolución de contraseña:

```python
auth_mode: Literal["password", "entra"] = Field("password", ...)
sslmode: str = Field("prefer", ...)          # 'require' en Azure

def _resolve_password(self) -> str: ...      # privado
@property
def conninfo(self) -> str: ...               # sigue siendo property
@property
def admin_conninfo(self) -> str: ...         # idem
```

`conninfo` y `admin_conninfo` **siguen siendo propiedades** a propósito: cinco
steps, `main.py` y varios scripts las consumen así (`build_stg_step.py:67`,
`ingest_raw_step.py:78`, …). Convertirlas en método multiplicaría el radio del
cambio sin ganar nada.

`_resolve_password()` devuelve la contraseña de `.env` en modo `password`, y en
modo `entra` importa **dentro de la función** el proveedor de token. El import
local mantiene `azure-identity` fuera del camino de arranque local y garantiza
R13.

Ambas propiedades añaden `sslmode={self.sslmode}` a la cadena.

### `etl_sigrid/infrastructure/postgres/entra_auth.py` — crear
Capa **infrastructure** (habla con un servicio externo). Responsabilidad única:

```python
def get_access_token(scope: str = "https://ossrdbms-aad.database.windows.net/.default") -> str
```

- Usa `DefaultAzureCredential` de `azure-identity`; en el job resuelve la
  identidad gestionada asignada al contenedor.
- Cachea el token con margen de expiración (renueva a partir de ~5 min antes del
  vencimiento), porque a lo largo de una carga completa se abren conexiones
  nuevas en cada step.
- SI falla, lanza una excepción con causa legible y **sin incluir el token ni
  fragmentos** en el mensaje (R14).

### `requirements.txt` — modificar
Añadir `azure-identity>=1.17.0`, **si F-004 no la ha añadido ya** (su diseño la
declara para leer los Excels del blob). Es la única dependencia que necesita
F-003 y queda declarada aquí, como exige C3 de `CHECKPOINTS.md`.

### `docs/ARCHITECTURE.md` — modificar
La sección «Infra» dice hoy `rg-seguimiento-dev` y describe el `infra/` viejo.
Actualizarla: resource group real, `infra/env/<entorno>.json` como fuente de
verdad, identidad gestionada y ausencia de contraseñas.

## 8. Ficheros que NO se tocan

- `main.py` y `etl_sigrid/application/steps/*` — el contrato de `conninfo` no
  cambia; por eso se mantiene como propiedad.
- `etl_sigrid/infrastructure/postgres/postgres_client.py` — recibe la cadena ya
  construida; no se entera de Entra.
- `etl_sigrid/infrastructure/postgres/sql/**` — F-003 no crea ni modifica SQL.
  **No hay capa SQL nueva en esta feature.**
- `config/tables_sigrid.yaml`, `config/business_rules.yaml`.
- `LoadExcelAuxStep` — es F-004. Aquí solo se crea el contenedor y el permiso.
- `harness/init.sh`, `CHECKPOINTS.md` — el arnés no cambia.
- `.gitattributes` — la regla `*.ps1 text eol=crlf` ya existe y basta.

## 9. Riesgos y decisiones

### Decisiones abiertas que el humano debe validar

- **DA-1 · ¿La autenticación Entra contra PostgreSQL es de F-003 o de F-005?**
  El bloque C (R12–R14, §7) es código de aplicación, no infraestructura, y F-005
  va por delante en el backlog. Si F-005 ya lo implementó, las tareas T12–T15 se
  reducen a **verificar** y el `requirements.txt` ya tendrá `azure-identity`. Si
  no, se implementa aquí, porque sin ello el job no conecta y F-003 no se puede
  cerrar. **Se necesita respuesta antes de empezar T12.**
- **DA-2 · Autorización para la regla de firewall de R23**, que es una escritura
  sobre `psql-albaranes-rs9k2`, recurso del proyecto `albaranes`. La ejecuta el
  humano, no un agente.
- **DA-3 · Nombre del action group de la landing zone**. Hace falta el nombre
  real del grupo que reciben las alertas de coste y seguridad para reutilizarlo;
  si no se identifica, se crea uno propio y los correos llegan por parámetro.

### Riesgos

- **El ID de suscripción sigue en el historial de git** (`infra/00_vars.ps1:5`).
  Quitarlo del árbol de trabajo no lo borra del historial. No es una credencial
  —no da acceso por sí solo— pero el criterio del repositorio es redactarlo. No
  se reescribe la historia en esta feature: se anota para que el humano decida.
- **Nombres globalmente únicos** (storage, Key Vault): pueden estar tomados. Se
  resuelve cambiando el valor en `env/dev.json`; ningún script se toca.
- **`--replica-timeout 7200` no está medido.** Si la carga completa tarda más, el
  job muere a las 2 h con `Failed` y disparará la alerta — que es el
  comportamiento correcto, pero conviene medir en la primera ejecución (entrada
  para F-011).
- **Vida del token de Entra** (~1 h) frente a un job de hasta 2 h. Mitigado con
  caché y renovación anticipada en `entra_auth.py`, pero una conexión ya abierta
  durante más de una hora no se reautentica: es comportamiento de PostgreSQL, no
  del cliente. Si aparece, se aborda como bug propio con datos.
- **`allowSharedKeyAccess=false`** en la storage account obliga a que cualquier
  subida de Excels use `--auth-mode login` y un rol de plano de datos. Es
  deliberado (el inventario señala que las ocho cuentas existentes no restringen
  nada) y hay que decirlo en `infra/README.md` para que F-010 no se estrelle.
- **Purge protection del Key Vault: deshabilitada** en `dev`. Con ella activada,
  un vault mal nombrado no se puede purgar y el nombre queda quemado durante
  días. Soft delete sí queda activo (viene por defecto). En `pro` se revisará.

### Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| Completar los scripts actuales en vez de reescribirlos | Dan por existentes tres recursos inexistentes y cablean el entorno; completarlos sería arrastrar D3 sin cerrarla. |
| Terraform, como la landing zone de acens | El pipeline de Terraform es de acens y ningún proyecto interno lo usa (§6.2 punto 6). Introducirlo aquí es una decisión de gobierno, no de esta feature. |
| Identidad asignada por el sistema | Huevo y gallina con `AcrPull` en la creación del job, y se pierde al recrearlo (§4). |
| ACR propio del datamart | D2 cerrada: `acralbaranesdev`. |
| Entorno integrado en VNet | §2. Sin private endpoints ni DNS privada, no acerca nada y quita la IP estática de salida. |
| ~~Contraseña de Postgres en Key Vault~~ | ~~El diseño confirmado dice «sin contraseñas». Un secreto que no existe no se filtra ni se rota.~~ **Descarte revertido el 2026-08-10 (DA-4 opción B): es lo que se implementa.** El razonamiento seguía siendo bueno, pero daba por hecho que Entra estaba disponible en el servidor, y no lo está; habilitarlo afecta a `albaranes` y `partes`. Al pasar la contraseña como referencia al vault, el valor sigue sin estar en el repositorio: lo que se pierde es la rotación automática, no la confidencialidad. |
| Alerta por consulta de log como opción primaria | Depende del esquema de tablas `_CL` y tiene más latencia que una métrica. Queda como alternativa acotada (§6). |
| `latest` como tag de imagen | Impide saber qué build corrió una noche concreta, que es justo lo que F-001 vino a resolver. |
