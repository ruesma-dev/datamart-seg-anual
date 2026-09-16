<!-- progress/mutacion_F-078.md -->
# F-078 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-078` el 2026-09-15 13:51.

## Alcance

Origen del diff: **rama** (`c3baf8809dafabb0030ba813c312d530499638c9` .. `feature/F-078-materializar-cp-tipologia`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/application/steps/build_mart_step.py` | 57 |
| `etl_sigrid/infrastructure/postgres/cp_tipologia_sql.py` | 391 |
| `main.py` | 100 |
| **Total** | **548** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 34 |
| Mutantes evaluados | 34 |
| Muertos | 34 |
| Supervivientes | 0 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 3047.4 s |
| SHA de HEAD medido | `0b877f5f2308649d0dbe355a08a21667dc1810ec` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-078_x7ofjewc/wk_0` | 377.0 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-078_x7ofjewc/wk_1` | 371.5 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-078_x7ofjewc/wk_2` | 372.4 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-078_x7ofjewc/wk_3` | 375.0 |
| Media por mutante evaluado (s) | 89.6 |
| Timeout efectivo por mutante (s) | 754 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 4 |
| Muestreo | no: campaña completa |

## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.

