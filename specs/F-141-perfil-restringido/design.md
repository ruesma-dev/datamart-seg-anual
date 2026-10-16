<!-- specs/F-141-perfil-restringido/design.md -->
# F-141 · Diseño

Mediciones: `progress/spec_F-141.md` (§N = sección de ese informe). Todo lo de abajo sigue la
opción RECOMENDADA de cada decisión de §9; si el humano elige otra, se ajustan R y T antes de
tocar código.

## 1. Encaje y límite

- Es la mitad «base de datos» del tercer perfil, como F-136 lo fue del total: grupo, login,
  permisos nocturnos, comprobación en el catálogo, diccionario y contrato. **Elegir el login según
  quién pregunta es de `mcp-bbdd`** (otro repositorio, una feature suya nueva): aquí solo se fija
  su contrato (§7). Power BI no entra (D1, §6 del informe: un login no acota por persona allí).
- Capas: `config/settings.py`, aplicación (`apply_grants`), infraestructura Postgres (cliente y
  `grants.py`), `infra/sql/02_roles.sql` (MANUAL), diccionario, documentación. Sin dominio nuevo:
  no hay regla de negocio, solo permisos. No crea ni cambia ningún objeto de datos.
- Granularidad (D2): **esquemas enteros más una lista corta de vistas excluidas**. Columnas
  enmascaradas y filas por obra quedan descartadas con medida (§9 D2, informe §4-§5).

## 2. Qué ve y qué no (D3-D5, recomendadas)

| | Estándar | Total | **Restringido** |
|---|---|---|---|
| `compras` | sí | sí | sí, menos `vencimientos`, `v_facturas_pago`, `v_control_forma_pago` (leen `tesoreria`) |
| `maestro`, `_meta` | sí | sí | sí (`maestro.obras` lee dos booleanos de `stg`: dependencia aceptada) |
| `mart`, `cierre`, `stg`, `descompuestos`, `aux` | sí | sí | **no** (venta, coste, margen, presupuesto, estudios) |
| `contabilidad`, `tesoreria`, `retenciones` | sí | sí | **no** (el dinero) |
| `personal` | sí | sí | **no** (las personas) |
| `*_restringida` | no | sí | **no** |
| `raw` | no | no | **no** |

`compras` entero hace que el restringido lea las cinco tablas de origen de los adjuntos: la regla
de F-139 (D1) se cumple sin vistas por familia ni RLS (informe §6).

## 3. Ficheros

**Modificar**
- `config/settings.py`: `DEFAULT_RESTRICTED_ROLE = "sigrid_dm_autorizado_ro"` (D6) y
  `NOMBRE_AUTORIZADO_RETIRADO = "sigrid_dm_restringido_ro"`; `DEFAULT_PERFIL_RESTRINGIDO_GROUP =
  "sigrid_dm_perfil_restringido_ro"`, `DEFAULT_PERFIL_RESTRINGIDO_LOGIN =
  "mcp_sigrid_dm_restringido"`, `DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS = "compras,maestro,_meta"`,
  `DEFAULT_PERFIL_RESTRINGIDO_EXCLUDED_TABLES = "compras.vencimientos,compras.v_facturas_pago,
  compras.v_control_forma_pago"`; campos `perfil_restringido_group/_login/_schemas/
  _excluded_tables` y sus propiedades `*_list`; comentario con la decisión del humano
  (2026-10-16, «administrativos y gente así», ve MENOS que el estándar) y el aviso del nombre.
- `.env.example`: las cuatro `PG_PERFIL_RESTRINGIDO_*` y el nombre nuevo del autorizado.
- `etl_sigrid/infrastructure/postgres/grants.py`: `DEPENDENCIAS_ACEPTADAS_RESTRINGIDO =
  {"maestro.obras": ("stg",)}`; `TABLAS_ORIGEN_ADJUNTOS` (las cinco de F-139: un test la
  contrasta con `ORIGEN_POR_FAMILIA` de `tests/test_f139_limite.py`); `build_perfil_restringido_
  statements` y `perfil_restringido_en_conflicto` (§4, §5); docstring con el nombre nuevo.
- `etl_sigrid/infrastructure/postgres/postgres_client.py`: `SQL_VISTAS_QUE_FILTRAN`,
  `SQL_PERTENENCIAS`, `vistas_que_filtran`, `pertenencias`, `apply_perfil_restringido` (§5).
- `etl_sigrid/application/steps/apply_grants_step.py`: guardas (§4), bloque del restringido
  (§5), docstring.
