<!-- progress/review_F-006.md -->
# F-006 · Review — el diccionario semántico (resumen)

> El detalle de las veinte pasadas —hallazgos, citas de código y las
> reverificaciones de esta— vive en
> [`review_F-006_detalle.md`](review_F-006_detalle.md) (5364 líneas). **Este
> fichero es el índice de entrada.**

## Veredicto · 20ª pasada, 2026-08-26

**Revisión COMPLETA** (pasada 20), no incremental: el veredicto vigente era
RECHAZADO desde la 16ª, así que no hay «último commit aprobado» desde el que
medir un delta. `HEAD = 6332995`.

# RECHAZADO

**Nivel de rigor: `critico`**, declarado en `harness/features.json`: exige C1-C5,
fase RED, cobertura, campaña de mutación, **cero supervivientes** salvo
justificación escrita aceptada por el humano, y RM1-RM6.

**Quede claro qué se rechaza y qué no.** La ingeniería está hecha y la he
verificado yo, no leída: la campaña de mutación es **válida por primera vez**,
sus totales cuadran con mi recálculo independiente, los 52 supervivientes son
mutantes reales byte a byte, los tres equivalentes se sostienen y los cinco
mutantes que reverifiqué en serie mueren. **Lo que bloquea es que los documentos
no dicen lo que dice el árbol** — el mismo defecto que ya quemó dos veces a esta
feature, y que aquí llega a prometerle a F-034 un mecanismo que no existe.
**Ninguno de los cuatro hallazgos exige ingeniería: los cuatro son escritura.**

## Lo que verifiqué contra el árbol (no contra el papeleo)

| Qué | Cómo | Resultado |
|---|---|---|
| Entorno | `bash harness/init.sh` tal cual | **exit 0**, 2473 pasados, 128 saltados, 603,92 s; cobertura 100 % de 33 líneas; tamaño dentro (impl 219/220) |
| Alcance y nº de mutantes | recálculo puro con `harness.alcance` + `harness.mutacion.generar_mutantes` | **3126 líneas / 256 mutantes: coincide exacto** |
| Que los 52 supervivientes existan | parseo del informe y contraste de fichero, línea, **operador** y texto original→mutado | **52 de 52 reproducibles**, 0 fallos |
| RM1 · SHA medido | diff `99e2335..HEAD` | **ninguno de los 8 ficheros del alcance cambió**: solo `progress/`, `BACKLOG`, `features.json` y 5 de `tests/` |
| RM2 · tiempos | `media × W` = 32,7 × 6 = **196,2 s** vs línea base ~470 s (ratio 0,42) | coherente; el 80 % de muertos con `-x` explica la media |
| Los 60 s | «Tiempo total» 8368,3 s (2 h 19 min) | **campaña NO reejecutada**, y queda dicho: la regla no obliga por encima de 60 s |
| RM5 · un equivalente | `relaciones_sql.py:282` `int(UMBRAL*100)→*101`, aplicado con el propio mutador, 11 casos (8 en la rama `AVISO`) | **salidas idénticas: equivalente confirmado** |
| Los otros dos equivalentes | premisas verificadas desde el árbol: `ficha`/`datos` son **JSONB** en el DDL, y el único `sha256` va sobre los **bytes del YAML** | `ensure_ascii` no es observable: se sostienen |
| RM4 · 5 mutantes en serie | worktree aparte, `.env` volcado, línea base **verde** primero (189 passed) | **5 de 5 MUERTOS**, incluido el falso muerto de `inventario.py:234` |
| RM6 | diff `99e2335..HEAD` | **ninguna línea de producción tocada**: no se quitó ninguna guarda |
| Secretos | 10 patrones sobre los 37 ficheros del diff `dev...HEAD` | **cero hallazgos** |
| T29-T31 | `grep` en todo el repositorio | **no existen**: sin `revocar_en`, sin `PG_REVOKE_FUERA_DE_CONSUMO`, `DEFAULT_CONSUMPTION_SCHEMAS` sigue en nueve esquemas |

## Recorrido de `CHECKPOINTS.md`

