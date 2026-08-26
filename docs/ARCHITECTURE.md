<!-- docs/ARCHITECTURE.md -->
# Arquitectura · datamart-seg-anual

ETL Sigrid → PostgreSQL → Power BI para el seguimiento económico mensual de
obras. Microservicio único; se despliega como job programado en Azure.

## Hexagonal + pipeline

- `etl_sigrid/domain/` — entidades puras (TableSpec, ColumnSpec, StepResult,
  StepStatus). CERO imports de infraestructura.
- `etl_sigrid/application/` — `Orchestrator` ejecuta una lista de steps.
  Cada step hereda de `steps/base.py::PipelineStep` y recibe/enriquece un
  contexto. Steps actuales: ingest_raw, load_excel_aux, build_stg, build_mart,
  build_maestros, build_cierre.
- `etl_sigrid/infrastructure/` — adaptadores: `sigrid/sigrid_api_client.py`
  (HTTP a sigrid-api), `postgres/postgres_client.py`, SQL por capas en
  `postgres/sql/`, logging estructurado.
- Punto de entrada: `main.py` (click). El pipeline se compone en main, no
  dentro de los steps.

## Capas PostgreSQL (¡no existe capa en `public`!)

`raw` → `stg` → `mart` (+ `cierre` para cierres mensuales y planif vs real).
Módulos adicionales: `compras`, `maestro`, `retenciones`, `auxiliar`.
SQL numerado `NN_nombre.sql` y ejecutado en orden dentro de cada capa.

## Semántica Sigrid imprescindible (fuente de bugs si se ignora)

- Ámbitos: amb=3 Coste Real, amb=7 Venta Real, amb=8 Master Coste,
  amb=11 Master Venta.
- Master (amb 8/11): `fas` = número de VERSIÓN; planif explosionada.
- Reales (amb 3/7): `fas` = MES; fas=0 = Previsto (foto viva),
  fas=1..N cierres mensuales; planif NO explosionada;
  importe del mes = diferencia con la fase anterior.
- `obr.ide = con.ide` (obra hereda de concepto). El nombre legible está en
  `con.res`. `con.nom` NO existe.
- En `raw.obrfas` el campo de fase se llama `fasnum`; en `raw.obrparpre` se
  llama `fas`. No confundirlos.
- Versión de master vigente por obra: campo extendido `cod='15'` en `conext`.
- `importe_origen = round(can * round(precio, decp), deci)`;
  `importe_mes` = diferencia entre orígenes consecutivos.
  REGLA: `importe_mes` jamás se suma entre meses distintos en vistas para
  Power BI; `importe_origen` es acumulado.
- Fechas Sigrid: enteros YYYYMMDD; 0 = NULL.
- La ingesta nocturna SIEMPRE `--full` (el cursor incremental por `ide`
  pierde los UPDATE).
- Palabra reservada `real` en vistas de `cierre` → siempre entre comillas.

## Acceso a datos

- Sigrid solo vía sigrid-api (`POST /api/sql/read`), nunca conexión directa.
  Tope duro 10.000 filas/petición; timeout de red efectivo 230 s.
- Solo LECTURA de Sigrid desde este proyecto. Las escrituras del datamart van
  al PostgreSQL propio (local en dev, Flexible Server en Azure).
- **Los tres Excels auxiliares de Negocio (F-004)** se leen de una ruta del
  sistema de ficheros **o** de Azure Blob Storage, y lo decide la FORMA del
  valor de `AUX_EXCEL_*`: una URI
  `https://<cuenta>.blob.core.windows.net/<contenedor>/<blob>` va a Blob
  Storage; cualquier otra cosa, al disco. No hay variable de modo que mantener
  coherente. La autenticación es `DefaultAzureCredential` —identidad
  gestionada en el job, sesión de `az` en el puesto—, con el rol
  `Storage Blob Data Reader` sobre la cuenta: **ni cadenas de conexión, ni
  claves, ni SAS** (una URI con query string se rechaza al arrancar el paso).
  El contenido se obtiene **en memoria**, sin ficheros temporales, porque el
  contenedor no tiene dónde escribirlos. Puerto y adaptadores en el paquete,
  bajo `infrastructure/excel/`; el step `load_excel_aux` no sabe de
  Azure. Hoy **lee y valida, no carga** a `aux.*`: las tablas destino y el
  esquema de los libros no están definidos todavía.

