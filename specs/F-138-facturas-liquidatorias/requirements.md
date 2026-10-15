# F-138 · Las alarmas de los documentos de Sigrid y la marca «liquidatoria»

Mediciones: `progress/spec_F-138.md`. Decisiones D1-D9 (2026-10-14): al final.

## Para qué (D1)
(a) Saber si se han **terminado las facturas** de un contrato; (b) el **IVA**:
con la liquidatoria ya no se puede diferir más; (c) **avisar si llega una
factura DESPUÉS** de la liquidatoria. Lo responden `compras.contrato_liquidacion`
y `compras.facturas_tras_liquidacion`. «CARTA LIQUIDACIÓN» = la última factura
no decía «liquidatoria» y hay que pedir la carta: cierra el contrato, pendiente.

## Ingesta
- R1. `config/tables_sigrid.yaml` debe declarar `conala` con `where` =
  `filtro_conala()` del dominio, `incremental_column: null` y sin columnas
  excluidas; y `auxala` entera, con `incremental_column: tiemod`.
- R2. El censo de `tables_sigrid.yaml` debe pasar de 74 a **76**, y los tests y
  textos que fijan el 74 (F-085, F-090, F-095, F-097) se actualizan a 76.
- R3. SI `FAMILIAS_ALARMAS` o el filtro contienen la familia 43 (empleados),
  ENTONCES un test debe fallar. La 43 no entra nunca, ni en `raw`.

## Dominio (`etl_sigrid/domain/liquidatoria.py`, oráculo puro)
- R4. `FAMILIAS_ALARMAS` = lista EXPLÍCITA {`con.tip`: nombre} de las 17 familias
  medidas salvo la 43: 1 INFORME, 4 CLIENTE, 5 PROVEEDOR, 11 FACTURA_VENTA, 12
  OFERTA, 14 ALBARAN, 15 FACTURA, 17 CUENTA_AUXILIAR, 20 ASIENTO, 25 EFECTO_PAGO,
  33 RECURSO, 35 PARTE_TRABAJO, 40 OTRA, 42 OBRA, 44 CONTRATO, 46 COMPARATIVO, 54
  CONTRATO_VENTA. `FAMILIAS_MARCA` = (14, 15). `FAMILIAS_RESTRINGIDAS` = {33,
  35} (D9), subconjunto de `FAMILIAS_ALARMAS`; la 25 NO (R32).
- R5. `normalizar(texto)`, en este orden: traducir vocales acentuadas, `ü`, `ñ`
  y `ç` (`TRADUCCION_ORIGEN` -> `TRADUCCION_DESTINO`); cada tramo que no sea
  `[A-Za-z0-9]` a UN espacio; mayúsculas; recortar. `None` -> cadena vacía.
- R6. `clasificar(texto)` sobre `normalizar(texto)`: si no casa `PATRON_MENCION`,
  `REMITE` si casa `PATRON_REMITE` y si no `None`; si casa, la primera que case
  de `NEGADA`, `CARTA_LIQUIDACION`, `DUDOSA`, y si ninguna `LIQUIDATORIA`.
- R7. Patrones válidos en Python `re` y en el `~` de PostgreSQL (sin `\b`, `\w`
  ni `(?`): MENCION `(^| )LIQ`; NEGADA `(^| )NO (ES |SERA )?([A-Z0-9]+ )?LIQ`;
  CARTA `(^| )CARTA (DE )?LIQ`; DUDOSA
  `PREVISION|POSTERIOR|TIENE QUE VENIR|QUEDA PENDIENTE|NO SE SI`; REMITE
  `(^| )(VER|MIRAR) (EL )?(TEXTO|NOTA)( |$)`.
- R8. Casos por test: «FACTURA LIQUIDATORIA», «Única y liquidatoria.», «ES
  LIQUIDACIÓN.», «ULTIMA Y LIQ», «LIQUDATORIA» -> LIQUIDATORIA; «NO ES
  LIQUIDATORIA», «Aunque no es liquidación no difiero el IVA» -> NEGADA; «CARTA
  LIQUIDACIÓN», «"Carta liquidación."» -> CARTA_LIQUIDACION; «TRABAJOS
  POSTERIORES A LA LIQUIDACION», «PREVISIÓN DE LIQUIDACIÓN», «NO SE SI ES
  LIQUIDACION» -> DUDOSA; «VER TEXTO», «MIRAR NOTA» -> REMITE; «INVERSION SUJETO
  PASIVO», «» y `None` -> `None`.
