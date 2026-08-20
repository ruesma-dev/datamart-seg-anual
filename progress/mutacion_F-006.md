<!-- progress/mutacion_F-006.md -->
# F-006 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-006` el 2026-08-20 22:00.

## Alcance

Origen del diff: **rama** (`4b1d3029c4ea47fb560ee59d70d04d2f2173c0a8` .. `feature/F-006-mcp-azure`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/application/steps/publicar_diccionario_step.py` | 190 |
| `etl_sigrid/domain/diccionario.py` | 1025 |
| `etl_sigrid/domain/inventario.py` | 288 |
| `etl_sigrid/infrastructure/diccionario/__init__.py` | 2 |
| `etl_sigrid/infrastructure/diccionario/cargador_yaml.py` | 468 |
| `etl_sigrid/infrastructure/postgres/diccionario_sql.py` | 236 |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | 82 |
| `main.py` | 67 |
| **Total** | **2358** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 166 |
| Mutantes evaluados | 166 |
| Muertos | 162 |
| Supervivientes | 0 |
| Timeouts | 4 |
| Tiempo total | 633.2 s |
| Muestreo | no: campaña completa |

## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.

## Timeouts

- `etl_sigrid/domain/diccionario.py:137` etl_sigrid/domain/diccionario.py:137 [entero] "grano": 20, -> "grano": 21,
- `etl_sigrid/domain/diccionario.py:140` etl_sigrid/domain/diccionario.py:140 [entero] "ejemplo_pregunta": 20, -> "ejemplo_pregunta": 21,
- `etl_sigrid/domain/diccionario.py:173` etl_sigrid/domain/diccionario.py:173 [booleano] @dataclass(frozen=True, slots=True) -> @dataclass(frozen=False, slots=True)
- `etl_sigrid/domain/diccionario.py:189` etl_sigrid/domain/diccionario.py:189 [booleano] @dataclass(frozen=True, slots=True) -> @dataclass(frozen=False, slots=True)

