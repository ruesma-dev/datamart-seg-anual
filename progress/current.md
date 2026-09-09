<!-- progress/current.md -->
# Estado actual · 2026-09-09 (miercoles; F-025 y F-068 cerradas, F-066 en su pasada de cierre)

> **PURGADO dos veces.** C2 pide que este fichero describa **solo la sesion
> activa**. El 2026-09-06 (review de F-066, pasada 1) bajo de 1.263 a 638 lineas,
> quitando cinco sesiones cerradas —F-042, F-047, las fases 1 y 2 de F-052, la
> spec de F-025— y el encabezado de F-066 escrito dos veces. El 2026-09-09
> (pasada 3 del mismo review) se le quitan las 253 lineas de la fase 7 de F-025,
> ya `done`, y el estado de F-066 anterior a T13. **Nada se pierde**: vive en
> `progress/history.md`, en los informes `impl_*`/`review_*`/`incidencia_*` de
> `progress/` y en las specs. Lo que queda aqui es lo que sigue vivo: **F-066**
> (solo le falta T14), **F-052** (`blocked`), el estado del servidor y la
> averia de la nocturna del 07 con su premio.

## POR DONDE SE SIGUE EN LA PROXIMA SESION (leer esto primero)

**LO UNICO ABIERTO ES F-066, Y LE FALTA UNA COSA: T14.** Son las dos
verificaciones `MANUAL (humano)` contra Azure, y **las hace el lider**, no el
implementer. El hueco esta preparado, con los dos comandos, el criterio de
cierre y el bloque donde se pega la salida, en
`specs/F-066-ingesta-raw-pendientes/mediciones.md` **§6**:

```powershell
python main.py check-raw-recuentos    # tiene que salir con codigo 0
python main.py check-diccionario      # sin objetos sin ficha
```

**Cuando lanzarlos**: con la nocturna **terminada**, nunca mientras corre. Cada
uno hace 56 `COUNT(*)` contra Sigrid y contra el Postgres compartido, que esta
en produccion con `albaranes` y `partes` dentro. La nocturna del 09-sep
(`29815200`) arranco a las 00:00 UTC.

**Que se espera ver.** La unica medicion contra Azure es del 08-sep a las 16:30
UTC y es con el criterio **viejo**: 31 iguales, 25 distintas, codigo 1. Con la
tolerancia con direccion que entro en T19-T24 eso mismo sale **conforme**, y lo
que hay que mirar es que no haya ninguna tabla con Sigrid **por debajo** de
`raw` (esas son alarma sea de una fila) y que `ausentes` y `sin_medir` esten a
cero. Rellenado el §6, T14 pasa a `[x]`, C4 se cierra y la feature va al
reviewer para la pasada 4.

**F-066 · LOS CAMBIOS DE LA PASADA 3 DEL REVIEW, APLICADOS (2026-09-09).**
Veredicto `CHANGES_REQUESTED` con el **codigo aprobado**: los seis puntos eran
de papeleo. Informe en `progress/impl_F-066_cierre.md`. Cerrados los puntos 1,
2, 4, 5 y 6; el 3 es T14 y es del lider.

* **R19 y R20 cumplidos** en `mediciones.md` §3 y §4, con las cifras sacadas de
  `_meta.etl_runs` y no del chat: la nocturna `p1gq8ks` (08-sep, 11:16 -> 14:19
  UTC, `Succeeded`, imagen `r20260908-1248`, SKU `Standard_B2s`) hizo
  `ingest_raw` en **2.454,1 s con 25.491.959 filas**, frente a **1.832,4 s y
  20.147.626** de la linea base del 05-sep: **+26,5 % de filas y +33,9 % de
  tiempo**. Filas y segundos **por tabla** de las 8 grandes y de `dcf`, en la
  tabla de §3. Creditos: **minimo 552 de 576**, o sea **hasta 24 gastados**.
* **Un numero de la spec estaba mal y ahora se sabe por que.** R19 declara la
  linea base en «20.148.546 filas»; el `rows_processed` de ese paso es
  **20.147.626**. Las 920 de diferencia son el tramo `ingest_raw.firma_origen`,
  que el paso padre no suma. Las dos lecturas valen; mezclarlas, no.
* **Seis commits estaban mal rotulados** (`da965c8`, `29f7c62`, `4a3cd2c`,
  `e2e2ad8`, `ddcf8b2`, `084f75a` dicen `F-066 T1`...`T6`, que son las tareas de
  la ingesta). El trabajo real —la tolerancia con direccion— ya esta declarado
  como **T19-T24** en `tasks.md`, con la tabla commit -> tarea. **No se
  reescribe el historial**: la rama ya esta revisada y un `rebase` invalidaria
  los SHA que citan `mediciones.md`, el review y los informes de mutacion.

**F-025 CERRADA** el 2026-09-08 (commit `96bb7b9`). La ventana de negocio
ahorra el **71,2 %** en `build_stg` (9.527 s -> 2.652 s) y la noche entera baja
de 4 h 52 a 3 h 03; dos mediciones independientes, en dos dias y con dos
imagenes distintas. Detalle en `specs/F-025-ventana-negocio-build/mediciones.md`
y `progress/review_F-025.md`. **T33 paso a F-065** (bloat tras siete noches
acotadas). De su cierre salio **F-071**.

