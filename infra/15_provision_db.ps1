# infra/15_provision_db.ps1
#
# Provisiona la base sigrid_dm y sus roles DENTRO del servidor compartido
# psql-albaranes-rs9k2, que ya sirve a albaranes y partes.
#
# ESTE SCRIPT NO HACE NADA POR DEFECTO. Sin -Ejecutar solo imprime el plan y
# lanza el diagnóstico de SOLO LECTURA. Es deliberado: el servidor tiene dos
# bases en producción y un error de alcance afecta a dos aplicaciones vivas.
#
# Uso:
#   . .\00_vars.ps1
#   .\15_provision_db.ps1                       # plan + diagnóstico, sin tocar nada
#   $env:APP_PWD = "<generada>"                 # ver el runbook: se generan y se
#   $env:MCP_PWD = "<generada>"                 #   guardan en Key Vault
#   .\15_provision_db.ps1 -Ejecutar
#
# Lo que este script NO hace, a propósito:
#   - no crea reglas de firewall (las crea el humano, ver el runbook §5);
#   - no habilita autenticación Entra: es una operación de SERVIDOR y el humano
#     la descartó el 2026-08-08 porque afectaría a albaranes y partes;
#   - no cambia parámetros del servidor, su SKU ni su almacenamiento;
#   - no toca albaranes ni partes.
#
# Requisitos: Azure CLI con sesión iniciada y psql en el PATH.

[CmdletBinding()]
param(
    [switch]$Ejecutar,
    [string]$AdminUser = $env:PG_ADMIN_USER
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\00_vars.ps1"

$sqlDir = Join-Path $PSScriptRoot "sql"

Write-Host ""
Write-Host "=== Provision de $PG_DB en $PG_HOST ===" -ForegroundColor Cyan
Write-Host "  Resource group  : $PG_RG (NO es el del datamart: es el de albaranes)"
Write-Host "  Servidor        : $PG_SERVER"
Write-Host "  Base a crear    : $PG_DB"
Write-Host "  Roles           : $PG_OWNER_ROLE (grupo), $PG_APP_ROLE (ETL), $PG_RO_ROLE (MCP)"
Write-Host ""

if (-not $AdminUser) {
    Write-Host "Falta el usuario administrador del servidor." -ForegroundColor Yellow
    Write-Host "Pasalo con -AdminUser o en la variable de entorno PG_ADMIN_USER."
    exit 1
}

# --- 1. Fotografia previa, solo lectura -------------------------------------
Write-Host "--- Estado actual del servidor (solo lectura) ---" -ForegroundColor Cyan
az postgres flexible-server show -g $PG_RG -n $PG_SERVER `
    --query "{sku:sku.name, version:version, almacenamientoGB:storage.storageSizeGb, ha:highAvailability.mode, retencionDias:backup.backupRetentionDays}" `
    -o table

Write-Host ""
Write-Host "--- Reglas de firewall existentes ---" -ForegroundColor Cyan
Write-Host "Guarda esta salida: tras cualquier cambio debe contener EXACTAMENTE" -ForegroundColor Yellow
Write-Host "estas mismas reglas mas las nuevas." -ForegroundColor Yellow
az postgres flexible-server firewall-rule list -g $PG_RG -n $PG_SERVER -o table

Write-Host ""
Write-Host "--- Diagnostico de la base (solo lectura) ---" -ForegroundColor Cyan
$dsnAdmin = "host=$PG_HOST dbname=postgres user=$AdminUser sslmode=require"
psql "$dsnAdmin" -f (Join-Path $sqlDir "03_diagnostico.sql")

if (-not $Ejecutar) {
    Write-Host ""
    Write-Host "Modo plan: no se ha creado nada." -ForegroundColor Green
    Write-Host "PUERTA DE ESPACIO: si quedan menos de 14 GB libres, PARA." -ForegroundColor Yellow
    Write-Host "Ampliar almacenamiento es IRREVERSIBLE: el disco solo crece."  -ForegroundColor Yellow
    Write-Host "Cuando este decidido, repite con -Ejecutar."
    exit 0
}

# --- 2. Comprobaciones antes de escribir ------------------------------------
if (-not $env:APP_PWD -or -not $env:MCP_PWD) {
    Write-Host "Faltan las contrasenas en el entorno: APP_PWD y MCP_PWD." -ForegroundColor Red
    Write-Host "Generalas y guardalas en Key Vault ANTES (runbook seccion 4)."
    Write-Host "No se escriben nunca en un fichero del repositorio."
    exit 1
}

# --- 3. Creacion de la base y los roles -------------------------------------
Write-Host ""
Write-Host "--- 01_create_database.sql (rol de grupo + base) ---" -ForegroundColor Cyan
psql "$dsnAdmin" -v ON_ERROR_STOP=1 -f (Join-Path $sqlDir "01_create_database.sql")

Write-Host ""
Write-Host "--- 02_roles.sql (roles de login, esquemas y permisos) ---" -ForegroundColor Cyan
$dsnDb = "host=$PG_HOST dbname=$PG_DB user=$AdminUser sslmode=require"
psql "$dsnDb" -v ON_ERROR_STOP=1 `
    -v app_pwd="$env:APP_PWD" -v mcp_pwd="$env:MCP_PWD" `
    -f (Join-Path $sqlDir "02_roles.sql")

Write-Host ""
Write-Host "Provision terminada. Siguiente paso del runbook: comprobar que" -ForegroundColor Green
Write-Host "albaranes y partes siguen conectando, y que el listado de reglas de"
Write-Host "firewall no ha cambiado."
