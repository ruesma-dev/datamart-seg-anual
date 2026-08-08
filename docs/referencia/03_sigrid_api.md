<!-- docs/referencia/03_sigrid_api.md -->
# sigrid-api — microservicio de acceso al ERP Sigrid

> Origen: `sigrid_api.md`, documentación del microservicio `sigrid-api`
> (repositorio propio, fuera de este proyecto) · Fecha del documento: 2026-06-07
> Incorporado a `docs/referencia/` el 2026-08-08.
> Llegó ya en Markdown: no requirió conversión con `markitdown`.

> **Redactado.** Se han sustituido por marcadores el **ID de suscripción de
> Azure** (`<ID-SUSCRIPCION>`) y el **host:puerto del SQL Server on-prem**
> (`<HOST-SQL-ONPREM>`, `<PUERTO>`). Los nombres de recursos (function app,
> Key Vault, resource group) se mantienen: son identificadores operativos
> necesarios para trabajar y los mismos que usa `infra/`. No hay contraseñas
> en el documento: viven en Key Vault y la function key se obtiene con
> `az functionapp keys list`.

## Por qué está aquí

`sigrid-api` es el **único** punto de acceso a la base de datos de Sigrid, y
es a quien llama nuestro cliente HTTP en
`etl_sigrid/infrastructure/sigrid/`. Este documento explica sus endpoints,
límites y modos de fallo; es la referencia para entender qué puede y qué no
puede pedir la fase de ingesta.

Recuerda la regla dura de `CLAUDE.md`: desde este proyecto **solo lecturas**
contra Sigrid. Los endpoints de escritura que se documentan aquí no se usan
desde este ETL.

---

# sigrid-api — Documentación completa del microservicio

`sigrid-api` es un microservicio (Azure Function, Python 3.12, arquitectura
hexagonal) que expone, de forma **acotada y segura**, el SQL Server on-prem del
ERP **Sigrid** (sector construcción) al resto de microservicios y herramientas
de Construcciones Ruesma. Es el **único** punto de acceso a la base de datos de
Sigrid: nadie se conecta por SQL directo; todo pasa por esta API.

Ofrece tres familias de capacidades:

1. **Lectura SQL acotada** (`sql/read`) y descarga de documentos (`documents/read`).
2. **Escritura SQL genérica** por lotes y transaccional (`sql/write`).
3. **Escritura de dominio** de alto nivel sobre objetos de Sigrid, que
   encapsula reglas del ERP: alta de líneas de contrato
   (`sigrid/contrato-lineas`), alta de albarán de compra **desde contrato**
   (`sigrid/albaran`) y alta de albarán de compra **directo / sin contrato**
   (`sigrid/albaran-directo`). Las tres con dry-run por defecto, recálculo de
   stock (PMP) y/o totales, y transacción atómica.

---

## 1. Arquitectura

Arquitectura hexagonal (puertos y adaptadores), con dependencias apuntando
siempre hacia el dominio. El `function_app.py` es el único punto de entrada
HTTP y compone las dependencias una sola vez (`@lru_cache`).

### 1.1. Árbol del proyecto

