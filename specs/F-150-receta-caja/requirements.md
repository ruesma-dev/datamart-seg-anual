# F-150 · La receta de la caja (fase 1)

Mediciones: `progress/spec_F-150.md` §8-§9 e `impl_F-150.md` §1-§3. Decisiones: `design.md` §9.
**Objetivo**: que la IA pase el devengo de una obra a caja SIEMPRE en el mismo orden (la receta),
cobrando la venta CON los coeficientes, el IVA y la retención del CONTRATO de cada partida, sin
perder la venta ejecutada sin facturar y fraccionando en meses. Sin caja proyectada: es F-151.

Vocabulario: **contrato de una partida**, el de `raw.obrparpar.ctride` (`raw.obrctr.ide`) de su
obra; **coeficiente del master**, `importe_oficial / importe` de `stg.presupuesto` (ámbito 9 u 11,
versión V); **perfil**, pares `[meses, porcentaje]` que reparten un importe entero.

## La receta (D1, D7, N5)

- R1. Cada hipótesis debe declarar `paso_receta`, uno de los siete pasos; SI falta o no es uno de
  ellos, ENTONCES `validar_catalogo` da error y el paso no publica nada. `tesoreria.hipotesis_caja`
  lo publica y el YAML real asigna cada código al paso de `design.md` §6 (test de la tabla entera).
- R2. La `descripcion` de la ficha `tesoreria.hipotesis_caja` debe contener la receta: siete pasos
  numerados en el orden de `PASOS_RECETA`, y en el tramo de cada paso los códigos cuyo
  `paso_receta` es ese (test que cruza el YAML con la ficha).
- R3. La receta debe nombrar sus ingredientes (las tres `devengo_*` y sus columnas nuevas de R14,
  R20 y R23, las dos `condiciones_contrato_*`, `tesoreria.efectos`, `cartera_emitida_tras_cierre`,
  `compras.v_pbi_albaranes_sin_facturar`)
  y decir: COSTE se paga y VENTA se cobra; los perfiles reparten el importe entero; la retención
  va sobre la base sin IVA; el devengo va sin IVA; nunca un coeficiente medio de obra; H10 y H12
  solo sobre la base sin dato del contrato; redondear solo al final (test por frases clave).
- R4. (N5) La receta debe AVISAR de lo que no cubre: la revisión de precios y lo certificado fuera
  del coeficiente (F-040); H13 y H14 pendientes de AdP; lo facturado por delante no se cobra; los
  albaranes de más de H27 meses no son caja (se declaran con su importe).
- R5. (D7) El `resumen` de `R-CAJA-HIPOTESIS` debe nombrar la receta, `tesoreria.hipotesis_caja`,
  `tesoreria.hipotesis_caja_obra`, la cartera y los niveles `DEFECTO`, `OBRA` y `USUARIO` en ≤ 230
  caracteres, y su `regla` empezar remitiendo a la receta. `PRESUPUESTO_MAX` de F-147 queda en
  30.873 y la puerta pasa (medida esperada 30.864).
- R6. (D1) `docs/CONVENTIONS.md` y `docs/ARCHITECTURE.md` deben recoger la excepción acotada: una
  receta de objetos del datamart puede ir en una ficha; los valores, en `config/hipotesis_caja.yaml`.

## El coeficiente por partida (N1, D3, D4, D6)

- R7. (N10) `leer_coeficientes_contrato(texto)` (dominio) debe leer `coestr` por LÍNEAS (`\r\n`
  o `\n`, recortadas; las vacías se ignoran), cada una `CODIGO|etiqueta|valor||base` (código =
  campo 1, valor = campo 3), y devolver `gg`, `bi`, `otros`, `baja`, `retencion` y `reconocido`:
  POR CÓDIGO, `COEF_RECGG` -> `gg` (también la forma «Gastos Generales+Beneficio Industrial»),
  `COEF_RECBI` -> `bi`, `COEF_RECCC` y `COEF_RECSYS` -> `otros` (sumados), `COEF_DESADJ` ->
  `baja`, `RETN`/`RETESP`/`RETNT` -> `retencion` (NO es coeficiente). Vacío o `NULL` -> sin dato;
  SI un código es desconocido o un valor no es número, ENTONCES no reconocido (falla cerrado).
  `factor_coeficientes(c)` = `ROUND((1 + (gg + bi + otros) / 100) × (1 + baja / 100), 6)` si está
  reconocido y tiene algún coeficiente, `None` si no: GG y BI se SUMAN (1,19) y la baja va en
  CASCADA sobre el subtotal de contrata (1,19 × (1 − 0,1277) = 1,038).
- R8. `tesoreria.condiciones_contrato_cliente` debe publicar `coeficientes_texto` (`coestr` tal
  cual, con sus etiquetas), `coeficientes_reconocidos`, `coeficiente_gg`, `_bi`, `_otros`,
  `_baja`, `coeficiente_contrato` y `retencion_coestr` (la retención declarada en `coestr`, dato
  aparte), con funciones SQL de literales iguales al dominio (test, patrón de `fn_plazo_dias`).
