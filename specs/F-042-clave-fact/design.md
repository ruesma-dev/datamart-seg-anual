<!-- specs/F-042-clave-fact/design.md -->
# F-042 · Diseño

**La idea, en una frase:** en la rama de reales de `stg/08_plan_mensual.sql`, se
elige un solo cierre por mes y se **renumera el orden interno** de los
supervivientes antes del `LAG`; nada más cambia, porque todo lo de arriba se
arregla solo al desaparecer la fila gemela.

---

## 1. El cambio de fondo: `sql/stg/08_plan_mensual.sql`

Capa **`stg`**, rama B (reales, `ambito_id IN (3, 7)`). Se insertan tres CTE
entre `reales_base` y `reales_con_lag`, y se retoca `reales_con_lag`.

```sql
-- F-042: un cierre por mes. Una fila por (obra, ambito, fase): miles, no millones.
reales_cierres AS (
    SELECT obra_id, ambito_id, anio_mes, mes_fase_num,
           SUM(importe_origen_round) AS acumulado
    FROM reales_base
    GROUP BY obra_id, ambito_id, anio_mes, mes_fase_num
),
-- R1 + R2 + R4: manda el mas moderno de entre los que NO estan a cero.
reales_vigente AS (
    SELECT DISTINCT ON (obra_id, ambito_id, anio_mes)
           obra_id, ambito_id, anio_mes, mes_fase_num
    FROM reales_cierres
    ORDER BY obra_id, ambito_id, anio_mes,
             (acumulado <> 0) DESC, mes_fase_num DESC
),
-- R5 + R6: desplaza SOLO por los descartes; los huecos de origen se respetan.
reales_orden AS (
    SELECT c.obra_id, c.ambito_id, c.mes_fase_num,
           (v.mes_fase_num IS NOT NULL) AS vive,
           c.mes_fase_num - COALESCE(SUM(CASE WHEN v.mes_fase_num IS NULL THEN 1 ELSE 0 END)
               OVER (PARTITION BY c.obra_id, c.ambito_id ORDER BY c.mes_fase_num
                     ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS orden_fase
    FROM reales_cierres c
    LEFT JOIN reales_vigente v USING (obra_id, ambito_id, mes_fase_num)
),
```

`reales_con_lag` pasa a leer de `reales_base ⨝ reales_orden` con `WHERE vive`, y
sus cuatro `CASE` cambian el predicado
`LAG(mes_fase_num) OVER w = mes_fase_num - 1` por
`LAG(orden_fase) OVER w = orden_fase - 1`, con
`WINDOW w AS (PARTITION BY obra_id, partida_id, ambito_id ORDER BY orden_fase)`.
`mes_fase_num` **sigue siendo lo que se inserta en `version`** (R7).

**Por qué el desplazamiento y no `dense_rank()`.** `dense_rank()` cerraría
*todos* los huecos, incluidos los que Sigrid ya trae. Una obra con fases 1, 2 y
4 pasaría a 1, 2, 3 y el `importe_mes` de la 4 cambiaría de «acumulado entero» a
«diferencia», **en obras que hoy están bien**. El desplazamiento cuenta solo
descartes, así que un hueco de origen sigue siendo un hueco (R6).

**Tramos de F-019.** `reales_base` ya viene filtrado por obra
(`/*F019_FILTRO_OBRAS*/`) y las tres CTE nuevas **particionan por obra**: ningún
cálculo cruza obras, así que el resultado por tramos es idéntico al de una
pasada. Es el mismo argumento estructural de F-019, no una coincidencia. **No
hace falta marcador nuevo** ni tocar `build_stg_step.py`.

## 2. Ficheros a crear

| Ruta | Capa | Qué es |
|---|---|---|
| `etl_sigrid/domain/cierres.py` | domain | La regla, pura. `Cierre(numero_fase, acumulado)`; `plan_de_cierres(cierres) -> PlanCierres(descartadas, orden)`. Cero imports de infraestructura. |
| `etl_sigrid/domain/huella.py` | domain | `FilaHuella(obra, ambito, periodo, filas, importe_mes, importe_origen)`; `comparar_huellas(antes, despues)`; `veredicto(comparacion, obras_esperadas)`. Puro. |
| `etl_sigrid/infrastructure/postgres/huella_obras.py` | infra | Construye el SQL agregado, lo ejecuta y escribe/lee el CSV. Al estilo de `fingerprint.py`, que ya hace esto para las vistas. |
| `etl_sigrid/infrastructure/postgres/cierres_sql.py` | infra | Construye la consulta de R17 (solo lectura). Al estilo de `unicidad_sql.py`: **no abre conexión**, solo produce texto. |
| `tests/test_f042_regla.py` | — | La regla contra las 24 colisiones reales como fixture. |
| `tests/test_f042_huella.py` | — | Comparación y veredicto. |
| `tests/test_f042_sql.py` | — | Aserciones de texto sobre el `.sql`: que la rama master no se toca, que el `LAG` usa `orden_fase`, que `version` recibe `mes_fase_num`. |

