<!-- progress/impl_F-148.md -->
# F-148 · Robustez de la nocturna · informe del implementer

Rama `feature/F-148-robustez-nocturna`, base `main` (`9ff322f`). Rigor **critico** (D5). Decisiones
D1-D7 cerradas por el humano según la propuesta (`design.md` §12). Un commit por tarea:
`F-148 T1` … `F-148 T13` (T14-T15, el commit de este informe).

## Qué cambió

| Parte | Ficheros | Qué hace |
|---|---|---|
| A · conexión | `config/settings.py`, `conninfo.py`, `reintento_conexion.py` (nuevo), `client_factory.py`, `main._get_pg` | `connect_timeout` 15 s, `keepalives=1` 30/10/3 y `tcp_user_timeout` 60.000 ms en TODA cadena (R1-R2); apertura con reintento tenacity (4 intentos, espera 2-30 s) solo ante transitorios (R3-R6); `SET ROLE` sin reintento (R7); `pg_conexion_lenta` si > 2 s o > 1 intento (R16) |
| B · sesión de carga | `sesion_carga.py` (nuevo), `postgres_client.py` (`sesion_de_carga`, `linea_copy`, `SQL_FILAS_EN_RANGO`; `copy_rows` retirado), `ingest_raw_step.py` | UNA conexión por tabla, `COPY` + `COMMIT` por página (R8-R9); conexión rota → cuenta el rango de ids (0 = repetir, todas = ya estaba, otra = «página ambigua») y reintenta hasta 3 (R10-R11); otro error → rollback y propaga (R12); cierre en `finally` (R13); `ingest_pagina` con `http_s`/`pg_connect_s`/`copy_s`/`reintentos` en TODAS las páginas (R14, D7); `conexiones_abiertas` en la metadata (R17) |
| C · reanudación | `domain/reanudacion.py` (nuevo), `domain/ejecucion.py`, `postgres_client.py` (`SQL_LOTE_REANUDABLE`, `SQL_TERMINADOS_EN_LOTE`, dos métodos), `orchestrator.py`, `ingest_raw_step.py`, `main.py` | sufijo del `batch_id` = `sha256(CONTAINER_APP_JOB_EXECUTION_NAME)[:6]`; adopta el lote de la réplica anterior (ventana 8 h) (R18-R20); omite pasos `SUCCESS` cuyas dependencias se omiten, nunca `apply_grants`, sin fila (R21-R22); omite tablas `ingest_raw.<t>` en `SUCCESS` (R23); la puerta de `build_stg` ve un lote (R24) |
| D · permisos por paso | `orchestrator.py` (`tras_paso`), `main.py` (`PASOS_CON_PERMISOS`, `_permisos_tras_paso`) | tras cada build EJECUTADO de los diez (SUCCESS o FAILED o excepción), `ApplyGrantsStep` íntegro sobre el mismo cliente y fila `apply_grants.tras_<paso>` (R25); fallo → `permisos_tras_paso_fallidos`, la noche sigue (R26-R27); omitido o SKIPPED no dispara (R28) |
| E · documentación | `_meta.yaml`, `00_global.yaml` (v60), `docs/ARCHITECTURE.md`, `../azure-apps/datamart_seg_anual.md` | R29-R30. `azure-apps`: commit LOCAL `40b0da9`, sin push, con «PENDIENTE de desplegar» |
| Tests | `tests/test_f148_{conexion,sesion_carga,reanudacion,permisos_por_paso,documentacion}.py` (162 tests); dobles adaptados en `test_f024_steps`, `test_f066_reconciliar_columnas`, `test_f025_firma_paso`; `test_f024_cli` R3; `test_f147_contenido` | ninguno toca red ni BBDD |

## Decisiones de diseño y desviaciones (justificadas también en `current.md`)

1. **`es_error_transitorio` sin rama explícita «clase `28`/`3D000` → False»** (§5 la lista). Esos
   casos ya dan False: marcas de texto (desde la revisión: `password authentication failed`,
   `pg_hba.conf`, `permission denied for database`), regex
   `(role|database) .* does not exist`, y `28…`/`3D000` no son `08…`/`53300`/`57P03`. La rama
   explícita sería código redundante = mutantes equivalentes por construcción. Probado caso a caso
   en la tabla de R3/R4 de `test_f148_conexion.py`.
