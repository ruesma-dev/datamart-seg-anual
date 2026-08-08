<!-- progress/impl_F-005.md -->
# F-005 · Postgres del datamart en Azure — Informe de implementación

Rama `feature/F-005-postgres-azure`. Fase 1 (T1-T11) terminada el 2026-08-08.
`bash harness/init.sh` en verde, exit code 0, **65 tests** (43 de ellos de
F-005). Un commit por tarea.

> **Lo primero, porque condiciona todo lo demás: no se ha ejecutado ni una sola
> operación contra Azure ni contra `psql-albaranes-rs9k2`.** Ni una lectura, ni
> una escritura, ni un `az`. Todo lo que la spec marca como `MANUAL (humano)`
> queda preparado y documentado, no ejecutado. Lo que sí se ha probado de
> verdad, y no solo con mocks, es contra el **PostgreSQL local**.

## 1. Qué cambió, en una frase

El ETL ya sabe conectarse a un Postgres de Azure —TLS obligatorio, `SET ROLE`,
sin auto-crear la base—, reaplica en cada ejecución los permisos del rol de
lectura, mide el tiempo de cada paso, y trae dos comandos para comprobar que
las vistas responden igual en local y en la nube. La provisión de la base y sus
roles queda como un runbook con SQL verificado, para que la ejecute el humano.

## 2. Decisiones del humano aplicadas (mandan sobre la spec)

Las cuatro decisiones del 2026-08-08 están aplicadas y son la fuente de las
desviaciones respecto a la spec aprobada.

| # | Decisión | Qué se hizo |
|---|---|---|
| 1 | **No se habilita Entra** en el servidor compartido | Plan B: roles nativos con contraseña en Key Vault, como ya hacen `albaranes` y `partes`. R12 y T14 quedan sin ejecutar; el runbook documenta el plan B como el camino real |
| 2 | **No se ejecuta `REVOKE CONNECT ... FROM PUBLIC`** | Riesgo aceptado y anotado en el runbook §5 bis y en `progress/current.md` |
| 3 | **El MCP lee todo, de momento** | `PG_CONSUMPTION_SCHEMAS` incluye por defecto los nueve esquemas, no solo los cinco de consumo |
| 4 | **F-006 pasa a ser servicio en cloud** | Ninguna IP de puesto cableada; el runbook dice que la regla será la IP de salida del entorno de Container Apps |

Consecuencia añadida de la 1: **F-005 ya no necesita la identidad gestionada**
`id-datamart-seg-dev`. Sin Entra no hay ningún principal que dar de alta en la
base, así que la decisión abierta 2 de la spec se cierra sola: la identidad la
crea F-003 cuando le haga falta para `AcrPull` y Key Vault.

## 3. Ficheros tocados

### Código nuevo

| Ruta | Qué hace |
|---|---|
| `etl_sigrid/infrastructure/postgres/conninfo.py` | Construye la cadena de conexión y la redacta para logs |
| `etl_sigrid/infrastructure/postgres/client_factory.py` | Única forma de construir un `PostgresClient` desde la configuración |
| `etl_sigrid/infrastructure/postgres/grants.py` | Generación pura de los `GRANT` de solo lectura |
| `etl_sigrid/infrastructure/postgres/step_run_recorder.py` | Persiste cada paso en `_meta.etl_runs` |
| `etl_sigrid/infrastructure/postgres/timings.py` | `Timing` + formato de la tabla de tiempos |
| `etl_sigrid/infrastructure/postgres/fingerprint.py` | Huella de las vistas, CSV y comparador |
| `etl_sigrid/infrastructure/azure/entra_token.py` | `EntraTokenProvider` (implementado, **inactivo**) |
| `etl_sigrid/application/ports.py` | Puerto `StepRunRecorder` |
| `etl_sigrid/application/steps/apply_grants_step.py` | Paso `apply_grants` |

### Código modificado

- `config/settings.py` — seis campos nuevos en `PostgresSettings` y el
  validador que rechaza TLS débil contra un host de Azure.
- `etl_sigrid/infrastructure/postgres/postgres_client.py` — proveedores
  callables, `auto_create_db`, `set_role`, y los métodos `role_exists`,
  `list_schemas`, `apply_readonly_grants`, `record_run_completed`,
  `fetch_timings`, `list_view_columns`, `fetch_aggregates`.
