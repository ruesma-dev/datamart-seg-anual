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
