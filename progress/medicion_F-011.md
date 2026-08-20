<!-- progress/medicion_F-011.md -->
# F-011 · Medición de la carga (bloque A) y puerta de decisión de R8

> **Fecha**: 2026-08-19 (noche) / 2026-08-20.
> **Rama**: `feature/F-011-carga-incremental`. **Rigor**: `critico`.
> **Estado**: bloque A implementado (T1–T6, T21). Este documento es **T8**, y
> lo que sigue es **T9: la PARADA**. Ningún requisito del bloque B (R9–R19) se
> ha empezado, y no puede empezarse sin que el humano firme aquí.

## Resumen en tres líneas

1. **Ahorro máximo posible de la ingesta incremental por watermark: 2,25 min.**
   El umbral de DA-7 son 20. No llega ni a la novena parte.
2. **La ingesta es el 19,9 % del tiempo de carga.** El umbral de DA-7 es el
   40 %. Tampoco.
3. **Recomendación firmada: NO implementar el bloque B.** Y no por poco margen,
   sino porque la marca de modificación que lo sostenía **no existe en las
   tablas que cuestan el tiempo**: se ha comprobado en el catálogo de Sigrid.

---

## 0 · De dónde salen los números (y de dónde no)

| Dato | Fuente | Cómo se reproduce |
|---|---|---|
| Duración por paso de pipeline (R1, R2) | `ContainerAppConsoleLogs_CL` del job en `log-datamart-seg-dev` — evento `step_finished`, que trae `duration_s` medido por el propio ETL | KQL del §0.1 |
| Duración y filas por tabla (R1, R3) | mismos logs — eventos `ingest_table_start` / `ingest_table_done`, con su `timestamp` y `rows_inserted` | KQL del §0.1 |
| Qué columnas de marca existen de verdad (R6, R7) | **catálogo de Sigrid** (`INFORMATION_SCHEMA.COLUMNS`) vía `sigrid-api`, en solo lectura | §3 |
| Semántica de `tiemod` | 5 filas de `dbo.con` y 5 de `dbo.auxobrtip`, leídas por `sigrid-api` | §3.2 |

**Lo que NO se ha podido leer, y por qué.** `_meta.etl_runs` en Azure: la
conexión desde el puesto muere con `connection timeout expired` porque **la IP
pública del puesto ha vuelto a rotar** y ninguna de las reglas de firewall
vigentes la cubre. Crear o modificar una regla es una **escritura sobre un
recurso compartido con `albaranes` y `partes`**, así que no se ha hecho: lo
decide el humano.

Consecuencia práctica: **ninguno de los números de este informe pierde valor**
—los logs del job traen los mismos instantes que `_meta.etl_runs`, medidos por
el mismo código— pero la ejecución de `python main.py perfil-carga` contra
Azure queda como verificación MANUAL pendiente (§7). El comando está
implementado y probado, y se ha ejecutado de verdad: devolvió el error de
conexión con salida 2, que es su camino de «no he podido leer».

### 0.1 · Las consultas exactas

```powershell
$ws = az monitor log-analytics workspace show -g rg-datamart-seg-dev `
        -n log-datamart-seg-dev --query customerId -o tsv
az monitor log-analytics query -w $ws --analytics-query `
  "ContainerAppConsoleLogs_CL | where TimeGenerated > ago(40h) | where Log_s has_any ('ingest_table_start','ingest_table_done','step_finished') | project TimeGenerated, Log_s | order by TimeGenerated asc | take 2000" -o json
```

Y, cuando el firewall lo permita, el equivalente desde el propio ETL:

```bash
python main.py perfil-carga                    # última carga
python main.py perfil-carga --batch <batch_id> # una carga concreta
```

---

## 1 · R1 y R2 · Dónde se va el tiempo, en tres cargas completas

Tres cargas completas y consecutivas del job `caj-datamart-seg-dev`. Las tres
terminaron en `SUCCESS`, las tres con `--full`, que es como corre hoy:

| Carga (UTC) | `ingest_raw` | `build_stg` | `build_mart` | **Total** | % ingesta |
|---|---|---|---|---|---|
| 2026-08-18 10:23 (manual) | 33,1 min | 110,6 min | 21,5 min | **165,1 min** | 20,0 % |
| 2026-08-19 02:00 (nocturna) | 35,6 min | 110,6 min | 21,6 min | **167,7 min** | 21,2 % |
| 2026-08-19 10:10 (manual) | 30,2 min | 111,0 min | 21,6 min | **162,8 min** | 18,5 % |
| **MEDIA** | **32,9 min** | **110,7 min** | **21,6 min** | **165,2 min** | **19,9 %** |

`apply_grants` y `load_excel_aux` suman menos de 4 s entre los dos: no cambian
nada y no se listan.

**Techo de mejora por paso (R2)**, sobre la media, que es lo que R2 existe para
dar:

| Si este paso costase cero… | La carga duraría | Ahorro | % |
|---|---|---|---|
| `build_stg` | 54,5 min | **110,7 min** | **67,0 %** |
| `ingest_raw` | 132,3 min | 32,9 min | 19,9 % |
| `build_mart` | 143,6 min | 21,6 min | 13,1 % |

Lo que decía la spec (`requirements.md` §0.1) con los datos de una sola carga
**se confirma con tres**, y con una estabilidad notable: `build_stg` varía
menos de 30 s entre cargas separadas por 24 h. **La sospecha que abrió la
feature —que el cuello estaba en la extracción— queda refutada por segunda vez
y con más datos.**

---

## 2 · R3 · Qué tablas se llevan el tiempo de la ingesta

Carga nocturna del 2026-08-19 (las otras dos dan el mismo reparto):

| # | tabla | seg | min | filas | % ingesta | % acumulado | ¿cursor declarado en el YAML? |
|---|---|---|---|---|---|---|---|
| 1 | `obrparpre` | 1.302,5 | 21,7 | 13.809.350 | 61,3 % | 61,3 % | `tiemod` |
| 2 | `dcapro` | 207,5 | 3,5 | 1.138.209 | 9,8 % | 71,0 % | `tiemod` |
| 3 | `dcfpro` | 183,6 | 3,1 | 1.084.628 | 8,6 % | **79,7 %** | `tiemod` |
| 4 | `con` | 142,4 | 2,4 | 2.172.969 | 6,7 % | 86,4 % | `tiemod` |
| 5 | `dca` | 64,9 | 1,1 | 307.571 | 3,1 % | 89,4 % | `tiemod` |
| 6 | `ctrpro` | 55,9 | 0,9 | 242.654 | 2,6 % | 92,0 % | `tiemod` |
| 7 | `dcf` | 48,5 | 0,8 | 164.382 | 2,3 % | 94,3 % | `tiemod` |
| 8 | `obrparpar` | 44,2 | 0,7 | 390.208 | 2,1 % | 96,4 % | `tiemod` |
| 9 | `pag` | 36,6 | 0,6 | 253.393 | 1,7 % | 98,1 % | `tiemod` |
| 10 | `comlin` | 10,4 | 0,2 | 195.332 | 0,5 % | 98,6 % | `tiemod` |
| | *(21 tablas más)* | 28,4 | 0,5 | 61.000 | 1,4 % | 100 % | mezcla |

**Respuesta de R3: TRES tablas acumulan el 79,7 % del tiempo de ingesta**
(`obrparpre`, `dcapro`, `dcfpro`) y **cuatro llegan al 86 %**. Atacar las 31 es
trabajo tirado, que es exactamente lo que R3 quería saber antes de diseñar
nada.

### 2.1 · Cuánto crece el datamart en un día (dato nuevo, gratis)

Comparando las filas ingeridas en dos cargas separadas 23,8 h:

| tabla | 18-ago | 19-ago | crecimiento |
|---|---|---|---|
| `obrparpre` | 13.809.325 | 13.809.381 | **+56** (0,0004 %) |
| `con` | 2.172.651 | 2.173.156 | +505 (0,023 %) |
| `dcapro` | 1.138.090 | 1.138.414 | +324 (0,029 %) |
| `dcfpro` | 1.084.347 | 1.084.824 | +477 (0,044 %) |
| **TOTAL `raw`** | **20.047.942** | **20.049.630** | **+1.688 (0,0084 %)** |

Traducción: **cada noche se traen 20 millones de filas para incorporar unas
1.700 nuevas**. Es el argumento a favor de la ingesta incremental… y es
justamente lo que la sección siguiente hace inviable.

---

## 3 · R6 y R7 · El veredicto de `tiemod`: la marca NO existe donde hace falta

Esta es la parte que decide, y el resultado **no es el que esperaba la spec**.

### 3.1 · Hallazgo: 24 de las 31 tablas no tienen `tiemod` en la base real

`config/tables_sigrid.yaml` declara `incremental_column: tiemod` en **18**
tablas. Consultado el catálogo de Sigrid (`INFORMATION_SCHEMA.COLUMNS`, una
consulta de lectura), la columna existe de verdad en **7**:

| Tienen `tiemod` de verdad (7) | Filas | Peso en la ingesta |
|---|---|---|
| `con` | 2,17 M | 6,7 % |
| `auxobrtip`, `auxobrcla`, `auxobramb`, `auxobrtca`, `auxpro`, `auxmun` | < 60 k entre todas | 0,2 % |

| **NO la tienen (24)** |
|---|
| `obrparpre`, `dcapro`, `dcfpro`, `dca`, `dcf`, `ctrpro`, `obrparpar`, `pag`, `cob`, `com`, `comlin`, `comprv`, `ctr`, `obr`, `obrfas`, `obrfasamb`, `obrctr`, `conext`, `cen`, `condir`, `obrprv`, `prv`, `dcfprodes`, `rec` |

**En la lista de las que no la tienen están las cuatro que se llevan el 86 % del
tiempo.** El primer intento de leer `SELECT TOP 5 [ide], [tiemod] FROM
[dbo].[obr]` devolvió, literalmente:

```
HTTP 500 de sigrid-api: ... [42S22] [Microsoft][ODBC Driver 18 for SQL Server]
[SQL Server]El nombre de columna 'tiemod' no es válido. (207)
```

Y las columnas reales de `obrparpre` —la tabla de 13,8 M filas que cuesta el
61 % de la ingesta— son estas 22, **sin una sola fecha ni marca de
modificación**:

```
ide, obride, paride, amb, fas, can, med, haymed, pre, tex, planif,
totinc, totinc2, des, haydes, coepas, varest, tipdes, marseg, canedi,
impcoe, impOcoe
```

`dcapro`, `dcfpro`, `dca` y `pag` sí tienen fechas (`fec`, `fecdoc`, `fecimp`,
`garfec`, `fecven`, `fecrea`…), pero **todas son fechas de negocio** —cuándo se
emitió el albarán, cuándo vence el efecto—, no de última modificación. Una
línea de albarán de enero que se corrige hoy sigue teniendo `fec` de enero.

**Corolario sobre la premisa heredada de F-009.** La spec corrigió el recuento
del diccionario (`tiemod` en 232 filas, ~190 tablas) y concluyó que la marca
«está en todas las tablas de negocio que ingerimos». **Eso no es cierto en la
base de datos real.** El diccionario es el autodocumentador de la v.20240618
(documento de 2024-11-06) y describe entidades lógicas: `tiemod` aparece
sobre todo en tablas «Propiedades de `con`», y las tablas de detalle que
nosotros ingerimos no lo heredan como columna física. La única forma de
saberlo era mirar el catálogo, y la spec ya lo había previsto: *«lo que NO está
acreditado es que Sigrid la mantenga»*. La respuesta llegó antes y peor: en las
tablas que importan **no está**.

