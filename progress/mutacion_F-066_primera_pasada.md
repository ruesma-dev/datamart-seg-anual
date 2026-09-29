<!-- progress/mutacion_F-066.md -->
# F-066 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-066` el 2026-09-06 15:34.

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
| Muertos | 20 |
| Supervivientes | 3 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 3621.8 s |
| SHA de HEAD medido | `ef98c30003be9737c2215b830e0b0b084869de20` |
| Línea base (s) — `.` | 222.5 |
| Media por mutante evaluado (s) | 157.5 |
| Timeout efectivo por mutante (s) | 446 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 1 |
| Muestreo | no: campaña completa |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `main.py:1954` [entero]

- Original: `respuesta = api.leer_sql(consulta, max_rows=1)`
- Mutado:   `respuesta = api.leer_sql(consulta, max_rows=2)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 2. `main.py:1956` [booleano]

- Original: `click.secho(f"  ! {source_table}: Sigrid no contestó ({e})", fg="yellow", err=True)`
- Mutado:   `click.secho(f"  ! {source_table}: Sigrid no contestó ({e})", fg="yellow", err=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 3. `main.py:1995` [booleano]

- Original: `click.secho("=== raw frente a Sigrid, tabla a tabla ===", fg="cyan", bold=True)`
- Mutado:   `click.secho("=== raw frente a Sigrid, tabla a tabla ===", fg="cyan", bold=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

