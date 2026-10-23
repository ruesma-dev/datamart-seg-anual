# F-148 · Tareas

Orden por dependencia. Cada tarea = un commit `F-148 Tn: ...`. Tests en fase RED
antes del código (rigor de la feature). Ningún test toca red ni BBDD: psycopg,
`sigrid-api` y el reloj se doblan.

- [x] T1: Settings y cadena: `PostgresSettings` (+6 campos, `design.md` §3) y `build_conninfo` con `connect_timeout`, keepalives y `tcp_user_timeout`  |  Verificación: `pytest tests/test_f148_conexion.py -k "r1 or r2"` y `tests/test_f005*` / tests de conninfo existentes en verde
- [x] T2: `reintento_conexion.py`: `es_error_transitorio` (tabla de casos R3/R4 con excepciones construidas), `abrir_con_reintento` con `dormir` inyectado, `psycopg_en_debug`; comprobar en el psycopg instalado (`.venv`) que registra los intentos de conexión en DEBUG y anotarlo en el informe  |  Verificación: `pytest tests/test_f148_conexion.py -k "r3 or r4 or r5 or r6 or r15"`
- [x] T3: `PostgresClient._connect` con reintento, `SET ROLE` sin reintento, `pg_conexion_lenta`, contador `conexiones_abiertas`; `client_factory` pasa `connect_intentos`  |  Verificación: `pytest tests/test_f148_conexion.py` y `tests/test_f005*`, `tests/test_f024*` en verde
- [x] T4: `sesion_carga.py` (`SesionDeCarga`, `MedidaPagina`) y `PostgresClient.sesion_de_carga`; formateo COPY compartido; `SQL_FILAS_EN_RANGO`  |  Verificación: `pytest tests/test_f148_sesion_carga.py -k "r8 or r9 or r10 or r11 or r12 or r13"`
- [x] T5: `IngestRawStep._ingest_one_table` sobre la sesión, `http_s` con iterador explícito, `ingest_pagina`, `conexiones_abiertas` en `metadata`; retirar `copy_rows` y adaptar los `_PgFalso` de `test_f024_steps.py` y `test_f066_reconciliar_columnas.py` sin debilitar aserciones  |  Verificación: `pytest tests/test_f148_sesion_carga.py tests/test_f024_steps.py tests/test_f066_reconciliar_columnas.py tests/test_f074_ingesta_censo.py tests/test_f097_tiemod_obrparpre.py`
- [x] T6: Dominio `reanudacion.py` y `ejecucion_desde_batch`  |  Verificación: `pytest tests/test_f148_reanudacion.py -k "dominio or r21 or r23"`
- [x] T7: `PostgresClient.buscar_lote_reanudable` y `fetch_terminados_en_lote` (constantes SQL; test estático del SQL enviado)  |  Verificación: `pytest tests/test_f148_reanudacion.py -k "sql"`
- [x] T8: `Orchestrator` con `terminados_en_lote` y `tras_paso`; omitidos sin fila y SUCCESS para dependientes; `apply_grants` nunca omitido  |  Verificación: `pytest tests/test_f148_reanudacion.py -k "r21 or r22" tests/test_f148_permisos_por_paso.py -k "r27 or r28"` y tests del orquestador existentes en verde
- [x] T9: `IngestRawStep(tablas_terminadas=…)` (R23) y test de R24 con `evaluar_coherencia_raw` sobre un lote reanudado  |  Verificación: `pytest tests/test_f148_reanudacion.py -k "r23 or r24"`
- [x] T10: `main.py`: `_arrancar_ejecucion(pg, ejecucion_job=…)`, lectura de `CONTAINER_APP_JOB_EXECUTION_NAME` (monkeypatch), `PASOS_CON_PERMISOS`, `_permisos_tras_paso` y composición en `run_all`  |  Verificación: `pytest tests/test_f148_reanudacion.py -k "r18 or r19 or r20" tests/test_f148_permisos_por_paso.py tests/test_f024_cli.py tests/test_f047*`
- [x] T11: Diccionario: fichas `etl_runs.batch_id` y `etl_runs.step` (R29) y `version: 60`  |  Verificación: `pytest tests/test_f148_documentacion.py -k r29` y la puerta del diccionario de `bash harness/init.sh`
- [ ] T12: `docs/ARCHITECTURE.md` (DA-8 y F-047) y `azure-apps/datamart_seg_anual.md` (commit local en `azure-apps`, sin push)  |  Verificación: `pytest tests/test_f148_documentacion.py -k r30` y `git -C ../azure-apps log -1`
- [ ] T13: Secuencia MANUAL de despliegue (`design.md` §7) y criterio de 7 noches (§8) copiados a `progress/current.md` como pendiente del humano  |  Verificación: MANUAL (humano): pasos 1-5 de §7; R31 con las consultas de §8, una línea por noche en `progress/current.md`
- [ ] T14: Mutación según el rigor que fije el humano (D5) sobre `reanudacion.py`, `reintento_conexion.py` y `sesion_carga.py`; supervivientes analizados en `progress/impl_F-148.md`  |  Verificación: `python -m harness.mutacion --feature F-148`
- [ ] T15: Ejecutar `bash harness/init.sh` en verde  |  Verificación: `bash harness/init.sh`
