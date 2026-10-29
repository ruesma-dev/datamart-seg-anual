<!-- progress/spec_F-150.md -->
# F-150 · Informe del spec-author (la receta de la caja, fase 1)

Fecha: 2026-10-26; **rehecha el 2026-10-27 por la tarde (§8)**: §6 y §7 quedan como historia. Rama `feature/F-150-receta-caja` desde `main` (`6681de8`). Spec en
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

## 7. Cierre de la spec (2026-10-27, mañana) · SUSTITUIDO por §8

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

## 8. La spec rehecha (2026-10-27, tarde): el contrato de cada partida

**Por qué.** Juan Romero (Dir. Admon y Control de Costes) contestó el 27-10 (transcripción
prevista en `docs/referencia/06_correos_coeficientes_iva_caja.md`, aún no en `main` ni en esta
rama: el resumen vino en el encargo del líder). Lo que cambia el diseño: en VENTA se trabaja sin
coeficientes y «cada contrato tiene sus coeficientes» (13 % GG + 6 % BI lo normal; baja en obra
pública; órdenes de cambio y contradictorios con otros, incluso dentro de un capítulo; la
revisión de precios, a menudo fuera); el master de certificación (9) «no es un referente» en fase
0; el IVA de la ficha es fiable, pero hay tipos mezclados en una obra; la liquidación del IVA y
el IVA soportado son de AdP.

**Lo medido por el líder** (solo lectura, 21 obras con devengo; scripts `coef_contrato.py` e
`iva_contrato.py` en su scratchpad; este spec-author NO ha leído Azure ni Sigrid):

| Hecho | Medido |
|---|---|
| Enlace partida -> contrato | `raw.obrparpar.ctride` -> `raw.obrctr.ide` (ya ingerido): 96-100 % del pendiente de venta en 19 obras; 0608 y 0715, ninguna partida con contrato |
| Coeficiente del contrato | 1 + Σ porcentajes de `raw.obrctr.coestr` (formas abajo); se SUMAN, no se multiplican |
| Contra el master (11, versión V) | ponderado por obra, igual a 4 decimales; 6 partidas difieren > 0,005 (0676-B 1, 0696 3, 0697 1, 0724 1) |
| IVA del contrato | `obrctr.ivaide` -> catálogo `iva` de Sigrid (`iva` en fracción, NO ingerido): igual al IVA efectivo de `cer` y `dvf` por `ctride` en TODOS los contratos, también los mixtos (0678 CONT_CATAS 21 %, 0686 ACOMETIDAS 21 %, seis casetas de la 0696 al 21 % frente a sus principales al 0 %) |
| IVA de la ficha | `obr.ivaide` coincide a nivel obra; `obrctr.tex` (no ingerido) dice «INVERSION SUJETO PASIVO» en 6 contratos principales |
| Retención del cliente | `obrctr.coegar` por contrato: 5 % casi siempre; 3 % en 0713, 2,5 % en 0723 |

Formas de `coestr` vistas: `COEF_RECGG|Gastos Generales|13|| COEF_RECBI|Beneficio Industrial|6||`,
una con `TOTAL EJECUCION CONTRATA` y `Gastos Generales+Beneficio Industrial|23.79`.

**Decisiones nuevas (PARADA 1 pendiente; `design.md` §9; N6 y N7 abajo)**: N1 coeficiente: contrato, si no
master 9, si no master 11 (sustituye a D2); N2 IVA del contrato y H12 = MANUAL > ficha > 21 % solo para la
base sin él (sustituye a D8; fuera contraste, excepción de `R-VENTA-COEFICIENTES`, R32 y T16
viejas); N3 retención del contrato y H10 de F-140 para el resto (sustituye a D9; fuera
`importe_adjudicado`); N4 la obra-mes lleva `importe_iva_contrato`, `importe_retencion_contrato`
y las bases `SIN`; N5 avisos (revisión de precios a F-040; H13/H14 con AdP). H09 sigue por obra.

