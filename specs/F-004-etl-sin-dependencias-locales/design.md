<!-- specs/F-004-etl-sin-dependencias-locales/design.md -->
# F-004 · Ejecutar el ETL en Azure sin dependencias locales — Diseño

## 1. Idea del diseño en una frase

Un **puerto de lectura de ficheros auxiliares** con dos adaptadores —disco y
Azure Blob Storage— elegidos por la **forma del valor** de `AUX_EXCEL_*`, y un
`LoadExcelAuxStep` que deja de ser un stub y pasa a obtener los tres libros a
través de ese puerto, en memoria.

Ninguna variable de entorno nueva. Ningún secreto. Ninguna infraestructura.

---

## 2. Ficheros a crear

| Ruta exacta | Capa | Contenido |
|---|---|---|
| `etl_sigrid/infrastructure/excel/aux_file_source.py` | infrastructure | `AuxFileRef`, jerarquía de errores, `parse_aux_file_ref()`, protocolo `AuxFileSource`, `LocalAuxFileSource`, fábrica `get_aux_file_source()` |
| `etl_sigrid/infrastructure/excel/blob_aux_file_source.py` | infrastructure | `BlobAuxFileSource`: descarga a memoria con `DefaultAzureCredential` y traducción de errores del SDK |
| `tests/test_f004_aux_file_source.py` | tests | R1–R11 sobre el puerto y los dos adaptadores |
| `tests/test_f004_load_excel_aux_step.py` | tests | R12–R14 sobre el step, con fuente inyectada |
| `tests/test_f004_sin_dependencias_locales.py` | tests | R15–R16, auditoría |

El paquete `etl_sigrid/infrastructure/excel/` **ya existe** con un `__init__.py`
vacío. Es su sitio natural: no se crea estructura nueva.

## 3. Ficheros a modificar

| Ruta exacta | Qué cambia |
|---|---|
| `etl_sigrid/application/steps/load_excel_aux_step.py` | Reescritura del stub. Recibe una fábrica de fuentes inyectable; lee, valida y reporta. Sigue sin tocar Postgres. |
| `config/settings.py` | Docstring de `AuxExcelSettings` (ruta local **o** URI de blob) + método `entries()` que devuelve las tres tuplas `(nombre_lógico, variable_de_entorno, valor)`. Evita duplicar los nombres `AUX_EXCEL_*` en el step. |
| `requirements.txt` | `azure-identity` y `azure-storage-blob` (§7). |
| `.env.example` | Documentar las dos formas admitidas; sustituir la ruta personal de OneDrive por un ejemplo neutro y añadir el ejemplo de URI de blob comentado. |
| `docs/ARCHITECTURE.md` | Una entrada en «Acceso a datos»: los Excels auxiliares se leen de ruta local o de Azure Blob Storage con identidad gestionada. |

## 4. Ficheros que NO se tocan

Están al lado y tientan. Quedan fuera:

- `etl_sigrid/application/orchestrator.py` y `steps/base.py` — el contrato del
  step no cambia. Solo cambia su implementación.
- `etl_sigrid/application/steps/{ingest_raw,build_stg,build_mart,build_maestros,build_cierre}_step.py`
  — auditados en §8, sin acción.
- Todo `etl_sigrid/infrastructure/postgres/sql/**` — F-004 no escribe SQL.
- `etl_sigrid/infrastructure/postgres/postgres_client.py` — el step no toca
  Postgres, ni siquiera para crear el schema `aux` (ya lo crea el bootstrap:
  `SCHEMAS = ("raw", "aux", "stg", "mart", "_meta")`).
- `Dockerfile` — ya copia `config/`, `etl_sigrid/` y `main.py`, que es todo lo
  que el ETL necesita en ejecución. R16 lo **verifica**, no lo modifica.
- `infra/**` — es F-003.
- `main.py` — sigue construyendo `LoadExcelAuxStep(settings)`; el parámetro
  nuevo del constructor es opcional y solo lo usan los tests.
- `harness/features.json` — el estado de la feature lo mueve el líder.

---

## 5. Clases y funciones

### 5.1 `etl_sigrid/infrastructure/excel/aux_file_source.py`

