<!-- progress/review_F-025.md -->
Revisión incremental desde `79059f8` (pasada 6). **El delta es VACÍO**: `HEAD` es
`79059f8`, el mismo commit de la pasada 5. Pasadas 1 (completa) a 5: `a34ed9b`,
`fbfd0fe`, `9ce89c4`, `11b4306`, `79059f8`.

# F-025 · Review · Las obras cerradas no se reconstruyen cada noche

## Veredicto: **CHANGES_REQUESTED**

**No por nada nuevo: porque no hay nada nuevo.** Los cuatro cambios que pidió la
pasada 5 siguen abiertos, comprobados **fichero a fichero, no de memoria**. El
mecanismo queda demostrado: las cuatro preguntas del líder se responden a favor
de la feature. Falta papeleo, ninguna nocturna más.

**Aviso de método (obligatorio decirlo).** Por orden expresa del líder **NO he
ejecutado `bash harness/init.sh`** (dos intentos previos murieron a los 600 s) ni
he conectado a la base. Doy por buena su ejecución de **hoy 16:30 UTC sobre este
mismo commit**: `3.895 passed, 159 skipped`, `COBERTURA 92,8 % de 752 líneas
(umbral 80 %, critico)`, `TAMAÑO OK`, exit 0 — **verificado por el líder, no por
mí**. Las cifras de producción salen de lo escrito y de la verificación contra
Azure de la pasada 5.

**Nivel de rigor: `critico`** (`harness/features.json`): exige fase RED,
cobertura de lo cambiado y mutación sin supervivientes.

## Las cuatro preguntas, con veredicto propio

**1 · El 71,2 % es legítimo.** Mismo paso (`build_stg`), los dos `SUCCEEDED`, los
dos en **`Standard_B2s`**, los dos con la imagen `r20260905-1237` (F-025 sin
F-066, a propósito), y las dos cifras salen de `_meta.etl_runs`. `hamsh8o` es
**la referencia correcta**: la única completa con el mismo código y el mismo SKU.
La objeción seria —`hamsh8o` bajó a **6 créditos** y `swtg78p` no bajó de 454, y
una base estrangulada inflaría el ahorro— **no se sostiene, por tres caminos**:
(a) en `hamsh8o`, con la hucha a 6, los últimos tramos iban a **47-57 s**, los
rápidos de la noche; (b) `ingest_raw` fue **más lento** en la acotada (2.256 s
con 475 créditos) que en la completa (1.832 s con 60), justo lo contrario de una
completa capada; (c) el **suelo volumétrico** no depende del reloj: se rehacen
**11,67 M de 29,77 M filas**, ~61 % menos, y T1 predijo 59,2 % por peso. Ruido en
los pasos no acotados: ±6 a ±12 %. Límite honesto: es **un par de ejecuciones**;
cítese el 59-61 % como suelo garantizado y el 71,2 % como lo medido una vez.

**2 · T33 no bloquea el cierre, pero no puede quedarse en `[ ]`.** No es criterio
de aceptación (los seis de `features.json` no la piden), mide el **riesgo 1 de
`design.md`** y su único desenlace es abrir otra feature, no tocar este código. Y
está mitigada: T14 dejó `VACUUM (ANALYZE)` al final del sub-paso y la puerta de
disco de F-019 vigila entretanto. **Pero es el riesgo que esta feature se creó a
sí misma** —el `DELETE`+`INSERT` deja tuplas muertas cada noche, en un disco de
64 GB con seis inquilinos que ya dio un susto el 07-sep—, y una casilla vacía
dentro de una feature `done` es el modo de fallo de F-052 aplicado a sí misma.
**Se cierra con una decisión escrita —dueño y umbral—, no con una semana de
espera**: T2 ya dejó la línea base. Recomiendo F-065.

**3 · La conclusión corregida se sostiene.** Verificado por mí en el código:
`postgres_client.py:336` `TABLAS_ACOTADAS = ("plan_mensual", "presupuesto")`, y
`design.md:162-163` y `:235` dejan `sql/mart/**` y `sql/cierre/**` fuera de
alcance (R33): cronometrar `build_mart` era medir un paso que la feature nunca
tocó. **Tres agujeros menores, ninguno bloqueante:** (a) las filas del mart que
cita `explore_F-025_coste_fijo.md` (5.359.591 / 5.361.017) no son las de
`etl_runs` (5.384.370 / 5.385.800) —será un sub-paso—, y siendo esa «la prueba de
una línea», conviene decir de dónde sale; (b) sin `EXPLAIN`, el reparto de los
2.740 s es deducción, y el informe lo avisa; (c) **el agujero de verdad es
de alcance**: R29 y el criterio 5 hablan de los créditos **del B1ms** y lo medido
es un **B2s** de 576 de tope. No hay respuesta hasta bajar de SKU —para eso nace
F-065— y debe quedar escrito como **diferido**, no como respondido.

