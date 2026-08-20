<!-- specs/F-011-carga-incremental/design.md -->
# F-011 · Carga incremental del datamart — Diseño técnico

> Se lee **después** de `requirements.md`. El orden de los bloques A / B es
> normativo: el bloque B no se escribe hasta que el humano firme la puerta de
> R8.

> **Cambio del 2026-08-18.** El humano cerró seis de las siete decisiones
> abiertas y dejó **DA-1 sin decidir**. Con ella sale de esta feature el
> **bloque C entero** (ventana de negocio y acotado del build), que pasa a
> `specs/F-025-ventana-negocio-build/`. Este diseño ya no contiene
> `perfil-ventana`, ni el bloque `ventana:` de `config/business_rules.yaml`,
> ni `fetch_peso_ventana`. Ver `requirements.md` §0.0 y su sección
> «Decisiones cerradas».

## 1 · El diagnóstico, antes del diseño

### 1.1 Dónde se va el tiempo (dato, no estimación)

Carga completa del job en Azure del 2026-08-18 (`caj-datamart-seg-dev-6a95hln`,
165 min): ingesta **33 min (20 %)**, `build_stg` **111 min (67 %)**,
`build_mart` **21 min (13 %)**.

La feature nace de una sospecha razonable —«el cuello puede estar en la
extracción, porque sigrid-api sirve 1.000 filas por petición y el balanceador
corta a los 230 s»— que este dato **no confirma**. Dos matices que hay que
medir antes de darla por refutada del todo:

1. **El límite de filas no es el documentado — y ya está zanjado (DA-6).**
   `azure-apps/sigrid_api.md` (línea 245) documenta `DEFAULT_MAX_ROWS /
   MAX_ALLOWED_ROWS = 200 / 1000`, pero **el cap real son 20.000 filas por
   petición**, confirmado por el humano el 2026-08-18. Este ETL usa
   `page_size = 10000`: **trabaja por debajo del límite real y le sobra
   margen**. Los 20,05 M de filas en 33 min encajan con páginas de 10.000
   (≈2.005 peticiones, ~1 s cada una), como tenía que ser.
   **Consecuencia para el diseño:** la premisa «sigrid-api limita a 1.000
   filas» que abre la feature queda **refutada**; el `bench-sigrid` ya no
   sirve para descubrir el cap, sino para responder dos preguntas distintas:
   ¿subir de 10.000 a 20.000 compra tiempo, o el coste está en el SQL Server
   y no en el transporte? (R4) y ¿cuál es el corte real del balanceador,
   documentado en 120 s y en uso a 230 s? (R5-bis, lo único que sigue sin
   acreditar). **El documento equivocado lo corrige su dueño, no este
   proyecto** (T8-bis).
2. **El agregado esconde el reparto.** 33 min entre 31 tablas puede ser
   uniforme o puede ser `obrparpre` (13,76 M filas) llevándose la mitad. R3
   existe para eso, y la respuesta ya está guardada: cada tabla tiene su fila
   `ingest_raw.<tabla>` en `_meta.etl_runs` con `started_at`, `finished_at` y
   `rows_processed`. **No hace falta ejecutar ninguna carga nueva para
   medirlo.**

Y un tercer matiz que no es de tiempo sino de riesgo: la ingesta es donde
murió el intento de abril y donde murió la noche del 18-ago (`timeout_seconds`
300 > 230). Que solo cueste el 20 % del tiempo no la hace inofensiva.

### 1.2 La marca de modificación: `tiemod` existe y ya está en `raw`

Verificado contra `azure-apps/sigrid_tablas.md` (ver §0.2 de
`requirements.md`): `fecalt` sale en 18 filas del diccionario (no 16),
`fecmod` en 6 (no 3), `sello` en 2 (correcto) — y **`tiemod` («Tiempo
modificación», tipo «Real tiempo») en 232 filas, ~190 tablas**.

Cadena que ya está montada en el código de hoy:

- `config/tables_sigrid.yaml` declara `incremental_column: tiemod` en 17 de
  las 31 tablas; en las otras 14 (catálogos: `conext`, `cen`, `auxobrtip`,
  `auxpro`, `auxmun`, `condir`, `obrprv`, `prv`, `rec`, `dcfprodes`…) está a
  `null` con el comentario «refresco completo».
- `ingest_raw_step._ingest_one_table` pasa esa columna a
  `postgres_client.copy_rows(tiemod_column=...)`.
