<!-- progress/impl_F-040.md -->
# Informe del implementer · F-040 fase 1 (ventas, certificaciones, clientes y cobro)

Rama `feature/F-040-ingresos`, worktree `agent-a110c4068b1c41df8`, 2026-11-09. Rigor `critico`.
Spec: `specs/F-040-ingresos/` (aprobada en la PARADA 1 del 09-11). Sin escrituras en Azure ni en
Sigrid: todo se verificó con tests y con un PostgreSQL 16 local desechable.

## 1. Qué cambió (un commit por tarea)

| Tarea | Commit | Qué |
|---|---|---|
| T1 | `0e12304` | Fase RED: `test_f040_dominio`, `_ingesta`, `_sql` |
| T2 | `7c68c30` | `etl_sigrid/domain/ventas.py`: persona física, CIF válido, clase de recargo (`CLASES_GARANTIA`, el único punto de D4), reparto de recargos y estado del seguimiento |
| T3 | `897922b` | `config/tables_sigrid.yaml`: `cli`, `cer`, `cerpro`, `cerrec`, `cerprodes`, `dvfpro` y `dvfrec` por lista blanca; `dvf` de 9 a 35 columnas; censo de 93 a 100 tablas; fichas de `raw` |
| T4-T9 | `adc9f14` `e80a6f2` `43bd491` `19e45b5` `76818d7` `647cb01` | `sql/ventas/`: `00_setup` (esquemas y funciones) y `01_clientes`; `02_facturas` (líneas y recargos en cuatro columnas); `03_certificaciones` (a cuenta, a origen, `base_origen_contrato`); `04_enlace` y `05_vistas` (cobro, seguimiento, contraste); `06_restringida`; `07_guardas` (cuadre con `raw` y nada personal en `ventas`) |
| T10 | `ca289ea` | `build_ventas_step.py` (ocho sub-pasos); `main.py`: tras `build_retenciones`, diecisiete pasos, `PASOS_CON_PERMISOS`, comando `build-ventas` |
| T11 | `f6889d9` | `settings.py` y `.env.example`: `ventas` en el consumo y `ventas_restringida` en vetados y restringidos; `ESQUEMAS_DEL_DATAMART` de 18 a 20; `00_global.yaml` |
| T12 | `4515ab0` | `infra/sql/02_roles.sql` (esquemas, punto 5, veto del 5 ter, concesión al autorizado, comprobaciones finales) y runbook § 15 |
| T13 | `eecc0fe` | `test_f040_frontera.py` (R30: `sql/retenciones` y `sql/tesoreria` sin diff) |
| T14 | `a851ea1` | Diccionario v75: `ventas.yaml` (16 fichas), `ventas_restringida.yaml` (3), `R-VENTAS-TRES-CIFRAS`, `R-VENTAS-RESTRINGIDA`, `R-PERFILES` y `R-FRESCURA` al día |
| T15 | `549111c` | `ARCHITECTURE.md`, mapa de `CLAUDE.md`; `azure-apps/datamart_seg_anual.md` (commit local `882abce` en `azure-apps`, sin push) |
| T16 | `01f4c9f` y el de este informe | `progress/current.md`, este informe, `tasks.md` |

Pasada 1: 66 ficheros (+6.301/−210): 8 SQL en `sql/ventas/`, 2 módulos Python, 8 `tests/test_f040_*.py` y listas
de otras features (§ 2.9). `sql/retenciones/` y `sql/tesoreria/` **no se tocan** (R30, `test_f040_frontera`).

## 2. Decisiones y desviaciones (justificadas)

1. **Diccionario v75, no v74**: `main` ya publicó la v74 con F-159. Los tests de versión usan
   `>=`; `test_f040_diccionario` fija `VERSION_ANTERIOR = 74`.
2. **Diecisiete pasos** en `run-all`, no dieciséis: F-156 ya añadió el suyo. `build_ventas` va tras
   `build_retenciones`, solo depende de `ingest_raw` y ningún paso depende de él.
