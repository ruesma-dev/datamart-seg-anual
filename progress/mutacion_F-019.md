<!-- progress/mutacion_F-019.md -->
# F-019 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-019` el 2026-08-10 12:35.

## Alcance

Origen del diff: **rama** (`2cb6de76fd81762b43de779198e2ada73d228647` .. `feature/F-019-plan-mensual-por-tramos`).

| Fichero | Líneas en alcance |
|---|---|
| `config/settings.py` | 21 |
| `etl_sigrid/application/steps/build_stg_step.py` | 205 |
| `etl_sigrid/domain/tramos.py` | 125 |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | 107 |
| **Total** | **458** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 41 |
| Mutantes evaluados | 41 |
| Muertos | 41 |
| Supervivientes | 0 |
| Timeouts | 0 |
| Tiempo total | 145.1 s |
| Muestreo | no: campaña completa |

## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.

