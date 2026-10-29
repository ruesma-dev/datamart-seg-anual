# F-150 · Diseño (la receta de la caja, fase 1)

Mediciones: `progress/spec_F-150.md` §8-§10, `progress/impl_F-150.md` §1-§3. Decisiones: §9.

## 1. Encaje y límite

Amplía `tesoreria` (F-140): columnas, dos tablas `raw` (`iva`, la cabecera de `dvf`), la RECETA en
una ficha, una regla que remite a ella y (N11) UN objeto nuevo, `tesoreria.albaranes_pendientes_neto`.
El ETL publica DATOS (coeficiente, IVA y retención del contrato, albaranes netos) y la IA aplica
las hipótesis en el orden de la receta.

**Fronteras.** F-151 ejecutará la receta (aquí no hay caja). **F-040**: líneas de `dvf`,
certificaciones y su casado por mes de certificación, importe a certificar, revisión de precios y
lo certificado fuera del coeficiente; aquí solo la CABECERA de `dvf` para el hueco. **F-099**
(pendiente): F-150 le adelanta el desglose y el enlace partida -> contrato; F-099 conserva
expedientes, adjudicado y fechas (el líder lo anota). H13/H14: de AdP. Ni `sigrid-api` ni el MCP.
**N12**: la caja de ESTRUCTURA (el coste proporcional, CP: seguros, avales...) es F-154; aquí
el CP sale de la receta, del devengo y de la cartera de la obra.

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

**Crear**: `tests/test_f150_{receta,coeficiente,contrato,hueco,ingesta,perfil,sql,diccionario,
albaranes,saldo}.py`; `sql/tesoreria/09_albaranes_pendientes.sql` (N11), `10_saldo_partida.sql` (N14).

**No se tocan**: `sql/stg/*`, `sql/mart/*`, `sql/compras/*` (N11 COPIA la fórmula, §5.7), `01`-
`05`, permisos (el esquema ya se concede entero; `raw` no), `main.py`, `domain/diccionario.py`,
`H21` (§8, riesgo 6). Ni IVA fijado a ninguna obra, ni `importe_adjudicado` (N3), ni H13 por
contrato (N7), ni columna nueva para CP (N12: ya está `categoria`).

## 3. La receta (en la ficha de `tesoreria.hipotesis_caja`)

El texto vive en la `descripcion` de la ficha (T12; `describir_tabla` la sirve entera y F-147 no
la mide) y R2-R4 fijan sus piezas: siete pasos (DEVENGO, DOCUMENTO, COEFICIENTES, PLAZO,
RETENCION, IVA, CARTERA), cada hipótesis en el suyo. El ajuste del 29-10 cambia tres tramos:

- **Paso 1 (N12, N13).** «Solo el coste de la OBRA: el coste PROPORCIONAL (`categoria` = `CP`,
  estructura) NO es caja de la obra: exclúyelo y declara su importe. El PERSONAL de la obra ya
  está aquí, como coste del RECURSO con sus cargas sociales: NO sumes pagos de personal de la
  cartera (nóminas, embargos, cuotas de `tesoreria_restringida`) ni digas que faltan.»
- **Paso 4 (N11).** Los albaranes netos, con la forma de pago de su `contrato_id` (H01) y, sin
  él, H02 `OTRO`. (N13-b) **Aviso**: el personal de la obra va en CI y se paga con H02 `CI`;
  su plazo real es mensual: si importa, fija H02 `CI` por obra (USUARIO u OBRA) y dilo.
- **Paso 7 (N11).** «... y los albaranes pendientes de facturar NETOS por proveedor
  (`importe_pendiente_neto` de `tesoreria.albaranes_pendientes_neto`; NUNCA sumes las líneas
  positivas de `compras.v_pbi_albaranes_sin_facturar`: lo sobrefacturado a un proveedor ya paga
  sus otras entregas). Sin las filas `tras_cierre`, que ya son devengo pendiente. H20: la factura,
  a fin de `mes_albaran`, y el plazo desde ahí; las de `meses_antiguedad` > H27 (o sin mes) NO son
  caja: exclúyelas y declara su importe.» Sale la mención a `R-ALBARAN-ABSURDO` (el objeto ya
  excluye esas líneas). (N12) De la cartera de PAGO resta lo de CP: `cartera_viva_coste_proporcional`
  y `cartera_emitida_tras_cierre_coste_proporcional` de `devengo_corte_obra` (COSTE), y decláralo.

