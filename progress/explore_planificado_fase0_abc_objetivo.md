# Exploración medida · «el planificado» de Aguado: fase 0, ABC, Oficina Técnica y coste objetivo

Medido el **2026-09-17** (15:23 UTC) contra Sigrid vivo por `sigrid-api` (`leer_sql`, SOLO
LECTURA) y contra el datamart por el MCP (diccionario v24, build `mart` 2026-09-17 02:54 UTC).
Cero escrituras. Continúa `progress/explore_F-038_comparativos.md`, del que da por buenas las
cifras de compras.

## 0 · Resumen en cinco líneas

1. **«Fase 0» es la VERSIÓN 0 del master coste (ámbito 8)**: 237 obras, **844,6 M€**. Existe
   en `stg.presupuesto`, pero **NO llega a `mart`**: solo 6 de sus 238 filas de `obrfasamb`
   tienen planificación temporal, y `stg.plan_mensual` exige `plafec > 0`.
2. **«Oficina Técnica» NO es `Planif Inicial`**. Hipótesis **DESCARTADA con cifra**: de las 19
   versiones master que lo nombran, **0 clasifican como `Planif Inicial`**. Oficina Técnica es
   el *autor* de la versión 0; `Planif Inicial` es «PLANIFICACION VALORADA INICIAL», que el
   jefe de obra escribe en las versiones 1 a 4.
3. **«El último ABC» ya está resuelto a medias**: `master_vigente_anual` ordena por fecha
   efectiva, así que entre varios ABC coge el bueno — **pero compite con Cuatrimestral y casi
   siempre pierde**: en 2026 rige ABC en **1 obra de 38**.
4. **El «coste objetivo» NO existe guardado en Sigrid.** Ni campo, ni ámbito, ni versión, ni
   campo extendido: todos los candidatos medidos están vacíos o son anecdóticos.
5. **El comparativo SÍ se puede comparar contra lo planificado**, pero **por partida, no por
   comparativo**: deduplicando por `(obra, partida)` da **690,4 M€** frente a 1.229,1 M€
   adjudicados (1,8×), no los 30.770 M€ (25×) que salían en F-038.

## 1 · ¿Qué es «el coste de FASE 0»?

**Hay dos lecturas de `fas = 0` y no son la misma cifra.** La regla publicada `R-FAS-AMBIGUO`
ya lo avisa: en los ámbitos reales (3, 7) `fas` es el MES y `fas = 0` es «el Previsto vivo»; en
los master (8, 11) `fas` es el NÚMERO DE VERSIÓN.

| lectura | filas `obrparpre` | obras | importe (`can×pre`) |
|---|---|---|---|
| **ámbito 8 (MASTER COSTE), `fas=0` = versión 0** | 122.616 | **237** | **844,6 M€** |
| ámbito 3 (COSTE), `fas=0` = «Previsto» vivo | 218.099 | 672 | 1.152,2 M€ |

`SELECT amb, COUNT(*), COUNT(DISTINCT obride), SUM(can*pre) FROM obrparpre WHERE fas=0 GROUP BY amb`

**No son la misma magnitud**: de las **236 obras que tienen las dos**, solo **7 coinciden al
euro** y **18 dentro del 1 %**.

**La lectura correcta es la del ámbito 8**, y lo dice el texto libre de esas 238 filas de
`obrfasamb`: `res` = «Versión 0 (dd/mm/aaaa)» y `tex` = **CIERRE INICIAL_ESTUDIO** (125 de 238
mencionan ESTUDIO), COSTE INICIAL OFICINA TECNICA, CIERRE INICIAL OT, CIERRE INICIAL_OBRA. Es
el coste de partida que carga Estudios/Oficina Técnica antes de que el jefe de obra planifique.
En el ámbito 3 la fase 0 no tiene ni `res` ni `tex` (vacíos en la muestra de 15): es el
previsto vivo, otra cosa.

**¿Es lo mismo que `Planif Inicial`? NO.** De las 238 filas de versión 0 del ámbito 8,
**ninguna clasifica como `Planif Inicial`**: 141 caen en `Cierre mensual` (su texto empieza
por «CIERRE»), 96 en `Sin clasificar` y 1 en `ABC`. `Planif Inicial` son 61 filas en 60 obras,
todas de versiones **1 a 4**, nunca la 0.

### El hallazgo que condiciona la feature: la fase 0 no llega a `mart`

Contando `plafec` en `obrfasamb` del ámbito 8: **`fas=0` son 238 filas y solo 6 tienen
`plafec > 0`**; `fas>0` son 2.937 filas con 2.240 informadas.

`stg/08_plan_mensual.sql` filtra `WHERE fa.plafec IS NOT NULL AND fa.plafec > 0`, así que la
versión 0 **no entra en `stg.plan_mensual`** ni, por tanto, en `master_versiones_tipadas` ni en
`master_vigente_anual`: de las 2.215 filas del ámbito 8 de `mart.master_versiones_tipadas`,
**solo 4 son `version = 0`**.

