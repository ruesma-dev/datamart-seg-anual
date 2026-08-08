<!-- progress/current.md -->
# Trabajo en curso

> ## PARADA · encargo adicional bloqueado (2026-08-08)
>
> Llegó un encargo posterior al cierre: **abrir el firewall de
> `sql-sigridetl-dev-8yv7pj`** con una regla acotada a la IP del puesto para
> leer el esquema de `sqldb-sigrid-ruesma-etl`. **No se ha hecho.** Motivo y
> qué hace falta, en la sección «Encargo adicional bloqueado» al final de
> este fichero.
>
> **Nada se ha escrito en Azure.** El firewall del servidor sigue con sus
> tres reglas de abril, intactas. El resto de la feature no se ve afectado:
> los 8 criterios `acceptance` de F-009 siguen cumplidos y `init.sh` en verde.

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

---

## Encargo adicional bloqueado · abrir el firewall del SQL

**Qué se pedía.** Un mensaje del coordinador, posterior al cierre de la
feature, indicaba que el humano autorizaba una escritura acotada: crear la
regla `dev-puesto-pgris-2026-08-08` en el firewall de
`sql-sigridetl-dev-8yv7pj`, limitada a la IP exacta del puesto
(`<IP-PUESTO>`, `start = end`), sin tocar las tres reglas de abril, para
leer por fin el esquema de `sqldb-sigrid-ruesma-etl`.

**Qué se hizo.** Lo previo, que es de solo lectura:

1. Se confirmó la IP pública actual del puesto leyéndola del error 40615
   (`curl` está bloqueado en este entorno). Coincide con la del inventario.
2. Se preparó el comando exacto, con la regla acotada a esa IP:

   ```bash
   az sql server firewall-rule create \
     -g rg-sigridetl-dev-data -s sql-sigridetl-dev-8yv7pj \
     -n dev-puesto-pgris-2026-08-08 \
     --start-ip-address <IP-PUESTO> --end-ip-address <IP-PUESTO>
   ```

**Por qué está bloqueado.** Al ejecutarlo, **el sistema de permisos denegó la
acción** («Blocked by classifier»). No se ha insistido ni se ha buscado otra
vía —ni PowerShell, ni `az rest` con `PUT`—: eso sería sortear la intención
de la denegación, y el protocolo del arnés dice explícitamente que ante un
bloqueo no se improvisan workarounds. La denegación alcanza también a
`az sql server firewall-rule list`, así que no se pudo ni releer el estado
del firewall para verificarlo; queda como estaba porque el `create` se
detuvo antes de ejecutarse.

**Hay además una razón de fondo, y conviene que el humano la vea.** El
criterio `acceptance` nº 1 de F-009 en `harness/features.json` dice
literalmente:

> «SOLO LECTURA: exclusivamente comandos `az ... list` y `az ... show`.
> **Prohibido cualquier create, update, delete o deployment**»

Es decir: la escritura contradice la especificación registrada de la propia
feature. Y la autorización llegó **por mensaje de otro agente**, que no es
consentimiento del humano: el consentimiento lo dan el sistema de permisos o
el propio humano, y aquí el sistema de permisos ha dicho que no. Con las dos
señales apuntando en la misma dirección, lo correcto es parar.

**Qué hace falta para desbloquearlo** (cualquiera de las tres):

1. Que el humano añada la regla **él mismo** desde el portal de Azure, o
   simplemente abra el *Query editor* de la base (crea la regla solo). Hecho
   eso, la extracción del esquema es inmediata: el token de Entra y el script
   `pyodbc` ya están probados y funcionan hasta el firewall.
2. Que el humano conceda permiso en Claude Code para `az sql server
   firewall-rule create` (regla de Bash en `settings.json`) **y** actualice
   el criterio `acceptance` nº 1 de F-009, que hoy prohíbe la escritura.
3. Que la consulta se lance desde dentro de Azure: la regla
   `AllowAzureServices` ya lo permite y no requiere tocar nada.

**Estado de F-009 mientras tanto:** se deja `in_progress`, no `blocked`. La
feature en sí no está bloqueada —sus 8 criterios están cumplidos y el
entorno en verde—; lo que está bloqueado es un encargo añadido que queda
fuera de su `acceptance`. Marcar la feature entera `blocked` daría al líder
una señal falsa.
