<!-- docs/referencia/04_azure_inventario_dev.md -->
# Inventario del entorno Azure — suscripción «Ruesma»

> Origen: inventario ejecutado con `az` (solo lectura) desde el puesto de
> trabajo, sobre la suscripción «Ruesma» · Fecha del inventario: 2026-08-08
> Incorporado a `docs/referencia/` el 2026-08-08.
> Llegó ya en Markdown: no requirió conversión con `markitdown`.

> **Redactado.** Se han sustituido por marcadores el **ID de suscripción**
> (`<ID-SUSCRIPCION>`), el **ID de tenant** (`<ID-TENANT>`), todos los
> **rangos de red y direcciones IP** —privadas y públicas— (`<RANGO-*>`,
> `<SUBRED-*>`, `<IP-*>`) y los **correos** de las cuentas administradoras
> (`<usuario-admin>`). Se ha sustituido también el nombre de usuario
> administrador del servidor SQL (`<usuario-admin-sql>`). El detalle real se
> obtiene con `az` contra la suscripción.
>
> Los **nombres de recursos se conservan**: son identificadores operativos y
> ya figuran en el repositorio. Única excepción, tres nombres que llevan un
> dato sensible incrustado y se redactan dentro del propio nombre: la
> conexión y el gateway local de la VPN (contienen la IP pública de la sede) y
> el workspace por defecto de Defender (contiene el ID de suscripción).
>
> De Key Vault se listan **solo nombres de secretos**. Ningún valor de
> secreto, cadena de conexión ni clave se ha leído ni figura aquí.

## Por qué está aquí

Antes de añadir el Postgres del datamart (F-005) y el Container Apps Job
(F-003) hacía falta saber qué hay montado ya, para no duplicar
infraestructura ni contradecir la landing zone que describe
`02_azure_landing_zone_acens.md`. El hallazgo principal es que **ya existe un
intento anterior de este mismo ETL**, sobre otra pila tecnológica y
abandonado desde abril: ver la sección 2.

Método: `az account/group/resource list`, `az ... show` y lecturas del ARM
REST API por `GET`. Ninguna escritura. Las salvedades de acceso están
anotadas en cada punto.

---

## 1. Suscripción y resource groups

Suscripción **Ruesma** (`<ID-SUSCRIPCION>`), tenant `ruesma.es`
(`<ID-TENANT>`), estado *Enabled*. **99 recursos** repartidos en **17
resource groups**. Todo en `spaincentral` salvo tres excepciones señaladas.

| Resource group | Ubicación | Rec. | Qué es |
|---|---|---:|---|
| `rg-hub-spaincentral` | spaincentral | 16 | **Hub de la landing zone** de acens: Azure Firewall, Bastion, VPN gateway, tablas de rutas, IPs públicas. Tags `acens-project=alz`, `acens-environment=PRO`, `acens-terraform=True`, `acens-responsable-iac=n3ms`. |
| `rg-sigrid-dev-data-api` | spaincentral | 15 | **`sigrid-api`** (`func-sigridapi-dev-huyke`) más tres aplicaciones de RRHH añadidas después: nóminas extras, retribución flexible y un portal (Static Web Apps). Tag `acens-project=sigrid-api`. |
| `rg-albaranes-dev` | spaincentral | 13 | Proyecto **albaranes**: 6 Container Apps, su entorno, **el único ACR de la suscripción**, un PostgreSQL flexible, Key Vault, storage y Log Analytics. Tag `acens-project=albaranes`. |
| `rg-partes-dev` | spaincentral | 11 | Proyecto **partes** (+ finanzas/remesas): 6 Container Apps, entorno, Key Vault, storage, Log Analytics. Sin ACR propio. Tag `acens-project=partes`. |
| `rg-sigridetl-dev-data` | spaincentral | 10 | **Intento anterior del ETL de Sigrid** sobre Azure Functions + Azure SQL. Detalle en la sección 2. Tag `acens-project=sigridetl`. |
| `rg-spoke-dev-spaincentral` | spaincentral | 10 | **Spoke DEV** de la landing zone: VNet, una VM de prueba (`prueba-ping`, Linux, *deallocated*), dos NSG y restos de pruebas. Sin tags `acens-*`. |
| `rg-management-spaincentral` | spaincentral | 9 | **Gestión de la landing zone**: Log Analytics central (`law-management-spaincentral`), reglas de recolección (VM Insights, Change Tracking, Defender for SQL), identidad del agente. Tags `acens-project=alz`. |
| `rg-spoke-prod-spaincentral` | spaincentral | 3 | **Spoke PROD** de la landing zone: VNet y poco más. Prácticamente vacío. |
| `NetworkWatcherRG` | spaincentral | 2 | Network Watcher automático + un flow log de `GatewaySubnet`. |
| `rg-alz-mgmt-identity-spaincentral-001` | spaincentral | 2 | Identidades gestionadas del **pipeline de Terraform** de acens (`plan` y `apply`). |
| `rg-health-manual` | spaincentral | 2 | Alertas de **Service Health** creadas por política (`_created_by_policy=true`). |
| `rg-alz-mgmt-state-spaincentral-001` | spaincentral | 1 | **Estado de Terraform** de acens: storage `stoalzmgmspa001owvp` (ZRS). |
| `rg-asc-export-spaincentral` | spaincentral | 1 | Exportación continua de **Defender for Cloud** a Log Analytics. |
| `rg-rsv-spaincentral` | spaincentral | 1 | **Recovery Services vault**. Ver sección 5: no protege nada hoy. |
| `DefaultResourceGroup-ESC` | spaincentral | 1 | Workspace por defecto que crea Defender: `DefaultWorkspace-<ID-SUSCRIPCION>-ESC`. |
| `rg-pericial-bc` | **westeurope** | 1 | Storage `ruesmapericial2026`, creado 2026-07-29. Fuera de la región del diseño y sin tags. Propósito no deducible del inventario. |
| `VisualStudioOnline-<GUID>` | **northeurope** | 1 | Cuenta de Azure DevOps (`ruesma`). Encaja con el CI/CD que describe acens. |

