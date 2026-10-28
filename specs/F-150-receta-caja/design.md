# F-150 · Diseño (la receta de la caja, fase 1)

Mediciones: `progress/spec_F-150.md` §8-§9, `progress/impl_F-150.md` §1-§3. Decisiones: §9.

## 1. Encaje y límite

Amplía `tesoreria` (F-140) sin objetos de consumo nuevos: columnas, dos tablas `raw` (`iva`, la
cabecera de `dvf`), la RECETA en una ficha y una regla que remite a ella. El ETL publica DATOS
(coeficiente, IVA y retención del contrato) y la IA aplica las hipótesis en el orden de la receta.

**Fronteras.** F-151 ejecutará la receta (aquí no hay caja). **F-040**: líneas de `dvf`,
certificaciones y su casado por mes de certificación, importe a certificar, revisión de precios y
lo certificado fuera del coeficiente; aquí solo la CABECERA de `dvf` para el hueco. **F-099**
(pendiente): F-150 le adelanta el desglose y el enlace partida -> contrato; F-099 conserva
expedientes, adjudicado y fechas (el líder lo anota). H13/H14: de AdP. Ni `sigrid-api` ni el MCP.

## 2. Ficheros

**Modificar**
- `domain/proyeccion_caja.py` (§4); `config/hipotesis_caja.yaml` (§6, cabecera); lector y carga
  (`infrastructure/config/hipotesis_caja_yaml.py`, `postgres/hipotesis_caja_sql.py`): `paso_receta`.
- Ingesta (§5.1): `etl_sigrid/domain/entities.py` (`TableSpec.include_columns`),
  `etl_sigrid/application/steps/ingest_raw_step.py`, `config/tables_sigrid.yaml` (`iva`, `dvf`) y
  `config/diccionario/raw.yaml` (sus fichas, patrón de `raw.auxcob`).
- `sql/tesoreria/00_setup.sql` (al final, idempotente, sin `DROP` ni `GRANT`): funciones de §5.2;
  `ALTER COLUMN unidad TYPE VARCHAR(20)` y `paso_receta VARCHAR(12)` en `hipotesis_caja`; las
  columnas de §5.2-§5.5 con `ADD COLUMN IF NOT EXISTS`.
- `sql/tesoreria/06_condiciones_contrato_cliente.sql` (§5.2), `07_devengo_pendiente.sql` (§5.3-
  §5.5), `08_hipotesis_caja_obra.sql` (rama H12 en el bloque SIGRID y el `COMMENT`, §5.6).
- `config/diccionario/tesoreria.yaml` y `00_global.yaml` (§7; nota de versión: `raw.iva` y
  `raw.dvf`, 80 tablas; `version` 62 -> 63).
- Tests de F-140 y del recuento: `test_f140_{hipotesis,paso,diccionario,sql}.py` (H03/H08, H14,
  H20, `1..28`, 23 -> 27, columnas, rama H12), `test_f066_ingesta_raw.py` (80).
- `docs/CONVENTIONS.md`, `docs/ARCHITECTURE.md`, `CLAUDE.md` (mapa) y
  `azure-apps/datamart_seg_anual.md` (consume `iva` y `dvf`; commit local allí, sin push).

**Crear**: `tests/test_f150_{receta,coeficiente,contrato,hueco,ingesta,perfil,sql,diccionario}.py`.

**No se tocan**: `sql/stg/*`, `sql/mart/*`, `01`-`05`, permisos (el esquema ya se concede entero;
`raw` no), `main.py`, `domain/diccionario.py`, `test_f147_*` (−9), `H21` (§8, riesgo 6). Ni IVA
fijado a ninguna obra, ni regla del peso de H10, ni `importe_adjudicado` (N3), ni H13 por contrato (N7).

## 3. La receta (texto de la ficha de `tesoreria.hipotesis_caja`, tras su párrafo actual)

Se copia tal cual (redacción ajustable sin perder piezas de R2-R4). Va en `descripcion`, que
`describir_tabla` sirve entera y F-147 no mide; con F-151 quedará para cálculos especiales.