- `etl_sigrid/application/orchestrator.py` — parámetro `recorder` opcional.
- `main.py` — `_get_pg()` con proveedores; `build_pipeline_steps()` extraída;
  comandos `apply-grants`, `timings`, `fingerprint-views`,
  `compare-fingerprints`; docstring al día.
- Los cinco steps y `scripts/refresh_presupuesto.py` — pasan por la factoría.
- `requirements.txt` — `azure-identity>=1.17`.
- `.env.example`, `harness/features.json`, `docs/ARCHITECTURE.md`.

### Provisión y documentación (nada de esto se ha ejecutado contra Azure)

- `infra/sql/01_create_database.sql`, `02_roles.sql`, `03_diagnostico.sql`
- `infra/15_provision_db.ps1` (no escribe nada sin `-Ejecutar`)
- `infra/00_vars.ps1` (solo se añaden variables de Postgres; `$RG`, `$CAE`,
  `$JOB`, `$ACR`, `$CRON` y `$SUB` intactos)
- `docs/runbook_postgres_azure.md`

### Tests

`tests/test_f005_conexion.py`, `test_f005_grants.py`,
`test_f005_verificacion.py`. **43 tests, ninguno toca red ni BBDD.**

## 4. Decisiones de diseño que conviene conocer

**La cadena de conexión es un callable, no una cadena.** Con Entra el token
caduca en ~1 h y el ETL abre conexiones durante toda la ejecución; una cadena
fija fallaría a mitad de la carga inicial. Se mantiene aunque Entra esté
inactivo: es también lo que permite rotar la contraseña sin reiniciar nada.

**`make_conninfo` de psycopg en vez de un f-string.** El código anterior
concatenaba `password={valor}` sin citar. Con el plan B la contraseña la genera
Key Vault y puede llevar espacios o comillas: sin citar, la conexión falla o
—peor— apunta a otro sitio. Hay un test con una contraseña con espacios y
comilla simple.

**Los steps pasan por una factoría (`client_factory.py`).** No estaba en la
spec y es la desviación de más calado: cada step construía su propio
`PostgresClient` con `settings.postgres.conninfo` pelado. Tal cual, con
`PG_SET_ROLE` y `PG_AUTO_CREATE_DB=false` configurados, **los steps se los
habrían saltado**: habrían creado objetos con otro propietario y habrían
intentado `CREATE DATABASE` contra el servidor de producción. Es decir, R7 y R9
se cumplirían en `main.py` y se incumplirían en el pipeline nocturno, que es
donde importan.

**`apply_readonly_grants` solo concede sobre los esquemas que existen.**
`run-all` no construye `cierre`, `compras`, `maestro` ni `retenciones`, así que
en una base recién creada esos esquemas no están. Sin este filtro, el paso
fallaría por algo que no es un problema.

**`fetch_timings` ancla la «ejecución» al arranque de `ingest_raw`** y, si no
hay ninguno —histórico anterior a esta feature—, devuelve como mucho 100 filas
en vez del histórico entero. Se detectó probándolo contra la base local, donde
la primera versión volcaba tres años de filas y un total de 68 horas.

## 5. Verificación: qué se probó y con qué resultado real

### Tests automáticos

`bash harness/init.sh` → **exit code 0**. `65 passed`. Los 26 requisitos
automáticos de la spec tienen test trazable:

R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, R11, R14, R15, R16, R17, R18, R21,
R28, R29, R30, R32, R33, R34, R35, R40, R41.

### Contra el PostgreSQL local (esto no son mocks)

1. **Sin regresión**: `python main.py check-pg` → `✓ Postgres OK. PostgreSQL
   16.4`. `python main.py status` sigue listando las tablas `raw`.
2. **Telemetría**: se grabó un `StepResult` y se comprobó la fila en
   `_meta.etl_runs` con etapa, duración de 42 s, 123 filas y `metadata` JSONB.
   Fila de prueba borrada después.
3. **`timings`**: con cuatro filas simuladas de una ejecución, la tabla sale en
   orden cronológico con total de 1802,0 s. Filas borradas después.
