<!-- specs/F-025-ventana-negocio-build/design.md -->
# F-025 · Acotar el build por ventana de negocio — Diseño técnico

> Se lee **después** de `requirements.md`. El orden de los bloques A / B es
> normativo: el bloque B no se escribe hasta que Negocio firme **DA-1** sobre
> el informe de R5.

## 1 · El diagnóstico, antes del diseño

### 1.1 Dónde se va el tiempo (dato, no estimación)

Carga completa en Azure, 2026-08-18, 165 min: ingesta 33 min (20 %),
`build_stg` 111 min (**67 %**), `build_mart` 21 min (13 %).

Y el desglose fino, medido en el T12 de F-019 sobre el mismo servidor
(`Standard_B1ms`, `psql-albaranes-rs9k2`):

| Sub-paso | Duración medida | Filas |
|---|---|---|
| `build_stg.build_plan_mensual` (60 tramos) | **5.993,9 s ≈ 100 min** | 29.398.375 |
| `build_stg.build_presupuesto` | 1.380 s ≈ 23 min | 13.759.593 |
| `build_mart.build_fact` | 1.168 s ≈ 19 min | 5.287.299 |
| `build_mart.agg_categoria` | resto de los 21 min | 24.591 |

Cada tramo deja su fila `build_stg.build_plan_mensual.tramo_NN` en
`_meta.etl_runs`, así que **el reparto por obra ya está guardado** y el bloque
A no necesita ejecutar ninguna carga nueva para medirlo: le basta con cruzar
esas duraciones con el peso por obra que devuelve `SQL_PESOS_PLAN_MENSUAL`.

**La hipótesis a validar, dicha con precisión:** de esos ~100 min, la parte que
corresponde a obras terminadas hace años se está gastando cada noche en
recalcular un resultado idéntico al de anoche. Si esa parte es el 70 %, el
build baja de 100 a ~30 min y la carga completa de 165 a ~95. Si es el 20 %, no
compensa el riesgo. **R1 y R2 lo miden antes de tocar una línea.**

### 1.2 Por qué la ventana solo puede ser un conjunto de obras

De F-019, y es una restricción dura, no una preferencia:

- Ninguna ventana analítica de `sql/stg/08_plan_mensual.sql` cruza obras: todas
  particionan por `presupuesto_id` o por `(obra_id, partida_id, ambito_id)`.
  Por eso el troceo por obras es demostrablemente equivalente al build
  monolítico, y por eso una ventana **por obras** también lo es.
- En cambio **el `ffill` y el `LAG` necesitan la serie mensual completa de la
  obra**. Acotar por «ejercicio en curso», que es como suena la idea en
  lenguaje de negocio, **rompería el cálculo**: no es una optimización, es un
  cambio de resultado.

Conclusión de diseño: *ventana de negocio* aquí significa **«un `SELECT` que
devuelve `obra_id`»**, nada más. Cualquier otra dimensión queda fuera.

### 1.3 El punto de inyección ya existe

F-019 dejó montado exactamente el mecanismo que esta feature necesita:

```
config/business_rules.yaml  ventana.vigente  ──►  SELECT obra_id ...
                                                        │
etl_sigrid/domain/ventana.py  (nuevo, puro)  ◄──────────┘
   filtrar_obras(pesos_por_obra, obras_en_ventana) -> dict[int, int]
                                                        │
etl_sigrid/domain/tramos.py  planificar_tramos(...)  ◄──┘   (NO SE TOCA)
                                                        │
build_stg_step.componer_sql_tramo(sql, obras)        ◄──┘   (sustituye
   /*F019_FILTRO_OBRAS*/  →  ARRAY[...]::BIGINT[]            el marcador)
```

Es decir: **la ventana entra por donde ya entra el troceo**. `planificar_tramos`
recibe menos obras, produce menos tramos, y el SQL que se ejecuta es
carácter por carácter el mismo que hoy salvo la lista de obras. Ese es el
motivo por el que la equivalencia de R12 es exigible y no una esperanza.

Lo único que hay que añadir en el step es lo que hoy no existe porque hoy no
hace falta: **dejar de hacer `TRUNCATE` global y borrar solo las obras que se
van a recalcular** (§2).

### 1.4 Límite de microservicio

Evaluado según manda el protocolo del `spec-author`:

- **El build del datamart es de este servicio.** `stg` y `mart` son su
  producto; nadie más los escribe.
