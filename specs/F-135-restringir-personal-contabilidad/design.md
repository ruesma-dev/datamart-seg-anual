<!-- specs/F-135-restringir-personal-contabilidad/design.md -->
# F-135 · Diseño

Mediciones: `progress/spec_F-135.md`. Requisitos: `requirements.md`. Decisiones: §8.

## 1. Encaje y límite

Todo vive en `build_contabilidad` (esquema módulo, F-056), en `apply_grants` y en
`infra/sql`. Sin ingesta nueva: lo restringido ya está en `raw`. La idea es la de
`personal` (F-057): **los permisos de PostgreSQL se dan por esquema**, así que lo que
el rol general no debe leer vive FÍSICAMENTE en otro esquema que nunca se le concede.

```
raw.apu ─► contabilidad_restringida.{plan_cuentas, mayor, saldos_cuenta_mes}   (completa, rol autorizado)
                     │  restringido = false
                     ▼
           contabilidad.{plan_cuentas, mayor, saldos_cuenta_mes, apuntes_restringidos_mes}  (general)
```

Lo que NO es de este repositorio y se deja escrito (R24): que `mcp-bbdd` conecte con un
rol distinto según quién pregunta y amplíe su lista blanca (su F-008), y que Power BI
tenga rol propio (F-087). Hasta entonces el rol autorizado existe pero no lo usa ningún
cliente: **nadie pierde lo que no debía ver, y quien debe verlo lo tiene en Sigrid**.
Límite de microservicio: nada sale de este repositorio; no hace falta extraer nada.

## 2. Ficheros

**Crear**
- `etl_sigrid/domain/restriccion_personal.py` — constantes y oráculo (§3).
- `etl_sigrid/infrastructure/postgres/sql/contabilidad/04_plan_cuentas_general.sql`,
  `05_mayor_general.sql`, `06_saldos_general.sql`, `07_apuntes_restringidos_mes.sql` (§4).
- `config/diccionario/contabilidad_restringida.yaml` — fichas de las 3 tablas.
- `tests/test_f135_dominio.py`, `tests/test_f135_sql.py`, `tests/test_f135_grants.py`.

**Modificar**
- `sql/contabilidad/00_setup.sql` — `CREATE SCHEMA IF NOT EXISTS contabilidad_restringida`.
- `sql/contabilidad/01_plan_cuentas.sql`, `02_mayor.sql`, `03_saldos_cuenta_mes.sql` —
  pasan a escribir en `contabilidad_restringida` (§4). `02` gana las tres columnas de R5.
- `application/steps/build_contabilidad_step.py` — `SUB_PASOS` con los 8 ficheros y su
  esquema destino; el docstring dice qué es general y qué restringido.
- `config/settings.py` — `raw` fuera de `DEFAULT_CONSUMPTION_SCHEMAS`;
  `DEFAULT_VETOED_SCHEMAS = "contabilidad_restringida,raw"`, campos `vetoed_schemas`
  (`PG_VETOED_SCHEMAS`), `restricted_role` (`PG_RESTRICTED_ROLE`, defecto
  `sigrid_dm_restringido_ro`) y `restricted_schemas` (`PG_RESTRICTED_SCHEMAS`, defecto
  `contabilidad_restringida`), con sus propiedades `*_list`. El comentario de
  `DEFAULT_EXCLUDED_TABLES` añade que devolver `raw` exige ahora también F-135.
- `infrastructure/postgres/grants.py` y `postgres_client.py` — §5.
- `application/steps/apply_grants_step.py` — §5.
- `infra/sql/02_roles.sql` — §6. `.env.example` — las tres variables nuevas.
- `etl_sigrid/domain/diccionario.py` — `contabilidad_restringida` en `ESQUEMAS_DEL_DATAMART`.
- `config/diccionario/contabilidad.yaml` (columnas nuevas, `saldo_acumulado` de lo
  visible, ficha de `apuntes_restringidos_mes`), `retenciones.yaml` (la excepción de
  R21), `00_global.yaml` (regla `R-CONTABILIDAD-RESTRINGIDA`, `version` 48).
- `tests/test_f056_contabilidad.py` — sus aserciones sobre 01-03 apuntan al esquema
  restringido (la semántica no cambia); `tests/test_f005_grants.py` y
  `tests/test_f068_exclusion_lectura_mcp.py` donde fijen la lista de consumo con `raw`.
- `docs/ARCHITECTURE.md` (§ capas y § datamart en Azure), `azure-apps/datamart_seg_anual.md`,
  `azure-apps/mcp_bbdd.md` §2 (el párrafo de lo que lee la credencial, como hizo F-068),
  `harness/features.json` (ficha de F-127, R23).

