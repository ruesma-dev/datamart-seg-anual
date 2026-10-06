<!-- progress/impl_F-067.md -->
# F-067 · Informe del implementer · foto diaria de estados, contrato y código 2

Rama `feature/F-067-compras-seguimiento-mcp`, 2026-10-06. Rigor **crítico**. D1
una entrega; D2-D4 según la recomendación (acceptance 4 → F-055, no se toca).
Tareas T1-T15 hechas, un commit por tarea (`git log main..HEAD`); T16-T23 son
MANUAL del humano (§6). Nada se ejecutó contra Azure ni contra Sigrid: los
tests leen el TEXTO del SQL.

## 1 · Qué cambió

| Fichero | Qué |
|---|---|
| `etl_sigrid/domain/historial_estados.py` (nuevo) | Oráculo puro de la foto: literales (`TIPOS_HISTORIAL` 44/15, `UMBRAL_PRESENCIA` 0.98, `MOTIVOS_CIERRE`, `EPOCA_DELPHI`), `Tramo`, `aplicar_foto`, `resumir_foto`, `dias_en_estado`, `fecha_delphi` |
| `sql/compras/00_setup.sql` | `compras.fn_sigrid_tiempo(DOUBLE PRECISION) → TIMESTAMP` (época de Delphi) |
| `sql/compras/11_historial_estados.sql` (nuevo) | `historial_estados` e `historial_estados_fotos` (`CREATE TABLE IF NOT EXISTS`, PERSISTENTES, sin `DROP`/`TRUNCATE`/`DELETE`), índice único parcial del tramo abierto, el `DO` de la foto (pasos 1-6 del design §3) y `compras.v_estado_documentos` |
| `sql/compras/01_documentos.sql` | `contratos` + 5 columnas al final (forma de pago, retención de garantía `RET%` de menor `pos`, `fecha_ultima_modificacion`); `contrato_lineas`, `albaran_lineas`, `factura_lineas` + `codigo_alternativo`, `necesidad_id`, `necesidad_linea_id` (D3); índice `idx_com_alblin_ncl` |
| `sql/compras/10_necesidades.sql` (nuevo) | `compras.necesidades` (el DPC; sin estado) |
| `sql/descompuestos/06_views.sql` | `necesidad_id` al final de `v_pbi_planif_jo` y `v_pbi_master_planif_jo` (subconsulta escalar a `raw.dncpro`) |
| `application/steps/build_compras_step.py` | Sub-pasos `10` (cuenta `necesidades`) y `11` (cuenta `historial_estados`), docstring |
| `config/diccionario/compras.yaml` | Fichas nuevas (5) y columnas nuevas; `contratos` reescrita (R14-R16), `comparativos` (R26) |
| `config/diccionario/descompuestos.yaml` | `codigo_alternativo` = «código 2» (R23); `necesidad_id` en dos vistas |
| `config/diccionario/00_global.yaml` | `version` 44, comentario de versión, `para_que_sirve` de `compras`, P23 (parcial, F-067), P24-P26 |
| `docs/ARCHITECTURE.md`, `specs/F-006-mcp-azure/design_detalle.md` | Tablas persistentes de `compras`; enmienda del recuento (204 objetos) |
| `azure-apps/datamart_seg_anual.md` | Sección F-067, commit propio en ese repositorio (`master`, sin push) |
| Tests nuevos | `test_f067_dominio.py` (47), `test_f067_sql.py` (56), `test_f067_diccionario.py` (36): 139 |
| Tests ajustados | `test_f047_steps`, `test_f073_pipeline`, `test_f080_pipeline` (lista de sub-pasos); `test_f073_sql` (hash de `01`, que pedía recalcularlo «en F-067»); `test_f006_reglas` (26 preguntas: 21/3/2); `test_f038_diccionario` (versión `>= 43`); `test_f079_stg_consultable` (inventario de funciones); `test_f120_factor` (ver §2) |

**Sello de `descompuestos` intacto (R21)**: `git diff main --stat --
etl_sigrid/infrastructure/postgres/sql/descompuestos/` → solo `06_views.sql`.
Ni `descompuestos.lineas` ni `00/01/02/03` cambian: no retrocea nada.

## 2 · Decisiones y desviaciones (justificadas)

- **Fichas en el commit que crea el objeto** (T2-T9), no todas en T10/T11: la
  puerta de cobertura exige ficha o pendiente y así cada commit queda casi
  verde. T11 quedó para `contratos`, `comparativos` y `00_global.yaml`.
- **`resumir_foto` además del design §4**: oráculo de los contadores de la
  foto (altas = tramos abiertos en la foto − cambios). El SQL los saca con
  `GET DIAGNOSTICS ... ROW_COUNT` (altas = insertados − cambios).
