# infra/40_create_storage.ps1
#
# Crea la cuenta de almacenamiento del proyecto y el contenedor donde Negocio
# deja los Excels auxiliares que lee el ETL (F-004).
#
# La cuenta nace endurecida y eso tiene consecuencias que hay que conocer:
#
#   --allow-blob-public-access false : ningun blob se sirve sin autenticar.
#   --allow-shared-key-access false  : NADIE entra con la clave de la cuenta,
#                                      ni las herramientas graficas. Todo el
#                                      acceso es con identidad (Entra) y rol de
#                                      plano de datos. Es deliberado, y es lo
#                                      que F-010 tendra que tener en cuenta.
#   --min-tls-version TLS1_2         : lo que exige la landing zone.
#
# IDEMPOTENTE: si la cuenta o el contenedor existen, no se recrean.

[CmdletBinding()]
param(
    [string]$Entorno
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\00_vars.ps1" -Entorno $Entorno

$etiquetas = @(Get-EtiquetasCli)

# --- 1. La cuenta -----------------------------------------------------------

$existente = az storage account show -g $CFG.resourceGroup -n $CFG.storageAccount `
    --query id -o tsv 2>$null

if ($LASTEXITCODE -eq 0 -and $existente) {
    Write-Host "La cuenta '$($CFG.storageAccount)' ya existe; no se recrea." -ForegroundColor Yellow
} else {
    Write-Host "Creando la cuenta '$($CFG.storageAccount)'..." -ForegroundColor Cyan
    az storage account create `
        -g $CFG.resourceGroup -n $CFG.storageAccount -l $CFG.location `
        --sku Standard_LRS --kind StorageV2 `
        --https-only true `
        --min-tls-version TLS1_2 `
        --allow-blob-public-access false `
        --allow-shared-key-access false `
        --tags $etiquetas -o none
    Confirmar-Exito "no se ha podido crear la cuenta de almacenamiento"
}

# --- 2. El contenedor de los Excels auxiliares ------------------------------
#
# Con la clave compartida deshabilitada, este paso se autentica con la sesion de
# 'az' y exige un rol de PLANO DE DATOS sobre la cuenta. Tener Owner sobre la
# suscripcion no basta: son planos distintos, y esa es la sorpresa clasica.

Write-Host "Creando el contenedor de los Excels auxiliares..." -ForegroundColor Cyan
az storage container create `
    --account-name $CFG.storageAccount `
    --name $CFG.auxContainer `
    --auth-mode login `
    --public-access off -o none

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "No se ha podido crear el contenedor." -ForegroundColor Red
    Write-Host "Casi siempre es falta de rol en el plano de datos. Asignatelo y repite:" -ForegroundColor Yellow
    Write-Host "  az role assignment create --role 'Storage Blob Data Contributor' \" -ForegroundColor Yellow
    Write-Host "    --assignee <tu-objectId> --scope <id-de-la-cuenta>" -ForegroundColor Yellow
    Write-Host "La propagacion tarda un par de minutos." -ForegroundColor Yellow
    throw "creacion del contenedor fallida"
}

# --- 3. Comprobacion --------------------------------------------------------

az storage account show -g $CFG.resourceGroup -n $CFG.storageAccount `
    --query "{publico:allowBlobPublicAccess, clave:allowSharedKeyAccess, tls:minimumTlsVersion}" `
    -o table

az storage container list --account-name $CFG.storageAccount --auth-mode login `
    --query "[].name" -o tsv

Write-Host ""
Write-Host "Almacenamiento listo." -ForegroundColor Green
Write-Host "Los Excels los sube una persona (F-010), no el job: el job solo lee."