- `infra/sql/02_roles.sql`: §6. `infra/15_provision_db.ps1`: exige `RESTRINGIDO_PWD` y rótulo.
- `docs/runbook_postgres_azure.md`: tabla de roles; §13 NUEVA (§6 P0-P9).
- `docs/ARCHITECTURE.md`: siete roles, qué lee el restringido, su comprobación, el nombre.
- `config/diccionario/00_global.yaml` (regla nueva y las tres `R-*-RESTRINGIDA`, versión 54),
  `compras.yaml` (aviso en las tres vistas excluidas), cabeceras de `contabilidad_restringida.yaml`,
  `tesoreria_restringida.yaml`, `compras_restringida.yaml` (§8).
- Renombre del autorizado (D6), solo texto: `build_contabilidad_step.py`,
  `build_tesoreria_step.py` (docstrings), `sql/contabilidad/00_setup.sql` (comentario), y las
  21 apariciones de `tests/test_f135_grants.py`, `test_f135_sql.py`, `test_f136_login_total.py`,
  `test_f037_grants.py`, `test_f138_grants.py` (el literal cambia, la aserción no).
- `../azure-apps/datamart_seg_anual.md` (contrato §7, fila nueva en la tabla de consumidores) y
  `../azure-apps/mcp_bbdd.md` (una línea que enlaza). Commit propio en `azure-apps`, sin push.

**Crear**: `tests/test_f141_perfil_restringido.py` (§10).

**NO se tocan**: el SQL de capas (ningún objeto cambia); `infra/80_create_job.ps1` e
`infra/env/dev.json` (los defectos viven en el código; el job no fija `PG_RESTRICTED_ROLE`);
`.env` y `.env.*.bak` (los edita el HUMANO); el repositorio `mcp-bbdd`; `BACKLOG.md` (generado).

## 4. Configuración y guardas (antes de abrir conexión)

Tras las guardas de F-135 y F-136, en este orden; ninguna abre conexión:
1. `restricted_role == NOMBRE_AUTORIZADO_RETIRADO` → FAILED: «nombre retirado por F-141: el
   grupo autorizado se llama `sigrid_dm_autorizado_ro`» (un `.env` viejo dejaría al total sin
   las tres `*_restringida` tras el primer `DROP` nocturno, con solo un aviso).
2. Grupo o login del restringido igual a `readonly_role`, `restricted_role`, `total_role`,
   `set_role` o entre sí → FAILED nombrando la variable.
3. `perfil_restringido_en_conflicto(...)`: esquemas del restringido que no están en el consumo o
   que están en vetados, restringidos o vetados del total → FAILED con la lista.
4. `_meta` fuera de los esquemas del restringido → FAILED (el MCP no tendría diccionario).
5. Tabla excluida mal escrita (`partir_tabla_cualificada`) o de un esquema no concedido → FAILED.
6. Una de `TABLAS_ORIGEN_ADJUNTOS` excluida (o su esquema fuera) sin excluir
   `compras.documento_adjuntos` → FAILED (F-139 D1: el índice sigue a su tabla de origen).

Grupo vacío → nada del restringido (`rol_restringido = "(sin configurar)"`, «no aplica»).

## 5. `apply_grants`: el bloque del restringido (el ÚLTIMO, tras el total)

```
si no role_exists(grupo) -> warning apply_grants_restringido_inexistente; "no aplica"; SUCCESS
filtran  = pg.vistas_que_filtran(esquemas_r, excluidas_r, DEPENDENCIAS_ACEPTADAS_RESTRINGIDO)
sentencias += pg.apply_perfil_restringido(grupo, dueno, esquemas_r, excluidas_r + filtran)
indebidas_r = pg.lecturas_indebidas(grupo, otros, excluidas_r + filtran)      # y del login
pert = pg.pertenencias(login) ; pert_g = pg.pertenencias(grupo)
faltan = pg.esquemas_sin_usage(login, esquemas_r)    # solo si el login existe
```

- `otros` = TODOS los esquemas existentes (`list_schemas`) menos los del restringido y menos
  `pg_catalog`, `information_schema`, `pg_toast`, `pg_temp_*` y `public` (vacío, sin `CREATE`):
  del CATÁLOGO y no de la configuración, para que un esquema que nadie listó también se mire.
