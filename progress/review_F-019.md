<!-- progress/review_F-019.md -->
# F-019 · Build de `stg.plan_mensual` por tramos — Informe de review

Rama `feature/F-019-plan-mensual-por-tramos` (verificada con
`git branch --show-current`). Revisión de la **Fase B** (T3–T10, el trabajo del
implementer). Fecha: 2026-08-10.

## Veredicto

**APPROVED** — con dos condiciones de cierre que NO son opcionales y que
recaen en el líder y en el humano (ver §Condiciones para marcar `done`).

## Nivel de rigor y puertas que exige

`harness/features.json` declara `"rigor": "critico"` para F-019. Puertas
exigidas por `CHECKPOINTS.md` y su resultado:

| Puerta | Exigido en `critico` | Resultado |
|---|---|---|
| `init.sh` en verde | sí | **[OK]** 379 passed, exit 0 |
| Cobertura de líneas cambiadas | ≥ umbral, `[OK]` con porcentaje | **[OK] 100,0 %** (120/120, umbral 80 %) |
| Fase RED con salida real | sí | **[OK]** trazas pegadas de T3, T4, T5, T6 y T7 |
| Campaña de mutación | totales verificados de forma independiente | **[OK]** 458 líneas / 41 mutantes, recalculados por mí |
| Supervivientes | **cero** sin justificación aceptada | **[OK]** 0 supervivientes |
| Verificaciones MANUAL | listadas con comando exacto | **[OK]** en `progress/current.md` §GUION MANUAL |

## Verificación INDEPENDIENTE de la mutación (lo que decide en `critico`)

No me creo el informe: lo recalculé y lo reejecuté.

**1 · Alcance y número de mutantes**, recalculados con `harness.alcance` y
`harness.mutacion.generar_mutantes` (cálculo puro, sin ejecutar la suite):

| Fichero | Líneas (yo) | Líneas (informe) | Mutantes (yo) |
|---|---|---|---|
| `config/settings.py` | 21 | 21 | 2 |
| `etl_sigrid/application/steps/build_stg_step.py` | 205 | 205 | 9 |
| `etl_sigrid/domain/tramos.py` | 125 | 125 | 13 |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | 107 | 107 | 17 |
| **Total** | **458** | **458** | **41** |

Coincide exactamente, incluido el ref base del diff
(`2cb6de76…` = `git merge-base dev HEAD`). El informe no está escrito a mano.

**2 · Comprobación de muerte real.** Como no hay supervivientes que muestrear,
apliqué yo mismo los **10 mutantes vecinos más peligrosos** —los que, de
sobrevivir, dejarían la puerta de disco o la equivalencia sin red— y lancé la
suite completa con cada uno (`pytest -x -q`, mismo criterio que
`EjecutorPytest`). Los diez **MUEREN**:

| Mutante | Qué rompería |
|---|---|
| `build_stg_step.py:317` `>` → `>=` | umbral de la puerta de disco |
| `build_stg_step.py:53` `RAMAS_CON_FILTRO = 2` → `3` | nº de ramas filtradas |
| `build_stg_step.py:86` `if not obras` → `if obras` | tramo vacío compuesto |
| `build_stg_step.py:103` `!=` → `==` | validación del marcador invertida |
| `postgres_client.py:623` `not fila or` → `fila or` | fail-safe de medición |
| `postgres_client.py:623` `or` → `and` | NULL tomado por medición válida |
| `postgres_client.py:101` `<= 0` → `<= 1` | validación de `PG_DISCO_TOTAL_GB` |
| `tramos.py:91` `and` → `or` | corte de tramo |
| `tramos.py:91` `>` → `>=` | frontera del peso máximo |
| `tramos.py:125` `>` → `>=` | detección de obra sobredimensionada |

El árbol de trabajo quedó restaurado y limpio tras la comprobación
(`git status` sin cambios).

## Checkpoints (CHECKPOINTS.md, recorrido completo)

### C1 — El arnés está completo y en verde

- [x] `bash harness/init.sh` termina con exit code 0 (ejecutado por mí).
- [x] Existen `CLAUDE.md`, `harness/features.json`, `specs/SPECS.md`,
      `progress/current.md`, `progress/history.md`, `docs/ARCHITECTURE.md`,
      `docs/CONVENTIONS.md`.

### C2 — El estado es coherente

- [x] Una sola feature `in_progress` (F-019); F-003 está `blocked` esperando
      justamente a esta.
- [x] Rama actual `feature/F-019-plan-mensual-por-tramos`.
- [x] `progress/current.md` describe la sesión activa (F-003 en espera, F-019
      en curso y el guion MANUAL pendiente), sin restos ajenos.
- [x] Ninguna feature pasa a `done` en este trabajo, así que no hay resumen
      que exigir en `history.md` todavía.

### C3 — El código respeta arquitectura y convenciones

- [x] **Dominio puro**: `etl_sigrid/domain/tramos.py` importa exclusivamente
      `collections.abc` y `dataclasses`. Cero infraestructura, cero logging
      (el WARNING de la obra gigante lo emite el step, que es quien puede).
- [x] SQL en su capa: el cambio es solo en `sql/stg/08_plan_mensual.sql`,
      numeración intacta.
- [x] Primera línea con la ruta relativa en los cinco ficheros Python
      tocados y en el de tests.
- [x] Sin `print()`, sin TODO sin contexto, sin secretos, sin dependencias
      nuevas (barrido sobre el diff: único acierto, la palabra «TODO» dentro
      de una frase en castellano de un docstring).
- [x] Semántica Sigrid respetada: la consulta de pesos usa amb 3/7/8/11 y
      pondera la rama master por las posiciones del `planif`, que es lo que
      explota. Cero líneas de lógica de negocio tocadas en el SQL.
- [x] `ruff check` limpio en los cinco ficheros de la feature
      (`All checks passed!`); los 127 avisos de `init.sh` son deuda previa
      del repositorio, ajena a F-019.

### C3 bis — Documentos que entran de fuera

**N/A justificado**: la feature no añade ni modifica ningún fichero de
`docs/referencia/` (comprobado en `git diff dev...HEAD --stat`: los únicos
documentos tocados son `docs/ARCHITECTURE.md`, la spec y `progress/`). No hay
documento externo que barrer.

### C4 — La verificación es real

- [x] Cada requisito AUTO tiene tests trazables y pasan (tabla abajo).
      37 tests `test_f019_*`, 37 passed.
- [x] Los tests no tocan red ni BBDD: barrido sobre `tests/test_f019_tramos.py`
      buscando `psycopg|httpx|requests|socket|urllib|connect(` → **cero
      coincidencias**. Los dobles están puestos en el límite correcto:
      `ConexionesFalsas` sustituye `PostgresClient.connection` (el cliente real
      se instancia con un DSN a `servidor-inexistente` y nunca lo usa), y
      `PgFalso` **no hereda** de `PostgresClient` a propósito, de forma que un
      método no previsto revienta el test en vez de acabar en una conexión.
- [x] Las verificaciones `MANUAL (humano)` están en `progress/current.md`
      §GUION MANUAL DEL HUMANO, ordenadas 1–5, con el comando exacto del
      pre-check de Azure inline y el resto remitidas al literal de
      `requirements.md`. **Ninguna ejecutada**, que es lo correcto: ningún
      agente ha abierto conexión a BBDD ni a la API en esta feature.

