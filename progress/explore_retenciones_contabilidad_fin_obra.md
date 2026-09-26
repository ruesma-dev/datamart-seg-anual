# Exploración — retenciones desde la contabilidad y fin de obra

Fecha: 2026-09-22 · Solo lectura: Sigrid por `sigrid-api` y datamart por MCP
(build `retenciones` 2026-09-18 02:53 UTC). Consultas en scratchpad `retx/*.sql`.
Criterio usado en todo el informe para **«viva de verdad»** en un efecto:
`fecrea = 0 AND con.fecbaj = 0 AND con.est NOT IN (10,14,15)`.

## 1 · Los efectos agrupados: qué son y cuánto pesan

### Los tres de FERMALUX (entidad 1958815), medidos uno a uno

| efecto | `con.cod` | `est` | `fecbaj` | `conide` | `cenide` | `remide` → remesa |
|---|---|---|---|---|---|---|
| 2537182 | `AGR25/0955` | 10 Pagado | 0 | 0 | 0631 | `RP25/0121` «REMESA PAGARES RETENCIONES MAYO» |
| 2446609 | `AGR24/2192` | 10 Pagado | 0 | 0 | 0650 | `RP24/0287` «REMESA RETENCIONES NOVIEMBRE» |
| 2462976 | `AGR25/0085` | 10 Pagado | 0 | 0 | 0 | `RP25/0009` «REMESA PAGARES RETENCIONES DIC. 24» |

Los tres son efectos de serie **`AGR`** (agrupación), en estado **Pagado**
pero con **`fecrea = 0`**: el datamart deriva `estado` solo de `fecrea`
(`sql/retenciones/01_movimientos.sql`), así que los publica **VIVA**.
Confirmado en `retenciones.movimientos`: los tres salen `VIVA`.

### Los agrupados: estado 14 y `fecbaj` = fecha del agrupador

**No hay campo que enlace agrupador y agrupados.** Descartados con consulta:
`pag.padide` = 0 (ya medido en F-080), `pag.efeide` es el TIPO de efecto (7 en
los AGR, 12 en los `_02`), y `rcc`, `rcl`, `rcf`, `rcx`, `rcd`, `rca` no tienen
ni una fila con estos `ide`. `rac` (log de estados) registra en cada original
el paso «Efecto agrupado» (`est1` 1 → `est2` 14) **sin puntero al agrupador**.
Lo que sí hay, y cuadra al céntimo en los tres casos:

- Los originales quedan con **`con.est = 14` (Agrupados)** y **`con.fecbaj` =
  `con.fec` del AGR**, mismo proveedor, y la suma de sus importes es la del AGR:
  `AGR25/0955` = 9 efectos `_02` de la 0631 con `fecbaj 20250528` → **14.046,05**;
  `AGR24/2192` = 2 de la 0650 con `fecbaj 20241203` → **313,33**;
  `AGR25/0085` = 1 de la 0629 (115,91) + 11 de la 0635 (2.771,47) con
  `fecbaj 20250110` → **2.887,38**. Exactamente lo que dijo Juan.
- Y **los originales también salen VIVA en el datamart** (`fecrea = 0`, p. ej.
  2002073, 2114080, 1982418): **el mismo dinero cuenta dos veces** y ninguna
  de las dos es viva. FERMALUX: el datamart da **98.695,48 € vivos**; viva de
  verdad **64.201,96 €**; la diferencia (34.493,52) es exactamente 2 × 17.246,76.

El enlace efecto→agrupador solo es **deducible** (proveedor + `fecbaj` + suma).
### Alcance en toda la empresa (efectos `pag` con `retide <> 0`, Sigrid hoy)

De los **25.012 efectos / 35,54 M€ que el datamart da VIVOS a proveedor**
(MCP: `sentido='PROVEEDOR' AND estado='VIVA'`, 23.090 con documento + 1.922 sin él):

| qué son en realidad (todos con `fecrea = 0`) | efectos | importe | proveedores |
|---|---|---|---|
| originales agrupados (`est 14`, `fecbaj<>0`) | 14.668 | 12,99 M€ | 776 |
| otros anulados (`fecbaj<>0`: DIV padre, AGR anulados…) | 841 | 5,70 M€ | 262 |
| **agrupadores AGR ya pagados** (`est 10`) | 1.444 | 6,73 M€ | 526 |
| otros pagados sin `fecrea` (`est 10`) | 311 | 1,78 M€ | 181 |
| AGR pendientes de pago | 159 | 0,51 M€ | 114 |
| **vivos de verdad (FR/DIV sin baja)** | 7.593 | 7,83 M€ | 620 |