**Decisión de diseño propia, a validar dentro de N2**: el valor MANUAL de Control de Costes para
H12 NO pisa el IVA del contrato de la partida, solo cubre la base sin él (aplanar una obra mixta
rompería las casetas al 21 % de la 0696). Igual con H10. Así el SQL no aplica ninguna hipótesis
(R13): el contrato es dato; H10 y H12, hipótesis que la IA aplica a la base `SIN`.

**Decisiones del humano añadidas el mismo día (vía líder)**: H26 «venta ejecutada pendiente de
facturar» (opción A; medido por el líder: real a origen × coeficiente 134,7 M EUR, facturado a
origen `dvf.totbas` 119,0, hueco 15,8 M EUR, 0676-B 5,2 y 0696 3,0; negativo en alguna obra por
facturar por delante): solo la CABECERA de `dvf` (enlace `dvf.cenide = obr.cenide`), mínimo 0 y lo
negativo declarado; líneas, certificaciones y casado por mes, F-040. H24/H25 son el
FRACCIONAMIENTO de cada pago y cobro. H14 por defecto MENSUAL (día 20 del mes siguiente; AdP). H21
casa por fecha de emisión y puede restar dos veces una certificación de un mes cerrado facturada
después: hoy 0 en cobros, se declara como riesgo y va a F-040. H13 por contrato de compra: N7,
recomendada pero aplazada (el devengo de coste no va por contrato de compra; falta ese enlace).

**Albaranes sin facturar (N8, medido por el líder el 27-10, solo lectura)**: sobre 239 M EUR
facturados con albarán de origen (`compras.factura_lineas.albaran_id`, albaranes 2024-01 a
2026-06, el 85 % de lo facturado), la factura del proveedor lleva fecha del MISMO mes que el
albarán en el 93 % (7 % el siguiente; proformas 94/6); el alta en Sigrid, 64 % el mismo mes, 35 %
el siguiente. Pendiente hoy en las 21 obras (`compras.v_pbi_albaranes_sin_facturar`): 56,9 M EUR
(≤1 mes 9,3; 1-2 meses 5,8; 2-6 meses 18,9; 6-12 meses 14,5; >12 meses 8,4; la 0696, 10,1, de
ellos 5,2 de más de 6 meses). En toda la base, 201,8 M EUR de más de 12 meses: sobre todo albarán
sin enlazar con su factura (`docoritip` cubre el 32,5 % de las líneas), no deuda. **De dónde salían
los 8,23 M EUR de H20**: de `progress/spec_F-140.md` §6, medidos sobre
`compras.fact_compras_linea.importe_pendiente_facturar` (otro objeto: la línea de albarán vista
desde el hecho de compras, con su propio universo), no sobre la vista de albaranes sin facturar;
no reproduzco aquí el porqué exacto de la diferencia (no leo Azure): T11 lo contrasta. Diseño: H20
`FIN_MES_ALBARAN` (la factura a fin del mes del albarán y el plazo desde ahí) y H27 nueva
(`MESES`, 6: lo más antiguo se excluye y se declara, como H17; más simple que una segunda unidad
en H20).

**Decisiones de diseño propias de este añadido (en N6)**: el hueco se calcula por contrato dentro
de la obra (partidas por su contrato, facturas por `dvf.ctride`, un grupo sin contrato) para dar
el IVA y la retención de cada contrato; y la ingesta gana `include_columns` (lista blanca) porque
el ingestor solo sabía excluir y `dvf` tiene ~330 columnas en `sigrid_tablas.md`.

**Requisitos.** La spec se renumeró entera (R1-R32, en lista): no hay correspondencia uno a uno
con la del 27-10 por la mañana, que queda en el historial de git (`3e19f39`). Retirados: H10 por
peso, contraste de H12 y su excepción, lista de vivienda. Tareas: T1-T2 ingesta (`include_columns`,
`iva`, `dvf`), T5 dominio del contrato y del hueco, T10 H12 SIGRID, T11 verificación en solo
lectura de N1-N3 y del hueco ANTES de la receta (T12), con PARADA (R29).

