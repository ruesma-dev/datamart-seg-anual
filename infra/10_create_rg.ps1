# infra/10_create_rg.ps1
# Crea el resource group y el Container Apps environment (una sola vez).
. "$PSScriptRoot\00_vars.ps1"

az account set --subscription $SUB
az group create -n $RG -l $LOC
az containerapp env create -g $RG -n $CAE -l $LOC