**F-068 CERRADA** el 2026-09-08 (commit `f94fae6`). Los datos personales de
`raw.emp` dejan de ser legibles por el rol del MCP y la nocturna lo mantiene:
lo declarado manda sobre el catalogo, asi que un `DROP` de la tabla ya no
repone el GRANT por defecto. **La revocacion es TEMPORAL** y su reversion esta
decidida por el humano: vuelve en cuanto el MCP tenga control por usuario, y
esta escrito en `config/settings.py`, `02_roles.sql`, `docs/ARCHITECTURE.md`,
el runbook y las fichas del diccionario para que nadie lo lea dentro de seis
meses como una prohibicion permanente. Informes: `progress/impl_F-068.md` y
`progress/impl_F-068_correcciones.md`.

**PENDIENTE QUE SOBREVIVE A F-068**: `infra/sql/02_roles.sql` no lo ejecuta
ningun test —solo se comprueba su texto— y esta corregido en dos sitios que
solo prueba `psql`. Antes de volver a provisionar un rol desde cero, ejecutarlo
contra una base de prueba.

**EL BACKLOG, REORDENADO** (por el humano, y ya en `harness/features.json` y
`BACKLOG.md`). Lo siguiente cuando F-066 cierre:

| Prioridad | Feature | Que es |
|---|---|---|
| 4 | **F-071** | La IA ve 583 obras cuando solo 349 tienen datos: marcarlas y declararlo, no borrarlas. Nace del hallazgo de F-025 (552 obras de ruido en el censo, 512 sin nada que construir, `0000` = «PLANTILLA DE OBRA» y el `0001` repetido ocho veces). |
| 5 | **F-070** | Auditar la calidad de las fichas del diccionario, **acotada a los ocho esquemas que el MCP lee** (`mart`, `cierre`, `stg`, `compras`, `maestro`, `retenciones`, `aux`, `_meta`): lo que el agente no puede consultar no se audita. Su spec ya esta escrita en `specs/F-070-auditoria-calidad-diccionario/`. |
| 6 | **F-034** | Power BI deja de leer de local y pasa a leer el datamart de Azure. |

Detras, F-057 (7) y F-056 (8), las dos ya sin ingesta dentro porque F-066 se la
llevo.

## LA NOCTURNA DEL LUNES 07 FALLO Y YA ESTA ARREGLADO (con premio detras)

**`caj-datamart-seg-dev-29812320`, 00:00 -> 01:26 UTC, `Failed` las dos veces.**
Era la primera acotada, la que tenia que dar T31b y T34.

**Causa**: un inquilino NUEVO del Postgres compartido, la base **`facturas`**
(dueño `facturas_owner`), sobre la que `sigrid_dm_etl` no tenia `CONNECT`; y la
puerta de disco de F-019 suma `pg_database_size` de **todas** las bases antes de
cada tramo. `permission denied for database facturas`. **La base quedo intacta**
y no por suerte: la puerta se niega a ejecutar a ciegas y aborto antes del tramo
1/21.

**RESUELTO el mismo dia, y mejor que la salida que se propuso.** El humano
concedio a `sigrid_dm_etl` el rol predefinido **`pg_read_all_stats`**, que mide
cualquier base **sin `CONNECT`, sin acceso a los datos y cubriendo las bases
futuras** -que es lo que de verdad fallo-. Verificado: `pg_has_role` da `t` y la
consulta devuelve las **nueve** bases. Por eso **`SQL_OCUPACION_DISCO` no se
toca**: filtrar por permiso habria dejado la medicion parcial y subestimando,
que es justo el riesgo que la puerta vigila.

**EL SEGUNDO HALLAZGO, PEOR QUE EL PRIMERO.** Al verificar el arreglo salio que
el disco **se amplio de 32 a 64 GB el 2026-08-29** y el job **no declaraba**
`PG_DISCO_TOTAL_GB`: durante nueve dias la puerta midio contra 32 GB y veia un
**74,32 %** donde la ocupacion real es del **37,16 %**. Aborta al 80 %: estaba a
menos de seis puntos de tumbar la nocturna todas las noches sin que nada
estuviera mal, y F-066 suma ~0,9 GB. Arreglado en tres sitios para que no vuelva
a divergir: el defecto pasa a 64, `dev.json` declara `discoTotalGb` y
`80_create_job.ps1` la inyecta, y un test ata las dos.

Informe: `progress/impl_disco_64gb.md`. Incidencia completa (diagnostico, censo
de bases y cierre): `progress/incidencia_nocturna_20260907.md`. En `azure-apps`,
commit `eccf6a4`: sexto inquilino, `pg_read_all_stats` y el disco de 64 GB.

**LA NOCTURNA SE RELANZO A MANO**: `caj-datamart-seg-dev-swtg78p`, arrancada a
las **07:48:46 UTC** del lunes 07 con **475 creditos** de 576 (SKU B2s) y con la
imagen vieja `r20260905-1237` a proposito. De ella salen T31b y T34.

