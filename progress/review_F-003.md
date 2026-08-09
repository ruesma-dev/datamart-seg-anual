<!-- progress/review_F-003.md -->
# F-003 · Infra: despliegue como Container Apps Job diario — Review

**Veredicto: CHANGES_REQUESTED**

Un solo cambio bloqueante, y es de tres líneas de documentación. Todo lo
demás —los 13 scripts, los 30 tests, la fase RED, la trazabilidad, el barrido
de secretos, la codificación, el contrato de variables— está bien hecho y
verificado de forma independiente por este reviewer. El motivo del rechazo es
que **la salvaguarda del incidente del disco está redactada con una condición
que hoy ya se cumple**, así que la puerta que debía impedir armar el cron
nocturno se lee como abierta. Detalle en «Cambios requeridos» §1.

Alcance revisado: **T1–T17** (bloques 1–4). Las tareas T18–T28 las ejecuta el
humano contra Azure; se ha revisado que su guion esté **completo y listo**, no
que esté ejecutado. Los requisitos R15–R25 [MANUAL] se han validado como
«comando exacto documentado y pendiente del humano».

---

## Nivel de rigor y puertas que exige

**Declarado en `harness/features.json`: `critico`.** Verificado: el campo existe
y su valor es válido (`harness/rigor.json` admite `documental`, `estandar`,
`critico`; por defecto `critico`; umbral de cobertura 80 %).

`critico` exige: C1–C5 + C3 bis + tests trazables + **fase RED** + **cobertura**
de lo cambiado + **campaña de mutación** con supervivientes analizados +
**cero supervivientes** sin justificación aceptada + verificaciones
**MANUAL (humano)** listadas con su comando exacto.

---

## Verificaciones ejecutadas por el reviewer

| Qué | Comando | Resultado real |
|---|---|---|
| Arnés | `bash harness/init.sh` | **ENTORNO LISTO**, exit 0 |
| Suite | dentro de `init.sh` | **251 passed**, 24 warnings, 2,91 s |
| Puerta de cobertura | `init.sh` | `[OK] PUERTA COBERTURA: N/A (F-003: las líneas cambiadas no contienen sentencias ejecutables)` — **N/A con motivo impreso** |
| Alcance de mutación (recalculado) | `harness.alcance.alcance_de_feature('F-003')` | `lineas={'config/settings.py': {40}}` — 1 fichero, 1 línea. **Coincide** con `progress/mutacion_F-003.md` |
| Mutantes (recalculado, cálculo puro) | `harness.mutacion.generar_mutantes(fuente, {40}, 'config/settings.py')` | **0 mutantes**. **Coincide** con el informe (0/0). No se ejecutó ninguna campaña |
| Contenido de la línea 40 | lectura directa | `    build (ver infra/70_build_image.ps1). Ejecutando desde el repositorio no` — **es docstring**: el 0/0 es correcto, no es un informe escrito a mano |
| R5 sobre bytes | lectura binaria de los 13 `.ps1` | **13/13** con BOM UTF-8, CRLF sin un solo LF suelto, y primera línea `# infra/<fichero>.ps1` |
| R4 barrido propio | 6 patrones sobre `infra/` y `specs/F-003-infra-caj/` | **0 hallazgos reales** (detalle abajo) |
| R7 cruce independiente | extracción de los 16 nombres de `80_create_job.ps1` + introspección de `config/settings.py` | **15/15 con prefijo existen** en los modelos pydantic; `AZURE_CLIENT_ID` es del SDK y tiene test propio |
| R8/R10 | `grep` sobre `infra/` | **ningún** `--command`/`--args` en 80/85; **ningún** `PG_PASSWORD` ni valor literal de secreto |
| Tests sin red ni BBDD | `grep` de imports | **ninguno** de `requests`, `httpx`, `psycopg`, `urllib`, `socket`, `azure` en los dos ficheros de test |

### Barrido de secretos (R4 / C3 bis) — patrones y resultado

Patrones usados sobre `infra/**` y `specs/F-003-infra-caj/**`: GUID
(suscripción/tenant), correo electrónico, IPv4, `password|passwd|pwd|secret|
apikey|api_key|token|connectionstring` seguido de asignación, cadena
`postgres(ql)://`, y base64 de ≥40 caracteres.

