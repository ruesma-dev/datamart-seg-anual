# F-113 · Diseño · la categoría CD/CI/CP sale del capítulo, no de letras sueltas

> Requisitos: `requirements.md`. Cifras y comparación A/B:
> `progress/spec_F-113.md`. Escrito para la opción A; las diferencias de B se
> marcan **[B]**.

## 1. Encaje y límite

Todo vive en `stg` (capa de staging, `docs/ARCHITECTURE.md` §Capas): la
categoría es una columna de `stg.partidas` y `mart`/`cierre` la leen tal cual
(`p.categoria = 'CD'|'CI'|'CP'`). No se toca ninguna capa de consumo: el cambio
llega aguas abajo solo, porque `stg.partidas`, `mart.fact_seguimiento_mensual`
y `cierre.fact_cierre_mensual` se reconstruyen enteros (`TRUNCATE` + `INSERT`)
cada noche y ninguno de los dos ficheros con ventana de F-025 (`06`, `08`) lee
`categoria`. Dentro del límite del servicio: no hay integración nueva ni
llamada a `sigrid-api` (Sigrid no trae marca de categoría: `obrparpar.tcaide`
= 0 en todas las filas, medido).

Hexagonal: la regla, en dominio puro (`domain/categoria_partida.py`), con su
réplica en el SQL; el patrón es el de F-052 (`domain/arbol_partidas.py` es el
espejo ejecutable de `04_partidas.sql`).

## 2. La regla

```
raíz (nivel 0):  UPPER(cod) empieza por CD → CD | CI → CI | CP → CP
                 si no: ^[0-9]+$ y no '34'/'99' → CD | resto → OTRO
intermedio:      UPPER(cod sin '.' ni ' ') ∈ {CD, CI, CP} → esa      [B: no existe]
                 si no → la del padre (también si cod = '', colapsado)
```

El **más cercano manda** sale solo: el recursivo baja de la raíz y cada nodo
sobrescribe o arrastra. «Subir por `capitulo_padre_id` hasta el capítulo CD/CI/CP»
y «bajar heredando» dan lo mismo y lo segundo no necesita otra recursión: se
reutiliza el `WITH RECURSIVE` de F-052 con su corta-ciclos y su tope de 40.

**Por qué exacto en los intermedios y prefijo en la raíz** (medido): las 15
variantes de raíz (`CD-FII`, `CI.F2`, `CIPD`, `CP.00`…) son todas capítulos
CD/CI/CP por su descripción; en los intermedios, en cambio, bajo raíces CD hay
391 nodos `CI…` y 191 `CP…` que son partidas de catálogo (`CI10` acero AEH-500,
`CPI8001` pilote CPI-8, `CI-0036` excavación, `CP110` puerta). Con prefijo en
los intermedios, 582 partidas de coste directo pasarían a CI/CP. Los 16
intermedios con código exacto son todos «COSTES DIRECTOS/INDIRECTOS/
PROPORCIONALES» (lista en `progress/spec_F-113.md` §2).

## 3. Ficheros a crear

- `etl_sigrid/domain/categoria_partida.py` — dominio puro, sin dependencias:
  - `CATEGORIAS_DE_CAPITULO: tuple[str, ...] = ("CD", "CI", "CP")`
  - `RAICES_NUMERICAS_FUERA: tuple[str, ...] = ("34", "99")`
  - `CARACTERES_IGNORADOS_EN_INTERMEDIO: tuple[str, ...] = (".", " ")` [B: no]
  - `OTRO = "OTRO"`
  - `def categoria_de_raiz(cod: str) -> str` — R1-R2. Numérico con
    `re.fullmatch(r"[0-9]+", cod)` (no `str.isdigit`, que acepta `²`).
  - `def categoria_heredada(cod: str, categoria_padre: str) -> str` — R4-R6.
    [B: devuelve siempre `categoria_padre`; no se crea la constante de
    caracteres.]
- `tests/test_f113_categoria.py` — R1-R6 y R9 sin base: paramétricos con los
  códigos medidos (los de los ejemplos de `requirements.md`), y `construir_arbol`
  sobre árboles pequeños (`CD > CI > CI.01`, `99 > CI`, `CD > '' > CI`,
  `CD > 02 > CI10`, nodo colapsado bajo `CI`).
