<!-- progress/current.md -->
# Trabajo en curso

**F-005 · código implementado** el 2026-08-08 por el `implementer`, pendiente
de review y de las verificaciones manuales. Informe completo en
`progress/impl_F-005.md`. Fase 1 (T1-T11) terminada, `bash harness/init.sh` en
verde, 65 tests. **No se ha ejecutado NADA contra Azure ni contra
`psql-albaranes-rs9k2`**: la Fase 2 son las tareas T12-T20, que ejecuta el
humano siguiendo `docs/runbook_postgres_azure.md`.

## F-005 · verificaciones MANUAL (humano) pendientes

Ninguna la ejecuta un agente. El procedimiento completo, con su contexto y sus
puertas, está en `docs/runbook_postgres_azure.md`; aquí van los comandos.

**T12 · Fotografía previa del servidor (solo lectura).** Guardar las salidas.

```
az postgres flexible-server show -g rg-albaranes-dev -n psql-albaranes-rs9k2 -o json
az postgres flexible-server firewall-rule list -g rg-albaranes-dev -n psql-albaranes-rs9k2 -o table
psql "host=psql-albaranes-rs9k2.postgres.database.azure.com dbname=postgres user=<admin> sslmode=require" -f infra/sql/03_diagnostico.sql
```

**T13 · Puerta de espacio (R25, R26). Bloqueante.** Si quedan menos de **14 GB
libres**, PARAR, anotarlo aquí y marcar la feature `blocked`. Ampliar
almacenamiento es irreversible.

```
az monitor metrics list --resource $(az postgres flexible-server show -g rg-albaranes-dev -n psql-albaranes-rs9k2 --query id -o tsv) --metric storage_percent --interval PT1H -o table
```

**T14 · Autenticación. RESUELTA por decisión del humano: plan B.** No se
habilita Entra en el servidor. Se usan roles nativos con contraseña en Key
Vault, como ya hacen `albaranes` y `partes`. No hay nada que ejecutar de la
tarea original; lo que sí hay que hacer es generar y guardar las dos
contraseñas (§4 del runbook) **antes** de T15.

**T15 · Crear la base y los roles.** Idempotente; reejecutar `02_roles.sql` es
además la forma de rotar las contraseñas. La identidad gestionada
`id-datamart-seg-dev` **ya no la crea F-005**: sin Entra no hace falta ningún
principal en la base, así que queda para F-003.

```
export APP_PWD=$(az keyvault secret show --vault-name <kv> --name pg-sigrid-dm-app --query value -o tsv)
export MCP_PWD=$(az keyvault secret show --vault-name <kv> --name pg-mcp-sigrid-dm-ro --query value -o tsv)
psql "host=<host> dbname=postgres  user=<admin> sslmode=require" -v ON_ERROR_STOP=1 -f infra/sql/01_create_database.sql
psql "host=<host> dbname=sigrid_dm user=<admin> sslmode=require" -v ON_ERROR_STOP=1 -v app_pwd="$APP_PWD" -v mcp_pwd="$MCP_PWD" -f infra/sql/02_roles.sql
```

Comprobar después (R13): nueve esquemas y `sigrid_dm_etl` como propietario.
Y que **`albaranes` y `partes` siguen conectando**.

**T16 · Firewall (R22, R23).** Comparar primero con el listado de T12; crear
regla solo si la IP no está cubierta. Ojo: la regla que necesitará el MCP es la
**IP de salida del entorno de Container Apps** donde se despliegue (F-006 pasó
a ser un servicio en cloud), no la IP de un puesto. No se crea hasta que ese
entorno exista.

```
az postgres flexible-server firewall-rule create -g rg-albaranes-dev -n psql-albaranes-rs9k2 --rule-name <uso>-<origen>-<AAAA-MM-DD> --start-ip-address <IP> --end-ip-address <IP>
az postgres flexible-server firewall-rule list -g rg-albaranes-dev -n psql-albaranes-rs9k2 -o table
```

**T17 · Huella local, antes de tocar Azure**, con el mes cerrado que fije el
humano (decisión abierta 5).

```
python main.py fingerprint-views --out progress/fingerprint_local.csv --periodo-hasta AAAA-MM
```

