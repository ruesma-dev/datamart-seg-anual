<!-- progress/current.md -->
# Estado actual · 2026-08-26

**Feature en curso: F-006 · MCP sobre el datamart.** Rama
`feature/F-006-mcp-azure`, con el arnés **1.7.7** dentro. `bash harness/init.sh`
**en verde: 2.336 tests, 125 saltados** (526 s); cobertura 100 % de 33 líneas
cambiadas y puerta de tamaño cumplida (impl 215/220). Árbol limpio y **sin
mutantes aplicados**.

**AL RETOMAR, LO PRIMERO: mira si terminó la campaña de mutación.** Se lanzó el
2026-08-26 a las 15:20 con **6 workers**, alcance de 8 ficheros y **256
mutantes**, salida en `progress/mutacion_F-006.md`. **No muta el árbol
principal** —cada worker va en su worktree—, así que si la sesión murió, el
árbol está intacto; compruébalo igual con `python -m harness.mutacion --estado`
y `git worktree list`.

---

## LO PRIMERO AL RETOMAR (2026-08-26, tarde)

**F-006 está a UNA sola cosa de poder ir a revisión: la campaña de mutación**,
más el bloque de documentación T28/T35/T36. La decisión de cómo se mide **ya la
tomó el humano**: campaña **en serie, de noche**.

### Cómo se mide F-006: el modo PARALELO, arreglado el 2026-08-26

**La decisión cambió a media tarde, y por un dato.** Primero se eligió la
campaña en serie de noche. Luego el humano señaló que el arnés ya trae
`harness/mutacion_paralela.py`, se midió qué lo impedía de verdad, y resultó
ser **una sola causa**, no media jornada de trabajo.

**Lo que se midió** (suite completa corrida dentro de un `git worktree` recién
creado desde HEAD): **25 fallos**. Veintitrés eran lo mismo —sin `.env`, la
configuración no valida (`SigridApiSettings: base_url Field required`) y el CLI
devuelve salida vacía—, uno era `test_f015_r12` por el detached HEAD y el otro
lo había roto yo en `current.md`. Con la línea base en rojo, la campaña abortaba
con `BaseRota` sin juzgar un solo mutante. **El modo paralelo no mentía: se
negaba a arrancar**, que es lo que hace desde la 1.5.3.

**Los dos arreglos, hechos hoy:**

| Pieza | Dónde vive | Qué hace |
|---|---|---|
| El `.env` llega a los workers | **`arnes-base` 1.7.7** (`62acb62`), instalado aquí en `c541c23` | El coordinador vuelca las variables al entorno del proceso **antes** de crear los worktrees; los workers las heredan porque `EjecutorPytest` ya lanza pytest con `{**os.environ}`. **El fichero NO se copia**: dejarlo en el temp del sistema pondría credenciales fuera del repositorio y de su `.gitignore`. Lo sostiene un test que levanta una campaña real de dos worktrees y comprueba que ninguno recibe copia |
| `test_f015_r12` | **aquí** (`eba4898`), no existe en `arnes-base` | Ya no pregunta por la rama del repositorio de al lado: monta un repo de juguete y fija la regla entera —con rama devuelve **esa** rama; en detached, cadena vacía, que es el contrato del que depende la puerta de cobertura |

**Y funcionó.** Prueba con 2 workers (`99e2335`): las dos líneas base **en
verde** (331,0 s y 335,5 s), timeout derivado solo (671 s = max(120, 335,5×2)),
**4 mutantes en 1.043 s: 3 muertos, 1 superviviente, 0 timeouts**. El árbol
principal no se mutó y los worktrees se retiraron solos.

**Alcance real: 256 mutantes** (contados con `generar_mutantes`, no estimados),
repartidos así: `diccionario.py` 93, `cargador_yaml.py` 42, `unicidad_sql.py`
27, `relaciones_sql.py` 26, `diccionario_sql.py` 25, `inventario.py` 24,
`catalogo.py` 14, `publicar_diccionario_step.py` 5. **No son los ~400 que se
estimaron ayer.**

| Vía | Duración | Árbol |
|---|---|---|
| Serie (lo decidido por la mañana) | ~18,3 h | mutado toda la noche |
| Paralelo, 2 workers | ~12,6 h | **nunca se muta** |
| Paralelo, 6 workers ← **elegido** | **~5 h** | ídem |

