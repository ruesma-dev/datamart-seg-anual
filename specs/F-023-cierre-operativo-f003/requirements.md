<!-- specs/F-023-cierre-operativo-f003/requirements.md -->
# F-023 · Cierre operativo de F-003 — Requisitos (EARS)

Rama: `feature/F-023-cierre-operativo-f003`. Rigor declarado hoy en
`harness/features.json`: `estandar` — **la spec propone elevarlo a
`critico`** (DA-1 en `design.md` §9): dos de los tres bloques escriben o
borran sobre recursos de **otro proyecto en producción**
(`kv-albaranes-rs9k2` y `psql-albaranes-rs9k2`). El cambio lo hace el
líder, no esta spec.

## Qué es esta feature, y qué no

F-023 es **operación contra Azure**, no desarrollo. De los 21 requisitos
de abajo, **6 son automatizables con test** (invariantes de configuración
que impiden volver atrás) y **13 son `MANUAL (humano)`** con su comando
exacto; 2 son de documentación y los valida el reviewer. Cerrarla es lo
único que separa a F-003 de su `done`.

**NO entra la carga de los Excels a las tablas `aux.*`.** Eso es **F-013**
y sigue `pending`: F-004 construyó la capacidad de **leer y validar** los
libros, no de volcarlos, porque el modelo destino no está acordado (DA-1
de F-004, en `progress/current.md`). Aquí se comprueba que la lectura
funciona de verdad contra el blob; ni una fila entra en ninguna tabla.

## Hechos verificados que la spec asume (leídos del árbol, no supuestos)

1. **El job ya compone las `AUX_EXCEL_*` como URIs de blob.** Contra lo
   que dice la `description` de la feature en `harness/features.json`,
   `infra/env/dev.json` **no contiene ninguna ruta de OneDrive**: declara
   `storageAccount`, `auxContainer` y `auxBlobs` (tres nombres de fichero
   `.xlsx`), y `infra/80_create_job.ps1` §4 construye
   `https://<storageAccount>.blob.core.windows.net/<auxContainer>/<blob>`
   para las tres variables. Las rutas de OneDrive están en el **`.env` del
   puesto** del humano (no versionado), que es lo que hay que cambiar para
   la verificación 1. Consecuencia: el fichero de entorno **no se toca**
   (salvo lo que descubra R4/R6, ver DA-6).
2. **El contenedor `aux` existe y la cuenta nace endurecida**:
   `40_create_storage.ps1` crea `stdatamartsegdev` con
   `--allow-shared-key-access false`. Todo acceso —también **subir** un
   fichero— exige rol de **plano de datos** sobre la cuenta; ser Owner de
   la suscripción **no** basta.
3. **El job tiene una ejecución completa correcta**: `caj-datamart-seg-dev`
   corrió el 2026-08-18 de 12:22 a 15:08 local (`Succeeded`, 2 h 45)
   resolviendo `PG_PASSWORD` por referencia a `kv-datamart-seg-dev`. Es la
   precondición que el propio `infra/README.md` §3 exige para retirar las
   copias viejas del vault de `albaranes`.
4. **`load-aux` escribe en `_meta`**: `main.py::load_aux` llama a
   `_arrancar_ejecucion`, que abre fila en `_meta.etl_runs` y **marca
   `ABORTED` toda fila `RUNNING` que encuentre** (F-024). Lanzarlo desde el
   puesto mientras el job está en marcha corrompería la contabilidad de esa
   ejecución y podría cerrar su puerta de coherencia. De ahí R8.
5. **`load-aux` necesita el Postgres**, no solo el blob: abre conexión
   antes de leer ningún libro. Desde el puesto eso exige una regla de
   firewall vigente en `psql-albaranes-rs9k2` — la misma que el bloque 3
   retira. **El orden de los bloques no es estético: es funcional.**
6. **F-024 Fase C (T17–T20) sigue pendiente y se ejecuta desde el puesto**
   (`apply-grants`, `timings`, `check-coherencia`, `stage --sin-puerta`).
   El bloque 3 la dejaría sin acceso. De ahí R14.