`domain/cierres.py` **no es una copia del SQL, es un oráculo independiente**:
recibe los acumulados leídos de la base y dice qué debería haber quedado. Si el
SQL y el oráculo discrepan, `check-cierres` falla. Ese es su valor.

## 3. Ficheros a modificar

- `sql/stg/08_plan_mensual.sql` — el cambio de la sección 1.
- `main.py` — tres comandos **de solo lectura**: `check-cierres` (R17),
  `huella-obras --out FICHERO [--desde stg|mart] [--propuesta]` (R22) y
  `comparar-huellas ANTES DESPUES [--obras-esperadas]` (R23–R25).
- `config/diccionario/stg.yaml` — ficha de `plan_mensual`: la regla nueva, y que
  `version` es el número de fase **original de Sigrid, con huecos** (R18).
- `config/diccionario/mart.yaml` — retirar el aviso de dato doblado de las cuatro
  fichas y de las columnas `importe_origen` / `importe_origen_raw`; describir el
  grano ya sin defecto en `v_pbi_fact_categoria` (R18, R19).
- `config/diccionario/cierre.yaml` — ficha de `v_pbi_planif_vs_real` (R19).
- `config/diccionario/00_global.yaml` — subir `version` (R21).
- `docs/ARCHITECTURE.md` — una línea en «Semántica Sigrid imprescindible»: dos
  cierres en un mes, manda el moderno.

## 4. Ficheros que NO se tocan, y por qué

- **`sql/mart/03_agg_categoria.sql`** — es la tentación principal. **No hace
  falta**: su `SUM(importe_origen)` doblaba porque veía dos filas gemelas; con
  una sola fila el agregado sale correcto sin cambiar una letra. Tocarlo sería
  arreglar el síntoma dos veces.
- **`sql/mart/01_ddl.sql`, `02_build_fact.sql`, `05_views_powerbi.sql`** — la
  clave **no crece** (decisión de Negocio) y Power BI no cambia de forma.
- **`sql/cierre/02_build_fact.sql` y `04_views_detalle.sql`** — sus **seis**
  `JOIN ... ON fm.numero_fase = pm.version` siguen valiendo **precisamente
  porque `version` no se renumera** (R7). El cierre descartado deja de tener
  filas en `plan_mensual`, así que el doble conteo de R15 desaparece solo.
- **`sql/stg/05_fases.sql` y `stg.fases`** — la fase descartada **sigue ahí**. Es
  el rastro: en `raw` y en `stg.fases` el cierre existe; en `plan_mensual`, no.
- **`raw/` y `ingest_raw_step.py`** — la ingesta reescribe `raw` cada noche, así
  que un borrado allí se deshace solo; y `raw` es la copia fiel del origen,
  mientras que «manda el cierre moderno» es interpretación.
- **`build_stg_step.py`** — ver el argumento de tramos.

## 5. La prueba que decide: antes/después con el mismo `raw`

Requisito del humano (R22–R25). El «después» exige reconstruir, y el Postgres
es **el compartido con `albaranes` y `partes` en producción**.

**El disco se amplió el 2026-08-29 de 32 a 64 GB** (online, sin corte), y los
IOPS de 120 a 240. Ocupación hoy: **19 GB, el 29 %, con 45,4 GB libres**. Eso
cambia el veredicto de una de las alternativas —ver «lo que ya sí cabe»— pero no
el diseño, porque hay un camino que **no necesita disco en absoluto**.

**El dato que lo resuelve: la huella cabe en un CSV.** El grano que el humano
pide —obra × ámbito × mes, con `importe_mes` e `importe_origen`— son **11.883
celdas** en los cuatro ámbitos (`mart.fact_seguimiento_categoria` entera son
24.684 filas y 6,6 MB). No hay que copiar nada: hay que **medir y guardar
fuera**.

