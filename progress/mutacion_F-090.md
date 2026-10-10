<!-- progress/mutacion_F-090.md -->
# F-090 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-090` el 2026-10-09 21:18.

## Alcance

Origen del diff: **rama** (`75389c5af065e84dcc9d8dccd7a70d4b74c480a8` .. `feature/F-090-documento-adjunto`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/application/steps/build_compras_step.py` | 20 |
| `etl_sigrid/domain/documento_adjuntos.py` | 112 |
| **Total** | **132** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 8 |
| Mutantes evaluados | 8 |
| Muertos | 8 |
| Supervivientes | 0 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 2427.0 s |
| SHA de HEAD medido | `b88fdbbac3aae908033f2a3bc71132dd0d918943` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-090_569ab_po/wk_0` | 708.2 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-090_569ab_po/wk_1` | 714.3 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-090_569ab_po/wk_2` | 722.6 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-090_569ab_po/wk_3` | 709.2 |
| Media por mutante evaluado (s) | 303.4 |
| Timeout efectivo por mutante (s) | 1800 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 1800 |
| Workers | 4 |
| Muestreo | no: campaña completa |

## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.

