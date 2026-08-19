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

---

## 2026-08-18 · T17 — Despliegue de la imagen con F-024 y verificación R25

Ejecutado por el agente `implementer` con autorización expresa del humano (ver
apartado siguiente). Rama `feature/F-024-coherencia-cargas-truncadas`.
`bash harness/init.sh` en verde antes de empezar: 596 tests, cobertura 100 % de
372 líneas cambiadas.

### Autorización del humano sobre `05_check_prereqs.ps1` (dejada por escrito)

`infra/05_check_prereqs.ps1` termina en **FALLO** por una sola comprobación: el
disco del servidor compartido va al **74,5 %**, y una carga completa lo llenó el
2026-08-09 dejándolo en solo lectura. **El humano lo ha visto con los datos
delante y ha autorizado desplegar igualmente**, y ha decidido sobre el disco
«dejarlo, vigilar y ya». Razón: **el despliegue no cambia el volumen de datos ni
el pipeline**, solo la imagen del job y las puertas de coherencia de F-024.

Datos ya medidos que soportan la decisión (no se volvieron a medir): base 74,5 %
bajando ~0,6 puntos/hora, picos de 88,5 % y 83,9 % durante las cargas de hoy,
18,5 GB de datos sobre 32 GB de disco, de los que `sigrid_dm` son 18 GB (`stg`
10 GB, `raw` 4,8, `mart` 2,2, `compras` 1,2) frente a 17 MB de `albaranes` y
8,9 MB de `partes`.

**Esta autorización cubre este despliegue y nada más.** No se extiende a
programar cargas, a T18 ni a ninguna otra escritura.

### 1. `powershell -NoProfile -File infra\70_build_image.ps1`

Construcción en Azure (`acr build`), sin Docker en el puesto. **Salida
recortada**: se omite el log de `pip install` y el de las 13 capas del
`docker build`, todos correctos. Se conserva el principio y el final:

```
=== Configuracion cargada: ...\infra\env\dev.json ===
  Entorno        : dev / spaincentral
  Resource group : rg-datamart-seg-dev
  Job            : caj-datamart-seg-dev en cae-datamart-seg-dev
  Postgres       : ...sigrid_dm como sigrid_dm_app (auth password)
  Suscripcion    : la del contexto activo (no se escribe en el repositorio)

Construyendo datamart-seg-anual:r20260818-2146 ...
  (la construccion ocurre en Azure; puede tardar varios minutos)
[... descarga de python:3.12-slim, pip install de 41 paquetes, pasos 1/13 a 13/13 ...]
Successfully built 206cd4cceb07
Successfully tagged acralbaranesdev.azurecr.io/datamart-seg-anual:r20260818-2146
2026/08/18 19:47:35 Executing step ID: push...
r20260818-2146: digest: sha256:f0b32704d18d7d45661a2c934ed597b114f52b27c21c398761d0dd249d0391b7 size: 2412
2026/08/18 19:47:46 Successfully pushed image
Run ID: nh4h was successful after 44s

r20260810-1024
r20260817-2025
r20260818-1003
r20260818-2146

Imagen publicada: acralbaranesdev.azurecr.io/datamart-seg-anual:r20260818-2146
APUNTA ESTE TAG: r20260818-2146
```

**TAG DESPLEGADO: `r20260818-2146`** (digest `sha256:f0b3270…0391b7`). Es el que
tiene que aparecer en los logs del job y en `python main.py version`.

### 2. `powershell -NoProfile -File infra\85_update_job.ps1 -Tag r20260818-2146`

Salida completa, sin recortar salvo la cabecera de configuración:

```
Imagen actual : acralbaranesdev.azurecr.io/datamart-seg-anual:r20260818-1003
Imagen nueva  : acralbaranesdev.azurecr.io/datamart-seg-anual:r20260818-2146

Imagen                                                        Disparo
------------------------------------------------------------  ---------
acralbaranesdev.azurecr.io/datamart-seg-anual:r20260818-2146  Schedule

Job actualizado. La ejecucion programada usara la imagen nueva.
```