3. **Tope de F-147 (presupuesto de contexto del MCP) a 37.042**. La causa son dos reglas duras
   nuevas y el ámbito ampliado de otras dos. Queda en un comentario del test, con el desglose
   (reglas 8.464, enrutado 18.516, bloques 10.062). Mismo precedente que F-156.
4. **Fichas de `raw` ya en T3**: la puerta R25 de F-006 exige ficha o pendiente al declarar la tabla.
5. **Sandbox Postgres extra** (`tests/test_f040_sandbox.py`): el SQL real sobre un PG16 local con los
   tipos de la ingesta; salta sin `F040_SANDBOX_DSN`. No estaba en tasks: defiende de lo solo literal.
6. **Adiciones al dominio** que pide el SQL, para tener un oráculo único: `TIP_CLIENTE`,
   `repartir_recargos`, `ESLABONES_COBERTURA` y los patrones de CIF.
7. **Persona física (R6, con la enmienda del ciclo 2)**: `perfis` <> 0 o CIF normalizado con forma de
   NIF, también con prefijo de país; y la factura sin cliente en `raw.cli`. Solo `perfis` NULL cuenta
   como 0 (el patrón de NIF lo cubre si el CIF es de persona). Ciclo 1 (H2) y § 8.
8. **Obra de la factura**: sale de la cabecera solo cuando la línea no trae centro. Así lo describe
   design § 4.
9. **Tests de otras features al día, solo listas y recuentos**: `f006_formato/_frescura/_publicacion`, `f024`,
   `f037`, `f047`, `f057`, `f066`, `f074`, `f085`, `f090`, `f097`, `f135`, `f138`, `f140`, `f141` (su
   instantánea de `CONSUMO`, autocontenida, se mantiene), `f146`, `f147`, `f148`, `f150`, `f156`.
10. **Inventario de F-006 a 316 objetos**: `design.md` y una enmienda en `design_detalle.md` (de ahí
   lee el test).
11. **`codigo_cliente` (`con.cod`)**: podía publicar un NIF. Resuelto en el código en el ciclo 1
   (H1, § 7), no en el despliegue.

## 3. Verificación real

- **Tests de F-040**: `F040_SANDBOX_DSN=... pytest tests/test_f040_*.py -q -p no:cacheprovider`
  → **2300 passed** en 15,29 s. Son 246 sin red ni base de datos y 2054 contra el PG16 local. Sin
  DSN: `246 passed, 2054 skipped`.
- **`bash harness/init.sh` (T19)** en este worktree: **rojo, solo por el entorno**: `[KO] Falta .env`, y
  pytest se para por `-x` en `test_f006_t26` (`SigridApiSettings`: `base_url` requerido) tras 256
  passed, así que su `PUERTA COBERTURA` (52,0 %, 77/148) no representa el cambio. `PUERTA TAMAÑO` y
  rama OK. Crear `.env` aquí está prohibido: la puerta completa es del líder.
- **Cobertura de las líneas cambiadas**, aparte: `coverage run -m pytest <los 31 ficheros de test
  que toca la rama>` con la sandbox y `harness.cobertura --base main` → **`PUERTA COBERTURA: 100.0% de
  148 líneas cambiadas cubiertas (148/148, umbral 80%, nivel critico)`** (3638 passed, 6 skipped, 1
  failed en 554,63 s; con la suite entera solo puede subir). Fallos de entorno, que piden `.env` y no
  tocan F-040: `test_f006_t26` y `test_f024_r19` (`check-frescura --help` pasa por `get_settings`).

## 4. Fase RED (comandos y salida real, recortada)

