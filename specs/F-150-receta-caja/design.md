# F-150 · Diseño (la receta de la caja, fase 1)

Mediciones: `progress/spec_F-150.md` §8-§10, `progress/impl_F-150.md` §1-§3. Decisiones: §9.

## 1. Encaje y límite

Amplía `tesoreria` (F-140): columnas, dos tablas `raw` (`iva`, la cabecera de `dvf`), la RECETA en
una ficha, una regla que remite a ella y (N11) UN objeto nuevo, `tesoreria.albaranes_pendientes_neto`.
El ETL publica DATOS (coeficiente, IVA y retención del contrato, albaranes netos) y la IA aplica
las hipótesis en el orden de la receta.

**Fronteras.** F-151 ejecutará la receta. **F-040**: líneas de `dvf`, certificaciones, revisión de
precios y lo certificado fuera del coeficiente. **F-099**: expedientes, adjudicado y fechas. H13,
H14 y H30, de AdP. **F-154**: la caja de ESTRUCTURA (el CP). Ni `sigrid-api` ni el MCP.

## 2. Ficheros

**Modificar**
- `domain/proyeccion_caja.py` (§4); `config/hipotesis_caja.yaml` (§6, cabecera); lector y carga
  (`infrastructure/config/hipotesis_caja_yaml.py`, `postgres/hipotesis_caja_sql.py`): `paso_receta`.
- Ingesta (§5.1): `etl_sigrid/domain/entities.py` (`TableSpec.include_columns`),
  `etl_sigrid/application/steps/ingest_raw_step.py`, `config/tables_sigrid.yaml` (`iva`, `dvf`) y
  `config/diccionario/raw.yaml` (sus fichas, patrón de `raw.auxcob`).
- `sql/tesoreria/00_setup.sql` (al final, idempotente, sin `DROP` ni `GRANT`): funciones de §5.2;
  `ALTER COLUMN unidad TYPE VARCHAR(20)` y `paso_receta VARCHAR(12)` en `hipotesis_caja`; las
  columnas de §5.2-§5.5 con `ADD COLUMN IF NOT EXISTS`; (N11) la tabla de §5.7.
- `sql/tesoreria/06_condiciones_contrato_cliente.sql` (§5.2), `07_devengo_pendiente.sql` (§5.3-
  §5.5), `08_hipotesis_caja_obra.sql` (rama H12 en el bloque SIGRID y el `COMMENT`, §5.6).
- (N11) `application/steps/build_tesoreria_step.py`: sub-paso `albaranes_pendientes` (`09`, tabla
  `albaranes_pendientes_neto`) AL FINAL de `SUB_PASOS`, tras `hipotesis_obra`.
- `config/diccionario/tesoreria.yaml`, `compras.yaml` (aviso en `v_pbi_albaranes_sin_facturar`,
  N11) y `00_global.yaml` (§7; `version` 62 -> 63 -> 64).
- Tests de F-140, F-147 y del recuento: `test_f140_{hipotesis,paso,diccionario,sql}.py` (H02 sin
  CP, H03/H08, H14, H20, `1..28`, 23 -> 27, columnas, rama H12, `SUB_PASOS`),
  `test_f066_ingesta_raw.py` (80), `test_f147_presupuesto_contexto.py` (N11, con su motivo).
- `docs/CONVENTIONS.md`, `docs/ARCHITECTURE.md`, `CLAUDE.md` (mapa) y
  `azure-apps/datamart_seg_anual.md` (consume `iva` y `dvf`; publica los albaranes netos).
- (N16-N17) `07` (§5.10-§5.11) y `00_setup.sql` (columnas y tabla nuevas); YAML: textos de H01, H02,
  H06 y H13 (siguen 30); `tesoreria.yaml`, `00_global.yaml` (`version` 67); `test_f140_sql.py`.