7. **El job no pasa `SIGRID_API_PAGE_SIZE`**: no está entre las variables
   de `80_create_job.ps1`, así que la carga nocturna usa el valor por
   defecto de `config/settings.py` (10000). Los 50000 son un apaño del
   `.env` del puesto para una red mala. La decisión pendiente afecta al
   puesto, no a Azure.
8. **Nadie más lee `pg-mcp-sigrid-dm-ro` de `kv-albaranes-rs9k2`** que se
   haya podido comprobar: el prototipo del MCP (`PycharmProjects/mcp-bbdd`)
   no usa Key Vault (solo aparece en dependencias de terceros), y ningún
   documento de `azure-apps/` menciona ese vault. Aun así, R9 lo convierte
   en pregunta explícita al humano antes de borrar.

## Convenciones de este documento

- **[TEST]**: lo comprueba pytest sin red ni BBDD. El nombre del test es el
  contrato.
- **[MANUAL]**: solo se puede comprobar contra Azure o contra el puesto. Lo
  ejecuta **el humano**, con el comando exacto que se da aquí, y su
  resultado real (salida, hora) se anota en `progress/impl_F-023.md`.
- Los nombres de recurso salen **siempre** de `infra/env/dev.json`. En los
  comandos van como `<clave>` cuando el valor es un nombre de recurso, y
  literal cuando es un nombre de otro proyecto que ya está escrito en el
  repositorio (`kv-albaranes-rs9k2`, `psql-albaranes-rs9k2`).
- **Ninguna IP, ningún correo, ningún ID de suscripción o tenant y ningún
  valor de secreto se escribe en esta spec.** Las reglas de firewall se
  citan por su **nombre**, nunca por su dirección.

---

## Bloque 0 · Invariantes que impiden volver atrás (automatizables)

> **R1.** El sistema debe componer las tres variables `AUX_EXCEL_*` que
> inyecta en el job como URIs
> `https://<storageAccount>.blob.core.windows.net/<auxContainer>/<blob>`,
> tomando cuenta, contenedor y nombre de blob del fichero de entorno, sin
> ninguna ruta del sistema de ficheros y sin query string.

Es el invariante que hace falsa para siempre la premisa «apuntan a
OneDrive»: si alguien vuelve a poner una ruta local ahí, la suite se pone
roja antes de llegar a Azure.

- [TEST] `test_f023_r1_las_aux_excel_del_job_son_uris_de_blob`
- [TEST] `test_f023_r1_ninguna_aux_excel_del_job_lleva_ruta_local_ni_sas`

> **R2.** El sistema debe declarar en el fichero de entorno los tres blobs
> auxiliares como **nombres de fichero `.xlsx` estables**: sin unidad de
> disco, sin carpeta, sin `~`, sin `?` y sin espacios al principio o al
> final.

El espacio colado antes de una barra ya rompió las rutas del `.env` el
2026-08-16 (`progress/current.md`); el nombre del blob es lo único que
queda entre el ETL y el fichero.

- [TEST] `test_f023_r2_los_tres_auxblobs_son_nombres_de_fichero_xlsx`

> **R3.** El sistema debe estar libre de rutas locales de los Excels
> auxiliares en el código y la configuración que viajan en la imagen
> (`etl_sigrid/`, `config/`, `main.py`) y en los scripts de `infra/`.

Complementa a R15 de F-004 (rutas absolutas) con lo concreto que se ha
visto fallar: `OneDrive`, `Documentos\Sigrid`, `tablas_auxiliares`.

- [TEST] `test_f023_r3_ni_el_codigo_ni_infra_mencionan_rutas_de_onedrive`

> **R4.** El sistema no debe inyectar `SIGRID_API_PAGE_SIZE` en el job: el
> tamaño de página de la carga nocturna es el valor por defecto de
> `config/settings.py`, en un solo sitio.

Cierra la parte automatizable de la decisión sobre `SIGRID_API_PAGE_SIZE`:
lo que se decida en el `.env` del puesto no puede cambiar en silencio lo
que hace el job.

- [TEST] `test_f023_r4_el_job_no_fija_el_tamano_de_pagina_de_la_api`

---

## Bloque 1 · Los Excels en el blob y las tres verificaciones de F-004

### Preparación

