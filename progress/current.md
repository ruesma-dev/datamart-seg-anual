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

# F-003 · BLOQUEADA esperando a F-019 — código APROBADO y tanda 1 desplegada

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

Falta el brazo 2: `stage` nuevo en el repo principal → checksum + huella
nuevos → comparación exacta.

### 3 · T12 — verificación contra AZURE (R14), en horario acordado

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

### 5 · T14 — desbloquear F-003

Con T12 y T13 en verde y F-019 marcada `done`: poner `jobProgramable: true` en
`infra/env/dev.json` y ejecutar la **tanda 2 de F-003 (T23–T26)** —crear el
job, prueba segura, logs y alerta—. `tests/test_f003_infra.py` solo lo admite
con F-019 cerrada, así que el propio test es la puerta. Esta feature **no
toca** ese fichero.

---
