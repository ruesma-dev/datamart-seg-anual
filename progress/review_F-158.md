<!-- progress/review_F-158.md -->
Revisión completa (pasada 1): `git diff fbf43dd..aea9e7c` (spec e847230 + T1-T5 4e46f0f..b7c091d + informe aea9e7c)

# F-158 · Review · Hotfix del céntimo negativo en el coste por contrato

- **Veredicto:** APPROVED, **condicionado a la puerta completa de `bash harness/init.sh` del líder
  sobre aea9e7c** (copia con `.env`). Si sale en rojo por algo que no sea el entorno, pasa a
  CHANGES_REQUESTED.
- **Nivel de rigor:** `estandar`, declarado en `features.json`. Exige fase RED, cobertura ≥ 80 % y
  mutación.
- Sin lecturas a Azure ni a Sigrid. Las pruebas de mutación, en una copia del scratchpad. Árbol
  limpio tras cada prueba.

## Lo que comprobé yo

| Qué | Resultado |
|---|---|
| `pytest` de F-158, F-150, F-140, F-147, F-149 y F-156 | **1392 passed, 1 skipped, 60,5 s** |
| `pytest` de F-006 (11 ficheros: fichas, formato, catálogo, cobertura, reglas, unicidad, publicación, contexto, punteros, relaciones, docs) | **1 failed, 1749 passed, 301 skipped, 285,8 s**. El rojo es `test_f006_r9_la_regla_de_frescura_cita_el_pipeline_real`, que reejecuté suelto: `ValidationError: SigridApiSettings (Field required)`. Es el `.env`: F-158 no toca ni `settings.py` ni la regla de frescura |
| `init.sh` en el worktree | No lo repito, por instrucción del líder. Según el implementer, el único rojo es el `.env` |
| Cobertura (`coverage` + `harness.cobertura --base main`) | **100,0 % de 12 líneas cambiadas (12/12)** |
| Alcance recalculado (`harness.alcance`) | 1 fichero, 37 líneas: `proyeccion_caja.py` (el SQL queda fuera del alcance automático) |
| Mutantes de la herramienta (`generar_mutantes`) | **5**. Los ejecuté uno a uno (RM4) con los tests de F-158, del personal de F-150 y del dominio de F-140: **5 de 5 muertos** |
| Dos filas de la campaña manual, al pie de la letra | D8 (`* acumulado / pendiente` → `/ pendiente * acumulado`) muere por `r1_multiplica_antes_de_dividir`. M2 (sin ` ORDER BY x.anio_mes`) muere por `r7_el_sql_sigue_al_dominio` |
| Ruff en los ficheros tocados | 3 avisos, todos de antes (`RUF002` ya estaba en fbf43dd; `E741` es de `test_f156`). F-158 no añade ninguno |

| Línea | Original → mutado (proyeccion_caja.py) | Fallos /132 |
|---|---|---|
| 187 | `if pendiente == 0:` → `if pendiente != 0:` | 7 |
| 187 | `if pendiente == 0:` → `if pendiente == 1:` | 1 |
| 193 | `acumulado += importe` → `acumulado -= importe` | 6 |
| 194 | `pendiente_personal * acumulado` → `pendiente_personal // acumulado` | 6 |
| 195 | `hasta_aqui - anterior` → `hasta_aqui + anterior` | 5 |

## Los puntos que pidió el líder

- [x] **Ni personal mayor que el pendiente ni suma descuadrada.** `p` > 0 porque `partes` filtra
  `d.pendiente > 0`. `pp = ROUND(p·cuota, 2)` con cuota en [0, 1] (`LEAST(1, …)`), así que
  `0 ≤ pp ≤ p`. Con el mes ≥ 0, el `ROUND` es monótono y `ROUND(u+i) = ROUND(u)+i` para un `i` en
  céntimos y `u ≥ 0`. De ahí, `0 ≤ personal ≤ importe`. La suma es telescópica: el `A` final es
  `p`, así que suma `pp` exacto, y R14 la sigue mirando. Lo prueban `r2_r3_invariantes` (2.000
  casos) y R4/R5.
- [x] **Sin empates en la ventana.** `_dev_plan` agrupa por (obra, concepto, partida, anio_mes)
  (línea 241) y `perfil` lo filtra: hay un solo mes por partición.
- [x] **La VENTA sigue con el personal a NULL.** `pendiente_personal` solo existe en COSTE (línea
  409). En VENTA es NULL, y la fórmula también da NULL.
- [x] **R14, R50 y R58 no cambian.** El diff no toca ningún `DO $$`. Lo fija `test_f158_r9`, que
  cubre también la cuota y el pendiente de la partida.
- [x] **El dominio y el SQL dicen lo mismo.** Los dos multiplican antes de dividir y redondean con
  `ROUND_HALF_UP`, como `ROUND(numeric)`. Lo fijan `r7` (el texto) y `r1_multiplica…` (la
  frontera de 0,085).
- [x] **La traza RED existe.** En `impl_F-158.md` está la salida real sobre fbf43dd (`12 failed,
  41 passed`), más `r6_el_algoritmo_de_ayer_daba_el_negativo` y los 18 de 2.000 casos con el
  algoritmo viejo.

## Las desviaciones del implementer

1. **Plan de 392521 reconstruido.** Acepto: reproduce los céntimos medidos (8.249,97 / 8.250,02 /
   -0,05). La propiedad general la defienden los invariantes. El dato real lo verifica el paso 4
   de design §6 (MANUAL).
