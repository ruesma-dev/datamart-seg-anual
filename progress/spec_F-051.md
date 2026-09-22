<!-- progress/spec_F-051.md -->
# F-051 · Resumen de la spec y línea base medida

Fecha: 2026-09-22 · spec-author · rama `feature/F-051-nombre-mes-real` (desde
`chore/fichas-2026-09-22`). Spec: `specs/F-051-nombre-mes-real/`
(requirements 150/150, design 250/250, 22 tareas). Todo lo medido es **solo
lectura**: MCP `bbdd-ruesma-azure` (build del **2026-09-22**, no del 18-09) y
`sigrid-api` con `SigridApiClient.leer_sql`. Ni un build, ni una escritura.

## 0 · Qué decide la spec (tras tres mensajes del líder con decisiones del humano)

1. El mes de cada fila real lo da el **TEXTO** de la fase (`fn_mes_de_fase`,
   ahora implementada una vez en `stg`), también en fases de un mes que
   discrepan y aunque el texto caiga fuera de las fechas.
2. Fase de **rango** (mes de `fecfin` > mes de `fecini`): todo el coste y la
   venta al mes del texto; desde el mes de `fecini` hasta el anterior al del
   texto, **filas de relleno a 0** (movimiento 0, acumulado arrastrado).
3. El relleno **nunca pisa** un mes con cierre propio de otra fase.
4. `stg.plan_mensual.anio_mes` es la única fuente del mes: `mart` y `cierre` lo
   leen sin recalcular. La vista `cierre.v_pbi_planif_vs_real` deja de agrupar
   por `nombre_mes`; `nombre_mes` sale de `anio_mes` en las cuatro ramas de
   `mart` y el texto queda en `version_descripcion`.
5. Descartada por el humano la reconstrucción con fuentes de coste. Nota de
   contexto de lo que se llegó a medir antes del cambio: en 17 cierres con coste
   desde 2024, el 69 % del |importe_mes| tenía alguna fuente fechada a nivel de
   partida; en venta no hay ninguna fuente fechada en el datamart.

## 1 · Clasificación de las fases (stg.fases, anio>0, mes>0, fase≥1)

Reproducida la del líder: 510 de varios meses con texto que discrepa del
archivado, 147 de varios meses sin discrepancia, 68 con rango en el texto, 14 de
un mes que discrepan. Con el universo `stg.obras`, las **fases de rango** son
694 por el caso de su texto:

| Texto frente a las fechas | Fases | Qué hace F-051 |
|---|---|---|
| texto = mes de `fecfin` | 508 | relleno desde `fecini` hasta el mes anterior |
| rango en el texto | 66 | con D4, el último mes del rango; relleno antes |
| texto = mes de `fecini` | 59 | sin relleno (R14); la mayoría son cortes a mitad de mes (16→15), no aglutinados |
| sin texto legible | 43 | con D5, mes de `fecfin` |
| texto intermedio | 16 | relleno hasta el texto; nada después |
| texto después de `fecfin` | 1 | 0249 f6 «DICIEMBRE 09 A FEBRERO 2010» (con D4 → feb-2010) |
| texto antes de `fecini` | 1 | 0337 f1 «Marzo 2011», fechas oct-2011→mar-2012: manda el texto, sin relleno |

Relleno: **522 fases** tienen meses que rellenar, **2.480 meses** en total
(mediana 3, máximo 23; 217 son la última fase de su obra, con 1.359 meses).
Filas estimadas (muestra de 25 fases): **~1,34 M** con la opción D3
recomendada, ~2,56 M con todas las partidas. Hoy `stg.plan_mensual` tiene 29,9 M
filas (11 GB) y `mart.fact_seguimiento_mensual` 5,39 M (2,27 GB).

Solape con el cierre anterior: 25 fases de rango tienen el mes del cierre
anterior dentro de sus fechas (el caso de la regla «no pisar»). Solape de fechas
con la fase siguiente: 2.

## 2 · ¿Las fases son por ámbito? Comprobado en Sigrid (solo lectura)

Juan Romero dice que en Sigrid las fases se mantienen por ámbito. Resultado:
`obrfasamb` (ámbitos 3 y 7, 4.574 + 4.530 filas) guarda por ámbito **estado**
(`est`), **activa** (`act`), **fecha de cierre** (`feccie`, distinta entre coste
y venta en 1.894 de 4.530 pares) y **ámbito/fase originaria** (`oriamb`/`orifas`,
p. ej. 0708 f5 coste originada desde venta), pero **`res`, `tex` y `fec` están
vacíos en el 100 %** y no tiene fechas de periodo. Las fechas y el texto solo
existen en `obrfas`, una fila por obra y fase. Conclusión: el detector y el mes
destino son **por obra** y valen para coste y venta. 45 fases no tienen fila de
venta en `obrfasamb` y 1 no la tiene de coste. Publicar estado/activa/originaria
es la feature aparte que fija la frontera del 22-09.

## 3 · Textos reales que fija el test (y defectos del parser actual)

