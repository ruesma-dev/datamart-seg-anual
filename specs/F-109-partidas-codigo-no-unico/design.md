<!-- specs/F-109-partidas-codigo-no-unico/design.md -->
# F-109 · Diseño — el código de partida NO es único dentro de su obra

## 1. Medidas (solo lectura, 2026-09-25, build de `stg` de las 01:32 UTC)

MCP `bbdd-ruesma-azure` y, para lo que pasa de 30 s, consultas propias con
`SET TRANSACTION READ ONLY` (scratchpad, nada versionado). La ficha decía
5.203 / 8.934 / 159 el 24: la cifra se mueve con Sigrid. Hoy: **5.202 pares
`(obra_id, codigo_partida)`** (4.017 x2, 1.185 x3 o más, máx. 22), **8.933 filas
de más, 158 obras** (92 del seguimiento, 2.177 pares), idéntico en
`mart.v_pbi_dim_partida` (394.035 filas). Todas activas y con `partida_id`
distinto. **No es la empresa**: cada par vive en UNA ficha de obra (156 obras de
la empresa 1, una de la 25, una de la 31), así que `R-CODIGO-POR-EMPRESA` no
aplica. **No es F-052**: 0 de las 14.135 filas implicadas está colapsada.

### 1.1 Causas, mutuamente excluyentes, en este orden (suman el total)

Por par, sobre `raw.obrparpar` (`ctride`/`expide` con 0 = sin valor, que cuenta
como un valor más):

| # | Causa (regla) | Pares | Filas de más | Obras (seg.) | Pares seg. |
|---|---|---|---|---|---|
| 1a | contratos distintos, todas las copias con contrato (`ctride` distinto) | 637 | 941 | 19 (19) | 637 |
| 1b | contrato distinto, alguna copia SIN contrato | 175 | 194 | 21 (17) | 59 |
| 2 | mismo contrato, expediente distinto (`expide`) | 61 | 70 | 3 (3) | 61 |
| 3 | mismo contrato y expediente, misma raíz, otro capítulo (ruta distinta) | 1.932 | 4.979 | 114 (55) | 871 |
| 4 | raíces paralelas (`capitulo_raiz_id` distinto) | 2.360 | 2.710 | 19 (4) | 519 |
| 5 | misma ruta: hermanas homónimas (descripción distinta) o marcador | 28 | 30 | 16 (16) | 28 |
| 6 | misma ruta, nada las distingue | 9 | 9 | 2 (1) | 2 |
| | **Total** | **5.202** | **8.933** | **158 (92)** | **2.177** |

812 pares con contrato distinto (1a+1b; 767 con una copia por contrato) y 218
con expediente distinto (157 dentro de 1, 61 en 2; 112 uno por expediente).

**Qué es cada causa en Sigrid** (`azure-apps/sigrid_tablas.md`: `obrctr` =
«Obras: contratos de obra» con el CLIENTE —cliente, importe adjudicado,
coeficientes, plazos—; `obrctrexp` = «Obras: expedientes de un contrato»
—tipo, situación, importe, fechas de envío y aprobación, código de contrato
convertido—; la partida apunta a ambos con `ctride` y `expide`):

- **1a · un contrato con el cliente por lote, y el jefe de obra repite el
  presupuesto en cada uno.** Casi siempre un capítulo por contrato (552 de 637
  además cambian de capítulo). 0617 (161 pares): `CONT_PPAL_PL.1ª` «Contrato
  principal planta 1ª» y `CONT_PPAL_PL.BJ` «planta baja». 0317 `01`
  «Acondicionamiento del terreno»: `CD > EDI > 01` (`CONT_PPAL_1` «Edificio»),
  `CD > PIS > 01` (`CONT_PPAL_2` «Pistas»), `CD > ACE > 01` (`CONT_PPAL_3`
  «Arenero»). 0243 `01`: una raíz por contrato (`AC`, `CG`, `DG`, `IG`, `RV` =
  Alumbrado Circunvalación, Colector General, Depósito, Impulsión, Red Viaria).
