<!-- progress/impl_F-078.md -->
# F-078 · Materializar FactCPTipologia · informe de implementación

Rama `feature/F-078-materializar-cp-tipologia`. Rigor **`critico`**, `sdd=false`:
el contrato son los diez `acceptance` de la ficha. Sin `tasks.md`, así que el
plan va aquí arriba para que el trabajo se pueda retomar si me cortan a mitad.

## Plan de tareas (un commit por tarea, `F-078 Tn: ...`)

- **T1** · Plan en este informe y apertura de la sección F-078 en
  `progress/current.md`.
- **T2** · Fase RED del SQL: `tests/test_f078_sql.py` sobre el TEXTO del SQL
  (tres tablas, las tres vistas leyendo de ellas, la lógica de negocio movida
  verbatim). Traza del fallo pegada.
- **T3** · `sql/mart/06_cp_tipologia.sql`: las tres tablas y las tres vistas.
  `build_mart_step` encadena el fichero y **cuenta las filas** de
  `mart.fact_cp_tipologia`.
- **T4** · Fase RED + `check-cp-tipologia`: la comparación cifra a cifra de la
  vista de antes contra la tabla nueva, como comando repetible
  (`cp_tipologia_sql.py` + `main.py`), para que el criterio 3 lo pueda ejecutar
  el humano cuando la nocturna acabe.
- **T5** · Diccionario: fichas de las tres tablas nuevas, las tres vistas
  actualizadas, **`R-COSTE-CONSULTA` corregida**, referencias de `cierre.yaml`,
  `stg.yaml` y `00_global.yaml`, versión 22 con su changelog, y los tests de
  F-006 / F-079 que hoy fijan lo contrario.
- **T6** · `azure-apps/datamart_seg_anual.md` y `docs/`.
- **T7** · `bash harness/init.sh` en verde, campaña de mutación y cierre del
  informe con la sección «Evidencias».


## Fase RED · el SQL (T2, rigor `critico`)

`tests/test_f078_sql.py` escrito ANTES del SQL. 66 tests, **65 en rojo**:

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

El unico verde de partida era `test_f078_r1_el_fichero_de_solo_vistas_ya_no_existe`,
y lo estaba **en falso**: `06_views_cp_tipologia.sql` si existia entonces. Es el
test que comprueba una ausencia, y por eso lleva su control al lado
(`test_f078_r5_el_fichero_del_sub_paso_existe_de_verdad`, que si fallaba).

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

**Honestidad sobre el alcance de esta RED**: el módulo
`cp_tipologia_sql.py` se escribió antes que sus tests de texto; lo que se
demostró en rojo es el comando. Lo que cubre de verdad la lógica del módulo es
la campaña de mutación de la sección «Evidencias». La fase RED completa, con el
SQL inexistente, es la de T2.

## Qué cambió

| Fichero | Qué |
|---|---|
| `sql/mart/06_views_cp_tipologia.sql` → **`06_cp_tipologia.sql`** | Ya no crea solo vistas: crea las TRES TABLAS y luego las tres vistas que las envuelven |
| `application/steps/build_mart_step.py` | `SUB_PASOS` sale de `run()` a nivel de módulo (como en `build_compras_step`); el sub-paso `cp_tipologia` cuenta las filas de `mart.fact_cp_tipologia` |
| `infrastructure/postgres/cp_tipologia_sql.py` (nuevo) | La fotografía congelada del cálculo anterior a F-078 y la consulta de comparación. Solo construye texto |
| `main.py` | Comando `check-cp-tipologia` (+ su línea en el índice de comandos) |
| `tests/test_f078_sql.py` (nuevo) | 113 tests sobre el TEXTO del SQL y del módulo. Ni red ni BBDD |
| `config/diccionario/mart.yaml` | Tres fichas nuevas; las tres vistas actualizadas |
| `config/diccionario/00_global.yaml` | **R-COSTE-CONSULTA corregida**, `R-VERSION-MASTER` alcanza las tablas, versión **22** con changelog |
| `tests/test_f006_fichas.py`, `tests/test_f079_stg_consultable.py` | Los tests que fijaban lo contrario, corregidos; uno nuevo impide que el aviso caducado vuelva |
| `specs/F-006-mcp-azure/design.md`, `progress/current.md` | Inventario a **153** objetos, 964 columnas, 66 fichas de consumo |
| `azure-apps/datamart_seg_anual.md` | Commit `db7c91e` en ese repositorio: toda `v_pbi_` tiene ya tabla detrás |

**Lo que NO se ha tocado, a propósito**: `config/objetos_pendientes.yaml` sigue
vacío (los objetos nuevos nacen construidos, no pendientes); no hay `GRANT` uno
a uno, porque `apply_grants` hace `GRANT SELECT ON ALL TABLES IN SCHEMA mart` y
corre el último de `run-all`; `cierre.yaml` y `stg.yaml` siguen apuntando a las
vistas, que conservan nombre y columnas; y `inspect-cp-tipologia` no cambia.

## Decisiones de diseño

1. **Un solo fichero SQL y una sola transacción.** `execute_sql_file` manda el
   texto entero en una llamada, así que los seis objetos se rehacen o no se
   toca ninguno. No hay ventana en la que Power BI encuentre la vista ausente.
   Es lo que evita repetir la avería de `03_agg_categoria.sql`, que dropeaba con
   `CASCADE` una vista de `cierre` que nadie recreaba.
2. **`CREATE TABLE ... AS SELECT`** y no DDL explícito: las tablas heredan el
   tipo de la proyección —`NUMERIC(18,2)` incluido— y la puerta de F-006
   contrasta sus columnas contra esa proyección, exactamente igual que con las
   siete tablas de `compras`. Con DDL a mano habría dos sitios que mantener.
3. **Sin índices.** Son decenas de miles de filas: un `seq scan` sobre eso es
   trivial. Añadir índices a una tabla que se dropea y rehace cada noche es
   trabajo de build a cambio de nada.
4. **La vigencia anual se calcula contra la TABLA de versiones, no contra la
   vista.** Es la decisión que mata el `WindowAgg` de 11,8 M de filas: con la
   vista, el plan volvería a barrer `stg.plan_mensual` por debajo y las tablas
   no habrían ahorrado nada. Tiene su test.
5. **El sub-paso cuenta el HECHO y no los dos helpers.** Un `_SubStep` cuenta
   una tabla. Se elige la que delata a las tres: sin versiones vigentes no hay
   filas de hecho. Mismo criterio que `compras.texto`, que cuenta los
   comentarios y no el memo.
6. **La comparación es un comando y no una consulta de usar y tirar.** El
   criterio 3 no se puede ejecutar hoy (hay una nocturna en curso y las tablas
   aún no existen), así que tenía que quedar algo repetible y versionado. Y como
   la vista ahora lee de la tabla, compararlas sería una tautología: de ahí la
   fotografía congelada, que recalcula desde `stg`.

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
