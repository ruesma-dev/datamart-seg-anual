<!-- specs/F-136-usuario-mcp-total/design.md -->
# F-136 · Diseño

## 1. Encaje y límite

- Es la mitad «base de datos» del acceso por persona. La otra mitad —dos conexiones en el MCP
  y elegir una u otra según el oid de quien pregunta— es la F-008 de `mcp-bbdd` (otro
  repositorio): aquí solo se fija su CONTRATO (§7). Power BI con rol propio es F-087.
- Infraestructura (`infra/sql`, `infra/*.ps1`, runbook) + capa de aplicación (paso
  `apply_grants`) + infraestructura Postgres (cliente). Sin dominio nuevo: no hay regla de
  negocio, solo permisos. No crea ni cambia ningún objeto publicado: el diccionario no se toca.
- Medido en Azure el 2026-10-12 (solo lectura, `progress/spec_F-136.md` §1): PostgreSQL
  16.15; `log_statement = none`, `log_min_error_statement = error`; el administrador tiene
  `ADMIN OPTION` sobre `mcp_sigrid_dm_ro` y `sigrid_dm_restringido_ro` (puede dar las
  pertenencias); `sigrid_dm_app` NO (la nocturna no puede darlas: solo verifica);
  `mcp_sigrid_dm_total` no existe; `PUBLIC` no tiene USAGE en `raw`.

## 2. Ficheros

**Modificar**
- `config/settings.py`: `DEFAULT_TOTAL_ROLE = "mcp_sigrid_dm_total"`,
  `DEFAULT_TOTAL_VETOED_SCHEMAS = "raw"` (comentario: decisión del humano del 2026-10-12, «total
  no incluye raw, siempre fuera»); campos `total_role`, `total_vetoed_schemas`; propiedad
  `total_vetoed_schema_list`.
- `.env.example`: `PG_TOTAL_ROLE`, `PG_TOTAL_VETOED_SCHEMAS` con su porqué.
- `etl_sigrid/infrastructure/postgres/postgres_client.py`: `SQL_ESQUEMAS_SIN_USAGE`,
  `apply_veto`, `esquemas_sin_usage` (§4).
- `etl_sigrid/application/steps/apply_grants_step.py`: guardas R2-R3 y bloque del total (§4);
  docstring.
- `infra/sql/02_roles.sql`: §5.
- `infra/15_provision_db.ps1`: `psql` con opciones delante y `-X`, sin `-v *_pwd`; exige
  `TOTAL_PWD`; el rótulo de roles nombra el total.
- `docs/runbook_postgres_azure.md`: §4 y §5 a la forma nueva (generador en PowerShell,
  `\getenv`, opciones delante); TODA llamada a `psql` del documento con opciones delante (§3,
  §5, §10, §11); tabla de roles con el total; §12 NUEVA: procedimiento de §6.
- `docs/ARCHITECTURE.md`: cinco roles y la comprobación del total.
- `tests/test_f135_grants.py`: el `_settings` falso gana `total_role=""` y
  `total_vetoed_schema_list=["raw"]` (sin cambiar ninguna aserción).
- `../azure-apps/datamart_seg_anual.md` (contrato §7) y `../azure-apps/mcp_bbdd.md` (una
  línea que enlaza al contrato en el párrafo de F-135). Commit propio en `azure-apps`, sin push.

**Crear**
- `tests/test_f136_login_total.py` (§9).

**NO se tocan**
- `grants.py`: `build_veto_statements` ya sirve tal cual para el total.
- `config/diccionario/*` (D13), `build_contabilidad` y todo el SQL de capas.
- `infra/80_create_job.ps1`, `infra/env/dev.json`: el job no necesita variables nuevas (los
  defectos viven en el código) ni secretos nuevos; el total no es del job.
- `.env` y `.env.*.bak`: los edita el HUMANO (regla dura). El repositorio `mcp-bbdd`.

## 3. Configuración y guardas (antes de abrir conexión)

Orden en `run()`: (a) `PG_READONLY_ROLE` vacío → no-op, como hoy (R4); (b) guardas de F-135
(R17), sin cambios; (c) R2: `total` no vacío e igual a `readonly_role`, `restricted_role` o
`set_role` → FAILED; (d) R3: `conflicto = [s for s in total_vetados if s in restringidos or s
in consumo or s not in vetados]` → FAILED con la lista. Ninguna de las tres abre conexión
(test: el cliente falso no recibe ninguna llamada).

