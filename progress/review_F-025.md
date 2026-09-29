<!-- progress/review_F-025.md -->
Revisión incremental desde `79059f8` (pasada 7): el delta son los cuatro arreglos
de `b3abcf4` más los commits de F-066 que se cruzaron. Pasadas 1 (completa) a 6:
`a34ed9b`, `fbfd0fe`, `9ce89c4`, `11b4306`, `79059f8`.

# F-025 · Review · Las obras cerradas no se reconstruyen cada noche

## Veredicto: **APROBADO**

**Los cuatro cambios de la pasada 6 están hechos, y el 1 mejor de lo que pedí.**
Verificados uno a uno sobre el árbol y sobre `azure-apps/`, no de memoria. El C2
que fallaba está cerrado. No queda nada que deba tocar el implementer, y
**ninguna de las cuatro observaciones del final bloquea el `done`**. Lo que
aprueba esta pasada es el papeleo: el árbol de código de F-025 es **el que
aprobó la pasada 5** —comprobado, ver C3— y el mecanismo (71,2 % de ahorro, las
cinco huellas, la 0599, T31b y T34) se dictaminó allí contra la base.

**Nivel de rigor: `critico`** (declarado en `harness/features.json`): exige fase
RED, cobertura de las líneas cambiadas y campaña de mutación sin supervivientes.

## Los cuatro cambios, verificados

**1 · El diccionario ya no cuenta el criterio como si fuera la conducta `[x]`.**
`stg.yaml:59`, `_meta.yaml:685` y `:802` y `00_global.yaml:17-21` distinguen las
**dos** cifras y dicen cuál vale para qué: el criterio **40 vivas / 880
congeladas** y la conducta real de `swtg78p`, **592 rehechas / 328 congeladas**,
con las 552 que entran por `sin_filas` y las 512 que siguen vacías. Y mata el
consejo falso, que era lo importante: **«esas 552 se rehacen TODAS las noches,
así que su dato tiene horas, no seis días»**, más la instrucción de mirar
`_meta.v_frescura_obra` en vez de suponerlo. Diccionario a **versión 16**.

**Barrido propio, que es lo que pedía el cambio:** `grep -rn "880"` sobre
`config/diccionario/` deja **cuatro** apariciones y **ninguna describe la
conducta nocturna** —dos explican el criterio como criterio, una es el censo de
la regla (`stg.yaml:74`, «920 obras, 880 congeladas y 40 vivas») y la cuarta es
el mismo par criterio/conducta—. Y «hasta 6 dias» deja tres frases vivas
(`stg.yaml:69`, `:291`, `_meta.yaml:801`): **las tres dicen «una obra
congelada»**, que es verdad —las 552 no lo son, se rehacen— y las tres van en la
ficha que ya trae la corrección. **No queda afirmación falsa publicada.**

**2 · El mismo error fuera del repositorio `[x]`.** Leído en `azure-apps` (sin
modificar nada): commit `ed20043`, +24/-7 sobre `datamart_seg_anual.md`. Trae la
corrección en **tabla** —criterio contra conducta— citando `swtg78p`, y arregla
la cifra muerta de `:250`: **«8 de las 48»** en vez de «40 obras… 39 cerradas».
Criterio de aceptación 6, cerrado en sus dos mitades.

**3 · `tasks.md` ya no contradice a `mediciones.md` `[x]`.** T31b cita `swtg78p`
y las cifras que verifiqué contra la base en la pasada 5 (328 del 05-sep, 592 del
07, 40 vivas, 552 por `sin_filas`). T34 trae **el matiz exacto que pedí**:
475→456 créditos, mínimo 454, gasto neto 21 en 3 h, y por escrito que se midió en
**`Standard_B2s`** mientras R29 habla del **`B1ms`**, cuya respuesta **queda
diferida a F-065**. Diferido, no respondido: es como tenía que quedar.

**4 · T33 decidida por escrito `[x]`, y en los dos sitios.** `tasks.md:69` la
deja en `[~]` con la decisión completa —por qué no es criterio de aceptación, por
qué a F-065, **dueño** F-065 y **umbral** de más de **10 puntos** de bloat sobre
la línea base de T2 tras siete noches acotadas—. Y lo que pedí expresamente
comprobar: **la ficha de F-065 en `harness/features.json` lo recoge de verdad**,
con el mismo umbral, dueño y motivo, más la herencia de la pregunta del B1ms de
R29. No vive solo en `tasks.md`.

**Y el C2 `[x]`:** `progress/current.md` ya no dice que F-025 espere la nocturna
del lunes; describe la sesión real, con el 71,2 % y los cuatro cambios.

## El delta de F-066 no invalida nada de F-025 (comprobado, no supuesto)

Entre `79059f8` y HEAD hay código de F-066 en `postgres_client.py`, `main.py` y
`recuentos.py`. **Ninguno toca la ventana**: sus *hunks* caen en `:50-74` y
`:753+` (reconciliación de columnas), lejos de `TABLAS_ACOTADAS` (`:336`), y los
de `main.py` dentro de `check_raw_recuentos_cmd`. `ventana.py` y
`build_stg_step.py` **no aparecen en el diff**: el alcance de la campaña sigue
intacto y la prueba de equivalencia sigue valiendo.

