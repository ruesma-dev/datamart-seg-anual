<!-- specs/F-024-coherencia-cargas-truncadas/requirements.md -->
# F-024 · Coherencia del datamart ante cargas truncadas — Requisitos (EARS)

**Rigor: `critico`.** Todo lo que se toca aquí escribe en `_meta` del
datamart que vive en `psql-albaranes-rs9k2` (servidor compartido con
`albaranes` y `partes` en producción) y decide si el pipeline nocturno
construye o se niega a construir. Aplica CHECKPOINTS.md nivel `critico`:
fase RED con traza, cobertura de las líneas cambiadas, cero mutantes
supervivientes sin justificación aceptada por el humano y toda verificación
`MANUAL (humano)` con su comando exacto y su resultado real.

## Por qué existe (hechos verificados que la spec asume)

- El 2026-08-18 la primera carga real lanzada desde el job murió por
  `DeadlineExceeded` de Azure a las 2 h justas, en el tramo 39/60 del
  stage. `mart` no se tocó, así que las vistas siguieron mostrando el build
  anterior completo. Pero `_meta.etl_runs` se quedó con dos filas `RUNNING`
  huérfanas (`build_stg.build_plan_mensual` y su `tramo_39`) y
  `stg.plan_mensual` a medias (39/60 tramos). `python main.py timings`
  miente desde entonces: enseña un tramo «en curso» de un proceso muerto.
- La ingesta escribe tabla a tabla, no de golpe. `stage` y `mart` empiezan
  con `TRUNCATE`. `stage` va en una transacción por tramo (F-019). Las
  vistas de consumo leen de `mart`, `cierre`, `compras`, `maestro` y
  `retenciones`.
- Hoy `stage` dentro de `run-all` solo arranca si la ingesta terminó
  `SUCCESS` en la MISMA corrida (dependencias del orquestador). Pero nada
  comprueba de qué ejecución viene cada tabla de `raw`, y `python main.py
  stage` suelto construye sobre lo que haya: un `raw` MEZCLADO (tablas de
  ejecuciones distintas tras una ingesta parcial seguida de otro fallo) da
  cuadros que no cuadran y nadie que lo sepa.
- La alerta de Azure (`alert-caj-datamart-seg-dev-failed`, verificada el
  17-ago) cubre «ejecución `Failed`»; los fallos INTERNOS llegan porque
  `run-all` sale con código 1 si algún paso está `FAILED` (verificado). La
  muerte EXTERNA (deadline, OOM, reinicio de nodo) también produce `Failed`
  y correo, pero deja el estado descrito arriba.
- **Se DESCARTA la atomicidad global** (una transacción de 3 h en el B1ms
  es exactamente lo que reventó el 09-ago y F-019 lo troceó a propósito).
  La coherencia se garantiza por **verificación** (puerta antes de
  construir) y **visibilidad** (estado honesto en `_meta`, frescura
  consultable, alerta).

> **Observación del spec-author, a confirmar por el humano (DA-8).** El
> líder da como hecho que la ingesta es «transaccional POR TABLA». Leyendo
> `PostgresClient.copy_rows` y `IngestRawStep._ingest_one_table`, cada
> página de 10.000 filas va en su propia `connection()` y por tanto en su
> propio COMMIT, y el `TRUNCATE` previo también: una muerte a mitad de tabla
> dejaría esa tabla **truncada y parcial**, no intacta. La puerta de esta
> feature **no depende de ello**: la marca de «tabla ingerida» solo se
> escribe cuando la tabla termina en `SUCCESS`, así que una tabla parcial
> queda con su última fila en `RUNNING`→`ABORTED` y la puerta la rechaza.
> Se anota para que el hecho quede corregido donde toque, no para
> re-investigar aquí.

## Convenciones de este documento

- **[AUTO]** — verificable con pytest, sin red ni BBDD (dobles de
  `PostgresClient`, `CliRunner`, lectura estática de SQL y `.ps1`). Nombre
  trazable `test_f024_rN_*`.
- **[MANUAL-local]** — la ejecuta el humano contra su PostgreSQL local
  (`.env.local.bak`).
- **[MANUAL-Azure]** — la ejecuta el humano contra Azure. Solo las
  imprescindibles.
- `PSQL` = `& "C:\Program Files\PostgreSQL\16\bin\psql.exe"`; las opciones
  van ANTES de la cadena de conexión.
- «Comando que escribe» = `run-all`, `ingest`, `load-aux`, `stage`,
  `build-mart`, `build-cierre`, `build-maestros`, `build-compras`,
  `build-retenciones`, `apply-grants`. Todo lo demás (`timings`, `status`,
  `check-*`, `inspect-*`, `fingerprint-views`, `compare-fingerprints`,
  `version`) es de solo lectura. `bootstrap` solo ejecuta DDL idempotente y
  no corre pasos: ni marca ni registra.
- **Ejecución** (o *batch*): una invocación de un comando que escribe. Se
  identifica con un `batch_id` único (Bloque 1). En el job nocturno una
  ejecución = un `run-all --full` completo.

---

## Decisiones que debe tomar el humano ANTES de implementar

