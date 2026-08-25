<!-- specs/F-006-mcp-azure/requirements.md -->
# F-006 · El diccionario semántico del datamart — Requisitos (EARS)

**Rigor: `critico`.** La ficha de `harness/features.json` no declara `rigor`, y
`CHECKPOINTS.md` §«Niveles de rigor» dice que la omisión se resuelve con el
nivel más exigente. Además lo merece por sí misma: esta feature **cambia los
permisos de lectura sobre una base que vive en un servidor compartido con
`albaranes` y `partes` en producción** (R23–R26) y **publica en la propia base
el texto que decide qué SQL escribirá un agente contra ella** (R13–R18). Aplica
`critico`: fase RED con traza, cobertura de las líneas cambiadas, cero mutantes
supervivientes sin justificación aceptada por el humano, y toda verificación
`MANUAL (humano)` con su comando exacto y su resultado real.

> **Petición al humano:** añadir `"rigor": "critico"` a la ficha de F-006 en
> `harness/features.json`. Hoy funciona por omisión y eso es frágil.

---

## 0 · Qué es esta feature y qué no

### 0.1 · El encuadre que manda (humano, 2026-08-20)

La ficha de F-006 describe un servidor MCP en cloud. **Esta spec no es eso.**
El humano reformuló el objetivo el 2026-08-20 y su reformulación manda sobre la
ficha:

- Los seis casos de uso que dictó son **pruebas de aceptación, no la
  especificación**: «habrá infinidad de ellos; el contexto del MCP debe explicar
  la estructura y significado de la BBDD para que el agente que conectemos por
  MCP pueda hacer sus propios casos de uso».
- El objetivo de fondo: este datamart tendrá **todo el conocimiento de negocio
  de la obra de la empresa**, extraído de Sigrid y posiblemente de otras
  fuentes.
- **El usuario final es de negocio, no técnico.**

De ahí el objeto de esta spec: **el datamart tiene que saber explicarse solo.**
No basta con que los datos estén; tienen que venir acompañados de su
significado, su grano, sus relaciones, sus trampas y su fecha de caducidad, en
un formato que un agente lea **por SQL contra la propia base**, sin conocer este
repositorio ni ningún fichero.

### 0.2 · Decisiones ya tomadas por el humano (no se reabren)

1. **El diccionario semántico vive aquí como YAML versionado, y un paso del ETL
   lo publica dentro de la propia base**, en `_meta`. El MCP lo lee por SQL.
   Razón: el multi-base sale gratis (cada base publica su semántica en su propio
   `_meta`) y permite una puerta automática de cobertura.
2. **El prototipo `mcp-bbdd` se migra, no se reescribe** (`git init` + arnés +
   transporte HTTP). Ocurre en SU repositorio y queda fuera de esta spec.
3. **Se empieza por el diccionario**, antes que por el despliegue en cloud.
4. Los huecos de dominio ya están dados de alta como **F-036** (oficios),
   **F-037** (tesorería), **F-038** (comparativos), **F-039** (vistas puente) y
   **F-040** (ingresos). **No se especifican aquí**: esta spec solo deja el
   diccionario preparado para crecer con ellos.

### 0.3 · Alcance de esta spec

| Bloque | Qué entra |
|---|---|
| **A · Formato** | El contrato del YAML del diccionario y su validador |
| **B · Reglas** | Las advertencias transversales codificadas como reglas duras |
| **C · Frescura** | Qué se refresca de noche y qué no, y cómo se cita |
| **D · Publicación** | El paso del ETL que publica el YAML en `_meta` |
| **E · Cobertura** | La puerta que impide que el diccionario se quede atrás |
| **F · Rol de lectura** | Acotar `mcp_sigrid_dm_ro` a los esquemas de consumo |
| **G · Conectividad** | Qué hace falta en el firewall para que el MCP llegue |
| **H · Aceptación** | La batería de preguntas de negocio como criterio de éxito |

### 0.4 · Fuera de alcance (explícito)

- **El servidor MCP entero**: transporte HTTP, autenticación Entra,
  autorización por grupo, multi-base, auditoría de quién consulta qué,
  Dockerfile, despliegue en Container Apps, `git init` y arnés del prototipo.
  Todo eso vive en el repositorio `mcp-bbdd` y lo ejecuta el arnés de ese
  repositorio. Aquí solo se produce **el dato que ese servidor consumirá** y
  **el permiso con el que lo consumirá**.
- **F-030** (las reglas de negocio en lenguaje natural como prompt, con su
  circuito de vuelta) y **D8** (dónde se persiste una planificación hecha por la
  IA). Son piezas vecinas y **dependencias declaradas**, no se resuelven aquí.
  Ver §6.
- **La ingesta de datos nuevos**: F-036 a F-040. Esta spec **no añade ni una
  columna al modelo**.
- **F-034** (rol separado para Power BI) y **F-032** (limpieza de copias viejas
  de secretos). Se dice cómo encajan (§F, R26) y no se invaden.

### 0.5 · Corrección de un dato que arrastran los informes

Los cuatro informes de exploración dicen «los ocho esquemas». **Son NUEVE**:
`_meta`, `raw`, `stg`, `aux`, `mart`, `cierre`, `compras`, `maestro`,
`retenciones`. `infra/sql/02_roles.sql:74-85` los crea y su propio comentario
dice «los nueve esquemas»; `DEFAULT_CONSUMPTION_SCHEMAS` en
`config/settings.py:81-83` lista los nueve. El diccionario debe cubrir **nueve**.
(Ojo con una trampa de nombres: el esquema se llama `aux`, pero su carpeta de
SQL es `sql/auxiliar/` — la primera línea de
`sql/auxiliar/01_periodificacion.sql` todavía se declara a sí misma como
`sql/aux/…`.)