- `build_perfil_restringido_statements(grupo, dueno, esquemas, database, excluidas, ausentes)`,
  pura: `GRANT CONNECT` a la base; por esquema `USAGE` y `SELECT ON ALL TABLES`; **siempre**
  `ALTER DEFAULT PRIVILEGES FOR ROLE <dueño> IN SCHEMA … REVOKE SELECT ON TABLES FROM <grupo>`
  (nunca GRANT por defecto: lo que nazca no lo lee hasta que esta comprobación lo vea); al final,
  `REVOKE ALL ON TABLE` de cada excluida existente y de cada vista que filtra. Después,
  `build_veto_statements(grupo, dueno, otros)` (reutilizada tal cual).
- `vistas_que_filtran`: `SQL_VISTAS_QUE_FILTRAN` es la clausura recursiva medida en el informe §3
  (`pg_rewrite` + `pg_depend`, vista sobre vista) de las vistas de `esquemas_r` que alcanzan un
  esquema que no está en `esquemas_r` ni es `raw`/`pg_catalog`/`information_schema`; devuelve
  `esquema.vista`, quitando las excluidas y las aceptadas (aceptada = vista Y esquema de origen
  listados en la constante). Solo catálogo.
- `pertenencias(rol) -> list[str]`: `SELECT g.rolname FROM pg_auth_members … WHERE member = rol`.
- Resultado: FAILED si `filtran` no vacía (ya revocadas: es la alarma de que una feature nueva
  creó una vista que lee lo que el restringido no ve), si `indebidas_r` no vacía, si el login es
  miembro de algo que no sea el grupo o el grupo de algo. UN mensaje con todo lo que falle, junto a
  lo del estándar y el total (patrón F-136 R9). `faltan` no vacía → solo aviso
  (`apply_grants_restringido_incompleto`). Login ausente → aviso, se comprueba solo el grupo.
- `metadata`: `rol_restringido`, `login_restringido`, `verificacion_restringido`,
  `filtraciones_restringido`, `pertenencias_restringido`, `acceso_restringido`. Grupo ausente:
  no es FAILED, no expone nada (como el autorizado).

## 6. `infra/sql/02_roles.sql` y procedimiento MANUAL (runbook §13)

En el orden del fichero:
1. **Renombre** (antes de todo, fuera de la transacción): `\if` existe
   `sigrid_dm_restringido_ro` y no `sigrid_dm_autorizado_ro` → `ALTER ROLE … RENAME TO
   sigrid_dm_autorizado_ro`; si existen los dos → `RAISE EXCEPTION`. Conserva OID, GRANT y
   pertenencias (el total sigue siendo miembro). Todo el fichero usa ya el nombre nuevo.
2. **Guarda** (patrón F-136 R18): login inexistente y `RESTRINGIDO_PWD` ausente → error antes de
   crear nada. `\getenv restringido_pwd RESTRINGIDO_PWD`, silencio `\set` ya existente.
3. **Punto 1**: `CREATE ROLE sigrid_dm_perfil_restringido_ro NOLOGIN` y
   `mcp_sigrid_dm_restringido LOGIN` si faltan; contraseña opcional con `\echo` sin valor;
   `NOCREATEDB NOCREATEROLE` (sin `NOSUPERUSER`). **Punto 3**: `CONNECT` al GRUPO.
4. **Punto 5 quinquies** (dentro del `BEGIN … COMMIT`, tras el 5 quater): concesiones al grupo
   sobre `compras`, `maestro`, `_meta` como la nocturna (default privileges en REVOKE), `REVOKE`
   de las tres vistas, y `GRANT sigrid_dm_perfil_restringido_ro TO mcp_sigrid_dm_restringido WITH
   INHERIT TRUE, SET FALSE`. Ningún `GRANT … TO mcp_sigrid_dm_restringido` más.
5. **Punto 6**: los siete roles; pertenencias del login (exactamente el grupo); `has_schema_
   privilege` del login: `compras`/`maestro`/`_meta` = t; `personal`, `contabilidad`,
   `tesoreria`, `mart`, `stg`, `raw` y las tres `*_restringida` = f; `has_table_privilege`
   de `compras.vencimientos` = f; `CONNECT` = t; cero filas de `table_privileges` del login.

Runbook §13, Windows PowerShell 5.1, una sesión, de día (patrón F-136 §6): **P0** puerta (hora
UTC 07-21, ninguna ejecución del job, imagen con F-141 desplegada); **P1** variables; **P2**
`Nueva-Clave` → `kv-mcp-bbdd-dev/pg-password-restringido` (`-o none`); **P3** releer del vault a
`$env:RESTRINGIDO_PWD` (más `APP_PWD`/`MCP_PWD`/`TOTAL_PWD` NO: opcionales desde F-136);
**P4** `psql -X -v ON_ERROR_STOP=1 -f $roles $dsn`; **P5** borrar la variable; **P6** negativa y
positiva con el login real (R31-R32) y `apply-grants` desde el puesto; **P7** comparación del
estándar y del total antes/después (R33); **P8** al día siguiente, la nocturna (R34); **P9**
entregar el contrato a `mcp-bbdd`. Vuelta atrás: `02_roles.sql` es idempotente; el renombre se
deshace con `ALTER ROLE … RENAME` inverso y la imagen anterior.

