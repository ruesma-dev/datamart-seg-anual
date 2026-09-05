<!-- progress/impl_F-025_metodo_ausente.md -->
# F-025 · El método que tumbó la nocturna, y el agujero por el que pasó

Arreglo de la incidencia de `progress/incidencia_F-025_nocturna_20260905.md`:
`AttributeError: 'PostgresClient' object has no attribute 'fetch_filas_por_obra'`
en la primera nocturna con F-025, sobre **3.308 tests en verde**.

Tres commits en `feature/F-025-ventana-negocio-build`:

| commit | qué |
|---|---|
| `a9e51ed` | T1 · `fetch_filas_por_obra` implementado, con sus tests |
| `202f0e4` | T2 · el contrato del cliente, comprobado en las dos direcciones |
| `481f6ca` | T3 · la lección en C4 y portada a `arnes-base` (allí, `9dd4f1f`) |

## T1 · El método

`etl_sigrid/infrastructure/postgres/postgres_client.py`, junto a
`registrar_obras_construidas`, que es su pareja: de aquí sale la columna `filas`
de `_meta.obra_build`.

- **`SQL_FILAS_POR_OBRA`** cuenta por `obra_id` **acotando por `WHERE obra_id =
  ANY(%(obras)s)`**. El filtro no es decoración: sin él sería un `GROUP BY`
  sobre los 29,7 M de `plan_mensual` cada noche en un `B1ms` sin créditos, más
  caro que el propio tramo. Se cuenta solo lo que se acaba de construir.
- **Obras sin filas: SIN clave** (no salen del `GROUP BY`). Lo pedía el
  encargo por escrito y está en el docstring: el diccionario dice lo que
  respondió la base, no lo que suponemos que habría respondido; inventar un `0`
  por obra pedida afirmaría «la miré y estaba vacía» también donde la consulta
  no llegó. Quien llama ya resuelve con `filas.get(obra_id, 0)`
  (`build_stg_step.py:628`), así que el contrato encaja sin tocar el step.
- **Lista vacía: ni conexión**. El sub-paso puede quedarse sin obras (R9).
- **`tabla` validada contra `TABLAS_ACOTADAS`** antes de interpolarse, como
  `fetch_obras_con_filas`. La lista blanca pasa a `_exigir_tabla_acotada()`,
  compartida por las dos: eran dos copias del mismo `raise` y ahora es una.

**No se ha tocado `build_stg_step.py`**: la llamada de `_registrar_construidas`
era correcta; lo que faltaba era el método.

### Fase RED de T1

`tests/test_f025_sql.py`, escritos antes que el código. Salida real:

```
$ python -m pytest tests/test_f025_sql.py -x -q
ERROR collecting tests/test_f025_sql.py
tests\test_f025_sql.py:30: in <module>
    from etl_sigrid.infrastructure.postgres.postgres_client import (
E   ImportError: cannot import name 'SQL_FILAS_POR_OBRA' from
    'etl_sigrid.infrastructure.postgres.postgres_client'
1 error in 1.43s
```

Tras implementar: `32 passed in 0.86s`.

## T2 · El modo de fallo, cerrado

`tests/test_f025_contrato_cliente.py` (nuevo, 9 tests). Cruza el contrato de
`PostgresClient` **en las dos direcciones y sin lista escrita a mano**: recorre
`tests/` con `ast` y toma por doble toda clase —anidada incluida— que declare
≥ 2 métodos públicos con nombre de la API real. Ese listón lo pasan los 19
dobles del árbol y no lo cruza por casualidad una clase que no imita nada.

1. **Ningún doble declara un método que el cliente no tenga.** Excepción: las
   ayudas de aserción, que hay que declarar en `AYUDAS_DEL_DOBLE` dentro de la
   clase. Añadir un método sin querer sale en rojo; a propósito cuesta una línea.
2. **Ningún doble acepta llamadas que el cliente real rechazaría**: más
   posicionales, un `keyword-only` colado por posición, otro nombre en el mismo
   hueco. Es la dirección peligrosa —el test pasa y producción revienta—.
3. **Y al revés: todo lo que producción invoca sobre un parámetro anotado
   `PostgresClient` existe en la clase.** Esta habría dado rojo *aunque ningún
   doble hubiera declarado el fantasma*, que es el hueco de verdad.

Hay dos «controles del control» (el barrido encuentra los dobles conocidos; el
barrido de producción ve ≥ 20 usos), porque una detección rota pasaría en vacío.

### Fase RED de T2, y prueba de que caza el fallo original

