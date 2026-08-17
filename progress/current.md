<!-- progress/current.md -->
# Trabajo en curso

> ## ⚠ LEE ESTO PRIMERO: `.env` APUNTA A AZURE
>
> Desde el 2026-08-09, `.env` está configurado contra
> **`psql-albaranes-rs9k2`**, el servidor compartido que sirve también a
> `albaranes` y `partes` en producción. **NO** apunta al Postgres local.
>
> Consecuencia inmediata: `check-pg`, `status`, `run-all` y cualquier cosa que
> abra conexión **van contra Azure**. Antes de lanzar nada que escriba,
> asegúrate de que es lo que quieres. Para volver a local, el humano guardó
> copia en `.env.local.bak`.
>
> Los tests de pytest **no** tocan red ni BBDD, así que `harness/init.sh`
> sigue siendo seguro de ejecutar.
>
> Datos útiles de entorno para no redescubrirlos:
> - `psql.exe` está en `C:\Program Files\PostgreSQL\16\bin` (no está en el
>   `PATH` por defecto). No hace falta instalar nada.
> - Las contraseñas del datamart están en **`kv-albaranes-rs9k2`**, secretos
>   `pg-sigrid-dm-app` y `pg-mcp-sigrid-dm-ro`. Nunca en ficheros del repo.
> - Al conectar con `psql`, **las opciones van ANTES** de la cadena de
>   conexión: este build deja de parsearlas tras el primer argumento
>   posicional.
> - Los ID de recurso de Azure se rompen en Git Bash por la conversión de
>   rutas: usa la forma `--resource NOMBRE --resource-group ... --resource-type ...`.

# F-003 · DESBLOQUEADA (F-019 done el 2026-08-17) — falta la tanda 2 (T23–T26)

> F-019 cerrada con APROBADO del reviewer (dos pasadas,
> `progress/review_F-019.md`) y resumen en `history.md`. El siguiente
> movimiento es del humano: `jobProgramable: true` en `infra/env/dev.json`
> (T14 de F-019 / R16) y la tanda 2 de abajo. La sección siguiente se
> conserva como contexto de F-003.

Rama `feature/F-003-infra-caj`, rigor `critico`. **T1–T17 completas** y
**re-review del reviewer: APPROVED** el 2026-08-10 (`progress/review_F-003.md`,
segunda pasada anexada; la primera fue CHANGES_REQUESTED por la puerta del
disco mal condicionada, corregida y verificada). DA-4 cerrada por el humano:
opción B, contraseña vía referencia de Key Vault; enmienda fechada en la spec.

## Tanda 1 del bloque 5 · EJECUTADA por el humano el 2026-08-10 (T18–T22)

| Qué | Resultado verificado (lecturas del líder) |
|---|---|
| Resource group | `rg-datamart-seg-dev` en spaincentral, 7 tags acens (R15) — `costcenter=pendiente` hasta que acens dé el centro de coste |
| Log Analytics | `log-datamart-seg-dev`, PerGB2018, 30 días |
| Entorno Container Apps | `cae-datamart-seg-dev`, sin VNet, logs a log-analytics (R16). **IP de salida: 68.221.221.85** |
| Firewall Postgres | Regla `caj-datamart-seg-dev` → 68.221.221.85 creada en `psql-albaranes-rs9k2` con autorización expresa del humano (R23 parcial) |
| Storage | `stdatamartsegdev`: sin acceso público, sin clave compartida, TLS1_2, contenedor `aux` (R17) |
| Key Vault | `kv-datamart-seg-dev` con RBAC; secretos: `SIGRID-API-FUNCTION-KEY`, `pg-sigrid-dm-app`, `pg-mcp-sigrid-dm-ro` (R18 + paso 8 bis hecho, migración sin exponer valores) |
| Identidad | `id-datamart-seg-dev` con exactamente 3 roles de ámbito recurso (R19) |
| Imagen | `datamart-seg-anual:r20260810-1024` en el ACR, único tag, sin latest (R20) |

**Pendiente (tanda 2, tras F-019): T23–T26** — crear el job, prueba segura
(`version`/`check-pg`), logs (R24) y alerta con correo real (R25); más las 3
verificaciones MANUAL de F-004 y retirar las copias viejas de los secretos en
`kv-albaranes-rs9k2` cuando el job complete una ejecución correcta.

**Defectos encontrados al desplegar (todos corregidos o anotados):** dos
roturas de PowerShell 5.1 en los scripts (JMESPath con `?`/`!` contra az.cmd y
comprobaciones de existencia que morían por stderr), corregidas por el
implementer y verificadas ejecutando; el puesto NO tiene pwsh 7, el README ya
usa `powershell -NoProfile -File`. Anotados sin corregir aún (para la vuelta
de F-003): el comando de firewall del README usa `-n` para el servidor y la
versión actual de az exige `--server-name`/`--name`; y la verificación de
roles de `60_create_identity.ps1` consulta antes de que RBAC propague y lanza
un `throw` falso (necesita reintento con espera).

## ⚠ LAS DOS PUERTAS DEL BLOQUE 5 (una sigue cerrada, la otra ya se resolvió)

**1 · El disco (incidente del 2026-08-09, más abajo).** El job nocturno
ejecuta la misma carga que llenó el disco del servidor compartido. Entre A, B y
C **ya se decidió: la B**, y es `F-019` en `harness/features.json`. Lo que
falta, por tanto, no es decidir: es implementarla. **NO crear el job programado
(T23) hasta que `F-019` (build de `stg.plan_mensual` por tramos) esté
implementada y verificada contra Azure.**

La puerta es detectable por máquina, no solo prosa: `infra/env/dev.json`
declara `jobProgramable: false`, `80_create_job.ps1` aborta con `throw`
mientras lo lea así, y `tests/test_f003_infra.py` deja la suite en rojo si
alguien lo pone a `true` con `F-019` sin cerrar. Además
`infra/05_check_prereqs.ps1` falla si la ocupación supera el 60 % y
`80_create_job.ps1` no hace nada sin `-Confirmar`, pero ninguna de esas dos
frena hoy: el disco volvió al 42,3 % al revertirse la transacción.

**2 · DA-4 · autenticación contra Postgres. CERRADA por ti el 2026-08-10:
OPCIÓN B, ya aplicada.** La spec aprobada prohibía pasar contraseña al job (R10)
y mandaba token de Entra (R12), pero `psql-albaranes-rs9k2` **tiene Entra
deshabilitado** y habilitarlo es una operación de servidor que afecta a
`albaranes` y `partes` — la descartaste el 2026-08-08, y F-005 se desplegó con
contraseña en Key Vault. Tal cual, **el job se creaba perfecto y fallaba al
conectar todas las noches**.

Cómo queda: el job se autentica como `sigrid_dm_app` con su contraseña, que
viaja como **referencia a Key Vault resuelta por la identidad gestionada**,
igual que la clave de `sigrid-api`. **Ningún valor de secreto** en el
repositorio, en un script ni en la línea de comandos. `pgAuthMode` pasa a
`password`; el modo `entra` queda implementado, probado y **dormido**. La
enmienda está escrita y fechada en `specs/F-003-infra-caj/requirements.md`
§Enmiendas, sin borrar el texto original de R10 ni el bloque C.

Esta puerta **ya no bloquea T23**; la única que queda es `F-019`. Lo que sí
añade es un paso nuevo al bloque 5: **T22 bis, migrar las dos contraseñas** de
`kv-albaranes-rs9k2` a `kv-datamart-seg-dev`, que también aprobaste. Va antes de
crear el job, y el procedimiento seguro (el valor no pasa por pantalla, ni por
fichero, ni por el historial) está en `infra/README.md` §«Paso 8 bis».

## Guion del bloque 5 (T18–T28), listo para ejecutar

