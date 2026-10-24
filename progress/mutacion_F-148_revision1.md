<!-- progress/mutacion_F-148_revision1.md -->
# F-148 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-148` el 2026-10-24 16:02.

## Alcance

Origen del diff: **ficheros** (alcance declarado en la orden).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/domain/reanudacion.py` | 106 |
| `etl_sigrid/infrastructure/postgres/reintento_conexion.py` | 137 |
| **Total** | **243** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 20 |
| Mutantes evaluados | 20 |
| Muertos | 20 |
| Supervivientes | 0 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 11862.5 s |
| SHA de HEAD medido | `6cb0de3392554663f3b611fc9f287f1ab465af32` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-148_ukzapun4/wk_0` | 1556.0 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-148_ukzapun4/wk_1` | 1550.0 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-148_ukzapun4/wk_2` | 1549.4 |
| Media por mutante evaluado (s) | 593.1 |
| Timeout efectivo por mutante (s) | 9000 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 9000 |
| Workers | 3 |
| Muestreo | no: campaña completa |

## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.


## Por qué esta campaña (revisión de F-148, pasada 1)

La campaña ENTERA de F-148 (92/92 muertos) está en `progress/mutacion_F-148.md` y no se toca. Esta
es la del delta de la revisión: el cambio 1 solo añade literales a `MARCAS_DEFINITIVAS` (el
generador no muta cadenas: 0 mutantes en sus líneas), pero el riesgo R-a toca la lógica de
`pasos_a_omitir`, así que se mutan ENTEROS (`--ficheros`) los dos módulos tocados. Las líneas
nuevas generan 2 mutantes (`reanudacion.py:94`, `and`→`or` y `<=`→`<`), los dos muertos. Las
marcas nuevas las fijan los casos de forma real de `test_f148_conexion.py` (su fase RED, en
`progress/impl_F-148.md`).

## Reverificación EN SERIE de los 20 muertos (rigor crítico, F-041 pendiente)

Mismo método que en `progress/mutacion_F-148.md`: worktree limpio del HEAD medido (`6cb0de3`), los
mismos 20 mutantes (`generar_mutantes` sobre los dos ficheros enteros) aplicados de uno en uno y
restaurados en `finally`, juzgados con `pytest -x` sobre el subconjunto de F-148 (los cinco
`tests/test_f148_*.py` y los siete de f024/f025/f066/f005/f047); el que no matara, con la suite
entera. Línea base del subconjunto: verde (67,4 s).

**Resultado: 20 de 20 muertos por el subconjunto** (5,0-10,0 s cada uno), 0 supervivientes, 0
indeterminados, misma lista que la campaña. Ningún falso muerto.
