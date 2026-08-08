<!-- specs/F-005-postgres-azure/requirements.md -->
# F-005 · Postgres del datamart en Azure — Requisitos (EARS)

## Aviso previo: la descripción de `harness/features.json` está desfasada

La entrada F-005 de `harness/features.json` dice «**Aprovisionar** el Azure
Database for PostgreSQL Flexible Server que sustituye al Postgres local».
**Eso ya no es lo que hay que hacer.**

El diseño confirmado por el humano el 2026-08-08
(`progress/current.md` § «Diseño de despliegue propuesto» y
`progress/decisiones_abiertas.md` § «Cierre del bloque Azure») **reutiliza el
servidor que ya existe**:

| | |
|---|---|
| Servidor | `psql-albaranes-rs9k2.postgres.database.azure.com` |
| Resource group | `rg-albaranes-dev` (región `spaincentral`) |
| Versión / SKU | PostgreSQL **16** · `Standard_B1ms` (1 vCPU, 2 GB RAM) |
| Almacenamiento | **32 GB**, compartidos |
| Bases ya presentes | `albaranes`, `partes` — **en producción interna** |
| Red | Endpoint **público** con reglas de firewall por IP (D1 → opción A) |
| HA / Backup | **Sin HA** · PITR **7 días** |

Fuente: `docs/referencia/04_azure_inventario_dev.md` §5.3.

**F-005 NO crea ningún Flexible Server.** Su alcance es *la base de datos*:
`sigrid_dm`, sus esquemas, sus dos roles, la autenticación del ETL, la regla
de firewall del puesto del MCP, la carga inicial y la verificación de que las
vistas de consumo responden igual que en local.

Corregir esa descripción es la tarea **T1** de `tasks.md`.

## Consecuencia dura: es un servidor con dos bases en producción

Todo lo que haga esta feature se acota a `sigrid_dm`. **Prohibido**, sin
autorización escrita y explícita del humano para esa operación concreta:

- tocar las bases `albaranes` o `partes` (DDL, DML, `REVOKE`, `ALTER`);
- cambiar parámetros globales del servidor (`ALTER SYSTEM`,
  `az postgres flexible-server parameter set`), su SKU o su almacenamiento;
- borrar o modificar reglas de firewall existentes;
- reiniciar el servidor.

Dos operaciones del diseño **rozan esa frontera** y por eso van marcadas como
autorización expresa: **habilitar la autenticación Entra** (R12) y
**revocar `CONNECT` a `PUBLIC`** en las otras bases (R19).

## Glosario de nombres que fija esta spec

| Nombre | Qué es |
|---|---|
| `sigrid_dm` | Base del datamart, nueva, dentro del servidor existente |
| `sigrid_dm_etl` | Rol de **grupo**, `NOLOGIN`, **propietario** de la base y de todos sus objetos. Es el rol de escritura |
| `id-datamart-seg-dev` | Identidad gestionada asignada por el usuario; principal Entra miembro de `sigrid_dm_etl`. La usará el job de F-003 |
| Principal del operador | Cuenta Entra del humano, miembro de `sigrid_dm_etl`. Provisiona y ejecuta la carga inicial desde su puesto |
| `mcp_sigrid_dm_ro` | Rol de **solo lectura** del MCP. Login nativo con contraseña |
| Esquemas de consumo | `mart`, `cierre`, `compras`, `maestro`, `retenciones` |
| Esquemas internos | `raw`, `stg`, `aux`, `_meta`, `public` — **nunca** visibles al MCP |

Por qué un rol de grupo propietario y no el rol de la identidad directamente:
la carga inicial la ejecuta el humano desde su puesto (la identidad gestionada
no se puede impersonar desde fuera de Azure) y el job nocturno la ejecuta la
identidad. Si cada uno crea objetos con su propio principal, el otro no puede
hacer `DROP`/`CREATE` sobre ellos — y las vistas se recrean en cada ejecución.
Con un grupo propietario y `SET ROLE`, todos los objetos tienen un único dueño
sea quien sea el que conecte.

---

# Requisitos

Cada `Rn` lleva su verificación. `MANUAL (humano)` = solo comprobable contra
Azure o contra una BBDD real; el comando exacto está en `tasks.md` y se copia
a `progress/current.md` al cerrar la feature. Los tests automáticos **no tocan
red ni BBDD**.

## Bloque A — Conexión y autenticación

