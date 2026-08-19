<!-- progress/decisiones_abiertas.md -->
# Decisiones abiertas · bloque Azure

Registro de las decisiones que el humano tiene que cerrar **antes** de que el
`spec-author` escriba las specs de F-004, F-005, F-003 y F-006. Ninguna
bloquea el trabajo ya terminado; todas bloquean el diseño del despliegue.

Estado: **pendientes de revisión por el humano** (aplazadas el 2026-08-08 a
petición suya, tras cerrar la integración de F-001 y el mantenimiento).

**Actualizado el 2026-08-08 con el inventario real de Azure (F-009).** Ese
inventario aporta datos a D1, D2, D3, D5 y D6, y abre una decisión nueva,
**D7**. No cierra ninguna por su cuenta: todas las que quedan requieren
criterio del humano. Fuente: `docs/referencia/04_azure_inventario_dev.md`.

Cuando se cierre una decisión, anótala aquí con su fecha y bórrala de la
lista de pendientes de la feature en `harness/features.json`.

---

## D1 · Acceso de red al Postgres de Azure — afecta a F-005, F-006

La más cara de cambiar a posteriori. El MCP corre en el puesto del usuario,
fuera de Azure, así que el Flexible Server tiene que ser alcanzable desde
fuera.

- **Opción A — acceso público con reglas de firewall por IP.** Rápido de
  montar. Expone el endpoint a Internet y exige que las IPs de salida de la
  oficina sean fijas.
- **Opción B — private endpoint + VPN.** Sin exposición pública. Más trabajo
  de red y el MCP solo funciona con la VPN levantada.

Sin cerrar esto no se puede diseñar F-005 ni verificar F-006.

> **Material nuevo (2026-08-08, F-008).** El diseño de acens en
> `docs/referencia/02_azure_landing_zone_acens.md` describe un hub&spoke en
> Spain Central con Azure Firewall (Basic), **VPN Site-to-Site permanente
> contra la red de la sede** y VPN SSL para puestos. La opción B ya no
> implica montar la VPN desde cero. Ojo: no se provisionan NSGs, el filtrado
> es del firewall central.

> **Material nuevo (2026-08-08, F-009 · inventario real).** Corrige en parte
> lo anterior. Ver `docs/referencia/04_azure_inventario_dev.md` §3.3, §3.5 y
> §5.3.
>
> - **La opción A ya está en uso y funcionando** para otro proyecto:
>   `psql-albaranes-rs9k2` (el único Postgres de la suscripción) tiene acceso
>   público con reglas por IP —la IP pública de la sede y una IP de puesto
>   individual— y sirve a las bases `albaranes` y `partes`.
> - **La opción B es más cara de lo que parecía.** En toda la suscripción hay
>   **cero private endpoints y cero zonas DNS privadas**: no hay nada de
>   Private Link montado sobre lo que apoyarse.
> - **La VPN SSL punto a sitio NO está configurada.** El diseño de acens la
>   promete, pero el gateway `vgw-hub-vpn-spaincentral` no tiene
>   configuración de cliente VPN (sin address pool ni protocolos). Solo está
>   la **S2S contra la sede**, que sí funciona (`Connected`, 12,7 GB de
>   tráfico). Es decir: hoy la opción B daría servicio al MCP **solo desde la
>   red de la oficina**, no desde un puesto remoto, salvo que se configure
>   además la P2S.
>
> **Sigue abierta**: es una decisión de criterio (exposición vs. coste de
> red) que el humano tiene que tomar. El inventario solo acota el terreno.

## D2 · Qué Azure Container Registry usar — afecta a F-003

`infra/00_vars.ps1` tiene `$ACR = "TODO_acr_existente"` con el comentario
«p.ej. el ACR compartido de albaranes», pero sin nombre real. Hace falta el
nombre del registro y confirmar que el Container Apps Job puede tirar de él.

