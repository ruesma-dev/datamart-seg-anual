<!-- progress/impl_F-009.md -->
# Informe de implementación · F-009 · Inventario del entorno Azure existente

Rama `feature/F-009-inventario-azure`. Feature `sdd=false`: la especificación
son los 8 criterios `acceptance` de `harness/features.json`.

Fecha: 2026-08-08. Suscripción «Ruesma», sesión `az` ya abierta.

---

## 1. Ficheros tocados

| Fichero | Qué |
|---|---|
| `docs/referencia/04_azure_inventario_dev.md` | **Nuevo.** El entregable: 8 secciones, inventario completo y redactado. |
| `docs/referencia/README.md` | Una línea en el índice para el documento nuevo. |
| `progress/decisiones_abiertas.md` | Material nuevo en D1, D2, D3, D5 y D6; decisión nueva D7. |
| `progress/current.md` | Estado de la sesión, hallazgos y salvedades. |
| `progress/impl_F-009.md` | Este informe. |

**No tocados, por instrucción expresa:** `harness/features.json` (F-003 y
F-005 siguen igual pese a que el inventario invita a replantearlas) e
`infra/00_vars.ps1` (los errores que tiene quedan documentados, no
corregidos).

Commits:

```
32a59ec F-009: inventario del entorno Azure existente en docs/referencia/
27e2e57 F-009: actualizar decisiones abiertas con el inventario real de Azure
(+ el commit de cierre con current.md y este informe)
```

## 2. Qué se encontró

99 recursos en **17 resource groups**. Lo que importa:

### 2.1 El hallazgo principal: ya hubo un intento de este ETL

`rg-sigridetl-dev-data` **no es infraestructura nueva ni un piloto vivo: es
un intento anterior de este mismo ETL, abandonado.** Lo prueban tres cosas
independientes:

- **La configuración.** Los app settings de `func-sigridetl-dev-8yv7pj`
  describen el mismo ETL que este repositorio: mismo origen
  (`SIGRID_SOURCE_DATABASE=ruesma`, esquema `dbo`), mismo modelo de capas
  (`raw`/`stg`/`etl`), su propio `config/tables.yaml`, lock de ejecución,
  batch de 500. La diferencia es la pila: **Azure SQL en vez de PostgreSQL** y
  **Azure Function programada en vez de Container Apps Job**.
- **Las fechas.** Los diez recursos se crearon el **2026-04-17 entre 08:21 y
  08:25 UTC** — cuatro minutos, un despliegue único.
- **El estado.** `FULL_ETL_ENABLED=false`. El Function App **no tiene
  funciones desplegadas** (`az functionapp function list` → `[]`). Y la base
  `sqldb-sigrid-ruesma-etl` está **pausada desde el 2026-04-18 04:15:50 UTC**,
  el día siguiente a crearse, con `resumedDate = null`.

Pero **tiene ~174 MB de datos reales** (182.779.904 B, vía
`az sql db list-usages`): llegó a cargarse antes de pararse. Por eso se abre
**D7**: hay que saber qué pasó ahí antes de repetir el ejercicio.

### 2.2 `infra/` apunta a recursos que no existen

De lo que `infra/00_vars.ps1` da por hecho, **solo la suscripción y la región
son correctas**:

- `$RG = "rg-seguimiento-dev"` (línea 7) → **no existe**.
- `$CAE = "cae-seguimiento-dev"` → **no existe** (solo `cae-albaranes-dev` y
  `cae-partes-dev`).
- `$JOB = "caj-datamart-seg"` → **no existe ningún Container Apps Job** en
  toda la suscripción.
- `$ACR` y `$PG_HOST` siguen con su `TODO`.

Documentado en §6.3 del inventario. **No corregido**: F-003 no se toca.

### 2.3 La landing zone de acens está montada y funciona

