> # ⛔ SPEC RETIRADA el 2026-09-09, ANTES DE IMPLEMENTAR NADA
>
> El humano paró F-071 al leer esta spec: **«no vamos a borrar nada de
> momento, vamos a seguir dejando todo. Quitamos esta feature.»** La purga
> nocturna (R20) y el acotado del censo (R19) **no se hacen**. F-071 ya no
> existe en `harness/features.json`.
>
> **Esta carpeta se conserva solo por lo que costó medir**, y esa evidencia
> pasa a alimentar **F-072** (el censo semántico) y **F-073** (las tablas
> nuevas y el enriquecimiento): las cifras del §1 de `design.md`, que tres de
> los ocho campos de dirección no son dirección de la obra, y que el municipio
> y la provincia viven en `raw.auxmun` y `raw.auxpro`. **Lo que sobrevive es
> el enriquecimiento —la dirección y las marcas— sin borrar ni filtrar nada.**
>
> No implementes desde aquí. Ver `progress/current.md`.

<!-- specs/F-071-obras-sin-datos/design.md -->
# F-071 · Diseño

Aditivo en la capa de consumo, restrictivo solo en el censo interno de la
ventana. Nada de lo que hoy lee Power BI pierde una fila ni una columna.

## 1 · Lo medido (Azure, solo lectura, 2026-09-09)

Las cifras están en `requirements.md`. Tres hallazgos que **cambian el
diseño** respecto de lo que suponía la ficha de la feature:

**H1 · El censo deja huérfanas 472.890 filas.** `06_presupuesto.sql` y
`08_plan_mensual.sql` construyen filtrando **solo por la lista de obras del
censo**, sin unir a `stg.obras`. Hoy hay **338** fichas del censo fuera de
`stg.obras`, **230** con filas en `stg.presupuesto` (390.028) y **19** en
`stg.plan_mensual` (82.862). Acotar el censo sin más las congelaría para
siempre: nadie las borraría y nadie las rehacía. Por eso R20 (la purga).

**H2 · De los ocho campos que cita la ficha, solo cuatro son dirección de la
obra.** Verificado en `azure-apps/sigrid_tablas.md`, ficha de la tabla `obr`:

| campo | qué es de verdad | ¿se publica? |
|---|---|---|
| `dir1`, `dir2`, `dircpo`, `dir` | dirección propia de la obra | sí (sujeto a R10) |
| `munide` → `auxmun.res` | **Municipio** | sí — eje de agrupación |
| `proide` → `auxpro.res` | **Provincia** | sí — eje de agrupación |
| `paiide` → `auxpai` | País | no: se mide, se espera constante |
| `dirtex` | Observaciones de la dirección | no: texto libre |
| `diride` | **Director de obra** (índice a `ref`) | no: no es una dirección |
| `perdir` | **Persona de contacto del director** | no: no es una dirección |
| `entdiride` | **Dirección del CLIENTE** (índice a `condir`) | no: otra cosa |

`munide` y `proide` **no estaban en la lista de ocho de la ficha** y son
justo los dos ejes de agrupación que el humano pide. Tres de los ocho
—`diride`, `perdir`, `entdiride`— no son la dirección de la obra.

**H3 · La consulta es barata.** El recuento de las tres marcas sobre las 583
obras con `EXISTS` tardó **183 ms** (índices `idx_pres_obra_amb`,
`idx_plan_mensual_obra_amb`, `idx_fact_obra_mes`). No hay riesgo de repetir el
problema de `mart.v_pbi_cp_tipologia` (F-034): las vistas nuevas son baratas.

## 2 · Decisiones

- **DA-1 · Las marcas se calculan en vista, no se materializan.** Una columna
  `BOOLEAN` en `stg.obras` se escribiría en `03_obras.sql`, que corre **antes**
  de `06_presupuesto.sql` y `08_plan_mensual.sql`: nacería con la foto de la
  noche anterior. En vista siempre es verdad y cuesta 183 ms.
- **DA-2 · `v_pbi_dim_obra` NO pasa a depender de `mart.fact_seguimiento_mensual`.**
  Sus dos marcas salen de `stg`. Hoy la dimensión sobrevive a un `build_mart`
  fallido; colgarla del hecho la tumbaría con él. La marca que sí mira el hecho
  vive en la vista nueva, que es de `mart` y puede depender de `mart`.
- **DA-3 · La superficie nueva NO se llama `v_pbi_*`.** `mart.v_obras_con_datos`:
  el prefijo `v_pbi_` es el contrato de Power BI y este objeto es para la IA.
  Así «nada de las `v_pbi_*` cambia» es literalmente cierto salvo por columnas
  añadidas, que Power BI con Import ignora.
- **DA-4 · Los nombres de dirección son los de `maestro.proveedores`**:
  `dir1`, `dir2`, `codigo_postal`, `municipio`, `provincia`,
  `direccion_completa`. No se inventa un segundo vocabulario para lo mismo.
