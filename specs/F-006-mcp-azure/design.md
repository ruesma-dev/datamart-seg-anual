<!-- specs/F-006-mcp-azure/design.md -->
# F-006 · El diccionario semántico del datamart — Diseño (resumen)

> **El diseño íntegro vive en [`design_detalle.md`](design_detalle.md)**: los
> esquemas SQL completos, los contratos literales, las firmas de clases y los
> razonamientos largos están allí y solo allí. Este fichero es el **mapa de
> entrada**: qué se decidió, dónde toca, y qué se dejó fuera. Cada sección cita
> el título de su sección homóloga en el anexo para poder localizarla.

## 1 · La arquitectura, en corto

El datamart se explica solo. El significado de cada objeto y columna —grano,
claves de negocio, relaciones, trampas, régimen de refresco— se escribe como
**YAML versionado** en `config/diccionario/`, un fichero por esquema. Un
**validador de dominio puro** lo comprueba sin red ni BBDD; un **paso del ETL lo
publica dentro de la propia base**, en tres tablas de `_meta` más una vista. El
MCP no necesita conocer este repositorio: lee semántica **por SQL**, igual que
lee datos, y por eso el multi-base sale gratis. Una **puerta de cobertura** en
cada `bash harness/init.sh` impide que el modelo crezca y el conocimiento se
quede atrás. Y se construye el mecanismo de **`REVOKE`** que hoy no existe, para
estrechar el rol de lectura fuera de `raw` y `stg`.

No añade una sola columna al modelo de datos: es **metadato sobre lo que ya hay**.

### Encaje hexagonal (anexo §2)

| Pieza | Capa |
|---|---|
| Entidades, validador, derivación de avisos, informe de cobertura | **domain** |
| Extracción del inventario desde textos SQL y del YAML de tablas | **domain** |
| Carga de los YAML y hash SHA-256 | **infrastructure** |
| SQL de publicación y de grants/revokes (`psycopg.sql`, patrón `grants.py`) | **infrastructure** |
| `PublicarDiccionarioStep` (carga → valida → publica → registra) | **application** |
| Comandos CLI y composición del pipeline | **main.py** |

El `Orchestrator` no cambia; `domain/` sigue sin un import de infraestructura.

### Los dos contratos (anexo §3 y §4)

- **CONTRATO 1 · el YAML** (anexo §3.1–§3.4, incluye el ejemplo de ficha
  completa y la tabla de reglas del formato). Un fichero por esquema más
  `00_global.yaml`; orden de carga alfabético, que es el que entra en el hash.
- **CONTRATO 2 · la publicación en `_meta`** (anexo §4.1 «Las tres tablas y la
  vista», §4.2 «La vista de consumo», §4.4 `diccionario_contexto`). Es la mitad
  del contrato con `mcp-bbdd` y lo único que este repositorio puede garantizarle:
  `_meta.diccionario`, `_meta.diccionario_reglas`,
  `_meta.diccionario_publicacion`, `_meta.diccionario_contexto` y
  `_meta.v_diccionario` como punto de entrada único.

### El pipeline (anexo §9)

```
IngestRaw -> LoadExcelAux -> BuildStg -> BuildMart -> PublicarDiccionario -> ApplyGrants
```

## 2 · Decisiones de diseño

### 2.1 · Decisiones abiertas cerradas (DA-1 a DA-6)

| # | Qué se decidió | Porqué |
|---|---|---|
| **DA-1** | Se publica en `run-all` y por comando suelto; **no** al final de cada build manual | No depende de los datos; publicar cinco veces es superficie de fallo |
| **DA-2** | `raw` se documenta **a nivel de objeto**, no de columna | 31 tablas y ~800 columnas; su diccionario real es `azure-apps/sigrid_tablas.md` |
| **DA-3** | Los `REVOKE` se construyen y se activan aquí **solo si la verificación R34 sale limpia**; si no, caen a F-034 | Power BI comparte hoy el rol de lectura |
| **DA-4** | La batería de aceptación corre contra el **prototipo local apuntado a Azure**, leyendo el diccionario de `_meta` | No dejar el éxito de F-006 rehén de otro repositorio |
| **DA-5** | Versión manual (`version: N`) **más** hash | El hash detecta el cambio; el número lo comunica |
| **DA-6** | Nada de recuentos de filas por objeto; órdenes de magnitud solo globales (R10) | Por objeto envejece mal y nadie lo actualiza |

### 2.2 · Decisiones estructurales del diseño