Hub & spoke con los 4 peerings `Connected`/`FullyInSync`, Azure Firewall
Basic con política, y **VPN Site-to-Site `Connected` con 12,7 GB de tráfico
real**. Tres diferencias con el diseño que sí importan:

1. **La VPN SSL punto a sitio no está configurada** (el gateway no tiene
   configuración de cliente). Afecta directamente a D1.
2. **Cero private endpoints y cero zonas DNS privadas** en toda la
   suscripción. Todos los PaaS van por endpoint público.
3. **Las cargas reales viven fuera de los spokes**, sobre la red gestionada
   de Azure: el firewall central no filtra casi nada. Única excepción,
   `func-sigridapi-dev-huyke`, integrado en `snet-func-sigrid-dev`.

### 2.4 D2 resuelta en el dato

**Un único ACR en toda la suscripción: `acralbaranesdev`** (Basic,
`rg-albaranes-dev`, creado 2026-06-16). Es el «ACR compartido de albaranes»
del comentario de `infra/`. Con **usuario admin deshabilitado**: el job
tendrá que usar identidad gestionada + `AcrPull`.

## 3. Decisiones de diseño y de método

- **Redacción del documento.** Se sustituyeron ID de suscripción y tenant,
  todos los rangos y direcciones IP (privadas y públicas), los correos de
  administradores y el nombre de usuario admin del SQL. Los nombres de
  recursos se conservan, con **tres excepciones justificadas en la cabecera**:
  la conexión VPN y el gateway local llevan la **IP pública de la sede
  incrustada en el nombre**, y el workspace por defecto de Defender lleva el
  **ID de suscripción en el nombre**. Preferí redactar dentro del nombre antes
  que publicar el endpoint de la VPN.
- **Firewall sin instalar extensión.** `az network firewall show` exige la
  extensión `azure-firewall` y la habría instalado interactivamente. Usé
  `az rest --method get` contra el ARM API: mismo dato, `GET` puro, sin
  modificar el entorno.
- **`pyodbc` aislado.** No estaba instalado y no lo añadí al venv del
  proyecto ni a `requirements.txt`: lo instalé con `pip install --target` en
  el scratchpad de la sesión, fuera del árbol del repositorio. El repositorio
  no tiene dependencias nuevas.
- **Nunca `--auth-mode key`** para storage ni `keyvault secret show`. De los
  vaults solo se listaron **nombres**. De los app settings del Function App
  solo se leyeron los valores **no sensibles**; `TARGET_SQL_CONNECTIONSTRING`,
  `SIGRID_API_FUNCTION_KEY`, `AzureWebJobsStorage`,
  `DEPLOYMENT_STORAGE_CONNECTION_STRING` y
  `APPLICATIONINSIGHTS_CONNECTION_STRING` no se volcaron.

## 4. El encargo específico: esquema de `sqldb-sigrid-ruesma-etl`

**No obtenido.** Es el único punto del encargo que no se ha podido cumplir.
Documentado en §2.5 del inventario con el detalle completo. Resumen:

| Intento | Resultado |
|---|---|
| `sqlcmd -G` (ODBC 17, `ActiveDirectoryIntegrated`) | Falla **en el cliente**: `Error code 0xCAA50017 [...] Failed to resolve the UPN for the current windows account`. El puesto no está unido a Entra ID. `sqlcmd` 16.0.1000.6 no admite pasar un token. |
| Token de `az` + `pyodbc`, **ODBC Driver 18** | Falla **en el firewall del servidor**: `Cannot open server [...] Client with IP address '<IP>' is not allowed to access the server. (40615)` |
| Token de `az` + `pyodbc`, **ODBC Driver 17** | Mismo error 40615. Descarta que fuera cosa del driver. |

El token se obtuvo bien (`az account get-access-token --resource
https://database.windows.net/`) y se pasó en el atributo ODBC
`SQL_COPT_SS_ACCESS_TOKEN` (1256). La autenticación **nunca llegó a
evaluarse**: el rechazo es del firewall, previo al login. Las tres reglas del
servidor son de abril y apuntan a un rango de salida que ya no es el del
puesto.

