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

## Revalidación 2026-11-16 (spec-author, contra `main` 9957fd7)

Rama `feature/F-104-retenciones-cliente` con `main` dentro (merge 9957fd7). Medido en Azure en SOLO
LECTURA (`PostgresClient` con `_bootstrap_done = True`, `filas_solo_lectura` en transacción `READ
ONLY` con timeout ≤ 240 s), sobre la nocturna del 16-11 (cobertura de `ventas` de las 03:42 UTC).
Scripts en el scratchpad de la sesión (`q_f104_base.py`, `qb_cliente.py`, `qc_cuadre.py`,
`qd_ventas.py`), no en el repositorio. Nada escrito contra Azure ni contra Sigrid.

### 7. Qué ha cambiado en `main` y cómo afecta a la spec

| Cambio | Efecto en F-104 |
|---|---|
| F-040 ingiere `raw.cli` (con `cueretide`, `cueide`), `dvfpro`, `dvfrec` | **D3 se reabre** (§8). `v_src_lineas_venta` ya tiene 29.285 filas: 0 filas CLIENTE sin obra |
| F-040 deja escritas tres promesas a F-104 (`ventas.yaml` cabecera, `v_factura_cobro`, `cobertura_enlace`; `ARCHITECTURE.md`; su `requirements.md`): `entidad_cif`, conciliación por documento, cobro vía AGR | **D9, D10, D11 nuevas**; R25 corrige los textos |
| `tests/test_f040_frontera.py` protege `retenciones/00_setup.sql` y vigila el diff de `retenciones/` | `cuentas_cliente` se muda al principio de `01`; R24 añade `01` y `08` a `TOCADOS_DESPUES` |
| F-162 (`stg.obras` por empresa) | Sin efecto: `maestro.centros_coste` no cambió y nada nuevo agrega por `codigo_obra` |
| F-161 (catálogo de versiones) | Solo tocó `retenciones/05_fin_obra.sql` (`tiene_reparto`), que F-104 no toca |
| F-163 (completa en fin de semana) | Diario incremental por `tiemod`: afecta igual a `saldo_contable_cliente` y a `contabilidad.mayor` (los dos leen `raw.apu`); riesgo (5) del design |
| Diccionario v72 → **v78** | R18: `main` + 1 al implementar (v79 si F-160/F-099 no suben antes) |
| Arnés 1.7.7 → 1.10.1 | Capa por requisito, rigor arriba del design, «Frontera», tabla «Decisiones», mutación informativa en `estandar` |
| `config/tables_sigrid.yaml`: el comentario de `cob` dice «sigue saliendo solo de fecrea, sin verificar» | R26: se corrige el comentario |

Ningún objeto, nombre ni fichero que la spec da por nuevo existe hoy: no hay `08_*.sql` en
`retenciones/`, ni `cuentas_cliente`, `saldo_contable_cliente`, `v_cuadre_cliente`,
`origen_retencion` o `cuenta_id` en `movimientos` (columnas leídas en `information_schema`).

### 8. El universo de cuentas, ahora que existe `cli.cueretide` (D3)

| Universo | cuentas | con apuntes | saldo contable (`contabilidad.mayor`) |
|---|---|---|---|
| 43x8 `tip 17` (lo aprobado) | 221 (214 4308, 3 4328, 4 4338) | 167 | 16.002.697,94 |
| `cli.cueretide` (1:1: 211 clientes, 211 cuentas) | 211 (203 4308, 2 4328, 2 4338, 3 5540, 1 4380) | 162 | 15.053.935,40 |
| en los dos | 207 | 160 | 15.053.935,40 |
| solo 43x8 | 14 | 7 | 948.762,54 |
| solo `cueretide` | 4 (5540 «retenciones suplidos» de UTE, 4380 «Anticipos») | 2 | 0,00 |
| **unión (recomendada)** | **225** | **169** | **16.002.697,94** |

- Lo que solo trae el prefijo es **UNEXUM REAL ESTATE** (4338001593, 947.835,66) y ROSADO ESTEVEZ
  (4308000145, 926,88). UNEXUM SÍ es cliente (`cli.ide` 2246663), pero su `cueretide` apunta a
  4308001593 y el dinero está en 4338001593: error de ficha en Sigrid, para la lista de D8.