**No se tocan**: `sql/retenciones/*` (D4), `sql/personal/*` (D10), la ingesta y
`config/tables_sigrid.yaml` (no se filtra en origen: el rol autorizado necesita todo),
`mart`, `cierre`, `compras`, `maestro`, `descompuestos` (medido: no leen nada restringido)
y `PG_EXCLUDED_TABLES` (F-068 queda igual).

## 3. Dominio (`domain/restriccion_personal.py`, sin dependencias)

- `PREFIJOS_CUENTA_RESTRINGIDA: tuple[str, ...]` = los 14 de CR, y
  `PATRON_CONCEPTO_NOMINA = r"\mn[oóÓ]minas?\M"` (sintaxis de PostgreSQL; el dominio la
  traduce a `\b` para su propio `re`).
- `REGEX_CUENTA_RESTRINGIDA: str` = `'^(640|641|...|4753)'`, construida desde la tupla:
  es el literal que el SQL debe llevar tal cual (R4).
- `es_cuenta_restringida(codigo: str | None) -> bool`.
- `ApunteContable(codigo_cuenta: str | None, clase_asiento: str, concepto: str | None)`.
- `es_asiento_de_personal(apuntes: Sequence[ApunteContable]) -> bool` (R2, R3).
- `motivo_restriccion(apunte, asiento_es_personal: bool) -> str | None` (R7).

Son el oráculo de los tests de SQL y la referencia del diccionario; el SQL no los llama.

## 4. SQL de `contabilidad` (un fichero, una transacción, como hoy)

- `00_setup.sql`: crea también el esquema restringido. Lo crea `sigrid_dm_etl` y nace
  sin ninguna concesión al rol general (no hay `ALTER DEFAULT PRIVILEGES` para él).
- `01`, `03`: el SQL de hoy con el esquema destino cambiado; `02` lee el plan restringido.
- `02_mayor.sql` → `contabilidad_restringida.mayor`. Tras `clasificados`, un CTE
  `asientos_personal` agrupa por `asiento_id` (solo `asiento_id IS NOT NULL`):
  `bool_and(clase_asiento = 'NORMAL') AND bool_or(codigo_cuenta ~ <REGEX_CR> OR concepto
  ~* <PATRON>)`, y se une por `asiento_id` (hash join, sin ventana por asiento). De ahí
  `restringido`, `motivo_restriccion` (R7) y
  `saldo_acumulado_visible = CASE WHEN restringido THEN NULL ELSE SUM(importe_saldo)
  FILTER (WHERE NOT restringido) OVER (<la ventana de hoy>) END`. Índice nuevo
  `(restringido)` parcial `WHERE restringido`. La guarda R6 se queda en este fichero.
- `04_plan_cuentas_general.sql` → `contabilidad.plan_cuentas`: todas las filas del
  restringido + `restringida = (nivel = 5 AND codigo_cuenta ~ <REGEX_CR>)`;
  `nombre_cuenta = CASE WHEN restringida THEN '(cuenta restringida)' ELSE ... END`.
  `ruta_codigos` solo lleva códigos: no se enmascara. Mismos índices y PK.
- `05_mayor_general.sql` → `contabilidad.mayor`: `SELECT` de las columnas de hoy, en su
  orden, con `saldo_acumulado_visible AS saldo_acumulado`, `WHERE NOT restringido`.
  Mismos índices y PK que hoy. Guarda R10 en un `DO`: 0 filas con
  `codigo_cuenta ~ <REGEX_CR>` y `general + restringidos = completo`; si no, `RAISE` y la
  transacción se deshace (queda la tabla de la noche anterior, ya filtrada).
- `06_saldos_general.sql` → `contabilidad.saldos_cuenta_mes`: el `GROUP BY` de hoy sobre
  `contabilidad_restringida.mayor` con cada agregado `FILTER (WHERE NOT restringido)`,
  `num_apuntes_restringidos = COUNT(*) FILTER (WHERE restringido)`, `incompleto`, y
  `HAVING COUNT(*) FILTER (WHERE NOT restringido) > 0`. `saldo_acumulado` como hoy, sobre
  lo visible. Misma PK.
- `07_apuntes_restringidos_mes.sql` → `contabilidad.apuntes_restringidos_mes`: empresa,
  ejercicio, mes, `num_apuntes`, `num_asientos`; PK (empresa_id, ejercicio, mes).
  Sin importes (D5).

Coste medido/estimado: `build_contabilidad` tarda hoy 590 s. La copia general añade un
CTAS de ~2,12 M filas sin ventana nueva (el acumulado visible se calcula en `02`, en la
misma pasada) y sus índices: **estimado +3-5 min y +0,75 GB** (el mayor ocupa 744 MB);
el `.env` del puesto apunta a Azure, así que lo mide el humano en el despliegue (T15).

## 5. Permisos cada noche (`grants.py`, cliente y paso)