> **Enmienda (2026-08-18): TODAS CERRADAS por el humano — «aprobado con las
> recomendadas».** DA-1 → A (`batch_id` en `_meta.etl_runs` + vistas
> `v_raw_state`/`v_frescura`). DA-2 → A (puerta estricta; `--sin-puerta`
> solo en comandos sueltos, registrado y con WARNING). DA-3 → A (regla KQL
> programada sobre `log-datamart-seg-dev`). DA-4 → 30 h. DA-5 → sí (puerta
> también antes de `build_mart`). DA-6 → sí (los comandos sueltos
> registran). DA-7 → solo los comandos que escriben; `timings` avisa.
> **DA-8 CONFIRMADA por el líder leyendo el código**: `truncate_table` y
> cada `copy_rows` abren su propia `connection()` con commit → la ingesta
> hace **commit por página, no por tabla**; una muerte a mitad de tabla la
> deja truncada y parcial. La afirmación «transaccional por tabla» de
> `progress/current.md` y de la cabecera de esta spec era incorrecta; se
> corrige en `docs/ARCHITECTURE.md` en T14. No cambia el diseño: la puerta
> se apoya en el `SUCCESS` de cada tabla, no en su atomicidad.
> **T3 hecha (líder, 2026-08-18)**: extensión `scheduled-query` instalada en
> el puesto; sintaxis confirmada con `--help`: `--condition "count
> 'Frescura' < 1"` + `--condition-query Frescura="<kql>"` + `--window-size`
> y `--evaluation-frequency` en formato `##h##m##s` (NO ISO 8601: `30h`,
> no `PT30H`). **Ojo: esto confirmó la FORMA, no el VALOR — `30h` resultó
> inválido y lo cuenta la enmienda de DA-4 del 2026-08-19.** **La columna del nombre del job en
> `ContainerAppConsoleLogs_CL` es `ContainerJobName_s`, NO
> `ContainerAppName_s`** (verificado con `getschema`; ese nombre no existe).
> La KQL con `has_all('step_finished','build_mart','SUCCESS')` ejecuta sin
> error; devuelve 0 filas a día de hoy porque ningún `build_mart` ha
> terminado aún desde el job (18-ago: dos ejecuciones muertas antes de mart
> y una tercera en curso), que es exactamente lo que la alerta detectaría.

Cada una con opciones y la recomendación del spec-author. Las tareas de
Fase A de `tasks.md` son cerrarlas y anotarlas aquí (enmienda fechada).

### DA-1 · Cómo se identifica la procedencia de cada tabla de `raw`

- **A (recomendada)**: columna `batch_id` en `_meta.etl_runs` (migración
  idempotente, `NULL` en el histórico) y **dos vistas derivadas** en
  `_meta`: `v_raw_state` (última ingesta por tabla: estado, batch, fechas,
  filas) y `v_frescura` (último OK y último intento por paso). Una sola
  fuente de verdad (`etl_runs`, que ya escriben todos los pasos), cero
  tablas nuevas que mantener, y `timings`, la puerta, el MCP y Power BI
  leen lo mismo. Coste: `DISTINCT ON` sobre una tabla pequeña e indexada.
- **B**: tabla propia `_meta.raw_state` (una fila por tabla, escrita al
  terminar cada ingesta). Descartada: segunda fuente de verdad que puede
  divergir de `etl_runs`; y F-011 (incremental) es quien podría necesitar
  una tabla de estado por tabla para su *watermark* — que la cree ella
  cuando sepa qué columnas necesita.

### DA-2 · Política de la puerta ante cargas parciales legítimas y ante el histórico

- **A (recomendada)**: **estricta** por defecto —`build_stg` FALLA si no
  todas las tablas declaradas en `config/tables_sigrid.yaml` provienen del
  mismo batch terminado en `SUCCESS`— con **una** vía de escape explícita:
  la opción `--sin-puerta` **solo en los comandos sueltos** (`stage`,
  `build-mart`), nunca en `run-all`. La puerta se evalúa igual, su
  veredicto queda registrado en `_meta.etl_runs` como `SKIPPED` con el
  motivo, y el log lleva un WARNING. Cubre `ingest --table X` en local y el
  `raw` anterior a F-024 (sin batch): quien construye sobre un raw que no
  puede acreditar lo dice por escrito.
- **B**: comando de «adopción» que estampe el raw actual como un batch
  ficticio. Descartada: fabrica una acreditación que nadie verificó; es el
  mismo silencio que se quiere eliminar, con firma.
- **C**: la puerta solo avisa y sigue. Descartada: es lo que hay hoy.

### DA-3 · Mecanismo de la alerta de frescura

Todas reutilizan el grupo de acción existente (`ag-datamart-seg-dev`) y
ninguna escribe correos en el repositorio.

- **A (recomendada)**: **regla de consulta programada (KQL)** sobre el
  workspace `log-datamart-seg-dev`: dispara si en las últimas
  `frescuraUmbralHoras` no hay ninguna línea de consola del job con el
  evento `step_finished` de `build_mart` en `SUCCESS` (evento que el
  orquestador ya emite; R21 lo fija con test). Ventajas: cero cómputo
  nuevo, cero secretos ni identidades nuevas, y vigila desde FUERA del ETL
  («el job no lo hizo» dispara igual que «el job murió»). Costes: exige
  instalar la extensión `scheduled-query` de `az` en el puesto (verificado
  el 2026-08-18: `az monitor scheduled-query` pide instalarla; un
  `az extension add --name scheduled-query` una vez), depende del esquema
  de `ContainerAppConsoleLogs_CL` (columna `Log_s` verificada en T25 de
  F-003; la del nombre del job se confirma en Fase A) y mide un evento de
  log, no la BBDD: un `build-mart` lanzado desde el puesto no lo apaga
  (falso positivo informativo).
- **B**: **segundo job** `caj-datamart-seg-dev-frescura` (misma imagen e
  identidad, cron `0 8 * * *` UTC) que ejecuta `python main.py
  check-frescura` y sale 1 si `_meta.v_frescura` está caducada; alerta de
  métrica `Executions state includes Failed` sobre ese job (el patrón ya
  verificado en T26). Ventajas: lee la VERDAD de la BBDD, la misma que ven
  MCP y Power BI, y es un canario diario de conectividad. Costes: un job
  más que mantener en `80/85_*.ps1` (imagen, secretos, identidad ×2), una
  alerta más, y ampliar los tests de F-003. Recomendable si el humano
  prefiere que alerta y consumidores lean el mismo dato.