**Sin medir, y por qué**: la gramática de `coestr` solo se conoce por las tres formas citadas; T11
lista las reales con el parser del dominio y R29 para si el contraste se aparta de lo medido. Las
columnas de `iva` y `dvf` salen de `azure-apps/sigrid_tablas.md`; T1 las mide en Sigrid (y `cla`
de `dvf`: si hay anuladas, el hueco cambia).

Tamaños: requirements 146/150, design 250/250, tasks T1-T16. F-150 en `spec_ready` (acceptance y
`notes` al día); backlog regenerado por `bash harness/init.sh` (ver el commit).

## 9. Ajuste tras la PARADA de T11 (2026-10-28; aprobado por el humano el 27-10)

El implementer paró en T11 (`progress/impl_F-150.md` §1): el hueco de H26 salía 14,30 M EUR
(−9,5 % frente a 15,8) y la gramática de `coestr` de R7 no casaba con el dato. El humano aprobó:

- **N9 · Hueco NETO POR OBRA** (R22, R23, `design.md` §5.5). Real a origen × coeficiente −
  `dvf.totbas`, suelo 0 por obra y lo negativo declarado; nunca por contrato (solo 4.665 de 15.665
  facturas llevan `ctride`; el casado por contrato lo infla a 18,59). La venta real sin ningún
  coeficiente (0,96 M EUR) entra con la media ponderada de su obra (`MEDIA_OBRA`, declarada en
  `venta_real_media_obra`); IVA y retención del hueco, por el peso de cada contrato en la venta
  real × coef de la obra. **R29 se recalcula** sobre esta definición: Σ neto de las 21 obras entre
  15,26 (todo a factor 1, lo medido) y 15,55 M EUR (0,96 a una media ≤ 1,26).
- **N10 · Gramática real de `coestr`** (R7, R8, `design.md` §4 y §5.2): líneas por `\r\n`,
  `CODIGO|etiqueta|valor||base`, clase POR CÓDIGO (`COEF_RECGG` gg, también la combinada 23,79, que
  conserva su etiqueta en `coeficientes_texto`; `COEF_RECBI` bi; `COEF_RECCC`/`COEF_RECSYS` otros;
  `COEF_DESADJ` baja EN CASCADA: (1 + gg + bi + otros) × (1 + baja), 1,19 × 0,8723 = 1,038;
  `RETN`/`RETESP`/`RETNT` -> `retencion_coestr`, dato aparte que no suma). Vacío o NULL = sin dato
  (al master); código desconocido, al master y declarado. Corrige la contradicción de §4 con R7.
- **R30** sin umbral de cobertura del coeficiente del contrato (cubre 9 obras; en 10, `coestr`
  vacío o NULL): cada coeficiente con su fuente; el ≥ 96 % queda para IVA y retención.
- **T1 medido** (`impl_F-150.md` §3) llevado al diseño: `dvf` 151 columnas, sin `tiemod`, `cla`
  1024 rectificativas ya netas en `totbas`, sin marca de anulada; `iva` 1.562 filas, sin `tiemod`.

Tamaños: requirements 148/150, design 249/250, tasks T1-T16. F-150 de `blocked` a `spec_ready`.

## 10. Ajuste del 29-10: albaranes netos (N11), CP fuera (N12), personal (N13), saldo de partida (N14)

Aprobado por el humano el 29-10 (vía líder), con F-150 ya desplegada (`r20261029-1340`). Todo
medido en SOLO LECTURA en Azure (`_bootstrap_done = True`, `filas_solo_lectura`; nocturna del
29-10, PostgreSQL 16.15). Universo: las 21 obras de `tesoreria.devengo_corte_obra` (COSTE = VENTA).

