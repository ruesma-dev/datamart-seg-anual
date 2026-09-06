<!-- progress/review_F-066.md -->
# F-066 · Revisión

**Revisión completa (pasada 1)** · `feature/F-066-ingesta-raw-pendientes`, HEAD
`26ce092`, árbol limpio. Diff revisado: `d1f56aa..HEAD`.

## Veredicto: RECHAZADO (CHANGES_REQUESTED) · 10 hallazgos, 4 bloqueantes

El fondo es sólido y lo verifiqué a fondo: 56 tablas sin duplicados, 56 fichas,
dominio puro, dobles que casan con los clientes reales y —reejecutando yo los 23
mutantes— **los mismos 22 muertos y 1 superviviente** del informe. Bloquea que
la herramienta declare inválida su propia campaña (C4 bis es checkbox duro) más
tres desajustes de papeleo baratos.

**Rigor `critico`**, declarado: C1–C5, fase RED, cobertura ≥ 80 %, campaña
completa, **cero supervivientes** salvo firma del humano, y las `MANUAL`.

## Checkpoints

**C3 bis: N/A justificado** — el diff no toca `docs/referencia/`, ni ahora ni en
el historial. **C4 ter: N/A sin nada que justificar** — no hay
`harness/rutas_sensibles.json`.

**En verde, y comprobado por mí, no leído del informe:**

* **C1** `init.sh` **exit 0** entero: 3.868 passed, 159 skipped, 682 s; `PUERTA
  COBERTURA` [OK] 92,5 % (662/716, nivel critico); `PUERTA TAMAÑO` [OK]; los
  siete ficheros obligatorios, ahí.
* **C2** una sola `in_progress` (F-066); rama correcta, no es `main` ni `dev`.
* **C3** hexagonal (`domain/recuentos.py` solo importa `dataclasses` y
  `collections.abc`; los clientes, en el CLI); ningún SQL nuevo, correcto:
  `ensure_raw_table` crea las tablas de `raw`; ruta en la 1.ª línea de los tres
  ficheros nuevos; sin `print()`, TODO sueltos, secretos ni dependencias nuevas;
  `ruff` limpio; semántica Sigrid intacta y `con.tip` medido por recuento.
* **C4** R1–R18 con test trazable (tabla abajo), 342 tests propios; ni red ni
  BBDD (`ApiDoble`/`PgDoble` revientan por `__getattr__`, con dos tests de
  control); **dobles cruzados contra el original**: `ApiDoble.leer_sql(sql,
  parameters=None, max_rows=None)` y `__enter__`/`__exit__` casan con
  `SigridApiClient`, y `PgDoble.table_exists/count_rows(schema, table)` con
  `PostgresClient` —a mano, porque la puerta automática solo barre `Postgres`
  (→ 8)—.
* **C4 bis** `rigor` válido; **fase RED** con traza real (`281 failed, 29
  passed` y el `ModuleNotFoundError`), más la fase RED al revés de tres tests
  nacidos de un hallazgo; cobertura [OK]; **totales recalculados aparte** con
  `harness.alcance` y `generar_mutantes` (cálculo puro) → **218 líneas (134+84)
  y 23 mutantes**, idénticos, y los tres supervivientes de la 1.ª pasada existen
  con su operador y su texto exacto; coste por mutante 144,0 s, sano; **RM1** lo
  medido en `ca31adb` es lo que reviso (los dos commits posteriores solo tocan
  papeleo); **RM2** base 208,9 s / media 144,0 s / 1 worker, coherente (con `-x`
  y 22 de 23 muertos, una media bajo la base es lo normal); **RM3** el
  equivalente sale vivo, no muerto; **RM5** reproducido; **RM6** ninguna guarda
  borrada; «Evidencias» completa, con el nº de workers.
* **C5** sin temporales ni artefactos; `features.json` real; un commit
  `F-066 Tn:` por tarea (T10+T11 y T12+T16 agrupados, nombrando ambas).

**Vacíos, y por qué:**

- [ ] **C4 bis · el informe de mutación LLEVA la cabecera «⚠ CAMPAÑA NO
      VÁLIDA»** («Sin veredicto (base rota)» sí está a 0). → 1
- [ ] **C4 bis · cero supervivientes**: queda 1 y su exención **no la ha
      aceptado aún el humano por escrito**, que es lo que `critico` exige. → 9
- [ ] **C5 · `tasks.md` tiene T15 en `[ ]` y T15 está hecha** en `26ce092`
      (verificado: los bloques R22 están en F-055, F-056 y F-057, F-067 ya traía
      los suyos y F-068 existe). T13 y T14 sí siguen legítimamente abiertas. → 2
- [ ] **C4 · las `MANUAL (humano)` de F-066 no están en `current.md` con su
      comando exacto**: van en prosa, y los comandos viven en `tasks.md` e
      `impl_F-066.md`. C4 los pide en `current.md`, como se hizo con F-025. → 3
- [ ] **C2 · `current.md` no describe solo la sesión activa**: 1.249 líneas con
      secciones cerradas (F-042 del 28-08, F-047, fases 1 y 2 de F-052, spec de
      F-025) y **el encabezado de F-066 duplicado** en las líneas 32 y 42. → 4