- **Sin `WHERE` en el lateral de la retención**: la correlación va en el `ON`
  (`r.docide = c.ide AND x.cod LIKE 'RET%'`), porque `test_f084_c2` prohíbe
  cualquier `WHERE` tras `FROM raw.ctr c`; y el lateral va DETRÁS del del
  estado, que `test_f084_sql` lee como el primero. `valpor` con
  `::NUMERIC` antes de `ROUND` (con DOUBLE no existe `round(x, 4)`).
- **`v_pbi_planif_jo.dncpro_id` como `N:N`** (no `N:1`): el validador R5 lo
  exige porque la clave de la vista es `(obra_id, partida_id, orden)`.
- **`test_f120_r18` exigía `factor` como ÚLTIMA columna** de las dos vistas,
  en contra de R20. Se ajusta a «`factor` es la última de las de F-120»: D8
  protegía justo esto (`CREATE OR REPLACE VIEW` solo admite columnas al
  final). En las fichas `necesidad_id` va antes de `factor` para no tocar
  `test_f120_r24`.
- **`_ingested_at` es `TIMESTAMP` sin zona** (lo pedía comprobar la spec:
  `postgres_client.py`, `DEFAULT NOW()`): se lee en la misma zona de sesión que
  lo escribió, así que el paso a `TIMESTAMPTZ` es el inverso exacto.
- **Fechas de la vista en `Europe/Madrid`**, `dias_en_estado` con la fecha de
  Madrid de hoy menos la de `desde`; calculado al consultar.

- **`reset-compras` CONSERVA la foto (decisión del humano del 2026-10-06,
  delegada en el líder, opción a)**: ya no tira el esquema; ejecuta
  `SQL_RESET_COMPRAS` (`infrastructure/postgres/compras_reset_sql.py`): borra
  vistas, tablas (menos `TABLAS_PERSISTENTES` del dominio) y funciones, con
  `CASCADE`; los índices de las dos mueren solo con su tabla.
  `tests/test_f067_reset.py` (8) lo vigila, con un veto a borrar el esquema
  `compras` entero en todo `*.py/*.sql/*.ps1/*.sh` del repositorio (por eso
  el parche histórico `patches/main_py_patch_compras.py` ya no borra nada).
  Corregidos `README_COMPRAS_C1_C2.md`, `LEEME_INTEGRACION.md`,
  `ARCHITECTURE.md`, `azure-apps` y las dos fichas. RED: `2 failed, 6 passed`
  (el comando ejecutaba el borrado del esquema; el veto cazaba `main.py` y el
  parche). Mutación: el generador de `harness.mutacion` da **0 mutantes** en
  las líneas nuevas (`main.py`, el dominio y el módulo nuevo); a mano, 6 sobre
  el SQL del reset (sin `NOT IN`, sin `'p'`, sin `'m'`, sin `CASCADE`, otro
  esquema, una sola conservada): **6/6 muertos** (`progress/mutacion_F-067.md`).

## 3 · Hallazgos para el líder (fuera del alcance de la spec, NO tocados)

1. `reset-compras` borraba el esquema `compras` entero: resuelto, ver §2
   (decisión del 2026-10-06).
2. `scripts/compras_setup.py` hace `DROP TABLE raw."<tabla>" CASCADE`: sobre
   `raw.dncpro` se llevaría las dos vistas de `descompuestos`. Script de puesta
   en marcha antiguo, no de la nocturna.
3. Commits intermedios con alguna prueba ajena en rojo, ya verdes al final:
   `test_f073_sql` (hash) entre T5 y T7; `test_f073/f080_pipeline` entre T6 y
   su commit de ajuste; `test_f006_punteros` entre T7 y T8;
   `test_f079_stg_consultable` desde T2 hasta T14 (lo destapó la línea base de
   la mutación).

## 4 · Fase RED (trazas reales; comando y salida resumida a lo esencial)

Todas con `python -m pytest <fichero> -q -p no:cacheprovider [-k ...]`, antes
de escribir el código; después, en verde.

- **T1** `tests/test_f067_dominio.py` →
  `E   ModuleNotFoundError: No module named 'etl_sigrid.domain.historial_estados'`
  · `1 error in 0.36s`. Verde: `45 passed in 0.17s`.
- **T2** `-k tiempo` → `E  assert 0 == 1` (`count('CREATE OR REPLACE FUNCTION
  compras.fn_sigrid_tiempo(')`) · `4 failed in 0.19s`.
- **T3** `-k "historial or foto or veto"` (fichero 11 aún inexistente) →
  `E  AssertionError: SQL no encontrado: ...\compras\11_historial_estados.sql`
  · `17 failed, 4 deselected in 1.31s`.
