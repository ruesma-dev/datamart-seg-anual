<!-- specs/F-111-nombres-partida-por-ancestro/design.md -->
# F-111 · Diseño — nombres de escalón por el ancestro real

## 1. Medidas (solo lectura, 2026-09-26; build de `stg` 01:56 UTC)

Consultas `READ ONLY` (scratchpad, `.env` del repositorio principal) y el MCP;
nada versionado ni creado. Comparan lo que enseña HOY la vista con §3-§4.

**1.1 La cadena de padres es fiable.** Sobre 394.046 partidas: 2.514 raíces, 0
padres inexistentes, 0 filas donde `ruta = ruta_del_padre || ' > ' || codigo`
falle, 0 con `nivel <> nivel_del_padre + 1`; nivel máximo 7 (5.905 filas de
nivel >= 6: la vista solo enseña 6 escalones, y eso no cambia).

**1.2 Niveles** (`mart.v_pbi_dim_partida_niveles`, 394.046 filas):

| Escalón | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| Filas que cambian de nombre | 4.720 | 4.165 | 3.186 | 1.496 | 166 | 24 |
| Etiquetas distintas (obra, valor) hoy | 2.510 | 25.373 | 151.472 | 114.327 | 57.709 | 30.226 |
| … con la propuesta | 2.510 | 25.466 | 151.755 | 114.861 | 57.832 | 30.241 |
| Nodos del árbol (prefijo `nivel_1..k` distinto) hoy | 2.510 | 25.575 | 152.446 | 116.980 | 59.602 | 30.866 |
| … con la propuesta | 2.510 | 25.575 | 152.463 | 116.993 | 59.612 | 30.869 |

Total **10.560 filas** (67 obras; 4.624 filas en 54 obras con hecho en
`mart.fact_seguimiento_mensual`; 3.280 son partidas con hecho). Ninguna pasa de
nombre vacío a lleno; 7 pasan de un nombre prestado a su nombre real, que es
cadena vacía (0560 `1.1.9.8` bajo `1.2.9`). Ejemplos (hoy → propuesta, filas):

| Obra | Escalón | Hoy | Real | Filas |
|---|---|---|---|---|
| 0626 | `CD` | INSTALACIONES | COSTES DIRECTOS | 1.921 |
| 0404 | `CD > 6` | PARTICIONES | FASE 6 | 113 |
| 0404 | `CD > 6 > 1` | FASE 1 | ACTUACIONES PREVIAS | 22 |
| 0407 | `CD > EXTRAS > 99.02` | JARDINERÍA | INSTALACIÓN DE ELECTRICIDAD E ILUMINACIÓN | 224 |
| 0243 | `IG > 02` | FIRMES Y PAVIMENTOS | ESTACION DE BOMBEO | 131 |
| 0444 | `CD > 23` | ELECTRICIDAD Y ESPECIALES | ELECTRICIDAD E ILUMINACION(SOLO VENTA) | 103 |
| 0371 | `CD > URB2 > 02` | MOVIMIENTO DE TIERRAS | ESTRUCTURAS Y ALBAÑILERIA | 24 |
| 0367 | `CD > DEM > 02` | HORMIGONES. | CAMBIO DE ANTENAS ADOSADAS A PARED DE NAVE A DEMOLER | 71 |

**1.3 Costes indirectos.** Dimensión (47.636 filas, incluye obras fuera de
`stg.obras`): 156 filas cambian de nombre, 0 aparecen o desaparecen, **0 banderas
INFRA cambian**. En obras del seguimiento, 11, y todas son grupos que funden
nodos de nombre distinto: 0444 `CI.1.1` y `CI.1.2` (el cargo con y sin nombre
propio de persona en `CI` / `CI-FII`), 0444 `CI.6.5` (hoy «TRATAMIENTO DE
RESIDUOS-PROTECC M.A», de `CI-FII`, cuando TODO su coste es de `CI`, «GESTION DE
RESIDUOS»), y el respaldo `CI / (sin detalle)` de 0444, 0517, 0584, 0644, 0676,
0692, 0693 y 0694, que funde dos raíces CI (`CI` y `CI-FII`, `CIPD`, ...). Fuera
del seguimiento, 145: 138 de una obra cuya raíz `AVDA_FRANCIA` la heurística
`LIKE '%CI%'` clasifica como CI (hallazgo H1, §11), con nombres de grupo tomados
de otras partidas (`01` «TRABAJOS PREVIOS Y DEMOLICIONES» → «ACTUACIONES PREVIAS»).
Detalle de indirectos: **117 filas**, todas 0444 (40 + 40 + 37 meses). **Solo
dos obras tienen dos raíces CI con capítulos homónimos**: 0444 (cierre hasta
2019-12) y 0517 (sin cierre); 112 filas del catálogo funden sus dos fases. La
cifra «22» de F-109 no se reproduce con ninguna definición explícita; la de hoy
es esta, con su definición.