### C4 bis — El rigor declarado se cumple

- [x] `rigor: "critico"` declarado en `harness/features.json`.
- [x] **Fase RED**: el informe trae la salida real del fallo previo para los
      requisitos centrales, con un detalle que merece nota: en T3 no se
      conformó con el `ModuleNotFoundError` (que solo prueba que falta el
      import), sino que puso las firmas sin lógica y pegó la RED de
      comportamiento; y declaró honestamente que 4 tests pasaban por vacuidad.
      Es la fase RED bien entendida.
- [x] **Cobertura**: `[OK] 100,0 % de 120 líneas cambiadas (120/120)`.
- [x] **Mutación**: `progress/mutacion_F-019.md` existe, generado por la
      herramienta, y sus totales los he verificado de forma independiente
      (arriba).
- [x] **Cero supervivientes**. Ninguna sección de análisis en `PENDIENTE`
      (no hay supervivientes que analizar). Merece constar cómo se llegó ahí:
      la primera pasada dejó 4, y el implementer **no justificó ninguno como
      equivalente**; tres se cazaron con tests nuevos y el cuarto
      (`total_bytes <= 0` → `<= 1`), que sí era equivalente de verdad, se
      resolvió **corrigiendo el código** —mover la validación a `total_gb`,
      que es el valor que configura el humano— en vez de escribir una excusa.
      Eso es exactamente lo que la puerta pretende provocar.
- [x] Sección **«Evidencias»** con los cuatro números: 379 passed, 100 % de
      cobertura, 41/41 mutantes muertos y 4,88 s de suite (145,1 s la campaña).
- [x] Ningún punto marcado N/A sin justificación escrita.

### C5 — La sesión se cerró bien

- [x] **Tareas del implementer (T3–T10) todas `[x]`**, con commit por tarea y
      formato `F-019 Tn: ...`: `a0bfd05` (T3), `b23f9da` (T4), `11091e3` (T5),
      `73c0b92` (T6), `15868b5` (T7), `c4da720` (T8), `69e4f04` + `382edc5`
      (T9 y T10).
- [x] **T1, T2 y T11–T14 siguen `[ ]` y eso es lo correcto, no un defecto**:
      `tasks.md` las coloca explícitamente en la Fase A y la Fase C, «humano;
      después del APPROVED del reviewer sobre Fase B», y exigen una BBDD real
      que la regla de hierro de esta feature prohíbe a todo agente. Marcarlas
      habría sido falsificar. Justificación escrita a efectos de la regla del
      N/A: **este APPROVED cubre la Fase B; el cierre de la feature no.**
- [x] Sin ficheros temporales ni artefactos sospechosos sin trackear
      (`git status` limpio).
- [x] `features.json` refleja el estado real (`in_progress`).

Nota sobre el diff: contiene un commit ajeno a la feature, `e056093`
(F-016, del líder, sobre `harness/features.json`). Verificado que no toca
código de F-019 y no altera el alcance de la mutación.

## Cobertura requisito → test / comando

| Req | Tipo | Cubierto por | Estado |
|---|---|---|---|
| R1 | MANUAL-local | `current.md` §1 + 4 consultas literales en `requirements.md` | Pendiente del humano (correcto) |
| R2 | MANUAL-local | `current.md` §2 + checksum y `fingerprint-views` en `requirements.md` | Pendiente del humano (correcto) |
| R3 | AUTO | `r3_plan_de_tramos_particiona_las_obras`, `r3_el_peso_de_cada_tramo_es_la_suma_de_sus_obras`, `r3_sin_obras_no_hay_tramos`, `r3_los_pesos_por_obra_llegan_como_diccionario` | **PASA** |
| R4 | AUTO | 8 tests `r4_*` (máximo respetado, obra gigante en tramo unitario con warning, frontera exacta, máximo configurable, máximo de 1 fila válido, máximo no positivo = error) | **PASA** |
| R5 | AUTO | `r5_plan_determinista`, `r5_las_obras_se_empaquetan_de_mayor_a_menor_peso`, `r5_un_tramo_es_un_valor_inmutable_y_cerrado` | **PASA** |
| R6 | AUTO | `r6_marcador_presente_en_ambas_ramas`, `r6_el_sql_ya_no_contiene_truncate`, `r6_la_logica_de_negocio_del_planif_sigue_intacta` | **PASA** |
| R7 | AUTO | `r7_solo_enteros_en_el_filtro`, `r7_sin_marcador_falla_antes_de_ejecutar`, `r7_un_tramo_sin_obras_no_compone_nada`, `r7_el_sql_real_compuesto_queda_sin_marcadores` | **PASA** |
| R8 | AUTO | `r8_mide_ocupacion_antes_de_cada_tramo`, `r8_medir_ocupacion_suma_todas_las_bases_del_servidor`, `r8_el_porcentaje_de_ocupacion_va_en_gigabytes_binarios`, `r8_un_disco_total_no_positivo_es_un_error_de_configuracion` | **PASA** |
| R9 | AUTO | `r9_supera_limite_aborta_sin_ejecutar_el_tramo`, `r9_aborto_deja_la_tabla_vacia_y_failed_en_meta`, `r9_una_ocupacion_justo_en_el_limite_no_aborta` | **PASA** |
| R10 | AUTO | `r10_medicion_fallida_aborta_no_continua`, `r10_una_medicion_vacia_o_nula_no_se_toma_por_cero` | **PASA** |
| R11 | AUTO | `r11_cada_tramo_en_su_transaccion`, `r11_fallo_de_tramo_limpia_y_para`, `r11_execute_sql_text_abre_una_conexion_por_llamada`, `r11_un_recuento_no_disponible_cuenta_como_cero_filas` | **PASA** |
| R12 | AUTO | `r12_log_por_tramo_con_campos_obligatorios`, `r12_registro_en_meta_por_tramo` | **PASA** |
| R13 | MANUAL-local | `current.md` §2 (T11) + comandos en R13 | Pendiente del humano (correcto) |
| R14 | MANUAL-Azure | `current.md` §3 (T12), pre-check `psql` literal incluido | Pendiente del humano (correcto) |
| R15 | MANUAL-Azure | `current.md` §4 (T13) | Pendiente del humano (correcto) |
| R16 | MANUAL | `current.md` §5 (T14) | Pendiente del humano (correcto) |
| R17 | AUTO | `bash harness/init.sh` (la verificación que declara el propio requisito), ejecutado por mí en verde + barrido de red/BBDD sobre el fichero de tests | **PASA** (ver observación 1) |

## Los puntos de vida o muerte, revisados con lupa

**La puerta de disco (R8–R11) es fail-safe de verdad.** La medición ocurre
dentro del bucle, ANTES de componer y ejecutar el tramo. `PostgresClient.
medir_ocupacion_disco_pct` **propaga** la excepción y además convierte en
`RuntimeError` los dos caminos silenciosos (`fetchone()` vacío y `fila[0] is
None`): no existe rama que devuelva 0 «por si acaso». En el step, cualquier
excepción de la medición cae en `except Exception` → `_abortar_plan_mensual`,
que **vacía la tabla y relanza**. No hay `continue` en ningún camino.