> **LA RECETA: DE DEVENGO A CAJA, EN ESTE ORDEN** (F-150). Cada hipótesis dice en `paso_receta`
> en qué paso se aplica; decláralas TODAS con valor y nivel (`R-CAJA-HIPOTESIS`). COSTE se paga
> (PAGO) y VENTA se cobra (COBRO). Los perfiles (`PERFIL_MESES`, pares `[meses, porcentaje]` que
> suman 100) reparten el importe ENTERO: `[[0, 100]]` es todo en el mes de partida y
> `[[1, 50], [2, 50]]`, la mitad uno y dos meses después. Redondea solo al final.
> 1. DEVENGO: el del mes, `importe_pendiente` de `tesoreria.devengo_pendiente_obra_mes` (H18; o
>    `importe_plan_restante`), lo retrasado sin perfil según H19, situado el día H23. Sin IVA. Si
>    H26 es INCLUIR, suma al cobro del primer mes pendiente la venta ejecutada sin facturar
>    (`venta_pendiente_facturar` de `tesoreria.devengo_corte_obra`, ya con coeficientes); lo
>    `facturado_por_delante` NO se cobra: decláralo.
> 2. DOCUMENTO: el devengo de cada mes se factura (pago, perfil H03) o se certifica (cobro,
>    perfil H08). Su mes es el del IVA del paso 6.
> 3. COEFICIENTES (solo cobro): se certifica y se cobra CON los coeficientes del contrato de cada
>    partida: `importe_pendiente_con_coeficientes` (por partida, `pendiente_con_coeficientes` y
>    `fuente_coeficiente` de `tesoreria.devengo_pendiente_partida`), nunca un coeficiente medio de
>    obra; jamás lo compares con el coste ni con lo ejecutado (`R-VENTA-COEFICIENTES`). **Aviso**:
>    la revisión de precios y lo que se certifica fuera del coeficiente NO están (F-040).
> 4. PLAZO: desde el documento, la forma de pago del contrato (H01, `condiciones_contrato_compra`;
>    con varios vencimientos, H15) o, sin contrato, la de su categoría (H02), con los días fijos y
>    meses sin pago del proveedor (H04) y el retraso real (H05); el cobro, a H09
>    (`condiciones_contrato_cliente`) y menos la morosidad H22. Cada pago y cada cobro se
>    FRACCIONA en meses con H24 (pago) o H25 (cobro).
> 5. RETENCIÓN, sobre la base SIN IVA: en el cobro, `importe_retencion_contrato` (y
>    `retencion_pendiente_facturar_contrato`) ya es la del contrato; H10 solo se aplica a las bases
>    `sin_retencion_contrato`. En el pago, H06. Se devuelve según H11 o H07.
> 6. IVA: en el cobro, `importe_iva_contrato` (y `iva_pendiente_facturar_contrato`) es el del
>    contrato (0 % en inversión del sujeto pasivo); H12 solo se aplica a las bases
>    `sin_iva_contrato`. En el pago, H13. Se cobra o paga con su documento; la liquidación con
>    Hacienda (repercutido menos soportado) va según H14. **Aviso**: H13 y H14 están pendientes de
>    validar con Administración (AdP): dilo al dar la caja.
> 7. CARTERA, SIN DUPLICAR: suma lo PREVISTO vivo de `tesoreria.efectos` en su vencimiento (H16;
>    el previsto antiguo, H17) y los albaranes sin facturar de `compras.v_pbi_albaranes_sin_facturar`
>    (sin las líneas de `R-ALBARAN-ABSURDO`; H20: la factura, a fin del mes del albarán y el plazo
>    desde ahí; lo de más de H27 meses NO es caja: exclúyelo y declara su importe), y quita del
>    primer mes pendiente lo emitido tras el cierre (H21, `cartera_emitida_tras_cierre`, CON IVA).

## 4. Dominio (`domain/proyeccion_caja.py`, sin infraestructura)

- `PASOS_RECETA = ("DEVENGO", "DOCUMENTO", "COEFICIENTES", "PLAZO", "RETENCION", "IVA",
  "CARTERA")`. `paso_receta` pasa a `_CAMPOS_OBLIGATORIOS`; `_errores_de_fila` rechaza uno fuera
  de la lista. `Hipotesis` gana `paso_receta: str = ""` AL FINAL; `construir_catalogo` lo rellena.
