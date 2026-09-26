<!-- progress/mutacion_F-079.md -->
# F-079 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-079` el 2026-09-09 22:20.

## Alcance

Origen del diff: **rama** (`cd18e0962b63edcc0017907b8c69a29352e433c4` .. `feature/F-079-todo-lo-publicado-es-consultable`).

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
| Tiempo total | 2239.0 s |
| SHA de HEAD medido | `bc1ce726cd9f050554efd64c209d8e25dbc4c140` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-079_oijuoulo/wk_0` | 354.6 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-079_oijuoulo/wk_1` | 349.8 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-079_oijuoulo/wk_2` | 347.9 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-079_oijuoulo/wk_3` | 346.0 |
| Media por mutante evaluado (s) | 111.9 |
| Timeout efectivo por mutante (s) | 710 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 4 |
| Muestreo | sí — 20 de 288 mutantes, semilla `20260820`, nivel `estandar` |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

> **LEER ESTO ANTES QUE LOS OCHO ANÁLISIS.** El alcance que la herramienta ha
> medido **no es el cambio de F-079**, y eso **ya tiene ficha abierta: F-075**
> («las dos puertas automáticas miden código de otras features: `harness.alcance`
> diffea contra una base que se quedó vieja»). Esta campaña es un caso más de lo
> mismo. F-079 toca `config/diccionario/*.yaml`,
> `tests/` y `progress/`: **cero líneas de Python de producción**. Lo que sale
> en la tabla de arriba —3.527 líneas en 14 ficheros— es el diff de la RAMA
> contra `cd18e096`, o sea todo lo que ha entrado en esta línea de commits desde
> entonces: F-025, F-066, F-072 y F-074. Compruébese con
> `git diff --name-only cd18e096..HEAD -- '*.py'` frente a
> `git diff --name-only 880b4fe..HEAD` (los commits de F-079).
>
> **Consecuencia: los ocho supervivientes son huecos PREEXISTENTES, ninguno
> introducido por esta feature.** Se analizan igual, uno a uno, porque el arnés
> lo exige y porque el análisis vale; pero **taparlos no es trabajo de F-079**:
> son código de otras features, y meter mano ahí sería exactamente el
> «workaround improvisado» que el protocolo prohíbe. Van propuestos como ficha
> propia al final.
>
> **Los ocho tienen una sola causa raíz, y es la misma:** son adaptadores que se
> comprueban por el TEXTO de su SQL y por la EXISTENCIA de su método, nunca
> alimentando un cursor falso con filas y mirando qué entidad sale. Seis viven
> en `postgres_client.py`, uno en `ventana_sql.py` —fichero que **no aparece en
> ningún test del árbol**: `grep -rn "ventana_sql" tests/` no devuelve nada— y
> el octavo es F-077, ya con ficha abierta.

### 1. `etl_sigrid/infrastructure/postgres/postgres_client.py:1529` [entero]

- Original: `tiene_filas=bool(fila[4]) and bool(fila[5]),`
- Mutado:   `tiene_filas=bool(fila[5]) and bool(fila[5]),`

#### Análisis

**Hueco real, no equivalente.** `fila[4]` y `fila[5]` son las dos columnas de
`SQL_ESTADO_OBRAS` que dicen si la obra tiene filas en `stg.presupuesto` y en
`stg.plan_mensual`. Con la mutación, `tiene_filas` pasa a mirar dos veces la
misma columna: una obra con plan y sin presupuesto —media obra construida—
saldría como completa y **se congelaría en vez de completarse**, que es justo lo
que el docstring del método dice que no debe pasar.

**Por qué ningún test lo caza:** nadie ejecuta `fetch_censo_de_obras` contra un
cursor falso. `tests/test_f025_sql.py` comprueba el TEXTO de `SQL_ESTADO_OBRAS`
y, en `test_f025_r14_los_metodos_de_la_ventana_existen_en_el_cliente`, que el
método exista y sea llamable. La traducción fila → `ObraCensada` no la mira
nadie, así que cualquier índice de tupla de este bloque es intocable.

**Decisión: no se tapa en F-079.** Es código de F-025, fuera del diff de esta
feature. Va a la propuesta de ficha del final.

### 2. `etl_sigrid/infrastructure/postgres/postgres_client.py:1529` [logico]

- Original: `tiene_filas=bool(fila[4]) and bool(fila[5]),`
- Mutado:   `tiene_filas=bool(fila[4]) or bool(fila[5]),`

#### Análisis

**Hueco real, no equivalente**, y más grave que el anterior: `and` → `or` hace
que baste UNA de las dos tablas para dar la obra por construida. Es literalmente
la regla que el docstring del método fija —«`tiene_filas` exige las DOS tablas»—
invertida.

