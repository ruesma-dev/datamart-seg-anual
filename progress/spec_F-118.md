<!-- progress/spec_F-118.md -->
# F-118 · Resumen de la spec y mediciones

Fecha: 2026-09-29 · spec-author · rama `feature/F-118-cruce-cierre-agosto`.
Spec: `specs/F-118-cruce-cierre-agosto/` (requirements 131, design 233, 31
tareas). **F-051 absorbida** por decisión del humano del mismo día. Todo lo
medido es **solo lectura**: Postgres del `.env` (Azure, `sigrid_dm`) en
transacción `READ ONLY`, build nocturno del **2026-09-29** (`build_cierre` 04:10
UTC, el mismo que usó Juan), y `sigrid-api` con `SigridApiClient.leer_sql`. Ni un
build, ni una escritura.

## 0 · En una frase

El fallo 1 y F-103 son **la misma causa** (el movimiento real se calcula sobre
una serie con huecos); F-051 es otra causa (el mes) en **el mismo sitio**; los
tres se arreglan con **una** construcción: la serie densa (design §5). El fallo 2
es otro mecanismo (qué columna suma el cierre) y su criterio lo deciden el humano
y Negocio: recomendación **A**, sin coeficientes.

## 1 · Fallo 1 · la 0709 remedida (coincide con Juan al céntimo)

| Mes 2026 | `cierre` venta mes | `stg`/`mart` venta mes | Acumulado (las dos) |
|---|---|---|---|
| jul | 396.768,08 | 396.768,08 | 2.068.214,21 |
| ago | **377.492,30** | **319.492,30** | 2.445.706,51 |
| sep | 0,00 | 0,00 | 2.445.706,51 |

Partida 417031 (27.01 AJUSTE VENTA), ámbito 7: `raw.obrparpre` tiene f11
(can 1, pre −58.000), **ninguna fila en f12** y f13 (can 0). `stg.plan_mensual`
publica f11 −58.000 y f13 0 con `importe_mes` 0: suma −58.000, acumulado real 0.
Las fases 11–13 tienen texto y fechas del mismo mes: **no es un problema de
mes** (F-051 sola no la arregla). La venta master de esa partida en la v13 es
−58.000 con `impcoe` −69.020 (×1,19): lo mismo que el fallo 2.

**Por qué `cierre` acierta:** suma acumulados por (obra, mes, concepto) y resta
meses; la partida ausente no suma. **Por qué `stg` falla:** resta por partida
solo si su fila anterior es de la fase consecutiva; si no, publica el acumulado.
**Por qué no saltó:** el telescopio de `check-cierres` aparta las series «con
hueco» y compara con la última fila de la partida.

## 2 · Fallo 1 · alcance (partida con acumulado ≠ 0 que falta en el cierre siguiente del ámbito)

| Ámbito | Eventos | Obras | Movimiento que falta (neto) | En valor absoluto |
|---|---|---|---|---|
| 3 coste | 23 | 8 | −381.855,85 | 381.855,85 |
| 7 venta | 467 | 26 | −1.283.966,80 | 1.706.253,40 |
| **Obras de `stg.obras`** | **490** | **32** | **−1.665.822,65** | **2.088.109,25** |
| Fuera de `stg.obras` | 5 | 3 | −80.753,48 | 80.753,48 |

Fuera de `stg.obras` son VAR «OBRAS VARIAS» y dos obras de prueba (180501,
180910): están en `plan_mensual` pero no llegan a `mart` ni a `cierre`. En los
últimos 12 meses, **solo la 0709** (+58.000 en ago-26). Desde 2024: 0658
(sep-24, 86 partidas, neto −21.149,39), 0660 (coste abr-23 −7.200, venta abr-24
−7.000), 0662 (oct-24), 0674 (ene-24, −36.905,90), 0696 (abr-25) y 0709.

