# F-148 · Diseño

Requisitos: [`requirements.md`](requirements.md). Diagnóstico:
[`progress/explore_F-148_corte.md`](../../progress/explore_F-148_corte.md).

## 1 · Encaje y límite

Todo es de este servicio: cómo el ETL abre SUS conexiones al Postgres
compartido y cómo se reanuda SU job. No toca `sigrid-api` ni el servidor (§9).
Capas: regla de reanudación e identidad del lote, **dominio puro**; omisión de
pasos y gancho de permisos, **aplicación** (composición en `main.py`); sesión de
carga, reintento de conexión y consultas, **infraestructura**. Sin DDL nuevo.

## 2 · Ficheros a crear

| Ruta | Qué |
|---|---|
| `etl_sigrid/domain/reanudacion.py` | `VENTANA_REANUDACION`, `PASOS_NUNCA_OMITIBLES`, `sufijo_de_ejecucion_job`, `pasos_a_omitir`, `tablas_a_omitir` (puro) |
| `etl_sigrid/infrastructure/postgres/reintento_conexion.py` | `es_error_transitorio(exc)`, `abrir_con_reintento(...)` (tenacity), `psycopg_en_debug()` |
| `etl_sigrid/infrastructure/postgres/sesion_carga.py` | `SesionDeCarga` y `MedidaPagina`: una conexión por tabla, COPY + COMMIT por página, reintento idempotente |
| `tests/test_f148_{conexion,sesion_carga,reanudacion,permisos_por_paso,documentacion}.py` | R1-R7 y R15-R16 · R8-R14 y R17 · R18-R24 · R25-R28 · R29-R30 (estático) |

## 3 · Ficheros a modificar

| Ruta | Cambio |
|---|---|
| `config/settings.py` | `PostgresSettings`: `connect_timeout_s` (15, 2..120), `keepalives_idle_s` (30), `keepalives_interval_s` (10), `keepalives_count` (3), `tcp_user_timeout_ms` (60000), `connect_intentos` (4, 1..10). `default=` solo en la firma |
| `etl_sigrid/infrastructure/postgres/conninfo.py` | `build_conninfo` añade `connect_timeout`, `keepalives=1`, `keepalives_idle`, `keepalives_interval`, `keepalives_count`, `tcp_user_timeout` |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | `_connect` pasa por `abrir_con_reintento` con `psycopg_en_debug()` alrededor de `psycopg.connect`; contador `conexiones_abiertas`; nuevos `sesion_de_carga(...)`, `fetch_terminados_en_lote(batch_id)`, `buscar_lote_reanudable(sufijo, desde)`; `copy_rows` se retira (su único llamante pasa a la sesión) y el formateo de la línea COPY se comparte con `SesionDeCarga` |
| `etl_sigrid/infrastructure/postgres/client_factory.py` | Pasa `connect_intentos` al cliente |
| `etl_sigrid/application/steps/ingest_raw_step.py` | `tablas_terminadas` (kwarg); `_ingest_one_table` usa `pg.sesion_de_carga` y mide `http_s`; `ingest_pagina` por página; `metadata`: `tablas_reanudadas`, `conexiones_abiertas` |
| `etl_sigrid/application/orchestrator.py` | kwargs `terminados_en_lote: frozenset[str]` y `tras_paso: Callable[[PipelineStep, StepResult], None] \| None`; omite lo que diga `pasos_a_omitir`; llama `tras_paso` tras cada paso ejecutado |
| `etl_sigrid/domain/ejecucion.py` | `ejecucion_desde_batch(batch_id) -> Ejecucion` (adoptar un lote) |
| `main.py` | `_arrancar_ejecucion(pg, ejecucion_job=None)`; `run_all` lee `CONTAINER_APP_JOB_EXECUTION_NAME`, adopta lote, lee terminados y compone `IngestRawStep(tablas_terminadas=…)`, `Orchestrator(terminados_en_lote=…, tras_paso=…)`; constante `PASOS_CON_PERMISOS`; `_permisos_tras_paso(settings, pg, recorder)` |
| `config/diccionario/_meta.yaml` | Fichas `etl_runs.batch_id` y `etl_runs.step` (R29) |
| `config/diccionario/00_global.yaml` | `version: 60` |
| `docs/ARCHITECTURE.md` | Párrafo «La ingesta hace commit por PÁGINA» y sección F-047 (R30) |
| `tests/test_f024_steps.py`, `tests/test_f066_reconciliar_columnas.py` | Sus `_PgFalso` sustituyen `copy_rows` por `sesion_de_carga`; las aserciones NO se debilitan |
| `../azure-apps/datamart_seg_anual.md` | «Cómo se ejecuta» y «Qué rompe este proyecto a otros»: ~3.500 → ~550 aperturas por noche (estimación; R17 lo mide), `connect_timeout` 15 s con reintento, keepalives, reanudación. Commit local en `azure-apps` |

