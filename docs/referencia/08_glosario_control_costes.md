<!-- docs/referencia/08_glosario_control_costes.md -->
# Glosario de control de costes de obra (términos 1 a 12 de Control de Costes)

> Origen: correos de Juan Romero (Dir. Admón y Control de Costes) a Pablo Gris, «RV: expresiones ruemsa», del 2026-11-16 y del 2026-11-17 · Fecha del documento: 2026-11-17
> Incorporado a `docs/referencia/` el 2026-11-20.
> Llegó por correo (HTML), no en PDF ni ofimática: se transcribe literal y solo se cambia el formato. **Versión redactada**: sin pie legal, teléfonos ni direcciones.

Es la respuesta de Control de Costes a la lista de términos que se pidió a Negocio el 2026-10-21 («expresiones ruemsa», a Juan Romero y Elena Díaz). Junto con `07_glosario_incurrido.md` (el término 13, «incurrido», y el derivado «almacén») es **la fuente de F-054** (`_meta.glosario`). Antes de publicar cada entrada, el spec-author de F-054 contrasta sus trampas con lo que calcula el datamart.

Qué versión manda de cada término:

- 1 (ABC), 2 (Planificación inicial) y 4 (Cierre mensual): los del correo del 2026-11-16.
- 3 (Master y versión vigente): la versión EDITADA del 2026-11-17, que añade que el master v1 es la referencia de los indirectos **y de los proporcionales**. Este término es el origen de F-165.
- 5 a 12: nuevos en el correo del 2026-11-17. El 10 pasa a llamarse «Costes proporcionales y "generales"» y el 11 queda solo como «Costes indirectos».

## 1. ABC

**Qué es.** La revisión del presupuesto de coste que hace el jefe de obra al arrancar la obra, partida a partida. Se guarda en Sigrid en una versión de Master y, desde ese momento, pasa a ser la versión de referencia de cara a los comparativos y la versión vigente del master hasta la primera cuatrimestral. Es la estimación de costes inicial del jefe de obra.

**Sinónimos.** Estudio Jefe de obra, planificación ABC.

**Cuándo y cómo.** Al inicio de la obra, una vez transcurridos 45 días desde que el presupuesto está subido a Sigrid o desde que se incorpora el jefe de obra, cuando el jefe de obra ya conoce el proyecto y los primeros precios. Se estudian las partidas de mayor peso, hasta sumar el 90 % del importe del presupuesto, incluyendo las instalaciones como partida alzada. El primer ABC es también la base contra la que se calcula el objetivo revisado de los comparativos. En este ABC se realiza también una primera planificación temporal valorada.

**Trampas.**
- El nombre viene de clasificar las partidas por su peso en el presupuesto (análisis ABC o de Pareto): se reestudian a fondo las que suman el 90 % del importe, unas 60 en una obra típica.
- El ABC es planificación, no cierre: no dice lo ejecutado.
- Los indirectos también se replanifican, pero el jefe de obra no puede cambiar los precios unitarios del equipo de obra: los fija control de costes. Es el precio unitario que tienen asociado los recursos de mano de obra (MO) que intervienen en la obra.
- Los ajustes de mediciones y precios se justifican y se consensúan con el jefe de grupo. A partir del ABC, dirección marca objetivos nuevos. Los nuevos objetivos de compras no son lineales, sino que se calculan por unidades de compra u oficios.

## 2. Planificación inicial

**Qué es.** La primera planificación valorada en el tiempo de una obra nueva, hecha a partir del planning contractual, si existe, mientras el jefe de obra prepara el ABC: el coste fase 0 repartido por meses, que después se copia a venta, y sobre esa venta se calculan los proporcionales. Es una valorada teórica, basada en el contrato, que hace el departamento de control de costes para las previsiones de tesorería, la planificación de resultados, etc. Se guarda como versión del master.

**Sinónimos.** «Planif Inicial» (tipo de versión en Sigrid), plan inicial, planificación valorada inicial, valorada inicial, planificación valorada contractual.

**Cuándo y cómo.** Al arrancar la obra, desde la vista «Planificación en el tiempo» del ámbito Coste fase 0, fijando la fecha inicial y el número de periodos. La realiza el departamento de control de costes. Después, la planificación valorada se rehace en cada cuatrimestral (febrero, junio y octubre), consolidando lo ya ejecutado; esas versiones ya no son la inicial.