**Crear**: `tests/test_f150_{receta,coeficiente,contrato,hueco,ingesta,perfil,sql,diccionario,
albaranes,saldo,personal,contrato_compra}.py`; `sql/tesoreria/09_albaranes_pendientes.sql` (N11), `10_saldo_partida.sql` (N14).

**No se tocan**: `sql/stg/*`, `sql/mart/*`, `sql/compras/*` (N11 COPIA la fórmula, §5.7), `01`-
`05`, permisos (el esquema ya se concede entero; `raw` no), `main.py`, `domain/diccionario.py`,
`H21` (§8, riesgo 6). Ni IVA fijado a ninguna obra, ni `importe_adjudicado` (N3), ni H13 por
contrato (N7), ni columna nueva para CP (N12: ya está `categoria`).

## 3. La receta (en la ficha de `tesoreria.hipotesis_caja`)

El texto vive en la `descripcion` de la ficha (`describir_tabla` la sirve entera; F-147 no la mide)
y R2-R4 fijan sus piezas: ocho pasos (SALDO, DEVENGO, DOCUMENTO, COEFICIENTES, PLAZO, RETENCION,
IVA, CARTERA), cada hipótesis en el suyo. Lo que ya está escrito (N11-N15: CP fuera, personal por
el RECURSO, albaranes netos, saldo, IVA de la obra) es la ficha v66. La CUARTA tanda (N16-N17) cambia:
- **Paso 1.** «El PERSONAL (`importe_pendiente_personal`) se paga el ÚLTIMO DÍA del mes de su
  devengo, sin documento, plazo, fraccionamiento, retención ni IVA: es una regla, no una hipótesis.
  Una obra sin partes no tiene cuota de personal (`fuente_personal` `SIN_PARTES`): dilo.»
- **Paso 4.** Sale el aviso N13-b. «El resto del coste de la obra va por
  `tesoreria.devengo_pendiente_contrato_mes`: las filas con `contrato_id`, con la forma de pago de
  ese contrato (H01, H15) y los días del proveedor (H04); las de `contrato_id` vacío, con H02 de
  su `categoria`. Declara la parte enlazada (`pendiente_enlazado_contrato` del corte).»
- **Paso 5.** «H06 solo en las filas con contrato (su `retencion_garantia_porcentaje`); sin
  contrato, el valor de H06; el personal, nunca.» **Paso 6.** «El H13 de la obra, sobre la base
  SIN personal (las nóminas no llevan IVA y el H13 se mide en facturas).»

## 4. Dominio (`domain/proyeccion_caja.py`, sin infraestructura)

- (Hecho, T3-T4) `PASOS_RECETA` y `paso_receta` obligatorio (R1); `PERFIL_MESES` con
  `_error_de_perfil` y `MAX_MESES_PERFIL = 120` (R25).
- (Hecho, T5) Coeficientes del contrato (`leer_coeficientes_contrato`, `CLASE_POR_CODIGO`,
  `factor_coeficientes`: R7, N10), `coeficiente_venta` y sus fuentes (R9), `porcentaje_iva`,
  `importe_con_coeficiente`, `importe_por_porcentaje`, `hueco_facturacion` y `coeficiente_medio`
  (R22), `FUENTE_MEDIA_OBRA`, `MOTIVO_H12_FICHA`; el reparto es el `repartir_pendiente` de F-140.
- **(N11) `neto_fifo(importes: Sequence[Decimal | None]) -> list[Decimal]`** (R33): `N` = Σ |negativos|;
  recorre en orden y a cada positivo `p` le resta `min(p, max(0, N − acumulado_previo))`, con
  `acumulado_previo` = Σ de los positivos anteriores; negativos y `None` -> 0. Es la fórmula de la
  ventana de `09` (§5.7) y los tests la comparan. `SERIES_ALBARAN_PENDIENTE = ("AC", "PROF")` y
  `UMBRAL_IMPORTE_ABSURDO = 1e8` (literales del SQL).