### 0.6 · Hechos verificados que la spec da por ciertos

- **`run-all` construye `raw → stg → mart` y aplica grants**
  (`main.py:405-428`: `IngestRaw → LoadExcelAux → BuildStg → BuildMart →
  ApplyGrants`). `cierre`, `compras`, `maestro` y `retenciones` **NO están en el
  pipeline nocturno**: se construyen con comandos propios y pueden estar
  arbitrariamente desfasados.
- **Los GRANT se reaplican en cada ejecución** porque siete ficheros SQL recrean
  vistas con `DROP VIEW ... CASCADE` y un `DROP` se lleva los `GRANT`
  (`etl_sigrid/infrastructure/postgres/grants.py`, docstring).
- **`apply_readonly_grants` solo CONCEDE; nunca REVOCA**
  (`postgres_client.py:656-694` + `grants.py:24-74`). **Consecuencia crítica y
  no evidente: estrechar `PG_CONSUMPTION_SCHEMAS` NO quita el acceso que ya está
  concedido.** Sin REVOKE explícito, acotar el rol es un cambio cosmético.
- **`mcp_sigrid_dm_ro` es hoy el único rol de lectura** y ve los nueve
  esquemas, `raw` y `stg` incluidos (`infra/sql/02_roles.sql:96-115`).
- **La IP de salida del entorno de Container Apps del ETL es estática**
  (`68.221.221.85`, regla `caj-datamart-seg-dev`) **porque el entorno se creó a
  propósito sin integración de VNet** (`docs/ARCHITECTURE.md` §Infra).
  Perseguir IPs de puesto no funciona: D11, CGNAT.
- **`_meta.v_frescura` y `_meta.v_raw_state` ya existen y ya son legibles por el
  rol del MCP** (F-024, `sql/ddl/00_meta.sql:44-99`).
- **El prototipo `mcp-bbdd` cubre 34 fichas de cinco esquemas** (`mart`,
  `cierre`, `stg`, `compras`, `retenciones`) en 1.083 líneas, y **`maestro` y
  `aux` no aparecen en todo el proyecto**. Su `pendiente.yaml` lista 37 tablas
  con columnas sin describir. Ese YAML es **el punto de partida del formato, no
  el contenido final**.

---

## 1 · Bloque A · Formato del diccionario

**R1 (Ubicuo).** El sistema debe mantener el diccionario semántico del datamart
como **YAML versionado en `config/diccionario/`**, con un fichero por esquema
(`_meta.yaml`, `raw.yaml`, `stg.yaml`, `aux.yaml`, `mart.yaml`, `cierre.yaml`,
`compras.yaml`, `maestro.yaml`, `retenciones.yaml`) más un fichero global
`00_global.yaml`. Un único fichero monolítico queda descartado: 34 fichas ya
ocupan 1.083 líneas en el prototipo y aquí hay más de 80 objetos.

**R2 (Ubicuo).** Cada ficha de objeto debe declarar, como mínimo: `tipo`
(`tabla`|`vista`|`funcion`), `capa` (`origen`|`preparacion`|`consumo`|
`operacion`), `consumo_recomendado` (booleano), `descripcion` (de negocio, no
técnica), `grano` (qué es una fila), `clave_negocio` (lista de columnas),
`paso_etl`, `refresco`, `columnas`, `relaciones` y `ejemplos_preguntas`. El
formato exacto está fijado en `design.md` §3 y es un **contrato**.

**R3 (Comportamiento no deseado).** SI una ficha declara
`consumo_recomendado: false`, ENTONCES el validador debe exigir un
`motivo_no_consumo` no vacío y fallar si falta. Sin esa exigencia,
`consumo_recomendado: false` sería la puerta trasera para esquivar la puerta de
cobertura de columnas (R20) sin que se note en el diff.

**R4 (Ubicuo).** El diccionario debe cubrir **los nueve esquemas** (§0.5). Cada
esquema debe tener, además de sus fichas, una entrada propia en `00_global.yaml`
con su título de negocio, para qué sirve, si es superficie de consumo y su
régimen de refresco.

**R5 (Comportamiento no deseado).** SI una `relacion` de una ficha apunta a un
`esquema.objeto.columna` que no existe en el diccionario, ENTONCES el validador
debe fallar nombrando la ficha, la relación y el destino no resuelto. Una
relación rota es peor que ninguna: el agente escribirá el JOIN igual.

**R6 (Ubicuo).** Cada columna documentada debe tener `significado` en lenguaje
de negocio. El validador debe admitir la forma abreviada
`columna: "<significado>"` como equivalente a `columna: {significado: "..."}`,
para que las 800+ columnas no exijan tres líneas cada una.

**R7 (Comportamiento no deseado).** SI una columna declara `agregacion`,
ENTONCES su valor debe pertenecer al vocabulario cerrado
`suma | promedio | no_sumable | suma_solo_dentro_del_mes | ultimo_valor |
clave_sustituta`, y el validador debe fallar ante cualquier otro valor. El
vocabulario es cerrado a propósito: es lo que el MCP traduce a «esta columna no
se suma».

**R8 (Ubicuo).** El validador del diccionario debe ser **dominio puro**:
ejecutable sin red, sin BBDD y sin leer nada fuera de `config/diccionario/`.

