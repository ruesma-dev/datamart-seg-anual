<!-- progress/impl_F-006.md -->
# F-006 · Informe de implementación (resumen)

> **La bitácora íntegra vive en [`impl_F-006_detalle.md`](impl_F-006_detalle.md)**: trazas
> de fase RED, salidas de comandos y el razonamiento tarea a tarea, dieciocho pasadas
> incluidas. Aquí van el estado por tarea, las cifras medidas, los supervivientes de
> mutación y la deuda; los enlaces `L#` apuntan a la línea del anexo.

**Qué hace F-006.** Publica en `_meta` la **capa semántica** del datamart —qué significa
cada objeto y cada columna, y qué reglas hay que respetar para leerlo— para que cualquier
agente conectado por MCP construya sus casos de uso. Rama `feature/F-006-mcp-azure`,
rigor `critico`.

## 1 · Estado por tarea (T1–T43 de `specs/F-006-mcp-azure/tasks.md`)

| Tarea | Qué es | Estado | Dónde en el anexo |
|---|---|---|---|
| **T1** | Cerrar DA-1 a DA-6 | ✅ hecha | L16 |
| **T2** | `rigor: critico` en la ficha | ✅ hecha | L16 |
| **T3** | `domain/diccionario.py` — entidades y `validar()` | ✅ hecha | L33 |
| **T4** | `derivar_avisos()` + R9/R11/R12 | ✅ hecha | L58 |
| **T5** | Frescura R13/R14 contra el pipeline real | ✅ hecha | L82 |
| **T6** | `domain/inventario.py` — inventario y cobertura | ✅ hecha | L106 |
| **T7** | `cargador_yaml.py` + `hash_fuente` | ✅ hecha | L125 |
| **T8** | La puerta real sobre el repositorio | ✅ hecha | L152 |
| **T9** | Las doce reglas duras en `00_global.yaml` | ✅ hecha (hoy **16**) | L192 |
| **T10** | Convenciones, ejes, `ocultar`, 9 esquemas | ✅ hecha | L246 |
| **T11** | Las 18 preguntas de la batería | ✅ hecha | L284 |
| **T12** | `mart.yaml` — 2 tablas de hecho | ✅ hecha | L323 |
| **T13** | Las 11 vistas de `mart` | ✅ hecha | L367 |
| **T14** | `cierre.yaml` — 1 tabla, **8** vistas (no 6), 3 funciones | ✅ hecha | L402 |
| **T15** | DDL del contrato `_meta` (**4 tablas** + `v_diccionario`; la tabla decía 3 — §8) | ✅ hecha | L1138 |
| **T16** | Constructores puros + 2 métodos del cliente | ✅ hecha | L1197 |
| **T17** | `PublicarDiccionarioStep` en el pipeline | ✅ hecha | L1255 |
| **T18** | Comando `publicar-diccionario` | ✅ hecha | L1302 |
| **T19** | Publicar contra la BBDD real (`MANUAL`) | ✅ **ejecutada** 2026-08-21 | L3496 |
| **T20** | `compras.yaml` | ✅ hecha | L1371 |
| **T21** | `retenciones.yaml` | ✅ hecha | L1371 |
| **T22** | `maestro.yaml` (4 objetos) | ✅ hecha | L1973 |
| **T23** | `stg.yaml` (10 objetos) | ✅ hecha | L2010 |
| **T24** | `aux_.yaml` (1) y `_meta.yaml` (**8**, no 7 — §8) | ✅ hecha | L2062 / L2138 |
| **T25** | `raw.yaml` (31 fichas de objeto) | ✅ hecha | L2210 |
| **T26** | Comando `check-diccionario` (R28) | ✅ hecha | L3300 |
| **T27** | Chequeo contra la base real (`MANUAL`) | ✅ **ejecutada**, recuento de la 2ª pasada **incompleto** | L3523 / L3547 |
| **T28** | Regla en `docs/CONVENTIONS.md` | ✅ hecha 2026-08-26 (`33808dc`) | L5017 |
| **T29** | `build_readonly_grant_statements(revocar_en=…)` | ⬜ **pendiente** (no existe en código) | — |
| **T30** | `PG_REVOKE_FUERA_DE_CONSUMO` en settings | ⬜ **pendiente** (no existe) | — |
| **T31** | `DEFAULT_CONSUMPTION_SCHEMAS` a los siete | ⬜ **pendiente** (siguen los nueve) | — |
| **T32** 🔏 | Verificar que Power BI no lee de `stg`/`raw` | ➡️ **entregada a F-034** (2026-08-25) | L4719 |
| **T33** 🔏 | Aplicar los `REVOKE` (solo si T32 sale limpia) | ➡️ **entregada a F-034**: DA-3 se resuelve = B | — |
| **T34** 🔏 | Comprobar que Power BI sigue refrescando | ➡️ **entregada a F-034** | — |
| **T35** | `runbook_postgres_azure.md` — firewall (6 bis y 6 ter) | ✅ hecha 2026-08-26 (`4e180c0`) | L5017 |
| **T36** | Sección en `docs/ARCHITECTURE.md` | ✅ hecha 2026-08-26 (`cf12d9a`) | L5017 |
| **T37** | `azure-apps/datamart_seg_anual.md` | ✅ **hecha 2026-08-22**, commit `2e9bee8` de `azure-apps` (constaba pendiente: §8) | L5083 |
| **T38** 🔏 | Firewall del entorno del MCP | ⛔ **bloqueada**: ese entorno no existe todavía | — |
| **T39** | Ejecutar las 18 preguntas | ✅ ejecutada 2026-08-22 → `progress/bateria_F-006.md` | §5 |
| **T40** | Corregir lo que la batería delató y republicar | ✅ hecha 2026-08-25 | L4475 |
| **T41** | Campaña de mutación del rigor `critico` | ✅ **hecha**: campaña completa y **válida**, commit `e89f71f` (256 mutantes, 52 supervivientes resueltos — §4) | L4375 |
| **T42** | `bash harness/init.sh` en verde | ✅ **verde**: exit 0, 2.473 pasados, 128 saltados, 0 fallos; reverificado por el reviewer en la 20ª pasada | §2 |
| **T43** | Registrar la deuda y decidir con el humano | ◐ **registrada** (§6); la decisión es del humano | tasks.md §Deuda |

