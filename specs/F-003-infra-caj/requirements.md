<!-- specs/F-003-infra-caj/requirements.md -->
# F-003 · Infra: despliegue como Container Apps Job diario — Requisitos (EARS)

Marco de la feature: la sección «Diseño de despliegue propuesto» de
`progress/current.md`, **confirmada por el humano**, y el cierre del bloque
Azure de `progress/decisiones_abiertas.md` (D1, D2, D3, D5, D6 y D7 cerradas).
Realidad del entorno: `docs/referencia/04_azure_inventario_dev.md`.

**Alcance**: todo el aprovisionamiento de la infraestructura del datamart. La
base de datos es de F-005 y el código del ETL es de F-004. F-003 crea el
resource group, el entorno de Container Apps, el job, el Key Vault, el Log
Analytics, la storage account con el contenedor `aux`, la identidad gestionada
con sus roles, la imagen en el ACR, la programación y la alerta de fallo.

**Punto de partida**: `infra/` **se reescribe**, no se completa. De los
recursos que hoy da por existentes (`rg-seguimiento-dev`, `cae-seguimiento-dev`,
`caj-datamart-seg`) **no existe ninguno**, y no hay ni un solo Container Apps
Job en la suscripción (§6.3 del inventario).

## Convenciones de verificación

- Los requisitos marcados **[AUTO]** se verifican con pytest, **sin red y sin
  BBDD**, con test trazable `test_f003_rN_*`.
- Los marcados **[MANUAL]** solo se pueden comprobar contra Azure. Llevan el
  comando `az` exacto y los ejecuta el humano. Ningún agente ejecuta escrituras
  contra Azure.
- En todos los comandos, `<rg>`, `<env>`, etc. se sustituyen por los valores de
  `infra/env/<entorno>.json`. **La suscripción nunca se escribe en el
  repositorio**: se toma del contexto de `az` o de `$env:AZ_SUBSCRIPTION_ID`.

---

## Enmiendas

### ENMIENDA 2026-08-10 · DA-4 resuelta con la **opción B**, aprobada por el humano

**Qué cambia.** El job **sí lleva un segundo secreto**: la contraseña del rol
nativo `sigrid_dm_app` con la que se conecta a PostgreSQL. Viaja **siempre**
como **referencia a Key Vault resuelta por la identidad gestionada**, el mismo
mecanismo que la clave de `sigrid-api`. `PG_AUTH_MODE` pasa a `password` en
`infra/env/dev.json`.

**Por qué.** R10 y el bloque C se escribieron sobre el diseño confirmado «sin
contraseñas: autenticación Entra contra PostgreSQL». Al implementar se descubrió
que `psql-albaranes-rs9k2` **tiene `activeDirectoryAuth` deshabilitado**, y
habilitarlo es una operación **de servidor** que afecta a `albaranes` y `partes`
—el humano la descartó el 2026-08-08, y F-005 se desplegó con contraseña en Key
Vault—. Tal cual estaba, el job se creaba perfecto y **fallaba al conectar todas
las noches**. Las dos salidas se elevaron como DA-4 y el humano eligió la B el
2026-08-10.

**Qué NO cambia, y es lo importante.** La prohibición real de R10 nunca fue la
palabra `PG_PASSWORD`: era que **un valor de secreto no puede aparecer en el
repositorio, en un script ni en la línea de comandos de `az`**. Eso sigue
intacto. Sigue prohibido `--secrets "…=<valor literal>"`, sigue prohibido
`--registry-password`, y `PG_PASSWORD` solo puede ir seguido de `secretref:`.

**Requisitos afectados:**

| Requisito | Antes | Después de la enmienda |
|---|---|---|
| **R10** | «no puede existir `PG_PASSWORD`… el **único** secreto del job es la clave de `sigrid-api`» | El job tiene **dos** secretos —clave de `sigrid-api` y contraseña de Postgres—, **ambos** por `keyvaultref` + `identityref`. `PG_PASSWORD` se admite **solo** como `secretref:<nombre>`; cualquier otro valor es un fallo |
| **R12–R14** (bloque C, modo `entra`) | Camino de ejecución previsto para el job | **Implementados, probados y dormidos.** No se borran ni se dejan de verificar: F-005 los implementó y sus cuatro tests siguen en verde. Son el camino de vuelta si algún día se habilita Entra en el servidor |
| **R7** (contrato de variables) | 15 variables con prefijo | 16: se añade `PG_PASSWORD`, que existe como campo `password` de `PostgresSettings` |