> **R5.** CUANDO el humano suba los tres Excels auxiliares al contenedor
> declarado en `auxContainer`, el listado del contenedor debe devolver
> **exactamente** los tres nombres declarados en `auxBlobs`, ni uno más ni
> uno menos.

- [MANUAL] Estado previo y subida (la cuenta no admite clave compartida:
  todo va con `--auth-mode login` y exige `Storage Blob Data Contributor`
  sobre la cuenta):

```powershell
# 1. Qué hay ya (solo lectura). Idempotencia: si los tres ya están, salta a R6.
az storage blob list --account-name <storageAccount> --container-name <auxContainer> `
  --auth-mode login --query "[].name" -o tsv

# 2. Subida, uno por uno, con el nombre EXACTO de auxBlobs.
az storage blob upload --account-name <storageAccount> --container-name <auxContainer> `
  --auth-mode login --name TipoPartida.xlsx --file "<ruta local del libro>"
az storage blob upload --account-name <storageAccount> --container-name <auxContainer> `
  --auth-mode login --name TipoCoste.xlsx --file "<ruta local del libro>"
az storage blob upload --account-name <storageAccount> --container-name <auxContainer> `
  --auth-mode login --name mapeo_proporcionales.xlsx --file "<ruta local del libro>"

# 3. Comprobación: los tres nombres, y su tamaño distinto de cero.
az storage blob list --account-name <storageAccount> --container-name <auxContainer> `
  --auth-mode login --query "[].{n:name, bytes:properties.contentLength}" -o table
```

  **Correcto si** el paso 3 devuelve los tres nombres de `auxBlobs` con
  tamaño > 0. Si la subida falla con `AuthorizationPermissionMismatch`, es
  el rol de plano de datos (§4 de `infra/README.md`), no la sesión.

> **R6.** MIENTRAS el humano tenga sesión `az login` activa y **al menos**
> el rol `Storage Blob Data Reader` sobre la cuenta de almacenamiento, el
> sistema debe poder leer los tres libros desde el blob.

- [MANUAL] Estado de los roles, antes de nada:

```powershell
$cuenta = az storage account show -g <resourceGroup> -n <storageAccount> --query id -o tsv
az role assignment list --scope $cuenta --query "[].{rol:roleDefinitionName, quien:principalName}" -o table
```

  **Anotar la lista literal**: es la que hay que restaurar en R8. Si al
  humano le falta el rol de lectura:

```powershell
az role assignment create --role "Storage Blob Data Reader" `
  --assignee "<su cuenta>" --scope $cuenta
```

  La propagación de RBAC tarda un par de minutos: si el comando siguiente
  falla por permisos, esperar y repetir antes de concluir nada.

### Verificación 1 de F-004 · lectura desde el puesto

> **R7.** CUANDO el humano ejecute `python main.py load-aux` desde el
> puesto, con las tres `AUX_EXCEL_*` de su `.env` apuntando a las URIs de
> blob, el step debe terminar en **SUCCESS** y reportar, para los tres
> ficheros, `origen=blob` con las hojas del libro y su tamaño.

- [MANUAL], y **antes**: `pip install -r requirements.txt` (`azure-identity`
  y `azure-storage-blob` están declaradas pero pueden no estar instaladas
  en el puesto; el síntoma sería `ModuleNotFoundError`, no un fallo de
  permisos).

```powershell
# En el .env del puesto (lo edita el humano; ningún agente toca .env):
#   AUX_EXCEL_TIPO_PARTIDA=https://<storageAccount>.blob.core.windows.net/<auxContainer>/TipoPartida.xlsx
#   AUX_EXCEL_TIPO_COSTE=https://<storageAccount>.blob.core.windows.net/<auxContainer>/TipoCoste.xlsx
#   AUX_EXCEL_MAPEO_PROPORCIONALES=https://<storageAccount>.blob.core.windows.net/<auxContainer>/mapeo_proporcionales.xlsx
# Sin comillas, sin espacios sobrantes, sin token: la URI limpia (R6/R7 de F-004).

az login                      # si la sesión ha caducado
python main.py load-aux
```

  **Correcto si** el paso sale `SUCCESS` y en el detalle aparecen los tres
  ficheros con `origen=blob`. **Incorrecto** —y hay que parar— si alguno
  sale con `origen=local`: significa que el `.env` conserva una ruta.

