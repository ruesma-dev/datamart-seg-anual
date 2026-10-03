<!-- progress/mutacion_F-113.md -->
# F-113 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-113` el 2026-10-03 14:31.

## Alcance

Origen del diff: **rama** (`1bc205ef250bdf9d63743810ee779f81d3d75b5e` .. `feature/F-113-categoria-capitulo-por-prefijo`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/domain/arbol_partidas.py` | 21 |
| `etl_sigrid/domain/categoria_partida.py` | 83 |
| **Total** | **104** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 1 |
| Mutantes evaluados | 1 |
| Muertos | 1 |
| Supervivientes | 0 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 1349.2 s |
| SHA de HEAD medido | `140758b87cb5a1a8e8291cad6e4742a6c49e59b2` |
| Línea base (s) — `.` | 464.9 |
| Media por mutante evaluado (s) | 1349.2 |
| Timeout efectivo por mutante (s) | 930 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 1 |
| Muestreo | no: campaña completa |

## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.

---

# Campaña MANUAL (SQL y dominio)

Escrita a mano por el implementer el 2026-10-03: **no la genera
`harness.mutacion`**. Motivo, en dos partes: (1) el arnés no muta SQL, y la
regla vive en `04_partidas.sql`; (2) sobre el dominio Python su juego de
operadores genera **un solo mutante en 104 líneas** (arriba). Script versionado:
`progress/mediciones/F-113_mutacion_sql.py`; se reproduce con
`python progress/mediciones/F-113_mutacion_sql.py`.

## Método

- Worktree desechable (`git worktree add --detach`) del HEAD medido. Por cada
  mutante se exige que el texto ORIGINAL aparezca una sola vez en su fichero,
  se sustituye por el MUTADO, se ejecutan `tests/test_f113_sql.py`,
  `test_f052_sql.py`, `test_f006_stg_trampas.py`, `test_f113_categoria.py` y
  `test_f052_arbol.py` **sin `-x`** (`-q --tb=no`), se cuentan los `FAILED` y se
  restaura el fichero (el script comprueba que vuelve idéntico byte a byte).
- Pares de la tabla: textos EXACTOS sustituidos, sin la sangría inicial; ` ⏎ `
  es un salto de línea. `fichero:línea` es la línea donde empieza el original.
  En «Tests que caen», `(+N)` son N tests más (el número total está en Fallos).
- Sin muestreo: M01-M27 cubren todo el SQL cambiado (las dos ramas del `CASE`
  y el `INSERT`), con los del diseño §8 (prefijos, `'34'`, `'99'`,
  `NOT IN`→`IN`, `ELSE a.categoria`→`ELSE 'OTRO'`, quitar un `REPLACE`, orden
  de los `WHEN`); D01-D20, cada constante y cada decisión del dominio.

| Métrica | Valor |
|---|---|
| SHA de HEAD medido | `8ecea163b3d855fe7d6758d14d2b17ceaf3bb115` |
| Línea base antes / después | 226 passed en 7,2 s / 226 passed en 9,3 s |
| Tiempo total de los mutantes | **323 s** (4,3-9,7 s por mutante), 2026-10-03 12:40-12:46 UTC |
| Workers | **1** (en serie) |
| Primera pasada (solo M01-M27, 3 tests, SHA `ad4d16a`) | 27/27 muertos en 134 s |

## Resultado: 47 generados, 47 muertos, 0 supervivientes

| Mutante | Fichero:línea | Original | Mutado | Fallos | Qué simula | Tests que caen |
|---|---|---|---|---|---|---|
| M01 | `04_partidas.sql:140` | `WHEN UPPER(p.cod) LIKE 'CD%' THEN 'CD'` | `WHEN UPPER(p.cod) LIKE '%CD%' THEN 'CD'` | 3 | vuelve el comodín delante (CD) | test_f113_r10_la_raiz_completa_y_en_el_orden_del_dominio, test_f113_r10_la_raiz_prueba_cada_prefijo_con_su_categoria, test_f113_r11_ningun_like_con_comodin_delante |
| M02 | `04_partidas.sql:141` | `WHEN UPPER(p.cod) LIKE 'CI%' THEN 'CI'` | `WHEN UPPER(p.cod) LIKE '%CI%' THEN 'CI'` | 3 | vuelve el comodín delante (CI): el defecto | test_f113_r10_la_raiz_completa_y_en_el_orden_del_dominio, test_f113_r10_la_raiz_prueba_cada_prefijo_con_su_categoria, test_f113_r11_ningun_like_con_comodin_delante |
| M03 | `04_partidas.sql:142` | `WHEN UPPER(p.cod) LIKE 'CP%' THEN 'CP'` | `WHEN UPPER(p.cod) LIKE '%CP%' THEN 'CP'` | 3 | vuelve el comodín delante (CP) | test_f113_r10_la_raiz_completa_y_en_el_orden_del_dominio, test_f113_r10_la_raiz_prueba_cada_prefijo_con_su_categoria, test_f113_r11_ningun_like_con_comodin_delante |
| M04 | `04_partidas.sql:140` | `WHEN UPPER(p.cod) LIKE 'CD%' THEN 'CD'` | `WHEN UPPER(p.cod) LIKE 'CD%' THEN 'CI'` | 2 | prefijo CD clasifica como CI | test_f113_r10_la_raiz_completa_y_en_el_orden_del_dominio, test_f113_r10_la_raiz_prueba_cada_prefijo_con_su_categoria |
| M05 | `04_partidas.sql:141` | `WHEN UPPER(p.cod) LIKE 'CI%' THEN 'CI'` | `WHEN UPPER(p.cod) LIKE 'C%' THEN 'CI'` | 2 | prefijo recortado a C | test_f113_r10_la_raiz_completa_y_en_el_orden_del_dominio, test_f113_r10_la_raiz_prueba_cada_prefijo_con_su_categoria |
| M06 | `04_partidas.sql:142` | `WHEN UPPER(p.cod) LIKE 'CP%' THEN 'CP'` | `WHEN UPPER(p.cod) LIKE 'CP%' THEN 'OTRO'` | 2 | prefijo CP clasifica como OTRO | test_f113_r10_la_raiz_completa_y_en_el_orden_del_dominio, test_f113_r10_la_raiz_prueba_cada_prefijo_con_su_categoria |
| M07 | `04_partidas.sql:140` | `WHEN UPPER(p.cod) LIKE 'CD%' THEN 'CD'` | `WHEN p.cod LIKE 'CD%' THEN 'CD'` | 2 | sin UPPER en la raíz (cd minúsculas) | test_f113_r10_la_raiz_completa_y_en_el_orden_del_dominio, test_f113_r10_la_raiz_prueba_cada_prefijo_con_su_categoria |
| M08 | `04_partidas.sql:140` | `WHEN UPPER(p.cod) LIKE 'CD%' THEN 'CD' ⏎               WHEN UPPER(p.cod) LIKE 'CI%' THEN 'CI'` | `WHEN UPPER(p.cod) LIKE 'CI%' THEN 'CI' ⏎               WHEN UPPER(p.cod) LIKE 'CD%' THEN 'CD'` | 1 | orden de los WHEN CD/CI (equivalente) | test_f113_r10_la_raiz_completa_y_en_el_orden_del_dominio |
| M09 | `04_partidas.sql:140` | `(CASE WHEN UPPER(p.cod) LIKE 'CD%' THEN 'CD'` | `(CASE WHEN p.cod ~ '^[0-9]+$' AND p.cod NOT IN ('34', '99') THEN 'CD' ⏎               WHEN UPPER(p.cod) LIKE 'CD%' THEN 'CD'` | 1 | la numérica antes que los prefijos (equivalente) | test_f113_r10_la_raiz_completa_y_en_el_orden_del_dominio |
| M10 | `04_partidas.sql:143` | `WHEN p.cod ~ '^[0-9]+$' AND p.cod NOT IN ('34', '99') THEN 'CD'` | `WHEN p.cod ~ '[0-9]+' AND p.cod NOT IN ('34', '99') THEN 'CD'` | 2 | numérica sin anclas | test_f113_r10_la_raiz_completa_y_en_el_orden_del_dominio, test_f113_r10_la_raiz_numerica_con_las_excepciones_del_dominio |
| M11 | `04_partidas.sql:143` | `WHEN p.cod ~ '^[0-9]+$' AND p.cod NOT IN ('34', '99') THEN 'CD'` | `WHEN p.cod ~ '^[0-9]+$' AND p.cod IN ('34', '99') THEN 'CD'` | 2 | NOT IN -> IN | test_f113_r10_la_raiz_completa_y_en_el_orden_del_dominio, test_f113_r10_la_raiz_numerica_con_las_excepciones_del_dominio |
| M12 | `04_partidas.sql:143` | `WHEN p.cod ~ '^[0-9]+$' AND p.cod NOT IN ('34', '99') THEN 'CD'` | `WHEN p.cod ~ '^[0-9]+$' AND p.cod NOT IN ('34') THEN 'CD'` | 2 | fuera el '99' | test_f113_r10_la_raiz_completa_y_en_el_orden_del_dominio, test_f113_r10_la_raiz_numerica_con_las_excepciones_del_dominio |
| M13 | `04_partidas.sql:143` | `WHEN p.cod ~ '^[0-9]+$' AND p.cod NOT IN ('34', '99') THEN 'CD'` | `WHEN p.cod ~ '^[0-9]+$' AND p.cod NOT IN ('33', '99') THEN 'CD'` | 2 | '34' -> '33' | test_f113_r10_la_raiz_completa_y_en_el_orden_del_dominio, test_f113_r10_la_raiz_numerica_con_las_excepciones_del_dominio |
| M14 | `04_partidas.sql:143` | `WHEN p.cod ~ '^[0-9]+$' AND p.cod NOT IN ('34', '99') THEN 'CD'` | `WHEN p.cod ~ '^[0-9]+$' AND p.cod NOT IN ('34', '99') THEN 'OTRO'` | 2 | numérica -> OTRO | test_f113_r10_la_raiz_completa_y_en_el_orden_del_dominio, test_f113_r10_la_raiz_numerica_con_las_excepciones_del_dominio |
| M15 | `04_partidas.sql:144` | `ELSE 'OTRO' END)::TEXT     AS categoria` | `ELSE 'CD' END)::TEXT     AS categoria` | 1 | ELSE 'OTRO' -> ELSE 'CD' | test_f113_r10_la_raiz_completa_y_en_el_orden_del_dominio |
| M16 | `04_partidas.sql:144` | `ELSE 'OTRO' END)::TEXT     AS categoria` | `ELSE 'OTRO' END)     AS categoria` | 1 | sin ::TEXT en la raíz | test_f113_r10_la_raiz_completa_y_en_el_orden_del_dominio |
| M17 | `04_partidas.sql:144` | `ELSE 'OTRO' END)::TEXT     AS categoria` | `ELSE 'OTRO' END)::TEXT     AS categoria_raiz` | 3 | la raíz proyecta otro nombre | test_f052_las_dos_ramas_del_recursivo_proyectan_lo_mismo_y_en_el_mismo_orden, test_f113_r10_la_raiz_completa_y_en_el_orden_del_dominio, test_f113_r7_categoria_en_las_dos_ramas_y_en_la_misma_posicion |
| M18 | `04_partidas.sql:175` | `IN ('CD', 'CI', 'CP')` | `IN ('CD', 'CI')` | 1 | fuera CP de la lista exacta | test_f113_r10_el_intermedio_compara_el_codigo_limpio_con_la_lista_exacta |
| M19 | `04_partidas.sql:177` | `ELSE a.categoria END)::TEXT AS categoria` | `ELSE 'OTRO' END)::TEXT AS categoria` | 2 | el intermedio no hereda: ELSE 'OTRO' | test_f113_r10_el_intermedio_compara_el_codigo_limpio_con_la_lista_exacta, test_f113_r5_el_intermedio_no_usa_prefijo |
| M20 | `04_partidas.sql:177` | `ELSE a.categoria END)::TEXT AS categoria` | `ELSE a.capitulo_raiz_cod END)::TEXT AS categoria` | 2 | hereda el código de la raíz, no su categoría | test_f113_r10_el_intermedio_compara_el_codigo_limpio_con_la_lista_exacta, test_f113_r5_el_intermedio_no_usa_prefijo |
| M21 | `04_partidas.sql:174` | `(CASE WHEN UPPER(REPLACE(REPLACE(h.cod, '.', ''), ' ', ''))` | `(CASE WHEN UPPER(REPLACE(h.cod, ' ', ''))` | 2 | WHEN sin quitar puntos (C.I. deja de contar) | test_f113_r10_el_intermedio_compara_el_codigo_limpio_con_la_lista_exacta, test_f113_r10_un_replace_por_cada_caracter_ignorado |
| M22 | `04_partidas.sql:176` | `THEN UPPER(REPLACE(REPLACE(h.cod, '.', ''), ' ', ''))` | `THEN UPPER(REPLACE(h.cod, '.', ''))` | 2 | THEN sin quitar espacios | test_f113_r10_el_intermedio_compara_el_codigo_limpio_con_la_lista_exacta, test_f113_r10_un_replace_por_cada_caracter_ignorado |
| M23 | `04_partidas.sql:176` | `THEN UPPER(REPLACE(REPLACE(h.cod, '.', ''), ' ', ''))` | `THEN a.categoria` | 2 | el intermedio exacto no manda nunca | test_f113_r10_el_intermedio_compara_el_codigo_limpio_con_la_lista_exacta, test_f113_r10_un_replace_por_cada_caracter_ignorado |
| M24 | `04_partidas.sql:174` | `(CASE WHEN UPPER(REPLACE(REPLACE(h.cod, '.', ''), ' ', ''))` | `(CASE WHEN (REPLACE(REPLACE(h.cod, '.', ''), ' ', ''))` | 1 | sin UPPER en el intermedio | test_f113_r10_el_intermedio_compara_el_codigo_limpio_con_la_lista_exacta |
| M25 | `04_partidas.sql:175` | `IN ('CD', 'CI', 'CP')` | `LIKE ANY (ARRAY['CD%', 'CI%', 'CP%'])` | 2 | prefijo en los intermedios (CI10 pasaría a CI) | test_f113_r10_el_intermedio_compara_el_codigo_limpio_con_la_lista_exacta, test_f113_r5_el_intermedio_no_usa_prefijo |
| M26 | `04_partidas.sql:177` | `ELSE a.categoria END)::TEXT AS categoria` | `ELSE a.categoria END) AS categoria` | 1 | sin ::TEXT en la recursiva | test_f113_r10_el_intermedio_compara_el_codigo_limpio_con_la_lista_exacta |
| M27 | `04_partidas.sql:199` | `categoria, ⏎     ruta_capitulos, ⏎     nivel,` | `'OTRO' AS categoria, ⏎     ruta_capitulos, ⏎     nivel,` | 1 | el INSERT no copia la categoría del recursivo | test_f113_r7_el_insert_toma_la_categoria_del_recursivo |
| D01 | `categoria_partida.py:43` | `CATEGORIAS_DE_CAPITULO: tuple[str, ...] = ("CD", "CI", "CP")` | `CATEGORIAS_DE_CAPITULO: tuple[str, ...] = ("CD", "CI")` | 10 | fuera CP de las categorías | test_f113_r10_constantes_de_la_regla, test_f113_r10_el_intermedio_compara_el_codigo_limpio_con_la_lista_exacta, test_f113_r10_la_raiz_completa_y_en_el_orden_del_dominio (+7) |
| D02 | `categoria_partida.py:47` | `RAICES_NUMERICAS_FUERA: tuple[str, ...] = ("34", "99")` | `RAICES_NUMERICAS_FUERA: tuple[str, ...] = ("34",)` | 5 | fuera el 99 | test_f113_r10_constantes_de_la_regla, test_f113_r10_la_raiz_completa_y_en_el_orden_del_dominio, test_f113_r10_la_raiz_numerica_con_las_excepciones_del_dominio (+2) |
| D03 | `categoria_partida.py:50` | `CATEGORIA_DE_RAIZ_NUMERICA = "CD"` | `CATEGORIA_DE_RAIZ_NUMERICA = "CI"` | 12 | numérica -> CI | test_f113_r10_constantes_de_la_regla, test_f113_r10_la_raiz_completa_y_en_el_orden_del_dominio, test_f113_r10_la_raiz_numerica_con_las_excepciones_del_dominio (+9) |
| D04 | `categoria_partida.py:54` | `CARACTERES_IGNORADOS_EN_INTERMEDIO: tuple[str, ...] = (".", " ")` | `CARACTERES_IGNORADOS_EN_INTERMEDIO: tuple[str, ...] = (".",)` | 4 | no se quitan espacios | test_f113_r10_constantes_de_la_regla, test_f113_r10_el_intermedio_compara_el_codigo_limpio_con_la_lista_exacta, test_f113_r4_codigo_exacto_sin_puntos_ni_espacios[ (+1) |
| D05 | `categoria_partida.py:57` | `OTRO = "OTRO"` | `OTRO = "OTROS"` | 2 | otro literal de OTRO | test_f113_r10_constantes_de_la_regla, test_f113_r10_la_raiz_completa_y_en_el_orden_del_dominio |
| D06 | `categoria_partida.py:60` | `_NUMERICO_PURO = re.compile(r"[0-9]+")` | `_NUMERICO_PURO = re.compile(r"[0-9]*")` | 1 | la cadena vacía cuenta como numérica | test_f113_r2_el_resto_es_otro[] |
| D07 | `categoria_partida.py:65` | `mayusculas = cod.upper()` | `mayusculas = cod` | 5 | sin mayúsculas en la raíz | test_f113_r1_minusculas_igual_que_mayusculas[Cd-fii-CD], test_f113_r1_minusculas_igual_que_mayusculas[cI.f2-CI], test_f113_r1_minusculas_igual_que_mayusculas[cd-CD] (+2) |
| D08 | `categoria_partida.py:67` | `if mayusculas.startswith(categoria):` | `if categoria in mayusculas:` | 10 | vuelve el defecto: letras en cualquier posición | test_f113_r1_el_prefijo_es_el_principio_del_codigo[, test_f113_r1_el_prefijo_es_el_principio_del_codigo[.CI], test_f113_r1_el_prefijo_es_el_principio_del_codigo[1CD] (+7) |
| D09 | `categoria_partida.py:69` | `if _NUMERICO_PURO.fullmatch(cod) and` | `if _NUMERICO_PURO.match(cod) and` | 3 | numérica solo al principio (match) | test_f113_r1_el_prefijo_es_el_principio_del_codigo[1CD], test_f113_r2_el_resto_es_otro[01.], test_f113_r2_el_resto_es_otro[1a] |
| D10 | `categoria_partida.py:69` | `and cod not in RAICES_NUMERICAS_FUERA:` | `and cod in RAICES_NUMERICAS_FUERA:` | 13 | not in -> in | test_f113_r2_las_raices_34_y_99_son_otro[34], test_f113_r2_las_raices_34_y_99_son_otro[99], test_f113_r2_raiz_numerica_pura_es_cd[01] (+10) |
| D11 | `categoria_partida.py:70` | `return CATEGORIA_DE_RAIZ_NUMERICA` | `return OTRO` | 9 | numérica -> OTRO | test_f113_r2_raiz_numerica_pura_es_cd[01], test_f113_r2_raiz_numerica_pura_es_cd[02], test_f113_r2_raiz_numerica_pura_es_cd[034] (+6) |
| D12 | `categoria_partida.py:68` | `return categoria ⏎     if _NUMERICO` | `return OTRO ⏎     if _NUMERICO` | 39 | el prefijo devuelve OTRO | test_f113_r1_las_variantes_medidas_conservan_su_categoria[CD, test_f113_r1_las_variantes_medidas_conservan_su_categoria[CD'-CD], test_f113_r1_las_variantes_medidas_conservan_su_categoria[CD-CD] (+36) |
| D13 | `categoria_partida.py:79` | `limpio = limpio.replace(caracter, "")` | `limpio = limpio.replace(caracter, "_")` | 6 | el carácter ignorado se sustituye en vez de quitarse | test_f113_r3_r4_r5_r9_construir_arbol_publica_la_categoria[codigos2-esperadas2], test_f113_r4_codigo_exacto_sin_puntos_ni_espacios[, test_f113_r4_codigo_exacto_sin_puntos_ni_espacios[C (+3) |
| D14 | `categoria_partida.py:80` | `limpio = limpio.upper() ⏎` | `` | 1 | sin mayúsculas en el intermedio | test_f113_r4_codigo_exacto_sin_puntos_ni_espacios[ci-CI] |
| D15 | `categoria_partida.py:81` | `if limpio in CATEGORIAS_DE_CAPITULO:` | `if limpio.startswith(CATEGORIAS_DE_CAPITULO):` | 24 | prefijo en los intermedios | test_f113_r3_r4_r5_r9_construir_arbol_publica_la_categoria[codigos0-esperadas0], test_f113_r3_r4_r5_r9_construir_arbol_publica_la_categoria[codigos1-esperadas1], test_f113_r3_r4_r5_r9_construir_arbol_publica_la_categoria[codigos10-esperadas10] (+21) |
| D16 | `categoria_partida.py:82` | `return limpio ⏎` | `return categoria_padre ⏎` | 17 | el intermedio exacto no manda | test_f113_r3_r4_r5_r9_construir_arbol_publica_la_categoria[codigos0-esperadas0], test_f113_r3_r4_r5_r9_construir_arbol_publica_la_categoria[codigos1-esperadas1], test_f113_r3_r4_r5_r9_construir_arbol_publica_la_categoria[codigos2-esperadas2] (+14) |
| D17 | `categoria_partida.py:83` | `return categoria_padre ⏎` | `return OTRO ⏎` | 39 | el intermedio no hereda | test_f113_r3_r4_r5_r9_construir_arbol_publica_la_categoria[codigos0-esperadas0], test_f113_r3_r4_r5_r9_construir_arbol_publica_la_categoria[codigos1-esperadas1], test_f113_r3_r4_r5_r9_construir_arbol_publica_la_categoria[codigos10-esperadas10] (+36) |
| D18 | `arbol_partidas.py:218` | `categoria = categoria_de_raiz(cod)` | `categoria = "CD"` | 9 | la raíz no se clasifica | test_f113_r3_r4_r5_r9_construir_arbol_publica_la_categoria[codigos1-esperadas1], test_f113_r3_r4_r5_r9_construir_arbol_publica_la_categoria[codigos14-esperadas14], test_f113_r3_r4_r5_r9_construir_arbol_publica_la_categoria[codigos15-esperadas15] (+6) |
| D19 | `arbol_partidas.py:264` | `categoria = categoria_heredada(hijo.cod, paso.categoria)` | `categoria = paso.categoria` | 8 | el árbol ignora el intermedio exacto | test_f113_r3_r4_r5_r9_construir_arbol_publica_la_categoria[codigos0-esperadas0], test_f113_r3_r4_r5_r9_construir_arbol_publica_la_categoria[codigos1-esperadas1], test_f113_r3_r4_r5_r9_construir_arbol_publica_la_categoria[codigos2-esperadas2] (+5) |
| D20 | `arbol_partidas.py:299` | `visitados=paso.visitados \| {hijo.ide}, ⏎                         categoria=categoria,` | `visitados=paso.visitados \| {hijo.ide}, ⏎                         categoria=paso.categoria,` | 7 | el paso no arrastra la del intermedio a sus hijos | test_f113_r3_r4_r5_r9_construir_arbol_publica_la_categoria[codigos0-esperadas0], test_f113_r3_r4_r5_r9_construir_arbol_publica_la_categoria[codigos1-esperadas1], test_f113_r3_r4_r5_r9_construir_arbol_publica_la_categoria[codigos2-esperadas2] (+4) |

## Lo que esta campaña NO prueba

Los tests del SQL son de TEXTO: construyen el `CASE` esperado desde las
constantes del dominio y matan cualquier cambio del texto, también los
**equivalentes** (M08 y M09 cambian el orden de `WHEN` mutuamente excluyentes:
mismo resultado, pero el texto deja de ser el del dominio; falso positivo, no
falso verde). Que la expresión haga lo que debe contra datos reales lo cubre T5:
la consulta del árbol nuevo, en solo lectura contra Azure, reproduce la tabla de
la spec celda a celda y deja 0 cambios en las otras diez columnas
(`progress/impl_F-113.md`, T5).
