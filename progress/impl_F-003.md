<!-- progress/impl_F-003.md -->
# F-003 · Infra: despliegue como Container Apps Job diario — Informe de implementación

Rama `feature/F-003-infra-caj`. Rigor **`critico`**. Tareas **T1–T17**
(bloques 1–4). Los bloques 5 (T18–T28) los ejecuta el humano contra Azure: **no
se ha ejecutado ni un comando `az` de escritura**, ni `python main.py` en
ninguna forma.

---

## 0. Lo que hay que leer aunque no se lea nada más

`infra/` está reescrito y completo, pero **el despliegue no debe empezar
todavía**. Hay dos puertas abiertas, y ninguna la puede cerrar un agente:

1. **El disco del servidor de Postgres.** El incidente del 2026-08-09 sigue sin
   resolverse y el job nocturno ejecuta exactamente la carga que llenó el
   disco. `80_create_job.ps1` exige `-Confirmar` y `05_check_prereqs.ps1` falla
   si la ocupación pasa del 60 %, pero la decisión (crecer el disco, trocear el
   `build_plan_mensual` o subir el SKU) es del humano.

2. **DA-4, nueva y bloqueante para T23.** La spec aprobada exige que el job no
   lleve contraseña (R10) y que la conexión use un token de Entra (R12), y así
   está escrito el fichero de entorno (`pgAuthMode = "entra"`). Pero
   **`psql-albaranes-rs9k2` tiene la autenticación Entra deshabilitada**: el
   humano descartó habilitarla el 2026-08-08 porque es una operación de
   servidor que afecta a `albaranes` y `partes`, y F-005 se desplegó con
   contraseña en Key Vault (`.env.example`, perfil Azure, lo documenta).
   Tal como está, **el job se crearía perfecto y fallaría al conectar todas las
   noches**. Detalle y salidas posibles en §5.

Ninguna de las dos se ha "resuelto por mi cuenta": los scripts se han escrito
cumpliendo la spec al pie de la letra, y las dos puertas se han hecho
**detectables por máquina** (una comprobación que falla) además de escritas.

---

## 1. Qué cambió

### Nuevo: `infra/env/dev.json`
Único sitio del repositorio con nombres de recurso. 42 claves + 7 tags
`acens-*`. Sin suscripción, sin tenant, sin claves, sin correos.

### Reescritos o creados en `infra/` (13 scripts)

| Script | Qué hace |
|---|---|
| `00_vars.ps1` | **Reescrito.** Carga y valida el fichero de entorno; aborta antes del primer `az`. Deriva `$PG_SERVER`, `$TAG`, `$IMG`, `$BUILD_DATE` y dos utilidades comunes. |
| `05_check_prereqs.ps1` | **Nuevo.** Solo lectura: sesión, extensión, registro, servidor de Postgres (modo de autenticación **y ocupación del disco**) y permiso para asignar roles. |
| `10_create_rg.ps1` | **Reescrito.** Resource group + tags. |
| `15_provision_db.ps1` | **Adaptado** (es de F-005): usaba variables de `00_vars.ps1` que ya no existen. |
| `20_create_observability.ps1` | **Nuevo.** Log Analytics propio. |
| `30_create_env.ps1` | **Nuevo.** Entorno de Container Apps sin red virtual; imprime la IP de salida. |
| `40_create_storage.ps1` | **Nuevo.** Cuenta endurecida + contenedor `aux`. |
| `50_create_keyvault.ps1` | **Nuevo.** Vault con RBAC, vacío. |
| `60_create_identity.ps1` | **Nuevo.** Identidad de usuario + tres permisos. |
| `70_build_image.ps1` | **Sustituye** a `20_build_image.ps1`. |
| `80_create_job.ps1` | **Sustituye** a `30_create_job.ps1`. |
| `85_update_job.ps1` | **Sustituye** a `40_update_job.ps1`. |
| `90_create_alert.ps1` | **Nuevo.** Grupo de acción + alerta de fallo. |

