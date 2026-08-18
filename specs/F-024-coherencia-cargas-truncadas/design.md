<!-- specs/F-024-coherencia-cargas-truncadas/design.md -->
# F-024 · Coherencia del datamart ante cargas truncadas — Diseño técnico

## 1 · La idea en un párrafo

No se hace nada atómico. Se hace **trazable y verificable**: cada ejecución
que escribe lleva un `batch_id`; toda fila de `_meta.etl_runs` lo lleva;
de esa tabla —que ya escriben todos los pasos— se derivan dos vistas
(`_meta.v_raw_state`, `_meta.v_frescura`) que leen por igual la puerta del
pipeline, el comando de diagnóstico, el MCP y Power BI. Al arrancar
cualquier comando que escribe se cierran las filas `RUNNING` que dejó un
proceso muerto (`ABORTED`, con motivo). Antes de construir `stg` se exige
que todo `raw` provenga del mismo batch terminado en `SUCCESS`; antes de
construir `mart` (DA-5), que el último `stage` terminara. Y una alerta
externa al ETL avisa si `mart` lleva más de N horas sin un build completo.

Encaje hexagonal: la lógica de decisión (identidad de ejecución, veredicto
de coherencia, formato) es **dominio puro**; los steps y la CLI
(**application** / composición en `main.py`) la orquestan; `PostgresClient`
y el DDL de `_meta` (**infrastructure**) leen y escriben. El
`Orchestrator` no cambia.

## 2 · Decisiones abiertas

Están en `requirements.md` §«Decisiones que debe tomar el humano» (DA-1 a
DA-8), con opciones y recomendación. Este diseño desarrolla la opción
recomendada de cada una; si el humano elige otra, se enmienda aquí con
fecha antes de implementar.

## 3 · Ficheros a crear

| Fichero | Contenido | Capa |
|---|---|---|
| `etl_sigrid/domain/ejecucion.py` | `@dataclass(frozen, slots) Ejecucion(batch_id: str, iniciada_en: datetime)`; `nueva_ejecucion(ahora: datetime \| None = None, sufijo: str \| None = None) -> Ejecucion` (formato `YYYYMMDDTHHMMSSZ-xxxxxx`, sufijo `secrets.token_hex(3)` si no se inyecta); constante `MOTIVO_HUERFANA` (plantilla del `error_message` de R4). Cero imports de infraestructura. | domain |
| `etl_sigrid/domain/coherencia.py` | `EstadoTablaRaw(tabla, status, batch_id, started_at, finished_at, filas)`, `EstadoPaso(step, status, batch_id, id, started_at, finished_at)`, `VeredictoCoherencia(ok: bool, batch_id: str \| None, faltantes, no_exitosas, sin_batch, batches_distintos)`; `evaluar_coherencia_raw(estados, tablas_requeridas) -> VeredictoCoherencia`; `formatear_veredicto_raw(v) -> str` (R9); `evaluar_coherencia_stg(ultimo: EstadoPaso \| None) -> VeredictoCoherencia`; `formatear_veredicto_stg(v) -> str`. Funciones puras, deterministas (orden estable por nombre de tabla). | domain |
| `etl_sigrid/infrastructure/postgres/frescura.py` | `FilaFrescura` (las 8 columnas de `v_frescura`), `format_frescura(filas, umbral_horas, paso, ahora) -> tuple[str, str]` (texto + veredicto `FRESCO`/`CADUCADO`/`SIN BUILD REGISTRADO`), `format_estado_raw(estados, veredicto) -> str` (R20), constante `UMBRAL_FRESCURA_HORAS = 30`. Mismo patrón que `timings.py`: puro, sin BBDD. | infrastructure (formato) |
| `infra/95_create_alert_frescura.ps1` | Regla de consulta programada (DA-3 = A). Detalle en §8. | infra |
| `tests/test_f024_dominio.py` | R1, R8, R9 (`ejecucion.py`, `coherencia.py`). | tests |
| `tests/test_f024_steps.py` | R3, R10, R11 (parte step), R12, R13 (mapeo), R15 con `PgFalso`. | tests |
| `tests/test_f024_cli.py` | R4, R5, R7, R11 (opción), R14, R18, R19 (códigos) con `CliRunner` y dobles de `main.get_settings`, `main._get_pg` y las clases de step. | tests |
| `tests/test_f024_meta_y_formato.py` | R2, R6, R13 (DDL), R16, R17, R19 (formato y cruce con dev.json), R20, R21 (orquestador). | tests |
| `tests/test_f024_infra_alerta.py` | R21 (script), R22. Reutiliza los helpers de `tests/test_f003_infra.py` (`_config`, `_script`, `_ps1`) importándolos, no copiándolos. | tests |

