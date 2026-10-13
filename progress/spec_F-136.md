<!-- progress/spec_F-136.md -->
# F-136 · Informe del spec-author (2026-10-12)

Spec: `specs/F-136-usuario-mcp-total/` (requirements 150/150, design 244/250, tasks 17 tareas).
Rama `feature/F-136-usuario-mcp-total` desde `main` `dc1797b`. Contra Azure SOLO lecturas
(`filas_solo_lectura` con `_bootstrap_done = True`, transacción `READ ONLY`). Ningún secreto,
oid, UPN ni nombre del administrador en este fichero ni en la spec.

## 1. Medido en Azure (2026-10-12, 19:25 UTC, catálogo)

| Qué | Valor | Para qué cuenta |
|---|---|---|
| Versión | PostgreSQL 16.15 | `GRANT … WITH INHERIT TRUE, SET FALSE` existe (16+) |
| `log_statement` | `none` | un `ALTER ROLE … PASSWORD` correcto no llega al log |
| `log_min_error_statement` | `error` | uno que FALLE sí deja su texto en el log (riesgo residual, design §5) |
| `password_encryption` | `scram-sha-256` | |
| `createrole_self_grant` | vacío | el administrador tiene solo `ADMIN OPTION` sobre lo que creó |
| Pertenencias | el administrador con `ADMIN OPTION` en `mcp_sigrid_dm_ro`, `sigrid_dm_restringido_ro` y `sigrid_dm_etl`; `sigrid_dm_app` en `sigrid_dm_etl` sin `ADMIN` | el administrador puede dar las dos pertenencias del total; la nocturna NO: solo puede verificar |
| `mcp_sigrid_dm_total` | no existe | |
| `sigrid_dm_restringido_ro` | existe, `NOLOGIN`, sin miembros | |
| USAGE del estándar | `contabilidad` y `personal` sí; `raw` y `contabilidad_restringida` no | F-135 en vigor |
| USAGE del autorizado | solo `contabilidad_restringida` | el total necesita además el estándar |
| `PUBLIC` en `raw` | sin USAGE | |
| Conexiones | `max_connections` 50, 15 reservadas, 22 en uso (1 del estándar) | el segundo pool de F-008, pequeño |

En el puesto: `psql` 16.4 y 15 instalados (no en el PATH de la sesión del agente): `\getenv`
disponible (psql ≥ 15).

## 2. Hallazgos que cambian el procedimiento

1. **`infra/15_provision_db.ps1` y el runbook tienen el mismo fallo que la incidencia**:
   `psql "$dsn" -v … -f …`, la cadena de conexión DELANTE. En Windows `psql` no permuta
   opciones: las ignora y las imprime. R20 lo corrige en los tres ficheros y lo fija con un test.
2. **Con `-v`, la contraseña está en la línea de órdenes** (lista de procesos) aunque se
   pase por variable de PowerShell. `\getenv` (D6-A) la saca de ahí sin dejarla en disco.
3. **`02_roles.sql` obliga hoy a fijar TODAS las contraseñas en cada ejecución**: por eso
   F-135 tuvo que manejar secretos para dar un permiso, y de ahí vino la incidencia. D7 las
   hace opcionales por variable, con guarda para el login que aún no existe.
4. **Un error en un `ALTER ROLE … PASSWORD` imprimiría la sentencia** (`LINE 1: …`) con la
   verbosidad por defecto: `\set VERBOSITY terse` y `SHOW_CONTEXT never` (R16), y R24 lo
   comprueba con `psql` real.
5. **`az keyvault secret set` sin `-o none` devuelve el valor** (ya documentado en el README de
   `infra/`, paso 8 bis): R22 lo exige en el runbook.
6. **Consumidores de las credenciales rotadas** (por nombre de usuario, sin leer valores): el
   `.env` del datamart y `.env.azure.bak` (los dos con contraseña de `sigrid_dm_app`), el `.env`
   de `mcp-bbdd` (estándar, para el MCP local), el job, el MCP de Azure y Power BI. Las copias de
   F-005 en `kv-albaranes-rs9k2` pueden seguir ahí (P13, D12).
7. **Vault antes que base**: con la base primero, si la sesión muere entre medias el valor solo
   existía en memoria; con el vault primero, P3 + P4 se repiten desde el vault.

## 3. Decisiones abiertas para el humano (design §8, recomendada primero)

D1 `PG_TOTAL_ROLE` con defecto en código · D2 total ausente = aviso · D3 por pertenencia, sin
GRANT propios, con veto nocturno de `raw` y verificación · D4 lista explícita
`PG_TOTAL_VETOED_SCHEMAS=raw` con guarda · D5 falta de lectura = aviso · D6 `\getenv` · D7
contraseñas opcionales por variable · D8 `INHERIT TRUE, SET FALSE` · D9 procedimiento manual en
el runbook · D10 imagen → rotación de día → nocturna → F-008 · D11 `pg-password-total` solo en
`kv-mcp-bbdd-dev` · D12 borrar `.env.azure.bak` y, con autorización, las copias de
`kv-albaranes-rs9k2` · D13 diccionario sin cambios hasta F-008 · D14 `check-pg` puntual del job.

## 4. Fuera de alcance (anotado)

- `mcp-bbdd` F-008: dos conexiones, la lista de oid, la lista blanca de la conexión total. Aquí
  solo su contrato (design §7), que va a `azure-apps/datamart_seg_anual.md`.
- F-087: Power BI con rol propio. Aquí solo se le actualiza la credencial tras rotar (P8).
- D6-E (verificador SCRAM en el puesto): eliminaría el riesgo del log del servidor; otra feature
  si el humano lo quiere.

## 5. Riesgo de calendario

Las contraseñas expuestas el 12-10 siguen valiendo hasta T15. La parte de código (T1-T13) no
bloquea la rotación en sí, pero P4 usa el `02_roles.sql` nuevo (`\getenv`, contraseñas
opcionales y el total): si el humano quisiera rotar ANTES de que F-136 esté aprobada, la vía
es el `02_roles.sql` actual con las opciones delante, y la del total queda para después.

## 6. Aprobación del humano (2026-10-13)

«apruebo con las recomendadas»: D1-D14 con la opción recomendada de design §8. Precisión del
líder: D11 (`pg-password-total` solo en `kv-mcp-bbdd-dev`) NO la había decidido antes el humano,
como decía el borrador; la propuso el líder en la ficha y el humano la aprueba ahora con el resto.
D12: borrar las copias de `kv-albaranes-rs9k2` sigue pidiendo autorización expresa en el momento.

## 7. Ampliación del humano (2026-10-13): D13 cambia

D13 pasa de «diccionario sin cambios en F-136» a **«diccionario v50 en F-136»**. Motivo, en
palabras del humano: «como los nombres se ven, la IA no se equivoque de esquema». En la F-008 de
`mcp-bbdd` el MCP no filtra el catálogo ni el diccionario por perfil: `contabilidad_restringida`
entra en su lista blanca para todos y al perfil estándar lo frena PostgreSQL con `permission
denied`. Se añaden R32 (reescrita) y R33, y la tarea T10 bis; T12 cambia de «el diccionario no
cambia» a «solo cambian `00_global.yaml` y `contabilidad_restringida.yaml`». Publicar la v50 es
parte del despliegue, nunca de un agente. Desajuste aceptado: si la v50 sale antes que F-008, el
MCP rechaza `contabilidad_restringida` por su lista blanca y no por `permission denied`.