- **1b · un capítulo añadido fuera de contrato** (ampliaciones, urbanización)
  reutiliza el código. 0371 `02.06`: `CD > 02` (`CONT_PPAL`), `CD > URB2 > 02`
  (`CONT_URBANIZ`) y `CD > URB1 > 02` (sin contrato). 0245 `PROP-159`: `CD > 25 >
  25.01` (`C.PPAL.EJEC.`) y `CD > 100` (sin contrato). 0410 `14.01.02` bajo
  `14.01` (`CONT_PPAL`) y `14.02` (sin contrato).
- **2 · expedientes del mismo contrato** (modificados/adicionales). 0410
  `14.01.01` «Caldera Platinum Roca» bajo `14.01` (expediente -4) y `14.02` (-3),
  mismo `CONT_PPAL`. 0318 `01.01.01`: `ACE` (exp. 35), `SAT` (-3), `VES` (35).
  0375 `01.01`: `PPAL` (sin exp.), `ADI1`, `ADI2` (-4).
  **Ojo**: `expide` vale 0 en el 97,8 % de `raw.obrparpar`; 3.554 filas llevan un
  expediente real (65, en 41 obras) y 5.258 llevan **-3 (3.041, 56 obras) o -4
  (2.217, 33)**, valores centinela sin fila en `obrctrexp` cuyo significado no
  documenta Sigrid. `raw.obrctrexp` **no se ingiere**. Es trabajo de F-099.
- **3 · subárbol copiado bajo capítulos hermanos del mismo contrato** (1.368 de
  los 1.932, sin contrato alguno). Lo que distingue a los capítulos es la
  unidad física o temporal de la obra: 0560 (227 pares) viviendas tipo —`1.1`
  «Vivienda tipo Ibiza con sótano 2_4», `1.2` «10_12», `2.1` «sin sótano 14_16»,
  `3` «Menorca 6_8»; `1.1.3.2 HORM. HA-25` cuelga de 11 capítulos—; 0404 (145)
  `CD > 1..6` «FASE 1..6»; 0430 (148) «Presupuesto base» frente a «Anexo
  voluntario parcela 1 / 6»; 0463 (90) `PUAS`, `B2`, `MICE 1`, `MICE 2`. En 1.805
  pares la descripción es idéntica: la misma unidad de obra repetida por bloque.
- **4 · raíces paralelas.** Fases con raíz propia e importes propios: 0444 `CD`
  «Fases IA-IB» / `CD-FII` «Fase II» (2,05 M EUR de coste real en la II) y `CI` /
  `CI-FII`; 0517 `CI` / `CI-FII`. Raíces que copian un capítulo: 0515 raíces `2` y
  `3` duplican `CD > 2` y `CD > 3` (sin importe). Fuera del seguimiento, 107 pares
  son una raíz duplicada con el MISMO código (un `CI` entero dos veces: misma
  ruta, distinta raíz) y presupuestos de prueba en paralelo («PRUEBA», «NUEVO
  PPTO», «LOTE 2-VENTA»).
- **5 · hermanas homónimas**: erratas y marcadores. 0510 `04.04.14` = «Vallado
  perimetral» y «Demolición soleras»; 0448 `22.44` = enchufes dobles y triples;
  0443 `N/A` y `----------`; 0444 código `'          .-'`.
- **6 · sin explicar (9 pares)**: filas iguales en código, ruta, padre,
  descripción, contrato y expediente; solo cambian `ide` y `pos`. 0446
  `2.2.4.1.1` «NOTA PAVIMENTOS» dos veces (`CONT_PPAL`); los otros 7 en una obra
  fuera del seguimiento (`obra_id` 939355, `OBANAC` «Bandeja apoyo canalón» x2).
  Parecen pegados dos veces; solo el jefe de obra puede decirlo.

**Descartados** (0 pares que difieran): `tipdes`, `tipcon`, `numord`,
`fecini`/`fecfin`, `proide`, `obrcalide`, `codobruni`, `parideori`; ni
`parcoside`/`parvenide` enlazan copias; `tipvis` (8) y `tip` (193) no explican.

### 1.2 Claves candidatas (repetidos / filas de más / obras; seguimiento)