## 4. Dominio (`domain/proyeccion_caja.py`, sin infraestructura)

- `PASOS_RECETA = ("DEVENGO", "DOCUMENTO", "COEFICIENTES", "PLAZO", "RETENCION", "IVA",
  "CARTERA")`. `paso_receta` pasa a `_CAMPOS_OBLIGATORIOS`; `_errores_de_fila` rechaza uno fuera
  de la lista. `Hipotesis` gana `paso_receta: str = ""` AL FINAL; `construir_catalogo` lo rellena.
- `UNIDADES` += `"PERFIL_MESES"`; `_error_de_valor` llama a `_error_de_perfil(valor)` (R25;
  `MAX_MESES_PERFIL = 120`; pares lista o tupla de 2; `meses` no booleano; suma con
  `Decimal(str(p))`). Cada fallo, su mensaje.
- (Hecho, T5) Coeficientes del contrato (`leer_coeficientes_contrato`, `CLASE_POR_CODIGO`,
  `factor_coeficientes`: R7, N10), `coeficiente_venta` y sus fuentes (R9), `porcentaje_iva`,
  `importe_con_coeficiente`, `importe_por_porcentaje`, `hueco_facturacion` y `coeficiente_medio`
  (R22), `FUENTE_MEDIA_OBRA`, `MOTIVO_H12_FICHA`; el reparto es el `repartir_pendiente` de F-140.
- **(N11) `neto_fifo(importes: Sequence[Decimal | None]) -> list[Decimal]`** (R33): `N` = Σ |negativos|;
  recorre en orden y a cada positivo `p` le resta `min(p, max(0, N − acumulado_previo))`, con
  `acumulado_previo` = Σ de los positivos anteriores; negativos y `None` -> 0. Es la fórmula de la
  ventana de `09` (§5.7) y los tests la comparan. `SERIES_ALBARAN_PENDIENTE = ("AC", "PROF")` y
  `UMBRAL_IMPORTE_ABSURDO = 1e8` (literales del SQL).

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

**5.7 · `09_albaranes_pendientes.sql` (N11).** Tabla en `00_setup.sql`:
`tesoreria.albaranes_pendientes_neto` (`obra_id`, `empresa_id`, `clave_obra`, `proveedor_id`,
`contrato_id`, `mes_albaran` DATE, `importe_pendiente_bruto`, `importe_sobrefacturado`,
`importe_compensado`, `importe_pendiente_neto` NUMERIC(18,2), `meses_antiguedad` INTEGER,
`tras_cierre` BOOLEAN) con `UNIQUE (obra_id, proveedor_id, contrato_id, mes_albaran) NULLS NOT
DISTINCT` (precedente: `retenciones.saldo_contable`). `09`, una transacción, con guarda de entrada
(`raw.dca`, `raw.dcapro`, `raw.con`, `tesoreria.devengo_corte_obra`):
1. **Universo**: las obras de `tesoreria.devengo_corte_obra` con `concepto = 'COSTE'` (su
   `empresa_id`, `clave_obra` y `mes_ultimo_cierre`).
2. **Líneas** `_alb_linea`: `raw.dcapro d JOIN raw.dca a ON a.ide = d.docide JOIN raw.con c ON
   c.ide = a.ide`, obra `NULLIF(d.obride, 0)` en el universo, `tesoreria.fn_serie(c.cod) IN ('AC',
   'PROF')`; proveedor `NULLIF(a.entide, 0)`; fecha `tesoreria.fn_fecha(c.fec)`; contrato
   `COALESCE(NULLIF(a.ctride, 0), CASE WHEN d.docoritip = 44 THEN NULLIF(d.docoriide, 0) END)`;
   pendiente = el `CASE` de `importe_pendiente_facturar` de `compras/01_documentos.sql` COPIADO
   letra a letra (un test compara el texto normalizado); solo `pendiente <> 0`, `abs(tot) < 1e8` y
   `abs(pendiente) < 1e8` (`R-ALBARAN-ABSURDO`). No lee `compras`: se construye DESPUÉS (main.py).