- **C**: alerta de métrica «`Executions` con `state=Succeeded` < 1 en 1
  día» sobre el job actual. Es una línea de `az`, pero la semántica de
  «sin datos» de las alertas de métrica es incierta (por defecto no
  disparan cuando la dimensión no emite) y no distingue `build_mart` del
  resto. Solo si el humano quiere probarla primero por barata; no se
  diseña aquí.
- **D**: alerta de datos de Power BI sobre una tarjeta de `v_frescura`.
  Complementaria, nunca sustituta: si el refresco de PBI falla, no hay
  alerta.

### DA-4 · Umbral de frescura

- **30 h (recomendado)**: el job arranca a las 02:00 UTC y tarda ~3 h 15
  (medido el 18-ago); 30 h cubre una noche entera más la variación de
  duración sin solapar con la siguiente (un umbral de 24 h dispararía
  cada mañana durante la hora en que la carga nueva aún no ha terminado).
- **36 h**: más margen, se entera 6 h más tarde. El valor vive en UN sitio
  (`infra/env/dev.json: frescuraUmbralHoras`) y de ahí sale la ventana de
  la alerta y el default del comando `check-frescura` (R19 lo cruza con
  test).

> **Enmienda (2026-08-19): el criterio sigue siendo 30 h; cambia cómo se
> expresa en la regla.** Al crear la alerta por primera vez, el ARM la
> rechazó:
>
> ```
> (InvalidRequestContent) The request content was invalid and could not be
> deserialized: 'WindowSize of 1800 minutes is not supported. Supported
> granularities are: 5, 10, 15, 30, 45, 60, 120, 180, 240, 300, 360, 720,
> 1440, 2880'
> ```
>
> 1800 min son las 30 h. **`windowSize` no es un valor libre**: solo admite
> esas granularidades, y entre 1440 (24 h) y 2880 (48 h) no hay ninguna, así
> que 30 h **no es expresable como ventana**. Decisión del humano, cerrada:
>
> 1. la **ventana** de la regla es *la menor granularidad admitida que
>    contenga el umbral* → con 30 h, **2880 min (48 h)**;
> 2. el **criterio** de 30 h se aplica **dentro de la consulta**, con un
>    `| where TimeGenerated > ago(30h)` derivado del mismo
>    `frescuraUmbralHoras`.
>
> La ventana es más ancha que el criterio a propósito y no lo relaja: la
> regla lee 48 h de logs y **cuenta solo** los de las últimas 30. El umbral
> sigue viviendo en un solo sitio y la ventana es un valor derivado, nunca
> escrito a mano. Un umbral por encima de 48 h no sería implementable así:
> el script falla antes de llamar a Azure y dice qué clave bajar.
>
> Por qué no lo cazó nadie antes: T3 dio la sintaxis por confirmada «con
> `--help`», y `--help` valida la **forma** (`##h##m##s`), no el **valor**.
> Un `30h` pasa el cliente entero y lo rechaza el servicio al final del
> viaje. R22 gana tests que ejecutan la derivación de verdad.

### DA-5 · Puerta también antes de `build_mart` (coherencia de `stg`)

- **Sí (recomendado)**: mismo mecanismo, coste bajo. Un `stage` muerto a
  medias deja `stg` MEZCLADO (los ficheros `03..07` son atómicos cada uno,
  pero entre sí no: `stg.obras` de esta noche y `stg.presupuesto` de ayer)
  y `python main.py build-mart` suelto construiría encima. La puerta exige
  que el último intento de stage terminó `SUCCESS` (R15).
- **No**: se acepta el hueco en los comandos sueltos porque en Azure solo
  corre `run-all`.

### DA-6 · Los comandos sueltos registran su resultado en `_meta.etl_runs`

- **Sí (recomendado, necesario para que `v_frescura` diga la verdad)**:
  hoy solo `run-all` registra las filas de paso (`build_mart`, `build_stg`,
  ...) vía el orquestador; `python main.py build-mart` suelto no deja
  rastro. Con esta feature los comandos sueltos que ejecutan un step
  registran igual (R18). `build-compras` y `build-retenciones`, que hoy
  ejecutan SQL en línea sin step, quedan fuera de `v_frescura` (aparecen
  como «sin registro»); convertirlos en steps es otra feature.
- **No**: `v_frescura` solo sería fiable para lo que corre desde `run-all`.

### DA-7 · Quién marca las huérfanas

- **Solo los comandos que escriben (recomendado)**: `timings` es de
  lectura y contra Azure no debe escribir nada; en su lugar AVISA al pie
  cuando ve filas `RUNNING` con más de 6 h (R6), y la siguiente ejecución
  que escriba las marca `ABORTED` (R4).
- **También `timings`**: enseña la verdad antes, a cambio de que un
  comando de lectura escriba en `_meta`. Descartada.

### DA-8 · Confirmar la transaccionalidad real de la ingesta

Ver la observación de arriba. No cambia el diseño; cambia una frase de
`docs/ARCHITECTURE.md` y la confianza en «no hubo daño» de futuros
incidentes. Se pide al humano confirmarlo leyendo `copy_rows` o con un
`SELECT count(*)` durante una ingesta local.

---

## Bloque 1 · Identidad de ejecución (`batch_id`)

### R1 · Cada ejecución tiene un identificador único [AUTO]

CUANDO arranca un comando que escribe, el sistema debe generar un
`batch_id` con la forma `YYYYMMDDTHHMMSSZ-xxxxxx` (UTC + 6 hex aleatorios),
único por proceso, ordenable cronológicamente como texto, y usarlo en TODAS
las filas que ese proceso escriba en `_meta.etl_runs`.

