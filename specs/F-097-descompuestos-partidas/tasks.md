<!-- specs/F-097-descompuestos-partidas/tasks.md -->
# F-097 · Tareas

Rama `feature/F-097-descompuestos-partidas`. Rigor `estandar`: fase RED
obligatoria, cobertura >= 80 % de líneas cambiadas y campaña de mutación
muestreada (20 mutantes, semilla fija). Un commit por tarea (`F-097 Tn: ...`), en
español. **No se empieza sin D1-D11 de `progress/spec_F-097.md` cerradas por el
humano** (T0); si una no sigue la recomendación, se devuelve la spec.

- [ ] T0: Comprobar que D1-D11 están decididas y anotadas en `progress/current.md`; si alguna cambia la recomendación, parar y devolver la spec al spec-author.  |  Verificación: anotación en `progress/impl_F-097.md`
- [ ] T1: Escribir `tests/test_f097_identidad_ingesta.py` en fase RED para R4-R7 (dobles del cliente de Sigrid y de Postgres, sin red ni BBDD) y el test de equivalencia sobre las 71 entradas actuales.  |  Verificación: `pytest tests/test_f097_identidad_ingesta.py` falla; traza en `progress/impl_F-097.md`
- [ ] T2: Escribir `tests/test_f097_descompuestos.py` en fase RED, al menos un test por R1-R3 y R8-R28 (YAML, texto del SQL sin comentarios `--`, cableado del step y de `main.py`, diccionario), con un registro de ejemplo de 38 campos, uno de 19 y uno con salto de línea dentro del texto.  |  Verificación: `pytest tests/test_f097_descompuestos.py` falla; traza en `progress/impl_F-097.md`
- [ ] T3: `ingest_raw_step.py`: identidad por `target_table` (nombre de paso, estadísticas, fallos, `only_table`), manteniendo `source_table` para esquema y lectura.  |  Verificación: `test_f097_r4_*`, `test_f097_r5_*`
- [ ] T4: `build_stg_step.py` y `main.py` (`check-coherencia`, `check-raw-recuentos`): requeridas y recuentos por `target_table`, conteo en Sigrid con `source_table` + `where`.  |  Verificación: `test_f097_r4_*`, `test_f097_r7_*`
- [ ] T5: Tests de F-066, F-006 y F-074: `_ingesta()` por `target_table`, unicidad por `target_table`, `TOTAL_TABLAS = 72`.  |  Verificación: `test_f097_r6_*` y `pytest tests/test_f066_ingesta_raw.py tests/test_f006_raw_ingesta.py tests/test_f074_ingesta_censo.py`
- [ ] T6: `config/tables_sigrid.yaml`: entrada `obrparpre` → `obrparpre_des` con las 13 exclusiones, `page_size: 2000` y el `where` de las cuatro ramas, comentada con las cifras.  |  Verificación: `test_f097_r1_*`, `test_f097_r2_*`, `test_f097_r3_*`
- [ ] T7: `sql/descompuestos/00_setup.sql` (esquema, `fn_num`, `fn_fecha`).  |  Verificación: `test_f097_r8_*`, `test_f097_r14_*`
- [ ] T8: `sql/descompuestos/01_registros.sql` (troceado por `\n(?=~X|)`, `WITH ORDINALITY`, campos por posición, marca de partida enlazada).  |  Verificación: `test_f097_r12_*`, `test_f097_r13_*`
- [ ] T9: `sql/descompuestos/02_lineas.sql`: ramas `ESTUDIO`, `MASTER_INICIAL`, `MASTER_PLANIF_JO` y `PLANIF_JO`, valores, tipo de elemento, `CHECK` de origen, PK de negocio e índices.  |  Verificación: `test_f097_r11_*`, `test_f097_r15_*` a `test_f097_r21_*`
- [ ] T10: `sql/descompuestos/03_elementos.sql` (catálogo con `producto_id`).  |  Verificación: `test_f097_r22_*`
- [ ] T11: `sql/descompuestos/04_cuadre.sql` (universo de partidas hoja con precio, suma, diferencia, los cuatro estados) y `05_views.sql` (tres vistas con el origen cableado).  |  Verificación: `test_f097_r23_*`, `test_f097_r24_*`, `test_f097_r25_*`, `test_f097_r9_solo_raw`
- [ ] T12: `build_descompuestos_step.py` (`SUB_PASOS`, `depends_on`, parada con nombre del sub-paso) y en `main.py` el comando `build-descompuestos` y el paso tras `BuildContabilidadStep`.  |  Verificación: `test_f097_r8_*`, `test_f097_r10_*`
- [ ] T13: Listas cerradas de pasos en otros tests (`test_f024_cli.py`, `test_f047_nocturna.py`, `test_f006_publicacion.py`, `test_f079_stg_consultable.py`) y lo que destape `pytest` completo.  |  Verificación: `pytest` completo en verde
- [ ] T14: `ESQUEMAS_DEL_DATAMART`, `DEFAULT_CONSUMPTION_SCHEMAS`, `.env.example`.  |  Verificación: `test_f097_r27_*`
- [ ] T15: `config/diccionario/descompuestos.yaml`, ficha de `raw.obrparpre_des` en `raw.yaml`, `00_global.yaml` (esquema, `R-DESCOMPUESTO-ORIGEN`, `version` + 1, pendiente de `_registros`) y `objetos_pendientes.yaml` si hace falta.  |  Verificación: `test_f097_r26_*` y la puerta de diccionario de `bash harness/init.sh`
- [ ] T16: `docs/ARCHITECTURE.md` (72 tablas, esquema, formato del `des`, qué es cada pestaña), `CLAUDE.md` (mapa de `sql/`) y `azure-apps/datamart_seg_anual.md` con su commit en ese repositorio.  |  Verificación: `test_f097_r28_*` y revisión del reviewer
- [ ] T17: Cerrar la fase VERDE: `pytest` completo y cobertura >= 80 % de líneas cambiadas.  |  Verificación: `bash harness/init.sh`
- [ ] T18: Campaña de mutación muestreada del nivel `estandar`, supervivientes analizados en `progress/impl_F-097.md`.  |  Verificación: `python -m harness.mutacion --feature F-097`
- [ ] T19: Ingesta y coste: `python main.py ingest --table obrparpre_des --full` y `python main.py build-descompuestos`, con minutos (ingesta y cada sub-paso), filas y MB de las tablas nuevas, y disco antes y después (R31).  |  Verificación: MANUAL (humano) — `python main.py timings --last 5` y `SELECT relname, pg_size_pretty(pg_total_relation_size(oid)) FROM pg_class WHERE relnamespace = 'descompuestos'::regnamespace AND relkind = 'r';`
- [ ] T20: Casos testigo R29 y R30 y `check-raw-recuentos` de `obrparpre_des`.  |  Verificación: MANUAL (humano) — consultas C1-C4 de `progress/spec_F-097.md`
- [ ] T21: `check-declarados`, `check-unicidad`, `check-relaciones`, `check-diccionario`, `apply-grants`, `publicar-diccionario`, imagen nueva del job y la lista blanca de `mcp-bbdd` (añadir `descompuestos`).  |  Verificación: MANUAL (humano) — escrituras contra Azure
- [ ] T22: Ejecutar `bash harness/init.sh` en verde.  |  Verificación: `bash harness/init.sh`
