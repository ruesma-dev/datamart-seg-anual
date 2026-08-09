<!-- progress/impl_F-003.md -->
# F-003 · Infra: despliegue como Container Apps Job diario — Informe de implementación

Rama `feature/F-003-infra-caj`. Rigor **`critico`**. Tareas **T1–T17**
(bloques 1–4). Los bloques 5 (T18–T28) los ejecuta el humano contra Azure: **no
se ha ejecutado ni un comando `az` de escritura**, ni `python main.py` en
ninguna forma.

---

## 0. Lo que hay que leer aunque no se lea nada más

> ⚠ **Esta sección refleja el estado al terminar T17. Lo posterior está en §10
> (correcciones tras la review) y §11 (DA-4 aplicada, 2026-08-10).** Se conserva
> tal cual porque es lo que se entregó a revisión. **Al día de hoy: la puerta 1
> sigue cerrada y pasa a depender de `F-019`; la puerta 2 (DA-4) está resuelta
> con la opción B.**

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

> ✅ **CERRADA el 2026-08-10 con la opción B. Aplicada en §11.** Lo que sigue es
> el planteamiento tal como se elevó al humano; se conserva porque es el
> razonamiento sobre el que decidió.

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

> Números **al terminar T17**. Los de las dos rondas posteriores están en §10.4
> (tras la review) y §11.7 (tras DA-4). Estado final vigente: **258 tests**,
> 1,93 s, cobertura N/A con motivo, 0/0 mutantes.

| Evidencia | Valor real |
|---|---|
| **Tests ejecutados** | `python -m pytest -q` → **254 passed**, 0 failed (baseline en `dev`: 221; **+33** de F-003: 26 de infraestructura + 4 de autenticación Entra + **3 de la puerta de F-019**, §10) |
| **Tiempo de la suite** | **2,09 s** (`pytest -q`); 4,36 s bajo medición de cobertura dentro de `init.sh` |
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

- **29 tests que analizan los `.ps1` y el JSON como texto** y por introspección
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
- **T18–T28 (más T22 bis, §11): del humano.** T23 sigue bloqueada por `F-019`;
  DA-4 ya no bloquea (§11).
- `harness/features.json`: F-003 sigue en **`in_progress`**. No se marca `done`:
  falta el veredicto del reviewer y todo el bloque 5.

---

## 10. Correcciones tras la review (CHANGES_REQUESTED)

`progress/review_F-003.md` rechazó la feature por un solo defecto bloqueante:
**la puerta que impide armar el cron nocturno estaba condicionada a «hasta que
se decida qué hacer con el disco», y esa decisión ya se había tomado** —la
opción B, que es `F-019` en `harness/features.json`, creada el 2026-08-09—. Leída
al pie de la letra, la salvaguarda se daba por cumplida. Lo que protege de
repetir el incidente no es haber decidido: es haber **implementado** `F-019`.

### 10.1 Qué se cambió

| # | Fichero | Cambio |
|---|---|---|
| 1 | `infra/README.md` §«Antes de desplegar» | La condición pasa a ser **«hasta que `F-019` esté implementada y verificada contra Azure»**. Se dice explícitamente que la opción B ya está elegida y que lo que falta es ejecutarla. Se añade por qué las dos comprobaciones existentes no frenan hoy (el disco volvió al 42 %, y `dev.json` ya declara `entra`). El encabezado deja de llamarlas «decisiones abiertas» y las llama **puertas cerradas** |
| 2 | `infra/README.md`, tabla de orden | El paso 9 dice ahora «**está bloqueado por `F-019`**» |
| 3 | `progress/current.md` §«DOS PUERTAS…» punto 1 | Misma corrección. Antes decía «hasta que se decida entre A, B o C», que además contradecía a `features.json` |
| 4 | `specs/F-003-infra-caj/tasks.md` **T23** | Nota de bloqueo por `F-019`, con la misma forma que la de DA-2 en T22. Quien trabaje desde las tareas ya ve la puerta |
| 5 | `infra/80_create_job.ps1` cabecera y avisos | La puerta 1 del comentario nombra a `F-019`; el aviso de `-Confirmar` y el mensaje final dejan de hablar de «decidirse» |
| 6 | `infra/env/dev.json` | Nueva clave **`jobProgramable: false`** con su `$aviso_jobProgramable`: qué protege, por qué está en `false` y cuándo pasarla a `true` (`F-019` cerrada **y** verificada) |
| 7 | `infra/80_create_job.ps1` §1 Puertas | `if (-not $CFG.jobProgramable) { throw ... }` **antes que ninguna otra comprobación**, con el identificador `F-019` en el mensaje |
| 8 | `infra/00_vars.ps1` | `jobProgramable` entra en `$clavesObligatorias`: un entorno nuevo que la olvide **aborta**, no se queda sin puerta (fail-closed) |
| 9 | `tests/test_f003_infra.py` | `jobProgramable` en `CLAVES_OBLIGATORIAS` (la clave es **obligatoria**, coherente con R1/R2/R3) y **tres tests nuevos** |

