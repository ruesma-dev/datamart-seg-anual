<!-- specs/F-141-perfil-restringido/design.md -->
# F-141 · Diseño

Mediciones: `progress/spec_F-141.md` (§N = sección de ese informe; §9 las de la segunda pasada).
**D1-D12 CERRADAS por el humano el 2026-10-16 y P1-P2 el 2026-10-17** (§9, con sus palabras).

## 1. Encaje y límite

- Es la mitad «base de datos» del tercer perfil, como F-136 lo fue del total: grupo, login,
  permisos nocturnos, comprobación en el catálogo, diccionario y contrato. **Elegir el login según
  quién pregunta es de `mcp-bbdd`** (otro repositorio, una feature suya): aquí solo su contrato
  (§7). Power BI no entra (D1).
- Capas: settings, aplicación (`apply_grants`), infraestructura Postgres, `02_roles.sql`
  (MANUAL), diccionario, documentación. Sin dominio nuevo ni objetos de datos: solo permisos.
- Granularidad (D2): **esquemas y objetos enteros**, con la lista de objetos excluidos como
  CONFIGURACIÓN extensible. Columnas: no ahora; cómo se añadirían, en §11.

## 2. Qué ve y qué no (D3, D4, D5)

Regla del humano: «ven como el estándar, menos el mayor, menos el mayor analítico, menos la
cartera de cobros (pero sí a retenciones)».

| Objeto | Estándar | Total | **Restringido** |
|---|---|---|---|
| `mart`, `cierre`, `stg`, `descompuestos`, `aux`, `maestro`, `_meta` | sí | sí | **sí** |
| `compras` entero, **incluidas** `vencimientos`, `v_facturas_pago`, `v_control_forma_pago` (D4) | sí | sí | **sí** |
| `retenciones` (incluye `apuntes_contables`: 49.762 apuntes del mayor de sus cuentas) | sí | sí | **sí** |
| `contabilidad.plan_cuentas`, `apuntes_restringidos_mes` | sí | sí | **sí** |
| `contabilidad.mayor` (2,12 M apuntes) y `contabilidad.saldos_cuenta_mes` (390.195, P1) | sí | sí | **no** |
| `personal` entero (nombre, NIF, DNI, coste por persona; P2) | sí | sí | **no** |
| El mayor ANALÍTICO (`raw.apa`, 709.403 filas): hoy NO está publicado; lo publicará F-127 | — | — | **no** (§5, vigilancia) |
| `tesoreria` (`efectos`, `efectos_restringidos_mes`) | sí | sí | **no** |
| `*_restringida`, `raw` | no / sí / no | | **no** |

Por D4 el restringido ve el ESTADO DE PAGO de las facturas (si y cuándo se pagó, forma de pago)
por las tres vistas de `compras`, aunque no lea la cartera: lo dice su ficha (§8). Con `compras`
entero lee las cinco tablas de origen de los adjuntos: la regla de F-139 (D1) se cumple sola.

## 3. Ficheros

**Modificar**
- `config/settings.py`: `DEFAULT_RESTRICTED_ROLE = "sigrid_dm_autorizado_ro"` y
  `NOMBRE_AUTORIZADO_RETIRADO = "sigrid_dm_restringido_ro"` (D6);
  `DEFAULT_PERFIL_RESTRINGIDO_GROUP = "sigrid_dm_perfil_restringido_ro"`,
  `…_LOGIN = "mcp_sigrid_dm_restringido"`, `…_SCHEMAS` = el consumo menos `tesoreria`
  y `personal` (`mart,cierre,compras,maestro,retenciones,contabilidad,descompuestos,stg,aux,_meta`:
  lista EXPLÍCITA, un esquema de consumo nuevo no le llega solo), `…_EXCLUDED_TABLES =
  "contabilidad.mayor,contabilidad.saldos_cuenta_mes"`; campos `perfil_restringido_group/_login/_schemas/_excluded_tables` y
  sus `*_list`; comentario con la regla del humano y el aviso del nombre.
- `.env.example`: las cuatro `PG_PERFIL_RESTRINGIDO_*` y el nombre nuevo del autorizado.
- `etl_sigrid/infrastructure/postgres/grants.py`: `EXCEPCIONES_FILTRACION_RESTRINGIDO =
  {"compras.vencimientos": "tesoreria", "compras.v_facturas_pago": "tesoreria",
  "compras.v_control_forma_pago": "tesoreria"}` (D4, nominal); `PATRON_VIGILADO_RESTRINGIDO =
  r"mayor"`; `TABLAS_ORIGEN_ADJUNTOS` (las cinco de F-139: un test la contrasta con
  `ORIGEN_POR_FAMILIA` de `tests/test_f139_limite.py`); `perfil_restringido_en_conflicto` y
  `build_perfil_restringido_statements` (§4, §5); docstring con el nombre nuevo.