**T32, T33 y T34 entregadas a F-034** el 2026-08-25 por decisión del humano («del BI olvídate»): DA-3 queda resuelta por su opción B y los `REVOKE` se quedan construidos y apagados. Ya no bloquean el cierre.
**T41 está hecha** y sus 52 supervivientes resueltos (§4); lo que va a **F-041** es la limitación de la campaña paralela, no la campaña. **Toda esta tabla se ha reverificado fila a fila contra el árbol** (§8), y el reviewer la reverificó otra vez en la 20ª pasada.

## 2 · Evidencias de la última medición (2026-08-26, reverificadas por el reviewer en la 20ª pasada)

| Evidencia | Valor | Comando |
|---|---|---|
| Tests ejecutados y resultado | **2.473 pasados, 128 saltados, 0 fallos**, exit 0. Medición del reviewer sobre este mismo árbol; coincide con la última del implementer | `bash harness/init.sh` |
| Cobertura de líneas cambiadas | **100,0 %** — **33 de 33** líneas cambiadas cubiertas (umbral 80 %, nivel `critico`) | línea `PUERTA COBERTURA` |
| Tiempo de la suite | **603,92 s** (10 min 04 s) bajo `coverage`, en la pasada del reviewer. Sobre el mismo árbol se midieron antes 675,15 s y 1.274,77 s: la diferencia es contención de CPU con otra suite a la vez, no trabajo nuevo | ídem |
| Mutantes generados y supervivientes | **256 generados, 256 evaluados, 204 muertos, 52 supervivientes**, 0 timeouts, 0 sin veredicto. Los **52 resueltos: 49 muertos con tests nuevos y 3 equivalentes** aprobados por el humano — §4 | `python -m harness.mutacion --feature F-006` |
| **Workers de la campaña** | **6** (fila «Workers» del informe). Con ellos el coste real por mutante es 32,7 s × 6 = **196,2 s**, frente a una línea base de ~470 s: coherente, porque el 80 % de los muertos para con `-x` | ídem |
| Diccionario | **versión 9 publicada**: `_meta` la sirve desde la nocturna del 2026-08-26 a las 06:59. Medido en el árbol: hash `72125091cc25`, 103 objetos, 798 columnas, 16 reglas, 29 filas de contexto, 0 pendientes, 46 objetos de consumo, cobertura de columnas 100 % | árbol: `cargar_diccionario` + `filas_*`. Publicación y `check-diccionario`: **medición del humano**, no verificable desde el árbol (§8) |
| Biyección publicado ↔ árbol | **102 de 103**; única huérfana `cierre.v_pbi_planif_vs_real` (deuda previa de `build-cierre`) | `check-diccionario` |
| Relaciones | **78 unen, 2 con cobertura escasa, 0 que NO unen, 16 sin comprobar, 2 con un extremo inexistente** (medido el 2026-08-26 a las 12:05; una relación más verificada que el día anterior) | `check-relaciones --todos` |
| Superficie de consumo | **46** objetos (bajó de 48 al retirar dos vistas inconsultables) | `cobertura_columnas` |
| Trinquete `pendientes` | **0**, desde 98 | `PENDIENTES_MAX` |

