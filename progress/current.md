<!-- progress/current.md -->
# Estado actual · 2026-09-06 (domingo, ~11:30 UTC)

## F-066: SPEC ESCRITA, PENDIENTE DE APROBACIÓN DEL HUMANO (PARADA 1)

`spec-author` ha dejado `specs/F-066-ingesta-raw-pendientes/` (requirements,
design, tasks) con el alcance ampliado a las 10:40 UTC (raw de COMPRAS por el
MCP). Todo lo afirmado sobre Sigrid se **midió** ese día con lecturas por
`sigrid-api` (`design.md` §1); ningún dato personal se imprimió ni se guardó.

**Lo que cambia respecto a la ficha, y el humano tiene que validar:**

1. **`hmores` entra** (328.760 filas): las horas están ahí, no en `hmo` (DA-4).
2. **Las seis de «proveedor» de la ficha están VACÍAS en Sigrid** (`PFfir`,
   `auxfam`, `act`, `auxacttip`, `actent`, `actseg`: 0 filas). No se
   ingieren. La actividad del proveedor real es **`conact` → `auxpronat`**
   (7.090 filas, 4.773 proveedores, 409 naturalezas; `homolo` = 0 en todas)
   más `prvcer` (certificados). F-055 se replantea sobre eso (DA-3).
3. **Firmas = `confir` + `deffir`** (69.993): fechas de firma por rol solo
   para comparativos; facturas sin fecha; contratos no pasan por ahí (DA-6).
4. **Sigrid NO guarda el histórico de estados de contratos ni facturas**
   (`concam` no audita `est`; `ctr` no tiene fechas de circuito; `PFID`
   vacío). La carencia (1) de Compras no se resuelve con ingesta: F-067
   tendrá que construir una foto diaria en el datamart (DA-7). `concam` no se
   ingiere.
5. **`apu` entera y `--full`** (DA-1): no tiene `tiemod`, incremental
   imposible; emp=1 es el 89,9 %. Y `apu.fec` viene informada al 100 %,
   contra lo que dice la ficha de F-056.
6. **`apa` entra** (709 k, desglose analítico; DA-2).
7. **Datos personales**: 72 columnas fuera en `emp`, 7 en `res`; nombre y
   apellidos se quedan y se declaran. **Aviso**: `mcp_sigrid_dm_ro` lee
   `raw` entero (decisión del 2026-08-08), así que `raw.emp` será legible por
   el MCP; revocar es decisión del humano (DA-5). Además 388 recursos ya
   llevan un `cod` con forma de DNI en `raw.con`.
8. **`dcf` recupera `pagtex`/`pagfor`** (condiciones de pago, DA-9) y entran
   `dco`/`dcopro`/`dcorec`/`dnc`/`dncpro` (ofertas y necesidades, DA-10),
   `ctrrec`/`dcfrec`/`dcarec` (retención), `auxpag`/`auxefp`.
9. Total: **24 tablas nuevas, +5,33 M filas (+26 %), ~+8-13 min** sobre los
   30 de `ingest_raw` en B2s. `raw` pasa de 31 a 55 tablas y fichas.
10. Nuevo comando **`check-raw-recuentos`** (dominio puro + CLI, solo
    lectura) para el criterio «recuento igual al de Sigrid» (DA-11); es el
    único Python nuevo y el que lleva la campaña de mutación de rigor crítico.

Los sondeos están en el scratchpad de la sesión (no versionados); las cifras
que importan están copiadas en `design.md` §1.

# Estado a las 07:45 UTC del domingo 06 (sesión anterior)

## F-025 BLOQUEADA A PROPÓSITO; LO SIGUIENTE ES F-066, LA INGESTA DE LOS RAW QUE FALTAN

**Decidido por el humano el domingo 06 a las 07:40 UTC.** F-025 pasa a
`blocked` mientras espera las nocturnas acotadas (T31b y T34 con la del lunes
07, T33 a la semana); cuando T31b esté en verde, reviewer y `done`. No es una
avería.

**El backlog se ha reordenado** (commit de esta mañana): nace **F-066**, una
sola feature de INGESTA que trae de una vez todos los raw que F-055, F-056 y
F-057 llevaban dentro (personal: `res`, `emp`, `hmo`; contabilidad: `apu`,
`asi`, `cua`, `apa`?, `con` tip=16; proveedor: `PFfir`, `auxfam`, `act`,
`auxacttip`, `actent`, `actseg`). Esas tres quedan como features de **mart**
sobre esos raw, en el orden F-057 → F-056 → F-055. Y las 45 vivas tienen ahora
**prioridad única** (1 a 45), conservando el orden relativo que tenían.
Palabras del humano: «una primera ficha de ingesta de esas 3 features, y luego
esas tres features serían solo reconstruir los mart de cada una».

**F-066 en `spec_ready` desde el domingo 06 a las 11:40 UTC** (spec en
`specs/F-066-ingesta-raw-pendientes/`, ampliada con lo que Compras pidió; ver
F-067). **Espera la aprobación del humano**: las once decisiones de
`design.md` §6 (DA-1 a DA-11) están enseñadas en el chat; las que necesitan
al humano son la lectura de `raw.emp` por el MCP (DA-5) y que Sigrid no
guarda histórico de estados de contratos ni facturas (DA-7, afecta a lo que
se le puede prometer a Compras). Los tests de F-025 que fallaban los domingos
están arreglados (`5fedc48`, informe en `progress/impl_F-025_tests_domingo.md`).

**Las tres decisiones del humano sobre la spec (12:05 UTC)**: `emp`/`res`
enteras, sin excluir DNI ni datos personales; el histórico de estados a F-067
como foto diaria (verificado por el líder contra Sigrid: `concam` nunca
audita `est`, `confir` no tiene contratos, `conest` define los siete estados
del contrato; F-066 añade `conest`); `apu` entera y `apa` dentro. El
`spec-author` revisa la spec con eso; al entregar, F-066 pasa a `in_progress`
y arranca el `implementer`.

**Por dónde se sigue**: F-066 por el flujo SDD, `spec-author` primero. Lo que
la spec tiene que decidir está en la ficha: cómo se trae `apu` (2,15 M, la
mayor jamás traída), qué pasa con el DNI de `emp`/`res` en `raw`, y la
medición de la ingesta nueva con su SKU. El servidor sigue en B2s.

# Estado a las 16:31 UTC del sábado 05 (sesión anterior)

## EL SERVIDOR ESTÁ EN B2s DESDE LAS 17:21 UTC, Y LA RECONSTRUCCIÓN VA POR SEGUNDA VEZ (`hamsh8o`)

**El giro del sábado por la tarde.** Con la hucha a **3 créditos** a las 16:24
UTC y todo el trabajo de la fase 7 parado hasta el domingo, el humano preguntó
si se podía **subir el SKU unos días, procesar lo pendiente y bajar cuando esté
estable**. Sí, y lo autorizó. Lo comprobado antes de tocar nada: en Spain
Central el único Burstable por encima del `B1ms` es el **`Standard_B2s`** (2
vCPU, 4 GB, 1.280 IOPS, 576 créditos de tope, 24/h); lo decisivo no es la hucha
doble sino que **su base con la hucha vacía es 0,8 vCPU**, cuatro veces el
B1ms estrangulado. Coste +37,38 €/mes, facturado por horas: ~1,23 €/día.