---

## 2 · Bloque B · Las reglas duras

**R9 (Ubicuo).** `00_global.yaml` debe declarar un bloque `reglas` con, como
mínimo, estas **doce** reglas, cada una con `codigo`, `titulo`, `severidad`
(`bloqueante`|`aviso`), `ambito` (esquemas y/u objetos afectados), `regla` (qué
hacer y qué no hacer) y `motivo` (por qué, con el incidente real si lo hubo):

| Código | Regla | Origen |
|---|---|---|
| `R-FRESCURA-MANUAL` | Cuatro de los nueve esquemas (`cierre`, `compras`, `maestro`, `retenciones`) **no se refrescan de noche**; toda respuesta que salga de ellos cita su fecha de build | A0.1 |
| `R-IMPORTE-MES` | `importe_mes` **no se suma entre meses**; `importe_origen` ya es acumulado y sumarlo en el tiempo multiplica (~9x) | A0.2, bug de la Tanda 1.4 |
| `R-UNIVERSO-OBRA` | Hay **dos universos de obra**: `stg.obras` (excluye administrativas, códigos de 5+ dígitos, deduplica por `conext.cod='15'`) y `maestro.obras` (no filtra). Toda respuesta que cuente obras dice cuál usa | A0.3 |
| `R-OBRA-ACTIVA` | `stg.obras.activa` está **cableado a `TRUE`** y no significa nada; para saber si una obra vive, `maestro.obras.es_activa` o las fechas de `cierre.v_pbi_cierre_cabecera` | A0.4 |
| `R-VERSION-MASTER` | En `stg.plan_mensual` conviven **todas** las versiones master: filtrar solo por obra y ámbito **multiplica los importes por el número de versiones**. La vigente solo está resuelta aguas abajo: ir a `mart`, no a `stg` | A0.5 |
| `R-FAS-AMBIGUO` | `fas` significa dos cosas: **mes** en ámbitos reales (3, 7; `fas=0` = «Previsto» vivo) y **número de versión** en master (8, 11). Se llama `fase_num` en `stg.presupuesto`, `version` en `stg.plan_mensual` y `fasnum` en `raw.obrfas` | A0.6 |
| `R-CLAVE-SUSTITUTA` | `plan_id`, `fact_id`, `fact_cat_id` y `cierre_id` son `BIGSERIAL` y **cambian en cada build**: nunca como identificador estable ni expuestos al usuario | A0.7 |
| `R-ABONO-NEGATIVO` | En `compras` los **abonos ya entran con signo negativo**: no se restan otra vez | informe de casos de uso §1 |
| `R-LINEA-ID-NO-UNICA` | `compras.fact_compras_linea` **no tiene PK y `linea_id` NO es único** (viene de `ctrpro`, `dcapro` y `dcfpro`, que colisionan). La clave real es `(tipo_doc, linea_id)` | inventario, `compras` |
| `R-RETENCION-NO-JOIN-LINEAS` | **Nunca unir un efecto de retención a las líneas de su factura**: multiplica el importe por el número de líneas. El error real dio 38,9 M€ en una obra siendo esa la cifra de toda la empresa | prototipo `notas_globales` |
| `R-COMPRAS-SIN-IVA` | Los importes de `compras` son **sin IVA**, mientras que `maestro.proveedores_obra.importe_contratado` es `SUM(ctr.totdoc)`, **total del documento CON IVA**: no son comparables | inventario, `maestro` |
| `R-COMPRAS-TIPO-DOC` | En `compras.fact_compras_linea` hay seis tipos de documento en la misma tabla: **no filtrar `tipo_doc` triplica** | prototipo `notas_globales` |

**R10 (Ubicuo).** El bloque `reglas` debe incluir además **órdenes de magnitud
de referencia** (por ejemplo: ~34,7 M€ retenidos a proveedores, ~21,9 M€ de
clientes, ~27.300 efectos), para que el agente detecte una cifra absurda antes
de darla por buena. Es lo que hizo el prototipo y funcionó.

**R11 (Comportamiento no deseado).** SI una regla `bloqueante` declara en su
`ambito` un `esquema.objeto` que no existe en el diccionario, ENTONCES el
validador debe fallar. Una regla que apunta a la nada no protege nada.

**R12 (Dirigido por evento).** CUANDO se publica el diccionario, el sistema debe
**adjuntar a cada ficha los códigos de las reglas cuyo ámbito la incluye**, de
modo que un agente que solo consulte la ficha de un objeto vea sus trampas sin
haber leído el bloque global. La derivación es automática (dominio puro): el
autor de la ficha no tiene que acordarse.

---

## 3 · Bloque C · Frescura

**R13 (Ubicuo).** Cada ficha debe declarar `refresco` ∈ `nocturno | manual |
estatico` y `paso_etl` (el nombre del paso tal y como aparece en la columna
`paso` de `_meta.v_frescura`, p. ej. `build_mart`).

**R14 (Comportamiento no deseado).** SI una ficha de `cierre`, `compras`,
`maestro` o `retenciones` declara `refresco: nocturno`, ENTONCES el validador
debe fallar: esos cuatro esquemas no están en `build_pipeline_steps`
(`main.py:422-428`) y decir lo contrario es exactamente la mentira que produce
respuestas de hace semanas dadas con aplomo. El test debe leer la composición
real del pipeline, no una lista copiada.