- `etl_sigrid/infrastructure/postgres/postgres_client.py`: `SQL_VISTAS_QUE_FILTRAN`,
  `SQL_OBJETOS_VIGILADOS`, `SQL_PERTENENCIAS`; `vistas_que_filtran`, `objetos_vigilados`,
  `pertenencias`, `apply_perfil_restringido` (§5).
- `etl_sigrid/application/steps/apply_grants_step.py`: guardas (§4), bloque (§5), docstring.
- `infra/sql/02_roles.sql`: §6. `infra/15_provision_db.ps1`: exige `RESTRINGIDO_PWD` y rótulo.
- `docs/runbook_postgres_azure.md`: tabla de roles y §13 NUEVA (§6).
- `docs/ARCHITECTURE.md`: siete roles, qué lee el restringido, su comprobación, el nombre y la
  obligación de F-127 (§5).
- `config/diccionario/00_global.yaml`, `contabilidad.yaml`, `tesoreria.yaml`, `compras.yaml` y
  cabeceras de los tres YAML `*_restringida` (§8).
- Renombre del autorizado (D6), solo texto: docstrings de `build_contabilidad_step.py` y
  `build_tesoreria_step.py`, comentario de `sql/contabilidad/00_setup.sql`, y las 21 apariciones
  de `tests/test_f135_grants.py`, `test_f135_sql.py`, `test_f136_login_total.py`,
  `test_f037_grants.py`, `test_f138_grants.py` (cambia el literal, no la aserción).
- `../azure-apps/datamart_seg_anual.md` (contrato §7) y `../azure-apps/mcp_bbdd.md` (un enlace).
  Commit propio en `azure-apps`, sin push.

**Crear**: `tests/test_f141_perfil_restringido.py` (§10).

**NO se tocan**: el SQL de capas; `infra/80_create_job.ps1` e `infra/env/dev.json` (los defectos
viven en el código; el job no fija `PG_RESTRICTED_ROLE`); `.env` y `.env.*.bak` (los edita el
HUMANO); el repositorio `mcp-bbdd`; `BACKLOG.md` y `harness/features.json` (son del líder).

## 4. Configuración y guardas (antes de abrir conexión)

Tras las de F-135 y F-136, en este orden; ninguna abre conexión:
1. `restricted_role == NOMBRE_AUTORIZADO_RETIRADO` → FAILED: «nombre retirado por F-141; el grupo
   autorizado es `sigrid_dm_autorizado_ro`» (un `.env` viejo dejaría al total sin las tres
   `*_restringida` tras el primer `DROP` nocturno, con solo un aviso).
2. Grupo o login iguales a `readonly_role`, `restricted_role`, `total_role`, `set_role` o entre
   sí → FAILED nombrando la variable.
3. `perfil_restringido_en_conflicto`: esquemas del restringido fuera del consumo o en vetados,
   restringidos o vetados del total → FAILED con la lista.
4. `_meta` fuera de sus esquemas → FAILED (el MCP no tendría diccionario).
5. Objeto excluido mal escrito (`partir_tabla_cualificada`) o de un esquema no concedido → FAILED.
6. Una de `TABLAS_ORIGEN_ADJUNTOS` excluida (o su esquema fuera) sin excluir
   `compras.documento_adjuntos` → FAILED (F-139 D1).

Grupo vacío → nada del restringido (`rol_restringido = "(sin configurar)"`, «no aplica»).

## 5. `apply_grants`: el bloque del restringido (el ÚLTIMO, tras el total)

```
si no role_exists(grupo) -> warning apply_grants_restringido_inexistente; "no aplica"; SUCCESS
otros    = list_schemas() - esquemas_r - {pg_catalog, information_schema, pg_toast, pg_temp_*, public}
filtran  = pg.vistas_que_filtran(esquemas_r, otros + excluidas_r) - EXCEPCIONES   # D10
vigilados= pg.objetos_vigilados(esquemas_r, PATRON_VIGILADO) - excluidas_r      # el mayor analítico
sentencias += pg.apply_perfil_restringido(grupo, dueno, esquemas_r, excluidas_r + filtran + vigilados)
sentencias += build_veto_statements(grupo, dueno, otros)
indebidas_r = pg.lecturas_indebidas(grupo y login, otros, excluidas_r + filtran + vigilados)
pert = pg.pertenencias(login), pg.pertenencias(grupo); faltan = pg.esquemas_sin_usage(login, esquemas_r)
```

