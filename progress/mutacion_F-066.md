<!-- progress/mutacion_F-066.md -->
# F-066 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-066` el 2026-09-07 00:22.

> **EL COMANDO EXACTO, CON SU BASE** (hallazgo 5 del review; la plantilla del
> arnés no imprime `--base` y por eso hay que escribirlo):
>
> ```bash
> python -m harness.mutacion --feature F-066 --base d1f56aa --workers 1
> ```
>
> **`--base d1f56aa` no es un recorte, es la base correcta.** El valor por
> defecto es `--base dev`, y esta rama **nace de `feature/F-025` sin fusionar**,
> así que el merge-base con `dev` es `cd18e096` y el alcance sale **2.904 líneas
> y 247 mutantes en 11 ficheros**: los de F-025, no los de F-066. Con
> `d1f56aa` —el commit del que sale realmente esta rama— el alcance son las
> **218 líneas y 23 mutantes** de esta feature, que es lo que hay que mutar.
> Quien recalcule con el comando de la cabecera verá 247 y no debe leerlo como
> una campaña recortada.

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
| Tiempo total | 2072.2 s |
| SHA de HEAD medido | `d8c73b8e6750a2afe9ecc7c9a2ac28b770b14117` |
| Línea base (s) — `.` | 132.7 |
| Media por mutante evaluado (s) | 90.1 |
| Timeout efectivo por mutante (s) | 266 — derivado de la línea base × 2.0 |
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
> **Decisión: MUTANTE EQUIVALENTE, exento.**
>
> **FIRMADO POR EL HUMANO el 2026-09-06 a las 20:45 UTC**, que es lo que el
> rigor `critico` exige para levantar `supervivientes_maximos: 0`. Palabra
> literal: «firmo». Queda registrado en la ficha de F-066 de
> `harness/features.json` (commit `5564975`) y en `specs/.../tasks.md`, nota de
> T12. El reviewer lo reprodujo por su cuenta aplicando el mutante y da por
> buena la exención (hallazgo 9 de `progress/review_F-066.md`). Precedente: el
> humano ya eximió campañas enteras en F-042, F-052 y F-025.
>
> **Sobrevivió también en esta campaña**, la tercera y la primera VÁLIDA
> (2026-09-07, 23 mutantes / 22 muertos / 1 superviviente / 0 sin veredicto),
> con el mismo operador y el mismo texto.
>
> Los otros dos supervivientes de la primera pasada **sí eran huecos reales** y
> están muertos desde el commit `ca31adb`: `max_rows=1` (cuántas filas se le
> piden a Sigrid, que corta por filas y por tiempo) y `err=True` (el aviso de
> tabla no medida se colaba en el informe de la salida estándar). Los dos tests
> se comprobaron a mano aplicando cada mutación: con el mutante fallan, con el
> código bueno pasan.

> _Análisis traído de la campaña anterior de esta feature: el mutante volvió a sobrevivir con el mismo operador y el mismo texto. Reléelo si el código de alrededor ha cambiado._

