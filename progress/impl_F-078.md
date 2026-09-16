<!-- progress/impl_F-078.md -->
# F-078 · Materializar FactCPTipologia · informe de implementación

Rama `feature/F-078-materializar-cp-tipologia`. Rigor **`critico`**, `sdd=false`:
el contrato son los diez `acceptance` de la ficha. Sin `tasks.md`, el plan va
aquí arriba para poder retomar el trabajo si me cortan a mitad.

## Plan de tareas (un commit por tarea, `F-078 Tn: ...`)

- **T1** · El plan aquí y la sección F-078 de `progress/current.md`.
- **T2** · **Fase RED del SQL**: `tests/test_f078_sql.py`, sobre el TEXTO.
- **T3** · `sql/mart/06_cp_tipologia.sql` y el sub-paso que cuenta sus filas.
- **T4** · Fase RED + `check-cp-tipologia`, para que el criterio 3 lo pueda
  ejecutar el humano en cuanto la nocturna acabe.
- **T5** · Diccionario: fichas nuevas, **`R-COSTE-CONSULTA` corregida**,
  versión 22, y los tests de F-006 / F-079 que fijaban lo contrario.
- **T6** · `azure-apps/datamart_seg_anual.md`, y el comando endurecido contra
  lo que destapó una primera campaña de mutación.
- **T7** · `init.sh` en verde, campaña medida y sección «Evidencias».

## Fase RED · el SQL (T2, rigor `critico`)

`tests/test_f078_sql.py`, escrito ANTES del SQL: 66 tests, **65 en rojo**.

```
$ python -m pytest tests/test_f078_sql.py -q
...
FAILED tests/test_f078_sql.py::test_f078_r3_las_filas_a_cero_siguen_sin_publicarse
FAILED tests/test_f078_sql.py::test_f078_r4_las_vistas_proyectan_exactamente_lo_de_siempre[v_pbi_cp_tipologia]
FAILED tests/test_f078_sql.py::test_f078_r5_el_sub_paso_cuenta_las_filas_del_hecho
65 failed, 1 passed in 1.79s
```

Las dos trazas que sostienen los dos requisitos centrales:

```
>       assert f"CREATE TABLE mart.{tabla} AS" in _ejecutable(), (
tests\test_f078_sql.py:101:
    @cache
    def _sql() -> str:
>       assert RUTA_CP.exists(), f"SQL no encontrado: {RUTA_CP}"
E       AssertionError: SQL no encontrado: C:\Users\pgris\PycharmProjects\
E       datamart-seg-anual\etl_sigrid\infrastructure\postgres\sql\mart\06_cp_tipologia.sql
```

```
>       return build_mart_step.SUB_PASOS
E       AttributeError: module 'etl_sigrid.application.steps.build_mart_step'
E       has no attribute 'SUB_PASOS'
tests\test_f078_sql.py:427: AttributeError
```

El unico verde de partida, `test_f078_r1_el_fichero_de_solo_vistas_ya_no_existe`,
lo estaba **en falso**: `06_views_cp_tipologia.sql` si existia entonces. Es el
test que comprueba una ausencia, y por eso lleva su control al lado.

## Fase RED · el comando de comparación (T4)

`check-cp-tipologia` compara la **fotografía congelada** del cálculo anterior a
F-078 (recalculada desde `stg`) contra la tabla nueva. Antes de escribirlo, sus
tests en rojo:

```
$ python -m pytest tests/test_f078_sql.py -q -k "r6 and comando"
E       AssertionError: Usage: cli [OPTIONS] COMMAND [ARGS]...
E         Error: No such command 'check-cp-tipologia'.
E           (Did you mean one of: 'check-pg', 'inspect-cp-tipologia'?)
E       assert 2 == 0
FFFF  4 failed
```

**Honestidad sobre el alcance de esta RED**: `cp_tipologia_sql.py` se escribió
antes que sus tests de texto; lo que se demostró en rojo es el comando. Lo que
cubre la lógica del módulo es la campaña de mutación. La fase RED completa, con
el SQL inexistente, es la de T2.

