<!-- progress/review_F-085.md -->
Revisión completa (pasada 1) · `main...HEAD` (merge-base `24f32fa`, HEAD `4453a1d`; implementer `08f14cb..HEAD`) · 2026-10-08

# F-085 · Review · CHANGES_REQUESTED

**Veredicto: CHANGES_REQUESTED.** Un solo defecto de fondo, pequeño pero en el
corazón de la feature: la ficha publicada de `raw.rac` sigue diciendo que la
tabla se recarga «con el mismo filtro» (R25). Todo lo demás —dominio, SQL,
ingesta, credenciales, diccionario, documentos, tests, rigor— está **revisado y
conforme**; la pasada 2 puede ser incremental sobre `4453a1d`.

**Rigor:** `estandar`, declarado en `features.json`. Exige fase RED, cobertura
≥ 80 % de lo cambiado y campaña de mutación muestreada (20, semilla 20260820);
no exige cero supervivientes.

## Qué se ejecutó (resultados reales)

- `bash harness/init.sh` tal cual en `4453a1d`: **exit 0**, **7.132 passed,
  228 skipped** en 2.289 s; `PUERTA COBERTURA [OK] 100,0 % (74/74)`;
  `PUERTA TAMAÑO [OK]` (134/150, 245/250, 207/220); 0 `[KO]`.
- **Mutación, recálculo independiente** (`harness.alcance` +
  `generar_mutantes`, cálculo puro): alcance 221 líneas (18 + 12 + 191) y **49
  mutantes**, igual que el informe. Muestra reproducida con `random.Random(20260820)`:
  los 20 son de `documento_procesos.py` (l. 58-189). **Campaña no reejecutada:
  8.873,9 s (2 h 28 min) según el informe**, por encima del umbral de 60 s.
- **RM3 sobre la muestra**: ninguno de los 20 es equivalente. El candidato
  dudoso, `len(candidatos) == 1 → == 2` (l. 186), lo mata
  `empleado_de_usuario([(501, 18)]) == 501` (candidato único de empresa ≠ 1);
  `slots=True → False` lo caza `test_f006_dataclasses_inmutables`.
- **Credenciales**: la ingesta pide a `sigrid-api` solo las columnas no
  excluidas (`ingest_raw_step.py:252-253`: `kept_cols` antes de
  `ensure_raw_table` y `stream_table`), así que `cla`, `fir`, `feccla`,
  `diascla`, `sid` y `cerid` **nunca salen de Sigrid**. Las 14 columnas que sí
  entran (cotejadas con `azure-apps/sigrid_tablas.md` l. 21726-21752): `ide cod
  res rol del obr delO codage codemp pos pro cet careje tipdes`; ninguna es
  credencial ni contacto. El diff entero (`main...HEAD`) solo nombra las
  credenciales, **ningún valor**; barrido de patrones DNI (`\d{8}[A-Z]`,
  `[XYZ]\d{7}[A-Z]`), `password=`, `contraseña:` y correos: **0 resultados**.
  El DNI solo aparece en `personal` (`06`, `00_setup`, ficha); el `12` no lee
  `raw.emp`, `codemp` ni `dni` (lo fija `test_f085_d4_*`).
- **F-095**: `retenciones/03_apuntes_contables.sql` no se toca y conserva
  `WHERE r.asiide <> 0 AND r.conide <> 0` (lo fija `test_f085_r5_*`). R31
  (mismas cifras antes/después) es MANUAL.
- **F-067 / la foto (D7)**: su SQL, su dominio y sus fichas, intactos. Solo
  cambian tests de ORDEN de sub-pasos, `test_f067_r27` (`>= 44`) y una nota en
  ARCHITECTURE. Conforme.
- **Sin escrituras contra Azure ni Sigrid**: el diff no toca `infra/` ni `.env`;
  yo solo leí por el MCP. `azure-apps`: commit local `e08a3bb`, sin push, limpio.

## Contra el design (desviaciones del §2 del informe)

Todas justificadas y aceptadas (CTE agrupado en `06`, `IS NOT DISTINCT FROM`,
`EPOCH::NUMERIC`, índice único `UPPER(login)`, fichas con su objeto, `raw.confir`,
`[[login]]`). `DROP ... CASCADE` es la convención de `compras/`. `rac.hor` es
entero (tipo 1014, como `confir.hor`, publicado `integer`): la división entera
del `CASE` de la hora es correcta.

## Checkpoints

- **C1** [x] `init.sh` exit 0 · [x] ficheros del arnés.
- **C2** [x] una sola `in_progress` (F-085) · [x] rama `feature/F-085-...` ·
  [x] `current.md` solo añade lo de F-085 (su volumen histórico es previo) ·
  [x] `history.md`: N/A hasta cerrar.
- **C3** [x] hexagonal: dominio sin imports de infraestructura, SQL en
  `compras/12_` y `personal/06_` · [x] primera línea con ruta en los 6 ficheros
  nuevos · [x] sin `print`, TODOs ni secretos; sin dependencias nuevas ·
  [x] semántica Sigrid: estado por la pareja tipo-estado (R8), `con` tipo 43 y
  `emp.ide` como en `01_recursos.sql`. Ámbito/fase, `importe_origen` y
  `obrfasamb`: N/A, la feature no toca importes ni planificación.
