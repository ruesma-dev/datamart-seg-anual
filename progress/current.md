<!-- progress/current.md -->
# Estado actual

## F-006 · El diccionario semántico del datamart — `in_progress`

Rama `feature/F-006-mcp-azure`. **APROBADO** en la undécima pasada, tras
corregir los defectos de la séptima a la décima.

**El contenido del diccionario está cerrado y no hay que seguir puliéndolo.** El
argumento del reviewer, que el líder asume: cerrar seis defectos de matiz en la
décima pasada **generó tres nuevos de la misma clase**, así que otra ronda no
acerca al objetivo, solo cambia qué frase está mal. Lo que sigue **sin medir** es
el riesgo grande: que un agente encuentre la ficha, reciba las trece reglas y
responda las preguntas.

La deuda viva está en `specs/F-006-mcp-azure/tasks.md`, sección **«Deuda
declarada»** (D1–D6), **con dueño y línea cada entrada**. Era la condición del
aprobado.

`bash harness/init.sh` en verde: **1758 tests**, 127 saltados, cobertura de las
líneas cambiadas **99,0 %** (715 de 722).

### Lo que la décima añade

Tres cosas que valen para cualquier feature de este arnés:

- **Una comprobación cruzada es ciega para lo que solo aparece una vez.** La de
  `agregacion` compara la misma columna entre objetos; medido, **32** columnas
  del ámbito de `R-IMPORTE-MES` están solas y nadie las mira. Se cerró la parte
  derivable y **el resto está declarado con su número**.
- **Un barrido sobre el fichero crudo no ve lo que el YAML pliega.** Hay que
  barrer el crudo (por los comentarios) **y** el cargado (por las frases
  partidas por el ajuste de línea).
- **Un recuento a mano en un docstring envejece.** Dos se desfasaron en una sola
  tanda; ahora se miden en un test y el número vive en un sitio.

### La lección de la novena, que va antes que ninguna otra

**Dos derivaciones con el mismo error no son una comprobación.** El reviewer
reprodujo mi lista «con su propio derivador» y coincidía **porque su script
tenía mi mismo bug**: los dos mapeábamos alias→tabla con un `dict` por fichero,
y en `compras/01_documentos.sql` tres tablas comparten el alias `l`.

Lo grave no fue el bug, sino que **mis pruebas no podían verlo**: fijaban la
coherencia regla↔derivador, no la corrección del derivador. Un derivador
equivocado hace que la regla copie el error y el test salga verde por
construcción. Ahora cada derivador lleva un control que **no lo usa a él**: SQL
fabricado con la respuesta calculada a mano, y contraste del fichero real por
otra vía.

Segunda mitad de la misma lección: **un detector puede cubrir menos de lo que su
mensaje da a entender**. El guardián de nulos saltaba las tres tablas grandes de
`stg` diciendo «no lee directamente de `raw`», que era falso: resolvía el origen
por el `CREATE` y esas tablas se pueblan con `INSERT ... SELECT` en otro
fichero. Al cubrirlo aparecieron seis nulos imposibles más.

### El criterio nuevo, que es lo que hay que recordar de aquí

La octava pasada rechazó porque **las dos correcciones centrales de la séptima
sustituyeron una afirmación falsa por otra**. No fue descuido: yo sí derivaba, y
aun así acerté dos veces mal, porque derivaba de una fuente que gobierna **otra
cosa**.

> **Si una afirmación no es derivable de la fuente que GOBIERNA el hecho, no se
> escribe.** Ni reformulada ni matizada. Se omite, y si el hueco importa se
> declara como hueco.

| Hecho | Fuente que lo gobierna |
|---|---|
| Qué corre en el job nocturno | `Dockerfile` (`CMD ["run-all", "--full"]`) |
| Cómo carga el comando según la bandera | `ingest_raw_step.py` |
| Cómo se llama una bandera | los `click.option` de `main.py` |
| Qué campos propios de `raw` existen | nuestro SQL, que no correría contra columnas inexistentes |

**`azure-apps/sigrid_tablas.md` no está en esa tabla y es deliberado.** Es la
conversión de un PDF de 380 páginas, no se deja segmentar —mi segmentador da a
`obr` un bloque de 1252 líneas y mete `cenrep` dentro de `cen`—, y los dos
intentos de derivar de él produjeron una afirmación falsa. Sirve para consultar
una columna a mano; **no para respaldar una ficha**.

**Se recortó contenido publicado, y está dicho**: `cen.res` (inventado),
`obr.res` (solo lo dice el PDF), cuatro excepciones falsas de la regla de oro, y
los `entcif` que la review sugería añadir —misma fuente, mismo riesgo—. El
diccionario es más pequeño y no miente, que es el propósito de la feature.