**Trazabilidad de los tests.** `test_f003_r10_sin_pg_password_ni_secretos_literales_en_los_scripts`
se sustituye por `test_f003_r10_ninguna_contrasena_literal_en_los_scripts` (mismo
requisito, la invariante que sobrevive a la enmienda) y se añaden
`test_f003_r10_la_contrasena_de_postgres_viaja_por_keyvaultref`,
`test_f003_r10_el_job_solo_admite_los_dos_modos_de_autenticacion_previstos`,
`test_f003_el_usuario_de_postgres_cuadra_con_el_modo_de_autenticacion` y
`test_f003_los_prerrequisitos_comprueban_el_modo_de_autenticacion_declarado`.

**Consecuencia operativa (bloque 5).** Las contraseñas viven todavía en
`kv-albaranes-rs9k2`, el vault de otro proyecto. El humano aprobó **migrarlas al
vault propio dentro de esta feature**: es el **paso 8 bis** del guion de
`infra/README.md`, y va **antes** de crear el job. Se migran las dos
(`pg-sigrid-dm-app` y `pg-mcp-sigrid-dm-ro`, esta última para el MCP, que no la
usa el job) y las copias viejas **no se borran hasta que el job funcione**.

**Requisito nuevo que nace de la enmienda:**

### R27 — [MANUAL] (enmienda 2026-08-10)
El sistema debe alojar la contraseña del rol de aplicación en el **Key Vault del
propio proyecto** (`keyVault` del fichero de entorno) antes de crear el job, y la
migración desde el vault de `albaranes` debe hacerse **sin que el valor aparezca
por pantalla, en un fichero ni en el historial del shell**.

> Verificación: MANUAL (humano), paso 8 bis de `infra/README.md`. Correcto si
> `az keyvault secret list --vault-name <keyVault> --query "[].name" -o tsv`
> incluye los dos nombres y **en ningún momento se ejecutó `az keyvault secret
> show` suelto** (sin asignar a variable). Comprobación automática asociada:
> `test_f003_r10_la_contrasena_de_postgres_viaja_por_keyvaultref` verifica el
> extremo del job, no la migración.

---

## A. Parametrización de `infra/` por entorno (D3)

### R1 — [AUTO]
El sistema debe declarar los nombres de todos los recursos de un entorno en un
único fichero de datos `infra/env/<entorno>.json`, y **ningún nombre de recurso
concreto** puede aparecer escrito en los ficheros `.ps1`.

> Test: `test_f003_r1_los_ps1_no_contienen_nombres_de_recurso`,
> `test_f003_r1_dev_json_tiene_todas_las_claves_obligatorias`.

### R2 — [AUTO]
El sistema debe resolver el entorno de trabajo por este orden: parámetro
`-Entorno` de `00_vars.ps1`, variable `$env:DATAMART_ENV`, y `dev` como último
recurso; de modo que crear `sta` o `pro` consista en **añadir un fichero
`infra/env/<entorno>.json`**, sin tocar ni duplicar ningún `.ps1`.

> Test: `test_f003_r2_00_vars_resuelve_el_entorno_por_parametro_o_variable`
> (análisis textual del script) + `test_f003_r2_todos_los_env_json_validan_igual`
> (cualquier fichero que se añada a `infra/env/` cumple el mismo esquema).

### R3 — [AUTO]
SI un valor obligatorio del fichero de entorno está vacío, ausente o contiene el
marcador `TODO`, ENTONCES `00_vars.ps1` debe abortar con mensaje explícito
**antes** de ejecutar ningún comando `az`.

> Test: `test_f003_r3_ningun_valor_obligatorio_vacio_ni_TODO`,
> `test_f003_r3_00_vars_valida_antes_de_llamar_a_az`.

