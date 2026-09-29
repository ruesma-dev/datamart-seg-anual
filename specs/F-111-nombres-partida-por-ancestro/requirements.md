<!-- specs/F-111-nombres-partida-por-ancestro/requirements.md -->
# F-111 · Requisitos — el nombre de cada escalón sale del ancestro real, no del código

EARS; cada R >= 1 test `test_f111_rN_...` en `tests/test_f111_nombres_por_ancestro.py`,
**sin red ni BBDD** salvo las marcadas **MANUAL**. Rigor `estandar`. Origen: la
decisión D3 del humano sobre F-109 (2026-09-26). Cifras **medidas en solo lectura
el 2026-09-26** sobre `sigrid_dm` (build de `stg` de las 01:56 UTC): `design.md` §1.
Los R marcados **[Dn]** dependen de la decisión abierta n (`design.md` §11) y se
escriben con la opción recomendada.

## Lo medido (hoy)

- `mart.v_pbi_dim_partida_niveles` (394.046 filas): **10.560 filas** enseñan algún
  escalón con un nombre que no es el de su ancestro real (4.624 en obras con
  seguimiento, 67 obras); el día 25 F-109 midió 10.593 / 4.657. Por escalón:
  4.720 / 4.165 / 3.186 / 1.496 / 166 / 24. Casos: 0626 `CD` sale «INSTALACIONES»
  y es «COSTES DIRECTOS» (1.921 filas); 0404 `CD > 6` sale «PARTICIONES» y es
  «FASE 6» (113); 0407 `CD > EXTRAS > 99.02` sale «JARDINERÍA» y es «INSTALACIÓN
  DE ELECTRICIDAD E ILUMINACIÓN» (224).
- La cadena `capitulo_padre_id` cuadra al 100 % con `ruta_capitulos` (0 descuadres
  en 394.046 filas; nivel máximo 7): el ancestro de cada segmento existe y es único.
- Dimensión CI (47.636 filas): **156 cambian de nombre** (11 en obras del
  seguimiento, todas grupos que funden varios nodos; 145 fuera, 138 de una sola
  obra con raíz `AVDA_FRANCIA`); detalle de indirectos: **117 filas**, todas de la
  0444 (`CI.1.1`, `CI.1.2`, `CI.6.5`). La cifra «22» de F-109 no se reproduce con
  una definición explícita (`design.md` §1.3). **0 banderas `es_infraestructura`
  cambian**, luego 0 importes.

## Árbol de partidas (`mart.v_pbi_dim_partida_niveles`)

R1. El sistema debe resolver el nombre de `nivel_k` como la `descripcion_corta`
del ancestro de la partida situado a profundidad `k-1`, alcanzado por
`capitulo_padre_id` (la propia partida cuando `k = nivel + 1`), y nunca por
`(obra_id, codigo_partida)`.

R2. El sistema debe conservar el formato y el grano de la vista: el código de
cada escalón es el segmento `k` de `ruta_capitulos`, la etiqueta es `código · nombre`
(`código · ` si el nombre es cadena vacía, como hoy), `NULL` si la rama no llega,
mismas columnas y en el mismo orden, una fila por `partida_id`.

R3. El sistema debe resolver el ancestro sin tope de profundidad por debajo de
`TOPE_DE_PROFUNDIDAD` (40, `etl_sigrid/domain/arbol_partidas.py`), el mismo que
corta el recursivo de `stg/04_partidas.sql`.

R4. `partida_label`, `es_hoja` y el resto de columnas que no son `nivel_1..6`
no deben cambiar de valor (la guarda de `es_hoja` de F-006 sigue verde).

## Costes indirectos (`cierre/04_views_detalle.sql`)

R5. El sistema debe resolver `grupo_nombre` de `(obra_id, grupo_cod)` con la
descripción de los nodos REALES de nivel 1 de las partidas CI de ese grupo (la
propia raíz para una partida de nivel 0) y `subcategoria_nombre` de
`(obra_id, grupo_cod, subcategoria_cod)` con los de nivel 2, alcanzados por
`capitulo_padre_id`.

R6. [D2] SI los nodos reales de un grupo o subcategoría tienen descripciones
distintas, ENTONCES el nombre debe ser todas ellas, sin repetir, ordenadas por
punto de código (`COLLATE "C"`) y unidas por ` / `; SI tienen una sola, esa.

R7. `cierre.v_pbi_dim_subcategoria_ci` y `cierre.v_pbi_cierre_indirectos_detalle`
deben dar el MISMO nombre para la misma `(obra_id, grupo_cod, subcategoria_cod)`;
el detalle deja de resolver la subcategoría solo por `(obra, subcategoria_cod)`.

R8. [D1] El sistema debe conservar el grano de las dos vistas (claves
`(obra_id, grupo_cod, subcategoria_cod)` y `(obra_id, anio_mes, grupo_cod,
subcategoria_cod)`), sus columnas, los respaldos `'CI'` / `'(sin detalle)'` y
toda expresión de importe; `es_infraestructura` se sigue decidiendo con
`LIKE '%INFRA%'` sobre `grupo_nombre`, ahora el de R5.

