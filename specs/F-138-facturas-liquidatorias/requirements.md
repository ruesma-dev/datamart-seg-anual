# F-138 · Las alarmas de los documentos de compra y la marca «liquidatoria»

Mediciones (solo lectura, 2026-10-14) y lo que concretan de la ficha:
`progress/spec_F-138.md` (§ 2: «Creada por / fecha y hora» de la ventana es
`conala.creusu`/`crefec`/`crehor`, sin `dbo.log`; `fec1`/`fec2` vacías).
Decisiones abiertas: D1-D8 al final. **D1 (para qué) bloquea el cierre, no el
arranque**: solo `contrato_liquidacion` (R21-R23) depende de ella.

## Ingesta
- R1. El sistema debe declarar `conala` en `config/tables_sigrid.yaml` filtrada
  en origen a `conide IN (SELECT ide FROM dbo.con WHERE tip IN (14, 15))`, con
  `incremental_column: null` (no tiene `tiemod`) y sin columnas excluidas.
- R2. El sistema debe declarar `auxala` entera, con `incremental_column: tiemod`.
- R3. El `where` de R1 debe ser literalmente `filtro_conala()` del dominio.
- R4. El censo de `tables_sigrid.yaml` debe pasar de 74 a **76**, y los tests y
  textos que fijan el 74 (F-085, F-090, F-095, F-097) se actualizan a 76.
- R5. SI el filtro de `conala` admite otra familia que las de R6 (p. ej. la 43,
  empleados), ENTONCES un test debe fallar.

## Dominio (`etl_sigrid/domain/liquidatoria.py`, oráculo puro)
- R6. `TIPOS_DOCUMENTO_ALARMAS` = (14, 15) debe ser la única fuente de las
  familias: albarán (series AC, PROF, NTC) y factura.
- R7. `normalizar(texto)` debe, en este orden: traducir vocales acentuadas, `ü`,
  `ñ` y `ç` (minúscula y mayúscula; `TRADUCCION_ORIGEN` -> `TRADUCCION_DESTINO`)
  a su letra base; sustituir cada tramo que no sea `[A-Za-z0-9]` por UN espacio;
  pasar a mayúsculas y recortar extremos. `None` -> cadena vacía.
- R8. `clasificar(texto)` debe devolver, sobre `normalizar(texto)`: si no casa
  `PATRON_MENCION`, `REMITE` cuando casa `PATRON_REMITE` y si no `None`; si casa,
  `NEGADA` cuando casa `PATRON_NEGADA`, si no `DUDOSA` cuando casa
  `PATRON_DUDOSA`, y si no `LIQUIDATORIA`.
- R9. Los patrones deben valer a la vez en Python `re` y en el `~` de PostgreSQL
  (sin `\b`, `\w` ni lookarounds): `PATRON_MENCION` = `(^| )LIQ`;
  `PATRON_NEGADA` = `(^| )NO (ES |SERA )?([A-Z0-9]+ )?LIQ`;
  `PATRON_DUDOSA` = `PREVISION|POSTERIOR|TIENE QUE VENIR|QUEDA PENDIENTE|NO SE SI|(^| )CARTA (DE )?LIQ`;
  `PATRON_REMITE` = `(^| )(VER|MIRAR) (EL )?(TEXTO|NOTA)( |$)`.
- R10. Casos fijados por test: «FACTURA LIQUIDATORIA», «Única y liquidatoria.»,
  «ES LIQUIDACIÓN.», «ULTIMA Y LIQ», «LIQUDATORIA» -> LIQUIDATORIA; «NO ES
  LIQUIDATORIA», «Aunque no es liquidación no difiero el IVA» -> NEGADA; «CARTA
  LIQUIDACIÓN», «TRABAJOS POSTERIORES A LA LIQUIDACION», «PREVISIÓN DE
  LIQUIDACIÓN», «NO SE SI ES LIQUIDACION» -> DUDOSA; «VER TEXTO», «MIRAR NOTA»
  -> REMITE; «INVERSION SUJETO PASIVO», «» y `None` -> `None`.
- R11. `marca_documento(clases)` debe devolver la de mayor precedencia presente
  (`NEGADA` > `LIQUIDATORIA` > `DUDOSA` > `REMITE`) o `None`.