**Agrupadores AGR contados como vivos: 1.776 efectos, 685 proveedores,
11,05 M€** (385 de ellos, 2,05 M€, sin obra). **La retención viva real a
proveedores es ~8,35 M€, no 35,5 M€**: el datamart (y el orden de magnitud de
34,7 M€ publicado en `contexto_bbdd`) la infla **4,3 veces**. El problema de
Juan es la punta: el fallo de fondo es `estado` por `fecrea` y no filtrar
`fecbaj` —lo mismo que F-080 resolvió para `compras.vencimientos`—.
**Cliente (`cob`), sin analizar a fondo**: de 22,1 M€ «VIVA», ~1.957 efectos /
~19,9 M€ tienen `fecbaj <> 0`. Sospecha del mismo defecto; hay que verificarlo.

## 2 · La contabilidad: retención, pago y agrupación se ven bien

**FERMALUX en su cuenta 4108005478** (`prv.cueretide` = `pag.cueide` = 1958889):
- **Saldo contable = 64.201,96 €, idéntico al vivo de verdad de los efectos.**
- Alta: haber en la factura (`Fact. B2207363…`, 225,28, `cenide = 0`).
- La agrupación se ve como **baja por obra**: el asiento «Pagaré a cartera»
  del AGR carga 4108 **una línea por obra con su `cenide`** (0629 115,91 /
  0635 2.771,47) y abona 4110 (efectos a pagar); el pago posterior carga 4110 y
  abona 572. El AGR de la 0650 carga 4108 contra 572 directamente. **La
  contabilidad no duplica ni deja viva la retención agrupada.**

**Trampas medidas en el mayor** (familias 4008/4108/4180, `raw.apu` ya ingerido):
- **Asientos de cierre y apertura**: 9.806 apuntes de cierre y 9.975 de apertura
  (~57 M€ cada lado). Sumar debe o haber sin excluirlos (`res LIKE 'Asiento de
  cierre%'/'…apertura%'`; `asi.ori` = 0 en todos, no sirve) multiplica. Las
  cifras de F-059 (p. ej. 1.025 apuntes en 2009) los incluyen; sin ellos 2009
  son 485.
- **Movimientos reales**: altas (haber) **28.245 apuntes / 23,87 M€**; bajas
  (debe) **4.386 / 16,92 M€**. Saldo total de las tres familias: **7,85 M€**
  (4108 7,04 · 4008 0,69 · 4180 0,12).
- **Las tres familias no son todas**: `prv.cueretide` apunta además a **4038**
  (3 cuentas, saldo 0,90 M€) y 4128 (1, 0,08 M€). Elegir cuentas por
  `prv.cueretide` y no por prefijo. Saldo de todas las cuentas de retención de
  proveedor: **8,76 M€** frente a 8,35 M€ vivos en efectos.
- **Cuadre por proveedor** (saldo de su `cueretide` contra sus efectos vivos de
  verdad): **1.027 de 1.268 proveedores cuadran a menos de 1 €** (81 %), pero
  solo 5,07 de 8,35 M€ (61 %): los grandes descuadran (historia anterior a
  2016, prescripciones, reclasificaciones). Sin explicar aún: es trabajo de spec.
- Bajas que los efectos no tienen: prescripciones (176 apuntes, 0,30 M€),
  compensaciones, anulaciones de UTE, reclasificaciones.

### Atribución a PROVEEDOR: resuelta

`prv.cueretide` es **1:1** (2.247 cuentas, ninguna compartida) y en efectos
`pag.cueide = prv.cueretide` en **22.683 de 23.126** efectos `FR` (98,1 %).
Cobertura sobre el mayor: **altas 98,1 % del importe, bajas 96,2 %**.

### Atribución a OBRA: buena en altas, floja en bajas

`apu.cenide` siempre apunta a un centro de coste (`con.tip = 21`, 6.326 de
6.326), así que el puente `maestro.centros_coste` (F-073) sirve tal cual. Pero
**desde 2016 el alta NO lleva `cenide`** (2017: 7 de 1.417; 2025: 6 de 2.798),
mientras que **2009-2015 sí** (≈ 99 %: 2014 708 de 723). Camino completo:
`apu.cenide`, o si no `apu.asiide → rac.conide` (factura) `→ pag` `_02`
`.cenide`, o `rac.conide` = efecto `→ pag.cenide`.
- **Altas: 26.700 de 28.245 apuntes, 22,97 de 23,87 M€ (96,2 %)** con obra.
- **Bajas: 2.655 de 4.386, 12,19 de 16,92 M€ (72,0 %)**. Las que quedan son
  pagos manuales («PAGO SU FRA», «Pago retenciones», «PAGO RETENC OBRAS
  0655,0690,0703…» en un solo apunte), prescripciones y anulaciones de UTE.
  **Un saldo por obra desde contabilidad dejaría ~4,7 M€ de bajas sin obra.**
- `rac` **no se ingiere**: sin ella, las altas desde 2016 no tienen obra.

## 3 · La fecha de fin de obra: hay seis candidatas y ninguna está completa

Universo: las **179 obras con retención viva de verdad** (7.752 efectos,
8,35 M€; 8,23 M€ resuelven a obra). Obra = centro con misma `emp` y `cod`.