```
sigrid-api/
├── function_app.py                 # rutas HTTP + inyeccion de dependencias
├── host.json
├── requirements.txt
├── local.settings.json(.sample)    # config local (no se sube)
├── config/
│   └── settings.py                 # Settings (pydantic-settings) + get_settings()
├── domain/                         # nucleo: modelos y puertos (sin dependencias de infra)
│   ├── models/
│   │   ├── sql_models.py           # SqlReadRequest/Response, SqlWriteRequest/Statement/Response, DocumentRead*
│   │   ├── document_models.py      # RawDocumentRecord
│   │   ├── sigrid_domain_models.py # ContractLineInput, AddContractLinesRequest/Response
│   │   ├── albaran_domain_models.py# ReceivedLine, AddPurchaseAlbaranRequest/Response, AlbaranLinePreview
│   │   └── albaran_directo_models.py # DirectLine, AddDirectAlbaranRequest
│   └── ports/
│       └── sql_repository.py       # SqlRepository (interfaz abstracta)
├── application/                    # casos de uso (orquestan dominio + puertos)
│   └── use_cases/
│       ├── execute_sql_query_use_case.py     # lectura
│       ├── execute_sql_command_use_case.py   # escritura por batch
│       ├── read_document_use_case.py         # documentos
│       ├── add_contract_lines_use_case.py    # dominio: lineas de contrato
│       ├── create_purchase_albaran_use_case.py  # dominio: albaran DESDE contrato
│       └── create_direct_albaran_use_case.py    # dominio: albaran DIRECTO (subclase del anterior)
├── infrastructure/                 # adaptadores concretos
│   ├── repositories/
│   │   └── sql_server_repository.py   # implementacion SqlRepository (pyodbc)
│   ├── security/
│   │   ├── identifier_guard.py        # valida identificadores (tabla/columna)
│   │   ├── sql_query_guard.py         # guard de LECTURA (solo SELECT)
│   │   └── sql_write_guard.py         # guard de ESCRITURA (lista blanca)
│   └── serialization/
│       └── json_encoder.py            # serializacion de valores SQL a JSON
├── interface_adapters/
│   └── http/
│       └── http_response_factory.py   # json_response, error_response, binary_file_response
├── infra/                          # IaC y scripts de despliegue (terraform, ps1, sql)
└── scripts/                        # utilidades (ejemplos de invocacion)
```

### 1.2. Flujo de una petición

```
HTTP → function_app (ruta) → valida body con modelo Pydantic
     → use case (aplica guard + lógica) → repositorio (pyodbc → SQL Server)
     → modelo de respuesta → http_response_factory → JSON/binario
```

`build_dependencies()` construye una sola vez (`@lru_cache`) `Settings`,
`SqlServerRepository` y los casos de uso, y los reparte a cada ruta. El caso de
uso de albarán directo se instancia en su propia ruta reutilizando el
repositorio y los settings ya construidos.

### 1.3. Principios

- Credenciales **separadas** de lectura (`ro_user`) y escritura (`user_rw`).
- Validación en dos planos: **Pydantic** (forma y caps) + **guard** (semántica/seguridad).
- Errores controlados → HTTP 400 con cuerpo JSON `{ok:false, error, details}`;
  inesperados → 500 con `details.exception`.
- La escritura está **desactivada por defecto** y se habilita por configuración.

---

## 2. Infraestructura Azure y conexión a Sigrid

| Recurso | Valor |
|---------|-------|
| Suscripción | `<ID-SUSCRIPCION>` |
| Resource Group | `rg-sigrid-dev-data-api` (spaincentral) |
| Function App | `func-sigridapi-dev-huyke` (Flex Consumption, Python 3.12) |
| URL base | `https://func-sigridapi-dev-huyke.azurewebsites.net` |
| Key Vault | `kv-sigridapi-dev-huyke` (secretos `sigrid-password` y `sigrid-write-password`) |
| SQL on-prem | `<HOST-SQL-ONPREM>:<PUERTO>` (vía VPN desde Azure) |
| Túnel local | `127.0.0.1:11433` (desarrollo) |
| Bases de datos | `ruesma` (escribible), `ruesma_rep` (réplica lectura), `master` |
| Usuarios SQL | `ro_user` (lectura), `user_rw` (escritura) |

Las contraseñas se referencian desde Key Vault en App Settings:
`@Microsoft.KeyVault(VaultName=kv-sigridapi-dev-huyke;SecretName=...)`.

Notas operativas: arranque en frío de Flex Consumption puede dar timeouts
aparentes en funciones ociosas; el balanceador de Azure impone **230 s** de
idle HTTP; TLS 1.2 forzado en las storage accounts.