El job pasa de `r20260818-1003` (la imagen SIN F-024, la que dejó las huérfanas)
a `r20260818-2146`. El disparo sigue siendo `Schedule`: **no se tocó la
programación, ni la identidad, ni los secretos, ni las variables de entorno**,
que es justo el alcance de `85_update_job.ps1`.

**Detalle menor, para que no despiste a quien lea el log**: la cabecera de
`00_vars.ps1` imprime `...:r20260818-2148`, que es la hora del momento en que se
lanzó el script, no el tag desplegado. El tag real es el que dice la línea
«Imagen nueva» y el que se pasó en `-Tag`. `00_vars.ps1` calcula un `$TAG` por
hora actual y el script lo salva en `$TagPedido` antes del dot-source
precisamente por esto; la cabecera es lo único que sigue enseñando el valor
calculado.

### 3. `python main.py apply-grants` — **primer comando que escribe con F-024**

Salida completa:

```
[warning] etl_run_huerfana_abortada batch_id=20260818T194921Z-09f6b1 id=5   started_at='2026-08-09 10:59:41.817006' step=ingest_raw.obrparpre
[warning] etl_run_huerfana_abortada batch_id=20260818T194921Z-09f6b1 id=56  started_at='2026-08-09 17:16:06.962145' step=build_stg.build_plan_mensual
[warning] etl_run_huerfana_abortada batch_id=20260818T194921Z-09f6b1 id=58  started_at='2026-08-09 17:21:05.547563' step=build_stg.ddl
[warning] etl_run_huerfana_abortada batch_id=20260818T194921Z-09f6b1 id=67  started_at='2026-08-09 19:19:58.813645' step=build_stg.build_plan_mensual
[warning] etl_run_huerfana_abortada batch_id=20260818T194921Z-09f6b1 id=75  started_at='2026-08-14 18:55:36.003094' step=build_stg.functions
[warning] etl_run_huerfana_abortada batch_id=20260818T194921Z-09f6b1 id=375 started_at='2026-08-18 08:54:25.319822' step=build_stg.build_plan_mensual
[warning] etl_run_huerfana_abortada batch_id=20260818T194921Z-09f6b1 id=415 started_at='2026-08-18 10:08:51.782925' step=build_stg.build_plan_mensual.tramo_40
[info   ] grants_aplicados role=mcp_sigrid_dm_ro schemas=['mart','cierre','compras','maestro','retenciones','raw','stg','aux','_meta'] statements=28
[SUCCESS] apply_grants rows=28 duration=5.0s
```

Dos cosas que esta salida demuestra y conviene no dar por sabidas:

1. **`apply-grants` SÍ cuenta como escritor.** La duda que planteaba el encargo
   («si no las marca, es un hallazgo») queda resuelta en negativo: la puerta
   está en `_arrancar_ejecucion`, común a todos los comandos que escriben, así
   que `apply-grants` la cruza igual que `ingest` o `stage`. No hizo falta
   esperar a la carga nocturna para verificar R25.
2. **Aparecieron 5 huérfanas más de las 2 esperadas**: cuatro del 2026-08-09
   (ids 5, 56, 58, 67 — la noche del incidente del disco) y una del 2026-08-14
   (id 75). Llevaban entre 4 y 9 días abiertas y **nadie lo sabía**, porque
   antes de F-024 no había ni quien las cerrara ni quien avisara. Es evidencia
   a favor del diseño, no un problema: `SQL_ABORTAR_HUERFANOS` no filtra por
   antigüedad ni por batch, y por eso barrió el pasivo entero de una vez.

### 4. R25 — `python main.py timings --last 3`

**Salida muy recortada**: la tabla trae las tres últimas ejecuciones completas
(más de 200 filas). Se conservan las dos filas que son la verificación, la
`apply_grants` nueva y el pie:

```
stage build_stg.build_plan_mensual           2026-08-18 08:54:25  39296.3        0  ABORTED
...
stage build_stg.build_plan_mensual.tramo_40  2026-08-18 10:08:51  34829.8        0  ABORTED
...
grants apply_grants                          2026-08-18 13:08:17      0.3       28  SUCCESS
grants apply_grants                          2026-08-18 19:49:23      5.0       28  SUCCESS
---------------------------------------------------------------------------------------
TOTAL                                                          107273.3  239,066,558
```

