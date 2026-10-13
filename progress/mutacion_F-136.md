<!-- progress/mutacion_F-136.md -->
# F-136 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-136` el 2026-10-13 04:45.

## Alcance

Origen del diff: **rama** (`dc1797bafbff37627862ee8a0a2941022fa6d0a6` .. `feature/F-136-usuario-mcp-total`).

| Fichero | Líneas en alcance |
|---|---|
| `config/settings.py` | 31 |
| `etl_sigrid/application/steps/apply_grants_step.py` | 97 |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | 55 |
| **Total** | **183** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 15 |
| Mutantes evaluados | 15 |
| Muertos | 15 |
| Supervivientes | 0 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 3189.2 s |
| SHA de HEAD medido | `974ff6819035fc3d88c1d377fc46c4fd09842a23` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-136_6250yakp/wk_0` | 602.4 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-136_6250yakp/wk_1` | 607.7 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-136_6250yakp/wk_2` | 602.6 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-136_6250yakp/wk_3` | 606.4 |
| Media por mutante evaluado (s) | 212.6 |
| Timeout efectivo por mutante (s) | 2400 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 2400 |
| Workers | 4 |
| Muestreo | no: campaña completa |

## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.