`grants.py`, funciones puras:
- `esquemas_en_conflicto(consumo, vetados) -> list[str]` (R17).
- `build_veto_statements(readonly_role, owner_role, vetoed_schemas) -> list[str]`: por
  esquema `REVOKE ALL ON ALL TABLES IN SCHEMA`, `REVOKE USAGE ON SCHEMA` y `ALTER DEFAULT
  PRIVILEGES [FOR ROLE owner] IN SCHEMA ... REVOKE SELECT ON TABLES FROM` (R16).
  Identificadores citados con `sql.Identifier`, como el resto del módulo.
- `build_restricted_grant_statements(restricted_role, owner_role, schemas)`: `USAGE`,
  `SELECT ON ALL TABLES` y el privilegio por defecto (R15).
- `build_readonly_grant_statements` NO cambia (F-068 intacto): los vetos se añaden detrás.

`PostgresClient`:
- `apply_readonly_grants(..., vetoed_schemas=())`: tras sus sentencias de hoy, las de veto
  de los esquemas vetados que EXISTEN (un `REVOKE` sobre un esquema ausente falla; uno
  ausente no tiene nada que proteger).
- `apply_restricted_grants(role, owner_role, schemas) -> list[str]`.
- `lecturas_indebidas(role, schemas, tables) -> list[str]`: `has_schema_privilege(role,
  s, 'USAGE')` por esquema y `has_table_privilege(role, t, 'SELECT')` por cada tabla de
  esos esquemas y de `tables`; devuelve lo que el rol PUEDE leer (R18). Solo catálogo.

`ApplyGrantsStep.run`, en este orden: (1) sin rol general → no-op de hoy; (2) conflicto
consumo ∩ vetados, o algún esquema restringido que no esté vetado → FAILED sin abrir
conexión de escritura; (3) concesiones generales + vetos; (4) si existe el rol autorizado,
sus concesiones; si no, `logger.warning` y sigue; (5) `lecturas_indebidas(rol general,
vetados, excluidas)` → si no está vacía, FAILED con la lista. `metadata`: `vetados`,
`rol_autorizado`, `verificacion = "ok"`. `main.py apply-grants` no cambia de firma.

## 6. `infra/sql/02_roles.sql` (MANUAL, administrador)

- Crea `sigrid_dm_restringido_ro NOLOGIN` si falta (sin contraseña: no es de login) y
  le da `CONNECT` sobre `sigrid_dm`, que heredarán sus futuros miembros.
- Crea el esquema `contabilidad_restringida` con `SET ROLE sigrid_dm_etl`.
- Punto 5: quita `raw` del bucle que concede al rol general y le da al autorizado el
  esquema restringido. Nuevo punto 5 ter, dentro del mismo `BEGIN ... COMMIT`: para
  `raw` y el esquema restringido, `REVOKE USAGE` + `REVOKE ALL ON ALL TABLES` como
  administrador y otra vez con `SET ROLE sigrid_dm_etl` (dos concedentes: lección F-068),
  y `ALTER DEFAULT PRIVILEGES FOR ROLE sigrid_dm_etl ... REVOKE`.
- Comprobación final: 0 filas de `information_schema.table_privileges` del rol general en
  esos dos esquemas, y `has_schema_privilege` falso.
- Un test (como `test_f068_r8`) comprueba que sus listas casan con `settings.py`.

## 7. Despliegue (MANUAL, en este orden, tras el review)

1. **Antes de nada (D3)**: el humano comprueba que ningún informe de Power BI lee `raw`
   (abrir los `.pbix` en uso: «Transformar datos», origen de cada consulta). `POWERBI.md`
   solo documenta `mart`, pero no lo prueba. Si alguno lo lee, se para y se decide.
2. Espacio: confirmar en el portal que el disco del servidor compartido admite +0,75 GB.
3. `infra/sql/02_roles.sql` como administrador (crea el rol y aplica el 5 ter).
4. Imagen con tag fechado y job apuntado a ella (comprobar el tag del job: memoria «el
   repositorio en verde no es producción»).
5. `python main.py build-contabilidad` y `python main.py apply-grants` desde el puesto
   (para no esperar a la noche con el mayor general aún sin filtrar).
6. Pruebas R25-R27 (`tasks.md` T16) y `publicar-diccionario` v48 + `check-diccionario` +
   reiniciar el MCP. 7. Al día siguiente, R28 sin tocar nada.

## 8. Decisiones abiertas para el humano (y para Juan)

**D1 · Criterio.** (a) V1, literal de Juan: asiento NORMAL con 640/642/649/465/466/476
entero + 460, 461, 544, 4753 enteras → 51.245 apuntes. (b) **V2 (recomendada)**: además
el asiento entero cuando lleva 460/461/544/4753 o concepto «nómina», y 641/643/644/645
(indemnizaciones) enteras → 55.504 (+4.258). V1 deja ver los pagos de anticipos y
embargos contra banco con el trabajador en el concepto (371 asientos de nómina sin
cuentas N2). V1 ⊂ V2 al 100 %.