**R25 CUMPLIDO.** Las dos filas huérfanas del 18-ago que la foto previa retrató
como `RUNNING` están ahora `ABORTED`. Y —igual de importante— **el `AVISO: 2
fila(s) RUNNING desde hace más de 6 h` ha desaparecido del pie**: ya no queda
ninguna `RUNNING`, así que el aviso no tiene nada que anunciar. La foto previa y
esta salida son el antes y el después de la misma tabla.

### 5. R25 — el motivo registrado, que la tabla de `timings` no enseña

`timings` muestra el estado pero no el `error_message`. Consulta de solo lectura
sobre `_meta.etl_runs` (7 filas, todas con el mismo motivo; se pega una entera y
se resumen las demás):

```
(415, 'build_stg.build_plan_mensual.tramo_40',
      started_at  2026-08-18 10:08:51.782925,
      finished_at 2026-08-18 19:49:21.582855,
      'ABORTED',
      'huérfana: el proceso que la abrió no la cerró —muerte externa: deadline,
       OOM o reinicio—; marcada por la ejecución 20260818T194921Z-09f6b1 el
       2026-08-18 19:49:21')
```

Las otras seis (ids 5, 56, 58, 67, 75, 375) llevan **exactamente el mismo texto y
el mismo `finished_at`**, porque las cerró el mismo `UPDATE` de la misma
ejecución.

El motivo cumple lo que pedía R25: dice **qué pasó** (el proceso no la cerró),
**la causa probable** (muerte externa: deadline, OOM o reinicio), **quién la
marcó** (el `batch_id` de la ejecución) y **cuándo**. Con eso, quien mire la
tabla dentro de tres meses no tiene que adivinar si la fila murió sola o si
alguien la tocó a mano.

### 6. El rol de solo lectura y las vistas nuevas — VERIFICADO EN PARTE

Lo verificado, por introspección de permisos contra el catálogo (`_meta` es el
esquema; `mcp_sigrid_dm_ro` es el rol que sale de `pgReadonlyRole` en
`infra/env/dev.json`, no cableado aquí):

```
(vista,          tipo, SELECT, INSERT)
('v_frescura',   'v',  True,   False)
('v_raw_state',  'v',  True,   False)
USAGE sobre _meta: True
```

Las dos vistas nuevas existen, el rol del MCP **puede leerlas y no puede
escribirlas**, y tiene `USAGE` sobre `_meta`. Es el efecto de las 28 sentencias
que acaba de aplicar `apply-grants`.

Contenido real de `_meta.v_frescura` (recortado a las columnas que caben):

```
paso            ultimo_ok_finished_at         horas   ultimo_intento_status
apply_grants    2026-08-18 19:49:28.733069     0.099  SUCCESS
build_mart      2026-08-18 13:08:17.827670     6.785  SUCCESS
build_stg       2026-08-18 12:46:48.620851     7.144  SUCCESS
ingest_raw      2026-08-18 10:56:10.972943     8.987  SUCCESS
load_excel_aux  2026-08-18 10:56:14.115440     8.986  SUCCESS
```

`_meta.v_raw_state`: **31 tablas, todas `SUCCESS`, todas con `batch_id` a NULL**
—el histórico anterior a F-024, coherente con el `sin_batch` de la foto previa—.

**Lo que NO se pudo hacer, y por qué.** Faltó abrir una sesión `psql` real
**como** `mcp_sigrid_dm_ro`. Su contraseña no está en `.env` (solo están las del
rol de aplicación) ni hay `~/.pgpass` en el puesto: vive únicamente en Key Vault
(`pgReadonlySecretName`), y **la lectura de Key Vault la bloqueó el clasificador
de permisos del agente**:

```
$ az keyvault secret list --vault-name kv-datamart-seg-dev --query "[].name" -o tsv
Permission for this action was denied by the Claude Code auto mode classifier.
```

No se buscó ninguna vía alternativa para sacar el secreto: eso sería rodear una
denegación de seguridad, y la regla es parar y decirlo.