**Ejecutado por el líder con autorización expresa** (saldo de partida 6
créditos a las 17:14):

```
az postgres flexible-server update -g rg-albaranes-dev -n psql-albaranes-rs9k2 --sku-name Standard_B2s --tier Burstable --yes
```

Ojo: sin `--yes` el CLI pide confirmación interactiva del reinicio y muere con
`EOF when reading a line` desde un agente. Reinicio de **7 minutos**
(17:21 → 17:28), el servidor volvió `Ready`, `check-pg` responde y las 17 apps
del servidor compartido siguen `Running`. **Y el saldo se resetea al escalar,
medido**: 6 créditos a las 17:19, **60 a las 17:28**, los «initial credits» de
la tabla oficial. Hoy juega a favor; al bajar a B1ms pasará lo mismo, así que
la bajada no debe hacerse justo antes de una nocturna completa. Anotado en `azure-apps/`
(`datamart_seg_anual.md` y `red_postgresql_compartido.md`, commit `c59eee8`)
con fecha límite **2026-09-20** para preguntar si la bajada se olvidó. La ficha
de F-065 lleva el giro.

**T29 relanzada a las 17:30 UTC como `caj-datamart-seg-dev-hamsh8o`**, sin
tocar nada más del job: imagen `r20260905-1237`, `PG_VENTANA_ACTIVA=true`,
timeout 7 h, cron aún en `0 2 1 1 *`. Estado con el comando de más abajo; logs
con `az containerapp job logs show ... --execution caj-datamart-seg-dev-hamsh8o --container caj-datamart-seg-dev --tail 50`.

**`hamsh8o` TERMINÓ EN `Succeeded` A LAS 22:22 UTC, 4 h 52. T29 CUMPLIDA.**
920 obras en `_meta.obra_build`, `stg.plan_mensual` completa (29,77 M),
`check-ventana` OK, `check-cobertura` en el KO conocido de F-052, diccionario
en versión 13. Créditos: 60 → mínimo **6** al acabar `plan_mensual` → 14 al
terminar; `mart` y `cierre` no gastan (E/S). Detalle, curva y tabla de pasos en
`mediciones.md`, intento 3 de T29. **El cron sigue apagado** (`0 2 1 1 *`):
la nocturna del domingo 06 NO va a correr sola; se reactiva al cerrar la fase 7
o, si el domingo no se llega, a mano al final del día.

**T28 y T30 HECHAS esa misma noche (22:44-23:05 UTC), Y T30 PIDE UNA
DECISIÓN DEL HUMANO.** Las cinco huellas del DESPUÉS capturadas (con el B2s,
segundos cada una salvo `stg` 9 min); las cinco comparaciones **KO a
tolerancia cero**, y **todas las diferencias son de Sigrid, no del ETL**:
once obras vivas con actividad de agosto, la versión 11 del master de la 0712
creada en Sigrid el 04-sep después del ANTES, `stg` = `raw` fila a fila en
todas ellas, y ninguna obra congelada se mueve. Pruebas y veredicto en
`mediciones.md` («T30 · Las cinco huellas del DESPUÉS»). **Propuesta**: T30
no concluyente por diseño (dos `raw` distintos, y la primera pasada no
congela nada); repetirla sobre el mismo `raw` con un build acotado sin
ingesta. **DECIDIDO el 06 a la 01:10 local: el humano la da por buena** («parecen cambios de obras vivas, es normal»). T28: 920 censadas, **40 vivas y 328
congeladas de las 368 con `plan_mensual`**; las 552 sin filas se rehacen por
R18 y 319 de ellas tienen presupuesto (T1 dirá cuánto pesa). Ojo: el `.env`
del puesto NO lleva `PG_VENTANA_ACTIVA`; T28 se lanzó con la variable en la
shell. Las huellas ANTES/DESPUÉS están en `huellas/` (no versionadas).

**FASE 7 CASI CERRADA (06-sep, 00:15 UTC).** Hechas T27, T28, T29, T30 (dada
por buena), T31, T32, T35, T1 y T2b. **Quedan T31b, T33 y T34, que necesitan
nocturnas acotadas**: la primera acotada será la del **lunes 07** (el domingo
toca completa por R25), así que **hay que reactivar el cron** (`0 2 * * *`)
para que corran; la del domingo 06 a las 02:00 UTC sería una completa más en
B2s (~4 h 52, como `hamsh8o`). Con T31b en verde: reviewer contra
`CHECKPOINTS.md` y `done`. Cifras de todo en `mediciones.md`, Fase 7.

**CRON REACTIVADO el domingo 06 a las 07:31 UTC** («sí, reactívalo ya»):
`0 2 * * *`, imagen `r20260905-1237`, 18 variables, `PG_VENTANA_ACTIVA=true`
comprobado con `show` después del `update` (ojo: la salida del propio `update`
enseña `env` vacío y asusta; no es real). La nocturna del domingo 06 **no
corrió** (el cron estaba apagado a las 02:00). Calendario que sale de R25:
**lunes 07, 02:00 UTC: primera acotada** (40 vivas + 552 sin filas de peso
nulo; da T31b y T34) · martes a sábado, acotadas · **domingo 13, completa**.
Aviso: la alerta de frescura (30 h sin `build_mart`) puede saltar el lunes
hacia las 03:30 UTC porque el último `build_mart` fue el sábado a las 21:27 y
la acotada del lunes no habrá terminado; si salta, es por el domingo sin
nocturna, no por un fallo.

**El plan de los próximos días, aprobado por el humano:**

1. ~~Hoy: `hamsh8o` termina~~ **HECHO, `Succeeded` a las 22:22**. T29
   cumplida; el cron NO se reactiva hasta cerrar la fase 7.
2. ~~Domingo: fase 7~~ **HECHA en la madrugada del 05 al 06** salvo T31b/T33/T34; **cron reactivado el 06 a las 07:31 UTC**. Reviewer y cierre cuando T31b esté en verde (lunes 07).
3. Lunes: F-052 en su rama, `check-cobertura --timeout 900` sobre `stg`
   completa.
4. Unos días de nocturnas acotadas en B2s, anotando créditos antes y después
   de cada una (tabla de F-065, con columna SKU).
5. **Bajar a B1ms** en hora de poco uso (segundo reinicio; lo ejecuta el humano
   o el líder con autorización expresa para ese comando). A partir de ahí, la
   semana de medición de F-065 sobre el régimen estable, que es la que responde
   a la pregunta real.

Lo que sigue debajo es el estado tal como quedó a las 15:50; sigue siendo
válido salvo lo que esta sección corrige (la espera al domingo ya no aplica).

# Estado a las 15:50 UTC (antes del giro)

## Comprobado al abrir la sesión del 2026-09-05

**El paso 4 no se había ejecutado al abrir la sesión:** `main` seguía en
`cd18e09` y el job de Azure apuntaba a **`r20260902-0019`** sin
`PG_VENTANA_ACTIVA`, o sea que la nocturna del 04 corrió con la imagen del
02-sep y sin F-025. **Se ejecutó esa misma madrugada**, ver la sección
siguiente.

