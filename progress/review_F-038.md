<!-- progress/review_F-038.md -->
Revisión incremental desde 7a01c15 (pasada 2): delta `7a01c15..9e21857`; la pasada 1 revisó entera `4dfe8c7..7a01c15`

# F-038 · Review · Fase 1 · el comparativo de ofertas

**Veredicto: APPROVED** (pasada 2). La pasada 1 pidió un solo cambio, ajeno al
código: F-039 había pasado a `spec_ready` sin decisión de nadie. Hecho.

## Pasada 2 · delta `7a01c15..9e21857`

- **Ficheros**: `features.json`, `BACKLOG.md`, `current.md`, `impl_F-038.md` y
  este informe. No toca `etl_sigrid/`, `tests/`, `config/` ni `specs/`: lo
  aprobado y la mutación siguen valiendo (RM1).
- **Cambio 1, hecho.** F-039 vuelve a `pending`, y `BACKLOG.md` lo refleja en
  la tabla y en la ficha. Frente a `main`, `features.json` ya solo cambia F-038
  (`in_progress`) y las prioridades del humano (`03dfcbc`). La nota sobre D4
  también está corregida: `current.md` e `impl` §6 la dan por decidida.
- **`bash harness/init.sh`** sobre `9e21857`: 6.614 passed, 223 skipped,
  cobertura `[OK]` 32/32. El primer intento salió KO solo en `PUERTA TAMAÑO`,
  por este informe a medio editar (141 > 140). Lo recorté y lo relancé:
  **ENTORNO LISTO, exit 0** (6.614 passed, 741 s; tamaño 139/140).

**Rigor:** `estandar`, declarado. Exige fase RED en los requisitos centrales,
cobertura de lo cambiado ≥ 80 % y mutación con los supervivientes analizados.

## Pasada 1 · lo verificado por mí (sigue valiendo: el delta no lo toca)

- **`bash harness/init.sh`** sobre `7a01c15`: **6.614 passed, 223 skipped**
  (1.008 s), `PUERTA COBERTURA [OK]` 100 % de 32/32 líneas. Primera ejecución
  KO solo en `PUERTA TAMAÑO` por ESTE informe en borrador (165 > 140);
  recortado y relanzado: **ENTORNO LISTO, exit 0** (6.614 passed, 945 s).
- **Contra Azure, solo lectura** (`psycopg` directo, `transaction_read_only =
  on`; sin el cliente del ETL):
  - **Paridad dominio ↔ SQL de la ficticia sobre datos reales**: el cuerpo de
    `fn_normalizar_nombre` + `fn_familia_ficticia`, copiado literal, sobre las
    71.302 ofertas, contra `familia_ficticia()` de Python: **8.049 pares
    (CIF, nombre), 0 discrepancias**; **32.896 ficticias** (la cifra de la
    spec). Locale `en_US.utf8`: `upper('técnica')` = `TÉCNICA`, el `translate`
    vale también con minúsculas acentuadas.
  - **Desviación 1 (`aprobado_por` solo con circuito cerrado), comprobada**:
    `confir.estfin` solo vale APROBADO (5), APROBADO UTE (51) y Aprobado
    Dirección Compras (114); `estado_es_final` es cierto en 18.801 + 256 + 171
    comparativos, justo esos estados, y en ningún RECHAZADO, EN ELABORACIÓN ni
    PROPUESTO. Equivale a «para los aprobados» (acceptance 5). **Aceptada.**
  - Guarda R21: 0 casos; `ctride < 0`: 0 filas (el `MAX(NULLIF(ctride,0))`
    casa con la guarda `> 0`). `comprv.docide` único (71.302/71.302);
    `maestro.v_obra_fichas` un `obra_id` por fila (922/922): el LEFT JOIN no
    multiplica.
- **SQL contra design §4**: columnas y orden iguales, CTE a CTE. Las cuatro
  magnitudes de `dco.totbas`, `Σ dcopro.tot` (`comlinide > 0`), `Σ
  comlin.can×pre` y `Σ contrato_lineas.importe`, sin IVA; ninguna `importe` a
  secas; ahorro/mínima/máxima con `FILTER (WHERE NOT es_ficticia AND … > 0)` y
  `>= 2`; ganadora solo con `n_ofertas_ganadoras = 1`; atípico `CASE` sin
  `ELSE` con 10 y 100000; contrato por `comlin.ctride` con la guarda lo primero;
  ni `prvide`, ni `totdoc`, ni `ctr.comide`, ni `raw.conest`.
- **`compras.contratos` no cambia** de columnas (`01_documentos.sql` fuera del
  diff): solo la ficha de `comparativo_id` (R22) y la relación nueva.
- **`azure-apps` `6a2bbde`**: los dos objetos, las funciones, el nuevo
  significado de `contratos.comparativo_id`, «nada existente cambia» y «sin
  desplegar». Sin push.
- **Desviaciones 2-6 (informe §2), aceptadas.** FASE_0 con `( |$)` cabe en
  design §3 y lo cubre la paridad. Los tests de otras features cambian por
  consecuencia directa (listas de `build_compras` en F-047/F-073/F-080; P1-P22
  y 18/2/2 en F-006, que pide R24; inventario de F-079; recuento 194 en el
  design de F-006): ninguno rebaja un umbral ni borra una aserción.
  `confir.fec` en `R-SIGRID-CON` es lo que lee `08`.

## Mutación

