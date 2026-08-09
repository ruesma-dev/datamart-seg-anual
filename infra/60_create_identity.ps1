# infra/60_create_identity.ps1
#
# Crea la identidad gestionada del job y le da EXACTAMENTE tres permisos, cada
# uno sobre un recurso concreto y ninguno sobre la suscripcion entera.
#
#   AcrPull                    -> el registro de contenedores (bajar la imagen)
#   Key Vault Secrets User     -> el vault del proyecto (leer la clave de la API)
#   Storage Blob Data Reader   -> la cuenta del proyecto (leer los Excels)
#
# Identidad asignada por el USUARIO y no por el sistema, por dos razones:
#
#   1. Huevo y gallina: la identidad del sistema no existe hasta que existe el
#      job, pero el job no arranca si no puede bajar la imagen, y para eso
#      necesita AcrPull ya asignado.
#   2. Sobrevive al job: recrear el job no destruye ni estos permisos ni el rol
#      que la base de datos tenga concedido a esta identidad.
#
# IDEMPOTENTE: se puede repetir; las asignaciones que ya existan se dejan estar.

[CmdletBinding()]
param(
    [string]$Entorno
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\00_vars.ps1" -Entorno $Entorno

$etiquetas = @(Get-EtiquetasCli)

# --- 1. La identidad --------------------------------------------------------

$existente = Invoke-Az identity show -g $CFG.resourceGroup -n $CFG.managedIdentity --query id -o tsv

if ($LASTEXITCODE -eq 0 -and $existente) {
    Write-Host "La identidad '$($CFG.managedIdentity)' ya existe; no se recrea." -ForegroundColor Yellow
} else {
    Write-Host "Creando la identidad '$($CFG.managedIdentity)'..." -ForegroundColor Cyan
    Invoke-Az identity create -g $CFG.resourceGroup -n $CFG.managedIdentity -l $CFG.location `
        --tags $etiquetas -o none
    Confirmar-Exito "no se ha podido crear la identidad gestionada"
}

$identidad = Invoke-Az identity show -g $CFG.resourceGroup -n $CFG.managedIdentity `
    --query "{id:id, principalId:principalId, clientId:clientId}" -o json
Confirmar-Exito "no se ha podido leer la identidad recien creada"
$uami = $identidad | ConvertFrom-Json

# La identidad tarda unos segundos en existir para el directorio. Sin esta
# espera, las asignaciones de rol fallan con 'PrincipalNotFound' de forma
# intermitente, que es la peor manera de fallar.
$intento = 0
while ($intento -lt 12) {
    Invoke-Az ad sp show --id $uami.principalId --query id -o tsv | Out-Null
    if ($LASTEXITCODE -eq 0) { break }
    $intento++
    Write-Host "  esperando a que el directorio publique la identidad ($intento)..."
    Start-Sleep -Seconds 5
}

# --- 2. Los ambitos: se preguntan, no se escriben ---------------------------

$idAcr = Invoke-Az acr show -n $CFG.acrName -g $CFG.acrResourceGroup --query id -o tsv
Confirmar-Exito "no se encuentra el registro de contenedores"

$idVault = Invoke-Az keyvault show -g $CFG.resourceGroup -n $CFG.keyVault --query id -o tsv
Confirmar-Exito "no se encuentra el Key Vault: ejecuta antes 50_create_keyvault.ps1"

$idCuenta = Invoke-Az storage account show -g $CFG.resourceGroup -n $CFG.storageAccount --query id -o tsv
Confirmar-Exito "no se encuentra la cuenta de almacenamiento: ejecuta antes 40_create_storage.ps1"

# --- 3. Las tres asignaciones -----------------------------------------------
#
# Escritas una a una a proposito: son el permiso real del job y tienen que poder
# leerse y auditarse de un vistazo. Un error aqui se llama exceso de privilegio.

Write-Host "Asignando permisos..." -ForegroundColor Cyan

Invoke-Az role assignment create --role "AcrPull" `
    --assignee-object-id $uami.principalId --assignee-principal-type ServicePrincipal `
    --scope $idAcr -o none

Invoke-Az role assignment create --role "Key Vault Secrets User" `
    --assignee-object-id $uami.principalId --assignee-principal-type ServicePrincipal `
    --scope $idVault -o none

Invoke-Az role assignment create --role "Storage Blob Data Reader" `
    --assignee-object-id $uami.principalId --assignee-principal-type ServicePrincipal `
    --scope $idCuenta -o none

# --- 4. Verificacion --------------------------------------------------------
#
# No basta con que los comandos no hayan protestado: se comprueba el resultado.
# Repetir el script no debe fallar por asignaciones que ya existian.

$asignados = Invoke-Az role assignment list --assignee $uami.principalId --all `
    --query "[].roleDefinitionName" -o tsv
Confirmar-Exito "no se han podido listar las asignaciones de rol"

$esperados = @("AcrPull", "Key Vault Secrets User", "Storage Blob Data Reader")
$faltan = $esperados | Where-Object { $asignados -notcontains $_ }

Invoke-Az role assignment list --assignee $uami.principalId --all `
    --query "[].{rol:roleDefinitionName, ambito:scope}" -o table

if ($faltan) {
    throw "faltan permisos por asignar: $($faltan -join ', ')"
}

$sobran = $asignados | Where-Object { $esperados -notcontains $_ }
if ($sobran) {
    Write-Host "AVISO: la identidad tiene mas permisos de los tres previstos: $($sobran -join ', ')" -ForegroundColor Yellow
    Write-Host "Revisalo: R19 exige exactamente tres y ninguno mas." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Identidad lista." -ForegroundColor Green
Write-Host "  clientId    = $($uami.clientId)"
Write-Host "  principalId = $($uami.principalId)"
Write-Host "El clientId es el que 80_create_job.ps1 inyecta como AZURE_CLIENT_ID."
