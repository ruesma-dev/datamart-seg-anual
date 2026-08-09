# infra/20_create_observability.ps1
#
# Crea el workspace de Log Analytics propio del datamart, destino de los logs
# del entorno de Container Apps (R16) y de la consulta de R24.
#
# IDEMPOTENTE: si el workspace ya existe no se recrea; se muestran sus datos.
#
# Workspace propio y no el central de la landing zone a proposito: los logs de
# una carga completa son ruidosos, y mezclarlos con los de gestion complica las
# consultas y reparte el coste donde no toca.

[CmdletBinding()]
param(
    [string]$Entorno
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\00_vars.ps1" -Entorno $Entorno

$etiquetas = @(Get-EtiquetasCli)

$existente = az monitor log-analytics workspace show `
    -g $CFG.resourceGroup -n $CFG.logAnalytics --query id -o tsv 2>$null

if ($LASTEXITCODE -eq 0 -and $existente) {
    Write-Host "El workspace '$($CFG.logAnalytics)' ya existe; no se recrea." -ForegroundColor Yellow
} else {
    Write-Host "Creando el workspace '$($CFG.logAnalytics)'..." -ForegroundColor Cyan
    az monitor log-analytics workspace create `
        -g $CFG.resourceGroup -n $CFG.logAnalytics -l $CFG.location `
        --retention-time $CFG.logRetentionDays `
        --tags $etiquetas -o none
    Confirmar-Exito "no se ha podido crear el workspace de Log Analytics"
}

# El identificador que necesita el entorno de Container Apps NO es el resource
# id, sino el customerId del workspace. Confundirlos es el error clasico aqui.
$customerId = az monitor log-analytics workspace show `
    -g $CFG.resourceGroup -n $CFG.logAnalytics --query customerId -o tsv
Confirmar-Exito "no se ha podido leer el identificador del workspace"

az monitor log-analytics workspace show -g $CFG.resourceGroup -n $CFG.logAnalytics `
    --query "{nombre:name, sku:sku.name, retencionDias:retentionInDays}" -o table

Write-Host ""
Write-Host "Workspace listo. customerId = $customerId" -ForegroundColor Green
Write-Host "Lo usa 30_create_env.ps1 (lo vuelve a consultar solo, no hay que copiarlo)."
