# F-150 · La receta de la caja (fase 1)

Mediciones: `progress/spec_F-150.md` §8-§11 e `impl_F-150.md`. Decisiones: `design.md` §9. **Objetivo**:
que la IA pase el devengo de una obra a caja SIEMPRE en el mismo orden (la receta), con los datos del
CONTRATO de cada partida. Sin caja proyectada (F-151). **Perfil**: pares `[meses, porcentaje]`.

## La receta (D1, D7, N5)
- R1. Cada hipótesis debe declarar `paso_receta` (uno de `PASOS_RECETA`); SI falta o no es válido,
  ENTONCES `validar_catalogo` da error; el YAML asigna cada código al paso de `design.md` §6.
- R2. La ficha de `tesoreria.hipotesis_caja` debe contener la receta: los pasos numerados en el orden
  de `PASOS_RECETA` y, en cada tramo, los códigos de ese paso (test que cruza YAML y ficha).
- R3. La receta debe nombrar sus ingredientes (las `devengo_*` y sus columnas de R14, R20, R23, R36,
  R45-R46 y R49, las `condiciones_contrato_*`, `tesoreria.efectos` y `albaranes_pendientes_neto`) y
  decir: COSTE se paga y VENTA se cobra; los perfiles reparten el importe entero; retención sobre la
  base sin IVA; devengo sin IVA; nunca un coeficiente medio de obra; H10 y H12 solo sobre la base sin
  dato del contrato; redondear solo al final (test por frases clave).
- R4. (N5) La receta debe AVISAR de lo que no cubre: la revisión de precios y lo certificado fuera
  del coeficiente (F-040); H13/H14 pendientes de AdP; lo facturado por delante y los albaranes de
  más de H27 meses o `tras_cierre` no son caja (se declaran); el CP tampoco (N12, va a F-154).
- R5. (D7) El `resumen` de `R-CAJA-HIPOTESIS` debe nombrar la receta, `tesoreria.hipotesis_caja`,
  `tesoreria.hipotesis_caja_obra`, la cartera y los niveles `DEFECTO`, `OBRA` y `USUARIO` en ≤ 230
  caracteres, y su `regla` empezar remitiendo a la receta; la puerta de F-147 pasa (R32).
- R6. (D1) `docs/CONVENTIONS.md` y `ARCHITECTURE.md`: una receta puede ir en una ficha; los valores, en el YAML.

## El coeficiente por partida (N1, D3, D4, D6)
- R7. (N10) `leer_coeficientes_contrato(texto)` (dominio) lee `coestr` por líneas `CODIGO|etiqueta|
  valor||base` y clasifica POR CÓDIGO (`CLASE_POR_CODIGO`, §4; `RET*` es retención); vacío o `NULL`,
  sin dato; código desconocido o valor no numérico, no reconocido. `factor_coeficientes` = `ROUND((1
  + (gg + bi + otros) / 100) × (1 + baja / 100), 6)` si está reconocido y tiene alguno; si no, `None`.
- R8. `tesoreria.condiciones_contrato_cliente` debe publicar `coeficientes_texto`, `_reconocidos`,
  `coeficiente_gg`, `_bi`, `_otros`, `_baja`, `coeficiente_contrato` y `retencion_coestr`, con
  funciones SQL de literales iguales al dominio (test, patrón de `fn_plazo_dias`).
- R9. `coeficiente_venta(...)` debe devolver `(contrato, "CONTRATO")` si existe; si no, el del 9
  (`MASTER_CERT`, importe no `None` ni 0), el del 11 (`MASTER_VENTA`) o `(None, "SIN")`; el del
  master, `ROUND(oficial / importe, 6)` con `oficial` ausente = importe.
- R10. (D3) `sql/tesoreria/` debe leer `stg.presupuesto` solo por obra, `ambito_id IN (9, 11)` y V.
- R11. `tesoreria.devengo_pendiente_partida` debe publicar, en VENTA (NULL en COSTE),
  `contrato_cliente_id` (de la misma obra), `coeficiente_venta`, `fuente_coeficiente`,
  `coeficiente_master` y `pendiente_con_coeficientes = ROUND(pendiente × coeficiente_venta, 2)`.
