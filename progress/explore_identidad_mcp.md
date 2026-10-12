# Identidad y permisos en mcp-bbdd (exploración en solo lectura, 2026-10-12)

Contexto: el humano pide acceso TOTAL (contabilidad completa, F-135) para tres personas y el
estándar para el resto. Rutas relativas al repositorio `mcp-bbdd`. Lo escribe el líder a partir
del informe del explorador (que no tenía herramienta de escritura).

## 1. El MCP SÍ sabe quién pregunta
- Easy Auth de Container Apps (Entra ID, `Return401`) delante; además, proxy OAuth propio ante
  Claude (`interface_adapters/oauth/proveedor.py`, `config/config.yaml:272-309`). Sin API key.
- El código lee las cabeceras de la plataforma (`interface_adapters/mcp/identidad.py`):
  `x-ms-client-principal-id` (oid, la clave estable) y `preferred_username` (UPN). Sin oid, la
  consulta se rechaza.
- `IdentidadSolicitante(id_objeto, upn, origen, herramienta)` (`domain/entities.py:146-163`);
  `PasoIdentificar` es el primer paso del pipeline y `ContextoConsulta.identidad` está
  documentado como el punto de enganche de F-008 (`application/pipeline/base.py:35-45`).
- Sin licencia Entra ID P1 no se asignan GRUPOS a la Enterprise App: entra cualquier cuenta del
  tenant (`config/config.yaml:131-133`).

## 2. Un solo login y un solo pool
- `PG_USER = mcp_sigrid_dm_ro`, un `ConnectionPool` para todo el proceso
  (`infrastructure/db/pool.py:40-60`, `fabrica.py:202`), una réplica. Sin conexión por usuario.
- Ningún mecanismo de perfiles: ni lista de usuarios, ni grupos, ni `SET ROLE` (`SET`/`RESET`
  son palabras prohibidas del validador, `config/config.yaml:96-97`).
- `sigrid_dm_restringido_ro` y `contabilidad_restringida` no aparecen en ese repositorio.

## 3. Lista blanca de esquemas GLOBAL
- `config/config.yaml:161-172` (`seguridad.esquemas_permitidos`): mart, cierre, stg, compras,
  maestro, retenciones, personal, contabilidad, descompuestos, aux, _meta. Sin `raw`.
- No mira la identidad (`paso_validar_objetos.py:25`, `servicio_catalogo.py:44,139`).

## 4. F-008 de mcp-bbdd: «Acotar lo que ve cada persona (APLAZADA A PROPÓSITO)»
- `pending`, prioridad 14, rigor crítico, sin spec. Aplazada el 2026-08-25 («de momento todos
  ven todo»). Da por hecho que el oid ya atraviesa las capas y que basta leer
  `contexto.identidad`, filtrando por oid y no por UPN, fail-closed. Deja abierto DE DÓNDE sale
  la política y quién la mantiene. No propone roles de PostgreSQL por usuario.

## 5. Quién lo usa hoy
- Cada acceso deja `usuario=<UPN> id=<oid>` en la auditoría (`application/auditoria/registro.py`),
  a `logs/mcp_bbdd.log` y a stderr (console logs de Log Analytics). El fichero del contenedor
  probablemente se pierde al reiniciar (no verificado contra Azure).
