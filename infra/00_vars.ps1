# infra/00_vars.ps1
#
# Cargador y validador de la configuracion del despliegue del datamart.
# Todos los demas scripts empiezan dot-sourceando este:
#
#     . "$PSScriptRoot\00_vars.ps1"
#
# REGLA DURA: aqui no hay ni un nombre de recurso. Todos viven en
# infra/env/<entorno>.json y se leen a traves de $CFG. Por eso montar otro
# entorno es copiar ese fichero y ejecutar con -Entorno <nombre>, sin duplicar
# ni tocar un solo script (R1, R2).
#
# La suscripcion NUNCA se escribe en el repositorio (R4): sale de
# $env:AZ_SUBSCRIPTION_ID o del contexto de la sesion iniciada.
#
# Uso:
#     . .\00_vars.ps1                 # entorno por defecto
#     . .\00_vars.ps1 -Entorno pro     # otro entorno
#     $env:DATAMART_ENV = "pro"; . .\00_vars.ps1
#
# PowerShell 5.1.

[CmdletBinding()]
param(
    [string]$Entorno
)

$ErrorActionPreference = "Stop"

# --- 1. Resolucion del entorno: parametro > variable > ultimo recurso --------

if (-not $Entorno) { $Entorno = $env:DATAMART_ENV }
if (-not $Entorno) { $Entorno = "dev" }

$rutaEntornos = Join-Path $PSScriptRoot "env"
$rutaCfg      = Join-Path $rutaEntornos "$Entorno.json"

if (-not (Test-Path $rutaCfg)) {
    $disponibles = (Get-ChildItem $rutaEntornos -Filter "*.json" |
        ForEach-Object { $_.BaseName }) -join ", "
    throw "No existe el fichero de entorno '$rutaCfg'. Disponibles: $disponibles."
}

$CFG = Get-Content -Raw -Encoding UTF8 $rutaCfg | ConvertFrom-Json

# --- 2. Validacion, ANTES de cualquier llamada a la nube (R3) ---------------
#
# Un fichero incompleto que se descubre a mitad del aprovisionamiento deja el
# entorno a medias, y deshacer eso cuesta mucho mas que abortar aqui.

$clavesObligatorias = @(
    "environment", "location",
    "resourceGroup", "logAnalytics", "logRetentionDays", "containerAppsEnv", "job",
    "storageAccount", "auxContainer", "auxBlobs",
    "keyVault", "sigridSecretName", "jobSecretName", "managedIdentity",
    "acrName", "acrResourceGroup", "imageRepository",
    "cron", "jobProgramable", "replicaTimeoutSeconds", "replicaRetryLimit",
    "parallelism", "replicaCompletionCount", "cpu", "memory",
    "sigridApiBaseUrl",
    "pgHost", "pgPort", "pgDatabase", "pgUser", "pgAuthMode",
    "pgSetRole", "pgReadonlyRole", "pgAutoCreateDb", "pgResourceGroup",
    "logLevel", "logFormat",
    "alertName", "alertActionGroupName", "alertActionGroupRg",
    "tags"
)

$tagsObligatorios = @(
    "acens-project", "acens-environment", "acens-customer", "acens-costcenter",
    "acens-compliance", "acens-responsable-iac", "acens-support"
)

$compuestas = @("tags", "auxBlobs")

foreach ($clave in $clavesObligatorias) {
    if (-not ($CFG.PSObject.Properties.Name -contains $clave)) {
        throw "El fichero de entorno '$rutaCfg' no declara la clave obligatoria '$clave'."
    }
    if ($compuestas -contains $clave) { continue }

    $valor = "$($CFG.$clave)"
    if ([string]::IsNullOrWhiteSpace($valor)) {
        throw "El fichero de entorno '$rutaCfg' deja vacia la clave obligatoria '$clave'."
    }
    if ($valor -match "TODO") {
        throw "La clave '$clave' de '$rutaCfg' sigue sin rellenar (contiene TODO): '$valor'."
    }
}

foreach ($clave in $compuestas) {
    foreach ($propiedad in $CFG.$clave.PSObject.Properties) {
        $valor = "$($propiedad.Value)"
        if ([string]::IsNullOrWhiteSpace($valor) -or $valor -match "TODO") {
            throw "El elemento '$($propiedad.Name)' de '$clave' esta vacio o sin rellenar."
        }
    }
}

foreach ($tag in $tagsObligatorios) {
    if (-not ($CFG.tags.PSObject.Properties.Name -contains $tag)) {
        throw "Falta el tag obligatorio de la landing zone '$tag' en '$rutaCfg'."
    }
}

if ($CFG.environment -ne $Entorno) {
    throw "El fichero '$rutaCfg' declara environment='$($CFG.environment)' y se ha pedido '$Entorno'."
}

# --- 3. Suscripcion: del entorno o de la sesion, nunca del repositorio ------

if ($env:AZ_SUBSCRIPTION_ID) {
    $SUB = $env:AZ_SUBSCRIPTION_ID
} else {
    $SUB = (az account show --query id -o tsv)
    if ($LASTEXITCODE -ne 0 -or -not $SUB) {
        throw "No hay sesion de Azure iniciada. Ejecuta 'az login', o define AZ_SUBSCRIPTION_ID."
    }
}

# --- 4. Valores derivados ---------------------------------------------------

# Nombre corto del servidor de Postgres: es la primera etiqueta de su DNS.
$PG_SERVER = $CFG.pgHost.Split(".")[0]

# Identidad de la build. Tag fechado y nunca reescrito: es lo que permite saber
# que imagen corrio una noche concreta (R11).
$TAG        = "r{0}" -f (Get-Date -Format "yyyyMMdd-HHmm")
$IMG        = "{0}.azurecr.io/{1}:{2}" -f $CFG.acrName, $CFG.imageRepository, $TAG
$BUILD_DATE = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

# --- 5. Utilidades compartidas ----------------------------------------------

function Get-EtiquetasCli {
    <#
        Los tags del entorno en la forma que espera 'az ... --tags k=v k=v'.
        Devuelve un array: PowerShell lo expande en argumentos sueltos.
    #>
    $CFG.tags.PSObject.Properties | ForEach-Object { "$($_.Name)=$($_.Value)" }
}

function Confirmar-Exito {
    <#
        Aborta si el ultimo comando externo fallo. Sin esto, un script
        idempotente sigue adelante sobre un recurso que no se creo.
    #>
    param([Parameter(Mandatory = $true)][string]$Mensaje)

    if ($LASTEXITCODE -ne 0) {
        throw "$Mensaje (codigo de salida $LASTEXITCODE)"
    }
}

# --- 6. Resumen (sin secretos) ----------------------------------------------

Write-Host ""
Write-Host "=== Configuracion cargada: $rutaCfg ===" -ForegroundColor Cyan
Write-Host ("  Entorno        : {0} / {1}" -f $CFG.environment, $CFG.location)
Write-Host ("  Resource group : {0}" -f $CFG.resourceGroup)
Write-Host ("  Job            : {0} en {1}" -f $CFG.job, $CFG.containerAppsEnv)
Write-Host ("  Imagen         : {0}" -f $IMG)
Write-Host ("  Postgres       : {0}/{1} como {2} (auth {3})" -f `
    $CFG.pgHost, $CFG.pgDatabase, $CFG.pgUser, $CFG.pgAuthMode)
Write-Host "  Suscripcion    : la del contexto activo (no se escribe en el repositorio)"
Write-Host ""
