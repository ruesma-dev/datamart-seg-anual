# F-157 · La planificación en el tiempo de la fase 0 (Previsto) de coste y venta

Petición de Juan Romero (Control de Costes, 2026-11-05): el datamart publica el total de cada
partida en fase 0 de coste (ámbito 3) y venta (ámbito 7), pero no su reparto mensual, el de la
pantalla de Sigrid «Planificación en el tiempo (por partidas)». Mediciones del 2026-11-05 en
solo lectura: `progress/spec_F-157.md` (§ n citados). Diseño: `design.md`.

Vocabulario: **fase 0** = el «Previsto», la foto VIVA que el jefe de obra evoluciona sin
historia (no es master ni cierre). **`planif`** = texto de `raw.obrparpre` con el % ACUMULADO
de cada mes separado por `|`; **`plafec`** = `raw.obrfasamb.plafec`, el mes 1 del reparto.

## Decisiones para la PARADA 1 (recomendada en negrita; razones en design § 9)

- **D1 · Dónde.** **A: tabla propia `stg.plan_mensual_fase0`**, sin columna `version`. B:
  filas `version = 0` en `stg.plan_mensual` (descartada: `mart` publicaría la planificación
  como «Coste/Venta Real», § 7 de las mediciones).
- **D2 · La regla de explosión, una sola vez.** **A: función `stg.fn_explotar_planif(text)`
  que usa SOLO el fichero nuevo**, con su equivalencia contra el master comprobada (R8, R22);
  `08_plan_mensual.sql` no se toca. B: copiar las CTE del master. C: pasar también el master a
  la función (toca masters: fuera de lo pedido).
- **D3 · Partidas sin reparto.** **A: vista `stg.v_plan_mensual_fase0_cobertura`** por obra y
  ámbito (total fase 0 frente a lo planificado). B: solo un aviso en la ficha.
- **D4 · Redondeo.** **A: el del master** (cada mes redondeado; en la 0726, 34 de 83 partidas
  descuadran ≤ 0,03 €, § 5). B: `importe_mes` = diferencia de acumulados redondeados (cuadra
  al céntimo, pero ya no casa con el master al compararlos).
- **D5 · Primera carga.** **A: el fichero nuevo entra en el sello y se despliega en SÁBADO**:
  la primera noche es la completa del domingo, sin coste extra. B: otro día (+~100 min esa
  noche: 143 frente a 42 min, § 6).
- **D6 · Ámbitos.** **A: solo 3 y 7** (lo pedido). B: también 5 (certificación, 11 obras) y
  12/13 (3 obras): misma mecánica, se añadirían a la lista del filtro.
- **D7 · Regla dura.** **A: ninguna nueva**: la ficha lo dice y la tabla entra en el `ambito`
  de `R-IMPORTE-MES`. B: regla `R-PLANIF-FASE0` (gasta presupuesto de F-147).
- **D8 · `mart`.** **A: no se toca**: la comparación con el master vigente se hace por SQL
  contra `mart.fact_seguimiento_mensual` (ejemplo en la ficha). B: escenarios nuevos en `mart`
  (otra feature: toca Power BI).

## A · El objeto `stg.plan_mensual_fase0` (D1 = A)

- **R1.** El sistema debe crear `stg.plan_mensual_fase0` con `presupuesto_id`, `obra_id`,
  `partida_id`, `ambito_id`, `mes_inicio` (DATE), `anio_mes`, `posicion_mes`,
  `pct_acumulado`, `pct_mes`, `precio_unitario`, `can_mes`, `can_origen`, `importe_mes`,
  `importe_origen`, `importe_mes_raw`, `importe_origen_raw`, `importe_partida` y
  `_built_at`, con los tipos de sus homónimas de `stg.plan_mensual` y clave primaria
  `(obra_id, ambito_id, partida_id, anio_mes)`.
- **R2.** El sistema debe publicar en ella SOLO filas de `stg.presupuesto` con `ambito_id IN
  (3, 7)` y `fase_num = 0` cuyo `raw.obrparpre.planif` no esté vacío y cuya obra tenga
  `raw.obrfasamb.plafec > 0` en `(obra, ámbito, fas = 0)`.
- **R3.** SI una `(obra, ámbito, fas = 0)` tiene dos filas en `raw.obrfasamb`, ENTONCES el
  sistema debe usar la de `ide` mayor y no duplicar ninguna fila (hoy no hay ninguna, § 2).
- **R4.** El sistema debe calcular `anio_mes` como el primer día del mes de `plafec` más
  `posicion_mes − 1` meses, y `mes_inicio` como ese primer mes.
- **R5.** El sistema debe calcular `pct_acumulado` y `pct_mes` con la regla del master de
  `08_plan_mensual.sql`: positivo literal; 0 con un positivo después = 0 (estorno); 0 final
  tras un positivo = el último positivo; 0 sin positivo antes = 0; `pct_mes` = diferencia con
  la posición anterior; una posición no numérica cuenta como 0.
- **R6.** El sistema debe descartar, como el master, las filas con `pct_acumulado = 0` y
  `pct_mes = 0` y las de `pct_acumulado > 2,5`.
- **R7.** El sistema debe calcular `importe_mes`, `importe_origen`, `importe_mes_raw`,
  `importe_origen_raw`, `can_mes` y `can_origen` con las fórmulas de la rama master (D4 = A), e
  `importe_partida` = `stg.presupuesto.importe`.
- **R8.** El sistema debe exponer la regla de R5 como `stg.fn_explotar_planif(text)` →
  `(posicion_mes, pct_acumulado, pct_mes)`, sin ventanas que crucen partidas, y un oráculo
  Python `etl_sigrid/domain/planif.py::explotar_planif` que la repita posición a posición.
