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
# 'step_finished', 'build_mart' y 'SUCCESS' dentro del umbral, y dispara si
# hay CERO. Se vigila la AUSENCIA porque es la senal: una regla que buscara "el
# ultimo evento" no disparia nunca cuando no hay ningun evento, que es
# exactamente el caso a detectar.
#
# LA VENTANA NO ES EL UMBRAL, Y NO ES UN CAPRICHO (defecto del 2026-08-19). El
# criterio de DA-4 sigue siendo 30 h, pero Azure NO admite una ventana de 30 h:
# solo acepta unas granularidades fijas y entre 24 h y 48 h no hay ninguna. Asi
# que el umbral se expresa en DOS sitios, los dos derivados del MISMO
# 'frescuraUmbralHoras' y ninguno escrito a mano:
#   - la VENTANA de la regla es la menor granularidad admitida que CONTIENE al
#     umbral (30 h -> 48 h), y la resuelve Resolver-VentanaAdmitida;
#   - el CRITERIO son las 30 h exactas, y viaja DENTRO de la consulta como
#     '| where TimeGenerated > ago(30h)'.
# Mirar 48 h de logs y contar solo los de las ultimas 30 no cambia lo que se
# vigila; lo que si lo cambiaria es quitar el filtro de la KQL y dejar que la
# regla juzgue con 48 h mientras 'check-frescura' juzga con 30.
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
#   - las ventanas van en formato ##h##m##s ("48h"), NO en ISO 8601: un PT48H
#     se rechaza;
#   - la columna del nombre del job en ContainerAppConsoleLogs_CL es
#     ContainerJobName_s, verificada con | getschema. ContainerAppName_s -la que
#     decia el README- NO existe para un job: filtrar por ella devolveria
#     siempre cero filas y la alerta disparia todas las noches.
#
# LA TRAMPA DE --help, que es lo que dejo pasar el defecto: --help valida la
# FORMA del argumento (##h##m##s), no el VALOR. Un "30h" pasa --help, pasa el
# cliente de az entero y lo rechaza el servicio al final del viaje:
#
#     (InvalidRequestContent) The request content was invalid and could not be
#     deserialized: 'WindowSize of 1800 minutes is not supported. Supported
#     granularities are: 5, 10, 15, 30, 45, 60, 120, 180, 240, 300, 360, 720,
#     1440, 2880'
#
# Por eso la lista de granularidades esta en el codigo y hay tests que la fijan:
# lo unico que confirma un valor es haberlo enviado o tener quien lo compruebe
# en la suite. "Lo dice --help" no es una confirmacion.
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

# --- 0. Lo que se deriva del umbral: la ventana y la consulta ---------------
#
# Las dos van en funciones y no sueltas en el cuerpo del script para que los
# tests puedan EJECUTARLAS y mirar el valor que producen. Leerlas como texto es
# lo que dejo pasar los dos defectos de esta feature: una ventana bien formada
# e invalida, y un filtro temporal bien definido que no llegaba a la consulta.

function Resolver-VentanaAdmitida {
    <#
    .SYNOPSIS
        Traduce el umbral de frescura (horas) a la ventana de la regla.

    .DESCRIPTION
        Azure solo admite unas granularidades fijas como windowSize, asi que la
        ventana NO puede ser el umbral: es la menor granularidad admitida que lo
        CONTIENE. La menor y no la mayor de la lista, porque una ventana mas
        ancha de lo necesario es mas caro de consultar y no aporta nada: el
        criterio exacto lo pone el filtro TimeGenerated de la KQL.

        Si el umbral no cabe en ninguna, se para AQUI: enviar una peticion que
        sabemos rechazada cuesta un viaje al ARM y devuelve un
        InvalidRequestContent que no dice que hacer.
    #>
    param(
        [Parameter(Mandatory = $true)]
        [int]$UmbralHoras
    )

    # La lista NO es una eleccion nuestra ni una defensa preventiva: es la que
    # devolvio el ARM el 2026-08-19 al rechazar la primera creacion de esta
    # regla ("Supported granularities are: ..."), copiada literal. Entre 1440
    # (24 h) y 2880 (48 h) no hay nada, y ahi es donde caen las 30 h de DA-4.
    $granularidades = @(5, 10, 15, 30, 45, 60, 120, 180, 240, 300, 360, 720, 1440, 2880)

    if ($UmbralHoras -lt 1) {
        throw ("el umbral de frescura configurado ($UmbralHoras h) no tiene " +
               "sentido: 'frescuraUmbralHoras' en infra/env/<entorno>.json debe " +
               "ser un numero de horas de 1 a 48")
    }

    $minutos = $UmbralHoras * 60
    $elegida = $granularidades | Where-Object { $_ -ge $minutos } | Select-Object -First 1

    if (-not $elegida) {
        throw ("el umbral de frescura configurado ($UmbralHoras h = $minutos min) " +
               "no cabe en ninguna ventana que admita Azure: la mayor es 2880 min " +
               "(48 h). Baja 'frescuraUmbralHoras' en infra/env/<entorno>.json a " +
               "48 o menos, o vigila esa frescura con otro mecanismo")
    }

    # Formato ##h##m##s, no ISO 8601. En horas cuando toca exacto, que es
    # siempre para umbrales de 1 h o mas, y en minutos por si algun dia no.
    if ($elegida % 60 -eq 0) {
        return ("{0}h" -f ($elegida / 60))
    }
    return ("{0}m" -f $elegida)
}

