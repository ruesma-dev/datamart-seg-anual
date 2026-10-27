<!-- progress/spec_F-150.md -->
# F-150 · Informe del spec-author (la receta de la caja, fase 1)

Fecha: 2026-10-26. Rama `feature/F-150-receta-caja` desde `main` (`6681de8`). Spec en
`specs/F-150-receta-caja/`; decisiones abiertas D1-D10 en su `design.md` §9. Rama re-apuntada a `main` `d3b412a` (el 27-10 `main` ganó dos commits de `progress/`; la rama aún no tenía commits).

Todo es de SOLO LECTURA: Azure con `main._get_pg()`, `_bootstrap_done = True` y
`filas_solo_lectura` (nocturna del 2026-10-26, la primera con F-140 desplegada), y Sigrid con
`main._get_api().leer_sql`. Solo agregados: ni nombres, ni importes de un tercero concreto.

## 1. El ámbito 9 (MASTER CERTIFICACION) en el datamart

| Hecho | Medido |
|---|---|
| `stg.ambitos` | 9 = `MASV`, MASTER CERTIFICACION, tipo `MASTER_CERTIFICACION`, sin `uso_seguimiento` |
| `stg.presupuesto`, ámbito 9 | 2.184.787 filas, 202 obras, 2.913 versiones; 430.601 filas con `importe_oficial` distinto de `importe` |
| `stg.presupuesto`, ámbito 11 | 2.540.243 filas, 228 obras, 3.190 versiones; 420.032 con coeficiente |
| `stg.plan_mensual` | SOLO ámbitos 8 y 11 (`sql/stg/08_plan_mensual.sql`): el 9 no tiene perfil mensual en el datamart |
| `mart.master_versiones_tipadas` | SOLO 8 y 11 (2.246 y 2.240 versiones, 132 obras): el 9 no está tipado |
| Sigrid `obrfasamb.plafec` > 0 | ámbito 9: **199 de 3.116** versiones; 11: 2.264 de 3.204; 8: 2.279 de 3.212 |
| Sigrid `obrparpre.planif` no vacío, última versión de cada obra | ámbito 9: **7.178 de 123.317** filas; 11: 94.520 de 143.783 |

Coincide con lo medido por el líder (199 de 3.115 versiones: hoy una más; 7.178 partidas). Su
denominador de 85.914 partidas es otro universo; el mío es la última versión de cada obra.

## 2. El coeficiente en las partidas de VENTA con devengo pendiente (el universo de F-150)

Universo: `tesoreria.devengo_pendiente_partida` con `concepto = 'VENTA'`: **18.997 partidas, 21
obras, pendiente 132,37 M EUR** (sin coeficientes). V = `version_master` de la fila.

**Versiones.** En las 21 obras el ámbito 9 TIENE la versión V (misma `fase_num`); y la última
versión del 9 es igual a la última del 11 en las 21, pero V es anterior a esa última en 20 de 21
(V es la que rige el último mes pendiente, no la más nueva: F-140, D2-A). Tomar «la última del 9»
mezclaría versiones.

Coeficiente = `SUM(importe_oficial) / SUM(importe)` por (obra, partida), ámbito y versión:

| Medida | 9 en V, 11 en V | 9 en su última versión, 11 en V |
|---|---|---|
| Partidas con coeficiente del 11 | 17.366 | 17.366 |
| Partidas con coeficiente del 9 | 17.207 | 17.236 |
| Sin fila en el 9 | 488 | 439 |
| Coeficiente igual (4 decimales) / distinto | **16.894 / 269** | 16.888 / 276 |
| Distintos con pendiente > 0 | 238 partidas, **0,02 M EUR** de pendiente | — |
| Con pendiente > 0 y sin coeficiente del 11 | **0** | 0 |
| Con pendiente > 0 y sin coeficiente del 9 | **93** (0,79 M EUR) | 113 |
| Pendiente × coeficiente (9, si no 11) | **143,198 M EUR** | 143,20 |
| Pendiente × coeficiente (solo 11) | **143,198 M EUR** | 143,20 |
| Diferencia absoluta entre las dos | < 0,001 M EUR | — |
| Coeficientes fuera de [0,9; 1,5] | 0 | — |

