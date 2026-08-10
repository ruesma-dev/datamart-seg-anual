<!-- progress/mutacion_F-016.md -->
# F-016 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-016` el 2026-08-10 13:05.

## Alcance

Origen del diff: **rama** (`1e6ea1e9148d77c15a5c9b0823ce9e5f9c21fb66` .. `feature/F-016-refuerzo-tests-f005`).

| Fichero | Líneas en alcance |
|---|---|
| **Total** | **0** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 0 |
| Mutantes evaluados | 0 |
| Muertos | 0 |
| Supervivientes | 0 |
| Timeouts | 0 |
| Tiempo total | 0.0 s |
| Muestreo | no: campaña completa |

## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.

## Por qué el alcance es 0 (justificación escrita, no un N/A en blanco)

`CHECKPOINTS.md` prohíbe saltarse esta puerta marcando N/A sin justificar.
Aquí no se salta: **se ejecuta y sale 0 de verdad**, y el motivo es el
siguiente.

F-016 es una feature de **solo tests**. Su diff contra `dev` toca tres
ficheros y **ninguno es código de producción**:

| Fichero | Por qué no entra en el alcance |
|---|---|
| `tests/test_f016_huecos_alto_f005.py` (nuevo) | `harness.alcance` excluye `tests/` por diseño: mutar un test no mide nada |
| `tests/test_f005_grants.py` (modificado) | ídem |
| `progress/*.md` | `progress/` excluido: no es código |

**Mutar los tests de esta feature sería medir al revés.** La pregunta que
responde una campaña de mutación es «¿los tests cazan un cambio en el código?».
Aquí el producto SON los tests, así que la pregunta se invierte, y esa
respuesta está en otro sitio, medida de verdad y con números:

- `progress/mutacion_F-005_tras_refuerzo.md` — la campaña de F-005 relanzada
  con los tests de F-016 dentro: los **seis** mutantes de riesgo ALTO pasan de
  supervivientes a **muertos**, más dos de riesgo MEDIO de propina.
- `progress/impl_F-016.md` § «Fase RED» — cada uno de los seis mutantes
  aplicado a mano sobre el árbol de hoy, con la traza real del fallo.

Es decir: el rigor de esta feature no se acredita con una campaña sobre su
propio código (no tiene), sino con la campaña sobre el código que sus tests
existen para vigilar. Ese es el número que hay que mirar.

