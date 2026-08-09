# infra/85_update_job.ps1
#
# Despliegue habitual: apunta el job que ya existe a una imagen nueva. No toca
# la programacion, ni la identidad, ni los secretos, ni las variables de
# entorno: cambiar cualquiera de esas cosas es volver a 80_create_job.ps1 con
# el fichero de entorno modificado.
#
# Tampoco sobrescribe el punto de entrada de la imagen: el alcance de la carga
# nocturna vive en el Dockerfile, en un solo sitio (R8).
#
# Uso habitual, despues de 70_build_image.ps1:
#
#     pwsh -File infra/85_update_job.ps1                 # la ultima publicada
#     pwsh -File infra/85_update_job.ps1 -Tag r20260810-0200

[CmdletBinding()]
param(
    [string]$Entorno,
    [string]$Tag
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\00_vars.ps1" -Entorno $Entorno

$existente = az containerapp job show -g $CFG.resourceGroup -n $CFG.job --query id -o tsv 2>$null
if ($LASTEXITCODE -ne 0 -or -not $existente) {
    throw "el job '$($CFG.job)' no existe todavia. Crealo con 80_create_job.ps1."
}

if (-not $Tag) {
    $Tag = az acr repository show-tags -n $CFG.acrName --repository $CFG.imageRepository `
        --orderby time_desc --top 1 -o tsv
    Confirmar-Exito "no hay ninguna imagen publicada: ejecuta antes 70_build_image.ps1"
}
$imagen = "{0}.azurecr.io/{1}:{2}" -f $CFG.acrName, $CFG.imageRepository, $Tag

$anterior = az containerapp job show -g $CFG.resourceGroup -n $CFG.job `
    --query "properties.template.containers[0].image" -o tsv

Write-Host "Imagen actual : $anterior"
Write-Host "Imagen nueva  : $imagen" -ForegroundColor Cyan

if ($anterior -eq $imagen) {
    Write-Host "Ya esta en esa imagen; no hay nada que hacer." -ForegroundColor Yellow
    exit 0
}

az containerapp job update -g $CFG.resourceGroup -n $CFG.job --image $imagen -o none
Confirmar-Exito "no se ha podido actualizar el job"

az containerapp job show -g $CFG.resourceGroup -n $CFG.job `
    --query "{imagen:properties.template.containers[0].image, disparo:properties.configuration.triggerType}" `
    -o table

Write-Host ""
Write-Host "Job actualizado. La ejecucion programada usara la imagen nueva." -ForegroundColor Green
Write-Host "Prueba manual: az containerapp job start -g $($CFG.resourceGroup) -n $($CFG.job)"
