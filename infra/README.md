<!-- infra/README.md -->
# `infra/` · Despliegue del datamart como Container Apps Job

Aquí vive **todo** el aprovisionamiento del ETL en Azure. La idea de fondo es
una sola: **los datos y el procedimiento están separados**.

- **Datos**: `infra/env/<entorno>.json`. Es el único sitio del repositorio con
  nombres de recurso.
- **Procedimiento**: los `.ps1`, iguales para todos los entornos. Ninguno
  contiene el nombre de un recurso, y hay un test que lo comprueba.

Ni la suscripción, ni el tenant, ni una clave, ni una contraseña, ni un correo
entran en estos ficheros. La suscripción sale de `$env:AZ_SUBSCRIPTION_ID` o
del contexto de `az`.

---

## ⚠ Antes de desplegar: dos puertas cerradas

Los scripts están completos y probados como texto, pero **no se han ejecutado
contra Azure**. Hay dos cosas que deben cerrarse antes de llegar al job:

1. **El disco del servidor de Postgres (incidente del 2026-08-09).** Una carga
   completa llenó el disco de 32 GB del servidor compartido y lo dejó en solo
   lectura diez minutos, afectando a otras dos aplicaciones en producción. El
   job nocturno ejecuta **esa misma carga**. Qué hacer ya está decidido —la
   opción B, trocear el build—, así que lo que falta no es decidir: es
   ejecutarlo. **Hasta que `F-019` (build de `stg.plan_mensual` por tramos)
   esté implementada y verificada contra Azure, el job no debe quedar
   programado**: no llegues al paso 9 de la tabla.

   No queda en la prosa. `infra/env/<entorno>.json` declara
   `jobProgramable: false` y **el script del paso 9 aborta con `throw`**
   mientras siga así; ponerlo a `true` con `F-019` sin cerrar en
   `harness/features.json` deja además la suite de tests en rojo. El
   comprobador de prerrequisitos (paso 1) mide por su cuenta la ocupación del
   disco y falla por encima del 60 %, pero eso no basta: tras revertirse la
   transacción del incidente el disco volvió al 42 % y esa comprobación
   pasaría.

2. **DA-4 · autenticación contra Postgres. CERRADA el 2026-08-10: opción B.**
   La spec original decía «sin contraseñas, autenticación Entra», pero **el
   servidor tiene la autenticación Entra deshabilitada** y habilitarla es una
   operación de servidor que afecta a las otras bases; el humano la descartó el
   2026-08-08. Tal cual, el job se creaba correctamente y **fallaba al conectar
   todas las noches**.

   **Resolución:** el job se autentica como el rol nativo `sigrid_dm_app` con su
   contraseña, que viaja como **referencia a Key Vault resuelta por la identidad
   gestionada** — exactamente el mismo mecanismo que la clave de `sigrid-api`.
   Ningún valor de secreto entra en el repositorio, en un script ni en la línea
   de comandos. El modo `entra` queda implementado y **dormido** por si algún
   día se habilita en el servidor. La enmienda está escrita en
   `specs/F-003-infra-caj/requirements.md` §Enmiendas.

   **Lo que esto añade al despliegue:** un **paso 8 bis** —migrar las
   contraseñas al vault del proyecto— que va **antes** de crear el job. Está
   abajo, en «Pasos que exigen autorización expresa».

---

## Cómo se ejecutan (Windows PowerShell 5.1)

Todos cargan primero `00_vars.ps1` y se lanzan igual, desde la raíz del
repositorio:

```powershell
powershell -NoProfile -File infra\05_check_prereqs.ps1
```

**No uses `pwsh`**: en el puesto donde se despliega **no está instalado**, y los
scripts están escritos y probados para **Windows PowerShell 5.1**, que es la que
viene con el sistema. Eso no es un detalle cosmético: 5.1 tiene dos trampas al
llamar a un ejecutable nativo que costaron un despliegue a medias el 2026-08-10.