> **Dato resuelto (2026-08-08, F-009).** Hay **exactamente un** Container
> Registry en toda la suscripción: **`acralbaranesdev`**
> (`acralbaranesdev.azurecr.io`), SKU **Basic**, en `rg-albaranes-dev`,
> creado el 2026-06-16, sin redundancia de zona. Es el «ACR compartido de
> albaranes» del comentario. Detalle en
> `docs/referencia/04_azure_inventario_dev.md` §5.1.
>
> **Tiene el usuario admin deshabilitado**, así que el Container Apps Job
> tendrá que autenticarse con **identidad gestionada + rol `AcrPull`**, no
> con usuario y contraseña. Eso es una restricción de diseño para F-003, no
> un impedimento.
>
> **Qué falta (criterio del humano):** decidir entre **(a)** reutilizar
> `acralbaranesdev` —un ACR nacido para otro proyecto pasaría a ser
> compartido, y en SKU Basic— o **(b)** crear un ACR propio del datamart.
> El dato ya está; la elección no la cierra el inventario.

## D3 · ¿Solo `dev`, o también producción? — afecta a F-003, F-005

Todo apunta hoy a `rg-seguimiento-dev`. Si va a haber un entorno productivo,
los scripts de `infra/` deben parametrizar el entorno desde el principio en
vez de duplicarse después.

> **Material nuevo (2026-08-08, F-008).** El diseño de acens ya contempla
> división por entorno **DEV/STA/PRO**, con rangos de red reservados para PRO
> y para DEV/POC, y despliegue por Terraform vía pipelines de Azure DevOps.
> Apunta a parametrizar `infra/` por entorno desde el principio.

> **Material nuevo (2026-08-08, F-009 · inventario real).** El andamiaje de
> PRO existe pero está vacío: hay `vnet-spoke-prod-spaincentral` con una
> subred y nada más. **No hay entorno STA** pese a que el diseño contempla
> DEV/STA/PRO, y **todos** los proyectos internos (`albaranes`, `partes`,
> `sigrid-api`, `sigridetl`) viven hoy en resource groups `-dev`. Es decir:
> montar PRO no requiere red nueva, pero hoy no hay ningún precedente de
> entorno productivo en la suscripción del que copiar.
>
> **Sigue abierta**: decisión de alcance del humano.

## D4 · Dónde vive el MCP — afecta a F-006

El MCP que hoy consulta el Postgres local **no está en este repositorio**
(verificado por búsqueda en el árbol). Hay que localizar su repositorio o su
configuración para poder repuntarlo y verificar que sus consultas siguen
funcionando contra Azure.

## D5 · Destino de los Excels auxiliares — afecta a F-004

`LoadExcelAuxStep` lee `TipoPartida.xlsx`, `TipoCoste.xlsx` y
`mapeo_proporcionales.xlsx` de rutas locales o de red vía `AUX_EXCEL_*`. En
un contenedor esas rutas no existen y `run-all` falla en el segundo paso.

Recomendación: llevarlos a Azure Blob Storage y que el step lea
indistintamente de ruta local o de blob. Falta confirmar la cuenta de
almacenamiento y quién mantiene esos ficheros.

> **Parcialmente cerrada el 2026-08-08.** El humano confirma que **los Excels
> auxiliares se suben a Azure**. El mecanismo de subida para gente de negocio
> (app web o sistema equivalente) se saca a feature propia, **F-010**, que
> depende de F-007; F-004 no la necesita, le basta con leer del blob aunque
> el fichero se suba a mano.
>
> Sigue pendiente: **qué storage account** concreta —debería salir del
> inventario de F-009— y **quién mantiene** los ficheros.

