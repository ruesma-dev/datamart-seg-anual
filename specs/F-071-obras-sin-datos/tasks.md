> # ⛔ SPEC RETIRADA el 2026-09-09, ANTES DE IMPLEMENTAR NADA
>
> El humano paró F-071 al leer esta spec: **«no vamos a borrar nada de
> momento, vamos a seguir dejando todo. Quitamos esta feature.»** La purga
> nocturna (R20) y el acotado del censo (R19) **no se hacen**. F-071 ya no
> existe en `harness/features.json`.
>
> **Esta carpeta se conserva solo por lo que costó medir**, y esa evidencia
> pasa a alimentar **F-072** (el censo semántico) y **F-073** (las tablas
> nuevas y el enriquecimiento): las cifras del §1 de `design.md`, que tres de
> los ocho campos de dirección no son dirección de la obra, y que el municipio
> y la provincia viven en `raw.auxmun` y `raw.auxpro`. **Lo que sobrevive es
> el enriquecimiento —la dirección y las marcas— sin borrar ni filtrar nada.**
>
> No implementes desde aquí. Ver `progress/current.md`.

<!-- specs/F-071-obras-sin-datos/tasks.md -->
# F-071 · Tareas

Rigor `estandar`: fase RED documentada, cobertura de las líneas cambiadas y
campaña de mutación con supervivientes analizados (`CHECKPOINTS.md` C4 bis).
T1 va **antes que todo**: su resultado puede tumbar la mitad de la feature.