- El **stderr** de un programa nativo se convierte en un error **terminante**
  cuando la preferencia de errores es `Stop`. Y `az` contesta por stderr algo tan
  normal como `ResourceNotFound`, que es la respuesta esperada de cualquier
  comprobación «¿existe ya?» en un primer despliegue.
- `az` es un **`.cmd`**, así que `cmd.exe` vuelve a interpretar la línea: una
  consulta `--query` con paréntesis, `?`, `|` o `!` se rompe con «No se esperaba
  -o en este momento».

Las dos están resueltas **en un solo sitio**: la función `Invoke-Az` de
`00_vars.ps1`, por la que pasan **todas** las llamadas (hay un test que lo
comprueba). Si añades una llamada a Azure, úsala; no escribas `az` directamente
ni filtres con JMESPath usando esos caracteres.

## Orden de ejecución

Todos los scripts admiten `-Entorno <nombre>` y todos son **idempotentes**:
repetirlos no rompe nada. Se ejecutan desde la raíz del repositorio.

| # | Script | Qué hace | ¿Escribe? |
|---|---|---|---|
| — | `00_vars.ps1` | Carga y **valida** `env/<entorno>.json`; deriva el tag de imagen y las utilidades comunes. No se ejecuta suelto: lo cargan los demás. | No |
| 1 | `05_check_prereqs.ps1` | **Solo lectura.** Sesión de `az`, extensión `containerapp`, registro de contenedores, servidor de Postgres (modo de autenticación y ocupación del disco) y permiso para crear asignaciones de rol. | No |
| 2 | `10_create_rg.ps1` | Resource group con los tags `acens-*`. | Sí |
| — | `15_provision_db.ps1` | Base y roles del datamart (es de F-005, ya ejecutado). Sin `-Ejecutar` solo imprime el plan. | Solo con `-Ejecutar` |
| 3 | `20_create_observability.ps1` | Workspace de Log Analytics propio. | Sí |
| 4 | `30_create_env.ps1` | Entorno de Container Apps **sin red virtual**. Imprime la **IP de salida**: apúntala. | Sí |
| 5 | `40_create_storage.ps1` | Cuenta de almacenamiento endurecida y contenedor de los Excels auxiliares. | Sí |
| 6 | `50_create_keyvault.ps1` | Key Vault con RBAC, **vacío**. | Sí |
| 7 | `60_create_identity.ps1` | Identidad gestionada + sus **tres** permisos. | Sí |
| 8 | `70_build_image.ps1` | Construye y publica la imagen con tag fechado. | Sí |
| 9 | `80_create_job.ps1` | Crea el job **programado**. Exige `-Confirmar` y **está bloqueado por `F-019`** (arriba). | Sí |
| — | `85_update_job.ps1` | Despliegue habitual: apunta el job a una imagen nueva. | Sí |
| 10 | `90_create_alert.ps1` | Grupo de acción (reutiliza el que haya) y alerta de fallo. | Sí |

Entre medias hay **tres** pasos **que no son scripts** y que hace el humano:
cargar la clave de la API en el vault (después del 6), autorizar la regla de
firewall del Postgres (después del 4) y **migrar las contraseñas de Postgres al
vault del proyecto** (paso **8 bis**, después del 8 y **antes del 9**). Están
abajo.

### Despliegue habitual, cuando ya está todo montado

```powershell
powershell -NoProfile -File infra/70_build_image.ps1     # publica una imagen nueva
powershell -NoProfile -File infra/85_update_job.ps1      # el job pasa a usarla
```

---

## Pasos que exigen autorización expresa del humano

### 1. Cargar la clave de la API en el vault

Crear el vault **no** concede permiso para escribir secretos: hace falta el rol
`Key Vault Secrets Officer` sobre él.

```powershell
az keyvault secret set --vault-name <keyVault> -n SIGRID-API-FUNCTION-KEY --file <ruta>
az keyvault secret list --vault-name <keyVault> --query "[].name" -o tsv
```

Con `--file` y no con `--value`: así el secreto no queda en el historial del
shell. **Nunca `az keyvault secret show`**, y el valor no se escribe en ningún
fichero del repositorio ni en `progress/`.