Antes de nada: `pip install -r requirements.txt`. `azure-identity` y
`azure-storage-blob` están declaradas pero **no instaladas** en el puesto, y la
verificación 1 de F-004 fallaría con `ModuleNotFoundError`.

Todo el detalle (comandos exactos, qué exige autorización, KQL de logs) está en
**`infra/README.md`**. Resumen operativo:

| Tarea | Comando | Comprobar |
|---|---|---|
| **T18** | `powershell -NoProfile -File infra/05_check_prereqs.ps1` → `10_create_rg.ps1` → `20_create_observability.ps1` → `30_create_env.ps1` | R15 y R16. **Anotar la IP de salida del entorno.** |
| **T19** | `40_create_storage.ps1` → `50_create_keyvault.ps1` → `60_create_identity.ps1` | R17 y R19 (tres roles, ni uno más). **Anotar el `clientId`.** |
| **T20** | `az keyvault secret set --vault-name kv-datamart-seg-dev -n SIGRID-API-FUNCTION-KEY --file <ruta>` | `secret list` devuelve el nombre. **Nunca `secret show`**; el valor no se escribe en ningún fichero. Necesitas `Key Vault Secrets Officer`. |
| **T21** | `powershell -NoProfile -File infra/70_build_image.ps1` | R20. **Anotar el tag.** |
| **T22** | Regla de firewall para la IP de T18 sobre `psql-albaranes-rs9k2` | ⚠ **Escritura sobre un recurso de `albaranes`**: autorización expresa, la ejecutas tú. Después, `firewall-rule list` debe traer las de antes **más** la nueva. |
| **T22 bis** | Migrar `pg-sigrid-dm-app` y `pg-mcp-sigrid-dm-ro` de `kv-albaranes-rs9k2` a `kv-datamart-seg-dev` | **DA-4 opción B (R27).** Procedimiento exacto en `infra/README.md` §«Paso 8 bis»: `show` **siempre** asignado a variable, `set` con `-o none`, sin ficheros temporales. Comprobar con `secret list` (**nunca `show`**). Las copias viejas se borran **después** de T24. |
| **T23** | `powershell -NoProfile -File infra/80_create_job.ps1 -Confirmar` | **BLOQUEADA por `F-019`** (DA-4 ya no bloquea). Exige que T22 bis esté hecha: el script aborta si falta el secreto. R21. |
| **T24** | `az containerapp job start` + `job start --command python --args main.py,version` | `Succeeded` y el tag coincide con T21. |
| **T25** | KQL de `infra/README.md` | Salen las líneas de T24. Si una columna no cuadra, `getschema` y **corregir el README**. |
| **T26** | `az monitor metrics list-definitions --resource <id-job>` y luego `90_create_alert.ps1` | Correcto **solo si llega el correo**. Anotar hora del fallo y de recepción. |
| **F-004** | Las tres verificaciones heredadas (blob desde el puesto, blob desde el job, prueba negativa de permisos) | Sección de F-004, más abajo. Van después de T19+T20. |

Antes de T26 hace falta el nombre del grupo de acción de la landing zone
(**DA-3**, sigue abierta): `az monitor action-group list --query "[].{n:name, rg:resourceGroup}" -o table`
y pasarlo con `-ActionGroupName` / `-ActionGroupRg`. Si no existe ninguno
reutilizable, `-AlertEmail`. **Ningún correo entra en el repositorio.**

## Deuda que dejas decidir a ti

El **ID de suscripción sigue en el historial de git** (estuvo en
`infra/00_vars.ps1` hasta esta feature). Del árbol de trabajo ha desaparecido y
hay un test que impide que vuelva; reescribir la historia es decisión tuya.

---

# F-004 · CERRADA (2026-08-09) — MERGEADA A `dev`

> Merge hecho: `79c48e2 Merge branch 'feature/F-004-etl-sin-dependencias-locales'
> into dev`. La rama de F-003 sale de ahí.

**APPROVED sin condiciones** (`progress/review_F-004.md`), rigor `estandar`.
Resumen en `progress/history.md`; detalle en `progress/impl_F-004.md` y
`progress/mutacion_F-004.md`. Quedan vivas las secciones siguientes: las tres
verificaciones MANUAL (bloqueadas hasta F-003), la decisión DA-1 (la carga a
`aux.*` es de F-013), la dependencia `AZURE_CLIENT_ID` hacia F-003 y el
hallazgo del barrido de secretos para F-016.

**Pendiente del humano**: el reviewer propone dos afinados nuevos de
protocolo (`review_F-004.md` § «Automejora»): (1) al muestrear supervivientes,
contrastar también que las mutaciones PELIGROSAS vecinas de la misma línea
murieron; (2) exigir en C4 que el reviewer deje constancia de CÓMO comprobó
que la suite no toca red (barrido de imports, SDK ausente, o ambos).

## Verificaciones MANUAL (humano) de F-004 · BLOQUEADAS hasta F-003

Las tres necesitan la storage account y el contenedor `aux`, que **crea
F-003**. No bloquean el cierre de F-004; sí deben ejecutarse antes de dar por
buena la lectura de blobs en Azure.

1. Con `az login` activo y el rol `Storage Blob Data Reader` sobre la cuenta,
   apuntar la variable al blob real y ejecutar:
   `python main.py load-aux`
   Esperado: `SUCCESS` y, en el detalle, `origen=blob` con las hojas del libro.
2. Desde el Container Apps Job, con identidad gestionada:
   `az containerapp job start -n <job> -g <rg>` y buscar en los logs el evento
   `aux_file_read`. Esperado: los tres ficheros leídos y **ninguna ruta local**.
3. Prueba negativa del mensaje de permisos: retirar temporalmente el rol,
   ejecutar `python main.py load-aux` y comprobar que el error dice qué rol
   falta y qué hacer. **Volver a asignarlo después.**

## Decisión abierta DA-1 · ¿quién carga los Excels a `aux.*`?

F-004 deja los tres libros **leídos y validados**, no volcados. Motivo: las
tablas destino no existen (`aux` solo tiene `periodificacion_partida`, vacía) y
**el esquema de los tres Excel no está en el repositorio** —columnas, hojas,
claves— ni las reglas que los mapean a `mart`. Inventarlo sería inventar el
modelo de datos de Negocio. Necesita decisión del humano y feature propia.

## Dependencia de F-004 hacia F-003

Si el job **no** usa identidad *system-assigned*, F-003 debe inyectar
`AZURE_CLIENT_ID` en el entorno del contenedor: `DefaultAzureCredential` lo lee
solo, pero alguien tiene que ponerlo. Y la identidad necesita el rol
`Storage Blob Data Reader` sobre la cuenta.

## Hallazgo para F-016 (refuerzo de los tests de F-005) · RESUELTO EN F-016

`test_f005_r21_barrido_de_secretos_en_el_arbol` daba **falso positivo con
rutas largas**: su patrón de base64 (`[A-Za-z0-9+/]{24,}`) casó con
`sigrid/infrastructure/excel/` al añadir una línea a `docs/ARCHITECTURE.md` y
puso `init.sh` en rojo. F-004 no tocó el test de otra feature: reformuló la
frase.

**Cerrado el 2026-08-10 por F-016** (única excepción autorizada para tocar un
test de F-005): el barrido es ahora la función `buscar_secretos()` y el patrón
de clave descarta el candidato solo si **parece una ruta** —dos barras o más
**y** ni una mayúscula—. Con control negativo
(`test_f016_el_barrido_afinado_caza_la_clave_y_no_la_ruta`), que se pone rojo
si alguien afina de más.

---

## ⚠ INCIDENTE 2026-08-09 ~21:00 · disco del servidor compartido casi lleno

