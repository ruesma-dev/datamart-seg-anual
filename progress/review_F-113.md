<!-- progress/review_F-113.md -->
Revisión incremental desde 5e6ded4 (pasada 2): delta `5e6ded4..775f7f3`; la pasada 1 revisó entera `1bc205e..37b38ed`

# F-113 · Review · la categoría sale del capítulo

**Veredicto: APPROVED** (pasada 2). La pasada 1 pidió tres cambios, todos de
trazabilidad (R14 y R15 sin test). Los tres están hechos y los he verificado.
El código de producción no cambia desde la pasada 1, así que lo aprobado allí
sigue valiendo.

**Rigor:** `critico`, declarado. Exige fase RED, cobertura, mutación con 0
supervivientes y las MANUAL listadas con su comando. Todo se cumple.

## Pasada 2 · delta `5e6ded4..775f7f3` (commits `410b081` y `775f7f3`)

- **Ficheros del delta:** solo `tests/test_f113_docs.py` (nuevo),
  `tests/test_f052_arbol.py` (un docstring), `progress/impl_F-113.md` y
  `progress/current.md`. No hay producción, SQL ni diccionario. Por RM1, la
  mutación (`140758b` y `8ecea16`) y el contraste T5 siguen valiendo: no se
  repiten.
- **Cambio 1 (R14), hecho.** Ocho tests `test_f113_r14_*` (14 casos). Fijan
  cuatro cosas:
  - `version >= 41` y la nota `# version 41 (F-113` de `00_global.yaml`;
  - en `stg.yaml`, la nota 4 de cabecera y `partidas.categoria` /
    `capitulo_raiz_cod` sin «heuristica» ni «entrada», con «mas cercano»,
    prefijo, exacto, `tcaide` e «informativo»;
  - las seis `categoria` de `mart` sin «heuristica» y con «mas cercano»;
  - en `raw`, `auxobrtca` sin «catalogo oficial/bueno», con `tcaide` y los
    tres oficios, y `obrparpar` con `tcaide`.

  Ahora volver a `version: 40` deja la suite en rojo: el hueco de la pasada 1
  está cerrado.
- **Cambio 2 (R15), hecho.** Tres tests `test_f113_r15_*`. Fijan que
  `README.md` §6.3 no tiene `LIKE '%CD%'` y explica prefijo, exacto y «más
  cercano»; que §5.3.1 ya no tiene la heurística y cita `tcaide`; y que el
  bloque `auxobrtca` de `tables_sigrid.yaml` cita `tcaide` y los oficios.
- **Cambio 3, hecho.** La fase RED está pegada en `impl_F-113.md`. **La
  reproduje yo:** worktree desechable de `main` (`1bc205e`), copiando dentro
  solo `tests/test_f113_docs.py`: **17 failed** (todos los casos). En la rama:
  **17 passed**. Worktree borrado y árbol limpio. El docstring de
  `tests/test_f052_arbol.py:183` ya dice que `capitulo_raiz_cod` es
  informativo. `tests/test_f113_docs.py` + `tests/test_f052_arbol.py`: 42
  passed.
- **`bash harness/init.sh`** sobre `775f7f3`: ENTORNO LISTO, exit 0, **6.423 passed, 221 skipped** (899 s), cobertura `[OK]` 29/29, tamaño `[OK]`.

## Pasada 1 · lo verificado entonces (vale, el delta no lo toca)

- `init.sh` en verde sobre `37b38ed`: 6.406 passed y cobertura 29/29.
- **Contraste T5 rehecho con un script mío**, en solo lectura contra Azure
  (`transaction_read_only = on`, `ROLLBACK`):
  - filas 395.207 / 395.207 y **0 diferencias en las otras diez columnas**;
  - transiciones iguales celda a celda a la spec §2: con A, **490 partidas en
    7 obras**; con B, **253 en 2**;
  - de las raíces que hoy están en OTRO solo cambian `99` y `TN`; **0 partidas**
    de `PD`, `MP`, `LEV`, `GG`, `MC` o posventa;
  - el global para T12 coincide (CD 287.734, CI 64.307, CP 8.421, OTRO 34.745).
- **Diferencial entre dominio y SQL** sobre las filas reales de `raw.obrparpar`:
  mismos 395.207 ids y **0 categorías distintas**. Cubre colapsados, ciclos y el
  tope de 40.
- **Campaña MANUAL reejecutada entera:** 47/47 muertos, con el mismo nº de
  fallos fila a fila. Arnés **recalculado** (no reejecutado: 1.349 s): 104
  líneas y 1 mutante, como el informe. Control con los ficheros completos:
  43 + 1.

## Checkpoints (estado tras la pasada 2)

