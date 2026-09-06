<!-- progress/current.md -->
# Estado actual · 2026-09-06 (domingo; sesión de correcciones del review de F-066)

> **PURGADO el 2026-09-06 (C2 del review de F-066).** Este fichero tenía 1.263
> líneas y arrastraba cinco sesiones cerradas —F-042 del 28-08, F-047, las fases
> 1 y 2 de F-052, la spec de F-025 y el «Estado» de tres días distintos—, más el
> encabezado de F-066 escrito dos veces. C2 pide que describa **solo la sesión
> activa**. Lo que se ha quitado no se ha perdido: vive en `progress/history.md`,
> en los informes `impl_*`/`review_*`/`incidencia_*` de `progress/` y en las
> specs. Lo que queda aquí es lo que sigue vivo: F-066 (en revisión), F-025 y
> F-052 (las dos `blocked`), el estado del servidor y las verificaciones
> `MANUAL` que esperan al humano.

## POR DONDE SE SIGUE EN LA PROXIMA SESION (leer esto primero)

**LA NOCTURNA PASA A LAS 00:00 UTC** (decidido por el humano el 2026-09-06 a
las 20:20 UTC; antes `0 2 * * *`). Cambiado en el job de Azure **y** en el
repositorio, que es donde se mentia: `infra/env/dev.json`, el test
`test_f003_r9_cron_del_entorno_dev_es_medianoche`, `docs/ARCHITECTURE.md` y
`azure-apps/datamart_seg_anual.md` (commit `3916ca6` alli). De paso se corrigio
otra divergencia: `dev.json` declaraba `replicaTimeoutSeconds` 18000 y Azure
tiene 25200 desde el 05-sep, cuando se subio a 7 h; ahora coinciden.

**LA NOCTURNA DE ESTA NOCHE (lunes 07, 00:00 UTC) ES LA PRIMERA ACOTADA**, y se
deja correr **con la imagen vieja `r20260905-1237` a proposito**: es la que da
T31b y T34 de F-025. Desplegar F-066 antes la contaminaria con un 26 % mas de
filas y la medicion no valdria ni para cerrar F-025 ni para F-065. Decidido con
el humano. El despliegue de F-066 va **despues**, para la nocturna del martes.

**Tres cosas esperan al humano, en este orden:**

1. **F-068, y corre prisa.** Comprobado a las 19:35 UTC contra Azure:
   `raw.emp` **ya esta ahi** con sus 1.352 filas y con `dni`, `tarseg`
   (Seguridad Social), `bancue`/`ban` (cuenta bancaria), `dir1` (domicilio),
   `tel` y `esigpas` (contraseña del portal); y `mcp_sigrid_dm_ro` tiene
   `SELECT` sobre ella. **No es un riesgo futuro: cualquier cuenta del tenant
   que consulte por el conector MCP puede leerla hoy.** No es un fallo de
   F-066 -el humano decidio traer `emp` entera, con el aviso delante- pero la
   consecuencia hay que decidirla: sacar `raw` de `PG_CONSUMPTION_SCHEMAS`,
   revocar el `SELECT` solo sobre esas dos tablas, o aceptarlo por escrito.
   `raw.res` no trae columnas de ese tipo.
2. **T13 de F-066**: construir y desplegar la imagen, y dejar correr la
   nocturna, que cargara las 8 tablas grandes (5,19 M filas) y **recargara
   `dcf`**, que es lo unico que crea sus columnas `pagtex`/`pagfor`. Requiere
   `infra/` y `az`: lo autoriza el humano. Detalle en `progress/impl_F-066.md`,
   seccion «Que necesita T13». Mejor decidir F-068 ANTES.
3. **F-025**, `blocked` a proposito, espera la nocturna acotada del **lunes
   07** para T31b y T34; con T31b en verde, reviewer y `done`. **OJO: la
   nocturna del lunes llevara la imagen que se despliegue en T13**, asi que si
   se despliega, esa nocturna hace las dos cosas a la vez.

**El servidor sigue en `Standard_B2s`** (temporal desde el 05-sep, 17:21 UTC).
La bajada a B1ms sigue pendiente, con fecha limite 2026-09-20 anotada en
`azure-apps/` para preguntar si se olvido. Al bajar, el saldo se resetea a 60.

