# infra/30_create_env.ps1
#
# Crea el entorno de Container Apps donde correra el job, con los logs dirigidos
# al workspace de 20_create_observability.ps1.
#
# SIN INTEGRACION DE RED VIRTUAL, y es una decision, no un olvido (seccion 2 del
# diseno): los dos entornos que ya existen en la suscripcion tampoco la usan; no
# hay ni un private endpoint al que acercarse; y un entorno externo tiene IP
# publica de salida ESTATICA, que es justo lo que hace falta para autorizar al
# job en el firewall del servidor de Postgres (R23).
#
# IDEMPOTENTE: si el entorno ya existe no se recrea.

[CmdletBinding()]
param(
    [string]$Entorno
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\00_vars.ps1" -Entorno $Entorno

$etiquetas = @(Get-EtiquetasCli)

$existente = az containerapp env show -g $CFG.resourceGroup -n $CFG.containerAppsEnv `
    --query id -o tsv 2>$null

if ($LASTEXITCODE -eq 0 -and $existente) {
    Write-Host "El entorno '$($CFG.containerAppsEnv)' ya existe; no se recrea." -ForegroundColor Yellow
} else {
    $customerId = az monitor log-analytics workspace show `
        -g $CFG.resourceGroup -n $CFG.logAnalytics --query customerId -o tsv
    Confirmar-Exito "no se encuentra el workspace: ejecuta antes 20_create_observability.ps1"

    # La clave del workspace vive solo en esta variable y durante esta ejecucion:
    # no se imprime, no se guarda y no entra en el repositorio.
    $claveWorkspace = az monitor log-analytics workspace get-shared-keys `
        -g $CFG.resourceGroup -n $CFG.logAnalytics --query primarySharedKey -o tsv
    Confirmar-Exito "no se ha podido leer la clave del workspace"

    Write-Host "Creando el entorno '$($CFG.containerAppsEnv)'..." -ForegroundColor Cyan
    az containerapp env create `
        -g $CFG.resourceGroup -n $CFG.containerAppsEnv -l $CFG.location `
        --logs-destination log-analytics `
        --logs-workspace-id $customerId `
        --logs-workspace-key $claveWorkspace `
        --tags $etiquetas -o none
    $claveWorkspace = $null
    Confirmar-Exito "no se ha podido crear el entorno de Container Apps"
}

# --- La IP de salida: entrada de la regla de firewall de R23 ----------------

$ip = az containerapp env show -g $CFG.resourceGroup -n $CFG.containerAppsEnv `
    --query properties.staticIp -o tsv
Confirmar-Exito "el entorno no responde despues de crearlo"

az containerapp env show -g $CFG.resourceGroup -n $CFG.containerAppsEnv `
    --query "{nombre:name, estado:properties.provisioningState, vnet:properties.vnetConfiguration, logs:properties.appLogsConfiguration.destination}" `
    -o json

Write-Host ""
Write-Host "Entorno listo. IP de salida = $ip" -ForegroundColor Green
Write-Host "APUNTALA: es la que hay que autorizar en el firewall del servidor de" -ForegroundColor Yellow
Write-Host "Postgres (tarea T22 / requisito R23), y esa escritura es sobre un recurso" -ForegroundColor Yellow
Write-Host "de OTRO proyecto: necesita autorizacion expresa del humano." -ForegroundColor Yellow