### 2. Autorizar la IP del job en el firewall del Postgres

Es una **escritura sobre un recurso de otro proyecto**. Requiere autorización
del humano, recurso a recurso, y la ejecuta él.

```powershell
az containerapp env show -g <resourceGroup> -n <containerAppsEnv> --query properties.staticIp -o tsv
az postgres flexible-server firewall-rule create -g <pgResourceGroup> -n <servidor> `
  --rule-name <job> --start-ip-address <ip> --end-ip-address <ip>
az postgres flexible-server firewall-rule list -g <pgResourceGroup> -n <servidor> -o table
```

El servidor tiene además una regla que autoriza a cualquier recurso de Azure.
**No se debe depender de ella**: autoriza también a suscripciones ajenas.
Revisarla es materia de otra feature, no de esta.

### 3. Paso 8 bis · Migrar las contraseñas de Postgres al vault del proyecto

Las contraseñas del datamart (`pg-sigrid-dm-app`, la que usa el job, y
`pg-mcp-sigrid-dm-ro`, la del MCP) viven desde F-005 en **`kv-albaranes-rs9k2`**,
el vault de otro proyecto. Con DA-4 cerrada, el job las necesita en **su propio
vault**, que es sobre el que la identidad gestionada tiene
`Key Vault Secrets User`. Se migran **antes de crear el job**: el paso 9 aborta
si el secreto no está.

Hace falta: `Key Vault Secrets User` (o superior) sobre el vault **de origen** y
`Key Vault Secrets Officer` sobre el **de destino**.

```powershell
$origen  = "kv-albaranes-rs9k2"
$destino = "<keyVault>"                     # del fichero de entorno

