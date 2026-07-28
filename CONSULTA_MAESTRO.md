# Consulta del schema `maestro` — Datamart Sigrid (Ruesma)

Documentación para que **otro servicio** consulte obras y proveedores del
datamart. El schema `maestro` expone catálogos en **PostgreSQL** (BD
`sigrid_dm`), pensados para consumo externo por SQL directo. Son **vistas**:
los datos se leen en vivo de `raw.*`, así que siempre están actualizados a la
última ingesta (no hay que refrescar nada por consulta).

Dos casos de uso cubiertos:

1. Obtener los datos de **una obra a partir de su código**.
2. Obtener la **lista de proveedores de una obra a partir del código de obra**.

---

## 1. Conexión

| Parámetro | Valor |
|---|---|
| Motor | PostgreSQL 15+ |
| Base de datos | `sigrid_dm` |
| Schema | `maestro` |
| Acceso recomendado | usuario **solo lectura** con `USAGE` sobre `maestro` y `SELECT` sobre sus vistas |

```sql
-- Permisos mínimos sugeridos para el servicio consumidor
GRANT USAGE ON SCHEMA maestro TO <usuario_servicio>;
GRANT SELECT ON ALL TABLES IN SCHEMA maestro TO <usuario_servicio>;
ALTER DEFAULT PRIVILEGES IN SCHEMA maestro
    GRANT SELECT ON TABLES TO <usuario_servicio>;
```

Las vistas disponibles son `maestro.obras`, `maestro.proveedores` y
`maestro.proveedores_obra`.

---

## 2. Caso de uso 1 — Obra por código

> ⚠️ **`codigo_obra` no es una clave única.** De 908 obras hay 838 códigos
> distintos: los códigos reales de proyecto (p.ej. `0676-B`) son únicos, pero
> unos pocos códigos genéricos/legacy se repiten (`0001`, `0002`, `CP`, `GG`…).
> La clave única real es **`obra_id`**. Diseña la consulta para poder devolver
> **0, 1 o N filas**.

### Consulta (parametrizada, estilo psycopg 3)

```sql
SELECT
    obra_id,
    codigo_obra,
    nombre_obra,
    nombre_cliente,
    codigo_cliente,
    estado_id,
    fecha_alta,
    fecha_baja,
    es_activa
FROM   maestro.obras
WHERE  codigo_obra = %(codigo)s
ORDER  BY fecha_alta DESC;
```

Parámetros: `codigo` → código de obra exacto (texto, p.ej. `'0676-B'`).

### Si necesitas exactamente una obra

Para códigos que pudieran repetirse, desambigua con un criterio de negocio.
Ejemplos:

```sql
-- a) Solo obras activas (sin fecha de baja)
SELECT * FROM maestro.obras
WHERE codigo_obra = %(codigo)s AND es_activa
ORDER BY fecha_alta DESC;

-- b) La más reciente con ese código
SELECT * FROM maestro.obras
WHERE codigo_obra = %(codigo)s
ORDER BY fecha_alta DESC
LIMIT 1;

-- c) Resolución directa por id (recomendado si ya conoces el obra_id)
SELECT * FROM maestro.obras WHERE obra_id = %(obra_id)s;
```

### Ejemplo de respuesta

| obra_id | codigo_obra | nombre_obra | nombre_cliente | estado_id | es_activa |
|---|---|---|---|---|---|
| 2442725 | 0676-B | RESIDENCIA ESTUDIANTES GREEN CAMPUS-FASE II | UNEXUM REAL ESTATE, S.L. | 15 | true |

---

## 3. Caso de uso 2 — Proveedores de una obra por código

Devuelve los proveedores con los que la obra tiene **contratos de compra**
(fuente: `ctr` de Sigrid). Una fila por proveedor.

### Consulta — lista simple (nombre + CIF)

```sql
SELECT DISTINCT
    nombre_proveedor,
    cif
FROM   maestro.proveedores_obra
WHERE  codigo_obra = %(codigo)s
ORDER  BY nombre_proveedor;
```

### Consulta — con importe y dirección

```sql
SELECT
    proveedor_id,
    codigo_proveedor,
    nombre_proveedor,
    cif,
    razon_social,
    direccion_completa,
    codigo_postal,
    municipio,
    provincia,
    telefono,
    n_contratos,
    importe_contratado
FROM   maestro.proveedores_obra
WHERE  codigo_obra = %(codigo)s
  AND  es_proveedor          -- excluye entidades que no son ficha de proveedor
ORDER  BY importe_contratado DESC;
```

Parámetros: `codigo` → código de obra exacto.

