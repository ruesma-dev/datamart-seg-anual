# F-136 · Informe del implementer (2026-10-13)

Rama `feature/F-136-usuario-mcp-total`, un commit por tarea (`6a435e4` T1 … `a297bab` T10 bis).
Spec aprobada el 2026-10-13 (D1-D14 recomendadas) y ampliada el mismo día: D13 pasa a
«diccionario v50» (R32-R33, T10 bis; nota en `progress/spec_F-136.md` §7). **Nada se ejecutó
contra Azure**: ni lecturas ni escrituras. Ningún secreto, oid, UPN ni nombre del administrador
en este fichero. `.env` y `.env.azure.bak` no se han tocado ni leído.

## 1. Qué cambió

| Fichero | Cambio |
|---|---|
| `config/settings.py`, `.env.example` | `PG_TOTAL_ROLE` (`mcp_sigrid_dm_total`) y `PG_TOTAL_VETOED_SCHEMAS` (`raw`), con `total_vetoed_schema_list` y la decisión del humano («siempre fuera») en el comentario. El job no necesita variables nuevas |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | `apply_veto` (veto sin GRANT, solo esquemas que existen, sin conexión si no hay nada) y `esquemas_sin_usage` + `SQL_ESQUEMAS_SIN_USAGE` (solo catálogo) |
| `etl_sigrid/application/steps/apply_grants_step.py` | Guardas R2-R3 sin conexión; bloque del total tras las concesiones: veto, `lecturas_indebidas`, `esquemas_sin_usage`; un único FAILED con las dos listas (R9); `metadata` `rol_total`, `verificacion_total`, `acceso_total`; docstring |
| `infra/sql/02_roles.sql` | Cabecera nueva; `\set ECHO none`, `VERBOSITY terse`, `SHOW_CONTEXT never`; `\getenv` de `APP_PWD`/`MCP_PWD`/`TOTAL_PWD`; guarda R18 (punto 0); alta idempotente del total; contraseñas opcionales con «fijada / SIN CAMBIOS»; `raw` vetado al total con los dos concedentes (5 ter); 5 quater con las dos pertenencias `WITH INHERIT TRUE, SET FALSE`; comprobación final R19 |
| `infra/15_provision_db.ps1` | `psql -X` con opciones delante y cadena al final, sin `-v *_pwd`; exige `TOTAL_PWD`; rótulo con el total |
| `docs/runbook_postgres_azure.md` | Tabla de cinco roles; §3, §5, §9 y §11 con opciones delante; §4 en PowerShell 5.1 (`-o none`, `show` asignado, `\getenv`); **§12 nueva**: P0-P13 + vuelta atrás |
| `docs/ARCHITECTURE.md` | «Cinco roles» y la comprobación del total en `apply_grants` |
| `config/diccionario/00_global.yaml`, `contabilidad_restringida.yaml` | v50: `R-CONTABILIDAD-RESTRINGIDA` reescrita (título «Usa contabilidad; contabilidad_restringida es solo para el perfil total del MCP»), aviso al principio de las tres fichas, el login total en la ficha del esquema y en la cabecera |
| `tests/test_f136_login_total.py` (nuevo) | 90 tests (R1-R33 salvo los MANUAL) |
| `tests/test_f135_grants.py`, `test_f005_grants.py`, `test_f068_exclusion_lectura_mcp.py` | Solo el settings falso gana `total_role=""` y `total_vetoed_schema_list` (ninguna aserción cambia) |
| `../azure-apps/datamart_seg_anual.md`, `mcp_bbdd.md` | Contrato del login total para la F-008 (design §7 + diccionario v50) y una línea que enlaza; commit `234fe9a` en `master`, sin push |
| `specs/F-136-*/` y `progress/spec_F-136.md` | R32 reescrito + R33, T10 bis, T12 y D13 por la ampliación (requirements 148/150) |

## 2. Decisiones y desviaciones (justificadas también en `progress/current.md`)

- **Settings falsos de F-005 y F-068** (además del de F-135 que pedía la spec): el paso lee los
  campos nuevos y un `SimpleNamespace` sin ellos da `AttributeError`. Sin cambiar aserciones.
