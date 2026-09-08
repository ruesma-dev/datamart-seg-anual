<!-- progress/mutacion_F-066_tolerancia_recuentos.md -->
# F-066 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-066` el 2026-09-09 01:29.

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
| Muertos | 29 |
| Supervivientes | 6 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 4264.1 s |
| SHA de HEAD medido | `f94fae66d08b50b3dab7e9901e8c451855d350f7` |
| Línea base (s) — `.` | 165.1 |
| Media por mutante evaluado (s) | 121.8 |
| Timeout efectivo por mutante (s) | 331 — derivado de la línea base × 2.0 |
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

### 3. `etl_sigrid/domain/recuentos.py:165` [logico]

- Original: `return max(medidas, key=lambda r: r.desviacion_pct or 0.0) if medidas else None`
- Mutado:   `return max(medidas, key=lambda r: r.desviacion_pct and 0.0) if medidas else None`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 4. `etl_sigrid/domain/recuentos.py:221` [comparacion]

- Original: `return _SIN_CIFRA if valor is None else f"{valor:+,}".replace(",", ".")`
- Mutado:   `return _SIN_CIFRA if valor is not None else f"{valor:+,}".replace(",", ".")`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 5. `etl_sigrid/domain/recuentos.py:228` [aritmetico]

- Original: `f"  {tabla}: Sigrid {_cifra(s)}, raw {_cifra(r)} ({_diferencia(s - r)})"`
- Mutado:   `f"  {tabla}: Sigrid {_cifra(s)}, raw {_cifra(r)} ({_diferencia(s + r)})"`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 6. `main.py:1988` [booleano]

- Original: `show_default=True,`
- Mutado:   `show_default=False,`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