Tercer intento del paso 8: `raw` completa (incl. `dca`), pero
`stage`/`build_plan_mensual` **llenó el disco de 32 GB** del servidor
compartido: storage_percent subió a **93,4 %** a las 20:55 y Azure activó la
protección → servidor **en solo-lectura ~10 min** (20:55–21:05) y conexión
matada (`AdminShutdown`). La transacción se revirtió y el disco volvió a
**42,3 %** (≈13,5 GB usados: base previa 4,1 + `raw` del datamart ≈9,4).
`albaranes` y `partes` pudieron fallar escrituras en esa ventana (sábado
noche; revisar sus logs).

**Causa raíz**: `stg/08_plan_mensual.sql` explota `raw.obrparpre` (13,76 M
filas) con `CROSS JOIN LATERAL unnest(string_to_array(planif,'|'))`; en el
B1ms (2 GB RAM) los sorts derraman a ficheros temporales sobre el mismo disco
→ 16+ GB de temporales/WAL y 103 min sin terminar. En local no pasa porque
sobra RAM. **Veredicto anticipado del paso 9: `Standard_B1ms` + 32 GB NO
aguanta el build completo de stg tal como está escrito.**

**PROHIBIDO relanzar `stage` contra Azure hasta decidir** (lo volvería a
llenar). → **Al día 2026-08-10**: decidido (opción B) e **implementado**
(F-019, sección al final de este fichero). La prohibición se levanta cuando el
humano complete T1/T2 y T11 en local; el propio T12 es el primer `stage`
autorizado contra Azure, y ya no es el mismo build: hay tramos acotados y una
puerta de disco que aborta al 80 %. Decisión del humano pendiente entre: (A) crecer el disco 32→64 GB
(operación online pero **irreversible** y sobre el servidor compartido; da
más IOPS), (B) trocear/optimizar el build de `plan_mensual` para acotar el
pico de temporales, (C) subir el SKU. La recomendación del líder es B
primero: A y C tocan el servidor de producción compartido y no arreglan que
1 vCPU se arrastre.

**F-005 · Fase 2 contra Azure, paso 8 a medias.** Pasos 3 a 7 y 11 hechos el
2026-08-09. Del paso 8 (carga inicial) van **dos intentos fallidos**: el
primero por corte de red local (11:46, `getaddrinfo failed`); el segundo llegó
a **30 de 31 tablas** (19,7 M filas, 63 min) y solo falló **`dca`** (causa sin
confirmar; el humano sospecha equipo desatendido/suspensión — si fue eso, el
guardián anti-suspensión de F-014 no cumplió y hay que revisarlo). Como la
ingesta es transaccional por tabla, lo cargado se conserva. **Recuperación
preparada**: worktree limpio de `dev` en
`C:\Users\pgris\PycharmProjects\datamart-carga` (para no importar código a
medio editar del árbol de F-004); el humano copia `.env` y lanza
`ingest --table dca --full` + `stage` + `build-mart` + `apply-grants`.
Alternativa aceptada: esperar a F-003 y hacer la carga completa desde el job
de Azure. Los pasos 9 y 10 dependen de que la base quede completa.

## Lo ejecutado contra Azure

| Paso | Estado |
|---|---|
| 3 · Puerta de espacio | **PASA**: 4,14 GiB usados de 32; **27,86 GiB libres** (exige ≥14) |
| 4 · Contraseñas en Key Vault | Hecho: `pg-sigrid-dm-app` y `pg-mcp-sigrid-dm-ro` en `kv-albaranes-rs9k2` |
| 5 · Base y roles | Hecho: `sigrid_dm`, 3 roles, 9 esquemas, todos propiedad de `sigrid_dm_etl` |
| 6 · Firewall | Añadida `datamart-puesto-pgris-2026-08-09`; las 3 reglas previas, intactas |
| 7 · `.env` | Hecho y verificado por el humano el 2026-08-09 |
| 8 · Carga inicial | **A MEDIAS**: 30/31 tablas; falta `dca` y los pasos posteriores (ver arriba) |
| 9 · Medición y veredicto del SKU | Pendiente del 8 |
| 10 · Verificación de vistas | Pendiente del 8 |
| 11 · Frontera de seguridad | Hecho, ver abajo |

**Fotografía previa** (antes de tocar nada): `Standard_B1ms`, PG 16.14, 32 GB,
auto-grow **deshabilitado**, sin HA, backup 7 días, `log_statement=none`.
Reglas de firewall previas: `AllowAzureServices`, `FirewallIPAddress_2026-6-16`,
`ClientPgris`. Bases previas: `albaranes`, `partes`.

## Frontera de seguridad, medida

- `sigrid_dm_app` conecta y `SET ROLE sigrid_dm_etl` funciona
  (`current_user=sigrid_dm_etl`, `session_user=sigrid_dm_app`). Crea y borra.
- `mcp_sigrid_dm_ro` **no puede escribir**: `permission denied`.
- `mcp_sigrid_dm_ro` **sí puede conectarse a `albaranes`** —riesgo aceptado el
  2026-08-08 al descartar `REVOKE CONNECT`— y **no puede leer sus datos**
  (`permission denied for table`). Lo que sí ve, cuantificado: **14 nombres de
  tabla y 450 de columna** vía `pg_catalog`, que no filtra por privilegios.
  `information_schema` sí filtra y le devuelve 0.

## Defecto encontrado y corregido

`infra/sql/02_roles.sql` hacía `ALTER ROLE ... WITH NOSUPERUSER ...` y **falla
contra Azure**: el administrador de un Flexible Server no es superusuario, y
PostgreSQL exige el atributo SUPERUSER para cambiarlo aunque sea para ponerlo
a NO. Contra un PostgreSQL local no fallaba porque allí el admin sí lo es:
este fichero **solo podía romperse contra Azure**, y solo al ejecutarlo.

Corregido quitando `NOSUPERUSER`, que era redundante: `CREATE ROLE` ya crea
sin superusuario, y así se verificó (`rolsuper = f` en los tres roles).

## Lo que falta

1. **`.env` · HECHO y verificado** el 2026-08-09. Los once valores correctos:
   host de Azure, `sigrid_dm`, `sigrid_dm_app`, contraseña de 32 caracteres
   que coincide con Key Vault, `sslmode=require`, **`PG_AUTO_CREATE_DB=False`**,
   `SET ROLE` y rol de solo lectura. `check-pg` responde PostgreSQL **16.14**
   (Azure; el local es 16.4). La contraseña está tipada como `SecretStr`, así
   que no puede colarse en un log.
2. **Carga inicial · PENDIENTE, la lanza el humano**:
   `python main.py run-all --full`. El `apply-grants` final no es opcional.
   Puede tardar: ~4 GB a través de una API que sirve 1.000 filas por petición,
   contra un servidor de 1 vCPU. Es repetible: si hay que abortarla porque
   `albaranes` o `partes` se resienten, se relanza sin más.
3. **Pasos 9 y 10, del líder, en cuanto termine la carga**: medición con
   `python main.py timings` y **veredicto explícito sobre si `Standard_B1ms`
   aguanta** —es la entrada de F-011—, y comparación de la huella de vistas
   local contra Azure con el mes cerrado que fije el humano.

## Nota sobre dónde viven las contraseñas

Se han guardado en **`kv-albaranes-rs9k2`** porque el vault propio del
datamart (`kv-datamart-seg-dev`) **lo crea F-003 y todavía no existe**. Es una
decisión de conveniencia, no de diseño: **F-003 debe moverlas** a su vault y
actualizar la referencia. Anotado para que no se quede así por inercia.

> **Al día 2026-08-10:** deja de ser una nota suelta. Con DA-4 cerrada (opción
> B) la migración es **T22 bis** del bloque 5, con procedimiento escrito en
> `infra/README.md` §«Paso 8 bis» y requisito propio (**R27**). Sigue
> pendiente de ejecutar: el vault de destino aún no existe.

---

# F-015 · CERRADA (2026-08-09) — pendientes resueltos el mismo día

