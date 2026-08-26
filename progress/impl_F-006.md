<!-- progress/impl_F-006.md -->
# F-006 · Informe de implementación (resumen)

> **La bitácora íntegra vive en [`impl_F-006_detalle.md`](impl_F-006_detalle.md)**:
> trazas de fase RED, salidas de comandos y el razonamiento tarea a tarea, dieciséis
> pasadas de review incluidas. Este fichero es el **índice de entrada**: estado por
> tarea, cifras medidas, supervivientes de mutación y deuda. Los enlaces `L#` apuntan
> a la línea del anexo.

**Qué hace F-006.** Publica en `_meta` la **capa semántica** del datamart —qué
significa cada objeto y cada columna, y qué reglas hay que respetar para leerlo— para
que cualquier agente conectado por MCP construya sus propios casos de uso. Rama
`feature/F-006-mcp-azure`. Rigor `critico`.

---

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
| **T15** | DDL del contrato `_meta` (3 tablas + `v_diccionario`) | ✅ hecha | L1138 |
| **T16** | Constructores puros + 2 métodos del cliente | ✅ hecha | L1197 |
| **T17** | `PublicarDiccionarioStep` en el pipeline | ✅ hecha | L1255 |
| **T18** | Comando `publicar-diccionario` | ✅ hecha | L1302 |
| **T19** | Publicar contra la BBDD real (`MANUAL`) | ✅ **ejecutada** 2026-08-21 | L3496 |
| **T20** | `compras.yaml` | ✅ hecha | L1371 |
| **T21** | `retenciones.yaml` | ✅ hecha | L1371 |
| **T22** | `maestro.yaml` (4 objetos) | ✅ hecha | L1973 |
| **T23** | `stg.yaml` (10 objetos) | ✅ hecha | L2010 |
| **T24** | `aux.yaml` (1) y `_meta.yaml` (7) | ✅ hecha | L2062 / L2138 |
| **T25** | `raw.yaml` (31 fichas de objeto) | ✅ hecha | L2210 |
| **T26** | Comando `check-diccionario` (R28) | ✅ hecha | L3300 |
| **T27** | Chequeo contra la base real (`MANUAL`) | ✅ **ejecutada**, recuento de la 2ª pasada **incompleto** | L3523 / L3547 |
| **T28** | Regla en `docs/CONVENTIONS.md` | ⬜ **pendiente** | — |
| **T29** | `build_readonly_grant_statements(revocar_en=…)` | ⬜ **pendiente** (no existe en código) | — |
| **T30** | `PG_REVOKE_FUERA_DE_CONSUMO` en settings | ⬜ **pendiente** (no existe) | — |
| **T31** | `DEFAULT_CONSUMPTION_SCHEMAS` a los siete | ⬜ **pendiente** (siguen los nueve) | — |
| **T32** 🔏 | Verificar que Power BI no lee de `stg`/`raw` | ➡️ **entregada a F-034** (2026-08-25) | L4719 |
| **T33** 🔏 | Aplicar los `REVOKE` (solo si T32 sale limpia) | ➡️ **entregada a F-034**: DA-3 se resuelve = B | — |
| **T34** 🔏 | Comprobar que Power BI sigue refrescando | ➡️ **entregada a F-034** | — |
| **T35** | `runbook_postgres_azure.md` — firewall | ⬜ **pendiente** (el runbook existe, de F-005) | — |
| **T36** | Sección en `docs/ARCHITECTURE.md` | ⬜ **pendiente** | — |
| **T37** | `azure-apps/datamart_seg_anual.md` | ⬜ **pendiente y obligatoria**: cambió lo que se expone | L4235 |
| **T38** 🔏 | Firewall del entorno del MCP | ⛔ **bloqueada**: ese entorno no existe todavía | — |
| **T39** | Ejecutar las 18 preguntas | ✅ ejecutada 2026-08-22 → `progress/bateria_F-006.md` | §5 |
| **T40** | Corregir lo que la batería delató y republicar | ✅ hecha 2026-08-25 | L4475 |
| **T41** | Campaña de mutación del rigor `critico` | ⬜ **pendiente y no declarable**: ver §4 (feature F-041) | L4375 |
| **T42** | `bash harness/init.sh` en verde | ✅ verde (2025 tests) — reejecutable al cierre | L4728 |
| **T43** | Registrar la deuda y decidir con el humano | ◐ **registrada** (§6); la decisión es del humano | tasks.md §Deuda |

**T32, T33 y T34 entregadas a F-034** el 2026-08-25 por decisión del humano («del BI olvídate»): DA-3 queda resuelta por su opción B y los `REVOKE` se quedan construidos y apagados. Ya no bloquean el cierre.
T41 (mutación) sigue dependiendo de **F-041**.

---

## 2 · Evidencias de la última medición (2026-08-25, tras T40)

