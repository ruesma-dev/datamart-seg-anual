<!-- progress/review_F-158.md -->
Revisión completa (pasada 1): `git diff fbf43dd..aea9e7c` (spec e847230 + T1-T5 4e46f0f..b7c091d + informe aea9e7c)

# F-158 · Review · Hotfix del céntimo negativo en el coste por contrato

- **Veredicto:** APPROVED, **condicionado a la puerta completa de `bash harness/init.sh` del líder
  sobre aea9e7c** (copia con `.env`). Si esa puerta sale en rojo por algo que no sea el entorno,
  este veredicto pasa a CHANGES_REQUESTED sin más.
- **Nivel de rigor:** `estandar`, declarado en `harness/features.json`. Exige fase RED, cobertura
  ≥ 80 % de lo cambiado y mutación.
- Reviewer, 2026-11-05, ~17:15-17:45 UTC. Sin lecturas a Azure ni a Sigrid. Nada escrito fuera
  del worktree salvo el scratchpad. Árbol limpio (`git status`) tras cada prueba.

## Lo que comprobé yo

| Qué | Resultado |
|---|---|
| `pytest` F-158 + F-150 + F-140 + F-147 + F-149 + F-156 | **1392 passed, 1 skipped, 60,5 s** |
| `pytest` F-006 (fichas, formato, catálogo, cobertura, reglas, unicidad, publicación, contexto, punteros, relaciones, docs) | ver la sección «F-006» al final |
| `init.sh` en el worktree | no lo repito, por instrucción del líder. Según el implementer, el único rojo es el `.env` (`[KO] Falta .env`, `test_f006_t26`) |
| Cobertura (`coverage` de F-158 + F-150 → `harness.cobertura --base main`) | **`PUERTA COBERTURA: 100.0% de 12 líneas cambiadas cubiertas (12/12, umbral 80%)`** |
| Alcance recalculado (`harness.alcance`, base `main`) | 1 fichero, 37 líneas: `etl_sigrid/domain/proyeccion_caja.py` (el SQL no entra en el alcance automático) |
| Mutantes de la herramienta (`generar_mutantes`, cálculo puro) | **5**. Los ejecuté uno a uno sobre una copia del scratchpad (RM4), con F-158, F-150 personal y F-140 dominio: **5 de 5 muertos** (tabla abajo) |
| Dos filas de la campaña manual, reproducidas al pie de la letra | D8 (`* acumulado / pendiente` → `/ pendiente * acumulado`) muere por `r1_multiplica_antes_de_dividir`. M2 (sin ` ORDER BY x.anio_mes` en la ventana) muere por `r7_el_sql_sigue_al_dominio` |
| Ruff en los ficheros tocados | 3 avisos, todos de antes (`RUF002` en la línea 300 de `proyeccion_caja.py`, que ya estaba en la 263 sobre fbf43dd; `E741` en `test_f156`). La feature no añade ninguno |

Los 5 mutantes de la herramienta, con el texto exacto y el número de fallos (suite de 132 tests):

| Línea | Original → mutado | Fallos |
|---|---|---|
| 187 | `if pendiente == 0:` → `if pendiente != 0:` | 7 |
| 187 | `if pendiente == 0:` → `if pendiente == 1:` | 1 |
| 193 | `acumulado += importe` → `acumulado -= importe` | 6 |
| 194 | `pendiente_personal * acumulado` → `pendiente_personal // acumulado` | 6 |
| 195 | `hasta_aqui - anterior` → `hasta_aqui + anterior` | 5 |

## Los puntos que pidió el líder

