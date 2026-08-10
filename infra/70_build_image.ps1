# infra/70_build_image.ps1
#
# Construye la imagen del ETL en el registro de contenedores y la publica con un
# tag fechado (rAAAAMMDD-hhmm). La construccion ocurre EN Azure ('acr build'):
# no hace falta Docker en el puesto.
#
# El tag fechado no es una manía: es lo que permite responder a "que build corrio
# la noche del 12" mirando los logs, y lo que hace que un despliegue nuevo no
# reescriba en silencio la imagen que esta corriendo. Por eso el script se niega
# a publicar sobre un tag que ya existe, y por eso no se usa ninguna etiqueta
# movil.
#
# El tag y la fecha de construccion entran ademas DENTRO de la imagen como
# argumentos de build: 'python main.py version' los devuelve desde el contenedor.

[CmdletBinding()]
param(
    [string]$Entorno
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\00_vars.ps1" -Entorno $Entorno

$contexto  = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$etiqueta  = "{0}:{1}" -f $CFG.imageRepository, $TAG

# --- 1. El tag no puede existir ---------------------------------------------

$publicados = Invoke-Az acr repository show-tags -n $CFG.acrName `
    --repository $CFG.imageRepository -o tsv

if ($LASTEXITCODE -eq 0 -and ($publicados -split "`n") -contains $TAG) {
    throw "el tag '$TAG' ya esta publicado. Espera un minuto: el tag lleva la hora."
}

# --- 2. Construccion --------------------------------------------------------

Write-Host "Construyendo $etiqueta desde $contexto..." -ForegroundColor Cyan
Write-Host "  (la construccion ocurre en Azure; puede tardar varios minutos)"

Invoke-Az acr build `
    -r $CFG.acrName `
    -g $CFG.acrResourceGroup `
    -t $etiqueta `
    --build-arg "IMAGE_TAG=$etiqueta" `
    --build-arg "BUILD_DATE=$BUILD_DATE" `
    $contexto
Confirmar-Exito "la construccion de la imagen ha fallado"

# --- 3. Comprobacion --------------------------------------------------------

Invoke-Az acr repository show-tags -n $CFG.acrName --repository $CFG.imageRepository -o tsv

Write-Host ""
Write-Host "Imagen publicada: $IMG" -ForegroundColor Green
Write-Host "APUNTA ESTE TAG: $TAG" -ForegroundColor Yellow
Write-Host "Es el que hay que ver en los logs del job y en 'python main.py version'."
