<!-- specs/F-006-mcp-azure/requirements.md -->
# F-006 · El diccionario semántico del datamart — Requisitos (índice)

> **El detalle íntegro vive en [`requirements_detalle.md`](requirements_detalle.md)**:
> allí está la redacción completa de cada requisito (EARS), su justificación, sus
> criterios de aceptación, la batería de preguntas de negocio y los riesgos. Este
> fichero es solo el **índice navegable**: están los 41 requisitos, uno por línea,
> con su identificador exacto y su estado. Para la letra pequeña, salta al detalle.

**Rigor: `critico`** (ya explícito en `harness/features.json`).

## Objetivo

Que **el datamart sepa explicarse solo**. No basta con que los datos estén: deben
venir con su significado, su grano, sus relaciones, sus trampas y su fecha de
caducidad, en un formato que un agente lea **por SQL contra la propia base**, sin
conocer este repositorio. El diccionario vive como YAML versionado en
`config/diccionario/` y un paso del ETL lo publica en `_meta`. El usuario final es
de negocio, no técnico.

**Fuera de alcance:** el servidor MCP entero (transporte, Entra, multi-base,
despliegue) vive en el repositorio `mcp-bbdd`; F-030 y D8; la ingesta de datos
nuevos (F-036 oficios, F-037 tesorería, F-038 comparativos, F-039 vistas puente,
F-040 ingresos); F-034 (rol de Power BI) y F-032 (limpieza de secretos). Aquí se
produce **el dato que ese servidor consumirá** y **el permiso con el que lo hará**.

**Dato base:** el datamart tiene **nueve** esquemas (`_meta`, `raw`, `stg`, `aux`,
`mart`, `cierre`, `compras`, `maestro`, `retenciones`), no ocho.

## Índice de requisitos

### Bloque A · Formato del diccionario

| id | Qué exige | Estado |
|---|---|---|
| **R1** | Diccionario como YAML versionado en `config/diccionario/`: un fichero por esquema más `00_global.yaml`. Nada de monolito | vigente |
| **R2** | Campos mínimos de cada ficha (`tipo`, `capa`, `consumo_recomendado`, `descripcion`, `grano`, `clave_negocio`, `paso_etl`, `refresco`, `columnas`, `relaciones`, `ejemplos_preguntas`); formato exacto en `design.md` §3, es contrato | vigente |
| **R3** | SI `consumo_recomendado: false`, el validador exige `motivo_no_consumo` no vacío. Antídoto contra esquivar R26 | vigente |
| **R4** | Cobertura de los **nueve** esquemas, cada uno con entrada propia en `00_global.yaml` | vigente |
| **R5** | Relación que apunta a un `esquema.objeto.columna` inexistente ⇒ el validador falla nombrando ficha, relación y destino | vigente |
| **R6** | Toda columna documentada lleva `significado` de negocio; se admite la forma abreviada `columna: "<significado>"` | vigente |
| **R7** | `agregacion` con vocabulario cerrado (`suma`, `promedio`, `no_sumable`, `suma_solo_dentro_del_mes`, `ultimo_valor`, `clave_sustituta`); cualquier otro valor falla | vigente |
| **R8** | El validador es **dominio puro**: sin red, sin BBDD, sin leer fuera de `config/diccionario/` | vigente |

### Bloque B · Las reglas duras

| id | Qué exige | Estado |
|---|---|---|
| **R9** | `00_global.yaml` declara un bloque `reglas` con **doce** reglas mínimas (`R-FRESCURA-MANUAL`, `R-IMPORTE-MES`, `R-UNIVERSO-OBRA`, `R-OBRA-ACTIVA`, `R-VERSION-MASTER`, `R-FAS-AMBIGUO`, `R-CLAVE-SUSTITUTA`, `R-ABONO-NEGATIVO`, `R-LINEA-ID-NO-UNICA`, `R-RETENCION-NO-JOIN-LINEAS`, `R-COMPRAS-SIN-IVA`, `R-COMPRAS-TIPO-DOC`), cada una con `codigo`, `titulo`, `severidad`, `ambito`, `regla` y `motivo` | vigente |
| **R10** | Las reglas incluyen **órdenes de magnitud de referencia** para detectar cifras absurdas | vigente |
| **R11** | Regla `bloqueante` cuyo `ambito` cita un objeto inexistente ⇒ el validador falla | vigente |
| **R12** | Al publicar, cada ficha recibe **automáticamente** los códigos de las reglas cuyo ámbito la incluye (derivación de dominio puro) | vigente |

