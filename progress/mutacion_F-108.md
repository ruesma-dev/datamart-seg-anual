<!-- progress/mutacion_F-108.md -->
# F-108 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-108` el 2026-09-25 18:23.

## Alcance

Origen del diff: **rama** (`323910fd84c43a11244e5e8cd1325a3397fe8599` .. `feature/F-108-claves-alternativas`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/domain/diccionario.py` | 84 |
| `etl_sigrid/infrastructure/diccionario/cargador_yaml.py` | 41 |
| `etl_sigrid/infrastructure/postgres/diccionario_sql.py` | 12 |
| `etl_sigrid/infrastructure/postgres/unicidad_sql.py` | 80 |
| `main.py` | 21 |
| **Total** | **238** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 37 |
| Mutantes evaluados | 20 |
| Muertos | 15 |
| Supervivientes | 5 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 8205.7 s |
| SHA de HEAD medido | `2158cc87570bb524a61a1a5cfc13e2f89cdf78e3` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-108_dpwixqei/wk_0` | 1082.9 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-108_dpwixqei/wk_1` | 1063.1 |
| Media por mutante evaluado (s) | 410.3 |
| Timeout efectivo por mutante (s) | 1800 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 1800 |
| Workers | 2 |
| Muestreo | sí — 20 de 37 mutantes, semilla `20260820`, nivel `estandar` |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/infrastructure/postgres/diccionario_sql.py:146` [booleano]

- Original: `return json.dumps(cuerpo_ficha, sort_keys=True, ensure_ascii=False)`
- Mutado:   `return json.dumps(cuerpo_ficha, sort_keys=True, ensure_ascii=True)`

#### Análisis (implementer)

> Por qué ningún test lo caza: la línea es la de F-006 (`ensure_ascii=False`),
> solo reformateada por F-108 al sacar el diccionario a `cuerpo_ficha`. El texto
> JSON se inserta en una columna `JSONB`, y PostgreSQL decodifica `\u00e9` y `é`
> al MISMO valor; los tests leen el JSON con `json.loads`, que tampoco distingue.
> Decisión: **mutante equivalente** respecto al contrato publicado (el `JSONB`
> de `_meta.diccionario` sale idéntico). Solo cambia el texto intermedio.

### 2. `main.py:973` [entero]

- Original: `omitidas = 0`
- Mutado:   `omitidas = 1`

#### Análisis (implementer)

> Por qué ningún test lo caza: ningún test fijaba el número de «sin
> contradiccion» del resumen cuando un objeto no existe; solo las subcadenas
> «con la clave rota» y «fichados que no existen».
> Decisión: **hueco real, cerrado con test**. `test_f108_r14_...` exige ahora
> `Resumen: {total - 2} sin contradiccion` (commit `32fd20b`). Comprobado a mano
> con el mutante aplicado: `1 failed`.

### 3. `main.py:976` [aritmetico]

- Original: `omitidas += 1`
- Mutado:   `omitidas -= 1`

#### Análisis (implementer)

> Por qué ningún test lo caza: el mismo hueco que el anterior (el recuento de
> «sin contradiccion» con una consulta omitida no lo miraba nadie).
> Decisión: **hueco real, cerrado con test** por la misma asercion de
> `test_f108_r14_...` (commit `32fd20b`). Comprobado con el mutante aplicado:
> `1 failed`.

### 4. `main.py:995` [aritmetico]

- Original: `f"Resumen: {len(consultas) - omitidas - fallos - sin_comprobar - inexistentes} sin "`
- Mutado:   `f"Resumen: {len(consultas) - omitidas + fallos - sin_comprobar - inexistentes} sin "`

#### Análisis (implementer)

> Por qué ningún test lo caza: los tests de una clave rota (F-006 y F-108)
> miraban «1 con la clave rota», no el total de «sin contradiccion».
> Decisión: **hueco real, cerrado con test**. `test_f108_r12_una_alternativa_rota_sale_con_uno`
> exige `Resumen: {total - 1} sin contradiccion`. Comprobado con el mutante
> aplicado: `1 failed`.

### 5. `main.py:995` [aritmetico]

- Original: `f"Resumen: {len(consultas) - omitidas - fallos - sin_comprobar - inexistentes} sin "`
- Mutado:   `f"Resumen: {len(consultas) - omitidas - fallos + sin_comprobar - inexistentes} sin "`

#### Análisis (implementer)

> Por qué ningún test lo caza: los tests de timeout miraban «1 sin comprobar»,
> no el total de «sin contradiccion».
> Decisión: **hueco real, cerrado con test**. `test_f108_r13_un_timeout_en_una_alternativa_no_es_un_ok`
> exige `Resumen: {total - 1} sin contradiccion` (commit `3afb1ae`). Comprobado
> con el mutante aplicado: `1 failed`.