**El coste que no son horas de máquina.** En la prueba salió **1 superviviente
de 4** (`inventario.py:234`: quitarle el `not` a `informe.avisos_columnas` no
mata a nadie). Cuatro no son una muestra, pero `critico` exige **cero
supervivientes**, y cada uno cuesta un test nuevo o una justificación escrita
que acepte el humano. **Decisión del humano: primero ver la lista analizada por
grupos, y solo entonces decidir** — si son decenas, la conversación deja de ser
«escribe tests» y pasa a ser si F-006 puede sostener el rigor que declara (T43).

**El alcance real es mayor que el que se midió ayer.** No son seis módulos:
son **ocho**, todos nacidos en F-006 (verificado con `git log --diff-filter=A`,
2026-08-26):

| Módulo | Líneas | Nació en |
|---|---:|---|
| `etl_sigrid/domain/diccionario.py` | 1.089 | T3 |
| `etl_sigrid/infrastructure/diccionario/cargador_yaml.py` | 468 | T7 |
| `etl_sigrid/infrastructure/postgres/diccionario_sql.py` | 332 | T16 |
| `etl_sigrid/infrastructure/postgres/relaciones_sql.py` | 319 | T40 |
| `etl_sigrid/domain/inventario.py` | 288 | T6 |
| `etl_sigrid/infrastructure/postgres/unicidad_sql.py` | 274 | 2026-08-21 |
| `etl_sigrid/application/steps/publicar_diccionario_step.py` | 190 | T17 |
| `etl_sigrid/infrastructure/postgres/catalogo.py` | 166 | 12ª pasada |
| **Total** | **3.126** | |

Son **489 líneas más** que las 2.637 anotadas ayer: un ~19 % más de mutantes, y
con ellos más horas. Lo demás medido sigue valiendo: **~4,3 min por mutante**
con la suite completa (2.291 tests), **~2,2 min** con solo los 617 de F-006. El
intento de ayer se paró a los 82 minutos, por la línea 219 de 1.089 del primer
fichero; el árbol quedó restaurado.

**La conclusión incómoda no cambia, y ahora es más grande**: 3.126 líneas de
producción con `rigor: critico` cuestan una campaña de una noche larga cada vez.
**F-006 es demasiado grande para el rigor que declara**, y eso es materia de
T43.

**Ojo con el modo serie**: muta el ÁRBOL PRINCIPAL (`muta_arbol_principal: true`).
Si una campaña muere a medias, queda código mutado en disco. El centinela
`.arnes_cache/mutacion_en_curso.json` lo declara y
`python -m harness.mutacion --restaurar` lo deshace. Compruébalo SIEMPRE antes de
fiarte de cualquier medición.

### Lo demás de F-006, ya cerrado

- Los **cuatro hallazgos** del review (H2-H5): cerrados, ver la sección siguiente.
- El **diccionario está en versión 9 y PUBLICADO** en `_meta` (103 objetos, 798
  columnas, 16 reglas, cobertura 100 %), verificado contra la base con
  `check-diccionario` y `check-unicidad`. La remisión falsa ya no se sirve.
- El **bloque de Power BI**, entregado a F-034.
- El **MCP, probado de punta a punta** en Claude Escritorio y en el móvil.

### Y un aviso sobre el papeleo

`progress/review_F-006.md` (el resumen) **arrastra como abiertos hallazgos que ya
estaban cerrados en el árbol**: se escribió copiando la tabla de la 16ª pasada sin
contrastarla contra el código. Cuando el reviewer haga la 17ª pasada, que
reverifique contra el árbol y reescriba esa tabla. La lección, que ya está en
este fichero desde F-006: **verificar lo que la tanda dice haber hecho, no lo que
parece**.

### Nada se ha subido a ningún remoto

`dev` va **145+ commits** por delante de `origin/dev` y no se ha hecho `git push`
en toda la sesión. `arnes-base` tiene la 1.7.5 y la 1.7.6 sin subir. `mcp-bbdd`
**no tiene remoto configurado**: sus commits existen solo en este disco.

---

## 17ª pasada: los cuatro hallazgos del review, cerrados (2026-08-26)

Encargo del humano tras resolver por vía externa el H1 (fallo del arnés, ya
arreglado río arriba) y el bloque de Power BI (entregado a F-034). Cuatro
commits, uno por hallazgo; el detalle con las trazas RED está en
`progress/impl_F-006.md` §7 y en el anexo (`impl_F-006_detalle.md`, L4767+).