### Nivel 1 · Sin escribir ni una fila (obligatorio, lo hace el implementer)

`huella-obras --desde stg` agrega `stg.plan_mensual` a (obra, ámbito, mes) →
huella **ANTES**. `huella-obras --desde stg --propuesta` ejecuta la rama de
reales **ya modificada como `SELECT`**, agregándola al vuelo **sin
materializar** → huella **DESPUÉS**. `comparar-huellas` emite las dos listas
completas de R23.

- **El agregado lleva los mismos `JOIN` que `mart`** (`stg.obras`,
  `stg.partidas`, ambos `INNER`). No es un detalle: sin ellos la huella de `stg`
  contaría partidas que `mart/02_build_fact.sql` descarta, y dejaría de ser
  predictiva. Con ellos, **en los ámbitos REALES (3 y 7) el agregado de `stg` es
  exactamente el que `mart.fact_seguimiento_categoria` publica**, porque de
  `stg` a esa tabla solo hay una proyección y un `SUM` por las mismas
  dimensiones. **Medido el 2026-08-29 celda a celda entre las dos huellas de
  T14: desviación 0 en las 8.243 celdas de los ámbitos 3 y 7** (4.251 + 3.992).
- **Y NO vale para los master (8 y 11)**, aunque la primera versión de este
  diseño lo afirmara de los cuatro. Ahí `stg.plan_mensual` guarda **todas** las
  versiones y `mart` publica **solo la vigente de cada mes**
  (`02_build_fact.sql`, `version_vigente_por_mes`), así que el agregado de `stg`
  suma la obra tantas veces como versiones tenga: en la 0644 son **43,6 M€ en
  `stg` frente a 1,3 M€ en `mart`**, y salen 473 celdas de más. **No invalida la
  prueba** —`comparar-huellas` enfrenta `stg` contra `stg`, así que el artefacto
  se cancela, y en los master no cambia nada—, pero quien compare las dos
  huellas de T14 sin saberlo creerá haber encontrado un defecto de 40 millones.
- **Coste: cero escrituras y cero crecimiento de disco.** Solo lecturas.
- **Temporales:** las ventanas ordenan por (obra, partida, ámbito). Se ejecuta
  **por tramos de obras** reutilizando `domain/tramos.py` y la **puerta de disco
  de F-019** (`PG_DISCO_LIMITE_PCT`), igual que el build. No se inventa
  mecanismo nuevo.
- **Ámbitos 8 y 11:** la huella propuesta **es la actual, copiada**, y no se
  vuelve a ejecutar la rama master. Dos motivos: el diff **no toca** esa rama
  (lo asegura `tests/test_f042_sql.py`) y hoy **no tienen ni una clave
  duplicada** (medido: 4.754 en amb 3, 4.024 en amb 7, **cero** en 8 y 11).
  Reejecutarla sería pagar el `CROSS JOIN LATERAL unnest` que provocó el
  incidente de F-019 para obtener, por construcción, el mismo número.
- **Qué garantiza:** la lista completa de obras cuya numeración e importes
  cambian, en los cuatro ámbitos, con el mismo `raw`, y que ninguna otra se
  mueve —lo que pide R24—. **Qué no garantiza:** el comportamiento de `cierre`,
  que agrega por su propio `mes_canonico` (`cierre.fn_mes_de_fase`) y no por
  `anio_mes`.

### Nivel 2 · La reconstrucción real — **la lanza el humano**

`python main.py stage` + `build-mart` + `build-cierre`, **sin `ingest`**, sobre
el `raw` que ya está. **No es tarea del implementer**: es escritura en
producción.

- **Coste en disco: cero neto.** El build es **en el mismo sitio**: `stage` hace
  `TRUNCATE` de `stg.plan_mensual` y `mart/01_ddl.sql` un `DROP TABLE …
  CASCADE`. El pico transitorio es el de una nocturna, que ya se paga todas las
  noches, y lo acota la puerta de F-019 midiendo **antes de cada tramo**.
- **Coste en tiempo: entre una hora y media y dos horas para el `stage`, y
  alrededor de media hora el `build-mart`.** Las únicas medidas que existen son
  del 2026-08-28 —110 min y 21,5 min— y se tomaron **con 120 IOPS**. Con 240
  debería bajar algo, pero **la spec no promete un número**: el techo del
  `Standard_B1ms` son 640 IOPS y **10 MiB/s** de ancho de banda, y en un build
  que mueve estos volúmenes manda el ancho de banda, que no se ha tocado.
