<!-- specs/F-003-infra-caj/tasks.md -->
# F-003 · Infra: despliegue como Container Apps Job diario — Tareas

Rama: `feature/F-003-infra-caj`. Un commit por tarea (`F-003 Tn: ...`).
Las tareas **T18 en adelante** las ejecuta el **humano** contra Azure: ningún
agente escribe en Azure.

> **Antes de T1**: comprobar que F-004 y F-005 están cerradas y que
> `progress/history.md` recoge de F-005 el `pgHost`, el nombre de la base y el
> nombre del rol/usuario del job. Si falta cualquiera de los tres, **no
> improvisar valores**: marcar F-003 `blocked`, anotarlo en
> `progress/current.md` y parar.
> Resolver también **DA-1** (§9 del diseño) antes de llegar a T12.

## Bloque 1 — Andamiaje parametrizado (sin tocar Azure)

- [x] **T1**: Crear `infra/env/dev.json` con todas las claves obligatorias de
      §3 del diseño y los valores de `dev`.
      **Verificación**: `python -c "import json;json.load(open('infra/env/dev.json',encoding='utf-8'))"` y
      `pytest tests/test_f003_infra.py -k r1 -q` (falla mientras no exista T2).

- [x] **T2**: Escribir `tests/test_f003_infra.py` con los tests de R1–R6:
      claves obligatorias, ausencia de nombres de recurso y del literal del
      entorno en los `.ps1`, ausencia de valores vacíos o `TODO`, barrido de
      secretos/GUID/correos sobre `infra/` y `specs/F-003-infra-caj/`, y
      codificación UTF-8 BOM + CRLF + cabecera de ruta en los `.ps1`.
      **Verificación**: `pytest tests/test_f003_infra.py -q` (en rojo por los
      scripts todavía sin reescribir: es lo esperado, se documenta en el commit).

- [x] **T3**: Reescribir `infra/00_vars.ps1`: `param(-Entorno)`, resolución
      `-Entorno` → `$env:DATAMART_ENV` → `dev`, carga de `env/<entorno>.json`,
      validación de claves obligatorias con `throw` previo a cualquier `az`, y
      suscripción desde `$env:AZ_SUBSCRIPTION_ID` o del contexto de `az`.
      **Verificación**: `pytest tests/test_f003_infra.py -k "r1 or r2 or r3 or r4 or r5" -q` en verde.

- [x] **T4**: Crear `infra/05_check_prereqs.ps1` (solo lectura): sesión de `az`,
      suscripción, extensión `containerapp`, existencia del ACR, alcance del
      Postgres de F-005 y permiso para crear asignaciones de rol.
      **Verificación**: `pytest tests/test_f003_infra.py -k "r5" -q` +
      MANUAL (humano): `pwsh -File infra/05_check_prereqs.ps1` termina con
      diagnóstico y código 0.

## Bloque 2 — Scripts de aprovisionamiento (escritos, no ejecutados)

- [x] **T5**: `infra/10_create_rg.ps1` (RG + tags) y
      `infra/20_create_observability.ps1` (Log Analytics).
      **Verificación**: `pytest tests/test_f003_infra.py -k "r1 or r5" -q`.

- [x] **T6**: `infra/30_create_env.ps1` — Container Apps environment sin VNet,
      logs a Log Analytics, imprime `staticIp`.
      **Verificación**: test R1/R5 + test nuevo
      `test_f003_r16_el_entorno_no_se_integra_en_vnet` (el script no usa
      `--infrastructure-subnet-resource-id`).

- [x] **T7**: `infra/40_create_storage.ps1` — cuenta con
      `--allow-blob-public-access false`, `--allow-shared-key-access false`,
      `--min-tls-version TLS1_2`, y contenedor `aux` con `--auth-mode login`.
      **Verificación**: `test_f003_r17_storage_endurecida` (comprueba los tres
      flags en el script).

- [x] **T8**: `infra/50_create_keyvault.ps1` — vault con
      `--enable-rbac-authorization true`, sin cargar el secreto.
      **Verificación**: `test_f003_r18_keyvault_rbac_y_sin_secreto_en_el_script`.

- [x] **T9**: `infra/60_create_identity.ps1` — identidad asignada por el usuario
      y exactamente las tres asignaciones de rol de R19, cada una con su ámbito
      de recurso.
      **Verificación**: `test_f003_r19_tres_roles_y_ningun_ambito_de_suscripcion`.

- [x] **T10**: `infra/70_build_image.ps1` — `az acr build` contra
      `$CFG.acrResourceGroup` con `--build-arg IMAGE_TAG` y `BUILD_DATE`, tag
      fechado, sin `latest`.
      **Verificación**: `pytest tests/test_f003_infra.py -k r11 -q`.

