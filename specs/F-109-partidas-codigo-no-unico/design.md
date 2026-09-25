<!-- specs/F-109-partidas-codigo-no-unico/design.md -->
# F-109 · Diseño — el código de partida NO es único dentro de su obra

## 1. Medidas (solo lectura, 2026-09-25, build de `stg` de las 01:32 UTC)

Por el MCP `bbdd-ruesma-azure` y, para lo que pasa de 30 s, consultas propias con
`SET TRANSACTION READ ONLY` desde el scratchpad (nada versionado, nada escrito).
La ficha decía 5.203 / 8.934 / 159 (medido el 24): la cifra se mueve con Sigrid.

| Medida | Valor |
|---|---|
| Pares `(obra_id, codigo_partida)` repetidos | 5.202 (4.017 x2, 1.185 x3 o más, máx. 22) |
| Filas de más / obras | 8.933 / 158 (92 del seguimiento, 2.177 pares) |
| `mart.v_pbi_dim_partida` | idéntico: 394.035 filas, 5.202 pares |
| Filas implicadas / colapsadas por F-052 | 14.135 / **0** (en toda la tabla hay 36 colapsadas) |
| Partidas activas en los pares | todas (`activa = TRUE`) |
| Pares con descripción distinta | 1.075 (4.127 comparten código Y descripción) |

**Clasificación** (por `count(DISTINCT ruta_capitulos)` y `capitulo_raiz_id`):

| Tipo | Pares | Filas de más | Obras (seg.) | Qué es | Ejemplo |
|---|---|---|---|---|---|
| D misma raíz, otro capítulo | 2.713 | 6.043 | 135 (76) | subárbol copiado por bloque/portal | 0560 `1.1.3.2` bajo `1.1.3`, `1.1.19`, `1.2.3`... (11) |
| B otra raíz | 2.340 | 2.739 | 19 (6) | árbol por fase con raíz propia, o raíz que copia un capítulo | 0444 `CD`/`CD-FII`, `CI`/`CI-FII`; 0515 raíz `2` y `CD > 2` |
| A misma ruta | 149 | 151 | 23 (19) | hermanas homónimas: marcadores y erratas; raíces duplicadas | 0443 `N/A`, `----------`; 0510 `04.04.14` x2; 0444 código `' '` |

Descartado con el dato (sobre `raw.obrparpar`): `tipvis` (coste/venta) distinto
solo en 8 pares; 0 pares enlazados entre sí por `parcoside`/`parvenide`; 0 con
`parideori` (copia MenfisNet); `numord` y `pos` no desambiguan. Las copias por
empresa (`R-CODIGO-POR-EMPRESA`) no aplican: el par vive dentro de un `obra_id`,
que ya es la ficha de UNA empresa. Los árboles por fase de tipo B son reales y
tienen importes propios (0444: `CD-FII` 2,05 M EUR de coste real); las copias de
0515 no tienen importe.

**Clave legible candidata**: `(obra_id, ruta_capitulos)` repite 155 pares, 162
filas de más, 25 obras (38 pares en 21 obras del seguimiento); `pos` no la
completa (109 ternas repetidas). **Solo `partida_id` es único.**

## 2. Quién une hoy por (obra, código) y qué pasa (criterio 4)

- **Ningún importe se duplica hoy dentro del repositorio.** Todo el SQL que
  suma une por `partida_id` (`mart/02_build_fact.sql`, `mart/06_cp_tipologia.sql`,
  `compras/03_views.sql`, `cierre/04_views_detalle.sql` en `fase0_por_partida`).
  Power BI relaciona `DimPartida` y `FactSeguimiento` por `partida_id`
  (`POWERBI.md` §relaciones). Ninguna relación del diccionario usa
  `codigo_partida`. `mcp-bbdd` no trae SQL propio: escribe consultas libres
  guiado por el diccionario, que hoy le dice que el código es único.
- **El riesgo, cuantificado**: unir `mart.fact_seguimiento_mensual` con
  `mart.v_pbi_dim_partida` por `(obra_id, codigo_partida)` infla, sobre toda la
  historia (`SUM(importe_mes)`): Coste Real **+12.108.634,53 EUR** (47 obras),
  Venta Real +13.145.742,76 (53), Coste Planificado +989.618,99, Venta
  Planificada +1.160.297,38. Obra 0437, coste real: **883.460,55 -> 3.474.491,83
  EUR (x3,9)**; por `partida_id` o por `(obra_id, ruta_capitulos)`, exacto.
