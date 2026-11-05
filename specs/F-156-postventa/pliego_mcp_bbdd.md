# Pliego para `mcp-bbdd` · lo que necesita la F-156 de `datamart-seg-anual` (postventa)

> De: `datamart-seg-anual`, F-156 (spec del 2026-11-03, decisiones del humano del mismo día).
> Para: el repositorio `mcp-bbdd`, que lo implementa y prueba en su propia feature. Aquí NO
> hay URLs, contraseñas ni identificadores: solo nombres de esquema, de rol y de secreto.
> Contrato vivo en `azure-apps/datamart_seg_anual.md` (se enlaza allí, no se duplica).

## Qué publica el datamart

- **`postventa`** (esquema general): `unidades`, `oficios_obra`, `incidencias`,
  `incidencia_intervinientes`, `tareas`, `incidencia_procesos` (histórico: fecha, estados de
  origen y destino, login y nombre de quien lo cambió), `v_estado_incidencias`,
  `documento_adjuntos`, `partida_obra_origen` y `v_coste_obra`. Sin nombres, teléfonos ni
  correos de clientes; texto libre con teléfonos y correos enmascarados.
- **`postventa_restringida`**: `contactos_incidencia`, `contactos_unidad` y `textos`, con los
  datos personales de propietarios, reclamantes y contactos (autorización del humano,
  2026-11-03, «d1 ok»).
- Las fichas de los dos esquemas van en el diccionario (`_meta.v_diccionario`) de la versión
  que se publique con la F-156.

## P1 · Lista blanca

Añadir a `seguridad.esquemas_permitidos`: `postventa` (entre los generales) y
`postventa_restringida` (al final, común a los perfiles como las otras `*_restringida`: a quien
no deba leerla la frena PostgreSQL con PERMISO_DENEGADO, no el validador). Actualizar el test que
fija la lista completa y su orden (`test_f022_esquema_compras_restringida.py` o el que lo herede).

## P2 · Índice de adjuntos múltiple

`adjuntos.indice` admite hoy UN objeto (`compras.documento_adjuntos`). Debe admitir una LISTA:

| Índice | Familias → tabla de origen (LEFT JOIN con el login de quien pregunta) |
|---|---|
| `compras.documento_adjuntos` | las cinco de hoy, sin cambios |
| `postventa.documento_adjuntos` | `INCIDENCIA` → `postventa.incidencias.incidencia_id`; `UNIDAD` → `postventa.unidades.unidad_id`; `TAREA` → `postventa.tareas.tarea_id`; `REPARACION` → `postventa_restringida.contactos_incidencia.incidencia_id` |

- Columnas idénticas en los dos índices (`adjunto_id`, `familia`, `documento_id`,
  `codigo_documento`, `cod_repositorio`, `empresa_repositorio` ENTERA, `nombre_fichero`,
  `extension`). `adjunto_id` es `rcg.ide` en los dos: único entre ambos (la herramienta puede
  buscar en uno y luego en el otro).
- **`REPARACION` son partes firmados por el cliente con su DNI manuscrito** (≈ 4.430): solo los
  abren el perfil postventa y el total; el estándar y el restringido deben recibir
  PERMISO_DENEGADO por la regla de origen, nunca el fichero.
- Ficheros: pdf, jpg/jpeg, png, heic, jfif, mp4/mov/3gp (≈ 190 vídeos) y algún zip/rar/msg;
  los vídeos y comprimidos no tienen extractor de texto: decidir allí si se entregan como
  enlace o se rechazan.

## P3 · Perfil nuevo «postventa»

- **Rol**: grupo `sigrid_dm_perfil_postventa_ro` (NOLOGIN, lleva los permisos) y login
  `mcp_sigrid_dm_postventa`, miembro solo de su grupo. Los crea el humano con
  `infra/sql/02_roles.sql` del datamart; la contraseña vive SOLO en `kv-mcp-bbdd-dev` como
  `pg-password-postventa`.
- **Qué ve**: lo mismo que el perfil restringido (`mart`, `cierre`, `compras`, `maestro`,
  `retenciones`, `descompuestos`, `stg`, `aux`, `_meta` y `postventa`) **más
  `postventa_restringida`**. No ve `contabilidad`, `tesoreria`, `personal`, `raw` ni las otras
  `*_restringida`. Lo garantiza `apply_grants` cada noche; el MCP no tiene que filtrar nada.
- **Orden de perfiles**: TOTAL ⊃ POSTVENTA ⊃ RESTRINGIDO, y ESTÁNDAR ⊃ RESTRINGIDO (estándar y
  postventa no se contienen: postventa ve los datos de clientes y no ve `personal` ni la
  cartera). El total lee `postventa_restringida` por pertenencia al grupo autorizado.
- **Qué conexión usa**: una tercera conexión fija con ese login, elegida por quien pregunta como
  hoy el restringido (por oid y grupo de Entra, fuera de todo repositorio; contrato E1-E8 de
  `azure-apps/datamart_seg_anual.md`). Quién es de Posventa lo decide Negocio. Por defecto,
  nunca hacia arriba: sin pertenencia expresa, el usuario no cae en este perfil.

## P4 · Puesta en marcha

Tras publicar el diccionario de la F-156: desplegar P1-P3, reiniciar el MCP (cachea el
diccionario) y probar, por perfil, tres preguntas («incidencias abiertas por obra y oficio»,
«tiempo medio de resolución», «coste de postventa por obra») y abrir un `REPARACION` con el
estándar (debe negarse) y con el perfil postventa (debe abrirse).
