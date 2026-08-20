<!-- progress/current.md -->
# Estado actual

## F-006 · El diccionario semántico del datamart — `in_progress`

Rama `feature/F-006-mcp-azure`. **Bloques A–G completos**: tras seis pasadas de
review y un APROBADO sin matices, la última tanda documentó los 53 objetos que
faltaban (`maestro`, `stg`, `aux`, `_meta` y `raw`).

`bash harness/init.sh` en verde: **1487 tests**, cobertura de las líneas
cambiadas **99,0 %** (714 de 721).

**El diccionario está completo: 102 objetos, 793 columnas, 13 reglas duras y
`pendientes` VACÍA.** El trinquete llegó a **0**, así que no hay ningún objeto
que declarar como excepción.

- Informe de implementación: `progress/impl_F-006.md`
- Campaña de mutación: `progress/mutacion_F-006.md`
- Review que provocó las correcciones: `progress/review_F-006.md`

### Qué hay ya

**Bloque E entregado** (T15–T18): el contrato con `mcp-bbdd` está construido y
probado con las fichas reales, sin tocar la base. Tres tablas y
`_meta.v_diccionario` en `sql/ddl/01_diccionario.sql`, los constructores puros
de `diccionario_sql.py`, `PublicarDiccionarioStep` **entre `build_mart` y
`apply_grants`**, y el comando `python main.py publicar-diccionario`. El
reemplazo va en UNA transacción con `DELETE`+`INSERT` y sin un solo `DROP`.

**Bloques F y G completos** (T20–T25): `compras` (14), `retenciones` (10),
`maestro` (4), `stg` (10), `aux` (1), `_meta` (7) y `raw` (31, a nivel de objeto
según DA-2). La regla de oro de Sigrid se publica como `R-SIGRID-CON`, la
decimotercera regla: estaba escrita en una cabecera YAML, que es un comentario y
**no llega al MCP**.


- **Andamiaje** (bloque A): `etl_sigrid/domain/diccionario.py` (entidades y
  validador), `etl_sigrid/domain/inventario.py` (inventario y cobertura),
  `etl_sigrid/infrastructure/diccionario/cargador_yaml.py`, y la puerta de
  cobertura, que corre en cada `init.sh`.
- **Bloque global** (bloque B): las doce reglas duras, los órdenes de magnitud,
  las convenciones, los nueve esquemas y las 18 preguntas de la batería.
- **Fichas**: los **102 objetos** del datamart con **793 columnas**, todas
  contrastadas contra el SQL. La superficie de consumo son 47 de esos 102, con
  el **100 %** de sus columnas con significado; los otros 55 llevan
  `motivo_no_consumo` diciendo a dónde ir en su lugar.

El trinquete `pendientes` recorrió 98 → 96 → 85 → 73 → 77 → 53 → 49 → 39 → 38 →
31 → **0**, anclado al inventario y al historial de git: un objeto documentado
ya no puede volver, aunque el repositorio sí puede publicar cosas nuevas.

### Lo siguiente

El **bloque H**: `check-diccionario` (R28, T26), que es lo que sustituye la
heurística offline de hoy por un contraste contra `information_schema` de la
base real; y T27, el chequeo contra esa base, que es `MANUAL (humano)`. Solo
después los bloques 🔏 de permisos y firewall, que necesitan firma.

Sigue sin pasarse la **batería de 18 preguntas** (T39): que una ficha sea
correcta todavía no demuestra que sea *suficiente* para responder la pregunta a
la que apunta.

### Verificaciones `MANUAL (humano)` pendientes

Ninguna corresponde a los bloques A–D; se listan aquí porque el checkpoint C4 lo
pide y para que no se pierdan:

| Tarea | Qué hay que hacer |
|---|---|
| **T19** | `python main.py publicar-diccionario` contra la BBDD real y comprobar el contrato de `_meta` |
| **T27** | `python main.py check-diccionario` contra el catálogo real, con código de salida 0 |
| **T32** 🔏 | Verificar que Power BI no lee de `stg` ni de `raw` |
| **T33** 🔏 | Activar `PG_REVOKE_FUERA_DE_CONSUMO` y ejecutar `apply-grants` |
| **T34** 🔏 | Comprobar que Power BI sigue refrescando |
| **T37** | Actualizar `azure-apps/datamart_seg_anual.md` |
| **T38** 🔏 | Regla de firewall para la IP del entorno del MCP |
| **T39** | Ejecutar las 18 preguntas de la batería contra el diccionario publicado |

### Límite conocido de la puerta (escrito, no descubierto luego)

Tras la cuarta review, la puerta comprueba además la **coherencia interna entre
campos de la misma ficha**: el `grano` tiene que nombrar todas las columnas de su
`clave_negocio`. Nació de un patrón, no de un caso —tres veces se corrigió una
afirmación en un campo y sobrevivió en el de al lado—, y al implementarla
fallaron **28 de 41 fichas**. En la misma línea, el aviso de «congelado en el
build» se propaga por derivación: `CURRENT_DATE` en un `CREATE TABLE AS` congela
y en una vista no, y quien referencia una columna congelada lo hereda.

Tras la quinta review, el contraste de clave se estrechó: una columna del
`GROUP BY` **puede** omitirse de la clave si se resuelve por una sola fuente, y
**no puede** si sale de un `COALESCE` de dos, porque entonces nada garantiza que
acompañe siempre al mismo valor de clave. Lo que sigue fuera —la clave corta
cuya dependencia falla por otro motivo— lo cierra la consulta de unicidad de T26,
ya escrita en `tasks.md`.

