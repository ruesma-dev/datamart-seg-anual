<!-- progress/mutacion_F-085.md -->
# F-085 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-085` el 2026-10-08 01:06.

## Alcance

Origen del diff: **rama** (`24f32faa84c969149d023d0cfb7e0109cb20ba5a` .. `feature/F-085-quien-aprobo-que-y-cuando`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/application/steps/build_compras_step.py` | 18 |
| `etl_sigrid/application/steps/build_personal_step.py` | 12 |
| `etl_sigrid/domain/documento_procesos.py` | 191 |
| **Total** | **221** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 49 |
| Mutantes evaluados | 20 |
| Muertos | 20 |
| Supervivientes | 0 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 8873.9 s |
| SHA de HEAD medido | `aa5b10fbd5182ea64691522c75cf8de26bd6e24d` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-085_ixk2fgx6/wk_0` | 1549.6 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-085_ixk2fgx6/wk_1` | 1571.8 |
| Media por mutante evaluado (s) | 443.7 |
| Timeout efectivo por mutante (s) | 3600 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 3600 |
| Workers | 2 |
| Muestreo | sí — 20 de 49 mutantes, semilla `20260820`, nivel `estandar` |

## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.

