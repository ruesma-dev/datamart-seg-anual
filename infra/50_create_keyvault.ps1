# infra/50_create_keyvault.ps1
#
# Crea el Key Vault del proyecto, donde vive el UNICO secreto del job: la clave
# de la API de Sigrid.
#
# Con autorizacion RBAC y no con politicas de acceso: es lo que permite dar a la
# identidad gestionada un permiso de lectura acotado a los secretos, y es el
# modelo que Azure recomienda desde hace anos.
#
# ESTE SCRIPT NO CARGA NINGUN VALOR. Meter el secreto es tarea del humano (T20)
# y necesita un rol que crear el vault NO concede; el comando exacto esta en
# infra/README.md. Aqui no se lee ni se imprime jamas el valor de un secreto.
#
# Proteccion contra purga: deshabilitada en los entornos que no son productivos.
# Con ella activada, un vault mal nombrado no se puede purgar y su nombre queda
# quemado durante dias. El borrado logico si queda activo, que viene de serie.
#
# IDEMPOTENTE: si el vault ya existe no se recrea.

[CmdletBinding()]
param(
    [string]$Entorno
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\00_vars.ps1" -Entorno $Entorno

$etiquetas = @(Get-EtiquetasCli)

$existente = Invoke-Az keyvault show -g $CFG.resourceGroup -n $CFG.keyVault --query id -o tsv

if ($LASTEXITCODE -eq 0 -and $existente) {
    Write-Host "El vault '$($CFG.keyVault)' ya existe; no se recrea." -ForegroundColor Yellow
} else {
    Write-Host "Creando el vault '$($CFG.keyVault)'..." -ForegroundColor Cyan
    Invoke-Az keyvault create `
        -g $CFG.resourceGroup -n $CFG.keyVault -l $CFG.location `
        --enable-rbac-authorization true `
        --retention-days 7 `
        --tags $etiquetas -o none
    Confirmar-Exito "no se ha podido crear el Key Vault"
}

Invoke-Az keyvault show -g $CFG.resourceGroup -n $CFG.keyVault `
    --query "{nombre:name, rbac:properties.enableRbacAuthorization, borradoLogico:properties.enableSoftDelete}" `
    -o table
Confirmar-Exito "el vault no responde despues de crearlo"

Write-Host ""
Write-Host "Vault listo, y VACIO." -ForegroundColor Green
Write-Host "Siguiente paso, del humano (T20): meter la clave de la API de Sigrid con" -ForegroundColor Yellow
Write-Host "el nombre '$($CFG.sigridSecretName)', tomando el valor de un fichero y" -ForegroundColor Yellow
Write-Host "nunca de la linea de comandos. El procedimiento esta en infra/README.md." -ForegroundColor Yellow