### R4 — [AUTO]
El sistema no debe contener en el repositorio ningún ID de suscripción, ID de
tenant, clave, contraseña, cadena de conexión ni dirección de correo — ni en
`infra/`, ni en `specs/F-003-infra-caj/`, ni en `progress/`.

> Test: `test_f003_r4_sin_secretos_ni_identificadores_en_infra_y_spec`.
> Nota: el `$SUB` en claro de `infra/00_vars.ps1:5` desaparece con la
> reescritura, pero **sigue en el historial de git**; ver «Riesgos» del diseño.

### R5 — [AUTO]
Todos los ficheros `.ps1` de `infra/` deben estar codificados en **UTF-8 con
BOM** y con finales de línea **CRLF**, y su primera línea debe ser un comentario
con su ruta relativa (`# infra/NN_nombre.ps1`).

> Test: `test_f003_r5_ps1_utf8_bom_crlf_y_cabecera_de_ruta`.

### R6 — [AUTO]
El sistema debe documentar en `infra/README.md` el orden de ejecución de los
scripts, qué hace cada uno, cuáles son idempotentes y qué pasos exigen
autorización del humano. Todo script `.ps1` presente en `infra/` debe estar
mencionado en ese README.

> Test: `test_f003_r6_readme_menciona_todos_los_scripts_en_orden`.

---

## B. Contrato de configuración del job

### R7 — [AUTO]
Toda variable de entorno que el script de creación del job pase al contenedor
con prefijo `PG_`, `SIGRID_API_`, `AUX_EXCEL_` o `LOG_` debe corresponder a un
campo declarado en `config/settings.py`.

Es el requisito que evita el fallo típico de las 02:00: una variable mal escrita
en el script que el ETL ignora silenciosamente.

> Test: `test_f003_r7_env_vars_del_job_existen_en_settings` (introspección de
> los modelos pydantic; sin red).

### R8 — [AUTO]
El sistema debe ejecutar **siempre `run-all --full`** en la ejecución
programada, y ese alcance debe venir del `CMD` del `Dockerfile`: el script del
job **no** debe sobrescribir `--command` ni `--args`.

> Test: `test_f003_r8_dockerfile_cmd_es_run_all_full`,
> `test_f003_r8_el_job_no_sobrescribe_el_comando_de_la_imagen`.

### R9 — [AUTO]
El sistema debe programar el job con la expresión cron **`0 2 * * *`** (UTC), y
el fichero de entorno debe ser la única fuente de esa expresión.

> Test: `test_f003_r9_cron_del_entorno_dev_es_0_2`.

### R10 — [AUTO] · **ENMENDADO el 2026-08-10** (DA-4 opción B, ver §Enmiendas)

> ⚠ **Texto original, que se conserva para que se vea qué cambió y por qué:**
>
> «El sistema no debe pasar ninguna contraseña al contenedor: no puede existir
> `PG_PASSWORD` ni ningún `--secrets "…=<valor literal>"` en los scripts. El
> único secreto del job es la clave de `sigrid-api`, y debe pasarse como
> **referencia a Key Vault resuelta con la identidad gestionada**.»
>
> Tests originales: `test_f003_r10_sin_pg_password_ni_secretos_literales_en_los_scripts`,
> `test_f003_r10_el_secreto_de_sigrid_se_pasa_por_keyvaultref`.

**Texto vigente.** El sistema no debe pasar **ningún valor de secreto** al
contenedor: no puede existir `--secrets "…=<valor literal>"` ni `PG_PASSWORD`
seguido de nada que no sea `secretref:<nombre>`. El job tiene **dos** secretos
—la clave de `sigrid-api` y la contraseña de PostgreSQL—, y **ambos** deben
pasarse como **referencia a Key Vault resuelta con la identidad gestionada**.

> Test: `test_f003_r10_ninguna_contrasena_literal_en_los_scripts`,
> `test_f003_r10_el_secreto_de_sigrid_se_pasa_por_keyvaultref`,
> `test_f003_r10_la_contrasena_de_postgres_viaja_por_keyvaultref`,
> `test_f003_r10_el_job_solo_admite_los_dos_modos_de_autenticacion_previstos`.