**Pero el importe SÍ está en el datamart**: `stg.presupuesto` con `fase_num = 0 AND
ambito_id = 8` da **122.616 filas y 237 obras**, exactamente lo de Sigrid (MCP, 22 s). Se
consume de ahí, sin ingerir nada nuevo. Lo que no existe es su reparto mensual: la versión 0 no
tiene `planif`, así que **es un total a origen, no una serie**.

## 2 · «Oficina Técnica»: existe en Sigrid, pero NO es `Planif Inicial`

Existe con ese nombre, y solo en texto libre: **20 filas** en `obrfasamb.res`/`tex`, 17 de
ellas en el ámbito 8 (17 obras). Literales: `COSTE INICIAL OFICINA TECNICA`, `CIERRE INICIAL
OFICINA TÉCNICA`, `V0. COSTE INICIAL OFICINA TÉCNICA`, `Version 0 - Oficina Tecnica` (con `tex`
= «COSTE INICIAL ESTUDIOS(k=1,22)»), `CIERRE INICIAL OT`. **No aparece en `obrfas`** —que ni
siquiera tiene filas con `fasnum = 0`: 0 de 4.567— **ni en ningún catálogo auxiliar**:
`auxrotval`, el único de «tipo de fase», tiene **3 filas** y ninguna es esa.

**Medición de la hipótesis, y la descarta.** Clasificando con el mismo CASE del datamart las
filas del ámbito 8 cuyo `res` o `tex` mencionan OFICINA, OF. TEC u OT: **19 filas ·
`Planif Inicial`: 0 · `Cierre mensual`: 10** (las 9 restantes, `Sin clasificar`).

**`Planif Inicial` es otra cosa**: sus textos son `PLANIFICACION VALORADA INICIAL` (42 filas),
`PLANIFICACIÓN VALORADA INICIAL` (6) y variantes, en versiones **1 a 4** (una en la 13),
**nunca la 0**. Es la primera planificación valorada del jefe de obra.

**Conclusión: «Oficina Técnica» y «fase 0» son la MISMA cosa** —la versión 0, cargada por
Estudios/Oficina Técnica— **y `Planif Inicial` es una tercera, posterior y del jefe de obra.**
Las magnitudes 1 y 3 del encargo probablemente coinciden: es la primera pregunta a devolver.

Aviso de cobertura: solo **17 obras de 237** escriben literalmente «Oficina Técnica» en la
versión 0; el resto escribe ESTUDIO (125) o nada (69). **No se identifica por el texto**: hay
que identificarla por ser `fas = 0`.

## 3 · «El último ABC si hay varios»

Contando por obra en `obrfasamb` del ámbito 8 con `tex LIKE '%ABC%'`: **35 obras con un ABC,
21 con dos y 1 con tres** → **57 obras con ABC, 22 de ellas con más de uno**. De sus 80 filas,
**78 tienen `plafec > 0`**,
así que el ABC sí llega al datamart (55 obras y 78 filas en `mart.master_versiones_tipadas`).

**¿`master_vigente_anual` elige el último? SÍ, por construcción**, pero no el último *ABC*:
`06_cp_tipologia.sql` hace `ROW_NUMBER() OVER (PARTITION BY obra, anio, ambito ORDER BY
version_fec_efectiva DESC, version DESC)` **sobre los tres tipos juntos** (`Planif Inicial`,
`ABC`, `Cuatrimestral`). Si hay un Cuatrimestral posterior, el ABC pierde. Medido:

| año | Cuatrimestral | ABC | Planif Inicial |
|---|---|---|---|
| 2024 | 53 | 6 | 3 |
| 2025 | 60 | 3 | 1 |
| **2026** | **36** | **1** | **1** |

Y de las 22 obras con varios ABC, **en 2026 ninguna tiene el ABC como vigente**.

**Lectura para la feature: se CONSUME la lógica de orden, pero NO el objeto tal cual.** Una
columna «planificado ABC» separada del vigente exige una selección propia restringida a
`tipo_master = 'ABC'` (misma ventana y mismo `ORDER BY`). La tipificación no se reimplementa:
`mart.master_versiones_tipadas` ya la da.

## 4 · «El COSTE OBJETIVO, un coste con un % de bajada respecto al ABC»

**NO EXISTE GUARDADO EN SIGRID. Dicho con todas las letras.** Barridos todos los candidatos:

