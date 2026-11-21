# F-127 · Revisión (reviewer)

Revisión incremental desde 876edbe (pasada 2): `git diff 876edbe..16651d9` (b5a2d62, 115d44b, a09e509, 16651d9) y `azure-apps` 7586308.

**Veredicto pasada 2: PENDIENTE SOLO DE C1** (la puerta completa del líder sobre 16651d9). Todo lo demás está
en `[x]`: si la puerta sale en verde, APPROVED; si no, CHANGES_REQUESTED por C1.

**Nivel de rigor:** `critico` (declarado): fase RED, cobertura 90 %, mutación con 0 supervivientes (60 %,
[100, 300]), RM1-RM7; e2e informativa.

## Pasada 2 · los tres cambios de la pasada 1

1. **[x] D9 (c1), las CP del centro `CP`.** R7 lleva la enmienda «2026-11-21, D9» y R15 la suya (la cuarta
   comprobación); design D9 tiene la decisión del humano con la confirmación de D7-b. El oráculo
   (`CODIGO_CENTRO_CONTRAPARTIDA = "CP"`, `es_cuenta_contrapartida(..., en_centro_contrapartida)`), el CTE
   `centro_cp` + la tercera rama de `cp` en 08 (`08_mayor_analitico.sql:81-105`) y su copia literal en la
   guarda de 10 (`10_mayor_analitico_general.sql:100-120`) dicen lo mismo, y `test_f127_r7_c3_el_conjunto_cp_con_d7`
   y `test_f127_r15_guarda_sin_cp` comparan los cuatro CTE con el mismo texto. R10: el literal `'CP'` lo
   fija el test contra la constante del dominio.
2. **[x] Cifras y frases.** Fichas, ARCHITECTURE, `current.md` (T13) y `azure-apps` 7586308 dicen 722.704 /
   181.804 (25,2 %) / 540.900 / 1.000 cuentas, con fecha 2026-11-21; la frase «Las cuentas de contrapartida
   ... no tienen fila» ahora incluye «todas las del centro `CP`». Ninguna cifra vieja sin fecha en el árbol
   (las de `raw.yaml`/`tables_sigrid.yaml` son la medición fechada de `raw.apa` del 2026-11-20).
3. **[x] Cuarta comprobación (C2) en la guarda.** `v_personal` con el mismo `GROUP BY ... HAVING
   bool_and(NORMAL) AND bool_or(restringido)` que el CTE `asientos_personal` de 08, sobre `g.asiento_id`
   (en 08, `NULLIF(a.conide, 0)`: el mismo identificador). Su test es `test_f127_r15_d9_guarda_sin_asientos_de_personal`.

**Fase RED `[x]`:** `impl_F-127.md` trae las salidas reales (ImportError de la constante; `6 failed, 180
passed` con las aserciones del CTE `centro_cp`; `3 failed` en las fichas) antes de cada cambio.

## Pasada 2 · verificación independiente

- **Azure, solo lectura** (desde el checkout principal, `pg._bootstrap_done = True`, `filas_solo_lectura`,
  el SELECT de 08 de 16651d9 como subconsulta, 35 s): completo **722.704** = `raw.apa`; restringidas
  **181.804** (CONTRAPARTIDA 174.295, APUNTE_RESTRINGIDO 7.509, SIN_RESOLVER 0, ASIENTO_PERSONAL 0);
  generales **540.900**; **1.000** cuentas; `restringido` nulo 0. Coincide con el implementer.
- **Residuo visible, con criterios propios y no con el CTE de 08:** cuenta cuyo centro tiene `raw.con.cod =
  'CP'` sin exigir `raw.cen` (833 cuentas): **0**; código `CP%`: **0**; asiento de personal (criterio C2):
  **0**; asiento con algún apunte restringido aunque no sea todo NORMAL (más laxo): **0**; mismo código que
  una CP actual en otra empresa (la c2): **0**; cuenta que es `caaconide` de algún recurso: **0**. Hay 20
  filas `raw.con` con `cod = 'CP'`, pero solo 10 son centros (`raw.cen`), y el residuo es 0 con las 20.
- **Mutación a mano (RM4), en una copia `git archive` de 16651d9** en el scratchpad, con `pytest -x
  tests/test_f127_mayor_analitico.py`: **9 de 9 muertos**. En 08: sin la rama `centro_cp`, con `'CP'`
  cambiado a `'CPX'` y sin el JOIN a `raw.cen`. En 10: sin la rama `centro_cp`, con `IF v_personal < 0`,
  con `bool_and` cambiado a `bool_or` y con `v_personal` sobre el completo. En el dominio: sin
  `en_centro_contrapartida` y con su defecto en `True`.