---

## 3. Configuración (variables de entorno / App Settings)

`config/settings.py` (pydantic-settings, `extra=ignore`, `case_sensitive=false`).
Las listas aceptan JSON-array (`["a","b"]`) o CSV (`a,b`).

| Variable | Defecto | Uso |
|----------|---------|-----|
| `SQL_DRIVER` | — | Driver ODBC (p.ej. *ODBC Driver 18 for SQL Server*). |
| `SQL_SERVER_HOST` / `SQL_SERVER_PORT` | — | Host/puerto del SQL on-prem. |
| `SQL_SERVER_USERNAME` / `SQL_SERVER_PASSWORD` | — | Credenciales de **lectura** (`ro_user`). |
| `SQL_SERVER_WRITE_USERNAME` / `SQL_SERVER_WRITE_PASSWORD` | (vacío) | Credenciales de **escritura** (`user_rw`). Si faltan, la escritura queda desactivada. |
| `DEFAULT_QUERY_TIMEOUT_SECONDS` / `MAX_QUERY_TIMEOUT_SECONDS` | 30 / 120 | Timeouts de lectura (tope sujeto al límite de 230 s del LB). |
| `DEFAULT_MAX_ROWS` / `MAX_ALLOWED_ROWS` | 200 / 1000 | Filas por defecto / tope duro en lectura. |
| `MAX_INLINE_BINARY_BYTES` | 65536 | Tope de binario embebido en JSON. |
| `ALLOWED_DATABASES` / `ALLOWED_QUERY_PREFIXES` | (vacío) | Lista blanca de BD y prefijos de lectura. |
| `ALLOWED_WRITE_DATABASES` / `ALLOWED_WRITE_PREFIXES` | (vacío) | Lista blanca de BD y prefijos de escritura. Vacío ⇒ escritura off. |
| `DEFAULT_WRITE_TIMEOUT_SECONDS` / `MAX_WRITE_TIMEOUT_SECONDS` | 30 / 120 | Timeouts de escritura. |
| `DEFAULT_MAX_AFFECTED_ROWS` / `MAX_AFFECTED_ROWS` | 200 / 1000 | Tope de filas afectadas (acumulado en el batch). |
| `MAX_STATEMENTS_PER_BATCH` | 20 | Máximo de sentencias por petición `sql/write`. |
| `USE_FAST_EXECUTEMANY` | true | Activa `fast_executemany` para `parameter_sets`. |
| `REQUIRE_WHERE_ON_UPDATE_DELETE` | true | Obliga `WHERE` en UPDATE/DELETE. |
| `SIGRID_DOMAIN_WRITE_ENABLED` | false | Habilita el **commit** de los endpoints de dominio. |
| `APPLOCK_TIMEOUT_MS` | 10000 | Timeout del `sp_getapplock` al reservar `ide`. |
| `DOMAIN_WRITE_MAX_RETRIES` | 3 | Reintentos ante colisión de `ide` (clave duplicada). |
| `SIGRID_ALBARAN_EMPIDE` | 2425207 | Empleado (`empide`) por defecto en la cabecera de un albarán creado por la API (sobreescribible por petición). |

`Settings.write_enabled` es `true` solo si hay credenciales rw **y**
`ALLOWED_WRITE_PREFIXES` no está vacío.

---

## 4. Seguridad

- **Credenciales segregadas**: lectura y escritura usan usuarios distintos; el
  repositorio elige uno u otro según la operación.
- **`SqlQueryGuard`** (lectura): solo `SELECT` (según `ALLOWED_QUERY_PREFIXES`),
  base en lista blanca, una sola sentencia, sin DDL/EXEC.
- **`SqlWriteGuard`** (escritura): lista blanca estricta
  (`ALLOWED_WRITE_PREFIXES`); prohíbe DDL/administración (`DROP/ALTER/CREATE/
  GRANT/EXEC/MERGE/...`); una sentencia por elemento; **`WHERE` obligatorio** en
  UPDATE/DELETE; valida cada sentencia del batch y respeta
  `MAX_STATEMENTS_PER_BATCH`.