**El caso retorcido que fui a buscar —la medición falla o dispara el límite
ENTRE tramos ya insertados— deja el estado coherente.** `_abortar_plan_mensual`
hace `truncate_table("stg", "plan_mensual")` incondicionalmente, así que lo ya
insertado por los tramos anteriores desaparece: el estado final es «tabla
vacía», que es inequívoco, y nunca «tabla a medias» que un consumidor tome por
completa. Está probado, no razonado: `r9_supera_limite_aborta_sin_ejecutar_el_
tramo` pone el límite en el **segundo** tramo, con el primero ya insertado, y
exige la traza cronológica completa
`["pesos", "truncate", "medicion", "sql", "medicion", "truncate"]`. Ese doble
con traza ordenada es la mejor pieza del test: un vaciado por tramo, una
medición hecha después del tramo o un tramo ejecutado tras superar el límite
cambian la lista y la ponen en rojo. Y la propagación llega arriba: la
`PlanMensualAbortado` la recoge el bucle de sub-pasos, que registra FAILED en
`_meta.etl_runs` y devuelve `StepStatus.FAILED`, de modo que `build_mart` no
llega a ejecutarse (verificado en `r9_aborto_deja_la_tabla_vacia_y_failed_en_
meta`, que ejerce el `run()` completo).

**Una transacción por tramo**: `execute_sql_text` abre su propia
`connection()` por llamada y el test cuenta las aperturas (2 llamadas → 2
aperturas). El pico de temporales de un tramo no se apila con el siguiente,
que es la causa raíz del incidente.

**Equivalencia (R6, R7): el filtro está en las DOS ramas.** Verificado en el
diff del `.sql` con mis propios ojos: `AND pp.obra_id = ANY
(/*F019_FILTRO_OBRAS*/)` aparece en el `WHERE` de `master_planif` (amb 8/11) y
en el de `reales_base` (amb 3/7). Fuera de eso, el diff solo quita el
`TRUNCATE` y añade comentario de cabecera: **cero líneas de lógica de negocio**,
ni una expresión, ni una ventana. La defensa contra la regresión silenciosa es
triple y de verdad: `sql.count(MARCADOR) == 2` en el test estático,
`RAMAS_CON_FILTRO = 2` comprobado en tiempo de ejecución antes de enviar nada
(un fichero al que le falte una sustitución **no se ejecuta**), y el marcador
escrito como comentario SQL, de modo que un fichero sin sustituir ni siquiera
sería SQL válido (`= ANY ()`). Mis mutantes confirmaron que las tres se
comprueban.

**Composición segura**: la lista se construye solo con `str(obra)` tras exigir
`type(obra) is not int` → `TypeError`. El uso de `type(...) is` y no
`isinstance` es deliberado y correcto: `bool` es subclase de `int` y
`ARRAY[True]` no es una lista de obras. No hay ningún camino por el que un
valor no entero llegue a concatenarse. La renuncia a `%(param)s` está bien
argumentada (los comentarios del fichero llevan `%` literales que psycopg
leería como marcadores) y compensada con un blindaje más estricto, no más
laxo.

**Pureza del dominio y determinismo**: `tramos.py` es una función pura sobre
un `Mapping`; el orden lo fija `_clave_de_empaquetado` con desempate por
`obra_id`, así que el plan no depende del orden de iteración del diccionario.
`Tramo` es `frozen=True, slots=True` y hay un test que lo exige —un test que,
además, nació de cazar un superviviente.

## Condiciones para marcar `done` (no las cubre este APPROVED)

1. **T1 y T2** (mediciones en local y confirmación de constantes). La columna
   «medido» de `design.md` §2 sigue **vacía**, y las tres constantes son hoy
   estimaciones. El diseño no depende de esos números —los tres son settings
   con default, con test que lo demuestra— pero el riesgo 3 del propio diseño
   (una obra que no quepa ni sola) solo se descarta midiendo, y hay que
   hacerlo **antes** de T12.
2. **T11 (R13), T12 (R14) y T13 (R15)**: la equivalencia funcional está
   razonada estructuralmente y probada con dobles, pero **no comprobada contra
   datos reales**. En nivel `critico` las verificaciones MANUAL no pueden
   quedar en «pendiente» al cerrar. Orden que no se puede invertir: T1–T2 y
   T11 en LOCAL antes de tocar Azure en T12.

Mientras eso no ocurra, F-019 sigue `in_progress`. No la marques `done`.

## Cambios requeridos

**Ninguno bloqueante.** Tres observaciones menores, para el líder o para la
próxima vuelta; no condicionan el APPROVED:

1. **R17 no tiene test con nombre trazable** `test_f019_r17_*`. No es un
   incumplimiento: el propio requisito declara `bash harness/init.sh` como su
   verificación, y la he ejecutado en verde. Aun así, la ausencia de red/BBDD
   se comprueba hoy por barrido manual del reviewer, no por la suite. Un
   `conftest` que bloquee `socket.socket` durante los tests convertiría eso en
   automático (**propuesta, no cambio pedido**; y sería mejora del arnés
   genérico, no de F-019).
2. **T10 no tiene commit propio**: viaja con T9 en `382edc5`
   (`F-019 T9 y T10: ...`). El formato `F-019 Tn:` se respeta y T10 es
   «ejecutar init.sh», que no produce cambios propios. Se anota por
   literalidad de C5.
3. **`azure-apps/datamart_seg_anual.md`** vive en otro repositorio (commit
   local `df5000e` según el informe): queda fuera de mi verificación desde
   este árbol. El líder debería confirmarlo antes del merge, porque la regla
   de propagación de `CLAUDE.md` es obligatoria.

## Automejora del protocolo (propuesta al humano, no aplicada)

`CHECKPOINTS.md` C5 exige «`tasks.md` con **todas** las tareas `[x]`». En
features cuya spec reparte tareas entre el implementer y el humano —como esta,
donde la Fase C es explícitamente «después del APPROVED del reviewer sobre
Fase B»— esa redacción obliga a marcar N/A algo que no es N/A, sino
*pendiente por diseño*. Propongo matizar C5 así: «todas las tareas asignadas al
implementer `[x]`; las asignadas al humano pueden quedar `[ ]` si la spec las
declara posteriores al review, y el informe debe listarlas como condición de
cierre». Es lo que he hecho aquí a mano, y valdría para cualquier proyecto:
si el humano lo aprueba, va también a `arnes-base`.

---

# Revisión FINAL de F-019 (2026-08-17) — segunda pasada

> La sección anterior (2026-08-10) cubría **solo la Fase B** y se conserva
> íntegra. Esta pasada revisa lo que faltaba: las Fases A y C ejecutadas por
> el humano (T1, T2, T11, T12, T13), las **enmiendas de R13 y R15**, los dos
> arreglos de T13 (`42e128d`, `65c52aa`) y el estado de cierre de la feature.
> Es la revisión que decide si F-019 puede pasar a `done`.

## Veredicto

**CAMBIOS_REQUERIDOS** — por **tres defectos documentales**, ninguno de
código. La ingeniería de F-019 está **aprobada**: el build por tramos es
correcto, está verificado contra datos reales en local y en Azure, y los dos
arreglos de T13 cumplen el rigor `critico`. Lo que impide el `done` es que
**la spec y la memoria no dicen todavía lo que de verdad pasó**. Los tres
arreglos son ediciones de texto en tres ficheros: no hay que tocar código, ni
tests, ni relanzar nada contra BBDD.

