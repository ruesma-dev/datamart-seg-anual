<!-- progress/mutacion_F-024.md -->
# F-024 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-024` el 2026-08-18 16:24.

## Alcance

Origen del diff: **rama** (`1f3d5df5a5519c84fc17b2a451cdce33526d5694` .. `feature/F-024-coherencia-cargas-truncadas`).

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
| Tiempo total | 464.4 s |
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

## Nota de la remedición (2026-08-18, arnés v1.5.0)

Campaña repetida tras actualizar el arnés a la v1.5.0 y fusionar `dev` en la
rama: el motor nuevo puede correr en paralelo (aquí se lanzó con
`--workers 1`, en serie, para medir en las mismas condiciones que la primera
vez) y el `merge-base` del diff cambió al merge del arnés. **Resultado
idéntico**: 108 mutantes, 106 muertos, los 2 mismos supervivientes de
`main.py` ya aceptados como equivalentes. El análisis de arriba es el que
aceptó el humano el 2026-08-18; la regeneración del informe lo había
sustituido por la plantilla vacía y se ha repuesto.
