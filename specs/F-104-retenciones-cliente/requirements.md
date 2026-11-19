# F-104 · La retención de CLIENTE saneada — requisitos (EARS)

Rigor `estandar`, prioridad 1. Mediciones: `progress/spec_F-104.md` (solo lectura, 2026-11-06 y
**revalidación 2026-11-16**, §7-§12). Antecedentes: F-094 (estado de PROVEEDOR), F-095 (la
contabilidad manda), F-150 (la retención de 0686), F-040 (`raw.cli`, `ventas`).
**[rev. 16-11]** marca lo que cambia frente a la versión aprobada el 2026-11-07 (design §9).

## Contexto en cuatro líneas

Los 1.956 efectos «vivos» con baja (19,93 M) **están agrupados**: en `cob` el original queda en
`est 1` con `fecbaj` = fecha del AGR, y el AGR y sus DIV llevan `retide = 0`. La retención viva
está en las cuentas de retención de cliente: 16,00 M en la contabilidad y 10,53 M en sus efectos.
**[rev. 16-11, D10 b]** La diferencia se explica factura a factura: la retención que la factura
manda a la cuenta frente a los efectos que la cobran (mediciones §12).

## A · Estado del efecto de cliente (`retenciones`)

- R1. El sistema debe derivar `estado` de las filas CLIENTE de `retenciones.movimientos` de la
  ficha `raw.con` del propio efecto con la precedencia de F-094: `BAJA` si `con.fecbaj <> 0` o
  `con.est IN (14, 15)`; si no, `LIQUIDADA` si `cob.fecrea <> 0` o `con.est = 10`; si no, `VIVA`.
  (capa: unit)
- R2. El sistema debe marcar `vencida_sin_liquidar` en CLIENTE solo para filas en `VIVA` según R1
  con vencimiento anterior a la fecha del build. (capa: unit)
- R3. La cabecera de `01_movimientos.sql` debe explicar el mecanismo (original en `est 1` con
  `fecbaj` = fecha del AGR) con el caso medido: cuenta 4308001150, AGR20/0010 = 57.973,72 €. (capa: unit)

## B · El dinero agrupado y las cuentas (`retenciones`)

- R4. **[rev. 16-11, D3 a]** El sistema debe publicar `retenciones.cuentas_cliente`: la UNIÓN de
  las cuentas de `raw.cli.cueretide` y las de `raw.con` `tip = 17` con código `^43[0-9]8` (225 el
  16-11), con `cuenta_id` (PK), `cliente_id` (NULL si no la declara nadie), `codigo_cuenta`,
  `nombre_cuenta`, `familia` y `criterio_seleccion` (`CUERETIDE` o `PREFIJO_43X8`). (capa: unit)
- R5. **[rev. 16-11]** SI `cuentas_cliente` queda vacía o dos clientes declaran la misma cuenta,
  ENTONCES el sub-paso `movimientos` debe fallar nombrando la tabla, antes de construir
  `movimientos`. (capa: unit)
- R6. La rama CLIENTE debe incluir los efectos de `raw.cob` con `retide <> 0` **y** los de
  `retide = 0` cuya `cueide` esté en `cuentas_cliente` (AGR, DIV, sin tipo). (capa: unit)
- R7. `movimientos` debe publicar `origen_retencion`: `EFECTO_RETENCION` (`retide <> 0`) o
  `CUENTA_RETENCION` (solo por R6); en PROVEEDOR, siempre `EFECTO_RETENCION`. (capa: unit)
- R8. `movimientos` debe publicar `cuenta_id` (`cueide`, NULL si 0) en los dos sentidos. (capa: unit)
- R9. El sistema no debe borrar filas: CLIENTE con `retide <> 0` y todo PROVEEDOR iguales en
  número e importe antes y después. (capa: integración, MANUAL)
- R10. La PK `(sentido, movimiento_id)` de `movimientos` debe seguir siendo única. (capa: unit)

## C · La contabilidad manda: saldo y cuadre por cuenta (`retenciones`)

- R11. El sistema debe publicar `retenciones.saldo_contable_cliente`, una fila por cuenta de
  `cuentas_cliente` con apuntes (`altas`, `bajas`, `saldo_inicial`, `saldo`, `saldo_anterior_2016`,
  `num_apuntes`, `primer_movimiento`, `ultimo_movimiento`), de `raw.apu` con `importe = deb - hab`
  y la MISMA clasificación que `03_apuntes_contables.sql`; `saldo` = ALTA + BAJA + SALDO_INICIAL.
  (capa: unit)