### Bloque C · Frescura

| id | Qué exige | Estado |
|---|---|---|
| **R13** | Cada ficha declara `refresco` ∈ `nocturno\|manual\|estatico` y `paso_etl` (el nombre real de la columna `paso` de `_meta.v_frescura`) | vigente |
| **R14** | Ficha de `cierre`, `compras`, `maestro` o `retenciones` con `refresco: nocturno` ⇒ falla; el test lee la composición **real** del pipeline, no una lista copiada | vigente |
| **R15** | Vista `_meta.v_diccionario` que une objeto y frescura por `paso_etl` con **LEFT JOIN**: una sola consulta da significado y fecha de build | vigente |
| **R16** | Regla global: toda respuesta sobre objetos `refresco: manual` **cita su fecha de build**, y se dice con qué consulta se obtiene | vigente |

### Bloque D · Publicación en `_meta`

| id | Qué exige | Estado |
|---|---|---|
| **R17** | `python main.py publicar-diccionario` carga los YAML, valida y **reemplaza** `_meta.diccionario`, `_meta.diccionario_reglas` y `_meta.diccionario_publicacion` | vigente |
| **R18** | El reemplazo va en **una sola transacción** (`DELETE`+`INSERT`, nunca `DROP TABLE`): el lector ve el anterior completo o el nuevo completo | vigente |
| **R19** | Si no valida, falla **antes** de abrir la transacción, deja el anterior intacto y devuelve el informe con fichero y ficha culpables | vigente |
| **R20** | `publicar_diccionario` entra en `run-all` **después de `build_mart` y antes de `apply_grants`** (el orden no es cosmético) | vigente |
| **R21** | Fallo de publicación ⇒ `FAILED` y `run-all` con código 1, **sin deshacer el build de datos** | vigente |
| **R22** | `_meta.diccionario_publicacion` registra `version`, `hash_fuente` (SHA-256), `publicado_en` (UTC sin zona), `batch_id` y recuentos + % de cobertura | vigente |
| **R23** | Documentar que cambiar las columnas de `_meta.v_diccionario` exige `DROP VIEW` y por tanto `apply-grants` inmediato después | vigente |

### Bloque E · La puerta de cobertura

| id | Qué exige | Estado |
|---|---|---|
| **R24** | Puerta **offline** (pytest, sin red ni BBDD) que compara el diccionario con el inventario derivado del propio repo (`sql/**` + `config/tables_sigrid.yaml` para `raw`) | vigente |
| **R25** | Objeto inventariado sin ficha y sin declarar en `pendientes` ⇒ la puerta **falla** e `init.sh` queda en rojo. Umbral: **100 %, bloqueante** | vigente |
| **R26** | Columna sin `significado` en objeto `consumo_recomendado: true` ⇒ **falla**; fuera de la superficie de consumo es **aviso**. Umbral: 100 % dentro, 0 % exigido fuera | vigente |
| **R27** | La lista `pendientes` es un **trinquete**: solo puede bajar. **Al cerrar F-006 debe estar vacía** (criterio del reviewer) | vigente |
| **R28** | `python main.py check-diccionario` compara contra el catálogo **real** (`information_schema`) y sale con 1 ante cualquier discrepancia. Verificación `MANUAL (humano)` | vigente |
| **R29** | La puerta offline se declara **heurística** en su docstring (lee SQL con regex); por eso `raw` se inventaría desde el YAML y por eso existe R28 | vigente |

### Bloque F · El rol de lectura (bloque I)

