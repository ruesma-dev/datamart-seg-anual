<!-- specs/F-067-compras-seguimiento-mcp/requirements.md -->
# F-067 · Requisitos · Compras por el MCP (con F-125: código 2 y necesidades)

Mediciones y porqués: `progress/spec_F-067.md`. No se reabre lo cerrado: la
**foto diaria** de estados es decisión del humano (2026-09-06); el estado y la
fecha de la factura (F-083), el cruce con pagos (F-080), el estado del contrato
(F-084) y el comparativo entero (F-038) ya están y no se rehacen.

## Decisiones que pide al humano (recomendación en negrita; detalle en §4 del informe)

- **D1 · Una entrega o dos.** **Una sola**, con la foto la primera tarea: la
  historia cuenta desde el día que se despliega y cada noche de retraso es una
  noche perdida. Si prefiere dos: Fase 1 = bloques A y B (foto y contratos)
  con su parte de D; Fase 2 = bloque C (código 2 y necesidades).
- **D2 · `con.tiemod` como «fecha de última modificación» del contrato.**
  **Publicarla, pero nunca como antigüedad del estado**: medido, la firma no la
  mueve (en el 85 % de los comparativos firmados la última firma es posterior a
  `tiemod`). La antigüedad la da solo la foto (R9-R11).
- **D3 · El código 2 y la necesidad también en las líneas de contrato y de
  factura** (mismos campos en `ctrpro`/`dcfpro`). **Sí**: coste nulo, y «gasto
  por código 2» se pregunta sobre facturas.
- **D4 · «Proveedores por actividad» (acceptance 4) pasa a F-055**, que modela
  `conact`. **Sí**: aquí solo se le dice a Compras que «validada» no existe en
  Sigrid (`conact.homolo = 0` en las 7.090 filas).

Los requisitos de abajo asumen las cuatro recomendaciones.

## A · La foto diaria de estados (acceptance 2 y 5)

- R1. El sistema debe mantener `compras.historial_estados`, una fila por TRAMO
  (documento, estado, desde, hasta) de los contratos (`con.tip` 44) y las
  facturas (15); la lista de tipos vive una vez en el dominio.
- R2. CUANDO `build_compras` corra con un `raw.con` más nuevo que la última
  foto, el sistema debe cerrar (`hasta` = esta observación) el tramo abierto de
  cada documento cuyo `con.est` haya cambiado y abrir uno nuevo con `desde` =
  esta observación y `observado_antes` = la observación anterior.
- R3. CUANDO un documento aparezca por primera vez después de la línea base, el
  sistema debe abrirle un tramo con `es_linea_base` falso.
- R4. CUANDO se tome la primera foto, el sistema debe abrir un tramo por
  documento con `es_linea_base` verdadero y `observado_antes` NULL («ya estaba
  en ese estado; desde cuándo, no se sabe»).
- R5. CUANDO un documento deje de estar en `raw.con`, el sistema debe cerrar su
  tramo con `motivo_cierre = 'DESAPARECIDO'` y no abrir otro.
- R6. SI los documentos de los tipos de R1 presentes en `raw.con` son menos del
  98 % de los tramos abiertos, ENTONCES el build debe fallar con `RAISE
  EXCEPTION` y no escribir nada (una ingesta a medias no cierra la historia).
- R7. SI `raw.con` no es más nuevo que la última foto, ENTONCES el sistema no
  debe escribir nada (idempotente al relanzar).
- R8. El sistema debe registrar cada foto en `compras.historial_estados_fotos`
  (instante observado, documentos, cambios, altas, desaparecidos). Ninguna de
  las dos tablas se borra ni se vacía jamás: ni `DROP`, ni `TRUNCATE`, ni
  `DELETE` en el SQL (test); `--full` solo trunca `raw`.
- R9. El sistema debe publicar `compras.v_estado_documentos`, una fila por
  documento de R1 con su tramo abierto: estado, `en_estado_desde`,
  `antiguedad_es_minima` (= `es_linea_base`) y `dias_en_estado`.
- R10. MIENTRAS el tramo sea de línea base, `dias_en_estado` debe ser un MÍNIMO
  («lleva al menos N días»); la ficha debe decir que, en cuanto ese mínimo
  supera 21, «más de tres semanas» es una respuesta cierta.
- R11. La ficha de la vista debe declarar que el cambio ocurrió entre
  `observado_antes` y `desde` (no a una hora exacta), y que la historia empieza
  el día del despliegue.

## B · El contrato: condiciones y última modificación (acceptance 1)

- R12. `compras.contratos` debe ganar AL FINAL, sin tocar las quince de
  siempre: `forma_pago_id` (`ctr.pagide`), `forma_pago` (`auxpag.res`),
  `retencion_garantia_porcentaje` y `retencion_garantia_concepto`.
