<!-- specs/F-025-ventana-negocio-build/tasks.md -->
# F-025 · Tareas

Rama `feature/F-025-ventana-negocio-build`. Un commit por tarea
(`F-025 Tn: ...`). **Las decisiones DA-1 a DA-4 las cerró el humano el 2026-09-02**
(`decisiones.md`); DA-5 queda con la recomendación de la spec y **DA-6 la EXIMIÓ el humano el 2026-09-04** (ver T26). Todo lo que
escriba en producción o reconstruya va marcado **MANUAL (humano)**.

## Fase 0 · Medir antes de tocar nada

- [ ] T1: Medir el ahorro real del criterio con la consulta de pesos que la nocturna ya ejecuta (`SQL_PESOS_PLAN_MENSUAL`), repartido entre las 40 obras vivas y las 880 congeladas  |  Verificación: MANUAL (humano), cifra escrita en `mediciones.md`; si el ahorro es menor del 40 % del peso, PARAR y reconsultar
- [x] T2: Medir tamaño (`pg_total_relation_size`) y `pg_stat_user_tables` de `stg.plan_mensual` y `stg.presupuesto` como línea base del bloat  |  Verificación: MANUAL (humano), cifras en `mediciones.md`
- [ ] T2b: Medir el coste del scan agregado de la firma sobre `raw.obrparpre`, en sus dos variantes (sin `planif` y con `md5(planif)`)  |  Verificación: MANUAL (humano), segundos de cada variante en `mediciones.md`; decide la forma final de la firma

## Fase 1 · Dominio puro (sin BBDD)

- [x] T3: RED — tests de `domain/ventana.py`: las tres reglas de DA-1 por separado y en unión, obra sin fases, obra sin filas, registro ausente  |  Verificación: `pytest tests/test_f025_ventana.py` falla por `ModuleNotFoundError` (traza en el informe)
- [x] T4: `domain/ventana.py`: `clasificar_obras()` devuelve reconstruidas, congeladas y **motivo por obra**; función pura  |  Verificación: `pytest tests/test_f025_ventana.py -q` en verde
- [x] T5: `firma_de_obra()` y `sello_sql()` deterministas, con fixtures  |  Verificación: `pytest tests/test_f025_firma.py -q`
- [x] T6: Tests de las tres precedencias (sello > firma > criterio) y de que **ningún filtro puede sacar una obra** de la lista  |  Verificación: `pytest tests/test_f025_precedencia.py -q`

## Fase 2 · Configuración y consultas

- [x] T7: `PG_VENTANA_ACTIVA` (default false), `PG_VENTANA_MESES`, `PG_VENTANA_DIA_COMPLETA` (domingo) y `PG_VENTANA_RESCATE` (off) en `config/settings.py`, y el bloque `ventana:` de `config/business_rules.yaml` con los tres estados que congelan (1, 11, 25) y el patrón de seis dígitos  |  Verificación: `pytest tests/test_f025_settings.py -q`
- [x] T8: `SQL_ESTADO_OBRAS` y `SQL_FIRMA_ORIGEN` (sobre `raw`) como constantes de módulo en `postgres_client.py`, con sus `fetch_*`  |  Verificación: test estático que lee el SQL enviado, sin conexión
- [x] T9: `sql/ddl/00_meta.sql`: `_meta.obra_build` (`CREATE TABLE IF NOT EXISTS`) y `_meta.v_frescura_obra` (`CREATE OR REPLACE VIEW`), sin `DROP`  |  Verificación: `pytest tests/test_f025_ddl.py -q` (el fichero contiene los objetos y ningún `DROP`)

## Fase 3 · El build que no borra lo que no reconstruye

