<!-- specs/F-025-ventana-negocio-build/requirements.md -->
# F-025 · Requisitos · Las obras cerradas no se reconstruyen cada noche

> Reemplaza la spec del 2026-08-28 (commit `1f01718`). Mediciones y consultas:
> **`mediciones.md`**; opciones abiertas: **`decisiones.md`**.

**No es una mejora de rendimiento: es la reparación de una avería.** La nocturna
del **2026-09-02 murió** por `replicaTimeout` en el tramo **5 de 60** y dejó
`stg.plan_mensual` **truncada al 21,6 %** (6.436.281 de 29.762.403 filas). Cada
tramo pasó de **1,57 min** —media de 15 noches— a **40,77**: el `Standard_B1ms`
**agotó sus 144 créditos de CPU a las 04:15 UTC** y Azure lo capó al 20 % de un
núcleo. Solo la puerta de F-024 evitó que `mart` construyera encima. Y el
desperdicio que lo causa: la nocturna reconstruye **687 obras**; de las **583**
del universo de seguimiento solo **44** han cerrado un mes en los últimos 12.

**Las dos frases del humano del 2026-09-02**, que cierran el principio de DA-1 y
acotan la feature: *«las obras que estén cerradas no se actualizan»* y *«que no se
reconstruyan, pero que **no se borren**, y que la información esté
**consultable**»*. **Rigor `critico`**: fase RED, cobertura de las líneas cambiadas
y mutación sin supervivientes, salvo exención escrita a cambio de la revisión de
datos ampliada, como en F-052.

## 1 · El criterio de obra congelada

- **R1.** El sistema debe clasificar cada obra del build en **RECONSTRUIR** o
  **CONGELAR** con una función **pura**, sin conexión, alimentada por datos ya
  medidos: última fase cerrada, estado de Sigrid, firma de origen y sello del SQL.
- **R2.** El criterio por defecto debe ser **la actividad**: se congela la obra que
  tuvo fases y ninguna en los últimos `N` meses (`N` configurable, propuesto 12).
  Censo medido: **322 congeladas de 583**.
- **R3.** SI una obra **no tiene ninguna fase** (217 obras, 64 marcadas EN CURSO),
  ENTONCES no puede congelarse por antigüedad: sin fases no hay señal que interpretar
  y su plan vive solo en los ámbitos master.
- **R4.** La marca de Sigrid solo actúa como **veto**, nunca como motivo de
  exclusión: `maestro.obras.estado_id = 15` (EN CURSO) se reconstruye siempre.
  Medido: `estado_id = 25` cubre 462 obras pero **7 cerraron mes en los últimos
  12** y su catálogo no está ingerido.
- **R5.** MIENTRAS la ventana esté desactivada, el comportamiento debe ser **el de
  hoy**: activarla es un interruptor explícito.

## 2 · Qué se acota y qué no

- **R6.** Solo se acota **`build_plan_mensual`** (`sql/stg/08_plan_mensual.sql`):
  **94 de los 110,7 min** de `build_stg`, el **67 %** de la carga.
- **R7.** Los sub-pasos `00`–`07` de `stg` y los cuatro build de negocio se siguen
  ejecutando **enteros**, desde una `stg.plan_mensual` completa: su contenido no
  puede cambiar por esta feature.
- **R8.** El mecanismo de troceado de F-019 **se reutiliza tal cual** —marcador
  `/*F019_FILTRO_OBRAS*/` en las dos ramas, planificador de tramos, puerta de disco
  antes de cada tramo, una transacción por tramo—. Acotar es **darle otro conjunto
  de obras**, no escribir SQL nuevo.
- **R9.** SI el conjunto a reconstruir queda vacío, ENTONCES el sub-paso termina en
  SUCCESS sin ejecutar tramos y **sin tocar la tabla**.

## 3 · No se borra nada, y todo sigue consultable

> Hoy el `TRUNCATE` **está fuera del troceado**: lo lanza `build_stg_step` una vez
> antes de los 60 tramos. Con él, «no reconstruir» significa **borrar**: una nocturna
> acotada e ingenua dejaría 44 obras y ninguna de las otras 539, la **0599** incluida.

- **R10.** El build acotado **no debe ejecutar `TRUNCATE`** sobre `stg.plan_mensual`:
  lo que se borra se **deriva de lo que se va a escribir**, y cada tramo borra sus
  obras y las reinserta en la **misma transacción**. Así es imposible borrar una obra
  que luego no se reescriba.
- **R11.** CUANDO termina un build acotado, toda obra congelada debe conservar el
  **mismo número de filas por (obra, ámbito)** e importes **idénticos al céntimo**.
- **R12.** Una consulta de negocio sobre una obra congelada debe devolver
  **exactamente lo mismo** que antes. Caso obligatorio: la **0599 TANATORIO
  MAJADAHONDA** en `cierre.v_pbi_cierre_resumen` sigue publicando DIRECTOS
  **2.624.793 €** y margen **1,8 %**.
- **R13.** SI un tramo falla, ENTONCES **no** se vacía la tabla: el aborto de F-019
  (`TRUNCATE` + FAILED) destruiría las obras congeladas. El build para, cada obra
  queda con su última versión buena y se registra cuáles faltan. Con esto la nocturna
  del 2026-09-02 habría acabado con 5 obras al día y 682 con el dato de ayer.
