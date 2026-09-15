<!-- progress/review_F-072.md -->
Revisión incremental desde `b2d10d3` (pasada 2) · HEAD `53bb40f`

# Review F-072 · el censo semántico de las 31 tablas sin consumidor

**VEREDICTO: CAMBIOS REQUERIDOS.** Queda **una sola cosa, de dos líneas**: el
punto 2 de la pasada 1 —`progress/current.md`— **no se ha tocado en el delta**.
Todo lo demás está aprobado: el bloqueante de la pasada 1 (criterio 7) **está
resuelto y verificado**, y el rigor ya es el correcto.

**Nivel de rigor**: pasa a **`documental`**, que es el que `CHECKPOINTS.md`
define para una feature cuyo entregable es conocimiento. Con él, fase RED,
cobertura y mutación **dejan de ser exigibles por nivel** —ya no hay que
justificarlas a mano como en la pasada 1— y quedan C1–C3, C3 bis y C5.

## El delta que reviso

`git diff b2d10d3..HEAD`: 5 ficheros, **0 `.py` y 0 `.sql`**. `BACKLOG.md` (+6),
`harness/features.json` (+4), `explore_F-072_catalogo.md` (+37),
`explore_F-074_las_nueve.md` (+150) y mi informe de la pasada 1 (+140).
Nada del delta invalida lo aprobado antes: no mueve ficheros, no cambia firmas y
no toca el alcance de ninguna medición. **Lo aprobado hasta `b2d10d3` queda dado
por bueno** y no lo vuelvo a leer, según acordamos: las cinco cifras clave y los
~35 volúmenes salieron exactos en la pasada 1.

## Punto 1 · el bloqueante, criterio 7 — **RESUELTO Y VERIFICADO**

`explore_F-072_catalogo.md` §6 «Los hallazgos heredados de F-071, ya medidos»
dice **exactamente lo que medí**, y lo comprobé de nuevo por el otro lado:

| §6 afirma | medido por mí ahora |
|---|---|
| 294 obras con `munide`, **31,9 %** | **294 · 31,9 %** ✓ |
| 305 obras con `dir1`, **33,1 %** | **305 · 33,1 %** ✓ |

Y verifiqué **el denominador**, que en la pasada 1 yo había medido sobre
`raw.obr` y la §6 atribuye a `maestro.obras`: **las dos tienen 921 filas y casan
921 de 921**, así que la atribución es correcta y los porcentajes se sostienen
medidos por cualquiera de los dos lados. No es un detalle ocioso en una feature
que existe para que nadie se equivoque de denominador.

Lo demás de la §6 también está bien atribuido:

- **Cuatro de los ocho campos son la dirección de la obra** (`dir1`, `dir2`,
  `dircpo`, `dir`) y **tres no lo son** (`diride` director de obra, `perdir` su
  persona de contacto, `entdiride` dirección del cliente). Las cuatro columnas
  existen en `raw.obr`, comprobado contra `information_schema`; y en la pasada 1
  medí que los tres que no son dirección vienen prácticamente vacíos —`diride` 8,
  **`perdir` 0**, `entdiride` 2—, que es la confirmación por el dato.
- **Municipio y provincia** por `raw.auxmun` (56.053) y `raw.auxpro` (95), vía
  `obr.munide`/`obr.proide` ✓.
- **Las 472.890 filas huérfanas se quedan**: 390.028 de `stg.presupuesto` más
  82.862 de `stg.plan_mensual`. Suman ✓, y la §6 las declara como medición
  **heredada de F-071**, no propia: rastreadas a `specs/F-071-obras-sin-datos/`
  `design.md:28-32` y `requirements.md:37`. Atribución honesta.

La §6 además saca la conclusión, y es la que importa: **«a la pregunta dónde
está la obra X, para dos de cada tres obras la respuesta correcta es no
consta»**, sin por ello descartar publicarla. **Criterio 7 [x] CUMPLIDO.**

## Punto 2 · el alcance de F-073 — **BIEN, con una observación**

La ficha de F-073 lleva el bloque `MEDIDO EL 2026-09-09 EN EL REVIEW DE F-072`
con los dos porcentajes, con el mandato de que **la ficha del diccionario diga el
porcentaje informado**, y con la advertencia de que **el criterio de aceptación
no puede exigir una cobertura que el origen no tiene**. Es lo que pedía.

*Observación, no bloqueo*: el `acceptance` 2 de F-073 sigue diciendo literalmente
que «se responde sin explicarle nada en el prompt», que es la cobertura que el
origen no da. La corrección vive en la `description`, que es la convención de
este repositorio —apendar bloque marcado, no reescribir— y el spec-author de
F-073 la leerá. Lo dejo anotado para que al especificar F-073 el criterio se
reformule con el porcentaje delante, y no se descubra al final.