## 4 · Ficheros a modificar

| Fichero | Qué cambia |
|---|---|
| `etl_sigrid/infrastructure/postgres/sql/ddl/00_meta.sql` | Se AÑADE al final, sin tocar el `CREATE TABLE`: `ALTER TABLE _meta.etl_runs ADD COLUMN IF NOT EXISTS batch_id TEXT NULL;` `CREATE INDEX IF NOT EXISTS idx_etl_runs_batch ON _meta.etl_runs (batch_id);` y las dos vistas `CREATE OR REPLACE VIEW _meta.v_raw_state` y `_meta.v_frescura` (§6). El fichero lo ejecuta `_bootstrap_schemas_and_meta` en la primera conexión de cada proceso: por eso todo es idempotente y por eso las vistas existen antes de que nadie las consulte. |
| `etl_sigrid/domain/entities.py` | `StepStatus.ABORTED = "ABORTED"` (vocabulario; ningún `StepResult` vivo lo usa, lo usan `format_timings` y el SQL de la marca a través de `.value`). |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | `record_run_start(stage, step, batch_id: str \| None = None)`; `record_run_completed(..., batch_id: str \| None = None)`; nuevos: `abortar_runs_huerfanos(batch_id: str, ahora: datetime \| None = None) -> list[tuple[int, str, datetime]]` (UPDATE ... WHERE status='RUNNING' RETURNING id, step, started_at), `fetch_estado_raw() -> list[EstadoTablaRaw]` (SELECT de `_meta.v_raw_state`), `fetch_ultimo_intento_stg() -> EstadoPaso \| None` (SELECT ... WHERE step LIKE 'build_stg%' ORDER BY id DESC LIMIT 1), `fetch_frescura() -> list[FilaFrescura]` (SELECT de `_meta.v_frescura`). Constantes SQL a nivel de módulo (como `SQL_OCUPACION_DISCO`) para que los tests estáticos las lean. |
| `etl_sigrid/infrastructure/postgres/step_run_recorder.py` | `PostgresStepRunRecorder(client, batch_id: str \| None = None)`; pasa `batch_id` a `record_run_completed`. |
| `etl_sigrid/infrastructure/postgres/timings.py` | `format_timings(timings, ahora: datetime \| None = None)`; constante `UMBRAL_HUERFANA_HORAS = 6`; pie de aviso de R6. Sin cambiar columnas. |
| `etl_sigrid/application/steps/ingest_raw_step.py` | Parámetro `batch_id: str \| None = None` en el constructor; se pasa a `record_run_start`. Nada más: la ingesta no cambia (F-011 la cambiará). |
| `etl_sigrid/application/steps/build_stg_step.py` | Parámetros `batch_id: str \| None = None` y `omitir_puerta: bool = False`. Nuevo método `_puerta_raw(pg) -> VeredictoCoherencia` llamado al principio de `run()`, ANTES de `_preflight_check`: lee `pg.fetch_estado_raw()`, tablas requeridas = `[t["source_table"] for t in settings.tables_sigrid["tables"]]`, evalúa, registra `build_stg.puerta_raw` (`SUCCESS` / `FAILED` / `SKIPPED` según R10-R11), y en KO sin omisión devuelve `FAILED` sin tocar nada. `batch_id` se pasa a todos los `record_run_start` (sub-pasos y tramos). |
| `etl_sigrid/application/steps/build_mart_step.py` | (DA-5) Parámetros `batch_id`, `omitir_puerta`; `_puerta_stg(pg)` al principio de `run()` con `pg.fetch_ultimo_intento_stg()` y `evaluar_coherencia_stg`; registra `build_mart.puerta_stg` con `record_run_start/end`. El resto intacto. |
| `main.py` | (1) helper `_arrancar_ejecucion(pg) -> Ejecucion`: crea la ejecución, llama a `pg.abortar_runs_huerfanos(batch_id)` dentro de `try/except` (R7), loguea WARNING por fila. (2) helper `_ejecutar_paso(step, pg, ejecucion) -> StepResult`: `step.run()`, `PostgresStepRunRecorder(pg, batch_id).record(step.stage, result)` en `try/except`, `_print_result`, `sys.exit(1)` si `FAILED`. (3) Los comandos `ingest`, `load-aux`, `stage`, `build-mart`, `build-cierre`, `build-maestros`, `apply-grants` pasan a: `pg=_get_pg(); ej=_arrancar_ejecucion(pg); _ejecutar_paso(Step(settings, batch_id=ej.batch_id, ...), pg, ej)`. `build-compras` y `build-retenciones` solo añaden `_arrancar_ejecucion(pg)` al principio. (4) `run-all`: `ej=_arrancar_ejecucion(pg)`, `build_pipeline_steps(settings, full_refresh, batch_id=ej.batch_id)`, `PostgresStepRunRecorder(pg, ej.batch_id)`. (5) `stage` y `build-mart` ganan `--sin-puerta`; `run-all` NO. (6) `timings` pasa `ahora=datetime.utcnow()`. (7) Comandos nuevos `check-coherencia` y `check-frescura` (§7). La docstring de cabecera de `main.py` lista los dos comandos nuevos. |
| `infra/env/dev.json` | `frescuraAlertName` (p. ej. `alert-caj-datamart-seg-dev-frescura`), `frescuraUmbralHoras` (30) y su `$aviso_frescura`. |
| `infra/README.md` | Fila del script 95 en la tabla (después del 90), sección «Probar la alerta de frescura» (R23), la KQL de coherencia, y la nota de que `az extension add --name scheduled-query` hace falta una vez. |
| `docs/ARCHITECTURE.md` | Sección nueva «Coherencia ante cargas truncadas (F-024)»: batch, huérfanas, puertas, vistas de `_meta`, `--sin-puerta`, alerta de frescura; y la corrección de DA-8 si el humano la confirma. Frases sin cadenas largas con `/`. |
| `azure-apps/datamart_seg_anual.md` (repo `azure-apps`) | Lo que exponemos: `_meta.v_frescura` y `_meta.v_raw_state` para MCP y Power BI; la alerta de frescura y su umbral; que un `raw` mezclado ya no llega a `mart`. En el mismo trabajo. |

