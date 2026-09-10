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

## T2 · Los recuentos y el % informado, MEDIDOS (2026-09-10)

| Medida | Valor | Requisito |
|---|---|---|
| `raw.cen` | **804** | R1 |
| puente resuelto a obra | **683** (121 sin obra) | R4, R6 |
| filas del puente / centros distintos | **804 / 804** → 1:1 | R5 |
| `cen.obride <> 0` | **0 de 804** | R3 |
| `raw.conest` | **193**, y `(tip, est)` único 193/193 | R19, R17 |
| `raw.auxpag` | **69** | R21 |
| `raw.auxefp` | **10** | R21 |
| `maestro.obras` hoy | **921** | R17, R18 |
| `maestro.obras` tras los 3 LEFT JOIN nuevos | **921** (no multiplica) | R17 |

Porcentaje informado sobre las **921** obras (R12):

| Columna | Informadas | % |
|---|---|---|
| `dir1` | 305 | **33,1 %** |
| `dir2` | 47 | **5,1 %** |
| `codigo_postal` (`dircpo`) | 303 | **32,9 %** |
| `direccion_completa` (`dir`) | 272 | **29,5 %** |
| `municipio` / `municipio_id` | 294 | **31,9 %** |
| `provincia` / `provincia_id` | 306 | **33,2 %** |
| `estado` (nombre) | 920 | **99,9 %** |

Los 294 `munide` y los 306 `proide` informados **resuelven todos** a nombre en
`auxmun` / `auxpro`: no hay identificador colgado. Una sola obra de 921 tiene un
`con.est` sin fila en `conest` para `tip = 42`: su `estado` sale NULL.

Marcas (R13–R15), sobre las mismas 921: **728 con presupuesto**, **368 con plan
mensual**, **349 con filas en `mart.fact_seguimiento_mensual`**. La diferencia
plan/hecho son **19 obras y ninguna al revés** — es la contrapartida declarada
de leer de `stg` (DA-1) y va en la ficha (R15).
