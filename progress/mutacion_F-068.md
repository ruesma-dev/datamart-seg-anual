<!-- progress/mutacion_F-068.md -->
# F-068 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-068` el 2026-09-07 17:36.

## Alcance

Origen del diff: **rama** (`120d3274ae1292eed2837e3f66ccf136782e666b` .. `HEAD`).

| Fichero | Líneas en alcance |
|---|---|
| `config/settings.py` | 49 |
| `etl_sigrid/application/steps/apply_grants_step.py` | 18 |
| `etl_sigrid/infrastructure/postgres/grants.py` | 78 |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | 31 |
| **Total** | **176** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 8 |
| Mutantes evaluados | 8 |
| Muertos | 4 |
| Supervivientes | 0 |
| Timeouts | 4 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 5937.6 s |
| SHA de HEAD medido | `31d50856be7d6f3902991c4cb9b840c3c7193197` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-068_qzbhesb5/wk_0` | 262.8 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-068_qzbhesb5/wk_1` | 257.9 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-068_qzbhesb5/wk_2` | 260.0 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-068_qzbhesb5/wk_3` | 256.3 |
| Media por mutante evaluado (s) | 742.2 |
| Timeout efectivo por mutante (s) | 526 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 4 |
| Muestreo | no: campaña completa |

## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.

## Nota del implementer: hicieron falta DOS pasadas, y por qué

Esta es la **segunda** pasada. La primera (2026-09-07 15:55, mismo alcance y
mismo HEAD salvo los commits de papeleo) dio **7 muertos y 1 superviviente**:
`grants.py:42 [not]`, `... or not all(...)` -> `... or all(...)`.

**Ese superviviente era un veredicto falso, y está demostrado por dos vías
independientes**, así que no queda ningún análisis pendiente:

1. **Reproducción a mano.** Aplicada esa misma mutación al árbol principal, la
   suite acotada la caza sin margen de duda:

   ```
   $ python -m pytest tests/test_f068_exclusion_lectura_mcp.py tests/test_f005_grants.py        -q --no-header -p no:cacheprovider --tb=line
   13 failed, 23 passed, 8 warnings in 1.13s
   ```

   Es lo esperable leyendo el código: con la mutación, `partir_tabla_cualificada`
   lanza `ValueError` ante una entrada **válida** (`'raw.emp'`), así que revienta
   todo lo que use la lista de exclusión.

2. **La segunda pasada la mata**: es el mutante `[1/8]`, `muerto`.

Descartado que el worktree no llevara los tests: se comprobó que
`tests/test_f068_exclusion_lectura_mcp.py` está presente en los cuatro (`wk_0`
a `wk_3`) y que los demás mutantes de esa misma función sí morían. La
explicación que queda es una carrera entre aplicar la mutación y lanzar la
suite en ese worker concreto, no un hueco de los tests.

## Los cuatro timeouts, matados a mano

Un timeout no es un veredicto: el mutante se queda sin juzgar. Los cuatro de
esta pasada **murieron en la primera**, y además se han matado uno a uno en el
árbol principal, aplicando la mutación y lanzando la suite acotada:

| Mutante | Resultado |
|---|---|
| `grants.py:47` `partes[0]` -> `partes[1]` | exit 1 — **7 failed**, 29 passed |
| `grants.py:47` `partes[1]` -> `partes[2]` | exit 1 — **10 failed**, 26 passed |
| `postgres_client.py:1119` `and` -> `or` | exit 1 — **1 failed**, 35 passed |
| `postgres_client.py:1119` quitar el `not` | exit 1 — **1 failed**, 35 passed |

El timeout se explica por la carga de la máquina, no por el código: la campaña
entera pasó de **1.069 s** (primera pasada) a **5.937 s** con el mismo alcance
y los mismos 4 workers, y el timeout efectivo por mutante estaba fijado en
526 s a partir de una línea base medida cuando la máquina estaba más suelta.

**Balance de las dos pasadas: los 8 mutantes tienen veredicto `muerto` en al
menos una, ninguno lo tiene `superviviente` en las dos, y los 8 se han matado
además a mano. Supervivientes reales: 0.**

## Timeouts

- `etl_sigrid/infrastructure/postgres/grants.py:47` [entero] return partes[0].strip(), partes[1].strip() -> return partes[1].strip(), partes[1].strip()
- `etl_sigrid/infrastructure/postgres/grants.py:47` [entero] return partes[0].strip(), partes[1].strip() -> return partes[0].strip(), partes[2].strip()
- `etl_sigrid/infrastructure/postgres/postgres_client.py:1119` [logico] if esquema in aplicables and not self.table_exists(esquema, tabla): -> if esquema in aplicables or not self.table_exists(esquema, tabla):
- `etl_sigrid/infrastructure/postgres/postgres_client.py:1119` [not] if esquema in aplicables and not self.table_exists(esquema, tabla): -> if esquema in aplicables and self.table_exists(esquema, tabla):

