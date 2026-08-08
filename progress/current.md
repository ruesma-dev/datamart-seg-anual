<!-- progress/current.md -->
# Trabajo en curso

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

- **Esquema de `sqldb-sigrid-ruesma-etl`: NO obtenido.** El firewall del
  servidor no incluye la IP de salida actual del puesto. Añadirla es una
  escritura y queda fuera del alcance. Detalle de los intentos y del error en
  el documento (§2.5) y en el informe.
- Conectarse disparó la **reanudación automática** de la base *serverless*
  (`Paused` → `Online`). No se escribió nada; se auto-pausa a los 60 min. Los
  datos del diagnóstico se capturaron antes de conectar.
- No se pudo listar el contenido de blobs: falta rol de plano de datos
  (`Storage Blob Data Reader`). No se usó `--auth-mode key` para no recuperar
  la clave de la cuenta.
