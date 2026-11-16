<!-- docs/referencia/07_glosario_incurrido.md -->
# Glosario de negocio: «incurrido / coste incurrido» (definición de Control de Costes)

> Origen: Juan Romero (Dir. Admón y Control de Costes), en un texto que pasó a Pablo Gris · Fecha: 2026-11-11.
> Llegó como texto pegado en la conversación, así que no hubo conversión. Se transcribe literal y solo se corrige el formato.
> Es la primera respuesta a la lista de términos que se envió a Negocio el 2026-10-20. Es la fuente de la entrada «incurrido» de F-054 (`config/diccionario/glosario.yaml`). Antes de publicarla, el spec-author de F-054 tiene que contrastar cada trampa con lo que calcula el datamart.

## Incurrido / coste incurrido

**Qué es.** Es el coste registrado e imputado a una unidad de coste, sea capitulo, subcapitulo o partida, a una fecha de cierre. Lo integran todos los documentos de compra: albaranes no facturados (incluye proformas), facturas recibidas y partes de trabajo, prevaleciendo para el cálculo del mismo el documento factura. Para determinadas partidas de costes indirectos (tasas ocupación de vía, avales, sanciones, etc) el coste incurrido lo componen, además de los anteriores, los asientos contables (sin documentos) registrados. Por definición, en las pruebas que he hecho, el coste incurrido es también el importe del coste incurrido en el cierre de obra (mes n), ya sea a origen o parcial.

**Sinónimos.** Coste real, coste incurrido, coste imputado, «lo que se ha gastado», coste de la fase, y lo creativo que se quiera poner alguno.

**Cuándo y cómo.** Se puede calcular en cualquier momento el coste total incurrido, pero lo normal es que se fije en cada cierre mensual. La fase de coste del mes, una vez cerrada, es la cifra de referencia para contrastarlo con los documentos. Lo alimentan los administrativos de obra al registrar albaranes y proformas, previsiones de coste, partes de trabajo y asientos que llegan del dpto financiero (solo indirectos y promoción delegada).

**Trampas o confusiones habituales.**

- No es lo facturado. Cuenta lo entregado por su fecha de entrega, aunque la factura llegue el mes siguiente.
- Manda la imputación de la factura. Si la factura pasa un albarán a otra partida, el incurrido se mueve con ella. Por eso, sumar albaranes por partida no cuadra. Si el documento albaran facturado de fecha «mes n» se ha facturado con fecha «mes n+1» el documento que prevalece en cierre del «mes n» es el albarán.
- Incluye las previsiones (albaranes PREV o «PREVISION»). Cuentan como incurrido, pero no son pendiente de facturar.
- Un documento registrado después de cerrar un mes entra en el mes siguiente. El incurrido a origen es correcto, pero el del mes queda desplazado.
- No es el valorado. El valorado es la medición por el precio de la partida, y no siempre coincide con el incurrido. En el coste real de Sigrid, el precio unitario es el resultado de dividir el incurrido entre la medición, no un precio contratado.
- Centro coste y obra no coinciden: Se imputa por el centro de coste de la línea de detalle, que prevalece sobre el campo obra.
- Almacén: coste incurrido sin partida asociada en las líneas registradas.

## Término derivado propuesto por Control de Costes

**Almacén:** coste incurrido sin partida asociada en las líneas registradas.