- **`IdentifierGuard`**: valida nombres de tabla/columna/esquema (anti-inyección)
  en las rutas que construyen SQL con identificadores (documentos y helpers de
  dominio).
- **Escritura de dominio**: doble llave — `SIGRID_DOMAIN_WRITE_ENABLED` + base
  permitida — y **dry-run por defecto**. La reserva de `ide` usa
  `sp_getapplock` + `MAX+1` + reintento.
- Toda escritura es **transaccional** (rollback ante error o si se supera el
  tope de filas).

---

## 5. Referencia de endpoints

Setup de consola (PowerShell):

```powershell
$base = "https://func-sigridapi-dev-huyke.azurewebsites.net"
$code = az functionapp keys list --name func-sigridapi-dev-huyke --resource-group rg-sigrid-dev-data-api --query "functionKeys.default" -o tsv
$headers = @{ "x-functions-key" = $code }
```

### 5.1. `POST /api/sql/read`

Lectura SQL parametrizada y acotada.

Petición: `{ database, sql, parameters[], timeout_seconds?, max_rows? }`
Respuesta: `{ ok, database, columns[], rows[][], row_count, truncated }`
(`truncated=true` si se alcanzó `max_rows`).

```powershell
$q = '{ "database":"ruesma","sql":"SELECT TOP 5 ide, cod, res FROM dbo.con WHERE tip = ?","parameters":[44] }'
Invoke-RestMethod -Uri "$base/api/sql/read" -Method Post -Headers $headers -ContentType "application/json" -Body $q | ConvertTo-Json -Depth 6
```

### 5.2. `POST /api/sql/write`

Escritura por **batch** transaccional. Dos formas:

- Atajo single-statement: `{ database, sql, parameters[] }`.
- Batch: `{ database, statements:[ { sql, parameters[] | parameter_sets[][] } ], max_affected_rows? }`.

`parameter_sets` ejecuta `executemany` (con `fast_executemany` si está activo).
Todo el batch va en **una transacción**; `max_affected_rows` es el tope
acumulado (si se supera ⇒ ROLLBACK). Respuesta:
`{ ok, database, statements, results:[{operation, affected_rows}], total_affected_rows, committed }`.

```powershell
# single
$w = '{ "database":"ruesma","sql":"UPDATE dbo.ctr SET tot = tot WHERE ide = ?","parameters":[1035535] }'
# batch (varias sentencias, atomico)
$wb = @'
{ "database":"ruesma","statements":[
  { "sql":"DELETE FROM dbo.ctrpro WHERE ide = ?","parameters":[258687] },
  { "sql":"UPDATE dbo.ctr SET tot = tot - 12.1 WHERE ide = ?","parameters":[1035535] }
] }
'@
Invoke-RestMethod -Uri "$base/api/sql/write" -Method Post -Headers $headers -ContentType "application/json" -Body $wb | ConvertTo-Json -Depth 6
```

### 5.3. `POST /api/documents/read`

Descarga el BLOB de una fila (documento adjunto). Petición:
`{ database, schema?, table, id_column, id_value, blob_column, filename_columns?, disposition? }`.
Devuelve el binario con `Content-Disposition` (los nombres de tabla/columna se
validan con `IdentifierGuard`).

### 5.4. `GET /api/diagnostics/tcp`

Test de conectividad TCP al SQL on-prem. Parámetros `host`, `port`, `timeout`.
Útil para diagnosticar VPN/túnel. `{ ok:true|false, host, port, error? }`.

```powershell
Invoke-RestMethod -Uri "$base/api/diagnostics/tcp?host=<HOST-SQL-ONPREM>&port=<PUERTO>" -Headers $headers
```

