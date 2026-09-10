<!-- progress/impl_F-073.md -->
# F-073 · Informe de implementación

Rama `feature/F-073-tablas-nuevas-y-enriquecimiento`. Rigor `estandar`.
Spec: `specs/F-073-tablas-nuevas-y-enriquecimiento/` (29 requisitos, 21 tareas).

## T1 · Los nombres de columna, MEDIDOS (2026-09-10, solo lectura)

Medidos con el cliente del ETL (`PostgresClient.filas_solo_lectura`, transacción
`READ ONLY`), no con el MCP: `raw` no está en los esquemas que el MCP lee.

### `raw.conest` (19 columnas)

| Papel | Columna | Tipo |
|---|---|---|
| tipo de documento | **`tip`** | integer |
| código del estado | **`est`** | integer |
| nombre del estado | **`res`** | character varying |
| código corto | `cod` | character varying (`EST`, `ECU`, `TER`…) |
| identificador | `ide` | integer |

`con.est` casa contra `conest.est` (no contra `conest.cod`, que es texto).
`tip = 42` da las **14** filas de estado de obra: `EN ESTUDIO` (1),
`EN CURSO` (15), `TERMINADA` (19), `CERRADA` (25), `PLANTILLA` (999)…

### `raw.auxefp` (15 columnas) — la contradicción, resuelta

`tables_sigrid.yaml` decía `est` y el informe de bloque decía `res`. **Gana
`res`**, medido sobre las 10 filas: `res` trae `CHEQUE`, `EFECTIVO`, `PAGARÉ`,
`TRANSFERENCIA`, `LETRA`, `CONFIRMING / PAGARÉ`…, mientras que **`est` está
vacío ('') en 5 filas y NULL en las otras 5**. `cla` (integer) es la clase de
medio. `tables_sigrid.yaml` está equivocado y el SQL de F-073 usa `res`.

### `raw.auxpag` (14 columnas)

`cod`, `res` (nombre), **`formul`** (text, el plazo — R22), `efeide` (→
`auxefp.ide`), `can`, `cat`, `ser`.

### `raw.obr` — los ocho campos que suenan a dirección

| Columna | Tipo | ¿Es la dirección de la obra? |
|---|---|---|
| `dir1` | varchar | **SÍ** (R8) |
| `dir2` | varchar | **SÍ** (R8) |
| `dircpo` | varchar | **SÍ**, código postal (R8) |
| `dir` | text | **SÍ**, dirección completa (R8) |
| `munide` | integer | eje de agrupación → `raw.auxmun` (R10) |
| `proide` | integer | eje de agrupación → `raw.auxpro` (R10) |
| `diride` | integer | **NO** — director de obra (R9) |
| `perdir` | text | **NO** — persona de contacto del director (R9) |
| `entdiride` | integer | **NO** — dirección del cliente (R9) |
| `dirtex` | text | **NO** — no se publica: no está en R8 |

### `raw.cen` (70 columnas) y `raw.con`

`raw.cen` **no tiene `cod`, `res` ni `emp`**: el código, el nombre y la empresa
del centro salen de su `raw.con` (mismo `ide`), que sí trae `emp`, `tip`, `cod`,
`res` y `est`. `raw.cen.obride` existe pero **está a 0 en las 804 filas** (R3).

