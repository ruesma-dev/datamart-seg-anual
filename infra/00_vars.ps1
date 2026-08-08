# infra/00_vars.ps1
# Única fuente de verdad de nombres/recursos del despliegue del datamart.
# PowerShell 5.1. Ejecutar con: . .\00_vars.ps1

$SUB        = "863dfedd-d208-467f-9e8b-415e9cb59c5d"
$LOC        = "spaincentral"
$RG         = "rg-seguimiento-dev"

$ACR        = "TODO_acr_existente"          # p.ej. el ACR compartido de albaranes
$IMG_NAME   = "datamart-seg-anual"
$TAG        = "r{0}" -f (Get-Date -Format "yyyyMMdd-HHmm")
$IMG        = "${ACR}.azurecr.io/${IMG_NAME}:${TAG}"

$CAE        = "cae-seguimiento-dev"         # Container Apps environment
$JOB        = "caj-datamart-seg"            # Container Apps Job
$CRON       = "0 3 * * *"                   # nocturno 03:00 UTC

# Postgres destino (el flexible server del datamart)
$PG_HOST    = "TODO_pg_flexible_server.postgres.database.azure.com"

Write-Host "Vars cargadas. IMG=${IMG} RG=${RG}"
