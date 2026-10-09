<!-- progress/impl_F-090.md -->
# F-090 · Informe del implementer · el índice de documentos adjuntos de compras

Spec: `specs/F-090-documento-adjunto/` (APROBADA el 2026-10-09, D1-D7 según la
recomendación, `progress/spec_F-090.md` §8). Rigor `estandar`. Worktree
`../datamart-seg-anual-wt-f090`, rama `feature/F-090-documento-adjunto`.
**`init.sh` final en el árbol principal: lo hace el líder** (el worktree no tiene
`.env`; ver §6).

## 1 · Qué cambió (commits locales, sin push)

| Commit | Qué |
|---|---|
| `c7a8a54` | `git merge main` (F-132 fase B, F-135). Conflictos solo en `BACKLOG.md` (regenerado) y `progress/current.md` (las dos secciones conservadas) |
| `8660af3` T1 | `etl_sigrid/domain/documento_adjuntos.py`: `FAMILIAS_ADJUNTOS` (15, 44, 46, 12, 14), `EXTENSIONES_POR_CLASE`, `COLUMNAS_EXCLUIDAS_GRA`, `extension()`, `clase_fichero()`, `filtro_rcg()`, `filtro_gra()` + `tests/test_f090_dominio.py` (50) |
| `238b9c9` T2 | `config/tables_sigrid.yaml`: `rcg` y detrás `gra`, filtradas en origen con el literal del dominio, `gra` sin `ima`/`pul`/`tex`/`cam` (motivo al lado). Fichas `raw.rcg` y `raw.gra` en `raw.yaml`, «Son 74 tablas» + tests R1-R6 |
| `d9edb96` T3 | Censo 72 -> 74 en los tests que lo fijan |
| `20baaaa` T4 | `sql/compras/14_documento_adjuntos.sql` (guarda R15 en un `DO`, `DROP ... CASCADE` + `CREATE TABLE AS` con CTE `base`, PK `adjunto_id`, índices por `documento_id` y `comparativo_id`, `COMMENT`) + ficha `compras.documento_adjuntos` + `gra` en el punto 3 de `R-SIGRID-CON` + enmienda del diseño de F-006 (208 objetos) + tests R11-R18 |
| `2196d59` T5 | `_SubStep("documento_adjuntos", "14_documento_adjuntos.sql", "compras", "documento_adjuntos")` detrás de `estado_documentos` y el docstring + tests R16; ajuste de los tests que fijaban la lista de sub-pasos |
| `2eaa382` T6 | Relaciones `1:N` de `facturas`, `contratos`, `albaranes`, `comparativos` y `comparativo_ofertas` al índice; `00_global.yaml` **versión 48** y «las 74 tablas» + `tests/test_f090_diccionario.py` |
| `1c1064a` T7 | `docs/ARCHITECTURE.md` (74 tablas, `rcg`/`gra`, el índice, binario en `ruesma_rep`) |
| `b939e94` | `tests/test_f132_retirada.py` deja de fijar que `13` es el último sub-paso (lo destapó la suite completa) |
| azure-apps `fc40216` | `datamart_seg_anual.md`: 74 tablas, sección F-090 (SIN DESPLEGAR), abrir = `sigrid-api` |

Ficheros de producción: `domain/documento_adjuntos.py` (nuevo),
`sql/compras/14_documento_adjuntos.sql` (nuevo), `build_compras_step.py`,
`config/tables_sigrid.yaml`, `config/diccionario/{raw,compras,00_global}.yaml`.
NO se tocan `01_documentos.sql` (`compras.facturas`), `12_`, `13_`, el cliente
de Sigrid, `ingest_raw_step.py`, `settings.py` ni `objetos_pendientes.yaml`.

## 2 · Decisiones y desviaciones (también en `progress/current.md`)

- **Versión del diccionario 48, no 47**: `main` ya usó la 47 (F-132 fase B). Lo
  previó el design («el que llegue segundo re-numera la `version`»).