## Nivel de rigor y puertas exigidas

`harness/features.json` declara `"rigor": "critico"` para F-019 (leído por mí,
no heredado del informe anterior).

| Puerta (`critico`) | Resultado de esta pasada |
|---|---|
| `init.sh` exit 0 | **[OK]** `398 passed` en 5,78 s, `ENTORNO LISTO` |
| Cobertura de líneas cambiadas | **[OK] 100,0 %** (4/4, umbral 80 %) — línea `PUERTA COBERTURA` |
| Fase RED con salida real | **[OK]** trazas pegadas en `impl_F-019.md` (T3–T7) y en `impl_T13_fixes_f019.md` (§2 A y B) |
| Campaña de mutación, verificada de forma independiente | **[OK]** 38 líneas / 1 mutante, recalculado por mí (abajo) |
| Supervivientes | **[OK]** cero |
| Verificaciones `MANUAL (humano)` con comando exacto y **resultado real** | **[OK]** R1, R2, R13, R14, R15 con números en `current.md`; R16 es constancia para F-003 |

## Verificación INDEPENDIENTE de la mutación

Recalculado con `harness.alcance` y `harness.mutacion.generar_mutantes`
(cálculo puro, sin ejecutar la suite ni escribir en disco):

| Magnitud | Yo | `progress/mutacion_F-019.md` |
|---|---|---|
| Ref base del diff | `659a4a4e…` .. `feature/F-019-plan-mensual-por-tramos` | idéntica |
| Ficheros en alcance | `fingerprint.py` | idéntico |
| Líneas en alcance | **38** | 38 |
| Mutantes generados | **1** | 1 |

El único mutante coincide **literalmente**, operador y texto incluidos:
`fingerprint.py:165`, operador `logico`, `if tipo in TIPOS_NUMERICOS and c not
in COLUMNAS_SUSTITUTAS` pasa a `... or ...`. El informe no está escrito a mano.

**Por qué el alcance es hoy tan pequeño, y por qué eso NO es un agujero.** El
núcleo de F-019 (`build_stg_step.py`, `domain/tramos.py`, `postgres_client.py`,
`config/settings.py`, `sql/stg/08_plan_mensual.sql`) se mergeó a `dev` en
`1e6ea1e` tras el APPROVED de la Fase B, así que ya no aparece en
`git diff dev...HEAD` y la campaña nueva no lo alcanza. Verificado que esos
ficheros están **inalterados** desde entonces (no aparecen en el diff de la
rama contra el merge-base), es decir, son exactamente el código sobre el que
la pasada del 2026-08-10 verificó **458 líneas / 41 mutantes / 0
supervivientes**, incluida la comprobación manual de los 10 mutantes vecinos
más peligrosos. La cobertura de mutación del núcleo sigue vigente; lo que ha
pasado es que el informe generado hoy **pisó** el de entonces (observación
no bloqueante nº 5).

## Recorrido de CHECKPOINTS.md, punto por punto

### C1 — El arnés está completo y en verde

- [x] `bash harness/init.sh` exit 0, ejecutado por mí: 398 tests, cobertura
      `[OK]`, rama correcta, `ENTORNO LISTO`.
- [x] Existen `CLAUDE.md`, `harness/features.json`, `specs/SPECS.md`,
      `progress/current.md`, `progress/history.md`, `docs/ARCHITECTURE.md`,
      `docs/CONVENTIONS.md`.

### C2 — El estado es coherente

- [x] Ninguna feature en `in_progress` (F-019 está `blocked`); `init.sh` lo
      valida y pasa.
- [x] Rama actual `feature/F-019-plan-mensual-por-tramos`.
- [ ] **`current.md` describe la sesión activa: NO del todo.** El §4 (T13)
      termina en «Pendiente: PARADA 1 con el plan de arreglo (propuesto al
      humano)», cuando esa parada **ya se resolvió**: el humano eligió la
      opción A el 2026-08-17 y R15 quedó enmendada y SUPERADA en el commit
      `2d95980`. La memoria contradice a la spec. → **bloqueante nº 3.**
      (Las secciones de F-003, F-004, F-015 y F-020 sí las doy por buenas:
      no son restos, llevan pendientes vivos que sobreviven a esta sesión.)
- [x] Toda feature `done` tiene resumen en `history.md` (comprobado
      programáticamente contra `features.json`: ninguna sin resumen). F-019
      todavía no es `done`, así que no le toca.

### C3 — El código respeta arquitectura y convenciones

- [x] **Dominio sin infraestructura**: `etl_sigrid/domain/tramos.py` sigue
      importando solo `collections.abc` y `dataclasses`.
- [x] **SQL en su capa**: el filtro de tramo vive en
      `sql/stg/08_plan_mensual.sql` (verificado:
      `AND pp.obra_id = ANY (/*F019_FILTRO_OBRAS*/)` en la línea 173, rama
      `master_planif`, y en la 326, rama `reales_base`; **cero** apariciones
      de `TRUNCATE`). Los arreglos de T13 tocan `mart/` y `cierre/`, cada uno
      en su carpeta, sin renumerar nada.
- [x] Primera línea con la ruta relativa en los ficheros nuevos y tocados
      (`fingerprint.py`, `tramos.py`, los tres `tests/test_f019_*.py`).
- [x] Sin `print()`, sin TODO sin contexto, sin secretos, sin dependencias
      nuevas. `python -m ruff check` sobre los seis ficheros de la feature:
      `All checks passed!`.
- [x] **Semántica Sigrid respetada.** Revisado el diff completo del SQL de
      `mart/` y `cierre/`: las 8 sustituciones cambian **solo** la derivación
      de `nombre_mes` (de `to_char(..., 'TMMonth YYYY')` al `ARRAY` de doce
      meses en castellano indexado por `EXTRACT(MONTH ...)`), sin tocar una
      sola expresión de negocio, ni un `JOIN`, ni una ventana. Confirmado
      además que no queda **ninguna** máscara `TM` en `etl_sigrid/`.

### C3 bis — Los documentos que entran de fuera son seguros

**Aplica en esta pasada** (la anterior lo declaró N/A con razón: entonces no
se tocaba `docs/referencia/`). Ahora la rama añade
`docs/referencia/05_caso_obrfasamb_version_duplicada.md`.

- [x] Cabecera con **origen y fecha**: «Origen: investigación interna sobre la
      BBDD local (T11 de F-019) · Fecha: 2026-08-13», más la nota de que se
      redactó directamente en Markdown y no procede conversión.
- [x] **Ningún original ofimático** en el repositorio ni en la historia:
      `git log --all --diff-filter=A --name-only` filtrado por
      `pdf|docx|xlsx|pptx|doc|xls|ppt` devuelve **cero** ficheros.
- [x] **Barrido de datos sensibles ejecutado por mí** sobre el documento
      nuevo, con estos patrones y **cero coincidencias en todos**:
      correos, IPv4, GUID de suscripción o tenant, credenciales
      (`password|passwd|contrase|secret|token|api key|bearer|pwd=|connectionstring|sas=|AccountKey|subscription|tenant`)
      y recursos de Azure (dominios de `postgres.database`, `azurecr`,
      `vault`, prefijos `rg-`). Lo que sí contiene son **códigos y nombres de
      obra** (0694, 0697, 2403576, 2491656) e `ide` de `obrfasamb`: son datos
      de negocio propios, imprescindibles para replicar el caso, y no entran
      en ninguna categoría prohibida por `CLAUDE.md`.