- R12. (D6) SI una partida VENTA con pendiente > 0 no tiene coeficiente, ENTONCES el SQL falla con su
  recuento antes de vaciar nada. R13. Ninguna columna nueva casa con `PATRON_COLUMNA_DE_CAJA` ni
  aplica un valor de hipótesis (tests R6/R16 de F-140).
- R14. (D4) `devengo_pendiente_obra_mes` debe publicar, en VENTA, `importe_pendiente_con_coeficientes`
  (repartido con `repartir_pendiente`) y `coeficiente_venta` (6 dec., NULL si el pendiente es 0); la
  guarda de la suma comprueba también la suma con coeficientes.
- R15. `R-VENTA-COEFICIENTES` debe incluir en su `ambito` las tres `devengo_*` (la `regla`, sin
  excepciones), y sus fichas decir que lo que lleva coeficientes no se suma ni compara con el
  coste, lo ejecutado ni la venta sin ellos.

## El IVA y la retención por partida (N2, N3, N4)
- R16. `tables_sigrid.yaml` debe ingerir `raw.iva` entero y la CABECERA de `raw.dvf`, sin `tiemod`;
  fichas en `raw.yaml`; `TOTAL_TABLAS` = 80. R17. CUANDO una tabla declare `include_columns`, la
  ingesta debe traer solo esas; SI declara también `exclude_columns` o una no existe, ENTONCES falla.
- R18. `condiciones_contrato_cliente` debe publicar `iva_id` (`NULLIF(ivaide, 0)`) e `iva_porcentaje`
  (`raw.iva.iva` × 100, 4 dec.; 0 es 0; sin catálogo, NULL).
- R19. `devengo_pendiente_partida` debe publicar, en VENTA, `iva_porcentaje` y `retencion_porcentaje`
  del contrato con `fuente_iva`/`fuente_retencion` (`CONTRATO` o `SIN`).
- R20. (N4) `devengo_pendiente_obra_mes` debe publicar, en VENTA, `importe_iva_contrato` e
  `importe_retencion_contrato` (Σ parte con coeficientes `CONTRATO` × % / 100, redondeado al final)
  y `base_sin_iva_contrato` / `base_sin_retencion_contrato` (Σ de las `SIN`).
- R21. `08` debe dar a H12 un valor SIGRID desde la ficha de la obra (`raw.obr.ivaide` ->
  `raw.iva`, × 100) con su motivo literal; MANUAL > SIGRID > DEFECTO y H10 de F-140, sin cambios.

## La venta ejecutada pendiente de facturar (N6, H26)
- R22. (N9) `hueco_facturacion(real_con_coeficientes, facturado)` (dominio) debe devolver
  `(pendiente, por_delante)`, ≥ 0 y al céntimo (lo facturado por delante nunca se cobra); y
  `coeficiente_medio(pares)` = Σ (real × coef) / Σ real a 6 decimales, `None` si Σ real es 0.
- R23. (N9) `tesoreria.devengo_corte_obra` debe publicar, en VENTA (NULL en COSTE), el hueco NETO
  POR OBRA de `design.md` §5.5 (nunca por contrato): `venta_real_origen_con_coeficientes` (sin
  coeficiente, `MEDIA_OBRA`, declarada en `venta_real_media_obra`), `facturado_origen` (Σ
  `dvf.totbas`), `venta_pendiente_facturar` y `facturado_por_delante` (R22), y el IVA, la retención
  y las bases sin ellos del hueco por el peso de cada contrato.
- R24. H26 debe nacer `OPCION` `[INCLUIR, NO_INCLUIR]`, defecto `INCLUIR`, COBRO, paso DEVENGO; y
  (N8) H27, antigüedad máxima de lo pendiente de facturar, `MESES`, defecto 6, PAGO, paso CARTERA;
  las dos `admite_obra: true`, `validado: false`: 27 hipótesis.

## El catálogo y el reparto en varios meses (D5)
- R25. El dominio debe admitir `PERFIL_MESES`: pares `[meses, porcentaje]` no vacíos, `meses` entero
  0-120 estrictamente creciente, `porcentaje` > 0, ≤ 100 y ≤ 2 decimales, suma exacta 100; SI no,
  ENTONCES un error por fallo, en `valor_defecto` y en `obras`.