| # | Qué era | Cómo queda |
|---|---|---|
| H2 | Mutante `and→or` en `diccionario_sql.py:297` | **cerrado**: ya moría; añadidos los tres casos de cadena, cada uno lo mata solo |
| H3 | Guardián de coherencia, tres vías de evasión | **cerrado**: las tres, desde la 16ª; hoy se cierra la CLASE con un criterio `ast` (22 comparaciones crudas reescritas) |
| H4 | «22 obras» mal atribuido | **cerrado**: las 7 apariciones ya estaban bien; se añade la guarda «donde va el 22 va el 9» |
| H5 | Remisión falsa publicada al agente | **cerrado**: era el único abierto de verdad |

**Lección que conviene no perder: el resumen del review mentía sin querer.**
`review_F-006.md` se escribió el 2026-08-25 partiendo el papeleo y copió la
tabla de hallazgos de la 16ª pasada **sin reverificar el árbol**. Y esa pasada
viaja en el **mismo commit** que sus arreglos (`3ec962c`): el reviewer escribió,
el implementer arregló y se comitearon juntos. Resultado: tres hallazgos
constaban abiertos estando cerrados. **Al resumir un informe, reverifica o di
que no lo has hecho.**

**Dos cosas paradas, a la espera del humano:**

1. ~~**Republicar el diccionario.**~~ **RESUELTO SOLO, y conviene saber por qué**
   (verificado el 2026-08-26 a las 11:42). No hizo falta publicar nada: **la
   nocturna ya lo hizo a las 06:59**, porque `publicar_diccionario` es un paso
   de `run-all`. `_meta` sirve la **versión 9**, hash `72125091cc25`, batch
   `20260826T065947Z-f0d443`, **idéntico al que calcula el árbol**. La remisión
   falsa ya no se sirve. Los permisos del rol del MCP sobrevivieron a que se
   recreara la vista: `mcp_sigrid_dm_ro` conserva `SELECT` sobre los ocho
   objetos de `_meta`, `v_diccionario` incluida, así que **no hizo falta
   `apply-grants`**. **La lección: antes de dar por pendiente una publicación,
   pregúntale a la base**; la nocturna publica sin avisar a nadie.
2. **La campaña de mutación** (RM1: se lanza con el árbol quieto). Las tres
   puertas contra la base **ya están ejecutadas** (2026-08-26, ver más abajo).

**Sigue abierto de higiene (h6):** publicar la consulta que da «37 celdas /
39,07 M€» y la del «22 obras». Exige medir contra la base; mientras tanto la
ficha **declara el hueco** en vez de inventar una consulta.

---

## El otro frente: `mcp-bbdd`, el servidor que sirve este diccionario

Repositorio aparte (`C:\Users\pgris\PycharmProjects\mcp-bbdd`), **sin remoto**.
El 2026-08-25 recibió el arnés (hoy 1.7.5), se le crearon las ramas `main`/`dev`
—antes se trabajaba directo en `main`— y se le sembró el backlog del despliegue.
Su `progress/current.md` manda sobre lo que aquí se resuma.

**Objetivo acordado con el humano:** migrar el MCP a Azure y exponerlo como MCP
remoto, para que cualquier usuario lo use desde Claude Escritorio **y desde el
móvil**. El móvil descarta `stdio` por definición: no hay proceso local que
lanzar.

Backlog: F-002 (verificar conectores) **done**; luego F-003 (transporte
`streamable-http`, entregando escuchando **solo en local**), F-004 (OAuth con
Entra ID), F-005 (auditoría con identidad desde el primer día), F-009 (las
reglas de negocio dejan de estar duplicadas), F-006 (contenedor y Container
App), F-007 (documento en `azure-apps/`) y F-008 (acotar por persona, aplazada
a propósito: hoy **todos ven todo**, decisión explícita del humano).

Tres hallazgos de la prueba de F-002 que ya viajan en sus fichas: Claude
descubre OAuth pidiendo `/.well-known/oauth-protected-resource[/mcp]` y
`/.well-known/oauth-authorization-server` —eso ES la especificación de F-004—;
el SDK responde **`421 Invalid Host header`** a lo que venga de fuera si el Host
no está en su lista blanca, y en Azure pasará igual; y **el cliente no protege
nada**: aceptó un servidor sin autenticación ninguna.

---


## El arnés, de 1.5.1 a 1.7.6 (2026-08-25 y 26, integrado en la rama de F-006)