Borrados: `20_build_image.ps1`, `30_create_job.ps1`, `40_update_job.ps1`.
Los trece están en **UTF-8 con BOM y CRLF**, con su ruta en la primera línea, y
la sintaxis de todos se ha validado con el parser de PowerShell **sin
ejecutarlos** (`[System.Management.Automation.Language.Parser]::ParseFile`).

### Nuevos: tests
- `tests/test_f003_infra.py` — 26 tests (R1–R11, R16–R19, R25, R26).
- `tests/test_f003_pg_entra_auth.py` — 4 tests (R12–R14).

### Documentación
- `infra/README.md` — **nuevo**: orden, idempotencia, los tres pasos que exigen
  autorización del humano, KQL de logs, prueba de la alerta, cómo se añade un
  entorno y la deuda del ID de suscripción en el historial.
- `docs/ARCHITECTURE.md` §Infra — reescrita.
- `GUIA_USO_HARNESS.md` §4 — mandaba rellenar `TODO_` inexistentes y ejecutar
  tres scripts que ya no existen.
- `config/settings.py` — una línea de docstring: la referencia a
  `infra/20_build_image.ps1` (**única** línea de Python de producción tocada).

---

## 2. Decisiones de diseño (y por qué)

**Los nombres se prohíben en los `.ps1`, y hay un test que lo comprueba.**
`test_f003_r1_los_ps1_no_contienen_nombres_de_recurso` toma cada valor del
fichero de entorno y verifica que no aparece escrito en ningún script; su
contrario, `..._todos_los_scripts_leen_del_fichero_de_entorno`, exige que cada
script lea de `$CFG`. Sin el segundo, un script podría cumplir el primero por
no hacer nada.

**El contrato de variables del job se comprueba por introspección.**
`test_f003_r7_env_vars_del_job_existen_en_settings` extrae del script los
nombres literales `PG_*`, `SIGRID_API_*`, `AUX_EXCEL_*` y `LOG_*` y los cruza
con los campos reales de `config/settings.py`. Por eso los **nombres** están
escritos en el script y solo los **valores** salen de `$CFG`: si estuvieran
todos generados en un bucle, el test no podría comprobar nada, que es justo el
fallo silencioso de las 02:00 que R7 viene a evitar.

**Tres variables de entorno que el diseño no traía** y que van al job:
`PG_AUTO_CREATE_DB`, `PG_SET_ROLE` y `PG_READONLY_ROLE`. Son las salvaguardas
que F-005 puso contra el servidor compartido: sin la primera, el ETL podría
lanzar `CREATE DATABASE` en un servidor de producción ajeno; sin la tercera,
`apply_grants` es un no-op y el MCP perdería el acceso cada noche. Cubiertas
por `test_f003_r7_el_job_fija_las_salvaguardas_de_la_base_compartida`.

**`AZURE_CLIENT_ID`** (aviso del reviewer de F-004). La identidad es
*user-assigned*, así que `DefaultAzureCredential` no sabe cuál usar si nadie se
lo dice, y eso no se manifiesta hasta la primera lectura de un blob. No encaja
en el barrido de prefijos de R7 —es del SDK de Azure, no de `settings.py`— así
que tiene **test propio**, `test_f003_r7_el_job_inyecta_azure_client_id_de_la_identidad`.

**La URI del secreto se compone, no se lee.** `80_create_job.ps1` toma
`properties.vaultUri` del vault y le concatena el nombre del secreto; comprueba
que el secreto existe con `secret list` (nombres), nunca con `secret show`. El
valor del secreto no lo ve ningún script.

**Dos puertas activas, no solo avisos escritos.** `80_create_job.ps1` no hace
nada sin `-Confirmar` y se niega si el modo de autenticación no es el que puede
satisfacer sin contraseña; `05_check_prereqs.ps1` falla si el servidor no tiene
Entra habilitado o si el disco pasa del 60 %. Un aviso en un README se salta
solo; una comprobación que devuelve código 1, no.

**Idempotencia real, verificada por resultado.** Los scripts consultan antes de
crear, y `60_create_identity.ps1` no se fía del código de salida de
`role assignment create`: al final **lista** los roles y falla si falta alguno
—y avisa si aparece un cuarto, que es exceso de privilegio—. También espera a
que el directorio publique la identidad: sin esa espera, las asignaciones
fallan de forma intermitente con `PrincipalNotFound`.