## 2. Inventario: quién resuelve algo por `(obra_id, codigo_partida)`

- **Resuelven NOMBRES por código (lo que arregla F-111)**: `mart/05b_view_dim_partida_niveles.sql`
  (CTE `nom`, 6 joins `n1..n6`) y `cierre/04_views_detalle.sql` (CTE
  `nombres_por_obra` dos veces: en la dimensión CI y en el detalle, donde alimenta
  `nombre_grupo` y `sub_nombres`). Son los dos de R15 de F-109: no hay más.
- **Agrupan importes por código a propósito** (no se tocan; se declara, D2 de
  F-109): el detalle de indirectos suma por `(obra, mes, grupo_cod,
  subcategoria_cod)`, lo que funde las fases de la 0444 y la 0517 (D1).
- **Fuera, y por qué**: `mart/06_cp_tipologia.sql`, `cp_tipologia_sql.py` y la
  vista de generales clasifican por el código de su PROPIA ruta; `mart/04_view_periodificado.sql`
  casa `codigo_partida LIKE patron_codigo` global y `aux.periodificacion_partida`
  tiene 0 reglas; Python, `compras/03_views.sql`, `harness/` e `infra/` van por
  `partida_id`. Nada depende de las tres vistas en la base (`pg_depend`: 0).

## 3. Niveles: SQL propuesto (`mart/05b_view_dim_partida_niveles.sql`)

Se sustituye el CTE `nom` y sus seis joins por un recursivo de arriba abajo que
acumula los nombres de la ruta; el resto del `SELECT` no cambia:

```sql
WITH RECURSIVE nombres_ruta AS (   -- nombres[k] = descripcion del ancestro de profundidad k-1
    SELECT partida_id, ARRAY[descripcion_corta]::TEXT[] AS nombres, 0 AS saltos
    FROM stg.partidas WHERE capitulo_padre_id IS NULL
    UNION ALL
    SELECT h.partida_id, r.nombres || h.descripcion_corta::TEXT, r.saltos + 1
    FROM nombres_ruta r JOIN stg.partidas h ON h.capitulo_padre_id = r.partida_id
    WHERE r.saltos < 40                       -- = TOPE_DE_PROFUNDIDAD (F-052)
), base AS ( ... + string_to_array(ruta_capitulos, ' > ') AS arr ... ),
cods AS ( SELECT b.*, (b.arr)[1] AS c1, ..., r.nombres FROM base b LEFT JOIN nombres_ruta r USING (partida_id) )
SELECT ...,
    CASE WHEN e.c1 IS NOT NULL THEN e.c1 || COALESCE(' · ' || e.nombres[1], '') END AS nivel_1,
    ... hasta nivel_6 con e.nombres[6]
```

`LEFT JOIN`, no `JOIN`: una partida que no bajara de una raíz desaparecería de la
dimensión y dejaría hechos sin partida en Power BI; con `LEFT` sale con el código
sin nombre, y R19 cuenta esas filas (hoy 0: §1.1, 394.046 alcanzadas y 0
descuadres entre `cardinality(nombres)` y la ruta). Alternativa medida y
descartada (D3): siete `LEFT JOIN` por `capitulo_padre_id` (2-3 s), topada en 7
saltos: un árbol más profundo perdería nombres sin avisar.

## 4. Costes indirectos: SQL propuesto (`cierre/04_views_detalle.sql`)