La mejora del punto 2 —hacer la puerta **detectable por máquina**— la señalaba
el reviewer como «lo más robusto» sin exigirla; el líder la pidió. La razón de
fondo: `-Confirmar` demuestra que alguien quiso ejecutar el script, no que
supiera que la carga completa sigue sin caber en el servidor compartido.

**Qué NO se ha tocado**, por instrucción expresa: los demás scripts, DA-4 (la
está cerrando el humano) y los tests que ya pasaban.

### 10.2 Los tres tests nuevos

| Test | Qué sujeta |
|---|---|
| `test_f003_la_puerta_del_job_programado_es_detectable_por_maquina` | La clave es un **booleano** JSON (como cadena, `"false"` sería *cierto* en PowerShell y la puerta no frenaría nada), el script la comprueba con `throw` y lo hace **antes** de `az containerapp job create` |
| `test_f003_la_puerta_solo_se_abre_cuando_la_feature_bloqueante_esta_cerrada` | Si alguien pone `jobProgramable: true` con `F-019` sin `done` en `harness/features.json`, **la suite se pone en rojo**. Y si `F-019` desapareciera del fichero, también: una puerta no puede apuntar a una referencia muerta |
| `test_f003_la_puerta_nombra_la_feature_bloqueante_en_la_documentacion` | `infra/README.md` y `tasks.md` nombran `F-019`. Es el segundo afinado que propone la review: un identificador se contrasta con `features.json`; una condición en prosa envejece sola |

El segundo es la respuesta directa al defecto: la puerta ya no depende de una
decisión, sino de **una condición verificable y todavía no cumplida**.

### 10.3 Fase RED (obligatoria en `critico`)

**Paso 1 — los tres tests escritos antes de tocar nada más.**

```
$ python -m pytest tests/test_f003_infra.py -q

>       assert isinstance(cfg["jobProgramable"], bool), (
E       KeyError: 'jobProgramable'
tests\test_f003_infra.py:686: KeyError

>       if _config("dev")["jobProgramable"]:
E       KeyError: 'jobProgramable'
tests\test_f003_infra.py:723: KeyError

>       assert FEATURE_BLOQUEANTE in readme, (
E       AssertionError: infra/README.md no nombra F-019 al explicar por qué el job
        no debe quedar programado
tests\test_f003_infra.py:742: AssertionError

FAILED tests/test_f003_infra.py::test_f003_r1_dev_json_tiene_todas_las_claves_obligatorias
FAILED tests/test_f003_infra.py::test_f003_r2_todos_los_env_json_validan_igual[dev.json]
FAILED tests/test_f003_infra.py::test_f003_r3_ningun_valor_obligatorio_vacio_ni_TODO[dev.json]
FAILED tests/test_f003_infra.py::test_f003_la_puerta_del_job_programado_es_detectable_por_maquina
FAILED tests/test_f003_infra.py::test_f003_la_puerta_solo_se_abre_cuando_la_feature_bloqueante_esta_cerrada
FAILED tests/test_f003_infra.py::test_f003_la_puerta_nombra_la_feature_bloqueante_en_la_documentacion
6 failed, 23 passed in 0.67s
```

Los tres fallos de R1/R2/R3 son **parte del mismo rojo**: al declarar
`jobProgramable` obligatoria, el esquema del fichero de entorno deja de
cumplirse hasta que la clave existe. Es la consecuencia buscada de haberla hecho
obligatoria y no opcional.

**Paso 2 — con la clave ya en `dev.json` pero *sin* la puerta en el `.ps1`.**
Es el rojo que importa: demuestra que el test caza la ausencia del `throw`, no
solo la de la clave.

