# F-150 · Diseño (la receta de la caja, fase 1)

Mediciones: `progress/spec_F-150.md` (§8, 27-10). Requisitos: `requirements.md`. Decisiones: §9
(D1, D3-D7, D10 cerradas; **N1-N8 nuevas, a confirmar en la PARADA 1**). Parte de F-140 (v62).

## 1. Encaje y límite

Amplía `tesoreria` (F-140) sin objetos de consumo nuevos: columnas, dos tablas `raw` (`iva` y la
cabecera de `dvf`), una ficha con la RECETA y una regla que remite a ella. El ETL publica
ingredientes (coeficiente, IVA y retención del CONTRATO son DATOS de Sigrid) y la IA aplica las
hipótesis en el orden de la receta.

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
fijado a ninguna obra, ni regla del peso de H10, ni `importe_adjudicado` (N3), ni H13 por
contrato (N7, siguiente paso).

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
- **Coeficientes del contrato (N1)**, gemelo de `leer_formula_plazo`: `SEPARADOR_SEGMENTOS =
  r"\|\|"`, `SEPARADOR_CAMPOS = "|"`, `REGEX_PORCENTAJE_COEF = r"^-?[0-9]+(\.[0-9]+)?$"`,
  `CODIGO_COEF_GG = "COEF_RECGG"`, `CODIGO_COEF_BI = "COEF_RECBI"`, `PALABRA_BAJA = "BAJA"`.
  `CoeficientesContrato(NamedTuple)`: `gg`, `bi`, `baja`, `otros` (`Decimal | None`),
  `reconocido`. `leer_coeficientes_contrato(texto)` y `factor_coeficientes(c)` según R7 (HALF_UP).
  Tests: las formas vistas (1,19; `...Industrial|23.79` -> otros, 1,2379), baja negativa, vacío,
  coma decimal y segmento sin número.
- `FUENTES_COEFICIENTE = ("CONTRATO", "MASTER_CERT", "MASTER_VENTA", "SIN")`;
  `AMBITO_COEFICIENTE = {"MASTER_CERT": 9, "MASTER_VENTA": 11}`; `coeficiente_venta(...) ->
  tuple[Decimal | None, str]` (R9). `FUENTES_DATO_CONTRATO = ("CONTRATO", "SIN")`;
  `porcentaje_iva(fraccion)`: `None` -> `None`, si no `ROUND(fraccion × 100, 4)` (0 es 0).
  `importe_con_coeficiente` e `importe_por_porcentaje`: `_redondear(...)`. El reparto con
  coeficientes es el MISMO `repartir_pendiente` de F-140.
- **Hueco (N6)**: `hueco_facturacion(real_con_coeficientes, facturado) -> tuple[Decimal,
  Decimal]`: `(max(0, r − f), max(0, f − r))` al céntimo; `None` cuenta 0.
- `MOTIVO_H12_FICHA = "Ficha de la obra (tipo de IVA)"`. `resolver_hipotesis` no cambia.

El SQL lleva los literales del dominio (regex, códigos, fuentes, `9`, `11`, `ROUND(…, 6)`, orden
del `COALESCE`, `GREATEST(0, …)`, motivo de H12) y los tests los comparan (patrón de F-135).

## 5. Ingesta y SQL

**5.1 · `raw.iva` y `raw.dvf`.** `TableSpec` gana `include_columns: tuple[str, ...] = ()`;
`_build_table_spec` lo lee y `_ingest_one_table`, si no está vacío, se queda solo con esas
columnas; falla antes de `ensure_raw_table` si hay `include_columns` y `exclude_columns` a la vez
o si una incluida no está en el esquema de Sigrid (R17; tests con un esquema falso, sin red).
`iva`: entero, sin incremental (`sigrid_tablas.md` no le da `tiemod`), `iva` en tanto por uno.
`dvf` (~330 columnas): `include_columns: [ide, cla, entide, cenide, ctride, fecdoc, totbas, totiva,
totdoc]` (+ `tiemod` si existe). T1 mide antes en Sigrid (solo lectura): filas, columnas, `iva`
en fracción, valores de `cla` (rectificativas, anuladas), cobertura de `ctride` y `cenide`.

**5.2 · `06` (N1, N2).** Funciones en `00_setup.sql`, `IMMUTABLE`, con `COMMENT`:
`tesoreria.fn_coeficientes(f TEXT) RETURNS NUMERIC[]` (`{gg, bi, baja, otros}`, NULL si no se
reconoce) y `tesoreria.fn_coeficientes_reconocidos(f TEXT) RETURNS BOOLEAN`. `06` gana
`coeficientes_texto`, `coeficientes_reconocidos`, `coeficiente_gg`, `_bi`, `_baja`, `_otros`
(NUMERIC(9,4)), `coeficiente_contrato` (NUMERIC(12,6)), `iva_id` e `iva_porcentaje`
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

