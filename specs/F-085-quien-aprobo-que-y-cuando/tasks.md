<!-- specs/F-085-quien-aprobo-que-y-cuando/tasks.md -->
# F-085 · Tareas

Rama `feature/F-085-quien-aprobo-que-y-cuando`. Un commit por tarea (`F-085 Tn: ...`), `git add` de ficheros concretos. Rigor **estándar**: fase RED de cada test nuevo, traza en `progress/impl_F-085.md`. Ningún agente escribe en ninguna base: los tests leen el TEXTO del SQL y del YAML. Asume D1-D8 con su recomendación (si el humano cambia alguna, se reescribe la spec antes de empezar).

## Dominio, ingesta y SQL

- [ ] T1: `etl_sigrid/domain/documento_procesos.py` (`FAMILIAS`, `Paso`, `PasoEncadenado`, `hora_sigrid`, `encadenar`) con `tests/test_f085_dominio.py` y los casos de design §7, FR26/10025 incluida (R9-R13)  |  Verificación: `python -m pytest tests/test_f085_dominio.py -q` (RED antes, traza en el informe)
- [ ] T2: `config/tables_sigrid.yaml`: `rac` con `where: null` y comentario nuevo con las cifras (R1, R2); bloque «LO QUE SIGRID NO GUARDA» corregido (R20); `test_f095_r9_*` ajustado; `test_f085_sql.py` con los tests de la ingesta y del censo en 71  |  Verificación: `python -m pytest tests/test_f085_sql.py tests/test_f095_retenciones_contables.py tests/test_f066_ingesta_raw.py tests/test_f074_ingesta_censo.py -q`
- [ ] T3: `sql/compras/12_documento_procesos.sql` según design §5 (R4-R12, R14) y el test de que `03_apuntes_contables.sql` sigue filtrando (R3)  |  Verificación: `python -m pytest tests/test_f085_sql.py -q`
- [ ] T4: `build_compras_step.py`: `SUB_PASOS` + `12` detrás de `11`, cuenta `compras.documento_procesos`; docstring; `tests/test_f047_steps.py` (lista y «`12` es el último»)  |  Verificación: `python -m pytest tests/test_f047_steps.py tests/test_f085_sql.py -q`

## Diccionario y documentos

- [ ] T5: ficha `compras.documento_procesos` (R15, R16) y correcciones de `comparativos.fecha_aprobacion` y `comparativo_firmas` (R18) en `config/diccionario/compras.yaml`; `test_f085_diccionario.py`  |  Verificación: `python -m pytest tests/test_f085_diccionario.py tests/test_f006_fichas.py tests/test_f006_formato.py tests/test_f006_cobertura.py tests/test_f038*.py -q`
- [ ] T6: ficha `raw.rac` en `config/diccionario/raw.yaml` (R17) y `00_global.yaml` `version` +1 con su comentario (R19)  |  Verificación: `python -m pytest tests/test_f085_diccionario.py tests/test_f095_retenciones_contables.py tests/test_f006_fichas.py -q`
- [ ] T7: `docs/ARCHITECTURE.md` («Qué se copia de Sigrid» y «Lo que Sigrid NO guarda», R20) y `../azure-apps/datamart_seg_anual.md` (R21; commit local aparte en `azure-apps`)  |  Verificación: `python -m pytest tests/test_f085_diccionario.py tests/test_f095_retenciones_contables.py -q`

## Contra la base (manual) y cierre

- [ ] T8: MANUAL (humano). Contra el Postgres LOCAL/dev del `.env`: `python main.py ingest --table rac --full`, `python main.py build-compras`, y en `psql`: `SELECT orden, proceso, estado_origen_codigo, estado_destino_codigo, usuario, momento, asiento_id, es_ultimo FROM compras.documento_procesos WHERE familia = 'FACTURA' AND codigo_documento = 'FR26/10025' ORDER BY orden;` → las 4 filas de R22. Anotar en `progress/impl_F-085.md` el tiempo de la ingesta de `rac` y del sub-paso `12` (R25)  |  Verificación: MANUAL (humano)
- [ ] T9: MANUAL (humano). Cobertura y coherencia (R23): `SELECT familia, COUNT(DISTINCT documento_id), COUNT(*) FILTER (WHERE es_ultimo), AVG((encaja_con_anterior)::int) FROM compras.documento_procesos GROUP BY familia;` y el cruce del último paso con el estado actual: `SELECT p.familia, AVG((p.estado_destino_id = c.est)::int) FROM compras.documento_procesos p JOIN raw.con c ON c.ide = p.documento_id WHERE p.es_ultimo GROUP BY p.familia;` (esperado ≥ 99,9 %)  |  Verificación: MANUAL (humano)
- [ ] T10: MANUAL (humano). `retenciones.apuntes_contables` igual antes y después (R24): `SELECT COUNT(*), COUNT(obra_id), SUM(importe) FROM retenciones.apuntes_contables;` antes del cambio y tras `python main.py build-retenciones` con `raw.rac` sin filtro; y `python main.py check-raw-recuentos` en verde para `rac`  |  Verificación: MANUAL (humano)
- [ ] T11: `progress/impl_F-085.md` (≤ 220 líneas) con trazas RED, resultado de T8-T10 y el aviso de ventana para el humano  |  Verificación: `python -m harness.tamano --feature F-085`
- [ ] T12: Ejecutar `bash harness/init.sh` en verde  |  Verificación: `bash harness/init.sh`
