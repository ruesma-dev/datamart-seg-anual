<!-- progress/spec_F-140.md -->
# F-140 · Informe del spec-author (fase 2 de la cartera: los ingredientes)

Fecha: 2026-10-24. Rama `feature/F-140-proyeccion-caja-ingredientes` desde `main` (`7086e04`).
Spec en `specs/F-140-proyeccion-caja-ingredientes/`. Decisiones abiertas en `design.md` §9.
**Rehecha el 2026-10-24** con las indicaciones del humano (criterio de caja, lista de hipótesis con
valores por defecto y por obra, descuento de lo ejecutado desde la versión): §5-§7 son nuevas.

Todas las cifras salen de lecturas de SOLO LECTURA: Azure con `main._get_pg()`,
`_bootstrap_done = True` y `filas_solo_lectura` (nocturna del 2026-10-24), y Sigrid con
`main._get_api().leer_sql` (solo `auxcob`, `auxefc` y el recuento de `pag.padide`/`cob.padide`).
Solo agregados: ni nombres, ni NIF, ni importes de un proveedor concreto.

## 1. Qué está ingerido (primera aceptación)

| Tabla | En `raw` | Filas | Lo que aporta | Lo que NO trae |
|---|---|---|---|---|
| `auxpag` (formas de PAGO) | sí (F-066) | 70, 0 de baja | `formul` (25 fórmulas distintas), `efeide` → medio | `can`, `cat`, `reccod`, `ser`: vacíos en las 70 |
| `auxefp` (medios de pago) | sí | 10 | `res` (CHEQUE, PAGARÉ, CONFIRMING...), `cla` | `pagdia`, `pagmes`, `pagdiad` vacíos en los 10 |
| `ctrrec` (recargos del contrato) | sí | 6.419 (6.410 contratos) | `recide`, `valpor` (tanto por uno), `reccla` | ningún plazo: `rec.diavto = -99` en todas las retenciones |
| `rec` (catálogo de recargos) | sí | 2.177 | `cla`, `valpor`, `diavto`, `tipcyp` | — |
| `ctr.pagide` / `pagfor` | sí | 19.161 / 19.161 de 19.170 | la forma pactada; `pagfor` = `auxpag.formul` en 19.151 | `diapag` vacío en los 19.170 |
| `prv.pagdia` / `pagmes` | sí | 2.919 / 2.223 de 9.638 | días fijos de pago («15», «15,30») y meses sin pago («8,12») | — |
| `obrctr` (contrato con el CLIENTE) | sí | 970 (450 obras) | `pagide` 705 (forma de COBRO), `retide` 517, `coegar` 500, `plaret` 184, `plagar` 223, `fecinigar` | `cobmeses`, `cobporret`: 0 en todas |
| `auxcob` (formas de COBRO) | **NO** | 52 en Sigrid, 0 de baja | `formul` con la misma gramática («90 365R») | — |
| `auxefc` (medios de cobro) | **NO** | 8 en Sigrid | el medio de `auxcob.efeide` | — |

**La fórmula de plazo SÍ se puede leer, y está medida contra los efectos.** Gramática de las 70 +
52 fórmulas: tokens separados por blancos, `N` = días de un vencimiento, `NR` = días del efecto de
RETENCIÓN (`30 60 90` son tres vencimientos; `120 450R`, 120 días y la retención a 450; un caso
con doble blanco, `90  450R`). Las 122 casan con esa gramática. Contraste (efectos no BAJA de
facturas desde 2023, días entre `dcf.fecdoc` y el vencimiento, p10/p50/p90):

| Fórmula | Efecto normal | Efecto de retención |
|---|---|---|
| `0` | 2 / 14 / 45 (10.799) | — |
| `30` | 30 / 37 / 59 (3.205) | — |
| `90` | 97 / 107 / 137 (2.232) | — |
| `120` | 126 / 137 / 168 (6.460) | — |
| `120 450R` | 130 / 142 / 175 (2.167) | 455 / 457 / 468 (1.845) |
| `150 450R` | 157 / 172 / 202 (6.568) | 455 / 457 / 463 (4.294) |
| `90 450R` | 100 / 112 / 168 (294) | 455 / 458 / 468 (228) |

El plazo real se alarga 7-22 días sobre el nominal (días fijos de pago del proveedor y fecha de
cómputo), y eso es una HIPÓTESIS que la IA tiene que declarar, no una corrección del ETL.

**Retención de garantía en el contrato de compra.** Por clase de recargo 4/5 (criterio de F-128):
6.358 contratos; por código `RET%` (criterio de F-067, `compras.contratos`): 6.360 (la diferencia es
`RETESP`, clase 1). Porcentaje: 5 % en 6.304, 2,5 % en 13, 10 % en 5, resto residual. Cruce con la
fórmula: con `R` y con retención 6.092; `R` sin retención 555; retención sin `R` 267; ninguna 12.247.
Ningún contrato tiene un tercero empleado (`con.tip = 43`): 0.