**9 coincidencias, las 9 benignas y ninguna es un secreto:**

- `infra/15_provision_db.ps1:13,14` — `PWD = "<generada>` (marcador de
  documentación, no un valor).
- `infra/15_provision_db.ps1:97`, `infra/sql/02_roles.sql:10` — `$env:APP_PWD`,
  `$env:MCP_PWD`: referencias a variables de entorno, no valores.
- `infra/sql/02_roles.sql:45,46` — `PASSWORD :'app_pwd'`: variables de `psql`.
- `specs/F-003-infra-caj/requirements.md:288` — `0.0.0.0`, que es la mención a
  la regla `AllowAzureServices` y precisamente la advertencia de no depender
  de ella.

**Cero GUID, cero correos, cero claves, cero cadenas de conexión.** El
`$SUB` en claro que arrastraba el `infra/` viejo ha desaparecido del árbol de
trabajo, confirmado. Sigue en el historial de git: correctamente declarado como
deuda en `infra/README.md` §«Deuda conocida» y en `progress/current.md`, y es
decisión del humano.

---

## Checkpoints

### C1 — El arnés está completo y en verde

- [x] `bash harness/init.sh` termina con exit code 0. Ejecutado por el reviewer.
- [x] Existen `CLAUDE.md`, `harness/features.json`, `specs/SPECS.md`,
      `progress/current.md`, `progress/history.md`, `docs/ARCHITECTURE.md`,
      `docs/CONVENTIONS.md`. Verificado por `init.sh`.

### C2 — El estado es coherente

- [x] Una sola feature `in_progress`: `['F-003']`.
- [x] Rama actual `feature/F-003-infra-caj`, la de la feature en curso.
- [x] `progress/current.md` describe la sesión activa. Conserva secciones de
      F-004, F-005 y F-015 **cerradas**, pero no son restos: son pendientes
      vivos (las tres verificaciones MANUAL de F-004 bloqueadas hasta F-003, el
      incidente del disco, DA-1/DA-3). Se acepta.
- [x] Las features `done` tienen su resumen en `progress/history.md`.

### C3 — El código respeta arquitectura y convenciones

- [x] Dominio sin imports de infraestructura. F-003 no añade SQL ni toca
      capas: su entregable es PowerShell, JSON y documentación.
- [x] Primera línea de cada fichero Python con su ruta relativa. Verificado en
      `tests/test_f003_infra.py` y `tests/test_f003_pg_entra_auth.py`.
- [x] Sin `print()` de debug, sin TODOs sin contexto, sin secretos
      hardcodeados, sin dependencias nuevas (las coincidencias de `TODO` en el
      test son el literal que R3 busca, no deuda).
- [x] Semántica Sigrid: N/A justificado — F-003 no toca lógica de negocio ni
      SQL; el único cambio en Python de producción es una línea de docstring
      (`config/settings.py:40`).

### C3 bis — Documentos que entran de fuera

**N/A justificado por escrito**: el diff `dev...HEAD` no añade ni modifica
ningún fichero de `docs/referencia/` (28 ficheros tocados, ninguno bajo esa
ruta). El barrido de datos sensibles se ha ejecutado igualmente sobre `infra/`
y la spec por exigencia de R4, y su resultado consta arriba con los patrones.

### C4 — La verificación es real

- [x] Cada requisito [AUTO] tiene ≥1 test trazable `test_f003_rN_*` y todos
      pasan. Tabla completa abajo. R1–R14 y R26 cubiertos, más R16–R19 y R25,
      que además de MANUAL tienen comprobación textual del script.
- [x] Los tests no tocan red ni BBDD. **Cómo se comprobó**: barrido de imports
      (ni `requests`, ni `httpx`, ni `psycopg`, ni `urllib`, ni `socket`, ni
      `azure` en los dos ficheros); los de infraestructura leen `.ps1` y JSON
      como texto; los de Entra usan dobles y `monkeypatch` de `__import__`; y
      `azure-identity` **ni siquiera está instalada** en el intérprete, así que
      una llamada real reventaría con `ModuleNotFoundError`.