- `copy_rows` la vuelca a la columna `_source_tiemod DOUBLE PRECISION` que
  `ensure_raw_table` añade a toda tabla de `raw`.

Es decir: **el datamart ya tiene guardado, carga tras carga, el valor de la
marca de modificación de Sigrid**. Si sirve o no como watermark se responde
con SQL local (R6, R7), sin una sola petición a Sigrid. Ese es el diseño
barato que la feature pedía y que el hallazgo heredado de F-009 dejaba fuera
de foco.

**Lo que no se puede saber sin dos cargas**: si `tiemod` avanza en toda fila
modificada. Por eso R7 compara dos fotografías y emite `SIRVE` / `NO SIRVE` /
`SIN EVIDENCIA`, y por eso R19 impide activar el modo `tiemod` sin ese
veredicto registrado.

### 1.3 El choque con F-024, y cómo se resuelve

`domain/coherencia.py::evaluar_coherencia_raw` exige que **todas** las tablas
declaradas vengan del **mismo** `batch_id` y en `SUCCESS`. Una carga
incremental que solo tocara las tablas con novedades dejaría `raw` con
`obrparpre` del batch de hoy y `cen` del batch del domingo → `batches_distintos`
→ **KO** → `build_stg` se niega. El `raw` estaría perfecto y la puerta lo
declararía roto. Peor: el mensaje de error mandaría hacer `ingest --full`,
deshaciendo la feature todas las noches.

**Solución elegida (R9): no se toca la puerta; se cambia lo que significa una
fila de ingesta.** En modo incremental, cada ejecución escribe fila
`ingest_raw.<tabla>` para **todas** las tablas declaradas, traiga o no filas
nuevas. La fila pasa de significar «esta tabla se cargó entera en este batch» a
significar «esta tabla se **puso al día** en este batch», que es exactamente
la garantía que la puerta necesita para dejar construir `stg` encima.

Alternativas descartadas:

- **Relajar la puerta** (aceptar batches distintos si son posteriores a la
  última `full`). Toca `domain/coherencia.py`, el corazón de F-024, con
  cobertura y mutación al 100 %, para debilitar precisamente la invariante que
  esa feature construyó hace un día. No.
- **Un `batch_id` sintético compartido entre cargas.** Rompe la ordenación
  cronológica del identificador y con ella `v_frescura`, `timings` y el
  `ORDER BY batch_id` que F-024 diseñó explícitamente para no parsear nada.

**Efecto secundario que hay que declarar**: en modo incremental,
`rows_processed` (y por tanto `_meta.v_raw_state.filas`) pasa a ser «filas
escritas esta noche», no «filas que tiene la tabla». Por eso R10 añade
`filas_en_tabla` a `metadata` y el bloque B amplía `_meta.v_raw_state` con dos
columnas **al final** (`modo`, `filas_en_tabla`), que es lo único que
`CREATE OR REPLACE VIEW` permite sin romper a quien ya la consulta (MCP y
Power BI).

### 1.4 Límite de microservicio

Evaluado según manda el protocolo del `spec-author`:

- **Todo el bloque A y el B pertenecen a este servicio.** Son la extracción y
  la contabilidad de la extracción: su casa es `etl_sigrid`.
- **Lo que NO pertenece aquí: los límites de sigrid-api.** Si la medición
  demuestra que la extracción es el cuello (cortes a 230 s, tamaño de página),
  el arreglo —subir `MAX_ALLOWED_ROWS`, añadir un endpoint de exportación
  masiva, revisar el timeout del balanceador— es trabajo **del proyecto
  `sigrid-api`**, y se le pide a su dueño con los números de `bench-sigrid` en
  la mano. Este ETL no implementa aquí ni un atajo ni una conexión directa al
  SQL Server: `sigrid-api` es el único acceso (`CLAUDE.md` § ecosistema).
  **Tampoco edita `azure-apps/sigrid_api.md`, que es de ese proyecto** — y eso
  incluye el dato de DA-6: sabemos que el documento está mal (dice 1.000, el
  cap real son 20.000) y lo que hacemos es **avisar al dueño** (T8-bis), no
  corregirlo nosotros.
- **El bloque C rozaba otra frontera distinta**, la del dominio: acotar el
  build a «obras abiertas» cambia qué ve Power BI. No es un microservicio
  nuevo, es una **feature nueva con decisión de Negocio**, y desde el
  2026-08-18 ya no está aquí: es **F-025**
  (`specs/F-025-ventana-negocio-build/`). F-011 ni la mide ni la implementa;
  R22 es la barrera que lo fija con un test.

