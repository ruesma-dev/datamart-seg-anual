# F-150 · La receta de la caja (fase 1)

Mediciones: `progress/spec_F-150.md` §8-§10 e `impl_F-150.md` §1-§3. Decisiones: `design.md` §9.
**Objetivo**: que la IA pase el devengo de una obra a caja SIEMPRE en el mismo orden (la receta),
con los coeficientes, el IVA y la retención del CONTRATO de cada partida (`raw.obrparpar.ctride`).
Sin caja proyectada: es F-151. **Perfil**: pares `[meses, porcentaje]` que reparten un importe entero.

## La receta (D1, D7, N5)
- R1. Cada hipótesis debe declarar `paso_receta` (uno de `PASOS_RECETA`); SI falta o no es válido,
  ENTONCES `validar_catalogo` da error; el YAML asigna cada código al paso de `design.md` §6.
- R2. La ficha de `tesoreria.hipotesis_caja` debe contener la receta: los pasos numerados en el orden
  de `PASOS_RECETA` y, en cada tramo, los códigos de ese paso (test que cruza YAML y ficha).
- R3. La receta debe nombrar sus ingredientes (las tres `devengo_*` y sus columnas nuevas de R14,
  R20, R23 y R36, las dos `condiciones_contrato_*`, `tesoreria.efectos`, `cartera_emitida_tras_cierre`
  y `tesoreria.albaranes_pendientes_neto`) y decir: COSTE se paga y VENTA se cobra; los perfiles reparten el importe entero; la retención
  va sobre la base sin IVA; el devengo va sin IVA; nunca un coeficiente medio de obra; H10 y H12
  solo sobre la base sin dato del contrato; redondear solo al final (test por frases clave).
- R4. (N5) La receta debe AVISAR de lo que no cubre: la revisión de precios y lo certificado fuera
  del coeficiente (F-040); H13/H14 pendientes de AdP; lo facturado por delante y los albaranes de
  más de H27 meses o `tras_cierre` no son caja (se declaran); el CP tampoco (N12, va a F-154).
- R5. (D7) El `resumen` de `R-CAJA-HIPOTESIS` debe nombrar la receta, `tesoreria.hipotesis_caja`,
  `tesoreria.hipotesis_caja_obra`, la cartera y los niveles `DEFECTO`, `OBRA` y `USUARIO` en ≤ 230
  caracteres, y su `regla` empezar remitiendo a la receta; la puerta de F-147 pasa (R32).
- R6. (D1) `docs/CONVENTIONS.md` y `ARCHITECTURE.md`: una receta puede ir en una ficha; los valores, en el YAML.

## El coeficiente por partida (N1, D3, D4, D6)

- R7. (N10) `leer_coeficientes_contrato(texto)` (dominio) debe leer `coestr` por líneas
  `CODIGO|etiqueta|valor||base` y clasificar POR CÓDIGO según `CLASE_POR_CODIGO` (`design.md` §4,
  `impl_F-150.md` §1.2; `RET*` -> `retencion`, que NO es coeficiente); vacío o `NULL` -> sin dato;
  SI un código es desconocido o un valor no es número, ENTONCES no reconocido (falla cerrado).
  `factor_coeficientes` = `ROUND((1 + (gg + bi + otros) / 100) × (1 + baja / 100), 6)` (1,19;
  baja en CASCADA: 1,038) si está reconocido y tiene algún coeficiente; si no, `None`.
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

- R29. (Hecho, T11) ANTES de la receta, contraste en solo lectura en las 21 obras: `coestr` no
  reconocido 0, contrato de otra obra 0, ≤ 6 partidas con coeficiente del contrato ≠ master 11 y
  el hueco dentro del rango del día (suelo a factor 1, techo + 0,26 × la venta sin coeficiente).
- R30. Contraste MANUAL tras el build frente a `impl_F-150.md` §2 y R29: 18.997 partidas VENTA,
  pendiente ~132,4 y con coeficientes ~143,3 M EUR, cada coeficiente con su fuente, IVA y retención
  del contrato en ≥ 96 % del pendiente de 19 obras, 0 fallos de las guardas y la duración. (N11-N12,
  29-10) Albaranes de las 21 obras: bruto ~56,9, sobrefacturado ~48,2, neto ~8,76 (0686: ~0,19),
  de más de 6 meses ~0,52 y `tras_cierre` ~0,47 M EUR; CP pendiente ~14,5; cartera viva CP ~0,03.
- R31. CUANDO se pregunte al MCP, en conversación nueva, por la caja de una obra con coeficientes,
  debe seguir los siete pasos (coeficientes, IVA y retención del contrato, hueco de H26, albaranes
  NETOS y los de más de H27 meses aparte, sin CP, sin nóminas, avisos de R4) y declarar las 27
  hipótesis: MANUAL (humano; la 0686 y otra obra).
