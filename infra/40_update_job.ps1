# infra/40_update_job.ps1
# Actualiza el job a una nueva imagen (despliegue habitual).
. "$PSScriptRoot\00_vars.ps1"

az account set --subscription $SUB
az containerapp job update -g $RG -n $JOB --image $IMG
Write-Host "Job ${JOB} actualizado a ${IMG}"
Write-Host "Ejecucion manual de prueba: az containerapp job start -g ${RG} -n ${JOB}"