**5.5 · `07`, el hueco de facturación (N6, H26).** **6 bis · `_dev_hueco`**, por (obra, grupo),
grupo = contrato de la partida o, sin él, NULL: `real` = Σ (real a origen hasta el último cierre
de cada partida VENTA en `mart.fact_seguimiento_mensual`, la misma fuente que
`real_origen_corte`) × su `coeficiente_venta` (partidas sin coeficiente: aparte, en
`venta_real_sin_coeficiente`); `facturado` = Σ `dvf.totbas` con `raw.obr ob ON ob.cenide =
dvf.cenide` (obra) y grupo `NULLIF(dvf.ctride, 0)` si ese contrato es de la obra, si no NULL; sin
corte de fecha (lo facturado tras el cierre sigue en la cartera: §8, riesgo 6). Por grupo,
`GREATEST(0, real − facturado)` y `GREATEST(0, facturado − real)`. `devengo_corte_obra` gana (VENTA;
NULL en COSTE) las columnas de R23: sumas de los grupos; IVA y retención del grupo × su
porcentaje del contrato (redondeo al final); bases `SIN` = hueco de los grupos sin el dato.

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
| H26 | NUEVA · Venta ejecutada pendiente de facturar | OPCION `[INCLUIR, NO_INCLUIR]` | `INCLUIR` | medido 27-10: 15,8 M EUR netos en 21 obras; lo facturado por delante no se cobra |
| H14 | Defecto | OPCION | `MENSUAL` | día 20 del mes siguiente; casi seguro (humano), lo confirma AdP |
| H20 | Opciones `[FIN_MES_ALBARAN, EXCLUIR]` | OPCION | `FIN_MES_ALBARAN` | factura del mismo mes que el albarán en el 93 % (7 % el siguiente; proformas 94/6), sobre 239 M EUR (27-10) |
| H27 | NUEVA · Antigüedad máxima de lo pendiente de facturar | MESES | `6` | lo más antiguo es casi siempre albarán sin enlazar con su factura, no deuda (como H17); lo revisa Control de Costes |

Todas `validado: false`, `admite_obra: true`; ingrediente de H24/H25 `tesoreria.plazos_forma_pago`,
de H26 `tesoreria.devengo_corte_obra`, de H20 y H27 `compras.v_pbi_albaranes_sin_facturar`. Ejemplos de cabecera: `[[1,
50], [2, 50]]` (H08), `[[3, 50], [4, 50]]` (H25). H03/H08 mueven el DOCUMENTO; H24/H25, el dinero.

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
(`30 60 90` y H24): la receta los compone. (3) Tests de F-140: al día con su porqué. (4)
**Gramática de `coestr`**: T11 lista las formas reales; una no reconocida cae al master; una baja
en positivo sumaría; más de 6 partidas distintas, PARADA (R29). (5) El hueco exige que `dvf` sea
la facturación completa (anuladas, rectificativas): T1 y T11, frente a 15,8 M EUR. (6) **H21 casa
por fecha de emisión**: una certificación de un mes cerrado facturada tras el cierre se restaría
dos veces (real a origen y `cartera_emitida_tras_cierre`); hoy 0 en cobros: no se cambia, F-040
traerá el mes de la certificación. (7) Los albaranes viejos son casi siempre falta de enlace con
su factura (`docoritip` cubre el 32,5 % de las líneas): H27 los aparta, no los borra.

## 9. Decisiones

**Cerradas (el humano, 27-10)**: D1, D3-D7, D10 (A); H26 (A); H24/H25 fraccionamiento; H14
`MENSUAL`; H21 como riesgo. D2, D8 y D9, sustituidas por N1-N3.

**NUEVAS, a confirmar en la PARADA 1** (Juan Romero, 27-10, y lo medido por el líder):
- **N1 · Coeficiente: contrato, master 9, master 11** (recomendada; sustituye a D2). «Cada
  contrato tiene sus coeficientes»; el 9 «no es un referente» en fase 0. Reproduce el master a 4
  decimales salvo 6 partidas. Alternativa (solo master): sin desglose ni porqué de las 6.
- **N2 · IVA: contrato de la partida; si no, H12 = MANUAL > ficha de la obra > 21 %**
  (recomendada; sustituye a D8): coincide al 100 % con `cer` y `dvf`, también en las mixtas. El
  MANUAL NO pisa el contrato, solo la base sin él (aplanar rompería las casetas al 21 % de la 0696).
- **N3 · Retención del contrato; H10 (F-140) solo para la base sin ella** (recomendada; sustituye
  a D9 e `importe_adjudicado`). Sin `coegar` ni recargo es `SIN` (en las 3 obras mixtas, DEFECTO 0).
- **N4 · La obra-mes lleva IVA y retención ya sumados más la base `SIN`** (recomendada, como D4).
  **N5 · Fuera y avisado**: revisión de precios (F-040); H13/H14 con AdP. H09 sigue por obra.
- **N6 · Hueco por contrato dentro de la obra** (recomendada: IVA y retención de cada contrato)
  frente a solo por obra; `include_columns` (recomendada) frente a `dvf` entera menos la lista.
- **N7 · H13 por contrato de compra** (`importe_iva / importe_base` de
  `condiciones_contrato_compra`; sin contrato, el 5,5 %): recomendada, pero NO cabe aquí (el
  devengo de coste no va por contrato de compra) ni la ha confirmado AdP: feature propia.
- **N8 · Albaranes sin facturar** (recomendada): H20 fecha la factura a fin del mes del albarán y
  H27 (6 meses) excluye y declara lo más antiguo. Los 8,23 M EUR de F-140 venían de
  `compras.fact_compras_linea`; lo bueno es 56,9 M EUR (`progress/spec_F-150.md` §8).
