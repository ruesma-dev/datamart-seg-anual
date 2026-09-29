Revisión completa (pasada 1) · `6e3fcb0..7ddfe38` (F-109 entera, desde el merge de `main` en la rama)
# F-109 · Review del reviewer (2026-09-26)

**Veredicto: APROBADO (APPROVED).**

**Rigor `estandar`** (declarado en `features.json`): fase RED, cobertura de lo
cambiado >= 80 % y campaña de mutación. Contra `specs/F-109-partidas-codigo-no-unico/`,
la sección «APROBADA (humano, 2026-09-26)» de `progress/spec_F-109.md`,
`docs/CONVENTIONS.md` y `CHECKPOINTS.md`.

## Lo que pidió el líder, punto por punto

1. **Ningún SQL cambia** [x]. `git diff --name-only 6e3fcb0..HEAD`: 15 ficheros,
   ninguno `.sql` ni de `etl_sigrid/`, `main.py` o `harness/*.py|sh`. Solo YAML
   del diccionario, `ARCHITECTURE.md`, un test nuevo y papeleo.
2. **Regla `R-PARTIDA-CODIGO-NO-UNICO`** [x]. `bloqueante`, tras
   `R-LINEA-ID-NO-UNICA` (orden 14; 18 reglas). El primer párrafo de `regla` es
   **literal** la redacción aprobada (comparada palabra a palabra con la sección
   «APROBADA»): prohíbe CRUZAR por obra + código, permite AGRUPAR por código
   declarándolo, e identifica ante el usuario por la ruta de capítulos. La frase
   de `design.md` §5 «Agrupar por código funde partidas distintas», que la
   contradecía, no está, y `test_f109_r10_la_regla_lleva_la_redaccion_aprobada...`
   impide que vuelva. El «Por qué» cita 5.202 / 158 / 2026-09-25 y 0437
   883.460,55 → 3.474.491,83. **Ámbito**: los siete objetos de R9; comprobado con
   `derivar_avisos` que los siete reciben el aviso. Barrido mío de todas las fichas
   con `codigo_partida`, `partida_label`, `nivel_N` o `grupo/subcategoria_nombre`:
   el único objeto fuera del ámbito es `cierre.v_pbi_cierre_indirectos_detalle`
   (no recomendado, nombres por código): ver Observación 1.
3. **Las tres fichas dicen la verdad** [x]. `stg.partidas.obra_id`,
   `mart.v_pbi_dim_partida.obra_id` y `mart.fact_seguimiento_mensual.codigo_partida`
   ya dicen «NO es único ni dentro de la obra» y mandan a `partida_id`.
   `stg.partidas.codigo_partida` trae las causas (contrato/expediente 873 =
   637+175+61, subárbol 1.932, raíces paralelas 2.360, homónimas 28 + 9 pegadas),
   que el contrato no desambigua (4.437) y la fecha. `test_f109_r4_*` barre TODO
   el diccionario (descripción, grano, motivo de no consumo, columnas, reglas);
   lo completé yo sobre los campos que no barre (`nulo_significa`, `valores`,
   `relaciones.porque`, `ejemplos_preguntas`, título de regla): **0 afirmaciones**.
4. **D1 y D3** [x]. D1: ninguna ficha declara clave con `codigo_partida` o
   `ruta_capitulos` salvo `compras.v_pbi_partida_coste`, cuya clave ya contenía
   `partida_id` (previa, superconjunto); `claves_alternativas` vacías en las tres
   fichas de partida; `ruta_capitulos` documentada como «CASI una clave… no para
   unir». D3: `nivel_1..6` y la dimensión CI avisan del nombre por `(obra,
   código)` y remiten a **F-111**, que existe `pending` en `features.json`;
   `mart/05b_…` y `cierre/04_…` intactos, fijados por el trinquete R15.
5. **Diccionario versión 35** [x], con su línea de historia en cabeza.
6. **Sin nombres de persona** [x]. Barrido de las líneas añadidas por el diff
   (pares de palabras capitalizadas, nombres conocidos, correos, IPs): solo
   topónimos y nombres de capítulo («Colector General», «Caldera Platinum»).

**Contraste con la base (MCP, solo lectura, hoy)**: `(obra, código)` 5.203 /
8.934 / 159; `(obra, ruta)` 155 / 162 / 25; 2 códigos de solo espacios.
Coincide con el implementer; las fichas citan la del 25 con su fecha.

## Checkpoints

- **C1** [x]: `bash harness/init.sh` tal cual en `7ddfe38`: **5.542 passed, 203 skipped en 776,96 s**, TAMAÑO dentro de topes (req. 131/150, design 250/250, impl 174/220), **ENTORNO LISTO, exit 0**.
  Ficheros del arnés presentes.
- **C2** [x]: una sola `in_progress` (F-109), rama `feature/F-109-...`.
  `current.md` tiene la sección de F-109 al día; arrastra ~2.200 líneas de
  sesiones cerradas, deuda previa del líder ya anotada en F-108 y F-110.
- **C3** [x]: sin SQL ni Python de producción; el test lleva primera línea con
  su ruta, en español, sin `print`, TODO ni secretos, `ruff` limpio; sin
  dependencias nuevas. Semántica Sigrid: `ARCHITECTURE.md` gana la entrada
  (R17), coherente con la regla.
