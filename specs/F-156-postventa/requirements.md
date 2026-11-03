# F-156 · Postventa entera: unidades, incidencias, tareas, histórico y gráficos

Mediciones (2026-11-03, solo lectura): `progress/spec_F-156.md`. Diseño: `design.md`.
Vocabulario: la **incidencia** es la reclamación de Sigrid (`rcp`, `con.tip` 708, serie
`RS…`), el «parte de reclamación» de Posventa; sus **tareas** son `tar` (`con.tip` 47, serie
`REP2…`); la **unidad** es la unidad postventa (`upv`, `con.tip` 707).

## Decisiones para la PARADA 1 (recomendada en negrita; alternativas en design § 8)

- **D1 · Datos personales** (propietario, quien reclama, contacto): **A** en
  `postventa_restringida` con autorización ESCRITA del responsable del dato (como F-057);
  B fuera (propietario como id opaco). Sin autorización al implementar, se hace B.
- **D2 · `mcp-bbdd`**: **pliego a ese repositorio** (lista blanca e índice de adjuntos
  múltiple) en el contrato de `azure-apps`; hasta entonces el MCP no ve postventa.
- **D3 · Perfiles**: **`postventa` para estándar, total y restringido**.
- **D4 · Coste**: **se enlaza, no se calcula** (Sigrid no lo liga a la incidencia).
- **D5 · Ingesta**: **completa cada noche** (~78.000 filas, ~15 s). **D6 · Orden**:
  **tras `build_contabilidad`**. **D7 · Fases**: **una feature aquí**, otra en `mcp-bbdd`.
- **D8 · Cierres de la aplicación**: **traer de `dbo.log` solo las 659 líneas
  `Cerrar parte (postventa-incidencias)`**; B: declararlos sin fecha.
- **D9 · Partes firmados** (PV002, DNI manuscrito): **familia `REPARACION` abrible solo por
  quien lee `postventa_restringida`**; con D1=B, fuera del índice.
- **D10 · Texto libre**: **en `postventa` con teléfonos y correos enmascarados**; íntegro
  solo en `postventa_restringida` (D1=A).

## A · Ingesta (`config/tables_sigrid.yaml`)

- **R1.** El sistema debe declarar `upv`, `rcp`, `rcpint`, `obrofc`, `auxrcp`, `auxtrcp`, `auxofc`,
  `prmtpl` y `auxgra` enteras, `tar` con `where` `rcpide > 0` y `tarres` con las tareas de
  reclamación, cada una con un comentario con sus cifras del 2026-11-03.
- **R2.** El sistema debe declarar `log` con `include_columns` sin `res` y un `where` que deje solo
  las líneas `tab = 'con'`, `tip = 708` cuyo `tex` empiece por
  `Cerrar parte (postventa-incidencias)` (D8).
- **R3.** DONDE D1=A, el sistema debe declarar `per` con `include_columns` = `ide`, `nom`, `tel`,
  `tel2`, `ele` y un `where` con solo las personas de `rcp.recide`, `rcp.cntide` o
  `upv.peride`; SI entra `dni`, una credencial (`esiglog`, `esigpas`, `clamai`), una dirección
  o una observación, ENTONCES un test debe fallar.
- **R4.** El `where` de `rcg` y `gra` debe pasar a los tipos `12, 14, 15, 44, 46, 707, 708, 47`, y
  `compras/14_documento_adjuntos.sql` debe seguir filtrando solo las cinco de compras.
- **R5.** El censo de `raw` debe subir de 80 a 92 (93 con D1=A) donde se fija (tests, fichas,
  `docs/ARCHITECTURE.md`, `CLAUDE.md`).

## B · Esquema `postventa` (paso `build_postventa`)

- **R6.** El sistema debe publicar `postventa.unidades`, una fila por `upv`: empresa, obra (id y
  código), código y nombre de la unidad, estado (707), tipología, fechas de garantía,
  escrituración, primer listado y visita técnica, y `tiene_propietario`.