## F-066 · IMPLEMENTADA HASTA T12 Y T15; T13 Y T14 ESPERAN AL HUMANO

**Encabezado único.** Este mismo título estaba escrito dos veces (líneas 32 y
42 del fichero viejo, hallazgo 4 del review); las dos secciones se han fundido
en esta.

**REVIEW RECHAZADO el 2026-09-06** (`progress/review_F-066.md`, 10 hallazgos,
4 bloqueantes) y **corregido esa misma noche**
(`progress/impl_F-066_correcciones.md`). El fondo lo dio por bueno el reviewer,
reejecutando él los 23 mutantes; lo que bloqueaba era que la herramienta
declaraba **inválida su propia campaña** porque un test aleatorio **de F-024**
rompía la línea base, más tres desajustes de papeleo. Lo hecho: se arregló el
test de F-024 —el defecto estaba en el test, no en el `batch_id`—, se repitió la
campaña entera, y se cerraron los hallazgos 2 a 7. Quedan sin hacer, fichadas
para el líder, las observaciones **8** (generalizar la puerta de dobles al
cliente de Sigrid y portarla a `arnes-base`) y **10** (F-044 y F-047 `done` sin
resumen en `history.md`, deuda previa).

**Las decisiones de la spec (DA-1 a DA-11) no se repiten aquí**: viven en
`specs/F-066-ingesta-raw-pendientes/design.md` §6 y en la ficha de
`harness/features.json`. Las tres que cerró el humano el 2026-09-06 a las 12:05
UTC: `emp` y `res` **enteras** (DNI, cuenta bancaria y domicilio incluidos, solo
11 exclusiones técnicas en `emp`), el histórico de estados a **F-067** como foto
diaria —Sigrid no lo guarda— con `conest` dentro de F-066, y `apu` entera con
`--full` más `apa`.

**T15 HECHA por el lider el 2026-09-06 a las 19:40 UTC**: los hallazgos de R22
estan en las fichas de F-055, F-056, F-057 y F-067 de `harness/features.json`,
y **nace F-068** con lo del MCP. Los cuatro hallazgos que cambian esas fichas:
`hmores` es donde estan las horas (F-057); `apu.fec` viene informada al 100 %,
lo que desmiente la ficha de F-056; la actividad del proveedor es
`conact`→`auxpronat` y no `act`, que esta vacia (F-055); y Sigrid no guarda
las fechas de cambio de estado, asi que F-067 las construira por foto diaria.

**Al día 2026-09-06, tarde.** T1 a T12 y T16 están hechas, con un commit por
tarea. La ingesta pasa de **31 a 56 tablas**; las 17 de menos de 100.000 filas
ya están en `raw` (136.536 filas), y las 8 grandes más la recarga de `dcf`
esperan a la primera nocturna. Informe completo en `progress/impl_F-066.md`,
mediciones en `specs/F-066-ingesta-raw-pendientes/mediciones.md`.

**Lo que NO se ha tocado, y por qué:** T13 construye y despliega la imagen en
Azure —eso lo autoriza el humano—, T14 depende de que esa nocturna haya
corrido, y T15 es del líder. No se ha ejecutado nada de `infra/` ni `az`.

**Dos cosas que conviene no perder:**

1. **`check-raw-recuentos` cazó un fallo real el día que nació**: el YAML tenía
   17 entradas duplicadas que la nocturna habría cargado dos veces cada noche.
   Ningún test lo veía porque todos leían la ingesta como un `dict`, que
   colapsa duplicados. Corregido, con dos comprobaciones nuevas.
2. **`tests/test_f024_dominio.py::test_f024_r1_batch_id_tiene_forma_y_es_unico`
   es aleatorio por construcción y falla el 0,8 % de las veces** (medido: 25
   fallos en 3.000 repeticiones; la paradoja del cumpleaños predice 0,741 %).
   Genera 500 `batch_id` con sufijo de 3 bytes y exige 500 distintos. Invalidó
   la campaña de mutación de esta feature al romper la línea base final. **Es
   de F-024 y no se ha tocado**; queda para el líder decidir quién lo arregla.

## F-066 · LAS VERIFICACIONES `MANUAL (humano)`, CON SU COMANDO EXACTO (C4)

