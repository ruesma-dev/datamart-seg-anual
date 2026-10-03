<!-- progress/review_F-113.md -->
Revisión completa (pasada 1), `git diff main...HEAD` desde `1bc205e` hasta `37b38ed`

# F-113 · Review · la categoría sale del capítulo

**Veredicto: CHANGES_REQUESTED.** El código está bien y verificado a fondo. Lo
único que falla es la trazabilidad de C4: R14 y R15 (diccionario, README y
`tables_sigrid.yaml`) no tienen ningún test, y la `version` 41 que R14 exige no
la fija nada. Son tres cambios pequeños. No hace falta repetir ninguna campaña
(ver «Pasada 2»).

**Rigor:** `critico`, declarado en `features.json`. Exige fase RED, cobertura,
mutación con 0 supervivientes y las MANUAL listadas con su comando.

## Lo que verifiqué yo (no lo tomé del informe)

- **`bash harness/init.sh`** sobre `37b38ed`: ENTORNO LISTO, exit 0, **6.406
  passed, 221 skipped** (1.008 s). Cobertura `[OK]` 29/29. Tamaño `[OK]`.
- **Contraste T5, rehecho de forma independiente** con mi propio script en el
  scratchpad (`conn.read_only = True`, `transaction_read_only = on`, `ROLLBACK`,
  solo el CTE de `04_partidas.sql` sin `TRUNCATE` ni `INSERT`):
  - filas 395.207 / 395.207, 0 en solo una de las dos, **0 diferencias en las
    otras diez columnas** (R8);
  - transiciones **iguales celda a celda** a §2 de la spec: 0229 95 OTRO→CI;
    229 9 OTRO→CI; 596085 221 CI→OTRO; 0462 10 CD→CI; 998691 32 CI→OTRO;
    0500 11 CD→CI; 1734235 99 CD→CI y 13 CD→CP. Con A: **490 partidas en 7
    obras**. Con B, calculada aparte: **253 en 2**;
  - las raíces que hoy están en OTRO y cambian son solo `99` (95) y `TN` (9).
    Ninguna partida de raíz `PD`, `MP`, `LEV`, `GG`, `MC` ni de posventa
    cambia: el límite del humano se respeta;
  - la previsión global para T12 coincide: CD 287.734, CI 64.307, CP 8.421 y
    OTRO 34.745.
- **Diferencial entre dominio y SQL con datos reales:** `construir_arbol` sobre
  las filas reales de `raw.obrparpar` frente a la `categoria` del CTE. Mismos
  395.207 ids y **0 categorías distintas**. Esto cubre los colapsados de F-052,
  los ciclos y el tope de 40: dominio y SQL aplican la misma regla.
- **Campaña MANUAL reejecutada entera** (`python progress/mediciones/F-113_mutacion_sql.py`
  sobre `37b38ed`, 271 s, en un worktree que el script borra al terminar):
  **47/47 muertos, con el mismo nº de fallos fila a fila** que el informe
  (M01 3 … M27 1, D01 10 … D20 7). Línea base: 226 passed antes y después.
  Árbol limpio después.
- **Mutación del arnés recalculada** con `harness.alcance` y `generar_mutantes`:
  104 líneas (21 + 83) y **1 mutante** (`and`→`or`, `categoria_partida.py:69`),
  igual que el informe. Control con los ficheros completos: 43 + 1, así que el
  generador funciona. **Campaña del arnés no reejecutada: 1.349 s según el informe.**

## Checkpoints

**C1** [x] init.sh exit 0 · [x] ficheros del arnés. **C2** [x] una sola
`in_progress` · [x] rama de la feature · [x] la sección F-113 de `current.md`
es el estado real (lo antiguo es deuda previa) · [x] `history.md`: aún no `done`.
**C3** [x] hexagonal: `categoria_partida.py` solo importa `re` y el SQL sigue en
`sql/stg/` · [x] primera línea con la ruta en todos los ficheros nuevos · [x]
sin `print` en producción, sin secretos ni dependencias nuevas · [x] la
semántica no cambia el grano, ni ámbitos ni fases.
**C3 bis** N/A: no toca `docs/referencia/`. **C4** [ ] **R14 y R15 sin test trazable** (cambios 1 y 2). R1-R11 y R16 sí
tienen test, todos en verde. R12 es el contraste T5, sin test porque escribiría
en el Postgres compartido; lo reproduje yo arriba. R13 es MANUAL (T12) ·
[x] sin red ni BBDD · [x] T9-T12 en `current.md`, en orden y con su comando y
lo que debe salir · [x] no añade dobles.
**C4 bis** [x] rigor declarado · [x] RED con traza real (T1, T2, T3) · [x]
cobertura `[OK]` 100 % · [x] alcance y nº de mutantes recalculados · [x] >60 s:
recálculo puro más la campaña manual reejecutada entera · [x] coste por
mutante 1.349 × 1 / 1 ≥ línea base · [x] sin «CAMPAÑA NO VÁLIDA» y «Sin
veredicto» = 0 · [x] RM1: SHA completo (`140758b` y `8ecea16`); lo posterior
solo toca `progress/` y `tasks.md`, no el alcance · [x] RM2: base 464,9 s y
media 1.349 s con 1 worker, sin saltos de orden de magnitud · [x] RM3: ver
abajo · N/A RM5: no hay supervivientes declarados equivalentes que justificar ·
[x] RM6: no se quitó ninguna guarda (el `cod is None` se filtra antes de
`categoria_heredada`) · [x] campaña manual con línea, texto exacto y nº de
fallos, reproducida entera · [x] 0 supervivientes · [x] «Evidencias» con los
cuatro números y el nº de workers · [x] ningún N/A sin motivo.
**C5** [x] T1-T8 `[x]`, con 11 commits `F-113 Tn:` · [x] árbol limpio · [x]
`features.json` coherente (`in_progress`, `acceptance` ajustados).