### R11 — [AUTO]
El sistema debe construir y publicar la imagen con un tag fechado
(`rAAAAMMDD-hhmm`) y pasar `IMAGE_TAG` y `BUILD_DATE` como `--build-arg`, de
forma que `python main.py version` dentro del contenedor identifique la build en
ejecución. El script no debe reescribir un tag existente (nada de `:latest`).

> Test: `test_f003_r11_build_pasa_image_tag_y_build_date`,
> `test_f003_r11_el_tag_es_fechado_y_no_latest`.

---

## C. Acceso a PostgreSQL sin contraseña (Entra)

> ⚠ **ENMENDADO el 2026-08-10 (DA-4 opción B, ver §Enmiendas).** Este bloque
> **no se elimina y no deja de verificarse**: R12–R14 quedan **implementados,
> probados y dormidos**. El job **no** usa este camino, porque el servidor tiene
> la autenticación Entra deshabilitada y habilitarla afecta a otras dos
> aplicaciones; se autentica con contraseña por referencia a Key Vault (R10
> enmendado). Reactivar este bloque es habilitar Entra en el servidor, poner
> `pgAuthMode = "entra"` y cambiar `pgUser` al nombre de la identidad gestionada
> —hay un test que exige esa coherencia—. Los cuatro tests de
> `tests/test_f003_pg_entra_auth.py` siguen en verde: el camino de vuelta está
> probado, no solo escrito.

> **Dependencia crítica y decisión abierta.** El diseño confirmado dice «sin
> contraseñas: autenticación Entra contra PostgreSQL», pero hoy
> `PostgresSettings.conninfo` construye la cadena con una contraseña de `.env` y
> **sin `sslmode`**. Sin este bloque, el job se crea correctamente y **falla
> todas las noches al conectar**. Ver la decisión abierta **DA-1** del diseño:
> si F-005 ya lo implementó, estos requisitos se verifican en vez de
> implementarse.

### R12 — [AUTO]
DONDE `PG_AUTH_MODE=entra`, el sistema debe construir la cadena de conexión
usando un token de acceso de Entra como contraseña y `sslmode=require`.

> Test: `test_f003_r12_conninfo_entra_usa_token_y_sslmode_require` (con el
> proveedor de token mockeado; sin red).

### R13 — [AUTO]
MIENTRAS `PG_AUTH_MODE=password` — el valor por defecto, que es el del
desarrollo local — el sistema debe comportarse exactamente como hoy y **no debe
importar `azure-identity`** ni intentar obtener ningún token.

> Test: `test_f003_r13_modo_password_no_toca_entra`.

### R14 — [AUTO]
SI la obtención del token de Entra falla, ENTONCES el sistema debe abortar con un
mensaje que identifique la causa y **sin volcar el token ni fragmentos de él** en
el log ni en la excepción.

> Test: `test_f003_r14_fallo_de_token_aborta_sin_filtrar_el_token`.

---

## D. Aprovisionamiento en Azure

### R15 — [MANUAL]
El sistema debe crear el resource group `rg-datamart-seg-<entorno>` en
`spaincentral` con los tags `acens-*` del estándar de la landing zone
(§3.6 de `02_azure_landing_zone_acens.md`).

```
az group show -n <rg> --query "{loc:location, tags:tags}" -o json
```
Correcto si `location=spaincentral` y están `acens-project`,
`acens-environment`, `acens-customer`, `acens-costcenter`, `acens-compliance`,
`acens-responsable-iac`, `acens-support`.

### R16 — [MANUAL]
El sistema debe crear un Log Analytics workspace propio del datamart y un
Container Apps environment **sin integración de VNet** —igual que
`cae-albaranes-dev` y `cae-partes-dev` (§5.2 del inventario)— con los logs
dirigidos a ese workspace.

```
az monitor log-analytics workspace show -g <rg> -n <law> --query "{sku:sku.name, ret:retentionInDays}" -o json
az containerapp env show -g <rg> -n <cae> --query "{vnet:properties.vnetConfiguration, dest:properties.appLogsConfiguration.destination, ip:properties.staticIp}" -o json
```
Correcto si `vnetConfiguration` es nulo o sin `infrastructureSubnetId`,
`destination=log-analytics` y `staticIp` devuelve una IP (se necesita en R23).