- **Cobertura del dominio**: 100 % (90 sentencias, 28 ramas) con `coverage --branch` en la copia.
- **Tests en el worktree:** `test_f127`: **188 passed, 1 skipped** (el de `azure-apps`, por la ruta del
  worktree). Batería de lo afectado (F-127, F-006, F-056, F-135, F-141, F-146, F-147, F-128, F-107, F-057,
  F-005 y los documentos del arnés): **3.994 passed, 22 failed, 370 skipped (1.413 s)**. Los 22 son los
  de siempre: 21 de `test_f006_comandos.py` y la frescura de `test_f006_reglas.py`, por `SigridApiSettings
  ... Field required` (el worktree no tiene `.env`). Caen igual en la base. Ninguno es de F-127.

## Pasada 2 · las preguntas del líder

- **(4) `test_f127_r22_ningun_nombre_de_persona`.** Antes prohibía «Juan» y «Romero»; ahora quita primero
  la cita exacta `FUENTE_D8` y prohíbe esas dos palabras en lo demás. Sigue cazando cualquier otra mención
  de Juan, y una cita mal escrita o partida haría fallar el test, no lo ablandaría. **Nunca protegió contra
  nombres de trabajadores en general**: solo conoce esas dos palabras. Esa protección la da el barrido de
  abajo, no el test. Acepto la desviación: la cita es la fuente de un dato de negocio (quien lo afirma), no
  un dato de un trabajador, y R22 ya nombraba el «aviso de Juan».
- **(5) Nombres y NIF en el diff nuevo.** Barrido en memoria (sin escribir nada a disco) de las líneas
  añadidas de `876edbe..16651d9` y de `azure-apps` 7586308 contra los 2.642 recursos de `raw.res` (nombre de
  `raw.con`, nombre y apellidos de `raw.emp`, `cif` y `dni`): **0 nombres completos, 0 parejas
  nombre-apellido, 0 NIF/DNI**, y 0 cadenas con forma de NIF. «Juan Romero» no casa con ningún recurso.

## Pasada 2 · observaciones (no bloquean)

1. **Lint nuevo de F-127**: `ruff` da I001 en `tests/test_f127_mayor_analitico.py:16`
   (`CODIGO_CENTRO_CONTRAPARTIDA` fuera de orden en el import). La puerta no lo bloquea (`LINT_BLOQUEA=0`),
   pero es deuda que nace en esta feature: `python -m ruff check --fix` sobre ese fichero antes del merge;
   lo compruebo en la pasada de evidencias.
2. `specs/F-127-mayor-analitico/tasks.md` T13 sigue con las cifras del 2026-11-20 (~544.330 / ~178.301). Las
   buenas están en `current.md`, que es lo que sigue el humano; conviene apuntar ahí en T13.
3. El comentario de 10 justo encima del `DO $$` («R15: ninguna fila de CP, ninguna de un apunte ... y
   general + restringidas») no nombra la cuarta comprobación; la cabecera del fichero sí la nombra.

## Checkpoints (estado tras la pasada 2)

- **C1** `[ ]` **pendiente de la puerta del líder** (`bash harness/init.sh` sobre 16651d9 en `puerta/F-127`).
- **C2** `[x]` F-127 es `in_review`, la única activa, en su rama. **C3 bis** N/A: no entra ningún documento
  de fuera (la respuesta de D8 es un correo resumido, sin original que versionar).
- **C3** `[x]` El dominio sigue siendo puro y el SQL está en `infrastructure/`. Sin secretos, sin prints y
  sin GRANT. `ruff`: observación 1.
- **C3 ter** `[x]` D8, contestada, con su fuente y su fecha en `spec_F-127.md` y en las fichas.
- **C3 quater** `[x]` `azure-apps` 7586308 toca solo `datamart_seg_anual.md`, en commit aparte, con
  `pull --rebase` previo y **sin push**: `main` va 3 por delante de `origin` (70a039a, 7586308 y un
  cd58cab de `partes`, que no es de F-127).
- **C4** `[x]` Requisitos → tests (tabla abajo); los tests no tocan red ni BBDD.
- **C4 bis**: fase RED `[x]`; cobertura: dominio al 100 % y la línea `PUERTA COBERTURA` llega con la
  puerta (C1); mutación, RM1-RM3, RM5 y RM6: **pendientes, pasada de evidencias** (T11 va tras el APPROVED);
  RM4 `[x]` (arriba); **RM7** `[x]`: la cuarta comprobación lee `contabilidad_restringida.mayor` (paso 02) y
  el general recién creado, así que no añade orden nuevo, y el orden 08 → 10 ya lo probé en la pasada 1.
  «Evidencias» `[x]`. Capa e2e: N/A, es un ETL sin interfaz y ningún requisito es `(capa: e2e)`.
