<!-- progress/mutacion_F-135.md -->
# F-135 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-135` el 2026-10-11 06:45.

## Alcance

Origen del diff: **rama** (`5f31a3d1d1507f0e197715436a199cc3b0386cf4` .. `feature/F-135-restringir-personal-contabilidad`).

| Fichero | Líneas en alcance |
|---|---|
| `config/settings.py` | 66 |
| `etl_sigrid/application/steps/apply_grants_step.py` | 87 |
| `etl_sigrid/application/steps/build_contabilidad_step.py` | 57 |
| `etl_sigrid/domain/diccionario.py` | 1 |
| `etl_sigrid/domain/restriccion_personal.py` | 128 |
| `etl_sigrid/infrastructure/postgres/grants.py` | 108 |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | 83 |
| **Total** | **530** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 25 |
| Mutantes evaluados | 25 |
| Muertos | 25 |
| Supervivientes | 0 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 6047.3 s |
| SHA de HEAD medido | `6ff4f16388dd1ca6034d69671c099e68dbb78f9d` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-135_wfg07pto/wk_0` | 979.4 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-135_wfg07pto/wk_1` | 976.6 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-135_wfg07pto/wk_2` | 972.7 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-135_wfg07pto/wk_3` | 984.7 |
| Media por mutante evaluado (s) | 241.9 |
| Timeout efectivo por mutante (s) | 1800 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 1800 |
| Workers | 4 |
| Muestreo | no: campaña completa |

## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.

