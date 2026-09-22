<!-- specs/F-051-nombre-mes-real/tasks.md -->
# F-051 · Tareas

Rama `feature/F-051-nombre-mes-real`. Un commit por tarea (`F-051 Tn: ...`). Rigor
`critico`: **fase RED obligatoria** (traza en el informe) y **cobertura de las
líneas cambiadas**. Campaña de mutación: según **D7** (si el humano concede la
exención de F-042, el reviewer la declara N/A en C4 bis citándola; si no, se corre
entera). Antes de T1, el humano resuelve D1–D9 (`design.md` §10).

## Bloque A · La regla, en dominio puro

- [ ] T1: Escribir `tests/test_f051_regla_mes.py` con la tabla de textos reales de `progress/spec_F-051.md` §3 (rango, años 00–19, «2.013», sin texto, 0673 f8, 0692 f14, 0440 f3) y las cuatro ramas de `mes_de_fase`, contra `etl_sigrid/domain/mes_fase.py` aún inexistente | Verificación: `pytest tests/test_f051_regla_mes.py` **falla** (fase RED, traza al informe)
- [ ] T2: Implementar `parse_mes_fase` y `mes_de_fase` en `etl_sigrid/domain/mes_fase.py` | Verificación: `pytest tests/test_f051_regla_mes.py -k "parse or mes_de_fase"` en verde
- [ ] T3: Añadir a `test_f051_regla_mes.py` los casos de relleno: R10, R11 (mes ocupado por otra fase aunque valga 0), R14 (texto = primer mes o intermedio), texto anterior a `fecha_inicio`, y colisión de F-042 sobre el mes del texto con la perdedora sin relleno (R8+R11) | Verificación: `pytest tests/test_f051_regla_mes.py -k relleno` **falla** (RED)
- [ ] T4: Implementar `meses_relleno` y `acumulado_relleno` (R12, R13) | Verificación: `pytest tests/test_f051_regla_mes.py` en verde
- [ ] T5: Escribir `tests/test_f051_invariante.py` (series generadas con semilla fija: suma de `importe_mes` y último acumulado por partida idénticos con y sin relleno; ninguna (obra, ámbito, partida, mes) repetida) | Verificación: `pytest tests/test_f051_invariante.py` en verde, y en rojo si se muta el arrastre de T4 (traza)

## Bloque B · SQL de `stg`

- [ ] T6: Escribir `tests/test_f051_sql.py` con las comprobaciones estructurales de `design.md` §8 para `stg` (funciones nuevas, `08` sin `make_date(f.anio, f.mes, 1)` en reales, un solo marcador de tramo, `reales_final` dentro de los marcadores, prefijos de mes del parser = oráculo, `00_functions.sql` en `FICHEROS_DEL_SELLO`) | Verificación: `pytest tests/test_f051_sql.py` **falla** (RED)
- [ ] T7: Crear `stg.fn_parse_mes_texto` y `stg.fn_mes_de_fase` en `sql/stg/00_functions.sql` (design §4) | Verificación: `pytest tests/test_f051_sql.py -k funciones` en verde
- [ ] T8: Añadir `es_relleno` a `stg.plan_mensual` en `sql/stg/01_ddl.sql` (bloque `DO` idempotente) | Verificación: `pytest tests/test_f051_sql.py -k ddl` en verde
- [ ] T9: Reescribir la rama de reales de `sql/stg/08_plan_mensual.sql` (design §5, pasos 1–8) y el `INSERT` con `es_relleno` | Verificación: `pytest tests/test_f051_sql.py tests/test_f042_sql.py` en verde (incluida `test_f042_ninguna_ventana_del_fichero_cruza_obras`)
- [ ] T10: Añadir `00_functions.sql` a `FICHEROS_DEL_SELLO` en `build_stg_step.py` y ajustar los tests de F-025 que fijan la lista | Verificación: `pytest tests/test_f025_*.py tests/test_f051_sql.py -k sello` en verde
- [ ] T11: Apuntar `sql_huella_propuesta` a `reales_final` en `huella_obras.py` | Verificación: `pytest tests/test_f042_huella.py tests/test_f025_huella.py` en verde

## Bloque C · `mart` y `cierre`

- [ ] T12: Ampliar `test_f051_sql.py` con `mart` y `cierre` (ARRAY en las ramas 1 y 2 de `mart/02`; `es_relleno` en `mart/01`, `v_pbi_fact` y `cierre/01`; `cierre/02` y `04` sin `fn_mes_de_fase` y agrupando por `pm.anio_mes`; la vista sin `nombre_mes` en `GROUP BY` ni `JOIN`) | Verificación: `pytest tests/test_f051_sql.py -k "mart or cierre or vista"` **falla** (RED)
- [ ] T13: Cambiar `sql/mart/01_ddl.sql`, `02_build_fact.sql` y `05_views_powerbi.sql` (design §2) | Verificación: `pytest tests/test_f051_sql.py -k mart tests/test_f019_t13_portabilidad.py tests/test_f078_sql.py` en verde
- [ ] T14: Envolver `cierre.fn_mes_de_fase` sobre la de `stg` y cambiar `cierre/01_ddl_fact.sql`, `02_build_fact.sql` y `04_views_detalle.sql` | Verificación: `pytest tests/test_f051_sql.py -k cierre` en verde
- [ ] T15: Blindar `sql/cierre/06_views_planif_vs_real.sql` (design §6) | Verificación: `pytest tests/test_f051_sql.py -k vista` en verde

## Bloque D · Comprobación en la base y documentación

- [ ] T16: Comando `python main.py check-mes-fase` (solo lectura, `READ ONLY`): `stg.fn_mes_de_fase` = oráculo en todas las fases; claves (obra, ámbito, partida, mes) únicas; relleno con movimiento 0 y nunca en mes ocupado; `--obras-esperadas CSV` para `comparar-huellas`; con tests offline del comando (mock de Postgres) | Verificación: `pytest tests/test_f051_check.py` en verde
- [ ] T17: Diccionario (`stg`, `mart`, `cierre`, `00_global` con `version` +1) según design §7, retirando el aviso de fan-out de `v_pbi_planif_vs_real` | Verificación: `pytest tests/test_f006_*.py` en verde
- [ ] T18: `docs/ARCHITECTURE.md`, viñeta «EL MES DE UN CIERRE REAL LO DA SU TEXTO (F-051)» con el relleno y la precedencia | Verificación: revisión del reviewer contra R1–R15
- [ ] T19: Huellas ANTES sobre la base actual: `python main.py huella-obras --desde stg --out huella_f051_stg_antes.csv` (y `mart`, `cierre`) | Verificación: MANUAL (humano), solo lectura
- [ ] T20: Crear SOLO las dos funciones de `stg` en la base (escritura aditiva, la autoriza el humano) y `python main.py huella-obras --desde stg --propuesta --out huella_f051_stg_propuesta.csv`; medir tiempo del tramo más pesado (riesgo R5) | Verificación: MANUAL (humano)
- [ ] T21: Tras despliegue y reconstrucción completa: huellas DESPUÉS, `comparar-huellas` con `check-mes-fase --obras-esperadas`, `check-unicidad` (vista en OK; fact con `--timeout 300`), `check-cierres`, `check-mes-fase` y los testigos de design §8, contando las filas de relleno (riesgo R2) | Verificación: MANUAL (humano), resultados en `progress/impl_F-051.md`
- [ ] T22: Ejecutar `bash harness/init.sh` en verde | Verificación: `bash harness/init.sh` sale con código 0