## 4 · Decisiones técnicas (las que el humano delegó)

**Keepalives y `tcp_user_timeout`: SÍ, en todas las conexiones.** Con una
conexión por tabla, la sesión de `obrparpre` vive 15-25 min y pasa la mayor
parte del tiempo ociosa esperando a `sigrid-api` (mediana 0,3 s, pero hay
pausas de 134 s). Sin keepalives, un flujo que la salida de red de la plataforma
deje caer en silencio solo se detecta al escribir, y un `write` bloqueado espera
la retransmisión de TCP de Linux (~15 min con `tcp_retries2` por defecto): sería
cambiar un cuelgue de 130 s por uno de 15 min. `tcp_user_timeout` = 60 s acota
eso; los keepalives (30/10/3) mantienen vivo el flujo en la tabla de SNAT
durante las esperas largas. No afectan a las consultas largas de los build: el
servidor acusa los keepalives aunque esté calculando, y `tcp_user_timeout` solo
cuenta datos enviados SIN acuse. En Windows (puesto) libpq ignora lo que no
soporta.

**Reintento de PÁGINA sí, de TABLA dentro del paso no.** La página es
idempotente con la comprobación de R11 (las tablas de `raw` tienen PK en
`id_column`, `ensure_raw_table(primary_key=…)`, y la página viene ordenada por
ese id por el keyset de `stream_table`). Reintentar la tabla entera
(`obrparpre` ≈ 20 min) dentro del paso queda cubierto por la reanudación del job
(R23), que repite SOLO la tabla caída. Dos niveles bastan.

**`connect_timeout` = 15 s** (no 10): una apertura sana tarda < 1 s, y 15 deja
margen a un TLS + SCRAM lento sin acercarse a los 130 s. Peor caso de R3: 4 × 15
+ 2 + 4 + 8 = 74 s, menos que el cuelgue que sustituye. Ver D1.

## 5 · Clases y funciones

**Dominio · `domain/reanudacion.py`**
- `VENTANA_REANUDACION = timedelta(hours=8)` — el `replicaTimeout` es 7 h.
- `PASOS_NUNCA_OMITIBLES = frozenset({"apply_grants"})`.
- `sufijo_de_ejecucion_job(nombre: str) -> str` — `sha256(nombre)[:6]`, mismo
  ancho que `BYTES_DEL_SUFIJO`.
- `pasos_a_omitir(orden: Sequence[tuple[str, Sequence[str]]], terminados:
  AbstractSet[str]) -> frozenset[str]` — recorre en orden topológico; omite si
  `nombre in terminados`, no está en `PASOS_NUNCA_OMITIBLES` y todas sus
  dependencias están ya omitidas.
- `tablas_a_omitir(declaradas: Iterable[str], terminados: AbstractSet[str]) ->
  frozenset[str]` — `ingest_raw.<t>` en `SUCCESS` ∩ declaradas (excluye
  `ingest_raw.firma_origen` por construcción).