> **R8.** SI hay una ejecución del job en curso, ENTONCES el humano no debe
> lanzar `load-aux` (ni ningún comando del ETL que escriba) desde el
> puesto, porque `_arrancar_ejecucion` marcaría `ABORTED` las filas
> `RUNNING` de esa ejecución.

- [MANUAL] Comprobación obligatoria **antes** de R7 y de R9:

```powershell
az containerapp job execution list -g <resourceGroup> -n <job> `
  --query "[].{n:name, estado:properties.status, inicio:properties.startTime}" -o table
```

  **Correcto si** ninguna ejecución está en `Running`. Además, no ejecutar
  nada del ETL desde el puesto dentro de la ventana nocturna (el `cron` del
  entorno es 02:00 UTC y la carga dura ~3 h 15).

### Verificación 2 de F-004 · lectura desde el job con identidad gestionada

> **R9.** CUANDO se lance una ejecución del job que ejecute solo
> `load-aux`, Log Analytics debe mostrar **tres** eventos `aux_file_read`
> con `origen=blob`, uno por fichero, y **ninguna ruta local** en ellos.

- [MANUAL]. La lección de T24 de F-003 sigue vigente: los argumentos van
  **sueltos y entrecomillados**, no pegados por comas.

```powershell
az containerapp job start -g <resourceGroup> -n <job> `
  --command python --args "main.py" "load-aux"

# Esperar a que termine (y anotar el nombre de la ejecución):
az containerapp job execution list -g <resourceGroup> -n <job> `
  --query "[0].{n:name, estado:properties.status}" -o table

# Los logs tardan unos minutos en indexarse:
$ws = az monitor log-analytics workspace show -g <resourceGroup> -n <logAnalytics> --query customerId -o tsv
az monitor log-analytics query -w $ws --analytics-query "ContainerAppConsoleLogs_CL | where ContainerJobName_s == '<job>' | where Log_s has 'aux_file_read' | project TimeGenerated, Log_s | order by TimeGenerated asc | take 20" -o table
```

  **Correcto si** salen tres líneas `aux_file_read`, las tres con
  `"origen": "blob"`, y ninguna contiene `OneDrive`, una unidad de disco
  (`C:\`, `D:\`) ni `\\`. Si la consulta devuelve cero filas, comprobar
  primero el nombre de columna con `ContainerAppConsoleLogs_CL | getschema`
  antes de concluir que el job no leyó: ya pasó una vez
  (`ContainerAppName_s` no existe para un job; la columna es
  `ContainerJobName_s`).

### Verificación 3 de F-004 · prueba negativa de permisos

> **R10.** SI el humano no tiene **ningún** rol de datos de blob sobre la
> cuenta (`Storage Blob Data Reader`, `Contributor` u `Owner`), ENTONCES
> `python main.py load-aux` debe fallar con un mensaje que nombre el rol
> **`Storage Blob Data Reader`** y las dos salidas según el entorno
> (`az login` en el puesto, identidad gestionada asignada al job en Azure).

Matiz que la redacción original de F-004 no recogía y que aquí es
bloqueante: **retirar solo `Storage Blob Data Reader` no prueba nada** si
el humano conserva `Storage Blob Data Contributor` (que incluye lectura).
Hay que retirar **todos** los roles de datos de blob que R6 haya listado
para su cuenta, y restaurarlos **exactamente** después.

- [MANUAL]

```powershell
# 1. Retirar CADA rol de datos de blob que R6 listó para su cuenta:
az role assignment delete --role "<rol tal cual salió en R6>" `
  --assignee "<su cuenta>" --scope $cuenta
# 2. Esperar a la propagación (un par de minutos) y provocar el fallo:
python main.py load-aux
# 3. RESTAURAR, uno por uno, exactamente los mismos roles:
az role assignment create --role "<el mismo rol>" --assignee "<su cuenta>" --scope $cuenta
# 4. Comprobar que la lista vuelve a ser la de R6 y que la lectura funciona:
az role assignment list --scope $cuenta --query "[].{rol:roleDefinitionName, quien:principalName}" -o table
python main.py load-aux
```

  **Correcto si**: en el paso 2 el step queda `FAILED` con un mensaje que
  contiene literalmente `Storage Blob Data Reader`, menciona `az login` y
  menciona la identidad gestionada; y en el paso 4 la lista de roles es
  idéntica a la de R6 y `load-aux` vuelve a dar `SUCCESS` con
  `origen=blob`. **La feature no puede cerrarse con el paso 4 sin hacer.**