## 5 · Ficheros que NO se tocan

- `etl_sigrid/application/orchestrator.py`: el batch viaja por el grabador
  y por los steps; el DAG y `_record` quedan como están.
- `etl_sigrid/domain/tramos.py`, `sql/stg/08_plan_mensual.sql` y el resto
  de SQL de `stg/`, `mart/`, `cierre/`, `compras/`, `maestro/`,
  `retenciones/`, `auxiliar/`: ni una línea de negocio.
- `etl_sigrid/infrastructure/postgres/fingerprint.py`, `grants.py`
  (`_meta` ya está en los esquemas de consumo y el GRANT cubre vistas).
- `infra/80_create_job.ps1`, `85_update_job.ps1`, `90_create_alert.ps1`,
  `Dockerfile` (salvo DA-3 = B, que se enmendaría).
- `.env`, `.env.local.bak`, `harness/`, `CHECKPOINTS.md`.

## 6 · SQL (capa `_meta`, fichero `ddl/00_meta.sql`)

Se añade al final del fichero existente. Es DDL de bootstrap, no una capa
del datamart: no lleva numeración nueva.

```sql
-- F-024 · identidad de ejecución (idempotente; el histórico queda NULL)
ALTER TABLE _meta.etl_runs ADD COLUMN IF NOT EXISTS batch_id TEXT NULL;
CREATE INDEX IF NOT EXISTS idx_etl_runs_batch ON _meta.etl_runs (batch_id);

-- F-024 · última ingesta por tabla de raw (lo que lee la puerta de stage,
-- check-coherencia y el MCP). Una fila por tabla; la más reciente manda.
CREATE OR REPLACE VIEW _meta.v_raw_state AS
SELECT DISTINCT ON (step)
       substr(step, length('ingest_raw.') + 1) AS tabla,
       status, batch_id, started_at, finished_at, rows_processed AS filas, id AS run_id
FROM _meta.etl_runs
WHERE step LIKE 'ingest_raw.%'
ORDER BY step, started_at DESC, id DESC;

-- F-024 · frescura por paso de pipeline (steps sin punto): último OK y
-- último intento por separado, porque no son la misma noticia.
CREATE OR REPLACE VIEW _meta.v_frescura AS
WITH pasos AS (
    SELECT * FROM _meta.etl_runs WHERE position('.' IN step) = 0
),
ultimo_ok AS (
    SELECT DISTINCT ON (step) step, finished_at, batch_id, rows_processed
    FROM pasos WHERE status = 'SUCCESS'
    ORDER BY step, finished_at DESC NULLS LAST, id DESC
),
ultimo_intento AS (
    SELECT DISTINCT ON (step) step, started_at, status, error_message
    FROM pasos
    ORDER BY step, started_at DESC, id DESC
)
SELECT i.step                                   AS paso,
       o.finished_at                            AS ultimo_ok_finished_at,
       o.batch_id                               AS ultimo_ok_batch_id,
       o.rows_processed                         AS ultimo_ok_filas,
       EXTRACT(EPOCH FROM (now() AT TIME ZONE 'UTC' - o.finished_at)) / 3600.0
                                                AS horas_desde_ultimo_ok,
       i.started_at                             AS ultimo_intento_started_at,
       i.status                                 AS ultimo_intento_status,
       i.error_message                          AS ultimo_intento_error
FROM ultimo_intento i
LEFT JOIN ultimo_ok o USING (step);
```

