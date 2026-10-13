<!-- specs/F-037-tesoreria/requirements.md -->
# F-037 · Fase 1: la cartera de cobros y pagos, sin obras

Mediciones: `progress/spec_F-037.md`. Decisiones D1-D10 en `design.md` §8: **los
requisitos siguen la opción recomendada**. **Alcance.** Cada efecto de `raw.pag` y `raw.cob` tal cual: es un HECHO, no un cálculo.
**FUERA, y se dice en la ficha**: la fase 2 (devengo pendiente de `stg.plan_mensual`,
plazos de `auxpag`/`auxefp`, retención de `ctrrec`) y cualquier conversión devengo → caja,
que es una hipótesis y la pone la IA en la consulta, declarándola.

Vocabulario:
- **Efecto**: una fila de `raw.pag` (sentido `PAGO`, `con.tip = 25`) o de `raw.cob`
  (`COBRO`, `tip = 24`). Su `ide` es un `con.ide`: único entre los dos (256.952 + 21.914).
- **Efecto de personal** (decisión del humano del 2026-10-13: «los pagos de nominas deben
  quedar restringidos»): `natide <> 0` (NOMINAS, EMBARGO, CUOTAS), o cuenta con prefijo
  de `REGEX_CUENTA_RESTRINGIDA` (F-135), o tercero empleado (`con.tip = 43`), o documento
  origen nómina (`con.tip = 306`), o cuenta que no resuelve (falla cerrado). Medido: 37.053
  pagos, los cuatro criterios coinciden; 0 cobros.
- **Rol estándar** `mcp_sigrid_dm_ro`; **autorizado** `sigrid_dm_restringido_ro`; **total** `mcp_sigrid_dm_total`.

## El criterio y el estado (dominio puro)

R1. El sistema debe decidir si un efecto es de personal con una única función de dominio
que recibe naturaleza, código y presencia de cuenta, tipo de `con` del tercero y del
documento origen, y devuelve el motivo (`NATURALEZA`, `CUENTA`, `CUENTA_SIN_RESOLVER`,
`TERCERO_EMPLEADO`, `DOCUMENTO_NOMINA`, en ese orden de precedencia) o `None`.

R2. El criterio de cuenta debe reutilizar `REGEX_CUENTA_RESTRINGIDA` de
`domain/restriccion_personal.py` (no una copia), y el SQL debe llevar ese literal y los
códigos 43 y 306 tal cual: un test compara el SQL con las constantes del dominio.

R3. El sistema debe derivar `estado_tesoreria` con una única función de dominio, igual en
los dos sentidos: `BAJA` si `con.fecbaj <> 0` o `con.est IN (14, 15)`; si no, `REALIZADO`
si `fecrea <> 0` o `con.est = 10`; si no, `PREVISTO` (precedencia de F-094).

R4. `importe_flujo` debe ser `+importe` en `COBRO` y `-importe` en `PAGO`, con el signo de origen.

## La cartera completa: `tesoreria_restringida.efectos`

R5. `tesoreria_restringida.efectos`: una fila por efecto de `raw.pag` y `raw.cob`, sin `WHERE` (un test lo prohíbe), PK `efecto_id`.

R6. Código, descripción, serie (lógica de `compras.fn_serie`), empresa, estado y baja del efecto se
deben LEER de la fila `raw.con` del propio efecto (`con.ide = efecto.ide`), nunca derivar.

R7. Cada fila debe llevar: sentido; empresa; documento origen (id, código, tipo de `con` y
`es_factura_compra` = existe en `raw.dcf`); tercero (id, nombre de `con.res`, CIF de
`raw.prv` solo en `PAGO`); fechas de emisión, vencimiento y real; importe e `importe_flujo`;
`estado_tesoreria`, `estado_codigo`, `estado_sigrid` (`raw.conest` con el `tip` del
sentido, `LEFT JOIN`), `efecto_anulado` y `fecha_anulacion`; medio de pago (`auxefp`),
naturaleza (`auxnap`), cuenta (código y nombre), banco y sucursal (`auxban`), retención,
remesa (código de `con`; fecha e importe de `raw.rpa` solo en `PAGO`), `restringido` y
`motivo_restriccion`.

R8. La obra debe salir SOLO del puente centro → obra (`maestro.centros_coste` por
`cenide`): `centro_coste_id`, `obra_id`, `codigo_obra`, `nombre_obra`; sin centro o con un
centro que no es obra, NULL. Sin respaldo por líneas (D4). Medido: 77,9 % de pagos y 78,0 %
de cobros con obra.

R9. El sistema NO debe publicar la cuenta bancaria del tercero (`bancue`, `ban`, `bandig`,
`cpa*`: 111.450 pagos la traen), ni `padide` ni `prpide` (vacíos o sin uso).

## La cartera general: `tesoreria`

R10. El sistema debe publicar `tesoreria.efectos` con las filas de la completa que no son
de personal y las mismas columnas en el mismo orden, sin `restringido` ni
`motivo_restriccion`.

R11. SI la remesa de un efecto contiene algún efecto restringido, ENTONCES
`tesoreria.efectos.importe_remesa` debe ser NULL (medido: 1 remesa mixta; su total
delataría los dos efectos de nómina que lleva).