Actualización con el instalador de `arnes-base` en modo actualizar. Lo genérico
entró solo; `harness/init.sh` y `CHECKPOINTS.md` se **fusionaron a mano** para
no perder lo propio del proyecto (la cabecera de configuración y la sección 9
del primero; las trampas del dominio Sigrid y la regla del SQL por capas del
segundo). `CLAUDE.md`, `docs/CONVENTIONS.md` y `docs/referencia/README.md` se
conservaron: el payload solo traía la plantilla sin adaptar.

**La 1.7.6 nació aquí, el 2026-08-26, y desbloquea las campañas de mutación de
cualquier proyecto con el arnés.** El test del propio arnés que vigila el
bytecode (`test_C_un_mutante_nunca_se_juzga_con_el_bytecode_del_anterior`)
fallaba cuando `PYTHONDONTWRITEBYTECODE` estaba en el entorno, que es justo la
variable que la campaña define en cada evaluación desde la 1.6.3. Resultado: la
línea base salía **siempre** en rojo y la campaña abortaba sin escribir informe.
Arreglado río arriba y reinstalado aquí; verificado con y sin la variable.

### Lo que cambia en el día a día

| Novedad | Qué significa |
|---|---|
| **Puerta de tamaño** (`python -m harness.tamano`) | El papeleo de la feature en curso tiene topes: requirements 150, design 250, impl 220, review 140 líneas. Pasarse pone el portero en **rojo**. Solo mide la feature abierta; lo `done` está amnistiado. |
| **`nivel_por_defecto` = `estandar`** | Antes, una feature sin `rigor` heredaba `critico`. Ya no: `critico` **se declara**. |
| **Campañas `estandar` muestreadas** | 20 mutantes con semilla fija `20260820`. **Sus números no son comparables** con los de campañas anteriores. `--max-mutantes 0` fuerza la campaña entera. |
| **El venv del proyecto manda** | El portero antepone `.venv` al PATH: se acabaron los veredictos distintos según cómo se abriera la terminal. |
| **Centinela de campaña** | Si queda un mutante aplicado en el árbol, el portero lo dice en vez de medir encima. |

### El papeleo de F-006 se partió en resumen + anexo

Lo exigía la puerta nueva (impl iba por 4.763 líneas contra un tope de 220). El
detalle **está intacto**, solo cambió de nombre:

| Se lee primero (resumen, medido) | Detalle íntegro (anexo, no medido) |
|---|---|
| `specs/F-006-mcp-azure/requirements.md` (132) | `requirements_detalle.md` (557) |
| `specs/F-006-mcp-azure/design.md` (191) | `design_detalle.md` (1.004) |
| `progress/impl_F-006.md` (197) | `impl_F-006_detalle.md` (4.763) |
| `progress/review_F-006.md` (125) | `review_F-006_detalle.md` (4.918) |

**Efecto colateral que conviene recordar:** tres tests de F-006
(`test_f006_fichas.py`, `test_f006_publicacion.py` ×2) leían `design.md` para
verificar el contrato **letra a letra** —los bloques YAML, el DDL de
`_meta.v_diccionario` y la §4.2—. Al resumir el diseño se pusieron rojos, y
ahora apuntan a `design_detalle.md`. Si algún día se parte más papeleo, mira
antes quién lo lee: `grep -rn "<fichero>" --include=*.py .`

Los resúmenes son **índices navegables**, no versiones cortas: están los 41
requisitos, las 43 tareas y el recorrido de checkpoints, cada uno con su enlace
al anexo. El veredicto vigente del reviewer sigue siendo **RECHAZADO** (pasada
decimosexta): la actualización del arnés no cambia nada de eso.

### Trece tests del proyecto iban por detrás de la herramienta

`tests/` no solo prueba el ETL: prueba también las herramientas del arnés, y
trece tests codificaban el comportamiento de la 1.5.1. Se adaptaron **sin
aflojar ninguna aserción** (`test_f015_mutacion.py` pasó de 92 a 97):

| Fichero | Qué codificaba de la versión vieja |
|---|---|
| `test_f006_fichas`, `test_f006_publicacion` | Leían el contrato letra a letra de `design.md`; ahora leen `design_detalle.md` |
| `test_f015_mutacion` (5) | La campaña sin línea base, sin código 3 y sin `stdout` en el proceso |
| `test_f020_mutacion` (7) | Campaña por servicios y códigos de error |
| `test_f015_rigor` (1) | «Sin rigor declarado se aplica el más exigente», la regla que derogó la 1.7.0 |
| `test_f020_genericidad` (2) | R17, gemela de R19; y una lista blanca de módulos estándar escrita a mano |

