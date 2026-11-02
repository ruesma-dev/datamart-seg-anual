<!-- specs/F-153-estado-albaranes/tasks.md -->
# F-153 · Tareas

- [x] T1: Fase RED: `tests/test_f153_dominio.py` y `tests/test_f153_sql.py` (design §10), en rojo y con la traza guardada  |  Verificación: `pytest tests/test_f153_dominio.py tests/test_f153_sql.py` falla por lo esperado
- [x] T2: Dominio: constantes, `ORIGENES_FECHA` y `fecha_estado` con `fecha_facturacion` (design §3)  |  Verificación: `pytest tests/test_f153_dominio.py tests/test_f132_dominio.py`
- [x] T3: `01_documentos.sql`: tres columnas al final, lateral, índice y nota de cabecera (design §4); `ALBARANES_F153` en `test_f128_sql.py`  |  Verificación: `pytest tests/test_f153_sql.py tests/test_f128_sql.py tests/test_f083_sql.py tests/test_f084_sql.py -k "not r5 and not r6 and not r7"`
- [x] T4: `13_estado_documentos.sql`: cuarto bloque, `origen_fecha`, `en_estado_desde`, `tipo_documento`, cabecera y `COMMENT` (design §5), y `test_f132_sql.py` al día  |  Verificación: `pytest tests/test_f153_sql.py tests/test_f132_sql.py`
- [x] T5: Comentario del sub-paso en `build_compras_step.py`  |  Verificación: `pytest tests/test_f132_sql.py -k r10`
- [x] T6: Fase RED de `tests/test_f153_diccionario.py`; fichas de `compras.yaml` (design §6) y `test_f132_diccionario.py` al día  |  Verificación: `pytest tests/test_f153_diccionario.py tests/test_f132_diccionario.py tests/test_f006_fichas.py`
- [ ] T7: `00_global.yaml` v70 con su nota, y `raw.yaml` si hace falta  |  Verificación: `pytest tests/test_f153_diccionario.py tests/test_f006_reglas.py tests/test_f147_presupuesto_contexto.py`
- [ ] T8: `docs/ARCHITECTURE.md` y `azure-apps/datamart_seg_anual.md` (commit local, sin push)  |  Verificación: `pytest tests/test_f132_diccionario.py -k architecture`; `git -C ../azure-apps log -1`
- [ ] T9: Informe `progress/impl_F-153.md` con trazas RED y campaña de mutación del rigor `estandar`; `bash harness/init.sh` en verde en la rama  |  Verificación: `bash harness/init.sh`; `python -m harness.tamano --feature F-153`
- [ ] T10: Despliegue tras APROBADO y merge: imagen, job, `build-compras`, cifras, `publicar-diccionario` v70, checks, reinicio del MCP y R16-R18  |  Verificación: MANUAL (humano), comandos exactos en design §9, con su vuelta atrás
- [ ] T11: Ejecutar `bash harness/init.sh` en verde  |  Verificación: `bash harness/init.sh`