## 4. Paso `apply_grants` (después de lo de F-135)

Tras conceder al estándar (con sus vetos) y al autorizado, y dentro del mismo `try`:

```
si total vacío            -> rol_total "(sin configurar)", verificacion_total/acceso_total "no aplica"
si no role_exists(total)  -> warning apply_grants_login_total_inexistente; "(no existe)"; "no aplica"
si existe:
    sentencias += pg.apply_veto(total, dueno, total_vetados)            # R7
    indebidas_total = pg.lecturas_indebidas(total, total_vetados, excluidas)   # R8
    faltan = pg.esquemas_sin_usage(total, consumo + restringidos)       # R10
indebidas = pg.lecturas_indebidas(rol, vetados, excluidas)              # F-135 R18, igual
```

- FAILED si `indebidas` o `indebidas_total` no están vacías, con UN mensaje que lista cada
  login con lo suyo (R9) y remite al punto 5 ter/5 quater de `02_roles.sql` y a revisar las
  pertenencias del total (miembro SOLO de los dos grupos). `metadata`: `verificacion` (F-135),
  `rol_total`, `verificacion_total`, `acceso_total`.
- `faltan` no vacía → warning `apply_grants_login_total_incompleto` y `acceso_total = faltan`;
  NO es FAILED (D5).
- Si el ESTÁNDAR no existe, el paso sale antes en SUCCESS como hoy y no mira el total.
- Que el total fuese miembro del dueño (`sigrid_dm_etl`) lo caza R8: el dueño lee `raw`.

Cliente (`PostgresClient`), infraestructura, sin lógica de negocio:
- `apply_veto(role: str, owner_role: str, schemas: Iterable[str]) -> list[str]`: ejecuta
  `build_veto_statements` solo sobre los esquemas que existen (`list_schemas`), como
  `apply_restricted_grants`; vacío → no abre cursor y devuelve `[]`; log `grants_veto_aplicado`.
- `esquemas_sin_usage(role: str, schemas: Iterable[str]) -> list[str]`: `SQL_ESQUEMAS_SIN_USAGE`
  = `SELECT n.nspname FROM pg_namespace n WHERE n.nspname = ANY(%s) AND NOT
  has_schema_privilege(%s, n.oid, 'USAGE') ORDER BY 1`. Los que no existen no salen. Solo
  catálogo. `has_*_privilege` respeta la herencia (`INHERIT`) y `PUBLIC`: lee lo que leería el login.

## 5. `infra/sql/02_roles.sql` (MANUAL, administrador)

Cambios, en el orden del fichero:
1. **Cabecera**: uso nuevo (variables `APP_PWD`/`MCP_PWD`/`TOTAL_PWD` en el entorno desde Key
   Vault, `psql -X -v ON_ERROR_STOP=1 -f infra/sql/02_roles.sql $dsn`, la cadena AL FINAL), el
   porqué (incidencia del 2026-10-12) y el modelo de roles con el total.
2. **Antes de nada**: `\set ON_ERROR_STOP on`, `\set ECHO none`, `\set VERBOSITY terse`,
   `\set SHOW_CONTEXT never`; `\getenv app_pwd APP_PWD` (ídem `mcp_pwd`, `total_pwd`). Con la
   variable de entorno ausente `\getenv` no toca la variable de psql (un `-v` viejo seguiría
   valiendo, pero nada lo documenta ya).
3. **Guarda R18**, antes de crear nada: por cada login, `SELECT NOT EXISTS (…) AS falta_<x>
   \gset`; `\if :falta_<x>` + `\if :{?<x>_pwd}` … `\else` → `DO $$ BEGIN RAISE EXCEPTION
   'F-136: <login> no existe y falta <VAR> en el entorno (runbook §12)'; END $$;`.
4. **Punto 1**: `CREATE ROLE mcp_sigrid_dm_total LOGIN` si falta (`\gexec`, como los otros);
   cada `ALTER ROLE … PASSWORD :'<x>_pwd'` dentro de `\if :{?<x>_pwd}`, con `\echo
   '<login>: contraseña fijada'` / `'… SIN CAMBIOS'` (R17); `ALTER ROLE mcp_sigrid_dm_total WITH
   NOCREATEDB NOCREATEROLE` junto a los otros (sin `NOSUPERUSER`, comentario existente).