**R19 y R17 se afinaron, y esto conviene entenderlo antes de tocarlas.** R19
(en `test_f015_rigor.py`) y R17 (en `test_f020_genericidad.py`) son la misma
regla escrita dos veces en dos features distintas. Exigían que
ninguna herramienta de `harness/` mencionara palabras del datamart, barriendo
el texto entero. El arnés 1.7.4 trae 20 menciones que **no son dependencias**:
notas de procedencia («esto nació en `albaranes` F-038»), `mutacion_paralela.py`
citando este repositorio como su origen, y «cierre» en castellano llano («la
línea base de cierre EXPIRÓ»). Decisión del humano el 2026-08-25: **R19 vigila
el código ejecutable, no la prosa**. En concreto:

- el barrido usa `ast` para quitar comentarios y docstrings, y **conserva los
  literales**: un mensaje de error que nombre a Sigrid sigue atando igual;
- `\bcierre\b` pasa a `cierre\.\w`, el uso cualificado con el que se cita un
  esquema;
- la lista blanca de módulos estándar de R17, escrita a mano, se sustituye por
  `sys.stdlib_module_names`: envejecía en cada versión del arnés (la 1.7.x trajo
  `math`, `signal` y `contextlib`) y cada envejecimiento se leía como una
  violación que no lo era. Preguntar por la biblioteca estándar de verdad caza
  además cualquier dependencia de terceros, incluida la que nadie prohibió;
- `f-0\d\d` **se retira** —`tamano.py` lo usa de ejemplo en el `help` de
  `--feature` y no ata a nadie— y en su lugar entra una comprobación más
  fuerte: **ninguna herramienta importa `etl_sigrid`, `config`, `main`, `tests`
  ni `infra`**, que es la atadura de verdad. Verificado metiendo el import a
  propósito: el test se pone rojo.

Queda **propuesto para `arnes-base`**: que las herramientas genéricas lleven su
procedencia en el registro de versiones y no en el docstring del módulo.

### Dos cosas que hay que mirar antes de seguir

1. **F-041 puede haber encogido.** Denuncia que la campaña de mutación miente
   por timeouts y bytecode. El bytecode **ya está arreglado** río arriba (1.6.3:
   la campaña ejecuta con `PYTHONDONTWRITEBYTECODE=1`) y los timeouts ahora se
   derivan de la línea base medida (1.7.2), no de una constante. Lo que **sigue
   vivo** es que un mutante cuya suite no recoge ni un test sale
   `SUPERVIVIENTE` en vez de «no juzgado», así que **una campaña de una sola
   pasada aún no vale como evidencia**: contrasta con una segunda
   (`--workers 1`). Revisa la ficha de F-041 antes de trabajarla.
2. **Siete features siguen sin `rigor` declarado** (F-002, F-007, F-010, F-012,
   F-013, F-017, F-018). Decisión del humano el 2026-08-25: **se quedan así** y
   el nivel se decide al abrir cada una, cuando se conozca el alcance real. Que
   nadie lo lea como un descuido.

---

## El MCP, probado por fin en Claude Escritorio (2026-08-25)

**El protocolo MCP queda ejercitado de punta a punta.** Era el agujero que
ningún agente podía cerrar —hacía falta la máquina y la aplicación del humano— y
ya está hecho: `initialize` → `notifications/initialized` → `tools/list`, los tres
con `result`, contra el datamart real en Azure.

Dos cosas que costaron encontrarse y conviene no volver a buscar:

- **Claude Escritorio está instalado desde la Microsoft Store**, así que NO lee
  `%APPDATA%\Claude\claude_desktop_config.json`. El fichero bueno es
  `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json`.
- Su entrada `bbdd-ruesma` **no declara bloque `env`**, y eso es lo correcto: sin
  variables que lo pisen, el servidor lee el `.env` de `mcp-bbdd`, que apunta a
  Azure con el rol de solo lectura. El `claude_desktop_config.json` que vive
  DENTRO del repositorio `mcp-bbdd` apunta a `localhost` con el usuario
  `postgres`: si alguien lo copia tal cual, se conecta a la base local con un rol
  de escritura.