```
$ python -m pytest tests/test_f003_infra.py -q -k "puerta_del_job"

>       assert re.search(r"if\s*\(\s*-not\s+\$CFG\.jobProgramable\s*\)\s*\{[^}]*throw", texto), (
            "80_create_job.ps1 no aborta cuando el entorno declara jobProgramable = false"
        )
E       AssertionError: 80_create_job.ps1 no aborta cuando el entorno declara jobProgramable = false
E       assert None
E        +  where None = <function search ...>('if\\s*\\(\\s*-not\\s+\\$CFG\\.jobProgramable\\s*\\)\\s*\\{[^}]*throw', '# infra/80_create_job.ps1\n...')
tests\test_f003_infra.py:693: AssertionError

FAILED tests/test_f003_infra.py::test_f003_la_puerta_del_job_programado_es_detectable_por_maquina
1 failed, 28 deselected in 0.52s
```

**Paso 3 — verde, ya con la puerta y las tres correcciones de texto.**

```
$ python -m pytest tests/test_f003_infra.py -q
29 passed in 0.60s
```

Hubo un rojo intermedio no previsto que conviene dejar escrito, porque es el
tipo de cosa que se arregla mal: al nombrar `80_create_job.ps1` en el §1 del
README, `test_f003_r6_readme_menciona_todos_los_scripts_en_orden` falló
(`At index 0 diff: 2828 != 1523`) — el script quedaba mencionado antes que
`00_vars.ps1`. **No se tocó el test**: se reescribió la frase como «el script
del paso 9», que es como el README se refiere ya a los pasos.

### 10.4 Evidencias tras la corrección

| Evidencia | Valor real |
|---|---|
| **Tests ejecutados** | `python -m pytest -q` → **254 passed**, 0 failed (251 antes de la review, **+3**) |
| **Tiempo de la suite** | **2,09 s**; 4,36 s bajo cobertura dentro de `init.sh` |
| **Cobertura de las líneas cambiadas** | **N/A con motivo**, sin cambios: la corrección no añade ni una línea de Python de producción (`PUERTA COBERTURA: N/A (F-003: las líneas cambiadas no contienen sentencias ejecutables)`) |
| **Mutantes / supervivientes** | **0 / 0**. Campaña relanzada tras el cambio: `python -m harness.mutacion --feature F-003` → «1 fichero(s), 1 línea(s) de producción … 0 mutantes evaluados, 0 muertos, 0 supervivientes». El alcance sigue siendo `config/settings.py:40`, docstring |
| **`bash harness/init.sh`** | **ENTORNO LISTO**, exit 0 |
| **Avisos de `ruff` propios** | **0** (`ruff check tests/test_f003_infra.py` → *All checks passed*) |
| **Codificación de los `.ps1`** | Los dos scripts tocados se han parcheado **byte a byte** para no perder el BOM ni el CRLF; `test_f003_r5_ps1_utf8_bom_crlf_y_cabecera_de_ruta` en verde sobre los 13 |

### 10.5 Lo que sigue pendiente (no lo cierra esta corrección)

- **`F-019` sigue en `pending`.** La puerta está bien puesta, no abierta. T23 no
  se puede ejecutar.
- **DA-4 sigue abierta** y la decide el humano; no se ha tocado. *(Se cerró al
  día siguiente: ver §11.)*
- Las observaciones 3 y 5 de la review (las contraseñas de F-005 en el vault
  antiguo, el hallazgo anotado para F-016) siguen como estaban: no eran
  bloqueantes y no entraban en el encargo. *(La 3 entra en el alcance en §11.)*

---

## 11. DA-4 aplicada: opción B (2026-08-10)

El humano cerró DA-4 el 2026-08-10 con la **opción B**: el job se autentica
contra PostgreSQL como el rol nativo `sigrid_dm_app` **con su contraseña**, que
viaja como **referencia a Key Vault resuelta por la identidad gestionada** —el
mismo mecanismo que la clave de `sigrid-api`—. La opción A (habilitar Entra en el
servidor) queda descartada: es una operación de servidor que afecta a `albaranes`
y `partes`, ya rechazada el 2026-08-08.

Aprobó además **migrar las contraseñas al vault propio dentro de F-003**, lo que
cierra la deuda que la review señalaba en su observación 3.

### 11.1 La enmienda de la spec, fechada y sin borrar nada

`specs/F-003-infra-caj/requirements.md` gana una sección **§Enmiendas** con la
enmienda del 2026-08-10: qué cambia, por qué, **qué NO cambia** y una tabla de
requisitos afectados. Los textos originales **se conservan**:

- **R10** lleva ahora su texto original **citado en bloque** («no puede existir
  `PG_PASSWORD`… el único secreto del job…») y debajo el texto vigente. Se ve de
  un vistazo qué decía antes y qué dice ahora.
