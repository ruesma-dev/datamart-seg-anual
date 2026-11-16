# F-157 · Mediciones del spec-author (2026-11-05, solo lectura)

Todo leído contra Azure (`sigrid_dm`) con `pg._bootstrap_done = True` y
`pg.filas_solo_lectura`, entre las 11:22 y las 13:40 UTC, desde la raíz del worktree de la
rama `feature/F-157-planificacion-fase0` (nace de `main` `fbf43dd`). Ni una escritura. No ha
hecho falta `sigrid-api`: `raw.obrfasamb` y `raw.obrparpre` se ingieren con todas sus columnas
(`exclude_columns: []`). Las consultas se guardaron fuera del repositorio (scratchpad).

## 1. Tamaños y tipos

| Objeto | Filas vivas (`pg_stat`) | Nota |
|---|---|---|
| `raw.obrparpre` | 14.069.515 | solo índice por `ide`: filtrar por obra o ámbito es barrido (~70-115 s) |
| `raw.obrfasamb` | 28.892 | solo índice por `ide` |
| `stg.presupuesto` | 14.191.851 | índices por `(obra_id, ambito_id, …)` |
| `stg.plan_mensual` | 32.805.456 | 11,94 GB con índices |

Disco del servidor: 36,55 GB de 64 (57 %). `raw.obrfasamb.planif` es ENTERO (el número de
periodos, «Planificación temporal, periodo»); `raw.obrparpre.planif` es TEXTO (el acumulado
por meses separado por `|`).

## 2. `obrfasamb` con `plafec` por ámbito (fase 0 frente al resto)

| Ámbito | Fase 0: obras con `plafec` | Fases ≥ 1: filas (obras) con `plafec` |
|---|---|---|
| 2 ESTUDIO | 0 de 436 | 0 |
| 3 COSTE | **144** de 534 | 20 (16) |
| 5 CERTIFICACION | 13 de 354 | 2 (2) |
| 7 VENTA | **139** de 377 | 16 (11) |
| 8 MASTER COSTE | 6 | 2.283 (131) |
| 9 MASTER CERTIFICACION | 0 de 233 | 200 (10) |
| 11 MASTER VENTA | 5 | 2.269 (131) |
| 12 ESTUDIO JEFE OBRA | 1 | 0 |
| 13 CERTIFICACIÓN PEC | 2 | 2 (2) |

`plafec` de la fase 0: coste de 2015-05-08 a 2026-08-03; venta de 2016-05-01 a 2026-10-01. De
las 138 obras con `plafec` en coste y venta fase 0, **136 comparten el mismo `plafec`**. No hay
filas duplicadas de `obrfasamb` en `(obride, amb, 0)` hoy (el caso de
`docs/referencia/05_caso_obrfasamb_version_duplicada.md` pasó en master).
Banderas `placap`/`plapar`/`plamed`: en fase 0, `plamed = 2` en 23 obras de coste y 18 de venta;
las obras con que se validó la regla del master (0696, 0677, 0705) tienen todas `plamed = 0`.

## 3. Partidas fase 0 con `planif` (ámbitos 3, 5, 7, 12, 13)

Fuera de las obras con `plafec` en fase 0 **no hay ni una partida con `planif`** en 2, 3, 5, 7,
9 y 13 (en 12, una obra con 1.214). Dentro (importes `can × pre`, sin redondear):

| Ámb. | Partidas | Con `planif` no vacío | Con algún positivo | Importe total | Importe con positivo |
|---|---|---|---|---|---|
| 3 | 114.828 (144 obras) | 89.591 (128 obras) | 76.027 | 815.806.371,70 | 705.554.133,77 |
| 7 | 113.175 (139 obras) | 102.185 (137 obras) | 87.965 | 823.026.099,95 | 772.111.029,29 |
| 5 | 9.500 (13) | 7.581 (11) | 6.932 | 89.070.359,65 | — |
| 12 / 13 | 703 / 1.668 | 703 / 1.620 | — | 3,7 M / 20,6 M | — |

**Sin reparto** (sin `planif` o todo a cero) en las obras con `plafec`: coste 38.801 partidas,
~110,25 M€ (13,5 %); venta 25.210 partidas, ~50,92 M€ (6,2 %).

## 4. ¿El acumulado termina en 1? (ámbitos 3 y 7, obras con `plafec`)

Con la regla del master (0 FINAL tras un positivo = se arrastra el último positivo):