**Trampas.**
- No es la referencia de comparación de la obra: hasta el ABC siempre se compara contra el master de Oficina técnica o Estudios (son lo mismo), exista o no planificación inicial.
- No siempre existe una planificación inicial. A discreción del departamento de control de costes.
- Tampoco se debe entender como planificación de compras, es solo una planificación valorada en el tiempo.

## 3. Master y versión vigente del master

**Qué es.** El master es el histórico de fotos del presupuesto de coste y venta fase 0 de la obra en un momento del tiempo. Cada foto es una versión numerada (ámbitos 8 de coste y 11 de venta en Sigrid). La versión vigente es la que rige como plan en un mes dado: la última de tipo ABC o Cuatrimestral con fecha anterior a ese mes. Mientras no hay ABC, la referencia para el coste directo es el master de Oficina técnica o Estudios (master 0); para los indirectos, a diferencia del coste directo, el master de referencia inicial es el master v1.

**Sinónimos.** Versiones master. Vigente: plan vigente, master vigente, versión en vigor. El master 0 es el de Oficina técnica o Estudios.

**Cuándo y cómo.** Cada master es una foto del coste o la venta fase 0. Se guarda una al terminar cada cierre mensual (cuando control de costes entrega el resumen de magnitudes), otra con el ABC y otra en cada planificación cuatrimestral; también la planificación inicial, cuando se hace. En la ventana de mantenimiento de fases se anota a qué corresponde cada versión, por ejemplo «cierre octubre-22» o «planificación valorada junio-22».

**Trampas.**
- La versión que vale depende de la pregunta. Para ver cómo ha cambiado el previsto en el mes, fase 0 frente a la versión N-1 (el cierre anterior). Para el planificado frente al real, la versión vigente en ese mes (ABC o cuatrimestral), no la última, que ya incorpora lo real de los meses pasados.
- Las versiones de tipo «Cierre mensual» no sustituyen al plan vigente.
- La planificación inicial, cuando existe, se guarda como versión del master pero no es versión vigente: es una valorada teórica para previsiones de tesorería y de resultados. Antes del ABC, la referencia es el master 0 para el coste directo y el master v1 para los indirectos.
- La versión vigente cambia cuando se guarda el ABC y con cada nueva cuatrimestral.
- El master 0 (Oficina técnica o Estudios) es inamovible.
- El master de referencia inicial no es el mismo para todo el coste: master 0 para el coste directo y master v1 para los indirectos y proporcionales.
- En el master, «fase» es el número de versión (v0, v1…), no un mes.
- En los master, la planificación de compras del jefe de obra se guarda en la pestaña «Descomposición»; en fase 0 esa pestaña es la de Estudios y la del jefe de obra es «Planificación compras».

## 4. Cierre mensual

**Qué es.** El proceso de fin de mes que fija lo ejecutado hasta la fecha (venta y coste reales a origen) y la previsión de cómo acabará la obra. Conceptos:

- Venta: producción real ejecutada hasta la fecha.
- Gasto total: suma de costes directos, costes indirectos y costes proporcionales.
- Beneficio: resultado de restar el gasto total a la venta.
**Sinónimos.** Cierre, cierre económico, cierre de mes, fase de cierre.

**Cuándo y cómo.** Cada mes y por obra, en este orden: crear la fase del mes (del día 1 al último del mes); imputar a su partida todo el coste incurrido (albaranes, proformas, facturas, partes de trabajo y previsiones, así como determinados costes que entran directamente desde contabilidad como asiento contable), que es tarea de los administrativos de obra; meter las mediciones de coste y de venta, que hace el jefe de obra; y calcular los proporcionales y analizar las desviaciones con los informes de cierre (análisis de coste, detalle por partidas, fase 0 frente a master y planificado frente a real), que hace control de costes. Control de costes prepara el resumen de magnitudes y en ese momento se guarda el master del mes. Cada cifra viene en pareja: la del mes y la acumulada a origen.

