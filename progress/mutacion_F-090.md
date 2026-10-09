<!-- progress/mutacion_F-090.md -->
# F-090 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-090` el 2026-10-09 20:03.

> ## ⚠ CAMPAÑA NO VÁLIDA
>
> La línea base de cierre EXPIRÓ en C:/Users/pgris/AppData/Local/Temp/mutacion_F-090_t8k7oswg/wk_0: se agotaron los 600 s concedidos. Ojo, la suite NO falló y NO hay ningún test roto que buscar: se quedó sin tiempo, que es otra cosa. Aun así los números de esta campaña no valen, porque no se ha podido comprobar que la base siguiera verde al terminar.
  Qué hacer: baja los workers (--workers N: cada worker corre una suite entera y todas compiten por la misma máquina) o sube el SUELO 'mutacion.timeout_por_mutante_s' de harness/rigor.json. No toques la suite.
>
> **No cierres la feature con estos números.** Arregla la línea base y repite la campaña.

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
| Tiempo total | 3567.5 s |
| SHA de HEAD medido | `a2b873f1db1b112381266cd4074dade7b88d2ed8` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-090_t8k7oswg/wk_0` | 534.9 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-090_t8k7oswg/wk_1` | 530.8 |
| Media por mutante evaluado (s) | 445.9 |
| Timeout efectivo por mutante (s) | 1070 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 2 |
| Muestreo | no: campaña completa |

## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.