Arranque bueno, para reconocerlo en `mcp-bbdd/logs/mcp_bbdd.log`:

```
Pool creado contra mcp_sigrid_dm_ro@psql-albaranes-rs9k2...  (sslmode=require)
Diccionario cargado de _meta: 103 objetos, 16 reglas, 29 entradas de contexto
                              en 5 bloques, 3 columnas ocultas (versión 8)
```

### El fallo que la capa semántica no puede evitar (→ F-046)

Primera pregunta de negocio real: retenciones a proveedores de la obra 0694. **El
MCP acertó y el modelo falló al escribir.** Lanzó el SQL correcto (22 filas) y
además consultó `retenciones.v_pbi_retencion_obra`, que le devolvió el total
exacto: **34.523,22 € en 61 efectos**. Al redactar la tabla copió en la casilla de
saldo vivo de un proveedor el valor de la columna *vencido* (251,32 en vez de
1.575,96), perdió un efecto de **1.324,64 €** —el cuarto mayor de la obra— y sumó
su propia tabla, publicando **33.198,58 € en 60 efectos**: contradijo el total que
tenía delante.

Todo lo demás estaba bien y verificado contra la base: 61 efectos vivos, ninguno
liquidado, cliente sin retenciones en la obra, 6.380,73 € vencidos, y el desglose
de OCL, Demoltécnica y Tepuy exacto. **Por eso es peligroso: la respuesta parece
impecable.** Es el diagnóstico del reviewer llevado al extremo —*el problema nunca
han sido los datos, sino los instrumentos que decían que los datos estaban
bien*—, solo que aquí el instrumento es el modelo. Ficha: **F-046**.

### Y un hueco de dominio (→ ampliado en F-039)

El cruce obra × proveedor **sí** se puede hacer: `retenciones.movimientos` trae
obra y entidad en la misma fila. Pero `saldo_vivo` y `neto_practicado` —las
métricas que el propio diccionario manda usar— **solo existen en
`v_pbi_retencion_entidad` y `v_pbi_retencion_resumen`**, que ya vienen agregadas
y han perdido la obra. Por obra tienes `importe`; por métrica correcta pierdes la
obra. Un agente obediente acabará llamando saldo vivo a un importe acumulado.

---

## Lo que hace F-006, en una línea

Publicar en `_meta` la **capa semántica** del datamart —qué significa cada
objeto y cada columna, y qué reglas hay que respetar para leerlo— para que
**cualquier agente conectado por MCP construya sus propios casos de uso**, no
solo los seis que el humano dio de ejemplo. Los seis casos son la **batería de
aceptación**, no la especificación.

## Dónde está

Diccionario en **versión 9, publicada y verificada**: **103 objetos**
documentados, **798 columnas**, **46 de consumo recomendado**. (Estas cifras las
comprueba un test: si envejecen, la suite se pone roja. Ya caducaron dos veces.)

**Lo que sirve `_meta` hoy ES lo del árbol**: versión 9, hash `72125091cc25`,
publicada por la **nocturna** del 2026-08-26 a las 06:59 y contrastada a las
11:42 con `check-diccionario` («OK lo publicado ES lo del arbol»). La remisión
falsa que corrigió la 17ª pasada ya no llega al agente.

Tres puertas que lo contrastan **contra el dato real**, no contra sí mismo:

| Comando | Qué comprueba |
|---|---|
| `check-diccionario` | biyección ficha ↔ objeto que existe en la base |
| `check-unicidad` | que la clave declarada sea de verdad única |
| `check-relaciones` | que el JOIN de cada relación declarada **devuelva filas** |

**Las tres, ejecutadas contra Azure el 2026-08-26 a las 11:42-12:05:**

| Puerta | Resultado |
|---|---|
| `check-diccionario` | **OK, lo publicado ES lo del árbol** (v9, hash `72125091cc25`). 103 fichas frente a los 102 que hoy existen en la base: la única huérfana sigue siendo `cierre.v_pbi_planif_vs_real`, la deuda de F-047 (la base va por detrás del repositorio) |
| `check-unicidad` | **39 sin contradicción, 0 con la clave rota**, 6 sin comprobar por timeout de 30 s (`mart.fact_seguimiento_mensual`, `v_pbi_fact`, `v_master_versiones_tipadas`, `v_master_vigente_anual` entre ellas), 1 fichado que no existe |
| `check-relaciones --todos` | **78 unen, 0 que NO unen**, 2 con cobertura escasa, 16 sin comprobar, 2 con un extremo inexistente |