4. **`fingerprint-views`** sobre el esquema `maestro`: 3 vistas, 51 métricas,
   CSV con BOM y coma decimal. Las vistas de `maestro` no tienen `anio_mes`, así
   que —correctamente— no generan bloque «cerrado».
5. **`compare-fingerprints`**: comparando una huella consigo misma, «Las dos
   huellas son equivalentes». Inyectando un cambio de tipo en estructura y un
   cambio de `count` en el bloque vivo: **1 FALLO + 1 AVISO y exit code 1**,
   que es exactamente el criterio de R33/R35.
6. **Los tres `.sql` de provisión se ejecutaron de verdad**, con los objetos
   renombrados (`sigrid_dm_f005test`, `f005test_etl/_app/_ro`) y borrados al
   terminar. Resultado:
   - base creada con propietario correcto y `datacl` sin `PUBLIC`;
   - reejecución de `01` y `02`: **idempotentes**, sin error;
   - los nueve esquemas, todos propiedad del rol de grupo;
   - `ALTER DEFAULT PRIVILEGES` **funciona**: una tabla y una vista creadas
     *después* de los `GRANT` resultaron legibles por el rol de solo lectura sin
     reaplicar nada;
   - el rol de solo lectura recibió `permiso denegado` al hacer `INSERT` y al
     hacer `CREATE TABLE`;
   - por la vía Python: `SET ROLE` efectivo (`current_user = f005test_etl`,
     `session_user = postgres`), `role_exists` correcto en ambos sentidos, y el
     esquema inexistente filtrado (7 sentencias en vez de 10).
   - **Limpieza comprobada**: 0 bases y 0 roles con el sufijo de prueba.
7. **Dos errores reales encontrados así, que habrían reventado delante del
   humano contra producción**:
   - `pg_database.datowner` no existe; la columna es `datdba`;
   - `pg_size_pretty(32 * 1024^3 - ...)` falla porque `1024^3` es
     `double precision`.
8. **PowerShell**: `15_provision_db.ps1` y `00_vars.ps1` parsean sin errores
   con el parser de PowerShell 5.1, y `00_vars.ps1` ejecutado deja las
   variables esperadas **sin tocar** `$RG`, `$CAE` ni las de F-003.
9. **Control negativo del barrido de secretos**: se inyectó
   `PG_PASSWORD=hunter2ClaveDeVerdad` en `.env.example` y el test R21 falló
   nombrando el fichero y el valor. Revertido.

## 6. Desviaciones respecto a la spec, con su justificación

1. **R12/T14 · Entra no se habilita.** Decisión del humano. Se aplica el plan B
   que la propia spec contemplaba. El código de Entra queda implementado y
   probado pero **inactivo**, con el estado escrito en la cabecera de
   `entra_token.py` — se mantiene porque R3-R5 son requisitos con test y porque
   el día que se habilite es un cambio de configuración, no de código.
2. **R14 · alcance de los `GRANT`.** La spec exigía «nunca ningún privilegio
   sobre `raw`, `stg`, `aux`, `_meta` ni `public`». El humano decidió que el
   MCP lee todo. Lo que el código garantiza ahora es que **no se concede nada
   fuera de la lista configurada**, y la lista por defecto incluye los nueve
   esquemas. El test se llama
   `test_f005_r14_grants_solo_sobre_los_esquemas_configurados` y la desviación
   está escrita en su docstring.
3. **R19 · `REVOKE CONNECT`.** No se ejecuta. Riesgo aceptado, documentado en
   el runbook §5 bis: `mcp_sigrid_dm_ro` podrá conectar a `albaranes` y
   `partes` y leer su **catálogo**, no sus datos.
4. **Rol de login `sigrid_dm_app`, que la spec no nombraba.** Sin Entra hacía
   falta *algún* rol con contraseña para el ETL. Se añade como miembro del
   grupo `sigrid_dm_etl`, que sigue siendo el propietario: así se conserva
   intacta la razón de ser del grupo (que cualquier principal pueda recrear las
   vistas de otro) y el plan B no degrada el modelo.