Notas:

- `started_at`/`finished_at` son `TIMESTAMP` sin zona escritos con
  `datetime.utcnow()`; por eso `now() AT TIME ZONE 'UTC'`. Si alguna vez se
  migra a `timestamptz`, esta es la única línea que cambia.
- `CREATE OR REPLACE VIEW` no admite quitar o reordenar columnas: si una
  enmienda futura cambia columnas, hará falta `DROP VIEW IF EXISTS` antes
  (y `apply-grants` después). Se anota aquí para no descubrirlo en Azure.
- Ninguna vista lee de `raw`, `stg` ni `mart`: solo de `_meta`. Cero coste
  sobre el servidor compartido.

## 7 · Comportamiento exacto

### 7.1 · Marca de huérfanas (R4–R7)

```
UPDATE _meta.etl_runs
SET status = 'ABORTED', finished_at = %(ahora)s,
    error_message = %(motivo)s
WHERE status = 'RUNNING'
RETURNING id, step, started_at
```

`motivo` = `MOTIVO_HUERFANA.format(batch_id=..., ahora=...)`. Se ejecuta
una vez por proceso, en `_arrancar_ejecucion`, antes de construir ningún
step. No filtra por antigüedad (todas las `RUNNING` que existan al arrancar
son de otro proceso por definición) ni por batch (las nuestras aún no
existen). Riesgo de dos procesos simultáneos: `requirements.md` §Riesgos.

### 7.2 · Puerta de `raw` (R8–R13)

Entrada: `estados = pg.fetch_estado_raw()` (una `EstadoTablaRaw` por
tabla presente en `v_raw_state`) y `requeridas` (source_table del YAML).

```
faltantes        = requeridas − {e.tabla}
no_exitosas      = {e : e.tabla ∈ requeridas ∧ e.status ≠ 'SUCCESS'}
sin_batch        = {e : e.tabla ∈ requeridas ∧ e.status = 'SUCCESS' ∧ e.batch_id IS NULL}
batches          = {e.batch_id → [e...] : e.tabla ∈ requeridas ∧ e.status = 'SUCCESS' ∧ e.batch_id NOT NULL}
ok               = ¬faltantes ∧ ¬no_exitosas ∧ ¬sin_batch ∧ |batches| = 1
batch_id (si ok) = la única clave de batches
```

Casos y qué pasa (con la política DA-2 = A):

| Situación | Veredicto | `stage` suelto | `run-all` |
|---|---|---|---|
| Noche normal: ingesta completa SUCCESS, batch B | OK | construye | construye |
| Muerte externa durante la ingesta: tablas 1..k con B_new, resto B_old, tabla k+1 `RUNNING`→`ABORTED` | KO (`no_exitosas` + `batches_distintos`) | FAILED en `puerta_raw`, sale 1 | no llega: `ingest_raw` no terminó y `build_stg` queda `SKIPPED` |
| `ingest --table X` en local, resto de otro batch | KO (`batches_distintos`) | FAILED; o `--sin-puerta` registrado `SKIPPED` | n/a |
| Primera vez tras desplegar, raw anterior a F-024 | KO (`sin_batch`) | FAILED con mensaje «histórico sin batch: `ingest --full` o `--sin-puerta`» | OK: la ingesta de esa misma noche estampa el batch |
| Tabla nueva en el YAML aún no ingerida | KO (`faltantes`) | FAILED | OK tras la ingesta de la noche |
| Una tabla falló en la ingesta (`stop_on_error=False`) | KO (`no_exitosas`) | FAILED | no llega (`ingest_raw` FAILED) |

