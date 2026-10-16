<!-- progress/review_F-139.md -->
Revisión incremental desde 0b2fe60 (pasada 2) · la pasada 1 fue completa (`main...0b2fe60`)

# F-139 · Review (reviewer, 2026-10-16)

## Veredicto (pasada 2): APPROVED (APROBADO)

## Pasada 2 · delta `0b2fe60..cc9fa73`

Lo aprobado hasta `0b2fe60` queda dado por bueno. El delta es un commit, `cc9fa73` «F-139 T6:
verificaciones MANUAL en current.md (rechazo C4 del reviewer)»: `progress/current.md` +14 y
`progress/impl_F-139.md` +1. Ni código, ni test, ni diccionario, ni spec: no invalida nada aprobado.

- **Cambio requerido 1, aplicado.** `current.md` gana «Verificaciones MANUAL (humano), con su
  comando exacto» dentro de la sección de F-139: (a) R8/T5 con `git -C … log -1 --stat ec1e38a` y
  el `grep -n "abrir_adjunto" …` — **reproducidos**: `ec1e38a`, 1 fichero, +122 −3; 4 apariciones;
  (b) `python main.py publicar-diccionario` (v53, escritura que autoriza el humano; el comando
  existe en `main.py:2187`) y reiniciar el MCP; (c) T7 del líder con el motivo literal de R10.
- **Observación 1, aplicada**: `impl_F-139.md` lleva ya la primera línea con su ruta.
- Barrido del delta (mismos patrones que la pasada 1): cero aciertos; solo rutas locales del puesto.
- **C4** `[ ]` → **[x]** (MANUAL listadas en `current.md` con su comando exacto). El resto de
  checkpoints, sin cambios respecto a la pasada 1 (abajo).
- **init.sh** entero sobre `cc9fa73`: ver «init.sh» abajo (pasada 2).

## init.sh (tal cual, árbol limpio salvo este informe sin versionar)

- **Pasada 2** (`cc9fa73`): exit 0, `8080 passed, 249 skipped … in 2621.18s (0:43:41)`; COBERTURA
  N/A con su motivo; TAMAÑO `… impl 149/220, review 133/140`; ruff 275; `ENTORNO LISTO`.
- **Pasada 1** (`0b2fe60`): exit 0, `8080 passed, 249 skipped … in 3966.17s (1:06:06)`; COBERTURA
  N/A (sin líneas Python de producción); TAMAÑO en los topes; ruff 275 (deuda previa; el test nuevo
  limpio: `ruff check tests/test_f139_limite.py` → «All checks passed!»). `ENTORNO LISTO`.

## Nivel de rigor

`rigor: "estandar"` declarado en `features.json`. Exige fase RED, cobertura y mutación con
supervivientes analizados. Cómo se cumple aquí (cero líneas de producción):

- **Fase RED**: traza real en `impl_F-139.md` (`7 failed, 8 passed`). **Reproducida por mí** en una
  copia del scratchpad con `compras.yaml`, `00_global.yaml` y `ARCHITECTURE.md` de `main`:
  `7 failed, 8 passed` (R1, R2, R3×2, R4, R5, R6 en rojo por la razón esperada).
- **Cobertura**: N/A con motivo impreso por `init.sh` (sin líneas Python de producción).
- **Mutación**: N/A justificado. `python -m harness.mutacion --feature F-139 --salida <scratchpad>`
  → exit 3, «ALCANCE VACÍO … 0 fichero(s), 0 línea(s)» y no escribe informe. Recalculado con
  `harness.alcance.alcance_de_feature('F-139', base='main')` → `lineas={}`. **Prueba de control**:
  `generar_mutantes` sobre el único `.py` del diff (`tests/test_f139_limite.py`, 337 líneas)
  ignorando la exclusión → 29 mutantes: el generador funciona y el cero es exclusión por diseño.
  Los sabotajes del implementer miden los dientes del test; no sustituyen a una campaña.

