<!-- specs/F-097-descompuestos-partidas/tasks.md -->
# F-097 · Tareas

Rama `feature/F-097-descompuestos-partidas`. Rigor `estandar`: fase RED
obligatoria, cobertura >= 80 % de líneas cambiadas y campaña de mutación
muestreada (20 mutantes, semilla fija). Un commit por tarea (`F-097 Tn: ...`), en
español. D1-D11 aprobadas (D4 y D5 cambiadas) y D12-D15 en `progress/spec_F-097.md`:
**no se empieza sin D12-D15 cerradas**, y el incremental (T4, T5, T7 y T9) **no se empieza
sin T0 superada**.

- [ ] T0: BLOQUEANTE, solo lectura, un día laborable a partir del 2026-10-05 (ideal: tras los cierres de mitad de mes): segunda toma con `progress/mediciones/F-097_huella_master.sql` por `SigridApiClient.leer_sql` y comparación con `F-097_huella_master_2026-09-27.csv`, versión a versión; anotar cuántas cambian por grupo (anterior a la vigente y no última / vigente / posterior / nueva). Si cambia alguna del primer grupo: PARAR y volver al humano.  |  Verificación: MANUAL (humano o implementer) — tabla de resultados en `progress/impl_F-097.md`
- [ ] T1: Comprobar que D12-D15 están decididas en `progress/current.md`; si alguna no sigue la recomendación, devolver la spec.  |  Verificación: anotación en `progress/impl_F-097.md`
- [ ] T2: Fase RED: `tests/test_f097_planificador.py`, `test_f097_ingesta_descompuestos.py`, `test_f097_descompuestos.py` y `test_f097_tiemod_obrparpre.py`, al menos un test por R2-R29 (registros de ejemplo de 38 y 19 campos y uno con salto de línea en el texto largo).  |  Verificación: `pytest tests/test_f097_*.py` falla; traza en `progress/impl_F-097.md`
- [ ] T3: `tables_sigrid.yaml`: `obrparpre` con `incremental_column: null` y el comentario de lo medido.  |  Verificación: `test_f097_r29_*`
- [ ] T4: `etl_sigrid/domain/descompuestos.py` con `planificar_relectura` (nuevas, vigentes, huella distinta, borradas, presupuesto, `sin_tope`).  |  Verificación: `test_f097_r5_*`, `test_f097_r6_*`, `test_f097_r7_*`
- [ ] T5: `postgres_client.reemplazar_filas` (DELETE + COPY + control en una transacción).  |  Verificación: `test_f097_r8_*` con doble de conexión
- [ ] T6: `sql/descompuestos/00_setup.sql` (esquema, `_des_texto`, `_versiones_cargadas` sin `DROP`, `fn_num`, `fn_fecha`).  |  Verificación: `test_f097_r2_*`, `test_f097_r14_*`
- [ ] T7: `ingest_descompuestos_step.py`: huella, ámbito 3 entero, versiones por el plan, recuento contra huella con reversión, registro en `_meta.etl_runs`.  |  Verificación: `test_f097_r3_*`, `test_f097_r4_*`, `test_f097_r9_*`, `test_f097_r10_*`, `test_f097_r11_*`
- [ ] T8: `01_troceado.sql` (`fn_trocear`) y `02_lineas_coste.sql` (`lineas`, `ESTUDIO`, `PLANIF_JO`).  |  Verificación: `test_f097_r12_*`, `test_f097_r13_*`, `test_f097_r15_*`, `test_f097_r16_*`, `test_f097_r18_*` a `test_f097_r20_*`
- [ ] T9: `03_lineas_master.sql` (lote con marcador, origen y flags, sello, borrado de versiones que ya no están).  |  Verificación: `test_f097_r17_*`, `test_f097_r21_*`
- [ ] T10: `04_elementos.sql`, `05_cuadre.sql` y `06_views.sql`.  |  Verificación: `test_f097_r22_*`, `test_f097_r23_*`, `test_f097_r24_*`, `test_f097_r26_solo_raw`
- [ ] T11: `build_descompuestos_step.py` y en `main.py` los comandos `ingest-descompuestos` y `build-descompuestos` (`--sin-tope`) y los dos pasos tras `BuildContabilidadStep`.  |  Verificación: `test_f097_r25_*`
- [ ] T12: `settings.py` (`DESCOMPUESTOS_PRESUPUESTO_MB`, `DEFAULT_CONSUMPTION_SCHEMAS`), `ESQUEMAS_DEL_DATAMART`, `.env.example` y las listas cerradas de pasos de otros tests.  |  Verificación: `test_f097_r27_*` y `pytest` completo
- [ ] T13: `config/diccionario/descompuestos.yaml`, `00_global.yaml` (esquema, regla, `version` + 1, pendientes de las tablas `_`) y `objetos_pendientes.yaml` si hace falta.  |  Verificación: `test_f097_r27_*` y la puerta de diccionario de `bash harness/init.sh`
- [ ] T14: `docs/ARCHITECTURE.md`, `CLAUDE.md` y `azure-apps/datamart_seg_anual.md` (commit en ese repositorio).  |  Verificación: `test_f097_r28_*` y revisión del reviewer
- [ ] T15: Fase VERDE: `pytest` completo y cobertura >= 80 % de líneas cambiadas.  |  Verificación: `bash harness/init.sh`
- [ ] T16: Campaña de mutación muestreada, supervivientes en `progress/impl_F-097.md`.  |  Verificación: `python -m harness.mutacion --feature F-097`
- [ ] T17: Primera carga fuera de la nocturna (D15): `python main.py ingest-descompuestos --sin-tope` y `python main.py build-descompuestos --sin-tope`, con tiempo, versiones, filas, MB por tabla y disco antes y después (R31).  |  Verificación: MANUAL (humano) — `python main.py timings --last 5` y `pg_total_relation_size` de las tablas de `descompuestos`
- [ ] T18: Casos testigo R30 y la noche siguiente medida (minutos de los dos pasos, versiones releídas y aplazadas).  |  Verificación: MANUAL (humano) — consultas C1-C4 de `progress/spec_F-097.md`
- [ ] T19: `check-declarados`, `check-unicidad`, `check-relaciones`, `check-diccionario`, `apply-grants`, `publicar-diccionario`, imagen nueva del job y `descompuestos` en la lista blanca de `mcp-bbdd`.  |  Verificación: MANUAL (humano) — escrituras contra Azure
- [ ] T20: Ejecutar `bash harness/init.sh` en verde.  |  Verificación: `bash harness/init.sh`
