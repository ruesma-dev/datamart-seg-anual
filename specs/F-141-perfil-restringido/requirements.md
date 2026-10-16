<!-- specs/F-141-perfil-restringido/requirements.md -->
# F-141 · El perfil RESTRINGIDO del datamart (administrativos): ve menos que el estándar

Mediciones: `progress/spec_F-141.md`. **D1-D12 cerradas por el humano el 2026-10-16** (`design.md`
§9); P1 y P2 se confirman al aprobar. Regla: «ven como el estándar, menos el mayor, menos el mayor
analítico, menos la cartera de cobros (pero sí a retenciones)».
Vocabulario: **estándar** = `mcp_sigrid_dm_ro`; **autorizado** = el grupo `NOLOGIN` que lee las
`*_restringida`, hoy `sigrid_dm_restringido_ro` y tras F-141 `sigrid_dm_autorizado_ro`; **total**
= `mcp_sigrid_dm_total`; **restringido** = el grupo `sigrid_dm_perfil_restringido_ro` (lleva los
permisos) y su login miembro `mcp_sigrid_dm_restringido`; **lo suyo** = los esquemas
`PG_PERFIL_RESTRINGIDO_SCHEMAS` (el consumo menos `tesoreria`) menos los objetos de
`PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES` (`contabilidad.mayor`); **excepciones** = las tres vistas
de pago de `compras` (`vencimientos`, `v_facturas_pago`, `v_control_forma_pago`), visibles aunque
lean `tesoreria` (D4). Elegir el login por persona es de `mcp-bbdd`: aquí, su contrato.

## Configuración
R1. El sistema debe ofrecer `PG_PERFIL_RESTRINGIDO_GROUP`, `…_LOGIN`, `…_SCHEMAS` y
`…_EXCLUDED_TABLES` con los defectos del vocabulario (listas sin blancos ni vacíos), documentadas
en `.env.example`; el job no necesita variables nuevas.

R2. El defecto de `PG_RESTRICTED_ROLE` debe ser `sigrid_dm_autorizado_ro`.

## Guardas de `apply_grants` (antes de abrir conexión)
R3. SI `PG_RESTRICTED_ROLE` vale `sigrid_dm_restringido_ro`, ENTONCES FAILED sin abrir conexión,
diciendo que F-141 retiró el nombre y cuál es el nuevo.

R4. SI el grupo o el login coinciden con `PG_READONLY_ROLE`, `PG_RESTRICTED_ROLE`,
`PG_TOTAL_ROLE`, `PG_SET_ROLE` o entre sí, ENTONCES FAILED sin abrir conexión, con la variable.

R5. SI un esquema del restringido no está en `PG_CONSUMPTION_SCHEMAS`, o está en
`PG_VETOED_SCHEMAS`, `PG_RESTRICTED_SCHEMAS` o `PG_TOTAL_VETOED_SCHEMAS`, ENTONCES FAILED sin
abrir conexión, con la lista.

R6. SI `_meta` no está entre sus esquemas, ENTONCES FAILED sin abrir conexión.

R7. SI un objeto excluido está mal escrito o es de un esquema que no se le concede, ENTONCES
FAILED sin abrir conexión, nombrándolo.

R8. SI una tabla de origen de los adjuntos (`compras.facturas`, `contratos`, `comparativos`,
`comparativo_ofertas`, `albaranes`) queda sin leer y `compras.documento_adjuntos` no está
excluida, ENTONCES FAILED sin abrir conexión (F-139 D1).

## `apply_grants`, cada noche
R9. CUANDO el grupo esté vacío, el paso no debe ejecutar nada del restringido y debe anotar
`rol_restringido = "(sin configurar)"` y el resto de su `metadata` a `"no aplica"`.

R10. SI el grupo no existe, ENTONCES el paso debe avisar (`apply_grants_restringido_inexistente`),
no ejecutar nada sobre él y no cambiar por ello su estado.

R11. CUANDO el grupo exista, el paso debe concederle, DESPUÉS de lo del estándar, el autorizado y
el total: `CONNECT`, `USAGE` y `SELECT` de todas las tablas de sus esquemas, en cada uno `ALTER
DEFAULT PRIVILEGES … REVOKE SELECT` (nunca un `GRANT` por defecto) y, al final, `REVOKE ALL` de
cada excluido existente y de cada objeto de R13 y R14.

R12. CUANDO el grupo exista, el paso debe vetarle (`build_veto_statements`) todos los esquemas
EXISTENTES del catálogo que no son suyos, salvo `pg_catalog`, `information_schema`, `pg_toast`,
`pg_temp_*` y `public`.

R13. CUANDO el grupo exista, el paso debe buscar en el catálogo las vistas de sus esquemas que,
directamente o por otras vistas, leen un esquema que no es suyo (salvo `raw`) o un objeto
excluido; SI hay alguna que no sea una de las tres excepciones, ENTONCES debe revocársela y
terminar en FAILED nombrando cada vista y lo que alcanza.

R14. CUANDO el grupo exista, el paso debe buscar en sus esquemas tablas y vistas cuyo nombre
contenga `mayor` y no estén excluidas (el mayor analítico de F-127); SI hay alguna, ENTONCES debe
revocársela y terminar en FAILED nombrándola.

R15. SI una de las tres excepciones ya no aparece como vista que lee `tesoreria`, ENTONCES el paso
debe avisar (`apply_grants_restringido_excepcion_sobrante`) y anotarla en `metadata`.