- R12. El sistema debe publicar `retenciones.v_cuadre_cliente`, una fila por cuenta con saldo o
  efectos vivos ≥ 1 €: `saldo_contable`, `viva_efectos`, `num_efectos_vivos`, `diferencia` y
  `categoria` en el orden de `v_cuadre_proveedor` (`CUADRA`, `SIN_EFECTOS_VIVOS`,
  `SIN_SALDO_CONTABLE`, `CONTABILIDAD_MAYOR`, `EFECTOS_MAYOR`). (capa: unit)
- R13. `v_cuadre_cliente` debe LEER el estado de `movimientos`, sin recalcularlo. (capa: unit)

## D · La conciliación por FACTURA (`ventas`) [rev. 16-11, D10 b]

- R27. El sistema debe publicar la tabla `ventas.retencion_factura`, una fila por factura de
  `ventas.facturas` con retención (D12), garantía o RETESP distintas de 0, o con efectos de
  retención: factura, cliente, obra, `cuenta_id`, `retencion` (D12), `retencion_garantia` y
  `retencion_retesp`, `efectos` y `num_efectos`, `efectos_viva`, `efectos_liquidada`,
  `efectos_agrupada`, `diferencia` (retención − efectos) y `motivo`. (capa: unit)
- R28. `motivo` debe valer, en este orden: `SIN_EFECTO` (retención ≠ 0, ningún efecto),
  `EFECTO_SIN_RETENCION` (efectos, retención 0), `CUADRA` (|diferencia| < 0,01), `DIFIERE` (el
  resto con efectos) y `SIN_CUENTA_RETENCION` (ni retención ni efectos: solo garantía o RETESP que
  no van a una cuenta de retención). (capa: unit)
- R29. Los efectos de una factura deben salir de `retenciones.movimientos` CLIENTE con
  `documento_id` = factura (los dos orígenes), y su reparto, de su `estado` sin recalcularlo. Lo
  `BAJA` va a `efectos_agrupada`: su dinero cuenta en un AGR/DIV que NO se atribuye a la factura
  (D11). (capa: unit)
- R30. La garantía y el RETESP deben leerse de `ventas.facturas` (`ventas.fn_clase_recargo`, único
  punto de decisión, D4 de F-040), sin copiar la función ni nombrar las clases. (capa: unit)
- R31. El sistema debe publicar la tabla `ventas.retencion_cuenta`, una fila por cuenta de
  `retenciones.v_cuadre_cliente` o de `retencion_factura`, con sus columnas copiadas y `cliente_id`
  (de `cuentas_cliente`), `retencion_facturas`, `retencion_sin_efecto`, `num_facturas_sin_efecto`,
  `viva_sin_factura` (efectos `VIVA` de la cuenta sin `documento_id`: AGR, DIV, manuales) y
  `diferencia_sin_explicar` = `diferencia` − (`retencion_sin_efecto` − `viva_sin_factura`), NULL
  en `CUADRA`. La cuenta de una factura es la de su recargo; sin recargo, la de su efecto. (capa: unit)
- R32. El sistema debe publicar la vista `ventas.v_retencion_cliente`, una fila por cliente con
  facturas en `retencion_factura` o cuenta en `retencion_cuenta`: importes por `motivo` y la suma
  de las columnas de `retencion_cuenta` de sus cuentas. Lee solo esas dos tablas. (capa: unit)
- R33. SI no existen `retenciones.v_cuadre_cliente` o la columna `origen_retencion` de
  `movimientos`, ENTONCES el sub-paso `retencion_cliente` debe fallar nombrándolas antes de
  borrar nada. (capa: unit)
- R34. `retencion_factura` y `retencion_cuenta` deben ser TABLAS (un `DROP ... CASCADE` de
  `retenciones` no las borra), construidas por el sub-paso `retencion_cliente`
  (`06b_retencion_cliente.sql`) ANTES de `guardas`, sin cambiar el `depends_on` de `build_ventas`.
  (capa: unit)
- R35. Las tres no deben tener columnas personales: ni CIF ni nombres de columna con un prefijo
  de `PREFIJOS_PROHIBIDOS_EN_VENTAS` (la guarda de `07_guardas.sql` las ve); los permisos, los
  de `ventas` por defecto, sin tocar `infra/sql/02_roles.sql`. (capa: unit; MANUAL los permisos)

## E · Lo que no cambia

- R14. **[rev. 16-11]** No deben cambiar `tesoreria/`, `retenciones/00_setup.sql`, la rama
  PROVEEDOR salvo R7 y R8, ni `retenciones/02`-`07`; en `ventas/`, solo `06b` es nuevo. (capa: unit)