**R1.** El sistema debe permitir configurar el modo TLS de la conexión
mediante `PG_SSLMODE`, y usar `require` por defecto cuando el host pertenece a
`*.postgres.database.azure.com`.
→ `test_f005_r1_sslmode_por_defecto_segun_host`

**R2.** SI el host es de Azure y `PG_SSLMODE` vale `disable`, `allow` o
`prefer`, ENTONCES el sistema debe abortar al construir la configuración con
un mensaje que nombre la variable y el valor exigido, en vez de conectar sin
cifrar.
→ `test_f005_r2_sslmode_debil_contra_azure_aborta`

**R3.** DONDE `PG_AUTH_MODE=entra`, el sistema debe usar como contraseña de la
cadena de conexión un token de acceso obtenido de `DefaultAzureCredential`
para el recurso `https://ossrdbms-aad.database.windows.net/.default`, y **no**
debe leer `PG_PASSWORD`.
→ `test_f005_r3_entra_usa_token_y_no_password` (credencial falsa inyectada)

**R4.** CUANDO se abre una conexión nueva y el token cacheado caduca en menos
de 5 minutos, el sistema debe solicitar un token nuevo; en caso contrario debe
reutilizar el cacheado.
→ `test_f005_r4_token_se_refresca_solo_cerca_de_caducar`

**R5.** SI `PG_AUTH_MODE=entra` y no se puede obtener el token (paquete
`azure-identity` ausente, o credencial no disponible), ENTONCES el sistema
debe fallar con un error que explique el plan B —secreto en Key Vault y
`PG_AUTH_MODE=password`— y **no** debe recurrir silenciosamente a contraseña.
→ `test_f005_r5_sin_credencial_error_explicito_sin_fallback`

**R6.** El sistema no debe escribir nunca la contraseña ni el token en logs,
trazas ni mensajes de error: toda cadena de conexión que se registre pasa
antes por un redactor.
→ `test_f005_r6_safe_dsn_redacta_password_y_token`

**R7.** CUANDO se abre una conexión y `PG_SET_ROLE` no está vacío, el sistema
debe ejecutar `SET ROLE` con ese rol antes de cualquier otra sentencia de la
sesión.
→ `test_f005_r7_set_role_es_la_primera_sentencia`

**R8.** La cadena de conexión debe seguir funcionando sin cambios en el modo
actual (`PG_AUTH_MODE=password`, host local), para no romper el desarrollo en
local.
→ `test_f005_r8_modo_password_local_sin_regresion`

## Bloque B — La base y los esquemas, sin salirse de `sigrid_dm`

**R9.** DONDE `PG_AUTO_CREATE_DB=false`, el sistema **no** debe ejecutar
`CREATE DATABASE` ni abrir conexión contra la base administrativa.
→ `test_f005_r9_sin_autocreate_no_toca_la_base_admin`

**R10.** SI `PG_AUTO_CREATE_DB=false` y `sigrid_dm` no existe o no es
alcanzable, ENTONCES el sistema debe fallar con un mensaje que remita a
`infra/sql/01_create_database.sql` y al runbook, sin intentar crearla.
→ `test_f005_r10_base_ausente_mensaje_remite_al_runbook`

**R11.** Ninguna sentencia que el ETL genere o ejecute debe nombrar las bases
`albaranes` o `partes`, ni contener `ALTER SYSTEM`, `CREATE DATABASE` (fuera
del camino de auto-bootstrap), `DROP DATABASE` ni
`ALTER ROLE ... SUPERUSER`.
→ `test_f005_r11_barrido_estatico_sql_no_toca_otras_bases` (barre
  `etl_sigrid/**/*.sql`, `infra/sql/*.sql` y las sentencias generadas por
  `build_readonly_grant_statements`)

**R12.** MIENTRAS la autenticación Entra no esté habilitada en el servidor, el
sistema debe considerar F-005 bloqueada en ese punto: habilitarla es una
operación **de servidor**, no de base, y afecta a `albaranes` y `partes`. Debe
hacerse con `--password-auth Enabled` para no romper las conexiones existentes
y con autorización escrita del humano.
→ **MANUAL (humano)** · verificación de que ambos métodos quedan habilitados y
  de que `albaranes` y `partes` siguen conectando

**R13.** La base `sigrid_dm` debe existir con los nueve esquemas del proyecto
(`raw`, `aux`, `stg`, `mart`, `_meta`, `cierre`, `compras`, `maestro`,
`retenciones`) y ser propiedad de `sigrid_dm_etl`.
→ **MANUAL (humano)**

