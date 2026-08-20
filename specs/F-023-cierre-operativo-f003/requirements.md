> ## NOTA DE CIERRE · 2026-08-20
>
> **Esta spec se escribió el 2026-08-18 y la feature se cerró sin ella**, con
> un alcance más pequeño. Se conserva porque recoge las **siete decisiones**
> que cerró el humano y el diseño de las verificaciones, que sí se ejecutaron.
>
> **Lo que cambió respecto a lo que aquí se lee**: el 2026-08-19 los bloques 2
> (retirada de secretos duplicados en el vault de *albaranes*) y 3 (limpieza
> del rastro en el puesto) **salieron de F-023** y pasaron a **F-032** con
> prioridad baja, porque era limpieza operativa que estaba reteniendo el cierre
> de F-003 y, con él, el arranque de la carga incremental y del MCP.
>
> **Lo que sí se hizo y está verificado**: las tres verificaciones de F-004,
> con sus salidas reales en `progress/manual_F-023.md` y el veredicto en
> `progress/review_F-023_F-003_cierre.md`. Ojo a una: la prueba negativa **no**
> se hizo como se describe aquí —quitando el rol y devolviéndolo—, sino
> apuntando a una cuenta sin ese rol; el reviewer lo dio por **mejor** que el
> requisito original, porque no exige permisos que el puesto no tiene y no deja
> ninguna asignación que devolver.
>
> **Y una que esta spec acertó y el `features.json` no recogió**: aquí F-023 es
> `critico`. El fichero la tenía en `estandar` hasta el cierre.

<!-- specs/F-023-cierre-operativo-f003/requirements.md -->
# F-023 · Cierre operativo de F-003 — Requisitos (EARS)

Rama: `feature/F-023-cierre-operativo-f003`. Rigor: **`critico`**, decidido
por el humano el 2026-08-18 (DA-1, cerrada en `design.md` §9). Motivo: dos
de los tres bloques escriben o borran sobre recursos de **otro proyecto en
producción** (`kv-albaranes-rs9k2` y `psql-albaranes-rs9k2`). El cambio del
campo `rigor` en `harness/features.json` lo hace el **líder**, no esta spec.

Consecuencias de `critico` que este documento asume: fase RED de los cinco
tests nuevos, cobertura y campaña de mutación ejecutadas y con su número
real, cero supervivientes, **las dieciséis verificaciones MANUAL con su
comando exacto y su resultado real**, y **acta con el OK del humano citado
literalmente para cada borrado** (R14 y R18).

## Qué es esta feature, y qué no

F-023 es **operación contra Azure**, no desarrollo. De los 24 requisitos de
abajo:

- **R1–R4 son automatizables con test** (cuatro requisitos, **cinco tests**):
  invariantes de configuración que impiden volver atrás.
- **R5–R20 son `MANUAL (humano)`** (dieciséis): once traen su comando exacto
  aquí; los cinco restantes (R11, R13, R17, R19, R20) son veredicto o
  decisión escrita del humano sobre la salida de otro.
- **R21–R24** los valida el reviewer (documentación, trazabilidad, backlog)
  y el código de salida de `init.sh`.

Cerrarla es lo único que separa a F-003 de su `done`.

**NO entra la carga de los Excels a las tablas `aux.*`.** Eso es **F-013**
y sigue `pending`: F-004 construyó la capacidad de **leer y validar** los
libros, no de volcarlos, porque el modelo destino no está acordado (la DA-1
**de F-004**, en `progress/current.md`, que no tiene nada que ver con las
DA de esta spec). Aquí se comprueba que la lectura
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
   la verificación 1. Consecuencia: el fichero de entorno **no se toca**.
   Si la fotografía inicial o R9 revelaran que el **job desplegado** no las
   tiene como URIs de blob, se aplica el plan cerrado de DA-6:
   `az containerapp job update --set-env-vars` a mano, documentado en el
   README; el fichero de entorno sigue sin tocarse y el job **no** se
   recrea.
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
   El bloque 3 la dejaría sin acceso. De ahí **R17**, que con DA-7 cerrada
   es una **puerta**: el bloque 3 no empieza hasta que la Fase C esté
   completa.
7. **El job no pasa `SIGRID_API_PAGE_SIZE`**: no está entre las variables
   de `80_create_job.ps1`, así que la carga nocturna usa el valor por
   defecto de `config/settings.py` (10000). Los 50000 son un apaño del
   `.env` del puesto para una red mala. Con DA-4 cerrada, el asunto afecta
   **solo al `.env` del puesto**, que no se versiona: se anota el valor y se
   cierra, y `.env.example` no se toca.
8. **Nadie más lee `pg-mcp-sigrid-dm-ro` de `kv-albaranes-rs9k2`** que se
   haya podido comprobar: el prototipo del MCP (`PycharmProjects/mcp-bbdd`)
   no usa Key Vault (solo aparece en dependencias de terceros), y ningún
   documento de `azure-apps/` menciona ese vault. Aun así, **R12 (d)** lo
   convierte en pregunta explícita al humano antes de borrar.

