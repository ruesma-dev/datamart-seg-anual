<!-- specs/F-051-nombre-mes-real/requirements.md -->
# F-051 · Requisitos · Cada cierre real en el mes de su TEXTO, en las tres capas

**Decisiones del humano del 2026-09-22** (ficha F-051, con sus palabras):
«Si la fecha ini y fin implican un rango de fechas, entonces se concentrará el
coste y la venta en el MES FINAL, que debe ser el del TEXTO (el texto manda). En
los meses anteriores, desde fecha ini hasta texto −1 mes, coste y venta serán
0.» «Puede ocurrir que el cierre diga un mes y el texto otro: se aplica en el
mes del texto.» «Si un mes en una fase anterior ya daba resultados […] el mes
inicial no debe pisar uno que ya tenga datos.» Juan Romero lo confirma: «Llevamos
todo el dinero al último mes, son casos residuales». **Se descarta** repartir
con las fuentes de coste.

Línea base medida y listas: **`progress/spec_F-051.md`** (build 2026-09-22, solo
lectura). Alcance: ámbitos **reales** 3 y 7 en `stg`, `mart` y `cierre`. Los
master (8, 11) **no se tocan**. D1–D9 decididas el 2026-09-22: `design.md` §10.

**Glosario.** *Mes del texto* = `stg.fn_mes_de_fase(fecha_inicio, nombre_mes,
fecha_fin, …)`: el texto manda; si no se lee, la fecha fin (R6). *Fase de rango*
= mes(`fecha_fin`) > mes(`fecha_inicio`). *Relleno* = fila de coste o venta real
a 0 en un mes anterior al del texto. La fase es **por obra** (`raw.obrfas`) y
vale para coste y venta: `obrfasamb` no guarda periodo (comprobado, §2 del
resumen).

---

## A · El mes de un cierre: una regla, una implementación

**R1.** El sistema debe implementar la regla del mes una sola vez, en
`stg.fn_mes_de_fase`, y `cierre.fn_mes_de_fase` debe devolver exactamente lo
mismo para los mismos argumentos (la resolución de masters no cambia, R5).

**R2.** SI el texto y la fecha de inicio dan meses distintos, ENTONCES manda el
texto, también en fases de un solo mes (0673 f8 «Diciembre-24», fechas de
marzo-2024, va a diciembre-2024) y aunque el texto caiga fuera de las fechas.

**R3.** SI el texto nombra un rango de meses («Enero 2020-Abril 2020»,
«Diciembre 2014 - Enero 2015», «DICIEMBRE 09 A FEBRERO 2010»), ENTONCES el mes
del texto debe ser el ÚLTIMO mes del rango con su año (**D4**).

**R4.** SI el texto trae el año con dos cifras entre 00 y 19 («DICIEMBRE-19»,
«AGOSTO17») o con punto de millar («Abril 2.013»), ENTONCES debe leerse como
ese mes y año, y no como texto ilegible (**D4**).

**R5.** `cierre.fn_parse_mes_fase`, que usan las versiones master, no debe
cambiar de comportamiento: R3 y R4 viven solo en el parser de `stg`.

**R6.** SI el texto de una fase real no se entiende, ni con R3–R4, ENTONCES
manda la fecha en cascada: mes de `fecha_fin`; sin ella, de `fecha_inicio`; sin
ninguna, `ano`/`mes` de `obrfas` (**D5**, matiz del humano del 2026-09-22).

## B · Dónde cae cada fila real

**R7.** CUANDO `stg.plan_mensual` construye las filas reales, `anio_mes` debe
ser el mes del texto de su fase, no el `ano`/`mes` que archiva `obrfas`.

**R8.** CUANDO dos fases de una obra y ámbito tienen el mismo mes del texto, el
sistema debe aplicar la regla de F-042 (manda la de mayor fase con acumulado
distinto de cero, y se renumera `orden_fase`) sobre ese mes (**D2**).

**R9.** El `importe_mes` de cada fase debe seguir calculándose con el `LAG` por
`orden_fase` de F-042, sobre la fase entera y sin cambios.

**R10.** CUANDO una fase vigente es de rango y su mes del texto es posterior al
de `fecha_inicio`, el sistema debe emitir filas de relleno en cada mes desde el
de `fecha_inicio` hasta el anterior al del texto, con `importe_mes`,
`importe_mes_raw`, `can_mes` y `total_incurrido_mes` a 0.

**R11.** SI un mes del relleno ya tiene fila de un cierre vigente de otra fase de
esa obra y ámbito (aunque valga 0), ENTONCES el sistema no debe emitir relleno en
ese mes: el relleno solo crea meses que no existen (**D1**).