2. **`Ejecucion.reanudada`** (nuevo campo, `False` por defecto; `ejecucion_desde_batch` → `True`).
   Es lo que dice a `run-all` si leer lo terminado del lote: un lote NUEVO lleva el mismo sufijo y,
   sin el campo, leería filas ajenas. `ejecucion_desde_batch` rechaza además un `batch_id` sin
   sufijo (`"20261023T000312Z"`, `"20261023T000312Z-"`).
3. **`main.py`**: además de §5, `VARIABLE_EJECUCION_JOB`, `_identidad_de_la_ejecucion` (R18-R20) y
   `_terminados_del_lote` (R20, fallo leyendo → aviso y nada omitido). `_arrancar_ejecucion(pg)`
   conserva su llamada literal en los comandos sueltos (la vigilan `test_f056`/`test_f097`).
4. **Import local de `SesionDeCarga`** dentro de `PostgresClient.sesion_de_carga` (y en
   `TYPE_CHECKING`): `sesion_carga` importa `SQL_FILAS_EN_RANGO` y `linea_copy` del cliente, y el
   cliente necesita la sesión: ciclo resuelto sin mover el formateo COPY de sitio.
5. **Versión del diccionario**: `test_f147` pasa a `>= 59` y el de F-148 es `>= 60`, la convención
   del repositorio (F-037, F-085, F-090... la fijan así para no romper a la siguiente).
6. **`test_f024_cli` R3** cuenta aparte las diez filas `apply_grants.tras_*` y exige, como antes,
   una fila por paso del pipeline. Ninguna aserción debilitada en los dobles de f024/f066.
7. **T2 · psycopg instalado (3.3.4)** registra los intentos de conexión en DEBUG en
   `.venv/Lib/site-packages/psycopg/connection.py`: línea 105 `connection attempt`, 111
   `connection failed`, 116 `connection succeeded`. Por eso `psycopg_en_debug()` sube el logger
   `psycopg` a DEBUG solo alrededor de `psycopg.connect` y restaura el nivel en `finally`.

## Fase RED (trazas reales; ruta del worktree temporal redactada como `<wt>`)

Los tests se escribieron antes del código, tarea a tarea, en un worktree temporal de la propia rama
(`tmp-f148-impl`, ya fusionado por fast-forward y borrado). Comando y salida de cada fallo:

**T1** · `python -m pytest tests/test_f148_conexion.py -k "r1 or r2" -q -p no:cacheprovider --tb=line`
```
E   KeyError: 'connect_timeout'                                        (x3)
E   AttributeError: 'PostgresSettings' object has no attribute 'connect_timeout_s'   (x3)
E   Failed: DID NOT RAISE ValueError                                   (x2)
8 failed, 5 deselected in 1.05s
```
**T2** · `python -m pytest tests/test_f148_conexion.py -k "r3 or r4 or r5 or r6 or r15" -q -p no:cacheprovider --tb=line`
```
E   ImportError: cannot import name 'reintento_conexion' from 'etl_sigrid.infrastructure.postgres' (<wt>\etl_sigrid\infrastructure\postgres\__init__.py)
1 error in 1.17s
```
**T3** · `python -m pytest tests/test_f148_conexion.py -q -p no:cacheprovider --tb=line`
```
E   AttributeError: 'PostgresClient' object has no attribute 'conexiones_abiertas'
E   TypeError: PostgresClient.__init__() got an unexpected keyword argument 'connect_intentos'
E   TypeError: PostgresClient.__init__() got an unexpected keyword argument 'dormir'     (x4)
E   ValueError: not enough values to unpack (expected 1, got 0)
E   assert 30 == 10
8 failed, 41 passed in 0.90s
```
**T4** · `python -m pytest tests/test_f148_sesion_carga.py -q -p no:cacheprovider --tb=line`
```
E   ModuleNotFoundError: No module named 'etl_sigrid.infrastructure.postgres.sesion_carga'
1 error in 0.55s
```
**T5** · `python -m pytest tests/test_f148_sesion_carga.py -q -p no:cacheprovider --tb=line`
```
E   AttributeError: 'PgIngesta' object has no attribute 'copy_rows'   (x5)
E   AttributeError: <module 'etl_sigrid.application.steps.ingest_raw_step' ...> has no attribute 'perf_counter'
E   AssertionError: assert not True            (copy_rows seguía existiendo)
7 failed, 26 passed, 1 warning in 0.87s
```
**T6** · `python -m pytest -q tests/test_f148_reanudacion.py`
```
E   ImportError: cannot import name 'ejecucion_desde_batch' from 'etl_sigrid.domain.ejecucion' (<wt>\etl_sigrid\domain\ejecucion.py)
1 error in 0.37s                         --- tras el código: 60 passed (con test_f024_dominio)
```
**T7** · `python -m pytest -q tests/test_f148_reanudacion.py -k sql`
```
E   ImportError: cannot import name 'SQL_LOTE_REANUDABLE' from 'etl_sigrid.infrastructure.postgres.postgres_client'
1 error in 0.52s                         --- tras el código: 22 passed
```
**T8** · `python -m pytest -q tests/test_f148_reanudacion.py tests/test_f148_permisos_por_paso.py`
```
E   TypeError: Orchestrator.__init__() got an unexpected keyword argument 'tras_paso'
E   TypeError: Orchestrator.__init__() got an unexpected keyword argument 'terminados_en_lote'
7 failed, 24 passed, 1 warning in 0.63s  --- tras el código (con f005, f006_publicacion, f024_infra_alerta, f047): 163 passed
```
**T9** · `python -m pytest -q tests/test_f148_reanudacion.py -k "r23 or r24"`
```
E   TypeError: IngestRawStep.__init__() got an unexpected keyword argument 'tablas_terminadas'
FAILED ...::test_f148_r23_la_ingesta_omite_las_tablas_terminadas
FAILED ...::test_f148_r23_sin_reanudar_carga_todas
2 failed, 3 passed, 25 deselected        --- tras el código: 213 passed
```
(Los dos de R24 pasan ya en RED a propósito: R24 no pide código nuevo en la puerta, sino que la
ingesta reanudada le llegue con UN lote; el control `..._sin_adoptar_el_lote_la_puerta_rechaza`
demuestra por qué hace falta adoptar.)

**T10** · `python -m pytest -q tests/test_f148_reanudacion.py tests/test_f148_permisos_por_paso.py`
```
E   AttributeError: 'Ejecucion' object has no attribute 'reanudada'
E   AttributeError: module 'main' has no attribute 'PASOS_CON_PERMISOS'
E   AttributeError: module 'main' has no attribute '_permisos_tras_paso'
E   TypeError: Ejecucion.__init__() got an unexpected keyword argument 'reanudada'
34 failed, 40 passed, 60 warnings in 23.12s   --- tras el código (con test_f024_cli): 140 passed
```
**T11** · `python -m pytest -q tests/test_f148_documentacion.py`
```
E   AssertionError: assert 'reintento' in 'la ejecucion completa a la que pertenece esta fila: ...'
E   AssertionError: assert 'apply_grants.tras_' in 'nombre del paso. **si lleva un punto es un tramo** ...'
E   AssertionError: docs/ARCHITECTURE.md no dice «una conexión por tabla»
4 failed, 1 skipped in 0.32s             --- tras T11 (-k r29): 3 passed; tras T12: 5 passed
```

## Revisión pasada 1 (CHANGES_REQUESTED, `progress/review_F-148.md`): lo hecho

Commits `5b2d201` (R4), `0f98420` (R-a), `e978440` (ARCHITECTURE), `6cb0de3` (current.md) y el
de este informe; en `azure-apps`, commit LOCAL `4535829` (sin push).