Las cinco `MANUAL` de `tasks.md`, en el orden en que se ejecutan y con el
comando literal: no hace falta abrir la spec. Todo desde la raíz del
repositorio, con el `.env` que toque y el entorno virtual activado. Los
comandos de Python van igual en PowerShell y en bash; el de `az` está escrito
para **bash** (`date -u -d`), que es donde se midieron los créditos.

| MANUAL | tarea | estado |
|---|---|---|
| 1 · recuento local | T9 | **HECHA** el 2026-09-06: código 0 sobre las 17 tablas pequeñas |
| 2 · commit en `azure-apps` | T11 | **HECHA**: commit `a900682` en `../azure-apps` |
| 3 · tiempos de la nocturna | T13 | **PENDIENTE** — espera el despliegue, que autoriza el humano |
| 4 · créditos de la nocturna | T13 | **PENDIENTE** — misma nocturna |
| 5 · recuento y diccionario contra Azure | T14 | **PENDIENTE** — depende de la 3 y la 4 |

### MANUAL 1 · T9 · [HECHA] `raw` tiene las mismas filas que Sigrid

```powershell
python main.py check-raw-recuentos
```

Solo lectura. Sale con código 1 si alguna tabla difiere, falta en `raw` o no se
pudo medir. **El día que nació cazó un fallo real**: 17 entradas duplicadas en
`config/tables_sigrid.yaml` que la nocturna habría cargado dos veces cada noche.

### MANUAL 2 · T11 · [HECHA] El documento del ecosistema, actualizado

```powershell
git -C ../azure-apps log -1 --stat
```

Tiene que enseñar el commit que pone `datamart_seg_anual.md` en 56 tablas, con
las 25 nuevas, las descartadas por vacías, `dcf` recuperando `pagtex`/`pagfor` y
el aviso de datos personales en `raw.emp`/`raw.res`.

### MANUAL 3 · T13 · [PENDIENTE] Qué tarda la ingesta nueva (R19)

Después de desplegar la imagen y de que corra la primera nocturna con las 25
tablas. Da los segundos y las filas por tabla, que van a `mediciones.md` §3:

```powershell
python main.py timings
```

La referencia contra la que se compara está medida: `ingest_raw` el 2026-09-05
en B2s fueron **20.148.546 filas y 1.832 s**; lo nuevo son **+5.328.841 filas
(+26 %)**.

### MANUAL 4 · T13 · [PENDIENTE] Qué créditos se come esa nocturna (R20)

El saldo de créditos del servidor, **antes y después** de la nocturna. Va a la
tabla de F-065 con la columna del SKU (hoy `Standard_B2s`).

```bash
az monitor metrics list --resource psql-albaranes-rs9k2 --resource-group rg-albaranes-dev \
  --resource-type Microsoft.DBforPostgreSQL/flexibleServers \
  --metric cpu_credits_remaining --interval PT1M --aggregation Average \
  --start-time $(date -u -d '-50 minutes' +%Y-%m-%dT%H:%M:%SZ) -o tsv
```

**`--interval PT1M` no es un detalle**: con `PT15M` la API devuelve los primeros
puntos del rango y parece que la métrica lleva trece horas de retraso. No es
cierto, llega al minuto. Costó descubrirlo.

### MANUAL 5 · T14 · [PENDIENTE] Contra Azure, tras esa nocturna

Los dos, contra la base de Azure y no contra la local. El primero tiene que
salir con **código 0** y el segundo **sin objetos sin ficha**:

```powershell
python main.py check-raw-recuentos
python main.py check-diccionario
```

Hasta que estas tres pendientes estén hechas, **R19, R20 y R24 siguen
PENDIENTES** en `mediciones.md` §3 y §4, y F-066 no puede pasar a `done`.

**El diccionario del árbol está en 130 objetos, 822 columnas y 47 fichas de
consumo** (subió de 105/822/47 con las 25 fichas de `raw` que trae F-066, todas
sin columnas y ninguna de consumo; el diccionario pasa a la versión 14 al
publicarse). El commit de cierre del 04 se llevó por delante
esta frase y dejó `init.sh` en rojo: el test
`test_f006_los_recuentos_de_current_son_los_de_hoy` existe justo para que estos
recuentos no envejezcan en silencio. **Si vuelves a reescribir la cabecera de
este fichero, los tres números se quedan.**