- **Las fichas van en el commit de su objeto, no en T6**: `raw.rcg`/`raw.gra` en
  T2 y `compras.documento_adjuntos` en T4, porque la puerta de F-006 exige ficha
  o pendiente para todo objeto ingerido o declarado en SQL (regla del líder).
  Por lo mismo, en T4 entran `gra` (`cod`, `fec`, `res`) en el punto 3 de
  `R-SIGRID-CON` (lo deriva `test_f006_fuente_que_gobierna`) y la enmienda de
  `specs/F-006-mcp-azure/design_detalle.md` (inventario 205 -> 208, columnas
  1608 -> 1624, consumo 96 -> 97; lo exige `test_f006_r24`).
- **Más tests fijaban el censo o la lista de sub-pasos que los que citaba la
  spec**: además de F-085 y F-095, `TOTAL_TABLAS` de `test_f066_ingesta_raw` y
  `test_f074_ingesta_censo` y un assert de `test_f097_ingesta_descompuestos`
  (72 -> 74); y `test_f047_steps`, `test_f073_pipeline`, `test_f080_pipeline`,
  `test_f085_sql`, `test_f132_sql` y `test_f132_retirada` fijaban que `13` era
  el ÚLTIMO sub-paso. R10 de F-132 dice «DETRÁS de `12`», no «el último»: esos
  tests pasan a comprobar el orden a partir de `10_necesidades.sql` y las dos
  listas `FICHEROS_COMPRAS` ganan `14`. Ningún test pierde lo que defendía.
- **`comparativo_id` de la oferta = `p.comide` sin `NULLIF`**, igual que
  `compras.comparativo_ofertas` (lo probé con `NULLIF(.., 0)` y lo quité: la
  spec dice «el `comprv.comide`»).
- **`extension()` recorta solo espacios (`strip(" ")`) y usa `\Z`**, para ser
  la misma expresión que `btrim` + `'\.([^.\s]+)$'` en Postgres; un test ata el
  patrón del dominio al literal del SQL.
- **El `COMMENT ON TABLE` nombra `ruesma_rep`** (dice dónde está el fichero); el
  test de R18 mira lo EJECUTABLE, sin el texto del comentario.
- `ARCHITECTURE.md`: «Va el ÚLTIMO de `build_compras`» (F-132) pasa a «DETRÁS
  de `12`», que es lo que sigue siendo cierto.

## 3 · Fase RED (salidas reales, `../datamart-seg-anual/.venv/Scripts/python.exe -m pytest <fichero> -q`)

T1, antes del dominio (`tests/test_f090_dominio.py`):
```
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.documento_adjuntos'
ERROR tests/test_f090_dominio.py
1 error in 0.76s
```
-> con el módulo: `50 passed in 0.38s`.

T2, antes de tocar el YAML (`tests/test_f090_ingesta_sql.py`):
```
FAILED tests/test_f090_ingesta_sql.py::test_f090_r1_rcg_filtrada_en_origen_sin_tiemod
FAILED tests/test_f090_ingesta_sql.py::test_f090_r2_gra_excluye_exactamente_binario_y_texto_ilimitado
FAILED tests/test_f090_ingesta_sql.py::test_f090_r3_los_dos_filtros_llevan_exactamente_las_familias
FAILED tests/test_f090_ingesta_sql.py::test_f090_r4_ninguna_columna_de_binario_se_ingiere
FAILED tests/test_f090_ingesta_sql.py::test_f090_r5_ninguna_familia_de_personal_o_posventa_en_los_filtros
FAILED tests/test_f090_ingesta_sql.py::test_f090_r6_el_censo_pasa_a_74 - Asse...
(… 5 más de R1-R3)
11 failed, 1 passed in 2.69s
```
(el que pasa es `r5_no_se_ingiere_auxgra`, cierto desde antes) -> `12 passed`.