- **R14.** El sistema debe registrar **por obra** de qué ejecución viene lo
  construido —`batch_id`, instante, filas, firma y sello—, **consultable por SQL**.
- **R15.** La superficie de consumo **no cambia**: ni una columna, ni una vista, ni un
  `DROP`; quien consulta no debe notar la diferencia.

## 4 · La exclusión tiene que ser correcta, no confiada

- **R16.** El sistema debe calcular por obra una **firma del origen** —agregados de
  `stg.presupuesto` y `stg.fases`, que se rehacen enteras cada noche— y **reconstruir
  toda obra cuya firma haya cambiado**, aunque el criterio la diera por congelada.
- **R17.** El sistema debe calcular un **sello del SQL** (hash de
  `08_plan_mensual.sql` y de los parámetros del build). SI cambia, ENTONCES **todas**
  las obras se reconstruyen esa noche: sin esto, un arreglo como el de F-052 solo
  alcanzaría a las obras vivas.
- **R18.** SI una obra congelada **no tiene ninguna fila** en `stg.plan_mensual`,
  ENTONCES se reconstruye: nunca se congela lo que no está construido.
- **R19.** SI el registro no cubre una obra, ENTONCES esa obra se reconstruye: la
  duda se resuelve siempre **reconstruyendo**.
- **R20.** La firma **no cubre `raw.obrparpre.planif`** —la cadena que explota el
  master— porque leerla entera cuesta lo que se quiere ahorrar. La laguna se declara
  y la cierra la reconstrucción completa periódica (R25).

## 5 · La prueba de equivalencia, con tolerancia cero

- **R21.** *(BLOQUEANTE.)* Sobre el **mismo `raw`**, las **cuatro huellas** de F-052
  —`stg`, `mart`, `dimension`, `cierre`— antes y después deben salir **idénticas**:
  `comparar-huellas` **sin `--obras-esperadas`**, cero diferencias. Cualquiera
  detiene la feature.
- **R22.** Debe añadirse una **quinta huella**: filas y suma de `importe_origen` por
  **obra × ámbito** de `stg.plan_mensual` completa, que demuestra R11 obra a obra.
- **R23.** El recuento total de `stg.plan_mensual` tras el primer build acotado debe
  coincidir con el de la última noche buena (**29.762.403**) salvo por lo reconstruido.
- **R24.** `check-unicidad`, `check-cierres`, `check-cobertura` y `check-declarados`
  deben dar el mismo veredicto que antes.

## 6 · La red de seguridad (sin ella no se cierra)

- **R25.** Debe existir una **reconstrucción completa periódica** que ignore la
  ventana y rehaga las 687 obras, con **cadencia configurada** (propuesta: semanal, en
  fin de semana) y **disparo automático**: no puede depender de que nadie se acuerde.
- **R26.** Debe existir un **guardián de solo lectura** que denuncie, nombrando obra:
  firma distinta de la registrada, obra congelada sin filas, sello de SQL no vigente,
  y reconstrucción completa más vieja que la cadencia.
- **R27.** El guardián corre al final de `run-all`, **avisa y no bloquea** (F-052
  DA-4), escribe una línea con **marcador estable y buscable** y a mano sale con
  código distinto de 0. Un test debe cruzar el marcador del código con el del `.ps1`.
- **R28.** El modo de fallo a impedir es el de F-052: **un dato que envejece y del
  que nadie se entera**. Ninguna obra puede quedar congelada indefinidamente en
  silencio: o la reconstrucción periódica la alcanza, o el guardián la nombra.

## 7 · El efecto medible

- **R29.** *(Aceptación.)* La nocturna acotada debe terminar **sin dejar los créditos
  de CPU a cero**: crédito restante del `B1ms` mayor que cero, métrica de Azure,
  verificación MANUAL.
- **R30.** El sub-paso debe registrar en `_meta.etl_runs` cuántas obras reconstruyó y
  cuántas congeló, y el ahorro debe **medirse antes de implementar** (estimación:
  **73 %** del peso de los ámbitos reales).

## 8 · Documentación y límites

- **R31.** Ficha de diccionario para todo objeto nuevo y actualización de la de
  `stg.plan_mensual`: **no todas sus filas se construyen cada noche**, y `_built_at`
  dice de cuándo es cada obra. Sin ficha o pendiente declarado, `init.sh` no pasa.
- **R32.** `docs/ARCHITECTURE.md` debe explicar la ventana junto al troceado de F-019
  y la coherencia de F-024, con el cambio de invariante de R13; y
  `azure-apps/datamart_seg_anual.md`, el cambio de frescura.
- **R33.** No se acota `build_mart` ni `build_cierre` (13 % del tiempo): su
  reconstrucción íntegra es lo que hace trivial R21. Tampoco `build_presupuesto`,
  que además es **la fuente de la firma** de R16: acotarla dejaría ciega la
  detección de cambios. Si el ahorro no basta, es otra feature.
- **R34.** No se toca la ingesta (F-011 midió que no compensa: `tiemod` no existe en
  24 de las 31 tablas, `obrparpre` incluida), ni la deduplicación de obras, ni el
  árbol de partidas, ni el literal `stg.obras.activa`, que llega a Power BI.
- **R35.** No se cambia el tamaño del servidor: esta feature reduce el trabajo, y si
  el `B1ms` se queda corto lo decide el humano con `albaranes` y `partes` delante.