**T1, dominio, ingesta y SQL** (antes de `etl_sigrid/domain/ventas.py`):
```
$ .venv/Scripts/python.exe -m pytest tests/test_f040_dominio.py tests/test_f040_ingesta.py tests/test_f040_sql.py -q -p no:cacheprovider
_________________ ERROR collecting tests/test_f040_dominio.py _________________
tests\test_f040_dominio.py:19: in <module>
    from etl_sigrid.domain import ventas as v
E   ImportError: cannot import name 'ventas' from 'etl_sigrid.domain'
_________________ ERROR collecting tests/test_f040_ingesta.py _________________
ERROR tests/test_f040_sql.py
!!!!!!!!!!!!!!!!!!! Interrupted: 3 errors during collection !!!!!!!!!!!!!!!!!!!
3 errors in 2.18s
```
**T10, paso del pipeline** (antes de `build_ventas_step.py`):
```
$ .venv/Scripts/python.exe -m pytest tests/test_f040_pipeline.py -q -p no:cacheprovider
FFFFFFFFFF.FFFF.                                                         [100%]
>       from etl_sigrid.application.steps.build_ventas_step import BuildVentasStep
E       ModuleNotFoundError: No module named 'etl_sigrid.application.steps.build_ventas_step'
FAILED tests/test_f040_pipeline.py::test_f040_r26_comando_build_ventas - Asse...
FAILED tests/test_f040_pipeline.py::test_f040_r26_apply_grants_lo_nombra_entre_los_sueltos
14 failed, 2 passed in 2.98s
```
**T11, permisos** (antes de cambiar `settings.py`):
```
$ .venv/Scripts/python.exe -m pytest tests/test_f040_grants.py -q -p no:cacheprovider
FAILED tests/test_f040_grants.py::test_f040_r27_ventas_en_el_consumo_y_en_ningun_perfil
FAILED tests/test_f040_grants.py::test_f040_r28_vetada_y_del_autorizado_pero_no_del_total
FAILED tests/test_f040_grants.py::test_f040_r29_crea_los_dos_esquemas_como_dueno
  (... 14 en total)
E       AssertionError: assert 'contabilidad...stringida,raw' == 'contabilidad...stringida,raw'
E         - stringida,ventas_restringida,raw
14 failed, 7 passed, 6 warnings in 1.47s
```
**T14, diccionario** (antes de `ventas.yaml`):
```
$ .venv/Scripts/python.exe -m pytest tests/test_f040_diccionario.py -q -p no:cacheprovider -rf
FAILED tests/test_f040_diccionario.py::test_f040_r31_una_ficha_por_objeto_del_sql
FAILED tests/test_f040_diccionario.py::test_f040_r31_las_columnas_de_la_ficha_son_las_del_sql[ventas.clientes]
FAILED tests/test_f040_diccionario.py::test_f040_r33_architecture_describe_ventas
FAILED tests/test_f040_diccionario.py::test_f040_r33_claude_md_mapa - Asserti...
32 failed, 9 passed in 6.98s
```
Las trazas completas se guardaron en el scratchpad de la sesión (`red_t1.txt`, `red_t10.txt`,
`red_t11.txt` y `red_t14.txt`). En verde tras el código: 2300 passed (§ 3).

## 5. Verificaciones MANUAL pendientes (del humano, tras APROBADO y merge a `main`)

- **T18, despliegue**: pasos 0-9 de `specs/F-040-ingresos/design.md` § 9, con su vuelta atrás.
  Imagen; `02_roles.sql` como administrador ANTES del build, sin `*_PWD` (runbook § 15); ingesta
  `--full` de las 7 tablas y `dvf` y `check-raw-recuentos`; `build-ventas` y `apply-grants`; prueba
  negativa y positiva por login; R34 (`retenciones.movimientos` CLIENTE igual); `publicar-diccionario`.
- **T17, `mcp-bbdd`** (fuera de este repositorio): `ventas` a la lista blanca del estándar y del
  total, `ventas_restringida` solo a la del total, y reinicio del MCP, que cachea el diccionario.
  Anotado en `progress/current.md` y en `azure-apps/datamart_seg_anual.md`.
- **Push de `azure-apps`**: commits locales `882abce` y `76e722c` (ciclo 1), a la espera del humano.

## 6. Fuera de alcance y lo que falta

- **Fase 2 (F-160)**: el contraste completo certificado-obra.
- **F-104**: la conciliación de la retención de cliente por documento y el cobro de los `AGR`.
- **D4 (garantía = clases 4 y 5)** es provisional, a la espera de Juan. Cambiarla es tocar solo
  `CLASES_GARANTIA` y `ventas.fn_clase_recargo`.