## Qué cambió

| Fichero | Qué |
|---|---|
| `sql/mart/06_views_cp_tipologia.sql` → **`06_cp_tipologia.sql`** | Ya no crea solo vistas: crea las TRES TABLAS y luego las tres vistas que las envuelven |
| `application/steps/build_mart_step.py` | `SUB_PASOS` sale de `run()` a nivel de módulo (como en `build_compras_step`); el sub-paso `cp_tipologia` cuenta las filas de `mart.fact_cp_tipologia` |
| `infrastructure/postgres/cp_tipologia_sql.py` (nuevo) | La fotografía congelada del cálculo anterior a F-078 y la consulta de comparación. Solo construye texto |
| `main.py` | Comando `check-cp-tipologia` (+ su línea en el índice de comandos) |
| `tests/test_f078_sql.py` (nuevo) | **127 tests** sobre el TEXTO del SQL y del módulo. Ni red ni BBDD |
| `config/diccionario/mart.yaml` | Tres fichas nuevas; las tres vistas actualizadas |
| `config/diccionario/00_global.yaml` | **R-COSTE-CONSULTA corregida**, `R-VERSION-MASTER` alcanza las tablas, versión **22** con changelog |
| `tests/test_f006_fichas.py`, `tests/test_f079_stg_consultable.py` | Los tests que fijaban lo contrario; uno nuevo impide que el aviso caducado vuelva |
| `specs/F-006-mcp-azure/design.md`, `progress/current.md` | Inventario a **153** objetos, 964 columnas, 66 fichas de consumo |
| `azure-apps/datamart_seg_anual.md` | Commit `db7c91e` **en ese repositorio** (su dueño): toda `v_pbi_` tiene ya tabla detrás |

**Lo que NO se ha tocado, a propósito**: `config/objetos_pendientes.yaml` sigue
vacío (los objetos nuevos nacen construidos, no pendientes); no hay `GRANT` uno
a uno, porque `apply_grants` hace `GRANT SELECT ON ALL TABLES IN SCHEMA mart` y
corre el último de `run-all`; `cierre.yaml` y `stg.yaml` siguen apuntando a las
vistas, que conservan nombre y columnas; y `inspect-cp-tipologia` no cambia.

## Decisiones de diseño

1. **Un solo fichero SQL y una sola transacción.** `execute_sql_file` manda el
   texto entero en una llamada: los seis objetos se rehacen o no se toca
   ninguno, y no hay ventana en la que Power BI encuentre la vista ausente. Es
   lo que evita repetir la avería de `03_agg_categoria.sql`.
2. **`CREATE TABLE ... AS SELECT`** y no DDL explícito: las tablas heredan el
   tipo de la proyección —`NUMERIC(18,2)` incluido— y la puerta de F-006
   contrasta sus columnas contra ella, como con las siete de `compras`.
3. **Sin índices**: son decenas de miles de filas y la tabla se rehace cada
   noche. Sería trabajo de build a cambio de nada.
4. **La vigencia anual se calcula contra la TABLA de versiones, no contra la
   vista.** Es la decisión que mata el `WindowAgg` de 11,8 M de filas: con la
   vista, el plan volvería a barrer `stg.plan_mensual` por debajo y las tablas
   no habrían ahorrado nada. Tiene su test.
5. **El sub-paso cuenta el HECHO y no los dos helpers.** Un `_SubStep` cuenta
   una tabla; se elige la que delata a las tres, porque sin versiones vigentes
   no hay filas de hecho. Mismo criterio que `compras.texto`.
6. **La comparación es un comando y no una consulta de usar y tirar.** El
   criterio 3 no se puede ejecutar hoy, así que tenía que quedar algo repetible
   y versionado. Y como la vista ahora lee de la tabla, compararlas sería una
   tautología: de ahí la fotografía congelada, que recalcula desde `stg`.

