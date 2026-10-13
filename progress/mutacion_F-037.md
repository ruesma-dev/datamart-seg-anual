<!-- progress/mutacion_F-037.md -->
# F-037 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-037` el 2026-10-14 01:25.

> ## ⚠ CAMPAÑA NO VÁLIDA
>
> La línea base de cierre EXPIRÓ en C:/Users/pgris/AppData/Local/Temp/mutacion_F-037_e0373sr3/wk_0: se agotaron los 12000 s concedidos. Ojo, la suite NO falló y NO hay ningún test roto que buscar: se quedó sin tiempo, que es otra cosa. Aun así los números de esta campaña no valen, porque no se ha podido comprobar que la base siguiera verde al terminar.
  Qué hacer: baja los workers (--workers N: cada worker corre una suite entera y todas compiten por la misma máquina) o sube el SUELO 'mutacion.timeout_por_mutante_s' de harness/rigor.json. No toques la suite.
>
> **No cierres la feature con estos números.** Arregla la línea base y repite la campaña.

## Alcance

Origen del diff: **ficheros** (alcance declarado en la orden).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/application/steps/build_tesoreria_step.py` | 157 |
| `etl_sigrid/domain/tesoreria.py` | 194 |
| **Total** | **351** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 45 |
| Mutantes evaluados | 45 |
| Muertos | 43 |
| Supervivientes | 0 |
| Timeouts | 2 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 23686.3 s |
| SHA de HEAD medido | `8ee5e35ca881e2f8837c86de5973117f4fb4f204` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-037_e0373sr3/wk_0` | 717.2 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-037_e0373sr3/wk_1` | 713.8 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-037_e0373sr3/wk_2` | 723.0 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-037_e0373sr3/wk_3` | 713.9 |
| Media por mutante evaluado (s) | 526.4 |
| Timeout efectivo por mutante (s) | 2400 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 2400 |
| Workers | 4 |
| Muestreo | no: campaña completa |

## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.

## Timeouts

- `etl_sigrid/domain/tesoreria.py:192` [comparacion] and vencimiento is not None -> and vencimiento is None
- `etl_sigrid/domain/tesoreria.py:193` [logico] and vencimiento < fecha_limite_previsto_antiguo(fecha_build) -> or vencimiento < fecha_limite_previsto_antiguo(fecha_build)


## Análisis del implementer (2026-10-14): la campaña paralela NO es válida y se reverifica EN SERIE

El arnés la marcó **CAMPAÑA NO VÁLIDA**: la línea base de cierre de `wk_0` agotó los 12.000 s
(la suite no falló: se quedó sin tiempo) y los dos últimos mutantes salieron `timeout`. La
campaña duró 23.686 s y cruzó la noche del 13 al 14 de octubre; la línea base de apertura fue
de ~715 s por worker, así que lo más probable es una suspensión o una contención extrema de la
máquina, no un mutante que cuelgue la suite. Por la regla de F-006 (lo que una campaña paralela
declara muerto se reverifica en serie antes de cerrar una feature crítica) se reevaluaron LOS 45
en serie, aplicando cada mutante en el árbol y restaurándolo:

1. Contra `tests/test_f037_dominio.py`, `test_f037_paso.py` y `test_f037_sql.py` (`pytest -x`):
   **42 muertos y 3 vivos**. Los 2 `timeout` (`tesoreria.py:192` y `:193`) mueren aquí en 0,1 s.
2. Los 3 vivos son las banderas de `@dataclass` (`EfectoTesoreria` `slots=False`; `_SubStep`
   `slots=False` y `frozen=False`). Los mata la guarda genérica de la suite,
   `tests/test_f006_dataclasses_inmutables.py` (`toda_dataclass_del_paquete_usa_slots` /
   `es_inmutable`), que es parte de la suite completa: muertos.

**Resultado: 45 generados, 45 muertos, 0 supervivientes, 0 timeouts** (en serie). Trazas:

```
# Reverificación EN SERIE de los 2 timeouts (mutante aplicado a mano, test del módulo):
        and vencimiento is None
$ python -m pytest tests/test_f037_dominio.py -x -q -p no:cacheprovider --tb=no
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 67 passed in 0.11s
        or vencimiento < fecha_limite_previsto_antiguo(fecha_build)
$ python -m pytest tests/test_f037_dominio.py -x -q -p no:cacheprovider --tb=no
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 67 passed in 0.12s
muertos con los tests de F-037: 42
SUPERVIVIENTE  etl_sigrid/domain/tesoreria.py:96 [booleano] @dataclass(frozen=True, slots=True) -> @dataclass(frozen=True, slots=False)
SUPERVIVIENTE  etl_sigrid/application/steps/build_tesoreria_step.py:54 [booleano] @dataclass(slots=True, frozen=True) -> @dataclass(slots=False, frozen=True)
SUPERVIVIENTE  etl_sigrid/application/steps/build_tesoreria_step.py:54 [booleano] @dataclass(slots=True, frozen=True) -> @dataclass(slots=True, frozen=False)
# Los 3 que sobreviven a los tests de F-037 solos, contra la guarda genérica de F-006:
@dataclass(frozen=True, slots=False)
E   Failed: DID NOT RAISE AttributeError
FAILED tests/test_f006_dataclasses_inmutables.py::test_f006_toda_dataclass_del_paquete_usa_slots[etl_sigrid.domain.tesoreria.EfectoTesoreria]
1 failed, 156 passed, 3 skipped in 1.57s
@dataclass(slots=False, frozen=True)
FAILED tests/test_f006_dataclasses_inmutables.py::test_f006_toda_dataclass_del_paquete_usa_slots[etl_sigrid.application.steps.build_tesoreria_step._SubStep]
1 failed, 99 passed, 3 skipped in 1.57s
@dataclass(slots=True, frozen=False)
FAILED tests/test_f006_dataclasses_inmutables.py::test_f006_toda_dataclass_del_paquete_es_inmutable[etl_sigrid.application.steps.build_tesoreria_step._SubStep]
1 failed, 10 passed in 1.52s
```