Implementada y **APROBADA** por el reviewer a la primera
(`progress/review_F-015.md`). Resumen en `progress/history.md`. Los cuatro
pendientes que elevó, cerrados por el humano el 2026-08-09:

1. **MANUAL de R20 · VERIFICADO por el humano**: los cuatro comandos
   devolvieron lo esperado (commit `5006ee8`, `ARNES_VERSION=1.2.0`,
   herramientas presentes, guía con la sección de mutación en su línea 287).
2. **Refuerzo de F-005 · SÍ**: creada **F-016** (`sdd=false`, rigor
   `estandar`, prioridad 9) para los 6 huecos de riesgo ALTO. Los de riesgo
   medio y bajo quedan como deuda anotada en `progress/mutacion_F-005.md`.
3. **Rigor de las 9 features sin abrir**: se decidirá al abrir cada una;
   mientras tanto heredan `critico`, que es el comportamiento buscado.
4. **Automejora del reviewer · APROBADA y aplicada**: `reviewer.md` (paso 4
   de la validación de rigor) y `CHECKPOINTS.md` (C4 bis) exigen ahora
   verificar los totales de mutación de forma independiente. Portada a
   `arnes-base` **1.2.1**.

# Rumbo confirmado por el humano (2026-08-09): el ETL debe correr en Azure

Nuevo orden de prioridades de las features abiertas: ~~F-004~~ (**cerrada el
2026-08-09**) → **F-003** (Container Apps Job nocturno `--full`; spec aprobada
el 2026-08-09, **bloques 1–4 implementados el 2026-08-10**, ver arriba) →
**F-016** (refuerzo tests F-005) → **F-011** (incremental) → resto.

Las dos recomendaciones del reviewer de F-004 están **incorporadas**: las tres
verificaciones MANUAL de F-004 viven ahora en el guion del bloque 5 y en
`infra/README.md`, y `AZURE_CLIENT_ID` se inyecta en el job con su propio test
(`test_f003_r7_el_job_inyecta_azure_client_id_de_la_identidad`).

Modelos de agentes: el humano decidió dejar implementer y reviewer fijados a
`opus`; leader y spec-author siguen en `inherit`.


---

# F-020 · CERRADA (2026-08-10)

**APPROVED del reviewer** (`progress/review_F-020.md`), rigor `estandar`.
Resumen en `progress/history.md`; detalle en `progress/impl_F-020.md` y
`progress/mutacion_F-020.md`. El arnés soporta monorepos multi-servicio
(`harness/servicios.json` opcional); `arnes-base` en **1.3.0**. Este repo
mono-proyecto no cambia de comportamiento (verificado por el reviewer).

# F-019 · Fase B APROBADA por el reviewer (2026-08-10) — BLOQUEADA esperando las fases A y C del humano

**APPROVED** (`progress/review_F-019.md`): 379 tests, 100 % de cobertura de
las líneas cambiadas, mutación 41/41 muertos (rigor `critico` cumplido).
La feature queda `blocked` hasta que el humano ejecute las fases A
(mediciones locales R1/R2) y C (equivalencia R13 y verificación Azure
R14–R16, que completa el paso 8 de F-005 y permite `jobProgramable: true`).
El guion detallado está justo debajo, escrito por el implementer.

Rama `feature/F-019-plan-mensual-por-tramos`, rigor `critico`. **T3–T10
completas** (un commit por tarea); informe en `progress/impl_F-019.md` y
campaña en `progress/mutacion_F-019.md`. Pendiente del **reviewer** y, después,
de las verificaciones MANUAL de abajo.

Números reales, no estimaciones: **379 tests en verde** (4,88 s), **cobertura
100 % de las 120 líneas cambiadas** (umbral 80 %) y **mutación 41/41 muertos,
cero supervivientes**. Ningún agente ha abierto conexión a BBDD ni a la API.

## Qué hace ahora el build de `stg.plan_mensual`

Pesos por obra → plan de tramos (`etl_sigrid/domain/tramos.py`, función pura)
→ vaciado UNA vez → por cada tramo: **puerta de disco** → SQL filtrado por sus
obras → **una transacción** → fila propia en `_meta.etl_runs`
(`build_stg.build_plan_mensual.tramo_NN`) y log estructurado. Si la ocupación
supera el límite, si la medición falla o si un tramo revienta: la tabla queda
**vacía**, el paso queda **FAILED** y `build_mart` no llega a ejecutarse.

Tres parámetros nuevos, todos con default y cambiables por variable de
entorno: `PG_TRAMO_MAX_FILAS` (1 000 000), `PG_DISCO_TOTAL_GB` (32) y
`PG_DISCO_LIMITE_PCT` (80).

## GUION MANUAL DEL HUMANO (por orden; ninguno lo puede ejecutar un agente)

Los comandos exactos están en
`specs/F-019-plan-mensual-por-tramos/requirements.md`. Recordatorios de
entorno: `PSQL` = `& "C:\Program Files\PostgreSQL\16\bin\psql.exe"`, **las
opciones van ANTES** de la cadena de conexión, y `.env` apunta HOY a Azure (la
copia local está en `.env.local.bak`).

### 1 · T1 y T2 — medir en LOCAL (R1) y fijar las constantes — HECHO 2026-08-11

Mediciones del humano anotadas en `design.md` §2: 29.091.584 filas finales
(7,5 GB), explosión master 69,05 M posiciones (×18,4), obra más pesada
298.053 filas. **Ninguna constante cambia** (298 k ≪ 1 M del tramo). El
derrame (medición 4 de R1) se toma en T11 alrededor del `stage` nuevo:
F-019 ya estaba mergeada en `dev`, el build antiguo ya no es ejecutable.

Incidencias del día, ya resueltas: (1) el checksum de R2/R13 se reformuló
**por cubos** — la fórmula original superaba el límite de 1 GB por cadena de
Postgres; la fórmula corregida está en `requirements.md` §R2 y es la que hay
que repetir en R13. (2) El humano editó por error `.env.example` (versionado)
con secretos reales; nunca llegó a commit, se restauró la plantilla y la
configuración de Azure quedó en `.env.azure.bak` (ignorada). **Recomendado
rotar** la contraseña de `sigrid_dm_app` (y el secreto `pg-sigrid-dm-app` de
`kv-datamart-seg-dev`) antes de crear el job.

**Línea base R2 capturada (build antiguo, local):**
`29091584|0a4024a22cb5c4872061820f66c9024c`
(+ `huella_local_antes_f019.csv` en el puesto del humano, sin versionar).

### 2 · T11 — equivalencia funcional en LOCAL (R13), la prueba de fuego

1. Con `.env` apuntando a LOCAL, y **antes** de nada, capturar la línea base
   de **R2**: el checksum de contenido y `python main.py fingerprint-views`
   con el árbol de `dev` (build antiguo).
2. Con la rama de F-019: `python main.py stage`, repetir el checksum y
   `python main.py compare-fingerprints`.

Esperado: **checksum idéntico carácter a carácter** y cero diferencias.
Cualquier diferencia es FALLO: se marca la feature `blocked`, no se
racionaliza.

**Incidente 2026-08-11/12 (T11 pendiente de reintento).** El primer `stage`
del build nuevo (2026-08-11 23:53) FALLÓ a los 28 s: la puerta de disco R10
saltó con «ocupación 169,26 % > 80 %» porque el `.env` local no define
`PG_DISCO_TOTAL_GB` y aplicó el default de 32 GB (pensado para Azure),
mientras el Postgres local suma ~54 GB de bases. El fail-safe se comportó
como está diseñado: tabla vacía, paso FAILED, cero tramos ejecutados.
Corrección para el reintento: añadir `PG_DISCO_TOTAL_GB=200` **solo al
`.env` local** (disco real de 920 GB); `.env.azure.bak` no define la
variable, así que en Azure seguirá aplicando el 32 correcto. Además, el
2026-08-12 el `.env` quedó apuntando a Azure por error y se lanzaron dos
`stage` contra el servidor compartido de producción: ambos murieron **antes
de conectar** (timeout y fallo de DNS), no se escribió nada. Nueva línea
base de derrame para el reintento (los contadores sobrevivieron al
reinicio del puesto de las 04:35): `temp_files=16161`,
`temp_bytes=578.037.755.664`.