> **Resultado del inventario (2026-08-08, F-009): la storage account no
> existe todavía.** El inventario encontró **8 storage accounts** en la
> suscripción y **ninguna es «la del datamart»**: son las de `albaranes`,
> `partes`, `sigrid-api` y sus aplicaciones de RRHH, la del estado de
> Terraform de acens, una en westeurope (`ruesmapericial2026`) y la del
> intento anterior del ETL. Ver `docs/referencia/04_azure_inventario_dev.md`
> §4.1.
>
> `stsigridetldev8yv7pj`, la del stack `sigridetl`, es la candidata natural
> por nombre, pero **solo contiene los tres contenedores de infraestructura
> del Function App** (`deployment-package`, `azure-webjobs-hosts`,
> `azure-webjobs-secrets`), sin contenedor de datos ni ficheros de negocio, y
> sin tocar desde el 2026-04-17. **Los Excels auxiliares no están hoy en
> Azure.**
>
> Salvedad del inventario: la cuenta de usuario tiene permisos de plano de
> control pero **no rol de plano de datos** (`Storage Blob Data Reader`), así
> que solo se pudieron listar contenedores, no blobs. No se usó
> `--auth-mode key` porque habría implicado recuperar la clave de la cuenta.
> Para descartar por completo que algún Excel esté ya subido a otra cuenta,
> hace falta asignar ese rol.
>
> **Qué falta (criterio del humano):** decidir **(a)** crear una cuenta
> propia del datamart, **(b)** reutilizar `stsigridetldev8yv7pj` si se decide
> qué hacer con ese stack, o **(c)** colgarlo de la cuenta de otro proyecto.
> Y sigue sin respuesta **quién mantiene** los ficheros.

## D6 · Horario del job nocturno y avisos de fallo — afecta a F-003

`infra/00_vars.ps1` propone `0 3 * * *` (03:00 UTC, que en horario de verano
español son las 05:00). Falta confirmar la hora y decidir si se quiere aviso
—correo u otro canal— cuando el job falle. Sin aviso, un fallo nocturno pasa
inadvertido hasta que alguien mire Power BI.

> **Material nuevo (2026-08-08, F-009).** El intento anterior del ETL
> (`func-sigridetl-dev-8yv7pj`) estaba programado a las **02:30**
> (`FULL_ETL_CRON = 0 30 2 * * *`), no a las 03:00, y **no tenía configurada
> ninguna alerta de fallo**. Dato de contexto, no cierra la decisión.

## D7 · Qué hacer con `rg-sigridetl-dev-data` — NUEVA, afecta a F-003, F-005

Abierta por el inventario de F-009. **Ya existe un intento anterior de este
mismo ETL en Azure**, y hay que decidir qué se hace con él antes de desplegar
el nuevo. Detalle completo en `docs/referencia/04_azure_inventario_dev.md`
§2.

Qué es: un ETL de Sigrid con el mismo origen (`SIGRID_SOURCE_DATABASE=ruesma`,
esquema `dbo`) y el mismo modelo de capas (`raw` / `stg` / `etl`) que este
repositorio, pero **escribiendo en Azure SQL en vez de PostgreSQL** y
corriendo como **Azure Function programada** en vez de Container Apps Job.
Todo el resource group se creó el **2026-04-17 en cuatro minutos**.

Estado: **abandonado**. `FULL_ETL_ENABLED=false`, el Function App no tiene
funciones desplegadas, y la base `sqldb-sigrid-ruesma-etl` **lleva pausada
desde el 2026-04-18** —el día siguiente a crearse— sin una sola reanudación.
Pero **tiene ~174 MB de datos reales**: llegó a cargarse.

