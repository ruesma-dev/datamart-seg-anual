<!-- progress/impl_F-073.md -->
# F-073 · Informe de implementación

Rama `feature/F-073-tablas-nuevas-y-enriquecimiento`. Rigor `estandar`.
Spec: `specs/F-073-tablas-nuevas-y-enriquecimiento/` (29 requisitos, 21 tareas).

## T1 · Los nombres de columna, MEDIDOS (2026-09-10, solo lectura)

Medidos con el cliente del ETL (`PostgresClient.filas_solo_lectura`, transacción
`READ ONLY`): el MCP no lee `raw`.

### `raw.conest` (19 columnas)

El tipo de documento es **`tip`** (integer), el código del estado **`est`**
(integer) y el nombre **`res`** (varchar). Hay además un `cod` de texto (`EST`,
`ECU`, `TER`) que **no** es por donde se une: `con.est` casa contra
`conest.est`. `tip = 42` da las **14** filas de estado de obra: `EN ESTUDIO`
(1), `EN CURSO` (15), `TERMINADA` (19), `CERRADA` (25), `PLANTILLA` (999)…

### `raw.auxefp` (15 columnas) — la contradicción, resuelta

`tables_sigrid.yaml` decía `est` y el informe de bloque decía `res`. **Gana
`res`**, medido sobre las 10 filas: `res` trae `CHEQUE`, `EFECTIVO`, `PAGARÉ`,
`TRANSFERENCIA`, `LETRA`, `CONFIRMING / PAGARÉ`…, mientras que **`est` está
vacío ('') en 5 filas y NULL en las otras 5**. `cla` (integer) es la clase de
medio. `tables_sigrid.yaml` está equivocado y el SQL de F-073 usa `res`.

### `raw.auxpag` (14 columnas)

`cod`, `res` (nombre), **`formul`** (text, el plazo — R22), `efeide` (→
`auxefp.ide`).

### `raw.obr` — los campos que suenan a dirección

**SÍ son la dirección de la obra** (R8): `dir1` y `dir2` (varchar), `dircpo`
(varchar, código postal) y `dir` (text, dirección completa). **Son los ejes de
agrupación** (R10): `munide` y `proide` (integer), hacia `raw.auxmun` y
`raw.auxpro`. **NO lo son** (R9): `diride` es el director de obra, `perdir` su
persona de contacto y `entdiride` la dirección del cliente; y `dirtex` no se
publica porque no está en R8.

### `raw.cen` (70 columnas) y `raw.con`

`raw.cen` **no tiene `cod`, `res` ni `emp`**: salen de su `raw.con` (mismo
`ide`), que sí trae `emp`, `tip`, `cod`, `res` y `est`. `cen.obride` existe pero
**está a 0 en las 804 filas** (R3).

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

Porcentaje informado sobre las **921** obras (R12): `dir1` 305 (**33,1 %**),
`dir2` 47 (**5,1 %**), `codigo_postal` 303 (**32,9 %**), `direccion_completa`
272 (**29,5 %**), `municipio` y `municipio_id` 294 (**31,9 %**), `provincia` y
`provincia_id` 306 (**33,2 %**), `estado` 920 (**99,9 %**).

Los 294 `munide` y los 306 `proide` informados **resuelven todos** a nombre en
`auxmun` / `auxpro`: no hay identificador colgado.

Marcas (R13–R15), sobre las mismas 921: **728 con presupuesto**, **368 con plan
mensual**, **349 con hecho**; la diferencia plan/hecho son **19 obras y ninguna
al revés**, que es la contrapartida declarada de leer de `stg` (DA-1).

## Lo que cambia

**Nuevos**: `sql/maestro/04_centros_coste.sql` (R1–R5),
`sql/maestro/05_estados_documento.sql` (R19–R20),
`sql/compras/04_formas_pago.sql` (R21–R22) y tres ficheros de tests
(`test_f073_sql.py`, `_pipeline.py`, `_diccionario.py`, **133 tests**).