**Dominio · `domain/ejecucion.py`**: `nueva_ejecucion(…, sufijo=…)` ya admite
sufijo; nueva `ejecucion_desde_batch(batch_id) -> Ejecucion` que parsea el
instante con `FORMATO_INSTANTE` (ValueError si no casa).

**Infraestructura · `reintento_conexion.py`**
- `es_error_transitorio(exc: BaseException) -> bool` — R3/R4. Orden: marca de
  autenticación o clase `28`/`3D000` → False; `ConnectionTimeout` → True;
  `OperationalError` con `sqlstate` `08…`/`53300`/`57P03` o sin `sqlstate` → True;
  resto → False.
- `abrir_con_reintento(abrir: Callable[[], Connection], *, intentos: int,
  dormir: Callable[[float], None] = time.sleep) -> tuple[Connection, float, int]`
  — tenacity (`stop_after_attempt`, `wait_exponential(min=2, max=30)`,
  `retry_if_exception(es_error_transitorio)`, `sleep=dormir`, `reraise=True`);
  devuelve conexión, segundos e intentos; log `pg_conexion_reintento` en
  `before_sleep`.
- `psycopg_en_debug()` — context manager que pone `logging.getLogger("psycopg")`
  en DEBUG y restaura el nivel previo en `finally`.

**Infraestructura · `PostgresClient`**
- `__init__(…, connect_intentos: int = 4, dormir=time.sleep)`; atributo
  `conexiones_abiertas: int`.
- `_connect(conninfo, *, autocommit=False)` → `abrir_con_reintento` sobre
  `psycopg.connect` (dentro de `psycopg_en_debug()`); luego `SET ROLE` como hoy
  (sin reintento, R7); `pg_conexion_lenta` si > 2 s o intentos > 1 (R16).
- `sesion_de_carga(schema, table, columns, *, id_column, tiemod_column=None)` —
  context manager que entrega una `SesionDeCarga` y la cierra en `finally` (R13).
- `fetch_terminados_en_lote(batch_id: str) -> frozenset[str]` — steps en
  `SUCCESS` del lote (con y sin punto).
- `buscar_lote_reanudable(sufijo: str, desde: datetime) -> str | None`.

**Infraestructura · `sesion_carga.py`**
- `MedidaPagina(filas: int, copy_s: float, pg_connect_s: float, reintentos: int)`.
- `SesionDeCarga.copiar_pagina(filas: Sequence[dict]) -> MedidaPagina` — abre
  la conexión perezosa en la primera página (su tiempo va a `pg_connect_s` de
  esa página); COPY + COMMIT; si `OperationalError` con `conn.broken`/`closed`:
  cierra, reconecta (`client._connect`), aplica R11 y reintenta hasta 3 veces;
  cualquier otro error, rollback y propaga (R12). `id_column` obligatorio.

**Aplicación · `IngestRawStep`**: `__init__(…, tablas_terminadas: frozenset[str]
= frozenset())`. En `run`, las tablas omitidas se registran como
`ingest_raw_tabla_reanudada` y no llaman a `_ingest_one_table`. En
`_ingest_one_table`: iterador explícito con `perf_counter` alrededor de `next()`
(`http_s`), `sesion.copiar_pagina(batch)`, `ingest_pagina` (R14).

**Aplicación · `Orchestrator`**: `__init__(steps, recorder=None, *,
terminados_en_lote=frozenset(), tras_paso=None)`. En `run_all`, calcula
`omitidos = pasos_a_omitir([(s.name, s.depends_on) for s in ordenados],
terminados_en_lote)`. Omitido → `StepResult(status=SUCCESS, metadata={"reanudado":
True})`, sin `_record` (R22). Ejecutado → como hoy, y después `tras_paso(step,
r)` envuelto en try/except (aviso y sigue). `run_one` no cambia.