function Componer-ConsultaFrescura {
    <#
    .SYNOPSIS
        Compone el argumento de --condition-query: "<nombre>=<kql>".

    .DESCRIPTION
        La consulta se compone AQUI, entera y en un solo sitio, para que un test
        pueda EJECUTAR esta funcion y mirar la cadena que se envia de verdad.

        No es una manera de ordenar el codigo: es la leccion del 2026-08-19. La
        consulta vivia suelta en el cuerpo del script y solo se podia comprobar
        leyendo el fichero, asi que un test veia la linea que define el filtro
        temporal y la daba por buena. Quitando esa variable de la concatenacion
        -lo que deja un merge mal resuelto o un refactor con prisa- la suite
        entera seguia en verde con la regla juzgando a 48 h en vez de a 30. Lo
        encontro el reviewer buscando exactamente eso.

        El nombre por defecto, 'Frescura', es el mismo que cuenta el argumento
        --condition ("count 'Frescura' < 1"). Son dos argumentos distintos que
        se refieren al mismo resultado, y hay un test que los cruza: si divergen,
        la regla cuenta algo que no existe y se queda muda sin que Azure proteste.
    #>
    param(
        [Parameter(Mandatory = $true)]
        [string]$Job,

        [Parameter(Mandatory = $true)]
        [int]$UmbralHoras,

        [string]$Nombre = "Frescura"
    )

    # El criterio exacto de DA-4 va DENTRO de la consulta porque la ventana de
    # la regla es mas ancha que el umbral (ver la cabecera). Sin este filtro, la
    # alerta contaria los eventos de las ultimas 48 h y no los de las 30 que
    # dice vigilar.
    $filtroTemporal = "| where TimeGenerated > ago({0}h)" -f $UmbralHoras

    $kql = ("ContainerAppConsoleLogs_CL " +
            "| where ContainerJobName_s == '$Job' " +
            "| where Log_s has_all ('step_finished','build_mart','SUCCESS') " +
            $filtroTemporal)

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

# Las dos mitades del criterio, las dos derivadas del MISMO umbral y ninguna
# escrita a mano: ese numero decide tambien el default de
# `python main.py check-frescura`, y si divergen la alerta vigila una cosa y el
# comando juzga otra. La ventana sale mas ancha que el umbral porque el servicio
# solo admite ciertas granularidades (ver la cabecera); el criterio exacto lo
# pone el filtro temporal dentro de la consulta.
$ventana = Resolver-VentanaAdmitida -UmbralHoras $horas

# La consulta viaja en una variable: al llevar espacios, PowerShell la
# entrecomilla al invocar az.cmd, y asi los parentesis y las barras verticales
# del KQL no los vuelve a interpretar cmd.exe.
$consulta = Componer-ConsultaFrescura -Job $CFG.job -UmbralHoras $horas

$yaExiste = Invoke-Az monitor scheduled-query show `
    -g $CFG.resourceGroup -n $CFG.frescuraAlertName --query id -o tsv

if ($LASTEXITCODE -eq 0 -and $yaExiste) {
    Write-Host "La alerta '$($CFG.frescuraAlertName)' ya existe; no se recrea." -ForegroundColor Yellow
} else {
    Write-Host "Creando la alerta de frescura '$($CFG.frescuraAlertName)'..." -ForegroundColor Cyan
    Write-Host ("  Ventana: {0} -la menor que admite Azure y contiene el umbral-," -f $ventana)
    Write-Host ("  criterio de {0} h dentro de la consulta, evaluada cada hora." -f $horas)

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
Write-Host ("Al restaurar, la ventana es {0}: cualquier otro valor que no sea una" -f $ventana)
Write-Host "granularidad admitida deja la regla con la ventana corta de la prueba."
