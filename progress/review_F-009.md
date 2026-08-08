<!-- progress/review_F-009.md -->
# Review · F-009 · Inventario del entorno Azure existente

Rama `feature/F-009-inventario-azure`. Feature `sdd=false`: se valida contra
los 8 criterios `acceptance` de `harness/features.json` y contra
`CHECKPOINTS.md`.

Fecha de la review: 2026-08-08.

---

## Veredicto

**CHANGES_REQUESTED**

Un único bloqueo, en C3 bis, y es de dos líneas: la cabecera del inventario
declara **tres** nombres de recurso redactados y en el cuerpo hay **cuatro**.
El cuarto (`<GUID>`) no está anotado en el bloque «Redactado».

**Todo lo demás está aprobado**, incluida la parte más delicada: el barrido
de datos sensibles salió **limpio en todos los patrones** y la excepción de
escritura está declarada de forma visible, honesta y **verificada por mí
contra Azure**. El trabajo es de calidad alta y de una exactitud poco común
—cada dato que he podido contrastar contra la suscripción real ha coincidido
exactamente—. No estoy rechazando el fondo, sino cerrando una inconsistencia
en el único bloque del documento cuya función es garantizar que no falta
nada por declarar.

---

## Checkpoints

### C1 — El arnés está completo y en verde

- [x] `bash harness/init.sh` termina con exit code 0. Ejecutado por mí:
      22 tests pasan, `ENTORNO LISTO`. (Aviso de `ruff`: 122, deuda previa
      declarada como no bloqueante por el propio script.)
- [x] Existen `CLAUDE.md`, `harness/features.json`, `specs/SPECS.md`,
      `progress/current.md`, `progress/history.md`, `docs/ARCHITECTURE.md`,
      `docs/CONVENTIONS.md`. Verificado por `init.sh`.

### C2 — El estado es coherente

- [x] Una sola feature `in_progress`: F-009. Verificado en `features.json` y
      por `init.sh` (`en curso: ['F-009']`).
- [x] Rama actual `feature/F-009-inventario-azure`, coincide con el campo
      `branch` de la feature. No es `main` ni `dev`.
- [x] `progress/current.md` describe solo la sesión de F-009. Sin restos de
      sesiones anteriores.
- [x] Las dos features `done` (F-001, F-008) tienen su resumen en
      `progress/history.md` (líneas 8 y 35).

### C3 — El código respeta arquitectura y convenciones

- [x] **N/A justificado.** La feature no añade ni modifica una sola línea de
      código. El diff de la rama toca 6 ficheros: un documento nuevo en
      `docs/referencia/`, una línea de índice en su `README.md`, tres ficheros
      de `progress/` y una línea de estado en `features.json`. No hay Python,
      ni SQL, ni dependencias nuevas, luego los cuatro sub-checkboxes de C3
      (dominio sin infraestructura, primera línea con ruta, `print()` de
      debug, semántica Sigrid) no tienen objeto sobre el que aplicarse.

  Comprobado además que **no se han introducido secretos**: ver C3 bis.

### C3 bis — Los documentos que entran de fuera son seguros

- [x] **Cabecera con origen y fecha.** Presente en las líneas 4-7, con la
      estructura del «Caso 2» de `docs/referencia/README.md`: origen
      (`inventario ejecutado con az [...] sobre la suscripción «Ruesma»`),
      fecha, «Incorporado a `docs/referencia/` el 2026-08-08» y «Llegó ya en
      Markdown: no requirió conversión con `markitdown`». Las dos últimas
      líneas son literales de la plantilla. Correcto. (Ver la observación
      no bloqueante nº 1 sobre el rótulo de la fecha.)

