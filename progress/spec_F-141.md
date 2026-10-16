<!-- progress/spec_F-141.md -->
# F-141 · Informe del spec-author (2026-10-16)

Spec: `specs/F-141-perfil-restringido/`. Rama `feature/F-141-perfil-restringido` desde `main`
`1672383` (lleva además `0288b86`, un commit de contabilidad del líder). Contra Azure SOLO
lecturas (`filas_solo_lectura` con `_bootstrap_done = True`, transacción `READ ONLY`); contra
Sigrid SOLO recuentos por `sigrid-api` (`leer_sql`). Ningún secreto, oid, UPN, login de persona
ni contraseña en este fichero ni en la spec: los miembros de los grupos que no son roles del
repositorio salen como `<otro>`.

## 1. Servidor y roles (Azure, 2026-10-16 07:46 UTC)

| Qué | Valor | Para qué cuenta |
|---|---|---|
| Versión | PostgreSQL 16.15 | `security_invoker` en vistas (15+) y `WITH INHERIT TRUE, SET FALSE` (16+) existen |
| Conexiones | `max_connections` 50, `superuser_reserved_connections` 10, 28 en uso (3 en `sigrid_dm`) | un tercer pool del MCP, pequeño (máx. 2): quedan ~12 libres en el servidor compartido |
| Roles del repositorio | `sigrid_dm_etl` (NOLOGIN), `sigrid_dm_app`, `mcp_sigrid_dm_ro`, `sigrid_dm_restringido_ro` (NOLOGIN), `mcp_sigrid_dm_total`; ninguno `rolsuper` ni `rolbypassrls` | no existe aún nada del perfil restringido |
| Pertenencias | `mcp_sigrid_dm_ro`: total + `<otro>`; `sigrid_dm_restringido_ro`: total + `<otro>`; `sigrid_dm_etl`: app + `<otro>` | `<otro>` es el administrador (ADMIN OPTION, F-136 §1) |
| Dueño de la base | `sigrid_dm_etl` | la nocturna puede dar `CONNECT` (ya lo hace al estándar) |
| `CONNECT` a `PUBLIC` | no (0 entradas `PUBLIC` en `datacl`) | el login nuevo necesita `CONNECT` explícito (o heredado del grupo) |
| `USAGE` de `PUBLIC` | solo `pg_catalog`, `information_schema`, `public` | `public` está VACÍO (0 objetos, 0 funciones); `CREATE` en `public` no (PG 15+) |
| Funciones `SECURITY DEFINER` | 0 fuera del catálogo | nada que salte los permisos por esquema |
| Lectura actual | estándar: los 12 de consumo, no `raw` ni las tres `*_restringida`; total: lo mismo más las tres | F-135/F-136/F-138 en vigor |

## 2. Qué hay publicado y qué tiene dentro (fuera de `raw`)

Objetos por esquema (r = tabla, v = vista; **no hay ni una vista materializada**: todo lo
«materializado» son tablas):

| Esquema | r | v | MB | Objetos con importes | con datos de persona* | con proveedor | sin columna de obra |
|---|---|---|---|---|---|---|---|
| `_meta` | 6 | 4 | 6 | 0 | 0 | 0 | 8 de 10 |
| `aux` | 1 | 0 | 0 | 1 | 0 | 0 | 0 de 1 |
| `cierre` | 1 | 8 | 8 | 4 | 7 | 0 | 2 de 9 |
| `compras` | 22 | 9 | 1.886 | 14 | 21 | 12 | 18 de 31 |
| `contabilidad` | 4 | 0 | 806 | 3 | 2 | 0 | 3 de 4 |
| `descompuestos` | 5 | 4 | 5.286 | 7 | 3 | 2 | 0 de 7 |
| `maestro` | 0 | 7 | 0 | 4 | 4 | 2 | 3 de 7 |
| `mart` | 5 | 11 | 3.097 | 11 | 7 | 0 | 2 de 16 |
| `personal` | 5 | 1 | 83 | 6 | 3 | 1 | 4 de 6 |
| `retenciones` | 6 | 9 | 24 | 11 | 11 | 6 | 7 de 15 |
| `stg` | 6 | 1 | 17.502 | 4 | 2 | 0 | 1 de 7 |
| `tesoreria` | 2 | 0 | 110 | 1 | 1 | 0 | 1 de 2 |