- **(N16) `cuota_personal(personal, real) -> Decimal`** (R44) y **(N17) `fracciones_contrato(pendiente,
  pendientes_servir: Mapping[int, Decimal]) -> dict[int, Decimal]`** y **`repartir_por_contratos(importe,
  fracciones) -> dict[int | None, Decimal]`** (R48); `FUENTES_PERSONAL = ("PARTES", "SIN_PARTES", "CP")`.

El SQL lleva los literales del dominio (regex, códigos, fuentes, `9`, `11`, `ROUND(…, 6)`, orden
del `COALESCE`, `GREATEST(0, …)`, motivo de H12, series, umbral) y los tests los comparan (F-135).

## 5. Ingesta y SQL

**5.1 · `raw.iva` y `raw.dvf` (hecho, T1-T2).** `TableSpec.include_columns` (R17); `dvf`: solo la
cabecera (`ide, cla, entide, cenide, ctride, fecdoc, totbas, totiva, totdoc`), `cla` 1024 =
rectificativas ya netas, sin marca de anulada; `iva` entero (en tanto por uno). Ninguna con `tiemod`.

**5.2 · `06` (N1, N2; hecho, T7-T8).** `tesoreria.fn_coeficientes(f TEXT) RETURNS NUMERIC[]` y
`fn_coeficientes_reconocidos` en `00_setup.sql`; `06` gana el desglose de R8 y `iva_id` /
`iva_porcentaje` (`ROUND((i.iva * 100)::NUMERIC, 4)`, `LEFT JOIN raw.iva i`).

**5.3-5.6 · `07` y `08` (hecho, T9-T10).** En `07`, misma transacción: `_dev_coef` (el master de V
leído de `stg.presupuesto` solo por obra, `ambito_id IN (9, 11)` y `fase_num`), `_dev_contrato`
(`raw.obrparpar.ctride` de la misma obra), `coeficiente_venta = COALESCE(contrato, master)`, la
guarda D6, el reparto con coeficientes, IVA y retención del contrato con sus bases `SIN` (R11-R20)
y `_dev_hueco` NETO POR OBRA (R23; por contrato no: solo 4.665 de 15.665 facturas llevan `ctride`).
En `08`, la rama H12 SIGRID (`raw.obr` -> `raw.iva`, `MOTIVO_H12_FICHA`). Detalle: los `COMMENT`.

**5.6 bis · `08`, H13 SIGRID (N15, TERCERA tanda).** Rama más en el bloque SIGRID: por obra, `base`
= Σ `raw.dcfpro.tot` y `cuota` = Σ `ivacuo` (`COALESCE(…, 0)::NUMERIC(18,2)`, `abs(tot) < 1e8`) de
sus líneas (`obride`) con factura (`raw.con.fec`) en los 12 meses hasta el build; SIGRID =
`ROUND(100 × cuota / base, 2)` si `base` ≥ 500.000 EUR (`UMBRAL_BASE_H13`) con `MOTIVO_H13_COMPRAS`;
si no, DEFECTO (5,5, la empresa). Dominio: `iva_efectivo_compra(base, cuota)` -> `Decimal | None`.
Receta, paso 6: el IVA del pago = base × el H13 DE LA OBRA, no el de la empresa.

**5.7 · `09_albaranes_pendientes.sql` (N11; hecho, T18).** Tabla `tesoreria.albaranes_pendientes_neto`
(R34; `UNIQUE (obra_id, proveedor_id, contrato_id, mes_albaran) NULLS NOT DISTINCT`), una transacción
con guarda de entrada: universo = obras de `devengo_corte_obra` COSTE; líneas de `raw.dcapro`/`dca`/
`con` (`AC`/`PROF`, contrato de cabecera o de línea 44, el `CASE` del pendiente COPIADO de
`compras/01`, `abs` < 1e8); FIFO por (obra, proveedor) con la ventana de `neto_fifo` (R33); agrupado
por (obra, proveedor, contrato, mes) con `meses_antiguedad` y `tras_cierre`; guarda R35. Detalle: el
`COMMENT` y la cabecera de `09`. Coste medido: 5-15 s.

