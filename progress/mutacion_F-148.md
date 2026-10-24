<!-- progress/mutacion_F-148.md -->
# F-148 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-148` el 2026-10-24 06:57.

## Alcance

Origen del diff: **rama** (`9ff322f7588d7e3faeaff12a27ef70866ae05ce4` .. `feature/F-148-robustez-nocturna`).

| Fichero | Líneas en alcance |
|---|---|
| `config/settings.py` | 20 |
| `etl_sigrid/application/orchestrator.py` | 51 |
| `etl_sigrid/application/steps/ingest_raw_step.py` | 56 |
| `etl_sigrid/domain/ejecucion.py` | 20 |
| `etl_sigrid/domain/reanudacion.py` | 85 |
| `etl_sigrid/domain/tiemod.py` | 1 |
| `etl_sigrid/infrastructure/postgres/client_factory.py` | 1 |
| `etl_sigrid/infrastructure/postgres/conninfo.py` | 10 |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | 123 |
| `etl_sigrid/infrastructure/postgres/reintento_conexion.py` | 128 |
| `etl_sigrid/infrastructure/postgres/sesion_carga.py` | 176 |
| `main.py` | 134 |
| **Total** | **805** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 92 |
| Mutantes evaluados | 92 |
| Muertos | 92 |
| Supervivientes | 0 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 31149.2 s |
| SHA de HEAD medido | `c2e226dd8e9ae8497834a4ef8887dfd02ab6d19b` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-148_vkxow2ee/wk_0` | 1002.7 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-148_vkxow2ee/wk_1` | 1012.6 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-148_vkxow2ee/wk_2` | 1014.4 |
| Media por mutante evaluado (s) | 338.6 |
| Timeout efectivo por mutante (s) | 9000 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 9000 |
| Workers | 3 |
| Muestreo | no: campaña completa |

## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.


## Reverificación EN SERIE de los 92 muertos (rigor crítico, F-041 pendiente)

La campaña de arriba es PARALELA (3 workers) y la paralela puede dar FALSOS MUERTOS (memoria
«coste real de una campaña de mutación»: mientras F-041 no esté hecha, con rigor crítico lo
declarado muerto se reverifica en serie). Hecho el 2026-10-24 por el implementer:

- **Cómo**: un `git worktree` limpio del mismo HEAD medido (`c2e226d`), los mismos 92 mutantes
  (`generar_mutantes` sobre el mismo alcance), aplicados **de uno en uno** con
  `aplicar_mutante` y restaurados en `finally`. Cada uno se juzga con `pytest -x` sobre un
  subconjunto (los cinco `tests/test_f148_*.py` más `test_f024_cli`, `test_f024_steps`,
  `test_f024_dominio`, `test_f025_firma_paso`, `test_f066_reconciliar_columnas`,
  `test_f005_verificacion`, `test_f047_nocturna`); el que el subconjunto no mata, con la
  **suite entera**. Un test que cae es un test que cae: muerto por subconjunto = muerto.
- **Línea base del subconjunto**: verde (código 0, 53,7 s).
- **Resultado**: **92 de 92 muertos, 0 supervivientes, 0 indeterminados.** 90 los mata el
  subconjunto (media 4,6 s, máximo 20,9 s); 2 necesitaron la suite entera y murieron en ella:
  `sesion_carga.py:49` `@dataclass(frozen=True → False, …)` (260,2 s) y
  `@dataclass(…, slots=True → False)` (226,8 s), que caen en tests de otros ficheros.
  Tiempo total en serie: 902,6 s de mutantes.
- **Lista idéntica a la de la campaña**, con una salvedad del LOG de la campaña: imprime 91
  líneas de progreso (`[1/92]` … `[91/92]`) aunque su resumen cuenta 92. La que no se imprimió
  es `sesion_carga.py:111 [not] if not (comprobar and …) -> if comprobar and …`; en serie,
  muerto por el subconjunto en 2,8 s.

Conclusión: ningún falso muerto. Las cifras de la campaña quedan confirmadas.
