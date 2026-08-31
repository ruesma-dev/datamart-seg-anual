# infra/96_create_alert_cobertura.ps1
#
# Crea la alerta de COBERTURA del datamart (F-052): avisa cuando el guardian
# `check-cobertura` encuentra una obra que entra en `stg` y no sale en `mart`, o
# filas que el build descarta sin decir nada.
#
# POR QUE HACE FALTA SI YA HAY DOS ALERTAS. 90_create_alert.ps1 dispara cuando
# una ejecucion TERMINA EN FALLO y 95_create_alert_frescura.ps1 cuando el job NO
# LLEGA A HACER su trabajo. Ninguna de las dos cubre el caso de esta feature: la
# noche va BIEN, el job termina en verde... y una obra entera no esta en el
# datamart. Es lo que llevaba pasando desde 2022 con la 0599 TANATORIO
# MAJADAHONDA, que publicaba 4.066.989,23 EUR de venta y 0,00 EUR de coste
# directo sin que nada chirriara.
#
# SIN ESTA REGLA EL GUARDIAN ES MUDO, y es el precio declarado de DA-4. Se
# decidio que `check-cobertura` AVISE Y NO BLOQUEE: la nocturna termina en verde
# aunque encuentre algo, asi que la alerta de fallo NO se dispara. Esta regla es
# la UNICA via por la que el hallazgo llega a una persona. Si no se despliega,
# el guardian detecta la obra invisible, la escribe en el log y no se entera
# NADIE.
#
# COMO FUNCIONA. Regla de consulta programada (KQL) sobre el workspace de Log
# Analytics: busca en las lineas de consola del job el marcador
# [F052-COBERTURA-KO] y dispara si hay AL MENOS UNA. Ojo, es AL REVES que la de
# frescura, que vigila la AUSENCIA de un evento: aqui se vigila la PRESENCIA de
# una linea. Confundirlas la deja disparando todas las noches o ninguna.
#
# EL MARCADOR VIVE EN DOS SITIOS que no pueden divergir: aqui y en
# etl_sigrid/domain/cobertura.py (constante MARCADOR_KO). Lo cruza
# tests/test_f052_marcador.py, que ademas EJECUTA la funcion de composicion de
# abajo y comprueba que el literal llega a la cadena que se envia de verdad. Si
# divergieran, la regla vigilaria un texto que ya nadie escribe y nadie se
# enteraria, que es exactamente el modo de fallo que F-052 existe para eliminar.
#
# LA VENTANA. 24 h, que es `coberturaVentanaHoras` en infra/env/<entorno>.json:
# el guardian corre una vez por noche, al final de `run-all`, asi que la ventana
# tiene que cubrir una noche entera y ninguna mas. 1440 minutos ES una de las
# granularidades que admite Azure (5, 10, 15, 30, 45, 60, 120, 180, 240, 300,
# 360, 720, 1440, 2880), asi que a diferencia de la alerta de frescura aqui no
# hace falta traducir nada. Las ventanas van en formato ##h##m##s ("24h"), NO en
# ISO 8601: un PT24H se rechaza.
#
# PASO PREVIO OBLIGATORIO, una sola vez por puesto (no es del repositorio, es de
# la maquina; esta anotado tambien en infra/README.md):
#
#     az extension add --name scheduled-query
#
# NINGUNA direccion de correo entra aqui (R30 de F-052, R26 de F-003): los
# destinatarios viven en el grupo de accion, que crea o localiza
# 90_create_alert.ps1 y al que se le pasan con -AlertEmail.
#
# DESPLIEGUE MANUAL, como el resto de infra/. Y NO ESTA VERIFICADA hasta que
# llegue un correo de verdad: la prueba de extremo a extremo esta en
# infra/README.md.
#
# IDEMPOTENTE: si la regla ya existe no se recrea.