3. **FIFO** (R33): `N` = Σ |negativos| por (obra, proveedor); en las positivas, ventana `SUM(p)
   OVER (PARTITION BY obra_id, proveedor_id ORDER BY fecha NULLS FIRST, linea_id)` y `compensado =
   LEAST(p, GREATEST(0, N − (acumulado − p)))`. Sin proveedor: `N` = 0 (no compensa ni se compensa).
4. `TRUNCATE` + `INSERT` agrupando por (obra, proveedor, contrato, `date_trunc('month', fecha)`):
   bruto, sobrefacturado (Σ |negativos|), compensado y neto; `meses_antiguedad` = meses entre
   `mes_albaran` y `date_trunc('month', CURRENT_DATE)` (NULL sin fecha); `tras_cierre` =
   `mes_ultimo_cierre IS NULL OR mes_albaran > mes_ultimo_cierre`. Filas con bruto o
   sobrefacturado > 0.
5. **Guarda** `DO` (R35): por (obra, proveedor) con proveedor, Σ neto = `GREATEST(0, Σ bruto − Σ
   sobrefacturado)`; sin proveedor, Σ neto = Σ bruto; ningún compensado fuera de [0, bruto]. Si
   no, `RAISE` con el recuento: la transacción se deshace y quedan las filas de ayer.
`COMMENT ON TABLE` con el qué y la clave. Coste medido en solo lectura: 5-15 s (30.533 líneas).

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

## 6. El catálogo (`config/hipotesis_caja.yaml`)

`paso_receta` de las 27: DEVENGO H18, H19, H23, H26 · DOCUMENTO H03, H08 · COEFICIENTES ninguna
(es dato) · PLAZO H01, H02, H04, H05, H09, H15, H22, H24, H25 · RETENCION H06, H07, H10, H11 ·
IVA H12, H13, H14 · CARTERA H16, H17, H20, H21, H27.

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
| H27 | NUEVA · Antigüedad máxima de lo pendiente de facturar; (N11) ingrediente y fuente | MESES | `6` | con el neto FIFO, 0,52 de 8,76 M EUR tienen más de 6 meses (bruto: 22,8) |

Todas `validado: false`, `admite_obra: true`; ingrediente de H24/H25 `plazos_forma_pago`, de H26
`devengo_corte_obra`, de H20/H27 (N11) `tesoreria.albaranes_pendientes_neto`. H20 dice además «neto
por proveedor; los `tras_cierre` ya son devengo». Textos de H10, H12-H15 como en la v63.

## 7. El diccionario y el presupuesto de F-147

`R-CAJA-HIPOTESIS`: `resumen` de la v63 (223 caracteres, NO cambia); `ambito` +
`tesoreria.albaranes_pendientes_neto`; la `regla` (no medida) gana: «el CP no es caja de la obra;
el personal va en el devengo como recurso: no sumes nóminas de la cartera» y «los albaranes, netos
por proveedor». Fichas (N11-N13): `albaranes_pendientes_neto` NUEVA (recomendada; grano, clave,
`suma` en importes, `no_sumable` en `meses_antiguedad`; cómo sale el residuo: Σ sobrefacturado − Σ
compensado; 2 preguntas cortas: «Cuanto queda de verdad por facturar de albaranes en la obra X»,
«Cuando se pagaran los albaranes pendientes de la obra X»); `compras.v_pbi_albaranes_sin_facturar`
avisa: solo líneas > 0, el pendiente real es el neto por proveedor; las tres `devengo_*`: «`CP`
no es caja de la obra»; `tesoreria.efectos` y `efectos_restringidos_mes`: «en la caja de una obra
el personal va por el devengo del recurso: no es lo que falta». `version` 64 con su nota. La ficha
recomendada nueva sube el enrutado: `PRESUPUESTO_MAX` sube EXACTAMENTE lo medido, con su línea de
historia (F-140 lo hizo igual); el resto del presupuesto no cambia.

## 8. Despliegue (MANUAL, tras el review) y riesgos