- **El personal no puede superar el pendiente ni descuadrar la suma.** La fórmula del SQL es
  `ROUND(pp·A(m)/p, 2) − ROUND(pp·A(m−1)/p, 2)`. El pendiente de la partida `p` es > 0 (`partes`
  filtra `d.pendiente > 0`), y `pp = ROUND(p · cuota, 2)` con `cuota = LEAST(1, …)` ≥ 0. Por eso
  `0 ≤ pp ≤ p`. Si el mes es ≥ 0, el `ROUND` es monótono, y un importe en céntimos `i` cumple
  `ROUND(u + i) = ROUND(u) + i` para `u ≥ 0`. De ahí sale `0 ≤ personal ≤ importe`. La suma es
  telescópica: `A` final = `p`, así que suma `ROUND(pp) − 0 = pp` exacto. La guarda R14 sigue
  mirando esa suma. Lo prueban `r2_r3_invariantes` (2.000 casos, semilla fija) y R4/R5. [x]
- **Empates en la ventana `ORDER BY`.** `_dev_plan` agrupa por `(obra, concepto, partida_id,
  anio_mes)` (línea 241 de `07`), y `perfil` es un filtro suyo. Hay un solo mes por partición:
  sin empates. El marco por defecto (`RANGE … CURRENT ROW`) da el acumulado hasta el mes,
  incluido. [x]
- **La VENTA sigue con el personal a NULL.** `pendiente_personal` es `CASE WHEN concepto =
  'COSTE'` (línea 409) y NULL en VENTA. `NULL · A / p` da NULL, y `importe_personal` queda NULL,
  como antes. El `INSERT` solo lo lee con `CASE WHEN x.concepto = 'COSTE'`. [x]
- **Las guardas R14, R50 y R58 no cambian.** El diff no toca ninguno de los tres `DO $$`. Lo fija
  además `test_f158_r9_las_guardas_no_cambian`, y la cuota y el pendiente de la partida, también.
  [x]
- **El dominio y el SQL dicen lo mismo.** Las dos multiplican antes de dividir y redondean la
  mitad lejos del cero (`_redondear` = `ROUND_HALF_UP`, igual que `ROUND(numeric)`).
  `r7_el_sql_sigue_al_dominio` fija el texto del SQL y `r1_multiplica_antes_de_dividir` fija el
  orden en la frontera de 0,085. [x]
- **La traza RED existe.** En `impl_F-158.md` § «Fase RED» está la salida real sobre fbf43dd
  (`12 failed, 41 passed`): el `AttributeError` de `repartir_personal` y los `AssertionError` de
  R7, R10 y R46. El fallo del algoritmo viejo queda escrito en
  `test_f158_r6_el_algoritmo_de_ayer_daba_el_negativo` (8.249,97 frente a 8.250,02) y en el
  recuento de 18 de los 2.000 casos. [x]

## Las desviaciones que declara el implementer

1. **El plan de 392521 está reconstruido.** Lo acepto. El diagnóstico (spec_F-158 §2) solo da
   los cinco importes distintos. La distribución elegida reproduce los céntimos medidos en Azure
   (8.249,97 / 8.250,02 y -0,05), que es lo que tiene que fijar una regresión. La propiedad
   general la defienden los invariantes aleatorios, no el fixture. La prueba con los datos reales
   es la comprobación MANUAL de design §6, paso 4: 0 negativos y la fila de 2563363 / 2027-10 / CI
   ≥ 0.
2. **`test_f156_r34` pasa de `==` a `>=`.** Lo acepto. Un `==` contra la versión rompe en cada
   subida. El test sigue fijando lo que es de F-156: la nota `# version 71 (F-156, …)`. Es el
   mismo patrón que F-153 y F-155.
3. **La mutación es manual.** Lo acepto con justificación (ver C4 bis). La campaña del arnés no
   puede ni arrancar en el worktree: su línea base es la suite entera, roja por el `.env`, y está
   prohibido crearlo. La sustituí por los 5 mutantes exactos que genera la herramienta,
   ejecutados por mí: 5 de 5 muertos. A eso se suman 16 de 16 en la campaña manual del
   implementer (dos reproducidos) y M1-M5 sobre el SQL, que la herramienta no muta.
4. **La errata va sin tildes.** Lo acepto. `postventa.yaml` sigue la convención ASCII de los YAML
   del diccionario. Lo que se pedía era quitar «lA MASCARA», y ya no está.