Tests: `test_f024_r1_batch_id_tiene_forma_y_es_unico`,
`test_f024_r1_batch_id_ordena_cronologicamente`.

### R2 · `_meta.etl_runs` conserva el histórico y gana `batch_id` [AUTO]

El DDL de `_meta` (`sql/ddl/00_meta.sql`) debe añadir la columna
`batch_id TEXT NULL` y su índice con sentencias idempotentes
(`ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`) sin `DROP` ni
recreación de la tabla, de forma que el histórico anterior a F-024 se
conserve con `batch_id = NULL` y `python main.py timings` siga funcionando
sobre él. `record_run_start` y `record_run_completed` deben aceptar
`batch_id` opcional (los llamantes actuales sin él siguen compilando y
escriben `NULL`).

Tests (estáticos sobre el SQL + doble del cliente):
`test_f024_r2_ddl_meta_migra_sin_destruir`,
`test_f024_r2_record_run_escribe_batch_id_si_lo_recibe`,
`test_f024_r2_llamantes_sin_batch_siguen_funcionando`.

### R3 · `run-all` propaga un único batch a todos los pasos [AUTO]

CUANDO se ejecuta `run-all`, el sistema debe pasar el mismo `batch_id` a
`ingest_raw` (filas por tabla), a `build_stg` (sub-pasos y tramos) y al
grabador del orquestador (filas de paso), de modo que todas las filas de
esa ejecución compartan `batch_id`.

Test: `test_f024_r3_run_all_un_solo_batch_para_todas_las_filas` (dobles:
recorder, ingest y stg falsos; se recogen los batch de cada `record_*`).

---

## Bloque 2 · Filas huérfanas → `ABORTED`

### R4 · Al arrancar un comando que escribe se cierran las huérfanas [AUTO]

CUANDO arranca un comando que escribe, ANTES de ejecutar ningún paso, el
sistema debe marcar toda fila de `_meta.etl_runs` con `status = 'RUNNING'`
como `status = 'ABORTED'`, `finished_at = ahora (UTC)` y `error_message`
con el motivo («huérfana: el proceso que la abrió no la cerró —muerte
externa: deadline, OOM o reinicio—; marcada por la ejecución
`<batch_id>` el `<timestamp>`»), y emitir un WARNING estructurado por fila
marcada (`etl_run_huerfana_abortada` con `id`, `step`, `started_at`).

Tests (CliRunner + dobles; uno por comando de la lista de convenciones):
`test_f024_r4_cada_comando_que_escribe_marca_huerfanas_antes_de_actuar`
(parametrizado), `test_f024_r4_la_marca_actualiza_solo_filas_running`
(SQL del cliente: `WHERE status = 'RUNNING'`, `SET status = 'ABORTED'`,
motivo con batch), `test_f024_r4_warning_por_fila_marcada`.

### R5 · Los comandos de solo lectura no marcan nada [AUTO]

MIENTRAS se ejecuta un comando de solo lectura (`timings`, `status`,
`check-pg`, `check-frescura`, `check-coherencia`, `fingerprint-views`), el
sistema NO debe ejecutar la marca de huérfanas ni ninguna otra escritura en
`_meta`.

Test: `test_f024_r5_los_comandos_de_lectura_no_marcan_huerfanas`
(parametrizado; el doble falla si se le pide abortar).

### R6 · `timings` enseña `ABORTED` y avisa de las `RUNNING` sospechosas [AUTO]

`format_timings` debe (1) mostrar `ABORTED` en la columna de estado como
cualquier otro estado, y (2) SI hay filas `RUNNING` con `started_at`
anterior a `ahora − 6 h`, ENTONCES añadir al pie un aviso: «N fila(s)
RUNNING desde hace más de 6 h: probablemente huérfanas de un proceso
muerto; la próxima ejecución que escriba las marcará ABORTED». `ahora` se
inyecta (parámetro con default UTC) para que sea comprobable.

Tests: `test_f024_r6_timings_muestra_aborted`,
`test_f024_r6_timings_avisa_de_running_antiguas`,
`test_f024_r6_timings_no_avisa_de_running_recientes`.

### R7 · Marcar huérfanas nunca tumba la carga [AUTO]

SI la marca de huérfanas lanza una excepción (permisos, red), ENTONCES el
comando debe registrar un WARNING (`huerfanas_no_marcadas`) y CONTINUAR:
es contabilidad, y el paso que venga detrás fallará por sí mismo si la
BBDD no está. Mismo criterio que el grabador del orquestador (F-005 R29).

Test: `test_f024_r7_fallo_al_marcar_huerfanas_no_impide_el_comando`.

---

## Bloque 3 · Puerta de coherencia de `raw` antes de `build_stg`

### R8 · Veredicto de coherencia (dominio puro) [AUTO]

El sistema debe disponer de una función pura
`evaluar_coherencia_raw(estados, tablas_requeridas)` que devuelva OK **si
y solo si**: (1) toda tabla requerida tiene estado (se ha ingerido alguna
vez), (2) el último intento de cada una terminó `SUCCESS`, (3) todas
tienen `batch_id` no nulo y (4) todas comparten el mismo `batch_id`. En
cualquier otro caso devuelve KO con los motivos clasificados: `faltantes`,
`no_exitosas` (con su estado real: `FAILED`/`ABORTED`/`RUNNING`),
`sin_batch` (histórico anterior a F-024 o ingesta antigua) y
`batches_distintos` (mapa batch → tablas y fechas). Las tablas de `raw`
que no estén declaradas se ignoran.

