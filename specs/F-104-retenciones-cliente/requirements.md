# F-104 · La retención de CLIENTE saneada — requisitos (EARS)

Rigor `estandar`, prioridad 3. Mediciones: `progress/spec_F-104.md` (solo lectura, 2026-11-06).
Antecedentes: F-094 (estado de PROVEEDOR), F-095 (la contabilidad manda; H5 deja fuera el
cliente), F-150 (la retención de 1,68 M€ de 0686, §3 de las mediciones).

## Contexto en cuatro líneas

Los 1.956 efectos «vivos» con baja (19,93 M) **están agrupados**: en `cob` el original queda en
`est 1` con `fecbaj` = fecha del agrupador AGR (en `pag` iría a `est 14`), y el AGR y sus DIV
llevan `retide = 0`, así que `movimientos` no los ve. 1.734 (90,4 %) casan con un AGR de la misma
cuenta ese día. La retención viva de verdad está en las cuentas 43x8: 15,49 M en la contabilidad
y 10,50 M en los efectos vivos de esas cuentas; la diferencia, casos concretos (§3-§4).

## Estado del efecto de cliente

- R1. El sistema debe derivar `estado` de las filas CLIENTE de `retenciones.movimientos` de la
  ficha `raw.con` del propio efecto con la precedencia de F-094: `BAJA` si `con.fecbaj <> 0` o
  `con.est IN (14, 15)`; si no, `LIQUIDADA` si `cob.fecrea <> 0` o `con.est = 10`; si no, `VIVA`.
- R2. El sistema debe marcar `vencida_sin_liquidar` en CLIENTE solo para filas que cumplan la
  condición de `VIVA` de R1 y tengan vencimiento anterior a la fecha del build.
- R3. La cabecera de `01_movimientos.sql` debe explicar por qué el criterio vale en cliente aunque
  `cob` no use `est 14`: el original agrupado queda en `est 1` con `fecbaj` = fecha del AGR, con
  el caso medido (cuenta 4308001150: AGR20/0010 = 57.973,72 € = sus cinco originales).

## El dinero agrupado: efectos de las cuentas de retención

- R4. El sistema debe publicar en `retenciones.cuentas_cliente` una fila por cuenta de retención
  de cliente: las cuentas imputables de `raw.con` (`tip = 17`) con código `^43[0-9]8` (220 el
  2026-11-06, 165 con apuntes), con `cuenta_id` (clave primaria),
  `codigo_cuenta`, `nombre_cuenta`, `familia` (4 dígitos) y `criterio_seleccion` = `PREFIJO_43X8`.
- R5. SI `retenciones.cuentas_cliente` queda vacía, ENTONCES el build debe fallar con un mensaje
  que la nombre, antes de construir `movimientos`.
- R6. El sistema debe incluir en la rama CLIENTE de `movimientos` los efectos de `raw.cob` con
  `retide <> 0` (como hoy) **y** los de `retide = 0` cuya `cueide` esté en `cuentas_cliente` (los
  agrupadores AGR, sus DIV y los efectos de retención sin tipo).
- R7. El sistema debe publicar en `movimientos` la columna `origen_retencion`: `EFECTO_RETENCION`
  si el efecto lleva `retide <> 0`, `CUENTA_RETENCION` si entra solo por R6; en PROVEEDOR,
  siempre `EFECTO_RETENCION`.
- R8. El sistema debe publicar en `movimientos` la columna `cuenta_id` (`cueide` del efecto, NULL
  si 0) en los dos sentidos.
- R9. El sistema no debe borrar ninguna fila: las filas CLIENTE con `retide <> 0` y todas las de
  PROVEEDOR deben seguir siendo las mismas, en número e importe, antes y después.
- R10. La clave primaria `(sentido, movimiento_id)` de `movimientos` debe seguir siendo única.

## La contabilidad manda: saldo y cuadre por cuenta