### 10.1 · N11, los albaranes pendientes de facturar

| Medida (21 obras, ALBARAN + PROFORMA) | M EUR |
|---|---|
| Líneas > 0 (lo que suma la vista) / líneas < 0 | 56,88 / −48,17 (30.533 líneas) |
| Neto por obra / por (obra, proveedor) con suelo 0 / residuo negativo | 8,71 / **8,76** / −0,05 (20 pares) |
| Neto por (obra, proveedor, serie) | 8,79 (compensar entre `AC` y `PROF` cambia 0,03) |
| Por tipo: ALBARAN / PROFORMA / NOTA | +55,52 −48,09 / +1,36 −0,07 / 0 líneas con pendiente |
| Desde `raw.dca`/`dcapro`/`con` con la fórmula de `compras/01` copiada | idéntico (56,88 / −48,17 / 30.533) |
| Neto con contrato de compra | 5,49 de 8,76; 2 pares con más de un contrato |
| Filas de la tabla (obra, proveedor, contrato, mes) con neto > 0 | 638 (630 sin contrato en el grano) |

Por antigüedad (meses hasta 2026-10), bruto / FIFO / LIFO: ≤1 mes 9,37 / **7,96** / 2,69; 1-2
5,85 / 0,06 / 0,54; 2-6 18,92 / 0,22 / 3,01; 6-12 14,38 / 0,31 / 1,74; >12 8,37 / 0,21 / 0,78.
**Más de 6 meses con FIFO: 0,52 M EUR** (bruto 22,75; LIFO 2,51). Las negativas están repartidas
por edades como las positivas (6,52 / 5,30 / 16,36 / 13,54 / 6,44). FIFO deja el neto en sept.
(5,28) y oct. (2,68): coherente con el 93 % de facturas del mes del albarán (N8); LIFO lo dejaría
viejo. Neto con mes posterior al último cierre de la obra (`tras_cierre`): **0,47 M EUR en 7
obras** (cierres: 12 obras en 2026-10, 6 en 2026-09, una en 2026-06, una en 2025-12, una sin real).
**0686**: vista 8,78; neto 0,19; de más de 6 meses 0,01.

**Hallazgo**: las líneas 588705 y 588733 de `R-ALBARAN-ABSURDO` ya NO están en `raw.dcapro`
(máximo |`tot`| de toda la base: 1,09 M EUR). El filtro `< 1e8` se queda; la ficha de la vista aún
dice «68,7 billones» y la regla sigue: retirarla es trabajo aparte (para el humano).

**Decisiones** (`design.md` §5.7 y §9): objeto `tesoreria.albaranes_pendientes_neto`, grano
(obra, proveedor, contrato, mes) con `NULLS NOT DISTINCT` (precedente `retenciones.saldo_contable`);
FIFO; solo `AC`/`PROF`; lee `raw` (`compras` se construye DESPUÉS de `tesoreria` en `run-all`:
leerla daría el pendiente de la víspera y no casaría con `compras.albaran_lineas`); `tras_cierre`
porque la propia H20 define los albaranes como «ejecutado que no es devengo pendiente»; sin
contrato, H02 `OTRO` (la vista tampoco traía categoría). `meses_antiguedad` contra el mes del build
(como `dias_desde_albaran` de la vista). La ficha nueva es recomendada: `PRESUPUESTO_MAX` sube lo
que mida (alternativa: no recomendada y sin subida; el aviso en la ficha de la vista basta a medias).

### 10.2 · N12, el coste proporcional

