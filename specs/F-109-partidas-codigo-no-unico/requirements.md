<!-- specs/F-109-partidas-codigo-no-unico/requirements.md -->
# F-109 · Requisitos — el código de partida NO es único dentro de su obra

EARS; cada R >= 1 test `test_f109_rN_...` en `tests/test_f109_partidas_codigo.py`,
**sin red ni BBDD** salvo las marcadas **MANUAL**. Rigor `estandar`. Origen: el
hallazgo H1 del spec-author de F-108 (`progress/spec_F-108.md`). Cifras
**medidas en solo lectura el 2026-09-25** (MCP y consultas `READ ONLY` sobre
`sigrid_dm`): `design.md` §1. Los requisitos marcados **[D1]**, **[D2]**, **[D3]**
o **[D5]** dependen de la decisión abierta de ese número (`design.md` §8) y se
escriben con la opción recomendada.

## Lo que se ha medido (criterio 1 de la ficha)

`(obra_id, codigo_partida)` se repite en **5.202 pares** (4.017 dos veces, 1.185
tres o más, máximo 22), **8.933 filas de más**, **158 obras** (92 del
seguimiento, 2.177 pares), idéntico en `stg.partidas` y `mart.v_pbi_dim_partida`
(394.035 filas). Todas las filas repetidas son partidas activas y distintas en
Sigrid (`partida_id` distinto). Tres causas, ninguna de ellas un defecto del ETL:

- **D · subárbol copiado bajo otro capítulo** (2.713 pares, 6.043 filas, 135
  obras): el jefe de obra replica el capítulo por bloque o portal y conserva los
  códigos. 0560: `1.1.3.2 HORM. HA-25` cuelga de once capítulos distintos.
- **B · otra raíz** (2.340 pares, 2.739 filas, 19 obras): árboles por fase con
  raíz propia (0444 `CD` y `CD-FII`, `CI` y `CI-FII`; 0692 `CI` y `CI.F2`), o una
  raíz que copia un capítulo (0515 raíz `2` y `CD > 2`).
- **A · misma ruta** (149 pares, 151 filas, 23 obras): hermanas con el mismo
  código, casi siempre marcadores (`N/A`, `----------`, código de solo espacios)
  o errores de tecleo (0510 `04.04.14` dos veces), y raíces duplicadas.

Descartado con el dato: códigos vacíos, versiones, ámbitos coste/venta
(`tipvis`, `parcoside`/`parvenide`), copias de MenfisNet (`parideori`), copias
por empresa (`R-CODIGO-POR-EMPRESA`: el par vive dentro de un `obra_id`, que es
una ficha) y el colapso de F-052 (0 de las 14.135 filas implicadas está colapsada).

## Las fichas dicen la verdad (criterio 3)

R1. La ficha de `stg.partidas`, columna `obra_id`, NO debe afirmar que el código
de partida sea único dentro de la obra, y debe decir que la partida se
identifica por `partida_id`.

R2. La ficha de `mart.v_pbi_dim_partida`, columna `obra_id`, debe cumplir lo
mismo que R1.

R3. La ficha de `mart.fact_seguimiento_mensual`, columna `codigo_partida`, NO
debe decir «único por obra» y debe decir que para identificar o unir una
partida se usa `partida_id`.

R4. El sistema debe garantizar que NINGUNA ficha de `config/diccionario/`
atribuye unicidad al código de partida dentro de la obra (frases «único por
obra», «solo son únicos dentro de su obra» y equivalentes, con o sin tildes).

R5. La ficha de `stg.partidas`, columna `codigo_partida`, debe decir que el
código NO es único dentro de la obra, con la cifra medida (5.202 pares, 158
obras) y su fecha, y las tres causas (subárbol copiado, otra raíz, misma ruta).

R6. [D5] La ficha de `stg.partidas`, columna `codigo_partida`, NO debe afirmar
«nunca vacío» sin matizar: 2 filas traen un código de solo espacios, que el
filtro `cod <> ''` deja pasar.

R7. [D1] La ficha de `stg.partidas`, columna `ruta_capitulos`, debe decir que
`(obra_id, ruta_capitulos)` es CASI única —155 pares, 162 filas de más, 25
obras (38 pares en 21 obras del seguimiento)— y que por eso sirve para leer y
navegar, no para unir.

