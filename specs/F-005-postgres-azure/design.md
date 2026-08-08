<!-- specs/F-005-postgres-azure/design.md -->
# F-005 · Postgres del datamart en Azure — Diseño técnico

> Léase primero `requirements.md`: allí está el aviso de que la descripción de
> la feature en `harness/features.json` está desfasada y que **F-005 no
> aprovisiona ningún Flexible Server**, sino la base `sigrid_dm` dentro del
> servidor existente `psql-albaranes-rs9k2`.

## 0. Resumen del cambio

Cuatro piezas, en este orden:

1. **Provisión** (manual, con privilegios de administrador): base, roles,
   identidad, firewall. Vive en `infra/`, no en el pipeline.
2. **Código** para que el ETL sepa conectarse a Azure (TLS, Entra, `SET ROLE`,
   sin auto-crear la base) y para que reaplique los permisos del MCP en cada
   ejecución.
3. **Instrumentación**: persistir el tiempo de cada paso en `_meta.etl_runs` y
   un comando para leerlo.
4. **Verificación**: huella comparable de las vistas de consumo entre local y
   Azure, con criterio de igualdad explícito.

Nada de esto cambia una sola línea de lógica de negocio: no se toca el SQL de
`stg`, `mart`, `cierre`, `compras`, `maestro`, `retenciones` ni `auxiliar`, ni
la semántica `amb`/`fas` ni `importe_origen`/`importe_mes`.

## 1. Modelo de roles y por qué

```
sigrid_dm (base)
  owner: sigrid_dm_etl        ← rol de GRUPO, NOLOGIN
     ├── id-datamart-seg-dev  ← principal Entra (identidad gestionada, job F-003)
     └── <operador>@ruesma.es ← principal Entra del humano (puesto, carga inicial)

  mcp_sigrid_dm_ro            ← LOGIN con contraseña, solo lectura
```

Tres decisiones y su motivo:

- **Rol de grupo propietario.** La carga inicial la ejecuta el humano desde su
  puesto (una identidad gestionada no se puede impersonar fuera de Azure) y la
  nocturna el job. Si cada uno crea objetos con su propio principal, el otro no
  puede `DROP` ni `CREATE OR REPLACE` sobre ellos — y las vistas se recrean en
  cada ejecución. Con `SET ROLE sigrid_dm_etl` al abrir sesión, el dueño es
  siempre el mismo, conecte quien conecte.
- **El ETL con Entra, el MCP con contraseña.** El token de Entra caduca en
  ~1 hora: perfecto para un job que abre conexiones durante una ejecución,
  impracticable para un cliente MCP de escritorio con una cadena de conexión
  estática. La asimetría es deliberada.
- **Base propia y no esquema compartido.** Es la frontera que impide que el
  rol del MCP consulte `albaranes` (precios de proveedor, datos bancarios):
  PostgreSQL no permite consultas entre bases. **Con la salvedad de R19**: sí
  permite *conectar*, porque `CONNECT` se concede a `PUBLIC` por defecto, y con
  ello leer el catálogo. Cerrarlo del todo exige tocar `albaranes`.

## 2. Ficheros a crear

### 2.1 Código — capa infrastructure

| Ruta | Responsabilidad |
|---|---|
| `etl_sigrid/infrastructure/azure/__init__.py` | Paquete nuevo |
| `etl_sigrid/infrastructure/azure/entra_token.py` | `EntraTokenProvider` |
| `etl_sigrid/infrastructure/postgres/conninfo.py` | Construcción de la cadena de conexión y redactado |
| `etl_sigrid/infrastructure/postgres/grants.py` | Generación pura de las sentencias `GRANT` |
| `etl_sigrid/infrastructure/postgres/step_run_recorder.py` | Adaptador que persiste `StepResult` en `_meta.etl_runs` |
| `etl_sigrid/infrastructure/postgres/fingerprint.py` | Construcción de consultas de huella, E/S del CSV y comparador |

**`entra_token.py`**

```python
class EntraTokenProvider:
    RESOURCE = "https://ossrdbms-aad.database.windows.net/.default"

    def __init__(self, credential: Any | None = None, margin_s: int = 300) -> None: ...
    def get_token(self) -> str: ...   # cachea; refresca si caduca en < margin_s
```

