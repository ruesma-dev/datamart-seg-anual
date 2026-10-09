<!-- specs/F-132-estado-desde-rac/requirements.md -->
# F-132 · La antigüedad del estado sale de `rac` y la foto diaria se retira tras contrastarla

Mediciones: `progress/spec_F-132.md`. Dos fases (D1): **A** al aprobar la spec;
**B** solo cuando el humano, con el contraste delante, decida sobre la foto (D7).

Vocabulario: **paso** = fila de `compras.documento_procesos` (F-085); **último
paso** = el de `es_ultimo`; **estado actual** = `con.est` de la cabecera
(`compras.contratos`, `facturas`, `comparativos`); **estados iniciales** =
factura {1, 20}, contrato {1}, comparativo {1, 11, 100} (medidos: son los de
todos los documentos sin pasos). **Historia NETA**: «Deshacer proceso» borra el
paso de `rac`, así que un estado al que se vuelve deshaciendo cuenta desde el
paso que llevó a él la primera vez (D2).

## Fase A · La vista desde `rac`

R1. El sistema debe publicar `compras.v_estado_documentos` con UNA fila por
documento de `compras.contratos` (44), `compras.facturas` (15) y
`compras.comparativos` (46) (D3), clave `documento_id`, sin leer
`compras.historial_estados` ni `compras.historial_estados_fotos`.

R2. La vista debe publicar, en este orden: `documento_id`,
`tipo_documento_codigo`, `tipo_documento` (CONTRATO, FACTURA, COMPARATIVO),
`codigo_documento`, `estado_id`, `estado_codigo`, `estado`, `en_estado_desde`,
`origen_fecha`, `dias_en_estado`, `cambio_posterior_a`, `paso_id`, `proceso`,
`usuario`, `nombre_usuario` (D4).

R3. El estado (`estado_id`, `estado_codigo`, `estado`) debe ser el de la
cabecera del documento, tal como lo publican sus tablas (pareja tipo-estado de
F-084), nunca el destino de un paso.

R4. CUANDO el destino del último paso es el estado actual, el sistema debe dar
`en_estado_desde` = `momento` del paso (hora de Madrid, al segundo; si el paso
no tiene hora, su `fecha` a las 00:00), `origen_fecha` = `PASO`, y `paso_id`,
`proceso`, `usuario` y `nombre_usuario` de ese paso.

R5. CUANDO el documento no tiene pasos y su estado actual es inicial de su
tipo, el sistema debe dar `en_estado_desde` = fecha de alta (`con.fec`) a las
00:00 y `origen_fecha` = `ALTA`; las columnas del paso, NULL.

R6. SI el destino del último paso no es el estado actual, o el documento no
tiene pasos y su estado no es inicial, ENTONCES el sistema debe dar
`origen_fecha` = `FUERA_DE_PROCESO`, `en_estado_desde` y `dias_en_estado` NULL
y `cambio_posterior_a` = `momento` del último paso (NULL si no tiene) (D5).

R7. `cambio_posterior_a` debe ser NULL en las filas `PASO` y `ALTA`.
R8. SI un documento `ALTA` no tiene fecha de alta (`con.fec` = 0), ENTONCES
`en_estado_desde` y `dias_en_estado` deben ser NULL y `origen_fecha` sigue
siendo `ALTA`.

R9. `dias_en_estado` debe ser la fecha de hoy en Madrid menos la fecha de
`en_estado_desde`, calculado AL CONSULTAR (no al construir).

R10. La vista debe crearse en un sub-paso nuevo de `build_compras`,
`13_estado_documentos.sql`, DETRÁS de `12_documento_procesos.sql`, con `DROP
VIEW IF EXISTS` + `CREATE VIEW`; `11_historial_estados.sql` debe dejar de
crearla y seguir tomando la foto sin otro cambio.

R11. Las familias, los estados iniciales y los tres orígenes deben vivir una
sola vez en `etl_sigrid/domain/estado_documentos.py`, con una función oráculo
que dé (`en_estado_desde`, `origen_fecha`, `cambio_posterior_a`) para un
documento; el SQL debe llevar los MISMOS literales (test).

## Fase A · El contraste foto ↔ `rac`

R12. CUANDO el humano ejecuta `python main.py contraste-estados`, el sistema
debe leer en una sesión de SOLO LECTURA los tramos de la foto cerrados por
`CAMBIO`, con su ventana (`observado_antes`, `desde`] y su estado nuevo, y los
pasos de esos documentos, y clasificar cada cambio con el dominio.

R13. Un cambio de la foto debe clasificarse, en este orden de prioridad:
`PASO` si hay un paso con destino el estado nuevo y `momento` (pasado de Madrid
a UTC) dentro de la ventana; `DESHECHO` si el último paso con `momento` ≤ fin de
la ventana tiene destino el estado nuevo; `VUELTA_AL_INICIAL` si no hay ningún
paso ≤ fin y el estado nuevo es inicial; `FUERA_DE_PROCESO` si el último paso ≤
fin lleva a otro estado y ningún paso posterior al fin lleva al estado nuevo;
y `DISCREPANCIA` en cualquier otro caso (p. ej. el paso existe, pero después
de la foto que ya vio el estado: reloj o zona horaria).