Un CTE común, escrito igual en las dos vistas (no hay vistas auxiliares
publicadas en `cierre` y no se crea una: pediría ficha y `GRANT`):

```sql
arbol_ci AS (   -- ids[k+1] = ancestro de nivel k
    SELECT p.partida_id, ARRAY[p.partida_id] AS ids, 0 AS saltos
    FROM stg.partidas p WHERE p.capitulo_padre_id IS NULL AND p.categoria = 'CI'
    UNION ALL
    SELECT h.partida_id, a.ids || h.partida_id, a.saltos + 1
    FROM arbol_ci a JOIN stg.partidas h ON h.capitulo_padre_id = a.partida_id
    WHERE a.saltos < 40
), partidas_ci AS ( ... grupo_cod, subcategoria_cod como hoy ...,
    COALESCE(a.ids[2], a.ids[1]) AS grupo_nodo_id, a.ids[3] AS subcategoria_nodo_id ),
nombre_grupo AS ( SELECT obra_id, grupo_cod,
    string_agg(DISTINCT g.descripcion_corta COLLATE "C", ' / '
               ORDER BY g.descripcion_corta COLLATE "C") AS grupo_nombre
    FROM partidas_ci JOIN stg.partidas g ON g.partida_id = grupo_nodo_id GROUP BY 1, 2 ),
nombre_subcategoria AS ( ... igual con subcategoria_nodo_id, GROUP BY obra_id, grupo_cod, subcategoria_cod )
```

- **`partidas_ci` une `arbol_ci` con `LEFT JOIN`** sobre `stg.partidas WHERE
  categoria = 'CI'`: en el detalle, un `JOIN` que perdiera una partida perdería
  su importe. Hoy las dos formas dan el mismo catálogo (medido: 0 filas de más o
  de menos), pero la seguridad no puede depender del dato.
- **Dimensión**: `catalogo` sale de `partidas_ci` (mismo `DISTINCT`); los joins
  `ng` / `ns` pasan a `nombre_grupo` por `(obra, grupo_cod)` y a
  `nombre_subcategoria` por `(obra, grupo_cod, subcategoria_cod)`. `COALESCE` al
  código, `'(sin detalle)'`, `orden_grupo` y `orden_subcategoria`: igual.
- **Detalle**: el `partidas_ci` actual gana los dos `*_nodo_id`; `nombres_por_obra`,
  su `nombre_grupo` y `sub_nombres` desaparecen; `combinado` une `ng` a
  `nombre_grupo` (conserva el alias `ng` y la columna `grupo_nombre`: R13) y el
  `SELECT` final une la subcategoría por `(obra, grupo_cod, subcategoria_cod)`.
  `agregado`, `fase0_*`, `venta_por_mes`, `plazo_obra`, `primer_mes_incurrido`,
  `con_lag` y todas las expresiones de importe: **intactos** (R8).
- El comentario de cabecera (Tanda 4) se corrige: el nombre ya no se resuelve
  por `(obra_id, codigo_partida)`, sino por el ancestro, y se dice por qué.

## 5. Dominio: `etl_sigrid/domain/nombres_arbol.py` (nuevo)

Mismo patrón que `domain/arbol_partidas.py` frente a `stg/04_partidas.sql` (F-052):
la regla se prueba con fixtures y el SQL se comprueba sobre su texto.

```python
@dataclass(frozen=True)
class NodoArbol:
    partida_id: int; obra_id: int; codigo: str; padre_id: int | None
    descripcion: str; ruta: str; categoria: str

def escalones(nodos: Iterable[NodoArbol], niveles: int = 6) -> dict[int, tuple[str | None, ...]]
    """R1-R3: por partida, las `niveles` etiquetas `código · nombre` (None si no llega)."""
def nombre_fundido(nombres: Iterable[str]) -> str
    """R6: distintos, ordenados por punto de código, unidos por ' / '."""
def catalogo_ci(nodos: Iterable[NodoArbol]) -> dict[tuple[int, str, str], tuple[str, str]]
    """R5-R6: (obra, grupo_cod, subcategoria_cod) -> (grupo_nombre, subcategoria_nombre)."""
```