**R12.** En una fila de relleno, `importe_origen` (y `importe_origen_raw`,
`can_origen`, `total_incurrido`) debe ser el de esa partida en el último cierre
vigente con mes anterior al del relleno, o 0 si no lo hay: el acumulado no salta.

**R13.** El relleno debe emitirse para las partidas que tienen acumulado
anterior distinto de 0 o movimiento en la fase (**D3**), con `version` = el
número de fase que lo genera.

**R14.** El sistema no debe emitir relleno después del mes del texto, aunque las
fechas de la fase sigan (fases cuyo texto es su primer mes o uno intermedio).

**R15.** Cada fila real de `stg.plan_mensual`, `mart.fact_seguimiento_mensual` y
`cierre.fact_cierre_mensual` debe publicar `es_relleno` (**D8**); NULL en las
filas planificadas.

## C · Las tres capas en el mismo mes

**R16.** `cierre.fact_cierre_mensual` y sus vistas `v_pbi_cierre_indirectos_detalle`
y `v_pbi_cierre_generales_detalle` deben tomar el mes de
`stg.plan_mensual.anio_mes`, sin recalcularlo: para toda fila real, (obra, mes)
coincide en `stg`, `mart` y `cierre`.

**R17.** En las ramas COSTE REAL y VENTA REAL de `mart/02_build_fact.sql`,
`nombre_mes` debe derivarse de `anio_mes` con el ARRAY sin locale de las ramas
planificadas, y el texto de la fase debe quedar en `version_descripcion`.

## D · La vista, blindada

**R18.** `cierre.v_pbi_planif_vs_real` no debe agrupar por `nombre_mes` ni por
ninguna columna descriptiva: agrupa por (`obra_id`, `anio_mes`, `categoria`,
`concepto`) y deriva `nombre_mes` de `anio_mes`.

**R19.** El CTE `beneficio` debe unir `producc` y `total_costes` al mismo grano
con el que agregan, y la vista debe publicar una sola fila por (`obra_id`,
`anio_mes`, `concepto_cuadro`).

**R20.** CUANDO se ejecuta `check-unicidad` tras el build,
`cierre.v_pbi_planif_vs_real` debe salir OK (hoy 204 combinaciones repetidas).

## E · Invariantes y verificación

**R21.** Para toda (obra, ámbito, partida), la suma de `importe_mes` y el último
`importe_origen` de `stg.plan_mensual` deben ser idénticos antes y después sobre
el mismo `raw`, salvo las obras cuya colisión de F-042 cambie por R8, que se
listan y se explican una a una.

**R22.** Los ámbitos 8 y 11 no deben cambiar ni una fila ni un céntimo.

**R23.** Las obras sin ninguna fase cuyo mes del texto difiera del archivado ni
ninguna fase de rango deben quedar idénticas celda a celda en `stg`, `mart` por
categoría y `cierre`.

**R24.** Los testigos de `design.md` §Testigos deben publicar lo previsto: 0650
f20, 0660 f28, 0664 f36, 0686 f2, 0683 f17, 0646 f28, 0673 f8, 0440 f3 y 0571
(en 2020-05, una sola fila por `concepto_cuadro`; hoy BENEFICIO sale 8 veces).

**R25.** Un test de dominio debe fijar la regla del texto (las cuatro ramas y
R2–R6) contra un oráculo puro, y `check-mes-fase` debe comprobar, en solo
lectura, que `stg.fn_mes_de_fase` y el oráculo coinciden en todas las fases.

**R26.** Tests de dominio deben fijar el relleno (R10–R14), la precedencia de
R11 junto a la colisión de R8, y el invariante de R21 con casos generados.

**R27.** El diccionario debe decir de dónde sale `anio_mes` en las filas reales,
qué es una fila de relleno y el nuevo grano de la vista, en `stg`, `mart` y
`cierre`, con fichas para las dos funciones nuevas; sube `version`.

**R28.** SI un fichero SQL da forma a `stg.plan_mensual`, ENTONCES debe estar en
`FICHEROS_DEL_SELLO`, para que su despliegue reconstruya las 920 obras.

## F · Lo que NO hace

- No publica estado, activa ni ámbito/fase originaria de las fases, ni controla
  fases mal generadas: feature aparte (frontera fijada el 2026-09-22).
- No corrige nada en Sigrid: los casos para Juan están en el resumen, §5.
- No arregla los 5 huecos de numeración de Sigrid que inflan `importe_mes`
  (0371 f28: +4,29 M€ en `mart` donde `cierre` da −441.229,31): ficha aparte.
- No reparte nada con compras ni partes: descartado por el humano.
