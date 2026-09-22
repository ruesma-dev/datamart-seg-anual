<!-- specs/F-051-nombre-mes-real/design.md -->
# F-051 · Diseño · Cada cierre real en el mes de su TEXTO

Cifras y listas: `progress/spec_F-051.md`. Código actual con `fichero:línea`:
`progress/explore_F-051_regla_mes.md`.

## 1 · Encaje: el mes se decide UNA vez, en `stg`

Hoy hay dos verdades: `stg`/`mart` ponen la fila real en el `ano`/`mes` de
`obrfas` (`stg/08_plan_mensual.sql:365`) y `cierre` la recalcula con
`cierre.fn_mes_de_fase` (`cierre/02_build_fact.sql:64`, `04_views_detalle.sql:128,
:508`). **El arreglo es que el mes se decida en `stg.plan_mensual.anio_mes` y
que `mart` y `cierre` lo lean sin recalcular.** Así «el mismo mes en las tres
capas» (R16) sale por construcción, no por coincidencia de dos cálculos.

Por qué `stg` y no `mart`: `cierre` lee de `stg.plan_mensual`, no de `mart`; la
regla de F-042 (un cierre por mes) y el `LAG` de `importe_mes` ya viven ahí; y
`huella-obras --propuesta` reejecuta ese bloque en solo lectura, que es la
prueba antes/después que exige R21–R23. Límite de microservicio: todo es del
datamart; no toca Sigrid, `sigrid-api` ni otros proyectos.

**La fase es por obra.** Comprobado en Sigrid (solo lectura, 2026-09-22):
`obrfasamb` guarda por ámbito `est`, `act`, `feccie` y `oriamb`/`orifas`, pero
`res`, `tex` y `fec` están vacíos en las 9.104 filas de los ámbitos 3 y 7. El
periodo y el texto solo viven en `obrfas`: detector y mes destino valen para
coste y venta a la vez.

## 2 · Ficheros a modificar

| Fichero | Cambio |
|---|---|
| `sql/stg/00_functions.sql` | Nuevas `stg.fn_parse_mes_texto(texto)` (parser con R3–R4) y `stg.fn_mes_de_fase(fecha_inicio, nombre_mes, fecha_fin DEFAULT NULL)` (§4). |
| `sql/stg/01_ddl.sql` | `ALTER TABLE stg.plan_mensual ADD COLUMN es_relleno BOOLEAN NULL`, en el bloque `DO` idempotente del resto de columnas añadidas. |
| `sql/stg/08_plan_mensual.sql` | Rama de reales (§5). Rama master: **ni una línea**. Cabecera: sección F-051. |
| `sql/mart/01_ddl.sql` | `es_relleno BOOLEAN` en `mart.fact_seguimiento_mensual`. |
| `sql/mart/02_build_fact.sql` | Ramas 1 y 2 (`:218`, `:243`): `nombre_mes` con el ARRAY de las ramas 3 y 4; `version_descripcion` sigue siendo el texto; `es_relleno = pm.es_relleno`. Ramas 3 y 4: `NULL::BOOLEAN`. |
| `sql/mart/05_views_powerbi.sql` | `es_relleno` en `mart.v_pbi_fact` (**D8**). |
| `sql/cierre/00_setup.sql` | `cierre.fn_mes_de_fase(fi, nm)` pasa a `RETURN stg.fn_mes_de_fase(fi, nm)`. `fn_parse_mes_fase` y `fn_mes_de_version_master` **no cambian** (R5). |
| `sql/cierre/01_ddl_fact.sql` | Columna `es_relleno BOOLEAN` en `cierre.fact_cierre_mensual`. |
| `sql/cierre/02_build_fact.sql` | CTE A/B: el mes es `pm.anio_mes`; `fases_con_mes` deja de calcular mes y solo aporta `fase_id`, `fecha_inicio`, `nombre_mes` por `(obra, numero_fase = MAX(pm.version))`; `es_relleno = bool_and(pm.es_relleno)`. |
| `sql/cierre/04_views_detalle.sql` | Las dos vistas (`:128`, `:508`): mismo cambio, agrupan por `pm.anio_mes`. |
| `sql/cierre/06_views_planif_vs_real.sql` | §6. |
| `application/steps/build_stg_step.py` | `FICHEROS_DEL_SELLO` += `"00_functions.sql"` (R28, §9 R1). |
| `infrastructure/postgres/huella_obras.py` | `sql_huella_propuesta` lee el CTE final nuevo (`reales_final`), no `reales_con_lag`. |
| `main.py` | Comando `check-mes-fase` (solo lectura, §8). |
| `config/diccionario/{stg,mart,cierre,00_global}.yaml` | §7. |
| `docs/ARCHITECTURE.md` | Viñeta en «Semántica Sigrid»: el mes de un cierre real y el relleno. |
| `tests/test_f042_sql.py`, `test_f042_huella.py`, `test_f019_t13_portabilidad.py`, `test_f078_sql.py`, `test_f006_*` | Ajustes a la nueva estructura (nombres de CTE, ARRAY en 4 ramas, fichas nuevas). |