Devengo pendiente de COSTE por categoría (21 obras): CD 106,12, CI 12,83, **CP 14,48 M EUR (18
obras, 246 partidas; 10,9 %)**, OTRO 0; 0686: CP 0,26. Partidas CP: COSTES ESTRUCTURA EMPRESA
11,58, LEVANTAMIENTO 1,91, COSTES ESTRUCTURA DELEGACIÓN 0,34, SEGURO T.R.C. 0,19 (LEVANTAMIENTO y
el seguro TRC quizá sean pagos de la obra: para que lo mire el humano; aquí sale todo el CP). En el
devengo basta la receta y `categoria` (ya publicada): una marca la duplicaría. H02 pierde `CP`.

**La cartera** (pagos PREVISTO vivos de las 21 obras: 38,56 M EUR, 4.666 efectos; 0686: 5,76):
- la cuenta del efecto es la del PROVEEDOR (410 30,56; 400 7,74; 414; 418): no dice el gasto;
- por nombre de aseguradora o banco: 0 en la cartera viva; en toda la base, 13 efectos REALIZADO
  con obra (0,06): los seguros y avales casi nunca llevan obra; «AVAL/PRIMA/COMISI» en el
  concepto: falsos positivos (SAVAL, SAVALL);
- por la categoría de las partidas de la FACTURA del efecto (`raw.dcfpro.paride` -> `categoria`):
  **0,03 M EUR** en la cartera viva (con algo de CP: 0,03; prorrateado, ~0); REALIZADO, 0,55 con
  algo de CP. 78 efectos (0,58) sin factura: no se pueden clasificar.
Elegido: la cuota CP de cada efecto por las partidas de su factura (mismo criterio que el devengo),
publicada en dos columnas de `devengo_corte_obra` COSTE (`design.md` §5.8). Hoy pesa ~0, pero deja
la regla escrita para F-154 y para la obra que sí impute seguros.

### 10.3 · N13, el personal

Solo textos (receta, `regla`, fichas de `efectos` y `efectos_restringidos_mes`). **N13-b (plazo del
personal) lo decidió el líder** por la prisa del humano (opción D): sin hipótesis nueva, H02 `CI` y
un aviso. Opciones que había: A H02 tal cual; B bajar el defecto de CI (mezcla personal y
alquileres); C H28 + lista manual de partidas de personal + marca en el devengo (cambia el grano
de `devengo_pendiente_obra_mes`); D aviso. Medido: por NOMBRE de partida (JEFE DE OBRA, ENCARGADO,
GRUISTA, CAPATAZ, PEÓN, OFICIAL...), 202 partidas CI en 21 obras, **6,03 de 12,83 M EUR de CI**
pendiente; los códigos no son estándar (`CI.1.2` y `CI.0.02` para JEFE DE OBRA) y `descompuestos`
no da naturaleza a esas partidas. En la 0686 el nombre falla: 0,02 de 34,81 M EUR de coste real.

### 10.4 · N14, el saldo de partida (SEGUNDA TANDA, no bloquea N11-N13)

Medido: efectos REALIZADO (no BAJA) de las 21 obras: COBRO 97,35 M EUR (258), PAGO 66,21 (5.514);
**0686: cobrado 30,21, pagado 22,28**. AGR en toda la cartera: REALIZADO con obra 157,01 (8.365) y
SIN obra **108,72 (11.288)**; PREVISTO sin obra 2,25 (294). `raw.pag.padide` NO enlaza el AGR con
sus efectos de origen (0 hijos): falta el campo (T28). Coste real a origen hasta el cierre: 134,22 M
EUR (CP 13,32; personal por nombre 6,90); 0686, 34,81 (personal por nombre 0,02).
**Preguntas abiertas para el humano**: (1) ¿el saldo de partida con o sin IVA? (los efectos van
CON IVA y el devengo sin él; el IVA se liquida por empresa); (2) ¿cómo se identifica el coste real
de personal histórico (lista de partidas, `personal.partes` y sus costes, o la contabilidad)?;
(3) ¿de dónde sale el enlace AGR -> efectos de origen que usó el líder en la 0686 (64 efectos,
271.733 EUR)?; (4) ¿las retenciones pendientes se restan del pagado y del cobrado, o se publican
aparte? Tareas T27-T30 en `tasks.md`.

