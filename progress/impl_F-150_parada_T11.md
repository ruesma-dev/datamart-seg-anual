<!-- progress/impl_F-150_parada_T11.md -->
# F-150 · Informe del implementer · PARADA T11 (R29) del 2026-10-27 (histórico; lo citan la spec como `impl_F-150.md` §1-§3)

Fecha: 2026-10-27 (tarde). Rama `feature/F-150-receta-caja`. **Estado: `blocked` por PARADA de
T11 (R29)**: la verificación en solo lectura se apartó de lo medido en `progress/spec_F-150.md`
§8 en dos puntos, y uno de ellos invalida la gramática de R7. No se ha escrito código ni SQL:
se adelantó la medición de T11 (solo lectura, sin tocar el árbol) precisamente para no gastar
T1-T10 sobre una gramática que no casa con el dato. Lo hecho en el árbol: `git merge main`,
F-150 a `blocked` y este informe.

Todo de SOLO LECTURA: Azure con `main._get_pg()`, `_bootstrap_done = True` y
`filas_solo_lectura` (nocturna del 2026-10-27); Sigrid con `main._get_api().leer_sql`
(`truncated` comprobado en cada lectura: `False` en todas). Solo agregados por obra. Scripts en
el scratchpad de la sesión (no versionados): `t1_sigrid.py`, `t1b_sigrid.py`, `t11a_azure.py`,
`t11b.py`, `t11c.py`, `t11d.py`, `t11e.py`.

## 1. Lo que manda parar

### 1.1 El hueco de facturación (H26) se aparta un 9,5 % de 15,8 M EUR (R29: PARA si > 5 %)

Calculado como `design.md` §5.5: real a origen VENTA hasta el último cierre de cada partida
(`mart.fact_seguimiento_mensual`, la fuente de `real_origen_corte`) × su `coeficiente_venta`
(contrato, si no master 9 en V, si no master 11 en V; sin ninguno, aparte); facturado = Σ
`dvf.totbas` (Sigrid) con `dvf.cenide = obr.cenide`; por contrato dentro de la obra.

| Medida (21 obras) | Medido hoy | §8 (líder) |
|---|---|---|
| Real a origen × coeficiente | **133,27** M EUR | 134,7 |
| Facturado a origen (`dvf.totbas`) | 118,97 | 119,0 |
| **Hueco neto** | **14,30 (−9,5 %)** | 15,8 |
| 0676-B / 0696 (neto) | 4,33 / 2,96 | 5,2 / 3,0 |
| Venta real SIN coeficiente (aparte, R23) | 0,96 | — |
| Σ por contrato de `GREATEST(0, real − facturado)` (`venta_pendiente_facturar`) | 18,59 | — |
| Σ por contrato de lo facturado por delante | 4,29 | — |

Variantes medidas para localizar la diferencia: contando a coeficiente 1 la venta real sin
coeficiente (partidas que la versión V ya no tiene y sin contrato con coeficientes), el neto es
**15,26 (−3,4 %)** y la 0676-B 4,76. La diferencia con el líder está casi entera en la 0676-B y en
qué se hace con lo real sin coeficiente. La gramática de `coestr` no la mueve (14,29 con la de
R7, 14,30 con la medida). **Decisión que hace falta**: si lo real sin coeficiente entra al hueco
(¿a 1?, ¿con el del contrato aunque `coestr` esté vacío?) o se queda aparte como dice R23.

Por obra (M EUR: real × coef | facturado | neto | pendiente de facturar por contrato | por delante):
0676-B 22,33 | 18,01 | 4,33 | 7,55 | 3,23 · 0678 8,35 | 7,04 | 1,31 | 1,42 | 0,10 ·
0686 33,29 | 32,25 | 1,03 | 1,10 | 0,07 · 0693 9,18 | 8,74 | 0,44 | 0,46 | 0,02 ·
0694 2,40 | 1,89 | 0,51 | 0,51 | 0,01 · 0696 28,84 | 25,88 | 2,96 | 2,96 | 0 ·
0697 0,96 | 0,50 | 0,46 | 0,46 | 0 · 0699 0,32 | 0,39 | −0,07 | 0 | 0,07 ·
0702 4,74 | 3,45 | 1,29 | 1,60 | 0,31 · 0704 5,87 | 5,87 | 0 | 0 | 0 ·
0707 3,40 | 3,15 | 0,25 | 0,25 | 0 · 0710 4,32 | 3,53 | 0,79 | 0,79 | 0 ·
0711 0,86 | 0,95 | −0,10 | 0,01 | 0,11 · 0713 4,57 | 3,74 | 0,83 | 1,21 | 0,38 ·
0719 1,01 | 0,88 | 0,13 | 0,13 | 0 · 0720 0,54 | 0,52 | 0,01 | 0,01 | 0 ·
0723 0,67 | 0,61 | 0,06 | 0,06 | 0 · 0724 0,54 | 0,47 | 0,07 | 0,07 | 0 ·
0690 1,10 | 1,10 | 0 | 0 | 0 · 0608 y 0715 sin real de venta.