5. **Punto 5 ter** (dentro de `BEGIN … COMMIT`): a los dos bucles de veto (administrador y
   `sigrid_dm_etl`) se suma `raw` para `mcp_sigrid_dm_total` (tablas, USAGE y, como dueño,
   privilegio por defecto). Solo `raw`: lo restringido lo hereda a propósito.
6. **Punto 5 quater** (NUEVO, tras el 5 ter, como administrador y antes del `COMMIT`):
   `GRANT mcp_sigrid_dm_ro TO mcp_sigrid_dm_total WITH INHERIT TRUE, SET FALSE;` y lo mismo con
   `sigrid_dm_restringido_ro`. Dentro de la transacción: el total nunca hereda un estándar
   que aún leyera `raw`. `SET FALSE`: no necesita `SET ROLE` (el MCP lo prohíbe) (D8).
7. **Punto 6**: R19 (los cinco roles; pertenencias del total; `has_schema_privilege` en
   `raw`, `contabilidad_restringida`, `contabilidad`; `has_database_privilege` CONNECT; cero
   filas de `table_privileges` del total). CONNECT lo hereda: no se le concede.

Riesgo residual medido: con `log_min_error_statement = error`, un `ALTER ROLE … PASSWORD` que
FALLE deja su texto en el log del servidor. Se acota con la guarda R18 y con valores
hexadecimales (sin comillas que escapar); la alternativa que lo elimina es D6-E.

## 6. Procedimiento MANUAL (runbook §12), Windows PowerShell 5.1, una sola sesión

Líneas cortas, todo por variables, ningún valor en pantalla. Pasos (el runbook trae el código):
- **P0 · Puerta** (lectura): hora UTC con `[DateTime]::UtcNow` entre 07:00 y 21:00 (lejos de la
  nocturna de 00:00, D10); ninguna ejecución del job en curso (`az containerapp job execution
  list … -o table`); el job lleva la imagen con F-136; `psql --version` ≥ 15 (`\getenv`); rol
  `Key Vault Secrets Officer` en los dos vaults.
- **P1 · Variables**: `$kvDm`, `$kvMcp`, `$pgh`, `$dsn` (administrador, `dbname=sigrid_dm`),
  `$roles`, y la función `Nueva-Clave` (32 bytes de `RandomNumberGenerator` en hexadecimal,
  64 caracteres: sin `+ / = '` que romperían una cadena de conexión o el `.env`).
- **P2 · Vault primero**: `$v = Nueva-Clave` y `az keyvault secret set … --value $v -o none`
  para `kv-datamart-seg-dev/pg-sigrid-dm-app`; otro `$v` para `pg-mcp-sigrid-dm-ro` (en
  `$kvDm`) y `pg-password` (en `$kvMcp`), el MISMO valor; otro para
  `kv-mcp-bbdd-dev/pg-password-total`; `$LASTEXITCODE` tras cada uno; `$v = $null`. Vault antes
  que base: si la sesión muere, el valor está en el vault y no solo en memoria (D10).
- **P3 · Releer del vault**: `$env:APP_PWD = az keyvault secret show … --query value -o tsv`
  (ídem `MCP_PWD` desde `$kvMcp/pg-password`, `TOTAL_PWD`); comparar en memoria
  `pg-mcp-sigrid-dm-ro` con `pg-password` (deben coincidir) y longitud 64; `throw` sin imprimir.
- **P4 · Base**: `psql -X -v ON_ERROR_STOP=1 -f $roles $dsn` (la del administrador la pide
  `psql`, oculta). Esperado: tres «contraseña fijada», `COMMIT`, R19 y las consultas de F-135.
- **P5**: `Remove-Item Env:APP_PWD, Env:MCP_PWD, Env:TOTAL_PWD`.
- **P6 · MCP**: reiniciar la revisión activa de `ca-mcp-bbdd-dev` (grupo y nombre:
  `azure-apps/mcp_bbdd.md` §5); comprobar que responde. Si su log dice `password authentication
  failed`, la referencia al vault aún sirve la versión vieja: esperar y reiniciar otra vez.