- **Donde sí muerde hoy, sin duplicar euros: los NOMBRES.** Dos sitios resuelven
  el nombre por `(obra, código)` con `MAX(descripcion_corta)` (sin fan-out
  porque agregan antes de unir):
  - `mart/05b_view_dim_partida_niveles.sql` (`nom`, `nivel_1..6`): **10.593
    filas** (4.657 del seguimiento) enseñan al menos un escalón con el nombre de
    otra partida homónima (1.429 filas con descripción distinta de su `MAX`).
  - `cierre/04_views_detalle.sql` (`nombres_por_obra`, y `catalogo`/detalle que
    agrupan por `grupo_cod`/`subcategoria_cod`, códigos sacados de la ruta): 22
    filas CI de nivel 1-2 cuyo nombre no es el `MAX` de su código, y las dos fases de 0444
    (`CI > CI.1` y `CI-FII > CI.1`) caen en el mismo grupo `CI.1`.
  - Power BI: `partida_label` y `codigo_partida` como eje funden homónimas
    (4.127 pares con código y descripción iguales dan la misma etiqueta).

## 3. Ficheros

**Crear**: `tests/test_f109_partidas_codigo.py` (offline; helpers copiados, no
importados, como hacen `test_f102_*`: `_ficha`, `_texto`, `_regla`, y
`tests._texto.contiene` para normalizar tildes).

**Modificar** (solo texto de diccionario y documentación):

| Fichero | Cambio |
|---|---|
| `config/diccionario/stg.yaml` | `partidas`: `descripcion` (un párrafo), `obra_id` (R1), `codigo_partida` (R5, R6), `ruta_capitulos` (R7) |
| `config/diccionario/mart.yaml` | `fact_seguimiento_mensual.codigo_partida` (R3); `v_pbi_dim_partida.obra_id`, `codigo_partida`, `partida_label` (R2, R8); `v_pbi_dim_partida_niveles.nivel_1..6` (R13) |
| `config/diccionario/compras.yaml` | `v_pbi_partida_coste.codigo_partida` (R8) |
| `config/diccionario/cierre.yaml` | `v_pbi_dim_subcategoria_ci.grupo_nombre`/`subcategoria_nombre` (R14) |
| `config/diccionario/00_global.yaml` | regla `R-PARTIDA-CODIGO-NO-UNICO` (R9, R10) tras `R-LINEA-ID-NO-UNICA`; `version` y comentario de historia (R16) |
| `docs/ARCHITECTURE.md` | entrada en «Semántica Sigrid imprescindible» tras la de F-052 (R17) |
| `harness/features.json`, `BACKLOG.md`, `progress/*` | estado y rastro |

**NO se tocan**: ningún SQL (`stg/04_partidas.sql`, `mart/05b_*`,
`cierre/04_views_detalle.sql`: arreglar los nombres es D3), ni
`etl_sigrid/domain/` ni `unicidad_sql.py` (F-108, en curso en otra rama), ni
`CODIGOS_REGLAS_OBLIGATORIAS` de `test_f006_reglas.py` (la lista cerrada de
F-006; `R-CODIGO-POR-EMPRESA` tampoco está en ella), ni la batería de aceptación
(`test_f006_r39` clava 18 preguntas), ni `azure-apps/datamart_seg_anual.md`: no
cambia ningún objeto ni columna publicados, solo su texto.

## 4. Texto de las fichas (lo que deben decir; redacción del implementer)

- **`stg.partidas.obra_id`** / **`mart.v_pbi_dim_partida.obra_id`**: «Obra a la
  que pertenece. Una partida pertenece a una sola obra, pero **el código de
  partida NO es único ni dentro de ella**: se identifica por `partida_id`».
- **`stg.partidas.codigo_partida`**: se conserva el bloque de F-052 y se añade
  «**NO es único dentro de la obra** (medido el 2026-09-25: 5.202 códigos
  repetidos en 158 obras)» + las tres causas en una línea cada una + «para unir
  o contar, `partida_id`; para leer dónde está, `ruta_capitulos`». Con D5, la
  frase «Nunca es NULL ni vacío» pasa a «Nunca es NULL ni cadena vacía; 2 filas
  traen un código de solo espacios».