- **DA-5 · `direccion_completa` es una sola cosa** (R8): `obr.dir` si viene
  informado, y si no la composición de las líneas. En `maestro.proveedores`
  esa columna es el `condir.dir` crudo; aquí se le añade el respaldo porque
  `obr.dir` es «Texto ilimitado» y puede venir vacío con `dir1` lleno. La ficha
  lo dice con esas palabras.
- **DA-6 · La dirección sí se materializa en `stg.obras`.** Es un atributo
  estable de la obra, `03_obras.sql` ya lee `raw.obr`, y así la dimensión y la
  vista nueva no vuelven a `raw` (que el MCP no puede leer). `maestro.obras`
  la compone aparte porque es otro universo (921 fichas) y ya lee `raw.obr`.
- **DA-7 · El censo se acota por `JOIN stg.obras`, no por lista de exclusiones.**
  Es el criterio que pide la `acceptance` y el único objetivo: lo que no llega
  al universo del seguimiento no se reprocesa. Reproduce los filtros de
  `03_obras.sql` sin duplicarlos.
- **DA-8 · La purga (R20) va en un fichero propio y corre cada noche**, no
  como limpieza de una vez. Un `DELETE` idempotente inmediatamente después de
  reconstruir `stg.obras` es autosostenible: el día que una obra salga del
  universo, sus filas se van con ella.
- **DA-9 · Las 234 obras de `stg.obras` sin hechos siguen entrando por
  `sin_filas`** (R22). Ahí `domain/ventana.py:472` tiene razón: una obra a
  medio construir se completa. Sacarlas es otra feature, con otra evidencia.
- **Descartado · borrar las obras vacías.** Ya lo descartó el humano: son obras
  reales y `raw` se reingiere entero cada noche (R34).
- **Descartado · marcas en `maestro.obras`.** Sería una tercera fuente de la
  misma verdad. El enrutado de la regla dura lleva a `mart`.

## 3 · Ficheros a crear

| ruta | qué |
|---|---|
| `etl_sigrid/infrastructure/postgres/sql/stg/03b_purga_obras_fuera.sql` | `DELETE` idempotente de `stg.presupuesto` y `stg.plan_mensual` para `obra_id NOT IN (SELECT obra_id FROM stg.obras)` (R20) |
| `etl_sigrid/infrastructure/postgres/sql/mart/07_view_obras_con_datos.sql` | `CREATE OR REPLACE VIEW mart.v_obras_con_datos` (R2) |
| `tests/test_f071_obras_sin_datos.py` | tests de R1–R8, R12, R19, R20, R22 |
| `specs/F-071-obras-sin-datos/mediciones.md` | la medición de dirección (R9–R11) y el antes/después del censo (R21) |

## 4 · Ficheros a modificar

| ruta | qué cambia |
|---|---|
| `sql/stg/01_ddl.sql` | seis `ALTER TABLE stg.obras ADD COLUMN IF NOT EXISTS` (R6) |
| `sql/stg/03_obras.sql` | el `INSERT` añade las seis columnas leyendo `raw.obr` + `LEFT JOIN raw.auxmun` / `raw.auxpro` (R6, R8) |
| `sql/mart/05_views_powerbi.sql` | `v_pbi_dim_obra` gana dos marcas y seis columnas de dirección. **Solo añade** (R1, R4, R7) |
| `sql/maestro/01_obras.sql` | gana las seis columnas de dirección y se corrige su cabecera (R7, R14) |
| `application/steps/build_stg_step.py` | sub-paso nuevo `purga_obras_fuera` con `03b`, entre `build_obras` y `build_partidas` |
| `application/steps/build_mart_step.py` | sub-paso nuevo con `07_view_obras_con_datos.sql`, el último |
| `infrastructure/postgres/postgres_client.py` | `SQL_ESTADO_OBRAS` (línea 215) gana `JOIN stg.obras so ON so.obra_id = c.ide` (R19) |
| `config/diccionario/mart.yaml` | ficha de `v_pbi_dim_obra` ampliada + ficha nueva de `v_obras_con_datos` |
| `config/diccionario/stg.yaml`, `maestro.yaml` | fichas de `obras` con las columnas de dirección y su % informado |
| `config/diccionario/00_global.yaml` | regla `R-OBRA-SIN-DATOS`, referencia cruzada en `R-UNIVERSO-OBRA`, `version: 17` |
| `tests/test_f006_fichas.py:1347` | la aserción sobre `R-UNIVERSO-OBRA` (hoy exige «919», el universo real son 921) |
| `docs/ARCHITECTURE.md` | el censo de la ventana pasa de 920 fichas a 583 obras |
| `../azure-apps/datamart_seg_anual.md` | «Qué expone»: la vista nueva y la dirección; y las cifras del censo |

## 5 · Ficheros que NO se tocan

- `sql/mart/01_ddl.sql`, `02_build_fact.sql`, `03_agg_categoria.sql`: el hecho
  no cambia ni una fila (R5).
- `sql/stg/06_presupuesto.sql` y `08_plan_mensual.sql`: **son los dos ficheros
  del sello** (`FICHEROS_DEL_SELLO`). Tocarlos forzaría una reconstrucción
  completa de todas las obras la noche siguiente. Su filtrado por lista de
  obras se queda como está; el acotado ocurre aguas arriba, en el censo.