- [x] **T11**: `infra/80_create_job.ps1` y `infra/85_update_job.ps1` — job según
      §5 del diseño: schedule, identidad, `--registry-identity`, secreto por
      `keyvaultref`, variables de entorno, y **sin** `--command`/`--args`.
      **Verificación**: `pytest tests/test_f003_infra.py -k "r7 or r8 or r9 or r10" -q`
      (R7 introspecciona `config/settings.py`, así que un nombre de variable mal
      escrito rompe el test).

## Bloque 3 — Autenticación Entra contra PostgreSQL

> ⚠ **ENMIENDA 2026-08-10 · DA-4 resuelta con la opción B.** Este bloque queda
> **implementado, probado y dormido**: el job **no** se autentica con Entra
> —el servidor la tiene deshabilitada y habilitarla afecta a `albaranes` y
> `partes`—, sino con la contraseña del rol nativo pasada como referencia a Key
> Vault. Las tareas T12–T14 **no se rehacen ni se revierten**: su verificación
> sigue siendo válida y sus tests siguen en verde, porque son el camino de
> vuelta si algún día se habilita Entra. Ver `requirements.md` §Enmiendas.

> Si **DA-1** se resuelve como «ya está en F-005», T12–T15 se reducen a
> verificar que los tests R12–R14 existen y pasan, y a anotarlo. No duplicar
> código.

> **DA-1 RESUELTA (2026-08-10): ya está en F-005.** T12, T13 y T14 son
> verificación; no se ha escrito ni una línea de código de producción. Lo
> verificado, con su resultado real, en `progress/impl_F-003.md` §T12–T14.
> El módulo NO está donde el diseño lo situaba: vive en
> `etl_sigrid/infrastructure/azure/entra_token.py` (capa `azure`, no
> `postgres`), con `EntraTokenProvider` en vez de una función suelta.
> Se añade `tests/test_f003_pg_entra_auth.py` con los tres tests trazables
> `test_f003_r12/r13/r14_*`, que cubren lo que los de F-005 no comprobaban:
> `sslmode=require` en la misma cadena que el token, que el modo `password`
> no importe `azure-identity`, y que un fallo de renovación no filtre el
> token ya obtenido.

- [x] **T12**: Crear `etl_sigrid/infrastructure/postgres/entra_auth.py` con
      `get_access_token()`, caché con margen de expiración y error legible que
      no filtra el token.
      **Verificación**: `pytest tests/test_f003_pg_entra_auth.py -k r14 -q`.

- [x] **T13**: Modificar `config/settings.py`: `auth_mode`, `sslmode`,
      `_resolve_password()` con import local, y `sslmode` en `conninfo` y
      `admin_conninfo` (que siguen siendo propiedades).
      **Verificación**: `pytest tests/test_f003_pg_entra_auth.py -q` (R12 y R13)
      y `pytest -q` completo sin regresiones en los tests existentes.

- [x] **T14**: Añadir `azure-identity>=1.17.0` a `requirements.txt` **si F-004 no
      la añadió ya** (su diseño la declara para leer los Excels del blob). No
      duplicar la línea.
      **Verificación**: `pip install -r requirements.txt` en el venv y
      `python -c "import azure.identity"`.

- [x] **T15**: Actualizar la sección «Infra» de `docs/ARCHITECTURE.md`
      (resource group real, `infra/env/<entorno>.json`, identidad gestionada,
      sin contraseñas).
      **Verificación**: revisión del reviewer; ninguna mención a
      `rg-seguimiento-dev` sobrevive (`grep -rn "rg-seguimiento-dev" docs infra`
      sin resultados).

## Bloque 4 — Alerta y documentación

- [x] **T16**: `infra/90_create_alert.ps1` — reutiliza el action group existente
      si lo hay; si no, lo crea con destinatarios pasados por `-AlertEmail`.
      Alerta de métrica según §6, con la alternativa de consulta programada
      documentada en comentario.
      **Verificación**: `pytest tests/test_f003_infra.py -k "r25 or r26" -q`
      (sin correos literales, alerta apuntando al job y a un action group).

- [x] **T17**: `infra/README.md` — orden de ejecución, idempotencia, pasos que
      exigen autorización del humano, KQL de logs de R24 y cómo añadir un
      entorno nuevo.
      **Verificación**: `pytest tests/test_f003_infra.py -k r6 -q`.

## Bloque 5 — Ejecución en Azure · MANUAL (humano)

Cada tarea de este bloque se anota con su salida real en `progress/current.md`.

- [ ] **T18**: Prerrequisitos y creación de la base de infraestructura.
      **Verificación**: MANUAL (humano):
      `pwsh -File infra/05_check_prereqs.ps1`, luego `10_create_rg.ps1`,
      `20_create_observability.ps1`, `30_create_env.ps1`; comprobar con los
      comandos de **R15** y **R16**. Anotar la `staticIp` del entorno.