- **`stg.partidas.ruta_capitulos`**: «CASI única dentro de la obra (155
  repeticiones, sobre todo marcadores como `N/A` y raíces duplicadas): sirve para
  leer y navegar, no como clave».
- **`mart.fact_seguimiento_mensual.codigo_partida`**: «Código jerárquico de la
  partida ('01.02'). **NO es único ni dentro de la obra**: el mismo código cuelga
  de varios capítulos. Para identificar o unir, `partida_id`».
- **`nivel_1..6`**: la frase de R13 una vez en `nivel_1` y «igual que
  `nivel_1`» en las demás (o en la `descripcion` de la ficha, si cabe mejor).
- La cifra lleva siempre su fecha: es una foto de Sigrid, no una constante.

## 5. La regla `R-PARTIDA-CODIGO-NO-UNICO` [D2]

```yaml
  - codigo: R-PARTIDA-CODIGO-NO-UNICO
    titulo: El codigo de partida NO es unico ni dentro de su obra
    severidad: bloqueante
    ambito: [stg.partidas, mart.v_pbi_dim_partida, mart.v_pbi_dim_partida_niveles,
             mart.fact_seguimiento_mensual, mart.v_fact_periodificado,
             compras.v_pbi_partida_coste, cierre.v_pbi_dim_subcategoria_ci]
    regla: >-   # orden + cifras de R10
      Una partida se identifica, se une y se cuenta por `partida_id`. NUNCA por
      `(obra, codigo_partida)`: el mismo codigo cuelga de varios capitulos de la
      misma obra (5.202 codigos repetidos en 158 obras, 2026-09-25) y ese JOIN
      multiplica importes: en la 0437 el coste real pasa de 883.460,55 EUR a
      3.474.491,83. `ruta_capitulos` dice DONDE esta, pero tampoco es clave.
      Agrupar por codigo funde partidas distintas en una fila.
    motivo: >-  # causa: F-109, tres tipos, las fichas decian lo contrario
```

Es el mismo patrón que `R-LINEA-ID-NO-UNICA`. `derivar_avisos` la lleva a las
siete fichas (R11). El MCP la sirve tras publicar y reiniciar (memoria: cachea el
diccionario hasta reiniciar).

## 6. Tests (`tests/test_f109_partidas_codigo.py`, sin red ni BBDD)

| Test | Qué comprueba |
|---|---|
| `test_f109_r1_..` a `r3_..` | la columna citada no contiene la afirmación y sí `partida_id` |
| `test_f109_r4_ninguna_ficha_dice_que_el_codigo_es_unico` | barrido de TODAS las fichas y columnas con regex normalizada (`unic[oa]s? (por\|dentro de su) obra`, `solo son unicos dentro`); falla nombrando ficha y columna |
| `test_f109_r5_..`, `r6_..`, `r7_..` | cifras y causas en `stg.partidas` (`5.202`, `158`, `2026-09-25`, «capitulo», «raiz», «ruta»); `solo espacios`; `155` en `ruta_capitulos` |
| `test_f109_r8_..` | `partida_id` en las tres columnas; `4.127` en `partida_label` |
| `test_f109_r9_..`, `r10_..` | regla bloqueante, ámbito ⊇ los siete, texto con `partida_id`, `5.202`, `0437`, `3.474.491,83` |
| `test_f109_r11_..` | `derivar_avisos(cargar_diccionario(...))`: las siete fichas llevan el código en sus avisos |
| `test_f109_r12_..` | `validar` del diccionario real sin errores y exigencias de longitud de F-006 |
| `test_f109_r13_..`, `r14_..` | `10.593` y `MAX` en niveles; «codigo» y `CI-FII` en la dimensión CI |
| `test_f109_r15_..` | trinquete de §7.2; un caso sintético (un tercer fichero en `tmp_path`) demuestra que la guarda muerde |
| `test_f109_r16_..`, `r17_..` | `version >= 33`; `F-109` y `partida_id` en `ARCHITECTURE.md` |

Fase RED: los tests de texto fallan contra el `main` actual (las tres fichas
mienten, no hay regla, versión 32). R15 pasa ya en RED (es una guarda de lo que
hay): se deja constancia en `progress/impl_F-109.md`, como con otras guardas.

## 7. SQL de referencia

**7.1 Verificación manual (R18, MCP, < 5 s):**

```sql
SELECT count(*) pares, sum(n-1) filas_de_mas, count(DISTINCT obra_id) obras
FROM (SELECT obra_id, codigo_partida, count(*) n FROM stg.partidas
      GROUP BY 1,2 HAVING count(*) > 1) d;
```

