<!-- specs/F-085-quien-aprobo-que-y-cuando/requirements.md -->
# F-085 · Requisitos · Quién aprobó qué y cuándo

Mediciones y porqués: `progress/spec_F-085.md` (2026-10-07, solo lectura).
**La fuente es `rac`**, el registro de PROCESOS de Sigrid (la ventana
«Procesos»): un paso por fila con proceso, estado de origen y destino, login,
fecha y hora. Cubre facturas 99,94 %, contratos 97,1 %, comparativos 97,0 % y
obras 72,2 % (las que faltan no han salido de su estado inicial). `dbo.log` no
hace falta y `confir` sigue siendo el detalle de firmas del comparativo (F-038).

## Decisiones: DECIDIDAS por el humano el 2026-10-07

- **D1** Quitar el filtro `asiide <> 0` de `raw.rac` (F-095 ya filtra en su SQL).
- **D2** Familias 15 FACTURA, 44 CONTRATO, 46 COMPARATIVO y 42 OBRA.
- **D3** `rac.tex` sigue excluida (hay correos pegados con datos de terceros).
- **D4 (CAMBIADA respecto a la propuesta)** «Luego querré saber quién lo ha
  hecho por nombre»: se ingiere `usu` SIN credenciales; `compras` publica login
  Y NOMBRE; el DNI y el enlace al empleado van SOLO en `personal`. Censo 71 → 72.
- **D5** `dbo.log` se queda en F-105. **D6** `confir` sin cambios.
- **D7** F-067 no se toca aquí: el líder ficha una feature que saca la
  antigüedad del estado de `rac` y retira la foto tras 1-2 semanas de contraste.
- **D8** `conpro` y `rol` no se ingieren.

## A · La ingesta (D1, D3, D4)

- R1. El sistema debe declarar `rac` en `config/tables_sigrid.yaml` con
  `where: null` y `exclude_columns: [tex]`, y el comentario debe decir por qué
  ya no va filtrada (F-085) con las cifras (2.517.791 filas, 758.927 con
  asiento) y el coste estimado.
- R2. El sistema debe declarar `usu` con `exclude_columns` exactamente
  `[cla, fir, feccla, diascla, sid, cerid, dni, ele, com, resdes]`: contraseña,
  firma digital, metadatos de la clave, identificadores de seguridad y de
  certificado, DNI (vacío en las 233 filas: el DNI sale de `raw.emp`), correo y
  textos libres. El comentario debe decir el motivo de cada una.
- R3. SI alguien añade a `usu` una columna de credenciales (`cla`, `fir`,
  `feccla`, `diascla`, `sid`, `cerid`), ENTONCES un test debe fallar: la lista
  vive una vez en el dominio.
- R4. El censo debe pasar de 71 a 72 tablas (`usu`), y no se dan de alta
  `conpro`, `rol` ni `log`.
- R5. CUANDO `retenciones.apuntes_contables` lea `raw.rac`, debe seguir
  filtrando `asiide <> 0 AND conide <> 0` en su SQL (CTE `rac_asiento`), de modo
  que quitar el filtro de la ingesta no cambia su resultado.

## B · El historial de procesos: `compras.documento_procesos` (D2, D4)

- R6. El sistema debe construir `compras.documento_procesos` en `build_compras`,
  una fila por fila de `raw.rac` cuyo documento sea de una de las familias
  declaradas una sola vez en el dominio (15, 44, 46, 42).
- R7. Clave primaria `paso_id` (`rac.ide`); columnas: `documento_id`,
  `tipo_documento_codigo`, `familia`, `codigo_documento`, `proceso_id`,
  `proceso`, `estado_origen_id`, `estado_origen_codigo`, `estado_origen`,
  `estado_destino_id`, `estado_destino_codigo`, `estado_destino`, `usuario`,
  `nombre_usuario`, `fecha`, `hora`, `momento`, `asiento_id`, `orden`,
  `es_ultimo`, `encaja_con_anterior`, `dias_desde_anterior`.
- R8. Los estados se traducen con `compras.fn_estado_documento(tipo, estado)`,
  nunca solo por el estado.
- R9. SI `rac.conproide` es 0, ENTONCES `proceso_id` es NULL y `proceso` es
  `rac.res` sin espacios a los lados. SI `rac.asiide` es 0, `asiento_id` es NULL.
- R10. SI `rac.fec` es 0, `fecha` es NULL; SI `rac.hor` es 0 o no es una hora
  HHMMSS válida, `hora` es NULL; `momento` = fecha + hora, NULL si falta una. Es
  la hora local de Madrid que enseña Sigrid.
- R11. `orden` numera los pasos de cada documento (1, 2…) por `fecha`, `hora` y
  `paso_id`; `es_ultimo` marca el de mayor orden.
- R12. `encaja_con_anterior`: verdadero si `estado_origen_id` = el
  `estado_destino_id` del paso anterior, falso si no, NULL en el primero.
- R13. `dias_desde_anterior`: días con dos decimales entre el `momento` anterior
  y este; NULL en el primero o si falta algún `momento`.