**Trampas.**
- La factura prevalece sobre el albarán. Un albarán ya facturado solo se tiene en cuenta si su factura es del mes siguiente.
- La medición a origen de una partida no puede superar la de fase 0: si la supera, primero se corrige fase 0.
- El informe de análisis de coste marca desviación si el avance de venta y el de gasto difieren más de un 5 %, o si el precio incurrido se aleja más de un 5 % del precio previsto en fase 0.
- Una versión master de cierre mensual no es plan: no sustituye a la vigente.
- La venta es la producción real y puede no coincidir con la certificación, que es lo que se factura a la propiedad. La venta del cierre es sin coeficientes; la certificación los lleva.
- Los albaranes con referencia PREV son previsiones que se van anulando hasta el fin de obra: no son albaranes pendientes de facturar. Los IMPUT o IMPU son reimputaciones y no cuentan en el análisis de albaranes.
- El coste de Sigrid no cuadra directamente con la hoja de cierre: la hoja añade el almacén (incurrido sin partida asignada) y los amortizables, que van en indirectos.
- Hay obras o fases llevadas con coste incurrido puro, sin mediciones ni precios en las partidas: su valorado sale a cero y no es un error.
- El coste se imputa por el centro de coste de la línea de detalle, que prevalece sobre la obra. Lo normal es que la obra y el centro de coste de la línea coincidan con los de la cabecera del documento, pero excepcionalmente pueden ser diferentes.
- La cifra a origen ya es acumulada: para una serie de meses se suman las cifras del mes, nunca las de origen.
- No confundir con el cierre definitivo de la obra, que se hace al terminarla.

## 5. Fase 0

**Qué es.** La fase del presupuesto que recoge lo previsto a fin de obra en cada momento del tiempo; por lo tanto, es una fase viva del presupuesto, ya sea de coste o de venta. Cada ámbito tiene su fase 0: la de coste recoge las mediciones reales que se van a ejecutar, a precio de coste; sobre ella se planifica, y su pestaña «Planificación compras» es la planificación de compras del jefe de obra. La de venta refleja las mediciones acordadas con la DF, coincidan o no con las reales, y los precios del presupuesto firmado con el cliente, además de las órdenes de cambio aprobadas.

**Sinónimos.** Previsto, presupuesto vivo, fase viva, coste previsto, venta prevista, coste fase 0, venta fase 0.

**Cuándo y cómo.** Para saber cómo está la obra hoy y compararla con el master vigente o con lo ejecutado. También aparece como oferta de referencia dentro de los comparativos, si nos referimos al ámbito coste. La mantiene el jefe de obra, que es quien planifica en ella tanto las mediciones como las compras, y se revisa en cada cierre mensual. Si cambia la venta prevista, hay que recalcular los proporcionales en fase 0.

**Trampas.**
- No guarda historia: cada día se sobrescribe. Para ver cómo era antes hay que ir a su foto en el master.
- Que la medición de coste fase 0 no coincida con la de venta fase 0 no es un error: una es la real y otra la contratada o aprobada por la DF.
- Al adjudicar un comparativo, Sigrid solo actualiza el precio unitario de coste fase 0, nunca la medición. Si se cambian mediciones o se añaden recursos en las ofertas, fase 0 no se actualiza.
- No es el master 0 (Estudios). «Fase 0» en los ámbitos reales es el previsto; «versión 0» en el master es Estudios.
- No es el planificado: el planificado es el master vigente (ABC o cuatrimestral); la fase 0 es el previsto de hoy.
- La medición a origen de una partida no puede superar la de fase 0: si la supera, primero se corrige fase 0.
- En coste fase 0, la pestaña «Descomposición» (el descompuesto de Estudios) pierde sentido, porque las mediciones se van actualizando. Para comparar con Estudios hay que ir al master 0.

## 6. Objetivo

**Qué es.** El porcentaje de mejora sobre el coste directo de estudio que marca dirección para alcanzar el beneficio previsto de la obra. Hay dos: uno para obra civil y otro para el conjunto de las instalaciones. En cada comparativo se refleja como una oferta ficticia «Objetivo»: una copia de la oferta Oficina técnica con ese porcentaje aplicado como descuento. En teoría, este objetivo se revisará tras el ABC, apareciendo entonces el objetivo revisado, que ya no será lineal, sino que cada unidad de compra tendrá un objetivo diferente; en la práctica, dirección no siempre lo revisa.

**Sinónimos.** Objetivo de compras, coste objetivo, oferta objetivo. ObjetivoRev u objetivo revisado: el que se fija después del ABC.

**Cuándo y cómo.** Dirección lo entrega en la hoja «Objetivo de Compras» al asignar la obra al jefe de obra, y es la referencia de los comparativos hasta el ABC (unos 45 días). Cuando el jefe de obra entrega el ABC, en teoría dirección marca objetivos nuevos y los comparativos pasan a llevar las ofertas «Planificación» y «ObjetivoRev» en lugar de «Oficina técnica» y «Objetivo».