## Estado del servidor · LOS 144 CRÉDITOS ERAN FALSOS (corregido el 2026-09-05)

`Standard_B1ms` Burstable, y este repositorio llevaba meses diciendo que el tope
eran **144 créditos**. **No lo es.** La tabla oficial de la serie Bv1 da para el
`B1ms`: **baseline 20 %** de 1 vCPU, **12 créditos/hora** con la CPU ociosa y
**288 de tope**. Y la métrica lo confirma: el servidor ha estado a **300 el
8-ago**, **277 el 15-ago** y 163 el 29-ago.

Consecuencia: cuando el saldo marca 57, **no estamos al 40 % del depósito sino
al 20 %**. Todas las cuentas de créditos anteriores al 05-sep están hechas sobre
un techo equivocado.

**Cómo se consulta el saldo de verdad**, que también costó descubrirlo: hay que
pedirlo con **`--interval PT1M`** y una ventana corta. Con `PT15M` la API
devuelve los primeros puntos del rango y parece que la métrica lleva 13 horas de
retraso; no es cierto, llega al minuto.

```bash
az monitor metrics list --resource psql-albaranes-rs9k2 --resource-group rg-albaranes-dev   --resource-type Microsoft.DBforPostgreSQL/flexibleServers   --metric cpu_credits_remaining --interval PT1M --aggregation Average   --start-time $(date -u -d '-50 minutes' +%Y-%m-%dT%H:%M:%SZ) -o tsv
```

**Historia del saldo.** El 02-sep llegaron a **cero** tras nuestras 12 h 48 de
reconstrucción manual y la nocturna murió en el tramo 6 de 60. Se recuperó solo:
60 el 04 a las 21:15 local, **78 a las 02:03 UTC del 05**. La nocturna fallida
del 05 (2 h 19, dos `ingest_raw` de 20 M filas) se comió **unos 40**: quedaban
**53 a las 09:03** y **57 a las 09:59**, subiendo ~4/h con la CPU al 12 %.

**Qué costaría tener más** (precios reales de Spain Central, EUR, 730 h/mes,
consultados el 05-sep en la API de tarifas de Azure):

| vía | qué da | coste |
|---|---|---|
| esperar | ~12 créditos/h con el servidor ocioso; lleno en ~19 h | 0 € |
| **B2s** permanente | 2 vCPU, 4 GB · 24 créditos/h, tope 576 · IOPS 1.280 | 49,86 €/mes frente a 12,48 → **+37,38 €/mes** |
| B2s solo de noche | lo mismo durante la ventana | ~**+12,3 €/mes** |
| General Purpose D2ds_v5 | 2 vCPU, 8 GB, **sin créditos** | 132,86 €/mes → **+120,38 €/mes** |

En Spain Central **solo existen B1ms y B2s** en Burstable: B2ms y superiores no
están disponibles, así que el salto siguiente es ya General Purpose. Y ojo con
escalar: **reinicia el servidor** —que es compartido con albaranes, partes,
remesas y el portal— y **probablemente resetea el saldo de créditos** (la tabla
oficial da 60 «initial credits» al B2s); eso habría que medirlo antes de fiarse.

## F-052 · SIGUE BLOQUEADA, y el motivo REAL no era el que se penso

Su unico pendiente es certificar `check-cobertura` en verde. Lanzado el 04 sobre
`stg` ya completa: **58 combinaciones miradas, 37 cubiertas** —antes decia CERO,
asi que **el guardian ya no miente**, que era el bloqueo de verdad— pero sale
**KO** con 20 obras invisibles y 294 filas huerfanas.

**Y eso tiene explicacion, comprobada:** el `check-cobertura` se lanzo desde la
rama de F-025, que **NO contiene los cinco commits de cierre de F-052**
(`ec516bd`..`fa2312c`, que viven solo en `feature/F-052-partidas-huerfanas`).
El fichero de excepciones de esta rama es el viejo: **10 entradas y con los
`tipo` sin corregir**. En la rama de F-052 estan las 23 y los tipos arreglados.

**Como se cierra F-052:** terminar F-025, volver a su rama, relanzar
`check-cobertura --timeout 900` **alli**, y si da codigo 0, al reviewer y a
`done`. **No se mezclan las dos ramas** sin decidirlo.