- [x] T10: RED — test de que el build acotado **no llama a `truncate_table`** para `plan_mensual` y sí emite `DELETE ... WHERE obra_id = ANY` por tramo  |  Verificación: `pytest tests/test_f025_build.py -q` en rojo primero
- [x] T11: `build_stg_step`: componer el plan de obras, borrar+insertar por tramo en la misma transacción y eliminar el `TRUNCATE` global  |  Verificación: `pytest tests/test_f025_build.py -q` en verde, con cliente simulado
- [x] T11b: Acotar `06_presupuesto.sql` (DA-2): marcador `/*F025_FILTRO_OBRAS*/`, `TRUNCATE` sustituido por el `DELETE` derivado, una sola pasada con las obras vivas  |  Verificación: `pytest tests/test_f025_presupuesto.py -q`
- [x] T11c: Sub-paso `firma_origen` tras `ingest_raw`: calcula la firma por obra sobre `raw` y la guarda en `_meta.obra_build`  |  Verificación: `pytest tests/test_f025_firma_paso.py -q`
- [x] T12: Nueva política de aborto (R13): parar sin vaciar, dejar cada obra con su última versión buena y registrar las no reconstruidas  |  Verificación: test de fallo de tramo intermedio; ninguna llamada de truncado
- [x] T13: Escritura de `_meta.obra_build` (upsert por obra) y recuentos en `_meta.etl_runs` (`obras_reconstruidas`, `obras_congeladas`)  |  Verificación: `pytest tests/test_f025_registro.py -q`
- [x] T14: `VACUUM (ANALYZE) stg.plan_mensual` al final del sub-paso, en conexión autocommit y tolerante a fallo (avisa, no tumba la noche)  |  Verificación: test de que se ejecuta fuera de transacción y de que un fallo no cambia el estado del paso
- [x] T15: Reconstrucción completa **semanal en domingo** por antigüedad registrada, más el flag `--reconstruir-todo` en `run-all` y `stage`  |  Verificación: `pytest tests/test_f025_completa.py -q`
- [x] T16: Comando `ventana-plan` (dry-run, solo lectura): obras a reconstruir, congeladas, motivo y peso  |  Verificación: `pytest tests/test_f025_cli.py -q`

## Fase 4 · Guardián y alerta

- [x] T17: `ventana_sql.py` (solo texto, sin conexión) con `SET LOCAL statement_timeout` en cada consulta  |  Verificación: test estático de que el módulo no importa el cliente
- [x] T18: Comando `check-ventana`: firma divergente, obra congelada sin filas, sello no vigente, reconstrucción completa vencida  |  Verificación: `pytest tests/test_f025_check_ventana.py -q`
- [x] T19: Enganche al final de `run-all` **sin cambiar el código de salida** y marcador `[F025-VENTANA-KO]`  |  Verificación: test de que `run-all` termina en 0 con el guardián en KO
- [x] T20: `infra/97_create_alert_ventana.ps1` + test que cruza el marcador del código con el del `.ps1`  |  Verificación: `pytest tests/test_f025_marcador.py -q`

## Fase 5 · La quinta huella

- [x] T21: Formato `plan_obra` en `domain/huella_ampliada.py` e implementación en `infrastructure/postgres/huella_ampliada.py`  |  Verificación: `pytest tests/test_f025_huella.py -q`
- [x] T22: `huella-obras --desde plan_obra` y su rama en `comparar-huellas`, con tolerancia cero  |  Verificación: `pytest tests/test_f025_huella_cli.py -q`

## Fase 6 · Documentación

- [x] T23: Fichas de `_meta.obra_build` y `_meta.v_frescura_obra`, y actualización de las de `stg.plan_mensual` y `stg.presupuesto` (no se reconstruyen enteras cada noche; `_built_at` por obra)  |  Verificación: `bash harness/init.sh` (puerta de diccionario) en verde
- [x] T23b: Documentar los catorce estados de `conest` (tipo 42) en la ficha de `maestro.obras.estado_id` de `config/diccionario/maestro.yaml`, que hoy dice que el catálogo no se ingiere; enlazar con F-054  |  Verificación: `python main.py check-diccionario` (MANUAL) y revisión del reviewer
- [x] T24: `version` de `00_global.yaml` y `pendientes` que no crece  |  Verificación: `bash harness/init.sh`
- [x] T25: `docs/ARCHITECTURE.md` (la ventana junto a F-019 y F-024, con el cambio de invariante) y `azure-apps/datamart_seg_anual.md` (frescura por obra)  |  Verificación: revisión del reviewer
- [x] T26: Campaña de mutación sobre `domain/ventana.py`  |  Verificación: `python -m harness.mutacion` sin supervivientes, o exención escrita del humano — **hecha sobre `domain/ventana.py` (83 mutantes, CERO supervivientes) y el resto del alcance EXENTO por el humano el 2026-09-04 (DA-6)**: no se extiende a los 219 mutantes de los diez ficheros, así que `build_stg_step.py` (34, el borrado derivado), `main.py` (37), `postgres_client.py` (31), `ventana_sql.py` (15) y `cobertura.py` (6) NO pasan por mutación; los cubren T27/T30 con tolerancia cero, `test_f025_build.py` y la cobertura de líneas cambiadas. El porqué entero, en `decisiones.md` §DA-6