## 3 · Ficheros a crear

- `etl_sigrid/domain/mes_fase.py` — **oráculo puro** (sin dependencias):
  `parse_mes_fase(texto) -> date | None`, `mes_de_fase(fecha_inicio, nombre_mes,
  fecha_fin=None) -> date | None`, `meses_relleno(fases_vigentes) ->
  dict[fase, list[date]]` (R10, R11, R14) y `acumulado_relleno(serie, mes)` (R12).
  Mismas reglas que el SQL, token a token; es contra lo que se contrasta el SQL.
- `tests/test_f051_regla_mes.py` — dominio: R1–R6, R10–R14, R8+R11 juntos.
- `tests/test_f051_invariante.py` — casos generados con semilla fija (sin
  `hypothesis`, que no está en el proyecto): suma de `importe_mes` y último
  acumulado por partida idénticos con y sin relleno; ningún mes repetido.
- `tests/test_f051_sql.py` (estructural, §8) y `test_f051_check.py` (comando).
- `progress/impl_F-051.md` lo escribe el implementer.

## 4 · Las dos funciones de `stg`

`stg.fn_parse_mes_texto(texto TEXT) RETURNS DATE IMMUTABLE`. Parte del
parser de `cierre` (`cierre/00_setup.sql:36-97`) con tres cambios:
1. **Punto de millar**: antes de trocear, `(\d)\.(\d{3})` → `\1\2` («2.013» →
   «2013»).
2. **Año de dos cifras 00–19**: si ya hay mes y aún no hay año, un token de dos
   cifras 00–19 es el año 2000+n. Sin mes previo se conserva la lógica actual
   (un 1–12 sin mes es mes).
3. **Rango**: se recorren TODOS los tokens; cada token de mes sustituye al
   anterior y cada año de 4 cifras (o de 2, por la regla 2) también. Devuelve
   el último mes con el último año visto. «Enero 2020-Abril 2020» → 2020-04;
   «Diciembre 2014 - Enero 2015» → 2015-01; «Enero-Febrero 2011» → 2011-02;
   «DICIEMBRE 09 A FEBRERO 2010» → 2010-02; «SEPTIEMBRE-DICIEMBRE» → NULL.
   Un texto de un solo mes da lo mismo que hoy.

`stg.fn_mes_de_fase(fecha_inicio DATE, nombre_mes TEXT, fecha_fin DATE DEFAULT
NULL) RETURNS DATE IMMUTABLE`: las cuatro ramas de hoy (texto y fecha iguales →
fecha; distintos → texto; solo uno → ese) con una salvedad (R6, **D5**): si el
texto no parsea y `fecha_fin` cae en un mes posterior al de `fecha_inicio`,
devuelve el mes de `fecha_fin`. Con dos argumentos (lo que llama `cierre`) se
comporta como hoy salvo R3–R4.

Por qué un parser nuevo y no tocar el de `cierre`: `fn_parse_mes_fase` también
decide el mes de las versiones master de cierre (`cierre/02_build_fact.sql:143`)
y R3 cambiaría textos como «CIERRE ENERO-FEBRERO 25». F-051 no mide masters.

## 5 · La rama de reales de `08_plan_mensual.sql`

Todo entre `/*F042_INICIO_REALES*/` y `/*F042_FIN_REALES*/`, con **un solo**
marcador de tramo (el de `reales_base`) y toda ventana con `PARTITION BY`
encabezado por `obra_id` (lo vigila `test_f042_ninguna_ventana_del_fichero_cruza_obras`).