- [x] Las verificaciones MANUAL están listadas en `progress/current.md` con su
      comando, en la tabla «Guion del bloque 5 (T18–T28)», y el detalle exacto
      en `infra/README.md` y en `requirements.md` §D y §E.

### C4 bis — El rigor declarado se cumple

- [x] Declara `rigor: "critico"` en `harness/features.json`, valor válido.
- [x] **Fase RED**: `progress/impl_F-003.md` §3 trae la salida real
      (`24 failed, 6 passed in 0.56s`), la traza de los fallos y la lista
      nominal de los 24. Es rojo de verdad: el barrido encontró el ID de
      suscripción real y el `PG_PASSWORD` del job viejo, y el test de
      codificación cazó que los `.ps1` anteriores no cumplían CRLF. Además
      **declara los 6 que nacieron en verde y por qué**, que es exactamente lo
      que evita leer como RED lo que no lo era.
- [x] **Cobertura**: `init.sh` imprime `N/A` **con motivo**, y la justificación
      escrita está en `impl_F-003.md` §8. Verificado que el motivo es cierto:
      el alcance Python es 1 línea y es docstring.
- [x] **Mutación**: existe `progress/mutacion_F-003.md` generado por la
      herramienta. **Totales verificados de forma independiente**: alcance
      recalculado idéntico (`config/settings.py: {40}`) y mutantes
      recalculados = **0**. No hubo supervivientes que muestrear porque no hubo
      mutantes, y se ha confirmado la causa leyendo la línea: es docstring.
- [x] Cero supervivientes, ninguno en `PENDIENTE`. El 0/0 está justificado por
      escrito en el propio informe de mutación y en §8 del informe de
      implementación, y este reviewer lo da por bueno tras recalcularlo.
- [x] Sección **«Evidencias»** con los cuatro números: tests (251 passed),
      cobertura (N/A con motivo), mutantes/supervivientes (0/0) y tiempo de la
      suite (2,22 s; 4,53 s bajo cobertura).
- [x] Ningún punto marcado N/A sin justificación escrita.

### C5 — La sesión se cerró bien

- [x] `tasks.md`: **T1–T17 todas `[x]`**, con un commit `F-003 Tn: ...` por
      tarea (16 commits verificados en `git log dev..HEAD`; T8+T9, T12+T13+T14
      y T5 agrupan tareas afines en un commit, todos con el prefijo correcto).
      T18–T28 sin marcar es **N/A justificado**: son del humano contra Azure y
      quedan explícitamente fuera del alcance de esta implementación.
- [x] Sin ficheros temporales ni artefactos sin trackear: `git status` limpio.
- [x] `features.json` refleja el estado real: F-003 sigue en `in_progress`, no
      se ha marcado `done`. Correcto.

---

## Cobertura: requisito → test o comando

### Automáticos

| Req | Verificación | Estado |
|---|---|---|
| R1 | `test_f003_r1_dev_json_tiene_todas_las_claves_obligatorias`, `..._los_ps1_no_contienen_nombres_de_recurso`, `..._todos_los_scripts_leen_del_fichero_de_entorno` | verde |
| R2 | `test_f003_r2_00_vars_resuelve_el_entorno_por_parametro_o_variable`, `..._todos_los_env_json_validan_igual[dev.json]` | verde |
| R3 | `test_f003_r3_ningun_valor_obligatorio_vacio_ni_TODO[dev.json]`, `..._00_vars_valida_antes_de_llamar_a_az` | verde |
| R4 | `test_f003_r4_sin_secretos_ni_identificadores_en_infra_y_spec` + **barrido propio del reviewer** | verde |
| R5 | `test_f003_r5_ps1_utf8_bom_crlf_y_cabecera_de_ruta` + **comprobación propia sobre los bytes de los 13 ficheros** | verde |
| R6 | `test_f003_r6_readme_menciona_todos_los_scripts_en_orden` | verde |
| R7 | `test_f003_r7_env_vars_del_job_existen_en_settings`, `..._el_job_fija_las_salvaguardas_de_la_base_compartida`, `..._el_job_inyecta_azure_client_id_de_la_identidad` + **cruce propio** | verde |
| R8 | `test_f003_r8_dockerfile_cmd_es_run_all_full`, `..._el_job_no_sobrescribe_el_comando_de_la_imagen` | verde |
| R9 | `test_f003_r9_cron_del_entorno_dev_es_0_2` | verde |
| R10 | `test_f003_r10_sin_pg_password_ni_secretos_literales_en_los_scripts`, `..._el_secreto_de_sigrid_se_pasa_por_keyvaultref` | verde |
| R11 | `test_f003_r11_build_pasa_image_tag_y_build_date`, `..._el_tag_es_fechado_y_no_latest` | verde |
| R12 | `test_f003_r12_conninfo_entra_usa_token_y_sslmode_require` | verde |
| R13 | `test_f003_r13_modo_password_no_toca_entra`, `..._azure_identity_no_se_importa_al_cargar_la_configuracion` | verde |
| R14 | `test_f003_r14_fallo_de_token_aborta_sin_filtrar_el_token` | verde |
| R26 | `test_f003_r26_el_script_de_alerta_no_lleva_correos_literales` + el barrido de R4 | verde |