**R15 (Ubicuo).** El sistema debe publicar una vista `_meta.v_diccionario` que
una cada objeto documentado con su fila de `_meta.v_frescura` por `paso_etl`, de
modo que **una sola consulta** devuelva significado y fecha de build. El JOIN
debe ser `LEFT`: un objeto cuyo paso nunca terminó bien sigue saliendo, con la
frescura a nulo.

**R16 (Ubicuo).** `00_global.yaml` debe declarar, en su bloque de reglas, que
toda respuesta construida sobre objetos con `refresco: manual` **debe citar su
fecha de build**, y decir con qué consulta se obtiene
(`SELECT * FROM _meta.v_frescura`).

---

## 4 · Bloque D · Publicación en `_meta`

**R17 (Dirigido por evento).** CUANDO se ejecuta `python main.py
publicar-diccionario`, el sistema debe cargar los YAML de
`config/diccionario/`, validarlos (R2–R14), y **reemplazar** el contenido de
`_meta.diccionario`, `_meta.diccionario_reglas` y `_meta.diccionario_publicacion`.

**R18 (Ubicuo).** El reemplazo debe hacerse **en una sola transacción**
(`DELETE` + `INSERT`, nunca `DROP TABLE`), de modo que un MCP que consulte
durante la publicación vea el diccionario anterior completo o el nuevo completo,
nunca uno a medias ni vacío. Es seguro hacerlo transaccional aquí —y solo aquí—
porque son unos cientos de filas: nada que ver con el caso de
`stg.plan_mensual`, que se trocea a propósito (F-019).

**R19 (Comportamiento no deseado).** SI el diccionario no valida, ENTONCES el
sistema debe fallar **antes de abrir la transacción de escritura**, dejar
publicado el diccionario anterior intacto y devolver el informe de validación
con el fichero y la ficha culpables.

**R20 (Ubicuo).** El paso `publicar_diccionario` debe formar parte del pipeline
de `run-all`, **después de `build_mart` y ANTES de `apply_grants`**. El orden no
es cosmético: `apply_grants` concede `SELECT ON ALL TABLES IN SCHEMA _meta`, que
es una foto del momento; publicar después dejaría las tablas nuevas dependiendo
solo del `ALTER DEFAULT PRIVILEGES`.

**R21 (Comportamiento no deseado).** SI el paso de publicación falla, ENTONCES
debe terminar en `FAILED` (y `run-all` salir con código 1) **sin deshacer ni
tocar el build de datos**: `mart` queda construido y el diccionario anterior
sigue publicado. Un fallo de publicación es una noticia, no una catástrofe.

**R22 (Ubicuo).** `_meta.diccionario_publicacion` debe registrar `version`,
`hash_fuente` (SHA-256 de los YAML en orden), `publicado_en` (UTC sin zona, como
el resto de `_meta`), `batch_id` de la ejecución, y los recuentos de objetos,
reglas y columnas más el porcentaje de cobertura. Es lo que permite responder
«¿el diccionario que estás leyendo es el del repositorio?» sin salir de SQL.

**R23 (Comportamiento no deseado).** SI alguien necesita cambiar la lista de
columnas de `_meta.v_diccionario`, ENTONCES debe documentarse que ese cambio
exige `DROP VIEW` y por tanto **un `apply-grants` inmediato después**, porque el
`DROP` se lleva los `GRANT` del rol del MCP. `CREATE OR REPLACE VIEW` solo
admite añadir columnas al final.

---

## 5 · Bloque E · La puerta de cobertura

**R24 (Ubicuo).** El sistema debe incluir una **puerta offline** (pytest, sin
red ni BBDD) que compare el diccionario contra el **inventario de objetos que
este repositorio publica**, derivado de sus propios ficheros: los `CREATE TABLE`
y `CREATE [OR REPLACE] VIEW` de `etl_sigrid/infrastructure/postgres/sql/**` y
las tablas declaradas en `config/tables_sigrid.yaml` para `raw`.

**R25 (Comportamiento no deseado).** SI existe un objeto en ese inventario que
no tiene ficha en el diccionario y no está en la lista `pendientes` de
`00_global.yaml`, ENTONCES la puerta debe **fallar** y `bash harness/init.sh`
quedar en rojo. Umbral: **100 % de los objetos, bloqueante.** Justificación: un
objeto publicado sin ficha es el caso peligroso —el agente lo ve en el catálogo
del servidor y **inventa** su significado—, y no admite grados.

**R26 (Comportamiento no deseado).** SI un objeto con `consumo_recomendado:
true` tiene una columna sin `significado`, ENTONCES la puerta debe **fallar**.
Para los objetos con `consumo_recomendado: false` la falta de descripción de
columnas es **aviso**, no fallo. Umbral: **100 % de columnas en la superficie de
consumo; 0 % exigido fuera de ella.**

> **Por qué un booleano y no un porcentaje.** Un umbral del 95 % permite
> justamente que la columna que falte sea la importante: nadie audita cuál es el
> 5 %. Acotar el 100 % a los objetos que el diccionario **recomienda** para
> consumo hace el trabajo finito (unas 25–30 vistas, no las 31 tablas de `raw`
> con sus ~800 columnas de Sigrid) y deja la decisión de qué entra en la
> superficie donde debe estar: en una decisión editorial visible en el diff, no
> en un porcentaje. El antídoto contra la trampa evidente —bajar
> `consumo_recomendado` para esquivar la puerta— es R3.

**R27 (Ubicuo).** La lista `pendientes` de `00_global.yaml` es un **trinquete**:
la puerta debe fallar si crece respecto al valor declarado en la propia puerta.
**Al cerrar F-006 debe estar vacía** y ese es un criterio de aceptación del
reviewer.

