<!-- progress/mutacion_F-066.md -->
# F-066 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-066` el 2026-09-06 16:40.

> ## ⚠ CAMPAÑA NO VÁLIDA
>
> La línea base estaba VERDE al empezar y ROJA al terminar en . (tests/test_f024_dominio.py::test_f024_r1_batch_id_tiene_forma_y_es_unico). La base se rompió durante la campaña, así que los mutantes contados como «muertos» pueden no estarlo: estos números NO valen para cerrar una feature. Arregla la suite y repite la campaña.
>
> **No cierres la feature con estos números.** Arregla la línea base y repite la campaña.

## Alcance

Origen del diff: **rama** (`d1f56aa100c7ea94a0c6161dc3de5dde87a773dd` .. `feature/F-066-ingesta-raw-pendientes`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/domain/recuentos.py` | 134 |
| `main.py` | 84 |
| **Total** | **218** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 23 |
| Mutantes evaluados | 23 |
| Muertos | 22 |
| Supervivientes | 1 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 3311.2 s |
| SHA de HEAD medido | `ca31adb6ea75db1aa8242534ed14554da89af1ef` |
| Línea base (s) — `.` | 208.9 |
| Media por mutante evaluado (s) | 144.0 |
| Timeout efectivo por mutante (s) | 418 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 1 |
| Muestreo | no: campaña completa |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `main.py:1995` [booleano]

- Original: `click.secho("=== raw frente a Sigrid, tabla a tabla ===", fg="cyan", bold=True)`
- Mutado:   `click.secho("=== raw frente a Sigrid, tabla a tabla ===", fg="cyan", bold=False)`

#### Análisis

> **Por qué ningún test lo caza:** `bold` no cambia ni una letra del texto ni el
> código de salida; solo pone o quita el atributo ANSI de negrita del título.
> `CliRunner` invoca con color desactivado, así que ni siquiera llega a la
> salida capturada. Un test que lo cazara tendría que afirmar sobre secuencias
> de escape ANSI, es decir, comprobar decoración en vez de comportamiento.
>
> **Decisión: MUTANTE EQUIVALENTE, exento.** Se documenta aquí y en
> `progress/impl_F-066.md`; queda para el humano aceptarlo o pedir el test.
>
> Los otros dos supervivientes de la primera pasada **sí eran huecos reales** y
> están muertos desde el commit `ca31adb`: `max_rows=1` (cuántas filas se le
> piden a Sigrid, que corta por filas y por tiempo) y `err=True` (el aviso de
> tabla no medida se colaba en el informe de la salida estándar). Los dos tests
> se comprobaron a mano aplicando cada mutación: con el mutante fallan, con el
> código bueno pasan.

## Nota sobre el veredicto del arnés

La campaña terminó con **CAMPAÑA NO VÁLIDA**: la línea base estaba verde al
empezar y roja al terminar, en
`tests/test_f024_dominio.py::test_f024_r1_batch_id_tiene_forma_y_es_unico`.

**No es el código de esta feature: ese test es aleatorio por construcción.**
Genera 500 `batch_id` con un sufijo de 3 bytes (16.777.216 valores) y exige que
los 500 sean distintos. Medido aquí mismo, 3.000 repeticiones: **25 lotes con
un repetido, 0,833 %**, contra el 0,741 % que predice la paradoja del
cumpleaños. Con 24 pasadas de la suite en una campaña, la probabilidad de que
salte al menos una vez es de un **18 %**.

Consecuencia para quien lea estos números: los 22 muertos se evaluaron **antes**
de esa rotura y con la base verde en el arranque, pero **el arnés no los
avala**, y con razón: su regla es la correcta. La conclusión que sí se sostiene
sin depender de esta campaña es que los dos supervivientes reales están muertos,
porque eso se verificó **a mano, mutante a mutante**.

El test flaky es de F-024 y **no se ha tocado**: arreglarlo es de esa feature, no
de esta. Queda anotado para el líder.

