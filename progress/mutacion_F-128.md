<!-- progress/mutacion_F-128.md -->
# F-128 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-128` el 2026-10-19 00:12.

## Alcance

Origen del diff: **ficheros** (alcance declarado en la orden).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/domain/cabecera_compra.py` | 528 |
| **Total** | **528** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 22 |
| Mutantes evaluados | 20 |
| Muertos | 20 |
| Supervivientes | 0 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 593.9 s |
| SHA de HEAD medido | `0fa730598aaf3824360b0058c30c90ac1e3da253` |
| Línea base (s) — `.` | 573.3 |
| Media por mutante evaluado (s) | 29.7 |
| Timeout efectivo por mutante (s) | 1147 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 4 |
| Muestreo | sí — 20 de 22 mutantes, semilla `20260820`, nivel `estandar` |

## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.


## Nota del implementer: suite ACOTADA a los importadores del módulo

La primera campaña (`python -m harness.mutacion --feature F-128 --ficheros
etl_sigrid/domain/cabecera_compra.py`, paralela con 4 workers) abortó sin veredictos:
«LÍNEA BASE SIN TERMINAR: la suite SIN MUTAR agotó los 600 s» (la suite entera tarda hoy
~54 min con cobertura). El propio mensaje del arnés dice «si ni con esa holgura cabe la suite
limpia, entonces sí: acótala». Esta campaña se lanzó con `harness.mutacion.main(...,
ejecutor=EjecutorPytest(...))` y la suite acotada a los CUATRO ficheros que importan el módulo
(`grep -rl cabecera_compra`: `tests/test_f128_{dominio,sql,restringida,diccionario}.py`), en
serie (con `ejecutor` el arnés no paraleliza: la fila «Workers 4» es el valor por defecto, no
lo usado). Ningún otro test importa `cabecera_compra`, así que la acotación no puede convertir
un superviviente en muerto. Misma semilla y mismo muestreo (20 de 22) que la orden estándar.
