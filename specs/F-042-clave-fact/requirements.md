<!-- specs/F-042-clave-fact/requirements.md -->
# F-042 · Requisitos · Un solo cierre por mes en los ámbitos reales

**Decisión de Negocio del 2026-08-28, cerrada:** «el mes no se parte en 2, se
coge el cierre más moderno de ese mes»; «en el acumulado a origen los cierres
que caigan doble en un mes deben ignorar el primero». La clave del datamart
**no crece** y Power BI **no cambia de forma**.

> **SIN CAMPAÑA DE MUTACIÓN.** Decisión del humano del **2026-08-29**: «no me
> hacen falta mutation test». `CHECKPOINTS.md` C4 bis la exige para rigor
> `critico`, así que **el reviewer debe declararla N/A citando esta decisión**
> (C4 bis admite N/A con motivo escrito; sin él es CHANGES_REQUESTED). La
> evidencia que la sustituye es R22–R25. **Fase RED y cobertura siguen
> exigiéndose**: no se tocan.

Línea base: **`progress/explore_F-042.md`**. **Alcance:** solo los ámbitos
**reales** (3 Coste, 7 Venta), donde `fas` es el mes. Los master (8, 11), donde
`fas` es la versión, **no se tocan**.

---

## La regla

**R1.** CUANDO el ETL construye `stg.plan_mensual` para los ámbitos reales, el
sistema debe conservar **un solo cierre** por (`obra_id`, `ambito_id`,
`anio_mes`): el de **mayor `numero_fase`** entre los de ese mes cuyo acumulado a
origen sea **distinto de cero**.

**R2.** SI todos los cierres de un mes tienen el acumulado a cero, ENTONCES debe
conservarse el de mayor `numero_fase`.

**R3.** MIENTRAS un mes tenga un único cierre —todas las obras salvo 22—, el
sistema debe conservarlo sin alterarlo.

**R4.** La regla debe valer para **N cierres en un mes**, no solo para dos: las
24 colisiones de hoy son todas de dos, pero la regla no puede depender de eso.

**R5.** CUANDO se descarta un cierre, el sistema debe **renumerar el orden
interno** de los supervivientes de esa (`obra_id`, `ambito_id`), desplazándolos
hacia abajo tantas posiciones como cierres se hayan descartado antes que ellos,
para que el cálculo de `importe_mes` siga viendo el cierre inmediatamente
anterior.

> `importe_mes` de los reales **no viene de Sigrid**: lo calcula el ETL como
> `importe_origen − LAG(importe_origen)` y **solo** si la fase anterior es la
> consecutiva (`sql/stg/08_plan_mensual.sql:347-362`). Sin renumerar, el
> movimiento de feb-2018 de la 0499 pasaría de **975.249,98 €** a **5.688.073,92 €**.

**R6.** El sistema debe **preservar los huecos de numeración que no cree esta
regla**: si una obra tiene fases ausentes en origen, esa discontinuidad debe
seguir tratándose como hoy (importe del mes = acumulado entero).

**R7.** `stg.plan_mensual.version` debe conservar el **número de fase original
de Sigrid**, sin renumerar, aunque queden huecos.

## Lo que NO puede cambiar

**R8.** El **movimiento del mes** se queda donde está: para cada (`obra_id`,
`partida_id`, `ambito_id`, `anio_mes`), el `importe_mes` del superviviente debe
igualar la **suma** de los `importe_mes` que hoy publican los cierres de ese mes.
Igual para `importe_mes_raw`, `can_mes` y `total_incurrido_mes`.

**R9.** MIENTRAS una obra no tenga dos cierres en el mismo mes, no debe cambiar
**ni una fila** en `stg.*`, `mart.*` ni `cierre.*`.

**R10.** Deben quedar intactas las **13 obras del conjunto A que no duplican**
(0422, 0425, 0435, 0464, 0472, 0473, 0505, 0509, 0514, 0515, 0516, 0521, 0559):
una de sus dos fases no tiene ni una línea de presupuesto.

**R11.** SI el cierre más moderno de un mes tiene el acumulado a cero y otro del
mismo mes no, ENTONCES se descarta **el de cero**. Obligatorio verificarlo en
**0606 · PUY DU FOU**, feb-2021: debe seguir publicando **9.053.263,61 €** de
coste y **9.188.957,62 €** de venta —sin R11 publicaría cero— y en **0433 ·
DOMINO'S PALMA**, nov-2014, donde el cambio esperado es de **0 €**.