\* Por NOMBRE de columna (`nif|dni|nombre|usuario|login|empleado|iban|banc…`): incluye
`nombre_proveedor` o `nombre_obra`, así que es una cota alta. Los datos personales de verdad están
en `personal` (nombre, NIF, DNI y coste por persona) y, como logins y nombres de usuarios de
Sigrid, en `compras.documento_procesos` y `compras.documento_alarmas.creada_por`.

Qué es cada esquema para un administrativo (lectura del diccionario y de `ARCHITECTURE.md`):
`compras` (albaranes, facturas, contratos, comparativos, adjuntos, alarmas: su trabajo diario),
`maestro` (obras, proveedores, centros de coste, estados), `_meta` (diccionario y frescura: sin él
el MCP no explica nada), frente a `mart`/`cierre` (venta, coste y margen de cada obra: el
seguimiento económico), `stg`/`descompuestos`/`aux` (presupuesto, planificación, estudios),
`contabilidad`, `tesoreria`, `retenciones` (el dinero) y `personal` (las personas).

## 3. Las vistas que cruzan esquemas (la trampa de dar esquemas sueltos)

Una vista se ejecuta con los permisos de su DUEÑO: quien lee la vista lee lo que la vista lee,
aunque no tenga permiso sobre el esquema de origen. Dependencias TRANSITIVAS (vista sobre vista)
hacia un esquema de consumo NO concedido, por conjunto candidato (sin contar `raw`):

| Conjunto concedido | Vistas que filtran |
|---|---|
| `compras, maestro, _meta` | `compras.vencimientos` ← `tesoreria.efectos`; `compras.v_facturas_pago` y `compras.v_control_forma_pago` ← `tesoreria` (vía `vencimientos`); `maestro.obras` ← `stg` |
| `+ tesoreria, retenciones` | `maestro.obras` ← `stg` |
| estándar menos `personal`, `contabilidad`, `tesoreria` | las tres de `compras` ← `tesoreria` |

`maestro.obras` solo toma de `stg` dos booleanos (`EXISTS` en `stg.presupuesto` y
`stg.plan_mensual`: `tiene_presupuesto`, `tiene_seguimiento`, `01_obras.sql` l. 95-96): no expone
cifras. Las TABLAS construidas en el build con datos de otro esquema no salen en el catálogo
(p. ej. `retenciones.apuntes_contables` sale de los apuntes contables): esa frontera la decide el
diseño, no la guarda.

## 4. Seguridad por fila (RLS): coste y trampas, medidos

- **Hoy: 0 tablas con RLS, 0 políticas, 0 vistas con `security_invoker` o `security_barrier`.**
- Las 54 vistas de consumo son del mismo dueño que sus tablas, y el dueño SALTA la RLS (salvo
  `FORCE ROW LEVEL SECURITY`, que rompería el propio build): **con RLS en las tablas, toda vista
  seguiría devolviendo todas las filas**. Arreglarlo exige `security_invoker = true` en cada
  vista, y entonces quien lee necesita `SELECT` en lo que la vista lee: 12 vistas de `compras` y
  `maestro` leen `raw` directamente (`maestro.obras` lee `raw.obr`, `raw.con`…). Habría que abrir
  `raw` (vetado «siempre») o reescribirlas como tablas.
- 29 ficheros SQL de capa contienen `DROP TABLE` (compras 11, contabilidad 7, retenciones 5, mart
  3, cierre 2, descompuestos 1): un `DROP` se lleva sus políticas cada noche; habría que
  recrearlas en `apply_grants` y verificarlas, como los GRANT.
- Sin columna de obra: 18 de 31 objetos de `compras`, 7 de 15 de `retenciones`, 3 de 4 de
  `contabilidad`… (§2): para ellos «solo sus obras» no tiene definición.
- Coste: un predicado por fila en tablas de 12 GB (`stg.plan_mensual`, 32 M filas) sobre un
  servidor de cómputo con créditos (B1ms/B2s compartido).

