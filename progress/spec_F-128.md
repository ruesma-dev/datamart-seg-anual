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
facturas, 790.276 € de apuntes de retención enlazados). **D2 = B (humano, 2026-10-17): NO es
garantía**; las fichas avisan del caso. Con eso la identidad es limpia: `totdoc − totpag` = Σ
clases 3, 4 y 5 en las **167.488** facturas de `raw` (0 excepciones, remedido el 17-10).

## 4. El cuadre contra el mayor de retenciones (F-095)

`retenciones.apuntes_contables.documento_id` es el documento del asiento (vía `rac`):
- **Por factura**, primera medición (con `RETESP` como garantía, opción D2-A que NO se tomó;
  universo = garantía ≠ 0 o apunte de retención enlazado): **27.000** facturas, 24,91 M € en factura frente a 24,54 M €
  contabilizados. Contabilidad: **26.824 cuadran al céntimo (99,3 %)**, 61 sin apunte
  (149.637 €), 133 solo en contabilidad, 7 difieren. Efectos (`retenciones.movimientos`,
  PROVEEDOR, `documento_id` = factura, estado ≠ BAJA o `estado_sigrid` = 14 agrupado):
  **22.725 cuadran (84,2 %)**, 4.100 sin efectos de la factura, 44 difieren. Sin el 14
  solo cuadraban 7.793: el agrupado es BAJA pero su dinero sigue vivo en el AGR.
- **Por factura con D2-B (la decidida; remedido el 2026-10-17, `raw` de 167.488 facturas)**:
  **27.002** facturas, 24,04 M € en factura frente a 24,54 M € contabilizados. Contabilidad:
  **26.762 CUADRA (99,1 %)**, 58 SIN_APUNTE (68.662 €), **175 SOLO_CONTABLE** (601.729 € netos;
  **42 de ellas son facturas con `RETESP`**), 7 DIFIERE. Efectos: **22.729 CUADRA (84,2 %)**,
  4.229 SIN_EFECTOS (42 con `RETESP`), 44 DIFIERE. Por (proveedor, obra): **6.109 pares, 5.304
  cuadran (86,8 %)**, 266 solo en contabilidad, 91 solo en factura. Son las cifras de la spec.
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
- Catálogo no ingerido (D5 = A, no se ingieren; `cocide` → F-143): `eioide` → `auxeio` 31,74/36,62 (5 valores), `almide` →
  `alm` 95,25/99,99, `cocide` → `auxobrcoc` 9,39/11,83 (20 valores).
- Datos bancarios (D4 = B): ya NO están en esta lista; ver §7 (se publican en
  `compras_restringida`, salvo `bantipide` y `dca.banide`).
- No ingeridos (exclusión de `tables_sigrid.yaml`), medidos en Sigrid: `tex` 475/602
  documentos (el memo de verdad es `con.tex`, F-080); `emptex`, `eiotex`, `eittra` 0;
  `dircon1` 6.086/20.889; `dirdir1` 164.465/309.683 (dirección del proveedor, 53 bytes);
  `dirdir2/3` < 5.500; `texent` 7/11; **`dca.pagfor`/`pagtex` 314.070 (100 %), 3,6 y 14,8
  bytes de media** (en dcf ya se ingieren) → D3 = A: no se publican.

## 6. Decisiones del humano (2026-10-17) y su efecto en la spec

- **D1 = A.** F-128 publica obra y centro de cabecera (`obride`, `cenide`, con código y nombre
  de `con`) en facturas y albaranes. F-093 se queda el DESAJUSTE cabecera-líneas y el caso de la
  proforma de Juan; `empide`/`hor` siguen en F-134 (exigen `dbo.log`). Fichas de F-093 y F-134
  actualizadas en `harness/features.json` en este mismo commit.
- **D2 = B** (no la recomendada). `es_retencion_garantia` = clases 4 y 5, sin mirar el código:
  la función pierde su segundo parámetro (R2, R14, R19). `RETESP` cuenta en `importe_descuentos`,
  no en garantía ni en `importe_retenciones`, y la identidad retención = garantía + fiscal queda
  sin excepciones (R7). En el cuadre, las 42 facturas `RETESP` con asiento de retención salen
  SOLO_CONTABLE: no se les da categoría propia; lo explican las fichas (R29). Cifras en §4.
