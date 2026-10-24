<!-- specs/F-140-proyeccion-caja-ingredientes/requirements.md -->
# F-140 · De devengo a caja: los ingredientes y las hipótesis

Mediciones: `progress/spec_F-140.md`. Decisiones en `design.md` §9; los requisitos van con la
opción recomendada y marcan «(Dn)». Rehecha el 2026-10-24 con las indicaciones del humano.
**Objetivo**: que la IA pase el DEVENGO de una obra (cobros y pagos) a criterio de CAJA, en vivo.
El datamart NUNCA convierte: publica ingredientes, hipótesis con valores por defecto y por obra, y
una regla dura que obliga a declararlas todas.

Vocabulario:
- **Versión V**: la master que rige el último mes pendiente de la obra y el concepto (COSTE,
  VENTA), la que `mart` elige (`R-VERSION-MASTER`). **Mes de V**: el de su `version_fec_efectiva`.
- **Intervalo**: los meses desde el mes de V hasta el último cierre real del concepto, ambos incluidos.
- **Pendiente de una partida** = máx(0, plan de V desde su mes − ejecutado real en el intervalo).
- **Hipótesis**: un supuesto de conversión con código `H..` (catálogo en `design.md` §6). **Nivel**
  del valor: `DEFECTO` (catálogo), `OBRA` (personalizado o leído de Sigrid) o `USUARIO` (en vivo).
- **Columna de caja**: una fecha, mes o importe que resulte de APLICAR un plazo, una retención o
  un IVA a un devengo. Ninguna se publica.

## Las hipótesis y sus valores

R1. El catálogo de hipótesis debe vivir en `config/hipotesis_caja.yaml` (D13) con, por cada una:
`codigo`, `sentido` (PAGO, COBRO, AMBOS), `descripcion`, `unidad`, `valor_defecto`,
`fuente_defecto` (de qué dato o decisión sale), `ingrediente` (objeto donde la IA lee el dato que
la alimenta), `validado` (si Negocio ya aprobó el valor) y `admite_obra`.

R2. El sistema debe validar el catálogo con una función de dominio: códigos únicos con el patrón
`H[0-9]{2}`, unidades de una lista cerrada, valor compatible con la unidad; SI falla, ENTONCES el
paso falla con la lista de errores, sin publicar nada a medias.

R3. Los valores por obra deben venir de (D14) la sección `obras` del mismo YAML (`clave_obra`,
`codigo`, `valor`, `motivo`, `fecha`), validados igual; SI una obra o un código no existen,
ENTONCES el paso falla diciendo cuáles.

R4. `tesoreria.hipotesis_caja` debe publicar el catálogo tal cual, una fila por código.

R5. `tesoreria.hipotesis_caja_obra` debe publicar, por (obra con devengo pendiente o con valor
manual, código), el valor resuelto con una única función de dominio: `MANUAL` del YAML gana a
`SIGRID` (D18: leído de los contratos de la obra, solo si es único), y si no hay ninguno,
`DEFECTO`; con columnas `valor`, `nivel` (`OBRA`/`DEFECTO`), `fuente` y `motivo`.

R6. Ningún valor de hipótesis debe aplicarse en el SQL a un importe ni a una fecha (R16).

## La fórmula de plazo y las condiciones pactadas

R7. Una única función de dominio debe leer una fórmula de plazo (`auxpag`/`auxcob.formul`): token
`N` = días de un vencimiento, `NR` = días del de RETENCIÓN; devuelve los días en el orden
escrito, la retención o `None`, y si se ha reconocido. Blancos repetidos separan igual que uno.

R8. SI la fórmula está vacía, es `NULL`, tiene un token que no es `N` ni `NR` o dos `NR`,
ENTONCES «no reconocida», sin días ni retención (falla cerrado). El SQL lleva los mismos regex
que el dominio, literalmente (test).

R9. `tesoreria.plazos_forma_pago` (vista): una fila por forma de PAGO (`auxpag`) y de COBRO
(`auxcob`, D7), con sentido, id, código, nombre, medio, `plazo_formula` VERBATIM,
`dias_vencimientos`, `num_vencimientos`, `dias_retencion`, `formula_reconocida` y `fecha_baja`.

R10. `tesoreria.condiciones_contrato_compra`: una fila por contrato de compra con obra, empresa,
proveedor, estado, importe base e IVA, forma de pago con las columnas de R9, días fijos de pago y
meses sin pago del proveedor (tal cual, D11) y retención de garantía (porcentaje, concepto, clase
4 o 5, D8). SI el tercero es un empleado (`tip = 43`), ENTONCES no se publica (medido: 0).

R11. (D7) `tesoreria.condiciones_contrato_cliente`: una fila por contrato con el cliente
(`obrctr`) con obra, cliente, forma de COBRO con las columnas de R9, retención (`coegar` o, si
no, `rec.valpor` de `retide`, con su fuente y concepto), `plaret`, `plagar` y `fecinigar`.

## El devengo pendiente, descontado lo ejecutado desde la versión (D3, D5)

R12. `tesoreria.devengo_pendiente_partida`: una fila por (obra, partida, concepto) con plan de V,
con categoría, V (número, tipo, mes), `mes_ultimo_cierre`, `plan_desde_version`,
`plan_intervalo`, `ejecutado_intervalo`, `plan_restante`, `pendiente` y `sobre_ejecutado`
(máx(0, ejecutado − plan desde V)), calculados con una función de dominio por partida.

