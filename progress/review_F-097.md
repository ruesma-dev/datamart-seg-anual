<!-- progress/review_F-097.md -->
Revisión incremental desde 6ca684d (pasada 3) · delta hasta HEAD `d4f36d0`

# F-097 · Review del reviewer

**Veredicto (pasada 3): APPROVED.** Los cuatro cambios de la pasada 2 están resueltos. El
informe de mutación es mi campaña sobre `6ca684d` y sigue valiendo por RM1, porque el delta
no toca código. Los tests nuevos matan de verdad S1 y S2: los apliqué a mano en una copia.
Quedan las verificaciones MANUAL del humano (T0, T17, T18, T19). T0 bloquea la puesta en
producción, no el cierre del código.

**Nivel de rigor:** `estandar` (declarado). Exige fase RED, cobertura >= 80 % de lo
cambiado y campaña de mutación con los supervivientes analizados. RM5 no aplica.

## Pasada 3

**Delta** (`323b3e5`, `a110ce7`, `afc6448`, `7e4f426`, `0f23dad`, `ba9b533`, `d4f36d0`):
dos tests en `test_f097_planificador.py` y `test_f097_descompuestos.py`, y
`progress/mutacion_F-097.md`, `impl_F-097.md` y este informe.
`git diff --stat 6ca684d HEAD -- etl_sigrid main.py config infra harness` sale **vacío**:
no cambia ni una línea de producción. Lo aprobado en las pasadas 1 y 2 sigue en pie.

- **Cambio 1, RESUELTO (informe de mutación).** He comparado `progress/mutacion_F-097.md`
  con mi informe original: alcance (1.333 líneas), totales (178 / 20 / 18 / 2 / 0 / 0),
  SHA `6ca684d251cc…`, líneas base, media, timeout, workers y muestreo son **idénticos**.
  Solo añade la nota de procedencia y los análisis de S1 y S2, que ya no están en
  `PENDIENTE`. RM1: el código medido es el de HEAD. RM2: 197,3 s × 2 = 394,6 s por mutante
  frente a una base de 448,4 s, coherente. Campaña > 60 s, así que no la reejecuto: ya es mía.
- **Cambio 2, RESUELTO (S1).** `test_f097_r21_dos_pendientes_que_llenan_el_lote_justo_van_juntas`.
  Copia con `git archive HEAD` y `descompuestos.py:437` `>` → `>=` aplicado a mano:
  **1 failed**. Sin mutar pasa.
- **Cambio 3, RESUELTO (S2).** `test_f097_r7_sin_la_opcion_no_hay_primera_carga` es de
  comportamiento: `CliRunner` más el paso doblado, a secas `False` y con la opción `True`.
  En la copia, con `default=True` en `main.py:5140` (`ingest-descompuestos`): **1 failed,
  1 passed**. Con `default=True` en `main.py:5169` (`build-descompuestos`): **1 failed,
  1 passed**. Cada mutación la caza su caso. Restaurado: 3 passed.
- **Cambio 4, RESUELTO.** El equivalente de `_redondeo` (`>=` → `>` en la primera guarda)
  está anotado en el informe de mutación con su motivo, el mismo que di yo.
- **Regresiones.** `bash harness/init.sh` entero: exit 0, **5931 passed, 219 skipped**,
  cobertura 99,6 % (516/518), tamaño dentro de los topes (ojo: `impl` 219/220).
- **Nota para el líder.** El commit local `0f23dad` (sin push) conserva, en este informe,
  la ruta de mi scratchpad con el identificador de sesión de Claude Code. `ba9b533` ya lo
  redacta. No es un secreto ni un ID de Azure (ni suscripción, ni tenant, ni credencial). Aun
  así, la puerta de GUID de `init.sh` lo marcaría si volviera al árbol. Reescribir ese commit
  antes del merge lo decides tú. Es error mío: no volveré a pegar rutas del scratchpad.

## Pasada 2 (resumen; texto completo en `git show d4f36d0:progress/review_F-097.md`)

**CHANGES_REQUESTED.** Los tres cambios de la pasada 1 quedaron resueltos, con evidencia en
PostgreSQL 16 local. Los importes que no caben en `NUMERIC(18,2)` salen NULL en SQL y en el
espejo, también en PLANIF_JO. `fullmatch` en el espejo. 15 casos límite, espejo frente a
SQL, todos iguales. Título de `current.md` corregido. El hallazgo 3 quedó como candidato a
ficha menor. Sobre el delta, 15 mutantes uno a uno: 14 muertos y 1 equivalente
(`_redondeo`). Pero el delta tocaba el alcance, así que por RM1 repetí la campaña en
`6ca684d`: 178 mutantes, 18 de 20 muertos. Salieron dos supervivientes reales sin analizar:
S1 (lote justo en el límite) y S2 (`--sin-tope` con `default=True`, que lanzaría la primera
carga a secas). Se pidieron sus tests y el informe nuevo.

## Pasada 1 (resumen; texto completo en `git show e366d05:progress/review_F-097.md`)

Revisión completa de `main...7d7dc0b`: **CHANGES_REQUESTED**. Hallazgos:

1. MEDIA: `fn_trocear` reventaba con un número válido pero grande.
2. BAJA: el espejo aceptaba un `\n` final que el SQL rechaza.
3. BAJA: un error de Postgres al escribir una versión aborta la ingesta. Va a ficha menor.
4. INFO: las PK de `lineas` y `cuadre_partida` dan 0 repetidos en Sigrid (solo lectura).
5. INFO: el SQL se prueba por texto (convención de F-056).
6. INFO: el título de `current.md`.