R8. La ficha de `compras.v_pbi_partida_coste`, columna `codigo_partida`, y la de
`mart.v_pbi_dim_partida`, columnas `codigo_partida` y `partida_label`, deben
decir que el código no identifica la partida y que se une por `partida_id`; la de
`partida_label`, además, que dos partidas homónimas dan la misma etiqueta
(4.127 pares comparten código y descripción) y un segmentador las suma juntas.

## La regla dura (criterio 4 y el riesgo de la ficha) [D2]

R9. El diccionario debe declarar la regla `R-PARTIDA-CODIGO-NO-UNICO`,
`bloqueante`, con ámbito al menos `stg.partidas`, `mart.v_pbi_dim_partida`,
`mart.v_pbi_dim_partida_niveles`, `mart.fact_seguimiento_mensual`,
`mart.v_fact_periodificado`, `compras.v_pbi_partida_coste` y
`cierre.v_pbi_dim_subcategoria_ci`.

R10. El texto de la regla debe ordenar unir y contar partidas por `partida_id`,
nunca por `(obra, codigo_partida)`, y citar las cifras medidas: 5.202 pares y el
caso de la obra 0437, cuyo coste real (883.460,55 EUR) sale 3.474.491,83 EUR
uniendo el hecho con la dimensión por obra y código.

R11. CUANDO se derivan los avisos del diccionario real (`derivar_avisos`), cada
ficha del ámbito de R9 debe llevar `R-PARTIDA-CODIGO-NO-UNICO` entre sus avisos.

R12. El diccionario real con la regla nueva debe validar sin errores
(`validar`), y la regla debe cumplir las exigencias de F-006 (texto >= 40,
motivo >= 30, ámbito resoluble).

## Los nombres resueltos por código (criterio 4, efecto medido) [D3]

R13. La ficha de `mart.v_pbi_dim_partida_niveles` (columnas `nivel_1` a
`nivel_6`) debe decir que el nombre de cada escalón se resuelve por
`(obra, código)` con `MAX(descripcion_corta)`, así que puede ser el de otra
partida homónima: 10.593 filas (4.657 del seguimiento) muestran al menos un
escalón con el nombre de otra partida.

R14. La ficha de `cierre.v_pbi_dim_subcategoria_ci` (`grupo_nombre`,
`subcategoria_nombre`) debe decir que un grupo o subcategoría se identifica por
su CÓDIGO, así que capítulos homónimos de la misma obra —las dos fases de 0444,
`CI` y `CI-FII`— se funden en una fila con un solo nombre.

R15. El sistema debe mantener cerrada la lista de ficheros SQL que resuelven
algo por `(obra_id, codigo_partida)`: un test barre `sql/**` buscando
`GROUP BY obra_id, codigo_partida` y exige exactamente
`cierre/04_views_detalle.sql` y `mart/05b_view_dim_partida_niveles.sql`. SI
aparece otro, ENTONCES el test falla y nombra el fichero (trinquete: solo baja).

## Versión y documentación

R16. `config/diccionario/00_global.yaml` debe subir `version` a la siguiente a la
de `main` en el momento de fusionar (hoy 32 -> 33; ver D4) con su comentario de
historia, y el test no debe clavar el número exacto (`>= 33`).

R17. `docs/ARCHITECTURE.md`, sección «Semántica Sigrid imprescindible», debe
llevar una entrada «el código de partida no es único ni dentro de su obra
(F-109)» con las tres causas y la orden de unir por `partida_id`.

Ningún SQL cambia en esta feature (`design.md` §3); no es un requisito con test
sino un límite de alcance que comprueba el reviewer con `git diff main --stat`.

## Verificación contra la base (MANUAL, humano)

R18. MANUAL: tras `python main.py publicar-diccionario` (escritura contra Azure,
la autoriza el humano) y el reinicio del MCP, `_meta.v_diccionario` sirve las
fichas corregidas y `_meta.diccionario_reglas` la regla nueva; y la consulta de
`design.md` §7 devuelve de nuevo ~5.200 pares (la cifra se mueve con Sigrid).