- **Para cerrar**: puerta completa con `.env` y campaña de mutación (líder, con su análisis en
  `progress/mutacion_F-040.md`), re-review contra `CHECKPOINTS.md` y los pasos MANUAL de § 5.

## 7. Ciclo 1 (review `progress/review_F-040.md`, CHANGES_REQUESTED)

| Cambio | Commit | Qué |
|---|---|---|
| H1 | `3ca7aea` | `codigo_cliente` a NULL en persona física o si, normalizado, casa con `PATRON_NIF_PERSONA` (`01_clientes.sql`; oráculo `codigo_cliente_publicado` en el dominio). Íntegro en `ventas_restringida.clientes_contacto` (columna nueva, `LEFT JOIN raw.con` tipo 4, 1:1). Guarda R24 ampliada. Fichas, `design_detalle` § B (enmienda), `current.md` (2654 columnas) y `azure-apps` (`76e722c`) al día |
| H2 | este | § 2.7 reescrito: qué casos NO son persona física |
| H3 | `96b3630` | Frontera `0 < cobrado < 1` en el dominio (0,01, 0,50, 1, y 0,50 con emitido 0) y en la sandbox (vista = dominio; cobro REALIZADO en una transacción que se deshace) |
| O2 | `d7f4fb1` | Fichas: `facturado_origen` incluye anuladas y rectificativas; la cobertura de efectos cuenta los de BAJA. `02_roles.sql`: «seis filas». Sin cambio de comportamiento |

**RED de H1** (tests antes del código):
```
$ F040_SANDBOX_DSN=... .venv/Scripts/python.exe -m pytest tests/test_f040_dominio.py tests/test_f040_sql.py tests/test_f040_sandbox.py -q -p no:cacheprovider -rf --tb=line
E   AttributeError: module 'etl_sigrid.domain.ventas' has no attribute 'codigo_cliente_publicado'
E   assert "CASE WHEN b.es_persona_fisica OR COALESCE(ventas.fn_cif_normalizado(b.codigo_cliente) ~ '^[0-9KLMXYZ][0-9]{7}[A-Z]$', FALSE) THEN NULL ELSE b.codigo_cliente END AS codigo_cliente" in 'CREATE TABLE ventas.clie
E   AssertionError: assert {2: 'C2', 1: ...54321-x', ...} == {1: 'C1', 2: ... 4: None, ...}
E   psycopg.errors.UndefinedColumn: column "codigo_cliente" does not exist
E   Failed: DID NOT RAISE RaiseException
15 failed, 2199 passed in 20.31s
```
**RED de H3**: el código ya era correcto, así que la prueba es que el test mata al mutante. Se
aplicó a mano `cobrado <= 0` -> `<= 1` en `ventas.py:228` y en `05_vistas.sql:95`, y se revirtió:
```
$ F040_SANDBOX_DSN=... .venv/Scripts/python.exe -m pytest tests/test_f040_dominio.py tests/test_f040_sandbox.py -q -p no:cacheprovider -k r18 -rf --tb=line
E   AssertionError: assert 'PENDIENTE_COBRO' == 'COBRADA_PARCIAL'
FAILED tests/test_f040_sandbox.py::test_f040_sandbox_r18_frontera_de_lo_cobrado[0.50-COBRADA_PARCIAL]
7 failed, 20 passed, 2120 deselected in 5.62s
```
**Verde**: F-040 con la sandbox, **2319 passed** (21,04 s). Propuestas de H2: (a) prefijo de país y (b)
factura sin cliente, APROBADAS por el humano y aplicadas en el ciclo 2 (§ 8); (c) `perfis` NULL, sin cambio.

**Supervivientes de `build_ventas_step.py`** (RM4 del reviewer, para `progress/mutacion_F-040.md`):
L51 `slots`/`frozen` `True` -> `False`, equivalentes (`_SubStep` solo se instancia en `SUB_PASOS` y nadie
le asigna nada); L119 `exc_info`, L126 `rows = 0 -> 1` (sin tabla destino `rows` solo va al log, no a
`total_rows`) y L133 `round(…, 2 -> 3)`: solo cambian el log. Matarlos = testear el formato del log.