## Bloque C — Los dos roles y sus permisos

**R14.** El sistema debe conceder al rol de solo lectura `USAGE` sobre los
esquemas de consumo y `SELECT` sobre sus tablas y vistas, y **nunca** ningún
privilegio sobre `raw`, `stg`, `aux`, `_meta` ni `public`.
→ `test_f005_r14_grants_solo_esquemas_de_consumo`

**R15.** El sistema debe fijar además `ALTER DEFAULT PRIVILEGES FOR ROLE
sigrid_dm_etl` en cada esquema de consumo, para que los objetos futuros nazcan
ya legibles por el rol de solo lectura.
→ `test_f005_r15_grants_incluyen_default_privileges`

**R16.** CUANDO termina `run-all`, o cuando se invoca `python main.py
apply-grants`, el sistema debe reaplicar los permisos de lectura. Es
obligatorio y no cosmético: las vistas de `mart`, `cierre`, `compras` y
`retenciones` se ejecutan con `DROP VIEW ... CASCADE` seguido de `CREATE`, así
que **cada ejecución del ETL destruye los permisos concedidos**.
→ `test_f005_r16_run_all_incluye_el_paso_de_grants`

**R17.** DONDE `PG_READONLY_ROLE` esté vacío (desarrollo local), el paso de
permisos debe terminar en `SUCCESS` sin ejecutar ninguna sentencia.
→ `test_f005_r17_sin_rol_configurado_el_paso_es_noop`

**R18.** SI el rol de solo lectura está configurado pero no existe en
`pg_roles`, ENTONCES el sistema debe avisar en el log y terminar el paso sin
error, en vez de tumbar el pipeline nocturno por un problema de permisos.
→ `test_f005_r18_rol_inexistente_avisa_y_no_falla`

**R19.** El sistema debe dejar constancia de que **una base propia impide las
consultas entre bases, pero no impide conectar**: en PostgreSQL el privilegio
`CONNECT` está concedido a `PUBLIC` por defecto, así que `mcp_sigrid_dm_ro`
puede abrir sesión contra `albaranes` y leer el catálogo (nombres de tablas y
columnas), aunque no pueda leer datos de sus tablas. Cerrar esa rendija exige
`REVOKE CONNECT ON DATABASE albaranes FROM PUBLIC`, que **toca otra base** y
por tanto necesita autorización expresa del humano previo diagnóstico de solo
lectura.
→ **MANUAL (humano)** · diagnóstico `SELECT datname, datacl FROM pg_database`
  y decisión anotada en `progress/current.md`

**R20.** El rol `mcp_sigrid_dm_ro` no debe poder leer ninguna tabla de
`albaranes` ni de `partes`, ni ninguna tabla de `raw`, `stg`, `aux` o `_meta`
dentro de `sigrid_dm`.
→ **MANUAL (humano)** · batería de `SELECT` que deben devolver
  `permission denied`

**R21.** La contraseña de `mcp_sigrid_dm_ro` la genera el humano y no debe
aparecer en el repositorio, en `specs/`, en `progress/`, en `.env.example` ni
en ningún log. Su custodia definitiva se decide en F-006.
→ `test_f005_r21_barrido_de_secretos_en_el_arbol` + **MANUAL (humano)**

## Bloque D — Firewall del puesto del MCP

**R22.** CUANDO haya que dar acceso al puesto del MCP, el sistema debe partir
del listado de reglas existentes y comprobar si la IP ya está cubierta —el
servidor ya tiene la IP pública de la sede y una regla de puesto individual
(`ClientPgris`)—, y crear regla nueva solo si no lo está.
→ **MANUAL (humano)** · `az postgres flexible-server firewall-rule list`
  guardado antes y después

**R23.** SI hay que crear una regla, ENTONCES debe cubrir una sola IP
(`start == end`), llamarse `mcp-<puesto>-<AAAA-MM-DD>` siguiendo el precedente
del servidor, y ninguna regla preexistente puede quedar modificada ni
eliminada.
→ **MANUAL (humano)** · diff del listado antes/después

**R24.** El sistema debe dejar anotado en el runbook que estas reglas caducan
de hecho cuando cambia la IP de salida del puesto, y cuál es el procedimiento
para retirarlas cuando el puesto deje de necesitarlas.
→ Revisión documental del reviewer