Reutiliza `SEPARADOR_DE_RUTA` y `TOPE_DE_PROFUNDIDAD` de `arbol_partidas.py`
(importar dentro de `domain` es legítimo). Padre inexistente o cadena por encima
del tope: `ValueError` con el `partida_id` (R12). Sin I/O, sin `print`.

## 6. Ficheros

**Crear**: `etl_sigrid/domain/nombres_arbol.py` (§5);
`tests/test_f111_nombres_por_ancestro.py` (§7).

| Modificar | Cambio |
|---|---|
| `etl_sigrid/infrastructure/postgres/sql/mart/05b_view_dim_partida_niveles.sql` | §3; cabecera y `COMMENT ON VIEW` dicen «por el ancestro» |
| `etl_sigrid/infrastructure/postgres/sql/cierre/04_views_detalle.sql` | §4, en las dos vistas CI; cabecera y `COMMENT ON VIEW` |
| `config/diccionario/mart.yaml` | `v_pbi_dim_partida_niveles`: `nivel_1..6`, `partida_label` (R14) |
| `config/diccionario/cierre.yaml` | `v_pbi_dim_subcategoria_ci` y `v_pbi_cierre_indirectos_detalle`: `grupo_nombre`, `subcategoria_nombre` y el `grano` del detalle (R15) |
| `config/diccionario/00_global.yaml` | ámbito de `R-PARTIDA-CODIGO-NO-UNICO` (R16); `version` + historia; el comentario de v35 que remite a F-111 queda como histórico (R17) |
| `docs/ARCHITECTURE.md` | la frase «Dos vistas resuelven aún el NOMBRE ... lo arregla F-111» pasa a «desde F-111, por el ancestro» (R17) |
| `tests/test_f109_partidas_codigo.py` | `r13`, `r14` retirados con nota a F-111; `AGRUPAN_POR_OBRA_Y_CODIGO = frozenset()` (R18, R9) |

**NO se tocan**: `stg/04_partidas.sql` (añadir allí una `ruta_nombres` evitaría el
recursivo, pero toca el árbol de F-052, la huella y el DDL de `stg`: descartado);
`mart/05_views_powerbi.sql` (`partida_label` es el nombre PROPIO, correcto); las
expresiones de importe de `cierre/04` y la vista de generales; `mart/04_view_periodificado.sql`;
la categoría heurística (H1); `azure-apps/` (ningún objeto ni columna cambia);
`POWERBI.md` (no documenta la vista de niveles; D4 lo decide el humano).

## 7. Tests (`tests/test_f111_nombres_por_ancestro.py`, sin red ni BBDD)

| Test | Qué comprueba |
|---|---|
| `r1`-`r3` | `escalones` con fixtures 0626, 0404, homónimas y rama de 7; code del segmento, nombre del ancestro; profundidad > 6 no rompe; tope 40 |
| `r4` | la guarda de `es_hoja` y la fórmula de `partida_label` siguen en `05b` (texto) |
| `r5`, `r6` | `catalogo_ci` con 0444 (`CI`/`CI-FII`), raíz de nivel 0, respaldos; `nombre_fundido` ordena por punto de código («É» tras «Z») y no repite |
| `r7`, `r8`, `r13` | texto de `cierre/04`: mismo CTE en las dos vistas, join de subcategoría con `grupo_cod`, 7 `UPPER(COALESCE(ng.grupo_nombre, a.grupo_cod))`, 2 derivaciones de mes, claves y `GROUP BY` de `agregado` intactos; `05b` sin `nom` ni `MAX(descripcion_corta)`, con `WITH RECURSIVE`, `capitulo_padre_id` y `< 40` (cruzado con `TOPE_DE_PROFUNDIDAD`) |
| `r9`, `r10` | trinquete sobre `sql/**` con las dos formas; lista vacía; caso sintético en `tmp_path` que nombra al intruso |
| `r11`, `r12` | fixtures de R11; `ValueError` con padre inexistente y con ciclo |
| `r14`-`r17` | fichas y regla con `cargar_diccionario` / `derivar_avisos`; `version >= 36` (o la de D5); `ARCHITECTURE.md` |

Fase RED: todo falla contra `main` salvo las guardas `r4` y la de meses de `r13`.