[CmdletBinding()]
param(
    [string]$Entorno
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\00_vars.ps1" -Entorno $Entorno

# --- 0. La consulta, en una funcion para poder EJECUTARLA desde un test ------

function Componer-ConsultaCobertura {
    <#
    .SYNOPSIS
        Compone el argumento de --condition-query: "<nombre>=<kql>".

    .DESCRIPTION
        La consulta se compone AQUI, entera y en un solo sitio, para que un test
        pueda EJECUTAR esta funcion y mirar la cadena que se envia de verdad.

        No es una manera de ordenar el codigo: es la leccion del 2026-08-19 en
        95_create_alert_frescura.ps1. Alli la consulta vivia suelta en el cuerpo
        del script y solo se podia comprobar leyendo el fichero, asi que un test
        veia la linea que definia el filtro y la daba por buena; quitando esa
        variable de la concatenacion, la suite entera seguia en verde con la
        regla vigilando otra cosa.

        El nombre por defecto, 'Cobertura', es el mismo que cuenta el argumento
        --condition ("count 'Cobertura' > 0"). Son dos argumentos distintos que
        se refieren al mismo resultado, y hay un test que los cruza: si divergen,
        la regla cuenta algo que no existe y se queda muda sin que Azure proteste.
    #>
    param(
        [Parameter(Mandatory = $true)]
        [string]$Job,

        [string]$Nombre = "Cobertura"
    )

    # EL LITERAL. Tiene que ser byte a byte el MARCADOR_KO de
    # etl_sigrid/domain/cobertura.py. Lo cruza tests/test_f052_marcador.py.
    $marcador = "[F052-COBERTURA-KO]"

    # `contains` y no `has`: `has` tokeniza, y el marcador lleva corchetes y
    # guiones. `contains` compara la subcadena tal cual, que es lo que se quiere.
    #
    # ContainerJobName_s, NO ContainerAppName_s: la segunda no existe en
    # ContainerAppConsoleLogs_CL para un job (verificado con | getschema el
    # 2026-08-18). Filtrar por ella devolveria siempre cero filas y esta alerta
    # no dispararia NUNCA, que aqui es el fallo silencioso.
    $kql = ("ContainerAppConsoleLogs_CL " +
            "| where ContainerJobName_s == '$Job' " +
            "| where Log_s contains '$marcador'")

    return "$Nombre=$kql"
}

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

# --- 3. El canal de aviso: el mismo que usan las otras dos alertas ----------

$idAg = Invoke-Az monitor action-group show `
    -g $CFG.alertActionGroupRg -n $CFG.alertActionGroupName --query id -o tsv
if ($LASTEXITCODE -ne 0 -or -not $idAg) {
    throw ("no existe el grupo de accion '$($CFG.alertActionGroupName)' en " +
           "'$($CFG.alertActionGroupRg)'. Lo crea o lo localiza " +
           "90_create_alert.ps1, que es donde se pasan los destinatarios; aqui " +
           "no se escribe ningun correo.")
}

# --- 4. La regla ------------------------------------------------------------

$ventana = "{0}h" -f [int]$CFG.coberturaVentanaHoras

# La consulta viaja en una variable: al llevar espacios, PowerShell la
# entrecomilla al invocar az.cmd, y asi los parentesis, los corchetes y las
# barras verticales del KQL no los vuelve a interpretar cmd.exe.
$consulta = Componer-ConsultaCobertura -Job $CFG.job

$yaExiste = Invoke-Az monitor scheduled-query show `
    -g $CFG.resourceGroup -n $CFG.coberturaAlertName --query id -o tsv

if ($LASTEXITCODE -eq 0 -and $yaExiste) {
    Write-Host "La alerta '$($CFG.coberturaAlertName)' ya existe; no se recrea." -ForegroundColor Yellow
} else {
    Write-Host "Creando la alerta de cobertura '$($CFG.coberturaAlertName)'..." -ForegroundColor Cyan
    Write-Host ("  Ventana: {0}, evaluada cada hora." -f $ventana)
    Write-Host "  Dispara por PRESENCIA del marcador, no por su ausencia."

    # --auto-mitigate true: sin el no llega el 'Deactivated' cuando la noche
    # vuelve a salir limpia, y la alerta se queda encendida para siempre.
    Invoke-Az monitor scheduled-query create `
        -g $CFG.resourceGroup -n $CFG.coberturaAlertName `
        --location $CFG.location `
        --scopes $idWorkspace `
        --condition "count 'Cobertura' > 0" `
        --condition-query $consulta `
        --window-size $ventana `
        --evaluation-frequency 1h `
        --severity 2 `
        --auto-mitigate true `
        --action-groups $idAg `
        --description "El datamart publico una noche con obras o filas fuera de config/cobertura_excepciones.yaml" `
        --tags @(Get-EtiquetasCli) -o none
    Confirmar-Exito "no se ha podido crear la alerta de cobertura"
}

Invoke-Az monitor scheduled-query show `
    -g $CFG.resourceGroup -n $CFG.coberturaAlertName `
    --query "{nombre:name, activa:enabled, severidad:severity}" -o table

Write-Host ""
Write-Host "Alerta de cobertura lista." -ForegroundColor Green
Write-Host "NO esta verificada hasta que llegue un correo de verdad." -ForegroundColor Yellow
Write-Host "Y hasta entonces el guardian es MUDO: check-cobertura no tumba el job,"
Write-Host "asi que esta regla es la unica via por la que el hallazgo llega a nadie."
Write-Host "La prueba de extremo a extremo esta en infra/README.md."
