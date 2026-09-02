<!-- specs/F-025-ventana-negocio-build/requirements.md -->
# F-025 · Requisitos · Las obras cerradas no se reconstruyen cada noche

> Reemplaza la spec del 2026-08-28 (commit `1f01718`). Mediciones y consultas:
> **`mediciones.md`**; decisiones del humano: **`decisiones.md`**, cerradas el
> **2026-09-02**.

**No es una mejora de rendimiento: es la reparación de una avería.** La nocturna
del **2026-09-02 murió** por `replicaTimeout` en el tramo **5 de 60** y dejó
`stg.plan_mensual` **truncada al 21,6 %** (6.436.281 de 29.762.403 filas). Cada
tramo pasó de **1,57 min** —media de 15 noches— a **40,77**: el `Standard_B1ms`
**agotó sus 144 créditos de CPU a las 04:15 UTC** y Azure lo capó al 20 % de un
núcleo. Solo la puerta de F-024 evitó que `mart` construyera encima. Y se
reconstruyen **todas** las obras cada noche cuando solo **80 de 920** han tenido
actividad en los últimos 12 meses.

**Las dos frases del humano del 2026-09-02**, que cierran el principio de DA-1 y
acotan la feature: *«las obras que estén cerradas no se actualizan»* y *«que no se
reconstruyan, pero que **no se borren**, y que la información esté
**consultable**»*. **Rigor `critico`**: fase RED, cobertura de las líneas cambiadas
y mutación sin supervivientes, salvo exención escrita a cambio de la revisión de
datos ampliada, como en F-052.

## 1 · El criterio de obra congelada

- **R1.** El sistema debe clasificar cada obra en **RECONSTRUIR** o **CONGELAR**
  con una función **pura**, sin conexión, y dejar escrito **el motivo** de cada una.
- **R2.** *(Decisión del humano, 2026-09-02.)* Se congela toda obra que cumpla **al
  menos una** de estas tres, en unión: (1) su estado es **EN ESTUDIO (1), NO
  PRESENTADA (11) o CERRADA (25)**; (2) `codigo_obra ~ '^[0-9]{6}$'`; (3) sin
  actividad en 12 meses. Censo sobre las 920 del maestro: **880 congeladas, 40
  vivas**, de ellas **38** publican en el fact.
- **R3.** *(Contrapartida aceptada por el humano, con el dato delante.)* De las **80
  obras con actividad en 12 meses, 40 quedan congeladas** —39 CERRADAS, 1 de seis
  dígitos— y tendrán **hasta 6 días de antigüedad**. De esas 39, **36 tienen su última
  actividad en 2025-12**, que es el cierre anual, y solo **4** algo posterior (la más
  reciente, 2026-07). El sistema **no debe** rescatarlas por su cuenta: debe
  **nombrarlas** (R26) y esperar al domingo (R25).
- **R4.** El catálogo de estados **está verificado** (2026-09-02): vive en
  `conest`, tipo **42**, y se llega por `con.est`. El sistema debe publicarlo en el
  diccionario para que deje de haber códigos sin nombre.
- **R5.** MIENTRAS la ventana esté desactivada, el comportamiento debe ser **el de
  hoy**: activarla es un interruptor explícito.

## 2 · Qué se acota y qué no

- **R6.** Se acotan **`build_plan_mensual`** (`08_plan_mensual.sql`; 94 de los
  110,7 min de `build_stg`) y, por decisión del humano, **`build_presupuesto`**
  (`06_presupuesto.sql`, 13,8 M filas). Los dos con el mismo mecanismo.
- **R7.** El resto de `stg` (`00`–`05`, `07`) y los cuatro build de negocio se
  siguen ejecutando **enteros**, desde `stg.presupuesto` y `stg.plan_mensual`
  completas: su contenido no puede cambiar por esta feature.
- **R8.** El mecanismo de troceado de F-019 **se reutiliza** —marcador
  `/*F019_FILTRO_OBRAS*/`, planificador de tramos, puerta de disco, una transacción
  por tramo—. En `06_presupuesto.sql` se añade un marcador equivalente; su
  `DISTINCT ON` ya particiona por obra, así que el corte es igual de seguro.
- **R9.** SI el conjunto a reconstruir queda vacío, ENTONCES el sub-paso termina en
  SUCCESS sin ejecutar tramos y **sin tocar la tabla**.

## 3 · No se borra nada, y todo sigue consultable

> El `TRUNCATE` de `plan_mensual` está **fuera del troceado** y el de
> `06_presupuesto.sql`, dentro. Con ellos, «no reconstruir» significa **borrar**: una
> nocturna acotada e ingenua dejaría 40 obras y ninguna de las otras 880.

- **R10.** El build acotado **no debe ejecutar `TRUNCATE`** sobre `stg.plan_mensual`
  ni sobre `stg.presupuesto`: lo que se borra se **deriva de lo que se va a
  escribir**, y cada tramo borra sus obras y las reinserta en la **misma
  transacción**. Así es imposible borrar una obra que luego no se reescriba.
- **R11.** CUANDO termina un build acotado, toda obra congelada conserva el **mismo
  número de filas por (obra, ámbito)** e importes **idénticos al céntimo**.
- **R12.** Una consulta de negocio sobre una obra congelada debe devolver
  **exactamente lo mismo** que antes. Caso obligatorio: la **0599** en
  `cierre.v_pbi_cierre_resumen`, DIRECTOS **2.624.793 €** y margen **1,8 %**.
