<!-- progress/impl_F-052_cierre.md -->
# F-052 · Cierre: los cuatro cambios requeridos por el review de la fase 2

Rama `feature/F-052-partidas-huerfanas`, cuatro commits (`ec516bd`, `ce3e9ac`,
`7216aa6`, `aad3412`). **Ni una línea de SQL ni del build**, como pedía el
encargo.

## AVISO QUE MANDA SOBRE TODO LO DEMÁS

**`check-cobertura` sale hoy en código 0, y ese verde NO PRUEBA NADA.** No lo
uses para cerrar la feature.

```
23 excepcion(es) declarada(s) y aceptada(s).
Cobertura stg -> mart · 0 combinacion(es) (obra x ambito) miradas, 0 cubierta(s)
OK   todo lo que entra en stg sale en mart, salvo lo declarado [...]
EXIT=0
```

Lo delata **«0 combinaciones miradas»**: sobre un `stg` completo tendría que
decir 56 miradas y 56 cubiertas (43 invisibles + 13 huérfanas). Dice cero porque
**`stg.plan_mensual` está truncada al 21,6 %**. La causa está medida, no
supuesta, en `_meta.etl_runs` de producción:

| id | paso | inicio | fin | estado |
|---|---|---|---|---|
| 2412 | `build_stg.build_plan_mensual.tramo_06` | 09-02 06:47:38 | — | **RUNNING** (muerto) |
| 2406 | `build_stg.build_plan_mensual` | 09-02 03:16:48 | — | **RUNNING** (muerto) |

La nocturna del 2026-09-02 murió en el **tramo 6 de 60** y dejó
`stg.plan_mensual` en **6.438.486 filas** (`pg_stat_user_tables`) de los ~29,7 M
que le tocan. Es la avería que motiva F-025. Con un quinto de las filas, las dos
consultas del guardián no traen ni una de las obras del veredicto, y **el verde
sale de no haber mirado nada**.

Es, literalmente, la observación 1 del review de la fase 1 —«`check-cobertura` da
verde sobre cero filas»— materializada contra producción. No la he podido cerrar
aquí: hacerlo exige contar el denominador, y eso es código del guardián.

**Lo que hay que hacer para tener el código 0 de verdad** (paso de cierre 6 de
`tasks.md`, que sigue vivo): una `stage` completa —o la primera nocturna que
termine— y volver a lanzar `python main.py check-cobertura --timeout 900`.
Entonces la salida debe decir **56 miradas, 56 cubiertas, ninguna fuera**. Yo no
he lanzado `stage`: son 8 h 15 de escritura contra el Postgres compartido, no
está en este encargo y el servidor lleva la hucha de créditos a cero.

**Lo que sí queda probado sin la base**, y es la parte que dependía de mí: el
YAML corregido tapa **el veredicto real que el reviewer midió**, replicado como
fixture en un test que corre en cada `init.sh` (abajo, fase RED).

## 1 · El `tipo` de cuatro excepciones (el defecto real) · `ec516bd`

`cobertura.py:61-65` filtra por `tipo`. Estaban declaradas `filas_huerfanas`
cuatro cosas que se manifiestan como **obra invisible**, así que no tapaban nada:
**15 de las 20** obras invisibles del veredicto venían de ahí.

**La causa es una y es la misma en las cuatro**, y con el código delante se ve:
una obra **sin ficha en `stg.obras`** es las dos cosas a la vez —todas sus filas
de `plan_mensual` son huérfanas (`sql_huerfanas`: `o.obra_id IS NULL`) **y** no
publica ni una en el fact (`sql_obras_invisibles`)—. La excepción tapaba la
mitad que ya nadie miraba y dejaba al aire la otra.

| Entrada | Antes | Ahora | Por qué |
|---|---|---|---|
| `OBRA PRUEBA` | `filas_huerfanas` | **`ambas`** | fuera de `stg.obras` por `con.cod !~ '[0-9]{5,}'` (`stg/03_obras.sql:113`) |
| `POSTVENTA` | `filas_huerfanas` | **`ambas`** | fuera por la lista negra (`:107`, códigos POSTV/POSTV2) |
| `VAR` | `filas_huerfanas` | **`ambas`** | fuera por la lista negra |
| `0606` | `filas_huerfanas` | **`ambas`** | el **ide perdido** por el desempate `rn = 1` no está en `stg.obras`; el ganador sí publica |

**Por qué `ambas` y no `obra_invisible`** en las cuatro: si sólo cambiara el tipo
a `obra_invisible`, las huérfanas que hoy tapaban volverían a salir. Las dos
manifestaciones tienen la misma causa única —no tener ficha—, y el día que la
causa se cierre desaparecen juntas.

**Y esto explica el «37 de 58 cubiertas» del review**, que si no no cuadra: la
0606 no aparece entre las huérfanas justamente **porque su excepción sí tapaba
ese lado**; lo que salía era el otro.

### Fase RED, ejecutada antes de tocar el YAML

