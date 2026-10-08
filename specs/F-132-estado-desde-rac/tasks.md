<!-- specs/F-132-estado-desde-rac/tasks.md -->
# F-132 · Tareas

Rama `feature/F-132-estado-desde-rac`. Un commit por tarea (`F-132 Tn: ...`). Fase A = T1-T15; Fase B = T16-T21, SOLO tras la decisión D7 del humano (hasta entonces no se empieza).

## Fase A

- [x] T1: `domain/estado_documentos.py` (constantes, `PasoEstado`, `FechaEstado`, `fecha_estado`, `dias_en_estado`) con su RED primero  |  Verificación: `pytest tests/test_f132_dominio.py -k "r4 or r5 or r6 or r7 or r8 or r9 or r11"` (casos PASO, paso sin hora, ALTA, ALTA sin fecha, FUERA_DE_PROCESO con y sin pasos)
- [x] T2: `clasificar_cambio` y `clasificar_no_visto` en el mismo módulo, con un caso real de cada clase medida el 08-10 como fixture (PASO, DESHECHO de factura y de contrato, VUELTA_AL_INICIAL, IDA_Y_VUELTA, ALTA) y una DISCREPANCIA construida  |  Verificación: `pytest tests/test_f132_dominio.py -k "r13 or r14"`
- [x] T3: `sql/compras/13_estado_documentos.sql` (design §3) y quitar la vista de `11_historial_estados.sql` (cabecera: la foto es respaldo en contraste)  |  Verificación: `pytest tests/test_f132_sql.py` (R1-R3, R7, R10, R11: columnas en orden, no nombra la foto, literales del dominio, `11` ya no crea la vista y su `DO` no cambia)
- [x] T4: sub-paso `estado_documentos` al final de `SUB_PASOS` en `build_compras_step.py` y las listas de `test_f047_steps`, `test_f073_pipeline`, `test_f080_pipeline`, `test_f085_sql`  |  Verificación: `pytest tests/test_f132_sql.py tests/test_f047_steps.py tests/test_f073_pipeline.py tests/test_f080_pipeline.py tests/test_f085_sql.py`
- [x] T5: retirar de `test_f067_sql.py` los tests de la vista (r9-r11, ahora de F-132) y añadir `contraste_estados_sql.py` a `QUIEN_PUEDE_NOMBRARLAS`  |  Verificación: `pytest tests/test_f067_sql.py`
- [ ] T6: `infrastructure/postgres/contraste_estados_sql.py` (tres SELECT, design §5)  |  Verificación: `pytest tests/test_f132_contraste.py -k r17` (ningún SQL escribe)
- [ ] T7: comando `python main.py contraste-estados` (sesión `read_only`, tabla por noche/tipo/clase, ≤ 50 ids de DISCREPANCIA, códigos de salida)  |  Verificación: `pytest tests/test_f132_contraste.py` (R12, R15-R17 con cliente falso)
- [ ] T8: fichas de `compras.yaml` (`v_estado_documentos` reescrita, `contratos`, `historial_estados`, `historial_estados_fotos`, `fn_sigrid_tiempo`) y `raw.yaml` (`conest`)  |  Verificación: `pytest tests/test_f132_diccionario.py -k "r18 or r19"` y `pytest tests/test_f067_diccionario.py`
- [ ] T9: `00_global.yaml` v46: entrada de historia, descripción de `compras`, P23 respondible, P24 con `documento_procesos`; ajustar `test_f067_diccionario` (r10, r11, p23, P24) y los recuentos de `test_f006_*`  |  Verificación: `pytest tests/test_f132_diccionario.py -k r20 tests/test_f067_diccionario.py tests/test_f006_reglas.py`
- [ ] T10: premisa falsa fuera del diccionario: `tables_sigrid.yaml` (C3), `docs/ARCHITECTURE.md`, `README_COMPRAS_C1_C2.md`, docstrings de `historial_estados.py` y `build_compras_step.py`  |  Verificación: `pytest tests/test_f132_diccionario.py -k r22`
- [ ] T11: `azure-apps/datamart_seg_anual.md` (sección F-132; F-067 sin «SIN DESPLEGAR» ni «Sigrid no la guarda»), commit propio en ese repositorio, sin push  |  Verificación: `git -C ../azure-apps log -1 --stat`
- [ ] T12: mutación muestreada (rigor estandar: 20 mutantes, semilla fija) sobre `domain/estado_documentos.py` y el comando; supervivientes analizados en `progress/mutacion_F-132.md`  |  Verificación: `python -m harness.mutacion` según `harness/rigor.json`
- [ ] T13: informe `progress/impl_F-132.md` (≤ 220 líneas) con las trazas RED y las MANUAL de abajo  |  Verificación: `python -m harness.tamano --feature F-132`
- [ ] T14: MANUAL (humano), solo lectura tras desplegar y `build-compras`: `SELECT origen_fecha, tipo_documento, count(*) FROM compras.v_estado_documentos GROUP BY 1,2` → PASO ≈ 205.000, ALTA ≈ 1.250, FUERA_DE_PROCESO ≈ 75 (+ los pasos lanzados entre la ingesta de `con` y la de `rac`); `SELECT count(*) FROM compras.v_estado_documentos WHERE tipo_documento='CONTRATO' AND estado_codigo='EPF' AND dias_en_estado > 21` ≈ 785; `python main.py contraste-estados` → resultado en `progress/contraste_F-132.md`; publicar v46, reiniciar el MCP y hacerle la pregunta de R24  |  Verificación: MANUAL (humano)
- [ ] T15: Ejecutar `bash harness/init.sh` en verde  |  Verificación: `bash harness/init.sh`

## Fase B (solo tras D7; el líder ajusta esta lista a la rama elegida)

- [ ] T16: contraste final: `python main.py contraste-estados` al cumplirse el plazo de D6, salida en `progress/contraste_F-132.md` y decisión D7 del humano anotada en `progress/current.md`  |  Verificación: MANUAL (humano)
- [ ] T17: (retirar) mover `EPOCA_DELPHI`/`fecha_delphi` a `domain/fecha_delphi.py`, borrar `11_historial_estados.sql`, su sub-paso y la lógica de la foto del dominio y sus tests  |  Verificación: `pytest tests/test_f067_sql.py tests/test_f047_steps.py tests/test_f132_sql.py`
- [ ] T18: (borrar) comando `retirar-foto-estados [--confirmar]`, `compras_reset_sql.py` sin conservadas, fuera `contraste-estados`, fichas e inventario de F-006 207 → 205  |  Verificación: `pytest tests/test_f067_reset.py tests/test_f132_contraste.py tests/test_f006_*.py`
- [ ] T19: (congelar) fichas «CONGELADA» con fechas y `reset-compras` intacto  |  Verificación: `pytest tests/test_f132_diccionario.py`
- [ ] T20: diccionario v47, `docs/ARCHITECTURE.md` y `azure-apps` según la rama; MANUAL: el humano lanza `retirar-foto-estados --confirmar` (rama borrar) tras desplegar  |  Verificación: `python main.py check-diccionario` (MANUAL, humano)
- [ ] T21: Ejecutar `bash harness/init.sh` en verde  |  Verificación: `bash harness/init.sh`