- [ ] T1: Medir la dirección en `raw.obr` con el SQL de `design.md` §7 (solo lectura, script de un uso en `scripts/`) y escribir `specs/F-071-obras-sin-datos/mediciones.md` con las cifras y el veredicto de R10 campo a campo (R9, R11)  |  Verificación: MANUAL (humano): el fichero existe, trae las ocho cuentas y dice qué se publica y qué no
- [ ] T2: PARAR y enseñar al humano el resultado de T1 si `dir1` o `municipio` no llegan a 195 obras: eso activa R13 y cambia el alcance  |  Verificación: MANUAL (humano): decisión anotada en `progress/current.md`
- [ ] T3: Fase RED — escribir `tests/test_f071_obras_sin_datos.py` con los tests de R1, R2, R3, R6, R8, R12, R19, R20 y R22 sobre el texto de los SQL y sobre `SQL_ESTADO_OBRAS`, y dejar la traza de que fallan  |  Verificación: `pytest tests/test_f071_obras_sin_datos.py` en rojo, traza en `progress/impl_F-071.md`
- [ ] T4: Añadir a `sql/stg/01_ddl.sql` los seis `ALTER TABLE stg.obras ADD COLUMN IF NOT EXISTS` de la dirección (R6)  |  Verificación: `pytest tests/test_f071_obras_sin_datos.py -k ddl`
- [ ] T5: Ampliar `sql/stg/03_obras.sql` para poblar las seis columnas desde `raw.obr` con `LEFT JOIN raw.auxmun` y `raw.auxpro`, y componer `direccion_completa` según R8 (R6, R8)  |  Verificación: `pytest tests/test_f071_obras_sin_datos.py -k direccion`
- [ ] T6: Crear `sql/stg/03b_purga_obras_fuera.sql` con los dos `DELETE` idempotentes de `design.md` §6 (R20)  |  Verificación: `pytest tests/test_f071_obras_sin_datos.py -k purga`
- [ ] T7: Registrar el sub-paso `purga_obras_fuera` en `build_stg_step.py`, entre `build_obras` y `build_partidas` (R20)  |  Verificación: `pytest tests/test_f071_obras_sin_datos.py -k subpaso_stg`
- [ ] T8: Añadir a `mart.v_pbi_dim_obra` en `sql/mart/05_views_powerbi.sql` las marcas `tiene_presupuesto` y `tiene_plan_mensual` y las seis columnas de dirección, sin quitar nada (R1, R4, R7)  |  Verificación: `pytest tests/test_f071_obras_sin_datos.py -k dim_obra`
- [ ] T9: Crear `sql/mart/07_view_obras_con_datos.sql` y registrar su sub-paso, el último, en `build_mart_step.py` (R2)  |  Verificación: `pytest tests/test_f071_obras_sin_datos.py -k obras_con_datos`
- [ ] T10: Añadir las seis columnas de dirección a `sql/maestro/01_obras.sql` y corregir su cabecera, que afirma que las obras no tienen dirección en Sigrid (R7, R14)  |  Verificación: `pytest tests/test_f071_obras_sin_datos.py -k maestro`
- [ ] T11: Acotar `SQL_ESTADO_OBRAS` (`postgres_client.py:215`) con `JOIN stg.obras so ON so.obra_id = c.ide` (R19)  |  Verificación: `pytest tests/test_f071_obras_sin_datos.py -k censo`
- [ ] T12: Escribir la regla dura `R-OBRA-SIN-DATOS` en `config/diccionario/00_global.yaml` con el enrutado de R15, la referencia cruzada en `R-UNIVERSO-OBRA` (R16) y `version: 17`  |  Verificación: `pytest tests/test_f006_fichas.py`
- [ ] T13: Corregir en `tests/test_f006_fichas.py:1347` la aserción de `R-UNIVERSO-OBRA` (hoy exige «919»; el universo medido el 2026-09-09 son 921)  |  Verificación: `pytest tests/test_f006_fichas.py -k universo`
- [ ] T14: Actualizar las fichas de `mart.v_pbi_dim_obra`, `stg.obras` y `maestro.obras` y crear la de `mart.v_obras_con_datos`, cada columna de dirección con su % informado de T1 (R11, R17)  |  Verificación: `pytest tests/test_f006_cobertura.py tests/test_f006_fichas.py`
- [ ] T15: Ejecutar `bash harness/init.sh` y comprobar que la puerta del diccionario sigue verde sin añadir pendientes (R17)  |  Verificación: `bash harness/init.sh`
- [ ] T16: Medir el antes/después del censo con `python main.py ventana-plan --detalle` y anotar en `mediciones.md` cuántas obras se dejan de reprocesar cada noche (R21)  |  Verificación: MANUAL (humano): las dos salidas, con el reparto por motivo
- [ ] T17: Comprobar contra Azure, en solo lectura, que siguen las 583 filas de `mart.v_pbi_dim_obra`, las 498 con presupuesto, las 349 con plan y las 349 con hechos (R5, R23)  |  Verificación: MANUAL (humano): la consulta de `requirements.md` §cifras, antes y después de la nocturna
- [ ] T18: Comprobar que `mart.v_obras_con_datos` trae 349 filas y es subconjunto de `mart.v_pbi_dim_obra` (R2, R3)  |  Verificación: MANUAL (humano): consulta por MCP tras la nocturna
- [ ] T19: Verificar la regla dura preguntando al MCP «¿cuántas obras tenemos?» y «¿dónde está la obra 0704?» **sin explicarle nada en el prompt**, y pegar las respuestas (R18)  |  Verificación: MANUAL (humano): las dos respuestas en `progress/impl_F-071.md`
- [ ] T20: Verificar que una obra sin datos se responde «existe, sin datos de seguimiento» y no «no existe», preguntando por una de las 234 (R3, R15)  |  Verificación: MANUAL (humano): la respuesta pegada
- [ ] T21: Actualizar `docs/ARCHITECTURE.md` con el censo nuevo (583 en vez de 920 fichas) y la purga (R24)  |  Verificación: `git diff docs/ARCHITECTURE.md`
- [ ] T22: Actualizar `azure-apps/datamart_seg_anual.md` («Qué expone»: `mart.v_obras_con_datos` y la dirección; y las cifras del censo) y hacer commit en ese repositorio (R24)  |  Verificación: MANUAL (humano): `git -C ../azure-apps log -1 --stat`
- [ ] T23: Ejecutar la campaña de mutación y analizar los supervivientes (C4 bis)  |  Verificación: `python -m harness.mutacion --feature F-071`
- [ ] T24: Escribir `progress/impl_F-071.md` con la traza de fase RED, las evidencias y las verificaciones MANUAL con su resultado real  |  Verificación: `python -m harness.tamano --feature F-071`
- [ ] T25: Ejecutar `bash harness/init.sh` en verde  |  Verificación: `bash harness/init.sh`
