<!-- specs/F-073-tablas-nuevas-y-enriquecimiento/design.md -->
# F-073 · Diseño técnico

## 1 · La frontera con las ocho features ya fichadas, y por qué

El censo (`progress/explore_F-072_catalogo.md` §5) propone diez
construcciones y enruta ocho a fichas existentes. La regla que aplico:

> **F-073 publica DIMENSIONES y el MAESTRO DE OBRA. La feature de dominio
> publica su HECHO y hace el CABLEADO.**

Una dimensión no es de nadie: `raw` está fuera de los ocho esquemas que el
MCP lee, así que un catálogo de 69 o 193 filas que traduce un número no
existe para Negocio hasta que alguien lo publica, y publicarlo cuesta media
hora. El hecho sí es de alguien, y el `acceptance` de esa ficha lo dice con
todas las letras. Caso por caso:

| Construcción | Va a | Por qué |
|---|---|---|
| Puente centro de coste → obra | **F-073** | Ninguna ficha lo reclama y tres lo necesitan (F-045, F-061, F-058). 40 líneas de SQL, 1:1 verificado |
| Dirección y marcas de la obra | **F-073** | Herencia de F-071, ya decidida por el humano |
| `conest` como **dimensión** | **F-073** | No es de compras: nombra estados de obra (42), contrato (44), factura (15), comparativo (46) y oferta (12). Además mata una duplicación real: la ficha de `maestro.obras.estado_id` **copia a mano** 14 nombres medidos el 02-sep de una tabla que sí se ingiere |
| `conest` **cableado a compras** | F-067 | Su `acceptance` 1 dice literalmente «`compras.contratos` publica el estado actual con su nombre (`conest`)» |
| `auxpag`+`auxefp` como **dimensión** | **F-073** | La forma de pago no existe en ninguna capa procesada, y la necesitan F-067 **y** F-037 por separado |
| `auxpag` **cableado a contratos y facturas** | F-067 | Misma `acceptance` 1 («forma de pago y retención»), y toca `compras/01_documentos.sql`, que F-067 reescribe entera |
| `hmores`+`auxhor`, `apa`, `apu`/`asi`/`cua`, comparativos, firmas, `ctrrec`, `dnc` | F-057, F-061, F-058, F-056, F-038, F-055, F-067 | Son hechos, y cada uno ya tiene ficha con criterios propios |

**Límite de microservicio**: nada de esto se sale del ETL del datamart. Todo
lee de `raw`/`stg` de esta base y escribe en esta base.

## 2 · Ficheros a crear

- `etl_sigrid/infrastructure/postgres/sql/maestro/04_centros_coste.sql`
  → vista `maestro.centros_coste` (R1–R6).
- `etl_sigrid/infrastructure/postgres/sql/maestro/05_estados_documento.sql`
  → vista `maestro.estados_documento` (R19–R20).
- `etl_sigrid/infrastructure/postgres/sql/compras/04_formas_pago.sql`
  → vista `compras.formas_pago` (R21–R22).
- `tests/test_f073_sql.py` — asserts sobre el TEXTO de los tres SQL nuevos y
  del de obras. Patrón ya establecido en `tests/test_f052_sql.py` y
  `tests/test_f042_sql.py`: el SQL no se puede ejecutar aquí porque escribe
  en un Postgres compartido con producción.
- `tests/test_f073_pipeline.py` — sub-pasos y `depends_on` de los dos steps.
- `tests/test_f073_diccionario.py` — fichas, versión y cobertura de columnas.

## 3 · Ficheros a modificar

- `.../sql/maestro/01_obras.sql` — añade dirección (R7–R11), `municipio_id` /
  `provincia_id` (R10), `tiene_presupuesto` / `tiene_seguimiento` (R13–R14) y
  `estado` (R16). **Ninguna columna actual se quita ni se renombra** (R18).
  Se corrige además su cabecera, que hoy afirma «SIN dirección … las obras no
  tienen dirección propia»: es falso y lo desmiente el censo.
- `etl_sigrid/application/steps/build_maestros_step.py` — dos sub-pasos
  nuevos (`centros_coste`, `estados_documento`) y `depends_on` pasa de
  `["ingest_raw"]` a `["ingest_raw", "build_stg"]` (R27). Se corrige el
  docstring, que aún dice «solo lee de raw.*» y «NO forma parte de run-all»
  (F-047 lo metió).
- `etl_sigrid/application/steps/build_compras_step.py` — sub-paso
  `formas_pago`.
- `config/diccionario/maestro.yaml` — fichas de `maestro.centros_coste` y
  `maestro.estados_documento`, y columnas nuevas de `maestro.obras`.