**El diccionario del árbol está en 105 objetos, 822 columnas y 47 fichas de
consumo** (subió de 103/798/46 con las dos fichas de F-025; el diccionario pasa
a la versión 13 al publicarse). El commit de cierre del 04 se llevó por delante
esta frase y dejó `init.sh` en rojo: el test
`test_f006_los_recuentos_de_current_son_los_de_hoy` existe justo para que estos
recuentos no envejezcan en silencio. **Si vuelves a reescribir la cabecera de
este fichero, los tres números se quedan.**

## LA NOCTURNA DEL 05 FALLÓ, Y YA ESTÁ ARREGLADA (2026-09-05, tarde)

La primera nocturna con F-025 (`caj-datamart-seg-dev-29809560`, imagen correcta
`r20260905-0034`) murió **dos veces** con
`AttributeError: 'PostgresClient' object has no attribute 'fetch_filas_por_obra'`
en `build_stg_step.py:628`. Diagnóstico completo, con los logs y el estado de la
base: `progress/incidencia_F-025_nocturna_20260905.md`.

**La base NO está rota**: el fallo cae *después* de construir el tramo, en el
registro de la traza. `stg` conserva sus cifras de siempre; lo que no hay es
refresco, y `_meta.obra_build` sigue vacía.

**Arreglado en tres commits** (`a9e51ed`, `202f0e4`, `481f6ca`), informe en
`progress/impl_F-025_metodo_ausente.md`:

1. `fetch_filas_por_obra` implementado en `PostgresClient` —nunca se escribió;
   solo existía en tres dobles de test, de ahí los 3.308 tests en verde—.
2. `tests/test_f025_contrato_cliente.py`: cruza cada doble con el original y
   cada llamada de producción con la clase, por barrido `ast` y sin lista a
   mano. Barrido hecho: **no había más métodos fantasma**.
3. La lección en `CHECKPOINTS.md` (C4) y portada a `arnes-base` 1.7.9.

`bash harness/init.sh` **en verde**: 3.321 pasados, 134 saltados, cobertura
**91,9 %** de 640 líneas cambiadas (umbral 80, nivel crítico).

**LO SIGUIENTE, y lo decide el humano:** volver a construir la imagen, apuntar
el job y **relanzar la reconstrucción como job de Azure** (no desde el puesto).
Hasta que esa ejecución termine, **T29 sigue sin ejecutar y T30 —las huellas del
DESPUÉS— no se puede hacer**. Las cinco huellas del ANTES siguen válidas.

## POR DONDE SE SIGUE: el DOMINGO 06, con la hucha llena (sesión cerrada el sábado a las 15:50 UTC)

**La reconstrucción manual `kcb9n2r` MURIÓ por el `replicaTimeout` de 5 h**, no
por el código. **El arreglo del método funciona**: `build_presupuesto` terminó a
las 11:42 con 13.874.194 filas y pasó el registro en `_meta.obra_build`, justo
donde anoche reventaba. Lo que la mató fue **la hucha de créditos**: arrancó con
57, llegó a **1 antes de las 15:01** y Azure la capó al 20 % de CPU. Cada tramo
de `plan_mensual` pasó de ~2 min a **9-13 min**; iba por el **35/60** a las
15:36 cuando el timeout la cortó a las 15:44. Es el 02-sep calcado.

**Lo que se hizo al morir, con autorización del humano** («vamos con los 4
pasos»), todo comprobado contra Azure:

| | |
|---|---|
| 1 · reintento | `az containerapp job stop` sobre `kcb9n2r`: **nada en `Running`** |
| 2 · nocturna | cron a **`0 2 1 1 *`** (no dispara), como el 02-sep |
| 4a · timeout | `replicaTimeout` **18.000 → 25.200 s (7 h)** |
| sin tocar | imagen `r20260905-1237` · `PG_VENTANA_ACTIVA=true` · 18 variables |

**El estado de la base**: `stg.plan_mensual` a medias (tramo 35/60), como el
02-sep. La protección de F-024 impide construir `mart` sobre ese `stage`, así
que el datamart publicado sigue siendo el del día 4. `_meta.obra_build` **ya
tiene filas** (las de `presupuesto`); la nocturna siguiente decide por R18/R19
qué rehace.

### El domingo, en este orden

1. **Créditos.** Con 12/h desde las 15:45 del sábado, el tope (288) se alcanza
   hacia las **15:30 UTC del domingo**. Comprobar con `--interval PT1M` (comando
   en la sección de créditos); **no lanzar por debajo de ~250**: la de hoy
   demostró que 57 no dan ni para `plan_mensual`.
2. **Lanzar a mano**: `az containerapp job start -g rg-datamart-seg-dev -n caj-datamart-seg-dev`.
   Con la hucha llena y 7 h de tope debe caber (el día 4 fueron 4 h 50).
3. **Vigilar** con el comando de estado de más abajo; si `Failed`, la consulta
   de Log Analytics con `ContainerGroupName_s startswith '<ejecución>'`.
4. **Si termina bien**: T29 cumplida → fase 7 (T30 huellas del DESPUÉS con
   tolerancia cero, T31/T31b, T32, T1, T2b, T28). El guion con comando literal
   está en «LAS MANUAL DE LA FASE 7».
5. **Al final del domingo, reactivar la nocturna**:
   `az containerapp job update -g rg-datamart-seg-dev -n caj-datamart-seg-dev --cron-expression "0 2 * * *"`.
   Red de seguridad: la alerta de frescura salta a las 30 h sin `build_mart`.

**La decisión del SKU ya tiene ficha: F-065** (prioridad 2, documental,
`sdd=false`), pedida por el humano el sábado: medir durante una semana de
nocturnas acotadas cuánto gasta cada una, el peor caso de una completa con la
hucha llena, y el saldo mínimo que queda para el uso diurno; con el criterio de
decisión escrito **antes** de medir. T33/T34 de F-025 alimentan esa tabla. Hasta
tener el veredicto, **no se toca el SKU**: el B2s (+37,38 €/mes) está en la
tabla de precios más abajo por si el domingo hace falta la salida rápida.

**Cómo se ve el estado de una ejecución:**

```powershell
az containerapp job execution list -g rg-datamart-seg-dev -n caj-datamart-seg-dev --query "[0:3].{nombre:name, estado:properties.status, arranque:properties.startTime, fin:properties.endTime, imagen:properties.template.containers[0].image}" -o yaml
```

## Lo hecho el 2026-09-04

| | |
|---|---|
| Review de F-025 | **APROBADO lo entregable** en la 4a pasada; C5 sigue abierto por la fase 7 |
| DA-6 | **EXENTA por el humano**, con lo que implica escrito |
| Paso 0 · `stg` completa | **ya lo estaba**: las nocturnas del 03 y 04 corrieron enteras (1 h 38) |
| Paso 1 · cinco huellas del ANTES | **HECHO**, en `huellas/antes_*.csv` (ignoradas por git) |
| Paso 3 · alerta de la ventana | **DESPLEGADA**: `alert-caj-datamart-seg-dev-ventana`, activa, sev 2 |
| Paso 2 · T1 | **no medible aun**, ver abajo |