- **La definición de «obra abierta» NO es de este servicio.** Es dominio de
  Sigrid y decisión de Negocio (DA-1). Este ETL la **consume declarada** en
  `config/business_rules.yaml`, no la inventa ni la deduce. Si Negocio elige la
  opción (c) —la situación del contrato, `obrctr.sitide` → `auxobrcts`—, el
  catálogo se ingiere como una tabla más por el camino normal (R20); **no** se
  consulta a Sigrid al vuelo desde el build.
- **Nada de esto justifica un microservicio nuevo.** Es una feature con
  decisión de Negocio dentro del ETL, exactamente como lo era F-019.
- **`sigrid-api` no se toca**, ni su documento en `azure-apps/`: esta feature
  no cambia lo que consumimos de él (salvo que DA-1 elija (c), que añadiría una
  tabla a la ingesta y **sí** obligaría a actualizar
  `azure-apps/datamart_seg_anual.md`, que es nuestro).

---

## 2 · La decisión estructural: acotar el REFRESCO, no el CONTENIDO

Hoy el build es *borrar todo y rehacer todo*:

- `build_stg_step` hace **un `TRUNCATE` de `stg.plan_mensual`** y luego recorre
  los 60 tramos (el `TRUNCATE` salió del `.sql` en F-019 justamente para poder
  trocear).
- `sql/mart/02_build_fact.sql` hace `TRUNCATE TABLE mart.fact_seguimiento_mensual;`
  (línea 49) y después un `INSERT INTO ... SELECT` (línea 200).

Con la ventana activa eso cambia a *borrar lo que voy a rehacer y rehacerlo*:

| Hoy | Con ventana activa |
|---|---|
| `TRUNCATE stg.plan_mensual` | `DELETE FROM stg.plan_mensual WHERE obra_id = ANY(<obras del tramo>)` **dentro de la transacción del tramo** |
| `TRUNCATE mart.fact_seguimiento_mensual` | `DELETE FROM mart.fact_seguimiento_mensual WHERE obra_id = ANY(<obras de la ventana>)` |

Y **las filas de las obras fuera de la ventana se quedan donde están**. De ahí
salen las tres propiedades que hacen esta feature defendible:

1. **Power BI no ve ningún cambio.** El contenido final es el mismo → la huella
   de las vistas de consumo tiene que ser idéntica (R12), y eso se comprueba
   con `fingerprint-views` / `compare-fingerprints`, el mismo instrumento con
   el que F-019 demostró su equivalencia.
2. **El riesgo es acotado y conocido**: lo que se arriesga es *quedarse con
   dato viejo* de una obra que se creía cerrada y se movió, no perder dato. La
   red es la reconstrucción completa semanal (R15).
3. **No hace falta una máquina de estados nueva.** No hay watermark, ni modos,
   ni cursores: hay un `SELECT` de obras y un `DELETE` por obra.

La alternativa —acotar el **contenido**, que el histórico cerrado deje de
existir— es **DA-2**, y no se recomienda: ahorraría algo más de disco y de
tiempo a cambio de que Power BI pierda informes, y no habría equivalencia que
demostrar, solo una pérdida que aceptar.

### El coste que esta decisión introduce, dicho sin adornos

`DELETE` + `INSERT` de ~20-30 % de una tabla de 29,4 M filas, todas las
noches, genera **WAL y bloat** donde hoy hay un `TRUNCATE` limpio. En el
`Standard_B1ms` compartido de 32 GB —el mismo donde el 2026-08-09 el disco
llegó al 93,4 %— eso no es un detalle. Mitigaciones en el diseño:

- Índice `stg.plan_mensual (obra_id)` para que el `DELETE` no haga *seq scan*
  de 29 M filas por tramo (§6).
- El `DELETE` va **dentro de la transacción del tramo** que F-019 ya abre, así
  que el pico de WAL sigue acotado por tramo, no por build.
- La **puerta de disco de F-019 sigue armada** y con el mismo umbral (R11); si
  el borrado repetido hincha la tabla, la puerta lo detiene igual que detuvo el
  derrame de temporales.
- El bloque A **mide** el tamaño real del borrado antes de decidir (DA-3).

---

## 3 · Ficheros a crear

### Bloque A · Medición

| Ruta | Qué es | Capa |
|---|---|---|
| `etl_sigrid/domain/ventana.py` | Funciones puras: `Candidato` (nombre + SQL + descripción), `PesoVentana` (obras dentro/fuera, filas dentro/fuera por tabla), `peso_de_la_ventana(...)`, **`ahorro_estimado(duraciones_por_tramo, pesos_por_obra, obras_dentro) -> AhorroEstimado`** (R2), `format_perfil_ventana(...)`. Sin psycopg, sin click. | domain |
| `tests/test_f025_ventana.py`, `test_f025_config.py` | Ver la trazabilidad de `requirements.md`. | tests |