foreach ($nombre in @("<pgSecretName>", "<pgReadonlySecretName>")) {
    $valor = az keyvault secret show --vault-name $origen -n $nombre --query value -o tsv
    if (-not $valor) { throw "no se ha podido leer '$nombre' de $origen" }
    az keyvault secret set --vault-name $destino -n $nombre --value $valor -o none
    if ($LASTEXITCODE -ne 0) { throw "no se ha podido escribir '$nombre' en $destino" }
    $valor = $null
}
[System.GC]::Collect()
```

**Por qué así y no de otra forma** (importa, y no es paranoia):

- **`show` siempre asignado a una variable, nunca suelto.** Un `show` a secas
  imprime la contraseña en la consola, y de ahí pasa al scrollback y a cualquier
  captura o registro de sesión.
- **`-o none` en el `set`.** Sin él, `az keyvault secret set` devuelve el objeto
  del secreto **incluyendo su valor**: el secreto acabaría en pantalla justo en
  el paso que pretendía protegerlo.
- **Nada de ficheros temporales.** Es la alternativa que parece más limpia y es
  peor: deja el valor en disco, y en PowerShell 5.1 la redirección (`>`,
  `Out-File`, `Set-Content`) añade BOM y salto de línea, con lo que además
  **corrompería la contraseña** — el job fallaría al autenticar con un error que
  no apunta a nada.
- **Nada de canalizar `show` a `set --value @-`.** La tubería de PowerShell
  añade igualmente el salto de línea final, con el mismo resultado.
- El **historial del shell** guarda la línea tal cual se escribió: `$valor`, no
  la contraseña. Por eso el valor nunca se teclea.
- **Riesgo residual, asumido y consciente:** durante el instante de la llamada,
  la contraseña está en la línea de comandos del proceso `az`, visible para otro
  proceso del mismo usuario en la misma máquina. Es el puesto del propio
  administrador que la conoce, y las alternativas (fichero en disco) son
  peores.

Verificación, **solo por nombre**:

```powershell
az keyvault secret list --vault-name <keyVault> --query "[].name" -o tsv
```

Deben aparecer los dos nombres, más `SIGRID-API-FUNCTION-KEY`. **Nunca uses
`az keyvault secret show` para «comprobar» que se copió bien.**

**Las copias viejas de `kv-albaranes-rs9k2` no se borran todavía**: se retiran
cuando el job haya completado una ejecución correcta (después del paso 10 de
verificación). Hasta entonces son la vuelta atrás.

### 4. Rol de plano de datos sobre la cuenta de almacenamiento

La cuenta se crea **sin clave compartida**, así que ni las herramientas
gráficas entran con la clave: todo el acceso es por identidad. Para crear el
contenedor o subir un Excel hace falta un rol de datos (`Storage Blob Data
Contributor`) sobre la cuenta; ser Owner de la suscripción **no** basta. Es
deliberado, y es lo que tendrá que resolver la feature de subida de Excels.

---

## Consultar los logs de una ejecución

```powershell
$ws = az monitor log-analytics workspace show -g <resourceGroup> -n <logAnalytics> --query customerId -o tsv
az monitor log-analytics query -w $ws --analytics-query "ContainerAppConsoleLogs_CL | where ContainerAppName_s == '<job>' | project TimeGenerated, Log_s | order by TimeGenerated desc | take 50" -o table
```

Si algún nombre de columna no coincide, comprueba el esquema real con
`ContainerAppConsoleLogs_CL | getschema` y **corrige este README**; no
improvises otra vía.

Para saber qué build corrió, una ejecución puntual con el comando cambiado (no
altera la programada):

```powershell
az containerapp job start -g <resourceGroup> -n <job> --command "python" --args "main.py,version"
```

## Probar la alerta

Una alerta que no se ha visto llegar no está verificada. La prueba, de extremo
a extremo:

```powershell
az containerapp job start -g <resourceGroup> -n <job> --command "python" --args "main.py,check-pg"
```

lanzado con el acceso a la base roto (por ejemplo, retirando temporalmente la
regla de firewall) debe producir una ejecución `Failed` **y un correo
recibido**. Anota la hora del fallo y la de recepción en `progress/current.md`.

## Verificaciones heredadas de F-004 (lectura de los Excels desde blob)

F-004 dejó tres comprobaciones bloqueadas porque necesitaban esta
infraestructura. Se hacen después del paso 7:

1. Desde el puesto, con `az login` y el rol de lectura de blobs, apuntar
   `AUX_EXCEL_*` a los blobs reales y ejecutar `python main.py load-aux`:
   debe dar `SUCCESS` con `origen=blob`.
2. Desde el job, con su identidad gestionada: lanzar una ejecución y buscar en
   los logs el evento `aux_file_read` con los tres ficheros y **ninguna ruta
   local**.
3. Prueba negativa: retirar el rol, repetir `load-aux` y comprobar que el error
   dice qué rol falta y qué hacer. **Volver a asignarlo después.**

Aviso: `azure-identity` y `azure-storage-blob` están declaradas en
`requirements.txt` pero pueden no estar **instaladas** en el puesto. La
comprobación 1 falla con `ModuleNotFoundError` hasta que se ejecute
`pip install -r requirements.txt`.

---

## Añadir un entorno nuevo

No se toca ni se duplica ningún script:

```powershell
Copy-Item infra/env/dev.json infra/env/pro.json    # y se ajustan los nombres
powershell -NoProfile -File infra/05_check_prereqs.ps1 -Entorno pro
```

El entorno se resuelve, por este orden: el parámetro `-Entorno`, la variable
`$env:DATAMART_ENV` y, como último recurso, el que trae `00_vars.ps1` por
defecto. La clave `environment` del fichero debe coincidir con su nombre; si no,
`00_vars.ps1` aborta.

Los nombres de la cuenta de almacenamiento y del Key Vault son **globalmente
únicos**: si están tomados, se cambia el valor en el fichero de entorno y ya
está. Esa es exactamente la flexibilidad que da separar datos de procedimiento.

## Deuda conocida

El **ID de suscripción sigue en el historial de git**: estuvo escrito en
`00_vars.ps1` hasta esta feature. Quitarlo del árbol de trabajo no lo borra del
historial. No es una credencial —no da acceso por sí solo—, pero el criterio
del repositorio es no versionarlo. Reescribir la historia es una decisión del
humano y no se ha hecho aquí.