**5.8 · `07`, la cartera de CP (N12).** `devengo_corte_obra` gana, en COSTE (NULL en VENTA),
`cartera_viva_coste_proporcional` y `cartera_emitida_tras_cierre_coste_proporcional` (NUMERIC(18,2),
CON IVA): en el `LATERAL` de la cartera, Σ `e.importe × cuota_cp` con los mismos `FILTER`, y
`cuota_cp` de cada efecto = Σ `raw.dcfpro.tot` de las líneas de su factura (`docide =
e.documento_id`) cuya partida (`paride`) es `categoria = 'CP'` en `mart.v_pbi_dim_partida` / Σ
`tot` de todas sus líneas (0 si la suma es 0 o el efecto no tiene factura). Mismo criterio que el
devengo (la categoría de la partida); la cuenta del efecto es la del proveedor (400/410) y el
nombre del tercero da falsos positivos (§10 del informe). Guarda de entrada: `raw.dcfpro`.

**5.9 · `10_saldo_partida.sql` (N14, SEGUNDA TANDA).** `tesoreria.saldo_partida_obra`, una fila por
obra del universo (COSTE), CON IVA, `fecha_corte` = `CURRENT_DATE` del build. Columnas (todas de
`tesoreria.efectos`, no BAJA salvo los originales, y la cuota CP de §5.8): `cobrado_realizado`
(COBRO REALIZADO); `pagado_realizado_sin_agr` (PAGO REALIZADO, `serie_efecto <> 'AGR'`);
`pagado_agr_con_obra` (los AGR REALIZADO que conservan obra); `agrupados_vencidos` y
`agrupados_pendientes` (los ORIGINALES: `sentido = 'PAGO'`, `estado_tesoreria = 'BAJA'`,
`estado_codigo = 14`, vencimiento < o ≥ `fecha_corte`); `cartera_viva_agr_con_obra` (AGR PREVISTO
con obra); `pagado_coste_proporcional` (cuota CP de lo pagado que se use); `personal_coste_partes`
(Σ `raw.hmores.tot` de recursos PERSONA internos de la obra con mes ≤ `mes_ultimo_cierre`: el
precio de cada parte es el del momento, sin IVA). Las retenciones son efectos propios: entran al
cobrarse o pagarse y las pendientes van en la proyección. Sub-paso tras `09`; guarda de entrada.
La receta, paso 0 SALDO (`PASOS_RECETA` gana `"SALDO"` delante: ocho pasos): con H28 `CON_SALDO`,
saldo = cobrado − (pagado sin AGR + [H29 `ORIGINALES`: agrupados vencidos | `AGR`: AGR con obra] −
CP) − personal; con `SIN_SALDO`, 0, y la proyección parte de hoy con la cartera vencida y no
pagada (H16, H17). En el paso 7, con `ORIGINALES`, resta `cartera_viva_agr_con_obra` y suma los
originales pendientes a su vencimiento (filtro exacto de arriba en `tesoreria.efectos`).
(N15) Gana `iva_soportado_pagado` (Σ importe del efecto × `totiva / totpag` de su factura en
`raw.dcf`, lo pagado de arriba) e `iva_repercutido_cobrado` (Σ × `totiva / totdoc` de `raw.dvf`),
y sus `_hasta_4t` (pagado o cobrado antes del 1 de enero del año del build) y `_hasta_4m` (en un mes
4 o más meses antes del mes del build). El saldo SUMA `iva_soportado_pagado − iva_repercutido_cobrado`
ya recuperado según H30 (`MENSUAL_REDEME`, el defecto: solo `_hasta_4m`; `COMPENSA_EMPRESA`: todo;
`ANUAL`: solo `_hasta_4t`).

