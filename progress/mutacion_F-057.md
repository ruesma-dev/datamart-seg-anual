<!-- progress/mutacion_F-057.md -->
# F-057 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-057` el 2026-09-18 18:10.

## Alcance

Origen del diff: **rama** (`cd18e0962b63edcc0017907b8c69a29352e433c4` .. `feature/F-057-recursos-empleados-partes`).

| Fichero | Líneas en alcance |
|---|---|
| `config/settings.py` | 117 |
| `etl_sigrid/application/steps/apply_grants_step.py` | 18 |
| `etl_sigrid/application/steps/build_compras_step.py` | 42 |
| `etl_sigrid/application/steps/build_maestros_step.py` | 76 |
| `etl_sigrid/application/steps/build_mart_step.py` | 57 |
| `etl_sigrid/application/steps/build_personal_step.py` | 145 |
| `etl_sigrid/application/steps/build_stg_step.py` | 613 |
| `etl_sigrid/application/steps/ingest_raw_step.py` | 70 |
| `etl_sigrid/domain/cobertura.py` | 35 |
| `etl_sigrid/domain/diccionario.py` | 15 |
| `etl_sigrid/domain/huella_ampliada.py` | 20 |
| `etl_sigrid/domain/recuentos.py` | 286 |
| `etl_sigrid/domain/texto_comentarios.py` | 141 |
| `etl_sigrid/domain/tramos.py` | 4 |
| `etl_sigrid/domain/ventana.py` | 784 |
| `etl_sigrid/infrastructure/postgres/cp_tipologia_sql.py` | 391 |
| `etl_sigrid/infrastructure/postgres/grants.py` | 101 |
| `etl_sigrid/infrastructure/postgres/huella_ampliada.py` | 33 |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | 723 |
| `etl_sigrid/infrastructure/postgres/ventana_sql.py` | 246 |
| `main.py` | 652 |
| **Total** | **4569** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 349 |
| Mutantes evaluados | 20 |
| Muertos | 13 |
| Supervivientes | 7 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 4084.7 s |
| SHA de HEAD medido | `f6547dd411afaddb333b95a08625fe806c3f70c7` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-057_82lmyypb/wk_0` | 743.3 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-057_82lmyypb/wk_1` | 732.9 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-057_82lmyypb/wk_2` | 752.9 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-057_82lmyypb/wk_3` | 737.7 |
| Media por mutante evaluado (s) | 204.2 |
| Timeout efectivo por mutante (s) | 2400 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 2400 |
| Workers | 4 |
| Muestreo | sí — 20 de 349 mutantes, semilla `20260820`, nivel `estandar` |

## LA LECTURA QUE HAY QUE HACER ANTES DE MIRAR LOS SUPERVIVIENTES

**Ninguno de los 20 mutantes de esta campaña cayo en codigo de F-057**, y los
siete supervivientes son de F-024 y F-025. No es casualidad: el alcance se
calcula contra el `merge-base` con `dev` (`cd18e09`), que en esta rama arrastra
**4.569 lineas de produccion de 21 ficheros** --F-025, F-066, F-068, F-074,
F-078 enteras-- mientras que lo que F-057 escribe de Python son **145 lineas**,
las de `build_personal_step.py`, mas un puñado en `main.py`, `settings.py` y
`diccionario.py`. Muestrear 20 de 349 sobre ese universo deja la feature sin
tocar con probabilidad alta, y eso es justo lo que paso.

Una campaña cuyos 20 mutantes caen todos fuera de la feature **no dice nada de
la feature**. Por eso se lanzo una SEGUNDA campaña, dirigida con `--ficheros` al
unico fichero de produccion que F-057 escribe entero, y **esa es la que juzga
esta feature**: sus cifras y sus supervivientes van al final de este documento.