**R28 (Dirigido por evento).** CUANDO se ejecuta `python main.py
check-diccionario`, el sistema debe comparar el diccionario contra el catálogo
**real** de la base (`information_schema`), listar objetos publicados sin ficha
y fichas que ya no corresponden a ningún objeto, y salir con código 1 si hay
alguna discrepancia. Este comando es la verdad; la puerta offline (R24) es solo
un trinquete barato que corre en cada `init.sh`. Verificación `MANUAL (humano)`.

**R29 (Ubicuo).** La puerta offline debe declararse en su propio docstring como
**heurística**: lee SQL con expresiones regulares, así que puede no ver un
objeto creado dinámicamente (por ejemplo, las tablas de `raw`, que se crean con
`ensure_raw_table` desde Python). Por eso `raw` se inventaría desde
`config/tables_sigrid.yaml` y no desde el SQL, y por eso existe R28.

---

## 6 · Bloque F · El rol de lectura

**R30 (Ubicuo).** El valor por defecto de `PG_CONSUMPTION_SCHEMAS`
(`DEFAULT_CONSUMPTION_SCHEMAS`, `config/settings.py:81-83`) debe pasar a
**`_meta,mart,cierre,compras,maestro,retenciones,aux`**, retirando `raw` y
`stg`. Motivo: para un MCP abierto a usuarios de negocio, `raw` es una copia
literal de Sigrid sin semántica y `stg` es una capa intermedia cuyo objeto
principal (`stg.plan_mensual`) **multiplica los importes si se consulta sin
filtrar versión** (R-VERSION-MASTER). Dejarlos visibles es ofrecerle al agente
el camino que produce números falsos.

**R31 (Ubicuo).** `build_readonly_grant_statements` debe poder emitir, además de
los `GRANT`, los **`REVOKE`** correspondientes a los esquemas de la base que
**no** están en la lista de consumo. Sin esto, estrechar la lista no quita nada:
la función de hoy solo concede (§0.6).

**R32 (Comportamiento no deseado).** SI `PG_REVOKE_FUERA_DE_CONSUMO` no está a
`true` (valor por defecto: `false`), ENTONCES no se debe emitir ningún `REVOKE`.
El pipeline nocturno no empieza a revocar permisos por un cambio de default: el
humano lo activa cuando ha verificado que nada más leía de ahí.

**R33 (Comportamiento no deseado).** SI se generan `REVOKE`, ENTONCES el
generador **nunca** debe emitirlos sobre `public`, `pg_catalog`,
`information_schema` ni `pg_toast`, y solo debe operar sobre esquemas listados
por `list_schemas()` de la conexión activa. La frontera con `albaranes` y
`partes` es la propia base: PostgreSQL no cruza bases y esta feature no la toca.

**R34 (Ubicuo).** Antes de activar R32 hay que verificar que **Power BI no lee
de `stg` ni de `raw`**, porque hoy `mcp_sigrid_dm_ro` es el único rol de lectura
y lo usan los dos consumidores. Verificación `MANUAL (humano)`, con comando
exacto en `tasks.md`. **Encaje con F-034**: esta feature no crea el rol
`pbi_sigrid_dm_ro`; lo que hace es dejar la lista de consumo estrechada y el
mecanismo de `REVOKE` construido y probado, que es exactamente lo que F-034
necesitará para separar los dos roles sin volver a inventarlo. **Encaje con
F-032**: la limpieza de copias viejas del secreto `pg-mcp-sigrid-dm-ro` y de las
reglas de firewall del puesto sigue siendo de F-032; aquí no se retira ninguna.

---

## 7 · Bloque G · Conectividad

**R35 (Ubicuo).** `docs/runbook_postgres_azure.md` debe documentar el
procedimiento exacto para autorizar al MCP desplegado en el firewall de
`psql-albaranes-rs9k2`: obtener la **IP de salida estática** del entorno de
Container Apps del MCP y crear la regla con el nombre del entorno. El patrón ya
existe y es el del ETL (`caj-datamart-seg-dev` → `68.221.221.85`).

**R36 (Ubicuo).** La documentación debe decir explícitamente que **el entorno de
Container Apps del MCP se crea sin integración de red virtual**, porque es esa
decisión —y no otra— la que le da IP de salida estática, y que **perseguir la IP
del puesto no funciona** (D11: CGNAT la rota).

**R37 (Ubicuo).** La documentación debe advertir de que la regla se crea sobre
un **recurso de otro proyecto** (`rg-albaranes-dev`), que la ejecuta el humano
con autorización explícita, y que **no se debe depender de la regla que autoriza
a cualquier recurso de Azure** porque autoriza también a suscripciones ajenas
(`infra/README.md:172-174`).

**R38 (Ubicuo).** `azure-apps/datamart_seg_anual.md` debe actualizarse **en este
mismo trabajo** con: las tres tablas y la vista nuevas de `_meta` como superficie
expuesta, el estrechamiento del rol de lectura, y la corrección de la
descripción del MCP, que ese documento todavía llama «cliente de escritorio».
Es la regla de `CLAUDE.md`: el dueño del documento es el proyecto que describe.

---

## 8 · Bloque H · La batería de aceptación

