<!-- specs/F-118-cruce-cierre-agosto/requirements.md -->
# F-118 · Requisitos · La serie mensual real, bien construida, y la venta final en la misma base que el ejecutado

**Origen.** Correo de Juan Romero del 2026-09-29 (dos fallos del cruce del
cierre de agosto) y **F-051 absorbida** por decisión del humano del mismo día.
Cifras remedidas en solo lectura (build del 29-09): `progress/spec_F-118.md`.
Decisiones abiertas **D1–D9**: `design.md` §10. Las **D1–D9 de F-051** siguen
decididas y no se reabren (`specs/F-051-nombre-mes-real/design.md` §10).

**Trazabilidad.** `[F-051 Rn]` = requisito de F-051 con su número;
`[Juan-1]`, `[Juan-2]` = fallo 1 y 2 del correo; `[F-103]` = si el humano la une
(D2). Los números R1–R28 son los de F-051 para no romper su rastro; R9 y R21 se
**sustituyen** (D1). R29 en adelante son nuevos.

**Glosario.** *Cierre del ámbito* = fase real vigente (tras F-042) con al menos
una fila de ese ámbito en la obra. *Serie de una partida* = sus meses desde el
primer cierre en que aparece. *Deshacer* = anular en un mes el acumulado que la
partida traía, porque en ese cierre ya no está o está a 0. Nunca «estorno».

---

## A · Heredados de F-051 sin cambios (texto completo en su `requirements.md`)

- **R1** una regla del mes, en `stg.fn_mes_de_fase`; `cierre.fn_mes_de_fase` da lo mismo. `[F-051 R1]`
- **R2** texto y fecha discrepan → manda el texto, también en fases de un mes. `[F-051 R2]`
- **R3** texto con rango → último mes del rango. **R4** años 00–19 y «2.013». `[F-051 R3, R4]`
- **R5** `cierre.fn_parse_mes_fase` (masters) no cambia. `[F-051 R5]`
- **R6** texto ilegible → `fecha_fin` → `fecha_inicio` → `ano`/`mes`. `[F-051 R6, D5]`
- **R7** `anio_mes` de las filas reales = mes del texto. `[F-051 R7]`
- **R8** F-042 (un cierre por mes, el más moderno con acumulado ≠ 0) sobre el mes del texto. `[F-051 R8]`
- **R10–R14** relleno de fases de rango: meses a 0, nunca en mes con cierre propio, acumulado arrastrado, solo partidas con acumulado o movimiento, nada después del mes del texto. `[F-051 R10–R14]`
- **R15** `es_relleno` en `stg`, `mart` y `cierre` (NULL en planificadas). `[F-051 R15]`
- **R16–R17** mismo mes en las tres capas; `nombre_mes` de `mart` sale de `anio_mes`. `[F-051 R16, R17]`
- **R18–R20** `cierre.v_pbi_planif_vs_real` sin columnas descriptivas en su grano; `check-unicidad` en OK. `[F-051 R18–R20]`
- **R22** los ámbitos 8 y 11 no cambian ni una fila ni un céntimo. `[F-051 R22]`
- **R23** obra sin fase afectada por el mes, el relleno ni la serie densa → idéntica celda a celda. `[F-051 R23, ampliado]`
- **R24** testigos de F-051 (0650, 0660, 0664, 0686, 0683, 0646, 0673, 0440, 0571). `[F-051 R24]`
- **R25–R26** oráculo puro de la regla y del relleno, y `check-mes-fase`. `[F-051 R25, R26]`
- **R27** diccionario del mes y del relleno. **R28** fichero que da forma a `plan_mensual` → `FICHEROS_DEL_SELLO`. `[F-051 R27, R28]`

## B · La serie densa: deshacer lo que desaparece (sustituye F-051 R9 y R21)

**R9 (sustituye a F-051 R9).** El `importe_mes` real de cada (obra, ámbito,
partida) debe ser su acumulado del mes menos su acumulado del mes anterior **de
su propia serie**, ordenada por `anio_mes` y sin ningún hueco: se deja de mirar
si la fase anterior es consecutiva (`orden_fase`). `[Juan-1] [F-103]`

**R29.** CUANDO una partida con acumulado ≠ 0 en un cierre del ámbito no tiene
fila en el cierre siguiente del mismo ámbito, el sistema debe emitir en el mes
de ese cierre una fila con acumulado 0 e `importe_mes` = −acumulado anterior
(y lo mismo con `importe_mes_raw`, `can_mes` y `total_incurrido_mes`). `[Juan-1]`

**R30.** CUANDO la partida reaparece en un cierre posterior, su `importe_mes` debe
calcularse contra 0 (lo deshecho), no contra el último acumulado que tuvo. `[Juan-1]`