**Por qué ningún test lo caza:** el mismo punto ciego que el superviviente 1.
Ningún test alimenta `fetch_censo_de_obras` con filas.

**Decisión: no se tapa en F-079** (código de F-025). Ficha propuesta al final.

### 3. `etl_sigrid/infrastructure/postgres/postgres_client.py:1551` [entero]

- Original: `int(fila[0]): dict(zip(COLUMNAS_FIRMA_ORIGEN, fila[1:], strict=True))`
- Mutado:   `int(fila[0]): dict(zip(COLUMNAS_FIRMA_ORIGEN, fila[2:], strict=True))`

#### Análisis

**Hueco real.** `fila[1:]` se empareja con `COLUMNAS_FIRMA_ORIGEN` mediante
`zip(..., strict=True)`. Con `fila[2:]` el emparejamiento se desplaza una
posición: **cada columna recibiría el valor de la siguiente**, y como la firma se
calcula sobre ese diccionario, la firma de todas las obras cambiaría a la vez.

En producción esto no pasaría inadvertido: con `strict=True`, `fila[2:]` tiene
una posición menos de las que espera `COLUMNAS_FIRMA_ORIGEN` y `zip` levantaría
`ValueError` en la primera fila. O sea, el mutante no falsea la firma: **rompe el
paso**. Que sobreviva no dice nada de `strict=True`; dice que la línea no se
ejecuta nunca en la suite.

**Por qué ningún test lo caza:** `tests/test_f025_firma_paso.py` y
`test_f025_sql.py` trabajan con la firma ya montada o con el texto del SQL;
`fetch_firma_origen` no se ejecuta nunca contra filas de prueba.

**Decisión: no se tapa en F-079** (código de F-025). Ficha propuesta al final.

### 4. `etl_sigrid/infrastructure/postgres/postgres_client.py:1565` [logico]

- Original: `return fila[0] if fila and fila[0] is not None else None`
- Mutado:   `return fila[0] if fila or fila[0] is not None else None`

#### Análisis

**Equivalente en la práctica, pero por accidente, no por diseño.**
`fila and fila[0] is not None` → `fila or fila[0] is not None`. `cur.fetchone()`
devuelve `None` cuando no hay filas, y `None or (...)` evaluaría `fila[0]` sobre
`None` y **reventaría con `TypeError`**; devuelve una tupla cuando sí hay, y
entonces la rama `or` da lo mismo que la `and`. O sea: la mutación solo se
distingue del original **en el caso de tabla vacía**, y ese caso es el que
significa «nunca se ha hecho una reconstrucción completa» —la línea base de R25—.

**Por qué ningún test lo caza:** no hay ninguno que llame a
`fetch_ultima_reconstruccion_completa` con un cursor que devuelva `None`. El
único test de esa consulta,
`test_f025_r25_la_ultima_completa_solo_cuenta_las_que_TERMINARON_bien`, lee el
texto del SQL.

**No se declara equivalente**: mata el proceso con `TypeError` justo en el caso
que la guarda existe para cubrir. Es un hueco real, del tamaño de un test.

**Decisión: no se tapa en F-079** (código de F-025). Ficha propuesta al final.

### 5. `etl_sigrid/infrastructure/postgres/postgres_client.py:1585` [entero]

- Original: `return {int(fila[0]) for fila in cur.fetchall() if fila[0] is not None}`
- Mutado:   `return {int(fila[1]) for fila in cur.fetchall() if fila[0] is not None}`

#### Análisis

**Hueco real.** `SQL_OBRAS_CON_FILAS` proyecta una sola columna, así que
`fila[1]` levantaría `IndexError` en cuanto la consulta devolviera una fila. La
mutación sobrevive porque **esa consulta no se ejecuta en ningún test**: los dos
que la nombran comprueban que el nombre de tabla se valida contra
`TABLAS_ACOTADAS` (y para eso construyen el cliente con
`PostgresClient.__new__`, que **no conecta**) y que el `{tabla}` está en el
texto.

Efecto en producción: la denuncia de obras sobrantes de
`build_stg_step._denunciar_obras_sobrantes` moriría con `IndexError` en cuanto
hubiera una obra sobrante — es decir, exactamente cuando hace falta.

**Decisión: no se tapa en F-079** (código de F-025). Ficha propuesta al final.

### 6. `etl_sigrid/infrastructure/postgres/postgres_client.py:1643` [not]

- Original: `if not registros:`
- Mutado:   `if registros:`

#### Análisis

**Hueco real, y del más caro.** `if not registros: return 0` → `if registros:
return 0` invierte la guarda: con registros que escribir, el método **devuelve 0
sin escribir ninguno**, y con la lista vacía cae al `with self.connection()` y
abre una conexión para nada.