## Bloque E — Espacio antes de la carga inicial

**R25.** MIENTRAS no se haya comprobado el espacio libre del servidor, el
sistema **no** debe iniciar la carga inicial. La comprobación es un requisito,
no una recomendación: son 32 GB compartidos con `albaranes` y `partes`, Sigrid
son ~4 GB en origen y `raw` + `stg` + `mart` con índices puede irse a 10-12 GB.
→ **MANUAL (humano)** · métrica `storage_percent` + tamaño por base

**R26.** SI el espacio libre es inferior a **14 GB** (12 GB de proyección más
2 GB de margen), ENTONCES la carga inicial no debe empezar: se para, se anota
en `progress/current.md` y decide el humano. Ampliar almacenamiento es
**irreversible**: en un Flexible Server el disco solo crece, nunca decrece.
→ **MANUAL (humano)**

**R27.** El sistema debe registrar el tamaño de cada base antes y después de
la carga inicial, y el tamaño final de `sigrid_dm` desglosado por esquema.
→ **MANUAL (humano)** · salida guardada en
  `progress/medicion_carga_inicial.md`

## Bloque F — Medición de tiempos por paso

**R28.** CUANDO el orquestador termina de ejecutar un paso, debe registrar en
`_meta.etl_runs` su etapa, nombre, marcas de inicio y fin, estado y filas
procesadas. Hoy solo lo hacen `ingest_raw` y `build_stg` desde dentro; los
pasos pesados —`build_mart`, `build_cierre`— **no dejan rastro persistente**, y
son justamente los que hay que medir en un SKU de 1 vCPU y 2 GB.
→ `test_f005_r28_orquestador_registra_cada_paso` (grabador falso, sin BBDD)

**R29.** SI el registro de telemetría falla, ENTONCES el orquestador debe
avisar en el log y continuar: una caída midiendo no puede tumbar la carga.
→ `test_f005_r29_fallo_del_grabador_no_rompe_el_pipeline`

**R30.** El sistema debe ofrecer `python main.py timings` mostrando, por
ejecución, etapa, paso, duración en segundos, filas y estado, ordenado
cronológicamente y con el total.
→ `test_f005_r30_timings_formatea_la_tabla` (función pura de formato)

**R31.** El resultado de la medición de la carga inicial debe quedar escrito
en `progress/medicion_carga_inicial.md` con un veredicto explícito sobre si
`Standard_B1ms` aguanta o hay que escalar el SKU —operación en caliente, un
reinicio, no una migración—. Ese fichero es la entrada de F-011.
→ **MANUAL (humano)** + revisión documental del reviewer

## Bloque G — Verificación de que las vistas responden igual que en local

**R32.** El sistema debe ofrecer `python main.py fingerprint-views --out FICHERO`
que produzca, para cada vista de consumo, un CSV con tres bloques:
1. **estructura** — lista ordenada de columnas y tipos;
2. **cerrado** — `COUNT(*)` y suma de cada columna numérica filtrando
   `anio_mes <= <mes cerrado>` en las vistas que tengan esa columna;
3. **vivo** — `COUNT(*)` y sumas sin filtro.
→ `test_f005_r32_fingerprint_construye_las_consultas_esperadas` (funciones
  puras de construcción de SQL, sin conexión)

**R33.** El sistema debe ofrecer
`python main.py compare-fingerprints LOCAL AZURE` que aplique estos criterios:

| Bloque | Criterio de «igual» |
|---|---|
| estructura | **Idéntica**. Cualquier diferencia de nombre, orden o tipo → FALLO |
| cerrado · `COUNT(*)` | **Exacto**. Cualquier diferencia → FALLO |
| cerrado · sumas | `abs(a - b) <= max(0,01, abs(a) * 1e-9)` → si no, FALLO |
| vivo | Se listan las diferencias como **AVISO**, no como fallo |

Los meses cerrados son inmutables: ahí la igualdad exacta sí significa algo.
El bloque vivo cambia entre las dos capturas porque Sigrid sigue vivo, y hay
además una vista que difiere **por construcción**: `mart.v_pbi_dim_fecha` se
genera con `CURRENT_DATE` y sus columnas `es_mes_actual` /
`es_pasado_o_actual` dependen del día de la captura.
→ `test_f005_r33_comparador_aplica_las_tolerancias`