- [x] **Los originales no están en el repositorio ni en el árbol.**
      Verificado en tres pasadas:
      - `git log --diff-filter=A` sobre la rama: los únicos ficheros añadidos
        son `docs/referencia/04_azure_inventario_dev.md` y
        `progress/impl_F-009.md`. Ninguno binario.
      - `git log --all --diff-filter=A` sobre **todo** el historial filtrando
        `.pdf|.docx|.xlsx|.pptx`: **cero resultados**. No basta con que no
        estén ahora y no lo están tampoco en el pasado.
      - `find` sobre el árbol de trabajo: ningún fichero ofimático.
      - `git status --porcelain --untracked-files=all`: **vacío**.

      Aplica con holgura: este documento se redactó directamente en Markdown,
      no hubo conversión, luego no hay original que pueda haberse colado.

- [x] **Barrido de datos sensibles ejecutado por mí.** Resultado y patrones
      en la sección «Barrido» de abajo. **Limpio.**

- [ ] **Lo que se haya redactado está anotado en la cabecera.** **FALLA.**
      Es el único checkbox vacío del informe. Motivo y arreglo en «Cambios
      requeridos» nº 1: se han redactado cuatro nombres de recurso y la
      cabecera declara tres.

### C4 — La verificación es real

- [x] **N/A justificado por escrito**, como exige la nota de `CHECKPOINTS.md`
      para features `sdd=false`. La justificación consta en
      `progress/impl_F-009.md` §6 y la comparto:

  > «la feature no añade código. Su entregable es un documento cuyo contenido
  > es el estado de una suscripción externa; un test que lo comprobara tendría
  > que llamar a Azure, lo que viola la regla de que los tests no tocan red.»

  **Lo doy por bueno.** Un `test_f009_rN_*` sobre este entregable solo podría
  hacer dos cosas: o afirmar el estado de Azure —y entonces toca red, contra
  la regla explícita de `CLAUDE.md` y contra el segundo sub-checkbox de este
  mismo C4—, o comprobar que el fichero Markdown existe y tiene ciertas
  cadenas, que es un test tautológico que no verifica nada real. El N/A no es
  una excusa: es la respuesta correcta. La verificación de esta feature es
  documental y de contraste, y la he ejecutado yo contra la suscripción.

- [x] Los unit tests no tocan red ni BBDD. La suite existente (22 tests) no
      se ha modificado y sigue en verde.

- [x] Las verificaciones `MANUAL (humano)` están en `progress/current.md`
      líneas 48-59, con sus comandos exactos (`az group list`, `az acr list`,
      `az sql db show`), pendientes de que el humano las ejecute. Los tres son
      de lectura.

### C5 — La sesión se cerró bien

- [x] `tasks.md`: **N/A justificado.** Feature `sdd=false`, no hay
      `specs/F-009-*/`, tal y como prevé la nota de `CHECKPOINTS.md`. El
      formato mínimo de commit que exige esa nota para `sdd=false` es
      `F-XXX: <descripción>` y **los seis commits de la rama lo cumplen**:

      ```
      f3ee7c3 F-009: esquema real de sqldb-sigrid-ruesma-etl y que era aquel ETL
      c329bf4 F-009: registrar el bloqueo del encargo de abrir el firewall del SQL
      047c450 F-009: informe de implementacion y estado de la sesion
      27e2e57 F-009: actualizar decisiones abiertas con el inventario real de Azure
      32a59ec F-009: inventario del entorno Azure existente en docs/referencia/
      ca1146c F-009: abrir feature de inventario de Azure
      ```

- [x] Sin ficheros temporales ni artefactos sin trackear.
      `git status --porcelain --untracked-files=all` **vacío**. El implementer
      instaló `pyodbc` con `pip install --target` en el scratchpad de sesión,
      fuera del árbol: `requirements.txt` no cambia y el diff lo confirma.
- [x] `features.json` refleja el estado real: F-009 `in_progress`, a la espera
      de que el cierre lo haga quien corresponda tras esta review.

---

## Barrido de datos sensibles (C3 bis) — ejecutado por el reviewer

Ejecutado por mí sobre `docs/referencia/04_azure_inventario_dev.md`, sin
apoyarme en el barrido declarado en `progress/impl_F-009.md` §5. Patrones
usados y resultado literal:

| # | Qué busca | Patrón (`grep -nEo`) | Resultado |
|---|---|---|---|
| 1 | GUID (suscripción, tenant, objectId) | `[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}` | **0 coincidencias** |
| 2 | GUID sin guiones / hash / hex largo | `\b[0-9a-fA-F]{32,}\b` | **0 coincidencias** |
| 3 | IPv4 | `\b([0-9]{1,3}\.){3}[0-9]{1,3}\b` | **1**: `0.0.0.0` (línea **196**). Es el centinela de la regla `AllowAzureServices` de Azure, no una dirección real. Aceptable. |
| 4 | CIDR / rangos de red | `\b([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}\b` | **0 coincidencias** |
| 5 | IPv6 | `\b([0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b` | **11 coincidencias, todas falsos positivos**: son marcas de hora `HH:MM:SS` de las tablas de fechas de creación (líneas 100-107, 178, 179, 244). Ninguna es una dirección. |
| 6 | Correos | `[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}` | **0 coincidencias** |
| 7 | Token / base64 / clave (≥40) | `[A-Za-z0-9+/_=-]{40,}` | **0 coincidencias** |
| 8 | Asignación clave=valor con valor real | `(password\|pwd\|secret\|token\|key)\s*[:=]\s*[^ *<\|]{6,}` (`-i`) | **0 coincidencias** |
| 9 | SAS, firmas, claves de cuenta, PEM | `AccountKey\|SharedAccessSignature\|sig=\|sv=20\|BEGIN (RSA\|PRIVATE)` (`-i`) | **0 coincidencias** |
| 10 | Cualquier `@` (correo camuflado) | `@` | **0 coincidencias** |
| 11 | FQDN de endpoints | `\.(database\.windows\.net\|azurecr\.io\|vault\.azure\.net\|blob\.core\.windows\.net\|azurewebsites\.net)` | **3**: `sql-sigridetl-dev-8yv7pj.database.windows.net` (173) y `acralbaranesdev.azurecr.io` (615, 743). Son **nombres de recurso públicos**, no secretos, y su publicación es justo lo que pedía el encargo (D2). Aceptable. |

**Conclusión del barrido: limpio.** No hay ID de suscripción, ni de tenant,
ni IPs, ni rangos de red, ni correos, ni valores de secreto en el documento.
Se cumple el criterio `acceptance` nº 5.

**Sobre las ~25 coincidencias de `password|secret|token|key|...`:** las revisé
una a una y **todas son nombres, nunca valores** — nombres de secretos de Key
Vault (`PG-PASSWORD`, `SIGRID-API-FUNCTION-KEY`…), nombres de app settings
marcados explícitamente *(no volcados)*, y prosa sobre el propio método
(`SQL_COPT_SS_ACCESS_TOKEN`). Listar nombres de secretos sin sus valores es
exactamente lo que pedía el criterio nº 3. Correcto.

**Sobre `ruesma.es` (línea 50):** es el dominio del tenant, no un correo.
Coincido con el criterio del implementer: es el dominio público de la empresa
y ya figura en la configuración de git del repositorio. **No lo considero un
defecto** y no pido cambiarlo.

**Nota menor:** el implementer sitúa `0.0.0.0` en la línea 183 y `ruesma.es`
en la 43; hoy están en la 196 y la 50. La diferencia es simplemente que el
documento creció con la §2.5 después de aquel barrido. No es un error.

---

## Punto 2 del encargo — La excepción al `acceptance` nº 1, verificada

Mi trabajo aquí no es juzgar la autorización (la dio el humano), sino
comprobar que está **declarada de forma visible y honesta** y que **los hechos
declarados son ciertos**. Lo he verificado contra Azure, no contra el informe.

### ¿Está declarada donde debe? Sí, en cuatro sitios

