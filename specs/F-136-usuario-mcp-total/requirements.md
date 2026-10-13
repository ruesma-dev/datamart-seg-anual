<!-- specs/F-136-usuario-mcp-total/requirements.md -->
# F-136 · Login de acceso TOTAL para el MCP y rotación de las contraseñas expuestas

Mediciones: `progress/spec_F-136.md`. D1-D14 en `design.md` §8; **los requisitos siguen la
recomendada**. Decidido por el humano (no se reabre): total solo para Juan Romero, Antonio de
Vicente y Pablo Gris; «total» = estándar + `contabilidad_restringida`; `raw` SIEMPRE fuera;
su contraseña solo en `kv-mcp-bbdd-dev`; elegir por persona es la F-008 de `mcp-bbdd`, y
Power BI, F-087: ninguna se implementa aquí.
Vocabulario: **estándar** = `mcp_sigrid_dm_ro` (MCP y Power BI hoy); **autorizado** =
`sigrid_dm_restringido_ro` (grupo `NOLOGIN` de F-135); **total** = `mcp_sigrid_dm_total`
(login NUEVO, miembro de los dos); **vetados del total** = `PG_TOTAL_VETOED_SCHEMAS` (`raw`).

## Configuración
R1. El sistema debe ofrecer `PG_TOTAL_ROLE` (por defecto `mcp_sigrid_dm_total`) y
`PG_TOTAL_VETOED_SCHEMAS` (por defecto `raw`, con su propiedad `*_list` sin blancos ni
vacíos), documentadas en `.env.example`; el job no necesita variables nuevas.

R2. SI `PG_TOTAL_ROLE` coincide con `PG_READONLY_ROLE`, `PG_RESTRICTED_ROLE` o `PG_SET_ROLE`,
ENTONCES `apply_grants` debe terminar en FAILED sin abrir conexión, nombrando la variable.

R3. SI un esquema de `PG_TOTAL_VETOED_SCHEMAS` está en `PG_RESTRICTED_SCHEMAS` o en
`PG_CONSUMPTION_SCHEMAS`, o no está en `PG_VETOED_SCHEMAS`, ENTONCES `apply_grants` debe
terminar en FAILED sin abrir conexión, con la lista de esquemas en conflicto (un `raw`
añadido a lo restringido lo heredaría el total).

## `apply_grants`, cada noche
R4. MIENTRAS `PG_READONLY_ROLE` esté vacío, el paso debe seguir siendo un no-op que no abre conexión
ni pregunta por el total (como hoy).

R5. CUANDO `PG_TOTAL_ROLE` esté vacío, el paso no debe ejecutar nada sobre el total y debe anotar
`rol_total = "(sin configurar)"`, `verificacion_total = "no aplica"` y `acceso_total = "no aplica"`
en `metadata`.

R6. SI el login total no existe en el servidor, ENTONCES el paso debe avisar en el log
(`apply_grants_login_total_inexistente`), anotar `rol_total = "<nombre> (no existe)"`, no
ejecutar ninguna sentencia sobre él y no cambiar por ello su estado (SUCCESS si lo demás va bien).

R7. CUANDO el login total exista, el paso debe emitirle el VETO de los vetados del total que existan
(tablas, USAGE y privilegio por defecto, `build_veto_statements`), DESPUÉS de las concesiones al
estándar y al autorizado, y NINGÚN `GRANT` (ni USAGE, ni SELECT, ni CONNECT): su lectura la hereda
por pertenencia.

R8. CUANDO el login total exista, el paso debe preguntar al catálogo
(`lecturas_indebidas`) si lee algo de los vetados del total o de `PG_EXCLUDED_TABLES`; SI
lee algo, ENTONCES debe terminar en FAILED con un mensaje que nombre el login y la lista, y
`verificacion_total` = esa lista; si no, `verificacion_total = "ok"`.

R9. SI el estándar y el total leen algo indebido a la vez, ENTONCES el FAILED debe nombrar
las dos listas, cada una con su login, en un único mensaje.

R10. CUANDO el login total exista, el paso debe comprobar que tiene USAGE en cada esquema
EXISTENTE de `PG_CONSUMPTION_SCHEMAS` y de `PG_RESTRICTED_SCHEMAS`; SI le falta alguno,
ENTONCES debe avisar en el log (`apply_grants_login_total_incompleto`) y anotar
`acceso_total` = esquemas que faltan, SIN pasar a FAILED (no expone nada); si no, `"ok"`.

R11. El paso debe sumar a `rows_processed` las sentencias del veto del total, y la comprobación del
estándar de F-135 (R17, R18) debe seguir igual: sus tests no cambian de aserción.

## `infra/sql/02_roles.sql` (MANUAL, administrador)
R12. El fichero debe crear `mcp_sigrid_dm_total` `LOGIN` de forma idempotente, con
`NOCREATEDB NOCREATEROLE`, sin escribir `NOSUPERUSER` (Azure no lo admite; `CREATE ROLE`
ya lo da) y comprobándolo en la consulta final (`rolsuper = f`).

R13. El fichero debe hacerlo miembro de `mcp_sigrid_dm_ro` y de `sigrid_dm_restringido_ro` con `WITH
INHERIT TRUE, SET FALSE`, como el administrador (fuera de `SET ROLE`), DENTRO del `BEGIN … COMMIT` y
DESPUÉS del punto 5 ter.

R14. El fichero debe revocar `raw` al total (tablas, USAGE y privilegio por defecto) con los
DOS concedentes, como hace el punto 5 ter con el estándar, dentro de la misma transacción.

R15. El fichero no debe contener ningún `GRANT … TO mcp_sigrid_dm_total` salvo las dos pertenencias
de R13.