- R9. `coeficiente_venta(contrato, importe_cert, oficial_cert, importe_venta, oficial_venta)` debe
  devolver `(contrato, "CONTRATO")` si el del contrato existe; si no, el del 9 con `MASTER_CERT` si
  su importe no es `None` ni 0; si no, el del 11 con `MASTER_VENTA`; si no, `(None, "SIN")`. El del
  master es `ROUND(oficial / importe, 6)`, con `oficial` ausente = importe.
- R10. (D3) `sql/tesoreria/` debe leer `stg.presupuesto` solo filtrando obra, `ambito_id IN (9,
  11)` y `fase_num` = la versión V (un test rechaza cualquier lectura sin los tres filtros).
- R11. `tesoreria.devengo_pendiente_partida` debe publicar, en VENTA, `contrato_cliente_id` (solo
  si es de la misma obra), `coeficiente_venta`, `fuente_coeficiente`, `coeficiente_master` (aunque
  mande el contrato) y `pendiente_con_coeficientes = ROUND(pendiente × coeficiente_venta, 2)`; en
  COSTE, NULL.
- R12. (D6) SI una partida VENTA con `pendiente > 0` no tiene coeficiente, ENTONCES el SQL debe
  fallar con su recuento antes de vaciar las tablas de consumo.
- R13. Ninguna columna nueva debe casar con `PATRON_COLUMNA_DE_CAJA`, y el SQL nuevo no puede
  aplicar un valor de hipótesis (los tests R6/R16 de F-140 siguen pasando sobre `07`).
- R14. (D4) `tesoreria.devengo_pendiente_obra_mes` debe publicar
  `importe_pendiente_con_coeficientes` (el de cada partida repartido con `repartir_pendiente`) y
  `coeficiente_venta` (cociente con `importe_pendiente`, 6 decimales, NULL si este es 0); en
  COSTE, NULL. La guarda de la suma comprueba también, por (obra, VENTA), la suma con coeficientes.
- R15. `R-VENTA-COEFICIENTES` debe incluir en su `ambito` las tres `devengo_*` (la `regla`, sin
  excepciones), y sus fichas decir que lo que lleva coeficientes no se suma ni compara con el
  coste, lo ejecutado ni la venta sin ellos.

## El IVA y la retención por partida (N2, N3, N4)

- R16. `config/tables_sigrid.yaml` debe ingerir `iva` entero en `raw.iva` (N2) y la CABECERA de
  `dvf` en `raw.dvf` (N6, R17), los dos sin `tiemod`; fichas en `raw.yaml`, `TOTAL_TABLAS` = 80.
- R17. CUANDO una tabla declare `include_columns`, la ingesta debe traer solo esas; SI declara
  también `exclude_columns` o una de ellas no existe en Sigrid, ENTONCES falla antes de crear nada.
- R18. `tesoreria.condiciones_contrato_cliente` debe publicar `iva_id` (`NULLIF(ivaide, 0)`) e
  `iva_porcentaje` (`raw.iva.iva` × 100, 4 decimales; 0 es 0, inversión del sujeto pasivo); sin
  `iva_id` o sin fila en el catálogo, NULL.
- R19. `tesoreria.devengo_pendiente_partida` debe publicar, en VENTA, `iva_porcentaje` y
  `retencion_porcentaje` del contrato de la partida, con `fuente_iva` y `fuente_retencion` =
  `CONTRATO` si hay valor y `SIN` si no; en COSTE, NULL.
- R20. (N4) `tesoreria.devengo_pendiente_obra_mes` debe publicar, en VENTA,
  `importe_iva_contrato` e `importe_retencion_contrato` (Σ de la parte con coeficientes de cada
  partida `CONTRATO` × su porcentaje / 100, redondeado solo al final) y `base_sin_iva_contrato` y
  `base_sin_retencion_contrato` (Σ de la de las partidas `SIN`); en COSTE, NULL.
- R21. `08_hipotesis_caja_obra.sql` debe dar a H12 un valor SIGRID desde la ficha de la obra
  (`raw.obr.ivaide` -> `raw.iva`, × 100) con su motivo literal; el orden MANUAL > SIGRID > DEFECTO
  no cambia, y H10 conserva la regla de F-140 (N3 retira la regla del peso de la D9).

## La venta ejecutada pendiente de facturar (N6, H26)

- R22. (N9) `hueco_facturacion(real_con_coeficientes, facturado)` (dominio) debe devolver
  `(pendiente, por_delante)`, ≥ 0 y al céntimo (lo facturado por delante nunca se cobra); y
  `coeficiente_medio(pares)` = Σ (real × coef) / Σ real a 6 decimales, `None` si Σ real es 0.
