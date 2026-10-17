# F-128 · Toda la cabecera de la factura y del albarán, sus recargos y el cuadre de retenciones

Mediciones (2026-10-17): `progress/spec_F-128.md`. Decisiones **D1-D5 ABIERTAS** al final, con
opciones cerradas; la spec está escrita con la RECOMENDADA de cada una. Sin ingesta nueva (D3-A).
Vocabulario: **garantía** = recargo con `es_retencion_garantia`; **fiscal** = clase 3 (IRPF,
arrendamientos, notarías); **inventario** = el de `etl_sigrid/domain/cabecera_compra.py`.

## Dominio (`etl_sigrid/domain/cabecera_compra.py`, oráculo puro)
- R1. `CLASES_RECARGO` debe ser {0: RECARGO, 1: DESCUENTO, 3: RETENCION_FISCAL, 4:
  RETENCION_GARANTIA_TOTAL, 5: RETENCION_GARANTIA_BASE}; `clase_recargo(reccla)` devuelve su literal,
  y `OTRA` para cualquier otro valor o `None`.
- R2. `es_retencion_garantia(reccla, codigo)` debe ser verdadero si `reccla` es 4 o 5, o si es 1 y
  el código del concepto empieza por `RET` (el `RETESP`, D2-A); falso en cualquier otro caso,
  `None` incluido. `es_retencion_fiscal(reccla)` = `reccla == 3`.
- R3. `INVENTARIO_DCF` e `INVENTARIO_DCA` deben tener una entrada por columna de `dcf`/`dca` en
  Sigrid (las de `raw` más las excluidas en `tables_sigrid.yaml` que existen allí, sin
  `_ingested_at` ni `_source_tiemod`): `("PUBLICADO", "<objeto>.<columna>")` o `(<motivo>, <nota>)`,
  con motivo en `MOTIVOS` = {VACIO, RESIDUAL, INTERNO, REDUNDANTE, OTRA_FEATURE,
  CATALOGO_NO_INGERIDO, DATO_BANCARIO, NO_INGERIDO}. Contenido: `progress/spec_F-128.md` §5.
- R4. SI un motivo no está en `MOTIVOS`, una nota está vacía o una columna se repite, ENTONCES un
  test debe fallar nombrándola.

## `compras.facturas` (`sql/compras/01_documentos.sql`)
- R5. Debe conservar sus 15 columnas en su nombre y orden, y añadir AL FINAL, en este orden:
  `importe_bruto`, `importe_neto`, `importe_descuentos`, `importe_recargos`, `base_imponible`,
  `cuota_iva`, `total_factura`, `importe_retenciones`, `importe_retencion_garantia`,
  `importe_retencion_fiscal`, `total_a_pagar`, `contrato_id`, `obra_cabecera_id`,
  `codigo_obra_cabecera`, `nombre_obra_cabecera`, `centro_coste_cabecera_id`,
  `codigo_centro_coste_cabecera`, `nombre_centro_coste_cabecera`, `cuenta_analitica_cabecera_id`,
  `proveedor_codigo`, `proveedor_nombre_documento`, `proveedor_tipo_identificacion`,
  `proveedor_pais_identificacion`, `iva_diferido`, `inversion_sujeto_pasivo`,
  `fecha_entrega_prevista`, `fecha_limite`.
- R6. Importes `NUMERIC(18,2)` con `COALESCE(…, 0)`: bruto `impbru`, neto `impnet`, descuentos
  `impdes`, recargos `imprec`, base `totbas`, IVA `totiva`, total `totdoc`, a pagar `totpag`, y
  `importe_retenciones` = `totdoc − totpag`. `tot` NO se publica (= `totpag` en el 100 %).
- R7. `importe_retencion_garantia` e `importe_retencion_fiscal` deben ser la suma de `cuota` de los
  recargos de la factura en `compras.factura_recargos` con `es_retencion_garantia` / clase
  `RETENCION_FISCAL`, agregada POR FACTURA antes de unirse (0 si no tiene).
- R8. Los `*_id` con 0 deben publicarse NULL; código y nombre de obra y centro, de `raw.con`
  (`R-SIGRID-CON`) por `LEFT JOIN`; `iva_diferido` (`ivadif`) e `inversion_sujeto_pasivo`
  (`tipisp`) booleanos que nunca son NULL; textos vacíos a NULL; fechas con `fn_sigrid_date`.
- R9. El grano no cambia: ningún `WHERE` en la consulta externa, solo `LEFT JOIN`, y los joins
  nuevos van DETRÁS del lateral del estado (lo exige `test_f083_sql`).