5. **`features.json` no se toca.** Lo acepto. Sobre fbf43dd, F-156 sigue `in_progress` e
   `init.sh` admite solo una. El estado de F-158 lo lleva el líder al fusionar (ver C5).

## Checkpoints

**C1**
- [x] `init.sh` exit 0: condicionado. En el worktree sale rojo solo por el entorno (`.env`). La
  puerta completa la pasa el líder sobre aea9e7c. Ese resultado manda.
- [x] Los ficheros del arnés existen.

**C2**
- [x] Una sola `in_progress` (F-156 sobre fbf43dd; F-158 no pasa a `in_progress`).
- [x] Rama `feature/F-158-hotfix-devengo-negativo`.
- [x] `current.md` lleva la entrada de F-158.
- N/A Feature `done` con su resumen en `history.md`: F-158 aún no es `done`.

**C3**
- [x] Arquitectura hexagonal: `repartir_personal` es pura, en `domain/`, sin imports nuevos. El
  SQL está en `infrastructure/`.
- [x] Primera línea con la ruta en el test nuevo. El resto de ficheros ya la tenían.
- [x] Sin `print`, sin TODO y sin secretos.
- [x] Semántica Sigrid: no se toca (solo cambia el reparto aritmético).

**C3 bis.** N/A: no entra ningún documento de fuera.

**C4**
- [x] Todos los requisitos tienen test (tabla abajo).
- [x] Sin red ni BBDD: dominio y texto del SQL.
- [x] MANUAL listado: T6 y design §6.
- N/A Dobles de test: no hay ningún doble. El SQL se lee como texto (patrón de F-135) y se
  descarta el sandbox por D4, decisión del humano.

**C4 bis**
- [x] `rigor` declarado: `estandar`.
- [x] Fase RED con traza real.
- [x] Cobertura: 100 % (12/12), medida por mí. En el `init.sh` del worktree sale 8,3 % porque
  pytest para con `-x` en el rojo del `.env`. Hay que confirmarla en la puerta del líder.
- N/A, justificado: no existe `progress/mutacion_F-158.md`. La herramienta no puede medir la línea
  base sin `.env`, y crearlo está prohibido. En su lugar: alcance y 5 mutantes recalculados con
  `harness.alcance` y `generar_mutantes`, y los 5 ejecutados por el reviewer, todos muertos. El
  texto exacto está en la tabla de arriba.
- [x] Muertos comprobados, no solo contados: los ejecuté yo.
- N/A, justificado: el coste por mutante, la cabecera «⚠ CAMPAÑA NO VÁLIDA», RM1 y RM2 no tienen
  informe de la herramienta que juzgar. El SHA verificado es aea9e7c, que es el HEAD revisado.
- N/A RM5: por nivel, porque es `estandar`, y además no hay equivalentes declarados.
- [x] RM6: no se quitó ninguna guarda. Al contrario, D1 añadió un test de la guarda
  `pendiente == 0`.
- [x] La tabla manual, con el texto exacto, la aporto yo para los 5 de la herramienta. Reproduje
  dos filas del implementer (D8 y M2).
- [x] Supervivientes analizados: los dos de la primera pasada (D1 y D8) eran huecos reales y se
  cerraron con tests.
- [x] La sección «Evidencias» trae los cuatro números. La campaña manual es serie: workers 1,
  implícito.

**C4 ter.** N/A: no hay `harness/rutas_sensibles.json`.

**C5**
- [x] `tasks.md`: T1-T5 `[x]`, cada una con su commit `F-158 Tn:`. N/A justificado para T6
  (MANUAL del humano, después del merge) y T7 (la puerta del líder).
- [x] Sin temporales ni ficheros sin seguimiento.
- N/A justificado: `features.json` deja F-158 en `pending`. Lo actualiza el líder al fusionar
  (desviación 5).

## Cobertura de requisitos