Imagen y job; `ingest` de `iva` y `dvf` ANTES de `build-tesoreria`; R30; `publicar-diccionario`
con la imagen ya en el job; `check-*`; MCP reiniciado; R31. Vuelta atrás: `r20261029-1340`.
**Riesgos.** (1) La IA no abre la ficha: `resumen` y `regla` la nombran. (2) Doble fraccionamiento
(`30 60 90` y H24). (3) Tests de F-140, al día con su porqué. (4) Código nuevo en `coestr`: al
master, declarado. (5) `dvf` no marca anuladas. (6) H21 casa por fecha de emisión (F-040). (7) La
fórmula del pendiente vive en `compras/01` y `09`: la ata un test. (8) FIFO es SUPOSICIÓN: la
avalan el 93 % de facturas del mes del albarán y que deja 7,96 de 8,76 en los dos últimos meses
(LIFO, 6,1 de más de un mes). (9) Las dos líneas de `R-ALBARAN-ABSURDO` ya NO están en `raw.dcapro`
(29-10): el filtro se queda; retirar la regla es otro trabajo. (10) El CP incluye LEVANTAMIENTO
(1,91) y SEGURO T.R.C. (0,19).

## 9. Decisiones

**Cerradas (el humano, 27-10)**: D1, D3-D7, D10 (A); H26 (A); H24/H25 fraccionamiento; H14
`MENSUAL`; H21 como riesgo. D2, D8 y D9, sustituidas por N1-N3. **N1-N8 (PARADA 1)**: N1
coeficiente: contrato, master 9, master 11; N2 IVA: contrato y H12 = MANUAL > ficha > 21 % solo
para la base sin él (el MANUAL NO pisa el contrato); N3 retención del contrato y H10 solo para la
base sin ella; N4 la obra-mes lleva IVA, retención y bases `SIN`; N5 avisos (F-040, AdP); N6
`include_columns`; N7 H13 por contrato de compra, fuera; N8 H20 a fin del mes del albarán y H27
(6 meses). Detalle en `progress/spec_F-150.md` §8. **N9-N10 (tras la PARADA de T11)**: N9 hueco
NETO POR OBRA con `MEDIA_OBRA` e IVA y retención por peso de contrato; N10 gramática real de
`coestr`; R30 sin umbral de cobertura del coeficiente del contrato (§9 del informe).

**N11-N13, aprobadas por el humano el 29-10** (medido: `progress/spec_F-150.md` §10):
- **N11 · Albaranes NETOS por (obra, proveedor), suelo 0**: objeto propio con grano (obra,
  proveedor, contrato, mes) para fechar H20/H27; FIFO; `AC`/`PROF` (NOTA: 0 en las 21 obras);
  desde `raw` (`compras` se construye después: daría el pendiente de AYER); solo las obras de la
  receta; `tras_cierre` por la propia H20. Descartado: columnas del corte (sin fecha) y LIFO.
- **N12 · El CP no es caja de la obra** (ni en el devengo ni en la cartera): en el devengo, por
  `categoria` (ya publicada; una marca la duplicaría) y fuera de H02; en la cartera, la parte CP
  de cada efecto por la categoría de las partidas de su factura (§5.8), en dos columnas del corte
  (no en `tesoreria.efectos`: se construye antes y `compras.vencimientos` fija sus columnas). Su
  caja, F-154.
- **N13 · El personal va por el devengo del RECURSO**: la receta no suma nóminas de la cartera ni
  las da por ausentes (textos, sin columnas). **N13-b, plazo del personal (decisión del líder,
  29-10, por la prisa del humano; opción D del informe §10)**: sin hipótesis nueva; va con H02
  `CI` y un aviso en la receta. El personal no se identifica limpio en el devengo (por nombre de
  partida, ~6,03 M EUR de los 12,83 de CI; ni código estándar ni naturaleza en `descompuestos`).
- **N14 · SEGUNDA TANDA, el saldo de partida (paso 0; respuestas del humano del 29-10, §10.5)**:
  CON IVA y opcional (H28); AGR por sus ORIGINALES como hipótesis (H29: rompe
  `R-TESORERIA-ESTADO` a propósito y se declara; con `ORIGINALES` los AGR con obra no se suman
  para no contarlos dos veces); retenciones, efectos propios; personal: **decisión del líder**,
  `raw.hmores.tot` de recursos PERSONA internos hasta el último cierre (Sigrid guarda el precio de
  cada parte: varía por año en 458 de 545 recursos; no hay otra tabla de histórico). §5.9.