1. **R4 real** (decisión del humano: SÍ). `MARCAS_DEFINITIVAS` = `password authentication
   failed`, `pg_hba.conf` (cubre «no … entry» y «rejects connection») y `permission denied for
   database`, con el porqué en el comentario: psycopg 3.3 abre SIN SQLSTATE. Tests: seis casos con
   la forma REAL (`connection failed: connection to server at "h" (192.0.2.1), port 5432 failed:
   FATAL:  …`, IP de documentación) y `test_f148_r4_la_apertura_real_llega_sin_sqlstate`, que
   provoca un fallo REAL de libpq sin red (`service=` inexistente, `PGSERVICEFILE` en `tmp_path`)
   y fija `sqlstate is None`. Los casos con SQLSTATE quedan anotados como contrato. R4 al día.
2. **Riesgo R-a** (decisión del humano). `domain/reanudacion.py`: `LECTURAS_PARA_REANUDAR =
   {"build_retenciones": {"build_stg", "build_mart"}}`; `pasos_a_omitir` omite solo si además las
   lecturas presentes en la ejecución ya se omiten (si van detrás en el orden, se rehace: ante la
   duda, construir). Orden, `depends_on` (`["ingest_raw"]`, lo fija un test) y noche normal sin
   cambios. **Barrido** de los SQL de cada build: es el ÚNICO que lee sin declarar una tabla de un
   build ANTERIOR (`05_fin_obra.sql`: `stg.plan_mensual`, `mart.master_versiones_tipadas`). El
   resto: vistas vivas (las de `maestro` sobre `stg`, `compras.vencimientos` → `tesoreria`),
   vistas solo sobre `raw` (`maestro.centros_coste`, `maestro.v_obra_fichas`), comentarios, o
   lecturas de builds POSTERIORES (retenciones → cierre, compras → descompuestos/personal), que
   en las dos réplicas son la noche anterior. R21 y `design.md` §10 al día (148/150 y 250/250).
3. **Mutación del delta**: ver «Evidencias».
4. **Documentación**: `ARCHITECTURE.md` (nocturnas del 17 al 23-10; lecturas al reanudar) y
   `azure-apps` (`conexiones_abiertas` mide solo la ingesta y el ~550 no cuenta los diez
   `apply_grants.tras_*`; 17-23 de octubre; R4 ampliado; retenciones al reanudar).
5. **Despliegue MANUAL** en `current.md`: paso 0 con el tag de hoy `r20261023-1016` y su vuelta
   atrás; comprobar la imagen del job tras reapuntarlo; reiniciar el MCP y ver «Versión 60»; push
   de `azure-apps` solo con autorización; R31(a) por SQL o `ejecucion_reanudada`.

**RED de R4** · `python -m pytest -q -p no:cacheprovider --tb=line tests/test_f148_conexion.py -k r4`
```
E   assert True is False  (es_error_transitorio(... FATAL:  pg_hba.conf rejects connection for host ...))
E   assert True is False  (es_error_transitorio(... FATAL:  permission denied for database "sigrid_dm" ...))
FAILED ...::test_f148_r4_errores_que_no_se_reintentan[real-pg_hba-rechaza]
FAILED ...::test_f148_r4_errores_que_no_se_reintentan[real-sin-connect]
2 failed, 17 passed, 38 deselected in 2.71s        --- tras el código: 57 passed (todo el fichero)
```
**RED de R-a** · `python -m pytest -q -p no:cacheprovider --tb=line tests/test_f148_reanudacion.py -k r21`
```
E   AssertionError: assert frozenset({'b...d_excel_aux'}) == frozenset({'i...d_excel_aux'})   (x2)
E   AssertionError: assert frozenset({'b...'ingest_raw'}) == frozenset({'b...'ingest_raw'})
E   AttributeError: module 'etl_sigrid.domain.reanudacion' has no attribute 'LECTURAS_PARA_REANUDAR'
E   AssertionError: assert ['build_stg', 'build_mart'] == ['build_stg',..._retenciones']
5 failed, 12 passed, 35 deselected in 2.06s   --- tras el código (con test_f110*): 85 passed
```

## Verificaciones MANUAL pendientes (humano, tras APROBADO y merge)