### 5.5. `POST /api/sigrid/contrato-lineas`

Añade líneas a un **contrato de compra** existente. Localiza el contrato por
(código de contrato + código de obra + CIF proveedor), clona una línea del
contrato como plantilla, calcula importes e **IVA**, y actualiza los totales de
la cabecera. **Dry-run por defecto.**

Petición:

```json
{
  "database": "ruesma",
  "cod_contrato": "CTSU16/0206",
  "cod_obra": "0404",
  "cif_proveedor": "A28685758",
  "template_line_ide": null,
  "commit": false,
  "lines": [ { "res": "DESCRIPCION", "can": 1, "pre": 10, "unimed": "UD", "paride": null, "proide": null, "tex": null } ]
}
```

Respuesta (dry-run): `ctride`/`obride` localizados, `reserved_ctrpro_ides`, la
fila `ctrpro` completa que insertaría y `header_totals_before`/`_after`.

Salvaguardas: `commit:true` exige `SIGRID_DOMAIN_WRITE_ENABLED=true` + base
permitida; reserva de `ide` con applock+MAX+1+reintento; **commit bloqueado si
el contrato tiene descuento/recargo global** (`impdes/imprec ≠ 0`); la línea se
crea sin descuento de línea (`tot = can×pre`).

```powershell
$body = @'
{ "database":"ruesma","cod_contrato":"CTSU16/0206","cod_obra":"0404","cif_proveedor":"A28685758",
  "lines":[ { "res":"PRUEBA","can":1,"pre":10,"unimed":"UD" } ] }
'@
Invoke-RestMethod -Uri "$base/api/sigrid/contrato-lineas" -Method Post -Headers $headers -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 8
```

### 5.6. `POST /api/sigrid/albaran`

Crea un **albarán de compra** (recepción) **a partir de un contrato**. Localiza
el contrato por la misma terna (código contrato + código obra + CIF proveedor),
**replica TODAS sus líneas** en `dcapro` (las recibidas con su cantidad, el
resto con `can=0`), genera la cabecera (`con` + `dca`), la trazabilidad
contrato→albarán (`ctrprodes`), el **ledger de stock** (`mov`) con recálculo de
PMP, actualiza `ctrpro.canser` de las líneas servidas y recalcula
`ctr.estser/estfac`. **Dry-run por defecto.**

Petición:

```json
{
  "database": "ruesma",
  "cod_contrato": "CTSU16/0206",
  "cod_obra": "0404",
  "cif_proveedor": "A28685758",
  "su_referencia": "ALB-PRUEBA-001",
  "fecha_albaran": null,
  "empide": null,
  "commit": false,
  "lineas_recibidas": [ { "ctrpro_ide": 258688, "cantidad": 6 }, { "ctrpro_ide": 258689, "cantidad": 4 } ]
}
```

Respuesta: `con_ide`, `cod` (serie automática `AC{año}/{n}`), `contrato`
(ides localizados), `cabecera` (dict `dca` completo, como válvula de seguridad
para detectar campos *stale* del clon), `lineas[]` (preview con stock/PMP
anterior y resultante por línea), `movimientos[]` (filas `mov` en crudo),
`estados_contrato` (`estser/estfac` antes/después y sumas), `totales` y
`warnings`.

Notas de negocio: `su_referencia` va al campo `entref` (Nº albarán del
proveedor); el documento numera con la serie `AC` automática (no se elige a
mano); las líneas no recibidas entran con `can=0` (igual que en Sigrid). El
PMP se recalcula en orden por (producto, almacén):
`pma = (stock·pma + can·pre) / (stock + can)` sin redondear.

```powershell
$body = @'
{ "database":"ruesma","cod_contrato":"CTSU16/0206","cod_obra":"0404","cif_proveedor":"A28685758",
  "su_referencia":"ALB-PRUEBA-001","commit":false,
  "lineas_recibidas":[ { "ctrpro_ide":258688,"cantidad":6 }, { "ctrpro_ide":258689,"cantidad":4 } ] }
'@
Invoke-RestMethod -Uri "$base/api/sigrid/albaran" -Method Post -Headers $headers -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 12
```