**T18 · Carga inicial contra Azure**, con el `.env` en el perfil Azure
(`PG_AUTO_CREATE_DB=false`, `PG_SET_ROLE=sigrid_dm_etl`, `PG_SSLMODE=require`,
`PG_USER=sigrid_dm_app`).

```
python main.py check-pg
python main.py run-all --full
python main.py build-cierre
python main.py build-maestros
python main.py build-compras
python main.py build-retenciones
python main.py apply-grants
```

**T19 · Medición y veredicto sobre el SKU (R31).** Escribir
`progress/medicion_carga_inicial.md` con tiempos por paso, tamaño por esquema y
una conclusión explícita: `Standard_B1ms` aguanta o hay que escalar. Es la
entrada de F-011.

```
python main.py timings --last 1
psql "host=<host> dbname=sigrid_dm user=<admin> sslmode=require" -f infra/sql/03_diagnostico.sql
```

**T20 · Verificación funcional (R20, R33, R36, R37).** Mismo commit a los dos
lados.

```
python main.py fingerprint-views --out progress/fingerprint_azure.csv --periodo-hasta AAAA-MM
python main.py compare-fingerprints progress/fingerprint_local.csv progress/fingerprint_azure.csv
psql "host=<host> dbname=sigrid_dm user=mcp_sigrid_dm_ro sslmode=require" -c "INSERT INTO mart.fact_seguimiento_mensual VALUES (1);"   # debe dar permission denied
psql "host=<host> dbname=albaranes user=mcp_sigrid_dm_ro sslmode=require" -c "\dt"                                                     # ninguna tabla legible
```

Y abrir el informe de Power BI contra `sigrid_dm` en Azure y refrescarlo.

## F-005 · decisiones del humano ya cerradas (2026-08-08)

1. **Entra NO se habilita** en `psql-albaranes-rs9k2`: es operación de servidor
   y afectaría a `albaranes` y `partes`, que están en uso. Plan B: roles
   nativos con contraseña en Key Vault. Cierra la decisión abierta 1.
2. **No se ejecuta `REVOKE CONNECT ... FROM PUBLIC`** en `albaranes` ni
   `partes`. **Riesgo aceptado y anotado**: `mcp_sigrid_dm_ro` podrá abrir
   sesión contra esas bases y leer su catálogo —nombres de tablas y columnas—,
   aunque no los datos. Cierra la decisión abierta 4.
3. **El MCP lee todos los esquemas de `sigrid_dm`**, no solo los cinco de
   consumo. Se revisará al rediseñar el MCP en F-006. Cierra la decisión
   abierta 3.
4. **F-006 pasa a ser un servicio en cloud, multi-base y en su propio
   repositorio.** Consecuencia para F-005: el rol de solo lectura lo usará un
   servicio en Azure, así que la regla de firewall será la IP de salida de un
   entorno de Container Apps. No se cablea ninguna IP de puesto.
5. **Identidad gestionada `id-datamart-seg-dev`**: sin Entra, F-005 ya no la
   necesita. Queda para F-003. Cierra la decisión abierta 2.

Sigue abierta la decisión 5 de la spec: **qué mes se toma como último cerrado**
para T17/T20. Lo fija el humano al ejecutar la verificación.

**F-004 · spec escrita** por el `spec-author` el 2026-08-08, pendiente de
aprobación del humano. Tres ficheros en
`specs/F-004-etl-sin-dependencias-locales/`: `requirements.md` (16 requisitos
EARS, todos con test trazable `test_f004_rN_*`), `design.md` y `tasks.md`
(T1–T11). No se ha tocado código. Decisiones abiertas más abajo.

**F-003 · spec escrita** por el `spec-author` el 2026-08-08, pendiente de
aprobación del humano. Tres ficheros en `specs/F-003-infra-caj/`:
`requirements.md` (26 requisitos EARS: 15 automáticos con pytest sin red ni
BBDD, 11 marcados `MANUAL (humano)` con su comando `az` exacto), `design.md` y
`tasks.md` (T1–T28). No se ha tocado código ni se ha ejecutado nada contra
Azure. Resumen y decisiones abiertas más abajo.

**F-005 · spec escrita** por el `spec-author` el 2026-08-08, pendiente de
aprobación del humano. Tres ficheros en `specs/F-005-postgres-azure/`:
`requirements.md` (41 requisitos EARS: 26 automáticos con pytest sin red ni
BBDD, 15 marcados `MANUAL (humano)` con su comando exacto), `design.md` y
`tasks.md` (T1–T21). No se ha tocado código ni se ha ejecutado nada contra
Azure. Resumen y decisiones abiertas más abajo.