- [ ] **C2 · F-044 y F-047 están `done` sin resumen en `history.md`** (cruzados
      los 18 `done` contra el fichero). Deuda previa, ajena a F-066. → 10

## La campaña, reejecutada por mí

En un **worktree aislado** (borrado después; el árbol quedó limpio) apliqué
**los 23 mutantes** con `harness.mutacion.aplicar_mutante`: **22 MUERTOS y 1
SUPERVIVIENTE**, los mismos del informe. Mi primera pasada dio «23 muertos» y
era **falsa** —el worktree no hereda `.env`,
`test_f066_r15_el_comando_esta_registrado` se cae allí y con la base roja todo
parecía morir: la trampa exacta que caza la cabecera «no válida»—. Los de
`frozen`/`slots` no los matan los tests de F-066 sino el barrido
`test_f006_dataclasses_inmutables.py`. **RM5**: con `bold=True → False`
(`main.py:1995`) la suite sigue verde, así que la justificación se sostiene.
**Los números son correctos; falta que los firme la herramienta.**

## Trazabilidad requisito → test

| Req | Test |
|---|---|
| R1–R9 | `test_f066_r1..r9_*` (`tests/test_f066_ingesta_raw.py`), con los dos guardianes de duplicados |
| R10, R11, R13, R14 | `test_f066_r10/r11/r13/r14_*`: 14 tests sobre `raw.yaml`, `00_global.yaml`, `objetos_pendientes.yaml` |
| **R12** | **sin test propio.** Se cumple de hecho (los dos `pendientes` a `[]`) y lo vigila el trinquete `PENDIENTES_MAX` de `test_f006_cobertura.py`. → 6 |
| R15–R18 | `test_f066_r15..r18_*` (`tests/test_f066_recuentos.py`): 27 de dominio, formato y CLI con dobles |
| R19, R20, R24 | **PENDIENTES** de T13/T14: `mediciones.md` §3 y §4 dicen PENDIENTE |
| R21, R22 | verificados: commit `a900682` en `../azure-apps` y los bloques R22 en `features.json` |
| R23 | **NO CUMPLIDO**: campaña no válida (hallazgo 1) |

## Cambios requeridos

1. **[BLOQUEANTE · C4 bis, R23] Repetir la campaña con la base sana.** No basta
   relanzar: mientras `test_f024_r1_batch_id_tiene_forma_y_es_unico` (F-024) siga
   siendo aleatorio (0,833 % medido; 18 % de saltar en 24 pasadas), la próxima
   campaña puede invalidarse igual. Que el líder decida: arreglarlo —defecto
   real— o excluirlo dejándolo escrito. Mi reejecución dice qué saldrá (22/1):
   trámite, pero quien firma es el arnés.
2. **[BLOQUEANTE · C5]** `tasks.md`: marcar **T15 `[x]`**; T13 y T14 igual.
3. **[BLOQUEANTE · C4]** `progress/current.md`: sección de `MANUAL (humano)` de
   F-066 **con el comando exacto** (`python main.py timings`; `az monitor
   metrics list ... cpu_credits_remaining`; `check-raw-recuentos`;
   `check-diccionario`), igual que la de F-025.
4. **[BLOQUEANTE · C2]** `progress/current.md`: purgar las sesiones cerradas y
   borrar el encabezado de F-066 duplicado (líneas 32/42).
5. **[C4 bis / RM1] El informe de mutación declara un comando que no reproduce
   sus números.** Dice «`python -m harness.mutacion --feature F-066`», pero ese
   comando usa `--base dev` y, como la rama nace de `feature/F-025` (sin
   fusionar), el merge-base con `dev` es `cd18e096`: da **2.904 líneas y 247
   mutantes en 11 ficheros**, no 218 y 23, que solo salen con `--base
   d1f56aa1...`. **La base elegida es la correcta** —aísla F-066 de F-025—, pero
   hay que escribirla: quien recalcule ve 247 y no distingue un recorte legítimo
   de uno interesado.
6. **[C4]** R12 sin test trazable: un `test_f066_r12_*` de dos líneas lo cierra.
7. **[Menor]** `design.md` §1 y R9 dicen que `dncpro` tiene **286.428** filas y
   `mediciones.md` §1 dice **286.432**, dos veces. Una está mal.

## Observaciones (no bloquean)

8. **La puerta de dobles solo cubre `PostgresClient`**: `ApiDoble` queda fuera.
   Generalizar `test_f025_contrato_cliente.py` a los dos clientes y portarlo a
   `arnes-base`. Además `_contar_en_sigrid(api, ...)` no anota `api`.
9. **El superviviente `bold` necesita la firma del humano** (`critico` exige
   `supervivientes_maximos: 0`); yo lo reproduje y se sostiene.
10. **F-044 y F-047 (`done`) sin resumen en `history.md`**: deuda previa.

## Automejora (propuesta, no aplicada)

* **`CHECKPOINTS.md` C4 bis**: que el informe de mutación imprima el **comando
  exacto** con que se lanzó, `--base` incluido; el hallazgo 5 se vería solo.
* **`.claude/agents/reviewer.md`**: un worktree nuevo no hereda `.env`; **hay
  que medir la línea base en la copia antes de juzgar mutantes**.