**El plazo de devolución de la retención tiene DOS fuentes que no dicen lo mismo:** Sigrid, en la
fórmula (`450R`, días desde la factura, confirmado en los efectos), y el criterio de Negocio ya
publicado en `retenciones.fin_obra` (fin de obra + `plaret` → `plagar` → 12 meses, decisión del
2026-09-22, F-110). Las dos son ingredientes; elegir una es hipótesis.

## 2. Qué versión de `stg.plan_mensual` vale para proyectar (`R-VERSION-MASTER`)

`mart.fact_seguimiento_mensual` ya resuelve la vigente mes a mes (`sql/mart/02_build_fact.sql`): la
de fecha efectiva más reciente anterior al mes siguiente, solo `Planif Inicial`, `ABC` o
`Cuatrimestral`. Para los meses futuros eso es la ÚLTIMA vigente de la obra, y es UNA sola: 0
obras con dos versiones en sus meses pendientes. Se lee de `mart`, nunca de `stg` sin versión.

Devengo pendiente = meses planificados POSTERIORES al último cierre real del mismo concepto:

| Concepto | Obras | Pendiente | Desde nov-26 | Meses pasados sin cierre |
|---|---|---|---|---|
| COSTE | 21 | 113,98 M€ | 102,52 M€ | 3 obras, 4,79 M€ |
| VENTA | 21 | 115,42 M€ | 103,19 M€ | 3 obras, 5,58 M€ |

Por tipo de la versión que rige (COSTE; VENTA igual de forma): 15 obras Cuatrimestral (66,6 M€
pendientes), 4 ABC (42,0) y 2 Planif Inicial (5,3; una de 2020). Las 21 son 19 de las 40 obras
vivas de la nocturna y 2 congeladas; las otras 21 vivas no tienen plan pendiente. Agregado de 737
filas (obra × mes × concepto × categoría) en ~90 s de lectura.

**El plan y el real NO casan en el corte, y eso es la hipótesis más cara.** En las 15 obras con
Cuatrimestral, la versión planificaba 144,85 M€ de coste hasta el último cierre y el real a
origen es 131,15 M€ (desfase absoluto sumado por obra: 14,06 M€). «Lo que queda» según el plan
(66,6 M€) no es «plan total − real» (211,5 − 131,2 = 80,3 M€). Las dos son legítimas.

## 3. La obra de los efectos: hoy y con la cascada (D4-B de F-037)

Efectos NO BAJA de `tesoreria.efectos`; «viva» = PREVISTO y no `previsto_antiguo`.

| Vía | Pagos | Importe | Viva | Cobros | Importe | Viva |
|---|---|---|---|---|---|---|
| 1 · centro → obra (hoy) | 122.895 | 795,46 M€ | 10.367 · 50,85 M€ | 9.273 | 963,34 M€ | 552 · 40,04 M€ |
| 2 · contrato (una sola obra) | 4 | 0,07 M€ | 0 | — | — | — |
| 3 · cabecera de la factura | 107 | 0,16 M€ | 2 | — | — | — |
| 3 · líneas (una sola obra) | 2 | 0,00 M€ | 0 | — | — | — |
| centro que no es obra | 1.317 | 7,46 M€ | 20 · 2,40 M€ | 202 | 11,65 M€ | 0 |
| documento sin obra | 4.674 | 5,02 M€ | 28 | 3.592 | 24,70 M€ | 28 · 0,88 M€ |
| sin documento | 12.478 | 100,42 M€ | 289 · 2,14 M€ | 318 | 30,68 M€ | 26 |

Cobertura de pagos: 86,87 % → 86,95 % (+113 efectos, +0,23 M€); de la cartera viva de pagos,
96,8 % → 96,8 % (+2). Cobros: sin vía (las ventas no se ingieren, F-040). El gran hueco son las
AGRUPACIONES (serie `AGR`, sin documento): 11.378 pagos sin obra, 88,56 M€ (274 vivos, 2,11 M€).
**Sigrid no guarda el vínculo** con los efectos agrupados: `pag.padide` («Pago destino») vale 0 en
los 257.717 pagos y `cob.padide` en los 21.941 cobros, leído en Sigrid; el asiento compartido de
`raw.rac` resuelve 178 a una obra y 555 a varias (descartado: conjetura).

## 5. Lo ejecutado desde la versión, por partida (indicación 3 del humano)