| Cubo del % final efectivo | Coste: partidas (obras) · importe | Venta: partidas (obras) · importe |
|---|---|---|
| Todo a cero (no se publica) | 13.564 (103) · 2,10 M | 14.220 (120) · 2,36 M |
| **= 1** | **74.935 (128) · 686,04 M** | **87.264 (136) · 766,53 M** |
| < 1 | 130 (20) · 1,83 M | 409 (33) · 2,96 M |
| en (1; 2,5] | 959 (59) · 17,68 M | 291 (38) · 2,62 M |
| > 2,5 (lo quita la cordura del master) | 3 (2) · 5.849 € | 1 (1) · 0 € |

Lectura literal del texto: solo 20.931 (coste) y 21.882 (venta) acaban en `1`; la mayoría
acaba en `0` tras llegar a 1 (`…|1|0|0`, 50.875 y 64.989): es el «0 final» que el master ya
arrastra. Con «0 intermedio» (estorno): 865 coste, 1.053 venta. Posiciones no numéricas: 0.
Negativos: 19 y 16. Partidas con alguna posición > 2,5 aunque acaben en 1: 312 y 57 (la cordura
del master quita esa FILA, no la partida). Hay partidas con más posiciones que
`obrfasamb.planif` (periodos): el master no recorta por ahí y aquí tampoco.

## 5. La obra 0726 (obra_id 2817778)

- `obrfasamb` fase 0: coste `plafec` 0, venta `plafec` 20261001 con `planif` (periodos) = **22**;
  master 0 y 1 (8/11) sin `plafec`.
- Venta fase 0: 1.460 partidas, **83 con `planif`** (todas con positivo), 9.666.069,97 € de
  23.928.969,90 €. Coste fase 0: 1.545 partidas, 0 con `planif`.
- Ejemplos: `02.03` `0|0|0|0|0.15|0.85|1`; `02.01` `0.3439|1`; `03.02` 21 ceros y `1`.
- `stg.plan_mensual` de la obra: solo ámbito 3 versión 1 (31 filas, 2026-10-01).
- Simulación SELECT de la regla del master sobre la fase 0 (sin escribir): **312 filas**, de
  **2026-10-01 a 2028-07-01** (22 meses, igual que los periodos), % final 1 en las 83; Σ
  `importe_mes` = 9.666.069,95 € frente a 9.666.069,97 €: **34 partidas descuadran por el
  redondeo de cada mes, como mucho 0,03 €** (es la misma aritmética del master, que se validó
  contra Sigrid con diferencias de −0,03 a +0,01 € por mes).

## 6. Coste de construirlo

Simulación SELECT completa (todas las obras, ámbitos 3 y 7): **103,5 s, 1.254.702 filas**
(593.251 coste, 661.451 venta), 163.987 partidas, 140 obras, meses de 2016-05 a 2028-07.
A ~370 B por fila (lo de `plan_mensual`): ~0,45 GB con índices. De las 145 obras con `plafec`
en fase 0, **41 son vivas y 104 congeladas** (`_meta.v_frescura_obra`).

`build_stg.build_plan_mensual` en `_meta.etl_runs`, últimos 9 días: **40,5-44,5 min** entre
semana y **142,9 min el domingo 2026-11-01** (la reconstrucción completa). Cambiar el sello del
SQL fuerza una noche completa: ~+100 min si no cae en domingo.

## 7. Quién lee `stg.plan_mensual` por ámbito real (por qué NO va ahí con versión 0)

- `mart/02_build_fact.sql` publica **todas** las filas de `ambito_id = 3` como «Coste Real» y
  las de `= 7` como «Venta Real», **sin filtrar `version`**.
- `mart/06_cp_tipologia.sql` y `cp_tipologia_sql.py`: «último mes con coste real» = `MAX(anio_mes)`
  de `ambito_id = 3`; la planificación lo llevaría a 2028.
- `check-cierres` (R21 de F-118): Σ `importe_mes` de cada partida real = acumulado del último cierre.
- `huella_obras.py`, `mes_fase_sql.py` (`ambito_id IN (3, 7)`), `retenciones/05_fin_obra.sql`.
- `cierre/` sí filtra `pm.version >= 1` (02_build_fact 82-115, 04_views_detalle 149 y 510).

## 8. La pantalla de Sigrid

Ni `docs/referencia/` ni `azure-apps/` describen «Planificación en el tiempo (por partidas)».
Lo único: `sigrid_tablas.md` define `obrfasamb.planif` (periodo), `plafec` (fecha ini),
`placap`/`plapar`/`plamed` (capítulos, parciales, mediciones) y `obrparpre.planif` (texto). El
cuadre con la pantalla queda como verificación MANUAL de Control de Costes (design § 11).

## 9. Fuera de alcance, medido de paso

Hay `planif` con positivo en cierres reales (fases ≥ 1): 8.202 partidas de coste y 7.195 de
venta en las obras con `plafec` en esas fases. Los cierres no usan `planif` y F-157 no los toca.