- **R9.** El oráculo debe dar lo documentado en `08_plan_mensual.sql`: 0696 P5.19.04.01 (0
  intermedio → estorno), 0677 40.04.04 (`…|0.93|0|0` → se queda en 0,93), P4.03.06
  (sobrepaso: arrastra el último positivo, no el máximo), y la 0726 `0|0|0|0|0.15|0.85|1` y
  `0.3439|1`; con posiciones vacías al final fuera del horizonte.
- **R10.** Una partida sin `planif`, con `planif` todo a cero o en una obra sin `plafec` NO
  debe tener ninguna fila: el sistema no inventa reparto.
- **R11.** (D3 = A) El sistema debe crear `stg.v_plan_mensual_fase0_cobertura`, una fila por
  `(obra_id, ambito_id)` con fase 0 en 3 o 7: `mes_inicio`, `partidas`, `partidas_planificadas`,
  `importe_fase0` (Σ `stg.presupuesto.importe`), `importe_planificado` (Σ `importe_partida` de
  las planificadas) e `importe_sin_planificar` (la diferencia).

## B · El build

- **R12.** El sistema debe construirla con `sql/stg/09_plan_mensual_fase0.sql`, en un sub-paso
  `build_plan_mensual_fase0` de `build_stg` que va DESPUÉS de `build_plan_mensual`, para las
  mismas obras del plan de la noche (F-025) y de una sola pasada.
- **R13.** El sub-paso debe borrar exactamente las obras que reinserta, en la misma
  transacción que el `INSERT` (borrado derivado de F-025), con un marcador
  `/*F157_FILTRO_OBRAS*/` que aparece UNA vez; SI no aparece exactamente una vez, ENTONCES no
  debe ejecutar nada y debe fallar con un mensaje que lo diga.
- **R14.** CUANDO el plan de la noche no tiene obras, el sub-paso no debe tocar la tabla.
- **R15.** Antes de escribir, el sub-paso debe pasar la puerta de disco de F-019; SI la
  ocupación supera el límite o no se puede medir, ENTONCES debe parar en FAILED sin borrar nada.
- **R16.** `09_plan_mensual_fase0.sql` debe entrar en `FICHEROS_DEL_SELLO` (tras el 08) y
  `plan_mensual_fase0` en `TABLAS_ACOTADAS`.
- **R17.** El sub-paso debe dejar su fila en `_meta.etl_runs` con las filas de la tabla, como
  los demás.

## C · Sin regresión

- **R18.** `sql/stg/08_plan_mensual.sql` y los SQL de `mart/`, `cierre/`, `tesoreria/`,
  `retenciones/` y `maestro/` no deben cambiar respecto a `main` (`fbf43dd`).
- **R19.** Ningún SQL fuera de `sql/stg/` debe leer `plan_mensual_fase0`: lo vigila un test.
- **R20.** (MANUAL) La huella `huella-obras --desde plan_obra` de antes y después de la
  primera noche debe coincidir en todas las obras congeladas; una diferencia en una viva se
  explica por su ingesta de esa noche.
- **R21.** (MANUAL) `check-cierres`, `check-unicidad` y `check-declarados` deben dar OK tras
  la primera noche.
- **R22.** (MANUAL) `stg.fn_explotar_planif` aplicada a los `planif` master de 0696, 0677 y
  0705 debe dar los mismos `pct_acumulado` y `pct_mes` que sus filas de `stg.plan_mensual`
  (0 diferencias).

## D · Diccionario

- **R23.** `config/diccionario/stg.yaml` debe tener ficha de la tabla y de la vista, que digan:
  que es planificación VIVA del jefe de obra (la de hoy, no master ni cierre, sin historia);
  que solo están las partidas planificadas y el total está en la vista; que no se suma con
  `stg.plan_mensual`; que el total de una partida es `importe_origen` de su último mes (el
  redondeo por meses descuadra céntimos); de cuándo es el dato (`_meta.v_frescura_obra`); y dos
  ejemplos de pregunta: el reparto de la venta de una obra y su comparación con el master
  vigente o con el coste.
- **R24.** La ficha de `stg.plan_mensual` debe dejar de decir que guarda `fas = 0` y apuntar a
  la tabla nueva; `R-IMPORTE-MES` debe incluirla en su `ambito`; `00_global.yaml` sube de
  versión; los tests de presupuesto (F-147) y de reglas no publicadas (F-149), en verde.

## E · Aceptación con datos (MANUAL, tras la primera noche)

- **R25.** La 0726 (obra_id 2817778) debe publicar en venta 83 partidas, 312 filas, de
  2026-10-01 a 2028-07-01, `pct_acumulado` final 1 en las 83, Σ `importe_mes` = 9.666.069,95 €
  (≤ 0,03 € por partida frente a `importe_partida`, 9.666.069,97 € en total) y ninguna de
  coste; su fila de cobertura de venta: 1.460 partidas, 83 planificadas, 23.928.969,90 €.
- **R26.** El total debe rondar 1,25 M de filas (593.251 coste y 661.451 venta el 2026-11-05) en
  140 obras, y la noche entre semana crecer como mucho ~5 min.

## F · Documentación

- **R27.** `docs/ARCHITECTURE.md` (semántica de la fase 0), el mapa de `CLAUDE.md` y
  `../azure-apps/datamart_seg_anual.md` (objeto nuevo, ~0,45 GB, minutos por noche) deben
  quedar al día en el mismo trabajo.
