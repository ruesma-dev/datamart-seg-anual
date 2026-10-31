<!-- progress/mutacion_F-150_n16_n17.md -->
# F-150 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-150` el 2026-10-31 07:50.

## Alcance

Origen del diff: **rama** (`b98c8303ed45f3c58830eca4ee501572d5bd6b0c` .. `feature/F-150-receta-caja`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/domain/proyeccion_caja.py` | 98 |
| **Total** | **98** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 33 |
| Mutantes evaluados | 8 |
| Muertos | 6 |
| Supervivientes | 2 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 6888.7 s |
| SHA de HEAD medido | `ddbc54fe7a87864b2a1f3fc85d0ffa47b3e604b1` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-150_etvlw6ic/wk_0` | 1555.6 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-150_etvlw6ic/wk_1` | 1553.4 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-150_etvlw6ic/wk_2` | 1559.6 |
| Media por mutante evaluado (s) | 861.1 |
| Timeout efectivo por mutante (s) | 3000 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 3000 |
| Workers | 3 |
| Muestreo | sí — 8 de 33 mutantes, semilla `20260820`, nivel `estandar` |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/domain/proyeccion_caja.py:472` [entero]

- Original: `if pendiente is None or pendiente <= 0:`
- Mutado:   `if pendiente is None or pendiente <= 1:`

#### Análisis

> Por qué ningún test lo caza: los tests probaban pendientes de 0, negativos y >= 7; ninguno
> entre 0 y 1 EUR, donde el mutante devuelve `{}` (nada enlazado). **Hueco real**, no equivalente.
> Decisión: test nuevo `test_f150_r48_un_pendiente_de_centimos_tambien_enlaza` (0,50 EUR con un
> contrato → fracción 1). Comprobado a mano con el mutante aplicado: 1 failed.

### 2. `etl_sigrid/domain/proyeccion_caja.py:474` [comparacion]

- Original: `vivos = {c: ps for c, ps in pendientes_servir.items() if ps is not None and ps > 0}`
- Mutado:   `vivos = {c: ps for c, ps in pendientes_servir.items() if ps is not None and ps >= 0}`

#### Análisis

> Por qué ningún test lo caza: con `ps >= 0` un contrato ya servido entra con fracción 0. Los
> tests probaban ps 0 solo cuando TODOS eran 0 (total 0 → `{}`) y un negativo junto a uno vivo.
> En el SQL no cambia ningún importe (trozo de 0), pero sí el resultado del dominio: **hueco
> real** en la definición («el servido no se lleva nada»). Decisión: aserción nueva en
> `test_f150_r48_pendiente_de_servir_cero_o_negativo_no_enlaza` (`{7: 0, 8: 400}` → `{8: 0,4}`).
> Comprobado a mano con el mutante aplicado: 1 failed.