**Conclusión**: en las partidas pendientes el coeficiente del 9 y el del 11 son el mismo salvo
en 238 partidas que pesan 0,02 M EUR; el 9 no tiene 93 partidas pendientes (0,79 M EUR), que
necesitan el 11 de respaldo. El coeficiente sube el pendiente de venta un **8,2 %** (132,37 ->
143,20 M EUR).

**El IMPORTE del 9 sí difiere del 11**: 8.965 partidas (7.018 con pendiente); en el total de V de
estas partidas, 231,82 M EUR en el 9 frente a 251,45 en el 11 sin coeficientes (250,02 frente a
273,66 con ellos): un 7,8 % menos. Usar el 9 como importe a certificar cambiaría el pendiente, y
exigiría su ejecutado propio (la certificación real, ámbito 5) y un perfil temporal que el 9 no
tiene: es el lado de ingresos de F-040, no esta feature.

**Mixtas.** Por obra (coeficiente del 11 en V, 3 decimales): 12 obras todo a 1,000; 2 todo a
1,190; **5 obras mezclan partidas a 1,000 con otras a 1,19-1,26** (coeficiente medio de obra
entre 1,187 y 1,257); 2 a 1,189-1,194 (redondeos de 1,19). Un coeficiente medio de obra se
equivoca en las 5 mixtas: hay que llevarlo por partida.

## 3. Formas de pago con varios vencimientos (`tesoreria.plazos_forma_pago`)

| Sentido | Vencimientos | Formas | Fórmulas |
|---|---|---|---|
| COBRO | 1 | 49 (17 con `NR`) | `0`…`180`, `N 365R` |
| COBRO | 2 / 3 | 1 / 2 | `120 150` / `30 60 90`, `60 90 120` |
| PAGO | 1 | 67 (25 con `NR`) | `0`…`180`, `N 450R` |
| PAGO | 2 / 3 | 1 / 2 | `120 150` / `30 60 90`, `60 90 120` |

**Uso real**: contratos de compra con 3 vencimientos, **6 de 19.170 (0,1 M EUR)**; con 1, 19.155
(705,3 M EUR); sin forma, 9. Contratos con el cliente con más de un vencimiento: **0** (705 con
uno, 265 sin forma; en las obras con devengo, 54 con uno y 2 sin forma). Sigrid no guarda
porcentajes por vencimiento (`auxpag.can`, `cat`, `ser` vacíos; `obrctr.cobmeses`, `cobporret`
a 0, `progress/spec_F-140.md` §1). **`plazos_forma_pago` ya da los vencimientos múltiples, pero
casi nadie los usa**: el reparto en varios meses no se puede leer de Sigrid, tiene que ser una
hipótesis con defecto y valor por obra.

`hipotesis_caja_obra` hoy: H09 y H10 SIGRID en 16 de 21 obras, H11 en 4.

## 4. La base de la retención de garantía (para el paso 5 de la receta)

Facturas de compra con retención de garantía y con IVA desde 2025: **520 de 526** retienen el 5 %
de la BASE (sin IVA), 1 del total. Además, 4.548 de las 5.074 facturas con retención van con
cuota de IVA 0 (inversión del sujeto pasivo de hecho, aunque la marca sea falsa: H13). En el
lado del cliente no hay dato equivalente (F-040).

## 5. El presupuesto de F-147

Medido en el árbol (v62): reglas 7.431, enrutado 15.000, bloques 8.442: **30.873, el tope
exacto**. El `resumen` de `R-CAJA-HIPOTESIS` mide 230 caracteres. La ficha (`descripcion`) NO
cuenta: solo `codigo + titulo + resumen` de las reglas `resumen`, y las 2 primeras preguntas de
cada ficha recomendada. El resumen propuesto en `design.md` §7 mide 223 (−7).