| candidato | qué es | medición | veredicto |
|---|---|---|---|
| `obrfasamb.beopor` / `beoimp` | «Benef Objetivo Porcentaje/Importe» | **0 filas informadas en los ámbitos 3, 8 y 11**; solo 101/104 en el ámbito **2 (ESTUDIO)**, de 564, y casi todas de 2016-2019, con valores de 1 a 4 % | **NO** · es beneficio del estudio, no coste, y no cubre el master |
| `obrfasamb.coeficpor` / `coeind` / `coecos` / `coestr` | coeficientes de la versión | **0 filas en los ámbitos 3, 8 y 11** (218 `coecos` en el ámbito 2) | **NO** |
| `obrparpre.varest` «% variación estudio» | porcentaje por partida | **0 filas informadas en las 13.941.970** | **NO, vacío en origen** |
| `obr.apebajmed` / `apebajref` / `apebajtem` | bajas de licitación | **0 de 922 obras** | **NO, vacío en origen** |
| `conext` (campos extendidos de obra) | clave-valor por obra | ningún `cod` con `vali` relevante: solo `DI` (7 filas) y `RV` (5), de 1.650 a 12.000 € | **NO** |
| `rob.tipobjofi` «Es objetivo oficial» | resumen mensual de obra | tabla con **77 filas y 25 obras**; `tipobjofi` a 0 en todas | **NO, tabla muerta** |
| ámbito 14 `POR_REF` «PRESUPUESTO REFERENCIA» | ámbito propio | 87.652 filas pero **solo 3 obras** con `fas=0` | **NO, cobertura ridícula** |
| texto libre «OBJETIVO» | `obrfasamb.res`/`tex` | **8 filas**: 3 obras de ~2010 con `res` = «OBJETIVO COSTE» y `tex` = «Estudio con coeficiente 80%», y 5 con «CIERRE OBJETIVO» / «OBJETIVO FIN OBRA» (2018) | **anecdótico** |
| texto libre «BAJA»/«COEFICIENTE» | ídem | **9 filas**, ninguna en el ámbito 8 salvo las 3 anteriores | **anecdótico** |

**Esas 3 filas son la única huella en toda la base de un coste objetivo con porcentaje**, y son
de tres obras de hace quince años. **El % de bajada lo aplica alguien fuera del sistema** (hoja
de cálculo, criterio de dirección). **Es una pregunta legítima para devolverle al humano y no
hay que inventar la fórmula.**

## 5 · Cómo se enlaza con el COMPARATIVO

**El desglose por partidas del comparativo no existe**: `comlinpar` («Desglose partidas de
Comparativos», `comlinide` → `paride` con importe) tiene **0 filas**. Y `dncpro.ambide` y
`dncpro.fas` —que apuntarían a la fila exacta de `obrparpre`— están **a 0 en las 287.643
líneas**. El único enlace sigue siendo `dncpro.paride`, sin ámbito y sin fase;
`comlin.dncproide` está informado en **197.651 de 197.651 líneas (100 %)**.

**El criterio que SÍ permite comparar: por `(obra, partida)`, no por comparativo.** Lo que
rompía la suma en F-038 era contar el presupuesto de una partida una vez por comparativo.
Deduplicando el par y eligiendo la fase 0:

| magnitud | pares `(obra, partida)` | importe |
|---|---|---|
| **Planificado, fase 0 del MASTER COSTE** (`amb=8, fas=0`) | 67.484 | **549,1 M€** |
| **Planificado, fase 0 del COSTE / previsto vivo** (`amb=3, fas=0`) | 83.035 | **690,4 M€** |
| **Adjudicado** (`comlin.can × pre`, 20.003 comparativos) | — | **1.229,1 M€** |

Consulta: `COUNT(*)` y `SUM` sobre el `DISTINCT (com.obride, dncpro.paride)` de `comlin JOIN
com JOIN dncpro ON d.ide=l.dncproide`, unido a `obrparpre` preagregado por `(obride, paride)`.

**Esto ya es una comparación, no un disparate**: 1,8× frente a los 25× de F-038. Que el
adjudicado supere al planificado es esperable (la partida se compra en varios contratos y el
presupuesto es de coste, no de compra), pero está en el mismo orden. **Y la dispersión es
manejable**: de los ~83.500 pares con comparativo, **64.918 (78 %)** se compran en **un solo
comparativo**; 9.575 en dos, 4.110 en tres, cola hasta 12 y más.

**Recomendación medida: la comparación se publica al nivel `(obra, partida)`**, con el
adjudicado agregado de todos sus comparativos enfrentado al presupuesto de esa partida. Al
nivel de UN comparativo el planificado **no se puede dar como cifra sumable** —la partida no es
suya— y como mucho se muestra con la etiqueta «presupuesto de la partida en la obra (no es el
presupuesto de este comparativo)». **Prorratear por medición NO es viable**: `dncpro.canref` ya
se descartó en F-038 (coincide con `comlin.can` en el 78 %) y `comlinpar`, que sería el reparto
oficial, está vacío.