- `UNIDADES` += `"PERFIL_MESES"`; `_error_de_valor` llama a `_error_de_perfil(valor)` (R25;
  `MAX_MESES_PERFIL = 120`; pares lista o tupla de 2; `meses` no booleano; suma con
  `Decimal(str(p))`). Cada fallo, su mensaje.
- **Coeficientes del contrato (N1, N10)**, gemelo de `leer_formula_plazo`: `SEPARADOR_LINEAS =
  r"\r?\n"`, `SEPARADOR_CAMPOS = "|"`, `REGEX_PORCENTAJE_COEF = r"^-?[0-9]+(\.[0-9]+)?$"` y
  `CLASE_POR_CODIGO = {"COEF_RECGG": "gg", "COEF_RECBI": "bi", "COEF_RECCC": "otros",
  "COEF_RECSYS": "otros", "COEF_DESADJ": "baja", "RETN": "retencion", "RETESP": "retencion",
  "RETNT": "retencion"}`. `CoeficientesContrato(NamedTuple)`: `gg`, `bi`, `otros`, `baja`,
  `retencion` (`Decimal | None`), `reconocido`. `leer_coeficientes_contrato` y
  `factor_coeficientes` según R7 (HALF_UP). Tests: todas las formas reales de `impl_F-150.md` §1.2
  (1,19; base `TOTAL EJECUCION CONTRATA`; 23,79 -> gg; `RETN`; `COEF_DESADJ` −12,77 -> 1,038; vacío;
  `NULL`), código desconocido y valor no numérico.
- `FUENTES_COEFICIENTE = ("CONTRATO", "MASTER_CERT", "MASTER_VENTA", "SIN")`;
  `AMBITO_COEFICIENTE = {"MASTER_CERT": 9, "MASTER_VENTA": 11}`; `coeficiente_venta(...) ->
  tuple[Decimal | None, str]` (R9). `FUENTES_DATO_CONTRATO = ("CONTRATO", "SIN")`;
  `porcentaje_iva(fraccion)`: `None` -> `None`, si no `ROUND(fraccion × 100, 4)` (0 es 0).
  `importe_con_coeficiente` e `importe_por_porcentaje`: `_redondear(...)`. El reparto con
  coeficientes es el MISMO `repartir_pendiente` de F-140.
- **Hueco (N6, N9)**: `hueco_facturacion(real_con_coeficientes, facturado) -> tuple[Decimal,
  Decimal]`: `(max(0, r − f), max(0, f − r))` al céntimo, `None` cuenta 0; `coeficiente_medio(pares
  (real, coef)) -> Decimal | None` (R22); `FUENTE_MEDIA_OBRA = "MEDIA_OBRA"` (solo en el hueco).
- `MOTIVO_H12_FICHA = "Ficha de la obra (tipo de IVA)"`. `resolver_hipotesis` no cambia.

El SQL lleva los literales del dominio (regex, códigos, fuentes, `9`, `11`, `ROUND(…, 6)`, orden
del `COALESCE`, `GREATEST(0, …)`, motivo de H12) y los tests los comparan (patrón de F-135).

## 5. Ingesta y SQL

**5.1 · `raw.iva` y `raw.dvf`.** `TableSpec` gana `include_columns: tuple[str, ...] = ()`;
`_build_table_spec` lo lee y `_ingest_one_table`, si no está vacío, se queda solo con esas
columnas; falla antes de `ensure_raw_table` si hay `include_columns` y `exclude_columns` a la vez
o si una incluida no está en el esquema de Sigrid (R17; tests con un esquema falso, sin red).
`iva`: entero, sin incremental (`sigrid_tablas.md` no le da `tiemod`), `iva` en tanto por uno.
`dvf` (151 columnas, 15.665 filas, sin `tiemod`: medido en T1): `include_columns: [ide, cla,
entide, cenide, ctride, fecdoc, totbas, totiva, totdoc]`; `cla` 1024 = rectificativas, ya netas en
`totbas`; no hay marca de anulada. `iva`: 1.562 filas, 30 columnas, sin `tiemod`.

