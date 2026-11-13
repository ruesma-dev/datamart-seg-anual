<!-- progress/mutacion_F-161.md -->
# F-161 · Campaña de mutación (nivel `estandar`: INFORMATIVA)

Orden: `python -m harness.mutacion --feature F-161 --timeout 2400 --workers 3`,
lanzada el 2026-11-13 16:30 sobre `2ebe20f` (código aprobado, review pasada 2).
Selección de tests apagada (cada mutante con la suite entera).

**Informe escrito a mano, no por la herramienta.** La campaña evaluó los 20
mutantes en paralelo y entró en el repaso en serie de los 7 timeouts; su línea
base de repaso tardó **2348,5 s contra un tope de 2400 s**, así que el repaso no
iba a distinguir nada. Por orden del líder (aprobada por el humano) se mató el
árbol de procesos, se ejecutó `--restaurar` (solo había un mutante aplicado en
el worktree `wk_0`, nunca en el árbol principal), se borraron los worktrees
`mutacion_F-161_*` y los 7 timeouts se reclasificaron aparte (ver abajo).

## Alcance y línea base

- Diff `d450937..feature/F-161-versiones-sin-reparto`: 4 ficheros, 237 líneas de
  producción. Muestreo uno por línea, tope 20, semilla `20260820`.
- Los 20 mutantes del muestreo cayeron en `etl_sigrid/domain/master_versiones.py`.
- Línea base paralela en verde: wk_0 2041,6 s · wk_1 2039,4 s · wk_2 2017,3 s.
- Repaso en serie: base wk_0 en verde en 2348,5 s (tope 2400 s): repaso abortado.

## Totales

| Métrica | Valor |
|---|---|
| Mutantes evaluados | 20 |
| Muertos (suite entera) | 11 |
| Supervivientes (suite entera) | 2 (:88, :104) |
| Timeouts de la campaña | 7 → reclasificados: 5 muertos, 2 supervivientes |
| **Total tras reclasificar** | **16 muertos, 4 supervivientes (1 equivalente, 3 huecos)** |

## Los 20 mutantes (`etl_sigrid/domain/master_versiones.py`)

| # | Línea | Mutación | Resultado |
|---|---|---|---|
| 1 | 41 | `slots=True` → `slots=False` | muerto |
| 2 | 60 | `"ABC" in` → `not in` | muerto |
| 3 | 57 | `== 0` → `!= 0` | muerto |
| 4 | 62 | `"VALORADA" in` → `not in` | muerto |
| 5 | 66 | `"CIERRE" in` → `not in` | muerto |
| 6 | 64 | `"VALORADA" in` → `not in` | muerto |
| 7 | 79 | `if not tiene_reparto` → `if tiene_reparto` | muerto |
| 8 | 87 | `month == 12` → `== 13` | muerto |
| 9 | 81 | `not con` → `con` | muerto |
| 10 | 88 | `mes.year + 1` → `+ 2` | **superviviente: hueco de test** |
| 11 | 93 | `is None` → `is not None` | timeout → muerto (12 tests) |
| 12 | 89 | `month + 1` → `+ 2` | timeout → muerto (4 tests) |
| 13 | 94 | `return False` → `return True` | timeout → **superviviente: equivalente** |
| 14 | 96 | `and` → `or` | timeout → muerto (3 tests) |
| 15 | 95 | `if temporal` → `if not temporal` | timeout → muerto (7 tests) |
| 16 | 97 | `n_lineas > 0` → `> 1` | timeout → **superviviente: hueco de test** |
| 17 | 108 | `< limite` → `<= limite` | muerto |
| 18 | 104 | `date(..., 1)` → `date(..., 2)` | **superviviente: equivalente** |
| 19 | 110 | `if not candidatas` → `if candidatas` | muerto |
| 20 | 112 | `max(` → `min(` | timeout → muerto (4 tests) |

## Reclasificación de los 7 timeouts

Cada mutante aplicado de uno en uno en un worktree temporal de `2ebe20f`, con
`pytest tests/test_f161_*.py` (los únicos que importan
`etl_sigrid.domain.master_versiones`: `test_f161_dominio.py` y
`test_f161_sandbox.py`; ningún código de producción lo importa). Base: 118
passed, 21 skipped (la sandbox se salta sin `F161_SANDBOX_DSN`). Tras cada uno
se restauró el fichero y se comprobó que quedaba idéntico.

| Línea | Resultado | Lo mata (entre otros) |
|---|---|---|
| :89 | muerto, 4 failed | `test_f161_r14_el_mes_incluye_la_fecha_efectiva_de_ese_mes`, `test_f161_r10_la_temporal_es_la_de_hoy` |
| :93 | muerto, 12 failed | `test_f161_r10_sin_fecha_de_creacion_no_rige`, `test_f161_r14_el_mes_de_diciembre_pasa_de_ano` |
| :94 | superviviente, 0 failed | — |
| :95 | muerto, 7 failed | `test_f161_r14_la_version_0_fuera_del_ultimo_cierre`, `test_f161_r10_sin_reparto_no_rige_aunque_sea_cuatrimestral` |
| :96 | muerto, 3 failed | `test_f161_r10_sin_reparto_no_rige_aunque_sea_cuatrimestral`, `test_f161_r10_sin_fecha_de_creacion_no_rige` |
| :97 | superviviente, 0 failed | — |
| :112 | muerto, 4 failed | `test_f161_r14_empate_de_fecha_gana_la_mayor_version` |

Cada mutante tardó entre 5 y 9 s con los tests de F-161. Los timeouts eran,
por tanto, de la máquina (tres suites de ~34 min compitiendo con otra campaña,
la de F-080), no de un bucle del mutante.

## Supervivientes (clasificados, NO matados: la campaña es informativa)

- **:88 `date(mes.year + 1, 1, 1)` → `+ 2` · hueco de test.** Con diciembre, el
  límite pasa a ser el 1 de enero de dos años después. El único test de
  diciembre (`test_f161_r14_el_mes_de_diciembre_pasa_de_ano`) tiene una versión
  del 31-12, que entra con los dos límites. Lo mataría una versión con fecha
  efectiva del año siguiente que NO debe regir diciembre.
- **:94 `return False` → `return True` · equivalente.** Solo se alcanza con
  `fec_efectiva is None`, y el único llamante (`version_vigente`, l.108) exige
  además `v.fec_efectiva is not None`, así que la versión queda fuera igual.
  `_elegible` no se usa en ningún otro sitio.
- **:97 `n_lineas > 0` → `> 1` · hueco de test.** Ningún test tiene una versión
  de cierre con exactamente 1 línea (`test_f161_r14_sin_lineas_...` usa 0 y el
  resto, 10). Lo mataría una versión con `n_lineas=1` que debe regir.
- **:104 `date(mes.year, mes.month, 1)` → `day=2` · equivalente.**
  `_mes_siguiente` solo lee `year` y `month`: el día 2 da el mismo límite.

Arreglar los dos huecos (:88 y :97) son dos tests de dominio de una línea; se
deja a decisión del líder y el humano.

## Limpieza verificada

`python -m harness.mutacion --estado` → «Sin campaña de mutación en curso»;
`git status` y `git diff` vacíos en `feature/F-161-versiones-sin-reparto`;
ningún worktree `mutacion_F-161_*` ni temporal de reclasificación.