### 1.2 La gramática de `coestr` de R7 no casa con el dato real

§8 citaba las formas como `COEF_RECGG|Gastos Generales|13|| COEF_RECBI|Beneficio Industrial|6||`.
El dato real (`raw.obrctr.coestr`, Azure) es **una LÍNEA por concepto, separadas por `\r\n`**, y
cada línea tiene CINCO campos: `CODIGO|etiqueta|valor||base`, donde `base` es el rótulo del
subtotal (vacío o `TOTAL EJECUCION CONTRATA`, `TOTAL ADJUDICACIÓN`...). Ejemplo literal:
`COEF_RECGG|Gastos Generales|13||\r\nCOEF_RECBI|Beneficio Industrial|6||TOTAL EJECUCION CONTRATA\r\n`.

Con la gramática de R7 tal cual (segmentos por `||`, campos por `|`, % = último campo no vacío):

- El tercer «segmento» de esa forma es `TOTAL EJECUCION CONTRATA\r\n`: no acaba en número y la
  fila entera queda NO reconocida. En las 21 obras: **3 contratos, 1.071 partidas VENTA, 6,85 M EUR
  de pendiente** que caerían al master en vez de al contrato.
- El código del segundo segmento llega como `\r\nCOEF_RECBI`: sin recortar, el 6 % del BI iría a
  `coeficiente_otros` y no a `coeficiente_bi` (el factor sale igual; el desglose publicado, no).
- `design.md` §4 pide que `...Gastos Generales+Beneficio Industrial|23.79` dé `otros`, pero su
  código es `COEF_RECGG`, y R7 lo manda a `gg`. R7 y el test previsto se contradicen.

Fuera de las 21 obras, pero publicado en `condiciones_contrato_cliente` para los 970 contratos:

- **Retenciones dentro de `coestr`**: `RETN|Retención garantía N% (sobre base imponible)|N||` en
  35 contratos, `RETESP` en 5 y `RETNT` en 1. Con R7 («el resto -> otros, sumados») una retención
  del 5 % se sumaría al coeficiente como +5 %.
- **La baja de adjudicación va en cascada**: `COEF_DESADJ|Coeficiente (Baja) de Adjudicación|-12.77||TOTAL ADJUDICACIÓN`
  detrás de GG+BI con base `TOTAL EJECUCIÓN POR CONTRATA` (8 contratos; valores −4, −10,4,
  −12,77, −19,17, −19,93, −35). El rótulo de base indica que se aplica sobre el subtotal de
  contrata, no sobre el PEM: 1,19 × (1 − 0,1277) = 1,0380 frente a 1 + (19 − 12,77)/100 = 1,0623
  sumando (R7). Solo 1 de esas 8 etiquetas contiene `BAJA`; el resto («Coeficiente de
  Adjudicación») iría a `otros`. También aparecen `COEF_RECCC` (control de calidad) y
  `COEF_RECSYS` (seguridad y salud).

Formas en los contratos de las partidas VENTA de las 21 obras (partidas): GG 13 + BI 6, 7.015;
`NULL`, 6.671; vacío, 1.617; GG + BI con `TOTAL EJECUCION CONTRATA`, 1.071; `GG+BI|23.79`, 972;
solo BI 6, 7; `COEF_RECBI|Mortero|7`, 4. Valores: GG 13/20/3,5, BI 6/3,5, 23,79, 7.

**Decisión que hace falta**: la gramática (líneas por salto de línea; código = campo 1, valor =
campo 3; ¿qué hacer con `RET*`: ignorar o no reconocido?; ¿`COEF_DESADJ` sumado o en cascada sobre
el subtotal de su rótulo?; ¿`COEF_RECCC`/`COEF_RECSYS` a `otros`?) y si `coestr` vacío o `NULL`
es «contrato sin coeficientes» (factor 1) o «sin dato» (cae al master, R7 hoy).

## 2. Lo que SÍ casa con §8