| id | Qué exige | Estado |
|---|---|---|
| **R30** | `DEFAULT_CONSUMPTION_SCHEMAS` pasa a `_meta,mart,cierre,compras,maestro,retenciones,aux`, retirando `raw` y `stg` | **ENMENDADO (2026-08-27): NO se hizo.** `config/settings.py` sigue con los **nueve** esquemas. Se entrega a F-034 sin construir (ver R32) |
| **R31** | `build_readonly_grant_statements` debe poder emitir **`REVOKE`** sobre los esquemas fuera de la lista de consumo (hoy la función solo concede) | **ENMENDADO (2026-08-27): NO se construyó.** `grants.py` no tiene `revocar_en` ni nada equivalente: la función solo concede. Se entrega a F-034 **por construir** |
| **R32** | Sin `PG_REVOKE_FUERA_DE_CONSUMO=true` (default `false`) no se emite ningún `REVOKE` | **enmendado (2026-08-21, DA-3→B): queda APAGADO y se entrega a F-034**; el MCP seguirá viendo `raw` y `stg` |
| **R33** | Los `REVOKE` nunca sobre `public`, `pg_catalog`, `information_schema`, `pg_toast`, y solo sobre esquemas de `list_schemas()` | **ENMENDADO (2026-08-27): sin `REVOKE` que gobernar.** La regla sigue siendo válida y **la hereda F-034**, que es quien construirá el mecanismo |
| **R34** | Verificar `MANUAL (humano)` que Power BI no lee de `stg` ni de `raw` antes de activar | **aplazado con R32**: la activación es de F-034; F-032 conserva la limpieza de secretos |

> **Consecuencia de alcance (humano, 2026-08-21):** el **bloque I deja de ser
> condición de cierre de F-006** y pasa a ser entrega documentada a F-034.

### Bloque G · Conectividad

| id | Qué exige | Estado |
|---|---|---|
| **R35** | `docs/runbook_postgres_azure.md` documenta cómo autorizar al MCP en el firewall de `psql-albaranes-rs9k2` usando la IP de salida estática de su entorno de Container Apps | vigente |
| **R36** | La documentación dice que ese entorno se crea **sin integración de red virtual** (eso da la IP estática) y que perseguir la IP del puesto no funciona (D11, CGNAT) | vigente |
| **R37** | Advertir de que la regla se crea sobre un recurso de **otro proyecto** (`rg-albaranes-dev`), la ejecuta el humano, y no se depende de la regla que autoriza a cualquier recurso de Azure | vigente |
| **R38** | Actualizar `azure-apps/datamart_seg_anual.md` **en este mismo trabajo**: tablas y vista nuevas de `_meta`, estrechamiento del rol y corrección de la descripción del MCP | vigente |

### Bloque H · La batería de aceptación

| id | Qué exige | Estado |
|---|---|---|
| **R39** | `00_global.yaml` declara `preguntas_aceptacion` (P1–P18) con `id`, `pregunta`, `objetos_esperados`, `respuesta_correcta` y `estado` | vigente |
| **R40** | Cada ficha lleva `ejemplos_preguntas` con al menos una pregunta de negocio real (permite el enrutado pregunta → objeto) | vigente |
| **R41** | Las preguntas `bloqueada_por` **no** entran en el criterio de cierre; el diccionario dice explícitamente que el dato no existe, para que el agente conteste «no puedo» en vez de inventar | vigente |

**Criterio de éxito (R41).** De 18 preguntas: **13 respondibles**, **3 parciales**
(P3, P5, P14) y **2 imposibles** (P4, P17), dependientes de F-036 a F-040. F-006
cierra con las 13 bien respondidas y las 5 bien rechazadas. La batería se ejecuta
contra el **prototipo local leyendo el diccionario de `_meta`** (DA-4).

## Decisiones del humano (ya cerradas)

DA-1..DA-6 resueltas el 2026-08-20 con la recomendación de la spec (detalle §12),
y cuatro autorizaciones del 2026-08-21 (detalle §13): escritura en `sigrid_dm`
**acotada a crear las tres tablas y la vista de `_meta` y publicar**; firewall del
puesto reescribiendo la regla única `datamart-puesto-pgris`; **DA-3 cae a B**
(REVOKE apagado, entregado a F-034); DA-4 contra el prototipo local vía `_meta`.

**Riesgos declarados** (detalle §11): volumen (~50 fichas con columnas),
desincronización (la puerta offline es heurística), alcance honesto sin
F-036/037/038, el `REVOKE` sobre servidor compartido, y que la otra mitad del
contrato vive en `mcp-bbdd`.
