<!-- progress/mutacion_F-011.md -->
# F-011 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-011` el 2026-08-20 01:31.

## Alcance

Origen del diff: **rama** (`30efd28f1675a8400dee1d708a4d3b6597c7f9a2` .. `feature/F-011-carga-incremental`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/domain/extraccion.py` | 273 |
| `etl_sigrid/domain/perfil_carga.py` | 289 |
| `etl_sigrid/domain/tiemod.py` | 324 |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | 163 |
| `etl_sigrid/infrastructure/sigrid/bench_extraccion.py` | 206 |
| `etl_sigrid/infrastructure/sigrid/sigrid_api_client.py` | 37 |
| `main.py` | 250 |
| **Total** | **1542** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 189 |
| Mutantes evaluados | 189 |
| Muertos | 187 |
| Supervivientes | 2 |
| Timeouts | 0 |
| Tiempo total | 811.2 s |
| Muestreo | no: campaña completa |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/infrastructure/sigrid/bench_extraccion.py:142` [entero]

- Original: `segundos=round(latencia, 3),`
- Mutado:   `segundos=round(latencia, 4),`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 2. `etl_sigrid/infrastructure/sigrid/sigrid_api_client.py:62` [entero]

- Original: `f"admiten consultas que empiecen por SELECT. Recibido: {sql[:200]!r}"`
- Mutado:   `f"admiten consultas que empiecen por SELECT. Recibido: {sql[:201]!r}"`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

