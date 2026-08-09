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

## ⚠ Antes de desplegar: dos decisiones abiertas

Los scripts están completos y probados como texto, pero **no se han ejecutado
contra Azure**. Hay dos cosas que el humano debe cerrar antes de llegar al job:

1. **El disco del servidor de Postgres (incidente del 2026-08-09).** Una carga
   completa llenó el disco de 32 GB del servidor compartido y lo dejó en solo
   lectura diez minutos, afectando a otras dos aplicaciones en producción. El
   job nocturno ejecuta **esa misma carga**. Hasta que se decida qué hacer
   (crecer el disco, trocear la consulta que lo llena o subir el SKU), **el job
   no debe quedar programado**: no llegues al paso 9 de la tabla. El
   comprobador de prerrequisitos (paso 1) mide la ocupación del disco y falla
   por encima del 60 %.

2. **DA-4 · autenticación contra Postgres.** El job no puede llevar contraseña
   (requisito R10), así que el fichero de entorno declara
   `pgAuthMode = "entra"`. Pero **el servidor tiene la autenticación Entra
   deshabilitada** y habilitarla es una operación de servidor que afecta a las
   otras bases; el humano la descartó el 2026-08-08. Mientras siga así, el job
   se crearía correctamente y **fallaría al conectar todas las noches**.
   El comprobador de prerrequisitos lo detecta y aborta. Las dos salidas posibles —
   habilitar Entra en el servidor, o enmendar R10 para permitir la contraseña
   como referencia a Key Vault— las decide el humano.

---

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
| 9 | `80_create_job.ps1` | Crea el job **programado**. Exige `-Confirmar`. | Sí |
| — | `85_update_job.ps1` | Despliegue habitual: apunta el job a una imagen nueva. | Sí |
| 10 | `90_create_alert.ps1` | Grupo de acción (reutiliza el que haya) y alerta de fallo. | Sí |

Entre medias hay dos pasos **que no son scripts** y que hace el humano: cargar
el secreto en el vault (después del 6) y autorizar la regla de firewall del
Postgres (después del 4). Están abajo.

### Despliegue habitual, cuando ya está todo montado

```powershell
pwsh -File infra/70_build_image.ps1     # publica una imagen nueva
pwsh -File infra/85_update_job.ps1      # el job pasa a usarla
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

### 3. Rol de plano de datos sobre la cuenta de almacenamiento

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
pwsh -File infra/05_check_prereqs.ps1 -Entorno pro
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
