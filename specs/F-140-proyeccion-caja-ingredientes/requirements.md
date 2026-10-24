<!-- specs/F-140-proyeccion-caja-ingredientes/requirements.md -->
# F-140 · Fase 2 de la cartera: los ingredientes de la proyección de caja

Mediciones: `progress/spec_F-140.md`. Decisiones abiertas D1-D12 en `design.md` §9; los requisitos
van con la opción recomendada y marcan «(Dn)» donde dependen de ella. **Regla del humano**: el
datamart NO convierte devengo en caja; publica INGREDIENTES y obliga a declarar la hipótesis.

Vocabulario:
- **Devengo pendiente**: el importe planificado (sin IVA) de la versión master que rige en los
  meses POSTERIORES al último cierre real del mismo concepto (COSTE o VENTA) de la obra.
- **Fórmula de plazo**: `auxpag.formul` / `auxcob.formul` tal cual («120 450R»). Token `N` =
  días de un vencimiento; token `NR` = días del vencimiento de la RETENCIÓN.
- **Columna de caja**: cualquier fecha, mes o importe que resulte de APLICAR un plazo, una
  retención o un IVA a un devengo. Ninguna se publica.

## La fórmula de plazo (dominio puro)

R1. El sistema debe leer una fórmula de plazo con una única función de dominio que devuelve los
días de cada vencimiento (en el orden escrito), los días de la retención (o `None`) y si la
fórmula se ha reconocido.

R2. SI la fórmula está vacía, es `NULL`, tiene un token que no es `N` ni `NR` o más de un token
`NR`, ENTONCES la función debe devolver «no reconocida», sin días ni retención (falla cerrado:
no se lee a medias). Los blancos repetidos separan igual que uno («90  450R»).

R3. El SQL debe llevar las mismas expresiones regulares que el dominio, literalmente; un test
compara el SQL con las constantes del dominio (patrón de F-037 R2).

## Los plazos pactados

R4. `tesoreria.plazos_forma_pago`: una fila por forma de PAGO (`raw.auxpag`) y, si D7-A, por
forma de COBRO (`raw.auxcob`), con `sentido` (PAGO/COBRO), id, código, nombre, medio (`auxefp` /
`auxefc`), `plazo_formula` VERBATIM, `dias_vencimientos` (INT[]), `num_vencimientos`,
`dias_retencion` y `formula_reconocida`. Sin filtrar las de baja; con `fecha_baja`.

R5. `tesoreria.condiciones_contrato_compra`: una fila por contrato de compra (`raw.ctr`), con
obra, empresa, proveedor (id y nombre), estado (código), importe base (`totbas`) e IVA
(`totiva`) del contrato, forma de pago y sus columnas leídas de R4, días fijos de pago y meses
sin pago del proveedor (`prv.pagdia`, `prv.pagmes`, texto tal cual; D11), y la retención de
garantía: porcentaje en tanto por cien, concepto y clase, con el criterio de clase 4 o 5 de
F-128 (D8).

R6. SI el tercero de un contrato es un empleado (`con.tip = 43`), ENTONCES el contrato no debe
publicarse (medido: 0); un test exige el filtro en el SQL.

R7. (D7-A) `tesoreria.condiciones_contrato_cliente`: una fila por contrato de obra con el cliente
(`raw.obrctr`), con obra, forma de COBRO y sus columnas de R4, retención de garantía (porcentaje
de `coegar` o, si no, de `rec.valpor` por `retide`, y su concepto), `plaret` y `plagar` (meses) y
`fecinigar`, todo tal cual.

R8. Ni R4, ni R5, ni R7 deben calcular una fecha de pago o de cobro, ni sumar días a nada.

## El devengo pendiente

R9. `tesoreria.devengo_pendiente_obra_mes`: una fila por (`obra_id`, `anio_mes`, `concepto`,
`categoria`) con empresa y clave de la obra, el devengo pendiente (`importe_devengo`, SUMA del
`importe_mes` planificado de `mart.fact_seguimiento_mensual`), `num_partidas`, la versión que
mart eligió para ESE mes (número, tipo, fecha de creación) y `mes_ultimo_cierre` (D2, D3, D5).

R10. R9 debe leer la planificación de `mart.fact_seguimiento_mensual`, que ya elige la versión
vigente mes a mes (`R-VERSION-MASTER`), y NO de `stg.plan_mensual`; un test lo prohíbe.

R11. Cada fila debe llevar `mes_pasado_sin_cierre` = el mes es anterior al mes del build (plan
de un mes ya pasado que la obra no ha cerrado; medido: 3 obras, 4,79 M€ de coste).

R12. (D4-A) `tesoreria.devengo_corte_obra`: una fila por (`obra_id`, `concepto`) con devengo
pendiente, con `mes_ultimo_cierre`, `real_origen_corte` (SUMA del `importe_mes` real de mart:
el acumulado al último cierre, F-118), `num_versiones_pendientes`, y la versión del ÚLTIMO mes
pendiente con su `plan_hasta_corte` y `plan_total`, de `stg.plan_mensual` FILTRANDO por obra,
ámbito master Y esa versión (el único acceso a `stg` permitido; test).