T4, sin el SQL (`-k "r11 or r12 or r13 or r14 or r15 or r17 or r18"`):
```
AssertionError: no encontrado: ...\sql\compras\14_documento_adjuntos.sql
FAILED ...::test_f090_r11_una_fila_por_enlace_de_rcg_con_join_y_no_left_join
FAILED ...::test_f090_r13_comparativo_id_por_familia
FAILED ...::test_f090_r14_las_extensiones_del_sql_son_las_del_dominio
FAILED ...::test_f090_r15_guarda_de_huerfanos_antes_de_construir
FAILED ...::test_f090_r18_no_lee_ruesma_rep_ni_binarios
(… 8 más de R11-R18)
13 failed, 1 passed, 12 deselected in 0.49s
```
(el que pasa es R17 sobre `01_documentos.sql`, cierto desde antes) -> `26 passed`.

T5, sin el sub-paso (`-k r16`):
```
AssertionError: sin sub-paso: ['14_documento_adjuntos.sql'] (R16)
FAILED ...::test_f090_r16_el_subpaso_va_detras_de_estado_documentos_y_cuenta_su_tabla
FAILED ...::test_f090_r16_el_docstring_del_paso_nombra_el_sql
FAILED ...::test_f090_r16_todos_los_sql_de_compras_tienen_su_subpaso
3 failed, 26 deselected in 1.47s
```
-> `29 passed`.

T6-T7, sin la ficha del índice (`tests/test_f090_diccionario.py`):
```
FAILED ...::test_f090_r19_la_ficha_existe_con_su_grano_y_su_clave
FAILED ...::test_f090_r20_la_ausencia_de_fila_no_es_un_fallo
FAILED ...::test_f090_r21_donde_esta_el_binario_y_como_se_pide
FAILED ...::test_f090_r23_el_dato_personal - Asser...
FAILED ...::test_f090_r19_cada_documento_apunta_al_indice[facturas]
FAILED ...::test_f090_r24_global_version_y_recuento
FAILED ...::test_f090_r25_azure_apps - AssertionEr...
(… 11 más)
18 failed, 4 passed in 0.76s
```
(los 4 que pasan son las fichas de `raw` y «Son 74 tablas», hechas en T2) ->
`22 passed` tras T6 y T7.

## 4 · Fuera del alcance

- Abrir el fichero (herramienta en `mcp-bbdd`, o `portal`), poner nombre a los
  31.720 documentos sin `nom` en `ruesma_rep` (`sigrid-api`), leer el contenido
  de los PDF y replicar binarios: fuera, según la spec.
- **El SQL NO se ha ejecutado contra ningún Postgres** (regla: nada contra
  Azure; el worktree no tiene `.env`). Verificado: (a) el texto, con 29 tests;
  (b) la SINTAXIS con el parser real de Postgres (`pglast` 8.5 instalado solo en
  el scratchpad, fuera del repositorio y del manifiesto): 7 sentencias
  (`DoStmt`, `DropStmt`, `CreateTableAsStmt`, `AlterTableStmt`, 2 `IndexStmt`,
  `CommentStmt`) y el cuerpo PL/pgSQL del `DO`, sin error. Las columnas de `raw`
  que usa están en `azure-apps/sigrid_tablas.md` (`rcg`, `gra`) y en
  `08_comparativos.sql` (`comprv.docide`, `comide`). La primera ejecución real
  es el MANUAL T9.

## 5 · MANUAL pendiente, EN ESTE ORDEN (Azure lo autoriza el humano)

1. **Integrar y verificar** (líder): `bash harness/init.sh` en el árbol
   principal sobre esta rama -> verde.
2. **Imagen y job** (humano): imagen nueva con tag fechado y el job apuntado a
   ella; comprobar el tag del job (memoria «el repositorio en verde no es
   producción»).