```python
BLOB_HOST_SUFFIX = ".blob.core.windows.net"

class AuxFileError(RuntimeError): ...
class AuxFileConfigError(AuxFileError): ...       # R5, R6, R7
class AuxFileNotFoundError(AuxFileError): ...     # R8 local, R9 blob
class AuxFileAccessError(AuxFileError): ...       # R10

@dataclass(frozen=True, slots=True)
class AuxFileRef:
    logical_name: str          # "tipo_partida"
    env_var: str               # "AUX_EXCEL_TIPO_PARTIDA"
    origin: str                # "local" | "blob"
    local_path: str | None
    account: str | None
    container: str | None
    blob_name: str | None

    @property
    def display(self) -> str:
        """Ubicación legible y segura para log (nunca query string)."""

def parse_aux_file_ref(logical_name: str, env_var: str, raw_value: str) -> AuxFileRef

class AuxFileSource(Protocol):
    def read_bytes(self, ref: AuxFileRef) -> bytes: ...

class LocalAuxFileSource:
    def read_bytes(self, ref: AuxFileRef) -> bytes: ...

def get_aux_file_source(ref: AuxFileRef) -> AuxFileSource
```

**Reglas de `parse_aux_file_ref`** (orden exacto, es lo que fija R2/R3/R5–R7):

1. Valor vacío o solo espacios → `AuxFileConfigError`. (El step filtra las
   vacías antes de llamar; llegar aquí con vacío es un bug.)
2. Empieza por `https://` (sin distinguir mayúsculas):
   - host termina en `.blob.core.windows.net` → origen `blob`;
   - si no → `AuxFileConfigError` nombrando la variable y el host (R5).
3. Empieza por `http://` → `AuxFileConfigError`: la identidad gestionada exige
   TLS.
4. Cualquier otra cosa → origen `local`, `local_path = raw_value`. Cubre
   `C:/...`, `C:\...`, `/datos/...` y UNC `\\servidor\recurso\...`.

**Descomposición de la URI de blob**: `account` = host sin el sufijo;
`container` = primer segmento del path; `blob_name` = **el resto entero**, con
sus barras (R2). Si falta contenedor o blob → `AuxFileConfigError` mostrando la
forma esperada (R7). Si hay query string o fragmento → `AuxFileConfigError`
cuyo mensaje **corta antes del `?`** (R6): el token no entra ni en el log ni en
la excepción.

`display` devuelve `ruta local: <path>` o
`blob: <cuenta>/<contenedor>/<blob>` — nunca la URI cruda.

**`LocalAuxFileSource.read_bytes`**: `Path(ref.local_path).read_bytes()` con
traducción `FileNotFoundError`/`IsADirectoryError` → `AuxFileNotFoundError` y
`PermissionError`/`OSError` → `AuxFileAccessError`. Mensaje de R8, plantilla:

```
No se encuentra el Excel auxiliar 'tipo_partida' en la ruta local
'D:/datos/TipoPartida.xlsx' (variable AUX_EXCEL_TIPO_PARTIDA).
Comprueba que la ruta existe y es accesible para el usuario que ejecuta el ETL.
En un contenedor de Azure las rutas locales NO existen: usa una URI de blob
'https://<cuenta>.blob.core.windows.net/aux/TipoPartida.xlsx'.
```

**`get_aux_file_source`**: `local` → `LocalAuxFileSource()`; `blob` → importa
`blob_aux_file_source` **de forma perezosa** (dentro de la función) y devuelve
`BlobAuxFileSource()`. Así un entorno sin el SDK de Azure instalado sigue
ejecutando el camino local y **toda** la batería de tests.

### 5.2 `etl_sigrid/infrastructure/excel/blob_aux_file_source.py`

```python
class BlobAuxFileSource:
    def __init__(self, blob_client_factory: Callable[[AuxFileRef], Any] | None = None) -> None
    def read_bytes(self, ref: AuxFileRef) -> bytes
```