`azure.identity` se importa **dentro** de `get_token`, no en el módulo: así el
desarrollo local sin la dependencia sigue arrancando, y si falta se levanta
`RuntimeError` con el texto del plan B (R5). `credential` inyectable para que
los tests usen un doble sin red (R3, R4).

**`conninfo.py`**

```python
def build_conninfo(pg: PostgresSettings, password: str) -> str: ...
def make_conninfo_provider(pg: PostgresSettings) -> Callable[[], str]: ...
def make_admin_conninfo_provider(pg: PostgresSettings) -> Callable[[], str]: ...
def safe_dsn(conninfo: str) -> str: ...   # 'password=***' — lo único que se loguea
def is_azure_host(host: str) -> bool: ...
```

El proveedor es un **callable**, no una cadena: el token caduca y hay que
resolverlo en cada conexión (R4).

**`grants.py`**

```python
def build_readonly_grant_statements(
    readonly_role: str, owner_role: str, schemas: Sequence[str]
) -> list[str]: ...
```

Función **pura**: devuelve texto SQL con identificadores citados. Por esquema
emite `GRANT USAGE ON SCHEMA`, `GRANT SELECT ON ALL TABLES IN SCHEMA` y
`ALTER DEFAULT PRIVILEGES FOR ROLE <owner> IN SCHEMA ... GRANT SELECT ON
TABLES`, más un `GRANT CONNECT ON DATABASE` inicial.

**Por qué en Python y no en un `.sql`**: haría falta un bloque `DO $$ ... $$`
con nombre de rol parametrizado, y `_split_sql_statements` de
`postgres_client.py` **no sabe manejar `$$`** — está documentado en su propio
docstring. Generarlo en Python evita la trampa y hace la unidad testeable sin
BBDD.

**`fingerprint.py`**

```python
@dataclass(frozen=True)
class Metrica:      # una fila del CSV
    esquema: str; vista: str; bloque: str; metrica: str; valor: str

def build_estructura_query(schemas: Sequence[str]) -> str: ...
def build_agregado_query(
    esquema: str, vista: str, columnas_numericas: Sequence[str],
    periodo_col: str | None, periodo_hasta: date | None,
) -> str: ...
def escribir_csv(metricas: Sequence[Metrica], path: Path) -> None: ...
def leer_csv(path: Path) -> list[Metrica]: ...
def comparar(a, b, *, tolerancia: float = 0.01) -> list[Diferencia]: ...
def veredicto(diffs) -> tuple[int, str]: ...   # (exit_code, informe)
```

`escribir_csv`/`leer_csv` son simétricos y siguen `docs/CONVENTIONS.md`:
UTF-8 **con BOM**, separador `;`, **coma decimal**. Todo lo demás es función
pura sobre listas → tests sin BBDD.

El filtro de periodo se aplica **solo a las vistas que tienen la columna**, y
la columna se detecta con `information_schema.columns`, no se asume. La
columna del proyecto es `anio_mes` (tipo `DATE`, primer día del mes).

### 2.2 Código — capa application

| Ruta | Responsabilidad |
|---|---|
| `etl_sigrid/application/ports.py` | `StepRunRecorder` (Protocol) |
| `etl_sigrid/application/steps/apply_grants_step.py` | `ApplyGrantsStep` |

```python
class StepRunRecorder(Protocol):
    def record(self, stage: str, result: StepResult) -> None: ...
```

Puerto en `application`, adaptador en `infrastructure`. El dominio no se toca.

`ApplyGrantsStep`: `name="apply_grants"`, `stage="grants"`,
`depends_on=["build_mart"]`. Si `PG_READONLY_ROLE` está vacío → `SUCCESS` con
`rows_processed=0` sin abrir conexión (R17). Si el rol no existe en `pg_roles`
→ log de aviso y `SUCCESS` (R18).

### 2.3 Provisión y operación

| Ruta | Contenido |
|---|---|
| `infra/sql/01_create_database.sql` | `CREATE DATABASE sigrid_dm`, `REVOKE ALL ON DATABASE ... FROM PUBLIC`, propietario `sigrid_dm_etl` |
| `infra/sql/02_roles.sql` | `sigrid_dm_etl` (NOLOGIN), `mcp_sigrid_dm_ro` (LOGIN, contraseña por variable de psql, **nunca literal**), altas de principales Entra con `pgaadauth_create_principal`, membresías |
| `infra/sql/03_diagnostico.sql` | **Solo lectura**: tamaño por base, `datacl` de `pg_database`, roles y pertenencias, tamaño por esquema de `sigrid_dm` |
| `infra/15_provision_db.ps1` | Envoltorio documentado: identidad gestionada (idempotente, coordinada con F-003), listado de firewall, alta de regla, invocación de los `.sql` con `psql`. PowerShell 5.1, UTF-8 BOM, CRLF |
| `docs/runbook_postgres_azure.md` | Runbook operativo completo (R38, R39) |

