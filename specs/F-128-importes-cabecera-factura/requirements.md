# F-128 · Toda la cabecera de la factura y del albarán, sus recargos y el cuadre de retenciones

Mediciones: `progress/spec_F-128.md` (2026-10-17). **D1-D5 CERRADAS por el humano el 2026-10-17**
(al final). Sin ingesta nueva: todo lo que se lee ya está en `raw`.
Vocabulario: **garantía** = recargo de clase 4 o 5 (D2-B); **fiscal** = clase 3 (IRPF, arrendamientos,
notarías); **inventario** = el de `domain/cabecera_compra.py`; **cuenta del proveedor** = `ban`,
`bancue`, `bandig`, `banban`, `bansuc` del documento (D4-B).

## Dominio (`etl_sigrid/domain/cabecera_compra.py`, oráculo puro)
- R1. `CLASES_RECARGO` debe ser {0: RECARGO, 1: DESCUENTO, 3: RETENCION_FISCAL, 4: RETENCION_GARANTIA_TOTAL,
  5: RETENCION_GARANTIA_BASE}; `clase_recargo(reccla)` da su literal, y `OTRA` si no está o es `None`.
- R2. `es_retencion_garantia(reccla)` debe ser verdadero SOLO si `reccla` es 4 o 5 (D2-B: `RETESP`,
  de clase 1, NO), falso si no o `None`; `es_retencion_fiscal(reccla)` = `reccla == 3`.
- R3. `INVENTARIO_DCF` e `INVENTARIO_DCA` deben tener una entrada por columna de `dcf`/`dca` en
  Sigrid (las de `raw` más las excluidas en `tables_sigrid.yaml` que existen allí, sin
  `_ingested_at` ni `_source_tiemod`): `("PUBLICADO", "<objeto>.<columna>[ + <objeto>.<columna>]")`
  o `(<motivo>, <nota>)`, con motivo en `MOTIVOS` = {VACIO, RESIDUAL, INTERNO, REDUNDANTE,
  OTRA_FEATURE, CATALOGO_NO_INGERIDO, NO_INGERIDO}. Contenido: `progress/spec_F-128.md` §5 y §7.
- R4. SI un motivo no está en `MOTIVOS`, una nota está vacía o una columna se repite, ENTONCES un test falla.

## `compras.facturas` (`sql/compras/01_documentos.sql`)
- R5. Debe conservar sus 15 columnas en su nombre y orden, y añadir AL FINAL, en este orden:
  `importe_bruto`, `importe_neto`, `importe_descuentos`, `importe_recargos`, `base_imponible`, `cuota_iva`,
  `total_factura`, `importe_retenciones`, `importe_retencion_garantia`, `importe_retencion_fiscal`,
  `total_a_pagar`, `contrato_id`, `obra_cabecera_id`, `codigo_obra_cabecera`, `nombre_obra_cabecera`,
  `centro_coste_cabecera_id`, `codigo_centro_coste_cabecera`, `nombre_centro_coste_cabecera`,
  `cuenta_analitica_cabecera_id`, `proveedor_codigo`, `proveedor_nombre_documento`,
  `proveedor_tipo_identificacion`, `proveedor_pais_identificacion`, `iva_diferido`,
  `inversion_sujeto_pasivo`, `fecha_entrega_prevista`, `fecha_limite`.
- R6. Importes `NUMERIC(18,2)` con `COALESCE(…, 0)`: bruto `impbru`, neto `impnet`, descuentos
  `impdes`, recargos `imprec`, base `totbas`, IVA `totiva`, total `totdoc`, a pagar `totpag`, y
  `importe_retenciones` = `totdoc − totpag`. `tot` NO se publica (= `totpag` en el 100 %).
- R7. `importe_retencion_garantia` e `importe_retencion_fiscal` deben ser la suma de `cuota` de los
  recargos de la factura en `compras.factura_recargos` con `es_retencion_garantia` / clase
  `RETENCION_FISCAL`, agregada POR FACTURA antes de unirse (0 si no tiene). Con D2-B,
  `importe_retenciones` = garantía + fiscal en el 100 % de las facturas (medido: 0 excepciones).