R14. El sistema debe clasificar también los documentos de contrato y factura
con algún paso en la ventana de una foto que esa foto no vio cambiar: `ALTA` si
la foto les abrió tramo (no de línea base) en ella, `IDA_Y_VUELTA` si el
destino del último paso ≤ fin es el estado que la foto les vio, y
`DISCREPANCIA` si no.

R15. El comando debe imprimir una tabla por noche (`observado_en`), tipo de
documento y clase, y los `documento_id` de cada `DISCREPANCIA` (como mucho 50
por noche), y salir con código 1 si hay alguna `DISCREPANCIA`, 0 si no.

R16. SI no hay ninguna foto posterior a la línea base, ENTONCES el comando debe
decirlo y salir con código 0 sin clasificar nada.
R17. El comando no debe escribir en la base: ni `INSERT`, ni `UPDATE`, ni DDL
(test sobre el SQL que ejecuta y sesión `read_only`).

## Fase A · La premisa falsa y las preguntas

R18. Las fichas de `config/diccionario/compras.yaml` deben decir que la fecha
del cambio de estado sale de `rac`: `v_estado_documentos` (reescrita: orígenes,
historia neta, `FUERA_DE_PROCESO` sin fecha), `contratos` (descripción y
ejemplo de pregunta), `historial_estados` e `historial_estados_fotos` (ya no
«lo único que sabe cuándo»: respaldo en contraste, F-132) y `fn_sigrid_tiempo`.

R19. La ficha de `raw.conest` (`config/diccionario/raw.yaml`) no debe decir que
ninguna tabla guarda cuándo entró un documento en su estado, ni que `tiemod`
sirve de aproximación.

R20. `config/diccionario/00_global.yaml` debe subir a la versión 46 con su
entrada de historia; la descripción del esquema `compras` debe citar la vista
desde `rac`; P23 debe pasar a `respondible` sin `bloqueada_por`, con una
respuesta que filtra `estado_codigo = 'EPF'` y `dias_en_estado > 21`, da
`en_estado_desde` como la fecha del envío y avisa de los envíos antiguos sin
cerrar; P24 debe esperar `compras.documento_procesos`.

R21. `config/tables_sigrid.yaml` (bloque C3), `docs/ARCHITECTURE.md` y
`README_COMPRAS_C1_C2.md` deben decir que la antigüedad del estado sale de
`rac` (F-132) y que la foto es un respaldo en contraste.

R22. Ningún texto VIGENTE del repositorio —código, SQL, `config/`, `docs/`,
`README*`; fuera quedan `progress/`, `specs/` y las entradas de historia de
`00_global.yaml`— debe afirmar que Sigrid no guarda cuándo cambia el estado
(test con las frases conocidas).

R23. `azure-apps/datamart_seg_anual.md` debe recoger F-132 (la vista cambia de
columnas y de familias) y quitar el «SIN DESPLEGAR» y el «Sigrid no la guarda»
de la sección de F-067, en un commit de ese repositorio.

R24. CUANDO se pregunta al MCP, sin explicarle nada, «¿qué contratos llevan más
de tres semanas enviados sin firmar y desde cuándo?», la respuesta debe dar la
fecha real del envío desde `compras.v_estado_documentos` (MANUAL, humano).

## Fase B · La retirada (solo tras la decisión D7 del humano)

R25. DONDE el humano decida RETIRAR la foto, `build_compras` debe dejar de
ejecutar `11_historial_estados.sql` (el fichero se borra), y `EPOCA_DELPHI` y
`fecha_delphi` deben seguir existiendo en el dominio para `fn_sigrid_tiempo`.

R26. DONDE la decisión sea BORRAR las tablas, CUANDO el humano ejecuta `python
main.py retirar-foto-estados --confirmar`, el sistema debe borrar las dos
tablas en una transacción; sin `--confirmar` debe imprimir lo que haría y no
tocar nada. `reset-compras` debe borrar entonces todas las tablas del esquema,
sin lista de persistentes y sin `DROP SCHEMA`, y las dos fichas y
`contraste-estados` deben desaparecer.

R27. DONDE la decisión sea CONGELAR las tablas, ningún build debe escribirlas,
`reset-compras` debe seguir conservándolas y sus fichas deben decir desde y
hasta cuándo hay foto y que la fecha del cambio está en la vista.

R28. Tras la Fase B, el diccionario debe subir de versión, P24 no debe esperar
`compras.historial_estados` y `docs/ARCHITECTURE.md` y `azure-apps` deben
describir lo que quede.