| Clave | Repetidos | Filas de más | Obras | Seg. (obras) |
|---|---|---|---|---|
| `(obra, codigo)` | 5.202 | 8.933 | 158 | 2.177 (92) |
| `(obra, contrato, codigo)` | 4.437 | 7.858 | 140 | 1.527 (74) |
| `(obra, contrato, expediente, codigo)` | 4.372 | 7.779 | 139 | 1.462 (73) |
| `(obra, ruta)` | 155 | 162 | 25 | 38 (21) |
| `(obra, expediente, ruta)` | 155 | 161 | 25 | 38 (21) |
| `(obra, contrato, ruta)` | 150 | 156 | 22 | 34 (19) |

**Lo que distingue las copias es el CAPÍTULO, no el contrato**: el contrato
explica POR QUÉ el jefe de obra abrió otro capítulo en 812 pares, pero es
redundante con la ruta (155 -> 150). Lo que queda repetido en `(obra, ruta)` son
las causas 4 (raíz duplicada con el mismo código), 5 y 6. `pos` no lo completa.
**Solo `partida_id` es único.**

## 2. Quién une hoy por (obra, código) y qué pasa (criterio 4)

- **Ningún importe se duplica hoy dentro del repositorio.** El SQL que suma une
  por `partida_id` (`mart/02_build_fact.sql`, `mart/06_cp_tipologia.sql`,
  `compras/03_views.sql`, `cierre/04_views_detalle.sql`); Power BI relaciona
  `DimPartida` y `FactSeguimiento` por `partida_id` (`POWERBI.md`); ninguna
  relación del diccionario usa `codigo_partida`. `mcp-bbdd` escribe SQL libre
  guiado por un diccionario que hoy le dice que el código es único.
- **Riesgo cuantificado**: unir el hecho y la dimensión por `(obra_id,
  codigo_partida)` infla la historia (`SUM(importe_mes)`): Coste Real
  +12.108.634,53 EUR (47 obras), Venta Real +13.145.742,76 (53). **Obra 0437:
  883.460,55 -> 3.474.491,83 EUR (x3,9)**; por `partida_id` o por `(obra, ruta)`,
  exacto.
- **Donde muerde hoy, sin euros: los nombres.** `mart/05b_view_dim_partida_niveles.sql`
  (`nom`) y `cierre/04_views_detalle.sql` (`nombres_por_obra`) resuelven el
  nombre por `(obra, código)` con `MAX(descripcion_corta)`: 10.593 filas de
  niveles (4.657 del seguimiento) enseñan algún escalón con el nombre de otra
  partida; en CI, 22 filas de nivel 1-2, y las dos fases de 0444 caen en el mismo
  grupo `CI.1`. En Power BI, `partida_label` funde homónimas (4.127 pares
  comparten código y descripción).

## 3. Ficheros

**Crear**: `tests/test_f109_partidas_codigo.py` (offline; helpers copiados de
`test_f102_*`, `tests._texto.contiene` para tildes).

| Modificar | Cambio |
|---|---|
| `config/diccionario/stg.yaml` | `partidas`: `descripcion`, `obra_id` (R1), `codigo_partida` (R5, R6), `ruta_capitulos` (R7) |
| `config/diccionario/mart.yaml` | `fact_seguimiento_mensual.codigo_partida` (R3); `v_pbi_dim_partida` `obra_id`, `codigo_partida`, `partida_label` (R2, R8); `v_pbi_dim_partida_niveles.nivel_1..6` (R13) |
| `config/diccionario/compras.yaml` | `v_pbi_partida_coste.codigo_partida` (R8) |
| `config/diccionario/cierre.yaml` | `v_pbi_dim_subcategoria_ci` `grupo_nombre`/`subcategoria_nombre` (R14) |
| `config/diccionario/00_global.yaml` | regla `R-PARTIDA-CODIGO-NO-UNICO` tras `R-LINEA-ID-NO-UNICA` (R9, R10); `version` y su historia (R16) |
| `docs/ARCHITECTURE.md` | entrada en «Semántica Sigrid imprescindible» tras la de F-052 (R17) |

