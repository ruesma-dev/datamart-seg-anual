<!-- progress/review_F-090.md -->
Revisión incremental desde 17ce64e (pasada 2): delta `17ce64e..2f3d927` + azure-apps `70cf76e`

# F-090 · Review · el índice de documentos adjuntos de compras

**Veredicto: APPROVED** (pasada 2). Pasada 1 (`17ce64e`): CHANGES_REQUESTED por cinco
cambios de documentación y estilo; los cinco están resueltos (tabla abajo).

**Nivel de rigor:** `estandar`, declarado en `harness/features.json`. Exige fase RED,
cobertura de lo cambiado ≥ umbral y campaña de mutación con supervivientes analizados.

## Verificación de la pasada 2

- `bash harness/init.sh` sobre `2f3d927`, entero: **VERDE**, 7.268 passed, 231 skipped (13 min 15 s), COBERTURA 100 % (28/28), TAMAÑO OK, ENTORNO LISTO.
- El delta toca `config/diccionario/compras.yaml`, dos tests, `tasks.md` y `progress/`; ni
  `etl_sigrid/` ni el SQL: el alcance de mutación no cambia y la campaña sigue valiendo
  (RM1). `ruff` sobre los ficheros de F-090: sin avisos. `azure-apps` `70cf76e` sin push.
- Lo aprobado en la pasada 1 (código, SQL, filtros, tests, mutación) no se relee.

| Pasada 1 | Resuelto en |
|---|---|
| 1. receta de `documents/read` sin `blob_column` | `compras.yaml` (ficha `documento_adjuntos`) y `azure-apps/datamart_seg_anual.md` dicen `blob_column: ima`, obligatorio, y que es la columna de `ruesma_rep.gra` y no de `raw.gra`; `test_f090_r21` exige `"blob_column: ima"`; el paso 4 del MANUAL de `impl` §5 trae la receta completa |
| 2. «Evidencias» desactualizadas | `impl` §6: campaña válida (8/8, 4 workers, `--timeout 1800`, 2.427 s, `b88fdbb`) e `init.sh` verde; §5 paso 1 «HECHO» |
| 3. `current.md` | F-090 con su estado real; fuera la sección «F-132 · FASE B en curso» (su pendiente de `01_documentos.sql` pasa a la de «CERRADA») |
| 4. T12 | `[x]` con la cifra |
| 5. SIM300 | `tests/test_f090_dominio.py:184` corregido |

## Verificación de la pasada 1 (sobre `335d671`, dada por buena)

- `init.sh` verde (7.268 passed, 231 skipped, cobertura 100 %, 28/28). Alcance y mutantes
  **recalculados** (`harness.alcance` + `harness.mutacion.generar_mutantes`): 132 líneas y
  **8 mutantes**, todos en `domain/documento_adjuntos.py` (las 5 claves de
  `FAMILIAS_ADJUNTOS`, los dos `is None`, `group(1)`); coinciden con
  `progress/mutacion_F-090.md`. Control del cero en `build_compras_step.py`: el fichero
  entero genera 12; las 20 líneas del diff, 0 (un `_SubStep` de datos). Cero legítimo.
- **Campaña no reejecutada: 2.427 s según el informe** (> 60 s): recálculo puro + RM1-RM6.

## Checkpoints

**C1** [x] `init.sh` en verde (arriba) · [x] ficheros del arnés.
**C2** [x] una sola `in_progress` (F-090) · [x] rama `feature/F-090-documento-adjunto` ·
[x] `current.md`: fuera la sección «F-132 · FASE B en curso» y F-090 con su estado real
(pasada 2, cambio 3) · [x] F-132 `done` tiene su entrada en `history.md`.
**C3** [x] hexagonal: el dominio solo importa `re` y `typing`; el SQL en `sql/compras/` con
`14_`; el step solo añade datos · [x] primera línea con ruta en los 5 ficheros nuevos ·
[x] sin `print`, sin TODO, sin secretos (barrido de IPs, GUID y `password` en el diff:
solo `127.0.0.1` ficticio en el informe), sin dependencias nuevas (`pglast` quedó en el
scratchpad del implementer) · [x] semántica Sigrid: no toca `amb`/`fas` ni importes; el
grano lo defiende la PK `adjunto_id` = `rcg.ide`, y el `LEFT JOIN raw.comprv` no
multiplica porque `compras.comparativo_ofertas` ya declara PK `oferta_id` = `comprv.docide`.
**C3 bis** N/A: la feature no añade ni cambia nada en `docs/referencia/`.
**C4** [x] R1-R25 y R27 con test `test_f090_rN_*` (tabla abajo), 101 tests, pasan; R26,
R28, R29 son MANUAL · [x] sin red ni BBDD: YAML y SQL se leen como texto · [x] MANUAL con
comando exacto en `impl_F-090.md` §5 y `current.md` apunta ahí (criterio aceptado en F-085
y F-132) · [x] dobles: F-090 no crea ninguno; los dos tests ajustados de F-047 y F-132
usan los mismos dobles de antes, y la puerta de dobles de `init.sh` sale en verde.
**C4 bis** [x] `rigor` declarado · [x] **fase RED** con salida real de T1, T2, T4, T5 y
T6-T7 (`impl` §3) · [x] cobertura de lo cambiado 100 % (28/28), en la puerta de `init.sh` ·
[x] mutación: informe generado por la herramienta, totales verificados (arriba) ·
[x] muertos: campaña > 60 s, no reejecutada, dicho arriba · [x] coste por mutante =
2.427 × 4 / 8 = 1.213 s ≫ 1 s · [x] sin «⚠ CAMPAÑA NO VÁLIDA», «Sin veredicto» = 0 ·
[x] **RM1**: medida sobre `b88fdbb`; de ahí a HEAD solo cambia `progress/mutacion_F-090.md`
· [x] **RM2**: línea base ~710 s, media 303,4 s con 4 workers → 1.213 s reales por
mutante (más que la base por la contienda de 4 suites a la vez, mismo orden de magnitud)
y 8 × 303,4 = 2.427 cuadra · [x] **RM3**: ninguno de los 8 es equivalente (cambiar una
familia o el grupo de la regex cambia el resultado; `15: ALBARAN` pisa la clave de
FACTURA) · N/A **RM5**: rigor `estandar`, sin equivalentes · [x] **RM6**: no se quitó
ninguna guarda · N/A campaña manual: la automática dio 8 · [x] sin supervivientes que
analizar · [x] **«Evidencias»** (`impl` §6): campaña válida, 4 workers, `--timeout 1800`,
2.427 s, SHA `b88fdbb`, e `init.sh` verde del árbol principal (pasada 2, cambio 2) ·
[x] ningún N/A sin motivo.
**C4 ter** N/A: no hay `harness/rutas_sensibles.json` en este repositorio.
**C5** [x] `tasks.md`: T1-T8 y T12 `[x]` con commit `F-090 Tn:` (T12 en `2f3d927`); T9-T11
MANUAL en `[ ]`, como debe ser ·
[x] `git status` limpio · [x] `features.json` en `in_progress`, correcto.

