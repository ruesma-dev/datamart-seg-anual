# lanzar_builds.ps1 — F-044: lanzar los cuatro build a mano, cronometrados y
# vigilando el disco. Temporal: no forma parte del ETL, se borra al cerrar F-044.
#
# Uso:   .\scripts_temp\lanzar_builds.ps1
#        .\scripts_temp\lanzar_builds.ps1 -SoloDisco     (solo mide, no construye)
#
# Antes de nada: `az login` hecho, y este script reescribe la regla UNICA del
# firewall con tu IP del momento. No crea reglas nuevas.

param(
    [switch]$SoloDisco,
    [int]$LimitePct = 80
)

$ErrorActionPreference = "Stop"
$SERVIDOR = "psql-albaranes-rs9k2"
$GRUPO    = "rg-albaranes-dev"
$REGLA    = "datamart-puesto-pgris"

function Medir-Disco {
    # Usa el propio cliente del proyecto: asi la contrasena sale del .env y no
    # pasa por la consola ni por el historial.
    $salida = python -c @"
import main
from config.settings import get_settings
pg = main._get_pg()
total = get_settings().postgres.disco_total_gb
print(round(pg.medir_ocupacion_disco_pct(total), 2))
"@
    if ($LASTEXITCODE -ne 0) { throw "No se pudo medir el disco (firewall? credenciales?)" }
    # El logger puede escribir lineas antes del numero: nos quedamos con la ultima.
    $ultima = ($salida | Select-Object -Last 1).ToString().Trim()
    return [double]$ultima
}

function Actualizar-Firewall {
    $ip = (Invoke-RestMethod -Uri "https://api.ipify.org?format=json").ip
    Write-Host "IP del puesto: $ip" -ForegroundColor Cyan
    az postgres flexible-server firewall-rule update `
        --resource-group $GRUPO --name $SERVIDOR -n $REGLA `
        --start-ip-address $ip --end-ip-address $ip --output none
    if ($LASTEXITCODE -ne 0) { throw "No se pudo actualizar la regla $REGLA" }
    Write-Host "Regla $REGLA apuntando a $ip" -ForegroundColor Green
}

# --- Arranque ---
Actualizar-Firewall

$discoInicial = Medir-Disco
Write-Host "`nDisco al inicio: $discoInicial %" -ForegroundColor Yellow
if ($discoInicial -ge $LimitePct) {
    Write-Host "PARADA: el disco ya esta en $discoInicial %, por encima del limite $LimitePct %." -ForegroundColor Red
    exit 1
}

if ($SoloDisco) { exit 0 }

# El orden importa: los cuatro leen de stg, y maestro y compras alimentan lo
# que consultan los demas.
$builds = @("build-maestros", "build-compras", "build-retenciones", "build-cierre")
$resultados = @()

foreach ($b in $builds) {
    Write-Host "`n=== $b ===" -ForegroundColor Cyan
    $t0 = Get-Date

    python main.py $b
    $ok = ($LASTEXITCODE -eq 0)

    $minutos = [math]::Round(((Get-Date) - $t0).TotalMinutes, 1)

    # La IP puede haber rotado durante el build: la regla se refresca antes de
    # medir, o la medicion fallaria por firewall y no por el disco.
    Actualizar-Firewall
    $disco = Medir-Disco

    $resultados += [pscustomobject]@{ Build = $b; Minutos = $minutos; Ok = $ok; DiscoPct = $disco }
    Write-Host "$b -> $minutos min | disco $disco % | ok=$ok" -ForegroundColor $(if ($ok) { "Green" } else { "Red" })

    if (-not $ok) {
        Write-Host "PARADA: $b fallo. No se lanzan los siguientes." -ForegroundColor Red
        break
    }
    if ($disco -ge $LimitePct) {
        Write-Host "PARADA: disco en $disco %, por encima del limite $LimitePct %." -ForegroundColor Red
        break
    }
}

Write-Host "`n=== RESUMEN (el dato que necesita F-044) ===" -ForegroundColor Yellow
$resultados | Format-Table -AutoSize
$total = ($resultados | Measure-Object -Property Minutos -Sum).Sum
Write-Host "Total de los cuatro: $total min. Disco: $discoInicial % -> $($resultados[-1].DiscoPct) %"
Write-Host "`nComprueba despues que la huerfana desaparecio:" -ForegroundColor Cyan
Write-Host "  python main.py check-diccionario"