- El **bloque C (R12–R14)** lleva un aviso al principio: **implementado, probado
  y dormido**. No se borra ni se deja de verificar, porque es el camino de vuelta
  si algún día se habilita Entra. Sus cuatro tests siguen en verde.
- **R27, nuevo** [MANUAL]: la contraseña vive en el Key Vault del proyecto y la
  migración no puede exponer el valor.

Lo mismo se refleja donde el diseño se contradecía: `design.md` §5 (claves nuevas
del fichero de entorno y `pgAuthMode = "password"`), §6 (la llamada real con los
**dos** secretos) y la tabla de alternativas descartadas, donde «Contraseña de
Postgres en Key Vault» pasa a estar **tachada con la explicación del porqué se
revierte** —el razonamiento era bueno, pero daba por disponible un Entra que el
servidor no tiene—. Y en `tasks.md`, el bloque 3 avisa de que T12–T14 **no se
rehacen ni se revierten**.

**Por qué así y no reescribiendo los requisitos**: una spec que se reescribe
sobre la marcha deja de servir para juzgar el trabajo. Quien revise esto dentro
de seis meses tiene que poder ver que R10 decía otra cosa, quién cambió el
criterio y con qué argumento.

### 11.2 Qué cambia en el código

| Fichero | Cambio |
|---|---|
| `infra/env/dev.json` | `pgAuthMode`: `entra` → **`password`**. Tres claves nuevas —`pgSecretName` (el secreto en el vault), `pgJobSecretName` (cómo se llama dentro del job) y `pgReadonlySecretName` (la del MCP, que el job no usa pero la migración sí)— con un `$doc_secretos_pg` que aclara que son **nombres, nunca valores**. `$aviso_pgAuthMode` reescrito: cuenta la resolución, qué se descartó y **cómo se reactiva** el modo `entra` |
| `infra/00_vars.ps1` | Las tres claves entran en `$clavesObligatorias`: fail-closed |
| `infra/80_create_job.ps1` | Nuevo apartado **«2 bis»**: comprueba que el secreto de la contraseña está en el vault —**por nombre, sin leer el valor**—, y construye `$secretosJob` y `$varsAuth`. En modo `password` añade el segundo `keyvaultref` y `PG_PASSWORD=secretref:…`; en modo `entra` no genera ninguno de los dos. La puerta de DA-4 (`-ne "entra"` → `throw`) se convierte en **lista blanca** (`-notin @("password","entra")`), porque cerrar la decisión no es motivo para dejar pasar una errata |
| `infra/05_check_prereqs.ps1` | El `if/else` de DA-4 pasa a `switch` de tres ramas: `entra` mantiene íntegra la comprobación contra `authConfig.activeDirectoryAuth`, `password` informa de dónde saldrá el secreto, y `default` **falla** ante un modo inexistente |

El detalle que decide el diseño del script: las variables de entorno y los
secretos **se construyen antes** de llamar a `az`, en dos arrays. Alternativa
descartada: duplicar la llamada a `az containerapp job create` bajo un `if`. Dos
llamadas de veinte líneas que hay que mantener idénticas salvo en dos renglones
es exactamente cómo se termina programando el job con la CPU de un entorno y la
memoria de otro.

### 11.3 Lo que NO cambia, y es lo que sujeta la enmienda

La prohibición real de R10 nunca fue la palabra `PG_PASSWORD`: era que **un valor
de secreto no aparezca en el repositorio, en un script ni en una línea de
comandos**. Eso sigue igual de cerrado, y con tests:

- Ningún `--secrets` con valor literal: **todos** por `keyvaultref` + `identityref`.
- `PG_PASSWORD` solo admite `secretref:<nombre>`; cualquier otra cosa es un fallo.
- El script **no lee** el secreto: comprueba que el **nombre** está en
  `az keyvault secret list`. Sigue sin haber un solo `secret show` en `infra/`.

### 11.4 Los tests, y un fallo propio que la fase RED destapó

Cuatro tests nuevos y uno reescrito:

| Test | Qué sujeta |
|---|---|
| `test_f003_r10_ninguna_contrasena_literal_en_los_scripts` | Reescritura del antiguo `..._sin_pg_password_ni_secretos_literales_...`: mismo requisito, expresado sobre la invariante que sobrevive a la enmienda (valores, no nombres) |
| `test_f003_r10_la_contrasena_de_postgres_viaja_por_keyvaultref` | El mecanismo **está**: segundo secreto por `keyvaultref` + `identityref` y `PG_PASSWORD=secretref:$($CFG.pgJobSecretName)`. Sin este test, «no hay contraseñas» se cumpliría también borrándolo todo |
| `test_f003_r10_el_job_solo_admite_los_dos_modos_de_autenticacion_previstos` | La lista blanca de modos: un `pgAuthMode` con errata aborta |
| `test_f003_el_usuario_de_postgres_cuadra_con_el_modo_de_autenticacion` | Cierra la **observación 2 de la review**: en `entra` el usuario debe ser la identidad gestionada; en `password`, no puede serlo. Cambiar el modo sin cambiar el usuario deja la suite en rojo |
| `test_f003_los_prerrequisitos_comprueban_el_modo_de_autenticacion_declarado` | Que el modo `entra` no se quede sin red de seguridad al dejar de usarse |

**El fallo propio, que merece constar.** La primera versión del ayudante
`_valores_de_secretos` seguía las variables que aparecían **dentro** de un
literal entrecomillado, y con ello daba por «secreto literal» el
`$uriSecreto = "{0}secrets/{1}"`:

```
E   AssertionError: 80_create_job.ps1 pasa un secreto literal: '{0}secrets/{1}'
```

Era un falso positivo del test, no un defecto del script. Se corrigió tokenizando
el argumento (una cadena entrecomillada se consume entera antes de mirar si hay
variables) en vez de relajar la aserción, que era la salida fácil y la que habría
dejado el test sin morder.

El ayudante existe por una razón que conviene dejar escrita: al volverse
condicionales, los secretos pasaron a construirse en una variable, y un test que
solo mirase `--secrets "..."` se habría quedado **verde por no encontrar nada**,
que es la peor forma de estar verde.

### 11.5 Fase RED (nivel `critico`)

Los cinco tests, escritos y ejecutados **antes** de tocar el JSON y los scripts:

```
$ python -m pytest tests/test_f003_infra.py -q

E       AssertionError: en modo entra el usuario de Postgres tiene que ser el nombre
        de la identidad gestionada, que es lo que el servidor reconoce
E       assert 'sigrid_dm_app' == 'id-datamart-seg-dev'

E       AssertionError: el modo con contraseña no se reconoce
E       assert '"password"' in '# infra/05_check_prereqs.ps1\n...'

E       AssertionError: 80_create_job.ps1 no aborta ante un modo de autenticación desconocido
E       assert None

FAILED tests/test_f003_infra.py::test_f003_r1_dev_json_tiene_todas_las_claves_obligatorias
FAILED tests/test_f003_infra.py::test_f003_r1_los_ps1_no_contienen_nombres_de_recurso
FAILED tests/test_f003_infra.py::test_f003_r2_todos_los_env_json_validan_igual[dev.json]
FAILED tests/test_f003_infra.py::test_f003_r3_ningun_valor_obligatorio_vacio_ni_TODO[dev.json]
FAILED tests/test_f003_infra.py::test_f003_r10_el_job_solo_admite_los_dos_modos_de_autenticacion_previstos
FAILED tests/test_f003_infra.py::test_f003_el_usuario_de_postgres_cuadra_con_el_modo_de_autenticacion
FAILED tests/test_f003_infra.py::test_f003_los_prerrequisitos_comprueban_el_modo_de_autenticacion_declarado
7 failed, 25 passed, 1 skipped in 0.72s
```

Dos lecturas que importan de ese rojo:

- **El `1 skipped` es `test_f003_r10_la_contrasena_de_postgres_viaja_por_keyvaultref`.**
  Se salta solo mientras el entorno no declare modo `password`; en cuanto
  `dev.json` cambió, pasó a ejecutarse. Queda dicho para que nadie lo lea como
  un test que se salta siempre.
- `test_f003_r10_ninguna_contrasena_literal_en_los_scripts` **nació en verde** y
  siguió en verde: es la invariante que la enmienda **no** toca. Lo contrario
  sería la señal de alarma.

Y el verde, ya con `dev.json`, `00_vars.ps1`, `80_create_job.ps1` y
`05_check_prereqs.ps1` aplicados:

```
$ python -m pytest tests/test_f003_infra.py -q
33 passed in 0.59s
```

### 11.6 El paso 8 bis: migrar las contraseñas sin enseñarlas

`infra/README.md` gana el procedimiento, `tasks.md` la tarea **T22 bis** (antes
de T23) y `current.md` su fila en el guion. La forma elegida en PowerShell 5.1:
`show` **siempre asignado a una variable**, `set` con **`-o none`**, y la
variable a `$null` al terminar.