**Lectura de los tags.** Conviven tres regímenes: los recursos de acens
(`acens-project=alz`, `acens-terraform=True`, responsable `n3ms`), los
proyectos internos etiquetados a mano (`albaranes`, `partes`, `sigrid-api`,
`sigridetl`, responsable `<usuario-admin>`) y un grupo sin etiquetar
(los spokes, `rg-pericial-bc`, los automáticos). El `sigridetl` declara
`acens-terraform=true` pero `acens-responsable-iac=manual`: se creó a mano
imitando el etiquetado, no por pipeline.

**No existe `rg-seguimiento-dev`.** Ver sección 6.

---

## 2. `rg-sigridetl-dev-data` — el intento anterior del ETL

Este resource group es un **intento previo de construir este mismo ETL**,
sobre una pila distinta de la que plantea el repositorio, y **abandonado**.
No es un piloto vivo ni infraestructura en uso.

### 2.1 Qué contiene y cuándo se creó

Los diez recursos se crearon **el 2026-04-17 entre las 08:21 y las 08:25
UTC**, en poco más de cuatro minutos: un despliegue único, no un entorno que
haya ido creciendo.

| Recurso | Tipo | Creado (UTC) | Últ. cambio ARM |
|---|---|---|---|
| `stsigridetldev8yv7pj` | Storage account | 2026-04-17 08:21:19 | 2026-04-17 08:31 |
| `sql-sigridetl-dev-8yv7pj` | SQL Server | 2026-04-17 08:21:19 | 2026-04-17 08:32 |
| `plan-sigridetl-dev-8yv7pj` | App Service plan (FC1) | 2026-04-17 08:21:20 | 2026-04-17 08:31 |
| `log-sigridetl-dev-8yv7pj` | Log Analytics (30 d) | 2026-04-17 08:21:20 | 2026-04-17 08:32 |
| `kv-sigridetl-dev-8yv7pj` | Key Vault | 2026-04-17 08:21:23 | 2026-04-17 08:31 |
| `appi-sigridetl-dev-8yv7pj` | Application Insights | 2026-04-17 08:22:07 | 2026-04-17 08:32 |
| `sqldb-sigrid-ruesma-etl` | Azure SQL Database | 2026-04-17 08:22:44 | 2026-04-18 04:26 |
| `func-sigridetl-dev-8yv7pj` | Function App (Linux) | 2026-04-17 08:24:52 | 2026-04-17 10:18 |

Todos con los mismos tags: `acens-project=sigridetl`,
`acens-environment=dev`, `acens-customer=ruesma`, `acens-compliance=gdpr`,
`acens-costcenter=pendiente`, `acens-responsable-iac=manual`,
`acens-support=manual`.

### 2.2 Qué era: un ETL de Sigrid a Azure SQL, programado y desactivado

Lo revelan los **nombres de la configuración** del Function App (valores no
sensibles leídos; los sensibles no se han tocado):