- [ ] **T19**: Storage, Key Vault e identidad.
      **Verificación**: MANUAL (humano): `40_create_storage.ps1`,
      `50_create_keyvault.ps1`, `60_create_identity.ps1`; comprobar con **R17**
      y **R19**.

- [ ] **T20**: Cargar el secreto de `sigrid-api` en el vault. Requiere que el
      humano tenga `Key Vault Secrets Officer` sobre el vault (crearlo no lo
      concede).
      **Verificación**: MANUAL (humano):
      `az keyvault secret set --vault-name <kv> -n SIGRID-API-FUNCTION-KEY --file <ruta>`
      y después `az keyvault secret list --vault-name <kv> --query "[].name" -o tsv`.
      **Nunca `secret show`; el valor no se escribe en ningún fichero del
      repositorio ni en `progress/`.** Preferir `--file` a `--value` para no
      dejar el secreto en el historial del shell.

- [ ] **T21**: Construir y publicar la imagen.
      **Verificación**: MANUAL (humano): `pwsh -File infra/70_build_image.ps1`
      y comprobar con **R20**. Anotar el tag publicado.

- [ ] **T22**: Autorizar y crear la regla de firewall del Postgres para la IP
      estática de salida del entorno (**DA-2**: escritura sobre un recurso del
      proyecto `albaranes`).
      **Verificación**: MANUAL (humano): comando de **R23**, y después
      `az postgres flexible-server firewall-rule list -g rg-albaranes-dev -n psql-albaranes-rs9k2 -o table`.

- [ ] **T22 bis**: Migrar las contraseñas de Postgres al Key Vault del proyecto
      (**R27**, enmienda del 2026-08-10). Hoy viven en `kv-albaranes-rs9k2`, el
      vault de otro proyecto, desde F-005. Se migran las dos:
      `pg-sigrid-dm-app` (la que usa el job) y `pg-mcp-sigrid-dm-ro` (la del
      MCP). Va **antes** de T23: `80_create_job.ps1` aborta si el secreto no
      está en el vault del proyecto.
      **Verificación**: MANUAL (humano): procedimiento del **paso 8 bis** de
      `infra/README.md` —el valor no pasa por pantalla, ni por fichero, ni por
      el historial del shell— y después
      `az keyvault secret list --vault-name <keyVault> --query "[].name" -o tsv`,
      que debe listar los dos nombres. **Nunca `az keyvault secret show` suelto.**
      Las copias viejas en `kv-albaranes-rs9k2` **no se borran** hasta que el
      job haya funcionado (después de T24).

- [ ] **T23**: Crear el job. **BLOQUEADA POR `F-019`** (build de
      `stg.plan_mensual` por tramos): el job nocturno ejecuta la misma carga
      completa que llenó el disco del servidor compartido el 2026-08-09. La
      opción B ya está elegida —es `F-019`—, así que lo que falta no es
      decidir: es que esté **implementada y verificada contra Azure**. Mientras
      tanto `infra/env/dev.json` declara `jobProgramable: false` y
      `80_create_job.ps1` aborta con `throw`; abrir la puerta es poner esa
      clave a `true`, y hay un test que lo impide si `F-019` no está `done`.
      **Verificación**: MANUAL (humano): `pwsh -File infra/80_create_job.ps1` y
      comprobar con **R21**.

- [ ] **T24**: Ejecución de prueba y verificación de la build.
      **Verificación**: MANUAL (humano): los dos comandos de **R22**
      (`job start` normal y `job start --command python --args main.py,version`).
      Correcto si la ejecución completa termina `Succeeded` y la salida de
      `version` coincide con el tag de T21.

- [ ] **T25**: Verificar los logs en Log Analytics.
      **Verificación**: MANUAL (humano): consulta de **R24**. Si el nombre de
      columna no coincide, comprobar `ContainerAppConsoleLogs_CL | getschema` y
      corregir el KQL de `infra/README.md`.

- [ ] **T26**: Crear la alerta y **probar que el correo llega**.
      **Verificación**: MANUAL (humano): `pwsh -File infra/90_create_alert.ps1`
      (antes, la comprobación de métricas de §6:
      `az monitor metrics list-definitions --resource <job-id> -o table`), y
      después la prueba de fallo forzado de **R25**. Correcto **solo si se
      recibe el correo**; anotar hora del fallo y hora de recepción.

## Cierre

- [ ] **T27**: Anotar en `progress/current.md` el resultado de cada verificación
      MANUAL, las decisiones abiertas que queden (DA-1/DA-2/DA-3 con su
      resolución) y el ID de suscripción todavía presente en el historial de git
      (riesgo §9), para que el humano decida.
      **Verificación**: revisión del reviewer contra `CHECKPOINTS.md` C4.

- [ ] **T28**: Ejecutar `bash harness/init.sh` en verde.
      **Verificación**: exit code 0.