**Las cinco huellas del ANTES**, sobre el datamart que dejo la nocturna del 04:
`stg` 12.407 celdas / 349 obras · `mart` 24.775 / 349 · `cierre` 16.948 / 330 ·
`dimension` 735 / 504 · `plan_obra` 938 / 350.

## AVISO · T1 dio 0 % y NO es lo que parece

`T1` midio **920 a reconstruir, 0 a congelar, ahorro 0,0 %**, por debajo del 40 %
que la spec fija como criterio de parada. **No hay que parar: la medicion no es
valida todavia.** La causa esta comprobada: **`_meta.obra_build` tiene CERO
filas** porque el build de F-025 no ha corrido nunca, y R18 dice que una obra sin
registro se reconstruye siempre («completar no es actualizar»). La primera pasada
reconstruye las 920 por diseno y a partir de la segunda ya congela.

**Consecuencia para la spec:** el orden que fijo el reviewer pone T1 en el paso 2,
antes de encender, y **en ese momento T1 no puede dar otra cosa que 0 %**. Hay que
**repetir T1 despues de la primera reconstruccion**, que es cuando la cifra
significa algo. Anotarlo en la spec al cerrar.

## AVISO · la conexion del puesto se cayo DOS veces en una hora

La huella de `stg` fallo dos veces y hubo que lanzarla tres: la primera con
`server closed the connection unexpectedly` **con la IP rotando a mitad de
consulta** (paso de 88.26.22.183 a 62.174.237.73, las dos autorizadas), y la
segunda con `connection timeout expired`. **Ninguna fue culpa del servidor**: en
ese momento tenia **60 creditos de 144** y la CPU al 12 %. A la tercera termino en
**15 minutos**.

Por eso el paso 4 **se lanza como job en Azure y no desde el puesto**: la
reconstruccion dura mucho mas que esa huella, y desde aqui se cae. Ademas dentro
de Azure tarda **1 h 38** frente a las **8 h 15** del 01-sep.

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

## F-025 · SPEC ESCRITA y DECISIONES CERRADAS por el humano (2026-09-02)

`specs/F-025-ventana-negocio-build/`: `requirements.md` (150/150),
`design.md` (250/250), `tasks.md`, más **`mediciones.md`** (línea base medida en
solo lectura) y **`decisiones.md`** (lo que decidió el humano y por qué). Rama
`feature/F-025-ventana-negocio-build`. Reemplaza la spec del 2026-08-28
(commit `1f01718`), anterior a la decisión y a la avería.

### El criterio, decidido: tres reglas en UNIÓN

Se congela toda obra que cumpla al menos una: **(1)** estado **EN ESTUDIO (1),
NO PRESENTADA (11) o CERRADA (25)**; **(2)** código de **seis dígitos**;
**(3)** **sin actividad en 12 meses**. Censo sobre las 920 de `maestro.obras`:
**880 congeladas, 40 vivas** (38 publican en el fact). Detalle obra a obra en
`obras_candidatas_a_congelar.csv`.

**El humano rechazó dos propuestas de la spec, las dos con el dato delante**: el
veto de actividad («pon las reglas que te he dicho») y la formulación en positivo
—solo se actualizan EN CURSO y ADJUDICADAS— («déjalo en negativo»). Las dos
quedan escritas como alternativas no elegidas.

**Contrapartida, sin suavizar y CON LA CIFRA CORREGIDA (2026-09-03):** de las **48
obras con actividad en 12 meses, 8 quedan congeladas** —7 CERRADAS (estado 25) y 1
de seis dígitos, la `180501`— y tendrán **hasta 6 días** de antigüedad.
**Al humano se le presentó un 40, y son 8**: aquel número se midió sobre
`maestro.obras` con `coalesce(fecha_fin, fecha_inicio)`, no con la definición del
código (`raw.obr ⨝ raw.con` y `MAX(make_date(...))` de `stg.fases`,
`SQL_ESTADO_OBRAS`). **Su decisión no cambia** —880 congeladas y 40 vivas cuadran
al dedillo— y la contrapartida real es **menor** que la que aceptó. El detalle,
con fuentes, en el aviso de `decisiones.md` §DA-1 y en `mediciones.md` §2.

**El catálogo de estados apareció y quedó verificado**: vive en `conest`, tipo 42,
vía `con.est`. «25 = CERRADA» ya **no es una suposición**, así que el riesgo que
iba a declararse se retira y en su lugar queda una tarea de documentación: la
ficha de `maestro.obras.estado_id` dice hoy que el catálogo no se ingiere, y eso
ha dejado de ser cierto (T23b, enlaza con F-054).

### Lo que el diseño resuelve

1. **El `TRUNCATE` es el problema, no el filtro.** Cada tramo borra **solo las
   obras que va a reinsertar**, en su misma transacción: imposible borrar lo que no
   se reescribe. De regalo, una muerte a mitad deja la tabla coherente —la nocturna
   del 02-sep habría acabado con 5 obras al día y el resto con el dato de ayer, en
   vez de al 21,6 %—.
2. **DA-2 obligó a rehacer la señal de cambio.** El humano decidió acotar también
   `build_presupuesto`, que era la fuente barata de la firma del origen. La firma se
   traslada a **`raw`** —lo único que la ingesta sigue trayendo completo cada
   noche—, en un sub-paso agregado de solo lectura tras `ingest_raw`. `tiemod` no
   sirve (F-011: no existe en 24 de 31 tablas) y hashear en la ingesta gastaría la
   CPU que falta. Su coste se mide en **T2b** antes de fijarla.
3. **La firma DENUNCIA, no rescata.** Como el humano acepta congelar 8 de las 48
   obras con actividad reciente, reconstruirlas por nuestra cuenta contradiría su decisión: el guardián las
   **nombra** y el domingo las pone al día. Hay interruptor `PG_VENTANA_RESCATE`
   (off) por si cambia de idea.
4. **Reconstrucción completa semanal, los DOMINGOS**, disparada desde `run-all` por
   antigüedad registrada y no por un cron nuevo.
5. **Prueba de equivalencia**: las cuatro huellas de F-052 **sin obras esperadas**
   —si la exclusión es correcta salen idénticas al byte— más una quinta por obra ×
   ámbito, y la 0599 publicando lo mismo que hoy.

### Lo que falta antes de escribir código

**T1** (ahorro real por obra con la consulta de pesos que la nocturna ya ejecuta;
si no llega al 40 % del peso, la spec manda parar), **T2** (línea base de tamaño y
tuplas muertas) y **T2b** (coste de la firma sobre `raw`, con y sin `planif`).

**Riesgo principal que queda:** el `DELETE` selectivo deja tuplas muertas en un
`B1ms` sin créditos. Mitigación: `VACUUM (ANALYZE)` al final del sub-paso y medir
la primera semana; si crece de forma sostenida, la salida es particionar por obra,
y eso sería otra feature.

---

# Estado del 2026-09-01

## F-052 · FASE 2 EJECUTADA — el arreglo está PUBLICADO en la base

**La 0599 ya no miente.** Cierre de 2022-12, contra lo que publicaba ayer:

| Concepto | Antes | Ahora |
|---|---|---|
| **DIRECTOS** | **0,00 €** | **2.624.793 €** |
| GASTOS totales | 1.369.593 € | **3.994.386 €** |
| VENTA | 4.066.989 € | 4.066.989 € |
| **BENEFICIO** | 2.697.396 € | **72.603 €** |
| **Margen** | **66,3 %** | **1,8 %** |

Los tres números que se predijeron el 2026-08-31 —coste 3.994.386,39, beneficio
72.602,84, margen 1,8 %— **han salido exactos**. La obra de control **0628
LEGAZPI no se mueve ni un céntimo**.

**Lo ejecutado el 2026-09-01, desde el puesto y contra producción:**

| Paso | Resultado |
|---|---|
| `stage` | SUCCESS, **8 h 15** (la misma tarea dentro de Azure: 1 h 37) |
| `build-mart` | SUCCESS, 2 h 31 · el fact gana **55.165 filas, todas de la 0599** |
| `build-cierre` | SUCCESS, 2 h 02 · 16.928 filas, las mismas de siempre |
| `publicar-diccionario` | versión **12**, biyección 103/103, `_meta` ya sirve lo del árbol |

**Las cuatro huellas, capturadas antes y después sobre el MISMO `raw`:**

| Huella | Veredicto | Obras que se mueven |
|---|---|---|
| dimension | **OK** | solo 0599 (117 → 1.440) |
| cierre | **OK** | solo 0599 |
| mart | KO por master | **solo 0599**, 144 diferencias |
| stg | KO por master | **solo 0599**, 70 diferencias |

### Las comprobaciones de cierre, contra la base reconstruida

| Comando | Resultado |
|---|---|
| **R12** · clave de `mart.fact_seguimiento_mensual` | **0 claves duplicadas**, 0 filas implicadas, con las 55.165 filas nuevas dentro |
| `check-cierres --timeout 900` | **0 discrepancias** en 8.540 cierres de 679 pares obra/ámbito; telescopio R16: **0 sin cuadrar** de 254.236 series |
| `check-diccionario` | biyección **103/103**; publicado = árbol (**versión 12**) |
| **`check-cobertura`** | **filas huérfanas: 183.824 → 294.** El guardián mide el arreglo: **−99,8 %** |

**El dato que mejor resume la feature es ese último.** El guardián que se
construyó para detectar el problema ahora mide su desaparición: de las 183.824
filas que el build descartaba en silencio quedan **294**. Las 183.530 de la 0599
ya no se pierden.

Sigue en **KO**, y es correcto que lo esté: quedan **20 obras invisibles** y esas
294 filas sin declarar. Ninguna es de F-052 —son las administrativas más 0585,
0687, 0578, 0670 y 0606, que es **F-053**—. **T15 y la desviación 4 del review se
afinan aquí**: esta es la línea base del DESPUÉS.

**OJO con los timeouts:** `check-unicidad` dejó **3 objetos sin comprobar** (antes
era 1) y `check-cierres` murió con `QueryCanceled` a la primera. No es un defecto:
es el servidor tras 12 h de escritura masiva. `check-cierres` necesitó
`--timeout 900`, y el objeto de R12 hubo que comprobarlo aparte con 900 s.

### El KO de master: FALSO POSITIVO, aceptado por el humano el 2026-09-02

`comparar-huellas` arrastra de **F-042** la regla «cualquier cambio en los ámbitos
master 8 u 11 es desbordamiento». **F-052 exige lo contrario y está escrito en
R9**: «deben aparecer las combinaciones 0599 × ámbito 7 y 0599 × ámbito 11, hoy
inexistentes». La herramienta marca como error justo lo que la spec pide.

Comprobado antes de aceptarlo: **las 214 diferencias de las dos huellas son todas
de la 0599**; ninguna otra obra aparece en ninguna. Palabras del humano: «si la
única diferencia es la 599 es lo esperado, está bien».

**Deuda que deja abierta**: `comparar-huellas` debería aceptar cambios en master
**para las obras esperadas**, en vez de rechazarlos siempre. Mientras no se
arregle, cualquier feature futura que toque master se encontrará el mismo KO y
tendrá que volver a razonarlo a mano.

### NOCTURNA DESACTIVADA — hay que revertirlo

El cron del job está en **`0 2 1 1 *`** (no dispara) desde el 2026-09-01 22:00.
Se desactivó porque la imagen del job es **`r20260830-0924`, anterior a F-052**:
a las 02:00 habría reconstruido con el SQL viejo, deshaciendo 12 h 48 de trabajo,
y su `ingest` habría cambiado `raw`, invalidando la comparación.

**Se revierte al desplegar la imagen nueva:**
`az containerapp job update -g rg-datamart-seg-dev -n caj-datamart-seg-dev --cron-expression "0 2 * * *"`

Red de seguridad si se olvida: la alerta de frescura salta a las **30 h** sin
`build_mart` y avisa a los dos buzones del grupo de acción.

### La alerta de cobertura, desplegada

`alert-caj-datamart-seg-dev-cobertura`, severidad 2, ventana de 24 h evaluada
cada hora, dispara por **presencia** del marcador `[F052-COBERTURA-KO]`. El grupo
de acción tiene ya **dos destinatarios**. **Sigue sin verificarse de extremo a
extremo**: no ha llegado ningún correo todavía, y no llegará hasta que el job
corra con la imagen nueva.

## F-052 · FASE 1 IMPLEMENTADA Y REVISADA

**Reviewer: FASE 1 APROBADA, ningún cambio requerido** →
`progress/review_F-052.md`. El cierre queda pendiente de la fase 2: **C5 no se
puede marcar** porque T13, T14 y T15 están sin hacer a propósito.

**La condición de DA-2, verificada por TERCERA vez y por otro camino.** El
reviewer ejecutó el CTE nuevo entero contra **todas las obras** y comparó el
`md5` del sitio de cada partida contra `stg.partidas` de hoy: **cambia UNA sola
obra, la 0599** (117 → 1.440); **las otras 734 salen idénticas al byte**. Es R6
cumplido y la huella 3 pre-validada en solo lectura.

**Dos cosas que el reviewer encontró en la huella 3 y que conviene no perder:**
lleva `ORDER BY p.partida_id` **dentro** del `string_agg` y `COALESCE` en las seis
columnas. Sin lo primero el `md5` bailaría solo; sin lo segundo, un
`capitulo_padre_id` NULL haría NULL el resumen entero de cualquier obra con raíz
y **la comparación parecería verde**. Es el modo de fallo más peligroso que tiene
esta feature: una verificación que miente en verde.

**Tres observaciones que NO bloquean, anotadas para la fase 2:**

1. `check-cobertura` **da verde sobre cero filas**. Hoy cero filas es el estado
   sano, pero un fallo que dejara las dos consultas sin resultados (tabla
   renombrada, esquema vacío) se leería como OK. Con la línea base de **T15** cabe
   añadir el denominador: combinaciones (obra × ámbito) vistas en `stg`.
2. Hay una **décima excepción que T10 no pedía**, la 0606 PUY DU FOU. Justificada
   y marcada `feature: F-053`, pero debía haberse declarado.