---

## 2 · Ficheros a crear

### Bloque A · Medición

| Ruta | Qué es | Capa |
|---|---|---|
| `etl_sigrid/domain/perfil_carga.py` | Funciones puras: `perfil_de_carga(filas) -> PerfilCarga`, `techo_de_mejora(perfil) -> tuple[TechoPaso, ...]`, `tablas_que_acumulan(perfil, pct) -> tuple[str, ...]`, `format_perfil(perfil) -> str`. Sin psycopg, sin click. | domain |
| `etl_sigrid/domain/extraccion.py` | Funciones puras del bench: `MedicionPagina`, `resumen_bench(mediciones) -> ResumenBench` (filas/s, latencia media, mejor tamaño), `es_sentencia_de_lectura(sql) -> bool` (R23), `comparar_cap(medido, documentado) -> Divergencia \| None` (R5, DA-6). | domain |
| `etl_sigrid/domain/tiemod.py` | Funciones puras: `EstadoTiemod` (por tabla), `veredicto_tiemod(antes, ahora) -> Veredicto` con los tres valores de R7, `format_diagnostico(...)`. | domain |
| `etl_sigrid/infrastructure/sigrid/bench_extraccion.py` | Adaptador: recorre los tamaños de página pedidos llamando a `SigridApiClient`, cronometra, captura `SigridApiPageSizeTooLargeError` y devuelve `list[MedicionPagina]`. **No importa `PostgresClient`.** | infrastructure |

### Bloque B · Ingesta incremental (solo tras la puerta de R8)

| Ruta | Qué es | Capa |
|---|---|---|
| `etl_sigrid/domain/carga_incremental.py` | `ModoCarga` (enum `FULL`/`INCREMENTAL`), `decidir_modo_de_carga(estado_watermark, hoy, cada_dias, forzar_full) -> ModoCarga` (R12), `decidir_modo_de_tabla(spec, modo_global, hay_deriva, columnas_sigrid) -> ModoTabla` (R15, R17), `motivo_del_modo(...)` para el `metadata`. Puro y exhaustivamente testeable. | domain |
| `etl_sigrid/infrastructure/postgres/sql/ddl/01_watermark.sql` | `CREATE TABLE IF NOT EXISTS _meta.ingesta_watermark (...)` + índice + ampliación aditiva de `_meta.v_raw_state`. Idempotente (R11). | infrastructure · capa `ddl` |
| `tests/test_f011_*.py` | Ver la tabla de trazabilidad de `requirements.md`. | tests |

---

## 3 · Ficheros a modificar

### Bloque A

| Ruta | Qué cambia |
|---|---|
| `main.py` | **Tres** comandos nuevos de **solo lectura**: `perfil-carga`, `bench-sigrid`, `diagnostico-tiemod`. Ninguno llama a `_arrancar_ejecucion()` (R25), igual que `timings`, `fingerprint-views` o `status`. **`perfil-ventana` ya no está aquí: es F-025.** |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | **Dos** métodos de lectura nuevos, siguiendo el patrón de `fetch_timings` / `fetch_pesos_plan_mensual`: `fetch_perfil_carga(batch_id: str \| None) -> list[FilaPerfil]` (una fila por paso y por tabla del batch) y `fetch_diagnostico_tiemod() -> list[EstadoTiemod]` (recorre las tablas de `raw` con `_source_tiemod`). Sin escrituras. **`fetch_peso_ventana` ya no está aquí: es F-025.** |
| ~~`config/business_rules.yaml`~~ | **NO SE TOCA.** El bloque `ventana:` salió a F-025 con DA-1 (R22). |

### Bloque B

