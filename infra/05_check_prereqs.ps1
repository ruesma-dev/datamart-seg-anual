# infra/05_check_prereqs.ps1
#
# SOLO LECTURA. No crea, no modifica y no borra nada: comprueba que estan todas
# las condiciones para que el resto de scripts funcione, y aborta con
# diagnostico si falta alguna. Ejecutalo SIEMPRE antes del primer despliegue de
# un entorno y despues de cualquier cambio en su fichero de configuracion.
#
#     pwsh -File infra/05_check_prereqs.ps1
#
# Codigo de salida 0 = se puede continuar. Distinto de 0 = PARA.

[CmdletBinding()]
param(
    [string]$Entorno
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\00_vars.ps1" -Entorno $Entorno

$script:fallos = 0
$script:avisos = 0

function Escribir-Ok {
    param([string]$Mensaje)
    Write-Host "[OK]    $Mensaje" -ForegroundColor Green
}

function Escribir-Aviso {
    param([string]$Mensaje)
    Write-Host "[AVISO] $Mensaje" -ForegroundColor Yellow
    $script:avisos++
}

function Escribir-Fallo {
    param([string]$Mensaje)
    Write-Host "[FALLO] $Mensaje" -ForegroundColor Red
    $script:fallos++
}

Write-Host "=== Prerrequisitos del despliegue (solo lectura) ===" -ForegroundColor Cyan

# --- 1. Sesion de Azure y suscripcion ---------------------------------------

$cuenta = az account show --query "{nombre:name, id:id, estado:state}" -o json 2>$null
if ($LASTEXITCODE -ne 0 -or -not $cuenta) {
    Escribir-Fallo "no hay sesion de Azure iniciada. Ejecuta 'az login'."
} else {
    $datos = $cuenta | ConvertFrom-Json
    Escribir-Ok "sesion activa sobre la suscripcion '$($datos.nombre)' ($($datos.estado))"
    if ($datos.id -ne $SUB) {
        Escribir-Aviso "el contexto apunta a otra suscripcion que AZ_SUBSCRIPTION_ID; manda la variable"
    }
}

# --- 2. Extension containerapp de la CLI ------------------------------------

$extension = az extension show -n containerapp --query version -o tsv 2>$null
if ($LASTEXITCODE -ne 0 -or -not $extension) {
    Escribir-Fallo "falta la extension 'containerapp' de la CLI: az extension add -n containerapp"
} else {
    Escribir-Ok "extension containerapp $extension"
}

# --- 3. El registro de contenedores existe ----------------------------------

$admin = az acr show -n $CFG.acrName -g $CFG.acrResourceGroup --query adminUserEnabled -o tsv 2>$null
if ($LASTEXITCODE -ne 0) {
    Escribir-Fallo "no se ve el registro de contenedores '$($CFG.acrName)' en '$($CFG.acrResourceGroup)'"
} else {
    Escribir-Ok "registro de contenedores '$($CFG.acrName)' accesible"
    if ($admin -eq "true") {
        Escribir-Aviso "el registro tiene habilitado el usuario administrador; el job no lo usa"
    }
}

# --- 4. El servidor de Postgres del datamart --------------------------------

$consultaPg = "{id:id, version:version, sku:sku.name, discoGB:storage.storageSizeGb, " +
              "entra:authConfig.activeDirectoryAuth}"
$servidor = az postgres flexible-server show -g $CFG.pgResourceGroup -n $PG_SERVER `
    --query $consultaPg -o json 2>$null

if ($LASTEXITCODE -ne 0 -or -not $servidor) {
    Escribir-Fallo "no se ve el servidor de Postgres '$PG_SERVER' en '$($CFG.pgResourceGroup)'"
} else {
    $pg = $servidor | ConvertFrom-Json
    Escribir-Ok "Postgres $($pg.version) ($($pg.sku), $($pg.discoGB) GB) accesible"

    # DA-4, CERRADA el 2026-08-10 (opcion B): el modo esperado es 'password' y
    # la contrasena viaja como referencia a Key Vault. El modo 'entra' queda
    # implementado y dormido, y esta comprobacion es la que evita que
    # reactivarlo salga barato en apariencia: sin ella el job se crea perfecto
    # y falla al conectar todas las noches a las 02:00, que es el fallo mas
    # caro de diagnosticar porque nadie esta mirando.
    switch ($CFG.pgAuthMode) {
        "entra" {
            if ($pg.entra -eq "Enabled") {
                Escribir-Ok "el servidor admite autenticacion Entra"
            } else {
                $texto = "el entorno pide autenticacion Entra y el servidor la tiene en " +
                         "'$($pg.entra)'. Habilitarla es una operacion de SERVIDOR que afecta " +
                         "a las demas bases alojadas ahi: NO la ejecutes por tu cuenta. " +
                         "DA-4 se cerro con la opcion B (contrasena por Key Vault); volver a " +
                         "Entra exige reabrirla. Ver infra/README.md."
                Escribir-Fallo $texto
            }
        }
        "password" {
            $texto = "autenticacion por contrasena (DA-4 opcion B): el job la recibe como " +
                     "referencia al secreto '$($CFG.pgSecretName)' del vault del proyecto. " +
                     "Ese secreto se migra a mano ANTES de crear el job (README, paso 8 bis)."
            Escribir-Ok $texto
        }
        default {
            Escribir-Fallo "el entorno declara pgAuthMode='$($CFG.pgAuthMode)', que no existe. Valores validos: 'password' o 'entra' (DA-4)."
        }
    }

    # Espacio en disco. El 2026-08-09 una carga completa lleno el disco del
    # servidor y lo dejo en solo lectura diez minutos. El job nocturno ejecuta
    # esa misma carga.
    $consultaMetrica = "max(value[0].timeseries[0].data[?maximum!=null].maximum)"
    $ocupacion = az monitor metrics list --resource $pg.id --metric storage_percent `
        --aggregation Maximum --interval PT15M --query $consultaMetrica -o tsv 2>$null

    if ($LASTEXITCODE -eq 0 -and $ocupacion) {
        $porcentaje = [double]$ocupacion
        $legible = "{0:N1}" -f $porcentaje
        if ($porcentaje -ge 60) {
            $texto = "el disco del servidor va al $legible %. Una carga completa lo lleno " +
                     "el 2026-08-09 y lo dejo en solo lectura. NO programes el job."
            Escribir-Fallo $texto
        } else {
            Escribir-Ok "ocupacion del disco del servidor: $legible %"
        }
    } else {
        Escribir-Aviso "no se ha podido leer la ocupacion del disco del servidor"
    }
}