| Hecho (21 obras, VENTA) | Medido hoy | §8 |
|---|---|---|
| Partidas / pendiente | 18.997 / 132,43 M EUR | 18.997 / 132,37 |
| Partidas con contrato de otra obra | **0** | 0 |
| Partidas sin contrato (`ctride` 0) | 1.640 (24,08 M EUR) | — |
| Pendiente con coeficientes (contrato > 9 > 11) | 143,28 M EUR | ~143,20 |
| Fuentes del pendiente (gramática por líneas) | CONTRATO 54,71 · MASTER_CERT 76,96 · MASTER_VENTA 0,76 · SIN 0 | — |
| Contrato ≠ master 11 en > 0,005, con pendiente > 0 | **5** (0676-B 1, 0696 3, 0724 1) | 6 (+0697 1) |
| Ídem, contando partidas con pendiente 0 | 11 (0676-B 7: contrato 1,2379, master 1,000) | — |
| Ponderado por obra, a 4 decimales | igual en 6 de 9 obras; distinto en 0676-B (1,2147/1,2156), 0696 (1,1879/1,1881), 0724 (1,1892/1,1900) | igual salvo esas partidas |
| Contrato ≠ master a 4 decimales, partida a partida | 170 (redondeo del `importe_oficial` por partida) | — |
| IVA y retención del contrato | ≥ 96 % del pendiente en 19 obras; 0608 y 0715, 0 % | ídem |
| H12 de la ficha (`obr.ivaide`) | 0 % en 14 obras; 21 % en 0690, 0697, 0699; sin dato en 0608, 0715, 0719, 0724 | — |
| Albaranes sin facturar (`compras.v_pbi_albaranes_sin_facturar`) | 56,88 M EUR (≤1 mes 9,26; 1-2 5,79; 2-6 18,95; 6-12 14,49; >12 8,39) | 56,9 (9,3; 5,8; 18,9; 14,5; 8,4) |
| Ídem, de más de 6 meses (lo que H27 apartaría) | 22,88 (22,75 por mes de albarán) | 22,9 |

El coeficiente, pues, pasa R29 con la medida del líder (> 0,005 y pendiente > 0: 5 ≤ 6). **Aviso
sobre R30**: «`CONTRATO` en ≥ 96 % del pendiente de 19 obras» solo se cumple para el IVA y la
retención; el COEFICIENTE del contrato cubre 9 obras, porque en 10 el contrato tiene `coestr`
vacío o `NULL` (8.288 partidas, 53,64 M EUR). Con la decisión de §1.2 sobre el vacío cambia.

## 3. T1 (medido en Sigrid, solo lectura; sin código aún)

- **`iva`**: 1.562 filas, 30 columnas, sin `tiemod` (-> `incremental_column: null`), sin texto
  pesado (entera, `exclude_columns: []`). `iva` es `float` en tanto por uno (0, 0,04, 0,07, 0,10,
  0,16, 0,21; IGIC 0,02-0,13): × 100 da el porcentaje, como prevé R18.
- **`dvf`**: **151 columnas** (no ~330), 15.665 filas (= `con.tip = 11`), **sin `tiemod`**. Existen
  las 9 de `include_columns` (`ide`, `cla`, `entide`, `cenide`, `ctride`, `fecdoc`, `totbas`,
  `totiva`, `totdoc`; importes `float`). `cla`: 0 (7.374), 1000 (2), 1001 (7.952), 1023 (1) y
  **1024 = rectificativas** (336, series `R/`, 330 en negativo, 19 con `facoriide`): sumar
  `totbas` ya las neta. **No hay marca de anulada** (`estfac` = 0 en todas). Cobertura: `cenide`
  > 0 en 12.183, `ctride` > 0 en 4.665 (todas a un contrato existente; 4.654 de su misma obra).
  **`dvf` tiene `obride`** (obra directa, 12.212 filas): coincide con `obr.cenide` en 11.853 y
  difiere en 77; el diseño enlaza por `cenide` (lo que midió el líder) y así se ha medido aquí.

## 4. Lo que queda sin hacer

T1 (código), T2-T10 y T12-T16: nada escrito, a la espera de la nueva propuesta. No hay fase
RED, cobertura ni mutación que declarar porque no hay código; el portero (`bash harness/init.sh`)
se ejecutó al empezar (resultado abajo).

## Evidencias

- `bash harness/init.sh` al empezar (antes del merge): **verde** (9.340 passed, 268 skipped en 4.991,96 s; PUERTA COBERTURA N/A, F-150 sin líneas Python de producción; PUERTA TAMAÑO dentro de los topes; «ENTORNO LISTO»).
- Tests: no hay tests nuevos (no hay código). Cobertura de líneas cambiadas, mutantes y tiempo de
  suite de F-150: **N/A por la PARADA** (no hay código de la feature que medir).