**C1** [x] init.sh exit 0 · [x] ficheros del arnés.
**C2** [x] una sola `in_progress` · [x] rama de la feature · [x] la sección
F-113 de `current.md` es el estado real (lo antiguo es deuda previa) · [x]
`history.md`: todavía no aplica, la feature aún no está `done`.
**C3** [x] hexagonal (dominio solo con `re`; SQL en `sql/stg/`) · [x] primera
línea con la ruta (también `test_f113_docs.py`) · [x] sin `print`, secretos ni
dependencias · [x] semántica: ni grano, ni ámbitos ni fases.
**C3 bis** N/A: no toca `docs/referencia/`.
**C4** [x] R1-R11 y R14-R16 con `test_f113_rN_*` en verde. R12 es el contraste
T5, sin test porque escribiría en el Postgres compartido; lo reproduje yo. R13
es MANUAL (T12) · [x] sin red ni BBDD · [x] T9-T12 en `current.md`, en orden,
con su comando y lo que debe salir · [x] no añade dobles.
**C4 bis** [x] rigor declarado · [x] RED con traza real: T1-T3, y R14-R15
reproducida contra `main` · [x] cobertura `[OK]` 29/29 · [x] alcance y nº de
mutantes recalculados · [x] más de 60 s: recálculo más la campaña manual entera ·
[x] coste por mutante ≥ línea base · [x] sin «CAMPAÑA NO VÁLIDA» y «Sin
veredicto» = 0 · [x] RM1: SHA completo, y nada posterior toca el alcance · [x]
RM2 coherente (base 464,9 s, media 1.349 s, 1 worker) · [x] RM3: ver abajo ·
N/A RM5: no hay supervivientes equivalentes que justificar · [x] RM6: no se
quitó ninguna guarda · [x] campaña manual con línea, texto exacto y nº de
fallos · [x] 0 supervivientes · [x] «Evidencias» al día · [x] ningún N/A sin
motivo.
**C5** [x] T1-T8 `[x]`, con sus commits `F-113 Tn:`, más las correcciones
`410b081` y `775f7f3` · [x] árbol limpio · [x] `features.json` coherente.

**RM3, juicio.** M08 y M09 son equivalentes y salen muertos, pero **no
invalidan la campaña**:
- sobre datos son equivalentes: comparé los dos órdenes del `CASE` en las 236
  raíces distintas de Azure y hay 0 diferencias;
- los mata un solo test, identificado: el de contrato textual de R10, que exige
  el orden de `CATEGORIAS_DE_CAPITULO`;
- la base está verde antes y después.

No se da ninguna de las dos causas que RM3 vigila: suite roja o informe falso.

## Cobertura requisito → test

| Req. | Test | Req. | Test |
|---|---|---|---|
| R1 | `r1_*` (4 tests, 32 casos) | R9 | `r3_r4_r5_r9_construir_arbol_*` |
| R2 | `r2_*` (3) | R10 | `r10_*` (6, cruzan las constantes del dominio) |
| R3 | `r3_r4_r5_r9_*` | R11 | `r11_ningun_like_con_comodin_delante` |
| R4 | `r4_*` (3) y la cadena | R12 | sin test: T5, reproducido en la review |
| R5 | `r5_*` (2) | R13 | MANUAL, T12 |
| R6 | `r6_*` (2), `r4_r6_*` | R14 | `test_f113_docs.py::r14_*` (8, 14 casos) |
| R7 | `r7_*` (3), F-052 `las_dos_ramas_*` | R15 | `test_f113_docs.py::r15_*` (3) |
| R8 | `r8_la_categoria_no_cambia_*` | R16 | `r16_la_cabecera_explica_*` |

**Desviaciones aceptadas:**
- F-123 (`== 40` → `>= 40`): se mantiene su suelo, y el 41 lo fija ahora
  `r14`;
- F-052 (14 → 15 columnas): es consecuencia directa de R7.

## Cambios requeridos

Ninguno. Para cerrar la feature faltan las MANUAL del humano, en este orden:
- **T9:** merge a `main`, imagen con tag fechado y el job apuntando a ella;
- **T10:** la nocturna;
- **T11:** publicar el diccionario v41 y reiniciar el MCP;
- **T12:** comprobación dirigida, contra la previsión que ya verifiqué.

## Para el humano (no bloquea)

- La regla A es genérica. Si mañana una raíz `PD` o `MP` gana un hijo con
  código exacto `CI`, ese subárbol pasará a CI. Hoy solo pasa con `99` y `TN`,
  que son las aprobadas en la tabla de la spec.
- **Automejora (propuesta, no aplicada):**
  - en `reviewer.md` RM3: distinguir el «equivalente sobre datos, matado por un
    test de contrato textual con causa identificada» (válido, como M08 y M09)
    del «equivalente matado sin causa» (invalida la campaña);
  - en C4 de `CHECKPOINTS.md`: «los requisitos de documentación del
    diccionario también llevan test (versión y fichas)». Esta spec los dejó
    fuera de su plan de tests y nadie lo vio hasta la review.