| campo (Sigrid) | qué es | en datamart | obras | % del importe vivo |
|---|---|---|---|---|
| `obrctr.fecreafin` | fin real (contrato de obra) | `cierre…cabecera.fecha_fin_real` (1ª) | 48 | 16,5 % |
| `obr.fecfinrea` | fin real (ficha de obra) | idem (2ª) | 52 | 23,8 % |
| **cualquiera de las dos** | = `fecha_fin_real` | sí | — | **25,3 %** |
| `obrctr.fecprorec` | **recepción provisional** | **no se publica** (sí en `raw`) | 40 | 21,4 % |
| `obrctr.fecdefrec` | recepción definitiva | no | 0 | 0 % |
| `obrctr.fecinigar` / `obr.garfecini` | inicio de garantía | no | 13 / 44 | 16,3 / 20,9 % |
| `obrctr.fecprefin` / `obr.fecfinpre` | fin **previsto** | `fecha_fin_previsto` | — / 95 | 45,4 / 73,6 % |
| `obr.fecfincie`, `cen.fecfin*` | cierre / centro | no | 2 / ≈0 | ≈0 % |

**138 de las 179 obras están en estado terminada/recibida/cerrada (19-25) y 85
de esas no tienen ninguna fecha de fin real.** `obrctr` tiene varias filas por
obra (966 filas, 448 obras, 165 con más de una): hay que decidir cuál manda
(`cierre` hoy toma el `MAX`). `obr.fecfinrea` y `obrctr.fecreafin` difieren en
4 de las 44 obras que tienen ambas.

## 4 · El plazo: no existe como dato de la retención de proveedor

- **Tipo de retención** (`rec`, `retenciones.tipos`): `diavto = -99` en los 15
  tipos de garantía usados (RET5, RET2.5, RET10, RET5T…). Solo trae el %.
- **Contrato de proveedor** (`ctr`): ningún campo de plazo; `tipgar` vale
  0 (11.425), -1 (7.506), 1 (79), 2 (8), sin catálogo. `ctrrec` (la regla de
  F-059) trae base, % y cuota, **ni plazo ni fecha**. `prv.plactr` es texto
  libre sobre formas de pago y `prv.codretpag` está vacío en 9.576 de 9.576.
- **Contrato con el cliente** (`obrctr`): **`plagar`** (plazo de garantía, meses)
  y **`plaret`** (plazo de retención, meses), más `fecdevret` (2 filas). Valor
  dominante 12 meses (166 y 125 filas). Cobertura sobre el vivo: `plagar`
  **93 obras / 61,8 %**, `plaret` **81 / 39,8 %**; `obr.garpla` 33 / 24,1 %.
  Es la garantía **del cliente**, no la del subcontrato: usarla para el
  proveedor es un criterio de Negocio (back-to-back), no un dato.
- **De facto**: `fecven` del `_02` = **factura + 15 meses en 22.620 de 23.129
  efectos (97,8 %)**; el vencimiento actual ignora el fin de obra.

## Decisiones que quedan para el humano

1. **Arreglo inmediato de lo publicado**, independiente del rediseño: ¿se
   corrige ya `retenciones.movimientos` (excluir `fecbaj <> 0` y tratar
   `est 10` como pagado) para que deje de dar 35,5 M€ vivos cuando son ~8,35?
   Hoy el orden de magnitud publicado al MCP (34,7 M€) es falso.
2. **Fuente del estado vivo/pagado**: contabilidad (saldo por `cueretide`, que
   cuadra en FERMALUX y en el 81 % de proveedores) o efectos saneados. Los 3,3 M€
   de proveedores que no cuadran hay que explicarlos antes de elegir.
3. **Selección de cuentas**: por `prv.cueretide` (incluye 4038 y 4128) o por
   las familias 4008/4108/4180 que fijó F-059.
4. **Obra de las bajas sin `cenide`** (~4,7 M€, 28 %): ¿se publican «sin
   obra», se reparten por FIFO contra las altas del proveedor, o se acepta el
   saldo por obra solo donde cuadra? Y **¿se ingiere `rac`?** (sin ella, las
   altas desde 2016 no tienen obra por vía contable).
5. **Qué fecha es «fin de obra»**: fin real (25 % del importe), recepción
   provisional (21 %), inicio de garantía (16-21 %) o fin previsto como
   respaldo (74 %). Y qué hacer con las **85 obras cerradas sin fin real**.
6. **Qué plazo**: `obrctr.plaret`/`plagar` del cliente (40-62 % del importe),
   un plazo fijo de Negocio (¿12 meses?), o el que ya aplica Sigrid (factura
   + 15 meses, 97,8 %). Ningún dato de proveedor lo trae.
7. **Cliente**: ¿~19,9 M€ «VIVA» con `fecbaj<>0` = mismo defecto? ¿Entra la 4308?
8. **Coordinación**: reescribe F-059 y toca F-045 y F-067: ¿feature nueva o F-059?