R16. El fichero debe leer las contraseñas de las variables de entorno `APP_PWD`, `MCP_PWD` y
`TOTAL_PWD` con `\getenv`, y antes de cualquier sentencia que lleve una contraseña debe fijar
`\set ECHO none`, `\set VERBOSITY terse` y `\set SHOW_CONTEXT never`.

R17. DONDE la variable de un login esté definida, el fichero debe fijar su contraseña y
escribir `<login>: contraseña fijada`; DONDE no lo esté, no debe tocarla y debe escribir
`<login>: contraseña SIN CAMBIOS`. Nunca escribe el valor.

R18. SI un login NO existe y su variable de contraseña no está definida, ENTONCES el
fichero debe fallar ANTES de crear o cambiar nada (error con `ON_ERROR_STOP`).

R19. La comprobación final debe mostrar: los cinco roles con sus atributos; las
pertenencias del total (exactamente las dos); `has_schema_privilege` del total con `raw = f`,
`contabilidad_restringida = t` y `contabilidad = t`; `has_database_privilege(…, 'CONNECT') = t`;
y CERO filas de `information_schema.table_privileges` con `grantee` el total.

## Higiene de `psql` y de los secretos
R20. En `infra/15_provision_db.ps1`, `docs/runbook_postgres_azure.md` y la cabecera de
`02_roles.sql`, toda llamada a `psql` debe poner las opciones ANTES de la cadena de
conexión, y ninguna debe pasar una contraseña con `-v` (en Windows `psql` deja de leer
opciones tras la cadena y las imprime: la incidencia del 2026-10-12).

R21. `infra/15_provision_db.ps1 -Ejecutar` debe exigir `APP_PWD`, `MCP_PWD` y `TOTAL_PWD` en
el entorno y pasárselas a `psql` solo por herencia del entorno.

R22. En el runbook, toda línea `az keyvault secret show` debe ser una asignación a una
variable, todo `az keyvault secret set` debe llevar `-o none`, y las líneas de los bloques de
código del procedimiento de F-136 no deben pasar de 100 caracteres.

R23. Ningún fichero del repositorio, de `specs/` ni de `progress/` debe contener una
contraseña, un oid ni un UPN (los patrones de F-005 alcanzan los ficheros nuevos).

R24. CUANDO `02_roles.sql` falle en una sentencia que lleva una contraseña, la salida de `psql`
(stdout y stderr) NO debe contener el valor: comprobado con `psql` real y un fallo provocado.

## Rotación y alta (procedimiento MANUAL del runbook, §12)
R25. El runbook debe documentar, en orden, una sola sesión que: genera tres valores nuevos en
memoria; los guarda en Key Vault (`kv-datamart-seg-dev`: `pg-sigrid-dm-app` y `pg-mcp-sigrid-dm-ro`;
`kv-mcp-bbdd-dev`: `pg-password` = el mismo del estándar, y `pg-password-total`); los relee del
vault al entorno; ejecuta `02_roles.sql`; borra las variables; reinicia el MCP; y actualiza Power
BI, el `.env` del datamart, el `.env.azure.bak` y el `.env` de `mcp-bbdd`.

R26. Prueba NEGATIVA con el login total real en Azure: `permission denied for schema raw`
en `raw.apu`, `raw.pag`, `raw.asi`, `raw.rac`, `raw.hmores`, `raw.con` y `raw.apa`, y
`permission denied` al escribir en `contabilidad`.

R27. Prueba POSITIVA con el login total real: `count(*)` de `contabilidad_restringida.mayor`
igual al de `raw.apu` medido con el ETL en el mismo momento, y `contabilidad.mayor` legible.

R28. Rotación verificada: la versión ANTERIOR de cada secreto rotado es rechazada (`password
authentication failed`); con la nueva conectan `check-pg` desde el puesto, el MCP tras reiniciarlo,
el job (ejecución puntual `check-pg` o la nocturna siguiente) y el refresco de Power BI.

R29. La nocturna siguiente debe terminar `apply_grants` en SUCCESS con `verificacion`,
`verificacion_total` y `acceso_total` a `"ok"`, sin ejecutar nada a mano.

## Documentación
R30. `azure-apps/datamart_seg_anual.md` debe describir el login total, su secreto (nombre y
vault, nunca el valor), qué lee y qué no, y el CONTRATO para la F-008 de `mcp-bbdd` (§7 del
diseño), en el mismo trabajo; `azure-apps/mcp_bbdd.md` solo enlaza a ese contrato.

R31. `docs/ARCHITECTURE.md` debe pasar de cuatro a cinco roles y describir la comprobación del total
en `apply_grants`.

R32 (ampliación de D13, aprobada por el humano el 2026-10-13: «como los nombres se ven, la IA no se
equivoque de esquema»). Diccionario v50: el título de `R-CONTABILIDAD-RESTRINGIDA` dice solo que se
usa `contabilidad` y que `contabilidad_restringida` es del perfil total del MCP; la regla manda
`contabilidad` por defecto, no rodear un `permission denied` de lo restringido sino responder con
`contabilidad` diciendo qué falta (`incompleto`, `num_apuntes_restringidos`,
`apuntes_restringidos_mes`) y no ir a lo restringido sin petición expresa de datos de personal; sin
nombres de personas, oid ni UPN.

R33. Cada objeto de `contabilidad_restringida` debe EMPEZAR su descripción por el aviso de acceso
restringido (perfil total; si no, `permission denied`: el equivalente de `contabilidad`) y la ficha
del esquema debe nombrar el login total; cobertura y `check-diccionario`, igual.