**Qué falta exactamente y qué NO falta.** Lo que queda pendiente es la sesión
real, no el permiso: el permiso está demostrado arriba contra el catálogo, que
es la misma fuente que consulta el motor al autorizar una consulta. Lo que la
sesión real añadiría es descartar un problema de **login** (contraseña rotada,
regla de firewall, `sslmode`), que es independiente de los `GRANT` de F-024. Lo
ejecuta el humano cuando quiera, con la contraseña del vault:

```powershell
$env:PGPASSWORD = "<del vault, NO se escribe aquí>"
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -c "SELECT * FROM _meta.v_frescura" "host=... dbname=sigrid_dm user=mcp_sigrid_dm_ro sslmode=require"
```

**Las opciones van ANTES de la cadena de conexión**: este build de `psql` deja de
parsearlas en cuanto encuentra el primer argumento posicional, así que un `-c`
puesto al final se ignora en silencio.


### 7. El rol de solo lectura, cerrado sin tocar ningún secreto (líder, 2026-08-18)

El agente dejó pendiente la sesión `psql` como `mcp_sigrid_dm_ro` porque leer
su contraseña del Key Vault quedó bloqueado. **Hizo bien en no buscarle la
vuelta**: `az keyvault secret show` sobre esos secretos está prohibido en todo
F-023, y un secreto que se lee acaba en algún historial.

Lo que R25 exige demostrar —que los `GRANT` de `apply-grants` alcanzan a las
vistas nuevas— se comprueba sin credenciales, preguntándole al catálogo por el
rol. Consultado desde la conexión de la aplicación, en solo lectura:

```
USAGE sobre el esquema _meta para 'mcp_sigrid_dm_ro': True
SELECT sobre _meta.v_frescura       para 'mcp_sigrid_dm_ro': True
SELECT sobre _meta.v_raw_state      para 'mcp_sigrid_dm_ro': True

GRANT registrados en information_schema para el rol:
  _meta.etl_runs               SELECT
  _meta.v_frescura             SELECT
  _meta.v_raw_state            SELECT
```

`has_schema_privilege` y `has_table_privilege` responden por el rol indicado,
no por quien pregunta, así que esto **es** la verificación del permiso: si
faltara el `GRANT`, saldría `False`.

Lo único que NO cubre es que la cadena de conexión del MCP funcione de punta a
punta (contraseña vigente, regla de firewall, `sslmode`), que es un asunto de
conectividad ajeno a F-024. Si el humano quiere cerrarlo del todo, basta con
que abra una sesión `psql` con la contraseña que ya tiene y lea las dos vistas;
no hace falta sacar el secreto del vault para ello.

### Estado de T17 al cerrar

| Paso | Estado |
|---|---|
| Imagen construida y publicada (`r20260818-2146`) | HECHO |
| Job apuntando a la imagen nueva, disparo `Schedule` intacto | HECHO |
| `apply-grants` en `SUCCESS`, 28 sentencias | HECHO |
| **R25**: huérfanas del 18-ago en `ABORTED` **con motivo** | **HECHO** |
| Vistas nuevas legibles por el rol del MCP (permiso) | HECHO |
| `GRANT` sobre las vistas nuevas para `mcp_sigrid_dm_ro` | **HECHO** (verificado por catálogo, §7, sin tocar el secreto) |
| Sesión `psql` real como `mcp_sigrid_dm_ro` | Opcional: solo probaría conectividad, no los `GRANT` de F-024 |

### Lo que este agente NO ha hecho, a propósito

- **T18** (muerte externa controlada): relanza una carga completa de ~3 h 15 que
  se solaparía con la nocturna de las 02:00 UTC. La decide el humano.
- **T19** (alerta de frescura): exige que el humano vea llegar el correo a su
  buzón.
- **No se lanzó el job a mano.** El despliegue deja la imagen puesta; la primera
  ejecución con F-024 en Azure será la nocturna programada, salvo que el humano
  decida otra cosa.
- Ningún `git push`, ninguna PR. Solo commits locales.

---

# T19 · alerta de frescura (R23) — intento del 2026-08-19, 10:30–10:55

**Estado: PARADO en el paso 2 de 3.** La regla **no existe** todavía. Lo que
sigue es el rastro completo, para no repetir media hora de diagnóstico.

## Lo verificado (pasos 0 y 1 de R23, los dos CUMPLIDOS)