## Convenciones de este documento

- **[TEST]**: lo comprueba pytest sin red ni BBDD. El nombre del test es el
  contrato.
- **[MANUAL]**: solo se puede comprobar contra Azure o contra el puesto. Lo
  ejecuta **el humano**, con el comando exacto que se da aquí, y su
  resultado real (salida, hora) se anota en `progress/impl_F-023.md`.
- **[ACTA]**: además de lo anterior, el requisito es una **escritura
  destructiva** y el rigor `critico` exige que el informe cite
  **literalmente**, con fecha y hora, el OK del humano para ese borrado
  concreto. Sin acta no hay borrado, y un borrado sin acta se rechaza en la
  revisión aunque esté bien hecho. Son dos: **R14** y **R18**.
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

  La propagación de RBAC es de **consistencia eventual** y tarda un par de
  minutos: si el comando siguiente falla con
  `AuthorizationPermissionMismatch`, o si el `role assignment list` no
  muestra todavía un rol recién creado, **esperar y repetir antes de
  concluir nada**. Es la mitigación acordada en DA-5 (cerrada) para el mismo
  defecto que hoy hace fallar en falso a `60_create_identity.ps1`; ese
  arreglo va al backlog y **no se hace en esta feature**.

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
# 2. Esperar a la propagacion (un par de minutos; consistencia eventual,
#    DA-5) y provocar el fallo:
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

- [MANUAL] [ACTA] — con rigor `critico` (DA-1), el acta es condición de
  aprobación: primero el OK citado, después el borrado, después la
  evidencia. En ese orden.

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

> **R17.** MIENTRAS la **Fase C de F-024 (T17–T20)** no esté completa, el
> sistema no debe retirar ninguna regla de firewall del puesto en
> `psql-albaranes-rs9k2`.

Retirarlas antes deja al humano sin `apply-grants`, sin `timings`, sin
`check-coherencia` y sin huellas: exactamente lo que F-024 necesita para
cerrar. **DA-7 está cerrada y esto es una puerta, no una preferencia**: no
existe la variante «retirar ahora y recrear la regla cuando haga falta para
F-024».

- [MANUAL] Comprobación de estado **antes** de tocar el firewall: la Fase C
  de F-024 consta completa (estado en `harness/features.json` y en
  `progress/current.md`), y así se anota en el informe. Si no lo está, el
  bloque 3 **no empieza**.

> **R18.** CUANDO la puerta de R17 esté abierta y el humano dé su **OK
> explícito y registrado**, el sistema debe retirar **todas** las reglas
> `datamart-puesto-*` de `psql-albaranes-rs9k2`, sin dejar ninguna vigente,
> y deben permanecer intactas la regla del entorno del job y la que
> autoriza a los servicios de Azure.

DA-2 (opción A, cerrada): **el puesto no conserva ningún acceso fijo**. Las
direcciones de esas reglas están caducadas —la IP del humano rota— así que
dejarlas sería una puerta abierta que además no sirve. Borrar la regla del
job, en cambio, apagaría la carga nocturna esa misma noche con un error de
conexión que no apunta al firewall: por eso R18 nombra qué debe permanecer.

- [MANUAL] [ACTA]. ⚠ **Escritura destructiva sobre un recurso de
  `albaranes`**: exige autorización expresa del humano, citada literalmente
  en el informe con fecha y hora, y la ejecuta él. El flag del servidor lo
  ha cambiado alguna versión de `az`: **comprobar primero con `--help`** y,
  si difiere de `infra/README.md`, corregir el README (defecto ya anotado
  en `progress/current.md`).

```powershell
az postgres flexible-server firewall-rule list --help    # confirmar el flag del servidor
az postgres flexible-server firewall-rule list -g <pgResourceGroup> --name psql-albaranes-rs9k2 -o table
# Por CADA regla `datamart-puesto-*` que salga, sin excepcion:
az postgres flexible-server firewall-rule delete -g <pgResourceGroup> --name psql-albaranes-rs9k2 `
  --rule-name <nombre de la regla> --yes
az postgres flexible-server firewall-rule list -g <pgResourceGroup> --name psql-albaranes-rs9k2 -o table
```

  **Correcto si** el listado final **no** contiene **ninguna**
  `datamart-puesto-*` y **sí** contiene la regla del job (`<job>`) y la de
  servicios de Azure, más las que ya existían de `albaranes` (R19).

**Volver a autorizar el puesto cuando haga falta** (DA-2): este es el
procedimiento que sustituye a la regla fija y que R21 obliga a dejar escrito
en `infra/README.md`. La IP **no se escribe en el repositorio**: se usa en
el comando y se olvida.

```powershell
az postgres flexible-server firewall-rule create --help   # confirmar el flag del servidor
(Invoke-RestMethod "https://api.ipify.org?format=json").ip

az postgres flexible-server firewall-rule create -g <pgResourceGroup> --name psql-albaranes-rs9k2 `
  --rule-name datamart-puesto-pgris-<AAAA-MM-DD> `
  --start-ip-address <ip> --end-ip-address <ip>