**NO se tocan**: ningún SQL (D3); `etl_sigrid/domain/` ni `unicidad_sql.py`
(F-108); `CODIGOS_REGLAS_OBLIGATORIAS`; la batería (18 preguntas clavadas);
`azure-apps/` (ningún objeto ni columna cambia); `ctride`/`expide` (F-099).

## 4. Texto de las fichas (redacción del implementer)

- **`stg.partidas.obra_id`** / **`mart.v_pbi_dim_partida.obra_id`**: «Una partida
  pertenece a una sola obra, pero **el código de partida NO es único ni dentro de
  ella**: se identifica por `partida_id`».
- **`stg.partidas.codigo_partida`**: se conserva el bloque de F-052 y se añade
  «**NO es único dentro de la obra** (2026-09-25: 5.202 códigos repetidos en 158
  obras)», las causas en una línea cada una (un contrato o expediente por copia,
  subárbol repetido por vivienda/bloque/fase, raíces paralelas, erratas), que
  **ni el contrato lo desambigua** (4.437 repetidos por obra, contrato y código) y
  «para unir o contar, `partida_id`; para leer dónde está, `ruta_capitulos`». Con
  D5, «Nunca es NULL ni vacío» pasa a «ni cadena vacía; 2 filas traen solo
  espacios».
- **`stg.partidas.ruta_capitulos`**: «CASI única en la obra (155 repeticiones:
  raíces duplicadas, erratas y copias pegadas dos veces): para leer, no clave».
- **`mart.fact_seguimiento_mensual.codigo_partida`**: «Código jerárquico
  ('01.02'). **NO es único ni dentro de la obra**. Para identificar o unir,
  `partida_id`».
- **`nivel_1..6`**: la frase de R13 en `nivel_1` y «igual que `nivel_1`» en las
  demás. Toda cifra lleva su fecha.

## 5. La regla `R-PARTIDA-CODIGO-NO-UNICO` [D2]

Bloqueante; ámbito: `stg.partidas`, `mart.v_pbi_dim_partida`,
`mart.v_pbi_dim_partida_niveles`, `mart.fact_seguimiento_mensual`,
`mart.v_fact_periodificado`, `compras.v_pbi_partida_coste`,
`cierre.v_pbi_dim_subcategoria_ci`. `regla`: «Una partida se identifica, se une
y se cuenta por `partida_id`. NUNCA por `(obra, codigo_partida)`, ni añadiendo
el contrato: el mismo código cuelga de varios capítulos (5.202 códigos repetidos
en 158 obras, 2026-09-25) y ese JOIN multiplica importes: en la 0437 el coste
real pasa de 883.460,55 EUR a 3.474.491,83. `ruta_capitulos` dice dónde está,
pero tampoco es clave. Agrupar por código funde partidas distintas.» `motivo`:
F-109, las causas de §1.1 y que las fichas decían lo contrario. Mismo patrón que
`R-LINEA-ID-NO-UNICA`; `derivar_avisos` la lleva a las siete fichas (R11); el
MCP la sirve tras publicar y reiniciar (cachea el diccionario).

## 6. Tests (`tests/test_f109_partidas_codigo.py`, sin red ni BBDD)

| Test | Qué comprueba |
|---|---|
| `r1`-`r3` | la columna citada no contiene la afirmación y sí `partida_id` |
| `r4_ninguna_ficha_dice_que_el_codigo_es_unico` | barrido de todas las fichas con regex normalizada (`unic[oa]s? (por\|dentro de su) obra`, `solo son unicos dentro`); nombra ficha y columna |
| `r5`, `r6`, `r7` | `5.202`, `158`, `2026-09-25`, «contrato», «capitulo», «raiz», `4.437`; «solo espacios»; `155` |
| `r8` | `partida_id` en las tres columnas; `4.127` en `partida_label` |
| `r9`, `r10` | regla bloqueante, ámbito ⊇ los siete, texto con `partida_id`, `5.202`, `0437`, `3.474.491,83` |
| `r11`, `r12` | `derivar_avisos` lleva la regla a las siete fichas; `validar` sin errores y longitudes de F-006 |
| `r13`, `r14` | `10.593` y `MAX` en niveles; «codigo» y `CI-FII` en la dimensión CI |
| `r15` | trinquete de §7.2 con un caso sintético en `tmp_path` que demuestra que muerde |
| `r16`, `r17` | `version >= 33`; `F-109` y `partida_id` en `ARCHITECTURE.md` |