La puerta se registra siempre como sub-paso `build_stg.puerta_raw` con
`record_run_start/end` (así aparece en `timings` con su duración, que
debe ser de milisegundos: dos SELECT sobre `_meta`).

### 7.3 · Puerta de `stg` (R15, DA-5)

`ultimo = pg.fetch_ultimo_intento_stg()` (fila con mayor `id` entre
`step LIKE 'build_stg%'`). OK sii `ultimo` existe, `ultimo.step ==
'build_stg'` y `ultimo.status == 'SUCCESS'`. La fila de paso `build_stg`
se inserta al terminar el step (por el orquestador o por
`_ejecutar_paso`), así que es la de mayor `id` solo si el step terminó; un
proceso muerto deja como última un sub-paso o tramo `RUNNING`/`ABORTED`.
Se registra como `build_mart.puerta_stg`.

### 7.4 · CLI (R4, R11, R14, R18, R19)

- `_arrancar_ejecucion(pg)`: única puerta de entrada de los comandos que
  escriben. Que la lista de comandos sea exactamente la de las convenciones
  lo fija el test parametrizado de R4/R5.
- `_ejecutar_paso(step, pg, ejecucion)`: concentra lo que hoy repiten
  siete comandos (`run` + `_print_result` + `exit 1`) y añade el registro.
  Menos líneas en `main.py`, no más.
- `check-coherencia`: `estados = pg.fetch_estado_raw()`; `v =
  evaluar_coherencia_raw(...)`; imprime `format_estado_raw`; si DA-5,
  también `fetch_ultimo_intento_stg` + `evaluar_coherencia_stg`; código
  0/1/2. Nunca llama a `_arrancar_ejecucion`.
- `check-frescura --umbral-horas N --paso build_mart`: `filas =
  pg.fetch_frescura()`; `texto, veredicto = format_frescura(filas, N, paso,
  ahora)`; código 0 si `FRESCO`, 1 si no, 2 si excepción de lectura.

### 7.5 · Cómo se prueba SIN BBDD

- **Dominio**: funciones puras con fixtures de `EstadoTablaRaw` /
  `EstadoPaso`.
- **Steps**: `PgFalso` (patrón de `tests/test_f019_tramos.py`) con traza de
  llamadas (`estado_raw`, `record_start`, `record_end`, `truncate`,
  `sql`...) inyectado por `monkeypatch.setattr(modulo,
  "build_postgres_client", lambda _s: pg)`; se afirma el ORDEN de la traza
  (la puerta antes que el preflight, ningún `sql` tras un KO).
- **CLI**: `CliRunner` con `monkeypatch` de `main.get_settings` (objeto
  mínimo con `postgres`, `logging`, `tables_sigrid`), `main._get_pg` (el
  `PgFalso`) y las clases de step (`main.IngestRawStep`, ...) por dobles
  que devuelven un `StepResult` prefijado. Es el patrón de
  `test_cli_version.py` llevado a los comandos que escriben.
- **SQL y `.ps1`**: lectura estática de `00_meta.sql` y del script (regex
  sencillas: `ADD COLUMN IF NOT EXISTS batch_id`, `CREATE OR REPLACE VIEW
  _meta.v_frescura`, columnas, tokens de la KQL, `$CFG.`, ausencia de
  nombres). Igual que R6 de F-019: no validan SQL completo (eso lo hacen
  R24–R26 en BBDD real), pero convierten la regresión más probable en rojo
  inmediato.
- **Cobertura y mutación** (rigor `critico`): la lógica vive en funciones
  puras y en helpers pequeños precisamente para que la campaña de mutación
  tenga poco código de pegamento; los comandos de la CLI son de tres
  líneas.

## 8 · La alerta de frescura (DA-3 = A)

`infra/95_create_alert_frescura.ps1`, mismo esqueleto que
`90_create_alert.ps1` (carga `00_vars.ps1`, `Invoke-Az`, `Confirmar-Exito`,
`Get-EtiquetasCli`, idempotencia por `show`):