**Modificados**: `sql/maestro/01_obras.sql` (+11 columnas, 0 quitadas, cabecera
corregida); `build_maestros_step.py` (`SUB_PASOS` de módulo, 2 sub-pasos,
`depends_on` gana `build_stg`), `build_compras_step.py` (1 sub-paso) y `main.py`
(un comentario); `tests/test_f047_steps.py` y `tests/test_f047_nocturna.py` (sus
asertos sobre los sub-pasos y el DAG de `compras`/`maestro`);
`config/diccionario/{maestro,compras,00_global}.yaml` (3 fichas, 11 columnas,
versión 19, y el punto 3 de `R-FUENTE-QUE-GOBIERNA`); y los recuentos del
inventario en `specs/F-006-mcp-azure/design*.md` y `progress/current.md`
(142 / 852 / 57).

**NO tocados, con tripwire por `sha256`**: `sql/compras/01_documentos.sql`
(R23, F-067) y los dos ficheros del SELLO (R25); más el `rn = 1` de
`sql/stg/03_obras.sql` (R26).

## Fase RED · las trazas reales

Seis tandas, una por commit. Comando:
`python -m pytest tests/test_f073_<fichero>.py -q`.

**T3 · el puente (R1–R5)** — el SQL no existía:
```
E       AssertionError: SQL no encontrado: ...\sql\maestro\04_centros_coste.sql
FAILED tests/test_f073_sql.py::test_f073_r2_el_puente_cruza_por_empresa_y_codigo
FAILED tests/test_f073_sql.py::test_f073_r3_no_usa_cen_obride
FAILED tests/test_f073_sql.py::test_f073_r4_el_lateral_es_left_join_y_no_join
FAILED tests/test_f073_sql.py::test_f073_r5_el_lateral_no_puede_multiplicar_filas
17 failed in 0.58s
```

**T5 · la dimensión de estados (R19–R20)**:
```
FAILED tests/test_f073_sql.py::test_f073_r19_no_filtra_por_tipo_de_documento
9 failed, 17 passed in 0.59s
```

**T7 · la obra enriquecida (R7–R18)**:
```
FAILED tests/test_f073_sql.py::test_f073_r7_la_obra_usa_el_vocabulario_de_proveedores[dir1]
FAILED tests/test_f073_sql.py::test_f073_r14_cada_marca_es_un_exists_sobre_su_tabla_de_stg[tiene_presupuesto-stg.presupuesto]
23 failed, 41 passed in 0.81s
```

**T9 · formas de pago (R21–R22)**. Los tripwires de R23, R25 y R26 salieron en
verde desde el primer momento:
```
FAILED tests/test_f073_sql.py::test_f073_r21_el_nombre_del_medio_sale_de_res_y_no_de_est
FAILED tests/test_f073_sql.py::test_f073_r22_el_plazo_se_publica_verbatim
14 failed, 71 passed in 0.63s
```

**T11 · los steps (R27)**:
```
FAILED tests/test_f073_pipeline.py::test_f073_r27_build_maestros_declara_que_lee_de_stg
10 failed, 2 passed, 20 warnings in 1.36s
```

**T13 · el diccionario (R6, R11, R12, R15, R20, R22, R28)**:
```
FAILED tests/test_f073_diccionario.py::test_f073_r6_la_ficha_del_puente_declara_cuantos_resuelven
FAILED tests/test_f073_diccionario.py::test_f073_r28_el_diccionario_sube_a_la_version_19
32 failed in 1.08s
```

**EL DEFECTO QUE LOS 85 TESTS NO VEÍAN, y su RED en copia aislada.**
`CREATE OR REPLACE VIEW` de PostgreSQL **solo admite columnas nuevas AL FINAL**.
`estado` estaba intercalada entre `estado_id` y `fecha_alta` —donde mejor se
lee—, así que la nocturna habría muerto con «cannot change name of view column».
Los tests de texto daban verde porque solo miraban PRESENCIA. Se añade
`test_f073_r18_las_columnas_de_siempre_van_primero_y_en_su_orden` y su fase RED
se hace **sobre una copia del fichero en el scratchpad, nunca sobre el árbol**:
```
AssertionError: las columnas que la vista ya publicaba van primero y en el
mismo orden; lo nuevo se anade DETRAS (R18)
  publicadas: ['obra_id', 'codigo_obra', 'nombre_obra', 'estado_id', 'estado',
               'fecha_alta', 'fecha_baja', 'es_activa', ...]
  de siempre: ['obra_id', 'codigo_obra', 'nombre_obra', 'estado_id',
               'fecha_alta', 'fecha_baja', 'es_activa', ...]
```

## Decisiones y desviaciones