| Evidencia | Valor | Comando |
|---|---|---|
| Tests | **2290 pasados**, 125 saltados, **0 fallos** (2026-08-26, tras la 17ª pasada) | `bash harness/init.sh` |
| Cobertura de líneas cambiadas | **N/A**: F-006 no cambia líneas Python de producción frente a `dev` (antes 98,0 %, 1117/1140) | línea `PUERTA COBERTURA` |
| Tiempo de la suite | **342,92 s** (5 min 43 s) bajo `coverage`; 465,77 s en una pasada con carga | ídem |
| Mutación | **NO MEDIDO, a propósito** — ver §4 | — |
| Diccionario | **versión 9 en el árbol, SIN publicar**; `_meta` sirve la **8** (103 objetos, 798 columnas, 16 reglas, 29 filas de contexto, hash `86651c493cb7`) | `publicar-diccionario`, pendiente del humano |
| Biyección publicado ↔ árbol | **102 de 103**; única huérfana `cierre.v_pbi_planif_vs_real` (deuda previa de `build-cierre`) | `check-diccionario` |
| Relaciones | **77 unen, 2 con cobertura escasa, 0 que NO unen, 17 sin comprobar, 2 con un extremo inexistente** | `check-relaciones --todos` |
| Superficie de consumo | **46** objetos (bajó de 48 al retirar dos vistas inconsultables) | `cobertura_columnas` |
| Trinquete `pendientes` | **0**, desde 98 | `PENDIENTES_MAX` |

Progresión histórica de la suite: 1052 → 1133 → 1171 → 1496 → 1985 → **2025** tests.

---

## 3 · Fase RED

Hubo fase RED **en todas las tandas**, con la traza del fallo pegada antes de existir
el código. Las trazas están en el anexo:

| Tanda | Traza |
|---|---|
| T3 a T8 (bloque A) | L28–L165 |
| T9 a T11 (bloque B) | L192–L300 |
| T12 a T14 (bloques C y D) | L323–L413 |
| T15 a T18 (bloque E) | L1140–L1311 |
| Los 10 defectos de la 1ª review | L535–L913 (cada uno con su RED) |
| Arrastres tras el APROBADO | L1012–L1062 |
| T40 (`relaciones_sql.py`) | **L4675–L4704** |

La RED de T40 es la más significativa: el test que sostenía la afirmación falsa del
98 % **falló primero** al corregir la ficha, y esa es la prueba de que la guardaba.

---

## 4 · Mutación: por qué no hay número, y los supervivientes analizados

**Los números de mutación de las tandas anteriores NO son evidencia** (L501, L4377).
La campaña corre en un `git worktree` con HEAD detached, donde
`test_f015_r12_la_rama_actual_se_lee_de_git` falla siempre; con `-x` la suite para ahí
y `harness/mutacion.py` cuenta **cualquier `returncode != 0` como mutante muerto**. La
suite estaba roja antes de mutar nada. Control del reviewer: el mismo worktree **sin
mutar** da el mismo fallo. Quedan como registro de lo declarado, no como prueba:
112/112 · 132/132 · 166/166 · 254/254.

**Decisión declarada**: hasta que **F-041** esté hecho no se declara ningún número de
mutación. `harness/mutacion.py` es del arnés y no se ha tocado.

### Supervivientes analizados

| Superviviente | Veredicto | Anexo |
|---|---|---|
| `frozen=True → False` en `Columna` (`diccionario.py:173`) | **test añadido** (`MINIMOS_FIJADOS` + `test_f006_supervivientes.py`) | L2409, L2452 |
| `frozen=True → False` en `Relacion` (`diccionario.py:189`) | **test añadido**, misma tanda | L2411, L2454 |
| `MINIMOS_TEXTO["grano"] 20→21` (`:137`) | **test añadido** tras un primer arreglo fallido (el test se movía con lo que vigilaba) | L2412, L2433 |
| `MINIMOS_TEXTO["ejemplo_pregunta"] 20→21` (`:140`) | **test añadido**, mismo caso | L2410, L2433 |
| `and → or` en `diccionario_sql.py:297` | **test añadido**, verificado a mano dos veces (16ª y 17ª): MUERTO por los tres casos de cadena | **L4395**, L4790 |

Los cuatro primeros llegaron como «timeouts» y **eran supervivientes**: un timeout es
un mutante **sin evaluar**, nunca uno muerto. Ninguno es equivalente. Hallazgos de
arnés asociados, no aplicados por no tocar `harness/`: la campaña deja mutantes vivos
en `__pycache__` (falso verde posible) y dejó 16 worktrees huérfanos (L2458, L2491).

---

## 5 · Batería de aceptación (T39, 2026-08-22, versión 6 publicada)

| Veredicto | Nº | Preguntas |
|---|---|---|
| RESPONDIDA | 11 | P1, P2, P6, P7, P10, P11, P13, P14, P15, P16, P18 |
| RESPONDIDA CON DUDA | 4 | P3, P5, P8, P12 |
| NO RESPONDIDA | 1 | P9 |
| RECHAZADA CORRECTAMENTE | 2 | P4, P17 |