**Trampas.**
- No es un proveedor: no cuenta en el número de ofertantes, la oferta más baja ni el ahorro. Esto en referencia a la oferta objetivo que introducimos en el comparativo.
- Objetivo y ObjetivoRev parten de bases distintas (el estudio o la planificación del jefe de obra). Comparar adjudicaciones de antes y de después del ABC contra «el objetivo» mezcla dos referencias.

## 7. Oficina técnica (como origen de un precio o una planificación)

**Qué es.** El precio o descompuesto que sale del estudio de la oferta, hecho por la oficina técnica. Se importa a Sigrid al adjudicar la obra como coste de estudio y queda bloqueado, solo para consulta. En los comparativos es la oferta ficticia «Oficina técnica».

**Sinónimos.** Estudio, coste de estudio, descompuesto de estudios, OT. Master 0.

**Cuándo y cómo.** Es la referencia de precio de los comparativos hasta que el jefe de obra entrega el ABC (unos 45 días). En la oferta Oficina técnica se ponen la medición y el precio unitario del descompuesto de estudios; si un recurso no estaba en el estudio, va a cero. Desde el ABC la sustituye la oferta «Planificación».

**Trampas.**
- Es una referencia interna, no una oferta: se excluye de cualquier análisis de mercado.
- Por defecto el comparativo copia cantidades y precios del DPC (la planificación). Si la planificación ya cambió, hay que poner a mano los de oficina técnica. Es la única oferta del comparativo en la que se puede tocar la medición; en las ofertas reales está prohibido. El propósito de esto es poder contar con un importe exacto de estudios (OT) referente a la unidad que se está comparando.
- Es la referencia inicial del coste directo. Para los indirectos, la referencia inicial es el master v1, no el master 0.
- Los descompuestos de estudio no sirven para planificar: no son productos válidos porque no llevan cuenta analítica ni naturaleza.
- Si una partida no tiene descompuesto de estudios, el precio se estima a partir del de la partida; debe ser un caso residual.
- Para consultar el descompuesto de Estudios hay que ir al master 0: en coste fase 0 la pestaña «Descomposición» pierde sentido porque las mediciones se actualizan.

## 8. Comparativo

**Qué es.** El documento de compras que pone lado a lado las ofertas de varios proveedores para una misma unidad de compra, y deja constancia de a quién se adjudica. Pasa por un circuito de firmas (jefe de obra, jefe de grupo, dirección de compras…) y acaba en contrato.

**Sinónimos.** Comparativo de ofertas, cuadro comparativo.

**Cuándo y cómo.** Siempre se crea desde el Documento de Planificación de Compras (DPC), seleccionando las partidas; si es de instalaciones, se marca ese tipo de comparativo (serie propia, ya que el proceso de firmas es diferente). Se añaden las ofertas ficticias (Oficina técnica o Planificación, y Objetivo u ObjetivoRev, según sea antes o después del ABC) y al menos tres ofertas reales, todas en estado «Recibida» (REB). Después se generan las condiciones, se valida y se firma. Firmado queda en APR, administración genera el contrato y la oferta adjudicada actualiza el precio de coste fase 0. Para compras de menos de 3.000 € existe el comparativo directo, que lleva las ofertas ficticias pero no exige un mínimo de ofertas reales

**Trampas.**
- Dentro hay ofertas ficticias (Oficina técnica o Planificación, Objetivo u ObjetivoRev): pueden ser casi la mitad de las ofertas registradas en Sigrid. El número de ofertantes y el ahorro solo cuentan las reales.
- Prohibido cambiar mediciones o añadir líneas en las ofertas: se cambian en la planificación de compras de la fase 0 y se actualiza el comparativo. Si no, el precio adjudicado no llega a fase 0.
- Un comparativo firmado no se modifica: cualquier cambio pasa por compras.
- Una ampliación lleva el código del comparativo maestro más una letra (A, B…) y solo admite una oferta de la empresa ya contratada.
- Si un comparativo rechazado vuelve al estado inicial, la oferta rechazada se queda en él. Para modificarla hay que duplicarla y proponer la copia, porque Sigrid no deja proponer dos veces la misma oferta. Por eso un mismo proveedor puede aparecer dos veces: el número de ofertantes se cuenta por proveedor, no por oferta.
- Los comparativos de instalaciones tienen serie propia y otro circuito de firmas: al medir plazos o circuitos, hay que separarlos de los de obra civil.
- Al adjudicar, solo se actualiza el precio unitario de coste fase 0, nunca la medición.
- En los comparativos directos puede haber una sola oferta real; eso no es falta de concurrencia. Al medir el número de ofertantes, hay que separarlos de los ordinarios.

