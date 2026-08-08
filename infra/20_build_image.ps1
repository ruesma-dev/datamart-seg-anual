# infra/20_build_image.ps1
# Construye y publica la imagen con tag fechado (nunca reescribir tags).
. "$PSScriptRoot\00_vars.ps1"

az account set --subscription $SUB
az acr build -r $ACR -g $RG -t "${IMG_NAME}:${TAG}" "$PSScriptRoot\.."
Write-Host "Imagen publicada: ${IMG}"
Write-Host "Apunta este tag para 30_create_job.ps1 / 40_update_job.ps1"
