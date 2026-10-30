<!-- progress/mutacion_F-150_n11_n15.md -->
# F-150 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-150` el 2026-10-30 17:31.

## Alcance

Origen del diff: **rama** (`065952825277b2a4abfca47d16f650255e3e5b01` .. `feature/F-150-receta-caja`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/application/steps/build_tesoreria_step.py` | 20 |
| `etl_sigrid/domain/proyeccion_caja.py` | 58 |
| **Total** | **78** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 17 |
| Mutantes evaluados | 8 |
| Muertos | 8 |
| Supervivientes | 0 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 9754.7 s |
| SHA de HEAD medido | `5f025556535fbb7a631b25a44fac2ab9cf47aec4` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-150_6o_lbxxe/wk_0` | 2295.1 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-150_6o_lbxxe/wk_1` | 2276.5 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-150_6o_lbxxe/wk_2` | 2273.2 |
| Media por mutante evaluado (s) | 1219.3 |
| Timeout efectivo por mutante (s) | 3000 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 3000 |
| Workers | 3 |
| Muestreo | sí — 8 de 17 mutantes, semilla `20260820`, nivel `estandar` |

## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.