3. **T9 · R26** (humano), contra Azure tras desplegar, o esperar a la nocturna:
   ```
   python main.py ingest --table rcg --full     # ~7 s de lectura; ~199.042 filas
   python main.py ingest --table gra --full     # ~42 s de lectura; ~199.042 filas
   python main.py build-compras                 # anotar «compras_substep_done sub_step=documento_adjuntos»
   python main.py check-raw-recuentos           # OK en rcg y gra (cuenta con el mismo where)
   ```
   `SELECT count(*), count(DISTINCT documento_id) FROM compras.documento_adjuntos;`
   -> ~199.000 y ~144.500 documentos (104.952 + 17.666 + 18.383 + 2.931 + 606).
   `SELECT familia, clase_fichero, count(*) FROM compras.documento_adjuntos GROUP BY 1, 2;`
   -> facturas ~99,5 % PDF; comparativos ~25 % EXCEL. Si la guarda R15 salta
   (`F-090 R15: N de M enlaces...`), reingerir `rcg` y luego `gra`.
4. **T10 · R27 y R29** (líder, lo autoriza el humano): `python main.py
   publicar-diccionario` (**versión 48**, 208 objetos, 1.624 columnas),
   `python main.py check-diccionario`, reiniciar `mcp-bbdd` y preguntarle: los
   adjuntos de una factura; cuántas facturas de 2025 no tienen adjunto; qué
   comparativos de la 0720 tienen un Excel (en el comparativo o en sus ofertas,
   por `comparativo_id`). UNA llamada a `documents/read` con un
   `cod_repositorio` publicado, sin guardar el fichero -> 200.
5. **T11 · R28** (líder): en la primera nocturna con F-090, `python main.py
   timings`: segundos de `ingest_raw.rcg`, `ingest_raw.gra` y del sub-paso,
   contra la ventana (4 h 39 min el 2026-10-09). Estimado: 1-2 min.

## 6 · Evidencias

| Evidencia | Valor real |
|---|---|
| Tests de F-090 | **101 passed** (`test_f090_dominio` 50, `test_f090_ingesta_sql` 29, `test_f090_diccionario` 22) |
| Suite completa en el worktree (sobre `1c1064a`, con cobertura, sin `-x`) | **7.155 passed, 113 failed, 231 skipped en 1.374,34 s (22 min 54 s)**. De los 113: 112 son EXACTAMENTE los mismos que fallan en la base (`c7a8a54`, mismo worktree sin `.env`: 112 failed, 7.031 passed, 228 skipped, 10 min 46 s), todos `ValidationError ... SigridApiSettings` por falta de `.env`; el 113.º (`test_f132_retirada::...r25_build_compras_ya_no_tiene_el_sub_paso_de_la_foto`) era mío y lo corrige `b939e94` (ese fichero, re-ejecutado: 25 passed + los 7 de entorno) |
| Los 112 de entorno, con ajustes FICTICIOS (`SIGRID_API_BASE_URL=http://127.0.0.1:9`, `PG_HOST=127.0.0.1`, `PG_PORT=9`, resto inventado; nada en disco, ningún `.env`) | **112 passed en 75,39 s**: el rojo es solo de entorno |
| `bash harness/init.sh` en el worktree (sobre `1c1064a`) | KO de ENTORNO: «Falta .env» y pytest con `-x` parado en el 1.º de entorno (`test_f006_t26_cli_dry_run_no_toca_la_base`; 255 passed antes). Por eso su PUERTA COBERTURA daba 50 % (14/28): medía 255 tests. Resto OK: compileall, `features.json`, `BACKLOG.md` al día, rigor, **PUERTA TAMAÑO OK (requirements 145/150, design 184/250)**, rama |
| Cobertura de las líneas cambiadas | **100,0 % (28/28)**, umbral 80 %: `python -m harness.cobertura --base main` sobre el `coverage.json` de la suite completa (diff desde `75389c5`, merge-base con `main`) |
| Mutantes generados y supervivientes | MUTACION_PENDIENTE |
| Tiempo de la suite | 1.374,34 s con cobertura (fila de arriba) |