- `config/diccionario/compras.yaml` — ficha de `compras.formas_pago`.
- `config/diccionario/00_global.yaml` — `version: 18` → `19` y su nota.

## 4 · Ficheros que NO se tocan (los que tientan)

- `sql/stg/06_presupuesto.sql` y `sql/stg/08_plan_mensual.sql` — **son el
  SELLO** (`FICHEROS_DEL_SELLO` en `build_stg_step.py`). Cambiar una coma
  fuerza la reconstrucción de las 921 obras la noche siguiente. F-073 los
  **lee desde una vista**, y leer no cambia su texto (R25).
- `sql/stg/03_obras.sql` — el desempate `rn = 1` es F-053 (R26).
- `sql/compras/01_documentos.sql`, `02_fact_linea.sql`, `03_views.sql` — son
  de F-067 (R23).
- `sql/retenciones/**` — arreglar `movimientos.obra_id` con el puente es
  F-045. Aquí solo se publica el puente.
- `sql/mart/**` — ver la trampa de §6.
- `config/tables_sigrid.yaml` — las cinco tablas de origen que hacen falta
  (`cen`, `obr`, `auxmun`, `auxpro`, `conest`, `auxpag`, `auxefp`) **ya se
  ingieren**. No hay ingesta nueva en esta feature.

## 5 · El SQL, capa por capa

### `maestro.centros_coste` (04, esquema `maestro`)

```sql
CREATE OR REPLACE VIEW maestro.centros_coste AS
SELECT  n.ide AS centro_coste_id, cc.cod AS codigo_centro,
        cc.res AS nombre_centro, cc.emp AS empresa,
        o.obra_id, o.codigo_obra, o.nombre_obra
FROM       raw.cen n
JOIN       raw.con cc ON cc.ide = n.ide
LEFT JOIN  LATERAL (
    SELECT co.ide AS obra_id, co.cod AS codigo_obra, co.res AS nombre_obra
    FROM   raw.con co
    JOIN   raw.obr ob ON ob.ide = co.ide
    WHERE  co.emp = cc.emp AND co.cod = cc.cod
    ORDER  BY co.ide
    LIMIT  1
) o ON TRUE;
```

Tres cosas y las tres son requisito. **`LEFT JOIN LATERAL`** y no `JOIN`:
los 121 centros que no son obra se publican con `obra_id` NULL (R4).
**`LIMIT 1` con `ORDER BY` declarado**: hoy el puente es 1:1 sobre 683 pares
sin ambigüedad, pero la vista no puede multiplicar filas el día que el origen
deje de serlo (R5). **`JOIN raw.obr`** dentro del lateral: es lo que descarta
la propia fila `con` del centro, que comparte empresa y código pero no tiene
ficha de obra.

### `maestro.estados_documento` (05, esquema `maestro`)

Proyección directa de `raw.conest`: identificador, tipo de documento, código
del estado y nombre. **Sin filtrar por tipo** (R19: las 193 filas).

### `maestro.obras` (01, esquema `maestro`, modificado)

Se añaden, sobre el `SELECT` actual:

- **Dirección**: `o.dir1`, `o.dir2`, `o.dircpo AS codigo_postal`,
  `o.dir AS direccion_completa`, más `LEFT JOIN raw.auxmun mu ON
  mu.ide = NULLIF(o.munide, 0)` y `LEFT JOIN raw.auxpro pr ON
  pr.ide = NULLIF(o.proide, 0)` para `municipio` / `provincia` y sus dos
  `_id`. Mismo vocabulario y mismo patrón que `02_proveedores.sql`.
- **Marcas**: `EXISTS (SELECT 1 FROM stg.presupuesto s WHERE s.obra_id =
  c.ide)` y su gemela sobre `stg.plan_mensual`. `EXISTS` y no `COUNT`: son
  921 sondas por índice, medidas en 471 ms y 33 ms el 2026-09-10.
- **Estado**: `LEFT JOIN` a `raw.conest` con el tipo de obra, resuelto con
  `DISTINCT ON` o `LATERAL … LIMIT 1` para que no multiplique (R17).

### `compras.formas_pago` (04, esquema `compras`)

`raw.auxpag` + `LEFT JOIN raw.auxefp`. El plazo va **verbatim** como
`plazo_formula` (R22).

### Los nombres exactos de columna se MIDEN, no se suponen