**5.10 · `07`, el personal del devengo (N16, CUARTA tanda).** `_dev_real` pasa a COSTE y VENTA
(misma fuente). `_dev_personal`: por (obra, partida) de COSTE, Σ `raw.hmores.tot::NUMERIC(18,2)` de
`raw.res` `cla = 1 AND COALESCE(prvide, 0) = 0` (el filtro de `_sal_personal` de `10`; un test compara
el texto) con mes ≤ `mes_ultimo_cierre`. En `_dev_partida` (COSTE): `cuota_personal` (R44, `CASE`
literal del dominio; `CP` -> 0), `pendiente_personal` y `fuente_personal`. En `_dev_reparto`,
`parte_personal` con el mismo patrón que `parte_con_coef` (el último mes absorbe el redondeo) ->
`importe_pendiente_personal`; el corte, `pendiente_personal`; la guarda de la suma, también el
personal. Elegido por MEDIDA (§11 del informe): Σ partes / Σ real a origen de LA PARTIDA (el 95 % del
personal histórico cae en 248 partidas CI con cuota ~1). Descartados: el descompuesto del master
(las partidas de personal no tienen líneas `MANO_OBRA`: daría 0 en CI y 1,42 de subcontrata en CD) y
el nombre de la partida (no estándar; en la 0686 no encuentra nada). Guarda de entrada: `raw.res`.

**5.11 · `07`, el coste por contrato (N17).** Tabla nueva en `00_setup.sql`:
`tesoreria.devengo_pendiente_contrato_mes` (`obra_id`, `empresa_id`, `clave_obra`, `anio_mes`,
`categoria`, `contrato_id` NULL = sin contrato, `importe_pendiente` NUMERIC(18,2), `num_partidas`;
`UNIQUE (obra_id, anio_mes, categoria, contrato_id) NULLS NOT DISTINCT`). En `07`, tras el reparto:
1. `_dev_ctr`: por (obra, partida, contrato), `GREATEST(0, Σ tot − Σ tot × canser / NULLIF(can, 0))`
   de `raw.ctrpro` (`::NUMERIC`, `abs(tot)` < 1e8, `NULLIF(paride, 0)`) JOIN `raw.ctr c` (`c.obride` =
   la obra) JOIN `raw.con` (`est NOT IN (8, 9)`: Terminado, Rescindido) y solo contratos de
   `tesoreria.condiciones_contrato_compra` (H01 necesita su forma de pago). Por (contrato, partida) y
   no por línea: las líneas se sirven cruzadas (0686: 12,18 por línea frente a 3,36 neto).
2. Fracciones (R48) sobre `np` = `pendiente − pendiente_personal` de cada partida COSTE no `CP`.
3. Cada fila de `_dev_reparto` (partida, mes) con `np` > 0: su importe sin personal × la fracción
   de cada contrato, al céntimo, y el resto a la fila sin contrato (`repartir_por_contratos`).
4. `TRUNCATE` + `INSERT` agrupando por (obra, mes, `categoria`, contrato); guarda R50 (`RAISE` con
   el recuento). El corte gana `pendiente_enlazado_contrato` (Σ de las filas con contrato).
Guarda de entrada: `raw.ctrpro`, `raw.ctr`, `raw.con`. Lo contratado pendiente de servir que supera
el devengo (15,34 M EUR) NO se publica: no es devengo.

## 6. El catálogo (`config/hipotesis_caja.yaml`)

`paso_receta` de las 30: SALDO H28, H29 · DEVENGO H18, H19, H23, H26 · DOCUMENTO H03, H08 · PLAZO
H01, H02, H04, H05, H09, H15, H22, H24, H25 · RETENCION H06, H07, H10, H11 · IVA H12-H14, H30 · CARTERA el resto.

