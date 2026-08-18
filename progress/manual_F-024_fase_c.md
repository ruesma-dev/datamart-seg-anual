<!-- progress/manual_F-024_fase_c.md -->
# F-024 · Fase C — verificaciones MANUAL en Azure

Cuaderno de las verificaciones que hace el humano contra Azure (T17–T20) y de
las lecturas que las acompañan. Cada intento se anota con su fecha, su comando
exacto y su **salida real**: es la evidencia que el reviewer valida contra
`CHECKPOINTS.md` C4 y la spec (R23–R26).

---

## 2026-08-18 · Foto previa al despliegue: NO SE PUDO CAPTURAR

**Qué se pretendía.** Capturar, antes de desplegar la imagen con F-024, el
estado que deja de existir en cuanto corra la primera carga con la puerta de
coherencia: `raw` cargado por una imagen anterior, sin `batch_id`. Es la
evidencia de que `check-coherencia` responde `sin_batch` (T20, R26).

**Qué pasó.** El comando no llega a la base de datos:

```
$ python main.py timings --last 3
RuntimeError: No puedo conectar a la BBDD 'sigrid_dm' ... Conexión usada:
host=psql-albaranes-rs9k2.postgres.database.azure.com port=5432
dbname=sigrid_dm user=sigrid_dm_app password=*** sslmode=require.
Detalle: connection timeout expired
```

**Causa, verificada, no supuesta.** La IP pública que tiene hoy el puesto no
está cubierta por ninguna regla del firewall de `psql-albaranes-rs9k2`. Las
reglas vigentes (leídas con `az`, solo lectura) son cinco: `AllowAzureServices`,
`caj-datamart-seg-dev` (la del job, que sí funciona), la del puesto de
2026-08-17 —un rango /24— y dos reglas heredadas de `albaranes`
(`ClientPgris` y `FirewallIPAddress_2026-6-16_16-42-54`). Ninguna contiene la
dirección actual.

Esto es exactamente lo que F-023 anticipó al cerrar su **DA-2**: las
direcciones del puesto rotan, así que las reglas caducan solas y dejar las
viejas puestas no da acceso, solo deja una puerta abierta que además no sirve.

**Qué hace falta para capturarla** (lo ejecuta el humano: es una escritura en
un recurso compartido con `albaranes` y `partes`, y por eso ningún agente la
lanza):

```powershell
$IP = (Invoke-RestMethod https://api.ipify.org)     # o la que dé tu router
az postgres flexible-server firewall-rule create --resource-group rg-albaranes-dev --server-name psql-albaranes-rs9k2 --rule-name "datamart-puesto-pgris-$(Get-Date -Format yyyy-MM-dd)" --start-ip-address $IP --end-ip-address $IP
```

**Ojo con los nombres de los parámetros**, que muerden: en
`firewall-rule create`, `--name`/`-n` es el nombre de la **regla** y el
servidor va en `--server-name`/`-s`. En `firewall-rule list`, en cambio,
`--server-name` es el servidor y no hay regla que nombrar. Pasar el servidor
en `--name` falla con «the following arguments are required:
--server-name/-s», que no dice lo que uno espera. Escrito en una sola línea a
propósito: un backtick de continuación con un espacio detrás rompe el comando
en PowerShell sin decir por qué.

Con la regla puesta, las tres lecturas de la foto (ninguna escribe nada):

```powershell
python main.py timings --last 3      # las 2 filas RUNNING huérfanas del 18-ago
python main.py check-coherencia      # se espera: sin_batch (raw anterior a F-024)
python main.py check-frescura        # horas desde el último build_mart completo
```

**Ventana**: la foto pierde su valor en cuanto arranque la primera carga con la
imagen de F-024, incluida la nocturna programada a las 02:00 UTC. Si no da
tiempo, no es un drama: T20 se puede verificar igual sobre el estado que haya,
declarando por escrito que el `sin_batch` no se llegó a fotografiar.

**Nota para quien lo retome**: la limpieza de las reglas del firewall es el
bloque 3 de F-023 y, por su DA-7, va **después** de esta Fase C. No borres la
regla que acabas de crear hasta que F-024 esté cerrada.