- R12. `fecha_hora_creacion(crefec, crehor)`: `datetime` de AAAAMMDD + HHMMSS (0
  o imposible -> `None`), oráculo del SQL de R14.

## SQL · `compras.documento_alarmas` (una fila por alarma)
- R13. `build_compras` debe construir `compras.documento_alarmas` con UNA fila
  por `raw.conala` cuyo documento (`raw.con`) es de R6; PK `alarma_id`.
- R14. Columnas: `alarma_id` (`conala.ide`), `documento_id`,
  `tipo_documento_codigo` (`con.tip`), `tipo_documento` (`fn_tipo_documento`),
  `codigo_documento`, `tipo_alarma_codigo` y `tipo_alarma` (`auxala.cod`/`res`
  por LEFT JOIN; NULL si `alaide = 0`), `texto` (íntegro), `ver_al_abrir`
  (`tipabr = 1`), `creada_el` (TIMESTAMP de `crefec` + `crehor`), `creada_por`
  (`creusu`, D6) y `clase_liquidacion` (R8 en SQL).
- R15. El SQL debe llevar LITERALMENTE los patrones de R9 y la traducción de R7:
  un test compara el texto del SQL con las constantes del dominio.
- R16. SI no hay ninguna fila de `raw.conala` de las familias de R6, ENTONCES el
  sub-paso debe fallar con `RAISE EXCEPTION` que nombre F-138.

## SQL · `compras.documento_liquidatoria` (una fila por documento con mención)
- R17. UNA fila por documento de R6 cuya marca de alarmas (R11) o cuya clase del
  memo (R8 sobre `raw.con.tex`) no sea NULL; PK `documento_id`.
- R18. Columnas: `documento_id`, `tipo_documento_codigo`, `tipo_documento`,
  `codigo_documento`, `fecha_alta` (`con.fec`), `marca_liquidacion` (R11),
  `es_liquidatoria` (marca = `LIQUIDATORIA`; FALSE, nunca NULL, en el resto),
  `texto_alarmas` (textos de sus alarmas con clase, unidos por ` | ` por
  `alarma_id`), `liquidatoria_creada_el` (la `creada_el` más antigua de sus
  alarmas LIQUIDATORIA) y `clase_memo`.
- R19. `es_liquidatoria` NO debe mirar el memo (D5): memo LIQUIDATORIA sin
  alarma que lo diga -> FALSE.
- R20. La clase del memo solo se calcula sobre `con.tex ILIKE '%liq%'` (prefiltro
  barato sobre `raw.con`, 2,18 M de filas).

## SQL · `compras.contrato_liquidacion` (depende de D1)
- R21. UNA fila por contrato al que llega al menos un documento con
  `es_liquidatoria`, por la cadena de `v_pbi_contrato_consumo` (factura ->
  línea directa, albarán de cabecera o línea del albarán; albarán -> cabecera o
  línea); PK `contrato_id`.
- R22. Columnas: `contrato_id`, `codigo_contrato`, `obra_id`, `codigo_obra` (de
  `compras.contratos`), `num_facturas_liquidatorias`,
  `primera_factura_liquidatoria_id`, `fecha_primera_factura_liquidatoria`,
  `num_albaranes_liquidatorios` (AC y PROF), `num_facturas_posteriores`
  (`fecha` > la de la primera liquidatoria) y `ultima_factura_es_liquidatoria`.
- R23. MANUAL en Azure: cifras en el orden de lo medido (±2 %): 5.859 contratos,
  5.530 con factura liquidatoria, 719 con 1.160 facturas posteriores, 5.200 cuya
  última factura es la liquidatoria.

## Build y frontera
- R24. El sub-paso `alarmas_liquidatoria` debe ir el ÚLTIMO de `SUB_PASOS` de
  `build_compras_step.py`, contando `compras.documento_alarmas`.
- R25. El SQL debe ser idempotente (`DROP TABLE IF EXISTS ... CASCADE` +
  `CREATE TABLE ... AS`), con PK e índices por `documento_id` y `obra_id`.
- R26. El sistema NO debe modificar `compras.facturas`, `compras.albaranes` ni
  `07_texto.sql` (D7): un test comprueba que `01_documentos.sql` y `07_texto.sql`
  no nombran `conala` ni `auxala`.