- `etl_sigrid/domain/ventana.py`: el criterio de la ventana no cambia (R22);
  cambia **qué se le da de comer**.
- `sql/cierre/**`, `sql/compras/**`, `sql/retenciones/**`.
- `sql/stg/03_obras.sql` en su `ROW_NUMBER() ... WHERE rn = 1`: es F-053.

## 6 · SQL nuevo, en su capa

**`stg/03b_purga_obras_fuera.sql`** (capa `stg`, corre dentro de `build_stg`
justo después de `03_obras.sql`, que deja `stg.obras` recién reconstruida):

```sql
DELETE FROM stg.presupuesto  p  WHERE NOT EXISTS (SELECT 1 FROM stg.obras o WHERE o.obra_id = p.obra_id);
DELETE FROM stg.plan_mensual pm WHERE NOT EXISTS (SELECT 1 FROM stg.obras o WHERE o.obra_id = pm.obra_id);
```

Va **por índice** (`idx_pres_obra_amb`, `idx_plan_mensual_obra_amb`), como el
borrado derivado de F-025. La primera noche borra ~472.890 filas; las
siguientes, cero o casi.

**`mart/07_view_obras_con_datos.sql`** (capa `mart`, la última del build, para
que `05_views_powerbi.sql` ya haya recreado la dimensión de la que cuelga):

```sql
CREATE OR REPLACE VIEW mart.v_obras_con_datos AS
SELECT d.* FROM mart.v_pbi_dim_obra d
WHERE EXISTS (SELECT 1 FROM mart.fact_seguimiento_mensual f WHERE f.obra_id = d.obra_id);
```

Cuelga de la dimensión a propósito: una sola definición de la dirección y de
las marcas. `05_views_powerbi.sql` hace `DROP VIEW ... CASCADE` de la
dimensión, así que esta vista se recrea después en la misma noche; el orden de
los sub-pasos es lo que lo garantiza y hay un test que lo fija.

## 7 · Cómo se mide la dirección (R9), que no se puede medir desde aquí

**`raw` no es consultable por el MCP** («El esquema 'raw' está fuera del ámbito
autorizado»), así que la medición es una tarea, no un dato de esta spec. El SQL
exacto, que es una **lectura** contra Azure y por tanto está permitido:

```sql
SELECT count(*) AS obras,
       count(*) FILTER (WHERE NULLIF(TRIM(o.dir1),   '') IS NOT NULL) AS con_dir1,
       count(*) FILTER (WHERE NULLIF(TRIM(o.dir2),   '') IS NOT NULL) AS con_dir2,
       count(*) FILTER (WHERE NULLIF(TRIM(o.dircpo), '') IS NOT NULL) AS con_cp,
       count(*) FILTER (WHERE NULLIF(o.munide, 0)       IS NOT NULL)  AS con_municipio,
       count(*) FILTER (WHERE NULLIF(o.proide, 0)       IS NOT NULL)  AS con_provincia,
       count(*) FILTER (WHERE NULLIF(o.paiide, 0)       IS NOT NULL)  AS con_pais,
       count(*) FILTER (WHERE NULLIF(TRIM(o.dir),    '') IS NOT NULL) AS con_dir_completa
FROM raw.obr o JOIN stg.obras so ON so.obra_id = o.ide;
```

Se lanza con el cliente del proyecto (`PostgresClient.connection()`) desde un
script de un solo uso en `scripts/`, o se pide al humano por `psql`. La misma
consulta sin el `JOIN` da el universo de 921 fichas. **Umbral de publicación
(R10): un tercio de las 583**, es decir 195 obras. Lo que no llegue, no se
publica y se dice por qué. Si `dir1` no llega al umbral, R13: no se publica
dirección y el diccionario declara que el dato no existe en el origen —lo que
convertiría la ampliación del 2026-09-08 en un «no se puede» documentado, que
es un resultado válido y hay que llevárselo al humano antes de seguir.

## 8 · Riesgos

- **El desempate `rn=1` (F-053) elige la ficha vacía.** Esta feature marca esas
  obras como «sin datos» y con esta feature dentro **quedan más visibles**, no
  menos: pasan a ser contables. No se toca el desempate. Si F-053 lo cambia
  después, las marcas se recalculan solas porque son vistas.
- **La purga escribe contra el Postgres compartido.** No la ejecuta un agente:
  la ejecuta la nocturna. La verificación desde el puesto es de solo lectura.
- **El censo acotado deja de vigilar 338 fichas.** Es lo que se busca, pero
  significa que si una obra sale de `stg.obras` por un cambio de Sigrid,
  desaparece del censo sin ruido. La purga (DA-8) es lo que hace que eso sea
  limpio en vez de silencioso: sus filas se borran, no se quedan mintiendo.
- **Límite de microservicio**: nada de esto sale del ETL del datamart. Lo que
  se sale —borrar plantillas en Sigrid— ya está descartado en la ficha.