- R14. `nombre_usuario` es `usu.res` del usuario cuyo login casa con
  `rac.usu` comparando en MAYÚSCULAS y sin espacios a los lados (exacto casan
  133 logins, 91,0 % de las filas; así, 137, 93,0 %). SI no casa, ENTONCES
  `nombre_usuario` es NULL y `usuario` sigue publicado.
- R15. La regla de R10-R14 debe estar escrita una vez como oráculo puro en
  `etl_sigrid/domain/documento_procesos.py`, y un test fija que el SQL lleva
  los mismos literales (familias, orden de desempate, normalización del login).
- R16. SI una fila de `raw.rac` no tiene documento en `raw.con`, no entra (84).

## C · Los usuarios con su persona: `personal.usuarios_sigrid` (D4)

- R17. El sistema debe construir `personal.usuarios_sigrid` en `build_personal`,
  una fila por fila de `raw.usu` (233), clave primaria `usuario_id` (`usu.ide`),
  con `login`, `nombre`, `desactivado` (`tipdes <> 0`), `codigo_empleado`,
  `empleado_id` y `dni`.
- R18. `empleado_id` es el `con.ide` de tipo 43 cuyo `cod` = `usu.codemp`: si
  hay uno, ése; si hay varios (una ficha por empresa), el de la empresa 1; si
  no, NULL. Medido: 211 con código, 210 casan, 189 únicos y 21 por empresa 1.
- R19. `dni` es `raw.emp.dni` de ese empleado (vacío → NULL): 204 usuarios.
- R20. La tabla no debe tener ninguna columna de credenciales ni de contacto;
  `login` es única sin distinguir mayúsculas (233 de 233, medido).
- R21. `personal.usuarios_sigrid` queda bajo el mismo GRANT por esquema que el
  resto de `personal`, sin tocar `config/settings.py`.

## D · El diccionario y los documentos

- R22. Ficha de `compras.documento_procesos`: grano y clave, cobertura por
  familia y por qué faltan los demás, historia NETA («Deshacer proceso» borra el
  paso; la bruta y la firma digital están en `dbo.log`, F-105), estado actual =
  destino del último paso (99,96 % facturas), `usuario` login y
  `nombre_usuario` con su cobertura (93,0 % de las filas, NULL = login sin ficha
  en Sigrid), el DNI solo en `personal`, y que las firmas pendientes del
  comparativo están en `compras.comparativo_firmas`.
- R23. Esa ficha debe decir que la aprobación de una FACTURA está aquí y no en
  `confir`: sus 3.474 filas DOCVAL no tienen ninguna firma y el 97,4 % de esas
  facturas ya está aprobada para pago.
- R24. Ficha de `personal.usuarios_sigrid`: datos personales autorizados
  (nombre y DNI, 2026-09-18 y 2026-10-07), qué NO sube (credenciales, correo),
  la regla de R18 con sus cifras, y la relación con `personal.recursos` por
  `empleado_id`.
- R25. Fichas de `raw.usu` (qué trae, qué se excluye y por qué, legible por el
  MCP sin DNI ni credenciales) y de `raw.rac` (ya no va filtrada;
  `retenciones` solo usa `asiide <> 0`; `usu` es un login).
- R26. Las fichas de `compras.comparativos` (`fecha_aprobacion`) y de
  `compras.comparativo_firmas` dejan de afirmar que Sigrid no guarda cuándo
  cambió el estado y apuntan a `compras.documento_procesos`.
- R27. `00_global.yaml`: `version` +1, el recuento de tablas a 72, y la lista
  de pendientes no crece.
- R28. `docs/ARCHITECTURE.md` («Qué se copia de Sigrid»: 72 tablas, `rac` sin
  filtro, `usu` sin credenciales; «Lo que Sigrid NO guarda» corregido), el
  bloque «LO QUE SIGRID NO GUARDA» de `tables_sigrid.yaml`, `raw.yaml` y
  `azure-apps/datamart_seg_anual.md` se actualizan en el mismo trabajo.

## E · Contra la base (manual, humano)

- R29. La factura FR26/10025 da cuatro pasos: Comprobar (REC→COM, jmvargas,
  28/09/2026 16:52:11), Contabilizar (COM→CON, jmvargas, 16:52:50, con
  asiento), Aprobar (CON→APJO, ialvarez, 05/10/2026 16:23:32) y Aprobar
  (APJO→APRJG, jmsanchez, 16:58:15), los cuatro con `nombre_usuario`, y
  `es_ultimo` en el cuarto.
- R30. Cobertura por familia, coincidencia del último paso con el estado
  actual, cobertura de `nombre_usuario` y recuentos de R18-R19 medidos en
  `progress/impl_F-085.md`, dentro de ±0,5 puntos de la spec.
- R31. `retenciones.apuntes_contables` da las mismas filas, obras e importe
  antes y después de quitar el filtro; `check-raw-recuentos` en verde.
- R32. Coste real de ingesta de `rac` y `usu` y de los dos sub-pasos nuevos,
  frente a la nocturna del 2026-10-07 (4 h 37 min 44 s).
