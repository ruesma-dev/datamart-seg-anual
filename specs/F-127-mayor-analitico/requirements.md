<!-- specs/F-127-mayor-analitico/requirements.md -->
# F-127 · Requisitos (EARS)

Origen: correos de Juan Romero del 24-09 y del 06-10 (ficha de F-127). Criterio heredado: R23 de
F-135 (nace restringido) y F-141/F-146 (el perfil restringido no lo ve). Mediciones del
2026-11-20: `progress/spec_F-127.md`. Decisiones abiertas: §Decisiones de `design.md`.

## El mayor analítico completo (`contabilidad_restringida`)

R1. El sistema debe publicar `contabilidad_restringida.mayor_analitico` con una fila por fila de
`raw.apa`, sin filtrar ninguna, con `apunte_analitico_id` (`apa.ide`) como clave primaria.
(capa: integración)

R2. CUANDO termina el SQL del mayor analítico completo, SI su recuento no es el de `raw.apa`,
ENTONCES el sistema debe hacer fallar el sub-paso con las dos cifras en el mensaje y deshacer el
fichero entero. (capa: unit)

R3. El sistema debe publicar en cada fila: asiento (`conide`), `tipo_asiento` (`CONTABLE` si
`con.tip = 20`, `ANALITICO` si `con.tip = 32`, `OTRO` si no), código de asiento, posición, fecha
(`apa.fec`), ejercicio, mes, empresa (la del asiento), centro de coste con su código, obra y
`clave_obra` por `maestro.centros_coste`, cuenta analítica con su código y descripción (de
`raw.con`), concepto, documento, punteo, debe, haber, `importe = debe - haber`, el apunte
financiero (`apuide`, NULL si 0) con su cuenta financiera, y `es_contrapartida_recurso`. (capa: unit)

R4. El sistema NO debe leer `apa.obride`, `apa.obr`, `apa.ori`, `apa.canal`, `apa.delo` ni `apa.del`:
la obra sale solo del centro del apunte analítico. (capa: unit)

R5. El sistema debe calcular `saldo_acumulado` como la suma de `importe` de la cuenta analítica
hasta la fila inclusive, en el orden fecha, código de asiento, posición, `apunte_analitico_id`.
(capa: unit)

R6. DONDE el asiento es `ANALITICO` y sus filas que no son de CP cargan a UNA sola obra, el sistema
debe publicar esa obra en `obra_imputada_id` y `clave_obra_imputada` en todas las filas del asiento;
si cargan a ninguna o a varias, NULL. (capa: unit) [D4]

## Qué fila analítica es restringida (R23 de F-135, criterio V2)

R7. El sistema debe marcar una fila como restringida si se cumple cualquiera de: (C1) su `apuide`
es un apunte con `restringido` en `contabilidad_restringida.mayor`; (C2) su `conide` es un asiento
de personal (todos sus apuntes `NORMAL` y alguno restringido); (C3) su cuenta analítica es una CP,
es decir, un `raw.res.caaconide` distinto de 0 [D7: o una cuenta de un centro de CP con abono en un
asiento `ANALITICO`].
(capa: unit)

R8. El sistema debe publicar `motivo_restriccion` con este orden de precedencia: `CONTRAPARTIDA`
(C3), `APUNTE_SIN_RESOLVER` (R9), `APUNTE_RESTRINGIDO` (C1), `ASIENTO_PERSONAL` (C2); NULL si es
visible. (capa: unit)

R9. SI una fila trae `apuide` distinto de 0 y ese apunte no está en `contabilidad_restringida.mayor`,
ENTONCES el sistema debe tratarla como restringida (falla cerrado), con motivo
`APUNTE_SIN_RESOLVER`. (capa: unit)

R10. El SQL debe llevar el criterio con los mismos literales que el dominio
(`etl_sigrid/domain/restriccion_personal.py`), y un test debe compararlos. (capa: unit)

R11. El sistema debe publicar `restringido` (nunca NULL) y `saldo_acumulado_visible`: el acumulado
de la cuenta sumando solo lo visible, NULL en las filas restringidas. (capa: unit)

## Los saldos por cuenta analítica y mes

