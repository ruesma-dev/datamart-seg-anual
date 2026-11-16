# F-104 · La retención de CLIENTE saneada — requisitos (EARS)

Rigor `estandar`, prioridad 1. Mediciones: `progress/spec_F-104.md` (solo lectura, 2026-11-06 y
**revalidación 2026-11-16**). Antecedentes: F-094 (estado de PROVEEDOR), F-095 (la contabilidad
manda; H5 deja fuera el cliente), F-150 (la retención de 0686), F-040 (ingiere `raw.cli`).
**[rev. 16-11]** marca lo que cambia frente a la versión aprobada el 2026-11-07 (design §9).

## Contexto en cuatro líneas

Los 1.956 efectos «vivos» con baja (19,93 M) **están agrupados**: en `cob` el original queda en
`est 1` con `fecbaj` = fecha del agrupador AGR (en `pag` iría a `est 14`), y el AGR y sus DIV
llevan `retide = 0`, así que `movimientos` no los ve. La retención viva de verdad está en las
cuentas de retención de cliente: **[rev. 16-11]** 16,00 M en la contabilidad y 10,53 M en sus
efectos vivos; la diferencia, casos concretos (mediciones §3-§4 y §7).

## Estado del efecto de cliente

- R1. El sistema debe derivar `estado` de las filas CLIENTE de `retenciones.movimientos` de la
  ficha `raw.con` del propio efecto con la precedencia de F-094: `BAJA` si `con.fecbaj <> 0` o
  `con.est IN (14, 15)`; si no, `LIQUIDADA` si `cob.fecrea <> 0` o `con.est = 10`; si no, `VIVA`.
  (capa: unit)
- R2. El sistema debe marcar `vencida_sin_liquidar` en CLIENTE solo para filas que cumplan la
  condición de `VIVA` de R1 y tengan vencimiento anterior a la fecha del build. (capa: unit)
- R3. La cabecera de `01_movimientos.sql` debe explicar por qué el criterio vale en cliente aunque
  `cob` no use `est 14`: el original agrupado queda en `est 1` con `fecbaj` = fecha del AGR, con
  el caso medido (cuenta 4308001150: AGR20/0010 = 57.973,72 € = sus cinco originales). (capa: unit)

## El dinero agrupado: efectos de las cuentas de retención

- R4. **[rev. 16-11, D3]** El sistema debe publicar en `retenciones.cuentas_cliente` una fila por
  cuenta de retención de cliente: la UNIÓN de las que declara un cliente en `raw.cli.cueretide`
  (211 el 2026-11-16) y las cuentas imputables de `raw.con` (`tip = 17`) con código `^43[0-9]8`
  (221), 225 en total; con `cuenta_id` (clave primaria), `cliente_id` (el que la declara; NULL si
  ninguno), `codigo_cuenta`, `nombre_cuenta`, `familia` (4 dígitos) y `criterio_seleccion` =
  `CUERETIDE` si la declara un cliente o `PREFIJO_43X8` si solo entra por el código. (capa: unit)
- R5. **[rev. 16-11]** SI `retenciones.cuentas_cliente` queda vacía, o si dos clientes declaran la
  misma cuenta, ENTONCES el sub-paso `movimientos` debe fallar con un mensaje que nombre la tabla,
  antes de construir `movimientos`. (capa: unit)
- R6. El sistema debe incluir en la rama CLIENTE de `movimientos` los efectos de `raw.cob` con
  `retide <> 0` (como hoy) **y** los de `retide = 0` cuya `cueide` esté en `cuentas_cliente` (los
  agrupadores AGR, sus DIV y los efectos de retención sin tipo). (capa: unit)
- R7. El sistema debe publicar en `movimientos` la columna `origen_retencion`: `EFECTO_RETENCION`
  si el efecto lleva `retide <> 0`, `CUENTA_RETENCION` si entra solo por R6; en PROVEEDOR,
  siempre `EFECTO_RETENCION`. (capa: unit)
- R8. El sistema debe publicar en `movimientos` la columna `cuenta_id` (`cueide` del efecto, NULL
  si 0) en los dos sentidos. (capa: unit)
- R9. El sistema no debe borrar ninguna fila: las filas CLIENTE con `retide <> 0` y todas las de
  PROVEEDOR deben seguir siendo las mismas, en número e importe, antes y después. (capa:
  integración, MANUAL en T8)
- R10. La clave primaria `(sentido, movimiento_id)` de `movimientos` debe seguir siendo única.
  (capa: unit)

## La contabilidad manda: saldo y cuadre por cuenta

- R11. El sistema debe publicar `retenciones.saldo_contable_cliente`, una fila por cuenta de
  `cuentas_cliente` con apuntes, con `altas`, `bajas`, `saldo_inicial`, `saldo`,
  `saldo_anterior_2016`, `num_apuntes`, `primer_movimiento` y `ultimo_movimiento`, leídos de
  `raw.apu` con `importe = deb - hab` (positivo: retención que nos practican) y la MISMA
  clasificación de apuntes que `03_apuntes_contables.sql` (CIERRE, SALDO_INICIAL, APERTURA, ALTA,
  BAJA); `saldo` = ALTA + BAJA + SALDO_INICIAL: cierres y aperturas no suman nunca. (capa: unit)
- R12. El sistema debe publicar la vista `retenciones.v_cuadre_cliente`, una fila por cuenta con
  saldo o efectos vivos de al menos 1 €, con `saldo_contable`, `viva_efectos` (suma de
  `movimientos` CLIENTE en `VIVA` de esa `cuenta_id`), `diferencia` y `categoria` en el orden de
  `v_cuadre_proveedor`: `CUADRA` (< 1 €), `SIN_EFECTOS_VIVOS`, `SIN_SALDO_CONTABLE`,
  `CONTABILIDAD_MAYOR`, `EFECTOS_MAYOR`, y el nombre de la cuenta. (capa: unit)