| Req. | Test |
|---|---|
| R1 | `test_f158_r1_la_formula_por_acumulado`, `_sin_pendiente_no_hay_reparto`, `_multiplica_antes_de_dividir_como_el_sql` |
| R2, R3 | `test_f158_r2_r3_invariantes`; R14 en el SQL (`test_f158_r9`) |
| R4 | `test_f158_r4_cuota_uno_y_cero` |
| R5 | `test_f158_r5_sin_perfil_una_fila`; `test_f158_r7_el_pendiente_y_los_coeficientes_no_cambian` (la rama `sin_perfil`) |
| R6 | `test_f158_r6_el_caso_tiene_los_numeros_del_diagnostico`, `_el_algoritmo_de_ayer_daba_el_negativo`, `_el_caso_1_0707_no_da_personal_mayor_que_pendiente` |
| R7 | `test_f158_r7_el_sql_sigue_al_dominio`, `_la_cabecera_lo_dice`; `test_f150_r46` actualizado |
| R8 | `test_f158_r8_un_mes_negativo_sigue_sin_contrato` (+ `test_f150_r49_*`) |
| R9 | `test_f158_r9_las_guardas_no_cambian` |
| R10 | `test_f158_r10_fichas`, `_version_72_con_su_nota`; la errata en `test_f158_la_errata_de_postventa` |
| R11 | MANUAL (T6, design §6) |

## Cambios requeridos

Ninguno bloqueante. Observaciones para el líder:

1. **Erratas del informe del implementer.** Dice «19 tests» en F-158 y son **17**: los conté y los
   ejecuté. Las horas que da como UTC son hora local (+01): los commits van de 17:00 a 18:15
   +0100. No cambia nada, pero corrígelas si `history.md` copia esos números.
2. **El merge.** La rama sale de fbf43dd y `main` ya está en 43f45e3 (F-156 `done`). Espera
   conflictos en `features.json`, `current.md` y `BACKLOG.md`. Al resolverlos, F-158 tiene que
   quedar con su estado real.
3. **El borde que queda fuera.** La garantía R2 solo vale con meses ≥ 0. Un mes negativo del plan
   (D2, 1-0702), o un último mes que el redondeo del pendiente deje negativo, sigue yendo sin
   contrato y puede volver a tumbar R50. Esto no es una regresión: es el riesgo que design §8 ya
   declara.
4. **El informe formal de mutación** (`python -m harness.mutacion --feature F-158` en la copia
   con `.env`) es opcional y no lo exijo: los 5 mutantes ya están ejecutados. Ya no hay prisa
   (el despliegue queda para el 06-11), y el líder puede decidir si lo lanza.

## Automejora (propuesta, no aplicada)

Hace falta una regla en `CHECKPOINTS.md` (C4 bis) y en `reviewer.md` para el caso en que la línea
base de la campaña sale roja **por el entorno**, como un worktree sin `.env`. Propuesta: que valga
la ejecución, por el reviewer, de los mutantes exactos de `generar_mutantes` sobre la suite del
módulo, con la tabla de texto exacto y fallos. Otra opción es dar a `harness.mutacion` un
`--tests` que acote la suite. Hoy esa situación cae en un N/A que hay que justificar a mano en
cada feature.

## F-006

Los 11 ficheros (`fichas`, `formato`, `catalogo`, `cobertura`, `reglas`, `unicidad`,
`publicacion`, `contexto`, `punteros`, `relaciones`, `docs`) sobre aea9e7c, en el worktree:
**1 failed, 1749 passed, 301 skipped, 285,8 s**. Es el mismo número que da el implementer.

El único rojo es `test_f006_reglas.py::test_f006_r9_la_regla_de_frescura_cita_el_pipeline_real`.
Lo reejecuté suelto: `ValidationError: 2 validation errors for SigridApiSettings (Field
required)`. Es la configuración que sale del `.env`, que el worktree no tiene. Es rojo del
entorno, no de F-158: la feature no toca ni `settings.py` ni la regla de frescura. Las fichas
nuevas de `tesoreria.yaml`, la v72 y la errata de `postventa.yaml` pasan formato, unicidad y
publicación. El veredicto no cambia, y sigue condicionado a la puerta del líder con `.env`, donde
ese test tiene que salir en verde.