## 9. Liquidatoria (factura o albarán liquidatorio, liquidación del contrato)

**Qué es.** El documento final de un contrato de compra, que cierra las cuentas con el proveedor: la factura (o el albarán o proforma) liquidatoria. La liquidación del contrato es el proceso de cerrarlo saldando lo pendiente.

**Sinónimos.** Factura de liquidación, factura última y liquidatoria, factura final, última factura, cierre del contrato. «Carta de liquidación» es la que se pide cuando la última factura no lo indica.

**Cuándo y cómo.** Al terminar los trabajos del contrato. Los administrativos de obra la marcan en Sigrid con una alarma de texto en el documento y avisan por correo al departamento financiero. Hasta la liquidatoria, el IVA de las facturas de los industriales (con o sin aporte de materiales) se difiere; desde ella ya no se difiere y no debería llegar ninguna factura más. Si, por error, la última factura de los trabajos no se pidió como liquidatoria, se pide al industrial una carta de liquidación.

**Trampas.**
- La marca es texto libre de una alarma, no un campo: puede faltar o estar mal escrita.
- Un contrato pendiente de carta de liquidación está cerrado igualmente.
- No confundir con la liquidación de la retención de garantía, la del IVA ni la liquidación final con el cliente.
- Una factura del mismo contrato posterior a la liquidatoria es una anomalía. Suelen ser trabajos adicionales excepcionales, y la factura debe venir como «factura única y liquidatoria». No confundir con la «factura última y liquidatoria», que es la que cierra el contrato.

## 10. Costes proporcionales y «generales»

**Qué es.** Todos los costes de la obra que se calculan como un porcentaje de la venta. Al adjudicar la obra se cargan en Sigrid los proporcionales de estudio (master 0), a título informativo, y los reales que tendrá la obra (master 1), que después pueden cambiar. Los habituales son un 9 % de estructura, un 1 % de postventa (2 % en viviendas) y otros como el TRC, los avales o la contratación, además de los gastos de delegación o de calidad y medioambiente. Algunos son directamente imputables a la obra (avales, TRC); otros son una tasa de aportación al sostenimiento de la estructura (el 9 %). En el árbol de Sigrid se ven en verde. En el cuadro de cierre aparecen como «Generales»; el 9 % de estructura es la aportación de la obra a los gastos generales de la empresa

**Sinónimos.** CP, gastos proporcionales, periodificables, «Generales».

**Cuándo y cómo.** En cada cierre, con la venta del mes ya cerrada (candado), desde el coste del mes con Acciones → Calcular periodificables. Lo mismo en coste fase 0, porque si cambia la venta prevista cambian los proporcionales de toda la obra; en fase 0 no hace falta cerrar la fase. También se recalculan al hacer cada planificación valorada. Los calcula el departamento de control de costes.

**Trampas.**
- Se calculan sobre la venta: si se lanzan antes de meter y cerrar la venta del mes, salen mal.
- Olvidar recalcularlos en fase 0 deja el previsto de la obra descuadrado y la vista resumen de Sigrid con cifras erróneas.
- En el cierre se llaman «Generales», pero no son los gastos generales de la empresa en sí: son la parte que se imputa a la obra.
- La referencia inicial de los proporcionales es el master v1, no el master 0, que es solo informativo.
- El 1 % (o 2 %) de postventa es una provisión, no el coste real de postventa.
- En Sigrid, «periodificables» son los proporcionales; no hay que confundirlos con los amortizables de la hoja de cierre.
- Los GG del presupuesto de venta al cliente (el GG+BI que separa el PEM del PEC) son un coeficiente de venta, no un coste
- Algunos proporcionales, como los avales o la postventa, son provisiones: el coste real entra después por asiento contable y la diferencia con lo provisionado genera un resultado
> Nota de Juan Romero: El punto 11 lo he renombrado al considerar que podría ser confuso mezclar indirectos y generales. De hecho, los generales suelen ser más afines con los proporcionales y lo he puesto en el punto 10.

