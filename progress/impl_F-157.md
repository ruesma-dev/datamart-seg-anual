<!-- progress/impl_F-157.md -->
# F-157 · Informe del implementer · la fase 0 repartida en el tiempo

Rama `feature/F-157-planificacion-fase0` (worktree del agente), rigor `estandar`. Spec aprobada
por el humano: la A en D1 a D8. `main` (`da6c36f`, F-156 y F-158 en `done`) traído a la rama en
`7569cb9`; F-157 pasa a `in_progress` y el diccionario a la **v73** (no a la 72 de la spec).

## Qué cambió (un commit por tarea)

| Tarea | Commit | Qué |
|---|---|---|
| merge | `7569cb9` | `main` a la rama; conflicto de `current.md` resuelto; F-157 `in_progress`, backlog regenerado |
| T1 | `21672ad` | RED de `test_f157_dominio.py`, `test_f157_sql.py`, `test_f157_step.py` |
| T2 | `e90e42e` | oráculo `etl_sigrid/domain/planif.py` (`PosicionPlanif`, `explotar_planif`, `conservar`) |
| T3 | `a4ec057` | `stg.fn_explotar_planif` al final de `00_functions.sql`; constante del marcador F157 |
| T4 | `d547718` | DDL de `stg.plan_mensual_fase0` (PK de negocio, `CHECK (3, 7)`, índice `anio_mes`) y vista `stg.v_plan_mensual_fase0_cobertura` en `01_ddl.sql` |
| T5 | `ad6a504` | `sql/stg/09_plan_mensual_fase0.sql` |
| T6 | `b497694` | `build_stg_step.py`: `MARCADOR_FILTRO_FASE0`, `componer_sql_fase0`, sello con el 09, sub-paso `build_plan_mensual_fase0` tras `build_plan_mensual` con su puerta de disco; `TABLAS_ACOTADAS` += `plan_mensual_fase0`; tests fijados al día (F-118, F-025 ×3) |
| T7-T8 | `4503c04` | sin regresión; `tests/test_f157_sandbox.py` |
| T9 | `47edc3e` | fichas (tabla, vista, función), `stg.plan_mensual` corregida, `R-IMPORTE-MES`, v73, enmienda de F-006 (290 objetos), F-079 y `PRESUPUESTO_MAX` |
| T10 | `74adda6` | `docs/ARCHITECTURE.md`, mapa de `CLAUDE.md`; `azure-apps` en `2ba73e3` (local, sin push) |
| T7 (2) | `91536f7`, `d2994db` | dos fallos del diccionario que destapó la suite completa (desviación 11) |

Ficheros de producción: `etl_sigrid/domain/planif.py` (nuevo),
`etl_sigrid/infrastructure/postgres/sql/stg/{00_functions,01_ddl}.sql`,
`.../stg/09_plan_mensual_fase0.sql` (nuevo), `etl_sigrid/application/steps/build_stg_step.py`,
`etl_sigrid/infrastructure/postgres/postgres_client.py` (solo la tupla y su comentario).
Diccionario: `config/diccionario/stg.yaml`, `00_global.yaml`. Documentación: ARCHITECTURE,
CLAUDE.md, `specs/F-006-mcp-azure/design_detalle.md`, `../azure-apps/datamart_seg_anual.md`.

## Decisiones de diseño y desviaciones (justificadas)

1. **Redacción (corrección del humano).** La ficha abre con «El presupuesto vivo de hoy (fase 0),
   repartido en el tiempo», dice que la fase 0 ES el coste y la venta de hoy, que NO se suma ni se
   une con `stg.plan_mensual` (cierres, fases 1 a N = Coste/Venta Real de `mart`; y el master) y
   que se COMPARA con ellos. Lo vigila `test_f157_r23_no_dice_que_no_sea_real` (también en
   ARCHITECTURE). Igual en `azure-apps`.
2. **R18 sin test de `git diff`.** Un test permanente contra `fbf43dd` prohibiría a cualquier
   feature futura cambiar `mart/` o `cierre/`. El 08 ya lo fija el sha256 de `test_f073_sql.py`;
   el diff de T7 se ha hecho a mano (abajo). `tesoreria/` sí cambió respecto a `fbf43dd`, pero por
   F-158 (ya en `main`): el diff de T7 se mide contra `main` y sale vacío.
3. **Puerta de disco no extraída a un helper común.** La de los tramos registra el FAILED de su
   tramo y lista obras hechas; compartirla tocaba la conducta de F-019. La del sub-paso nuevo lanza
   `PlanMensualAbortado` con el mismo texto y el bucle de `run` deja la fila en FAILED (design § 6
   lo dejaba a criterio: «si sale limpio»).
