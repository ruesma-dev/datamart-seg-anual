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

> **CAZADO Y CERRADO POR F-074.** Este si estaba dentro de lo que esta feature
> defiende, y era el mas grave de los ocho: `--full` es la bandera que el `CMD`
> del `Dockerfile` pasa desnuda para que la nocturna haga `TRUNCATE` y recarga
> entera. **Toda la decision de carga de F-074 se apoya en ella.**
>
> **Por que sobrevivio.** `test_f006_r13_el_cli_declara_full_y_no_full_refresh`
> comprueba que la opcion EXISTE, leyendo `main.py` con una expresion regular
> sobre el texto. No comprueba QUE ES. Con `is_flag=False` la opcion sigue
> llamandose `--full` y el barrido por texto la sigue encontrando, asi que el
> mutante pasaba entero.
>
> **NO es equivalente**: sin `is_flag`, click espera un VALOR detras de `--full`.
> El `CMD` del contenedor la pasa sola, asi que el job nocturno fallaria al
> arrancar --o, peor, dejaria de significar «recarga completa»-- y las seis
> tablas sin `tiemod` que F-074 da de alta quedarian congeladas de verdad.
>
> **Cerrado con un test nuevo**, no quitando codigo:
> `test_f074_r2_la_bandera_full_de_run_all_es_un_flag_booleano`, que se lo
> pregunta a click y no al texto del fichero. Verificado mutando el arbol a mano
> y restaurandolo despues:
>
> ```
> - @click.option("--full", "full_refresh", is_flag=True, default=False)
> + @click.option("--full", "full_refresh", is_flag=False, default=False)
>
> $ python -m pytest tests/test_f074_ingesta_censo.py -k "bandera_full" --tb=line
> E   AssertionError: `--full` ha dejado de ser una bandera: el `CMD` del
>     Dockerfile la pasa sin valor y la nocturna dejaria de hacer recarga completa
>     assert False is True
>      +  where False = <Option full_refresh>.is_flag
> 1 failed, 118 deselected in 1.11s
> ```

