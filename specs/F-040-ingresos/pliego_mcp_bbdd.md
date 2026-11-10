# Pliego para `mcp-bbdd` · lo que necesita la F-040 de `datamart-seg-anual` (ventas)

> De: `datamart-seg-anual`, F-040 (desplegada en Azure el 2026-11-10).
> Para: el repositorio `mcp-bbdd`. Se añade a su **F-034**, junto al pliego de postventa
> (decisión del humano del 2026-11-10: «todo en f34»). Aquí NO hay URLs, contraseñas ni
> identificadores, solo nombres de esquema y de rol. El contrato vivo está en
> `azure-apps/datamart_seg_anual.md`, que se enlaza y no se duplica.

## Qué publica el datamart

- **`ventas`** (esquema general, lo leen el perfil estándar y el total):
  - Tablas: `clientes`, `facturas`, `factura_lineas`, `factura_recargos`, `certificaciones`,
    `certificacion_recargos`, `certificacion_factura` y `cobertura_enlace`.
  - Vistas: `v_factura_cobro`, `v_seguimiento_certificacion` y `v_contraste_certificado_obra`.
  - El CIF de una persona jurídica es público.
  - Lo que identifica a una persona física va a NULL: su NIF, el código de cliente con forma de
    NIF y el texto de las líneas de sus facturas. También va a NULL lo de las facturas cuyo
    cliente no está en `raw.cli`.
- **`ventas_restringida`** (solo el perfil total): `clientes_contacto`, `factura_cabecera` y
  `factura_lineas_persona`, con los datos personales de los clientes.
- Ni el perfil restringido ni el de postventa leen ninguno de los dos esquemas.
- Las fichas están en el diccionario v75, publicado en `_meta` el 2026-11-10. Las reglas son
  `R-VENTAS-TRES-CIFRAS` (emitido, facturado y cobrado son tres cifras distintas que no se
  suman) y `R-VENTAS-RESTRINGIDA`.

## P4 · Lista blanca (se añade a P1 de F-034)

Añadir a `seguridad.esquemas_permitidos`:
- `ventas`, entre los generales.
- `ventas_restringida`, al final, común a los perfiles como las demás `*_restringida`. Al
  estándar lo frena PostgreSQL con PERMISO_DENEGADO, no el validador. Ve el nombre y la ficha,
  que es el riesgo aceptado en F-008 y que mitiga `R-VENTAS-RESTRINGIDA`.

Hay que actualizar el test que fija la lista completa y su orden
(`test_f022_esquema_compras_restringida.py`).

**Los permisos ya están dados y comprobados en Azure** (2026-11-10, `02_roles.sql` y
`apply-grants`, con las cuatro verificaciones ok). Leídos con `has_table_privilege` sobre los
logins:

| Login | `ventas` | `ventas_restringida` |
|---|---|---|
| `mcp_sigrid_dm_ro` (estándar) | sí | no |
| `mcp_sigrid_dm_total` | sí | sí |
| `mcp_sigrid_dm_restringido` | no | no |
| `mcp_sigrid_dm_postventa` | no | no |

En `mcp-bbdd` no hace falta ningún perfil nuevo ni ningún secreto para esto.

## Aceptación propuesta (para la spec de F-034)

- El MCP lista y consulta `ventas` con los perfiles estándar y total.
- `ventas_restringida` da PERMISO_DENEGADO con el estándar, y con el total devuelve filas.
- `describir_tabla` sirve las fichas de la v75 o posterior. Hay que reiniciar después de
  desplegar, porque el servidor cachea el diccionario al arrancar.
