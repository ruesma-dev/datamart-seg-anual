<!-- progress/mutacion_F-138.md -->
# F-138 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-138` el 2026-10-15 04:35.

## Alcance

Origen del diff: **ficheros** (alcance declarado en la orden).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/domain/liquidatoria.py` | 196 |
| **Total** | **196** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 37 |
| Mutantes evaluados | 20 |
| Muertos | 17 |
| Supervivientes | 3 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 5597.7 s |
| SHA de HEAD medido | `cb2431aecf99326304b87ffb0ab15414636954ea` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-138_87ckyy7g/wk_0` | 587.7 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-138_87ckyy7g/wk_1` | 584.8 |
| Media por mutante evaluado (s) | 279.9 |
| Timeout efectivo por mutante (s) | 2400 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 2400 |
| Workers | 2 |
| Muestreo | sí — 20 de 37 mutantes, semilla `20260820`, nivel `estandar` |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/domain/liquidatoria.py:187` [entero]

- Original: `if not crefec or not crehor or crefec < 0 or crehor < 0:`
- Mutado:   `if not crefec or not crehor or crefec < 1 or crehor < 0:`

#### Análisis (implementer, 2026-10-15)

> Por qué ningún test lo caza: `crefec < 1` solo difiere de `crefec < 0` en `crefec = 0`, y el 0
> ya lo descarta `not crefec`, que se evalúa antes en el mismo `or`. Para cualquier entrada las
> dos condiciones dan lo mismo.
> Decisión: **mutante EQUIVALENTE**. No hay test que pueda distinguirlo.

### 2. `etl_sigrid/domain/liquidatoria.py:187` [logico]

- Original: `if not crefec or not crehor or crefec < 0 or crehor < 0:`
- Mutado:   `if not crefec or not crehor or crefec < 0 and crehor < 0:`

#### Análisis (implementer, 2026-10-15)

> Por qué ningún test lo caza: con `and`, un `crefec` negativo (o un `crehor` negativo) ya no sale
> por la guarda, pero sigue dando `None`: `divmod` de un negativo deja un año (u hora) negativo
> —`divmod(-1, 10_000) == (-1, 9999)`— y `datetime()` lanza `ValueError`, que la función
> convierte en `None`. Los casos `(-20260929, 73806)` y `(20260929, -73806)` del test pasan por
> esa rama y siguen dando `None`. La comparación con negativos es una red redundante con el
> `try/except`; Sigrid no trae negativos (medido: mínimo de `crefec` 20081204).
> Decisión: **mutante EQUIVALENTE** (el comportamiento observable no cambia para ninguna entrada).

### 3. `etl_sigrid/domain/liquidatoria.py:187` [comparacion]

- Original: `if not crefec or not crehor or crefec < 0 or crehor < 0:`
- Mutado:   `if not crefec or not crehor or crefec < 0 or crehor <= 0:`

#### Análisis (implementer, 2026-10-15)

> Por qué ningún test lo caza: `crehor <= 0` solo difiere de `crehor < 0` en `crehor = 0`, que ya
> descarta `not crehor` antes en el mismo `or` (caso `(20260929, 0)` del test, `None` en los dos).
> Decisión: **mutante EQUIVALENTE**.

