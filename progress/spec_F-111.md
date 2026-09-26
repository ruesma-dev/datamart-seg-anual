<!-- progress/spec_F-111.md -->
# F-111 · Spec escrita (spec-author, 2026-09-26)

Spec en `specs/F-111-nombres-partida-por-ancestro/` (requirements 140/150, design
250/250, tasks 12 tareas). Rama `feature/F-111-nombres-partida-por-ancestro`
desde `main` (42d4b05), en un worktree aparte. Ficha: `status: spec_ready`;
`BACKLOG.md` regenerado. Nace de la D3 del humano sobre F-109.

## Qué propone

El NOMBRE de cada escalón sale del ANCESTRO REAL por `capitulo_padre_id`, nunca
por `(obra_id, codigo_partida)`:

- `mart/05b_view_dim_partida_niveles.sql`: un `WITH RECURSIVE` de arriba abajo
  (tope 40 = `TOPE_DE_PROFUNDIDAD` de F-052) acumula los nombres de la ruta y
  sustituye al CTE `nom` con `MAX(descripcion_corta)` y sus seis joins. Mismas
  filas, columnas, códigos y formato `código · nombre`.
- `cierre/04_views_detalle.sql` (dimensión CI y detalle de indirectos): el grupo
  y la subcategoría toman el nombre de sus nodos reales de nivel 1 y 2. Si el
  grupo funde varios nodos de nombre distinto, enseña todos unidos por ` / `
  (orden por punto de código). Grano, claves e importes intactos.
- Una regla equivalente en Python puro (`etl_sigrid/domain/nombres_arbol.py`,
  patrón de F-052) para probarla sin base y darle alcance a la mutación.
- Trinquete sobre `sql/**`: ninguna resolución por código (lista de F-109 → vacía).
- Fichas de niveles y de las dos vistas CI; `cierre.v_pbi_cierre_indirectos_detalle`
  entra en el ámbito de `R-PARTIDA-CODIGO-NO-UNICO` (observaciones 1 y 2 del
  review de F-109); la versión del diccionario sube.

## Medido (solo lectura, 2026-09-26, build de `stg` 01:56 UTC)

- **Niveles**: 10.560 filas cambian algún escalón (F-109 midió 10.593 el día 25);
  4.624 en obras con seguimiento, 67 obras. Por escalón 4.720 / 4.165 / 3.186 /
  1.496 / 166 / 24. La cadena `capitulo_padre_id` cuadra al 100 % con la ruta.
- **Ejemplos**: 0626 `CD` «INSTALACIONES» → «COSTES DIRECTOS» (1.921 filas);
  0404 `CD > 6` «PARTICIONES» → «FASE 6» (113); 0407 `CD > EXTRAS > 99.02`
  «JARDINERÍA» → «INSTALACIÓN DE ELECTRICIDAD E ILUMINACIÓN» (224); 0243 `IG > 02`
  «FIRMES Y PAVIMENTOS» → «ESTACION DE BOMBEO» (131).
- **Power BI**: mismas filas y `partida_id`; el árbol casi no cambia de forma (+43
  nodos en 387.979); los valores distintos de cada `nivel_k` suben como mucho
  +534 (escalón 4). El `.pbix` no está en el repositorio.
- **CI**: dimensión 47.636 filas, 156 cambian de nombre (11 en obras del
  seguimiento, todas grupos que funden varios nodos; 138 de una obra fuera del
  seguimiento con raíz `AVDA_FRANCIA`). Detalle: 117 filas, todas 0444
  (`CI.1.1`, `CI.1.2`, `CI.6.5`). En `CI.6.5` hoy sale el nombre de la fase II
  cuando todo el coste es de la I. **0 banderas `es_infraestructura` cambian: 0
  importes.** El «22» de F-109 no se reproduce con una definición explícita.
- **Las dos fases fundidas**: solo 0444 (cierre hasta 2019-12) y 0517 (sin
  cierre) tienen dos raíces CI con capítulos homónimos (112 filas del catálogo).
- **Inventario**: los dos ficheros de R15 de F-109 son todos los que resuelven
  nombres por código (4 sitios: 1 en `05b`, 3 CTE en `cierre/04`). Agrupan por
  código a propósito los importes del detalle CI (se declara, no se toca).
  Clasifican por el código de su propia ruta `06_cp_tipologia` y generales (fuera).
  `v_fact_periodificado` casa por patrón global con 0 reglas en `aux` (fuera).
- **Coste**: son vistas (nocturna ~0). Leer niveles entera: 16,5 s hoy → 4,2-4,6 s.

## Decisiones abiertas para el humano (`design.md` §11)

- **D1 · (Negocio) ¿Fundir las fases de 0444 / 0517 en costes indirectos?**
  Recomendada **(a) seguir fundidas en F-111** y preguntar a Negocio; separarlas
  es otra feature (cambio de grano y de relación en Power BI; las variantes
  `_inc` de la periodificación pueden cambiar de importe).
- **D2 · Nombre de un grupo que funde nodos distintos**: recomendada **todos
  unidos por ` / `**; alternativas: el de una raíz, o seguir con `MAX`.
- **D3 · SQL de niveles**: recomendado **recursivo con tope 40** (4,5 s);
  descartados siete joins (2,5 s, pero topados en 7 saltos).
- **D4 · Árbol Presupuesto**: el humano confirma qué columnas lee el visual y si
  hay medidas o filtros sobre literales de etiqueta.
- **D5 · Versión** del diccionario: la siguiente a `main` al fusionar (36 si nadie
  se adelanta; F-056 va en paralelo).
- **H1 (hallazgo)**: `categoria` es `LIKE '%CI%'` sobre el código de la raíz;
  `AVDA_FRANCIA`, `P1414_PISCIN` y `P1414_PCI` entran como CI. ¿Fichar feature?

## APROBADA (humano, 2026-09-26)

D1-D5 con la recomendacion: D1 las fases de la 0444 y la 0517 SIGUEN FUNDIDAS en
CI (separarlas cambia importes por grupo: seria feature aparte, a consultar con
Negocio); D2 un grupo que funde nodos de nombres distintos los muestra unidos por
« / »; D3 consulta recursiva por `capitulo_padre_id` con tope de 40 niveles; D4 el
humano revisa el visual Arbol Presupuesto de Power BI tras el despliegue
(verificacion MANUAL); D5 version del diccionario = la siguiente libre de `main`
al fusionar. El hallazgo H1 (la regla `LIKE '%CI%'`) queda pendiente de que el
humano decida si se ficha.