- R26. H03 y H08 deben pasar a `PERFIL_MESES` (`[[0, 100]]`, `[[1, 100]]`) y nacer H24 (PAGO) y H25
  (COBRO), el FRACCIONAMIENTO, con `[[0, 100]]`, paso PLAZO, `validado: false`, `admite_obra: true`.
- R27. CUANDO `obras` dé un perfil a una obra, el paso debe cargarlo en `hipotesis_caja_manual` y
  `hipotesis_caja_obra` publicarlo tal cual (JSON, OBRA/MANUAL); `unidad` admite `PERFIL_MESES`.
- R28. El YAML debe decir: H10 y H12, el valor del contrato va en el devengo y la hipótesis solo
  cubre la base sin él (H12: ficha de la obra, si no 21 %); H13, propuesta pendiente de AdP; H14,
  `MENSUAL` (día 20 del mes siguiente); H15, solo formas con varios vencimientos; H20 con opciones
  `[FIN_MES_ALBARAN, EXCLUIR]`; (N11) H20 y H27, ingrediente `tesoreria.albaranes_pendientes_neto`.

## Verificación, diccionario y documentación
- R29. (Hecho, T11; `impl_F-150.md` §2) Contraste previo de solo lectura en las 21 obras: `coestr`
  no reconocido 0, contrato de otra obra 0, ≤ 6 partidas contrato ≠ master 11, hueco en su rango.
- R30. Contraste MANUAL tras cada build frente a `impl_F-150.md` §2 y las tablas de T20, T29, T34 y
  T40 (cifras de cada tanda), con 0 fallos de las guardas y la duración.
- R31. CUANDO se pregunte al MCP, en conversación nueva, por la caja de una obra, debe seguir los ocho
  pasos de la receta y declarar las 30 hipótesis: MANUAL (humano; la 0686 y otra obra).
- R32. Fichas, `version` del diccionario (`PRESUPUESTO_MAX` sube solo lo que midan las fichas nuevas),
  `CLAUDE.md`, `docs/` y `azure-apps/datamart_seg_anual.md` al día; `init.sh` en verde.

## Albaranes netos, CP y personal (N11-N13, 29-10)
- R33. (N11) `neto_fifo(importes)` (dominio): los pendientes de un (obra, proveedor) en orden (fecha,
  línea); Σ |negativas| compensa primero las positivas MÁS ANTIGUAS; negativas y `None` dan 0,
  ningún resto < 0 ni > su línea, y Σ = max(0, Σ importes) al céntimo.
- R34. (N11) `tesoreria.albaranes_pendientes_neto`: una fila por (obra de `devengo_corte_obra` COSTE,
  proveedor, contrato, `mes_albaran`) con bruto, sobrefacturado, compensado (R33), neto,
  `meses_antiguedad` y `tras_cierre`, desde `raw` (`AC`/`PROF`, el pendiente de `compras/01`, < 1e8).
- R35. SI en un (obra, proveedor) Σ neto ≠ max(0, Σ bruto − Σ sobrefacturado) o un compensado sale
  de [0, bruto], ENTONCES `09` falla con su recuento y quedan las filas de ayer.
- R36. (N12) Receta y fichas de las `devengo_*`: `CP` NO es caja de la obra (fuera por `categoria`,
  declarado); H02 sin `CP`; `devengo_corte_obra` (COSTE) publica `cartera_viva_coste_proporcional`
  y `cartera_emitida_tras_cierre_coste_proporcional` (§5.8), que el paso 7 resta.
- R37. (N13) La receta, la `regla` de `R-CAJA-HIPOTESIS` y las fichas de `tesoreria.efectos` y
  `efectos_restringidos_mes` deben decir que el personal entra por el devengo del RECURSO: no se
  suman nóminas de la cartera ni se dan por ausentes. (El aviso N13-b de H02 `CI` lo sustituye R47.)
- R38. (N14) `tesoreria.saldo_partida_obra`: por obra del universo, CON IVA y con `fecha_corte`, las
  columnas de §5.9 (cobrado y pagado REALIZADO sin AGR, AGR con obra, ORIGINALES agrupados vencidos y
  pendientes, cuota CP de lo pagado y `personal_coste_partes`: PERSONA interna, ≤ cierre).
