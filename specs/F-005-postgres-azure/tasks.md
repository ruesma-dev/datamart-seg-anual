<!-- specs/F-005-postgres-azure/tasks.md -->
# F-005 · Postgres del datamart en Azure — Tareas

Rama: `feature/F-005-postgres-azure`. Un commit por tarea
(`F-005 Tn: descripción`).

Las tareas **T1-T11 son de código** y las ejecuta el implementer; terminan con
tests que no tocan red ni BBDD. Las tareas **T12-T20 son manuales del humano**
contra Azure: el implementer las deja escritas en `progress/current.md` con su
comando exacto y **no las ejecuta**.

> **Puerta previa a T12.** Antes de cualquier operación contra el servidor hay
> que tener cerradas las decisiones abiertas 1, 2 y 4 de `requirements.md`
> (habilitar Entra, dónde vive la identidad gestionada, y si se revoca
> `CONNECT` a `PUBLIC`). Sin ellas, la feature se marca `blocked`.

---

## Fase 1 — Código

- [x] **T1**: Corregir la descripción de F-005 en `harness/features.json` para
      que refleje que se reutiliza `psql-albaranes-rs9k2` y que el alcance es
      la base `sigrid_dm`, no aprovisionar un servidor.
      **Verificación**: `test_f005_r41_descripcion_de_la_feature_actualizada`
      (comprueba que la descripción no contiene «Aprovisionar» y sí nombra
      `sigrid_dm`) + `bash harness/init.sh` valida el JSON.

- [x] **T2**: Añadir a `PostgresSettings` (`config/settings.py`) los campos
      `sslmode`, `auth_mode`, `auto_create_db`, `set_role`, `readonly_role` y
      `consumption_schemas`, con los valores por defecto que reproducen el
      comportamiento actual. Incluir el validador que rechaza TLS débil contra
      host de Azure.
      **Verificación**: `test_f005_r1_*`, `test_f005_r2_*`, `test_f005_r8_*`.

- [x] **T3**: Crear `etl_sigrid/infrastructure/azure/entra_token.py` con
      `EntraTokenProvider` (import perezoso de `azure.identity`, caché con
      margen de 5 min, credencial inyectable) y añadir
      `azure-identity>=1.17` a `requirements.txt`.
      **Verificación**: `test_f005_r3_*`, `test_f005_r4_*`, `test_f005_r5_*`
      con una credencial doble; ninguna llamada de red.

- [x] **T4**: Crear `etl_sigrid/infrastructure/postgres/conninfo.py`
      (`build_conninfo`, `make_conninfo_provider`,
      `make_admin_conninfo_provider`, `safe_dsn`, `is_azure_host`) y hacer que
      `PostgresSettings.conninfo` delegue en él sin cambiar su firma.
      **Verificación**: `test_f005_r6_*` (redactado) y `test_f005_r8_*`
      (sin regresión en modo password local).

- [x] **T5**: Modificar `postgres_client.py`: aceptar proveedores callables,
      `auto_create_db` y `set_role`; saltar `_ensure_database` y verificar
      existencia cuando `auto_create_db=False`; emitir `SET ROLE` como primera
      sentencia de cada sesión. `main.py::_get_pg()` pasa a construirlo así.
      **Verificación**: `test_f005_r7_*`, `test_f005_r9_*`, `test_f005_r10_*`
      con un doble de `psycopg.connect` que registra las sentencias.

- [x] **T6**: Crear `etl_sigrid/infrastructure/postgres/grants.py` con
      `build_readonly_grant_statements` (función pura) y añadir a
      `PostgresClient` los métodos `role_exists` y `apply_readonly_grants`.
      **Verificación**: `test_f005_r14_*` (solo esquemas de consumo; ni una
      sentencia menciona `raw`, `stg`, `aux`, `_meta` ni `public`),
      `test_f005_r15_*` (default privileges presentes).

- [x] **T7**: Crear `etl_sigrid/application/steps/apply_grants_step.py` y
      registrarlo en `run-all`; añadir el comando
      `python main.py apply-grants`.
      **Verificación**: `test_f005_r16_*` (el paso está en la composición de
      `run-all`), `test_f005_r17_*` (no-op sin rol), `test_f005_r18_*` (rol
      inexistente: avisa y no falla).

