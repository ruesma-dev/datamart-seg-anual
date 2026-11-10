<!-- progress/mutacion_F-040.md -->
# F-040 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-040` el 2026-11-10 10:08.

## Alcance

Origen del diff: **rama** (`66b4eb089bf19519b487c03b3c86dc0715156b5d` .. `feature/F-040-ingresos`).

| Fichero | Líneas en alcance |
|---|---|
| `config/settings.py` | 18 |
| `etl_sigrid/application/steps/build_ventas_step.py` | 139 |
| `etl_sigrid/domain/diccionario.py` | 5 |
| `etl_sigrid/domain/ventas.py` | 266 |
| `main.py` | 56 |
| **Total** | **484** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 61 |
| Mutantes evaluados | 61 |
| Muertos | 58 |
| Supervivientes | 3 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 19465.1 s |
| SHA de HEAD medido | `fcfd86f72c340b53ef5c8a0563846dd2003ae006` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-040_mpxr0w7c/wk_0` | 1354.0 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-040_mpxr0w7c/wk_1` | 1358.0 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-040_mpxr0w7c/wk_2` | 1336.4 |
| Media por mutante evaluado (s) | 319.1 |
| Timeout efectivo por mutante (s) | 9000 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 9000 |
| Workers | 3 |
| Muestreo | no: campaña completa |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/application/steps/build_ventas_step.py:119` [booleano]
**Aceptación del humano.** Los tres supervivientes, con los otros dos de L51 (`slots`/`frozen`) que esta
campaña ya mata o no genera, los aceptó por escrito el humano el **2026-11-10** («1 acepto»), a la vista de
la justificación de `progress/impl_F-040.md` § 7. El reviewer los da por buenos en la pasada 3
(`progress/review_F-040.md` § Condición). En `etl_sigrid/domain/ventas.py` no sobrevive ninguno.

### 1. `etl_sigrid/application/steps/build_ventas_step.py:119` [booleano]

- Original: `sub_step=sub.name, duration_s=duration, exc_info=True,`
- Mutado:   `sub_step=sub.name, duration_s=duration, exc_info=False,`

> **Por qué ningún test lo caza:** solo cambia si el log del sub-paso que falla lleva la traza. El paso
> sigue FAILED y relanza la excepción igual.
> **Decisión:** equivalente a efectos del contrato. Matarlo sería testear el formato del log. **Aceptado
> por el humano el 2026-11-10.**

### 2. `etl_sigrid/application/steps/build_ventas_step.py:126` [entero]

- Original: `rows = 0`
- Mutado:   `rows = 1`

> **Por qué ningún test lo caza:** en un sub-paso sin tabla destino, `rows` solo va al log. No entra en
> `total_rows` ni en `_meta.etl_runs`.
> **Decisión:** equivalente a efectos del contrato. **Aceptado por el humano el 2026-11-10.**

### 3. `etl_sigrid/application/steps/build_ventas_step.py:133` [entero]

- Original: `duration_s=round((datetime.utcnow() - t0).total_seconds(), 2),`
- Mutado:   `duration_s=round((datetime.utcnow() - t0).total_seconds(), 3),`

> **Por qué ningún test lo caza:** solo cambia los decimales de la duración que se escribe en el log.
> **Decisión:** equivalente a efectos del contrato. **Aceptado por el humano el 2026-11-10.**

## Campaña previa (informativa, no cuenta)

Sobre `39c21d4` (antes del ciclo 2), con 58 mutantes: 55 muertos y los mismos 3 supervivientes, en
24.858,8 s. La línea base salió en verde.
