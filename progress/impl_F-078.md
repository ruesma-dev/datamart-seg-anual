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
