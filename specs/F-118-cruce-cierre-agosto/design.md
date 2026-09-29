<!-- specs/F-118-cruce-cierre-agosto/design.md -->
# F-118 · Diseño · Una sola construcción de la serie real, y la venta final en la base del ejecutado

Cifras, listas y consultas: `progress/spec_F-118.md`. Lo heredado de F-051 se
enlaza a `specs/F-051-nombre-mes-real/design.md` (§n) en vez de copiarse.

## 1 · Encaje: qué es la misma causa y qué no (con el dato delante)

**F-051 y el fallo 1 no son la misma causa, pero viven en el mismo sitio y se
arreglan con el mismo cambio.** F-051 es **en qué mes** cae un cierre real (el
`ano`/`mes` de `obrfas` en vez del texto). El fallo 1 es **cómo se calcula el
movimiento**: la 0709 no tiene ningún problema de mes (f11 «Julio 2026», f12
«Agosto 2026», f13 «Septiembre 2026», con sus fechas), así que F-051 sola no la
arregla. Lo que comparten es la raíz: la rama de reales de
`stg/08_plan_mensual.sql` construye la serie **fila a fila con lo que Sigrid
guarda**, sin esqueleto de meses, y calcula `importe_mes` con un `LAG` que solo
resta si la fila anterior de la partida es de la fase inmediatamente anterior
(`:430-448`); si no, publica el acumulado entero.

- **0709, partida 417031, venta:** f11 −58.000, **sin fila en f12**, f13 a 0. En
  agosto no hay fila que deshaga; en f13 el `LAG` no es consecutivo y publica el
  acumulado (0) en vez de +58.000. Agosto sale 319.492,30 € donde el cierre da
  377.492,30 € (remedido: coincide con Juan al céntimo).
- **Por qué `cierre` acierta:** no resta por partida. Suma acumulados por
  (obra, mes, concepto) y resta meses (`cierre/02_build_fact.sql:75-131, :353`):
  la partida ausente simplemente no suma, y la diferencia recoge el +58.000.
- **Por qué nadie lo vio:** el telescopio de `check-cierres`
  (`cierres_sql.py:237-247`) **aparta** las series con hueco y compara con la
  última fila de la partida, no con el último cierre de la obra.

**F-103 sí es la misma causa** que el fallo 1: el mismo `CASE` publica el
acumulado entero cuando falta un número de fase en Sigrid. Medido: fuera de las
fases descartadas por F-042 (que `orden_fase` ya repara), **todas** las series
rotas de `stg.plan_mensual` caen en tres grupos, y los tres los arregla la
serie densa sin una línea específica: **fallo 1** (32 obras de `stg.obras`),
**F-103** (0371, 0404, 0455, 0562, 0606) y **venta sin cierre del ámbito** (11
obras, D3). Ninguna obra con la serie bien cambia (R23): el temor de F-042 a
«mover obras que hoy están bien» no se cumple en el dato. D2 decide la unión.

**El arreglo único:** la rama de reales pasa a construir una **serie densa** por
(obra, ámbito, partida) sobre un esqueleto de meses —los cierres vigentes del
ámbito en el mes del texto (F-051 R7–R8) más los meses de relleno (F-051
R10–R14)—, rellena cada hueco según su tipo (cierre ausente → 0, R29; relleno →
arrastre, R33) y calcula `importe_mes` como diferencia con el mes anterior **de
la serie**, que ya no puede tener huecos (R9). Es lo que hace `cierre`, a grano
de partida.

**El fallo 2 es otro mecanismo** (qué columna suma el cierre para la venta
final) y otro fichero; va en su bloque de tareas, desacoplado (D8).

Límite de microservicio: todo es del datamart. No toca Sigrid, `sigrid-api`,
ni el documento de `azure-apps/` (no cambia nada expuesto ni consumido).

## 2 · Ficheros a modificar

