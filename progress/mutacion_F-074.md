<!-- progress/mutacion_F-074.md -->
# F-074 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-074` el 2026-09-09 16:23.

## Alcance

Origen del diff: **rama** (`cd18e0962b63edcc0017907b8c69a29352e433c4` .. `feature/F-074-ingesta-tablas-del-censo`).

| Fichero | Líneas en alcance |
|---|---|
| `config/settings.py` | 108 |
| `etl_sigrid/application/steps/apply_grants_step.py` | 18 |
| `etl_sigrid/application/steps/build_stg_step.py` | 613 |
| `etl_sigrid/application/steps/ingest_raw_step.py` | 70 |
| `etl_sigrid/domain/cobertura.py` | 35 |
| `etl_sigrid/domain/huella_ampliada.py` | 20 |
| `etl_sigrid/domain/recuentos.py` | 286 |
| `etl_sigrid/domain/tramos.py` | 4 |
| `etl_sigrid/domain/ventana.py` | 784 |
| `etl_sigrid/infrastructure/postgres/grants.py` | 101 |
| `etl_sigrid/infrastructure/postgres/huella_ampliada.py` | 33 |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | 723 |
| `etl_sigrid/infrastructure/postgres/ventana_sql.py` | 246 |
| `main.py` | 486 |
| **Total** | **3527** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 288 |
| Mutantes evaluados | 20 |
| Muertos | 12 |
| Supervivientes | 8 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 1563.8 s |
| SHA de HEAD medido | `08832c42a8e6c5b53fb50acd47ed306b140d2f4d` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-074_l23k_guo/wk_0` | 232.0 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-074_l23k_guo/wk_1` | 234.0 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-074_l23k_guo/wk_2` | 236.4 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-074_l23k_guo/wk_3` | 232.6 |
| Media por mutante evaluado (s) | 78.2 |
| Timeout efectivo por mutante (s) | 473 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 4 |
| Muestreo | sí — 20 de 288 mutantes, semilla `20260820`, nivel `estandar` |

## La muestra de 20, reproducida

Los 288 mutantes se muestrean a 20 con la semilla del nivel `estandar`
(`harness/rigor.json`). **Reproducida de forma independiente** tras el review de
la pasada 1, con el mismo procedimiento que usa la herramienta
--`random.Random(20260820).sample(mutantes, 20)` sobre los mutantes generados en
el orden de `alcance.ficheros()`, ordenados despues por
`(fichero, linea, col, operador)`-- y sin ejecutar la suite. Se lista aqui porque
la pasada 1 identifico mal uno de los supervivientes y la unica forma de que eso
no vuelva a pasar es que la muestra este escrita:

| # | Fichero:linea | Operador | Original | Veredicto |
|---:|---|---|---|---|
| 1 | `etl_sigrid/application/steps/build_stg_step.py:732` | logico | `if self._plan and self._plan.completa:` | muerto |
| 2 | `etl_sigrid/application/steps/build_stg_step.py:771` | aritmetico | `sobrantes = sorted(pg.fetch_obras_con_filas(tabla) - vivas)` | muerto |
| 3 | `etl_sigrid/domain/ventana.py:149` | entero | `if self.meses_sin_actividad <= 0:` | muerto |
| 4 | `etl_sigrid/domain/ventana.py:350` | aritmetico | `return (hasta.year - desde.year) * 12 + (hasta.month - desd...` | muerto |
| 5 | `etl_sigrid/domain/ventana.py:706` | entero | `return 1 if (self.hay_hallazgos or self.no_ha_mirado_nada) ...` | muerto |
| 6 | `etl_sigrid/domain/ventana.py:706` | entero | `return 1 if (self.hay_hallazgos or self.no_ha_mirado_nada) ...` | muerto |
| 7 | `etl_sigrid/infrastructure/postgres/postgres_client.py:1529` | entero | `tiene_filas=bool(fila[4]) and bool(fila[5]),` | **vive** |
| 8 | `etl_sigrid/infrastructure/postgres/postgres_client.py:1529` | logico | `tiene_filas=bool(fila[4]) and bool(fila[5]),` | **vive** |
| 9 | `etl_sigrid/infrastructure/postgres/postgres_client.py:1551` | entero | `int(fila[0]): dict(zip(COLUMNAS_FIRMA_ORIGEN, fila[1:], str...` | **vive** |
| 10 | `etl_sigrid/infrastructure/postgres/postgres_client.py:1565` | logico | `return fila[0] if fila and fila[0] is not None else None` | **vive** |
| 11 | `etl_sigrid/infrastructure/postgres/postgres_client.py:1585` | entero | `return {int(fila[0]) for fila in cur.fetchall() if fila[0] ...` | **vive** |
| 12 | `etl_sigrid/infrastructure/postgres/postgres_client.py:1643` | not | `if not registros:` | **vive** |
| 13 | `etl_sigrid/infrastructure/postgres/ventana_sql.py:215` | logico | `codigo_obra=str(codigo or ""),` | **vive** |
| 14 | `main.py:543` | booleano | `is_flag=True,` | **vive** |
| 15 | `main.py:1428` | not | `if not censo:` | muerto |
| 16 | `main.py:1506` | comparacion | `if veredicto is None:` | muerto |
| 17 | `main.py:1549` | entero | `miradas = int(por_nombre["censo"][0][0]) if por_nombre["cen...` | muerto |
| 18 | `main.py:1558` | comparacion | `dias = None if ultima is None else (datetime.utcnow() - ult...` | muerto |
| 19 | `main.py:1957` | booleano | `click.secho(f"  ! {source_table}: Sigrid no contestó ({e})"...` | muerto |
| 20 | `main.py:1988` | booleano | `show_default=True,` | muerto |