- R8. Los `*_id` con 0 deben publicarse NULL; código y nombre de obra y centro, de `raw.con`
  (`R-SIGRID-CON`) por `LEFT JOIN`; `iva_diferido` (`ivadif`) e `inversion_sujeto_pasivo`
  (`tipisp`) booleanos que nunca son NULL; textos vacíos a NULL; fechas con `fn_sigrid_date`.
- R9. El grano no cambia: sin `WHERE` externo, solo `LEFT JOIN`, y los joins nuevos DETRÁS del
  lateral del estado (lo exige `test_f083_sql`).

## `compras.albaranes` (proformas y notas incluidas)
- R10. Debe conservar sus 12 columnas y añadir AL FINAL: los 11 importes de R5 en el mismo orden (con
  `total_documento` en lugar de `total_factura`), `fecha_documento`, `forma_pago_id`, `forma_pago`,
  `medio_pago_id`, `medio_pago`, `cuenta_contable`, las 6 de obra y centro de cabecera de R5,
  `cuenta_analitica_cabecera_id`, las 4 de proveedor de R5, `iva_diferido`, `fecha_entrega_prevista`,
  `fecha_limite`, `facturado_sigrid`, `fecha_facturacion` y `factura_cabecera_id`.
- R11. `forma_pago` de `raw.auxpag` y `medio_pago` de `raw.auxefp`; `cuenta_contable` = `con.cod` de
  `cueide`; `facturado_sigrid` = `estfac = 1`, nunca NULL; `fecha_facturacion` = `fecfac`;
  `factura_cabecera_id` = `NULLIF(idefac, 0)`. Mismas reglas que R6-R8, sin `WHERE` externo.

## Recargos y retenciones de cada documento
- R12. `compras.factura_recargos` debe tener una fila por fila de `raw.dcfrec` cuyo `docide` sea
  una factura: `recargo_id` (PK, `ide`), `factura_id`, `posicion`, `concepto_id` (`recide`),
  `codigo_concepto` y `concepto` (de `raw.con`), `clase_recargo`, `es_retencion_garantia`, `base`,
  `porcentaje` (`valpor` × 100, 4 decimales), `cuota`, `cuota_iva`, `valor_fijo` (`valfij <> 0`),
  `cuenta_id` y `cuenta_contable` (`con.cod`).
- R13. `compras.albaran_recargos` debe ser lo mismo sobre `raw.dcarec` con `albaran_id`.
- R14. La clase y la marca deben salir de `compras.fn_clase_recargo(reccla)` y
  `compras.fn_es_retencion_garantia(reccla)` (`00_setup.sql`, UN parámetro); un test compara sus `CASE` con R1-R2.

## El cuadre de la retención de garantía (`sql/retenciones/07_cuadre_factura.sql`)
- R15. `retenciones.retencion_factura` debe tener una fila por factura con garantía ≠ 0 o con algún
  apunte ALTA/BAJA de `retenciones.apuntes_contables` cuyo `documento_id` sea ella, leyendo SOLO
  `raw` y `retenciones` (nunca `compras`): `factura_id` (PK), `codigo_factura`, `fecha_alta`,
  `fecha_factura`, `proveedor_id`, `proveedor_nombre`, `obra_id` (de cabecera), `empresa_id`,
  `codigo_obra`, `clave_obra`, `nombre_obra`, `retencion_factura`, `retencion_contable`,
  `diferencia_contable`, `efectos_generados`, `efectos_vivos`, `diferencia_efectos`,
  `categoria_contable`, `categoria_efectos`.
- R16. `retencion_contable` = Σ `importe` de esos apuntes; `efectos_generados` = Σ `importe` de
  `retenciones.movimientos` PROVEEDOR con ese `documento_id` y (`estado <> 'BAJA'` o `estado_sigrid
  = 14`); `efectos_vivos`, los `VIVA`. NULL sin filas; diferencias = factura − otro lado (o NULL).
