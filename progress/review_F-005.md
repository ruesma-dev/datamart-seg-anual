<!-- progress/review_F-005.md -->
# F-005 · Postgres del datamart en Azure — Review

Rama `feature/F-005-postgres-azure`, 14 commits sobre `dev` (13 de
implementación + 1 de corrección de review). Revisado el 2026-08-08 contra
`specs/F-005-postgres-azure/`, `CHECKPOINTS.md`, `docs/CONVENTIONS.md` y las
cuatro decisiones del humano de `progress/decisiones_abiertas.md`.

## Veredicto: **APPROVED**

> **Historial.** Primera pasada: `CHANGES_REQUESTED` por un único defecto —un
> byte NUL en `infra/00_vars.ps1`—. Corregido en el commit `b39b137` y
> **verificado por el reviewer** (§ «Verificación de la corrección»). Segunda
> pasada: **APPROVED**.

El trabajo es sólido. La parte crítica —que no se haya tocado Azure ni el
servidor compartido con `albaranes` y `partes`— está verificada y limpia, la
trazabilidad requisito→test es completa, y el runbook es ejecutable tal cual.

## Lo primero: ¿se ha escrito algo contra Azure o contra `psql-albaranes-rs9k2`?

**No. Verificado, no leído del informe.**

- Barrido de `az` sobre todas las líneas añadidas del diff: **todas** las
  invocaciones en modo escritura (`firewall-rule create`, `keyvault secret set`,
  `flexible-server update`) están dentro de documentación —
  `docs/runbook_postgres_azure.md`, `progress/current.md`, `specs/` — como
  instrucciones para el humano. Ninguna en código ejecutable.
- El único `.ps1` que habla con Azure es `infra/15_provision_db.ps1`, y sus dos
  llamadas (líneas 54 y 62) son `flexible-server show` y `firewall-rule list`,
  **solo lectura**. Sin `-Ejecutar` el script sale en la línea 75 sin escribir
  nada, y con `-Ejecutar` aún exige `APP_PWD`/`MCP_PWD` en el entorno (línea 79)
  antes de invocar `psql`.
- `CREATE DATABASE` aparece exactamente en dos sitios: `infra/sql/01_create_database.sql:47`
  (lo ejecuta el humano con `psql`, nunca el ETL) y `postgres_client.py:221`,
  alcanzable **solo** bajo `if self._auto_create_db` (línea 159). Con
  `PG_AUTO_CREATE_DB=false` la rama es `_assert_database_reachable()`, que abre
  una conexión contra la base destino y **jamás contra la admin**.
- Ni un `CREATE`/`ALTER`/`GRANT` ejecutado fuera del Postgres local. Las pruebas
  reales del implementer se hicieron en local con objetos sufijados
  (`sigrid_dm_f005test`) y borrados después.

Las cuatro decisiones del humano están aplicadas y **declaradas por escrito**
(`impl_F-005.md` §2 y §6, runbook §1 y §5 bis, `02_roles.sql` cabecera):
Entra implementado pero inactivo, sin `REVOKE CONNECT`, MCP leyendo los nueve
esquemas, nada ejecutado contra Azure. Ninguna de esas desviaciones es defecto.

## Barrido de secretos (ejecutado por el reviewer)

Patrones aplicados sobre las líneas añadidas del diff y sobre el árbol:
GUID de suscripción/tenant `[0-9a-f]{8}-...`, `(password|passwd|pwd|secret|token|api_key|clave)\s*[=:]\s*<valor>`,
IPv4 literales, base64 de 24+ caracteres, y un barrido de bytes NUL sobre
`git ls-files` completo.

| Ámbito | Resultado |
|---|---|
| Contraseñas / claves / tokens con valor | **Limpio** |
| Cadenas de conexión completas | **Limpio** (todas con `<host>`, `<admin>`, `$APP_PWD`) |
| IPs literales | **Limpio** (cero) |
| `.env.example` | **Limpio**: `PG_PASSWORD=` vacío; las seis variables nuevas documentadas |
| `infra/*.ps1`, `infra/sql/*.sql` | **Limpio**: contraseñas por `-v app_pwd=`, nunca literales |
| `progress/`, `specs/` | **Limpio** |

**Un hallazgo, no imputable a F-005:** `infra/00_vars.ps1:5` versiona el ID de
suscripción `$SUB = "863dfedd-..."`. Verificado con `git show dev:infra/00_vars.ps1`:
**ya estaba en `dev`**, F-005 no lo introdujo. Es deuda previa y queda como aviso
para el humano, no como cambio requerido de esta feature.

