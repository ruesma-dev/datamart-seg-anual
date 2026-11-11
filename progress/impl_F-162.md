<!-- progress/impl_F-162.md -->
# F-162 · Informe del implementer · el seguimiento lleva TODAS las fichas de obra

Rama `feature/F-162-obra-duplicada-ruesma` (desde `cd81ea6`), worktree
`agent-aafca17a47111efe6`, sin `.env`. Rigor `estandar`. Decisiones del humano
en la PARADA 1 (2026-11-11, «ok a d1 a d5»): D1 a D5 del design §8.

## Qué cambió

| Tarea | Commit | Qué |
|---|---|---|
| T1 | `0ee7c93` | `tests/test_f162_fichas_por_empresa.py` (R1-R21) y `tests/test_f162_sandbox.py` (R23), en RED |
| T2 | `05fb5c1` | `etl_sigrid/domain/ficha_obra.py`: el oráculo puro `FichaObra`, `clave_por_defecto` y `ficha_por_defecto` |
| T3 | `b0fad62` | `stg/01_ddl.sql`: `empresa_id`, `clave_obra` y `es_por_defecto` tras `_built_at`, más la migración idempotente en el `DO` y el índice `(empresa_id, codigo_obra)` |
| T4 | `c25df3e` | `stg/03_obras.sql`: todas las fichas, con CTE `dudosas`/`lineas` y `es_por_defecto` por `ROW_NUMBER` (Ruesma, líneas, `tiemod DESC NULLS LAST`, `ide DESC`). Sin `conext` (D2) |
| T5 | `3c501cc` | Fuera, con su motivo escrito en el propio test, las guardas del desempate: f102 r7 (hash) y r18, y f073 r26 |
| T6 | `5ec286b` | `maestro.obras.es_por_defecto` como última columna: `COALESCE(stg.obras.es_por_defecto, es_ficha_principal)` (D1). Comentarios de `00_setup.sql` |
| T7 | `93a3b65` | `mart.v_pbi_dim_obra` (`obra_label` = `clave_obra · nombre`, D3) y `cierre.v_pbi_cierre_cabecera`, con las tres columnas al final |
| T8 | `f0c84ac`, `f9ce66f`, `820c052` | `main.py`: `_obra_de_stg` (clave o código) en los seis `inspect-*`. Avisa en amarillo de las otras fichas y sale con 2 si no encuentra la obra. `find-obra` muestra `emp`, `clave_obra` y la marca `*`. Tests de CLI con un PostgreSQL falso |
| T9 | `0a79888` | Diccionario v76: fichas de stg, maestro, mart, cierre y personal; reglas R-EMPRESA-POR-DEFECTO (D4), R-UNIVERSO-OBRA y R-CODIGO-POR-EMPRESA; preguntas P4, P6, P7, P9, P10, P11 y P14 |
| T10 | `e9069bd` | `config/cobertura_excepciones.yaml` sin la sección 3 (F-053); `EXCEPCIONES_MAX` 23 → 19 |
| T11 | `c92717b` | `docs/ARCHITECTURE.md`. En `azure-apps/datamart_seg_anual.md`, commit local `f2cd5eb` tras `git pull`, **sin push** |
| R21 | `498d20d` | `features.json`: F-053 con nota «absorbida por F-162», en `pending`; F-106 con el punto (1) y acceptance[0] enmendados (design §8), también en `pending`. BACKLOG regenerado |

En total son 25 ficheros, +1.792 y −329 líneas: `git diff --stat cd81ea6..HEAD`.

## Decisiones de diseño y desviaciones (justificadas)

1. **`dudosas` usa `count(*) FILTER (WHERE empresa_id = 1) <> 1`**, no `= 0`. Solo cuentan líneas de `obrparpre` los códigos con varias fichas en los que Ruesma no decide sola. Con 0 fichas de Ruesma decide el número de líneas. Con 2 o más, el desempate entre ellas también pasa por las líneas, y así el SQL da lo mismo que el oráculo `ficha_por_defecto`. Si `dudosas` solo cogiera los códigos sin Ruesma, con dos fichas de empresa 1 el SQL desempataría por `tiemod` y el oráculo por líneas. Hoy no hay ningún caso, pero el test `r6` lo fija. El coste no cambia: hoy no hay ningún código con dos fichas de Ruesma.
2. **Guardas extra adaptadas** que el design no listaba, sin relajarlas:
   - `test_f102_r8`: su lista exacta de columnas de `maestro.obras` crece con `COLUMNAS_OBRAS_F162 = ("es_por_defecto",)`.
   - `test_f108` declara las claves alternativas de `stg.obras`.
   - `test_f052_cobertura` ahora exige que los cuatro códigos de F-053 **no** estén.
   - `test_f052_cierre_excepciones` saca la 0606 de la línea base, con su comentario.