**Composición · `main.py`**
- `PASOS_CON_PERMISOS: tuple[str, ...]` (R25, los diez build).
- `_permisos_tras_paso(settings, pg, recorder) -> Callable` — si
  `step.name in PASOS_CON_PERMISOS`: `ApplyGrantsStep(settings, client=pg).run()`;
  copia el resultado con `step_name = f"apply_grants.tras_{step.name}"` y lo
  graba; si `FAILED` o excepción → `permisos_tras_paso_fallidos` (R26).
- `run_all`: `nombre = os.environ.get("CONTAINER_APP_JOB_EXECUTION_NAME")`;
  `_arrancar_ejecucion(pg, ejecucion_job=nombre)` busca/adopta (R18-R20) y
  después aborta huérfanas como hoy; si se adoptó, `terminados =
  pg.fetch_terminados_en_lote(batch)` (fallo → aviso y vacío).

## 6 · SQL (constantes de `postgres_client.py`, sin DDL)

```sql
-- SQL_LOTE_REANUDABLE: sin LIKE para no mezclar % con parámetros
SELECT batch_id FROM _meta.etl_runs
WHERE right(batch_id, 7) = %(cola)s AND started_at >= %(desde)s
ORDER BY batch_id DESC LIMIT 1;
-- SQL_TERMINADOS_EN_LOTE
SELECT DISTINCT step FROM _meta.etl_runs
WHERE batch_id = %(batch)s AND status = 'SUCCESS';
-- SQL_FILAS_EN_RANGO (R11): identificadores con sql.Identifier
SELECT count(*) FROM {schema}.{table} WHERE {id} BETWEEN %(lo)s AND %(hi)s;
```

`cola` = `'-' + sufijo`. Índices: `idx_etl_runs_*` y la PK de `raw`.

## 7 · Despliegue MANUAL (humano, tras APROBADO y merge)

1. `powershell -NoProfile -File infra/70_build_image.ps1` (anotar el tag).
2. `powershell -NoProfile -File infra/85_update_job.ps1 -Tag <tag>`. Sin
   variables nuevas en el job; sin DDL; el diccionario v60 lo publica la propia
   nocturna con la imagen nueva (no publicar desde el puesto antes: memoria
   «publicar el diccionario solo con su imagen»).
3. Primera nocturna: comprobar en Log Analytics que aparece
   `ejecucion_job=<nombre>` en el arranque (D3), `ingest_pagina` por página,
   `conexiones_abiertas` en la `metadata` de `ingest_raw` y filas
   `apply_grants.tras_*` en `SUCCESS`.
4. Medir el coste de los permisos por paso (D4): `SELECT step,
   finished_at - started_at FROM _meta.etl_runs WHERE batch_id = '<lote>' AND
   step LIKE 'apply_grants%'`.
5. Contar 7 noches (R31) con §8 y anotar cada una en `progress/current.md`.

## 8 · Medición de la aceptación (R31)

`_meta.etl_runs`: `SELECT batch_id, step, status, started_at FROM
_meta.etl_runs WHERE started_at >= '<día>' AND (step LIKE 'ingest_raw%' AND
status IN ('FAILED','ABORTED'));` — cero filas. Reintento de réplica:
`az containerapp job execution list` (una sola réplica por ejecución).

Huecos > 100 s entre páginas (KQL, workspace del entorno del job), y su
atribución por `ingest_pagina`:

```
ContainerAppConsoleLogs_CL
| where Log_s has "ingest_pagina"
| extend j = parse_json(Log_s)
| project ts = todatetime(j.timestamp), tabla = tostring(j.table), page = toint(j.page),
          http_s = todouble(j.http_s), pg_connect_s = todouble(j.pg_connect_s),
          copy_s = todouble(j.copy_s), exec = ContainerGroupName_s
| where http_s > 100 or pg_connect_s > 100 or copy_s > 100
```

Control independiente: la consulta H6 del diagnóstico (`sigrid_stream_page`,
`gap_s > 100`); cada hueco suyo debe tener su `ingest_pagina` que lo explique.