- R32. Fichas al día (`paso_receta`, columnas, «27», `raw.iva`, `raw.dvf`, N11-N13), diccionario v64
  (`PRESUPUESTO_MAX` sube solo lo que mida la ficha nueva), `CLAUDE.md`, `docs/ARCHITECTURE.md` y
  `azure-apps/datamart_seg_anual.md`; `bash harness/init.sh` en verde (pytest, cobertura, mutación).

## Albaranes netos, CP y personal (N11-N13, 29-10)

- R33. (N11) `neto_fifo(importes)` (dominio) debe recibir los pendientes de un (obra, proveedor)
  en orden (fecha, línea) y devolver, por posición, el resto de cada positiva cuando Σ |negativas|
  compensa primero las MÁS ANTIGUAS; negativas y `None` dan 0, ningún resto < 0 ni > su línea, y
  Σ = max(0, Σ importes) al céntimo.
- R34. (N11) `tesoreria.albaranes_pendientes_neto` debe publicar, para las obras de
  `devengo_corte_obra` (COSTE), una fila por (obra, proveedor, contrato, `mes_albaran`) con bruto
  (Σ > 0), sobrefacturado (Σ |< 0|), compensado (R33), neto, `meses_antiguedad` (al mes del build)
  y `tras_cierre`, leyendo `raw` (series `AC`/`PROF`, fórmula del pendiente IGUAL a la de
  `compras/01`, `abs(tot)` y `abs(pendiente)` < 1e8); sin proveedor, la línea no compensa.
- R35. SI en un (obra, proveedor) Σ neto ≠ max(0, Σ bruto − Σ sobrefacturado), o un compensado
  sale de [0, bruto], ENTONCES `09` falla con su recuento y quedan las filas de ayer.
- R36. (N12) La receta y las fichas de las `devengo_*` deben decir que `CP` NO es caja de la obra
  (se excluye por `categoria` y se declara); H02 pierde la clave `CP`; y `devengo_corte_obra`
  (COSTE) debe publicar `cartera_viva_coste_proporcional` y
  `cartera_emitida_tras_cierre_coste_proporcional` (la parte CP de cada efecto por las partidas
  de su factura, `design.md` §5.8), que el paso 7 resta.
- R37. (N13) La receta, la `regla` de `R-CAJA-HIPOTESIS` y las fichas de `tesoreria.efectos` y
  `efectos_restringidos_mes` deben decir que el personal entra por el devengo del RECURSO: no se
  suman nóminas de la cartera ni se dan por ausentes; y avisar de que va con H02 `CI` (N13-b).
- R38. (N14, segunda tanda) `tesoreria.saldo_partida_obra` debe publicar por obra del universo, CON
  IVA y con `fecha_corte`, las columnas de `design.md` §5.9: lo cobrado y pagado REALIZADO (sin
  AGR), los AGR con obra, los ORIGINALES agrupados (`estado_codigo = 14`) vencidos y pendientes, la
  cuota CP de lo pagado y `personal_coste_partes` (`raw.hmores.tot`, PERSONA interna, ≤ cierre).
- R39. (N14) H28 `[CON_SALDO, SIN_SALDO]` (defecto `CON_SALDO`) y H29 `[ORIGINALES, AGR]` (defecto
  `ORIGINALES`) deben nacer en el paso nuevo `SALDO` (primero de `PASOS_RECETA`): 29 hipótesis.
- R40. (N14) La receta debe dar la fórmula del saldo del paso 0 (§5.9), decir que H29 es HIPÓTESIS
  que rompe `R-TESORERIA-ESTADO` a propósito, y que las retenciones entran al cobrarse o pagarse.
- R41. (N15, tercera tanda) `08` debe dar a H13 un valor SIGRID por obra = `ROUND(100 × Σ ivacuo / Σ
  tot, 2)` de sus líneas de factura de compra de 12 meses si Σ `tot` ≥ `UMBRAL_BASE_H13` (500.000),
  con `MOTIVO_H13_COMPRAS`; si no, DEFECTO; `iva_efectivo_compra` del dominio da lo mismo (test).
- R42. (N15) H30 `[COMPENSA_EMPRESA, MENSUAL_REDEME, ANUAL]` (defecto `COMPENSA_EMPRESA`, paso IVA,
  `validado: false`) debe nacer con el aviso de AdP y lo medido en la contabilidad: 30 hipótesis.
- R43. (N15) `saldo_partida_obra` debe publicar `iva_soportado_pagado`, `iva_repercutido_cobrado` y
  sus `_hasta_4t`, y la receta sumar al saldo el IVA neto ya recuperado según H30 (`design.md` §5.9).