- R13. `v_cuadre_cliente` debe LEER el estado de `movimientos`, no recalcularlo de columnas de
  Sigrid (igual que `v_cuadre_proveedor`). (capa: unit)

## Lo que no cambia

- R14. **[rev. 16-11]** El sistema no debe cambiar `tesoreria` (ya aplica la precedencia en los dos
  sentidos), ni `retenciones/00_setup.sql` (lo protege la frontera de F-040), ni la rama PROVEEDOR
  de `movimientos` salvo las columnas de R7 y R8, ni `03`-`07`, ni el SQL de `ventas`.
  (capa: unit)
- R15. Las vistas `v_pbi_*` de `02_views.sql` deben seguir leyendo `estado = 'VIVA'` sin cambios
  de texto: el saneamiento les llega por `movimientos`. (capa: unit)
- R23. **[rev. 16-11, D9]** `entidad_cif` de CLIENTE debe seguir a NULL (la rama CLIENTE no lee
  `cli.cif`), y su ficha debe decir que el CIF del cliente se lee en `ventas.clientes` por
  `entidad_id` = `cliente_id`, enmascarado si es persona física. (capa: unit)
- R24. **[rev. 16-11]** `tests/test_f040_frontera.py` debe admitir en `TOCADOS_DESPUES`, con su
  motivo, `retenciones/01_movimientos.sql` y `retenciones/08_saldo_cliente.sql`, y nada más de
  `retenciones/` ni de `tesoreria/`. (capa: unit)

## Diccionario y documentación

- R16. Las fichas de `config/diccionario/retenciones.yaml` deben describir el estado de CLIENTE
  (R1, con el mecanismo del AGR), `origen_retencion`, `cuenta_id`, `entidad_cif` (R23) y las tres
  tablas o vistas nuevas, con la regla «la retención viva de cliente la manda la contabilidad
  (`saldo_contable_cliente`); los efectos son el detalle y el vencimiento». (capa: unit)
- R17. **[rev. 16-11]** El orden de magnitud de CLIENTE en `00_global.yaml` debe dejar de decir
  «SIN VERIFICAR» y de valer 21.900.000: pasa al saldo contable de `cuentas_cliente` medido tras el
  build (≈ 16,0 M) con su fuente, y un segundo concepto con los efectos vivos (≈ 10,5 M), cada uno
  con fecha de medición. (capa: unit)
- R18. **[rev. 16-11]** La versión del diccionario debe subir en una unidad sobre la de `main` al
  implementar (v78 el 2026-11-16) con su nota de versión. (capa: unit)
- R19. `azure-apps/datamart_seg_anual.md` debe recoger los tres objetos nuevos de `retenciones`
  y el cambio de criterio de CLIENTE, en el mismo trabajo. (capa: unit, revisión del reviewer)
- R25. **[rev. 16-11, D10, D11]** Los textos que hoy prometen algo a F-104 —la cabecera de
  `config/diccionario/ventas.yaml`, las fichas de `v_factura_cobro` y `cobertura_enlace`, y la
  frontera de `docs/ARCHITECTURE.md`— deben decir lo que F-104 entrega: el mecanismo del AGR
  explicado y su dinero en `retenciones.movimientos` por cuenta, sin atribuirlo a la factura, y
  dónde queda la conciliación por factura (la feature que diga D10). Deben seguir nombrando
  `F-104` (lo exigen `test_f040_diccionario.py` y la R33 de F-040). (capa: unit)
- R26. **[rev. 16-11]** El comentario de `cob` en `config/tables_sigrid.yaml` («la de cob sigue
  saliendo solo de fecrea y esta sin verificar») debe decir el criterio nuevo. Solo el comentario:
  ninguna tabla ni columna de la ingesta cambia. (capa: unit)

## Verificación sobre la base (MANUAL, humano)

- R20. **[rev. 16-11]** Tras `build-retenciones` en Azure: CLIENTE `VIVA` ≈ 10,53 M€ (347 efectos
  el 2026-11-16); CLIENTE con `retide <> 0` en `VIVA` = 2.403.526,74 € ± lo que se mueva; Σ
  `saldo` de `saldo_contable_cliente` = Σ `contabilidad.mayor.importe_saldo` de las mismas cuentas
  al céntimo (16.002.697,94 el 16-11). (capa: integración, MANUAL)
- R21. **[rev. 16-11]** En `v_cuadre_cliente`: la cuenta 4308001150 (TERTIO MILLENNIO) `CUADRA`
  con 12.000,00; 4308001634 (ESPACIO PROMOCIÓN VIII, obra 0686) `CONTABILIDAD_MAYOR` con ≈ 1,11 M
  de diferencia; 4308001550 (ARCHER) `SIN_SALDO_CONTABLE` con 945.000,05; 4338001593 (UNEXUM)
  `SIN_EFECTOS_VIVOS` con 947.835,66 (con D3 = a). (capa: integración, MANUAL)
- R22. `check-unicidad` y `check-relaciones` siguen en verde sobre `retenciones`. (capa:
  integración, MANUAL)

## Fuera de alcance (va en `design.md` §7)

Atribuir el SALDO contable de cliente a obra; **[rev. 16-11]** rellenar `entidad_cif` de CLIENTE
(D9), la conciliación de la retención por FACTURA de cliente (D10) y atribuir a la factura lo
cobrado por un AGR (D11); el vencimiento de la retención de cliente desde el fin de obra; corregir
en Sigrid los efectos sin cancelar, las facturas sin efecto de retención o la `cueretide` de
UNEXUM (eso es de Administración, con la lista de `v_cuadre_cliente`).