| Dónde | Líneas | Visibilidad |
|---|---|---|
| `docs/referencia/04_azure_inventario_dev.md`, cabecera «Por qué está aquí» | 38-44 | Bloque destacado, antes de la sección 1 |
| `docs/referencia/04_azure_inventario_dev.md` §2.5 | 203-220 | Recuadro `⚠` con título «léase antes que la sección» |
| `progress/impl_F-009.md` §4, «Adenda 2» | 197-212 | Encabezado `⚠ Excepción al acceptance nº 1, declarada` |
| `progress/current.md` | 4-19 | **Lo primero del fichero**, antes incluso del título de la feature |

Es imposible no verla. Cumple de sobra el listón que me marcaba el encargo
(«que el reviewer la vea sin buscarla»). Además la declaración es honesta en
lo incómodo: dice explícitamente que **contradice** el criterio `acceptance`
nº 1, en vez de reinterpretarlo.

### ¿Los hechos declarados son ciertos? Sí, verificado contra Azure

Ejecuté yo las lecturas (`az sql server firewall-rule list` / `show`, ambas
de solo lectura):

| Lo que declara | Lo que encuentro | ¿Coincide? |
|---|---|---|
| Se creó **una sola** regla, `dev-puesto-pgris-2026-08-08` | El servidor tiene **4 reglas**: `AllowAzureServices`, `AllowLocalDev-20260417`, `QueryEditorClientIPAddress_...` y `dev-puesto-pgris-2026-08-08` | **Sí** |
| **Las tres de abril no se tocaron** | Las tres siguen ahí, con sus nombres originales | **Sí** |
| Acotada a **una única IP** (`start = end`) | `startIpAddress == endIpAddress` → **`True`** | **Sí** |
| **Sigue puesta** | Sigue puesta | **Sí** |

*(No reproduzco aquí las direcciones: sería exactamente lo que el barrido
trata de evitar.)*

### Punto 3 — ¿Hubo alguna otra escritura? No he encontrado ninguna

- **Estado de los recursos.** El único cambio de estado atribuible a la sesión
  es la regla de firewall, más la reanudación automática de la base
  *serverless* —que el propio documento declara y que no es una escritura
  ordenada, sino el comportamiento por diseño del tier ante cualquier lectura.
- **Log de actividad.** `az monitor activity-log list` desde el 2026-08-08
  devuelve **4 eventos en toda la suscripción**, y los cuatro son
  `Microsoft.Storage/storageAccounts/ListServiceSas/action` sobre
  `stoalzmgmspa001owvp`, la cuenta del **estado de Terraform de acens**: es su
  pipeline automático, no esta sesión. **Ninguna operación de `write`,
  `delete` o `deployment` atribuible al arnés.**
- **Salvedad de método, que debo declarar:** el `create` de la regla de
  firewall **tampoco** aparece en ese log, pese a que la regla existe. Es
  latencia de ingesta del activity log. Por tanto el log **corrobora pero no
  prueba** la ausencia de otras escrituras; la evidencia fuerte es el estado
  directo de los recursos, que sí he leído. Con lo que tengo, **no hay
  indicio alguno de ninguna otra escritura**, y sí hay evidencia positiva de
  que las tres reglas preexistentes están intactas.

### Lo que el humano tiene pendiente

**La regla `dev-puesto-pgris-2026-08-08` sigue activa en
`sql-sigridetl-dev-8yv7pj`.** Mientras exista, esa IP alcanza el servidor.
Retirarla es otra escritura y no está autorizada, así que **queda a decisión
del humano**. Está correctamente escalado en `current.md` (línea 84) y en
`decisiones_abiertas.md` (D7, pregunta 3). No es un defecto de la feature:
es la consecuencia esperada, bien señalizada.

---

## Punto 4 del encargo — Coherencia temporal del documento

**Correcto, y además comprobado empíricamente.** El documento avisa (§2.5,
líneas 241-247) de que conectarse disparó la reanudación automática de la
base, que los valores forenses se capturaron **antes** de conectar, y que
*«si el reviewer repite `az sql db show` verá otros valores: es esperado y
esta es la explicación»*.