- R9. `marca_documento(clases)`: la de mayor `PRECEDENCIA` presente (`NEGADA` >
  `LIQUIDATORIA` > `CARTA_LIQUIDACION` > `DUDOSA` > `REMITE`) o `None`.
- R10. `fecha_hora_creacion(crefec, crehor)`: `datetime` de AAAAMMDD + HHMMSS (0
  o imposible -> `None`), oráculo del SQL de R12.

## SQL · las alarmas, en dos esquemas (D9, patrón F-135/F-037)
- R11. `build_compras` debe construir `compras_restringida.documento_alarmas`
  COMPLETA (una fila por `raw.conala` con documento en `raw.con`; PK
  `alarma_id`) y `compras.documento_alarmas` = la completa SIN las familias de
  `FAMILIAS_RESTRINGIDAS`.
- R12. Columnas de las dos: `alarma_id`, `documento_id`, `tipo_documento_codigo`,
  `familia` (R4), `tipo_documento` (`fn_tipo_documento` en 14, 15 y 44; NULL
  en el resto), `codigo_documento`, `tipo_alarma_codigo`/`tipo_alarma` (`auxala`
  por LEFT JOIN; NULL si `alaide = 0`), `texto` (íntegro), `ver_al_abrir`,
  `creada_el` (`crefec` + `crehor`), `creada_por` (`creusu`) y
  `clase_liquidacion` (R6 en SQL). La completa añade `restringido` y
  `motivo_restriccion` (la familia, o NULL).
- R13. El SQL debe llevar LITERALMENTE los patrones de R7, la traducción de R5,
  las parejas de R4 y las familias restringidas: un test compara el texto.
- R14. SI no hay ninguna alarma de factura en `raw.conala`, o la general contiene
  una alarma de familia restringida, o general + restringidas no suman la
  completa, ENTONCES el SQL debe lanzar `RAISE EXCEPTION` (nombrando F-138) y
  la transacción del sub-paso se deshace.

## SQL · `compras.documento_liquidatoria` (facturas, albaranes, proformas y notas)
- R15. UNA fila por documento de `FAMILIAS_MARCA` cuya marca de alarmas (R9) o
  cuya clase del memo (R6 sobre `raw.con.tex`, solo si `ILIKE '%liq%'`) no sea
  NULL; PK `documento_id`. Lee la general (14 y 15 no son restringidas).
- R16. Columnas: `documento_id`, `tipo_documento_codigo`, `tipo_documento`,
  `codigo_documento`, `fecha_alta`, `marca_liquidacion`, `es_liquidatoria`,
  `pendiente_carta_liquidacion`, `cierra_contrato` (cualquiera de las dos; los
  tres booleanos FALSE y nunca NULL en el resto), `texto_alarmas` (las de clase
  no nula, ` | ` por `alarma_id`), `liquidacion_creada_el` (la más antigua de
  sus alarmas que cierran) y `clase_memo` (no entra en los booleanos, D5).

## SQL · contratos: `contrato_liquidacion` y `facturas_tras_liquidacion`
- R17. `contrato_liquidacion`: UNA fila por contrato de `compras.contratos` (PK),
  con la cadena factura -> contrato de `v_pbi_contrato_consumo`. Factura de
  cierre = la de menor (`fecha`, `factura_id`) con `cierra_contrato`.
- R18. Columnas: `contrato_id`, `codigo_contrato`, `obra_id`, `codigo_obra`,
  `facturas_terminadas` (nunca NULL), `tipo_cierre`, `factura_cierre_id`,
  `codigo_factura_cierre`, `fecha_cierre`, `num_facturas_liquidatorias`,
  `num_facturas_carta_liquidacion`, `num_albaranes_liquidatorios` (AC y PROF),
  `num_facturas_posteriores` y `ultima_factura_cierra`.
- R19. `facturas_tras_liquidacion`: UNA fila por (contrato, factura) con `fecha` >
  `fecha_cierre` (PK compuesta): contrato y obra, `factura_id`, `codigo_factura`,
  `fecha`, `fecha_factura`, proveedor, factura de cierre, `fecha_cierre`,
  `dias_tras_cierre` y `cierra_contrato` de la propia factura.

## Build, frontera y permisos
- R20. Sub-paso `alarmas_liquidatoria` el ÚLTIMO de `SUB_PASOS` de
  `build_compras_step.py`, contando `compras.documento_alarmas`; SQL idempotente
  (`DROP ... CASCADE` + `CREATE TABLE ... AS`) con PK e índices.