| Ajuste | Valor | Lectura |
|---|---|---|
| `FULL_ETL_ENABLED` | `false` | **El ETL está explícitamente desactivado.** |
| `FULL_ETL_CRON` | `0 30 2 * * *` | Carga completa diaria a las 02:30. |
| `TARGET_RAW_SCHEMA` / `TARGET_STAGE_SCHEMA` / `TARGET_ETL_SCHEMA` | `raw` / `stg` / `etl` | Mismo modelo de capas que el repositorio. |
| `SIGRID_SOURCE_DATABASE` / `SIGRID_SOURCE_SCHEMA` | `ruesma` / `dbo` | Mismo origen. |
| `TABLES_CONFIG_PATH` | `config/tables.yaml` | Equivalente a `config/tables_sigrid.yaml`. |
| `DEFAULT_BATCH_SIZE` | `500` | — |
| `DEFAULT_CONTINUE_ON_ERROR` | `true` | — |
| `SIGRID_HTTP_TIMEOUT_SECONDS` / `SIGRID_QUERY_TIMEOUT_SECONDS` | `180` / `120` | — |
| `ETL_RUN_LOCK_NAME` | `sigrid-ruesma-etl` | Control de ejecuciones concurrentes. |
| `APP_ENV` / `LOG_LEVEL` | `dev` / `INFO` | — |
| `SIGRID_API_BASE_URL`, `SIGRID_API_FUNCTION_KEY` | *(no volcados)* | Consumía el mismo `sigrid-api`. |
| `TARGET_SQL_CONNECTIONSTRING` | *(no volcado)* | Destino: el Azure SQL de al lado. |

Es decir: **el mismo ETL que este repositorio, con el mismo origen y el mismo
modelo de capas, pero escribiendo en Azure SQL en vez de PostgreSQL y
ejecutándose como Azure Function programada en vez de Container Apps Job.**

### 2.3 Estado real: parado desde el 18 de abril

- **Function App**: `state=Running`, `enabled=true`, runtime **Python 3.12**,
  plan **Flex Consumption (FC1)**, `maximumInstanceCount=1`,
  `instanceMemoryMB=2048`, identidad **SystemAssigned**, HTTPS only.
  Despliegue desde el contenedor `deployment-package` del storage de al lado.
- **Pero no tiene funciones desplegadas**: `az functionapp function list`
  devuelve lista vacía. La aplicación está configurada y arrancada, sin
  código publicado —o publicado y retirado después—. `lastModifiedTimeUtc`
  del sitio es reciente (2026-08-08), pero es un *touch* de plataforma: el
  último cambio real registrado en ARM es del 2026-04-17 10:18.
- **Sin integración con la VNet** (`virtualNetworkSubnetId` vacío): salía a
  Internet por la red gestionada de Azure, no por el hub.
- **Base de datos**: ver 2.4.
- **Key Vault** `kv-sigridetl-dev-8yv7pj`: RBAC activado, *purge protection*
  activada, acceso público habilitado, **un único secreto**:
  `sigrid-api-function-key` (actualizado 2026-04-17). No hay secreto de la
  base de datos: la credencial del SQL vivía en la cadena de conexión del
  Function App, no en el vault.
- **Storage** `stsigridetldev8yv7pj`: Standard_LRS, sólo tres contenedores, y
  los tres son de infraestructura del Function App —`deployment-package`,
  `azure-webjobs-hosts`, `azure-webjobs-secrets`—, todos con última
  modificación **2026-04-17**. **No hay ningún contenedor de datos ni
  ficheros de negocio.** Los Excels auxiliares no están aquí.

### 2.4 La base `sqldb-sigrid-ruesma-etl`

| Propiedad | Valor |
|---|---|
| Servidor | `sql-sigridetl-dev-8yv7pj.database.windows.net` (SQL 12.0) |
| Tier | **GeneralPurpose serverless** `GP_S_Gen5_1` (1 vCore máx., 0,5 mín.) |
| Auto-pausa | **60 minutos** de inactividad |
| Tamaño máximo | 20 GB |
| **Datos reales** | **≈ 174 MB** usados (182.779.904 B), 192 MB asignados |
| Creada | 2026-04-17 08:23:32 UTC |
| **Pausada desde** | **2026-04-18 04:15:50 UTC** |
| Collation | `SQL_Latin1_General_CP1_CI_AS` |
| Backup | redundancia **Local**, restauración más antigua 2026-08-01 |
| Zone redundant | No |

**Esto es lo que cierra el diagnóstico.** La base tiene ~174 MB de datos
—alguien la cargó de verdad, no está vacía— y lleva **pausada desde el día
siguiente a su creación**, sin una sola reanudación hasta hoy. El ETL corrió
una o dos veces el 17–18 de abril, cargó datos, y se abandonó.

**Acceso al servidor:**

- Acceso público **habilitado**, TLS mínimo 1.2.
- Administrador Entra ID configurado: un **grupo** cuyo login es
  `<usuario-admin>`. Autenticación *Entra-only* **no** forzada
  (`azureAdOnlyAuthentication=false`): sigue activo el administrador SQL
  `<usuario-admin-sql>`.