Con el árbol tal y como estaba **antes** del arreglo:

```
$ python -m pytest tests/test_f025_dobles.py -q
E       AssertionError: métodos fantasma:
E         test_f006_publicacion.py:863 _PgDeCli.record_run no existe en PostgresClient
E         test_f019_tramos.py:540 PgFalso.fetch_filas_por_obra no existe en PostgresClient
E         test_f024_steps.py:165 PgFalso.fetch_filas_por_obra no existe en PostgresClient
E         test_f024_steps.py:184 PgFalso.escrituras no existe en PostgresClient
E         test_f024_steps.py:188 PgFalso.cierre_de no existe en PostgresClient
E         test_f025_build.py:300 PgVentana.fetch_filas_por_obra no existe en PostgresClient
E       AssertionError: firmas incompatibles:
E         test_f019_tramos.py:612 PgFalso.execute_sql_file acepta 2 posicionales y el cliente real 1 (params es solo-clave en el real)
E         test_f019_tramos.py:619 PgFalso.assert_columns_exist el posicional 2 se llama 'columnas' y en el cliente real 'required_columns'
E         test_f024_steps.py:107 PgFalso.execute_sql_file acepta 2 posicionales y el cliente real 1 (params es solo-clave en el real)
E         test_f024_steps.py:118 PgFalso.assert_columns_exist el posicional 2 se llama 'cols' y en el cliente real 'required_columns'
E         test_f025_build.py:357 PgVentana.execute_sql_file acepta 2 posicionales y el cliente real 1 (params es solo-clave en el real)
E         test_f025_build.py:364 PgVentana.assert_columns_exist el posicional 2 se llama 'columnas' y en el cliente real 'required_columns'
E         test_f025_cli.py:78 PgSoloLectura.filas_solo_lectura el posicional 0 se llama 'sql' y en el cliente real 'sql_text'
2 failed, 6 passed in 7.50s
```

Y la prueba directa de que el control ataja **exactamente** la avería del 05:
renombrando a mano `fetch_filas_por_obra` en el cliente, con todo lo demás ya
arreglado, el fichero vuelve a rojo por los dos lados:

```
E       AssertionError: producción llama a lo que PostgresClient no tiene:
E         fetch_filas_por_obra · etl_sigrid/application/steps/build_stg_step.py:628
E       AssertionError: métodos fantasma:
E         test_f019_tramos.py:540 PgFalso.fetch_filas_por_obra no existe en PostgresClient
E         test_f024_steps.py:167 PgFalso.fetch_filas_por_obra no existe en PostgresClient
E         test_f025_build.py:300 PgVentana.fetch_filas_por_obra no existe en PostgresClient
2 failed, 7 passed in 5.22s
```

(árbol restaurado tras la prueba; comprobado byte a byte)

### El barrido: ¿había más métodos fantasma?

**No.** El único fantasma que producción llegaba a llamar era
`fetch_filas_por_obra`, en tres dobles. Lo demás que sacó el barrido, y qué era:

| hallazgo | veredicto |
|---|---|
| `_PgDeCli.record_run` (`test_f006_publicacion`) | **código muerto**: no existe en el cliente y no lo llama ni un test. **Borrado**, no inventado |
| `PgFalso.escrituras`, `.cierre_de` (`test_f024_steps`) | ayudas de aserción de verdad → **declaradas** en `AYUDAS_DEL_DOBLE` |
| `execute_sql_file(path, params)` en 3 dobles | `params` es **solo-clave** en el cliente: los dobles lo aceptaban por posición. Corregido |
| `assert_columns_exist(..., columnas/cols)` en 3 dobles | el cliente lo llama `required_columns`. Renombrado |
| `filas_solo_lectura(sql, …)` (`test_f025_cli`) | el cliente lo llama `sql_text`. Renombrado |

Barrido extendido a los otros dos originales con dobles en el árbol
(`SigridApiClient`, 2 dobles; `PostgresStepRunRecorder`): **cero fantasmas**.
El agujero de F-019 produjo uno solo, y ya no puede producir otro sin rojo.

## T3 · La lección

`CHECKPOINTS.md`, bloque **C4**: un punto nuevo que exige la comprobación
automática de los dobles contra su original, por barrido y no por lista escrita
a mano, con el caso del 2026-09-05 como justificación —incluida la parte
incómoda: **no lo caza la lectura**, porque el doble es coherente por su lado y
el código que lo llama por el suyo, y cuatro pasadas de reviewer no lo vieron.

