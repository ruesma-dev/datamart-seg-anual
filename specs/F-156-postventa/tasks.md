# F-156 · Tareas

Precondición: F-153 cerrada (una sola `in_progress`). Decisiones del humano del 2026-11-03 en
`requirements.md`.

- [x] T1: Fase RED: `tests/test_f156_dominio.py` y `tests/test_f156_ingesta_sql.py` (design § 13), en rojo y con la traza guardada  |  Verificación: `pytest tests/test_f156_dominio.py tests/test_f156_ingesta_sql.py` falla por lo esperado
- [x] T2: Dominio `etl_sigrid/domain/postventa.py`: constantes, `fin_garantia`, `dentro_garantia`, `familia_adjunto`, `origen_fecha`, `enmascarar`, `obra_de_partida`, `liga_coste` (design § 5)  |  Verificación: `pytest tests/test_f156_dominio.py`
- [x] T3: `config/tables_sigrid.yaml`: las 13 tablas con comentario (incluida `per` con sus 5 columnas) y el `where` ampliado de `rcg`/`gra` (R1-R4); censo 80 -> 93 en los tests que lo fijan (R5)  |  Verificación: `pytest tests/test_f156_ingesta_sql.py -k "r1 or r2 or r3 or r4 or r5" tests/test_f090_ingesta_sql.py tests/test_f138_ingesta_sql.py tests/test_f074_ingesta_censo.py`
- [x] T4: `sql/postventa/00_setup.sql` a `03_tareas.sql` y `build_postventa_step.py` con `SUB_PASOS` (R6-R13)  |  Verificación: `pytest tests/test_f156_ingesta_sql.py -k "r6 or r7 or r8 or r9 or r10 or r11 or r12 or r13"`
- [x] T5: `04_procesos.sql` y `05_estado.sql`: histórico con fechas, estados y login/nombre, y vista de estado (R14-R16, R18)  |  Verificación: `pytest tests/test_f156_ingesta_sql.py -k "r14 or r15 or r16 or r18" tests/test_f156_dominio.py`
- [x] T6: `06_adjuntos.sql`: índice de gráficos con su guarda y las expresiones de compras (R19-R21)  |  Verificación: `pytest tests/test_f156_ingesta_sql.py -k "r19 or r20 or r21" tests/test_f090_ingesta_sql.py`
- [x] T7: `07_restringida.sql` (R23-R24)  |  Verificación: `pytest tests/test_f156_ingesta_sql.py -k "r23 or r24"`
- [x] T8: `08_coste_obra.sql`: `partida_obra_origen` y `v_coste_obra` (R25-R26)  |  Verificación: `pytest tests/test_f156_ingesta_sql.py -k "r25 or r26" tests/test_f156_dominio.py`
- [x] T9: Fase RED de `tests/test_f156_grants.py`; listas en `settings.py` y `.env.example`, `ESQUEMAS_DEL_DATAMART` (R28-R29); tests de listas de esquemas al día  |  Verificación: `pytest tests/test_f156_grants.py -k "r28 or r29" tests/test_f135_grants.py tests/test_f138_grants.py tests/test_f057_personal.py`
- [x] T10: Perfil postventa: `perfil_postventa_en_conflicto` en `grants.py` y su bloque en `apply_grants_step.py` (R29-R30)  |  Verificación: `pytest tests/test_f156_grants.py tests/test_f141_perfil_restringido.py tests/test_f136_*.py`
- [x] T11: `infra/sql/02_roles.sql`: grupo, login con `POSTVENTA_PWD`, `postventa_restringida` y punto 5 sexies; runbook (R31)  |  Verificación: `pytest tests/test_f156_grants.py -k r31`
- [ ] T12: `main.py`: `BuildPostventaStep` en `run-all`, `PASOS_CON_PERMISOS` y `build-postventa` (R32); tests de pasos al día  |  Verificación: `pytest tests/test_f156_pipeline.py tests/test_f047_nocturna.py tests/test_f148_permisos_por_paso.py tests/test_f006_frescura.py tests/test_f024_cli.py`
- [ ] T13: Fase RED de `tests/test_f156_diccionario.py`; fichas `postventa.yaml`, `postventa_restringida.yaml`, `raw.yaml` y `00_global.yaml` (versión +1, esquemas, `R-FRESCURA`, `R-PERFILES`, `R-POSTVENTA-RESTRINGIDA`) (R22-R23, R33-R34)  |  Verificación: `pytest tests/test_f156_diccionario.py tests/test_f006_fichas.py tests/test_f006_reglas.py tests/test_f147_presupuesto_contexto.py tests/test_f149_mcp_sin_reglas_no_publicadas.py`
- [ ] T14: `docs/ARCHITECTURE.md`, `docs/runbook_postgres_azure.md`, mapa de `CLAUDE.md` y `../azure-apps/datamart_seg_anual.md` con enlace al pliego (commit local en `azure-apps`, sin push) (R35)  |  Verificación: `pytest tests/test_f156_diccionario.py -k architecture`; `git -C ../azure-apps log -1`
- [ ] T15: Informe `progress/impl_F-156.md` con trazas RED y la campaña de mutación del rigor `estandar`  |  Verificación: `python -m harness.tamano --feature F-156`
- [ ] T16: Despliegue tras APROBADO y merge: imagen, job, contraseña y `02_roles.sql`, ingesta, `build-postventa`, `apply-grants`, cifras (R17, R27), `publicar-diccionario`, checks, pliego a `mcp-bbdd` y reinicio del MCP  |  Verificación: MANUAL (humano), comandos exactos y vuelta atrás en design § 12
- [ ] T17: Ejecutar `bash harness/init.sh` en verde  |  Verificación: `bash harness/init.sh`