**Las tres cosas que esta seccion dejaba esperando al humano ESTAN HECHAS**
(se dejan nombradas para que se entienda el resto de la seccion, sin repetir su
detalle): (0) `PG_DISCO_TOTAL_GB=64` entro en el job al desplegar la imagen de
F-066; (1) **F-068 cerrada** el 08-sep; (2) **T13 de F-066 hecha** el 08-sep,
con la nocturna `p1gq8ks`; (3) **F-025 cerrada** el 08-sep. El estado de las
tres esta arriba, en «POR DONDE SE SIGUE».

**El servidor sigue en `Standard_B2s`** (temporal desde el 05-sep, 17:21 UTC).
La bajada a B1ms sigue pendiente, con fecha limite 2026-09-20 anotada en
`azure-apps/` para preguntar si se olvido. Al bajar, el saldo se resetea a 60.

## F-066 · TODO HECHO SALVO T14, QUE ES DEL LIDER

**Al 2026-09-09.** T1-T13 y T15-T27 hechas, con un commit por tarea. La ingesta
pasa de **31 a 56 tablas** y las 56 corren cada noche en produccion desde la
imagen `r20260908-1248`. Lo que queda es **T14**, las dos verificaciones
`MANUAL` contra Azure: comando, criterio y hueco donde pegar la salida, en
`specs/F-066-ingesta-raw-pendientes/mediciones.md` §6.

**Las decisiones de la spec (DA-1 a DA-11) no se repiten aqui**: viven en
`specs/F-066-ingesta-raw-pendientes/design.md` §6 y en la ficha de
`harness/features.json`. Las tres que cerro el humano el 2026-09-06 a las 12:05
UTC: `emp` y `res` **enteras** (DNI, cuenta bancaria y domicilio incluidos, solo
11 exclusiones tecnicas en `emp`), el historico de estados a **F-067** como foto
diaria —Sigrid no lo guarda— con `conest` dentro de F-066, y `apu` entera con
`--full` mas `apa`.

**Informes de la feature**, por si hay que volver a ellos:
`progress/impl_F-066.md` (la ingesta), `impl_F-066_correcciones.md` (pasada 1
del review), `impl_F-066_reconciliar_columnas.md` (R25-R28, el defecto que
tumbo dos nocturnas), `impl_F-066_tolerancia_recuentos.md` (T19-T24) e
`impl_F-066_cierre.md` (pasada 3). El review, en `progress/review_F-066.md`.

**Cuatro cosas que conviene no perder:**

1. **`check-raw-recuentos` cazo un fallo real el dia que nacio**: el YAML tenia
   17 entradas duplicadas que la nocturna habria cargado dos veces cada noche.
   Ningun test lo veia porque todos leian la ingesta como un `dict`, que
   colapsa duplicados. Corregido, con dos comprobaciones nuevas.
2. **El criterio de igualdad exacta era inalcanzable por diseno** —Sigrid es un
   ERP vivo y el datamart una foto— y se sustituyo por **tolerancia CON
   DIRECCION**: filas de mas en Sigrid son deriva y se toleran hasta 0,05 % por
   tabla; filas de MENOS son alarma sea de una fila; `ausentes` y `sin_medir`
   siguen siendo fallo. La grieta, dicha en voz alta por el reviewer: 0,05 % de
   `obrparpre` son ~6.940 filas. **Revisar el umbral si baja `page_size` o
   aparece una tabla mayor.**
3. **`tests/test_f024_dominio.py::test_f024_r1_batch_id_tiene_forma_y_es_unico`
   era aleatorio** y fallaba el 0,8 % de las veces, invalidando campanas de
   mutacion ajenas. Arreglado el 06-sep: 0 fallos en 3.000 pasadas.
4. **`harness/mutacion.py` no muta constantes `float` ni la division.** En el
   alcance de la tolerancia son seis sitios ciegos, y uno es
   `TOLERANCIA_DERIVA_PCT = 0.05`, el numero del que depende entero el criterio.
   Estan cubiertos por tests —el reviewer los muto a mano y mueren—, pero eso lo
   demuestran los tests y no la campana. **Automejora fichada para F-069.**

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

## F-025 · CERRADA el 2026-09-08 — esta seccion se ha retirado

Ocupaba 253 lineas con los once pasos de la fase 7 y sus comandos, todos
ejecutados. **F-025 esta `done`** (commit `96bb7b9`), asi que aqui no queda
sesion activa que describir. Donde vive lo que habia:

* **Las mediciones** (el 71,2 % de ahorro, las tres nocturnas comparadas, los
  creditos, el bloat de T2): `specs/F-025-ventana-negocio-build/mediciones.md`.
* **El estado de los once pasos y de cada T**: `tasks.md` de esa misma carpeta.
* **El veredicto y los cuatro cambios del review**: `progress/review_F-025.md`.
* **Lo que quedo abierto**: **T33** (bloat sostenido tras siete noches
  acotadas) pasa a **F-065**, con dueno y umbral escritos; y el hallazgo de las
  552 obras de ruido en el censo abre **F-071**, hoy en prioridad 4.