## Diccionario y documentación
- R27. `compras.yaml` debe tener las fichas de los tres objetos (grano, clave,
  todas las columnas) y de `fn_texto_normalizado` y `fn_clase_liquidacion`, con la regla R7-R11 en palabras, que la marca es TEXTO
  LIBRE de una alarma y no un campo, que no tener fila es «sin alarma ni memo que
  lo mencione», y que `fec1`/`fec2` no se publican por vacías.
- R28. La ficha de `documento_liquidatoria` debe declarar la cobertura medida
  (facturas 8.653, albaranes 4.586, proformas 55, notas 0; ≈ 5 % de las facturas
  desde 2018; nada antes de 2008-12-04), las cifras de DUDOSA/NEGADA/REMITE y las
  458 facturas y 46 albaranes cuyo memo la afirma sin alarma.
- R29. Y las ~770 alarmas «LIQUIDA» fuera (ventas 700, contratos 32, otras; D3).
- R30. `raw.yaml`: fichas de `conala` y `auxala`, «Son 76 tablas»;
  `00_global.yaml`: sube `version`, «las 76 tablas», `pendientes: []`.
- R31. `docs/ARCHITECTURE.md` y `azure-apps/datamart_seg_anual.md` deben decir
  «76 tablas» y nombrar `conala`, `auxala` y los tres objetos nuevos.

## Verificación en Azure (MANUAL, tras el despliegue)
- R32. `check-raw-recuentos` OK en `conala` y `auxala`; `documento_alarmas`
  ~23.800 filas; ~8.650 facturas y ~4.640 albaranes/proformas con
  `es_liquidatoria`.
- R33. El MCP, sin explicarle nada, responde: (a) «¿qué facturas liquidatorias
  tiene la obra X?»; (b) «¿qué contratos tienen ya su factura liquidatoria?»;
  (c) «¿la FR26/10035 es liquidatoria y desde cuándo?» (29/09/2026 7:38:06).
- R34. La primera nocturna con F-138 deja medido en `progress/` el coste añadido.

Fuera de alcance: alarmas de ventas (11, 54), contratos (44), comparativos (46)
y empleados (43) (D3); escribir en Sigrid; la marca en `facturas`/`albaranes`
(D7); el memo de los albaranes en `compras.documento_texto` (hoy solo 15 y 44).

## Decisiones abiertas para el humano (recomendación entre corchetes)
- D1. **Para qué** (criterio 1 del `acceptance`; solo lo contesta Elena Díaz).
  Propuesta: control de CIERRE de contrato (qué contratos tienen ya su
  liquidatoria y cuáles reciben facturas después: 719 contratos, 1.160
  facturas) y base para liberar la retención (F-095, F-128). Pregunta para
  reenviar: «Elena, para preparar las liquidatorias en el datamart: ¿qué
  necesitas responder con la marca? (a) qué contratos tienen ya su liquidatoria;
  (b) avisar si llega una factura después; (c) cuándo liberar la retención; (d)
  el IVA (alarmas antiguas: "aunque no es liquidación no difiero el IVA"); (e)
  otra. ¿Una alarma "CARTA LIQUIDACIÓN" cuenta como liquidatoria? ¿Vale si solo
  lo dice el TEXTO del documento y no la alarma?» [R1-R20 ya; R21-R23 después].
- D2. Notas `NTC` [dentro: mismo `tip = 14`, coste cero, hoy 0 marcadas].
- D3. Ingesta filtrada a facturas y albaranes [sí: 23.833 de 46.242 filas, fuera
  empleados]; contratos (+15.562: «CONTRATO INTERNO», forma de pago), otra feature.
- D4. «LIQUIDACION» cuenta como liquidatoria [sí]; «CARTA LIQUIDACIÓN» (99) va a
  DUDOSA [hasta que conteste Elena].
- D5. El memo fuera de `es_liquidatoria`, publicado aparte en `clase_memo` [sí:
  varios comentarios por memo, regla más ruidosa].
- D6. Publicar `creada_por` (login, sin nombre) [sí, criterio de F-085 y F-090 D3].
- D7. Objetos propios, `facturas`/`albaranes` intactas [sí: F-128 y F-093 las van
  a tocar; la columna se añade cuando cierren].
- D8. Aceptar el `acceptance` concretado: criterio 1 = «D1 contestada y escrita
  en la spec»; el resto se verifica con R13-R34.