- **R3 se evalúa aunque `PG_TOTAL_ROLE` esté vacío**, como dice design §3 (d) literalmente.
- **El aviso del FAILED del total nombra a los dos grupos** («miembro SOLO de …»): es la pista
  para arreglarlo. El mensaje de F-135 queda idéntico cuando solo falla el estándar.
- **`02_roles.sql`**: el veto del total va en un `FOREACH vetado_total` propio dentro de los dos
  `DO` del 5 ter (los tests de F-135 cuentan exactamente sus dos `FOREACH vetado`); el alta del
  total pone `ALTER ROLE … WITH LOGIN NOCREATEDB NOCREATEROLE` (las contraseñas ya no son
  obligatorias y no deben ser lo único que asegura `LOGIN`).
- **Runbook**: `--value $v` sigue en la línea de órdenes de `az` (inevitable con la CLI, como en
  design P2); lo que ya no ocurre es que el valor llegue a `psql` ni a la pantalla.
- **Diccionario**: texto en ASCII sin tildes, como el resto del diccionario; el título de la regla
  mide 79 caracteres (el más largo publicado mide 87; el validador no fija tope). El `motivo`
  conserva «Correo de Juan Romero …» porque es procedencia de F-135 y su test lo exige; el
  perfil total no se nombra por personas (test).

## 3. Fase RED (comando exacto y salida real, antes del código)

T1 · `python -m pytest tests/test_f136_login_total.py -k "r1 or settings" -q -p no:cacheprovider --tb=line`
```
tests\test_f136_login_total.py:80: KeyError: 'PG_TOTAL_ROLE'
E   AssertionError: quien quiera dar raw al total tiene que leer que el humano lo prohibió
6 failed, 1 passed in 0.63s
```
T2 · `… -k cliente`
```
tests\test_f136_login_total.py:202: AttributeError: 'PostgresClient' object has no attribute 'esquemas_sin_usage'
E   ImportError: cannot import name 'SQL_ESQUEMAS_SIN_USAGE' from 'etl_sigrid.infrastructure.postgres.postgres_client'
7 failed, 7 deselected in 0.34s
```
T3 · `… -k "r2 or r3 or r4" -W ignore`
```
E   AssertionError: assert 'SUCCESS' == 'FAILED'      (x7: R2 x3, R3 x3, raw en lo restringido)
7 failed, 3 passed, 14 deselected in 0.31s
```
T4 · `… -k "r5 or r6 or r7 or r8 or r9 or r10 or r11 or paso" -W ignore`
```
tests\test_f136_login_total.py:512: AssertionError: assert ('veto', 'mcp_sigrid_dm_total', 'sigrid_dm_etl', ['raw']) in [('role_exists', 'mcp_sigrid_dm_ro'), ('general', …), ('role_exists', 'sigrid_dm_restringido_ro'), ('verifica', 'mcp_sigrid_dm_ro', …)]
tests\test_f136_login_total.py:545: AssertionError: assert ('F-136' in '\nStep que reaplica los permisos …')
14 failed, 1 passed, 24 deselected in 0.36s
```
T5 · `… -k "r12 or r13 or r14 or r15 or r16 or r17 or r18 or r19"`
```
E   assert "SELECT 'CREATE ROLE mcp_sigrid_dm_total LOGIN'\nWHERE NOT EXISTS (…)\n\\gexec" in "\n\\set ON_ERROR_STOP on…"
E   AssertionError: falta: GRANT mcp_sigrid_dm_ro TO mcp_sigrid_dm_total WITH INHERIT TRUE, SET FALSE;
E   assert not <re.Match object; span=(383, 393), match='-v app_pwd'>
11 failed, 39 deselected in 0.68s
```
T6 · `… -k "r20 or r21"`
```
E   AssertionError: 15_provision_db.ps1: «-f» va detrás de la cadena: psql "$dsnAdmin" -f (Join-Path $sqlDir "03_diagnostico.sql")
E   AssertionError: runbook: «-f» va detrás de la cadena: psql "host=psql-albaranes-rs9k2… sslmode=require"       -f infra/sql/03_diagnostico.sql
E   AssertionError: -Ejecutar no exige TOTAL_PWD
5 failed, 3 passed, 50 deselected in 0.14s
```
T7 · `… -k "r22 or r25 or r26"`
```
E   AssertionError: §4 (dos) y §12 P2 (cuatro)
E   AssertionError: falta la §12 del runbook
8 failed, 1 passed, 58 deselected in 0.18s
```
T8 · el barrido pasa desde el principio (los ficheros estaban limpios). Prueba de que muerde: un
GUID y un correo SINTÉTICOS añadidos a `progress/spec_F-136.md` y retirados al instante:
```
E   AssertionError: assert ['<GUID sintético>', '<correo sintético>'] == []   (valores reales omitidos:
    test_f003 R4 caza cualquier correo pegado en progress/)
1 failed, 77 deselected in 1.08s
```
T9 · `… -k "r30 or r31"`
```
E   AssertionError: assert ('**Cinco roles.**' in '<!-- docs/ARCHITECTURE.md -->…')
E   AssertionError: datamart_seg_anual.md no cita mcp_sigrid_dm_total
3 failed, 78 deselected in 0.25s
```
T10 bis · `… -k "r32 or r33"`
```
E   assert 49 == 50
E   AssertionError: A la contabilidad general le falta la informacion de personal, y esta marcado
E   AssertionError: la regla no dice «Por defecto usa SIEMPRE `contabilidad`»
7 failed, 1 passed, 81 deselected in 1.61s
```
Todas, en verde tras su código: `pytest tests/test_f136_login_total.py` → **90 passed**.