## 6. Los hallazgos de R25 de F-140 (27-10, obra 0696), medidos en las 21 obras con devengo

- **H12 (IVA de venta).** `raw.obrctr.impiva / impadj` por contrato: 21 % en 5 obras, **0 % en
  13** (IVA sin rellenar, no exento), 10 % en ninguna; 16 de 17 obras con un único valor.
  `ivaide` está en 823 de 970 contratos, pero su catálogo no está ingerido. Sigrid no da el 10 %
  de la vivienda: hoy solo cabe el valor por obra del YAML (D8).
- **H10 (retención del cliente).** Ninguna obra tiene dos porcentajes distintos; **3 obras**
  mezclan contratos al 5 % con contratos sin retención, y los que retienen pesan del **99,5 % al
  100 %** del adjudicado. La regla de F-140 («todos dan valor y el mismo») las deja en DEFECTO 0
  (D9).
- **H15.** Contratos con varios vencimientos: 0 con el cliente, 6 de compra (§3). «No aplica» es
  correcto casi siempre (D10).

## 7. Cierre de la spec (2026-10-27)

El humano pasó la PARADA 1 y cerró D1-D10 en la opción A (`design.md` §9, «Decisiones
cerradas»). D9 y D8 entran en el alcance:

- **D9** (H10 por peso): `importe_adjudicado` nuevo en `tesoreria.condiciones_contrato_cliente`
  (`raw.obrctr.impadj`, ya ingerido), `valor_h10_sigrid` en el dominio y la rama H10 de `08` con
  los mismos literales (R25, R30; T7). Esperado: 3 obras más en OBRA/SIGRID 5.
- **D8** (H12, vivienda al 10 %), con el contenido de la A: (1) `fuente_defecto` de H12 y ejemplo
  de la cabecera del YAML SIN obra real (R27); (2) paso 6 de la receta: si H12 sale DEFECTO, IVA
  implícito = `e / (p × k) − 1` con `e` = efectos COBRO no BAJA de la obra (`tesoreria.efectos`,
  con IVA), `p` = «Venta Real» de `mart.fact_seguimiento_mensual` y `k` = cociente con/sin
  coeficientes de `devengo_pendiente_obra_mes`; >= 17 % `GENERAL`, <= 14 % `REDUCIDO`, entre
  medias `SIN_CONTRASTE` (R28, `contraste_iva_venta` en el dominio); (3) la única excepción en la
  `regla` de `R-VENTA-COEFICIENTES` (R29); (4) la lista de obras de vivienda es MANUAL de Control
  de Costes (R31, T16): ninguna obra se fija sin ella.
- Todo lo que necesita el contraste ya está publicado o lo publica F-150 (`k`): no hace falta
  objeto nuevo.

**Sin medir, y por qué**: el contraste de H12 no se ha medido en Azure: la lectura de solo
lectura que lo hacía fue denegada en esta sesión por el clasificador de permisos. Por eso T11 lo
mide ANTES de escribir la receta (T9) y R32 manda PARAR si las 5 obras con `impiva` al 21 % no
salen `GENERAL`. Riesgos: `k` es el del pendiente, el cobro puede no estar todo en su `obra_id` y
el cobro se retrasa respecto a la producción (`design.md` §8, riesgo 4).

**Para el humano**: el contraste cruza cobro (con coeficientes e IVA) con venta producida (sin
coeficientes) multiplicada por `k`, que es lo que `R-VENTA-COEFICIENTES` prohíbe; por eso la spec
añade una excepción acotada a esa regla (R29). Si prefiere no tocarla, la alternativa es el
contraste por contabilidad (IVA repercutido frente a ventas en `contabilidad.mayor` por obra),
sin medir si los apuntes de IVA llevan obra.

Tamaños: requirements 149/150, design 247/250, tasks T1-T16. F-150 a `spec_ready`; backlog
regenerado; `bash harness/init.sh` en verde (ver el commit).