## `compras.albaranes` (proformas y notas incluidas)
- R10. Debe conservar sus 12 columnas y añadir AL FINAL: los 11 importes de R5 en el mismo orden
  (con `total_documento` en lugar de `total_factura`), `fecha_documento`, `forma_pago_id`,
  `forma_pago`, `medio_pago_id`, `medio_pago`, `cuenta_contable`, las 6 de obra y centro de
  cabecera de R5, `cuenta_analitica_cabecera_id`, las 4 de proveedor de R5, `iva_diferido`,
  `fecha_entrega_prevista`, `fecha_limite`, `facturado_sigrid`, `fecha_facturacion` y
  `factura_cabecera_id`.
- R11. `forma_pago` de `raw.auxpag` y `medio_pago` de `raw.auxefp` por su id; `cuenta_contable` =
  `con.cod` de `cueide`; `facturado_sigrid` = `estfac = 1`, nunca NULL; `fecha_facturacion` =
  `fecfac`; `factura_cabecera_id` = `NULLIF(idefac, 0)`. Mismas reglas que R6-R8, sin `WHERE` externo.

## Recargos y retenciones de cada documento
- R12. `compras.factura_recargos` debe tener una fila por fila de `raw.dcfrec` cuyo `docide` sea
  una factura: `recargo_id` (PK, `ide`), `factura_id`, `posicion`, `concepto_id` (`recide`),
  `codigo_concepto` y `concepto` (de `raw.con`), `clase_recargo`, `es_retencion_garantia`, `base`,
  `porcentaje` (`valpor` × 100, 4 decimales), `cuota`, `cuota_iva`, `valor_fijo` (`valfij <> 0`),
  `cuenta_id` y `cuenta_contable` (`con.cod`).
- R13. `compras.albaran_recargos` debe ser lo mismo sobre `raw.dcarec` con `albaran_id`.
- R14. La clase y la marca deben salir de `compras.fn_clase_recargo(reccla)` y
  `compras.fn_es_retencion_garantia(reccla, codigo)` (`00_setup.sql`), cuyos `CASE` un test compara
  con `CLASES_RECARGO` y con R2.

## El cuadre de la retención de garantía (`sql/retenciones/07_cuadre_factura.sql`)
- R15. `retenciones.retencion_factura` debe tener una fila por factura con garantía ≠ 0 o con algún
  apunte ALTA/BAJA de `retenciones.apuntes_contables` cuyo `documento_id` sea ella, leyendo SOLO
  `raw` y `retenciones` (nunca `compras`): `factura_id` (PK), `codigo_factura`, `fecha_alta`,
  `fecha_factura`, `proveedor_id`, `proveedor_nombre`, `obra_id` (de cabecera), `empresa_id`,
  `codigo_obra`, `clave_obra`, `nombre_obra`, `retencion_factura`, `retencion_contable`,
  `diferencia_contable`, `efectos_generados`, `efectos_vivos`, `diferencia_efectos`,
  `categoria_contable`, `categoria_efectos`.
- R16. `retencion_contable` = Σ `importe` de esos apuntes; `efectos_generados` = Σ `importe` de
  `retenciones.movimientos` PROVEEDOR con ese `documento_id` y (`estado <> 'BAJA'` o
  `estado_sigrid = 14`); `efectos_vivos`, los `VIVA`. NULL si no hay filas; diferencias = factura −
  el otro lado (NULL si el otro es NULL).
- R17. `categoria_contable`, en este orden: SOLO_CONTABLE (garantía 0), SIN_APUNTE, CUADRA (|dif|
  < 0,01), DIFIERE. `categoria_efectos`: SIN_EFECTOS, CUADRA (< 0,01), DIFIERE.
- R18. `retenciones.v_cuadre_factura_obra` debe dar, por (`proveedor_id`, `obra_id`) con `FULL JOIN`
  entre `retencion_factura` y `retenciones.saldo_contable`: `retencion_facturas`, `altas_contables`,
  `diferencia`, `num_facturas`, `num_facturas_descuadre` (categoría contable ≠ CUADRA) y `categoria`
  (CUADRA < 1 €, SOLO_FACTURAS, SOLO_CONTABILIDAD, FACTURAS_MAYOR, CONTABILIDAD_MAYOR, en ese orden),
  solo pares con algún lado ≥ 1 €.
- R19. `retenciones.fn_es_retencion_garantia` debe ser una COPIA deliberada de la de `compras`
  (`retenciones` no depende de otro esquema construido); un test compara los cuerpos.

