<!-- progress/review_F-073.md -->
# F-073 · Review

**Revisión completa (pasada 1)**, sobre `git diff 59a6b36..d203a5a` (21 commits,
21 tareas). HEAD revisado: `d203a5a6cd5175bdf0c07733d1dbbcc2c316ee99`.

## Veredicto: **APROBADO**

**Nivel de rigor:** `estandar`, **declarado** en `harness/features.json`. Exige
C1–C5, fase RED en los requisitos centrales, cobertura ≥ 80 % de las líneas
cambiadas y campaña de mutación con supervivientes analizados; no exige cero
supervivientes ni RM5.

`bash harness/init.sh` ejecutado por el reviewer, tal cual: **exit 0**,
`ENTORNO LISTO`, **4.367 passed / 171 skipped / 0 failed**, PUERTA COBERTURA
**[OK] 93,6 % (791/845)**, PUERTA TAMAÑO [OK]. Los cuatro números coinciden con
las «Evidencias» del implementer.

## Los cuatro puntos pedidos con lupa

1. **`main.py` (5 líneas): solo un comentario** (l. 503-509), sin una sola línea
   ejecutable. Corrige la frase «`maestro`, `compras` y `retenciones` solo leen
   de `raw`», que **R27 vuelve falsa**. Justificado: dejarla al lado de un
   `depends_on` que ya incluye `build_stg` es la mina que F-047 vino a quitar.
2. **Los tests de F-047 NO se relajan, se endurecen.** En
   `test_f047_nocturna.py` el aserto viejo recorría tres pasos exigiendo
   `depends_on == ["ingest_raw"]`; ahora recorre dos y `build_maestros` sale a un
   test **propio y más estricto**: igualdad exacta con `["ingest_raw",
   "build_stg"]` **más** `orden.index("build_maestros") >
   orden.index("build_stg")`, que antes no se comprobaba. En
   `test_f047_steps.py` la lista de `build_compras` **sigue siendo exhaustiva**;
   de `build_maestros` no hay entrada ahí, ni antes ni ahora.
3. **`specs/F-006-mcp-azure/design*.md`: NO es contaminación, es obligatorio.**
   `tests/test_f006_fichas.py:788` calcula el inventario real del repositorio y
   exige que ese número **esté escrito en `design_detalle.md`**; con tres objetos
   nuevos pasa a 142 y sin tocar el documento la suite se pone en rojo. Los dos
   cambios son **aditivos** (una fila de changelog y una «Enmienda»).
4. **`tasks.md` (42 líneas): solo `[ ]` → `[x]`.** Diff línea a línea: las 21
   tareas conservan su texto **carácter por carácter**. Cero reescritura del
   contrato a posteriori.

## Lo que la spec exige, verificado sobre el árbol (no sobre el informe)

* **R5 (grano del puente).** `04_centros_coste.sql`: `LEFT JOIN LATERAL` con
  `ORDER BY co.ide` + `LIMIT 1` y el `JOIN raw.obr` **dentro** del lateral. 1:1
  por construcción, no por el dato de hoy; el test de R5 exige ambas cláusulas.
* **R17 (921 filas).** Los tres `LEFT JOIN` nuevos de `01_obras.sql` son
  `auxmun`/`auxpro` por `ide` (identificador de catálogo) y el lateral a `conest`
  con `WHERE ce.tip = 42`, `ORDER BY ce.ide`, `LIMIT 1`. El único punto con
  riesgo real —que `(tip, est)` deje de ser único— queda acotado por el
  `LIMIT 1`. Medido 921 en solo lectura (T2) y re-verificable en la MANUAL 2.
* **R18 (ninguna columna desaparece ni se renombra).** Comparado
  `git show 59a6b36:…01_obras.sql` contra el fichero actual: las **10 columnas de
  siempre siguen idénticas, en el mismo orden y con la misma expresión**
  (`es_activa` incluida), y las 11 nuevas van detrás. **`b6eda79` no se llevó
  nada**: solo movió lo nuevo al final, y por buen motivo —`CREATE OR REPLACE
  VIEW` no admite columnas intercaladas—. El test
  `..._r18_las_columnas_de_siempre_van_primero_y_en_su_orden` fija el hueco que
  los tests de presencia no veían.
* **R23, R25, R26 (lo intocable).** `git diff --name-only 59a6b36..d203a5a` sobre
  `stg/06_presupuesto.sql`, `stg/08_plan_mensual.sql`, `stg/03_obras.sql`,
  `compras/01_documentos.sql` y `sql/retenciones/**` devuelve **vacío**; los
  `sha256` del árbol coinciden con los tripwires y el `rn = 1` sigue en
  `03_obras.sql:125`.
* **R28 (diccionario).** Fichas presentes: `maestro.centros_coste` (l. 465),
  `maestro.estados_documento` (l. 538), `compras.formas_pago` (l. 1068) y **las
  11 columnas nuevas** de `maestro.obras` (l. 154-250), cada una con su
  porcentaje medido (R12), su `nulo_significa` (R11) y la trampa `stg` vs `mart`
  (R15). `00_global.yaml` en **`version: 19`** (l. 131) con su nota. Declara
  además la relación `estados_documento → obras` como **N:N** y manda filtrar el
  42 antes de unir: correcto, y es la clase de trampa que evita una cifra falsa.
* **Fase RED.** Están las **seis tandas** con salida real de pytest, una por
  bloque central (R1–R5, R19–R20, R7–R18, R21–R22, R27 y el diccionario), más la
  del defecto de R18 hecha **sobre copia en scratchpad**. Son reales, no
  narradas: los recuentos encajan entre tandas (17 → 26 → 64 → 85 tests en
  `test_f073_sql.py`).

