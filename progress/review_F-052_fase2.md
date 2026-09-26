<!-- progress/review_F-052_fase2.md -->
# F-052 · Review de la FASE 2 (pasada 2, incremental)

**Revisión incremental desde `3c9826d`** (pasada 2), rango `3c9826d..cd18e09`, 4
commits. Lo aprobado en `progress/review_F-052.md` queda dado por bueno. El delta
**no trae una línea de código** —son `current.md` y el review de la fase 1—, así
que reviso entero **el resultado en la base**, más `bash harness/init.sh`.

## Veredicto: **RECHAZADO** (CHANGES_REQUESTED)

**Léase bien el motivo: el arreglo es correcto y está verificado.** No he
encontrado un defecto en el SQL, en los datos publicados ni en el despliegue, y lo
he comprobado yo contra la base y contra Azure, no leyendo el acta. Falta el
**cierre**: tres tareas sin marcar, dos pasos de cierre incumplidos y **un defecto
real en las excepciones de T10**.

**Nivel de rigor `critico`.** T21 (mutación) **N/A por la decisión escrita del
humano del 2026-08-31**, ya juzgada en la fase 1; RM1, RM2, RM5 y RM6, N/A por no
haber campaña. La sustituyen las cuatro huellas, y **esas las he ejecutado yo**.

## Lo que verifiqué por mi cuenta (solo lectura, 900 s)

| Requisito | Resultado |
|---|---|
| **R7** | `stg.partidas` **390.505** de `raw.obrparpar` **390.524** → faltan **19 exactas**: **7 con `cod` vacío + 12 con código**, y esos 12 son el bucle mutuo 279988↔279997 con sus 8 hermanos, más 310512 y 375474. Literalmente lo que R7 exige |
| **R8** | 0599 en `stg.partidas`: **1.440**. Exacto |
| **R3 · R4** | `capitulo_padre_id` sin fila publicada: **0**. `cardinality(ruta) <> nivel+1`: **0**. Segmento vacío: **0** |
| **R9** | ámbitos de la 0599 en el fact: **3:21.051 · 7:18.266 · 8:9.999 · 11:8.999**. Los ámbitos 7 y 11, inexistentes ayer, están |
| **R10** | cierre 0599 2022-12: VENTA 4.066.989,23 · **DIRECTOS 2.624.793,46** · GASTOS 3.994.386,13 · **BENEFICIO 72.603,10** → margen **1,785 %**. Al céntimo |
| **R12 · R20-R22** | duplicados de `(obra_id, partida_id, anio_mes, escenario)`: **0**. `check-diccionario`: biyección **103/103**, publicado = árbol, **versión 12** |
| **R29 · despliegue** | `alert-...-cobertura` **existe y habilitada**, sev 2, grupo de acción con **2 destinatarios**; job con imagen **`r20260902-0019`** y cron **`0 2 * * *`**. La lección de F-047, respetada |
| **C1** | `bash harness/init.sh` **exit 0**, 2.978 passed, 130 skipped, 327 s |

**El matiz de R7 juega a favor:** la spec decía 390.501 sobre 390.520 y hoy son
390.505 sobre 390.524 porque `raw` creció 4 filas entre el 08-31 y la huella del
ANTES; la diferencia sigue siendo 19 y son las previstas. Y entre ANTES y DESPUÉS
no hubo `ingest`: el cron se apagó a las 22:00 del 09-01 y aún no ha disparado.

## 1 · El KO de master: **SÍ es falso positivo. Dictamen firme.**

Comprobado por **dos caminos independientes**, sin fiarme del acta:

1. **Diff propio de los 8 CSV**, sin código del proyecto: `dimension` 1 clave con
   diferencia, `stg` 84, `mart` 80, `cierre` 28. **La única obra que aparece en
   las cuatro es la 0599.** Ni una más.
2. **`comparar-huellas` ejecutado por mí** con `--obras-esperadas
   0599,0613,0618,0630,0565,0686`: `dimension` y `cierre` **exit 0**; `stg` y
   `mart` **exit 1** con **una sola línea KO, la de master** (70 y 48 cambios). La
   línea «se mueven N obra(s) FUERA de la lista esperada» **no sale en ninguna**.

La contradicción es de manual: **R9 exige que aparezca `0599 × ámbito 11`**, y el
11 es master. La regla que F-042 dejó en `huella.py:239` marca como desbordamiento
cualquier cambio en 8 u 11 sin mirar de qué obra. **Marca como error justo lo que
esta spec pide.** Falso positivo, confirmado. (Y «mart 144 diferencias, stg 70»
son dos métricas distintas con el mismo nombre: 144 es el bloque *Importes* de
`mart`, 70 el bloque *master* de `stg`, y su suma «214» no significa nada. Reales:
`stg` 42 + 152; `mart` 0 + 144. **Todas de la 0599**, que es lo que decide.)

## 2 · ¿Se puede marcar C5? **No todavía.**

**C1** [x] · **C2** [x] · **C3** [x] y **C3 bis N/A** (el delta no toca código ni
`docs/referencia/`) · **C4** [x], con R7-R12 ya juzgables y verificados arriba ·
**C4 bis** [x] con los N/A de la fase 1 · **C4 ter N/A** (sin
`rutas_sensibles.json`). **C5 [ ]**, por tres cosas concretas:

1. **`tasks.md` sigue con T13, T14 y T15 en `[ ]`** y sin commit `F-052 T13:`. El
   trabajo está hecho y la evidencia existe; el fichero no lo dice.
2. **Paso de cierre 6 incumplido**: exige `check-cobertura` **código 0** lanzado a
   mano. Lo he lanzado: **exit 1**. Ver el punto 3.
