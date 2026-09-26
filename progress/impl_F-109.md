# F-109 · Informe del implementer · el código de partida no es único ni dentro de su obra

Rama `feature/F-109-partidas-codigo-no-unico` (desde `main` 1ed4d6e). Rigor
`estandar`. Spec APROBADA por el humano el 2026-09-26 (`progress/spec_F-109.md`,
sección «APROBADA»): D1 (a) solo `partida_id`; D2 con la redacción del humano;
D3 documentar aquí y arreglar en F-111; D4 versión 35; D5 solo texto.
**Ningún SQL cambia** (`git diff main --stat` no lista ningún `.sql`).

## Qué cambió

| Fichero | Cambio | R |
|---|---|---|
| `config/diccionario/stg.yaml` | `partidas`: párrafo nuevo en `descripcion`; `obra_id` ya no dice «los códigos solo son únicos dentro de su obra»; `codigo_partida` explica la repetición con cifras, causas y fecha, y matiza «nunca vacío» (2 filas de solo espacios); `ruta_capitulos`: CASI clave (155), para leer, no para unir | R1, R5-R7 |
| `config/diccionario/mart.yaml` | `fact_seguimiento_mensual.codigo_partida` (quita «Único por obra»); `v_pbi_dim_partida` `obra_id`, `codigo_partida`, `partida_label` (4.127 homónimas, un segmentador las suma juntas); `v_pbi_dim_partida_niveles.nivel_1..6` (nombre por `(obra, código)` con `MAX`, 10.593 filas, F-111) | R2, R3, R8, R13 |
| `config/diccionario/compras.yaml` | `v_pbi_partida_coste.codigo_partida`: no identifica, cruzar por `partida_id` | R8 |
| `config/diccionario/cierre.yaml` | `v_pbi_dim_subcategoria_ci` `grupo_nombre` / `subcategoria_nombre`: se identifica por CÓDIGO, las fases `CI`/`CI-FII` de la 0444 se funden, F-111 | R14 |
| `config/diccionario/00_global.yaml` | regla `R-PARTIDA-CODIGO-NO-UNICO` (bloqueante, 7 objetos) tras `R-LINEA-ID-NO-UNICA`; `version` 34 -> **35** con su historia en cabeza | R9-R12, R16 |
| `docs/ARCHITECTURE.md` | entrada «El código de partida no es único ni dentro de su obra (F-109)» en «Semántica Sigrid imprescindible», tras las de F-052 | R17 |
| `tests/test_f109_partidas_codigo.py` | 23 tests offline, `test_f109_rN_*`, R1-R17 | todos |
| `harness/features.json`, `BACKLOG.md`, `progress/current.md`, `tasks.md` | `in_progress`, backlog regenerado, seguimiento | — |

Commits: `8b45624` (arranque), `434dab0` T1, `a0e1418` T2, `7f3ce89` T3,
`785896d` T4, `0a7822c` T5, `570d203` T6, `f0af7d8` T7, `bd1506c` T8+T10, y el
del cierre (informe y `BACKLOG.md`).

## Decisiones de diseño y desviaciones (justificadas)

1. **Texto de la regla = redacción aprobada por el humano, no `design.md` §5.**
   El primer párrafo de `regla` es literal: «No cruces tablas por obra + código
   de partida: usa `partida_id`. Agrupar por código es válido si se quiere sumar
   todas las copias del concepto (por ejemplo, la misma partida en todos los
   bloques o fases), y hay que decirlo. Para identificar una partida ante el
   usuario, enseña su ruta de capítulos.» Se quita la frase de §5 «Agrupar por
   código funde partidas distintas», que contradecía D2; un test
   (`test_f109_r10_la_regla_lleva_la_redaccion_aprobada_por_el_humano`) exige
   la redacción y prohíbe que vuelva esa frase. Las cifras de R10 (5.202, 158,
   0437, 883.460,55 -> 3.474.491,83) van en el segundo párrafo, «Por qué».
