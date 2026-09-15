<!-- progress/review_F-081.md -->
Revisión completa (pasada 1) · rango `87f4d84..d5e484c`, 8 commits.

# F-081 · Review

**Veredicto: APROBADO**

**Rigor `estandar`, declarado en la ficha.** Exige C1–C5, fase RED, cobertura
≥ 80 % y campaña de mutación con supervivientes analizados; no exige cero
supervivientes ni MANUAL. Sin spec: el contrato son los siete `acceptance` y lo
que dependa de `tasks.md` es N/A.

## La restricción dura: verificada en el diff, no en el informe

`git diff --name-only 87f4d84~1..d5e484c` da 11 ficheros y **ninguno es
`build_stg_step.py` ni `ventana_sql.py`** (el `grep` sale vacío, exit 1). El
commit `c8bc532` («sin tocar el codigo») **se confirma**: su `--stat` son
`progress/impl_F-081.md` y `tests/test_f081_supervivientes.py`, nada más.

**Corrección a la premisa de la ficha, medida por mí:** `build_stg_step.py`
**no es fichero del sello**. `FICHEROS_DEL_SELLO` (línea 96) son `06_presupuesto
.sql` y `08_plan_mensual.sql`, y `sello_vigente_del_repositorio` sólo hashea
esos más un parámetro: tocar el módulo no habría reconstruido las 921 obras. El
implementer lo midió y **respetó la restricción igualmente**.

## Los dos mutantes: reproducidos, no leídos

Recalculé ambos con `generar_mutantes` (puro): coinciden fichero, línea,
operador y texto original→mutado con `mutacion_F-073.md`. Los ejecuté sobre una
**copia aislada** (`git archive` al scratchpad), nunca sobre el árbol.

| Mutante | Antes | Después (test nuevo) |
|---|---|---|
| `ventana_sql.py:215` `or`→`and` | `test_f025_cli` + `test_f025_ventana`: **84 passed** → SUPERVIVIENTE | **2 failed, 5 passed** → MUERTO |
| `build_stg_step.py:732` `and`→`or` | — | **1 failed, 6 passed** → MUERTO |

Cifras idénticas a las del informe. **El superviviente falso se confirma**:
con ese mutante puesto `tests/test_f025_build.py` da `1 failed, 42 passed`, y
el test que lo mata no ha cambiado desde `b6eda79`, el «SHA de HEAD medido» de
la campaña de F-073. Aquella emitió un veredicto equivocado; el implementer lo
escaló en `current.md` y lo ratifico.

## Los cinco puntos pedidos con lupa

1. **`04_formas_pago.sql`, 12 líneas: justificado, no es alcance colado.** El
   diff filtrado de líneas que no empiezan por `--` sale **vacío**: sólo cambia
   la cabecera, uno de los tres sitios donde F-073 denunciaba la mentira y que
   ahora habla en pasado. **R21 y R22 intactos**: la línea 36 sigue siendo
   `ap.formul AS plazo_formula` y no hay `dias_pago`.
2. **`test_f073_diccionario.py`, 12 líneas: no relaja nada.** Son 10 de
   docstring y 2 de aserto, `== "19"` → `>= 19`. R28 exige que la versión
   *suba*, no que se congele, y `>= N` es el patrón ya establecido en
   `test_f066` (14), `test_f074` (17) y `test_f079` (18); con 18 o menos sigue
   en rojo. Ningún otro aserto cambia.
3. **Criterio 2, barrido sistemático: verificado por mi cuenta.** Pasé el
   detector del test sobre **las 65 entradas** del YAML: sólo cinco atribuyen
   columna de nombre —`auxefp`, `auxpro`, `auxmun` (vigiladas y correctas),
   `obrprv` (cierto y examinado en el informe) y `apa` (**falso positivo** del
   troceo: su bloque arrastra el comentario de módulo de COMPRAS)—. `cen` ya no
   salta: está corregido. Y nadie la creyó: `04_centros_coste.sql` toma el
   rótulo de `raw.con`, `05_views_cabecera.sql` usa sólo `cen.ide` y el único
   SQL sobre `auxefp` ya lee `ef.res`.
4. **Criterio 3, el candado cierra.** Ejecuté el test **revirtiendo el YAML a
   su texto de antes de F-081** (`git show 87f4d84~1:...`), sustituido en
   memoria y sin tocar el árbol: **4 fallos**, los mismos tests y mensajes que
   la fase RED del informe (`c3[auxefp]`, `c3[cen]` y los dos `c1`), y los tres
   controles positivos en verde.
5. **AVISO PARA EL LÍDER · la versión 20 la tenía reservada F-080.** Su
   `design.md:74` dice «`version` 19 → **20**» y su `tasks.md:71` (T22) manda
   subirla «tras comprobar que el fichero está en 19»: ya no se cumple. **F-080
   tiene que pasar a la 21** y reescribir esa comprobación. No es defecto de
   F-081 —su bump es obligatorio—, pero hay que corregir la spec antes de
   implementarla.

## Checkpoints