| Fichero | Cambio |
|---|---|
| `sql/stg/00_functions.sql` | Las dos funciones de F-051 (§4 de su diseño), sin cambios. |
| `sql/stg/01_ddl.sql` | `es_relleno` (F-051) y `es_deshacer BOOLEAN NULL` en `stg.plan_mensual`, en el bloque `DO` idempotente. |
| `sql/stg/08_plan_mensual.sql` | Rama de reales: §5. Rama master: **ni una línea**. Cabecera: sección F-118 que sustituye la explicación del `LAG` por `orden_fase` y dice qué es deshacer. |
| `sql/mart/01_ddl.sql`, `02_build_fact.sql`, `05_views_powerbi.sql` | Lo de F-051 (§2 de su diseño) más `es_deshacer` en ramas 1–2 (`pm.es_deshacer`) y `NULL::BOOLEAN` en 3–4; `v_pbi_fact` la publica. |
| `sql/cierre/00_setup.sql`, `01_ddl_fact.sql`, `04_views_detalle.sql`, `06_views_planif_vs_real.sql` | Lo de F-051 (§2 y §6 de su diseño), sin cambios. |
| `sql/cierre/02_build_fact.sql` | Lo de F-051 (CTE A/B leen `pm.anio_mes`) **más** §6 de este diseño (R38 y fallo 2). |
| `application/steps/build_stg_step.py` | `FICHEROS_DEL_SELLO` += `00_functions.sql` (F-051 R28). |
| `infrastructure/postgres/huella_obras.py` | `sql_huella_propuesta` lee `reales_final` (`importe_mes`, `importe_origen` ya redondeados). |
| `infrastructure/postgres/cierres_sql.py` | `sql_telescopio` y `_detalle`: R37 (§7). |
| `domain/cierres.py` | `hay_hueco_de_origen` y `orden_de_los_publicados` dejan de decidir el telescopio; se conservan si `check-cierres` las usa para otra cosa, si no se retiran con sus tests. |
| `main.py` | `check-mes-fase` (F-051 §8) y `check-cierres` con el telescopio nuevo. |
| `config/diccionario/{stg,mart,cierre,00_global}.yaml` | §8. |
| `docs/ARCHITECTURE.md` | Viñetas «el mes de un cierre real» (F-051) y «la serie real es densa» (F-118). |
| `tests/test_f042_sql.py`, `test_f042_huella.py`, `test_f042_check_cierres.py`, `test_f019_t13_portabilidad.py`, `test_f078_sql.py`, `test_f006_*` | Los que fijan `orden_fase`/`reales_con_lag` se reescriben contra la estructura nueva y su motivo se cita en el informe: fijaban el defecto. |

## 3 · Ficheros a crear

- `etl_sigrid/domain/mes_fase.py` — oráculo de F-051 (§3 de su diseño).
- `etl_sigrid/domain/serie_real.py` — oráculo puro de la serie densa:
  `serie_densa(cierres: Sequence[CierreDePartida], meses_relleno: Sequence[date])
  -> list[FilaSerie]` con `FilaSerie(mes, acumulado, movimiento, es_relleno,
  es_deshacer)`. Aplica R9, R29–R34 y D3 de F-051. Es contra lo que se contrasta
  el SQL.
- `etl_sigrid/domain/coeficientes.py` (solo si D6 = B) — `ejecutado_con_coeficientes`.
- `tests/test_f118_regla_mes.py`, `test_f118_serie_densa.py`, `test_f118_invariante.py`
  (semilla fija, sin `hypothesis`), `test_f118_sql.py`, `test_f118_check.py`,
  `test_f118_coeficientes.py`.

## 4 · Las funciones del mes

Exactamente las de F-051 (§4): `stg.fn_parse_mes_texto` y `stg.fn_mes_de_fase`
con la cascada de D5. No hay nada nuevo que decidir.

## 5 · La rama de reales de `08_plan_mensual.sql`

Todo entre `/*F042_INICIO_REALES*/` y `/*F042_FIN_REALES*/`, **un** marcador de
tramo (el de `reales_base`) y toda ventana con `PARTITION BY` encabezado por
`obra_id` (`test_f042_ninguna_ventana_del_fichero_cruza_obras` sigue vigente).

1. `reales_base`: `anio_mes = stg.fn_mes_de_fase(...)`, `mes_ini_fase`, `es_rango`
   (F-051 §5 paso 1).
2. `reales_cierres`, `reales_vigente`: sin cambios (F-042 sobre el mes del texto,
   F-051 R8). `reales_orden` **desaparece**: solo aportaba `vive` y el orden del
   `LAG`; `vive` sale de un `JOIN` con `reales_vigente`.
3. `reales_filas`: las filas de `reales_base` de cierres vigentes, con sus
   acumulados (`importe_origen_round`, `_raw`, `cantidad`, `total_incurrido_raw`).
4. `reales_meses`: por (obra, ámbito), los meses de sus cierres vigentes
   (`tipo = 'CIERRE'`, con su `mes_fase_num` y texto) **unión** los de relleno
   de F-051 §5 pasos 4–5 (`tipo = 'RELLENO'`, fase generadora, nunca en un mes
   ocupado: D1 de F-051). Ámbito a ámbito: una fase sin filas del ámbito no es
   mes de ese ámbito (R34, D3).
5. `reales_alta`: por (obra, ámbito, partida), el primer mes en que tiene fila;
   para las partidas que nacen en una fase de rango, el primer mes de su relleno
   (D3 de F-051: llevan relleno si tienen movimiento en la fase).
