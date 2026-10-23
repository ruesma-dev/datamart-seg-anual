<!-- progress/mutacion_F-147.md -->
# F-147 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-147` el 2026-10-22 23:21.

## Alcance

Origen del diff: **rama** (`053777827f7d25e61582f07557ce3818bba8c0c1` .. `feature/F-147-presupuesto-contexto-mcp`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/domain/diccionario.py` | 189 |
| `etl_sigrid/infrastructure/diccionario/cargador_yaml.py` | 9 |
| `etl_sigrid/infrastructure/postgres/diccionario_sql.py` | 15 |
| **Total** | **213** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 31 |
| Mutantes evaluados | 20 |
| Muertos | 19 |
| Supervivientes | 1 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 12173.3 s |
| SHA de HEAD medido | `61e169f81114a7437ee9c490b3f2d855c30657ee` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-147_g0vd_z4y/wk_0` | 1785.8 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-147_g0vd_z4y/wk_1` | 1773.2 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-147_g0vd_z4y/wk_2` | 1799.3 |
| Media por mutante evaluado (s) | 608.7 |
| Timeout efectivo por mutante (s) | 6000 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 6000 |
| Workers | 3 |
| Muestreo | sí — 20 de 31 mutantes, semilla `20260820`, nivel `estandar` |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/domain/diccionario.py:1353` [aritmetico]

- Original: `f"{tope}: sobran {medida.total - tope} ({desglose}). Acorta lo que "`
- Mutado:   `f"{tope}: sobran {medida.total + tope} ({desglose}). Acorta lo que "`

#### Análisis (implementer, 2026-10-22)

> Por qué ningún test lo caza: HUECO REAL. `test_f147_r18_por_encima_del_tope_dice_cuanto_sobra_y_el_desglose`
> comprobaba `"500" in mensaje` con total 29.000 y tope 28.500; el mutante escribe «sobran 57500»,
> que también contiene «500». La cifra de lo que sobra no se comprobaba de verdad.
> Decisión: test reforzado (`"sobran 500 (" in mensaje`). Comprobado a mano aplicando el mutante
> sobre el árbol: `pytest tests/test_f147_presupuesto_contexto.py -k sobra` -> `1 failed`;
> restaurado -> `1 passed`. Queda MUERTO.