> **R11.** SI el mensaje de error de R10 no nombra el rol o no dice qué
> hacer, ENTONCES la verificación es un FALLO de F-004 y se anota como tal:
> no se «interpreta» un mensaje que en la práctica no sirve. El arreglo
> sería feature propia, no un parche aquí.

- [MANUAL] Veredicto escrito en `progress/impl_F-023.md` con el texto real
  del error (que no contiene secretos: F-004 R6 garantiza que ni siquiera
  filtra un token).

---

## Bloque 2 · Retirar las copias viejas de los secretos

Contexto: las dos contraseñas del datamart (`pgSecretName` y
`pgReadonlySecretName` del fichero de entorno) nacieron en
**`kv-albaranes-rs9k2`** —el vault de **otro proyecto**— porque el vault
propio no existía todavía (F-005). El paso 8 bis de F-003 las copió a
`kv-datamart-seg-dev` y dejó escrito que las copias viejas eran **la vuelta
atrás** hasta que el job acreditara una ejecución correcta. Ya la tiene.

> **R12.** MIENTRAS no se cumplan **las cuatro** precondiciones —(a) el
> vault del proyecto lista los dos secretos **por nombre**, (b) el job tiene
> una ejecución `Succeeded` posterior a la migración, (c) el vault de origen
> tiene **soft-delete** activo, y (d) el humano confirma que ningún otro
> consumidor lee esos dos secretos de `kv-albaranes-rs9k2`— el sistema no
> debe borrar nada.

- [MANUAL]

```powershell
# (a) por NOMBRE. Nunca `az keyvault secret show` sobre estos dos nombres.
az keyvault secret list --vault-name <keyVault> --query "[].name" -o tsv
# (b) ejecución correcta del job:
az containerapp job execution list -g <resourceGroup> -n <job> `
  --query "[].{n:name, estado:properties.status, fin:properties.endTime}" -o table
# (c) red de seguridad del vault de origen:
az keyvault show -n kv-albaranes-rs9k2 `
  --query "{soft:properties.enableSoftDelete, purge:properties.enablePurgeProtection, dias:properties.softDeleteRetentionInDays}" -o json
```

  **Correcto si** (a) devuelve los dos nombres más `SIGRID-API-FUNCTION-KEY`,
  (b) muestra al menos una `Succeeded` posterior a la migración, y (c)
  devuelve `soft: true` con su retención en días. (d) es una pregunta al
  humano, con su respuesta anotada.

> **R13.** SI el vault de origen **no** tiene soft-delete activo, ENTONCES
> el sistema debe **parar** y no borrar: sin soft-delete el borrado es
> irreversible y no hay vuelta atrás para una contraseña de producción.

- [MANUAL] Veredicto de la salida de R12 (c). Si sale `soft: false`, la
  feature queda `blocked` con el motivo en `progress/current.md`.

> **R14.** CUANDO el humano dé su **OK explícito y registrado** para ese
> borrado concreto, el sistema debe borrar **exactamente los dos secretos
> del datamart** en `kv-albaranes-rs9k2`, sin leer ni imprimir ningún
> valor, y dejarlos recuperables durante la retención del vault.

Es una **escritura destructiva en un recurso de otro proyecto**: el OK va
citado literalmente, con fecha y hora, en `progress/impl_F-023.md`. Los
demás secretos de ese vault (los de `albaranes`) **no se tocan ni se
listan con detalle**.

- [MANUAL]