Tamaños: requirements 150/150, design 249/250 (§3, §4, §5.1-§5.2 y §8 resumidos y enlazados: el
texto completo de la receta vive ya en la ficha), tasks T1-T30. Rama `feature/F-150-receta-caja`
avanzada a `main` (`935fdd3`, fast-forward).

### 10.5 · N14 cerrada con las respuestas del humano (29-10)

1. **IVA**: el saldo va CON IVA (los efectos lo llevan). Y es OPCIONAL: H28 `[CON_SALDO, SIN_SALDO]`
   (defecto `CON_SALDO`); sin saldo, la proyección parte de hoy con la cartera vencida y no pagada.
2. **Personal histórico** (Sigrid, solo lectura, `truncated` falso): no hay tabla de histórico de
   coste por recurso, pero NO hace falta: cada línea de parte (`hmores`) guarda su `pre` y su `tot`
   del momento. En los partes ingeridos el precio medio por recurso y año VARÍA en 458 de 545
   recursos con más de un año. 0686 en Sigrid: 4.986 líneas, 2.295.755 EUR (fechas 2024-03 a
   2026-10), igual que `raw.hmores`. Recursos PERSONA internos (`personal.recursos`): 21 obras
   11,67 M EUR (11,55 hasta el último cierre); 0686 2,13 (2,07 hasta su cierre, 2026-09); los
   CONSUMO, 0,77, no son personal. **Decisión del líder**: `personal_coste_partes` = Σ `tot` de
   PERSONA interna hasta el último cierre (lo de después ya es devengo pendiente: no se cuenta dos
   veces); se da por pagado en su mes. Descartado: recurso actual × horas (pierde el histórico) y
   el real de los cierres por nombre de partida (en la 0686 solo encuentra 0,02).
3. **AGR**: por los ORIGINALES (`sentido = 'PAGO'`, `estado_tesoreria = 'BAJA'`, `estado_codigo
   = 14`, «Agrupados»; 56.503 en toda la cartera, 99,33 M EUR). 21 obras: vencidos (< 29-10)
   **8,63 M EUR** (3.498, 21 obras), pendientes **2,21** (796, 18 obras); **0686: 1.315.128,62 y
   271.733,31 (64 efectos)**, lo mismo que midió la conversación. Riesgo de doble conteo: los AGR
   que CONSERVAN la obra están ya en la cartera de la obra (REALIZADO 2,22, PREVISTO 0,58; 0686
   0,32 y 0,12): con `ORIGINALES` se dejan fuera. Validación por proveedor (aproximada: un AGR
   mezcla obras): de los 2,21 pendientes, 1,48 tienen AGR PREVISTO sin obra del mismo tercero que
   los cubre y 0,59 son de proveedores sin ningún AGR previsto (quizá ya pagados: caso 0722
   ERCALUM); se declara. H29 `[ORIGINALES, AGR]`, defecto `ORIGINALES`, HIPÓTESIS.
4. **Retenciones**: efectos propios de la factura; el saldo = efectos REALIZADO (sin las pendientes,
   que van en la proyección como hoy). No hace falta columna.

**Saldo medido con los defectos** (H28 `CON_SALDO`, H29 `ORIGINALES`, CP ~0): 21 obras ≈ 97,35 −
63,99 − 8,63 − 11,55 = **13,18 M EUR**; 0686 ≈ 30,21 − 21,96 − 1,32 − 2,07 = **4,86 M EUR**.
Diseño en `design.md` §5.9 (`tesoreria.saldo_partida_obra`, `10_saldo_partida.sql`, paso SALDO
delante de los siete, H28 y H29: 29 hipótesis); requisitos R38-R40; tareas T27-T31 (segunda
tanda, tras T26). Tamaños: requirements 150/150, design 248/250 (§5.3-§5.6 resumidos: hechos).
