<!-- progress/review_F-006.md -->
# F-006 · Review — el diccionario semántico (resumen)

> El detalle de las veintiuna pasadas —hallazgos, citas de código y las
> reverificaciones— vive en [`review_F-006_detalle.md`](review_F-006_detalle.md)
> (5615 líneas), que es donde está lo que aquí solo se resume.

## Veredicto · 21ª pasada, 2026-08-27

**Revisión INCREMENTAL desde `735b53a`** (mi commit de la 20ª). `HEAD = 0c6d5f1`.
Lo verificado en la 20ª queda dado por bueno, con una excepción que sí se
recomprobó entera: que **ninguno de los ocho ficheros del alcance haya cambiado**
desde el SHA de la campaña. Ninguno ha cambiado, así que RM1 sigue en pie.

# APROBADO

**Nivel `critico`.** Los cuatro hallazgos de mi 20ª pasada están **cerrados y
verificados contra el árbol**, no contra la lista que me pasaron. Y están mejor
cerrados de lo que pedí: donde había una salida cómoda —marcar T29-T31 como
hechas por estar entregadas— se eligió la incómoda y correcta, dejarlas en `[ ]`
con el estado real medido al lado.

**Queda un hallazgo abierto que NO bloquea el cierre y que sí exijo fichar**: el
arreglo del guardián de secretos lo aflojó más de lo que quería. Está medido en
§5 del anexo, con una alternativa verificada.

## Los cuatro hallazgos, verificados

| # | Qué era | Cómo lo comprobé | Estado |
|---|---|---|---|
| **H1** | Los 52 análisis de supervivientes, en `PENDIENTE` | Por programa: **0** `PENDIENTE`, 52 secciones, 52 análisis, **0 bloques sin puntero o sin decisión**; reparto 49 `MUERTO` + 3 `EQUIVALENTE` = 52; y **los 12 punteros `L#` caen los 12 sobre un encabezado real** del anexo, que este delta no toca. Cada superviviente apunta a **su** sección, no a una genérica: 0 discrepancias contra la lista esperada | **CERRADO** |
| **H2** | `impl_F-006.md` se contradecía y no declaraba los workers | §2 trae los cuatro números reales **y una fila propia «Workers · 6»** con la aritmética del coste por mutante (32,7 × 6 = 196,2 s frente a ~470 s de línea base) — la misma que hice yo por mi cuenta en la 20ª. §1 con T41/T42 hechas y su commit; §4 reescrita, ahora cuenta la campaña y su limitación con dueño (F-041) | **CERRADO** |
| **H3** | `tasks.md` no reflejaba el árbol | T41 y T42 a `[x]` con evidencia. **T29-T31 siguen `[ ]` a propósito**, con aviso de cabecera de bloque: «siguen en `[ ]` porque **no están hechas**». T32-T34 con su entrega a F-034; **T38 con la entrega a `mcp-bbdd`** que su cláusula de escape exigía y faltaba; la tabla 🔏 dice que **ninguna de las cuatro se ejecutó**. Los dos commits mal etiquetados se documentan en vez de reescribir el historial: correcto | **CERRADO** |
| **H4** | La spec prometía a F-034 unos `REVOKE` que nunca existieron | Reverificado que siguen sin existir (`grants.py` sin `revocar_en`, la variable en ningún fichero, `settings.py:81` con los nueve esquemas) — que es lo que las enmiendas afirman. R30/R31/R33 enmendados con «NO se hizo»; §11.4 reescrita **conservando la trampa del rol compartido**; y la ficha de F-034 **en `BACKLOG.md` y en `features.json`** (las dos) pasa a «**CONSTRUIR Y** aplicar los `REVOKE`… **T29-T31 llegan aquí POR CONSTRUIR**» | **CERRADO** |

## El cambio en el guardián de secretos: mi juicio