- R11. El sistema debe publicar `retenciones.saldo_contable_cliente`, una fila por cuenta de
  `cuentas_cliente` con apuntes, con `altas`, `bajas`, `saldo_inicial`, `saldo`,
  `saldo_anterior_2016`, `num_apuntes`, `primer_movimiento` y `ultimo_movimiento`, leídos de
  `raw.apu` con `importe = deb - hab` (positivo: retención que nos practican) y la MISMA
  clasificación de apuntes que `03_apuntes_contables.sql` (CIERRE, SALDO_INICIAL, APERTURA, ALTA,
  BAJA); `saldo` = ALTA + BAJA + SALDO_INICIAL: cierres y aperturas no suman nunca.
- R12. El sistema debe publicar la vista `retenciones.v_cuadre_cliente`, una fila por cuenta con
  saldo o efectos vivos de al menos 1 €, con `saldo_contable`, `viva_efectos` (suma de
  `movimientos` CLIENTE en `VIVA` de esa `cuenta_id`), `diferencia` y `categoria` en el orden de
  `v_cuadre_proveedor`: `CUADRA` (< 1 €), `SIN_EFECTOS_VIVOS`, `SIN_SALDO_CONTABLE`,
  `CONTABILIDAD_MAYOR`, `EFECTOS_MAYOR`, y el nombre de la cuenta.
- R13. `v_cuadre_cliente` debe LEER el estado de `movimientos`, no recalcularlo de columnas de
  Sigrid (igual que `v_cuadre_proveedor`).

## Lo que no cambia

- R14. El sistema no debe cambiar `tesoreria` (ya aplica la precedencia en los dos sentidos), ni
  la rama PROVEEDOR de `movimientos` salvo las columnas de R7 y R8, ni `03`-`07`.
- R15. Las vistas `v_pbi_*` de `02_views.sql` deben seguir leyendo `estado = 'VIVA'` sin cambios
  de texto: el saneamiento les llega por `movimientos`.

## Diccionario y documentación

- R16. Las fichas de `config/diccionario/retenciones.yaml` deben describir el estado de CLIENTE
  (R1, con el mecanismo del AGR), `origen_retencion`, `cuenta_id`, y las tres tablas o vistas
  nuevas, con la regla «la retención viva de cliente la manda la contabilidad (`saldo_contable_
  cliente`); los efectos son el detalle y el vencimiento».
- R17. El orden de magnitud de CLIENTE en `00_global.yaml` debe dejar de decir «SIN VERIFICAR» y
  de valer 21.900.000: pasa al saldo contable 43x8 medido tras el build (≈ 15,5 M) con su fuente,
  y un segundo concepto con los efectos vivos (≈ 10,5 M), cada uno con fecha de medición.
- R18. La versión del diccionario debe subir en una unidad sobre la de `main` al implementar
  (hoy v72) con su nota de versión.
- R19. `azure-apps/datamart_seg_anual.md` debe recoger los tres objetos nuevos de `retenciones`
  y el cambio de criterio de CLIENTE, en el mismo trabajo.

## Verificación sobre la base (MANUAL, humano)

- R20. Tras `build-retenciones` en Azure: CLIENTE `VIVA` ≈ 10,50 M€ (345 efectos el 2026-11-06);
  CLIENTE con `retide <> 0` en `VIVA` = 2.371.937,54 € ± lo que se mueva; Σ `saldo` de
  `saldo_contable_cliente` = Σ `contabilidad.mayor.importe_saldo` de las mismas cuentas al céntimo.
- R21. En `v_cuadre_cliente`: la cuenta 4308001150 (TERTIO MILLENNIO) `CUADRA` con 12.000,00;
  4308001634 (ESPACIO PROMOCIÓN VIII, obra 0686) `CONTABILIDAD_MAYOR` con ≈ 1,06 M de diferencia;
  4308001550 (ARCHER) `SIN_SALDO_CONTABLE` con 945.000,05.
- R22. `check-unicidad` y `check-relaciones` siguen en verde sobre `retenciones`.

## Fuera de alcance (va en `design.md` §7)

Atribuir el SALDO contable de cliente a obra; el CIF y la ficha del cliente; el vencimiento de la
retención de cliente desde el fin de obra; corregir en Sigrid los efectos sin cancelar o las
facturas sin efecto de retención (eso es de Administración, con la lista de `v_cuadre_cliente`).