## 9 · Recomendaciones fuera de alcance (escrituras en Azure: decide el humano)

- **Logs del servidor** (`PostgreSQLLogs` en la configuración de diagnóstico, o
  `logfiles.download_enable`): con `log_connections` ya activo, diría si el
  servidor llega a ver la conexión colgada. Afecta al servidor compartido.
- **No mover la hora** (paradas de 00:09 a 00:46, servidor ocioso). **VNet +
  NAT Gateway**, solo si 7 noches con este arreglo no bastan.
- Fijar versiones (`psycopg`, imagen base), feature aparte; y sigue pendiente
  la bajada del servidor de B2s a B1ms.

## 10 · Riesgos y alternativas descartadas

- **La omisión depende de que `depends_on` declare las dependencias de
  DESTRUCCIÓN** (como `build_cierre` → `build_mart`). Una no declarada podría
  dejar un objeto destruido sin recrear tras reanudar; el guardián
  `check-declarados` del final de `run-all` lo detecta y sale con 1.
- **Un lote con dos intentos**: `timings`/`perfil-carga` verán dos filas del
  mismo paso en el lote (FAILED y SUCCESS). Es lo que ocurrió; se documenta en
  la ficha (R29), no se oculta.
- **Permisos por paso ×10**: coste sin medir (D4). Si es alto, se reduce la
  lista `PASOS_CON_PERMISOS`; la autoridad sigue siendo el `apply_grants` final.
- **Descartado: conceder solo el esquema del paso** (más barato): saltaría la
  búsqueda de vistas que filtran del perfil restringido y le daría lectura
  temporal de algo que el final le revocaría. Se reutiliza el paso entero.
- **Descartados**: lote por ventana temporal sin identidad del job (confundiría
  un `run-all` manual con el reintento); diez pasos `apply_grants_*` en el DAG
  (diez pasos más en `v_frescura` y en los nocturnos; la sub-fila con punto no
  sale en `v_frescura` ni en `v_raw_state`); subir `page_size` (lo absorbe R8).

## 11 · Lo que NO se toca

`ApplyGrantsStep` (se reutiliza tal cual) y su `depends_on`; `infra/sql/`;
`infra/env/*.json` (ni reintentos, ni `replicaTimeout`, ni cron);
`sigrid_api_client.py`; `domain/coherencia.py`; `ingest_descompuestos` (gana
el reintento vía `_connect`); el DDL de `_meta`; `abortar_runs_huerfanos`.

## 12 · Decisiones del humano (CERRADAS el 2026-10-23: todas según la propuesta)

D1 15 s · D2 30/10/3 y 60 s · D3 sí · D4 sí, medir y recortar si > ~30 s · D5 rigor `critico` · D6 7 noches · D7 todas las páginas.

- **D1** `connect_timeout` 15 s (propuesto) o 10 s.
- **D2** Valores de keepalives (30/10/3) y `tcp_user_timeout` 60 s (§4).
- **D3** Identidad del lote por `CONTAINER_APP_JOB_EXECUTION_NAME` (variable
  documentada por Microsoft para jobs; se confirma en la primera nocturna). Si
  no estuviera, la reanudación no se activa y todo funciona como hoy.
- **D4** Permisos completos tras cada uno de los diez build; medir y, si cuesta
  más de ~30 s cada uno, recortar la lista.
- **D5** Rigor: la feature está en `estandar`; toca las conexiones al servidor
  compartido y el camino de los permisos del perfil restringido. Propuesta:
  subir a `critico` (campaña de mutación entera).
- **D6** N = 7 noches (propuesto). Un hueco de `http_s` > 100 s no rompe la
  racha y se remite a `sigrid-api` (hipótesis B del diagnóstico).
- **D7** `ingest_pagina` en TODAS las páginas (~3.000 líneas más por noche) o
  solo las lentas (> 5 s). Propuesto: todas, hasta cerrar la causa de fondo.