## Ninguna resolución por código (inventario y trinquete)

R9. Ningún fichero de `etl_sigrid/infrastructure/postgres/sql/**` debe agrupar
por `obra_id, codigo_partida` (con o sin alias) ni unir con
`codigo_partida = <alias>.<columna>`; la lista permitida del trinquete de F-109
(R15) pasa de dos ficheros a **vacía**.

R10. El test del trinquete debe nombrar el fichero intruso en un caso sintético
(`tmp_path`) de cada una de las dos formas de R9.

## Regla equivalente, ejecutable (dominio)

R11. `etl_sigrid/domain/nombres_arbol.py` debe ofrecer, en Python puro, la regla
de R1-R3 (`escalones`) y la de R5-R6 (`catalogo_ci`), y los tests deben
demostrarla con fixtures que reproducen 0626 (raíz `CD` y otra partida `CD`),
0404 (`CD > 6` «FASE 6» frente a otro `6`), las raíces `CI` / `CI-FII` de la 0444,
hermanas homónimas y un nodo con descripción vacía.

R12. SI un nodo apunta a un padre inexistente o la cadena supera
`TOPE_DE_PROFUNDIDAD`, ENTONCES el dominio debe lanzar `ValueError` nombrando el
`partida_id` (el SQL no lo puede denunciar; el modelo sí).

R13. Los tests de texto deben fijar que el SQL dice lo mismo que el modelo: en
`mart/05b_...` y `cierre/04_...` no queda `MAX(descripcion_corta)` ni CTE
`nom` / `nombres_por_obra`; ambos recorren `capitulo_padre_id` con
`WITH RECURSIVE` y el tope 40; `string_agg(DISTINCT ... COLLATE "C", ' / ' ...)`
en las dos vistas CI; `UPPER(COALESCE(ng.grupo_nombre, a.grupo_cod))` sigue
apareciendo 7 veces (1 `LIKE` y 6 `NOT LIKE '%INFRA%'`); y el nombre del mes se
sigue derivando 2 veces en `cierre/04` (guarda de F-019).

## Diccionario y documentación

R14. Las fichas `mart.v_pbi_dim_partida_niveles.nivel_1..6` deben decir que el
nombre sale del ancestro por `capitulo_padre_id` (F-111, 2026-09-26) y dejar de
decir `(obra, codigo)` y `MAX(descripcion_corta)`; `partida_label` de esa vista
debe avisar de las homónimas como la de `v_pbi_dim_partida` (observación 2 del
review de F-109).

R15. Las fichas de `grupo_nombre` y `subcategoria_nombre` de
`cierre.v_pbi_dim_subcategoria_ci` y `cierre.v_pbi_cierre_indirectos_detalle`
deben decir que el nombre es el del ancestro real, que el grupo se AGRUPA por
código a propósito (las fases `CI` / `CI-FII` de la 0444 y de la 0517 suman
juntas; D1 abierta con Negocio) y que un grupo que funde nodos de nombre distinto
los enseña unidos por ` / `.

R16. La regla `R-PARTIDA-CODIGO-NO-UNICO` debe añadir
`cierre.v_pbi_cierre_indirectos_detalle` a su ámbito (observación 1 del review de
F-109) sin tocar su texto `regla`, que es el aprobado por el humano.

R17. `00_global.yaml` debe subir `version` a la siguiente de `main` al fusionar
(35 hoy) con su historia en cabeza, y `docs/ARCHITECTURE.md` debe dejar de decir
que dos vistas resuelven el nombre por código.

R18. Los tests de F-109 que fijaban el estado anterior (`r13`, `r14`: el aviso
«nombre por código» y la mención a F-111) deben retirarse o reescribirse en el
mismo commit que cambia las fichas, diciendo que los sustituye F-111.

## Verificación contra la base (MANUAL)

R19. MANUAL (humano o implementer, SOLO LECTURA, antes de desplegar): el cuerpo
nuevo de cada vista, ejecutado como `SELECT` en transacción `READ ONLY`, frente a
la vista vigente por clave: mismas filas; solo cambian `nivel_1..6`,
`grupo_nombre`, `subcategoria_nombre` y `orden_*` en el orden de magnitud de §1;
0 banderas `es_infraestructura` distintas.

R20. MANUAL (humano, tras el despliegue): contrastar en el «Árbol Presupuesto» de
Power BI las obras 0626, 0404 y 0444 antes y después, y confirmar qué columnas
lee el visual (el `.pbix` no está en el repositorio).

R21. MANUAL (humano): `python main.py publicar-diccionario` con la versión de R17
y reinicio de `mcp-bbdd`; `_meta.v_diccionario` sirve las fichas de R14-R16.
