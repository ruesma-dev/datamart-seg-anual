# infra/80_create_job.ps1
#
# Crea el Container Apps Job programado del datamart. Es el paso que pone la
# carga nocturna en marcha, asi que no se ejecuta por accidente: hace falta
# -Confirmar.
#
# ANTES DE EJECUTARLO, DOS PUERTAS ABIERTAS (leelas, no son burocracia):
#
#   1. INCIDENTE DEL 2026-08-09. La carga completa lleno el disco del servidor
#      de Postgres y lo dejo en solo lectura diez minutos, afectando a otras
#      dos aplicaciones en produccion. Este job ejecuta esa MISMA carga todas
#      las noches. Hasta que el humano decida que hacer con el disco o con la
#      consulta que lo llena, el job NO debe quedar programado.
#   2. DECISION DA-4. El entorno declara autenticacion Entra contra Postgres
#      porque el job no puede llevar contrasena (R10), pero el servidor tiene
#      esa autenticacion deshabilitada y habilitarla afecta a las otras bases.
#      05_check_prereqs.ps1 lo comprueba y falla si no cuadra.
#
# Lo que este script NO hace, a proposito:
#
#   - No sobrescribe el punto de entrada de la imagen. El alcance de la carga
#     nocturna esta escrito en el Dockerfile y en ningun sitio mas: si
#     estuviera en dos, un dia dejarian de coincidir (R8).
#   - No pasa ninguna contrasena. El unico secreto del job es la clave de la
#     API de Sigrid, y viaja como referencia al vault resuelta por la identidad
#     gestionada, no como valor (R10).
#
# Actualizar la imagen de un job que ya existe es 85_update_job.ps1.