## 5. ¿De dónde saldría la lista de obras de cada persona? (Sigrid y Azure, 2026-10-16)

| Fuente | Medido | Sirve |
|---|---|---|
| `raw.usu.obr` (obra del usuario de Sigrid) | informada en 1 de 233 usuarios | no |
| `raw.obr.diride` (director de obra) | informado en 8 de 923 obras | no |
| Sigrid `conseg` (seguridad por concepto) | 399 filas, 2 usuarios distintos, conceptos de tipo 15/14/20; **0 obras** | no |
| Sigrid `consegweb`, `consegwebgru` | 0 filas | no |
| Sigrid `obrusu` («últimos accesos de usuarios a obras») | 9.228 filas, 714 obras, 255 usuarios | NO como permiso: es un historial de quién abrió qué, no a qué tiene derecho |
| `maestro.obras` | 923 fichas, `es_activa` en las 923 (`R-OBRA-ACTIVA`) | no dice de quién es la obra |
| El portal (`azure-apps/portal.md`) | da tarjetas por GRUPO de Entra, no obras por persona | no |

**No existe hoy una fuente de «obras por persona».** Un acotado por obra exigiría una tabla
mantenida a mano (quién, con qué proceso, qué pasa con las bajas y las obras nuevas).

## 6. Las otras dos piezas

- **`compras.documento_adjuntos` por familia** (requisito de F-139 D1): FACTURA 134.121, CONTRATO
  38.193, OFERTA 22.078, COMPARATIVO 4.453, ALBARAN 690. Con `compras` concedido entero, el
  restringido lee las cinco tablas de origen y la regla se cumple sin vistas ni RLS; solo hace
  falta una guarda para el día que se excluya una tabla de origen.
- **Power BI**: el modelo semántico lee con UNA credencial de origen para todos sus lectores (el
  conector de PostgreSQL no pasa la identidad del usuario a la base). Un login de base no acota a
  una persona en Power BI: acotar ahí es un modelo aparte o RLS de Power BI, y el acceso a los
  informes lo gobierna el workspace (`azure-apps/portal.md`). El MCP sí elige login por persona
  (por oid, F-008 de `mcp-bbdd`).
- **El MCP hoy** (`azure-apps/mcp_bbdd.md` §2): oid en `MCP_PERFIL_TOTAL_OIDS` → total; cualquier
  otro → estándar. Sin licencia Entra ID P1, Easy Auth deja entrar a cualquier cuenta del tenant
  (§6.2): hoy quien no está en ninguna lista ve el estándar (personas, contabilidad, márgenes).
  `listar_tablas`, `contexto_bbdd` y `estado_servidor` leen con el estándar para todos.

## 7. El nombre

`sigrid_dm_restringido_ro` (el grupo AUTORIZADO, que ve MÁS) aparece en 19 ficheros fuera de
`progress/` y `specs/`: `settings.py`, `grants.py`, dos pasos de build (docstrings),
`contabilidad/00_setup.sql` (comentario), `02_roles.sql`, el runbook, `ARCHITECTURE.md`,
`.env.example`, cinco ficheros de test (21 apariciones), cuatro YAML del diccionario (las tres
reglas `R-*-RESTRINGIDA` lo nombran) y `BACKLOG.md`. El job NO fija `PG_RESTRICTED_ROLE`
(`infra/80_create_job.ps1` solo pasa `PG_READONLY_ROLE`): el nombre vive en el defecto del código.
`ALTER ROLE … RENAME TO` conserva OID, GRANT y pertenencias.

## 8. Decisiones abiertas para el humano

D1-D12 en `specs/F-141-perfil-restringido/design.md` §9, cada una con su recomendada. Las que
cambian la forma de la feature: **D1** vía (recomendada: solo MCP), **D3** contenido
(recomendada: `compras` + `maestro` + `_meta`), **D6** nombre (recomendada: renombrar el grupo
autorizado a `sigrid_dm_autorizado_ro`) y **D9** perfil por defecto del MCP (recomendada: por
defecto restringido, con lista de estándar).