2. **R16: `version >= 35`, no `>= 33`** (D4: `main` ya está en la 34).
3. **R4 con negación.** El barrido normaliza (sin tildes, sin `*`/`` ` ``,
   minúsculas, espacios colapsados) y caza `únic[oa]s? (por|en|dentro de)
   (su|la|cada)? obra` y «solo son únicos dentro», salvo tras «no es»/«no son».
   Recorre descripción, grano, motivo de no consumo, columnas y reglas de TODO
   el diccionario. Un test aparte demuestra que muerde las tres frases que
   había (con y sin tildes) y deja pasar la negación. Por eso la ficha de
   `ruta_capitulos` dice «CASI una clave dentro de la obra» y no «casi única en
   la obra», que el patrón habría denunciado.
4. **Causas en la ficha**: se agrupan en cuatro (contrato/expediente 873 =
   637+175+61; subárbol copiado 1.932; raíces paralelas 2.360; homónimas y
   marcadores 28, más 9 copias pegadas dos veces), con ejemplos de
   `design.md` §1.1. La causa 6 («sin explicar») se escribe como «copias
   idénticas pegadas dos veces», que es lo que parecen.
5. **Alcance de R14**: solo `v_pbi_dim_subcategoria_ci`, como dice la spec.
   `cierre.v_pbi_cierre_indirectos_detalle` también resuelve el nombre por
   `(obra, código)` (`cierre/04_views_detalle.sql:123`) y su ficha no avisa;
   la ficha de F-111 ya la nombra («y el detalle de costes indirectos»), así
   que se deja para allí.
6. **La cifra de hoy no reescribe la de la spec.** Remedida hoy por el MCP
   (solo lectura, build de `stg` del 2026-09-26 01:56 UTC), la consulta de
   `design.md` §7.1 da **5.203 pares / 8.934 filas / 159 obras** (el 25:
   5.202 / 8.933 / 158). Las fichas y la regla citan la del **2026-09-25** con
   su fecha, que sigue siendo cierta y es la única con el desglose por causas
   que suma al par; cambiar solo el total rompería esa suma por un par. Se
   anota como desviación de `design.md` §9 («si remide y cambia, actualiza»).
7. **Precondición `init.sh`**: no se relanzó al empezar (14-25 min); `main`
   estaba verde (F-110, f730acf) y la rama solo llevaba el merge 1ed4d6e.

## Fase RED (obligatoria, rigor `estandar`)

Comando, con los tests escritos y ninguna ficha tocada (commit `434dab0`):

```
$ .venv/Scripts/python.exe -m pytest tests/test_f109_partidas_codigo.py -q --tb=no -rfp -p no:cacheprovider
FFFF.FFFFFFFFF.FFF..FFF                                                  [100%]
19 failed, 4 passed in 3.31s
```

Una línea por fallo (`--tb=line`, ruta recortada):

```
L162: AssertionError: obra a la que pertenece. los codigos de partida solo son unicos dentro de su obra.
L170: AssertionError: obra a la que pertenece. una partida pertenece siempre a una sola obra: los codigos de partida solo son unicos dentro de su obra.
L178: AssertionError: assert 'unico por obra' not in 'codigo jera...entre obras.'
L202: AssertionError: el diccionario atribuye unicidad al codigo de partida dentro de la obra, y NO la tiene (F-109: 5.202 pares repetidos):
L235: AssertionError: a la ficha de stg.partidas.codigo_partida le falta ['no es unico dentro de la obra', '5.202', '158', '2026-09-25', 'contrato', 'expediente', 'raices paralelas', 'errata', '4.437', 'partida_id', 'ruta_capitulo
L241: AssertionError: 2 filas traen un codigo de solo espacios, que el filtro `cod <> ''` deja pasar
L254: AssertionError: a la ficha de stg.partidas.ruta_capitulos le falta ['casi', '155', '162', '25 obras', '38', '2026-09-25', 'partida_id', 'no para unir']
L264: AssertionError: compras.v_pbi_partida_coste.codigo_partida no manda unir por partida_id
L272: AssertionError: partida_label no avisa de las homonimas: falta ['4.127', '2026-09-25']
L121: AssertionError: 00_global.yaml no declara `R-PARTIDA-CODIGO-NO-UNICO`      (r9, r10 x2, r12)
L322: AssertionError: R-PARTIDA-CODIGO-NO-UNICO no llega como aviso a ['stg.partidas', 'mart.v_pbi_dim_partida', 'mart.v_pbi_dim_partida_niveles', 'mart.fact_seguimiento_mensual', 'mart.v_fact_periodificado', 'compras.v_pbi_partid
L361: AssertionError: nivel_1 no avisa del nombre resuelto por codigo: ['(obra, codigo)', 'max(descripcion_corta)', '10.593', '4.657', '2026-09-25', 'F-111']
L372: AssertionError: cierre.v_pbi_dim_subcategoria_ci.grupo_nombre: falta ['0444', 'CI-FII', 'F-111']
L425: assert 34 >= 35
L431: AssertionError: 00_global.yaml no lleva el comentario de historia de la version de F-109
L444: AssertionError: ARCHITECTURE.md no documenta F-109: falta ['el codigo de partida no es unico ni dentro de su obra (f-109)', 'partida_id', 'raices paralelas', '5.202']
```

Los 4 verdes de la fase RED son guardas, no requisitos sin probar:
`r4_el_barrido_muerde_con_y_sin_tildes` (prueba del propio patrón),
`r12_el_diccionario_real_valida_sin_errores` (ya validaba en `main`) y los dos
de `r15` (el trinquete describe lo que YA hay; la spec lo preveía).

**R15 muerde sobre el árbol real** (T6): con un tercer fichero temporal
`sql/compras/99_intruso_f109.sql` que agrupa por obra y código, borrado después:

```
L381: AssertionError: compras/99_intruso_f109.sql resuelve algo por (obra_id, codigo_partida), que NO es unico (F-109): une o agrupa por partida_id, o declaralo aqui con su porque
1 failed, 22 deselected in 0.17s
```

En verde, tras T7: `pytest tests/test_f109_partidas_codigo.py` -> **23 passed
in 1.84s**.

## Verificaciones intermedias (resultado real)

- T2: `pytest tests/test_f006_fichas.py tests/test_f006_stg_trampas.py tests/test_f052_huella_dimension.py` -> 740 passed, 197 skipped.
- T3: `pytest tests -k "f006 or f102"` -> 2.098 passed, 200 skipped, 1 failed
  (`test_f109_r12_la_regla_cumple...`, que esperaba a T4).
- T4: `test_f006_reglas`, `_publicacion`, `_constantes_de_contrato`, `test_f078_sql` -> 271 passed; `_contexto`, `_cobertura`, `_docs` -> 80 passed.
- T5: `pytest tests -k "version or publicacion or r16"` -> 265 passed, 7 skipped.
- T7: `pytest tests -k "docs or arquitectura or architecture"` -> 24 passed.
- `ruff check tests/test_f109_partidas_codigo.py` -> All checks passed.
- Contra la base (MCP, solo lectura, 2026-09-26): consulta de `design.md` §7.1
  -> 5.203 / 8.934 / 159 (esperado «~5.200»; ver desviación 6).

## Qué queda fuera del alcance

- Ningún SQL: los nombres por código de `mart/05b_view_dim_partida_niveles.sql`
  y `cierre/04_views_detalle.sql` (las dos vistas de nombres) son **F-111**,
  ya fichada por el líder (T10 cumplida con esa ficha; no se redacta otra).
- No se publica `ctride`/`expide` ni se ingiere `obrctrexp` (entradas para
  F-099, las anota el líder).
- No se declara clave alternativa (D1 (a)): ni `(obra, ruta)` ni `(obra,
  contrato, ruta)`.
- `azure-apps/` no cambia: ningún objeto ni columna publicada cambia de forma.

## Qué falta (MANUAL, humano) · T9 / R18

1. `python main.py publicar-diccionario` contra Azure (escritura, la autoriza
   el humano): publica la **versión 35**.
2. Reiniciar `mcp-bbdd` (cachea el diccionario hasta reiniciar).
3. Comprobar: `_meta.diccionario_reglas` trae `R-PARTIDA-CODIGO-NO-UNICO` (18
   reglas) y `_meta.v_diccionario` las fichas de `stg.partidas.obra_id`,
   `mart.v_pbi_dim_partida.obra_id` y `mart.fact_seguimiento_mensual.codigo_partida`
   corregidas. La consulta §7.1 ya está hecha (arriba).
4. Reviewer + cierre de la feature (no lo hace el implementer).

## `bash harness/init.sh` (T11)

Lanzado tal cual sobre `bd1506c` (árbol limpio salvo este informe y
`progress/current.md`, que no ejecutan). Salida, final:

```
5542 passed, 203 skipped, 1484 warnings in 773.54s (0:12:53)
[OK] pytest en verde (con medición de cobertura)
[OK] PUERTA COBERTURA: 95.1% de 1106 líneas cambiadas cubiertas (1052/1106, umbral 80%, nivel estandar)
[OK] PUERTA TAMAÑO: F-109 dentro de los topes (requirements 131/150, design 250/250, impl 160/220)
[OK] Rama actual: feature/F-109-partidas-codigo-no-unico
ENTORNO LISTO. Puedes trabajar.   (exit 0)
```

Avisos no bloqueantes: `BACKLOG.md` regenerado (va en el commit de cierre),
F-052 `blocked` (previo), ruff 233 avisos de deuda previa (el test nuevo pasa
`ruff check` limpio).

## Evidencias

| Evidencia | Valor |
|---|---|
| Tests de la feature | 23 (23 passed en 1,84 s; en RED 19 failed / 4 passed) |
| Suite completa | 5.542 passed, 203 skipped, 0 failed (`bash harness/init.sh`, exit 0) |
| Cobertura de las líneas cambiadas | `PUERTA COBERTURA: 95.1% de 1106 líneas cambiadas cubiertas (1052/1106)`. OJO: F-109 no cambia ninguna línea de Python de producción; la cifra es la que la puerta mide sobre su propia base de comparación (la misma 95,1 % / 1.106 que dio F-110), no líneas de esta feature |
| Mutantes generados / supervivientes | **0 / 0: no hay Python de producción que mutar.** `python -m harness.mutacion --feature F-109 --base main` -> «ALCANCE VACÍO en F-109: ni una línea de producción que mutar (origen rama, 6e3fcb0..feature/F-109-partidas-codigo-no-unico). No se ha juzgado NADA.» y **no escribe** `progress/mutacion_F-109.md` a propósito (un cero no medido se leería como «nada que arreglar»). Todo el diff es YAML, Markdown y tests. Desviación de la verificación de T8, que esperaba ese fichero |
| Tiempo de la suite | 773,54 s (12 min 53 s) la suite completa con cobertura; 1,84 s los 23 tests de F-109 |