### R17 — [MANUAL]
El sistema debe crear una storage account del proyecto con el contenedor `aux`,
**sin acceso público a blobs**, **sin autenticación por clave compartida** y con
TLS mínimo 1.2. Es el destino de los Excels auxiliares que consume F-004 (D5).

```
az storage account show -g <rg> -n <sa> --query "{pub:allowBlobPublicAccess, key:allowSharedKeyAccess, tls:minimumTlsVersion}" -o json
az storage container list --account-name <sa> --auth-mode login --query "[].name" -o tsv
```
Correcto si `allowBlobPublicAccess=false`, `allowSharedKeyAccess=false`,
`minimumTlsVersion=TLS1_2` y el listado incluye `aux`.

### R18 — [MANUAL]
El sistema debe crear un Key Vault del proyecto con **autorización RBAC** y
alojar en él el único secreto del job, la clave de `sigrid-api`, con el mismo
nombre que usa el patrón de `kv-albaranes-rs9k2`:
`SIGRID-API-FUNCTION-KEY`.

```
az keyvault show -g <rg> -n <kv> --query "{rbac:properties.enableRbacAuthorization, sd:properties.enableSoftDelete}" -o json
az keyvault secret list --vault-name <kv> --query "[].name" -o tsv
```
Correcto si `enableRbacAuthorization=true` y el listado devuelve
`SIGRID-API-FUNCTION-KEY`. **Nunca `az keyvault secret show`.**

### R19 — [MANUAL]
El sistema debe crear una **identidad gestionada asignada por el usuario** para
el job y asignarle exactamente tres roles: `AcrPull` sobre `acralbaranesdev`,
`Key Vault Secrets User` sobre el vault del proyecto y `Storage Blob Data
Reader` sobre la storage account del proyecto. No debe existir ninguna
credencial de registro en el job (el ACR tiene el usuario admin deshabilitado,
D2).

```
az identity show -g <rg> -n <uami> --query "{principalId:principalId, id:id}" -o json
az role assignment list --assignee <principalId> --all --query "[].{rol:roleDefinitionName, ambito:scope}" -o table
```
Correcto si aparecen los tres roles y **ninguno más**, y ningún ámbito es la
suscripción entera.

### R20 — [MANUAL]
El sistema debe publicar la imagen en `acralbaranesdev` con el tag fechado y sin
usar credenciales de registro.

```
az acr repository show-tags -n acralbaranesdev --repository datamart-seg-anual -o tsv
```
Correcto si aparece el tag `rAAAAMMDD-hhmm` recién construido y **no** existe
`latest`.

### R21 — [MANUAL]
El sistema debe crear el Container Apps Job con disparo por programación
`0 2 * * *`, la identidad gestionada asignada, el ACR autenticado con esa misma
identidad y el secreto de `sigrid-api` referenciado desde Key Vault.

```
az containerapp job show -g <rg> -n <job> --query "{trigger:properties.configuration.triggerType, cron:properties.configuration.scheduleTriggerConfig.cronExpression, ident:identity, reg:properties.configuration.registries, sec:properties.configuration.secrets[].name, img:properties.template.containers[0].image, cmd:properties.template.containers[0].command, args:properties.template.containers[0].args}" -o json
```
Correcto si `triggerType=Schedule`, `cronExpression=0 2 * * *`, hay una
`userAssignedIdentity`, el registro usa `identity` (y **no** `username`),
`command` y `args` son nulos, y el secreto figura con su `keyVaultUrl`.

### R22 — [MANUAL]
CUANDO el humano lanza el job a mano, el sistema debe completar la ejecución con
estado `Succeeded` y sus logs deben permitir identificar la build en ejecución.

```
az containerapp job start -g <rg> -n <job>
az containerapp job execution list -g <rg> -n <job> --query "[0].{n:name, st:properties.status, ini:properties.startTime, fin:properties.endTime}" -o json
```
Correcto si `status=Succeeded`. Para identificar la build, ejecución puntual con
override de comando (no altera la programada):

```
az containerapp job start -g <rg> -n <job> --command "python" --args "main.py,version"
```
La salida en los logs debe mostrar `image: datamart-seg-anual:rAAAAMMDD-hhmm` y
`build: <fecha ISO>`, coincidentes con el tag publicado en R20.

