<!-- specs/F-095-retenciones-contabilidad-fin-obra/requirements.md -->
# F-095 · Requisitos — retenciones de proveedor desde la contabilidad, por obra y con vencimiento desde el fin de obra

Notacion EARS. Cada R se traduce a >= 1 test `test_f095_rN_...`. Cifras **medidas
en solo lectura el 2026-09-22** (Sigrid por `sigrid-api`, datamart por MCP):
`progress/explore_retenciones_contabilidad_fin_obra.md` y `design.md` §Medidas.
Rigor `critico`. **Precondicion: F-094 `done`** (el criterio «viva de verdad» de
los efectos lo publica F-094 en `retenciones.movimientos.estado`; aqui se lee,
no se reescribe). **[Hn]** = decision del humano del 2026-09-22, ya tomada
(`design.md` §Decisiones del humano).

## Las cuentas y los apuntes

R1. El sistema debe elegir las cuentas de retencion de proveedor por
`raw.prv.cueretide <> 0` (1:1, 2.247 cuentas) y **nunca por prefijo de codigo**:
asi entran solas 4008, 4108, 4180, 4038 (0,90 M€) y 4128, sin lista escrita.

R2. El sistema debe publicar `retenciones.cuentas_proveedor`: una fila por proveedor
con cuenta, con codigo, nombre (`raw.con`) y `familia` (4 digitos, descriptiva).

R3. El sistema debe publicar `retenciones.apuntes_contables` con **una fila por
apunte de `raw.apu`** sobre esas cuentas (49.505 medidos), sin filtrar ninguno,
con `apunte_id` unico, fecha (`apu.fec`), asiento, cuenta, proveedor, concepto
(`apu.res`), `importe_alta` (`hab`), `importe_baja` (`deb`) e
`importe = hab - deb` (positivo = se retiene, negativo = se devuelve o da de baja).

R4. El sistema debe clasificar cada apunte en `clase`: `CIERRE` si el concepto
empieza por «Asiento de cierre»; `APERTURA` si empieza por «Asiento de apertura»
y la misma cuenta tiene cierre en el ejercicio anterior; `SALDO_INICIAL` si es
apertura **sin** cierre previo de esa cuenta; `ALTA` si `importe > 0`; `BAJA` si
`importe <= 0`. `asi.ori` no se usa (vale 0 en todos).

R5. SI se excluyen cierres y aperturas de una suma, ENTONCES el saldo inicial no
se pierde: para cada cuenta, `SUM(importe)` de `ALTA`+`BAJA`+`SALDO_INICIAL`
debe igualar `SUM(hab - deb)` de todos sus apuntes. Medido: excluir todas las
aperturas da 8.117.748,99 € en vez de 8.760.524,49 € (la apertura de 2008,
642.775,50 €, es historia anterior a Sigrid).

R6. El sistema debe marcar `es_prescripcion` (concepto con «PRESCRI») sin excluir el apunte.

## La obra de cada apunte

R7. El sistema debe resolver la obra de cada apunte por esta cascada, y publicar
en `via_obra` cual resolvio: `APUNTE` (`apu.cenide` -> `maestro.centros_coste`);
`FACTURA` (`apu.asiide` -> `rac.conide` = factura -> su efecto de retencion con
centro unico); `EFECTO` (`rac.conide` = efecto -> `pag.cenide`); **[H3]**
`PROVEEDOR_UNA_OBRA` (el proveedor solo tiene efectos de retencion en una obra);
si ninguna, `SIN_OBRA` con `obra_id` NULL.

R8. El sistema no debe multiplicar apuntes: cada salto agrega o usa `LATERAL ...
LIMIT 1`, y `apunte_id` es clave primaria.

R9. **[H4]** El sistema debe ingerir `raw.rac` con `where: asiide <> 0`
(755.086 de 2.505.089 filas, excluida `tex`), acordado con F-091. Sin `rac` las
altas con obra caen del 97,2 % al 10,8 % del importe.

R10. El sistema no debe usar `apu.obr` ni `cen.obride` para atribuir obra.

## Saldo contable por proveedor y obra

R11. El sistema debe publicar `retenciones.saldo_contable` con una fila por
(proveedor, obra), `obra_id` NULL como fila «sin obra» propia, con `altas`,
`bajas`, `saldo_inicial`, `saldo` (= suma de las tres), `saldo_anterior_2016`
(apertura de 2016) y fechas de primer y ultimo movimiento. Cierres y aperturas
no suman nunca aqui.

R12. El diccionario debe declarar que **el saldo vivo a proveedor lo manda la
contabilidad** (`saldo_contable`); `movimientos` es el detalle por efecto.

R13. El importe `SIN_OBRA` debe ir a la fila sin obra, sin repartir, con su cifra en la ficha.

## El cuadre contabilidad - efectos