## Desviaciones y riesgos, declarados

* **`CURRENT_DATE` se congela en el build.** Es inherente a materializar y es el
  único cambio de semántica. El "año en curso" y el "mes de corte" pasan a ser
  los de la noche de la carga. Con refresco nocturno solo se nota el día 1 de
  cada mes antes de que corra `run-all`. Está escrito en la cabecera del SQL,
  en la ficha del diccionario y en el `--help` del comando de comparación.
  **Consecuencia práctica**: `check-cp-tipologia` hay que lanzarlo el mismo día
  en que se construyó la tabla, o las dos mitades cortan en meses distintos.
* **El build nocturno se alarga.** El cálculo pasa de hacerse en cada consulta
  a hacerse una vez de noche. No se ha podido cronometrar: ver más abajo.
* **El fichero SQL se renombró.** Si alguien resucita
  `06_views_cp_tipologia.sql`, habría dos definiciones de los mismos objetos y
  el build ejecutaría la que esté en `SUB_PASOS`. Hay un test que lo impide.

## VERIFICACIONES MANUAL (humano) · pendientes, y por qué

**Hay una nocturna en curso** (job lanzado a mano con la imagen
`r20260915-1014`, `run-all --full`, ~3 h 30). `build_mart` dropea y reconstruye:
cruzarse con ella es buscarse un problema, así que **no se ha ejecutado ninguna
escritura contra Azure**. La autorización del humano del 2026-09-09 para
construir las tres tablas a mano es ANTERIOR a esta nocturna.

Cuando haya terminado, **en este orden y el mismo día**:

| # | Comando | Qué hay que anotar | Criterio |
|---|---|---|---|
| 1 | `python main.py build-mart` | El **tiempo** del sub-paso `cp_tipologia` (log `mart_substep_done`) y sus **filas**, y cuánto crece `build_mart` entero | 1, 4 |
| 2 | `python main.py check-cp-tipologia` | El **número de diferencias**. Tiene que ser **0** | 3 |
| 3 | `time psql ... -c "SELECT * FROM mart.v_pbi_cp_tipologia"` (o el MCP) | Cuánto tarda ahora, con el dato real | 4, 8 |
| 4 | `python main.py inspect-cp-tipologia --obra <obra> --anio 2025` | Que el mapping CP.x → tipología sigue saliendo | 9 |
| 5 | `python main.py check-declarados` | En verde **sin tocar** `objetos_pendientes.yaml`, que sigue vacío | 7 |
| 6 | `python main.py check-diccionario` | Biyección exacta: **153 fichas y 153 objetos** | 6 |
| 7 | `python main.py publicar-diccionario` | Sube a la **versión 22**. Es la única escritura que no es el build | 5, 6 |
| 8 | Abrir el `.pbix` y refrescar **FactCPTipologia** | Que carga **sin tocar una línea** del `.pq` | 2 |

**El 2 es delicado**: recalcula la vista de antes, *la consulta que no terminaba
en 60 s* (con `--obra` se desploma y sirve de sonda), y hay que lanzarlo **el
mismo día** del build: la mitad izquierda evalúa `CURRENT_DATE` ahora y la
derecha lo lleva congelado.

## Lo que SÍ se pudo medir contra Azure sin escribir

`EXPLAIN` **planifica, no ejecuta**: es una lectura. Con él, el 2026-09-15:

* La fotografía del cálculo anterior **planifica**: `GroupAggregate
  (cost=8928225.79..8931862.36 rows=19395)`. Esos **8,93 M de unidades** son el
  precio de la vista de antes, medido hoy, del orden de los 6,6 M de la ficha.
* Los **seis objetos** del SQL nuevo y las **tres consultas** del comando
  **parsean**: `master_versiones_tipadas` planifica, y el resto contesta
  `UndefinedTable` —la tabla de la que dependen aún no existe— y **no
  `SyntaxError`, que es lo que se estaba comprobando**.
