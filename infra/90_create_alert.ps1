# infra/90_create_alert.ps1
#
# Crea la alerta que avisa cuando el job nocturno falla. Sin ella, una carga que
# muere a las 02:00 se descubre por la manana cuando alguien mira un informe con
# los datos de anteayer, que es la peor forma de enterarse.
#
# CANAL DE AVISO. Primero se busca un grupo de accion que ya exista -el mismo
# que reciben las alertas de coste y seguridad de la landing zone- y se
# reutiliza. Solo si no existe se crea uno propio, y entonces los destinatarios
# llegan por parametro:
#
#     pwsh -File infra/90_create_alert.ps1 -AlertEmail "quien@ejemplo" "otro@ejemplo"
#
# NINGUNA direccion de correo entra en el repositorio (R26). Si no sabes cual es
# el grupo de la landing zone, lo dice:
#
#     az monitor action-group list --query "[].{n:name, rg:resourceGroup}" -o table
#
# y se lo pasas con -ActionGroupName / -ActionGroupRg.
#
# COMPROBACION PREVIA OBLIGATORIA (seccion 6 del diseno). Antes de la primera
# ejecucion, confirma que la metrica existe para el job en esta region:
#
#     az monitor metrics list-definitions --resource <id-del-job> -o table
#
# Si no apareciera, la alternativa prevista -y la unica admitida- es una regla
# de consulta programada sobre los logs del sistema, en lugar de una alerta de
# metrica:
#
#     az monitor scheduled-query create -g <rg> -n <alerta> \
#       --scopes <id-del-workspace> --condition "count > 0" \
#       --condition-query "ContainerAppSystemLogs_CL | where JobName_s == '<job>' \
#            | where Reason_s in ('JobExecutionFailed','BackoffLimitExceeded')" \
#       --evaluation-frequency 15m --window-size 15m --severity 1 --action-groups <id-ag>
#
# Cualquier tercer camino no se improvisa: se para y se consulta.
#
# IDEMPOTENTE: si la alerta ya existe no se recrea.

[CmdletBinding()]
param(
    [string]$Entorno,
    [string[]]$AlertEmail,
    [string]$ActionGroupName,
    [string]$ActionGroupRg
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\00_vars.ps1" -Entorno $Entorno

$nombreAg = if ($ActionGroupName) { $ActionGroupName } else { $CFG.alertActionGroupName }
$rgAg     = if ($ActionGroupRg)   { $ActionGroupRg }   else { $CFG.alertActionGroupRg }

# --- 1. El job tiene que existir --------------------------------------------

$idJob = az containerapp job show -g $CFG.resourceGroup -n $CFG.job --query id -o tsv 2>$null
if ($LASTEXITCODE -ne 0 -or -not $idJob) {
    throw "el job '$($CFG.job)' no existe todavia: no hay nada que vigilar. Ejecuta antes 80_create_job.ps1."
}

# --- 2. El canal de aviso ---------------------------------------------------

$idAg = az monitor action-group show -g $rgAg -n $nombreAg --query id -o tsv 2>$null

if ($LASTEXITCODE -eq 0 -and $idAg) {
    Write-Host "Reutilizando el grupo de accion '$nombreAg' de '$rgAg'." -ForegroundColor Green
} elseif ($AlertEmail) {
    Write-Host "Creando el grupo de accion '$nombreAg' con $($AlertEmail.Count) destinatario(s)..." -ForegroundColor Cyan

    $receptores = @()
    $indice = 0
    foreach ($correo in $AlertEmail) {
        $indice++
        $receptores += "email"
        $receptores += "aviso$indice"
        $receptores += $correo
    }

    $corto = "dm" + $CFG.environment
    if ($corto.Length -gt 12) { $corto = $corto.Substring(0, 12) }

    az monitor action-group create -g $rgAg -n $nombreAg --short-name $corto `
        --action $receptores -o none
    Confirmar-Exito "no se ha podido crear el grupo de accion"

    $idAg = az monitor action-group show -g $rgAg -n $nombreAg --query id -o tsv
    Confirmar-Exito "el grupo de accion no responde despues de crearlo"
} else {
    throw ("no existe el grupo de accion '$nombreAg' en '$rgAg' y no se han dado " +
           "destinatarios. Localiza el de la landing zone con 'az monitor action-group " +
           "list' y pasalo con -ActionGroupName / -ActionGroupRg, o crea uno propio con " +
           "-AlertEmail. Los correos no se escriben en el repositorio.")
}

# --- 3. La alerta -----------------------------------------------------------

$yaExiste = az monitor metrics alert show -g $CFG.resourceGroup -n $CFG.alertName `
    --query id -o tsv 2>$null

if ($LASTEXITCODE -eq 0 -and $yaExiste) {
    Write-Host "La alerta '$($CFG.alertName)' ya existe; no se recrea." -ForegroundColor Yellow
} else {
    # Alerta de METRICA y no de consulta de log: no depende de que el esquema de
    # las tablas de logs cambie, y avisa en minutos en vez de en cuartos de hora.
    $condicion = "total JobExecutionCount > 0 where Status includes Failed"

    Write-Host "Creando la alerta '$($CFG.alertName)'..." -ForegroundColor Cyan
    az monitor metrics alert create `
        -g $CFG.resourceGroup -n $CFG.alertName `
        --scopes $idJob `
        --condition $condicion `
        --window-size 5m --evaluation-frequency 5m `
        --severity 1 `
        --action $idAg `
        --description "El job nocturno del datamart ha terminado en fallo" `
        --tags @(Get-EtiquetasCli) -o none
    Confirmar-Exito "no se ha podido crear la alerta"
}

az monitor metrics alert show -g $CFG.resourceGroup -n $CFG.alertName `
    --query "{nombre:name, activa:enabled, severidad:severity, ambito:scopes[0]}" -o table

Write-Host ""
Write-Host "Alerta lista." -ForegroundColor Green
Write-Host "NO esta verificada hasta que llegue un correo de verdad." -ForegroundColor Yellow
Write-Host "La prueba, de extremo a extremo, esta en infra/README.md (R25): forzar una"
Write-Host "ejecucion fallida y anotar la hora del fallo y la de recepcion."