**RM3, juicio.** M08 y M09 se declaran equivalentes y salen muertos. **No
invalidan la campaña.** Sobre datos son equivalentes: lo medí con los dos
órdenes del `CASE` sobre las 236 raíces distintas de Azure y hay 0
diferencias, y los prefijos son excluyentes por construcción. Los mata un único
test identificado, `test_f113_r10_la_raiz_completa_y_en_el_orden_del_dominio`,
que fija el contrato textual de R10 (el SQL prueba en el orden de
`CATEGORIAS_DE_CAPITULO`). La línea base está en verde antes y después. No se
da ninguna de las dos causas que RM3 vigila: suite roja o informe falso.

## Cobertura requisito → test

| Req. | Test | Req. | Test |
|---|---|---|---|
| R1 | `r1_*` (4 tests, 32 casos) | R9 | `r3_r4_r5_r9_construir_arbol_*` |
| R2 | `r2_*` (3) | R10 | `r10_*` (6, cruzan las constantes del dominio) |
| R3 | `r3_r4_r5_r9_*` | R11 | `r11_ningun_like_con_comodin_delante` |
| R4 | `r4_*` (3) y la cadena | R12 | sin test: T5, reproducido en esta revisión |
| R5 | `r5_*` (2) | R13 | MANUAL, T12 |
| R6 | `r6_*` (2), `r4_r6_*` | **R14** | **ninguno** |
| R7 | `r7_*` (3), F-052 `las_dos_ramas_*` | **R15** | **ninguno** |
| R8 | `r8_la_categoria_no_cambia_*` | R16 | `r16_la_cabecera_explica_*` |

**Desviación del test de F-123** (`== 40` → `>= 40`). La aserción de F-123 no
se pierde: el suelo 40 sigue, y es el mismo arreglo de `e138fcb` en F-120. Lo
que falta es el test **propio** de F-113 que fije el 41, como hicieron F-120
(`r26`) y F-123 (`r18`). Hoy volver a `version: 40` deja la suite en verde.
Ese hueco es el cambio 1. La de F-052 (14 → 15 columnas) es consecuencia
directa de R7: correcta.

## Cambios requeridos

1. **R14 sin test.** Añadir `test_f113_r14_*` (en `tests/test_f113_sql.py` o
   en un fichero de test de F-113) que compruebe cuatro cosas:
   - `version` de `00_global.yaml` `>= 41` y la nota `version 41 (F-113`;
   - `stg.yaml` (`partidas.categoria`, `capitulo_raiz_cod` y la nota 4 de
     cabecera): ya no dicen «HEURISTICA» ni «ENTRADA» y dicen «MAS CERCANO»;
   - las seis `categoria` de `mart.yaml` no dicen «heuristica»;
   - `raw.yaml`: `auxobrtca` ya no dice «catalogo OFICIAL» ni «catalogo
     bueno» y cita `tcaide` y los oficios; `obrparpar` cita `tcaide`.
2. **R15 sin test.** Añadir `test_f113_r15_*`: `README.md` §6.3 no contiene
   `LIKE '%CD%'` y explica prefijo, exacto y «más cercano»; §5.3.1 no dice
   «heurística sobre el código del raíz»; el comentario de `auxobrtca` en
   `config/tables_sigrid.yaml` ya no dice «sin depender de heurísticas» y cita
   `tcaide`.
3. **Fase RED de 1 y 2**: pegar en `impl_F-113.md` su fallo contra los ficheros
   de documentación de `main`, en un worktree desechable y no en el árbol real.
   De paso, corregir el docstring caducado de `tests/test_f052_arbol.py:183`
   («`capitulo_raiz_cod` es la ENTRADA de la heurística de categoría»): desde
   F-113 es informativo.

**Pasada 2** (incremental desde `37b38ed`): si el delta solo toca `tests/` y
`progress/`, la mutación sigue valiendo (RM1) y no se repiten T5 ni campañas;
`init.sh`, sí.

## Para el humano (no bloquea)

- La regla A es genérica. Si mañana una raíz `PD` o `MP` gana un hijo con
  código exacto `CI`, ese subárbol pasará a CI. Hoy ocurre solo con `99` y
  `TN`, que son las aprobadas en la tabla de la spec.
- **Automejora (propuesta, no aplicada)** de `reviewer.md` RM3: distinguir
  «equivalente sobre datos pero matado por un test de contrato textual con
  causa identificada» (válido, como M08 y M09) de «equivalente matado sin causa»
  (invalida la campaña). Y en C4 de `CHECKPOINTS.md`: «los requisitos de
  documentación del diccionario también llevan test (versión y fichas)», porque
  esta spec los dejó fuera del plan de tests y nadie lo vio hasta la review.
