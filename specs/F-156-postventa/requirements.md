# F-156 · Postventa entera: unidades, incidencias, tareas, histórico, gráficos y coste

Mediciones (2026-11-03, solo lectura): `progress/spec_F-156.md`. Diseño: `design.md`. Pliego
para `mcp-bbdd`: `pliego_mcp_bbdd.md`. Vocabulario: la **incidencia** es la reclamación de
Sigrid (`rcp`, `con.tip` 708, serie `RS…`), el «parte de reclamación» de Posventa; sus
**tareas** son `tar` (47, serie `REP2…`); la **unidad** es la unidad postventa (`upv`, 707).

## Decisiones del humano (2026-11-03, chat; alternativas descartadas en design § 9)

- **D1 = A**: datos personales en `postventa_restringida` («d1 ok», el humano, 2026-11-03), que
  leen el **perfil nuevo «postventa»** (= el restringido + `postventa_restringida`) y el total.
- **D2**: pliego a `mcp-bbdd` (`pliego_mcp_bbdd.md`); hasta su despliegue el MCP no ve postventa.
- **D3**: `postventa` lo leen estándar, total, restringido y postventa.
- **D4**: el coste se liga a la OBRA de origen por las partidas de las obras de postventa.
- **D5-D8, D10** las recomendadas: ingesta completa; tras `build_contabilidad`; una feature;
  de `dbo.log` solo los 659 cierres de la aplicación; texto enmascarado en el general.
- **D9**: `REPARACION` (partes firmados) la abren el perfil postventa y el total, no el restringido.

## A · Ingesta (`config/tables_sigrid.yaml`)

- **R1.** El sistema debe declarar `upv`, `rcp`, `rcpint`, `obrofc`, `auxrcp`, `auxtrcp`, `auxofc`,
  `prmtpl` y `auxgra` enteras, `tar` con `where` `rcpide > 0` y `tarres` con las tareas de
  reclamación, cada una con un comentario con sus cifras del 2026-11-03.
- **R2.** El sistema debe declarar `log` con `include_columns` sin `res` y un `where` que deje solo
  `tab = 'con'`, `tip = 708` y `tex` que empiece por `Cerrar parte (postventa-incidencias)`.
- **R3.** El sistema debe declarar `per` con `include_columns` = `ide`, `nom`, `tel`, `tel2`, `ele`
  y un `where` con solo las personas de `rcp.recide`, `rcp.cntide` o `upv.peride`; SI entra
  `dni`, una credencial (`esiglog`, `esigpas`, `clamai`), una dirección o una observación,
  ENTONCES un test debe fallar.
- **R4.** El `where` de `rcg` y `gra` debe pasar a los tipos `12, 14, 15, 44, 46, 707, 708, 47`, y
  `compras/14_documento_adjuntos.sql` debe seguir filtrando solo las cinco de compras.
- **R5.** El censo de `raw` debe subir de 80 a 93 donde se fija (tests, fichas,
  `docs/ARCHITECTURE.md`, `CLAUDE.md`).

## B · Esquema `postventa` (paso `build_postventa`)

- **R6.** El sistema debe publicar `postventa.unidades`, una fila por `upv`: empresa, obra (id y
  código), código y nombre de la unidad, estado (707), tipología, fechas de garantía,
  escrituración, primer listado y visita técnica, y `tiene_propietario`.
- **R7.** El sistema debe publicar `postventa.incidencias`, una fila por `rcp` con cabecera en
  `raw.con`: empresa, obra, unidad, código, fecha y momento de alta, estado (708), clase,
  tipo, oficio, motivo, forma de comunicación (código), urgencia, ubicación, descripción y
  descripción larga enmascaradas (D10) y `referencia_externa` (`RCPCLI`).
- **R8.** Cada incidencia debe llevar `fin_garantia_clase` (`fecfin1` para la clase 0001,
  `fecfin2` para la 0002, NULL para la 0003 y sin clase) y `dentro_garantia` (alta <= fin).
- **R9.** El sistema debe publicar `postventa.incidencia_intervinientes` (una fila por `rcpint` con
  incidencia existente: oficio, proveedor, causante) y `postventa.oficios_obra` (por `obrofc`).
- **R10.** El sistema debe publicar `postventa.tareas`, una fila por tarea de reclamación: su
  incidencia, código, estado (47), `empleado_id` sin nombre, oficio y proveedor por `tarres`,
  fechas, prioridad, porcentaje y texto enmascarado.