`02_roles.sql` recibe la contraseña por `psql -v` desde una variable de entorno
de la sesión del humano. **Ni el fichero ni el `.ps1` la contienen** (R21, R40).

Numeración `15_` deliberada: va **antes** de `20_build_image.ps1` y
`30_create_job.ps1`, que son de F-003.

### 2.4 Tests

| Ruta | Cubre |
|---|---|
| `tests/test_f005_conexion.py` | R1-R11, R41 |
| `tests/test_f005_grants.py` | R14-R18, R21, R40 |
| `tests/test_f005_verificacion.py` | R28-R30, R32-R35 |

Todos sin red ni BBDD: dobles de `psycopg.Connection` y de la credencial,
`CliRunner` para los comandos, ficheros temporales para el CSV.

## 3. Ficheros a modificar

| Ruta | Qué cambia |
|---|---|
| `config/settings.py` | `PostgresSettings` gana `sslmode`, `auth_mode`, `auto_create_db`, `set_role`, `readonly_role`, `consumption_schemas`. Validador de R2. `conninfo`/`admin_conninfo` pasan a delegar en `conninfo.py` manteniendo la firma actual para el modo password |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | Acepta `str \| Callable[[], str]` en `conninfo`/`admin_conninfo`; `auto_create_db: bool` y `set_role: str \| None` nuevos; `_ensure_database` se salta y `_auto_bootstrap` verifica existencia si `auto_create_db=False`; `SET ROLE` en `connection()`; métodos nuevos `apply_readonly_grants`, `role_exists`, `record_run_completed`, `fetch_timings`, `list_view_columns` |
| `etl_sigrid/application/orchestrator.py` | `__init__(steps, recorder: StepRunRecorder \| None = None)`; tras cada `StepResult` llama a `recorder.record(...)` dentro de `try/except` que solo loguea (R29) |
| `main.py` | `_get_pg()` construye con proveedores; `run-all` inyecta el grabador y añade `ApplyGrantsStep`; comandos nuevos `apply-grants`, `timings`, `fingerprint-views`, `compare-fingerprints`; docstring del módulo al día |
| `.env.example` | Variables nuevas, todas vacías o con valor de ejemplo no sensible; bloque comentado «perfil Azure» |
| `requirements.txt` | `azure-identity>=1.17` (única dependencia nueva; se declara aquí porque `CHECKPOINTS.md` C3 prohíbe dependencias no previstas) |
| `infra/00_vars.ps1` | **Solo** las variables de Postgres e identidad: `$PG_RG`, `$PG_SERVER`, `$PG_HOST`, `$PG_DB`, `$PG_OWNER_ROLE`, `$PG_RO_ROLE`, `$MI_NAME`. `$RG`, `$CAE`, `$JOB`, `$ACR`, `$CRON` y `$SUB` **no se tocan**: son de F-003 / F-012 |
| `docs/ARCHITECTURE.md` | Sección «Acceso a datos» e «Infra»: servidor real, base `sigrid_dm`, los dos roles, los cinco esquemas de consumo, y el enlace al runbook |
| `harness/features.json` | Descripción de F-005 corregida (R41) |
| `progress/current.md` | Verificaciones `MANUAL (humano)` con su comando exacto y decisiones abiertas |

### Variables nuevas (`.env`)

```
PG_SSLMODE=              # vacío = 'require' si el host es de Azure, 'prefer' si no
PG_AUTH_MODE=password    # 'password' | 'entra'
PG_AUTO_CREATE_DB=true   # false contra Azure: la base la crea el humano
PG_SET_ROLE=             # 'sigrid_dm_etl' contra Azure
PG_READONLY_ROLE=        # 'mcp_sigrid_dm_ro' contra Azure; vacío = no aplicar grants
PG_CONSUMPTION_SCHEMAS=mart,cierre,compras,maestro,retenciones
```