### Qué falló en la séptima pasada, en una línea

Trece afirmaciones publicadas que el SQL o el origen desmienten. La mitad eran
**declaradas a mano donde había una fuente comprobable**, así que se cerraron
derivando: un detector de punteros rotos (encontró **24**, once más que la
review), el guardián de nulos ampliado a las dos convenciones de sufijo, el
pipeline citado anclado a `main.build_pipeline_steps`, y el contraste de la
carga de `raw` movido a `ingest_raw_step.py`.

**La peor fue mía y merece quedar escrita**: las 31 fichas de `raw` describían
una carga que no ocurre porque las contrasté contra `config/tables_sigrid.yaml`,
que es **justo el documento que miente**. Sí derivé, pero de la fuente
equivocada, y eso deja 31 fichas en verde afirmando algo falso. Detalle en
`progress/impl_F-006.md`, sección «Séptima pasada».

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

### Estado tras la 13ª pasada

- **Publicado**: `_meta` sirve la **version 3** (`a105d8f1109c`), con el aviso del
  duplicado **corregido y en las cinco fichas** que sirven medidas del fact.
- **El aviso estaba INVERTIDO** y era lo más dañino: alarmaba sobre `importe_mes`,
  que **telescopea y se puede sumar** (200/200 series), y callaba sobre
  `importe_origen`, que **no** (28/200). Ahora va columna a columna.
- **El plegado, tercera vez y dentro del guardián que lo vigilaba.** Tratado como
  clase en `tests/_texto.py`, con dos controles.
- **Cobertura 97,8 %** (era 90,9 %): el cuerpo de los dos comandos se cubre con
  `CliRunner`, sin conexión. Llevaba tres tandas explicando esa laguna.

### Estado tras la 12ª pasada (2026-08-21)

- **Publicado y casando**: `_meta` sirve la **version 2**, hash `a7584ee84391`,
  y `check-diccionario` confirma «lo publicado ES lo del arbol». Las **cuatro**
  fichas del fact avisan ya del duplicado, verificado en la base.
- **`check-diccionario` existe** y contrasta los **102** objetos en las tres
  direcciones. Detecta además que lo publicado se quede atrás comparando
  `hash_fuente`, que es lo que dejó a `_meta` sirviendo un grano falso.
- **El `READ ONLY` se aplica de verdad** (`SET LOCAL transaction_read_only`), y
  hay un control que barre constructores muertos.
- **Los siete NO COMPROBADO, con nombre**, en `progress/impl_F-006.md`. Entre
  ellos **`mart.fact_seguimiento_mensual`**: salía como no comprobado con 30 s y
  60 s, y solo con 180 s reveló la clave rota. **Es la demostración de por qué un
  timeout no puede contarse como OK.**

**Lo único que queda para la batería, y NO lo puede hacer un agente**: lanzar
`build_cierre` para que exista `cierre.v_pbi_planif_vs_real`. Escribe en un
esquema de negocio del servidor compartido y la autorización del humano está
acotada a `_meta`. Pendiente de que el líder la pida.

### EJECUTADO contra la base (2026-08-21) · T19, bloque H y T26

Desbloqueado con el `az login` del humano. Detalle y salidas reales en
`progress/impl_F-006.md`, sección «Contra Azure, de verdad».

- **T19 hecho.** El contrato vive en `_meta`: 102 objetos, 13 reglas, 793
  columnas, cobertura 100 %, singleton con una fila. `v_diccionario` con sus 19
  columnas en orden y `motivo_no_consumo` la última. Los dos `LEFT JOIN`
  comprobados: 4 objetos sin paso siguen saliendo.
- **Bloque H hecho.** Cero objetos publicados sin ficha y cero tipos mal. **Una
  huérfana: `cierre.v_pbi_planif_vs_real`**, que el repositorio crea y la base no
  tiene porque `build_cierre` no registra paso y no se ha vuelto a lanzar. **La
  base va por detrás del repositorio**, y es justo lo que la puerta offline no
  podía ver.
- **T26 ejecutado, y encontró lo gordo.**

  > **`mart.fact_seguimiento_mensual` tiene la clave rota**: la declarada
  > `(obra_id, partida_id, anio_mes, escenario)` **no identifica una fila** en
  > **8.778** casos (17.556 filas), siempre exactamente dos. Causa: **22 obras
  > con dos fases que Sigrid tiene con el mismo `ano` y `mes`**. Un
  > `SUM(importe_origen)` por esa clave **cuenta dos veces**.

  La **ficha ya lo dice** con el número, la causa y el apaño (agregar también por
  `nombre_mes`). **El build no se ha tocado**: es `mart`, de otra feature, y
  ninguna columna publicada identifica la fase, así que arreglarlo es un cambio
  de esquema o de agregación y **necesita su propia feature**.