Comparado con la medición del 2026-08-25 (77 unen / 17 sin comprobar), **una
relación más queda verificada**. Y lo que ninguna de las tres demuestra, dicho
por ellas mismas: *un objeto sin contradicción no tiene la clave demostrada, y
una relación que une podría unir por la columna equivocada y coincidir*.

El lado consumidor (`C:\Users\pgris\PycharmProjects\mcp-bbdd`, repo aparte, ya
en git) consume `_meta` y sirve **los cinco bloques** de contexto.

---

## Lo que falta para cerrar F-006

### Nuestro
- ~~**Bloque J, documentación** (T35-T37)~~ y ~~**T28**~~: **HECHAS el
  2026-08-26** (18ª pasada). T28 en `33808dc`, T35 en `4e180c0`, T36 en
  `cf12d9a`; **T37 ya estaba hecha desde el 2026-08-22** (`2e9bee8` de
  `azure-apps`) y el informe la daba por pendiente. Las tres nuevas van atadas
  por 14 tests (`tests/test_f006_docs.py`): la documentación deja de poder
  envejecer en silencio.
- **La tabla de tareas de `impl_F-006.md` está reverificada fila a fila** contra
  el árbol, con cuatro desfases corregidos: T15 decía 3 tablas y el DDL crea 4;
  T24 decía 7 objetos en `_meta.yaml` y son 8; T37 constaba pendiente estando
  hecha; y la progresión de la suite contradecía desde hacía tres pasadas a su
  propia fila de al lado.
- **T29-T31** (los `REVOKE` construidos y apagados) **siguen sin existir en
  código**. No bloquean el cierre —DA-3 se resolvió por B—, pero la tabla los
  cuenta como pendientes y conviene no confundirlos con «entregados a F-034»,
  que son T32-T34.
- **T43**: decidir con el humano qué deuda declarada se paga y cuál viaja.
  **Los supervivientes de la campaña son materia de T43**: si son muchos, la
  pregunta no es cuántos tests se escriben, sino si esta feature puede sostener
  el rigor que declara.
- **Cierre**: T41 (mutación, **lanzada**) y T42 (`init.sh`, **verde**: 2.336
  tests), más el veredicto del reviewer contra `CHECKPOINTS.md`. Sin él, la
  feature **no se marca `done`**.

### Del humano: las dos, resueltas el 2026-08-25
- ~~Probar el MCP dentro de Claude Escritorio.~~ **HECHO.** El protocolo quedó
  ejercitado de punta a punta contra Azure; ver la sección «El MCP, probado por
  fin en Claude Escritorio» más arriba.
- **T32 🔏 (Power BI): DECIDIDA — no se hace aquí.** Decisión del humano:
  *«del BI olvídate, será una feature posterior»*. Con eso, la decisión abierta
  **DA-3 se resuelve por su opción B**: los `REVOKE` (T29-T31) se quedan
  **construidos y apagados**, y T32, T33 y T34 se **entregan a F-034**, que es
  la feature que se ocupa de Power BI. Ya no bloquean el cierre de F-006.

  Lo que hay que llevarse a F-034, porque es la trampa: el rol
  `mcp_sigrid_dm_ro` **lo comparten hoy el MCP y Power BI**. Encender los
  `REVOKE` sin verificar antes qué lee Power BI le rompe los informes. Y la
  urgencia sube cuando el MCP se abra a más usuarios (backlog de `mcp-bbdd`),
  porque ese rol compartido pasa a ser el de todos ellos.

### El objetivo que todavía NO está cumplido
El humano pidió **«un MCP que pueda usar cualquier usuario desde cualquier
puesto»**. Hoy el MCP corre **en el puesto de pgris** apuntando a Azure. T38
(desplegar el entorno) está **bloqueada hasta que ese entorno exista**. Lo
construido es la capa semántica, que era el prerrequisito, no el despliegue.

---

## Lo que esta feature ha enseñado, y conviene no volver a aprender

1. **El defecto sobrevive «en el campo de al lado».** Ocurrió más de cinco
   veces: se corrige la cabecera y el aviso sigue mal en la columna; se arregla
   una vista y la hermana queda igual. En T40, «el centro de coste coincide con
   la obra» estaba en **cuatro fichas**, y `es_activa` mentía en **cinco
   sitios**. Corregir donde te lo señalan no es corregir.
