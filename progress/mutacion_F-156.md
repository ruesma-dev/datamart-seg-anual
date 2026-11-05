<!-- progress/mutacion_F-156.md -->
# F-156 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-156` el 2026-11-05 02:56.

## Alcance

Origen del diff: **rama** (`bec363cde4de5d9161540e757f493f7b58b42b86` .. `feature/F-156-postventa`).

| Fichero | Líneas en alcance |
|---|---|
| `config/settings.py` | 53 |
| `etl_sigrid/application/steps/apply_grants_step.py` | 157 |
| `etl_sigrid/application/steps/build_postventa_step.py` | 143 |
| `etl_sigrid/domain/diccionario.py` | 4 |
| `etl_sigrid/domain/documento_adjuntos.py` | 20 |
| `etl_sigrid/domain/postventa.py` | 288 |
| `etl_sigrid/infrastructure/postgres/grants.py` | 41 |
| `main.py` | 56 |
| **Total** | **762** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 77 |
| Mutantes evaluados | 20 |
| Muertos | 19 |
| Supervivientes | 1 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 19878.0 s |
| SHA de HEAD medido | `9720e8270f083f6d743c557cd8a175c1f1fc8ad3` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-156_652ccuv8/wk_0` | 2193.2 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-156_652ccuv8/wk_1` | 2204.1 |
| Media por mutante evaluado (s) | 993.9 |
| Timeout efectivo por mutante (s) | 3000 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 3000 |
| Workers | 2 |
| Muestreo | sí — 20 de 77 mutantes, semilla `20260820`, nivel `estandar` |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/application/steps/build_postventa_step.py:137` [entero]

- Original: `duration_s=round((datetime.utcnow() - t0).total_seconds(), 2),`
- Mutado:   `duration_s=round((datetime.utcnow() - t0).total_seconds(), 3),`

#### Análisis (implementer, 2026-11-05)

> Por qué ningún test lo caza: es la duración de cada sub-paso que solo va al log
> (`logger.info(..., duration_s=...)`); no entra en el `StepResult` ni en `_meta`, y
> ningún consumidor la lee. Con 2 o 3 decimales el log dice lo mismo.
> Decisión: **mutante equivalente a efectos de negocio**, sin test nuevo. Es la misma
> línea, copiada a propósito, que `build_personal_step.py:168` y los demás pasos con
> sub-pasos; fijar el redondeo de un log con un test sería probar el formato, no el ETL.