**T11-bis (aprobado por el humano el 2026-08-12).** El reintento del stage
nuevo terminó en verde (60 tramos, 53 min, ocupación máx. ~31 %,
29.403.619 filas), pero destapó que la línea base del 22-jul era
**inválida**: el `raw` se reingirió el **30-jul**, después del último build
viejo. Quedan ANULADOS el checksum `29091584|0a4024a2...` y
`huella_local_antes_f019.csv` (comparaban datos del 22-jul contra datos
del 30-jul). Plan aprobado: worktree del build viejo en
`C:\Users\pgris\PycharmProjects\datamart-old-f019` (commit `2cb6de7`, el
`dev` previo al merge de F-019) → build viejo sobre el `raw` del 30-jul →
checksum y huella viejos → build nuevo en el repo principal → checksum y
huella nuevos → comparación exacta. **`ingest` no se ejecuta en ningún
momento** para mantener el `raw` congelado. Verificado que el SQL de
`stg/` no usa `CURRENT_DATE`/`now()`: el build es determinista dado el
`raw`. Medición 4 de R1 ya tomada con el stage nuevo de hoy: **derrame
12,8 GB de temporales / 29,4 M filas ≈ 0,47 KB/fila** (delta de
`temp_bytes` 578.037.755.664 → 591.769.096.726 alrededor del `stage`
completo).

**T11-bis, brazo 1 COMPLETADO (2026-08-13).** Build viejo (worktree
`2cb6de7`) sobre el `raw` del 30-jul: **29.403.619 filas** — mismo recuento
que el build nuevo. Duración del monolítico: **6 h 24 min** (22.532 s solo
`plan_mensual`) frente a los 53 min del build por tramos. Derrame del
monolítico: 13,86 GB ≈ 0,47 KB/fila (calcado al del nuevo; la mejora del
troceo es tiempo y pico de ocupación, no derrame). Capturas de referencia:

- **Checksum viejo (la referencia a clavar):**
  `29403619|ec74147ef3e7175c66ed9d30d3e72f9f`
- **Huella vieja:** `huella_build_viejo_f019.csv` (34 vistas, 694 métricas,
  sin `--periodo-hasta`; la nueva debe capturarse igual), sin versionar.
- Base de temporales antes del brazo 2: `temp_files=17802`,
  `temp_bytes=620.626.993.530`.

**T11-bis, brazo 2 y VEREDICTO: FALLO (2026-08-13, ~01:00).** El stage
nuevo terminó en verde (49 min, mismo recuento 29.403.619) pero el checksum
NO coincide:

- viejo:  `29403619|ec74147ef3e7175c66ed9d30d3e72f9f`
- nuevo:  `29403619|c58b928de0c7bf297c9158b8f3faa370`

La feature sigue `blocked` (ya lo estaba) y NO se avanza a T12/T13/T14.
Evidencia completa: mismo recuento; `compare-fingerprints` de
`huella_build_viejo_f019.csv` vs `huella_build_nuevo_f019.csv` equivalente
sin avisos (OJO al peso real de esa evidencia: las tablas fact de `mart`
están congeladas desde el 22-jul porque `build-mart` no corrió, pero las
vistas de `cierre/04_views_detalle.sql` y `mart/06_views_cp_tipologia.sql`
SÍ leen `stg.plan_mensual` en vivo y sus sumas/recuentos coincidieron);
`raw` congelado verificado (cero ejecuciones en `_meta.etl_runs` entre
builds); diff del SQL viejo→nuevo limpio (solo comentarios, TRUNCATE al
step y el filtro `F019_FILTRO_OBRAS` en ambas ramas; ni una expresión de
negocio cambió); sin columnas float (todo `numeric`/fechas/ids/text); las
ventanas de 08 son MAX/COUNT (insensibles a empates) y el LAG ordena por
`posicion_mes`, único por `WITH ORDINALITY` dentro de cada presupuesto.

Hipótesis abiertas: (a) no determinismo por empates en alguna parte aún no
localizada (se manifestaría también entre dos ejecuciones del MISMO build),
(b) diferencia de ESCALA en `numeric` (`1.50` vs `1.5`: igual como número,
distinto como texto; invisible para vistas y tests, letal para el
checksum), (c) diferencia real de contenido que los agregados no ven.

Plan de diagnóstico propuesto al humano (pendiente de su OK):
1. Congelar evidencia: `CREATE TABLE tmp_f019_nuevo_a AS SELECT * FROM
   stg.plan_mensual` (~7,5 GB en local).
2. Test de reproducibilidad (barato, decisivo): relanzar el stage NUEVO
   (~50 min) y re-checksum. Si difiere de `c58b928d...` → el build no es
   reproducible consigo mismo → el criterio de R13 es insatisfacible tal
   cual y el arreglo es fijar desempates deterministas (cambio de código
   vía SDD) o redefinir R13. Si coincide → diferencia sistemática
   viejo↔nuevo.
3. Solo si es sistemática: relanzar el build VIEJO en el worktree (~6,4 h)
   y hacer diff por filas contra `tmp_f019_nuevo_a` con igualdad NUMÉRICA
   (`EXCEPT` en ambas direcciones, insensible a escala): vacío → solo
   escala (equivalencia semántica probada, decidir sobre R13); no vacío →
   muestrear filas y columnas discrepantes y buscar la causa.

**Resultados del plan (2026-08-13, humano dio OK y lo ejecuta el agente):**

- Paso 1 HECHO: `public.tmp_f019_nuevo_a` creada con las 29.403.619 filas
  del build nuevo (borrar al cerrar la investigación).
- Paso 2 HECHO — **el build nuevo ES reproducible**: segunda ejecución
  (2026-08-13 10:07→11:51) → checksum `29403619|c58b928de0c7bf297c9158b8f3faa370`,
  idéntico carácter a carácter al de la primera. La diferencia con el
  viejo es SISTEMÁTICA. Hipótesis (a) descartada para el build nuevo.
- Descartado también que el parámetro de `07_version_master_vigente.sql`
  sea una fecha: es `cod=15` (código de configuración), y ningún SQL de
  `stg/` usa `CURRENT_DATE`/`now()`.
- Paso 3 LANZADO (~14:15 local): build viejo en el worktree (~6,4 h).
  Al terminar: `EXCEPT` numérico en ambas direcciones entre
  `stg.plan_mensual` (contenido viejo) y `tmp_f019_nuevo_a` (nuevo), y
  muestreo de discrepancias por columna. Suspensión del portátil con
  corriente desactivada (`powercfg standby/hibernate-timeout-ac 0`) a
  petición del humano para aguantar la tirada.

**CAUSA RAÍZ ENCONTRADA (2026-08-13 tarde).** Cadena de evidencia:

1. El build viejo también es reproducible (2ª ejecución, 1 h 24 esta vez:
   las 6 h 24 de ayer eran el portátil): `ec74147e...` clavado. Ambos
   builds deterministas, contenido establemente distinto.
2. `EXCEPT ALL` numérico: **10.259 filas difieren en cada dirección**
   (0,035 %), solo **2 obras** (2403576, 2491656), 1.955 presupuestos,
   solo rama master (ámbitos 8 y 11).
3. Esas 2 obras son EXACTAMENTE las únicas de master con «filas gemelas»
   (clave presupuesto+ámbito+mes+posición duplicada): 23.111 + 7.749 =
   30.860, el total de master. Correlación perfecta.
