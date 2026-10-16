<!-- specs/F-141-perfil-restringido/requirements.md -->
# F-141 · El perfil RESTRINGIDO del datamart (administrativos): ve menos que el estándar

Mediciones: `progress/spec_F-141.md`. D1-D12 en `design.md` §9; **los requisitos siguen la
recomendada** y se reescriben si el humano elige otra. Decidido por el humano (no se reabre): el
perfil se llama «restringido», es para administrativos «y gente así» y ve MENOS que el estándar.
Vocabulario: **estándar** = `mcp_sigrid_dm_ro`; **autorizado** = el grupo `NOLOGIN` que lee las
`*_restringida`, hoy `sigrid_dm_restringido_ro` y tras F-141 `sigrid_dm_autorizado_ro` (D6);
**total** = `mcp_sigrid_dm_total`; **restringido** = el grupo `sigrid_dm_perfil_restringido_ro`
(lleva los permisos) y su login miembro `mcp_sigrid_dm_restringido`; **lo suyo** = los esquemas
`PG_PERFIL_RESTRINGIDO_SCHEMAS` (`compras,maestro,_meta`) menos las tablas
`PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES` (`compras.vencimientos`, `compras.v_facturas_pago`,
`compras.v_control_forma_pago`). Elegir el login por persona es de `mcp-bbdd`: aquí solo se
escribe su contrato.

## Configuración
R1. El sistema debe ofrecer `PG_PERFIL_RESTRINGIDO_GROUP`, `PG_PERFIL_RESTRINGIDO_LOGIN`,
`PG_PERFIL_RESTRINGIDO_SCHEMAS` y `PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES` con los defectos del
vocabulario (listas sin blancos ni vacíos), documentadas en `.env.example`; el job no necesita
variables nuevas.

R2. El defecto de `PG_RESTRICTED_ROLE` debe ser `sigrid_dm_autorizado_ro`.

## Guardas de `apply_grants` (antes de abrir conexión)
R3. SI `PG_RESTRICTED_ROLE` vale `sigrid_dm_restringido_ro`, ENTONCES el paso debe terminar en
FAILED sin abrir conexión, con un mensaje que diga que el nombre lo retiró F-141 y cuál es el nuevo.

R4. SI el grupo o el login del restringido coinciden con `PG_READONLY_ROLE`, `PG_RESTRICTED_ROLE`,
`PG_TOTAL_ROLE`, `PG_SET_ROLE` o entre sí, ENTONCES FAILED sin abrir conexión, nombrando la variable.

R5. SI un esquema del restringido no está en `PG_CONSUMPTION_SCHEMAS`, o está en
`PG_VETOED_SCHEMAS`, `PG_RESTRICTED_SCHEMAS` o `PG_TOTAL_VETOED_SCHEMAS`, ENTONCES FAILED sin
abrir conexión, con la lista.

R6. SI `_meta` no está entre los esquemas del restringido, ENTONCES FAILED sin abrir conexión.

R7. SI una tabla excluida del restringido está mal escrita o es de un esquema que no se le
concede, ENTONCES FAILED sin abrir conexión, nombrándola.

R8. SI una tabla de origen de los adjuntos (`compras.facturas`, `contratos`, `comparativos`,
`comparativo_ofertas`, `albaranes`) queda sin leer para el restringido y
`compras.documento_adjuntos` no está excluida, ENTONCES FAILED sin abrir conexión (F-139 D1).

## `apply_grants`, cada noche
R9. CUANDO el grupo esté vacío, el paso no debe ejecutar nada del restringido y debe anotar
`rol_restringido = "(sin configurar)"` y el resto de su `metadata` a `"no aplica"`.

R10. SI el grupo no existe, ENTONCES el paso debe avisar (`apply_grants_restringido_inexistente`),
no ejecutar nada sobre él y no cambiar por ello su estado.

R11. CUANDO el grupo exista, el paso debe concederle, DESPUÉS de todo lo del estándar, el
autorizado y el total: `CONNECT` a la base, `USAGE` y `SELECT` de todas las tablas de lo suyo, y
en cada uno de esos esquemas `ALTER DEFAULT PRIVILEGES … REVOKE SELECT` (nunca un `GRANT` por
defecto); y, al final, `REVOKE ALL` de cada excluida existente.

R12. CUANDO el grupo exista, el paso debe vetarle (`build_veto_statements`) todos los esquemas
EXISTENTES del catálogo que no son suyos, salvo `pg_catalog`, `information_schema`, `pg_toast`,
`pg_temp_*` y `public`.

R13. CUANDO el grupo exista, el paso debe buscar en el catálogo las vistas de sus esquemas que,
directamente o por otras vistas, leen un esquema que no es suyo (ni `raw`), sin contar las
excluidas ni las aceptadas (`maestro.obras` ← `stg`); SI hay alguna, ENTONCES debe revocársela
al grupo y terminar en FAILED nombrando cada vista y el esquema que alcanza.

R14. CUANDO el grupo exista, el paso debe preguntar al catálogo (`lecturas_indebidas`) si el
grupo, y el login si existe, leen algo de los esquemas de R12, de las excluidas o de las vistas
de R13; SI leen algo, ENTONCES FAILED con la lista y el rol; si no, `verificacion_restringido = "ok"`.