- [x] Nada redactado, luego no hay nada que anotar en cabecera.
- [x] Indexado en `docs/referencia/README.md` (línea 28).

### C4 — La verificación es real

- [x] Cada requisito EARS tiene al menos un test trazable y todos pasan: **48
      funciones** `test_f019_*` (37 del núcleo R3–R12 y 19 de los arreglos de
      T13). Tabla completa abajo.
- [x] Los unit tests **no tocan red ni BBDD**: barrido sobre los tres
      `tests/test_f019_*.py` buscando psycopg, httpx, requests, socket,
      urllib, `connect(`, localhost y `.env`; única coincidencia, un
      **comentario** que explica precisamente que el `.env` del puesto no debe
      decidir el resultado.
- [x] Las verificaciones `MANUAL (humano)` no solo están listadas con su
      comando exacto: **están ejecutadas y con resultado real anotado**, que
      es lo que exige `critico` para cerrar. Ver §Requisitos MANUAL.

### C4 bis — El rigor declarado se cumple

- [x] `rigor: "critico"` declarado en `features.json`.
- [x] **Fase RED con salida real.** `impl_T13_fixes_f019.md` §2 pega el
      `AssertionError` con los 8 ficheros culpables **antes** de tocar un
      solo `.sql`, y el `AttributeError: module … has no attribute
      COLUMNAS_SUSTITUTAS` antes de existir la constante. Y declara con
      honestidad cuáles de los tests pasaban ya por ser de no-regresión (3 en
      A, 2 en B). Eso es fase RED bien entendida, no una frase.
- [x] **Cobertura**: `[OK] 100,0 % de 4 líneas cambiadas (4/4, umbral 80 %,
      nivel critico)`. Las 4 líneas son las de Python; la tarea A es SQL, que
      la cobertura no instrumenta, y su red son los 13 tests de texto sobre el
      árbol de `.sql` — el propio informe lo dice en vez de disimularlo.
- [x] **Mutación**: informe generado por la herramienta, totales verificados
      por mí de forma independiente (arriba), incluido el texto
      original→mutado del único mutante.
- [x] **Cero supervivientes**; ninguna sección en `PENDIENTE`.
- [x] Sección **«Evidencias»** con los cuatro números en los dos informes:
      `impl_F-019.md` (379 passed, 100 % de 120 líneas, 41/41 muertos,
      4,88 s) e `impl_T13_fixes_f019.md` (398 passed, 100 % de 4 líneas,
      1/1 muerto, 6,03 s).
- [x] Ningún punto de este bloque marcado N/A sin justificación escrita.

### C5 — La sesión se cerró bien

- [ ] **`tasks.md` NO refleja el trabajo hecho.** T1, T2, T11, T12 y T13
      siguen `[ ]` **aunque están ejecutadas, con resultado real y con commit
      propio** (`181e01e` T11, `c74b65b` T12, `8582485` T13, entre otros).
      No es N/A justificable: son tareas hechas marcadas como pendientes, y
      un lector de la spec concluiría que la verificación contra datos reales
      nunca ocurrió, que es justo lo contrario de la verdad.
      → **bloqueante nº 1.** (T14 sí puede quedar `[ ]`: por su propia
      redacción es posterior al `done` y pertenece operativamente a F-003.)
- [x] Sin ficheros temporales sospechosos. Los 6 `huella_*.csv` de la raíz
      están sin trackear, que es **lo correcto y lo que manda la spec**;
      constan como evidencia en R15 y en `impl_T13_fixes_f019.md` §5.3.
      (Recomendación no bloqueante nº 6: añadirlos al `.gitignore`.)
- [ ] **`features.json` no refleja el estado real**: F-019 sigue `blocked`, y
      lo que la bloqueaba —las verificaciones manuales del humano— está
      hecho. Lo anoto como **acción de cierre del líder**, no como bloqueante:
      el estado correcto (`done`) depende precisamente de este veredicto, y
      exigirlo antes sería circular.

## Los requisitos MANUAL, contrastados (no los puedo re-ejecutar)

Mi trabajo aquí es comprobar que el rastro es **coherente, completo y con
números que cuadran**. Lo es. Detalle de lo contrastado:

**R1/R2 (T1, T2) — [x].** `design.md` §2 ya no tiene celdas «medido» vacías:
29.091.584 filas finales, 7.532 MB, explosión master 69,05 M posiciones
(×18,4), obra más pesada 298.053 filas. Y la conclusión está escrita: **no
cambia ninguna constante**, porque 298 k es muy inferior a 1 M. Cuadra con los
defaults que leí en `config/settings.py` (`tramo_max_filas=1_000_000`,
`disco_total_gb=32`, `disco_limite_pct=80.0`). Las dos celdas «pendiente»
(derrame y coeficiente) traen el motivo escrito y el dato acabó tomándose en
T11: 12,8 GB sobre 29,4 M filas ≈ **0,47 KB/fila**, cuatro veces mejor que el
1,2 estimado — y el build viejo dio 0,47 también, o sea que la mejora del
troceo es **tiempo y pico**, no derrame. Que el informe diga eso en vez de
apuntarse un tanto es señal de que está medido, no adornado.

**R13 (T11) — [x], contra el criterio ENMENDADO.** He leído la enmienda
entera, no solo su veredicto. La cadena es sólida y, sobre todo, **cae del
lado incómodo primero**: el checksum falló (`ec74147e` contra `c58b928d`), se
declaró FALLO, no se racionalizó, y se abrió una investigación con un plan que
el humano aprobó. Los cuatro puntos del criterio enmendado se sostienen: misma
cardinalidad (29.403.619 en ambos), **ambos** builds reproducibles consigo
mismos por duplicado, `EXCEPT ALL` numérico en las dos direcciones con solo
10.259 filas discrepantes (0,035 %) **todas** de las 2 obras del caso, y
multiconjuntos de valores idénticos por clave. La causa raíz —ventanas
subespecificadas ante `posicion_mes` empatada por versiones master
duplicadas— es **preexistente al troceo** y está documentada con receta de
replicación en `docs/referencia/05_…`, con la decisión de negocio abierta
convertida en F-022 (`pending`, prioridad 12) en vez de resuelta a ojo. Los
números del documento de referencia cuadran con los de `current.md`
(30.860 filas gemelas = 23.111 + 7.749; 16.980 claves).

**R14 (T12) — [x].** `stage` SUCCESS en **6.851,8 s**, `build_plan_mensual`
troceado 5.993,9 s, **60/60 tramos sin un solo aborto**, 29.398.375 filas.
Disco: 23,6 % inicial y **pico 46,55 %**, muy por debajo del límite 80 %; la
puerta no intervino, que es exactamente el resultado que pedía R14. Las cifras
cuadran entre sí: 29.398.375 contra 29.403.619 en local son −5.244, deriva
esperada de un `raw` de Azure del 09-ago contra uno local congelado el 30-jul,
y es justo el motivo por el que T13 se hizo con `--periodo-hasta`.
`build-mart` y `apply-grants` SUCCESS, `timings` con el desglose de los 60
tramos (máximo 293 s). La segunda pasada del 17-ago (build-mart 1.400 s y
build-cierre 1.634 s) es coherente con la primera. El veredicto del paso 9 de
F-005 —el B1ms aguanta— queda justificado con el número, no con una impresión.