Progresión de la suite: 1052 → 1133 → 1171 → 1496 → 1985 → 2025 → 2290 → 2305 → 2467 →
**2473**. (Aquí llegó a poner 2025, contradiciendo tres pasadas seguidas a la fila
«Tests» de al lado: dato copiado sin contrastar, y la misma causa que el H2 de la 20ª.)

## 3 · Fase RED

Hubo fase RED **en todas las tandas**, con la traza del fallo pegada antes de existir el
código. La más significativa es la de T40: el test que sostenía la afirmación falsa del
98 % **falló primero** al corregir la ficha, y esa es la prueba de que la guardaba.

| Tanda | Traza |
|---|---|
| T3 a T8 (bloque A) | L28–L165 |
| T9 a T11 (bloque B) | L192–L300 |
| T12 a T14 (bloques C y D) | L323–L413 |
| T15 a T18 (bloque E) | L1140–L1311 |
| Los 10 defectos de la 1ª review | L535–L913 (cada uno con su RED) |
| Arrastres tras el APROBADO | L1012–L1062 |
| T40 (`relaciones_sql.py`) | **L4675–L4704** |
| T28, T35 y T36 (18ª pasada) | **L4953–L5015**: 10 rojos de 14 antes de tocar un documento, y el verde después |

## 4 · Mutación: la campaña, sus números y su limitación

**Campaña completa y VÁLIDA**, la primera de F-006 (commit `e89f71f`, informe en
`progress/mutacion_F-006.md`): **256 mutantes generados y evaluados, 204 muertos, 52
supervivientes, 0 timeouts, 0 sin veredicto**, sobre 3.126 líneas de 8 ficheros, con **6
workers**, en 8.368,3 s; SHA medido `99e2335`, y ninguno de esos 8 ficheros ha cambiado
desde entonces. El reviewer recalculó alcance y nº de mutantes por su cuenta en la 20ª
pasada: **coincide exacto**.

**Los 52 supervivientes, resueltos: 49 muertos con tests nuevos** —ni una línea de
producción tocada— **y 3 equivalentes** demostrados y **aprobados por el humano el
2026-08-26**. Los 52 análisis están completados, cada uno con el puntero a su traza, en el
propio informe de la campaña; el reparto y las fases RED, en §9 y en el anexo (L5136,
L5355, L5463, L5576, L5626). Lo que se declara muerto por los tests nuevos se reverificó
**EN SERIE**, nunca por una segunda campaña paralela.

**LA LIMITACIÓN, declarada, medida y con dueño** — `progress/control_mutacion_F-006.md`:
la campaña paralela produce **falsos muertos** (uno confirmado, `inventario.py:234
[not]`, perseguido hasta matarlo), así que **204 muertos no es lista cerrada y 52 es un
SUELO**; la muestra de control —12 de los 204, reevaluados en serie— dio **0 cambios de
veredicto**, que no descarta una tasa baja. Fichada en **F-041**. Y los números de las
tandas anteriores —112/112, 132/132, 166/166, 254/254— **siguen sin ser evidencia**:
corrían con la base roja, contando cualquier `returncode != 0` como muerto (L501, L4377).

## 5 · Batería de aceptación (T39, 2026-08-22, versión 6 publicada)

De las 18 preguntas: **11 RESPONDIDAS** (P1, P2, P6, P7, P10, P11, P13-P16, P18), **4 con
duda** (P3, P5, P8, P12), **1 NO respondida** (P9) y **2 rechazadas correctamente** (P4,
P17). Veredicto global: *«el diccionario no está completo, pero le falta poco y lo que le falta
es identificable»*; 4 de 12 hallazgos bloqueantes, ninguno exige reescribirlo. **T40
corrigió los cinco encargos**, pero **la batería NO se ha vuelto a ejecutar contra las
versiones 8 ni 9**: que las fichas ya no mientan no demuestra que las respuestas salgan
bien. Detalle en `progress/bateria_F-006.md`.