- **T4** `-k estado_documentos` → `E  AssertionError: falta
  compras.v_estado_documentos` · `7 failed, 1 passed` (el que pasa es el veto
  «la vista nunca usa tiemod»).
- **T5** `-k contratos` → `E  Right contains 5 more items, first extra item:
  'forma_pago_id'` · `6 failed, 29 deselected in 0.41s`.
- **T6** `tests/test_f047_steps.py` → `E  Right contains one more item:
  '11_historial_estados.sql'` · `2 failed, 23 passed in 2.84s`.
- **T7** `-k lineas` → `E  Right contains 3 more items, first extra item:
  'codigo_alternativo'` · `10 failed` (3 eran de un test de universo mal
  escrito, que contaba dos `WHERE` en `WHERE EXISTS (... WHERE ...)`; se
  corrigió a comparar el `FROM` exacto, y es guarda de regresión).
- **T8** `-k "necesidades or steps or pipeline"` → `E  AssertionError: SQL no
  encontrado: ...\compras\10_necesidades.sql` · `12 failed, 42 passed`.
- **T9** `-k descompuestos` → `E  assert False` (`endswith("factor, (SELECT
  NULLIF(n.dncide, 0) FROM raw.dncpro n ...")`) · `2 failed, 3 passed`.
- **T10/T11** `tests/test_f067_diccionario.py`, ejecutado sobre un worktree del
  commit de T6 (`462fcf1`, antes de las fichas de líneas y necesidades) →
  `27 failed, 9 passed in 1.56s`; las de R8-R14 sobre el de T1 (`b3fac41`) →
  `10 failed`. Ejemplos: `E  assert 'codigo 2' in 'codigo alternativo (campo
  7), que en las lineas sincronizadas...'`; `E  assert 'penalizacion no es un
  campo de sigrid' in 'cabecera de cada contrato...'`.

## 5 · Verificado (resultado real)

- `bash harness/init.sh` sobre `37c915a`: **ENTORNO LISTO**; pytest **6976
  passed, 226 skipped** en 2.258 s (con cobertura); `PUERTA COBERTURA: 100.0%
  de 66 líneas cambiadas (66/66, umbral 80%, nivel critico)`; `PUERTA TAMAÑO:
  ... impl 196/220`. Tras él solo cambian este informe, `current.md` y el
  estilo de 4 líneas de `test_f067_dominio.py` (ruff `UP017`/`SIM300`); la
  pasada final de `init.sh` va en §8.
- Tests de la feature: `pytest tests/test_f067_*.py` → 139 passed.
- `git diff main --stat -- sql/descompuestos/` → solo `06_views.sql`.
- `git -C azure-apps log -1 --stat`: `datamart_seg_anual.md | 28 +++`.

## 6 · MANUAL del humano, EN ORDEN (tras el APROBADO del reviewer)

1. **T16** Merge a `main`; imagen y job:
   `powershell -NoProfile -File infra/70_build_image.ps1`;
   `powershell -NoProfile -File infra/85_update_job.ps1 -Tag rYYYYMMDD-HHmm`;
   `az containerapp job show -g rg-datamart-seg-dev -n caj-datamart-seg-dev
   --query "properties.template.containers[0].image" -o tsv` → el tag nuevo.
2. **T17** Dejar correr la nocturna (00:00 UTC): toma la LÍNEA BASE.
   `python main.py status` → `run-all` SUCCESS; `python main.py timings
   --last 1` → `build_compras` < +1 min sobre la noche anterior.
3. **T18** (solo lectura) `python main.py check-declarados`, `check-unicidad`,
   `check-relaciones`, `check-diccionario` → los cuatro con código 0.
4. **T19** (solo lectura) `SELECT * FROM compras.historial_estados_fotos;` →
   una fila, `es_linea_base`, ≈ 185.800 documentos; `SELECT count(*),
   count(codigo_alternativo), count(necesidad_linea_id) FROM
   compras.albaran_lineas;` → ≈ 1.163.000 / 357.000 / 378.000; `SELECT
   count(*) FROM compras.necesidades;` → ≈ 277; `SELECT
   count(retencion_garantia_porcentaje), count(forma_pago_id) FROM
   compras.contratos;` → ≈ 6.330 / 19.070. Desviación > 5 %: parar y avisar.
5. **T20** (segunda noche) `SELECT observado_en, n_cambios, n_altas,
   n_desaparecidos FROM compras.historial_estados_fotos ORDER BY 1;` → dos
   filas, cambios de decenas a cientos.
6. **T21** Reiniciar el MCP y preguntarle P23-P26 sin explicar nada, más el
   caso de Juan (`AC26/28510`, `codigo_alternativo = 'MOMOSA'`).