- Reglas de firewall (3): `AllowAzureServices` (`0.0.0.0`),
  `AllowLocalDev-20260417` (`<IP-PUESTO-ABRIL-1>`) y
  `QueryEditorClientIPAddress_...` (`<IP-PUESTO-ABRIL-2>`), ambas de un rango
  de salida que **ya no es el del puesto**.

### 2.5 Esquema de la base: NO obtenido — bloqueado por el firewall

Encargo específico del humano, **no completado**. Se documenta con detalle
porque el bloqueo es de configuración, no de permisos, y se resuelve en un
minuto cuando se decida.

Lo que se intentó, en orden:

1. **`sqlcmd -G`** (ODBC Driver 17, `ActiveDirectoryIntegrated`) contra
   `sql-sigridetl-dev-8yv7pj.database.windows.net`.
   → Falla en el **cliente**, antes de salir a la red:
   `Failed to authenticate the user '' in Active Directory
   (Authentication option is 'ActiveDirectoryIntegrated'). Error code
   0xCAA50017 [...] Failed to resolve the UPN for the current windows
   account.` El puesto no está unido a Entra ID, así que la autenticación
   integrada no puede resolver el UPN. `sqlcmd` 16.0.1000.6 no admite pasar
   un token de acceso.
2. **Token de la sesión de `az` + `pyodbc`**, la vía que se indicó:
   `az account get-access-token --resource https://database.windows.net/`,
   token pasado en el atributo ODBC `SQL_COPT_SS_ACCESS_TOKEN` (1256).
   Probado con **ODBC Driver 18** y con **ODBC Driver 17** (ambos instalados
   en el puesto).
   → Ambos fallan **en el firewall del servidor**, antes de la
   autenticación: `Cannot open server 'sql-sigridetl-dev-8yv7pj' requested by
   the login. Client with IP address '<IP-PUESTO>' is not allowed to access
   the server. (40615)`.

**Qué haría falta:** añadir la IP de salida actual del puesto a las reglas de
firewall del servidor —o conectarse desde una IP ya autorizada—. Es una
**escritura** sobre Azure, así que **no se ha hecho**, conforme al alcance de
solo lectura de esta feature. Alternativas para cuando se decida: el *Query
editor* del portal (crea él mismo la regla), o ejecutar la consulta desde un
recurso dentro de Azure (la regla `AllowAzureServices` ya lo permite).

Consecuencia: no se ha podido listar esquemas, tablas, filas por tabla,
columnas, vistas ni procedimientos. **Lo que sí sabemos del contenido** es
que hay ~174 MB de datos y que la configuración del ETL apuntaba a los
esquemas `raw`, `stg` y `etl` (sección 2.2).

> **Efecto colateral a dejar por escrito.** La base era *serverless* y estaba
> pausada. El primer intento de conexión —una lectura— **disparó la
> reanudación automática** que ese tier hace por diseño: pasó a `Online` a
> las 2026-08-08 16:03:43 UTC. No se ha escrito nada en ella y volverá a
> pausarse sola a los 60 minutos de inactividad. Los datos que sostienen el
> diagnóstico (`pausedDate = 2026-04-18T04:15:50Z`, `resumedDate = null`) se
> capturaron **antes** de conectar y quedan registrados arriba.

---

## 3. Red

La landing zone de acens está desplegada y **funcionando**.

### 3.1 VNets y peerings

| VNet | Resource group | Espacio | Peerings |
|---|---|---|---|
| `vnet-hub-spaincentral` | `rg-hub-spaincentral` | `<RANGO-HUB>` (/22) | 2, hacia dev y prod |
| `vnet-spoke-dev-spaincentral` | `rg-spoke-dev-spaincentral` | `<RANGO-SPOKE-DEV>` (/18) | 1, hacia el hub |
| `vnet-spoke-prod-spaincentral` | `rg-spoke-prod-spaincentral` | `<RANGO-SPOKE-PROD>` (/18) | 1, hacia el hub |

Los **cuatro peerings están `Connected` y `FullyInSync`**. El hub publica
gateway (`allowGatewayTransit=true`) y los spokes lo consumen
(`useRemoteGateways=true`): los spokes alcanzan la sede por la VPN del hub.
Topología hub & spoke correcta y operativa.

### 3.2 Subredes

Hub (`vnet-hub-spaincentral`):

| Subred | Rango | Tabla de rutas |
|---|---|---|
| `AzureFirewallSubnet` | `<SUBRED-FIREWALL>` (/26) | `rt-hub-fw-spaincentral` |
| `AzureFirewallManagementSubnet` | `<SUBRED-FIREWALL-MGMT>` (/26) | — |
| `AzureBastionSubnet` | `<SUBRED-BASTION>` (/26) | — |
| `GatewaySubnet` | `<SUBRED-GATEWAYS>` (/27) | `rt-hub-vpn-spaincentral` |
| `default` | `<SUBRED-HUB-DEFAULT>` (/24) | — |