Lo repetí. Efectivamente:

| Campo | Documentado (foto previa) | Lo que veo ahora |
|---|---|---|
| `status` | (pausada) | `Online` |
| `pausedDate` | `2026-04-18T04:15:50Z` | `null` |
| `resumedDate` | `null` | `2026-08-08T16:03:43Z` |

El `resumedDate` que veo coincide **al segundo** con el que el documento
anticipó. Esto es lo contrario de un problema: es un aviso predictivo que se
cumple, y descarta que nadie haya tocado la base entre medias. Un lector
futuro no confundirá la foto con el estado permanente, porque la cabecera fija
«Fecha del inventario: 2026-08-08» y §2.5 explica el efecto colateral.

*(Mejora opcional, no bloqueante: ver observación nº 2.)*

---

## Cobertura de los criterios `acceptance`

| # | Criterio | Veredicto | Evidencia |
|---|---|---|---|
| 1 | SOLO LECTURA, prohibido create/update/delete/deployment | **Cumplido con excepción declarada y autorizada** | Una escritura: la regla de firewall. Declarada en 4 sitios y verificada por mí contra Azure. Ninguna otra escritura detectada. |
| 2 | Existe `04_azure_inventario_dev.md` con la cabecera de `README.md` | **Cumplido, con el defecto nº 1** | Cabecera «Caso 2» correcta (líneas 4-7) + bloque «Redactado» (9-24). El bloque declara tres nombres redactados y hay cuatro. |
| 3 | Cubre RGs, VNets, peerings, subredes, VPN y estado, Firewall, storages, Key Vaults, ACR, Postgres y el contenido de `rg-seguimiento-dev` y `rg-sigrid-dev-data-api` | **Cumplido** | §1 (17 RG), §3.1-3.2, §3.3 (VPN `Connected`), §3.4, §4.1 (8 storages), §4.2 (4 KV), §5.1 (1 ACR), §5.3 (1 Postgres, 1 SQL). `rg-sigrid-dev-data-api` en §1. `rg-seguimiento-dev` **no existe** y se documenta como tal (§6.3) en vez de inventarse: es la respuesta correcta. **Verificado**: `az group exists -n rg-seguimiento-dev` → `false`. |
| 4 | Contrasta con `02_azure_landing_zone_acens.md` y señala diferencias | **Cumplido** | §6.1 (10 elementos que se cumplen) y §6.2 (7 diferencias, con la VPN P2S inexistente y los cero private endpoints a la cabeza). |
| 5 | Sin ID de suscripción, sin IPs internas, sin secretos; redactado como el resto | **Cumplido** | Barrido propio: limpio en los 11 patrones. |
| 6 | Responde a D2 y aporta a D1, D3 y la storage de D5 | **Cumplido** | §7. D2 respondida en el dato. **Verificado**: `az acr list` → un único ACR, `acralbaranesdev`, Basic, `adminUserEnabled=False`. Coincide exactamente. |
| 7 | `decisiones_abiertas.md` actualizado | **Cumplido** | D1, D2, D3, D5, D6 con material nuevo; D7 nueva. Ver punto 6 abajo. |
| 8 | `bash harness/init.sh` en verde | **Cumplido** | Ejecutado por mí: exit 0, 22 tests. |

---

## Punto 6 del encargo — ¿Cierra decisiones por su cuenta?

**No. Correcto.** Revisadas una a una en `progress/decisiones_abiertas.md`:

| Decisión | Qué aporta | ¿Cierra? |
|---|---|---|
| **D1** | Precedente real (opción A ya en uso en `psql-albaranes-rs9k2`), cero private endpoints, VPN P2S no configurada | **No.** Cierra con *«Sigue abierta: es una decisión de criterio (exposición vs. coste de red) que el humano tiene que tomar. El inventario solo acota el terreno.»* |
| **D2** | El dato pedido: `acralbaranesdev`, Basic, admin deshabilitado | **No.** *«Qué falta (criterio del humano): decidir entre (a) reutilizar [...] o (b) crear un ACR propio.»* Distingue con precisión «dato resuelto» de «decisión cerrada». |
| **D3** | Spoke PROD vacío, no hay STA, todo en `-dev` | **No.** *«Sigue abierta: decisión de alcance del humano.»* |
| **D5** | Las 8 storages, ninguna es «la del datamart»; los Excels no están en Azure | **No.** Da tres opciones (a/b/c) y añade *«sigue sin respuesta quién mantiene los ficheros»*. Declara además la limitación de permisos de plano de datos. |
| **D6** | El ETL anterior corría a las 02:30 y sin alertas | **No.** Explícito: *«Dato de contexto, no cierra la decisión.»* |
| **D7** (nueva) | Todo el hallazgo de `rg-sigridetl-dev-data` | **No.** Plantea **4 preguntas** al humano, incluida la retirada de la regla de firewall. |

La cabecera del fichero lo dice de frente (líneas 11-14): *«No cierra ninguna
por su cuenta: todas las que quedan requieren criterio del humano.»* Es
exactamente la conducta que pedía el encargo. **Aprobado sin reservas.**

---

## Punto 7 del encargo — `features.json`

**Correcto.** El diff de `harness/features.json` contra `dev` es de **una sola
línea**:

```diff
-      "status": "pending",
+      "status": "in_progress",
```

dentro del bloque de F-009. **F-003 y F-005 no se han tocado**, ni sus
`blocked_by_decisions`, ni su prioridad, ni su descripción — pese a que el
inventario da argumentos de peso para replantear ambas. El implementer lo
registra como decisión consciente en su §1 y en §6.3 del documento
(*«queda documentado, no resuelto»*). Es la disciplina correcta.

---

## Contraste independiente de los datos del inventario

Comprobé una muestra de afirmaciones verificables. **Todas exactas:**

| Afirmación del documento | Mi verificación | ¿Coincide? |
|---|---|---|
| Único ACR: `acralbaranesdev`, Basic, admin deshabilitado (§5.1) | `az acr list` | **Sí** |
| `rg-seguimiento-dev` no existe (§6.3) | `az group exists` → `false` | **Sí** |
| Ningún Container Apps Job en la suscripción (§5.2) | `az containerapp job list` → 0 | **Sí** |
| Base creada 2026-04-17 08:23:32 UTC (§2.4) | `creationDate` idéntico | **Sí** |
| Tamaño máximo 20 GB, SKU `GP_S_Gen5_1` (§2.4) | `21474836480` B y `GP_S_Gen5_1` | **Sí** |
| `pausedDate = 2026-04-18T04:15:50Z` capturado antes de conectar (§2.5) | Coherente: hoy `resumedDate = 2026-08-08T16:03:43Z`, el valor exacto que el documento anticipó | **Sí** |
| Líneas citadas de `infra/00_vars.ps1` (5, 6, 7, 9, 14, 15, 19) | Las siete exactas, incluido `$SUB` con el ID en claro | **Sí** |
| `config/tables_sigrid.yaml` declara 31 tablas (§2.6) | `grep -c source_table` → **31** | **Sí** |
| Solo 6 tablas coinciden; 14 solo en Azure; 25 solo aquí (§2.6) | Verificada la intersección completa contra las 31 del YAML: las 6 están, las 14 no, y 31−6 = 25, con la lista literal correcta | **Sí** |

Que la aritmética de conjuntos de §2.6 cuadre al detalle, y que el
`resumedDate` anticipado coincida al segundo, son buenos indicadores de que
el resto del inventario —lo que no puedo contrastar sin repetirlo entero— está
tomado con el mismo cuidado.

---

## Cambios requeridos

Uno solo, y es de dos líneas.