La consecuencia es la que el propio docstring describe como el lado malo: las
obras quedarían construidas y **sin registrar** en `_meta.obra_build`, así que la
noche siguiente entrarían todas por R18. No se pierde dato; se pierde la noche.

**Por qué ningún test lo caza:** `registrar_obras_construidas` aparece en seis
ficheros de test, pero siempre a través de dobles del cliente o comprobando el
texto de `SQL_REGISTRAR_OBRA`. El método real no se ejecuta.

**Decisión: no se tapa en F-079** (código de F-025). Ficha propuesta al final.

### 7. `etl_sigrid/infrastructure/postgres/ventana_sql.py:215` [logico]

- Original: `codigo_obra=str(codigo or ""),`
- Mutado:   `codigo_obra=str(codigo and ""),`

#### Análisis

**Hueco real, y el que peor pinta tiene de los ocho.** `str(codigo or "")` →
`str(codigo and "")` deja `codigo_obra` **vacío siempre que el código exista**:
la denuncia de «obra construida con un sello que ya no es el vigente» saldría sin
decir de qué obra habla.

**Por qué ningún test lo caza: `etl_sigrid/infrastructure/postgres/ventana_sql.py`
no aparece en ningún test del árbol.** Comprobado:
`grep -rn "ventana_sql\|hallazgos_de" tests/` no devuelve una sola línea. Son
246 líneas en alcance sin una prueba, y las cuatro consultas de la ventana y su
traducción a `HallazgoVentana` salen de ahí.

Eso es más grande que un mutante: es un fichero entero sin red. Se destaca en la
propuesta de ficha del final.

**Decisión: no se tapa en F-079** (código de F-025/F-074).

### 8. `main.py:543` [booleano]

- Original: `is_flag=True,`
- Mutado:   `is_flag=False,`

#### Análisis

**Hueco real, YA DIAGNOSTICADO: es F-077**, ficha abierta en el backlog (commit
`7d2d8b9`), hallada por la campaña de F-074 y descrita en
`progress/mutacion_F-074.md` §8 y en `progress/current.md`.

Bajar `is_flag` a `False` hace que click infiera que `--reconstruir-todo` toma
valor, y la opción deja de funcionar como bandera.

**Por qué ningún test lo caza:** T15 de `tests/test_f025_cli.py` comprueba que la
cadena `--reconstruir-todo` sale en `--help` (líneas 139 y 426) y que el callback
la cablea, leyendo el **texto fuente** con `inspect.getsource` (líneas 434 y
440). **Ninguno invoca la opción a través del parser de click**, que es lo único
que distingue una bandera de una opción con valor.

**Decisión: no se tapa en F-079.** Tiene ficha propia y no es código de esta
feature. Que la campaña de F-079 lo reencuentre por su cuenta, con otra semilla y
otro muestreo, **confirma el diagnóstico de F-074**.


## Conclusión y propuesta al líder

**F-079 no introduce ningún superviviente**: su diff no toca una sola línea de
Python de producción. Los ocho salen del alcance heredado de la rama (3.527
líneas de F-025, F-066, F-072 y F-074) y **ninguno se tapa aquí**, por la regla
del protocolo: no se improvisa sobre código de otra feature.

Que el alcance venga inflado **ya tiene ficha: F-075**. Lo que esta campaña
añade es un diagnóstico distinto, sobre el código medido, y ese sí merece **ficha
propia**:

> **La capa de adaptadores de la ventana de negocio se comprueba por el texto de
> su SQL, no por lo que devuelve.** Siete de los ocho supervivientes son
> traducciones fila → entidad en `postgres_client.py` y en `ventana_sql.py` que
> **ningún test ejecuta**. Los tests que las nombran comprueban tres cosas: que
> la constante SQL contiene ciertas cadenas, que el método existe y es llamable,
> y que el nombre de tabla se valida (con un cliente creado por `__new__`, que no
> conecta). Ninguna alimenta un cursor falso.
>
> El caso más claro es
> `etl_sigrid/infrastructure/postgres/ventana_sql.py`: **246 líneas en alcance y
> cero apariciones en `tests/`** (`grep -rn "ventana_sql\|hallazgos_de" tests/`
> no devuelve nada). Ahí viven las cuatro consultas de la ventana y la
> traducción a `HallazgoVentana`.
>
> El arreglo es barato y de una sola clase: un cursor falso que devuelva filas
> conocidas y aserciones sobre la entidad resultante. Cazaría los siete de golpe.

El octavo, `main.py:543`, **ya tiene ficha: F-077**. Que esta campaña lo
reencuentre por su cuenta, con otro muestreo, confirma aquel diagnóstico.
