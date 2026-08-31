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
    "pgSecretName", "pgJobSecretName", "pgReadonlySecretName",
    "pgHost", "pgPort", "pgDatabase", "pgUser", "pgAuthMode",
    "pgSetRole", "pgReadonlyRole", "pgAutoCreateDb", "pgResourceGroup",
    "logLevel", "logFormat",
    "alertName", "alertActionGroupName", "alertActionGroupRg",
    "frescuraAlertName", "frescuraUmbralHoras",
    "coberturaAlertName", "coberturaVentanaHoras",
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

# --- 2 bis. Como se llama a 'az' (leer antes de tocar cualquier script) -----

$global:AzUltimoError = ""

function Invoke-Az {
    <#
        UNICO punto de entrada a la CLI de Azure en todo infra/. Nadie llama a
        'az' a pelo, y hay un test que lo comprueba.

        El puesto donde se ejecuta esto NO tiene pwsh: corre Windows PowerShell
        5.1 con 'powershell -NoProfile -File'. Ahi hay tres trampas que cuestan
        un despliegue a medias, y las tres se resuelven aqui:

          1. Con $ErrorActionPreference = "Stop", el stderr de un ejecutable
             nativo se envuelve en un ErrorRecord (NativeCommandError) que es
             TERMINANTE. Y az escribe por stderr algo tan normal como
             'ResourceNotFound', que es la respuesta esperada de toda
             comprobacion "existe ya?" en un primer despliegue. Resultado: el
             script moria justo antes de crear el recurso que faltaba. Le paso
             a 20_create_observability.ps1 el 2026-08-10. Por eso aqui se baja
             la preferencia a "Continue" durante la llamada, y se restaura en
             un finally: si no, un fallo la dejaria bajada para el resto.
          2. 'az' es un .cmd, asi que cmd.exe vuelve a parsear la linea ya
             expandida. Los parentesis, '?', '|' y '!' de una expresion JMESPath
             la rompen ("No se esperaba -o en este momento") cuando PowerShell
             no la entrecomilla, que es siempre que no lleva espacios. Por eso
             ninguna consulta --query de infra/ lleva esos caracteres: lo que
             haya que filtrar o agregar se hace en PowerShell sobre el JSON.
          3. Los avisos de az (actualizacion disponible, comandos en preview)
             se cuelan en la salida capturada y confunden un diagnostico:
             --only-show-errors los calla.

        Devuelve la SALIDA ESTANDAR como cadena. El codigo de salida se
        consulta como siempre, en $LASTEXITCODE, y el texto del error de az
        queda en $AzUltimoError. No lanza: decide quien llama.

        Se usa exactamente igual que az, sin el 'az':

            $id = Invoke-Az group show -n $CFG.resourceGroup --query id -o tsv
            if ($LASTEXITCODE -ne 0) { ... }
    #>
    $anterior = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $salida = & az @args --only-show-errors 2>&1
    } finally {
        $ErrorActionPreference = $anterior
    }

    $errores = @($salida |
        Where-Object { $_ -is [System.Management.Automation.ErrorRecord] })
    $normal = @($salida |
        Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] })

    $global:AzUltimoError = ($errores -join " ").Trim()

    ($normal -join "`n")
}

# --- 3. Suscripcion: del entorno o de la sesion, nunca del repositorio ------

if ($env:AZ_SUBSCRIPTION_ID) {
    $SUB = $env:AZ_SUBSCRIPTION_ID
} else {
    $SUB = (Invoke-Az account show --query id -o tsv)
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
        $detalle = if ($AzUltimoError) { " -> $AzUltimoError" } else { "" }
        throw "$Mensaje (codigo de salida $LASTEXITCODE)$detalle"
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
