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
az postgres flexible-server firewall-rule create --resource-group rg-albaranes-dev --server-name psql-albaranes-rs9k2 --name "datamart-puesto-pgris-$(Get-Date -Format yyyy-MM-dd)" --start-ip-address $IP --end-ip-address $IP
```

**Ojo con los nombres de los parámetros**, que muerden dos veces seguidas
(pagado el 2026-08-18):

- El servidor va en `--server-name`/`-s`, **no** en `--name`. Pasarlo en
  `--name` falla con «the following arguments are required: --server-name/-s»,
  que no dice lo que uno espera.
- La regla se nombra con `--name`/`-n`. **`--rule-name` no existe** en la CLI
  instalada en el puesto: devuelve «unrecognized arguments».

Escrito en una sola línea a propósito: un backtick de continuación con un
espacio detrás rompe el comando en PowerShell sin decir por qué.

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

---

## 2026-08-18 · Foto previa al despliegue: CAPTURADA

El humano creó la regla de firewall y las tres lecturas pasaron. Salidas
reales, recortadas solo donde se indica. **Ninguna escribe nada.**

### `python main.py timings --last 3`

Las dos filas huérfanas del 18-ago siguen ahí, y el aviso al pie funciona:

```
stage  build_stg.build_plan_mensual           2026-08-18 08:54:25   0.0   0  RUNNING
stage  build_stg.build_plan_mensual.tramo_40  2026-08-18 10:08:51   0.0   0  RUNNING
------------------------------------------------------------------------------------
TOTAL                                                        33142.2  239,066,530

AVISO: 2 fila(s) RUNNING desde hace más de 6 h: probablemente huérfanas de un
proceso muerto; la próxima ejecución que escriba las marcará ABORTED.
```

Es el **estado de partida de R25**: tras el primer arranque con la imagen de
F-024, estas dos deben quedar `ABORTED` con motivo.

### `python main.py check-coherencia` → **KO, `sin_batch`** (evidencia de T20/R26)

```
Coherencia de raw: KO. El esquema raw no acredita una carga completa y
coherente, asi que no se construye stg encima:
  · ingeridas sin identidad de ejecucion (historico anterior a F-024):
    auxmun, auxobramb, auxobrcla, auxobrtca, auxobrtip, auxpro, cen, cob, com,
    comlin, comprv, con, condir, conext, ctr, ctrpro, dca, dcapro, dcf,
    dcfpro, dcfprodes, obr, obrctr, obrfas, obrfasamb, obrparpar, obrparpre,
    obrprv, pag, prv, rec

Solo hay dos salidas:
  1. Relanzar la ingesta completa: python main.py ingest --full
  2. Si la carga parcial fue deliberada: python main.py stage --sin-puerta
     (el veredicto queda registrado como SKIPPED en _meta.etl_runs)

=== Estado de stg ===
Coherencia de stg: OK. El ultimo build_stg termino correctamente (ejecucion None).
```

**Esto es exactamente lo que R26 exige demostrar**: las 31 tablas de `raw`
vienen de una imagen anterior a F-024, no llevan `batch_id`, y la puerta lo
dice con nombre y apellidos en vez de dejar construir `stg` encima. El
mensaje distingue el caso «histórico» del caso «batches mezclados», que es lo
que se verá en T18.

### `python main.py check-frescura` → **FRESCO**

```
paso            ultimo OK             horas        filas  ultimo intento      estado
------------------------------------------------------------------------------------
apply_grants    2026-08-18 13:08:18     6.4           28  2026-08-18 13:08:17 SUCCESS
build_mart      2026-08-18 13:08:17     6.4    5,319,560  2026-08-18 12:46:48 SUCCESS
build_stg       2026-08-18 12:46:48     6.8   43,793,846  2026-08-18 10:56:14 SUCCESS
ingest_raw      2026-08-18 10:56:10     8.7   20,047,942  2026-08-18 10:23:07 SUCCESS
load_excel_aux  2026-08-18 10:56:14     8.6            3  2026-08-18 10:56:11 SUCCESS

build_mart: FRESCO (umbral 30.0 h, lleva 6.4 h desde el último build correcto)
```

### Observaciones menores, para no perderlas

- El mensaje de `stg` termina en «(ejecucion **None**)» porque el histórico no
  tiene `batch_id`. No es un fallo —el veredicto es correcto—, pero enseña un
  `None` de Python al usuario donde debería decir algo como «sin identidad de
  ejecución». Merece un retoque cosmético; no bloquea nada.
- El `TOTAL` de `timings` (33.142 s ≈ 9,2 h) **suma las tres ejecuciones del
  día**, incluidas las dos que murieron. No es la duración de la carga buena
  (2 h 45): quien lea ese total sin contexto se lleva una idea equivocada.
