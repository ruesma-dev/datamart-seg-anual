# infra/20_build_image.ps1
# Construye y publica la imagen con tag fechado (nunca reescribir tags).
. "$PSScriptRoot\00_vars.ps1"

az account set --subscription $SUB

# Sella la imagen con su identidad: `python main.py version` la devuelve luego
# desde el contenedor, que es como se sabe que build esta corriendo en Azure.
$BUILD_DATE = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

az acr build -r $ACR -g $RG -t "${IMG_NAME}:${TAG}" `
  --build-arg "IMAGE_TAG=${IMG_NAME}:${TAG}" `
  --build-arg "BUILD_DATE=${BUILD_DATE}" `
  "$PSScriptRoot\.."
Write-Host "Imagen publicada: ${IMG}"
Write-Host "Apunta este tag para 30_create_job.ps1 / 40_update_job.ps1"