- R17. `categoria_contable`, en este orden: SOLO_CONTABLE (garantía 0), SIN_APUNTE, CUADRA (|dif|
  < 0,01), DIFIERE. `categoria_efectos`: SIN_EFECTOS, CUADRA (< 0,01), DIFIERE.
- R18. `retenciones.v_cuadre_factura_obra` debe dar, por (`proveedor_id`, `obra_id`) con `FULL JOIN`
  entre `retencion_factura` y `retenciones.saldo_contable`: `retencion_facturas`, `altas_contables`,
  `diferencia`, `num_facturas`, `num_facturas_descuadre` (categoría contable ≠ CUADRA) y `categoria`
  (CUADRA < 1 €, SOLO_FACTURAS, SOLO_CONTABILIDAD, FACTURAS_MAYOR, CONTABILIDAD_MAYOR, en ese orden),
  solo pares con algún lado ≥ 1 €.
- R19. `retenciones.fn_es_retencion_garantia` debe ser COPIA deliberada de la de `compras` (no
  depende de otro esquema construido); un test compara los cuerpos.

## La cuenta bancaria del proveedor, SOLO en `compras_restringida` (D4-B)
- R20. `compras_restringida.documento_cuenta_bancaria` debe tener una fila por factura (`raw.dcf`)
  o albarán (`raw.dca`, proformas y notas incluidas) con `ban` no vacío, y nada más: `documento_id`
  (PK), `tipo_documento` (`FACTURA`/`ALBARAN`), `codigo_documento`, `fecha_documento`, `proveedor_id`,
  `proveedor_nombre`, `banco_id`, `banco`, `sucursal_id`, `sucursal`, `digitos_control`,
  `numero_cuenta`, `cuenta_bancaria`. Lee SOLO `raw` (`dcf`, `dca`, `con`, `auxban`); textos con
  `btrim` y vacíos a NULL; ids con 0 a NULL; `bantipide` NO se publica.
- R21. SI un fichero SQL publica `ban`, `bancue` o `bandig` fuera del bloque de R20, o `banban` /
  `bansuc` de `dca` fuera de él, o un objeto que no sea de `compras_restringida` lee
  `compras_restringida.documento_cuenta_bancaria`, ENTONCES un test debe fallar nombrando el fichero.
- R22. Un test debe fijar que los defectos de `settings.py` dejan `compras_restringida` en
  `PG_VETOED_SCHEMAS` y `PG_RESTRICTED_SCHEMAS`, fuera de `PG_TOTAL_VETOED_SCHEMAS` y (si existe,
  F-141) de `PG_PERFIL_RESTRINGIDO_SCHEMAS`, y que `grants.py` y `02_roles.sql` no la nombran.
- R23. SI un fichero de F-128 contiene una cadena con forma de IBAN o CCC (país + 2 dígitos + ≥ 16
  dígitos, o 20 seguidos), ENTONCES un test debe fallar nombrándolo.

## Pasos ETL
- R24. `01_documentos.sql` construye los recargos antes de albaranes y facturas y la tabla de R20
  al final (sin sub-paso nuevo); `build_retenciones` gana el sub-paso `cuadre_factura`
  (`07_cuadre_factura.sql`, destino `retencion_factura`) el último, con docstring.

## Diccionario semántico
- R25. Cada columna nueva de `facturas` y `albaranes` debe tener ficha con significado, cobertura
  (§5 del informe) y agregación; `total_factura` CON IVA y antes de retenciones, `base_imponible`
  SIN IVA, `importe_retenciones` = garantía + fiscal, `contrato_id` el de cabecera (6.991 por línea).