## Checkpoints

### C1 — El arnés está completo y en verde
- [x] `bash harness/init.sh` → exit code 0, **65 passed**.
- [x] Los ocho ficheros obligatorios existen.

### C2 — El estado es coherente
- [x] Una sola feature `in_progress` (F-005).
- [x] Rama `feature/F-005-postgres-azure`.
- [x] `progress/current.md`: el diff es **125 líneas añadidas, 0 borradas**, un
      bloque F-005 delimitado al principio. El contenido de F-003/F-004 que hay
      debajo es de la sesión de specs, ambas siguen abiertas: es estado vigente,
      no residuo.
- [x] N/A: F-005 no se cierra en esta review.

### C3 — El código respeta arquitectura y convenciones
- [x] `etl_sigrid/domain/` sin un solo import de infraestructura (verificado).
      Puerto `StepRunRecorder` en `application/ports.py`, adaptador en
      `infrastructure/` — hexagonal respetada. F-005 no añade SQL a ninguna capa
      de negocio, así que la numeración `NN_nombre.sql` no aplica.
- [x] Primera línea con su ruta relativa en los 14 ficheros `.py` nuevos y
      modificados (verificado uno a uno).
- [x] Sin `print()` de debug, sin TODOs sin contexto, sin secretos. Única
      dependencia nueva `azure-identity>=1.17`, **prevista** en `design.md` §3.
- [x] Semántica Sigrid intacta: F-005 no toca una línea de SQL de negocio.
- [x] `docs/CONVENTIONS.md:41` («PowerShell: UTF-8 con BOM y CRLF») —
      `infra/00_vars.ps1` cumple. **Estuvo vacío en la primera pasada** por un
      byte NUL en la posición 135; corregido en `b39b137` y verificado abajo.

### C3 bis — Documentos que entran de fuera
- [x] **N/A justificado**: F-005 no añade ni modifica ningún fichero de
      `docs/referencia/`. Verificado sobre el diff completo.

### C4 — La verificación es real
- [x] Los 26 requisitos automáticos tienen test trazable `test_f005_rN_*` y
      todos pasan (tabla abajo).
- [x] **Ningún test toca red ni BBDD.** Verificado: `psycopg.connect` está
      sustituido por un doble vía `monkeypatch` (`_instalar_psycopg_falso`), la
      credencial de Entra se inyecta, el CSV usa ficheros temporales. La única
      aparición del host de Azure en los tests es la constante
      `tests/test_f005_conexion.py:28`, usada para construir settings, no para
      conectar.
- [x] Las 15 verificaciones `MANUAL (humano)` están en `progress/current.md`
      (T12-T20) con su comando exacto, pendientes.

### C5 — La sesión se cerró bien
- [x] `tasks.md`: T1-T11 y T21 marcadas `[x]`, con **12 commits** `F-005 Tn: ...`,
      uno por tarea. T12-T20 siguen `[ ]` **legítimamente**: la propia spec las
      define como Fase 2 manual del humano contra Azure, que el implementer tiene
      prohibido ejecutar.
- [x] Árbol de trabajo limpio (`git status --porcelain` vacío).
- [x] `features.json`: F-005 `in_progress`, descripción corregida (R41).

## Cobertura requisito → test

Los 26 automáticos, todos en verde:

