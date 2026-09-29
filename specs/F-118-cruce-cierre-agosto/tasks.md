<!-- specs/F-118-cruce-cierre-agosto/tasks.md -->
# F-118 · Tareas

Rama `feature/F-118-cruce-cierre-agosto` (la de F-051 no se usa). Un commit por tarea (`F-118 Tn: ...`). Rigor `critico`: **fase RED obligatoria** (traza en el informe) y **cobertura de las líneas cambiadas**. Campaña de mutación: N/A por la exención de F-051 D7 (como F-042), sustituida por huellas e invariante R21–R23; el reviewer la declara N/A en C4 bis citándola. Requisitos heredados de F-051: sus tareas T1–T22 se reparten aquí. **Antes de T1, el humano decide D1–D9** (`design.md` §11); el bloque E espera a D6.

## Bloque A · El mes (F-051), en dominio puro

- [ ] T1: Escribir `tests/test_f118_regla_mes.py` con la tabla de textos de `progress/spec_F-051.md` §3 y las ramas de R2–R6, contra `etl_sigrid/domain/mes_fase.py` aún inexistente | Verificación: `pytest tests/test_f118_regla_mes.py` **falla** (RED, traza al informe)
- [ ] T2: Implementar `parse_mes_fase` y `mes_de_fase` en `etl_sigrid/domain/mes_fase.py` | Verificación: `pytest tests/test_f118_regla_mes.py -k "parse or mes_de_fase"` en verde
- [ ] T3: Añadir los casos de relleno R10–R14 y R8+R11 (F-051 T3) | Verificación: `pytest tests/test_f118_regla_mes.py -k relleno` **falla** (RED)
- [ ] T4: Implementar `meses_relleno` en `mes_fase.py` | Verificación: `pytest tests/test_f118_regla_mes.py` en verde

## Bloque B · La serie densa, en dominio puro

- [ ] T5: Escribir `tests/test_f118_serie_densa.py`: 0709 417031 (−58.000, ausente, 0 → movimientos −58.000, +58.000, 0), partida que sale en el último cierre, que sale y vuelve (R30), una sola fila de deshacer (R32), relleno tras un deshacer (R33), fase sin filas del ámbito (R34), hueco de numeración de F-103 | Verificación: `pytest tests/test_f118_serie_densa.py` **falla** (RED)
- [ ] T6: Implementar `serie_densa` en `etl_sigrid/domain/serie_real.py` (design §3 y §5 pasos 4–9) | Verificación: `pytest tests/test_f118_serie_densa.py` en verde
- [ ] T7: Escribir `tests/test_f118_invariante.py` (semilla fija): para toda serie generada, suma de movimientos = acumulado del último cierre del ámbito (R21) y ningún (partida, mes) repetido | Verificación: en verde, y en rojo si se muta el 0 del cierre ausente de T6 (traza)

## Bloque C · SQL de `stg` y `check-cierres`

- [ ] T8: Escribir `tests/test_f118_sql.py` para `stg` (funciones de F-051, `es_relleno` y `es_deshacer` en el DDL, sin `make_date(f.anio, f.mes, 1)` ni `orden_fase` ni `CASE` de consecutividad en la rama de reales, `reales_final` dentro de los marcadores, un solo marcador de tramo, `00_functions.sql` en `FICHEROS_DEL_SELLO`) | Verificación: `pytest tests/test_f118_sql.py` **falla** (RED)
- [ ] T9: Crear `stg.fn_parse_mes_texto` y `stg.fn_mes_de_fase` en `sql/stg/00_functions.sql` (F-051 design §4) | Verificación: `pytest tests/test_f118_sql.py -k funciones` en verde
- [ ] T10: Añadir `es_relleno` y `es_deshacer` a `stg.plan_mensual` en `sql/stg/01_ddl.sql` | Verificación: `pytest tests/test_f118_sql.py -k ddl` en verde
- [ ] T11: Reescribir la rama de reales de `sql/stg/08_plan_mensual.sql` (design §5, pasos 1–9) y su cabecera, y el `INSERT` con las dos columnas | Verificación: `pytest tests/test_f118_sql.py -k stg` y `tests/test_f042_sql.py::test_f042_ninguna_ventana_del_fichero_cruza_obras` en verde
- [ ] T12: Reescribir los tests de F-042 que fijaban `orden_fase`/`reales_con_lag` contra la estructura nueva, citando en el informe cada uno y su sustituto | Verificación: `pytest tests/test_f042_sql.py tests/test_f042_huella.py` en verde
- [ ] T13: `FICHEROS_DEL_SELLO` += `00_functions.sql` y ajuste de los tests de F-025 que fijan la lista | Verificación: `pytest tests/test_f025_*.py tests/test_f118_sql.py -k sello` en verde
- [ ] T14: `sql_huella_propuesta` lee `reales_final` | Verificación: `pytest tests/test_f042_huella.py tests/test_f025_huella.py` en verde
- [ ] T15: Telescopio de `check-cierres` sin apartados y contra el último cierre de la obra (design §7, R37), con `domain/cierres.py` y `tests/test_f042_check_cierres.py` al día | Verificación: `pytest tests/test_f042_check_cierres.py tests/test_f118_check.py -k telescopio` en verde tras verlo en rojo (RED)

