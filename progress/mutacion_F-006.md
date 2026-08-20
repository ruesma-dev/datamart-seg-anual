<!-- progress/mutacion_F-006.md -->
# F-006 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-006` el 2026-08-20 17:58.

## Alcance

Origen del diff: **rama** (`4b1d3029c4ea47fb560ee59d70d04d2f2173c0a8` .. `feature/F-006-mcp-azure`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/application/steps/publicar_diccionario_step.py` | 190 |
| `etl_sigrid/domain/diccionario.py` | 1024 |
| `etl_sigrid/domain/inventario.py` | 288 |
| `etl_sigrid/infrastructure/diccionario/__init__.py` | 2 |
| `etl_sigrid/infrastructure/diccionario/cargador_yaml.py` | 435 |
| `etl_sigrid/infrastructure/postgres/diccionario_sql.py` | 236 |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | 82 |
| `main.py` | 67 |
| **Total** | **2324** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 161 |
| Mutantes evaluados | 161 |
| Muertos | 161 |
| Supervivientes | 0 |
| Timeouts | 0 |
| Tiempo total | 377.8 s |
| Muestreo | no: campaña completa |

## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.