7. **T22** Correo a Compras y a Juan Romero: qué se responde ya, «más de tres
   semanas» cierto desde el día 21, la penalización no es un campo (¿dónde la
   escriben?), «actividad validada» no existe (F-055).
8. **T23** (a los 21 días) la consulta de `tasks.md` T23 sobre `tiemod` y P23
   a `respondible`.

## 7 · Mutación (detalle completo en `progress/mutacion_F-067.md`)

- **`python -m harness.mutacion --feature F-067 --timeout 1800 --workers 4`**
  sobre `d088327029b1b38f29cad6595e9d2056f9b1f060`, campaña COMPLETA: **50
  generados, 50 evaluados, 44 muertos, 5 supervivientes, 1 timeout**, 15.340 s;
  línea base 1.088-1.099 s por worker. El `--timeout` se fijó a mano porque con
  el suelo (120 s × 5 = 600 s) la línea base no cabía con 4 workers (primer
  intento abortado por el propio arnés).
  Una primera tentativa abortó además por la línea base EN ROJO:
  `test_f079_r3` no tenía `compras.fn_sigrid_tiempo` en su inventario; corregido
  en `d088327` antes de la campaña válida.
- **Supervivientes, todos cerrados** (análisis escrito en el informe):
  1. `n_abiertos >= 0` (l. 121): EQUIVALENTE (`len < 0` nunca se cumple); se
     quita la condición redundante y el mutante deja de existir.
  2. `n_abiertos > 1` (l. 121): hueco real → test nuevo
     `test_f067_r6_con_un_solo_tramo_abierto_tambien_hay_guarda` (aplicado a
     mano: 1 fallo).
  3. y 4. `UMBRAL_PRESENCIA // 100` y `* 101` en el mensaje (l. 125): el test no
     miraba el %; el mensaje pasa a `{UMBRAL_PRESENCIA:.0%}` y el test exige
     «menos del 98%.».
  5. y el timeout: `!= _CAMBIO` / `!= _DESAPARECIDO` en `resumir_foto`: con un
     cambio y un desaparecido los recuentos coincidían → test nuevo
     `test_f067_r8_cambios_y_desaparecidos_se_cuentan_por_separado` (3/1/2;
     aplicado a mano: 1 fallo).
- **Re-verificación sobre `d698881`** (`progress/mutacion_dominio_F-067.py`,
  versionado): el MISMO generador sobre TODAS las líneas del dominio contra
  los tests de la feature (subconjunto de la suite): **45 mutantes, 45
  muertos, 0 supervivientes**, 1 worker en serie. No se repitió la campaña
  entera (~4 h); queda el comando para el reviewer.

### Anexo · campaña MANUAL del SQL

`progress/mutacion_sql_F-067.py`, worktree desechable de
`cc8113ad5499622eabda245bd39fa33c3113e396`, **1 worker**, 10 ficheros de test
sin `-x` (sin `test_f073_sql`, cuyo hash lo mataría todo): **40 mutantes, 40
muertos, 0 supervivientes**; línea base 0 fallos antes y después (1197
passed). Tabla `fichero:línea | original -> mutado | fallos` completa en
`progress/mutacion_F-067.md`. Cubre la época y el `> 0` de Delphi, las dos
guardas, `IS DISTINCT FROM`, el tipo en cambio/desaparición, línea base y
`observado_antes`, el veto `DROP`, el índice único, la vista (tramo abierto,
Madrid, mínimo, tipos, pareja), la retención (`RET%`, `pos`, `LIMIT 1`, ×100),
`auxpag` LEFT, `tiemod`, las tres tablas de líneas, `necesidades` y las dos
vistas de `descompuestos`. La primera pasada (`57a2940`) dejó vivo M21 (`NOT
h.es_linea_base`): el test buscaba con `in`; ahora compara el elemento exacto.

## 8 · Evidencias

| Evidencia | Valor medido |
|---|---|
| Tests ejecutados | `init.sh`: 6976 passed, 226 skipped, 0 failed (139 de F-067) |
| Cobertura de líneas cambiadas | 100.0 % (66/66), `PUERTA COBERTURA` de `init.sh` |
| Mutantes Python (`harness.mutacion`) | 50 generados, 44 muertos, 5 supervivientes + 1 timeout, todos cerrados; re-verificación 45/45 muertos, **0 supervivientes** |
| Mutantes SQL (a mano) | 40 generados, 40 muertos, **0 supervivientes** |
| Tiempo de la suite | 2.258 s con cobertura (`init.sh`); 470 s sin ella |
| `init.sh` final | sobre `c946706`: ENTORNO LISTO; 6976 passed, 226 skipped en 2.090 s; cobertura 100 % (66/66); impl 207/220 |