## F-025 · LAS MANUAL DE LA FASE 7, CON SU COMANDO EXACTO (C4)

**ESTADO DE LOS ONCE PASOS al 2026-09-05, 12:45 local.** Cada cabecera de abajo
lo lleva escrito; este es el resumen para no tener que recorrerlos:

| paso | tarea | estado |
|---|---|---|
| 3 | T35 · la alerta | **HECHO** 04-sep |
| 4 | T27 · huellas del ANTES | **HECHO** 04-sep |
| 6 | encender `PG_VENTANA_ACTIVA` | **HECHO** 05-sep 00:40 |
| 7 | T29 · primera reconstrucción | **HECHO** · `hamsh8o`, 4 h 52 en B2s |
| 8 | T30 · huellas del DESPUÉS | **HECHO 05-sep · KO explicado por el origen · DADA POR BUENA por el humano el 06** |
| 9 | T31 · la 0599 · T31b · frescura | **T31 HECHO** (2.624.793 / 1,79 %) · T31b espera la primera acotada (lunes 07) |
| 10 | T32 · los cinco `check-*` | **HECHO** · mismo veredicto que antes en los cinco |
| 1 | T1 · el peso real | **HECHO** · ahorro 59,2 % (umbral 40) |
| 2 | T2b · el coste de la firma | **HECHO** · barata 111 s, cara +186 s; implantarla es decisión del humano |
| 5 | T28 · `ventana-plan` en seco | **HECHO 05-sep** · 40 vivas / 328 congeladas / 552 sin filas |
| 11 | T33 bloat · T34 créditos | a la semana |

El orden de ejecución **no es el de la numeración**: es 8 → 9 → 10 → 1 → 2 → 5,
y el 11 a la semana.

**Para el humano.** Esto es el guion completo de lo que queda, en el orden en
que hay que hacerlo y con el comando literal de cada paso: no hace falta releer
la spec. Todo desde la raiz del repositorio, con el `.env` de produccion y el
entorno virtual activado. Los comandos van en **PowerShell**, que es la consola
de este puesto.

**PRECONDICION: YA SE CUMPLE desde el 2026-09-03.** Este parrafo decia que
`stg.plan_mensual` seguia truncada al 21,6 % por la averia del 02-sep, y **eso
dejo de ser cierto**: las nocturnas del 03 y del 04 corrieron enteras y la
dejaron en 29,7 M de filas. Comprobarlo igualmente antes de empezar:

```powershell
python main.py status-stg
python main.py check-coherencia
```

### Paso 1 · T1 · [PENDIENTE — REPETIR tras la reconstrucción] El peso real

Reparte el peso de `SQL_PESOS_PLAN_MENSUAL` entre las 40 obras vivas y las 880
congeladas. **Es caro**: barre `stg.presupuesto` (13,8 M filas) unido a
`raw.obrparpre`. Lanzarlo **fuera del horario de carga**.

```powershell
@'
import datetime, main
from config.settings import get_settings
from etl_sigrid.application.steps.build_stg_step import sello_vigente_del_repositorio
from etl_sigrid.domain.ventana import clasificar_obras, criterio_desde_reglas

s = get_settings(); pg = main._get_pg()
plan = clasificar_obras(
    pg.fetch_censo_de_obras(),
    criterio_desde_reglas(s.business_rules, s.postgres.ventana_meses),
    datetime.date.today(), sello_vigente_del_repositorio(s),
    completa=False, rescate=s.postgres.ventana_rescate)
pesos = pg.fetch_pesos_plan_mensual()          # <-- lo caro de T1
vivas = sum(pesos.get(d.obra_id, 0) for d in plan.reconstruir)
frias = sum(pesos.get(d.obra_id, 0) for d in plan.congelar)
print(f"obras vivas={len(plan.reconstruir)} peso={vivas:,}")
print(f"congeladas={len(plan.congelar)} peso={frias:,}")
print(f"AHORRO = {100*frias/(vivas+frias):.1f} %   (si baja del 40 %, PARAR)")
'@ | python -
```

**Criterio de parada de T1: si el ahorro es menor del 40 %, PARAR** y volver a
consultar antes de encender nada. La cota estimada de `mediciones.md` §3 es
73,3 %, pero es un proxy que no cubre los ambitos master (8 y 11).