F-009 cerrada el 2026-08-08, resumen en `progress/history.md`.

## F-005 · qué plantea la spec, en corto

- **La descripción de F-005 en `harness/features.json` está desfasada** y la
  spec lo señala en su primera línea: dice «aprovisionar el Flexible Server» y
  el diseño confirmado **reutiliza `psql-albaranes-rs9k2`**. Corregirla es T1.
  F-005 **no crea ningún servidor**: crea la base `sigrid_dm` dentro del que
  ya sirve a `albaranes` y `partes`.
- **Tres principales, dos roles de aplicación.** Un rol de **grupo**
  `sigrid_dm_etl` (NOLOGIN) es el **propietario** de la base y de todos sus
  objetos; son miembros suyos la identidad gestionada del job y la cuenta
  Entra del humano. Motivo: la carga inicial la lanza el humano desde su
  puesto (una identidad gestionada no se puede impersonar fuera de Azure) y la
  nocturna el job; si cada uno crea objetos con su propio principal, el otro
  no puede recrear las vistas. Con `SET ROLE` el dueño es siempre el mismo.
  El tercero es `mcp_sigrid_dm_ro`, de solo lectura.
- **El ETL con Entra, el MCP con contraseña.** Asimetría deliberada: el token
  de Entra caduca en ~1 h, lo cual va bien a un job y fatal a un cliente MCP
  de escritorio con cadena de conexión estática.
- **Hallazgo que matiza la frontera de seguridad.** Una base propia impide las
  consultas **entre** bases, pero **no impide conectar**: en PostgreSQL el
  privilegio `CONNECT` está concedido a `PUBLIC` por defecto, así que
  `mcp_sigrid_dm_ro` podría abrir sesión contra `albaranes` y leer el catálogo
  (nombres de tablas y columnas), aunque no los datos. Cerrarlo exige
  `REVOKE CONNECT ... FROM PUBLIC` en `albaranes`, que **toca otra base**.
- **Los permisos del MCP se destruyen en cada ejecución.** No es hipótesis:
  siete ficheros SQL de `mart`, `cierre` y `compras` hacen `DROP VIEW ...
  CASCADE` + `CREATE`, y un `DROP` se lleva los `GRANT`. Por eso la spec añade
  un paso `apply_grants` al final de `run-all` y un comando suelto, más
  `ALTER DEFAULT PRIVILEGES` como red de seguridad.
- **Se desactiva el auto-bootstrap contra Azure.** Hoy `PostgresClient` se
  conecta a la base `postgres` y ejecuta `CREATE DATABASE` si la suya no
  existe. Contra un servidor de producción compartido eso es un fallo
  esperando a ocurrir: `PG_AUTO_CREATE_DB=false` y la base la crea el humano.
- **Medición como requisito, no como consejo.** Los pasos pesados
  (`build_mart`, `build_cierre`) hoy **no dejan rastro** en `_meta.etl_runs`;
  solo lo hacen `ingest_raw` y `build_stg`. La spec instrumenta el
  orquestador y añade `python main.py timings`.
- **Verificación de vistas con criterio explícito.** Huella en tres bloques:
  *estructura* (igualdad exacta), *meses cerrados* (recuento exacto, sumas con
  tolerancia 0,01 €) y *vivo* (solo avisos, porque Sigrid sigue cambiando
  entre las dos capturas y `mart.v_pbi_dim_fecha` difiere por construcción, al
  generarse con `CURRENT_DATE`).
- Una sola dependencia nueva: `azure-identity`.

### F-005 · decisiones que el humano tiene que validar antes de la Fase 2

1. **Habilitar la autenticación Entra en `psql-albaranes-rs9k2` (T14).** Es
   una operación **de servidor**, no de base: afecta a `albaranes` y `partes`.
   Necesita autorización escrita y hacerse con `--password-auth Enabled` para
   no romper lo existente. Si se prefiere no tocarlo, plan B del runbook: rol
   nativo con contraseña en Key Vault, nunca en el repositorio.