```powershell
az keyvault secret delete --vault-name kv-albaranes-rs9k2 -n <pgSecretName> -o none
az keyvault secret delete --vault-name kv-albaranes-rs9k2 -n <pgReadonlySecretName> -o none

# Comprobación, siempre por nombre:
az keyvault secret list --vault-name kv-albaranes-rs9k2 --query "[].name" -o tsv
az keyvault secret list-deleted --vault-name kv-albaranes-rs9k2 --query "[].name" -o tsv
```

  **Correcto si** los dos nombres desaparecen del primer listado y
  aparecen en el de borrados (esa es la vuelta atrás:
  `az keyvault secret recover`). **PROHIBIDO `az keyvault secret purge`**:
  destruiría la única red de seguridad. **PROHIBIDO
  `az keyvault secret show`** sobre estos nombres, aquí y en cualquier
  comprobación posterior.

> **R15.** CUANDO se hayan borrado las copias viejas, el job debe seguir
> ejecutando correctamente: la referencia a Key Vault que resuelve
> `PG_PASSWORD` apunta al vault del proyecto y no debe haberse visto
> afectada.

- [MANUAL] Prueba barata inmediata (segundos, no 3 h) más confirmación de
  la siguiente nocturna:

```powershell
az containerapp job start -g <resourceGroup> -n <job> --command python --args "main.py" "check-pg"
az containerapp job execution list -g <resourceGroup> -n <job> `
  --query "[0].{n:name, estado:properties.status}" -o table
```

  **Correcto si** esa ejecución termina `Succeeded` (prueba que la
  contraseña se resuelve y que Postgres la acepta) **y** si la siguiente
  ejecución nocturna programada también termina `Succeeded` sin correo de
  alerta. Las dos cosas, no una.

---

## Bloque 3 · Limpieza del puesto

> **R16.** CUANDO el humano retire del fichero `hosts` la línea que fija a
> mano la dirección del servidor de Postgres, el nombre debe volver a
> resolverse por DNS y el puesto debe seguir conectando.

La línea se puso el 2026-08-14 como blindaje contra una red inestable y es
deuda pura: si Azure cambia la dirección del servidor, el puesto deja de
conectar **y nadie sabrá por qué**.

- [MANUAL] (consola de administrador; el fichero es
  `C:\Windows\System32\drivers\etc\hosts`)

```powershell
Select-String -Path C:\Windows\System32\drivers\etc\hosts -Pattern "postgres.database.azure.com"
# ... retirar la línea con un editor abierto como administrador ...
Resolve-DnsName <pgHost> | Select-Object Name, Type
python main.py check-pg
```

  **Correcto si** el `Select-String` final no devuelve nada, el
  `Resolve-DnsName` responde y `check-pg` sigue diciendo la versión del
  servidor. `check-pg` es de solo lectura y no abre ejecución en `_meta`.

> **R17.** MIENTRAS queden verificaciones que se ejecutan **desde el
> puesto** —las de esta misma feature y la **Fase C de F-024** (T17–T20)—
> el sistema no debe retirar las reglas de firewall del puesto en
> `psql-albaranes-rs9k2`.

Retirarlas antes deja al humano sin `apply-grants`, sin `timings`, sin
`check-coherencia` y sin huellas: exactamente lo que F-024 necesita para
cerrar.

- [MANUAL] Comprobación de estado antes de tocar el firewall: F-024 con
  Fase C completa (o el humano acepta por escrito recrear la regla cuando
  la necesite, DA-2).

> **R18.** CUANDO se retiren las reglas del puesto, deben desaparecer
> **solo** las reglas creadas por este proyecto para el puesto (las
> `datamart-puesto-*`), y deben permanecer intactas la regla del entorno
> del job y la que autoriza a los servicios de Azure.

Borrar la regla del job apagaría la carga nocturna esa misma noche, con un
error de conexión que no apunta al firewall.

- [MANUAL]. ⚠ **Escritura sobre un recurso de `albaranes`**: exige
  autorización expresa del humano y la ejecuta él. El flag del servidor lo
  ha cambiado alguna versión de `az`: **comprobar primero con `--help`** y,
  si difiere, corregir `infra/README.md` (defecto ya anotado en
  `progress/current.md`).

```powershell
az postgres flexible-server firewall-rule list --help    # confirmar el flag del servidor
az postgres flexible-server firewall-rule list -g <pgResourceGroup> --name psql-albaranes-rs9k2 -o table
# Por CADA regla `datamart-puesto-*` que salga:
az postgres flexible-server firewall-rule delete -g <pgResourceGroup> --name psql-albaranes-rs9k2 `
  --rule-name <nombre de la regla> --yes
az postgres flexible-server firewall-rule list -g <pgResourceGroup> --name psql-albaranes-rs9k2 -o table
```

  **Correcto si** el listado final **no** contiene ninguna
  `datamart-puesto-*` y **sí** contiene la regla del job (`<job>`) y la de
  servicios de Azure, más las que ya existían de `albaranes`.

