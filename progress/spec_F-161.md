<!-- progress/spec_F-161.md -->
# spec-author · F-161 · Versiones del máster sin reparto temporal

- Fecha: 2026-11-13. Rama `feature/F-161-versiones-sin-reparto`, desde `main` (`491fbf1`).
- Spec: `specs/F-161-versiones-sin-reparto/` (requirements 122 líneas, design 250, tasks 14 tareas).
- Estado: `pending` → `todo` → `spec_ready`. Este repositorio lleva el arnés 1.7.7, y su `init.sh`
  no admite `todo` (`harness/init.sh:180`). Por eso `todo` queda anotado en `notes` y el fichero
  pasa directamente a `spec_ready`.
- Pendiente: la PARADA 1, con las decisiones D5-D14 de `design.md` §10.

## Decisiones del humano que la spec toma como dadas

Son D1, D3 y D4, anotadas en `notes` de F-161 el 2026-11-11. D2 está revocada y la sustituye D4.
Por eso la spec NO plantea como abierta la combinación de las dos vigencias, aunque el encargo lo
pedía: ya la decidió el humano. Se queda así:

- la temporal no cambia;
- lo nuevo es aditivo;
- el último cierre y su diferencia se publican al lado, sin reescalar.

Si el líder quiere reabrirlo, tiene que hacerlo de forma explícita en la PARADA 1.

## Cómo se midió

- MCP `bbdd-ruesma-azure`, solo lectura, el 2026-11-13 entre las 00:05 y las 00:20 UTC.
  - Esa franja coincide con la ingesta de la nocturna: `ingest_raw.obrparpre` estaba RUNNING desde
    las 00:02:44.
  - `stg` y `mart` eran los del 2026-11-12: lote de stg `20261112T092908Z-8a4f1c` y de mart
    `20261112T102833Z-4a4b97`.
  - Cuatro consultas tardaron entre 20 y 30 s (los barridos de `stg.presupuesto` por lotes de
    obras). Las demás, milisegundos.
- **`raw` no es accesible desde el MCP** (lo dice `contexto_bbdd`).
  - El intento de leer el `.env` del checkout principal para usar `filas_solo_lectura` lo denegó
    el clasificador de permisos, y no se ha forzado.
  - Lo que solo está en `raw` (`planif`, `plafec`, el texto y la fecha de las cabeceras sin reparto)
    se toma del diagnóstico del 2026-11-10 y se vuelve a medir en T7.

## Cifras (las que cita el design, con su consulta)

1. **El catálogo de hoy** (`mart.master_versiones_tipadas`).
   - 2.270 filas de coste y 2.264 de venta, en 133 obras.
   - 0 claves `(obra, ámbito, versión)` repetidas y 0 `version_fec_creacion` nulas.
   - 562 filas temporales en cada ámbito.
   - Versión 0: 8 filas. Son las obras 1286520 (0578), 1338614 (fuera de `stg.obras`), 1612629
     (0613) y 1664456 (0578-B), en los dos ámbitos. Todas son 'Sin clasificar' o 'Cierre mensual'.
2. **Versiones con líneas frente al catálogo.** El universo es `stg.obras` con `LATERAL` sobre
   `stg.presupuesto`, por índice `(obra_id, ambito_id)`, en cuatro lotes de `obra_id` (496412-1063125,
   1063830-1907366, 1907664-2300590 y 2301858-2872024), cruzado con el catálogo.

   | Ámbito | Versión | En catálogo | Versiones | Líneas | Importe (€) |
   |---|---|---|---|---|---|
   | 8 | >= 1 | sí | 2.262 | 2.162.832 | 17.809.778.794,00 |
   | 8 | >= 1 | no | 722 (168 obras) | 537.199 | 2.917.069.840,42 |
   | 8 | 0 | sí / no | 3 / 219 | | |
   | 11 | >= 1 | sí | 2.256 | 1.967.501 | 17.286.691.352,87 |
   | 11 | >= 1 | no | 726 (164 obras) | 488.231 | 2.928.911.323,70 |
   | 11 | 0 | sí / no | 3 / 214 | | |

   - El catálogo tiene 5 filas por ámbito de obras que no están en `stg.obras`: son restos de
     `stg.plan_mensual`.