- Lo que solo trae `cueretide`: 4 cuentas con saldo 0 y 1 efecto `retide = 0` (3.957,70, no vivo).
- Ninguna cuenta de cliente (43x8 ni `cueretide`) es `cueretide` de un proveedor.
- Por eso la recomendación pasa de «prefijo provisional → `cueretide`» a **la unión**, con
  `criterio_seleccion` por fila y `cliente_id`: la regla de F-095 donde existe el dato, y el
  prefijo para no perder 0,95 M que Sigrid tiene mal declarados.

### 9. Cifras de 06-11 frente a 16-11

| Medida | 06-11 | 16-11 |
|---|---|---|
| CLIENTE en `movimientos` (filas / VIVA publicado) | 2.254 / 22.406.732,96 (2.212) | 2.256 / 22.438.322,16 (2.214) |
| VIVA con baja, `est 1` | 1.956 / 19.928.538,74 | 1.956 / 19.928.538,74 |
| VIVA sin baja, `est 1` (= VIVA con R1) | 245 / 2.371.937,54 | 247 / 2.403.526,74 |
| VIVA sin baja, `est 10` (pasa a LIQUIDADA) | 11 / 106.256,68 | 11 / 106.256,68 |
| CLIENTE con R1: BAJA / LIQUIDADA | — | 1.957 / 19.937.206,76 · 52 / 420.440,16 |
| PROVEEDOR VIVA (no debe moverse, R9) | — | 7.621 / 8.856.229,44 |
| Efectos `retide = 0` que entran por R6 | 1.204 | 1.205 (1.204 de 43x8 + 1 de `cueretide`) |
| CLIENTE tras F-104 (filas) | 3.458 | 3.461 |
| Efectos vivos de las cuentas (R1) | 345 / 10.495.108,25 | 347 / 10.526.697,45 (247 con `retide`, 100 AGR/DIV/sin tipo: 8.123.170,71) |
| Saldo contable de las cuentas | 15.485.863,29 (43x8) | 16.002.697,94 (43x8 = unión) |
| Cuadre (cuentas con ≥ 1 €) | 18 CUADRA, 25 descuadran, 14 solo saldo, 5 solo efectos | 20 CUADRA, 23 descuadran (20 CONTAB_MAYOR + 3 EFECTOS_MAYOR), 16 solo saldo, 5 solo efectos |
| 4308001150 TERTIO MILLENNIO | CUADRA 12.000,00 | CUADRA 12.000,00 |
| 4308001634 ESPACIO PROMOCIÓN VIII (0686) | 1.679.407,38 / 622.160,33 | 1.735.233,86 / 622.160,33 (dif. 1.113.073,53) |
| 4308001550 ARCHER | SIN_SALDO 945.000,05 | SIN_SALDO 945.000,05 |

Los mayores descuadres hoy: LEVITT (1,23 M), ESPACIO 0686 (1,11 M), MK MADRID II (1,02 M), UNEXUM
(0,95 M sin efectos), ARCHER (−0,95 M), VÍA CÉLERE (0,54 M), SABINA (−0,53 M), REDES 2 (0,33 M),
IDS ALJARAFE (0,32 M), CUYAM (0,31 M), PRORED (0,24 M sin efectos), BTS (−0,22 M).

### 10. Las tres promesas de F-040 a F-104, medidas (D9-D11)

- **`entidad_cif` (D9)**: las 2.256 filas CLIENTE tienen su `entidad_id` en `raw.cli` y en
  `ventas.clientes`; 18 (26.334,49 €) son de persona física, cuyo NIF `ventas` publica a NULL.
  Leerlo de `ventas.clientes` por `entidad_id` ya da el CIF enmascarado; copiarlo a `retenciones`
  obliga a duplicar `ventas.fn_es_persona_fisica` y es tratar datos personales (disparador 3).