Por obra (ámbito, eventos, neto): 0355 (3, 1, −300), 0419 (7, **125**,
−522.924,77), 0462 (7, 1, +20,95), 0465 (7, **60**, −115.303,49), 0470 (7, 17),
0473 (7, 23, −125.654,21), 0483 (3, 4), 0508 (7, 2), 0538 (3, 8, −28.532,11),
0542, 0554, 0562 (3, 3, −312.848,15), 0567, 0581 (7, 1, −186.657,52), 0592,
0599 (7, **63**, −156.180,84), 0610, 0611, 0615, 0616 (7, **61**, −124.630,79),
0627, 0632, 0648, 0652 (3, 3, −19.265,02), 0654, 0658 (7, **86**), 0660, 0662,
0669, 0674, 0696 (3 y 7), 0709. En 30 de los 34 pares (obra, ámbito) alguna
partida **reaparece** después (como la 0709). Las cinco «masivas» (en negrita) son fases con muchas
partidas ausentes a la vez: van a Juan (D9).

«Aparece con cantidad 0» ya se calcula bien hoy si la fase anterior tenía la
partida; solo falla cuando la precede una ausencia (la f13 de la 0709).

## 3 · Todas las series rotas hoy, y a qué grupo pertenecen

Invariante «suma de `importe_mes` = acumulado en el último cierre del ámbito»,
por (obra, ámbito, partida). Rotas: **las 32+3 obras del §2, más**:

- **Hueco de numeración en Sigrid (F-103)**: 0371 f27→29 (coste y venta), 0404
  f6→8, 0455 f4→6, 0562 f21→31 (coste, 3.377.583,79), 0606 f14→17 (con la f15
  inexistente y la f16 descartada por F-042; coste 9.053.263,61, venta
  9.188.957,62). 0371 f29: hoy +4.293.905,89, con la serie densa −441.229,31 =
  `cierre`.
- **Fase de la obra sin ninguna fila de venta** (11 obras): 0247 f9, 0249 f7,
  0255 f14, 0316 f17, 0317 f7, 0318 f8, 0321 f9, 0395 f10, 0412 f5, 0483 f2, 0538
  f2 (8,23 M€ de exceso neto en total; todas de 2010-2020). Solo 0255 y 0483
  tienen fila de venta en `obrfasamb`: Sigrid no abrió la fase de venta.
- Los **descartes de F-042** (0246, 0462, 0471, 0499, 0545, 0571) ya los repara
  `orden_fase` y **no cambian**.

Comparado fila a fila, la serie densa solo cambia `importe_mes` en esos tres
grupos: **ninguna obra con la serie bien se mueve**.

## 4 · `cierre` publica una caída a cero donde no hay cierre del concepto (D5)

`cierre.fact_cierre_mensual` con `fase_numero` NULL, ejecutado a origen 0 y
anterior ≠ 0: **22 obras de VENTA** (0241, 0247, 0249, 0255, 0256, 0272, 0286,
0287, 0316, 0317, 0318, 0321, 0342, 0395, 0427, 0458, 0466, 0467, 0483, 0538,
0562; 2010-03 a 2020-01; −21.788.805,41 € en el mes y su rebote) y 1 de
GENERALES (0538, ene-2018). Es el mismo grupo del §3 visto desde `cierre`, más
obras cuya venta termina antes que el coste. Con la serie densa, `stg` ya no
tendrá conceptos «desaparecidos» por deshacer: la única ausencia que queda es la
de un ámbito sin cierre, y arrastrar es lo correcto (R38).

## 5 · Fallo 2 · coeficientes (coincide con Juan en las 12 obras)

**De dónde salen:** `stg.presupuesto.importe_oficial = COALESCE(NULLIF(impcoe,0),
importe)`. Por ámbito, en `stg` y **leído también en Sigrid** (`obrparpre`):
`impcoe` distinto de `can×pre` **solo en 9 (master certificación, 670.101 filas)
y 11 (master venta, 661.537)**; **0 filas** en 3, 7, 8 y 13. La venta real y el
coste no tienen versión con coeficientes; el respaldo de fase 0 de venta tampoco
cambia nada hoy. En `stg`: 48 obras y 741 versiones master de venta difieren.
En `cierre`: **511 filas-mes de 42 obras** (2021-01 a 2026-08) llevan venta
final con coeficientes; la cabecera cambia el presupuesto vigente en 41 obras y
el inicial en 36. El ratio es 1,19 en casi todas (13 % + 6 %: gastos generales
y beneficio industrial), 1,2574 en la 0702 y 1,2124 en la 0676-B. `mart` ya
planifica la venta **sin** coeficientes (`importe`).