```
$horas   = [int]$CFG.frescuraUmbralHoras            # 30
$ventana = "PT{0}H" -f $horas                        # ISO 8601 (30 h)
$kql     = "ContainerAppConsoleLogs_CL | where ContainerAppName_s == '$($CFG.job)' | where Log_s has_all ('step_finished','build_mart','SUCCESS')"

az monitor scheduled-query create -g <rg> -n $CFG.frescuraAlertName `
    --scopes <id del workspace $CFG.logAnalytics> `
    --condition "count 'Frescura' < 1" `
    --condition-query Frescura=$kql `
    --window-size $ventana --evaluation-frequency PT1H `
    --severity 2 --auto-mitigate true `
    --action-groups <id del action group> `
    --description "El datamart lleva mas de $horas h sin un build_mart completo"
```

- **Sintaxis a confirmar en Fase A** (T3): la forma exacta de `--condition`
  / `--condition-query` y si `--window-size` admite `PT30H` o exige `P1DT6H`
  (`az monitor scheduled-query create --help` tras `az extension add`). El
  script no se ejecuta contra Azure sin haberlo confirmado; ese es el
  «cualquier tercer camino no se improvisa» de `90_create_alert.ps1`.
- La columna del nombre del job en `ContainerAppConsoleLogs_CL`
  (`ContainerAppName_s` según el README de F-003) se confirma con
  `| getschema` en Fase A; si es otra, se corrige el script Y el README.
  También se confirma a mano que `has_all` casa con `step_finished` (KQL
  tokeniza por términos alfanuméricos y el guion bajo puede partirlo); si
  no, se usa `contains` para ese término y se anota.
- Por qué `count < 1` sobre una ventana de 30 h evaluada cada hora, y no
  «edad del último evento»: la ausencia es la señal; una regla que busque
  el último evento no dispara si no hay eventos.
- Falso positivo asumido: si el humano reconstruye `mart` desde el puesto
  la regla no lo ve. Es coherente con lo que vigila: «el job hizo su
  trabajo».
- Alternativas: DA-3 en `requirements.md`.

## 9 · Riesgos y decisiones técnicas menores

1. **`error_message` reutilizado para el motivo del ABORTED** en vez de una
   columna nueva `aborted_reason`: menos DDL, y `timings`/`status` ya
   enseñan `error_message`. `metadata` JSONB queda libre para F-011.
2. **La puerta lee `SUCCESS` de la última fila por tabla, no «existe una
   SUCCESS reciente»**: un `FAILED` posterior a un `SUCCESS` significa que
   se intentó recargar y no se sabe qué quedó en la tabla (truncada,
   parcial). Conservador a propósito.
3. **`--sin-puerta` como `SKIPPED` en `_meta`**: no es `SUCCESS` (no se
   verificó) ni `FAILED` (no se paró); `SKIPPED` ya existe en el
   vocabulario y `timings` lo enseña.
4. **`format_timings` sin cambio de columnas**: el aviso va al pie para no
   romper a quien parsee la tabla ni los tests existentes de F-005.
5. **Registro de comandos sueltos y `fetch_timings`**: `timings` ancla en
   el arranque de `ingest_raw`; con DA-6, un `stage` suelto también deja
   fila de paso `build_stg`, que entra en la ventana de la última ejecución
   con `ingest_raw`. Es el comportamiento deseado (se ve todo lo que corrió
   desde la última ingesta), no un efecto colateral.
6. **`horas_desde_ultimo_ok` calculado en la vista** y no en Python: Power
   BI y el MCP lo leen sin lógica; `check-frescura` recalcula con `ahora`
   inyectado solo para ser testeable.
7. **`bootstrap` no marca huérfanas**: solo DDL. Si alguien lo quiere, es
   una línea; no se hace por defecto para no escribir en `_meta` desde un
   comando que se ejecuta «para ver si conecta».
8. **`load-aux` registra aunque hoy solo lea y valide** (F-004): así
   `v_frescura` ya tiene la fila `load_excel_aux` cuando F-013 lo convierta
   en carga real.
9. **Extensión `scheduled-query` de `az`**: dependencia del puesto, no del
   repositorio; se documenta en `infra/README.md` como paso previo del
   script 95, igual que la advertencia de `pwsh`.