`cierre.fn_parse_mes_fase` no lee **102** textos de fase: 20 con año de dos
cifras 10–19 («Abril-19», «AGOSTO17», «DICIEMBRE-13»), 13 con punto de millar
(«Abril 2.013», «AGOSTO 2.010»), 3 con año 0x, «AÑO 2012», «2012», «POSTVENTA
2009», «LEVANTAMIENTO», «Dciiembre 2018», «SEPTIEMBRE-DICIEMBRE». Y lee **el
primer mes** de los 73 textos con dos meses: «Enero 2020-Abril 2020» → enero,
«Mayo-Julio 2012» → mayo, «Diciembre 2014 - Enero 2015» → dic-2014, «Junio-Julio-1
2017» → junio. Con D4 esos textos van al último mes. Casos para la tabla del
test: los anteriores más 0673 f8 «Diciembre-24» (fechas mar-2024) → dic-2024,
0692 f14 «Febrero 2026» (archivada ene-2026) → feb-2026, 0440 f3 «Mayo 2015»
(archivada mar-2015) → may-2015, 0444 f21 «Mayo-17» con fechas invertidas
(01-12-2017 → 31-05-2017).

## 4 · Lo que se mueve

- **Mes distinto entre capas hoy** (medición del líder, `cierre.fact_cierre_mensual`):
  500 cierres de 255 obras, 276 con dinero, 15,3 M€ de venta en valor absoluto;
  desde 2024, 102 y 17 con dinero. Con F-051 `mart` pasa a publicar el mes que
  ya publica `cierre`, salvo las fases que cambian por D4/D5 (entonces cambian
  las dos capas).
- **Fases de rango con dinero en `cierre`**: 279 de 503 (179 obras); desde 2024,
  19. Lista de 2024+ y testigos en `design.md` §8.
- **Fases de un mes que discrepan (regla decidida, se aplica el texto)**:
  mueven dinero 0440 f3 (coste 126.384,35, venta 105.734,94, mar→may 2015),
  0656 f1 (71.305,82 / 41.574,30, ene→dic 2022), 0692 f14 (coste 29.027,32,
  ene→feb 2026), 0677 f1 (1.000,00 / 1.180,95, ene→dic 2023), 0266 f10 (679,03),
  0555 f2 (−553,97), 0298 f4 (−0,65); a cero o sin filas: 0331 f3, 0444 f21,
  0546 f16, 0559 f3, 0569 f13, 0575 f2, 0673 f8.
- **Colisiones de F-042 sobre el mes del texto**: 21 (hoy 24 sobre el
  archivado); 19 iguales; nuevas 0444 dic-2017 {21,26} y 0546 sep-2019 {16,17};
  desaparecen 0246 jun-10 {12,13}, 0514 nov-16 {2,3}, 0515 dic-16 {3,4}, 0571
  may-20 {21,22} y 0606 feb-21 {14,16}: la fase que F-042 descartaba revive en
  el mes de su texto. Son exactamente el patrón 2 de F-050. El total por obra no
  cambia (el `LAG` sigue telescopiando), el reparto mensual sí.
- **0571** (el fan-out de la vista): hoy f21 «Enero 2020-Abril 2020» está
  descartada y f22 «Agosto 2020» vive en may-2020. Después: f21 en abr-2020
  (relleno ene–mar) y f22 en ago-2020 (relleno may–jul).

## 5 · Para Juan Romero (no se inventa regla; manda el texto)

- Confirmados por Juan el 22-09: 0673 f8 (debería ir hasta dic-24) y 0692 f14
  (debería ser 01/01–28/02). Mientras Sigrid no cambie, 0692 ene-2026 se queda sin
  fila (sus fechas dicen un mes).
- Texto de un mes que contradice sus fechas: 0266 f10, 0298 f4 (abr→oct 2011),
  0331 f3, 0546 f16, 0555 f2, 0559 f3, 0569 f13 (texto anterior), 0673 f8.
- Fechas raras: 0444 f21 (invertidas), 0337 f1 (texto antes de `fecini`), 0249
  f6, y las 59+16 fases con texto = primer mes o intermedio (lista con
  `check-mes-fase`).

## 6 · Hallazgos fuera de alcance (proponer ficha)

- **Huecos de numeración de Sigrid** (0371 f28, 0404 f7, 0455 f5, 0562 f22–30,
  0606 f15): la fase siguiente publica el acumulado ENTERO como `importe_mes`.
  0371 f29: `stg`/`mart` dan **+4.293.905,89** en 2015-02 donde `cierre` da
  −441.229,31 (4.293.905,89 − 4.735.135,20). Ficha aparte.
- **0606 PUY DU FOU desde f17** (sep-2021): fases valoradas a cero; `cierre`
  publica −9.053.263,61 de coste y −9.188.957,62 de venta en sep-2021 y `stg`
  da movimiento 0. Es de F-050 / Negocio.

## 7 · Decisiones para el humano

D1–D9 con opciones, cobertura medida y recomendación: `design.md` §10.
Resumen de las recomendaciones: D1 «tener datos» = existe fila de cierre de otra
fase aunque valga 0; D2 F-042 sobre el mes del texto; D3 relleno solo en
partidas con acumulado o movimiento; D4 parser nuevo solo en `stg`; D5 sin
texto → mes de `fecfin`; D6 sin relleno después del mes del texto; D7 exención
de mutación como F-042; D8 publicar `es_relleno`; D9 reducir F-050 y fichar
los huecos de numeración.

## 8 · Coordinación

- **F-096** toca la rama master del mismo `08_plan_mensual.sql`: sin conflicto
  de líneas; primero F-051 y F-096 rebasa; ámbitos disjuntos en las huellas.
- **F-076**: no hay fuente fechada de venta (certificación comparte las fases
  de `obrfas`); nada que coordinar tras descartar el reparto.