| Decisión | Qué se decidió | Porqué |
|---|---|---|
| **`ficha JSONB` y no modelo normalizado** (§4.1) | Columnas, relaciones y ejemplos viajan en un JSONB; `n_columnas` sí sale a columna | El MCP solo lista o describe: un JOIN de más no gana ninguna consulta real |
| **Publicación singleton** (§4.1) | `diccionario_publicacion` con `CHECK (id = 1)` | Imposible que queden dos versiones publicadas |
| **`hash_fuente`** (R22) | SHA-256 de los YAML concatenados en orden alfabético | «¿lees el diccionario del repositorio?» se responde sin salir de SQL |
| **Crecer por el final** (§4.2, §4.3) | `motivo_no_consumo` se añadió como **columna 19, la última**, de `v_diccionario` | Insertarla en su sitio natural correría de posición a 13 columnas ya publicadas |
| **Los dos `LEFT JOIN`** (§4.2, R15) | `v_frescura` y `diccionario_publicacion` con `LEFT JOIN ... ON TRUE` | Un `CROSS JOIN` con la tabla vacía devolvería cero filas: la vista mentiría |
| **`diccionario_contexto` crece por FILAS** (§4.4) | Bloques `convenciones`, `ordenes_de_magnitud`, `ejes`, `esquemas`, `ocultar`; nunca columnas nuevas | El contrato tiene que crecer sin romper; recrear vista exige `DROP` y se lleva los `GRANT` |
| **`texto` se renderiza en origen** (§4.4) | La entrada redactada se genera aquí, no en cada consumidor | Si cada uno compone el suyo, divergen (ya pasó) |
| **Qué viaja y qué no** (§4.4) | `CONTEXTO_PUBLICADO` / `CONTEXTO_NO_PUBLICADO` en `domain/diccionario.py`, con test que exige que toda clave esté en una de las dos | Tres veces se quedó sin viajar algo importante y las tres se vieron por casualidad |
| **`ocultar` es lista de COLUMNAS** (§4.4) | Una fila por columna, la columna **como `clave`**; requiere un gancho de columna en `mcp-bbdd` | Compararla contra el gancho de tabla de hoy no oculta nada |
| **Nunca `DROP` de las tablas del diccionario** (§9.3) | DDL `CREATE TABLE IF NOT EXISTS`; reemplazo por `DELETE` + `INSERT` en una transacción (R18) | Un `DROP` se lleva los `GRANT` y deja al MCP ciego hasta el `apply-grants` siguiente |
| **Publicar ANTES de `apply-grants`** (§9.1, R20) | El paso va entre `build_mart` y `apply_grants` | El `GRANT ... ON ALL TABLES IN SCHEMA _meta` es una foto del instante: así las alcanza siempre |
| **Fallar sin abrir escritura** (§9.2, R19) | Si el YAML no valida, `FAILED` antes de la transacción; queda publicado el anterior íntegro | Un diccionario a medias deja al MCP inventando significados |
| **Puerta doble** (§10) | Offline heurística en `init.sh` (R24–R27) + `check-diccionario` contra la base real (R28) | La barata corre siempre; la cara dice la verdad |
| **Cobertura 100 %, no porcentual** (§10, R25/R26) | 100 % de objetos y columnas **dentro de la superficie de consumo**; fuera, aviso | Un 95 % permite que la que falte sea la importante, y nadie audita cuál es el 5 % |
| **Antídoto a la trampa** (R3) | `consumo_recomendado: false` exige `motivo_no_consumo` escrito | Si no, se esquiva la puerta bajando la bandera |
| **Trinquete de `pendientes`** (R27) | Los objetos sin ficha se declaran y la puerta los tolera; la lista **solo baja** y debe quedar vacía al cerrar | Permite entregar por bloques sin abrir un agujero permanente |
| **La puerta contrasta contra el SQL** (enmienda §10) | `agregacion` vs. la función que envuelve la columna; `clave_negocio` vs. `GROUP BY` y PK; `grano` vs. su propia clave | Lo no derivable se traslada a T26 como consulta de unicidad contra la base real |
| **`pasos_nocturnos` se inyecta** (§8.1) | R14 lee la lista de `build_pipeline_steps`, no de una copia a mano | Una lista copiada se desincroniza el día que el pipeline cambie |
| **El validador devuelve TODOS los errores** (§8.1) | No para en el primero | Con más de ochenta fichas, parar al primero son ochenta vueltas |
| **JSONB con `sort_keys=True`** (§8.4) | Serialización estable de la ficha | Dos publicaciones del mismo YAML dan el mismo texto y el `diff` es legible |
| **El generador de `REVOKE` sigue siendo puro** (§11.2) | `build_readonly_grant_statements(..., revocar_en=())`, identificadores citados | Comprobable sin BBDD, como hoy |
| **Orden de los `REVOKE`** (§11.2) | 1) `ALTER DEFAULT PRIVILEGES ... REVOKE SELECT ON TABLES`, 2) `REVOKE ALL ON ALL TABLES`, 3) `REVOKE USAGE ON SCHEMA` | Al revés, lo creado entre ambas sentencias quedaría concedido |
| **Lista blanca de esquemas del sistema** (§11.2, R33) | `revocar_en = list_schemas() − consumo − {public, pg_catalog, information_schema, pg_toast}` | Solo esquemas que existen en la conexión activa |
| **`REVOKE` apagado por defecto** (§11.3, R32) | `PG_REVOKE_FUERA_DE_CONSUMO=false`; rollback = una variable + `apply-grants` | Power BI usa hoy el mismo rol y su fallo es silencioso |
| **DDL en fichero propio** (§7) | `sql/ddl/01_diccionario.sql`, no dentro de `00_meta.sql` | `00_meta.sql` corre en la primera conexión de **cada** proceso |
| **Entorno del MCP sin VNet** (§12) | Se repite el patrón del ETL: entorno sin integración de red virtual → IP de salida estática → regla de firewall con el nombre del entorno | Es esa decisión, y no otra, la que da IP estática |

