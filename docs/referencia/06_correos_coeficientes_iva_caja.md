<!-- docs/referencia/06_correos_coeficientes_iva_caja.md -->
# Correos de Control de Costes sobre coeficientes de venta e IVA para la caja proyectada

> Origen: dos correos de Juan Romero (Dir. Admón y Control de Costes) a Pablo Gris · Fechas de los documentos: 2026-10-26 y 2026-10-27
> El de 2026-10-26 llegó en PDF (impresión de Outlook) y se convirtió a Markdown el 2026-10-27 con la herramienta MCP `markitdown`. El de 2026-10-27 llegó como texto pegado en la conversación y no requirió conversión.
> Los originales viven fuera del repositorio.

> **Redactado.** Se han quitado direcciones de correo, teléfonos, CIF y dirección postal de las firmas, los enlaces de Outlook y el pie legal de confidencialidad. La «captura» que cita el segundo correo no viene en el PDF: no está transcrita.

Contexto: sirven a F-150 (receta de la caja) y a F-099 / F-040. Las mediciones que las contrastan están en `progress/spec_F-150.md`.

## 1. «coeficientes de venta» · 2026-10-26

**Pregunta (Pablo Gris, 17:37):**

> Estoy preparando una estructura procedural para generar los flujos de caja por obra (todos los que se quiera) con diversas hipótesis con ClaudIA, pero tengo una duda con la venta. Tenemos el master venta donde los números son sin coeficientes. Como lo convierto desde devengo a caja también debería meterle los coeficientes ya que ingresaremos el total. Eso lo puedo sacar del ámbito venta? Mi idea era sacar los coeficientes por partida y eso es lo que aplicará al flujo de caja a partir de master venta.

**Respuesta (Juan Romero, 18:06, con copia a Elena Díaz):**

> Que confirme Elena si tenemos alguna excepción, pero en el ámbito venta (NO certificación) trabajamos con las cifras incluyendo coeficientes. De todas formas, podemos verlo con detalle: todas las partidas tienen alimentado su contrato, y cada contrato tiene sus coeficientes. Pero ya te digo, esto aplica a la certificación. Y en venta trabajamos sin coeficientes.

## 2. Respuesta al planteamiento de la caja · 2026-10-27

Juan contesta intercalado (marcado aquí con **→**) al correo que se le envió con las dudas de coeficientes e IVA.

> Pablo, en este sentido te echo una mano, pero creo que debes concretarlo con AdP. Entiendo que esta materia es suya.

**Coeficiente**

- La producción pendiente sale del master de venta, que da la venta de gestión, sin coeficientes. **→ OK. Sería interesante contrastarla con el ámbito certificación (más coeficientes).**
- Si no aplicamos el coeficiente, el cobro sale corto, normalmente en torno a un 19 %. **→ Los coeficientes son variopintos, aunque en líneas generales suele ser el 13 % + 6 %.**

**IVA**

- Se suma a lo certificado para saber cuánto entra de verdad en el banco. **→ Totalmente, al igual que para nuestros pagos hay que incluir el IVA soportado.**
- Además decide cuánto IVA hay que ingresar a Hacienda en cada liquidación trimestral. **→ AdP.**

**1. Coeficientes: de dónde los sacamos**

- Calculamos el coeficiente partida a partida… **→ Tenemos informado a nivel de detalle en contratos; si no existe puedes deducirlo como dices.**
- Lo sacamos del master de certificación, en la misma versión del master de venta. **→ OK.**
- Si una partida no está en el master de certificación, usamos el del master de venta; la diferencia es de 0,02 M€. **→ OK.**
- El importe no lo cogemos del master de certificación, solo el coeficiente… **→ Efectivamente, el ámbito certificación no es un referente, ya que no actualizamos fase 0, pero sí arroja datos buenos en la certificación fase «n».**
- Qué incluye: en Sigrid solo vemos el coeficiente total… ¿De dónde sacamos el desglose? **→ Captura que te envié ayer: lo tenemos desglosado, incluso si en obra pública con coeficiente de baja.**

Dudas:

- ¿Es correcto pasar de la venta de gestión a lo que se certifica aplicando el coeficiente del master de certificación? **→ Necesito aclaración sobre este punto.**
- ¿Hay conceptos que se certifiquen fuera de ese coeficiente, por ejemplo la revisión de precios? **→ Sí, ocurre en muchas ocasiones. Órdenes de cambio y contradictorios que van con coeficientes diferentes; incluso dentro del propio capítulo puede haber partidas con distintos coeficientes.**

**2. IVA de venta**

- Por defecto poníamos un 21 %. **→ En líneas generales aplica la ISP, pero hay bastantes obras que sí tienen IVA (suele ser el 21 %). Es raro ver IVA al 10 %; incluso en obras de viviendas, las mejoras a propietarios se facturan con el 21 %.**
- En la 0696 pensamos que, al ser vivienda, debería ir al 10 %. **→ No, es ISP. El 10 % lo aplicará el promotor al comprador final, supongo.**
- Ninguna obra factura al 10 %. **→ Ya te digo, es raro.**

Dudas:

- ¿El 0 % es inversión del sujeto pasivo, por ser venta a promotoras? **→ Creo que sí, aunque depende de varios factores.**
- ¿Podemos tomar el tipo de IVA de la ficha de la obra como dato fiable para la caja? **→ SÍ.**
- ¿Hay obras con tipos mezclados que la ficha no recoja? **→ Sí, caso de mejoras en viviendas: aplica el 21 % frente a ISP al promotor.**