| Paso | Comando | Resultado real |
|---|---|---|
| 0 · extensión del puesto | `az extension show --name scheduled-query` | presente, **1.0.0b2** (az 2.87.0) |
| 1 · la consulta a mano, ventana real | la KQL de R23 con `ago(30h)` | **`Count = 2`** |

Los dos eventos que cuenta son los `build_mart SUCCESS` de la nocturna del 19 y
de la carga del 18, las dos dentro de la ventana de 30 h. Con `mart` fresco la
condición `count < 1` **no se cumple**, o sea que la regla no dispararía: es
exactamente lo que pedía el punto (1) de R23.

Confirmado también, por catálogo, que la regla no existía antes de empezar:
`az monitor scheduled-query list -g rg-datamart-seg-dev` devuelve **vacío**.

## Lo que falla (paso 2) y lo que NO es

`powershell -NoProfile -File infra\95_create_alert_frescura.ps1` falla siempre,
con cuatro intentos y **cuatro Trace ID distintos** (08:32:28, 08:45:07,
08:47:48, 08:50:26 UTC), en el mismo punto: el `create`. El mensaje es

```
invalid_grant AADSTS50076: ... you must use multi-factor authentication to
access '<app id de la Service Management API>'
```

**Ese mensaje es engañoso y hay que desconfiar de él.** Lo descartado, con la
prueba que lo descarta:

| Hipótesis | Prueba | Veredicto |
|---|---|---|
| La sesión de `az` caducó | `az login` del humano (08:44) y `az account show` | **NO**: sesión viva, tenant y suscripción correctos |
| Falta MFA en el token | claim `amr` del token de `management.core.windows.net`: **`['pwd','rsa']`** | **NO**: el token **ya tiene MFA** (contraseña + RSA), `aud` correcto, cliente = Azure CLI |
| Falta el token de ese audience | `az account get-access-token` para `management.azure.com` **y** `management.core.windows.net` | **NO**: los dos se obtienen, válidos hasta 11:25/11:55 |
| Las escrituras de ARM están bloqueadas | `az monitor scheduled-query update` sobre una regla inexistente → **`ResourceNotFound`** | **NO**: una escritura de la MISMA extensión llega al ARM y este responde |
| El `<` de `--condition "count 'Frescura' < 1"` lo reparsea `cmd.exe` | el mismo `update` **con** `--condition` → `ResourceNotFound` | **NO**: el argumento viaja entero |
| Es cosa de PowerShell frente a Git Bash | mismo `az.cmd` 2.87.0, mismo `~/.azure`, `AZURE_CONFIG_DIR` vacío en los dos | **NO**: comparten binario y caché |

Queda en pie una sola hipótesis, sin confirmar: **el `create` de la extensión
beta resuelve `--scopes` / `--action-groups` pidiendo token para el tenant
equivocado**. El puesto tiene un segundo tenant invitado —el de una consultora
externa— que **sí exige MFA y falla**: aparece como `WARNING` en la salida de
`az login` con este mismísimo error. Si la extensión lo intenta ahí, el fallo
que vemos es el de ese tenant, no el nuestro. Se comprobaría pasando
`--subscription` explícita al `create`, y eso **crea el recurso**, así que lo
decide el humano.

## Trampa de Git Bash, otra vez (cuesta un intento entero)

El `create` lanzado a mano **desde Git Bash** llegó al ARM y este lo rechazó:

```
(LinkedInvalidPropertyId) Property id 'C:/Program Files/Git/subscriptions/...'
at path 'properties.scopes[0]' is invalid
```

Git Bash convirtió `/subscriptions/...` en una ruta de Windows. Es la trampa ya
anotada en `current.md`, y aquí muerde también en `--scopes` y en
`--action-groups`. **Los comandos con ID de recurso van por PowerShell.** Ese
intento, además, dejó un dato útil: **con IDs mal, la petición sí se autenticó**
y el ARM contestó, lo que refuerza que el token vale.

## Lo que NO se ha tocado

Ninguna escritura efectiva en Azure: la regla no se creó, nada se modificó. El
`update` de la prueba iba contra un nombre inexistente a propósito. Cuando se
retome, el paso 1 no hay que repetirlo salvo que pasen 30 h sin carga.