Fase RED: todo falla contra `main` salvo R15 (guarda de lo que ya hay).

## 7. SQL de referencia

**7.1 Verificación manual (R18, MCP, < 5 s)**:
`SELECT count(*) pares, sum(n-1) filas_de_mas, count(DISTINCT obra_id) obras FROM
(SELECT obra_id, codigo_partida, count(*) n FROM stg.partidas GROUP BY 1,2 HAVING
count(*) > 1) d;`

**7.2 Trinquete de R15**: regex `GROUP\s+BY\s+obra_id\s*,\s*codigo_partida`
(sin distinguir mayúsculas) sobre `sql/**/*.sql`; hoy casa solo en
`cierre/04_views_detalle.sql` (líneas 60 y 123) y
`mart/05b_view_dim_partida_niveles.sql` (29). Las consultas de §1 no se versionan.

## 8. Decisiones abiertas para el humano

- **D1 · ¿Qué clave legible identifica una partida?** Con §1.2 delante: el
  contrato NO desambigua el código (5.202 -> 4.437) y apenas mejora la ruta
  (155 -> 150); lo que distingue es el capítulo. Recomendación: **(a) ninguna
  clave legible; `partida_id` es la única**, y `ruta_capitulos` se documenta como
  dirección CASI única (R7). Descartadas: (b) declarar `(obra_id,
  ruta_capitulos)` como clave alternativa de F-108: KO permanente en
  `check-unicidad` (155; 38 en el seguimiento) salvo que Negocio limpie en
  Sigrid las causas 4-6; (b') `(obra, contrato, ruta)`: 150, igual de rota y con
  un campo que F-109 no publica; (c) clave sintética `<clave_obra>/<ruta>#n`: el
  sufijo depende del orden, ni estable ni legible. Con (b), F-109 depende de F-108
  y gana una tarea.
- **D2 · ¿Regla dura nueva?** Recomendación: **sí** (§5), por el caso 0437. Sin
  D2 caen R9-R11.
- **D3 · Nombres por código (niveles y cierre CI).** Recomendación: **(a)
  documentarlo aquí (R13, R14) y fichar una feature** que resuelva el nombre por
  el ANCESTRO (`capitulo_padre_id`), no por código: toca SQL de `mart` y `cierre`
  y etiquetas del «Árbol Presupuesto» (~4.657 filas del seguimiento). Que Negocio
  diga también si fundir las fases de 0444 en `CI.1` es lo que quiere. (b)
  meterlo aquí sube el alcance y deja de ser verificable offline.
- **D4 · Versión**: la siguiente a la de `main` al fusionar (33 hoy; 34 si F-108
  fusiona antes).
- **D5 · Los 2 códigos de solo espacios**: **corregir solo el texto** (R6);
  cambiar el filtro tocaría el árbol de F-052.

**Relación con F-099** (expedientes de obra, `pending`): F-099 publicará qué
partidas cuelgan de cada contrato y expediente; esta medida le sirve de entrada:
(i) en 812 pares el mismo código existe una vez por contrato, así que su
enlace partida -> expediente debe ir por `partida_id`; (ii) `expide` = -3 / -4 en
5.258 partidas son centinelas que tiene que explicar; (iii) `raw.obrctrexp` hay
que ingerirla. F-109 no publica `ctride`/`expide`.

## 9. Límite de microservicio y riesgos

- **Dentro del límite**: documenta el dato que este ETL publica. Limpiar
  erratas, raíces duplicadas o copias dobles es trabajo de Negocio en Sigrid.
- **La cifra envejece**: va con fecha; si el implementer remide y cambia,
  actualiza texto y test en el mismo commit y lo anota como desviación.
- **Choque con F-108** (mismos YAML y `version`): D4. **Sin Python de
  producción**, la campaña de mutación no tendrá mutantes: se deja escrito.
