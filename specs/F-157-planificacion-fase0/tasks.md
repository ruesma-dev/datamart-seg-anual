# F-157 · Tareas

Precondición: F-156 cerrada (una sola `in_progress`) y PARADA 1 resuelta (D1-D8 en
`requirements.md`; si el humano elige otra opción, el spec-author revisa la spec antes de T1).
Rama `feature/F-157-planificacion-fase0` desde `main`.

- [x] T1: Fase RED: `tests/test_f157_dominio.py`, `tests/test_f157_sql.py` y `tests/test_f157_step.py` (design § 10), en rojo con la traza guardada  |  Verificación: `pytest tests/test_f157_dominio.py tests/test_f157_sql.py tests/test_f157_step.py` falla por lo esperado
- [x] T2: Oráculo `etl_sigrid/domain/planif.py` (`explotar_planif`, `conservar`, `PosicionPlanif`) con los casos de R9 (R5, R6, R8-R10)  |  Verificación: `pytest tests/test_f157_dominio.py`
- [x] T3: `stg.fn_explotar_planif` al final de `sql/stg/00_functions.sql` (design § 5.1, R8)  |  Verificación: `pytest tests/test_f157_sql.py -k "funcion or r5 or r8"`
- [x] T4: DDL de `stg.plan_mensual_fase0` y vista `stg.v_plan_mensual_fase0_cobertura` en `sql/stg/01_ddl.sql` (design § 5.3, R1, R11)  |  Verificación: `pytest tests/test_f157_sql.py -k "r1 or r11"`
- [x] T5: `sql/stg/09_plan_mensual_fase0.sql` (design § 5.2, R2-R4, R6, R7, R10)  |  Verificación: `pytest tests/test_f157_sql.py`
- [ ] T6: `build_stg_step.py` (marcador, `componer_sql_fase0`, sello, sub-paso, `_build_plan_mensual_fase0` con la puerta de disco) y `TABLAS_ACOTADAS` en `postgres_client.py` (design § 6, R12-R17); tests que fijan sello, tablas acotadas o sub-pasos, al día  |  Verificación: `pytest tests/test_f157_step.py tests/test_f025_sql.py tests/test_f019_tramos.py` y los que salgan del `grep` de design § 3
- [ ] T7: Sin regresión: `git diff main -- etl_sigrid/infrastructure/postgres/sql/stg/08_plan_mensual.sql etl_sigrid/infrastructure/postgres/sql/mart etl_sigrid/infrastructure/postgres/sql/cierre etl_sigrid/infrastructure/postgres/sql/tesoreria etl_sigrid/infrastructure/postgres/sql/retenciones etl_sigrid/infrastructure/postgres/sql/maestro` vacío y test de R19 (R18, R19)  |  Verificación: el `git diff` sin salida; `pytest tests/test_f157_sql.py -k "r18 or r19" tests/test_f042_sql.py`
- [ ] T8: `tests/test_f157_sandbox.py` (design § 10) corrido en un PostgreSQL local desechable con `F157_SANDBOX_DSN`, traza en el informe; sin DSN, `skip`  |  Verificación: `pytest tests/test_f157_sandbox.py` (local: pasa; sin DSN: skipped)
- [ ] T9: Fase RED de `tests/test_f157_diccionario.py`; fichas de `stg.yaml` (tabla, vista, `plan_mensual.version`), `R-IMPORTE-MES.ambito` y versión de `00_global.yaml` (design § 8, R23, R24)  |  Verificación: `pytest tests/test_f157_diccionario.py tests/test_f006_fichas.py tests/test_f006_reglas.py tests/test_f006_cobertura.py tests/test_f147_presupuesto_contexto.py tests/test_f149_mcp_sin_reglas_no_publicadas.py`
- [ ] T10: `docs/ARCHITECTURE.md`, mapa de `CLAUDE.md` y `../azure-apps/datamart_seg_anual.md` (commit local en `azure-apps`, sin push) (R27)  |  Verificación: `pytest tests/test_f157_diccionario.py -k architecture`; `git -C ../azure-apps log -1`
- [ ] T11: Informe `progress/impl_F-157.md` con trazas RED, traza del sandbox y la campaña de mutación del rigor `estandar`  |  Verificación: `python -m harness.tamano --feature F-157`
- [ ] T12: Despliegue tras APROBADO y merge, en SÁBADO (D5): imagen, job, primera noche completa, huella, checks, R22, cifras R25-R26, `publicar-diccionario`, reinicio del MCP y cuadre con la pantalla de Sigrid por Control de Costes  |  Verificación: MANUAL (humano), comandos exactos y vuelta atrás a `fbf43dd` en design § 12
- [ ] T13: Ejecutar `bash harness/init.sh` en verde  |  Verificación: `bash harness/init.sh`