## 11. Costes indirectos

**Qué es.** Los costes de la obra que no se asignan a una unidad de obra concreta, sino a la obra en su conjunto, y que dependen sobre todo de su duración. Son el equipo de obra (jefe de grupo, jefe de obra, encargado, capataz, técnico de prevención, administrativo…), las casetas, los medios auxiliares comunes y partidas como las tasas de ocupación de vía o las sanciones. En el árbol de Sigrid se ven en azul; los directos van en negro y los proporcionales en verde.

**Sinónimos.** Indirectos, CI, costes indirectos de obra, gastos de obra.

**Cuándo y cómo.** Se planifican en el estudio y se replanifican en el ABC y en cada cuatrimestral. El jefe de obra replanifica plazos y cantidades, pero los precios unitarios del equipo de obra los fija control de costes. Se imputan mes a mes mientras dura la obra, sobre todo con los partes de trabajo del equipo de obra y, en algunas partidas, con asientos contables que llegan de financiero.

**Trampas.**
- La referencia inicial es el master v1, no el master 0.
- La hoja de cierre suma a los indirectos los amortizables, que no están en Sigrid.
- Dependen del plazo, no de la producción: si la obra se alarga, el indirecto crece aunque la venta no cambie.
- No son los proporcionales ni los «Generales» del cuadro de cierre (término 10).
- Los avales no son indirectos aunque su coste real entre por asiento contable: son un proporcional provisionado (término 10).

## 12. Retención de garantía

**Qué es.** Un porcentaje que se descuenta del pago de cada factura o certificación como garantía de buena ejecución, y se devuelve al acabar el plazo de garantía. Va en dos sentidos: la que retenemos a los proveedores (dinero que les debemos) y la que nos retiene el cliente (dinero que nos debe).

**Sinónimos.** Retención, fondo de garantía, garantía retenida.

**Cuándo y cómo.** El porcentaje y el vencimiento los fija cada contrato. La retención se practica en cada factura o certificación. A los subcontratistas les suele vencer a los 12 meses de la RPO (recepción provisional de la obra), salvo que el contrato diga otra cosa. La que nos retiene el cliente depende de su contrato: suele ser también un año desde la RPO, pero puede ser de 15 meses o de otro plazo. La devolución no es automática: el industrial debe solicitarla expresamente a Ruesma con el modelo corporativo, y se inicia un proceso de validaciones. Si el contrato lo prevé, al terminar la obra el industrial puede entregar un aval por el importe retenido, y entonces se le devuelven las retenciones antes de su vencimiento.

**Trampas.**
- No mezclar los dos sentidos: retenido a proveedores y retenido por clientes son saldos opuestos.
- El saldo vivo a proveedores que manda es el de contabilidad, no el de los efectos.
- La retención que figura en el albarán y la de su factura son la misma: no se suman.
- No es la retención de IRPF ni otros descuentos que aparecen en la factura.
- El vencimiento se cuenta desde la RPO, no desde la fecha de cada factura. Mientras la obra no tenga RPO, la retención no tiene fecha de vencimiento cierta.
- Que una retención haya vencido no significa que se haya devuelto: la devolución exige la solicitud del industrial y las validaciones
- Los cargos de postventa (notas de cargo) se descuentan de la retención: reducen lo que se le devuelve al industrial, pero no son una devolución
- Una retención devuelta antes de vencer puede ser correcta: el industrial la ha sustituido por un aval. La garantía sigue existiendo, ahora en forma de aval. No es un error ni un pago anticipado indebido.
- Las facturas de industriales llevan retención aunque vayan fuera de contrato.

## Pendientes de revisión (lista de Juan Romero a 2026-11-17)

Sin definición todavía; del 28 al 31 son términos nuevos que añade a la lista.

- 14. Almacén
- 15. Levantamiento / postventa
- 16. Certificación
- 17. PEM / PEC
- 18. Costes amortizables / periodificables
- 19. DPC
- 20. Producción
- 21. Coste pendiente
- 22. Coste previsto
- 23. Recurso
- 24. Parte
- 25. Precios contradictorios / órdenes de cambio
- 26. Previsión / IMPUT
- 27. Descompuesto / planificado
- 28. Centro coste
- 29. Unidad de compra
- 30. Partida/subcapítulo/capitulo
- 31. Colchon/bolsa del jefe de obra