**Cobertura sobre las 192 obras con comparativo**: **181 (94,3 %)** tienen fase 0 del master
coste, **192 (100 %)** la del ámbito 3 y **solo 57 (29,7 %)** alguna versión ABC; de master
vigente en 2026 hay **38 obras en todo el datamart**. **La única de las cuatro magnitudes con
cobertura casi total es la fase 0.**

## Decisiones que quedan para el humano

1. **¿«Fase 0» y «Oficina Técnica» son la misma cosa?** Todo apunta a que sí: las dos son la
   **versión 0 del master coste**, la que carga Estudios/Oficina Técnica antes de que el jefe
   de obra planifique. Si es así, las cuatro magnitudes son **tres**. Si no, hay que preguntar
   qué distingue una de otra, porque en Sigrid no se distinguen.
2. **`Planif Inicial` NO es Oficina Técnica** (0 de 19 coincidencias). ¿Entra como cuarta
   magnitud, o se queda fuera del informe de comparativos?
3. **El coste objetivo hay que preguntarlo.** No existe en Sigrid ni el importe ni el %. ¿De
   dónde sale, quién lo fija y con qué granularidad (empresa, obra, capítulo)? Sin esa
   respuesta **no se puede implementar** sin inventar una cifra plausible y falsa.
4. **La fase 0 es un TOTAL A ORIGEN, no una serie mensual.** No tiene `planif` (232 de 238
   filas sin `plafec`), así que no se puede repartir por meses ni compararla contra un año
   concreto. ¿Vale así para el informe, o Negocio la espera anualizada?
5. **ABC como columna propia exige un objeto nuevo.** `master_vigente_anual` da «la última de
   las tres» y hoy el ABC rige en **1 obra de 38 en 2026**. ¿Se publica «planificado ABC» como
   columna separada (última versión ABC, exista o no un cuatrimestral posterior) o se acepta
   el vigente?
6. **El grano de la comparación.** Propuesta: `(obra, partida)`. Al nivel de comparativo el
   planificado no es sumable: ¿se muestra igual como contexto o no se muestra?
7. **Ingesta**: no hace falta traer nada nuevo. `obrparpre` y `obrfasamb` ya están en `raw`, y
   `stg.presupuesto` ya contiene la fase 0 del ámbito 8 (122.616 filas, 237 obras). Lo que hay
   que decidir es si la fase 0 se publica en `mart` como objeto propio o se consume de `stg`.

---

## CORRECCIÓN DEL HUMANO, 2026-09-18: no son dos lecturas, son DOS MAGNITUDES

Este informe presentó la fase 0 como **una** magnitud con dos lecturas posibles
que «no cuadran», y planteó como decisión 1 si «fase 0» y «Oficina Técnica» son
lo mismo. **El humano responde que no, y que las dos lecturas son correctas
porque miden cosas distintas**, cada una en su ámbito:

> «el coste fase 0 está en el **ámbito coste**, es el previsto que está vivo. Sin
> embargo el **abc y oficina técnica están en el ámbito master coste**, no
> coste.»

Así que el mapa queda así, y **las cuatro magnitudes del encargo siguen siendo
cuatro**:

| magnitud | ámbito | qué es | medido |
|---|---|---|---|
| **Coste fase 0** | **3 · COSTE** | el previsto **vivo**, `fas = 0` | **672 obras, 1.152,2 M EUR** |
| **Oficina Técnica** | **8 · MASTER COSTE** | lo que carga Estudios/OT | **237 obras, 844,6 M EUR** (la versión 0) |
| **Planificado ABC** | **8 · MASTER COSTE** | la última versión tipo `ABC` | 57 obras, 22 con más de una |
| **Coste objetivo** | — | el ABC con un % de bajada | **sin localizar** |

**Lo que este informe midió como «fase 0, segunda lectura» (`amb=3, fas=0`,
672 obras, 1.152,2 M EUR) es EL COSTE FASE 0**, y lo que midió como «fase 0 =
versión 0 del master coste» (`amb=8`, 237 obras, 844,6 M EUR) **es OFICINA
TÉCNICA**. Que solo 7 de 236 obras coincidan al euro **no es una anomalía a
resolver**: son dos cosas distintas y por eso no coinciden. La sección 1 de
arriba se lee con esta corrección delante.

**Sigue en pie, y sin tocar**, todo lo demás: que `Planif Inicial` NO es Oficina
Técnica (0 de 19), que el ABC pierde casi siempre contra el cuatrimestral en
`master_vigente_anual` (rige en 1 obra de 38 en 2026), que la comparación contra
lo comprado funciona al grano `(obra, partida)` con un factor de 1,8 y no de 25,
y que no hace falta ingerir nada nuevo.

**El coste objetivo se vuelve a buscar** por orden del humano: «el porcentaje de
coste objetivo revisa a ver si está en Sigrid».