`raw.conest` (columna de tipo, de código de estado y de nombre),
`raw.auxefp` (el nombre del medio: `tables_sigrid.yaml` dice que es `est`, y
el informe de bloque dice `res` — **se contradicen**) y los ocho campos de
dirección de `raw.obr`. La T1 los mide en solo lectura contra la base y los
deja escritos en `progress/impl_F-073.md` **antes** de escribir SQL. `raw` no
es consultable por el MCP: se usa el cliente del ETL, y **solo lecturas**.

## 6 · Riesgos y decisiones

- **DA-1 · Las marcas leen de `stg`, no de `mart`. Es la decisión más
  importante del diseño.** `mart/01_ddl.sql` hace
  `DROP TABLE IF EXISTS mart.fact_seguimiento_mensual CASCADE`, así que una
  vista de `maestro` que lo referenciara **la destruiría la nocturna
  siguiente** — el incidente literal de F-047 con
  `cierre.v_pbi_planif_vs_real`, y agravado: `build_maestros` no es
  dependencia de nadie, así que una noche en que falle dejaría
  `maestro.obras` **inexistente**. `stg.presupuesto` y `stg.plan_mensual` se
  crean con `CREATE TABLE IF NOT EXISTS` y **no se dropean nunca**.
  Contrapartida declarada: `tiene_seguimiento` es superconjunto del hecho en
  19 obras (R15), y la ficha lo dice.
- **DA-2 · Alternativa descartada: calcular las marcas desde `raw`**
  (`obrparpre`, `obrfasamb`) para que `maestro` siguiera siendo raw-only.
  Responde otra pregunta: el humano quiere distinguir la obra que **el
  datamart** no puede contar, no la que Sigrid no tiene.
- **DA-3 · Coste de `depends_on: build_stg`.** Si `build_stg` falla, el
  orquestador marca `build_maestros` como SKIPPED, cosa que hoy no pasa. Es
  aceptable porque los cuatro objetos de `maestro` son **vistas**: no
  materializan nada y saltarlas deja exactamente la definición de ayer, que
  es idéntica. A cambio, un `build-maestros` contra una base sin `stg`
  reventaría al crear la vista, y el DAG es donde eso se declara.
- **DA-4 · Alternativa descartada: `maestro.obras` consumiendo
  `maestro.estados_documento`.** Sería una vista sobre vista dentro del mismo
  esquema y obligaría a invertir la numeración de ficheros (`01` leería de
  `05`). `01_obras.sql` lee `raw.conest` directamente con el tipo de obra; la
  duplicación es un predicado, no lógica.
- **DA-5 · No se parsea `auxpag.formul` a días.** `30 450R` es un valor real
  del catálogo. Publicar un `dias_pago` numérico sería inventar precisión;
  quien la necesite, la decide en F-067 o F-037 con el criterio escrito.
- **DA-6 · La dirección se publica con un tercio de cobertura.** Es la
  corrección que mató a F-071 y aquí se resuelve al revés: se publica y **se
  declara el porcentaje**, y el criterio de aceptación no exige cobertura
  (R11, R12). Para dos de cada tres obras, «no consta» es la respuesta
  correcta y la ficha lo dice.
- **DA-7 · Permisos.** No hace falta tocar nada: `stg` ya está en
  `DEFAULT_CONSUMPTION_SCHEMAS`, y además una vista de PostgreSQL comprueba
  permisos como su **dueño**, no como quien consulta.
- **Riesgo · Multiplicación de filas.** Los tres `LEFT JOIN` nuevos de
  `maestro.obras` (auxmun, auxpro, conest) y el lateral del puente son los
  únicos puntos por donde el grano se puede romper. Por eso R5, R17 y la
  verificación MANUAL de recuentos.
- **Riesgo · Campaña de mutación.** El código Python que cambia son dos
  listas de sub-pasos y un `depends_on`: la campaña puede dar pocos mutantes
  o ninguno. Si da cero, se hace la **campaña manual** con la tabla fila a
  fila que exige `CHECKPOINTS.md` (C4 bis), con el texto exacto original →
  mutado. Omitirla no es una opción.

## 7 · Verificaciones que solo puede hacer el humano (BBDD real)

Van en `tasks.md` como `MANUAL (humano)` y en `progress/current.md` con su
comando exacto: recuentos de las tres vistas nuevas (804 / 683 / 193 / 69),
`maestro.obras` en **921 filas** y sin columnas perdidas, porcentaje
informado de cada columna nueva, `check-declarados` y `check-diccionario` en
verde, y la prueba de que el puente resuelve F-045: los **261 de 261**
valores de `retenciones.movimientos.obra_id` casan contra
`maestro.centros_coste.centro_coste_id`.