- R21. NO se modifican `compras.facturas`, `compras.albaranes` ni `07_texto.sql`
  (D7): un test comprueba que `01_` y `07_` no nombran `conala` ni `auxala`.
- R22. `compras_restringida` debe estar en `DEFAULT_VETOED_SCHEMAS` y en
  `DEFAULT_RESTRICTED_SCHEMAS` (no en el consumo ni en `DEFAULT_TOTAL_VETOED_SCHEMAS`),
  igual en `.env.example`, y en `ESQUEMAS_DEL_DATAMART` (16); los tests que
  fijan esas listas se actualizan.
- R23. `infra/sql/02_roles.sql` debe crear `compras_restringida` como
  `sigrid_dm_etl`, vetarla al estándar (no al total), concederla al autorizado
  (USAGE, SELECT y privilegio por defecto) y nombrarla en las comprobaciones
  finales; un test compara sus listas con `settings`.

## Diccionario y documentación
- R24. `compras.yaml`: fichas de los cuatro objetos y de `fn_texto_normalizado` y
  `fn_clase_liquidacion` (grano, clave, columnas), con la regla R5-R9 en
  palabras, el para qué, la carta, que la marca es TEXTO LIBRE de una alarma y
  que `fec1`/`fec2` no se publican; `compras_restringida.yaml`: la completa.
- R25. La ficha de `documento_liquidatoria` declara la cobertura (facturas 8.653
  + 99 con carta, albaranes 4.586, proformas 55, notas 0; ≈ 5 % de las facturas
  desde 2018; nada antes de 2008-12-04), DUDOSA/NEGADA/REMITE y las 458 facturas
  y 46 albaranes con memo sin alarma; la de `documento_alarmas`, que las marcas
  de ventas (668), contratos (31) y comparativos (22) se leen allí.
- R26. `00_global.yaml`: entrada de esquema `compras_restringida`, regla dura
  `R-COMPRAS-RESTRINGIDA` (hermana de `R-TESORERIA-RESTRINGIDA`), `version` +1,
  «las 76 tablas», `pendientes: []`; `raw.yaml`: `conala`, `auxala`, «Son 76».
- R27. `docs/ARCHITECTURE.md`, `CLAUDE.md` y `azure-apps/datamart_seg_anual.md`:
  «76 tablas», los objetos nuevos, el esquema restringido y, en azure-apps, el
  contrato: `mcp-bbdd` añade `compras_restringida` a su lista blanca común.

## Verificación en Azure (MANUAL, tras el despliegue; orden en el design)
- R28. `check-raw-recuentos` OK en `conala` y `auxala`; completa ~45.750 y
  general ~45.720 alarmas; ~8.750 facturas y ~4.640 albaranes/proformas con
  `cierra_contrato`; `contrato_liquidacion` = filas de `compras.contratos`.
- R29. Contratos (±2 %): 5.611 con `facturas_terminadas` (81 solo por carta),
  722 con 1.167 facturas posteriores, 5.281 cuya última factura cierra.
- R30. `apply-grants` con `verificacion`, `verificacion_total` y `acceso_total`
  = ok; el estándar sin USAGE en `compras_restringida` y el total con él.
- R31. El MCP, sin explicarle nada: (a) «¿qué facturas liquidatorias tiene la obra
  X?»; (b) «¿qué contratos tienen ya su factura liquidatoria?»; (c) «¿qué
  facturas han llegado después de la liquidatoria?»; (d) «¿la FR26/10035 es
  liquidatoria y desde cuándo?» (29/09/2026 7:38:06); con la cuenta estándar,
  `compras_restringida` da PERMISO_DENEGADO. Primera nocturna: coste medido.
- R32. La familia 25 se queda en la general: sus 88 efectos con alarma son los 88
  «general» de `tesoreria_restringida.efectos` (0 de personal según F-037).

## Decisiones (humano, 2026-10-14)
- D1. Para qué: (a)-(c) de arriba (cumple el criterio 1 del `acceptance`).
- D2. Notas `NTC` dentro. D3. `conala` con todas las familias menos la 43. D4.
  «LIQUIDACIÓN» = liquidatoria; «CARTA LIQUIDACIÓN» = clase propia que cierra.
- D5. Memo aparte (`clase_memo`). D6. Se publica `creada_por` (login).
- D7. Objetos propios; `facturas`/`albaranes` intactas. D8. `acceptance` por R11-R32.
- D9. Recursos (33) y partes (35): «mete esas alarmas en lectura solo para el
  perfil admin y no el estándar» -> `compras_restringida`, solo perfil total.