- [x] **T8**: Crear `etl_sigrid/application/ports.py` con el Protocol
      `StepRunRecorder` y
      `etl_sigrid/infrastructure/postgres/step_run_recorder.py` con el
      adaptador; añadir `PostgresClient.record_run_completed`. Dar a
      `Orchestrator` el parámetro `recorder` opcional, con `try/except` que
      solo loguea.
      **Verificación**: `test_f005_r28_*` (grabador falso recibe un registro
      por paso, con etapa, duración y estado), `test_f005_r29_*` (grabador que
      revienta no rompe el pipeline).

- [x] **T9**: Añadir `PostgresClient.fetch_timings` y el comando
      `python main.py timings [--last N]`, con la función pura de formato.
      **Verificación**: `test_f005_r30_*` sobre la función de formato y con
      `CliRunner` mockeando el cliente.

- [x] **T10**: Crear `etl_sigrid/infrastructure/postgres/fingerprint.py`
      (construcción de consultas, `escribir_csv`/`leer_csv` simétricos según
      `docs/CONVENTIONS.md`, `comparar`, `veredicto`) y los comandos
      `fingerprint-views` y `compare-fingerprints`.
      **Verificación**: `test_f005_r32_*` (SQL generado, filtro de periodo solo
      donde existe `anio_mes`), `test_f005_r33_*` (tolerancias),
      `test_f005_r34_*` (vista ausente = fallo), `test_f005_r35_*` (código de
      salida). Todo sobre listas y ficheros temporales.

- [x] **T11**: Documentación y provisión, sin ejecutar nada:
      `infra/sql/01_create_database.sql`, `infra/sql/02_roles.sql`,
      `infra/sql/03_diagnostico.sql`, `infra/15_provision_db.ps1`,
      `docs/runbook_postgres_azure.md`; variables de Postgres en
      `infra/00_vars.ps1`; bloque «perfil Azure» en `.env.example`; sección de
      `docs/ARCHITECTURE.md` al día.
      **Verificación**: `test_f005_r21_*` y `test_f005_r40_*` (barrido de
      secretos: ningún fichero nuevo contiene `password=` con valor,
      `PG_PASSWORD=` con valor, ni cadenas con pinta de clave); revisión
      documental del reviewer para R24, R38 y R39.

---

## Fase 2 — Verificaciones manuales del humano

Ninguna la ejecuta un agente. Todos los comandos van con
`--subscription` implícita de la sesión `az` y **solo** contra
`rg-albaranes-dev` / `psql-albaranes-rs9k2` / `sigrid_dm`.

- [ ] **T12**: Fotografía previa del servidor (solo lectura). Guardar las
      salidas en `progress/`.
      **Verificación: MANUAL (humano)**
      ```
      az postgres flexible-server show -g rg-albaranes-dev -n psql-albaranes-rs9k2 -o json
      az postgres flexible-server firewall-rule list -g rg-albaranes-dev -n psql-albaranes-rs9k2 -o table
      az postgres flexible-server parameter list -g rg-albaranes-dev -s psql-albaranes-rs9k2 --query "[?name=='max_connections' || name=='shared_buffers']" -o table
      psql "host=psql-albaranes-rs9k2.postgres.database.azure.com dbname=postgres sslmode=require" -f infra/sql/03_diagnostico.sql
      ```

- [ ] **T13**: **Puerta de espacio (R25, R26).** Del diagnóstico anterior,
      sumar el tamaño de las bases y restarlo de los 32 GB. **Si quedan menos
      de 14 GB libres, PARAR**, anotarlo en `progress/current.md` y marcar la
      feature `blocked`. No iniciar T16 sin este dato escrito.
      **Verificación: MANUAL (humano)**
      ```
      az monitor metrics list --resource $(az postgres flexible-server show -g rg-albaranes-dev -n psql-albaranes-rs9k2 --query id -o tsv) --metric storage_percent --interval PT1H -o table
      ```

- [ ] **T14**: **Autorización expresa** para habilitar Entra en el servidor
      (afecta a `albaranes` y `partes`) y ejecución con el humano delante,
      manteniendo la autenticación por contraseña. Verificar después que
      `albaranes` y `partes` siguen conectando.
      **Verificación: MANUAL (humano)**
      ```
      az postgres flexible-server update -g rg-albaranes-dev -n psql-albaranes-rs9k2 --microsoft-entra-auth Enabled --password-auth Enabled
      az postgres flexible-server microsoft-entra-admin create -g rg-albaranes-dev -s psql-albaranes-rs9k2 --display-name <operador> --object-id <oid> --type User
      ```
      Si el humano decide no habilitarlo: aplicar el **plan B** del runbook
      (rol nativo con contraseña en Key Vault, `PG_AUTH_MODE=password`) y
      anotar la decisión.