### Manuales (comando documentado, pendiente del humano)

| Req | Dónde está el comando exacto | Tarea |
|---|---|---|
| R15 | `requirements.md:175` (`az group show`) + `current.md` T18 | T18 |
| R16 | `requirements.md:188-189` + test textual `test_f003_r16_el_entorno_no_se_integra_en_vnet` | T18 |
| R17 | `requirements.md:200-201` + `test_f003_r17_storage_endurecida` | T19 |
| R18 | `requirements.md:213-214` + `test_f003_r18_keyvault_rbac_y_sin_secreto_en_el_script` | T19/T20 |
| R19 | `requirements.md:228-229` + `test_f003_r19_tres_roles_y_ningun_ambito_de_suscripcion` | T19 |
| R20 | `requirements.md:239` (`az acr repository show-tags`) | T21 |
| R21 | `requirements.md:250` (`az containerapp job show` con el `--query` completo) | T23 |
| R22 | `requirements.md:261-268` | T24 |
| R23 | `requirements.md:283-285` + `infra/README.md` §2 | T22 |
| R24 | `requirements.md:301` + KQL en `infra/README.md` | T25 |
| R25 | `requirements.md:314-321` + `test_f003_r25_la_alerta_apunta_al_job_y_a_un_action_group` | T26 |

Los once están recogidos en la tabla de `progress/current.md` §«Guion del
bloque 5» y en `progress/impl_F-003.md` §7, con el orden y lo que hay que
anotar de cada uno.

---

## Puntos calientes: resultado

**(a) `AZURE_CLIENT_ID` — INCORPORADO.** `infra/80_create_job.ps1:130` inyecta
`AZURE_CLIENT_ID=$($uami.clientId)`, tomado de `az identity show --query
clientId` en la misma llamada que resuelve el `id`. Tiene test propio,
`test_f003_r7_el_job_inyecta_azure_client_id_de_la_identidad`, y un comentario
en el script que explica por qué no encaja en el barrido de prefijos de R7 y
por qué su ausencia no se manifestaría hasta la primera lectura de un blob. La
advertencia del reviewer de F-004 está bien cerrada.

**(b) Las tres verificaciones MANUAL de F-004 — INTEGRADAS.** Aparecen en
`infra/README.md` §«Verificaciones heredadas de F-004» (con su ubicación en el
orden: después del paso 7), en la tabla del guion de `progress/current.md`
(fila «F-004», situada después de T19+T20) y en `impl_F-003.md` §7 fila 11.
Incluyen el aviso operativo de que `azure-identity` y `azure-storage-blob`
están declaradas pero no instaladas en el puesto, que es justo lo que haría
fallar la primera de las tres.

**(c) Salvaguarda del incidente de disco — INSUFICIENTE.** Ver §1 de «Cambios
requeridos». La puerta existe y está escrita en tres sitios, pero su condición
de apertura ya se cumple y la comprobación automática no la cubre.