## Verificaciones independientes del reviewer (pasada 1, copia en scratchpad)

| Sabotaje (copia) | Resultado |
|---|---|
| M1 · relación del índice `a: compras.albaranes.albaran_id` → `albaran_idx` | `:330 … rompe el contrato de abrir_adjunto …` · 1 failed |
| M2 · `from openpyxl import` → `from openpyxl_no import` en `load_excel_aux_step.py` | `:302 … la excepción de R7 … sobra: ya no importa openpyxl; quítala` · 1 failed |
| M3 · `from fitz import open as abrir` añadido a `steps/base.py` | `:227 … ['etl_sigrid/application/steps/base.py: fitz']` · 1 failed |
| M5 (nuevo) · la ficha nombra `abrir_adjunto` | `:105 … la herramienta aún no existe (R2)` · 1 failed |
| Sin sabotaje | `15 passed` |

`etl_sigrid` importado desde la copia (`etl_sigrid.__file__`); `git status` limpio tras todo.

**azure-apps (R8)**: `ec1e38a` («contrato de abrir_adjunto para mcp-bbdd (F-139, pliego H1-H13)»,
+122 −3) en `master`; el repositorio **no tiene remoto**, así que no hay push posible. Sección leída:
H1-H13 idénticos a la spec, SQL de H3, tabla de cinco familias, D1, D2 (ChatGPT), decisiones y «qué
se rompe si cambia»; «Qué rompe este proyecto a otros» la enlaza. Los commits posteriores de
`azure-apps` (`2cf42ec`, `7913365`) no tocan `datamart_seg_anual.md`.

**Barrido de secretos y datos** sobre `git diff main...HEAD` (líneas añadidas) y `ec1e38a`:
IPv4 `([0-9]{1,3}\.){3}[0-9]{1,3}`, GUID `[0-9a-f]{8}-[0-9a-f]{4}-…`, correos `@….(es|com)`,
`password|contrase|secret|api_key|x-api-key|Bearer|oid|upn|kv-`, NIF/NIE/CIF (`[0-9]{8}[A-Z]`,
`[XYZ][0-9]{7}[A-Z]`, `[A-W][0-9]{8}`), IBAN `ES[0-9]{22}`. **Cero aciertos** salvo la frase «Sin
secretos: el vault…» del informe. `progress/spec_F-139.md` solo trae agregados (recuentos, tamaños,
tiempos). `design.md` nombra el vault `kv-mcp-bbdd-dev` (nombre de recurso, no secreto).

## Checkpoints (estado tras la pasada 2)