## Bloque D · `mart` y `cierre` (mes, relleno, deshacer)

- [ ] T16: Ampliar `test_f118_sql.py` con `mart` y `cierre` (ARRAY en las ramas 1–2 de `mart/02`, `es_relleno`/`es_deshacer` en `mart/01` y `v_pbi_fact`, `cierre/02` y `04` agrupando por `pm.anio_mes`, la vista sin `nombre_mes` en `GROUP BY` ni `JOIN`, y R38 si D5 = arrastrar) | Verificación: `pytest tests/test_f118_sql.py -k "mart or cierre or vista"` **falla** (RED)
- [ ] T17: Cambiar `sql/mart/01_ddl.sql`, `02_build_fact.sql` y `05_views_powerbi.sql` | Verificación: `pytest tests/test_f118_sql.py -k mart tests/test_f019_t13_portabilidad.py tests/test_f078_sql.py` en verde
- [ ] T18: Envolver `cierre.fn_mes_de_fase` sobre la de `stg` y cambiar `cierre/01_ddl_fact.sql`, `02_build_fact.sql` (mes y, si D5, R38) y `04_views_detalle.sql` | Verificación: `pytest tests/test_f118_sql.py -k cierre` en verde
- [ ] T19: Blindar `sql/cierre/06_views_planif_vs_real.sql` (F-051 design §6) | Verificación: `pytest tests/test_f118_sql.py -k vista` en verde

## Bloque E · La venta final (fallo 2), SOLO con D6 decidida (si no, D8: se parte)

- [ ] T20: Escribir `tests/test_f118_coeficientes.py`: la venta final y el ejecutado usan la misma base según D6 (A: `pres.importe` en `final_master` y `final_fase0` de VENTA; B: coeficiente por partida en `ejecutado_concepto`, con oráculo en `domain/coeficientes.py`) | Verificación: `pytest tests/test_f118_coeficientes.py` **falla** (RED)
- [ ] T21: Cambiar `sql/cierre/02_build_fact.sql` (design §6, fallo 2) y su cabecera | Verificación: `pytest tests/test_f118_coeficientes.py` en verde

## Bloque F · Diccionario, documentación y comprobación en la base

- [ ] T22: Comando `python main.py check-mes-fase` (solo lectura; F-051 design §8, más: ninguna fila `es_deshacer` con movimiento 0 y ninguna en mes de relleno; `--obras-esperadas CSV`), con tests offline (mock de Postgres) | Verificación: `pytest tests/test_f118_check.py` en verde
- [ ] T23: Diccionario `stg`, `mart`, `cierre` y `00_global` (`version` +1) según design §8, sin «estorno» en lo nuevo o tocado (test) | Verificación: `pytest tests/test_f006_*.py tests/test_f118_sql.py -k diccionario` en verde
- [ ] T24: `docs/ARCHITECTURE.md`: viñetas «El mes de un cierre real lo da su texto» y «La serie real es densa: lo que desaparece se deshace» | Verificación: revisión del reviewer contra R1–R38
- [ ] T25: Huellas ANTES sobre la base actual: `python main.py huella-obras --desde stg --out huella_f118_stg_antes.csv` (y `mart`, `cierre`) | Verificación: MANUAL (humano), solo lectura
- [ ] T26: Crear SOLO las dos funciones de `stg` en Azure (escritura aditiva, la autoriza el humano) y `python main.py huella-obras --desde stg --propuesta --out huella_f118_stg_propuesta.csv`; medir el tramo más pesado | Verificación: MANUAL (humano)
- [ ] T27: Avisar a Juan Romero con las listas de `progress/spec_F-118.md` §2 y §8 D9 (meses cerrados que cambian, desapariciones masivas, 0606) antes de desplegar | Verificación: MANUAL (humano)
- [ ] T28: Desplegar y reconstrucción completa; huellas DESPUÉS y `comparar-huellas` con la lista esperada de `progress/spec_F-118.md` §6; `check-unicidad` (vista en OK; fact con `--timeout 300`), `check-cierres` (0 series rotas), `check-mes-fase` y los testigos de design §9 y de F-051 §8 | Verificación: MANUAL (humano), resultados en `progress/impl_F-118.md`
- [ ] T29: Cuadrar el cierre de agosto de 2026 de las 12 obras del correo y la 0709 contra la hoja de cierre de agosto de Juan (R45, D7), sin versionar la hoja | Verificación: MANUAL (humano), tabla obra a obra en `progress/impl_F-118.md`
- [ ] T30: `publicar-diccionario` y `apply-grants` contra Azure tras el despliegue | Verificación: MANUAL (humano), `python main.py check-diccionario` sin diferencias
- [ ] T31: Ejecutar `bash harness/init.sh` en verde | Verificación: `bash harness/init.sh` sale con código 0