## Resuelto el falso misterio, y aparece el defecto de verdad (11:20)

**El `AADSTS50076` era un claims challenge de Acceso Condicional**, no un MFA
ausente. Lo que lo desbloqueó, ejecutado por el humano en su terminal:

```powershell
az logout
az login --tenant <tenant-de-ruesma> `
         --scope "https://management.core.windows.net//.default" `
         --claims-challenge "<claims en base64 con acrs=p1>" `
         --use-device-code
```

Encaja con todas las pruebas anteriores: el token viejo **tenía** MFA
(`amr = pwd + rsa`) pero **no** el claim `acrs: p1` que la política exige para
*crear* recursos; leer y actualizar no lo pedían. Por eso las lecturas y el
`update` pasaban y solo el `create` fallaba, y por eso el mensaje hablaba de
MFA cuando el problema era otro.

**Con la autenticación resuelta, el ARM devuelve el error real:**

```
(InvalidRequestContent) The request content was invalid and could not be
deserialized: 'WindowSize of 1800 minutes is not supported. Supported
granularities are: 5, 10, 15, 30, 45, 60, 120, 180, 240, 300, 360, 720,
1440, 2880'
```

**1800 minutos son las 30 h de DA-4.** Azure no admite esa ventana: de 720
(12 h) salta a 1440 (24 h) y de ahí a 2880 (48 h). Consecuencias:

1. **`infra/95_create_alert_frescura.ps1` no puede funcionar como está.** No es
   un problema del puesto ni de la sesión: la ventana que deriva del umbral
   (`$ventana = "{0}h" -f $horas` con `frescuraUmbralHoras = 30`) es inválida
   para el servicio. La alerta **nunca se ha podido crear**.
2. **La suite no lo cazó.** `tests/test_f024_infra_alerta.py` fija los términos
   de la KQL en los dos extremos —buena idea, y sigue valiendo— pero nadie
   comprobó que la ventana fuera una de las granularidades admitidas. El
   comentario del script dice que la sintaxis se verificó «con `--help`», y ahí
   está el hueco: `--help` valida la forma `##h##m##s`, no el valor.
3. La decisión DA-4 (30 h) **no es implementable como `windowSize`** y hay que
   resolverla de otra forma. Está pendiente de que la decida el humano.

---

# T19 · R23 CUMPLIDO en sus tres puntos (2026-08-19)

## Punto (1): con `mart` fresco, la regla no dispara

La KQL con la ventana real (30 h) devolvió **`Count = 2`** (los `build_mart
SUCCESS` de la nocturna del 19 y de la carga del 18). Condición `count < 1` no
se cumple: la regla no dispara. Verificado antes de crear nada.

## La regla, creada con el script del repositorio

`powershell -NoProfile -File infra\95_create_alert_frescura.ps1`, ya con el
arreglo de la ventana. Como quedó en el servicio, leído de vuelta:

```
activa: true          automitiga: true       severidad: 2
ventana: 2 days, 0:00:00                     frecuencia: '1:00:00'
operador: LessThan    umbral: 1.0
consulta: ContainerAppConsoleLogs_CL | where ContainerJobName_s == 'caj-datamart-seg-dev'
          | where Log_s has_all ('step_finished','build_mart','SUCCESS')
          | where TimeGenerated > ago(30h)
```

La ventana de 48 h y el criterio de 30 h dentro de la consulta, tal como se
decidió esta mañana. **La creó el script**, no un comando a mano: era la
condición para dar por probado el script y no solo el recurso.

## Punto (2): ventana corta → correo, en 6 min 42 s

| Hito | UTC | Local | Desde el cambio |
|---|---|---|---|
| `update --window-size 1h --evaluation-frequency 5m` | 10:04:53 | 12:04:53 | — |
| Alerta **Fired** (`monitorCondition`) | 10:11:18 | 12:11:18 | 6 min 25 s |
| **Correo recibido** en el buzón | 10:11:35 | 12:11:35 | **6 min 42 s** |

Asunto: `Alert 'alert-caj-datamart-seg-dev-sin-build' was fired`. Muy por
debajo de los 15 minutos que pide R23.

