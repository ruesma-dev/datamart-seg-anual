# F-138 · Las alarmas de los documentos de Sigrid y la marca «liquidatoria»

Mediciones (solo lectura, 2026-10-14): `progress/spec_F-138.md`. Decisiones del
humano del 2026-10-14 al final (D1-D8 cerradas; D9 nueva, abierta).

## Para qué (D1, contestada por Control de Costes el 2026-10-14)

La marca sirve para tres cosas, y `compras.contrato_liquidacion` las responde:
(a) saber si se han **terminado las facturas** de un contrato; (b) el **IVA**:
con la liquidatoria ya no se puede diferir más; (c) **avisar si llega una
factura DESPUÉS** de la liquidatoria (`compras.facturas_tras_liquidacion`).
«CARTA LIQUIDACIÓN» = la última factura no decía «liquidatoria» y hay que pedir
al proveedor la carta de liquidación: cierra el contrato, pendiente de carta.

## Ingesta
- R1. `config/tables_sigrid.yaml` debe declarar `conala` filtrada en origen a
  `conide IN (SELECT ide FROM dbo.con WHERE tip IN (<FAMILIAS_ALARMAS>))`, con
  `incremental_column: null` (no tiene `tiemod`) y sin columnas excluidas.
- R2. Debe declarar `auxala` entera, con `incremental_column: tiemod`.
- R3. El `where` de R1 debe ser literalmente `filtro_conala()` del dominio.
- R4. El censo de `tables_sigrid.yaml` debe pasar de 74 a **76**, y los tests y
  textos que fijan el 74 (F-085, F-090, F-095, F-097) se actualizan a 76.
- R5. SI `FAMILIAS_ALARMAS` o el filtro de `conala` contienen la familia 43
  (empleados), ENTONCES un test debe fallar. La 43 no entra nunca, ni en `raw`.

## Dominio (`etl_sigrid/domain/liquidatoria.py`, oráculo puro)
- R6. `FAMILIAS_ALARMAS` debe ser la LISTA EXPLÍCITA {`con.tip`: nombre} de las
  17 familias con alarmas medidas salvo la 43 (D3): 1 INFORME, 4 CLIENTE, 5
  PROVEEDOR, 11 FACTURA_VENTA, 12 OFERTA, 14 ALBARAN, 15 FACTURA, 17
  CUENTA_AUXILIAR, 20 ASIENTO, 25 EFECTO_PAGO, 33 RECURSO, 35 PARTE_TRABAJO, 40
  OTRA, 42 OBRA, 44 CONTRATO, 46 COMPARATIVO, 54 CONTRATO_VENTA.
  `FAMILIAS_MARCA` = (14, 15): las que llevan marca por documento.
- R7. `normalizar(texto)` debe, en este orden: traducir vocales acentuadas, `ü`,
  `ñ` y `ç` (minúscula y mayúscula; `TRADUCCION_ORIGEN` -> `TRADUCCION_DESTINO`)
  a su letra base; sustituir cada tramo que no sea `[A-Za-z0-9]` por UN espacio;
  pasar a mayúsculas y recortar extremos. `None` -> cadena vacía.
- R8. `clasificar(texto)` debe devolver, sobre `normalizar(texto)`: si no casa
  `PATRON_MENCION`, `REMITE` cuando casa `PATRON_REMITE` y si no `None`; si casa,
  la primera que case de `NEGADA`, `CARTA_LIQUIDACION`, `DUDOSA`; y si ninguna,
  `LIQUIDATORIA`.
- R9. Patrones válidos a la vez en Python `re` y en el `~` de PostgreSQL (sin
  `\b`, `\w` ni `(?`): `PATRON_MENCION` = `(^| )LIQ`; `PATRON_NEGADA` =
  `(^| )NO (ES |SERA )?([A-Z0-9]+ )?LIQ`; `PATRON_CARTA` = `(^| )CARTA (DE )?LIQ`;
  `PATRON_DUDOSA` = `PREVISION|POSTERIOR|TIENE QUE VENIR|QUEDA PENDIENTE|NO SE SI`;
  `PATRON_REMITE` = `(^| )(VER|MIRAR) (EL )?(TEXTO|NOTA)( |$)`.