- **P7 · Puesto**: el humano pone el valor nuevo de `pg-sigrid-dm-app` en el `PG_PASSWORD` del
  `.env` (portapapeles: `Set-Clipboard -Value $v` desde una variable, pegar, `Set-Clipboard
  -Value " "`; vaciar el historial Win+V si está activo); `python main.py check-pg`. Borrar
  `.env.azure.bak` (D12). Lo mismo con el `.env` de `mcp-bbdd` (estándar).
- **P8 · Power BI**: credenciales del origen en cada modelo semántico del servicio y en los
  Desktop que la tengan guardada; «Actualizar ahora» → correcto.
- **P9 · La vieja ya no entra**: versión anterior de cada secreto rotado (`list-versions -o
  json | ConvertFrom-Json`, ordenar en PowerShell, nunca `--query` con `&`, `|` o `(`, que
  rompen `az.cmd`) a `$env:PGPASSWORD`; `psql -X -c "SELECT 1" $dsnX` → `password authentication
  failed`; `Remove-Item Env:PGPASSWORD`.
- **P10 · Negativa y positiva del total** (R26-R27): `$env:PGPASSWORD` desde
  `pg-password-total`; bucle `foreach ($t in "apu","pag","asi","rac","hmores","con","apa")
  { psql -X -c "SELECT 1 FROM raw.$t LIMIT 1" $dsnT }`; `CREATE TABLE contabilidad.f136_x (x
  int)` → denegado; recuentos de `contabilidad_restringida.mayor` y `contabilidad.mayor`; y como
  administrador `SELECT count(*) FROM raw.apu`. Quitar `PGPASSWORD`. Cerrar la ventana.
- **P11**: `python main.py apply-grants` desde el puesto → SUCCESS y los tres «ok».
- **P12 · Job**: ejecución puntual de `check-pg` con su secreto (patrón «job puntual con
  `--yaml`», sin ingesta) o, si no, la nocturna; **al día siguiente** R29.
- **P13**: `az keyvault secret list --vault-name kv-albaranes-rs9k2 --query "[].name" -o tsv`:
  si siguen las dos copias de F-005, ya son valores muertos (D12).
- **Vuelta atrás**: si P4 falla, PG no ha cambiado (guarda R18) o sí (los `ALTER` van antes
  del `BEGIN`); en los dos casos se repite P4 con el entorno aún cargado. Si la sesión se
  perdió, P3 + P4 recargan del vault: el vault siempre tiene el valor bueno.

## 7. Contrato para la F-008 de `mcp-bbdd` (va a `azure-apps/datamart_seg_anual.md`)

- **Login** `mcp_sigrid_dm_total`; mismo host, base, puerto y `sslmode=require` que el estándar.
- **Secreto** `kv-mcp-bbdd-dev/pg-password-total`, por referencia al vault con la identidad
  gestionada, como `pg-password`. Nunca por valor ni en un repositorio.
- **Lee**: todo lo del estándar + `contabilidad_restringida` (`plan_cuentas`, `mayor`,
  `saldos_cuenta_mes`). **No lee** `raw` (`permission denied`). No escribe. Sin `SET ROLE`.
- **Lista blanca**: la conexión total necesita `contabilidad_restringida`; nunca `raw`.
- **Quién**: los tres, por oid en la configuración del contenedor, no en un repositorio.
  Oid fuera de la lista → estándar. Si la conexión total falla, nunca se sirve a un oid que no
  esté en la lista; degradar al estándar es la dirección segura.
- **Conexiones**: `max_connections = 50` (15 reservadas), 22 en uso el 12-10 a las 19:25 UTC
  en el servidor compartido: el segundo pool, pequeño (máximo 2).
- **Orden**: F-136 desplegada y verificada ANTES que F-008. Rotar: `02_roles.sql` con
  `TOTAL_PWD` + reiniciar el MCP. El diccionario se ajusta al desplegar F-008 (D13).

## 8. Decisiones para el humano (recomendada en negrita)

- **D1** `apply_grants` conoce el total: **A, por configuración (`PG_TOTAL_ROLE`, defecto en
  código, el job no cambia)**; B, nombre fijo; C, no verificar (solo `02_roles.sql`).
- **D2** Total ausente: **aviso y SUCCESS (R6)**, como el autorizado; o FAILED.
- **D3** Cómo lee: **por pertenencia, sin GRANT propios, más veto nocturno de `raw` y
  verificación**; o GRANT propios (duplica la lista y deriva con el tiempo).