**D2 · Mecanismo.** (a1) **Recomendada**: copia completa en esquema propio + general
filtrada y materializada (+0,75 GB, +3-5 min). Garantía física, el MCP sigue en 30 s, el
autorizado ve hoy lo mismo que hoy. (a2) Vista `security_barrier` sobre la completa: 0 GB,
pero un `LIKE` del usuario no es *leakproof* y deja de usar índices (riesgo para los 30 s
del MCP) y cambia tabla por vista. (a3) Partición disjunta (general + solo los 55.504
restringidos): +20 MB, pero el acumulado completo de 71 prefijos de cuentas mixtas no se
puede reconstruir sin recalcular sobre 2,17 M filas. (b) RLS: el dueño de las vistas se
la salta (haría falta `FORCE`), no corrige el acumulado (que delata) ni distingue a nadie
mientras MCP y Power BI compartan rol; y en `raw` exigiría políticas con subconsulta.

**D3 · `raw`.** (A) **Recomendada**: fuera entero del rol general. El MCP ya no lo admite
(lista blanca) y `raw` trae, además del mayor, 37.048 efectos de nómina de 1.015
trabajadores con su cuenta bancaria (`raw.pag`), 100.502 repartos analíticos (`raw.apa`),
las cabeceras (`raw.con`, `raw.asi`), `raw.rac` y `raw.hmores`. Condición: paso 1 de §7.
(B) Si Power BI lee `raw`: `raw` sigue concedido y van a `PG_EXCLUDED_TABLES`
`raw.apu, raw.apa, raw.asi, raw.pag, raw.rac, raw.hmores` (sin `raw.con`, que es el
maestro de todo: sus 521 nombres de cuenta CR quedarían visibles). Cambia R16, R19 y
R25; el resto, igual.

**D4 · `retenciones`.** (A) **Recomendada**: no se toca; los 8 apuntes (4 proveedores,
19.963,11 € en valor absoluto) son retenciones de proveedor en asientos mixtos, sin dato
de trabajador. (B) Quitarlos: el saldo de esos 4 proveedores dejaría de cuadrar y
`build_retenciones` pasaría a depender del criterio (hoy corre antes que contabilidad).

**D5 · «Cuánto queda fuera».** **Recomendada: solo recuentos** (`num_apuntes_restringidos`,
`incompleto`, `apuntes_restringidos_mes`). Dar el importe restringido por empresa y mes
sería dar la masa salarial mensual, que es lo que se protege.

**D6 · Nombres de cuentas CR en el plan general.** **Recomendado enmascarar** las 521:
que exista una cuenta de préstamo o de embargo a nombre de alguien ya es el dato.

**D7 · Nombres.** Esquema `contabilidad_restringida`, rol `sigrid_dm_restringido_ro`.

**D8 · «Ese rol» (para Juan).** Quiénes son y por qué canal (MCP, Power BI Desktop,
consulta directa). **Recomendado**: aquí solo el grupo `NOLOGIN`; un rol de login por
canal se crea cuando Juan dé la lista, por `infra/sql` y con contraseña en Key Vault.

**D9 · 570.** **Recomendado (lo de Juan)**: solo dentro de AP (207 apuntes de 124
cuentas). Alternativa: esas 124 cuentas enteras (+12.031 apuntes).

**D10 · Coste por persona en `personal`** (`partes_lineas.precio/importe`,
`recursos_tipos_hora.precio_coste`): hoy lo leen MCP y Power BI por decisión del
2026-09-22, y es el mismo dato que `raw.reshor`, revocada. Fuera de F-135; preguntar a Juan.

**D11 · 641/643/644/645** entran en CR (dentro de D1-b). **D12 · 4751**: 62 de sus 101
cuentas tienen forma de nombre de persona; fuera de AP son retenciones de profesionales.
Se quedan visibles salvo que Juan diga que son trabajadores.

## 9. Riesgos

- **Ventana del primer despliegue**: hasta que corre el paso 5 de §7 el mayor general
  sigue sin filtrar (como hoy). Por eso el build va a mano el mismo día.
- **Un `.env` viejo con `raw` en la lista de consumo** (ya pasó con `personal`): R17 lo
  para en seco en vez de reabrir `raw` en silencio.
- **Restringir de más** oculta ~7.270 apuntes que no son de personal (asientos mixtos) y
  deja incompletas 6.063 filas de saldos: está marcado, y se afina con Juan.
- **Lo que este cambio no arregla**: la credencial sigue siendo una para MCP y Power BI;
  quien la tenga ve la contabilidad general, no la restringida.