R13. El plan debe leerse de `stg.plan_mensual` FILTRANDO obra, ámbito master (8 coste, 11 venta)
y versión V, y lo ejecutado de las filas REALES de `mart.fact_seguimiento_mensual`; un test
rechaza cualquier lectura de `stg.plan_mensual` sin filtro de versión.

R14. `tesoreria.devengo_pendiente_obra_mes`: una fila por (obra, mes, concepto, categoría) con
`importe_plan_restante` (perfil de V tras el cierre) e `importe_pendiente`: el pendiente de cada
partida repartido en proporción a su perfil restante; el de una partida SIN meses restantes, al
primer mes pendiente, también en `importe_retraso_sin_perfil` (D19). El último mes del perfil de
cada partida absorbe el redondeo: la suma iguala R12 al céntimo (test del dominio).

R15. `tesoreria.devengo_corte_obra`: una fila por (obra, concepto) con V, `mes_version`,
`mes_ultimo_cierre`, `num_versiones_pendientes`, las sumas de R12 (y `adelantado`, `retrasado`,
`ejecutado_sin_plan`, `retraso_sin_perfil`), `real_origen_corte`, `plan_total` y la frontera con
la cartera (D16): `cartera_viva` (PREVISTO y no antiguo) y `cartera_emitida_tras_cierre` del
sentido del concepto, de `tesoreria.efectos`.

R16. Ninguna tabla de R4-R15 debe tener una columna de caja: un test rechaza `caja`, `flujo`,
`previst`, `fecha_pago`, `fecha_cobro` y `con_iva` en sus nombres, y el SQL nuevo no puede sumar
`INTERVAL` ni días a una fecha, ni multiplicar por un valor de hipótesis.

## La obra de los efectos (D10, abierta)

R17. (Si D10-A) La obra de un efecto sin centro debe salir de una función de dominio en este
orden: centro con obra; centro sin obra → ninguna; obra única de los contratos de la factura;
obra de su cabecera; obra única de sus líneas. Las dos `efectos` ganan `obra_via` al final y
`compras.vencimientos` conserva sus columnas (test de F-037).

## Lo que no cambia: personal y perfiles

R18. Ningún objeto nuevo debe leer `raw.pag`, `raw.cob`, `tesoreria_restringida`, `raw.emp`,
`raw.hmores` ni `personal` (test); `devengo_corte_obra` lee la cartera de `tesoreria.efectos`, la
GENERAL. Los pagos de personal siguen solo en `tesoreria_restringida` (`R-PERFILES`).

R19. Con el login estándar los objetos nuevos se leen; con el restringido de F-141, «permission
denied» como el resto de `tesoreria`: MANUAL (humano).

## El paso, la ingesta y el diccionario

R20. `build_tesoreria` debe ejecutar los sub-pasos nuevos detrás de los de F-037, con su tabla
destino y `depends_on = ["ingest_raw"]`; SI falla uno, FAILED con su nombre.
`LECTURAS_PARA_REANUDAR` declara que lee `build_stg` y `build_mart`.

R21. (D7) `config/tables_sigrid.yaml` debe ingerir `auxcob` y `auxefc` (78 tablas), con fichas
en `raw.yaml`. `check-declarados` y `check-unicidad` conocen los objetos nuevos y sus claves.

R22. Fichas de los objetos nuevos; la de `tesoreria.efectos` deja de decir que la fase 2 no
existe; `compras.formas_pago` y `compras.contratos` remiten a `tesoreria`.

R23. Regla dura nueva `R-CAJA-HIPOTESIS` (bloqueante, `entrega: resumen`, D12): no hay caja
proyectada; quien pase devengo a caja debe declarar TODAS las hipótesis del catálogo, cada una
con su valor y su nivel (`DEFECTO`, `OBRA` o `USUARIO`), avisar de las no validadas, y no repetir
lo que ya está en la cartera (`cartera_viva`, `cartera_emitida_tras_cierre`, albaranes).

R24. El `resumen` de R23 debe nombrar `tesoreria.hipotesis_caja_obra`, «hipótesis», `DEFECTO`,
`OBRA` y `USUARIO`; su `ambito`, los objetos nuevos y `mart.fact_seguimiento_mensual`; el
presupuesto de F-147 se respeta o se sube con su motivo.

R25. CUANDO se pregunte al MCP, en una conversación nueva, por la caja futura de una obra (y
luego con un plazo dado por el usuario), la respuesta debe listar cada hipótesis con valor y
nivel sin que se le pida, y marcar `USUARIO` la dada: MANUAL (humano), anotado.

R26. `docs/ARCHITECTURE.md`, `CLAUDE.md` (mapa) y `azure-apps/datamart_seg_anual.md` al día;
`version` del diccionario +1 sobre el valor real.

## Verificación

R27. Coste medido en el primer `build-tesoreria` (estimado +3-4 min).

R28. Contraste MANUAL de solo lectura tras el build frente a `progress/spec_F-140.md` §5 (21
obras, pendiente ajustado por concepto ± la variación diaria), las 122 fórmulas reconocidas y,
si D10-A, la cobertura de obra antes y después.

R29. `bash harness/init.sh` en verde (pytest, cobertura y mutación de rigor `estandar`).
