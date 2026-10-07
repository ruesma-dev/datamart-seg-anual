<!-- specs/F-085-quien-aprobo-que-y-cuando/requirements.md -->
# F-085 · Requisitos · Quién aprobó qué y cuándo

Mediciones y porqués: `progress/spec_F-085.md` (2026-10-07, solo lectura).
**El hallazgo que reordena la ficha**: la fuente es `rac`, el registro de
PROCESOS de Sigrid (la ventana «Procesos» de la captura de Carmen Calle). Cada
fila es un paso con proceso, estado de origen y destino, login, fecha y hora, y
cubre las cuatro familias: facturas 99,94 %, contratos 97,1 %, comparativos
97,0 % y obras 72,2 % (los que faltan no han salido de su estado inicial).
`dbo.log` deja de hacer falta y `confir` sigue siendo el detalle de firmas del
comparativo que ya publica F-038 (`compras.comparativo_firmas`).

## Decisiones que pide al humano (recomendación en negrita; detalle en design §8)

- **D1 · Quitar el filtro de `raw.rac`** (`where: asiide <> 0`) en vez de una
  segunda tabla: +1,76 M filas, ~+3 min, ~+260 MB. F-095 ya filtra en su SQL.
- **D2 · Familias**: **las cuatro de la ficha** (factura 15, contrato 44,
  comparativo 46, obra 42). Oferta, albarán y efecto quedan en `raw.rac`.
- **D3 · `rac.tex` sigue excluida**: hay correos pegados con nombres y
  direcciones de terceros.
- **D4 · El usuario se publica como login**, igual que `comparativo_firmas`; el
  nombre de la persona, no (la tabla `usu` lleva contraseñas y DNI).
- **D5 · `dbo.log` no se ingiere en F-085**: la firma digital, el alta, las
  modificaciones y los pasos deshechos son de F-105.
- **D6 · `confir` no cambia**: DOCVAL (factura) y OBRHOJ (obra) no se publican.
- **D7 · F-067 no se toca aquí**; su premisa la corrige otra feature.
- **D8 · `conpro` y `rol` no se ingieren**: `rac.res` ya trae el nombre.

Los requisitos de abajo asumen las ocho recomendaciones.

## A · La ingesta (D1, D3)

- R1. El sistema debe declarar `rac` en `config/tables_sigrid.yaml` con
  `where: null` y `exclude_columns: [tex]`, y el comentario de la entrada debe
  decir por qué ya no va filtrada (F-085), con las cifras medidas (2.517.791
  filas, 758.927 con asiento) y el coste estimado.
- R2. El censo debe seguir en 71 tablas: F-085 no da de alta `conpro`, `usu`,
  `rol` ni `log`.
- R3. CUANDO `retenciones.apuntes_contables` lea `raw.rac`, el sistema debe
  seguir filtrando `asiide <> 0 AND conide <> 0` en el SQL (hoy ya lo hace, en el
  CTE `rac_asiento`), de modo que quitar el filtro de la ingesta no cambia su
  resultado.

## B · El historial de procesos (D2, D4)

- R4. El sistema debe construir `compras.documento_procesos` en `build_compras`,
  una fila por fila de `raw.rac` cuyo documento sea de una de las familias
  declaradas una sola vez en el dominio: 15 FACTURA, 44 CONTRATO, 46 COMPARATIVO
  y 42 OBRA.
- R5. La tabla debe tener clave primaria `paso_id` (`rac.ide`) y publicar el
  documento (`documento_id`, `tipo_documento_codigo`, `familia`,
  `codigo_documento`), el proceso (`proceso_id`, `proceso`), los estados
  (`estado_origen_id`, `estado_origen_codigo`, `estado_origen`,
  `estado_destino_id`, `estado_destino_codigo`, `estado_destino`), `usuario`,
  `fecha`, `hora`, `momento` y `asiento_id`.
- R6. El sistema debe traducir los estados de origen y de destino con
  `compras.fn_estado_documento(tipo, estado)`, nunca solo por el estado.
- R7. SI `rac.conproide` es 0, ENTONCES `proceso_id` debe ser NULL y `proceso`
  debe seguir siendo el nombre de `rac.res` sin espacios a los lados.