**`main.py:539` --el `is_flag` de `--full`-- NO esta en la muestra.** El de
`main.py:543` es el `is_flag` de `--reconstruir-todo`, cuatro lineas mas abajo en
el mismo comando. Confundir los dos fue el error de la pasada 1; ver el
superviviente 8.

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/infrastructure/postgres/postgres_client.py:1529` [entero]

- Original: `tiene_filas=bool(fila[4]) and bool(fila[5]),`
- Mutado:   `tiene_filas=bool(fila[5]) and bool(fila[5]),`

#### Análisis

> **Por que ningun test lo caza.** La linea vive en `PostgresClient`, el
> adaptador que habla con Postgres: se ejecuta DENTRO de
> `with self.connection() as conn, conn.cursor() as cur`, sobre las tuplas que
> devuelve un cursor real. La suite no abre ni red ni BBDD --lo exige
> `docs/CONVENTIONS.md`-- y los tests que usan este metodo lo sustituyen por un
> doble en la frontera, asi que **el cuerpo del metodo no se ejecuta ni una vez
> en toda la campaña**. Un mutante ahi dentro no puede morir: no es que el test
> sea flojo, es que no hay test que pase por esa linea.
>
> **NO es equivalente**: `fila[4]` es el presupuesto y `fila[5]` el plan mensual. El docstring del propio metodo dice que `tiene_filas` **exige las DOS** tablas, porque media obra construida no se congela: se completa. El mutante ignora el presupuesto y decide solo por el plan, asi que una obra con plan y sin presupuesto se congelaria a medio construir.
>
> **Decision: hueco real, y NO se tapa en F-074.** Es codigo de F-025 que esta
> feature no toca --su unico `.py` de produccion tocado es la constante de
> `config/settings.py`--, y entra en el alcance porque el diff se calcula contra
> el `merge-base` con `dev`, que arrastra F-025, F-066 y F-068 enteras. Taparlo
> exige un test de integracion contra un Postgres de verdad, que es una decision
> de alcance del humano y no un apaño de esta feature. **Queda escrito aqui para
> que se pueda fichar**, no dado por bueno.

### 2. `etl_sigrid/infrastructure/postgres/postgres_client.py:1529` [logico]

- Original: `tiene_filas=bool(fila[4]) and bool(fila[5]),`
- Mutado:   `tiene_filas=bool(fila[4]) or bool(fila[5]),`

#### Análisis

> **Por que ningun test lo caza.** La linea vive en `PostgresClient`, el
> adaptador que habla con Postgres: se ejecuta DENTRO de
> `with self.connection() as conn, conn.cursor() as cur`, sobre las tuplas que
> devuelve un cursor real. La suite no abre ni red ni BBDD --lo exige
> `docs/CONVENTIONS.md`-- y los tests que usan este metodo lo sustituyen por un
> doble en la frontera, asi que **el cuerpo del metodo no se ejecuta ni una vez
> en toda la campaña**. Un mutante ahi dentro no puede morir: no es que el test
> sea flojo, es que no hay test que pase por esa linea.
>
> **NO es equivalente**: cambia el `and` por un `or` y convierte «las dos tablas» en «cualquiera de las dos». Es exactamente el fallo contra el que el docstring avisa, y con el mismo desenlace: obras a medias marcadas como completas.
>
> **Decision: hueco real, y NO se tapa en F-074.** Es codigo de F-025 que esta
> feature no toca --su unico `.py` de produccion tocado es la constante de
> `config/settings.py`--, y entra en el alcance porque el diff se calcula contra
> el `merge-base` con `dev`, que arrastra F-025, F-066 y F-068 enteras. Taparlo
> exige un test de integracion contra un Postgres de verdad, que es una decision
> de alcance del humano y no un apaño de esta feature. **Queda escrito aqui para
> que se pueda fichar**, no dado por bueno.

### 3. `etl_sigrid/infrastructure/postgres/postgres_client.py:1551` [entero]

- Original: `int(fila[0]): dict(zip(COLUMNAS_FIRMA_ORIGEN, fila[1:], strict=True))`
- Mutado:   `int(fila[0]): dict(zip(COLUMNAS_FIRMA_ORIGEN, fila[2:], strict=True))`

#### Análisis

> **Por que ningun test lo caza.** La linea vive en `PostgresClient`, el
> adaptador que habla con Postgres: se ejecuta DENTRO de
> `with self.connection() as conn, conn.cursor() as cur`, sobre las tuplas que
> devuelve un cursor real. La suite no abre ni red ni BBDD --lo exige
> `docs/CONVENTIONS.md`-- y los tests que usan este metodo lo sustituyen por un
> doble en la frontera, asi que **el cuerpo del metodo no se ejecuta ni una vez
> en toda la campaña**. Un mutante ahi dentro no puede morir: no es que el test
> sea flojo, es que no hay test que pase por esa linea.
>
> **NO es equivalente**: `fila[1:]` son los valores que se emparejan con `COLUMNAS_FIRMA_ORIGEN`; con `fila[2:]` el `zip(..., strict=True)` recibe una secuencia mas corta y **levanta `ValueError`**. La firma del origen no se calcularia, y como `_calcular_firma_origen` avisa y no tumba, la noche terminaria en verde sin firmar ninguna obra.
>
> **Decision: hueco real, y NO se tapa en F-074.** Es codigo de F-025 que esta
> feature no toca --su unico `.py` de produccion tocado es la constante de
> `config/settings.py`--, y entra en el alcance porque el diff se calcula contra
> el `merge-base` con `dev`, que arrastra F-025, F-066 y F-068 enteras. Taparlo
> exige un test de integracion contra un Postgres de verdad, que es una decision
> de alcance del humano y no un apaño de esta feature. **Queda escrito aqui para
> que se pueda fichar**, no dado por bueno.

### 4. `etl_sigrid/infrastructure/postgres/postgres_client.py:1565` [logico]

- Original: `return fila[0] if fila and fila[0] is not None else None`
- Mutado:   `return fila[0] if fila or fila[0] is not None else None`

#### Análisis

> **Por que ningun test lo caza.** La linea vive en `PostgresClient`, el
> adaptador que habla con Postgres: se ejecuta DENTRO de
> `with self.connection() as conn, conn.cursor() as cur`, sobre las tuplas que
> devuelve un cursor real. La suite no abre ni red ni BBDD --lo exige
> `docs/CONVENTIONS.md`-- y los tests que usan este metodo lo sustituyen por un
> doble en la frontera, asi que **el cuerpo del metodo no se ejecuta ni una vez
> en toda la campaña**. Un mutante ahi dentro no puede morir: no es que el test
> sea flojo, es que no hay test que pase por esa linea.
>
> **NO es equivalente**: con `or`, cuando `fila` es `None` --que es el caso que la guarda existe para cubrir: «nunca se ha reconstruido»-- Python evalua `fila[0]` y **revienta con `TypeError`**. La guarda no protege nada.
>
> **Decision: hueco real, y NO se tapa en F-074.** Es codigo de F-025 que esta
> feature no toca --su unico `.py` de produccion tocado es la constante de
> `config/settings.py`--, y entra en el alcance porque el diff se calcula contra
> el `merge-base` con `dev`, que arrastra F-025, F-066 y F-068 enteras. Taparlo
> exige un test de integracion contra un Postgres de verdad, que es una decision
> de alcance del humano y no un apaño de esta feature. **Queda escrito aqui para
> que se pueda fichar**, no dado por bueno.

### 5. `etl_sigrid/infrastructure/postgres/postgres_client.py:1585` [entero]

- Original: `return {int(fila[0]) for fila in cur.fetchall() if fila[0] is not None}`
- Mutado:   `return {int(fila[1]) for fila in cur.fetchall() if fila[0] is not None}`

#### Análisis

> **Por que ningun test lo caza.** La linea vive en `PostgresClient`, el
> adaptador que habla con Postgres: se ejecuta DENTRO de
> `with self.connection() as conn, conn.cursor() as cur`, sobre las tuplas que
> devuelve un cursor real. La suite no abre ni red ni BBDD --lo exige
> `docs/CONVENTIONS.md`-- y los tests que usan este metodo lo sustituyen por un
> doble en la frontera, asi que **el cuerpo del metodo no se ejecuta ni una vez
> en toda la campaña**. Un mutante ahi dentro no puede morir: no es que el test
> sea flojo, es que no hay test que pase por esa linea.
>
> **NO es equivalente**: `SQL_OBRAS_CON_FILAS` proyecta el identificador de obra en la primera columna; `fila[1]` lee otra cosa, o **`IndexError`** si la consulta devuelve una sola columna. La denuncia de obras sobrantes nombraria obras equivocadas.
>
> **Decision: hueco real, y NO se tapa en F-074.** Es codigo de F-025 que esta
> feature no toca --su unico `.py` de produccion tocado es la constante de
> `config/settings.py`--, y entra en el alcance porque el diff se calcula contra
> el `merge-base` con `dev`, que arrastra F-025, F-066 y F-068 enteras. Taparlo
> exige un test de integracion contra un Postgres de verdad, que es una decision
> de alcance del humano y no un apaño de esta feature. **Queda escrito aqui para
> que se pueda fichar**, no dado por bueno.

### 6. `etl_sigrid/infrastructure/postgres/postgres_client.py:1643` [not]

- Original: `if not registros:`
- Mutado:   `if registros:`

#### Análisis

> **Por que ningun test lo caza.** La linea vive en `PostgresClient`, el
> adaptador que habla con Postgres: se ejecuta DENTRO de
> `with self.connection() as conn, conn.cursor() as cur`, sobre las tuplas que
> devuelve un cursor real. La suite no abre ni red ni BBDD --lo exige
> `docs/CONVENTIONS.md`-- y los tests que usan este metodo lo sustituyen por un
> doble en la frontera, asi que **el cuerpo del metodo no se ejecuta ni una vez
> en toda la campaña**. Un mutante ahi dentro no puede morir: no es que el test
> sea flojo, es que no hay test que pase por esa linea.
>
> **NO es equivalente**: invierte la salida temprana: con registros que escribir se devolveria 0 **sin escribir ninguno**, y con la lista vacia se abriria una conexion para nada. Las obras quedarian construidas y sin registrar, que es justo lo que el docstring describe como el fallo a evitar.
>
> **Decision: hueco real, y NO se tapa en F-074.** Es codigo de F-025 que esta
> feature no toca --su unico `.py` de produccion tocado es la constante de
> `config/settings.py`--, y entra en el alcance porque el diff se calcula contra
> el `merge-base` con `dev`, que arrastra F-025, F-066 y F-068 enteras. Taparlo
> exige un test de integracion contra un Postgres de verdad, que es una decision
> de alcance del humano y no un apaño de esta feature. **Queda escrito aqui para
> que se pueda fichar**, no dado por bueno.

### 7. `etl_sigrid/infrastructure/postgres/ventana_sql.py:215` [logico]

- Original: `codigo_obra=str(codigo or ""),`
- Mutado:   `codigo_obra=str(codigo and ""),`

#### Análisis

> **Por que ningun test lo caza.** La linea construye el `codigo_obra` de un
> `HallazgoVentana` del tipo `TIPO_SELLO_NO_VIGENTE`. Los tests de
> `tests/test_f025_ventana.py` que recorren ese tipo lo hacen con el codigo a
> `None` o con la lista vacia, asi que la rama con codigo informado **no se
> ejecuta**: el `or` solo se distingue del `and` cuando `codigo` es verdadero.
>
> **NO es equivalente**: con `codigo and ""` el resultado es SIEMPRE la cadena
> vacia, tambien cuando la obra tiene codigo. El hallazgo se publicaria sin
> identificar la obra --«construida el ... con el sello ...», y de que obra, no
> se sabe--, que es precisamente lo que el hallazgo existe para decir.
>
> **Decision: hueco real, y NO se tapa en F-074.** Mismo motivo que los seis de
> `postgres_client.py`: es codigo de F-025 que esta feature no toca y que entra
> en el alcance por el `merge-base`. Aqui, ademas, el test que faltaria es
> barato --un caso con codigo informado-- asi que **queda anotado para ficharlo**.

### 8. `main.py:543` [booleano]

- Original: `is_flag=True,`
- Mutado:   `is_flag=False,`

#### Análisis

> **CORREGIDO TRAS EL REVIEW (pasada 1).** La primera version de este analisis
> decia que esta linea era la bandera `--full` de `run-all` y que F-074 la habia
> cerrado con un test nuevo. **Era falso, y se retira entero**: `main.py:539` es
> `@click.option("--full", ...)` y **la 543 es el `is_flag=True,` de
> `--reconstruir-todo`**, cuatro lineas mas abajo, en el mismo comando. Reproduje
> la muestra con la semilla declarada (`random.Random(20260820).sample`, 20 de
> 288) y **el mutante de la 539 NO esta en ella**; el de la 543, si. Se retiran
> «CAZADO Y CERRADO POR F-074», «el octavo si era nuestro» y «era el peor», y con
> ellas la traza pegada, que mutaba la 539. **Este superviviente sigue vivo.**
>
> **De que opcion es.** `--reconstruir-todo` de `run-all` (F-025): «ignora la
> ventana de negocio y rehace TODAS las obras». No la usa la nocturna --el `CMD`
> del `Dockerfile` es `run-all --full` a secas-- ni hace falta programarla: la
> reconstruccion completa del domingo se dispara sola por antiguedad registrada.
> Es una bandera para forzarla a mano.
>
> **Que hace el mutante, MEDIDO y no supuesto.** Con `default=False`, click
> infiere el tipo `BOOL`, asi que sin `is_flag` la opcion pasa a exigir un valor:
>
> ```
> run-all --reconstruir-todo          -> exit 2  Option '--reconstruir-todo' requires an argument.
> run-all --reconstruir-todo --full   -> exit 2  Invalid value: '--full' is not a valid boolean.
> run-all --full                      -> exit 0  full=True  recon=False   (igual que antes)
> run-all                             -> exit 0  full=False recon=False   (igual que antes)
> --help                              ->        `--reconstruir-todo BOOLEAN`
> ```
>
> **NO es equivalente**: `run-all --reconstruir-todo` deja de funcionar. Pero
> falla **ruidosamente** (exit 2, mensaje de click) y solo en la via manual: la
> nocturna y el rebuild del domingo no la tocan. Y **no es una limitacion del
> mutador**: es un cambio de comportamiento real y reproducible.
>
> **Por que ningun test lo caza.** `--reconstruir-todo` SI tiene tests, en el
> bloque «T15» de `tests/test_f025_cli.py`, y son ellos los que deberian haberlo
> visto. No lo ven porque comprueban dos cosas que el mutante no rompe: que la
> cadena `"--reconstruir-todo"` aparezca en la salida de `--help` --y sigue
> apareciendo, ahora seguida de `BOOLEAN`-- y que el callback la cablee, leyendo
> el codigo fuente con `inspect.getsource`. **Ningun test invoca
> `run-all --reconstruir-todo` por el parser de click**, que es lo unico que
> distinguiria una bandera de una opcion con valor. Es el mismo vicio que F-074
> encontro en `test_f006_r13_el_cli_declara_full_y_no_full_refresh`: comprobar
> que la opcion EXISTE, por texto, en vez de QUE ES.
>
> **Decision: superviviente ACEPTADO, y NO se tapa aqui.** Rigor `estandar` no
> exige cero supervivientes; exige que se documenten y se puedan juzgar.
>
> * Es **codigo y test de F-025**, no de F-074: esta feature no toca `main.py` ni
>   `tests/test_f025_cli.py`, y su unico `.py` de produccion tocado es la
>   constante `DEFAULT_EXCLUDED_TABLES` de `config/settings.py`. Entra en el
>   alcance por el `merge-base` con `dev`, como los otros siete.
> * **Tiene dueño y sitio natural**: el arreglo es endurecer T15 de
>   `tests/test_f025_cli.py`, no meter una asercion sobre la ventana de negocio en
>   `tests/test_f074_ingesta_censo.py`, donde no seria trazable a ningun criterio
>   `acceptance` de esta feature.
> * **Severidad baja**: fallo ruidoso, via manual, nocturna intacta.
>
> **Queda fichado, no dado por bueno**, y el arreglo esta escrito para que sea de
> aplicar. En `tests/test_f025_cli.py`, junto a T15:
>
> ```python
> def test_f025_r15_reconstruir_todo_es_una_bandera_booleana() -> None:
>     opcion = next(
>         p for p in main.cli.commands["run-all"].params
>         if "--reconstruir-todo" in getattr(p, "opts", [])
>     )
>     assert opcion.is_flag is True
>     assert CliRunner().invoke(main.cli, ["run-all", "--help"]).exit_code == 0
> ```
>
> **La frontera la decide el lider, no yo**: si prefiere que entre en F-074, es
> ese bloque y esta el hueco hecho.
>
> **El test que F-074 SI escribio se queda**, y el review lo confirma:
> `test_f074_r2_la_bandera_full_de_run_all_es_un_flag_booleano` es correcto y mata
> un mutante real, el de la **539**, que la campaña nunca llego a evaluar porque
> el muestreo no lo eligio. Lo que era falso es decir que cerraba ESTE.