Para cada (obra, concepto) con devengo pendiente: la versión V que rige el último mes pendiente, su
mes (`date_trunc` de `version_fec_efectiva`) y, POR PARTIDA, el plan de V desde su mes
(`stg.plan_mensual` filtrado por obra, ámbito master y versión), el plan de V en el intervalo
[mes de V, último cierre], lo ejecutado en ese intervalo (`importe_mes` real de `mart`, que
telescopa, F-118) y el plan restante (meses posteriores al cierre). M€:

| Concepto · tipo de V | Obras (con intervalo) | Plan restante | Plan en el intervalo | Ejecutado en el intervalo | Adelantado | Retrasado | Pendiente ajustado | Ejecutado fuera del plan |
|---|---|---|---|---|---|---|---|---|
| COSTE · Cuatrimestral | 15 (15) | 66,62 | 49,46 | 34,88 | 5,22 | 19,81 | 84,51 | 0,94 |
| COSTE · ABC | 4 (3) | 42,03 | 1,73 | 0,52 | 0,21 | 1,42 | 43,27 | 0,00 |
| COSTE · Planif Inicial | 2 (1) | 5,33 | 0,63 | 1,03 | 0,71 | 0,31 | 5,42 | 0,03 |
| VENTA · Cuatrimestral | 15 (15) | 67,16 | 47,11 | 32,14 | 4,83 | 19,79 | 84,31 | 1,28 |
| VENTA · ABC | 4 (2) | 42,88 | 0,34 | 0,56 | 0,25 | 0,03 | 42,76 | — |
| VENTA · Planif Inicial | 2 (1) | 5,38 | 0,58 | 0,67 | 0,18 | 0,09 | 5,29 | — |

Pendiente ajustado de una partida = máx(0, plan de V desde su mes − ejecutado en el intervalo);
adelantado y retrasado, la diferencia partida a partida en el intervalo. **Pesa**: en COSTE el
pendiente ajustado es 133,2 M€ frente a 114,0 de plan restante (+19,2 M€, +16,8 %); en VENTA,
132,4 frente a 115,4 (+16,9 M€): las obras van RETRASADAS respecto a su versión, y quitar solo los
meses ya cerrados olvidaría lo planificado y no ejecutado. Partidas sobre-ejecutadas (ejecutado >
plan desde V; su pendiente es 0): 913 de coste y 322 de venta. Partidas con pendiente pero SIN
meses restantes en V (todo lo planificaba antes del cierre): 2.087 de coste (5,99 M€) y 1.720 de
venta (6,09 M€). Partidas con plan pendiente: 20.842 de coste y 18.524 de venta (39.366 filas).

## 6. La frontera con la cartera de F-037 (no contar dos veces)

En las 21 obras con devengo pendiente (último cierre de cada una como corte):

| Pieza | Importe | Obras | Dónde vive |
|---|---|---|---|
| Cartera viva de pagos (PREVISTO y no antiguo, con IVA) | 36,44 M€ | 19 | `tesoreria.efectos` |
| Cartera viva de cobros | 21,31 M€ | 19 | `tesoreria.efectos` |
| Pagos vivos EMITIDOS tras el último cierre | 0,86 M€ | 12 | `tesoreria.efectos.fecha_emision` |
| Cobros vivos emitidos tras el último cierre | 0 | 0 | ídem |
| Facturas de compra posteriores al cierre (base) | 0,83 M€ | 11 | `compras.facturas.fecha_factura` |
| Albaranes recibidos pendientes de facturar | 8,23 M€ | 20 | `compras.fact_compras_linea.importe_pendiente_facturar` |

Lo ejecutado y facturado ya es cartera (no es devengo pendiente); lo ejecutado y NO facturado (los
albaranes) no está en ninguna de las dos; y lo facturado tras el cierre está en las dos.

## 7. IVA y plazos de cliente (para los valores por defecto)

- Facturas de compra de los últimos 12 meses (17.613): cuota de IVA / base = 7,99 / 144,53 M€ =
  **5,5 %**. La marca `inversion_sujeto_pasivo` vale falso en TODAS: no sirve para separar la
  inversión del sujeto pasivo, y el tipo efectivo dice que buena parte de la compra va sin IVA.
- Forma de cobro más frecuente en los contratos con el cliente: `CF60` (110 de 705), luego `TR0R`
  (97), `CF90R` (70), `TR0` (68). Forma de pago más frecuente en contratos de compra: `120` (5.624
  de 19.170).

## 8. Lo que queda fuera de la medición

- `auxcob`/`auxefc` no están en `raw`: el lado de cobros necesita ingerirlas (D7).
- La relación entre el devengo pendiente y QUÉ contrato lo facturará no existe en Sigrid: repartir
  el devengo entre contratos es, otra vez, hipótesis de quien consulta.