* **El `CASCADE` no se lleva nada de nadie.** Consultado `pg_depend` en la base
  real: los únicos dependientes de las tres vistas son **ellas mismas entre sí**
  (`v_master_vigente_anual` <- `v_master_versiones_tipadas`,
  `v_pbi_cp_tipologia` <- `v_master_vigente_anual`), y las tres se recrean en el
  mismo fichero y la misma transacción. Era el riesgo real de repetir la avería
  de `03_agg_categoria.sql`, y está descartado con el catálogo delante.
* **NO COMPROBADO**: `count(*)` de `mart.v_master_versiones_tipadas` agotó los
  **180 s** (la ficha lo midió en 16 s el 2026-08-25). No es un fallo del
  código: el servidor está con la nocturna encima. Queda sin medir cuántas filas
  tendrá la tabla.

## Evidencias

| Evidencia | Valor medido |
|---|---|
| **Tests ejecutados** | **4.826 pasan, 188 saltados, 0 fallos** (`bash harness/init.sh`). De ellos **127 son de F-078** |
| **Cobertura de las líneas cambiadas** | **94,3 %** (901/955), umbral 80 %, nivel `critico` — línea `PUERTA COBERTURA` de `init.sh` |
| **Tiempo de la suite** | **447,7 s** dentro de `init.sh` (con cobertura); **223 s** sin ella |
| **Mutantes y supervivientes** | **34 generados, 34 evaluados, 34 muertos, 0 supervivientes**, 0 timeouts, 0 sin veredicto, en **3.047 s** (`progress/mutacion_F-078.md`) |
| **Tamaño del papeleo** | `PUERTA TAMAÑO: F-078 dentro de los topes (impl 220/220)` |

**Sobre la campaña, y lo que el reviewer tiene que poder comprobar (RM1/RM2)**:
SHA medido `0b877f5`, cuatro worktrees, línea base entre 371,5 s y 377,0 s,
timeout derivado de ~754 s por mutante. Se lanzó con **`--base main`** y no con
el `dev` por defecto: `dev` lleva meses de retraso, y contra él el alcance sube
a 15 ficheros y ~5.000 líneas que son de F-073, F-080 y F-081 y que ya midieron
sus propias campañas. Con `main` —que ES la base común de esta rama— el alcance
son los **tres ficheros** que toca F-078: `cp_tipologia_sql.py` (391 líneas),
`main.py` (100) y `build_mart_step.py` (57).

**Análisis de supervivientes: no hay ninguno que analizar.** No salió así a la
primera. Una campaña previa sobre el commit `28b859b` destapó que
`TIMEOUT_POR_CONSULTA_S`, el recorte a 50 filas, el color del veredicto y la
posición de cada columna de la fila de diferencia **no los miraba ningún test**,
y que `CLAVES` y `MEDIDAS` eran **constantes muertas**. Eso se cerró en T6 —las
listas ahora generan el `ON` y el `WHERE`, y hay test para cada detalle— antes
de medir la campaña que se reporta aquí. Los mutantes que lo confirman están en
el informe: `[:50] -> [:51]`, `> 50 -> >= 50`, `f[6] -> f[7]`, `is_flag=True ->
False`, `SystemExit(1) -> SystemExit(2)`, todos **muertos**.

**Fidelidad de la fotografía congelada**, que es lo único que un reviewer no
puede comprobar ejecutando: se copió del `06_views_cp_tipologia.sql` del commit
`b208a59` con dos cambios que no alteran el resultado y conviene declarar —los
dos helpers pasan a CTE, y `codigo_partida` sale del `GROUP BY` de `real_anual`
y `plan_anual` porque `partida_id`, que sigue agrupando, lo determina—. La
cascada de tipologías, el corte temporal, el tipado del master y el orden de la
matriz están fijados cadena a cadena contra el SQL del build
(`test_f078_r6_la_fotografia_conserva_la_logica_de_negocio`, 22 casos).