| Ruta | Qué cambia |
|---|---|
| `config/settings.py` | Clase nueva `IngestaSettings` (prefijo `INGESTA_`): `modo: str = "full"`, `full_cada_dias: int = 7`, **`full_dia_semana: int = 6`** (0 = lunes … 6 = **domingo**, convenio `datetime.weekday()`; DA-2) y `deriva_max_filas: int = 0`. Todo con default y **sin secretos**; con los defaults el comportamiento es idéntico al de hoy (R18). Pydantic v2, `default=` solo en la firma (`docs/CONVENTIONS.md`). El rango de `full_dia_semana` se valida (0–6) y un valor fuera de rango es error de arranque, no un domingo silencioso. |
| `etl_sigrid/application/steps/ingest_raw_step.py` | (a) decide el modo global consultando `_meta.ingesta_watermark` y `decidir_modo_de_carga`; (b) recorre **todas** las tablas declaradas siempre (R9); (c) por tabla, elige cursor `full` / `tiemod` / `solo-altas` con `decidir_modo_de_tabla`; (d) rellena el `metadata` de R10; (e) actualiza `_meta.ingesta_watermark`. La orquestación queda en el step; las decisiones, en el dominio. |
| `etl_sigrid/infrastructure/sigrid/sigrid_api_client.py` | `stream_table` acepta `desde_tiemod: float \| None`. Cuando viene, el `WHERE` añade `AND [tiemod] > ?` manteniendo el keyset por `ide` como orden y cursor de paginación (la paginación **no** cambia: sigue siendo `ide > ?`, que es lo que garantiza no saltarse filas). Método nuevo `count_rows(source_table, where)` para la guardia de deriva de R17. |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | `record_run_end(...)` gana un parámetro opcional `metadata: dict \| None = None` (hoy no lo tiene; `record_run_completed` sí). Métodos `leer_watermark()` / `actualizar_watermark(...)`. `_bootstrap_schemas_and_meta` pasa a ejecutar **todos** los `sql/ddl/*.sql` en orden en vez del `00_meta.sql` fijo que ejecuta hoy — sin esto, `01_watermark.sql` no se crearía nunca. |
| `main.py` | `ingest` gana `--solo-altas` y se niega sin `--full` ni modo validado (R16). `run-all` **no** gana ninguna vía de escape nueva: como en F-024, a las 02:00 no hay nadie delante. |
| `docs/ARCHITECTURE.md` | Sección nueva con el modelo de carga resultante, y **corrección** de la frase «La ingesta nocturna SIEMPRE `--full` (el cursor incremental por `ide` pierde los UPDATE)», que deja de ser toda la verdad. |
| `azure-apps/datamart_seg_anual.md` | **Solo si el bloque B se implementa**: cambia lo que este servicio consume de `sigrid-api` (frecuencia y volumen de peticiones) y sus variables de entorno. La regla de `CLAUDE.md` obliga a actualizarlo **en el mismo trabajo**. |

---

## 4 · Ficheros que NO se tocan (los que tientan)

- **`etl_sigrid/domain/coherencia.py`** — la puerta de F-024. R13 y R14 exigen
  que su comportamiento sea idéntico. Si el implementer se ve editando este
  fichero, el diseño se torció: vuelva a §1.3.
- **`etl_sigrid/infrastructure/postgres/sql/stg/*.sql` y `sql/mart/*.sql`** —
  ni una línea. Acotar el build es **F-025** (R22, con test de que los
  ficheros no cambian en esta rama).
- **`config/business_rules.yaml`** — sin bloque `ventana:`, sin predicado de
  «obra abierta». Es de F-025 y depende de DA-1, que sigue sin decidir.
- **`etl_sigrid/domain/tramos.py`, `build_stg_step.py` y el troceo de F-019** —
  el build por tramos se queda exactamente como está. Es lo que impide repetir
  el incidente del disco del 2026-08-09, y es también la pieza sobre la que
  F-025 se apoyará: F-011 no la mueve ni un milímetro.
- **`_meta.v_frescura`** — la vista de frescura de F-024 no cambia. La
  ampliación aditiva es solo de `v_raw_state` (§1.3).
- **`harness/features.json`** — lo actualiza el líder, no esta spec.
- **`azure-apps/sigrid_api.md` y `azure-apps/sigrid_tablas.md`** — documentos
  del ecosistema cuyo dueño es otro proyecto. Se leen y se citan; no se
  editan (DA-6).
- **`specs/F-023-cierre-operativo-f003/`** — otra feature, otra sesión.

---

## 5 · Clases y funciones nuevas (firma y capa)

```python
# etl_sigrid/domain/perfil_carga.py  ·  domain, puro
@dataclass(frozen=True, slots=True)
class FilaPerfil:
    stage: str; step: str; segundos: float; filas: int; status: str

@dataclass(frozen=True, slots=True)
class PerfilCarga:
    batch_id: str | None
    pasos: tuple[FilaPerfil, ...]      # pasos de pipeline (step sin punto)
    tablas: tuple[FilaPerfil, ...]     # ingest_raw.<tabla>
    total_segundos: float

def perfil_de_carga(filas: Iterable[FilaPerfil]) -> PerfilCarga: ...
def techo_de_mejora(perfil: PerfilCarga) -> tuple[TechoPaso, ...]: ...   # R2
def tablas_que_acumulan(perfil: PerfilCarga, pct: float) -> tuple[str, ...]: ...  # R3
def format_perfil(perfil: PerfilCarga) -> str: ...
```