> **Esquema ya leído (2026-08-08).** El acceso se desbloqueó creando la regla
> de firewall `dev-puesto-pgris-2026-08-08` —escritura autorizada
> expresamente por el humano y ejecutada por el líder—. **La regla sigue
> puesta y hay que decidir si se retira.** El esquema completo está en
> `docs/referencia/04_azure_inventario_dev.md` §2.5, y la interpretación en
> §2.6. Lo que cambia respecto a la primera lectura:
>
> - **Nunca pasó de la ingesta.** Esquemas `raw`, `stg` y `etl` (control);
>   **no hay capa `mart`**, ni una sola vista, ni un procedimiento
>   almacenado, ni índices ni claves en las 40 tablas de datos. `stg` es un
>   espejo plano de `raw`. **El datamart no llegó a empezarse.**
> - **No era «el mismo ETL» de este repositorio.** De sus 20 tablas, solo **6**
>   coinciden con las 31 de `config/tables_sigrid.yaml`. Su catálogo gira en
>   torno a **mano de obra y recursos** (`hmo` + `hmores` = 201.329 de las
>   ~310.000 filas cargadas, más `res`, `emp`, `tar`, `auxhor`); el nuestro,
>   en torno a **obra, contratos, compras y facturación**. Falta incluso
>   `obr`. Parece un ETL de **control de horas**, no de seguimiento económico.
> - **Una sola tarde de trabajo.** Las 42 tablas se crearon el 2026-04-17
>   entre las 15:25 y las 20:06 UTC y **ninguna se modificó después**.
> - **Nada técnico que heredar.** Los datos están en Azure SQL (aquí somos
>   **PostgreSQL**) y son un volcado de Sigrid **regenerable** desde el
>   origen, no dato maestro. El DDL es T-SQL y además aquí se genera
>   dinámicamente. No hay lógica de transformación que portar. Se salvan dos
>   ideas que este repositorio **ya aplica**: auditoría por fila
>   (`__etl_run_id` / `__etl_loaded_at_utc` ≈ nuestro `_ingested_at` y
>   `_meta.etl_runs`) y **acceso con identidad gestionada**, que sí conviene
>   replicar en F-005.
> - **⚠ Hay datos personales y bancarios cargados.** `stg.age` (198 filas)
>   incluye columnas `ban`/`bancue` —**cuentas bancarias** de terceros—, `cif`,
>   `tel` y `ele`; `stg.res` (2.508 filas) incluye `cif`, `recema` y
>   `logacc`/`ideacc`. La tabla `emp` (con `dni` y `tarseg`) **está vacía**.
>   Todo ello en una base con acceso público habilitado, sin enmascaramiento
>   y con backup solo local, en un RG etiquetado `acens-compliance=gdpr`.
>   **Esto sube la urgencia de la decisión.**
>
> **Consecuencia para la decisión:** desmontarlo **no tiene coste de
> oportunidad técnico**. Lo único que se perdería es la respuesta a «por qué
> se paró», y esa respuesta está en las tablas de control, no en los datos.

Preguntas para el humano:

1. ¿Qué fue ese intento y **por qué se paró**? Sigue sin respuesta, pero ahora
   se sabe **dónde está**: en `etl.etl_run` (6 filas) y `etl.etl_table_run`
   (22 filas), cuyas columnas `status`, `message`, `rows_extracted`,
   `rows_loaded` y las marcas de tiempo dirían exactamente qué se ejecutó y
   qué falló. **No se leyeron** por la instrucción de no volcar contenido de
   tablas. Son 28 filas de telemetría del propio ETL, no datos de negocio:
   **basta una línea de autorización para cerrarlo.**
2. ¿Se conserva, se archiva o se borra? Ahora con dos datos nuevos: no hay
   nada técnico que heredar, y **contiene datos personales y bancarios** que
   nadie está vigilando.
3. **¿Se retira la regla de firewall `dev-puesto-pgris-2026-08-08`?** Sigue
   activa. Borrarla es una escritura y no está autorizada.
4. Si el datamart va a PostgreSQL (F-005), ¿el Azure SQL sobra del todo, o
   había un motivo para elegirlo? El esquema no da ninguna pista de que lo
   hubiera: no se usó ninguna capacidad específica de SQL Server.

## D8 · Dónde se persiste una planificación hecha por la IA — afecta a F-006, F-030

**Abierta el 2026-08-19.** El humano quiere pedirle a la IA una planificación
temporal, que la IA la resuelva con juicio (no hay regla determinista para
asignar partidas a meses) y luego corregirla de forma interactiva. Eso deja una
pregunta sin responder: **el resultado corregido, ¿dónde se guarda?**

Por qué no es un detalle:

- `mcp-bbdd` es **solo lectura por diseño**, y esa restricción es justo lo que
  permite dárselo a cualquier usuario sin miedo. Persistir una planificación es
  un camino de **escritura**.
- Sin persistencia no hay **traza** —qué repartió la IA, con qué criterio, qué
  corrigió el usuario— ni forma de **reanudar** mañana donde se dejó hoy. Una
  planificación que nadie puede auditar seis meses después es un número
  huérfano.