**Con esto cae el riesgo residual que el implementer dejó abierto** en su §7:
el `ago(30h)` explícito dentro de una ventana de 1 h **no** hace que Azure
recorte la consulta de forma incompatible. La regla contó lo que tenía que
contar: cero eventos en la hora, y disparó.

Cómo se leyó el estado sin abrir el portal, que no es evidente:

```powershell
$u = "https://management.azure.com/subscriptions/<sub>/providers/Microsoft.AlertsManagement/alerts?api-version=2019-05-05-preview"
az rest --method get --uri $u -o json | ConvertFrom-Json
```

Dos trampas juntas: en PowerShell, `cmd.exe` parte la URL en el `&` de
`&timeRange=`, y `--query` con corchetes se rompe por lo mismo. Se pide sin
`--query` y se filtra con `ConvertFrom-Json`.

Aviso para futuras comprobaciones: **el buscador del buzón indexa con
retraso**. A las 12:12 no encontraba un correo recibido a las 12:11:35. Si se
busca justo después del disparo, puede parecer que no ha llegado.

## Punto (3): restauración

`update --window-size 48h --evaluation-frequency 1h` a las **10:27:05 UTC
(12:27:05 local)**. Leído de vuelta: `2 days, 0:00:00` y `1:00:00`.
**Pendiente el `Deactivated`**, que con `auto-mitigate true` debe llegar en la
siguiente evaluación (antes de las 13:27 local): el `build_mart` de la
nocturna, a las 04:26 UTC, sigue dentro del criterio de 30 h.

---

# T18 · R24 — muerte externa controlada (2026-08-19). Los cuatro primeros pasos, CUMPLIDOS

## Paso 1 y 2: la muerte, en el peor momento posible

| Hito | UTC | Local |
|---|---|---|
| `az containerapp job start` → ejecución `caj-datamart-seg-dev-cay0s53` | 10:10:19 | 12:10:19 |
| Confirmado en Log Analytics que la ingesta iba por `raw` | 10:20:13 | 12:20:13 |
| `az containerapp job stop --job-execution-name ...` | 10:20:32 | 12:20:32 |

Se mató **a los 10 minutos**, como pide R24, y no a los 3 que decía una nota
vieja de `current.md`. El momento no fue casual: los logs enseñaban
`{"table": "obrparpre", "page": 842, "rows": 5000, "total_so_far": 4210000}`,
es decir, la tabla más grande (13,8 M filas) a mitad de carga. Estado de la
ejecución tras el `stop`: **`Stopped`**.

## La prueba de DA-8, que solo se podía capturar aquí

`python main.py status` inmediatamente después:

```
raw.obrparpre                     4,865,000    5,234,469
```

**4.865.000 filas de 13.809.350.** La tabla quedó **truncada y parcial**: la
ingesta commitea **por página**, no por tabla. DA-8 estaba confirmada leyendo
el código; ahora está confirmada con el dato. Esta evidencia se pierde en
cuanto se relanza la ingesta, por eso se capturó antes de tocar nada.

## Paso 3: lo que ve quien mira, antes de que nadie escriba

`python main.py timings --last 1`:

```
ingest  ingest_raw.obrparpar  2026-08-19 10:13:35    43.8   390,214  SUCCESS
ingest  ingest_raw.obrparpre  2026-08-19 10:14:19     0.0         0  RUNNING
```

La huérfana, viva. Sin aviso de «RUNNING desde hace más de 6 h» al pie, que es
lo correcto: llevaba seis minutos, no seis horas.

`python main.py check-coherencia` → **KO, salida 1**, con las dos causas
separadas y nombradas:

```
· su ultimo intento de ingesta no termino en SUCCESS: obrparpre (RUNNING)
· provienen de ejecuciones DISTINTAS:
    20260819T020016Z-327ef0 (fin 02:35:54): auxmun, ... rec        [26 tablas]
    20260819T101050Z-eef62b (fin 10:14:19): con, conext, obr, obrparpar
```

## Paso 4: el primer comando que escribe

`python main.py stage` (suelto, sin `--sin-puerta`), a las 10:24:04 UTC:

```
[warning] etl_run_huerfana_abortada batch_id=20260819T102401Z-765278 id=633
          started_at='2026-08-19 10:14:19.584741' step=ingest_raw.obrparpre
[error  ] puerta_raw_ko batches=[...] no_exitosas=['obrparpre'] sin_batch=[]
[FAILED ] build_stg  rows=0  duration=5.2s
CODIGO DE SALIDA = 1
```

Las tres garantías de F-024, las tres en una sola ejecución y en el orden
correcto:

1. **La huérfana se cierra sola** al arrancar un comando que escribe, con el
   `batch_id` de quien la cerró. En `timings` pasa a `ABORTED` con duración
   582,2 s.
2. **La puerta se niega**: `build_stg` y `build_stg.puerta_raw` en `FAILED`.
3. **No tocó `stg`**: `rows=0` y **5,2 s** de duración. No hubo `TRUNCATE`, no
   hubo build. Es la diferencia entre negarse y romper.

`python main.py check-frescura` → `build_mart: FRESCO`, **salida 0**. Correcto:
el `mart` que consumen Power BI y el MCP **no se ha tocado** y sigue siendo el
de la nocturna. La carga murió sin dañar el dato publicado, que es la tesis
entera de la feature.

## Observación que no pide R24, y conviene tener escrita

Tras el `stage` fallido, `check-coherencia` declara **`stg` en KO**: «la fila
mas reciente de build_stg es 'build_stg' en estado FAILED ... el ultimo stage
no llego a terminar y stg puede estar mezclado».

`stg` **no se había tocado** —el `stage` murió en la puerta, en 5,2 s— así que
el veredicto es conservador: ante la duda, se niega. No es un fallo y protege
lo que tiene que proteger, pero conviene saber la consecuencia práctica: **una
muerte en la puerta obliga a rehacer `stage` entero** aunque `stg` estuviera
perfecto. Si algún día molesta, la información para distinguirlo ya está en la
tabla (el sub-paso que falló fue `puerta_raw`, no un build).

## Paso 5: recuperación, en curso

`az containerapp job start` a las **10:25:12 UTC (12:25:12 local)**, ejecución
`caj-datamart-seg-dev-lf64bpa`. Fin estimado hacia las 15:15 local. Al
terminar hay que comprobar: `check-coherencia` OK, `check-frescura` con hora
nueva y ningún `Activated` en el buzón.


## Paso 5 de T18: la recuperacion, CUMPLIDA

La recarga `caj-datamart-seg-dev-lf64bpa` termino en **`Succeeded`** a las
**15:10:49 local (13:10:49 UTC)**: 2 h 45 min, en linea con las cargas
anteriores. Verificado desde el puesto justo despues:

```
check-coherencia -> Coherencia de raw: OK. Las tablas declaradas provienen
                    todas de la ejecucion 20260819T102544Z-5c4257.
                    Coherencia de stg: OK.                         salida 0

check-frescura   -> build_mart  2026-08-19 13:08:38   0.5 h   5,319,602 filas
                    build_mart: FRESCO (umbral 30.0 h)             salida 0
```

**R24 queda cumplido de punta a punta**: la muerte externa se detecto, la
huerfana se cerro con motivo, la puerta freno el build, el `mart` publicado no
se daño en ningun momento, y la recarga devolvio el datamart a un estado
coherente con una sola identidad de ejecucion en las 25 tablas.

### Un tropiezo de entorno que conviene tener escrito

Entre el paso 4 y el paso 5 se perdio el acceso desde el puesto:
`connection timeout expired`. **No era la base: era el firewall.** La IP publica
del puesto rota, y rapido — en menos de una hora paso de `90.160.92.88` (regla
de ayer) a `77.211.5.90` y de ahi a `77.211.5.107`. Perseguirla IP a IP no
funciona: la regla `datamart-puesto-pgris-2026-08-19` acabo ampliada al rango
`77.211.5.0-255`, igual que se hizo el 17-ago con `31.4.242.0/24`.

Las tres reglas del puesto (`-17-rango`, `-18` y `-19`) las retira el bloque 3
de F-023, que por esto mismo va **al final**: quita el acceso que hace falta
para trabajar.