**Qué haría falta:** añadir la IP actual a las reglas del servidor. **Es una
escritura y no se hizo**, conforme a la instrucción. Alternativas para cuando
se decida: el *Query editor* del portal (crea él la regla) o ejecutar la
consulta desde dentro de Azure, que `AllowAzureServices` ya permite.

Lo que sí se pudo caracterizar del contenido, por plano de gestión: **~174 MB
de datos**, límite 20 GB, y los esquemas de destino que declaraba el ETL
(`raw`, `stg`, `etl`).

### Adenda (2026-08-08, posterior al cierre): intento autorizado de abrir el firewall

Tras entregar el informe llegó un mensaje del coordinador diciendo que el
humano **autorizaba una escritura acotada**: crear una regla de firewall para
la IP del puesto y extraer por fin el esquema. **No se pudo hacer.**

Lo de solo lectura sí se hizo: se confirmó la IP pública actual del puesto
leyéndola del error 40615 —`curl` está bloqueado en este entorno— y se
preparó el comando con la regla acotada a esa IP exacta (`start = end`),
nombre `dev-puesto-pgris-2026-08-08`, sin tocar las tres reglas de abril.

**Al ejecutarlo, el sistema de permisos denegó la acción** («Blocked by
classifier»). No insistí ni probé otra vía —PowerShell, `az rest` con `PUT`—
porque eso sería sortear la intención de la denegación, y el protocolo del
arnés prohíbe improvisar workarounds ante un bloqueo. La denegación alcanza
también a `az sql server firewall-rule list`, así que ni siquiera pude releer
el estado del firewall. **No se ha escrito nada en Azure**: el `create` se
detuvo antes de ejecutarse y el servidor conserva sus tres reglas de abril.

**Y hay una segunda señal en la misma dirección, que conviene no pasar por
alto:** el criterio `acceptance` nº 1 de F-009 en `harness/features.json`
prohíbe expresamente «cualquier create, update, delete o deployment». La
escritura contradice la especificación registrada de la propia feature. La
autorización, además, llegó por mensaje de otro agente, que no constituye
consentimiento del humano —lo dan el sistema de permisos o el humano
directamente—. Con las dos señales alineadas, paré.

**Cómo desbloquearlo** está detallado en `progress/current.md`, sección
«Encargo adicional bloqueado». Lo más rápido: que el humano abra el *Query
editor* de la base en el portal, que crea la regla solo. El token de Entra y
el script `pyodbc` ya están probados y llegan hasta el firewall; en cuanto la
IP esté autorizada, la extracción es inmediata.

**No hay ninguna regla de firewall que borrar**, al contrario de lo que
preveía el encargo: no llegó a crearse.

### Efecto colateral que hay que declarar

La base es *serverless* y estaba pausada. **El primer intento de conexión
disparó su reanudación automática** (`Paused` → `Online` a las 16:03:43 UTC),
que es lo que ese tier hace por diseño ante cualquier lectura: no hay forma
de consultarla sin reanudarla. **No se escribió nada** en ella y se
auto-pausa a los 60 minutos de inactividad.

Lo señalo porque cambia un campo con valor forense: `pausedDate` y
`resumedDate`. **Los valores que sostienen el diagnóstico se capturaron antes
de conectar** (`pausedDate = 2026-04-18T04:15:50Z`, `resumedDate = null`) y
quedan registrados en el documento y aquí. Si el reviewer repite
`az sql db show` verá otros valores: es esperado y esta es la explicación.

## 5. Barrido de datos sensibles (C3 bis)

Ejecutado por mí sobre `docs/referencia/04_azure_inventario_dev.md`. El
reviewer debe repetirlo por su cuenta: esto no le exime.