- [ ] **T15**: Crear la identidad gestionada y la base con sus roles. Las dos
      primeras órdenes son **idempotentes y coordinadas con F-003**, cuya spec
      lista los mismos recursos: quien llegue primero los crea, el otro los
      reutiliza sin recrearlos.
      **Verificación: MANUAL (humano)**
      ```
      az group create -n rg-datamart-seg-dev -l spaincentral
      az identity create -g rg-datamart-seg-dev -n id-datamart-seg-dev -l spaincentral
      psql "host=... dbname=postgres sslmode=require" -f infra/sql/01_create_database.sql
      PGPASSWORD_MCP=<generada> psql "host=... dbname=sigrid_dm sslmode=require" -v mcp_pwd="$PGPASSWORD_MCP" -f infra/sql/02_roles.sql
      ```
      Comprobar después (R13): existen los nueve esquemas y `sigrid_dm_etl` es
      el propietario. La contraseña generada **no se escribe en ningún fichero
      del repositorio**.

- [ ] **T16**: Regla de firewall del puesto del MCP, **solo si hace falta**
      (R22, R23): comparar la IP de salida con las reglas del listado de T12.
      **Verificación: MANUAL (humano)**
      ```
      az postgres flexible-server firewall-rule create -g rg-albaranes-dev -n psql-albaranes-rs9k2 \
        --rule-name mcp-<puesto>-<AAAA-MM-DD> --start-ip-address <IP> --end-ip-address <IP>
      az postgres flexible-server firewall-rule list -g rg-albaranes-dev -n psql-albaranes-rs9k2 -o table
      ```
      El listado posterior debe contener **exactamente** las reglas de T12 más
      la nueva.

- [ ] **T17**: Huella **local** antes de tocar Azure, con el mes cerrado que
      fije el humano.
      **Verificación: MANUAL (humano)**
      ```
      python main.py fingerprint-views --out progress/fingerprint_local.csv --periodo-hasta AAAA-MM
      ```

- [ ] **T18**: **Carga inicial completa contra Azure**, desde el puesto del
      humano con el `.env` apuntando al servidor (`PG_AUTO_CREATE_DB=false`,
      `PG_SET_ROLE=sigrid_dm_etl`, `PG_SSLMODE=require`), seguida de los
      módulos que `run-all` no incluye y de los permisos.
      **Verificación: MANUAL (humano)**
      ```
      python main.py check-pg
      python main.py run-all --full
      python main.py build-cierre
      python main.py build-maestros
      python main.py build-compras
      python main.py build-retenciones
      python main.py apply-grants
      ```

- [ ] **T19**: Medición y veredicto de rendimiento (R31). Escribir
      `progress/medicion_carga_inicial.md` con la tabla de tiempos por paso,
      el tamaño final por esquema, y una conclusión explícita: `Standard_B1ms`
      aguanta / hay que escalar. Ese fichero es la entrada de F-011.
      **Verificación: MANUAL (humano)**
      ```
      python main.py timings --last 1
      psql "host=... dbname=sigrid_dm sslmode=require" -f infra/sql/03_diagnostico.sql
      ```

- [ ] **T20**: Verificación funcional (R20, R33, R36, R37):
      **Verificación: MANUAL (humano)**
      ```
      python main.py fingerprint-views --out progress/fingerprint_azure.csv --periodo-hasta AAAA-MM
      python main.py compare-fingerprints progress/fingerprint_local.csv progress/fingerprint_azure.csv
      psql "host=... dbname=sigrid_dm user=mcp_sigrid_dm_ro sslmode=require" -c "SELECT count(*) FROM raw.obr;"        # debe dar 'permission denied'
      psql "host=... dbname=albaranes user=mcp_sigrid_dm_ro sslmode=require" -c "\dt"                                   # ninguna tabla legible
      ```
      Y abrir el informe de Power BI contra `sigrid_dm` en Azure y refrescarlo
      sin errores. Adjuntar el informe del comparador a `progress/`.

---

- [ ] **T21**: Ejecutar `bash harness/init.sh` en verde.
      **Verificación**: exit code 0.
