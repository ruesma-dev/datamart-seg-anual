# infra/15_provision_db.ps1
#
# Provisiona la base del datamart y sus roles DENTRO del servidor de Postgres
# compartido que ya sirve a otras dos aplicaciones en produccion. Es de F-005;
# F-003 solo lo reescribio para que lea sus nombres de $CFG como el resto.
#
# ESTE SCRIPT NO HACE NADA POR DEFECTO. Sin -Ejecutar solo imprime el plan y
# lanza el diagnostico de SOLO LECTURA. Es deliberado: el servidor tiene dos
# bases en produccion y un error de alcance afecta a dos aplicaciones vivas.
#
# Uso:
#   .\15_provision_db.ps1 -AdminUser <usuario>              # plan, sin tocar nada
#   (APP_PWD, MCP_PWD y TOTAL_PWD en el entorno, leidas de Key Vault: runbook
#    secciones 4 y 12; nunca escritas a mano ni en un fichero)
#   .\15_provision_db.ps1 -AdminUser <usuario> -Ejecutar
#
# psql: las OPCIONES van SIEMPRE delante de la cadena de conexion, que es lo
# ultimo (F-136). En Windows psql deja de leer opciones tras la cadena: las
# ignora y las imprime, y asi se expusieron dos contrasenas el 2026-10-12. Las
# contrasenas NO van como argumento: 02_roles.sql las lee del entorno con
# \getenv, y psql las hereda de esta sesion. -X: sin el psqlrc del usuario.
#
# Lo que este script NO hace, a proposito:
#   - no crea reglas de firewall (las crea el humano, ver el runbook seccion 5);
#   - no habilita autenticacion Entra: es una operacion de SERVIDOR y el humano
#     la descarto el 2026-08-08 porque afectaria a las otras dos bases;
#   - no cambia parametros del servidor, su SKU ni su almacenamiento;
#   - no toca ninguna base que no sea la del datamart.
#
# Requisitos: Azure CLI con sesion iniciada y psql en el PATH.

[CmdletBinding()]
param(
    [switch]$Ejecutar,
    [string]$AdminUser = $env:PG_ADMIN_USER,
    [string]$Entorno
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\00_vars.ps1" -Entorno $Entorno

$sqlDir = Join-Path $PSScriptRoot "sql"

Write-Host ""
Write-Host "=== Provision de $($CFG.pgDatabase) en $($CFG.pgHost) ===" -ForegroundColor Cyan
Write-Host ("  Resource group  : {0} (NO es el del datamart)" -f $CFG.pgResourceGroup)
Write-Host ("  Servidor        : {0}" -f $PG_SERVER)
Write-Host ("  Base a crear    : {0}" -f $CFG.pgDatabase)
Write-Host ("  Roles           : {0} (grupo), {1} (ETL), {2} (solo lectura)" -f `
    $CFG.pgSetRole, $CFG.pgUser, $CFG.pgReadonlyRole)
# Los otros dos los crea 02_roles.sql con su nombre: aqui no se escribe ningun
# nombre de recurso (F-003, R1), solo se dice que existen.
Write-Host "                    + grupo autorizado (F-135) y login de acceso total del MCP (F-136)"
Write-Host ""

if (-not $AdminUser) {
    Write-Host "Falta el usuario administrador del servidor." -ForegroundColor Yellow
    Write-Host "Pasalo con -AdminUser o en la variable de entorno PG_ADMIN_USER."
    exit 1
}

# --- 1. Fotografia previa, solo lectura -------------------------------------
Write-Host "--- Estado actual del servidor (solo lectura) ---" -ForegroundColor Cyan
Invoke-Az postgres flexible-server show -g $CFG.pgResourceGroup -n $PG_SERVER `
    --query "{sku:sku.name, version:version, almacenamientoGB:storage.storageSizeGb, ha:highAvailability.mode, retencionDias:backup.backupRetentionDays}" `
    -o table

Write-Host ""
Write-Host "--- Reglas de firewall existentes ---" -ForegroundColor Cyan
Write-Host "Guarda esta salida: tras cualquier cambio debe contener EXACTAMENTE" -ForegroundColor Yellow
Write-Host "estas mismas reglas mas las nuevas." -ForegroundColor Yellow
Invoke-Az postgres flexible-server firewall-rule list -g $CFG.pgResourceGroup -n $PG_SERVER -o table

Write-Host ""
Write-Host "--- Diagnostico de la base (solo lectura) ---" -ForegroundColor Cyan
$dsnAdmin = "host=$($CFG.pgHost) dbname=postgres user=$AdminUser sslmode=require"
psql -X -f (Join-Path $sqlDir "03_diagnostico.sql") "$dsnAdmin"

if (-not $Ejecutar) {
    Write-Host ""
    Write-Host "Modo plan: no se ha creado nada." -ForegroundColor Green
    Write-Host "PUERTA DE ESPACIO: si quedan menos de 14 GB libres, PARA." -ForegroundColor Yellow
    Write-Host "Ampliar almacenamiento es IRREVERSIBLE: el disco solo crece."  -ForegroundColor Yellow
    Write-Host "Cuando este decidido, repite con -Ejecutar."
    exit 0
}

# --- 2. Comprobaciones antes de escribir ------------------------------------
if (-not $env:APP_PWD -or -not $env:MCP_PWD -or -not $env:TOTAL_PWD) {
    Write-Host "Faltan las contrasenas en el entorno: APP_PWD, MCP_PWD y TOTAL_PWD." -ForegroundColor Red
    Write-Host "Generalas y guardalas en Key Vault ANTES (runbook secciones 4 y 12)."
    Write-Host "No se escriben nunca en un fichero del repositorio."
    exit 1
}

# --- 3. Creacion de la base y los roles -------------------------------------
Write-Host ""
Write-Host "--- 01_create_database.sql (rol de grupo + base) ---" -ForegroundColor Cyan
psql -X -v ON_ERROR_STOP=1 -f (Join-Path $sqlDir "01_create_database.sql") "$dsnAdmin"

Write-Host ""
Write-Host "--- 02_roles.sql (roles de login, esquemas y permisos) ---" -ForegroundColor Cyan
$dsnDb = "host=$($CFG.pgHost) dbname=$($CFG.pgDatabase) user=$AdminUser sslmode=require"
# Las contrasenas las lee 02_roles.sql del entorno con \getenv: no van como argumento.
psql -X -v ON_ERROR_STOP=1 -f (Join-Path $sqlDir "02_roles.sql") "$dsnDb"

Write-Host ""
Write-Host "Provision terminada. Siguiente paso del runbook: comprobar que las" -ForegroundColor Green
Write-Host "otras dos aplicaciones siguen conectando, y que el listado de reglas"
Write-Host "de firewall no ha cambiado."