R12. SI tras construir la general alguna fila cumple el criterio de personal, o la general
más los restringidos no suman el recuento de la completa, ENTONCES el SQL debe lanzar
`RAISE` y la transacción se debe deshacer (queda la tabla de la noche anterior).

R13. El sistema debe publicar `tesoreria.efectos_restringidos_mes` (empresa, sentido, año, mes
de vencimiento, `estado_tesoreria`, `num_efectos`), SIN importes (D6).

R14. Las tres tablas no se deben dropear cada noche: `CREATE TABLE IF NOT EXISTS` en el
setup y `TRUNCATE` + `INSERT` en cada build (patrón de `personal`), para que las vistas que
cuelgan de ellas sobrevivan.

## `compras.vencimientos` pasa a ser vista de la general (D1)

R15. `compras.vencimientos` debe ser una VISTA sobre `tesoreria.efectos` filtrada a `PAGO`
y `es_factura_compra`, con las MISMAS columnas, nombres, orden y tipos que la tabla de
F-080; un test fija la lista de columnas.

R16. CUANDO se construye `compras`, `05_vencimientos.sql` debe borrar el objeto anterior sea
tabla o vista y crear la vista; `06_pago_factura.sql` no cambia. Su recuento debe igualar el
de hoy (197.190 el 2026-10-13, ± la variación diaria): MANUAL.

## El paso y la nocturna

R17. El sistema debe tener el paso `build_tesoreria` (stage `build_aux`, `depends_on =
["ingest_raw"]`) en `run-all` DELANTE de `build_compras`, y el comando
`python main.py build-tesoreria`. Ningún paso lo declara en su `depends_on`.

R18. SI falla un sub-paso, ENTONCES el paso debe terminar en FAILED con el nombre del
sub-paso en el mensaje y la nocturna debe continuar.

R19. `check-declarados` y `check-unicidad` deben conocer los objetos nuevos (con sus claves).

## Permisos (patrón F-135 / F-136)

R20. `tesoreria` debe entrar en `DEFAULT_CONSUMPTION_SCHEMAS`, y `tesoreria_restringida` en
`DEFAULT_VETOED_SCHEMAS` y `DEFAULT_RESTRICTED_SCHEMAS` (y en `.env.example`).

R21. CUANDO corre `apply_grants`, el rol estándar NO debe leer `tesoreria_restringida`
(verificación en el catálogo; si la lee, FAILED con la lista) y el autorizado SÍ; el total
la lee por pertenencia, sin GRANT propio, y sigue sin leer `raw`.

R22. `infra/sql/02_roles.sql` debe vetar `tesoreria_restringida` al estándar y concederla
al autorizado como hace con `contabilidad_restringida`; un test exige que sus listas casen
con `settings.py`.

R23. Prueba NEGATIVA con el login estándar real (`permission denied` en
`tesoreria_restringida.efectos`; 0 filas con `natide <> 0` en `tesoreria.efectos`) y
POSITIVA con el total (recuento = `raw.pag` + `raw.cob`): MANUAL (humano).

## Diccionario y documentación

R24. Fichas de `tesoreria.efectos`, `tesoreria.efectos_restringidos_mes` y
`tesoreria_restringida.efectos`; entradas de los dos esquemas en `00_global.yaml` y en
`ESQUEMAS_DEL_DATAMART`; la ficha de `compras.vencimientos` pasa a vista y cita su origen.

R25. Regla dura `R-TESORERIA-ESTADO`: nunca se suma `BAJA`; «fecha real vacía» no es
«previsto»; la cartera prevista es `estado_tesoreria = 'PREVISTO'`, y un previsto con
vencimiento pasado es un vencido sin puntear, no caja futura.

R26. La regla `R-CONTABILIDAD-RESTRINGIDA` (o una hermana) debe cubrir tesorería: la
general no tiene los pagos de personal; los dos esquemas no se suman.

R27. La ficha de `tesoreria.efectos` debe declarar: cobertura floja de cobros sin F-040
(21.914 efectos, sin documento de venta); la duda de las retenciones de cliente de baja
(F-094: 19,9 M€); que es caja/cartera y no devengo, y que la fase 2 no existe.

R28. `docs/ARCHITECTURE.md`, `azure-apps/datamart_seg_anual.md` y el contrato para
`mcp-bbdd` (`tesoreria` en la lista blanca de las dos conexiones, `tesoreria_restringida`
solo en la total) deben actualizarse en el mismo trabajo.

## Verificación

R29. El coste del paso en la ventana (hoy 4 h 52 min, tope del job 7 h) debe quedar medido
en el primer build manual y anotado; estimado +1-3 min y +0,2 GB.

R30. Contraste MANUAL de solo lectura: `PAGO` `PREVISTO` de la general frente al saldo de
las cuentas 40 y 41 en `contabilidad.mayor` (`importe_saldo`) (hoy 80,1 M€ frente a 78,8 M€), y
`COBRO` `PREVISTO` frente a 43 (40,2 M€ frente a 47,5 M€); la diferencia se anota.

R31. `bash harness/init.sh` en verde (pytest, cobertura, mutación sin supervivientes).