- `otros` sale del CATÁLOGO, no de la configuración: hoy `tesoreria`, `personal`, `raw` y las tres
  `*_restringida`; mañana, cualquier esquema que nadie haya listado. `public` está vacío y sin
  `CREATE` (informe §1).
- `build_perfil_restringido_statements(grupo, dueno, esquemas, database, excluidas, ausentes)`,
  pura: `GRANT CONNECT`; por esquema `USAGE` y `SELECT ON ALL TABLES`; **siempre** `ALTER DEFAULT
  PRIVILEGES FOR ROLE <dueño> IN SCHEMA … REVOKE SELECT ON TABLES FROM <grupo>` (nunca GRANT por
  defecto: lo que nazca no lo lee hasta que esta comprobación lo haya visto); al final `REVOKE ALL
  ON TABLE` de cada excluida existente, de cada vista que filtra y de cada vigilado.
- `SQL_VISTAS_QUE_FILTRAN`: la clausura recursiva del informe §3 (`pg_rewrite` + `pg_depend`,
  vista sobre vista) de las vistas de `esquemas_r` que alcanzan un esquema de `otros` (salvo
  `raw`, que lo leen las vistas curadas de `maestro` y `compras`) o un objeto excluido. Hoy
  devuelve exactamente las tres excepciones de D4 (informe §9). Una excepción que el catálogo YA
  NO devuelve → aviso `apply_grants_restringido_excepcion_sobrante` y `metadata`.
- `SQL_OBJETOS_VIGILADOS`: tablas y vistas de `esquemas_r` cuyo nombre casa con `mayor`. Hoy solo
  `contabilidad.mayor`, ya excluido. **El mayor analítico no existe todavía**: lo publicará F-127;
  si nace con «mayor» en el nombre y nadie lo excluye, la nocturna se lo revoca y FAILED. Si F-127
  le pone otro nombre, su spec TIENE que añadirlo a `PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES`
  (queda en `ARCHITECTURE.md` y en la nota al líder para la ficha de F-127).
- Resultado: FAILED si `filtran` o `vigilados` no están vacíos (ya revocados: es la alarma), si
  `indebidas_r` no está vacía o si el login es miembro de algo que no sea el grupo o el grupo de
  algo (`pertenencias`, `pg_auth_members`); UN mensaje con todo, junto a lo del
  estándar y el total (patrón F-136 R9). `faltan` → solo aviso. Login ausente → aviso, se
  comprueba el grupo. Grupo ausente → aviso, SUCCESS (no expone nada).
- `metadata`: `rol_restringido`, `login_restringido`, `verificacion_restringido`,
  `filtraciones_restringido`, `vigilados_restringido`, `pertenencias_restringido`,
  `acceso_restringido`, `excepciones_sobrantes`.

## 6. `infra/sql/02_roles.sql` y procedimiento MANUAL (runbook §13)

1. **Renombre** (antes de todo): `\if` existe `sigrid_dm_restringido_ro` y no
   `sigrid_dm_autorizado_ro` → `ALTER ROLE … RENAME TO sigrid_dm_autorizado_ro`; los dos →
   `RAISE EXCEPTION`; solo el nuevo → nada. Conserva OID, GRANT y pertenencias.
2. **Guarda** (patrón F-136 R18): login inexistente sin `RESTRINGIDO_PWD` → error antes de crear
   nada. `\getenv restringido_pwd RESTRINGIDO_PWD` bajo el silencio `\set` existente.
3. **Punto 1**: `CREATE ROLE sigrid_dm_perfil_restringido_ro NOLOGIN` y `mcp_sigrid_dm_restringido
   LOGIN` si faltan; contraseña opcional con `\echo` sin valor; `NOCREATEDB NOCREATEROLE` (sin
   `NOSUPERUSER`). **Punto 3**: `CONNECT` al GRUPO.
4. **Punto 5 quinquies** (en el `BEGIN … COMMIT`, tras el 5 quater): al grupo, lo de la nocturna
   (USAGE y SELECT en sus diez esquemas, default privileges en REVOKE, `REVOKE` de los dos
   excluidos, veto de `tesoreria`, `personal`, `raw` y las `*_restringida`) y `GRANT <grupo> TO
   mcp_sigrid_dm_restringido WITH INHERIT TRUE, SET FALSE`. Ningún otro `GRANT … TO <login>`.