- `tests/test_f113_sql.py` — textual sobre `04_partidas.sql` (R7, R10, R11):
  - ningún `LIKE '%` en el fichero (R11);
  - la rama raíz contiene `LIKE 'CD%'`, `'CI%'`, `'CP%'` construidos desde
    `CATEGORIAS_DE_CAPITULO`, y `'34'`, `'99'` desde `RAICES_NUMERICAS_FUERA`;
  - la rama recursiva contiene el `IN ('CD', 'CI', 'CP')` y un `REPLACE` por
    cada carácter de `CARACTERES_IGNORADOS_EN_INTERMEDIO`, y su `ELSE` es
    `a.categoria`; [B: la rama proyecta `a.categoria` sin `CASE`]
  - `categoria` es una columna proyectada en las dos ramas (el test de F-052
    `test_f052_las_dos_ramas_del_recursivo_proyectan_lo_mismo_y_en_el_mismo_orden`
    ya fija nombre y orden);
  - el `INSERT` toma `categoria` del CTE recursivo y ya no existe
    `arbol_categorizado`.

## 4. Ficheros a modificar

- `etl_sigrid/infrastructure/postgres/sql/stg/04_partidas.sql`:
  - rama raíz: nueva columna, tras `nivel_bruto`:
    ```sql
    (CASE WHEN UPPER(p.cod) LIKE 'CD%' THEN 'CD'
          WHEN UPPER(p.cod) LIKE 'CI%' THEN 'CI'
          WHEN UPPER(p.cod) LIKE 'CP%' THEN 'CP'
          WHEN p.cod ~ '^[0-9]+$' AND p.cod NOT IN ('34', '99') THEN 'CD'
          ELSE 'OTRO' END)::TEXT          AS categoria
    ```
  - rama recursiva, misma posición:
    ```sql
    (CASE WHEN UPPER(REPLACE(REPLACE(h.cod, '.', ''), ' ', ''))
               IN ('CD', 'CI', 'CP')
          THEN UPPER(REPLACE(REPLACE(h.cod, '.', ''), ' ', ''))
          ELSE a.categoria END)::TEXT     AS categoria
    ```
    [B: `a.categoria AS categoria`]
  - se borra el CTE `arbol_categorizado`; el `INSERT … SELECT … FROM
    arbol_partidas WHERE publicable` (columnas y orden del `INSERT` iguales).
  - cabecera: el bloque «CATEGORIA» se reescribe con §2 de este diseño y el
    porqué del exacto en intermedios (R16).
- `etl_sigrid/domain/arbol_partidas.py`: `Partida` gana `categoria: str` (último
  campo); `_Paso` arrastra `categoria`; la raíz usa `categoria_de_raiz`, el hijo
  `categoria_heredada(hijo.cod, paso.categoria)` — también el colapsado, cuyo
  `cod` es `''` y por tanto hereda (R6). Docstring: cita F-113.
- `tests/test_f052_sql.py`: `_rama_recursiva()` corta en `INSERT INTO
  stg.partidas` en vez de en `arbol_categorizado AS (`, y su docstring lo dice.
  Nada más cambia en los tests de F-052.
- `config/diccionario/stg.yaml`: nota 4 de cabecera; `partidas.categoria`
  (regla, «el más cercano manda», ramas sin capítulo reconocible: numérica → CD,
  resto → OTRO; ya no es «heurística sobre la raíz»); `capitulo_raiz_cod` (deja
  de ser «la ENTRADA de la heurística»: es informativo; la categoría puede venir
  de un intermedio).
- `config/diccionario/mart.yaml`: las seis columnas `categoria`
  (`fact_seguimiento_mensual`, `fact_seguimiento_categoria`,
  `v_pbi_fact_categoria`, `v_pbi_dim_partida`, `v_pbi_dim_partida_niveles`,
  `v_fact_periodificado`): «derivada del capítulo CD/CI/CP más cercano (raíz por
  prefijo, intermedio por código exacto)».
- `config/diccionario/raw.yaml`: `obrparpar` (descripción) y `auxobrtca`
  (deja de ser «el catálogo bueno sin usar»: medido el 2026-10-03, `tcaide` = 0
  en las 395.226 filas y el catálogo son tres oficios).
- `config/diccionario/00_global.yaml`: `version` + 1 (41 si nadie se adelanta).
- `config/tables_sigrid.yaml`: comentario de `auxobrtca` (no es CD/CI/CP).
- `README.md`: §5.3.1 (línea de `categoria`) y §6.3 (la regla nueva).

## 5. Ficheros que NO se tocan