R13. Contraste MANUAL tras el build: en las (obra, concepto) con `num_versiones_pendientes = 1`,
`plan_total − plan_hasta_corte` debe igualar la suma de R9 al céntimo; si no, se documenta antes
del review (hoy todas tienen una sola versión pendiente).

R14. Ninguna tabla de las de R4-R12 debe tener una columna de caja: un test recorre las
columnas declaradas en el setup y rechaza `caja`, `flujo`, `previst`, `fecha_pago`, `fecha_cobro`
y `con_iva` en sus nombres, y el SQL de 04-07 no puede sumar `INTERVAL` ni días a una fecha.

## La obra de los efectos (D4-B de F-037, D10)

R15. (D10-A) La obra de un efecto debe decidirse con una única función de dominio, en este
orden: (1) centro de coste que resuelve a obra; (2) si el efecto TIENE centro y no es obra:
ninguna (es estructura); (3) sin centro: la obra única de los contratos de la factura (cabecera y
líneas); (4) la obra de la cabecera de la factura (`dcf.obride`); (5) la obra única de sus
líneas (`dcfpro.obride`); si no, ninguna. Devuelve la obra y la vía.

R16. (D10-A) `tesoreria_restringida.efectos` y `tesoreria.efectos` deben ganar al final
`obra_via` (`CENTRO`, `CONTRATO`, `FACTURA_CABECERA`, `FACTURA_LINEAS` o NULL) y rellenar
`obra_id`, `codigo_obra` y `nombre_obra` con la cascada; con varias obras candidatas en un
escalón, ese escalón no decide. El SQL lleva los literales del dominio (test).

R17. `compras.vencimientos` debe conservar sus columnas, nombres, orden y tipos (test de F-037).

R18. La cobertura de obra antes y después (pagos, cobros y cartera viva) debe quedar medida
contra Azure tras el primer build y en la ficha: MANUAL (hoy 86,87 % → 86,95 % de pagos).

## Lo que no cambia: personal y perfiles

R19. Ningún objeto nuevo debe leer `raw.pag`, `raw.cob`, `tesoreria_restringida`, `raw.emp`,
`raw.hmores` ni `personal`: un test lo exige sobre el SQL de 04-07. Los pagos de personal siguen
solo en `tesoreria_restringida` (`R-PERFILES`), y los objetos nuevos viven solo en `tesoreria`.

R20. Con el login estándar los objetos nuevos se leen; con el restringido de F-141, «permission
denied» como el resto de `tesoreria`: MANUAL (humano).

## El paso y la nocturna

R21. `build_tesoreria` debe ejecutar los sub-pasos nuevos detrás de los cuatro de F-037, con su
tabla destino, y seguir con `depends_on = ["ingest_raw"]`; SI falla uno, FAILED con su nombre.

R22. `LECTURAS_PARA_REANUDAR` debe declarar que `build_tesoreria` lee `build_stg` y `build_mart`
(si se rehacen en un reintento, se rehace la tesorería).

R23. (D7-A) `config/tables_sigrid.yaml` debe ingerir `auxcob` y `auxefc` (78 tablas), con su
ficha en `raw.yaml` y los recuentos de tablas de los tests al día.

R24. `check-declarados` y `check-unicidad` deben conocer los objetos nuevos y sus claves.

## Diccionario y documentación

R25. Fichas de los objetos nuevos y de `obra_via`; la ficha de `tesoreria.efectos` deja de decir
que la obra sale SOLO del centro y que la fase 2 no existe; `compras.formas_pago` y
`compras.contratos` remiten a `tesoreria` para el plazo leído y las condiciones.

R26. Regla dura nueva `R-CAJA-HIPOTESIS` (bloqueante, `entrega: resumen`; D12): no hay caja
proyectada; quien convierta devengo en caja debe declarar versión y mes de corte, plazo y su
fuente, retención (porcentaje, plazo y fuente: Sigrid o `retenciones.fin_obra`), tratamiento del
IVA (el devengo va sin IVA, los efectos con IVA) y el solape con la cartera PREVISTA.

R27. El `resumen` de R26 debe nombrar `tesoreria.devengo_pendiente_obra_mes`, «hipótesis» e
«IVA», y su `ambito` debe incluir los objetos de R4, R5, R7, R9 y R12 y
`mart.fact_seguimiento_mensual`; el presupuesto de F-147 se respeta (o se sube con su motivo).

R28. CUANDO se pregunte al MCP, en una conversación nueva, por la caja futura de una obra, la
respuesta debe declarar la hipótesis sin que se le pida: MANUAL (humano), con la pregunta y la
respuesta anotadas.

R29. `docs/ARCHITECTURE.md`, `CLAUDE.md` (mapa) y `azure-apps/datamart_seg_anual.md` al día en el
mismo trabajo; `version` del diccionario +1 sobre el valor real.

## Verificación

R30. Coste medido en el primer `build-tesoreria` (estimado +2-3 min).

R31. Contraste MANUAL de solo lectura tras el build: 21 obras con devengo pendiente (± la
variación diaria), sumas de R9 por concepto frente a `progress/spec_F-140.md` §2, y las 122
fórmulas reconocidas.

R32. `bash harness/init.sh` en verde (pytest, cobertura y mutación de rigor `estandar`).