- R10. Casos fijados por test: «FACTURA LIQUIDATORIA», «Única y liquidatoria.»,
  «ES LIQUIDACIÓN.», «ULTIMA Y LIQ», «LIQUDATORIA» -> LIQUIDATORIA; «NO ES
  LIQUIDATORIA», «Aunque no es liquidación no difiero el IVA» -> NEGADA; «CARTA
  LIQUIDACIÓN», «"Carta liquidación."» -> CARTA_LIQUIDACION; «TRABAJOS
  POSTERIORES A LA LIQUIDACION», «PREVISIÓN DE LIQUIDACIÓN», «NO SE SI ES
  LIQUIDACION» -> DUDOSA; «VER TEXTO», «MIRAR NOTA» -> REMITE; «INVERSION
  SUJETO PASIVO», «» y `None` -> `None`.
- R11. `marca_documento(clases)` debe devolver la de mayor `PRECEDENCIA`
  presente: `NEGADA` > `LIQUIDATORIA` > `CARTA_LIQUIDACION` > `DUDOSA` >
  `REMITE`; `None` si no hay ninguna (motivo: design § Precedencia).
- R12. `fecha_hora_creacion(crefec, crehor)`: `datetime` de AAAAMMDD + HHMMSS (0
  o imposible -> `None`), oráculo del SQL de R14.

## SQL · `compras.documento_alarmas` (una fila por alarma, todas las familias)
- R13. `build_compras` debe construir `compras.documento_alarmas` con UNA fila
  por `raw.conala` cuyo documento está en `raw.con`; PK `alarma_id`.
- R14. Columnas: `alarma_id`, `documento_id`, `tipo_documento_codigo`
  (`con.tip`), `familia` (nombre de R6), `tipo_documento` (`fn_tipo_documento`
  en 14, 15 y 44; NULL en el resto), `codigo_documento`, `tipo_alarma_codigo` y
  `tipo_alarma` (`auxala` por LEFT JOIN; NULL si `alaide = 0`), `texto`
  (íntegro), `ver_al_abrir` (`tipabr = 1`), `creada_el`, `creada_por`
  (`creusu`) y `clase_liquidacion` (R8 en SQL, en TODAS las familias).
- R15. El SQL debe llevar LITERALMENTE los patrones de R9, la traducción de R7 y
  las parejas de R6 (en el `CASE` de `familia`): un test compara el texto.
- R16. SI `raw.conala` no tiene ninguna fila de factura (tip 15), ENTONCES el
  sub-paso debe fallar con `RAISE EXCEPTION` que nombre F-138.

## SQL · `compras.documento_liquidatoria` (facturas, albaranes, proformas y notas)
- R17. UNA fila por documento de `FAMILIAS_MARCA` cuya marca de alarmas (R11) o
  cuya clase del memo (R8 sobre `raw.con.tex`) no sea NULL; PK `documento_id`.
- R18. Columnas: `documento_id`, `tipo_documento_codigo`, `tipo_documento`,
  `codigo_documento`, `fecha_alta`, `marca_liquidacion` (R11),
  `es_liquidatoria` (marca LIQUIDATORIA), `pendiente_carta_liquidacion` (marca
  CARTA_LIQUIDACION), `cierra_contrato` (cualquiera de las dos), los tres
  booleanos FALSE y nunca NULL en el resto; `texto_alarmas` (textos de sus
  alarmas con clase, unidos por ` | ` por `alarma_id`), `liquidacion_creada_el`
  (la `creada_el` más antigua de sus alarmas LIQUIDATORIA o CARTA) y `clase_memo`.
- R19. Los booleanos NO deben mirar el memo (D5): memo LIQUIDATORIA sin alarma ->
  FALSE. R20. La clase del memo solo se calcula sobre `con.tex ILIKE '%liq%'`.

## SQL · `compras.contrato_liquidacion` y `compras.facturas_tras_liquidacion`
- R21. `contrato_liquidacion`: UNA fila por contrato de `compras.contratos` (PK
  `contrato_id`), con la cadena factura -> contrato de `v_pbi_contrato_consumo`.
  Factura de cierre = la de menor (`fecha`, `factura_id`) con `cierra_contrato`.
- R22. Columnas: `contrato_id`, `codigo_contrato`, `obra_id`, `codigo_obra`,
  `facturas_terminadas` (hay factura de cierre; nunca NULL), `tipo_cierre`
  (marca de la factura de cierre), `factura_cierre_id`, `codigo_factura_cierre`,
  `fecha_cierre`, `num_facturas_liquidatorias`, `num_facturas_carta_liquidacion`,
  `num_albaranes_liquidatorios` (AC y PROF), `num_facturas_posteriores`
  (`fecha` > `fecha_cierre`) y `ultima_factura_cierra`.