### El datamart en Azure (F-005)

- **No hay servidor propio.** La base `sigrid_dm` vive dentro de
  `psql-albaranes-rs9k2.postgres.database.azure.com` (`rg-albaranes-dev`,
  PostgreSQL 16, `Standard_B1ms`, 32 GB), que ya sirve a `albaranes` y
  `partes`, **las dos en uso**. Base propia y no esquema compartido: PostgreSQL
  no permite consultas entre bases, y esa es la frontera que impide que el rol
  de lectura vea `albaranes`.
- **Tres roles.** `sigrid_dm_etl` (grupo `NOLOGIN`) es el propietario de todo;
  `sigrid_dm_app` (login, contraseña en Key Vault) es el que usa el ETL y es
  miembro del grupo; `mcp_sigrid_dm_ro` (login) es de solo lectura, para el
  MCP. Autenticación por contraseña: habilitar Entra es una operación de
  servidor y se descartó para no tocar las otras dos bases. El modo
  `PG_AUTH_MODE=entra` existe en el código, probado, pero inactivo.
- **`PG_SET_ROLE=sigrid_dm_etl`** en cada sesión: los objetos deben tener
  siempre el mismo dueño, porque las vistas se recrean en cada ejecución y
  quien no es dueño no puede hacer `DROP`.
- **`PG_AUTO_CREATE_DB=false`** contra Azure: el ETL no ejecuta
  `CREATE DATABASE` ni abre la base admin en un servidor de producción
  compartido. La base la crea el humano con `infra/sql/`.
- **Los permisos de lectura se reaplican en cada ejecución** (paso
  `apply_grants` y comando `apply-grants`): siete ficheros SQL recrean vistas
  con `DROP VIEW ... CASCADE` y un `DROP` se lleva los `GRANT`.
- **La recuperación es volver a ejecutar el ETL, no restaurar**: el PITR es de
  servidor entero y arrastraría `albaranes` y `partes` al pasado.
- Procedimiento completo: `docs/runbook_postgres_azure.md`.

### El build de `stg.plan_mensual` va por tramos (F-019)

El 2026-08-09 ese build llenó el disco del servidor compartido: la explosión
del `planif` con `CROSS JOIN LATERAL unnest(...)` sobre 13,76 M filas derramó
16+ GB de temporales, la ocupación llegó al 93,4 % y Azure dejó el servidor en
solo-lectura diez minutos, con `albaranes` y `partes` en producción. En local
no pasaba porque sobra RAM.

Desde F-019, el sub-paso `build_plan_mensual` **no se ejecuta de una pasada**:

- **Corte por obra.** Ninguna ventana del SQL cruza obras (particionan por
  `presupuesto_id` o por la terna obra-partida-ámbito), así que ejecutar el
  mismo statement con un filtro de obras disjunto y completo da exactamente
  las mismas filas. La equivalencia es estructural, no casual.
- **Quién hace qué.** `domain/tramos.py` planifica (función pura: pesos por
  obra + tope), `build_stg_step` orquesta y `postgres_client` mide y ejecuta.
  El fichero SQL lleva un marcador que el step sustituye por las obras del
  tramo, **en las dos ramas** (master amb 8/11 y reales amb 3/7); filtrar solo
  una duplicaría la otra. El vaciado de la tabla lo hace el step una vez.
- **Una transacción por tramo**, para que el pico de temporales de un tramo no
  se apile con el del siguiente.