**Pendiente de esta tanda**: 7 objetos quedaron **NO COMPROBADO** por
`statement_timeout` —nunca contados como OK— y la segunda pasada con 180 s no
terminó dentro de la ventana. Repetirla es barato y no bloquea nada.

### Lo siguiente · la batería de aceptación (bloque K)

Es lo que queda por hacer, y **en este orden**, porque cada paso depende del
anterior:

| Paso | Qué es | Necesita |
|---|---|---|
| **T26** | Comando `check-diccionario` (R28): contrasta contra `information_schema` en vez de la heurística offline de hoy | nada; se puede escribir sin base |
| **T19** 🔌 | `python main.py publicar-diccionario` contra la BBDD real y comprobar el contrato de `_meta` | conexión |
| **T27** 🔌 | `check-diccionario` contra el catálogo real, y **la consulta de unicidad por objeto** (la que cierra «la clave es demasiado corta») | conexión |
| **T39** 🔌 | Las **18 preguntas** de `requirements.md` §9 contra el diccionario publicado | T19 hecho |
| **T40** | Corregir las fichas que la batería delate y republicar | T39 |
| **T37** | Actualizar `azure-apps/datamart_seg_anual.md` | nada |

**🔌 = abre conexión a la base.** Ningún agente lo hace: el `.env` de este puesto
apunta a `psql-albaranes-rs9k2`, compartido con `albaranes` y `partes` **en
producción**. Los tres son `MANUAL (humano)`.

**Lo que hace falta para poder pasar la batería**, en una línea: **T26 escrito** y
**T19 ejecutado por el humano**. Con eso, T39 ya se puede lanzar. Nada de la
deuda D1–D6 bloquea la batería; son afirmaciones de prosa y guardas de
regresión, y la decisión de si alguna entra antes es de T43.

### Lo que necesita firma del humano

Ninguno de estos lo toca un agente, y están detallados en el «Resumen de las
tareas que necesitan firma 🔏» de `tasks.md`:

| Tarea | Qué toca | Riesgo si sale mal |
|---|---|---|
| **T32** | Leer `pg_stat_activity` para ver si Power BI consulta `stg` o `raw` | ninguno: solo lectura; la firma es por el acceso |
| **T33** | **`REVOKE`** sobre `mcp_sigrid_dm_ro` | **Power BI deja de refrescar en silencio**. Rollback: una variable de entorno y `apply-grants` |
| **T34** | Comprobar que Power BI sigue refrescando | ninguno: verificación |
| **T38** | **Regla de firewall** en `rg-albaranes-dev`, recurso de otro proyecto | superficie de red abierta de más |

T19, T27 y T40 escriben en `_meta` de `sigrid_dm` —tres tablas propias de esta
feature— y no tocan datos de negocio ni permisos, así que no llevan firma; solo
los ejecuta el humano por la regla de no abrir conexión.

### Lo siguiente (histórico)

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

- **Los comentarios de `sql/stg/06_presupuesto.sql` mienten** y ya mordieron:
  dicen `importe = ROUND(ROUND(can, decc) * ...)` cuando el código hace
  `ROUND(can * ROUND(pre, decp), deci)` —`decc` no interviene—, y la NOTA de
  cuatro líneas después los desmiente. De ahí salió una ficha falsa en la 8ª
  pasada, por copiar el comentario en vez de leer el código. **Intenté
  corregirlos y no debía**: el guardián de F-011 saltó («F-006 ha tocado SQL de
  negocio») y tiene razón, porque ese fichero es de F-025 y exige su prueba de
  equivalencia. Revertido; **no se debilita un guardián para dejar pasar un
  cambio propio**. Queda propuesto: es un arreglo de dos comentarios que elimina
  una trampa viva.
- **`config/tables_sigrid.yaml` sigue diciendo «catálogo estable, refresco
  completo»** en 13 tablas, y poner `incremental_column: null` no provoca
  ninguna recarga: la recarga la decide `--full` en el `Dockerfile`. Las fichas
  ya aciertan; el fichero de configuración es el que engaña, y fue la fuente que
  me indujo el error de la 7ª pasada.
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
verde—, y **deja los worktrees huérfanos** (dieciséis, en `Temp`).

El reviewer **reprodujo el del bytecode** en un módulo de laboratorio y los tres
están dados de alta como **F-041**, que se arregla fuera de esta feature y viaja
a `arnes-base`. Consecuencia que hay que tener presente: `harness/mutacion.py`
sigue sin tocarse, así que las campañas de F-006 **se han medido con el defecto
presente**; las de esta última tanda se lanzaron borrando `__pycache__` a mano
antes.

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