**(d) R7 — CORRECTO, verificado de forma independiente.** Las 15 variables con
prefijo que el script pasa al contenedor existen todas en `config/settings.py`:
`SIGRID_API_BASE_URL`/`FUNCTION_KEY` → `SigridApiSettings(base_url,
function_key)`; `PG_HOST/PORT/DB/USER/AUTH_MODE/SET_ROLE/READONLY_ROLE/
AUTO_CREATE_DB` → `PostgresSettings`; `AUX_EXCEL_TIPO_PARTIDA/TIPO_COSTE/
MAPEO_PROPORCIONALES` → `AuxExcelSettings`; `LOG_LEVEL`/`LOG_FORMAT` →
`LoggingSettings`. **No se pasa `PG_PASSWORD`**, conforme a R10.

---

## Cambios requeridos

### 1. [BLOQUEANTE] La puerta del disco está condicionada a una decisión que ya se tomó

**Qué pasa.** La salvaguarda que impide armar el cron nocturno está redactada
así:

- `infra/README.md:26-28` — «Hasta que se decida qué hacer (crecer el disco,
  trocear la consulta que lo llena o subir el SKU), **el job no debe quedar
  programado**: no llegues al paso 9 de la tabla.»
- `progress/current.md:41-43` — «**NO crear el job programado (T23) hasta que
  se decida entre A, B o C.**»
- `infra/80_create_job.ps1:9-13` — «Hasta que el humano decida que hacer con el
  disco o con la consulta que lo llena, el job NO debe quedar programado.»

Pero **la decisión ya está tomada**. `harness/features.json` recoge F-019
(«Build de stg.plan_mensual por tramos»), creada el 2026-08-09 en el commit
`94137c3` de esta misma línea de trabajo, y su descripción dice literalmente:
«es la OPCION B elegida por el humano tras el incidente» y «desbloquea armar la
programacion del job de F-003». F-019 está en `pending`: elegida, **no
implementada**.

Es decir: hoy, alguien que lea el README y `current.md` al pie de la letra
concluye que la condición de la puerta se cumple —ya se decidió, fue B— y puede
llegar al paso 9. Y lo que protege de repetir el incidente no es haber decidido:
es haber **implementado** F-019.

**Por qué no lo tapan las comprobaciones automáticas.** Se ha revisado
`infra/05_check_prereqs.ps1:108-126`: la comprobación del disco falla si la
ocupación es **≥ 60 %**. Tras revertirse la transacción del incidente el disco
volvió a **42,3 %** (`progress/current.md:170-173`), así que hoy esa puerta
**pasaría**. Y `80_create_job.ps1` no comprueba el disco en absoluto: sus dos
puertas son `-Confirmar` y `pgAuthMode -eq "entra"` —y `dev.json:45` ya declara
`entra`, con lo que tampoco frena—. La única barrera real contra el disco es la
prosa, y la prosa está mal condicionada.

**Qué hay que hacer** (tres ediciones, ningún cambio de código):

1. `infra/README.md`, §«Antes de desplegar», punto 1: sustituir «Hasta que se
   decida qué hacer (…)» por la condición correcta, nombrando la feature —
   p. ej. «**Hasta que F-019 (build de `plan_mensual` por tramos) esté
   implementada y verificada contra Azure, el job no debe quedar programado**:
   no llegues al paso 9. La opción B ya está elegida; lo que falta es
   ejecutarla».
2. `progress/current.md`, §«DOS PUERTAS QUE BLOQUEAN EL BLOQUE 5», punto 1:
   misma corrección. Ahora dice «hasta que se decida entre A, B o C», lo que
   además contradice a `features.json`.
3. `specs/F-003-infra-caj/tasks.md`, **T23** (línea 173): hoy dice solo «Crear
   el job», sin ninguna nota de bloqueo. Quien trabaje desde `tasks.md` no ve
   la puerta. Añadir el aviso de que está bloqueada por F-019, como ya se hace
   con T22 y su DA-2.

Opcionalmente, y sería lo más robusto: hacer la puerta detectable por máquina
como se hizo con DA-4 —una clave `jobProgramable: false` en `infra/env/dev.json`
que `80_create_job.ps1` compruebe con un `throw`, o crear el job con
`--trigger-type Manual` hasta que F-019 cierre—. No lo exijo para aprobar; con
las tres correcciones de texto basta, porque `-Confirmar` sigue exigiendo un
acto deliberado.