---

## 3. Fase RED (nivel `critico`)

Los tests se escribieron **antes** que los scripts (T2 antes que T1 y T3–T17;
desviación de orden justificada en §6). Comando y salida reales:

```
$ python -m pytest tests/test_f003_infra.py tests/test_f003_pg_entra_auth.py -q --tb=line
...
24 failed, 6 passed in 0.56s
```

Extracto de la traza, con el GUID redactado en este informe (R4):

```
E   FileNotFoundError: [Errno 2] No such file or directory:
    '...\datamart-seg-anual\infra\env\dev.json'
E   AssertionError: 10_create_rg.ps1 no lee ningún valor de $CFG
    assert '$CFG.' in '# infra/10_create_rg.ps1\n# Crea el resource group y el
    Container Apps environment (una sola vez).\n. "$PSScriptRoot\...
E   AssertionError: 00_vars.ps1 debe admitir parámetros
E   AssertionError: 00_vars.ps1 no aborta nunca: falta el validador
    assert 'throw' in '# infra/00_vars.ps1\n# Única fuente de verdad de
    nombres/recursos del despliegue del datamart...
E   AssertionError: el repositorio contiene datos que no deben versionarse:
      infra/00_vars.ps1: GUID (suscripción o tenant) -> '<GUID-REDACTADO>'
E   AssertionError: 30_create_job.ps1 pasa una contraseña de Postgres
    assert 'PG_PASSWORD' not in '...    "PG_PASSWORD=secretref:pg-<redactado>" `