## Campaña de mutación — verificación independiente

* **Recalculado** con `harness.alcance` + `harness.mutacion.generar_mutantes`
  (cálculo puro): **3.617 líneas y 288 mutantes**, idénticos al informe, fichero
  a fichero. **Cinco supervivientes muestreados** (`build_stg_step:732`,
  `postgres_client:1529` ×2, `ventana_sql:215`, `main.py:544`) **reproducen
  exactamente**: mismo fichero, línea, operador y texto original→mutado.
* **Campaña NO reejecutada: 5.470,2 s (91 min) según el informe**, muy por encima
  del umbral de 60 s de C4 bis. Coste por mutante = 5.470,2 × 1 ÷ 20 = **273,5
  s**, coherente con la línea base de 412,8 s con `-x` (RM2: la media por debajo
  de la base es lo esperable con 11 de 20 muertos).
* **RM1.** SHA medido `b6eda794…`, que **no es HEAD**; entre `b6eda79` y
  `d203a5a` solo cambian `impl_F-073.md`, `mutacion_F-073.md` y `tasks.md`:
  **ningún fichero del alcance**. La campaña sigue siendo válida.
* **RM6.** No se quitó ninguna guarda defensiva: el diff de Python solo añade.
* **Los nueve supervivientes, leídos uno a uno.** Ninguno en `PENDIENTE` y
  **ninguno cae en código de F-073**: las líneas que F-073 toca generan **0
  mutantes**, y la prueba de control (mutar los dos ficheros **enteros**,
  ignorando el alcance) da **24**, la cifra que el informe declara. El cero es
  legítimo: lo que F-073 cambia en Python es declarativo (docstrings,
  `SUB_PASOS`, `depends_on`), no expresiones mutables. Siete son
  `PostgresClient`/`build_stg_step`, inalcanzables offline por la convención de
  no tocar BBDD y de **F-025**; el noveno es **F-077, ya fichado**.
* **¿Agujero real que fichar, como con F-077?** Sí, dos, y **ninguno de F-073**:
  el nº 8 (`ventana_sql.py:215`, `codigo_obra=str(codigo or "")`, se tapa con un
  assert) y el nº 1 (`build_stg_step.py:732`, el camino acotado con plan
  PARCIAL). **No bloquean** —`build_stg_step.py` es el SELLO y R25 prohíbe
  tocarlo—, pero recomiendo ficha propia contra F-025, como se hizo con F-077.

## Checkpoints

* **C1** `[x]` init.sh exit 0 y los siete ficheros del arnés presentes.
* **C2** `[x]` una sola `in_progress`; rama correcta; `history.md` al día.
  `current.md` arrastra MANUAL de F-074/F-079/F-080: pendientes vivos, no restos.
* **C3** `[x]` SQL en su capa con numeración `NN_nombre.sql`; primera línea con
  la ruta en los seis ficheros nuevos; sin `print()`, TODOs ni secretos (barrido
  hecho); dominio intacto. Semántica Sigrid respetada, con el acierto de no usar
  `cen.obride` (a 0 en las 804 filas) ni la aritmética del `ide`.
* **C3 bis** `N/A` **justificado**: no toca ningún fichero de `docs/referencia/`.
* **C4** `[x]` **R1–R28 con test trazable `test_f073_rN_*`**, los 63 tests nuevos
  (130 con parametrización) en verde; R29 es la propia puerta de `init.sh`. No
  tocan red ni BBDD (`grep` de `psycopg`/`connect`/`requests`: vacío). El doble
  `_PgFalso` declara `execute_sql_file` y `count_rows`, **las dos existen en
  `PostgresClient` con firma compatible** (introspección + barrido de
  `test_f025_contrato_cliente.py`). Las MANUAL están en `current.md` con su
  comando exacto y en orden, incluida la de T19 con su `261 / 261`.
* **C4 bis** `[x]` según la sección anterior. RM5 `N/A` **por nivel**
  (`estandar`, y ningún superviviente se declara equivalente).
* **C4 ter** `N/A` **justificado**: no existe `harness/rutas_sensibles.json`.
* **C5** `[x]` 21 tareas `[x]` con commit `F-073 Tn:` cada una (T18 y T19
  comparten `6a1dd7f`, ambas papeleo del mismo fichero) más el correctivo
  `b6eda79`. Los untracked del árbol son de **F-080**, otra sesión.

## Observaciones (no bloquean)

1. **El «tiempo de la suite» no cuadra**: el informe declara 1.048,4 s; mi
   ejecución tardó **3.929,6 s**. Lo que decide —4.367/171/0 y 791/845— coincide
   al dígito, así que se ejecutó de verdad; la diferencia la explica la otra
   sesión trabajando en el árbol.
2. **La puerta de mutación no dice nada de una feature cuyo entregable es SQL.**
   **Automejora propuesta** (no aplicada) a `CHECKPOINTS.md`: cuando el diff no
   genere mutantes en sus propias líneas, que el informe lo declare —como hizo
   aquí el implementer— y que el reviewer quede obligado a la prueba de control.
3. **`config/tables_sigrid.yaml` dice que el nombre del medio de pago es
   `auxefp.est`, y es falso** (vacío o nulo en las 10 filas; está en `res`). Bien
   dejado fuera de alcance y documentado en tres sitios, pero merece ficha: es
   una mentira en la configuración de la ingesta.