**5.2 · `06` (N1, N2).** Funciones en `00_setup.sql`, `IMMUTABLE`, con `COMMENT`:
`tesoreria.fn_coeficientes(f TEXT) RETURNS NUMERIC[]` (`{gg, bi, otros, baja, retencion}`, NULL
si no se reconoce; partido por `E'\r?\n'`) y `tesoreria.fn_coeficientes_reconocidos(f TEXT)
RETURNS BOOLEAN`. `06` gana `coeficientes_texto`, `coeficientes_reconocidos`, `coeficiente_gg`,
`_bi`, `_otros`, `_baja`, `retencion_coestr` (NUMERIC(9,4)), `coeficiente_contrato`
(NUMERIC(12,6), la cascada de R7), `iva_id` e `iva_porcentaje`
(`ROUND((i.iva * 100)::NUMERIC, 4)`, `LEFT JOIN raw.iva i`).

**5.3 · `07`, coeficiente (N1, D3, D6).** Misma transacción; los pasos de F-140 solo ganan
columnas. La guarda de entrada exige además `raw.obrparpar`, `raw.obr`, `raw.dvf` y
`tesoreria.condiciones_contrato_cliente` (la construye `06` justo antes).
- **2 bis · `_dev_coef`**: por (obra, partida) de VENTA con plan en V o real a origen, desde
  `stg.presupuesto pp JOIN _dev_version v ON pp.obra_id = v.obra_id AND pp.ambito_id IN (9, 11)
  AND pp.fase_num = v.version_master WHERE v.concepto = 'VENTA'`: `SUM(importe)` y
  `SUM(importe_oficial)` por ámbito (`FILTER`) -> `coeficiente_master` y su fuente. `ANALYZE`.
- **2 ter · `_dev_contrato`**: por partida VENTA, `raw.obrparpar pp ON pp.ide = partida_id JOIN
  tesoreria.condiciones_contrato_cliente k ON k.contrato_cliente_id = NULLIF(pp.ctride, 0) AND
  k.obra_id = obra_id` -> contrato, coeficiente, IVA y retención. Uno de otra obra no se enlaza
  (T11 los cuenta: esperado 0). `coeficiente_venta = COALESCE(contrato, master)` y su fuente.
- **4 · `_dev_partida`** gana, en VENTA, las columnas de R11 y R19; NULL en COSTE. **Guarda** `DO`
  (D6): VENTA con `pendiente > 0` sin coeficiente -> `RAISE` con su recuento (hoy 0).

**5.4 · `07`, IVA y retención (N2-N4).** `fuente_iva`/`fuente_retencion`: `CONTRATO` si el valor
no es NULL, si no `SIN`. **5 · `_dev_reparto`** gana `parte_con_coef`: en `partes`,
`ROUND(d.pendiente_con_coeficientes * pr.importe_mes / d.total_perfil, 2)` y el resto al último
mes; en `sin_perfil`, entero al primer mes. `devengo_pendiente_obra_mes` gana (VENTA; NULL en
COSTE) `importe_pendiente_con_coeficientes = SUM(parte_con_coef)`, `coeficiente_venta =
ROUND(con / sin, 6)`, `importe_iva_contrato = ROUND(SUM(parte_con_coef * iva_porcentaje) FILTER
(fuente_iva = 'CONTRATO') / 100, 2)`, `base_sin_iva_contrato = SUM(parte_con_coef) FILTER
(fuente_iva = 'SIN')` y lo mismo con la retención. **La guarda de la suma** se extiende a la suma
con coeficientes. Coste estimado +10-60 s sobre 118,9 s (R30).

**5.5 · `07`, el hueco de facturación (N9, H26).** **6 bis · `_dev_hueco`**, NETO POR OBRA:
`real` = Σ (real a origen hasta el último cierre de cada partida VENTA, la fuente de
`real_origen_corte`) × su `coeficiente_venta` (R9); sin ninguno, × la media ponderada de su obra
(`MEDIA_OBRA`; sin ninguna en la obra, 1), esa parte en `venta_real_media_obra`; `facturado` = Σ
`dvf.totbas` con `raw.obr ob ON ob.cenide = dvf.cenide`, sin corte de fecha (§8, riesgo 6). Por obra, `GREATEST(0, real − facturado)` y `GREATEST(0, facturado − real)`. El IVA y
la retención del hueco: peso de cada contrato = su real × coef / el de la obra (partidas sin
contrato, grupo propio); `iva_pendiente_facturar_contrato = ROUND(hueco × Σ peso × iva / 100, 2)`
sobre los contratos con IVA, y la base sin él = hueco × peso restante (igual la retención). Por
contrato NO: solo 4.665 de 15.665 facturas llevan `ctride` y el casado infla el hueco (18,59).

