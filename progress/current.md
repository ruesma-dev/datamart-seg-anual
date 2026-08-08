<!-- progress/current.md -->
# Trabajo en curso

> ## ⚠ Excepción al alcance de solo lectura — el reviewer tiene que verla
>
> Para leer el esquema de `sqldb-sigrid-ruesma-etl` se creó la regla de
> firewall **`dev-puesto-pgris-2026-08-08`** en `sql-sigridetl-dev-8yv7pj`,
> acotada a una única IP (`start = end`). Las tres reglas de abril no se
> tocaron y no hubo ninguna otra escritura.
>
> La hizo el **líder**, con **autorización expresa y directa del humano**.
> Cuando el implementer lo intentó, el sistema de permisos lo denegó y paró.
>
> Esto **contradice el criterio `acceptance` nº 1 de F-009**, que prohíbe
> cualquier `create`. Está declarado en `docs/referencia/04_azure_inventario_dev.md`
> §2.5 y en `progress/impl_F-009.md`.
>
> **La regla sigue puesta.** Borrarla es otra escritura y no está autorizada:
> **el humano decide si la retira.**

**F-009 · Inventario del entorno Azure existente** (`sdd=false`, solo
lectura). Implementación terminada, pendiente de review.

Rama: `feature/F-009-inventario-azure`. Informe:
`progress/impl_F-009.md`. Entregable:
`docs/referencia/04_azure_inventario_dev.md`.

## Estado

- Inventario completo de la suscripción «Ruesma» tomado con `az`: 17 resource
  groups, 99 recursos. Documento redactado (sin IDs, IPs ni secretos) y
  barrido de datos sensibles ejecutado, resultado en el informe.
- `progress/decisiones_abiertas.md` actualizado: material nuevo para D1, D2,
  D3, D5 y D6, y una decisión nueva **D7**. Ninguna cerrada por cuenta propia.
- `bash harness/init.sh` en verde.
- `features.json`: F-009 sigue `in_progress` (la cierra el reviewer). F-003 y
  F-005 **no se han tocado**, por instrucción expresa.

## Hallazgos que el humano tiene que ver

1. **`rg-sigridetl-dev-data` es un intento anterior de este mismo ETL**
   (Azure Functions + Azure SQL, creado 2026-04-17, desactivado, base pausada
   desde 2026-04-18 pero con ~174 MB de datos). Abre **D7**.
2. **`rg-seguimiento-dev` no existe.** `infra/00_vars.ps1` da por existentes
   recursos que no están: el RG, el Container Apps environment y el job.
3. **D2 respondida en el dato**: el único ACR es `acralbaranesdev`.

## Verificación MANUAL (humano) — pendiente

Todo el inventario es de solo lectura y no admite test automático. Para
reproducirlo, la sección 8 del documento lista los comandos exactos. Los tres
que más conviene contrastar a ojo:

```bash
az group list -o table
az acr list --query "[].{name:name, rg:resourceGroup, sku:sku.name}" -o table
az sql db show -g rg-sigridetl-dev-data -s sql-sigridetl-dev-8yv7pj \
  -n sqldb-sigrid-ruesma-etl --query "{status:status, pausedDate:pausedDate}"
```

## Salvedades registradas

- **Esquema de `sqldb-sigrid-ruesma-etl`: OBTENIDO.** Ver
  `docs/referencia/04_azure_inventario_dev.md` §2.5 (esquema) y §2.6
  (interpretación). Hizo falta la regla de firewall declarada arriba; los
  tres intentos previos fallidos quedan documentados como nota de método.
- **No se leyó el contenido de `etl.etl_run` (6 filas) ni de
  `etl.etl_table_run` (22)**, por la instrucción de no volcar tablas. Son la
  lectura pendiente de más valor: dirían por qué se paró aquel ETL. Telemetría
  del propio ETL, no datos de negocio. Basta autorizarlo.
- **⚠ La base contiene datos personales y bancarios** (`stg.age` con `ban` /
  `bancue` / `cif` / `ele`, 198 filas; `stg.res` con `cif` / `recema`, 2.508).
  No se consultó ningún valor: se deduce de los nombres de columna. `emp`
  —con `dni` y `tarseg`— está vacía. Detalle en §2.5.
- Conectarse disparó la **reanudación automática** de la base *serverless*
  (`Paused` → `Online`). No se escribió nada en ella; se auto-pausa a los 60
  min. Los datos del diagnóstico se capturaron antes de conectar.
- No se pudo listar el contenido de blobs: falta rol de plano de datos
  (`Storage Blob Data Reader`). No se usó `--auth-mode key` para no recuperar
  la clave de la cuenta.

## Decisiones pendientes del humano tras esta sesión

1. **¿Se retira la regla `dev-puesto-pgris-2026-08-08`?** Sigue puesta.
2. **¿Se autoriza leer `etl.etl_run` / `etl.etl_table_run`?** Cierra D7.
3. Las demás, en `progress/decisiones_abiertas.md` (D1–D7).
