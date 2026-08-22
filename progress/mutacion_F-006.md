<!-- progress/mutacion_F-006.md -->
# F-006 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-006` el 2026-08-22 02:14.

## Alcance

Origen del diff: **rama** (`4b1d3029c4ea47fb560ee59d70d04d2f2173c0a8` .. `feature/F-006-mcp-azure`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/application/steps/publicar_diccionario_step.py` | 190 |
| `etl_sigrid/domain/diccionario.py` | 1089 |
| `etl_sigrid/domain/inventario.py` | 288 |
| `etl_sigrid/infrastructure/diccionario/__init__.py` | 2 |
| `etl_sigrid/infrastructure/diccionario/cargador_yaml.py` | 468 |
| `etl_sigrid/infrastructure/postgres/catalogo.py` | 166 |
| `etl_sigrid/infrastructure/postgres/diccionario_sql.py` | 332 |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | 156 |
| `etl_sigrid/infrastructure/postgres/unicidad_sql.py` | 274 |
| `main.py` | 226 |
| **Total** | **3191** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 254 |
| Mutantes evaluados | 254 |
| Muertos | 254 |
| Supervivientes | 0 |
| Timeouts | 0 |
| Tiempo total | 658.8 s |
| Muestreo | no: campaña completa |

## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.