- R39. (N14) H28 `[CON_SALDO, SIN_SALDO]` y H29 `[ORIGINALES, AGR]` (defectos los primeros) nacen en
  el paso nuevo `SALDO`, primero de `PASOS_RECETA`: 29 hipótesis.
- R40. (N14) La receta da la fórmula del saldo del paso 0 (§5.9), dice que H29 rompe
  `R-TESORERIA-ESTADO` a propósito y que las retenciones entran al cobrarse o pagarse.
- R41. (N15) `08` da a H13 un valor SIGRID por obra = `ROUND(100 × Σ ivacuo / Σ tot, 2)` de sus
  facturas de compra de 12 meses si Σ `tot` ≥ `UMBRAL_BASE_H13` (500.000), con `MOTIVO_H13_COMPRAS`;
  si no, DEFECTO; `iva_efectivo_compra` del dominio da lo mismo (test).
- R42. (N15) H30 `[MENSUAL_REDEME, COMPENSA_EMPRESA, ANUAL]` (defecto `MENSUAL_REDEME`, paso IVA,
  `validado: false`) nace con el aviso de AdP y lo medido en la 4700: 30 hipótesis.
- R43. (N15) `saldo_partida_obra` publica `iva_soportado_pagado`, `iva_repercutido_cobrado` y sus
  `_hasta_4t` y `_hasta_4m`; la receta suma al saldo el IVA neto ya recuperado según H30 (§5.9).
## Personal a fin de mes y coste por contrato (N16-N17, cuarta tanda, 31-10; `design.md` §5.10-§5.11)
- R44. (N16) `cuota_personal(personal, real)` (dominio) = `min(1, ROUND(personal / real, 6))` si los dos > 0;
  si no, 0. R45. `devengo_pendiente_partida` publica, en COSTE (NULL en VENTA), `cuota_personal`,
  `pendiente_personal` = `ROUND(pendiente × cuota, 2)` y `fuente_personal` (`PARTES`, `SIN_PARTES`,
  `CP` con cuota 0); personal = Σ `raw.hmores.tot` PERSONA interna (el filtro de `10`) ≤ cierre.
- R46. `devengo_pendiente_obra_mes` publica `importe_pendiente_personal` (COSTE; mismo reparto) y el
  corte `pendiente_personal` y `pendiente_enlazado_contrato`; la guarda de la suma mira el personal.
- R47. Receta y `regla`: el personal se paga el ÚLTIMO día del mes de su devengo, sin H03, plazo,
  H24, H06 ni IVA (regla fija: siguen 30 hipótesis); el H13 va sobre la base sin personal; sale N13-b.
- R48. (N17) `fracciones_contrato(pendiente, pendientes_servir)` (dominio): enlazado = min(pendiente,
  Σ ps > 0), fracción de c = enlazado / pendiente × ps_c / Σ ps; `repartir_por_contratos(importe,
  fracciones)` da `ROUND(importe × f, 2)` por contrato y el resto, ≥ 0, a `None` (sin contrato).
- R49. `tesoreria.devengo_pendiente_contrato_mes`: una fila por (obra, mes, `categoria`, contrato o
  NULL) con el pendiente de COSTE sin CP ni personal repartido por R48 entre los contratos de
  compra de la partida (`raw.ctrpro.paride`, misma obra, no Terminado ni Rescindido, en
  `condiciones_contrato_compra`), con lo pendiente de servir por (contrato, partida) (`canser`).
- R50. SI Σ por obra de R49 ≠ Σ (`importe_pendiente` − `importe_pendiente_personal`) sin CP, o hay
  un importe < 0, ENTONCES `07` falla con su recuento antes de vaciar nada.
- R51. Receta (pasos 4-5), H01, H02 y H06: con contrato, H01/H15/H04 y la retención del contrato;
  sin él, H02 por `categoria` y H06; el corte declara la parte enlazada.
- R52. Contraste de SOLO LECTURA (T40) antes del diccionario: personal ~5,64 M EUR (0686 ~0,21);
  enlazado ~48,9 de 112,85 (43 %; 0686 ~1,64 de 2,39); si se aparta > 5 %, PARADA.