Los valores por defecto son exactamente los del comportamiento de hoy: un
`.env` local sin tocar sigue funcionando igual (R8).

## 4. Ficheros que NO se tocan

- **Todo el SQL de negocio**: `sql/stg/`, `sql/mart/`, `sql/cierre/`,
  `sql/compras/`, `sql/maestro/`, `sql/retenciones/`, `sql/auxiliar/`. F-005
  no cambia ni una regla de negocio, y es lo que hace comparable la huella de
  las vistas entre local y Azure.
- `etl_sigrid/domain/` — sigue sin imports de infraestructura.
- `etl_sigrid/infrastructure/sigrid/` — la extracción no cambia.
- `etl_sigrid/application/steps/` salvo el fichero nuevo. En particular
  `load_excel_aux_step.py` es **de F-004**, no de esta feature.
- `infra/10_create_rg.ps1`, `20_build_image.ps1`, `30_create_job.ps1`,
  `40_update_job.ps1`, `Dockerfile` — F-003.
- `config/tables_sigrid.yaml`, `config/business_rules.yaml`.
- `.env` — regla dura del arnés.
- **Las bases `albaranes` y `partes` y los parámetros globales del servidor.**

## 5. SQL nuevo, y en qué capa

F-005 **no añade SQL a ninguna capa del datamart**. No hay ficheros nuevos en
`stg/`, `mart/` ni `cierre/`, así que no aplica la numeración `NN_nombre.sql`
de esas capas ni la semántica de fases y ámbitos.

El SQL que sí aparece es de dos tipos, ambos fuera del pipeline de negocio:

1. **Provisión** — `infra/sql/01_create_database.sql`,
   `infra/sql/02_roles.sql`, `infra/sql/03_diagnostico.sql`. Se ejecutan a mano
   con `psql`, con privilegios de administrador, una sola vez (los dos
   primeros) o cuantas veces haga falta (el tercero, de solo lectura).
2. **Permisos** — generados en Python por `grants.py` y ejecutados por
   `ApplyGrantsStep` en cada `run-all`.

Tablas y vistas afectadas: **ninguna**. `_meta.etl_runs` se usa tal cual está;
su DDL (`sql/ddl/00_meta.sql`) ya tiene todas las columnas necesarias
(`stage`, `step`, `started_at`, `finished_at`, `status`, `rows_processed`,
`error_message`, `metadata`) y no cambia.

## 6. Encaje en la arquitectura

| Pieza | Capa | Cumple |
|---|---|---|
| `EntraTokenProvider`, `conninfo`, `grants`, `fingerprint`, `step_run_recorder` | infrastructure | Adaptadores; ningún import desde `domain` |
| `StepRunRecorder` (Protocol) | application | Puerto; la implementación se inyecta desde `main.py` |
| `ApplyGrantsStep` | application | Hereda de `steps/base.py::PipelineStep`, se compone en `main.py` como el resto |
| Comandos CLI | `main.py` | Click, coherente con los ~40 comandos existentes |

Se respeta que **el pipeline se compone en `main.py`, no dentro de los steps**.

## 7. Riesgos y decisiones

### 7.1 `Standard_B1ms` — 1 vCPU y 2 GB de RAM

Las transformaciones de `mart` y `cierre` son pesadas y comparten CPU con
`albaranes` y `partes`. El job es nocturno, así que no compite, pero un SKU
Burstable **agota créditos de CPU**: si la carga es larga, el rendimiento cae
a la línea base a mitad de ejecución.

Mitigación, no eliminación: **medir** (R28-R31). `_meta.etl_runs` con un paso
por fila y `python main.py timings` dan el dato. El veredicto se escribe en
`progress/medicion_carga_inicial.md`, es el que decide si se escala el SKU
—operación en caliente, un reinicio— y es la entrada de F-011.

Se descartó dimensionar a ojo antes de medir: la recomendación del propio
`progress/current.md` es «no construir el incremental todavía; instrumentar la
primera carga completa y decidir con números».

### 7.2 32 GB compartidos, y el disco solo crece

Sigrid son ~4 GB en origen; `raw` + `stg` + `mart` con índices proyecta 10-12 GB.
Con `albaranes` y `partes` dentro, el margen puede no existir. Por eso R25 y
R26 hacen de la comprobación de espacio una **puerta bloqueante**, no un
consejo, con umbral explícito de 14 GB libres.

