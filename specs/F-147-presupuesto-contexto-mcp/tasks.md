# F-147 · Tareas

- [ ] T1: Pactar con `mcp-bbdd` el contrato de `design.md` (columnas al final, semántica, `fuera_mcp` sin fila, 2 primeras preguntas, códigos retirados) y citarlo en `progress/current.md`  |  Verificación: MANUAL (humano) — respuesta de `mcp-bbdd` anotada
- [ ] T2: Medida ANTES con la fórmula de R17 sobre el árbol de `main` y medida real de `contexto_bbdd` en Azure (solo lectura) en `progress/impl_F-147.md`  |  Verificación: cifras en el informe
- [ ] T3: Tests RED de R1–R6 en `tests/test_f147_resumen_reglas.py`  |  Verificación: `pytest tests/test_f147_resumen_reglas.py` falla por lo que falta
- [ ] T4: `Regla.resumen`/`entrega`, `ENTREGAS`, límites, cargador, validación, `filas_reglas`, `fila_publicacion`, `SQL_INSERT_REGLA` y DDL con `DO`  |  Verificación: `pytest tests/test_f147_resumen_reglas.py` en verde
- [ ] T5: Tests RED de R17–R20 en `tests/test_f147_presupuesto_contexto.py` (fixtures; el del árbol con un `PRESUPUESTO_MAX` provisional = medida de T2)  |  Verificación: `pytest tests/test_f147_presupuesto_contexto.py` falla
- [ ] T6: `presupuesto_contexto` y `MAX_PREGUNTAS_ENRUTADO` en dominio  |  Verificación: `pytest tests/test_f147_presupuesto_contexto.py` en verde
- [ ] T7: Tests RED de R7–R16 en `tests/test_f147_contenido.py`  |  Verificación: `pytest tests/test_f147_contenido.py` falla
- [ ] T8: Reglas de `00_global.yaml` según `revision_reglas.md` (resúmenes, recortes, `R-PERFILES`, `R-COMPRAS-LINEA`, fuera `R-COSTE-CONSULTA`, `R-SIGRID-CON` `fuera_mcp`, `R-OBRA-ACTIVA`, `R-COMPRAS-SIN-IVA`, `R-ALBARAN-ABSURDO` mínima) y `CODIGOS_REGLAS_OBLIGATORIAS`  |  Verificación: `pytest tests/test_f147_contenido.py tests/test_f006_reglas.py`
- [ ] T9: Detalle que sale de las reglas a sus fichas y códigos retirados sustituidos en YAML, SQL (comentario), tests y docs  |  Verificación: `pytest tests/test_f147_contenido.py tests/test_f006_fichas.py tests/test_f141_perfil_restringido.py tests/test_f146_restringido_sin_contabilidad.py`
- [ ] T10: Convenciones (`importes_iva`, `identidad_sigrid`, `fechas`), cabecera de `compras.yaml` y `para_que_sirve` ≤ 350  |  Verificación: `pytest tests/test_f147_contenido.py tests/test_f006_copias.py tests/test_f006_contexto.py`
- [ ] T11: Las 2 primeras `ejemplos_preguntas` de cada ficha recomendada con más de 2 (reordenar, no borrar)  |  Verificación: `pytest tests/test_f147_contenido.py`
- [ ] T12: `version: 59` con su comentario y `PRESUPUESTO_MAX` bajado a la medida final, con la historia al lado  |  Verificación: `pytest tests/test_f147_presupuesto_contexto.py tests/test_f006_publicacion.py`
- [ ] T13: `docs/ARCHITECTURE.md`, `docs/CONVENTIONS.md` y `azure-apps/datamart_seg_anual.md` (commit local en `azure-apps`)  |  Verificación: `pytest tests/test_f006_docs.py` y lectura del reviewer
- [ ] T14: Medida DESPUÉS en `progress/impl_F-147.md` y despliegue MANUAL en `progress/current.md` (imagen, `python main.py publicar-diccionario`, `python main.py check-diccionario`, medir `contexto_bbdd` en Azure)  |  Verificación: MANUAL (humano)
- [ ] T15: Ejecutar `bash harness/init.sh` en verde  |  Verificación: `bash harness/init.sh`