- `sql/mart/*`, `sql/cierre/*`: leen `p.categoria`; el valor cambia, el código
  no. En particular `cierre/04_views_detalle.sql` (dimensión y detalle CI) y
  `mart/05b_view_dim_partida_niveles.sql` son de **F-111**.
- `sql/stg/06_presupuesto.sql`, `08_plan_mensual.sql`: no leen `categoria`; su
  sello de ventana (F-025) no se mueve, así que la nocturna no rehace las 880
  obras congeladas por esta feature (no hace falta: no cambia su contenido).
- `huella_obras.py`, `huella_ampliada.py`, `main.py`: se usan tal cual.
- `azure-apps/datamart_seg_anual.md`: no cambia lo que se expone ni se consume
  (mismas columnas, mismo grano).

## 6. Efecto previsto aguas abajo (detalle en `progress/spec_F-113.md` §2-3)

- **B** y la parte común de A: 253 partidas de 2 obras sin código de obra en
  `stg.obras` (fuera del seguimiento) pasan de CI a OTRO; 0 EUR.
- **A** además: 237 partidas de 5 obras (4 del seguimiento: 0229, 229, 0462,
  0500) pasan a CI (y 13 a CP en una obra sin código). Importes: **229** coste
  real 8.121 EUR de OTRO a CI → en el cierre (2011-01..03) INDIRECTOS sube y
  BENEFICIO baja hasta 8.121 EUR; **0462** venta real 25.002 EUR de CD a CI en
  `mart.fact_seguimiento_categoria` (el cierre no cambia: la VENTA no va por
  categoría). 0229 y 0500: 0 EUR.
- **Dimensión y detalle CI del cierre** (A): en 0462, 0500 y 229 aparecen
  grupos CI cuyo `grupo_cod` es el segundo escalón de la ruta (`CI` o `C.I.`),
  un nivel más arriba que en una raíz CI. Se declara, no se corrige (obras de
  2011-2016; corregirlo es materia de F-111).
- **Power BI**: mismas filas y claves; cambia el valor de `categoria` en esas
  obras.

## 7. Relación con F-111

Sin ficheros de código comunes (F-111: `mart/05b`, `cierre/04`,
`domain/nombres_arbol.py`). Se cruzan en dos sitios: la `version` del
diccionario (la que mergee segunda toma la siguiente libre) y las cifras de la
dimensión CI de F-111, que contaban 138 filas de la obra de `AVDA_FRANCIA` que
F-113 saca de CI (y con A entran las de 0462/0500/229). **Ninguna espera a la
otra**; si F-113 entra antes, el implementer de F-111 remide su dimensión CI
antes de cerrar.

## 8. Riesgos y decisiones

- **Alternativas descartadas**: (1) `tcaide`/`auxobrtca`: sin dato (todo 0).
  (2) Prefijo también en intermedios: 582 partidas de catálogo mal movidas.
  (3) Lista cerrada de raíces: 15 variantes hoy y el JO inventa más; el prefijo
  las cubre todas sin falsos positivos medidos. (4) Una segunda recursión «hacia
  arriba» por `capitulo_padre_id` en otro CTE: mismo resultado, el doble de
  coste; el árbol ya se recorre una vez.
- **Conocido y no corregido**: raíz `CDP` «PROPORCIONALES» (0685) sigue en CD
  con A y B (prefijo CD); solo tiene venta (0 coste), no toca el cierre. Las
  raíces OTRO del seguimiento (`PD` promoción delegada, `MP`…) siguen en OTRO:
  ver hallazgo H1 de `progress/spec_F-113.md`.
- **Riesgo de tipos en el recursivo**: Postgres exige el mismo tipo en las dos
  ramas; por eso `::TEXT` en ambas. Lo prueba T5 (SELECT real, solo lectura).
- **Rigor crítico y mutación**: la campaña del arnés solo muta Python (el
  dominio); el SQL va con campaña MANUAL como F-123 (tabla con texto exacto
  original → mutado, una fila por mutante, 0 supervivientes): prefijos, `'34'`,
  `'99'`, `NOT IN`→`IN`, `ELSE a.categoria`→`ELSE 'OTRO'`, quitar un `REPLACE`,
  el orden de los `WHEN`.
- **Contraste (D2 de `progress/spec_F-113.md`)**: recomendado el ligero (T5 en
  solo lectura antes + T12 dirigido después). El completo de F-042 (huellas y
  job puntual sin ingesta, ~3 h del servidor compartido) va en T13-T15, solo si
  el humano lo elige.