### Bloque B · Acotado del build (solo tras la puerta de R5)

| Ruta | Qué es | Capa |
|---|---|---|
| `etl_sigrid/domain/ventana.py` (amplía) | `filtrar_obras(pesos_por_obra, obras_en_ventana) -> dict[int, int]` y `validar_ventana(obras_dentro, obras_totales, max_pct_fuera) -> None \| MotivoAborto` (R13). Puro y exhaustivamente testeable: es la pieza que la campaña de mutación va a morder. | domain |
| `etl_sigrid/infrastructure/postgres/sql/stg/01_ddl.sql` (amplía, no se crea) | Índice `idx_plan_mensual_obra` sobre `stg.plan_mensual (obra_id)`, `IF NOT EXISTS`. | infrastructure · capa `stg` |
| `tests/test_f025_build.py`, `test_f025_guardias.py`, `test_f025_apagado.py`, `test_f025_alcance.py` | Ver la trazabilidad. | tests |

---

## 4 · Ficheros a modificar

### Bloque A

| Ruta | Qué cambia |
|---|---|
| `config/business_rules.yaml` | Bloque nuevo `ventana:` con dos claves: `candidatos:` (lista de predicados con nombre, SQL y comentario, para que el bloque A los mida todos) y `vigente: null` **con el comentario que apunta a DA-1**. Con `vigente` a `null`, el build se comporta como hoy (R7) y `perfil-ventana` sigue funcionando sobre los candidatos. Si además `candidatos` está vacío, `perfil-ventana` falla a propósito (R3). |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | `fetch_peso_ventana(predicado_sql: str) -> PesoVentana` y `fetch_obras_de_la_ventana(predicado_sql: str) -> tuple[int, ...]`, ambos **solo lectura**, siguiendo el patrón de `fetch_pesos_plan_mensual` / `fetch_timings`. El predicado se valida antes de ejecutarse: debe empezar por `SELECT` y no contener `;`. |
| `main.py` | Comando nuevo de **solo lectura** `perfil-ventana [--detalle] [--out]`, sin `_arrancar_ejecucion()` (R19). |

### Bloque B

| Ruta | Qué cambia |
|---|---|
| `config/settings.py` | Clase nueva `VentanaSettings` (prefijo `VENTANA_`): `activa: bool = False`, `max_pct_fuera: float = 95.0`. Con los defaults, comportamiento idéntico al de hoy (R7). Pydantic v2, `default=` solo en la firma (`docs/CONVENTIONS.md`). |
| `etl_sigrid/application/steps/build_stg_step.py` | (a) si la ventana está activa, resuelve las obras con `fetch_obras_de_la_ventana` y filtra los pesos con `filtrar_obras` **antes** de llamar a `planificar_tramos`; (b) sustituye el `TRUNCATE` global de `stg.plan_mensual` por un `DELETE ... WHERE obra_id = ANY(...)` **por tramo, dentro de su transacción**; (c) aplica `validar_ventana` y aborta con `PlanMensualAbortado` si procede (R13); (d) escribe el `metadata` de R14. **`componer_sql_tramo` no cambia**, ni el marcador, ni `RAMAS_CON_FILTRO`. |
| `etl_sigrid/application/steps/build_mart_step.py` | Si la ventana está activa, ejecuta `02_build_fact.sql` en su variante acotada (§6) y deja `agg_categoria` coherente. Sin ventana, ejecuta exactamente lo de hoy. |
| `etl_sigrid/infrastructure/postgres/sql/mart/02_build_fact.sql` | El `TRUNCATE` de la línea 49 pasa a ser condicional al modo: se sustituye por el marcador `/*F025_BORRADO*/`, que el step reemplaza por el `TRUNCATE` de siempre (sin ventana) o por el `DELETE ... WHERE obra_id = ANY(...)` (con ventana). Mismo patrón de sustitución textual que `/*F019_FILTRO_OBRAS*/`, y por la misma razón: el fichero tiene `%` literales en comentarios y no admite `%(param)s`. |
| `docs/ARCHITECTURE.md` | Sección nueva: qué es la ventana de negocio, qué acota (el refresco, no el contenido), cómo se declara y qué garantiza la reconstrucción completa semanal. |
| `azure-apps/datamart_seg_anual.md` | **Solo si la feature se implementa**: cambia el perfil de carga del servicio y sus variables de entorno (`VENTANA_ACTIVA`, `VENTANA_MAX_PCT_FUERA`), y —si DA-1 elige la opción (c)— la lista de tablas que consumimos de `sigrid-api`. La regla de `CLAUDE.md` obliga a actualizarlo **en el mismo trabajo**. |