- **Puerta de disco antes de CADA tramo**: se mide la ocupación del servidor
  (suma de `pg_database_size` de todas las bases) y, si supera el límite, el
  build **para**, deja la tabla **vacía** y marca FAILED. Si la medición
  falla, también para: seguir a ciegas es lo que provocó el incidente.
- **Tres settings**, todos con default y sin secretos: `PG_TRAMO_MAX_FILAS`
  (1 000 000), `PG_DISCO_TOTAL_GB` (32) y `PG_DISCO_LIMITE_PCT` (80). Un
  máximo enorme reproduce el comportamiento antiguo si alguna vez hiciera
  falta diagnosticar, sin conservar una rama de código con el arma cargada.
- Cada tramo deja su fila en `_meta.etl_runs`, así que `python main.py timings`
  desglosa el coste real tramo a tramo.

### Coherencia ante cargas truncadas (F-024)

El 2026-08-18 la primera carga real lanzada desde el job murió por
`DeadlineExceeded` a las dos horas justas, en el tramo 39/60 del stage. `mart`
no llegó a tocarse, así que las vistas siguieron enseñando el build anterior
completo; pero `_meta.etl_runs` se quedó con dos filas `RUNNING` huérfanas para
siempre y `stg.plan_mensual` a medias. Destapó tres huecos: una muerte externa
del proceso no deja rastro honesto, nada impide construir sobre un `raw`
MEZCLADO, y el consumidor no tiene forma de saber si lo que ve es de anoche o
de hace tres días.

**No se hace nada atómico.** Una transacción de tres horas en el `B1ms` es
exactamente lo que reventó el 09-ago, y F-019 la troceó a propósito. La
coherencia se garantiza por **verificación** y **visibilidad**:

- **Identidad de ejecución.** Todo comando que ESCRIBE genera un `batch_id`
  (`YYYYMMDDTHHMMSSZ-xxxxxx`, dominio puro en `domain/ejecucion.py`) y lo
  estampa en cada fila que deja en `_meta.etl_runs`. El formato se ordena
  cronológicamente **como texto**, así que un `ORDER BY batch_id` sale ordenado
  sin parsear nada. El histórico anterior queda con `batch_id` a `NULL`: la
  columna se **añade**, la tabla no se recrea.
- **Filas huérfanas → `ABORTED`.** Al arrancar, antes de ejecutar ningún paso,
  todo comando que escribe cierra las filas que siguen en `RUNNING` con el
  motivo, la ejecución que las marcó y la hora. Toda `RUNNING` que exista al
  arrancar es de otro proceso por definición. Si la marca falla, se avisa y se
  **continúa**: es contabilidad, y el paso siguiente fallará por sí mismo si la
  BBDD no está.
- **Dos puertas, ambas ANTES de escribir nada.** `build_stg` exige que TODAS
  las tablas declaradas en `tables_sigrid.yaml` provengan del **mismo** batch
  terminado en `SUCCESS`; `build_mart` exige que la fila más reciente de
  `build_stg%` sea el **paso** completo, no un sub-paso ni un tramo. El
  veredicto es dominio puro (`domain/coherencia.py`) y queda registrado en
  `_meta.etl_runs` (`build_stg.puerta_raw`, `build_mart.puerta_stg`) pase lo
  que pase. Que vayan primero no es un detalle de orden: `stg` empieza con
  `TRUNCATE` y `mart/01_ddl.sql` con un `DROP`, y eso no se deshace porque el
  step devuelva `FAILED` después.
- **`--sin-puerta`, solo en los comandos sueltos.** `stage` y `build-mart` la
  admiten; `run-all` **no**, porque a las 02:00 no hay nadie delante para
  valorar si saltársela es razonable. Con la opción, la puerta se evalúa
  igualmente y su fila queda `SKIPPED` con el veredicto dentro: lo que esa fila
  cuenta es que el build se hizo **sin** puerta, no lo que la puerta habría
  dictaminado.