- **C3 bis** N/A: no toca `docs/referencia/`.
- **C4** [x]: R1-R17 con test trazable (tabla abajo), 23 tests offline sobre el
  diccionario del árbol, `tmp_path` para R15. R18 es MANUAL y está en
  `current.md` §F-109 (T9: `publicar-diccionario` v35 y reinicio del MCP), con
  los comandos exactos en `impl_F-109.md` §«Qué falta». Sin dobles de test.
- **C4 bis**:
  - [x] Rigor declarado: `estandar`.
  - [x] **Fase RED reproducida por mí**: copia aislada (`git archive 7ddfe38` +
    `config/diccionario` y `ARCHITECTURE.md` de `6e3fcb0`) → **19 failed, 4
    passed**, idéntico a la traza de `impl_F-109.md`. Los 4 verdes son guardas
    (patrón del barrido, validación, trinquete R15). R15 muerde: traza real con
    un intruso en el árbol y caso sintético en `tmp_path`.
  - [x] **Cobertura**: la puerta sale `[OK]` («95,1 % de 1106 líneas», 1052/1106), pero **no mide
    F-109**: `RAMA_BASE=dev` y `dev` está muy atrás de `main`, así que cuenta
    líneas de features ya fusionadas (el implementer lo declara). Contra `main`
    F-109 tiene **0 líneas de producción** (`alcance_de_feature(..., base='main')`
    → `lineas={}`): cobertura N/A justificado por alcance vacío. Observación 2.
  - [x] **Mutación, N/A justificado por alcance vacío, verificado por mí**: no
    existe `progress/mutacion_F-109.md` y es correcto: reejecuté
    `python -m harness.mutacion --feature F-109 --base main --salida <scratchpad>`
    → «ALCANCE VACÍO … No se ha juzgado NADA», exit 3, nada escrito, `git status`
    limpio. **Control del cero**: `generar_mutantes` sobre el único `.py` del
    diff ignorando la exclusión (el test) da **50 mutantes**: el generador
    funciona y el cero es exclusión por diseño (todo es YAML, Markdown y tests).
    No hay tiempos, supervivientes, SHA ni campaña manual que juzgar: RM1, RM2,
    RM3, RM4, «CAMPAÑA NO VÁLIDA», coste por mutante y análisis de supervivientes
    N/A por la misma razón. RM5 N/A por nivel (`estandar`). RM6 N/A: no se quitó
    código defensivo.
  - [x] «Evidencias» con los cuatro números (23 tests, cobertura con su
    advertencia, 0/0 mutantes con el motivo, 773,5 s de suite).
- **C4 ter** N/A: la puerta de rutas sensibles no señaló rutas tocadas.
- **C5** [x]: T1-T8, T10, T11 `[x]` con commit `F-109 Tn:`; T9 abierta por ser
  MANUAL (humano), como marca la spec. La verificación de T8 («escribe
  `progress/mutacion_F-109.md`») no se cumple a propósito: la herramienta se
  niega a escribir un cero no medido; desviación declarada y correcta. Sin
  temporales; `features.json` en `in_progress` hasta este veredicto.

## Cobertura requisito → test (`tests/test_f109_partidas_codigo.py`)

| R | Test(s) |
|---|---|
| R1-R3 | `test_f109_r1_*`, `r2_*`, `r3_*` |
| R4 | `r4_ninguna_ficha_dice_que_el_codigo_es_unico`, `r4_el_barrido_muerde_con_y_sin_tildes` |
| R5-R7 | `r5_*`, `r6_*`, `r7_*` |
| R8 | `r8_el_codigo_no_identifica_*`, `r8_partida_label_avisa_*` |
| R9-R12 | `r9_*`, `r10_*` (2, uno con la redacción del humano), `r11_*`, `r12_*` (2) |
| R13-R15 | `r13_*`, `r14_*`, `r15_*` (2: árbol real y caso sintético) |
| R16-R17 | `r16_*` (2, `>= 35` por D4), `r17_*` |
| R18 | MANUAL (humano), T9 |

## Observaciones (no bloquean)

1. `cierre.v_pbi_cierre_indirectos_detalle` resuelve `grupo_nombre` y
   `subcategoria_nombre` por `(obra, código)` igual que la dimensión CI
   (`cierre/04_views_detalle.sql:123`) y ni su ficha avisa ni está en el ámbito
   de la regla. Fuera de R14 por la spec y ya nombrada en la ficha de F-111:
   que F-111 la cierre o, si se retrasa, añadirla al ámbito.
2. `mart.v_pbi_dim_partida_niveles.partida_label` tiene el mismo problema de
   homónimas que el de la dimensión base y no lo dice (R8 solo pedía la base).
3. `azure-apps/datamart_seg_anual.md` no cambia: ningún objeto ni columna
   cambia de forma; la regla nueva viaja en `_meta.diccionario_reglas`. Correcto.
4. El MCP sirve hoy la versión 34 con 17 reglas
   (visto en `contexto_bbdd`): la regla no llega al agente hasta T9/R18 (humano).

## Automejora (propuesta, no aplicada)

La puerta de cobertura de este repositorio mide contra `RAMA_BASE=dev`
(`harness/init.sh:34`), pero las features salen de `main` y `dev` está parado
en `a1845db`: F-109 sale «95,1 % de 1.106 líneas», la misma cifra que F-110, y
ninguna es de F-109. Propongo que la base sea `main` en este proyecto (cambio
local), y en `arnes-base` que la puerta use el `merge-base` con la rama de
integración más reciente o avise cuando la base esté por detrás de `main`.