| Req | Test |
|---|---|
| R1 | `test_f005_r1_sslmode_por_defecto_segun_host` |
| R2 | `test_f005_r2_sslmode_debil_contra_azure_aborta` |
| R3 | `test_f005_r3_entra_usa_token_y_no_password` |
| R4 | `test_f005_r4_token_se_refresca_solo_cerca_de_caducar` |
| R5 | `test_f005_r5_sin_credencial_error_explicito_sin_fallback` + `..._sin_paquete_azure_identity_...` |
| R6 | `test_f005_r6_safe_dsn_redacta_password_y_token` |
| R7 | `test_f005_r7_set_role_es_la_primera_sentencia` |
| R8 | `test_f005_r8_modo_password_local_sin_regresion` |
| R9 | `test_f005_r9_sin_autocreate_no_toca_la_base_admin` |
| R10 | `test_f005_r10_base_ausente_mensaje_remite_al_runbook` |
| R11 | `test_f005_r11_barrido_estatico_sql_no_toca_otras_bases` |
| R14 | `test_f005_r14_grants_solo_sobre_los_esquemas_configurados` (+2) |
| R15 | `test_f005_r15_grants_incluyen_default_privileges` + `..._grant_connect_sobre_la_base_propia` |
| R16 | `test_f005_r16_run_all_incluye_el_paso_de_grants` + `..._con_el_propietario_correcto` |
| R17 | `test_f005_r17_sin_rol_configurado_el_paso_es_noop` |
| R18 | `test_f005_r18_rol_inexistente_avisa_y_no_falla` |
| R21 | `test_f005_r21_barrido_de_secretos_en_el_arbol` |
| R28 | `test_f005_r28_orquestador_registra_cada_paso` (+2) |
| R29 | `test_f005_r29_fallo_del_grabador_no_rompe_el_pipeline` |
| R30 | `test_f005_r30_timings_formatea_la_tabla` (+3) |
| R32 | `test_f005_r32_fingerprint_construye_las_consultas_esperadas` (+3) |
| R33 | `test_f005_r33_comparador_aplica_las_tolerancias` |
| R34 | `test_f005_r34_vista_ausente_en_un_lado_es_fallo` (+1) |
| R35 | `test_f005_r35_codigo_de_salida_segun_veredicto` (+1) |
| R40 | `test_f005_r40_ni_env_example_ni_infra_contienen_secretos` |
| R41 | `test_f005_r41_descripcion_de_la_feature_actualizada` |

Muestra verificada leyendo el cuerpo del test, no solo el nombre — **R7, R9,
R11, R21, R33, R35** (seis, incluidos los tres exigidos). Los seis contienen
aserciones reales y con contraste negativo; ninguno pasa trivialmente. Ejemplos:
R7 comprueba que `conexion.sentencias[0] == 'SET ROLE "sigrid_dm_etl"'` **y**
que sin rol no se emite ninguna; R9 comprueba que no aparece `dbname=postgres`
**y** contrasta que con `auto_create_db=True` sí; R33 verifica las cuatro filas
de la tabla de tolerancias de la spec, incluida la relativa `1e-9`.

**Requisitos `MANUAL (humano)`** (15): R12, R13, R19, R20, R22, R23, R25, R26,
R27, R36, R37 quedan pendientes en `current.md` T12-T20, correcto. Los de
**revisión documental del reviewer** los doy por cumplidos habiendo leído el
runbook: **R24** (§6, líneas 194-203: las reglas caducan al cambiar la IP, el
síntoma es *timeout* y no error de permisos, y el procedimiento de retirada),
**R38** (runbook completo con provisión, plan B, firewall, espacio, carga y
verificación), **R39** (§2: la recuperación es reejecutar el ETL; el PITR es de
servidor entero y arrastraría `albaranes` y `partes`), **R31** (§9 exige
veredicto explícito sobre el SKU).

## Los cinco puntos de presión

**1. `apply_grants` y `ALTER DEFAULT PRIVILEGES` — correcto, cubre los tres
casos, no solo el feliz.** Los dos mecanismos son complementarios y ambos están:
`GRANT SELECT ON ALL TABLES IN SCHEMA` (`grants.py:58`) cubre los objetos **ya
existentes**, incluidos los anteriores a los `GRANT`; `ALTER DEFAULT PRIVILEGES
FOR ROLE <owner>` (`grants.py:62-66`) cubre los **futuros**, y va `FOR ROLE` del
propietario del grupo, que es lo correcto: los privilegios por defecto se
declaran por rol creador, y los objetos nacen como `sigrid_dm_etl` gracias al
`SET ROLE`. **Esquemas nuevos**: `apply_readonly_grants` consulta
`list_schemas()` en cada ejecución (`postgres_client.py:469`), así que un
esquema creado después de la provisión se recoge en la siguiente pasada; el
filtro por esquemas existentes evita que el paso muera por `cierre`/`compras`
ausentes en una base recién creada, y los ausentes se registran con `warning`.
La coherencia de permisos también está: el paso corre con `SET ROLE
sigrid_dm_etl`, que es dueño de la base y de los objetos, así que tiene potestad
para el `GRANT CONNECT`, el `GRANT SELECT` y su propio `ALTER DEFAULT
PRIVILEGES`.

**2. `PG_AUTO_CREATE_DB=false` — ningún camino llega a `CREATE DATABASE`.**
Ya detallado arriba. El mensaje de error de `_assert_database_reachable`
(`postgres_client.py:181-189`) remite a `01_create_database.sql` y al runbook y
pasa la cadena por `safe_dsn`, así que ni ahí se filtra la contraseña.