- **D4** Qué se le veta: **lista explícita `PG_TOTAL_VETOED_SCHEMAS=raw` con guarda R3**; o
  derivar «vetados − restringidos» (un `raw` en lo restringido se colaría en silencio).
- **D5** Le falta lectura: **aviso (R10)**; o FAILED (despertaría la alarma por algo que no
  expone nada).
- **D6** Contraseñas a `psql`: **A, `\getenv` desde variables de entorno cargadas del vault
  (sin línea de órdenes, sin disco; `psql` ≥ 15, hay 16.4 en el puesto)**; B, `\set` en fichero
  temporal (deja el valor en disco y PS 5.1 le mete BOM); C, `-v` (incidencia y lista de
  procesos); D, `\password` interactivo (sin texto plano al servidor, pero se teclea o pega
  seis veces); E, verificador SCRAM calculado en el puesto (elimina el riesgo del log, código
  nuevo con secretos; para otra feature si el humano lo quiere).
- **D7** Contraseñas opcionales por variable (**sí, R17-R18**): reejecutar `02_roles.sql` por
  otro motivo (F-087…) ya no obliga a manejar secretos; la causa de la incidencia fue esa.
- **D8** Pertenencias **`WITH INHERIT TRUE, SET FALSE`**; o las de por defecto.
- **D9** Procedimiento: **manual en el runbook, líneas cortas con variables**; o un script
  `infra/16_*.ps1` (código con secretos de otro vault para una operación anual).
- **D10** Orden y ventana: **imagen → rotación + alta de día (P0) → nocturna (R29) → F-008**;
  vault antes que base.
- **D11** Nombre del secreto: **`pg-password-total`**, solo en `kv-mcp-bbdd-dev` (aprobada por el
  humano el 2026-10-13: sin copia en `kv-datamart-seg-dev`).
- **D12** Copias muertas: **borrar `.env.azure.bak` y, con autorización expresa, las de
  `kv-albaranes-rs9k2`** (vault de otro proyecto); o dejarlas.
- **D13** Diccionario: **sin cambios en F-136**; ajustar `R-CONTABILIDAD-RESTRINGIDA` (sin
  nombres de personas) cuando despliegue F-008.
- **D14** Verificar el job tras rotar: **ejecución puntual de `check-pg`**; o esperar la nocturna.

## 9. Pruebas

- **Sin red ni BBDD** (`tests/test_f136_login_total.py`): settings y `.env.example` (R1);
  guardas sin llamadas al cliente (R2-R4); paso con cliente falso: sin configurar, ausente,
  veto antes de verificar, FAILED con una o dos listas, aviso de incompleto, `rows_processed`
  (R5-R11); cliente con conexión simulada: `apply_veto` solo sobre lo que existe, SQL de
  `esquemas_sin_usage` (R7, R10); contrato textual de `02_roles.sql` (R12-R19); `psql` con
  opciones delante y sin `-v *_pwd` en los tres ficheros (R20-R21); reglas de §12 (R22);
  patrones de F-005 + GUID y `@` de dominio en los ficheros de F-136 (R23).
- **PostgreSQL 16 real local** (contenedor desechable, administrador NO superusuario con
  `CREATEROLE`, como F-135, y el `psql.exe` 16.4 de WINDOWS, que es el que no permuta
  opciones): `02_roles.sql` dos veces; R18 sin `TOTAL_PWD` en base nueva (no crea nada); R24
  con fallo provocado y `Select-String` del valor en la salida = 0; el total: negativa y
  positiva; `apply_grants` con cliente real: «ok» ×3, concesión directa a `raw` del total y a
  `PUBLIC` → FAILED que nombra a quien toca, total sin el autorizado → `acceso_total`.
- **Azure, MANUAL del humano**: §6 P4-P12 y R29.

## 10. Riesgos

- Entre P4 y P6/P7/P8, cada cliente con el valor viejo falla al abrir conexión (el pool del
  MCP sigue con las ya abiertas). Minutos; P8 depende de que el humano llegue a Power BI.
- La referencia al vault sin versión puede tardar en servir la nueva (P6, P12).
- Un `ALTER ROLE … PASSWORD` fallido queda en el log del servidor (§5). Hasta rotar, las
  contraseñas expuestas siguen valiendo: la rotación no debería esperar a F-008.
- El valor del estándar vive en dos vaults y las copias pueden divergir: P3 lo comprueba.