Cierre de agosto de 2026 (venta final, coste final, beneficio final; ejecutado):

| Obra (v) | Venta final hoy | Opción A (sin coef.) | Benef. final hoy | Benef. final A | Ejec. venta hoy | Ejec. venta B |
|---|---|---|---|---|---|---|
| 0672 (39) | 10.087.950,79 | 8.504.774,65 | 615.248,53 | −967.927,61 | 8.504.774,65 | 10.087.950,79 |
| 0676-B (25) | 23.429.009,21 | 19.324.695,13 | 5.388.206,30 | 1.283.892,22 | 17.283.745,61 | 20.913.707,28 |
| 0681 (37) | 7.986.814,97 | 6.739.547,84 | 488.966,90 | −758.300,23 | 6.739.547,83 | 7.986.814,96 |
| 0694 (28) | 7.924.848,81 | 6.659.536,66 | 510.405,56 | −754.906,59 | 1.893.639,56 | 2.253.431,11 |
| 0697 (15) | 2.420.456,58 | 2.039.405,37 | 187.825,16 | −193.226,05 | 504.304,49 | 595.799,06 |
| 0698 (23) | 2.142.011,46 | 1.805.946,51 | 29.983,68 | −306.081,27 | 1.805.946,51 | 2.142.011,46 |
| 0702 (19) | 12.144.681,17 | 9.658.390,84 | 1.695.571,87 | **−790.718,46** | 2.910.579,09 | 3.643.832,04 |
| 0709 (14) | 3.524.865,37 | 2.962.071,66 | 871.216,03 | 308.422,32 | 2.445.706,51 | 2.910.390,79 |
| 0710 (11) | 10.862.989,61 | 9.128.562,59 | 1.368.039,29 | −366.387,73 | 2.755.184,58 | 3.278.669,66 |
| 0712 (11) | 3.315.938,68 | 2.786.503,07 | 755.947,08 | 226.511,47 | 1.908.577,89 | 2.271.207,70 |
| 0713 (11) | 18.229.703,79 | 15.319.078,94 | 2.793.190,39 | −117.434,46 | 3.143.911,27 | 3.741.254,44 |
| 0722 (6) | 1.477.172,09 | 1.244.304,73 | 278.631,83 | 45.764,47 | 1.214.748,60 | 1.442.000,28 |

Diferencias con coeficientes: las 12 de Juan, exactas. En **A** cambian venta
final, pendiente, variación, % y beneficio final; el ejecutado no. En **B** la
venta y el beneficio final **no cambian** (la 0702 sigue en +1.695.571,87, que no
es lo que prevé la hoja de Juan); cambian el ejecutado de venta, el beneficio a
origen y del mes. B se ha medido con el coeficiente partida a partida de la
versión master del mes (`importe_oficial/importe`, 1 si no está): en las obras
terminadas (0672, 0681, 0698) el ejecutado B iguala la venta final, así que es
coherente, pero inventa un dato que Sigrid no guarda en la venta real.

## 6 · Listas esperadas para `comparar-huellas` (R44)

- `stg`/`mart`, ámbitos 3 y 7: obras de F-051 (`check-mes-fase --obras-esperadas`)
  ∪ las 32 del §2 ∪ F-103 (0371, 0404, 0455, 0562, 0606; si D2) ∪ las 11 del §3.
- `cierre`: obras de F-051 ∪ las 22+1 del §4 (si D5) ∪ las 42 del §5 (si D6 = A;
  con B, las mismas 42 en el ejecutado). El fallo 1 y F-103 **no cambian
  `cierre`** por construcción (suma acumulados).