La cifra se escribe en `mediciones.md` §3.

### Paso 2 · T2b · [PENDIENTE — NUNCA EJECUTADO] Cuanto cuesta la firma

Las dos variantes, cronometradas. La cara detoasta `planif` en 13,8 M de filas.
**Tambien fuera del horario de carga.**

```powershell
@'
import time, main
from etl_sigrid.infrastructure.postgres.postgres_client import (
    SQL_FIRMA_ORIGEN, SQL_FIRMA_ORIGEN_CON_PLANIF)

pg = main._get_pg()
for nombre, consulta in (("barata (sin planif)", SQL_FIRMA_ORIGEN),
                         ("cara (md5(planif))", SQL_FIRMA_ORIGEN_CON_PLANIF)):
    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '1800s'")
        t0 = time.perf_counter(); cur.execute(consulta); filas = cur.fetchall()
        print(f"{nombre}: {time.perf_counter()-t0:.1f} s, {len(filas)} obras")
'@ | python -
```

Si la cara resulta asumible, sustituye a `SQL_FIRMA_ORIGEN` (R20); si no, la
laguna se queda declarada y la cierra el domingo. Los segundos de cada variante
van a `mediciones.md` §6.

### Paso 3 · T35 · [HECHO el 2026-09-04] Desplegar la alerta

`check-ventana` **avisa y no tumba el job** (DA-5), asi que la alerta de fallo
no se dispara y esta regla es la **unica** via por la que el hallazgo llega a
una persona. Va **antes** de encender la ventana, no despues.

```powershell
az extension add --name scheduled-query          # una vez por puesto
powershell -NoProfile -File infra/97_create_alert_ventana.ps1

# El buzon vive en el grupo de accion, no en el .ps1 (R30 de F-052):
powershell -NoProfile -File infra/90_create_alert.ps1 -AlertEmail <buzon>
```

Comprobar que la consulta de la regla ve el marcador, con el workspace de Log
Analytics:

```powershell
$ws = az monitor log-analytics workspace show -g <resourceGroup> -n <logAnalytics> --query customerId -o tsv
az monitor log-analytics query -w $ws --analytics-query "ContainerAppConsoleLogs_CL | where ContainerJobName_s == '<job>' | where Log_s contains '[F025-VENTANA-KO]' | count" -o table
```

**No esta verificada hasta que llegue un correo de verdad.**

### Paso 4 · T27 · [HECHO el 2026-09-04] Las CINCO huellas del ANTES

**Antes de reconstruir nada y sobre el `raw` vigente.** Solo lectura. Si se
capturan despues, ya no prueban nada.

```powershell
mkdir huellas -Force
python main.py huella-obras --out huellas/antes_stg.csv       --desde stg       --timeout 900
python main.py huella-obras --out huellas/antes_mart.csv      --desde mart      --timeout 900
python main.py huella-obras --out huellas/antes_dimension.csv --desde dimension --timeout 900
python main.py huella-obras --out huellas/antes_cierre.csv    --desde cierre    --timeout 900
python main.py huella-obras --out huellas/antes_plan_obra.csv --desde plan_obra --timeout 900
```

Guardar los cinco CSV **fuera de la base**; `huellas/` no se versiona.

### Paso 5 · T28 · [PENDIENTE] El plan, en seco, contra produccion

```powershell
python main.py ventana-plan
python main.py ventana-plan --detalle
```

**Tiene que decir 920 censadas, 40 a reconstruir y 880 congeladas.** Si no
cuadra con `mediciones.md` §2, PARAR: el criterio no esta viendo lo que se
midio. Ojo, con la ventana todavia apagada imprime `completa: True`; eso es
correcto y no es un fallo.

### Paso 6 · [HECHO el 2026-09-05 a las 00:40] Encender

Nace apagada (R5): nada de lo anterior cambia una sola cifra publicada. En
local, en `.env`:

```
PG_VENTANA_ACTIVA=true
```

En Azure, **el valor esta versionado** desde el 2026-09-04 (hallazgo 2 del
review): `infra/env/dev.json` declara `ventanaActiva`, `ventanaMeses`,
`ventanaDiaCompleta` y `ventanaRescate`, y `infra/80_create_job.ps1` los inyecta
como `PG_VENTANA_*`. Encenderla es **cambiar `"ventanaActiva": "true"` en
`dev.json`** y llevar ese valor al job.