- **Dos vistas en `_meta`**, derivadas de la tabla que ya escriben todos los
  pasos, sin tablas nuevas que mantener: `v_raw_state` (de qué carga viene cada
  tabla de `raw`) y `v_frescura` (último OK y último intento por paso, **por
  separado**: un `build_mart` que falló esta noche deja `mart` con lo de ayer y
  el consumidor necesita las dos noticias). Las leen por igual la puerta, el
  MCP y Power BI. Ninguna toca `raw`, `stg` ni `mart`: cero coste sobre el
  servidor compartido.
- **Diagnóstico y alerta.** `check-coherencia` y `check-frescura` son de solo
  lectura (`timings` también: ve las huérfanas y **avisa**, no las marca). Y
  `infra/95_create_alert_frescura.ps1` crea una regla de consulta programada
  que dispara si en `frescuraUmbralHoras` (30) no hay ninguna línea de log del
  job diciendo que `build_mart` terminó en `SUCCESS`. Vigila desde **fuera**
  del ETL, así que «el job no lo hizo» dispara igual que «el job murió».

**La ingesta hace commit por PÁGINA, no por tabla** (DA-8, confirmado leyendo
`copy_rows` el 2026-08-18). `truncate_table` y cada página de 10.000 filas
abren su propia conexión, y por tanto su propia transacción. Consecuencia para
cualquier post mortem futuro: una muerte a mitad de tabla la deja **truncada y
parcial**, no intacta. Donde se dijo «la ingesta es transaccional por tabla, lo
cargado se conserva» se dijo mal. La puerta de F-024 no depende de ello: la
marca de «tabla ingerida» solo se escribe cuando la tabla termina en `SUCCESS`,
así que una tabla parcial queda con su última fila en `RUNNING` → `ABORTED` y
la puerta la rechaza igual.

### El datamart se explica solo (F-006)

El datamart publica **su propia semántica dentro de la base**: qué significa
cada objeto y cada columna, qué grano tiene, qué trampas hay que respetar al
leerlo y qué preguntas de negocio contesta. No es documentación para personas:
es un **contrato de datos** que un agente conectado por MCP lee por SQL, sin
poder preguntarle a nadie si algo no encaja.

- **La fuente son los YAML de `config/diccionario/`**: uno por esquema —los
  nueve del datamart— más `00_global.yaml`, que lleva las reglas duras
  transversales, los ejes, las convenciones de nombre y la batería de preguntas
  de aceptación. Están en este repositorio a propósito: qué significa
  `mart.fact_seguimiento_mensual` lo sabe quien escribió el SQL que la
  construye, y cualquier otro sitio se desincroniza. Por eso la ficha se
  actualiza en el mismo trabajo que el objeto (`docs/CONVENTIONS.md`).
- **El paso `publicar_diccionario`** los carga, valida, deriva los avisos y los
  escribe. Va dentro de `run-all`, **entre `build_mart` y `apply_grants`**, y
  ese orden no es cosmético: `apply_grants` concede `SELECT` sobre lo que hay
  en `_meta` en ese instante, así que publicar después dejaría las tablas del
  contrato colgando solo de los privilegios por defecto. Suelto, el comando es
  `python main.py publicar-diccionario`.
- **El contrato en `_meta` son cuatro tablas y una vista.** `_meta.diccionario`
  (una fila por objeto documentado, con la ficha entera en `JSONB` y en
  columnas lo que se filtra barato); `_meta.diccionario_reglas` (las reglas
  duras que no son de ningún objeto en particular);
  `_meta.diccionario_contexto` (los bloques de contexto, que crecen **por
  filas**, no por columnas); y `_meta.diccionario_publicacion`, una única fila
  con `version`, `hash_fuente` y los recuentos. Encima, `_meta.v_diccionario`
  es la vista plana que consulta el cliente.