**7.2 Trinquete de R15**: regex `GROUP\s+BY\s+obra_id\s*,\s*codigo_partida`
(insensible a mayúsculas) sobre `sql/**/*.sql`; hoy casa en
`cierre/04_views_detalle.sql` (líneas 60 y 123) y
`mart/05b_view_dim_partida_niveles.sql` (línea 29). Nada más.

Las consultas de §1-§2 (fan-out, tipos, nombres) no se versionan: son de medición
y sus resultados están aquí y en `progress/spec_F-109.md`.

## 8. Decisiones abiertas para el humano

- **D1 · ¿Qué clave legible identifica una partida?** Recomendación: **(a)
  ninguna; `partida_id` es la única clave** y `ruta_capitulos` se documenta como
  dirección legible CASI única (R7). No se publica columna nueva ni se declara
  clave alternativa de F-108. Descartadas: (b) declarar `(obra_id,
  ruta_capitulos)` como clave alternativa: `check-unicidad` daría KO permanente
  (155 pares) y saldría con 1 cada vez; solo sería viable si Negocio limpia en
  Sigrid los marcadores `N/A`/`----------` y las raíces duplicadas (38 pares en
  el seguimiento). (c) publicar `clave_partida = <clave_obra>/<ruta>#n`: el
  desambiguador depende del orden de las filas, no es estable ni legible; si
  usara `partida_id` no aportaría nada. Si el humano elige (b), F-109 pasa a
  depender de F-108 y gana una tarea (declararla en `stg.partidas` y
  `mart.v_pbi_dim_partida`).
- **D2 · ¿Regla dura nueva?** Recomendación: **sí**, `R-PARTIDA-CODIGO-NO-UNICO`
  bloqueante (§5): el caso 0437 (x3,9) es exactamente una cifra plausible y
  falsa, y una ficha sola no llega a quien consulta el hecho sin mirar la
  dimensión. Sin D2 caen R9-R11 y queda solo el texto de las fichas.
- **D3 · Los nombres resueltos por código (niveles y cierre CI).**
  Recomendación: **(a) F-109 los documenta (R13, R14) y se ficha una feature
  nueva** que resuelva el nombre de cada escalón por el ANCESTRO
  (`capitulo_padre_id` o prefijo de `ruta` con `partida_id`), no por código. Toca
  SQL de `mart` y `cierre`, cambia etiquetas del «Árbol Presupuesto» de Power BI
  en ~4.657 filas del seguimiento, y `cierre.v_pbi_cierre_indirectos_detalle` no
  se puede consultar (R-COSTE-CONSULTA): merece su propia verificación. (b)
  meterlo aquí sube el alcance y la verificación deja de ser offline. Fundir las
  fases de 0444 en `CI.1` puede ser incluso lo que Negocio quiere: que lo diga.
- **D4 · Versión del diccionario**: la siguiente a la de `main` al fusionar (hoy
  32 -> 33; si F-108 fusiona antes con la suya, 34). Misma regla que D5 de F-108.
- **D5 · Los 2 códigos de solo espacios** (0444 `CD > 21 >  `). Recomendación:
  **corregir solo el texto** de la ficha (R6). Cambiar el filtro a
  `trim(cod) <> ''` alteraría qué se publica y tocaría el árbol de F-052: fuera.

## 9. Límite de microservicio y riesgos

- **Dentro del límite**: es documentación del dato que este ETL publica. La
  causa vive en cómo los jefes de obra montan el presupuesto en Sigrid; limpiar
  los marcadores o las raíces duplicadas es trabajo de Negocio en Sigrid, no de
  este repositorio ni de `sigrid-api`.
- **La cifra envejece**: se escribe con fecha, y el test busca las cifras de la
  spec como históricas (si el implementer remide y cambian, actualiza texto y
  test en el mismo commit y lo anota como desviación).
- **Choque con F-108** (misma familia de ficheros YAML y `version`): se resuelve
  en el merge con D4; F-109 no toca `claves_alternativas` salvo D1 (b).
- **Rigor `estandar` con cero código de producción**: la campaña de mutación no
  tendrá mutantes en Python de producción; el implementer la ejecuta y lo deja
  escrito, y el reviewer juzga (no se propone bajar a `documental` porque hay
  tests nuevos y una guarda sobre SQL).