3. **F-106:** se enmienda también su `acceptance[0]`, citando el texto original, porque el original pedía lo que D5 descarta. F-053 y F-106 siguen `pending`: cambiar su estado le toca al líder.
4. **`main.py` fuera de alcance:** `inspect-contrato-consumo`, `proveedores-obra`, `albaranes-sin-facturar`, `retenciones` y `retenciones-vencidas` siguen filtrando por `codigo_obra` sobre vistas de compras y retenciones. La obra ya la resuelven por ficha, pero esas vistas no llevan `obra_id` en todos los casos. Eso es F-106 (enmendada) y no se toca aquí.
5. **T3:** el test `-k r3` del `INSERT` nombra siete columnas, así que solo podía pasar tras T4. El RED de `r3_create_table` fue primero un fallo de parseo del propio test, corregido en T3 con `_entre_parentesis`. El RED real de R3 son los tests de la migración y del índice (traza abajo).
6. **Guarda f102 r7 (stg no lee `maestro.v_obra_fichas`):** se queda viva. Los comentarios de `01_ddl.sql` y `03_obras.sql` se redactaron sin nombrar la vista.
7. **El criterio vive dos veces**, en el oráculo Python y en el SQL. Lo atan los tests `r5`/`r6` y la sandbox R23, que compara el SQL real con el oráculo en 9 casos.

## Fase RED (trazas reales)

**Tests de F-162 sobre `cd81ea6`, antes de cualquier código** (T1):

```
$ .venv/Scripts/python.exe -m pytest tests/test_f162_fichas_por_empresa.py -q -rf
FAILED ...::test_f162_r1_sin_desempate - AssertionError: stg.obras ya no se queda con una ficha (R1)
FAILED ...::test_f162_r2_cada_ficha_sale_con_su_empresa
FAILED ...::test_f162_r3_la_migracion_las_anade_en_el_mismo_orden
FAILED ...::test_f162_r3_indice_por_empresa_y_codigo_tras_la_migracion
FAILED ...::test_f162_r5_oraculo_de_la_ficha_por_defecto[ruesma_gana_a_todo]
...
83 failed, 6 passed in 30.18s
```

Detalle de los motivos (selección `-k` de un caso por requisito):

```
E   AssertionError: stg.obras ya no se queda con una ficha (R1)
E   AssertionError: el SELECT final lee TODAS las fichas; las líneas por LEFT JOIN (R2)
E   AssertionError: ['obra_id', 'codigo_obra']
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.ficha_obra'
E   AssertionError: assert ['obra_id', '...ha_baja', ...] == ['obra_id', '...ha_baja', ...]
E   AssertionError: D3: clave_obra · nombre, distingue las fichas de un código
E   ImportError: cannot import name '_obra_de_stg' from 'main'
E   AssertionError: assert '`es_por_defecto`' in 'Sin empresa en la pregunta, filtra `empresa_id = 1` (Construcciones Ruesma) y dilo. ...
E   AssertionError: ya no deduplica por conext 15 (R14)
E   assert 75 >= 76
E   assert 23 == 19
13 failed, 76 deselected in 2.14s
```

Los 6 que pasaban en RED son guardas de lo que **no** debe cambiar: filtros de hoy, `obr`⋈`con`, la clave de negocio, etc.

**Sandbox R23 contra un PostgreSQL 16 desechable** (`initdb` en el scratchpad, puerto 55462, sin datos reales):

Con el DDL y el `03_obras.sql` VIEJOS:

```
$ F162_SANDBOX_DSN=... .venv/Scripts/python.exe -m pytest tests/test_f162_sandbox.py -q
E   psycopg.errors.UndefinedColumn: column "empresa_id" does not exist   (x8)
9 failed in 1.80s
```

Con el DDL nuevo y el `03_obras.sql` VIEJO, es decir, el desempate de hoy con las columnas puestas:

```
E   assert [901, 911, 922, 931, 2855829] == [901, 902, 91...921, 922, ...]
E   KeyError: 2759553        <- el SQL viejo se queda la 0721 de PORSAN y pierde la de Ruesma
E   assert [] == [901]
E   AssertionError: assert 0 == 5
8 failed, 1 passed in 1.61s
```

Ya en verde, con el código nuevo y el mismo cluster: `9 passed`. El cluster está parado y no se versiona.

## Verde

- Los tests de F-162 (`tests/test_f162_fichas_por_empresa.py`, unos 110) pasan, igual que los afectados: f102, f073, f108, f052, f144, f147 y f006. `pytest -k "r12 or r5"` da 42 passed, y `tests/test_f006_contexto.py` da 21 passed tras actualizar los recuentos en `current.md`.
- `ruff check` sin errores en los ficheros tocados.
- **Suite ENTERA sin `-x`**, con `SIGRID_API_BASE_URL=http://ficticio.invalid SIGRID_API_FUNCTION_KEY=ficticia` (valores ficticios, como F-040):
  `1 failed, 11161 passed, 2482 skipped, 2748 warnings in 2935.17s (0:48:55)`, con cobertura.
  El único fallo fue `test_f006_los_recuentos_de_current_son_los_de_hoy`: `current.md` no decía aún los recuentos del diccionario v76. **Ya está corregido** (316 objetos, 2664 columnas, 153 de consumo) y su fichero da 21 passed.
