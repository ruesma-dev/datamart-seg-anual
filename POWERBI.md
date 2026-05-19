# Power BI — Guía de implementación

> Cómo conectar Power BI Desktop al data mart Postgres y construir el cuadro
> de seguimiento mensual de obras. Incluye queries Power Query (M), medidas
> DAX y diseño de páginas.

---

## Tabla de contenidos

1. [Resumen del modelo](#1-resumen-del-modelo)
2. [Prerrequisitos](#2-prerrequisitos)
3. [Conexión a Postgres](#3-conexión-a-postgres)
4. [Queries Power Query (M)](#4-queries-power-query-m)
5. [Modelo y relaciones](#5-modelo-y-relaciones)
6. [Medidas DAX](#6-medidas-dax)
7. [Diseño de páginas](#7-diseño-de-páginas)
8. [Publicación y refresh](#8-publicación-y-refresh)
9. [Resolución de problemas](#9-resolución-de-problemas)

---

## 1. Resumen del modelo

### 1.1 Decisiones técnicas

| Decisión | Elegido | Por qué |
|---|---|---|
| Modo conexión | **Import** | Velocidad de filtros, compresión VertiPaq, full DAX |
| Modelo | **Estrella** (Fact + 4 Dim) | Compresión, mantenibilidad, estándar BI |
| Fuente de datos | **Vistas Postgres** `mart.v_pbi_*` | Desacopla Power BI del mart interno |
| Granularidad fact | (obra × partida × mes × escenario) | Permite drill-down completo |
| Calendario | Generado en Postgres (`v_pbi_dim_fecha`) | Mismo idioma para todos, mantenible |

### 1.2 Esquema del modelo

```
        ┌──────────────┐
        │  DimFecha    │ (calendario mensual)
        └──────┬───────┘
               │ 1:N por anio_mes
               ▼
┌──────────┐  ┌─────────────────────┐  ┌──────────────┐
│ DimObra  │─►│  FactSeguimiento    │◄─│ DimPartida   │
│          │  │  (~13M filas)       │  │              │
└──────────┘  │                     │  └──────────────┘
              │  importe_mes        │
              │  importe_origen     │  ┌──────────────────┐
              │  can_mes, etc.      │◄─│ DimEscenario     │
              └─────────────────────┘  │ (4 valores)      │
                                       └──────────────────┘

         (tabla auxiliar para KPIs rápidos por capítulo:)
              ┌──────────────────────┐
              │ FactCategoria        │  (~23k filas)
              │ (obra × mes × cat)   │
              └──────────────────────┘
```

### 1.3 Tabla resumen del modelo

| Tabla en Power BI | Origen Postgres | Tipo | Volumen | Modo |
|---|---|---|---|---|
| `FactSeguimiento` | `mart.v_pbi_fact` | Fact | ~13M | Import |
| `FactCategoria` | `mart.v_pbi_fact_categoria` | Fact agregada | ~23k | Import |
| `DimObra` | `mart.v_pbi_dim_obra` | Dimensión | ~900 | Import |
| `DimPartida` | `mart.v_pbi_dim_partida` | Dimensión | ~383k | Import |
| `DimEscenario` | `mart.v_pbi_dim_escenario` | Dimensión | 4 | Import |
| `DimFecha` | `mart.v_pbi_dim_fecha` | Dimensión calendario | ~120 (10 años) | Import |
| `_Medidas` | (tabla vacía con medidas DAX) | Solo medidas | 0 filas | — |

---

## 2. Prerrequisitos

### 2.1 Software

- **Power BI Desktop** (versión 2024 o superior). Descargar desde
  https://powerbi.microsoft.com/desktop/.
- El proyecto ETL **debe estar ejecutado al menos una vez** y el mart
  construido. Verifica con:

```powershell
python main.py status-stg
# Debe mostrar mart.fact_seguimiento_mensual con filas
```

### 2.2 Asegurar que las vistas existen

Las vistas `mart.v_pbi_*` se crean automáticamente al ejecutar `build-mart`.
Si las pasaste antes de añadir el archivo `05_views_powerbi.sql`, ejecuta:

```powershell
python main.py build-mart
```

Verifica desde psql:

```sql
SELECT viewname FROM pg_views WHERE schemaname = 'mart' AND viewname LIKE 'v_pbi%';
-- Esperado:
--   v_pbi_dim_escenario
--   v_pbi_dim_fecha
--   v_pbi_dim_obra
--   v_pbi_dim_partida
--   v_pbi_fact
--   v_pbi_fact_categoria
```

### 2.3 Permisos

El usuario que conecta Power BI a Postgres necesita `SELECT` en `mart.*`.
Si usas el mismo usuario `postgres` que el ETL, ya tiene permisos. Si quieres
usuario separado de solo-lectura:

```sql
CREATE USER pbi_reader WITH PASSWORD 'una_contraseña_segura';
GRANT CONNECT ON DATABASE sigrid_dm TO pbi_reader;
GRANT USAGE ON SCHEMA mart TO pbi_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA mart TO pbi_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA mart
    GRANT SELECT ON TABLES TO pbi_reader;
```

---

## 3. Conexión a Postgres

### 3.1 Pasos en Power BI Desktop

1. **Inicio → Obtener datos → Más...**
2. Buscar **PostgreSQL** y seleccionar.
3. Rellenar:
   - **Servidor**: `127.0.0.1` (o `localhost`)
   - **Base de datos**: `sigrid_dm`
4. Modo de conectividad de datos: **Importar** (seleccionado por defecto).
5. **Aceptar**.
6. Power BI pide credenciales:
   - Tipo: **Database**
   - Usuario: `postgres` (o `pbi_reader` si lo creaste)
   - Contraseña: tu password de Postgres
7. **Conectar**.

### 3.2 Si pide instalar driver

Si aparece error "el proveedor Npgsql no está instalado":

1. Descargar Npgsql desde https://github.com/npgsql/Npgsql/releases (versión
   estable más reciente).
2. Instalar.
3. Cerrar Power BI Desktop y volver a abrir.
4. Reintentar conexión.

### 3.3 Seleccionar las vistas

En el navegador de Power BI, expande `mart`. Selecciona estas vistas:

- ☑️ `v_pbi_dim_escenario`
- ☑️ `v_pbi_dim_fecha`
- ☑️ `v_pbi_dim_obra`
- ☑️ `v_pbi_dim_partida`
- ☑️ `v_pbi_fact`
- ☑️ `v_pbi_fact_categoria`

Pulsa **Transformar datos** (NO "Cargar" todavía — vamos a renombrar y limpiar
columnas primero en Power Query).

---

## 4. Queries Power Query (M)

Power Query es donde transformamos los datos antes de cargarlos. Voy a darte
el código M de cada tabla. Para verlo, en el editor Power Query:

- Selecciona la query en el panel izquierdo
- **Ver → Editor avanzado** (muestra el código M)

### 4.1 Query: FactSeguimiento

```m
let
    Source = PostgreSQL.Database("127.0.0.1", "sigrid_dm"),
    mart_v_pbi_fact = Source{[Schema="mart",Item="v_pbi_fact"]}[Data],

    // Conversión de tipos (PostgreSQL → Power BI)
    Typed = Table.TransformColumnTypes(mart_v_pbi_fact, {
        {"fact_id",            Int64.Type},
        {"obra_id",            Int64.Type},
        {"partida_id",         Int64.Type},
        {"anio_mes",           type date},
        {"escenario",          type text},
        {"importe_mes",        type number},
        {"importe_origen",     type number},
        {"importe_mes_raw",    type number},
        {"importe_origen_raw", type number},
        {"can_mes",            type number},
        {"can_origen",         type number},
        {"precio_unitario",    type number},
        {"version_master",     Int64.Type},
        {"version_descripcion",type text},
        {"tipo_master",        type text},
        {"total_incurrido",    type number},
        {"total_incurrido_mes",type number}
    }),

    // Renombrar para nombres limpios en visuales
    Renamed = Table.RenameColumns(Typed, {
        {"anio_mes",            "Fecha"},
        {"importe_mes",         "Importe Mes"},
        {"importe_origen",      "Importe Origen"},
        {"importe_mes_raw",     "Importe Mes (Raw)"},
        {"importe_origen_raw",  "Importe Origen (Raw)"},
        {"can_mes",             "Cantidad Mes"},
        {"can_origen",          "Cantidad Origen"},
        {"precio_unitario",     "Precio Unitario"},
        {"version_master",      "Versión Master Num"},
        {"version_descripcion", "Versión Master"},
        {"tipo_master",         "Tipo Master"},
        {"total_incurrido",     "Total Incurrido"},
        {"total_incurrido_mes", "Incurrido Mes"}
    })
in
    Renamed
```

### 4.2 Query: FactCategoria

```m
let
    Source = PostgreSQL.Database("127.0.0.1", "sigrid_dm"),
    mart_v_pbi_fact_categoria = Source{[Schema="mart",Item="v_pbi_fact_categoria"]}[Data],

    Typed = Table.TransformColumnTypes(mart_v_pbi_fact_categoria, {
        {"fact_cat_id",        Int64.Type},
        {"obra_id",            Int64.Type},
        {"anio_mes",           type date},
        {"categoria",          type text},
        {"escenario",          type text},
        {"importe_mes",        type number},
        {"importe_origen",     type number},
        {"num_partidas",       Int64.Type}
    }),

    Renamed = Table.RenameColumns(Typed, {
        {"anio_mes",            "Fecha"},
        {"importe_mes",         "Importe Mes"},
        {"importe_origen",      "Importe Origen"},
        {"categoria",           "Categoría"},
        {"num_partidas",        "Num Partidas"}
    })
in
    Renamed
```

### 4.3 Query: DimObra

```m
let
    Source = PostgreSQL.Database("127.0.0.1", "sigrid_dm"),
    mart_v_pbi_dim_obra = Source{[Schema="mart",Item="v_pbi_dim_obra"]}[Data],

    Typed = Table.TransformColumnTypes(mart_v_pbi_dim_obra, {
        {"obra_id",     Int64.Type},
        {"codigo_obra", type text},
        {"nombre_obra", type text},
        {"obra_label",  type text}
    }),

    Renamed = Table.RenameColumns(Typed, {
        {"codigo_obra", "Código Obra"},
        {"nombre_obra", "Nombre Obra"},
        {"obra_label",  "Obra"}
    })
in
    Renamed
```

### 4.4 Query: DimPartida

```m
let
    Source = PostgreSQL.Database("127.0.0.1", "sigrid_dm"),
    mart_v_pbi_dim_partida = Source{[Schema="mart",Item="v_pbi_dim_partida"]}[Data],

    Typed = Table.TransformColumnTypes(mart_v_pbi_dim_partida, {
        {"partida_id",          Int64.Type},
        {"obra_id",             Int64.Type},
        {"codigo_partida",      type text},
        {"descripcion_partida", type text},
        {"unidad_medida",       type text},
        {"categoria",           type text},
        {"capitulo_raiz_cod",   type text},
        {"ruta_capitulos",      type text},
        {"nivel",               Int64.Type},
        {"activa",              type logical},
        {"partida_label",       type text},
        {"es_hoja",             type logical}
    }),

    Renamed = Table.RenameColumns(Typed, {
        {"codigo_partida",      "Código Partida"},
        {"descripcion_partida", "Descripción"},
        {"unidad_medida",       "UM"},
        {"categoria",           "Categoría"},
        {"capitulo_raiz_cod",   "Capítulo Raíz"},
        {"ruta_capitulos",      "Ruta"},
        {"nivel",               "Nivel"},
        {"activa",              "Activa"},
        {"partida_label",       "Partida"},
        {"es_hoja",             "Es Hoja"}
    })
in
    Renamed
```

### 4.5 Query: DimEscenario

```m
let
    Source = PostgreSQL.Database("127.0.0.1", "sigrid_dm"),
    mart_v_pbi_dim_escenario = Source{[Schema="mart",Item="v_pbi_dim_escenario"]}[Data],

    Typed = Table.TransformColumnTypes(mart_v_pbi_dim_escenario, {
        {"escenario", type text},
        {"tipo_dato", type text},
        {"concepto",  type text},
        {"ambito_id", Int64.Type},
        {"orden",     Int64.Type}
    }),

    Renamed = Table.RenameColumns(Typed, {
        {"escenario", "Escenario"},
        {"tipo_dato", "Tipo Dato"},
        {"concepto",  "Concepto"},
        {"ambito_id", "Ámbito ID"},
        {"orden",     "Orden"}
    })
in
    Renamed
```

### 4.6 Query: DimFecha

```m
let
    Source = PostgreSQL.Database("127.0.0.1", "sigrid_dm"),
    mart_v_pbi_dim_fecha = Source{[Schema="mart",Item="v_pbi_dim_fecha"]}[Data],

    Typed = Table.TransformColumnTypes(mart_v_pbi_dim_fecha, {
        {"anio_mes",           type date},
        {"anio",               Int64.Type},
        {"mes",                Int64.Type},
        {"trimestre",          Int64.Type},
        {"nombre_mes_solo",    type text},
        {"nombre_mes_anio",    type text},
        {"anio_mes_iso",       type text},
        {"trimestre_label",    type text},
        {"es_pasado_o_actual", type logical},
        {"es_mes_actual",      type logical}
    }),

    Renamed = Table.RenameColumns(Typed, {
        {"anio_mes",          "Fecha"},
        {"anio",              "Año"},
        {"mes",               "Mes Num"},
        {"trimestre",         "Trimestre Num"},
        {"nombre_mes_solo",   "Mes"},
        {"nombre_mes_anio",   "Mes Año"},
        {"anio_mes_iso",      "Año-Mes ISO"},
        {"trimestre_label",   "Trimestre"},
        {"es_pasado_o_actual","Es Pasado"},
        {"es_mes_actual",     "Es Mes Actual"}
    })
in
    Renamed
```

### 4.7 Query: _Medidas (tabla vacía)

Crear desde **Inicio → Especificar datos**:

- Nombre: `_Medidas`
- Una columna llamada `_` (guion bajo)
- Sin filas (o una fila con valor vacío)

Después se ocultará la columna `_` y solo se mostrarán las medidas DAX.

El propósito: **agrupar todas las medidas DAX en una "tabla" lógica** para
mantener el modelo limpio. Por convención, las tablas de solo-medidas
empiezan con `_` para que aparezcan al principio del panel.

### 4.8 Una vez creadas todas las queries

Click **Inicio → Cerrar y aplicar**. Power BI ejecutará las queries M, cargará
los datos y volverá a la vista normal.

---

## 5. Modelo y relaciones

### 5.1 Vista de modelo

En Power BI Desktop, ir a la vista **Modelo** (icono columna izquierda).
Verás las 6 tablas + _Medidas. Power BI puede haber detectado relaciones
automáticamente — verifica y ajusta si es necesario.

### 5.2 Relaciones a configurar

| De (1) | A (N) | Columna en (1) | Columna en (N) | Filtro |
|---|---|---|---|---|
| `DimObra` | `FactSeguimiento` | `obra_id` | `obra_id` | Único, dirección única |
| `DimPartida` | `FactSeguimiento` | `partida_id` | `partida_id` | Único, dirección única |
| `DimEscenario` | `FactSeguimiento` | `Escenario` | `escenario` | Único, dirección única |
| `DimFecha` | `FactSeguimiento` | `Fecha` | `Fecha` | Único, dirección única |
| `DimObra` | `FactCategoria` | `obra_id` | `obra_id` | Único, dirección única |
| `DimFecha` | `FactCategoria` | `Fecha` | `Fecha` | Único, dirección única |
| `DimEscenario` | `FactCategoria` | `Escenario` | `escenario` | Único, dirección única |

Nota: NO se crea relación entre `DimPartida` y `FactCategoria` (la fact
agregada no lleva partida).

### 5.3 Marcar DimFecha como tabla de fechas

En la vista Modelo:

1. Click derecho sobre `DimFecha`.
2. **Marcar como tabla de fechas**.
3. Elegir columna `Fecha`.

Esto habilita time-intelligence completa en DAX.

### 5.4 Ocultar columnas técnicas

Para evitar que el usuario use IDs en visuales, oculta:

- `FactSeguimiento[fact_id]`, `[obra_id]`, `[partida_id]`, `[escenario]`, `[Fecha]`
- `FactCategoria[fact_cat_id]`, `[obra_id]`, `[escenario]`, `[Fecha]`
- `DimObra[obra_id]`
- `DimPartida[partida_id]`, `[obra_id]`
- `DimEscenario[Ámbito ID]`, `[Orden]`
- `DimFecha[Mes Num]`, `[Trimestre Num]`

Click derecho sobre cada columna → **Ocultar en vista de informe**.

### 5.5 Ordenar columnas por otra columna

Para que los meses se ordenen cronológicamente (no alfabéticamente):

1. Selecciona `DimFecha[Mes]`.
2. **Herramientas de columnas → Ordenar por columna → `Mes Num`**.

Para `DimEscenario`:
1. Selecciona `DimEscenario[Escenario]`.
2. **Ordenar por columna → `Orden`**.

---

## 6. Medidas DAX

Todas las medidas se crean en la tabla `_Medidas`. Click derecho sobre
`_Medidas` → **Nueva medida** para cada una.

### 6.1 Medidas base (importes del mes)

```dax
Coste Real = 
CALCULATE(
    SUM(FactSeguimiento[Importe Mes]),
    DimEscenario[Escenario] = "Coste Real"
)

Coste Planificado = 
CALCULATE(
    SUM(FactSeguimiento[Importe Mes]),
    DimEscenario[Escenario] = "Coste Planificado"
)

Venta Real = 
CALCULATE(
    SUM(FactSeguimiento[Importe Mes]),
    DimEscenario[Escenario] = "Venta Real"
)

Venta Planificada = 
CALCULATE(
    SUM(FactSeguimiento[Importe Mes]),
    DimEscenario[Escenario] = "Venta Planificada"
)
```

### 6.2 Medidas a origen (acumulado)

```dax
Coste Real Origen = 
CALCULATE(
    SUM(FactSeguimiento[Importe Origen]),
    DimEscenario[Escenario] = "Coste Real"
)

Coste Plan Origen = 
CALCULATE(
    SUM(FactSeguimiento[Importe Origen]),
    DimEscenario[Escenario] = "Coste Planificado"
)

Venta Real Origen = 
CALCULATE(
    SUM(FactSeguimiento[Importe Origen]),
    DimEscenario[Escenario] = "Venta Real"
)

Venta Plan Origen = 
CALCULATE(
    SUM(FactSeguimiento[Importe Origen]),
    DimEscenario[Escenario] = "Venta Planificada"
)
```

### 6.3 Desviaciones y beneficios

```dax
Desviación Coste = [Coste Real] - [Coste Planificado]

Desviación Venta = [Venta Real] - [Venta Planificada]

Beneficio Real = [Venta Real] - [Coste Real]

Beneficio Planif = [Venta Planificada] - [Coste Planificado]

Desviación Beneficio = [Beneficio Real] - [Beneficio Planif]
```

### 6.4 Márgenes (porcentaje)

```dax
Margen Real % = 
DIVIDE([Beneficio Real], [Venta Real], 0)

Margen Planif % = 
DIVIDE([Beneficio Planif], [Venta Planificada], 0)
```

Tras crear, formato como porcentaje: selecciona la medida y en
**Herramientas → Formato → Porcentaje, 2 decimales**.

### 6.5 Acumulados año

```dax
Coste Real YTD = 
CALCULATE(
    [Coste Real],
    DATESYTD(DimFecha[Fecha])
)

Venta Real YTD = 
CALCULATE(
    [Venta Real],
    DATESYTD(DimFecha[Fecha])
)

Coste Planif YTD = 
CALCULATE(
    [Coste Planificado],
    DATESYTD(DimFecha[Fecha])
)
```

### 6.6 Comparativa vs mes anterior

```dax
Coste Real Mes Anterior = 
CALCULATE(
    [Coste Real],
    DATEADD(DimFecha[Fecha], -1, MONTH)
)

Coste Real Crecimiento = 
VAR Actual = [Coste Real]
VAR Anterior = [Coste Real Mes Anterior]
RETURN
    DIVIDE(Actual - Anterior, Anterior, 0)
```

### 6.7 KPIs orientados a dirección

```dax
% Avance Real = 
DIVIDE(
    [Coste Real Origen],
    CALCULATE([Coste Plan Origen], ALL(DimFecha))   // CP total de toda la obra
)

% Avance Planif = 
DIVIDE(
    [Coste Plan Origen],
    CALCULATE([Coste Plan Origen], ALL(DimFecha))
)

Adelanto/Retraso = [% Avance Real] - [% Avance Planif]
```

### 6.8 Conteos auxiliares

```dax
Num Partidas = 
DISTINCTCOUNT(FactSeguimiento[partida_id])

Num Obras = 
DISTINCTCOUNT(FactSeguimiento[obra_id])

Num Meses Con Datos = 
CALCULATE(
    DISTINCTCOUNT(FactSeguimiento[Fecha]),
    DimEscenario[Tipo Dato] = "REAL"
)
```

### 6.9 Medida dinámica de escenario (avanzada)

Permite tener un segmentador "Escenario" que el usuario elige y los visuales
muestran solo ese escenario. Útil para informes parametrizables.

```dax
Importe Seleccionado = 
VAR EscSel = SELECTEDVALUE(DimEscenario[Escenario], "Coste Real")
RETURN
CALCULATE(
    SUM(FactSeguimiento[Importe Mes]),
    DimEscenario[Escenario] = EscSel
)
```

### 6.10 Validación rápida vs Sigrid

Medida para verificar que cuadramos contra Sigrid (la "diferencia entre las dos
versiones de cálculo de precio"):

```dax
Diff Sigrid vs Raw (Mes) = 
SUM(FactSeguimiento[Importe Mes]) - SUM(FactSeguimiento[Importe Mes (Raw)])

Diff Sigrid vs Raw (Origen) = 
SUM(FactSeguimiento[Importe Origen]) - SUM(FactSeguimiento[Importe Origen (Raw)])
```

Si filtras por una obra/mes/escenario y este número no es 0, sabes que hay
diferencia por el redondeo del precio.

---

## 7. Diseño de páginas

Propuesta de 4 páginas para el informe. Cada una con un propósito claro y
una audiencia específica.

### 7.1 Página 1 — Vista global

**Audiencia**: dirección general. Quieren ver el estado en 10 segundos.

**Layout**:

```
┌─────────────────────────────────────────────────────────────┐
│  [Segmentador: Obra]    [Segmentador: Año]                  │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ Coste Real  │  │ Venta Real  │  │ Beneficio   │         │
│  │  XXX.XXX €  │  │  XXX.XXX €  │  │  XXX.XXX €  │         │
│  │  vs Planif  │  │  vs Planif  │  │ Margen XX%  │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Gráfico líneas: evolución mensual                   │    │
│  │ Líneas: Coste Real, Coste Planif, Venta Real,       │    │
│  │         Venta Planif                                │    │
│  │ Eje X: meses                                        │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────┐ ┌──────────────────────────┐   │
│  │ Tabla: TOP partidas      │ │ Donut: distribución CD/  │  │
│  │ con mayor desviación     │ │ CI/CP del coste planif   │  │
│  └─────────────────────────┘ └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Componentes**:

1. **Segmentador Obra**: `DimObra[Obra]` (lista desplegable, single-select).
2. **Segmentador Año**: `DimFecha[Año]` (botones).
3. **3 tarjetas KPI**:
   - Tarjeta 1: medida `Coste Real`, con subtítulo `Desviación Coste`.
   - Tarjeta 2: medida `Venta Real`, con subtítulo `Desviación Venta`.
   - Tarjeta 3: medida `Beneficio Real`, con subtítulo `Margen Real %`.
4. **Gráfico de líneas**:
   - Eje X: `DimFecha[Mes Año]`
   - Eje Y: 4 líneas con medidas `Coste Real`, `Coste Planificado`, `Venta Real`, `Venta Planificada`.
5. **Tabla TOP partidas**:
   - Columnas: `DimPartida[Código Partida]`, `DimPartida[Descripción]`, `Desviación Coste`.
   - Ordenado por `Desviación Coste` desc.
   - Top N = 10.
6. **Donut**:
   - Categoría: `DimPartida[Categoría]` (CD/CI/CP).
   - Valores: `Coste Planificado`.

### 7.2 Página 2 — Por capítulos (CD/CI/CP)

**Audiencia**: control de gestión. Quieren ver dónde se desvía el coste.

```
┌─────────────────────────────────────────────────────────────┐
│  [Segmentadores: Obra, Año]                                 │
├─────────────────────────────────────────────────────────────┤
│  Matriz:                                                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Filas: Meses                                         │   │
│  │ Columnas: Categoría (CD, CI, CP) × Escenario         │   │
│  │ Valores: Importe Mes                                 │   │
│  │ Totales: por fila y por columna                      │   │
│  └──────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Gráfico de barras apiladas:                                 │
│  - Eje X: meses                                              │
│  - Series apiladas: CD, CI, CP                               │
│  - Valor: Coste Real                                         │
└─────────────────────────────────────────────────────────────┘
```

**Importante**: para esta página usa preferentemente `FactCategoria` en lugar
de `FactSeguimiento`. Es 600x más pequeña y los visuales serán instantáneos.

### 7.3 Página 3 — Drill-down por partida

**Audiencia**: jefe de obra, control de proyecto. Quieren ver el detalle.

```
┌─────────────────────────────────────────────────────────────┐
│  [Segmentadores: Obra, Categoría, Mes (rango)]              │
├─────────────────────────────────────────────────────────────┤
│  Matriz con jerarquía:                                       │
│  - Filas: Capítulo Raíz > Ruta > Partida                    │
│  - Columnas: meses (rango seleccionado)                      │
│  - Valores: Importe Mes (Coste Real)                         │
│  - Drill-down: el usuario expande capítulos                  │
└─────────────────────────────────────────────────────────────┘
```

**Componentes**:

1. **Segmentador Obra**: single-select.
2. **Segmentador Categoría**: `DimPartida[Categoría]`, multi-select.
3. **Segmentador Mes**: `DimFecha[Fecha]` como rango.
4. **Matriz**:
   - Filas (con jerarquía): `DimPartida[Capítulo Raíz]` → `DimPartida[Ruta]` → `DimPartida[Partida]`.
   - Columnas: `DimFecha[Mes Año]`.
   - Valores: `Coste Real`, `Coste Planificado`, `Desviación Coste`.

### 7.4 Página 4 — Versiones del master

**Audiencia**: el JO. Saber qué replanificaciones ha hecho.

```
┌─────────────────────────────────────────────────────────────┐
│  [Segmentador: Obra]                                         │
├─────────────────────────────────────────────────────────────┤
│  Tabla:                                                      │
│  - Mes                                                       │
│  - Versión vigente (número)                                  │
│  - Tipo (Planif Inicial / ABC / Cuatrimestral)               │
│  - Texto JO                                                  │
│  - Fecha de creación                                         │
└─────────────────────────────────────────────────────────────┘
```

Crea una medida específica para esto:

```dax
Versión Vigente = 
CALCULATE(
    MAX(FactSeguimiento[Versión Master Num]),
    DimEscenario[Escenario] = "Coste Planificado"
)

Tipo Master Vigente = 
CALCULATE(
    MAX(FactSeguimiento[Tipo Master]),
    DimEscenario[Escenario] = "Coste Planificado"
)

Texto JO Vigente = 
CALCULATE(
    MAX(FactSeguimiento[Versión Master]),
    DimEscenario[Escenario] = "Coste Planificado"
)
```

---

## 8. Publicación y refresh

### 8.1 Publicar al servicio Power BI

1. **Inicio → Publicar** (botón en cinta).
2. Elige el espacio de trabajo destino (puede ser "Mi espacio de trabajo" para empezar).
3. Si tu Postgres está en local, Power BI Service necesita un **Data Gateway**:

#### 8.1.1 Instalar Power BI Gateway (si Postgres está local)

1. Descargar **On-premises data gateway (standard mode)** desde
   https://powerbi.microsoft.com/gateway/.
2. Instalar en la máquina que tiene acceso al Postgres (puede ser un servidor
   Windows dedicado o tu propio PC si estará siempre encendido).
3. Configurar con tu cuenta corporativa.
4. En Power BI Service → **Configuración → Administrar puertas de enlace**:
   - Añadir origen de datos: PostgreSQL
   - Servidor: `127.0.0.1` o el nombre del servidor
   - Base de datos: `sigrid_dm`
   - Método autenticación: Basic
   - Credenciales: usuario/password Postgres.
5. En el dataset publicado:
   - **Configuración → Conexión de gateway**:
     - Seleccionar el gateway instalado
     - Mapear el origen de datos al que acabas de añadir.

### 8.2 Programar refresh

Una vez configurado el gateway:

1. En Power BI Service → tu dataset → **Configuración → Actualización programada**.
2. Activar.
3. Frecuencia: diaria, por ejemplo a las **07:00** (asume que el ETL nocturno
   acabó antes).
4. Email de notificación en caso de error.

### 8.3 Refresh manual

Desde Power BI Service: dataset → click en icono ↻ **Actualizar ahora**.

Desde Power BI Desktop: **Inicio → Actualizar**.

---

## 9. Resolución de problemas

### 9.1 "No se puede conectar al servidor"

- Verifica que Postgres está corriendo: `psql -U postgres -h 127.0.0.1`.
- Verifica firewall: el puerto 5432 debe estar abierto en `localhost`.
- Si el servidor es remoto, verifica que `pg_hba.conf` permite conexiones desde tu IP.

### 9.2 "Hay un error en el modelo de datos"

Suele ser por columnas que cambiaron tipo. Reabre cada query en Editor avanzado
y verifica que `Table.TransformColumnTypes` cubre todas las columnas que existen
en la vista (algunas pueden haberse añadido).

### 9.3 Refresh muy lento

Power BI Desktop está cargando 13M filas. Es normal que tarde **5-15 minutos**.

Si es inaceptable, opciones:

- **Filtrar por año en Power Query**: añadir paso `Table.SelectRows` que
  limite a los últimos 2 años.
- **Cambiar a DirectQuery**: cada visual irá a Postgres en lugar de tener
  los datos cargados. Hay que reescribir algunas medidas DAX porque
  DirectQuery limita ciertas funciones.

### 9.4 "La medida X devuelve resultado incorrecto"

Verifica con el comando CLI:

```powershell
python main.py inspect-month --obra <obra> --mes <YYYY-MM-DD>
```

Si los números del CLI son correctos pero los de Power BI no, suele ser:

- Filtro de contexto inesperado (otra medida o segmentador filtrando algo).
- Relación mal configurada.
- Confusión entre `Importe Mes` (Sigrid-compat) y `Importe Mes (Raw)`.

Usa el **panel de filtros** del visual para ver qué filtros están activos.

### 9.5 Cardinalidad del modelo

Para verificar el tamaño del modelo: **Archivo → Opciones y configuración →
Configuración del modelo de datos**. Verás cuánto pesa.

Si supera 1GB y tienes Power BI Pro, se subirá pero hay límite. Las soluciones:

- Quitar columnas que no se usan.
- Reducir cardinalidad de strings (mover a dimensión).
- Filtrar en Power Query (últimos N años).

### 9.6 El gateway falla

Errores típicos del gateway:

- **"No se pudo encontrar el origen de datos"**: el mapping en el dataset
  no apunta al data source correcto. Revisar configuración del dataset.
- **"Credenciales incorrectas"**: el password de Postgres cambió. Actualizar
  en el gateway.
- **"El gateway no está ejecutándose"**: el servicio Windows del gateway está
  parado. Reiniciar.

---

## Apéndice A — Resumen de pasos

Resumen comprimido para tenerlo a mano:

```
1. Verificar mart construido         python main.py status-stg
2. Power BI Desktop → Obtener datos → PostgreSQL
3. Servidor: 127.0.0.1, BD: sigrid_dm
4. Importar 6 vistas: v_pbi_*
5. Renombrar y tipar en Power Query (código M)
6. Aplicar y cargar
7. Vista Modelo: crear relaciones (7 relaciones)
8. Marcar DimFecha como tabla de fechas
9. Ocultar columnas técnicas (IDs)
10. Crear tabla _Medidas y añadir las medidas DAX
11. Diseñar las 4 páginas
12. Publicar al servicio
13. (Si Postgres local) Instalar Gateway
14. Configurar refresh programado
```

## Apéndice B — Volúmenes esperados

| Visual | Tabla usada | Velocidad esperada |
|---|---|---|
| KPI cards | FactSeguimiento o FactCategoria | < 1s |
| Gráfico líneas obra | FactSeguimiento filtrado | 1-2s |
| Matriz CD/CI/CP | FactCategoria | < 1s |
| Drill-down partidas | FactSeguimiento | 2-5s |
| Lista versiones | FactSeguimiento | < 1s |

Tras el refresh inicial, los visuales son rápidos porque VertiPaq tiene todo
en memoria.