## 4. T10 · PostgreSQL 16 REAL local con el `psql.exe` 16.4 de Windows

Contenedor desechable `postgres:16` (**16.15**, `log_statement = none`, `log_min_error_statement =
error`, `createrole_self_grant` vacío: lo mismo que Azure). Administrador `admin_f136` **no
superusuario** (`CREATEROLE CREATEDB`). Todo con `C:\Program Files\PostgreSQL\16\bin\psql.exe`,
opciones delante. Scripts y salidas en el scratchpad (`t10/`); contenedor y claves locales, borrados.

- **Hallazgo lateral (fuera de alcance)**: `01_create_database.sql` falla en PG16 con un
  administrador CREATEROLE no superusuario (`must be able to SET ROLE "sigrid_dm_etl"`): su
  `pg_has_role(…, 'MEMBER')` ve la pertenencia implícita con `SET FALSE` y se salta el GRANT. En
  Azure la base ya existe; para la prueba se dio `GRANT sigrid_dm_etl TO admin WITH SET TRUE`.
- **R18** (base nueva, `APP_PWD` y `MCP_PWD` sí, `TOTAL_PWD` no): `exit=3`, `ERROR: F-136:
  mcp_sigrid_dm_total no existe y falta TOTAL_PWD en el entorno (runbook §12)`; **0 roles**
  creados y 0 esquemas; los valores, 0 veces en la salida.
- **Primera ejecución** con las tres: `exit=0`, tres «contraseña fijada», `COMMIT`; los cinco
  roles con `rolsuper = f`; el total con exactamente dos pertenencias (`hereda t`, `set_role f`,
  `admin f`); `raw f`, `contabilidad_restringida t`, `contabilidad t`, `conecta t`; 0 filas de
  privilegios propios; las consultas de F-135, 0 filas y `lee = f`. Ningún valor en la salida.
- **Segunda ejecución sin variables**: tres «SIN CAMBIOS», `COMMIT`; los tres logins siguen
  entrando con su contraseña. Con una pertenencia alterada a mano a `SET TRUE`, reejecutar la
  devuelve a `set_role = f`.