```python
# etl_sigrid/domain/carga_incremental.py  ·  domain, puro  (bloque B)
class ModoCarga(StrEnum):
    FULL = "full"
    INCREMENTAL = "incremental"

def decidir_modo_de_carga(
    ultima_full: datetime | None, hoy: datetime,
    cada_dias: int, dia_semana_full: int,      # 0=lunes … 6=domingo (DA-2)
    modo_configurado: str, forzar_full: bool,
) -> tuple[ModoCarga, str]:           # (modo, motivo legible)  · R12, R12-bis, R18
    ...
    # FULL si: forzar_full | modo_configurado == "full" | ultima_full is None
    #        | (hoy.weekday() == dia_semana_full and ultima_full.date() < hoy.date())
    #        | (hoy - ultima_full).days >= cada_dias
    # El día de la semana es la REGLA (domingo); los días son la RED de
    # seguridad si el domingo el job no corrió. Comparación por date(), para
    # que dos ejecuciones el mismo domingo hagan UNA sola recarga completa.

def decidir_modo_de_tabla(
    tabla: str, modo_global: ModoCarga, columna_cursor: str | None,
    columnas_en_sigrid: Sequence[str], filas_raw: int, filas_sigrid: int,
    deriva_max: int,
) -> tuple[ModoCarga, str]:           # R15, R17
    ...
```

El patrón es el de F-019 y F-024, y es deliberado: **la decisión de «cómo se
carga» es dominio puro** (se prueba exhaustivamente sin BBDD y la mutación
tiene dónde morder), el step solo obedece y la infraestructura solo lee y
escribe.

---

## 6 · SQL nuevo

Un único fichero, en la capa `ddl` (la de `_meta`), numerado según la
convención `NN_nombre.sql` a continuación del que ya existe:

**`etl_sigrid/infrastructure/postgres/sql/ddl/01_watermark.sql`** (bloque B)

- `CREATE TABLE IF NOT EXISTS _meta.ingesta_watermark` con las columnas de
  R11 y `PRIMARY KEY (tabla)`.
- `CREATE OR REPLACE VIEW _meta.v_raw_state` **repitiendo las columnas
  actuales en el mismo orden** y añadiendo al final `modo` y `filas_en_tabla`,
  leídas de `metadata->>'modo'` y `(metadata->>'filas_en_tabla')::bigint`.
  Añadir columnas al final es lo único que `CREATE OR REPLACE VIEW` admite;
  reordenar o quitar exigiría `DROP ... CASCADE`, que se llevaría por delante
  los `GRANT` del rol del MCP (`docs/ARCHITECTURE.md` § permisos).
- Sin bloques `$$`: `_split_sql_statements` de `postgres_client.py` no los
  sabe trocear (por eso `infra/sql/` se ejecuta a mano con `psql`).

Ninguna capa de negocio (`stg`, `mart`, `cierre`, `compras`, `maestro`,
`retenciones`, `auxiliar`) recibe SQL nuevo en esta feature.

---

## 7 · Encaje en la arquitectura y en el pipeline

```
main.py (click)
 ├─ perfil-carga        ─┐  SOLO LECTURA. Sin batch_id, sin filas en _meta (R25)
 ├─ diagnostico-tiemod   ├─ dominio puro + fetch_* del PostgresClient
 └─ bench-sigrid        ─┘  dominio puro + SigridApiClient (lectura de Sigrid)
      (perfil-ventana ya NO está aquí: es F-025)

run-all  →  Orchestrator([
      IngestRawStep,      ← ÚNICO step que cambia (bloque B)
      LoadExcelAuxStep,   ← intacto
      BuildStgStep,       ← intacto (puerta de raw de F-024 incluida)
      BuildMartStep,      ← intacto
      ApplyGrantsStep,    ← intacto
   ])
```

La composición del pipeline sigue en `build_pipeline_steps()` de `main.py`
(`docs/CONVENTIONS.md`), y no cambia: F-011 no añade ni quita pasos. El único
step tocado es la ingesta, y solo en el bloque B.

---

## 8 · Riesgos y decisiones