3. Un CSV de huella de F-042 anterior a T27 (8 columnas) ya no lo reconoce
   `comparar-huellas` y muere con un mensaje confuso. Hoy no existe ninguno.

**Desviación 4, aceptada CON SEGUIMIENTO:** no hay tope de filas por excepción,
así que la de 0565, 0630 y 0686 tapa **cualquier** número de huérfanas en esas
obras. **T15 fija la línea base y ahí se afina.**

**Automejora propuesta por el reviewer, sin aplicar:** `.claude/agents/reviewer.md`
obliga a un veredicto binario, y una feature partida en dos fases por diseño no es
ni APPROVED ni CHANGES_REQUESTED. Propone un tercero, `APPROVED_FASE_1`, que
obligue a enumerar los checkpoints pendientes. **Decisión del humano.**

### Lo entregado en la fase 1

**Informe completo: `progress/impl_F-052.md`.** Hechas T1-T12, T16-T19 y
T22-T30; T20 ya venía hecha y **T21 (mutación) está exenta** por decisión del
humano del 2026-08-31. `bash harness/init.sh` en verde, cobertura de las líneas
cambiadas al 100 %.

**Pendiente del humano, y es lo que falta para cerrar:** T13, T14, T15 y los diez
pasos de cierre de `tasks.md`. Son escrituras contra el Postgres compartido en
producción o lecturas de varios GB, y desde el puesto **no hay conexión directa**
(`connection timeout expired` contra `psql-albaranes-rs9k2`). Dos de ellos no son
opcionales:

* **el aviso a Negocio (R27) es BLOQUEANTE**: sin él no se publica;
* **desplegar `infra/96_create_alert_cobertura.ps1`** y añadir el buzón al grupo
  de acción. Sin ese paso el guardián nuevo **es mudo**, porque al no bloquear el
  job la alerta de fallo no se dispara.

**Hoy la 0599 sigue publicando las cifras de siempre**: el arreglo está escrito y
probado, no reconstruido.

### El riesgo (a) del informe queda ELIMINADO: el motor ya vio el SQL

El implementer dejó dicho que el `WITH RECURSIVE` con `visitados` estaba probado
en dominio y sobre el texto, **pero no contra Postgres** — porque yo le pasé
información desactualizada: la conexión se había restablecido antes de lanzarlo.
Validado por el líder el 2026-09-01 tomando el CTE **literal** del fichero, sin
`TRUNCATE` ni `INSERT`, como `SELECT` de agregados en solo lectura:

| Comprobación | Resultado |
|---|---|
| El recursivo se ejecuta y **no se cuelga** | 390.508 nodos, **390.501 publicables** — R7 al nodo |
| La 0599 (R8) | **1.440 partidas**, de ellas **1.326 CD** (hoy son 3) |
| Invariante R4 (`cardinality(ruta) = nivel + 1`) | **0 filas lo rompen** |
| R3 (todo `capitulo_padre_id` apunta a fila publicada) | **0 padres colgados** |
| Tope de 40 del corta-ciclos | **0 nodos** por encima de 39: no trunca nada |

Sigue vivo el riesgo (b): la alerta solo está probada como texto, **no hay correo
recibido**. Y R11 sigue sin ejecutarse: esto valida el árbol, no el dinero
publicado.

## F-052 · spec aprobada — las 7 decisiones cerradas por el humano

`specs/F-052-partidas-huerfanas/`. Rama `feature/F-052-partidas-huerfanas`.
Línea base: `progress/explore_F-052.md`. **La causa quedó identificada y la
hipótesis previa desmentida**: la cadena de `padide` de la 0599 **sí llega a la
raíz `CD`**; lo que corta es el filtro `AND h.cod <> ''` de
`sql/stg/04_partidas.sql:78`, que impide **descender a través de** tres capítulos
intermedios con código vacío y amputa 1.323 partidas. Las otras 12 son ciclos.

### Las siete decisiones, cerradas el 2026-08-31

| | Decisión del humano |
|---|---|
| **DA-1** | Solo se relaja la rama de descenso (línea 78). La raíz **no se toca**: criterio de mínimo cambio, «ahora mismo estaba funcionando bien en general» |
| **DA-2** | **Colapsar**, y CONDICIONADO: si se mueve una cifra de una obra distinta de las seis afectadas, **se para y se consulta**. Palabras del humano: «si cambia algo, prefiero perder la 0599 porque no sigue el patrón correcto» |
| **DA-3** | Array de visitados **+** tope de profundidad |
| **DA-4** | **AVISA, NO BLOQUEA** — la nocturna termina en verde. Y **aviso por correo** al buzón de desarrollo |
| **DA-5** | Sí, se lleva a Sigrid sin esperar. Único caso prioritario: la **0686**, obra viva |
| **DA-6** | Avisar a Negocio **antes** de publicar, y nota en el diccionario |
| **DA-7** | Feature propia: **F-053**, prioridad 2 |

**Por qué DA-2 se puede dar por segura sin medirla contra la base**: cada partida
tiene **un solo padre**, luego un solo camino a la raíz. Una partida publicada hoy
tiene todo su camino con código, y el algoritmo nuevo recorre ese mismo camino con
idéntico resultado. **El cambio es estrictamente aditivo.** Datos que lo respaldan:
fuera de la 0599 el movimiento máximo posible son **226 filas de 183.756, a 0,00 €**;
y la profundidad máxima real de `stg.partidas` es de **7 niveles, con cero partidas
de nivel 8 o más sobre 389.178** (medido el 2026-08-31), lo que valida que el tope
de 40 del corta-ciclos no trunca nada legítimo.

**Y ya no hace falta el argumento: está MEDIDO contra `raw`** (2026-08-31, tras
restablecer el acceso). Simulado el árbol nuevo entero y cruzado con
`stg.partidas`: las partidas nuevas son **1.323 y TODAS de la 0599** —ni una en
las otras cinco obras—; **ninguna** partida ya publicada cambia ruta, nivel ni
padre; **ninguna** desaparece; la profundidad máxima es de 7 niveles. El árbol
alcanza 390.508 nodos, menos los 7 no publicables = **390.501, la cifra exacta
de R7**. La condición del humano está verificada **antes de tocar código**.

### El aviso por correo (DA-4) reutiliza lo que ya existe

**No se escribe código de correo.** El patrón ya está en el repositorio:
`infra/90_create_alert.ps1` crea el grupo de acción `ag-datamart-seg-dev` con
destinatarios pasados por `-AlertEmail`, y `infra/95_create_alert_frescura.ps1`
crea una regla de consulta programada sobre `log-datamart-seg-dev` que lo dispara.
`check-cobertura` escribirá un marcador estable en el log y un script nuevo
(`infra/96_create_alert_cobertura.ps1`) creará la regla que lo busca.

**Riesgo declarado**: al no bloquear, la alerta de fallo existente
(`alert-caj-datamart-seg-dev-failed`) **no se disparará**. Esa regla nueva es la
única vía por la que el guardián se hace oír; **si no se despliega, es mudo**.
Su despliegue es manual y lo ejecuta el humano.

**Los correos NO se versionan** — lo dice `infra/90_create_alert.ps1` y se respeta:
el destinatario se pasa con `-AlertEmail` en el despliegue.