**C1** — [x] `bash harness/init.sh`: `4385 passed, 171 skipped in 766,86 s`,
`PUERTA COBERTURA [OK] 93,6 % (791/845)`, `PUERTA TAMAÑO [OK]`, **exit 0**. [x]
Los ocho ficheros del arnés existen. *La primera pasada cayó por este mismo
informe (177 > 140 líneas); reescrito y revalidado en esta segunda.*

**C2** — [x] Una sola `in_progress`: F-081. [x] Rama correcta. [x] `current.md`
con su sección y la consulta al humano. [x] F-073 `done` con resumen en
`history.md:895`. *Observación*: `current.md` conserva la sección de F-073, ya
cerrada; higiene del líder al mergear, no de F-081.

**C3** — [x] Sin cambios de arquitectura: **ni una línea de producción
ejecutable**. [x] Primera línea con la ruta en los dos ficheros nuevos. [x] Sin
`print()`, TODOs, secretos ni dependencias nuevas. [x] Semántica Sigrid: la
feature *repara* una afirmación falsa. **C3 bis — N/A justificado**: no toca
`docs/referencia/`, luego no hay documento externo que barrer.

**C4** — [x] Los siete criterios trazados (tabla abajo); 18 tests nuevos, todos
pasan. [x] Ni red ni BBDD: mi `grep` de `psycopg|httpx|requests|connect(|socket|
urllib|SigridApiClient` sobre `tests/test_f081_*.py` sale **vacío**. [x] MANUAL:
**N/A justificado**, nada de lo cambiado altera la nocturna (comentarios de
YAML, cabecera de SQL y una ficha); declarado en `current.md`. [x] **Dobles
cruzados con el original**: los cuatro métodos de `PgDelPresupuesto` existen en
`PostgresClient` con firma compatible (`inspect.signature`), y el barrido de
`test_f025_contrato_cliente.py` corre en la suite. *Observación*: los tests se
llaman `test_f081_cN_*` y no `rN`; sin requisitos EARS la `c` de «criterio»
traza mejor, lo doy por bueno (automejora 1).

**C4 bis** — [x] `rigor` declarado. [x] **Fase RED**: trazas reales, y he
**reproducido las tres** (los dos mutantes y el YAML revertido). [x]
**Cobertura** `[OK] 93,6 %`. [x] **Mutación**: verifiqué de forma independiente
que el alcance es **vacío** (`alcance_de_feature('F-081', base='87f4d84')` →
`lineas={}`), así que la ausencia de `progress/mutacion_F-081.md` es correcta:
la herramienta se niega a escribir un cero que nadie ha medido. **Prueba de
control del cero**: ignorando la exclusión el generador da 34/54/17 mutantes
sobre los tres `.py` del diff, luego no está roto; el cero viene de que el diff
**no trae ni un `.py` de producción**. [x] Sin «⚠ CAMPAÑA NO VÁLIDA» ni «base
rota». [x] RM1 y RM2: **N/A por alcance vacío**; la acotada de T4 la reproduje
entera, más de lo que RM4 pide. [x] RM3: ningún equivalente declarado. [x] RM5:
**N/A por nivel**. [x] RM6: **no se quitó ni una guarda** —no se tocó
producción—, que es el modo de fallo que RM6 vigila. [x] «Evidencias» con los
cuatro números. **C4 ter — N/A justificado**: no hay
`harness/rutas_sensibles.json`.

**C5** — [x] `tasks.md`: **N/A justificado** (`sdd=false`). Los ocho commits
siguen el formato `F-081 Tn: ...`. [x] Árbol limpio: lo único sin trackear es
`specs/F-080-.../` y `progress/explore_F-080_...md`, **ajenas a F-081**. [x]
`features.json` y `BACKLOG.md` al día.

## Cobertura: criterio → test

| # | Criterio | Test |
|---|---|---|
| 1 | El YAML dice `res` y trae la medición | `test_f081_c1_el_yaml_dice_...`, `test_f081_c1_el_yaml_deja_escrita_la_medicion_...` |
| 2 | Barrido y quién la creyó | `test_f081_c2_el_sql_de_las_formas_de_pago_...`, `test_f081_c2_el_nombre_del_centro_de_coste_...` + informe T2 (65 entradas) |
| 3 | Test que impide deshacerlo | `test_f081_c3_el_yaml_solo_atribuye_el_nombre_...` (5 params) + 2 controles |
| 4 | Muere `ventana_sql.py:215` | `test_f081_c4_cada_denuncia_...` (3 params), `test_f081_c4_una_obra_sin_codigo_...` |
| 5 | Muere `build_stg_step.py:732` sin tocarlo | `test_f081_c5_el_presupuesto_acotado_con_plan_PARCIAL_...` + las otras dos ramas de la guarda |
| 6 y 7 | Sin red ni BBDD; `init.sh` verde + mutación acotada | `grep` del reviewer (vacío) y las secciones C1 y C4 bis de este informe |

## Automejora propuesta (no aplicada)

1. **`CHECKPOINTS.md` C4**: aceptar `test_fXXX_cN_*` en features `sdd=false`.
2. **Ficha de F-081**: «`build_stg_step.py` es fichero del SELLO» es falso; que
   el líder lo corrija donde se haya propagado.