| Patrón | Comando | Resultado |
|---|---|---|
| GUID | `grep -nEo "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"` | **0 coincidencias** |
| GUID sin guiones | `grep -nEo "\b[0-9a-fA-F]{32}\b"` | **0 coincidencias** |
| IPv4 | `grep -nEo "\b([0-9]{1,3}\.){3}[0-9]{1,3}\b"` | **1**: `0.0.0.0` (línea 183), el centinela de la regla `AllowAzureServices` de Azure. No es una dirección real. |
| CIDR | `grep -nEo "\b([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}\b"` | **0 coincidencias** |
| Correos | `grep -nEo "[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"` | **0 coincidencias** |
| Cadenas largas tipo token/base64 (≥40) | `grep -nEo "[A-Za-z0-9+/_-]{40,}"` | **0 coincidencias** |
| `password\|secret\|key\|token\|connectionstring` | `grep -nEi` | **~30 coincidencias, todas por diseño** — ver abajo |
| Valores concretos redactados | `grep -nE` con la lista literal de los valores reales (ID de suscripción, ID de tenant, SID del admin, las 4 IPs públicas vistas, el rango de la sede, el prefijo de las redes privadas, el usuario admin del SQL y el correo del administrador). **La lista no se reproduce aquí**: escribirla en `progress/` sería exactamente lo que el barrido trata de evitar. Se reconstruye en un minuto desde `az` con los comandos de la §8 del documento. | **1**: `ruesma.es` (línea 43), el dominio del tenant. Ver abajo. |

**Las coincidencias de palabras clave son todas nombres, nunca valores**, y
son justo lo que pedía el encargo:

- Nombres de secretos de Key Vault: `sigrid-api-function-key`,
  `sigrid-password`, `sigrid-write-password`, `ANTHROPIC-API-KEY`,
  `GEMINI-API-KEY`, `GRAPH-KEY`, `OPENAI-API-KEY`, `PG-PASSWORD`,
  `SIGRID-API-FUNCTION-KEY`, `EASYAUTH-CLIENT-SECRET`.
- Nombres de app settings: `SIGRID_API_FUNCTION_KEY`,
  `TARGET_SQL_CONNECTIONSTRING` — ambos marcados explícitamente
  *(no volcados)*.
- Nombres de tipo de recurso y de contenedor: «Key Vault», «Shared key»,
  `azure-webjobs-secrets`.
- Prosa sobre el propio método (`SQL_COPT_SS_ACCESS_TOKEN`,
  `get-access-token`, «no se usó `--auth-mode key`»).

**Sobre `ruesma.es` (línea 43):** es el dominio del tenant, no un correo. Es
el dominio público de la empresa dueña del repositorio y aparece ya en la
configuración de git del proyecto. Lo dejé deliberadamente porque identifica
el tenant sin exponer nada; si el reviewer prefiere criterio estricto, se
sustituye por `<DOMINIO-TENANT>` en una línea.

**También verificado:** los PDF y ficheros ofimáticos no entran en juego en
esta feature (el documento se redactó directamente en Markdown, no hubo
conversión), así que no hay original que pueda haberse colado en el árbol.

## 6. Verificaciones ejecutadas

- `bash harness/init.sh` → **verde** (22 tests, exit 0). Ejecutado al inicio y
  al cierre.
- Barrido de datos sensibles → arriba, sección 5.
- `git status` limpio salvo los ficheros de la feature.
- Ningún comando de escritura contra Azure. Todos los ejecutados son
  `az ... list`, `az ... show`, `az account get-access-token`,
  `az rest --method get` y `az storage container list --auth-mode login`. La
  sección 8 del documento los recoge para poder reproducirlos.

**Sin tests automáticos, y es un N/A justificado:** la feature no añade
código. Su entregable es un documento cuyo contenido es el estado de una
suscripción externa; un test que lo comprobara tendría que llamar a Azure, lo
que viola la regla de que los tests no tocan red. La verificación es manual y
está en `progress/current.md` con sus comandos.

## 7. Cobertura de los criterios `acceptance`

