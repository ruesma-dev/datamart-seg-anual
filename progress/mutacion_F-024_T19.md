<!-- progress/mutacion_F-024_T19.md -->
# F-024 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-024` el 2026-08-19 11:52.

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
| Muertos | 108 |
| Supervivientes | 0 |
| Timeouts | 0 |
| Tiempo total | 270.9 s |
| Muestreo | no: campaña completa |

## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.