- **C3 bis** N/A: no toca `docs/referencia/` · **C4 ter** N/A: sin `rutas_sensibles.json`.
- **C4** [ ] **R25 no se cumple del todo** (ver Cambio 1). Resto: [x] R1-R24,
  R26-R28 con test trazable y en verde (tabla abajo) · [x] tests sin red ni
  BBDD (leen el texto del SQL/YAML; `pg` es un doble) · [x] MANUAL (T12-T14,
  R29-R32) con comando exacto en `impl_F-085.md` §6, enlazado desde
  `current.md` · [x] dobles: la comprobación automática corre en la suite verde.
- **C4 bis** [x] `rigor: estandar` declarado · [x] fase RED con trazas reales
  (T1: `ModuleNotFoundError` y 34 `NotImplementedError`; T2-T11: 79 failed) ·
  [x] cobertura `[OK]` 100 % · [x] mutación: informe de la herramienta, totales
  recalculados (221 / 49) · [x] muertos: campaña > 60 s, recálculo puro + RM,
  dicho arriba · [x] coste por mutante 8.873,9 × 2 / 20 = 887 s ≥ 1 s ·
  [x] sin «CAMPAÑA NO VÁLIDA», «Sin veredicto» = 0 · [x] **RM1**: mide
  `aa5b10f`; `aa5b10f..HEAD` solo toca `progress/` y `tasks.md` · [x] **RM2**:
  media × W = 887 s frente a 1.550-1.572 s de base (0,57: legítimo con 20/20
  muertos y `-x`); 20 × 443,7 = 8.874 = «Tiempo total» · [x] RM5 N/A por nivel
  `estandar` · [x] RM6 N/A: código nuevo, no se quitó ninguna guarda · [x]
  campaña manual N/A (automática, 49 mutantes) · [x] 0 supervivientes ·
  [x] «Evidencias» con los cuatro números y 2 workers.
- **C5** [x] T1-T11, T15, T16 `[x]` con commit `F-085 Tn:` (más `aa5b10f`, el
  ajuste de la suite) · **T12-T14 son MANUAL del humano**, pendientes y bien
  descritas · [x] árbol limpio (los worktrees listados son de otras sesiones) ·
  [x] `features.json`: `in_progress`, correcto.

## Cobertura requisito → test

| Req. | Test (`tests/test_f085_*`) |
|---|---|
| R1 | `sql::r1_rac_se_ingiere_sin_filtro_y_sin_tex`, `r1_el_comentario_*` |
| R2-R3 | `sql::r2_usu_excluye_exactamente_las_diez`, `r3_ninguna_credencial_*`, `r3_compras_no_lee_*`; `dominio::r3_*` |
| R4 | `sql::r4_el_censo_pasa_a_72_sin_conpro_rol_ni_log` |
| R5 | `sql::r5_retenciones_sigue_filtrando_el_asiento_en_su_sql` |
| R6-R9 | `sql::r6_*` (5), `r7_*` (2), `r8_*`, `r9_proceso_y_asiento` |
| R10-R14 | `dominio::r10/r11/r12/r13/r14_*` (oráculo) + `sql::r10/r11/r12/r13/r14_*` |
| R15 | sin test con su id: lo cubren `sql::r6_las_familias_*`, `r6_el_case_*`, `r11_el_orden_*`, `r14_*` y `r18_el_empleado_*`, que importan los literales del dominio |
| R16 | `sql::r16_sin_documento_no_entra` |
| R17-R21 | `sql::r17_*` (4), `r18_*`, `r19_*`, `r20_*` (2), `r21_*`; `dominio::r18_*` (6) |
| R22-R23 | `diccionario::r22_*` (4; R23 = «DOCVAL», «3.474», «97,4») |
| R24 | `diccionario::r24_*` (3) |
| R25 | `diccionario::r25_*` (4) — **incompleto: Cambio 1** |
| R26-R28 | `diccionario::r26_*`, `r27_*`, `r28_*`; `sql::r28_*` |
| R29-R32 | MANUAL (humano), T12-T14 |

## Cambios requeridos

1. **`config/diccionario/raw.yaml:1611`**, ficha `raw.rac`, párrafo «Como se
   carga»: quitar «, con el mismo filtro» de «cada noche la tabla se
   **recarga entera** desde Sigrid, con el mismo filtro». Era cierto con F-095
   y hoy contradice el párrafo de arriba («SE TRAE ENTERA DESDE F-085»); es el
   texto que lee el MCP para decidir si un recuento de pasos sobre `raw.rac`
   vale. R25 pide que la ficha diga que **ya no va filtrada**, sin matices.
2. **`tests/test_f085_diccionario.py:154`**
   (`test_f085_r25_raw_rac_ya_no_va_filtrada`): añadir
   `assert "mismo filtro" not in texto`, para que la regresión del punto 1 no
   vuelva. Fase RED: la aserción falla hoy sobre `4453a1d`; pegar esa traza en
   el informe.
3. **`progress/impl_F-085.md`**, nota de «Evidencias»: dice que las líneas de
   `SUB_PASOS` de los dos steps «no salieron en la muestra». En realidad
   **generan 0 mutantes** (recálculo: 18 + 12 líneas, 0 mutantes; los 49 son
   del dominio). Corregir la frase; los totales no cambian.

No hace falta repetir la campaña: ningún cambio toca su alcance (RM1).

## Para `done` (humano, tras aprobar)

T12-T14 (`impl_F-085.md` §6, LOCAL/dev, R29-R32); `usu.delO` en T12; ventana.

## Automejora (propuesta, no aplicada)

- C4: o se acepta que las MANUAL vivan en `impl_F-XXX.md` con puntero desde
  `current.md` (lo que se hace), o se exige el comando en `current.md` (lo que
  dice). C2: `current.md` tiene ~3.600 líneas cerradas; purgar o reescribir.
