# F-150 · La receta de la caja (fase 1)

Mediciones: `progress/spec_F-150.md` §8-§10 e `impl_F-150.md` §1-§3. Decisiones: `design.md` §9.
**Objetivo**: que la IA pase el devengo de una obra a caja SIEMPRE en el mismo orden (la receta),
con los coeficientes, el IVA y la retención del CONTRATO de cada partida (`raw.obrparpar.ctride`).
Sin caja proyectada: es F-151. **Perfil**: pares `[meses, porcentaje]` que reparten un importe entero.

## La receta (D1, D7, N5)

- R1. Cada hipótesis debe declarar `paso_receta`, uno de los siete pasos; SI falta o no es uno de
  ellos, ENTONCES `validar_catalogo` da error y el paso no publica nada. `tesoreria.hipotesis_caja`
  lo publica y el YAML real asigna cada código al paso de `design.md` §6 (test de la tabla entera).
- R2. La `descripcion` de la ficha `tesoreria.hipotesis_caja` debe contener la receta: siete pasos
  numerados en el orden de `PASOS_RECETA`, y en el tramo de cada paso los códigos cuyo
  `paso_receta` es ese (test que cruza el YAML con la ficha).
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

- R25. El dominio debe admitir la unidad `PERFIL_MESES`: lista no vacía de pares `[meses,
  porcentaje]`, `meses` entero de 0 a 120 y estrictamente creciente, `porcentaje` > 0 y ≤ 100 con
  2 decimales como mucho, suma exacta 100; SI no, ENTONCES un error por cada fallo, igual en
  `valor_defecto` y en la sección `obras`.
- R26. H03 y H08 deben pasar a `PERFIL_MESES` (`[[0, 100]]` y `[[1, 100]]`), y nacer H24 (PAGO) y
  H25 (COBRO), el FRACCIONAMIENTO de cada pago y cada cobro, en `PERFIL_MESES` con `[[0, 100]]`,
  paso PLAZO, `validado: false` y `admite_obra: true`; su `descripcion` dice «fraccionamiento».
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