1. `reales_base`: `anio_mes = stg.fn_mes_de_fase(f.fecha_inicio, f.nombre_mes,
   f.fecha_fin)` (R7) en vez de `make_date(f.anio, f.mes, 1)`. Añade
   `mes_ini_fase = date_trunc('month', f.fecha_inicio)` y `es_rango =
   date_trunc('month', f.fecha_fin) > mes_ini_fase`. Filtro nuevo:
   `anio_mes IS NOT NULL` (hoy la guarda es `make_date`, que aborta).
2. `reales_cierres`, `reales_vigente`, `reales_orden`: **sin cambios de
   código**; al agrupar por el nuevo `anio_mes`, la regla de F-042 se aplica al
   mes del texto (R8).
3. `reales_con_lag`: sin cambios en los cuatro `CASE` del `LAG` (R9); arrastra
   `mes_ini_fase`, `es_rango`.
4. `reales_ocupados`: `DISTINCT (obra_id, ambito_id, anio_mes)` de
   `reales_con_lag` — los meses con cierre vigente propio (**D1**).
5. `reales_meses_relleno`: por fase vigente con `es_rango AND anio_mes >
   mes_ini_fase`, `generate_series(mes_ini_fase, anio_mes - 1 mes, 1 mes)`
   menos `reales_ocupados` (R10, R11, R14). Una fila por (obra, ámbito, fase,
   mes). Si el mes del texto es anterior o igual a `mes_ini_fase` (texto antes
   de las fechas, o texto = primer mes), no hay relleno.
6. `reales_esqueleto`: `reales_meses_relleno` × partidas de la fase generadora
   (sus filas de `reales_con_lag`), con acumulados NULL.
7. `reales_serie`: `UNION ALL` de las filas reales (con sus acumulados) y del
   esqueleto; por (obra, ámbito, partida) y `ORDER BY anio_mes`, arrastre del
   último acumulado no nulo con el truco de grupos de la rama master
   (`COUNT(x) OVER` + `MAX() OVER (PARTITION BY ..., grupo)`); sin anterior, 0
   (R12). Aplica a `importe_origen_round`, `importe_origen_raw`, `cantidad`,
   `total_incurrido_raw`.
8. `reales_final`: filas reales con `es_relleno = FALSE` + filas de relleno con
   `es_relleno = TRUE`, `importe_mes_* = 0`, `cantidad_mes = 0`,
   `total_incurrido_mes_calc = 0`, `version`/`posicion_mes` = fase generadora,
   `res_descripcion` = su texto, `precio` = el de la fila de su fase. Solo se
   conservan filas de relleno con acumulado arrastrado ≠ 0 o con `importe_mes`
   ≠ 0 en la fase generadora (R13, **D3**).

El `INSERT` de la rama de reales lee `reales_final` y escribe `es_relleno`; la
rama master escribe `NULL::BOOLEAN`. `huella_obras.sql_huella_propuesta` pasa a
leer `reales_final` con las mismas columnas y redondeos.

**Invariante por construcción**: el relleno solo añade filas con movimiento 0,
así que la suma de `importe_mes` por partida y el último acumulado son los de
hoy salvo donde R8 cambie qué fase manda (siete obras, §9 D2).

## 6 · `cierre.v_pbi_planif_vs_real`, blindada

- `base`: `GROUP BY obra_id, anio_mes, categoria, concepto`; `codigo_obra`,
  `nombre_obra`, `anio`, `mes` con `MAX()` (son función de la clave).
- `producc` y `total_costes`: `GROUP BY obra_id, anio_mes`. `beneficio`: JOIN
  por `(obra_id, anio_mes)`, el mismo grano de los dos lados (R19).
- `nombre_mes` se deriva **en la SELECT final** de `anio_mes` con el ARRAY sin
  locale; ningún CTE lo arrastra (R18).
- La lista de columnas y su orden no cambian: Power BI no nota nada salvo que
  deja de ver filas repetidas.

## 7 · Diccionario

