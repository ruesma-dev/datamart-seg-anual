<!-- progress/mutacion_F-073.md -->
# F-073 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-073` el 2026-09-10 15:21.

## Alcance

Origen del diff: **rama** (`cd18e0962b63edcc0017907b8c69a29352e433c4` .. `feature/F-073-tablas-nuevas-y-enriquecimiento`).

| Fichero | Líneas en alcance |
|---|---|
| `config/settings.py` | 108 |
| `etl_sigrid/application/steps/apply_grants_step.py` | 18 |
| `etl_sigrid/application/steps/build_compras_step.py` | 11 |
| `etl_sigrid/application/steps/build_maestros_step.py` | 76 |
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
| `main.py` | 489 |
| **Total** | **3617** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 288 |
| Mutantes evaluados | 20 |
| Muertos | 11 |
| Supervivientes | 9 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 5470.2 s |
| SHA de HEAD medido | `b6eda794eda72465eed63b040a36f47eb4c90916` |
| Línea base (s) — `.` | 412.8 |
| Media por mutante evaluado (s) | 273.5 |
| Timeout efectivo por mutante (s) | 826 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 1 |
| Muestreo | sí — 20 de 288 mutantes, semilla `20260820`, nivel `estandar` |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/application/steps/build_stg_step.py:732` [logico]

- Original: `if self._plan and self._plan.completa:`
- Mutado:   `if self._plan or self._plan.completa:`

#### Análisis

> **Por qué ningún test lo caza**: la guarda decide si, al construir el
> presupuesto ACOTADO, se denuncian las obras sobrantes. Los dos operadores
> solo difieren cuando `self._plan` es un plan de verdad **y**
> `plan.completa` es False; con `_plan` a None la mutación reventaría con
> `AttributeError` y el mutante habría muerto. Que sobreviva significa que
> ningún test recorre el camino acotado con un plan PARCIAL.
> **Decisión**: hueco real, y **NO es de F-073**. La línea es de F-025 (la
> ventana de reconstrucción) y entra en el alcance solo porque el diff se
> calcula contra `dev`. F-073 no toca `build_stg_step.py` -es el SELLO, R25-
> y taparlo aquí sería meterse en otra feature. Queda anotado para quien
> vuelva a F-025.

### 2. `etl_sigrid/infrastructure/postgres/postgres_client.py:1529` [entero]

- Original: `tiene_filas=bool(fila[4]) and bool(fila[5]),`
- Mutado:   `tiene_filas=bool(fila[5]) and bool(fila[5]),`

#### Análisis

> **Por qué ningún test lo caza**: está dentro de `fetch_censo_de_obras`, que
> ejecuta `SQL_ESTADO_OBRAS` contra el Postgres real y construye
> `ObraCensada` con la fila que devuelve el cursor. La convención del
> proyecto (`docs/CONVENTIONS.md`) es que los unit tests **no tocan BBDD**,
> así que no hay ninguno que pueda fabricar esa fila: los tests de F-025
> construyen `ObraCensada` a mano y prueban la lógica de la ventana, no la
> lectura.
> **Decisión**: hueco real pero **inalcanzable desde la suite offline**, y de
> F-025, no de F-073. Lo que sí lo cubre es la verificación contra la base
> (`python main.py huella-obras`), que es MANUAL. No se tapa aquí.

### 3. `etl_sigrid/infrastructure/postgres/postgres_client.py:1529` [logico]

- Original: `tiene_filas=bool(fila[4]) and bool(fila[5]),`
- Mutado:   `tiene_filas=bool(fila[4]) or bool(fila[5]),`

#### Análisis

> **Por qué ningún test lo caza**: mismo caso que el superviviente 2 -misma
> línea, otro operador-. `and` frente a `or` cambia `tiene_filas` para las
> obras con filas en una sola de las dos tablas, que es justo el reparto que
> decide la ventana; pero la línea solo se ejecuta con un cursor real.
> **Decisión**: hueco real, inalcanzable offline, de F-025. No se tapa aquí.

### 4. `etl_sigrid/infrastructure/postgres/postgres_client.py:1551` [entero]

- Original: `int(fila[0]): dict(zip(COLUMNAS_FIRMA_ORIGEN, fila[1:], strict=True))`
- Mutado:   `int(fila[0]): dict(zip(COLUMNAS_FIRMA_ORIGEN, fila[2:], strict=True))`

#### Análisis

> **Por qué ningún test lo caza**: `fetch_firma_origen` lee `SQL_FIRMA_ORIGEN`
> del cursor. Con datos reales el mutante moriría **de inmediato**, porque el
> `zip(..., strict=True)` lanzaría `ValueError` al quedarse una columna corto.
> Sobrevive solo porque ningún test llega a ejecutar el método.
> **Decisión**: hueco real, inalcanzable offline, de F-025. El `strict=True`
> ya es la red que lo caza en cuanto haya una fila de verdad.

### 5. `etl_sigrid/infrastructure/postgres/postgres_client.py:1565` [logico]

- Original: `return fila[0] if fila and fila[0] is not None else None`
- Mutado:   `return fila[0] if fila or fila[0] is not None else None`

#### Análisis

> **Por qué ningún test lo caza**: `fetch_ultima_reconstruccion_completa`
> también lee de cursor. Con `fila = None` el mutante reventaría
> (`None[0]`), así que moriría; sobrevive porque el método no se ejecuta en
> la suite.
> **Decisión**: hueco real, inalcanzable offline, de F-025. No se tapa aquí.

### 6. `etl_sigrid/infrastructure/postgres/postgres_client.py:1585` [entero]

- Original: `return {int(fila[0]) for fila in cur.fetchall() if fila[0] is not None}`
- Mutado:   `return {int(fila[1]) for fila in cur.fetchall() if fila[0] is not None}`

#### Análisis

> **Por qué ningún test lo caza**: `fetch_obras_con_filas` lee de cursor.
> `fila[1]` ni siquiera existe -el SQL proyecta una sola columna-, así que
> con datos reales saldría `IndexError`. Sobrevive por no ejecutarse.
> **Decisión**: hueco real, inalcanzable offline, de F-025. No se tapa aquí.

### 7. `etl_sigrid/infrastructure/postgres/postgres_client.py:1643` [not]

- Original: `if not registros:`
- Mutado:   `if registros:`

#### Análisis

> **Por qué ningún test lo caza**: `registrar_obras_construidas` abre conexión.
> Invertir la guarda hace que una lista NO vacía salga con 0 sin registrar
> nada -y una vacía intente conectarse-, que es un defecto serio; pero el
> método no se ejecuta en la suite offline.
> **Decisión**: hueco real, inalcanzable offline, de F-025. No se tapa aquí.

### 8. `etl_sigrid/infrastructure/postgres/ventana_sql.py:215` [logico]

- Original: `codigo_obra=str(codigo or ""),`
- Mutado:   `codigo_obra=str(codigo and ""),`

#### Análisis

> **Por qué ningún test lo caza**: `codigo and ""` devuelve cadena vacía para
> cualquier código informado, así que el hallazgo de sello no vigente saldría
> **sin código de obra**. Sobrevive porque los tests de `ventana_sql`
> comprueban el TIPO y el recuento de hallazgos, y ninguno afirma el
> `codigo_obra` de un `TIPO_SELLO_NO_VIGENTE`.
> **Decisión**: hueco real y **barato de tapar con un assert más**, pero es
> código de F-025 y no de F-073. Queda anotado, no se toca aquí.

### 9. `main.py:544` [booleano]

- Original: `is_flag=True,`
- Mutado:   `is_flag=False,`

#### Análisis

> **Por qué ningún test lo caza**: es el `is_flag` de `--reconstruir-todo` en
> `run-all`. Sin él, click infiere `BOOL` y `run-all --reconstruir-todo` sale
> con **exit 2**. Los tests que lo rodean (T15 de `tests/test_f025_cli.py`)
> comprueban que la cadena aparezca en `--help` y que el callback la cablee,
> pero **no invocan la opción por el parser de click**.
> **Decisión**: superviviente **YA CONOCIDO, ACEPTADO Y FICHADO**: es
> **F-077** (prioridad 12, commit `7d2d8b9`), lo destapó F-074 y su arreglo
> -tres líneas- está escrito en `progress/mutacion_F-074.md` §8. No es código
> de F-073 ni de su fichero de tests, y por eso salio a ficha propia.


## Lectura de esta campaña (implementer, 2026-09-10)

**NINGUNO DE LOS NUEVE SUPERVIVIENTES ESTÁ EN CÓDIGO QUE ESCRIBA F-073**, y
conviene entender por qué antes de leerlos: el alcance se calcula contra el
punto de fork con `dev`, que es `cd18e096` -de la época de F-052-, así que
arrastra **3.617 líneas** de seis features que nunca llegaron a `dev` (F-025,
F-066, F-068, F-074, F-079 y esta). De esas 3.617, las que toca F-073 son
**87** (76 de `build_maestros_step.py` y 11 de `build_compras_step.py`), un
**2,4 %**. Con un muestreo de 20 mutantes sobre 288, lo esperable de F-073 es
**medio mutante**, y salieron cero.

Los nueve se analizan igualmente y ninguno queda en PENDIENTE, pero el
veredicto honesto es que **esta campaña no dice casi nada sobre F-073**: dice
que el `PostgresClient` tiene siete líneas que la suite offline no puede
alcanzar por diseño (la convención prohibe que los unit tests toquen BBDD),
que a `ventana_sql` le falta un assert y que `main.py:544` sigue siendo F-077.

**Para juzgar el código de F-073 en concreto** hay que acotar la campaña a sus
dos ficheros. Está medido que generan **24 mutantes**:

    python -m harness.mutacion --feature F-073 --max-mutantes 0 --workers 1 \
      --ficheros etl_sigrid/application/steps/build_maestros_step.py,etl_sigrid/application/steps/build_compras_step.py

Con la línea base medida hoy (412,8 s) y en serie eso son **~1 h 50 min**, y
**no se lanzó**: la campaña que exige `CHECKPOINTS.md` C4 bis es la de
`--feature`, que es la que está arriba y la que el reviewer recalcula igual.

**POR QUÉ EN SERIE (`--workers 1`) Y NO EN PARALELO**, que es lo normal: la
campaña paralela crea sus worktrees desde `HEAD` y se niega a arrancar con el
árbol sucio. Hay **otra sesión de Claude trabajando en este repositorio**
(F-080) con cambios sin commitear que no son míos y que no puedo commitear ni
guardar. De ahí el factor de workers **1** al calcular el coste por mutante:
5.470,2 s x 1 / 20 = **273,5 s**, muy por encima del segundo que C4 bis marca
como sospechoso, y coherente con una línea base de 412,8 s con `-x`.
