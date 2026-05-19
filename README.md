# Datamart Seguimiento Anual — Sigrid → Postgres → Power BI

> Microservicio Python que ingiere datos de **Sigrid** (ERP de construcción),
> los reestructura en un **data mart Postgres** y los expone a **Power BI**
> para el cuadro de seguimiento mensual de obras de Construcciones Ruesma.

---

## Tabla de contenidos

1. [Qué hace este proyecto](#1-qué-hace-este-proyecto)
2. [Conceptos clave del negocio](#2-conceptos-clave-del-negocio)
3. [Arquitectura técnica](#3-arquitectura-técnica)
4. [Modelo de datos en Sigrid](#4-modelo-de-datos-en-sigrid)
5. [Capas del data mart](#5-capas-del-data-mart)
6. [Reglas de negocio implementadas](#6-reglas-de-negocio-implementadas)
7. [Instalación y arranque](#7-instalación-y-arranque)
8. [Comandos del CLI](#8-comandos-del-cli)
9. [Validación contra Sigrid](#9-validación-contra-sigrid)
10. [Conexión a Power BI](#10-conexión-a-power-bi)
11. [Despliegue en Azure](#11-despliegue-en-azure)
12. [Mantenimiento y resolución de problemas](#12-mantenimiento-y-resolución-de-problemas)
13. [Glosario](#13-glosario)

---

## 1. Qué hace este proyecto

Construcciones Ruesma usa **Sigrid** como ERP para gestionar el seguimiento
económico de sus obras. Cada Jefe de Obra (JO) trabaja en Sigrid cargando:

- **Master coste** (planificación inicial del coste de obra)
- **Master venta** (planificación inicial de la producción/venta)
- **Coste real** que se va incurriendo cada mes
- **Venta real** (producción) que se va ejecutando cada mes

Sigrid no ofrece un dashboard de seguimiento agregado fácil de consultar para
dirección. Este proyecto:

1. **Extrae** los datos de Sigrid vía su API (Function App de Azure).
2. **Transforma** la estructura propia de Sigrid (que mezcla planificación,
   versiones de master, fases mensuales, cierres, revisiones, etc.) en una
   estructura analítica clara.
3. **Carga** los datos transformados en una base de datos Postgres con varias
   capas (`raw`, `aux`, `stg`, `mart`).
4. **Expone** una tabla fact lista para Power BI con todos los importes mensuales
   por obra, partida y escenario (Coste Real, Coste Planificado, Venta Real,
   Venta Planificada).

El resultado final es un cuadro de mando que permite a dirección:

- Ver el **estado mensual** de cada obra (lo planificado vs lo real).
- Comparar **versiones del master** (Planif Inicial vs ABC vs Cuatrimestral).
- Analizar **desviaciones de coste y venta** mes a mes.
- Hacer **drill-down** desde el total de obra hasta partida individual.
- Ver agregados por **capítulos contables** (CD/CI/CP).

---

## 2. Conceptos clave del negocio

Esta sección es **esencial** para entender el proyecto. Sigrid usa terminología
muy específica del sector construcción que conviene tener clara.

### 2.1 Obra, capítulo y partida

Una **obra** es un proyecto de construcción concreto (ej: "0707 - 88 VIVIENDAS
EL TOMILLAR EL ESCORIAL"). Cada obra se descompone en un árbol jerárquico:

```
Obra "0707"
├── CD COSTES DIRECTOS                    ← capítulo raíz
│   ├── 01 MOVIMIENTO DE TIERRAS          ← capítulo
│   │   ├── 01.01 DESBROCE                ← partida (hoja)
│   │   ├── 01.02 EXCAVACIÓN VACIADOS     ← partida (hoja)
│   │   └── ...
│   ├── 02 CIMENTACIONES Y CONTENCIONES
│   │   ├── 02.01 CIMENTACIONES
│   │   │   ├── 02.01.01 HORMIGÓN LIMPIEZA
│   │   │   └── ...
│   │   └── 02.02 CONTENCIONES
│   │       └── 02.02.01 MURO HORMIGÓN
│   └── ...
├── CI COSTES INDIRECTOS                  ← capítulo raíz
│   ├── CI.1 PERSONAL
│   │   ├── CI.1.2 JEFE DE OBRA
│   │   └── CI.1.3 ENCARGADO
│   └── ...
├── CP COSTES PROPORCIONALES              ← capítulo raíz
│   ├── CP.8 COSTES ESTRUCTURA EMPRESA
│   └── CP.9 LEVANTAMIENTO
└── 34 ORDENES DE CAMBIO                  ← capítulo raíz "OTRO"
```

Las **partidas hoja** son lo que se valora económicamente (cantidad, precio,
importe). Los **capítulos** son nodos intermedios para organización.

### 2.2 Las tres categorías contables

En construcción se clasifican los costes en tres categorías:

- **CD (Costes Directos)**: costes que se imputan directamente a la obra
  (excavación, hormigón, ladrillos, mano de obra de albañiles...). Se factura
  al cliente como partida.
- **CI (Costes Indirectos)**: costes necesarios para la obra pero no
  directamente facturables como partida (jefatura de obra, encargado, técnicos
  de prevención, vehículos, oficina). El cliente paga estos costes a través
  del margen general.
- **CP (Costes Proporcionales)**: costes generales de estructura de empresa
  asignados proporcionalmente a la obra (estructura de empresa, costes
  generales de la empresa repartidos por proyectos).

**Solo CD tiene contrapartida en venta** (la venta = producción que se factura
al cliente). CI y CP solo tienen coste; su recuperación viene del margen
aplicado a las partidas CD.

### 2.3 Ámbitos en Sigrid

Sigrid usa el concepto de "ámbito" para diferenciar tipos de datos. Los que
nos importan para el seguimiento mensual son cuatro:

| ámbito_id | nombre Sigrid | qué contiene |
|---|---|---|
| 3 | COSTE | Coste real ejecutado mensualmente |
| 7 | VENTA (PROD) | Producción real ejecutada mensualmente |
| 8 | MASTER COSTE | Planificación del coste (con múltiples versiones) |
| 11 | MASTER VENTA | Planificación de la venta (con múltiples versiones) |

Hay otros ámbitos en Sigrid (CERTIFICACIÓN, COSTE PENDIENTE...) que **no** se
usan en este seguimiento.

### 2.4 Versiones del master y "tex"

El JO no planifica una obra una sola vez: la **replanifica varias veces** a lo
largo del proyecto. Cada replanificación genera una nueva "versión" del master
(coste y venta). En Sigrid esto se materializa como múltiples filas en
`obrfasamb` con valores distintos de `fas` (fase) para el mismo ámbito.

El **texto libre** que el JO escribe al crear cada versión queda en
`obrfasamb.tex`. Patrones reales observados en Ruesma:

| Texto `tex` | Tipo asignado | Significado |
|---|---|---|
| `PLANIFICACION VALORADA INICIAL` | **Planif Inicial** | Primera planificación oficial al arrancar la obra |
| `PLANIFICACION VALORADA OCT-25` | **Cuatrimestral** | Cierre cuatrimestral de octubre |
| `PLANIFICACION CUATRIMESTRAL FEB-26` | **Cuatrimestral** | Cierre cuatrimestral de febrero (formato explícito) |
| `CIERRE DICIEMBRE-25/ ABC` | **ABC** | Cierre tipo ABC (revisión profunda con clasificación) |
| `CIERRE ENERO-26` | **Cierre mensual** | Revisión mensual menor |
| `CIERRE INICIAL_ESTUDIO` | (descartado) | Versión v0 sin `plafec`, no es planificación real |

**Regla crítica**: solo las versiones de tipo **Planif Inicial**, **ABC** y
**Cuatrimestral** son consideradas "master vigente". Los **Cierre mensual** son
revisiones puntuales del JO que no reemplazan al plan oficial.

### 2.5 Versión vigente por mes

Para cada mes de una obra, hay UNA versión del master que rige (la "vigente").
Se calcula así:

> La versión vigente para el mes M es la versión del master de tipo
> Planif Inicial / ABC / Cuatrimestral con `fec_creacion <= último día de M`
> más reciente.

Ejemplo real (obra 2563363):

| Mes | Versión vigente | Tipo | Por qué |
|---|---|---|---|
| Sep 2025 | v2 | Planif Inicial | única disponible en ese momento |
| Oct-Dic 2025 | v3 | Cuatrimestral | v3 se creó el 29/10/2025 |
| Ene 2026 | v4 | ABC | v4 se creó el 19/01/2026 |
| Feb 2026 | v4 | ABC | v5 fue Cierre mensual, no master vigente |
| Mar 2026+ | v6 | Cuatrimestral | v6 se creó el 06/03/2026 |
| Abr 2026+ | v6 | Cuatrimestral | v7 y v8 son Cierres mensuales, se ignoran |

### 2.6 La columna `planif` y la explosión mensual

En cada fila del master (`obrparpre` ámbito 8 o 11), Sigrid guarda una columna
**`planif`** que es un string como:

```
0|0.05|0.15|0.35|0.6|0.85|1|1|1|1...
```

Cada valor separado por `|` representa el **porcentaje acumulado** de avance
en cada mes desde la fecha ancla (`plafec` de `obrfasamb`).

Para reconstruir la distribución mensual:

```
posición 1: 0          (mes 1 = septiembre 2025: nada)
posición 2: 0,05       (mes 2 = octubre: 5% acumulado)
posición 3: 0,15       (mes 3 = noviembre: 15% acumulado)
posición 4: 0,35       (mes 4 = diciembre: 35% acumulado)
...
```

El **importe del mes** = `cantidad × precio × (pct_acumulado − pct_acumulado_mes_anterior)`.
El **importe a origen** = `cantidad × precio × pct_acumulado`.

### 2.7 Reales sin planif

Para los ámbitos reales (3 y 7), la columna `planif` está vacía. Sigrid usa
otra mecánica: cada **fase mensual** (`fas`) tiene su propia fila con la
cantidad y precio acumulados a esa fecha. El cálculo es entonces:

```
importe_origen (en fase N) = can × pre   ← acumulado en esa fase
importe_mes    (en fase N) = (can_N × pre) − (can_N-1 × pre)
                           = LAG sobre fase anterior
```

### 2.8 El detalle del precio (`pre`)

Sigrid almacena `pre` con **4 decimales** internamente (ej: `18.8085`), pero
**usa el precio redondeado a 2 decimales** (`18,81`) para todos los cálculos
visibles en la UI de Seguimiento.

Ejemplo real obra 0707 partida 01.02 enero 2026 venta:

| Cálculo | Resultado |
|---|---|
| `can × pre_crudo` = `18.378,23 × 18,8085` | `345.666,94` (cálculo crudo) |
| `can × ROUND(pre, 2)` = `18.378,23 × 18,81` | `345.694,51` (lo que muestra Sigrid) |

Nuestro mart guarda **ambas versiones** en columnas paralelas:

- `importe_mes`, `importe_origen`: usan `ROUND(pre, 2)` → cuadran con Sigrid
- `importe_mes_raw`, `importe_origen_raw`: usan `pre` crudo (referencia)

Las versiones "oficiales" (sin sufijo) son las que consume Power BI.

---

## 3. Arquitectura técnica

### 3.1 Diagrama general

```
┌────────────────────┐
│   Sigrid (cliente) │ Base de datos Sigrid en local de Ruesma
│   SQL Server       │
└──────────┬─────────┘
           │ SQL queries
           ▼
┌────────────────────┐
│ Sigrid API         │ Function App en Azure que expone Sigrid vía HTTP
│ (Function App)     │ Endpoint /api/sql/read con paginación
└──────────┬─────────┘
           │ HTTPS
           ▼
┌────────────────────┐
│  etl_sigrid_       │ Este proyecto (Python 3.12)
│   seguimiento      │   - Ingest: descarga datos vía HTTP
│  (microservicio)   │   - Stage: transforma con SQL
│                    │   - Mart: tabla fact lista para BI
└──────────┬─────────┘
           │ Postgres protocol (psycopg)
           ▼
┌────────────────────┐
│   Postgres         │ 4 schemas: raw, aux, stg, mart
│  (local hoy,       │
│   Azure mañana)    │
└──────────┬─────────┘
           │ Postgres connector
           ▼
┌────────────────────┐
│   Power BI         │ Conector Postgres nativo
│                    │ Modelo + DAX + visualizaciones
└────────────────────┘
```

### 3.2 Stack tecnológico

| Componente | Tecnología | Versión |
|---|---|---|
| Lenguaje | Python | 3.12 |
| Driver Postgres | psycopg | 3.x |
| Servidor BD | PostgreSQL | 15+ |
| HTTP client | httpx | 0.x |
| Configuración | pydantic-settings | 2.x |
| CLI | click | 8.x |
| Logging | structlog | 24.x |
| Sigrid API | Azure Function App | huyke-dev / huyke-prod |
| BI | Power BI Desktop / Service | 2024+ |

### 3.3 Patrón de arquitectura

Se usa **arquitectura hexagonal (puertos y adaptadores)**:

```
etl_sigrid/
├── domain/                          ← entidades de dominio (sin dependencias)
├── application/                     ← casos de uso
│   ├── steps/                       ← pasos del pipeline (Step pattern)
│   │   ├── ingest_raw_step.py
│   │   ├── build_stg_step.py
│   │   └── build_mart_step.py
│   └── pipelines/                   ← orquestación
├── infrastructure/                  ← adaptadores
│   ├── postgres/                    ← driver Postgres + SQL files
│   │   ├── postgres_client.py
│   │   └── sql/
│   │       ├── stg/                 ← SQL de capa staging
│   │       ├── mart/                ← SQL de capa mart
│   │       └── aux/                 ← SQL de catálogos
│   └── sigrid_api/                  ← cliente HTTP de Sigrid
└── interface_adapters/
    └── controllers/                 ← entrada CLI
```

El patrón **Pipeline** se usa para encadenar pasos: `ingest → stage → build_mart`.
Cada paso es independiente y puede ejecutarse aislado.

### 3.4 Estructura de carpetas

```
datamart-seg-anual/
├── main.py                          ← entrypoint CLI (click)
├── config/
│   ├── settings.py                  ← Pydantic settings (lee .env)
│   ├── tables_sigrid.yaml           ← tablas a ingerir y sus columnas
│   └── business_rules.yaml          ← constantes de negocio
├── .env                             ← credenciales (NO commitear)
├── etl_sigrid/
│   ├── domain/
│   ├── application/
│   │   ├── steps/
│   │   └── pipelines/
│   ├── infrastructure/
│   │   ├── postgres/
│   │   │   ├── postgres_client.py
│   │   │   └── sql/
│   │   │       ├── stg/01_ddl.sql
│   │   │       ├── stg/02_ambitos.sql
│   │   │       ├── stg/03_obras.sql
│   │   │       ├── stg/04_partidas.sql      ← reconstrucción árbol
│   │   │       ├── stg/05_fases.sql
│   │   │       ├── stg/06_presupuesto.sql
│   │   │       ├── stg/07_version_master_vigente.sql
│   │   │       ├── stg/08_plan_mensual.sql  ← núcleo: explosión y LAG
│   │   │       ├── mart/01_ddl.sql
│   │   │       ├── mart/02_build_fact.sql   ← fact con 4 escenarios
│   │   │       ├── mart/03_agg_categoria.sql ← agregado CD/CI/CP
│   │   │       ├── mart/04_view_periodificado.sql
│   │   │       └── aux/01_periodificacion.sql
│   │   └── sigrid_api/
│   └── interface_adapters/
└── tests/
```

---

## 4. Modelo de datos en Sigrid

Las tablas más relevantes de Sigrid (de las 200+ que tiene) son:

### 4.1 `obr` y `con` — obras

- `con` (concepto/entidad base): tiene `cod` y `res` de la obra.
- `obr` (obra): hereda de `con` (`obr.ide = con.ide`). Tiene metadatos
  específicos de obra.

### 4.2 `obrparpar` — partidas y capítulos

Una fila por nodo del árbol (capítulo o partida). Campos clave:

| Campo | Tipo | Significado |
|---|---|---|
| `ide` | int | Identificador único |
| `obride` | int | Obra a la que pertenece |
| `padide` | int | ID del **padre** en el árbol (0 = raíz) |
| `cod` | str | Código (`01.02`, `CI.1.2`, etc) |
| `res` | str | Descripción corta |
| `tipdes` | int | 1 = partida desactivada, 0 = activa |
| `unimed` | str | Unidad de medida (m3, m2, ud, mes...) |
| `tcaide` | int | FK a `auxobrtca` (tipo de capítulo) |

### 4.3 `obrparpre` — presupuesto y mediciones

El corazón. Una fila por **(obra, partida, ámbito, fase)**. Campos clave:

| Campo | Tipo | Significado |
|---|---|---|
| `ide` | int | Identificador único |
| `obride` | int | Obra |
| `paride` | int | Partida |
| `amb` | int | Ámbito (3/7/8/11) |
| `fas` | int | Fase. Significa cosas distintas según el ámbito: |
| | | • amb=3,7 (reales): número de mes-fase (1=primer cierre, 2=segundo...) |
| | | • amb=8,11 (master): número de versión del master |
| `can` | decimal | Cantidad (medición a origen para reales / planificada para master) |
| `pre` | decimal | Precio unitario |
| `planif` | text | String con porcentajes acumulados separados por `|` (solo master) |
| `totinc` | decimal | Total incurrido (a origen, calculado por Sigrid) |

### 4.4 `obrfas` — fases mensuales

Define los **meses de obra**: una fila por (obra, número_de_fase) con `ano`, `mes`,
`fecini`, `fecfin`, `res` (ej "Octubre 2025").

### 4.5 `obrfasamb` — versiones del master

Una fila por (obra, ámbito, versión). El campo clave aquí es:

| Campo | Significado |
|---|---|
| `fas` | número de versión |
| `plafec` | fecha ancla de la planificación (mes 1) |
| `fec` | fecha en que se creó la versión |
| `res` | texto automático "Versión N (DD/MM/YYYY)" |
| `tex` | **texto libre escrito por el JO** ← clasificación |

### 4.6 Tablas auxiliares

| Tabla | Propósito |
|---|---|
| `auxobramb` | Catálogo de ámbitos (qué id corresponde a COSTE, VENTA, MASTER...) |
| `auxobrtca` | Catálogo de tipos de capítulo (en Ruesma solo tiene 3 entradas: Instalaciones, Demoliciones, Carpintería — no usado para categorización) |
| `conext` | Campos extendidos por concepto. `cod='15'` indica la versión vigente actual del master |

---

## 5. Capas del data mart

El data mart Postgres tiene **4 schemas**, cada uno con un propósito claro.

### 5.1 Schema `raw`

**Datos brutos descargados desde Sigrid sin transformación**.

- Cada tabla de `raw.*` es una réplica de la tabla equivalente en Sigrid.
- Se mantiene incremental con `_source_tiemod` (timestamp de modificación
  en Sigrid).
- Una columna `_ingested_at` registra cuándo se descargó cada fila.
- **NO se debe consultar directamente** desde Power BI. Solo es origen para
  transformaciones.

Tablas que se ingieren (declaradas en `config/tables_sigrid.yaml`):

```
raw.con               raw.obr              raw.obrparpar
raw.obrparpre         raw.obrfas           raw.obrfasamb
raw.conext            raw.auxobramb        raw.auxobrtca
```

### 5.2 Schema `aux`

**Tablas auxiliares con reglas o configuración mantenidas a mano**.

Hoy solo contiene:

- `aux.periodificacion_partida`: reglas para periodificar partidas
  (montaje de grúa, instalación de obra...). **Hoy vacía**, infraestructura
  preparada para activarse cuando Negocio defina reglas.

En el futuro puede contener:
- `aux.tipo_partida`: subcategorías finas (CI_jefatura, CI_INFRAESTRUCTURA, etc).
- `aux.excluir_obras`: lista de obras a excluir del seguimiento.
- `aux.calendario`: ajustes de calendario por obra.

### 5.3 Schema `stg` (staging)

**Datos transformados en estructura analítica pero todavía cercanos al modelo
original**. Las tablas:

| Tabla | Granularidad | Propósito |
|---|---|---|
| `stg.obras` | 1 fila por obra | Lookup de obras con código y nombre |
| `stg.partidas` | 1 fila por partida | **Árbol reconstruido** con categoría CD/CI/CP |
| `stg.fases` | 1 fila por (obra, mes-fase) | Calendario de obra (qué mes es cada fase) |
| `stg.presupuesto` | 1 fila por `obrparpre` | Limpieza básica de `obrparpre` |
| `stg.version_master_vigente` | 1 fila por obra | Versión vigente actual desde `conext` |
| `stg.plan_mensual` | 1 fila por (obra, partida, ámbito, mes, versión) | **Distribución mensual** ya explotada |
| `stg.ambitos` (vista) | 1 fila por ámbito | Catálogo de ámbitos con tipos lógicos |

#### 5.3.1 `stg.partidas` con árbol

Esta tabla es el corazón de la clasificación. Reconstruye el árbol del
presupuesto siguiendo `padide` con un CTE recursivo, y propaga el **capítulo
raíz** a cada partida hoja.

Columnas clave:
- `capitulo_raiz_id`, `capitulo_raiz_cod`: ID y código del capítulo raíz
- `categoria`: CD / CI / CP / OTRO (derivado del código del raíz)
- `ruta_capitulos`: ej `"CD > 01 > 01.02"` para trazabilidad
- `nivel`: profundidad (0 = raíz, 1, 2, 3...)

La asignación de categoría usa heurística sobre el código del raíz porque
`auxobrtca` en Ruesma no clasifica por contabilidad sino por tipo de trabajo.

#### 5.3.2 `stg.plan_mensual`

La tabla más compleja del proyecto. Combina dos lógicas distintas en una sola
tabla con el mismo schema:

**Para master (ámbitos 8 y 11)**:
- Una fila por (obra × partida × ámbito × versión × mes-de-la-planificación).
- `version` guarda el número de versión del master.
- `pct_acumulado` y `pct_mes` vienen de explotar la columna `planif`.
- `version_fec_creacion` = fecha en que el JO creó esa versión.
- `version_tex` = texto libre del JO (para clasificación).

**Para reales (ámbitos 3 y 7)**:
- Una fila por (obra × partida × ámbito × mes-fase).
- `version` aquí guarda el número de fase mensual.
- `version_descripcion` = nombre del mes ("Octubre 2025").
- `pct_*` = NULL.
- Los importes mensuales se calculan con `LAG` sobre el acumulado.
- `total_incurrido` viene de `obrparpre.totinc`.

### 5.4 Schema `mart`

**Tablas finales optimizadas para consumo por Power BI**.

#### 5.4.1 `mart.fact_seguimiento_mensual`

**La tabla principal**. Una fila por (obra × partida × mes × escenario).

Columnas (resumido):

```
fact_id (PK)
-- Dimensión obra
obra_id, codigo_obra, nombre_obra
-- Dimensión partida
partida_id, codigo_partida, descripcion_partida, unidad_medida
categoria, capitulo_raiz_cod, ruta_capitulos
-- Dimensión temporal
anio_mes, anio, mes, nombre_mes
-- Dimensión escenario
escenario              ← "Coste Real" / "Coste Planificado" /
                         "Venta Real" / "Venta Planificada"
tipo_dato              ← "REAL" / "PLANIFICADO"
concepto               ← "COSTE" / "VENTA"
ambito_id              ← 3 / 7 / 8 / 11
-- Métricas (versiones Sigrid-compatible)
importe_mes            ← can × ROUND(pre, 2) × pct_mes (master)
                       ← LAG sobre acumulado redondeado (reales)
importe_origen         ← acumulado a origen Sigrid-compatible
-- Métricas (versiones raw, sin redondear pre)
importe_mes_raw
importe_origen_raw
-- Cantidades y precio
can_mes, can_origen, precio_unitario
-- Trazabilidad de versión master (solo planificado)
version_master, version_descripcion, version_tex,
version_fec_creacion, tipo_master
-- Incurrido Sigrid (solo coste real)
total_incurrido, total_incurrido_mes
```

Volumen orientativo: **~13 millones de filas** con datos reales de Ruesma.

#### 5.4.2 `mart.fact_seguimiento_categoria`

**Tabla pre-agregada por (obra × mes × categoría × escenario)** para visuales
de cuadro de mando que no necesitan drill-down a partida.

Volumen orientativo: **~23.000 filas**. Permite que Power BI muestre KPIs
sin tener que agregar 13M filas en cada refresh.

#### 5.4.3 `mart.v_fact_periodificado` (vista)

Vista derivada de `mart.fact_seguimiento_mensual` que aplica las reglas de
`aux.periodificacion_partida`. **Hoy devuelve lo mismo que la tabla** porque
no hay reglas definidas. Cuando se activen, periodifica el coste de partidas
seleccionadas (montaje grúa, instalación obra...) a lo largo de varios meses.

---

## 6. Reglas de negocio implementadas

### 6.1 Selección de la versión vigente

Para cada mes, se elige UNA versión del master como vigente:

```sql
-- Pseudocódigo
WHERE version_fec_creacion < (anio_mes + INTERVAL '1 month')
  AND tipo_master IN ('Planif Inicial', 'ABC', 'Cuatrimestral')
ORDER BY version_fec_creacion DESC, version DESC
LIMIT 1
```

**Solo las versiones de tipo Planif Inicial, ABC y Cuatrimestral son master
vigente**. Las versiones de tipo Cierre mensual se descartan en esta selección.

### 6.2 Clasificación del `tex`

Reglas en orden de prioridad (la primera que matchea gana):

```
1. tex contiene "ABC"                        → ABC
2. tex contiene "INICIAL" Y "VALORADA"       → Planif Inicial
3. tex contiene "CUATRIM" O "VALORADA"       → Cuatrimestral
4. tex contiene "CIERRE" (sin ABC)           → Cierre mensual
5. tex vacío o no matchea nada               → Sin clasificar
```

La regla 3 captura los dos formatos que usa el JO de Ruesma:
- `"PLANIFICACION CUATRIMESTRAL FEB-26"` (explícito con palabra "cuatrim")
- `"PLANIFICACION VALORADA OCT-25"` (sin palabra "cuatrim", solo "valorada")

### 6.3 Categoría CD/CI/CP

Se asigna usando el código del capítulo raíz del árbol:

```
LIKE '%CD%'                                          → CD
LIKE '%CI%'                                          → CI
LIKE '%CP%'                                          → CP
numérico puro (01, 02...) salvo 34 y 99              → CD (defensiva)
resto                                                → OTRO
```

La regla "numérico puro = CD" es defensiva: si una obra organiza partidas
directamente bajo un raíz numérico sin un raíz "CD" explícito, se asume CD.

### 6.4 Propagación coste→venta del `tex`

En Ruesma, el JO solo rellena `obrfasamb.tex` para el master coste (amb=8).
El master venta (amb=11) viene con `tex` vacío.

El SQL hace una propagación: para cada (obra, versión, amb=11), si `tex` está
vacío, se busca el `tex` correspondiente en (obra, versión, amb=8) y se usa.
Así, ambos ámbitos comparten clasificación.

### 6.5 Doble cálculo de importe (Sigrid-compatible vs raw)

Para cada importe se calculan dos versiones:

| Columna | Fórmula | Uso |
|---|---|---|
| `importe_mes`, `importe_origen` | `can × ROUND(pre, 2)` | **Oficial** — cuadra con Sigrid al céntimo |
| `importe_mes_raw`, `importe_origen_raw` | `can × pre` | Referencia para auditoría |

Power BI consume las columnas oficiales. Las `_raw` están disponibles para
investigar discrepancias si surgen.

### 6.6 Cálculo del importe mensual de reales

Se hace con `LAG` sobre el acumulado:

```sql
importe_mes = importe_origen_N − COALESCE(LAG(importe_origen) OVER (...), 0)
```

Donde la partición es `(obra, partida, ámbito)` y el orden es `mes_fase_num`.

### 6.7 Explosión del `planif` del master

El string `planif` se parsea con `string_to_array(planif, '|')` y `unnest`
con `WITH ORDINALITY` para preservar la posición:

```sql
SELECT
  posicion_mes,
  pct_acumulado,
  pct_acumulado − LAG(pct_acumulado) OVER (...) AS pct_mes
FROM ... CROSS JOIN LATERAL unnest(string_to_array(planif, '|')) WITH ORDINALITY
```

El mes ancla es `obrfasamb.plafec`. El mes 1 = plafec, mes 2 = plafec + 1 mes,
etc.

---

## 7. Instalación y arranque

### 7.1 Prerrequisitos

- **Python 3.12** (instalar desde python.org).
- **PostgreSQL 15+** corriendo en local (instalación nativa o Docker).
- **Git** para clonar el repositorio.
- **Acceso a la API de Sigrid** (Function App de Azure). El equipo IT
  proporciona la URL base y la function key.

### 7.2 Configuración del entorno

#### Paso 1 — Clonar el repositorio

```powershell
cd C:\Users\<usuario>\PycharmProjects
git clone <url-del-repo> datamart-seg-anual
cd datamart-seg-anual
```

#### Paso 2 — Crear el entorno virtual

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

#### Paso 3 — Configurar Postgres

Asegúrate de que Postgres está corriendo. Crea un usuario y una base de datos
admin si no existen:

```sql
CREATE USER postgres WITH PASSWORD 'tu_password_aqui' SUPERUSER;
CREATE DATABASE postgres OWNER postgres;
```

El proyecto creará la base de datos `sigrid_dm` automáticamente al arrancar.

#### Paso 4 — Crear el archivo `.env`

En la raíz del proyecto, crea `.env` con tus credenciales:

```env
# API de Sigrid
SIGRID_API_BASE_URL=https://func-sigridapi-dev-huyke.azurewebsites.net
SIGRID_API_FUNCTION_KEY=<la-function-key-que-te-dieron>
SIGRID_API_DATABASE=ruesma
SIGRID_API_TIMEOUT_S=120
SIGRID_API_PAGE_SIZE=500000
SIGRID_API_MAX_RETRIES=3

# Postgres
PG_HOST=127.0.0.1
PG_PORT=5432
PG_DB=sigrid_dm
PG_USER=postgres
PG_PASSWORD=<tu-password-postgres>
PG_ADMIN_DB=postgres

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=console
```

### 7.3 Primera ejecución (BD vacía)

```powershell
# 1. Verifica conexiones
python main.py check-pg
python main.py check-api

# 2. Bootstrap (crea schemas, idempotente)
python main.py bootstrap

# 3. Ingesta completa desde Sigrid (toma ~50-60 minutos)
python main.py ingest --full

# 4. Construcción de stg (toma ~20-25 minutos)
python main.py stage

# 5. Construcción del mart (toma ~3 minutos)
python main.py build-mart
```

Alternativa "todo en uno":

```powershell
python main.py run-all --full
```

### 7.4 Refresco diario (BD ya existe)

```powershell
# Ingesta incremental (solo filas modificadas en Sigrid)
python main.py ingest

# Reconstrucción stg + mart
python main.py stage
python main.py build-mart
```

O encadenado: `python main.py run-all` (sin `--full`).

---

## 8. Comandos del CLI

### 8.1 Comandos principales

#### `bootstrap`

Crea base de datos `sigrid_dm` y schemas `raw, aux, stg, mart, _meta`.
Idempotente — si existen, no hace nada.

```powershell
python main.py bootstrap
```

#### `check-pg`

Verifica que la conexión a Postgres funciona. Imprime versión del servidor.

```powershell
python main.py check-pg
```

#### `check-api`

Verifica que la API de Sigrid responde y la function key es válida.

```powershell
python main.py check-api
```

#### `ingest [--full] [--table T]`

Descarga datos desde Sigrid → `raw.*`.

- Sin opciones: ingesta incremental de todas las tablas (rápido, solo trae
  cambios desde la última ejecución).
- `--full`: refresco completo (TRUNCATE + INSERT). Necesario tras cambios de
  schema o si los datos `raw` se corrompen.
- `--table T`: ingiere solo una tabla concreta.

```powershell
python main.py ingest
python main.py ingest --full
python main.py ingest --table obrparpre --full
```

#### `stage`

Reconstruye `stg.*` desde `raw.*`. Es un TRUNCATE+INSERT, no incremental:
siempre regenera todo.

Sub-pasos internos (visibles en logs):
- `functions`: funciones auxiliares (formato de fecha Sigrid, etc.)
- `ddl`: crea tablas si no existen
- `ambitos_view`: vista de ámbitos con clasificación lógica
- `build_obras`: carga obras
- `build_partidas`: **reconstruye el árbol** de partidas y asigna categoría
- `build_fases`: calendario de obra
- `build_presupuesto`: limpieza básica de `obrparpre`
- `build_version_master_vigente`: lee de `conext`
- `build_plan_mensual`: **núcleo** — explota planif y calcula LAG

```powershell
python main.py stage
```

#### `build-mart`

Reconstruye `mart.*` desde `stg.*`. También TRUNCATE+INSERT.

Sub-pasos:
- `ddl`: crea tablas si no existen
- `build_fact`: tabla principal con 4 escenarios
- `agg_categoria`: tabla agregada por capítulo
- `view_periodificado`: vista con periodificación

```powershell
python main.py build-mart
```

#### `run-all [--full]`

Encadena ingest → stage → build-mart en orden, con manejo de errores.

```powershell
python main.py run-all              # diario
python main.py run-all --full       # desde cero
```

### 8.2 Comandos de reset

Útiles cuando cambia el schema de una tabla.

#### `reset-fases`

Borra `stg.fases`. Lanzar antes de `stage` si se cambió su DDL.

#### `reset-plan-mensual`

Borra `stg.plan_mensual`. Lanzar antes de `stage` si se cambió su DDL.

#### `reset-mart`

Borra `mart.fact_seguimiento_mensual`. Lanzar antes de `build-mart` si se
cambió el DDL del mart.

### 8.3 Comandos de inspección

#### `status`

Cuenta filas en cada tabla de `raw.*`.

#### `status-stg`

Cuenta filas en cada tabla de `stg.*` y `mart.*`.

#### `inspect-raw`

Lista todas las tablas raw con sus columnas y conteos.

#### `inspect-tree --obra N [--top N]`

Muestra el árbol jerárquico de partidas de una obra. Útil para validar la
clasificación CD/CI/CP.

```powershell
python main.py inspect-tree --obra 2563363 --top 100
```

Salida:

```
nivel  código       raíz  cat   descripción              ruta
   0   CD           CD    CD    COSTES DIRECTOS          CD
   1     01         CD    CD    MOV. TIERRAS             CD > 01
   2       01.02    CD    CD    EXCAVACIÓN VACIADOS      CD > 01 > 01.02
   ...
```

#### `list-versions --obra N [--ambito A]`

Lista todas las versiones de master (y reales) de una obra con su clasificación.

```powershell
python main.py list-versions --obra 2563363
```

#### `inspect-categoria --obra N [--mes M]`

Muestra el agregado por categoría (CD/CI/CP/OTRO) para una obra y opcionalmente
un mes concreto.

```powershell
python main.py inspect-categoria --obra 2563363 --mes 2026-01-01
```

Salida:

```
mes          cat       CR_mes       CP_mes       VR_mes       VP_mes   #part
2026-01-01   CD     104,874.12   144,558.19   152,670.61   195,114.50    267
2026-01-01   CI      54,221.67   104,184.45        -            -         41
2026-01-01   CP      17,633.46    21,756.30        -            -          5
```

#### `inspect-mart --obra N [--partida P] [--anio-mes-desde D] [--anio-mes-hasta H]`

Muestra la comparativa mensual completa de una obra (o partida concreta dentro
de la obra). Pivota los 4 escenarios para que cada mes sea una fila con
CR_mes / CP_mes / VR_mes / VP_mes lado a lado.

```powershell
python main.py inspect-mart --obra 2563363
python main.py inspect-mart --obra 2563363 --partida 394181
```

#### `inspect-month --obra N --mes YYYY-MM-DD [--top N] [--ambito coste|venta|todos]`

El comando más útil para **validar contra Sigrid**. Muestra TODAS las partidas
de una obra para un mes concreto con los 4 escenarios y ambas versiones de
importe (Sigrid-compatible vs raw).

```powershell
python main.py inspect-month --obra 2563363 --mes 2026-01-01 --top 30
python main.py inspect-month --obra 2563363 --mes 2026-01-01 --ambito venta
```

#### `inspect-plan --obra N [--partida P] [--ambito A]`

Muestra las versiones del master de una partida concreta con el detalle del
`planif` crudo (los porcentajes acumulados).

```powershell
python main.py inspect-plan --obra 2563363 --partida 394181 --ambito 11
```

---

## 9. Validación contra Sigrid

Esta sección describe cómo verificar que el mart cuadra con lo que muestra
Sigrid en su UI. Es **importantísimo** hacer esta validación periódicamente,
sobre todo cuando se añaden obras nuevas o cambian estructuras.

### 9.1 Validación a nivel partida

Abrir Sigrid y navegar a:

```
Obra → pestaña "Seguimiento" → Ámbito (COSTE / VENTA) → Fase del mes
```

Anotar para una partida concreta los valores que Sigrid muestra:
- Med.Origen, Med.Parcial
- Precio
- Importe Parcial, Importe Origen

Luego ejecutar:

```powershell
python main.py inspect-month --obra <obra_id> --mes <YYYY-MM-DD> --top 30
```

Buscar la misma partida en el output y comparar:

| Sigrid | Nuestro mart | Esperado |
|---|---|---|
| Imp.Parcial (coste) | `CR_mes` | Idénticos al céntimo |
| Imp.Origen (coste) | `CR_orig` | Idénticos al céntimo |
| Imp.Parcial (venta) | `VR_mes` | Idénticos al céntimo |
| Imp.Origen (venta) | `VR_orig` | Idénticos al céntimo |

### 9.2 Validación a nivel total de obra

Sigrid muestra los totales en la cabecera del seguimiento (filas
"PRESUPUESTO", "CD", "CI", "CP").

```powershell
python main.py inspect-categoria --obra <obra_id> --mes <YYYY-MM-DD>
```

Comparar suma de CR_mes de CD+CI+CP con el TOTAL CR_mes de Sigrid.

### 9.3 Validación de versión vigente

Para verificar qué versión del master rige en cada mes:

```powershell
python main.py list-versions --obra <obra_id>
```

El output indica con `✓` qué versiones son master vigente (Planif Inicial /
ABC / Cuatrimestral). Las que no llevan `✓` son Cierre mensual y NO se usan
para CP/VP.

### 9.4 Tolerancia esperada

**Para coste**: tolerancia = 0,00 €. Los costes cuadran al céntimo exacto
porque los precios suelen ser redondos (14,00 €/m3, etc.).

**Para venta**: tolerancia = 0,00 € si se usan las columnas `_mes` y `_orig`
(Sigrid-compatible). Si por error se consultan las `_raw`, pueden aparecer
diferencias de céntimos (~0,01% del importe).

---

## 10. Conexión a Power BI

### 10.1 Instalar el conector

Power BI Desktop tiene el conector Postgres **nativo**. No necesita instalación
de driver adicional.

Si la versión de Power BI Desktop es muy antigua y pide el driver Npgsql,
descargarlo desde:
https://github.com/npgsql/Npgsql/releases

### 10.2 Conectar

1. En Power BI Desktop: **Obtener datos → Base de datos PostgreSQL**.
2. Servidor: `127.0.0.1` (si Postgres está en local) o el host de Azure cuando
   se despliegue.
3. Base de datos: `sigrid_dm`.
4. Modo: **Importar** (recomendado para empezar; DirectQuery se considera más
   adelante si el dataset crece mucho).
5. Credenciales: usuario `postgres` (o el que tengas configurado).

### 10.3 Tablas a importar

Mi recomendación es importar estas tablas/vistas:

| Tabla/Vista | Propósito | Volumen |
|---|---|---|
| `mart.fact_seguimiento_mensual` | Fact principal | ~13M filas |
| `mart.fact_seguimiento_categoria` | Fact agregado por capítulo | ~23k filas |
| `stg.obras` | Dimensión obra | ~900 |
| `stg.partidas` | Dimensión partida | ~380k |

Power BI generará automáticamente una tabla de fechas. Alternativamente, se
puede crear una dimensión calendario con DAX:

```dax
DimFecha =
ADDCOLUMNS(
    CALENDAR(DATE(2023,1,1), DATE(2030,12,31)),
    "Año",         YEAR([Date]),
    "Mes",         MONTH([Date]),
    "Nombre Mes",  FORMAT([Date], "MMMM yyyy"),
    "Trimestre",   "Q" & FORMAT([Date], "Q"),
    "AnioMes",     DATE(YEAR([Date]), MONTH([Date]), 1)
)
```

### 10.4 Modelo de datos sugerido

```
DimFecha[AnioMes] ─────────► FactSeguimiento[anio_mes]
                              │
DimObras[obra_id]    ────────►│
                              │
DimPartidas[partida_id] ─────►│
```

Configurar relaciones **uno a muchos** (1:N) desde las dimensiones hacia el
fact. Marcar `DimFecha` como tabla de fechas (`Mark as Date Table`).

### 10.5 Medidas DAX clave

Crear estas medidas en una tabla `_Medidas`:

```dax
// ===== Importes mensuales =====
[Coste Real]        = CALCULATE(SUM(FactSeguimiento[importe_mes]),
                                FactSeguimiento[escenario] = "Coste Real")
[Coste Planificado] = CALCULATE(SUM(FactSeguimiento[importe_mes]),
                                FactSeguimiento[escenario] = "Coste Planificado")
[Venta Real]        = CALCULATE(SUM(FactSeguimiento[importe_mes]),
                                FactSeguimiento[escenario] = "Venta Real")
[Venta Planificada] = CALCULATE(SUM(FactSeguimiento[importe_mes]),
                                FactSeguimiento[escenario] = "Venta Planificada")

// ===== Importes a origen =====
[Coste Real Orig]   = CALCULATE(SUM(FactSeguimiento[importe_origen]),
                                FactSeguimiento[escenario] = "Coste Real")
[Coste Plan Orig]   = CALCULATE(SUM(FactSeguimiento[importe_origen]),
                                FactSeguimiento[escenario] = "Coste Planificado")
[Venta Real Orig]   = CALCULATE(SUM(FactSeguimiento[importe_origen]),
                                FactSeguimiento[escenario] = "Venta Real")
[Venta Plan Orig]   = CALCULATE(SUM(FactSeguimiento[importe_origen]),
                                FactSeguimiento[escenario] = "Venta Planificada")

// ===== Desviaciones =====
[Desviación Coste]    = [Coste Real]    - [Coste Planificado]
[Desviación Venta]    = [Venta Real]    - [Venta Planificada]
[Beneficio Real]      = [Venta Real]    - [Coste Real]
[Beneficio Planif]    = [Venta Planificada] - [Coste Planificado]
[Beneficio Real Orig] = [Venta Real Orig] - [Coste Real Orig]
[Margen Real %]       = DIVIDE([Beneficio Real], [Venta Real])
[Margen Planif %]     = DIVIDE([Beneficio Planif], [Venta Planificada])
```

### 10.6 Páginas sugeridas del informe

#### Página 1 — Vista global

KPI cards arriba con:
- Coste Real (mes actual)
- Coste Planificado (mes actual)
- Beneficio Real Acumulado
- Margen %

Gráfico de líneas debajo: evolución mensual de CR vs CP y VR vs VP.

Segmentadores en lateral: obra (single-select), año.

#### Página 2 — Por categoría (CD/CI/CP)

Matriz con:
- Filas: meses
- Columnas: CD / CI / CP (categoría)
- Valores: Coste Real / Coste Planificado / Desviación

Útil para ver dónde se desvía el coste (¿en directos o indirectos?).

#### Página 3 — Drill-down por partida

Matriz con:
- Filas: partidas (jerárquicas usando `ruta_capitulos`)
- Columnas: meses
- Valores: Coste Real, Coste Planificado, Desviación

Permite navegar desde un total alto hasta una partida concreta.

#### Página 4 — Versiones del master

Tabla mostrando para una obra:
- Mes
- Versión vigente
- Tipo (Planif Inicial / ABC / Cuatrimestral)
- Texto JO (`version_tex`)

Útil para entender qué replanificaciones ha tenido la obra y cuándo.

### 10.7 Configuración de refresh

En Power BI Service (cloud):
1. Publicar el `.pbix` al workspace.
2. Configurar **Programa de actualización**: por ejemplo a las 06:00 cada día.
3. Necesita configurar un **gateway** si Postgres está en local.

Si Postgres está en Azure, no se necesita gateway — el refresh es directo.

---

## 11. Despliegue en Azure

(Sección preparada para el futuro; se completará cuando llegue el momento.)

### 11.1 Arquitectura objetivo

```
┌──────────────────────────────────────────────────────────┐
│                     AZURE                                 │
│                                                           │
│  ┌─────────────────┐      ┌──────────────────────┐       │
│  │ Sigrid API      │      │ Postgres Flexible    │       │
│  │ (existente)     │      │ Server               │       │
│  └────────┬────────┘      └──────────▲───────────┘       │
│           │                          │                    │
│           │                          │                    │
│  ┌────────▼──────────────────────────┴───────┐           │
│  │ Container Apps Job (ETL)                   │          │
│  │  - imagen Docker con este proyecto         │          │
│  │  - schedule nocturno 03:00                 │          │
│  │  - endpoint HTTP /refresh para botón       │          │
│  └────────▲───────────────────────────────────┘          │
│           │                                                │
│           │ Power Automate Flow / Web URL                  │
│           │                                                │
└───────────┼────────────────────────────────────────────────┘
            │
            │
   ┌────────┴─────────┐
   │ Power BI Service │
   │ + botón refresh  │
   └──────────────────┘
```

### 11.2 Componentes

- **Postgres Flexible Server B2s**: ~40 €/mes. Reemplaza el Postgres local.
- **Container Apps Job**: ~5 €/mes. Ejecuta el ETL en schedule + HTTP trigger.
- **Power BI Pro**: 10 €/usuario/mes.
- **Total**: ~50-60 €/mes infraestructura + licencias usuarios.

### 11.3 Botón "Actualizar" en Power BI

Opción recomendada: **Power Automate Flow** desde Power BI.

1. Visual Power Automate en el informe.
2. Flow configurado para hacer HTTP POST a `/refresh` del Container Apps Job.
3. Esperar respuesta.
4. Llamar a la API de Power BI para refrescar el dataset.
5. El usuario ve confirmación visual.

### 11.4 Roadmap

**Fase 1** (actual): pipeline local estable + Power BI Desktop funcionando.
**Fase 2**: migración a Azure (Postgres + Container Apps Job con schedule).
**Fase 3**: botón Actualizar con Power Automate.
**Fase 4**: monitorización (Application Insights, alertas).

---

## 12. Mantenimiento y resolución de problemas

### 12.1 Cuando cambia el schema de Sigrid

Si Sigrid añade/elimina columnas, el preflight de `stage` detectará el problema:

```
ERROR: Columnas faltantes en raw.obrparpar: ['nueva_columna_x']
```

Solución:
1. Ejecutar `python main.py ingest --table <tabla> --full` para recoger el
   schema actualizado.
2. Si se quiere usar la columna nueva, añadirla al SQL correspondiente en
   `stg/` y al preflight en `build_stg_step.py`.

### 12.2 Cuando se añade una obra nueva

No requiere ninguna acción especial. La ingesta incremental traerá automáticamente
las nuevas filas de `obrparpar`, `obrparpre`, etc. La obra aparecerá en `stg.obras`
y el mart se construirá con ella tras `stage` y `build-mart`.

### 12.3 Cuando se cambia un DDL

Si cambia el DDL de una tabla, la tabla existente no se modifica
automáticamente. Soluciones:

```powershell
# Para stg.fases:
python main.py reset-fases
python main.py stage

# Para stg.plan_mensual:
python main.py reset-plan-mensual
python main.py stage

# Para stg.partidas (no hay reset específico — drop manual):
python -c "
from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient
from config.settings import get_settings
s = get_settings()
pg = PostgresClient(conninfo=s.postgres.conninfo,
                    admin_conninfo=s.postgres.admin_conninfo,
                    target_db=s.postgres.db)
with pg.connection() as c, c.cursor() as cur:
    cur.execute('DROP TABLE IF EXISTS stg.partidas CASCADE')
    c.commit()
"
python main.py stage

# Para mart:
python main.py reset-mart
python main.py build-mart
```

### 12.4 Errores comunes

#### `Tabla 'X' no declarada en tables_sigrid.yaml`

Significa que se intentó ingerir una tabla que no está configurada. Solución:
añadir entrada en `config/tables_sigrid.yaml`.

#### `no existe la columna 'X'` (Postgres)

Una columna del SQL no está en la tabla. Posibles causas:
- DDL desactualizado (ejecutar reset + rebuild).
- Ingesta incremental no añadió una columna nueva (ejecutar `ingest --full`).

#### `no existe la relación 'raw.X'`

La tabla raw aún no se ha ingerido. Ejecutar `python main.py ingest --table X`.

#### Stage tarda mucho

Es normal. `08_plan_mensual.sql` es la operación más pesada (~20 minutos con
volúmenes de Ruesma) porque hace explosión del `planif` para 5M+ filas master.

### 12.5 Periodificación de partidas

Cuando Negocio defina las reglas:

```sql
-- Conectarse a Postgres y ejecutar:
INSERT INTO aux.periodificacion_partida (patron_codigo, metodo, plazo_meses, descripcion)
VALUES
  ('CI.2.%',  'LINEAL', 12, 'Instalación de obra: amortizar 12 meses'),
  ('CI.1.16', 'LINEAL', 24, 'Técnico prevención: contrato anual');

-- Luego rebuild:
-- python main.py build-mart
```

Las partidas que matcheen las reglas se periodificarán en `mart.v_fact_periodificado`.

---

## 13. Glosario

| Término | Significado |
|---|---|
| **ABC** | Tipo de cierre de Sigrid: revisión completa con clasificación de partidas |
| **A origen** | Importe acumulado desde inicio de obra hasta el momento |
| **Ámbito** | Concepto de Sigrid para diferenciar tipos de datos (Coste, Venta, Master Coste, Master Venta...) |
| **CD** | Costes Directos (excavación, hormigón, etc.) |
| **CI** | Costes Indirectos (jefatura de obra, técnicos, etc.) |
| **CP** | Costes Proporcionales (estructura de empresa repartida) |
| **Capítulo** | Nodo intermedio del árbol de presupuesto |
| **Cierre mensual** | Tipo de versión del master: revisión menor que no reemplaza al plan oficial |
| **Cuatrimestral** | Tipo de versión del master: cierre cuatrimestral oficial (cada 4 meses) |
| **Fase** | En Sigrid, el campo `fas` significa cosas distintas según el ámbito: número de versión (master) o número de mes-fase (reales) |
| **JO** | Jefe de Obra |
| **Master** | Planificación oficial (puede haber varias versiones a lo largo de la obra) |
| **Master vigente** | La versión del master que rige para un mes concreto (regla temporal) |
| **Mart** | Schema con tablas finales optimizadas para Power BI |
| **Partida** | Nodo hoja del árbol de presupuesto, con cantidad, precio e importe |
| **planif** | Columna de Sigrid con string de porcentajes acumulados separados por `|` |
| **Planif Inicial** | Tipo de versión del master: primera planificación al arrancar la obra |
| **Producción** | Sinónimo de "Venta Real" en este proyecto: lo ejecutado mensualmente |
| **Raw** | Schema con datos brutos descargados desde Sigrid sin transformación |
| **Sigrid** | ERP de construcción usado por Ruesma |
| **Sigrid-compatible** | Versión de los importes que cuadra con Sigrid (precio redondeado a 2 dec) |
| **Stg / Staging** | Schema intermedio con datos transformados |
| **`tcaide`** | FK en `obrparpar` al tipo de capítulo (`auxobrtca`). En Ruesma no clasifica CD/CI/CP. |
| **`tex`** | Columna de `obrfasamb` con texto libre del JO al crear una versión |
| **Versión** | En master: cada replanificación crea una versión (v2, v3, v4...) |

---

## Apéndice A — Volúmenes de datos reales (Ruesma)

Datos orientativos de la última carga completa:

| Tabla | Filas |
|---|---|
| `raw.obrparpre` (todas las filas master + reales) | ~13.7 M |
| `raw.obrparpar` (partidas) | ~384 k |
| `raw.obrfas` (fases) | ~4.4 k |
| `raw.obrfasamb` (versiones de master) | ~5 k |
| `stg.obras` | ~900 |
| `stg.partidas` | ~383 k |
| `stg.plan_mensual` | ~13.7 M |
| `mart.fact_seguimiento_mensual` | ~3.4 M |
| `mart.fact_seguimiento_categoria` | ~23 k |

Tiempos orientativos:

| Operación | Tiempo |
|---|---|
| Ingesta incremental (sin novedades) | ~1 minuto |
| Ingesta completa de `obrparpre` | ~1 minuto (384k filas) |
| Ingesta completa total | ~50-60 minutos |
| `stage` completo | ~20-25 minutos (dominado por `plan_mensual`) |
| `build-mart` completo | ~3 minutos |

---

## Apéndice B — Referencias

- **Documentación Sigrid**: `/docs/tablas_sigrid.pdf` (380 páginas, esquema BD)
- **PDF de despliegue Acens**: `/docs/CO388632_Construcciones_Ruesma__Documento_Entregable.pdf`
- **Memoria de versiones SQL**: `business_rules.yaml` contiene comentarios
  con histórico de decisiones de negocio

---

## Apéndice C — Contactos

- **Mantenedor del código**: equipo Construcciones Ruesma + colaborador externo.
- **Soporte Sigrid**: SoftMaint Sigrid (proveedor del ERP).
- **Soporte Azure / infraestructura**: Acens (Telefónica Tech).
- **Acceso a la Function App de Sigrid**: equipo IT Ruesma.