`stg.yaml`: `plan_mensual.anio_mes` (en reales = mes del texto de la fase, con
la regla y el relleno), `plan_mensual.es_relleno`, `fases.nombre_mes` (el rango
se lee por su último mes) y fichas de `stg.fn_parse_mes_texto` y
`stg.fn_mes_de_fase`. `mart.yaml`: `fact_seguimiento_mensual.nombre_mes` (ya
no es texto libre en reales), `version_descripcion` (el texto de la fase),
`es_relleno`, y lo mismo en `v_pbi_fact`. `cierre.yaml`: `fact_cierre_mensual`
(mes = el de `stg`, `es_relleno`), `fn_mes_de_fase` (envoltorio de la de
`stg`), `v_pbi_planif_vs_real` (grano real y fin del fan-out: se retira el aviso
de F-051). `00_global.yaml`: sube `version`. Sin pendientes nuevos.
`azure-apps/datamart_seg_anual.md` no lista columnas: no cambia.

## 8 · Verificación

**Offline** (`bash harness/init.sh`): `test_f051_regla_mes.py` (tabla de
textos reales de `progress/spec_F-051.md` §3 → mes esperado; las cuatro
ramas; R6), `test_f051_invariante.py`, y `test_f051_sql.py`: 08 ya no contiene
`make_date(f.anio, f.mes, 1)` en reales y llama a `stg.fn_mes_de_fase`; un solo
marcador de tramo; `reales_final` dentro de los marcadores; las ramas 1 y 2 de
`mart/02` usan el ARRAY; `cierre/02` y `04` no llaman a `fn_mes_de_fase` y
agrupan por `pm.anio_mes`; la vista no tiene `nombre_mes` en ningún `GROUP BY`
ni `JOIN`; `FICHEROS_DEL_SELLO` contiene `00_functions.sql`; los prefijos de mes
del parser SQL son los del oráculo.

**Contra la base (MANUAL, humano)**, el protocolo de F-042/F-052 sobre el MISMO
`raw`: (1) huellas ANTES `--desde stg|mart|cierre`; (2) crear SOLO las dos
funciones de `stg` (escritura aditiva: la autoriza el humano) y
`huella-obras --propuesta`; (3) desplegar y reconstrucción completa; (4)
huellas DESPUÉS y `comparar-huellas` con la lista esperada que saca
`check-mes-fase --obras-esperadas`; (5) `check-unicidad` (la vista en OK, el
fact con `--timeout 300`), `check-cierres`, `check-mes-fase` (SQL = oráculo en
todas las fases; ninguna clave (obra, ámbito, partida, mes) repetida; relleno
siempre con movimiento 0 y nunca en un mes con cierre propio) y los testigos.

### Testigos (antes → después; cifras del build del 2026-09-22)

| Obra/fase | Texto · fechas | Hoy en `mart` | Después |
|---|---|---|---|
| 0650 f20 | «JUNIO 24» · feb–jun 2024 | feb-24: coste 40.785,46, venta 131.705,66 | jun-24 (como `cierre`); feb–may relleno |
| 0660 f28 | «Diciembre 2025» · may–dic | may-25: venta 124.690,46 | dic-25; may–nov relleno |
| 0664 f36 | «Mayo 2026» · ene–may | ene-26: coste 52.071,27 | may-26; ene–abr relleno |
| 0686 f2 | «Agosto 2024» · jun–ago | jun-24: coste 130.436,40 | ago-24; jun–jul relleno |
| 0683 f17 | «Diciembre 2025» · oct–dic | oct-25: generales 98.117,48 | dic-25; oct–nov relleno |
| 0646 f28 | «Septiembre 2024» · ago–sep | ago-24: venta 36.343,14 | sep-24; ago relleno |
| 0673 f8 | «Diciembre-24» · mar-2024 | mar-24 (0 €) | dic-24 (R2) |
| 0440 f3 | «Mayo 2015» · may-2015 | mar-15: coste 126.384,35 | may-15 (R2) |
| 0571 f21/f22 | rango ene–abr / «Agosto 2020» | may-20: f22; f21 descartada | abr-20 f21 y ago-20 f22 (R3, R8) |

## 9 · Riesgos

- **R1 · Reconstrucción completa**: 08 y `00_functions.sql` están (o entran) en
  `FICHEROS_DEL_SELLO`: la noche del despliegue se reconstruyen las 920 obras.
  Con el B2s temporal, 3 h 31 min en F-042; volver a B1ms antes empeora. Se
  despliega con el humano, fuera de horas y con la huella ANTES tomada.