Spoke DEV:

| Subred | Rango | Delegación | Uso |
|---|---|---|---|
| `snet-spoke-dev-spaincentral` | `<SUBRED-SPOKE-DEV>` (/24) | — | VM `prueba-ping` |
| `snet-func-sigrid-dev` | `<SUBRED-FUNC-SIGRID>` (/27) | `Microsoft.App/environments` | **Integración VNet de `func-sigridapi-dev-huyke`** |

Spoke PROD: una sola subred `snet-spoke-prod-spaincentral` (/24), sin uso.

`snet-func-sigrid-dev` es relevante para F-003: es la subred **ya delegada a
`Microsoft.App/environments`** por la que `sigrid-api` sale a la red
corporativa. Un Container Apps environment integrado en VNet necesita una
subred con esa misma delegación.

Ningún NSG en las subredes; los dos NSG que existen (`testSQL-nsg`,
`prueba-ping-nsg`) cuelgan de recursos de prueba. Coincide con el diseño:
el filtrado es del firewall central.

### 3.3 VPN gateway y estado real de la conexión

| Propiedad | Valor |
|---|---|
| Gateway | `vgw-hub-vpn-spaincentral` |
| SKU | **`VpnGw1AZ`** (zone-redundant), Generation1 |
| Tipo | `Vpn` / `RouteBased`, **activo-activo** (2 IPs públicas) |
| BGP | Deshabilitado |
| Point-to-Site | **No configurado** (sin *address pool* ni protocolos) |
| Conexión S2S | `cn-<IP-PUBLICA-SEDE>-remota`, IPsec/IKEv2 |
| **Estado** | **`Connected`** |
| Tráfico | **12,7 GB de entrada** y 212 MB de salida acumulados |
| Gateway local | `<IP-PUBLICA-SEDE>-remota`, red remota `<RED-SEDE-CLIENTE>` (/22) |

La VPN Site-to-Site **está levantada y transportando tráfico real** —los
12,7 GB de entrada son, casi con seguridad, las lecturas de `sigrid-api`
contra el SQL on-premise—. En cambio la **VPN SSL punto a sitio que menciona
el diseño no está configurada**: el gateway no tiene configuración de cliente
VPN.

### 3.4 Azure Firewall

`fw-hub-spaincentral`, SKU **`AZFW_VNet` tier Basic**, *Threat Intelligence*
en modo `Alert`, aprovisionado correctamente. Política
`fwp-hub-spaincentral` (Basic), con un grupo de colecciones de reglas
(`fwpolicy-rcg`); ninguna regla clásica en el propio firewall. DNS proxy no
habilitado. Coincide con lo diseñado.

### 3.5 Private endpoints y DNS privado

**Cero private endpoints y cero zonas DNS privadas en toda la suscripción.**
Ningún PaaS de la suscripción está hoy detrás de Private Link: SQL, Postgres,
storages y Key Vaults se exponen por endpoint público con filtrado por IP.
Es el dato más importante para D1.

---

## 4. Almacenamiento y secretos

### 4.1 Storage accounts (8)

Todas `StorageV2`, tier Hot, TLS 1.2 mínimo, **todas `Standard_LRS` salvo
una**, y **todas con `defaultAction=Allow`**: sin restricción de red, sin
reglas de IP y sin reglas de VNet.

| Cuenta | Resource group | Redundancia | Creada | Blob público | Shared key |
|---|---|---|---|---|---|
| `stsigridetldev8yv7pj` | `rg-sigridetl-dev-data` | Standard_LRS | 2026-04-17 | No | Sí |
| `stsigridapidevhuyke` | `rg-sigrid-dev-data-api` | Standard_LRS | 2026-04-15 | **Sí** | Sí |
| `stnominasextrasruesma` | `rg-sigrid-dev-data-api` | Standard_LRS | 2026-06-01 | No | — |
| `stretflexruesma` | `rg-sigrid-dev-data-api` | Standard_LRS | 2026-06-02 | No | — |
| `stalbaranesrs9k2` | `rg-albaranes-dev` | Standard_LRS | 2026-06-16 | No | — |
| `stpartespt7m3` | `rg-partes-dev` | Standard_LRS | 2026-06-22 | No | — |
| `ruesmapericial2026` | `rg-pericial-bc` | Standard_LRS | 2026-07-29 | No | — |
| `stoalzmgmspa001owvp` | `rg-alz-mgmt-state-spaincentral-001` | **Standard_ZRS** | 2026-03-09 | No | Sí |