## 6 · Deuda declarada (T43) y lo que queda fuera

| Id | Qué | Dueño |
|---|---|---|
| **D1** | Décimo caso de la copia en un docstring (`test_f006_stg_trampas.py:151`); barrer docstrings **no conviene** (falsos positivos) | revisión humana |
| **D2** | Referencia posicional en `config/diccionario/stg.yaml:598` («unas líneas más abajo», son nueve arriba) | implementer |
| **D3** | Recuento a mano en `test_f006_fichas.py:615` («cinco tablas», son seis): hay que **derivarlo** | implementer |
| **D4** | Tres correcciones sin guarda de regresión (`entidad_cif` CLIENTE, familias de columnas excluidas en las 31 de `raw`, `proveedores_obra.cif`) | implementer |
| **D5** | **Zona NO FIABLE**: lo que no se deriva de este repositorio (punto 2 de `R-SIGRID-CON`, y todo lo que dependa de `azure-apps/sigrid_tablas.md`, que ya produjo dos afirmaciones falsas). Fuera de ella, las 47 fichas de consumo están verificadas | **humano** |
| **D6** | Deuda anterior viva: detector de `COALESCE` multifuente, menores 5-7 de la 5ª review, **F-041**, comentarios mentirosos de `sql/stg/06_presupuesto.sql` (F-025), `tables_sigrid.yaml` promete recarga que no gobierna | varios |
| **D11** | La IP del puesto rota cada pocos minutos: la regla de firewall hubo que reescribirla seis veces en una tanda | humano |

**Deuda técnica medida, sin arreglar aquí (es de otras features).** Los siete puntos, con
sus números y su remisión al anexo, están en **L5112** (movidos por la puerta de tamaño):
la **clave rota de `mart.fact_seguimiento_mensual`** (8.778 duplicadas de 17.556 filas →
**F-042**, 39,07 M€ de más en 8 obras que alimentan KPI de Power BI); `build-compras` y
`build-retenciones` sin fila en `_meta.etl_runs`; `cierre.v_pbi_planif_vs_real` en el
repositorio y no en la base; 4 relaciones sin comprobar a 90 s, contadas como «no lo
sabemos» y nunca como OK; `aux.periodificacion_partida` vacía por diseño; el
**intragrupo**, que tumba cualquier ranking de facturación (→ **F-045**); y los 39 «sin
contradicción» de `check-unicidad`, que **no tienen la clave demostrada**.

**Lo que la puerta NO comprueba** (L1103): que el `grano` sea cierto, que
`clave_negocio` sea la clave de verdad (y una clave reducida **desarma** la comprobación
de fan-out), y que el `significado` de una columna lo sea. Solo lo cazan la revisión
humana y la batería.

**Fuera del alcance entregado**: **T29, T30 y T31** (los `REVOKE`, verificados como no
escritos) y **T38** (firewall del entorno del MCP, que no existe). **T41 ya no está en
esta lista: se hizo** (§4). El objetivo del humano —«un MCP que use cualquiera
desde cualquier puesto»— **sigue sin cumplirse**: hoy corre en el puesto de pgris. Lo
construido es la capa semántica, que era el prerrequisito, no el despliegue.

## 7 · 17ª pasada: los cuatro hallazgos del review (2026-08-26, anexo **L4767+**)

**H2, H3, H4 y H5: los cuatro CERRADOS**, con el detalle y las trazas en L4767+. H2 (el
mutante `and→or` de `diccionario_sql.py:297`), H3 (guardián de coherencia) y H4 («22
obras» mal atribuido) ya morían desde `3ec962c` y se verificaron uno a uno; H5 —una
remisión falsa al agente— era el único abierto de verdad. De H3 salió la lección que esta
pasada ha vuelto a aplicar: la vigilancia era **una lista de dos ficheros escrita a mano**
y se sustituyó por un criterio derivado (`ast` + los campos de prosa de las dataclases),
que en RED encontró **22 comparaciones crudas** en 4 ficheros. Y de H4, la guarda de que
donde se nombra el 22 hay que nombrar el 9.

**Antes de la 18ª**: `review_F-006.md` se escribió el 2026-08-25 copiando el veredicto de
la 16ª **sin reverificar el árbol**, y esa pasada y sus arreglos viajan en el mismo commit
(`3ec962c`): por eso H2, H3 y H4 constaban abiertos estando ya cerrados. **Parada de la
17ª, ya levantada**: la versión 9 quedó sin publicar esperando autorización, y **la
publicó la nocturna del 2026-08-26 a las 06:59**, así que la remisión falsa ya no está en
`_meta`. Sigue sin lanzarse la mutación (RM1: la lanza el humano con el árbol quieto).