- **R24**: login sin CREATEROLE ejecutando el `02` con `-b -e` en la línea de órdenes y un
  CENTINELA (valor aleatorio de usar y tirar) en las tres variables: `exit=3`, `ERROR:
  permission denied to alter role` y **0 apariciones** en stdout+stderr. Control sin las tres
  `\set` de silencio: **1 aparición** (la línea `SENTENCIA:` del ALTER ROLE, con el centinela entre comillas). Log
  del SERVIDOR: el centinela aparece (2 líneas `STATEMENT:`), el riesgo residual de design §5.
- **La incidencia, reproducida** (valor inocuo): `psql "<cadena>" -X -v prueba=VALOR -tAc …` →
  `psql: precaución: se ignoró argumento extra «prueba_inocua=VALOR_DE_PRUEBA»`.
- **Negativa** con el login total: `permission denied for schema raw` en `raw.apu`, `pag`, `asi`,
  `rac`, `hmores`, `con` y `apa`; `permission denied for schema contabilidad` (CREATE TABLE);
  `permission denied for table mayor` (INSERT); `permission denied to set role
  "mcp_sigrid_dm_ro"`. **Positiva**: `contabilidad_restringida.mayor` 5 = `raw.apu` 5 (admin);
  `contabilidad.mayor` 4; `mart` legible. El estándar, `permission denied` en las dos.
- **`apply_grants` con el cliente REAL** (como `sigrid_dm_app`, `SET ROLE sigrid_dm_etl`):

| Escenario | Resultado |
|---|---|
| 1 Noche normal | SUCCESS, 46 sentencias; `verificacion`, `verificacion_total`, `acceso_total` = ok |
| 2 Total miembro del dueño | FAILED; `verificacion_total` = `raw (USAGE)` + las 8 tablas; solo el total nombrado |
| 3 Concesión directa al total de OTRO concedente | FAILED con `raw (USAGE), raw.apu (SELECT)`; la nocturna no la puede revocar (sigue) |
| 4 Concesión a PUBLIC | FAILED con las dos listas en un mensaje (estándar y total) |
| 5 Total sin el autorizado | SUCCESS, `acceso_total = ["contabilidad_restringida"]` |
| 6 / 3b Tras deshacer | SUCCESS, los tres ok |
| 7 Concesión del DUEÑO al total (8 tablas + USAGE + por defecto) | SUCCESS: el veto las quita (0 concesiones, 0 por defecto) |

## 5. Verificaciones MANUAL pendientes (humano; nada de esto lo ha hecho un agente)

En este orden; el detalle, con el código, en `docs/runbook_postgres_azure.md` §12. Reglas de
toda la sesión: Windows PowerShell 5.1, de día (07:00-21:00 UTC), `psql` con las opciones
DELANTE y la cadena al final, ningún valor en pantalla, `-o none` en cada `secret set`.

1. **T14 · Despliegue**: merge a `main`; `infra/70_build_image.ps1`;
   `infra/85_update_job.ps1 -Tag <tag>`; comprobar la imagen del job con
   `az containerapp job show -g rg-datamart-seg-dev -n caj-datamart-seg-dev --query "properties.template.containers[0].image" -o tsv`.
   Publicar el diccionario v50: `python main.py publicar-diccionario`; luego
   `python main.py check-diccionario` y reiniciar el MCP (cachea el diccionario).
2. **T15 · §12 P0-P11, en una sola sesión**:
   - P0 puerta: hora UTC, ninguna ejecución del job en curso, imagen con F-136, `psql --version` ≥ 15.
   - P1 variables (`$kvDm`, `$kvMcp`, `$dsn` con `$env:PG_ADMIN_USER`, `$q`, `Nueva-Clave`).
   - P2 vault primero: `pg-sigrid-dm-app`; `pg-mcp-sigrid-dm-ro` y `pg-password` con el MISMO
     valor; `pg-password-total`; `$LASTEXITCODE` tras cada uno; `$v = $null`.
   - P3 releer del vault a `APP_PWD`, `MCP_PWD`, `TOTAL_PWD`; comparar las dos copias; 64 caracteres.
   - P4 `psql -X -v ON_ERROR_STOP=1 -f $roles $dsn` → tres «contraseña fijada» y `COMMIT`.
   - P5 `Remove-Item Env:APP_PWD, Env:MCP_PWD, Env:TOTAL_PWD`.
   - P6 reiniciar la revisión activa de `ca-mcp-bbdd-dev` y comprobar que responde.
   - P7 `.env` del datamart por el portapapeles; `python main.py check-pg`;
     **borrar `.env.azure.bak` (D12)**; el `.env` de `mcp-bbdd` con el estándar.
   - P8 credencial de Power BI (servicio y Desktop) y «Actualizar ahora».
   - P9 la versión ANTERIOR de cada secreto rotado → `password authentication failed`.
   - P10 negativa y positiva del total (R26-R27) y `Remove-Item Env:PGPASSWORD`; cerrar la ventana.
   - P11 `python main.py apply-grants` → SUCCESS y los tres «ok».
   Resultados, SIN valores, en `progress/current.md`.
