<!-- progress/mutacion_F-140.md -->
# F-140 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-140` el 2026-10-26 10:13.

## Alcance

Origen del diff: **rama** (`a5e268ee4eeadfcbac5e6039a3f80ee1062467f0` .. `feature/F-140-proyeccion-caja-ingredientes`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/application/steps/build_tesoreria_step.py` | 87 |
| `etl_sigrid/domain/proyeccion_caja.py` | 429 |
| `etl_sigrid/domain/reanudacion.py` | 5 |
| `etl_sigrid/domain/tesoreria.py` | 52 |
| `etl_sigrid/infrastructure/config/__init__.py` | 2 |
| `etl_sigrid/infrastructure/config/hipotesis_caja_yaml.py` | 66 |
| `etl_sigrid/infrastructure/postgres/hipotesis_caja_sql.py` | 55 |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | 31 |
| **Total** | **727** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 141 |
| Mutantes evaluados | 20 |
| Muertos | 19 |
| Supervivientes | 1 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 6448.8 s |
| SHA de HEAD medido | `e733268520a072eda2e3c39e1984a7c43847ab1e` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-140_j6qr0_pe/wk_0` | 777.7 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-140_j6qr0_pe/wk_1` | 785.8 |
| Media por mutante evaluado (s) | 322.4 |
| Timeout efectivo por mutante (s) | 2400 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 2400 |
| Workers | 2 |
| Muestreo | sí — 20 de 141 mutantes, semilla `20260820`, nivel `estandar` |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/domain/proyeccion_caja.py:331` [logico]

- Original: `etiqueta = codigo if isinstance(codigo, str) and codigo else f"fila {n}"`
- Mutado:   `etiqueta = codigo if isinstance(codigo, str) or codigo else f"fila {n}"`

#### Análisis (implementer, 2026-10-26)

> Por qué ningún test lo caza: los tests de `validar_catalogo` solo daban códigos
> válidos (`"H07"`, `"H9"`) o una fila que no es un mapa (rama anterior, que ya
> etiqueta `fila n`). Ninguno daba un código VACÍO o que no fuera texto, que es
> justo donde `and` y `or` divergen: con `or`, `""` etiqueta el error como `": ..."`
> y `9` o `["H01"]` como `"9: ..."`/`"['H01']: ..."`, en vez de `"fila 1: ..."`.
> Decisión: **hueco real, no equivalente: test nuevo**,
> `tests/test_f140_hipotesis.py::test_f140_r2_sin_codigo_legible_el_error_dice_la_fila`
> (parametrizado con `""`, `9` y `["H01"]`). Verificado a mano: con el mutante
> aplicado, `3 failed`; con el original, `3 passed`.

