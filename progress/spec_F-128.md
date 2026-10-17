# F-128 · Informe del spec-author: mediciones de la cabecera de factura y albarán

Spec: `specs/F-128-importes-cabecera-factura/`. Todo medido el **2026-10-17** en SOLO
LECTURA: el Postgres de Azure (`filas_solo_lectura`, sin bootstrap) y Sigrid por
`sigrid-api` (`leer_sql`). Sin escrituras. Solo agregados: ni códigos de factura ni
nombres de proveedor. Los scripts vivieron en el scratchpad y no se versionan.

## 1. Volúmenes (Azure, `raw` = copia de la noche del 2026-10-17)

| Tabla | Filas | Documentos | Sigrid hoy |
|---|---|---|---|
| `raw.dcf` / `compras.facturas` | 167.458 / 167.458 | — | 167.488 |
| `raw.dca` / `compras.albaranes` | 314.042 / 314.042 | — | 314.105 |
| `raw.dcfrec` | 32.994 | 32.922 facturas (19,7 %) | 33.005 / 32.933 |
| `raw.dcarec` | 41.466 | 41.419 albaranes (13,2 %) | 41.468 / 41.421 |

`raw.dcf` 136 columnas, `raw.dca` 134, `dcfrec`/`dcarec` 22. 0 recargos huérfanos
(todo `docide` está en su cabecera), 0 duplicados de `(docide, pos)`; 10 facturas
repiten el mismo `recide` en dos posiciones. **`compras.albaranes` publica proformas y
notas**: ALBARAN/AC 310.907, PROFORMA/PROF 2.856, NOTA/NTC 278, OTRO/CTSB 1 = 314.042.

## 2. Los importes de la cabecera (`dcf`, `dca`): identidades, 0 excepciones

Confirmado en Sigrid y en `raw` (0 filas que no cumplen):
- `totdoc = totbas + totiva` (total del documento CON IVA y ANTES de retenciones);
- `tot = totpag` en el 100 % (Sigrid documenta `tot` «con ret» y `totpag` «a pagar»:
  son el mismo número, así que se publica uno);
- **retención = `totdoc − totpag`** y es EXACTAMENTE la suma de `cuo` de los recargos
  de clase 3, 4 y 5 en las **32.922** facturas con recargos (0 excepciones); ninguna
  factura tiene `totdoc ≠ totpag` sin recargos. Albaranes: igual salvo **9** con
  recargos cuya diferencia no casa.
- `impnet` = Σ `dcfpro.tot` en 167.448 de 167.458 (99,99 %); `totbas = impnet −
  impdes + imprec`: `impdes` = Σ clase 1 (69 de 69) e `imprec` = Σ clase 0 (55 de 55).
  `impbru` difiere de `impnet` en 11.334 facturas sin descuento de cabecera (6,99 M €:
  descuentos de LÍNEA). Σ `totiva` de cabecera = Σ `dcfpro.ivacuo` a 91 € en total, pero
  difieren factura a factura en ~14.400 (redondeo por línea).

| Serie | Facturas | Base | IVA | Total (totdoc) | A pagar | Retención | Negativas |
|---|---|---|---|---|---|---|---|
| FR | 131.128 | 762,03 M | 59,87 M | 821,90 M | 797,94 M | 23,96 M | 4.517 |
| FRGG | 36.317 | 86,55 M | 10,17 M | 96,73 M | 95,38 M | 1,35 M | 1.537 |
| AB+ABGG+FC | 13 | — | — | −8,1 mil | — | — | 12 |

Retención total en factura **25,31 M €** = garantía (clases 4 y 5) 24,04 M + fiscal
(clase 3) 1,27 M. Albaranes: retención 20,71 M (AC 19,28 M; PROF 1,43 M; NTC 0); las
NTC suman −0,82 M (notas de cargo en negativo). **La retención del albarán y la de su
factura son la misma retención vista dos veces: no se suman.**

## 3. Los recargos y retenciones (`dcfrec`/`dcarec`): `reccla` = `rec.cla`