### 2.3 · Enmiendas registradas

| Fecha | Qué cambió |
|---|---|
| 2026-08-20 (review A–D) | El ejemplo de ficha usaba columnas y literales inexistentes; corregido contra el SQL real. Recuentos: **98** objetos (102 tras el DDL) |
| 2026-08-20 (3.ª review) | `v_diccionario` proyecta **19** columnas: entra `motivo_no_consumo`, la última |
| 2026-08-20 (4.ª review) | La puerta offline pasa a contrastar contra el SQL (agregación, clave, grano) |
| 2026-08-22 | Entra `_meta.diccionario_contexto`: el bloque global se perdía al leer de base. Inventario a **103** objetos |

## 3 · Componentes y ficheros que toca

### 3.1 · Se crean (anexo §5)

| Grupo | Contenido |
|---|---|
| `config/diccionario/*.yaml` | `00_global.yaml` + un fichero por esquema: `_meta` (7), `raw` (31, a nivel de objeto), `stg` (~11), `aux` (1), `mart` (13), `cierre` (12), `compras` (~14), `maestro` (~4), `retenciones` (~9). **Es el grueso del trabajo** |
| `etl_sigrid/domain/diccionario.py` | `Columna`, `Relacion`, `Ficha`, `Regla`, `Diccionario`, `ErrorValidacion`; `validar`, `derivar_avisos`, `formatear_errores` (anexo §8.1) |
| `etl_sigrid/domain/inventario.py` | `ObjetoPublicado`, `InformeCobertura`; `objetos_de_sql`, `objetos_de_raw`, `evaluar_cobertura`, `formatear_cobertura` (anexo §8.2) |
| `etl_sigrid/infrastructure/diccionario/cargador_yaml.py` | `cargar_diccionario(dir) -> (Diccionario, hash)` (anexo §8.3) |
| `etl_sigrid/infrastructure/postgres/diccionario_sql.py` | Constantes SQL y `filas_*` puras para `executemany` (anexo §8.4) |
| `etl_sigrid/infrastructure/postgres/sql/ddl/01_diccionario.sql` | El DDL del contrato 2 (anexo §4.1) |
| `etl_sigrid/application/steps/publicar_diccionario_step.py` | `PublicarDiccionarioStep` (anexo §8.5) |
| `tests/test_f006_*.py` | `formato`, `reglas`, `frescura`, `publicacion`, `cobertura` (la puerta, sobre el diccionario real), `grants`, `docs` |

### 3.2 · Se modifican (anexo §6)

| Fichero | Qué cambia |
|---|---|
| `config/settings.py` | `DEFAULT_CONSUMPTION_SCHEMAS` sin `raw` ni `stg`; `revoke_fuera_de_consumo`; `diccionario_dir` |
| `infrastructure/postgres/grants.py` | Parámetro `revocar_en`; emite el trío de `REVOKE`. Sigue puro |
| `infrastructure/postgres/postgres_client.py` | `apply_readonly_grants(revocar=False)`, `publicar_diccionario(...)`, `list_objetos_catalogo(...)` |
| `application/steps/apply_grants_step.py` | Pasa `revocar` y lo deja en `result.metadata["revocado"]` |
| `main.py` | Inserta el paso en `build_pipeline_steps`; comandos `publicar-diccionario` y `check-diccionario` |
| `infra/sql/02_roles.sql` | El bucle de esquemas pasa a los siete de consumo |
| `docs/ARCHITECTURE.md`, `docs/CONVENTIONS.md` | Sección nueva; regla: quien cambia un objeto publicado actualiza su ficha en el mismo trabajo |
| `docs/runbook_postgres_azure.md`, `infra/README.md` | Firewall del entorno del MCP y activación/rollback del `REVOKE` |
| `azure-apps/datamart_seg_anual.md` | R38, en este mismo trabajo: qué exponemos y el rol estrechado |
| `harness/features.json` | F-006 pasa a `"rigor": "critico"` |