- **ORDEN CRÍTICO.** La huella de ANTES se saca **antes** de reconstruir: la
  reconstrucción **pisa la tabla** y no hay vuelta atrás (el PITR es de servidor
  entero y arrastraría a los vecinos). Los CSV van **fuera de la base**, como los
  `huella_*.csv` de F-019.
- **No sirve la nocturna siguiente**: reingiere `raw` con `--full`, y entonces el
  `raw` ya no sería el mismo.

### Lo que ya sí cabe, y por qué aun así no se hace

**Reconstruir en esquemas paralelos (`stg_f042`, `mart_f042`) ha dejado de ser
un riesgo de disco**: ~9,8 GB de tablas y un pico de ~26 GB sobre 45,4 GB
libres. Tiene una ventaja real —**no destruye el «antes»**— y aun así no se
propone, **y el motivo ya no es el disco sino el código**: ni
`08_plan_mensual.sql` ni `mart/` están parametrizados por esquema, así que haría
falta parametrizarlos, y eso es superficie nueva y sin probar **dentro de la
tarea cuyo objetivo es demostrar que nada se mueve**. Queda anotada por si el
humano prefiere no sobrescribir `stg`.

**Reconstruir en un Postgres local:** posible y sin riesgo para los vecinos,
pero exige reingerir ~20 M filas y **prueba el código, no el dato de
producción**.

## 6. Riesgos y decisiones descartadas

1. **Publicar `version` renumerado — DESCARTADO.** Tres razones: (a) seis
   `JOIN` de `cierre/` cruzan `pm.version` contra `stg.fases.numero_fase` y
   renumerar los desalinea **en silencio**; (b) el diccionario ya documenta
   `version` como el número de fase de Sigrid; (c) quien mire el dato tiene que
   poder contrastarlo contra Sigrid. **Consecuencia aceptada:** `version` queda
   con huecos en 9 obras, y la ficha lo dice.
2. **Añadir el número de fase a la clave — DESCARTADO por Negocio** el
   2026-08-28. No se vuelve a abrir aquí.
3. **Borrar la fila sin renumerar — DESCARTADO:** arregla el acumulado y rompe
   el movimiento (0499 feb-2018: 975.249,98 → 5.688.073,92).
4. **Riesgo de rendimiento del build.** Las CTE nuevas agregan `reales_base` a
   unos pocos miles de filas y añaden un `JOIN` pequeño. Se mide con
   `python main.py timings` y se compara con el 1 h 50 del 2026-08-28.
5. **R8 NO se cumple en una celda, y se acepta.** Medido en T17: en
   **0471 · ámbito 7 · marzo de 2016** el `importe_mes` publicado cambia de
   485.843,69 a **481.305,60 (−4.538,09)**, así que deja de ser la suma de los
   `importe_mes` que hoy publican los dos cierres del mes. **La causa, medida:**
   una partida tiene fila en las fases **4 y 6** y **no en la 5**, con
   `importe_origen` de 4.538,09 € en la 4. Antes, su fila de la 6 no tenía `LAG`
   consecutivo y publicaba **el acumulado entero**; con la 5 descartada,
   `orden_fase(6) = 5` y pasa a publicar la diferencia. **El valor nuevo es el
   correcto**: repara el telescopio de R16, que ahí estaba roto por +4.538,09.
   O sea que R8, redactado como «el superviviente iguala la suma de lo que hoy
   publican», arrastraba un defecto preexistente. Se acepta la desviación
   —corrige, no rompe— y queda declarada aquí y en `impl_F-042.md`.

6. **Riesgo de `<> 0` frente a `> 0`.** Se usa **distinto de cero**, que es el
   complemento exacto de la condición que fijó el humano («acumulado cero») y no
   inventa regla para un acumulado negativo, que hoy no existe.
7. **Riesgo de alcance:** `cierre` cambia de números aunque no se toque su SQL.
   No basta con mirar `mart`: el nivel 2 debe medir los dos.

## 7. Límite de microservicio

Dentro. Todo ocurre en `stg` y en la lectura de `mart`/`cierre` de este mismo
ETL. No se toca `sigrid-api`, ni el origen, ni ningún otro proyecto. La
investigación de **por qué** Sigrid tiene esas obras así está fichada aparte
como **F-050**, y no entra aquí.