### 1. La cabecera declara tres nombres de recurso redactados; hay cuatro

**Fichero:** `docs/referencia/04_azure_inventario_dev.md`
**Líneas del defecto:** 17-21 (la declaración) contra la línea 72 (el caso no
declarado).

La cabecera afirma:

> «Los **nombres de recursos se conservan** [...]. **Única excepción, tres
> nombres** que llevan un dato sensible incrustado y se redactan dentro del
> propio nombre: la conexión y el gateway local de la VPN (contienen la IP
> pública de la sede) y el workspace por defecto de Defender (contiene el ID
> de suscripción).»

Enumerados en el cuerpo hay **cuatro** nombres redactados, no tres:

| Línea | Nombre redactado | ¿Declarado en la cabecera? |
|---|---|---|
| 70 | `DefaultWorkspace-<ID-SUSCRIPCION>-ESC` | Sí (workspace de Defender) |
| 527 | `cn-<IP-PUBLICA-SEDE>-remota` | Sí (conexión VPN) |
| 530 | `<IP-PUBLICA-SEDE>-remota` | Sí (gateway local) |
| **72** | **`VisualStudioOnline-<GUID>`** | **No** |

El marcador `<GUID>` de la línea 72 —el identificador de la organización de
Azure DevOps, que Azure incrusta en el nombre del resource group— **no aparece
en ninguna parte del bloque «Redactado»** (líneas 9-24), que enumera
`<ID-SUSCRIPCION>`, `<ID-TENANT>`, `<RANGO-*>`, `<SUBRED-*>`, `<IP-*>`,
`<usuario-admin>` y `<usuario-admin-sql>`, pero no `<GUID>`.

**Por qué lo bloqueo, siendo tan pequeño.** La redacción en sí está **bien
hecha** —el GUID no se publica, el documento es más seguro, no menos—. Lo que
falla es la **declaración**. El bloque «Redactado» es el único punto del
documento cuya función es responder a «¿está todo lo redactado declarado
aquí?», y ahora mismo contiene un recuento numérico explícito («tres») que es
falso. Un lector que audite el documento en el futuro usará esa frase como
garantía de completitud, y la garantía no se sostiene. Es exactamente el
cuarto checkbox de C3 bis: *«Lo que se haya redactado está anotado en la
cabecera del documento.»*

**Arreglo propuesto** (línea 18, cambiar «tres» por «cuatro» y añadir el
cuarto caso):

```markdown
> Los **nombres de recursos se conservan**: son identificadores operativos y
> ya figuran en el repositorio. **Cuatro excepciones**, nombres que llevan un
> dato sensible incrustado y se redactan dentro del propio nombre: la
> conexión y el gateway local de la VPN (contienen la IP pública de la sede),
> el workspace por defecto de Defender (contiene el ID de suscripción) y el
> resource group de Azure DevOps (contiene el identificador de la
> organización, `<GUID>`).
```

No hace falta tocar nada más del documento.

---

## Observaciones no bloqueantes

Ninguna de estas impide el cierre. Las dejo por si se quieren aprovechar en
la misma pasada que el cambio nº 1.

**1. Rótulo de la fecha en la cabecera (línea 5).** La plantilla del «Caso 2»
de `docs/referencia/README.md` fija `Fecha del documento: AAAA-MM-DD` y dice
que *«la primera línea del bloque de origen es siempre la misma»*. Este
documento escribe `Fecha del inventario: 2026-08-08`. La sustancia exigida
—origen y fecha— está, y el rótulo elegido es de hecho **más preciso** para un
documento que *es* la toma de datos, no un original externo. Los tres
documentos hermanos (01, 02, 03) usan `Fecha del documento`. **No lo pido como
cambio**, pero conviene decidir si se homogeneiza el rótulo o se añade a
`README.md` una variante para documentos generados en casa, que es lo que
este es. Es el primer documento de `docs/referencia/` que no viene de fuera, y
la plantilla no lo contemplaba.