Los siete de abajo se analizan igual, uno a uno, porque el nivel `estandar` lo
exige y porque varios siguen abiertos desde campañas anteriores.

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/infrastructure/postgres/postgres_client.py:1529` [logico]

- Original: `tiene_filas=bool(fila[4]) and bool(fila[5]),`
- Mutado:   `tiene_filas=bool(fila[4]) or bool(fila[5]),`

#### Análisis

> **Por que ningun test lo caza.** La linea vive en el cuerpo de un metodo de
> `PostgresClient`, dentro de `with self.connection() as conn, conn.cursor()`:
> se ejecuta sobre las tuplas de un cursor REAL. La suite no abre ni red ni
> BBDD --lo exige `docs/CONVENTIONS.md`-- y los tests que usan este metodo lo
> sustituyen por un doble en la frontera, asi que **el cuerpo no se ejecuta ni
> una vez en toda la campaña**. Un mutante ahi dentro no puede morir.
>
> **NO es equivalente**: `fila[4]` es el presupuesto y `fila[5]` el plan
> mensual, y el metodo exige las DOS para dar la obra por construida. Con `or`,
> una obra con plan y sin presupuesto se congelaria a medio construir.
>
> **Hueco real, y NO se tapa en F-057.** Es codigo de F-025; entra en el
> alcance porque el diff se calcula contra el `merge-base` con `dev`, que
> arrastra F-025, F-066, F-074 y F-078 enteras. Taparlo exige un test de
> integracion contra un Postgres de verdad: decision de alcance del humano, no
> apaño de esta feature. Es **el mismo superviviente que ya documento
> `progress/mutacion_F-074.md`**, asi que no es un hallazgo nuevo sino uno que
> sigue abierto.

### 2. `etl_sigrid/infrastructure/postgres/postgres_client.py:1565` [logico]

- Original: `return fila[0] if fila and fila[0] is not None else None`
- Mutado:   `return fila[0] if fila or fila[0] is not None else None`

#### Análisis

> **Por que ningun test lo caza.** Mismo motivo que el superviviente 1: cuerpo
> de `PostgresClient` dentro de `with self.connection()`, que la suite nunca
> ejecuta porque no toca BBDD.
>
> **NO es equivalente, y ademas revienta**: con `fila or fila[0] is not None`,
> cuando `fila` es `None` --que es justo el caso que el `and` protege-- Python
> evalua `fila[0]` y lanza `TypeError`. El original devuelve `None` y el
> llamante lo interpreta como «no hay ninguna completa registrada».
>
> **Hueco real, codigo de F-025, no se tapa aqui.** Misma razon que el 1.

### 3. `etl_sigrid/infrastructure/postgres/postgres_client.py:1670` [not]

- Original: `if not firmas:`
- Mutado:   `if firmas:`

#### Análisis

> **Por que ningun test lo caza.** Tercer caso identico: cuerpo de
> `PostgresClient`, no ejecutado por la suite offline.
>
> **NO es equivalente**: es la guarda de entrada de la escritura de firmas. Con
> `if firmas: return 0`, un diccionario CON firmas sale por la puerta y no
> escribe ninguna, y uno vacio cae al bucle --que no itera-- y devuelve 0 igual.
> O sea: la mutacion **desactiva la escritura entera** devolviendo 0, que es
> exactamente lo que el llamante interpreta como «no habia nada que escribir».
> Es el peor modo de fallo posible: silencioso y con aspecto de exito.
>
> **Hueco real, codigo de F-025, no se tapa aqui.** Misma razon que el 1.

### 4. `main.py:558` [booleano]

- Original: `is_flag=True,`
- Mutado:   `is_flag=False,`

#### Análisis

> **Por que ningun test lo caza.** `is_flag=False` convierte `--reconstruir-todo`
> en una opcion que ESPERA VALOR. Los tests de `run-all` la invocan **sin la
> bandera**, y ahi las dos versiones se comportan igual; solo una invocacion
> `run-all --reconstruir-todo` por el parser de click distinguiria.
>
> **NO es equivalente**: con el mutante, `python main.py run-all
> --reconstruir-todo` falla en el parseo y la reconstruccion completa de F-025
> deja de poder forzarse a mano.
>
> **Hueco real, ya fichado y NO nuevo.** Es el mismo defecto que
> `progress/mutacion_F-074.md` §8 dejo escrito, con el arreglo de tres lineas
> incluido, y que su reviewer acepto no tapar por estar fuera de alcance. Sigue
> fuera del de F-057: no es codigo de esta feature ni de sus tests.

### 5. `main.py:1498` [booleano]

- Original: `completa = True`
- Mutado:   `completa = False`

#### Análisis

> **Por que ningun test lo caza.** La linea esta dentro de
> `if not settings.postgres.ventana_activa:`, la rama de escape que fuerza la
> reconstruccion completa cuando `PG_VENTANA_ACTIVA=false`. Los tests del
> comando no construyen esa configuracion, asi que la rama **no se recorre**.
>
> **NO es equivalente**: con `completa = False`, desactivar la ventana dejaria
> de forzar la reconstruccion completa y haria lo contrario de lo que promete
> la variable --y el `motivo_completa` que se imprime justo debajo seguiria
> diciendo que la ventana esta desactivada, o sea mintiendo.
>
> **Hueco real, codigo de F-025, no se tapa aqui**: un test de esa rama es
> trabajo de la feature dueña del comando.

### 6. `main.py:1610` [entero]

- Original: `click.echo(f"  sello vigente     = {sello[:16]}...")`
- Mutado:   `click.echo(f"  sello vigente     = {sello[:17]}...")`

#### Análisis

> **Por que ningun test lo caza.** Es un `click.echo` de la cabecera informativa
> del comando: recorta el sello a 16 caracteres para que la linea quepa. Ningun
> test afirma cuantos caracteres se imprimen, y con razon.
>
> **Es equivalente EN LA PRACTICA**: el sello es un hash hexadecimal largo, asi
> que `[:16]` y `[:17]` producen los dos un prefijo truncado seguido de `...`;
> no cambia ninguna decision, ningun valor calculado ni ningun codigo de salida.
> Lo unico que cambia es un caracter en una linea que lee una persona.
>
> **Decision: se documenta y NO se escribe test.** Fijar por test la longitud de
> un truncado de presentacion seria testear decoracion, y dejaria el comando sin
> poder reformatear su salida sin romper la suite. Es el caso que el nivel
> `estandar` contempla al no exigir cero supervivientes.

### 7. `main.py:1677` [comparacion]

- Original: `if dias is None or dias >= DIAS_MAXIMOS_SIN_COMPLETA:`
- Mutado:   `if dias is None or dias > DIAS_MAXIMOS_SIN_COMPLETA:`

#### Análisis

> **Por que ningun test lo caza.** Es un mutante de FRONTERA: `>=` contra `>`
> solo se distinguen cuando `dias` vale EXACTAMENTE
> `DIAS_MAXIMOS_SIN_COMPLETA`. Los tests de la ventana construyen casos
> claramente dentro o claramente fuera del limite, no el valor justo.
>
> **NO es equivalente**: en el dia exacto del limite, el original avisa de
> «completa vencida» y el mutante se calla. Dicho eso, `dias` se calcula como
> `(ahora - ultima).total_seconds() / 86400.0`, un flotante: acertar el entero
> exacto en una ejecucion real es practicamente imposible, asi que el efecto
> sobre la conducta de produccion es nulo y el efecto sobre la SUITE es que
> falta un caso de frontera.
>
> **Hueco real de cobertura de frontera, en codigo de F-025, y no se tapa
> aqui**: el test que lo cierra pertenece a la feature dueña de la ventana.


---

## SEGUNDA CAMPAÑA — la que juzga F-057: `build_personal_step.py` entero

Lanzada por la sesion anterior desde un worktree limpio en HEAD, con
`--ficheros etl_sigrid/application/steps/build_personal_step.py`, `--timeout 2400`
y 4 workers (lo que registra el propio informe de la herramienta; la orden
literal no quedo anotada).

Generada el 2026-09-18 19:04 sobre el mismo HEAD `f6547dd`. Informe crudo de la
herramienta fuera del repositorio (scratchpad de la sesion); sus cifras, aqui:

| Métrica | Valor |
|---|---|
| Alcance | `build_personal_step.py`, 145 lineas (declarado con `--ficheros`) |
| Mutantes generados / evaluados | **12 / 12** (sin muestreo: campaña completa) |
| Muertos | **8** |
| Supervivientes | **4** → **3** tras el test nuevo (ver S3) |
| Timeouts / sin veredicto | 0 / 0 |
| Tiempo total | 2906,6 s (4 workers; linea base 618-627 s por worker) |

### S1. `build_personal_step.py:125` [booleano] — `exc_info=True` → `False`

> **Por que ningun test lo caza.** Es un argumento del `logger.error` de la rama
> de fallo: decide si la traza de la excepcion acompaña al log. Los tests de esa
> rama (`_PgQueRevienta`) afirman `status`, `error_message` y que se para en el
> sub-paso correcto, no el contenido del log.
>
> **Equivalente en la conducta del step**: el `StepResult` es identico —mismo
> estado, mismo mensaje con el nombre del sub-paso—. Solo cambia cuanto detalle
> recibe quien lea el log. **Decision: se documenta, sin test**: fijar por test
> los argumentos de un `logger` es testear la instrumentacion, no el paso.

### S2. `build_personal_step.py:132` [entero] — `rows = 0` → `rows = 1`

> **Por que ningun test lo caza.** Ese `rows = 0` es el valor por defecto de los
> sub-pasos SIN destino (`setup`, `views`). En ellos `rows` **solo se usa en el
> `logger.info`**: `total_rows` se acumula dentro del `if`, y en los que tienen
> destino `rows` se sobrescribe con `count_rows`.
>
> **Equivalente para el resultado**: `rows_processed` no cambia —el test
> `r24_el_step_encadena_sus_cuatro_sql` afirma 14 y sigue en 14—. Lo unico que
> cambia es un `rows=1` en la linea de log de `setup`. **Decision: equivalente
> justificado, sin test.**

### S3. `build_personal_step.py:133` [logico] — `and` → `or` — **MATADO**

> **Por que ningun test lo cazaba.** Los cuatro sub-pasos reales declaran o las
> dos mitades del destino o ninguna, asi que con ellos `and` y `or` dan lo mismo.
> **NO es equivalente**: un `_SubStep` a medio configurar llamaria a
> `count_rows(esquema, None)` y reventaria contra la base de noche, no en la
> suite. **Hueco real.**
>
> **Tapado** con `test_f057_r24_un_sub_paso_a_medio_configurar_no_cuenta_filas`,
> que sustituye `SUB_PASOS` por dos sub-pasos con solo esquema y solo tabla.
> Verificado a mano el 2026-09-22: con el mutante aplicado el test **falla**
>
> ```
> $ python -m pytest tests/test_f057_personal.py -k medio_configurar -q --tb=line -p no:warnings
> E   AssertionError: un sub-paso con solo la mitad de su destino NO puede contar filas: ...
>     assert [('personal',..., 'recursos')] == []
> 1 failed, 72 deselected in 0.64s
> ```
>
> y con el original restaurado **pasa** (`1 passed, 72 deselected in 0.55s`).

### S4. `build_personal_step.py:139` [entero] — `round(..., 2)` → `round(..., 3)`

> **Por que ningun test lo caza.** Es la precision de `duration_s` en el
> `logger.info` de cada sub-paso: presentacion de un log.
>
> **Equivalente en la practica**: no interviene en ninguna decision, valor
> devuelto ni codigo de salida. **Decision: se documenta, sin test**, por el
> mismo motivo que el superviviente 6 de la primera campaña.

**Saldo de F-057**: de 12 mutantes sobre su codigo, **9 muertos y 3
supervivientes, los tres equivalentes** en la conducta del step (instrumentacion
de log). Ningun hueco real abierto en codigo de esta feature.