Tests: `test_f024_r8_ok_cuando_todas_del_mismo_batch_success`,
`test_f024_r8_ko_si_falta_una_tabla`,
`test_f024_r8_ko_si_la_ultima_ingesta_no_es_success` (parametrizado
FAILED/ABORTED/RUNNING), `test_f024_r8_ko_si_batch_nulo`,
`test_f024_r8_ko_si_batches_distintos`,
`test_f024_r8_ignora_tablas_no_declaradas`.

### R9 · Mensaje accionable [AUTO]

CUANDO el veredicto es KO, el mensaje debe listar cada motivo con sus
tablas (para `batches_distintos`: cada batch con su fecha de fin y sus
tablas), y terminar con las dos acciones posibles y solo esas: relanzar la
ingesta completa (`python main.py ingest --full`) o, si la carga parcial
fue deliberada, `python main.py stage --sin-puerta` con la advertencia de
que queda registrado. Sin ninguna otra sugerencia.

Tests: `test_f024_r9_mensaje_lista_tablas_y_batches`,
`test_f024_r9_mensaje_termina_con_las_dos_acciones`.

### R10 · La puerta va ANTES de cualquier escritura de `build_stg` [AUTO]

CUANDO `BuildStgStep.run` arranca, el sistema debe evaluar la puerta antes
del pre-flight y antes del primer sub-paso. SI KO, ENTONCES: (1) ninguna
llamada a `execute_sql_file`, `execute_sql_text` ni `truncate_table`,
(2) fila `build_stg.puerta_raw` en `_meta.etl_runs` con `FAILED` y el
mensaje de R9, (3) `StepStatus.FAILED` con ese mensaje (por tanto `stage`
sale 1 y `run-all` marca los siguientes `SKIPPED`). SI OK, ENTONCES fila
`build_stg.puerta_raw` `SUCCESS`, `metadata['raw_batch_id']` en el
resultado del paso, y se continúa como hasta ahora.

Tests (doble `PgFalso` con traza de llamadas, patrón de F-019):
`test_f024_r10_puerta_ko_no_toca_stg_y_falla`,
`test_f024_r10_puerta_ok_registra_y_continua`,
`test_f024_r10_la_puerta_precede_al_preflight`.

### R11 · `--sin-puerta` solo en comandos sueltos y siempre registrado [AUTO]

DONDE el comando `stage` (o `build-mart`, R15) se invoca con
`--sin-puerta`, el sistema debe evaluar la puerta igualmente, registrar la
fila `build_stg.puerta_raw` como `SKIPPED` con «puerta omitida por
--sin-puerta; veredicto: <mensaje>», emitir WARNING `puerta_omitida` y
continuar. `run-all` NO debe aceptar `--sin-puerta` (click devuelve error
de opción desconocida): el pipeline nocturno no tiene vía de escape.

Tests: `test_f024_r11_stage_sin_puerta_registra_skipped_y_continua`,
`test_f024_r11_run_all_no_admite_sin_puerta`.

### R12 · Qué se exige: todas las tablas declaradas [AUTO]

Las tablas requeridas por la puerta deben ser exactamente las
`source_table` declaradas en `config/tables_sigrid.yaml` (las mismas que
ingiere `run-all`), sin lista paralela en código.

Test: `test_f024_r12_las_requeridas_salen_del_yaml` (settings falsos con
tres tablas → la función recibe esas tres).

### R13 · Cómo se lee el estado: la vista `_meta.v_raw_state` [AUTO]

`PostgresClient.fetch_estado_raw()` debe leer de la vista
`_meta.v_raw_state` (definida en `00_meta.sql`: última fila por
`step LIKE 'ingest_raw.%'` ordenando por `started_at DESC, id DESC`, con
`tabla` = el sufijo del step, `status`, `batch_id`, `started_at`,
`finished_at`, `rows_processed`) y devolver `EstadoTablaRaw` por tabla.
La misma vista es la que ve el rol de solo lectura del MCP.

Tests: `test_f024_r13_vista_raw_state_definida_en_el_ddl` (estático:
`CREATE OR REPLACE VIEW _meta.v_raw_state`, `DISTINCT ON`, `ingest_raw.`),
`test_f024_r13_fetch_estado_raw_mapea_filas` (doble de cursor).

### R14 · Comando de diagnóstico `check-coherencia` (solo lectura) [AUTO]

CUANDO se ejecuta `python main.py check-coherencia`, el sistema debe
imprimir el estado por tabla de `raw` (tabla, estado, batch, fin, filas),
el veredicto de la puerta de `raw` y (si DA-5) el de `stg`, y salir con 0
si ambos OK, 1 si alguno KO y 2 si no puede leer. No escribe nada.

Tests: `test_f024_r14_check_coherencia_codigos_de_salida` (parametrizado),
`test_f024_r14_check_coherencia_no_escribe`.

---

## Bloque 4 · Puerta de coherencia de `stg` antes de `build_mart` (DA-5)

### R15 · `build_mart` exige un stage completo [AUTO]

DONDE DA-5 esté aceptada, CUANDO `BuildMartStep.run` arranca, el sistema
debe comprobar que la fila más reciente (por `id`) de `_meta.etl_runs` con
`step LIKE 'build_stg%'` es la fila de paso `build_stg` con `SUCCESS`
(cualquier otra cosa —un sub-paso o tramo `RUNNING`/`ABORTED`/`FAILED`, o
ninguna fila— significa que el último stage no terminó). SI KO, ENTONCES
`FAILED` sin ejecutar ningún SQL de `mart`, con mensaje accionable
(`python main.py stage`, o `build-mart --sin-puerta` registrado como en
R11); SI OK, continúa.

Tests: `test_f024_r15_build_mart_ko_si_ultimo_stage_no_termino`
(parametrizado: sub-paso ABORTED / tramo RUNNING / sin filas),
`test_f024_r15_build_mart_ok_si_stage_success`,
`test_f024_r15_build_mart_sin_puerta_registra_y_continua`.