**R39 (Ubicuo).** `00_global.yaml` debe declarar un bloque
`preguntas_aceptacion` con la batería de §9, cada pregunta con `id`, `pregunta`,
`objetos_esperados`, `respuesta_correcta` (qué debe contener la respuesta para
darse por buena, incluidas las advertencias que debe citar) y `estado`
(`respondible` | `parcial` | `bloqueada_por: F-0XX`).

**R40 (Ubicuo).** Cada ficha debe llevar `ejemplos_preguntas` con al menos una
pregunta de negocio real que ese objeto responda. Es lo que hacía el prototipo y
es lo que permite el enrutado pregunta → objeto.

**R41 (Dirigido por estado).** MIENTRAS F-036, F-037 y F-038 no estén
terminadas, las preguntas marcadas `bloqueada_por` **no forman parte del
criterio de cierre de F-006**, y el diccionario debe decir explícitamente que el
datamart **no tiene** ese dato, de modo que un agente conteste «no puedo
responderlo con esta base» en vez de fabricar una cifra. Un «no sé» correcto es
una respuesta correcta.

---

## 9 · La batería de preguntas de negocio

**Cómo se usa.** No es un test automático: es una comprobación manual que el
humano (o un agente conectado al MCP) ejecuta contra el diccionario publicado.
Una pregunta se da por superada si la respuesta usa los objetos esperados **y**
cita las advertencias que la pregunta exige.

### 9.1 · Los seis casos del humano

| id | Pregunta | Objetos esperados | Qué se considera correcto | Estado |
|---|---|---|---|---|
| **P1** | ¿Qué proveedores nos han facturado más? | `compras.v_pbi_proveedor_obra`; `compras.fact_compras_linea` para grano mensual | Importes **sin IVA**; los abonos ya restan (`R-ABONO-NEGATIVO`); **no se pierden** las filas con `obra_id IS NULL` (estructura y generales); si agrega por línea, usa `(tipo_doc, linea_id)` | respondible |
| **P2** | ¿Qué retenciones tengo de los proveedores de la obra X? | `retenciones.movimientos` con `sentido='PROVEEDOR'` | Usa `saldo_vivo` por defecto y menciona la otra lectura (`neto_practicado`); no une a las líneas de la factura (`R-RETENCION-NO-JOIN-LINEAS`); señala las filas con `obra_id` nulo y `num_obras_documento > 1` | respondible (la vista cruzada obra×proveedor llega con F-039) |
| **P3** | ¿Quién fue el proveedor de fontanería de la obra X? | hoy: `compras.contratos.descripcion` con `LIKE` | La respuesta correcta **declara que es una heurística sobre texto libre** y que el datamart no tiene taxonomía de oficio | **parcial — bloqueada_por: F-036** |
| **P4** | ¿Cuál es el flujo de caja de la obra X? | — | La respuesta correcta es **«el datamart no tiene tesorería»**, no un número. Cero objetos de tesorería en los nueve esquemas | **bloqueada_por: F-037** |
| **P5** | De la obra X: lo facturado por contrato, lo que hay en albarán sin facturar y los comparativos | `compras.v_pbi_contrato_consumo`, `compras.v_pbi_albaranes_sin_facturar` | Contrato y albarán se responden; solo ALBARAN y PROFORMA cuentan como pendientes y la sobrefacturación conserva signo negativo. **El comparativo no existe** como objeto y hay que decirlo | **parcial — bloqueada_por: F-038** |
| **P6** | ¿Cuál es la planificación mensual de la obra X? | `mart.fact_seguimiento_mensual`, `mart.v_master_versiones_tipadas` | Va a `mart`, **no a `stg.plan_mensual`** (`R-VERSION-MASTER`); usa `importe_mes` y no suma `importe_origen` (`R-IMPORTE-MES`); menciona que las versiones de «Cierre mensual» no reemplazan al plan | respondible |

### 9.2 · Doce preguntas más, que el diccionario debería permitir inventar