3. **T16 · P12**: `az containerapp job start -g rg-datamart-seg-dev -n caj-datamart-seg-dev
   --command "python" --args "main.py,check-pg" -o none` (o la nocturna); al día siguiente R29
   en `_meta.etl_runs` (consulta en §12 P12): `verificacion`, `verificacion_total` y
   `acceso_total` = ok, sin nada a mano.
4. **T17 · P13**: `az keyvault secret list --vault-name kv-albaranes-rs9k2 --query "[].name" -o tsv`;
   borrar las copias de F-005 SOLO con autorización expresa (vault de otro proyecto).

## 6. Fuera de alcance y riesgos

- La F-008 de `mcp-bbdd` (dos conexiones, lista de oid, lista blanca) y F-087 (Power BI): solo su
  contrato, en `azure-apps`. Hasta F-008, el MCP rechaza `contabilidad_restringida` por su lista
  blanca y no por `permission denied` (desajuste aceptado por el humano).
- D6-E (verificador SCRAM en el puesto): el log del servidor guarda el texto de un `ALTER ROLE`
  que FALLE (medido en T10). Lo acotan la guarda R18 y los valores hexadecimales.
- `01_create_database.sql` en PG16 con administrador no superusuario (hallazgo de T10): no afecta
  a Azure hoy; si se quisiera reprovisionar desde cero, es otra feature.
- Las contraseñas expuestas el 2026-10-12 siguen valiendo hasta T15.

## 7. Evidencias

| Evidencia | Valor medido |
|---|---|
| `bash harness/init.sh` (final) | **ENTORNO LISTO**: 7.582 passed, 238 skipped, 0 failed; ruff 273 avisos de deuda previa |
| Tests de F-136 | 90 en `tests/test_f136_login_total.py`, todos en verde |
| Cobertura de líneas cambiadas | **100,0 %** (60/60, umbral 80 %, nivel crítico) |
| Mutación (`progress/mutacion_F-136.md`) | **15 generados, 15 muertos, 0 supervivientes**, 0 timeouts; 3.189 s con 4 workers |
| Tiempo de la suite | 800 s en `init.sh` (13 min 20 s); línea base de mutación ~605 s por worktree |
| Tamaño | requirements 148/150, design 244/250, impl 203/220 |

- **Mutación, cómo se llegó**: la 1.ª campaña abortó (la suite limpia, ~18 min con cobertura, no
  cabe en los 600 s de línea base por defecto) y la 2.ª, por el árbol sin commitear; la 3.ª
  encontró la **base en rojo** en el worktree: `test_f003_r1` (el rótulo de
  `15_provision_db.ps1` escribía nombres de rol que contienen `sigrid_dm`, valor de `$CFG`) y
  `test_backlog_md` (BACKLOG.md sin regenerar). Arreglado en `974ff68` (el rótulo ya no nombra
  roles; el test R21 se ajustó a ello) y la 4.ª, con `--timeout 2400 --workers 4` (timeout
  FIJADO a mano, no derivado), dio el resultado de arriba.
- Tras la mutación solo cambiaron tests e informe (R23 ya no barre `mutacion_F-136.md`, con SHA
  de git que parecen claves; la traza RED de T8, que `test_f003_r4` cazó, va descrita).