- `blob_client_factory` por defecto: import perezoso de
  `azure.identity.DefaultAzureCredential` y `azure.storage.blob.BlobClient`;
  construye
  `BlobClient(account_url=f"https://{ref.account}{BLOB_HOST_SUFFIX}",
  container_name=ref.container, blob_name=ref.blob_name,
  credential=DefaultAzureCredential())`.
  La credencial se crea **una vez por instancia** y se reutiliza para los tres
  ficheros.
- `read_bytes` → `client.download_blob().readall()`; devuelve `bytes`. **Nada
  toca el disco** (R11).
- Traducción de errores del SDK, capturados **por nombre de clase** para no
  atarse a la jerarquía de `azure-core`:
  - `ResourceNotFoundError` → `AuxFileNotFoundError` (R9).
  - `ClientAuthenticationError`, `CredentialUnavailableError`, o
    `HttpResponseError` con `status_code in (401, 403)` →
    `AuxFileAccessError` (R10).
  - `ImportError` del import perezoso → `AuxFileAccessError` indicando
    `pip install -r requirements.txt`.
  - Cualquier otra → `AuxFileError` con el tipo y el texto del original.
- **Inyectar la fábrica es lo que hace testeable el adaptador sin red y sin el
  SDK instalado**: los tests pasan un doble que devuelve los bytes de un
  `.xlsx` generado en `tmp_path`, o que lanza una excepción falsa con el nombre
  de clase correspondiente.

Mensaje de R10, plantilla:

```
Acceso denegado al leer el Excel auxiliar 'tipo_coste'
(blob: stdatamartsegdev/aux/TipoCoste.xlsx, variable AUX_EXCEL_TIPO_COSTE).
La identidad que ejecuta el ETL necesita el rol 'Storage Blob Data Reader'
sobre la cuenta de almacenamiento 'stdatamartsegdev'.
En Azure: comprueba que el Container Apps Job tiene identidad gestionada y
ese rol asignado. En local: ejecuta 'az login' con una cuenta que lo tenga.
```

### 5.3 `config/settings.py`

```python
class AuxExcelSettings(BaseSettings):
    """Ubicación de los Excels auxiliares: ruta local/de red o URI de blob."""

    def entries(self) -> tuple[tuple[str, str, str], ...]:
        """(nombre_lógico, variable_de_entorno, valor) de los tres ficheros."""
```

Los campos no cambian de tipo ni de nombre: siguen siendo tres `str` con
default `""`. Solo cambia lo que un valor **puede** contener.

### 5.4 `etl_sigrid/application/steps/load_excel_aux_step.py`

```python
class LoadExcelAuxStep(PipelineStep):
    def __init__(
        self,
        settings: Settings,
        *,
        source_factory: Callable[[AuxFileRef], AuxFileSource] = get_aux_file_source,
    ) -> None
```

`run()`:

1. `entries = self._settings.aux_excel.entries()`.
2. Reparte en configuradas / vacías. **Si no hay ninguna configurada →
   `SKIPPED`** con el mensaje de qué variables faltan (R13). Este es el caso
   normal de un entorno de desarrollo recién clonado y **no debe romper
   `run-all`**.
3. Para cada configurada, acumulando errores en vez de abortar al primero
   (mismo criterio que `_preflight_check` de `build_stg_step`):
   `parse_aux_file_ref` → `source_factory(ref)` → `read_bytes(ref)` →
   `openpyxl.load_workbook(BytesIO(data), read_only=True, data_only=True)` →
   recoger `sheetnames`, cerrar el libro.
   Un `.xlsx` corrupto lanza excepción de `openpyxl` → se traduce a fallo del
   fichero, nombrándolo (R14).
4. Si hay errores → `FAILED` con **todos** ellos en un único mensaje,
   separados como hace `build_stg_step` (`\n\n  · `).
5. Si no → `SUCCESS`, `rows_processed` = **número de ficheros leídos**
   (documentado: no son filas de datos, porque nada se carga todavía), y
   `metadata`:

```python
{
  "files": {
    "tipo_partida": {"origen": "blob", "ubicacion": "...", "bytes": 24576,
                     "hojas": ["Hoja1"]},
    ...
  },
  "omitidos": ["mapeo_proporcionales"],
}
```

6. Log estructurado por fichero: `aux_file_read` con `logical_name`, `origen`,
   `ubicacion` (la de `display`, nunca la URI cruda), `bytes`.