La puerta **sí** contrasta contra el SQL `agregacion`
(la función que envuelve cada columna) y `clave_negocio` (contenida en el
`GROUP BY`, o igual a la PK del DDL). Lo que sigue **sin** ser derivable, y por
eso no se comprueba, es la dirección contraria de la clave: **«la clave es
demasiado corta»** exige saber si una columna del `GROUP BY` depende
funcionalmente de otra, y eso no se lee del texto: dos pares de columnas se
escriben igual y solo uno tiene dependencia funcional. (El ejemplo que circuló
en `progress/review_F-006.md` era erróneo en su primera mitad y está corregido
en los tests; queda anotado aquí para que no se vuelva a copiar.) Esa mitad, y la veracidad del `grano` y de cada `significado`, siguen en
revisión humana.


La puerta comprueba que las columnas de cada ficha sean exactamente las del SQL,
que las relaciones resuelvan y que las cardinalidades no prometan unicidad
falsa. **No comprueba que el `grano`, la `clave_negocio` ni el `significado` de
una columna sean CIERTOS**: un grano falso y una clave reducida pasan en verde,
verificado. Y hay un efecto de segundo orden: la detección de fan-out deriva la
unicidad de la clave declarada, así que **una clave reducida desarma esa
detección**. Hoy eso solo lo cazan la revisión humana y la batería de aceptación
(T39). Desglose completo en `progress/impl_F-006.md`, §«Qué comprueba la puerta
y qué NO».

### Avisos que no hay que perder

- **`AUX` es un nombre de dispositivo reservado de Windows.**
  `config/diccionario/aux.yaml` pasó los 618 tests y **git no podía indexarlo**
  (`open(...): No such file or directory` sobre un fichero que `ls` enseña). El
  esquema se llama `aux_.yaml`, y el cargador conoce ya la familia entera
  (`con`, `prn`, `nul`, `com1`..`lpt9`) — `con` habría mordido igual, que es el
  nombre de la tabla central de Sigrid. Lección que vale para cualquier
  repositorio del ecosistema: **la suite en verde no demuestra que el fichero
  sea versionable**. Candidata a `arnes-base`; no la he portado porque el código
  que la aplica es el cargador de este proyecto. Decide el líder.
- **Seis tablas de `raw` se ingieren cada noche y no las lee ningún SQL**:
  `auxobrtca`, `obrprv`, `com`, `comlin`, `comprv` y `dcfprodes`. Cuesta ventana
  nocturna y hace creer que hay funcionalidad que no existe. `auxobrtca` es
  además el catálogo oficial de tipos de capítulo que `stg.partidas.categoria`
  **no usa** (usa una heurística). Candidatas a una feature de limpieza o a
  aprovecharlas.
- **`raw.obrprv` está vacía en Ruesma**, y de ahí sale la asimetría de
  `maestro.proveedores_obra`: su `importe_contratado` es `SUM(ctr.totdoc)`, con
  IVA, frente a las sumas de línea sin IVA de `compras`. Documentado en las dos
  fichas.
- **`build-compras` y `build-retenciones` no registran paso en
  `_meta.etl_runs`**: su fecha de build no es consultable por SQL. Afecta a T20,
  T21 y al valor real de `_meta.v_diccionario`. Ya está dicho dentro de
  `R-FRESCURA-MANUAL`.
- **`check-diccionario` (R28) no existe todavía.** Los docstrings ya no lo dan
  por cubierto, y hay un test que se pone en rojo el día que se implemente para
  obligar a corregirlos.
- **Dependencia dura del bloque E**: si T15 crea `_meta.v_diccionario`, hay que
  añadirla al texto de `R-FRESCURA-MANUAL`, de donde se retiró por no existir.
- **Deuda del SQL de negocio, anotada y no tocada**: tres comentarios que
  mienten —el tope del `ratio_lineal` (`04_views_detalle.sql:295`), un fallback
  inexistente (`03_views.sql:129`) y un JOIN muerto con `raw.cen`
  (`05_views_cabecera.sql:174`)—. Engañarán a quien lea el SQL creyendo que el
  YAML se equivoca. Candidatos a una feature de limpieza.

### Decisión pendiente del líder

**El informe de mutación cuenta los timeouts aparte de los supervivientes**, y
eso invita al error: «162 muertos, 0 supervivientes, 4 timeouts» se lee como
campaña limpia. En F-006 los cuatro timeouts **eran cuatro supervivientes**,
comprobado reevaluándolos uno a uno. Propuesta escrita en
`progress/impl_F-006.md`: que el veredicto sea `muertos == total` y que la línea
diga «SIN EVALUAR (timeout)». No aplicada: toca `harness/mutacion.py`, es del
arnés y cambiaría el veredicto de features ya cerradas. Si se acepta, la regla
de propagación obliga a llevarlo a `arnes-base` en el mismo trabajo.

Salieron además **dos defectos más de la campaña**, tampoco tocados: al terminar
**no borra `__pycache__`**, así que la ejecución siguiente puede correr sobre un
mutante compilado —nos dio un falso rojo en `init.sh`, y al revés daría un falso
verde—, y **deja los worktrees huérfanos** (dieciséis, en `Temp`). Ambos en la
misma propuesta.

### Decisión pendiente del humano

El reviewer propone una mejora de `CHECKPOINTS.md`, **no aplicada**: que cuando
una feature entregue contenido declarativo que otro sistema consumirá, C4 exija
que los valores del contrato pasen por un vocabulario cerrado validado, no solo
que el campo exista. Es lo que habría cazado el `cardinalidad: 61`, que ni la
cobertura ni la mutación podían ver porque el valor venía del dato y no del
código.

### Nada de esto se ha tocado

Permisos, `REVOKE`, firewall, Azure y cualquier conexión a la base. Tampoco
`main.py`, `config/settings.py`, `grants.py`, `postgres_client.py` ni ningún SQL
de negocio.