## El resultado en la base

**R13.** CUANDO termina `build-mart`, `python main.py check-unicidad` debe dar
**0 claves duplicadas** en `mart.fact_seguimiento_mensual`, frente a las **8.778
(17.556 filas)** de hoy.

**R14.** `mart.fact_seguimiento_categoria.importe_origen` debe dejar de venir
doblado en las **35 celdas de 7 obras**, retirando **30.425.881,56 €**. Uno de
estos contrastes por obra, con las categorías sumadas:

| Obra · mes · escenario | Hoy | Debe quedar |
|---|---:|---:|
| 0499 feb-2018 Coste | 10.753.384,34 | **5.688.073,92** |
| 0571 may-2020 Coste | 9.182.732,45 | **4.591.393,06** |
| 0471 abr-2016 Venta | 1.917.453,12 | **1.049.832,59** |
| 0246 jun-2010 Venta | 1.226.105,88 | **613.052,94** |
| 0462 dic-2015 Coste | 395.309,32 | **197.654,52** |
| 0545 dic-2017 Coste | 308.951,40 | **156.704,75** |
| 0310 may-2011 Venta | 116.072,72 | **58.036,36** |

**R15.** CUANDO termina `build-cierre`, sus **seis** `SUM(pm.importe_origen)`
sobre `stg.plan_mensual` (`cierre/02_build_fact.sql`, `cierre/04_views_detalle.sql`)
deben dejar de contar dos veces.

**R16.** Para cada (`obra_id`, `partida_id`, `ambito_id`), `SUM(importe_mes)`
debe igualar el último `importe_origen` de la serie (el telescopio que F-006
midió 200/200 y que un desplazamiento mal hecho rompería).

## La prueba que decide: antes/después sobre el mismo `raw`

> Requisito del humano del 2026-08-29, y **manda sobre cualquier otra forma de
> verificar**: «hay que probar que el mensual y el acumulado de las obras no
> afectadas no cambie», «con el mismo raw», «en los 4 ámbitos para estar seguro».

**R22.** El sistema debe permitir capturar una **huella** de
`mart.fact_seguimiento_categoria` y de la numeración de fases de
`stg.plan_mensual`, en **solo lectura**, a fichero **fuera de la base**, con
`importe_mes` **e** `importe_origen`, cubriendo los **cuatro ámbitos (3, 7, 8 y
11)**.

**R23.** El sistema debe comparar dos huellas y emitir **la lista completa** —no
una muestra— de (a) las obras cuya **numeración de fase** cambia y (b) las obras
cuyos **importes** cambian, con el ámbito, el mes y la diferencia.

**R24.** El veredicto de esa comparación debe ser: **cambian exactamente las
obras afectadas y solo en lo previsto por R14; el resto, ni un céntimo.** En los
**ámbitos 8 y 11 el resultado esperado es cero cambios** —hoy no tienen ni una
clave duplicada—, y son la prueba de que el arreglo no se desborda.

**R25.** SI la comparación encuentra una diferencia fuera de las 7 obras de R14,
ENTONCES debe salir con código distinto de 0 y **la feature no se cierra**.

## Verificación y documentación

**R17.** Debe existir una comprobación **de solo lectura** que, obra a obra,
contraste `stg.plan_mensual` contra la decisión esperada: qué cierre manda cada
mes, que no queda más de uno, y que el telescopio de R16 se cumple. SI hay
discrepancia, ENTONCES código distinto de 0 nombrando obra, mes y cierres.

**R18.** Debe retirarse del diccionario el aviso de dato doblado en
`mart.fact_seguimiento_mensual`, `mart.fact_seguimiento_categoria`,
`mart.v_pbi_fact` y sus columnas `importe_origen` / `importe_origen_raw`, y
describirse en `stg.plan_mensual` la regla nueva y que `version` es el número
original **con huecos**.

**R19.** El significado debe llegar a la **superficie de consumo**:
`mart.v_pbi_fact_categoria` y `cierre.v_pbi_planif_vs_real` no llevaban ningún
aviso mientras la tabla de la que salen sí lo llevaba.

**R20.** Debe revisarse la **detección de fan-out** del diccionario, que
derivaba de la unicidad de la clave y se apoyaba en una premisa falsa.

**R21.** SI el diccionario cambia, ENTONCES `version` en `00_global.yaml` debe
subir y `check-diccionario` debe seguir dando biyección exacta.
