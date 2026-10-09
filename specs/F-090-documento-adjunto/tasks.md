<!-- specs/F-090-documento-adjunto/tasks.md -->
# F-090 · Tareas

Requisito previo: el humano ha aprobado la spec y decidido D1-D7
(`requirements.md`). Si una decisión cambia el diseño, el spec-author ajusta la
spec antes de T1.

- [x] T1: `etl_sigrid/domain/documento_adjuntos.py` (familias, clases por extensión, `extension`, `clase_fichero`, `filtro_rcg`, `filtro_gra`, columnas excluidas) + `tests/test_f090_dominio.py` en RED primero  |  Verificación: `python -m pytest tests/test_f090_dominio.py -q` (R7-R10)
- [x] T2: `config/tables_sigrid.yaml` + `rcg` y + `gra` (filtro del dominio, exclusiones con su motivo, comentario con las cifras) + tests de ingesta en `tests/test_f090_ingesta_sql.py`  |  Verificación: `python -m pytest tests/test_f090_ingesta_sql.py -q -k "r1 or r2 or r3 or r4 or r5 or r6"` (R1-R6)
- [x] T3: actualizar el censo 72 -> 74 en `tests/test_f085_sql.py`, `tests/test_f085_diccionario.py` y `tests/test_f095_retenciones_contables.py` (solo los asserts del censo)  |  Verificación: `python -m pytest tests/test_f085_sql.py tests/test_f085_diccionario.py tests/test_f095_retenciones_contables.py -q` (en rojo hasta T6-T7 por los textos de documentación; se anota en el informe)
- [x] T4: `sql/compras/14_documento_adjuntos.sql` (guarda R15, tabla, PK, índices) + tests de texto SQL (literales del dominio, JOIN, `comprv`, no nombra `ruesma_rep` ni `ima`)  |  Verificación: `python -m pytest tests/test_f090_ingesta_sql.py -q -k "r11 or r12 or r13 or r14 or r15 or r17 or r18"`
- [ ] T5: sub-paso `documento_adjuntos` en `SUB_PASOS` de `build_compras_step.py` (detrás de `estado_documentos`) y su línea del docstring + test del orden y del destino  |  Verificación: `python -m pytest tests/test_f090_ingesta_sql.py -q -k r16`
- [ ] T6: diccionario: ficha `compras.documento_adjuntos` (R19-R23) y relaciones en las fichas de los documentos; fichas `raw.gra` y `raw.rcg`; «Son 74 tablas»; `00_global.yaml` a `version: 47` con su nota + `tests/test_f090_diccionario.py`  |  Verificación: `python -m pytest tests/test_f090_diccionario.py -q` (R19-R24)
- [ ] T7: `docs/ARCHITECTURE.md` (74 tablas, `gra`/`rcg`, binario en `ruesma_rep`) y `azure-apps/datamart_seg_anual.md` (commit en ese repo) + tests R25  |  Verificación: `python -m pytest tests/test_f090_diccionario.py tests/test_f085_diccionario.py tests/test_f095_retenciones_contables.py -q`
- [ ] T8: `progress/impl_F-090.md` con trazas RED/GREEN y la lista de verificaciones manuales pendientes (T9-T11)  |  Verificación: `python -m harness.tamano --feature F-090`
- [ ] T9: MANUAL (humano): ingesta y build en Azure tras desplegar la imagen: `python main.py ingest --table rcg --full` y `python main.py ingest --table gra --full` (o la nocturna), `python main.py build-compras`, `python main.py check-raw-recuentos`; `SELECT count(*), count(DISTINCT documento_id) FROM compras.documento_adjuntos` ~199.000  |  Verificación: MANUAL (humano) (R26)
- [ ] T10: MANUAL (líder, solo lectura): `publicar-diccionario` (lo autoriza el humano), reiniciar el MCP y hacerle las tres preguntas de R27; una sola llamada a `documents/read` con un `cod_repositorio` publicado, sin guardar el fichero (R29)  |  Verificación: MANUAL (humano), resultado en `progress/impl_F-090.md`
- [ ] T11: MANUAL (líder): medir en la primera nocturna con F-090 los segundos de `ingest_raw.rcg`, `ingest_raw.gra` y del sub-paso (`python main.py timings`) y anotarlos contra la ventana  |  Verificación: MANUAL (humano) (R28)
- [ ] T12: Ejecutar `bash harness/init.sh` en verde  |  Verificación: `bash harness/init.sh`
