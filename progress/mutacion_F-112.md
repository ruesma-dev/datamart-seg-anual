<!-- progress/mutacion_F-112.md -->
# F-112 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-112` el 2026-09-26 13:54.

## Alcance

Origen del diff: **rama** (`fb52d96e1441cdaa3a505db6e84161e20bcfd873` .. `feature/F-112-cobertura-contra-main`).

| Fichero | Líneas en alcance |
|---|---|
| `harness/alcance.py` | 131 |
| `harness/cobertura.py` | 38 |
| `harness/mutacion.py` | 7 |
| `harness/rutas_sensibles.py` | 15 |
| **Total** | **191** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 27 |
| Mutantes evaluados | 20 |
| Muertos | 18 |
| Supervivientes | 2 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 3611.7 s |
| SHA de HEAD medido | `25795ccd07ab16e7784fd839319d765c67b875eb` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-112_040t16o2/wk_0` | 517.7 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-112_040t16o2/wk_1` | 524.0 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-112_040t16o2/wk_2` | 531.2 |
| Media por mutante evaluado (s) | 180.6 |
| Timeout efectivo por mutante (s) | 2400 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 2400 |
| Workers | 3 |
| Muestreo | sí — 20 de 27 mutantes, semilla `20260820`, nivel `estandar` |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `harness/cobertura.py:167` [entero]

- Original: `return f"diff del merge {hasta[:10]}, ya integrado en {base}"`
- Mutado:   `return f"diff del merge {hasta[:11]}, ya integrado en {base}"`

#### Análisis

> Por qué ningún test lo caza: en el HEAD medido (`25795cc`) ningún test
> ejecutaba la rama `origen == "merge"` de `medido_contra` (la cobertura de
> `init.sh` la dio como línea sin cubrir).
> Decisión: **hueco real, test nuevo** (`90e787e` + `3912100`):
> `test_f112_r5_la_puerta_de_una_rama_integrada_dice_que_midio_su_merge` exige
> la cadena exacta `diff del merge <10 caracteres>, ya integrado en main`.
> Rejugado a mano sobre el árbol: con `[:11]` el test sale ROJO
> (`1 failed, 19 deselected in 3.68s`); restaurado, verde.

### 2. `harness/cobertura.py:168` [entero]

- Original: `return f"diff desde {desde[:10]}, merge-base con {base}"`
- Mutado:   `return f"diff desde {desde[:11]}, merge-base con {base}"`

#### Análisis

> Por qué ningún test lo caza: el test contra `main` comprobaba
> `base[:10] in salida`, y con `[:11]` esos diez caracteres siguen dentro de
> la línea: la aserción era por subcadena, no por formato.
> Decisión: **hueco real, test endurecido** (`48499f4`):
> `test_f112_r2_puerta_cobertura_mide_solo_la_rama_contra_main` exige
> `diff desde <10 caracteres>, merge-base con main`. Rejugado a mano: con
> `[:11]` ROJO (`1 failed, 19 deselected in 1.36s`); restaurado, verde. Los
> dos tests van también al payload de `arnes-base` (`c5666fc`, `ab0df0f`).