Las salidas que se ven, sin recomendar ninguna todavía:

1. **No se persiste**: el usuario se lleva el resultado como fichero. Lo más
   simple y lo más seguro; se pierde la traza y la continuidad.
2. **Tabla propia en el datamart**: encaja con que el dato viva donde vive el
   resto, pero obliga a decidir quién escribe y con qué rol, y este proyecto
   pasaría a tener una capa de escritura de usuario que hoy no tiene.
3. **Otro servicio con su propio permiso**: no relaja el MCP y aísla la
   escritura, a costa de una pieza más que mantener.

**Lo que no se hará**: relajar el MCP para que escriba. Perdería la garantía
que lo hace repartible a cualquiera.

---

## Decisiones ya cerradas

- **2026-08-08 · Backlog priorizado.** Aprobado el orden F-001, F-004, F-005,
  F-003, F-006, F-002, F-007. El bloque Azure pasa por delante de
  PLAN_VIGENTE.
- **2026-08-08 · Subagentes.** El humano confirma la autorización permanente
  de subagentes recogida en `CLAUDE.md`.

---

## Cierre del bloque Azure · 2026-08-08

El humano confirma el diseño de despliegue propuesto tras el inventario de
F-009. Con ello se cierran cinco decisiones y queda **D4** como única abierta.

- **D1 · CERRADA → opción A.** Endpoint público con reglas de firewall. Es lo
  que ya hace `psql-albaranes-rs9k2` en producción para `albaranes` y
  `partes`. La opción B partía de cero: cero private endpoints y cero zonas
  DNS privadas en toda la suscripción, y la VPN punto a sitio sin configurar,
  así que hoy ni siquiera serviría al MCP fuera de la oficina.
- **D2 · CERRADA → `acralbaranesdev`.** Único ACR de la suscripción. SKU
  Basic y usuario admin deshabilitado: el job tirará de identidad gestionada
  con `AcrPull`.
- **D3 · CERRADA → parametrizar el entorno desde el principio, desplegar solo
  `dev`.** Existe `rg-spoke-prod-spaincentral` y el diseño de acens ya prevé
  DEV/STA/PRO, así que parametrizar ahora es barato y duplicar scripts
  después, caro.
- **D5 · CERRADA.** Los Excels auxiliares van a Azure Blob Storage, en una
  cuenta nueva del proyecto con contenedor `aux`, dentro de
  `rg-datamart-seg-dev`. El mecanismo de subida para gente de negocio es
  **F-010**, que depende de la app web; F-004 solo necesita leer del blob.
- **D6 · CERRADA → `0 2 * * *` UTC** (04:00 en verano español, 03:00 en
  invierno) y alerta de fallo del job por Azure Monitor al mismo canal de
  correo que ya usan las alertas de coste y seguridad de la landing zone.
- **D7 · CERRADA.** El humano decide **no** leer las tablas de control y
  borrar. Se eliminó **solo la base** `sqldb-sigrid-ruesma-etl` el
  2026-08-08; el servidor SQL queda vacío y sin coste, y el resto de
  `rg-sigridetl-dev-data` pasa a **F-012** (auditoría y limpieza de costes).
  Nota: Azure conserva la base eliminada durante la ventana de retención
  PITR (~7 días), así que los datos personales de `stg.age` siguen en copias
  hasta que caduque.
- **D4 · SIGUE ABIERTA.** Dónde vive el repositorio o la configuración del
  MCP. Bloquea F-006.

Decisiones de diseño complementarias, sin número porque no estaban en la
lista:

- **Base de datos propia `sigrid_dm`**, no un esquema dentro de otra base.
  PostgreSQL no permite consultas entre bases, así que el rol de solo lectura
  del MCP no puede ver `albaranes` —precios de proveedor, facturas, datos
  bancarios—. Es una frontera real y no de disciplina. Si algún día hay que
  cruzar datos entre proyectos, `postgres_fdw` dentro del mismo servidor.