3. **Paso de cierre 6 bis incumplido**: exige provocar el marcador y **comprobar
   que llega el correo**; `current.md` lo reconoce. La regla está desplegada y el
   job lleva la imagen nueva, así que la nocturna de las 02:00 UTC lo resuelve.

**Sobre la puerta de cobertura:** `init.sh` imprime `PUERTA COBERTURA: N/A (F-052
no cambia líneas Python de producción frente a dev)`, **artefacto de haber movido
`dev` y `main` a `cd18e09` antes de cerrar la review**: el alcance contra `dev` es
vacío porque `dev == HEAD`. Vale la medición de la fase 1, **100,0 % de 504
líneas**; queda la lección de que mergear antes de aprobar apaga las puertas.

## 3 · `check-cobertura` en KO: **parte de ese rojo SÍ es de F-052**

Ejecutado por mí, `--timeout 900`, **exit 1**: 20 obras invisibles en 43
combinaciones, 294 filas huérfanas en 13, 10 excepciones, 37 de 58 cubiertas.
**`current.md` se equivoca al decir que ninguna de las 294 es de F-052.** Reales:
**0613 RICHMOND PARK 150** (ámbitos 3, 7, 8, 11), **0618 SOTOGRANDE 76** (3, 8,
11), y 12 + 6 + 50 de MERCADO PROSPERIDAD, OBRA FORMACIÓN y OBRA CANILLAS.
**0613 y 0618 son dos de las SEIS obras de F-052**, y sus 150+76 = **226 filas son
exactamente las «226 filas de 183.756, a 0,00 €» que la propia spec anticipó**
como movimiento máximo fuera de la 0599. Y 0585, 0687, 0578, 0670 y 0606 **no
están entre las huérfanas**: están en la lista de **obras invisibles**, que es
otra. El acta mezcla las dos listas.

**Y hay un defecto real en T10.** Las excepciones se filtran por `tipo`
(`cobertura.py:61-65`) y varias declaran el que no es: **0606 PUY DU FOU**,
declarada `filas_huerfanas`, sale como **obra invisible** en los cuatro ámbitos;
**`OBRA PRUEBA`, `POSTVENTA` y `VAR`**, también `filas_huerfanas`, salen **todas**
como invisibles —15 de las 20—. Ninguna excepción tapa nada. El guardián no está
rojo solo «por causas ajenas»: lo está en buena parte **porque las excepciones que
F-052 escribió no casan con cómo se manifiestan esas obras**. Se arregla aquí, no
en F-053, y cierra la **desviación 4** de la fase 1: hoy
`EXCEPCIONES_MAX` pone un trinquete sobre diez declaraciones de las que varias
apuntan al hallazgo equivocado. **Respuesta a la pregunta:** cerrar con el
guardián en rojo vale **solo si el rojo está declarado y es ajeno**, y hoy no lo
está; arreglado eso, el residual se declara por escrito y se cierra sin problema.

## Cambios requeridos (cuatro, ninguno toca el SQL)

1. **`config/cobertura_excepciones.yaml`**: corregir el `tipo` de **0606** y de los
   patrones **`OBRA PRUEBA`**, **`POSTVENTA`** y **`VAR`** a `ambas` (u
   `obra_invisible`), que es como se manifiestan. `EXCEPCIONES_MAX` solo se toca si
   cambia el nº de entradas, y nunca al alza sin motivo.
2. **Declarar o resolver lo que quede**: **0613** (150) y **0618** (76), de las
   seis de esta feature, más las invisibles **0578, 0585, 0670, 0687** y las
   administrativas restantes, con motivo y feature. Si el humano prefiere no
   declararlas, **el paso de cierre 6 de `tasks.md` se reescribe** dejando escrito
   que el guardián queda rojo con esta línea base.
3. **`tasks.md`**: marcar **T13, T14 y T15** con su evidencia (tiempos de
   `check-cobertura`, los cuatro CSV del ANTES, veredicto de línea base) y commit.
4. **`current.md`**: corregir las dos inexactitudes —reparto de las 294 huérfanas
   y «144 / 70 / 214 diferencias»— con los números de este informe.

## Deuda declarada, que NO bloquea

1. **`comparar-huellas` no distingue obra esperada en master.** Ficharlo: toda
   feature futura que toque master repetirá este razonamiento a mano.
2. **El correo de la alerta sigue sin recibirse.** Mirar la nocturna de las 02:00
   UTC del 09-02, ya con `r20260902-0019`, y anotar el resultado.
3. `mart.yaml` fecha la reconstrucción el **2026-08-31** y fue el **2026-09-01**.
4. **R9 predijo ~183.756 filas nuevas en el fact y han entrado 55.165** (fact de
   5.297.341 a **5.352.553**; la 0599 de 3.150 a 58.315). Se cumple por su letra
   —decía «gana **hasta**»—, pero el factor 3,3 **no está explicado en ningún
   sitio**: es el filtro de versión vigente del build.
5. Los ocho CSV de huella (5,6 MB) viven en la raíz, ignorados por `.gitignore`:
   son la evidencia de R11, archívense. Y **`dev` y `main` ya están en `cd18e09`**.

**Automejora (propuesta, no aplicada).** Mantengo la de la fase 1
(`APPROVED_FASE_1`) y añado una: **`init.sh` debería distinguir «cobertura N/A
porque no hay líneas Python» de «cobertura N/A porque la rama ya está mergeada en
`dev`»**. Hoy imprimen igual, y la segunda es una puerta que se apaga sola justo
cuando más falta hace.