4. **El oráculo redondea a 6 decimales** (`ROUND_HALF_UP`, como el cast `NUMERIC(18,6)` del regex)
   antes de decidir si un valor es positivo: así casa con el SQL también con más de 6 decimales
   (la sandbox lo prueba con 500 `planif` aleatorios de 0 a 7 decimales). Design § 4 bis decía
   «sin redondeos»; es más fiel así.
5. **Filtro de `plafec` inválido** en el 09 (`fn_sigrid_date_to_date(plafec) IS NOT NULL`), como el
   master (`fa.plafec_date IS NOT NULL`): sin él, un `plafec` no fecha violaría el `NOT NULL` de
   `anio_mes` y tumbaría `build_stg`.
6. **La vista de cobertura une por la PK** (`LEFT JOIN LATERAL ... LIMIT 1` por `(obra_id,
   ambito_id, partida_id)`) en vez de agregar la tabla entera por `presupuesto_id`: filtrar la
   vista por obra no barre 1,25 M de filas. Equivale porque `stg.presupuesto` tiene una fila por
   (obra, partida, ámbito, fase).
7. **Tres tocados fuera de la lista del design § 3**, todos por las puertas del diccionario:
   ficha de `stg.fn_explotar_planif` (la cobertura de F-006 exige ficha a toda función publicada),
   su entrada en `GRUPO_B_FUNCIONES` de `test_f079_stg_consultable.py`, y la enmienda del recuento
   en `design_detalle.md` de F-006 (`test_f006_r24`: 287 → 290 objetos).
8. **`PRESUPUESTO_MAX` 34.056 → 34.253** (+197 de enrutado: dos fichas recomendadas, tres
   preguntas ya acortadas), con su motivo en la historia del test (convención F-147).
9. **Nulos.** Las columnas copian el `NOT NULL` de sus homónimas de `plan_mensual`; una partida de
   fase 0 con `can` o `pre` nulos haría fallar el sub-paso (la rama master tiene el mismo
   contrato y nunca ha fallado). `importe_partida` admite NULL. Riesgo anotado para el paso 2.
10. **`init.sh` se lanzó redirigiendo a un log** del scratchpad para poder leerlo (la salida es de
    ~20 min); el comando en sí, `bash harness/init.sh`, sin cambios.
11. **La suite completa destapó tres fallos MÍOS** que las suites acotadas no veían, ya corregidos:
    la relación de la tabla hacia la vista de cobertura declaraba `N:1` y la vista tiene una fila
    por `(obra_id, ambito_id)` (R5 de F-006: pasa a `N:N`, «se une por las dos columnas»);
    `pct_acumulado`/`pct_mes` iban con agregación distinta de `stg.plan_mensual` dentro de
    `R-IMPORTE-MES` y uno como sumable (R10: ahora `promedio`, como allí); y `current.md` no decía
    el recuento real (ahora «v73, 290 objetos, 2485 columnas, 139 de consumo»).

## Fase RED (trazas reales)

`<PY>` = `C:/Users/pgris/PycharmProjects/datamart-seg-anual/.venv/Scripts/python.exe`.

T1, antes de cualquier código: `<PY> -m pytest tests/test_f157_dominio.py tests/test_f157_sql.py tests/test_f157_step.py -q -p no:cacheprovider`
```
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.planif'
E   ImportError: cannot import name 'MARCADOR_FILTRO_FASE0' from 'etl_sigrid.application.steps.build_stg_step'
!!!!!!!!!!!!!!!!!!! Interrupted: 3 errors during collection !!!!!!!!!!!!!!!!!!!
```
T3-T5 (SQL), con solo la constante del marcador ya escrita: `<PY> -m pytest tests/test_f157_sql.py -q -p no:cacheprovider -rf`
```
FAILED tests/test_f157_sql.py::test_f157_r8_funcion_firma - ValueError: subst...
FAILED tests/test_f157_sql.py::test_f157_r5_funcion_mismo_case_que_el_master
FAILED tests/test_f157_sql.py::test_f157_r5_funcion_mismo_regex_que_el_master
FAILED tests/test_f157_sql.py::test_f157_r1_clave_primaria_de_negocio_y_check_de_ambito
FAILED tests/test_f157_sql.py::test_f157_r13_marcador_una_vez_dentro_de_un_any
FAILED tests/test_f157_sql.py::test_f157_r6_mismo_descarte_que_el_master - Fi...
FAILED tests/test_f157_sql.py::test_f157_r16_el_09_entra_en_el_sello_tras_el_08
FAILED tests/test_f157_sql.py::test_f157_r16_tabla_acotada - AssertionError: ...
46 failed, 3 passed in 8.93s
```
T6 (step), con `componer_sql_fase0` ya escrita y el sub-paso aún no: `<PY> -m pytest tests/test_f157_step.py -q -p no:cacheprovider`
```
FAILED tests/test_f157_step.py::test_f157_r12_va_despues_de_plan_mensual_y_es_el_ultimo
FAILED tests/test_f157_step.py::test_f157_r12_r13_una_sola_pasada_borra_e_inserta_las_obras_del_plan
FAILED tests/test_f157_step.py::test_f157_r12_el_domingo_entran_todas - Index...
FAILED tests/test_f157_step.py::test_f157_r14_plan_sin_obras_no_toca_la_tabla
FAILED tests/test_f157_step.py::test_f157_r15_disco_por_encima_del_limite_para_sin_escribir
FAILED tests/test_f157_step.py::test_f157_r15_disco_sin_medir_para_sin_escribir
FAILED tests/test_f157_step.py::test_f157_r17_registra_las_filas_de_la_tabla
7 failed, 6 passed, 8 warnings in 8.83s
```
T9 (diccionario), antes de las fichas: `<PY> -m pytest tests/test_f157_diccionario.py -q -p no:cacheprovider`
```
FAILED tests/test_f157_diccionario.py::test_f157_r23_es_el_presupuesto_vivo_de_hoy_repartido_en_el_tiempo
FAILED tests/test_f157_diccionario.py::test_f157_r23_no_se_suma_con_los_cierres_ni_con_el_master_y_se_compara
FAILED tests/test_f157_diccionario.py::test_f157_r24_plan_mensual_ya_no_dice_que_guarda_la_fase_0
FAILED tests/test_f157_diccionario.py::test_f157_r24_r_importe_mes_la_incluye
FAILED tests/test_f157_diccionario.py::test_f157_r24_la_version_sube_a_la_73
FAILED tests/test_f157_diccionario.py::test_f157_r27_architecture_describe_la_fase_0
13 failed in 2.02s
```
Todas en verde después (ver «Evidencias»).