- **D3 = A.** `tables_sigrid.yaml` no cambia (R33).
- **D4 = B** (no la recomendada). Nueva `compras_restringida.documento_cuenta_bancaria` (R20-R23,
  R30; design §7). Detalle y mediciones en §7.
- **D5 = A.** Sin ingesta de `auxeio`, `alm`, `auxobrcoc`. El tipo de contrato de compra pasa a
  **F-143** (nueva, `pending`): `cocide` está en `ctr` 14.453 de 19.137 (75,5 %, 19 valores),
  `dcf` 15.726 (9,4 %) y `dca` 37.157 (11,8 %); ningún SQL lo usa hoy.
- **No queda ninguna decisión abierta**: F-128 pasa a `spec_ready`. `progress/current.md` no se
  toca (lo usa F-141): el líder lo anota al retomar.

## 7. D4-B: la cuenta bancaria del proveedor (medido el 2026-10-17, solo agregados)

Las siete columnas `ban*` de `dcf` y `dca` YA se ingieren (no están en `exclude_columns`): **no
hace falta ingesta nueva**. `raw.auxban` (banco y sucursal) también está; `auxcueban` (tipo de
cuenta) NO.

| | `dcf` (167.488) | `dca` (314.105) |
|---|---|---|
| `ban` (cuenta completa, texto) | 17.706 (10,6 %) | 17.756 (5,7 %) |
| `bancue` = `bandig` = `banban` | 14.345 | 9.939 |
| `bansuc` | 12.517 | 9.913 |
| `ban` con forma de IBAN (país + 2 dígitos) | 7.858 (44 %) | 12.103 (68 %) |
| `ban` que empieza por dígito (CCC) / otro | 9.698 / 150 | 5.351 / 302 |
| longitud de `ban` | 20-32 | 20-32 |
| `ban` sin `bancue` (IBAN sin desglose) | 3.361 | 7.817 |
| igual a la cuenta ACTUAL de la ficha del proveedor (`prv.ban`) | 5.484 (31 %) | 12.780 (72 %) |
| la ficha del proveedor ya no tiene cuenta | 11.447 | 2.797 |
| proveedores distintos | 638 | 530 |

- **Es la cuenta del proveedor**: coincide con `prv.ban` del `entide` en 5.484 / 12.780
  documentos; `raw.prv` solo conserva cuenta en 1.032 de 9.618 proveedores. 61 proveedores
  llevan más de una cuenta en sus facturas. Es la que llevaba el documento, no la ficha de hoy.
- **Universo `ban` no vacío**: ningún documento tiene `bancue`, `bandig` ni `banban` sin `ban`
  (0 y 0), así que `ban` es el superconjunto. 0 `ide` comunes entre `dcf` y `dca`: `documento_id`
  vale de PK. En albaranes con cuenta, `banban` resuelve contra `auxban` en 9.939 y `bansuc` en
  9.913.
- **`bantipide` no se publica** (elección del spec-author dentro de D4-B, coherente con D5-A): su
  catálogo no se ingiere y no predice el formato (tipo 1: 2.699 IBAN y 9.390 CCC en `dcf`; tipo
  2: 3.146 y 308; tipo 0: 2.013 IBAN). Valores 0/1/2; el 1 está en 128.643 facturas sin cuenta.
- **`dca.banide` no se publica** (INTERNO): cuenta de banco propia, sin resolver (como
  `cuenta_transferencia_id` de `v_facturas_pago`), 2.861 albaranes, 95 de ellos sin cuenta.
- **Observación, no decisión**: `compras.v_facturas_pago` (F-080) ya publica al ESTÁNDAR el nombre
  del banco y de la sucursal de la factura (`banban`/`bansuc`). No son la cuenta; F-128 no lo
  cambia. Si el humano quiere también eso fuera del estándar, es un cambio de F-080 aparte.
- **Permisos sin cambios**: grants por esquema; `compras_restringida` vetada al estándar, fuera
  del restringido de F-141 (R5/R12 de F-141) y en la lista blanca del MCP (`mcp-bbdd`).
- Fuera de alcance (no pedido): la cuenta de la FICHA del proveedor (`raw.prv`) y una marca
  «cuenta del documento distinta de la ficha» (control antifraude). Serían feature aparte.