Dos cosas a revisar al margen de este proyecto: `stsigridapidevhuyke` permite
**acceso público a blobs**, y ninguna cuenta restringe el acceso por red.

**Ninguna cuenta contiene hoy los Excels auxiliares.** El único contenido
inspeccionable (`stsigridetldev8yv7pj`) sólo tiene contenedores de
infraestructura de Functions.

> **Limitación del inventario.** La cuenta de usuario tiene permisos de plano
> de control (puede *listar contenedores*) pero **no roles de plano de datos**
> (`Storage Blob Data Reader` o superior), así que no se pudo listar el
> contenido de los blobs. No se ha usado `--auth-mode key`: habría implicado
> recuperar la clave de la cuenta, un secreto. Para inventariar ficheros hace
> falta asignar el rol de lectura de datos.

### 4.2 Key Vaults (4)

Los cuatro: SKU standard, **RBAC** activado (no *access policies*), soft
delete activo y **acceso público habilitado sin reglas de red**. Sólo
`kv-sigridetl-dev-8yv7pj` tiene *purge protection*.

Se listan **nombres** de secretos. Ningún valor se ha leído.

| Key Vault | Resource group | Secretos (nombres) |
|---|---|---|
| `kv-sigridetl-dev-8yv7pj` | `rg-sigridetl-dev-data` | `sigrid-api-function-key` |
| `kv-sigridapi-dev-huyke` | `rg-sigrid-dev-data-api` | `sigrid-api-function-key`, `sigrid-password`, `sigrid-write-password` |
| `kv-albaranes-rs9k2` | `rg-albaranes-dev` | `ANTHROPIC-API-KEY`, `GEMINI-API-KEY`, `GRAPH-KEY`, `OPENAI-API-KEY`, `PG-PASSWORD`, `SIGRID-API-FUNCTION-KEY` |
| `kv-partes-pt7m3` | `rg-partes-dev` | `EASYAUTH-CLIENT-SECRET`, `GEMINI-API-KEY`, `GRAPH-KEY`, `PG-PASSWORD`, `SIGRID-API-FUNCTION-KEY` |

`kv-albaranes-rs9k2` es el **patrón a imitar en F-003**: un vault por
proyecto, con `PG-PASSWORD` y `SIGRID-API-FUNCTION-KEY`, consumido por
Container Apps con identidad gestionada.

---

## 5. Contenedores y bases de datos

### 5.1 Container registries — **un solo ACR**

| ACR | Resource group | SKU | Login server | Admin | Red |
|---|---|---|---|---|---|
| `acralbaranesdev` | `rg-albaranes-dev` | **Basic** | `acralbaranesdev.azurecr.io` | **Deshabilitado** | Público |

Es el único de toda la suscripción, creado el 2026-06-16, sin redundancia de
zona. **Es «el ACR compartido de albaranes» al que alude el comentario de
`infra/00_vars.ps1`.** Ver D2 en la sección 7.

### 5.2 Container Apps

| Entorno | Resource group | Integración VNet | Logs |
|---|---|---|---|
| `cae-albaranes-dev` | `rg-albaranes-dev` | **Ninguna** | Log Analytics |
| `cae-partes-dev` | `rg-partes-dev` | **Ninguna** | Log Analytics |

12 Container Apps entre ambos (`ca-sv1-intake`, `ca-sv2-extraccion`,
`ca-sv3-persistencia`, `ca-sv4-front`, `ca-sv5-valuation`,
`ca-sv6-valorador`, `ca-sv1-poller`, `ca-finanzas-remesas`,
`ca-finanzas-remesas-front`, …). Ninguno es de este proyecto.

**No existe ningún Container Apps Job en la suscripción.** F-003 parte de
cero. Y ningún entorno está integrado en la VNet: los dos existentes corren
sobre la red gestionada de Azure, no sobre los spokes.

### 5.3 Bases de datos

**PostgreSQL — uno solo:**

| Servidor | RG | Versión | SKU | Almac. | Red | HA | Backup |
|---|---|---|---|---|---|---|---|
| `psql-albaranes-rs9k2` | `rg-albaranes-dev` | **16** | `Standard_B1ms` (Burstable) | 32 GB | **Público**, sin subred delegada ni DNS privado | Deshabilitada | 7 días |

Bases dentro: `albaranes`, `partes` (más las de sistema). **Un mismo servidor
sirve a dos proyectos.** Sus reglas de firewall son el precedente directo de
D1: `AllowAzureServices`, la IP pública de la sede y una IP de puesto
individual (`ClientPgris`). Es decir, **la opción A de D1 ya está en uso** en
producción interna para otro proyecto.