### 5.7. `POST /api/sigrid/albaran-directo`

Crea un albarán de compra **directo (sin contrato)**. El proveedor se resuelve
por **CIF** (de su último albarán, que aporta formas de pago/cuentas), la obra
por su **código**, y cada línea aporta producto + cantidad + precio; el
almacén/IVA/cuenta/centro de coste se heredan de la **última `dcapro` del
producto** (o se pasan en `almide`/`cenide`/`ivaide`). Inserta `con` + `dca` +
`dcapro` + `mov`. **No** crea `ctrprodes`, **no** toca `canser` ni los estados
de contrato; `dca.ctride = 0` y las `dcapro` van sin `docori*`. El efecto en
stock (PMP) es idéntico al del albarán desde contrato. **Dry-run por defecto.**

Petición:

```json
{
  "database": "ruesma",
  "cif_proveedor": "A28685758",
  "cod_obra": "0404",
  "almide": null,
  "cenide": null,
  "su_referencia": "ALB-DIRECTO-PRUEBA-001",
  "fecha_albaran": null,
  "empide": null,
  "commit": false,
  "lineas": [ { "proide": 498102, "can": 3, "pre": 40.0, "res": "DESCRIPCION", "unimed": null, "ivaide": null, "paride": null } ]
}
```

La respuesta reutiliza el mismo modelo que `sigrid/albaran` (con
`contrato.sin_contrato=true` y `estados_contrato` vacío). Requisito: el
proveedor debe tener al menos un albarán previo (para clonar la cabecera); si un
producto no tiene histórico de `dcapro`, hay que pasar `almide`/`ivaide`.

```powershell
$body = @'
{ "database":"ruesma","cif_proveedor":"A28685758","cod_obra":"0404","su_referencia":"ALB-DIRECTO-PRUEBA-001","commit":false,
  "lineas":[ { "proide":498102,"can":3,"pre":40.0,"res":"PRUEBA DIRECTO L1" } ] }
'@
Invoke-RestMethod -Uri "$base/api/sigrid/albaran-directo" -Method Post -Headers $headers -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 12
```

> **Dry-run vs commit (uso programático).** El dry-run (`commit:false`) es solo
> el valor por defecto, como red de seguridad: **no es obligatorio**. Desde el
> pipeline puedes llamar directamente con `commit:true` y se escribe en una sola
> transacción atómica. Lo único imprescindible para escribir es
> `SIGRID_DOMAIN_WRITE_ENABLED=true` (el dry-run no lo necesita).

---

## 6. Conocimiento del modelo de datos Sigrid

### 6.1. Conceptos y `ide`

- Casi todo en Sigrid es un **Concepto** (`con`) con extensiones 1:1 por tipo
  (`obr`, `ctr`, `dca`, `dcf`, `prv`, …) que comparten el mismo `ide`. El
  discriminador es **`con.tip`**; el nombre legible es `con.res`; las fechas son
  enteros `YYYYMMDD` (`0` = nulo).
- **`ide` no es IDENTITY ni hay SEQUENCE activa** (la tabla `sig_ides` está
  vacía; `SiUsarSEQ=false`). Asignación por `MAX(ide)+1` por tabla:
  - **Conceptos**: Sigrid usa `bas.conagrega(tip, cod, res, fec)` (crea `con` +
    extensión, `cod` desde una **serie** `sercon`).
  - **Líneas/detalle (1N)** (`ctrpro`, `dcapro`, `conext`, `aux*`): `MAX(ide)+1`
    + `INSERT`. La API lo hace con applock + reintento.

### 6.2. Tipos de concepto relevantes