### 3.2 · Lo que sí quedó acreditado de `tiemod`, donde existe

En `con` la columna existe, está mantenida y **es una marca completa de fecha y
hora**, no una fracción del día. Cinco filas leídas de `dbo.con`:

| `ide` | `tiemod` | Interpretado como TDateTime (días desde 1899-12-30) |
|---|---|---|
| 2820171 | 46253,827465 | 2026-08-19 19:51:32 |
| 2820170 | 46253,665475 | 2026-08-19 15:58:17 |
| 2820169 | 46253,663530 | 2026-08-19 15:55:28 |

Es decir: **donde existe, `tiemod` serviría** —avanza, tiene resolución de
segundos y llega hasta hoy—. El problema no es su calidad; es su ausencia.

### 3.3 · Veredicto de R7, tabla por tabla

| Veredicto | Tablas | Motivo |
|---|---|---|
| `SIRVE` (potencial) | `con` + 6 catálogos = **7** | la columna existe, avanza y tiene resolución de segundos (§3.2) |
| `NO SIRVE` | **24** | la columna **no existe** en Sigrid ⇒ `raw._source_tiemod` es nula en el 100 % de sus filas |

El veredicto de las 24 se emite **sin necesidad de dos cargas**: `NO SIRVE` por
columna toda nula es precisamente el caso que `veredicto_tiemod` resuelve con
una sola fotografía, y aquí se ha resuelto todavía más arriba, en el origen.

> **Para el reviewer**: la comparación de dos fotografías de `_source_tiemod`
> (R7 con `--comparar-con`) sigue siendo una verificación MANUAL pendiente
> (§7), pero **ya no puede cambiar la decisión**: ninguna comparación puede
> hacer aparecer una columna que no existe en el origen.

---

## 4 · R5 y R5-bis · Barrido de tamaños de página: PENDIENTE (MANUAL del humano)

`bench-sigrid` está implementado, probado y listo. **No se ha ejecutado**: la
spec (T7) lo reserva al humano porque lanza peticiones sostenidas contra el SQL
Server de producción de Sigrid y quien elige el momento es él.

```bash
python main.py bench-sigrid --tabla obrparpre --paginas 1000,5000,10000,20000 --out bench_sigrid.csv
```

Queda por acreditar, por tanto: si subir el `page_size` de 10.000 a 20.000
compra tiempo (R4) y cuál es el corte real del balanceador (R5-bis). **Ninguna
de las dos cosas afecta a la decisión de este informe**: aunque la extracción
fuera instantánea, el techo son 32,9 min de 165.

Sí hay un dato nuevo que llevarse a T8-bis: `progress/current.md` (2026-08-18)
recoge que la instancia `dev` corre **`MAX_ALLOWED_ROWS` 500.000** y
**`MAX_QUERY_TIMEOUT_SECONDS` 230**, no los 1.000 / 120 s del documento. Sigue
siendo trabajo del dueño de `sigrid-api`; **este proyecto no edita
`azure-apps/sigrid_api.md`** y no lo ha hecho.

---

## 5 · La puerta de DA-7, con los dos números al lado de sus dos umbrales

R8 exige exactamente esto: los números medidos junto a los límites, no una
valoración cualitativa.

| Criterio de DA-7 | Umbral | **Medido** | ¿Se cumple? |
|---|---|---|---|
| Ahorro estimado de la ingesta incremental | **≥ 20 min** | **2,25 min** | **NO** (11 % del umbral) |
| Peso de la ingesta en el tiempo total | **≥ 40 %** | **19,9 %** | **NO** (la mitad del umbral) |

**Cómo se calcula el ahorro de 2,25 min, y por qué es un TECHO y no una
estimación.** El tiempo de ingesta se reparte así (media de las tres cargas):

| | segundos | minutos | % de la ingesta |
|---|---|---|---|
| Tablas con marca de modificación **real** (7) | 134,9 | **2,25** | 6,9 % |
| Tablas **sin** ninguna marca (24) | 1.831,3 | 30,52 | 93,1 % |
| **Total ingesta** | 1.966,2 | 32,77 | 100 % |