- R15. Las `v_pbi_*` de `02_views.sql` deben seguir leyendo `estado = 'VIVA'` sin cambios. (capa: unit)
- R23. **[rev. 16-11, D9 a]** `entidad_cif` de CLIENTE sigue NULL (sin leer `cli.cif`); su ficha
  manda a `ventas.clientes` por `entidad_id` = `cliente_id`. (capa: unit)
- R24. **[rev. 16-11]** `TOCADOS_DESPUES` de `tests/test_f040_frontera.py` debe admitir, con su
  motivo, `retenciones/01_movimientos.sql` y `retenciones/08_saldo_cliente.sql`, y nada más. (capa: unit)

## F · Diccionario y documentación

- R16. `retenciones.yaml`: fichas del estado de CLIENTE (con el AGR), `origen_retencion`,
  `cuenta_id`, `entidad_cif` y los tres objetos nuevos de `retenciones`, con «la retención viva de
  cliente la manda la contabilidad; los efectos son el detalle y el vencimiento». (capa: unit)
- R36. **[rev. 16-11]** `ventas.yaml`: fichas de los tres objetos de D, con la regla «la
  retención de la factura no es la garantía de `ventas.facturas`» (D12). (capa: unit)
- R17. `00_global.yaml`: el orden de magnitud de CLIENTE deja «SIN VERIFICAR» y 21.900.000; pasa
  al saldo contable (≈ 16,0 M) y a los efectos vivos (≈ 10,5 M), con fuente y fecha. (capa: unit)
- R18. La `version` del diccionario sube una unidad sobre la de `main` al implementar (v78 el
  16-11), con su nota. (capa: unit)
- R19. `azure-apps/datamart_seg_anual.md` recoge los seis objetos nuevos y el cambio de criterio
  de CLIENTE, en el mismo trabajo. (capa: unit, revisión del reviewer)
- R25. **[rev. 16-11, D10 b, D11 a]** Lo que hoy se promete a F-104 se CUMPLE y se dice así en la
  cabecera de `ventas.yaml`, las fichas de `v_factura_cobro` y `cobertura_enlace` y la frontera de
  `docs/ARCHITECTURE.md`: la conciliación por factura vive en `ventas.retencion_factura`; lo
  cobrado por un AGR se explica y no se atribuye. Siguen nombrando `F-104` (lo exigen los tests de
  F-040). (capa: unit)
- R26. El comentario de `cob` en `config/tables_sigrid.yaml` dice el criterio nuevo (solo el
  comentario). (capa: unit)

## G · Verificación sobre la base (MANUAL, humano)

- R20. Tras `build-retenciones`: CLIENTE `VIVA` ≈ 10,53 M€ (347 efectos el 16-11), de ellos con
  `retide` 2.403.526,74 ± lo que se mueva; Σ `saldo` de `saldo_contable_cliente` = Σ
  `contabilidad.mayor.importe_saldo` de esas cuentas al céntimo (16.002.697,94). (capa: integración, MANUAL)
- R21. `v_cuadre_cliente`: 4308001150 `CUADRA` 12.000,00; 4308001634 (0686) `CONTABILIDAD_MAYOR`
  ≈ 1,11 M; 4308001550 (ARCHER) `SIN_SALDO_CONTABLE` 945.000,05; 4338001593 (UNEXUM)
  `SIN_EFECTOS_VIVOS` 947.835,66. (capa: integración, MANUAL)
- R37. **[rev. 16-11]** Tras `build-ventas` (con D12 = a): `motivo` ≈ 2.696 CUADRA, 1.114
  SIN_EFECTO (17,78 M), 56 DIFIERE, 284 EFECTO_SIN_RETENCION, 27 SIN_CUENTA_RETENCION; en
  4308001634, `retencion_sin_efecto` 1.735.233,86, `viva_sin_factura` 622.160,33 y
  `diferencia_sin_explicar` 0. (capa: integración, MANUAL)
- R22. `check-unicidad` y `check-relaciones` siguen en verde sobre `retenciones` y `ventas`.
  (capa: integración, MANUAL)

## Fuera de alcance

Atribuir el saldo contable a obra (D5); rellenar `entidad_cif` (D9); atribuir a la factura lo
cobrado por un AGR (D11); decidir si el RETESP de venta es garantía (D4 de F-040, Juan Romero);
el vencimiento desde el fin de obra; corregir en Sigrid efectos sin cancelar, facturas sin efecto
o la `cueretide` de UNEXUM (Administración, con `ventas.retencion_cuenta`).