- **La publicación es atómica**: `DELETE` + `INSERT` dentro de UNA transacción,
  así que quien consulte mientras se publica ve el diccionario anterior
  completo o el nuevo completo, nunca uno a medias. **Nunca `DROP` ni
  `TRUNCATE`**, y nunca quitar o reordenar columnas de la vista: eso exige un
  `DROP VIEW`, y un `DROP` se lleva por delante los `GRANT` del rol de lectura.
  Las reglas de compatibilidad completas están en la cabecera de
  `etl_sigrid/infrastructure/postgres/sql/ddl/01_diccionario.sql`.
- **Quien lo consume es `mcp-bbdd`**, un servicio con su propio repositorio, y
  lo hace **por SQL** con el rol de solo lectura `mcp_sigrid_dm_ro`. No hay API
  que versionar ni fichero que exportar: la base es la interfaz, y por eso un
  cambio en esas cinco formas es un cambio de API.
- **Dónde está la línea**: el MCP sabe de transporte, permisos, auditoría y
  multi-base; el significado del dato es del dueño del dato. Por eso el
  diccionario vive aquí y el servidor MCP no. Y el diccionario describe lo que
  el dato **es**, no cómo se decide con él: un procedimiento de negocio es otro
  repositorio.
- **La frescura no se declara, se une.** El `paso_etl` de cada ficha casa con
  `_meta.v_frescura.paso` (F-024), así que el consumidor sabe de cuándo es lo
  que está mirando sin tener que creerse un texto escrito a mano.
- **Verificación**: `python main.py check-diccionario` contrasta el diccionario
  del árbol contra el catálogo real de la base en las dos direcciones —objeto
  publicado sin ficha, ficha sin objeto, tipo que no casa— y avisa si lo
  publicado va por detrás del repositorio. La puerta offline de
  `bash harness/init.sh` solo puede exigir ficha **o** pendiente declarado.

Lo que este proyecto **expone al ecosistema** y quién lo consume está en
`azure-apps/datamart_seg_anual.md`, y no se duplica aquí.

## Infra

- `Dockerfile` en raíz. `infra/` con scripts PowerShell 5.1 (UTF-8 BOM, CRLF)
  numerados por orden de ejecución. Procedimiento y datos están separados:
  **los nombres de recurso viven solo en `infra/env/<entorno>.json`** y ningún
  `.ps1` escribe uno. Montar `sta` o `pro` es copiar ese fichero y ejecutar con
  `-Entorno <nombre>`; `00_vars.ps1` lo carga, lo valida y aborta antes de la
  primera llamada a `az` si falta un valor. Lo verifican los tests
  `test_f003_r1..r11` sin tocar Azure.
- **Ni la suscripción ni ningún secreto están en el repositorio.** La
  suscripción sale de `$env:AZ_SUBSCRIPTION_ID` o del contexto de `az`.
- `infra/sql/` contiene la provisión de `sigrid_dm` (base, roles, diagnóstico).
  Se ejecuta a mano con `psql`, nunca desde el ETL: usa bloques `$$`, que el
  troceador de sentencias de `postgres_client.py` no sabe manejar.
- Destino: **Container Apps Job programado** (`0 2 * * *` UTC, siempre
  `run-all --full`) en un resource group propio del datamart, región
  `spaincentral`, con entorno **sin integración de red virtual** — así tiene IP
  de salida estática, que es lo que se autoriza en el firewall del Postgres.
  Tags de imagen fechados (`rYYYYMMDD-HHmm`), nunca reescritos.
- **Sin contraseñas en el job.** Corre con una **identidad gestionada asignada
  por el usuario** que tiene exactamente tres permisos: bajar la imagen del
  registro, leer el único secreto (la clave de `sigrid-api`) del Key Vault del
  proyecto y leer los Excels auxiliares del blob. Esa misma identidad es la que
  `AZURE_CLIENT_ID` señala dentro del contenedor.
- Orden de ejecución, pasos que exigen autorización del humano y consulta de
  logs: `infra/README.md`.
