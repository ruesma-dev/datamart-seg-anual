# F-150 · La receta de la caja (fase 1)

Mediciones: `progress/spec_F-150.md` §8 (27-10, tras el correo de Juan Romero). Decisiones en
`design.md` §9: D1, D3-D7 y D10 cerradas; **N1-N8 NUEVAS, pendientes de la PARADA 1** (sustituyen
a D2, D8 y D9). **Objetivo**: que la IA pase el devengo de una obra a caja SIEMPRE en el mismo
orden (la receta), cobrando la venta CON los coeficientes, el IVA y la retención del CONTRATO de
cada partida, sin perder la venta ejecutada pendiente de facturar y fraccionando en varios meses.
Sin caja proyectada (F-140): la función que la calcula es F-151.

Vocabulario: **receta**, los siete pasos de `design.md` §3. **Contrato de una partida**: el de
`raw.obrparpar.ctride` (`raw.obrctr.ide`), de la misma obra. **Coeficiente del master**:
`importe_oficial / importe` de `stg.presupuesto` en el ámbito 9 o 11, versión V (F-140).
**Perfil**: pares `[meses, porcentaje]` que reparten un importe entero en el tiempo.

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

- R7. `leer_coeficientes_contrato(texto)` (dominio) debe devolver `gg`, `bi`, `baja`, `otros` y
  `reconocido`: segmentos por `||`, campos por `|`, porcentaje = último campo no vacío;
  `COEF_RECGG` -> `gg`, `COEF_RECBI` -> `bi`, etiqueta con `BAJA` -> `baja`, el resto -> `otros`
  (sumados); vacío o `NULL` -> todo `None`; SI un segmento no acaba en número, ENTONCES todo `None`
  y no reconocido (falla cerrado). `factor_coeficientes(c)` = `ROUND(1 + Σ / 100, 6)` si está
  reconocido, `None` si no: se SUMAN, no se multiplican (13 + 6 = 1,19).
- R8. `tesoreria.condiciones_contrato_cliente` debe publicar `coeficientes_texto` (`coestr` tal
  cual), `coeficientes_reconocidos`, `coeficiente_gg`, `_bi`, `_baja`, `_otros` y
  `coeficiente_contrato`, con funciones SQL de literales iguales al dominio (test, patrón de
  `fn_plazo_dias`).
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

- R16. `config/tables_sigrid.yaml` debe ingerir el catálogo `iva` entero en `raw.iva` (N2) y la
  CABECERA de las facturas de venta en `raw.dvf` (N6) con `include_columns` (R17); fichas en
  `config/diccionario/raw.yaml` y `TOTAL_TABLAS` = 80.
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

- R22. `hueco_facturacion(real_con_coeficientes, facturado)` (dominio) debe devolver
  `(pendiente, por_delante)`, los dos ≥ 0 y al céntimo: lo que se ejecutó y no se facturó, y lo
  facturado por delante (nunca se cobra).
- R23. `tesoreria.devengo_corte_obra` debe publicar, en VENTA, por obra y sumando contrato a
  contrato (partidas por su contrato; facturas por `dvf.ctride`; sin contrato, un grupo propio):
  `venta_real_origen_con_coeficientes` (real a origen hasta el cierre × coeficiente de R9),
  `facturado_origen` (Σ `dvf.totbas`, obra por `dvf.cenide = obr.cenide`),
  `venta_pendiente_facturar` y `facturado_por_delante` (R22), `iva_pendiente_facturar_contrato`,
  `retencion_pendiente_facturar_contrato`, `base_pendiente_facturar_sin_iva_contrato`,
  `base_pendiente_facturar_sin_retencion_contrato` (como R20) y
  `venta_real_sin_coeficiente` (lo no contado); en COSTE, NULL.
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

- R29. ANTES de escribir la receta (T12), en solo lectura en las 21 obras: formas de `coestr` no
  reconocidas, partidas con contrato de otra obra (0), coeficiente del contrato frente al master a
  4 decimales y el hueco de facturación; SI difieren más partidas que las 6 del líder (0676-B 1,
  0696 3, 0697 1, 0724 1) o el hueco neto se aparta de 15,8 M EUR más de un 5 %, ENTONCES PARA.
- R30. Contraste MANUAL tras el build frente a `progress/spec_F-150.md` §8: 18.997 partidas VENTA,
  pendiente 132,37 y con coeficientes ~143,20 M EUR, `CONTRATO` en ≥ 96 % del pendiente de 19
  obras, hueco ~15,8 M EUR, 0 fallos de las guardas, y la duración del primer `build-tesoreria`.
- R31. CUANDO se pregunte al MCP, en conversación nueva, por la caja de una obra con coeficientes,
  debe seguir los siete pasos, cobrar con coeficientes, IVA y retención del contrato y el hueco de
  H26, apartar y declarar los albaranes de más de H27 meses, dar los avisos de R4 y declarar las
  27 hipótesis: MANUAL (humano), anotado.
- R32. Fichas al día (`paso_receta`, columnas nuevas, «27», `raw.iva`, `raw.dvf`), diccionario
  v63, `CLAUDE.md`, `docs/ARCHITECTURE.md` y `azure-apps/datamart_seg_anual.md` (consume `iva` y
  `dvf`); `bash harness/init.sh` en verde (pytest, cobertura y mutación `estandar`).