**5.6 · `08`, H12 SIGRID (N2).** Rama más en el `UNION ALL` SIGRID: `raw.obr ob JOIN raw.iva i ON
i.ide = NULLIF(ob.ivaide, 0)` -> `ROUND((i.iva * 100)::NUMERIC, 4)`, `MOTIVO_H12_FICHA`.

## 6. El catálogo (`config/hipotesis_caja.yaml`)

`paso_receta` de las 27: DEVENGO H18, H19, H23, H26 · DOCUMENTO H03, H08 · COEFICIENTES ninguna
(es dato) · PLAZO H01, H02, H04, H05, H09, H15, H22, H24, H25 · RETENCION H06, H07, H10, H11 ·
IVA H12, H13, H14 · CARTERA H16, H17, H20, H21, H27.

| Código | Cambio | Unidad | Defecto | `fuente_defecto` |
|---|---|---|---|---|
| H03 | Perfil del mes de devengo a la factura del proveedor | PERFIL_MESES | `[[0, 100]]` | todo en el mes de devengo (propuesta) |
| H08 | Perfil del mes de producción a la certificación | PERFIL_MESES | `[[1, 100]]` | todo al mes siguiente (propuesta) |
| H24 | NUEVA · FRACCIONAMIENTO en meses de cada PAGO | PERFIL_MESES | `[[0, 100]]` | sin fraccionar; Sigrid no lo guarda (6 contratos con varios vencimientos) |
| H25 | NUEVA · FRACCIONAMIENTO en meses de cada COBRO | PERFIL_MESES | `[[0, 100]]` | sin fraccionar; 0 contratos con el cliente con varios vencimientos |
| H26 | NUEVA · Venta ejecutada pendiente de facturar | OPCION `[INCLUIR, NO_INCLUIR]` | `INCLUIR` | ~15,3 M EUR netos en 21 obras (27-10); lo facturado por delante no se cobra |
| H14 | Defecto | OPCION | `MENSUAL` | día 20 del mes siguiente; casi seguro (humano), lo confirma AdP |
| H20 | Opciones `[FIN_MES_ALBARAN, EXCLUIR]` | OPCION | `FIN_MES_ALBARAN` | factura del mismo mes que el albarán en el 93 % (7 % el siguiente; proformas 94/6), sobre 239 M EUR (27-10) |
| H27 | NUEVA · Antigüedad máxima de lo pendiente de facturar | MESES | `6` | lo más antiguo es casi siempre albarán sin enlazar con su factura, no deuda (como H17); lo revisa Control de Costes |

Todas `validado: false`, `admite_obra: true`; ingrediente de H24/H25 `plazos_forma_pago`, de H26
`devengo_corte_obra`, de H20/H27 `compras.v_pbi_albaranes_sin_facturar`. Ejemplos: `[[1, 50], [2,
50]]` (H08), `[[3, 50], [4, 50]]` (H25). H03/H08 mueven el DOCUMENTO; H24/H25, el dinero.

Textos: **H10** «La del contrato va en el devengo; esta solo cubre las bases
`sin_retencion_contrato`: la de la obra si es única (SIGRID), si no 0». **H12** «El del contrato
va en el devengo (0 % en ISP); esta solo cubre las bases `sin_iva_contrato`: la ficha de la obra
(SIGRID), si no 21 %; Control de Costes puede fijar la obra». **H13** añade «propuesta pendiente
de AdP: el IVA de cada contrato de compra (N7)». **H14** `descripcion` añade «mensual: día 20 del
mes siguiente». **H15** (D10) «solo formas con varios vencimientos; con uno, no aplica».

## 7. El diccionario y el presupuesto de F-147

`R-CAJA-HIPOTESIS` · `resumen` (223 caracteres, hoy 230): «No hay caja proyectada: sigue la
receta de la ficha de `tesoreria.hipotesis_caja`, sin repetir la cartera, y declara TODAS las
hipótesis de `tesoreria.hipotesis_caja_obra` con valor y nivel: DEFECTO, OBRA o USUARIO
(manda).» `regla`: empieza por «Sigue la RECETA de la ficha de `tesoreria.hipotesis_caja`, en su
orden»; `motivo` gana la frase de F-150. `R-VENTA-COEFICIENTES`: solo `ambito` + las `devengo_*`.