Nuevo `tests/test_f052_cierre_excepciones.py`. `test_f052_cobertura.py` prueba el
**mecanismo** con filas inventadas y estaba bien; el defecto estaba en el
**contenido**, y eso sólo lo caza replicar el veredicto real.

```
$ python -m pytest tests/test_f052_cierre_excepciones.py -q
7 failed in 0.27s

E  AssertionError: quedan obras invisibles sin declarar: 0578 12 VIVIENDAS
   C/CANILLAS (MADRID) (obra 1286520) · ambito 8, ... 0606 PARQUE TEMÁTICO PUY DU
   FOU - LOTE 7 (TOLEDO) (obra 1581377) · ambito 3, ... 171104 OBRA PRUEBA 4
   (obra 1186269) · ambito 3, ... POSTV POSTVENTA (obra 870589) · ambito 11, ...
   VAR VARIOS (obra 870000) · ambito 11, ... 181001 OBRA CANILLAS (obra 1359231)
   · ambito 11          [44 combinaciones]
E  AssertionError: assert set() == {'0578', '0585', '0670', '0687'}
```

Con sólo los `tipo` corregidos: **3 failed, 4 passed**. Los tres que faltaban
eran el bloque 2. Tras él: **49 passed** (los dos ficheros de cobertura).

## 2 · Declarado el resto · `ce3e9ac`

Decisión del humano, y su motivo está escrito **en la cabecera del YAML**, que es
donde lo va a leer quien pregunte dentro de seis meses: *un guardián que nace en
rojo permanente manda un correo cada noche que no significa nada, y en dos
semanas no lo mira nadie; con todo declarado, el día que aparezca una obra
invisible nueva el correo significará algo.*

Trece entradas, ninguna sin motivo medido ni sin quién la cierra:

| Nº | Qué | Tipo | Feature |
|---|---|---|---|
| 2 | **0613** (150 huérfanas) y **0618** (76) | `filas_huerfanas` | **F-052** |
| 8 | **0578, 0585, 0670, 0687**, dos entradas cada una | `obra_invisible` + `ambito_id` 8 y 11 | **F-055** |
| 3 | **150414** MERCADO PROSPERIDAD (12), **150703** OBRA FORMACIÓN (6), **181001** OBRA CANILLAS (50) | `ambas` | — |

Tres decisiones que conviene no perder:

1. **0613 y 0618 se declaran como CERRADAS POR F-052, no como pendientes.** Sus
   150 + 76 = **226 filas** son exactamente las «226 filas de 183.756, a 0,00 €»
   que DA-2 anticipó como movimiento máximo fuera de la 0599. Residuo previsto y
   medido.
2. **Las cuatro ciegas en master van ACOTADAS con `ambito_id`**, dos entradas por
   obra en vez de una sin ámbito. Cuesta cuatro líneas más y compra esto: si
   mañana una de ellas desapareciera del **ámbito 3 —coste real, dinero—**, el
   guardián grita. Es la respuesta directa a la *desviación 4* de la fase 1, que
   se aceptó «con seguimiento» porque una excepción sin acotar tapa cualquier
   cosa.
3. **Las papeleras de seis dígitos se declaran POR CÓDIGO, no por nombre.**
   `CANILLAS` como `patron_nombre` casaría también con la **0578**, que es una
   obra de verdad. Una excepción que tapa una obra real es peor que ninguna.

**F-055 dada de alta** (`harness/features.json`, prioridad 4, rigor estándar,
`feature/F-055-obras-ciegas-en-master`), y **como pregunta abierta, no como
diagnóstico**: las cuatro publican con normalidad en los ámbitos reales 3 y 7 y
tienen cero filas en 8 y 11. Puede ser legítimo —el build de planificado elige la
versión master vigente, y una obra sin versión vigente no tiene filas ahí por
diseño, que es justo por lo que R14 compara **presencia y no conteo**— o ser otro
agujero. Su ficha lleva la pista por donde empezar
(`stg.version_master_vigente` y el campo extendido `cod 15`) y, entre sus
`acceptance`, retirar sus ocho excepciones y bajar el trinquete.

**`EXCEPCIONES_MAX`: 10 → 23.** Sube porque el humano decidió declarar, y el
motivo, el desglose (2 + 8 + 3) y la fecha de vuelta están escritos en el propio
test. **Es la única vez que sube**: 8 las cierra F-055 y 2 las cerró F-052, así
que **baja a 15** en cuanto F-055 conteste.

## 3 · T13, T14 y T15 marcadas con su evidencia · `7216aa6`

Estaban hechas y sin marcar; era el primero de los tres motivos por los que C5 no
se podía marcar.

* **T13 · el coste real del guardián.** Con los 30 s por defecto **no vuelve**:
  necesita `--timeout 900`. La misma noche `check-unicidad` dejó **3 objetos sin
  comprobar** (antes era 1) y `check-cierres` murió con `QueryCanceled` a la
  primera. No es un defecto del guardián: es el `B1ms` sin créditos tras 12 h 48
  de escritura. **DA-4 se confirma sin cambios**: dentro de `run-all` avisa y no
  bloquea, así que un timeout suyo no tumba la nocturna.