6. `reales_esqueleto`: `reales_meses` × partidas de `reales_alta` con
   `mes >= alta`, `LEFT JOIN reales_filas`.
7. `reales_serie`: acumulado por hueco — fila propia → su valor; `CIERRE` sin fila
   → **0** (R29, R30); `RELLENO` → NULL y arrastre del último no nulo con el truco
   de grupos de la rama master (`COUNT(x) OVER` + `MAX() OVER (..., grupo)`), sin
   anterior 0 (R33). Los cuatro acumulados igual.
8. `reales_con_lag`: movimiento = acumulado − `LAG(acumulado) OVER (PARTITION BY
   obra_id, partida_id, ambito_id ORDER BY anio_mes)`, `COALESCE` 0 en el
   primero (R9). Cuatro columnas, **sin** `CASE` de consecutividad.
9. `reales_final`: se conservan (a) las filas de Sigrid (`es_relleno = FALSE`,
   `es_deshacer = FALSE`); (b) las de relleno con acumulado ≠ 0 o con movimiento
   en su fase generadora (D3 de F-051), `es_relleno = TRUE`; (c) las de cierre
   sin fila con movimiento ≠ 0, `es_deshacer = TRUE` (R29, R32). `version` y
   `posicion_mes` = fase del mes (generadora en el relleno); `presupuesto_id`,
   `precio` = los de la última fila de Sigrid anterior de la partida (R31);
   `res_descripcion` = texto de la fase del mes.

El `INSERT` lee `reales_final` y escribe `es_relleno`, `es_deshacer`; la rama
master escribe `NULL::BOOLEAN` en las dos.

**Invariante por construcción (R21):** la serie no tiene huecos y el movimiento
es diferencia de acumulados consecutivos, así que la suma telescopea al último
acumulado de la serie, que es el del último cierre del ámbito (0 si la partida
salió). Las filas (b) y (c) descartadas tienen movimiento 0: no lo rompen.

**Por qué `anio_mes` y no `orden_fase`:** tras F-051 el mes del texto es único por
(obra, ámbito) (R8) y los meses de relleno no chocan con cierres (D1). Medido: 2
inversiones fase/mes en todo el histórico, ambas anteriores a 2020
(`check-mes-fase` las lista para Juan).

## 6 · `cierre/02_build_fact.sql`

- **F-051**: CTE A/B leen `pm.anio_mes` y `bool_and(pm.es_relleno)` (su §2).
- **R38 (si D5 = arrastrar)**: en `combinado`, `ejecutado_origen` de un concepto
  sin filas ese mes = el del último mes con filas (ventana por obra y concepto),
  no `COALESCE(..., 0)`. Hoy 22 obras de venta (≤ 2020) publican un mes con la
  venta a origen a 0 y su rebote.
- **Fallo 2 (D6)**. Opción A: `final_master` VENTA y `final_fase0` VENTA suman
  `pres.importe` (hoy `importe_oficial`), y la cabecera de la sección cambia de
  «Tanda 1.7» a F-118 con el motivo. Opción B: `ejecutado_concepto` VENTA
  multiplica `pm.importe_origen` por `importe_oficial/importe` de la partida en
  la versión master de ese mes (`master_vigente_por_mes`, 1 si no está); la
  venta final no cambia. En las dos, `final_fase0` es inocua hoy (amb 7 nunca
  lleva coeficientes) pero se alinea para que no diverja mañana.
- Nada más: `v_pbi_cierre_cabecera`, `v_pbi_cierre_resumen` y
  `v_pbi_cierre_indirectos_detalle` leen `final_importe` y heredan (R42).

## 7 · `check-cierres`: el telescopio sin apartados (R37)

`sql_telescopio`: la serie de cada partida se compara con el acumulado en el
**último mes publicado del ámbito de la obra** (0 si la partida no tiene fila
ese mes), sin la columna `con_hueco`. Devuelve `series_comprobadas` y
`series_rotas`; `series_con_hueco` desaparece de la salida y del comando. Tras
el build: **0 rotas** sobre todas las series reales.

## 8 · Diccionario

Lo de F-051 (§7 de su diseño) más: `stg.plan_mensual.importe_mes` (diferencia
con el mes anterior de la serie de la partida; una partida que sale de un cierre
se deshace en ese mes), `es_deshacer` en `stg`, `mart.fact_seguimiento_mensual`
y `v_pbi_fact`; `cierre.fact_cierre_mensual.final_importe` y la cabecera (base
de la venta final según D6); la regla global de `00_global.yaml` que hoy dice
«`importe_oficial` para venta» (`:1550`) y `stg.presupuesto.importe_oficial`
(`stg.yaml:361, :406`), que deja de ser «lo que usa el cierre» si D6 = A. Ninguna
ficha nueva ni modificada dice «estorno» (test). Sube `version`. Sin pendientes.