---

## Observaciones que NO bloquean

1. **DA-4 está bien planteada y no es motivo de rechazo.** La contradicción
   entre R10/R12 (sin contraseña, token de Entra) y la realidad del servidor
   (`activeDirectoryAuth` deshabilitado, descartado por el humano el
   2026-08-08) se ha manejado como corresponde: no se improvisó un camino de
   contraseña que habría violado la spec y su test; se escribió el fichero de
   entorno como manda la spec; y se hizo **detectable por máquina** en dos
   sitios (`05_check_prereqs.ps1:94-104` aborta, `80_create_job.ps1:52-55`
   lanza `throw`). Las dos salidas (A: habilitar Entra; B: enmendar R10) están
   expuestas con sus consecuencias. Es exactamente lo que pide la regla de «no
   improvisar workarounds»: parar, dejarlo detectable y elevar la decisión.
   **El humano debe cerrarla antes de T23**, y F-003 no puede pasar a `done`
   sin eso.
2. **`pgUser: "sigrid_dm_app"` con `pgAuthMode: "entra"` es incoherente** —en
   modo Entra el usuario debe ser el nombre de la identidad gestionada—, pero
   está declarado como parte de DA-4 en `impl_F-003.md` §5 y en el
   `$aviso_pgAuthMode` del propio `dev.json`. Se resolverá con DA-4, sea cual
   sea la salida.
3. **Las contraseñas de F-005 siguen en `kv-albaranes-rs9k2`.**
   `progress/current.md:263-268` anota que F-003 «debe moverlas» a
   `kv-datamart-seg-dev`. Ese movimiento **no está en el guion del bloque 5**
   ni en `tasks.md`. Si la salida de DA-4 es la (B), esa migración se vuelve
   parte del camino crítico. Conviene decidir si entra en F-003 o se convierte
   en tarea propia, para que no se quede por inercia como avisa la nota.
4. **Desviaciones del implementer**: las siete de §6 del informe están
   justificadas y se aceptan. En particular, adaptar `15_provision_db.ps1`
   (de F-005) era obligado —dot-sourcea `00_vars.ps1`— y renombrar
   `alertActionGroupResourceGroup` → `alertActionGroupRg` para no disparar el
   falso positivo de `test_f005_r21` es la forma correcta de resolverlo: sin
   tocar el test de otra feature. El hallazgo sigue anotado para F-016.
5. **Calidad de los tests, por encima de lo exigido.** Merece constar:
   `test_f003_r1_todos_los_scripts_leen_del_fichero_de_entorno` es el
   contrapeso de `..._los_ps1_no_contienen_nombres_de_recurso` —sin él, un
   script vacío pasaría—; y R7 escribe los **nombres** de las variables en el
   script a propósito para que un test pueda cruzarlos con `settings.py`. Son
   decisiones de diseño de test, no tests escritos para pasar.
6. **`init.sh` avisa de 127 avisos de `ruff`** (deuda previa, no bloquea). Los
   ficheros nuevos de F-003 están a cero, verificado por el implementer.

---

## Automejora del protocolo (propuesta, no aplicada)

Este review ha encontrado el defecto bloqueante **por comparar la prosa de una
salvaguarda con el estado real de `features.json`**, no por ningún checkpoint.
`CHECKPOINTS.md` comprueba que las decisiones abiertas estén escritas, pero no
que su **condición de cierre siga siendo cierta**. Propongo añadir a C4 (o a
C2, que es donde vive la coherencia de estado):

> - [ ] Toda puerta o bloqueo que el informe declare abierto se expresa contra
>       una **condición verificable y todavía no cumplida** (una feature sin
>       cerrar, un valor medible), no contra «que el humano decida» cuando la
>       decisión ya consta en `harness/features.json` o en `progress/`.

Un segundo afinado, más barato: cuando una feature quede bloqueada por otra,
**nombrar el `F-XXX` bloqueante** en el README y en `tasks.md`, no describir el
problema. Un identificador se puede comprobar contra `features.json`; una
descripción en prosa, no.