## 8 · 18ª pasada: T28, T35, T36 y la tabla reverificada (2026-08-26, anexo **L4947+**)

**T28, T35 y T36 escritas con fase RED** (10 rojos de 14 antes de tocar un documento,
L4953), en `tests/test_f006_docs.py`, que no existía. Sus guardianes no comprueban que la
frase esté: **derivan** lo que el documento afirma de la fuente que manda —los comandos
citados, de los `@cli.command` de `main.py`; las tablas del contrato, de los
`CREATE TABLE` de `01_diccionario.sql`—, y ese último destapó el desfase 1.

**La tabla de §1 se ha reverificado fila a fila contra el árbol** (L5040), midiendo con el
cargador real y `grep` **antes** de mirar lo que decía la tabla. Cuatro desfases:

| # | Qué decía | Qué es |
|---|---|---|
| 1 | T15: «3 tablas + `v_diccionario`» | **4 tablas**: `diccionario`, `_reglas`, `_contexto`, `_publicacion`. La cabecera del propio DDL ya decía «CUATRO» |
| 2 | T24: `_meta.yaml` con 7 objetos | **8** |
| 3 | T37 «pendiente y obligatoria» | **hecha el 2026-08-22**, commit `2e9bee8` de `azure-apps` |
| 4 | `_meta` sirve la versión 8, hash `86651c493cb7` | **versión 9, hash `72125091cc25`**, publicada por la nocturna |

Los desfases 1 y 2 tienen el mismo origen: `diccionario_contexto` llegó después de que se
escribieran esos textos y nadie los recontó. El resto de las filas —incluidas T29, T30 y
T31, que **siguen pendientes de verdad**— resultó exacto; se corrigió además la línea de
progresión de la suite (§2).

**No verificable desde el árbol, y así queda escrito**: que `_meta` sirva hoy la 9 (exige
base; el hash del árbol coincide con el que reporta el humano, pero la medición es suya)
y todo lo `MANUAL` —T19, T27, T32-T34, T38, T39—, que no se reetiqueta.

**Hallazgo declarado y NO arreglado** (fuera del encargo, toca código): `main.py:434`
dice «las tres tablas del diccionario» y son cuatro, por lo mismo que el desfase 1.

## 9 · 19ª pasada: los 31 supervivientes baratos de la 2ª campaña (2026-08-26, anexo **L5333+**)

**31 de los 52 muertos, cero equivalentes, solo con tests** (ni una línea de producción: todos eran huecos de test, no defectos). Los **20 `frozen`/`slots`** caen con **un barrido** que descubre las 38 dataclasses del paquete en vez de listarlas —una dataclass mutable nueva da 2 rojos ella sola, sin tocar ninguna lista—, que es la lección de la 1ª campaña cobrada por segunda vez: aquellos dos se taparon a mano y el defecto sobrevivió en las doce clases de al lado. Los **11 de constantes** quedan fijados por su EFECTO y no por su valor (el `LIMIT 500` del SQL, el `'30s'` del `SET LOCAL`, 33.33 frente a 33.333, `com9` sí y `com10` no), porque un test que lee la constante se mueve con ella —que es lo que ya le pasa a `test_f006_nombres_fichero.py`, con su propia copia del conjunto—. Los 31 verificados **uno a uno** aplicando el mutante en un worktree: `exit=1` en los 31, trazas en L5333+. `bash harness/init.sh` **en verde**: **2.467 pasados, 128 saltados en 21:14**, cobertura **100 % de 33 líneas cambiadas**. Commits `4d336fb` y `143fa07`. **Cierre (2026-08-26):** los **dos últimos** —`grano` crudo vs. `_texto()` en `cargador_yaml.py:361` y el `<`/`<=` del umbral de cobertura en `relaciones_sql.py:278`, que se quedaron fuera del reparto por descuido del líder y la reevaluación en serie confirmó **vivos**— quedan muertos con tests (secciones 13 y 14 de `test_f006_supervivientes_logica.py`), sin tocar producción, con la fase RED verificada en worktree y `.env` volcado: **52/52 resueltos, 49 muertos y 3 equivalentes**. Detalle y trazas en **L5626+**.
