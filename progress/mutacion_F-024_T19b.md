<!-- progress/mutacion_F-024_T19b.md -->
# F-024 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-024` el 2026-08-19 12:44.

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
| Tiempo total | 1047.1 s |
| Muestreo | no: campaña completa |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `main.py:564` [booleano]

- Original: `click.secho("=== Estado de raw por tabla ===", fg="cyan", bold=True)`
- Mutado:   `click.secho("=== Estado de raw por tabla ===", fg="cyan", bold=False)`

#### Análisis (implementer, 2026-08-19)

> Por qué ningún test lo caza: `bold` es un atributo de PRESENTACIÓN de una
> cabecera decorativa de `check-coherencia`. No cambia el dato, ni el veredicto,
> ni el código de salida, que es lo que los tests de la CLI comprueban. Para
> cazarlo habría que afirmar sobre los códigos ANSI que emite `click`, es decir,
> testear `click` y no el ETL. Verificado además a mano: aplicando la mutación
> en el árbol real, `python -m pytest tests/ -q` da `617 passed`.
> Decisión: **mutante equivalente justificado**, con la misma justificación que
> ya aceptó el reviewer en la Fase B (`progress/impl_F-024.md` §6.1 y
> `progress/review_F-024.md`). Ningún test nuevo: fijar la negrita de una
> cabecera sería ruido de mantenimiento sin valor.

### 2. `main.py:567` [booleano]

- Original: `click.secho("=== Estado de stg ===", fg="cyan", bold=True)`
- Mutado:   `click.secho("=== Estado de stg ===", fg="cyan", bold=False)`

#### Análisis (implementer, 2026-08-19)

> Por qué ningún test lo caza: `bold` es un atributo de PRESENTACIÓN de una
> cabecera decorativa de `check-coherencia`. No cambia el dato, ni el veredicto,
> ni el código de salida, que es lo que los tests de la CLI comprueban. Para
> cazarlo habría que afirmar sobre los códigos ANSI que emite `click`, es decir,
> testear `click` y no el ETL. Verificado además a mano: aplicando la mutación
> en el árbol real, `python -m pytest tests/ -q` da `617 passed`.
> Decisión: **mutante equivalente justificado**, con la misma justificación que
> ya aceptó el reviewer en la Fase B (`progress/impl_F-024.md` §6.1 y
> `progress/review_F-024.md`). Ningún test nuevo: fijar la negrita de una
> cabecera sería ruido de mantenimiento sin valor.


## Nota del implementer (2026-08-19, segunda vuelta de T19)

Esta campaña se lanzó con `--workers 1`. **La del mismo día a las 11:52
(paralela, 16 worktrees) declaró 108 muertos y CERO supervivientes, y ese
número era falso**: estos dos mutantes no los puede matar ningún test —ninguno
menciona `bold`— y se ha comprobado a mano que con la mutación aplicada la
suite entera pasa (`617 passed`). Los resultados buenos son los de aquí, que
además coinciden con la campaña del 2026-08-18 (106/2).

Queda anotado como aviso para el que venga: **si una campaña paralela declara
cero supervivientes donde otra declara dos, no se celebra, se investiga.** El
número que se lleva a un informe tiene que ser reproducible.
