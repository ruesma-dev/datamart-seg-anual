# infra/95_create_alert_frescura.ps1
#
# Crea la alerta de FRESCURA del datamart (F-024): avisa cuando pasan mas de N
# horas sin que el job haya completado un build_mart.
#
# POR QUE HACE FALTA SI YA EXISTE 90_create_alert.ps1. Esa alerta se dispara
# cuando una ejecucion TERMINA EN FALLO. Esta cubre el otro agujero, el que
# nadie estaba vigilando: que el job NO LLEGUE A HACER su trabajo sin que nadie
# lo declare fallo -no arranco, se quedo colgado, alguien lo deshabilito, la
# programacion se perdio en un despliegue-. Vigila desde FUERA del ETL, asi que
# "el job no lo hizo" dispara igual que "el job murio".
#
# COMO FUNCIONA. Regla de consulta programada (KQL) sobre el workspace de Log
# Analytics: cuenta las lineas de consola del job que digan a la vez
# 'step_finished', 'build_mart' y 'SUCCESS' dentro de la ventana, y dispara si
# hay CERO. Se vigila la AUSENCIA porque es la senal: una regla que buscara "el
# ultimo evento" no disparia nunca cuando no hay ningun evento, que es
# exactamente el caso a detectar.
#
# Los tres terminos son los que emite el orquestador al cerrar cada paso. Hay un
# test (tests/test_f024_infra_alerta.py) que fija los DOS extremos a la vez: si
# alguien renombra el evento, se rompe la suite en vez de romperse la alerta en
# silencio a las 02:00 de un martes.
#
# PASO PREVIO OBLIGATORIO, una sola vez por puesto (no es del repositorio, es
# de la maquina; esta anotado tambien en infra/README.md):
#
#     az extension add --name scheduled-query
#
# LO QUE ESTA CONFIRMADO Y NO SE IMPROVISA (T3 de F-024, 2026-08-18):
#   - la sintaxis es --condition "count 'Nombre' < 1" mas --condition-query
#     Nombre="<kql>", comprobada con --help;
#   - las ventanas van en formato ##h##m##s ("30h"), NO en ISO 8601: un PT30H
#     se rechaza;
#   - la columna del nombre del job en ContainerAppConsoleLogs_CL es
#     ContainerJobName_s, verificada con | getschema. ContainerAppName_s -la que
#     decia el README- NO existe para un job: filtrar por ella devolveria
#     siempre cero filas y la alerta disparia todas las noches.
#
# FALSO POSITIVO ASUMIDO: la regla mide LOGS, no la base de datos. Si el humano
# reconstruye mart desde su puesto, la regla no lo ve y avisa igual. Es
# coherente con lo que vigila, que es "el job hizo su trabajo".
#
# NINGUNA direccion de correo entra aqui (R26 de F-003): los destinatarios
# viven en el grupo de accion, que crea o localiza 90_create_alert.ps1.
#
# IDEMPOTENTE: si la regla ya existe no se recrea.

[CmdletBinding()]
param(
    [string]$Entorno
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\00_vars.ps1" -Entorno $Entorno

# --- 1. La extension de az, sin la cual no existe el comando ----------------

Invoke-Az extension show --name scheduled-query --query name -o tsv | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw ("falta la extension 'scheduled-query' de az en este puesto. " +
           "Instalala una vez con: az extension add --name scheduled-query")
}

# --- 2. El workspace de Log Analytics, que es el ambito de la regla ---------

$idWorkspace = Invoke-Az monitor log-analytics workspace show `
    -g $CFG.resourceGroup -n $CFG.logAnalytics --query id -o tsv
if ($LASTEXITCODE -ne 0 -or -not $idWorkspace) {
    throw ("no existe el workspace '$($CFG.logAnalytics)': sin el no hay logs " +
           "que consultar. Ejecuta antes 20_create_observability.ps1.")
}

# --- 3. El canal de aviso: el mismo que usa la alerta de fallo --------------

$idAg = Invoke-Az monitor action-group show `
    -g $CFG.alertActionGroupRg -n $CFG.alertActionGroupName --query id -o tsv
if ($LASTEXITCODE -ne 0 -or -not $idAg) {
    throw ("no existe el grupo de accion '$($CFG.alertActionGroupName)' en " +
           "'$($CFG.alertActionGroupRg)'. Lo crea o lo localiza " +
           "90_create_alert.ps1, que es donde se pasan los destinatarios; aqui " +
           "no se escribe ningun correo.")
}

# --- 4. La regla ------------------------------------------------------------

$horas = [int]$CFG.frescuraUmbralHoras

# Formato ##h##m##s, no ISO 8601. Y derivado del umbral, nunca escrito a mano:
# el mismo numero decide la ventana de esta alerta y el default de
# `python main.py check-frescura`, y si divergen la alerta vigila una cosa y el
# comando juzga otra.
$ventana = "{0}h" -f $horas

# La consulta viaja en una variable: al llevar espacios, PowerShell la
# entrecomilla al invocar az.cmd, y asi los parentesis y las barras verticales
# del KQL no los vuelve a interpretar cmd.exe.
$kql = ("ContainerAppConsoleLogs_CL " +
        "| where ContainerJobName_s == '$($CFG.job)' " +
        "| where Log_s has_all ('step_finished','build_mart','SUCCESS')")
$consulta = "Frescura=$kql"

$yaExiste = Invoke-Az monitor scheduled-query show `
    -g $CFG.resourceGroup -n $CFG.frescuraAlertName --query id -o tsv

if ($LASTEXITCODE -eq 0 -and $yaExiste) {
    Write-Host "La alerta '$($CFG.frescuraAlertName)' ya existe; no se recrea." -ForegroundColor Yellow
} else {
    Write-Host "Creando la alerta de frescura '$($CFG.frescuraAlertName)'..." -ForegroundColor Cyan
    Write-Host ("  Ventana: {0} (umbral de {1} h), evaluada cada hora." -f $ventana, $horas)

    # --auto-mitigate true: sin el no llega el 'Deactivated' cuando vuelve a
    # haber carga, y la alerta se queda encendida para siempre.
    Invoke-Az monitor scheduled-query create `
        -g $CFG.resourceGroup -n $CFG.frescuraAlertName `
        --location $CFG.location `
        --scopes $idWorkspace `
        --condition "count 'Frescura' < 1" `
        --condition-query $consulta `
        --window-size $ventana `
        --evaluation-frequency 1h `
        --severity 2 `
        --auto-mitigate true `
        --action-groups $idAg `
        --description "El datamart lleva mas de $horas h sin un build_mart completo desde el job" `
        --tags @(Get-EtiquetasCli) -o none
    Confirmar-Exito "no se ha podido crear la alerta de frescura"
}

Invoke-Az monitor scheduled-query show `
    -g $CFG.resourceGroup -n $CFG.frescuraAlertName `
    --query "{nombre:name, activa:enabled, severidad:severity}" -o table

Write-Host ""
Write-Host "Alerta de frescura lista." -ForegroundColor Green
Write-Host "NO esta verificada hasta que llegue un correo de verdad." -ForegroundColor Yellow
Write-Host "La prueba de extremo a extremo esta en infra/README.md (R23 de F-024):"
Write-Host "acortar la ventana fuera del horario de carga, esperar el Activated,"
Write-Host "restaurarla y comprobar el Deactivated tras la siguiente noche buena."