1. **El cuerpo de las cuatro vistas se ejecutó contra la base antes de darlas
   por buenas**, como `SELECT COUNT(*) FROM (<cuerpo>) x` en transacción
   `READ ONLY`: **804, 193, 921 y 69 filas**. Crear la vista es escritura y no
   se hizo; leerla no.
2. **`build_maestros` saca sus sub-pasos a `SUB_PASOS` de módulo.** No estaba
   en el diseño, pero `build_compras` ya lo hacía: con la lista dentro de
   `run()` no se puede comprobar sin ejecutar el step que cada `.sql` está
   declarado.
3. **Tripwires por `sha256` para R23 y R25**, con el idioma de
   `tests/test_f042_sql.py`. Un test que dijera «`01_documentos.sql` no menciona
   `auxpag`» sería una mina el día que F-067 haga su cableado legítimo.
4. **Dos frases vetadas por nombre en todo el fichero** (`obride`, R3; «las
   obras no tienen dirección», R11): ni la nota que corrige el error puede
   citarlas.
5. **La relación `estados_documento → obras` es `N:N`, no `1:N`**, y lo cazó
   el validador del diccionario: la clave del catálogo es
   `(tipo_documento, estado_id)`, así que unir por `estado_id` a secas
   multiplica la obra por los 29 tipos. La ficha manda filtrar el 42 antes.
6. **Papeleo derivado que no estaba en `tasks.md`** y sin el que `init.sh` no
   cierra: los recuentos del inventario, la lista de ficheros de `compras` en
   `tests/test_f047_steps.py`, el aserto de `test_f047_nocturna.py` que decía
   que los TRES pasos raw-only dependen solo de la ingesta —`build_maestros`
   dejó de ser uno—, y el punto 3 de `R-FUENTE-QUE-GOBIERNA`, que se DERIVA del
   SQL y ahora declara `auxefp.res`, `auxpag.cod/res` y `conest.cod/res`.

## Lo encontrado que NO se arregla aquí

* **`config/tables_sigrid.yaml` miente sobre `auxefp`**: dice que el nombre del
  medio de pago está en `est`, vacío o nulo en las 10 filas; está en `res`.
  **No se corrige**: tocar ese YAML es tocar la ingesta. Queda escrito en la
  ficha, en la cabecera del SQL y en un test que lo veta por nombre.
* **Una obra de 921 tiene un `con.est` sin fila en `conest` para el tipo 42** y
  sale con `estado` a NULL. Es del origen; la ficha lo declara.
* **`retenciones.movimientos.obra_id` sigue trayendo centros de coste.**
  Arreglarlo es F-045: aquí se publica el puente y se anota la prueba (T19).

## Evidencias

| Evidencia | Valor real |
|---|---|
| **Tests ejecutados** | **4.366 pasados**, 171 saltados, 0 fallidos |
| **Cobertura de las líneas cambiadas** | **93,6 %** (791/845, umbral 80 %) |
| **Tiempo de la suite** | **777,8 s** (12 min 57 s) con medición de cobertura; **412,8 s** sin ella (la línea base de la campaña, con `-x`) |
| **Mutantes** | 288 generados, **20 evaluados** (muestreo del nivel `estandar`, semilla `20260820`), **11 muertos, 9 supervivientes**, 0 timeouts |
| **Workers de la campaña** | **1** (en serie). Coste por mutante = 5.470,2 × 1 ÷ 20 = **273,5 s** |
| `bash harness/init.sh` | **exit 0** — «ENTORNO LISTO» |

**LOS NUEVE SUPERVIVIENTES ESTÁN ANALIZADOS UNO A UNO** en
`progress/mutacion_F-073.md`, ninguno en `PENDIENTE`, y el titular está ahí con
su aritmética: **ninguno cae en código de F-073**. El alcance se calcula contra
el punto de fork con `dev` y arrastra 3.617 líneas de seis features; las de
F-073 son 87, el **2,4 %**. Siete son líneas de `PostgresClient` que la suite
offline no alcanza por diseño, una es un assert que le falta a `ventana_sql` y
la novena es **F-077**, ya fichada. Allí está también el comando y el coste
medido (~1 h 50 min) de la campaña acotada a los dos ficheros de F-073, que
**no se lanzó**, y el motivo de ir en serie: la paralela crea worktrees desde
`HEAD` y hay otra sesión con cambios sin commitear en este árbol.