2. **Quién crea `id-datamart-seg-dev`.** La spec de F-003 la lista entre sus
   recursos y a la vez dice que F-005 puede ir por delante. Propuesta de
   F-005: crearla ella de forma idempotente y que F-003 la reutilice.
3. **Hasta dónde lee el MCP.** La spec concede solo `mart`, `cierre`,
   `compras`, `maestro` y `retenciones`. Si el MCP de hoy consulta `raw` o
   `stg`, se quedaría corto — y no se puede comprobar porque **D4 sigue
   abierta**. Se cierra en F-006; mientras tanto es un parámetro
   (`PG_CONSUMPTION_SCHEMAS`).
4. **`REVOKE CONNECT ... FROM PUBLIC` en `albaranes` y `partes`.** Recomendado
   pero toca otras bases; decisión tras el diagnóstico de solo lectura de T12.
5. **Qué mes se toma como «último cerrado»** para la comparación exacta de
   vistas local ↔ Azure (T17/T20).

### F-005 · puertas bloqueantes que impone la spec

- **Espacio (T13)**: si quedan menos de **14 GB libres** de los 32 GB del
  servidor, la carga inicial **no empieza**. Ampliar almacenamiento es
  irreversible: el disco de un Flexible Server solo crece.
- **Medición (T19)**: `progress/medicion_carga_inicial.md` con tiempos por
  paso y veredicto explícito sobre si `Standard_B1ms` (1 vCPU, 2 GB) aguanta
  o hay que escalar. Es la entrada de F-011.
- **Recuperación**: queda escrito en el runbook que es «volver a ejecutar el
  ETL». El PITR es de **servidor entero** y restaurar arrastraría `albaranes`
  y `partes` al pasado, así que no es un mecanismo utilizable para
  `sigrid_dm`.

## F-003 · qué plantea la spec, en corto

- **`infra/` se reescribe**, no se completa. Los datos (nombres de recursos) se
  separan del procedimiento: `infra/env/<entorno>.json` es la única fuente de
  nombres y ningún `.ps1` contiene un nombre de recurso ni el literal del
  entorno. Crear `sta` o `pro` = añadir un fichero (D3). Se elige JSON porque
  PowerShell lo lee con `ConvertFrom-Json` y pytest lo valida sin ejecutar
  PowerShell: es lo que hace verificables sin red la mitad de los requisitos.
- **Identidad gestionada asignada por el usuario**, no por el sistema: con
  *system-assigned* hay huevo y gallina con `AcrPull` al crear el job, y recrear
  el job destruiría las asignaciones de rol y el rol Entra que F-005 crea en la
  base. Tres roles con ámbito de recurso: `AcrPull` sobre `acralbaranesdev`,
  `Key Vault Secrets User` y `Storage Blob Data Reader`.
- **Entorno de Container Apps sin VNet**, como `cae-albaranes-dev` y
  `cae-partes-dev`. Justificado: sin private endpoints ni zonas DNS privadas en
  la suscripción, integrar en VNet no acerca nada y quitaría la **IP pública
  estática de salida**, que es justo lo que necesita la regla de firewall del
  Postgres (D1, opción A).
- **Alerta de fallo por métrica** (`JobExecutionCount` con dimensión `Status`),
  con una alternativa acotada por consulta programada y el comando que decide
  cuál se usa. Reutiliza el action group de la landing zone; ninguna dirección
  de correo entra en el repositorio.
- El `--full` nocturno sigue viniendo del `CMD` del `Dockerfile`: el job no
  sobrescribe el comando de la imagen.

### F-003 · decisiones que el humano tiene que validar antes de implementar

1. **DA-3.1 · ¿La autenticación Entra contra PostgreSQL es de F-003 o de F-005?**
   Es la más importante. Hoy `PostgresSettings.conninfo` construye la cadena con
   una contraseña de `.env` y **sin `sslmode`**: tal cual, el job se desplegaría
   correctamente y **fallaría todas las noches al conectar**. La spec incluye el
   cambio mínimo (campos `auth_mode`/`sslmode`, un
   `etl_sigrid/infrastructure/postgres/entra_auth.py` y `azure-identity`, que
   F-004 ya declara), pero F-005 va por delante en el backlog y podría haberlo
   resuelto ya. Si ya está, T12–T15 se reducen a verificar.