| CP | Estado | Motivo |
|---|---|---|
| **C1** Arnés en verde | `[x]` | `init.sh` exit 0; los siete ficheros obligatorios existen |
| **C2** Estado coherente | `[x]` | Una sola `in_progress`; rama correcta; `current.md` solo la sesión del 26 |
| **C3** Arquitectura y convenciones | `[x]` | Dominio sin infraestructura; ruta en la 1ª línea; sin `print()` ni TODO; SQL en `sql/ddl/01_diccionario.sql` con numeración. **Las tres trampas Sigrid documentadas en el diccionario**: `fasnum`/`fas`, `importe_origen`/`importe_mes` (con la medición 200/200) y las versiones master duplicadas |
| **C3 bis** Documentos de fuera | **N/A justificado** | El diff no toca `docs/referencia/`. El barrido de secretos se hizo igual: cero |
| **C4** Verificación real | `[ ]` | **R30-R34 sin un solo test trazable** (H4). Menor: R35/R36 se prueban pero nombrados `test_f006_t35_*` en vez de `test_f006_r35_*` |
| **C4 bis** El rigor declarado | `[ ]` | **Los 52 análisis de supervivientes siguen en `PENDIENTE`** (H1) y la sección «Evidencias» de `impl_F-006.md` contradice al árbol y **omite el nº de workers** (H2). Todo lo demás del bloque —RM1 a RM6, totales, cero cabecera de campaña no válida, 0 timeouts, 0 «sin veredicto»— **cumple y está verificado** |
| **C4 ter** Rutas sensibles | **N/A sin nada que justificar** | No existe `harness/rutas_sensibles.json`: es el caso mayoritario que el propio checkpoint declara N/A |
| **C5** Sesión cerrada | `[ ]` | **T41 y T42 hechas y sin marcar**; T29-T34 y T38 sin anotar su entrega (H3). Árbol limpio, sin ficheros sin trackear, sin worktrees huérfanos |

## Mi criterio sobre LA LIMITACIÓN (respuesta a la pregunta del líder)

**¿Basta para un `critico` que la campaña paralela produzca falsos muertos y que
los 204 muertos no sean lista cerrada? SÍ, basta para cerrar F-006** — y no
bastaría sin las dos condiciones que ya se cumplen. Razones, porque un «sí» sin
razones aquí no vale nada:

1. **La dirección peligrosa está tapada donde importa.** Un falso muerto esconde
   un superviviente, pero **todo lo que se declaró muerto por los tests nuevos se
   reverificó EN SERIE**. Yo he reverificado cinco más, también en serie y con
   línea base verde delante. El riesgo residual vive solo en los 204 que la
   campaña paralela juzgó y nadie volvió a mirar.
2. **El único falso muerto confirmado se persiguió hasta matarlo.**
   `inventario.py:234 [not]` no se documentó y se dejó: se cazó, se explicó y
   hoy muere. Lo he comprobado en mi propio worktree.
3. **Está declarado por escrito, con dueño y con consecuencia práctica.**
   `control_mutacion_F-006.md` no maquilla el cero de la muestra de control:
   escribe que doce casos no descartan una tasa baja y que **52 es un suelo, no
   una lista cerrada**. Está fichado en **F-041** (`pending`, prioridad 2) con la
   regla operativa escrita para la próxima feature.

**Lo que NO acepto, por si vuelve:** esto **no es precedente general**. Si en la
próxima feature `critico` los supervivientes se matan y se dan por muertos **por
una segunda campaña paralela**, el argumento se cae entero. Lo que aquí salva la
campaña no es que el defecto sea pequeño: es que **el paso decisivo se hizo en
serie**. Mientras F-041 no esté, esa es la condición.

**Y confirmo lo otro que preguntabas: T29-T31 NO bloquean.** El humano resolvió
DA-3 por su opción B el 2026-08-25 y `requirements.md` recoge que el bloque I
deja de ser condición de cierre. Lo que bloquea es lo de H4: que tres documentos
sigan diciendo lo contrario.

## Hallazgos abiertos (numerados y accionables)