- Ámbitos 8 y 11: ninguna.

## 7 · Unión con F-051

**Se hereda sin tocar:** R1–R8, R10–R20, R22–R28 con su número, sus D1–D9 (con
el matiz de D5), su parser, su relleno, `es_relleno`, la vista blindada, sus
testigos y su protocolo de huellas. **No se reabre ninguna decisión.**
**Se sustituyen dos requisitos, no decisiones** (D1 abajo): R9 (el `LAG` por
`orden_fase` «sin cambios») choca con el fallo 1, porque es exactamente el
cálculo que lo produce; y R21 (antes = después salvo colisiones) deja de valer
porque ahora sí cambian a propósito las series rotas. **Se añade:** `es_deshacer`
(D4) al lado de `es_relleno`, sin tocar D8 de F-051. El relleno y el deshacer
conviven: en un mes de relleno la ausencia arrastra; en un cierre, deshace.

## 8 · Decisiones abiertas (recomendación)

- **D1 · Sustituir F-051 R9 y R21** por la serie densa y el invariante contra el
  acumulado del último cierre. **Sí**: sin ello el fallo 1 no se arregla.
- **D2 · Unir F-103.** Es la misma causa y la serie densa la arregla sin una
  línea propia; no unirla obligaría a reproducir el defecto a propósito. **Sí**:
  el líder marca F-103 como absorbida si el humano lo aprueba.
- **D3 · Fase de la obra sin filas del ámbito** (11 obras de venta, 2010-2020).
  (a) No es cierre de ese ámbito: el movimiento va al siguiente; (b) es un cierre
  a 0: deshacer toda la venta y rehacerla al mes siguiente (lo que hace hoy
  `cierre`). **(a)**: Sigrid no abrió esas fases de venta (9 de 11 sin fila en
  `obrfasamb`).
- **D4 · Marcar las filas de deshacer** con `es_deshacer` en `stg`, `mart` y
  `v_pbi_fact`. **Sí**: son filas que Sigrid no guarda (495).
- **D5 · Arrastrar en `cierre`** el ejecutado de un concepto sin filas en el mes
  (22 obras de venta y 1 de generales, ≤ 2020). **Sí**, aquí: sin ello `mart` y
  `cierre` no cuadran en esas obras. Alternativa: ficha aparte.
- **D6 · Coeficientes, A o B: lo deciden el humano y Negocio.** Recomendación
  **A**: la venta real no lleva coeficientes en Sigrid (0 de 1,82 M filas), `mart`
  ya planifica sin ellos, la hoja de cierre de Juan prevé −790.718 en la 0702
  (= A), y B exige inventar un coeficiente por partida. Juan revisa en Sigrid por
  qué esos masters los llevan (F-099 publicará los expedientes).
- **D7 · Alcance del contraste:** huellas `stg`, `mart`, `cierre` antes y después
  con las listas del §6, `--propuesta` antes de desplegar y la hoja de cierre de
  agosto de Juan para las 12 obras y la 0709. **La hoja no se versiona** (resultados
  de obra): el humano la pide y el resultado va a `impl_F-118.md`.
- **D8 · Partir el fallo 2** si D6 no está decidida al acabar el bloque D de
  tareas: el bloque E pasa a una feature propia sin bloquear lo demás. **Sí.**
- **D9 · Casos para Juan:** 0606 PUY DU FOU pasa a publicar en `mart` −9.053.263,61
  de coste y −9.188.957,62 de venta en sep-2021 (hoy ya en `cierre`), y las cinco
  desapariciones masivas (0419, 0465, 0599, 0616, 0658). **Aplicar la regla**, que
  es la de Juan, y pasarle la lista antes de desplegar (T27).

## 9 · Hallazgos al margen

- 2 inversiones fase/mes del texto en todo el histórico (anteriores a 2020).
- Tres obras de prueba/varias en `stg.plan_mensual` fuera de `stg.obras` (§2).