2. **DA-3.2 · Autorización para la regla de firewall del Postgres.** El job entra
   por la IP estática del entorno, y esa regla es una **escritura sobre
   `psql-albaranes-rs9k2`**, recurso del proyecto `albaranes`. La ejecuta el
   humano. Aviso relacionado: el servidor ya tiene `AllowAzureServices`
   (`0.0.0.0`), que autoriza a cualquier recurso de Azure de cualquier tenant;
   el job podría funcionar sin regla propia, pero la spec no depende de ello y
   deja la revisión de esa regla para F-012.
3. **DA-3.3 · Nombre real del action group** que recibe hoy las alertas de coste y
   seguridad de la landing zone, para reutilizarlo. Si no se identifica, se crea
   uno propio y los destinatarios se pasan por parámetro al ejecutar el script.
4. **Nota, no decisión**: el ID de suscripción que hoy está en claro en
   `infra/00_vars.ps1:5` desaparece con la reescritura, pero **sigue en el
   historial de git**. No es una credencial y la spec no reescribe la historia;
   queda anotado para que el humano decida.

Prerrequisito de arranque: F-003 necesita de F-005 el host, el nombre de la base
y el nombre del rol del job. Sin los tres, la implementación debe marcar
`blocked` en vez de inventar valores.

## Pendiente de decisión del humano

1. **Borrado del stack abandonado — HECHO el 2026-08-08.** El humano decidió
   el alcance (**solo la base**) y no leer las tablas de control. Eliminada
   `sqldb-sigrid-ruesma-etl`; el servidor SQL queda con `master` y sin coste.
   El resto de `rg-sigridetl-dev-data` pasa a **F-012**. Nota: Azure conserva
   la base durante la ventana PITR (~7 días), así que los datos personales de
   `stg.age` siguen en copias hasta que caduque. Ver **D7**, cerrada.
2. **Diseño del despliegue en Azure** — **confirmado por el humano**. Es el
   marco de F-004 y del bloque F-003/F-005. Resumen abajo, sin cambios.
3. **La regla de firewall `dev-puesto-pgris-2026-08-08`** sigue puesta en
   `sql-sigridetl-dev-8yv7pj`. Decidir si se retira — irrelevante si se borra
   el resource group entero.
4. **Cuatro decisiones de la spec de F-004** (DA-4.1 a DA-4.4, justo debajo).

## Decisiones que necesita validar el humano — spec de F-004

**DA-4.1 · F-004 lee los Excels, pero NO los carga a `aux.*`. Es la decisión
importante.** Y hay un hallazgo detrás: la descripción de F-004 en
`harness/features.json` dice que «hoy `run-all` incluye `LoadExcelAuxStep`,
que lee los Excels desde rutas locales». **No es así.** El step es un *stub*
que devuelve `SKIPPED` con «No implementado todavía»; las variables
`AUX_EXCEL_*` existen pero **nadie las lee**. O sea: el pipeline no está roto
hoy en un contenedor por este motivo.

La spec propone que F-004 entregue la **capacidad de lectura** (puerto +
adaptador local + adaptador de blob + validación de que los tres libros se
abren) y que la carga a `aux.*` sea feature aparte, porque:

- las tablas destino no existen (`README.md` §5.2 las lista como «en el
  futuro»; el schema `aux` solo tiene `periodificacion_partida`, vacía), y
- **el esquema de los tres Excel no está en el repositorio**: ni columnas, ni
  hojas, ni las reglas que los mapean a `mart`.

Inventarlos sería el «workaround ante spec ambigua» que prohíbe `CLAUDE.md`.
**Si el humano prefiere que F-004 incluya la carga, hace falta que aporte los
tres ficheros o su estructura**, y la spec se reescribe con ese alcance.

**DA-4.2 · Sin variables configuradas → `SKIPPED`, no `FAILED`.** Propuesta:
«no me han dicho dónde está el fichero» deja el step en `SKIPPED` y no rompe
`run-all` (caso normal de un entorno recién clonado); «me han dicho dónde está
y no está» es `FAILED`. Confirmar que el job nocturno **no** debe fallar
cuando falta la configuración.

**DA-4.3 · Se rechaza el SAS en la URI.** Si `AUX_EXCEL_*` trae query string, el
ETL falla en el arranque remitiendo a la identidad gestionada, en vez de
aceptar el token. Un SAS en una variable de entorno es un secreto y caduca una
noche cualquiera. Confirmar que nadie contaba con usar SAS.

