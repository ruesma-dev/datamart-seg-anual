# F-156 · Tareas

Precondición: F-153 cerrada (una sola `in_progress`) y D1-D10 decididas en la PARADA 1. Las
tareas [D1=A] solo con D1=A; con D1=B se saltan y sus requisitos se marcan fuera en el informe.

- [ ] T1: Fase RED: `tests/test_f156_dominio.py` y `tests/test_f156_ingesta_sql.py` (design § 13), en rojo y con la traza guardada  |  Verificación: `pytest tests/test_f156_dominio.py tests/test_f156_ingesta_sql.py` falla por lo esperado
- [ ] T2: Dominio `etl_sigrid/domain/postventa.py`: constantes, `fin_garantia`, `dentro_garantia`, `familia_adjunto`, `origen_fecha`, `enmascarar` (design § 5)  |  Verificación: `pytest tests/test_f156_dominio.py`
- [ ] T3: `config/tables_sigrid.yaml`: las 12 tablas con comentario y el `where` ampliado de `rcg`/`gra` (R1, R2, R4); censo 80 -> 92 en los tests que lo fijan  |  Verificación: `pytest tests/test_f156_ingesta_sql.py -k "r1 or r2 or r4 or r5" tests/test_f090_ingesta_sql.py tests/test_f138_ingesta_sql.py tests/test_f074_ingesta_censo.py`
- [ ] T4: `sql/postventa/00_setup.sql` a `03_tareas.sql` y `build_postventa_step.py` con `SUB_PASOS` (R6-R13)  |  Verificación: `pytest tests/test_f156_ingesta_sql.py -k "r6 or r7 or r8 or r9 or r10 or r11 or r12 or r13"`
- [ ] T5: `04_procesos.sql` y `05_estado.sql`: el histórico y la vista de estado (R14-R16, R18)  |  Verificación: `pytest tests/test_f156_ingesta_sql.py -k "r14 or r15 or r16 or r18" tests/test_f156_dominio.py`
- [ ] T6: `06_adjuntos.sql`: el índice de gráficos con su guarda y las expresiones de compras (R19-R21)  |  Verificación: `pytest tests/test_f156_ingesta_sql.py -k "r19 or r20 or r21" tests/test_f090_ingesta_sql.py`
- [ ] T7: [D1=A] `per` en `tables_sigrid.yaml` (R3) y `07_restringida.sql` (R23-R24); censo 92 -> 93  |  Verificación: `pytest tests/test_f156_ingesta_sql.py -k "r3 or r23 or r24"`
- [ ] T8: Permisos: `settings.py`, `.env.example`, `ESQUEMAS_DEL_DATAMART` e `infra/sql/02_roles.sql` (R25-R26); tests de listas de esquemas al día  |  Verificación: `pytest tests/test_f156_grants.py tests/test_f135_grants.py tests/test_f138_grants.py tests/test_f141_perfil_restringido.py tests/test_f057_personal.py`
- [ ] T9: `main.py`: `BuildPostventaStep` en `run-all`, `PASOS_CON_PERMISOS` y comando `build-postventa` (R27-R28); tests de pasos al día  |  Verificación: `pytest tests/test_f156_pipeline.py tests/test_f047_nocturna.py tests/test_f148_permisos_por_paso.py tests/test_f006_frescura.py tests/test_f024_cli.py`
- [ ] T10: Fase RED de `tests/test_f156_diccionario.py`; fichas `postventa.yaml` ([D1=A] `postventa_restringida.yaml`), `raw.yaml` y `00_global.yaml` (versión +1, esquemas, `R-FRESCURA`, [D1=A] `R-POSTVENTA-RESTRINGIDA`) (R22, R29-R31)  |  Verificación: `pytest tests/test_f156_diccionario.py tests/test_f006_fichas.py tests/test_f006_reglas.py tests/test_f147_presupuesto_contexto.py tests/test_f149_mcp_sin_reglas_no_publicadas.py`
- [ ] T11: `docs/ARCHITECTURE.md`, mapa de `CLAUDE.md` y `../azure-apps/datamart_seg_anual.md` con el pliego de design § 11 (commit local en `azure-apps`, sin push) (R32)  |  Verificación: `pytest tests/test_f156_diccionario.py -k architecture`; `git -C ../azure-apps log -1`
- [ ] T12: Informe `progress/impl_F-156.md` con trazas RED y la campaña de mutación del rigor `estandar`  |  Verificación: `python -m harness.tamano --feature F-156`
- [ ] T13: Despliegue tras APROBADO y merge: imagen, job, [D1=A] `02_roles.sql`, ingesta, `build-postventa`, `apply-grants`, cifras (R17), `publicar-diccionario`, checks, pliego a `mcp-bbdd` y reinicio del MCP  |  Verificación: MANUAL (humano), comandos exactos y vuelta atrás en design § 12
- [ ] T14: Ejecutar `bash harness/init.sh` en verde  |  Verificación: `bash harness/init.sh`