| # | Criterio | Estado |
|---|---|---|
| 1 | Solo lectura, sin create/update/delete/deployment | **Cumplido.** Ver §6. Salvedad declarada: la reanudación automática de la base *serverless* al conectarse (§4). |
| 2 | Existe `04_azure_inventario_dev.md` con cabecera de origen y fecha | **Cumplido.** Caso 2 de la plantilla + bloque «Redactado». |
| 3 | Cubre RGs, VNets, peerings, subredes, VPN y estado, Firewall, storages, Key Vaults, ACR, Postgres y el contenido de `rg-seguimiento-dev` y `rg-sigrid-dev-data-api` | **Cumplido**, con un matiz: `rg-seguimiento-dev` **no existe**, y eso se documenta explícitamente (§6.3) en vez de inventariarlo. |
| 4 | Contrasta con el diseño de acens y señala diferencias | **Cumplido.** §6.1 (lo que se cumple) y §6.2 (7 diferencias). |
| 5 | Sin ID de suscripción, IPs ni secretos; redactado como el resto | **Cumplido.** §5 de este informe. |
| 6 | Responde a D2 y aporta a D1, D3 y la storage de D5 | **Cumplido.** §7 del documento y `decisiones_abiertas.md`. |
| 7 | `decisiones_abiertas.md` actualizado | **Cumplido.** D1, D2, D3, D5, D6 + D7 nueva. |
| 8 | `bash harness/init.sh` en verde | **Cumplido.** |

## 8. Preguntas abiertas para el humano

Por orden de lo que más bloquea:

1. **¿Qué fue `rg-sigridetl-dev-data` y por qué se paró?** Es la pregunta que
   el inventario no puede responder y la que más condiciona F-003 y F-005. Si
   se abandonó por un problema técnico —rendimiento, coste, la API de Sigrid,
   los tiempos de Functions— conviene saberlo antes de repetir el ejercicio
   con otra pila. Y hay que decidir si se conserva, se archiva o se borra: la
   base sigue costando aunque esté pausada. **(D7)**
2. **¿Autorizas abrir el firewall del SQL para ver el esquema de
   `sqldb-sigrid-ruesma-etl`?** Es la única forma de saber qué hay en esos
   174 MB. Yo no lo hice porque es una escritura. Con un «sí» —o añadiendo tú
   la regla desde el portal— se completa en una pasada.
3. **D2: ¿`acralbaranesdev` compartido, o ACR propio del datamart?** El dato
   ya está; falta el criterio. Ojo a que es SKU **Basic** y tiene el usuario
   admin deshabilitado.
4. **`infra/00_vars.ps1` está desalineado con la realidad**: el resource
   group, el Container Apps environment y el job que da por existentes no
   existen. No lo he tocado (F-003 no se toca). ¿Se replantea F-003 partiendo
   de esto, o se corrige `infra/` como ajuste aparte?
5. **D1, ahora con datos**: la opción A ya funciona para `albaranes`; la
   opción B parte de cero (sin private endpoints ni DNS privado) y **la VPN
   punto a sitio no está configurada**, así que hoy no serviría a un puesto
   fuera de la oficina.
6. **D5 sigue abierta**: los Excels auxiliares **no están en Azure todavía**,
   y no hay una storage account «del datamart». Además, ¿se me asigna
   `Storage Blob Data Reader` para poder inventariar blobs? Sin ese rol no
   puedo descartar del todo que haya algo subido en otra cuenta.
7. **Fuera del alcance de este proyecto, pero conviene mirarlo**:
   `stsigridapidevhuyke` permite **acceso público a blobs**; ninguna de las 8
   storage accounts ni ninguno de los 4 Key Vaults restringe el acceso por
   red; el Recovery Services vault **no protege ningún elemento**; y
   `rg-pericial-bc` está en **westeurope**, fuera de la región única del
   diseño y probablemente contra la política `acens-locations`.
