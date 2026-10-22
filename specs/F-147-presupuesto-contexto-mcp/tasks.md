# F-147 · Tareas (BORRADOR: se cierran cuando el humano decida D1–D10)

- [ ] T0: Decidir con el humano D1–D10 y anotar la decisión en `requirements.md` (quitar los **[ABIERTA]**)  |  Verificación: MANUAL (humano) — `requirements.md` sin marcas abiertas
- [ ] T1: Pactar con `mcp-bbdd` el contrato (columna `resumen` al final, semántica, D4, D8)  |  Verificación: MANUAL (humano) — acuerdo citado en `progress/current.md`
- [ ] T2: Tests RED de R1–R6 (carga, validación, filas, SQL, DDL guardado, columnas que lee `mcp-bbdd` intactas)  |  Verificación: `pytest tests/test_f147_resumen_reglas.py` falla por lo que falta
- [ ] T3: `Regla.resumen`/`entrega`, cargador, validación, `filas_reglas`, `SQL_INSERT_REGLA` y DDL con `DO`  |  Verificación: `pytest tests/test_f147_resumen_reglas.py` en verde
- [ ] T4: Tests RED de R10–R14 (medida, tope, trinquete, bloque nuevo cuenta)  |  Verificación: `pytest tests/test_f147_presupuesto_contexto.py` falla
- [ ] T5: `presupuesto_contexto` en dominio y `PRESUPUESTO_MAX` con su historia  |  Verificación: `pytest tests/test_f147_presupuesto_contexto.py` en verde
- [ ] T6: Contenido de D1 en `00_global.yaml` y fichas receptoras, `version: 59`, avisos y `CODIGOS_REGLAS_OBLIGATORIAS` (D3)  |  Verificación: `pytest tests/test_f006_reglas.py tests/test_f006_fichas.py tests/test_f147_*.py`
- [ ] T7: Bajar `PRESUPUESTO_MAX` al valor medido tras T6 (D10)  |  Verificación: `pytest tests/test_f147_presupuesto_contexto.py`
- [ ] T8: `docs/ARCHITECTURE.md`, `docs/CONVENTIONS.md` y `azure-apps/datamart_seg_anual.md` (commit local en `azure-apps`)  |  Verificación: `pytest tests/test_f006_docs.py` y revisión del reviewer
- [ ] T9: Medida antes/después en `progress/impl_F-147.md` y despliegue MANUAL en `progress/current.md` (imagen, `publicar-diccionario`, `check-diccionario`, medir `contexto_bbdd` en Azure)  |  Verificación: MANUAL (humano)
- [ ] T10: Ejecutar `bash harness/init.sh` en verde  |  Verificación: `bash harness/init.sh`