| `reccla` | Qué es (medido por los conceptos) | dcfrec filas / Σ cuota | dcarec filas / Σ cuota |
|---|---|---|---|
| 0 | Recargo (financiero, materiales) → `imprec` | 59 / 1.603 € | 294 / −465 € |
| 1 | Descuento (p. p. p.) → `impdes`; **y `RETESP`** | 69 / 879.162 € | 11 / 1.934 € |
| 3 | Retención fiscal (IRPF profesionales, arrendamientos, notarías) | 6.009 / 1,27 M € | 789 / 65.870 € |
| 4 | Retención de garantía sobre TOTAL (`RET5T`) | 158 / 0,29 M € | 241 / 71.058 € |
| 5 | Retención de garantía sobre BASE (`RET5`, `RET2.5`, `RET10`, `gar02`) | 26.699 / 23,75 M € | 40.131 / 20,59 M € |

`cuo = bas × valpor` siempre que `valfij = 0`; `valpor` en tanto por uno; 444 cuotas
negativas (abonos). `refide`, `frasupide`, `item`, `resalt`, `reqcuo`: 0 filas;
`ivaide` 205. **TRAMPA `RETESP`**: «Retención 5 % garantía (sin IVA)», 44 facturas y
871.193 €, está dada de alta como clase 1 (DESCUENTO): baja la base y NO entra en
`totdoc − totpag`, pero su asiento va a la cuenta de retención del proveedor (42
facturas, 790.276 € de apuntes de retención enlazados). Decisión D2.

## 4. El cuadre contra el mayor de retenciones (F-095)

`retenciones.apuntes_contables.documento_id` es el documento del asiento (vía `rac`):
- **Por factura** (garantía con `RETESP` incluido; universo = garantía ≠ 0 o apunte de
  retención enlazado): **27.000** facturas, 24,91 M € en factura frente a 24,54 M €
  contabilizados. Contabilidad: **26.824 cuadran al céntimo (99,3 %)**, 61 sin apunte
  (149.637 €), 133 solo en contabilidad, 7 difieren. Efectos (`retenciones.movimientos`,
  PROVEEDOR, `documento_id` = factura, estado ≠ BAJA o `estado_sigrid` = 14 agrupado):
  **22.725 cuadran (84,2 %)**, 4.100 sin efectos de la factura, 44 difieren. Sin el 14
  solo cuadraban 7.793: el agrupado es BAJA pero su dinero sigue vivo en el AGR.
- Los efectos AGR (agrupadores) no tienen factura: 2.454 efectos, 0,82 M € VIVOS. Es el
  origen del descuadre de `v_cuadre_proveedor` que la factura no puede atribuir.
- **Por (proveedor, obra de cabecera)** contra `retenciones.saldo_contable.altas`: 6.108
  pares, **5.302 cuadran a < 1 € (86,8 %)**, 266 solo en contabilidad, 92 solo en factura,
  201 sin obra. La obra del apunte (cascada F-095) = `dcf.obride` en 26.320 de 26.361
  facturas enlazadas (99,8 %).
- **Por proveedor**: 1.674, **1.205 cuadran (72,0 %)**; factura 24,04 M frente a altas
  26,02 M (las altas sin factura enlazada son ~1,07 M; 2,68 M de altas son anteriores a
  2016). Hoy `v_cuadre_proveedor` (contabilidad contra efectos): **527 de 768 cuadran**
  (eran 520 de 761 el 25-09); de los que allí descuadran, 100 cuadran factura-contabilidad.

## 5. Inventario de `dcf` y `dca` (cobertura = no nulo, no 0, no vacío)

**Ya publicado**: `ide`, `entide`, `entcif`, `entref`, `fecdoc` (facturas), `comide`,
`ctride` (albaranes); en `compras.v_facturas_pago`: `pagide`, `efeide`, `cueide`,
`banide`, `banban`, `bansuc`, `pagfor`, `pagtex` (facturas); `cypnatide` 0 %.

