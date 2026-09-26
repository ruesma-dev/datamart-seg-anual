<!-- progress/mutacion_F-025.md -->
# F-025 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-025` el 2026-09-03 15:05.

## Alcance

Origen del diff: **ficheros** (alcance declarado en la orden).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/domain/ventana.py` | 779 |
| **Total** | **779** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 83 |
| Mutantes evaluados | 83 |
| Muertos | 79 |
| Supervivientes | 0 |
| Timeouts | 4 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 7720.4 s |
| SHA de HEAD medido | `073af30aec64992dd1b4b0183a8c2c1373808ee9` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-025_fzlfs3ay/wk_0` | 467.5 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-025_fzlfs3ay/wk_1` | 470.0 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-025_fzlfs3ay/wk_2` | 473.6 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-025_fzlfs3ay/wk_3` | 467.5 |
| Media por mutante evaluado (s) | 93.0 |
| Timeout efectivo por mutante (s) | 948 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 4 |
| Muestreo | no: campaña completa |

## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.

## Timeouts

- `etl_sigrid/domain/ventana.py:207` [not] if not all(isinstance(e, int) and not isinstance(e, bool) for e in estados): -> if all(isinstance(e, int) and not isinstance(e, bool) for e in estados):
- `etl_sigrid/domain/ventana.py:207` [logico] if not all(isinstance(e, int) and not isinstance(e, bool) for e in estados): -> if not all(isinstance(e, int) or not isinstance(e, bool) for e in estados):
- `etl_sigrid/domain/ventana.py:216` [comparacion] meses_sin_actividad=int(bloque[CLAVE_MESES] if meses is None else meses), -> meses_sin_actividad=int(bloque[CLAVE_MESES] if meses is not None else meses),
- `etl_sigrid/domain/ventana.py:242` [booleano] tiene_filas: bool = False -> tiene_filas: bool = True