Copiadas a `progress/current.md` (T13): imagen nueva (`infra/70_build_image.ps1`) y job
reapuntado (`infra/85_update_job.ps1`), sin variables ni DDL; la nocturna publica la v60 (NO
publicar desde el puesto antes). Primera nocturna: `ejecucion_job=` en el arranque,
`ingest_pagina` por página, `conexiones_abiertas` y filas `apply_grants.tras_*` en `SUCCESS`;
coste de los permisos por paso (D4); **7 noches seguidas** (R31) con las consultas de §8.
Además: avisar a quien mantenga `mcp-bbdd` de que en `_meta.etl_runs` aparecen filas con punto
`apply_grants.tras_*` (ya lo dice la ficha publicada en v60).

## Fuera del alcance

Lo de `design.md` §9 (escrituras en Azure: logs del servidor compartido, hora del job,
VNet/NAT). `.env.example` no lleva los seis `PG_*` nuevos: tienen valor por defecto y el job no
los define (§7: «sin variables nuevas»).

## Evidencias

Números medidos, no estimados.

| Evidencia | Valor | De dónde sale |
|---|---|---|
| Tests ejecutados | **8.783 passed, 254 skipped, 0 failed** | `bash harness/init.sh` sobre `c2e226d` (T1-T13), exit 0, `ENTORNO LISTO` |
| Tests propios de F-148 | 162 (conexion 50, sesion_carga 33, reanudacion 44, permisos_por_paso 30, documentacion 5), todos en verde; el de `azure-apps` se ejecuta en el árbol principal (se salta solo en un worktree) | `pytest tests/test_f148_*.py` → `162 passed in 20.18s` |
| Cobertura de las líneas cambiadas | **100,0 % (281/281)**, umbral 80 %, nivel critico | `PUERTA COBERTURA` de `init.sh` (diff desde `9ff322f`, merge-base con `main`) |
| Mutación (campaña ENTERA, sin muestreo) | **92 generados, 92 evaluados, 92 muertos, 0 supervivientes, 0 timeouts, 0 sin veredicto**; 31.149,2 s (8 h 39 min), 3 workers, `--timeout 9000`, línea base 1.002,7-1.014,4 s por worker | `python -m harness.mutacion --feature F-148 --max-mutantes 0 --workers 3 --timeout 9000` → `progress/mutacion_F-148.md` |
| Reverificación EN SERIE de los muertos | **92/92 muertos** (90 por subconjunto, 2 por la suite entera); ningún falso muerto | `progress/mutacion_F-148.md`, sección «Reverificación EN SERIE» |
| Mutación del delta de la revisión (los dos módulos ENTEROS) | **20 generados, 20 muertos, 0 supervivientes, 0 timeouts**; 11.862,5 s, 3 workers, `--timeout 9000`; en serie, **20/20 muertos** por el subconjunto | `python -m harness.mutacion --feature F-148 --ficheros etl_sigrid/domain/reanudacion.py,etl_sigrid/infrastructure/postgres/reintento_conexion.py --workers 3 --timeout 9000 --max-mutantes 0` → `progress/mutacion_F-148_revision1.md` |
| Tiempo de la suite | 1.344,07 s (22 min 24 s) con medición de cobertura | la línea final de pytest dentro de `init.sh` |
| Tamaño | `PUERTA TAMAÑO` OK: requirements 148/150, design 250/250; este informe ≤ 220 | `init.sh` |
| Lint | sin avisos nuevos en lo tocado: los ficheros nuevos pasan `ruff check` y `ruff format`; `main.py` tiene los mismos 73 avisos previos antes y después | `python -m ruff check` (la deuda previa no bloquea, `LINT_BLOQUEA=0`) |

**Supervivientes: ninguno**, así que no hay análisis de equivalentes que pedir al humano.

Primer intento de la campaña entera (4 workers): abortó en la línea base (> 600 s) sin aplicar
ningún mutante; se relanzó con `--workers 3 --timeout 9000`, el patrón de F-141.

**`bash harness/init.sh` final** (T15, sobre `a09fe92`, con este informe ya commiteado): exit 0,
**8.783 passed, 254 skipped en 2.265,46 s (37 min 45 s)**, `PUERTA COBERTURA` 100,0 % (281/281),
`PUERTA TAMAÑO` OK (requirements 145/150, design 250/250, impl 164/220), `ENTORNO LISTO`. Es más
lenta que la de `c2e226d` (22 min 24 s) por la máquina, no por los tests: mismo recuento.