**R34.** SI una vista aparece en una captura y no en la otra, ENTONCES el
comparador debe marcarlo FALLO y nombrarla, en vez de ignorarla.
→ `test_f005_r34_vista_ausente_en_un_lado_es_fallo`

**R35.** CUANDO `compare-fingerprints` encuentra al menos un FALLO, el proceso
debe salir con código distinto de 0; con solo AVISOS debe salir con 0.
→ `test_f005_r35_codigo_de_salida_segun_veredicto`

**R36.** La comparación real local ↔ Azure debe ejecutarse con el **mismo
commit** del repositorio a ambos lados y el informe adjuntarse a
`progress/`.
→ **MANUAL (humano)**

**R37.** El informe de Power BI debe abrir y refrescar contra `sigrid_dm` en
Azure sin errores de origen de datos ni columnas ausentes.
→ **MANUAL (humano)**

## Bloque H — Documentación, recuperación y limpieza

**R38.** El sistema debe incluir un runbook `docs/runbook_postgres_azure.md`
con: provisión de la base y los roles, autenticación Entra y **plan B**
(secreto en Key Vault con `PG_AUTH_MODE=password`, **nunca** en el
repositorio), reglas de firewall, comprobación de espacio, carga inicial y
verificación.
→ Revisión documental del reviewer

**R39.** El runbook debe decir explícitamente que **la recuperación de
`sigrid_dm` es volver a ejecutar el ETL, no restaurar**. No hay HA y el PITR
es de 7 días y **de servidor entero**: restaurar arrastraría `albaranes` y
`partes` a un punto del pasado, lo cual es inaceptable. Es decir, para este
datamart el backup del servidor **no es un mecanismo de recuperación
utilizable**; sí lo es la regenerabilidad desde Sigrid.
→ Revisión documental del reviewer

**R40.** El sistema no debe introducir ningún secreto en el repositorio: ni
contraseñas, ni cadenas de conexión completas, ni claves. `.env.example`
documenta las variables nuevas con valores vacíos o de ejemplo.
→ `test_f005_r40_ni_env_example_ni_infra_contienen_secretos`

**R41.** La descripción de F-005 en `harness/features.json` debe corregirse
para que no siga diciendo que se aprovisiona un servidor.
→ `test_f005_r41_descripcion_de_la_feature_actualizada`

---

## Decisiones que esta spec deja abiertas para el humano

Ninguna bloquea la escritura de la spec; todas deben cerrarse **antes** de
ejecutar las tareas manuales correspondientes.

1. **Habilitar Entra en el servidor compartido (R12).** Es una operación de
   servidor que afecta a `albaranes` y `partes`. Hace falta autorización
   escrita y, previsiblemente, una ventana. Si el humano prefiere no tocarlo,
   se va directamente al plan B: rol nativo con contraseña en Key Vault.
2. **Quién crea la identidad gestionada `id-datamart-seg-dev` (R12/T15).**
   Hay que coordinarlo con F-003, cuya spec (escrita en paralelo el mismo día)
   la lista entre los recursos que crea en `rg-datamart-seg-dev` y a la vez
   afirma que «F-005 puede ir por delante: crea el rol Entra en la base contra
   un principal que ya existe». Ambas cosas no pueden ser ciertas si F-005 va
   primera en el backlog. Propuesta de esta spec: **F-005 crea el resource
   group y la identidad de forma idempotente** (`az group create` +
   `az identity create`) y F-003 la reutiliza sin recrearla. Alternativa:
   F-005 queda con el plan B de contraseña y el principal Entra se da de alta
   en F-003. Lo decide el humano al aprobar ambas specs.
3. **Hasta dónde llega la lectura del MCP (R14).** La spec concede solo los
   cinco esquemas de consumo. Si el MCP de hoy consulta `raw` o `stg`, se
   quedaría corto — y no se puede comprobar porque **D4 sigue abierta**: no se
   sabe dónde vive el MCP. Se cierra en F-006; hasta entonces, la lista de
   esquemas es un parámetro (`PG_CONSUMPTION_SCHEMAS`).
4. **`REVOKE CONNECT ... FROM PUBLIC` en `albaranes` y `partes` (R19).**
   Recomendado, pero toca otras bases y podría romper sus aplicaciones si
   dependen del `CONNECT` de `PUBLIC`. Decisión del humano tras el
   diagnóstico de solo lectura.
5. **Qué mes se toma como «último cerrado» (R32/R33).** Lo fija el humano al
   ejecutar la verificación; el comando lo recibe por parámetro.