2. **Un barrido de texto sobre el YAML crudo no ve las frases plegadas.**
   Rompió cuatro comprobaciones de esta feature, una de ellas el propio
   guardián escrito para evitarlo. Barre siempre sobre el diccionario
   **cargado**.
3. **Un test verde puede sostener una mentira.** Había un test exigiendo
   literalmente `assert "98" in obra.significado` — es decir, obligaba a que la
   ficha repitiera una afirmación falsa.
4. **Una relación puede resolver perfectamente y no unir nada.** El validador
   offline no puede verlo: los dos extremos existen y los tipos encajan. Lo que
   falla está en los datos. De ahí `check-relaciones`.
5. **Preguntarle al adaptador cuántos bloques hay es preguntarle al acusado.**
   El verificador de `mcp-bbdd` lee de la base por el pool, no por el código que
   se los estaba dejando.

---

## Deuda y decisiones abiertas

### Del humano
- **`CHECKPOINTS.md`**: el reviewer propone que C4 exija que los valores de un
  contrato declarativo pasen por un **vocabulario cerrado validado**, no solo
  que el campo exista. Es lo que habría cazado el `cardinalidad: 61` (YAML leyó
  `1:1` como sexagesimal), que ni la cobertura ni la mutación podían ver porque
  el valor venía del dato, no del código. **No aplicada.**
- **`harness/mutacion.py`**: que el veredicto sea `muertos == total` y que un
  timeout diga «SIN EVALUAR». En F-006 los cuatro timeouts **eran cuatro
  supervivientes**. Toca el arnés y cambiaría el veredicto de features ya
  cerradas; si se acepta, viaja a `arnes-base` en el mismo trabajo.

### Backlog nacido de esta feature
| Feature | Prio | Qué |
|---|---|---|
| **F-041** | 2 | **La puerta de mutación no comprueba nada.** Mientras no se arregle, **ningún número de mutación de este repositorio es evidencia**. Superviviente real conocido: `and`→`or` en `diccionario_sql.py:297`. |
| **F-042** | 2 | Clave rota del fact y **agregado doblado**: 39,07 M€ de más en 8 obras, alimentando tarjetas KPI de Power BI. |
| **F-045** | 2 | **Las retenciones no se pueden atribuir a una obra** (nace de T40). |
| **F-044** | 1 (tras el MCP) | Los cuatro `build-*` a la nocturna. Medido: **37,5 min**, el disco no se mueve. |
| F-036..F-040 | 2-6 | Huecos de dominio: oficios, tesorería, comparativos, vistas puente, ingresos. |

### Huecos de negocio declarados, sin resolver
- **El mayor proveedor de la empresa es la propia empresa** (intragrupo). Tumba
  silenciosamente cualquier ranking de «quién ha facturado más», que era uno de
  los seis casos de uso.
- **Los órdenes de magnitud** ya llegan al agente, pero cubrían solo
  `retenciones`; T40 los amplió a donde están los importes.

---

## Reglas vigentes que no se negocian

- Escritura autorizada **solo en el esquema `_meta`** de `sigrid_dm`. Todo lo
  demás, lecturas. `psql-albaranes-rs9k2` lo comparten `albaranes` y `partes`
  **en producción**: las puertas corren en transacción `READ ONLY` y con
  timeout.
- **Firewall**: regla **única y sin fecha** `datamart-puesto-pgris`, se reescribe
  con la IP del momento. No se crean reglas nuevas ni se tocan las ajenas.
  (`-n` es la REGLA; el servidor va en `--server-name`.)
- **No ampliar** los 32 GB del servidor; umbral de parada al **80 %** de disco
  (hoy 57,93 %).
- Nunca secretos en el repositorio. `.env` no se toca ni se sube.
- Sin `git push` ni PRs sin petición explícita.
- Commits **con rutas explícitas** (`git add <ruta>`, nunca `-A`): más de un
  agente sobre el mismo árbol, y ya se mezcló trabajo ajeno en un commit.
  **Y no basta** (medido el 2026-08-26, commit `9c04534`): la ruta explícita
  protege de arrastrar *otros ficheros*, no de arrastrar a otro agente dentro
  del **mismo** fichero, porque `git add` se lleva lo que ese fichero tenga ya
  en el índice. Con dos agentes escribiendo en un anexo compartido no hay forma
  de commitear por separado: **cada uno a su propio fichero**, o el primero que
  commitee se lleva lo que el otro tuviera preparado.