# --- 5. Permiso para crear asignaciones de rol ------------------------------
#
# 60_create_identity.ps1 crea tres. Sin uno de estos dos roles fallara ahi, con
# medio entorno ya aprovisionado.

$yo = az ad signed-in-user show --query id -o tsv 2>$null
if ($LASTEXITCODE -ne 0 -or -not $yo) {
    Escribir-Aviso "no se ha podido identificar al usuario de la sesion (permisos de Graph)"
} else {
    $consultaRoles = "[?roleDefinitionName=='Owner' || " +
                     "roleDefinitionName=='User Access Administrator'].roleDefinitionName"
    $roles = az role assignment list --assignee $yo --all --query $consultaRoles -o tsv 2>$null
    $rolesTexto = (($roles -split "`n") | Where-Object { $_ }) -join ", "
    if ($rolesTexto) {
        Escribir-Ok "la cuenta puede crear asignaciones de rol ($rolesTexto)"
    } else {
        Escribir-Aviso "no se ve un rol que permita crear asignaciones; si 60_create_identity falla con AuthorizationFailed, es esto"
    }
}

# --- 6. Nombres globalmente unicos todavia libres ---------------------------

$libre = az storage account check-name --name $CFG.storageAccount --query nameAvailable -o tsv 2>$null
if ($LASTEXITCODE -eq 0 -and $libre -eq "false") {
    Escribir-Aviso "el nombre de la cuenta de almacenamiento ya esta tomado (o ya es tuyo); si no es tuyo, cambialo en el fichero de entorno y no toques ningun script"
}

# --- Veredicto --------------------------------------------------------------

Write-Host ""
Write-Host "-----------------------------------------------"
if ($script:fallos -eq 0) {
    Write-Host "PRERREQUISITOS OK ($script:avisos aviso(s)). Puedes continuar." -ForegroundColor Green
    exit 0
} else {
    Write-Host "$script:fallos comprobacion(es) fallida(s). NO despliegues." -ForegroundColor Red
    exit 1
}