**Se publica (D1-A)**, cobertura dcf / dca: importes `impbru` 99,98/98,94, `impnet`,
`impdes` 0,04/0,00, `imprec` 0,03/0,00, `totbas` 99,98/98,94, `totiva` 81,75/86,87,
`totdoc` 99,99/98,95, `totpag` 99,99/98,95; `ctride` 51,75 (facturas; 86.664, todos
existen en `ctr`; la línea directa a contrato solo cubre 6.991); `obride` 95,98/99,98 y
`cenide` 97,05/100 (0 huérfanos contra `obr`/`cen`); `caaide` 1,10/0,33; `entcod`
99,99/99,98 (= código del proveedor en `con` en el 99,97 %); `entres` 99,99/99,99 (=
nombre actual en el 83,4 % / 83,3 %: es el nombre que llevaba el documento);
`entciftip` 95,44/98,65 (códigos 01-06 del tipo de identificación); `entcifpai`
95,52/98,58; `ivadif` 14,72/7,99; `tipisp` 0,73/0; `fecent` 8,92/11,21; `feclim`
7,52/8,94. Solo albaranes: `fecdoc` 99,99; `pagide` 99,99; `efeide` 99,99; `cueide`
99,12; `estfac` 85,74 (=1 ⇒ pendiente de facturar 0 en 269.109 de 269.249); `fecfac`
74,61; `idefac` 17,08 (53.647 de 53.654 son una `dcf`; la relación buena es por línea).

**No se publica, y por qué**:
- Otra feature: `empide` 92,03/95,82 y `hor` 95,96/100 → F-134 (qué son exige `dbo.log`).
- Vacíos (0 % en las dos): `ivareq facper fecpag eitide ivaide bul pes volum ageide
  ageimp fecrec estser antestser comide(dcf) divcod divcam empconide docrelide paclis
  prmide estped antestped empcif cveide alqide alqfec pexide divcamfec ctdide *div
  cypnatide refarc pdpide ano mes refcom emnet eg3w cptide delide aoside PFID cad*
  cpa* ppoide clabieser facoriide duaide numregcon fas periodo tipctr impavr synckey`;
  en dcf además `estfac antestfac fecfac horfac idefac tipsininv`.
- Residuales (≤ 1 fila): `emppreide`, `horlim`, `eleenvio`.
- Internos de Sigrid sin catálogo ni significado medible: `cla` (dcf 1001/0; dca 141 =
  casi solo PROF), `tipgar` (−1/0: no predice la retención, 15.035 vs 11.813 facturas
  con garantía), `dtumID` (2 valores), `docoritip`/`docoriide`/`pasdeside`/`pasori`
  (≤ 1,6 %, copia de documentos), `antestfac`, `horfac`, `tipsininv` (stock).
- Redundante: `diremp1` (= `entres` en el 99,95 %), `tot` (= `totpag` en el 100 %).
- Catálogo no ingerido (D5): `eioide` → `auxeio` 31,74/36,62 (5 valores), `almide` →
  `alm` 95,25/99,99, `cocide` → `auxobrcoc` 9,39/11,83 (20 valores).
- Datos bancarios de tercero (D4): `bandig`, `bancue`, `ban` 8,6-10,6 % / 3-5,7 %,
  `bantipide` 78,87/85,56; en albaranes también `banide`, `banban`, `bansuc` (≤ 3,2 %).
- No ingeridos (exclusión de `tables_sigrid.yaml`), medidos en Sigrid: `tex` 475/602
  documentos (el memo de verdad es `con.tex`, F-080); `emptex`, `eiotex`, `eittra` 0;
  `dircon1` 6.086/20.889; `dirdir1` 164.465/309.683 (dirección del proveedor, 53 bytes);
  `dirdir2/3` < 5.500; `texent` 7/11; **`dca.pagfor`/`pagtex` 314.070 (100 %), 3,6 y 14,8
  bytes de media** (en dcf ya se ingieren) → D3.

## 6. Decisiones abiertas para el humano (opciones cerradas; ver `requirements.md`)

D1 frontera F-093/F-134 · D2 `RETESP` · D3 `pagfor`/`pagtex` del albarán · D4 datos
bancarios · D5 catálogos no ingeridos. Tras decidir, el líder actualiza las fichas de
F-093 y F-134 en `harness/features.json` y anota en `progress/current.md` (este trabajo
corre en paralelo con F-141 y no toca ese fichero para no chocar en el merge).