> **R19.** DONDE el humano confirme por escrito que ninguna otra persona ni
> proceso las usa, el sistema debe retirar también las dos reglas antiguas
> ajenas al datamart (`ClientPgris` y `FirewallIPAddress_2026-6-16`); en
> caso contrario debe dejarlas y anotar por qué.

Son de `albaranes`, anteriores a este proyecto. La opción por defecto es
**no borrarlas**: el coste de dejarlas es cero y el de equivocarse es
cortar el acceso de otro.

- [MANUAL] Respuesta del humano anotada literalmente, y listado posterior
  como evidencia.

> **R20.** El sistema debe dejar **decidida y anotada** la política de
> `SIGRID_API_PAGE_SIZE`: qué valor queda en el `.env` del puesto, por qué,
> y la constatación de que el job **no** depende de esa variable.

- [TEST] la segunda mitad la fija R4.
- [MANUAL] la primera: decisión del humano escrita en
  `progress/impl_F-023.md` y en `progress/current.md`. `.env` y `.env.*.bak`
  son del humano; **ningún agente los edita**. `.env.example` conserva el
  valor por defecto del código (no se toca salvo que el humano decida
  cambiar ese defecto, que sería otra feature).

---

## Bloque 4 · Documentación y cierre

> **R21.** El sistema debe reflejar el estado final en la documentación, en
> el mismo trabajo: `infra/README.md` (los Excels viven en el blob con sus
> URIs; los secretos viven **solo** en el vault del proyecto y las copias
> viejas ya no son la vuelta atrás; cómo volver a autorizar el puesto en el
> firewall cuando haga falta; el flag correcto del comando de firewall) y
> `azure-apps/datamart_seg_anual.md` (qué consume y desde dónde, dónde
> viven los secretos, y corrección de lo que ese documento sigue dando por
> «no desplegado»).

Regla del `CLAUDE.md` raíz: el dueño del documento es el proyecto que
describe, y se actualiza **en el mismo trabajo**, no después. Un documento
desactualizado que parece vigente hace más daño que no tenerlo.

- Verificación: revisión del reviewer (C3), contrastando cada afirmación
  del documento contra lo verificado en los bloques 1–3.

> **R22.** El sistema debe dejar cerrada la trazabilidad de F-003:
> `specs/F-003-infra-caj/tasks.md` con T23–T26 marcadas y las tres
> verificaciones heredadas de F-004 marcadas con su resultado real y la
> fecha.

- Verificación: revisión del reviewer (C4) contra los resultados anotados
  en `progress/impl_F-023.md`.

> **R23.** El sistema debe terminar con `bash harness/init.sh` en verde.

- Verificación: código de salida 0.

---

## Trazabilidad con los criterios `acceptance` de `harness/features.json`

| `acceptance` | Requisitos |
|---|---|
| Excels subidos, rol al humano, `AUX_EXCEL_*` a URIs de blob | R1, R2, R5, R6 |
| Verificación 1 (`load-aux` desde el puesto) | R7, R8 |
| Verificación 2 (job con identidad gestionada) | R9 |
| Verificación 3 (prueba negativa de permisos) | R10, R11 |
| Copias viejas retiradas con OK explícito, sin `secret show` | R12, R13, R14, R15 |
| Puesto limpio (hosts, firewall, `SIGRID_API_PAGE_SIZE`) | R16, R17, R18, R19, R20, R4 |
| README de infra y `azure-apps/` actualizados | R21 |
| F-003 con T23–T26 marcadas, reviewer e `init.sh` verde | R22, R23 |
| (invariante añadido por la spec) rutas locales imposibles | R3 |