5. **Punto 6**: los siete roles; pertenencias del login (solo el grupo); `has_schema_privilege`
   del login `t` en los diez y `f` en `tesoreria`, `personal`, `raw` y las tres `*_restringida`;
   `has_table_privilege` `f` en `contabilidad.mayor` y `saldos_cuenta_mes`, `t` en `contabilidad.plan_cuentas` y
   `compras.vencimientos`; `CONNECT` = `t`; cero filas de `table_privileges` del login.

Runbook §13 (PowerShell 5.1, una sesión, de día, patrón F-136 §6): **P0** puerta (UTC 07-21, sin
ejecución del job en curso, imagen con F-141 desplegada); **P1** variables; **P2** `Nueva-Clave`
→ `kv-mcp-bbdd-dev/pg-password-restringido` (`-o none`); **P3** releer a `$env:RESTRINGIDO_PWD`;
**P4** `psql -X -v ON_ERROR_STOP=1 -f $roles $dsn`; **P5** borrar la variable; **P6** negativa y
positiva con el login real y `apply-grants` desde el puesto; **P7** estándar y total
antes/después; **P8** la nocturna siguiente; **P9** contrato a `mcp-bbdd`. Vuelta atrás:
`02_roles.sql` es idempotente; el renombre se deshace con el `RENAME` inverso y la imagen anterior.
**Imagen y `02_roles.sql` el MISMO día, entre nocturnas** (P0): con la imagen nueva y el nombre
viejo, el autorizado «no existiría» y el total perdería las `*_restringida` tras los `DROP`.

## 7. Contrato para `mcp-bbdd` (va a `azure-apps/datamart_seg_anual.md`)

- **E1. Login** `mcp_sigrid_dm_restringido`; mismo host, base, puerto y TLS. **Secreto**
  `pg-password-restringido` en `kv-mcp-bbdd-dev`, por referencia al vault; nunca por valor.
- **E2. Lee** lo del estándar menos `contabilidad.mayor`, `saldos_cuenta_mes`, `tesoreria` y
  `personal` (y, cuando exista, el mayor
  analítico de F-127). `permission denied` en eso. No escribe. Sin `SET ROLE`.
- **E3. Quién** (D9-B): **por defecto restringido**; estándar y total por LISTA de oid (secretos
  del contenedor, nunca un repositorio). Un oid en dos listas → el arranque falla.
- **E4. Nunca hacia arriba**: pool restringido sin configurar o caído → `PERFIL_NO_DISPONIBLE`,
  jamás el estándar (al revés que el total). Poblar la lista de estándar ANTES de desplegar.
- **E5. Catálogo** (D11): `listar_tablas`, `describir_tabla` y `contexto_bbdd` del restringido
  con SU login (solo lo que puede leer); sin identidad, restringido.
- **E6. El perfil se dice**: `estado_servidor` devuelve el perfil de quien pregunta (la IA aplica
  `R-PERFIL-RESTRINGIDO` sin adivinar); la traza lleva `perfil=restringido`.
- **E7. Lista blanca** común, sin esquemas nuevos. **Pool** máx. 2 (28 de 50 en uso, informe §1).
- **E8. Orden**: F-141 desplegada y verificada (R31-R34) ANTES que la feature de `mcp-bbdd`; el
  diccionario nuevo sale con F-141.

## 8. Diccionario (D7; versión = la siguiente a la de `main` en el momento del merge)

- **`R-PERFIL-RESTRINGIDO`** (nueva, bloqueante, `_global`): tres perfiles, TOTAL ⊃ ESTÁNDAR ⊃
  RESTRINGIDO; el restringido (administrativos) ve lo del estándar menos `contabilidad.mayor`, el
  mayor analítico y `tesoreria`; los `*_restringida` son del TOTAL y NO del perfil restringido;
  un `permission denied` no se rodea (ni reconstruyendo el mayor o sus saldos desde
  `retenciones.apuntes_contables`, ni las personas desde los logins de `compras`, ni la cartera desde `compras.vencimientos`): se responde que
  el perfil no lo incluye. Sin nombres de personas, oid ni UPN.
- **Las tres `R-*-RESTRINGIDA`**: grupo `sigrid_dm_autorizado_ro` y una frase: «"restringida" =
  reservada al perfil total; el perfil RESTRINGIDO (administrativos) ve MENOS que el estándar y
  no lee este esquema» (en tesorería: tampoco la general). Títulos sin cambio.
- **Avisos al principio de la ficha**: `contabilidad.mayor`, `saldos_cuenta_mes`, los dos de
  `tesoreria` y los seis de `personal`, «No disponible para el perfil restringido»; las tres vistas de pago
  de `compras`, que el restringido las lee y por ellas ve el estado de pago de las facturas aunque
  no lea la cartera. Cabeceras de los tres YAML `*_restringida`: grupo nuevo.