| `con.tip` | Objeto |
|-----------|--------|
| 5 | Proveedor (`prv`) |
| 11 | Factura de venta (`dvf`) |
| 13 | Pedido de compra (`dcp`) |
| 14 | Albarán de compra (`dca`) |
| 15 | Factura de compra (`dcf`) |
| 21 | Centro de coste (`cen`) |
| 42 | Obra (`obr`) |
| 44 | **Contrato de compra** (`ctr`) |
| 49 | Parte de consumo (`hpc`) |
| 54 | Certificación (`cer`) |

### 6.3. Contrato de compra y líneas

- **`ctr`** (cabecera): `entcif` (CIF proveedor, sin prefijo país),
  `entide/entcod/entres`, `obride` (obra), y totales almacenados `impbru`
  (bruto), `impnet`, `impdes/imprec` (descuento/recargo global), `totbas`,
  `totiva`, `totdoc`, `tot`, `totpag`. **Sin triggers**: los totales no se
  recalculan solos.
- **`ctrpro`** (líneas): `docide`→`ctr`, `proide`, `can`, `pre`, `tar`, `dto`,
  `tot`, `ivaide`, `ivacuo`, `unimed`, `cenide`, `caaide`, `paride`, `pos`,
  `numlin`. `tot = round(can×pre, 2)`, `ivacuo = round(tot×tasa, 2)`.
- **Localizador**: `con.tip=44 AND con.cod=? AND obra.cod=? AND ctr.entcif=?`
  (join `con`→`ctr`→`con` por `obride`).

### 6.4. Albaranes, stock y encadenamiento

El albarán de compra (`dca`, `con.tip=14`) + líneas `dcapro` se enlaza al
contrato por `dca.ctride`. Una línea de albarán enlaza con su línea de contrato
origen por `dcapro.linoriide = ctrpro.ide` con `dcapro.docoritip = 44`
(tipos de origen: 13 pedido, 14 albarán, 15 factura, 44 contrato). En un albarán
directo (sin contrato) esos campos van a cero y `dca.ctride = 0`.

**Aprendizaje crítico — `cod`/`res`/`fec` viven en `con`, NO en la extensión.**
El **código** de documento (`cod`, serie `AC{año}/{n}`), la **descripción**
(`res`) y la **fecha** (`fec`) son columnas del **concepto `con`**; la extensión
`dca` **no** las tiene (sí tiene `fecdoc`, `hor`, `entref`, etc.). Insertarlas en
`dca` provoca `42S22 "El nombre de columna 'cod' no es válido"`. Regla general:
al construir una cabecera, `cod/res/fec/tip/est` → `con`; el resto → la
extensión, y todo *override* sobre el clon se aplica con `if col in fila` para no
añadir columnas inexistentes.

**Numeración (`cod`).** Serie automática `AC{YY}/{MAX(sufijo)+1}` sobre
`con WHERE tip=14 AND cod LIKE 'AC{YY}/%'`. No se elige a mano.

**Stock y PMP — viven solo en `mov`.** Cada línea genera una fila en el ledger
`mov` (no se tocan `pro`/`proalm`). Para una entrada de compra:
`tip=1, oritip=5 (proveedor=oriide), destip=2, deside=almide, doctip=14,
fecdoc=0, fechor=float("{fec}.{hor:06d}")`. El **PMP** se recalcula en orden por
(producto, almacén): `pma = (stock·pma + canent·pre) / (stock + canent)` **sin
redondear**; las líneas con `can=0` arrastran el balance sin avanzarlo.
Validado: partiendo de stock 78 / pma 69,5602564102564, una entrada de 1×100 da
stock 79 / pma 69,9455696202532.

**Estados de cabecera del contrato (`ctr.estser/estfac`, binarios 0/1).** Tras
servir, `estser = 1` si `Σcanser ≥ Σcan` (sobre todas las líneas), `estfac = 1`
si `Σcanfac ≥ Σcan`. Sigrid **no** los recalcula solo (sin triggers): el alta de
líneas los deja *stale*; el alta de albarán los recalcula y actualiza, y suma
`ctrpro.canser += recibido` por línea servida.