**C1** [x] init.sh exit 0 (pasadas 1 y 2) · [x] ficheros del arnés presentes.
**C2** [x] una sola `in_progress` (F-139) · [x] rama `feature/F-139-leer-graficos-asociados` ·
[x] `current.md`: las secciones de F-139 arriba y al día (arrastra historia anterior, estado
heredado aceptado en F-037/F-136/F-138, no introducido aquí) · [x] `history.md` sin cambios.
**C3** [x] hexagonal: cero cambios en `etl_sigrid/`, SQL ni `main.py`; diff = ficheros previstos en
design §3-§4 (más `BACKLOG.md` regenerado y `progress/`) · [x] primera línea con ruta en
`tests/test_f139_limite.py` y en las tres de la spec · [x] sin `print`, sin TODO, sin secretos, sin
dependencias nuevas (`requirements.txt` intacto) · [x] semántica Sigrid: no toca cálculo; las cinco
tablas y claves coinciden con `relaciones` de la ficha y con `FAMILIAS_ADJUNTOS` del dominio.
**C3 bis** N/A: no toca `docs/referencia/` (el barrido se hizo igualmente, arriba).
**C4** [x] cada R automatizable con test `test_f139_rN_*` que pasa (tabla abajo); R8 es MANUAL por
spec y R10 es del líder tras el APROBADO · [x] sin red ni BBDD (YAML, Markdown y `ast`) · [x]
MANUAL en `current.md` con su comando exacto (`cc9fa73`; en la pasada 1 era `[ ]`) · [x] dobles:
F-139 no añade ninguno (`test_f025_contrato_cliente.py` pasa en la suite).
**C4 bis** [x] rigor declarado (`estandar`) · [x] fase RED con traza real, reproducida · [x]
cobertura N/A con motivo impreso · [x] mutación N/A justificado (alcance vacío recalculado + prueba
de control con 29 mutantes) · N/A muertos comprobados / tiempo de campaña / cabecera «⚠ CAMPAÑA NO
VÁLIDA» / RM1 / RM2: no hay campaña (alcance vacío, la herramienta no escribe informe) · N/A RM5:
rigor `estandar` · N/A RM6: no se quitó código defensivo (cero líneas de producción) · N/A campaña
manual: no se sustituyó la automática · N/A supervivientes: no hay · [x] «Evidencias» con los
cuatro números (8080/249/0; cobertura N/A; mutación 0 con motivo; 4.165,68 s) · [x] ningún N/A sin
motivo.
**C4 ter** N/A: no existe `harness/rutas_sensibles.json`.
**C5** [x] T1-T5 y T8 `[x]` con commits `F-139 T1..T5`; T6 (informe y este review, commits
`0b2fe60`, `cc9fa73`) se cierra con este veredicto y T7 es del líder tras el APROBADO (R10, fuera
de lo exigible aquí por indicación del líder) · [x] sin temporales · [x] `features.json`:
`in_progress`, coherente con el estado.

## Cobertura requisito → test

| Req. | Test (`tests/test_f139_limite.py`) |
|---|---|
| R1 | `test_f139_r1_la_ficha_dice_como_pedir_el_fichero_sin_el_500` |
| R2 | `test_f139_r2_la_ficha_declara_el_limite`, `test_f139_r2_la_ficha_no_afirma_que_la_herramienta_exista` |
| R3 | `test_f139_r3_la_regla_de_permisos_con_la_tabla_de_cada_familia`, `test_f139_r3_la_regla_del_propio_indice` |
| R4 | `test_f139_r4_ficheros_grandes_y_ofertas_sin_fila` |
| R5 | `test_f139_r5_la_version_sube_sobre_la_de_main` (`main` = 52, comprobado con `git show`; rama = 53) |
| R6 | `test_f139_r6_la_arquitectura_declara_limite_aviso_y_permisos` |
| R7 | `test_f139_r7_el_etl_no_importa…`, `…_control_el_barrido_lee_el_etl_de_verdad`, `…_sabotaje_un_modulo_que_importa_pypdf…`, `…_sabotaje_la_excepcion_no_perdona…`, `…_control_cada_excepcion_hace_falta` |
| R8 | MANUAL (spec); verificado por el reviewer (pasadas 1 y 2) |
| R9 | `test_f139_r9_las_familias_son_las_del_dominio`, `test_f139_r9_las_tablas_de_origen_existen_y_se_relacionan` |
| R10 | Del líder tras el APROBADO (T7) |

## Cambios requeridos

Ninguno. (Pasada 1: uno, las MANUAL en `current.md`; aplicado en `cc9fa73`.)

## Observaciones (no bloquean)

- Incidencias del informe: se pararon «los `init.sh` creados en los últimos 5 minutos». Matar por
  ventana de tiempo en una máquina compartida puede llevarse procesos ajenos; mejor por PID propio.
- R7 usa `ast`: no ve `importlib.import_module("pypdf")`. Aceptable como guarda.

## Automejora (propuesta, no aplicada)

Para `.claude/agents/reviewer.md`: si el delta de una pasada N ≥ 2 toca **solo** `progress/` y el
`init.sh` de la pasada anterior salió en verde, permitir sustituir el `init.sh` entero por sus
puertas no-pytest (`features.json`, BACKLOG, tamaño) más el `git diff --stat` que lo demuestre.
Esta pasada 2 costó otra hora de suite por 15 líneas de Markdown.