## Sandbox SQL (T8)

PostgreSQL 16 local desechable (el contenedor Docker `f155pg` del puesto, `localhost:55155`); el
fixture crea una base `f157_sandbox_<uuid>` y la borra. Carga `00_functions.sql` y `01_ddl.sql`
reales, un `raw` con los tipos de la ingesta, y ejecuta el 08 y el 09 compuestos como el step.
`F157_SANDBOX_DSN=postgresql://postgres:***@localhost:55155/postgres <PY> -m pytest tests/test_f157_sandbox.py -q -p no:cacheprovider`
```
24 passed in 9.36s
```
Sin DSN: `24 skipped in 5.33s`. Lo que prueba: la función = el oráculo en 17 casos y en 500
`planif` aleatorios (semilla 157); **el 08 (master, ámbito 8) y el 09 (ámbito 7) sobre los mismos
73 `planif`, cantidad, precio y decimales dan las mismas filas** (posición, %, cantidades, los
cuatro importes y `anio_mes`; más de 200 filas) — es R22 en sintético; solo fase 0 de venta con
`plafec`; la fila de `obrfasamb` de `ide` mayor; meses desde `plafec`; cobertura (60/20/40 €); el
borrado derivado idempotente y sin tocar otras obras.

## Sin regresión (T7)

`git diff main --stat -- .../sql/stg/08_plan_mensual.sql .../sql/mart .../sql/cierre .../sql/tesoreria .../sql/retenciones .../sql/maestro` → **sin salida**.
`test_f073_sql.py` (sha256 del 08) y `test_f042_sql.py` en verde en la suite completa.

## Lo que queda fuera y lo que falta

- **Fuera (D6, D8):** ámbitos 5, 12 y 13; escenarios nuevos en `mart`; pasar el master a la
  función (D2 = C). `stg.plan_mensual` y su 08 no se tocan.
- **MANUAL tras APROBADO y merge (T12, design § 12, en SÁBADO):** imagen y job; primera noche
  completa; huella antes/después (R20); `check-cierres`, `check-unicidad`, `check-declarados`
  (R21); R22 real contra los `planif` master de 0696, 0677 y 0705; cifras de la 0726 y totales
  (R25, R26); `publicar-diccionario` (v73) y reinicio del MCP; cuadre con la pantalla de Sigrid
  por Control de Costes en la 0726 y en una obra con `plamed = 2`. No he leído nada de Azure: el
  worktree no tiene `.env` y no hacía falta.
- **La puerta completa de `init.sh`** en una copia con `.env` (la pasa el líder).

## Evidencias