## Lo que pidió mirar el líder

- **Filtro en origen (D2)**: `rcg` solo enlaces con `con.tip IN (12, 14, 15, 44, 46)`, `gra`
  solo los gráficos que esos enlaces nombran; 43, 306 y 708 no entran ni en `raw` (R3, R5).
  Un gráfico con varios documentos entra solo si uno es de compras, sin su enlace de
  personal. `run-all --full` (`Dockerfile`) las recarga enteras cada noche con el filtro, y
  `check-raw-recuentos` cuenta con el mismo `where`.
- **Sin binario**: `gra` tiene dos binarios (`ima`, `pul`) y dos textos ilimitados (`tex`,
  `cam`) según `azure-apps/sigrid_tablas.md`: los cuatro fuera, R4 nombra la que falte.
- **`cod` + `emp` bastan**: sí. `ruesma_rep.gra.cod` es único y la spec probó una lectura
  con 200. La receta publicada ya lleva `blob_column: ima` (cambio 1, pasada 2).
  Los avisos del 11 % sin nombre y del 0,23 % sin binario están en la ficha y en `azure-apps`.
- **Objetos intactos**: ningún SQL de `compras` cambia salvo el nuevo `14_` (R17 vigila `01_`);
  `documento_procesos` y `v_estado_documentos` no dependen del `14` ni él de ellos.
- **MANUAL de `impl` §5**: en orden (imagen y job → ingesta `rcg` antes que `gra` →
  `build-compras` → `check-raw-recuentos` → diccionario v48 y MCP → timings), con cifras
  esperadas y qué hacer si salta la guarda. Ninguna escritura contra Azure ni Sigrid en la rama.
- **El SQL no ha corrido nunca contra Postgres.** Lo que lo respalda: 29 tests de texto,
  el parser real de Postgres (`pglast`, informe §4), el `DO $$ … RAISE EXCEPTION` ya probado
  en `08_comparativos.sql`, `fn_sigrid_date(BIGINT)` usado igual sobre `con.fec` (el mismo
  «Entero tipo fecha»), la regex `\.([^.\s]+)$` válida en ARE (`\s` dentro de corchetes está
  permitido) y la PK garantizada por `rcg.ide`. **Riesgos del primer `build-compras`**, no
  bloqueantes: (a) si la ingesta de `gra` falla la primera noche (`stop_on_error` falso por
  defecto), `raw.gra` no existe y `build_compras` cae en su último sub-paso, con el resto
  de `compras` ya hecho pero el paso en FAILURE; (b) con `raw.rcg` VACÍA la guarda pasa
  (`v_total > 0`) y publica una tabla vacía: lo caza `check-raw-recuentos`, no la guarda;
  (c) los tipos de `raw.rcg`/`raw.gra` los decide la ingesta: lo comprueba el `SELECT` de
  T9. Recomiendo T9 a mano antes de dejarlo a la nocturna.

## Cobertura (requisito → test)

| Req. | Test(s) |
|---|---|
| R1-R6 | `test_f090_ingesta_sql.py::test_f090_r1_*` … `r6_el_censo_pasa_a_74` (12) |
| R7-R10 | `test_f090_dominio.py::test_f090_r7_*` … `r10_*` (50, parametrizados) |
| R11-R18 | `test_f090_ingesta_sql.py::test_f090_r11_*` … `r18_*` (17) |
| R19-R25, R27 | `test_f090_diccionario.py::test_f090_r19_*` … `r25_*`, `r27_*` (22) |
| R26, R28, R29 | MANUAL: T9, T11 y T10 (`impl_F-090.md` §5, pasos 3-5) |

Sin cambios requeridos.

**Automejora (propuesta, no aplicada)**: en `CHECKPOINTS.md` C4 bis, «Evidencias», añadir
«y coinciden con el `progress/mutacion_F-XXX.md` vigente (workers, tiempo, SHA)»: aquí la
campaña se repitió después del informe y nadie actualizó las evidencias.