- **No renombrar `psql-albaranes-rs9k2`.** Un Flexible Server no se puede
  renombrar: el nombre es su endpoint DNS. Se hará el día que otro motivo
  obligue a recrearlo, migrando las tres bases de una vez.

---

## Decisiones del humano · 2026-08-08 (tarde)

- **DA-4.1 · CERRADA → F-004 SÍ carga los Excels a la base.** «Ya veremos
  dónde»: el destino concreto lo propone el líder. Estructura inspeccionada
  (solo lectura, los ficheros no se versionan): `TipoCoste` 108 filas
  (`ide`, `Nombre`, `subtipo`, `tipo`); `TipoPartida` 864 filas
  (`codigo partida`, `codigo obra`, `ide_tipo`, `ide`);
  `mapeo_proporcionales` 2.408 filas (`codigo_obra`, `ide`, `tipo de coste`,
  `porcentaje`). Son tablas pequeñas: ~3.400 filas en total.
  **Aviso**: `.env.example` apunta a `OneDrive - Construcciones Ruesma`, ruta
  que ya no existe. Los ficheros están hoy en
  `OneDrive - Ruesma/Documentos/Sigrid/tablas_auxiliares/`.

- **F-005 nº1 y nº4 · CERRADAS → NO se toca nada a nivel de servidor.** El
  humano: «las bbdd de partes y albaranes se están usando en las apps y no
  quiero romper eso, podemos seguir como hasta ahora». En consecuencia:
  - **No** se habilita autenticación Entra en `psql-albaranes-rs9k2`. El ETL
    usa un rol nativo de PostgreSQL con **contraseña en Key Vault**, que es
    exactamente lo que ya hacen `albaranes` y `partes` (`PG_PASSWORD` como
    referencia a Key Vault en la Container App).
  - **No** se ejecuta `REVOKE CONNECT ... FROM PUBLIC` sobre `albaranes` ni
    `partes`.
  - Coste asumido conscientemente: un secreto que rotar, y que
    `mcp_sigrid_dm_ro` pueda abrir sesión contra las otras bases y leer su
    catálogo (nombres de tablas y columnas, no datos). Revisable el día que
    haya un motivo que ya obligue a tocar el servidor.

- **F-005 nº3 · CERRADA → el MCP lee todo, de momento.** Sin restringir a los
  esquemas de consumo. Se revisará cuando se cierre D4 y se sepa qué consulta
  realmente el MCP.

---

## 2026-08-08 · D4 cerrada y salvedades del humano al aprobar las specs

- **D4 · CERRADA.** El MCP está en `C:\Users\pgris\PycharmProjects\mcp-bbdd`:
  prototipo local, arquitectura hexagonal, pipeline de validación de solo
  lectura y servicio de catálogo. **No es un repositorio git.**
- **El MCP pasa a cloud.** Decisión del humano: «debe ser accesible desde
  otros equipos sin que mi PC deba estar conectado; en local era una prueba».
  Y será **multi-base**, no solo `sigrid_dm`. En consecuencia vive en **su
  propio repositorio y su propio servicio**, y F-006 se reformula: de
  «repuntar el MCP» a «MCP de bases de datos como servicio en cloud».
- **Permisos del MCP, pregunta del humano resuelta.** Se destruyen cada noche
  porque el ETL reconstruye sus vistas con `DROP VIEW ... CASCADE` +
  `CREATE`, y en PostgreSQL los privilegios viven pegados al objeto. Se
  reconstruyen **automáticamente** por dos vías: `ALTER DEFAULT PRIVILEGES`
  para el rol propietario en cada esquema (mecanismo de fondo) y el paso
  `apply_grants` al final de `run-all` (red de seguridad para objetos
  previos, esquemas nuevos y objetos creados por otro rol). Sin intervención
  manual. Alternativa descartada: `CREATE OR REPLACE VIEW` conserva permisos
  pero no admite cambiar tipos, nombres ni orden de columnas.
- **Specs de F-005, F-003 y F-004 APROBADAS** por el humano. Arranca F-005.