## Checkpoints

- **C1** `[x]` — `bash harness/init.sh` **exit 0**, ejecutado por mí (dos veces,
  ver la observación 1): **3.961 pasados, 159 saltados**, `PUERTA COBERTURA`
  **93,6 % de 841 líneas** (umbral 80 %, `critico`), `PUERTA TAMAÑO` OK,
  `BACKLOG.md` al día. `ruff`: 216 avisos, deuda previa declarada.
- **C2** `[x]` — una sola `in_progress` (F-025). Rama actual `feature/F-066-…`,
  **justificado como en las pasadas anteriores**: `feature/F-025-…` (`5fedc48`)
  es **ancestro de HEAD**. `current.md` ya describe solo la sesión activa. Falta
  el resumen en `history.md`, del cierre, que escribe el líder al marcar `done`.
- **C3** `[x]` — sin delta de código de F-025: `git diff 79059f8..HEAD` no toca
  `ventana.py`, `build_stg_step.py` ni `sql/**`. Convenciones `[x]` sobre lo que
  sí cambió (YAML del diccionario y Markdown). **C3 bis** y **C4 ter** `N/A`: no
  entra documentación de fuera y no existe `harness/rutas_sensibles.json`.
- **C4** `[x]` — arrastrado de la pasada 5 y ahora completo en el papeleo: las
  cinco huellas (T30, KO con las diferencias probadas del origen y **dada por
  buena por el humano el 06-sep**), la 0599 (T31), los cinco `check-*` (T32) y
  **T31b/T34 ya marcadas**.
- **C4 bis** `[x]` — RED `[x]` (trazas en `impl_F-025_metodo_ausente.md`).
  Cobertura `[x]`. Mutación: sin cabecera «⚠ CAMPAÑA NO VÁLIDA», **0
  supervivientes**, **0 «sin veredicto»**, 83/83 evaluados, 4 *timeouts*
  cerrados por RM4 en la pasada 4. **Campaña NO reejecutada**: declara
  **7.720,4 s**, muy por encima del umbral de 60 s. **RM1 revalidada hoy**: el
  diff `79059f8..HEAD` **no toca el alcance medido**. **RM2** `[x]` (83 × 93,0 s
  ≈ 7.720 s; media por debajo de la línea base, lo legítimo con 79 muertos y
  `-x`). **RM3-RM6** `N/A`: ni equivalentes declarados ni guardas quitadas. La
  mutación **fuera de `ventana.py` sigue `N/A` por la exención escrita del humano
  del 2026-09-04** (DA-6), que deja `build_stg_step.py` sin mutación y lo
  sustituye por `test_f025_build.py`, la cobertura y las huellas. «Evidencias»
  `[x]` en `impl_F-025.md:126`.
- **C5** `[x]` — **41 de 41**: 40 en `[x]` y T33 en `[~]` **con decisión escrita,
  dueño y umbral**, que es lo que pedí en vez de la casilla vacía. Commits
  `F-025 Tn: …` en la rama, nada sin trackear, `features.json` al día.

## Observaciones que NO bloquean

**1 · El KO que me encontré era de F-066, no de F-025, y ya no está.** La primera
ejecución salió `EXIT=1` por un **centinela de mutación huérfano** (F-066, pid
58648, muerto al reiniciarse la sesión). Lo comprobé antes de descartarlo:
`recuentos.py:213` tenía el **original** (`is None`), `git status` lo daba limpio
y el pid no existía. `.arnes_cache/` quedó vacío y la segunda ejecución salió en
verde. **Queda un cambio espurio de finales de línea (CRLF→LF) en
`recuentos.py`, sin una línea de contenido distinta**: es de F-066, no lo he
tocado, y que lo limpie quien cierre aquélla.

**2 · La segunda nocturna `p1gq8ks` no está escrita.** El líder la cita por chat
(2026-09-08, `build_stg` 2.652 s frente a 9.527 s = **72,2 %**, con la imagen
nueva) y confirmaría el 71,2 % de forma independiente, pero **no está en ningún
fichero** (`grep` sobre `specs/` y `progress/`) y **no la he verificado yo** —no
ejecuto `az`—. No cambia el veredicto: el criterio 2 lo cerraba ya la primera
medición, documentada y verificada contra la base. Si se va a citar, que caiga
en `mediciones.md` §7 con su fecha y su `Succeeded`: un dato caro que solo vive
en el chat es el modo de fallo que este arnés se dedica a evitar.

**3 · Dos costuras de redacción, sin efecto semántico:** `stg.yaml:60-61` repite
«NO SE BORRAN Y SIGUEN CONSULTABLES» y `00_global.yaml:21` pegó dos frases.

**4 · La versión 16 aún no está publicada:** llega a `_meta.v_diccionario` con el
próximo despliegue, no con este commit.

## Automejora propuesta (no aplicada)

Para `.claude/agents/reviewer.md`: **cuando el KO de `init.sh` sea un centinela
de mutación huérfano de OTRA feature, el reviewer puede comprobar los tres hechos
que lo delatan —fichero en su texto original, `git status` limpio, pid muerto—,
limpiarlo con `--restaurar` y reejecutar.** Hoy el protocolo solo dice «init.sh
en rojo, rechazo», y eso rechaza una feature por la basura de otra.
