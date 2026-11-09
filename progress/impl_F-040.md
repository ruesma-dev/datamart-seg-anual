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
| T4 | `adc9f14` | `sql/ventas/00_setup.sql` (los dos esquemas y las funciones) y `01_clientes.sql` |
| T5 | `e80a6f2` | `02_facturas.sql`: facturas, líneas y recargos repartidos en cuatro columnas |
| T6 | `43bd491` | `03_certificaciones.sql`: a cuenta, a origen, `base_origen_contrato` y recargos |
| T7 | `19e45b5` | `04_enlace.sql` (`certificacion_factura`, `cobertura_enlace`) y `05_vistas.sql` (cobro, seguimiento y contraste) |
| T8 | `76818d7` | `06_restringida.sql`: `clientes_contacto`, `factura_cabecera` y `factura_lineas_persona` |
| T9 | `647cb01` | `07_guardas.sql`: recuentos, base y reparto contra `raw`, y ninguna columna personal en `ventas` |
| T10 | `ca289ea` | `build_ventas_step.py` (ocho sub-pasos); `main.py`: tras `build_retenciones`, diecisiete pasos, `PASOS_CON_PERMISOS`, comando `build-ventas` |
| T11 | `f6889d9` | `settings.py` y `.env.example`: `ventas` en el consumo y `ventas_restringida` en vetados y restringidos; `ESQUEMAS_DEL_DATAMART` de 18 a 20; `00_global.yaml` |
| T12 | `4515ab0` | `infra/sql/02_roles.sql` (esquemas, punto 5, veto del 5 ter, concesión al autorizado, comprobaciones finales) y runbook § 15 |
| T13 | `eecc0fe` | `test_f040_frontera.py` (R30: `sql/retenciones` y `sql/tesoreria` sin diff) |
| T14 | `a851ea1` | Diccionario v75: `ventas.yaml` (16 fichas), `ventas_restringida.yaml` (3), `R-VENTAS-TRES-CIFRAS`, `R-VENTAS-RESTRINGIDA`, `R-PERFILES` y `R-FRESCURA` al día |
| T15 | `549111c` | `ARCHITECTURE.md`, mapa de `CLAUDE.md`; `azure-apps/datamart_seg_anual.md` (commit local `882abce` en `azure-apps`, sin push) |
| T16 | `01f4c9f` y el de este informe | `progress/current.md`, este informe, `tasks.md` |

En total son 66 ficheros (`git diff --stat main...HEAD`), con +6.301 y −210 líneas. Del código nuevo, 8 ficheros SQL
(`etl_sigrid/infrastructure/postgres/sql/ventas/`), 2 módulos Python y 8 ficheros de test
`tests/test_f040_*.py`. Además se pusieron al día los tests de listas y censos de otras features (§ 2.9).

`sql/retenciones/` y `sql/tesoreria/` **no se tocan** (R30, lo vigila `test_f040_frontera`).

## 2. Decisiones y desviaciones (justificadas)

1. **Diccionario v75, no v74**: `main` ya publicó la v74 con F-159. Los tests de versión usan
   `>=`; `test_f040_diccionario` fija `VERSION_ANTERIOR = 74`.
2. **Diecisiete pasos** en `run-all`, no dieciséis: F-156 ya añadió el suyo. `build_ventas` va tras
   `build_retenciones`, solo depende de `ingest_raw` y ningún paso depende de él.
3. **Tope de F-147 (presupuesto de contexto del MCP) a 37.042**. La causa son dos reglas duras
   nuevas y el ámbito ampliado de otras dos. Queda en un comentario del test, con el desglose
   (reglas 8.464, enrutado 18.516, bloques 10.062). Mismo precedente que F-156.
4. **Fichas de `raw` ya en T3**: la puerta R25 de F-006 (`test_f006_r25_puerta...`) exige ficha
   o pendiente en cuanto la tabla se declara. Sin ellas, T3 no pasaba la suite.
5. **Una sandbox Postgres extra**: `tests/test_f040_sandbox.py` ejecuta el SQL real de
   `sql/ventas/` sobre un PG16 local con los tipos reales de la ingesta (`double precision`, con
   cast a `NUMERIC`). Sin `F040_SANDBOX_DSN`, salta. No estaba en tasks; es la defensa contra SQL que
   solo se comprueba como literal.
6. **Adiciones al dominio** que pide el SQL, para tener un oráculo único: `TIP_CLIENTE`,
   `repartir_recargos`, `ESLABONES_COBERTURA` y los patrones de CIF.
7. **Fail-closed**: un CIF ilegible o un `perfis` desconocido se tratan como persona física, así
   que van a `ventas_restringida` y no se publican.
8. **Obra de la factura**: sale de la cabecera solo cuando la línea no trae centro. Así lo describe
   design § 4.
9. **Tests de otras features puestos al día**, solo en listas y recuentos:
   - `f006_formato`, `f006_frescura`, `f006_publicacion`, `f024_cli`
   - `f037`, `f047`, `f057`, `f066`, `f074`, `f085`, `f090`, `f097`
   - `f135`, `f138`, `f140`, `f141`, `f146`, `f147`, `f148`, `f150`, `f156`

   En `f141` se mantiene su instantánea de `CONSUMO`, que es autocontenida, y solo cambia `esperado`.
10. **Inventario de F-006 a 316 objetos**: `design.md` y una enmienda en `design_detalle.md` (de ahí
   lee el test).
11. **Observación sin medir**: `ventas.clientes.codigo_cliente` (`con.cod`) podría contener un NIF
   en personas físicas. Se propone comprobarlo en el paso MANUAL 6 de design § 9 con `<Q>` (por
   ejemplo, cuántos códigos de personas físicas casan con el patrón de NIF). Si aparecen, se pasa
   la columna a `ventas_restringida`.