- R23. (N9) `tesoreria.devengo_corte_obra` debe publicar, en VENTA, NETO POR OBRA (nunca por
  contrato): `venta_real_origen_con_coeficientes` (real a origen hasta el cierre de cada partida ×
  su coeficiente de R9; sin ninguno, × el `coeficiente_medio` de su obra, fuente `MEDIA_OBRA`),
  `venta_real_media_obra` (esa parte, declarada), `facturado_origen` (Σ `dvf.totbas`, rectificativas
  incluidas; obra por `dvf.cenide = obr.cenide`), `venta_pendiente_facturar` y
  `facturado_por_delante` (R22 por obra), `iva_pendiente_facturar_contrato` y
  `retencion_pendiente_facturar_contrato` (el hueco repartido por el peso de cada contrato en la
  venta real × coef de la obra, × su porcentaje) y `base_pendiente_facturar_sin_iva_contrato` /
  `_sin_retencion_contrato` (el peso sin el dato); en COSTE, NULL.
- R24. H26 debe nacer `OPCION` `[INCLUIR, NO_INCLUIR]`, defecto `INCLUIR`, COBRO, paso DEVENGO; y
  (N8) H27, antigüedad máxima de lo pendiente de facturar, `MESES`, defecto 6, PAGO, paso CARTERA;
  las dos `admite_obra: true`, `validado: false`: 27 hipótesis.

## El catálogo y el reparto en varios meses (D5)

- R25. El dominio debe admitir la unidad `PERFIL_MESES`: lista no vacía de pares `[meses,
  porcentaje]`, `meses` entero de 0 a 120 y estrictamente creciente, `porcentaje` > 0 y ≤ 100 con
  2 decimales como mucho, suma exacta 100; SI no, ENTONCES un error por cada fallo, igual en
  `valor_defecto` y en la sección `obras`.
- R26. H03 y H08 deben pasar a `PERFIL_MESES` (`[[0, 100]]` y `[[1, 100]]`), y nacer H24 (PAGO) y
  H25 (COBRO), el FRACCIONAMIENTO de cada pago y cada cobro, en `PERFIL_MESES` con `[[0, 100]]`,
  paso PLAZO, `validado: false` y `admite_obra: true`; su `descripcion` dice «fraccionamiento».
- R27. CUANDO `obras` dé un perfil a una obra, el paso debe cargarlo en
  `tesoreria.hipotesis_caja_manual` y `hipotesis_caja_obra` publicarlo tal cual (JSON),
  OBRA/MANUAL. `unidad` admite `PERFIL_MESES` (`ALTER ... TYPE VARCHAR(20)` idempotente) y
  `hipotesis_caja_obra` publica las 27 por obra (tests de F-140 al día).
- R28. El YAML debe decir: en H10 y H12, que el valor del contrato va en el devengo y la hipótesis
  solo cubre la base sin él (H12: ficha de la obra, si no 21 %; Control de Costes puede fijar la
  obra); en H13, que es propuesta pendiente de AdP (N7); H14 con defecto `MENSUAL` (día 20 del mes
  siguiente, pendiente de AdP); en H15 (D10), que solo aplica a formas con varios vencimientos;
  (N8) H20 con opciones `[FIN_MES_ALBARAN, EXCLUIR]`, defecto `FIN_MES_ALBARAN`, e ingrediente
  `compras.v_pbi_albaranes_sin_facturar` (56,9 M EUR en las 21 obras, no los 8,23 de F-140).

## Verificación, diccionario y documentación

- R29. ANTES de la receta (T12), en solo lectura en las 21 obras y con el dominio de T5: líneas de
  `coestr` no reconocidas (0 esperadas), contrato de otra obra (0), partidas con pendiente > 0 cuyo
  coeficiente del contrato difiere del master 11 en > 0,005 (≤ 6; medidas 5) y Σ (real × coef −
  facturado) con `MEDIA_OBRA` dentro del rango DEL DÍA (humano, 28-10): suelo = ese Σ con la venta
  real sin coeficiente a factor 1; techo = suelo + 0,26 × esa venta (28-10: 15,50-15,75); SI no, PARA.
- R30. Contraste MANUAL tras el build frente a `progress/impl_F-150.md` §2 y el valor de R29:
  18.997 partidas VENTA, pendiente ~132,4 y con coeficientes ~143,3 M EUR, cada coeficiente con su
  fuente (`CONTRATO`, `MASTER_CERT`, `MASTER_VENTA`; `MEDIA_OBRA` en el hueco), IVA y retención del
  contrato en ≥ 96 % del pendiente de 19 obras, 0 fallos de las guardas y la duración del build.
- R31. CUANDO se pregunte al MCP, en conversación nueva, por la caja de una obra con coeficientes,
  debe seguir los siete pasos (coeficientes, IVA y retención del contrato, hueco de H26, albaranes
  de más de H27 meses aparte, avisos de R4) y declarar las 27 hipótesis: MANUAL (humano).
- R32. Fichas al día (`paso_receta`, columnas nuevas, «27», `raw.iva`, `raw.dvf`), diccionario
  v63, `CLAUDE.md`, `docs/ARCHITECTURE.md` y `azure-apps/datamart_seg_anual.md` (consume `iva` y
  `dvf`); `bash harness/init.sh` en verde (pytest, cobertura y mutación `estandar`).