| id | Pregunta | Objetos esperados | Qué se considera correcto | Estado |
|---|---|---|---|---|
| **P7** | ¿Cuánto llevamos ejecutado en la obra X a cierre del mes M, en venta y en coste? | `cierre.v_pbi_cierre_resumen`, `cierre.v_pbi_cierre_cabecera` | **Cita la fecha de build** porque `cierre` es `refresco: manual` (`R-FRESCURA-MANUAL`); los % van contra la VENTA de esa misma columna y ese mismo mes | respondible |
| **P8** | ¿Qué obras se desvían más de su master vigente en coste directo? | `mart.fact_seguimiento_categoria`, `mart.v_master_vigente_anual` | Separa escenario Coste/Venta y Real/Planificado; no mezcla ámbitos | respondible |
| **P9** | ¿Cuántas obras activas tenemos? | `maestro.obras.es_activa` | **Declara qué universo usa** (`R-UNIVERSO-OBRA`) y **no usa `stg.obras.activa`**, que está cableado a `TRUE` (`R-OBRA-ACTIVA`) | respondible — es una **pregunta trampa** deliberada |
| **P10** | ¿Cuál es el presupuesto de la obra X? | `stg.presupuesto` (o su equivalente en `mart`) | Usa el importe **total sin distribución mensual**, no la suma de `plan_mensual`; `importe` para coste (amb 3, 8) e `importe_oficial` para venta (amb 7, 11) | respondible — **pregunta trampa** |
| **P11** | Dame la evolución mensual del coste directo de la obra X en el año A | `mart.fact_seguimiento_mensual` | Usa `importe_mes`; **no** suma `importe_origen` (multiplicaría ~9x) | respondible — **pregunta trampa** |
| **P12** | ¿Qué tenemos en albaranes sin facturar? | `compras.v_pbi_albaranes_sin_facturar` | Solo ALBARAN y PROFORMA; las NOTA suman en consumido pero no en pendiente | respondible |
| **P13** | ¿Qué retenciones vencen este trimestre y siguen vivas? | `retenciones.v_pbi_retenciones_vencidas`, `v_pbi_retenciones_vivas` | Cita frescura (`refresco: manual`) | respondible |
| **P14** | ¿Cuáles son las diez partidas con más coste incurrido de la obra X? | `compras.v_pbi_partida_coste` | Advierte de que `compras` **no filtra por `stg.obras`** y puede traer obras administrativas; el puente plan vs incurrido por `partida_id` **no existe todavía** | parcial — el puente es **F-039** |
| **P15** | ¿De cuándo es el dato que me estás dando? | `_meta.v_frescura`, `_meta.v_diccionario`, `_meta.diccionario_publicacion` | Devuelve último OK y último intento **por separado**, y la versión del diccionario publicado. **Es la prueba de aceptación de R15 y R16** | respondible |
| **P16** | ¿Cuánto le hemos comprado al proveedor P en toda la empresa este año? | `compras.fact_compras_linea` | Filtra `tipo_doc` (`R-COMPRAS-TIPO-DOC`); no trata `linea_id` como único; no compara contra `maestro.proveedores_obra.importe_contratado`, que lleva IVA (`R-COMPRAS-SIN-IVA`) | respondible — **pregunta trampa** |
| **P17** | ¿Quiénes son nuestros diez mayores clientes? | — | La respuesta correcta es **«la tabla `cli` no se ingiere; solo conocemos el nombre vía `con.res`»** | **bloqueada_por: F-040** |
| **P18** | ¿Qué obras están mal configuradas, sin planificado en algún mes? | `mart.v_master_versiones_tipadas`, `mart.fact_seguimiento_mensual` | Reconoce el síntoma: obras con solo versiones de «Cierre mensual»; y que un mes sin fila de la versión vigente da importes 0 sin dejar de ser la vigente | respondible |

**Recuento honesto de lo que F-006 puede cerrar:** de 18 preguntas, **13
respondibles**, **3 parciales** (P3, P5, P14) y **2 imposibles** (P4, P17). Las
cinco no cerradas dependen de F-036, F-037, F-038, F-039 y F-040, que ya están
dadas de alta. **Esto acota el criterio de éxito de F-006: el diccionario está
completo cuando las 13 se responden bien y las 5 restantes se contestan con un
«no puedo, y este es el motivo» correcto** (R41).

---

## 10 · Decisiones que debe tomar el humano

| id | Decisión | Opciones | Recomendación |
|---|---|---|---|
| **DA-1** | ¿El diccionario se publica también cuando corren los comandos manuales (`build-cierre`, `build-compras`, `build-maestros`, `build-retenciones`)? | (A) solo en `run-all` y por comando suelto; (B) también al final de cada build manual | **A**. El diccionario no depende de los datos; publicarlo cinco veces no añade nada y sí superficie de fallo |
| **DA-2** | ¿`raw` se documenta a nivel de columna? | (A) solo objeto; (B) objeto + columna | **A**. Son 31 tablas y ~800 columnas de Sigrid, `raw` sale de la lista de consumo (R30) y su diccionario real es `azure-apps/sigrid_tablas.md`. La ficha de `raw` apunta ahí |
| **DA-3** | ¿Cuándo se activa `PG_REVOKE_FUERA_DE_CONSUMO=true`? | (A) en esta feature, tras verificar Power BI; (B) se deja construido y lo activa F-034 | **A**, y solo si la verificación de R34 sale limpia. Si sale sucia, **B** y se anota como entrega de F-006 a F-034 |
| **DA-4** | ¿La batería de aceptación se ejecuta contra el MCP local (stdio, prototipo) o se espera al MCP en cloud? | (A) contra el prototipo local apuntado a Azure; (B) esperar | **A**. Esperar al despliegue convierte el criterio de éxito de esta feature en rehén de otro repositorio |
| **DA-5** | ¿Se versiona el diccionario con número propio (`version: 1`) o con el hash? | (A) número manual + hash; (B) solo hash | **A**. El hash detecta el cambio; el número lo comunica |
| **DA-6** | ¿La ficha de un objeto incluye recuentos de filas u órdenes de magnitud por objeto? | (A) solo en las reglas globales (R10); (B) también por objeto | **A**. Por objeto envejece mal y nadie lo actualiza; el orden de magnitud global sí es estable |

---

## 11 · Riesgos declarados

1. **Volumen.** 31 tablas `raw` + 18 tablas derivadas + 33 vistas + 12
   funciones. Aunque `raw` vaya a nivel de objeto (DA-2), quedan ~50 fichas con
   columnas descritas una a una. **Es la mayor parte del coste de esta feature**
   y por eso las tareas van por bloques entregables (`tasks.md`).
2. **Desincronización.** Un diccionario que miente es peor que no tenerlo: el
   agente escribe SQL con aplomo sobre una descripción caducada. R24–R28 son
   toda la defensa que hay, y la offline es heurística (R29). El día que alguien
   añada una vista y la puerta no la vea, el trinquete falla en silencio.
3. **Alcance honesto.** Sin F-036/F-037/F-038 hay casos de uso que seguirán sin
   respuesta (§9). Si el criterio de cierre de F-006 se lee como «responde los
   seis casos del humano», la feature **no puede cerrar**. Se cierra con R41: 13
   bien respondidas y 5 bien rechazadas.