| # | Hallazgo | Fichero y sitio |
|---|---|---|
| **H1** | **Los 52 supervivientes tienen su análisis literalmente en `PENDIENTE`**: 52 encabezados `#### Análisis (PENDIENTE del implementer)` y 104 apariciones de la palabra, ninguna completada, y sin puntero a dónde vive el análisis. C4 bis lo exige completado. El análisis **existe y es bueno** en `impl_F-006_detalle.md`: falta traerlo o enlazarlo | `progress/mutacion_F-006.md`, las 52 secciones |
| **H2** | **`impl_F-006.md` se contradice a sí mismo.** §2 «Evidencias» dice 2305 tests (son 2473), 1 línea de cobertura (son 33), 466,09 s (son 603,92) y **«Mutación: NO MEDIDO, a propósito»**; §1 marca **T41 «pendiente y no declarable»** y §4 sigue diciendo que hasta F-041 no se declara ningún número. Solo §9 está al día. Falta además el **nº de workers** (6), que C4 bis exige literalmente: la palabra no aparece ni una vez en el informe ni en sus 5768 líneas de anexo | `progress/impl_F-006.md` §1 (filas T41, T42), §2 entera, §4 entera |
| **H3** | **`tasks.md` no refleja el árbol.** T41 y T42 están `[ ]` estando **hechas** (commit `e89f71f F-006 T41: …`, e `init.sh` exit 0 verificado). T29-T31 `[ ]` a secas cuando el bloque I está entregado; T32-T34 `[ ]` cuando `impl_F-006.md` §1 ya las da entregadas a F-034; T38 `[ ]` sin la anotación de entrega a `mcp-bbdd` que su propia cláusula de escape exige. Menor: `143fa07` y `4d336fb` van etiquetados `F-006 T42:` y son trabajo de T41 | `specs/F-006-mcp-azure/tasks.md` líneas 255-271, 311, 356-360 |
| **H4** | **La spec le promete a F-034 un mecanismo que no existe.** Verificado: sin `revocar_en` en `grants.py:24`, `PG_REVOKE_FUERA_DE_CONSUMO` en ningún fichero, `settings.py:81` con los nueve esquemas. Pero `requirements.md` marca **R30 «vigente»**, **R31 «vigente: se construye y se prueba»** y **R33 «vigente»**; `design_detalle.md` §11.4 dice que se entrega «el mecanismo de `REVOKE` **construido y probado**»; y la ficha de **F-034** en `BACKLOG.md` y `features.json` dice que recibe «los `REVOKE` que F-006 deja **CONSTRUIDOS Y APAGADOS**». Si F-006 cierra hoy, F-034 arranca buscando algo que no está, con su spec diciéndole que sí | `requirements.md` R30/R31/R33; `design_detalle.md` §11.4; `BACKLOG.md` y `harness/features.json`, ficha de F-034 |

## Qué falta para APROBADO

1. **Completar los 52 análisis** de `progress/mutacion_F-006.md`, o —si el humano
   acepta la automejora del §7 del anexo— poner en su cabecera el puntero exacto
   a la sección de `impl_F-006_detalle.md` donde vive cada uno.
2. **Poner al día `impl_F-006.md`**: §2 con los cuatro números reales **más el
   nº de workers (6)**, §1 con T41 y T42 en ✅, y §4 reescrita —hoy dice lo
   contrario de lo que pasó—. El fichero está en 219/220: §4 entera es lo que
   sobra y paga el arreglo.
3. **Marcar `tasks.md`**: T41 y T42 `[x]`; T29-T31 y T32-T34 con su marca de
   entrega a F-034; T38 anotada como entregada a `mcp-bbdd`.
4. **Deshacer la promesa falsa a F-034**: enmendar R30/R31/R33 igual que R32/R34,
   corregir `design_detalle.md` §11.4 y la ficha de F-034 para que digan que el
   mecanismo **no** se construyó. (O construir T29-T31 aquí, si el humano lo
   prefiere; entonces lo que sobra es la enmienda.)

**No verificable desde el árbol, y así queda escrito**: que `_meta` sirva hoy la
versión 9 (exige la base), los `ensure_ascii` contra la base real —verifiqué sus
premisas—, T37 en `azure-apps`, y las `MANUAL` T19, T27, T32-T34, T38 y T39.

## Evolución de las rondas

| # | Veredicto | Eje |
|---|---|---|
| 1-15 | 3 APROBADO, 12 RECHAZADO | Fichas falsas, guardianes verdes sobre afirmaciones falsas, campañas caducadas |
| 16 | **RECHAZADO** | La puerta de mutación no medía nada: base roja y `returncode != 0` contado como muerto |
| 17-19 | (sin veredicto) | Arnés 1.7.7 arregla la campaña; 52 supervivientes resueltos: 49 muertos, 3 equivalentes |
| **20** | **RECHAZADO** | **La campaña ya es válida y lo he verificado. Bloquea el papeleo, no el código** |

Diagnóstico de las veinte: *el problema nunca han sido los datos, sino los
instrumentos que decían que los datos estaban bien*. Vuelta de tuerca de esta
pasada: arreglado el instrumento, lo que miente es **el informe que cuenta lo
que el instrumento midió**.

**Automejora propuesta y no aplicada** ([§7 del anexo](review_F-006_detalle.md)):
que C4 bis acepte un **puntero al fichero donde vive el análisis** de los
supervivientes cuando no quepa en el informe generado — hoy obliga a rellenar 52
secciones a mano en un fichero de la herramienta, que es justo el trabajo que
nadie hace y por eso se queda en `PENDIENTE`.