**DA-4.4 · Dependencias nuevas**: `azure-identity` y `azure-storage-blob` en
`requirements.txt` (~15 MB en la imagen). Es el único camino para
`DefaultAzureCredential`. Justificadas en `design.md` §7; el implementer no
puede añadirlas si esta línea no queda aprobada.

**Dependencia hacia F-003**: si el Container Apps Job usa identidad
*user-assigned*, F-003 debe inyectar `AZURE_CLIENT_ID` en el entorno del job.
El SDK la lee solo; no hace falta nada en `config/settings.py`.

**Verificación end-to-end aplazada**: los tres puntos MANUAL de
`tasks.md` exigen la storage account y el contenedor `aux`, que crea F-003.
F-004 se cierra con sus tests en verde; la prueba contra Azure queda pendiente.

## Diseño de despliegue propuesto (pendiente de confirmación)

No inventar infraestructura: el datamart es la cuarta pieza de un patrón que
ya funciona en producción con albaranes, partes y remesas.

- **Reutilizar** `psql-albaranes-rs9k2` creando la base `sigrid_dm`, y
  `acralbaranesdev` como registro de imágenes.
- **Crear** `rg-datamart-seg-dev` con su Container Apps Job, entorno, Key
  Vault, Log Analytics y una storage account con contenedor `aux` para los
  Excels auxiliares (cierra la parte que faltaba de D5).
- **Base propia, no esquema compartido**: PostgreSQL no permite consultas
  entre bases, así que el rol de solo lectura del MCP no puede ver
  `albaranes`, que contiene precios de proveedor y datos bancarios. Es una
  frontera real, no de disciplina. Si algún día hace falta cruzar datos entre
  proyectos, `postgres_fdw` dentro del mismo servidor.
- **Sin contraseñas**: identidad gestionada con `AcrPull`, `Key Vault Secrets
  User` y autenticación Entra contra PostgreSQL.
- **D1 → opción A** (endpoint público con reglas de firewall), que es lo que
  ya hace el servidor compartido para dos proyectos. La opción B parte de
  cero: no hay ni un private endpoint ni una zona DNS privada en toda la
  suscripción, y la VPN punto a sitio no está configurada.
- **D3 → parametrizar entorno desde el principio**, desplegar solo `dev`.
- **D6 → `0 2 * * *` UTC** y alerta de fallo por Azure Monitor al canal de
  correo que ya usan las alertas de coste de la landing zone.
- **No renombrar el servidor**: un Flexible Server no se puede renombrar, su
  nombre es su endpoint DNS. Se hará el día que otro motivo obligue a
  recrearlo, migrando las tres bases de una vez.

### Riesgos anotados

- `Standard_B1ms`: 1 vCPU y 2 GB de RAM para las transformaciones de `mart` y
  `cierre`. El job es nocturno y no compite con las apps, y escalar el SKU es
  un reinicio, no una migración — pero hay que medirlo en la primera carga.
- 32 GB compartidos con `albaranes` y `partes`. Sigrid son ~4 GB en origen,
  pero `raw` + `stg` + `mart` con índices puede irse a 10-12 GB. Comprobar
  espacio libre antes de la carga inicial. El almacenamiento solo crece.
- Sin HA y con 7 días de backup: la recuperación es «volver a ejecutar el
  ETL», no «restaurar». Asumible para un datamart regenerable.

### Cargas incrementales — hallazgo que condiciona F-004

**Sigrid no tiene marca de última modificación fiable**: en el diccionario,
`fecalt` aparece en 16 tablas, `fecmod` en 3 y `sello` en 2. No hay watermark
para un incremental directo. Palancas alternativas: ventana de negocio
(ejercicio en curso y obras abiertas, con recarga completa semanal) y altas
nuevas por `ide` autoincremental.

Sospecha a verificar: el cuello de botella probablemente **no** sea la base
sino la extracción — `sigrid-api` limita a 1.000 filas por petición y el
balanceador corta a los 230 s. Encaja con que el intento de abril muriera en
la ingesta.

**Recomendación: no construir el incremental todavía.** Instrumentar la
primera carga completa con tiempos por paso y por tabla, y decidir con
números.