- **R2 · Volumen**: estimado ~1,34 M filas de relleno (muestra de 25 fases:
  2.559 filas por fase con acumulado ≠ 0; 4.909 con todas las partidas). En
  `stg.plan_mensual` (29,9 M, 11 GB) es +4,5 %; en `mart.fact_seguimiento_mensual`
  (5,39 M, 2,27 GB) +25 %. Se mide en T-verificación; disco de 64 GB.
- **R3 · Meses cerrados que cambian en Power BI**: unos 500 cierres de 255 obras
  cambian de mes en `mart` (medición del líder), 17 con dinero desde 2024. Se
  avisa a Juan Romero antes de desplegar, con la lista.
- **R4 · Colisiones de F-042 sobre el mes del texto** (**D2**): 21 en vez de 24;
  19 iguales; nuevas 0444 dic-17 {21,26} y 0546 sep-19 {16,17}; desaparecen 5
  (0246, 0514, 0515, 0571, 0606): su fase descartada revive en su mes.
- **R5 · Rendimiento**: el arrastre del paso 7 es una ventana más sobre las filas
  reales de cada tramo; se mide el tramo más pesado antes de desplegar.
- **R6 · Coordinación con F-096**: toca la rama master del mismo fichero. Sin
  conflicto de líneas, pero las dos fuerzan la reconstrucción y las huellas se
  confunden si se despliegan juntas: primero F-051, F-096 se rebasa; si van la
  misma noche, 8/11 se atribuye a F-096 y 3/7 a F-051 (conjuntos disjuntos).
- **R7 · F-050**: su patrón 2 lo resuelve esta regla (D9).

## 10 · Decisiones para el humano (con recomendación)

- **D1 · Qué es «un mes que ya tiene datos».** (a) existe fila de cierre vigente
  de otra fase en esa (obra, ámbito, mes), valga lo que valga; (b) solo si su
  importe ≠ 0. **Recomiendo (a)**: un cierre a 0 es un cierre que Sigrid hizo;
  con (b) el relleno tendría que sustituir filas y rompería la clave. Medido: 25
  fases de rango tienen el mes de su cierre anterior dentro de sus fechas.
- **D2 · F-042 sobre el mes del texto**: misma regla (manda la más moderna con
  acumulado ≠ 0); la perdedora no genera relleno. **Recomiendo sí**; 7 obras
  cambian de reparto mensual (R4) sin cambiar su total, y 0606 f16 (todo a
  cero) reaparece en may-21 con acumulado 0 como ya pasa desde su f17.
- **D3 · Qué partidas llevan relleno**: las de acumulado anterior ≠ 0 o
  movimiento en la fase (~1,34 M filas) o todas (~2,56 M). **Recomiendo la
  primera**: el acumulado del mes es idéntico y cuesta la mitad.
- **D4 · Parser de fases** (R3 rango → último mes, R4 años 00–19 y «2.013»):
  73 textos con dos meses, 23 con año de dos cifras, 13 con punto. **Recomiendo
  sí**, solo en `stg` (masters intactos). Cambia `cierre` en esas fases.
- **D5 · Fase de rango sin texto legible → mes de `fecha_fin`** (43 hoy, menos
  tras D4). **Recomiendo sí**: es «considerar la fecha final» de Juan.
- **D6 · Texto = primer mes o intermedio** (59 + 16 fases de rango): el dinero
  queda en el mes del texto y los meses de después no se rellenan (R14).
  **Recomiendo** así y pasar la lista a Juan: rellenar hacia delante diría que
  el coste se paró, y eso no lo dice nadie.
- **D7 · Campaña de mutación** (C4 bis, rigor `critico`): **recomiendo** la
  misma exención que F-042, sustituida por las huellas y el invariante R21–R23.
- **D8 · Publicar `es_relleno`** en `stg`, `mart`, `v_pbi_fact` y `cierre`.
  **Recomiendo sí**: sin ella un mes a 0 de relleno no se distingue de uno sin
  actividad.
- **D9 · F-050**: **recomiendo** reducirla al patrón 1 (quincenas) y a la lista
  de anomalías para Juan; y fichar aparte los 5 huecos de numeración de Sigrid.