- **Arnés recalculado, no reejecutado** (3.011 s según el informe, > 60 s):
  `harness.alcance` 135 líneas (16 + 119) y `generar_mutantes` **14**, como el
  informe; el superviviente existe tal cual (`comparativos.py:117`, `entero`,
  `<= 0` → `<= 1`).
- **RM1**: SHA medido `9a73809…`; `git diff 9a73809..HEAD -- etl_sigrid/` vacío.
  **RM2**: base 393,6/397,7 s, media 215,1 s × 2 workers = 430 s por mutante,
  coherente; 14 × 215,1 = 3.011 s. **RM3**: ninguno de los 14 ni de los 24 del
  SQL es equivalente (M07 y M21 no cambian las cifras de hoy, sí la
  semántica). **RM6**: no se quitó ninguna guarda; test nuevo (0,50 € y 0,01 €).
- **Reproducido en un worktree desechable de HEAD** (borrado; `git status`
  limpio), base 936 passed: superviviente → `2 failed, 67 passed`; SQL **M09
  → 2 fallos, M19 → 1, M04 → 1**. Las tres filas, idénticas a la tabla.

## Checkpoints

**C1** [x] init.sh exit 0 · [x] ficheros del arnés.
**C2** [x] una sola `in_progress` · [x] rama `feature/F-038-comparativos` · [x]
la sección F-038 de `current.md` es el estado real (lo antiguo es deuda previa)
· [x] `history.md`: no aplica aún.
**C3** [x] hexagonal (dominio solo con `re`/`Decimal`; SQL en `sql/compras/08_…`)
· [x] primera línea con la ruta · [x] sin `print` de depuración (los de
`progress/mutacion_sql_F-038.py` son salida de CLI), secretos ni dependencias ·
[x] semántica Sigrid: `con.est`/`fec`/`res` por `con`, estado por la pareja.
**C3 bis** N/A: no toca `docs/referencia/`.
**C4** [x] R1-R24 con `test_f038_rN_*` en verde (tabla) · [x] sin red ni BBDD
· [x] T20-T24 en `current.md`, en orden, con comando y lo que debe salir · [x]
ningún doble nuevo (`_PgFalso` ya existía).
**C4 bis** [x] rigor declarado · [x] RED con traza real en T1-T6 (R3, R8-R12,
R14-R16, R19-R22, R24) · [x] cobertura `[OK]` 32/32 · [x] alcance y nº de
mutantes recalculados · [x] > 60 s: recálculo + tres filas reproducidas · [x]
430 s/mutante ≥ base · [x] sin «CAMPAÑA NO VÁLIDA», «Sin veredicto» = 0 · [x]
RM1 · [x] RM2 · N/A RM5: rigor `estandar`, sin equivalentes declarados · [x]
RM6 · [x] SQL manual con línea, texto exacto y nº de fallos · [x] superviviente
analizado · [x] «Evidencias» con los cuatro números y los workers · [x] ningún
N/A sin motivo.
**C4 ter** N/A: no existe `harness/rutas_sensibles.json`.
**C5** [x] T1-T10 `[x]` con commits `F-038 T1`…`T10` (T9 en dos) · [x] árbol
limpio · [x] `features.json` refleja el estado real. En la pasada 1 estaba en
`[ ]` (F-039); se corrigió en la pasada 2.

## Cobertura requisito → test (`tests/test_f038_*.py`)

| Req. | Test | Req. | Test |
|---|---|---|---|
| R1 | `r1_*` (3) + F-047 `r1_*` | R13 | `r13_las_cuatro_magnitudes_*` |
| R2 | `ofertas_r2_*` (2) | R14 | `r14_*` (SQL y ficha) |
| R3 | `ofertas_r3_*`, `prvide_r3_*` | R15 | `r15_*`, `ofertas_r15_*` |
| R4 | `ofertas_r4_*`, `r4_*` | R16 | `r16_*` (4: dominio, SQL, ficha) |
| R5 | `r5_fecha_alta_*` | R17 | `r17_el_contratado_*` |
| R6 | `r6_actividad_*` | R18 | `r18_recuentos_*` |
| R7 | `r7_obra_*` | R19 | `r19_*` (SQL y ficha) |
| R8 | `r8_*`, `r8_r9_*`, `r8_r10_*`, `ofertas_r8_*` | R20 | `r20_contrato_por_comlin_ctride` |
| R9 | `r9_*` (9) | R21 | `guarda_r21_*` |
| R10 | `r10_*`, `r8_r10_*` | R22 | `r22_*` (2) |
| R11 | `r11_*` (7) + mi paridad con datos reales | R23 | `r23_*` (2) |
| R12 | `ofertas_r12_*`, `totdoc_r12_*` | R24 | `r24_*` (10) |

## Cambios requeridos

Ninguno. El de la pasada 1 (F-039 a `pending`, entró en `44133de` sin
decisión del humano) está hecho en `9e21857`. Faltan T20-T24 del humano.

## Para el humano y el líder (no bloquea)

- Lo que no puede probar ningún test: que el SQL corra en Postgres (tipos de
  `confir.hor`, `dco.totbas`) y sus cifras. Eso es T21-T23; mi lectura previa
  ya cuadra con dos de ellas (32.896 ficticias, 0 casos de la guarda).
- **Automejora (propuesta, no aplicada)** para C5 de `CHECKPOINTS.md`: «el
  diff de `features.json` solo toca la entrada de la feature, salvo decisión
  citada del humano». Hoy nadie lo vigila (caso F-039).