- **R11.** SI una columna de `postventa` contiene `telefono`, `correo`, `dni`, `reclamante`,
  `contacto` o `propietario_nombre`, ENTONCES un test debe fallar.
- **R12.** SI `raw.rcp` llega vacía o con menos del 99 % de sus filas con cabecera 708 en
  `raw.con`, ENTONCES el sub-paso debe fallar con la cifra.
- **R13.** La máscara debe cambiar por `[TELEFONO]` nueve dígitos que empiezan por 6-9 (seguidos
  o en grupos 3-2-2-2) y por `[CORREO]` las direcciones de correo, igual en SQL
  (`postventa.fn_enmascarar`) y en el dominio (`enmascarar`), con los mismos casos.

## C · Histórico (fechas, estados y quién)

- **R14.** El sistema debe publicar `postventa.incidencia_procesos`: una fila por paso de
  `raw.rac` de los tipos 707, 708 y 47 (origen `RAC`) y una por línea de `raw.log` de R2 (origen
  `CIERRE_APLICACION`, destino 9), con documento, tipo, proceso, estado de origen y de destino
  (id, código y nombre por la pareja tipo-estado), fecha, momento, `usuario` (el login: `rac.usu`,
  `log.usu`), `usuario_nombre` (de `raw.usu`, NULL si el login no está) y `es_ultimo`.
- **R15.** El sistema debe publicar `postventa.v_estado_incidencias` con `en_estado_desde`,
  `cambiado_por` (login del paso que la dejó en su estado) y `origen_fecha` por este orden:
  `PASO` (último paso con destino = estado), `CIERRE_APLICACION` (estado 9 y cierre de la
  aplicación posterior al último paso), `ALTA` (sin pasos y estado 1) y `SIN_HISTORIAL`.
- **R16.** La vista debe dar `abierta` (1 o 3), `fecha_resolucion` (primer momento a 5, 7 o 9),
  `dias_hasta_resolucion`, `dias_abierta` (hasta hoy si abierta) y `dias_en_estado`.
- **R17.** CUANDO se reconstruya con el `raw` del 2026-11-03, `origen_fecha` debe dar ~19.505
  `PASO`, ~658 `CIERRE_APLICACION`, ~2.015 `ALTA` y ~1 `SIN_HISTORIAL`, y `usuario` informado en
  el 100 % de los pasos y `usuario_nombre` en ~96,8 % de los de 708 (MANUAL).
- **R18.** `domain/postventa.py` debe ser el oráculo de R8, R13, R15, R16 y R25; un test debe
  comparar sus literales con los del SQL.

## D · Gráficos (adjuntos)

- **R19.** El sistema debe publicar `postventa.documento_adjuntos`, una fila por enlace de `raw.rcg`
  de los tipos 707, 708 y 47 con su gráfico, con las columnas que lee `abrir_adjunto`
  (`adjunto_id`, `familia`, `documento_id`, `codigo_documento`, `cod_repositorio`,
  `empresa_repositorio` entera, `nombre_fichero`, `extension`) más `incidencia_id`,
  `unidad_id`, `tarea_id`, `clase_grafico`, `descripcion`, `fecha_alta` y `subido_por`.
- **R20.** `familia` debe ser `UNIDAD` (707), `TAREA` (47), `REPARACION` (708 y `gratipide` 35) o
  `INCIDENCIA` (resto de 708), con los literales del dominio.
- **R21.** SI más del 1 % de los enlaces de postventa no tienen su gráfico en `raw.gra`, ENTONCES
  el sub-paso debe fallar (como F-090 R15).
- **R22.** La ficha debe declarar el origen de cada familia para `abrir_adjunto` (`INCIDENCIA` →
  `postventa.incidencias.incidencia_id`, `UNIDAD` → `postventa.unidades.unidad_id`, `TAREA` →
  `postventa.tareas.tarea_id`, `REPARACION` →
  `postventa_restringida.contactos_incidencia.incidencia_id`), que hay DNI manuscrito y quién
  abre cada familia (D9).

## E · Datos personales (`postventa_restringida`)

- **R23.** El sistema debe publicar `postventa_restringida.contactos_incidencia` (propietario,
  quien reclama y contacto: nombre, teléfonos, correo), `contactos_unidad` (propietario,
  persona de contacto, `restel`, `resele`, avisos, horarios) y `textos` (íntegros de
  incidencias y tareas); su ficha debe citar «d1 ok», el humano, chat del 2026-11-03.
