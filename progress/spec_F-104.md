# F-104 · Mediciones del spec-author (solo lectura, 2026-11-06 08:55-09:40 UTC)

Rama `feature/F-104-retenciones-cliente` desde `main` `da6c36f`. Todo leído del PostgreSQL de
Azure (`raw` de la nocturna del 06-11, ingesta 00:45 UTC) con `pg.filas_solo_lectura` (transacción
`READ ONLY`); nada escrito contra Azure ni contra Sigrid. Scripts fuera del repo (scratchpad).
Las cifras de hoy difieren algo de las de la ficha (22,16 M del 23-09): la cartera se mueve.

## 1. Qué publica hoy `retenciones.movimientos` para CLIENTE

| estado hoy | `fecha_baja` | `con.est` | efectos | importe |
|---|---|---|---|---|
| VIVA | con baja | 1 Pendiente | **1.956** | **19.928.538,74** |
| VIVA | sin baja | 1 | 245 | 2.371.937,54 |
| VIVA | sin baja | 10 Cobrado (remesa, sin `fecrea`) | 11 | 106.256,68 |
| LIQUIDADA | sin baja | 10 | 41 | 314.183,48 |
| LIQUIDADA | con baja | 1 | 1 | 8.668,02 |

VIVA publicado hoy = **22.406.732,96 €** en 2.212 efectos. Catálogo de estados del tip 24
(`raw.conest`): 1 PDT, 5 CAR, 6 DESC, 7 REM, 10 COB, 12 DEV, **14 AGR, 15 DIV**: existen, pero
`cob` no los usa en los originales agrupados.

## 2. Qué les pasa a los 1.956 efectos con baja: SE AGRUPAN, como en proveedor

- Todos son la retención de una factura de venta (documento tip 11, `_02` = «Cobro 2 de 2»),
  sin `padide`, sin remesa, sin `fecrea`. La baja cae entre 2016 y 2025, después del vencimiento
  en 1.492 (14,90 M) y antes en 462.
- **El mecanismo** (caso FUNDACIÓN TERTIO MILLENNIO, cuenta 4308001150, verificado al céntimo):
  los cinco efectos de 2016-17 (57.973,72 €) tienen `fecbaj` 2020-03-04 y existe
  **AGR20/0010 = 57.973,72**, misma cuenta, fecha 2020-03-04; los cinco de 2017-18 (176.487,48,
  incluidas dos rectificativas `R/`) tienen `fecbaj` 2020-03-05 y existe **AGR20/0011 =
  176.487,48**. Los AGR se dividen (`DIV20/0003`...`0012`), unos se cobran (`est 10`) y
  **DIV20/0010, 12.000 €, sigue pendiente: es exactamente el saldo de la cuenta en la contabilidad
  (12.000,00)**. El agrupador y sus hijos llevan `retide = 0`: `movimientos` los pierde.
- En `cob` el original agrupado queda en **`est 1` con `fecbaj` = fecha del AGR** (en `pag` va a
  `est 14`). Por eso F-094 no lo vio: el criterio por `est` no casa, el de `fecbaj` sí.
- Cobertura: **1.734 de 1.956 (18,02 M, 90,4 %) tienen un AGR en la misma cuenta y en la fecha de
  su baja**; en 67 grupos (1.012 efectos, 11,17 M) la suma del AGR es exactamente la de los
  originales; en 44 (722, 6,85 M) el AGR suma otra cosa (más efectos). 222 (1,91 M) no tienen AGR
  ese día: 78 (0,72 M) sí en su cuenta otro día y 144 (1,19 M) ninguno (cobro por asiento manual,
  p. ej. «COBRO RETENCIONES PARCIAL SANTA MONICA», COB20/0104). Ninguno parece pendiente.
- Estado HOY de los 135 AGR que reciben originales: 89 cobrados (11,14 M), 35 de baja por
  división (6,31 M) y **11 pendientes (1,39 M)**.
- `tesoreria.efectos` ya los trata bien: su `R-TESORERIA-ESTADO` (precedencia de F-094 en los dos
  sentidos) da BAJA con `fecbaj <> 0`. El único que publica mal es `retenciones.movimientos`.

## 3. Las cuentas de retención de cliente y la contabilidad

`raw.cli` no se ingiere (F-040), así que no hay `cli.cueretide`. En el plan de cuentas:

| familia | cuentas | nombre «…, Retenciones» | saldo hoy | saldo al 22-09 |
|---|---|---|---|---|
| 4308 | 160 | 157 (las 3 restantes suman 926,88) | 14.006.257,51 | 13.373.262,21 |
| 4328 | 2 | 2 | 82.443,83 | 82.443,83 |
| 4338 | 3 | 3 | 1.397.161,95 | 1.380.965,44 |
| **43x8** | **165** | | **15.485.863,29** | **14.836.671,48** |

