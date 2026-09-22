<!-- specs/F-095-retenciones-contabilidad-fin-obra/requirements.md -->
# F-095 · Requisitos — retenciones de proveedor desde la contabilidad, por obra y con vencimiento desde el fin de obra

Notacion EARS. Cada R se traduce a >= 1 test `test_f095_rN_...`. Cifras **medidas
en solo lectura el 2026-09-22** (Sigrid por `sigrid-api`, datamart por MCP):
`progress/explore_retenciones_contabilidad_fin_obra.md` y `design.md` §Medidas.
Rigor `critico`. **Precondicion: F-094 `done`** (el criterio «viva de verdad» de
los efectos lo publica F-094 en `retenciones.movimientos.estado`; aqui se lee,
no se reescribe). Lo marcado **[Hn]** depende de la decision n del humano
(`design.md` §Decisiones para el humano); el texto lleva la opcion recomendada.

## Las cuentas y los apuntes

R1. El sistema debe elegir las cuentas de retencion de proveedor por
`raw.prv.cueretide <> 0` (1:1, 2.247 cuentas) y **nunca por prefijo de codigo**:
asi entran solas 4008, 4108, 4180, 4038 (0,90 M€) y 4128, sin lista escrita.

R2. El sistema debe publicar `retenciones.cuentas_proveedor` con una fila por
proveedor con cuenta de retencion: proveedor, cuenta, codigo y nombre de la
cuenta (de `raw.con`) y `familia` (4 primeros digitos, solo descriptiva).

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

R6. El sistema debe marcar `es_prescripcion` si el concepto contiene «PRESCRI»
(sin distinguir mayusculas), sin excluir el apunte.

## La obra de cada apunte

R7. El sistema debe resolver la obra de cada apunte por esta cascada, y publicar
en `via_obra` cual resolvio: `APUNTE` (`apu.cenide` -> `maestro.centros_coste`);
`FACTURA` (`apu.asiide` -> `rac.conide` = factura -> su efecto de retencion con
centro unico); `EFECTO` (`rac.conide` = efecto -> `pag.cenide`); **[H3]**
`PROVEEDOR_UNA_OBRA` (el proveedor solo tiene efectos de retencion en una obra);
si ninguna, `SIN_OBRA` con `obra_id` NULL.

R8. El sistema no debe multiplicar apuntes al resolver la obra: cada salto
agrega o usa `LATERAL ... ORDER BY ... LIMIT 1`, y `apunte_id` es clave primaria.

R9. **[H4]** El sistema debe ingerir `raw.rac` con `where: asiide <> 0`
(755.086 de 2.505.089 filas, excluida `tex`). SIN `rac`, ENTONCES las altas
desde 2016 quedan sin obra: con `rac` 97,2 % del importe de altas con obra; sin
ella 10,8 %.

R10. El sistema no debe usar `apu.obr` ni `cen.obride` para atribuir obra.

## Saldo contable por proveedor y obra

R11. El sistema debe publicar `retenciones.saldo_contable` con una fila por
(proveedor, obra), `obra_id` NULL como fila «sin obra» propia, con `altas`,
`bajas`, `saldo_inicial`, `saldo` (= suma de las tres), `saldo_anterior_2016`
(apertura de 2016) y fechas de primer y ultimo movimiento. Cierres y aperturas
no suman nunca aqui.

R12. El diccionario debe declarar que **la fuente que manda para el saldo vivo
de retencion a proveedor es la contabilidad** (`saldo_contable`), y que
`retenciones.movimientos` es el detalle por efecto que la explica.

R13. MIENTRAS haya importe con `via_obra = 'SIN_OBRA'`, el sistema debe
publicarlo en la fila sin obra y no repartirlo, y la ficha debe dar su cifra.

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

R16. CUANDO se construye el cuadre, FERMALUX (1958815, cuenta 4108005478) debe
salir `CUADRA` con 64.201,96 € a los dos lados.

## El fin de obra

R17. El sistema debe publicar `retenciones.fin_obra` con una fila por obra de
`raw.obr` y cada candidata **en su columna y con su nombre**: `fecha_fin_real`
(misma regla que `cierre.v_pbi_cierre_cabecera`: `MAX(obrctr.fecreafin)`, si no
`obr.fecfinrea`), `fecha_recepcion_provisional` (`MAX(obrctr.fecprorec)`),
`fecha_inicio_garantia` (`MAX(obrctr.fecinigar)`, si no `obr.garfecini`),
`fecha_fin_prevista` (`MAX(obrctr.fecprefin)`, si no `obr.fecfinpre`), y el
estado de la obra (`con.est`).

R18. **[H1]** El sistema debe calcular `fecha_fin_obra` = primera no nula de
`fecha_fin_real`, `fecha_recepcion_provisional`; y publicar `fuente_fin_obra`
(`FIN_REAL`, `RECEPCION_PROVISIONAL` o NULL). La fin prevista **no** entra en
`fecha_fin_obra`.

R19. SI la obra esta terminada (`con.est` en 19, 21, 23, 25) y no tiene
`fecha_fin_obra`, ENTONCES `terminada_sin_fin_obra = TRUE` y `fecha_fin_obra`
queda NULL: la fecha no se inventa (83 obras con retencion viva, 2,09 M€).

R20. **[H2]** El sistema debe publicar `plazo_meses` y `fuente_plazo` con la regla
que apruebe el humano; recomendada: `obrctr.plaret`, si no `obrctr.plagar`, si no
un plazo fijo de Negocio en una sola constante del SQL (`PLAZO_NEGOCIO`).

## El vencimiento

R21. El sistema debe calcular `fecha_vencimiento = fecha_fin_obra +
plazo_meses meses`. **La fecha de la factura no interviene nunca** (decision del
humano del 2026-09-22): ni `fecha_documento`, ni `pag.fecven`, ni `con.fec`.

R22. El sistema debe publicar `retenciones.v_retencion_contable_obra`: por
(proveedor, obra) con saldo distinto de 0, saldo, fechas de fin de obra, plazo,
`fecha_vencimiento` y `estado_vencimiento`: `SIN_OBRA`, `SIN_FIN_OBRA`,
`SIN_PLAZO`, `VENCIDA` (vencimiento < `CURRENT_DATE`) o `PENDIENTE`.

R23. El sistema no debe tocar `fecha_prevista_devolucion` ni
`vencida_sin_liquidar` de `retenciones.movimientos`: son el vencimiento de
Sigrid (factura + 15 meses en el 97,8 %) y la ficha lo dice.

## Alcance y propagacion

R24. **[H5]** El sistema no debe construir saldo contable de cliente (4308).

R25. El paso `build_retenciones` debe ejecutar los ficheros nuevos en orden
dentro de `SUB_PASOS`, contando filas de cada tabla nueva, sin cambiar su
`name`, `stage` ni `depends_on`.

R26. `config/diccionario/retenciones.yaml` debe tener ficha de cada objeto nuevo
con grano, `clave_negocio` y `relaciones` (obra -> `maestro.obras`, proveedor ->
`maestro.proveedores`), y `raw.yaml` la de `rac`; `00_global.yaml` sube
`version` y sustituye el orden de magnitud falso de 34,7 M€ por el saldo contable.

R27. `check-declarados`, `-unicidad` y `-relaciones` deben cubrir los objetos
nuevos sin tocar su codigo; `config/objetos_pendientes.yaml` sigue vacio.

R28. Los tests deben correr sin red ni BBDD; cifras, FERMALUX y R5 son MANUAL.

R29. `azure-apps/datamart_seg_anual.md` debe recoger `raw.rac` y los objetos
nuevos en el mismo trabajo.