## Punto 3 · el rigor — **BIEN**

`harness/features.json` pone F-072 en **`documental`** y `BACKLOG.md` está
regenerado y coherente (tabla resumen y ficha larga, las dos). Es el nivel que
corresponde: 0 `.py` y 0 `.sql` en toda la rama de la feature.

## Lo que falta, y es lo único

**`progress/current.md` no está en el delta.** Sigue con la tabla de la sesión
anterior en las líneas 17-21:

> `| 4 | **F-071** | spec en curso | ... subir la direccion de la obra ... |`

Cuando la línea 126 del mismo fichero dice «**F-071 ESTÁ RETIRADA**». Hoy esa
tabla está **tres features desactualizada**: manda a la próxima sesión a una
feature muerta y no nombra ni F-072 (la que está en curso), ni F-073, ni F-074.
Es C2 —«describe SOLO la sesión activa, sin restos de sesiones anteriores»— y es
el punto 2 de mi pasada 1, que quedó sin aplicar. **Dos líneas.**

## CHECKPOINTS (contra el nivel `documental`)

- **C1 [x]** — `bash harness/init.sh` de esta pasada, exit 0: **3.970 passed,
  159 skipped** en 338 s; TAMAÑO [OK]; y la puerta de cobertura ahora imprime
  **`N/A (F-072 es de nivel documental: no exige cobertura)`**. Es decir: el
  cambio de rigor **hizo desaparecer el 93,6 % de 842 líneas heredadas** que yo
  denuncié en la pasada 1, y en su lugar hay un N/A con su motivo impreso, que es
  lo que el arnés pide. Los siete ficheros del arnés existen.
- **C2 [ ]** — Una sola `in_progress` (F-072) ✓, rama
  `feature/F-072-censo-semantico-raw` ✓, `history.md` al día ✓. **Falla por
  `current.md`**, arriba.
- **C3 N/A justificado** — 0 `.py` y 0 `.sql` en el delta y en toda la feature:
  no hay arquitectura ni convenciones de código que juzgar. Repetí el **barrido
  de datos sensibles sobre la §6 nueva: limpia** (direcciones de obra y
  catálogos, ni un dato personal). **C3 bis N/A**: no se toca `docs/referencia/`.
- **C4 [x]** — los siete `acceptance` cumplidos: los seis primeros en la pasada 1
  y **el séptimo verificado arriba**. No hay tests posibles ni requisitos EARS:
  el entregable es conocimiento y la verificación es el contraste contra la base,
  hecho por el reviewer.
- **C4 bis [x]** — `rigor` declarado y **correcto**: `documental` **no exige**
  fase RED, cobertura ni mutación (`CHECKPOINTS.md`, tabla de niveles), así que
  no son N/A que haya que justificar sino puertas que este nivel no pide. RM1-RM6
  no aplican: no hay campaña porque no hay código.
- **C4 ter N/A** — no hay `harness/rutas_sensibles.json`.
- **C5 [x] con nota** — `tasks.md` N/A (`sdd=false`); commits bien rotulados;
  `features.json` refleja el estado real; árbol limpio salvo este informe. *Nota
  sin consecuencia*: `53bb40f` se llevó dentro
  `progress/explore_F-074_las_nueve.md` (150 líneas), que es exploración de
  **F-074** y no de esta feature. No estorba, pero conviene saberlo cuando se
  mire la historia de esta rama.

## Sobre el defecto del arnés: **sí, abre la ficha**

El coordinador pregunta si merece ficha propia que `harness.alcance` diffee
contra `cd18e09` y arrastre F-025, F-066 y F-068. **Sí.** No es cosmético: con
`dev` varias features por detrás, **las dos puertas automáticas del arnés miden
código que no es el de la feature en curso**. Aquí salió a favor —cobertura en
verde por herencia— pero el mismo mecanismo puede (a) tapar una feature mal
cubierta detrás del buen dato de otras, y (b) inflar una campaña de mutación
hasta hacerla impagable, mutando código ajeno. Es la misma familia que RM1
(«¿contra qué commit se midió?») y encaja al lado de F-041. El arreglo: anclar el
alcance al primer commit de la rama de la feature, no a `dev`.

---

**Para cerrar**: arreglado `current.md`, esto es APROBADO. No hace falta que se
me devuelva nada más de la pasada 1 ni del delta: el resto está verificado.