### Ciclo 1 · base roja (9 tests de otras features; el `-x` de `init.sh` y mi subconjunto los tapaban)

| Arreglo | Commit | Qué protege el test y qué se cambió |
|---|---|---|
| B1 | `055033f` | R9 de F-006 (`R-SIGRID-CON` = barrido del SQL): punto 3 con `cli.cif`, `cli.raz`, `dvfpro.res`; punto 4 con `cerprodes` y sin `dvf` (ya se une a `con` en `02_facturas`) |
| B2 | `58b5e0d` | R26 de F-006: fichas de `raw.cerrec` y `raw.dvfrec` con «**No se traen** 1 columna» (`tex`) |
| B3 | `87dfaa3` | Inventario de F-079: grupo H con las 5 `ventas.fn_*` (como las de `postventa`, F-156) |
| B4, B5 | `50d177f`, `126d334` | Censos de F-085 y F-138: 93 -> 100 tablas (+7 de F-040), con su motivo en el comentario |
| B6, B8 | `9d148c8` (`B6` lo corrigió B8) | R-PERFILES ≤ 1.000: 978, quitando el paréntesis repetido del POSTVENTA (la primera frase ya lo dice); motivo entero, con la fecha de F-146 |
| B7 | `0e6ea77` | F-147 R7: las dos reglas nuevas de F-040 en `REGLAS_TRAS_F147`, como F-140 y F-156 |

Ningún tope ni sentido de test cambiado; el diccionario sigue en 316 objetos, 2654 columnas y 153 de consumo. **Suite entera sin `-x`**
(`python -m pytest -q -p no:cacheprovider`, sobre `9d148c8`): `112 failed, 10944 passed, 2461 skipped, 2724 warnings in 1157.15s`.
Los 112 son de ENTORNO, no 2: los CLI de 17 ficheros (`f006_comandos`, `f025_cli`, `f052_*`, `f078_sql`, `f118_check`...) caen en el `get_settings` del grupo sin `.env` (`SigridApiSettings`: `base_url`, `function_key`). Prueba: esos 17 ficheros con `SIGRID_API_BASE_URL`/`_FUNCTION_KEY` ficticios en el proceso (sin `.env` ni red) → `705 passed, 3 skipped`.

**PG de pruebas** (`scratchpad/pgdata`, 55440): seguía arrancado; usado y parado (`pg_ctl stop`: «servidor detenido»).

## 8. Ciclo 2 (H2 a y b, aprobadas por el humano el 2026-11-10)

| Cambio | Commit | Qué |
|---|---|---|
| R2-a | `9ea7e7e` | `normalizar_cif` y `ventas.fn_cif_normalizado` quitan un prefijo de país de 2 letras SOLO si queda un NIF (`PATRON_NIF_CON_PREFIJO_PAIS` = `^[A-Z]{2}` + el patrón de NIF; un NIF nunca abre con dos letras). Cubre `cif`, `cif_normalizado`, `cif_cliente`, `codigo_cliente`, líneas y la guarda R24 (todo pasa por la función). `ESB12345678`, `FR12345678901` o `ES1234567Z` no cambian (en dominio y sandbox, con prefijos en los 2.000 CIF aleatorios: SQL = dominio) |
| R2-b | `118776a` | Factura sin cliente en `raw.cli`: `COALESCE(vc.es_persona_fisica, TRUE)` (oráculo `persona_fisica_de_factura`); descripción a NULL y entera en `factura_lineas_persona`. La cuenta el 4º eslabón `FACTURA_CLIENTE` de `cobertura_enlace` (`total - enlazados`), sin tumbar el paso. `azure-apps` `0f5ae73` |