**Orden de despliegue** (D6): imagen con F-141 y `02_roles.sql` el MISMO día, entre nocturnas.
Si la nocturna corriera con la imagen nueva antes del renombre, el autorizado «no existe» y el
total perdería las `*_restringida` tras los `DROP` (aviso, no FAILED): P0 lo impide.

## 7. Contrato para `mcp-bbdd` (va a `azure-apps/datamart_seg_anual.md`)

- **E1. Login** `mcp_sigrid_dm_restringido`; mismo host, base, puerto y TLS. **Secreto**
  `pg-password-restringido` en `kv-mcp-bbdd-dev`, por referencia al vault; nunca por valor.
- **E2. Lee** `compras` (menos las tres vistas de pago), `maestro`, `_meta`; nada más.
  `permission denied` en el resto. No escribe. Sin `SET ROLE`.
- **E3. Quién** (D9, recomendada B): **por defecto restringido**; estándar y total por LISTA de
  oid (secretos del contenedor, nunca un repositorio). Un oid en dos listas → el arranque falla.
- **E4. Nunca se degrada hacia arriba**: si el pool restringido no está configurado o no conecta,
  quien le toca recibe `PERFIL_NO_DISPONIBLE`, jamás el estándar (lo contrario que el total).
- **E5. Catálogo** (D11): `listar_tablas`, `describir_tabla` y `contexto_bbdd` del restringido,
  con SU login (solo lo que puede leer); sin identidad, restringido.
- **E6. El perfil se dice**: `estado_servidor` devuelve el perfil de quien pregunta, para que la
  IA aplique `R-PERFIL-RESTRINGIDO` sin adivinar; la traza lleva `perfil=restringido`.
- **E7. Lista blanca**: común; ningún esquema nuevo. **Pool** máx. 2 (28 de 50 en uso, informe §1).
- **E8. Orden**: F-141 desplegada y verificada (R31-R34) ANTES que la feature de `mcp-bbdd`; el
  diccionario v54 sale con F-141.

## 8. Diccionario (versión 54)

- **`R-PERFIL-RESTRINGIDO`** (nueva, bloqueante, ámbito `_global`): hay tres perfiles, de más a
  menos: TOTAL ⊃ ESTÁNDAR ⊃ RESTRINGIDO. El restringido (administrativos) lee solo `compras`
  (menos tres vistas de pago), `maestro` y `_meta`. Los esquemas `*_restringida` NO son del perfil
  restringido: son de acceso reservado al TOTAL. Ante `permission denied` no se rodea (ni por otra
  vista, ni reconstruyendo desde `compras`): se responde que el perfil no lo incluye. Sin nombres
  de personas, oid ni UPN.
- **Las tres `R-*-RESTRINGIDA`**: el grupo pasa a `sigrid_dm_autorizado_ro` y cada una suma una
  frase: «"restringida" = reservada al perfil total; el perfil RESTRINGIDO (administrativos) ve
  MENOS que el estándar y no lee este esquema» (en contabilidad y tesorería: tampoco la general).
  Títulos sin cambio (los lee ya el MCP).
- **`compras.yaml`**: las tres vistas excluidas EMPIEZAN por «No disponible para el perfil
  restringido (`R-PERFIL-RESTRINGIDO`)». Cabeceras de los tres YAML `*_restringida`: grupo nuevo.
  Ningún objeto nuevo: cobertura y `check-diccionario`, igual.

## 9. Decisiones para el humano (recomendada en negrita)

- **D1 Vía**: **A, solo MCP** (elige login por persona); B, MCP y un modelo de Power BI aparte con
  el mismo grupo (otro login miembro, F-087); C, solo Power BI (un login no acota a una persona
  en Power BI: informe §6).
- **D2 Granularidad**: **esquemas enteros + vistas excluidas**; columnas (privilegios por
  columna: `SELECT *` falla, 48 columnas de importe en 14 objetos solo de `compras`, se pierden en
  cada `DROP`); filas por obra con RLS (informe §4: las 54 vistas saltan RLS, arreglarlo abre
  `raw`; 29 ficheros con `DROP TABLE`; 18 de 31 objetos de `compras` sin obra; §5: no hay fuente
  de obras por persona, haría falta una tabla a mano y alguien que la mantenga).