az postgres flexible-server firewall-rule list -g <pgResourceGroup> --name psql-albaranes-rs9k2 -o table

# AL TERMINAR el trabajo, en el mismo trabajo:
az postgres flexible-server firewall-rule delete -g <pgResourceGroup> --name psql-albaranes-rs9k2 `
  --rule-name datamart-puesto-pgris-<AAAA-MM-DD> --yes
```

  Si durante el trabajo la IP rota dentro de una subred (pasó el
  2026-08-17), se crea **una sola** regla de rango con el mismo nombre
  datado y sufijo `-rango`, en vez de ir acumulando una regla por dirección.
  Es igual de temporal y se borra igual.

> **R19.** El sistema **no debe borrar** las dos reglas antiguas ajenas al
> datamart (`ClientPgris` y `FirewallIPAddress_2026-6-16`), y debe dejar
> escrito que se conservan **a propósito**.

DA-3, cerrada: son de `albaranes` y **anteriores a este proyecto**. Este
proyecto no sabe quién las usa y el coste de dejarlas es cero, mientras que
el de equivocarse es cortarle el acceso a otro. Que sigan ahí después de
F-023 **no es un olvido de la limpieza**: es la decisión, y por eso se
anota. Si algún día alguien quiere retirarlas, es trabajo de `albaranes`.

- [MANUAL] El listado final de R18 sirve de evidencia: las dos reglas
  aparecen intactas, y el informe dice explícitamente que se conservan por
  DA-3.

> **R20.** El sistema debe dejar **anotada y cerrada** la política de
> `SIGRID_API_PAGE_SIZE`: qué valor queda en el `.env` del puesto y por
> qué, y la constatación de que el job **no** depende de esa variable.

DA-4, cerrada: el asunto afecta **solo al `.env` del puesto**, que no se
versiona. Por tanto **`.env.example` no se toca** —conserva el valor por
defecto del código— y cambiar ese defecto sería otra feature. `.env` y
`.env.*.bak` son del humano: **ningún agente los edita**. Una vez anotado,
el asunto **no vuelve** como decisión pendiente a `progress/current.md`.

- [TEST] la segunda mitad la fija R4.
- [MANUAL] la primera: el valor y su motivo, escritos en
  `progress/impl_F-023.md`.

---

## Bloque 4 · Documentación y cierre

> **R21.** El sistema debe reflejar el estado final en la documentación, en
> el mismo trabajo: `infra/README.md` (los Excels viven en el blob con sus
> URIs; los secretos viven **solo** en el vault del proyecto y las copias
> viejas ya no son la vuelta atrás; **cómo volver a autorizar el puesto en
> el firewall cuando haga falta**, con el comando completo de R18, la
> convención de nombre datado y la obligación de borrarla al terminar;
> **cómo cambiar una variable de entorno de un job vivo**, con el comando de
> DA-6 y la comprobación posterior de que las referencias a secretos siguen
> en su sitio; el flag correcto del comando de firewall) y
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

> **R23.** El sistema debe dejar en el informe la **ficha de los dos
> defectos que van al backlog** —el de `60_create_identity.ps1` (DA-5) y la
> carencia de los guiones de despliegue para cambiar variables de entorno de
> un job vivo (DA-6)— con detalle suficiente para que el líder los dé de
> alta en `harness/features.json` **sin volver a investigarlos**.

Ninguno de los dos se arregla aquí. La ficha completa de ambos está en
`design.md` §9 (DA-5 y DA-6): fichero, líneas, causa, arreglo propuesto,
gravedad y cómo se verificaría. El informe la reproduce o la referencia sin
ambigüedad. **Ningún agente edita `harness/features.json`**: el alta la hace
el líder.

- Verificación: revisión del reviewer — las dos fichas existen y son
  accionables.

> **R24.** El sistema debe terminar con `bash harness/init.sh` en verde.

- Verificación: código de salida 0.

---

## Trazabilidad con los criterios `acceptance` de `harness/features.json`

| `acceptance` | Requisitos |
|---|---|
| Excels subidos, rol al humano, `AUX_EXCEL_*` a URIs de blob | R1, R2, R5, R6 |
| Verificación 1 (`load-aux` desde el puesto) | R7, R8 |
| Verificación 2 (job con identidad gestionada) | R9 |
| Verificación 3 (prueba negativa de permisos) | R10, R11 |
| Copias viejas retiradas con OK explícito, sin `secret show` | R12, R13, R14 (con acta), R15 |
| Puesto limpio (hosts, firewall, `SIGRID_API_PAGE_SIZE`) | R16, R17 (puerta), R18 (con acta), R19 (no se borran), R20, R4 |
| README de infra y `azure-apps/` actualizados | R21 |
| F-003 con T23–T26 marcadas, reviewer e `init.sh` verde | R22, R24 |
| (invariante añadido por la spec) rutas locales imposibles | R3 |
| (añadido por las decisiones cerradas) los dos defectos al backlog | R23 |