3. **Por obra** (última versión >= 1 con líneas, comparada con el catálogo y con
   `mart.master_vigente_anual` de 2026).

   | | Coste (8) | Venta (11) |
   |---|---|---|
   | Sin ninguna versión en el catálogo | 58 (5 en el último lote) | 54 (5) |
   | La última no está en el catálogo | 8 (4) | 3 (2) |
   | La última está en el catálogo | 121 | 126 |
   | Con temporal 2026 distinta de la última | 22 + 3 | 24 + 1 |

   - Lista del último lote (la más reciente): 0685 (v12, catálogo hasta v9), 0698 (v24 / v23), 0705
     (v18 / v16), 0722 (v8 / v6, en los dos ámbitos), y 0714, 0718, 0721, 0725 y 0727, sin ninguna
     versión en el catálogo.
4. **Importes por versión.**
   - 0698, coste:
     - v20: 785 líneas, 2.165.726,69 €.
     - v23: 803 líneas, 2.112.027,78 €; con mes, 690 líneas y 2.055.968,14 €.
     - v24: 776 líneas, 2.107.662,97 €; con mes, 0.
   - 0698, venta v24: 688 líneas, 1.808.375,61 €; con mes, 642 líneas y 1.767.231,51 €.
   - 0705, coste: v16 (Cuatrimestral), 3.026.987,39 €; v18, 2.882.351,55 €.
   - 0722, coste: v3 (Cuatrimestral), 1.094.131,22 €; v8, 1.073.686,01 €.
   - 0721, coste: v1, 850 líneas y 13.523.755,74 €; es la única versión de la obra.
   - 0685, coste: v10 a v12 fuera del catálogo; v12 tiene 3.036.955,03 €.
   - «Con mes» quiere decir que el `presupuesto_id` de la línea existe en `stg.plan_mensual`, por
     índice `idx_plan_mensual_presupuesto`. La consulta tarda 210 ms.
5. **Tamaños.**
   - `stg.presupuesto`: 2.448 MB de heap y 4.810 MB en total.
   - `stg.plan_mensual`: 8.564 MB de heap y 12 GB en total.
   - `mart.master_versiones_tipadas`: 512 kB.
   - `mart.fact_seguimiento_mensual`: 2.533 MB.
6. **Tiempos** (`_meta.etl_runs`, SUCCESS en los últimos 8 días, 9 noches).
   - `build_stg`: 5.024 s de media y 9.919 s de máximo.
   - `build_mart`: 5.033 s de media y 5.458 s de máximo.
   - `build_presupuesto`: 540 s de media.
   - `build_plan_mensual_fase0`: 88 s de media.
   - `build_retenciones`: 217 s de media.
   - `build_tesoreria`: 546 s de media.
   - Los sub-pasos de `build_mart` no dejan fila propia, así que el coste del catálogo de hoy no
     está medido (T3).

## Hallazgos fuera del alcance (para el líder)

- **La ficha de `stg.plan_mensual` dice que no hay filas de la fase 0, y no es así.** Hay 4 obras
  con versión 0 de los ámbitos 8 y 11 en el catálogo, deducido de `plan_mensual`. Puede que se solapen
  con `stg.plan_mensual_fase0` (F-157). La ficha se corrige en F-161 (R20), pero el posible solape
  no está medido.
- **El catálogo arrastra la obra 1338614**, que no está en `stg.obras` y sigue con filas en
  `plan_mensual`. Es de la misma familia que la 1562946 del diagnóstico.
- **Dentro de una versión con reparto hay líneas con `planif` que no dejan ningún mes.** En la v23
  de la 0698 son 61. D7 las cuenta como líneas sin reparto.