5. **`client_factory.py`, que la spec no listaba.** Justificado en §4.
6. **`is_azure_host` vive en `conninfo.py` y `config/settings.py` lo importa.**
   La spec pedía que el validador de R2 estuviera en `settings.py` y la función
   en `conninfo.py`; para evitar un ciclo de imports, `conninfo.py` no importa
   `config` en tiempo de ejecución (solo bajo `TYPE_CHECKING`).
7. **`build_readonly_grant_statements` tiene un parámetro `database`.** La
   firma de la spec no lo tenía, pero el diseño pedía emitir un
   `GRANT CONNECT ON DATABASE`, que necesita el nombre.
8. **El barrido de R11 no busca la palabra `albaranes`.** Buscarla da falsos
   positivos: `compras/01_documentos.sql` tiene una columna
   `albaran_linea_id`, y «albaranes» y «partes» son vocabulario de negocio de
   Sigrid. Lo que se prohíbe es la **referencia a la base**
   (`DATABASE|dbname=|\c`) y los mecanismos que permiten cruzar bases (`dblink`,
   `postgres_fdw`, `IMPORT FOREIGN SCHEMA`, `CREATE SERVER`).
9. **T21 de `tasks.md`** no existía como fase: es el `init.sh` final.

## 7. Runbook: lo que debe ejecutar el humano

El procedimiento completo, con contexto y puertas, está en
**`docs/runbook_postgres_azure.md`**. Los comandos exactos, en orden, están
además en `progress/current.md`. Resumen del orden y de lo que es irreversible:

1. **T12 · Fotografía previa** (solo lectura). Guardar el listado de reglas de
   firewall: después debe quedar igual más lo nuevo.
2. **T13 · Puerta de espacio. BLOQUEANTE.** Menos de 14 GB libres → parar y
   marcar `blocked`. **Ampliar almacenamiento es IRREVERSIBLE**: el disco de un
   Flexible Server solo crece.
3. **Generar las dos contraseñas y guardarlas en Key Vault** (runbook §4).
   Nunca en el repositorio.
4. **T15 · `01_create_database.sql` y `02_roles.sql`.** Idempotentes y
   reversibles (`DROP DATABASE` deshace; el datamart se regenera). Reejecutar
   `02` es la forma de rotar contraseñas. Comprobar después que **`albaranes` y
   `partes` siguen conectando**.
5. **T16 · Firewall**, solo si la IP no está cubierta. La del MCP será la IP de
   salida de Container Apps, y no se crea hasta que ese entorno exista.
6. **T17 · Huella local** con el mes cerrado que fije el humano.
7. **T18 · Carga inicial** con el perfil Azure del `.env`. El `apply-grants`
   final **no es opcional**.
8. **T19 · Medición** → `progress/medicion_carga_inicial.md` con veredicto
   explícito sobre el SKU. Es la entrada de F-011.
9. **T20 · Verificación**: comparar huellas, comprobar que el rol de lectura no
   escribe, y refrescar el informe de Power BI.

## 8. Qué queda pendiente

- **Toda la Fase 2 (T12-T20)**: son del humano, contra Azure.
- **Decisión abierta 5 de la spec**: qué mes se toma como último cerrado para
  la comparación de huellas. La fija el humano al ejecutar T17.
- **La contraseña del rol del MCP**: se crea el rol, pero su custodia
  definitiva la decide F-006.
- **`run-all` no incluye `cierre`, `compras`, `maestro` ni `retenciones`.** Se
  ha documentado en el docstring del comando y en el runbook, no se ha
  cambiado: ampliar `run-all` es un cambio de alcance mayor y no es de esta
  feature.
- **Deuda de ruff: 122 → 127 avisos.** Los cinco nuevos son todos `RUF100`
  («unused noqa») sobre los `# noqa: E402` de los imports nuevos de `main.py`.
  Se mantienen porque **todos** los imports de ese fichero los llevan (van
  después de `sys.path.insert`) y porque son correctos si algún día se activa
  la regla E402. Ningún fichero nuevo de F-005 tiene avisos: `ruff check` sobre
  ellos pasa limpio.
- El `DeprecationWarning` de `datetime.utcnow()` que sale en los tests es deuda
  previa del proyecto (`steps/base.py`); el código nuevo mantiene esa
  convención por coherencia y no la arregla dentro de esta feature.