Aunque las siete tablas con `tiemod` pasaran a costar **cero** —imposible: hay
que pedir su esquema y al menos una página— la carga bajaría de 165,2 a 163,0
minutos. Las otras 24 hay que traerlas enteras cada noche porque **no hay
forma de preguntarle a Sigrid qué ha cambiado en ellas**.

Y las dos condiciones de DA-7 van en **O**: basta con que una se cumpla. No se
cumple ninguna, y ninguna se queda cerca.

---

## 6 · RECOMENDACIÓN FIRMADA

> ## NO implementar el bloque B (R9–R19).
>
> Firmado por el implementer de F-011 el 2026-08-20, contra el umbral de DA-7,
> con los números del §5 y el hallazgo del §3.

Los tres motivos, por orden de peso:

1. **No hay watermark que usar.** No es que sea caro o arriesgado: la columna
   que sostenía todo el diseño no existe en las 24 tablas que se llevan el
   93 % del tiempo de ingesta. DA-4 ya previó este desenlace y lo cerró:
   *«si el veredicto de R7 es NO SIRVE, se renuncia a la ingesta incremental
   por watermark y el esfuerzo se lleva al build»*.
2. **El ahorro máximo es 2,25 min de 165.** El bloque B añadiría una máquina de
   estados nueva —tabla `_meta.ingesta_watermark`, decisión de modo global y
   por tabla, guardia de deriva, recarga completa de los domingos, cuatro
   ajustes de configuración nuevos— a un ETL que hoy es reproducible y
   aburrido, a cambio del 1,4 % del tiempo de carga.
3. **El sitio donde está el tiempo ya tiene feature.** `build_stg` son 110,7
   min (67,0 %). Es **F-025**, y DA-5 ya le dio prioridad sobre el bloque B
   *«si los números de la medición lo confirman»*. Lo confirman.

### 6.1 · Lo que se ha descartado explícitamente, para que no vuelva por la puerta de atrás

- **Cursor por `ide` («solo altas») como estrategia nocturna.** Es la única vía
  que llegaría al umbral: traería 1.688 filas en vez de 20 M. Y es la que R16
  prohíbe activar en silencio, con razón: solo ve **altas**. `obrparpre` guarda
  la cadena `planif` de cada partida, que se **edita** constantemente; una
  noche de solo altas dejaría el seguimiento con la planificación de ayer y
  nadie se enteraría. Descartada salvo que Negocio acepte por escrito esa
  pérdida.
- **Watermark propio por sumas de control.** Ya descartada en DA-4 (opción c) y
  ahora además inútil: leer 20 M de filas para saber cuáles cambiaron cuesta lo
  mismo que traérselas.
- **Acotar la extracción con el campo `where` del YAML** (opción b de DA-4).
  Sigue siendo viable y barata, pero **acota por negocio**, no por
  modificación: qué obras entran es DA-1, que sigue sin decidir. Su sitio es
  F-025, no aquí.

---

## 6.2 · FIRMA DEL HUMANO · 2026-08-20

> ## NO al bloque B. Firmado por el humano.

Aceptada la recomendación del §6 con los números del §5 delante: ahorro máximo
**2,25 min** frente al umbral de 20, e ingesta al **19,9 %** frente al umbral
del 40. Ninguna de las dos condiciones de DA-7 se cumple, y van en O.

El motivo de fondo pesa más que los números: **la marca de modificación no
existe en las 24 tablas que se llevan el 93 % de la ingesta**, así que no hay
nada que preguntarle a Sigrid. DA-4 ya había previsto por escrito este
desenlace y qué hacer entonces: llevar el esfuerzo al build.

**Consecuencia**: F-011 se cierra con el **bloque A entregado** —la medición,
que es el resultado— y el **bloque B descartado**. El trabajo se traslada a
**F-025**, donde está el tiempo de verdad: `build_stg`, 110,7 min, el 67,0 % de
la carga.