4. Por clave, los multiconjuntos de valores son IDÉNTICOS entre builds en
   todas las columnas de negocio (pct, cantidades, importes, versión): los
   valores solo se reparten al revés entre las gemelas. Residuo de 3
   filas: mismo fenómeno vía `version_descripcion`.
5. Origen de las gemelas: esas obras tienen **DOS versiones master con el
   mismo número 13**, creadas el 22/07/2026 y el 23/07/2026. La selección
   de vigente no desempata (empatan en número), así que cada posición sale
   DUPLICADA. Ninguna pareja de gemelas es duplicado exacto (16.980
   claves, todas con valores distintos entre gemelas).
6. Mecanismo: las ventanas de 08 (`MAX ... ROWS UNBOUNDED PRECEDING`,
   `LAG ... ORDER BY posicion_mes`) quedan SUBESPECIFICADAS cuando
   `posicion_mes` empata (gemelas). Cada plan de ejecución (monolítico vs
   por tramos) resuelve el empate distinto pero estable. **El troceo de
   F-019 NO cambia ningún valor: el no determinismo es preexistente** (el
   build viejo también cambiaría de bytes con otro plan/versión de PG).

Conclusión técnica: **equivalencia semántica PROBADA** (mismos
multiconjuntos de valores por clave en toda la tabla; los agregados a
cualquier nivel son idénticos, por eso la huella coincidía). El checksum
byte a byte de R13 es insatisfacible tal cual ante gemelas: mide el orden
del empate, no el contenido.

Hallazgo colateral (PREEXISTENTE, igual en ambos builds, fuera del alcance
de F-019): la versión 13 duplicada hace que TODO el plan master de esas 2
obras esté contado DOS VECES en `stg.plan_mensual`. Revisar con negocio si
la vigente debería desempatar (p. ej. por fecha de creación más reciente).

**DECISIÓN DEL HUMANO (2026-08-13): opción C** — enmendar R13 y dar T11
por superado, más registrar el caso «muy bien, con código de obra y causa,
para poder replicarlo a mano». Ejecutado:

- `requirements.md` R13: enmienda fechada con el criterio canónico
  (cardinalidad + `EXCEPT ALL` numérico con multiconjuntos por clave +
  huella) y el veredicto **R13 SUPERADO**.
- `docs/referencia/05_caso_obrfasamb_version_duplicada.md`: el caso
  completo — obras 0694 (2403576, v26 duplicada, creada 20/07 y
  23/07/2026) y 0697 (2491656, v13 duplicada, creada 22/07 y 23/07/2026),
  ides 29916/29983, 29918/29985, 29949/29977, 29951/29979 (el segundo de
  cada pareja siempre del 23/07, ides consecutivos: parece una misma
  acción en Sigrid ese día), mecanismo del join por (obride, amb, fas) y
  receta SQL de replicación. Indexado en el README de referencia.
- `harness/features.json`: **F-022** creada (pending, sdd, prioridad 12):
  desempate determinista, con la pregunta de negocio previa (¿corregir en
  Sigrid o desempatar en ETL?). La F-021 sigue reservada para la
  planificación consolidada.
- Limpieza: DROP de `tmp_f019_nuevo_a`, `tmp_f019_diff_viejo` y
  `tmp_f019_diff_nuevo`; worktree `datamart-old-f019` retirado (su copia
  de `.env` eliminada con él); borrado `huella_local_antes_f019.csv`
  (anulado). Se conservan `huella_build_viejo_f019.csv` y
  `huella_build_nuevo_f019.csv` (evidencia del T11, sin versionar).
  `stage` final lanzado para dejar la tabla local en estado del build
  nuevo.

**T11 CERRADO (SUPERADO).** Siguiente: T12 (R14, Azure) en horario
acordado con el humano.

- **Rotación de secretos DESCARTADA por el humano (2026-08-14):** «no es
  crítico de momento, ignoralo». No volver a pedirla en los guiones de
  T12/T14; queda como mejora opcional a futuro.
- Conectividad del puesto resuelta el 2026-08-14: la IP pública del
  humano cambió (90.160.96.77; las reglas tenían 62.174.237.73 del
  09-ago). El clasificador de permisos bloqueó la escritura del firewall
  al agente: los comandos `az` (crear regla del día + borrar la del
  09-ago) se le pasaron al humano para que los ejecute él. Reglas
  candidatas a limpieza futura si él confirma que sobran: `ClientPgris`
  (188.87.59.11) y `FirewallIPAddress_2026-6-16` (80.28.223.30).

### 3 · T12 — verificación contra AZURE (R14), en horario acordado

**Pre-check SUPERADO el 2026-08-14 (~12:40).** Camino recorrido por el
humano: re-login `az` con MFA reforzado (`--claims-challenge` +
`--use-device-code`; la política de acceso condicional lo exigió al
cambiar la IP), regla `datamart-puesto-pgris-2026-08-14` (90.160.96.77)
creada y `datamart-puesto-pgris-2026-08-09` borrada en
`rg-albaranes-dev`/`psql-albaranes-rs9k2`. La consulta de medición como
`sigrid_dm_app` devolvió **7743 MB** ocupados en total (≈7,6 de 32 GB):
margen sobrado para el derrame estimado de ~13 GB (pico previsto ~21 GB,
~65 % < límite 80 %). Verificado además que `raw` quedó COMPLETA el
09-ago: 31 tablas y `dca` con 306.737 filas; `sigrid_dm` ocupa 7.680 MB
(los ~13,5 GB del incidente incluían WAL/sistema, que cuentan en
`storage_percent` pero no en `pg_database_size`). T12 es directamente
`stage` → `build-mart` → `apply-grants`, sin re-ingesta. Falta solo el
horario acordado para la tirada.

**Intento 1 de T12 FALLIDO el 2026-08-14 ~14:15 (red, no código).** El
humano lanzó `stage` desde un sitio con cobertura mala e inestable:
`build_presupuesto` terminó y commiteó (13.759.593 filas, 1.380 s), pero
la conexión nueva para `record_run_end` cayó con `getaddrinfo failed`
(tercer fallo de red de este tipo: 09-ago 11:46, 14-ago 12:33 y este).
`plan_mensual` ni arrancó (tabla vacía). Estado de Azure seguro; el
relanzamiento machaca lo parcial (TRUNCATE por sub-paso). **Acordado:
reintento esta noche a la 01:00** desde conexión estable, suspensión
desactivada. ⚠ Si el humano está en otra red, su IP pública habrá
cambiado otra vez (la regla vigente es 90.160.96.77): comprobar con
`ifconfig.me/ip` y crear regla nueva antes de lanzar. Dato útil ya
medido: `build_presupuesto` en el B1ms = 1.380 s (~23 min).

**T12 COMPLETADO en el intento 2 (14-ago 18:58Z → 15-ago 10:01Z, con
pausa nocturna entre stage y build-mart).** El humano decidió relanzar
desde la misma red inestable; blindaje aplicado: IP verificada
(90.160.96.77 sin cambios) y `hosts` fijado a 68.221.140.205 desde
consola de administrador (⚠ RETIRAR la línea al terminar T13). Resultados
medidos en el `Standard_B1ms`:

- `stage` **SUCCESS en 6.851,8 s (1 h 54)**: `build_plan_mensual`
  troceado 5.993,9 s (~100 min), **60/60 tramos sin un solo aborto**,
  29.398.375 filas. Ocupación de disco: 23,6 % inicial → **pico 46,55 %**
  (~14,9 de 32 GB), muy lejos del límite 80 %; la puerta no intervino.
- `build-mart` SUCCESS en 1.305,8 s (~22 min): `build_fact` 5.287.299
  filas (1.168 s), `agg_categoria` 24.591.
- `apply-grants` SUCCESS: 28 sentencias, rol `mcp_sigrid_dm_ro`.
- `timings` capturado con el desglose de los 60 tramos (máx 293 s el
  tramo 2; el 60 —564 obras pequeñas— 250 s).