| Código | Cambio | Unidad | Defecto | `fuente_defecto` |
|---|---|---|---|---|
| H02 | (N12) sin la clave `CP`; texto: «el CP no es caja de la obra» | MAPA_DIAS | `{CD: 120, CI: 120, OTRO: 120}` | igual |
| H03 / H08 | Perfil del devengo a la factura / de la producción a la certificación | PERFIL_MESES | `[[0, 100]]` / `[[1, 100]]` | propuesta |
| H24 / H25 | NUEVAS · FRACCIONAMIENTO en meses de cada PAGO / COBRO | PERFIL_MESES | `[[0, 100]]` | Sigrid no lo guarda |
| H26 | NUEVA · Venta ejecutada pendiente de facturar | OPCION `[INCLUIR, NO_INCLUIR]` | `INCLUIR` | el hueco neto; lo facturado por delante no se cobra |
| H14 | Defecto | OPCION | `MENSUAL` | día 20 del mes siguiente; lo confirma AdP |
| H20 | Opciones `[FIN_MES_ALBARAN, EXCLUIR]`; (N11) ingrediente y fuente | OPCION | `FIN_MES_ALBARAN` | factura del mes del albarán en el 93 %; 8,76 M EUR NETOS por proveedor en 21 obras (la vista, 56,9: 48,2 ya sobrefacturados) |
| H28 | (N14) NUEVA · Saldo de partida, AMBOS, paso SALDO | OPCION `[CON_SALDO, SIN_SALDO]` | `CON_SALDO` | CON IVA; sin saldo, desde hoy con la cartera vencida |
| H29 | (N14) NUEVA · Pagarés agrupados, PAGO, paso SALDO | OPCION `[ORIGINALES, AGR]` | `ORIGINALES` | HIPÓTESIS: el AGR pierde la obra; vencido = pagado en su fecha, no vencido = pendiente a su vencimiento (0686: 1,32 y 0,27 M EUR) |
| H13 | (N15) SIGRID por obra (§5.6 bis); defecto, la empresa | PORCENTAJE | `5.5` | 12 meses, base ≥ 0,5 M EUR: 16 de 21 obras (0686 2,36 %; 0697 20,9 %) |
| H30 | (N15) NUEVA · Cuándo vuelve el IVA a devolver, AMBOS, paso IVA | OPCION `[MENSUAL_REDEME, COMPENSA_EMPRESA, ANUAL]` | `MENSUAL_REDEME` (humano, 29-10) | empresa 1: a devolver casi cada mes y devuelto a los 3-5 meses (4700): apunta a `MENSUAL_REDEME` (4 meses); AdP |
| H01 / H06 | (N17) ingrediente también `devengo_pendiente_contrato_mes`; texto: «las filas con contrato» | igual | igual | cobertura medida (§11) |
| H02 | (N17) «solo lo que NO tiene contrato: las filas sin `contrato_id`; el personal, nunca (fin de mes)» | igual | igual | igual |
| H13 | (N16) «sobre la base SIN personal» | igual | igual | igual |
| H27 | NUEVA · Antigüedad máxima de lo pendiente de facturar; (N11) ingrediente y fuente | MESES | `6` | con el neto FIFO, 0,52 de 8,76 M EUR tienen más de 6 meses (bruto: 22,8) |

Todas `validado: false`, `admite_obra: true`; ingredientes: H24/H25 `plazos_forma_pago`, H26
`devengo_corte_obra`, H20/H27 `albaranes_pendientes_neto` («neto por proveedor; `tras_cierre` es devengo»).

## 7. El diccionario y el presupuesto de F-147