- R8. SI `rac.asiide` es 0, ENTONCES `asiento_id` debe ser NULL.
- R9. SI `rac.fec` es 0, ENTONCES `fecha` debe ser NULL; SI `rac.hor` es 0 o no es
  una hora HHMMSS válida, ENTONCES `hora` debe ser NULL; y `momento` es fecha más
  hora, NULL si falta cualquiera de las dos. La hora es la local de Madrid, la
  que enseña Sigrid.
- R10. El sistema debe numerar los pasos de cada documento en `orden` (1, 2…)
  por `fecha`, `hora` y `paso_id`, y marcar `es_ultimo` en el de mayor orden.
- R11. El sistema debe publicar `encaja_con_anterior`: verdadero si el
  `estado_origen_id` del paso es el `estado_destino_id` del anterior, falso si
  no, y NULL en el primer paso del documento.
- R12. El sistema debe publicar `dias_desde_anterior`: días (con decimales) entre
  el `momento` del paso anterior y el de este; NULL en el primero o si falta
  algún `momento`.
- R13. La regla de R9-R12 debe estar escrita una vez como oráculo puro en
  `etl_sigrid/domain/documento_procesos.py`, y un test debe fijar que el SQL
  lleva los mismos literales (familias, orden de desempate).
- R14. SI una fila de `raw.rac` no tiene documento en `raw.con`, ENTONCES no
  entra en la tabla (84 huérfanas medidas).

## C · El diccionario y los documentos

- R15. La ficha de `compras.documento_procesos` debe declarar grano y clave, la
  cobertura medida por familia (documentos con pasos sobre el total y por qué
  faltan los demás), que es la historia NETA («Deshacer proceso» borra el paso)
  y que la bruta, con los pasos deshechos y la firma digital, está en
  `dbo.log` (F-105), que `usuario` es el login y no el nombre, que el estado
  actual coincide con el destino del último paso en el 99,96 % de las facturas,
  y a qué objeto ir para las firmas pendientes del comparativo
  (`compras.comparativo_firmas`).
- R16. La ficha debe decir que la aprobación de una FACTURA está aquí y no en
  `confir`: sus 3.474 filas DOCVAL no tienen ninguna firma y el 97,4 % de esas
  facturas ya está aprobada para pago.
- R17. La ficha de `raw.rac` debe dejar de decir que la tabla va filtrada y
  seguir diciendo que `retenciones.apuntes_contables` solo usa las filas con
  `asiide <> 0` y que `usu` es un login legible por el MCP.
- R18. La ficha de `compras.comparativos` (`fecha_aprobacion`) y la de
  `compras.comparativo_firmas` deben dejar de afirmar que Sigrid no guarda
  cuándo cambió el estado, y apuntar a `compras.documento_procesos`.
- R19. `config/diccionario/00_global.yaml` debe subir `version` y la lista de
  pendientes no debe crecer.
- R20. `docs/ARCHITECTURE.md` («Qué se copia de Sigrid» y «Lo que Sigrid NO
  guarda») y el comentario «LO QUE SIGRID NO GUARDA» de
  `config/tables_sigrid.yaml` deben corregirse: `rac` no va filtrada y el
  historial de procesos SÍ existe en Sigrid.
- R21. `azure-apps/datamart_seg_anual.md` debe recoger el objeto nuevo y que
  `raw.rac` va sin filtro, en el mismo trabajo.

## D · Lo que se comprueba contra la base (manual, humano)

- R22. CUANDO se construya `compras` sobre un `raw` cargado sin filtro, la
  factura FR26/10025 debe dar exactamente cuatro pasos: Comprobar (REC→COM,
  jmvargas, 28/09/2026 16:52:11), Contabilizar (COM→CON, jmvargas, 16:52:50,
  con asiento), Aprobar (CON→APJO, ialvarez, 05/10/2026 16:23:32) y Aprobar
  (APJO→APRJG, jmsanchez, 16:58:15), con `es_ultimo` en el cuarto.
- R23. La cobertura por familia y la coincidencia del último paso con el estado
  actual deben quedar medidas en `progress/impl_F-085.md`, dentro de ±0,5
  puntos de las de la spec.
- R24. `retenciones.apuntes_contables` debe dar el mismo número de filas y el
  mismo importe antes y después de quitar el filtro.
- R25. El coste real de ingesta de `raw.rac` y del nuevo sub-paso se debe medir
  y anotar frente a la nocturna del 2026-10-07 (4 h 37 min 44 s).