- Filas stg.plan_mensual: 29.398.375 vs 29.403.619 en local (−5.244) =
  deriva esperada de raw (Azure 09-ago, local congelado 30-jul). Por eso
  T13 compara solo meses cerrados con `--periodo-hasta`.

**Veredicto del paso 9 de F-005: el B1ms AGUANTA el build troceado.**
Factor de lentitud ~×2 respecto al portátil, pipeline completo
stage+mart ≈ 2 h 16 — perfectamente viable como job nocturno. Pasos 8 y
9 de F-005 COMPLETADOS.

Levanta la prohibición de «no relanzar `stage` contra Azure» **porque ya no es
el mismo build**. Antes de nada, el pre-check de que el rol real puede medir:

```
PSQL -h psql-albaranes-rs9k2.postgres.database.azure.com -p 5432 -U sigrid_dm_app -d sigrid_dm -X -c "SELECT pg_size_pretty(SUM(pg_database_size(datname))) FROM pg_database;"
```

Si eso falla, la puerta R10 abortaría el build nada más empezar (a propósito).
Después: `stage` → `build-mart` → `apply-grants`, vigilando `storage_percent`
por Portal o `az monitor metrics list`. Anotar **pico de disco**, duración y
`python main.py timings` con el desglose por tramo.

Esto **completa el paso 8 de F-005** y da el dato del paso 9 (veredicto sobre
si el `Standard_B1ms` aguanta con el build troceado).

### 4 · T13 — huella local contra Azure (R15)

`fingerprint-views` contra Azure y `compare-fingerprints` con la huella local
de T11. Sin diferencias. Cierra el **paso 10 de F-005**.

**Intento 1 (2026-08-15, `--periodo-hasta 2026-05` a petición del humano;
junio es el último cerrado pero prefirió margen): 41 FALLOS + 59 avisos.**
Diagnóstico en dos grupos, ninguno es un bug del build:

1. **22 vistas «presente vs ausente»**: en Azure nunca se construyeron
   las capas `cierre`, `compras`, `maestro` y `retenciones` — sus builds
   (`build-cierre`, `build-maestros`, `build-compras`,
   `build-retenciones`) NO forman parte de `run-all` (docstring de
   `run-all` en `main.py`) y el 09-ago solo llegó a correr `stage`.
   Hueco de despliegue, se arregla ejecutándolos allí + `apply-grants`.
2. **19 fallos del bloque cerrado del mart** (count +117 sobre 4,87 M =
   0,0024 %; +319,54 € de incurrido): deriva REAL del raw entre 30-jul
   (local) y 09-ago (Azure) — documentos de coste con fecha retroactiva
   en meses cerrados y versiones nuevas que añaden filas a meses
   pasados. Con raws de fechas distintas la igualdad exacta es
   imposible por diseño; el docstring de `fingerprint-views` ya exige
   capturar ambos lados con el mismo estado. Hace falta re-ingesta
   sincronizada en los dos lados antes de repetir la huella.

Huellas del intento: `huella_azure_f019.csv` y
`huella_local_cerrados_f019.csv` (raíz, sin versionar).

**Parte A del arreglo (2026-08-15, tarde): 3 de 4 capas desplegadas en
Azure.** `build-maestros` (23,6 s), `build-compras` (566,1 s, 2,46 M
filas de fact) y `build-retenciones` (86,5 s) en verde + `apply-grants`
(303 s, lento — el servidor venía de una muerte). **`build-cierre` FALLA
de forma REPRODUCIBLE en `build_fact`**: dos intentos muertos con
«server closed the connection unexpectedly» a duraciones muy distintas
(982 s a las 11:46Z y 3.654 s a las 17:26Z) → presión de memoria
dependiente de la carga del momento (B1ms, 2 GB compartidos), no un
punto fijo. Mismo mal que F-019 curó en plan_mensual, ahora en cierre;
destapado porque cierre NUNCA se había construido en Azure. Además, tras
el segundo fallo `apply-grants` estuvo **71 min sin poder conectar**
(timeout) — servidor grogui o red del humano caída; pendiente de
confirmar salud del servidor (sirve albaranes y partes en producción).

**DECISIÓN: no más reintentos de `build-cierre` contra Azure** hasta
diagnosticar. Plan propuesto al humano (pendiente de su OK): evidencia
en métricas del Portal (Memory/CPU percent en las dos ventanas), parche
corto (`SET LOCAL work_mem/jit=off` en build_fact de cierre), feature de
backlog para trocearlo con el planner de F-019, y builds de cierre solo
en horario valle mientras tanto.

**Giro del diagnóstico (2026-08-15 noche): el sospechoso principal pasa
a ser LA RED DEL HUMANO, no el servidor.** Cadena de evidencia: (1) el
humano confirmó estar en un sitio «con mala cobertura e inestable»; (2)
las dos muertes de `build_fact` ocurren a duraciones aleatorias (16 y
61 min) durante consultas largas = conexión TCP en silencio, perfil
típico de NAT móvil que descarta conexiones calladas; (3) ayer una
consulta de 19,5 min (mart build_fact) sobrevivió; (4) a las 18:43Z el
servidor respondía al psql a la primera (bases 18 GB, sano) y a las
19:05Z un tercer intento de build-cierre NI SIQUIERA CONECTÓ (timeout a
los 130 s) — un servidor ocioso no rechaza conexiones nuevas, una red
caída sí. El apagón de 71 min de apply-grants queda también explicado
por la red. **AZURE EN PAUSA hasta que el humano esté en red estable.**
Al volver: reintento `build-cierre` + `apply-grants`; solo si volviera a
morir a mitad de consulta en red buena, investigar OOM (experimento
pg_sleep 40 min + métricas del Portal). Backlog nuevo: keepalives TCP en
la conexión del ETL (no salvan un enlace muerto, sí consultas largas
tras NAT agresivo).

**CASO CERRADO (2026-08-15 ~20:20Z): era la red.** Con el enlace «un
poco más estable» (palabras del humano), el 4º intento de `build-cierre`
pasó a la primera: SUCCESS en 2.701 s (`build_fact` 1.609 s, 16.856
filas; `ddl_fact` tardó 1.086 s, probablemente el servidor digiriendo
los abortos previos) y `apply-grants` volvió a sus 9,6 s. El servidor
queda exonerado del todo: no hay OOM, no hace falta parche de memoria ni
trocear cierre. Los keepalives TCP siguen siendo mejora recomendable de
backlog. **Parte A de T13 COMPLETA: las 4 capas + grants desplegadas en
Azure.** Los 22 fallos de vistas ausentes quedan resueltos; el bloque
cerrado sigue pendiente de la parte B (re-ingesta sincronizada de ambos
lados + huellas `--periodo-hasta 2026-05`), que exige red estable
(~5-6 h, la ingesta pasa todo por el portátil dos veces).

**Parte B en marcha (2026-08-16). FASE 1 (Azure) CERRADA a las ~14:22Z.**
Odisea de red del sábado, toda resuelta sobre la marcha: (1) la ingesta
moría con páginas de 500k (descargas >2,5 min cortadas); el humano bajó
`SIGRID_API_PAGE_SIZE` a 50000 en `.env` y pasó; (2) los 3 Excels
auxiliares apuntaban a la carpeta extinta `OneDrive - Construcciones
Ruesma` — ruta buena: `OneDrive - Ruesma/Documentos/Sigrid/
tablas_auxiliares/`; corregida en `.env` (⚠ en los `.bak` quedó un
ESPACIO colado antes de la barra, el humano debía quitarlo); `load-aux`
solo valida, no bloquea stage; (3) la IP del humano rotó DOS veces
(90.160.96.77 → 90.160.92.59 → 77.211.5.184); la regla vigente es
`datamart-puesto-pgris-2026-08-16b` (77.211.5.184) — esta vez el humano
me autorizó expresamente y los `az` los ejecuté yo (create + delete de
obsoletas). Resultado fase 1: `run-all --full` verde (raw fresco de la
madrugada del 16), 4 capas + grants verdes (`build_fact` cierre 16.876
filas), y `huella_azure_t13.csv` completa: 34 vistas, 794 métricas,
bloques estructura/vivo/CERRADO (100). FASE 2 (local) lanzada en
paralelo en otra consola con `.env` local; regla acordada: si hay que
relanzar la huella de Azure, SOLO tras restaurar `.env.azure.bak` al
acabar la fase 2. Después: `compare-fingerprints huella_local_t13.csv
huella_azure_t13.csv`.