- **R24.** SI una columna de `postventa_restringida` sale de `per.dni`, de una credencial, de una
  dirección o de una observación, ENTONCES un test debe fallar.

## F · Coste de postventa por obra (D4)

- **R25.** El sistema debe publicar `postventa.partida_obra_origen`: una fila por partida de las
  obras de postventa (tipo 42 con «POSTVENTA» en el nombre o código `POSTV*`) con la obra de origen
  de su empresa por el código de la partida (cifras iniciales a 4 con ceros) o, si no, del
  ancestro más cercano que lo tenga, y `liga` = `PARTIDA`, `ANCESTRO` o `SIN_OBRA`.
- **R26.** El sistema debe publicar la vista `postventa.v_coste_obra`: el coste de FACTURAS de
  compra (`compras.factura_lineas` + `compras.facturas.fecha_factura`) de esas partidas por obra
  de postventa, obra de origen y mes. El coste de los partes de personal NO entra (el perfil
  restringido no ve `personal`); la ficha dice cómo cruzarlo con `personal.partes_lineas`.
- **R27.** CUANDO se consulte con el dato del 2026-11-03, la parte ligada debe ser ~2.577.000 €
  de facturas (POSTV y POSTV2 de la empresa 1) frente a ~537.000 € sin obra (MANUAL).

## G · Permisos, perfil postventa y pipeline

- **R28.** `postventa` debe estar en `DEFAULT_CONSUMPTION_SCHEMAS` y en
  `DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS`; `postventa_restringida` en `DEFAULT_VETOED_SCHEMAS` y
  `DEFAULT_RESTRICTED_SCHEMAS` y en ninguna otra lista salvo la de R29.
- **R29.** `settings` debe declarar `DEFAULT_PERFIL_POSTVENTA_GROUP`
  (`sigrid_dm_perfil_postventa_ro`), `DEFAULT_PERFIL_POSTVENTA_LOGIN` (`mcp_sigrid_dm_postventa`)
  y `DEFAULT_PERFIL_POSTVENTA_SCHEMAS` = la lista del restringido + `postventa_restringida`;
  SI la lista no es exactamente esa, ENTONCES `apply_grants` debe terminar FAILED sin conectar.
- **R30.** `apply_grants` debe conceder al grupo postventa lo suyo con privilegio por defecto en
  REVOKE, vetarle todo esquema del catálogo que no sea suyo, buscar sus vistas que filtran y
  verificar en el catálogo lo que lee y sus pertenencias, como al restringido (F-141).
- **R31.** `.env.example`, `infra/sql/02_roles.sql` (grupo, login con `POSTVENTA_PWD` y punto
  5 sexies) y `ESQUEMAS_DEL_DATAMART` deben recoger lo anterior; un test debe comparar sus
  listas con `settings`.
- **R32.** `run-all` debe incluir `build_postventa` tras `build_contabilidad` y antes de
  `ingest_descompuestos`, con `depends_on = ["ingest_raw"]`, sin dependientes y en
  `PASOS_CON_PERMISOS`; debe existir `build-postventa`. SI falla, ENTONCES la noche debe
  continuar y `R-FRESCURA` debe alcanzar a sus dos esquemas.

## H · Diccionario y documentación

- **R33.** Cada objeto nuevo debe tener ficha (`postventa.yaml`, `postventa_restringida.yaml`,
  `raw.yaml`) con las trampas medidas: 1.502 cabeceras sin `rcp`, 1.499 intervinientes
  huérfanos, 15.229 sin clase, forma con solo el 1 documentado, coste de `tar` a 0, sin fin de
  garantía de estructura, unidades de venta vacías en Sigrid y logins sin nombre.
- **R34.** `00_global.yaml` debe subir `version` en uno, añadir los esquemas,
  `R-POSTVENTA-RESTRINGIDA` y tres `ejemplos_preguntas` (abiertas por obra y oficio, tiempo
  medio de resolución, por unidad dentro de garantía) y una de coste por obra.
- **R35.** `docs/ARCHITECTURE.md`, el mapa de `CLAUDE.md` y `azure-apps/datamart_seg_anual.md`
  (commit local, sin push) deben describir los esquemas, el perfil postventa, las tablas que
  consume y el pliego.
- **R36.** `bash harness/init.sh` debe terminar en verde.