- **R7.** El sistema debe publicar `postventa.incidencias`, una fila por `rcp` con cabecera en
  `raw.con`: empresa, obra, unidad, código, fecha y momento de alta, estado (708), clase,
  tipo, oficio, motivo, forma de comunicación (código), urgencia, ubicación, descripción y
  descripción larga enmascaradas (D10) y `referencia_externa` (`RCPCLI`).
- **R8.** Cada incidencia debe llevar `fin_garantia_clase` (`fecfin1` para la clase 0001, `fecfin2`
  para la 0002, NULL para la 0003 y sin clase) y `dentro_garantia` (alta <= fin; NULL sin fin).
- **R9.** El sistema debe publicar `postventa.incidencia_intervinientes` (una fila por `rcpint`
  con incidencia existente: oficio, proveedor y causante) y `postventa.oficios_obra` (una por
  `obrofc`: obra, oficio y proveedor).
- **R10.** El sistema debe publicar `postventa.tareas`, una fila por tarea de reclamación: su
  incidencia, código, estado (47), `empleado_id` sin nombre, oficio y proveedor por `tarres`,
  fechas, prioridad, porcentaje y texto enmascarado.
- **R11.** SI una columna de `postventa` contiene `telefono`, `correo`, `dni`, `reclamante`,
  `contacto` o `propietario_nombre`, ENTONCES un test debe fallar.
- **R12.** SI `raw.rcp` llega vacía o con menos del 99 % de sus filas con cabecera 708 en `raw.con`,
  ENTONCES el sub-paso debe fallar con la cifra.
- **R13.** La máscara debe cambiar por `[TELEFONO]` nueve dígitos que empiezan por 6-9 (seguidos o
  en grupos 3-2-2-2) y por `[CORREO]` las direcciones de correo, igual en SQL
  (`postventa.fn_enmascarar`) y en el dominio (`enmascarar`), con los mismos casos.

## C · Histórico

- **R14.** El sistema debe publicar `postventa.incidencia_procesos`: una fila por paso de `raw.rac`
  de los tipos 707, 708 y 47 (origen `RAC`) y una por línea de `raw.log` de R2 (origen
  `CIERRE_APLICACION`, destino 9), con documento, tipo, proceso, estados de origen y destino
  traducidos por la pareja tipo-estado, login, fecha, momento y `es_ultimo`.
- **R15.** El sistema debe publicar `postventa.v_estado_incidencias` con `en_estado_desde` y
  `origen_fecha` por este orden: `PASO` (último paso con destino = estado),
  `CIERRE_APLICACION` (estado 9 y cierre de la aplicación posterior al último paso), `ALTA`
  (sin pasos y estado 1, desde el alta) y `SIN_HISTORIAL` (el resto, fecha NULL).
- **R16.** La vista debe dar `abierta` (estado 1 o 3), `fecha_resolucion` (primer momento a 5, 7 o
  9), `dias_hasta_resolucion`, `dias_abierta` (hasta hoy si abierta) y `dias_en_estado`.
- **R17.** CUANDO se reconstruya con el `raw` del 2026-11-03, `origen_fecha` debe dar ~19.505
  `PASO`, ~658 `CIERRE_APLICACION`, ~2.015 `ALTA` y ~1 `SIN_HISTORIAL` (MANUAL).
- **R18.** `domain/postventa.py` debe ser el oráculo de R8, R13, R15 y R16; un test debe comparar
  sus literales con los del SQL.

## D · Gráficos (adjuntos)

- **R19.** El sistema debe publicar `postventa.documento_adjuntos`, una fila por enlace de `raw.rcg`
  de los tipos 707, 708 y 47 con su gráfico, con las columnas que lee `abrir_adjunto`
  (`adjunto_id`, `familia`, `documento_id`, `codigo_documento`, `cod_repositorio`,
  `empresa_repositorio` entera, `nombre_fichero`, `extension`) más `incidencia_id`,
  `unidad_id`, `tarea_id`, `clase_grafico`, `descripcion`, `fecha_alta` y `subido_por`.