**OJO, Y ESTO SE PROBO: sobre el job de produccion NO vale relanzar
`80_create_job.ps1`.** Ese script lanza excepcion si el job ya existe
(`80_create_job.ps1:85-87`: «el job ya existe. Para cambiarle la imagen usa
85_update_job.ps1»), que es exactamente el caso de hoy. El camino versionado
solo funciona **al crear el job de cero**. Sobre un job vivo, la unica via que
funciona hoy es fijarla a mano:

```
az containerapp job update -g rg-datamart-seg-dev -n caj-datamart-seg-dev --set-env-vars PG_VENTANA_ACTIVA=true
```

**OJO: `85_update_job.ps1` NO sirve para esto.** Solo cambia la imagen y dice
expresamente que no toca el entorno, asi que el despliegue habitual no llevara
el valor nuevo. Si no se quiere recrear el job, se fija a mano —pero entonces el
valor vuelve a vivir fuera del repositorio y desaparece la proxima vez que
alguien lo recree:

```powershell
az containerapp job update -g <resourceGroup> -n <job> --set-env-vars "PG_VENTANA_ACTIVA=true"
```

En cualquiera de los dos caminos, verificar despues que llego:

```powershell
az containerapp job show -g <resourceGroup> -n <job> --query "properties.template.containers[0].env[?name=='PG_VENTANA_ACTIVA']" -o table
```

### Paso 7 · T29 · [EN CURSO — kcb9n2r, lanzada 10:44 UTC] La primera reconstruccion

```powershell
python main.py stage
python main.py timings --last 1
```

Anotar duracion por tramo y ocupacion de disco. Para forzar la completa —lo que
hace sola la noche del domingo—: `python main.py stage --reconstruir-todo`.

### Paso 8 · T30 · [PENDIENTE — ES LO SIGUIENTE] Las cinco huellas del DESPUES

**SIN `--obras-esperadas`.** Tolerancia cero: **una sola diferencia PARA la
feature.**

```powershell
python main.py huella-obras --out huellas/despues_stg.csv       --desde stg       --timeout 900
python main.py huella-obras --out huellas/despues_mart.csv      --desde mart      --timeout 900
python main.py huella-obras --out huellas/despues_dimension.csv --desde dimension --timeout 900
python main.py huella-obras --out huellas/despues_cierre.csv    --desde cierre    --timeout 900
python main.py huella-obras --out huellas/despues_plan_obra.csv --desde plan_obra --timeout 900

python main.py comparar-huellas huellas/antes_stg.csv       huellas/despues_stg.csv
python main.py comparar-huellas huellas/antes_mart.csv      huellas/despues_mart.csv
python main.py comparar-huellas huellas/antes_dimension.csv huellas/despues_dimension.csv
python main.py comparar-huellas huellas/antes_cierre.csv    huellas/despues_cierre.csv
python main.py comparar-huellas huellas/antes_plan_obra.csv huellas/despues_plan_obra.csv
```

Las cinco tienen que salir con **codigo 0 y cero diferencias**.

### Paso 9 · T31 y T31b · [PENDIENTE] La 0599 y la frescura por obra

```powershell
python main.py inspect-cierre --codigo 0599
```

Tiene que seguir dando **DIRECTOS 2.624.793 €** y margen **1,8 %**. Y que las
40 vivas se rehicieron mientras las 880 conservan su `_built_at` anterior:

```sql
SELECT congelada, count(*), min(construido_at), max(construido_at)
FROM _meta.v_frescura_obra
GROUP BY congelada;
```

### Paso 10 · T32 · [PENDIENTE] Los guardianes

```powershell
python main.py check-unicidad --timeout 300
python main.py check-cierres --timeout 900
python main.py check-cobertura
python main.py check-declarados
python main.py check-ventana
```

### Paso 11 · T33 y T34 · [PENDIENTE — a la semana]

Repetir la medicion de bloat de `mediciones.md` §7 sobre `pg_class` y
`pg_stat_user_tables` y compararla con T2; **si crece de forma sostenida, abrir
la feature de particionado**. Y mirar en el portal de Azure los creditos de CPU
restantes al terminar la nocturna (R29): **tienen que quedar por encima de 0**.