R15. SI el login es miembro de algún rol distinto del grupo, o el grupo es miembro de algún rol,
ENTONCES FAILED nombrando las pertenencias; si no, `pertenencias_restringido = "ok"`.

R16. SI el login no existe, ENTONCES el paso debe avisar, anotar `login_restringido =
"<nombre> (no existe)"` y comprobar solo el grupo.

R17. SI al login le falta `USAGE` en un esquema existente de lo suyo, ENTONCES el paso debe
avisar (`apply_grants_restringido_incompleto`) y anotar `acceso_restringido` con la lista, sin
pasar a FAILED; si no, `"ok"`.

R18. SI fallan a la vez comprobaciones del estándar, el total o el restringido, ENTONCES el
FAILED debe ser UN mensaje con cada rol y lo suyo.

R19. Las sentencias del estándar, el autorizado y el total deben ser las de antes (los tests de
F-135, F-136, F-037 y F-138 cambian solo el literal del nombre del autorizado), y
`rows_processed` debe sumar las del restringido.

## `infra/sql/02_roles.sql` (MANUAL, administrador)
R20. El fichero debe renombrar `sigrid_dm_restringido_ro` a `sigrid_dm_autorizado_ro` solo si
existe el viejo y no el nuevo; si existen los dos, fallar antes de cambiar nada; si solo existe
el nuevo, no tocarlo.

R21. El fichero debe crear el grupo `NOLOGIN` y el login `LOGIN` si faltan, con `NOCREATEDB
NOCREATEROLE` y sin `NOSUPERUSER`, y fijar la contraseña del login SOLO desde la variable de
entorno `RESTRINGIDO_PWD` (`\getenv`), escribiendo `fijada`/`SIN CAMBIOS`, nunca el valor.

R22. SI el login no existe y `RESTRINGIDO_PWD` no está definida, ENTONCES el fichero debe fallar
antes de crear o cambiar nada.

R23. Dentro del `BEGIN … COMMIT`, el fichero debe dar al grupo `CONNECT` y lo suyo como R11, y
`GRANT <grupo> TO <login> WITH INHERIT TRUE, SET FALSE`; ningún otro `GRANT … TO <login>`.

R24. La comprobación final debe mostrar los siete roles (`rolsuper = f`), las pertenencias del
login (exactamente el grupo), `has_schema_privilege` del login `t` en `compras`, `maestro` y
`_meta` y `f` en `personal`, `contabilidad`, `tesoreria`, `retenciones`, `mart`, `cierre`, `stg`,
`raw` y las tres `*_restringida`; `has_table_privilege` de `compras.vencimientos` = `f`; y
`CONNECT` = `t`.

## Renombre y secretos
R25. Fuera de `progress/`, `specs/`, `harness/features.json` y `BACKLOG.md`, ningún fichero debe
contener `sigrid_dm_restringido_ro` salvo el bloque de renombre de `02_roles.sql`, la guarda de
R3 y su test.

R26. Ningún fichero que toque F-141 (ni `specs/F-141-*` ni `progress/spec_F-141.md`) debe contener
una contraseña, un oid, un UPN ni un login de persona (patrones de F-005, GUID y `@` de dominio).

## Diccionario (versión 54)
R27. `00_global.yaml` debe tener la regla bloqueante `R-PERFIL-RESTRINGIDO`: los tres perfiles en
orden (total ⊃ estándar ⊃ restringido), qué lee el restringido, que los `*_restringida` son del
total y NO del perfil restringido, y que un `permission denied` no se rodea sino que se responde
que el perfil no lo incluye.

R28. Cada `R-*-RESTRINGIDA` debe nombrar `sigrid_dm_autorizado_ro` y decir que el perfil
restringido no lee ese esquema; las tres vistas excluidas de `compras.yaml` deben EMPEZAR su
descripción por «No disponible para el perfil restringido»; `version` = 54; cobertura y puerta
offline del diccionario, en verde.

## Documentación y contrato
R29. `azure-apps/datamart_seg_anual.md` debe describir el perfil (grupo, login, secreto
`pg-password-restringido` en `kv-mcp-bbdd-dev` por nombre, qué lee y qué no) y el contrato E1-E8
de `design.md` §7; `azure-apps/mcp_bbdd.md`, solo un enlace.

R30. `docs/ARCHITECTURE.md` debe pasar a siete roles con el nombre nuevo del autorizado, qué lee
el restringido y su comprobación; el runbook debe traer el procedimiento §13.

## Verificación en Azure (MANUAL, humano)
R31. Con el login real: `permission denied` en `personal.recursos`, `contabilidad.mayor`,
`tesoreria.efectos`, `retenciones.movimientos`, `mart.fact_seguimiento_mensual`, `stg.obras`,
`raw.obr`, `contabilidad_restringida.mayor`, `compras.vencimientos` y `compras.v_facturas_pago`;
y al crear una tabla en `compras`.

R32. Con el login real: `compras.facturas`, `maestro.obras` y `_meta.v_diccionario` legibles, y
`count(*)` de `compras.documento_adjuntos` igual al del administrador.

R33. `has_schema_privilege` y `has_table_privilege` del estándar y del total sobre todos los
objetos de consumo deben ser IGUALES antes y después de `02_roles.sql` y de `apply-grants`.

R34. La nocturna siguiente debe terminar `apply_grants` en SUCCESS con `verificacion`,
`verificacion_total`, `verificacion_restringido` y `pertenencias_restringido` a `"ok"`.