Verificado entonces y sin tocar después:

- **Incremental.** Ningún `DROP` ni `TRUNCATE` de las tablas de estado.
  `reemplazar_filas` va en una transacción. Si el recuento no cuadra, no se escribe y la
  versión se relee la noche siguiente.
- **Tope.** Orden vigente > cambiada > nueva, el ámbito 3 primero, y `--sin-tope`.
- **Orígenes y marcas.** v0, primera ABC, vigente y `tipo_version` de `mart`.
  `SUSTITUIDO_POR_PLANIFICACION` solo en ESTUDIO.
- **Cuadre.** Solo partidas hoja con `pre <> 0` y `obride <> 0`, tolerancia 0,01, y
  `SIN_DESCOMPUESTO` cuando no hay líneas.
- **R29.** Solo `obrparpre`; las otras 13 van a F-115.
- **Pipeline.** D3 y `check-declarados`: 11 objetos y ningún rojo propio.
- **Diccionario.** Master INCOMPLETO, tipos 3 y 11 PROVISIONALES, `version: 37`.
- **Reglas duras.** Sin secretos ni escrituras en Azure.
- **Campaña de `c1bf0bf`.** Verificada con RM1-RM4.

## Checkpoints (estado final)

- C1: [x] `init.sh` exit 0 (arriba) · [x] ficheros del arnés.
- C2: [x] una `in_progress` · [x] rama correcta · [x] `current.md` solo añade lo de F-097 ·
  [x] `done` con resumen en `history.md` (sin cambios).
- C3: [x] hexagonal y SQL en `sql/descompuestos/NN_*.sql` · [x] ruta en primera línea ·
  [x] sin prints de debug, secretos ni dependencias nuevas · [x] troceado robusto;
  ámbito/fase y versiones duplicadas de `obrfasamb`, bien.
- C3 bis: N/A, no toca `docs/referencia/`. C4 ter: N/A, no hay `rutas_sensibles.json`.
- C4: [x] R2-R29 con test (lo exige `test_f097_un_test_por_requisito`); R1, R30 y R31 son
  MANUAL · [x] sin red ni BBDD · [x] las MANUAL están en `current.md` con comando y
  resultado esperado (T0 con PARAR, T17, T18 C1-C4, T19) · [x] dobles contrastados con el
  original: el barrido de la suite, en verde.
- C4 bis: [x] `rigor` · [x] fase RED con trazas en las tres rondas · [x] cobertura (arriba) ·
  [x] mutación con totales verificados (campaña propia, `6ca684d`) · [x] muertos: la
  campaña la ejecuté yo · [x] coste por mutante 394,6 s · [x] sin cabecera de campaña no
  válida · [x] RM1 · [x] RM2 · N/A RM5 (`estandar`) · [x] RM6: las guardas nuevas añaden
  defensa, no quitan · N/A campaña manual (la automática dio 178) · [x] supervivientes
  analizados, con test que los mata · [x] «Evidencias» con 2 workers.
- C5: [x] tareas `[x]` con commit `F-097 Tn:`, más `R1-n` y `R2-n` de las reviews. T0,
  T17, T18 y T19 siguen `[ ]` a propósito: son MANUAL y bloquean la puesta en producción
  (decisión del humano del 2026-09-28) · [x] sin temporales · [x] `features.json` en
  `in_progress`.

## Cobertura requisito → test (prefijo `test_f097_`)

| Req. | Test | Req. | Test | Req. | Test |
|---|---|---|---|---|---|
| R1 | MANUAL T0 | R11 | `r11_*` (2) | R21 | `r21_*` (dominio y SQL) |
| R2 | `r2_*` (7) | R12 | `r12_*` (2) | R22 | `r22_catalogo_de_elementos` |
| R3 | `r3_*` (3) | R13 | `r13_*` (14) | R23 | `r23_*` (2) |
| R4 | `r4_*` (5) | R14 | `r14_*` (8) | R24 | `r24_tres_vistas_*` |
| R5 | `r5_*` (11) | R15 | `r15_estudio_sin_*` | R25 | `r25_*` (8) |
| R6 | `r6_*` (10) | R16 | `r16_planif_jo_*` | R26 | `r26_*` (2) |
| R7 | `r7_*` (4) | R17 | `r17_*` (6) | R27 | `r27_*` (6) |
| R8 | `r8_*` (8) | R18 | `r18_identificacion_*` | R28 | `r28_documentacion` |
| R9 | `r9_*` (3) | R19 | `r19_*` (7) | R29 | `r29_*` (4) |
| R10 | `r10_*` (3) | R20 | `r20_clave_*` | R30-31 | MANUAL T17-T18 |

## Automejora (propuesta, no aplicada)

- `reviewer.md`: si hay un espejo Python de un SQL, contrastar los dos en casos límite en
  un PostgreSQL local desechable. Así salieron los hallazgos 1 y 2.
- `CHECKPOINTS.md`, en RM1: cuando la review pide cambios en código del alcance, avisar en
  el propio informe de review de que la campaña caduca. Aquí costó una pasada más.
- `reviewer.md`: no escribir rutas del scratchpad en los informes, porque llevan el
  identificador de sesión y la puerta de GUID lo trata como sospechoso.
