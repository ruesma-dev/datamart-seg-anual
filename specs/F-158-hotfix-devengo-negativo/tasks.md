<!-- specs/F-158-hotfix-devengo-negativo/tasks.md -->
# F-158 · Tareas

- [ ] T1: Tests nuevos `tests/test_f158_reparto_personal.py` (R2-R10) y `test_f150_r46_el_reparto_lleva_la_parte_de_personal` actualizado; RED sobre `fbf43dd` anotado en `progress/impl_F-158.md`  |  Verificación: `.venv/Scripts/python.exe -m pytest tests/test_f158_reparto_personal.py tests/test_f150_personal.py` falla en R6/R7/R10
- [ ] T2: `repartir_personal` en `etl_sigrid/domain/proyeccion_caja.py` (design §4)  |  Verificación: `pytest tests/test_f158_reparto_personal.py -k "r2 or r3 or r4 or r5 or r6"` en verde
- [ ] T3: `07_devengo_pendiente.sql` paso 5: `repartido_personal` por acumulado y comentarios (design §3)  |  Verificación: `pytest tests/test_f158_reparto_personal.py tests/test_f150_personal.py tests/test_f150_contrato_compra.py tests/test_f140_sql.py` en verde
- [ ] T4: Fichas de `config/diccionario/tesoreria.yaml` (R10) y `version: 72` en `00_global.yaml`  |  Verificación: `pytest tests/test_f158_reparto_personal.py -k r10` y los tests del diccionario en verde
- [ ] T5: Campaña de mutación (alcance `repartir_personal`) y manual del SQL M1-M3 (design §5)  |  Verificación: informe en `progress/impl_F-158.md` con muertos y supervivientes analizados
- [ ] T6: Despliegue en Azure con los pasos de `design.md` §6 (imagen, job, `build-tesoreria`, `apply-grants`, comprobaciones, diccionario v72)  |  Verificación: MANUAL (humano): `count(*)` de negativos = 0 y `build_tesoreria` SUCCESS en `_meta.etl_runs`
- [ ] T7: Ejecutar `bash harness/init.sh` en verde  |  Verificación: `bash harness/init.sh` exit 0