| Evidencia | Valor real |
|---|---|
| `bash harness/init.sh` en el worktree | **ROJO solo por el `.env`**: `[KO] Falta .env` y `FAILED tests/test_f006_comandos.py::test_f006_t26_cli_dry_run_no_toca_la_base` (`SigridApiSettings`: falta `base_url`, `function_key`); `1 failed, 256 passed ... in 1158.78s`; para con `-x`, así que no llega a cobertura ni tamaño |
| Suite completa sin `-x` (`pytest tests -q -rfE`, tras los arreglos de la desviación 11) | `112 failed, 10498 passed, 369 skipped`. Los 112 son **todos** por el `.env`: 112 trazas `validation errors for SigridApiSettings` (falta `base_url`, `function_key`), en tests que arrancan el CLI de `main.py` (F-006 comandos/reglas r9, F-024, F-025 cli/huella, F-042, F-047, F-052, F-066, F-067, F-078, F-108, F-118 check, F-132). Ningún otro rojo |
| Tests de F-157 | 121: dominio 22, SQL 49, step 13, diccionario 13, sandbox 24 (con DSN) |
| Afectados (`build_stg`, sello, `TABLAS_ACOTADAS`, F-019, F-025, F-042, F-073, F-118) | `391 passed` + F-025 build `43 passed` tras fijar los pins |
| Diccionario (F-157, F-079, F-147, F-006 cobertura) | `149 passed` + 1 fallo de presupuesto, corregido: `27 passed` (F-147 + F-157) |
| Cobertura de líneas cambiadas | `PUERTA COBERTURA: 100.0% de 71 líneas cambiadas cubiertas (71/71, umbral 80%, nivel estandar; diff desde da6c36f6ea)`. Medida con `coverage run` sobre los tests de F-157 y los afectados (388 passed, sandbox encendida; `COVERAGE_FILE` aparte): la suite entera bajo coverage iba a tardar más de 4 h |
| Tamaño (`harness.tamano --feature F-157`) | `PUERTA TAMAÑO: F-157 dentro de los topes (requirements 132/150, design 250/250, impl 192/220)` (antes de esta última edición) |
| Tiempo de la suite | `2393.53s (0:39:53)` sin coverage |

**Mutación (manual, suite acotada).** `python -m harness.mutacion` no puede arrancar aquí: su
línea base corre la suite entera (~20 min por worker) y sale ROJA por el `.env` (la misma razón
que F-158). Campaña manual de **21 mutantes** (script `scratchpad/f157_impl/mutar.py`): cada uno
un cambio textual, suite `test_f157_{dominio,sql,step,sandbox}.py` con `-x` y sandbox encendida;
fichero restaurado tras cada uno (`git status` limpio al terminar). 376,7 s. **20 muertos, 1
superviviente.** Sus números no son comparables con una campaña del arnés.

| Mutante | Resultado | Lo caza |
|---|---|---|
| D1 positivo `> 0` → `>= 0` | muerto | `r9_0677_cero_final_arrastra` |
| D2 estorno `any` → `all` | muerto | `r9_0696_cero_intermedio_es_estorno` |
| D3 mirar posteriores desde `indice` (incluida la actual) | **superviviente** | — |
| D4 arrastrar el máximo y no el último positivo | muerto | `r9_p4_03_06_sobrepaso` |
| D5 `pct_mes` sin restar el anterior | muerto | `r9_0726_arranque_tardio` |
| D6 `anterior` no avanza | muerto | `r9_0726_arranque_tardio` |
| D7 renumerar los huecos | muerto | `r5_un_hueco_intermedio_no_renumera` |
| D8 tope `<= 2.5` → `< 2.5` | muerto | `r6_conservar` |
| D9 `conservar`: `and` → `or` | muerto | `r6_conservar` |
| S1 marcador `!=` → `>` | muerto | `r13_sin_marcador_o_doble_no_se_compone` |
| S2 sin borrado derivado | muerto | `r13_compone_borrado_y_filtro` |
| S3 sin el umbral de disco | muerto | `r15_disco_por_encima_del_limite` |
| S4 plan vacío no corta | muerto | `r14_plan_sin_obras_no_toca_la_tabla` |
| S5 despacho al sub-paso de presupuesto | muerto | `r12_va_despues_de_plan_mensual` |
| F1 función sin arrastre del 0 final | muerto | `r5_funcion_mismo_case_que_el_master` |
| F2 función sin `COALESCE` del `LAG` | muerto | sandbox `r8_funcion_igual_al_oraculo` |
| Q1 09 `ide DESC` → `ASC` | muerto | `r2_r3_..._la_de_ide_mayor` |
| Q2 09 `fase_num = 0` → `>= 0` | muerto | `r2_r3_...` |
| Q3 09 `anio_mes` sin `- 1` | muerto | `r4_mes_de_inicio_y_anio_mes` |
| Q4 09 `importe_partida` = acumulado | muerto | `r7_importe_partida_es_el_de_presupuesto` |
| V1 vista: planificado sin `FILTER` | muerto | sandbox `r11_cobertura` |

**D3 es EQUIVALENTE:** la rama `elif any(...)` solo se alcanza cuando la posición actual NO es
positiva, así que incluirla en la búsqueda de «hay un positivo después» no cambia nada. No es un
hueco.