---

## Bloque 5 · Frescura visible y alertada

### R16 · Vista `_meta.v_frescura` [AUTO]

El DDL de `_meta` debe definir `CREATE OR REPLACE VIEW _meta.v_frescura`
con una fila por paso de nivel de pipeline (`step` sin punto:
`ingest_raw`, `build_stg`, `build_mart`, `build_cierre`, `build_maestros`,
`apply_grants`, `load_excel_aux`...) y estas columnas: `paso`,
`ultimo_ok_finished_at`, `ultimo_ok_batch_id`, `ultimo_ok_filas`,
`horas_desde_ultimo_ok` (numérico, `NULL` si nunca hubo OK),
`ultimo_intento_started_at`, `ultimo_intento_status`,
`ultimo_intento_error`. «Último OK» y «último intento» van por separado a
propósito: un `build_mart` que falló esta noche deja `mart` con lo de ayer
(o vacío si murió entre el DDL y el INSERT) y el consumidor tiene que ver
las dos cosas.

Test (estático): `test_f024_r16_vista_frescura_columnas_y_or_replace`.

### R17 · Las vistas de `_meta` son legibles por el rol de solo lectura [AUTO]

`_meta` debe seguir en `PG_CONSUMPTION_SCHEMAS` por defecto y las
sentencias de `apply_readonly_grants` deben cubrir vistas (`GRANT SELECT
ON ALL TABLES IN SCHEMA` incluye vistas en PostgreSQL). Tras el despliegue
hace falta un `apply-grants` (o la primera noche completa) para que
`mcp_sigrid_dm_ro` vea las vistas nuevas: consta en R25.

Tests: `test_f024_r17_meta_en_esquemas_de_consumo`,
`test_f024_r17_grants_cubren_vistas_de_meta`.

### R18 · Los comandos sueltos registran su resultado [AUTO]

DONDE DA-6 esté aceptada, CUANDO se ejecuta un comando suelto que corre un
step (`ingest`, `load-aux`, `stage`, `build-mart`, `build-cierre`,
`build-maestros`, `apply-grants`), el sistema debe registrar el resultado
del paso en `_meta.etl_runs` con el mismo grabador que usa `run-all` y con
su `batch_id`, después de ejecutarlo y antes de salir. Un fallo del
registro se loguea y no cambia el código de salida (R7).

Test: `test_f024_r18_comandos_sueltos_registran_el_paso` (parametrizado).

### R19 · Comando `check-frescura` [AUTO]

CUANDO se ejecuta `python main.py check-frescura [--umbral-horas N]
[--paso build_mart]`, el sistema debe imprimir `_meta.v_frescura`
formateada (función pura `format_frescura(filas, umbral_horas, ahora)`) y
un veredicto para el paso indicado —`FRESCO` (último OK con horas ≤ umbral),
`CADUCADO` (horas > umbral) o `SIN BUILD REGISTRADO`— y salir con 0 solo si
`FRESCO`; 1 en los otros dos; 2 si no puede leer. El default de
`--umbral-horas` es la constante `UMBRAL_FRESCURA_HORAS` (30, DA-4); el
código no lee `infra/env/dev.json` en tiempo de ejecución (el contenedor
no lo lleva), pero un test cruza la constante con `frescuraUmbralHoras` de
ese fichero para que no diverjan.

Tests: `test_f024_r19_format_frescura_veredictos` (parametrizado),
`test_f024_r19_check_frescura_codigos_de_salida`,
`test_f024_r19_umbral_por_defecto_coincide_con_dev_json`.

### R20 · Formato de estado por tabla [AUTO]

`format_estado_raw(estados, veredicto)` (función pura, usada por
`check-coherencia`) debe listar una línea por tabla con estado, batch, fin
y filas, marcar visualmente las que rompen la coherencia y cerrar con el
veredicto y, si KO, el mensaje de R9.

Test: `test_f024_r20_format_estado_raw_marca_las_incoherentes`.

### R21 · El evento de log que vigila la alerta es estable [AUTO]

DONDE DA-3 sea la opción A, el orquestador debe seguir emitiendo el evento
estructurado `step_finished` con las claves `step` y `status` al terminar
cada paso (hoy ya lo hace), y el script de la alerta debe filtrar
exactamente por los tres términos `step_finished`, `build_mart` y
`SUCCESS`. Un test fija ambos extremos para que renombrar el evento rompa
la suite y no la alerta en silencio.

Tests: `test_f024_r21_orquestador_emite_step_finished_con_step_y_status`
(logger falso), `test_f024_r21_la_alerta_filtra_por_los_tres_terminos`
(estático sobre el `.ps1`).

### R22 · Script de la alerta de frescura [AUTO]

DONDE DA-3 sea la opción A, debe existir
`infra/95_create_alert_frescura.ps1` que: (1) lea TODO de `$CFG`
(`frescuraAlertName`, `frescuraUmbralHoras`, `logAnalytics`, `job`,
`resourceGroup`, `alertActionGroupName`, `alertActionGroupRg`) sin ningún
nombre de recurso ni correo literal, (2) sea idempotente (si la regla
existe, no la recrea), (3) derive de `frescuraUmbralHoras` **las dos
mitades del criterio, ninguna escrita a mano** (enmienda de DA-4,
2026-08-19): la **ventana**, que es la menor granularidad que admite Azure
y contiene el umbral (30 h → `48h`, formato `##h##m##s`, NO ISO 8601), y el
**filtro temporal de la consulta**, que es el umbral exacto
(`| where TimeGenerated > ago(30h)`); si el umbral no cabe en ninguna
granularidad (> 48 h) el script debe fallar con un mensaje accionable
**antes** de llamar a Azure, y evalúe cada hora, (4) dispare con
`count == 0` sobre la consulta de R21 acotada al job por
`ContainerJobName_s` (nombre real de la columna, confirmado en T3), severidad 2, auto-mitigación activa (que llegue el
«Deactivated» cuando vuelva a haber carga), (5) sea UTF-8 con BOM, CRLF y
cabecera con su ruta, y (6) esté en la tabla de `infra/README.md` en su
orden. `infra/env/dev.json` gana `frescuraAlertName` y
`frescuraUmbralHoras`.