[CmdletBinding()]
param(
    [string]$Entorno,
    [string]$Tag,
    [switch]$Confirmar
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\00_vars.ps1" -Entorno $Entorno

# --- 1. Puertas -------------------------------------------------------------

if (-not $Confirmar) {
    Write-Host ""
    Write-Host "Este script deja el job PROGRAMADO ($($CFG.cron), UTC)." -ForegroundColor Yellow
    Write-Host "Lee la cabecera del fichero: hay dos decisiones abiertas (disco del" -ForegroundColor Yellow
    Write-Host "servidor y DA-4) que deben cerrarse antes." -ForegroundColor Yellow
    Write-Host "Cuando lo tengas claro, repite con -Confirmar."
    exit 0
}

if ($CFG.pgAuthMode -ne "entra") {
    throw ("el entorno pide autenticacion '$($CFG.pgAuthMode)' contra Postgres y este " +
           "script no puede pasar credenciales al contenedor (R10). Cierra DA-4 antes.")
}

$yaExiste = az containerapp job show -g $CFG.resourceGroup -n $CFG.job --query id -o tsv 2>$null
if ($LASTEXITCODE -eq 0 -and $yaExiste) {
    throw "el job '$($CFG.job)' ya existe. Para cambiarle la imagen usa 85_update_job.ps1."
}

# --- 2. Piezas que tienen que existir ya ------------------------------------

$identidad = az identity show -g $CFG.resourceGroup -n $CFG.managedIdentity `
    --query "{id:id, clientId:clientId}" -o json
Confirmar-Exito "no se encuentra la identidad gestionada: ejecuta antes 60_create_identity.ps1"
$uami = $identidad | ConvertFrom-Json

$vaultUri = az keyvault show -g $CFG.resourceGroup -n $CFG.keyVault `
    --query properties.vaultUri -o tsv
Confirmar-Exito "no se encuentra el Key Vault: ejecuta antes 50_create_keyvault.ps1"

# Se comprueba que el secreto ESTA, sin leer su valor: basta con el listado de
# nombres. Si falta, el job arrancaria y moriria al llamar a la API.
$secretos = az keyvault secret list --vault-name $CFG.keyVault --query "[].name" -o tsv
Confirmar-Exito "no se puede listar el contenido del vault (te falta rol sobre el vault)"
if (($secretos -split "`n") -notcontains $CFG.sigridSecretName) {
    throw "falta el secreto '$($CFG.sigridSecretName)' en el vault. Es la tarea T20 del humano."
}

$uriSecreto = "{0}secrets/{1}" -f $vaultUri, $CFG.sigridSecretName

# --- 3. La imagen: la que se diga, o la ultima publicada --------------------

if (-not $Tag) {
    $Tag = az acr repository show-tags -n $CFG.acrName --repository $CFG.imageRepository `
        --orderby time_desc --top 1 -o tsv
    Confirmar-Exito "no hay ninguna imagen publicada: ejecuta antes 70_build_image.ps1"
}
$imagen = "{0}.azurecr.io/{1}:{2}" -f $CFG.acrName, $CFG.imageRepository, $Tag

# --- 4. Variables de entorno del contenedor ---------------------------------
#
# Los NOMBRES se escriben aqui y los valores salen del fichero de entorno. Que
# los nombres esten escritos es lo que permite que un test compruebe, sin tocar
# Azure, que cada uno existe de verdad en config/settings.py (R7): una variable
# mal escrita se ignoraria en silencio y la carga correria con otro valor.

$baseAux = "https://{0}.blob.core.windows.net/{1}" -f $CFG.storageAccount, $CFG.auxContainer

Write-Host "Creando el job '$($CFG.job)' con la imagen $imagen..." -ForegroundColor Cyan

az containerapp job create `
    -g $CFG.resourceGroup -n $CFG.job --environment $CFG.containerAppsEnv `
    --trigger-type Schedule --cron-expression $CFG.cron `
    --replica-timeout $CFG.replicaTimeoutSeconds `
    --replica-retry-limit $CFG.replicaRetryLimit `
    --parallelism $CFG.parallelism `
    --replica-completion-count $CFG.replicaCompletionCount `
    --image $imagen --cpu $CFG.cpu --memory $CFG.memory `
    --mi-user-assigned $uami.id `
    --registry-server "$($CFG.acrName).azurecr.io" `
    --registry-identity $uami.id `
    --secrets "$($CFG.jobSecretName)=keyvaultref:$uriSecreto,identityref:$($uami.id)" `
    --tags @(Get-EtiquetasCli) `
    --env-vars `
        "SIGRID_API_BASE_URL=$($CFG.sigridApiBaseUrl)" `
        "SIGRID_API_FUNCTION_KEY=secretref:$($CFG.jobSecretName)" `
        "PG_HOST=$($CFG.pgHost)" `
        "PG_PORT=$($CFG.pgPort)" `
        "PG_DB=$($CFG.pgDatabase)" `
        "PG_USER=$($CFG.pgUser)" `
        "PG_AUTH_MODE=$($CFG.pgAuthMode)" `
        "PG_SET_ROLE=$($CFG.pgSetRole)" `
        "PG_READONLY_ROLE=$($CFG.pgReadonlyRole)" `
        "PG_AUTO_CREATE_DB=$($CFG.pgAutoCreateDb)" `
        "AUX_EXCEL_TIPO_PARTIDA=$baseAux/$($CFG.auxBlobs.tipo_partida)" `
        "AUX_EXCEL_TIPO_COSTE=$baseAux/$($CFG.auxBlobs.tipo_coste)" `
        "AUX_EXCEL_MAPEO_PROPORCIONALES=$baseAux/$($CFG.auxBlobs.mapeo_proporcionales)" `
        "AZURE_CLIENT_ID=$($uami.clientId)" `
        "LOG_LEVEL=$($CFG.logLevel)" `
        "LOG_FORMAT=$($CFG.logFormat)" `
    -o none

Confirmar-Exito "no se ha podido crear el job"

# AZURE_CLIENT_ID no es configuracion del ETL: es lo que DefaultAzureCredential
# necesita para saber CUAL de las identidades del contenedor debe usar al leer
# los Excels del blob. Sin ella la lectura falla, y no falla hasta la primera
# noche que se intente.

# --- 5. Comprobacion ---------------------------------------------------------

az containerapp job show -g $CFG.resourceGroup -n $CFG.job `
    --query "{disparo:properties.configuration.triggerType, programacion:properties.configuration.scheduleTriggerConfig.cronExpression, identidad:identity.type, registro:properties.configuration.registries[0].identity, secretos:properties.configuration.secrets[].name, imagen:properties.template.containers[0].image}" `
    -o json
Confirmar-Exito "el job no responde despues de crearlo"

Write-Host ""
Write-Host "Job creado y PROGRAMADO." -ForegroundColor Green
Write-Host "Prueba manual: az containerapp job start -g $($CFG.resourceGroup) -n $($CFG.job)"
Write-Host "Si el disco del servidor sigue sin decidirse, considera dejar el job sin" -ForegroundColor Yellow
Write-Host "programacion hasta entonces: el nocturno ejecuta la carga completa." -ForegroundColor Yellow