**Mención especial, y es un acierto de calado:** `client_factory.py` no estaba en
la spec. Sin él, los cinco steps seguían construyendo su `PostgresClient` con
`settings.postgres.conninfo` pelado y **se habrían saltado `PG_SET_ROLE` y
`PG_AUTO_CREATE_DB`** — es decir, R7 y R9 se cumplirían en `main.py` y se
incumplirían justo en el pipeline nocturno contra producción. La desviación está
declarada en `impl_F-005.md` §4 y §6.5. Bien visto.

**3. El runbook (§7 del informe) — orden correcto, idempotencia declarada,
irreversible marcado.** El orden 0→11 es ejecutable tal cual: prohibiciones,
autenticación, recuperación, **puerta de espacio antes de nada**, contraseñas a
Key Vault, base y roles, firewall, configuración del `.env`, carga, medición,
verificación, frontera de seguridad. Lo irreversible está señalado donde toca
(§0 y §3: ampliar almacenamiento solo crece) y lo reversible también (§5:
scripts idempotentes, reejecutar `02_roles.sql` es la forma de rotar). Los
comandos son correctos y coherentes con los ficheros del repo. Detalle que
agradezco: §8 explica **por qué** el `apply-grants` final no es opcional, en vez
de limitarse a listarlo.

**4. No regresión en local.** `init.sh` en verde con los 65 tests, R8 cubre el
modo `password` local, y el implementer verificó `check-pg` y `status` contra el
PostgreSQL local. Los valores por defecto de las seis variables nuevas
reproducen el comportamiento actual: un `.env` local sin tocar sigue igual.

**5. Trazabilidad y aislamiento de los tests.** Verificado arriba.

## Verificación de la corrección (segunda pasada)

El único cambio requerido está **resuelto**. Commit `b39b137 · F-005: eliminar
el byte NUL de infra/00_vars.ps1`. Comprobado por mí, no dado por bueno leyendo
el parte:

| Comprobación | Resultado |
|---|---|
| Bytes NUL en `infra/00_vars.ps1` | **0** (antes 1) |
| Bytes NUL en todo el árbol versionado (157 ficheros) | **ninguno** |
| `git diff dev...HEAD --numstat -- infra/00_vars.ps1` | **`16  3`** — ya no `-  -`: git lo trata como texto |
| Ficheros que git ve binarios en el diff | **ninguno** |
| Línea 3, a nivel de bytes | `b' . .\\00_vars.ps1'` — un backslash literal, ruta correcta |
| Codificación | UTF-8 **con BOM**, **34 CRLF**, 0 LF sueltos (`CONVENTIONS.md:41`) |
| `bash harness/init.sh` | **exit 0**, `65 passed` |
| Alcance del commit | **solo** `infra/00_vars.ps1`; los otros 36 ficheros del diff intactos |

Dos matices que dejo escritos:

- **El líder restauró también el backslash, y tuvo razón.** Mi informe pedía
  sustituir el NUL por `00`, lo que habría dejado `. .00_vars.ps1` — ruta
  incorrecta, porque el escape se había comido la barra además del `00`. La
  corrección aplicada es mejor que la que pedí.
- **Ahora que el fichero es diffable, verifico por diff real lo que antes solo
  pude comprobar abriéndolo**: el *hunk* empieza en la línea 15, así que
  `$SUB`, `$LOC`, `$RG`, `$ACR`, `$IMG_NAME`, `$TAG`, `$IMG`, `$CAE`, `$JOB` y
  `$CRON` quedan **fuera del cambio, intactos**. Se confirma lo que declaraba
  `impl_F-005.md` §3: F-005 solo añade las variables de Postgres. Nota: el
  barrido de GUID sobre el diff sigue saliendo vacío, y eso es lo correcto —
  la línea de `$SUB` no está modificada, así que no entra en el diff. El aviso
  de la observación 1 se mantiene tal cual.

El commit de corrección usa el formato `F-005: <descripción>` en vez de
`F-005 Tn: ...`. Es correcto: no es una tarea de `tasks.md`, es una corrección
de review. T1-T11 y T21 conservan cada una su commit `F-005 Tn:`.

## Cambios requeridos — RESUELTOS

**Hubo uno solo, ya corregido.** Se conserva el enunciado como registro:

1. ~~**`infra/00_vars.ps1`, línea 3, posición 135 del fichero: hay un byte NUL
   (`0x00`) incrustado.**~~ **RESUELTO en `b39b137`.** La línea debería decir
   `# PowerShell 5.1. Ejecutar con: . .\00_vars.ps1`
   y decía `. .` + `<NUL>` + `_vars.ps1`: el `\00` de `.\00_vars.ps1` se
   interpretó como escape y se convirtió en un NUL literal.

   **Es una regresión introducida por esta rama**, verificada:
   `git show dev:infra/00_vars.ps1` → 870 bytes, **0 bytes NUL**, línea 3
   correcta. En `HEAD` → 1634 bytes, **1 byte NUL**. Es el único fichero del
   repositorio con NUL (barrido sobre `git ls-files` completo).

   **Por qué no lo dejo pasar, siendo un carácter dentro de un comentario que no
   afecta a la ejecución:** ese byte hace que **git clasifique el fichero como
   binario**. Consecuencia concreta, no hipotética: `infra/00_vars.ps1` deja de
   aparecer en `git diff` para siempre, y ese es precisamente el fichero que
   contiene el **ID de suscripción**, los nombres de recursos y el host del
   Postgres destino. Lo he comprobado en mi propia review: mi primer barrido de
   GUID sobre el diff dio **limpio** y solo encontré el `$SUB` al abrir el
   fichero a mano. En un repositorio cuya regla dura número uno es «no entran
   secretos», perder la visibilidad en diff justo sobre el fichero de
   identificadores de Azure es una propiedad de seguridad que se pierde en
   silencio — y una vez mergeado a `dev`, nadie lo va a notar.

   Añadido menor: el runbook §5 le dice al humano que ejecute `. .\00_vars.ps1`,
   y la cabecera del propio fichero le mostraba otra cosa.

   **Arreglo pedido**: sustituir el byte NUL por los dos caracteres `00`,
   guardando en UTF-8 con BOM y CRLF (`docs/CONVENTIONS.md:41`).
   **Arreglo aplicado**: se restauró la línea entera, `\` incluido — mejor que
   lo pedido, ver § «Verificación de la corrección».

## Observaciones (no bloquean, no hace falta actuar para aprobar)

1. **`infra/00_vars.ps1:5` versiona el ID de suscripción.** Ya estaba en `dev`;
   no es de F-005, y sigue ahí tras la corrección (línea intacta, fuera del
   *hunk*). Conviene que el humano decida si un GUID de suscripción debe estar
   en git o salir a variable de entorno. Ahora al menos el fichero vuelve a ser
   diffable, que era condición previa para poder vigilarlo.
2. **`FICHEROS_VIGILADOS` de `test_f005_grants.py:120` no incluye `progress/`**,
   aunque el texto de R21 dice «ni en `progress/`». Hoy no hay nada que
   encontrar —lo he barrido yo—, pero el test no cubre del todo lo que su
   requisito promete.
3. **Runbook §4, líneas 111-115**: dice que las contraseñas van «por variable de
   psql desde un fichero, **nunca escritas en la línea de comandos**», pero §5
   usa `-v app_pwd="$APP_PWD"`, que sí las expande en `argv` (visible en `ps` y
   en el historial del shell). El literal no se teclea y no entra en el repo, así
   que el riesgo real es bajo, pero la afirmación es más fuerte que lo que hacen
   los comandos. Vale la pena matizar la frase.
4. **Deuda de `ruff`: 122 → 127 avisos**, los cinco nuevos `RUF100` sobre los
   `# noqa: E402` de `main.py`. Justificado en `impl_F-005.md` §8 y coherente con
   el resto del fichero. No bloquea (`init.sh` lo trata como aviso).

## Automejora del arnés (propuesta, no aplicada)

Este defecto pasó por delante de un implementer que verificó el fichero, de un
test que lo lee, y de mi propio barrido sobre el diff. Los tres fallaron por el
mismo motivo: **nadie mira la codificación en bytes**. Propongo al humano añadir
a `CHECKPOINTS.md`, en C3, un checkbox:

- [ ] Ningún fichero versionado ha pasado a ser **binario** para git en este
      diff (`git diff dev...HEAD --numstat | awk '$1=="-"'` vacío), salvo que
      sea un binario legítimo y declarado.

Es una línea, cuesta un segundo, y cierra el agujero de que un fichero de texto
se vuelva inauditable sin que salte nada. Aplicarlo lo decide el humano.
