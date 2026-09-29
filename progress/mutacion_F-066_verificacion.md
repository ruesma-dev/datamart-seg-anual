<!-- progress/mutacion_F-066_verificacion.md -->
# F-066 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-066` el 2026-09-09 02:39.

## Alcance

Origen del diff: **rama** (`b3abcf48160ed0411712a1b30e7faf67c9e77b2e` .. `e2e2ad8`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/domain/recuentos.py` | 195 |
| `main.py` | 46 |
| **Total** | **241** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 35 |
| Mutantes evaluados | 35 |
| Muertos | 33 |
| Supervivientes | 2 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 3871.5 s |
| SHA de HEAD medido | `ddcf8b26487751b69845f9eecc7f3a428bf97ca8` |
| Línea base (s) — `.` | 210.4 |
| Media por mutante evaluado (s) | 110.6 |
| Timeout efectivo por mutante (s) | 421 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 1 |
| Muestreo | no: campaña completa |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/domain/recuentos.py:129` [comparacion]

- Original: `if diferencia < 0:  # type: ignore[operator]`
- Mutado:   `if diferencia <= 0:  # type: ignore[operator]`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 2. `etl_sigrid/domain/recuentos.py:129` [entero]

- Original: `if diferencia < 0:  # type: ignore[operator]`
- Mutado:   `if diferencia < 1:  # type: ignore[operator]`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