**R15 (T13) — [x], contra el criterio ENMENDADO.** Tres iteraciones, y las
tres destaparon algo real: el intento 1 (41 fallos) era despliegue incompleto
en Azure más raws desincronizados; el intento 2 (22 fallos), **tres defectos
de verdad**, dos corregidos en código con rigor `critico` completo y el
tercero (tipos de `compras.*`, donde el desviado era el raw **local**)
resuelto por el humano recreándolo; el intento 3, **0 fallos en estructura,
mart, compras, maestro y planif_vs_real** y 5 residuales reducidos **fila a
fila** a una sola edición en Sigrid. Ese último número es el que hace creíble
el resto y lo he comprobado aritméticamente: 632,74 € × 3 meses = **1.898,22 €**,
que es exactamente la diferencia de los sumatorios. La explicación de por qué
esas filas están en el bloque «cerrado» —`final_version_master` vacío, luego
fallback de fase 0 del cierre, que usa el presupuesto **vivo** por diseño,
documentado en `cierre/02_build_fact.sql` §E— es verificable y no un comodín:
acota la excepción a un mecanismo concreto y nombrado, no a «pequeñas
diferencias aceptables». El criterio enmendado que sale de ahí (igualdad
exacta exigida a estructura y a toda métrica determinista; en el fallback de
fase 0, una discrepancia solo es FALLO si **no** queda explicada fila a fila)
es defendible y, sobre todo, **sigue siendo falsable**.

**R16 — constancia, no bloquea.** F-019 no toca `infra/env/dev.json`
(verificado: no aparece en el diff de la rama) y deja las condiciones
cumplidas. El desbloqueo es de F-003.

## Cobertura requisito → test / evidencia (esta pasada)

| Req | Tipo | Cubierto por | Estado |
|---|---|---|---|
| R1 | MANUAL-local | `design.md` §2 con las 4 mediciones | **HECHO** (2026-08-11) |
| R2 | MANUAL-local | checksum por cubos y huella; línea base anulada y **rehecha** contra worktree `2cb6de7` | **HECHO** (2026-08-13) |
| R3 | AUTO | 4 tests `r3_*` | PASA |
| R4 | AUTO | 7 tests `r4_*` (incluye obra gigante, frontera exacta, máximo configurable) | PASA |
| R5 | AUTO | 3 tests `r5_*` | PASA |
| R6 | AUTO | `r6_marcador_presente_en_ambas_ramas`, `r6_el_sql_ya_no_contiene_truncate`, `r6_la_logica_de_negocio_del_planif_sigue_intacta` | PASA |
| R7 | AUTO | 4 tests `r7_*` | PASA |
| R8 | AUTO | 4 tests `r8_*` | PASA |
| R9 | AUTO | 3 tests `r9_*` | PASA |
| R10 | AUTO | 2 tests `r10_*` | PASA |
| R11 | AUTO | 4 tests `r11_*` | PASA |
| R12 | AUTO | 2 tests `r12_*` | PASA |
| R13 | MANUAL-local | enmienda fechada y `current.md` §2 (cardinalidad, reproducibilidad ×2, `EXCEPT ALL`, huella) | **SUPERADO** (criterio enmendado) |
| R14 | MANUAL-Azure | `current.md` §3: 6.851,8 s, 60/60 tramos, pico 46,55 % | **SUPERADO** |
| R15 | MANUAL-Azure | enmienda fechada y `current.md` §4 (3 iteraciones, 3 defectos, 5 residuales explicados) | **SUPERADO** (criterio enmendado) |
| R16 | MANUAL | constancia; pertenece a F-003 | No bloquea |
| R17 | AUTO | `bash harness/init.sh` verde y barrido de red/BBDD hecho por mí | PASA |
| — (fix locale, colateral de R15) | AUTO | 13 tests `t13_*` de portabilidad | PASA (ver observación 7) |
| — (fix sustitutas, colateral de R15) | AUTO | 6 tests `t13_*` de huella | PASA (ver observación 7) |

## Cambios requeridos (bloqueantes)

Los tres son ediciones de texto. **No hay que tocar código, ni tests, ni
volver a ejecutar nada contra ninguna BBDD.**

1. **`specs/F-019-plan-mensual-por-tramos/tasks.md`: marcar `[x]` T1, T2,
   T11, T12 y T13** (líneas 14, 19, 65, 70 y 77), cada una con su commit o su
   resultado en una línea, como ya se hizo con T3–T10. Severidad **media**;
   bloqueante por C5. Dejar T14 en `[ ]` es correcto y conviene decirlo ahí
   mismo en una nota, para que no parezca olvido.

2. **`specs/F-019-plan-mensual-por-tramos/design.md` §6: enmienda fechada.**
   Hoy §6 «Ficheros que NO se tocan» (líneas 161–166) declara literalmente
   intocables `etl_sigrid/infrastructure/postgres/fingerprint.py` —«se USAN
   como verificación, no se modifican (si se tocaran, dejarían de ser un
   árbitro independiente)»— y «todo `mart/`, `cierre/`…». La rama **toca los
   dos grupos**: `fingerprint.py` (`65c52aa`) y cinco ficheros de `mart/` y
   `cierre/` (`42e128d`). Severidad **media**; bloqueante porque el diseño,
   tal y como está, afirma lo contrario de lo que hay en el árbol, y es
   exactamente el «documento desactualizado que parece vigente» que prohíbe
   `CLAUDE.md`. La justificación ya existe y es buena —el árbitro tenía un
   defecto real de falsos positivos y el locale rompía la portabilidad—, pero
   está escrita en la enmienda de **R15**, no donde vive la restricción.
   Añadir a §6 una enmienda fechada 2026-08-17 que diga: qué se tocó, por qué
   la excepción no anula la independencia del árbitro (la exclusión es de dos
   claves sustitutas nominadas, `fact_id` y `fact_cat_id`, que **siguen** en
   el bloque `estructura`, y los tests de no-regresión fijan que las claves
   naturales se siguen sumando), y que el cambio se hizo **después** de que
   R13 estuviera verificado con el checksum, no para hacerlo pasar.

3. **`progress/current.md` §4 (T13): cerrar la sección.** Termina en
   «Pendiente: PARADA 1 con el plan de arreglo (propuesto al humano)»
   (línea 858), cuando esa parada se resolvió: opción A, R15 enmendada y
   SUPERADA (`2d95980`, 2026-08-17). Severidad **baja**; bloqueante por C2.
   Sustituir por el desenlace real y mantener ahí las dos tareas operativas
   que siguen abiertas en el puesto del humano (ver observación 8).

## Observaciones NO bloqueantes

4. **`features.json`: F-019 sigue `blocked`.** Acción de cierre del líder
   (pasarla a `done` tras estos tres arreglos) junto con el resumen en
   `progress/history.md`, que hoy no la menciona.