**2. Un dato caducado en §2.4 (línea 179).** La tabla dice «**Pausada desde**
| **2026-04-18 04:15:50 UTC**», que a día de hoy ya no es cierto (la base
está `Online`). La salvedad está muy bien explicada, pero **en §2.5**, es
decir *después*. Un lector que consulte solo la tabla de §2.4 se lleva un dato
obsoleto sin el aviso. Bastaría añadir en esa celda «*(foto del 2026-08-08
previa a la conexión; ver §2.5)*». Mejora de robustez, no un error: el
documento ya declara el efecto, solo que un párrafo más abajo.

**3. Para el humano, fuera del alcance de F-009 pero conviene verlo.** El
propio inventario lo señala en §6.3 y lo confirmo: **`infra/00_vars.ps1:5`
tiene el ID de suscripción escrito en claro y versionado en el repositorio.**
Es **preexistente**, no lo introduce esta feature, y el implementer hizo bien
en no tocarlo (F-003 no se toca). Pero es el tipo de dato que el resto del
proyecto se está tomando la molestia de redactar en `docs/referencia/`, así
que hay una incoherencia entre el rigor del documento y el del código. Merece
una tarea propia.

**4. También para el humano**, del §8 del informe del implementer y de §4.1
del documento: `stsigridapidevhuyke` permite **acceso público a blobs**;
ninguna de las 8 storage accounts ni ninguno de los 4 Key Vaults restringe el
acceso por red; y la base `sqldb-sigrid-ruesma-etl` contiene **datos
personales y bancarios** (`stg.age` con `ban`/`bancue`/`cif`, `stg.res` con
`cif`/`recema`) con acceso público habilitado, en un RG etiquetado
`acens-compliance=gdpr`. El documento lo escala correctamente a D7. **No es
responsabilidad de esta feature resolverlo, pero sí conviene que no se pierda
de vista.**

---

## Qué hay que hacer para cerrar

1. Aplicar el cambio nº 1 (dos líneas en la cabecera de
   `docs/referencia/04_azure_inventario_dev.md`).
2. Commit `F-009: declarar el cuarto nombre redactado en la cabecera`.
3. Nueva review. No hace falta repetir el barrido completo: lo daré por
   válido salvo que cambie el cuerpo del documento.

Todo lo demás de esta feature está aprobado.

---

## Automejora (propuesta, no aplicada)

Dos cosas que esta review ha dejado ver, para que el humano decida:

1. **`docs/referencia/README.md` no contempla documentos generados en casa.**
   Sus dos casos son «llegó en PDF y se convirtió» y «llegó ya en Markdown».
   `04_azure_inventario_dev.md` no es ninguno de los dos: **se produjo aquí**,
   tomando datos de un sistema vivo. De ahí la fricción de la observación nº 1.
   Propongo añadir un **«Caso 3 — generado en este proyecto a partir de un
   sistema vivo»**, con `Fecha de la toma de datos: AAAA-MM-DD` y la exigencia
   explícita de **declarar la caducidad del dato** (que es justo lo que la
   observación nº 2 echa en falta). Habrá más documentos así.

2. **`CHECKPOINTS.md` C3 bis no dice qué hacer con una excepción autorizada al
   alcance.** Aquí funcionó porque el implementer y el líder fueron
   escrupulosos por iniciativa propia, no porque el protocolo lo exigiera.
   Propongo un quinto checkbox en C3 bis, o una sección nueva:

   > - [ ] Si la feature ejecutó alguna acción **fuera del alcance declarado**
   >       en su spec o en sus `acceptance`, consta por escrito **qué se hizo,
   >       quién lo autorizó, qué alcance tuvo y si el efecto sigue vigente**,
   >       y el reviewer lo ha **verificado contra el sistema afectado**, no
   >       solo contra el informe.

   La feature ha demostrado que el caso ocurre; conviene que el listón no
   dependa del criterio de quien la implemente.