* **T14 · las cuatro huellas del ANTES**, capturadas el 01-sep antes de tocar la
  base, con tamaño y hora: `stg` 865.076 B (10:05), `mart` 1.264.271 B (09:56),
  `dimension` 39.196 B (09:56), `cierre` 1.236.693 B (09:56). Las del DESPUÉS,
  sobre el **mismo `raw`**, al lado. **Viven en la raíz y los ignora
  `.gitignore`**: son la evidencia de R11, archívense.
* **T15 · la línea base.** ANTES (SQL viejo): **183.824 filas huérfanas y 21
  obras invisibles**. DESPUÉS: **294 y 20 en 43 combinaciones**. El guardián
  midiendo su propio arreglo: **−99,8 %**.

## 4 · Las dos inexactitudes de `current.md` · `aad3412`

Van **como cita dentro del párrafo equivocado**, sin borrarlo: lo que se dijo mal
el 01-sep forma parte de lo que hay que recordar.

1. «Ninguna de las 294 es de F-052» → **falso**: 0613 lleva 150 y 0618 lleva 76.
   El párrafo además **mezclaba las dos listas**: 0585, 0687, 0578, 0670 y 0606
   no están entre las huérfanas sino entre las **invisibles**, y de esas cinco
   sólo la 0606 es F-053 —las otras cuatro son **F-055**—.
2. «Las 214 diferencias» → **ese número no existe**. Sale de sumar 144 (bloque
   *Importes* de `mart`) y 70 (bloque *master* de `stg`), dos métricas distintas
   con el mismo nombre. Los reales: **`stg` 42 + 152**, **`mart` 0 + 144**, y lo
   que decide es que las cuatro huellas señalan **una sola obra, la 0599**.
   Corregida también la tabla de huellas, que invitaba a esa suma.

## Lo que queda fuera de este encargo (no lo he tocado)

* **El paso de cierre 6 sigue abierto** por lo del aviso de arriba: hace falta un
  `stg` completo para que el código 0 signifique algo.
* **Paso 6 bis**: sigue sin recibirse el correo de la alerta.
* **C5 y el veredicto final** los marca el reviewer, no yo.
* No he tocado el SQL, el build, ni `dev`/`main`. Ningún `git push`.

## Nota operativa para el líder

Al empezar, el repositorio estaba en `feature/F-025-ventana-negocio-build` con
**cambios sin commitear en `BACKLOG.md` y `harness/features.json`** (F-025 a
`spec_ready`). Los guardé con `git stash push` —mensaje *«F-025 spec_ready
pendiente del lider…»*, es `stash@{0}`— para trabajar en la rama de F-052 con el
árbol limpio. **Hay que recuperarlos**: `git checkout
feature/F-025-ventana-negocio-build && git stash pop`.

**Y avisa de un conflicto que va a salir**: ese stash toca
`harness/features.json` y yo también (F-055 y F-025 son entradas distintas del
mismo fichero, así que el `pop` conflictúa en cuanto F-052 esté en esa rama). Se
resuelve quedándose con **las dos**: F-025 a `spec_ready` **y** F-055 dada de
alta. Dejo `HEAD` en `feature/F-052-partidas-huerfanas`, que es donde el reviewer
tiene que mirar.

## Evidencias

| Evidencia | Valor |
|---|---|
| **Tests ejecutados** | `bash harness/init.sh` **código 0**: **2.985 passed, 130 skipped**. Son **7 más** que los 2.978 del review, y los 7 son los de `test_f052_cierre_excepciones.py`. Los dos ficheros de cobertura por separado: **49 passed en 3,19 s** |
| **Fase RED** | **7 failed** antes de tocar el YAML, traza pegada arriba. Tras corregir los `tipo`: 3 failed / 4 passed. Tras declarar: 49 passed |
| **Cobertura de las líneas cambiadas** | `PUERTA COBERTURA: N/A (F-052 no cambia líneas Python de producción frente a dev)`. Aquí el N/A **es correcto y no un artefacto**: este cierre no toca ni una línea de Python de producción —YAML, JSON, Markdown y un fichero de tests—. Vale la medición de la fase 1, **100,0 % de 504 líneas** |
| **Mutantes generados y supervivientes** | **N/A**: T21 exenta por decisión escrita del humano del 2026-08-31. La sustituyen las cuatro huellas (T27-T30) |
| **Tiempo de la suite** | **3.724,24 s (1 h 02 min)**, contra los **327 s** que midió el reviewer ayer con la misma suite. **Factor 11, y no es del código**: es el `B1ms` con la hucha de créditos a cero, el mismo estrangulamiento que mató la nocturna. Dato para F-025 |
| **Puerta de tamaño** | `PUERTA TAMAÑO: F-052 dentro de los topes` (requirements 150/150, design 242/250, **impl 220/220**, review 140/140). Este informe, 217 |
| **`check-cobertura` contra la base** | **exit 0 pero NO VÁLIDO**: 0 combinaciones miradas sobre un `stg` al 21,6 % |
| **Excepciones declaradas** | 10 → **23** (2 F-052 + 8 F-055 + 3 papeleras) |