Portado a `arnes-base` **en este mismo trabajo** (regla de propagación):
`arnes-base/CHECKPOINTS.md` con el mismo bloque, su sección en
`GUIA_INSTALACION.md` y `harness/VERSION` a **1.7.9 (2026-09-05)**; commit
`9dd4f1f` de aquel repositorio. No se ha reinstalado el arnés aquí: este
repositorio sigue en la **1.7.7** y el cambio se porta a mano por ser su origen.

## Ficheros tocados

- `etl_sigrid/infrastructure/postgres/postgres_client.py` — `SQL_FILAS_POR_OBRA`,
  `_exigir_tabla_acotada()`, `fetch_filas_por_obra()`.
- `tests/test_f025_contrato_cliente.py` — **nuevo**.
- `tests/test_f025_sql.py` — 4 tests nuevos y dos existentes ampliados.
- `tests/test_f006_publicacion.py`, `test_f019_tramos.py`, `test_f024_steps.py`,
  `test_f025_build.py`, `test_f025_cli.py` — dobles alineados con el original.
- `CHECKPOINTS.md`; y fuera del repo, `arnes-base` (3 ficheros).

## Evidencias

| Evidencia | Número real |
|---|---|
| Tests ejecutados | **3.321 pasados, 134 saltados**, 0 fallos (`bash harness/init.sh`, con cobertura) |
| Cobertura de las líneas cambiadas | **91,9 %** — `PUERTA COBERTURA: 588/640, umbral 80 %, nivel critico` |
| Mutantes generados y supervivientes | campaña completa **no relanzada** (ver abajo); **mutación manual: 7 mutantes, 7 muertos, 0 supervivientes** |
| Tiempo de la suite | **436,0 s** dentro de `init.sh` con cobertura; **200,7 s** sin ella |
| Puerta de tamaño | `F-025 dentro de los topes (impl 220/220, review 121/140)` |

`bash harness/init.sh` termina en **`ENTORNO LISTO. Puedes trabajar.`**

### Mutación: qué se hizo y qué no

La campaña completa de F-025 **está eximida por el humano** (DA-6, registrada en
`harness/features.json` el 2026-09-04) y `--feature F-025` volvería a mutar el
diff entero de la rama, 219 mutantes y horas de máquina. En su lugar, mutación
**manual acotada a las líneas nuevas**, con la suite de F-025 como juez:

```
M1 quitar la lista blanca:                        MUERTO :: 3 failed, 80 passed
M2 invertir el corte por lista vacia:             MUERTO :: 3 failed, 80 passed
M3 el valor pasa a ser la clave:                  MUERTO :: 1 failed, 82 passed
M4 invertir el filtro de nulos:                   MUERTO :: 1 failed, 82 passed
M5 la consulta deja de acotarse a las obras:      MUERTO :: 1 failed, 82 passed
M6 el parametro viaja vacio:                      MUERTO :: 1 failed, 82 passed
M7 la lista blanca deja pasar todo:               MUERTO :: 3 failed, 80 passed
arbol restaurado: True
```

**Y una anécdota que viene al caso, contada porque casi cuela.** La primera
vuelta de esa tabla dio 6/6 «MUERTO» y era **falsa**: el `subprocess` llamaba a
`python` por PATH y caía en el intérprete del sistema, que no tiene `pytest`;
el `returncode 1` de `No module named pytest` se leía como mutante muerto. Se
detectó porque el resumen de pytest venía vacío. Repetido con `sys.executable`,
7/7 muertos de verdad. Es el mismo modo de fallo que esta feature arregla: **un
verde —o un rojo— que nadie cruzó con lo que decía medir.**

## Lo que queda fuera y lo que falta

- **No se ha lanzado nada contra producción**: ni `stage`, ni `run-all`, ni
  escrituras en el Postgres de Azure. Solo lecturas y tests locales.
- **Pendiente (humano)**: reconstruir con el arreglo —imagen nueva y job—, y
  después la fase 7 de F-025, que sigue donde la dejó la incidencia: **T29 no se
  ha ejecutado**, así que **T30 (huellas del DESPUÉS) no se puede hacer**. Las
  cinco huellas del ANTES en `huellas/antes_*.csv` siguen válidas: el fallo cayó
  tras construir el tramo y no destruyó nada (`stg` con sus cifras de siempre).
- **T1 sigue sin medir de verdad**: `_meta.obra_build` continúa vacía, y hasta
  que una nocturna la pueble el ahorro medido será 0 % por diseño.
- La feature **no se marca `done`**: eso es del reviewer tras APROBADO.