4. **El REVOKE.** Es la parte peligrosa. Corre contra un servidor compartido con
   dos aplicaciones en producción, y un `REVOKE` mal dirigido deja a Power BI sin
   datos sin que salte ninguna alerta (los informes simplemente dejan de
   refrescar). Mitigado por el default `false` (R32), la lista blanca de
   esquemas del sistema (R33) y la verificación manual previa (R34). **No se
   ejecuta sin firma del humano.**
5. **Este repositorio no controla al consumidor.** Todo esto solo sirve si el
   servidor MCP lee `_meta.diccionario` en vez de su YAML local. Esa mitad del
   contrato vive en `mcp-bbdd` y esta spec no puede garantizarla: lo único que
   puede hacer es dejar el contrato de `_meta` fijado y documentado (`design.md`
   §4) para que el otro repositorio lo implemente contra algo estable.
6. **Dependencias vecinas sin resolver.** **F-030** (las reglas de negocio como
   prompt, con su circuito de vuelta) y **D8** (dónde se persiste una
   planificación hecha por la IA) siguen abiertas. El diccionario describe **lo
   que el dato es**; F-030 describe **cómo se decide con él**. Son cosas
   distintas y esta spec no resuelve la segunda.


---

## 12 · Decisiones resueltas (humano, 2026-08-20)

Las seis decisiones de la seccion 10 estan cerradas. Todas se resolvieron con
la recomendacion de la spec.

| id | Resolucion |
|---|---|
| **DA-1** | **A.** El diccionario se publica en `run-all` y por comando suelto. No se republica al final de cada build manual: no depende de los datos. |
| **DA-2** | **A.** `raw` se documenta a nivel de objeto, no de columna. La ficha de cada tabla de `raw` remite a `azure-apps/sigrid_tablas.md`, que es su diccionario real. |
| **DA-3** | **A.** Los `REVOKE` se construyen Y se activan dentro de F-006, **pero solo despues de verificar (R34) que Power BI no depende de los esquemas que se retiran**. Si esa verificacion sale sucia, se cae a la opcion B: quedan construidos y apagados, y se entregan a F-034 como dependencia explicita. |
| **DA-4** | **A.** La bateria de aceptacion se ejecuta contra el **prototipo local apuntado a la base de Azure**, leyendo el diccionario nuevo. Motivo: no dejar el criterio de exito de esta feature como rehen del repositorio `mcp-bbdd`. Implica abrir la regla de firewall del puesto en cada tanda (D11, CGNAT). |
| **DA-5** | **A.** Version manual (`version: N`) mas hash. El hash detecta el cambio; el numero lo comunica. |
| **DA-6** | **A.** Nada de recuentos de filas por objeto: envejecen mal y nadie los actualiza. Los ordenes de magnitud van solo en las reglas globales (R10). |

Ademas, en la misma sesion:

- Se anadio **`"rigor": "critico"`** explicito a la ficha de F-006, como pedia
  la cabecera de este documento. Ya no depende de la omision.
- Se confirmaron las prioridades **2 a 6 para F-036..F-040**, por delante de
  F-035 y F-025. Motivo dado por el humano: el conocimiento de negocio va
  primero. Esto acota que puede cerrar F-006 y que queda para esas fichas.
- Orden de trabajo aprobado: **empezar por los bloques A-D** (andamiaje, reglas
  duras, fichas de `mart` y de `cierre`).


---

## 13 · Autorizaciones del humano (2026-08-21)

Cuatro decisiones tomadas al abrir la fase que toca la base real.

| Asunto | Resolucion |
|---|---|
| **Escritura en `sigrid_dm` (T19)** | **AUTORIZADA y acotada a esta accion**: crear las tres tablas y la vista del contrato en el esquema `_meta`, y publicar el diccionario. No alcanza a ningun otro esquema ni a ningun dato de negocio. |
| **Firewall del puesto** | Lo actualiza el agente, **reescribiendo la regla unica `datamart-puesto-pgris`** con la IP del momento antes de cada tanda. No se crean reglas nuevas: D11 ya dejo cuatro fechadas e inutiles. |
| **DA-3 · los `REVOKE`** | **Cae a la opcion B.** El mecanismo queda construido y probado, y **se entrega APAGADO a F-034**, que lo activara cuando Power BI tenga su propio rol. Motivo: hoy `mcp_sigrid_dm_ro` es el unico rol de lectura y lo comparten el MCP y Power BI; retirar un esquema sin saber cual consume romperia los informes. **Consecuencia de alcance: F-006 NO cierra el bloque I**; lo entrega. El MCP seguira viendo `raw` y `stg` hasta que F-034 lo separe. |
| **DA-4 · la bateria** | Se ejecuta contra el prototipo local **haciendo que lea el diccionario de `_meta`**, no de su YAML. Implica un cambio minimo en `mcp-bbdd` -que no tiene git ni arnes todavia-, y a cambio prueba el contrato de verdad, que es lo que ese repositorio tendra que implementar igualmente. |

### Lo que esto cambia en el cierre de F-006

- El bloque I deja de ser condicion de cierre y pasa a ser **entrega documentada a F-034**.
- Los bloques H, J, K y T19 siguen dentro, y ya tienen via libre.
- La bateria mide lo unico que hoy vale cero: que un agente encuentre la ficha,
  reciba las trece reglas y responda. Sin eso, F-006 no puede declararse hecha.