- R23. `facturas_tras_liquidacion`: UNA fila por (contrato, factura) con `fecha`
  > `fecha_cierre` del contrato (PK compuesta): contrato y obra, `factura_id`,
  `codigo_factura`, `fecha`, `fecha_factura`, proveedor, la factura de cierre,
  `fecha_cierre`, `dias_tras_cierre` y `cierra_contrato` de la propia factura.

## Build y frontera
- R24. El sub-paso `alarmas_liquidatoria` debe ir el ÚLTIMO de `SUB_PASOS` de
  `build_compras_step.py`, contando `compras.documento_alarmas`.
- R25. SQL idempotente (`DROP TABLE IF EXISTS ... CASCADE` + `CREATE TABLE ...
  AS`), con PK e índices por `documento_id`, `familia` y `obra_id`.
- R26. NO se modifican `compras.facturas`, `compras.albaranes` ni `07_texto.sql`
  (D7): un test comprueba que `01_` y `07_` no nombran `conala` ni `auxala`.

## Diccionario y documentación
- R27. `compras.yaml`: fichas de los cuatro objetos y de `fn_texto_normalizado` y
  `fn_clase_liquidacion` (grano, clave, todas las columnas), con la regla R7-R11
  en palabras, el para qué (a)-(c) y qué es la carta, que la marca es TEXTO LIBRE
  de una alarma y no un campo, y que `fec1`/`fec2` no se publican por vacías.
- R28. La ficha de `documento_liquidatoria` declara la cobertura medida (facturas
  8.653 liquidatorias + 99 pendientes de carta, albaranes 4.586, proformas 55,
  notas 0; ≈ 5 % de las facturas desde 2018; nada antes de 2008-12-04), las
  cifras de DUDOSA/NEGADA/REMITE y las 458 facturas y 46 albaranes cuyo memo la
  afirma sin alarma; y la de `documento_alarmas`, que las marcas de ventas (668),
  contratos (31) y comparativos (22) se leen allí, filtrando por `familia`.
- R29. `raw.yaml`: fichas de `conala` y `auxala`, «Son 76 tablas», y que la 43
  no entra; `00_global.yaml`: `version` +1, «las 76 tablas», `pendientes: []`.
- R30. `docs/ARCHITECTURE.md` y `azure-apps/datamart_seg_anual.md` dicen «76
  tablas» y nombran `conala`, `auxala` y los cuatro objetos nuevos.

## Verificación en Azure (MANUAL, tras el despliegue)
- R31. `check-raw-recuentos` OK en `conala` y `auxala`; `documento_alarmas`
  ~45.700 filas; ~8.750 facturas y ~4.640 albaranes/proformas con
  `cierra_contrato`; `contrato_liquidacion` = filas de `compras.contratos`.
- R32. Cifras de contrato en el orden de lo medido (±2 %): 5.611 con
  `facturas_terminadas` (81 solo por carta), 722 con 1.167 facturas posteriores,
  5.281 cuya última factura cierra.
- R33. El MCP, sin explicarle nada, responde: (a) «¿qué facturas liquidatorias
  tiene la obra X?»; (b) «¿qué contratos tienen ya su factura liquidatoria?»;
  (c) «¿qué facturas han llegado después de la liquidatoria?»; (d) «¿la
  FR26/10035 es liquidatoria y desde cuándo?» (29/09/2026 7:38:06).
- R34. La primera nocturna con F-138 deja medido en `progress/` el coste añadido.

## Decisiones (humano, 2026-10-14)
- D1. Para qué: (a)-(c) de arriba. Cumple el criterio 1 del `acceptance`.
- D2. Notas `NTC` dentro (mismo `tip = 14`; hoy 0 marcadas).
- D3. `conala`: TODAS las familias menos empleados (43); proformas incluidas.
- D4. «LIQUIDACIÓN» = liquidatoria; «CARTA LIQUIDACIÓN» = clase propia que cierra.
- D5. Memo aparte (`clase_memo`), fuera de los booleanos. D6. Se publica
  `creada_por` (login, sin nombre). D7. Objetos propios; `facturas`/`albaranes`
  intactas. D8. `acceptance` concretado: se verifica con R13-R34.
- **D9 (NUEVA, abierta, medida al aplicar D3)**: 27 alarmas de recursos (33, 3) y
  partes (35, 24) nombran trabajadores y sus bajas, y 89 de efectos de pago
  (25) nombran personas. Con D3 irían a `compras.documento_alarmas`, que leen el
  MCP y Power BI. Recomendación: sacar también 33 y 35 de `FAMILIAS_ALARMAS`
  (una línea; nada de la marca depende de ellas). Sin respuesta, entran (D3).