- **R20.** `familia` debe ser `UNIDAD` (707), `TAREA` (47), `REPARACION` (708 y `gratipide` 35) o
  `INCIDENCIA` (resto de 708), con los literales del dominio; DONDE D1=B, sin `REPARACION`.
- **R21.** SI más del 1 % de los enlaces de postventa no tienen su gráfico en `raw.gra`, ENTONCES
  el sub-paso debe fallar (como F-090 R15).
- **R22.** La ficha debe declarar el origen de cada familia para `abrir_adjunto` (`INCIDENCIA` →
  `postventa.incidencias.incidencia_id`, `UNIDAD` → `postventa.unidades.unidad_id`, `TAREA` →
  `postventa.tareas.tarea_id`, `REPARACION` →
  `postventa_restringida.contactos_incidencia.incidencia_id`) y que hay DNI manuscrito.

## E · Datos personales (DONDE D1=A)

- **R23.** El sistema debe publicar en `postventa_restringida` `contactos_incidencia` (propietario,
  quien reclama y contacto: nombre, teléfonos, correo), `contactos_unidad` (propietario,
  persona de contacto, `restel`, `resele`, avisos y horarios) y `textos` (íntegros de
  incidencias y tareas), y su ficha debe citar la autorización (quién y fecha).
- **R24.** SI una columna de `postventa_restringida` sale de `per.dni`, de una credencial, de una
  dirección o de una observación, ENTONCES un test debe fallar.

## F · Permisos y pipeline

- **R25.** `postventa` debe estar en `DEFAULT_CONSUMPTION_SCHEMAS` y (D3) en
  `DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS`; DONDE D1=A, `postventa_restringida` en
  `DEFAULT_VETOED_SCHEMAS` y `DEFAULT_RESTRICTED_SCHEMAS` y en ninguna otra.
- **R26.** `.env.example`, `infra/sql/02_roles.sql` y `ESQUEMAS_DEL_DATAMART` deben recoger los
  esquemas nuevos; un test debe comparar sus listas con `settings`.
- **R27.** `run-all` debe incluir `build_postventa` tras `build_contabilidad` y antes de
  `ingest_descompuestos`, con `depends_on = ["ingest_raw"]`, sin dependientes y en
  `PASOS_CON_PERMISOS`; debe existir el comando `build-postventa`.
- **R28.** SI `build_postventa` falla, ENTONCES la noche debe continuar y `R-FRESCURA` debe
  alcanzar a sus esquemas.

## G · Diccionario y documentación

- **R29.** Cada objeto nuevo debe tener ficha (`postventa.yaml`, `postventa_restringida.yaml`, y
  `raw.yaml` para las tablas nuevas) con las trampas medidas: 1.502 cabeceras sin `rcp`, 1.499
  intervinientes huérfanos, 15.229 sin clase, forma con solo el 1 documentado, coste y venta de
  `tar` a 0, sin fin de garantía de estructura, unidades de venta vacías en Sigrid.
- **R30.** La ficha de `postventa` debe decir que el coste de postventa NO está aquí y dónde está
  (obras `POSTV`/`POSTV2`/`0004` y partidas de postventa en `mart`), sin enlace por incidencia.
- **R31.** `00_global.yaml` debe subir `version` en uno, añadir los esquemas, `R-POSTVENTA-RESTRINGIDA`
  (D1=A) y al menos tres `ejemplos_preguntas` (abiertas por obra y oficio, tiempo medio de
  resolución, por unidad dentro de garantía).
- **R32.** `docs/ARCHITECTURE.md`, el mapa de `CLAUDE.md` y `azure-apps/datamart_seg_anual.md`
  (commit local, sin push) deben describir el esquema, las tablas que consume y el pliego D2.
- **R33.** `bash harness/init.sh` debe terminar en verde.