- **Sin entorno ninguno** (el worktree sin `.env`) la suite da 117 fallos. Todos son de entorno: con los valores ficticios caen a ese único fallo, ya resuelto. Es la línea base de `scratchpad/baseline.txt`, con el mismo patrón que antes del cambio.

## `bash harness/init.sh` (resultado real)

**ROJO, por el `.env` del worktree, como estaba previsto.** No lo he arreglado: el encargo dice «dilo, no lo arregles». Salida real, exit 1, «3 comprobaciones fallidas»:

```
[KO] Falta .env — copiar de .env.example
FAILED tests/test_f006_comandos.py::test_f006_t26_cli_dry_run_no_toca_la_base
  (2 validation errors for SigridApiSettings: base_url / function_key  Field required)
!!! stopping after 1 failures !!!   1 failed, 256 passed in 418.11s
[KO] pytest en rojo
[KO] PUERTA COBERTURA: 30.6% de 49 líneas (15/49) — la suite paró en el test 257
[OK] PUERTA TAMAÑO: F-162 dentro de los topes (requirements 120/150, design 250/250, impl 137/220)
[OK] Rama actual: feature/F-162-obra-duplicada-ruesma
```

Los tres KO vienen del `.env`. Sin él, `SigridApiSettings` no carga y la puerta corta la suite con `-x` en el 257. Así la cobertura sale con 256 tests, y por eso da 30,6 %. Con valores ficticios la suite entera da el resultado de arriba, y la cobertura de lo cambiado llega al 100 %. **El líder tiene que pasar la puerta en la copia con `.env`** (T15).

## MANUAL pendiente (líder o humano)

1. **T12 · sandbox con DSN** en la copia con `.env`: `F162_SANDBOX_DSN=<dsn local> .venv/Scripts/python.exe -m pytest tests/test_f162_sandbox.py`. Aquí se pasó en un cluster desechable (9 passed); falta en el Postgres local del puesto, sin `skip`.
2. **`EXPLAIN (ANALYZE, BUFFERS)` en solo lectura en Azure** del `SELECT` de `03_obras.sql`, desde `WITH fichas AS` hasta el final. Está preparado en `<scratchpad del líder>/explain_f162.sql`. Envuelto en `BEGIN READ ONLY; ... ROLLBACK;`. Se espera un coste de +0 s a +48 s (design §6).
3. **T13 · medición ANTES** (design §7, paso 0): cuatro CSV `antes_*` y el recuento por ficha.
4. **T14 · despliegue** (design §7, pasos 1-10) y su vuelta atrás. Lo que se espera: 634 fichas, 585 por defecto y las huellas de las 585 de hoy sin cambio.
5. **Campaña oficial de mutación:** `python -m harness.mutacion --feature F-162 --base main` → `progress/mutacion_F-162.md`. Aquí no se pudo: con workers > 1 crea worktrees de git (prohibido en este encargo), y en serie la línea base pasa del timeout de 600 s, como en F-040.
6. **`check-cobertura`** tras el despliegue: confirmar que las 4 excepciones retiradas (0581, 0606, 0671, 0720) no disparan.
7. **Push de `azure-apps`** (`f2cd5eb`) cuando el humano lo autorice.
8. **Republicar el diccionario v76** solo con la imagen nueva del job: la nocturna republica el de su imagen.

## Fuera del alcance

- Llevar la empresa a las tablas de hechos (D5: se cruza por `obra_id` con `maestro.obras`).
- Los cinco comandos de compras y retenciones (punto 4 de las desviaciones): son F-106.
- El master de la 0721: le falta `planif`, así que depende de F-161.
- `conext` 15 (D2).

## Evidencias

| Evidencia | Valor real |
|---|---|
| Tests ejecutados (suite entera, entorno ficticio) | 11.161 passed, 2.482 skipped, 1 failed, ya corregido (`current.md`); tras el arreglo, `test_f006_contexto.py` da 21 passed |
| Tests propios de F-162 | ~110 en `test_f162_fichas_por_empresa.py` + 9 de sandbox (9 passed en un PG16 desechable) |
| Cobertura de las líneas cambiadas | **100 % (49/49)** sobre `main.py` y `etl_sigrid/domain/ficha_obra.py`, medida con la suite y `harness.alcance`. Antes de los tests de CLI de T8 era 71,4 % (35/49); el umbral es 80 % |
| Mutación | Campaña oficial **pendiente del líder** (MANUAL 5). Alcance: 2 ficheros, 140 líneas, 42 mutantes (12 en `ficha_obra.py` y 30 en `main.py`). Pre-análisis no oficial con los tests de f162 y f102: 41 de 42 muertos |
| Superviviente del pre-análisis | `ficha_obra.py:57`, `else 1` → `else 2`. **Equivalente**: solo importa que Ruesma (0) vaya antes que el resto, y 1 o 2 ordenan igual |
| Tiempo de la suite | 2935 s (48 min 55 s), en serie y con cobertura; `pytest-xdist` no está instalado |