**4 · Las 552 obras no bloquean el mecanismo; sí bloquean el papeleo publicado.**
De acuerdo con no bloquear, y no por confianza: (a) pesan **24.697 de 74,9 M**
por `SQL_PESOS_PLAN_MENSUAL` (T1) y 47.723 filas contadas en la base por la
pasada 5, el 0,16 %: no comprometen el 71,2 %; (b) el código cumple R18 al pie de
la letra —`ventana.py:472`—, y el defecto está **aguas arriba**, en el censo
`SQL_ESTADO_OBRAS` sobre `raw.obr ⨝ raw.con`, anterior a esta feature y conectado
con F-053; (c) no tocan R11, R12 ni R21: ninguna congelada se mueve y la 0599
sigue en 2.624.793,46 € y 1,79 %. **Lo que sí se llevan por delante es la
frescura publicada**: quien pregunte al MCP por esas 552 recibirá «hasta 6 días»
cuando se rehacen cada noche. Es el cambio 1, y es de cierre, no de F-071.

## Cambios requeridos (los cuatro de la pasada 5, verificados hoy sin tocar)

**1 · El diccionario publicado dice lo que la ventana NO hace.** Comprobado con
`grep` sobre HEAD: `config/diccionario/stg.yaml:58`, `:73-74`, `:285`;
`_meta.yaml:684`, `:735`, `:799`; `00_global.yaml:16` siguen diciendo «se rehacen
las 40 vivas y las 880 congeladas conservan la versión». La nocturna acotada real
dice **592 rehechas y 328 congeladas**. Distíngase el **censo del criterio**
(880/40, correcto donde se explica la regla) de la **conducta nocturna**
(592/328). Sube `version`. R31 y criterio 6.

**2 · El mismo error fuera del repositorio.** `azure-apps/datamart_seg_anual.md`:
`:206` repite el 880; **`:250` conserva además la cifra muerta** «Hay 40 obras
con actividad reciente que quedan congeladas —39 cerradas…—», corregida por R3 el
03-sep a **8 de las 48**. R32.

**3 · `tasks.md` contradice a `mediciones.md`.** T31b y T34 siguen `[ ]` («necesitan
nocturnas acotadas») y las dos están medidas el 07-sep y verificadas contra la
base en la pasada 5 (328 obras con `construido_at` del 05, 592 del 07; 21
créditos, mínimo 454). Márquense `[x]` con su evidencia, y **T34 con su matiz**:
medida en B2s, la respuesta para el B1ms es de F-065.

**4 · T33: decidir por escrito.** Pasarla a F-065 (recomendado) o a ficha propia,
**con umbral y dueño**. La casilla vacía no vale.

## Checkpoints

- **C1** `[x]` — init.sh en verde **según la ejecución del líder de hoy sobre este
  commit**, no mía (ver el aviso de método): cobertura 92,8 % y tamaño OK.
- **C2** `[ ]` — una sola feature `in_progress` (F-025) `[x]`; rama actual
  `feature/F-066-…` **justificado**: `feature/F-025-…` (`5fedc48`) es **ancestro
  de HEAD** (`git merge-base --is-ancestor`). Falla el tercer punto:
  `progress/current.md:118` sigue diciendo que F-025 está `blocked` esperando «la
  nocturna del lunes», que ya corrió y ya está medida.
- **C3** `[x]` — arrastrado de la pasada 5 sin delta que revisar: el árbol de
  código es byte a byte el que aprobó. **C3 bis** y **C4 ter** `N/A`: no entra
  documentación de fuera y no existe `harness/rutas_sensibles.json`.
- **C4** `[x]` — la verificación es la fase 7 entera: cinco huellas (T30 KO con
  las diferencias probadas del origen y **dada por buena por el humano el
  2026-09-06**), la 0599 (T31), los cinco `check-*` con el mismo veredicto que
  antes (T32) y T31b/T34 en la primera acotada.
- **C4 bis** `[x]` — RED `[x]` (trazas en `impl_F-025_metodo_ausente.md`).
  Cobertura `[x]`. **RM1 revalidada por mí**: el informe midió `073af30` y HEAD
  es `79059f8`, pero el único commit que toca `ventana.py` desde entonces es
  `f7fe187`, y su diff es **solo docstring** (`git show`): el alcance medido
  sigue siendo el revisado. **RM2 `[x]`**: 83 × 93,0 s = 7.719 ≈ 7.720,4 s de
  total; la media (93 s) queda muy por debajo de la línea base (467-473 s) y eso
  es **legítimo**: 79 de 83 mutantes mueren y `-x` aborta la suite en el primer
  fallo. **Campaña NO reejecutada** (7.720 s, muy por encima del umbral de 60 s).
  Cero supervivientes, cero «sin veredicto», sin cabecera de campaña no válida; 4
  timeouts listados con su texto. RM3-RM6 `N/A`: ni equivalentes declarados ni
  guardas quitadas. **La mutación fuera de `ventana.py`, `N/A` por exención
  escrita del humano del 2026-09-04** (DA-6, `features.json` y T26), que deja
  `build_stg_step.py` —donde vive el borrado derivado— sin mutación, cubierto por
  `test_f025_build.py`, la cobertura y las cinco huellas.
- **C5** `[ ]` — **38 de 41**: T31b y T34 hechas y sin marcar (cambio 3); T33 sin
  medir y sin dueño (cambio 4).

## Automejora propuesta (no aplicada)

Sigue en pie la de la pasada 5 (el barrido de una cifra corregida cubre el árbol,
`azure-apps/` y los campos **publicados** del diccionario). Añado una para
`.claude/agents/reviewer.md`: **con el delta vacío —`HEAD` idéntico al de la
pasada anterior— no se revisa de nuevo; se comprueban los cambios requeridos uno
a uno y se declara en la primera línea.** Cuesta un `git log`.