Me pediste que lo juzgara, y va por delante lo que está bien: **el diagnóstico es
correcto** (el escáner cazándose a sí mismo, cero credenciales), **no tocar mi
informe fue la decisión correcta**, y **la versión fácil se descartó por la razón
correcta** — eximir la comilla invertida a secas habría dejado pasar un secreto
citado como código, y quien lo arregló lo vio, lo escribió y lo fijó con un test.
Así es como se toca un guardián.

**Pero el arreglo llega más lejos de lo que quería, y lo he medido.** La comilla
se exime cuando no la sigue un carácter de `[A-Za-z0-9_./+-]`; un valor puede
empezar por un carácter fuera de esa clase, y entonces la exención se lo traga:

- **Nueve casos que el guardián cazaba y ya no caza**: una contraseña entre
  comillas invertidas que empiece por `!`, `@`, `&`, `~`, `(`, `^`, `:`, `[` o
  `|`. No es la clase inofensiva: una contraseña que empieza por símbolo es, si
  acaso, **más** probable que una que empieza por letra.
- **Y el falso positivo no está resuelto del todo**: una cita seguida de punto
  —como termina media frase de un informe— sigue disparándolo.
- Total: **el patrón actual falla 10 de 17 casos de prueba**. Una alternativa que
  exime la comilla solo ante fin de línea o puntuación de prosa **falla 0 de 17**;
  la dejo escrita y medida en §5 del anexo.

**La causa es la de siempre en esta feature**: los ocho casos parametrizados
fijan **las dos caras que el autor pensó** y no barren el vecindario de la
segunda. Es la lección ya cobrada dos veces aquí —«se taparon dos a mano y el
defecto sobrevivió en las doce clases de al lado»—, cuya respuesta buena fue la
de los `frozen`/`slots`: un barrido derivado, no una lista escrita a mano.

**Por qué no bloquea, dicho sin rodeos.** El patrón **ya era poroso** para
valores que empiezan por símbolo: cuatro de ellos estaban exentos sin ninguna
comilla invertida, desde siempre. Esto **ensancha un agujero existente**, no abre
una clase nueva; a cambio desbloquea un portero que impedía todo trabajo; y no
toca ni la evidencia, ni el código, ni los tests, ni el contrato de F-006 con
otras features. Además **verifiqué yo mismo que no hay ningún secreto en el
árbol**, con patrones más amplios que los del guardián: cuatro aciertos, los
cuatro autorreferenciales (la lista de patrones de mi propio informe y los
valores de pega `hunter2` / `SuperSecreta1` del test nuevo). **Cero credenciales.**

## Recorrido de `CHECKPOINTS.md`

| CP | 20ª | 21ª | Motivo |
|---|---|---|---|
| **C1** Arnés en verde | `[x]` | `[x]` | `init.sh` exit 0: **2.481 pasados, 128 saltados** (396,97 s), cobertura 100 % de 33 líneas, tamaño dentro |
| **C2** Estado coherente | `[x]` | `[x]` con reserva | Una `in_progress`, rama correcta. `current.md` no trae restos de sesiones **anteriores** —trae restos de un estado intermedio de esta—: el checkpoint literal se cumple, la reserva va abajo |
| **C3** Arquitectura y convenciones | `[x]` | `[x]` | Ningún fichero de producción del ETL en el delta; el único código tocado es `tests/test_f003_infra.py` |
| **C3 bis** Documentos de fuera | N/A | N/A justificado | El delta no toca `docs/referencia/`. Barrido de secretos hecho igual: cero |
| **C4** Verificación real | `[ ]` | **`[x]`** | R30/R31/R33 dejan de estar «vigentes» sin código: enmendados y entregados. **Ya no hay requisito vigente sin test** |
| **C4 bis** El rigor declarado | `[ ]` | **`[x]`** | 52 análisis completados con puntero verificado; «Evidencias» con los cuatro números **y los workers**. RM1-RM6 siguen cumpliéndose: el alcance no ha cambiado |
| **C4 ter** Rutas sensibles | N/A | N/A | No existe `harness/rutas_sensibles.json` |
| **C5** Sesión cerrada | `[ ]` | **`[x]`** | T41 y T42 `[x]` con su commit; bloque I y T38 con entrega anotada y estado real medido. **T43 queda `[ ]` justificado**: el registro está hecho y lo que falta es una decisión del humano, como una verificación `MANUAL` |