- **Conciliación por factura (D10)**: 2.904 facturas con garantía (`dvfrec`, clases 4-5;
  25.951.380,55). De las 2.250 que tienen efectos con `retide`, 2.244 cuadran al céntimo y 6
  difieren (−1.415,94 en total); **654 facturas (3.315.531,18) no tienen efecto de retención**: son
  los CONTABILIDAD_MAYOR de `v_cuadre_cliente` (ESPACIO, LEVITT, MK...), que F-104 ya enseña por
  cuenta. La garantía de venta tiene un único punto de decisión (`ventas.fn_clase_recargo`, D4
  provisional de F-040) y `retenciones` corre antes que `ventas`: hacerlo dentro de F-104
  obligaría a copiarlo o a ponerlo en `ventas`.
- **Cobro vía AGR (D11)**: `ventas.cobertura_enlace` EFECTO_FACTURA = 20.538 de 22.035 efectos
  (1.206,8 de 1.392,4 M); lo no enlazado son los AGR/DIV. Atribuirlos exige la casación (cuenta,
  fecha de baja) del §2: 90,4 % de cobertura y 44 grupos en los que el AGR suma más que sus
  originales.

### 11. Veredicto

**Requiere PARADA 1.** D1, D2, D4-D8 siguen valiendo con las cifras al día (D6: la 0686 tiene hoy
1,74 M de saldo y 0,62 M en efectos). **D3 cambia de sentido** (unión en vez de «prefijo
provisional → `cueretide`») y hay **tres decisiones nuevas** (D9-D11), heredadas de lo que F-040
dejó escrito a nombre de F-104. Tabla en `design.md` §9; el resto de cambios (fichero de
`cuentas_cliente`, `TOCADOS_DESPUES`, textos, versión, mutación) es técnico y no altera ninguna
decisión aprobada.

### 12. D10 = b (humano, 2026-11-16): la conciliación por factura, medida (y una corrección)

Decisiones del humano registradas en b7dc9a2: D3 a, D9 a, **D10 b**, D11 a; D1, D2, D4-D8 como
estaban. Medido de nuevo en solo lectura (`qe_factura.py`, `qf_recargos.py`, `qg_retesp.py`,
`qh_factura2.py`, `qi_cuenta.py`, `qj_resto.py` en el scratchpad).

**CORRECCIÓN de §10.** Dije que las 654 facturas con garantía sin efecto (3,32 M) «son los
CONTABILIDAD_MAYOR de `v_cuadre_cliente` (ESPACIO, LEVITT, MK...)». **Es falso**: 580 de ellas son
de 2008-2015 y ESPACIO, LEVITT y MK no tienen ninguna. Sus facturas llevan la retención como
**RETESP** (clase 1, «Retención 5% garantía (sin iva)»), que `ventas.facturas` no cuenta como
garantía (D4 provisional de F-040):

| Cliente | facturas | garantía (4-5) | RETESP | saldo de su cuenta 43x8 |
|---|---|---|---|---|
| ESPACIO PROMOCIÓN VIII (0686) | 26 | 0,00 | 1.735.233,86 | 1.735.233,86 |
| LEVITT LAS ROZAS | 74 | 0,00 | 1.561.705,72 | 1.561.705,72 |
| MK MADRID II | 21 | 0,00 | 1.347.109,23 | 1.347.109,23 |

Recargos de `raw.dvfrec` por clase y por si su `cueide` es cuenta de retención de cliente: clase 1
(RETESP) 1.067 a cuenta de retención (17.714.201,72) y 22 a otras (616.029,04); clase 4: 72
(1.312.923,84) y 9 (21.304,14); clase 5: 2.728 (24.323.614,89) y 96 (293.537,68); las clases 0, 2
y 3 nunca van a una cuenta de retención. **Nueva decisión D12** (design §9): qué retención de la
factura se concilia. Recomendado (a), los recargos que van a una cuenta de retención: sigue a la
contabilidad y no depende de la D4 de F-040.

**Los efectos de la factura** tienen que ser los de F-104 (`retide <> 0` o cuenta de retención),
no solo los de `retide`: ESPACIO tiene 622.160,33 € vivos en su cuenta en 2 efectos SIN documento
ni `retide` (agrupadores manuales). Por motivo, con D12 = a y ese universo:

| motivo | facturas | retención | efectos | diferencia | efectos vivos | agrupados (BAJA) |
|---|---|---|---|---|---|---|
| CUADRA | 2.696 | 25.270.436,45 | 25.270.436,45 | 0,00 | 2.495.450,75 | 21.965.891,86 |
| SIN_EFECTO | 1.114 | 17.781.786,37 | 0 | 17.781.786,37 | 0 | 0 |
| DIFIERE | 56 | 298.517,63 | 525.983,34 | −227.465,71 | 12.663,27 | 447.447,98 |
| EFECTO_SIN_RETENCION | 284 | 0 | 443.750,44 | −443.750,44 | 87.209,93 | 341.376,47 |
| SIN_CUENTA_RETENCION | 27 | 0 | 0 | (garantía 15.146,34 + RETESP 568.527,49 a otras cuentas) | | |

SIN_EFECTO por año: 2008-2015 159 facturas (1,42 M), 2016-2022 75 (0,81 M), 2023 97 (1,63 M),
2024 252 (3,69 M), 2025 293 (5,11 M), 2026 238 (5,11 M). Ningún recargo reparte entre dos
cuentas; en 26 facturas la cuenta del recargo no es la del efecto (por eso la cuenta de una
factura es la de su recargo). 164 clientes, todas las facturas con cliente.

Con la garantía sola (D12 = c), en cambio: 2.244 CUADRA, 654 SIN_EFECTO (3,32 M), 6 DIFIERE
(−1.415,94), 6 EFECTO_SIN_RETENCION (123.908,35, que son RETESP), y 1.063 facturas con RETESP
sin efecto (18,20 M) fuera del universo.

**Por cuenta** (`ventas.retencion_cuenta`): diferencia = saldo − efectos vivos, frente a
`retencion_sin_efecto` − `viva_sin_factura` (efectos vivos de la cuenta sin documento: 7,93 M en
37 cuentas). En las 44 cuentas que descuadran (Σ |diferencia| 9.469.807,80), **22 quedan
explicadas al euro** (ESPACIO: 1.735.233,86 − 622.160,33 = 1.113.073,53; CUYAM; REDES 2; LEVITT y
MK por su RETESP) y lo sin explicar baja a 4.943.305,62. En las cuentas que CUADRAN la resta da
5.176.601,32 de «resto» espurio (43 cuentas): facturas antiguas sin efecto cobradas por asiento.
Por eso `diferencia_sin_explicar` es NULL en `CUADRA`. Lo que queda sin explicar es la lista de
Administración: UNEXUM (+947.835,66 en 4338001593 y −947.835,66 en 4308001593: se anulan por
cliente), ARCHER (−945.000,05), SABINA (−525.731,62), SANTANDER DE LEASING (−392.804,75),
FUNDACIÓN MONCLOA 2000 (−316.205,24), BTS (−221.494,76), COLEGIO JUAN PABLO II (126.294,21).

**Diseño técnico** (sin cambio de fondo): tablas `ventas.retencion_factura` y
`ventas.retencion_cuenta` y la vista `ventas.v_retencion_cliente` sobre ellas, en
`ventas/06b_retencion_cliente.sql`, antes de la guarda. Son TABLAS y no vistas sobre `retenciones`
porque `retenciones/01` hace `DROP TABLE retenciones.movimientos CASCADE` cada noche. Permisos sin
cambios: `ventas` la leen solo estándar y total, que ya leen `retenciones`.

### 13. Veredicto (sustituye al §11)

**Requiere PARADA 1 por UNA decisión nueva, D12** (qué retención de la factura se concilia).
Recomendado (a), recargos a cuenta de retención; con (c), la que se deduce literalmente de
«garantía por `fn_clase_recargo`», la conciliación no explica ninguno de los grandes descuadres.
Todo lo demás de D10 (b) está diseñado. Tamaño: requirements 146/150, design 180/250; columnas y
mapa de tests en `specs/F-104-retenciones-cliente/design_detalle.md`.