## Pasos ETL
- R20. `build_compras` construye los recargos en `01_documentos.sql` antes de albaranes y facturas;
  `build_retenciones` gana el sub-paso `cuadre_factura` (`07_cuadre_factura.sql`, destino
  `retencion_factura`) el último, con docstring y comentario de orden.

## Diccionario semántico
- R21. Cada columna nueva de `compras.facturas` y `compras.albaranes` debe tener ficha con
  significado, cobertura medida (§5 del informe) y agregación; `total_factura` dice CON IVA y antes
  de retenciones, `base_imponible` SIN IVA, `importe_retenciones` = garantía + fiscal, y
  `contrato_id` de facturas que es el de cabecera (la línea solo da 6.991 directos).
- R22. Las fichas de `compras.facturas` y `compras.albaranes` deben decir qué columnas de la
  cabecera de Sigrid NO se publican y por qué, agrupadas por motivo; la de albaranes, las cifras por
  tipo (310.907 / 2.856 / 278 / 1) y que la retención del albarán y la de su factura NO se suman.
- R23. Fichas nuevas para los dos `*_recargos`, las tres funciones, `retencion_factura` y
  `v_cuadre_factura_obra`, con relaciones factura → recargos, albarán → recargos,
  `v_cuadre_proveedor` → `retencion_factura` y `retencion_factura` → `compras.facturas`.
- R24. La ficha de `retencion_factura` debe traer «¿qué facturas explican el descuadre de
  retenciones del proveedor X?» en `ejemplos_preguntas`; la de `v_cuadre_proveedor`, que los
  efectos agrupadores (AGR) no tienen factura y no se pueden atribuir así (2.454, 0,82 M € vivos).
- R25. La trampa `RETESP` (clase DESCUENTO que es retención: baja la base y no entra en
  `importe_retenciones`, pero sí en la garantía y en el cuadre) debe estar en las fichas de
  `importe_retencion_garantia` y de `clase_recargo`.
- R26. `version` de `00_global.yaml` debe ser la siguiente a la de `main` en el momento del merge
  (test: ≥ la de `git show main:…` + 1) con su entrada «(F-128» en la historia; puerta offline y
  cobertura en verde.

## Fronteras y lo que no cambia
- R27. SI el SQL de `facturas` o `albaranes` lee `empide` u `hor`, o publica un desajuste
  cabecera-línea, ENTONCES un test debe fallar: son de F-134 y F-093 (D1-A).
- R28. `config/tables_sigrid.yaml` no cambia: `dca` sigue excluyendo `pagfor` y `pagtex` (D3-A).
- R29. `docs/ARCHITECTURE.md` (semántica Sigrid: `totdoc`/`tot`/`totpag`, `reccla`, `RETESP`) y
  `azure-apps/datamart_seg_anual.md` (lo que se expone) deben describir lo nuevo.

## Verificación en Azure (MANUAL, humano)
- R30. Tras `build-compras` y `build-retenciones`: recuentos = `raw` (167.458 / 314.042 / 32.994 /
  41.466 a 17-10); 0 facturas con `importe_retenciones` ≠ fiscal + garantía salvo las de `RETESP`;
  categorías del orden de §4 del informe; `check-diccionario` sin diferencias; publicar diccionario.
- R31. Por el MCP, sin explicarle nada: «¿qué facturas explican el descuadre de retenciones del
  proveedor X?» y «¿cuánto se le retuvo en factura y cuánto está contabilizado?».

## Decisiones abiertas (recomendada: A en todas)
- **D1 Frontera con F-093 y F-134.** A: aquí las columnas de obra y centro de cabecera; F-093 se
  queda el desajuste cabecera-línea y el caso de la proforma de Juan; `empide`/`hor`, en F-134
  (exigen `dbo.log`). B: absorber F-093 entera (+1 vista). C: nada; las publica F-093.
- **D2 `RETESP`** (44 facturas, 871.193 €). A: es garantía (su asiento va a la cuenta de
  retención: 42 facturas, 790.276 €). B: solo clases 4 y 5, y la trampa en la ficha.
- **D3 `dca.pagfor`/`pagtex`** (100 %, excluidas de la ingesta). A: no se publican (exigen
  `ingest --table dca --full`; la forma de pago sí sale por `pagide`). B: des-excluir y publicar.
- **D4 Datos bancarios del proveedor** (`ban`, `bancue`, `bandig`, `bantipide`). A: no se
  publican. B: en `compras_restringida`.
- **D5 Catálogos no ingeridos** (`eioide`, `almide`, `cocide`). A: no se publican; `cocide`
  (tipo de contrato de compra) a backlog. B: ingerir `auxeio`, `alm`, `auxobrcoc` aquí.