**R31.** Una fila de R29 debe llevar `version` = número de fase del cierre donde
falta, `presupuesto_id` y `precio_unitario` de la última fila de la partida, y
publicar `es_deshacer = TRUE` en `stg`, `mart` y `v_pbi_fact` (D4). `[Juan-1]`

**R32.** Tras la partida deshecha, el sistema no debe emitir más filas suyas
mientras siga ausente: solo la fila que mueve el acumulado. `[Juan-1]`

**R33.** En un mes de relleno (R10–R14) la ausencia NO deshace: arrastra el
acumulado del cierre anterior, ya deshecho si lo estaba. `[F-051 R12, Juan-1]`

**R34.** SI una fase real existe en la obra pero el ámbito no tiene ninguna fila
en ella, ENTONCES esa fase no es cierre de ese ámbito: no se deshace nada y el
movimiento va al siguiente cierre del ámbito (D3, 11 obras de venta). `[Juan-1]`

**R21 (sustituye a F-051 R21).** Para toda (obra, ámbito, partida) de
`stg.plan_mensual`, la suma de `importe_mes` debe ser igual al acumulado de la
partida en el último cierre del ámbito de la obra (0 si ya no está). `[Juan-1] [F-103]`

**R35.** CUANDO se construye la obra 0709, la venta real de agosto de 2026 en
`stg` y `mart` debe dar **377.492,30 €**, la de septiembre **0,00 €**, y la
partida 417031 (27.01 AJUSTE VENTA) debe sumar 0 en sus `importe_mes`. `[Juan-1]`

**R36.** DONDE se una F-103 (D2), 0371 f29 debe publicar −441.229,31 € de coste
en `mart`, igual que `cierre`. `[F-103]`

**R37.** `check-cierres` debe comprobar R21 en TODAS las series, sin apartar
ninguna por «hueco de origen», contra el acumulado del último cierre de la obra
y no contra la última fila de la partida. `[Juan-1]`

**R38.** DONDE el humano elija arrastrar en `cierre` (D5), SI un concepto de
una obra no tiene filas en un mes que sí tiene cierre de otro concepto,
ENTONCES su `ejecutado_origen` debe ser el del mes anterior, no 0. `[Juan-1]`

## C · La venta final en la misma base que el ejecutado (fallo 2)

**R39.** La venta FINAL de `cierre.fact_cierre_mensual` (rama master y respaldo
de fase 0) y el ejecutado de venta deben expresarse en la misma base, según el
criterio que decidan el humano y Negocio (D6): (A) sin coeficientes, o (B) con
coeficientes también en el ejecutado. `[Juan-2]`

**R40.** DONDE se elija (A), la venta final debe salir de `importe` y la 0702 en
agosto de 2026 debe dar venta final 9.658.390,84 €, coste final 10.449.109,30 € y
beneficio final **−790.718,46 €**. `[Juan-2]`

**R41.** DONDE se elija (B), el ejecutado de venta debe llevar, partida a
partida, el coeficiente `importe_oficial / importe` de la versión master que
fija la venta final de ese mes (1 si la partida no está o su importe es 0), y la
0702 debe dar un ejecutado de 3.643.832,04 € en agosto de 2026. `[Juan-2]`

**R42.** `cierre.v_pbi_cierre_cabecera` (presupuesto inicial y vigente,
modificados) y las vistas que usan `final_importe` (resumen, detalle de
indirectos) deben heredar la base elegida sin cálculo propio. `[Juan-2]`

**R43.** `stg.presupuesto.importe_oficial` debe seguir publicándose tal cual: el
dato de Sigrid no cambia, cambia qué columna usa el cierre. `[Juan-2]`

## D · Contraste

**R44.** El sistema debe contrastarse antes y después obra a obra con las
huellas `stg`, `mart` y `cierre` sobre el mismo `raw`, y `comparar-huellas` debe
fallar fuera de la lista de obras esperadas que declara `progress/spec_F-118.md`.

**R45.** CUANDO se despliegue, el cierre de agosto de 2026 de las 12 obras del
correo y de la 0709 debe cuadrar con la hoja de cierre de agosto de Juan, obra a
obra en venta, coste y beneficio a origen, del mes y final (MANUAL, D7).

**R46.** El diccionario (`stg`, `mart`, `cierre`, `00_global`) debe decir cómo se
construye la serie, qué es una fila de deshacer y en qué base va la venta final,
sin la palabra «estorno» en ningún texto nuevo o modificado; sube `version`.

## E · Lo que NO hace

- No corrige nada en Sigrid: por qué esos masters llevan coeficientes lo mira Juan.
- No publica los coeficientes por separado ni los expedientes: es F-099.
- No toca la rama master de `08_plan_mensual.sql` (el tope del 250 % es F-096).
- No reparte con compras ni partes, y no cambia la frontera de fases de F-051.