### Documento para Negocio, listo

`specs/F-052-partidas-huerfanas/aviso_negocio.md`: qué se encontró, la tabla de
cifras antes/después (margen de la 0599 del **66,3 % al 1,8 %**), a quién afecta,
la pérdida del desglose por fases y lo que hay que pedirle a quien administra
Sigrid. **Es paso bloqueante previo a publicar.**

### BLOQUEO OPERATIVO para implementar

**No hay conexión directa a la base desde el puesto** (2026-08-31,
`connection timeout expired` contra `psql-albaranes-rs9k2`). La base está viva y
responde por la vía de solo lectura del MCP, pero **esa vía no expone `raw`**, que
es donde vive el árbol de partidas. Las verificaciones con huella antes/después no
se pueden ejecutar hasta restablecerlo — probablemente una regla de firewall, y
tocar ese servidor compartido lo autoriza el humano.

## F-042 · `done` — CERRADA, y con ella los 30,4 M€ que se publicaban de más

Rama `feature/F-042-clave-fact`, 27 commits (T1–T25) más el de cierre.
`bash harness/init.sh` en código 0 (2.802 tests). Reviewer **APROBADO** en la 2ª
pasada y **criterio 5 verificado** en una 3ª contra la base ya reconstruida.
Informes: `progress/impl_F-042.md`, `progress/review_F-042.md`,
`progress/explore_F-042.md`. El relato completo, en `progress/history.md`.

**La carga que la bloqueaba terminó.** Job `caj-datamart-seg-dev-d8y5q10`,
imagen **`r20260830-0924`** —la primera con F-042—, `run-all --full` con los diez
pasos: 08:06:36 → **11:38:00 UTC**, 3 h 31 min, `Succeeded`. Comprobada **la
imagen del job**, no solo su estado: es la lección de F-047.

**Los cuatro comandos de cierre, contra la base reconstruida:**

| Comando | Resultado |
|---|---|
| `check-unicidad --timeout 300` | `mart.fact_seguimiento_mensual` **OK**: de **8.778 combinaciones duplicadas a CERO** |
| `check-cierres` | **0 discrepancias** en 8.540 cierres de 679 pares obra/ámbito; telescopio R16: **0 sin cuadrar** de 254.189 |
| `check-diccionario` | Biyección exacta **103/103**; lo publicado es lo del árbol (versión 11, hash `68ecfd13f697`) |
| `bash harness/init.sh` | **Código 0**, 2.802 tests, 100 % de 656 líneas cambiadas |

**OJO CON EL TIMEOUT, y esto vale para cualquier sesión futura:** con los 30 s por
defecto, `check-unicidad` deja `mart.fact_seguimiento_mensual` en **NO
COMPROBADO**, que no es un OK. Hay que lanzarlo con **`--timeout 300`**. Con ese
timeout el cuadro completo es **44 sin contradicción · 1 con la clave rota · 1
sin comprobar**.

**El diccionario no cambia de tamaño con F-042**, que solo altera lo que dicen
seis fichas: sigue en **103 objetos**, **798 columnas** y **46 fichas de
consumo**, y la lista de pendientes declarados no crece.

**El quinto criterio —que `importe_origen` deja de venir doblado— lo verificó el
reviewer con un oráculo independiente del build:** recompone el acumulado desde
`stg.presupuesto ⨝ stg.fases ⨝ stg.partidas` (las tres intactas en F-042) y
valida el propio oráculo reproduciendo al céntimo los 18 importes publicados de
`explore_F-042.md`. Resultado: **17.289 celdas cruzadas, desvío máximo 0,00 €**;
cambian **35 celdas de 7 obras**, exactamente la línea base honesta, por
**30.424.662,34 €** retirados, y fuera de ellas **no se mueve ninguna otra
celda**. Los casos que decidían, medidos en la base y no en un fixture: **0606
PUY DU FOU** conserva la fase 14 y cambia **0,00 €**; **0462 RETAMAR**, cuyo mes
en conflicto era el ÚLTIMO de la obra, publica ya **197.654,80 €** de coste donde
publicaba 395.309,32; y la joroba de la 0246 desaparece.

---

## LO QUE F-042 DEJA ABIERTO (nada bloquea, todo está fichado o anotado)

1. **F-051 · nueva, prioridad 3, rigor crítico.** `nombre_mes` de las filas
   reales trae **la descripción del cierre** en vez del mes, y eso rompe la
   clave de `cierre.v_pbi_planif_vs_real`. Ver la sección de abajo.
2. **El diccionario publicado dice 30.425.881,56 € y lo retirado son
   30.424.662,34.** Celdas (35) y obras (7) son exactas; ese importe describe la
   regla **exploratoria**, no la implantada. Una línea a corregir en el próximo
   `publicar-diccionario`. **Sin fichar todavía.**
3. **F-052 · nueva, prioridad 2, rigor crítico.** La observación lateral de la
   3ª pasada —«1.152 filas de la obra 0599 no llegan al fact»— **resultó ser dos
   órdenes de magnitud mayor** al medirla: son **104.737 filas** de
   `stg.presupuesto` en 6 obras, y **la 0599 TANATORIO MAJADAHONDA se ha caído
   del datamart casi entera** (104.366 de sus 108.790 filas, el 96 %). Ver la
   sección de abajo.
4. **`mart.v_master_vigente_anual` no se puede comprobar.** `check-unicidad`
   agota **300 s** sin dar veredicto, así que su clave `(obra_id, anio,
   ambito_id)` es hoy un «no lo sabemos» **permanente**, no un OK. Ninguna otra
   de las 46 de la superficie de consumo se queda sin medir con ese timeout.

---

## F-051 · `pending` — el mes que enseña Power BI no es el mes de la fila

Descubierto el 2026-08-30 por `check-unicidad` sobre la base recién
reconstruida. **No lo introducen F-042 ni F-047**: es preexistente y sale ahora
porque F-047 hizo que la vista se construya cada noche en vez de destruirse, y
por eso entra por primera vez en el alcance del check.

**El síntoma:** `cierre.v_pbi_planif_vs_real` no cumple su clave —**204
combinaciones repetidas, 472 filas**, siempre en el renglón **BENEFICIO** y hasta
cuatro filas por combinación—. Quien sume ese renglón ahí recibe hasta el
cuádruple.

**La causa, localizada en el código:** en `mart/02_build_fact.sql`, las ramas
**COSTE REAL (línea 218, ámbito 3)** y **VENTA REAL (línea 248, ámbito 7)**
rellenan `nombre_mes` con **`pm.version_descripcion`** —el texto que alguien
tecleó al cerrar en Sigrid— en vez de derivarlo de `anio_mes`, que es lo que sí
hacen las dos ramas planificadas (líneas 275 y 305). Y como el CTE `beneficio`
de la vista une `producc` con `total_costes` **solo por `(obra_id, anio_mes)`**
mientras ambos agrupan incluyendo `nombre_mes`, cada etiqueta distinta multiplica
las filas en producto cartesiano.

**El alcance, medido en la base en solo lectura:**

