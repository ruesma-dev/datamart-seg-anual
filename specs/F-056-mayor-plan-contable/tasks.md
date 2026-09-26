<!-- specs/F-056-mayor-plan-contable/tasks.md -->
# F-056 · Tareas

Rama `feature/F-056-mayor-plan-contable`. Rigor `critico`: fase RED obligatoria,
cobertura >= 80 % de líneas cambiadas y campaña de mutación ENTERA con **0
supervivientes** (cada uno, test nuevo o justificación aceptada por el humano).
Un commit por tarea (`F-056 Tn: ...`), en español. **No se empieza sin las
decisiones D1-D8 cerradas por el humano** (T0); si alguna cambia la
recomendación, se reescribe la spec antes de tocar código.

- [ ] T0: Comprobar que D1-D8 de `design.md` están decididas y anotadas en `progress/current.md`; si una no sigue la recomendación, parar y devolver la spec al spec-author.  |  Verificación: anotación en `progress/impl_F-056.md`
- [ ] T1: Escribir `tests/test_f056_contabilidad.py` en fase RED con al menos un test por requisito R1-R32 (offline: texto del SQL sin comentarios `--`, YAML, cableado del step y de `main.py`).  |  Verificación: `pytest tests/test_f056_contabilidad.py` falla y la traza queda en `progress/impl_F-056.md`
- [ ] T2: Crear `sql/contabilidad/00_setup.sql` (esquema y `contabilidad.fn_fecha`).  |  Verificación: `test_f056_r1_*`, `test_f056_r2_solo_raw_y_el_puente`
- [ ] T3: Crear `sql/contabilidad/01_plan_cuentas.sql`: las dos ramas (tip 16 y `cua`), PK, único `(empresa_id, codigo_cuenta)`, `clave_cuenta`, empresa y nombre.  |  Verificación: `test_f056_r6_*`, `test_f056_r7_*`, `test_f056_r12_*`
- [ ] T4: En `01_plan_cuentas.sql`, `nivel` por longitud, padre por prefijo dentro de la empresa, `cuenta_padre_declarada_id` y `padre_declarado_difiere`, sin `WITH RECURSIVE`.  |  Verificación: `test_f056_r8_*`, `test_f056_r9_*`, `test_f056_r10_*`
- [ ] T5: En `01_plan_cuentas.sql`, `ruta_codigos`, los cuatro ids de ancestro y `grupo_pgc`.  |  Verificación: `test_f056_r11_*`
- [ ] T6: Crear `sql/contabilidad/02_mayor.sql`: una fila por apunte, PK `apunte_id`, fechas (`fecha`, `fecha_asiento`, `fecha_difiere`, `ejercicio`, `mes`), empresa del asiento, cuenta por `plan_cuentas`, importes `NUMERIC(18,2)`.  |  Verificación: `test_f056_r13_*`, `test_f056_r15_*`, `test_f056_r16_*`, `test_f056_r17_*`
- [ ] T7: En `02_mayor.sql`, `clase_asiento` (orden de R18, `ILIKE`, anti-join de cierres, sin `asi.ori`) e `importe_saldo`.  |  Verificación: `test_f056_r18_*`, `test_f056_r19_*`
- [ ] T8: En `02_mayor.sql`, `saldo_acumulado` por ventana, obra solo por `maestro.centros_coste`, tercero, columnas de R23, índices y la guarda `DO $$` de recuento.  |  Verificación: `test_f056_r14_*`, `test_f056_r20_*`, `test_f056_r21_*`, `test_f056_r22_*`, `test_f056_r23_*`, `test_f056_r24_*`
- [ ] T9: Crear `sql/contabilidad/03_saldos_cuenta_mes.sql` desde `contabilidad.mayor`, con las columnas por clase y `saldo_acumulado` de fin de mes.  |  Verificación: `test_f056_r25_*`, `test_f056_r26_*`
- [ ] T10: Crear `etl_sigrid/application/steps/build_contabilidad_step.py` (`SUB_PASOS` a nivel de módulo, `depends_on = ["ingest_raw"]`, parada con nombre del sub-paso).  |  Verificación: `test_f056_r3_*`, `test_f056_r5_*`
- [ ] T11: PROPAGACIÓN 1/9 — `main.py`: comando `build-contabilidad`, paso en `build_pipeline_steps` tras `BuildPersonalStep` y los dos docstrings.  |  Verificación: `test_f056_r1_orden_en_run_all`, `test_f056_r4_*`
- [ ] T12: PROPAGACIÓN 2/9 — listas cerradas de otros tests (`test_f024_cli.py`, `test_f047_nocturna.py`, `test_f006_publicacion.py`, `test_f079_stg_consultable.py`) y cualquier otra que destape `pytest` completo.  |  Verificación: `pytest` completo en verde
- [ ] T13: PROPAGACIÓN 3/9 — `ESQUEMAS_DEL_DATAMART`, `DEFAULT_CONSUMPTION_SCHEMAS`, `.env.example`; verificar sin tocar código que `apply_grants` y `check-declarados` cubren `contabilidad`.  |  Verificación: `test_f056_r31_*`
- [ ] T14: PROPAGACIÓN 4/9 — `config/diccionario/contabilidad.yaml` con las tres fichas, claves, relaciones y las advertencias de R28 con cifra.  |  Verificación: `test_f056_r27_*`, `test_f056_r28_*`, puerta de diccionario de `bash harness/init.sh`
- [ ] T15: PROPAGACIÓN 5/9 — `00_global.yaml`: esquema `contabilidad`, regla `R-SALDO-CONTABLE`, `version` + 1, `pendientes` sin crecer.  |  Verificación: `test_f056_r29_*`
- [ ] T16: PROPAGACIÓN 6/9 — fichas `raw.cua`, `raw.asi`, `raw.apu`, `raw.apa` corregidas (fecha, grupos tip 16 / auxiliares tip 17, `apa` analítica).  |  Verificación: `test_f056_r30_*`
- [ ] T17: PROPAGACIÓN 7/9 — `docs/ARCHITECTURE.md` y `CLAUDE.md` (mapa de `sql/`).  |  Verificación: `test_f056_r32_documentacion`, revisión del reviewer contra `design.md`
- [ ] T18: PROPAGACIÓN 8/9 — `azure-apps/datamart_seg_anual.md` (esquema expuesto), commit en el repositorio `azure-apps`.  |  Verificación: revisión del reviewer (R32)
- [ ] T19: PROPAGACIÓN 9/9 — dejar escrito en `progress/impl_F-056.md` el cambio exacto que necesita `mcp-bbdd` (lista blanca `servidor.esquemas_permitidos`), sin tocar ese repositorio.  |  Verificación: revisión del reviewer (R32, D5)
- [ ] T20: Cerrar la fase VERDE: `pytest` completo en verde y cobertura >= 80 % de líneas cambiadas.  |  Verificación: `bash harness/init.sh`
- [ ] T21: Campaña de mutación ENTERA del nivel `critico`, con el análisis de cada superviviente en `progress/mutacion_F-056.md`.  |  Verificación: `python -m harness.mutacion --feature F-056`
- [ ] T22: Build contra la base que autorice el humano: `python main.py build-contabilidad`, con minutos por sub-paso, MB de las tres tablas, SKU del servidor y ocupación del disco antes y después (R35).  |  Verificación: MANUAL (humano) — `python main.py timings` y `pg_total_relation_size` de las tres tablas
- [ ] T23: Caso testigo y contraste: el mayor de `1-4308000197` (R33) y el saldo 2026 de la subcuenta `1-434` (R34), más `count(*)` de `contabilidad.mayor` = `raw.apu` y la suma de `importe_saldo` igual en `mayor` y `saldos_cuenta_mes` (R26).  |  Verificación: MANUAL (humano) — consultas C1-C4 de `progress/spec_F-056.md`
- [ ] T24: `python main.py check-declarados`, `check-unicidad`, `check-relaciones`, `check-diccionario`; después `apply-grants` (comprobar que lista `contabilidad`), `publicar-diccionario` y el cambio de `mcp-bbdd`.  |  Verificación: MANUAL (humano) — escrituras contra Azure, las autoriza el humano
- [ ] T25: Ejecutar `bash harness/init.sh` en verde.  |  Verificación: `bash harness/init.sh`