Lo que se descartó, y por qué —está escrito en el README, no solo aquí—:

- **Fichero temporal**: deja el valor en disco y, en PowerShell 5.1, la
  redirección añade BOM y salto de línea. No es solo menos seguro: **corrompe la
  contraseña**, y el job fallaría a autenticar con un error que no apunta a nada.
- **Canalizar `show` a `set --value @-`**: la tubería añade igualmente el salto
  de línea final. Mismo resultado.
- **`-o none` no es cosmético**: `az keyvault secret set` devuelve el objeto del
  secreto **con su valor**. Sin él, el paso que protege el secreto lo imprime.
- **Riesgo residual declarado**: durante la llamada, el valor está en la línea de
  comandos del proceso `az`, visible para otro proceso del mismo usuario en esa
  máquina. Se asume: es el puesto del administrador que ya conoce la contraseña,
  y las alternativas son peores.

Verificación por **nombre** (`secret list`), nunca `show`. Y las copias de
`kv-albaranes-rs9k2` **no se borran** hasta que el job complete una ejecución:
son la vuelta atrás.

### 11.7 Evidencias

| Evidencia | Valor real |
|---|---|
| **Tests ejecutados** | `python -m pytest -q` → **258 passed**, 0 failed (254 antes de la enmienda, **+4**) |
| **Tiempo de la suite** | **1,93 s**; 2,94 s bajo cobertura dentro de `init.sh` |
| **Cobertura de las líneas cambiadas** | **N/A con motivo**, sin cambios: la enmienda no añade Python de producción (`PUERTA COBERTURA: N/A (F-003: las líneas cambiadas no contienen sentencias ejecutables)`) |
| **Mutantes / supervivientes** | **0 / 0**. Campaña relanzada: «1 fichero(s), 1 línea(s) de producción … 0 mutantes evaluados, 0 muertos, 0 supervivientes» |
| **`bash harness/init.sh`** | **ENTORNO LISTO**, exit 0 |
| **Avisos de `ruff` propios** | **0** (`ruff check tests/test_f003_infra.py`). El total del repo sigue en 127, deuda previa |
| **Sintaxis de los 13 `.ps1`** | Validada con el parser de PowerShell **sin ejecutarlos**: 13 OK, incluidos el `switch` y los arrays nuevos |
| **Barrido de secretos** | `test_f003_r4_sin_secretos_ni_identificadores_en_infra_y_spec` en verde tras la enmienda: los nombres de secreto añadidos son nombres, y el README documenta el procedimiento **sin** ningún valor |

### 11.8 Lo que queda pendiente (al cerrar la ronda de DA-4)

- **T22 bis no está ejecutada**: la migración la hace el humano y necesita que
  exista `kv-datamart-seg-dev` (paso 6). El job aborta si el secreto falta, así
  que el orden está protegido por el propio script.
- **`F-019` sigue en `pending`** y sigue siendo la única puerta que bloquea T23.
- **En `kv-albaranes-rs9k2` siguen las copias**, y así debe ser hasta que el job
  funcione.
- No se ha ejecutado ni un `az` de escritura, ni `python main.py`, ni una
  conexión a la base o a la API.

---

## 12. Dos defectos reales encontrados desplegando (2026-08-10)

Los scripts estaban «probados como texto» y **no habían corrido nunca**. Al
ejecutarlos de verdad aparecieron dos defectos que ningún test textual podía
ver, los dos del intérprete y no de la lógica. Los dos se manifiestan **solo en
Windows PowerShell 5.1**, que es lo único que hay en el puesto: **`pwsh` no está
instalado**, comprobado. La suposición «esto correrá en PowerShell 7» estaba en
el aire y era falsa.

### 12.1 Defecto 1 · la consulta que `cmd.exe` parte por la mitad

**Síntoma** (paso 1 del bloque 5, `05_check_prereqs.ps1`):

```
az : No se esperaba -o en este momento.
```

**Causa.** La línea era:

```powershell
$consultaMetrica = "max(value[0].timeseries[0].data[?maximum!=null].maximum)"
... --query $consultaMetrica -o tsv
```

`az` en Windows es un **`.cmd`**, así que la línea ya expandida la vuelve a
interpretar `cmd.exe`. La expresión **no lleva espacios**, así que PowerShell no
la entrecomilla, y los paréntesis llegan crudos: `cmd` los toma por agrupación de
órdenes y se atraganta con lo que viene detrás. Que el mensaje culpe a `-o` es lo
que despista.