## 3. Verificación real

- **Tests de F-040**: `F040_SANDBOX_DSN=... pytest tests/test_f040_*.py -q -p no:cacheprovider`
  → **2300 passed** en 15,29 s. Son 246 sin red ni base de datos y 2054 contra el PG16 local. Sin
  DSN: `246 passed, 2054 skipped`.
- **`bash harness/init.sh` (T19)** en este worktree: **rojo, solo por el entorno**.
  - `[KO] Falta .env`.
  - pytest se para por `-x` en `test_f006_t26_cli_dry_run_no_toca_la_base` (`SigridApiSettings`:
    `base_url` requerido) tras 256 passed.
  - Por ese corte, su `PUERTA COBERTURA` da 52,0 % (77/148), una cifra que no representa el
    cambio.
  - `PUERTA TAMAÑO` OK (requirements 148/150, design 247/250); rama OK.
  - Está prohibido crear `.env` aquí: el líder pasa la puerta completa en una copia con `.env`.
- **Cobertura de las líneas cambiadas**, medida aparte:
  - Comando: `coverage run -m pytest <los 31 ficheros de test que toca la rama>` con el DSN de la
    sandbox, y después `harness.cobertura --base main`.
  - Resultado: **`PUERTA COBERTURA: 100.0% de 148 líneas cambiadas cubiertas (148/148, umbral 80%,
    nivel critico)`**.
  - Ese subconjunto dio 3638 passed, 6 skipped y 1 failed en 554,63 s. El fallo,
    `test_f024_r19_la_ayuda_ensena_el_umbral_y_el_paso_por_defecto`, es de entorno: `check-frescura
    --help` pasa por `get_settings` y sin `.env` cae.
  - Con la suite entera la cobertura solo puede subir.
- **Dos fallos que solo son de entorno**: `test_f006_t26` y `test_f024_r19`. Los dos piden
  `.env` y no tocan F-040.

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
  - Imagen.
  - `02_roles.sql` como administrador ANTES del build, sin `*_PWD` (runbook § 15).
  - Ingesta `--full` de las 7 tablas y `dvf`, y `check-raw-recuentos`.
  - `build-ventas` y `apply-grants`.
  - Prueba negativa y positiva por login.
  - Cifras de R34: `retenciones.movimientos` CLIENTE igual antes y después.
  - `publicar-diccionario` con la imagen del job.
  - Añadido de este informe: medir `codigo_cliente` (§ 2.11).
- **T17, `mcp-bbdd`** (fuera de este repositorio): `ventas` a la lista blanca del estándar y del
  total, `ventas_restringida` solo a la del total, y reinicio del MCP, que cachea el diccionario.
  Anotado en `progress/current.md` y en `azure-apps/datamart_seg_anual.md`.
- **Push de `azure-apps`**: commit local `882abce`, a la espera del humano.

## 6. Fuera de alcance y lo que falta

- **Fase 2 (F-160)**: el contraste completo certificado-obra.
- **F-104**: la conciliación de la retención de cliente por documento y el cobro de los `AGR`.
- **D4 (garantía = clases 4 y 5)** es provisional, a la espera de Juan. Cambiarla es tocar solo
  `CLASES_GARANTIA` y `ventas.fn_clase_recargo`.
- **Para cerrar**:
  - Puerta completa con `.env` (líder).
  - Campaña de mutación en una copia con `.env`, con menos workers o con el suelo de
    `timeout_por_mutante_s` subido (ver Evidencias). Su análisis irá a `progress/mutacion_F-040.md`.
  - Review contra `CHECKPOINTS.md`.
  - Los pasos MANUAL de § 5.

## Evidencias

| Evidencia | Valor real |
|---|---|
| Tests ejecutados | Propios de F-040: **2300 passed**, 0 failed (246 sin base + 2054 en el PG16 local), 15,29 s. Subconjunto de la rama bajo cobertura: **3638 passed, 6 skipped, 1 failed** (el de entorno `test_f024_r19`). `init.sh`: 256 passed antes del corte por `-x` en `test_f006_t26` (entorno) |
| Cobertura de líneas cambiadas | **100,0 % (148/148)**, `PUERTA COBERTURA` de `harness.cobertura --base main` sobre el subconjunto. La de `init.sh` en este worktree, 52,0 %, es por el corte de `-x` |
| Mutantes | **Sin veredicto: la campaña no corre en este worktree. Queda para el líder.** `python -m harness.mutacion --feature F-040 --base main` (árbol limpio): alcance de 5 ficheros y 450 líneas de producción, 4 workers, y **exit=3**: «LÍNEA BASE SIN TERMINAR [...] la suite SIN MUTAR agotó los 600 s que se le concedieron (el suelo 'mutacion.timeout_por_mutante_s' multiplicado por la holgura de 5), con 4 worker(s) compitiendo por la máquina». Además, sin `.env` la línea base saldría roja (`test_f006_t26`, `test_f024_r19`) y la campaña abortaría igual. No se evaluó ningún mutante: 0 generados y 0 supervivientes. No se cambió `rigor.json` ni se acotó la suite (no improvisar). El SQL de `sql/ventas/` no se muta; lo cubren la sandbox (2054 tests) y los literales contra el dominio |
| Tiempo de la suite | Subconjunto con cobertura: **554,63 s** (9 min 14 s). `init.sh` hasta el corte: 405,19 s. La suite entera no se completó aquí: con cobertura ronda las 4 h (F-156: 15.176 s) |
