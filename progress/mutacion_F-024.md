<!-- progress/mutacion_F-024.md -->
# F-024 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-024` el 2026-08-18 15:15.

## Alcance

Origen del diff: **rama** (`8de4d9edd363f2697a890d6dcf81168e2092f8e2` .. `feature/F-024-coherencia-cargas-truncadas`).

| Fichero | Líneas en alcance |
|---|---|
| `config/settings.py` | 12 |
| `etl_sigrid/application/steps/build_mart_step.py` | 75 |
| `etl_sigrid/application/steps/build_stg_step.py` | 104 |
| `etl_sigrid/application/steps/ingest_raw_step.py` | 8 |
| `etl_sigrid/domain/coherencia.py` | 270 |
| `etl_sigrid/domain/ejecucion.py` | 74 |
| `etl_sigrid/domain/entities.py` | 7 |
| `etl_sigrid/infrastructure/postgres/frescura.py` | 212 |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | 176 |
| `etl_sigrid/infrastructure/postgres/step_run_recorder.py` | 3 |
| `etl_sigrid/infrastructure/postgres/timings.py` | 53 |
| `main.py` | 274 |
| **Total** | **1268** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 108 |
| Mutantes evaluados | 108 |
| Muertos | 106 |
| Supervivientes | 2 |
| Timeouts | 0 |
| Tiempo total | 604.4 s |
| Muestreo | no: campaña completa |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `main.py:564` [booleano]

- Original: `click.secho("=== Estado de raw por tabla ===", fg="cyan", bold=True)`
- Mutado:   `click.secho("=== Estado de raw por tabla ===", fg="cyan", bold=False)`

#### Análisis (completado por el líder y ACEPTADO por el humano, 2026-08-18)

> Por qué ningún test lo caza: `bold` solo cambia el atributo ANSI de una
> cabecera decorativa de la consola de `check-coherencia`; no altera ningún
> dato, veredicto, código de salida ni texto que un test deba fijar. Los
> tests del comando fijan el texto de las líneas y el código de salida
> (`test_f024_cli.py`), que es lo que importa.
> Decisión: **mutante equivalente, justificado**. Fijar el atributo de
> negrita sería un test de la librería `click`, no de esta feature. Mismo
> criterio que aplicó F-019 con literales de presentación.

### 2. `main.py:567` [booleano]

- Original: `click.secho("=== Estado de stg ===", fg="cyan", bold=True)`
- Mutado:   `click.secho("=== Estado de stg ===", fg="cyan", bold=False)`

#### Análisis (completado por el líder y ACEPTADO por el humano, 2026-08-18)

> Por qué ningún test lo caza: `bold` solo cambia el atributo ANSI de una
> cabecera decorativa de la consola de `check-coherencia`; no altera ningún
> dato, veredicto, código de salida ni texto que un test deba fijar. Los
> tests del comando fijan el texto de las líneas y el código de salida
> (`test_f024_cli.py`), que es lo que importa.
> Decisión: **mutante equivalente, justificado**. Fijar el atributo de
> negrita sería un test de la librería `click`, no de esta feature. Mismo
> criterio que aplicó F-019 con literales de presentación.