**Corrección.** La métrica se pide con `-o json` **sin filtro** y el máximo se
calcula en PowerShell recorriendo los puntos. Es más código y no depende de cómo
quede entrecomillado nada. Lo mismo con el filtro de roles de la §5, que llevaba
`[?…]` y `||`: ahora se piden los nombres (`[].roleDefinitionName`) y se filtran
con `-contains`.

**Verificado** con la carga real de la métrica, incluyendo huecos:

```
maximo calculado: 93.4 (esperado 93.4)     # datos con maximum:null intercalados
sin datos -> ocupacion nula: True          # caso degenerado, da el aviso
```

Los `93.4` no son un número al azar: es el porcentaje al que llegó el disco la
noche del incidente.

### 12.2 Defecto 2 · el script muere justo antes de crear lo que falta

**Síntoma** (paso 3, `20_create_observability.ps1`): el script terminó con
`NativeCommandError` y **el workspace no se creó**.

**Causa.** La comprobación de idempotencia era `az … show … 2>$null` seguida de
un `if ($LASTEXITCODE -eq 0 …)`. En 5.1, **redirigir el stderr de un ejecutable
nativo envuelve cada línea en un ErrorRecord**, y con
`$ErrorActionPreference = "Stop"` ese error es **terminante**. Como `az` contesta
`ResourceNotFound` por stderr, el patrón fallaba exactamente en el caso que venía
a cubrir: **el recurso todavía no existe**, que es el 100 % de un primer
despliegue. El mismo patrón estaba en **21 sitios** de 10 scripts.

**Comprobado en el puesto** (5.1.26100), con un `az` de mentira:

| Forma | ¿Aborta con `$ErrorActionPreference = "Stop"`? |
|---|---|
| `az … 2>$null` | **Sí** |
| `$x = az … 2>&1` | **Sí** |
| `az … 2>&1 \| Out-Null` | **Sí** |
| `az …` sin redirigir | No |
| `Invoke-Az` (preferencia bajada + captura) | No |

### 12.3 La corrección: un solo punto de entrada

`00_vars.ps1` define **`Invoke-Az`**, y **las 65 llamadas** de los 13 scripts
pasan por ella. Hace cuatro cosas, todas por un motivo que costó un despliegue:

1. Baja `$ErrorActionPreference` a `Continue` **solo durante la llamada** y lo
   restaura en un `finally` —si no, un fallo la dejaría bajada para el resto—.
2. Captura la salida y separa los ErrorRecord: devuelve la **salida estándar**
   como cadena y deja el mensaje de error en `$AzUltimoError`. `$LASTEXITCODE`
   se sigue consultando como siempre, así que **ningún sitio de llamada cambió
   su lógica**: solo el nombre del comando.
3. Añade `--only-show-errors`, para que los avisos de `az` no se cuelen en lo
   que el script interpreta.
4. Concentra en un sitio la regla de las consultas: ninguna `--query` lleva
   `(`, `?`, `|` ni `!`.

`Confirmar-Exito` ahora incluye `$AzUltimoError` en el mensaje: antes, con la
salida de error tragada, un fallo real se diagnosticaba a ciegas.

**Por qué una función y no «quitar el `2>$null`»**: quitar la redirección
también evita el aborto (está en la tabla), pero deja el error de `az` pintado en
rojo en la consola cada vez que se pregunta por algo que aún no existe —o sea,
todo el rato en un primer despliegue— y pierde el mensaje cuando sí importa.
Además, con la salida del host redirigida a un fichero el comportamiento vuelve a
cambiar. La función se comporta igual en los dos casos, y eso está probado.

### 12.4 Prueba de extremo a extremo, no solo textual

Con un `az` simulado (que responde `ResourceNotFound` mientras el recurso no
existe y lo «crea» después), ejecutando **el script real** con
`powershell -NoProfile -File`:

```
=== 20_create_observability.ps1 con el workspace INEXISTENTE (el caso que moria) ===
Creando el workspace 'log-datamart-seg-dev'...
Workspace listo. customerId = identificador-de-workspace
### codigo de salida: 0

=== segunda pasada: ahora ya existe (idempotencia) ===
El workspace 'log-datamart-seg-dev' ya existe; no se recrea.
### codigo de salida: 0
```

Y el contraste, con la versión anterior sacada de `git show HEAD:` y el mismo
`az` simulado:

```
az : ERROR: (ResourceNotFound) Workspace no encontrado
    + FullyQualifiedErrorId : NativeCommandError
### codigo de salida: 1
### se creo el workspace? False
```