- Ningún objeto nuevo: cobertura y `check-diccionario`, igual.

## 9. Decisiones del humano (CERRADAS el 2026-10-16) y preguntas que quedan

- **D1 Vía: A, solo MCP.** **D5: aceptar** (ya no aplica: `stg` está concedido).
- **D2: esquemas y objetos enteros hoy**; «en el futuro es posible que haya que limitar columnas
  o tablas»: lista de objetos excluidos como configuración y columnas preparadas (§11).
- **D3: «ven como el estándar, menos el mayor, menos el mayor analítico, menos la cartera de
  cobros (pero sí a retenciones)»** (§2), ajustada por P1-P2.
- **D4: «no»**, «compras debe poder verse»: las tres vistas de pago visibles, como excepción
  nominal de la guarda (test que falla si sobran).
- **D6: «el nombre que quieras»** → renombrar el autorizado a `sigrid_dm_autorizado_ro`; grupo
  `sigrid_dm_perfil_restringido_ro` + login `mcp_sigrid_dm_restringido`.
- **D7: regla nueva + frase en las tres + avisos**; versión la siguiente a `main` al fusionar.
- **D8: grupo NOLOGIN + login miembro.** **D9: B** (contrato). **D10: revocar y FAILED**, con
  las tres excepciones de D4. **D11: catálogo con el login del perfil.** **D12: no se funde.**
- **P1 y P2 (cerradas el 2026-10-17): «personal también quítalo, y saldos cuenta también».** El
  restringido no ve el esquema `personal` ni `contabilidad.saldos_cuenta_mes` (el mayor agregado).
  Medido: ninguna vista que ve lee `personal` ni `saldos_cuenta_mes` (informe §10).

## 10. Pruebas

- **Sin red ni BBDD** (`tests/test_f141_perfil_restringido.py`): settings y `.env.example`;
  guardas sin llamadas al cliente; `build_perfil_restringido_statements` pura; paso con cliente
  falso (sin configurar, ausente, filtraciones y vigilados revocados y FAILED, excepción sobrante,
  indebidas, pertenencias, mensaje único, `metadata`, `rows_processed`); SQL de los tres métodos
  con conexión simulada; **excepciones de D4 vivas**: la de `vencimientos` lee `tesoreria.` en
  `05_vencimientos.sql` y las otras dos leen `compras.vencimientos` en `06_pago_factura.sql` (si
  una deja de leerlo, el test falla y la excepción sobra); `02_roles.sql` textual; renombre (grep);
  diccionario: versión ≥ la de `git show main:config/diccionario/00_global.yaml` + 1.
- **PostgreSQL 16 real local** (contenedor, `psql.exe` 16.4, patrón F-136 T10): `02_roles.sql`
  dos veces con el nombre VIEJO (renombra; el total conserva las `*_restringida`) y con el nuevo;
  vista nueva en `mart` que lee `tesoreria` → revocada y FAILED; tabla `contabilidad.mayor_x` →
  vigilada; `GRANT USAGE ON SCHEMA tesoreria TO PUBLIC` → FAILED; login miembro del estándar →
  FAILED; negativa y positiva.
- **Azure, MANUAL del humano**: runbook §13 P4-P8 (R31-R34).

## 11. Riesgos y cómo crece

- **Columnas (D2, futuro, no se implementa)**: `PG_PERFIL_RESTRINGIDO_EXCLUDED_COLUMNS`
  (`esquema.tabla.columna`); el builder, tras el `SELECT ON ALL TABLES`, haría por tabla afectada
  `REVOKE SELECT ON TABLE` + `GRANT SELECT (<columnas visibles del catálogo>)`, cada noche (los
  `DROP` lo borran); verificación con `has_column_privilege`; la ficha avisaría de que `SELECT *`
  da `permission denied`. Grupo, login, guardas y contrato no cambian. Tablas: ya es la lista.
- Una feature que meta en un esquema del restringido una TABLA con datos del mayor o de la cartera
  la verá el restringido: la guarda solo ve vistas y nombres. Mitigan la regla de §8 y el aviso en
  `ARCHITECTURE.md`. `_meta` describe todo el datamart (sin datos): aceptado (D11). Sin `personal`
  siguen visibles los logins y nombres de usuarios de Sigrid de `compras.documento_procesos`,
  `documento_alarmas.creada_por` y `documento_adjuntos.subido_por` («compras debe poder verse»).
- D9-B cambia `mcp-bbdd` para todos: mal desplegado deja sin estándar a quien lo tenía (hacia menos).