## 9 · Verificación

**Offline** (`bash harness/init.sh`): oráculos de mes y de serie densa con los
casos reales (0709 417031; partida que sale y vuelve; que sale en el último
cierre; relleno tras un deshacer; fase sin filas del ámbito; hueco de F-103);
invariante R21 con series generadas; SQL estructural: sin `orden_fase` ni `CASE`
de consecutividad en la rama, `reales_final` dentro de los marcadores, un solo
marcador de tramo, `es_deshacer` en `stg`/`mart`/`v_pbi_fact`, la columna de la
venta final según D6, `sql_telescopio` sin `con_hueco`; «estorno» ausente de lo
tocado del diccionario.

**Contra la base (MANUAL, humano)**, protocolo de F-042/F-052 sobre el MISMO
`raw`: (1) huellas ANTES `stg`, `mart`, `cierre`; (2) crear solo las funciones de
`stg` (escritura aditiva) y `huella-obras --propuesta`; (3) desplegar y
reconstrucción completa; (4) huellas DESPUÉS y `comparar-huellas` con la lista
esperada (`progress/spec_F-118.md` §6); (5) `check-unicidad`, `check-cierres`
(0 rotas), `check-mes-fase`, testigos; (6) hoja de cierre de agosto (R45, D7).

### Testigos nuevos (los de F-051 están en su §8)

| Caso | Hoy | Después |
|---|---|---|
| 0709 venta ago-26 (`stg`, `mart`) | 319.492,30 | 377.492,30 (= `cierre`); sep-26 0,00 |
| 0709 partida 417031 | suma −58.000 | suma 0; fila `es_deshacer` en ago-26 (+58.000) |
| 0371 coste f29 (D2) | +4.293.905,89 | −441.229,31 (= `cierre`) |
| 0606 coste / venta sep-21 (D9) | 0 / 0 | −9.053.263,61 / −9.188.957,62 (= `cierre`) |
| 0247 venta f10 (D3) | acumulado entero | f10 − f8 |
| 0702 ago-26, D6 = A | venta final 12.144.681,17; benef. +1.695.571,87 | 9.658.390,84; −790.718,46 |
| 0702 ago-26, D6 = B | ejecutado venta 2.910.579,09 | 3.643.832,04; final sin cambio |

## 10 · Riesgos

- **Reconstrucción completa** (`08` y `00_functions.sql` en el sello): 920 obras
  esa noche, con la huella ANTES tomada; créditos de CPU del servidor compartido.
- **Volumen**: relleno ~1,34 M filas (F-051); deshacer, 495 filas. Disco de 64 GB.
- **Rendimiento**: el esqueleto añade un `JOIN` y dos ventanas por tramo; se mide
  el tramo más pesado con `--propuesta` antes de desplegar.
- **Meses cerrados que cambian en Power BI**: los de F-051 (~500 cierres de 255
  obras) más el fallo 1 (desde 2024: 0658, 0660, 0662, 0674, 0696, 0709) y, con
  D6 = A, la venta y el beneficio final de 42 obras (511 filas mes, 2021-2026) y
  el presupuesto vigente de 41 en la cabecera. Aviso a Juan antes, con la lista.
- **F-096** toca la rama master del mismo fichero: primero F-118, F-096 rebasa.
- **Tests de F-042 que fijaban el defecto**: se reescriben, no se borran sin
  sustituto; el reviewer lo comprueba uno a uno.

## 11 · Decisiones abiertas (recomendación; detalle y cifras en `progress/spec_F-118.md` §8)

- **D1** Sustituir F-051 R9 y R21 por la serie densa y el invariante contra el acumulado real. **Sí.**
- **D2** Unir F-103: misma causa, la arregla la serie densa sin código extra. **Sí.**
- **D3** Fase sin filas del ámbito (11 obras de venta, 2010-2020): no es cierre del ámbito. **Sí** (R34).
- **D4** Marcar las filas de deshacer con `es_deshacer`. **Sí.**
- **D5** Arrastrar en `cierre` el concepto sin filas del mes (22 obras, ≤ 2020). **Sí**, en esta feature.
- **D6** Coeficientes, A o B: **lo deciden el humano y Negocio.** Recomendación **A**.
- **D7** Contraste: huellas + hoja de cierre de agosto de Juan, fuera del repositorio. **Sí.**
- **D8** Si D6 no está decidida al acabar el bloque B, el fallo 2 se parte a feature propia. **Sí.**
- **D9** 0606 y las desapariciones masivas (0419, 0465, 0599, 0616, 0658): aplicar la regla y listarlas a Juan. **Sí.**