### R23 — [MANUAL]
El sistema debe poder alcanzar el PostgreSQL del datamart (F-005) desde el job:
la IP estática de salida del Container Apps environment debe estar autorizada
por regla de firewall en el servidor (D1, opción A).

> ⚠ **Escritura sobre un recurso de otro proyecto** (`psql-albaranes-rs9k2`, en
> `rg-albaranes-dev`). Requiere **autorización expresa del humano**, recurso a
> recurso, y la ejecuta el humano. Ningún agente la lanza.

```
az containerapp env show -g <rg> -n <cae> --query properties.staticIp -o tsv
az postgres flexible-server firewall-rule create -g rg-albaranes-dev -n psql-albaranes-rs9k2 \
  --rule-name caj-datamart-seg-<entorno> --start-ip-address <ip> --end-ip-address <ip>
```
Correcto si tras ello R22 pasa. Nota: el servidor ya tiene una regla
`AllowAzureServices` (`0.0.0.0`) que podría hacer funcionar el job sin esta
regla; **no se debe depender de ella** (autoriza a cualquier recurso de Azure,
de cualquier tenant). Revisarla es materia de F-012, no de F-003.

---

## E. Observabilidad

### R24 — [MANUAL]
El sistema debe permitir consultar los logs de cualquier ejecución del job en
Log Analytics con una consulta documentada en `infra/README.md`.

```
az monitor log-analytics query -w <workspace-customer-id> --analytics-query "ContainerAppConsoleLogs_CL | where ContainerAppName_s == '<job>' | project TimeGenerated, Log_s | order by TimeGenerated desc | take 50" -o table
```
Correcto si devuelve las líneas de la ejecución de R22. Si el nombre de columna
no coincide, comprobar el esquema real con `ContainerAppConsoleLogs_CL |
getschema` y **actualizar el README**, no improvisar otra vía.

### R25 — [MANUAL]
CUANDO una ejecución del job termina en fallo, el sistema debe enviar un aviso
por Azure Monitor al **mismo canal de correo que ya usan las alertas de coste y
seguridad de la landing zone** (§5.1.1 y §5.1.2 de
`02_azure_landing_zone_acens.md`), en menos de 15 minutos.

```
az monitor action-group list --query "[].{n:name, rg:resourceGroup, mails:emailReceivers[].name}" -o table
az monitor metrics alert list -g <rg> --query "[].{n:name, enabled:enabled, sev:severity, act:actions[].actionGroupId}" -o table
```
Prueba de extremo a extremo, que es la única que vale:

```
az containerapp job start -g <rg> -n <job> --command "python" --args "main.py,check-pg"
```
lanzado con `PG_HOST` inexistente (o con la regla de firewall de R23 retirada
temporalmente) debe producir una ejecución `Failed` y **un correo recibido**.
Correcto solo si el correo llega. Anotar en `progress/current.md` la hora del
fallo y la de recepción.

### R26 — [AUTO]
El sistema no debe escribir ninguna dirección de correo en el repositorio: los
destinatarios de la alerta se resuelven reutilizando el action group existente
de la landing zone, o se pasan como parámetro en la ejecución del script.

> Test: cubierto por `test_f003_r4_sin_secretos_ni_identificadores_en_infra_y_spec`
> más `test_f003_r26_el_script_de_alerta_no_lleva_correos_literales`.

---

## Fuera de alcance (explícito)

- **La base de datos `sigrid_dm`, sus roles y su carga inicial**: F-005.
- **La lectura de los Excels desde blob** en `LoadExcelAuxStep`: F-004. F-003
  solo crea la cuenta, el contenedor `aux` y el permiso de lectura.
- **La subida de los Excels por gente de negocio**: F-010.
- **El disparo manual desde web**: F-007.
- **La carga incremental**: F-011. Aquí el job es siempre `--full`.
- **Retirar recursos huérfanos y revisar `AllowAzureServices`**: F-012.
- **Entornos `sta` y `pro`**: se deja el andamiaje parametrizado (R2), pero solo
  se despliega `dev` (D3).