---

## 5 · Ficheros que NO se tocan (los que tientan)

- **`etl_sigrid/domain/tramos.py`** — `planificar_tramos`, `Tramo`,
  `tramos_sobredimensionados`. Es el corazón de F-019 y su prueba de
  equivalencia. La ventana le pasa menos obras; el algoritmo no cambia (R10).
  Si el implementer se ve editando este fichero, el diseño se torció: vuelva a
  §1.3.
- **`etl_sigrid/infrastructure/postgres/sql/stg/08_plan_mensual.sql`** — ni una
  línea. El único punto de inyección sigue siendo `/*F019_FILTRO_OBRAS*/`, en
  sus dos ramas (ámbitos 8/11 y 3/7). Si hiciera falta tocar el SQL, la
  equivalencia de F-019 habría que rehacerla entera.
- **`etl_sigrid/infrastructure/postgres/fingerprint.py`** — es el **instrumento
  de medida** de R12. Se usa, no se ajusta. Cambiar el instrumento para que la
  prueba pase es exactamente lo que F-019 T11 prohíbe.
- **`sql/stg/03_obras.sql` y el flag `activa`** — sigue siendo `TRUE` literal
  (R18, DA-5).
- **La puerta de coherencia de `raw` de F-024** — no cambia (R16).
- **`config/tables_sigrid.yaml`** — salvo que DA-1 elija la opción (c), en cuyo
  caso se añade `auxobrcts` como una tabla más (R20).
- **`azure-apps/sigrid_api.md` y `azure-apps/sigrid_tablas.md`** — documentos
  cuyo dueño es otro proyecto. Se leen y se citan; no se editan.
- **`harness/features.json`** — lo actualiza el líder, no esta spec.

---

## 6 · SQL nuevo y SQL modificado

**No se crea ninguna capa ni ningún esquema nuevo.** Todo ocurre en `stg` y en
`mart`, que ya existen.

1. **`sql/stg/01_ddl.sql`** (capa `stg`, fichero existente, se amplía):

   ```sql
   CREATE INDEX IF NOT EXISTS idx_plan_mensual_obra
       ON stg.plan_mensual (obra_id);
   ```

   Justificación: sin él, cada uno de los N tramos haría un *seq scan* de 29,4
   M de filas para borrar las suyas. Es aditivo e idempotente, y no cambia
   ninguna consulta existente.

2. **`sql/mart/02_build_fact.sql`** (capa `mart`, fichero existente): el
   `TRUNCATE` de la línea 49 se sustituye por el marcador `/*F025_BORRADO*/`,
   que el step reemplaza por texto —igual que `/*F019_FILTRO_OBRAS*/`—:

   | Modo | Texto inyectado |
   |---|---|
   | Sin ventana (por defecto) | `TRUNCATE TABLE mart.fact_seguimiento_mensual;` (**el de hoy, carácter por carácter**) |
   | Con ventana | `DELETE FROM mart.fact_seguimiento_mensual WHERE obra_id = ANY (ARRAY[...]::BIGINT[]);` |

   Un test comprueba que, con la ventana apagada, el SQL resultante es
   **idéntico** al fichero actual (R7).

3. **Sin bloques `$$`** en nada de lo anterior: el troceador de sentencias de
   `postgres_client.py` no los sabe partir (por eso los `GRANT` se generan en
   Python y `infra/sql/` se ejecuta a mano con `psql`).

Ninguna otra capa (`cierre`, `compras`, `maestro`, `retenciones`, `auxiliar`,
`ddl`) recibe SQL en esta feature.

---

## 7 · Encaje en la arquitectura y en el pipeline

```
main.py (click)
 └─ perfil-ventana   ── SOLO LECTURA. Sin batch_id, sin filas en _meta (R19)
                        dominio puro (ventana.py) + fetch_* del PostgresClient

run-all  →  Orchestrator([
      IngestRawStep,      ← intacto (es F-011)
      LoadExcelAuxStep,   ← intacto
      BuildStgStep,       ← CAMBIA: obras filtradas + DELETE por tramo
      BuildMartStep,      ← CAMBIA: DELETE por obra en vez de TRUNCATE
      ApplyGrantsStep,    ← intacto
   ])
```