Fichas: `hipotesis_caja` (receta, `paso_receta`, «27»; 1.ª pregunta «Como se pasa paso a paso el
devengo de una obra a caja», 54 frente a 56 caracteres); `hipotesis_caja_obra` (567 filas, H12
SIGRID); `condiciones_contrato_cliente`; las tres `devengo_*` (`suma` en importes, `no_sumable` en
coeficientes y porcentajes, NULL = COSTE; las 6 partidas en que manda el contrato; el hueco);
`raw.iva` y `raw.dvf` (solo cabecera). Presupuesto: **30.864**.

## 8. Despliegue (MANUAL, tras el review) y riesgos

Imagen y job; `ingest` de `iva` y `dvf` ANTES de `build-tesoreria`; R30; `publicar-diccionario`
con la imagen ya en el job; `check-*`; MCP reiniciado; R31. Vuelta atrás: `r20261026-2111`.
**Riesgos.** (1) La IA no abre la ficha: `resumen` y `regla` la nombran. (2) Doble fraccionamiento
(`30 60 90` y H24): la receta los compone. (3) Tests de F-140: al día con su porqué. (4) Un código
nuevo en `coestr` cae al master y se declara (R7). (5) `dvf` no marca anuladas (T1). (6) **H21 casa
por fecha de emisión**: una certificación de un mes cerrado facturada tras el cierre se restaría
dos veces (real a origen y `cartera_emitida_tras_cierre`); hoy 0 en cobros: no se cambia, F-040
traerá el mes de la certificación. (7) Los albaranes viejos son casi siempre falta de enlace con
su factura (`docoritip` cubre el 32,5 % de las líneas): H27 los aparta, no los borra.

## 9. Decisiones

**Cerradas (el humano, 27-10)**: D1, D3-D7, D10 (A); H26 (A); H24/H25 fraccionamiento; H14
`MENSUAL`; H21 como riesgo. D2, D8 y D9, sustituidas por N1-N3.

**N1-N8, de la PARADA 1** (Juan Romero, 27-10, y lo medido por el líder):
- **N1 · Coeficiente: contrato, master 9, master 11** (sustituye a D2): «cada contrato tiene sus
  coeficientes»; el 9 «no es un referente» en fase 0; reproduce el master salvo 5-6 partidas.
- **N2 · IVA: contrato; si no, H12 = MANUAL > ficha > 21 %** (sustituye a D8): casa al 100 % con
  `cer` y `dvf`. El MANUAL NO pisa el contrato (aplanaría las casetas al 21 % de la 0696).
- **N3 · Retención del contrato; H10 solo para la base sin ella** (sustituye a D9). **N4** · La
  obra-mes lleva IVA y retención sumados y la base `SIN`. **N5** · Avisos: revisión de precios
  (F-040), H13/H14 (AdP). H09 sigue por obra.
- **N6** · `include_columns` para `dvf`. **N7** · H13 por contrato de compra (`importe_iva /
  importe_base`; sin contrato, 5,5 %): fuera, feature propia (sin enlace coste -> contrato; AdP).
- **N8 · Albaranes**: H20 a fin del mes del albarán; H27 (6 meses) aparta y declara lo antiguo.
  Los 8,23 M EUR de F-140 eran `compras.fact_compras_linea`; lo bueno, 56,9 M EUR.

**APROBADAS por el humano tras la PARADA de T11** (27-10, `impl_F-150.md` §1):
- **N9 · Hueco NETO POR OBRA** (no por contrato), mínimo 0 y lo negativo declarado; la venta real
  sin coeficiente entra con la media ponderada de su obra (`MEDIA_OBRA`, «si no existe puedes
  deducirlo»); IVA y retención por el peso de cada contrato. R29 mide contra esta definición.
- **N10 · Gramática real de `coestr`** (líneas `CODIGO|etiqueta|valor||base`, por código; `RET*`
  aparte; `COEF_DESADJ` en cascada; vacío o `NULL` = sin dato, cae al master; código desconocido,
  al master y declarado). R30 sin umbral de cobertura del coeficiente del contrato.