**`ctrprodes`** (trazabilidad contrato→albarán): `docproide` (línea de contrato),
`can`, `docdestip=14`, `docdescod` (cod del albarán), `docdeside` (ide del
albarán), `lindeside` (ide de la línea de albarán). Solo en el albarán **desde
contrato**.

`dcapro.pos` se asigna en múltiplos de 64 (orden de líneas).

---

## 7. Despliegue y operación

```powershell
cd C:\Users\pgris\PycharmProjects\sigrid-api
func azure functionapp publish func-sigridapi-dev-huyke
```

- **App Settings de escritura**: fijarlos vía **fichero JSON** (ASCII sin BOM)
  con `az ... --settings "@fichero"`; el inline rompe por comillas/`;` en
  PowerShell.
- **`az ... --query`** en Windows: evitar paréntesis JMESPath (rompen `az.cmd`).
- Tras `appsettings set`, el worker puede tardar en recoger el cambio: si un
  flag recién puesto "no aplica", esperar o `az functionapp stop`+`start`.
- **`Invoke-RestMethod` ante 4xx/5xx no muestra el cuerpo**; capturarlo:

  ```powershell
  try { Invoke-RestMethod ... -ErrorAction Stop }
  catch {
    $r = $_.Exception.Response
    $sr = New-Object System.IO.StreamReader($r.GetResponseStream()); $sr.BaseStream.Position=0; $sr.DiscardBufferedData()
    Write-Host ([int]$r.StatusCode); $sr.ReadToEnd()
  }
  ```

- Regla de mantenimiento: al tocar `settings.py`, `function_app.py` o el
  repositorio, **editar sobre el archivo vivo**, no regenerarlo de memoria
  (evita revertir features ya existentes).

---

## 8. Estado actual y próximos pasos

Hecho y validado:
- Lectura, descarga de documentos y diagnóstico.
- Escritura genérica por batch transaccional (`fast_executemany`).
- Alta de líneas de contrato (`sigrid/contrato-lineas`) con dry-run, applock,
  recálculo de totales y guarda de descuento global.
- **Alta de albarán de compra desde contrato** (`sigrid/albaran`): replica
  todas las líneas, genera `dca`/`dcapro`/`ctrprodes`/`mov` con recálculo de
  PMP, actualiza `canser` y `estser/estfac`.
- **Alta de albarán de compra directo / sin contrato** (`sigrid/albaran-directo`).

Todo lo anterior validado de punta a punta contra el contrato `CTSU16/0206`
(obra 0404, GARSAN, producto MA3413): albaranes `AC26/15951` (desde contrato) y
`AC26/15952` (directo) creados, verificados en la UI de Sigrid y con el stock/PMP
encadenado correcto.

Roadmap:
1. **Idempotencia** en altas de dominio (p.ej. `synckey` en cabeceras) para
   evitar duplicados ante reintentos del pipeline.
2. **Resolución de producto por código** (leer maestro `pro` para `cueide/ivaide/
   natide`) cuando un producto no tenga histórico de `dcapro`, y de partida
   (`paride`); resolución de obra→almacén/centro de coste sin pasar `almide`.
3. **Permiso `DELETE` para `user_rw`** y/o endpoint de **borrado con revert** de
   stock/canser/estados, para no limpiar a mano con `sql/write` (hoy se borra
   desde la UI de Sigrid, que revierte de forma nativa).
4. Conectar con el **pipeline de albaranes (sv1–sv7)**: tras valorar líneas
   contra contrato/partidas, llamar a `sigrid/albaran` (o `albaran-directo`) con
   `commit:true`.
5. Endurecer el localizador de contrato con `obra.tip=42` (opcional).
6. Tests automatizados de guards y casos de uso.