Ampliar almacenamiento en un Flexible Server es **irreversible**: se puede
subir de 32 GB, nunca bajar, y la factura sube para siempre. Decisión que no
toma el implementer.

Palanca conocida si el espacio aprieta, para F-011: `raw` es un espejo
regenerable de Sigrid y es el mayor consumidor.

### 7.3 Servidor compartido con producción

Cualquier error de alcance afecta a dos aplicaciones vivas. Contramedidas:

- R11 y su barrido estático: ninguna sentencia del ETL nombra `albaranes` ni
  `partes`, ni contiene `ALTER SYSTEM`.
- `PG_AUTO_CREATE_DB=false` en Azure: el auto-bootstrap perezoso actual se
  conecta a la base `postgres` y ejecuta `CREATE DATABASE`. Eso, contra un
  servidor de producción y con un rol que no debe tener ese privilegio, es un
  fallo esperando a ocurrir. Se desactiva y la base la crea el humano una vez.
- Habilitar Entra (R12) y `REVOKE CONNECT` (R19) quedan explícitamente fuera
  del alcance del implementer: autorización escrita del humano.

### 7.4 Sin HA, PITR de 7 días — y de servidor entero

La recuperación de `sigrid_dm` es **volver a ejecutar el ETL**, no restaurar.
Y no es solo una preferencia: el PITR de un Flexible Server restaura **el
servidor completo** a un instante pasado, lo que arrastraría `albaranes` y
`partes`. Para este datamart, el backup del servidor **no es un mecanismo de
recuperación utilizable**. Queda escrito en el runbook (R39) para que nadie
asuma otra cosa.

### 7.5 Los permisos del MCP se destruyen en cada ejecución

No es una hipótesis: `cierre/03_views.sql`, `04_views_detalle.sql`,
`05_views_cabecera.sql`, `06_views_planif_vs_real.sql`,
`mart/05_views_powerbi.sql`, `mart/05b_...` y `compras/03_views.sql` hacen
`DROP VIEW ... CASCADE` seguido de `CREATE VIEW`. Un `DROP` se lleva los
`GRANT` por delante. De ahí que R16 exija reaplicarlos y que R15 añada
`ALTER DEFAULT PRIVILEGES` como red de seguridad para lo que se cree después.

**Aviso operativo que va al runbook**: `run-all` compone hoy solo
`ingest_raw → load_excel_aux → build_stg → build_mart`. Los módulos `cierre`,
`compras`, `maestro` y `retenciones` se construyen con comandos aparte
(`build-cierre`, `build-compras`, `build-maestros`, `build-retenciones`), que
también recrean vistas. Tras ejecutarlos hay que lanzar
`python main.py apply-grants`. Ampliar `run-all` para incluirlos es un cambio
de alcance mayor y **no es de esta feature**.

### 7.6 La huella de vistas y el tiempo

Sigrid está vivo: la captura local y la de Azure no son del mismo instante.
Comparar el total sin más produciría diferencias inexplicables y ruido que
acabaría en «pues será eso». Por eso la huella se parte en tres bloques y el
criterio duro se aplica solo donde significa algo: **estructura** (que no
depende del dato) y **meses cerrados** (inmutables por definición de negocio:
`fas=1..N` son cierres). El bloque vivo se informa como aviso.

Alternativa descartada: congelar Sigrid o cargar Azure desde un volcado del
Postgres local. Lo primero no está en nuestra mano; lo segundo verificaría la
copia, no el ETL contra Azure, que es lo que hay que verificar.

### 7.7 Alternativas descartadas en el diseño de conexión

- **Cadena de conexión fija en vez de proveedor callable.** Descartada: el
  token de Entra caduca y el ETL abre conexiones a lo largo de toda la
  ejecución. Una cadena fija fallaría a mitad de la carga inicial, que es
  justo la ejecución más larga.
- **Caída automática a contraseña si falla Entra.** Descartada (R5): convierte
  un fallo de configuración en un cambio silencioso de modelo de seguridad.
- **`GRANT` desde un `.sql` con bloque `DO $$`.** Descartada: el troceador de
  sentencias de `postgres_client.py` no maneja `$$`, según su propio docstring.
- **Un solo rol con lectura y escritura.** Descartada por el enunciado y por
  el sentido común: el MCP es una superficie de consulta abierta a lenguaje
  natural.