R16. CUANDO el grupo exista, el paso debe preguntar al catálogo (`lecturas_indebidas`) si el
grupo, y el login si existe, leen algo de los esquemas de R12, de los excluidos o de R13-R14;
SI leen algo, ENTONCES FAILED con la lista y el rol; si no, `verificacion_restringido = "ok"`.

R17. SI el login es miembro de un rol distinto del grupo, o el grupo de algún rol, ENTONCES
FAILED nombrando las pertenencias; si no, `pertenencias_restringido = "ok"`.

R18. SI el login no existe, ENTONCES el paso debe avisar, anotar `login_restringido =
"<nombre> (no existe)"` y comprobar solo el grupo; SI le falta `USAGE` en un esquema suyo
existente, ENTONCES solo avisar (`apply_grants_restringido_incompleto`, `acceso_restringido`).

R19. SI fallan a la vez comprobaciones del estándar, el total o el restringido, ENTONCES el
FAILED debe ser UN mensaje con cada rol y lo suyo; `rows_processed` suma las del restringido, y
las sentencias del estándar, el autorizado y el total son las de antes (sus tests cambian solo
el literal del nombre del autorizado).

## `infra/sql/02_roles.sql` (MANUAL, administrador)
R20. El fichero debe renombrar `sigrid_dm_restringido_ro` a `sigrid_dm_autorizado_ro` solo si
existe el viejo y no el nuevo; si existen los dos, fallar antes de cambiar nada.

R21. El fichero debe crear el grupo `NOLOGIN` y el login si faltan, con `NOCREATEDB NOCREATEROLE`
y sin `NOSUPERUSER`, y fijar la contraseña SOLO desde `RESTRINGIDO_PWD` (`\getenv`), escribiendo
`fijada`/`SIN CAMBIOS` y nunca el valor; SI el login no existe y la variable falta, ENTONCES
fallar antes de crear o cambiar nada.

R22. Dentro del `BEGIN … COMMIT` debe dar al grupo `CONNECT` y lo de R11-R12, y `GRANT <grupo>
TO <login> WITH INHERIT TRUE, SET FALSE`; ningún otro `GRANT … TO <login>`.

R23. La comprobación final debe mostrar los siete roles (`rolsuper = f`), las pertenencias del
login (solo el grupo), `has_schema_privilege` del login `t` en sus once esquemas y `f` en
`tesoreria`, `raw` y las tres `*_restringida`, `has_table_privilege` `f` en `contabilidad.mayor`
y `t` en `contabilidad.plan_cuentas` y `compras.vencimientos`, y `CONNECT = t`.

## Renombre y secretos
R24. Fuera de `progress/`, `specs/`, `harness/features.json` y `BACKLOG.md`, ningún fichero debe
contener `sigrid_dm_restringido_ro` salvo el renombre de `02_roles.sql`, la guarda R3 y su test.

R25. Ningún fichero de F-141 debe contener una contraseña, un oid, un UPN ni un login de persona.

## Diccionario (D7)
R26. `00_global.yaml` debe tener la regla bloqueante `R-PERFIL-RESTRINGIDO` (los tres perfiles en
orden; qué no ve el restringido; que los `*_restringida` son del total y NO del perfil
restringido; que un `permission denied` no se rodea, tampoco desde `saldos_cuenta_mes`,
`retenciones.apuntes_contables` o `compras.vencimientos`).

R27. Cada `R-*-RESTRINGIDA` debe nombrar `sigrid_dm_autorizado_ro` y decir que el perfil
restringido no lee ese esquema.

R28. Las fichas de `contabilidad.mayor`, `tesoreria.efectos` y `tesoreria.efectos_restringidos_mes`
deben EMPEZAR por «No disponible para el perfil restringido»; las de las tres excepciones deben
decir que el restringido las lee y ve por ellas el estado de pago de las facturas.

R29. `version` de `00_global.yaml` debe ser mayor o igual que la de `main` más uno en el momento
del merge (test contra `git show main:…`); cobertura y puerta offline, en verde.

## Documentación y contrato
R30. `azure-apps/datamart_seg_anual.md` debe describir el perfil (grupo, login, secreto
`pg-password-restringido` en `kv-mcp-bbdd-dev` por nombre, qué lee y qué no) y el contrato E1-E8
de `design.md` §7; `azure-apps/mcp_bbdd.md`, solo un enlace. `docs/ARCHITECTURE.md`: siete roles,
el restringido, su comprobación y la obligación de F-127 (§5); el runbook, la §13.

## Verificación en Azure (MANUAL, humano)
R31. Con el login real: `permission denied` en `contabilidad.mayor`, `tesoreria.efectos`,
`raw.obr`, `contabilidad_restringida.mayor`, `tesoreria_restringida.efectos` y
`compras_restringida.documento_alarmas`, y al crear una tabla en `compras`.

R32. Con el login real, legibles: `compras.vencimientos`, `compras.v_facturas_pago`,
`contabilidad.plan_cuentas`, `retenciones.movimientos`, `personal.recursos`,
`mart.fact_seguimiento_mensual`, `_meta.v_diccionario`; `count(*)` de
`compras.documento_adjuntos` igual al del administrador.

R33. `has_schema_privilege` y `has_table_privilege` del estándar y del total sobre todos los
objetos de consumo deben ser IGUALES antes y después de `02_roles.sql` y de `apply-grants`.

R34. La nocturna siguiente debe terminar `apply_grants` en SUCCESS con `verificacion`,
`verificacion_total`, `verificacion_restringido` y `pertenencias_restringido` a `"ok"`.