| Tabla | Filas REAL | Con `nombre_mes` que no es su mes | PLANIFICADO |
|---|---|---|---|
| `mart.fact_seguimiento_mensual` | 3.332.312 | **566.504 (17,0 %)** | **0** de 1.965.029 |
| `mart.fact_seguimiento_categoria` | 17.289 | **3.226 (18,7 %)** | **0** de 7.395 |

**36 pares (obra, mes)** tienen más de una etiqueta distinta, y esos 36 son los
que producen el fan-out. Ejemplos reales: la obra **0571** tiene 2020-05-01
etiquetado a la vez «Mayo 2020» y «Agosto 2020»; 186 filas de 2024 en adelante
dicen «Diciembre 2025»; 61 filas de jun-2010 dicen «DICIEMBRE 2010», en
mayúsculas, porque es texto libre.

Comparte raíz de negocio con el **patrón 2 de F-050** (la fase abarca varios
meses y Sigrid la archiva en el de arranque), pero **el arreglo no depende de esa
investigación**: aquí la decisión es de qué columna se deriva `nombre_mes`.

---

## F-052 · `pending` — una obra entera que el datamart no ve

Medido el **2026-08-31** contra la base, en solo lectura, al ir a fichar la
observación lateral del reviewer. **La observación se quedaba muy corta.**

| | Filas |
|---|---|
| `stg.presupuesto` con `partida_id` **sin ficha** en `stg.partidas` | **104.737** en 6 obras y 1.215 partidas |
| De la 0599 · `stg.presupuesto` sin ficha | **104.366** de 108.790 (**96 %**) |
| De la 0599 · `stg.plan_mensual` → `mart.fact_seguimiento_mensual` | 197.846 → **3.150** |
| Comparación: 0613 RICHMOND PARK, de tamaño parecido | 217.230 → **62.568** |

**El dato no se pierde en la ingesta, lo pierde nuestro ETL.** Las 1.215
partidas huérfanas están **las 1.215** en `raw.obrparpar`, todas con `cod` no
nulo y ninguna con `padide = 0`: Sigrid las tiene y la ingesta las trae.

**Causa probable, a confirmar:** `stg/04_partidas.sql` construye `stg.partidas`
con un recorrido **recursivo** que arranca en las raíces (`COALESCE(padide,0)=0`,
línea 56) y baja por `padide` (línea 76). Una partida cuya cadena de ancestros no
llegue a una raíz queda fuera del árbol, y entonces el **`INNER JOIN`** del build
del fact la borra del datamart **sin decir nada**.

**Lo que lo hace grave no es el importe, es el silencio.** Una obra que no está
no produce un número raro: produce respuestas como si casi no existiera. Y
ninguna comprobación de hoy lo caza —`check-unicidad` mira claves,
`check-cierres` mira la regla de F-042, `check-diccionario` mira el catálogo—:
**nadie mira que lo que entra en `stg` salga en `mart`**.

---

## F-047 · CERRADA el 2026-08-28 (absorbió F-044)

La nocturna no dejaba de crear `cierre.v_pbi_planif_vs_real`, **la destruía**
(`mart/03_agg_categoria.sql` dropea con `CASCADE` la tabla de la que cuelga).
Detalle en `progress/explore_F-047.md`, `impl_F-047.md` y `review_F-047.md`.

**La lección que vale para cualquier feature futura: el repositorio en verde no
es producción.** El despliegue llevaba congelado desde el 18 de agosto, diez
noches terminando `Succeeded` con código de hace diez días.

**F-044**, que absorbió, quedó cerrada el 2026-08-30 con las dos mediciones que
faltaban: la nocturna completa tarda **3 h 45** y termina a las 05:45 UTC (07:45
locales), aceptado por el humano; y el pico de disco fue **89,25 %** sobre los 32
GB de entonces —a 5,75 puntos del bloqueo por solo lectura—, lo que motivó la
ampliación a 64 GB del 29 por la tarde. Con 64 GB ese mismo pico sería 44,6 %.

### Lo que sigue abierto de aquella tanda

- **F-041**: el `__pycache__` opera también en serie, y es bidireccional.
- **F-049**: `mutacion.py` deja el sello `PENDIENTE` puesto tras resolverse.
- **F-048**: el guardián de secretos decide por el primer carácter del valor.
- **F-012**: siete reglas de firewall de puestos sueltos acumuladas.

---

## LO SIGUIENTE

**Ninguna feature `in_progress`.** El backlog tiene 31 abiertas; por prioridad,
las de nivel 2 son **F-036** (clasificación por oficio), **F-041** (la campaña de
mutación miente) y **F-045** (retenciones sin obra), y en el 3 entra ya
**F-051**.

### La cola de trabajo, fijada por el humano el 2026-08-31

**F-052 → F-053 → F-045 → F-051 → F-050**, con las prioridades 1 a 5 puestas en
`features.json` y la razón anotada en cada ficha. Salió de preguntarse qué falta
para que **negocio pueda usar el datamart a través del MCP**; **F-053 se insertó
en el 2 el 2026-08-31**, al aparecer en la exploración de F-052.

1. **F-052** — una obra que no está en el datamart no produce un número raro,
   produce respuestas como si casi no existiera. No hay nada que chirríe, así
   que envenena la confianza en todo lo demás.
2. **F-053** — la hermana de F-052: otras tres obras invisibles (0517, 0252,
   0720) por una causa distinta, el desempate `rn = 1` de `stg/03_obras.sql:125`
   que elige la ficha vacía. ~10,65 M€ de coste y 10,94 M€ de venta. **Pero
   primero hay que analizar si de verdad es un error**: la ficha llena puede ser
   una versión jubilada a propósito, y publicarla sería resucitar datos retirados
   o doblarlos. Es resultado válido cerrarla sin tocar código. **No se mezcla con
   F-052**: la verificación de las dos es la misma huella antes/después, y tocar
   dos causas a la vez impide saber cuál movió qué.
3. **F-045** — el caso de uso 3 del humano, las retenciones de los proveedores
   de una obra, hoy **no tiene respuesta**: `retenciones.movimientos.obra_id` no
   une con `maestro.obras`, 0 de 261 valores casan.
4. **F-051** — con el diagnóstico ya hecho y medido.
5. **F-050** — los meses que faltan, que es la raíz de negocio compartida.

**Lo demás espera**, incluidas las de prioridad 2 que había antes (F-036, F-041).

### Lo que no es una feature y decide el humano

Antes de dar el conector del MCP a la primera persona de negocio hay dos cosas
que no se resuelven con código: si se compra **Entra ID P1** —sin él entra
cualquier cuenta del tenant, y eso se aceptó por escrito cuando detrás había un
`pong`, no el seguimiento económico real— y si se encienden los **`REVOKE` de
F-034**, sabiendo que hacerlo sin verificar antes qué lee Power BI le rompe los
informes. El rol `mcp_sigrid_dm_ro` lo comparten hoy el MCP y Power BI, y ve
`raw` y `stg`.

Queda **una** cosa sin fichar, a propósito: la línea del diccionario que dice
30.425.881,56 € cuando lo retirado son 30.424.662,34. Es una línea de YAML y se
corrige **dentro de F-051**, que ya toca el diccionario y obliga a republicar;
una feature para una línea es papeleo por papeleo.
