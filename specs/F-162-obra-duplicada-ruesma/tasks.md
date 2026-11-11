<!-- specs/F-162-obra-duplicada-ruesma/tasks.md -->
# F-162 · Tareas

- [ ] T1: Tests `tests/test_f162_desempate_obras.py` (R2-R16) y `tests/test_f162_sandbox.py` (R18); RED sobre `17b41ec` anotado en `progress/impl_F-162.md`  |  Verificación: `.venv/Scripts/python.exe -m pytest tests/test_f162_desempate_obras.py` falla en R2, R5, R7-R9, R11-R13 y R16
- [ ] T2: `etl_sigrid/domain/ficha_obra.py` con `FichaObra`, `clave_desempate` y `elegir_ficha` (design §3)  |  Verificación: `pytest tests/test_f162_desempate_obras.py -k "r2_la_0721 or r3 or r4"` en verde
- [ ] T3: `stg/01_ddl.sql`: `empresa_id INTEGER NULL` detrás de `_built_at` y su migración en el bloque `DO` (R8, D1)  |  Verificación: `pytest tests/test_f162_desempate_obras.py -k r8` en verde
- [ ] T4: `stg/03_obras.sql`: CTE `lineas_presupuesto`, marca por `EXISTS`, `ORDER BY` de cinco criterios, `empresa_id` en `INSERT`/`SELECT` y cabecera nueva (R1-R11)  |  Verificación: `pytest tests/test_f162_desempate_obras.py tests/test_f073_sql.py tests/test_f025_build.py` en verde
- [ ] T5: Retirar `test_f102_r7_stg_obras_es_identico_al_de_main` y `HASH_STG_OBRAS_MAIN` con su motivo (R15)  |  Verificación: `pytest tests/test_f102_obra_principal.py` en verde
- [ ] T6: Cobertura: fuera `0252` y `0517` de `config/cobertura_excepciones.yaml` y `EXCEPCIONES_MAX = 21` (R16; la `0720` solo si el humano decide D3)  |  Verificación: `pytest tests/test_f052_cobertura.py tests/test_f162_desempate_obras.py -k "r16 or cobertura"` en verde
- [ ] T7: Ficha `obras` de `config/diccionario/stg.yaml` (regla, `empresa_id`, lista de §5.4) y `version` siguiente en `00_global.yaml` con su nota (R12, R14)  |  Verificación: `pytest tests/test_f162_desempate_obras.py -k "r12" tests/test_f006_fichas.py tests/test_f079_stg_consultable.py` en verde
- [ ] T8: Textos con la lista vieja: `maestro.yaml`, comentarios de `sql/maestro/00_setup.sql` y `01_obras.sql`, `docs/ARCHITECTURE.md` (R13)  |  Verificación: `pytest tests/test_f162_desempate_obras.py -k r13` en verde
- [ ] T9: `azure-apps/datamart_seg_anual.md`: la regla nueva y `empresa_id`, commit local en `azure-apps` (R13)  |  Verificación: `git -C C:/Users/pgris/PycharmProjects/azure-apps log -1` con el commit de F-162
- [ ] T10: Sandbox con DSN (lo ejecuta el líder en la copia con `.env`)  |  Verificación: MANUAL (líder): `F162_SANDBOX_DSN=<dsn local> .venv/Scripts/python.exe -m pytest tests/test_f162_sandbox.py` en verde, sin `skip`
- [ ] T11: Medición ANTES en Azure, mismo `raw` (design §6, paso 0)  |  Verificación: MANUAL (humano o líder, solo lectura): cuatro CSV `antes_*` y el recuento de §5.1-5.2 en `progress/impl_F-162.md`
- [ ] T12: Despliegue (design §6, pasos 1-9) con su vuelta atrás  |  Verificación: MANUAL (humano): `comparar-huellas ... --obras-esperadas 0252,0517,0721` como dice el paso 4, paso 5 con 650280/12, 1088657/25, 2759553/1 y 585 filas, paso 6 con 0 filas de devengo nuevo
- [ ] T13: Ejecutar `bash harness/init.sh` en verde  |  Verificación: `bash harness/init.sh` exit 0
