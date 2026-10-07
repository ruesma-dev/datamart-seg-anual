<!-- specs/F-085-quien-aprobo-que-y-cuando/tasks.md -->
# F-085 · Tareas

Rama `feature/F-085-quien-aprobo-que-y-cuando`. Un commit por tarea (`F-085 Tn: ...`), `git add` de ficheros concretos. Rigor **estándar**: fase RED de cada test nuevo, traza en `progress/impl_F-085.md`. Ningún agente escribe en ninguna base: los tests leen el TEXTO del SQL y del YAML. D1-D8 DECIDIDAS por el humano el 2026-10-07 (D4 cambiada: login + nombre en `compras`, DNI y empleado en `personal`, `usu` sin credenciales).

## Dominio e ingesta

- [x] T1: `etl_sigrid/domain/documento_procesos.py` (`FAMILIAS`, `COLUMNAS_CREDENCIALES_USU`, `EMPRESA_PREFERENTE`, `Paso`, `PasoEncadenado`, `hora_sigrid`, `normalizar_login`, `encadenar`, `empleado_de_usuario`) con `tests/test_f085_dominio.py` y los casos de design §7 bis (R3, R10-R15, R18)  |  Verificación: `python -m pytest tests/test_f085_dominio.py -q` (RED antes, traza en el informe)
- [x] T2: `config/tables_sigrid.yaml`: `rac` con `where: null` y comentario nuevo (R1); bloque «LO QUE SIGRID NO GUARDA» corregido; `test_f095_r9_*` ajustado; primeros tests de `test_f085_sql.py` (entrada `rac`, R5)  |  Verificación: `python -m pytest tests/test_f085_sql.py tests/test_f095_retenciones_contables.py -q`
- [x] T3: `config/tables_sigrid.yaml`: entrada `usu` con las diez exclusiones y su motivo (R2, R3); test de exclusiones exactas contra `COLUMNAS_CREDENCIALES_USU`  |  Verificación: `python -m pytest tests/test_f085_sql.py -q -k usu`
- [x] T4: Censo 71 → 72 en los tests que lo fijan: `TOTAL_TABLAS` de `tests/test_f066_ingesta_raw.py` y `tests/test_f074_ingesta_censo.py`, `tests/test_f097_ingesta_descompuestos.py:189`, «71 tablas» de `test_f095_r31_*`, comentarios de `tests/test_f107_contrapartidas_cuentas.py`; y en los textos que esos tests leen: `docs/ARCHITECTURE.md` (título y l. 361), `config/diccionario/00_global.yaml` (l. 940 y comentario), `config/diccionario/raw.yaml` (l. 5) (R4, R27, R28)  |  Verificación: `python -m pytest tests/test_f066_ingesta_raw.py tests/test_f074_ingesta_censo.py tests/test_f097_ingesta_descompuestos.py tests/test_f095_retenciones_contables.py tests/test_f107_contrapartidas_cuentas.py tests/test_f085_sql.py -q`

## SQL y pasos

- [x] T5: `sql/compras/12_documento_procesos.sql` según design §5 (R6-R14, R16)  |  Verificación: `python -m pytest tests/test_f085_sql.py -q`
- [x] T6: `build_compras_step.py`: `SUB_PASOS` + `12` detrás de `11`, cuenta `compras.documento_procesos`; docstring; `tests/test_f047_steps.py` («`12` es el último»)  |  Verificación: `python -m pytest tests/test_f047_steps.py tests/test_f085_sql.py -q`
- [ ] T7: `sql/personal/00_setup.sql` (tabla) y `sql/personal/06_usuarios_sigrid.sql` según design §6 (R17-R21); `build_personal_step.py` + `06` al final; `FICHEROS_PERSONAL` de `tests/test_f057_personal.py`  |  Verificación: `python -m pytest tests/test_f057_personal.py tests/test_f085_sql.py -q`

## Diccionario y documentos

- [ ] T8: ficha `compras.documento_procesos` (R22, R23) y correcciones de `comparativos.fecha_aprobacion` y `comparativo_firmas` (R26); `test_f085_diccionario.py`  |  Verificación: `python -m pytest tests/test_f085_diccionario.py tests/test_f006_fichas.py tests/test_f006_formato.py tests/test_f006_cobertura.py tests/test_f038*.py -q`
- [ ] T9: ficha `personal.usuarios_sigrid` (R24) en `config/diccionario/personal.yaml`  |  Verificación: `python -m pytest tests/test_f085_diccionario.py tests/test_f057_personal.py tests/test_f006_fichas.py tests/test_f006_cobertura.py -q`
- [ ] T10: fichas `raw.rac` y `raw.usu` (R25) y `00_global.yaml` `version` +1 con su comentario (R27)  |  Verificación: `python -m pytest tests/test_f085_diccionario.py tests/test_f095_retenciones_contables.py tests/test_f006_fichas.py -q`
- [ ] T11: `docs/ARCHITECTURE.md` («Qué se copia»: `rac` sin filtro, `usu` sin credenciales; «Lo que Sigrid NO guarda») y `../azure-apps/datamart_seg_anual.md` (72 tablas, `rac`, `usu`, los dos objetos; commit local aparte en `azure-apps`) (R28)  |  Verificación: `python -m pytest tests/test_f085_diccionario.py tests/test_f095_retenciones_contables.py -q`

## Contra la base (manual) y cierre

- [ ] T12: MANUAL (humano). Postgres LOCAL/dev del `.env`: `python main.py ingest --table rac --full`, `python main.py ingest --table usu --full`, `python main.py build-compras`, y `SELECT orden, proceso, estado_origen_codigo, estado_destino_codigo, usuario, nombre_usuario, momento, asiento_id, es_ultimo FROM compras.documento_procesos WHERE familia = 'FACTURA' AND codigo_documento = 'FR26/10025' ORDER BY orden;` → R29. Anotar tiempos de ingesta y de los sub-pasos (R32)  |  Verificación: MANUAL (humano)
- [ ] T13: MANUAL (humano). Cobertura (R30): `SELECT familia, COUNT(DISTINCT documento_id), AVG((encaja_con_anterior)::int), AVG((nombre_usuario IS NOT NULL)::int) FROM compras.documento_procesos GROUP BY familia;`, el último paso contra `raw.con.est` (`WHERE es_ultimo`, esperado ≥ 99,9 %) y, tras `python main.py build-personal`, `SELECT COUNT(*), COUNT(empleado_id), COUNT(dni) FROM personal.usuarios_sigrid;` → 233 / 210 / ~204  |  Verificación: MANUAL (humano)
- [ ] T14: MANUAL (humano). R31: `SELECT COUNT(*), COUNT(obra_id), SUM(importe) FROM retenciones.apuntes_contables;` antes y después (`python main.py build-retenciones`), y `python main.py check-raw-recuentos` en verde para `rac` y `usu`  |  Verificación: MANUAL (humano)
- [ ] T15: `progress/impl_F-085.md` (≤ 220 líneas) con trazas RED, resultados de T12-T14 y el aviso de ventana  |  Verificación: `python -m harness.tamano --feature F-085`
- [ ] T16: Ejecutar `bash harness/init.sh` en verde  |  Verificación: `bash harness/init.sh`