Es el defecto reproducido y corregido, medido por los dos lados.

**Un riesgo que había que descartar antes de dar esto por bueno**: al pasar las
llamadas por una función, los argumentos que son **array** (`--tags`,
`--secrets`, `--env-vars`) llegan a `$args` como un elemento anidado. Comprobado
que el *splatting* los aplana igual: la línea que recibe `az` es **idéntica**
carácter a carácter a la de antes, tanto para los tags como para la forma mixta
del job (literal + array + literal). Si no lo fuera, los recursos se habrían
creado con las etiquetas mal puestas y nadie lo habría notado hasta la factura.

### 12.5 Tests que fijan la técnica

| Test | Qué impide |
|---|---|
| `test_f003_ninguna_consulta_a_az_lleva_metacaracteres_de_cmd` | Que vuelva a colarse un `--query` con `(`, `?`, `\|` o `!`. Resuelve también las consultas guardadas en variable, que son justo las largas |
| `test_f003_solo_el_ayudante_redirige_la_salida_de_error_de_az` | Un `2>$null` nuevo en cualquier script |
| `test_f003_todas_las_llamadas_a_az_pasan_por_el_ayudante` | Una llamada suelta a `az`, con su contraste: cada script debe seguir llamando a Azure por algún sitio |
| `test_f003_el_ayudante_de_az_esta_endurecido_para_powershell_51` | Que `Invoke-Az` pierda cualquiera de sus cuatro piezas (preferencia bajada, `finally`, `--only-show-errors`, `$AzUltimoError`) |
| `test_f003_los_prerrequisitos_siguen_midiendo_el_disco_del_servidor` | La salida fácil: dejar de tener consultas problemáticas dejando de comprobar cosas |

**Fase RED**, con la salida real antes de tocar los scripts:

```
E   AssertionError: 05_check_prereqs.ps1: la consulta
    'max(value[0].timeseries[0].data[?maximum!=null].maximum)' lleva ['!', '(', ')', '?'],
    que cmd.exe reinterpreta al invocar az.cmd. Pide -o json y filtra en PowerShell

E   AssertionError: 05_check_prereqs.ps1:45 redirige la salida de error: con
    ErrorActionPreference=Stop eso aborta el script en 5.1

E   AssertionError: no existe el ayudante Invoke-Az en 00_vars.ps1
```

**Dos defectos de los propios tests**, encontrados y corregidos sin relajar
ninguna aserción: no entendían los comentarios de bloque `<# … #>` de PowerShell
(señalaban la prosa que explica por qué no hay que llamar a `az` así) ni las
cadenas de texto (el mensaje «Ejecuta `az login`» no es una invocación). Un test
que da falsos positivos se acaba desactivando, y entonces no sujeta nada.

### 12.6 Además: `pwsh` no existe en el puesto

Todos los comandos de ejemplo pasan de `pwsh -File` a
**`powershell -NoProfile -File`**: `infra/README.md` (con una sección nueva que
explica las dos trampas y remite a `Invoke-Az`), `tasks.md`, `progress/current.md`
y `GUIA_USO_HARNESS.md`, más las cabeceras de tres scripts. Copiar y pegar un
comando con `pwsh` en ese puesto no arranca.

### 12.7 Evidencias

| Evidencia | Valor real |
|---|---|
| **Tests ejecutados** | **263 passed**, 0 failed (258 antes de esta ronda, **+5**) |
| **Tiempo de la suite** | **2,41 s**; 3,21 s bajo cobertura dentro de `init.sh` |
| **Cobertura de las líneas cambiadas** | **N/A con motivo**, sin cambios: la corrección es PowerShell y documentación |
| **Mutantes / supervivientes** | **0 / 0**, campaña relanzada |
| **`bash harness/init.sh`** | **ENTORNO LISTO**, exit 0 |
| **Sintaxis de los 13 `.ps1`** | 13 OK con el parser de PowerShell, tras convertir las 65 llamadas |
| **Ejecución real** | `20_create_observability.ps1` con `az` simulado: **crea y es idempotente**; la versión anterior, **muere sin crear** |
| **Avisos de `ruff` propios** | **0** |

### 12.8 Lo que esto deja pendiente

- Los scripts siguen **sin ejecutarse contra Azure de verdad**: lo probado es el
  intérprete, no las respuestas de la nube. Del paso 3 en adelante sigue siendo
  el humano quien ejecuta.
- Si aparece un tercer defecto de este tipo, el sitio donde arreglarlo ya es uno
  solo.