`R-CAJA-HIPOTESIS`: `resumen` de la v63 (NO cambia); `ambito` + los objetos nuevos; la `regla` (no
medida) gana el CP fuera, el personal por el devengo del recurso y los albaranes netos. Fichas:
`albaranes_pendientes_neto` NUEVA (recomendada; residuo = Σ sobrefacturado − Σ compensado; 2
preguntas cortas: «Cuanto queda de verdad por facturar de albaranes en la obra X», «Cuando se
pagaran los albaranes pendientes de la obra X»); aviso en `compras.v_pbi_albaranes_sin_facturar`
(solo líneas > 0); `devengo_*`: «`CP` no es caja de la obra»; `efectos` y `efectos_restringidos_mes`:
el personal va por el devengo. `version` 64 con su nota; (N16-N17) `version` 67: `regla` con el
personal a fin de mes y el coste por contrato, ficha NUEVA de `devengo_pendiente_contrato_mes`
(recomendada, 2 preguntas cortas) y columnas nuevas de las `devengo_*`; `PRESUPUESTO_MAX` sube EXACTAMENTE lo que
mida la ficha nueva, con su línea de historia.

## 8. Despliegue (MANUAL, tras el review) y riesgos

Imagen y job; `ingest` de `iva` y `dvf` ANTES de `build-tesoreria`; R30; `publicar-diccionario`
con la imagen ya en el job; `check-*`; MCP reiniciado; R31. Vuelta atrás: `r20261030-2125` (N16-N17).
**Riesgos.** (1) La IA no abre la ficha: `resumen` y `regla` la nombran. (2) Doble fraccionamiento
(`30 60 90` y H24). (3) `dvf` no marca anuladas; H21 casa por emisión (F-040). (4) La fórmula del
pendiente vive en `compras/01` y `09` (la ata un test). (5) FIFO es SUPOSICIÓN (lo avala el 93 % de
facturas del mes del albarán). (6) Las líneas de `R-ALBARAN-ABSURDO` ya no están en `raw.dcapro`:
retirar la regla es otro trabajo. (7) El CP incluye LEVANTAMIENTO (1,91) y SEGURO T.R.C. (0,19).
(8, N16) Una obra sin partes no tiene cuota (0715: ~2,1 M EUR de partidas CI con nombre de oficio,
sin un parte); la receta lo avisa. (9, N17) `canser` es de Sigrid: si se sirve sin marcarlo, el
enlace sobra (cota: lo enlazado nunca pasa del devengo sin personal de la partida).

## 9. Decisiones

**Cerradas antes del 29-10** (`progress/spec_F-150.md` §7-§9): D1, D3-D7, D10, H14, H21, H24-H26;
N1-N10 (coeficiente, IVA y retención del contrato, bases `SIN`, avisos, `include_columns`, H20/H27,
hueco NETO POR OBRA, gramática de `coestr`).

**N11-N15, aprobadas por el humano el 29-10** (medido: `progress/spec_F-150.md` §10): **N11**
albaranes NETOS por (obra, proveedor), FIFO, suelo 0, objeto propio desde `raw` (`compras` se
construye después); **N12** el CP no es caja de la obra: en el devengo por `categoria`, en la cartera
por las partidas de la factura de cada efecto (§5.8), su caja es F-154; **N13** el personal va por el
devengo del RECURSO, no por las nóminas (N13-b, H02 `CI` con aviso, SUSTITUIDA por N16); **N14** el
saldo de partida CON IVA y opcional (H28), los AGR por sus ORIGINALES (H29, hipótesis que rompe
`R-TESORERIA-ESTADO`), el personal por `raw.hmores.tot` PERSONA interna hasta el cierre; **N15** H13
SIGRID por obra con umbral, H30 para la vuelta del IVA y el saldo con el IVA neto recuperado
(simétrico, decisión del spec-author).
**N16-N17, CUARTA tanda (humano, 31-10: «el pago de salarios es a fin de mes siempre»; «arréglalo
todo ya»; medido en `progress/spec_F-150.md` §11)**: **N16** el personal se paga a fin de mes, regla
fija y no hipótesis; cuota por partida de partes sobre real (§5.10). **N17** VIABLE en parte: el
enlace partida -> contrato existe (`raw.ctrpro.paride`, 32.386 líneas en las 21 obras) y cubre el
43 % del coste sin personal ni CP (0686: 69 %); el resto, H02. Tareas T36-T45, tras T35.