R6, R7, R20, R23 enmendados («*Enmienda del humano 2026-11-10*»), `design_detalle.md` y fichas al día; recuentos sin cambio.
**RED** (trazas enteras en el scratchpad, `red_r2a.txt` y `red_r2b.txt`):
```
$ F040_SANDBOX_DSN=... .venv/Scripts/python.exe -m pytest tests/test_f040_dominio.py tests/test_f040_sql.py tests/test_f040_sandbox.py -q -p no:cacheprovider -rf --tb=line
E   AssertionError: assert 'ES12345678Z' == '12345678Z'
E   AttributeError: module 'etl_sigrid.domain.ventas' has no attribute 'PATRON_NIF_CON_PREFIJO_PAIS'
E   Failed: DID NOT RAISE RaiseException
10 failed, 2238 passed in 19.75s
$ (lo mismo + tests/test_f040_diccionario.py, para R2-b)
E   AttributeError: module 'etl_sigrid.domain.ventas' has no attribute 'persona_fisica_de_factura'
E   assert 'COALESCE(vc.es_persona_fisica, TRUE) AS es_persona_fisica' in 'CREATE TABLE ventas.facturas AS ...
E   assert {1005: (None,...(None, False)} == {1005: (None,... (None, True)}
9 failed, 2287 passed in 28.68s
```
**Verde**: F-040 con la sandbox, **2352 passed** (31,49 s). Suite entera sin `-x` (`118776a`): `112 failed, 10965 passed, 2473 skipped in 2251.60s`. Los 112 son los mismos CLI de entorno (17 ficheros); con `SIGRID_API_*` ficticios, esos ficheros dan `679 passed, 1 skipped`.
**Alcance de mutación** (`harness.alcance` + `generar_mutantes`, base `main`): 5 ficheros, 484 líneas, **61
mutantes** (49 en `ventas.py`, 12 en `build_ventas_step.py`; eran 58). La campaña, del líder.

## Evidencias

| Evidencia | Valor real |
|---|---|
| Tests ejecutados | Suite entera sin `-x` (ciclo 2, `118776a`): **10965 passed, 2473 skipped, 112 failed**, todos de entorno. Ciclo 1 (`9d148c8`): **10944 passed, 2461 skipped, 112 failed**, todos de entorno (CLI sin `.env`; con `SIGRID_API_*` ficticios, 705 passed). Ciclo 1: propios de F-040 **2319 passed**, 0 failed (21,04 s). Pasada 1: propios de F-040 **2300 passed**, 0 failed (246 sin base + 2054 en el PG16 local), 15,29 s. Subconjunto de la rama bajo cobertura: **3638 passed, 6 skipped, 1 failed** (el de entorno `test_f024_r19`). `init.sh`: 256 passed antes del corte por `-x` en `test_f006_t26` (entorno) |
| Cobertura de líneas cambiadas | **100,0 % (148/148)**, `PUERTA COBERTURA` de `harness.cobertura --base main` sobre el subconjunto. La de `init.sh` en este worktree, 52,0 %, es por el corte de `-x` |
| Mutantes | **Sin veredicto: la campaña no corre en este worktree. Queda para el líder.** `python -m harness.mutacion --feature F-040 --base main` (árbol limpio): alcance de 5 ficheros y 450 líneas de producción, 4 workers, y **exit=3**: «LÍNEA BASE SIN TERMINAR [...] la suite SIN MUTAR agotó los 600 s que se le concedieron (el suelo 'mutacion.timeout_por_mutante_s' multiplicado por la holgura de 5), con 4 worker(s) compitiendo por la máquina». Además la línea base estaba roja: los de entorno y los 9 de § 7 «base roja», ya arreglados. No se evaluó ningún mutante: 0 generados y 0 supervivientes. No se cambió `rigor.json` ni se acotó la suite (no improvisar). El SQL de `sql/ventas/` no se muta; lo cubren la sandbox (2054 tests) y los literales contra el dominio |
| Tiempo de la suite | Suite entera sin cobertura: **1157,15 s** (19 min 17 s). Subconjunto con cobertura: **554,63 s** (9 min 14 s). `init.sh` hasta el corte: 405,19 s. La suite entera no se completó aquí: con cobertura ronda las 4 h (F-156: 15.176 s) |
