# infra/30_create_job.ps1
# Crea el Container Apps Job programado (primera vez).
# Secretos: pasarlos aqui via Key Vault o --secrets; el .env NO se despliega.
. "$PSScriptRoot\00_vars.ps1"

az account set --subscription $SUB
az containerapp job create `
  -g $RG -n $JOB --environment $CAE `
  --trigger-type Schedule --cron-expression $CRON `
  --replica-timeout 7200 --replica-retry-limit 1 `
  --image $IMG `
  --registry-server "${ACR}.azurecr.io" `
  --cpu 1.0 --memory 2.0Gi `
  --secrets "pg-password=TODO" "sigrid-key=TODO" `
  --env-vars `
    "PG_HOST=${PG_HOST}" `
    "PG_PASSWORD=secretref:pg-password" `
    "SIGRID_API_FUNCTION_KEY=secretref:sigrid-key" `
    "SIGRID_API_BASE_URL=https://func-sigridapi-dev-huyke.azurewebsites.net"