5. **`progress/mutacion_F-019.md` ya solo documenta la campaña de los
   arreglos de T13** (38 líneas, 1 mutante): la del núcleo (458 líneas, 41
   mutantes) quedó pisada al regenerar el informe, porque el núcleo vive en
   `dev` y salió del diff. La evidencia sobrevive en la sección del
   2026-08-10 de este mismo fichero y en `impl_F-019.md`, y he verificado que
   el núcleo no ha cambiado desde entonces, así que **no es un agujero de
   rigor**. Sugerencia: que la herramienta no sobrescriba campañas anteriores
   sino que anexe con fecha, o al menos que el informe diga qué quedó fuera
   del alcance y por qué. Es mejora del arnés genérico (`arnes-base`).

6. **`.gitignore` no ignora `huella_*.csv`.** Los 6 CSV de la raíz están
   correctamente sin versionar, pero solo por disciplina: un `git add -A`
   distraído los mete. Una línea `huella_*.csv` lo hace imposible.

7. **Los 19 tests de los arreglos de T13 se llaman `test_f019_t13_*`, no
   `test_f019_rN_*`.** No incumplen C4 —que exige que cada requisito EARS
   tenga test, no al revés— pero se quedan sin requisito al que trazar,
   porque la spec nunca ganó un requisito AUTO del tipo «el nombre del mes no
   depende del locale del servidor» ni «la huella no agrega claves
   sustitutas». Son dos propiedades **permanentes** del sistema, no
   incidencias de una tarea: si algún día alguien vuelve a meter un `TMMonth`,
   el test que lo caza no apunta a ninguna regla escrita. Sugerencia (no
   bloqueante): añadirlas como R18/R19 al enmendar la spec, o recogerlas en
   `docs/CONVENTIONS.md` como regla de SQL portable.

8. **Cabos operativos en el puesto del humano**, que conviene no perder al
   cerrar (están citados en `current.md` pero sin confirmación de cierre): la
   línea fijada a mano en `hosts` marcada «⚠ RETIRAR al terminar T13»; las
   reglas de firewall `datamart-puesto-pgris-2026-08-16`, `-16b` y
   `-2026-08-17-rango`; y `SIGRID_API_PAGE_SIZE=50000` en `.env`, que fue un
   apaño para la red del humano y conviene decidir si se queda. Ninguno es
   del repositorio; por eso no bloquea.

9. **Aviso a consumidores, para el líder.** El arreglo del locale cambia
   **valores expuestos** en Azure: `nombre_mes` y `nombre_mes_anio` pasan de
   «May 2026» a «Mayo 2026» en las vistas de Power BI. El esquema no cambia
   (sigue `text`, comprobado y razonado en el informe), pero un informe que
   filtre o segmente por ese texto sí se entera.
   `azure-apps/datamart_seg_anual.md` ya documenta la protección de disco de
   F-019 (T8 cumplida), y valdría la pena añadir esta nota antes del merge,
   por la regla de propiedad de `azure-apps/`.

## Lo que he mirado con lupa y ha aguantado

- **La puerta de disco sigue siendo fail-safe.** `medir_ocupacion_disco_pct`
  propaga la excepción a propósito y convierte en `RuntimeError` los dos
  caminos silenciosos (`fetchone()` vacío, `fila[0] is None`); no existe rama
  que devuelva 0 «por si acaso». En el step, cualquier fallo cae en
  `_abortar_plan_mensual`, que vacía la tabla y relanza. Y la prueba de que no
  es teoría: el 2026-08-11 la puerta **saltó de verdad** en local («ocupación
  169,26 % > 80 %») por un `PG_DISCO_TOTAL_GB` inadecuado, y se comportó como
  está diseñada: tabla vacía, paso FAILED, cero tramos. Un fail-safe que ya ha
  disparado en caliente vale más que uno solo probado.
- **El filtro está en las dos ramas** (líneas 173 y 326) y el `TRUNCATE` no
  está en el fichero: verificado sobre el SQL actual, no sobre el informe.
- **60/60 tramos contra el servidor compartido sin un solo aborto y con pico
  46,55 %.** El incidente que originó la feature tocó el 93,4 %. Ese es el
  número que dice que F-019 hizo lo que venía a hacer.
- **La disciplina del método.** Dos veces el trabajo dio un resultado
  incómodo (checksum distinto en T11; 22 fallos de huella en T13) y las dos
  veces se declaró FALLO y se investigó hasta la causa raíz, en vez de ajustar
  el criterio primero. Las enmiendas de R13 y R15 llegan **después** de la
  evidencia y las decide el humano por escrito, con fecha y opción. Es la
  diferencia entre enmendar un requisito y rebajarlo.

## Qué tiene que pasar para el APROBADO

Los tres arreglos de arriba, en tres ficheros de texto. Una re-review solo
necesita releer `tasks.md`, `design.md` §6 y `current.md` §4: no hay que
volver a ejecutar la campaña de mutación ni nada contra BBDD (el protocolo
volverá a lanzar `init.sh`, que hoy está verde). El código de F-019 está
**aprobado tal cual está**.

## Automejora del protocolo (propuesta, no aplicada)

Esta pasada ha destapado un hueco del propio arnés: **cuando una feature se
mergea a `dev` a mitad de camino** —aquí fue necesario, R14 exigía que el
humano cargara desde el árbol de `dev`— el alcance del diff se vacía y las dos
puertas que dependen de él, cobertura y mutación, pasan a medir solo el resto
del trabajo. Hoy eso se detecta solo si el reviewer se fija en que «4 líneas
cambiadas» es sospechosamente poco para una feature de este tamaño, y se salva
porque hay un review anterior que sí cubrió el núcleo. Propongo dos cosas para
`CHECKPOINTS.md` y `harness/`:

1. Que el informe de mutación **declare siempre el ref base** y avise cuando
   el alcance sea menor que el de una campaña previa de la misma feature, en
   vez de sobrescribirla en silencio.
2. Que C4 bis pida al reviewer, en features con merge intermedio a `dev`,
   **citar explícitamente qué campaña cubre el núcleo** y verificar que esos
   ficheros no han cambiado desde ella. Es lo que he hecho aquí a mano.

Vale para cualquier proyecto: si el humano lo aprueba, va también a
`arnes-base`.

**Veredicto final de esta pasada: CAMBIOS_REQUERIDOS** (3 bloqueantes, todos
documentales; ningún defecto de código).


---

# Re-review de F-019 (2026-08-17, tarde) — tercera pasada y cierre

> Verifica los tres bloqueantes de la segunda pasada, aplicados por el líder
> en el commit `be35b50`. Las dos secciones anteriores se conservan íntegras.

## Veredicto

**APROBADO.** Los tres bloqueantes están resueltos, y resueltos bien: no con
un `[x]` cosmético, sino con el contenido que faltaba. F-019 cumple
`CHECKPOINTS.md` en nivel `critico` y puede pasar a `done`.

## Estado del arnés, reejecutado por mí

`bash harness/init.sh` sobre `be35b50`: **398 passed** en 5,83 s,
`PUERTA COBERTURA: 100.0% de 4 líneas cambiadas (4/4, umbral 80%, nivel
critico)`, rama correcta, `ENTORNO LISTO`, exit 0. Sin cambios respecto a la
pasada anterior, como debía ser: el commit no toca código ni tests
(`git show --stat`: solo `tasks.md`, `design.md` y `current.md`, 71
inserciones y 28 borrados).

## Bloqueante 1 — `tasks.md` · RESUELTO [x]

Las cinco tareas del humano quedan `[x]` con fecha, resultado y commits, y
**cada una es contrastable**. He verificado los datos que afirman, no solo
que la casilla esté marcada:

| Tarea | Lo que afirma `tasks.md` | Contrastado contra |
|---|---|---|
| T1/T2 (11-ago) | 29,09 M filas, 7.532 MB, ×18,4, obra más pesada 298.053 filas ≪ 1 M | `design.md` §2, columna «medido» completa |
| T11 (13-ago) | checksum FALLÓ (`ec74147e` vs `c58b928d`), equivalencia semántica probada, opción C, commits `acee46b`…`181e01e` | `current.md` §2 y enmienda de R13; commits existen |
| T12 (14/15-ago) | 6.851,8 s, 60/60 tramos, pico 46,55 %, commit `c74b65b` | `current.md` §3; commit existe |
| T13 (15/17-ago) | 3 defectos corregidos (`42e128d`, `65c52aa`), 5 residuales = edición real de 632,74 €, opción A, commits `8582485`, `2d95980` | `current.md` §4, enmienda de R15, `impl_T13_fixes_f019.md`; commits existen |

Mención aparte para T11: la entrada **no esconde que el criterio original
falló**. Dice «el checksum dio FALLO … se declaró sin racionalizar» antes de
decir que quedó superado por enmienda. Un `tasks.md` que solo dijera «T11
hecha» habría sido peor documento con la misma casilla marcada.

**T14 queda `[ ]` con la justificación escrita en el propio fichero** («A
PROPÓSITO: es posterior al `done` y pertenece operativamente a F-003»). Con
eso, el N/A deja de ser un hueco: cumple la regla de `CHECKPOINTS.md` de que
un N/A sin motivo escrito cuenta como casilla vacía. C5 satisfecho.

## Bloqueante 2 — `design.md` §6 · RESUELTO [x]

La enmienda fechada 2026-08-17 hace exactamente lo que pedí, y añade algo
que no había pedido y mejora el documento: **conserva el texto original
intacto** y se coloca detrás como enmienda, igual que R13 y R15. Contiene:

1. **Qué se tocó y con qué commit**: `fingerprint.py` (`65c52aa`) y los 5
   ficheros de `mart/`/`cierre/` (`42e128d`).
2. **Por qué la excepción estaba justificada**: el árbitro daba **falsos
   positivos** (BIGSERIAL sin `ORDER BY` reparte ids distintos en cada
   máquina) y el `TMMonth` era un bug real de portabilidad (+48 % de filas en
   `cierre.v_pbi_planif_vs_real` en Azure).
3. **La defensa de la independencia del árbitro**, que es el punto que hacía
   falta: exclusión de dos columnas **nominadas** en una constante
   documentada, ambas siguen en el bloque `estructura`, tests de no-regresión
   que fijan que las claves naturales se siguen sumando, y —lo decisivo— que
   el cambio se hizo **después** de que R13 estuviera verificado con el
   checksum, «no para hacerlo pasar». Ese orden temporal es el que impide que
   la excepción sea un ajuste del examen para aprobarlo, y ahora está escrito
   donde vive la restricción, no solo en la enmienda de R15.

## Bloqueante 3 — `progress/current.md` §4 · RESUELTO [x]

La sección de T13 ya no muere en «Pendiente: PARADA 1». Termina en
**«DESENLACE (2026-08-17): el humano eligió la OPCIÓN A … T13 CERRADO»**, con
el commit de la enmienda, y separa con claridad lo que sigue abierto —tres
tareas del **puesto** del humano: la línea de `hosts`, las reglas de firewall
y `SIGRID_API_PAGE_SIZE`— de lo que es del repositorio, que ya no es nada.
La memoria y la spec vuelven a decir lo mismo.

## Recorrido final de CHECKPOINTS.md

| Bloque | Estado | Nota |
|---|---|---|
| **C1** | [x] | `init.sh` exit 0 reejecutado por mí; ficheros del arnés completos |
| **C2** | [x] | Rama correcta, ninguna feature `in_progress`, `current.md` ya coherente (bloqueante 3 resuelto), `history.md` sin features `done` huérfanas |
| **C3** | [x] | Dominio puro, SQL en su capa, cabeceras de ruta, `ruff` limpio, cero lógica de negocio tocada, ninguna máscara `TM` restante |
| **C3 bis** | [x] | Cabecera con origen y fecha; ningún original ofimático en la historia; **barrido de datos sensibles ejecutado por mí** con cinco familias de patrones y cero coincidencias; indexado en el README |
| **C4** | [x] | 48 tests `test_f019_*` trazables y en verde; sin red ni BBDD; verificaciones MANUAL **ejecutadas con resultado real**, no pendientes |
| **C4 bis** | [x] | `rigor: critico` declarado; fase RED con traza real; cobertura `[OK]` 100 %; mutación verificada de forma independiente (38 líneas / 1 mutante, coincidencia literal); cero supervivientes; «Evidencias» con los cuatro números en los dos informes; ningún N/A sin motivo |
| **C5** | [x] | `tasks.md` con todo `[x]` salvo T14, justificado por escrito en el propio fichero; sin artefactos sospechosos (los `huella_*.csv` son evidencia deliberadamente sin versionar); `features.json` → acción de cierre del líder |

**Ninguna casilla vacía en C1–C5.**

## Lo que queda en manos del líder al cerrar (no bloquea el APROBADO)

1. `harness/features.json`: F-019 de `blocked` a **`done`**.
2. Resumen de F-019 en `progress/history.md` (hoy no la menciona).
3. Las observaciones 5 a 9 de la segunda pasada, todas no bloqueantes y
   todas vigentes: informe de mutación pisado, `huella_*.csv` fuera del
   `.gitignore`, los 19 tests `t13_*` sin requisito EARS al que trazar, los
   cabos operativos del puesto (ya listados en `current.md`, punto 3
   resuelto) y el **aviso a consumidores de Power BI**: `nombre_mes` pasa de
   «May 2026» a «Mayo 2026» en Azure, cambio de valor expuesto que merece una
   línea en `azure-apps/datamart_seg_anual.md` antes del merge.
4. Detalle cosmético menor: en `current.md`, las dos líneas antiguas sobre
   las reglas de firewall `-2026-08-16` y `-16b` quedaron pegadas justo
   debajo de la lista nueva y se solapan con su tercer punto. No confunde,
   pero sobra una de las dos al consolidar la sesión en `history.md`.

## Cierre

F-019 nació de un incidente: el 2026-08-09 este build llenó al 93,4 % el
disco de un servidor compartido y dejó a `albaranes` y `partes` en
solo-lectura diez minutos. El 2026-08-15 el mismo build corrió contra el
mismo servidor en **60 tramos, sin un solo aborto, con pico del 46,55 %**.
Por el camino la verificación destapó cuatro defectos que nadie buscaba —dos
versiones master duplicadas en el sistema origen, un nombre de mes que
dependía del idioma del servidor, una huella que sumaba claves sustitutas y
un raw local con esquema legado— y ninguno se tapó: dos se arreglaron con
rigor `critico` completo, uno se documentó y se convirtió en F-022, y el
cuarto lo rehízo el humano. Las dos veces que el resultado fue incómodo se
declaró FALLO antes de enmendar el criterio, y las enmiendas las firmó el
humano con fecha y opción elegida. Eso es lo que hace que este APROBADO
signifique algo.

**Veredicto: APROBADO.**

