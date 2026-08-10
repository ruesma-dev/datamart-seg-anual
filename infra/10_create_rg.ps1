# infra/10_create_rg.ps1
#
# Crea el resource group del datamart con los tags de la landing zone.
#
# IDEMPOTENTE: si el grupo ya existe, se limita a reaplicar los tags. Los tags
# no son decoracion: una politica de la suscripcion los exige y son lo que
# permite imputar el coste al proyecto correcto (seccion 3.6 de la landing zone).

[CmdletBinding()]
param(
    [string]$Entorno
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\00_vars.ps1" -Entorno $Entorno

$etiquetas = @(Get-EtiquetasCli)

Write-Host "Creando el resource group '$($CFG.resourceGroup)' en $($CFG.location)..." -ForegroundColor Cyan

Invoke-Az group create --name $CFG.resourceGroup --location $CFG.location --tags $etiquetas -o none
Confirmar-Exito "no se ha podido crear el resource group '$($CFG.resourceGroup)'"

Invoke-Az group show --name $CFG.resourceGroup --query "{nombre:name, region:location, tags:tags}" -o json
Confirmar-Exito "el resource group no responde despues de crearlo"

Write-Host "Resource group listo." -ForegroundColor Green