> Si el código de obra estuviera repetido (ver aviso del caso 1), esta consulta
> agrega los proveedores de **todas** las obras con ese código. Para acotar a
> una obra concreta, filtra además por `obra_id`:
> `WHERE obra_id = %(obra_id)s`.

### Ejemplo de respuesta

| nombre_proveedor | cif |
|---|---|
| A.G. PREMOLDEADOS, S.L. | B04366399 |
| AIRMAX RENTAL GROUP, S.A.U. | A88360953 |
| ALGECO CONSTRUCCIONES MODULARES, S.L.U. | B28871192 |
| … | … |

---

## 4. Referencia de columnas

### `maestro.obras`

| Columna | Tipo | Descripción |
|---|---|---|
| `obra_id` | int | **Clave única** de la obra (ide de Sigrid). |
| `codigo_obra` | text | Código de obra (no garantizado único). |
| `nombre_obra` | text | Nombre/descripción de la obra. |
| `estado_id` | int | Código interno de estado (p.ej. `15` = en curso). Sin texto. |
| `fecha_alta` | date | Fecha de alta. |
| `fecha_baja` | date | Fecha de baja (NULL si activa). |
| `es_activa` | bool | `true` si no tiene fecha de baja. |
| `cliente_id` | int | ide del cliente (NULL si no tiene). |
| `codigo_cliente` | text | Código del cliente. |
| `nombre_cliente` | text | Nombre del cliente (NULL en ~43% de obras). |

### `maestro.proveedores_obra`

| Columna | Tipo | Descripción |
|---|---|---|
| `obra_id` | int | ide de la obra. |
| `codigo_obra` | text | Código de la obra. |
| `nombre_obra` | text | Nombre de la obra. |
| `proveedor_id` | int | ide del proveedor. |
| `codigo_proveedor` | text | Código del proveedor. |
| `nombre_proveedor` | text | Nombre del proveedor. |
| `cif` | text | CIF/NIF (NULL si no consta). |
| `razon_social` | text | Razón social. |
| `es_proveedor` | bool | `false` si el contrato apunta a una entidad que no es ficha de proveedor. |
| `dir1`, `dir2` | text | Líneas de dirección (NULL si no consta). |
| `codigo_postal` | text | Código postal. |
| `municipio` | text | Municipio (texto). |
| `provincia` | text | Provincia (texto). |
| `direccion_completa` | text | Dirección en una línea. |
| `telefono` | text | Teléfono. |
| `n_contratos` | int | Nº de contratos de compra de ese proveedor en la obra. |
| `importe_contratado` | numeric(18,2) | Suma de los importes de esos contratos. |

### `maestro.proveedores` (catálogo global, sin filtro de obra)

Misma información de proveedor (codigo, nombre, cif, razon_social, dirección)
pero para **todos** los proveedores, sin relación con obra. Útil para búsquedas
o validaciones por CIF:

```sql
SELECT codigo, nombre, cif FROM maestro.proveedores WHERE cif = %(cif)s;
```

---

## 5. Notas y limitaciones

- **Unicidad de código de obra**: usar `obra_id` como clave cuando se requiera
  unicidad. `codigo_obra` puede repetirse en códigos genéricos/legacy.
- **Dirección de obra**: no se expone — Sigrid no almacena dirección de
  emplazamiento de obra. `maestro.obras` no tiene campos de dirección.
- **Dirección de proveedor**: presente solo en los proveedores que la tengan
  cargada en Sigrid (una minoría); el resto sale NULL. Nombre y CIF sí salen
  casi siempre.
- **`estado_id`**: es un código interno, sin descripción de texto. Si se
  necesita el literal, hay que mapearlo aguas arriba.
- **Frescura**: las vistas leen en vivo de `raw.*`. Reflejan la última ingesta
  del datamart; no hay caché ni necesidad de refresco por parte del consumidor.
- **Fuente del vínculo obra↔proveedor**: contratos de compra (`ctr`). Un
  proveedor que no tenga contrato en la obra no aparecerá, aunque haya
  trabajado de otra forma no registrada como contrato.

---

## 6. (Opcional) Exposición como endpoint HTTP

Si el servicio consumidor no puede consultar PostgreSQL directamente, estas dos
consultas se pueden envolver en endpoints REST (FastAPI ya está en el stack):

```
GET /obras/{codigo}              → datos de la obra (lista, por no-unicidad)
GET /obras/{codigo}/proveedores  → proveedores de la obra (nombre, cif, importe)
```

Cada endpoint ejecuta su consulta parametrizada contra `maestro.*` y devuelve
JSON. Si quieres, se especifica el contrato de request/response y se implementa.