## 8. Power BI («Árbol Presupuesto»)

El `.pbix` no está en el repositorio: lo que se sabe sale del SQL (el comentario de
`05b` manda repuntar `DimPartida` a esta vista para el visual). Si el visual pinta
`nivel_1 → ... → nivel_6`: **mismas filas y mismo `partida_id`**, 10.560 filas
con otra etiqueta en algún escalón; el árbol casi no cambia de forma (+43 nodos
en 387.979, §1.2: hoy fundía hermanas homónimas bajo el mismo padre), pero los
textos pasan a ser los del capítulo real. Un segmentador sobre una sola columna
`nivel_k` ve más valores distintos (hasta +534 en el escalón 4). Una medida DAX o
un filtro que compare con un literal de etiqueta («CD · INSTALACIONES») dejaría de
casar: solo el humano puede revisarlo (R20). En CI, `grupo_nombre` y
`subcategoria_nombre` cambian en 11 filas de obras del seguimiento y
`orden_subcategoria` puede moverse en ellas; las claves no.

## 9. Coste en la nocturna

Son VISTAS: la nocturna las recrea en milisegundos; el coste es de quien las lee.
Lectura completa, medida dos veces: niveles **16,5 s hoy → 4,2-4,6 s** (desaparecen
el `GROUP BY obra, codigo` de 394.046 filas y seis hash joins); dimensión CI 3,2 s
hoy, propuesta del orden (4,9 s con la comparación). El detalle (> 60 s) cambia un
`GROUP BY` de TODAS las partidas por un recursivo de las CI; R19 lo mide.

## 10. Riesgos y alternativas descartadas

- **Un importe que cambie**: solo `es_infraestructura` depende de un nombre; hoy 0
  grupos del seguimiento con varios nombres ⇒ 0 cambios. Mañana, un grupo que
  funda «INFRAESTRUCTURA» con otro nombre saldría INFRA con ` / ` y no con `MAX`:
  es más correcto y lo dice la ficha (R15).
- **Por `(obra, ruta)`** (155 repetidas) o **`(obra, contrato, código)`** (4.437):
  funden igual (F-109). Descartadas.
- **Elegir UNO de los nombres fundidos** (el de la raíz de menor código): oculta la
  fusión que D1 tiene que decidir. Descartado en favor de ` / ` (D2).
- **Límite de microservicio**: dentro; son etiquetas del dato que este ETL publica.

## 11. Decisiones abiertas para el humano

- **D1 · (Negocio) ¿Fundir las fases en costes indirectos?** Hoy el grupo es el
  CÓDIGO: `CI.1` de `CI` y de `CI-FII` suman en una fila (0444 y 0517, 112 filas del
  catálogo; más el respaldo `CI / (sin detalle)` de 8 obras). Recomendación:
  **(a) seguir fundidas en F-111** (sin cambio de grano ni de importes; 0444 cerró
  en 2019-12 y 0517 no tiene cierre) y preguntar a Negocio; si quiere **(b)
  separarlas**, es una feature nueva: la clave gana la raíz, Power BI cambia la
  relación, y las variantes `_inc` de la periodificación pueden cambiar de importe.
- **D2 · Nombre de un grupo que funde nodos de nombre distinto**: (a) **todos,
  unidos por ` / `** (recomendada, R6); (b) el de una raíz; (c) seguir con `MAX`.
- **D3 · Forma del SQL de niveles**: (a) **recursivo con tope 40** (recomendada);
  (b) siete joins topados en 7 saltos.
- **D4 · Árbol Presupuesto**: el humano confirma en Power BI qué columnas usa el
  visual y si hay medidas o filtros sobre literales de etiqueta (R20).
- **D5 · Versión**: la siguiente a la de `main` al fusionar (35 hoy → 36; F-056
  va en paralelo y puede tomarla antes).
- **H1 (hallazgo, no se toca)**: `categoria` es `LIKE '%CI%'` sobre el código de la
  raíz: `AVDA_FRANCIA` (fuera del seguimiento) y `P1414_PISCIN` entran como CI. 13
  raíces CI no se llaman `CI`. ¿Fichar feature para la heurística?