## Fase 7 · Verificación contra la base (MANUAL, en este orden)

- [x] T27: Capturar las CINCO huellas del ANTES sobre el `raw` vigente, antes de reconstruir nada  |  Verificación: MANUAL (humano), cinco CSV guardados fuera de la base  |  **HECHA 2026-09-04: cinco CSV en huellas/antes_*.csv**
- [x] T28: `python main.py ventana-plan` contra producción y comprobar que el conjunto coincide con el censo de `mediciones.md`  |  Verificación: MANUAL (humano)  |  **HECHA 2026-09-05: 40 vivas / 328 congeladas de las 368 con `plan_mensual`; 552 sin filas se rehacen por R18 (T1 dirá cuánto pesan). Lanzada con `PG_VENTANA_ACTIVA=true` en la shell: el `.env` del puesto no la lleva**
- [x] T29: Primera reconstrucción acotada (`stage`), midiendo duración por tramo y ocupación de disco  |  Verificación: MANUAL (humano), `python main.py timings`  |  **HECHA 2026-09-05: `hamsh8o`, 4 h 52 en B2s, 920 obras en `_meta.obra_build`; tramos y créditos en `mediciones.md`, intento 3**
- [x] T30: Capturar las cinco huellas del DESPUÉS y compararlas **sin `--obras-esperadas`**  |  Verificación: MANUAL (humano), `comparar-huellas` con CERO diferencias en las cinco; cualquier diferencia PARA la feature  |  **HECHA 2026-09-05 y DADA POR BUENA POR EL HUMANO el 2026-09-06**: las cinco salieron KO, y todas las diferencias son del origen (dos volcados de Sigrid distintos, el del 04 y el del 05, con un día laborable entre medias); once obras vivas con actividad de agosto y la versión 11 del master de la 0712 creada en Sigrid el 04-sep; `stg` = `raw` fila a fila; ninguna congelada se mueve. Palabras del humano: «parecen cambios de obras vivas, es normal». Pruebas en `mediciones.md`. Queda dicho: esta primera pasada no congeló nada (R18), así que la prueba de que congelar no cambia una celda la da la primera nocturna acotada (T31b)
- [x] T31: Comprobar la 0599 en `cierre.v_pbi_cierre_resumen`: DIRECTOS 2.624.793 €, margen 1,8 %  |  Verificación: MANUAL (humano)  |  **HECHA 2026-09-05 23:07 UTC, tras `hamsh8o`: `inspect-cierre --codigo 0599`, Diciembre 2022 (fase 28), DIRECTOS 2.624.793,46 €, BENEFICIO 72.603,10 € = 1,79 %**
- [ ] T31b: Comprobar que las 40 obras vivas SÍ se han reconstruido esa noche y que las 880 conservan su `_built_at` anterior  |  Verificación: MANUAL (humano), `SELECT` sobre `_meta.v_frescura_obra`
- [ ] T32: `check-unicidad --timeout 300`, `check-cierres --timeout 900`, `check-cobertura`, `check-declarados` y `check-ventana`  |  Verificación: MANUAL (humano), mismo veredicto que antes del cambio
- [ ] T33: Medir el bloat tras la primera semana acotada y compararlo con T2  |  Verificación: MANUAL (humano), cifra en `mediciones.md`; si crece de forma sostenida, abrir la feature de particionado
- [ ] T34: Medir los créditos de CPU restantes al terminar la nocturna acotada (R29)  |  Verificación: MANUAL (humano), métrica de Azure; crédito restante > 0
- [x] T35: Desplegar `infra/97_create_alert_ventana.ps1` y añadir el buzón al grupo de acción  |  Verificación: MANUAL (humano), sin este paso el guardián es mudo  |  **HECHA 2026-09-04: alert-caj-datamart-seg-dev-ventana, activa, sev 2**
- [x] T36: Ejecutar `bash harness/init.sh` en verde  |  Verificación: código 0, incluidos pytest, tamaño y diccionario