Veredicto global: *«el diccionario no está completo, pero le falta poco y lo que le
falta es identificable»*; 4 de 12 hallazgos bloqueantes, ninguno exige reescribirlo.
**T40 corrigió los cinco encargos**, pero **la batería NO se ha vuelto a ejecutar
contra la versión 8**: que las fichas ya no mientan no demuestra que las respuestas
salgan bien. Detalle en `progress/bateria_F-006.md`.

---

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

**Deuda técnica medida, sin arreglar aquí (son de otras features):**
- **`mart.fact_seguimiento_mensual` tiene la clave rota** (T27): 8.778 claves duplicadas
  / 17.556 filas, siempre exactamente dos. Causa: 22 obras con dos fases con el mismo
  `ano`/`mes` en Sigrid, de las que **9** duplican en el fact. Efecto: `SUM` doblado y
  fan-out; y la detección de cardinalidades **derivaba la unicidad de esa clave**, así
  que las relaciones al fact se validaron sobre una premisa falsa → **F-042** (39,07 M€
  de más en 8 obras, alimentando KPI de Power BI). Corregida la ficha, no el build (L3567).
- **`build-compras` y `build-retenciones` no registran paso en `_meta.etl_runs`**: su
  frescura no es consultable por SQL. Dicho dentro de `R-FRESCURA-MANUAL` (L474).
- **`cierre.v_pbi_planif_vs_real`**: el repositorio la crea, la base no la tiene porque
  `build-cierre` no se ha relanzado. Deja 2 relaciones sin comprobar.
- **4 relaciones sin comprobar a 90 s** (objetos que `R-COSTE-CONSULTA` declara caros),
  contadas como «no lo sabemos», nunca como OK (L4662).
- **`aux.periodificacion_partida` se crea vacía por diseño** → `mart.v_fact_periodificado`
  no periodifica nada; `consumo_recomendado: false` con motivo.
- **Intragrupo**: el mayor proveedor de la empresa es la propia empresa (23,8 M€, más
  del doble que el segundo) más UTEs. Tumba cualquier ranking de facturación; exige
  modelar el grupo → **F-045**/backlog, no es de esta feature (L4634).
- Los 39 «sin contradicción» de `check-unicidad` **no tienen la clave demostrada**: los
  datos de hoy no la contradicen, que es otra cosa (L3634).

**Lo que la puerta NO comprueba, dicho sin adornos** (L1103): que el `grano` sea cierto,
que `clave_negocio` sea la clave de verdad (y una clave reducida **desarma** la
comprobación de fan-out), y que el `significado` de una columna sea cierto. Solo lo
cazan la revisión humana y la batería.

**Fuera del alcance entregado**: T28 a T38 (regla de convenciones, los `REVOKE` y su
verificación con Power BI, documentación de bloque J y firewall del entorno MCP) y T41.
El objetivo del humano —«un MCP que use cualquiera desde cualquier puesto»— **no está
cumplido**: hoy el MCP corre en el puesto de pgris. Lo construido es la capa semántica,
que era el prerrequisito, no el despliegue.

---

## 7 · 17ª pasada: los cuatro hallazgos del review (2026-08-26, anexo **L4767+**)

| # | Hallazgo | Estado | Qué se hizo |
|---|---|---|---|
| **H2** | Mutante `and→or` en `diccionario_sql.py:297` | **CERRADO** | Ya moría desde `3ec962c`; verificado aplicando el mutante. Añadidos los otros dos casos de cadena (solo espacios y blancos mezclados): cualquiera lo mata solo |
| **H3** | Guardián de coherencia, tres vías | **CERRADO** | Las tres, cerradas desde `3ec962c` y verificadas hoy. Seguía abierta la **clase**: la vigilancia del plegado era una lista de dos ficheros a mano. Sustituida por criterio derivado (`ast` + campos de prosa de las dataclases); RED con **22 comparaciones crudas** en 4 ficheros, las 22 reescritas |
| **H4** | «22 obras» mal atribuido | **CERRADO** | Barrido del diccionario **cargado**: 7 apariciones, las 7 bien atribuidas ya desde `3ec962c`. Añadida la guarda que faltaba: **donde se nombra el 22 hay que nombrar el 9** |
| **H5** | Remisión falsa al agente | **CERRADO** | Era el único abierto de verdad. Corregido en los dos sitios y añadido el criterio: los números que una remisión atribuye a una consulta tienen que estar declarados junto a ella |

**Antes de la 18ª pasada**: el resumen `review_F-006.md` se escribió el 2026-08-25
copiando el veredicto de la 16ª **sin reverificar el árbol**, y esa pasada y sus
arreglos viajan en el mismo commit (`3ec962c`): por eso H2, H3 y H4 constaban abiertos
estando ya cerrados.

**Parada declarada**: el diccionario sube a **versión 9 y NO se publica** —
`publicar-diccionario` escribe en Azure y esa autorización es del humano; hasta que la
dé, `_meta` sirve la 8 **con la remisión falsa dentro**—. Tampoco se han ejecutado
`check-diccionario`, `check-unicidad` ni `check-relaciones`, que exigen base, ni la
campaña de mutación (RM1: la lanza el humano con el árbol quieto).