**Intento 2 de T13 (2026-08-16 noche): 22 FALLOS, los tres diagnosticados
con causa raíz confirmada por consultas a ambos lados.** La GRAN noticia:
los datos de negocio de los meses cerrados YA SON IDÉNTICOS (la deriva
del intento 1 desapareció con las ingestas sincronizadas). Los 22 fallos
son tres defectos de otra índole que la huella ha destapado:

1. **10 × tipos en compras (bigint/text local vs integer/varchar
   Azure).** Las tablas de compras heredan tipos de `raw.*` (`CREATE
   TABLE AS`), y el raw LOCAL conserva el esquema del mapeo antiguo
   (todo BIGINT/TEXT) porque la ingesta solo trunca, nunca recrea.
   Azure (creado el 09-ago) refleja el mapeo vigente de
   `entities.py::postgres_type` (int→INTEGER, nvarchar(n)→VARCHAR).
   **El desviado es el LOCAL.** Fix: recrear el raw local (drop +
   re-ingesta) y rebuild de compras.
2. **9 × cierre.v_pbi_planif_vs_real (count 24.736 vs 36.657, +48 %).**
   Bug REAL de portabilidad, confirmado: `nombre_mes` mezcla texto
   libre de las fases de Sigrid con derivados
   `to_char(anio_mes,'TMMonth YYYY')`, y `TM` depende de `lc_time` del
   servidor — local `Spanish_Spain.1252` genera «Mayo 2026» (coincide
   con el texto de fase y colapsa), Azure `en_US.utf8` genera
   «May 2026» (convive con «Mayo 2026» y parte cada grupo en dos).
   Verificado: mayo-2026 tiene 1 nombre en local y 2 en Azure; tabla
   base y definición de la vista idénticas en ambos lados. Fix: derivar
   el nombre del mes con constantes en español (sin TM) en los SQL de
   mart/cierre y reconstruir ambos lados.
3. **2 × sum_fact_id del mart.** `fact_id` es BIGSERIAL asignado por
   orden de inserción sin ORDER BY → no determinista entre máquinas.
   count y TODAS las sumas de negocio idénticas. Benigno. Fix candidato:
   que la huella excluya claves sustitutas (columnas con default
   nextval) o INSERT con ORDER BY determinista.

**Arreglo de los defectos 2 y 3 (2026-08-16): HECHO en código.** Commits
`42e128d` (locale: 8 apariciones de `TMMonth` → ARRAY de meses en
castellano, dos más de las previstas en `cierre/04_views_detalle.sql`) y
`65c52aa` (la huella deja de sumar `fact_id`/`fact_cat_id`). `init.sh`
verde: 398 tests, cobertura 100 % de las líneas cambiadas, 1 mutante y 0
supervivientes. Informe: `progress/impl_T13_fixes_f019.md`.
Reprocesando las huellas T13 con el criterio nuevo los fallos bajan de 22
a 20 y los dos que caen son los dos `sum_fact_id`. **Falta la parte del
humano**: reconstruir mart+cierre en local y en Azure y repetir
`compare-fingerprints`; y el defecto 1 (tipos de `compras.*`), que sigue
abierto.

**Intento 3 de T13 (2026-08-17): 5 FALLOS residuales, causa raíz cazada
fila a fila — deriva REAL de datos, no build.** Cronología del día: el
humano reconstruyó local anoche (run-all --full con los fixes, raw del
sáb. noche) y por error capturó la huella local con nombre azure (el
líder la renombró; regla nemotécnica dada: el .env decide el destino,
--out solo el nombre). Fase Azure: build-mart 1.400 s + build-cierre
1.634 s + grants en verde. La huella de Azure necesitó 4 intentos por la
red (2 cortes en consulta larga + 1 rotación de IP): se resolvió con
keepalives TCP vía `PGOPTIONS=-c tcp_keepalives_idle=30...` (sin tocar
código) y con una REGLA DE RANGO en el firewall
(`datamart-puesto-pgris-2026-08-17-rango`, 31.4.242.0-255; el operador
del humano rota dentro de esa subred — limpiar al cerrar). Compare:
**0 fallos de estructura, 0 de mart, 0 de compras, 0 de planif_vs_real**
(los 3 defectos del intento 2, arreglados y verificados). Quedan 5
fallos, todos en `cierre.v_pbi_cierre_resumen` bloque cerrado, y el
COPY fila a fila los reduce a UNA edición en Sigrid: obra 2313811,
DIRECTOS, +632,74 € en el «Previsto» (fase 0) entre las dos ingestas —
632,74×3 meses = 1.898,22 exactos en los sumatorios. Esas filas tienen
`final_version_master` vacío: son el FALLBACK de fase 0 del cierre, que
usa el presupuesto VIVO por diseño (documentado en cierre/02_build_fact
§E). Conclusión: el bloque «cerrado» de las vistas de cierre contiene
un componente legítimamente vivo; la igualdad exacta ahí solo se cumple
si NADIE toca ningún previsto entre las dos capturas.

**DESENLACE (2026-08-17): el humano eligió la OPCIÓN A.** R15 enmendada
y SUPERADA en la spec (commit `2d95980`); tasks.md y design.md §6
actualizados a petición del reviewer (`review_F-019.md`, 2ª pasada).
**T13 CERRADO.** Quedan abiertas SOLO estas tareas operativas del puesto
del humano (no son del repositorio):

- Retirar la línea de `hosts` (68.221.140.205) cuando acabe el trabajo
  contra Azure desde el portátil.
- Limpiar reglas de firewall del puesto cuando el job de F-003 exista:
  `datamart-puesto-pgris-2026-08-17-rango` (31.4.242.0-255) y las
  antiguas `ClientPgris` / `FirewallIPAddress_2026-6-16` si el humano
  confirma que sobran.
- Decidir si `SIGRID_API_PAGE_SIZE=50000` se queda en los `.env` (fue un
  apaño para la red inestable; en red buena 500000 es más rápido).
Reglas de firewall vigentes: `-2026-08-16` (90.160.92.59) y `-16b`
(77.211.5.184) — la IP del humano rebota entre ambas; se limpiarán al
acabar.

### 5 · T14 — desbloquear F-003

Con T12 y T13 en verde y F-019 marcada `done`: poner `jobProgramable: true` en
`infra/env/dev.json` y ejecutar la **tanda 2 de F-003 (T23–T26)** —crear el
job, prueba segura, logs y alerta—. `tests/test_f003_infra.py` solo lo admite
con F-019 cerrada, así que el propio test es la puerta. Esta feature **no
toca** ese fichero.

---

# F-016 · CERRADA (2026-08-10)

**APPROVED** (`progress/review_F-016.md`). Resumen en `progress/history.md`.
Los 6 huecos de riesgo ALTO de F-005, fijados con tests: la mutación sobre
F-005 pasa de 55 a **47 supervivientes, CERO de riesgo alto**. Barrido de
secretos afinado (sin falsos positivos de rutas largas). Deuda restante:
47 MEDIO/BAJO contabilizados en `progress/mutacion_F-005_tras_refuerzo.md`.