- R13. La retención debe salir de `raw.ctrrec` con concepto de código `RET%`
  (6.333 contratos); SI hay más de una, ENTONCES la de menor `pos`; el
  porcentaje en tanto por cien (`valpor` 0,05 → 5).
- R14. `compras.contratos` debe publicar `fecha_ultima_modificacion` desde
  `con.tiemod` (fecha de Delphi: días desde 1899-12-30) con una función del
  dominio y su espejo SQL; la ficha debe decir que NO es la fecha del cambio de
  estado y por qué (D2).
- R15. La ficha de `contratos` debe decir que la penalización no es un campo de
  Sigrid y que solo aparece en el texto (`compras.documento_texto`, 9 contratos).
- R16. La ficha de `contratos` debe dejar de decir «no se puede saber cuánto
  lleva» y remitir a `compras.v_estado_documentos`.

## C · El código 2 y el documento de necesidades (F-125)

- R17. `compras.albaran_lineas` debe ganar AL FINAL `codigo_alternativo`
  (`dcapro.cod2`, vacío → NULL), `necesidad_id` (`dncide`) y
  `necesidad_linea_id` (`dncproide`), 0 → NULL.
- R18. DONDE D3 esté aprobada, `compras.contrato_lineas` y
  `compras.factura_lineas` deben ganar las mismas tres columnas al final.
- R19. El sistema debe publicar `compras.necesidades`, una fila por `raw.dnc`
  (`necesidad_id` PK) con código, nombre, fecha de alta (`con`, tip 36), obra
  y `n_lineas` (`dncpro`).
- R20. `descompuestos.v_pbi_planif_jo` y `v_pbi_master_planif_jo` deben ganar
  AL FINAL `necesidad_id` (`dncpro.dncide` de su `dncpro_id`), sin cambiar su
  `FROM ... WHERE origen = ...` ni la tabla `descompuestos.lineas`.
- R21. Ningún fichero del sello de `descompuestos` (`00_setup.sql`,
  `01_troceado.sql`, `03_lineas_master.sql`) debe cambiar (lo verifica el
  reviewer con `git diff main --stat`).
- R22. Las fichas deben llamar «código 2» a `codigo_alternativo` en
  `compras` y en `descompuestos`: lo pone el jefe de obra para agrupar o filtrar
  sus compras en el documento de planificación de compras (DPC), y viaja de la
  línea de necesidad al albarán (igual en el 99,9 % de las 295.210 enlazadas).
- R23. La ficha de `descompuestos.lineas` debe decir que el código alternativo
  es el código 2 en los cuatro orígenes (ESTUDIO y master: campo 7 del texto;
  PLANIF_JO: `dncpro.cod2`) y que en el master es el de la fecha de la versión.
- R24. La ficha de `compras.necesidades` debe decir que es el DPC, uno por obra
  (271 de 277), y que su estado no informa (los 277 «En curso»).
- R25. Relaciones declaradas: `albaran_lineas.necesidad_id` → `necesidades`;
  `necesidad_linea_id` → `descompuestos.v_pbi_planif_jo.dncpro_id`;
  `necesidades.obra_id` → `maestro.obras`.

## D · Comparativos y cierre (acceptance 3, 6, 7)

- R26. El acceptance 3 ya se responde con `compras.comparativos` (F-038):
  `actividad_id` 99,2 % y `proveedor_ganador_id` 87,7 %. El sistema no debe
  crear objetos nuevos para él; la ficha debe ganar las dos preguntas como
  `ejemplos_preguntas` y la nota de los 877 comparativos con contrato y sin
  ganadora única (su proveedor, por `contrato_id`).
- R27. `00_global.yaml` debe subir `version` y ganar preguntas de aceptación
  para las cuatro del correo, con P de «más de tres semanas» en `parcial` hasta
  21 días después del despliegue.
- R28. Cada objeto nuevo o cambiado debe tener ficha, clave declarada y
  relaciones; `check-unicidad`, `check-relaciones`, `check-declarados` y
  `check-diccionario` en verde tras la nocturna (MANUAL).
- R29. `docs/ARCHITECTURE.md` y `azure-apps/datamart_seg_anual.md` deben
  recoger las tablas persistentes de `compras` y los objetos nuevos.
- R30. Probado con Compras por el MCP (MANUAL): enviados sin firmar y su
  antigüedad; comparativos por actividad y adjudicaciones repetidas; facturas
  por estado con su fecha de cambio; un albarán de MOMOSA (`AC26/28510`) con
  líneas sin contrato muestra su código 2.

**Fuera de alcance**: `conact` y proveedores por actividad (F-055, D4); quién
aprobó (F-085, que podrá rellenar hacia atrás la historia desde `dbo.log`);
tesorería (F-037); foto de comparativos u ofertas (sus firmas ya tienen fecha).