**SQL Server — uno solo:** `sql-sigridetl-dev-8yv7pj`, con
`sqldb-sigrid-ruesma-etl`. Ya descrito en la sección 2.

**Backup:** el Recovery Services vault `rg-rsv-spaincentral` existe pero
**no protege ningún elemento** (`az backup item list` vacío). Las políticas
`GOLDEN-vm` / `SILVER-vm` / `GOLDEN-sql` del diseño no tienen nada asignado,
coherente con que no haya cargas productivas todavía.

---

## 6. Diseño contra realidad

Contraste con `02_azure_landing_zone_acens.md`.

### 6.1 Lo que se cumple

| Elemento del diseño | Realidad |
|---|---|
| Región **Spain Central** | Cumplido: 15 de 17 RG en `spaincentral`. |
| Arquitectura **hub & spoke** con peering | Cumplido: hub + 2 spokes, 4 peerings `Connected` y `FullyInSync`. |
| **Azure Firewall** en modalidad **Basic** | Cumplido: `fw-hub-spaincentral`, `AZFW_VNet`/Basic, con política. |
| **VPN Site-to-Site** `VpnGw1` contra la sede | Cumplido y **en uso**: `Connected`, 12,7 GB de tráfico. |
| **Sin NSG** en las subredes | Cumplido: sólo NSG residuales en recursos de prueba. |
| **Log Analytics** centralizado, retención **30 días** | Cumplido: `law-management-spaincentral`, 30 días. |
| **Defender for Cloud** con exportación continua | Cumplido: `rg-asc-export-spaincentral`. |
| **Terraform** vía Azure DevOps | Cumplido en la parte de acens: RG de estado, identidades `plan`/`apply`, cuenta DevOps `ruesma`. |
| Tags `acens-*` | Cumplido en los recursos de acens; parcial e inconsistente en los proyectos internos. |
| División por entorno **DEV/STA/PRO** | Parcial: existen spokes **DEV y PROD**; **no hay STA**. |

### 6.2 Diferencias entre diseño y realidad

1. **La VPN SSL punto a sitio no existe.** El diseño dice «se hace uso de VPN
   SSL» además de la S2S. El gateway **no tiene configuración de cliente VPN**
   (sin *address pool*, sin protocolos, sin tipos de autenticación). Afecta
   de lleno a D1: la opción B «private endpoint + VPN» hoy sólo funcionaría
   para lo que esté dentro de la red de la sede, no para un puesto remoto.
2. **Cero private endpoints y cero zonas DNS privadas.** El diseño no los
   promete explícitamente, pero la política `Enforce-Subnet-Private` y el
   planteamiento general los sugieren. Todos los PaaS —SQL, Postgres, los
   ocho storages, los cuatro Key Vaults— están expuestos por endpoint público
   y filtrados, como mucho, por IP.
3. **El grueso de las cargas de trabajo vive fuera de los spokes.** Los
   spokes DEV y PROD están casi vacíos (una VM apagada y restos de prueba).
   Container Apps, Function Apps y bases de datos corren en resource groups
   propios sobre la red gestionada de Azure, sin pasar por el hub ni por el
   firewall. La única excepción es `func-sigridapi-dev-huyke`, integrado en
   `snet-func-sigrid-dev`. **El firewall central no está filtrando el tráfico
   de casi ninguna aplicación real.**
4. **El spoke PROD está vacío.** No hay entorno productivo, sólo su VNet.
5. **Backup sin nada protegido.** Las tres políticas del diseño existen sobre
   el papel; el vault no protege ningún elemento.
6. **Recursos fuera del modelo.** `rg-pericial-bc` está en **westeurope**,
   contradiciendo la decisión de región única y probablemente la política
   `acens-locations`; y no tiene tags. Los proyectos internos
   (`albaranes`, `partes`, `sigrid-api`, `sigridetl`) se crearon a mano fuera
   del pipeline de Terraform, con tags imitados: `sigridetl` declara
   `acens-terraform=true` pero `acens-responsable-iac=manual`.
7. **Guardrails aplicados de forma desigual.** Convive infraestructura
   gobernada por Terraform con infraestructura manual; la «única vía oficial»
   que declara el diseño no se está respetando para las cargas de trabajo.

### 6.3 `rg-seguimiento-dev` NO existe

**`infra/00_vars.ps1:7` fija `$RG = "rg-seguimiento-dev"`. Ese resource group
no existe en la suscripción**, ni con ese nombre ni con ninguno parecido: los
17 resource groups están listados en la sección 1.

Arrastra al resto del fichero:

| Línea | Variable | Estado real |
|---|---|---|
| `infra/00_vars.ps1:5` | `$SUB` | ID de suscripción correcto, **pero está escrito en claro en el repositorio**. |
| `infra/00_vars.ps1:6` | `$LOC = "spaincentral"` | Correcto. |
| **`infra/00_vars.ps1:7`** | **`$RG = "rg-seguimiento-dev"`** | **No existe.** |
| `infra/00_vars.ps1:9` | `$ACR = "TODO_acr_existente"` | Existe uno solo: `acralbaranesdev` (D2). |
| `infra/00_vars.ps1:14` | `$CAE = "cae-seguimiento-dev"` | **No existe.** Sólo `cae-albaranes-dev` y `cae-partes-dev`. |
| `infra/00_vars.ps1:15` | `$JOB = "caj-datamart-seg"` | **No existe.** No hay ningún Container Apps Job. |
| `infra/00_vars.ps1:19` | `$PG_HOST` | Sin resolver. El único Postgres es `psql-albaranes-rs9k2`. |

O sea: **de los recursos que `infra/` da por existentes, no existe ninguno
salvo la suscripción y la región.** F-003 tendría que crearlos —o
reutilizar los de `albaranes`—. Esto queda **documentado, no resuelto**:
F-003 y F-005 no se tocan en esta feature.

---

## 7. Qué aporta a las decisiones abiertas

Detalle y seguimiento en `progress/decisiones_abiertas.md`.

- **D2 · Qué ACR usar — respondida en el dato, pendiente de criterio.**
  Existe **exactamente un** Container Registry en la suscripción:
  **`acralbaranesdev`** (`acralbaranesdev.azurecr.io`), SKU **Basic**, en
  `rg-albaranes-dev`, con **usuario admin deshabilitado** —así que un
  Container Apps Job tendría que tirar de él con **identidad gestionada** y
  rol `AcrPull`, no con usuario y contraseña—. Falta que el humano decida
  entre reutilizarlo (un ACR de otro proyecto pasa a ser compartido) o crear
  uno propio del datamart.
- **D1 · Acceso de red al Postgres.** Precedente en funcionamiento: el
  Postgres de albaranes usa **acceso público con reglas por IP** (opción A),
  con la IP de la sede y una IP de puesto. En contra de la opción B: **no hay
  ni un private endpoint ni una zona DNS privada** en toda la suscripción, y
  **la VPN punto a sitio no está configurada** (sólo la S2S contra la sede),
  luego «private endpoint + VPN» hoy no da servicio a un puesto fuera de la
  oficina sin trabajo adicional.
- **D3 · ¿Sólo dev o también producción?** Existe el spoke
  `vnet-spoke-prod-spaincentral` pero **está vacío**, y no hay entorno STA
  pese a que el diseño contempla DEV/STA/PRO. Todos los proyectos internos
  están hoy en `-dev`. El andamiaje de red para PRO existe; la decisión sigue
  siendo del humano.
- **D5 · Storage account de los Excels auxiliares.** El inventario **no
  encuentra ninguna cuenta que los contenga hoy**. Hay 8 candidatas; la única
  cuyo contenido se pudo listar (`stsigridetldev8yv7pj`) sólo tiene
  contenedores de infraestructura. No hay una cuenta «del datamart». Además,
  no se pudo inspeccionar el contenido de blobs por falta de rol de plano de
  datos. La decisión sigue abierta.
- **D4 · Dónde vive el MCP.** El inventario no aporta nada: no hay recurso en
  Azure que corresponda al MCP.
- **D6 · Horario y avisos.** Dato de contexto: el ETL anterior se programó a
  las **02:30** (`FULL_ETL_CRON = 0 30 2 * * *`), no a las 03:00 que propone
  `infra/00_vars.ps1`. Y no hay ninguna alerta de fallo configurada para él.

---

## 8. Cómo repetir este inventario

```bash
az account show
az group list -o table
az resource list -o json
az sql db show -g rg-sigridetl-dev-data -s sql-sigridetl-dev-8yv7pj -n sqldb-sigrid-ruesma-etl
az sql db list-usages -g rg-sigridetl-dev-data -s sql-sigridetl-dev-8yv7pj -n sqldb-sigrid-ruesma-etl -o table
az functionapp config appsettings list -g rg-sigridetl-dev-data -n func-sigridetl-dev-8yv7pj --query "[].name"
az network vnet list -g <rg>            # esta versión de az exige -g
az network vpn-connection show -g rg-hub-spaincentral -n <conexion>
az acr list; az containerapp env list; az containerapp job list
az postgres flexible-server list; az sql server list
az keyvault secret list --vault-name <kv> --query "[].name"   # NUNCA 'secret show'
```

Todos son de lectura. Para el firewall se usó `az rest --method get` sobre el
ARM API en vez de instalar la extensión `azure-firewall`.