---

## 7 · Verificaciones MANUAL que quedan pendientes (todas del humano)

Ninguna cambia la recomendación; están aquí porque la spec las pide y porque
dos de ellas tienen valor por sí solas.

| # | Qué | Comando | Por qué sigue interesando |
|---|---|---|---|
| 1 | `perfil-carga` contra Azure | `python main.py perfil-carga` | Ejercita el comando contra `_meta.etl_runs` de verdad. **Necesita una regla de firewall para la IP del puesto**: es una escritura sobre un recurso compartido y la decide el humano |
| 2 | `diagnostico-tiemod` | `python main.py diagnostico-tiemod --out huella_tiemod_1.csv` | Confirmaría desde el datamart lo que el catálogo ya dijo: `_source_tiemod` nula en 24 tablas. **Ojo al coste**: recorre las tablas de `raw` enteras (20 M filas) con un `COUNT(DISTINCT)`, sobre el servidor compartido. Lanzarlo fuera de la ventana de carga |
| 3 | `bench-sigrid` (§4) | ver §4 | R4 y R5-bis siguen sin acreditar. Va contra producción de Sigrid: momento a elegir por el humano |
| 4 | **T8-bis**: avisar al dueño de `sigrid-api` | — | El documento del ecosistema sigue diciendo 1.000 filas y 120 s; los valores reales son otros. **Este proyecto no lo edita** |

---

## 8 · Hallazgos colaterales que conviene no perder

1. **`config/tables_sigrid.yaml` miente en 17 entradas.** Declara
   `incremental_column: tiemod` en 18 tablas y solo `con` la tiene. No rompe
   nada hoy —`ingest_raw_step` comprueba si la columna está en el esquema que
   devuelve Sigrid y, si no está, no la copia— pero es exactamente la
   documentación equivocada que hizo verosímil la premisa de F-009 durante
   meses. **Propuesta**: poner `null` en las 17, con el comentario de por qué.
   Es un cambio inerte en comportamiento y honesto en documentación; **no se ha
   hecho** porque toca la configuración de la ingesta y F-011 está en su parada.
2. **`raw._source_tiemod` está vacía en 24 de 31 tablas** y nadie lo sabía. La
   columna se creó para esto y no ha sido nunca útil ahí.
3. **La vía «documentos vía `con`».** En Sigrid, `dca`, `dcf`, `com`, `ctr` y
   `prv` son «Propiedades de `con`» y comparten `ide` con `con`, que **sí**
   tiene `tiemod`. Se les podría preguntar por su marca de modificación con un
   `JOIN`. Es elegante y **sigue sin servir**: esas cinco tablas suman ~130 s
   de los 1.966 (6,6 %), y `obrparpre`, `dcapro` y `dcfpro` —el 80 %— no son
   extensiones de `con`. Anotado para que nadie lo redescubra creyendo que
   cambia el resultado.
4. **La carga es notablemente estable**: `build_stg` 110,6 / 110,6 / 111,0 min
   en tres cargas de días distintos. Cualquier mejora que F-025 traiga se va a
   poder medir con precisión contra esta línea base.

---

## 9 · Qué desbloquea esta parada

- Si el humano **firma el NO**: F-011 se cierra entregando **solo el bloque A**
  (tres comandos de medición, 108 tests nuevos), tal como prevé T9 →
  «la feature salta a T21 y se cierra». El trabajo de rendimiento continúa en
  **F-025**, que ataca los 110,7 min del build.
- Si el humano **quiere seguir con el bloque B** pese a los números, hay que
  volver a la spec antes de escribir código: **R11, R12, R12-bis, R15, R17 y
  R19 están escritos sobre un watermark que no existe**, y habría que rediseñar
  el bloque entero sobre otra base (la única disponible sería el cursor por
  `ide`, con la pérdida de R16 aceptada por escrito).