Tests: `test_f024_r22_script_alerta_frescura_lee_de_cfg_y_sin_nombres`,
`test_f024_r22_script_alerta_frescura_bom_crlf_cabecera`,
`test_f024_r22_readme_documenta_el_script_en_orden`,
`test_f024_r22_dev_json_declara_umbral_y_nombre`,
`test_f024_r22_la_ventana_sale_del_umbral_y_no_es_iso_8601`,
`test_f024_r22_el_script_declara_las_granularidades_que_admite_azure`,
`test_f024_r22_la_kql_acota_el_criterio_con_el_umbral` y, ejecutando de
verdad la función del `.ps1` con `powershell`,
`test_f024_r23_la_ventana_del_umbral_configurado_es_una_granularidad_admitida`,
`test_f024_r23_la_ventana_es_la_menor_granularidad_que_contiene_el_umbral` y
`test_f024_r23_un_umbral_imposible_falla_antes_de_llamar_a_azure`. Leer el
script como texto no bastaba: `30h` estaba bien formado y era inválido.

> **Segunda enmienda (2026-08-19, review):** lo mismo valía para el criterio.
> La consulta se compone en `Componer-ConsultaFrescura`, que los tests
> **ejecutan** para afirmar sobre la cadena que se envía:
> `test_f024_r22_la_kql_acota_el_criterio_con_el_umbral` (el `ago(...)` lleva
> las horas del umbral y no las de la ventana),
> `test_f024_r22_la_consulta_compuesta_lleva_el_evento_y_el_job`,
> `test_f024_r22_el_nombre_de_la_consulta_es_el_que_cuenta_la_condicion` y
> `test_f024_r22_la_consulta_compuesta_es_la_que_viaja_en_condition_query`.
> Motivo: con el test anterior —que leía el texto— desconectar el filtro
> temporal de la consulta dejaba la suite entera en verde con la regla
> juzgando a 48 h.

> Si el humano elige DA-3 = B, R21/R22 se sustituyen por: parametrizar
> `80_create_job.ps1`/`85_update_job.ps1`/`90_create_alert.ps1` para un
> segundo job y su alerta, con los tests de F-003 extendidos. El
> spec-author los redactará como enmienda cuando se decida; no se escriben
> los dos caminos.

### R23 · La alerta de frescura llega al buzón [MANUAL-Azure]

CUANDO la regla exista, el humano debe verificarla de extremo a extremo:
(1) con `mart` fresco, la consulta manual devuelve ≥ 1 y la regla no
dispara; (2) se acorta temporalmente la ventana a 1 h y la frecuencia a
5 min (`az monitor scheduled-query update`) fuera del horario de carga →
debe llegar el correo «Activated» en < 15 min; (3) se restauran ventana
(**`48h`**, la real de la regla tras la enmienda de DA-4 — con `30h` el
`update` se rechaza y la regla se queda con la ventana corta de la prueba,
disparando cada hora) y frecuencia, y llega el «Deactivated» tras la
siguiente carga correcta. Anotar horas en `progress/current.md`.

Verificación: MANUAL (humano). Comandos (todos leen los nombres de
`infra/env/dev.json`; ninguno va escrito aquí con valores):

```powershell
# 0 · una vez en el puesto
az extension add --name scheduled-query

# 1 · la consulta, a mano, con la ventana real (debe devolver >= 1 tras una noche buena)
$ws = az monitor log-analytics workspace show -g <resourceGroup> -n <logAnalytics> --query customerId -o tsv
az monitor log-analytics query -w $ws --analytics-query "ContainerAppConsoleLogs_CL | where ContainerJobName_s == '<job>' | where Log_s has_all ('step_finished','build_mart','SUCCESS') | where TimeGenerated > ago(30h) | count" -o table

# 2 · crear la regla (idempotente)
powershell -NoProfile -File infra\95_create_alert_frescura.ps1

# 3 · provocar: ventana corta, esperar el correo, restaurar
az monitor scheduled-query update -g <resourceGroup> -n <frescuraAlertName> --window-size 1h --evaluation-frequency 5m
#   ... correo Activated recibido a las HH:MM ...
#   Restaurar con 48h: es la ventana que crea el script (umbral 30 h envuelto
#   en la menor granularidad admitida). Un 30h aqui se rechaza.
az monitor scheduled-query update -g <resourceGroup> -n <frescuraAlertName> --window-size 48h --evaluation-frequency 1h
```

Resultado esperado: correo Activated en la prueba, Deactivated tras
restaurar, y ninguna alerta en una noche buena.

---

## Bloque 6 · Verificación en Azure de una muerte externa controlada

### R24 · Muerte controlada durante la ingesta: ABORTED + puerta + frescura [MANUAL-Azure]

Con la imagen de F-024 desplegada en el job, el humano debe provocar UNA
muerte externa controlada y comprobar las tres piezas sin lanzar ningún
build pesado contra el servidor compartido:

```powershell
# 1 · lanzar la carga tal cual la lanza el cron (SIN --command ni --args: el override borra las variables de entorno)
az containerapp job start -g <resourceGroup> -n <job>
# 2 · a los ~10 min (la ingesta dura ~33 min; confirmar en los logs que va por las tablas de raw), matarla desde fuera
az containerapp job execution list -g <resourceGroup> -n <job> --query "[0].name" -o tsv
az containerapp job stop -g <resourceGroup> -n <job> --job-execution-name <ejecucion>
# 3 · con .env de Azure, desde el puesto: la mentira actual, y su aviso al pie
python main.py timings --last 1          # filas RUNNING de ingest_raw.<tabla> y aviso «RUNNING desde hace más de 6 h» solo si han pasado 6 h
python main.py check-coherencia          # KO: batches distintos + tabla en RUNNING (aún no marcada: es de lectura); sale 1
# 4 · el primer comando que escribe marca las huérfanas y la puerta se niega a construir
python main.py stage                     # FAILED en build_stg.puerta_raw, mensaje de R9, sale 1, ningún TRUNCATE en stg
python main.py timings --last 1          # las RUNNING ahora ABORTED con motivo y batch
python main.py check-frescura            # build_mart: FRESCO (el último OK sigue siendo el de la noche anterior)
# 5 · recuperación: la carga completa
az containerapp job start -g <resourceGroup> -n <job>
#   al terminar (~3 h 15): check-coherencia OK, check-frescura FRESCO con la hora nueva, buzón sin Activated
python main.py check-coherencia; python main.py check-frescura
```

Resultado esperado: (3) `timings` enseña `RUNNING`; (4) `stage` sale 1 sin
tocar `stg` y las `RUNNING` pasan a `ABORTED`; (5) todo OK y sin correo. Si
en (4) `check-coherencia` dijera OK (la muerte cayó después de la ingesta),
**no ejecutar `stage`**: repetir desde (1) matando antes.

### R25 · Primer despliegue: las huérfanas del 18-ago quedan cerradas [MANUAL-Azure]

CUANDO la primera ejecución con F-024 arranque en Azure, las dos filas
`RUNNING` del 2026-08-18 (`build_stg.build_plan_mensual` y
`build_stg.build_plan_mensual.tramo_39`) deben quedar `ABORTED` con motivo,
y tras `apply-grants` el rol `mcp_sigrid_dm_ro` debe poder leer
`_meta.v_frescura` y `_meta.v_raw_state`.

```powershell
python main.py timings --last 3
PSQL -h <pgHost> -p 5432 -U mcp_sigrid_dm_ro -d sigrid_dm -X -c "SELECT paso, ultimo_ok_finished_at, round(horas_desde_ultimo_ok,1) AS horas, ultimo_intento_status FROM _meta.v_frescura ORDER BY paso;"
PSQL -h <pgHost> -p 5432 -U mcp_sigrid_dm_ro -d sigrid_dm -X -c "SELECT tabla, status, batch_id, finished_at FROM _meta.v_raw_state ORDER BY tabla;"
```

### R26 · Primera vez en local tras F-024 [MANUAL-local]

Con `.env` apuntando a local y el `raw` cargado antes de F-024,
`python main.py check-coherencia` debe decir KO por `sin_batch` (histórico)
y `python main.py stage` debe negarse con el mensaje de R9; después de
`python main.py ingest --full` (o con `stage --sin-puerta`, que queda
registrado como `SKIPPED`), debe construir. Sirve también para DA-8:
durante `ingest --full`, un `SELECT count(*) FROM raw.con` repetido enseña
si la tabla crece por páginas (commits parciales) o aparece de golpe.

---

## Bloque 7 · Salud del repositorio

### R27 · Suite sin red ni BBDD, init.sh en verde [AUTO]

Todos los tests `test_f024_*` deben ejecutarse sin abrir conexión a red ni
a BBDD y `bash harness/init.sh` debe terminar en verde con la cobertura y
la mutación que exige el rigor `critico`.

Verificación: `bash harness/init.sh`.

---

## Riesgos, dependencias y lo que queda fuera

- **F-011 (carga incremental)** cambiará la ingesta. Compatibilidad
  exigida a F-011, no resuelta aquí: la semántica de `v_raw_state` es «la
  última ingesta SUCCESS de cada tabla y su batch»; una ingesta incremental
  que toque todas las tablas en una ejecución sigue cumpliendo la puerta;
  una que toque solo algunas la rompe **a propósito** y F-011 tendrá que
  decidir si su unidad de coherencia es «batch» u otra cosa (p. ej. estampar
  batch en todas las tablas que decida NO recargar). `batch_id` en
  `etl_runs` es lo que F-011 necesita para razonar sobre ello.
- **Dos procesos a la vez** (cron + arranque manual, o job + puesto): la
  marca de huérfanas de uno cerraría las `RUNNING` del otro como `ABORTED`;
  cuando ese otro cierre sus filas por `id`, las sobreescribe con su estado
  real, así que el daño es transitorio. Ejecutar dos cargas a la vez ya es
  incorrecto hoy (se truncan las tablas mutuamente): riesgo aceptado, no se
  añade bloqueo.
- **`mart` a medias por fallo interno** (`01_ddl.sql` recrea la tabla y
  `02_build_fact.sql` falla): fuera de alcance; `v_frescura` lo hace
  visible (último intento `FAILED` con hora), no lo impide.
- **La alerta A mide logs, no BBDD**: un `build-mart` desde el puesto no la
  calla. Asumido y documentado; B lo evita al precio de otro job.
- **Fuera**: atomicidad global; bloqueo de concurrencia; convertir
  `build-compras`/`build-retenciones` en steps; wrapper `mart.v_pbi_frescura`
  (si Power BI exige el prefijo, es una vista de una línea en otra feature);
  cualquier cambio en `08_plan_mensual.sql`, `tramos.py`, `fingerprint.py`,
  `orchestrator.py`, `Dockerfile`, `.env`.