**Sigue sin `depends_on`**: no depende de la ingesta y ningún step depende de
él, así que su resultado no arrastra a nadie a `SKIPPED` en el orquestador.

---

## 6. SQL

**Ninguno.** F-004 no crea ni modifica ficheros en
`etl_sigrid/infrastructure/postgres/sql/**`, no toca capas `stg`/`mart`/
`cierre`, y no escribe en Postgres. El schema `aux` ya lo crea el
auto-bootstrap del cliente.

---

## 7. Dependencias nuevas — justificación

`requirements.txt` (van a la imagen; `requirements-dev.txt` no se instala en
el contenedor):

| Paquete | Versión mínima | Por qué |
|---|---|---|
| `azure-identity` | `>=1.17.0` | Único camino para `DefaultAzureCredential`, que es lo que permite autenticar **sin cadena de conexión ni claves**: identidad gestionada en el job, sesión de `az` en el puesto. La alternativa —clave de cuenta o SAS en una variable de entorno— es exactamente lo que el diseño confirmado en `progress/current.md` descarta («Sin contraseñas»). |
| `azure-storage-blob` | `>=12.20.0` | Cliente oficial de blobs. La alternativa sería hablar con la REST API por `httpx` y firmar los tokens a mano: más código, más superficie de error y ningún beneficio. |

`azure-core` entra como dependencia transitiva; **no** se declara suelta.

Coste: unos 15 MB en la imagen y un `pip install` más lento. Aceptable para un
job nocturno. El import es **perezoso**: quien ejecute solo el camino local no
paga arranque, y la suite de tests corre aunque el SDK no esté instalado.

Ninguna dependencia de test nueva: los `.xlsx` de prueba se generan con
`openpyxl`, que ya está en `requirements.txt`.

---

## 8. Auditoría del resto del pipeline (punto 3 del alcance)

Barrido de `etl_sigrid/`, `config/` y `main.py` buscando rutas absolutas,
escritura de temporales y lectura de configuración fuera del repositorio.

| # | Hallazgo | Veredicto | Acción en F-004 |
|---|---|---|---|
| 1 | `build_stg`, `build_mart`, `build_maestros` y `build_cierre` resuelven su `sql_dir` con `Path(__file__).resolve().parents[2] / "infrastructure" / "postgres" / "sql" / <capa>` | **Correcto.** Relativo al paquete; el `Dockerfile` hace `COPY etl_sigrid/`, así que los SQL viajan en la imagen | Ninguna. Queda blindado por R16 |
| 2 | `Settings._load_yaml` lee `config/tables_sigrid.yaml` y `config/business_rules.yaml` vía `Path(__file__).resolve().parent` | **Correcto.** El `Dockerfile` hace `COPY config/` | Ninguna. Blindado por R16 |
| 3 | `main.py` añade la raíz al `sys.path` con `Path(__file__).resolve().parent` | **Correcto.** Relativo al fichero | Ninguna |
| 4 | `SettingsConfigDict(env_file=".env")` en las cuatro clases de settings | **Aceptable.** En el contenedor no hay `.env` y pydantic-settings lo ignora en silencio: la configuración llega por variables de entorno, como declara el `Dockerfile`. Riesgo residual **solo en local**: `.env` se resuelve contra el *cwd*, así que lanzar el CLI desde otro directorio lo pierde sin avisar | Se documenta. Sin acción: cambiarlo afectaría a las cuatro clases y al arranque, fuera del alcance |
| 5 | `build_stg_step` es el único de los cuatro que **no** comprueba `sql_path.exists()` antes de ejecutar | **Menor.** Un SQL ausente daría un error críptico en vez de «SQL file no encontrado». No es dependencia del sistema de ficheros local: el fichero viaja en la imagen o no existe en ninguna parte | Se documenta, **no se corrige**. Probarlo exigiría *mockear* `PostgresClient` para cero ganancia funcional. Candidato a backlog |
| 6 | Ningún step escribe ficheros temporales, ni logs a disco: `logging_config.py` emite a `stdout` | **Correcto**, y es justo lo que consume Log Analytics | Ninguna. La lectura de blob mantiene la propiedad (R11) |
| 7 | `scripts/` y `patches/` contienen rutas locales y utilidades sueltas | **Irrelevante para el despliegue**: el `Dockerfile` no los copia, no forman parte del pipeline | Ninguna. Excluidos del barrido de R15 |
| 8 | No existe `.dockerignore` | **Sin riesgo hoy**: el `Dockerfile` copia rutas explícitas (`config/`, `etl_sigrid/`, `main.py`), así que `.env` no puede colarse en la imagen | Se documenta. Añadirlo es endurecimiento de F-003 |
| 9 | `LoadExcelAuxStep` es un stub, no lee nada | **Es el objeto de esta feature** | Se reescribe (§5.4) |