En `raw.con` son `tip = 17` (220 cuentas 43x8, 165 con apuntes; con `tip = 16`, 0 con apuntes), y
llevan **1.204 efectos de `cob` con `retide = 0`** (AGR, DIV y sin tipo), hoy fuera de `movimientos`.
F-095 midió 13,81 M por `cli.cueretide` (Sigrid, 22-09): ~1,03 M de 43x8 no lo declara ningún
cliente (candidato: UNEXUM 4338001593, 0,95 M, sin ningún efecto). Las cuentas de los efectos con
`retide <> 0` NO sirven de universo: 115 cuentas, mezclan 4300 (14) y 5540 (6) y dejan fuera 70
cuentas 4308 con 8,96 M de saldo.

Efectos PREVISTO (sin baja, sin cobro, `est` fuera de 10/14/15) en cuentas 43x8: **345 efectos,
10.495.108,25 €** (2,37 M con `retide`, el resto AGR/DIV y efectos sin `retide`); todos con obra
por el centro salvo 16 (926,88). Cuadre por cuenta, saldo contable frente a esos efectos:

| categoría | cuentas | saldo | efectos vivos |
|---|---|---|---|
| CUADRA (< 1 €) | 121 (18 con importe) | 2.063.324,87 | 2.063.324,76 |
| descuadra | 25 | 11.844.601,54 | 6.925.266,26 |
| solo saldo | 14 | 1.577.936,88 | 0 |
| solo efectos | 5 | 0 | 1.506.517,23 |

Los grandes descuadres son tres casos, con el dato delante:
- **Factura reciente sin efecto de retención** (contabilidad > efectos). ESPACIO PROMOCIÓN VIII
  (4308001634, obra 0686): saldo **1.679.407,38**, efectos 622.160,33. Sus 23 facturas de
  2024-12 a 2026-10 cargan la retención en 4308 y Sigrid solo crea el efecto del neto (4300); las
  de 2025-08 en adelante no tienen efecto de retención ninguno. Igual LEVITT (1,03 M) y MK MADRID
  II (1,02 M). **Esta es la retención de 1,68 M€ de cliente que F-150 dejó pendiente**: la caja de
  0686 solo ve 0,62 M en la cartera (nota: no hay rastro escrito de la cifra en `progress/` ni en
  `specs/F-150*`; se identifica por el importe, y el líder debe confirmarlo).
- **Retención devuelta por factura y efecto sin cancelar** (efectos > contabilidad). ARCHER HOTEL
  PALACE (4308001550): las facturas 25/04/0031 y 25/07/0033 abonan 472.500,03 + 472.500,02 en 4308
  (saldo 0) y siguen PREVISTO AGR24/0005 y AGR24/0024 por lo mismo (945.000,05). Igual SABINA
  ESTATES (0,53 M).
- **Cuenta sin efectos**: UNEXUM (4338, 0,95 M), PRORED ALICANTE (0,19 M).

## 4. Las tres cifras de la ficha, conciliadas

| cifra | qué es |
|---|---|
| 22,16 M (22,41 hoy) publicado | 2,37 vivos de verdad + **19,93 agrupados o cobrados por asiento** (cuentan en su AGR) + 0,11 cobrados por remesa sin `fecrea` |
| ~2,2 M «criterio de proveedor» | los 245 efectos con `retide` sin baja: correcto como estado, **incompleto como saldo**: el dinero agrupado vive en AGR/DIV con `retide = 0` |
| 13,81 M contable (F-095) | 43x8 de las cuentas que declara `cli.cueretide`; 43x8 entero daba 14,84 M ese día y 15,49 M hoy |
| **10,50 M** efectos vivos en 43x8 | la retención viva según la cartera de Sigrid, contando AGR/DIV |
| 15,49 − 10,50 = 4,99 M | neto de: facturas sin efecto de retención (3,11 M solo en las tres primeras), cuentas sin efectos (1,58 M), efectos sin cancelar (−1,51 M) y el resto de los 25 descuadres; es la lista para Administración, no se reparte |

## 5. Atribución a obra y venta (lo que toca a F-040)

- Efectos vivos en 43x8: obra por el centro en el 99,99 %. No hace falta F-040 para la obra de
  los efectos.
- Contabilidad 43x8: las altas casan con una factura de `raw.dvf` (ya ingerida, cabecera con
  `cenide`) por el código del asiento en 70 % del importe; las bajas (cobros) casi nunca llevan
  obra. Atribuir el SALDO contable a obra exige un reparto por cliente que no está medido: fuera.
- `retenciones.v_src_lineas_venta` sigue vacía hasta que F-040 ingiera `dvfpro`; solo afecta al
  fallback de obra de un efecto sin centro (16 efectos, 926,88 €). El CIF de cliente es `cli`
  (F-040): `entidad_cif` sigue NULL en CLIENTE.

## 6. Consultas (resumen; texto completo en el scratchpad de la sesión)

Q1 estado×baja×est de `movimientos`; Q2 `cob`+`con` de los 1.956 (padre, remesa, año de baja,
documento, serie); Q5 mayor y efectos de las cuentas 1025308 y 1680579; Q6-Q8 universo de cuentas
y cuadre por cuenta (`contabilidad.mayor.importe_saldo` frente a `cob` PREVISTO); Q9-Q10 ESPACIO
PROMOCIÓN VIII y ARCHER; Q11 casación de altas con `raw.dvf`; Q12 casación original→AGR por
(cuenta, fecha = `fecbaj`); Q13 saldo al 22-09 y retención de las obras de la receta.