2. **`test_f156_r34` pasa a `>=`.** Acepto. Sigue fijando la nota de la v71 de F-156, con el
   patrón de F-153 y F-155.
3. **La mutación es manual.** Acepto con justificación (C4 bis): la línea base de la herramienta
   necesita el `.env`. La sustituyen 5 de 5 mutantes de la herramienta, ejecutados por mí, más 16
   de 16 del implementer y M1-M5 sobre el SQL.
4. **La errata, sin tildes.** Acepto: es la convención ASCII de `postventa.yaml`.
5. **`features.json` sin tocar.** Acepto: F-156 sigue `in_progress` sobre fbf43dd. El estado lo
   lleva el líder.

## Checkpoints

- C1: [x] `init.sh` exit 0, condicionado: en el worktree solo falla el entorno, y manda la puerta
  del líder. [x] Los ficheros del arnés existen.
- C2: [x] Una sola `in_progress`. [x] Rama correcta. [x] `current.md` al día. N/A `history.md`,
  porque F-158 aún no es `done`.
- C3: [x] Hexagonal: `repartir_personal`, pura y en `domain/`. [x] Primera línea con la ruta.
  [x] Sin `print`, sin TODO y sin secretos. [x] Semántica Sigrid intacta.
- C3 bis: N/A, no entra ningún documento de fuera.
- C4: [x] Requisitos con test (tabla abajo). [x] Sin red ni BBDD. [x] MANUAL listado (T6, design
  §6). N/A dobles: no hay ninguno; el SQL se lee como texto y el sandbox lo descarta D4.
- C4 bis: [x] rigor declarado. [x] RED. [x] Cobertura 100 %, medida por mí. En el `init.sh` del
  worktree sale 8,3 % porque `-x` para en el `.env`: hay que confirmarla en la puerta del líder.
  - N/A justificado: no hay `mutacion_F-158.md`, porque la línea base requiere `.env` y crearlo
    está prohibido. Lo sustituyen el alcance y los 5 mutantes recalculados y ejecutados por mí.
  - [x] Muertos comprobados.
  - N/A justificado: el coste por mutante, «⚠ CAMPAÑA NO VÁLIDA», RM1 y RM2 no tienen informe de
    la herramienta que juzgar. El SHA verificado es aea9e7c, el HEAD revisado.
  - N/A RM5, por nivel `estandar`. [x] RM6: no se quitó ninguna guarda.
  - [x] Tabla manual con el texto exacto (la de arriba) y dos filas reproducidas. [x] D1 y D8,
    los dos supervivientes, analizados y cerrados con tests. [x] «Evidencias» con los cuatro
    números (campaña en serie, 1 worker).
- C4 ter: N/A, no hay `rutas_sensibles.json`.
- C5: [x] T1-T5 `[x]` con su commit. T6 (MANUAL) y T7 (la puerta del líder) quedan para después,
  justificado. [x] Sin temporales. N/A justificado: `features.json` en `pending`, lo lleva el
  líder (desviación 5).

## Cobertura de requisitos

| Req. | Test |
|---|---|
| R1 | `test_f158_r1_la_formula_por_acumulado`, `_sin_pendiente_no_hay_reparto`, `_multiplica_antes_de_dividir_como_el_sql` |
| R2, R3 | `test_f158_r2_r3_invariantes`; R14 en `test_f158_r9` |
| R4 | `test_f158_r4_cuota_uno_y_cero` |
| R5 | `test_f158_r5_sin_perfil_una_fila`; `test_f158_r7_el_pendiente_y_los_coeficientes_no_cambian` |
| R6 | `test_f158_r6_el_caso_tiene_los_numeros_del_diagnostico`, `_el_algoritmo_de_ayer_daba_el_negativo`, `_el_caso_1_0707_no_da_personal_mayor_que_pendiente` |
| R7 | `test_f158_r7_el_sql_sigue_al_dominio`, `_la_cabecera_lo_dice`; `test_f150_r46` |
| R8 | `test_f158_r8_un_mes_negativo_sigue_sin_contrato` (+ `test_f150_r49_*`) |
| R9 | `test_f158_r9_las_guardas_no_cambian` |
| R10 | `test_f158_r10_fichas`, `_version_72_con_su_nota`, `test_f158_la_errata_de_postventa` |
| R11 | MANUAL (T6, design §6) |

## Cambios requeridos

Ninguno bloqueante. Observaciones para el líder:

1. **Erratas del informe.** Dice «19 tests» en F-158 y son **17**. Las horas que da como «UTC»
   son locales (+01). Corrígelas si pasan a `history.md`.
2. **El merge.** `main` ya está en 43f45e3 (F-156 `done`). Espera conflictos en `features.json`,
   `current.md` y `BACKLOG.md`.
3. **El borde que queda fuera.** R2 solo vale con meses ≥ 0. Un mes negativo del plan (D2,
   1-0702), o un último mes que el redondeo del pendiente deje negativo, sigue yendo sin contrato
   y puede tumbar R50. Es el riesgo que design §8 ya declara, no una regresión.
4. **El informe formal de mutación** (`python -m harness.mutacion --feature F-158`, en la copia
   con `.env`) es opcional: no lo exijo.

## Automejora (propuesta, no aplicada)

C4 bis y `reviewer.md` no cubren una línea base roja **por el entorno**, como un worktree sin
`.env`. Propuesta: que valga la ejecución, por el reviewer, de los mutantes exactos de
`generar_mutantes` con su tabla de texto y fallos, o un `--tests` en `harness.mutacion` que acote
la suite.
