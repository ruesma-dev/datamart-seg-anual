<!-- progress/review_F-006.md -->
# F-006 · Review — el diccionario semántico

> **F-006, bloques A–D, E y F parcial: APROBADO** en la sexta pasada. La septima
> pasada revisa el diccionario completo (los 53 objetos restantes) y lo RECHAZA.
>
> Este fichero tiene **dieciséis pasadas**, de la más reciente a la más antigua. Se
> conservan íntegras: son lo que se pidió corregir cada vez y el patrón contra el
> que se contrasta la siguiente. Leídas al revés cuentan cómo un diccionario que
> parecía correcto resultó tener un defecto sistemático en dos tercios de sus
> fichas, y cómo se cerró: derivando la comprobación en vez de revisando a ojo.

---

# DECIMOSEXTA PASADA · la mejor tanda, y la puerta que la acreditaba no mide nada

**Veredicto: RECHAZADO.** Y quiero separar bien las dos cosas, porque el reparto
importa más que nunca:

**Esta es la mejor tanda de las dieciséis.** La formulación nueva es exacta, los
tres números están medidos y son coherentes, el error de paso 22 → 9 estaba bien
visto y bien corregido, `ocultar` viaja en una forma que sí resuelve lo que
planteé, `_ACUMULADAS` se deriva de verdad, y **por primera vez una comprobación
ataca la clase y no el caso** — y una de sus dos mitades funciona.

**Y sin embargo bloquea, por algo que no es de esta tanda ni del implementer**:
la puerta de mutación del arnés **declara «0 supervivientes» sin haber comprobado
nada**. Lo he demostrado con su control. Eso invalida la evidencia que llevamos
dieciséis pasadas citando, **incluida la campaña que yo mismo lancé hace un rato**
y que también dio 254/254.

Los tres motivos, por orden de gravedad:

1. **La puerta de mutación falla en verde** (fallo del arnés, afecta a otras
   features).
2. **El guardián de coherencia tiene tres vías de evasión**, una de las cuales lo
   deja inerte hoy mismo.
3. **La corrección 22 → 9 llegó a la cabecera y no a las fichas de columna**, y
   una frase publicada al agente le remite a una consulta que devuelve otro
   número.

**Nivel de rigor: `critico`.** **Entorno:** `init.sh` verde — **1982 pasados**,
124 saltados, cobertura **98,1 %** de 979 líneas. Árbol limpio, sin `push`.

## GRAVE · La puerta de mutación del arnés da «0 supervivientes» sin comprobar nada

Esto no es un defecto de F-006 ni del implementer. **Es un fallo del arnés**, lo
he demostrado de punta a punta, y afecta a todas las features que hayan pasado
por esta puerta. Lo pongo el primero porque invalida una evidencia que llevamos
dieciséis pasadas dando por buena, incluida la que yo mismo generé hace un rato.

### El hecho

El mutante `and` → `or` en `diccionario_sql.py:297` —línea en alcance, operador
del catálogo del propio arnés— **sobrevive a la suite completa**:

| | Resultado |
|---|---|
| Copia con `.env`, **con** el mutante | 1976 pasados, 2 fallos (de entorno git) |
| Copia con `.env`, **sin** el mutante (control) | 1976 pasados, **los mismos 2 fallos** |

Idénticos. El mutante no cambia nada: **ningún test lo caza**. Y sin embargo
`progress/mutacion_F-006.md` declara 254/254 muertos, y **mi propia campaña
independiente también** —la lancé con el bytecode borrado y dio 254 muertos, 0
supervivientes, 688,3 s—. Las dos se equivocan igual.

### Por qué, que es lo accionable

Dos piezas de `harness/mutacion.py` que por separado son razonables:

```python
self.argumentos = argumentos or ["-x", "-q", "--tb=no", "-p", "no:cacheprovider"]
...
if proceso.returncode in (0, PYTEST_SIN_TESTS):
    return SUPERVIVIENTE
return MUERTO
```

**Cualquier** salida distinta de cero cuenta como mutante cazado. Y la campaña
paralela corre cada evaluador **en un `git worktree` con HEAD detached**. Ahí:

```
FAILED tests/test_f015_cobertura.py::test_f015_r12_la_rama_actual_se_lee_de_git
!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!
1 failed, 1539 passed
```

En un worktree detached **no hay rama actual**, así que ese test falla. Y con
`-x` la suite para en él, antes de llegar a los tests que sí comprobarían el
mutante. Control obligado, y lo hice: **el mismo worktree sin ningún mutante da
exactamente el mismo fallo**. La suite está en rojo **antes** de mutar nada.

De ahí que todo salga «muerto»: no porque los tests cacen al mutante, sino porque
la suite ya venía roja por un motivo ajeno. **El «0 supervivientes» es un
artefacto de medición**, no evidencia.

Y es la peor forma de fallar que puede tener una puerta de calidad: **falla en
verde**. Un mutante que sobrevive se declara muerto; nadie se entera; y el número
ocupa el sitio de la evidencia en el checkpoint, así que quien lo lee ya ha
terminado de mirar. Es exactamente lo que el implementer describió de los
recuentos —«parece evidencia»— llevado a su extremo.

### Qué hay que arreglar, y dónde

En `harness/mutacion.py`, y de ahí a **`arnes-base`** por la regla de propagación:

1. **Exigir línea base verde antes de empezar.** Correr la suite sin mutar en el
   entorno donde se va a evaluar y **abortar la campaña** si no da returncode 0.
   Es la comprobación que convierte el resultado en interpretable.
2. **Distinguir «falló por el mutante» de «falló por otra cosa».** Como mínimo,
   comparar el conjunto de tests fallidos con el de la línea base; un mutante
   está muerto si falla **algo que antes pasaba**.
3. **Revisar `-x`**: parar al primer fallo hace que el orden de recolección
   decida el veredicto.
4. Y quitar del camino la causa concreta: `test_f015_r12` no debería fallar por
   ejecutarse en un worktree detached, o debería saltarse ahí.

### Alcance del daño

**No sé cuántas campañas anteriores están afectadas y no lo voy a afirmar sin
medirlo**, pero la lista de candidatas está a la vista en `progress/`:
`mutacion_F-005.md`, `F-015`, `F-016`, `F-019`, `F-020`, `F-024`, `F-003`,
`F-004`, `F-011`. Todas las que declaren 0 supervivientes y se hayan lanzado en
modo paralelo merecen repetirse con la línea base arreglada. Es trabajo, y es
inevitable: la alternativa es seguir citando como evidencia un número que hoy
sabemos que no la da.

**Para F-006 en concreto**: no digo que la suite sea mala —la cobertura real es
del 98,1 % y los tests de esta feature son de los mejores que he revisado—. Digo
que **la campaña no ha demostrado lo que dice demostrar**, y que al menos un
mutante vivo lo prueba.

## MOTIVO 3 · La corrección 22 → 9 llegó a un sitio y no a los otros

El error de paso estaba bien visto: en el fact son **9 obras**, no 22; las 22
tienen fases duplicadas y solo 9 llegan a producir filas duplicadas. La cadena
**22 → 9 → 8** es coherente y decreciente, que es justo lo que tenía que salir.
Mi objeción de la pasada anterior —«deberían ser 22 en los tres sitios»— **era
mía y era el mismo cruce que ellos detectaron**.

Pero la corrección no viajó entera. Medido sobre el YAML:

| Ficha de columna | dice «22 obras» | dice «9 obras» |
|---|---|---|
| `fact_seguimiento_categoria.importe_origen` | **sí** | no |
| `fact_seguimiento_categoria.importe_origen_raw` | **sí** | no |
| `v_pbi_fact_categoria.importe_origen` | **sí** | no |

**Las tres fichas de columna que llevan el aviso siguen con la cifra que el
propio informe declara mal atribuida, y en ninguna aparece el 9.** La cabecera
del fact sí explica el 22 → 9; las columnas de los objetos de categoría, no. Es
la tercera variante del mismo patrón: la corrección llega a un nivel y no al
otro, y el guardián de coherencia no lo caza porque comprueba que aparezca
«DOBLADO», no que las cifras concuerden.

### Y una afirmación falsa publicada al agente

Las dos cabeceras dicen, literalmente:

> «**La consulta que da ese numero esta en el grano de
> `mart.fact_seguimiento_mensual`**, junto a la explicacion de por que 8.778, 37
> y 22 son numeros distintos…»

«Ese numero» es el del doblado —37 celdas, 39,07 M€—. **La consulta que hay allí
devuelve 8.778 y 9 obras**, que es otra cosa. Un agente que la ejecute para
comprobar el dato obtendrá algo que no cuadra con lo que acaba de leer, y lo
razonable será que desconfíe del aviso entero, que es lo peor que puede pasar
con el aviso que más importa.

Además esa misma frase sigue enumerando «8.778, 37 y **22**», el trío antiguo.

**Ninguno de estos dos tiene consulta publicada**: del «22 obras» y del «37
celdas / 39,07 M€» solo hay líneas de salida en el informe
(`impl_F-006.md:3855-3856` y `:4157`). El titular «Los tres números, cada uno con
su consulta» promete tres y entrega una. La de las 8.778 es correcta y sí mide lo
que se le atribuye.

## El guardián de coherencia, atacado: corta el caso real y tiene tres puertas

Me pediste que intentara escribir una ficha donde cabecera y columna se
contradigan sin que salte. **Lo conseguí tres veces**, en copias de
`git archive HEAD` que borré después; en las tres, `5 passed`.

**Primero, lo que sí corta.** `..._la_cabecera_no_contradice_a_sus_columnas`
**funciona**: le quité el «DOBLADO» de la cabecera dejándolo en las columnas —el
caso exacto de la decimoquinta pasada— y saltó. Es la primera vez en dieciséis
pasadas que una comprobación ataca la clase. No es poco y quiero que conste.

**Vía 1 · otra redacción.** `_TRANQUILIZADORAS` es una lista a mano de cuatro
frases. Inserté en el grano: «*Al agregar, el duplicado queda resuelto y el total
es fiable.*» Falso, tranquilizador, en el texto que ve el agente. Pasa. Es el
mismo problema que `_ACUMULADAS` tenía y que **esta misma tanda ha corregido**:
el arreglo se aplicó a un guardián y no al que se escribió a la vez.

**Vía 2 · partir la frase.** Los bloques usan plegado `>-`, que une líneas con un
espacio; pero **una línea en blanco produce un salto real**. Partí «La clave no
duplica»:

```
'la clave no duplica' literal presente? False
presente si normalizo espacios?          True
```

El lector la lee entera, el guardián no la ve. Misma piedra de las pasadas 8, 10,
13 y 15, y el repo **ya tiene** `tests/_texto.py::normalizado()`.

**Vía 3 · el salvoconducto, y es la que lo deja inerte.**

```python
if f in cabecera and "el numero de dentro" not in cabecera
```

La exención se evalúa sobre **toda la cabecera**, así que esa frase —que es
justamente la formulación nueva de esta tanda, siempre presente— habilita **todas**
las tranquilizadoras a la vez. Inserté una de la propia lista, «*Esta tabla no
esta afectada por el duplicado*»: pasa. Control: retiré el salvoconducto dejando
la misma frase y **entonces sí saltó**.

Conclusión: **`..._la_cabecera_no_afirma_lo_contrario` no puede fallar hoy por
ninguna de sus cuatro frases.** Está en verde por construcción.

**El arreglo es pequeño**: exigir la aclaración *junto a* cada frase y no en
cualquier parte; normalizar antes de comparar; y cambiar la lista por un
criterio, como ya se hizo con `_ACUMULADAS`.

### Y el guardián hermano se relajó en esta misma tanda

`..._todo_objeto_que_sirve_medidas_del_fact_avisa` pasó de exigir «8.778» a
aceptar **cualquiera de tres cadenas** (`"8.778"`, `"37 celdas"`, `"39,07"`). Un
objeto puede citar ahora el número de otro objeto —el de categoría en la ficha
del mensual, o al revés— y pasar. Justo cuando acabamos de descubrir que cruzar
esos números es el error fácil.

## Lo que está bien, y es la mayor parte

### La formulación nueva · exacta, y deja al agente mejor

> «**CUIDADO: el valor de `importe_origen` que hay guardado aqui esta DOBLADO en
> 37 celdas de 8 obras…** La clave no duplica —esta tabla agrega, asi que sale
> una sola fila y no hay fan-out—, pero **el numero de dentro si esta mal**…»

Es exacta en el punto difícil: **no niega que la clave sea única** —lo era, y
negarlo habría sido cambiar una mentira por otra—, sino que separa las dos cosas
que antes se confundían. Y el aviso va **antes** del matiz tranquilizador, no
después.

Deja al agente mejor por las dos vías: quien llama `listar_tablas` recibe el
«CUIDADO … DOBLADO» en la primera línea, cuando antes recibía solo «la clave no
duplica —comprobado—»; quien llama `describir_tabla` recibe cabecera y columna
**diciendo lo mismo**. No queda ninguna frase tranquilizadora suelta en el texto
actual.

### `ocultar` · viaja usable, y resuelve lo que planteé

Fui yo quien argumentó que debía viajar, así que juzgo si lo publicado sirve.
**Sirve.** Ejecuté la generación:

```
('ocultar', '_ingested_at',   0, '_ingested_at')
('ocultar', '_source_tiemod', 1, '_source_tiemod')
('ocultar', '_built_at',      2, '_built_at')
```

**La clave es el nombre de la columna**, no la posición: `mcp-bbdd` puede leerla
y comparar contra nombres de columna sin cablear nada, que era exactamente mi
objeción —la segunda copia de nuestra semántica no llega a existir—. El docstring
lo dice sin adornos: «con la posición, publicar la lista **no le habría servido
de nada**». Y `design.md:486-495` avisa de la asimetría lista-de-columnas /
gancho-de-tabla, que es lo que pediste comprobar.

**Pero el arreglo no está protegido por ningún test, y lo demostré**: eliminé las
dos líneas que lo hacen (`diccionario_sql.py:297-298`) y

```
ocultar publicado ahora: [('ocultar','0'), ('ocultar','1'), ('ocultar','2')]
19 passed
```

Vuelve a publicar la posición —lo que el propio docstring dice que no serviría de
nada— y **los 19 tests de contexto siguen verdes**. Es la misma función donde
vive el mutante superviviente, y no es casualidad: nadie comprueba esa línea.

**Un hueco de propagación**: `azure-apps/datamart_seg_anual.md` enumera lo que
lleva `_meta.diccionario_contexto` y **no incluye `ocultar`**. El contrato creció
en esta tanda y el documento del ecosistema se quedó en la versión anterior; la
regla del `CLAUDE.md` pide actualizarlo en el mismo trabajo. Y `design.md:159`
sigue describiendo `ocultar` como «patrones fnmatch de columnas técnicas» con dos
entradas, contradiciendo a su propia §4.4.

### `_ACUMULADAS`, derivada de verdad · con una pérdida silenciosa

Ahora es `_acumuladas_de(objeto)` con criterio real y del diccionario:
`agregacion == "ultimo_valor"` **y** que lleve unidad. No es circular —deriva de
`agregacion`/`unidad` y verifica `significado`— y tiene control anti-vacío.

**Pero ya produce un conjunto incompleto, en silencio.** Ejecutada:

```
mart.fact_seguimiento_mensual  -> ['importe_origen', 'importe_origen_raw', 'total_incurrido']
```

**Falta `can_origen`**, que era uno de los cuatro nombres de la lista a mano: no
declara `unidad`, así que el criterio la deja fuera. El control solo ancla dos de
los cuatro y solo sobre `fact_seguimiento_categoria`. **Basta borrar un `unidad:`
de un YAML para que una columna doblada salga de la lista y deje de exigírsele el
aviso**, sin que nada falle. Es la derivación correcta con el ancla demasiado
corta.

## La batería · SÍ, lanzadla, y lo que falta se corrige mientras corre

**Respuesta directa: la batería puede lanzarse ya.** Nada de lo que bloquea el
APROBADO bloquea la batería, y la distinción es limpia:

- **El contenido publicado está bien.** La formulación es exacta, `ocultar` viaja
  usable, y la biyección es 103/103 con lo publicado casando con el árbol.
- **Lo que está roto son instrumentos**: una puerta de calidad que mide mal y
  unos guardianes que se pueden esquivar. Protegen contra regresiones futuras, no
  contra lo que hay escrito hoy — y el texto de hoy lo he leído entero.
- **Ninguno de los arreglos toca las fichas**, salvo el del 22 → 9, que es
  sustituir una cifra en tres `significado`. Ni siquiera obliga a replantear
  nada: se republica y ya.

Lo que conviene tener delante al leer los resultados, porque la batería no lo
destapará —juzga plausibilidad, no números—:

1. **El «22 obras» de las tres fichas de columna es la cifra mal atribuida.** Si
   una respuesta la cita, no es del agente: es nuestra.
2. **La remisión «la consulta que da ese numero está en…» apunta a otra
   consulta.** Si alguien la sigue para verificar, no le va a cuadrar.
3. **El doblado sigue vivo en la base**: el diccionario avisa bien, pero el
   número seguirá mal hasta que se arregle el build. F-042 lo recoge como dato
   erróneo, que es la clasificación correcta.
4. **Los 39 «sin contradicción» no tienen la clave demostrada.**

## Checkpoints

| | Estado | Razón |
|---|---|---|
| **C1** Entorno en verde | `[x]` | 1982 pasados, 124 saltados, cobertura 98,1 % de 979 líneas. |
| **C2** Trazabilidad requisito → test | **`[ ]`** | La coherencia cabecera↔columnas tiene una mitad que funciona y otra inerte; el arreglo de `ocultar` no lo protege ningún test (demostrado); `_acumuladas_de` pierde `can_origen` en silencio. |
| **C3** Diff conforme al diseño | `[x]` | Solo los ficheros previstos. `design.md` §4.4 actualizado, aunque su §159 se contradice. |
| **C3 bis** Sin secretos ni prints | `[x]` | Sin GUID ni correo en el árbol. |
| **C4** Convenciones y veracidad | **`[ ]`** | «La consulta que da ese numero está en…» remite a una consulta que da otro número; las tres fichas de columna conservan el «22» mal atribuido; dos de los tres números siguen sin consulta. |
| **C4 bis** Campaña de mutación | **`[ ]`** | **La puerta no mide**: en worktree detached la suite ya está roja antes de mutar, y `returncode != 0` se cuenta como mutante muerto. Demostrado con control. |
| **C4 ter** Cero supervivientes | **`[ ]`** | Hay **al menos un superviviente real** (`diccionario_sql.py:297`, `and`→`or`), declarado muerto por las dos campañas. |
| **C5** Tareas y commits | `[x]` **parcial** | Reserva: `azure-apps` no recoge `ocultar` en el contrato ampliado, y R38 pedía hacerlo en el mismo trabajo. Las MANUAL (T19, T27, T29-T34) siguen abiertas por diseño. |

**Rectifico** los checkpoints que había puesto en `[x]` en el borrador de esta
misma pasada: di C4 bis y C4 ter por buenos porque mi recálculo del **conteo**
(254) coincidía exacto con el informe. El conteo coincide y sigue coincidiendo;
lo que no vale es el **veredicto** de cada mutante. Contar bien los mutantes y
creerse su resultado son dos cosas distintas, y yo verifiqué la primera y di por
buena la segunda.

## Sobre su observación de la mutación, que se ha quedado corta

> «Un número de mutación sin recalcular envejece como un recuento a mano, con el
> agravante de que **parece evidencia**.»

**La suscribo y la extiendo, porque hoy resulta ser peor de lo que dice.** No es
solo que un número de mutación **envejezca**: es que podía **no haber medido
nunca nada**. El de esta tanda está recalculado, es de hoy, y aun así no vale.
Un recuento a mano caducado al menos midió algo en su día.

Y coincide con el diagnóstico de fondo de las dieciséis pasadas: **el problema
nunca han sido los datos, han sido los instrumentos que decían que los datos
estaban bien**. El aviso que estaba en el sitio equivocado, el guardián que
comprobaba que una cadena aparece, la lista a mano bajo un comentario que decía
«se derivan», y ahora la puerta que cuenta muertos sin mirar. Cada vez el
contenido estaba mejor y el instrumento seguía igual.

## Automejora que propongo (no aplico)

Tres, y la primera es urgente y no es de este proyecto:

1. **Línea base verde obligatoria en `harness/mutacion.py`.** Correr la suite sin
   mutar en el entorno de evaluación y **abortar** si no da returncode 0; y
   decidir «muerto» comparando contra los tests que fallaban en la base, no
   contra un código de salida. Va a **`arnes-base`** por la regla de propagación,
   y con ella la revisión de las campañas anteriores que declararon 0
   supervivientes en modo paralelo.
2. **Que un guardián nuevo venga con su intento de evasión**, no solo con su
   control anti-vacío. El control responde «¿comprueba a alguien?»; falta
   «**¿puedo escribir el defecto de forma que no salte?**». Las tres vías de hoy
   se encuentran en diez minutos si alguien se sienta a intentarlo, y **ninguna
   se encuentra leyendo el test**: leyéndolo parece correcto, con su lista, su
   docstring y su control.
3. **Que los tests que comparan prosa normalicen el marcado**, con
   `tests/_texto.py::normalizado()`, que ya existe y ya resolvió esto tres veces.

## Qué falta para APROBADO

**Bloqueantes:**

1. **Arreglar la puerta de mutación** (línea base verde + veredicto por
   comparación) y **relanzar la campaña** para saber cuántos supervivientes hay
   de verdad. Hoy sabemos de uno; no sabemos si son diez.
2. **Cerrar el mutante conocido**: un test que compruebe `_clave_de` con
   entradas de tipo cadena, que es lo que hace `ocultar` usable.
3. **Quitar el salvoconducto** del guardián de coherencia, normalizar antes de
   comparar y sustituir la lista de frases por un criterio.
4. **Propagar el 22 → 9** a las tres fichas de columna, y corregir la remisión
   «la consulta que da ese numero está en el grano de…», que apunta a otra.

**De higiene, no bloqueantes:** publicar la consulta del «37 celdas / 39,07 M€» y
la del «22 obras»; anclar `can_origen` y `v_pbi_fact_categoria` en el control de
`_acumuladas_de`; deshacer la relajación del guardián hermano a tres cadenas;
añadir `ocultar` a `azure-apps/datamart_seg_anual.md`; y arreglar `design.md:159`,
que contradice a su §4.4.

## Nota de método

Esperé la auditoría independiente **y** relancé yo la campaña de mutación con el
bytecode borrado. Las dos cosas importaron: mi campaña confirmó el conteo y **me
llevó a la conclusión equivocada**, y fue la auditoría la que señaló un mutante
concreto que yo no había mirado. Lo verifiqué entonces con su control —copia con
`.env`, con y sin mutante, resultados idénticos— y de ahí salió el fallo del
arnés.

La lección, y va contra mi propio trabajo: **relanzar una medición no la valida
si la medición está mal construida**. Yo hice exactamente lo que pedía el
protocolo —no fiarme del informe, recalcular por mi cuenta— y obtuve el mismo
resultado falso, con la confianza añadida de haberlo obtenido yo. La verificación
independiente reproduce el método; solo atacar el resultado lo pone a prueba.

Todo lo que sostiene esta pasada lo comprobé personalmente: el recálculo del
alcance (3191 líneas) y de los mutantes (254, exacto); la campaña completa
relanzada; el mutante vivo con su control; el worktree detached que rompe
`test_f015_r12` **con y sin mutante**; los tres ataques al guardián, cada uno con
su control; la eliminación del arreglo de `ocultar` con los 19 tests en verde; la
derivación de `_acumuladas_de` ejecutada; y las cifras de las fichas de columna
contadas sobre el YAML. Todos los worktrees y copias que creé están borrados y
`git worktree list` vuelve a tener una sola entrada.

---

# DECIMOQUINTA PASADA · el aviso bajó a la columna, pero la cabecera sigue tranquilizando

**Veredicto: RECHAZADO**, por dos motivos.

1. **La campaña de mutación sigue sin relanzarse.** Es el GRAVE 1 que escribí en
   la pasada anterior, intacto: mismo fichero, misma fecha, 1111 bytes.
2. **El aviso del doblado bajó a la columna pero no se corrigió en la cabecera**,
   que conserva el encuadre suave que rechacé —y que dice, además, algo
   tranquilizador y engañoso: «la clave no duplica —comprobado—».

**Rectifico lo que escribí hace un rato en la primera versión de esta pasada.**
Di el GRAVE 1 por «cerrado, y bien cerrado esta vez», y respondí que un agente ya
no puede equivocarse. Una auditoría que encargué —y que esta vez sí esperé—
volvió con la pieza que me faltaba: **cómo llega el diccionario al agente**. Con
eso delante, la respuesta correcta es que **sí puede equivocarse**, y explico por
dónde.

Es la segunda pasada seguida en que doy este defecto por cerrado y no lo estaba.
La causa es la misma que el implementer describió tan bien: verifiqué donde el
guardián nuevo mira —la columna— igual que la vez anterior verifiqué donde miraba
el guardián viejo —el objeto—. **El guardián enseña a mirar donde él mira**, y yo
he caído dos veces seguidas.

**Nivel de rigor: `critico`.** **Entorno:** `init.sh` verde — **1974 pasados**,
124 saltados, cobertura **98,2 %** de 976 líneas. Árbol limpio, sin `push`,
publicado en versión 5.

## MOTIVO 1 · La campaña de mutación, sin relanzar

Recalculado hoy sobre `HEAD` con `harness.alcance` y `generar_mutantes`:

| | Campaña (21-ago 10:42) | Hoy | Diferencia |
|---|---|---|---|
| Ficheros | 8 | **10** | +2 |
| Líneas | 2358 | **3174** | +816 |
| Mutantes | 166 | **252** | **+86** |

Siguen enteros fuera `unicidad_sql.py` (24 mutantes) —el módulo del `SET LOCAL
transaction_read_only` que corre contra el servidor compartido con producción— y
`catalogo.py` (14), que sostiene `check-diccionario`. En nivel `critico`, 86
mutantes sin ejecutar no son cero supervivientes: son 86 desconocidos.

## MOTIVO 2 · El aviso llega a la columna, pero la cabecera dice lo contrario

### Lo que sí está bien hecho, y no es poco

El aviso **bajó al `significado`** de las cuatro columnas afectadas y es
completo: dice qué pasa, cuánto, que **leer una fila y darla por buena devuelve
el doble**, y dos vías para el valor bueno. Las columnas sanas dicen que lo son
(«**Esta columna NO esta afectada por el duplicado del fact**»), que corrige el
error inverso de la pasada 13. El punto ciego del bloque está acotado: ejecuté la
derivación y `v_pbi_fact` ya **no** se cuela. Todo eso es correcto y lo doy por
verificado.

### Lo que faltó, y por qué importa

Fui a ver **cómo llega esto al agente**, que es lo que no había mirado. El MCP
tiene dos presentadores (`mcp-bbdd/interface_adapters/mcp/presentadores.py`):

- **`listar_tablas`** → `presentar_catalogo` (líneas 26-58): descripción y grano.
  **Sin columnas.**
- **`describir_tabla`** → `presentar_tabla` (líneas 61-85): descripción, grano
  **y** la tabla de columnas, en la misma respuesta.

Y la cabecera de los dos objetos sigue diciendo, literalmente:

> `fact_seguimiento_categoria.grano`: «Como esta tabla **agrega**, las dos filas
> se funden en una y **la clave no duplica** —comprobado, sin contradiccion—.»
>
> `v_pbi_fact_categoria.descripcion`: «`importe_origen` viene **sumado dos
> veces**, asi que **no lo uses para un total**.»

Las dos consecuencias:

1. **Por `listar_tablas` el agente solo ve eso.** Y eso dice que la agregación
   resolvió el duplicado y que el único riesgo es hacer totales. Quien lea una
   fila para responder «¿cuánto llevamos a origen en esta obra?» concluye que es
   seguro. **Es el encuadre exacto que rechacé en la pasada anterior**: «no es que
   se infle si alguien lo suma; está inflado en la tabla».
2. **Por `describir_tabla` el agente recibe las dos cosas a la vez, y se
   contradicen.** La cabecera dice «la clave no duplica, comprobado»; la columna,
   tres párrafos más abajo, dice «EL VALOR ALMACENADO ESTA DOBLADO». Ante dos
   afirmaciones opuestas en la misma respuesta, el resultado no es predecible.

**Que conste el matiz honesto**: el catálogo instruye «Usa `describir_tabla(...)`
antes de escribir SQL», así que el flujo normal sí pasa por la respuesta que
lleva el aviso bueno. El riesgo no es que el aviso no llegue nunca; es que llegue
**acompañado de su contrario**. Arreglar la cabecera son dos párrafos.

### Y un defecto de presentación que degrada justo ese aviso

Los `significado` nuevos vienen de YAML plegado con línea en blanco, así que
llevan **saltos de línea literales**: 1 en `importe_mes`, 2 en `importe_origen` y
en `importe_origen_raw` (lo medí en los cinco). `presentar_tabla` los inserta en
una **fila de tabla Markdown** escapando solo el `|` (`presentadores.py:82-85`).
Un salto de línea dentro de una celda rompe la fila: el aviso «OJO: … DOBLADO»
sale partido en líneas huérfanas fuera de la tabla. Es el aviso más importante
del diccionario y es el que peor se va a ver.

## El número: el hecho se sostiene, el alcance no

En la primera versión de esta pasada escribí que «el número se sostiene».
Rectifico a medias, porque hay que separar dos cosas.

**El hecho está probado**: el build hace `SUM(importe_origen)`
(`03_agg_categoria.sql:68`) y en el fact el acumulado es idéntico en las dos
filas duplicadas (`impl_F-006.md:3880`). Eso no lo discute nadie.

**El alcance publicado —«37 celdas de 8 obras, 39,07 M€»— no está respaldado.**
Dos razones:

1. **No hay consulta.** En todo el repositorio solo está el bloque de salida
   (`impl_F-006.md:4157`). Sin el SQL no se sabe qué se midió ni sobre qué
   recorte, y no se puede reproducir. En una feature donde la regla es «lo que no
   se pueda derivar no se afirma», esto es una cifra sin derivación.
2. **No cuadra con las otras cifras de la misma ficha.** El propio informe
   establece **8.778 claves duplicadas repartidas en 22 obras**
   (`impl_F-006.md:3570`, `:3576`). Si una obra tiene partidas duplicadas, su
   celda de categoría queda afectada por construcción — así que deberían salir
   **22 obras, no 8**. Puede haber una explicación buena (que la medición se
   acotara a un mes o a un escenario), pero no está escrita, y el texto se
   publica al agente como si fuera el alcance total.

No sé cuál de las dos cifras es la correcta, y no lo afirmo: digo que **se
contradicen en el mismo párrafo** y que la que viaja al agente es la que menos
respaldo tiene. Si el alcance real fueran 22 obras, el aviso publicado
**subestima** el daño.

Va en la misma línea el «**200 de 200 series**» que ahora respalda a las columnas
sanas: es una muestra sobre `fact_seguimiento_mensual` —no sobre los dos objetos
de categoría donde se publica— y se lee como exhaustiva. Es el mismo tipo de
error que el «28/200» que sí se retiró.

## Riesgos latentes en la derivación, medidos

Verifiqué el derivador buscando por dónde se le escapa algo. Tres huecos, ninguno
con consecuencia hoy y los tres del mismo tipo: **la comprobación es más estrecha
que el problema**.

1. **`_ACUMULADAS` es una lista a mano con un comentario que dice lo contrario.**
   `tests/test_f006_stg_trampas.py:599-602`: «Se derivan: son las acumuladas a
   origen…» encima de `_ACUMULADAS = ("importe_origen", "importe_origen_raw",
   "can_origen", "total_incurrido")`, que es una tupla escrita a mano. Es
   exactamente la afirmación de derivación falsa que esta feature persigue,
   dentro del test que la persigue. Además `total_incurrido` **no está doblado**
   (0.00 vs 27850.09, `impl_F-006.md:3892-3895`) y `can_origen` no se ha medido
   nunca: si un objeto publicara cualquiera de las dos, el test exigiría escribir
   un «DOBLADO» **falso**, y alguien lo escribiría para poner el test en verde.
2. **La regex no casa con alias.** `:624` busca `SUM\s*\(\s*importe_origen`, que
   no ve `SUM(pm.importe_origen)`. Y esa es justo la forma que usa
   `cierre/02_build_fact.sql:78,93,107,121`, que agrega sobre `stg.plan_mensual`
   unido a `stg.fases` — **la misma fuente de fases duplicadas**. Si ese build
   dobla o no, no lo dice nadie: no está verificado en ninguna parte.
3. **El filtro `ficha.esquema != "mart"` excluye el resto del datamart sin
   declararlo.** Comprobé el único consumidor del fact de categoría fuera de
   `mart` —`cierre.v_pbi_planif_vs_real`, `06_views_planif_vs_real.sql:45`— y
   **hoy es inocuo**: solo lee `f.importe_mes`, la columna sana. Pero el doblado
   viaja con la columna, no con el esquema.

## `ocultar` · la razón ya es cierta; la decisión, cambio de opinión

**La razón nueva es verificable y la verifiqué.** El gancho del consumidor es
`esta_oculta(nombre_completo)` recibiendo **tabla**
(`mcp-bbdd/application/services/servicio_catalogo.py:49`, con `fnmatch` en
`diccionario_yaml.py:87-89`), y la lista de `00_global.yaml:554-557` son tres
nombres de **columna**. Ninguna tabla se llama `_built_at`, así que nunca ocultó
nada. Cierto punto por punto, y con el hueco reconocido en vez de tapado. El
proveedor Postgres, además, devuelve `False` cableado (`diccionario_postgres.py:303-305`).

**Sobre si debe seguir fuera, cambio de opinión respecto a lo que escribí hace un
rato.** Mi argumento era que el hueco ya está mitigado por otra vía, y **eso es
cierto**: las 11 columnas de instrumentación fichadas dicen en su propio
`significado` «Instrumentación del ETL, **no negocio**: para la frescura del
esquema se consulta `_meta.v_frescura`». La defensa contra «el agente la ofrece
como si fuera de negocio» ya viaja al consumidor.

Pero eso resuelve el riesgo **funcional** y no el que decide la cuestión, que es
**arquitectónico**. La propia razón escrita dice que el hueco «se cierra en
`mcp-bbdd` añadiendo un gancho de COLUMNA». Para escribir ese gancho, `mcp-bbdd`
necesita **la lista**; y si la lista no viaja por el contrato, la cablea en su
repositorio. Eso es **una segunda copia de la semántica de este repo, divergiendo
de él**: exactamente lo que F-006 nació para terminar —el diccionario vivía en un
YAML del propio MCP— y el fallo que el `CLAUDE.md` documenta con `sigrid_api.md`
y sus dos copias.

Y publicarla es barato: `_meta.diccionario_contexto` crece **por filas**, y un
bloque que el consumidor no conozca lo ignora. No hay coste de compatibilidad.

Así que: **debería viajar**, y la razón para excluirla —«publicar la lista antes
solo mueve el problema de sitio»— es el paso que no se sostiene. Publicar el dato
no mueve el problema: evita la segunda copia y desbloquea el gancho en lugar de
condicionarlo. **No lo pongo como bloqueante** —hoy no rompe nada y la decisión
está escrita y fechada, que es lo que pedí—, pero sí como recomendación con
argumento, para que se decida con esto delante y no con lo que yo dije antes.

## Recuentos y R38

**Bien resuelto donde se pudo derivar.** La ayuda de `main.py` **ya no da la
cifra** —la imprime el comando, que la cuenta— y el DDL dice «Estas **CUATRO**
tablas». Eliminar el dato en vez de actualizarlo es la única forma de que no
vuelva a caducar. Recuentos reales, recalculados por mí: **103 objetos, 798
columnas, 48 de consumo, 13 reglas**.

**Cuatro huecos:**

1. **`current.md:142` perdió el sujeto.** El titular del hallazgo principal de la
   tanda quedó así: «`- ** está DOBLADO** en el valor almacenado: 37 celdas de 8
   obras…`». Falta el nombre del objeto. El lector no sabe **qué** está doblado,
   justo en el documento que es la memoria del proyecto.
2. **«tres tablas» solo se arregló en el DDL.** Siguen caducados
   `design.md:306` (el título de §4.1, «Las tres tablas y la vista»), `:548`,
   `:552`, `:566`; `tasks.md:138`, `:306`, `:362`; y `current.md:275`. Y
   `design.md:511` cuenta «**7 objetos**» en `_meta.yaml` cuando son **8**. Lo
   pedí en la pasada anterior con las líneas puestas.
3. **Eso contradice al documento del ecosistema.** `azure-apps/datamart_seg_anual.md`
   manda al consumidor a `design.md` §4 «para el contrato completo», y allí §4.1
   anuncia **tres** tablas mientras la tabla de `azure-apps` lista **cuatro** y la
   vista. El documento correcto remite al caducado.
4. **El guardián de los recuentos es el patrón que dice combatir.** Lo probé en
   una copia de `git archive HEAD`: inyecté «El datamart tiene **102** objetos
   fichados» dentro de la sección de estado y el test pasó (`1 passed`). Busca la
   cadena literal `"102 objetos"` y la negrita la separa. Además `assert str(valor)
   in estado` es una subcadena suelta: cualquier «48» del texto la satisface, sin
   atarla a su sustantivo. Cuarta vez que esta feature tropieza con comparar
   contra prosa sin normalizar —plegado YAML en las pasadas 8, 10 y 13—.

### R38, revisado como dueño del documento

**Bien hecho.** `azure-apps/datamart_seg_anual.md` (commit `2e9bee8`) documenta
las cuatro tablas y la vista, quién las consume, cómo se publican, las reglas de
compatibilidad y qué rompe a `mcp-bbdd`. Ya no llama al MCP «cliente de
escritorio». Verifiqué lo que más caro sale en un documento de ecosistema:

- **No duplica: enlaza** a `design.md` §4, que es la regla que se incumplió con
  `sigrid_api.md` y sus dos copias divergentes.
- **Los comandos que cita existen**: `publicar-diccionario` (`main.py:762`) y
  `check-diccionario` (`main.py:603`).

Dos huecos menores como dueño: no dice que `ocultar` se deja fuera a propósito
—y `mcp-bbdd` va a ir a buscarla—, y no nombra el rol de solo lectura en esa
sección, aunque sí aparece más abajo para F-024.

## Más comprobaciones que exigen por objeto lo que es de columna, y al revés

Me pediste buscar más casos del patrón. Los hay, y en el mismo fichero que lo
cerró:

- **`..._el_aviso_no_alarma_sobre_la_medida_sana`** (`test_f006_stg_trampas.py:559-586`)
  condiciona por la existencia de la **columna** `importe_mes` y luego asierta
  `"telescopea"` contra `ficha.descripcion + ficha.grano`, **a nivel de objeto**.
  Es el gemelo exacto del defecto que esta tanda cierra, intacto.
- **`..._todo_objeto_que_sirve_medidas_del_fact_avisa`** (`:548-556`) exige el
  `"8.778"` solo en `descripcion`/`grano`. En la primera versión de esta pasada
  escribí que los dos niveles «conviven, que es lo que hay que tener». Me
  corrijo: **conviven mal**. Nada exige que el texto de objeto diga que el
  **valor almacenado** está doblado, así que entre estos dos guardianes la
  redacción vieja y suave de la cabecera queda fijada y en verde.
- **Y al revés, que es lo que se me escapó**: el doblado del valor almacenado es
  una propiedad **del objeto** —todas sus filas están mal, y `listar_tablas` no
  lleva columnas—, y los tests nuevos (`:643-670`) lo exigen **solo en la
  columna**. Ningún test cubre la cabecera. Hace falta en los dos sitios porque
  hay dos caminos de lectura.

Revisé los demás usos de `ficha.descripcion` y **son correctos**: los de
`stg.presupuesto` están cubiertos en ambos niveles, y los de `raw.*`
(`test_f006_raw_ingesta.py`, `..._fuente_que_gobierna.py`, `..._regla_de_oro.py`)
solo pueden ir a nivel de objeto porque esas fichas tienen **0 columnas** por
DA-2. No hay nada que corregir ahí.

## ¿Puede lanzarse la batería de las 18 preguntas?

**Sí, pero arreglando antes la cabecera de esos dos objetos.** Son dos párrafos y
elimina una contradicción interna que la batería no va a destapar.

El razonamiento, para que se pueda discutir: el catálogo instruye «Usa
`describir_tabla(...)` antes de escribir SQL», así que el flujo normal sí entrega
el aviso bueno de la columna. El problema no es que falte, es que **llega junto a
su contrario** —«la clave no duplica, comprobado»— y que por `listar_tablas` solo
llega el contrario. La batería es cualitativa: juzga si la respuesta parece
razonable, no si el número cuadra, así que un acumulado al doble pasará por
bueno.

**Lo demás no bloquea la batería** y puede ir en paralelo: la campaña de
mutación son 19 minutos de máquina sin nadie delante, y los recuentos y el
formato son higiene.

Lo que conviene tener delante al leer los resultados:

1. **El alcance del doblado no está claro** (37 celdas / 8 obras contra 8.778
   claves / 22 obras). Si una pregunta da un acumulado a origen, no basta con que
   el aviso salga: hay que contrastar el número.
2. **Los 39 «sin contradicción» no tienen la clave demostrada, y 7 objetos
   quedaron sin comprobar**, entre ellos `mart.fact_seguimiento_mensual` y
   `mart.v_pbi_fact`.
3. **La base cambia bajo los pies** con los cuatro `build-*` que se lanzan ahora:
   desaparecerá la huérfana de `cierre` y pueden aparecer objetos nuevos sin
   ficha. **Pasar `check-diccionario` después de los builds y antes de la
   batería.**
4. **El doblado sigue vivo en la base.** F-042 lo recoge ya como dato erróneo,
   que es la clasificación correcta: el diccionario avisa, el número sigue mal
   hasta que se arregle el build.

## Checkpoints

| | Estado | Razón |
|---|---|---|
| **C1** Entorno en verde | `[x]` | 1974 pasados, 124 saltados, cobertura 98,2 % de 976 líneas. |
| **C2** Trazabilidad requisito → test | **`[ ]`** | R10 cubierto en la columna pero **no en la cabecera**, que es el único texto que entrega `listar_tablas`; y dos guardianes fijan la redacción vieja del objeto. |
| **C3** Diff conforme al diseño | `[x]` | Solo los ficheros previstos. El build de `mart` no se toca: correcto, es de otra feature y la firma está acotada a `_meta`. |
| **C3 bis** Sin secretos ni prints | `[x]` | Sin GUID ni correo en el árbol; ID de suscripción redactado en `HEAD`. |
| **C4** Convenciones y veracidad | **`[ ]`** | Cifra publicada al agente sin consulta que la respalde y en contradicción con las del mismo párrafo; comentario «Se derivan» sobre una lista a mano; «tres tablas» vivo en `design.md` y `tasks.md`; `current.md:142` sin sujeto. |
| **C4 bis** Campaña de mutación | **`[ ]`** | Sin relanzar: 166 mutantes sobre 2358 líneas; hoy son **252 sobre 3174**. |
| **C4 ter** Cero supervivientes | **`[ ]`** | Depende del anterior. |
| **C5** Tareas y commits | `[x]` **parcial** | T37/R38 hecho y bien. Siguen abiertas por diseño las MANUAL (T19, T27, T29-T34), pendientes de autorización: no son defecto de esta tanda. |

## Nota de método: esta vez esperé, y cambió el veredicto

Encargué una auditoría independiente y **la esperé**, que es lo que me faltó en
la pasada anterior. Volvió con la pieza decisiva: **cómo llega el diccionario al
agente**. Yo había verificado que el aviso estaba en la ficha de columna y me
detuve ahí; no fui a mirar qué entrega cada presentador del MCP. Con eso delante,
el defecto que iba a dar por cerrado —por segunda vez— no lo está.

La diferencia entre mi primera versión de esta pasada y esta: un RECHAZO solo por
la mutación, con el GRAVE 1 aprobado y un «la batería puede lanzarse sin
matices», contra un RECHAZO con motivo material y una condición previa a la
batería. Esperar quince minutos valió eso.

Dos rectificaciones mías que dejo a la vista:

- **«Un agente que lea solo la ficha de columna ya no puede equivocarse»** era
  responder a una pregunta que no describe el sistema: el agente **nunca** lee
  solo la columna. O lee la cabecera sola (`listar_tablas`) o las dos juntas
  (`describir_tabla`). La pregunta útil era «¿qué recibe el agente?», y esa no me
  la hice.
- **«Los dos niveles conviven, que es lo que hay que tener»**: conviven mal
  mientras la cabecera diga lo contrario que la columna.

Todo lo que sostiene esta pasada lo comprobé personalmente, incluido lo que trajo
la auditoría, que **no di por bueno sin repetirlo**: el recálculo del alcance y
los mutantes; los dos presentadores abiertos en `mcp-bbdd`; las cabeceras y las
cinco fichas de columna leídas enteras; los saltos de línea contados; la
ejecución del derivador; el `SUM(pm.importe_origen)` de `cierre/02_build_fact.sql`;
la aritmética de 8.778/22 contra 37/8; el experimento de las negritas en una copia
de `git archive HEAD` que borré después; el gancho `esta_oculta`; y los comandos
de `azure-apps` localizados en `main.py`.

## Automejora que propongo (no aplico)

Mantengo las de las pasadas anteriores —**estampar el SHA en el informe de
mutación y que `init.sh` avise `PUERTA MUTACION: [CADUCADA]`**, y **que un
guardián de prosa declare qué NO comprueba**—. La primera habría evitado el
motivo 1: nadie olvidó relanzar la campaña por descuido, sino porque **nada se lo
recordó**, y en una feature de quince tandas eso pasa seguro.

Añado dos, con el experimento hecho:

1. **Que los tests que comparan contra prosa normalicen el marcado, no solo los
   espacios.** `tests/_texto.py::normalizado()` colapsa espacios; le falta quitar
   `*`, `` ` `` y `_`. Probado: `**102** objetos` esquiva un guardián que busca
   `"102 objetos"`. Es la cuarta vez con la misma piedra.
2. **Que `CHECKPOINTS.md` pida verificar el aviso en el camino de entrega, no en
   el fichero.** La lección de esta pasada no es «mira también la columna» ni
   «mira también el objeto»: es que **el sitio correcto depende de qué entrega el
   consumidor**, y eso se averigua abriendo el consumidor. Un aviso que no llega
   no existe, y dónde llega no se deduce del YAML.

## Qué falta para APROBADO

1. **Corregir la cabecera** de `mart.fact_seguimiento_categoria` y
   `mart.v_pbi_fact_categoria`: que digan que el **valor almacenado** está
   doblado, y retirar el «la clave no duplica —comprobado—», que tranquiliza
   sobre lo que no debe. Y un test que lo exija **en los dos niveles**.
2. **Relanzar `python -m harness.mutacion --feature F-006`** sobre `HEAD`, con los
   `__pycache__` borrados (F-041), y cerrar con los totales reales: 252, no 166.
   Más la sección **«Evidencias»**.
3. **Respaldar o acotar el «37 celdas / 8 obras»**: publicar la consulta, o
   escribir a qué recorte corresponde. Hoy contradice al 8.778/22 de la misma
   ficha.

Y de higiene, que no bloquea: los saltos de línea en los `significado`; el
comentario «Se derivan» sobre `_ACUMULADAS` y sacar de ahí `total_incurrido`;
«tres tablas» en `design.md` y `tasks.md`; el sujeto de `current.md:142`; y
normalizar el marcado en el guardián de recuentos.

---

# DECIMOCUARTA PASADA · una campaña caducada, un número doblado y una cifra que yo mismo copié mal

**Veredicto: RECHAZADO**, ahora por tres motivos y no por uno. Escribí la primera
versión de esta pasada con un solo grave; una auditoría independiente que había
encargado volvió tarde, con hallazgos que yo no tenía, y **dos de ellos me
obligan a rectificar cosas que ya había dado por buenas en este mismo informe**.
Lo dejo escrito así, con la rectificación a la vista, porque el historial de esta
review vale más que mi acierto.

Los tres motivos:

1. **La campaña de mutación acredita un código que ya no es el que hay.** 86
   mutantes sin evaluar, dos ficheros enteros fuera.
2. **`importe_origen` está doblado en el valor almacenado, y su ficha de columna
   no lo dice.** Es la tercera vez en esta feature que el aviso llega a la
   descripción del objeto y no a la columna que lleva el número malo — y yo di
   ese defecto por «cerrado y bien cerrado» hace media hora.
3. **La razón escrita para dejar `ocultar` fuera del contrato es falsa**, con un
   test verde encima que solo comprueba que la cadena aparezca.

Y una corrección que me toca a mí: **el diccionario tiene 103 objetos, 798
columnas y 48 de consumo, no 102 / 793 / 47.** Escribí las cifras viejas en la
primera versión de esta pasada, copiándolas de las anteriores en vez de
recalcularlas. Es exactamente lo que llevo catorce pasadas reprochando. Las
recalculé cargando el diccionario: la ficha 103 es `_meta.diccionario_contexto`,
que añade esta misma tanda.

Lo que **sí** está cerrado, verificado uno a uno: el plegado tratado como clase
(cubre todos los sitios; las únicas comparaciones contra crudo son SQL literal,
que no se pliega), el alcance real del barrido de código muerto, la quinta ficha
del aviso llegada por derivación legítima, y el contrato versión 4 —las 21 filas
cuadran recalculadas, las once claves del `00_global.yaml` están todas
clasificadas sin solapamiento, y el mecanismo **no** admite una clave nueva en
silencio: lo probé metiendo una, y por partida doble (la rechaza el whitelist del
cargador y, si pasara, el guardián).

**Nivel de rigor: `critico`** (declarado en `harness/features.json`). Exige fase
RED con traza real, cobertura de lo cambiado, campaña de mutación **con cero
supervivientes** y verificaciones MANUAL (humano) con comando y resultado real.

**Entorno:** `bash harness/init.sh` en **verde** — 1968 pasados, 124 saltados,
cobertura **98,2 %** de 976 líneas. Rama `feature/F-006-mcp-azure`, sin `push`.

## GRAVE 1 · La campaña de mutación acredita un código que ya no es el que hay

Esto no lo encontré revisando lo que la tanda dice haber hecho, sino haciendo lo
que mi protocolo manda y llevo catorce pasadas repitiendo: **recalcular los
totales en vez de creérmelos**. Esta vez no cuadran.

`progress/mutacion_F-006.md` lleva fecha del **2026-08-21 a las 10:42** y declara
**2358 líneas en 8 ficheros, 166 mutantes, 0 supervivientes**. Recalculado por mí
sobre `HEAD`, con `harness.alcance` y `harness.mutacion.generar_mutantes`:

| | Campaña (21-ago 10:42) | Hoy en `HEAD` | Diferencia |
|---|---|---|---|
| Ficheros en alcance | 8 | **10** | +2 |
| Líneas en alcance | 2358 | **3164** | **+806** |
| Mutantes | 166 | **252** | **+86** |

**Un tercio de los mutantes del alcance no se ha evaluado nunca.** Y no son
líneas cualesquiera: entre la campaña y hoy entraron **siete commits que tocan
producción** —`ebd88a6`, `1444c77`, `726e009`, `39c83f7`, `70e7bb7`, `abdab22`,
`909cd79`—, es decir, **todo lo que se escribió para cerrar los graves de las
pasadas 12, 13 y 14**. Los dos ficheros que faltan enteros son:

- **`etl_sigrid/infrastructure/postgres/unicidad_sql.py`** (274 líneas, 24
  mutantes) — el módulo que emite el `SET LOCAL transaction_read_only = on`
  contra el servidor **compartido con producción**. Es exactamente el código
  nacido del GRAVE 1 de la duodécima pasada, donde el `READ ONLY` resultó ser
  mentira impresa.
- **`etl_sigrid/infrastructure/postgres/catalogo.py`** (166 líneas, 14 mutantes)
  — el que sostiene `check-diccionario`, la única fuente que dice la verdad.

Más los crecimientos sin cubrir de `main.py` (+157 líneas), `diccionario.py`
(+51), `diccionario_sql.py` (+84) y `postgres_client.py` (+74), donde vive el
`diccionario_contexto` que esta misma tanda añade.

**No estoy diciendo que el informe mienta**: lleva su fecha honesta y su alcance
honesto para el momento en que se generó. Estoy diciendo que **no se relanzó**, y
que un informe correcto de ayer no acredita el código de hoy.

Por qué bloquea, y no es formalismo: el nivel **crítico** exige cero
supervivientes. **86 mutantes sin ejecutar no son cero supervivientes; son 86
desconocidos**, y están concentrados justo en el código que se escribió a
correr para tapar tres graves —el peor momento posible para dejar de mirar—. La
mutación existe precisamente para decir si esos tests nuevos comprueban algo o
solo acompañan. Aprobar aquí sería hacer lo que llevo catorce pasadas señalando:
dar por buena una afirmación de completitud sin su evidencia.

**Qué hace falta:** relanzar `python -m harness.mutacion --feature F-006` sobre
`HEAD` y volver con los totales reales. La anterior tardó 738 s sobre 166
mutantes; esta rondará los 19 minutos. Si sale en 252/252 muertos, cae este
grave y no tengo nada más que oponer a la tanda. Y conviene borrar los
`__pycache__` antes: F-041 documenta que Python ejecuta bytecode mutado obsoleto
cuando el fuente restaurado conserva mtime y tamaño.

## GRAVE 2 · `importe_origen` viene doblado en el valor almacenado, y la ficha de columna dice que está bien

Este no lo vi yo en la primera vuelta. Lo trajo la auditoría, lo verifiqué, y es
el más peligroso de los tres para lo que viene ahora.

**El hecho, por dos vías independientes.** El propio informe del implementer
(`progress/impl_F-006.md:3880`) mide y concluye: «`importe_origen` **idéntico en
las dos** [filas duplicadas]: por eso un `SUM` cuenta dos veces». Y el build de la
categoría hace exactamente ese `SUM` (`sql/mart/03_agg_categoria.sql:68`):

```sql
SUM(importe_mes)        AS importe_mes,
SUM(importe_origen)     AS importe_origen,
```

Es decir: **el valor que queda escrito en
`mart.fact_seguimiento_categoria.importe_origen` ya está inflado ×2** para las
series afectadas. No es que se infle si alguien lo suma. Está inflado en la
tabla, y `mart.v_pbi_fact_categoria` lo lee tal cual.

**Y lo que la ficha de columna le dice al agente es que ese número es el bueno.**
`config/diccionario/mart.yaml:348-353` y `543-546`:

> `importe_origen` — «Suma del acumulado a origen de esas partidas. **Ya es
> acumulado**: sumarlo en el tiempo multiplica.» · `agregacion: ultimo_valor`

El aviso corregido en la descripción del objeto dice «no la uses para un total».
Correcto y útil, pero **no cubre el camino de lectura que importa**: leer **una
sola fila** para responder «¿cuánto llevamos acumulado a origen en la obra X,
categoría CD, a fecha M?». Ahí no hay ningún total que evitar; hay un valor que
la ficha marca como `ultimo_valor`, que es la instrucción de tomarlo tal cual, y
que viene doblado.

**Por qué me obliga a rectificarme.** En la primera versión de esta pasada
escribí que el DEFECTO 3 estaba «cerrado, y bien cerrado». Lo verifiqué en
`descripcion` y en `grano`, que es donde el implementer lo puso y donde el
derivador lo exige, **y no abrí las fichas de columna**. El derivador de
`tests/test_f006_stg_trampas.py` tiene el mismo punto ciego: asierta sobre
`ficha.descripcion` y `ficha.grano`, nunca sobre `columna.significado`. Un
guardián que solo mira donde ya se arregló.

**Qué hace falta:** que el aviso baje a `significado` de `importe_origen` en los
dos objetos, diciendo lo que pasa —el valor almacenado viene sumado dos veces
para las series afectadas— y qué usar en su lugar; y que el derivador exija el
aviso **en la columna**, no en la ficha.

### Dos afirmaciones más del mismo aviso que no se sostienen

- **`total_incurrido` está en el saco equivocado.** `mart.yaml:52-55` lo lista
  entre las que «repiten el mismo acumulado en las dos filas». La comparación
  fila a fila del propio informe (`impl_F-006.md:3892-3895`) muestra **0.00 vs
  27850.09**: no repite, y sumarlas no dobla.
- **El «28/200» no prueba lo que se le hace probar.** Se cita como evidencia del
  doblado (`impl_F-006.md:3975`, `mart.yaml:53-56`), pero mide que
  `SUM(importe_origen)` sobre **todos los meses** no da el último valor — algo que
  es cierto con duplicado y sin él, porque sumar un acumulado a lo largo del
  tiempo está mal de por sí. La medición que sí prueba el doblado es la de la
  línea 3880. El hecho es correcto; la cifra que se publica como su prueba, no.
  Y esto importa: un agente al que se le da un número como razón puede razonar a
  partir de él.

## GRAVE 3 · la razón por la que `ocultar` se queda fuera es falsa, y hay un test verde encima

Yo había anotado esto como observación menor: la razón cita `motivo_no_consumo`,
que es de objeto, para un `ocultar` que es de columna. La auditoría fue más
lejos y tiene razón: **el mecanismo que se invoca no existe en ninguno de los dos
lados**.

- `ocultar` (`config/diccionario/00_global.yaml:554-557`) son tres nombres de
  **columna**: `_ingested_at`, `_source_tiemod`, `_built_at`.
- `motivo_no_consumo` vive en `Ficha`, no en `Columna` (`domain/diccionario.py:224-232`),
  y la tabla `_meta.diccionario` no lo lleva a nivel de columna. **No puede
  sustituir a `ocultar` ni en principio.**
- En el consumidor el gancho es de **tabla**:
  `mcp-bbdd/.../servicio_catalogo.py:49` llama `esta_oculta(tabla.nombre_completo)`,
  con `fnmatch` sobre ese nombre.

Conclusión, y es peor que la mía: `ocultar` lista **columnas** contra un gancho de
**tabla**, así que **nunca ocultó nada**, tampoco en el proveedor YAML. La
intención original (`design.md:159`, «patrones fnmatch de columnas técnicas»)
jamás se implementó, y la exclusión del contrato la ha certificado como
«resuelta por otra vía» sin que nadie lo notara.

El resultado práctico de hoy es inocuo —esas tres columnas de instrumentación no
estorban a nadie—. Lo que no es inocuo es el mecanismo: `tests/test_f006_contexto.py:82-85`
comprueba que las cadenas `"motivo_no_consumo"` y `"2026-08-22"` **aparezcan** en
el texto de la razón, no que la razón sea cierta. Es el patrón exacto que esta
feature lleva catorce pasadas produciendo: **un guardián verde sosteniendo una
afirmación falsa**. Y esta vez el guardián es nuevo, de esta tanda, y nació ya
así.

**Qué hace falta:** reescribir la razón para que diga la verdad —`ocultar` no se
publica porque nunca llegó a funcionar y está pendiente de decidir si se
implementa a nivel de columna o se retira— y abrir la deuda correspondiente. Un
test no puede validar la veracidad de una prosa; por eso la prosa tiene que
decir lo que se puede sostener.

## DEFECTO 4 · la tanda cierra sin «Evidencias», y no es papeleo

La sección de `progress/impl_F-006.md` que documenta esta tanda —«El contrato
crece · `_meta.diccionario_contexto`»— termina en la verificación contra la base,
que está muy bien hecha, pero **no trae la sección «Evidencias»** con los cuatro
números que el nivel crítico exige (tests, cobertura de lo cambiado, mutantes y
supervivientes, tiempo de la suite). Las pasadas anteriores sí la traían.

Lo señalo porque **está causalmente unido al grave**. Si esta tanda hubiera
tenido que escribir «mutantes: N, supervivientes: 0», alguien habría abierto
`progress/mutacion_F-006.md` para copiar los números, habría visto la fecha del
21 a las 10:42, y el grave se habría cazado solo. La sección Evidencias no está
para que el reviewer tenga una tabla bonita: está para obligar a **volver a mirar
la evidencia** en cada tanda, que es exactamente el paso que se saltó.

Se arregla con el mismo trabajo que el grave: relanzar la campaña y cerrar la
tanda con los cuatro números reales.

Tampoco encuentro **traza RED** para los tests nuevos de `test_f006_contexto.py`.
Es menos grave —el mecanismo de clasificación lo probé yo metiendo una clave
inventada, y falla en rojo como debe, así que sé que los tests muerden—, pero el
nivel crítico pide la traza escrita y esta vez no está.
## Los cuatro defectos, atacados donde podían haberse escapado

Mi patrón de error en esta feature ha sido verificar lo que la tanda dice haber
hecho. Esta vez fui a buscar lo contrario: **lo que se le pudo escapar**.

### GRAVE 1 · ¿está tratado como clase, o solo en los dos sitios conocidos?

`tests/_texto.py` existe, con su `normalizado()` y su historia escrita —las tres
apariciones—, y lo usan **dos** ficheros. La pregunta era si con dos basta.

Barrí los diez ficheros de test de la feature buscando comparaciones de frase que
**no** pasen por el helper: salen 37. Pero la clase no es «comparar texto», es
**comparar prosa contra texto no parseado**, y ahí está la diferencia: lo que
carga `yaml.safe_load` llega ya desplegado —el parser colapsa el plegado de un
bloque `>-`—, así que las comparaciones contra `significado`, `grano` o `motivo`
**no son vulnerables**. Las vulnerables son las que miran el crudo: ficheros
`.py` (docstrings) y `.yaml` sin parsear.

Filtré por eso y el resultado es limpio: **las únicas comparaciones de frase
contra texto crudo son las tres de `test_f006_fichas.py:1807-1910`, y son
fragmentos de SQL literal** —`WHERE l.importe_pendiente_facturar > 0`,
`CREATE TABLE retenciones.movimientos AS`—, que no se pliegan. **No queda ninguna
comparación de prosa cruda fuera del helper.** El tratamiento como clase se
sostiene.

### GRAVE 2 · ¿el alcance declarado es el real?

El barrido declara cinco módulos barridos y tres consumidores, con el motivo
escrito: «una afirmación de completitud sin su alcance es de la misma familia que
las que esta feature lleva trece pasadas corrigiendo». Ocho de los diez módulos
Python que toca la feature.

Los dos que quedan fuera son el dominio (`diccionario.py`) y el `__init__`. Así
que **busqué código muerto ahí por mi cuenta**: recorrí las funciones públicas de
`domain/diccionario.py`, los métodos de `postgres_client.py` y los del step, y
comprobé para cada uno si tiene consumidor fuera de `tests/`. Resultado:
**ninguno sin consumidor**. El alcance declarado no esconde nada.

### DEFECTO 3 · el aviso invertido, y la lectura que se me pedía

> **Rectificado más abajo.** Lo que sigue es mi lectura de la primera vuelta y la
> mantengo porque es correcta **en lo que mira**: el aviso ya no está invertido y
> la instrucción es accionable. Pero mira solo `descripcion` y `grano`. El GRAVE 2
> de esta misma pasada explica lo que se me escapó: en la ficha de **columna** el
> número sigue doblado y sin avisar.


Está corregido, y el texto ahora es **accionable**, que es lo que importa:

> «**Qué le pasa a cada medida, medido y no supuesto:** `importe_mes` **sale
> bien**, porque las dos filas del origen telescopean y su suma es exactamente el
> movimiento del mes (200 de 200 series). `importe_origen` **sale sumado dos
> veces**, porque las dos filas repiten el mismo acumulado. Por eso esa columna
> es `ultimo_valor` y no se suma nunca: aquí ya viene agregada, así que **no la
> uses para un total** —usa la serie de `importe_mes`—.»

Tiene las cuatro cosas que un agente necesita: **qué medida está rota**, **cuál
no**, **por qué** y **qué hacer en su lugar**. Y el acotado por escenario.

Lo que más me interesa de esta corrección no es el texto, es el método: la
primera medida fue comprobar si los dos valores eran iguales, y **eso no zanjaba
nada**; la pregunta buena era si **la suma da lo que debe**. Cambiar la pregunta
convirtió una intuición en 200/200 frente a 28/200. Es la diferencia entre medir
y confirmar lo que uno ya cree.

### DEFECTO 4 · la quinta ficha, y la lista derivada

`mart.v_pbi_fact_categoria` ya avisa. Y la lista **se deriva de verdad**:
`_objetos_que_sirven_medidas_del_fact()` recorre las fichas y mira qué SQL las
puebla, con dos controles que cierran los dos sentidos:

- `..._control_la_derivacion_encuentra_los_afectados` exige que no salga vacía,
  que **`v_pbi_fact_categoria` esté** —nombrando que es «la que la propagación a
  mano dejó fuera»— y que **no arrastre las dimensiones**, que no publican
  medidas;
- y dos tests parametrizados **sobre la derivación**: uno exige que cada objeto
  afectado traiga el `8.778`, y otro que el aviso **no vuelva a alarmar sobre la
  medida sana**.

Es el mecanismo completo: deriva, se controla contra el vacío y contra el falso
positivo, y fija la corrección del defecto 3 para que no se revierta.

## El contrato, versión 4

- **Las 21 filas cuadran**, recalculadas por mí desde el árbol: 5 convenciones +
  4 órdenes de magnitud + 3 ejes + 9 esquemas.
- **Las once claves del bloque global están clasificadas**: cuatro viajan y siete
  se declaran fuera, sin solapamiento y con su razón. Las razones son ciertas y
  concretas: `reglas` ya viaja en `_meta.diccionario_reglas`, `version`/`base`/
  `titulo` van en `diccionario_publicacion`, `pendientes` es el trinquete interno
  y `preguntas_aceptacion` es instrumentación de la propia feature.
- **El mecanismo no deja añadir una clave en silencio.** Lo probé: añadí
  `clave_inventada_por_el_reviewer` a una copia de `00_global.yaml` y la batería
  se puso en rojo —13 fallos, entre ellos el de clasificación—. Y hay un tercer
  test que exige que lo excluido lleve motivo de al menos 20 caracteres, que es
  el antídoto contra el hueco declarado sin razón.

**Un matiz sobre `ocultar`**, la exclusión que más me chirriaba: su razón dice que
se resuelve «sin contrato» porque `mcp-bbdd` antepone un aviso usando el
`motivo_no_consumo` que sí viaja. Eso es impreciso: `motivo_no_consumo` es de
**objeto** y `ocultar` lista **columnas** de instrumentación (`_built_at`,
`_ingested_at`, `_source_tiemod`), así que no cubre el mismo caso. La conclusión,
sin embargo, es correcta: esas columnas **sí llegan documentadas**, cada una con
su `significado` diciendo que son instrumentación y con `agregacion: no_sumable`.
El consumidor no se queda sin la información; la razón escrita cita el mecanismo
equivocado. Corrección de una línea, y la decisión queda fechada, que era lo
importante.

## La pregunta que se me hace: ¿está listo para las 18 preguntas?

**Rectifico.** En la primera versión de esta pasada respondí «sí, está listo, sin
matices». Con el segundo grave delante, la respuesta correcta es: **casi, y hay
una cosa que arreglar antes, precisamente porque la batería no la va a
destapar** — que es la condición exacta que se me pidió aplicar.

**Lo que hay que arreglar antes: el aviso de `importe_origen` en la ficha de
columna.** No por perfeccionismo. Porque es el único defecto conocido que puede
hacer que una de las 18 preguntas **se responda con un número que es el doble del
verdadero, con toda la seguridad del mundo y una ficha que lo respalda**. Y una
pregunta como «¿cuánto llevamos acumulado a origen en tal obra y tal categoría?»
es de las que van a caer seguro. Es media hora de trabajo en el `significado` de
dos columnas.

**Lo que la batería sí puede juzgar, y por eso hay que lanzarla igualmente**, es
lo único que catorce pasadas de revisión no han podido responder: si el enrutado
funciona. Si una pregunta en castellano llega al objeto correcto, si el MCP
entrega las 13 reglas duras junto con las fichas, si las 21 filas de contexto
sirven para lo que se pensaron. Eso no se revisa leyendo YAML; se mide
preguntando. **Los 103 objetos, las 798 columnas y el contrato están donde tienen
que estar y el consumidor los lee.**

### Lo que la batería NO va a destapar, y conviene tener delante al leerla

1. **El doblado de `importe_origen`** — arriba. Si se lanza antes de arreglarlo,
   hay que leer con lupa cualquier respuesta que dé un acumulado a origen por
   categoría.
2. **Los 39 «sin contradicción» no tienen la clave demostrada, y 7 objetos
   siguieron sin comprobar** —entre ellos `mart.fact_seguimiento_mensual` y
   `mart.v_pbi_fact`, que son justo los del duplicado, y
   `cierre.v_pbi_cierre_indirectos_detalle`—. Que un dato de hoy no contradiga
   una clave no demuestra la clave. Si una pregunta cae ahí, el número puede
   venir inflado y **la batería no lo notará**, porque juzga si la respuesta es
   plausible, no si cuadra. El implementer lo declara con todas las letras, que
   es lo correcto; lo repito aquí porque hay que tenerlo delante.
3. **La base va a cambiar bajo los pies.** Tras los cuatro `build-*` que el
   humano lanzará a mano desaparecerá la huérfana —que era el síntoma de que la
   base iba por detrás del repositorio— y pueden aparecer objetos nuevos sin
   ficha. **Recomiendo pasar `check-diccionario` después de los builds y antes de
   la batería**: cuesta una conexión de lectura y es la única fuente que dice la
   verdad.
4. **`ocultar` y los recuentos caducados** no los verá ninguna pregunta. Se
   arreglan porque el siguiente que los lea se los va a creer.

## Recuentos caducados, todos verificados por mí

El diccionario creció a **103 objetos / 798 columnas / 48 de consumo** y varios
sitios se quedaron en la cifra anterior. Cargando el diccionario:

```
objetos : 103      columnas: 798      consumo : 48      reglas  : 13
```

| Dónde | Dice | Es |
|---|---|---|
| `main.py:613` — **ayuda visible al usuario** de `check-diccionario` | «los 102 objetos fichados» | 103 |
| `sql/ddl/01_diccionario.sql:7` — **el contrato de API** | «Estas **tres** tablas y esta vista» | cuatro tablas |
| `design.md:11`, `:511`, `:552`; `tasks.md:305-306` | «tres tablas más una vista»; `_meta.yaml` «7 objetos» | cuatro; 8 |
| `progress/current.md:101`, `:131-132` | «102 objetos, 793 columnas», consumo 47 | 103 / 798 / 48 |

El del DDL es el que más me molesta: es el fichero que **define las cuatro** y
que se declara a sí mismo «lo único que este repositorio le garantiza al servidor
MCP». El de `main.py` es el segundo, porque lo lee un humano en la terminal. El
recuento sí se derivó donde tocaba —en el test (`tests/test_f006_catalogo.py:50`,
con su comentario)— y se dejó cableado justo en los dos sitios que se leen.

## El docstring de módulo de `inventario.py`, arreglado a medias

Verifiqué en la primera vuelta que el docstring de `objetos_de_sql`
(`inventario.py:102-105`) ya dice «**ya existe**», y lo di por corregido. El
docstring de **módulo**, cuatro líneas más arriba (`inventario.py:14-17`), sigue
diciendo:

> «**YA EXISTE**, es R28 y **llega en el bloque H**. **Mientras tanto no hay red
> de seguridad detrás de esta puerta**»

Las tres afirmaciones se contradicen entre sí en la misma frase: se corrigió la
parte que el guardián busca y sobrevivieron el futuro y el «mientras tanto». Es
el patrón denunciado, a cuatro líneas del arreglo, y es también un aviso sobre el
método: **buscar una cadena arregla la cadena, no el párrafo**.

## R38 sin cumplir: `azure-apps` no sabe que existe el diccionario

`design.md:552` manda actualizar `azure-apps/datamart_seg_anual.md` «en este
mismo trabajo», y el `CLAUDE.md` global lo pone como regla de propiedad: el dueño
del documento es el proyecto que describe, y se actualiza en el mismo trabajo, no
después. Comprobado en el documento real: **no menciona `_meta.v_diccionario` ni
ninguna tabla del contrato**. Su tabla de consumidores (línea 58) sigue diciendo
que el MCP consume `_meta.v_frescura` y `_meta.v_raw_state`, y la línea 57 lo
describe como «**MCP** (cliente de escritorio)». La única aparición de la palabra
«diccionario» (línea 189) es el diccionario de tablas de Sigrid, que es otra cosa.

`tasks.md:305` sigue en `[ ]`, así que la tarea está viva y no perdida — pero
esta tanda publicó el contrato contra la base real, y el documento que lo tiene
que contar sigue describiendo un mundo sin diccionario. Añado que su redacción ya
nacería caducada: dice «las tres tablas».

## Una copia a mano nueva, sin test que la ate

`config/diccionario/_meta.yaml:479` publica
`valores: [convenciones, ordenes_de_magnitud, ejes, esquemas]`, que replica a mano
`CONTEXTO_PUBLICADO`; el mismo listado vuelve a aparecer en
`01_diccionario.sql:94` y en `design.md:450`. Nada ata esas cuatro copias entre
sí. El día que se publique un quinto bloque de contexto, el mecanismo de
clasificación —que sí funciona— dejará pasar el cambio con su verde, y **el
`valores` que ve el agente quedará mintiendo**. No bloquea hoy; es deuda con
fecha de caducidad conocida, y barata de atar ahora.

## Sobre el aviso de higiene del `git add -A`

Comprobado y sin consecuencias: rehíce la lectura del contrato sobre el rango
completo de la tanda en vez de sobre `9ab9be7`, y el diseño enmendado aparece
repartido entre varios commits, como se me advirtió. El árbol queda limpio y la
redacción del ID de suscripción (F-043) se sostiene en `HEAD`: ni una
coincidencia en los ficheros versionados. El historial lo conserva, y eso está
escrito como excepción aceptada, no como cierre limpio.

## Checkpoints

| | Estado | Razón |
|---|---|---|
| **C1** Entorno en verde | `[x]` | `init.sh` verde: 1968 pasados, 124 saltados, cobertura 98,2 % de 976 líneas. |
| **C2** Trazabilidad requisito → test | **`[ ]`** | R28 y R29 sí. **R10 no**: el derivador exige el aviso en `descripcion`/`grano` y nunca en `columna.significado`, que es donde falta y donde está el número doblado. El guardián de la razón de `ocultar` comprueba que una cadena aparezca, no que sea cierta. |
| **C3** Diff conforme al diseño | `[x]` | Solo los ficheros previstos; dominio sin infraestructura; el contexto en `domain/diccionario.py`, el SQL en `infrastructure/`. |
| **C3 bis** Sin secretos ni prints | `[x]` | Ni GUID ni correo real en el árbol; el ID de suscripción queda redactado en `HEAD` (F-043), con su excepción escrita. |
| **C4** Convenciones y veracidad | **`[ ]`** | Prosa falsa publicada: la razón de `ocultar`, el `total_incurrido` mal clasificado, el «28/200» como prueba de lo que no prueba, «tres tablas» en el DDL del contrato y «102 objetos» en la ayuda de `main.py`. |
| **C4 bis** Campaña de mutación | **`[ ]`** | El informe es del 21-ago 10:42 y cubre 2358 líneas / 166 mutantes; hoy el alcance es **3164 / 252**. Faltan 86 mutantes y dos ficheros enteros. |
| **C4 ter** Cero supervivientes | **`[ ]`** | Depende del anterior: cero supervivientes sobre un alcance que ya no es el vigente no acredita el actual. |
| **C5** Tareas y commits | **`[ ]`** | Además de las MANUAL pendientes por diseño (T19, T27, T29-T34, que **no** son defecto de esta tanda), **T28/R38 sigue sin hacerse y era «en este mismo trabajo»**: `azure-apps/datamart_seg_anual.md` no menciona el contrato del diccionario. Falta también la sección «Evidencias» y la traza RED de los tests nuevos. |

### Trazabilidad de lo nuevo

| Requisito | Test que lo cubre | |
|---|---|---|
| R28 · toda clave del global, decidida | `test_f006_contexto.py::test_f006_r28_toda_clave_del_global_esta_decidida` | ✔ probado con clave inventada |
| R28 · sin solapamiento entre listas | `..._ninguna_clave_esta_en_las_dos_listas` | ✔ |
| R28 · lo excluido lleva motivo | `..._lo_excluido_lleva_su_motivo` | ⚠ exige ≥20 caracteres, no veracidad |
| R10 · el aviso alcanza a todo objeto afectado | `test_f006_stg_trampas.py::..._todo_objeto_que_sirve_medidas_del_fact_avisa` | ⚠ solo mira ficha, no columna |
| R10 · la derivación no está vacía ni infla | `..._control_la_derivacion_encuentra_los_afectados` | ✔ control legítimo |
| R10 · el aviso no se invierte otra vez | `..._el_aviso_no_alarma_sobre_la_medida_sana` | ✔ |
| Plegado YAML como clase | `tests/_texto.py`, usado por `test_f006_cobertura.py` y `test_f006_copias.py` | ✔ con dos controles |
| R38 · documento de `azure-apps` | — | ✘ sin cubrir y sin hacer |

## Automejora que propongo (no aplico): la campaña puede caducar y nadie se entera

El grave de esta pasada **no es culpa del implementer, es un agujero del arnés**.
`harness/init.sh` dice en sus líneas 428-430, y con razón, que la mutación no
corre ahí porque es cara, y que «el reviewer la comprueba por
`progress/mutacion_F-XXX.md`». El problema es que **nada comprueba que ese
informe siga siendo válido**: se escribe con su fecha, el código sigue creciendo,
y el fichero de ayer parece exactamente igual de verde que el de hoy.

En una feature de tanda única eso casi nunca muerde. En una de **catorce
pasadas**, con siete commits de producción después de la campaña, muerde seguro.
Y lo he cazado a mano; si en esta pasada me hubiera limitado a comprobar que el
informe existe, dice 0 supervivientes y sus totales cuadran **entre sí**, habría
aprobado. Cuadran entre sí perfectamente: lo que no cuadra es con `HEAD`.

**Propuesta concreta**, barata y que automatiza justo el fallo:

1. Que `harness/mutacion.py` estampe en el informe el **SHA de `HEAD`** sobre el
   que se generó la campaña, además de la fecha y el `ref_diff` que ya escribe.
2. Que `harness/init.sh`, en la feature `in_progress`, compare ese SHA con el
   `HEAD` actual y emita una línea **`PUERTA MUTACION: [CADUCADA]`** cuando entre
   medias haya commits que toquen ficheros de producción. No hace falta ejecutar
   la campaña —que es lo caro—: basta un `git log` para saber que hay que
   relanzarla.
3. Que `.claude/agents/reviewer.md` añada al punto 4 de la validación de rigor:
   «comprueba que la campaña se generó sobre el `HEAD` que revisas; un informe
   correcto de una versión anterior del código no acredita la actual».

Los tres cambios valen para **cualquier** proyecto, así que, si se aprueban, van
a `arnes-base` en el mismo trabajo, por la regla de propagación del `CLAUDE.md`.

### Segunda propuesta: un guardián no puede validar una prosa

Los dos graves nuevos de esta pasada tienen la misma forma, y no es casualidad:
**un test verde comprobando que una cadena aparece, encima de una afirmación
falsa**. `..._lo_excluido_lleva_su_motivo` exige veinte caracteres de razón y da
por buena una razón que describe un mecanismo inexistente. El derivador de R10
exige el aviso en `descripcion` y deja intacta la columna que lleva el número
doblado. En ambos casos el guardián certifica **presencia**, y lo que hacía falta
era **veracidad**.

No propongo un test que valide prosa, porque no existe. Propongo dos cosas
baratas para `CHECKPOINTS.md`:

1. **Que un guardián de prosa declare explícitamente qué NO comprueba.** Una línea
   en su docstring: «comprueba que la razón existe y tiene contenido; **no**
   comprueba que sea cierta — eso es trabajo del reviewer». Convierte un verde
   engañoso en un verde honesto, y le dice al reviewer dónde tiene que mirar a
   mano.
2. **Que cuando un aviso corrija un número, el checkpoint pida verificar la ficha
   de la columna afectada, no solo la del objeto.** Es el punto ciego que hemos
   repetido tres veces en esta feature, y el reviewer —yo— lo heredé del guardián
   que estaba revisando.

Y una tercera, para el rol reviewer: **cuando encargue una auditoría, esperarla o
decir que no la encargué**. Dar por perdida la de esta pasada me costó dos graves
y una cifra copiada mal, y la primera versión del informe ya llevaba escrito, con
todas las letras, que no me apoyaba en nada que no hubiera verificado yo.

Y una observación que va con esto: llevo catorce pasadas comprobando que los
totales de mutación cuadran, y **hasta hoy los comparaba solo consigo mismos**.
La verificación que mi propio protocolo pide —recalcular con `harness.alcance` y
`generar_mutantes`— vale para cazar un informe escrito a mano, que era el miedo
original, pero solo caza un informe caducado si uno recuerda que el alcance de
hoy puede no ser el de la campaña. Merece decirlo explícitamente en el protocolo,
porque es un modo de fallo distinto del que estaba previsto.

## Nota de método, para que conste

Encargué en paralelo una auditoría independiente y **escribí la primera versión
de esta pasada dándola por perdida**, porque no había devuelto nada en mi
ventana. Dejé escrito entonces: «no me apoyo en nada que no haya verificado yo».
Volvió después, con **cinco hallazgos que yo no tenía**, dos de ellos graves. He
reescrito la pasada entera.

Lo dejo a la vista en vez de limpiarlo porque las dos lecciones son del mismo
tipo que llevo catorce pasadas señalando, y esta vez me tocan a mí:

- **Di por cerrado el DEFECTO 3 mirando donde se había arreglado.** Verifiqué el
  aviso en `descripcion` y en `grano` —que es donde el derivador lo exige— y no
  abrí las fichas de columna, que es donde vive el número doblado. Mi
  verificación heredó el punto ciego del guardián que estaba verificando.
- **Copié 102 objetos / 793 columnas de las pasadas anteriores** en lugar de
  recalcularlos, en el mismo informe en el que reprocho exactamente eso. Son 103
  y 798.

Y una tercera, sobre el encargo: dar por perdida una auditoría por impaciencia
sale igual de caro que no encargarla. La diferencia entre mi primera versión y
esta —un grave contra tres— es lo que costaron esos minutos.

Lo que sostiene esta pasada lo he comprobado personalmente, incluido todo lo que
vino de la auditoría, que **no he dado por bueno sin repetirlo**: el recálculo del
alcance y de los mutantes; el `SUM(importe_origen)` leído en el SQL del build y
la medición fila a fila del informe; el recuento real cargando el diccionario; el
gancho de tabla contra la lista de columnas de `ocultar`; las 21 filas de
contexto; la clasificación de las once claves; el experimento de la clave
inventada; el barrido de prosa cruda por los ficheros de test; la búsqueda de
código muerto en los módulos fuera del alcance declarado; y el documento de
`azure-apps` abierto y leído.

## Qué hace falta para que esto pase a APROBADO

Por orden de lo que más daño hace si se queda:

1. **Bajar el aviso de `importe_origen` a la ficha de columna** en
   `mart.fact_seguimiento_categoria` y `mart.v_pbi_fact_categoria`: decir que el
   valor **almacenado** viene sumado dos veces para las series afectadas, y qué
   usar en su lugar. Y que el derivador lo exija **en la columna**, no en la
   ficha, o el punto ciego sigue ahí.
2. **Relanzar `python -m harness.mutacion --feature F-006` sobre `HEAD`**, con los
   `__pycache__` borrados antes (F-041), y volver con los totales reales: 252
   mutantes, no 166.
3. **Reescribir la razón de `ocultar`** para que diga la verdad —nunca funcionó,
   lista columnas contra un gancho de tabla— y abrir la deuda de decidir si se
   implementa a nivel de columna o se retira.
4. **Corregir `total_incurrido`** de saco y **retirar el «28/200»** como prueba
   del doblado, citando en su lugar la medición fila a fila que sí lo prueba.
5. **Actualizar los recuentos**: `main.py:613` (102 → 103),
   `sql/ddl/01_diccionario.sql:7` («tres tablas» → cuatro), `design.md:11/511/552`,
   `tasks.md:305-306`, `progress/current.md:101/131-132`.
6. **Cerrar T28/R38**: `azure-apps/datamart_seg_anual.md` con el contrato del
   diccionario, ya con el recuento bueno.
7. **Rematar el docstring de módulo** de `inventario.py:14-17`, del que solo se
   corrigió la parte que buscaba el guardián.
8. **Cerrar la tanda con «Evidencias»** y los cuatro números, y con la traza RED
   de los tests nuevos.

Los puntos 1 y 2 son los que bloquean de verdad. Del 3 al 8 son prosa falsa y
deuda: ninguno rompe un número, y todos se los va a creer el siguiente que los
lea.

### Sobre lanzar la batería mientras tanto

**Puede lanzarse**, corre contra lo ya publicado y mide lo único que la revisión
no alcanza —el enrutado—. Pero **el punto 1 antes**, si es posible: son dos
`significado` y evita que la primera pregunta sobre acumulado a origen devuelva
el doble con una ficha respaldándolo. Los puntos 2 al 8 no tienen por qué
esperarla, y la campaña son unos 19 minutos de máquina sin nadie delante.

---

# DECIMOTERCERA PASADA · 2026-08-21 — los tres graves, cerrados

> Commits revisados: `39c83f7` y `9ea8346`.

## Veredicto de la decimotercera pasada

**RECHAZADO**, y **rectifico el APROBADO que ya había emitido**. Es la sexta vez
en esta feature, siempre por lo mismo: emito antes de que vuelva la auditoría que
yo mismo encargo, y verifico lo que la tanda dice haber hecho en lugar de buscar
lo que se le ha escapado. Los cuatro defectos los he confirmado uno a uno.

**Lo que sí está cerrado, y bien**, sigue en pie: el `READ ONLY` aplicado de
verdad y comprobado sobre lo que el cliente ejecuta, la republicación con
`version: 2` y el mecanismo que detecta la desincronización, las evidencias
completas —los hashes pegados casan con árboles reconstruidos, no son
inventables— y los siete NO COMPROBADO con nombre.

Lo que falla son **dos reincidencias del patrón que esta misma tanda decía
cerrar**, y dos huecos en la propagación del aviso.

---

## Los dos graves

### 1 · El guardián de R28 está verde sosteniendo una afirmación falsa

`etl_sigrid/domain/inventario.py:102-105` sigue diciendo, hoy:

> «La comprobación contra `information_schema` … es `python main.py
> check-diccionario` (R28) y **está sin implementar**: llega en el bloque H.
> Hasta entonces esta heurística es lo único que hay.»

Y `check-diccionario` **existe desde este commit**. El guardián escrito para
impedir justo eso (`tests/test_f006_cobertura.py:172-201`) busca la subcadena
literal `"sin implementar"` en ese fichero, y **el ajuste de línea la parte** en
`"está sin\n    implementar"`. Lo medí:

```
'sin implementar' in inventario.py            -> False
'sin implementar' in " ".join(texto.split())  -> True
```

Es **el mismo punto ciego del plegado que yo demostré en la décima pasada** con
`test_f006_copias.py`, tercera aparición, y esta vez dentro del dispositivo
escrito para evitarlo. Además no es un docstring cualquiera: `objetos_de_sql` es
la heurística cuya única red de seguridad **es** R28, y su documentación sigue
diciendo que esa red no existe.

*Arreglo*: normalizar espacios antes de buscar y ampliar el vocabulario («no
existe», «llega en el bloque H», «pendiente»).

### 2 · Código muerto nuevo, con test verde, en la tanda que dice haberlo barrido

`PostgresClient.list_objetos_catalogo` (`postgres_client.py:841-856`) hace lo
mismo que el nuevo `fetch_catalogo_objetos` (`:692-705`) y ejecuta la **misma**
constante SQL. Su **único consumidor en todo el repositorio** es un test
(`test_f006_publicacion.py:589,594`). Producción no lo llama.

El barrido de constructores muertos —que celebro, y que encontró el que yo
denuncié— **solo escanea los `def` de nivel de módulo de `unicidad_sql.py`**, así
que no puede ver este. La afirmación «era el único» es cierta dentro de un
alcance que no se declara, y el contraejemplo lo introduce el mismo commit.

---

## Los dos huecos de propagación

### 3 · El aviso alarma sobre la medida sana y calla la enferma

El aviso de `mart.fact_seguimiento_categoria` (`mart.yaml:270-277`) dice que
«**el importe de esas obras y meses viene inflado**» y separa por **escenario**
—`Coste Real` y `Venta Real` sí, master no— pero **no por medida**. Contra el SQL
no son equivalentes:

- **`importe_origen`** es acumulado e **idéntico en las dos filas** —la propia
  evidencia lo enseña: `27850.08 | 27850.08`—, así que el `SUM` del agregado
  **lo duplica**. Inflado, cierto.
- **`importe_mes`** se calcula con `LAG` particionado por
  `(obra_id, partida_id, ambito_id)` —no por fase— en
  `stg/08_plan_mensual.sql:331-360`: las dos filas llevan `origen(12)−origen(11)`
  y `origen(13)−origen(12)`, y su suma **telescopea** al incremento correcto.
  **No se infla.**

O sea: el aviso pone bajo sospecha la medida que Power BI usa para toda serie
temporal y no señala la única realmente rota. Y las fichas de esas dos columnas
(`mart.yaml:321-332`) no dicen nada.

### 4 · La propagación dejó fuera una quinta ficha, y es de consumo

`mart.v_pbi_fact_categoria` (`mart.yaml:475-487`) es `consumo_recomendado: true`,
proyecta `importe_origen` desde la agregada (`05_views_powerbi.sql:177-187`) y
**no tiene ni una palabra del duplicado**. Es la vista que Power BI consume para
las tarjetas de KPI. «Las cuatro avisan» es cierto; que fueran cuatro, no.

*(`cierre.v_pbi_planif_vs_real` también lee la agregada, pero solo `importe_mes`,
así que **no** está afectada — justo la distinción que el defecto 3 no hace.)*

---

## Y la cobertura, tercera vez, ahora con la prueba hecha

Ya no es una opinión: se midió. De las 85 líneas sin cubrir, **64 están en
`main.py`** —el cuerpo **entero** de `check-diccionario` (619-648) y el de
`check-unicidad` (699-757)— y 12 en los dos métodos nuevos del cliente.
`catalogo.py`, en cambio, está al **100 %**: el módulo está bien cubierto; lo que
no lo está es el pegamento.

Y se demostró que era cubrible con lo que ya hay: añadiendo un `CliRunner` con
`main._get_pg` sustituido —el patrón de `test_f006_publicacion.py:856-863`— la
cobertura pasa de **90,9 % a 93,4 %**, **+23 líneas con unas 40 de doble y sin
abrir una conexión**. «El bloque nuevo añade líneas de CLI» describe dónde está
el hueco, no por qué sigue ahí.

Lo que agrava: esas líneas sin test son precisamente donde vive lo que la tanda
presenta como su entrega —el desfase de hash, el `SystemExit(1)`, el aviso de
`_meta` vacío—.

---

## Lo que sí está cerrado y verificado

- **El `READ ONLY` se aplica de verdad.** `SET LOCAL transaction_read_only = on`,
  y el diagnóstico es correcto: `BEGIN READ ONLY` no vale porque la conexión llega
  ya en transacción. El test mira **lo que el cliente ejecuta**, con cursor espía.
- **La republicación y su mecanismo.** `version: 2`, hash nuevo, y
  `check-diccionario` comparando el `hash_fuente` publicado con el del árbol: KO
  antes, OK después, y salta siempre que difieran.
- **Las evidencias son sólidas y reproducibles**: el log completo con
  `hash_fuente`, las cuatro comprobaciones con su salida, y los **siete NO
  COMPROBADO con nombre y clave** —`mart.v_pbi_fact` entre ellos—. Los hashes
  pegados casan exactamente con árboles históricos reconstruidos: no son
  inventables.
- **`check-diccionario` alcanza a los 102** —los nueve esquemas, no la superficie
  de consumo—, comprueba **las tres direcciones** y **no pasa en vacío**:
  probado, con `information_schema` a cero da 102 huérfanas y `exit=1`.
- **El dato de los 180 s es exacto** y confirma mi deducción: el fact sale NO
  COMPROBADO a 30 s y a 60 s, y solo a 180 s revela los 8.778. Es el mejor
  argumento para **F-041**.
- **La huérfana no bloquea**: no lanzar `build_cierre` fue obedecer la firma, ya
  no es un estado silencioso y no es objeto esperado de ninguna pregunta.

---

## ¿Listo para la batería? El contenido sí; el diccionario, tras cerrar los cuatro

De las cuatro condiciones que puse en la pasada anterior, **tres están hechas**:
republicado con `version: 2` y hash nuevo, el `READ ONLY` aplicado de verdad, y el
aviso propagado —aunque a cuatro fichas de **cinco**, que es el defecto 4—. La
cuarta, `build_cierre`, no es del implementer.

**Antes de la batería hay que cerrar los cuatro defectos de esta pasada.** Ninguno
es estructural y dos son de una línea, pero dos tocan lo que el MCP sirve: el
aviso que señala la medida equivocada (defecto 3) y la quinta ficha sin aviso
(defecto 4). Si la batería corre antes, P8 y las preguntas de KPI se responderían
sobre `importe_origen` inflado sin advertencia, y quien lea el aviso desconfiará
de `importe_mes`, que está sano. Los dos graves no afectan a lo publicado, pero
dejan al repositorio afirmando que R28 no existe y arrastrando código muerto
recién creado.

Lo que falta, exactamente:

1. **Autorizar y lanzar `build_cierre`** (humano). Deja `check-diccionario` en
   verde y la base al día con el repositorio. **No condiciona las preguntas**: esa
   vista no es objeto esperado de ninguna.
2. **Decidir cómo se ejecuta T39.** DA-4 dijo que contra el prototipo local
   apuntado a Azure, y eso implica abrir la regla de firewall del puesto en cada
   tanda, con la salvedad de D11 (CGNAT rota la IP). Conviene fijarlo antes de
   empezar, no a mitad.
3. **Leer el resultado con el criterio ya escrito** (R41): el éxito son **13
   respondibles bien contestadas y 5 bien rechazadas** —3 parciales y 2
   imposibles—, no 18 de 18. Un «no puedo, y este es el motivo» correcto cuenta
   como acierto.

Y una advertencia para interpretar lo que salga: **los 39 objetos «sin
contradicción» de T26 no tienen la clave demostrada**, solo no la contradicen con
los datos de hoy; y siete siguen sin comprobar. Si una pregunta de la batería da
un número raro sobre uno de ellos, el diccionario es el primer sitio donde mirar,
no el último.

---

# DUODÉCIMA PASADA · 2026-08-21 — la primera contra la base real

> Commits revisados: hasta `726e009` (más `b2a2b06`, el alta de F-042 y F-043).
> Esta tanda se ejecutó **contra la base de Azure**, con autorización del humano
> acotada a crear el `_meta` del contrato y publicar el diccionario.

## Veredicto de la duodécima pasada

**RECHAZADO**, y **rectifico el mío propio**: emití «un solo defecto, de alcance»
antes de tener las dos auditorías que había encargado. Al llegar, encontraron
tres cosas graves que yo no vi, y las he confirmado una a una contra el código.
Es la quinta vez en esta feature que me pasa, y el patrón vuelve a ser el mismo:
verifiqué lo que la tanda dice haber hecho, no lo que la evidencia demuestra.

Que conste primero lo que sigue siendo cierto, porque es lo importante de la
pasada: **ejecutar contra la base real destapó en una tarde un defecto de datos
que once pasadas de revisión estática no podían ver**, y la ficha que lo
documenta es la mejor de la feature. La decisión estaba bien tomada.

Pero hay tres defectos graves, y dos de ellos no son de contenido: son de
**confianza en la evidencia**.

---

## Los tres graves

### 1 · El `READ ONLY` que se le anunció al humano no existe

`main.py:658` imprime por pantalla, antes de ejecutar contra el servidor
compartido con producción:

> `statement_timeout = 30s por consulta, transaccion READ ONLY`

**No hay ninguna transacción de solo lectura.** Lo verifiqué: `comprobar_unicidad`
(`postgres_client.py:665-685`) emite exactamente dos sentencias —`SET LOCAL
statement_timeout` y la consulta— y **ningún `BEGIN READ ONLY`**. El constructor
que sí lo emite, `sentencias_de_la_transaccion` (`unicidad_sql.py:196`), tiene un
único consumidor en todo el repositorio: **el test** (`test_f006_unicidad.py:201`).
Es código muerto en producción, y su test está verde afirmando
`sentencias[0] == "BEGIN READ ONLY"`.

El riesgo material es bajo —lo generado son `SELECT count(*)` con identificadores
citados— pero la garantía que se le dio al operador por pantalla era falsa, y el
test que la respalda fija la coherencia con un artefacto que producción no usa.
Es literalmente el patrón que esta misma review denunció en su novena pasada.

### 2 · Lo publicado ya no es lo del repositorio, y nadie lo dice

El commit `726e009` es el que publica el diccionario en `_meta`… y **el mismo
commit edita `config/diccionario/mart.yaml`** (+23 líneas: justo el aviso del
duplicado). Se publicó, se cambió el contenido y **no se volvió a publicar**.

Consecuencias que no son teóricas:

- El `hash_fuente` que hay en `_meta.diccionario_publicacion` **ya no es el del
  repositorio**, que es exactamente la garantía que `design.md` §4.3 vende y que
  el `COMMENT ON COLUMN` manda mirar para invalidar caché.
- `version` sigue en `1` pese a un cambio material.
- Y lo que importa: **el MCP sigue leyendo hoy que
  `(obra_id, partida_id, anio_mes, escenario)` identifica una fila** del fact. El
  arreglo está en git; la base sirve la versión mentirosa.

### 3 · La evidencia pegada de T19 está recortada justo donde dolería

`resumen_publicacion` (`diccionario_sql.py:231`) emite **siempre** `hash_fuente`.
El log pegado como prueba de la publicación (`impl_F-006.md:3498`) va **sin él**,
con las demás claves en orden alfabético y el hueco exactamente donde iría. El
mismo evento aparece **con** `hash_fuente` en otro punto del propio informe.

Puede no haber intención —la cabecera dice «salidas reales, redactadas de
identificadores», y alguien pudo tomar el hash por uno—, pero un SHA-256 de
ficheros YAML públicos no es un identificador ni un secreto, y el efecto es que
**falta el único campo que habría delatado el defecto 2**. Además, de las cuatro
comprobaciones que la sección titula «sobre la salida real», **tres no traen
ninguna salida**: la existencia de los 7 objetos, el orden de las 19 columnas y
el singleton se afirman en prosa. La lista de columnas pegada es indistinguible
de haber copiado el DDL.

---

## Y dos más, de gravedad media

4. **El «Bloque H» no lo produjo ningún comando del repositorio**: `check-diccionario`
   (R28) **no existe** —no hay tal `@cli.command` en `main.py`—, y lo que se
   presenta como su resultado sale de la sonda de unicidad. Que la huérfana
   `cierre.v_pbi_planif_vs_real` se detectara es un **efecto colateral** de un
   `except psycopg.errors.UndefinedTable`, no una comprobación de existencia. Por
   eso solo alcanza a los 47 objetos de consumo con clave: los otros 55 podrían
   faltar en la base sin que nada lo diga.
5. **Los siete NO COMPROBADO no se nombran, y uno de ellos era el defecto de la
   feature.** El código los trata de forma ejemplar —nunca cuentan como OK,
   restan del recuento y devuelven código 1—, pero el informe pegó solo la línea
   de Resumen. Y se deduce de sus propios números: la pasada 1 dio «0 con la
   clave rota» y la 2 dio KO en `mart.fact_seguimiento_mensual`, luego **ese
   objeto era uno de los siete**. Los siete son, por construcción, los más
   grandes: justo donde una clave corta colisiona antes.

---

## El alcance de la clave rota: no es una tabla, son cuatro objetos

Este es el hallazgo de la pasada y lo verifiqué por mi cuenta, porque la pregunta
que importa no es si el número es cierto —lo es— sino **hasta dónde llega**.

Recorrí el diccionario buscando quién se apoya en esa clave:

| Objeto | Qué declara | ¿Lo dice? |
|---|---|---|
| `mart.fact_seguimiento_mensual` | clave `(obra_id, partida_id, anio_mes, escenario)` | **Sí**, corregida: 8.778 casos, siempre dos filas, 22 obras con dos fases |
| **`mart.v_pbi_fact`** | **la misma cuaterna** como clave | **No dice nada** |
| **`mart.v_fact_periodificado`** | **la misma cuaterna** como clave | **No dice nada** |
| **`mart.fact_seguimiento_categoria`** | agrega con `SUM(importe_mes)` sobre el fact (`03_agg_categoria.sql:67,72`) | **No dice nada** |

Las dos vistas **heredan la fila** del fact, así que su clave es falsa por la
misma causa y en la misma medida. Y el agregado es peor que una clave falsa: la
causa que F-042 documenta —la fase 13 «AGOSTO 2010» guardada con `mes = 6`—
significa que **dos fases de meses distintos acaban en el mismo `anio_mes`**, así
que el `SUM` del agregado **imputa a un mes lo que pertenece a otro**. Eso no es
una advertencia de clave: es un importe equivocado en un objeto de consumo.

Las dos relaciones con lado `1` que apuntan a la tabla van por `fact_id`
(`1:1`), que es la PK real y sí es única: esas no se ven afectadas. El daño está
en las tres fichas de arriba.

## La ficha corregida es excelente, y hay que decirlo

La de `mart.fact_seguimiento_mensual` es el mejor ejemplo de esta feature de cómo
se documenta un defecto que no se puede arreglar aquí. Trae:

- **el número medido y desglosado**: 8.778 combinaciones, siempre exactamente dos
  filas, 4.754 en `Coste Real` y 4.024 en `Venta Real`;
- **la causa localizada con ejemplo real**: la obra 584748 tiene las fases 12
  («Junio 2010») y 13 («AGOSTO 2010»), y las dos llevan `ano = 2010, mes = 6`;
- **por qué no se puede arreglar en la ficha**: ninguna columna publicada las
  distingue —solo cambian `nombre_mes`, `version_descripcion` y
  `total_incurrido`—, así que no se puede alargar la clave con lo que hay;
- **las consecuencias de número**: un `SUM(importe_origen)` por esa clave cuenta
  dos veces el mismo importe (27.850,08 en el ejemplo) y un `JOIN` produce
  fan-out;
- **el acotado**: los ámbitos master (8 y 11) no están afectados;
- y **el apaño mientras tanto**: agregar también por `nombre_mes`.

Corregir la ficha y no el build es además la decisión correcta: `mart` es de otra
feature y la autorización de esta tanda llegaba hasta `_meta`.

El problema es de alcance: ese texto está en una de las cuatro fichas.

## El efecto de segundo orden, verificado: no se materializa

El informe advierte, con razón, de que «la detección de cardinalidades deriva la
unicidad de esta clave, así que todas las relaciones que apuntan a este fact se
validaron contra una premisa falsa». Lo comprobé una a una y **la consecuencia no
llega**: las dos únicas relaciones con lado `1` hacia el fact —desde `v_pbi_fact`
y desde `v_fact_periodificado`— van por **`fact_id`**, que es la PK `BIGSERIAL`
real y sí es única. Ninguna cardinalidad del diccionario cambia de veredicto. Es
un punto a favor que conviene dejar escrito, porque el temor era razonable.

## Los dos incidentes de secretos

Los reviso porque la regla del proyecto es dura y explícita, y porque uno de los
dos es de esta tanda.

- **El de esta tanda está bien resuelto.** Al pegar la salida real de `az` entraron
  un GUID de tenant y un correo del puesto en `progress/`. La guarda de F-003 lo
  cazó, se redactó y **se reescribió el commit con `--amend`** en vez de arreglarlo
  en uno posterior, que es lo correcto: el historial no suelta lo que entra. Lo
  verifiqué: **el diff completo de la rama (`dev...HEAD`) no introduce ni un GUID
  ni un correo real**, y ningún fichero versionado del repositorio contiene un
  GUID (los que aparecen en un barrido ingenuo son todos de `.venv`).
- **El otro es preexistente, real y sigue expuesto.** `progress/review_F-005.md`
  contiene el ID de suscripción de Azure; entró en el commit `5b486d4` —el cierre
  de F-005— y, según su propia ficha, **ya está en GitHub**. Lo confirmé: tres
  commits del historial lo contienen. En el árbol de hoy está truncado, pero el
  historial no. **No nació en F-006 y F-006 no lo empeora: lo detectó**, y está
  dado de alta como **F-043**. No bloquea esta feature, pero la limpieza del
  historial y la valoración de rotar lo que toque son acción del humano y
  conviene que no se quede en la cola.

## La bajada de cobertura: la explicación no se sostiene

Se atribuye la caída de 99,0 % a 93,7 % a que «el bucle del CLI no se puede
cubrir sin conexión» y a que «llega con T27». Lo comprobé y no es así:

- **El propio repositorio ya resolvió ese problema, en esta misma feature, dos
  bloques antes.** `tests/test_f006_publicacion.py:854-860` cubre el comando
  `publicar-diccionario` con `CliRunner` y `monkeypatch.setattr(main, "_get_pg",
  …)` más un `get_settings` falso: sin conexión y sin base.
- `tests/test_f006_unicidad.py` **no usa `CliRunner` ni una sola vez**. Cubre muy
  bien la parte pura —que la consulta agrupe por la clave entera, que no use
  `COUNT DISTINCT`, que no interpole identificadores, que la transacción no
  escriba, que un resultado vacío no signifique que la clave es correcta— y deja
  el comando sin tocar.

O sea: lo que falta no es incubrible, es que no se hizo, y hay un patrón propio a
mano. Se comprobó además ejecutando `--dry-run` con `CliRunner`: **retorna antes
de abrir conexión** y cubre 18 de esas líneas sin doble alguno, y las 23 restantes
se alcanzan con el `_ClienteFalso` que ya vive en ese mismo fichero de tests. De
las 41 líneas del comando, **las 41 eran cubribles**. Y «llega con T27» tampoco cierra el hueco: T27 es una ejecución manual
contra la base, y la puerta mide cobertura con la suite, no con lo que alguien
ejecute a mano. Sigue por encima del umbral (80 %) y no bloquea, pero la
explicación es más cómoda que la realidad.

## Y la conexión con la batería, que es lo que decide

Crucé los objetos afectados con los `objetos_esperados` de las 18 preguntas:

| Pregunta | Objeto esperado | ¿Tiene el aviso? |
|---|---|---|
| P6, P11, P18 | `mart.fact_seguimiento_mensual` | **Sí** |
| **P8** | **`mart.fact_seguimiento_categoria`** | **No** |

`cierre.v_pbi_planif_vs_real` —la huérfana que existe en el repositorio y no en
la base— **no es objeto esperado de ninguna pregunta**, así que su ausencia no
falsearía la batería. Eso juega a favor.

## ¿Está el diccionario listo para la batería?

**Todavía no, y ahora las condiciones son cuatro.** En mi primera redacción dije
«casi, con dos»; con los tres graves confirmados, la lista crece — y una de ellas
es que lo que el MCP lee **hoy** no es lo que dice el repositorio.

1. **Propagar el aviso del duplicado a las tres fichas que faltan.** Es media
   hora y cierra el único defecto abierto. Sin ello, P8 se responde sobre
   importes afectados sin advertencia, y la batería mediría mal por culpa nuestra.
2. **Lanzar `build_cierre` antes de la batería.** El bloque H demuestra que **la
   base va por detrás del repositorio**: hay una vista publicada en el SQL que no
   existe en la base porque ese build no se ha vuelto a ejecutar. Si la batería
   corre contra la base tal cual, alguna pregunta podría fallar por un objeto
   ausente y no por el diccionario, y eso ensucia la medición.

3. **Republicar, y con `version` subida.** Es la condición nueva y la más
   importante: la base sirve ahora mismo un grano que la propia tanda ha
   demostrado falso. Publicar y luego editar el diccionario en el mismo commit
   deja el contrato caduco; si la batería corre contra lo publicado, medirá el
   diccionario de ayer.
4. **Aplicar de verdad el `READ ONLY`** —o dejar de anunciarlo— antes de volver a
   ejecutar nada contra el servidor compartido.

Con esas cuatro, mi respuesta es **sí**. El contenido está: 102 fichas, 793 columnas,
13 reglas, `pendientes` en 0, el contrato publicado y comprobado contra el diseño.
Y sostengo lo que dije en la pasada anterior, ahora con un argumento más fuerte:
**la vía rentable ya no es leer el YAML contra el SQL, es preguntarle a la
realidad**. T26 lo acaba de demostrar; la batería es el siguiente paso de esa
misma línea y mide lo único que sigue sin medirse.

---

# UNDÉCIMA PASADA · 2026-08-21 — los seis, y el punto de rendimientos decrecientes

> Commits revisados: `c56daa6`..`6b84da6`.

## Veredicto de la undécima pasada

**APROBADO.** Los seis defectos de la décima están cerrados, verificados uno a
uno contra el SQL, y los dos focos que se me pidieron atacar salen bien: **mi
experimento del plegado ahora falla** —y ha quedado como control permanente— y
**el punto ciego de las 32 columnas está honestamente acotado**, comprobado en
los dos sentidos.

No queda ningún defecto abierto. Lo que sigue es mi lectura del punto de
rendimientos decrecientes, que es lo que se me pidió además del veredicto.

---

## Los dos focos que se me pidieron

### 1 · Mi experimento del plegado: ahora falla, y ha quedado como control

Reejecuté exactamente el mismo experimento de la décima pasada —plantar en
`stg.obras.motivo_no_consumo` dos frases que las pasadas séptima y octava
rechazaron, **plegadas como las pliega el propio YAML**—. Antes: `14 passed`.
Ahora:

```
FAILED tests/test_f006_copias.py::..._ninguna_frase_rechazada_sobrevive_en_el_fichero[stg.yaml]
AssertionError: stg.yaml conserva 2 frase(s) que una revisión ya rechazó
```

Y, mejor que el arreglo, **el experimento quedó como control permanente**
(`test_f006_r26_control_el_barrido_ve_una_frase_plegada`): fija que la frase **no
está** en el texto crudo y **sí** en lo que se publica, y que el barrido la ve. Si
alguien revierte el barrido a mirar solo el fichero, ese control cae. Es la
diferencia entre arreglar un caso y cerrar la clase.

### 2 · El punto ciego de las 32 columnas: **el acotado es honesto**

Lo comprobé en vez de creerlo, y en los dos sentidos:

- **El número es correcto.** Recorrí el ámbito de `R-IMPORTE-MES` contando las
  columnas con `agregacion` que aparecen en un solo objeto: **32**, exactamente
  las que declara.
- **La parte que cierra es la que cazaba el defecto real**: «ningún porcentaje se
  declara sumable», y es una comprobación **por columna**, no cruzada, así que
  alcanza a las que están solas —que es justo donde se escondía
  `pct_acumulado`—. Tiene control anti-vacío (`>= 8` porcentajes).
- **La parte que declara no es comodidad.** Busqué si en esas 32 quedaba algo
  derivable por otro criterio evidente —columnas cuyo nombre dice `*_origen` o
  `*acumulad*`, que fue como yo encontré `pct_acumulado`—: son **6**, y **las 6
  están correctamente marcadas** (`promedio` o `ultimo_valor`). Es decir, lo
  declarado «no derivable» **no esconde ningún defecto vivo**.
- Y el hueco lleva un test que salta si cambia de tamaño (25–40), que es lo que
  impide que la comprobación cruzada se degrade en silencio.

**Mejora posible, no defecto**: añadir el criterio por nombre —`*_origen` /
`*acumulad*` no puede ser sumable— cerraría 6 de esas 32 con la misma lógica que
los porcentajes. Hoy no cambiaría ningún veredicto.

## Los seis, verificados

| # | Defecto de la décima | Estado |
|---|---|---|
| 1 | `entidad_cif`: mecanismo falso en la mitad CLIENTE | **cerrado**. Las cuatro fichas dicen ahora «**solo existe en la mitad PROVEEDOR**. En `sentido = 'CLIENTE'` la consulta escribe un NULL constante», que es exactamente lo que hace `01_movimientos.sql:107` |
| 2 | `maestro.proveedores_obra.razon_social` | **cerrado**: «de su ficha (`prv.raz`), **en crudo**», alineada con su hermana |
| 3 | El punto ciego de la comprobación cruzada | **cerrado en la parte derivable y declarado en el resto** (ver arriba) |
| 4 | `pct_acumulado` sumable | **cerrado**: pasa a `promedio`, y con él `pct_mes` |
| 5 | Los recuentos inventados en la prosa | **cerrado**: los números salen de la prosa y se miden en controles. Las cuatro menciones que quedan son hechos verificados o **la cita del propio error** —«y "tres tablas" donde son cinco»—, que es la forma correcta de no repetirlo |
| 6 | El ejemplo del `anio = 0` | **cerrado y mejorado**: ahora dice que `make_date(f.anio, f.mes, 1)` «con `anio = 0` **aborta el build** en vez de colar una fila silenciosa», mantiene la conclusión de fondo y añade el consejo operativo: comprobar contra `0`, no contra NULL |

## Rigor e higiene

- **1895 tests**, 122 saltados, cobertura **99,0 %**, ejecutado por mí.
- **Mutación**: 2358 líneas, 166 mutantes, 0 supervivientes, 0 timeouts.
- **Nada prohibido**: el diff toca tres YAML, tres ficheros de tests y
  `progress/`. **`harness/` y `etl_sigrid/` intactos**, ni un `GRANT`, `REVOKE`,
  firewall, Azure ni conexión a la base. **Sin `push`**.

---

---

## La deuda declarada, con nombre y línea

Los seis están cerrados, pero la pasada deja cuatro cosas anotadas. **Ninguna
produce un número falso** y ninguna bloquea; las escribo con su ubicación para
que se puedan cerrar cuando se toque esa zona.

1. **Décimo caso del patrón de la copia, y esta vez fuera del alcance del
   barrido.** `tests/test_f006_stg_trampas.py:151-163`: el docstring del test
   sigue publicando como conclusión vigente «el filtro `f.anio IS NOT NULL` […]
   **no descarta nada**, y una fase con `anio = 0` **entra igual**» — la frase
   exacta que el defecto 5 acaba de rechazar por falsa. El test que la corrige
   está 290 líneas más abajo, en el mismo fichero. El barrido de copias **no
   puede verlo**: solo mira `config/diccionario/*.yaml`. Es el hueco de alcance
   que queda: la prosa de los tests no está barrida.
2. **Una ubicación falsa en ficha publicada.** `stg.yaml:598-600` dice que
   `make_date(f.anio, f.mes, 1)` está «unas lineas **mas abajo**» del filtro. Lo
   comprobé: `make_date` está en `08_plan_mensual.sql:319` y el filtro en `:328`
   — **nueve líneas por encima**. La afirmación de fondo es correcta; la
   indicación para encontrarla, no.
3. **Un recuento nuevo escrito a mano, y equivocado**, justo en la corrección que
   consistía en dejar de escribir recuentos a mano:
   `tests/test_f006_fichas.py:2447` dice «"tres tablas" donde son **cinco**», y la
   derivación devuelve **seis** —falta `stg.version_master_vigente`, que es TABLE
   en `stg/01_ddl.sql:181` y se puebla en `stg/07_version_master_vigente.sql:22`—.
   Lo verifiqué ejecutando la propia derivación del repositorio.
4. **Un disfraz que sigue abierto.** `PORCENTAJES_NO_SUMABLES` admite
   `clave_sustituta`, así que marcar `pct_acumulado` con esa etiqueta deja la
   batería en verde. Lo reconoce el propio comentario del bloque. Y hay tres
   correcciones —`entidad_cif`, la regla derivada y el ejemplo del `anio = 0`—
   que **no tienen guarda de regresión**: reescribirlas con otras palabras pasa
   sin un solo fallo.

**Lo que esto dice, y por qué lo pongo aquí y no en la lista de defectos**: en la
misma pasada en la que se cerraron seis defectos de matiz **se han generado tres
nuevos de la misma clase** —una copia en un docstring, una ubicación equivocada y
un recuento a mano—. No es descuido de nadie: es lo que pasa cuando se corrige
prosa técnica a mano, y es exactamente el dato que sostiene la recomendación de
abajo. El proceso está cerrando matices a la misma velocidad a la que los crea.

---

## El juicio de fondo que se me pide

Once pasadas mirando esto de cerca. Doy mi lectura sin suavizarla.

### ¿Destaparía la batería lo que sigo encontrando? **No, casi nada.**

Clasifiqué los defectos de las tres últimas pasadas por si una pregunta de negocio
real los expondría:

| Defecto | ¿Lo vería la batería? |
|---|---|
| La copia divergente de `identidad_sigrid` | **No.** Habla del origen; ninguna de las 18 preguntas consulta `raw` |
| El bug del derivador de campos propios | **No.** Se ve leyendo el YAML contra el SQL, no preguntando |
| `entidad_cif`: mecanismo falso en la mitad CLIENTE | **Casi seguro que no.** P2 pregunta por retenciones de proveedor; nadie filtra por `entidad_cif IS NULL` para eso |
| `razon_social` de la ficha hermana | **No** |
| `pct_acumulado` sumable | **No.** Vive en `stg.plan_mensual`, fuera del consumo recomendado, y ninguna pregunta va ahí |
| Recuentos en la prosa, ejemplo del `anio = 0` | **No** |
| `es_hoja` prometiendo lo que no cumple | **Quizá**, y solo a medias: P8 y P14 agregan por jerarquía, pero la batería es cualitativa —«usa estos objetos y cita estas advertencias»— y no trae cifras esperadas contra las que cuadrar |

La conclusión es incómoda pero es la que hay: **lo que la revisión estática está
encontrando ahora es de una clase que la batería no ve**. Son afirmaciones que
solo se detectan leyendo la ficha contra el SQL que la genera.

Y el reverso importa igual: **la batería destaparía cosas que once pasadas no han
tocado**, porque nadie las ha probado nunca. Si el agente encuentra la ficha del
objeto que necesita; si el `contexto_bbdd` que sirve el MCP incluye de verdad las
trece reglas; si el enrutado pregunta→objeto funciona; si las trampas están donde
el agente las lee y no solo donde nosotros las verificamos; y si las 13
respondibles se responden. Ese riesgo —el del criterio de éxito de la feature— hoy
**no está medido en absoluto**.

### ¿Alguna zona que considere no fiable? **Una, y la nombro.**

**Las afirmaciones sobre el sistema de origen que no se derivan de este
repositorio.** En concreto el punto 2 de `R-SIGRID-CON` —«diez tablas son
"Propiedades de `con`" en 1:1»— y cualquier cosa que dependa de
`azure-apps/sigrid_tablas.md`. Su única fuente es un PDF de 380 páginas cuya
segmentación el propio equipo ha declarado no fiable, y **ya produjo dos
afirmaciones falsas en dos pasadas seguidas** (`cen.res`, que no existe, y una
lista de siete excepciones con una sola acertada). El número «diez» está
verificado y es correcto, pero su respaldo no es reproducible: si mañana cambia,
nadie se entera.

Fuera de eso, **no señalo ninguna otra zona como no fiable, y lo digo con la misma
claridad**. Las 47 fichas de la superficie de consumo tienen columnas, granos,
claves compuestas, cardinalidades, agregaciones y nulos verificados uno a uno
contra el SQL, y ahora además con mecanismo derivado que impide la recaída.

### ¿Qué recomiendo? **Pasar a la batería, con una lista corta de deuda declarada.**

No es complacencia; es dónde está el riesgo ahora:

1. **La revisión estática ha dejado de converger a cero: converge a matices.** Las
   últimas tandas han encontrado menos y más pequeño cada vez, pero siguen
   encontrando. Con 793 columnas y 13 reglas, una pasada doce encontraría algo
   más, y una trece también. Eso no es señal de que el diccionario esté mal: es
   la asíntota de este método.
   Y hay un dato que lo cierra: **en esta misma pasada, cerrar seis defectos de
   matiz ha generado tres nuevos de la misma clase** (§«La deuda declarada»).
   Corregir prosa técnica a mano produce matices al mismo ritmo al que los quita;
   por debajo de cierto umbral, otra pasada no acerca al objetivo, solo cambia
   qué frase está mal.
2. **Ninguno de los defectos vivos produce un número falso silencioso en la
   superficie de consumo**, que es el daño que esta feature existe para evitar.
   Los que lo producían —`importe_origen` sumable, las claves reducidas, los
   `COUNT(DISTINCT)` marcados `suma`, el fan-out de las cardinalidades— están
   cerrados y con guardián.
3. **El riesgo no medido es el otro**, y es mayor: que esto no funcione con un
   agente de verdad. Es lo que dice R41 y es lo que decide si la feature sirve.
4. **La deuda tiene que quedar escrita y con dueño**, no «pendiente». Si se pasa a
   la batería, que sea con la lista corta anotada en `tasks.md` y revisable
   cuando esos bloques se toquen.

Dicho esto: **si algo bloqueara, lo diría**. En esta pasada no bloquea nada.

---

# DÉCIMA PASADA · 2026-08-21 — el vicio de fondo, cerrado

> Commits revisados: `ad88f9b`..`5bb6963`.

## Veredicto de la décima pasada

**RECHAZADO**, y **rectifico el APROBADO que ya había emitido**. Es la cuarta vez
en esta feature que me pasa lo mismo, y el patrón de mi error es siempre el
mismo, así que lo dejo escrito: **verifico el estado y doy por buena la defensa**.
Comprobé que hoy no queda ninguna copia —con mi propio barrido normalizado, y es
cierto— y de ahí di por bueno que el barrido *cubre* la superficie publicable. No
la cubre, y basta un experimento adverso para verlo.

Lo cerrado sigue cerrado y es mucho: los dos graves, el vicio de fondo de los
derivadores, `es_hoja`. Pero quedan **dos defectos en la superficie de consumo**,
uno en `stg`, un mecanismo que promete lo que no hace, dos recuentos declarados
que no cuadran y un ejemplo publicado que el SQL no soporta.

---

## Bloquean · están en la superficie de consumo

### 1 · `retenciones.entidad_cif`: el mecanismo publicado es falso, y va por cuadruplicado

La corrección acertó en la conclusión y falló en el porqué, que es lo que un
agente copia para escribir SQL. El texto nuevo dice:

> «La entidad **no tiene ficha de proveedor**: el `LEFT JOIN` con `raw.prv` no
> casa.»

Vale para la rama PROVEEDOR. **No vale para la mitad CLIENTE de la tabla**: en
`retenciones/01_movimientos.sql:107`, `entidad_cif` es el literal
`NULL::VARCHAR(24)`. Ahí no hay ningún `LEFT JOIN raw.prv` que pueda casar o no:
el NULL es una constante. Quien lea la ficha buscará una ficha de proveedor
ausente donde lo que hay es una columna que no existe para ese sentido.

Y el bloque de siete líneas está **duplicado literalmente en cuatro fichas**
—`movimientos`, `v_pbi_retencion_entidad`, `v_pbi_retenciones_vivas`,
`v_pbi_retenciones_vencidas`—: el arreglo de esta tanda ha creado, de un golpe,
cuatro copias que la próxima corrección tendrá que acertar a la vez.

### 2 · `maestro.proveedores_obra.razon_social`: el arreglo no llegó a la ficha hermana

En la misma tanda se corrigió `maestro.proveedores.razon_social` para decir que
una razón social sin informar llega como **cadena vacía** y nunca como NULL. Su
hermana, en el mismo fichero (`maestro.yaml:229-231`), sigue diciendo
`nulo_significa: La entidad no tiene ficha de proveedor, **o no tiene razon
social**`. El SQL es el mismo patrón —`maestro/03_proveedores_obra.sql:45`,
`pv.raz` en crudo con `LEFT JOIN raw.prv`—, así que la segunda mitad es falsa por
el mismo motivo que se acaba de corregir arriba.

---

## No bloquea la batería, pero hay que corregirlo · `stg`

### 3 · `pct_acumulado`, la cuarta hermana

Ya lo tenía localizado por mi cuenta y la auditoría llega a la misma columna:
`stg.plan_mensual.pct_acumulado` sigue en `suma_solo_dentro_del_mes` siendo un
porcentaje **acumulado** —lo dice su propio `significado`—, con `pct_mes` al lado
como la desacumulada y con `R-IMPORTE-MES` (bloqueante) incluyéndola en su
ámbito. Las otras cuatro columnas del mismo grupo sí pasaron a `ultimo_valor`.

Lo que lo explica está en el test: `tests/test_f006_stg_trampas.py:292` enumera
**a mano** `["can_origen", "importe_origen", "importe_origen_raw",
"total_incurrido"]`. El guardián se escribió a la medida del arreglo, así que no
podía ver la quinta. Es la octava instancia del patrón, y esta vez vive en el
test, no en la ficha.

---

## El mecanismo · el barrido de copias no cubre lo que dice cubrir

Se declaró que el barrido pasa a cubrir «toda la superficie publicable, no solo
las fichas». **No la cubre, y lo comprobé yo**: en un worktree aislado planté en
`stg.obras.motivo_no_consumo` —campo publicable— dos afirmaciones que las pasadas
séptima y octava rechazaron, plegadas como las pliega el propio YAML:

```yaml
      Se rehace cada noche con una ingesta incremental por
      `tiemod`, asi que no se refresca
      nunca.
```

Resultado: **`14 passed`**. Y lo que `yaml.safe_load` publica de ahí es
exactamente «ingesta incremental por `tiemod`, asi que no se refresca nunca»: las
dos frases rechazadas, servidas al MCP, con la batería en verde.

La causa está a la vista en el fichero: el barrido parametrizado sobre los diez
YAML mira **texto crudo**, y una frase partida por el salto de línea que `>-`
introduce es invisible para él; el que sí normaliza el plegado **solo lee
`00_global.yaml`**. La protección que funciona es justo la que no se extendió a
los otros nueve ficheros. Y `BLOQUES_PUBLICABLES` es una **constante muerta**: no
la usa ninguna función.

El arreglo es de una línea: que el barrido normalizado recorra
`str(yaml.safe_load(...))` de los **diez** ficheros. Y conviene, porque los
defectos 1 y 2 de arriba son justamente lo que ese barrido debería haber cazado.

---

---

## Dos recuentos declarados que no cuadran

No cambian el veredicto, pero sí lo que uno cree que está protegido.

**Las correcciones del guardián son nueve, no diez.** El desglose real es **4 + 5**:
las cuatro que ningún sufijo cazaba (`maestro.proveedores.razon_social`,
`stg.ambitos.codigo`, `.descripcion`, `.clase_sigrid`) y **cinco** del punto ciego
del `INSERT … SELECT` (`stg.obras.codigo_obra`, `.nombre_obra`,
`stg.partidas.descripcion_corta`, `stg.fases.anio`, `.mes`). El propio mensaje de
commit que anuncia «seis» **enumera cinco**. `entidad_cif` no cuenta como décima:
el guardián **no la marca** —llega por `LEFT JOIN`, donde el NULL sí es posible— y
su arreglo fue de significado, no de posibilidad.

**Y las tablas que dejaron de saltarse son cinco, no tres.** Lo medí: el guardián
evalúa ahora **seis** objetos de `stg` —`ambitos`, `fases`, `obras`, `partidas`,
`plan_mensual` y `presupuesto`—, y el docstring que documenta el arreglo
(`tests/test_f006_fichas.py:571`) nombra solo `partidas`, `fases` y
`plan_mensual`. Quedan sin mencionar **`stg.obras`** —que aportó **dos** de los
cinco hallazgos— y **`stg.presupuesto`**. El control se escribió sobre la lista
corta, así que fija menos de lo que el arreglo consiguió.

## Por qué `pct_acumulado` era invisible: la derivación tiene un punto ciego estructural

La comprobación nueva de coherencia dentro del ámbito de cada regla
(`tests/test_f006_stg_trampas.py:266`) **funciona y no es un falso control**: su
control comparte el accesor del ámbito, pero fija literales, así que al encoger
el ámbito la comprobación pasa en vacío y **el control falla**. Correcto.

Lo que no puede ver es otra cosa: compara **la misma columna declarada en varios
objetos** del ámbito. Una columna que existe en **uno solo** —y `pct_acumulado`
existe solo en `stg.plan_mensual`— no tiene con qué compararse y es invisible por
construcción. Comprobado: marcarla `clave_sustituta` deja la batería entera en
verde. Por eso el defecto no se detectó ni por la lista escrita a mano ni por la
derivación: hacían falta las dos y ninguna la alcanza.

## Un ejemplo publicado que el SQL no soporta

`stg.yaml:594-598` explica —con razón— que el filtro `f.anio IS NOT NULL` de
`08_plan_mensual.sql:328` no descarta nada, y lo ilustra diciendo que «una fase
con `anio = 0` **entra igual**». No entra: dos líneas antes, la misma `SELECT`
hace `make_date(f.anio, f.mes, 1)` (`:319`), y `make_date` **rechaza el año 0**
—«year 0 is out of range»—. Una fase así no entraría: **abortaría el build**. El
punto de fondo se sostiene; el ejemplo concreto, no.

## Rectificación de un test mío

La tarea C del encargo era juzgar si el implementer tenía razón al corregir un
test que escribí yo en la séptima pasada. **La tiene, y yo estaba al revés.**
Aquel test afirmaba que `stg.fases.anio`/`.mes` podían ser NULL y que
`stg.plan_mensual` descartaba esas fases. Es falso: `stg/05_fases.sql:26-27`
proyecta `f.ano` y `f.mes` **en crudo** desde `raw.obrfas`, sin `NULLIF` —y en la
línea de al lado sí lo ponen donde lo querían: `NULLIF(TRIM(f.res), '')`—, así
que con la convención de Sigrid el «sin informar» llega como 0 y el filtro es
inerte. La premisa nueva es la correcta.

## `es_hoja`: cerrado, con dos matices menores

La corrección es cierta y está en las dos vistas, y el fenómeno que denuncia es
estructural: `capitulo_padre_id` existe en `stg.partidas` y el árbol llega a seis
niveles. Dos imprecisiones que no bloquean: la receta que propone —«bajar al
último nivel de la jerarquía»— sugiere un `MAX(nivel)` cuando la profundidad es
variable y el criterio exacto es «ninguna fila la apunta con `capitulo_padre_id`»,
columna que **ninguna de las dos vistas proyecta**; y el ejemplo llama «nivel 2» a
`CI.2`, que con `CI` como raíz es nivel 1.

---

## GRAVE 2 · el derivador, verificado con uno que no comparte linaje

Es lo que se me pidió atacar, porque en la novena pasada mi verificación y la
suya coincidieron **en el mismo error**. Así que esta vez escribí un derivador
**desde cero**, con otro diseño: trocea cada fichero en **sentencias**
—respetando los bloques `$$` de las funciones—, resuelve el mapa alias→tabla
**dentro de cada sentencia** y solo entonces busca `alias.campo`. No reutiliza
ni una línea del repositorio ni de mi script anterior.

Resultado: **13 tablas**, y contrastado contra lo que la regla publica hoy,
**coincidencia exacta, campo a campo**:

`auxmun`(res) · `auxobramb`(cod,res) · `auxobrcla`(res) · `auxobrtip`(res) ·
`auxpro`(res) · `conext`(cod) · **`ctrpro`(res)** · **`dcapro`(res)** ·
`dcfpro`(res) · `obrfas`(res) · `obrfasamb`(fec,res) · `obrparpar`(cod,res) ·
`prv`(cif,raz)

Las dos que faltaban están dentro. El diagnóstico era el correcto: el alias es
local a la sentencia, y `l` era `ctrpro`, `dcapro` y `dcfpro` en el mismo fichero.

**Y el vicio de fondo está cerrado, que es lo que importaba más.** Los controles
nuevos no comparten linaje con lo que controlan:

| Control | Qué hace |
|---|---|
| `..._el_derivador_no_pierde_un_alias_repetido` | SQL **fabricado** con el caso exacto del bug y **la respuesta escrita a mano**: `{"ctrpro": {"res"}, "dcapro": {"res"}}`. Un derivador por fichero lo suspende |
| `..._el_troceo_en_sentencias_separa_los_ambitos` | Fija que `SELECT … raw.a x; SELECT … raw.b x;` da `{x: a}` y `{x: b}`, no uno solo |
| `..._las_tres_lineas_de_compras_existen_de_verdad` | Contraste del **fichero real por otra vía**: lee líneas con su propia regex y **no usa `alias_de_raw` ni `sentencias`**. Si el derivador vuelve a perder una tabla, este no se entera de la misma manera |

Eso es exactamente lo que hacía falta: el control ya no puede confirmar el error
del derivador con el mismo error. Se acaba una clase entera de falsos verdes.

## GRAVE 1 · la copia borrada, y ninguna más en lo publicable

`convenciones.identidad_sigrid` ya no repite la regla: **remite** a ella y dice
por qué, dejando la lección escrita para el siguiente que pase:

> «**Lo que hay que saber antes de consultar `raw` esta en la regla
> `R-SIGRID-CON`, que es la unica version** […]. Esta entrada no lo repite a
> proposito. Cuando lo repetia, se quedo atras […]. Eran dos versiones publicadas
> que se contradecian.»

Barrí **toda la superficie publicable** de los diez YAML —lo que sobrevive a
`yaml.safe_load`, con el texto normalizado sin tildes y sin plegado de línea—
buscando las ocho afirmaciones que revisiones anteriores rechazaron: «viven en
`con`», «no en la extension», «no en la tabla especifica», `cen.res`, «Reparto
nombre», `--full-refresh`, «incremental por `tiemod`» y «no se refresca nunca».
**Cero coincidencias: el estado de hoy es limpio.**

Lo que **no** puedo dar por bueno es la defensa: el barrido del repositorio no
cubre esa superficie, y lo demuestro en §«El mecanismo». Estado limpio y defensa
incompleta son dos cosas distintas, y confundirlas es lo que me llevó a aprobar
antes de tiempo.

## El guardián sin sufijos, medido

Dejó de perseguir nombres y comprueba la afirmación real —«columna proyectada en
crudo desde `raw` que declara `nulo_significa`»—. Lo medí antes y después:

| | Novena pasada | Ahora |
|---|---|---|
| Fichas evaluadas | 15 | **20** |
| Fichas de `stg` dentro | 1 (`ambitos`) | **6** (`ambitos`, `fases`, `obras`, `partidas`, `plan_mensual`, `presupuesto`) |
| Columnas recorridas | 30 | **95** |
| Saltos «no lee de `raw`» | 45 | **40** |

El punto ciego está cerrado: las tablas de `stg` se pueblan con `INSERT … SELECT`
en un fichero distinto del que las declara, y el guardián las saltaba con un
motivo que era **falso** —decía que no leen de `raw` cuando sí lo hacen—. Ahora
concatena los ficheros que **declaran o pueblan** el objeto.

Cero columnas llegan hoy al `assert`, pero esta vez eso significa lo correcto:
las que llegaban se corrigieron, y el detector tiene desde la octava pasada un
control que distingue «cero por sano» de «cero por roto».

## Rigor e higiene

- **1828 tests**, 122 saltados, cobertura **99,0 %**, ejecutado por mí.
- **Mutación recalculada con el `__pycache__` borrado**: 2358 líneas, **166
  mutantes**, 0 supervivientes, 0 timeouts.
- **Nada prohibido**: el diff toca cinco YAML, cuatro ficheros de tests y
  `progress/`. Ni un `GRANT`, `REVOKE`, firewall, Azure ni conexión a la base.
  **`harness/` intacto** y **sin `push`**.
- Mi novena pasada quedó preservada en un commit propio, sin alterar su contenido.

## La superficie de consumo: uno cerrado, dos abiertos

**`es_hoja` sí está cerrado**, y bien, en **las dos** vistas
(`mart.v_pbi_dim_partida` y `v_pbi_dim_partida_niveles`): retirada la promesa y
sustituida por la verdad, con el ejemplo concreto —«un **capitulo** intermedio de
nivel 2 con descendientes —`CI.2`, con `CI.2.1` debajo— sale marcado como hoja
igual que ellas. Por eso **no evita el doble conteo**»—.

**`entidad_cif` no**: la conclusión es correcta y el mecanismo publicado es falso
para la mitad CLIENTE de la tabla (defecto 1). Y aparece un tercero que esta
tanda dejó atrás, `maestro.proveedores_obra.razon_social` (defecto 2).

Corrijo aquí lo que escribí antes de tener la auditoría: **la superficie de
consumo no está limpia**. Lo que sí sigue siendo cierto es que sus 47 fichas y
644 columnas no tienen ningún defecto de los grandes —columnas inventadas,
granos falsos, claves que no identifican, acumulados marcados sumables—: los dos
que quedan son afirmaciones sobre *por qué* una columna es nula.

## Alcance y qué falta para la batería

El diccionario está **estructuralmente completo**: bloques A a G, **102 fichas
para 102 objetos publicados, 793 columnas, 13 reglas duras y `pendientes` en 0**,
más el contrato de `_meta` con `mcp-bbdd` y el paso que lo publica. Lo que falta
para aprobarlo son los cuatro puntos de arriba, ninguno estructural.

Para poder pasar la batería de aceptación hace falta, por este orden:

1. **Los cuatro defectos de esta pasada**, empezando por los dos de consumo.
2. **T19**: `python main.py publicar-diccionario` contra la base real y las tres
   consultas de comprobación del contrato. Es la primera vez que algo de esto se
   ejecutará contra un PostgreSQL: la adaptación de tipos de psycopg, el `JSONB`,
   los `TEXT[]` y el `CHECK (id = 1)` están sin probar, y está declarado.
3. **T26/T27**: `check-diccionario` contra el catálogo real, **con la consulta de
   unicidad de clave**. Es lo único que convierte «102 objetos» en una verdad
   comprobada y no en lo que ve una expresión regular, y lo único que puede
   cerrar las claves compuestas que el análisis estático no decide.
4. **T39**: las 18 preguntas contra el diccionario publicado —13 respondibles, 3
   parciales y 2 que deben contestarse con un «no puedo, y este es el motivo»—.
   Ese es el criterio de éxito de F-006.
5. Los bloques 🔏 de permisos y firewall, que necesitan firma del humano y no
   condicionan la batería.

**Deuda declarada que viaja** y que conviene no perder: el falso positivo del
detector de multifuente (`COALESCE` de dos ramas del mismo objeto); los menores 5
a 7 de la sexta pasada; **F-041**, para que «cero supervivientes» signifique lo
que dice; los comentarios del SQL que mienten —ya mordieron una vez con
`dec_cantidades`—; y la lista del punto 4 de `R-SIGRID-CON`, que es conservadora
y cuyo enunciado se lee cerrado.

---

# NOVENA PASADA · 2026-08-21 — el criterio, y la copia que sobrevivió

> Commits revisados: `0f9bb54`..`7ffd1e0`.

## Veredicto de la novena pasada

**RECHAZADO.** Y **rectifico un APROBADO que ya había emitido**: lo di apoyándome
en mis propias comprobaciones, con una auditoría de barrido todavía corriendo.
Al llegar encontró dos cosas que yo no vi, y una de ellas **demuestra que mi
verificación estaba mal hecha**. Las he confirmado las dos contra el código.

El criterio —lo que no se pueda derivar de la fuente que gobierna el hecho, no se
afirma— **sí está aplicado en el texto de la regla**, y eso es real y valioso.
Lo que falla es que **el derivador tiene un bug** y que **la afirmación
rechazada sigue publicada doce líneas más abajo, en el mismo fichero**.

### Lo que me corrige a mí

Escribí que había reproducido la lista del punto 3 «con mi propio derivador» y
que daba «exactamente las mismas once tablas». Es cierto que coincidía, pero
**coincidía porque mi script tenía el mismo bug que el suyo**: los dos
construimos el mapa alias→tabla **por fichero**, con un `dict` que machaca la
clave. En `compras/01_documentos.sql` las tres tablas de línea comparten el alias
`l` —`FROM raw.ctrpro l` (:61), `FROM raw.dcapro l` (:126), `FROM raw.dcfpro l`
(:179)— y las tres proyectan `l.res AS descripcion` (:52, :103, :167). El `dict`
se queda con la última, así que el `res` de las tres se atribuye solo a
`dcfpro`. Dos derivaciones con el mismo error no son una verificación
independiente: son el mismo error dos veces. Lo doy por lección propia.

---

## Los defectos

### 1 · El sexto superviviente, y esta vez publicado (GRAVE)

`config/diccionario/00_global.yaml:399-403`, en `convenciones.identidad_sigrid`:

> «En Sigrid `ide` es la clave universal y muchas tablas son "propiedades de
> `con` 1:1" […]. El codigo (`cod`), el nombre (`res`) y la fecha (`fec`) viven
> en `con`, **no en la extension**. `con.nom` NO existe.»

Es **la afirmación que la séptima pasada rechazó**, viva y en contenido
**publicable** —no en un comentario, como el quinto caso—, y **contradice al
punto 3 de `R-SIGRID-CON` doce líneas más abajo en el mismo fichero**, que
enumera once tablas cuyos `cod`/`res`/`fec`/`cif`/`raz` propios lee el ETL sin
pasar por `con`. El MCP publica las dos. Y las dos listas de «propiedades de
`con`» divergen: **ocho** tablas aquí, **diez** en el punto 2.

**Por qué no lo cazó el detector nuevo**: `tests/test_f006_copias.py` es una
lista negra de **subcadenas literales**. Busca `"no en la tabla especifica"`; aquí
pone `"no en la extension"`. Es además sensible a tildes y mayúsculas y —lo
decisivo— **ciega al plegado de línea**: en un bloque `>-` cualquier frase de la
lista partida por un salto es invisible. Lo que sí compara afirmaciones es
`test_f006_fuente_que_gobierna.py`, pero su alcance son las 31 fichas de `raw`, y
`00_global.yaml` queda fuera.

### 2 · La lista «derivada» está incompleta por un bug del generador (GRAVE)

Por la colisión de alias descrita arriba, el punto 3 publica `dcfpro` (`.res`) y
**omite `ctrpro` y `dcapro`**, que cumplen el mismo criterio en el mismo fichero.

Lo agravante no es la omisión, son tres líneas: es que
`test_f006_r9_la_regla_declara_exactamente_los_campos_derivados` compara la regla
**contra la misma derivación defectuosa**. Está verde por construcción y no puede
detectar el fallo. Y el `motivo` de la regla vende esa lista como garantía: «la
genera un test […] y la regla queda en rojo si dejan de coincidir». Mis pruebas
P1 y P2 de esta misma pasada —quitar `obrparpar`, añadir una tabla inventada— sí
saltaron, y por eso di el mecanismo por bueno: fijan la **coherencia** entre
regla y derivador, no la **corrección** del derivador.

Arreglo: resolver el alias por ámbito de consulta y no por fichero, y añadir al
control un caso con alias repetido, que es justo lo que el repositorio ya tiene.

### 3 · `stg.plan_mensual` contradice a una regla bloqueante que la incluye (MEDIA)

Cuatro columnas acumuladas pasaron a `suma_solo_dentro_del_mes`:
`importe_origen`, `importe_origen_raw`, `can_origen` y `pct_acumulado`
(`stg.yaml:126,149,159,168`). Pero `R-IMPORTE-MES` es **bloqueante**, su `ambito`
**incluye `stg.plan_mensual`** (`00_global.yaml`) y dice que el acumulado ya
lleva dentro los meses anteriores. Las **doce** columnas equivalentes de `mart`
—`fact_seguimiento_mensual`, `fact_seguimiento_categoria`, `v_pbi_fact`,
`v_pbi_fact_categoria`, `v_fact_periodificado`— siguen todas en `ultimo_valor`,
que es lo correcto. La misma magnitud, en el linaje directo, con dos etiquetas
opuestas, y la de aguas arriba contradiciendo la regla que se le adjunta.

`pct_acumulado` es peor: es un **porcentaje** (`unidad: "%"`), y sumar
porcentajes de avance de partidas distintas no significa nada.

*(Aviso: aquí yo mismo leí mal primero con `sed` y creí que `mart` había
cambiado. No: `mart` está intacto, lo verifiqué parseando los diez YAML.)*

### 4 · La receta de `sigrid_tablas.md` es falsa en 25 de 31 fichas (MEDIA)

La coletilla nueva dice que `grep -n "^| <tabla> "` devuelve «tambien las filas
de otras tablas con un campo llamado así». Ejecutado contra el documento: **25 de
31 devuelven exactamente una línea**, así que describe filas que no existen. En
las seis restantes la regla de desambiguación —«la de entidad es la que lleva la
descripcion en la segunda columna»— **no desambigua** (las filas de campo también
la llevan) y **en `con` está invertida**: su fila de entidad es
`| con Conceptos | | ETC | |`, con la segunda columna **vacía**. Seguir la receta
en la ficha de `con` lleva al sitio equivocado.

### 5 · El `motivo` promete una procedencia que el punto 2 incumple (MEDIA)

«Todo lo que afirma esta regla se **deriva de este repositorio**». El punto 2
—«**Diez** tablas son "Propiedades de `con`" en 1:1»— no es derivable: ningún SQL
une `prv`, `cen`, `com`, `dca`, `dcf`, `cob`, `pag` ni `rec` a `con` por `ide`
(solo `obr`, en `maestro/01_obras.sql:30`). Su única fuente es el PDF que el
mismo `motivo` declara no apto. El número es correcto —diez de las 31—, pero el
cambio de «Muchas» a «**Diez**» endurece a exhaustiva una afirmación no
verificable, justo cuando el `motivo` presume de lo contrario.

### Menores

6. El desglose de exclusiones de `dca` y `dcf` **no suma**: «6 de direcciones, 2
   de descripciones largas, 2 de observaciones, 11 sueltas» = 21, y son 23
   (`raw.yaml:1054-1056`, `:1140-1142`). El test comprueba el total y los nombres
   citados, no que el desglose cuadre.
7. `stg.yaml:443`: `capitulo_raiz_cod` quedó con `nulo_significa: null` en vez de
   documentar que nunca es NULL, como sus tres hermanas. Y la razón que da
   `codigo_partida` (`:414-417`) es inventada: lo que protege a las descendientes
   es su propio filtro (`04_partidas.sql:77-78`), no el del padre.

---

## Lo que sí está bien, y es mucho

- **El criterio está aplicado en el texto**: el mapa fuente→hecho de la cabecera
  de `raw.yaml`, el recorte de lo insostenible (`cen.res`, `obr.res`, las cuatro
  excepciones falsas) y el hueco declarado con su fuente son exactamente lo
  pedido. **Al rechazar los `entcif` que yo sugería tiene razón y me corrige**:
  los propuse desde el mismo PDF que ya había producido dos afirmaciones falsas.
- **El ancla de la carga es correcta y completa**: cita el `CMD ["run-all",
  "--full"]` real y cubre los dos caminos sin negar ninguno. Las 31 citas de
  `--full-refresh` fuera, contrastadas contra los `click.option`.
- **La reversión del retoque de `06_presupuesto.sql` está limpia**: en toda la
  feature el único SQL tocado es el DDL nuevo del contrato. Revertir en vez de
  debilitar el guardián de F-011 es la decisión correcta, y `dec_cantidades`
  quedó cerrado por otra vía y mejor: dice que no interviene y **avisa de que los
  comentarios del SQL repiten una fórmula que el código no ejecuta**.
- **`_source_tiemod`** cerrado y bien anclado; **`stg.presupuesto`** corregido con
  la prosa exacta («sumable dentro de UNA fase, nunca a través de `fase_num`») y
  el reconocimiento de que se pasó con `ultimo_valor`; el «cinco cosas» ya dice
  seis; y el **control que le faltaba al guardián de nulos** existe, mide el
  detector sobre un caso fabricado y admite que está en cero.
- **El punto 4 de la regla es cierto**, verificado tabla a tabla: `auxobramb`,
  `obrfas`, `obrfasamb` y `obrparpre` no se unen a `raw.con` en ningún SQL.
- **Mutación** recalculada con el bytecode borrado: 2358 líneas, 166 mutantes, 0
  supervivientes, 0 timeouts. `pendientes` en 0, 102 fichas ↔ 102 objetos. Nada
  prohibido, sin `push`, `harness/` intacto.

---

---

## Y SÍ hay defectos en la superficie de consumo

Esto responde directamente a la pregunta de alcance, y la respuesta cambia la
decisión: **recortar `raw` no basta**. Una revisión fresca de los seis esquemas
recomendados —60 fichas, 707 columnas, 50 claves (25 compuestas), 84 relaciones y
214 `nulo_significa`, contrastadas una a una— los encuentra **sustancialmente
sanos** pero con **dos defectos de gravedad media**, los dos verificados por mí:

### C1 · `mart.v_pbi_dim_partida.es_hoja` promete lo que no cumple (MEDIA)

La ficha (`mart.yaml:567-569`) dice: «Marca las partidas de detalle frente a los
capitulos, **para no sumar dos veces al agregar por la jerarquia**». El SQL
(`mart/05_views_powerbi.sql:58-60`) es una heurística:

```sql
CASE WHEN nivel >= 2 OR codigo_partida LIKE '%.%' THEN TRUE ELSE FALSE END AS es_hoja
```

Un **capítulo intermedio** de nivel ≥ 2 sale `es_hoja = TRUE`. Que los árboles
llegan más hondo lo prueba la vista hermana, que tiene `nivel_1..nivel_6`. Filtrar
`es_hoja = TRUE` y sumar puede contar el capítulo **y** sus hijos: doble conteo de
importes, en `mart`, que es la superficie principal. El comentario del propio SQL
es más prudente que la ficha («útil para filtrar si se quiere solo partidas
hoja»), y existe `stg.partidas.capitulo_padre_id`, con el que la prueba de hoja
sí sería exacta. Arreglo: declararlo heurística y retirar la promesa.

### C2 · `entidad_cif` sin sanear, y cuatro fichas documentan un NULL que no llega (MEDIA)

`retenciones/01_movimientos.sql:59` proyecta `prv.cif AS entidad_cif` **en crudo**.
El mismo origen, en los dos maestros, sí se sanea: `maestro/02_proveedores.sql:28`
hace `NULLIF(TRIM(p.cif), '') AS cif`. Que el propio repositorio lo envuelva ahí
es la prueba de que los blancos ocurren.

Cuatro fichas declaran `nulo_significa: La entidad no tiene CIF en el maestro`
—`movimientos`, `v_pbi_retencion_entidad`, `v_pbi_retenciones_vivas` y
`v_pbi_retenciones_vencidas`—, así que `WHERE entidad_cif IS NULL` pierde en
silencio a los proveedores con CIF en blanco. Y `maestro.proveedores.cif` sí lo
dice bien («no tiene CIF, **o esta en blanco**»), lo que deja la incoherencia a la
vista dentro del mismo diccionario.

**Lo importante es por qué se escapó**: es el tercer caso de la misma familia que
ya corregimos dos veces —`cierre.v_pbi_cierre_cabecera.cliente_ide` en la tercera
pasada, `maestro.obras.cliente_id` en la séptima—. El guardián se amplió entonces
de `_ide` a `_id`; ahora se escapa por `_cif`. **Persigue sufijos en vez de
derivar**: lo derivable es «columna proyectada en crudo desde una tabla de `raw`
que declara `nulo_significa`», sin mirar cómo se llama.

### Menores en consumo (omisión, no falsedad)

`nulo_significa` más estrechos que la realidad en `cierre` (`fase_numero`,
`fase_nombre_mes`, `fase_fecha_inicio` y las derivadas de periodificación, que
también son NULL cuando la venta final es 0 o falta el importe de fase 0); nueve
columnas de fecha en `compras` sin `nulo_significa` pese a que
`compras.fn_sigrid_date(0)` devuelve NULL —un `WHERE anio = 2025` descarta en
silencio los documentos sin fecha—; `nivel_1`/`nivel_2` sin el `nulo_significa`
que sí llevan `nivel_3..6`; y el grano de `v_master_vigente_anual`, que dice «31
de diciembre si el año ya pasó, hoy si es el año en curso» cuando el `CASE` usa
`hoy` también para años futuros.

Queda además un **riesgo no verificable sin base**: la clave de
`v_master_versiones_tipadas` es una terna sobre un `SELECT DISTINCT` de ocho
columnas; se sostiene solo si las otras cinco dependen de ella. Es material para
la consulta de unicidad de T26.

### Lo que en consumo está limpio, y conviene decirlo

Las 707 columnas existen y pertenecen **a su** objeto —comprobado también en los
ficheros que crean varios—; ni un grano falso; las 25 claves compuestas
identifican una fila, incluidas las tres históricamente frágiles
(`v_pbi_proveedor_obra` con sus seis columnas, `v_pbi_partida_coste` con cinco,
`v_pbi_retencion_obra` con tres); ni un `COUNT(DISTINCT)` marcado `suma`; todos
los acumulados en `ultimo_valor`; y **las seis trampas de negocio están en campos
publicables y son ciertas**. Los dos casos peligrosos de `*_ide` sin `NULLIF`
—`maestro.obras.cliente_id` y `cierre.v_pbi_cierre_cabecera.cliente_ide`— están
correctamente documentados como no nulables, que era justo lo que se corrigió.

### Dos incoherencias más en el bloque global

`esquemas.compras.pasos_etl: []` y `esquemas.retenciones.pasos_etl: []`
contradicen el `paso_etl: build_compras` / `build_retenciones` que llevan todas
sus fichas; y `esquemas._meta.pasos_etl` omite `publicar_diccionario`, que es
precisamente el paso que escribe las tablas del diccionario y el que declaran sus
cuatro fichas.

---

## Dónde caen los defectos, para la decisión de alcance

Se pidió separar lo que está en `raw` de lo que toca a los esquemas de consumo:

- **Ninguno de los siete está en `mart`, `cierre`, `compras`, `retenciones`,
  `maestro` ni `_meta`**. Esta tanda no toca esos seis ficheros, y las doce
  columnas de `mart` que podían haberse contagiado siguen correctas.
- **Pero dos no son «solo `raw`»**: el defecto 1 y el 5 están en
  `00_global.yaml`, que el MCP publica **entero** y sirve a cualquier consulta,
  sea del esquema que sea; y el 3 pone a una ficha a contradecir una regla
  `bloqueante` cuyo ámbito abarca cinco objetos de `mart` y cuatro de `cierre`.
  El bloque global no es zona acotable.

Así que la respuesta a la pregunta de fondo es: **recortar `raw` no cierra esto**.
Los defectos 1, 2 y 5 viven en la regla y en las convenciones globales, y el 3 en
`stg`. Lo que sí sigue siendo cierto es que **el contenido de las 47 fichas de
consumo, con sus 644 columnas, no está en cuestión**: si se quiere avanzar hacia
la batería, el camino es cerrar estos siete —los dos graves son un borrado y un
`dict` mal construido— y no seguir puliendo fichas de `raw`.

---

---

## El criterio: aplicado de verdad, no de nombre

La instrucción era: **lo que no se pueda derivar de la fuente que gobierna el
hecho, no se afirma; se omite, y si el hueco importa se declara como hueco.**
Lo ha aplicado, y se puede comprobar sin creerle:

1. **Hay un mapa explícito fuente→hecho** en la cabecera de `raw.yaml`: qué corre
   de noche → el `Dockerfile`; cómo carga según la bandera →
   `ingest_raw_step.py`; cómo se llama la bandera → los `click.option` de
   `main.py`; qué campos propios existen → nuestro SQL. Cada afirmación tiene
   una fuente asignada, y son las que gobiernan cada hecho.
2. **La lista del punto 3 la reproduje por mi cuenta.** Escribí mi propio
   derivador —para cada alias de una tabla de `raw`, usos de `.cod`, `.res`,
   `.fec`, `.raz`, `.cif`— y da **exactamente las mismas once tablas con los
   mismos campos**: `auxmun`(res), `auxobramb`(cod,res), `auxobrcla`(res),
   `auxobrtip`(res), `auxpro`(res), `conext`(cod), `dcfpro`(res), `obrfas`(res),
   `obrfasamb`(fec,res), `obrparpar`(cod,res) y `prv`(cif,raz). Incluye
   `obrparpar.cod`/`.res`, que era el hueco que más pesaba.
   De paso me corrijo: en la octava pasada di `dcfpro.res` por dudoso; **existe
   y se lee** (`compras/01_documentos.sql:167`, `l.res AS descripcion` sobre
   `FROM raw.dcfpro l`).
3. **El mecanismo cierra los dos sentidos**, que es lo que faltaba en las pasadas
   7 y 8. Lo probé en un worktree:

   | Prueba | Resultado |
   |---|---|
   | Quitar `obrparpar` de la lista de la regla | **detectado** — la regla no puede quedarse corta |
   | Añadir una tabla inventada (`comlin`) | **detectado** — la regla no puede inventar |

   El test compara lo declarado con lo derivado exigiendo **igualdad**, y muestra
   la diferencia en los dos sentidos. Con esto, el defecto que causó los dos
   rechazos anteriores no puede repetirse en silencio.
4. **Recortó lo que no podía sostener y declaró el hueco.** Fuera `cen.res`
   (inventado), `obr.res` (solo lo respaldaba el PDF) y las cuatro excepciones
   falsas. Y el `motivo` dice qué deja de decir y a dónde ir:

   > «**Lo que esta regla NO dice, y es deliberado**: que campos existen en
   > Sigrid y el datamart no lee. Esa pregunta solo la responde
   > `azure-apps/sigrid_tablas.md` […]. Para preguntar por una columna concreta,
   > ese documento; para fiarse de una afirmacion, este repositorio.»

   Eso es exactamente lo pedido: omitir y declarar el hueco con su fuente.
5. **Al rechazar los `entcif` que yo sugería, tiene razón y me corrige.** Los
   propuse desde el mismo PDF cuyo segmentador ya había producido dos
   afirmaciones falsas; son misma fuente y mismo riesgo. Rechazarlos es aplicar
   el criterio también contra la sugerencia del reviewer, que es la parte difícil
   de aplicarlo.

## Lo demás que declaraba, verificado

| Punto | Veredicto |
|---|---|
| **El ancla de la carga** | **Correcta y completa.** La cabecera cita el `CMD ["run-all","--full"]` real, y las fichas cubren **los dos caminos** sin negar ninguno: de noche recarga entera, sin `--full` append por `MAX(ide)`. Es la corrección del defecto 6 de la octava pasada, hecha contra la fuente que gobierna qué se ejecuta |
| **Las 31 citas de `--full-refresh`** | Fuera; ahora se contrasta contra los `click.option` reales, y hay test que reconoce una bandera inventada |
| **La reversión del retoque de `06_presupuesto.sql`** | **Limpia**: `git diff a7cccdd..HEAD -- etl_sigrid/` está vacío. Y en **toda la feature** el único SQL tocado es `sql/ddl/01_diccionario.sql`, el DDL nuevo del contrato: **ni un SQL de negocio modificado**, que es la regla de hierro 3 de esta feature. Revertir en vez de debilitar el guardián de F-011 es la decisión correcta |
| **`dec_cantidades`** | **Cerrado por otra vía y mejor**: la ficha dice ahora que **no interviene**, da la fórmula real y **avisa de que los comentarios del SQL repiten una fórmula que no es**. Convierte la deuda en aviso en vez de tocar el SQL |
| **`stg.presupuesto`** | Corregido: `cantidad` e `importe` quedan en `suma_solo_dentro_del_mes`, que es lo exacto —sumar entre partidas de la misma fase es correcto; entre fases, no—. Reconocer que se pasó con `ultimo_valor` es la lectura buena: lo no sumable era la dimensión |
| **Mutación** | Recalculada con el `__pycache__` borrado: **2358 líneas, 166 mutantes**, idéntico a lo declarado, 0 supervivientes y 0 timeouts. `harness/mutacion.py` intacto |
| **Higiene** | Nada prohibido: ni `GRANT`, `REVOKE`, firewall, Azure ni conexión a la base. **Sin `push`**. Árbol limpio y sin worktrees huérfanos |

---

# OCTAVA PASADA · 2026-08-21 — la regla de oro y la carga de `raw`

> Commits revisados: `f1d449f`..`a7cccdd`.

## Veredicto de la octava pasada

**RECHAZADO.** Las dos correcciones centrales de la tanda —la regla de oro y la
carga de `raw`— **sustituyeron una afirmación falsa por otra**, y en los dos
casos la nueva es falsa en dirección contraria. No es un matiz: la regla es
`bloqueante` y se adjunta a las 31 fichas del origen, y la carga es lo que le
dice al agente cuán viejo es el dato que está leyendo.

Lo demás de la tanda está bien, y una parte muy bien: el fallo de
`_proyeccion_de` **no tuvo efecto retroactivo** —medido por dos vías
independientes—, las seis fichas de `compras` revalidadas no tienen ni una
columna ajena, la biyección 102↔102 es exacta y la mutación cuadra con el
bytecode limpio.

**Rectifico además una frase de mi propio borrador**: escribí que el guardián de
nulos «pasa de cubrir 1 ficha a 15». Eso describe el bucle, no la comprobación:
lo medí y **cero columnas llegan hoy al `assert`** (defecto 12).

---

## Los defectos

### A · La regla de oro: 1 de 7 excepciones es correcta

1. **`cen.res` no existe: la regla vuelve a inventar un campo (GRAVE).** Es el
   defecto por el que se rechazó la séptima pasada, movido de tabla. La regla
   dice que `cen.res` es «Reparto nombre» y la ficha lo repite
   (`raw.yaml:354-356`). Conté las coincidencias en el bloque de `cen` de
   `azure-apps/sigrid_tablas.md` (L4651-4715): **cero**. El `res | Reparto
   nombre` está en **`cenrep`** (L4723), tabla distinta que **ni se ingiere**.
   Lo corrobora nuestro SQL: `cierre/05_views_cabecera.sql:175` toma el nombre
   del centro de `cenc.res`, donde `cenc` es **`raw.con`**, y el `LEFT JOIN
   raw.cen` de la línea anterior no aporta ninguna columna.
2. **Cuatro falsos positivos más (MEDIA-GRAVE).** La regla exige «campos propios
   **con el mismo nombre**». `ctr`, `dca` y `dcf` llevan `entcod`, `entres`,
   `entcif` y `fecdoc` —nombres distintos—; `com` no tiene ninguno de los tres.
   Y `prv` no tiene `cod`/`res`/`fec`: tiene `cif` y `raz`, que es lo que dice
   bien el punto 4, así que el punto 3 la contradice y contradice a su propia
   ficha, que acierta.
3. **Y dieciséis falsos negativos (GRAVE).** «Las que los tienen son …» se lee
   como enumeración cerrada sobre las 31 tablas. Faltan `conext`, `obrparpar`,
   `obrfas`, `obrfasamb`, `obrctr`, `condir`, `obrprv`, los cinco catálogos
   `aux*`, `ctrpro`, `dcapro` y `dcfpro`. Mi barrido derivable sobre nuestro SQL
   —para cada alias de `raw`, usos de `.cod`/`.res`/`.fec`/`.raz`/`.cif`—
   confirma que **ocho de ellas se leen a diario sin unir a `con`**: entre otras
   **`obrparpar`** (`stg/04_partidas.sql:46-47`: `p.cod AS codigo_partida`,
   `p.res AS descripcion_corta` — el código y la descripción de la partida),
   `obrfas.res` (el nombre del mes) y los catálogos `auxobramb`, `auxobrtip`,
   `auxobrcla`, `auxpro`, `auxmun`, que **no tienen ninguna relación con `con`**:
   el JOIN que la regla sugiere no existe.
4. **La copia divergente sigue publicada (MEDIA).** La cabecera de `raw.yaml`,
   que encabeza las 31 fichas, conserva intacta la frase rechazada —«`cod`,
   `res` y `fec` viven en `con`, **no en la tabla especifica**»— y ocho líneas
   después declara: «Esta regla se publica ademas como `R-SIGRID-CON` en el
   bloque global», presentando como la misma dos versiones que divergen. Es el
   **quinto caso** del patrón: la corrección se aplica donde se señaló y la copia
   sobrevive.
5. **El mecanismo no podía cazarlo (MEDIA).** `CON_CAMPOS_PROPIOS`
   (`tests/test_f006_regla_de_oro.py:48`) es una lista escrita a mano, y el test
   que exige que las fichas repitan la excepción (`:143`) se parametriza solo con
   `["obr", "prv"]`: **con `cen` dentro habría fallado**. El comentario que
   justifica no derivarla del PDF es honesto —el segmentador daba resultados
   inestables, y de ahí salió justamente el error de `cen`/`cenrep`—, pero la
   conclusión es la equivocada: **había una fuente derivable sin usar, nuestro
   propio SQL**.

**Cómo cerrarlo**: que la regla enuncie el patrón sin lista cerrada, nombre las
excepciones verificadas una a una —`obr.res` es la única confirmada entre las
diez extensiones 1:1, y `prv` aporta `cif`/`raz` con otro nombre— y que un test
derive del SQL las tablas cuyos campos propios usa el ETL y exija que la regla no
las contradiga.

### B · La carga de `raw`: la nueva redacción es falsa contra la ejecución real

6. **La imagen desplegada hace recarga completa (GRAVE).** Las 31 fichas dicen
   ahora que la carga es append por `MAX(ide)` y que **«lo modificado en Sigrid
   no se refresca nunca»**. El `Dockerfile:26-27` dice lo contrario, y es lo que
   se despliega:

   ```dockerfile
   # El job nocturno SIEMPRE full (el incremental pierde UPDATEs).
   ENTRYPOINT ["python", "main.py"]
   CMD ["run-all", "--full"]
   ```

   Y lo corroboran `docs/ARCHITECTURE.md` («la ingesta nocturna SIEMPRE
   `--full`»), `infra/80_create_job.ps1` («el alcance de la carga nocturna está
   escrito en el Dockerfile y en ningún sitio más»), el runbook y
   `azure-apps/datamart_seg_anual.md`. La corrección se derivó de
   `ingest_raw_step.py` —la fuente correcta para *cómo* carga el comando— y no de
   la que gobierna *qué se ejecuta de noche*. Es el error que el docstring de ese
   mismo fichero de tests denuncia: «derivar de la fuente equivocada es tan malo
   como no derivar».
7. **La bandera citada 31 veces no existe (GRAVE).** Las fichas dicen «la recarga
   completa existe —`--full-refresh`, que hace `TRUNCATE`—». La opción real es
   **`--full`** (`python main.py ingest --help`); `--full-refresh` falla con «no
   such option». Un comando inejecutable, publicado 31 veces.
8. **«`run-all` no la pasa» es falso (MEDIA).** `run-all` tiene `--full`
   (`main.py:457`) y lo propaga hasta `IngestRawStep`. Lo cierto es que el
   *valor por defecto* es incremental; combinado con el defecto 6, la frase manda
   al lector justo al revés de lo que ocurre en producción.

### C · Copias supervivientes del mismo defecto

9. **`stg.yaml:323-326`** conserva la frase que esta misma tanda erradicó de las
   31 fichas de `raw`: `_source_tiemod` «Marca de modificacion de la fila en
   Sigrid, **que usa la ingesta incremental**». El barrido de frases prohibidas
   del test nuevo solo mira `raw.yaml`. Y falta la consecuencia que sí importa y
   nadie dice: bajo append, `_source_tiemod` guarda el `tiemod` que la fila tenía
   **al entrar**, así que es una marca de inserción, no de modificación.
10. **Cuatro `nulo_significa` imposibles en `stg.partidas`**, uno de ellos el que
    se acaba de «corregir»: `capitulo_raiz_cod` dice ahora «El capitulo raiz no
    tiene codigo en Sigrid», imposible porque la rama raíz filtra `p.cod IS NOT
    NULL AND p.cod <> ''` (`04_partidas.sql:57-58`). Igual en `codigo_partida`,
    `ruta_capitulos` y `nivel`, que se construyen sin poder ser nulos.

### D · Otras fichas

11. **`dec_cantidades` afirma gobernar una fórmula en la que no aparece
    (GRAVE).** La ficha (`stg.yaml:307-314`) dice que gobierna el redondeo
    `ROUND(ROUND(can, decc) * ROUND(pre, decp), deci)`. El SQL real es
    `ROUND(pp.can::NUMERIC * ROUND(pp.pre::NUMERIC, decp), deci)`
    (`06_presupuesto.sql:73-76`): **`decc` no interviene**, y la NOTA de cuatro
    líneas antes lo dice expresamente —«la cantidad NO se redondea… Sigrid solo
    redondea el PRECIO»—. El origen del error es reconocible: los comentarios de
    `08_plan_mensual.sql:309,401-402` sí repiten la fórmula con `decc`, y la
    ficha copió el comentario en vez del código. Es la deuda «comentarios del SQL
    que mienten» mordiendo por primera vez.
12. **El guardián de nulos no comprueba nada hoy (MEDIA, mecanismo).** Lo medí:
    15 fichas evaluadas, **30 columnas candidatas y cero llegan al `assert`** —se
    filtran todas en la guarda de proyección desnuda—. No es inútil: queda como
    alarma para el futuro. Pero, a diferencia de los otros seis detectores del
    fichero, **no tiene un `test_..._control_...`** que fije que sigue detectando
    algo, que es justo lo que impide que un detector se degrade a cero en
    silencio. Y ya está en cero.
13. **La plantilla de exclusiones es falsa en 19 fichas (MEDIA).** «No se traen N
    columnas: textos largos, observaciones e imagenes» se aplicó igual a todas:
    en `pag` la única excluida es `blores`; en `dca`/`dcf` seis de las 23 son
    direcciones; en `cen` y `obrprv` solo hay `tex`. En `dca`/`dcf` el texto
    anterior —«una lista larga de textos y campos de direccion»— era **exacto**,
    así que el diff cambió una frase cierta por una falsa. El test comprueba el
    número y las columnas citadas, no la caracterización.

### Menores

- «Antes de escribir cualquier consulta contra `raw`, **cinco cosas**» y numera
  **seis**; el `motivo` repite el error. El punto 6 —polimorfismo `docoritip`,
  nuevo, correcto y con cita literal verificada— queda anunciado como si no
  existiera.
- El punto 4 acierta con `prv.cif` pero omite que `ctr.entcif`, `dca.entcif` y
  `dcf.entcif` traen el CIF desnormalizado en la cabecera del documento.
- `stg.presupuesto` baja sus tres medidas a `ultimo_valor`, lo que contradice su
  propio `ejemplos_preguntas` («cuánto suma el presupuesto de venta…») y el uso
  real de `cierre/02_build_fact.sql:259-286`, que hace `SUM(importe_oficial)`
  sobre una fase fija. Lo no sumable es la dimensión `fase_num`, no la columna.
- `fase_num = 0` en los ámbitos reales es el «Previsto» vivo, no un mes, y el
  `grano` reescrito no lo recoge pese a que `cierre/02_build_fact.sql:252-286`
  depende de ello.
- La receta `grep -n "^| <tabla> "` que las 31 fichas dan para localizar la tabla
  en `sigrid_tablas.md` no aísla el bloque de `con`.
- `config/tables_sigrid.yaml` sigue diciendo «catálogo estable, refresco
  completo» en 13 tablas, y poner `incremental_column: null` no provoca ninguna
  recarga. Las fichas aciertan y el fichero de configuración miente.

---

## Lo que sí está verificado y correcto

### El fallo de `_proyeccion_de` no tuvo efecto retroactivo

Era lo que más preocupaba y se midió por dos vías independientes que coinciden:

- **Un solo llamante en toda su vida**: el guardián de nulos. `git log -S` da
  tres commits —nacimiento, corrección, informe— y ninguna otra llamada. Los
  demás contrastes van por `columnas_del_create_table`, `cuerpo_de_vista`,
  `cuerpo_del_insert`, `pk_declarada` y `proyeccion_por_alias`, todos
  cualificados por `esquema.objeto`.
- **Alcanzaba a una sola ficha**: `cierre.v_pbi_cierre_cabecera`, cuyo fichero
  crea **un solo objeto**. No había vecino del que heredar proyección.
- **Revalidación a mano de las seis fichas de `compras/01_documentos.sql`**: 78
  columnas documentadas contra 78 proyectadas, **ninguna ajena y ninguna
  omitida**, y los **30 `nulo_significa` respaldados por el `NULLIF`/`CASE` de su
  propio bloque**. Los dos casos donde el vecino sí habría mentido
  —`albaranes.contrato_id` y `factura_lineas.albaran_id`— son correctos.
- Mismo contraste sobre los otros once ficheros multiobjeto: **0 problemas**.

El acotado fue en la práctica un anti-falsos-positivos: eliminó tres acusaciones
falsas contra `compras` que aparecieron al ampliar el guardián. Correcto y
necesario, pero no reparó nada retroactivo.

### Lo demás

- **`pendientes` en 0 significa lo que dice**: biyección exacta, 102 fichas ↔ 102
  objetos, sin huérfanas ni fantasmas, con los recuentos por esquema cuadrando
  uno a uno. Salvedad ya conocida: «los que el repositorio publica» son los que
  ve la heurística; la verdad es R28, que sigue sin existir.
- **El punto 2 de la regla es exacto**: las diez «Propiedades de `con`» son
  exactamente esas diez. El punto 6 (polimorfismo) es correcto con cita literal.
  `con.nom` no existe, `obr.res` sí, y `prv.cif`/`prv.raz` tienen la doble
  verificación que declaran.
- **Mutación**: recalculada con el `__pycache__` borrado —2358 líneas, 166
  mutantes—, idéntica a lo declarado, 0 supervivientes y 0 timeouts.
  `harness/mutacion.py` **intacto**, como debe ser: su arreglo es F-041.
- **Nada prohibido**: el diff toca YAML, dominio, tests y `progress/`. Ni un
  `GRANT`, `REVOKE`, firewall, Azure ni conexión a la base. **Sin `push`**.
- El resto de correcciones de la tanda que verifiqué y son ciertas:
  `R-FRESCURA-MANUAL` con los seis pasos reales, `stg.fases.anio`/`.mes`,
  `maestro.obras.cliente_id`, `capitulo_raiz_id`, `version_master_vigente` a
  `1:N`, `total_incurrido` en los dos ámbitos reales y la guarda del mes oficial.

---

## Qué falta para poder pasar la batería de aceptación

Cuando se cierren estos trece, lo que queda ya no es contenido:

1. **T19**: publicar contra la base real y comprobar el contrato de `_meta`.
2. **T26/T27**: `check-diccionario` contra el catálogo real, con la consulta de
   unicidad de clave. Es además lo único que convierte «102 objetos» en una
   verdad y no en lo que ve una expresión regular.
3. **T39**: las 18 preguntas contra el diccionario publicado —13 respondibles, 3
   parciales y 2 que deben contestarse con un «no puedo, y este es el motivo»—.
4. Los bloques 🔏 de permisos y firewall, que necesitan firma del humano.

Y la deuda declarada que viaja: el falso positivo del detector de multifuente,
los menores 5-7 de la sexta pasada, F-041 para que «cero supervivientes»
signifique lo que dice, y ahora los comentarios del SQL que mienten —que con el
defecto 11 han dejado de ser deuda teórica—.

---

# SÉPTIMA PASADA · 2026-08-20 — el diccionario completo

> Commits revisados: `c5c0bd6`..`df4b199`. Alcance nuevo: los **53 objetos** que
> faltaban —`maestro` (4), `stg` (10), `aux` (1), `_meta` (7) y `raw` (31)—.
> Total del diccionario: **102 objetos, 793 columnas, 13 reglas, `pendientes` en 0**.

## Veredicto de la séptima pasada

**RECHAZADO.** El andamiaje de esta tanda es excelente —los recuentos cuadran, el
trinquete llega a 0 de verdad, la mutación se recalcula sola, el barrido de
comentarios está automatizado y los tres hallazgos de «derivar antes de
corregir» son ciertos— pero **el contenido de los dos esquemas más grandes tiene
defectos graves**, y son de la clase que esta feature existe para impedir: fichas
que producen números falsos y una regla **bloqueante** que le dice al agente que
un campo cargado en la base no existe.

Los diez que bloquean están abajo. Ninguno es de forma: los verifiqué uno a uno
contra el SQL y contra `azure-apps/sigrid_tablas.md`.

---

## Lo que hay que corregir

### En `raw` y en la regla de oro

1. **`R-SIGRID-CON` está sobregeneralizada, y es `bloqueante` sobre las 31
   fichas.** Dice que `cod`, `res` y `fec` viven en `con` «**no en la tabla
   específica**». Falso para la tabla más consultada del datamart:
   `sigrid_tablas.md:16542` da `obr.res = "Nombre completo", Texto ilimitado`, y
   `raw.obr` se ingiere con `exclude_columns: []`, así que **la columna está
   cargada en Postgres**. El `motivo` repite el error —«consultar `obr` sin unir
   a `con` devuelve una obra sin nombre y sin código»: sin código sí, sin nombre
   no— y la ficha `raw.obr` (`raw.yaml:115-118`) lo dice otra vez. Una regla
   bloqueante que niega un campo real es peor que no tenerla.
2. **La ficha `raw.prv` ubica el CIF donde no está** (`raw.yaml:373-374`: «el
   CIF, el nombre y el código del proveedor están en `con`»). El CIF es
   `prv.cif`, y lo confirma el propio repositorio:
   `maestro/02_proveedores.sql:28-29` toma `p.cif` y `p.raz` **de `raw.prv`**, y
   solo `cod`/`res` de `raw.con`. El agente que siga la ficha buscará `con.cif` y
   se estrellará: exactamente el fallo que la regla de oro existe para evitar.
3. **Las 31 fichas describen mal cómo se carga la tabla.** 18 dicen «carga
   incremental por `tiemod`» y 13 «se recarga entera cada noche», y **ninguna de
   las dos cosas ocurre**: `ingest_raw_step.py:205-211` toma
   `last_id_already = pg.get_max_id("raw", tabla, "ide")` —append de los `ide`
   por encima del máximo ya guardado— y usa `incremental_column` **solo** para
   volcar `_source_tiemod`. Una fila modificada en Sigrid no se refresca nunca, y
   el `TRUNCATE` solo ocurre con `full_refresh=True`, que `run-all` no pasa. Es
   información operativa falsa sobre la frescura del origen.
4. **`tiemod` no existe en 15 de las 18 tablas** a las que `tables_sigrid.yaml`
   —y por herencia la ficha— le asigna esa columna de corte. Solo `con` y
   `comprv` la tienen.
5. **Trece punteros a objetos que no existen**: `compras.documentos` (×7) y
   `compras.fact_linea` (×6), en las fichas de `con`, `ctr`, `ctrpro`, `dca`,
   `dcapro`, `dcf` y `dcfpro`. Lo verifiqué: 13 menciones en `raw.yaml` y **cero
   apariciones en todo el SQL**; los reales son `compras.contratos`,
   `compras.albaranes`, `compras.facturas` y `compras.fact_compras_linea`. Como
   todo el argumento de DA-2 es «no consultes `raw`, ve aguas abajo y la ficha te
   dice dónde», el puntero roto vacía el `motivo_no_consumo` de siete tablas.
6. **Ninguna de las 31 fichas remite a `azure-apps/sigrid_tablas.md`**, que es la
   contrapartida que DA-2 prometía a cambio de no documentar columnas. Las dos
   menciones viven en el comentario de cabecera, que `yaml.safe_load` descarta.
   **Rectifico aquí mi propio barrido**: lo hice contra el publicable *global*, y
   ahí el puntero aparece —en la entrada `esquemas.raw` de `00_global.yaml`—, así
   que lo di por bueno. El matiz que se me escapó es que un agente que pida
   `describir_tabla('raw.dcapro')` recibe la ficha, no el bloque de esquema: el
   puntero tiene que estar **en la ficha**.

### En `stg`

7. **`stg.presupuesto` no dice que en los ámbitos reales es ACUMULADO A ORIGEN, y
   encima marca `agregacion: suma`.** Las tres medidas —`cantidad`, `importe`,
   `importe_oficial`— llevan `suma`, y el desacumulado se hace aguas abajo por
   diferencia con la fase anterior (`08_plan_mensual.sql:346-352`:
   `cantidad - LAG(cantidad)`). Sumar a través de `fase_num` multiplica. Es la
   trampa de `R-IMPORTE-MES` otra vez, en la ficha que se autoproclama «la fuente
   buena para cuál es el presupuesto de la obra» y que propone como ejemplo
   «Cuál es el presupuesto de la obra X».
8. **La trampa de las versiones master no está escrita en `stg.presupuesto`**,
   donde aplica igual que en `plan_mensual`: en los ámbitos 8 y 11 hay una fila
   por versión. La ficha invita a la pregunta y solo dice «filtrar la fase
   correcta», sin advertir de qué pasa si no se filtra.
9. **`stg.fases.anio` y `.mes` declaran un origen falso**: «derivado de su fecha
   de inicio», con `nulo_significa: La fase no tiene fecha de inicio`.
   `05_fases.sql:26-27` los copia de `f.ano` y `f.mes` de `raw.obrfas`, que son
   independientes de `fecini`. No es cosmético: `08_plan_mensual.sql:328-329`
   exige `anio`/`mes` no nulos para construir los ámbitos reales.
10. **Cuatro `nulo_significa` imposibles en `stg.partidas`, uno de ellos
    invertido**: `capitulo_raiz_id.nulo_significa: «La propia fila es el capítulo
    raíz»` cuando `04_partidas.sql:51` hace exactamente lo contrario —«En la
    raíz, ella misma es el raíz», `p.ide AS capitulo_raiz_id`—. Buscar las raíces
    con `WHERE capitulo_raiz_id IS NULL` devuelve cero filas.

### En `maestro`, y en el mecanismo que debía impedirlo

11. **`maestro.obras.cliente_id` declara un nulo que nunca ocurre**, y es la
    **reincidencia exacta** del defecto que ya corregimos en la tercera pasada.
    `maestro/01_obras.sql:26` proyecta `o.entide AS cliente_id` **sin
    `NULLIF(…, 0)`** —el propio fichero avisa en su cabecera de que en Sigrid
    esas referencias «vienen a 0»— y la ficha (`maestro.yaml:75`) dice
    `nulo_significa: La obra no tiene cliente asignado`. Un `WHERE cliente_id IS
    NULL` devuelve cero filas siempre.
    Lo importante es **por qué se coló**: el guardián que se escribió para esto,
    `test_f006_r2_un_nulo_declarado_en_un_ide_tiene_que_ser_posible`, filtra por
    `columna.nombre.endswith("_ide")` (`tests/test_f006_fichas.py:514`), y
    `maestro` nombra sus columnas `_id`. El mecanismo estaba y no cubrió el caso
    por un sufijo. Arreglo doble: la ficha, y ampliar el guardián a `_id`.
12. **El `motivo` de `R-FRESCURA-MANUAL` cita una composición del pipeline que ya
    no es la real** (`00_global.yaml:49-51`): «IngestRaw, LoadExcelAux, BuildStg,
    BuildMart y ApplyGrants». Falta **`PublicarDiccionarioStep`**, que el bloque E
    insertó entre `BuildMart` y `ApplyGrants`. La conclusión de la regla no
    cambia, pero es una regla `bloqueante` cuya evidencia citada está desfasada
    desde hace dos tandas.
13. **`tests/test_f006_raw_ingesta.py:78-97` pasa en vacío en 11 de las 31
    fichas.** La aserción es `citadas <= excluidas`, que se cumple trivialmente
    cuando `citadas` está vacío, y las columnas citadas se extraen con una regex
    que exige un formato de prosa concreto (`**No se traen** …`). Hoy solo 7
    fichas citan alguna, mientras 11 tienen exclusiones y no citan ninguna
    —`dca` y `dcf` con 23 columnas excluidas cada una—. Sin un control de
    no-vacuidad, el día que alguien escriba el aviso con otro formato el test
    seguirá verde mientras la ficha calla.

### Deuda de la misma tanda, que puede viajar

`stg.fn_master_fecha_efectiva` omite la guarda `IF v_mes_creac IN (2,6,10)`, que
es media regla; `stg.version_master_vigente` declara `N:N` una relación que es
`1:N`; `stg.plan_mensual.total_incurrido` dice «no es de coste real» cuando
también llega en el ámbito 7; `presupuesto.dec_cantidades` dice gobernar un
redondeo que el SQL declara explícitamente que no aplica; `R-SIGRID-CON` no
advierte de las referencias polimórficas (`linoriide` + `docoritip`); y
`domain/diccionario.py:99` sigue diciendo «las DOCE reglas duras» cuando la tupla
tiene trece.

---

## Los números, recontados

No me fío de los recuentos y esta vez hay una discrepancia con lo que llegó por
el chat, sin consecuencias pero conviene fijarla:

| | Declarado | Medido por mí |
|---|---|---|
| Tests | 1496 | **1557** |
| Saltados | 40 | **82** |
| Cobertura | 99,0 % de 722 | 99,0 % de 722 ✔ |
| Objetos / columnas / pendientes | 102 / 793 / 0 | **102 / 793 / 0** ✔ |

La diferencia de tests es de medición: el líder contó antes de los cuatro
últimos commits. El **inventario cuadra exactamente**: 102 fichas para 102
objetos publicados, `pendientes` vacía y `PENDIENTES_MAX = 0`. El trinquete en 0
significa lo que dice.

Reparto verificado: `_meta` 7 objetos (los tres de instrumentación más las tres
tablas del diccionario y su vista), `aux` 1, `cierre` 12, `compras` 14,
`maestro` 4, `mart` 13, `raw` 31 **con 0 columnas** —como manda DA-2—,
`retenciones` 10 y `stg` 10.

## Los 82 saltados, explicados

Subieron de 40 a 82 y el informe no lo menciona, así que lo desgloso:

| Nº | Motivo | Veredicto |
|---|---|---|
| 31 | «las tablas de `raw` no tienen DDL en el repositorio (DA-2)» | **legítimo y esperado**: son las 31 fichas nuevas de `raw` |
| 35 | «el `GROUP BY` de este objeto no es derivable» | legítimo (eran 28; suben porque hay más objetos) |
| 6 | «la PK es una clave sustituta; la de negocio es otra cosa» | **legítimo, y es la prueba de que la corrección de la PK inline funciona** |
| 3+3 | «la proyección no se deja leer» | legítimo: los catálogos `VALUES` |
| 2 | «el DDL no declara clave primaria, ni aparte ni inline» | legítimo: las CTAS sin PK |
| 2 | «se crea con SQL dinámico; tiene su propio test» | legítimo, ya validado |

**Ninguno esquiva una comprobación que antes se ejecutara.** Y el mensaje falso
que denuncié en la cuarta pasada está corregido: ahora dice «ni aparte ni
inline» y solo aplica a las dos tablas que de verdad no tienen PK; las tres
tablas de hecho caen en la rama correcta —clave sustituta—, que antes no se
alcanzaba.

## La mutación, mirada con lupa

- **Recalculada de forma independiente**: alcance **2358 líneas**, **166
  mutantes**. Coincide con `progress/mutacion_F-006.md`, que declara 166
  evaluados, 166 muertos, **0 supervivientes y 0 timeouts**.
- **Los cuatro «timeouts» eran cuatro supervivientes**, y está contado sin
  adornos en `tests/test_f006_supervivientes.py`, que además explica por qué
  sobrevivían: dos `frozen=True → False` en `Columna` y `Relacion` —que nadie
  cazaba, mientras la hermana `Ficha` sí tenía quien la cazara— y dos mínimos de
  longitud subidos en uno, que sobrevivían porque **ningún caso ejercitaba el
  borde**. La lección que deja escrita es la correcta: **un timeout no es un
  mutante muerto, es un mutante sin evaluar.**
- **El mutante vivo en el bytecode: confirmado, y lo reproduje.** Monté un
  módulo de laboratorio fuera del repositorio, generé su `__pycache__`, apliqué
  una mutación **del mismo tamaño** conservando el `mtime`, y después restauré el
  fuente original conservándolo otra vez. Python siguió ejecutando el bytecode
  **mutado**:

  ```
  resultado: True      <- fuente original
  resultado: False     <- fuente mutado
  resultado: False     <- fuente RESTAURADO, pero corre el .pyc mutado
  ```

  Es real y es serio: con el fuente restaurado la suite corre contra código
  mutado. En este caso dio un falso rojo; **en el caso simétrico daría un falso
  verde**, es decir, un mutante contado como muerto sin estarlo.

  **Salvedad que el líder debe conocer**: `harness/mutacion.py` **no se ha
  tocado** —lo comprobé: el diff de `harness/` en esta tanda es solo
  `features.json`—, así que el defecto sigue vivo en la herramienta y la campaña
  de 166/166 se midió con él presente. Está dado de alta como **F-041**, junto
  con el recuento de timeouts y los worktrees huérfanos, y es del arnés genérico,
  así que viaja a `arnes-base` por la regla de propagación. No bloquea F-006: la
  evidencia disponible es la que la herramienta puede dar hoy, y los cuatro
  supervivientes reales se reevaluaron uno a uno.

## La regla de oro, verificada en la fuente

`R-SIGRID-CON` es la decimotercera regla y gobierna cómo un agente entiende todo
`raw`. **Fui a la fuente** (`azure-apps/sigrid_tablas.md`, entidad `con`) y sus
puntos centrales se confirman al pie de la letra:

| Afirmación | Verificación |
|---|---|
| «`ide` es la clave … y es el índice primario» | `ide Identificador \| Entero \| INDICE PRIMARIO \| Unico` |
| «`cod`, `res` y `fec` viven en `con`» | los tres están en la entidad: `cod Código`, `res Resumen`, `fec Fecha alta` |
| «`con.nom` NO EXISTE; el nombre legible es `con.res`» | **no hay ningún campo `nom`** en la entidad |
| El `motivo` cita `ide`, `cod`, `res`, `fec`, `est` y `fecbaj` | los seis están, con esos nombres |
| «un campo que acaba en `ide` es una referencia» | la lista de referencias de `con` es exactamente eso: `pag.conide`, `ctr.entide`, `obrfasamb.ofeentide`… |

Y el hallazgo que la motiva es cierto y no menor: **la regla estaba solo en un
comentario del YAML**, y los comentarios no se publican. El MCP no la habría
visto nunca.

## El parser que no veía las columnas migradas

Verificado por mí, y es un hallazgo genuino de «derivar antes de corregir»:
`_meta.etl_runs.batch_id` **no está en el `CREATE TABLE`**, se añade después con
`ALTER TABLE _meta.etl_runs ADD COLUMN IF NOT EXISTS batch_id TEXT NULL`
(`sql/ddl/00_meta.sql:34`). El contraste exacto de columnas no leía los `ALTER`,
así que acusaba a la ficha de documentar una columna inexistente **cuando la
columna existe**, solo que migrada. Ejecuté el parser corregido sobre el fichero
y devuelve las diez columnas, `batch_id` incluida. Si se hubiera «corregido» la
ficha en vez del parser, se habría borrado de la ficha una columna real.

## El barrido de comentarios, hecho a máquina

Es la segunda vez que aparece el mismo fallo —ya pasó con el aviso de frescura en
la cabecera—, así que no me fié del barrido manual: parseé los diez YAML con
`safe_load` —que descarta los comentarios— y comparé el conjunto de
identificadores citados en comentarios contra **todo** el texto publicable del
diccionario.

**No queda ninguna afirmación importante fuera de lo publicable.** Los únicos
identificadores que viven solo en comentarios son `describir_tabla` —el nombre
de una herramienta del MCP— y `exclude_columns` / `incremental_column`, que son
claves de `config/tables_sigrid.yaml` citadas al explicar **cómo se verificó** la
ficha; lo que esas claves significan está contado en prosa publicable en 19
sitios de `raw.yaml`. Ninguno de los tres es semántica de negocio.

## El nombre de fichero que git no podía indexar

`aux.yaml` pasaba los tests y `git add` lo rechazaba: `AUX` es nombre de
dispositivo reservado en Windows. La solución —`aux_.yaml`, con el sufijo de la
convención de Python— es correcta y está bien acotada:

- **el contenido sigue declarando `esquema: aux`**, que es lo que consultará el
  MCP: el nombre del fichero no se publica;
- el cargador resuelve **la familia entera** de reservados —`con`, `prn`, `aux`,
  `nul`, `com1`–`com9`, `lpt1`–`lpt9`— en una sola función usada por el cargador
  y por quien cree un esquema nuevo;
- y el comentario señala el caso que habría dolido de verdad: **`con` es el
  nombre de la tabla central de Sigrid**.

## Rigor y comprobaciones de siempre

- **1557 tests + 82 saltados**, ejecutados por mí; cobertura **99,0 % de 722
  líneas**.
- **Nada prohibido**: el diff no toca `main.py`, `settings.py`, `grants.py`,
  `postgres_client.py`, `infra/**` ni ningún SQL de negocio; ni un `GRANT`,
  `REVOKE`, firewall, Azure ni conexión a la base. **Sin `push`**: no hay rama
  remota. **Sin worktrees huérfanos.**
- El dominio sigue puro: `diccionario.py` importa solo `re`, `collections.abc` y
  `dataclasses`; el manejo de nombres de fichero vive en el cargador, que es
  infraestructura.
- Deuda menor nueva: un aviso `I001` de `ruff` en
  `tests/test_f006_supervivientes.py` (orden de imports). Es la segunda vez que
  un test nuevo entra con ese aviso.
- **Matiz de proceso**: el commit `df4b199` es de **F-041** y va en la rama de
  F-006. Es solo el alta en `features.json` y `BACKLOG.md` de una feature nacida
  de este trabajo, no una implementación, así que es defendible; conviene que el
  líder lo sepa porque la regla es una rama por feature.

---

## Lo que esta bien y no hay que rehacer

El rechazo es de contenido y el andamiaje es solido; conviene decirlo para que la
correccion no se lleve por delante lo que funciona:

- **Ni una columna inventada ni omitida** en las 75 de `stg`, contrastadas una a
  una; ni una ficha de `raw` de mas o de menos: las 31 `target_table` de
  `config/tables_sigrid.yaml` casan con las 31 del YAML, en el mismo orden.
- Los **31 titulos de `raw`** coinciden literalmente con la fila de entidad del
  autodocumentador de Sigrid, y las 31 tablas tienen `ide` como indice primario
  unico, como afirma la regla.
- **Nueve de las doce afirmaciones de `R-SIGRID-CON` son ciertas**, incluidas las
  dos que mas pesan: `con.nom` no existe y el `0` es el NULL de las fechas.
- Las **seis trampas de `stg`** que se pidio comprobar estan escritas en campos
  **publicables** y son ciertas: ninguna vive solo en un comentario.
- **`_meta` y `aux_` estan limpios**: los siete objetos de `_meta` casan columna a
  columna con su DDL —y `v_diccionario` conserva el orden del contrato, con
  `motivo_no_consumo` la ultima—, y las dos afirmaciones de `aux_` (se crea vacia
  por diseno, la vista no periodifica nada) se verificaron contra el SQL.
- Las tres trampas de `maestro` estan escritas y son ciertas.
- Las seis tablas de `raw` que las fichas declaran sin consumidor son exactamente
  las seis que ningun SQL lee.

Con esas bases, lo que falta es corregir trece afirmaciones y dos mecanismos, no
rehacer el trabajo.

## Checkpoints (septima pasada)

**C1** `[x]` · **C2** `[x]` · **C3** `[x]` · **C3 bis** N/A · **C4** `[ ]` —trece
afirmaciones publicadas que el SQL o el origen desmienten, una de ellas en una
regla bloqueante— · **C4 bis** `[x]`, con la salvedad del bytecode · **C4 ter**
N/A · **C5** N/A parcial (los bloques A a G del alcance encargado).

---

# SEXTA PASADA · 2026-08-20 — cierre

> Commits revisados: `6fb7f13`..`c81457f`.

## Veredicto de la sexta pasada

**APROBADO, sin matices.**

Los tres defectos de la quinta pasada están cerrados y verificados contra el SQL,
y el trabajo entregado queda aprobado con este alcance:

| Bloque | Estado |
|---|---|
| **A · Formato** (T3–T8) | aprobado |
| **B · Reglas duras** (T9–T11) | aprobado |
| **C · Fichas de `mart`** (T12, T13) | aprobado |
| **D · Fichas de `cierre`** (T14) | aprobado |
| **E · Publicación en `_meta`** (T15–T18) | aprobado — T19 queda como verificación MANUAL (humano), con sus comandos escritos |
| **F · parcial** (T20 `compras`, T21 `retenciones`) | aprobado |

**49 fichas, 593 columnas, 12 reglas duras y el contrato con `mcp-bbdd`**, con las
claves, los granos, las cardinalidades, las nulidades y las agregaciones
contrastadas contra el SQL que crea cada objeto. Quedan 53 objetos por documentar
—`stg`, `maestro`, `aux`, `_meta`, `raw`— y su trinquete en 53.

## Los tres defectos

1. **`v_pbi_retencion_obra`** declara ahora la clave de tres columnas y su grano
   explica por qué: «en `retenciones.movimientos` las tres se resuelven con
   cascadas DISTINTAS […] un `obra_id` cuyo centro de coste no exista en el
   maestro puede aparecer con dos códigos y dar DOS filas». Cerrado.
2. **`v_pbi_cierre_indirectos_detalle`**: «traen valor tanto si el grupo se
   periodifica como si no, **pero pueden ser nulas por su propia causa**: no
   haber presupuesto vivo o no haber plazo calculable». Cerrado, y con el SQL por
   delante.
3. **La premisa falsa del comentario del test**, cerrada y con el porqué escrito.
   **Y corregida también en este informe**, que era donde nació: ver la nota de
   enmienda en la cuarta pasada, §«La acotación de lo no derivable».

## El barrido, y los dos «legítimos»

El barrido automatizado —hecho **antes** de tocar nada, que era la lección
pendiente— dio tres candidatos. Los reproduje ejecutando el detector sobre los 49
objetos y **salen exactamente los mismos tres**. De los dos declarados legítimos,
verifiqué la dependencia contra el SQL:

- **`mart.fact_seguimiento_categoria`** omite `anio`, `mes`, `tipo_dato`,
  `concepto` y `ambito_id`. Las dos primeras se derivan de `anio_mes` y las tres
  siguientes de `escenario`, cuya correspondencia es 1:1 y está fijada en
  `mart.v_pbi_dim_escenario`. **Legítimo.**
- **`retenciones.v_pbi_retencion_entidad`** omite `entidad_nombre` y
  `entidad_cif`. Aguas arriba, en `movimientos`, las dos ramas resuelven
  `entidad_nombre` con `ent.res` —una sola fuente, lookup por `entidad_id`— y
  `entidad_cif` con `prv.cif` en la rama PROVEEDOR y `NULL` constante en la de
  CLIENTE (`01_movimientos.sql:57-59, 105-107`). **Legítimo.**

Ninguno de los dos miente.

## El ataque a la comprobación nueva

Es la que va a gobernar los 53 objetos que faltan, así que fui a romperla.

**Lo que hace bien**: ejecutada sobre el diccionario entero **no marca ni una
sola columna**, y las siete omisiones legítimas de arriba pasan limpias. Su test
de control separa los dos casos (`COALESCE(cen_con.cod, obr_con.cod)` sí,
`ent.res` no, `COALESCE(od.num_obras, 0)` no). Cero falsos positivos hoy.

**Dónde se rompe** (encontrado, reproducido, y **no bloquea**): la regla mira si
dentro del `COALESCE` hay dos alias distintos, no si esos alias resuelven al
**mismo objeto**. Construí una vista con dos ramas de la misma tabla unidas por
la propia clave:

```sql
SELECT COALESCE(a.obra_id, b.obra_id)         AS obra_id,
       COALESCE(a.nombre_obra, b.nombre_obra) AS nombre_obra,
       SUM(a.importe_mes)                     AS total
FROM mart.fact_seguimiento_mensual a
FULL JOIN mart.fact_seguimiento_mensual b ON a.obra_id = b.obra_id
GROUP BY obra_id, nombre_obra;
```

Aquí `nombre_obra` **sí** depende de `obra_id` —las dos ramas son la misma
tabla—, y el test la marca:

```
['mart.v_prueba_fulljoin.nombre_obra'] se agrupan y salen de un COALESCE de
varias fuentes, asi que no se pueden dar por dependientes de la clave: o entran
en ella, o la ficha promete una unicidad que no existe
```

Es decir: obligaría a meter `nombre_obra` en la clave, **a mentir en la ficha
para pasar la puerta**, que es justo lo que había que evitar. Dos matices que lo
dejan en deuda y no en defecto: hoy **ningún objeto del repositorio** tiene ese
patrón en un `GROUP BY` analizable, y la variante con `GROUP BY` por expresiones
—`GROUP BY COALESCE(...), COALESCE(...)`— ni siquiera se analiza, así que tampoco
salta. El patrón existe ya en el repositorio dentro de una CTE
(`06_views_cp_tipologia.sql`, `detalle_partida`: `COALESCE(r.codigo_partida,
p.codigo_partida)` sobre las dos ramas de un `FULL JOIN`), así que aparecerá.

**Arreglo cuando muerda**: comparar si los dos alias del `COALESCE` resuelven al
mismo objeto en el `FROM`/`JOIN`; si lo hacen y el join es por la clave, la
dependencia se mantiene. Alternativa barata: permitir declarar la omisión
justificada en la ficha, como ya se hace con `motivo_no_consumo`.

## Deuda declarada que viaja con los bloques que faltan

Por decisión del líder, y con mi acuerdo: los menores 5 (la analogía suavizada de
`compras.yaml`), 6 (`MIN`/`MAX` sobre todos los efectos en una vista de saldo
vivo, preexistente) y 7 (la justificación del SQL de T26 que dice que agrupar los
NULOS es «como se comportan en un JOIN», cuando es al revés: es **más** estricto
que un JOIN). A esos tres se suma el falso positivo de arriba. Ninguno bloquea, y
los cuatro están escritos con su caso reproducible.

## Rigor

- **1361 tests + 40 saltados**, ejecutados por mí; cobertura **98,9 %**.
- **Mutación verificada de forma independiente**: 2324 líneas, **161 mutantes**,
  cero supervivientes; coincide con `progress/mutacion_F-006.md`.
- **Nada prohibido**: el diff toca dos YAML, un fichero de tests y `progress/`.
  Ni un `GRANT`, `REVOKE`, firewall, Azure ni conexión a la base. **Sin `push`**.
- Trinquete coherente: 49 fichas + 53 pendientes = 102 objetos.

### Checkpoints

**C1** `[x]` · **C2** `[x]` · **C3** `[x]` · **C3 bis** N/A · **C4** `[x]` ·
**C4 bis** `[x]` · **C4 ter** N/A · **C5** N/A parcial (20 de 42 tareas: el
alcance encargado; C5 se exigirá entero cuando F-006 pase a `done`).

---

# QUINTA PASADA · 2026-08-20 — el grano, derivado

> Commits revisados: `d07a67a`..`bbf9045` (cuatro). Alcance: T15–T18, T20 y T21.

## Veredicto de la quinta pasada

**RECHAZADO**, por dos defectos de gravedad media que aparecieron al terminar el
contraste de los 28 granos.

**Rectifico un veredicto que ya había emitido.** Di APROBADO apoyándome en mis
propias comprobaciones —el recuento, los mecanismos, cinco granos muestreados— y
dejando dicho que dos auditorías paralelas seguían corriendo. Al llegar,
confirmaron los 28 granos uno a uno y **encontraron dos cosas que yo no había
mirado**. Las he verificado contra el SQL y son ciertas, así que el veredicto
cambia. Es la segunda vez en esta feature que me pasa lo mismo, y la lección es
la de siempre: el contraste caso a caso encuentra lo que el muestreo no.

Lo que se pidió está hecho y bien hecho —los cuatro defectos de campo vecino, los
tres menores, la vía (a) implementada y la (b) diferida con criterio—, y los 28
granos reescritos son ciertos: **ninguno se escribió para el test**. Lo que falla
es otra cosa: **el barrido de copias no fue exhaustivo**, y quedan dos fichas que
siguen diciendo algo que el SQL desmiente. El commit se titula «los cuatro
defectos de campo vecino»; este es el quinto y el sexto.

Lo importante de esta tanda no es que se hayan corregido cuatro fichas: es que
**el defecto que llevábamos tres pasadas persiguiendo caso a caso era
sistemático**, y solo se vio al derivarlo. Eso confirma lo que veníamos diciendo
desde la segunda pasada, y esta vez el número lo dice sin ambigüedad.

---

## Lo que hay que corregir

### 1 · `retenciones.v_pbi_retencion_obra`: la clave no cubre su `GROUP BY` (MEDIA)

Es **el mismo defecto que motivó el rechazo de la tercera pasada**, en la ficha
hermana de la que sí se corrigió.

- Ficha (`retenciones.yaml:363`): `grano` «Una fila por `obra_id`» y
  `clave_negocio: [obra_id]`.
- SQL (`retenciones/02_views.sql:89`): `GROUP BY obra_id, codigo_obra, nombre_obra`.
- Y las tres columnas **no se derivan unas de otras**: en `movimientos`,
  `obra_id = COALESCE(NULLIF(p.cenide,0), CASE WHEN od.num_obras = 1 THEN
  od.obra_unica END)` mientras `codigo_obra = COALESCE(cen_con.cod, obr_con.cod)`
  y `nombre_obra = COALESCE(cen_con.res, obr_con.res)`
  (`01_movimientos.sql:61-64`): son cascadas distintas, resueltas por joins
  distintos. Con `cenide <> 0` sin fila en `raw.con` y `num_obras = 1`, la misma
  `obra_id` puede salir con dos `codigo_obra` → **dos filas para la clave
  declarada**, y quien una por `obra_id` duplica.

En `compras.v_pbi_partida_coste` este mismo caso se corrigió bien, y su ficha lo
explica con esas palabras: «`codigo_obra` se resuelve con una cascada distinta de
la de `obra_id`» (`compras.yaml:919-920`). Faltó cruzarlo con `retenciones`.

**Por qué no lo cazó el test nuevo**: el contraste es `clave ⊆ GROUP BY`, de
subconjunto y no de igualdad. Es la limitación que ya señalé en la cuarta pasada,
y este es el caso donde muerde. La comprobación de unicidad de T26 lo resolvería,
pero hasta entonces la ficha miente.

### 2 · `cierre.v_pbi_cierre_indirectos_detalle`: «traen valor siempre» es falso (MEDIA)

El `grano` (`cierre.yaml:499-500`) afirma: «Sus dos entradas, `importe_fase0` y
`plazo_total_meses`, **traen valor siempre**». No es cierto, y **la propia ficha
se contradice cincuenta líneas más abajo**: `importe_fase0.nulo_significa: La
subcategoria no tiene presupuesto vivo` (`:550`) y
`plazo_total_meses.nulo_significa: La obra no tiene plazo calculable` (`:559`).
El SQL confirma que ambas pueden ser NULL —`04_views_detalle.sql:340-341` guarda
explícitamente `WHEN po.plazo_total_meses IS NULL THEN NULL` y `WHEN
f0s.importe_fase0_subcat IS NULL THEN NULL`, y las dos llegan por `LEFT JOIN`—.

La intención se adivina —«traen valor **sea el grupo INFRA o no**», que es lo que
dicen bien los `significado` de las dos columnas— pero, tal y como está escrito,
quien lea el grano concluye que nunca son nulas y no comprobará el NULL. Es de
una línea: «traen valor tanto si el grupo se periodifica como si no; pueden ser
nulas por su propia causa (ver `nulo_significa`)».

### 3 · Una premisa falsa sostiene el límite del test — y la escribí yo (MEDIA-BAJA)

`tests/test_f006_fichas.py:1156` justifica por qué «la clave es demasiado corta»
no es derivable diciendo: «`codigo_obra` **sí** depende de `obra_id` y
`proveedor_cif` NO depende de `proveedor_id`». La segunda mitad es cierta; **la
primera es falsa**, y lo desmiente el propio commit en `compras.yaml:919-920`
—con el SQL a favor de la ficha—.

El origen de la frase es mi informe de la cuarta pasada: la escribí yo, el
implementer la tomó como fundamento y su propia corrección la contradice. Hay que
arreglarla en los dos sitios, porque el límite del test sigue siendo real —lo es
por `proveedor_cif`— pero el ejemplo que lo ilustra es justamente un caso en el
que la dependencia **no** existe.

### Menores

4. `retenciones.yaml:428-431` etiqueta `N:1` la relación `obra_id →
   maestro.obras.obra_id` mientras el grano de esa misma ficha dice una fila por
   `obra_id`; los dos casos análogos de `compras` usan `1:1` (`:694`, `:887`).
   Una de las dos afirmaciones sobra. (Se resuelve sola al corregir el defecto 1.)
5. `compras.yaml:667-669`: la analogía nueva («`importe_facturado` tampoco
   filtra») compara cosas distintas —ahí no filtrar da el neto correcto, sobre
   `factura_lineas`; en el pendiente arrastra NOTA y OTRO, sobre
   `albaran_lineas`—. La corrección era necesaria, pero suaviza un aviso que no
   conviene suavizar.
6. `v_pbi_retencion_entidad.primera_devolucion_prevista` y
   `ultima_devolucion_prevista` son `MIN`/`MAX` sobre **todos** los efectos,
   liquidados incluidos (`02_views.sql:45-46`), y la ficha no lo dice en una
   vista cuyo titular es `saldo_vivo`. Preexistente, no de esta tanda.
7. La justificación del SQL de unicidad de T26 dice que agrupar los NULOS es
   «como se comportan en un JOIN»: **falso**, en un `JOIN … ON a.x = b.x` los
   NULL no casan. Agruparlos juntos es **más estricto** que un JOIN, que es lo
   que conviene para comprobar una clave, pero el motivo escrito no es el
   verdadero. El SQL en sí es correcto.

## El 28 de 41, verificado

No me fié del recuento. Lo reproduje: en un worktree aislado dejé los tests de
HEAD y **revertí los cinco YAML al commit anterior** (`c20c933`), que es
exactamente «activar la comprobación sobre el diccionario de ayer». Resultado:

```
28 failed, 14 passed, 268 deselected
```

**28 de 42 fichas con clave declarada**, ni una más ni una menos. Es decir: dos
tercios del diccionario tenían un `grano` que no nombraba todas las columnas de
su propia clave, incluidas fichas de `mart` y `cierre` que tres revisiones
—las mías entre ellas— habían dado por veraces. Lo eran en columnas, en claves y
en cardinalidades; en granos, no.

Vale la pena decirlo claro porque es la lección de las cinco pasadas: **la
revisión humana caso a caso encontró dos; la comprobación derivada encontró 28**.

## Las 28 correcciones — la parte que había que mirar de verdad

El riesgo de reescribir 28 granos de golpe contra un criterio automático es que
alguno se escriba para el test y no para el lector. Lo verifiqué por dos vías: un
barrido propio en busca de coletillas —del tipo «… la clave incluye X, Y, Z»
pegado al final, que satisface el `\b` del test sin explicar nada— y el contraste
uno a uno contra el SQL.

Contrasté contra el SQL, uno a uno, **cinco de los 28** —los dos que motivaron
el rechazo (`v_pbi_proveedor_obra`, `v_pbi_albaranes_sin_facturar`) y otros tres
elegidos por ser los más fáciles de estropear: `fact_seguimiento_categoria`,
`v_pbi_cierre_resumen` y `retenciones.movimientos`—. Los cinco son ciertos, y uno
trae una corrección no trivial que nadie había pedido: `movimientos` pasa a
declarar la clave `(sentido, movimiento_id)` porque el identificador sale de
`p.ide` y de `c.ide` —dos secuencias distintas, `pag` y `cob`
(`retenciones/01_movimientos.sql:47-48, 97-98`)—, así que **solo es único dentro
de su sentido**. El barrido no encuentra coletillas, y el caso que motivó el
rechazo quedó así:

> «Una fila por (`obra_id`, `codigo_obra`, `proveedor_id`, `proveedor_nombre`,
> `proveedor_cif`, `anio`), que es su clave de negocio y son SEIS columnas, no
> tres. No basta con (obra, proveedor, ano): `proveedor_cif` sale del CIF que
> traía cada documento y NO depende de `proveedor_id`, así que dos facturas del
> mismo proveedor con CIF distinto dan DOS filas. Unir por tres columnas
> duplica.»

Eso no es satisfacer un test: es explicar la trampa que la review tardó tres
pasadas en aislar, y dejarla escrita donde el agente la va a leer.

**Los 28 se verificaron enteros**, uno a uno contra el SQL —19 de `mart` y
`cierre`, 9 de `compras` y `retenciones`— y **los 28 son ciertos**. El patrón de
la reescritura es homogéneo y honesto: traducir la palabra de negocio al nombre
de columna (`obra` → `obra_id`, `mes` → `anio_mes`, «renglón del cuadro» →
`concepto_cuadro`), sin inventar dimensiones, sin meter columnas redundantes para
pasar el test y sin prometer unicidad que el SQL no dé. Se comprobó además, con
las dos versiones del YAML parseadas y comparadas objeto a objeto, que **el único
campo que cambió es `grano`**: `columnas`, `clave_negocio`, `relaciones`,
`cardinalidad`, `descripcion`, `paso_etl` y `refresco` están intactos en los
cuatro ficheros. **Cero regresiones.**

Los dos defectos de arriba no son granos reescritos mal: son fichas que el
barrido de copias no visitó.

## El detector elegido — es el correcto, no el cómodo

Descartó dos variantes y las razones son buenas:

- **Casar la enumeración del grano con la clave** exige emparejar conceptos de
  negocio («obra», «mes») con nombres de columna (`obra_id`, `anio_mes`): un
  emparejamiento difuso que **marcaría de más**.
- **Contar dimensiones** no delata nada: las seis columnas de
  `v_pbi_proveedor_obra` son tres conceptos.
- **Exigir que los nombres aparezcan** es exacto, no admite interpretación y
  tiene un efecto colateral bueno: el grano pasa a decir por qué columnas hay que
  unir.

Su límite, dicho para que conste: es una comprobación **textual**, así que se
puede satisfacer mencionando la columna sin arreglar la contradicción. Por eso
las 28 correcciones necesitaban revisión humana, y por eso la hice.

## La derivación del congelado — correcta, y con control en los dos sentidos

Es la afirmación más fuerte de la tanda y es cierta en semántica PostgreSQL:
`CURRENT_DATE` dentro de un `CREATE TABLE … AS SELECT` se evalúa **una vez**, al
construir, y el valor queda materializado; dentro de una vista se reevalúa en
cada consulta. El detector solo marca columnas de **tablas**
(`test_f006_fichas.py:1843-1868`) y su control lo ancla en los dos sentidos:
exige que `retenciones` dé exactamente `{vencida_sin_liquidar,
dias_desde_vencimiento}` y que `compras.dias_desde_albaran` —que es de una
vista— **no** aparezca.

La herencia también es correcta: `v_pbi_retenciones_vencidas.antiguedad` se
calcula con un `CASE` sobre `dias_desde_vencimiento`
(`retenciones/02_views.sql:139-145`), que viene congelada de la tabla; y un
`SUM(importe) FILTER (WHERE vencida_sin_liquidar)` es tan de la fecha del build
como la marca, porque el conjunto de filas se decidió entonces.

Lo probé: quité la palabra «build» del significado de `antiguedad` y
`test_f006_r2_toda_columna_congelada_lo_advierte` se puso en rojo.

Y el aviso **llega completo y no se sobrepropaga**: se recorrieron las columnas
que dependen de `vencida_sin_liquidar` o `dias_desde_vencimiento` en el SQL
—`movimientos`, las dos de `vivas`, las cuatro de `vencidas` incluida
`antiguedad`, `entidad.importe_vencido`/`num_vencidas`,
`obra.vencido_proveedores`/`vencido_cliente` y
`resumen.importe_vencido`/`num_vencidas`— y **todas lo declaran**; mientras que
`compras.dias_desde_albaran`, que vive en un `CREATE VIEW` y por tanto se
recalcula, **no** lo dice, que es lo correcto.

**Dónde puede quedarse corto** (deuda, no defecto): el conjunto de columnas
congeladas se agrupa **por esquema**, no por objeto, y la herencia es de
profundidad uno —una vista que referenciara una columna heredada de otra vista no
se marcaría—. Hoy no existe ninguna cadena así, y agrupar por esquema peca de
conservador, que es el lado bueno del error.

## Lo demás que declaraba

| Punto | Verificado |
|---|---|
| **P12 de la batería** | Corregido, y bien: «no generaliza la regla: en `compras.v_pbi_contrato_consumo` el pendiente se suma sin filtrar, así que allí las NOTA también cuentan» |
| **Vía (a), tablas agregadas** | **Probado por mí**: puse `num_partidas` en `suma` y falla `test_f006_r7_la_agregacion_de_las_tablas_agregadas_casa_con_el_sql`. Antes no lo cubría nada |
| **PK inline** | Corregido: `pk_declarada` devuelve ahora `['fact_id']` y `['cierre_id']` donde antes daba `None`, y sigue dando `None` para el CTAS sin PK. Los tres motivos de skip falsos, resueltos |
| **El aserto que impedía crecer** | Sustituido por el invariante de prefijo (`proyectadas[:18] == COLUMNAS_V_DICCIONARIO[:18]`), que es el correcto: permite añadir al final, que es lo único que el contrato declara compatible |
| **Los dos docstrings** | Corregidos. El del `rollback` distingue ahora que el `commit` sí se ejecutaba y solo el `rollback` no |
| **Vía (b), diferida a T26** | El SQL hace lo que dice (ver abajo) y el reparto es sensato: T26 construye el comando, T27 lo ejecuta contra la base como verificación MANUAL (humano), coherente con la regla de que ningún agente abre conexión |

---

## Rigor y comprobaciones de siempre

- **1359 tests + 40 saltados**, ejecutados por mí; cobertura **98,9 % de 718
  líneas**. Los 40 saltados siguen siendo los mismos cinco grupos ya auditados en
  la cuarta pasada, ahora con los tres motivos falsos de PK corregidos.
- **Mutación verificada de forma independiente**: alcance **2324 líneas** y
  **161 mutantes** recalculados; coinciden con `progress/mutacion_F-006.md`; cero
  supervivientes. (No varía respecto a la tanda anterior porque estos cuatro
  commits tocan YAML, tests y specs, no código de producción.)
- **Nada prohibido**: el diff no toca `main.py`, `settings.py`, `grants.py`,
  `postgres_client.py`, `infra/**` ni ningún SQL de negocio; ni un `GRANT`,
  `REVOKE`, firewall o Azure; ninguna conexión a la base. **Sin `push`**: no
  existe rama remota de la feature.
- Trinquete coherente: 49 fichas + 53 pendientes = 102 objetos, `PENDIENTES_MAX`
  = 53.
- Árbol limpio; mis experimentos se hicieron en worktrees aislados ya eliminados.

### Checkpoints (quinta pasada)

**C1** `[x]` · **C2** `[x]` · **C3** `[x]` · **C3 bis** N/A · **C4** `[ ]` —dos
fichas siguen declarando algo que el SQL desmiente (defectos 1 y 2): una clave
que no identifica una fila y una nulidad imposible. Todo lo demás de C4 está
cumplido, y el resto del diccionario —49 fichas, 593 columnas— sí cuadra— ·
**C4 bis** `[x]` · **C4 ter** N/A · **C5** N/A parcial (20 de 42 tareas, el
alcance encargado).

---

# CUARTA PASADA · 2026-08-20 — cierre de los defectos del bloque E y F

> Commits revisados: `efbef48`..`c20c933` (cinco). Mismo alcance: T15–T18,
> T20 y T21.

## Veredicto de la cuarta pasada

**RECHAZADO**, por poco y por una sola razón: **tres de los defectos dados por
cerrados lo están en el campo que la review señaló y siguen abiertos en el campo
vecino de la misma ficha**, y dos de ellos son afirmaciones falsas en el `grano`,
que es lo primero que un agente lee.

Todo lo demás está bien, y es mucho: el contrato con `mcp-bbdd` quedó resuelto
como debía, el mecanismo derivable funciona y no marca de más, y los 40 tests
saltados —el punto por el que había que empezar— tienen explicación buena.

**Rectifico además mi propia verificación**: di por cerrados los defectos (a),
(e) y el del congelado tras comprobar `clave_negocio` y la ficha de la columna.
No miré el `grano` ni las dos vistas derivadas, y ahí seguían. La lección es del
proceso, no de una persona: **cuando se corrige una afirmación hay que buscar sus
copias en el mismo fichero**, porque esta es la tercera vez que el defecto
sobrevive en el campo de al lado —pasó con el ejemplo de `design.md`, con los
residuos de «mes anterior» y ahora con los granos—.

---

## Lo que hay que corregir

1. **El `grano` contradice a su propia `clave_negocio`, y el grano es el que
   induce el fan-out.** En `v_pbi_proveedor_obra` la clave pasó a las seis
   columnas del `GROUP BY` (`compras.yaml:710`) pero el `grano` sigue diciendo
   «Una fila por (obra, proveedor, ano)» (`:707-709`). Son incompatibles: si
   `proveedor_cif` no depende funcionalmente de `proveedor_id` —y no depende,
   sale de `entcif` del documento— entonces hay más de una fila por (obra,
   proveedor, año), que es justo el motivo por el que se amplió la clave. Quien
   lea el grano unirá por tres columnas y duplicará. Idéntico en
   `v_pbi_partida_coste`: clave de cinco (`:904`), grano «Una fila por (obra,
   partida)» (`:900-901`).
2. **La regla falsa de la NOTA sobrevive en el `grano` de la vista vecina.** La
   corrección quedó bien en la ficha de `tipo_documento` (`:329-333`) y en la de
   `importe_albaranado_sin_facturar` (`:659-666`), pero el `grano` de
   `v_pbi_albaranes_sin_facturar` (`:803-806`) mantiene la formulación general:
   «las notas de cargo suman en el consumido del contrato pero no cuentan como
   pendiente de facturar». La segunda mitad es **exactamente lo que es falso** en
   `v_pbi_contrato_consumo`, cuyo `SUM(pendiente_facturar)` no filtra por tipo
   (`compras/03_views.sql:42`). El test que fija la corrección no mira ese campo.
3. **El aviso de congelado no llega a las dos vistas donde aterriza la
   pregunta.** En la tabla base quedó muy bien explicado, pero
   `v_pbi_retenciones_vivas` (`retenciones.yaml:477-482`) sigue diciendo «Si la
   fecha prevista ya paso» y «Dias desde el vencimiento», y
   `v_pbi_retenciones_vencidas` (`:541-543`) «Cuantos dias lleva vencido», las
   dos sin advertir de que ambas columnas se calcularon con `CURRENT_DATE` **en
   el build** (`retenciones/01_movimientos.sql:21, 77-79, 120-122`) y llevan
   parados los días que lleve sin reconstruirse el esquema. Son las vistas que
   responden P13 de la batería, y mi informe anterior las citó por número de
   línea.

### Menores (arreglar al pasar)

4. **El detector de PK tiene un punto ciego y su mensaje de skip miente.**
   `pk_declarada` reconoce `ALTER TABLE … ADD PRIMARY KEY (col)` —por eso cubre
   de verdad 8 de las 12 tablas— pero **no la forma inline** `col TIPO PRIMARY
   KEY`. Llamé a la función: devuelve `None` para `mart.fact_seguimiento_mensual`,
   `mart.fact_seguimiento_categoria` y `cierre.fact_cierre_mensual`, cuyos DDL la
   declaran en la propia columna. El test las salta diciendo «el DDL no declara
   clave primaria para este objeto», **que es falso**. Hoy no cuesta nada —esas
   tres habrían saltado igual por la rama «la PK es una clave sustituta»—, pero
   el día que alguien declare una PK de negocio inline, el test la saltará en
   silencio. Su control prueba positivo y negativo, pero solo de la forma `ALTER
   TABLE`, así que no ve el hueco.
5. **Un aserto rompe el crecimiento que el propio contrato declara compatible.**
   `test_f006_publicacion.py:989` fija `proyectadas[-1] == "motivo_no_consumo"`.
   Añadir una columna **al final** —lo único que la cabecera del DDL permite sin
   romper a nadie— pone ese aserto en rojo aunque se actualicen SQL, `design.md`
   y la lista. El invariante correcto es el prefijo de 18, que ya está en la
   línea siguiente.
6. **Dos docstrings afirman de más.** El del `rollback` dice que «el `commit` y
   el `rollback` reales no se ejecutaban en ningún test»: lo del `rollback` es
   cierto y está demostrado, pero el `commit` **sí** se ejecutaba
   (`test_f005_conexion.py` usa el `connection()` real). Y el de `apply_grants`
   es un test **estructural** —comprueba `depends_on`—, no conductual: protege
   del escenario que nombra, no de un cambio en la lógica de salto del
   orquestador. Es la misma clase de sobreventa que ya se corrigió dos veces.
7. Tres medidas más de la clase «`SUM(…) FILTER` sin `COALESCE`, NULL no
   declarado» quedan sin `nulo_significa` —`v_pbi_retencion_resumen.saldo_vivo`,
   `.importe_liquidado`, `.importe_vencido`— mientras sus hermanas del mismo
   fichero sí lo declaran; `compras.yaml:662-664` dice «es el único agregado de
   la vista que se suma SIN filtrar por tipo», y no lo es (`importe_facturado`
   tampoco filtra, y la propia ficha lo admite en `:646-652`); y
   `fact_compras_linea.proveedor_id` (`:91-93`) no declara `nulo_significa`
   pese a salir de un `NULLIF(entide, 0)`, siendo la tabla a la que la ficha
   vecina te manda «para no perder las líneas sin proveedor».

### El mecanismo: dos puntos ciegos que explican por qué pasan estos tres

- **El contraste `clave_negocio` ⊆ `GROUP BY` es de subconjunto, no de
  igualdad** (`test_f006_fichas.py:1399`). Por eso una clave corta lo pasaba
  antes y por eso hoy nada impide que el `grano` diga menos que la clave.
- **Nada contrasta el `grano` con la `clave_negocio`**, y buena parte de eso
  **sí es derivable**: cuando el `grano` enumera columnas entre paréntesis
  —«Una fila por (obra, proveedor, ano)»—, esa enumeración debería casar con la
  clave declarada, o declararse explícitamente como resumen. Es un test corto y
  habría cazado los defectos 1 y 2 de esta lista.
- Además, el contraste de agregación excluye `TABLAS_CON_DDL_EXPLICITO`
  (`:1263`), así que `mart.fact_seguimiento_categoria.num_partidas` —un
  `COUNT(DISTINCT)`— hoy está bien pero nada lo fija.

---

## Lo que sí está cerrado, verificado

### Los 40 saltados — explicados, y ninguno esquiva nada que antes corriera

| Nº | Motivo impreso | Veredicto |
|---|---|---|
| 2 | «se crea con SQL dinámico; tiene su propio test» | **legítimo**, ya validado |
| 3 | «la proyección no se deja leer» (agregación) | **legítimo** |
| 3 | ídem (`GROUP BY`) | **legítimo** |
| 28 | «el `GROUP BY` no es derivable» | **legítimo** |
| 4 | «el DDL no declara clave primaria» | **motivo falso en 3 de los 4** (defecto 4) |

Los tres tests son **nuevos de esta tanda**, parametrizados sobre las 49 fichas,
y saltan donde no aplican; lo que ya existía sigue ejecutándose entero. Los 3+3
de «proyección ilegible» son los tres catálogos `SELECT * FROM (VALUES …)`, y
**comprobé que los tres siguen cubiertos** por el test de proyección exacta, que
pasa para los tres. Los 28 del `GROUP BY` son legítimos: el test corre sobre las
**seis** vistas con `GROUP BY` directo y salta donde la agregación vive en CTEs
bajo un `UNION`; su test de control ancla el alcance en los dos sentidos —exige
que tres objetos SÍ se lean y que uno con `UNION` NO—, que es lo que impide que
se degrade en silencio.

### El contrato (defecto 6) — cerrado y bien resuelto

`motivo_no_consumo` se queda —el MCP necesita el porqué— pero **al final**: las
18 columnas del contrato conservan su posición. Extraje el orden de las dos
fuentes y **coinciden posición por posición**. `design.md` §4.2 se enmendó con
nota fechada, y también su bloque SQL, no solo la nota.

Y los tests **fijan posiciones, no presencia**, probado en worktree aislado:

| Experimento | Resultado |
|---|---|
| Intercambiar `d.tipo` y `d.capa` | **detectado**: `At index 2 diff` |
| Mover `motivo_no_consumo` al medio | **detectado**: `At index 5 diff` |

Los cuatro menores del contrato también: los denominadores de `cobertura_cols` y
`n_columnas` quedan explicados en dos `COMMENT ON COLUMN` —en la base, que es
donde el MCP los lee—; el DDL dice ahora que la identidad es `hash_fuente` y no
`version`; y las cifras viejas de T19 están corregidas a 49 y 12.

### El mecanismo — funciona y no marca de más

- **`agregacion` contra la función del SQL**: corre en **34 de 37** casos, y su
  criterio es más fino que el que yo habría escrito: distingue
  `COUNT(DISTINCT …)` de `COUNT(*)` sobre particiones disjuntas, que sí es
  aditivo. Lo comprobé por la vía contraria: un detector tosco («todo COUNT es
  no sumable») **habría marcado nueve columnas de más**; el suyo no marca
  ninguna.
- **Los cinco `COUNT(DISTINCT)` son ciertos**: los tres que encontré a mano más
  `num_entidades` y `num_obras` de `v_pbi_retencion_resumen`
  (`retenciones/02_views.sql:161-162`), que **no vi**. Es el argumento a favor de
  derivar en vez de revisar a ojo.

### Las fichas — cinco de los seis graves, cerrados

Cerrados y verificados contra el SQL: los tres contadores a `no_sumable`; los
negativos imposibles de `v_pbi_albaranes_sin_facturar` («la vista filtra `> 0`,
así que las líneas sobrefacturadas **no aparecen**»); las claves de las dos
vistas fuente de `retenciones`, resueltas **mejor de lo pedido** —`clave_negocio:
[]` con el `grano` advirtiendo que el par es «exactamente el que produce el
fan-out de `R-RETENCION-NO-JOIN-LINEAS`, y por eso esta vista se agrega SIEMPRE
por documento antes de usarse»—; los cuatro medios; y los once menores 12-20.

**Sobre la clave vacía declarada**: es mejor que una clave inventada y **no abre
puerta trasera**. El validador la admite **solo fuera de la superficie de
consumo** (`domain/diccionario.py:499-505`), y salir de ella cuesta escribir un
`motivo_no_consumo` con mínimo de longitud, visible en el diff. Una clave
inventada manda al agente a un JOIN que multiplica; un hueco declarado le dice
que esa vista no deduplica.

**Sin regresión en `mart` ni `cierre`**: el diff de esta tanda toca solo
`compras.yaml` y `retenciones.yaml`; los otros tres YAML son idénticos byte a
byte, y sus granos, claves y cardinalidades se revalidaron igualmente.

### Los dos tests sin fase RED — justificados, y el hueco existía

El del `rollback` cubre una ruta que **ningún test del repositorio ejecutaba**:
confirmado empíricamente instrumentando `connection()` en una copia del commit
anterior y corriendo su suite entera —la marca de `commit` se crea, la de
`rollback` no—. El test nuevo pisa la ruta real: solo sustituye la apertura del
socket. Y `apply_grants` sigue corriendo con la publicación fallida, verificado
montando el pipeline (`build_mart SUCCESS / publicar_diccionario FAILED /
apply_grants SUCCESS`).

### `CLAUDE.md` — corregido con precisión

Pasa de «hay una puerta que lo exige» a «la puerta exige **ficha o pendiente
declarado**: se puede aplazar la ficha, pero no ignorarla, y la lista de
pendientes solo baja». Es exactamente lo que la puerta hace.

### La acotación de lo no derivable — honesta, y dos vías que aporto

Que la clave sea *demasiado corta* exige dependencias funcionales que no siempre
están en el texto: `proveedor_cif` no depende de `proveedor_id` —sale del CIF que
traía cada documento— y aun así se escribe igual que una columna que sí
dependiera. Forzar la igualdad con el `GROUP BY` marcaría fichas correctas
—`mart.fact_seguimiento_categoria` agrupa por nueve columnas de las que cinco se
derivan de otras dos—: **la acotación es honesta**. Dos vías que no aparecen en
su informe:

> **Corrección del 2026-08-20 (sexta pasada).** Este párrafo decía «`codigo_obra`
> depende de `obra_id` y omitirla es correcto». **Era falso**, y el error es mío:
> en `retenciones.movimientos` las dos salen de cascadas distintas
> (`01_movimientos.sql:61-64`) y en `compras.v_pbi_partida_coste` la ficha lo
> dice con esas palabras. El implementer tomó la frase de aquí como fundamento
> del límite del test y su propia corrección la desmintió. El límite sigue siendo
> real —lo es por `proveedor_cif`—, pero el ejemplo que lo ilustraba era
> justamente un caso en el que la dependencia **no** existe. Queda corregido
> arriba y en `tests/test_f006_fichas.py`.

- **Derivable hoy y gratis**: las tablas agregadas que se llenan con
  `INSERT … SELECT … GROUP BY` —`mart.fact_seguimiento_categoria`,
  `sql/mart/03_agg_categoria.sql`— tienen su `GROUP BY` en el repositorio, y
  ningún mecanismo comprueba su clave: el de `GROUP BY` solo mira vistas y el de
  PK las salta por clave sustituta. Es el mismo parser sobre otra sentencia.
- **La definitiva**: que `check-diccionario` (R28, T27) incluya una consulta de
  unicidad por objeto —`SELECT count(*) - count(DISTINCT (clave)) FROM …`—.
  Liquida el problema entero, dependencias funcionales incluidas, con una
  consulta barata por objeto. Conviene declararlo como parte de T27 antes de que
  se escriba.

---

## Rigor y comprobaciones de siempre

- **1310 tests + 40 saltados**, ejecutados por mí; cobertura **98,9 %**.
- **Mutación verificada de forma independiente**: recalculé alcance (**2324
  líneas**) y mutantes (**161**); coinciden con `progress/mutacion_F-006.md`;
  cero supervivientes.
- **Nada prohibido**: el diff no toca `main.py`, `settings.py`, `grants.py`,
  `infra/**` ni ningún SQL de negocio; ni un `GRANT`, `REVOKE`, firewall o Azure;
  ninguna conexión a la base. **Sin `push`**: no existe rama remota de la feature.
- `ruff` se queda en 161 avisos, los mismos que antes: no añade deuda.
- Trinquete coherente: 49 fichas + 53 pendientes = 102 objetos, y
  `PENDIENTES_MAX` vale 53.

### Checkpoints (cuarta pasada)

**C1** `[x]` · **C2** `[x]` · **C3** `[x]` · **C3 bis** N/A · **C4** `[ ]` —tres
fichas siguen declarando en su `grano` algo que el SQL desmiente (defectos 1-3);
todo lo demás de C4 está cumplido— · **C4 bis** `[x]` · **C4 ter** N/A · **C5**
N/A parcial (20 de 42 tareas, el alcance encargado).

---

# TERCERA PASADA · 2026-08-20 — bloque E y bloque F parcial

> Commits revisados: `5b5e8ff`..`206eae3` (doce: cinco de arrastres de la
> segunda pasada y siete del trabajo nuevo). Alcance: **T15–T18** (publicación
> en `_meta`) y **T20, T21** (fichas de `compras` y `retenciones`).

## Veredicto de la tercera pasada

**RECHAZADO.**

El **bloque E está casi bien hecho** —el contrato cumple sus tres invariantes y
sus tres tablas son idénticas a `design.md` §4.1, aunque **la vista se desvía**
(defecto 6)—, el trinquete
reformulado **aguanta las cinco vías de burla** que le probé, y los cinco
arrastres de la segunda pasada están cerrados. Nada de eso salva la entrega:
**las fichas nuevas de `compras` y `retenciones` mienten en cinco puntos que
producen números falsos**, y el criterio de esta feature es explícito —una ficha
que miente es motivo de rechazo aunque todo lo demás esté bien—.

Lo que más pesa: la ficha de `compras.albaranes` enuncia como regla general una
de las trampas que esta feature existe para contar bien —«la NOTA suma en el
consumido pero no en el pendiente»— y **es falsa en una de las dos vistas donde
se aplica**. Tres contadores `COUNT(DISTINCT …)` van marcados `agregacion:
suma`, que es justo el campo que el MCP traduce a «esta columna se suma». Y dos
fichas de `retenciones` declaran una clave de negocio que **contradice su propio
grano** y que es exactamente el par que produce el fan-out que el fichero
declara como la regla que más dinero ha costado.

No es un problema de volumen ni de descuido puntual: **la puerta no contrasta
con el SQL ni las claves de negocio ni el campo `agregacion`**, y son los dos
huecos que ya señalé en la segunda pasada (experimentos E6 y E11). Entonces no
habían hecho daño porque `mart` y `cierre` tienen claves simples; `compras` y
`retenciones` las tienen compuestas, y ahí es donde se ha caído.

---

## Lo que hay que corregir

### Graves · afirmaciones que producen números falsos

1. **`compras.yaml:326-328` — la regla de la NOTA es falsa en `v_pbi_contrato_consumo`.**
   La ficha de `albaranes.tipo_documento` dice, sin acotar: «Solo ALBARAN y
   PROFORMA cuentan como pendiente de facturar; la NOTA suma en el consumido
   pero no en el pendiente». Es cierto en `v_pbi_albaranes_sin_facturar`
   (`03_views.sql:172`) y **falso** en `v_pbi_contrato_consumo`: en la CTE
   `alb_pivot`, las tres primeras medidas llevan `FILTER` por tipo y
   `SUM(pendiente_facturar)` **no lo lleva** (`03_views.sql:39-42`), así que
   `importe_albaranado_sin_facturar` incluye NOTA y OTRO. Ni esa ficha ni la de
   la columna (`compras.yaml:652-657`) lo dicen.
2. **`compras.yaml:741,744,747` — tres `COUNT(DISTINCT …)` declarados sumables.**
   `num_facturas`, `num_albaranes` y `num_contratos` llevan `agregacion: suma` y
   son `COUNT(DISTINCT documento_id)` / `COUNT(DISTINCT contrato_id)`
   (`03_views.sql:126-130`). Una factura repartida entre tres obras aparece en
   tres filas con valor 1: sumarlas da tres facturas donde hay una. El
   vocabulario cerrado ya tiene `no_sumable` para esto.
3. **`retenciones.yaml:639` y `:667` — clave de negocio que contradice su propio
   grano.** `v_src_lineas_compra` es `SELECT docide, obride FROM raw.dcfpro`
   (`retenciones/00_setup.sql:101-103`): **una fila por línea**, como dice su
   propio `grano`. La `clave_negocio: [docide, obride]` declarada se repite
   tantas veces como líneas tenga la factura contra esa obra. Es el par que
   produce el fan-out de `R-RETENCION-NO-JOIN-LINEAS`, ofrecido como clave. Lo
   mismo en `v_src_lineas_venta`, hoy inocuo porque la vista está vacía, pero la
   ficha describe la forma que tendrá cuando se ingiera `dvfpro`.
4. **`compras.yaml:827-831` — anuncia negativos que la vista no puede devolver.**
   `v_pbi_albaranes_sin_facturar.importe_pendiente_facturar` dice que «NEGATIVO
   significa que se facturó de más, y el signo se conserva a propósito». La
   vista filtra `WHERE l.importe_pendiente_facturar > 0` (`03_views.sql:171`):
   ahí no hay negativos. El texto es correcto en `albaran_lineas`
   (`compras.yaml:436-441`), de donde parece copiado. Quien pregunte por
   sobrefacturación mirará aquí y concluirá que no existe.
5. **`compras.yaml:699` — clave de negocio reducida en `v_pbi_proveedor_obra`.**
   Declara `[obra_id, proveedor_id, anio]`; el `GROUP BY` real tiene seis
   columnas (`03_views.sql:133-134`), y `proveedor_cif` **no** depende de
   `proveedor_id`: sale del CIF del documento, como la propia ficha admite en
   `:716`. Dos facturas del mismo proveedor con `entcif` distinto dan dos filas
   para la clave declarada.

6. **`sql/ddl/01_diccionario.sql:118` — la vista del contrato se desvía de la
   spec, y de la forma que el propio fichero prohíbe.** `_meta.v_diccionario`
   proyecta **19 columnas**; `design.md` §4.2 especifica **18**. La añadida es
   `motivo_no_consumo`, y no está al final: va **en posición 6**, entre
   `consumo_recomendado` y `descripcion`. La cabecera del mismo fichero, cuatro
   líneas más arriba (`:10-16`), dice: «QUE SE PUEDE CAMBIAR SIN ROMPER A NADIE:
   añadir columnas **AL FINAL**… QUE NO: quitar o **reordenar** columnas de la
   vista». La columna es una buena idea —el MCP necesita el porqué de un objeto
   no recomendado—, pero esta es **la mitad del contrato que `mcp-bbdd` va a
   consultar de verdad**, y quien implemente contra la spec y desempaquete por
   posición se encontrará los campos corridos a partir del sexto. `design.md`
   §4.2 **no se enmendó**, y en esta misma tanda sí se enmendaron sus recuentos,
   así que la ocasión estaba. **Decidir ahora**: mover la columna al final o
   enmendar §4.2. Dejarlo como está, no.
7. **La vista es la única de las cuatro estructuras sin test que fije sus
   columnas.** Las tres tablas tienen contraste exacto y parametrizado
   (`tests/test_f006_publicacion.py:157`); la vista solo tiene una comprobación
   de presencia por subcadena de 15 de sus 19 nombres (`:190`), que además omite
   justo `tipo`, `capa`, `consumo_recomendado` y `motivo_no_consumo`. Rigor
   asimétrico en la pieza más expuesta: falta el test con la lista completa **y
   ordenada**.

### Medias

8. **`compras.yaml:712` — `nulo_significa` imposible y, peor, un filtro no
   documentado.** La vista lleva `WHERE proveedor_id IS NOT NULL`
   (`03_views.sql:132`): la fila que la ficha describe no existe, y **las líneas
   sin proveedor desaparecen de la vista** sin que ninguna ficha lo advierta. La
   pérdida silenciosa de `obra_id IS NULL` sí está protegida (`:705-708`); esta
   es la misma familia, contada a medias.
9. **`retenciones.yaml:72` — `tipo_id.nulo_significa` imposible.** Las dos ramas
   filtran `WHERE COALESCE(retide, 0) <> 0` (`01_movimientos.sql:89,131`): un
   efecto sin tipo no entra en la tabla. Quien busque `WHERE tipo_id IS NULL`
   obtendrá cero filas y concluirá que no hay efectos sin tipo.
10. **Ocho medidas que devuelven NULL y no lo declaran.** Los cuatro importes de
   `v_pbi_proveedor_obra` (`compras.yaml:721-738`) y los cuatro de
   `v_pbi_partida_coste` (`:885-901`) son `SUM(…) FILTER (…)` **sin
   `COALESCE`** (`03_views.sql:118-125`, `:188-195`). El contraste lo delata:
   `v_pbi_contrato_consumo` sí envuelve en `COALESCE(...,0)` (`:77-82`) y por eso
   allí no hace falta declararlo. `WHERE facturado > 0` pierde filas en silencio.
11. **`retenciones.yaml:145-154` (y sus copias en `:466-471`, `:530-532`) —
   `vencida_sin_liquidar` y `dias_desde_vencimiento` están congelados.**
   `movimientos` es un `CREATE TABLE AS` (`01_movimientos.sql:21`) y ambas se
   calculan con `CURRENT_DATE` **en el build** (`:77-79`, `:120-122`). El texto
   («días transcurridos desde la fecha prevista», «la fecha prevista ya pasó»)
   se lee como *hoy*. En un esquema de refresco manual **cuya frescura ni
   siquiera es consultable por SQL**, la lista de vencidas puede llevar semanas
   parada y nadie puede saber cuánto. Hay que decir que para vencimiento a fecha
   de hoy se recalcula sobre `fecha_prevista_devolucion`.

### Menores (arreglar al pasar, no bloquean por sí solos)

12. `compras.yaml:45` — `(tipo_doc, linea_id)` es correcta para los seis tipos
    nombrados, pero `OTRO` es alcanzable desde dos ramas del UNION
    (`00_setup.sql:40` y `:43`, `tip=14` y `tip=15` con serie desconocida), así
    que ahí vuelve a colisionar. Basta con decirlo en la ficha.
13. `compras.yaml:863` — `v_pbi_partida_coste` declara `[obra_id, partida_id]` y
    el `GROUP BY` incluye `codigo_obra`, que se resuelve con una cadena
    `COALESCE` distinta de `obra_id` (`02_fact_linea.sql:52-53` y `:83-84`).
14. `compras.yaml:77-81` — la cascada de `obra_id` omite el respaldo por
    contrato: el SQL es `COALESCE(l.obra_id, ctr.obra_id)` (`02_fact_linea.sql:52`).
15. `compras.yaml:799-803` — `contrato_id` sale solo de la cabecera y
    `codigo_contrato` de `COALESCE(a.contrato_id, l.contrato_id_linea)`
    (`03_views.sql:169-170`): pueden salir juntos nulo e informado.
16. `retenciones.yaml:344-347` — invita a cuadrar euros contra
    `sin_obra_asignada`, que es un `COUNT`, no un importe (`02_views.sql:170`).
17. `retenciones.yaml:117-122` — `num_obras_documento` es **siempre 0** en
    sentido CLIENTE, porque se alimenta de la vista vacía; se describe como «lo
    que explica que la obra esté vacía», y para CLIENTE nunca explica nada.
18. `retenciones.yaml:168-175` — la relación a `compras.facturas` solo casa en
    sentido PROVEEDOR; la ficha gemela de `v_pbi_retencion_entidad` (`:326-331`)
    sí lo acota, esta no.
19. `retenciones.yaml:607-610` dice que las dos lecturas del saldo «no hay que
    compararlas entre sí» cuando el SQL dice lo contrario (`02_views.sql:19-20`):
    la divergencia **es** el diagnóstico.
20. `compras.yaml:640-644` y `:951-954`, `:971-975`: `importe_facturado` suma sin
    filtrar tipo; `fn_serie` devuelve cadena vacía, no NULL, y su ejemplo no es
    el formato real de Sigrid (`00_setup.sql:24-25`).
21. `diccionario_sql.py:38-40` justifica `DELETE` frente a `TRUNCATE` diciendo
    que «`TRUNCATE` no es transaccional de la misma forma en todos los
    escenarios». En PostgreSQL `TRUNCATE` **sí** es transaccional; la razón
    buena es que toma un `ACCESS EXCLUSIVE` que bloquea a los lectores, que es
    justo lo que aquí se quiere evitar. La decisión es correcta; el motivo
    escrito, no.
22. **`CLAUDE.md` promete más de lo que la puerta hace.** Dice que «quien añade o
    cambia un objeto publicado actualiza su ficha en el mismo trabajo: hay una
    puerta en `init.sh` que lo exige». Lo comprobé (**experimento E14**): publicar
    una vista nueva sin ficha, declararla en `pendientes` y subir el tope **pasa
    la puerta de cobertura**; lo único que salta es, de rebote, el test que
    cuenta objetos contra `design.md`. Lo que la puerta exige es «ficha **o**
    pendiente declarado». Rebajar la frase o cerrar el hueco.

23. **Falta el test de que `apply_grants` siga corriendo cuando
    `publicar_diccionario` falla.** Hoy es cierto porque
    `ApplyGrantsStep.depends_on == ["build_mart"]` y el orquestador solo salta
    un paso si falló una dependencia **declarada**. Pero nada lo fija: el día
    que alguien añada `"publicar_diccionario"` a esas dependencias «para que
    quede ordenado», una noche con el diccionario inválido dejaría al MCP sin
    `GRANT` — que es exactamente el fallo que R20 existe para evitar. Es un test
    de una línea.
24. **`cobertura_cols` y `n_columnas` no comparten denominador.** `n_columnas`
    publica **593** (todas las fichas) y `cobertura_columnas` se mide solo sobre
    `consumo_recomendado: true` (**554**). Hoy ambos dan 100 % y no se nota,
    pero `n_columnas * cobertura_cols / 100` no es el número de columnas
    documentadas. Sin `COMMENT ON COLUMN` que lo aclare ni mención en la spec, un
    consumidor razonable los combinará.
25. **La atomicidad está probada estructuralmente, no conductualmente.** El
    doble sustituye `connection()` entera, así que el `commit`/`rollback` real
    de `postgres_client.py:332-334` no se ejecuta en ningún test del
    repositorio. Falta uno que compruebe que una excepción a mitad del `with`
    provoca `rollback()`.
26. **`version` es un `1` estático que nadie incrementa** (`00_global.yaml`). Si
    `mcp-bbdd` lo usa para invalidar caché, no invalidará nunca: la identidad
    real es `hash_fuente`, y eso solo está dicho en un comentario del SQL. DA-5
    decidió «número manual **más** hash»; el número está, pero conviene
    documentar en el DDL cuál de los dos manda.
27. **`progress/impl_F-006.md` da por buena una comprobación con cifras
    viejas**: la verificación manual de T19 habla de «37 filas en
    `_meta.diccionario` (25 fichas hoy)» cuando ya son **49** y **62**. Quien
    ejecute T19 verá un desajuste que no es un fallo.

### Y el mecanismo, que es lo que evita la próxima vez

Los cinco defectos graves los habría cazado la puerta si comprobara dos cosas
que hoy no comprueba, y que ya salieron en la segunda pasada (E6, E11):

- **Contrastar `clave_negocio` contra el SQL**: para las vistas, comparar con
  las columnas del `GROUP BY`; para las tablas, con la PK del DDL. Ambas son
  derivables con el parser que ya existe. Habría cazado los defectos 3, 5 y 11.
- **Contrastar `agregacion` con la función del alias**: `COUNT(DISTINCT …)` no
  puede ser `suma`. Habría cazado el defecto 2.

Mientras eso no exista, cada esquema con claves compuestas exige revisión
humana columna a columna, y eso no escala a los 45 objetos que quedan.

---

## Lo que sí está bien, verificado

### El contrato con `mcp-bbdd` (bloque E)

- **Las tres tablas, columna por columna iguales a `design.md` §4.1.** Extraje
  los nombres del DDL real y del diseño: **coinciden exactamente**, en el mismo
  orden, incluido el `CHECK (id = 1)` del singleton. Tienen además test de
  contraste exacto y parametrizado. **La vista es la excepción, y es el defecto
  6**: rectifico aquí mi propia comprobación inicial, que se quedó en §4.1.
- **Invariante del orden**: `build_pipeline_steps` compone `IngestRaw →
  LoadExcelAux → BuildStg → BuildMart → **PublicarDiccionario** → ApplyGrants`
  (`main.py`), con el motivo escrito en el propio código: `apply_grants` es una
  foto del instante, y publicar después dejaría las tres tablas nuevas sin
  `GRANT` para el rol del MCP.
- **Invariante del reemplazo**: `DELETE` + `INSERT`
  (`diccionario_sql.py:41-43`), y **ni un `DROP` ni un `TRUNCATE` ejecutable** en
  el DDL, en los constructores ni en el paso: las únicas apariciones de esas
  palabras son comentarios que explican por qué no se usan.
- **Reusa la conexión abierta** en vez de abrir una segunda contra el servidor
  compartido, y el comando suelto valida con los pasos nocturnos de la
  composición real, no con una lista escrita a mano.
- **R19 y R21 se cumplen y están bien probados**: si el diccionario no valida,
  el cliente ni siquiera se instancia, y los tests lo demuestran con un espía
  cuyo `connection()` **lanza excepción si alguien lo llama**, comprobando
  después que la lista de llamadas está vacía. El fallo termina en `FAILED` y
  `run-all` sale con código 1 sin tocar el build de datos.
- **El `hash_fuente` es reproducible de verdad**: ordena los ficheros, incluye
  el nombre de cada uno y **normaliza `\r\n` a `\n`** —el detalle que casi
  siempre se olvida y que haría que el mismo diccionario diera dos hashes según
  el puesto—, con tests para las cuatro propiedades.
- **El test de las 49 fichas prueba lo que dice**: carga el diccionario real de
  `config/diccionario/`, no una maqueta; el cliente es el de producción con solo
  `connection` sustituida; y las 62 filas están **derivadas** (49 objetos + 12
  reglas + 1 publicación), no cableadas. El doble registra el orden real de las
  sentencias, y con él se comprueba que los `DELETE` preceden a los `INSERT` y
  que todo cae dentro de una única transacción.

### El trinquete reformulado

Cambió de «cada revisión cabe en la anterior» a «ningún objeto que tuvo ficha
vuelve a `pendientes`», y el motivo es legítimo: el DDL del contrato añadió
cuatro objetos nuevos a `_meta` y la comparación cruda los daba por regresión.
**Le probé cinco vías y ninguna pasa**: desdocumentar una ficha vieja y subir el
tope (**E1**); hacerlo con una ficha estrenada en este mismo commit (**E12**,
nuevo); **commitear** el retroceso para que el árbol coincida con HEAD (**E9**);
renombrar el fichero de esquema y borrar la ficha en el mismo commit (**E13**,
nuevo); y la ficha esquelética de `x` (**E2**). Además siguen cazados el resto de
experimentos de las pasadas anteriores (**E3**, columna de otra vista del mismo
fichero SQL). El falso positivo se arregló **sin** abrir un falso negativo en lo
que importa. El único hueco que queda es el consciente y acotado del defecto 20.

### Los arrastres de la segunda pasada

Los cinco, cerrados y verificados: el `porque` de `v_pbi_planif_vs_real` ahora
explica que la vista colapsó `categoria` dentro de `concepto_cuadro` y que no
hay clave directa; el de `v_pbi_cp_tipologia` pasa a `(obra_id, anio)` diciendo
que el ámbito lo fija el SQL; `final_pct` da el mapa real de divisores; queda
**un** «mes anterior» en todo `cierre.yaml`, y es el legítimo; y el informe
rebajó su afirmación sobre granos y claves. Hay además un test que exige que las
columnas citadas en un `porque` existan.

### Los tres hallazgos que el implementer se apunta

- **Las tablas `CREATE TABLE AS SELECT` no las comprobaba nadie**: cierto, y
  ahora el test de proyección exacta las cubre explícitamente
  (`test_f006_fichas.py:544`). Es lo que hace que las 162 columnas de `compras` y
  las 99 de `retenciones` estén verificadas nombre a nombre — y, en efecto,
  **no hay ni una inventada ni una omitida** en los 24 objetos nuevos.
- **El aviso de frescura estaba en la cabecera del YAML, que no se publica**:
  cierto y bien resuelto. `R-FRESCURA-MANUAL` lleva ahora dentro que
  `build-compras` y `build-retenciones` no registran paso y que de esos dos
  esquemas hay que **advertir que la antigüedad se desconoce, en vez de
  callarlo**.
- **Los dos `1:1` de retenciones que eran `N:N`**: corregidos; repasadas las
  nueve relaciones del fichero, todos los lados `1` prometen unicidad real.

### Rigor

- **1242 tests + 2 skipped**, ejecutados por mí. Los 2 skips son legítimos y
  están cubiertos: las dos vistas de `retenciones` creadas con SQL dinámico
  dentro de un `DO $$` tienen su propio test a mano
  (`test_f006_r26_las_vistas_dinamicas_de_retenciones`).
- **Cobertura 98,9 % de 718 líneas cambiadas.**
- **Mutación verificada de forma independiente**: recalculé alcance (**2313
  líneas**, ocho ficheros) y mutantes (**160**), y coinciden con
  `progress/mutacion_F-006.md`; cero supervivientes.
- **T19 bien diferida**: `MANUAL (humano)` con los comandos exactos y las tres
  consultas de comprobación, listada en `current.md`. Esto cierra la reserva que
  dejé en la primera pasada sobre C4.
- **Nada prohibido**: ni un `GRANT`, `REVOKE`, firewall ni Azure en el diff; las
  únicas apariciones de esas palabras son comentarios que explican el orden del
  pipeline. `grants.py` y `apply_grants_step.py`, intactos. Y la ausencia de
  conexiones no se dio por buena leyendo: se comprobó **relanzando la suite
  entera con los sockets parcheados para lanzar excepción** — 1242 passed, ni un
  socket abierto.
- **Riesgo residual honesto**: nada del bloque E se ha ejecutado nunca contra un
  PostgreSQL. La adaptación de tipos de psycopg (el `JSONB` como texto, los
  `list[str]` a `TEXT[]`), el `CHECK (id = 1)` y la propia sintaxis del DDL están
  sin probar. Está declarado y planificado como T19, no oculto.
- **`azure-apps/datamart_seg_anual.md` no menciona todavía las tres tablas ni la
  vista.** Está planificado como T37 (bloque J), así que es un aplazamiento
  deliberado; pero la regla de `CLAUDE.md` dice «en el mismo trabajo, no
  después», y el contrato con otro equipo es justo el caso que esa regla cubre.
  Conviene decidirlo explícitamente en vez de que se arrastre.
- Deuda menor nueva: **+2 avisos de `ruff`** (un `I001` en
  `tests/test_f006_publicacion.py` y el bloque de imports de `main.py`), cuando
  las tandas anteriores dejaban `ruff` limpio en lo propio.

### Checkpoints (tercera pasada)

- **C1** `[x]` — `init.sh` exit 0, 1242 tests + 2 skipped, ejecutado por mí.
- **C2** `[x]` — una `in_progress`, rama correcta, `current.md` al día.
- **C3** `[x]` — dominio sin infraestructura; el paso nuevo en `application/steps/`,
  los constructores SQL en `infrastructure/postgres/`, el DDL en `sql/ddl/` con
  su numeración. Cabeceras de ruta presentes. Deuda menor: +2 avisos de `ruff`.
- **C3 bis** — **N/A**: no se toca `docs/referencia/`.
- **C4** `[ ]` — **el checkbox que falta**: R2 exige que la ficha diga qué es una
  fila y qué la identifica, y cinco fichas nuevas declaran claves o reglas que el
  SQL desmiente (defectos 1-5). Los tests pasan; lo que no se cumple es el
  requisito. Las verificaciones `MANUAL (humano)` sí están listadas con su
  comando exacto.
- **C4 bis** `[x]` — fase RED por tarea; cobertura 98,9 % de 718 líneas;
  mutación **verificada de forma independiente** (2313 líneas, 160 mutantes,
  coinciden), cero supervivientes; sección «Evidencias» presente.
- **C4 ter** — **N/A**: no existe `harness/rutas_sensibles.json`.
- **C5** — **N/A parcial**: 20 de 42 tareas, que son el alcance encargado.

### Observación de coherencia

Las cuatro tablas y vistas nuevas de `_meta` entran en `pendientes` sin ficha:
es decir, **el diccionario se publica a sí mismo sin describirse**. Es coherente
con el trinquete y T24 lo recoge, pero conviene que no se cierre el bloque F sin
ello, porque el MCP verá esos cuatro objetos en el catálogo antes que su ficha.

---
---

# SEGUNDA PASADA · 2026-08-20

> Commits revisados: `5783cbc`..`7d9845b` (trece). Mismo alcance: **T3–T14**,
> bloques A a D.

## Veredicto de la segunda pasada

**APROBADO**, con cuatro correcciones de arrastre que deben entrar **antes de
que el bloque E publique el diccionario en `_meta`** (§«Lo que arrastra»).

Los **diez defectos están corregidos**, verificados uno a uno y no de palabra:
cada arreglo lo comprobé contra el SQL o reproduciendo el experimento que antes
pasaba en verde. En cinco casos se arregló **el mecanismo y no el caso**, y las
ampliaciones que eso destapó son **ciertas, no ruido**: las 4 relaciones de
fan-out nuevas y los 2 objetos extra de `R-IMPORTE-MES` los verifiqué contra el
SQL uno a uno. Las fichas **siguen siendo veraces tras 277 líneas de edición**:
332 columnas, 22 granos y 22 claves de negocio revalidados, sin una sola
regresión.

Apruebo aun quedando cuatro imprecisiones (una de ellas introducida al
corregir) porque son de **otra categoría** que las que motivaron el rechazo.
Aquellas publicaban un valor sin sentido (`cardinalidad: 61`), inducían un
fan-out silencioso que multiplica importes y etiquetaban mal las cifras de
control: producían números falsos sin avisar. Las que quedan son prosa del
campo `porque` que, si un agente la sigue, produce **un error de SQL ruidoso**
(une por una columna que no existe) o una matización imperfecta. Bloquear otra
ronda completa por eso no protegería nada que no proteja ya el hecho de que el
diccionario **todavía no se publica**: hasta el bloque E no llega a ningún
agente, y ahí es donde deben entrar.

---

## Los diez defectos, uno a uno

Estado verificado por mí. «Experimento» significa que reproduje en un worktree
aislado la mutación que antes pasaba en verde.

| # | Defecto | Estado | Cómo lo comprobé |
|---|---|---|---|
| 1 | `cardinalidad: 1:1` publicada como `61` | **corregido, con mecanismo** | Vocabulario cerrado `CARDINALIDADES` (`domain/diccionario.py:83`) aplicado en `:625`. **Experimento E7**: quitar las comillas a un `1:1` → falla `test_f006_r5_ninguna_relacion_real_publica_una_cardinalidad...` con un mensaje que dice «escríbelo ENTRE COMILLAS». Las 8 relaciones afectadas, entrecomilladas; `yaml.safe_load` confirma que **las 42 cardinalidades son ahora `str`** |
| 2 | Seis cardinalidades `N:1` que eran `N:N` | **corregido, con mecanismo; 10 instancias** | La unicidad se **deriva** de la clave de negocio (`_es_unica_por`, `diccionario.py:675`; `_validar_cardinalidad`, `:699`). Las 4 nuevas salen de `mart.yaml`, que la primera pasada no auditó, y **las cuatro son ciertas** contra el SQL. Ninguna relación legítima quedó degradada: las `N:1` hacia dimensiones de clave simple siguen intactas. **Experimento E8**: degradar un `N:N` a `N:1` → detectado |
| 3 | `orden_concepto` «1 a 6» falso | **corregido, ampliado a 3 fichas + 1 relación** | Contrastado: `02_build_fact.sql:299-304` da 1/2/3/4 y `03_views.sql:56,87` añaden GASTOS=2 y BENEFICIO=6. La ficha declara ahora los valores reales `{1,2,2,3,4,6}`, dice que el 2 está duplicado y que no hay 5, y **manda ordenar por `v_pbi_dim_concepto`**, que sí va 1→6 |
| 4 | Órdenes de magnitud: «total» siendo saldo vivo | **corregido** | Las cifras cuadran **al dígito** con `LEEME_RETENCIONES_R1.md:21-22` («34,7 M€ vivos», «21,9 M€ vivos»), ahora con `criterio: saldo_vivo`/`total`, fuente comprobable y sentido (quién retiene a quién, contra `sql/retenciones/01_movimientos.sql:6-8`). La cifra de «~27.300 efectos», que **no estaba en ninguna fuente**, se sustituyó por los dos recuentos reales desglosados |
| 5 | `cliente_ide.nulo_significa` falso | **corregido, con mecanismo** | La ficha dice ahora que llega **0** y cómo filtrarlo. La afirmación fuerte («es el único `*_ide` sin `NULLIF`») es cierta: los otros seis lo llevan. **Experimento E10**: reintroducir el nulo imposible → detectado por dos tests |
| 6 | `R-FRESCURA-MANUAL` citaba `_meta.v_diccionario`, inexistente | **corregido, con mecanismo** | Ahora cita solo `_meta.v_frescura`, que sí existe (`sql/ddl/00_meta.sql:70`), y añade que la antigüedad de `compras`/`retenciones` **se desconoce**. Hay barrido con regex de los nueve esquemas sobre `regla`, `motivo` y `respuesta_correcta`, contrastado contra el inventario derivado del SQL. Queda una cita en `nota` de P15, en condicional y correcta |
| 7 | `R-CLAVE-SUSTITUTA` marcaba estable→inestable | **corregido; mecanismo a medias** | `aux.periodificacion_partida` fuera del ámbito, y las cuatro claves que sí son inestables (`fact_id`, `fact_cat_id`, `plan_id`, `cierre_id`) siguen dentro. El matiz: el test nuevo cubre los falsos positivos y no los falsos negativos, y por eso `mart.v_fact_periodificado.fact_id` —marcada `clave_sustituta`— no la alcanza la regla. Hueco preexistente, no regresión |
| 8 | `R-IMPORTE-MES` no cubría `cierre` | **corregido, ampliado a 4; cero ruido** | Los dos extra (`v_pbi_cierre_indirectos_detalle`, `v_pbi_cierre_generales_detalle`) **tienen la trampa de verdad**: CTE `agregado` con `SUM(importe_origen)` + `LAG` + `ejecutado_mes`. El detector es **simétrico** (busca todo objeto que documente a la vez una columna EUR `suma_solo_dentro_del_mes` y otra `ultimo_valor`) y lleva test de control anti-detector-vacío: devuelve 9 objetos y los 9 están en el ámbito |
| 9 | `design.md` señalado y no corregido | **corregido** | Nota de enmienda fechada (`design.md:40-48`), ejemplo §3.3 con los nombres reales, relación a `maestro.obras.obra_id`, §5.1 a 13 y 12 objetos, y «más de 80» → 98. **Experimentos D1 y D2**: reintroducir el literal `COSTE_REAL` o la columna `obra_codigo` en el ejemplo → detectado. (D3, falsear el recuento de la tabla §5.1, no está vigilado: menor) |
| 10 | Las defensas de la puerta | **corregido: 3 de mis 4 experimentos ahora se cazan; el 4º, declarado** | Ver el apartado siguiente |

## Los experimentos, reejecutados por mí

Worktree aislado (`git worktree --detach`), árbol real intacto. Línea base: 327
tests de F-006 en verde.

| Experimento | Antes | Ahora |
|---|---|---|
| **E1** · desdocumentar `v_pbi_dim_escenario`, devolverla a `pendientes` y **subir** el tope a 74 | pasaba (252 passed) | **detectado**: `test_f006_r27_el_trinquete_solo_baja_a_lo_largo_del_historial` |
| **E2** · ficha esquelética (`descripcion: x`, `grano: x`, `motivo_no_consumo: x`) que saca un objeto de `pendientes` | pasaba | **detectado**: 3 fallos (mínimos de contenido + proyección exacta + validación) |
| **E3** · colar `obra_label`, columna de otra vista del **mismo fichero SQL**, en `v_pbi_fact` | pasaba (254 passed) | **detectado**: `..._las_vistas_documentan_exactamente_su_proyeccion[mart.v_pbi_fact]` |
| **E4** · invertir el `significado` de `importe_mes` a «Importe ACUMULADO» | pasaba | **sigue pasando** — y está **declarado sin adornos** en el informe: «que el TEXTO de una ficha sea cierto […] lo garantiza la revisión humana y la batería T39» |
| **E9** (nuevo) · el mismo retroceso de E1 pero **commiteado**, para que el árbol coincida con HEAD | — | **detectado**: el anclaje recorre el historial del fichero por pares, no solo el árbol |
| **E5** (nuevo) · grano falso en `fact_seguimiento_mensual` («una fila por obra y mes») | — | **pasa en verde** |
| **E6** (nuevo) · `clave_negocio: [obra_id]` en esa misma tabla | — | **pasa en verde** |
| **E11** (nuevo) · clave de negocio falsa **y** degradar a `N:1` el fan-out que esa clave sostiene | — | **pasa en verde** |

Sobre E4: no es un incumplimiento. Ninguna de las cuatro defensas que pedí
podía cazar un texto invertido, y el implementer lo dice en vez de taparlo,
que es exactamente la conducta que la primera pasada echó en falta.

Sobre E5, E6 y E11 sí hay algo que corregir, aunque no en el código: el informe
afirma que ahora están cubiertos «nombres de columna, **granos declarados**,
**claves de negocio**, cardinalidades…». Lo que de verdad está cubierto es que
las columnas de la clave **existan** y que la cardinalidad no prometa una
unicidad que la clave declarada no sostiene. Que el grano o la clave sean
**ciertos** no lo comprueba nada, y E11 enseña la consecuencia: como la
detección de fan-out se **deriva** de la clave de negocio, quien declare una
clave falsa desactiva de paso la defensa que esa clave sostiene. Es la misma
clase de sobreventa —una línea que promete más de lo que el test hace— que
motivó parte del rechazo anterior, y por eso conviene arreglar la frase.

## Lo que arrastra (obligatorio antes de que el bloque E publique)

1. **`cierre.yaml:933` manda un JOIN por una columna que no existe.** El
   `porque` de la relación `v_pbi_planif_vs_real → mart.fact_seguimiento_categoria`
   dice «El JOIN va por `(obra_id, anio_mes, categoria)`», pero la vista **no
   proyecta `categoria`**: sus 13 columnas llevan `concepto_cuadro`
   (`sql/cierre/06_views_planif_vs_real.sql:113-123`). Y no es solo el nombre:
   `PRODUCCIÓN`, `TOTAL COSTES` y `BENEFICIO` son agregados que no corresponden
   a ninguna categoría (`06:52-62`, `:84-106`). **Lo introdujo la corrección del
   defecto 2**, y la corrección hermana de `cierre.yaml:339-341` sí eligió una
   columna que existe en los dos lados (`concepto`), lo que confirma que es un
   despiste.
2. **`mart.yaml:881`**: la relación `v_pbi_cp_tipologia → v_master_vigente_anual`
   manda unir por `(obra_id, anio, ambito_id)`, y `ambito_id` no es columna de
   la vista origen (sus 7 columnas están verificadas); en el SQL es un filtro
   constante `va.ambito_id = 8` (`06_views_cp_tipologia.sql:216`).
3. **`cierre.yaml:298-302`**: al explicar la excepción, `final_pct` se
   autoincluye en ella. En la fila VENTA usa `aprobado_venta`
   (`03_views.sql:190-196`), no `venta_final` como los otros cuatro. Aun así es
   mejor que el texto anterior.
4. **Seis residuos de «mes anterior»** (`cierre.yaml:122,126,269,272,282,307`)
   en columnas vecinas de las siete que sí se corrigieron a «FILA anterior». Es
   la misma trampa —el `LAG` salta los meses sin cierre— en la misma ficha.
5. **La frase del informe** sobre granos y claves de negocio: rebajarla a lo que
   los tests hacen de verdad (ver arriba). Y, si se quiere cerrar E6/E11 de
   verdad, contrastar la clave de negocio contra la PK o el índice único del
   DDL en las tablas, que es donde sí es derivable.

## Rigor y checkpoints (segunda pasada)

- **C1** `[x]` — `bash harness/init.sh` exit 0, **1125 tests**, ejecutado por mí.
- **C2** `[x]` — una sola feature `in_progress`, rama correcta, `current.md` al día.
- **C3** `[x]` — dominio sin infraestructura, cabeceras de ruta, `ruff` limpio.
- **C3 bis** — **N/A**: el diff no toca `docs/referencia/`.
- **C4** `[x]` — la reserva de la primera pasada (R27 se cumplía «al pie de la
  letra» pero no conseguía lo que prometía) **queda resuelta**: el anclaje al
  historial de git es la comprobación que faltaba, y E9 confirma que ni
  commiteando se esquiva.
- **C4 bis** `[x]` — fase RED con trazas por defecto corregido; cobertura
  **98,7 % de 544 líneas**; **mutación verificada de forma independiente**:
  recalculé alcance (**1693 líneas**) y mutantes (**128** = 81 + 24 + 0 + 23),
  y coinciden con `progress/mutacion_F-006.md`; cero supervivientes; sección
  «Evidencias» presente.
- **C4 ter** — **N/A**: no existe `harness/rutas_sensibles.json`.
- **C5** — **N/A parcial**, como en la primera pasada: 14 de 42 tareas, que son
  el alcance encargado. Se exigirá entero al pasar F-006 a `done`.

## Nada prohibido, otra vez

`git diff 5e901f8..HEAD --name-status`: solo los tres YAML del diccionario, el
dominio, los tests, `design.md` y ficheros de `progress/`. **Cero cambios** en
`main.py`, `config/settings.py`, `grants.py`, `postgres_client.py`, `infra/**` y
cualquier `.sql`. Ningún GRANT, REVOKE, firewall ni Azure; ninguna conexión a la
base. Árbol limpio; mis experimentos se hicieron en worktrees aislados que ya
he eliminado.

---
---

# PRIMERA PASADA · 2026-08-20 (RECHAZADO)

> Commits revisados: `ba8ff93`..`5e901f8`. Se conserva íntegra: es lo que se
> pidió corregir y el patrón de contraste de la segunda pasada.

## Veredicto

**RECHAZADO (CHANGES_REQUESTED).**

No por el código —que es sólido— sino por **el contenido publicado**, que es
lo que esta feature entrega. En 25 fichas y 332 columnas no hay **ninguna
columna inventada, ninguna columna omitida, ningún grano falso y ninguna clave
de negocio falsa**: eso está verificado una a una contra el SQL y es la parte
difícil, que está bien hecha. Pero quedan **diez defectos** que sí hay que
corregir, y **cinco de ellos son afirmaciones falsas o engañosas en el texto
que un agente leerá para decidir qué SQL escribe**: una publica un valor sin
sentido (`cardinalidad: 61`) en ocho relaciones de los dos ficheros, otra
invita a un JOIN con fan-out en seis, y otra convierte en «total de la empresa»
unas cifras que son de saldo vivo. Con rigor `critico` y siendo la mentira con aplomo el riesgo
que esta feature existe para eliminar, no se aprueba: son correcciones baratas
y localizadas, y consagrarlas ahora las propaga a las 73 fichas que faltan.

Y hay un segundo motivo, de fondo: **la puerta que debería impedir que esto se
repita en las 73 fichas restantes no lo impide**. Demostrado con experimentos
(ver §«La puerta de cobertura»): el trinquete **puede subir**, una ficha
esquelética de `x` saca objetos de `pendientes`, y el grano, la clave de
negocio y el significado de una columna se pueden invertir sin que ningún test
se entere. El trabajo entregado **no** explota ninguno de esos huecos —lo
comprobé ficha a ficha—, pero el bloque A se entregó como «el andamiaje que
garantiza que el diccionario no se quede atrás» y hoy garantiza bastante menos
de lo que dice. Corregirlo ahora es barato; después de escribir 73 fichas, no.

## Nivel de rigor

`"rigor": "critico"`, declarado explícitamente en `harness/features.json`
(commit `cab50ab`; antes funcionaba por omisión). Exige, según
`CHECKPOINTS.md`: fase RED con traza, cobertura de las líneas cambiadas,
campaña de mutación con **cero supervivientes** sin justificación aceptada por
el humano, y verificaciones `MANUAL (humano)` con su comando y su resultado
real. **Las cuatro puertas se cumplen** (ver C4 bis).

---

## Lo que hay que corregir

Numerado y ordenado por gravedad. Todo con fichero y línea de los dos lados.

### 1. `cardinalidad: 1:1` se publica como el entero `61` (8 relaciones)

YAML interpreta `1:1` sin comillas como **sexagesimal**: 1×60+1 = 61.
`cargador_yaml.py:431` lo pasa por `_texto()` (`:106-108`, que es `str(valor)`),
así que la ficha que consumirá el MCP dirá literalmente `cardinalidad: "61"`.

Verificado ejecutando el propio parser sobre los dos ficheros:

- `mart.yaml`: `v_pbi_fact:408`, `v_pbi_fact_categoria:474`,
  `v_pbi_dim_obra:508`, `v_pbi_dim_partida:565`,
  `v_pbi_dim_partida_niveles:622`, `v_fact_periodificado:1008`.
- `cierre.yaml`: `v_pbi_cierre_cabecera:776` y `:782`.

`1:N` y `N:1` se salvan solo porque llevan letra.

**Corregir**: entrecomillar (`cardinalidad: "1:1"`) **y** cerrar el hueco que
lo permitió: `Relacion.cardinalidad` (`domain/diccionario.py:142`) se declara
`str` pero **no se valida contra ningún vocabulario**. Añadir vocabulario
cerrado `1:1 | 1:N | N:1 | N:N` con su test, como ya se hizo con `agregacion`
(R7). Sin eso el mismo fallo entra otra vez en las 73 fichas que faltan.

### 2. Seis cardinalidades declaradas `N:1` / `1:N` que en realidad son `N:N`

El `de` es `obra_id` a secas y el destino tiene muchas filas por obra:

| Ficha | Relación | Dice | Es |
|---|---|---|---|
| `cierre.yaml:154-156` | `fact_cierre_mensual.obra_id → mart.fact_seguimiento_mensual.obra_id` | 1:N | N:N |
| `cierre.yaml:302-304` | `v_pbi_cierre_resumen.obra_id → cierre.fact_cierre_mensual.obra_id` | N:1 | N:N |
| `cierre.yaml:556-558` | `indirectos_detalle.obra_id → v_pbi_dim_subcategoria_ci.obra_id` | N:1 | N:N |
| `cierre.yaml:560-562` | `indirectos_detalle.obra_id → fact_cierre_mensual.obra_id` | N:1 | N:N |
| `cierre.yaml:630-632` | `generales_detalle.obra_id → fact_cierre_mensual.obra_id` | N:1 | N:N |
| `cierre.yaml:855-857` | `planif_vs_real.obra_id → mart.fact_seguimiento_categoria.obra_id` | N:1 | N:N |

Un agente que se fíe del `N:1` escribe un JOIN con **fan-out silencioso y
duplica importes**. Es exactamente el error que `R-RETENCION-NO-JOIN-LINEAS`
existe para castigar, cometido dentro del propio diccionario.

**Corregir**: poner `N:N` donde lo sea, o —mejor— declarar la relación por su
clave real (`(obra_id, anio_mes)`, `(obra_id, grupo_cod, subcategoria_cod)`),
que es la información que evita el fan-out.

### 3. `v_pbi_cierre_resumen.orden_concepto`: el rango declarado es falso

- Ficha (`cierre.yaml:211-213`): «Orden de presentacion del concepto **(1 a 6)**».
- Real: los cuatro conceptos base heredan `1,2,3,4` de
  `sql/cierre/02_build_fact.sql:291-297`; `GASTOS` recibe **2**
  (`03_views.sql:56`) y `BENEFICIO` **6** (`03_views.sql:85`). Los valores son
  `{1, 2, 2, 3, 4, 6}`: **el 2 está duplicado y el 5 no existe**.
- Además **no coincide** con `v_pbi_dim_concepto.orden` (`03_views.sql:25-32`),
  pese a que la relación de `cierre.yaml:312-315` dice que el dim aporta «el
  orden de presentacion».

Un `ORDER BY orden_concepto` deja GASTOS e INDIRECTOS empatados y en orden
indefinido. La ficha debe decir qué valores toma de verdad y mandar ordenar
por el dim.

### 4. Los órdenes de magnitud (R10) mezclan dos criterios y llaman «total» a lo vivo

`00_global.yaml:260-276` publica «Retenido a proveedores, **total de la
empresa**: 34.700.000» y «Retenido de clientes, **total de la empresa**:
21.900.000». La fuente primaria del repositorio, `LEEME_RETENCIONES_R1.md:19-22`,
dice **«34,7 M€ vivos»** y **«21,9 M€ vivos»** (saldo vivo, `fecrea = 0`).
La tercera cifra, ~27.300 efectos, sí es el total (25.124 + 2.219 = 27.343).

Es decir: el bloque cuya única función es **detectar una cifra absurda antes de
darla por buena** mezcla saldo vivo con totales sin avisar. Un agente que
compare un `SUM(importe)` de todos los movimientos contra 34,7 M€ concluirá que
su número está mal cuando está bien, o al revés.

**Corregir**: añadir «vivos» a las dos primeras y citar como `fuente` el
documento del repositorio que trae la medición (`LEEME_RETENCIONES_R1.md:19-22`),
no la nota de segunda mano del prototipo.

### 5. `v_pbi_cierre_cabecera.cliente_ide`: el `nulo_significa` es falso

Ficha (`cierre.yaml:662-665`): «La obra no tiene cliente asignado».
`sql/cierre/05_views_cabecera.sql:71` proyecta `obr.entide AS cliente_ide`
**sin `NULLIF(..., 0)`** — es el único `*_ide` de la vista que no lo lleva
(compárese con `tecnico_ide:73`, `centro_coste_ide:75`, `tipo_obra_ide:77`,
`clase_obra_ide:79`, `director_obra_ide:162`). Las obras sin cliente traen
**0**, y `WHERE cliente_ide IS NULL` no devuelve nada.

### 6. `R-FRESCURA-MANUAL` manda consultar una vista que todavía no existe

`00_global.yaml:43-44`: «se obtiene con `SELECT * FROM _meta.v_frescura` (o de
una sola vez, junto con la semantica, en `_meta.v_diccionario`)».
`_meta.v_diccionario` **no existe en el repositorio** (cero apariciones fuera
de `specs/`); la crea T15, en el bloque E. El propio fichero se contradice en
`00_global.yaml:655`: «Cuando exista `_meta.v_diccionario` (bloque E)».

No es catastrófico porque el diccionario aún no se publica —la publicación es
también bloque E—, pero deja una dependencia dura que hay que fijar: **o se
condiciona la frase, o el bloque E no puede publicar sin haber creado antes la
vista**. Publicar en ese orden sería servir una instrucción que revienta.

### 7. `R-CLAVE-SUSTITUTA` marca como inestable una clave que sí es estable

La regla (`00_global.yaml:156-165`) mete `aux.periodificacion_partida` en el
ámbito y declara `regla_id` entre las claves que «se reasignan enteras en cada
build», con el motivo «las tablas se recrean con DROP + CREATE».
`sql/mart/04_view_periodificado.sql:14` crea esa tabla con **`CREATE TABLE IF
NOT EXISTS`** y ningún build la reconstruye: `regla_id` es estable. El error es
conservador (no produce números falsos), pero es un dato falso dentro de una
regla dura, y las reglas duras se respetan por ser exactas.

### 8. `R-IMPORTE-MES` no cubre `cierre`, que es donde ocurrió el bug que la motiva

El ámbito (`00_global.yaml:55-61`) lista objetos de `mart` y `stg`, pero el
`motivo` cita el bug de la Tanda 1.4 **del cierre**
(`sql/cierre/02_build_fact.sql:7-10`, el ≈9x). `cierre.fact_cierre_mensual`
tiene la misma trampa con otros nombres: `ejecutado_origen` es acumulado y
`ejecutado_mes` el parcial (`sql/cierre/01_ddl_fact.sql:23-26`). Está mitigado
en las fichas (`agregacion: ultimo_valor`), pero un agente que lea la regla y
no la ficha repite el error original.

**Corregir**: añadir `cierre.fact_cierre_mensual` y `cierre.v_pbi_cierre_resumen`
al ámbito, nombrando esas dos columnas.

### 9. `design.md` quedó señalado y no corregido

El informe del implementer dice, con razón, que el ejemplo de `design.md` §3.3
usa columnas y literales que no existen, y que el recuento de §5.1 está mal.
Pero **no lo arregló**, y el documento sigue como estaba:

- `design.md:186,192,208,219-220`: `obra_codigo`, `partida_codigo`, `mes`,
  `valores: [COSTE_REAL, COSTE_PLAN, VENTA_REAL, VENTA_PLAN]` y la relación
  `a: maestro.obras.obra_codigo`. **Ninguno existe**: el SQL dice `codigo_obra`,
  `codigo_partida`, `anio_mes` y `Coste Real / Coste Planificado / Venta Real /
  Venta Planificada` (`sql/mart/01_ddl.sql:47-72`,
  `sql/mart/05_views_powerbi.sql:73-79`), y `maestro.obras` expone `obra_id`
  (`sql/maestro/01_obras.sql:19`).
- `design.md:393-394`: «`mart.yaml` ~11 objetos: 2 tablas + **9 vistas**» y
  «`cierre.yaml` ~10 objetos: 1 tabla, **6 vistas**, 3 funciones».
  El inventario real es **13 objetos en `mart` (2 + 11 vistas)** y **12 en
  `cierre` (1 + 8 vistas + 3 funciones)**, verificado por mí objeto a objeto.
  `design.md:823` sigue diciendo «más de 80 objetos» cuando son 98.

`design.md` §3 es **el contrato del YAML** y su ejemplo es lo que copiará quien
escriba `compras.yaml`, `retenciones.yaml` y las 73 fichas restantes. Que las
fichas de este bloque estén bien no evita que el error se propague desde el
documento. Si el arnés exige que la enmienda la firme el spec-author, que la
firme; pero no puede quedarse sin hacer.

### 10. Las defensas de la puerta, antes de escribir 73 fichas más

Detalle y evidencia en §«La puerta de cobertura». Lo mínimo:

- **Mínimos de contenido** en `descripcion`, `grano`, `significado` y
  `motivo_no_consumo`, como ya se exige en el bloque global
  (`test_f006_formato.py:964`, `test_f006_reglas.py:301-302,450-451`). Cierra
  la ficha esquelética y la puerta trasera de R3 de un golpe.
- **Acotar la búsqueda de columnas al `SELECT` de la vista** y quitar los
  comentarios antes de buscar.
- **Anclar `PENDIENTES_MAX`** a algo que no sea la misma línea que se edita, o
  añadir un test que prohíba que un objeto vuelva de documentado a `pendientes`.
- **Retirar de los docstrings** la afirmación de que `check-diccionario` cubre
  hoy lo que la puerta offline no ve, o implementarlo. Hoy es una promesa.

Esto es prevención, no reparación: **ninguna de las 25 fichas entregadas
explota estos huecos**. Si el líder prefiere tratarlo como tarea aparte del
bloque A en vez de como condición de esta entrega, es defendible; lo que no lo
es es dejarlo sin decidir.

---

## Correcciones del implementer que SÍ he verificado y son correctas

Conviene decirlo porque son enmiendas a la spec y, si estuvieran mal, el error
quedaría consagrado en el contrato:

| Corrección | Veredicto | Evidencia |
|---|---|---|
| El inventario real son **98 objetos**, no «más de 80» | **correcta** | reproducido por mí con `objetos_de_sql` + `objetos_de_raw`: **98** = raw 31, compras 14, mart 13, cierre 12, retenciones 10, stg 10, maestro 4, `_meta` 3, aux 1. Coincide con el reparto declarado |
| `mart` tiene **11 vistas**, no 9 | **correcta** | las 11 en `sql/mart/04`, `05`, `05b`, `06` |
| `cierre` tiene **8 vistas**, no 6 | **correcta** | `03_views.sql:24,37`, `04_views_detalle.sql:50,101,117,503`, `05_views_cabecera.sql:21`, `06_views_planif_vs_real.sql:31` |
| Los cuatro literales de escenario son `Coste Real / Coste Planificado / Venta Real / Venta Planificada` | **correcta** | `sql/mart/05_views_powerbi.sql:73-79` |
| `clave_negocio` con `obra_id`/`partida_id` en vez de los códigos | **correcta** | `codigo_partida` es anulable y `obra_id` = `con.ide`, estable |
| `presupuesto_aprobado_venta` es copia literal del inicial | **correcta** | `sql/cierre/05_views_cabecera.sql:167` |
| `final_pct` de VENTA va contra el aprobado | **correcta** | `sql/cierre/03_views.sql:193-202` |
| `ejecutado_mes_periodif` resta el INCURRIDO del mes anterior | **correcta** | `sql/cierre/04_views_detalle.sql:388-396,449-452` |
| `ratio_lineal` no tiene tope en el 100 % | **correcta** | `04_views_detalle.sql:307-320`, solo `GREATEST`, ningún `LEAST` (el comentario del SQL en `:295` es el que miente) |
| `v_pbi_dim_subcategoria_ci` resuelve por obra | **correcta** | `04_views_detalle.sql:52-61,87-90` |
| `build-compras` y `build-retenciones` no registran paso en `_meta.etl_runs` | **correcta** | `main.py:3189-3191` y `:3491-3493` ejecutan SQL en línea sin step; `build_cierre` y `build_maestros` sí (`main.py:2246,2261`) |
| `mart.v_fact_periodificado` no periodifica nada hoy | **correcta** | `aux.periodificacion_partida` se crea vacía; `consumo_recomendado: false` con motivo escrito |

---

## Veracidad de las fichas: lo que se comprobó y cómo

No es un muestreo simbólico: se contrastaron **las 25 fichas y las 332 columnas
una a una** contra el SQL que crea cada objeto.

- **`mart.yaml`** (13 objetos, 185 columnas), contra `sql/mart/01_ddl.sql`,
  `02_build_fact.sql`, `03_agg_categoria.sql`, `04_view_periodificado.sql`,
  `05_views_powerbi.sql`, `05b_view_dim_partida_niveles.sql` y
  `06_views_cp_tipologia.sql`. Las 34 columnas de `fact_seguimiento_mensual`,
  las 19 de `fact_seguimiento_categoria`, las 17 de `v_pbi_fact`, las 35 de
  `v_fact_periodificado` y las 18 de `v_pbi_dim_partida_niveles` coinciden
  **exactamente**, ni una de más ni una de menos. Los granos son ciertos,
  incluida la parte delicada: la elección de versión vigente **por mes**
  (`02_build_fact.sql:152-170`) y la ventana común plan/real de
  `v_pbi_cp_tipologia` (`06_views_cp_tipologia.sql`, CTE `corte`), que la
  ficha describe con exactitud, mes de corte incluido.
- **`cierre.yaml`** (12 objetos, 147 columnas), contra los siete ficheros de
  `sql/cierre/`. Mismo resultado: 147/147 columnas existen con el nombre exacto
  y no sobra ninguna; los 9 granos y las 9 claves de negocio son ciertos.
- **Relaciones**: los destinos que hoy el validador **no puede** comprobar
  (porque están en `pendientes`) los comprobé a mano: `stg.obras.obra_id`
  (`sql/stg/03_obras.sql:83`), `stg.partidas.partida_id`, `maestro.obras.obra_id`
  (`sql/maestro/01_obras.sql:19`), `compras.v_pbi_partida_coste.partida_id`
  (`sql/compras/03_views.sql:181+`), `cierre.fact_cierre_mensual.obra_id`,
  `stg.plan_mensual.obra_id` y `aux.periodificacion_partida.regla_id`. **Todos
  existen.** El defecto de las relaciones es la cardinalidad (punto 2), no el
  destino.

### Las doce reglas duras

Las doce están, con los seis campos, todas `bloqueante`, y **ninguna es falsa**.
Verificadas contra el SQL las siete que pedía el encargo:

| Regla | Veredicto | Evidencia |
|---|---|---|
| `R-IMPORTE-MES` | verdadera (ámbito corto, punto 8) | `stg/08_plan_mensual.sql:352-355`: `importe_mes = importe_origen - LAG(importe_origen)`. El ≈9x está literal en `cierre/02_build_fact.sql:7-10` |
| `R-VERSION-MASTER` | verdadera y accionable | `stg/01_ddl.sql:202-224` (conviven todas las versiones); la vigente se resuelve solo aguas abajo, `mart/02_build_fact.sql:152-170`, con el filtro `tipo_master IN ('Planif Inicial','ABC','Cuatrimestral')` palabra por palabra |
| `R-ABONO-NEGATIVO` | verdadera | `compras/03_views.sql:10` y las vistas agregan FACTURA y ABONO juntos (`:118`, `:192`) |
| `R-RETENCION-NO-JOIN-LINEAS` | verdadera | `retenciones/01_movimientos.sql:3,48,68`: un registro por efecto. El incidente de 38,9 M€ está declarado en `progress/explore_F-006_mcp_bbdd.md:80-83` |
| `R-LINEA-ID-NO-UNICA` | verdadera | `compras/02_fact_linea.sql:12-13`: `CREATE TABLE ... AS` de tres orígenes (`ctrpro`, `dcapro`, `dcfpro`), sin PK; `tipo_doc` y `linea_id` existen |
| `R-UNIVERSO-OBRA` | verdadera | `stg/03_obras.sql:105-118` (lista de administrativas, `cod !~ '[0-9]{5,}'`, dedup por `conext.cod='15'`) vs `maestro/01_obras.sql:17-30`, vista **sin un solo WHERE** |
| `R-CLAVE-SUSTITUTA` | verdadera salvo `aux` (punto 7) | `fact_id`, `fact_cat_id`, `cierre_id`, `plan_id` son BIGSERIAL y sus tablas se recrean o truncan en cada build |

Las otras cinco (`R-FRESCURA-MANUAL`, `R-OBRA-ACTIVA`, `R-FAS-AMBIGUO`,
`R-COMPRAS-SIN-IVA`, `R-COMPRAS-TIPO-DOC`) también son verdaderas. Dos matices
menores: el `motivo` de `R-COMPRAS-TIPO-DOC` describe mal el mecanismo (la
función se llama con literales `14`/`15` y `compras.fn_serie(con.cod)`, no con
`con.tip`, y `'CONTRATO'` es un literal de `02_fact_linea.sql:17`), y
`R-COMPRAS-SIN-IVA` puede afinar que `totdoc` es «total sin retención», o sea
que la diferencia no es solo el impuesto.

**Observación de cobertura**: `derivar_avisos` solo adjunta códigos a fichas que
existen. Hoy **siete de las doce reglas apuntan únicamente a objetos que siguen
en `pendientes`**, así que no se adjuntan a ninguna ficha. Es coherente con el
trinquete, pero hasta que `pendientes` esté vacía esas reglas solo llegan al
agente si se le sirve el bloque global entero. Conviene que el bloque E lo
tenga en cuenta al diseñar qué devuelve `contexto_bbdd`.

---

## La puerta de cobertura: qué garantiza y qué no

Se pidió expresamente comprobar tres cosas. Las respondo con experimentos
reales, hechos en un **worktree aislado** (el árbol de trabajo nunca se tocó y
`git status` sigue limpio).

**1. ¿El trinquete solo puede bajar?** **No. El trinquete no es un trinquete.**
`PENDIENTES_MAX` (`tests/test_f006_cobertura.py:417`) es una constante escrita
en el propio fichero de test, y nada la ancla a su valor anterior. Los dos
tests que la vigilan comparan la constante **con la lista del YAML**, no con el
pasado: `..._solo_baja` (`:468`) exige `len(pendientes) <= PENDIENTES_MAX` y
`..._no_esta_holgado` (`:483`) exige la igualdad. Subir las dos cosas a la vez
pasa en verde.

Demostrado: borré la ficha de `mart.v_pbi_dim_escenario`, la devolví a
`pendientes` y subí el tope a 74 → **252 passed, todo verde**. Es decir,
**desdocumentar un objeto ya documentado y retroceder el contador es legal**,
que es exactamente lo que la regla de hierro 4 de `tasks.md` dice que no puede
pasar. Lo único realmente protegido es la holgura (que la constante no quede
por encima de la lista) y la coherencia de `pendientes` (ni fantasmas ni
objetos ya documentados), más
`test_f006_r24_puerta_el_inventario_no_esta_vacio` (`:432`), que sí cubre bien
el fallo silencioso clásico —si cambia la ruta del SQL y el `rglob` no
encuentra nada, la puerta pasaría sin comprobar nada—. La frase del docstring
«**Solo baja.** […] ninguna tarea lo sube» es hoy un comentario, no un test.

**2. ¿Se puede pasar declarando un objeto como documentado sin estarlo?**
**Sí, y por varias vías. Esto hay que cerrarlo antes de los bloques F y G.**
Los experimentos:

- **Omitir columnas de una vista pasa desapercibido.** Borré `can_mes` de la
  ficha de `mart.v_pbi_fact` —una columna que la vista sí tiene
  (`sql/mart/05_views_powerbi.sql:157`)— y la suite entera quedó **en verde:
  `98 passed`**. Para las **tablas** la comprobación de
  `test_f006_fichas.py:153` sí es exacta en los dos sentidos; para las
  **vistas** solo se exige que cada columna documentada *aparezca* en el
  fichero SQL, así que una ficha con la mitad de sus columnas pasa.
- **Una ficha esquelética baja el trinquete.** Escribí un `maestro.yaml` con
  `descripcion: x`, `grano: x`, `motivo_no_consumo: x`,
  `consumo_recomendado: false` y una sola columna `obra_id: x`, saqué
  `maestro.obras` de `pendientes` y bajé `PENDIENTES_MAX` a 72: **todos los
  tests de F-006 en verde**. El validador exige que los campos *existan*, no
  que digan algo. Escalado en la auditoría paralela: generando las **31 fichas
  de `raw` rellenas con `x`** el trinquete cae de 73 a 42 en verde. Por ese
  camino F-006 «cierra» con `pendientes` a 0 sin una línea de conocimiento.
- **El contraste de vistas admite cualquier palabra del fichero.** El test
  genérico (`test_f006_fichas.py:254-270`) busca `\b<nombre>\b` en el **texto
  crudo del fichero entero, comentarios incluidos**. Documenté `obra_label`
  —columna de `mart.v_pbi_dim_obra`— dentro de la ficha de `mart.v_pbi_fact`,
  ambas en `05_views_powerbi.sql` → **254 passed**. La auditoría paralela
  confirma que también pasan palabras que solo aparecen en un comentario
  (`segmentadores`, `estrella`) y hasta el nombre de la tabla origen como si
  fuera una columna. Sí funciona el corte **entre** ficheros distintos.
- **El texto no se contrasta con nada, tampoco en las tablas.** Grano, clave de
  negocio, descripción, `tipo`, `capa` y el `significado` de cada columna no
  los cruza ningún test con el SQL. Comprobado en la auditoría paralela con
  nueve mutaciones, todas en verde; las tres que más importan: grano falso en
  `fact_seguimiento_mensual` («una fila por obra y mes», borrando partida y
  escenario), `clave_negocio: [obra_id]` en esa misma tabla, y el
  `significado` de `importe_mes` **invertido** a «Importe ACUMULADO desde el
  inicio de la obra». Esa última es literalmente la trampa nº 1 del datamart
  (`R-IMPORTE-MES`) escrita al revés, y la suite no se entera:
  `test_f006_r7_mart_importe_origen_no_se_declara_sumable` (`:180`) solo mira
  el campo `agregacion`, no el texto.

Es un hueco de la puerta, no del trabajo entregado: **verifiqué que ninguna de
las 25 fichas de este bloque lo explota** —las 332 columnas están completas, los
granos y las claves son ciertos y los significados también—. Pero quedan 73
fichas por escribir y el mecanismo que debería impedirlo no lo impide. Cuatro
defensas baratas, por orden de rentabilidad: **(a)** exigir mínimos de
contenido como ya se hace en el bloque global (`descripcion >= 40`,
`grano >= 20`, `significado >= 15`, `motivo_no_consumo >= 30`), que mata de una
vez la ficha esquelética y el `motivo_no_consumo: x`; **(b)** recortar el texto
de la vista concreta —entre su `CREATE VIEW` y el siguiente— y quitar
comentarios antes de buscar, que cierra lo de `obra_label`; **(c)** para las
vistas de `consumo_recomendado: true`, comparar el número de columnas
documentadas con el de alias del `SELECT` final; **(d)** anclar
`PENDIENTES_MAX` a algo que no se pueda subir editando la misma línea.

**3. ¿El umbral acordado es el que se aplicará en el bloque H?** El umbral
implementado en `evaluar_cobertura` (`domain/inventario.py:171-219`) es el de
R25/R26: **100 % de objetos con ficha** (bloqueante) y **100 % de columnas con
`significado` dentro de `consumo_recomendado: true`** (bloqueante), con aviso
no bloqueante fuera. Además bloquea dos cosas que la spec no pedía y que están
bien traídas: fichas huérfanas (describen humo) y pendientes fantasma (inflan
el trinquete). La salvedad es la del punto 2: ese 100 % se mide **sobre las
columnas declaradas**, no sobre las que el objeto tiene de verdad. La
comprobación contra el catálogo real es `check-diccionario` (R28), que llega en
el bloque E y sigue siendo imprescindible: el propio docstring de la puerta
declara que es heurística (R29), como pedía la spec.

Con un matiz que conviene fijar: **`check-diccionario` se cita tres veces como
la defensa que cubre lo que la puerta offline no ve** (`test_f006_fichas.py:23`,
`test_f006_cobertura.py:17`, `domain/inventario.py:13,94`) **y todavía no
existe** —no hay tal comando en `main.py`; es T27, bloque E—. Está bien que no
exista, es alcance futuro; lo que no está bien es citarlo en presente como si
protegiera algo hoy. Y hay un test que roza la circularidad:
`test_f006_r29_dominio_el_docstring_declara_la_heuristica`
(`test_f006_cobertura.py:163-169`) comprueba que la cadena `"check-diccionario"`
**esté escrita en el docstring**, es decir, verifica la promesa, no el comando.

## Checkpoints

| | Estado | Nota |
|---|---|---|
| **C1** · arnés en verde | `[x]` | `bash harness/init.sh` exit 0, 1052 tests, ejecutado por mí |
| **C1** · ficheros del arnés | `[x]` | los siete presentes |
| **C2** · una sola `in_progress` | `[x]` | solo F-006 |
| **C2** · rama correcta | `[x]` | `feature/F-006-mcp-azure` |
| **C2** · `current.md` solo la sesión activa | `[x]` | 46 líneas, sin restos |
| **C2** · `history.md` de las `done` | `[x]` | F-006 no es `done` |
| **C3** · arquitectura hexagonal | `[x]` | `domain/diccionario.py` y `domain/inventario.py` importan solo stdlib y dominio; el cargador YAML vive en `infrastructure/` |
| **C3** · primera línea con ruta | `[x]` | los 9 ficheros nuevos |
| **C3** · sin prints, TODOs ni secretos | `[x]` | `ruff check` limpio en todo lo nuevo |
| **C3** · semántica Sigrid | `[x]` | `amb`/`fas`, `importe_origen` vs `importe_mes` y las versiones master duplicadas están tratadas y son el núcleo de las reglas |
| **C3 bis** · documentos de fuera | **N/A** | no se añade ni se modifica nada en `docs/referencia/`. Justificado: el diff no toca esa carpeta |
| **C4** · requisito → test | `[x]` con reserva | R1–R14, R16, R22, R24–R27, R29, R39, R41 con tests `test_f006_rN_*`; R40 lo exige el validador (`diccionario.py:455-461`) aunque su test no lleve el número; el resto son de bloques E–K. **La reserva**: R27 se cumple *al pie de la letra* —la puerta falla si `pendientes` crece por encima del valor declarado— pero ese valor se declara en la línea de al lado y se puede subir, así que el requisito, tal y como está redactado, **no consigue lo que la regla de hierro 4 de `tasks.md` promete**. El hueco es del requisito tanto como del test |
| **C4** · tests sin red ni BBDD | `[x]` | ni un import de `psycopg`/`requests`; hay un test que **prohíbe** al dominio importar `yaml`, `psycopg` o `pathlib` |
| **C4** · verificaciones MANUAL listadas | `[~]` | están en `progress/impl_F-006.md` (T19, T27, T32–34, T37–T39), **no en `current.md`** como pide el checkpoint. Ninguna correspondía a los bloques A–D. Defecto menor, no bloqueante |
| **C4 bis** · rigor declarado | `[x]` | `"rigor": "critico"` explícito |
| **C4 bis** · fase RED | `[x]` | trazas reales pegadas para T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13 y T14. Además el implementer declara y explica un test RED que **reescribió** al implementar, en vez de esconderlo |
| **C4 bis** · cobertura | `[x]` | `PUERTA COBERTURA: 98.8% de 499 líneas cambiadas (493/499, umbral 80%)`, reproducido por mí |
| **C4 bis** · mutación verificada de forma independiente | `[x]` | ver abajo |
| **C4 bis** · supervivientes analizados | `[x]` | cero supervivientes; nada que analizar |
| **C4 bis** · sección «Evidencias» con los cuatro números | `[x]` | `impl_F-006.md:501-525` |
| **C4 ter** · rutas sensibles | **N/A** | no existe `harness/rutas_sensibles.json` (solo el `.ejemplo.json`): el bloque es N/A por configuración |
| **C5** · `tasks.md` todo `[x]` | **N/A parcial** | 14 de 42 tareas marcadas, que son **exactamente** T1–T14, el alcance encargado. Justificado: esto es una revisión de entrega intermedia, no el cierre de la feature; C5 se exigirá entero cuando F-006 pase a `done` |
| **C5** · sin artefactos sueltos | `[x]` | `git status` limpio |
| **C5** · `features.json` refleja el estado | `[x]` | `in_progress` |

### Verificación independiente de la mutación (C4 bis)

No me fié del informe. Recalculado con cálculo puro, sin ejecutar la suite:

- **Alcance**: `harness.alcance.alcance_de_feature('F-006')` da 808 + 278 + 2 +
  435 = **1523 líneas**, idéntico a `progress/mutacion_F-006.md`.
- **Mutantes**: `harness.mutacion.generar_mutantes` sobre esas líneas devuelve
  **112** (65 + 24 + 0 + 23), idéntico al informe.
- **Muestreo de mortalidad**: como la campaña declara 0 supervivientes no hay
  supervivientes que muestrear, así que hice la comprobación inversa en un
  **worktree aislado** (nunca en el árbol real): apliqué tres mutantes elegidos
  al azar —`diccionario.py:501`, `inventario.py:127`,
  `cargador_yaml.py:239`— y la suite de F-006 los mató a los tres
  (exit 1 en los tres casos). El «112 de 112 muertos» es creíble.
- La campaña no declara cero mutantes, así que la prueba de control por
  exclusión de alcance no aplica.

---

## Que no se haya tocado nada prohibido

Comprobado con `git diff dev...HEAD --name-status`. El diff **añade** nueve
ficheros de código y contenido y modifica solo `BACKLOG.md`,
`harness/features.json` y `progress/current.md`.

- **Cero cambios** en `main.py`, `config/settings.py`, `grants.py`,
  `postgres_client.py`, `infra/**` y en cualquier `.sql`. Ningún `GRANT`,
  ningún `REVOKE`, ninguna regla de firewall, nada de Azure.
- Ninguna conexión a la base: los tests nuevos no importan `psycopg` y hay un
  test que lo prohíbe explícitamente en el dominio.
- El cambio de `harness/features.json` es el `status`/`rigor` de F-006 y el
  alta de F-036 a F-040, que venía de la sesión de spec.

---

## Cómo quedan preparados los bloques E a K

Se pidió opinión expresa sobre el contrato de `_meta` que consumirá `mcp-bbdd`.
**Queda bien preparado**, con una salvedad y una dependencia:

- Las entidades del dominio cubren **campo por campo** el DDL de `design.md`
  §4.1: `tipo`, `capa`, `consumo_recomendado`, `motivo_no_consumo`,
  `descripcion`, `grano`, `clave_negocio`, `paso_etl`, `refresco`, `avisos`
  (derivados, no escritos a mano) y el resto de la ficha para el `JSONB`.
  Publicar no exige tocar el formato: es serializar lo que ya hay.
- `derivar_avisos` (R12) ya funciona y es dominio puro, así que la columna
  `avisos` del contrato se llena sola.
- **Salvedad**: el defecto 1 (`cardinalidad: 61`) llegaría tal cual al `JSONB`
  publicado. Corregirlo antes del bloque E cuesta ocho comillas; después
  cuesta una republicación.
- **Dependencia dura**: el bloque E debe crear `_meta.v_diccionario` (T15)
  **antes o a la vez** que la primera publicación, porque el texto de
  `R-FRESCURA-MANUAL` ya la cita como consultable (defecto 6).

---

## Hallazgos menores (anotar, no bloquean)

No entran en la lista de correcciones exigidas, pero conviene que el
implementer los recoja al pasar por ahí:

1. `cierre.yaml:433-436` y `:472-475` dicen que fuera de INFRA «todas las
   columnas de periodificacion son nulas»; `importe_fase0` y
   `plazo_total_meses` traen valor siempre (`04_views_detalle.sql:438-439`).
   Curiosamente las fichas de esas dos columnas sí lo dicen bien.
2. `final_anterior` (`cierre.yaml:100`): un mes anterior sin previsión da **0**,
   no NULL (`02_build_fact.sql:331`); es NULL solo en la primera fila de la
   partición.
3. «al cierre del mes anterior» (cuatro fichas) significa **fila anterior
   presente**, no mes de calendario anterior: el `LAG` salta los meses sin
   fase (`02_build_fact.sql:353-359`).
4. `v_pbi_cierre_cabecera.plazo_meses` y
   `v_pbi_cierre_indirectos_detalle.plazo_total_meses` se calculan distinto y
   dan números distintos para la misma obra; ninguna ficha lo advierte.
5. `final_pct` como «única excepción del cuadro» (`cierre.yaml:267-274`) exagera:
   en la fila VENTA los cinco porcentajes son excepción; lo único propio del
   `final_pct` es el divisor.
6. `v_pbi_dim_concepto` y `v_pbi_dim_tipologia_cp` se describen como «catálogo
   ESTATICO» pero declaran `refresco: manual`, existiendo `estatico` en el
   vocabulario.
7. Tres comentarios del SQL mienten y el YAML acierta —`04_views_detalle.sql:295`
   (cap del `ratio_lineal`), `03_views.sql:129` (fallback inexistente),
   `05_views_cabecera.sql:174` (JOIN muerto con `raw.cen`)—. No es deuda de
   esta feature, pero engañarán a quien lea el SQL: candidatos a una feature de
   limpieza.

---

## Propuesta de mejora del protocolo (no aplicada)

Para `CHECKPOINTS.md`, a decisión del humano: **cuando una feature entrega
contenido declarativo que otro sistema consumirá (YAML, prompts, fichas), C4
debería exigir explícitamente que los valores del contrato pasen por un
vocabulario cerrado validado**, no solo que el campo exista. El defecto 1 de
esta review —un `1:1` que YAML convierte en `61` y que ningún test vio— es
justo lo que ese punto habría cazado, y no lo cazan ni la cobertura (la línea
se ejecuta) ni la mutación (el valor viene del dato, no del código).

---

# 20ª pasada · 2026-08-26 — la campaña válida, reverificada por el reviewer

**Revisión completa** (no incremental: el veredicto vigente era RECHAZADO desde
la 16ª, así que no hay «último commit aprobado» desde el que medir un delta).
`HEAD = 6332995`. Rama `feature/F-006-mcp-azure`. Nivel `critico` declarado en
`harness/features.json`.

Todo lo que sigue se midió **contra el árbol**, no leyendo el papeleo. Donde no
he podido verificar algo, lo digo.

## 1 · El entorno

`bash harness/init.sh`, tal cual, exit **0**:

```
2473 passed, 128 skipped, 909 warnings in 603.92s (0:10:03)
[OK] pytest en verde (con medición de cobertura)
[OK] PUERTA COBERTURA: 100.0% de 33 líneas cambiadas cubiertas (33/33, umbral 80%, nivel critico)
[OK] PUERTA TAMAÑO: F-006 dentro de los topes (requirements 132/150, design 191/250, impl 219/220, review 125/140)
[OK] Rama actual: feature/F-006-mcp-azure
ENTORNO LISTO. Puedes trabajar.
```

`git status` limpio, sin ficheros sin trackear, `git worktree list` con una sola
entrada. Ningún mutante aplicado.

**Sobre las «33 líneas cambiadas».** El alcance por diff de la rama
(`harness.alcance`, base `dev`, merge-base `7dd010d`) da **139 líneas de
producción en 4 ficheros, todos de `harness/`** —`mutacion_paralela.py` 101,
`mutacion.py` 29, `tamano.py` 7, `rigor.py` 2—. Las 33 son la intersección con
las líneas *ejecutables*; el resto son comentarios y docstrings. El número es
correcto. Lo que hay que entender es que **el cuerpo de F-006 ya está en `dev`**
y no aparece en el diff de la rama: por eso la campaña se lanzó con `--ficheros`
sobre los ocho módulos del diccionario, que es lo correcto y más exigente que el
diff.

## 2 · La campaña de mutación (T41), verificada de forma independiente

### 2.1 · Recálculo puro del alcance y del nº de mutantes

Ejecutado por el reviewer con `harness.alcance.alcance_de_ficheros` +
`harness.mutacion.generar_mutantes` (cálculo puro: no ejecuta la suite ni
escribe en disco), sobre los ocho ficheros declarados:

| Fichero | Líneas | Mutantes |
|---|---|---|
| `application/steps/publicar_diccionario_step.py` | 190 | 5 |
| `domain/diccionario.py` | 1089 | 93 |
| `domain/inventario.py` | 288 | 24 |
| `infrastructure/diccionario/cargador_yaml.py` | 468 | 42 |
| `infrastructure/postgres/catalogo.py` | 166 | 14 |
| `infrastructure/postgres/diccionario_sql.py` | 332 | 25 |
| `infrastructure/postgres/relaciones_sql.py` | 319 | 26 |
| `infrastructure/postgres/unicidad_sql.py` | 274 | 27 |
| **Total** | **3126** | **256** |

**Coincide exactamente** con el informe: 3126 líneas y 256 mutantes.

### 2.2 · Los 52 supervivientes son mutantes reales

No basta con que los totales cuadren: un informe con el alcance bien y unos
supervivientes inventados pasaría el recálculo. Se parsearon los **52** bloques
del informe y se contrastó cada uno —fichero, línea, **operador** y el **texto
exacto original → mutado**— contra el conjunto de mutantes que el mutador genera
hoy sobre el árbol:

```
supervivientes parseados: 52
supervivientes NO reproducibles como mutante real: 0
```

**52 de 52 reproducibles**, byte a byte. Reparto por fichero: `diccionario.py`
15, `cargador_yaml.py` 10, `diccionario_sql.py` 8, `unicidad_sql.py` 7,
`relaciones_sql.py` 5, `catalogo.py` 4, `inventario.py` 3.

### 2.3 · RM1 — el SHA medido y el alcance revisado

El informe declara `SHA de HEAD medido = 99e23356a69a1bf79ac803a25fdf5a4f53393bf4`.
HEAD es hoy `6332995`. **Comprobado el diff `99e2335..HEAD`**: 13 ficheros, y
**ninguno de los ocho del alcance**. Solo cambiaron `progress/`, `BACKLOG.md`,
`harness/features.json` y **cinco ficheros de tests**. El alcance medido ES el
alcance que reviso. **RM1 se cumple.**

### 2.4 · La campaña tardó lo que tenía que tardar

| Dato | Valor |
|---|---|
| Tiempo total | 8368,3 s (2 h 19 min) |
| Workers | **6** (declarados por el informe) |
| Media por mutante evaluado | 32,7 s |
| Línea base por worker | 462,6 – 485,8 s |
| Timeout efectivo | 972 s (línea base × 2,0), suelo 120 s |

- **Coste real por mutante** = 8368,3 × 6 ÷ 256 = **196,1 s**. Muy por encima
  del segundo: la campaña no es sospechosa por construcción.
- **RM2**: `media × W` = 32,7 × 6 = 196,2 s frente a una línea base de ~470 s →
  ratio **0,42**, muy lejos del «ni la décima parte» que obliga a rechazar sin
  reejecutar. Y es lo esperable: la campaña evalúa con `-x`, **204 de 256
  mutantes mueren** (79,7 %) y abortan la suite en el primer fallo. El caso que
  RM2 caza —F-034, 18 mutantes en 111 s— no se parece a este.
- `256 × 32,7 = 8371 ≈ 8368,3`: internamente coherente.
- **Regla de los 60 segundos: NO se reejecuta la campaña**, porque el «Tiempo
  total» declarado (8368,3 s) supera con mucho el umbral. **Queda dicho
  explícitamente**, como manda C4 bis: campaña no reejecutada, 2 h 19 min según
  el informe. En su lugar se aplican el recálculo puro (§2.1-2.2), RM1-RM6 y la
  reverificación de mutantes concretos de §2.6.
- Sin cabecera «⚠ CAMPAÑA NO VÁLIDA». «Sin veredicto (base rota)» = **0**.
  Timeouts = **0**. Las **seis líneas base** salieron en verde y están impresas.

### 2.5 · RM5 — reproducción de UN equivalente, elegido por el reviewer

Elijo **`relaciones_sql.py:282`**, `int(UMBRAL_AVISO_COBERTURA * 100)` →
`int(... * 101)`. Reproducido de verdad, no leído: el mutante se generó con
`harness.mutacion.generar_mutantes` (aparecen dos en esa línea; se tomó el
`[entero]`), se aplicó con `aplicar_mutante` a una copia en memoria del módulo,
se cargaron original y mutante como dos módulos distintos y se comparó la salida
de `interpretar_relacion` en once combinaciones, **ocho de ellas dentro de la
rama `AVISO`** que es la única donde la línea se ejecuta:

```
casos que entran en la rama AVISO: 8 de 11
ejemplo AVISO original: AVISO x.y.a -> z.w: une, pero poco. 1 de 10 valores casan (10%), por debajo del 50 % ...
ejemplo AVISO mutado  : AVISO x.y.a -> z.w: une, pero poco. 1 de 10 valores casan (10%), por debajo del 50 % ...
int(0.5*100)= 50 int(0.5*101)= 50
SALIDAS IDENTICAS: True
```

**Equivalente confirmado.** La advertencia que deja el implementer —si el umbral
deja de ser 0,5 el mutante puede volverse matable— es correcta y está escrita.
Añado el dato que la sostiene: `tests/test_f006_relaciones.py:308` afirma
`f"{int(UMBRAL_AVISO_COBERTURA * 100)}" in escasa`, es decir **calcula la misma
expresión que vigila**, así que ese test tampoco podría matarlo. No es un
defecto aquí (no hay nada que matar), pero es el antipatrón que esta feature ya
aprendió a evitar en las constantes.

**Los otros dos equivalentes (`ensure_ascii=False → True`) no los reproduje
contra la base** —no ejecuto consultas contra producción para una review—, pero
**sí verifiqué desde el árbol lo que hace verdadera la demostración**, que es
más fuerte que repetirla:

1. `sql/ddl/01_diccionario.sql:59` declara `ficha JSONB NOT NULL` y `:98`
   declara `datos JSONB NOT NULL`. Los dos `json.dumps` en cuestión
   (`diccionario_sql.py:142` y `:277`) alimentan exactamente esas dos columnas.
   PostgreSQL **parsea** el JSON al insertarlo en `jsonb` y decodifica los
   escapes `\uXXXX`: lo almacenado y lo que recupera el MCP es idéntico.
2. Comprobé que **ningún hash depende del texto serializado**: el único
   `hashlib.sha256` del proyecto (`cargador_yaml.py:203`) se calcula sobre los
   **bytes de los YAML**, no sobre el JSON. `ensure_ascii` no puede mover
   `hash_fuente`.

Con eso, el único efecto observable es el texto en el cable y al depurar, que es
lo que dice el implementer. **Los tres equivalentes se sostienen.**

### 2.6 · RM4 — reverificación de mutantes concretos, por el reviewer

`git worktree add --detach` en mi scratchpad desde `6332995`, `.env` volcado con
`harness.mutacion_paralela.volcar_variables` (25 variables), mutantes aplicados
con el **propio mutador** (nunca `sed`), `PYTHONDONTWRITEBYTECODE=1`, sin caché
de pytest. **Línea base primero**, para no repetir el error de diagnóstico de la
tarde del 26:

```
base: exit=0 | 189 passed, 3 skipped in 41.16s
```

| Mutante | Por qué lo elijo | Veredicto |
|---|---|---|
| `inventario.py:234` [not] #0 (quita el `not` a `avisos_columnas`) | **es el falso muerto confirmado** de `control_mutacion_F-006.md` | **MUERTO** (2 failed) |
| `inventario.py:234` [not] #1 (quita el 2.º `not`) | mismo sitio | **MUERTO** (3 failed) |
| `unicidad_sql.py:189` [not] | superviviente nº 52 de la lista | **MUERTO** (3 failed) |
| `diccionario.py:299` [booleano] `frozen=True→False` | superviviente nº 6 | **MUERTO** (1 failed) |
| `diccionario.py:299` [booleano] `slots=True→False` | superviviente nº 7 | **MUERTO** (1 failed) |

**5 de 5 muertos, con la línea base verde delante.** Worktree eliminado; `git
worktree list` y `git status` limpios después.

Lo importante del primero: el mutante que la campaña paralela declaró MUERTO
siendo superviviente **hoy está muerto de verdad**, y lo he comprobado yo. El
implementer lo cazó porque al verificar los 17 encargados verificó también los
**5 mutantes vecinos** que el mutador genera en esas mismas líneas y que no
figuraban en la lista (`impl_F-006_detalle.md` L5208, fila «+5»). Es el mismo
método que salvó los dos supervivientes que el líder se dejó fuera del encargo:
**no fiarse de la lista, barrer el sitio**.

### 2.7 · RM3 y RM6

- **RM3** (un equivalente no puede salir MUERTO): revisados los tres declarados
  equivalentes, ninguno figura entre los muertos. No hay contradicción.
- **RM6** (matar un mutante quitando código defensivo): **no aplica**. Los 49
  se mataron **sin tocar una línea de producción** —el diff `99e2335..HEAD` lo
  demuestra: los únicos ficheros de código que cambian son cinco de `tests/`—.
  No se retiró ninguna guarda. Es exactamente lo contrario del patrón que RM6
  vigila, y merece decirse en positivo: los 52 eran **huecos de test**, no
  defectos de código.

## 3 · Mi criterio sobre LA LIMITACIÓN (pregunta explícita del líder)

**La pregunta:** la campaña paralela produce algún falso muerto; los 204 muertos
no son una lista cerrada; ¿basta para un `critico`?

**Mi respuesta: SÍ, basta para cerrar F-006 — y no bastaría sin las dos
condiciones que ya se cumplen.** Lo razono, porque un «sí» sin razones aquí no
vale nada.

**Lo que hace aceptable el riesgo residual:**

1. **La dirección peligrosa está tapada donde importa.** Un falso muerto esconde
   un superviviente. Pero **todo lo que se declaró muerto por los tests nuevos se
   reverificó EN SERIE**, no por campaña paralela; y yo he reverificado cinco
   más, también en serie y con línea base. El riesgo no está en lo que se
   arregló: está en los 204 que la campaña paralela juzgó y nadie volvió a mirar.
2. **El único caso confirmado se persiguió hasta matarlo.** `inventario.py:234`
   no se documentó y se dejó: se cazó, se explicó y hoy muere. Verificado por mí.
3. **Está declarado por escrito, con dueño y con consecuencia práctica.**
   `control_mutacion_F-006.md` no maquilla el cero de la muestra de control:
   escribe que doce casos no descartan una tasa baja y que **52 es un suelo, no
   una lista cerrada**. Eso está fichado en **F-041** (`pending`, prioridad 2,
   `critico`) y en el `BACKLOG.md`, con la regla operativa —«lo que una campaña
   paralela declare MUERTO hay que reverificarlo en serie antes de cerrar un
   `critico`»— escrita para la próxima feature. Un instrumento con un defecto
   medido, acotado y fichado es utilizable; uno con un defecto no declarado, no.

**Lo que NO acepto, y quede dicho por si vuelve:** este razonamiento **no vale
como precedente general**. Si en la próxima feature `critico` los supervivientes
se matan y se dan por muertos **por una segunda campaña paralela**, el argumento
se cae entero y el veredicto sería otro. Lo que aquí salva la campaña no es que
el defecto sea pequeño: es que **el paso decisivo —confirmar la muerte— se hizo
en serie**. Mientras F-041 no esté, esa es la condición.

**Una hipótesis que sigue sin demostrarse** y conviene no perder: las líneas
base bajo contención tardaron 462-486 s frente a 216-268 s en solitario. La
sospecha (algún test cae bajo contención y `-x` lo convierte en «muerto») **no
está probada**: no se ha identificado el test culpable ni descartado la
interferencia entre los seis worktrees, que comparten `.git` y el mismo `.env`
apuntando a la misma base. Es trabajo de F-041 y aquí solo lo dejo apuntado.

## 4 · Lo que SÍ bloquea: el papeleo no dice lo que dice el árbol

Y esto es lo que duele, porque es el defecto que ya quemó dos veces a esta
feature: no el contenido, sino **el documento que lo cuenta**.

### H1 · Los 52 análisis siguen literalmente en `PENDIENTE`

`progress/mutacion_F-006.md` tiene **52 secciones de superviviente y las 52
dicen**:

```
#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?
```

Contadas: 52 encabezados `#### Análisis (PENDIENTE del implementer)` y 104
apariciones de la palabra `PENDIENTE`. **Ni una sola completada**, y el informe
no lleva ningún puntero a dónde vive el análisis.

C4 bis es explícito: «Cada superviviente de esa campaña tiene su sección de
análisis **completada** (ninguna en `PENDIENTE`)». Es un checkbox vacío.

El análisis **existe** —está en `impl_F-006_detalle.md`, y es bueno—, así que
esto no es trabajo de investigación: es trabajo de escritura. Pero no es
cosmético. Quien abra `mutacion_F-006.md` dentro de seis meses —o quien lo lea
sin poder preguntar, que es el usuario que esta feature construye— lee un
informe que dice que **nadie analizó nada**. Es una afirmación falsa servida a
quien decide con ella.

### H2 · `impl_F-006.md` contradice al árbol en su sección «Evidencias»

El informe resumen —el que nombra C4 bis— dice hoy, en §2:

| Lo que dice `impl_F-006.md` | Lo que mide el árbol |
|---|---|
| Tests: **2305 pasados, 125 saltados** | **2473 pasados, 128 saltados** |
| Cobertura: **1 de 1 línea** | **33 de 33 líneas** |
| Tiempo de la suite: **466,09 s** | **603,92 s** |
| Mutación: **«NO MEDIDO, a propósito»** | **256 mutantes, 204 muertos, 52 supervivientes, 52/52 resueltos** |

Y además:

- **§1, fila T41**: «⬜ **pendiente y no declarable**: ver §4 (feature F-041)».
  Falso: la campaña está hecha, es válida y la he verificado.
- **§1, fila T42**: «✅ verde el 2026-08-26: 2305 pasados, 125 saltados».
  Desfasado.
- **§4** entero, «Mutación: por qué no hay número», sigue diciendo «Hasta que
  F-041 esté hecho **no se declara ningún número**». Ya no es cierto: el defecto
  que lo justificaba (línea base roja en el worktree) lo arregló el arnés 1.7.7,
  y esa es precisamente la novedad de esta pasada.
- **Falta el nº de workers en «Evidencias»**, que C4 bis exige de forma
  literal («sin él no se puede calcular el coste por mutante»). La palabra
  `workers` no aparece **ni una vez** en `impl_F-006.md` ni en sus 5768 líneas
  de anexo. El 6 solo consta en el informe generado por la herramienta.
  *Atenuante*: el dato existe y viene de la herramienta, que es la fuente
  fiable; por sí solo no justificaría un rechazo.

Solo **§9** (la última línea del fichero) está al día. Es decir: el mismo
documento afirma en §2 que la mutación no se midió y en §9 que hay 52/52
resueltos. **Un informe que se contradice a sí mismo no es evidencia.**

Nota de contexto, no excusa: `impl_F-006.md` está en **219/220 líneas**, al
filo de la puerta de tamaño. Corregir §1, §2 y §4 exige podar; §4 entero (diez
líneas sobre por qué no hay número) ya sobra y paga el arreglo.

### H3 · `tasks.md`: tareas hechas sin marcar, tareas entregadas sin anotar

C5 exige todas las tareas `[x]` con su commit `F-006 Tn:`. Estado real:

| Tarea | En `tasks.md` | En el árbol |
|---|---|---|
| **T41** | `[ ]` | **hecha**, commit `e89f71f F-006 T41: la campana de mutacion, entera y por primera vez valida` |
| **T42** | `[ ]` | **hecha**, `init.sh` exit 0 verificado por mí |
| **T29-T31** | `[ ]` a secas | **no existen en código** (verificado, H4) y el bloque I ya no es condición de cierre: hay que anotarlo, no dejarlo en blanco |
| **T32-T34** | `[ ]` a secas | **entregadas a F-034** el 2026-08-25; `impl_F-006.md` §1 lo dice, `tasks.md` no |
| **T38** | `[ ]` | bloqueada legítimamente, pero su propia cláusula de escape dice «se entrega a `mcp-bbdd` **y se anota como tal**», y esa anotación no está: `impl_F-006.md` solo dice «⛔ bloqueada» |
| **T43** | `[ ]` | deuda registrada; la decisión es del humano |

Ninguna de estas tareas necesita trabajo de ingeniería. Necesitan que el fichero
diga lo que pasó. Y dos commits `F-006 T42:` (`143fa07`, `4d336fb`) hablan en
realidad de matar supervivientes, que es T41: mal etiquetados.

### H4 · La spec promete a F-034 un mecanismo que no existe

Este es el hallazgo con consecuencias fuera de F-006, y por eso lo separo.

**Verificado en el árbol** (`grep` sobre todo el repositorio):

- `build_readonly_grant_statements` (`etl_sigrid/infrastructure/postgres/grants.py:24`)
  tiene la firma `(readonly_role, owner_role, schemas, *, database=None)`:
  **no existe `revocar_en`** (T29/R31).
- **`PG_REVOKE_FUERA_DE_CONSUMO` no aparece en ningún fichero** del repositorio
  (T30/R32).
- `config/settings.py:81` `DEFAULT_CONSUMPTION_SCHEMAS` sigue siendo los
  **nueve** esquemas: `mart,cierre,compras,maestro,retenciones,raw,stg,aux,_meta`
  (T31/R30), con `raw` y `stg` dentro.
- No existe `tests/test_f006_grants.py`, y **R30, R31, R32, R33 y R34 no tienen
  ni un test trazable** (comprobado sobre los 41 requisitos EARS: los únicos sin
  test son R30-R38; R35 y R36 sí lo tienen pero nombrados `test_f006_t35_*` /
  `test_f006_t36_*` en vez de `test_f006_rNN_*`, y R37/R38 son `MANUAL`).

**Nada de eso bloquea por sí mismo**: el humano decidió el 2026-08-25 («del BI
olvídate») que DA-3 se resuelve por su opción B, y `requirements.md` recoge la
consecuencia: «el **bloque I deja de ser condición de cierre de F-006** y pasa a
ser entrega documentada a F-034». **Confirmo esa lectura: T29-T31 no bloquean.**

Lo que sí bloquea es que **tres documentos siguen afirmando lo contrario**:

1. `requirements.md` marca **R30 «vigente»**, **R31 «vigente: se construye y se
   prueba»** y **R33 «vigente»**. Solo R32 y R34 llevan la enmienda. Un
   requisito «vigente» sin código y sin test es un checkbox de C4 vacío.
2. `design_detalle.md` §11.4 dice que F-006 entrega a F-034 «la lista de consumo
   ya estrechada y el mecanismo de `REVOKE` **construido y probado**, que es
   exactamente la pieza que F-034 necesitaría y que hoy no existe».
3. **Peor**, porque lo lee otra feature: la ficha de **F-034** en `BACKLOG.md`
   y en `harness/features.json` dice que recibe de F-006 «aplicar los `REVOKE`
   que F-006 deja **CONSTRUIDOS Y APAGADOS** (`PG_REVOKE_FUERA_DE_CONSUMO`)».

Si F-006 se cierra hoy, F-034 arranca buscando una variable de entorno, un
parámetro y una lista estrechada que **no existen**, con su propia spec
diciéndole que sí. Es el mismo tipo de fallo que esta feature entera se dedica a
impedir: una ficha que describe mal un objeto no es documentación incompleta, es
una afirmación falsa servida a quien decide con ella. Aquí el lector no es un
agente MCP: es el spec-author de F-034.

**El arreglo es documental**, no de código, y el humano ya tomó la decisión de
fondo: basta con que R30/R31/R33 lleven la misma enmienda que R32/R34, que
§11.4 diga que el mecanismo **no** se construyó, y que la ficha de F-034 diga
que recibe el trabajo entero y no solo la activación. Salvo que el humano
prefiera lo contrario —construir T29-T31 aquí— y entonces lo que sobra es la
enmienda.

## 5 · Lo que sí está bien, y conviene que conste

- **C3, arquitectura y convenciones: limpio.** Los ocho módulos del alcance y
  los ficheros nuevos de test llevan su ruta relativa en la primera línea. Cero
  `print()` de debug. Cero TODO/FIXME sin contexto (los únicos aciertos del
  `grep` son la palabra «TODOS»). `domain/diccionario.py` y `domain/inventario.py`
  importan **solo** `re`, `collections.abc`, `dataclasses` y entre sí: dominio
  sin infraestructura. El DDL vive en `sql/ddl/01_diccionario.sql`, con la
  numeración `NN_nombre.sql` y documentado en `docs/ARCHITECTURE.md:230`.
- **Las tres trampas del dominio Sigrid están escritas en el diccionario**, que
  es donde tienen que estar para el agente que no puede preguntar:
  `fasnum`/`fas` (`00_global.yaml:263` «Nunca cruces las dos lecturas»;
  `stg.yaml:576` «en los ámbitos reales es el MES y en los master el número de
  versión: la misma columna significa dos cosas»);
  `importe_origen`/`importe_mes` (regla dura en `00_global.yaml:57`, con la
  medición que la sostiene en `mart.yaml:61`: `SUM(importe_mes)` iguala al
  último `importe_origen` en 200 de 200 series); y las **versiones master
  duplicadas** (`stg.yaml:10` «conviven TODAS las versiones master», más el
  objeto `stg.version_master_vigente`).
- **Barrido de datos sensibles** sobre los 37 ficheros del diff `dev...HEAD`,
  con los patrones `password=`, `pwd=`, `secret=`, `api[_-]?key`,
  `BEGIN … PRIVATE KEY`, GUID (`8-4-4-4-12`), `Server=…Password`,
  `postgres://user:pass@`, IPs privadas `10.*`/`192.168.*` y cadenas base64 de
  40+ caracteres: **cero hallazgos**. El único acierto de `pwd=` es
  `runbook_postgres_azure.md:141`, `-v app_pwd="$APP_PWD"`, que es una
  referencia a variable de shell y no un valor.
- **C3 bis: N/A justificado.** El diff no toca ningún fichero de
  `docs/referencia/`. (El barrido de secretos se hizo igual, arriba.)
- **C4 ter: N/A y sin nada que justificar.** No existe
  `harness/rutas_sensibles.json` en este repositorio, que es el caso
  mayoritario que el propio checkpoint declara N/A.
- **T37 confirmada hecha.** `azure-apps/datamart_seg_anual.md`, commit
  `2e9bee8` del 2026-08-22. No la reverifiqué en el repositorio `azure-apps`
  (está fuera de este árbol): **lo digo en vez de darla por buena en silencio**.
  Lo que sí puedo verificar es que `docs/ARCHITECTURE.md` enlaza a `azure-apps`
  en vez de duplicarlo, y lo hace
  (`test_f006_t36_arquitectura_enlaza_azure_apps_sin_duplicarlo`).
- **T28, T35 y T36 verificadas**: `tests/test_f006_docs.py` existe con 12 tests
  que **derivan** lo que el documento afirma de la fuente que manda (los
  `@cli.command` de `main.py`, los `CREATE TABLE` del DDL) en vez de comprobar
  que una frase esté escrita. Es el método correcto.
- **La fase RED está pegada con traza real** en todas las tandas, incluidas las
  dos últimas: `cargador_yaml.py:361` (`assert 2024 == '2024'` y
  `assert '' is None`) y `relaciones_sql.py:278` (los tres casos frontera
  parametrizados). No hay ni un «se siguió TDD» sin traza.
- **C2 limpio**: una sola feature `in_progress`, rama correcta,
  `progress/current.md` describe solo la sesión del 2026-08-26.

## 6 · Lo que NO he podido verificar, y así queda escrito

- **Que `_meta` sirva hoy la versión 9.** Exige la base; no ejecuto consultas
  contra producción para una review. El hash del árbol es el que reporta el
  humano, pero la medición es suya.
- **La demostración de los dos equivalentes `ensure_ascii` contra la base
  real.** Verifiqué en su lugar las dos premisas desde el árbol (columnas
  `JSONB` y hash sobre los YAML, §2.5), que es lo que las hace verdaderas.
- **T19, T27, T32-T34, T38, T39**: verificaciones `MANUAL (humano)`. No se
  reetiquetan.
- **T37 en el repositorio `azure-apps`** (fuera de este árbol).
- **Los 204 muertos de la campaña, uno a uno.** La regla de los 60 segundos no
  obliga y reejecutar cuesta 2 h 19 min de máquina. Verifiqué cinco (§2.6) más
  el recálculo puro de los totales (§2.1-2.2).

## 7 · Propuesta de mejora del protocolo (no aplicada)

Para `CHECKPOINTS.md` y `.claude/agents/implementer.md`, a decisión del humano:
**cuando el análisis de los supervivientes no quepa en el informe de la campaña,
el informe debe llevar en su cabecera un puntero al fichero donde vive**, y el
checkbox de C4 bis debería aceptar ese puntero como «análisis completado». Hoy
la regla obliga a rellenar 52 secciones a mano en un fichero generado por la
herramienta, que es justo el trabajo que nadie hace y por eso se queda en
`PENDIENTE`. Lo que la regla quiere impedir —que un superviviente se cierre sin
juicio— se consigue igual con el puntero, y se consigue de verdad.

---

# 21ª pasada · 2026-08-27 — los cuatro hallazgos cerrados, y el portero que se aflojó de más

**Revisión INCREMENTAL desde `735b53a`** (mi commit de la 20ª pasada) hasta
`HEAD = 0c6d5f1`. Lo aprobado y verificado en la 20ª —la campaña, los 52
supervivientes, los tres equivalentes, la arquitectura, el barrido de secretos—
queda dado por bueno y no se vuelve a leer, con una excepción que sí se
recomprueba entera: **que ninguno de los ocho ficheros del alcance haya
cambiado**. No ha cambiado ninguno (`git diff 99e2335..HEAD -- etl_sigrid/`
vacío), así que RM1 sigue en pie y la campaña sigue midiendo lo que reviso.

El delta son 9 ficheros: `progress/` (4), `specs/` (3), `BACKLOG.md`,
`harness/features.json` y **`tests/test_f003_infra.py`**, que es el único código.

## 1 · H1 — los 52 análisis: CERRADO, y verificado uno a uno

No me basta con que la palabra `PENDIENTE` haya desaparecido, así que verifiqué
la estructura entera por programa:

```
PENDIENTE restantes:            0
secciones de superviviente:    52
encabezados de análisis:       52
bloques sin puntero o sin decisión: 0
```

**El reparto de decisiones cuadra con lo que verifiqué en la 20ª pasada**: 49
`MUERTO por test nuevo` + 3 `MUTANTE EQUIVALENTE` = 52.

Y lo que de verdad importa: **los punteros no son decorativos**. Se usan doce
líneas del anexo y **las doce caen sobre un encabezado real** de
`progress/impl_F-006_detalle.md` —fichero que este delta **no toca**, así que la
numeración sigue valiendo—:

| Puntero | Cae sobre |
|---|---|
| L5136 / L5196 | `# Anexo · 17 supervivientes…` / `## Verificación: cada mutante aplicado…` |
| L5355 / L5417 | `## Grupo 1 · los 20 frozen/slots…` / `### Fase RED · los 20 mutantes…` |
| L5463 / L5497 | `## Grupo 2 · las 11 constantes…` / `### Fase RED · los 11 mutantes…` |
| L5576 / L5584 / L5599 | `## Los tres mutantes equivalentes…` / `### 1 · relaciones_sql.py:282` / `### 2 y 3 · diccionario_sql.py:142 y :277` |
| L5626 / L5638 / L5688 | `## Los dos supervivientes que se quedaron fuera…` / `### 1 · cargador_yaml.py:361` / `### 2 · relaciones_sql.py:278` |

Y **cada superviviente apunta al sitio que le toca**, no a un puntero genérico:
20 bloques de `frozen`/`slots` → L5355+L5417; 16 → L5136+L5196; 11 de constantes
→ L5463+L5497; los 3 equivalentes → L5584 y L5599; los 2 del descuido → L5638 y
L5688. Comprobado por programa contra la lista esperada: **0 discrepancias**.

## 2 · H2 — el informe deja de contradecirse: CERRADO

`progress/impl_F-006.md` §2 trae ahora los cuatro números reales **y una fila
propia para los workers**, que era lo que C4 bis exigía literalmente y faltaba:

> **Workers de la campaña · 6** — «con ellos el coste real por mutante es
> 32,7 s × 6 = **196,2 s**, frente a una línea base de ~470 s: coherente, porque
> el 80 % de los muertos para con `-x`».

Es exactamente la aritmética que hice yo por mi cuenta en la 20ª pasada, con el
mismo resultado. §1 marca T41 y T42 como hechas con su commit; §4, que decía
«por qué no hay número», está reescrita y ahora cuenta la campaña, sus totales y
**la limitación con su dueño (F-041)**; y la lista de «fuera del alcance» ya no
arrastra T41.

## 3 · H3 — `tasks.md` deja de contradecir al árbol: CERRADO

T41 y T42 pasan a `[x]` con su evidencia pegada. Y lo que me parece bien
resuelto: **T29-T31 siguen en `[ ]` a propósito**, con un aviso de cabecera de
bloque que dice por qué —«las siete tareas siguen en `[ ]` porque **no están
hechas**, y eso es lo que hay que leer aquí»— y con el estado medido contra el
árbol. Eso es preferible a marcarlas `[x]` por estar entregadas: un `[x]` habría
vuelto a sugerir que el mecanismo existe.

T32-T34 llevan su marca de entrega a F-034; **T38 la de entrega a `mcp-bbdd`**,
que es lo que su propia cláusula de escape exigía y no estaba; y la tabla de
tareas con firma 🔏 dice ahora que **ninguna de las cuatro se ejecutó**.

Detalle menor bien tratado: los commits `4d336fb` y `143fa07` van etiquetados
`F-006 T42:` siendo trabajo de T41. **No se reescribió el historial**; se dejó
dicho en una nota de trazabilidad. Es la decisión correcta.

## 4 · H4 — la promesa falsa a F-034: CERRADO, y bien cerrado

Decisión del humano del 2026-08-27: **enmendar los documentos, no construir el
mecanismo**. Reverificado contra el árbol que sigue sin existir (`grants.py` sin
`revocar_en`, `PG_REVOKE_FUERA_DE_CONSUMO` en ningún fichero,
`config/settings.py:81` con los nueve esquemas), que es lo que las enmiendas
afirman.

- `requirements.md`: **R30, R31 y R33 enmendados** diciendo «NO se hizo» / «NO se
  construyó» / «sin `REVOKE` que gobernar», los tres con la entrega a F-034.
- `design_detalle.md` §11.4 reescrito, y **conserva la trampa que importa**: que
  el rol `mcp_sigrid_dm_ro` lo comparten hoy el MCP y Power BI, así que encender
  los `REVOKE` sin verificar antes qué lee Power BI le rompe los informes.
- La ficha de **F-034**, en `BACKLOG.md` **y** en `harness/features.json` (las
  dos, que es lo que hay que comprobar porque una se genera de la otra): pasa de
  «aplicar los `REVOKE` que F-006 deja CONSTRUIDOS Y APAGADOS» a «**CONSTRUIR Y**
  aplicar los `REVOKE`, que F-006 **NO dejó construidos** pese a lo que decía su
  spec», con la verificación pegada y con «**T29, T30 y T31 llegan aquí POR
  CONSTRUIR**».

Quien recoja F-034 ya no arranca buscando una pieza que no está.

**Nit, no hallazgo.** R32 sigue redactado como «queda **APAGADO** y se entrega a
F-034», que insinúa un mecanismo que existe y está desactivado. Es la única fila
del bloque sin enmendar. No puede engañar a nadie hoy —R30, R31 y R33 dicen lo
contrario en la fila de al lado, y el aviso de cabecera de `tasks.md` remata con
«no se construyó, **ni siquiera apagado**»—, pero si algún día se lee esa fila
suelta, vuelve el problema. Una línea de arreglo.

## 5 · El cambio en el guardián de secretos, que me pediste que juzgara

Lo primero, y va por delante de la crítica: **el diagnóstico es correcto, la
decisión de no tocar mi informe es la correcta, y la versión fácil se descartó
por la razón correcta.** Eximir la comilla invertida a secas habría dejado pasar
un secreto citado como código, y quien lo arregló lo vio, lo escribió y lo fijó
con un test. Eso es exactamente cómo se toca un guardián.

**Pero el arreglo llega más lejos de lo que quería, y lo he medido.**

El patrón exime ahora la comilla invertida cuando **no la sigue** un carácter de
`[A-Za-z0-9_./+-]`. La intención escrita es «cuando cierra el código en línea,
sin valor pegado detrás». El problema es que **un valor puede empezar por un
carácter que no está en esa clase**, y entonces la exención se lo traga.

Probado con el patrón de antes y el de ahora, sobre el árbol:

```
ANTES  AHORA  caso
 True  False  'con los patrones `password=`, `pwd=`'      <- el falso positivo, resuelto
 True   True  secreto en backticks que empieza por letra
 True  False  secreto en backticks que empieza por !      <- REGRESION
 True  False  ... por @, &, ~, (, ^, :, [, |              <- REGRESION (8 mas)
```

**Nueve casos que el guardián cazaba y ya no caza.** Y no es la clase
inofensiva: una contraseña que empieza por símbolo es, si acaso, **más** probable
que una que empieza por letra.

Hay un segundo defecto, en la dirección contraria: **el falso positivo no está
resuelto del todo**. Una cita seguida de punto —`` `…=` `` y punto y seguido,
que es como termina media frase de un informe— **sigue disparando** el guardián.
Es el mismo caso que lo puso en rojo, con otra puntuación detrás.

Total sobre 17 casos de prueba: **el patrón actual falla 10** (9 por defecto de
sensibilidad, 1 por falso positivo).

**La causa es la de siempre en esta feature**, y por eso la señalo en vez de
dejarla pasar: los ocho casos parametrizados fijan **las dos caras que el autor
pensó** —cita con coma detrás, secreto que empieza por letra— y no barren el
vecindario de la segunda. Es la misma lección que ya se cobró dos veces aquí:
*«aquellos dos se taparon a mano y el defecto sobrevivió en las doce clases de al
lado»*. La respuesta buena fue la de los `frozen`/`slots`: un barrido derivado,
no una lista escrita a mano.

**Alternativa verificada**, por si sirve —eximir la comilla solo cuando la sigue
fin de línea o puntuación de prosa—:

```
r"(?i)\bpassword\s*=\s*(?![#$%<*{\"'\s]|secretref:|keyvaultref:|`(?=[\s,;.)\]]|$))\S"
```

Sobre los mismos 17 casos: **0 fallos**. Caza los nueve que ahora se escapan y
además resuelve la cita terminada en punto. No la aplico —no es mi trabajo
escribir el código—, pero la dejo medida para que el arreglo no cueste otra
investigación.

**Y lo que hay que tener en la cabeza al ponderar esto**, porque cambia el
tamaño del problema: el patrón **ya era poroso antes** para valores que empiezan
por símbolo. `password=%x`, `password=#x`, `password=<x` y `password='x'` estaban
exentos **sin ninguna comilla invertida**, desde siempre. Lo que este cambio hace
no es abrir una clase nueva de agujero: es **ensanchar uno que ya estaba ahí**,
de ocho símbolos a unos veinte, y solo dentro de comillas invertidas.

**Comprobado además que no hay ningún secreto de verdad en el árbol.** Barrí el
delta `dev...HEAD` con patrones **más amplios que los del guardián** —GUID, clave
privada, `AccountKey`, SAS, cadena de conexión con credencial, IP privada,
`x-functions-key` y un patrón de contraseña deliberadamente más laxo que el
oficial—. Cuatro aciertos, **los cuatro autorreferenciales**: `postgres://user:pass@`
es la lista de patrones de mi propio informe, y `hunter2` / `SuperSecreta1` son
los valores de pega del test nuevo. **Cero credenciales.**

## 6 · El papeleo que volvió a quedarse atrás (y por qué no bloquea)

Tres afirmaciones del delta que **el árbol contradice**, las tres nacidas en esta
misma sesión y superadas por commits posteriores de la propia sesión:

| Dónde | Qué dice | Qué es |
|---|---|---|
| `progress/impl_F-006.md:83` | «El portero está **HOY en rojo**» | verde: `init.sh` exit 0 |
| `progress/current.md:4` | encabezado «🔴 LO PRIMERO: `init.sh` está **EN ROJO**» | lo desmiente **su propio párrafo siguiente**, que dice «el portero está en verde» |
| `progress/current.md:41-54` | «desde `735b53a` está en rojo», «impl **218**/220», «**H4 esperando decisión** del humano», «Falta H4, el portero en verde» | H4 cerrado en `31152c0`; impl 219/220 |

**Por qué esto no bloquea, y quiero que la diferencia con la 20ª pasada quede
escrita, porque es la misma clase de defecto y merezco que me la exijan.**

En la 20ª, lo que `impl_F-006.md` falseaba era **la evidencia de la feature**:
decía que la campaña de mutación no se había medido. Cerrar con eso habría
metido en `history.md`, para siempre, una afirmación falsa sobre aquello en lo
que se apoya un cierre `critico`.

Hoy el informe es exacto en todo eso —lo he reverificado— y lo que queda mal es
**el estado transitorio del portero en un commit intermedio de la sesión que
cierra**. Nadie que lea F-006 dentro de seis meses se lleva una idea equivocada
de qué se construyó ni de qué se verificó. Es bookkeeping caducado, no evidencia
falsa. Se arregla borrando cuatro frases, y **la próxima sesión que toque
`current.md` lo hace de todos modos**.

Aplicar aquí el mismo rechazo sería, además, caer justo en lo que esta feature ya
tiene medido y escrito en su propia deuda (T43): *cerrar seis defectos de matiz
en la décima pasada generó tres nuevos de la misma clase, así que otra ronda no
acerca al objetivo, solo cambia qué frase está mal*.

## 7 · Recorrido de checkpoints, y qué cambia respecto a la 20ª

| CP | 20ª | 21ª | Por qué |
|---|---|---|---|
| C1 | `[x]` | `[x]` | `init.sh` exit 0 |
| C2 | `[x]` | `[x]` con reserva | Una sola `in_progress`, rama correcta. `current.md` **no** trae restos de sesiones anteriores —lo que trae son restos de un estado intermedio de ESTA—, así que el checkpoint literal se cumple; la reserva queda en §6 |
| C3 | `[x]` | `[x]` | Ningún fichero de producción del ETL cambió en el delta. El único código tocado es `tests/test_f003_infra.py` (§5) |
| C3 bis | N/A | N/A | El delta no toca `docs/referencia/`. Barrido de secretos hecho igual: cero (§5) |
| C4 | `[ ]` | `[x]` | R30/R31/R33 dejan de estar «vigentes» sin código: enmendados diciendo que no se hicieron y entregados a F-034 (§4). Ya no hay requisito vigente sin test |
| C4 bis | `[ ]` | `[x]` | Los 52 análisis, completados y con puntero verificado (§1); «Evidencias» con los cuatro números **y los workers** (§2). RM1-RM6 siguen cumpliéndose: los 8 ficheros del alcance no han cambiado |
| C4 ter | N/A | N/A | No existe `harness/rutas_sensibles.json` |
| C5 | `[ ]` | `[x]` | T41 y T42 `[x]` con su commit; el bloque I y T38 con su entrega anotada y su estado real medido (§3). T43 queda `[ ]` **justificado**: el registro está hecho y lo que falta es una decisión del humano, igual que una verificación `MANUAL` |

## 8 · Lo que exijo antes de marcar `done`, y lo que NO he verificado

**Antes de `done`** (no reabre la review; es condición de C5, «`features.json`
refleja el estado real»):

1. **Fichar el hallazgo del guardián** (§5) como entrada propia de backlog, con
   los nueve casos medidos y la alternativa verificada. Si esto no se ficha, el
   siguiente reviewer debe tratarlo como abierto: un control de secretos más
   flojo que ayer no puede quedar vivo solo en un informe de review que nadie
   reabre.

**Recomendado, no exigido:** borrar las cuatro frases caducadas de §6 y enmendar
la fila R32 del nit de §4.

**No verificado en esta pasada, y así queda escrito:**

- **No reejecuté la campaña de mutación** ni volví a reverificar mutantes: los
  ocho ficheros del alcance no han cambiado desde `99e2335`, así que vale lo
  medido en la 20ª (recálculo puro 3126/256 exacto, 52/52 supervivientes
  reproducibles, 5 mutantes reevaluados en serie con línea base verde).
- **No releí el cuerpo de F-006** (fichas, YAML, SQL, dominio): revisión
  incremental, y el delta no lo toca.
- Siguen sin ser verificables desde este árbol: que `_meta` sirva la versión 9,
  T37 en el repositorio `azure-apps`, y las `MANUAL (humano)` T19, T27, T32-T34,
  T38 y T39.