## Abierto, que no bloquea

1. **Fichar el hallazgo del guardián** (§5 del anexo) como entrada propia de
   backlog, con los nueve casos medidos y la alternativa verificada. **Lo exijo
   antes de marcar `done`**, por C5 («`features.json` refleja el estado real»):
   un control de secretos más flojo que ayer no puede quedar vivo solo dentro de
   un informe de review que nadie reabre. Si no se ficha, el siguiente reviewer
   debe tratarlo como abierto.
2. **Cuatro frases caducadas**, las tres nacidas en esta misma sesión y
   superadas por commits posteriores de la propia sesión: `impl_F-006.md:83` («el
   portero está HOY en rojo»), el encabezado `🔴 … EN ROJO` de `current.md:4`
   —desmentido por su propio párrafo siguiente— y el bloque de `current.md:41-54`
   («H4 esperando decisión», «impl 218/220»). Recomendado, no exigido: la próxima
   sesión que toque `current.md` las borra de todos modos.
3. **Nit**: R32 sigue diciendo «queda **APAGADO**», que insinúa un mecanismo que
   existe desactivado. Hoy no puede engañar —R30/R31/R33 dicen lo contrario en la
   fila de al lado y `tasks.md` remata con «ni siquiera apagado»—, pero es una
   línea de arreglo.

**Por qué el punto 2 no bloquea, y la diferencia con la 20ª pasada.** Entonces
lo que `impl_F-006.md` falseaba era **la evidencia**: decía que la campaña no se
había medido, y cerrar con eso habría metido en `history.md` una afirmación falsa
sobre aquello en lo que se apoya un cierre `critico`. Hoy el informe es exacto en
todo eso —lo he reverificado— y lo que queda mal es el estado transitorio del
portero en un commit intermedio. Nadie que lea F-006 dentro de seis meses se
lleva una idea equivocada de qué se construyó ni de qué se verificó. Rechazar por
esto sería caer justo en lo que la propia deuda T43 tiene medido: *cerrar seis
defectos de matiz generó tres nuevos de la misma clase*.

## No verificado en esta pasada, y así queda escrito

- **No reejecuté la campaña** ni volví a reverificar mutantes: los ocho ficheros
  del alcance no han cambiado desde `99e2335`, así que vale lo medido en la 20ª
  (recálculo puro 3126/256 exacto, 52/52 reproducibles, 5 mutantes reevaluados en
  serie con línea base verde). **No releí el cuerpo de F-006** —fichas, YAML,
  SQL, dominio—: revisión incremental, y el delta no lo toca.
- Sigue sin ser verificable desde este árbol: que `_meta` sirva la versión 9, T37
  en `azure-apps`, y las `MANUAL` T19, T27, T32-T34, T38 y T39.

## Evolución de las rondas

| # | Veredicto | Eje |
|---|---|---|
| 1-15 | 3 APROBADO, 12 RECHAZADO | Fichas falsas, guardianes verdes sobre afirmaciones falsas, campañas caducadas |
| 16 | RECHAZADO | La puerta de mutación no medía nada |
| 17-19 | (sin veredicto) | Arnés 1.7.7 arregla la campaña; 52 supervivientes resueltos |
| 20 | RECHAZADO | La campaña ya era válida; bloqueaba el papeleo que la contaba |
| **21** | **APROBADO** | **Los cuatro cerrados y verificados. Queda fichar el guardián** |

Diagnóstico de las veintiuna: *el problema nunca han sido los datos, sino los
instrumentos que decían que los datos estaban bien*. Y el cierre lo confirma: el
último instrumento en fallar no fue la campaña —esa ya está verificada— sino
**el guardián de secretos**, que se aflojó al arreglarlo.