### 3.3 · No se tocan (anexo §7)

Todo el **SQL de negocio** (`sql/stg|mart|cierre|compras|maestro|retenciones|auxiliar`):
esta feature no cambia una fila del modelo, y escribir las fichas obliga a leer
las 33 vistas, así que **los errores que aparezcan se anotan y van a su feature**.
Tampoco: `ddl/00_meta.sql`, `application/orchestrator.py`, `domain/coherencia.py`,
`domain/ejecucion.py`, `domain/tramos.py`, `config/tables_sigrid.yaml` (se lee,
no se modifica), `config/business_rules.yaml` y el repositorio `mcp-bbdd` entero.

## 4 · Lo que se apartó

### 4.1 · Alternativas descartadas (anexo §14.1)

| Alternativa | Por qué se descarta |
|---|---|
| Dejar el diccionario en `mcp-bbdd` (como hoy) | Lo mantendría quien no conoce el modelo, y ese repositorio no sabe qué objetos publica el datamart: no habría puerta posible |
| Publicarlo por HTTP o por fichero compartido | Segunda fuente además de la conexión SQL, y rompe el multi-base |
| Generarlo desde `pg_catalog` | Da nombres y tipos, que es lo que el MCP ya obtiene solo; el significado no está en ningún catálogo |
| Un único YAML monolítico | 34 fichas ya son 1.083 líneas en el prototipo; aquí hay ~103 objetos |
| Modelo normalizado con tabla de columnas | Un JOIN más y dos esquemas que mantener, sin ganar consultas reales |
| Umbral porcentual (95 %) | Permite que la columna que falte sea la importante |
| Atomicidad por `DROP TABLE` + `CREATE` | Se lleva los `GRANT` y deja al MCP ciego |
| Revocar por defecto | Power BI usa hoy el mismo rol |
| Resolver aquí F-036 a F-040 | Son features propias; convertirían una feature de metadato en un cambio del modelo |

### 4.2 · Fuera de alcance, con dueño (anexo §13)

| Qué | Dónde vive |
|---|---|
| Transporte HTTP, Entra, grupos, multi-base, auditoría y despliegue del MCP | `mcp-bbdd` |
| El segundo rol de lectura (`pbi_sigrid_dm_ro`) y separar Power BI | **F-034**. F-006 le entrega la lista estrechada y el mecanismo de `REVOKE` construido y probado |
| Retirar secretos viejos y las reglas de firewall del puesto | **F-032**. Aquí solo se **añade** la regla del entorno del MCP |
| Reglas de negocio como procedimiento en lenguaje natural | **F-030**, dueño en Negocio. La línea: *el diccionario describe lo que el dato ES; F-030, cómo se DECIDE con él* |
| Ingerir tablas nuevas de Sigrid | **F-036 a F-040** |
| Dónde se persiste una planificación hecha por la IA | **D8**, sin decidir. El MCP es de solo lectura por diseño y no se relaja |

### 4.3 · Riesgos asumidos (anexo §14.2)

1. **Volumen** — ~50 fichas con columnas una a una más 31 de `raw`. Mitigación:
   entrega por bloques con el trinquete de `pendientes`.
2. **Desincronización** — un diccionario que miente es peor que no tenerlo.
   Mitigación: puerta doble y regla nueva de convenciones. **Residual**: la
   puerta offline es heurística y puede fallar en silencio hasta el
   `check-diccionario` siguiente.
3. **Alcance honesto** — sin F-036/037/038 quedan casos sin respuesta; F-006
   cierra con R41 (13 preguntas bien respondidas, 5 bien rechazadas), no con
   «responde los seis casos del humano».
4. **El `REVOKE`** — servidor compartido con dos aplicaciones en producción y
   fallo silencioso. **No se ejecuta sin firma del humano.**
5. **No controlamos al consumidor** — todo sirve solo si `mcp-bbdd` lee `_meta`
   en vez de su YAML. Aquí solo se puede fijar y documentar el contrato.
6. **Leer las 33 vistas destapará errores** — la disciplina es anotarlos, no
   arreglarlos aquí.