- **D3 Contenido**: **A, «documental»: `compras`, `maestro`, `_meta`**; B, A más `tesoreria` y
  `retenciones` (la cartera; `retenciones` trae apuntes contables de sus cuentas); C, el estándar
  menos `personal`, `contabilidad` y `tesoreria` (ve márgenes, venta y estudios).
- **D4 Vistas de pago de `compras`** (con A o C): **excluir las tres**; o dejar
  `v_facturas_pago`/`v_control_forma_pago` (dicen si y cuándo se pagó cada factura).
- **D5 `maestro.obras` ← `stg`**: **aceptar** (dos booleanos); o excluirla (sin maestro de obras).
- **D6 Nombre**: **A, renombrar el grupo autorizado a `sigrid_dm_autorizado_ro`** y perfil
  restringido = grupo `sigrid_dm_perfil_restringido_ro` + login `mcp_sigrid_dm_restringido`; B,
  sin renombrar (convivirían `…restringido_ro`, que ve MÁS, y `…restringido`, que ve MENOS; un
  `GRANT` equivocado abre la contabilidad completa, aunque la comprobación lo cace en una noche);
  C, un nombre técnico sin «restringido» (`mcp_sigrid_dm_basico`) y «restringido» solo en prosa.
  Los esquemas `*_restringida` no se renombran en ninguna (diccionario, MCP, reglas).
- **D7 Diccionario**: **regla nueva + frase en las tres + aviso en las tres vistas (v54)**; o solo
  la regla nueva.
- **D8 Modelo de permisos**: **grupo NOLOGIN con los GRANT + login miembro** (lo pide el
  `acceptance`; permite D1-B sin rehacer nada); o GRANT directos al login.
- **D9 Perfil por defecto del MCP**: **B, por defecto restringido y listas de estándar y total**
  (hoy cualquier cuenta del tenant que llegue a la URL ve el estándar; olvidarse a alguien le da
  MENOS, no más; exige poblar la lista de estándar ANTES de desplegar en `mcp-bbdd`); A, lista de
  restringidos y por defecto estándar (como hoy; olvidarse a un administrativo le da MÁS).
- **D10 Vista que filtra**: **revocarla y FAILED**; o solo FAILED (seguiría legible esa noche).
- **D11 Catálogo del MCP**: **con el login del perfil** (E5); o aceptar que vea nombres y fichas
  de lo que no lee (como se aceptó para el estándar en F-008).
- **D12 F-087**: **no se funde** (Power BI no acota por persona con un login; F-087 es el rol
  propio de Power BI y sigue aparte).

## 10. Pruebas

- **Sin red ni BBDD** (`tests/test_f141_perfil_restringido.py`): settings y `.env.example`;
  guardas sin llamadas al cliente; `build_perfil_restringido_statements` pura (orden, REVOKE por
  defecto, ni un `GRANT … ON TABLES` por defecto, excluidas al final); paso con cliente falso
  (sin configurar, ausente, filtraciones revocadas y FAILED, indebidas, pertenencias, mensaje
  único, `metadata`, `rows_processed`); SQL de `vistas_que_filtran` y `pertenencias` con conexión
  simulada; contrato textual de `02_roles.sql`; renombre (grep en el árbol); diccionario v54.
- **PostgreSQL 16 real local** (contenedor desechable, `psql.exe` 16.4 de Windows, patrón F-136
  T10): `02_roles.sql` dos veces sobre una base con el nombre VIEJO (renombra) y otra con el
  nuevo (no toca); una vista nueva en `compras` que lee `tesoreria` → revocada y FAILED; `GRANT
  personal TO PUBLIC` → FAILED; login miembro del estándar → FAILED; negativa y positiva.
- **Azure, MANUAL del humano**: runbook §13 P4-P8 (R31-R34).

## 11. Riesgos

- Una feature futura que meta en `compras` una TABLA con datos de otro esquema la verá el
  restringido: la guarda solo ve vistas. Lo mitiga la regla de §8 y el aviso en `ARCHITECTURE.md`.
- `_meta` describe TODO el datamart (fichas de `personal` incluidas, sin datos). Aceptado (D11).
- D9-B cambia `mcp-bbdd` para todos: mal desplegado deja sin estándar a quien lo tenía (hacia menos).
