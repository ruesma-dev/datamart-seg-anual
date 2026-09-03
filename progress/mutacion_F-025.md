<!-- progress/mutacion_F-025.md -->
# F-025 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-025` el 2026-09-03 05:20.

## Alcance

Origen del diff: **ficheros** (alcance declarado en la orden).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/domain/ventana.py` | 760 |
| **Total** | **760** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 83 |
| Mutantes evaluados | 83 |
| Muertos | 78 |
| Supervivientes | 5 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 3560.1 s |
| SHA de HEAD medido | `8e9b1f2a02fd50b136ee0abb793024aee231b9ba` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-025_ii8rb0dh/wk_0` | 214.0 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-025_ii8rb0dh/wk_1` | 209.3 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-025_ii8rb0dh/wk_2` | 210.6 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-025_ii8rb0dh/wk_3` | 212.4 |
| Media por mutante evaluado (s) | 42.9 |
| Timeout efectivo por mutante (s) | 429 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 4 |
| Muestreo | no: campaña completa |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/domain/ventana.py:492` [logico]

- Original: `return (sello or "(ninguno)")[:8]`
- Mutado:   `return (sello and "(ninguno)")[:8]`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 2. `etl_sigrid/domain/ventana.py:492` [entero]

- Original: `return (sello or "(ninguno)")[:8]`
- Mutado:   `return (sello or "(ninguno)")[:9]`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 3. `etl_sigrid/domain/ventana.py:666` [entero]

- Original: `obras_miradas: int = 0`
- Mutado:   `obras_miradas: int = 1`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 4. `etl_sigrid/domain/ventana.py:685` [comparacion]

- Original: `return tuple(h for h in self.hallazgos if h.tipo == tipo)`
- Mutado:   `return tuple(h for h in self.hallazgos if h.tipo != tipo)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 5. `etl_sigrid/domain/ventana.py:694` [not]

- Original: `if not self.codigo:`
- Mutado:   `if self.codigo:`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