- R26. Las fichas de `compras.facturas` y `compras.albaranes` deben decir qué columnas de la
  cabecera de Sigrid NO se publican y por qué, agrupadas por motivo, y que la cuenta del proveedor
  está en `compras_restringida`; la de albaranes, las cifras por tipo (310.907 / 2.856 / 278 / 1) y
  que la retención del albarán y la de su factura NO se suman.
- R27. Fichas nuevas para los dos `*_recargos`, las tres funciones, `retencion_factura` y
  `v_cuadre_factura_obra`, con relaciones factura → recargos, albarán → recargos,
  `v_cuadre_proveedor` → `retencion_factura` → `compras.facturas`.
- R28. `retencion_factura` debe traer «¿qué facturas explican el descuadre de retenciones del
  proveedor X?» en `ejemplos_preguntas`; `v_cuadre_proveedor`, que los AGR no tienen factura (2.454
  efectos, 0,82 M € vivos).
- R29. El aviso `RETESP` (D2-B: 44 facturas, 871.193 €, clase DESCUENTO, NO es garantía: baja la
  base vía `importe_descuentos` y no está en `importe_retenciones`, pero su asiento va a la cuenta
  de retención en 42 de las 44) debe estar en las fichas de `importe_retencion_garantia`,
  `importe_descuentos`, `clase_recargo` y `retencion_factura` (donde esas 42 salen SOLO_CONTABLE).
- R30. La ficha de R20 (`compras_restringida.yaml`) debe EMPEZAR por «**ACCESO RESTRINGIDO: solo
  el perfil total del MCP.**» y dar cobertura, proporción IBAN/CCC, que es la cuenta del DOCUMENTO
  (no la ficha actual del proveedor) y relaciones a `facturas` y `albaranes`;
  `R-COMPRAS-RESTRINGIDA` debe nombrarla en `regla` sin cambiar su `ambito`.
- R31. `version` de `00_global.yaml` debe ser la siguiente a la de `main` en el momento del merge
  (test: ≥ la de `git show main:…` + 1) con su entrada «(F-128» en la historia; puerta offline y
  cobertura en verde.

## Fronteras y lo que no cambia
- R32. SI el SQL de `facturas` o `albaranes` lee `empide` u `hor`, o publica un desajuste
  cabecera-línea, ENTONCES un test debe fallar: son de F-134 y F-093 (D1-A).
- R33. `tables_sigrid.yaml` no cambia: `dca` sigue excluyendo `pagfor`/`pagtex` (D3-A); sin
  `auxeio`, `alm`, `auxobrcoc` (D5-A) ni `auxcueban`.
- R34. `ARCHITECTURE.md` (`totdoc`/`tot`/`totpag`, `reccla`, `RETESP`; qué guarda
  `compras_restringida`), el mapa de `CLAUDE.md` y `azure-apps/datamart_seg_anual.md` lo describen.

## Verificación en Azure (MANUAL, humano)
- R35. Tras `build-compras`, `build-retenciones` y `apply-grants`: recuentos = `raw`; 0 facturas con
  `importe_retenciones` ≠ fiscal + garantía; categorías del orden de §4 del informe; R20 = ~35.460
  filas; «permission denied» del login estándar en ella; `apply_grants` y `check-diccionario` ok.
- R36. Por el MCP, sin explicarle nada: «¿qué facturas explican el descuadre de retenciones del
  proveedor X?» y «¿cuánto se le retuvo en factura y cuánto está contabilizado?».

## Decisiones (CERRADAS por el humano el 2026-10-17; detalle y efecto: informe §6)
D1-A (aquí obra y centro de cabecera; F-093 el desajuste y la proforma; `empide`/`hor` en F-134) ·
D2-B (solo clases 4 y 5; `RETESP` avisado, R29) · D3-A (sin `dca.pagfor`/`pagtex`) · D4-B (la
cuenta del proveedor solo en `compras_restringida`, R20-R23 y R30) · D5-A (sin catálogos; `cocide`
a F-143). **Sin decisiones abiertas**; lo que D4-B dejó al diseño, en `design.md` §7.