- **R13.** SI un tramo falla, ENTONCES **no** se vacía la tabla: el aborto de F-019
  (`TRUNCATE` + FAILED) destruiría lo congelado. El build para, cada obra queda con su
  última versión buena y se registra cuáles faltan.
- **R14.** El sistema debe registrar **por obra** de qué ejecución viene lo
  construido —`batch_id`, instante, filas, firma y sello—, **consultable por SQL**.
- **R15.** La superficie de consumo **no cambia**: ni una columna, ni una vista, ni un
  `DROP`; quien consulta no debe notar la diferencia.

## 4 · La exclusión tiene que ser correcta, no confiada

- **R16.** El sistema debe calcular por obra una **firma del origen** sobre **`raw`**
  —lo único que la ingesta sigue trayendo completo— y **denunciar** toda obra
  congelada cuya firma cambie. No la reconstruye —contradiría R3—: la rehace el
  domingo (R25), o el humano a mano.
- **R17.** El sistema debe calcular un **sello del SQL** (hash de
  `08_plan_mensual.sql` y de los parámetros del build). SI cambia, ENTONCES **todas**
  las obras se reconstruyen esa noche: sin esto, un arreglo como el de F-052 solo
  alcanzaría a las obras vivas.
- **R18.** SI una obra congelada no tiene filas en `stg.plan_mensual` o
  `stg.presupuesto`, o el registro no la cubre, ENTONCES se reconstruye: no se congela
  lo que no está construido, y eso es completar, no actualizar.
- **R20.** El **coste** de la firma debe medirse antes de fijarla (T2b): si incluir
  `raw.obrparpre.planif` —texto largo de 13,8 M filas— resulta prohibitivo, la firma
  se queda en los agregados numéricos y la laguna se declara. La cierra R25.

## 5 · La prueba de equivalencia, con tolerancia cero

- **R21.** *(BLOQUEANTE.)* Sobre el **mismo `raw`**, las **cuatro huellas** de F-052
  —`stg`, `mart`, `dimension`, `cierre`— antes y después deben salir **idénticas**:
  `comparar-huellas` **sin `--obras-esperadas`**, cero diferencias.
- **R22.** Debe añadirse una **quinta huella**: filas y suma de `importe_origen` por
  **obra × ámbito** de `stg.plan_mensual` completa, que demuestra R11 obra a obra.
- **R23.** El recuento de `stg.plan_mensual` tras el primer build acotado debe
  coincidir con el de la última noche buena (**29.762.403**) salvo lo reconstruido.
- **R24.** `check-unicidad`, `check-cierres`, `check-cobertura` y `check-declarados`: mismo veredicto que antes.

## 6 · La red de seguridad (sin ella no se cierra)

- **R25.** *(Decisión del humano.)* Debe existir una **reconstrucción completa
  semanal, los DOMINGOS**, que ignore la ventana y rehaga todas las obras, disparada
  desde `run-all` por antigüedad registrada y **no** por un cron nuevo (de ahí el
  «hasta 6 días» de R3).
- **R26.** Debe existir un **guardián de solo lectura** que denuncie, nombrando obra:
  firma distinta de la registrada, congelada sin filas, sello no vigente y
  reconstrucción completa vencida.
- **R27.** El guardián corre al final de `run-all`, **avisa y no bloquea**, escribe
  una línea con **marcador estable y buscable** y a mano sale con código distinto de
  0. Un test debe cruzar el marcador del código con el del `.ps1`.
- **R28.** El modo de fallo a impedir es el de F-052: **un dato que envejece y del
  que nadie se entera**. Ninguna obra queda congelada en silencio: o la reconstrucción
  del domingo la alcanza, o el guardián la nombra.

## 7 · El efecto medible

- **R29.** *(Aceptación.)* La nocturna acotada debe terminar **sin dejar los créditos
  de CPU a cero**: crédito restante mayor que cero, métrica de Azure, MANUAL.
- **R30.** Los sub-pasos acotados deben registrar en `_meta.etl_runs` cuántas obras
  reconstruyeron y cuántas congelaron; el ahorro se **mide antes de implementar** (T2).

## 8 · Documentación y límites

- **R31.** Ficha para todo objeto nuevo y actualización de las de `stg.plan_mensual`
  y `stg.presupuesto` (**no todas sus filas se construyen cada noche**) y de
  `maestro.obras.estado_id`, que hoy dice que su catálogo no se ingiere: los catorce
  estados de `conest` se documentan con su nombre (R4).
- **R32.** `docs/ARCHITECTURE.md` debe explicar la ventana junto al troceado de F-019
  y la coherencia de F-024, con el cambio de invariante de R13; y
  `azure-apps/datamart_seg_anual.md`, el cambio de frescura.
- **R33.** No se acota `build_mart` ni `build_cierre` (13 % del tiempo): su
  reconstrucción íntegra desde un `stg` completo es lo que hace trivial R21. Si el
  ahorro no basta, es otra feature.
- **R34.** No se acota la ingesta —F-011 midió que no compensa y que `tiemod` no
  existe en 24 de las 31 tablas, `obrparpre` incluida—, y por eso `raw` sigue completo
  cada noche, que es lo que hace posible R16. Tampoco se tocan la deduplicación de
  obras, el árbol de partidas, el literal `stg.obras.activa` ni el tamaño del
  servidor, que afecta a `albaranes` y `partes` y lo decide el humano.
