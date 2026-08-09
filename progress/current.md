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

# F-003 · EN CURSO — bloques 1–4 hechos, bloque 5 es del humano

Rama `feature/F-003-infra-caj`, rigor `critico`. **T1–T17 completas** (13
scripts de `infra/` reescritos o creados, `infra/env/dev.json`, 33 tests
nuevos, `infra/README.md`). Informe completo: `progress/impl_F-003.md`.
Campaña de mutación: `progress/mutacion_F-003.md`. `bash harness/init.sh` en
verde, **254 tests** (eran 221).

**Review del 2026-08-10: `CHANGES_REQUESTED`, ya corregido**
(`progress/review_F-003.md`, correcciones en `impl_F-003.md` §10). El defecto:
la puerta que bloquea el cron nocturno estaba escrita como «hasta que se decida
qué hacer con el disco», y esa decisión ya estaba tomada —es `F-019`—, con lo
que se leía como puerta abierta. Ahora depende de que `F-019` esté
**implementada y verificada**, y además es detectable por máquina:
`jobProgramable: false` en `infra/env/dev.json`, `throw` en
`80_create_job.ps1` y tres tests que se ponen en rojo si alguien la abre antes
de tiempo. Falta el nuevo veredicto del reviewer.

**No se ha ejecutado ni un comando `az` de escritura, ni `python main.py`.**

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

## Hallazgo para F-016 (refuerzo de los tests de F-005)

`test_f005_r21_barrido_de_secretos_en_el_arbol` da **falso positivo con rutas
largas**: su patrón de base64 (`[A-Za-z0-9+/]{24,}`) casó con
`sigrid/infrastructure/excel/` al añadir una línea a `docs/ARCHITECTURE.md` y
puso `init.sh` en rojo. No se ha tocado el test de otra feature: se reformuló
la frase. Conviene exigir contexto de asignación o excluir cadenas con varias
barras.

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
llenar). Decisión del humano pendiente entre: (A) crecer el disco 32→64 GB
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