R14. El sistema debe publicar `retenciones.v_cuadre_proveedor`: por proveedor,
`saldo_contable`, `viva_efectos` (`SUM(importe)` de `retenciones.movimientos`
con `sentido='PROVEEDOR' AND estado='VIVA'`), `diferencia` y
`saldo_anterior_2016`. **No recalcula** el criterio de viva: no lee `fecrea`,
`fecbaj` ni `est`.

R15. El sistema debe clasificar el cuadre en `categoria`: `CUADRA` (|dif| < 1 €),
`SIN_EFECTOS_VIVOS`, `SIN_SALDO_CONTABLE`, `CONTABILIDAD_MAYOR`,
`EFECTOS_MAYOR`, evaluadas en ese orden, y la ficha debe publicar el reparto
medido (design §Medidas, **[H7]**).

R16. CUANDO se construye el cuadre, FERMALUX (1958815) debe salir `CUADRA` 64.201,96 €.

## El fin de obra **[H1]**

R17. El sistema debe publicar `retenciones.fin_obra` con una fila por obra de
`raw.obr`, con `fecha_inicio_garantia` (`MAX` no nulo de `obrctr.fecinigar`; si
no, `obr.garfecini`), `ultimo_cierre` y, solo informativas, `fecha_fin_real`
(regla de `cierre.v_pbi_cierre_cabecera`), `fecha_recepcion_provisional` y
`fecha_fin_prevista`, cada una en su columna, y el estado de la obra (`con.est`).

R18. El sistema debe tomar como `ultimo_cierre` el mayor `anio_mes` de
`cierre.fact_cierre_mensual` de la obra con `ejecutado_mes <> 0` en algun
concepto: el ultimo cierre que movio algo, no la ultima fase creada (124 de 330
obras tienen fases vacias, ~12 meses despues de su ultimo movimiento).

R19. El sistema debe calcular `fecha_fin_obra` = `fecha_inicio_garantia`; si es
NULL, el ultimo dia del mes siguiente a `ultimo_cierre`; y publicar
`fuente_fin_obra` = `INICIO_GARANTIA`, `ULTIMO_CIERRE_MAS_1_MES` o NULL.
Cobertura medida: 20,9 % + 76,1 % = 97,0 % del vivo.

R20. SI una obra no tiene ni inicio de garantia ni `ultimo_cierre`, ENTONCES
`fecha_fin_obra` queda NULL y no se inventa (17 obras con retencion viva,
132.544,84 €, 9 terminadas); `terminada_sin_fin_obra` marca las de `con.est`
en 19, 21, 23, 25.

R21. SI `cierre.fact_cierre_mensual` esta vacia al construir, ENTONCES el sub-paso
`fin_obra` debe fallar con su nombre en vez de publicar todo sin fecha.

R22. **[H2]** El sistema debe publicar `plazo_meses` = `obrctr.plaret`; si no,
`obrctr.plagar`; si no, 12, y `fuente_plazo` = `PLAZO_RETENCION_CLIENTE`,
`PLAZO_GARANTIA_CLIENTE` o `PLAZO_FIJO_12`. El 12 vive en una sola constante.

## El vencimiento

R23. El sistema debe calcular `fecha_vencimiento = fecha_fin_obra +
plazo_meses meses`. **La fecha de la factura no interviene nunca** (decision del
humano del 2026-09-22): ni `fecha_documento`, ni `pag.fecven`, ni `con.fec`.

R24. El sistema debe publicar `retenciones.v_retencion_contable_obra`: por
(proveedor, obra) con saldo distinto de 0, saldo, fin de obra y su fuente,
plazo y su fuente, `fecha_vencimiento` y `estado_vencimiento`: `SIN_OBRA`,
`SIN_FIN_OBRA`, `VENCIDA` (< `CURRENT_DATE`) o `PENDIENTE`.

R25. El sistema no debe tocar `fecha_prevista_devolucion` ni `vencida_sin_liquidar`
de `movimientos`: son el vencimiento de Sigrid (factura + 15 meses) y la ficha lo dice.

## Alcance y propagacion

R26. **[H5]** El sistema no debe construir saldo contable de cliente (4308).

R27. El paso `build_retenciones` debe ejecutar los ficheros nuevos en orden
dentro de `SUB_PASOS`, contando filas de cada tabla nueva, sin cambiar su
`name`, `stage` ni `depends_on`.

R28. `config/diccionario/retenciones.yaml` debe tener ficha de cada objeto nuevo
con grano, `clave_negocio` y `relaciones` (obra -> `maestro.obras`, proveedor ->
`maestro.proveedores`), y `raw.yaml` la de `rac`; `00_global.yaml` sube
`version` y sustituye el orden de magnitud falso de 34,7 M€ por el saldo contable.

R29. `check-declarados`, `-unicidad` y `-relaciones` deben cubrir los objetos
nuevos sin tocar su codigo; `config/objetos_pendientes.yaml` sigue vacio.

R30. Los tests deben correr sin red ni BBDD; cifras, FERMALUX y R5 son MANUAL.

R31. `azure-apps/datamart_seg_anual.md` debe recoger `raw.rac` y los objetos
nuevos en el mismo trabajo.