La composición del pipeline sigue en `build_pipeline_steps()` de `main.py`
(`docs/CONVENTIONS.md`) y **no cambia**: F-025 no añade ni quita pasos. El
patrón se mantiene: **la decisión es dominio puro** (qué obras, si abortar), el
step solo orquesta, y la infraestructura solo lee y escribe.

`apply_grants` sigue reaplicándose al final, porque los `DROP VIEW ... CASCADE`
de siete ficheros se llevan los `GRANT` del rol del MCP por delante.

---

## 8 · Riesgos y decisiones

| Riesgo | Mitigación en el diseño |
|---|---|
| **Cambiar lo que ve Power BI sin darse cuenta.** Es el riesgo principal: `mart.v_pbi_*`, `mart.v_fact_periodificado`, `cierre.v_pbi_*`. | Acotar el **refresco y no el contenido** (§2) + prueba de equivalencia obligatoria con `fingerprint-views` / `compare-fingerprints` (R12), con el criterio de F-019: cualquier diferencia en los bloques `estructura` y `cerrado` es FALLO y la feature se marca `blocked`. |
| **Quedarse con dato viejo** de una obra que se creía cerrada y se movió. | Reconstrucción completa semanal (R15, domingo) + el predicado de DA-1 con la red de «movimiento en los últimos 12 meses» que recomienda el spec-author. |
| **Un predicado mal escrito vacía el datamart a las 02:00.** | R13: cero obras o más del `VENTANA_MAX_PCT_FUERA` % fuera → aborto **antes** de borrar nada, con `PlanMensualAbortado`. A las 02:00 no hay nadie delante (criterio heredado de F-024). |
| **El `DELETE` repetido hincha la tabla y llena el disco compartido.** Precedente real: 93,4 % el 2026-08-09. | Índice por `obra_id`, `DELETE` dentro de la transacción del tramo, puerta de disco de F-019 intacta (R11) y medición previa en el bloque A (DA-3). |
| **Romper la equivalencia de F-019 al tocar el troceo.** | R10 + test de que `tramos.py` no cambia + los tests de F-019 pasan **sin modificarse**. El único punto de inyección sigue siendo el marcador. |
| **Implementar todo esto para ahorrar diez minutos.** | Puerta de R5 con números: el bloque A mide el ahorro por candidato **antes** de escribir el bloque B. Si el ahorro no justifica el riesgo, la feature se cierra entregando solo la medición — exactamente como F-011 con su bloque B. |
| **DA-1 se decide «por lo que diga el código»** en vez de por Negocio. | R3: sin predicado declarado, `perfil-ventana` **falla**; no hay criterio por defecto que se pueda colar en producción por omisión. |
| **El doble conteo preexistente de F-022** (obras 0694 y 0697, versiones master duplicadas en `raw.obrfasamb`) se confunda con un fallo de la ventana. | Está documentado en `docs/referencia/05_caso_obrfasamb_version_duplicada.md`; la prueba de equivalencia compara **build acotado contra build completo del mismo `raw`**, así que el defecto aparece idéntico en ambos lados y no contamina el veredicto. |

### Alternativas descartadas

- **Acotar por ejercicio o por rango de meses.** Rompe el `ffill` y el `LAG` de
  `08_plan_mensual.sql`, que necesitan la serie mensual completa de la obra
  (§1.2). No es una optimización: es un cambio de resultado.
- **Vistas materializadas incrementales / `REFRESH MATERIALIZED VIEW
  CONCURRENTLY`.** Exige índice único y duplica el almacenamiento durante el
  refresco, en un servidor de 32 GB compartido donde ya hubo un incidente.
- **Particionar `stg.plan_mensual` por obra.** Miles de particiones en un
  `Standard_B1ms`; el planificador de PostgreSQL lo paga en cada consulta de
  Power BI.
- **Cachear el resultado de las obras cerradas en una tabla histórica aparte y
  unir por `UNION ALL` en las vistas.** Añade una tabla, un `UNION` en todas
  las vistas de consumo y una forma nueva de que las dos mitades diverjan, a
  cambio de lo mismo que da el `DELETE` por obra.
- **Adelgazar el datamart (opción (b) de DA-2).** Ahorra más, pero Power BI
  pierde informes. Si Negocio lo quiere, es otra feature y otra conversación.
