<!-- progress/current.md -->
# Estado actual

## F-006 · El diccionario semántico del datamart — `in_progress`

Rama `feature/F-006-mcp-azure`. **Bloques A, B, C y D entregados y corregidos
tras el RECHAZADO del reviewer** (`progress/review_F-006.md`): los diez defectos
están cerrados, cada uno con su fase RED.

`bash harness/init.sh` en verde: **1242 tests**, cobertura de las líneas
cambiadas **98,9 %** y campaña de mutación con **0 supervivientes de 160
mutantes**.

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

**Bloque F a medias** (T20, T21): `compras` (14 objetos) y `retenciones` (10).
Quedan `maestro`, `stg`, `aux`, `_meta` y `raw`.


- **Andamiaje** (bloque A): `etl_sigrid/domain/diccionario.py` (entidades y
  validador), `etl_sigrid/domain/inventario.py` (inventario y cobertura),
  `etl_sigrid/infrastructure/diccionario/cargador_yaml.py`, y la puerta de
  cobertura, que corre en cada `init.sh`.
- **Bloque global** (bloque B): las doce reglas duras, los órdenes de magnitud,
  las convenciones, los nueve esquemas y las 18 preguntas de la batería.
- **Fichas**: `mart` (13), `cierre` (12), `compras` (14) y `retenciones` (10):
  **49 objetos y 593 columnas**, todas contrastadas contra el SQL.

El trinquete `pendientes` está en **53** de 102 objetos —el DDL del contrato
añadió cuatro objetos nuevos a `_meta`—, anclado al inventario y al historial de
git: un objeto documentado ya no puede volver, aunque el repositorio sí puede
publicar cosas nuevas.

### Lo siguiente

El resto del bloque F (`maestro`) y el bloque G (`stg`, `aux`, `_meta`, `raw`):
son los 53 objetos que faltan. Después el bloque H (`check-diccionario`, R28), y
solo entonces los bloques 🔏 de permisos y firewall, que necesitan firma del
humano.

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