E   AssertionError: 10_create_rg.ps1 no usa CRLF
E   FileNotFoundError: ...\infra\80_create_job.ps1
E   FileNotFoundError: ...\infra\70_build_image.ps1
E   FileNotFoundError: ...\infra\30_create_env.ps1
E   FileNotFoundError: ...\infra\40_create_storage.ps1
E   FileNotFoundError: ...\infra\50_create_keyvault.ps1
E   FileNotFoundError: ...\infra\60_create_identity.ps1
E   FileNotFoundError: ...\infra\90_create_alert.ps1
FAILED test_f003_r1_dev_json_tiene_todas_las_claves_obligatorias
FAILED test_f003_r1_los_ps1_no_contienen_nombres_de_recurso
FAILED test_f003_r1_todos_los_scripts_leen_del_fichero_de_entorno
FAILED test_f003_r2_00_vars_resuelve_el_entorno_por_parametro_o_variable
FAILED test_f003_r2_todos_los_env_json_validan_igual[dev.json]
FAILED test_f003_r3_ningun_valor_obligatorio_vacio_ni_TODO[dev.json]
FAILED test_f003_r3_00_vars_valida_antes_de_llamar_a_az
FAILED test_f003_r4_sin_secretos_ni_identificadores_en_infra_y_spec
FAILED test_f003_r26_el_script_de_alerta_no_lleva_correos_literales
FAILED test_f003_r5_ps1_utf8_bom_crlf_y_cabecera_de_ruta
FAILED test_f003_r6_readme_menciona_todos_los_scripts_en_orden
FAILED test_f003_r7_env_vars_del_job_existen_en_settings
FAILED test_f003_r7_el_job_inyecta_azure_client_id_de_la_identidad
FAILED test_f003_r7_el_job_fija_las_salvaguardas_de_la_base_compartida
FAILED test_f003_r8_el_job_no_sobrescribe_el_comando_de_la_imagen
FAILED test_f003_r9_cron_del_entorno_dev_es_0_2
FAILED test_f003_r10_sin_pg_password_ni_secretos_literales_en_los_scripts
FAILED test_f003_r10_el_secreto_de_sigrid_se_pasa_por_keyvaultref
FAILED test_f003_r11_build_pasa_image_tag_y_build_date
FAILED test_f003_r16_el_entorno_no_se_integra_en_vnet
FAILED test_f003_r17_storage_endurecida
FAILED test_f003_r18_keyvault_rbac_y_sin_secreto_en_el_script
FAILED test_f003_r19_tres_roles_y_ningun_ambito_de_suscripcion
FAILED test_f003_r25_la_alerta_apunta_al_job_y_a_un_action_group
```

Lo que ese rojo demuestra, que es lo que importa: el barrido de secretos
**encontró de verdad** el ID de suscripción y la contraseña de marcador del
script viejo; el test de codificación detectó que los scripts anteriores no
cumplían CRLF; y el de R10 vio el `PG_PASSWORD` que el job viejo pasaba al
contenedor. No son tests escritos para pasar.

**Los 6 que nacieron en verde y por qué**: los 4 de `test_f003_pg_entra_auth.py`
(verifican código de F-005 que ya existía: DA-1) y dos que el `infra/` viejo ya
satisfacía por casualidad (`r8_dockerfile_cmd_es_run_all_full`, porque el
`Dockerfile` es de F-001/F-004 y ya era correcto, y
`r11_el_tag_es_fechado_y_no_latest`, porque el `00_vars.ps1` viejo ya derivaba
un tag fechado). Están declarados aquí para que no se lean como fase RED.

Estado final: **30 de 30 en verde**.

---

## 4. T12–T14 · DA-1 verificada, no reimplementada

El líder confirmó que F-005 ya implementó `PG_AUTH_MODE=entra`. Verificado:

| Qué | Resultado real |
|---|---|
| Módulo del token | **Existe**, pero no donde el diseño lo situaba: `etl_sigrid/infrastructure/azure/entra_token.py` (capa `azure`, no `postgres`), con clase `EntraTokenProvider` y caché con margen de 300 s, en vez de una función `get_access_token()`. |
| `config/settings.py` | `auth_mode` y `sslmode` presentes; `conninfo` y `admin_conninfo` **siguen siendo propiedades** (comprobado con `isinstance(..., property) → True`), como exigía el diseño para no tocar los cinco steps que las consumen. |
| `requirements.txt` | `azure-identity>=1.17` ya declarada por F-004. **No se duplica la línea.** |
| Tests | `pytest tests/test_f003_pg_entra_auth.py tests/test_f005_conexion.py -q` → **18 passed**. |

**Hueco real encontrado y tapado**: R13 exige que el modo `password` **no
importe** `azure-identity`, y ningún test de F-005 lo comprobaba (comprobaban
que el comportamiento no cambia, que no es lo mismo). `test_f003_r13_*` lo
verifica de dos formas: monkeypatch de `__import__` que revienta ante cualquier
`azure*`, y análisis con `ast` de que ninguno de los tres módulos importa
`azure` a nivel de módulo. R12 añade que `sslmode=require` viaja en la **misma**
cadena que el token, y R14 que un fallo de renovación no filtra el token ya
obtenido; ninguna de las dos cosas estaba comprobada.

**Hallazgo operativo**: `azure-identity` y `azure-storage-blob` están
declaradas en `requirements.txt` pero **no instaladas** en el intérprete del
puesto (`ModuleNotFoundError: No module named 'azure'`). No afecta a la suite
—los imports son perezosos y los tests usan dobles—, pero **la verificación
MANUAL 1 de F-004 fallará** hasta ejecutar `pip install -r requirements.txt`.
Anotado en `infra/README.md` y en el guion del humano.

---

## 5. DA-4 · la contradicción entre la spec y el servidor (BLOQUEA T23)

- **R10** prohíbe pasar contraseña alguna al contenedor: «el único secreto del
  job es la clave de `sigrid-api`». **R12** manda usar token de Entra.
- **La realidad**: `psql-albaranes-rs9k2` tiene la autenticación Entra
  deshabilitada. Habilitarla es una operación **de servidor** y ese servidor
  sirve a `albaranes` y `partes`; el humano lo descartó el 2026-08-08.
- Además, en modo `entra` el `PG_USER` tendría que ser el **nombre de la
  identidad gestionada**, no `sigrid_dm_app`, y ese rol **no existe** en la
  base: F-005 creó roles nativos.

Qué se ha hecho, y qué no:

- **No se ha improvisado un camino de contraseña**: habría violado R10 y su
  test. El fichero de entorno declara `entra`, como manda la spec.
- Se ha hecho **detectable**: `05_check_prereqs.ps1` falla si el entorno pide
  Entra y el servidor no la tiene; `80_create_job.ps1` se niega a crear el job
  si el modo no es `entra`.
- Queda **escrito en tres sitios**: `infra/env/dev.json` (`$aviso_pgAuthMode`),
  `infra/README.md` y aquí.

**Decide el humano**, y son las dos únicas salidas:
**(A)** habilitar Entra en el servidor —operación de servidor, afecta a dos
aplicaciones vivas, y hay que crear el rol de la identidad en `sigrid_dm`— o
**(B)** enmendar R10 para admitir la contraseña del rol nativo como referencia
a Key Vault, igual que la clave de la API. La (B) es coherente con lo que ya
hacen `albaranes` y `partes` y con la decisión del 2026-08-08; la (A) es lo que
dice la spec. **No se puede cerrar F-003 sin cerrar esto.**

---

## 6. Desviaciones respecto a la spec (todas justificadas)

1. **T2 antes que T1.** El nivel `critico` exige demostrar el rojo previo; con
   `dev.json` ya escrito, los tests de R1 habrían nacido verdes. Se ejecutó
   T2 → RED → T1. Es la regla «tests primero» del protocolo del implementer.

2. **Claves añadidas al fichero de entorno** sobre la lista de §3 del diseño:
   `pgSetRole`, `pgReadonlyRole`, `pgAutoCreateDb`, `pgResourceGroup`,
   `auxBlobs`, `jobSecretName`, `logRetentionDays`, `logLevel`, `logFormat`,
   `parallelism`, `replicaCompletionCount`. Las cuatro primeras son las
   salvaguardas de F-005 y el ámbito del servidor de Postgres; el resto evita
   literales en los scripts.

3. **`alertActionGroupResourceGroup` se acortó a `alertActionGroupRg`.** El
   nombre largo (29 caracteres alfanuméricos seguidos) **disparaba el falso
   positivo del barrido de base64 de `test_f005_r21`** y ponía `init.sh` en
   rojo. Es el hallazgo ya anotado para F-016. Se ha resuelto **sin tocar el
   test de otra feature**, igual que hizo F-004.

4. **El test de R2 comprueba el orden de resolución, no posiciones textuales.**
   La primera versión comparaba dónde aparecía `$Entorno` y dónde
   `$env:DATAMART_ENV`, y fallaba solo porque el comentario de uso del script
   nombra la variable de entorno antes que el parámetro. Se sustituyó por algo
   que mide lo que R2 dice: que el defecto se aplica **después** de consultar
   la variable.

5. **`15_provision_db.ps1` (de F-005) se adaptó.** No estaba en el alcance,
   pero dot-sourcea `00_vars.ps1` y usaba variables que la reescritura elimina:
   se habría roto en silencio, y además `test_f005_r21` exige que exista.

6. **`docs/referencia/04_azure_inventario_dev.md` conserva las menciones a
   `rg-seguimiento-dev`.** La verificación de T15 pedía que el `grep` saliera
   vacío en `docs` e `infra`; sale vacío salvo ese documento, que es un
   **inventario fechado** cuyo contenido es precisamente «ese grupo NO existe».
   Reescribirlo falsearía un registro externo. Las dos menciones vivas
   (`ARCHITECTURE.md`, `GUIA_USO_HARNESS.md`) sí se corrigieron.

7. **`GUIA_USO_HARNESS.md`**, fuera del alcance declarado, se corrigió: daba
   instrucciones de despliegue que ya no existen.

---

## 7. Verificaciones MANUAL pendientes (las ejecuta el humano)

Ninguna se ha ejecutado: escriben en Azure. El guion completo, con comandos y
orden, está en `progress/current.md` §F-003 y en `infra/README.md`.

| # | Qué | Requisito |
|---|---|---|
| 1 | `pwsh -File infra/05_check_prereqs.ps1` termina en código 0 | T4 |
| 2 | RG y tags; Log Analytics y entorno sin VNet; anotar la IP de salida | R15, R16 |
| 3 | Storage endurecida + contenedor; vault RBAC; identidad con **tres** roles | R17, R18, R19 |
| 4 | Cargar la clave de la API en el vault (`--file`, nunca `--value`) | T20 |
| 5 | Construir y publicar la imagen; anotar el tag | R20 |
| 6 | Regla de firewall para la IP del entorno — **escritura sobre un recurso de otro proyecto, autorización expresa** | R23 |
| 7 | Crear el job y comprobar disparo, identidad, registro y secreto | R21 |
| 8 | Ejecución de prueba `Succeeded` + `main.py version` coincide con el tag | R22 |
| 9 | Logs en Log Analytics con el KQL del README | R24 |
| 10 | Alerta creada **y correo recibido**; anotar hora del fallo y de recepción | R25 |
| 11 | Las **tres** verificaciones heredadas de F-004 (blob desde el puesto, blob desde el job, prueba negativa de permisos) | F-004 |

---

## 8. Evidencias

| Evidencia | Valor real |
|---|---|
| **Tests ejecutados** | `python -m pytest -q` → **251 passed**, 0 failed (baseline en `dev`: 221; **+30** de F-003: 26 de infraestructura + 4 de autenticación Entra) |
| **Tiempo de la suite** | **2,22 s** (`pytest -q`); 4,53 s bajo medición de cobertura dentro de `init.sh` |
| **Cobertura de las líneas cambiadas** | **N/A con motivo impreso** por `init.sh`: `PUERTA COBERTURA: N/A (F-003: las líneas cambiadas no contienen sentencias ejecutables)`. El alcance Python es **1 línea** (`config/settings.py:40`), y es una línea de docstring. El entregable de F-003 es PowerShell, JSON y documentación, que la puerta no mide por diseño (`harness/alcance.es_produccion` solo admite `.py`) |
| **Mutantes generados / supervivientes** | **0 / 0** (`progress/mutacion_F-003.md`). Alcance: 1 fichero, 1 línea. Cero mutantes porque esa única línea es docstring: no hay operador, literal ni condición que mutar |
| **`bash harness/init.sh`** | **ENTORNO LISTO**, exit 0 |
| **Avisos de `ruff` propios** | **0** (`ruff check tests/test_f003_infra.py tests/test_f003_pg_entra_auth.py` → *All checks passed*). El total del repo baja de 128 a 127 |
| **Sintaxis de los 13 `.ps1`** | Validada con el parser de PowerShell sin ejecutarlos: 13 OK |

### Justificación escrita del N/A de cobertura y del 0/0 de mutación (exigida en `critico`)

No es que las puertas se hayan saltado: es que **F-003 no añade código Python
de producción**. Toda su superficie son 13 scripts PowerShell, un fichero de
datos JSON y documentación, y el arnés —por diseño explícito de F-015— solo
mide y muta `.py` fuera de `tests/`, `specs/`, `progress/` y `docs/`. La
verificación equivalente que sí se ha hecho, y que es la que el reviewer debe
juzgar:

- **26 tests que analizan los `.ps1` y el JSON como texto** y por introspección
  de `config/settings.py`, con fase RED demostrada (§3): cubren R1–R11, R16–R19,
  R25 y R26.
- **4 tests de R12–R14** sobre el código de F-005 que el job va a usar, que
  cerraron un hueco real (§4).
- El único cambio en Python de producción es una línea de docstring; mutarla no
  produciría ningún mutante ni en un escenario ideal.

Si se quisiera una puerta de verdad sobre este tipo de entregable, la mejora
sería del arnés (mutar los `.ps1` o los ficheros de datos), no de esta feature.
Queda anotado como propuesta, no como deuda de F-003.

---

## 9. Estado

- **T1–T17: completas.** `tasks.md` marcado.
- **T18–T28: del humano**, y bloqueadas por el disco y por DA-4.
- `harness/features.json`: F-003 sigue en **`in_progress`**. No se marca `done`:
  falta el veredicto del reviewer y todo el bloque 5.