R12. El sistema debe publicar `contabilidad_restringida.saldos_cuenta_analitica_mes` desde el mayor
analítico completo, una fila por (`cuenta_analitica_id`, `centro_coste_id`, `empresa_id`,
`ejercicio`, `mes`) con alguna fila, con `num_apuntes`, debe, haber, `importe` y `saldo_acumulado` a
fin de mes; las filas sin cuenta o sin centro se agrupan con 0. (capa: unit)

R13. La suma de `importe` de los saldos por cuenta debe igualar la del mayor analítico, y su
último `saldo_acumulado`, el último del mayor. (capa: integración)

## La versión general (`contabilidad`)

R14. El sistema debe publicar `contabilidad.mayor_analitico` con solo las filas no restringidas,
las columnas de R3 salvo `es_contrapartida_recurso`, y `saldo_acumulado` igual al
`saldo_acumulado_visible` del completo. (capa: unit)

R15. CUANDO termina el SQL del mayor analítico general, SI contiene alguna fila de una cuenta CP,
alguna fila cuyo apunte es restringido o sin resolver, o si general más restringidas no suman el
completo, ENTONCES el sistema debe hacer fallar el sub-paso y deshacer el fichero. (capa: unit)

R16. El sistema debe publicar `contabilidad.saldos_cuenta_analitica_mes` con los agregados de R12
calculados solo sobre lo visible, sin las filas que no tienen nada visible, y al final
`num_apuntes_restringidos` e `incompleto`. Solo recuentos de lo restringido, nunca importes.
(capa: unit)

R17. El sistema debe publicar `contabilidad.apuntes_analiticos_restringidos_mes`: cuántas filas
analíticas restringidas hay por empresa, ejercicio y mes, y cuántas por motivo; sin importes.
(capa: unit)

## Encaje en el paso y en los permisos

R18. El sistema debe construir los cinco objetos dentro de `build_contabilidad`, detrás de los
ocho sub-pasos actuales y sin cambiar ninguno de ellos ni su `depends_on`. (capa: unit)

R19. El sistema NO debe conceder ningún objeto del mayor analítico al perfil restringido ni al de
postventa: `contabilidad` y `contabilidad_restringida` siguen fuera de sus listas de esquemas, y
`PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES` sigue vacía. (capa: unit) [D3]

R20. CUANDO se despliega, los roles estándar, restringido y postventa deben ver
`has_table_privilege(..., 'SELECT')` falso en los dos objetos de `contabilidad_restringida`, y el
restringido y el postventa, también en los tres de `contabilidad`. (capa: integración, MANUAL)

## Diccionario y documentación

R21. El diccionario debe llevar ficha de los cinco objetos (clave declarada, relaciones a
`maestro.cuentas_analiticas`, `maestro.centros_coste`, `contabilidad.mayor` y
`personal.recursos.cuenta_analitica_contrapartida_id`), con `version` subida en `00_global.yaml`.
(capa: unit)

R22. Las fichas deben decir, con las cifras medidas: que el saldo analítico SÍ es `debe - haber`
(no hay cierres ni aperturas); que el mayor analítico y `contabilidad.mayor` no se suman entre sí;
que el asiento de nómina cargó las CP hasta marzo de 2026 y no desde abril (aviso de Juan); y que el
perfil restringido no las lee. (capa: unit)

R23. La ficha del mayor analítico completo debe decir cómo responder «saldo y movimientos de la CP
del trabajador X en la obra Y» y su cruce con `personal.partes_lineas` (por la CP de
`personal.recursos` y `obra_imputada_id`), sin que el consumidor tenga que deducirlo. (capa: unit)

R24. `docs/ARCHITECTURE.md` y `azure-apps/datamart_seg_anual.md` deben describir los objetos nuevos,
quién los lee y el criterio de restringido. (capa: unit)

## Aceptación en producción (MANUAL, humano)

R25. CUANDO el humano lanza `build-contabilidad` en Azure, los recuentos deben ser los de `raw.apa`
(completo) y completo = general + restringidas, y el tiempo añadido al paso debe quedar anotado
frente a la ventana nocturna. (capa: integración, MANUAL)

R26. CUANDO el humano pregunta por el MCP con el perfil total «saldo y movimientos de la cuenta CP
del recurso X en la obra Y y su cruce con lo imputado en sus partes», la respuesta debe salir del
diccionario sin explicación adicional. (capa: integración, MANUAL)