**Conclusión de la auditoría: la única dependencia real del sistema de
ficheros local del pipeline son los tres `AUX_EXCEL_*`.** Todo lo demás se
resuelve relativo al paquete y viaja dentro de la imagen. El resto de la tabla
son observaciones, no defectos en alcance.

---

## 9. Riesgos y decisiones descartadas

### Decisiones tomadas

- **Discriminar por la forma del valor, no por una variable `AUX_SOURCE=blob`.**
  Una variable de modo obliga a mantener dos configuraciones coherentes y
  permite el estado absurdo «modo blob con ruta de Windows». La URI ya lleva
  toda la información.
- **Fábrica inyectable en el step y en el adaptador de blob.** Es lo que
  permite cumplir la regla dura de «tests sin red»: los dobles se inyectan en
  el límite, sin parchear módulos de terceros.
- **Rechazar el SAS en vez de admitirlo.** Un SAS en `AUX_EXCEL_*` sería un
  secreto en una variable de entorno, en contra del diseño confirmado. Mejor
  fallar en el arranque con un mensaje que lo explique que aceptarlo y que
  caduque una noche cualquiera.
- **`SKIPPED` cuando no hay variables configuradas, `FAILED` cuando las hay y
  el fichero no está.** «No me han dicho dónde está» y «me han dicho dónde
  está y no está» son problemas distintos y merecen desenlaces distintos.

### Alternativas descartadas

- **Montar el blob como volumen en el Container Apps Job** (Azure Files). Mueve
  el problema a la infraestructura, ata el ETL a un montaje concreto y deja el
  código local sin cambiar; además no funciona en el puesto del desarrollador.
- **Hablar con la REST API de blobs por `httpx`.** Habría que firmar tokens a
  mano y reimplementar reintentos. `azure-storage-blob` ya lo hace.
- **Descargar el blob a un temporal y pasar la ruta a `openpyxl`.** Reintroduce
  la dependencia del sistema de ficheros que esta feature viene a eliminar, y
  falla si el contenedor tiene el filesystem en solo lectura.
- **Meter en F-004 la carga a `aux.*`.** Requiere el esquema de los tres Excel
  y las tablas destino, que no están en el repositorio (ver `requirements.md`,
  «Frontera explícita»). Sería inventar el modelo de datos de Negocio.

### Riesgos

- **`DefaultAzureCredential` con identidad *user-assigned*** necesita
  `AZURE_CLIENT_ID` en el entorno. El SDK la lee solo, así que no hace falta
  nada en `config/settings.py`, pero **F-003 debe inyectar esa variable** si
  el job no usa identidad *system-assigned*. Anotado como dependencia hacia
  F-003.
- **Nombres reales de cuenta, contenedor y blobs**: F-004 asume la forma
  `https://<cuenta>.blob.core.windows.net/aux/<Fichero>.xlsx` conforme a D5
  (cerrada: cuenta nueva del proyecto, contenedor `aux`, en
  `rg-datamart-seg-dev`). Los valores concretos son datos de configuración,
  no de código: no se hardcodean en ninguna parte.
- **Primer arranque en Azure**: `DefaultAzureCredential` recorre varias
  credenciales antes de acertar y puede tardar unos segundos. Irrelevante en
  un job nocturno.
- **La feature no se puede verificar de extremo a extremo hasta F-003.** Los
  tres puntos MANUAL de `requirements.md` quedan pendientes del humano.