| Riesgo | Mitigación en el diseño |
|---|---|
| **Implementar el bloque B y ahorrar 33 min de 165.** Es el riesgo principal de la feature entera. | Puerta de R8 con umbral numérico escrito (DA-7). El bloque A se implementa siempre; el B, solo si los números lo justifican. |
| **Romper la coherencia de F-024 el día después de cerrarla.** | R9 (fila por tabla siempre) resuelve el choque **sin tocar** `domain/coherencia.py`; R13 y R14 lo verifican con tests. |
| **Perder bajas de Sigrid en silencio.** Ni `ide` ni `tiemod` ven un `DELETE`. | Guardia de recuento por tabla (R17) + recarga completa periódica (R12) + DA-3 explícita para que el humano acepte o rechace el residuo. |
| **Que `tiemod` no sea fiable y se descubra en producción.** | Se descubre antes y gratis: R6/R7 lo miden sobre los `_source_tiemod` ya guardados, y R19 impide activar el modo sin veredicto. |
| **`_meta.v_raw_state.filas` cambia de significado y alguien lo lee.** | Ampliación **aditiva** de la vista + `filas_en_tabla` en metadata (§1.3). Ningún consumidor existente ve columnas distintas. |
| **`01_watermark.sql` no se ejecuta nunca.** El bootstrap de hoy abre `00_meta.sql` **por ruta fija**. | Cambio explícito de `_bootstrap_schemas_and_meta` a recorrer `sql/ddl/*.sql` ordenados, con su test. Está listado en §3 para que no se escape. |
| **Medir contra Sigrid en horario de trabajo.** `bench-sigrid` lanza peticiones reales al SQL Server de producción. | Solo lectura (R23), una tabla por invocación, tamaños de página acotados, y la ejecución real es tarea **MANUAL del humano**, que elige el momento. |
| **La primera incremental real deja `raw` a medias.** | La ingesta hace commit **por página**, no por tabla (DA-8 de F-024): una muerte deja la tabla truncada y parcial. En incremental **no hay TRUNCATE**, así que el riesgo baja; pero la fila queda en `RUNNING` → `ABORTED` al arrancar el siguiente comando y la puerta la rechaza igual. Ese mecanismo no se toca. |

### Alternativas descartadas

- **Conexión directa al SQL Server de Sigrid para hacer una extracción
  masiva.** Prohibido: `sigrid-api` es el único acceso (`CLAUDE.md`,
  `docs/ARCHITECTURE.md`).
- **CDC / triggers en Sigrid.** Escritura sobre el sistema origen de
  producción de un tercero. Fuera de discusión.
- **Cursor por `ide` como estrategia incremental principal.** Solo ve altas.
  Sobrevive únicamente como `--solo-altas` explícito (R16), para diagnóstico.
- **Sumas de control por tabla y obra como watermark propio** (opción (c) de
  DA-4). Descartada de entrada: leer 20 M de filas para saber cuáles cambiaron
  cuesta lo mismo que traérselas.
- **Materializar `stg`/`mart` de forma incremental por obra.** Es donde está
  el 67 % del tiempo y es tentador, pero cambia qué ve Power BI y necesita
  decisión de Negocio (DA-1) y prueba de equivalencia. **Feature propia, ya
  escrita: `specs/F-025-ventana-negocio-build/`** (DA-5 cerrada el
  2026-08-18). R22 impide que se cuele en esta rama.

### Lo que cambia en este diseño tras las decisiones del 2026-08-18

| Decisión | Qué cambia en el diseño |
|---|---|
| DA-1 sin decidir | Desaparecen del diseño `perfil-ventana`, `fetch_peso_ventana` y el bloque `ventana:` de `config/business_rules.yaml`. Van a F-025. |
| DA-2 domingos | `IngestaSettings` gana `full_dia_semana: int = 6` y `decidir_modo_de_carga` un parámetro más; la regla exacta está en R12-bis. |
| DA-3 aceptada | R17 y `deriva_max_filas = 0` se quedan como están; no se diseña comparación de conjuntos de `ide`. |
| DA-4 aceptada | La opción (c) (watermark propio por sumas de control) sale del diseño; si R7 dice `NO SIRVE`, el bloque B no se escribe. |
| DA-5 aceptada | F-025 existe y va **por delante** del bloque B si R8 lo confirma (el build es el 67 %). |
| DA-6 (cap 20.000) | §1.1 corregida; `bench-sigrid` mide hasta 20.000 y añade R5-bis (latencia máxima vs `timeout_s`); tarea T8-bis para avisar al dueño de `sigrid-api`. |
| DA-7 aceptada | El umbral (≥ 20 min o ≥ 40 %) está escrito en R8 y en la verificación de T8/T9. |