- **C4 ter** N/A: no hay `harness/rutas_sensibles.json`.
- **C5** `[x]` T1-T10 `[x]`; los commits de la pasada 2 son de corrección de review (D9) y citan la
  decisión. T11 (campaña), T12-T16 (MANUAL) y T17 (la puerta) siguen abiertos, como corresponde.

## Cobertura requisito → test (`tests/test_f127_mayor_analitico.py`)
| Req | Test(s) |
|---|---|
| R1-R2 | `r1_el_completo_es_una_tabla…`, `r1_sin_filtrar…`, `r1_nada_multiplica`, `r1_indices…`, `r2_la_guarda_de_recuento` |
| R3-R6 | `r3_*`, `r4_no_lee_los_campos_vetados_de_apa`, `r4_la_obra_solo…`, `r5_saldo_acumulado…`, `r6_*` |
| R7 | `r7_*` (C1-C3, D7-b) y, de D9, `r7_c3_d9_toda_cuenta_del_centro_cp_es_cp`, `r7_c3_d9_el_centro_cp_es_el_de_codigo_cp`, `r7_c3_d9_sin_cuenta…`, `r7_c3_el_conjunto_cp_con_d7[centro_cp]` |
| R8-R11 | `r8_*`, `r9_*`, `r10_los_literales_del_sql_son_los_del_dominio` (con `'CP'`), `r11_*` · R13: MANUAL (T14) |
| R12, R14 | `r12_*`, `r14_*` |
| R15 | `r15_guarda_sin_cp` (con `centro_cp`), `r15_guarda_sin_apunte…`, **`r15_d9_guarda_sin_asientos_de_personal`**, `r15_guarda_general_mas…` |
| R16-R19 | `r16_*`, `r17_*`, `r18_*`, `r19_*` · R20: MANUAL (T15) |
| R21-R23 | `r21_*`, `r22_*` (cifras de la pasada 2, `r22_d8_contestada_en_las_fichas_de_las_cp`), `r23_*` |
| R24 | `r24_*` (el de `azure-apps` se salta en el worktree) · R25, R26: MANUAL (T13, T16) |

## Pasada 1 (resumen; detalle en el historial de este fichero, commit f920fb8)

Revisión completa de `90d1bfd...876edbe` y `azure-apps` 70a039a: **CHANGES_REQUESTED**. (1) 60 filas de 3
cuentas `CP.*` del centro `CP`, sin recurso ni abono `ANA`, llegaban al general (conceptos de nómina);
opciones c1/c2/c3, recomendada c1. (2) Las cifras y frases dependientes. (3) La guarda de R15 no vigilaba
C2. D7-b (5.857 filas y no 324) era la lectura literal de la spec, a confirmar por el humano. Verificado
entonces: `restringido` nunca NULL, las tres guardas fallan cerrado, ningún test de otra feature pierde lo
que protegía (F-056, F-135, F-141, F-146), F-147 +605 exactos, `R-PERFILES` en 996 caracteres, D3 y
diccionario v81 correctos, 0 nombres y 0 NIF en el diff. RM4 con 9 mutantes muertos y RM7 (mover 10 delante
de 08 pone en rojo la suite de F-127). Batería de entonces: 3.994 passed, 22 failed, todos previos a F-127
(`SigridApiSettings ... Field required`, también en la base).

## Automejora (propuesta, no aplicada)
- `spec-author.md` / `CHECKPOINTS.md` C4 bis (de la pasada 1): si una restricción se define por un
  CONJUNTO, medir el **residuo visible de su familia** (mismo centro, prefijo, código en otra empresa), no
  solo lo que el conjunto atrapa. En esta pasada se ha medido así y da 0 con seis criterios.
- Un test de «ningún nombre de persona» que solo conoce dos palabras da una falsa sensación de cobertura.
  Propuesta para `reviewer.md`: cuando una feature publique fichas sobre datos personales, el barrido
  contra `raw.res`/`raw.emp` (en memoria, solo recuentos) es obligatorio en cada pasada y consta en el
  informe; el test queda como guarda de la regresión concreta.

Azure: solo lecturas (`filas_solo_lectura`, READ ONLY) desde el checkout principal, sin cambiar su rama.
