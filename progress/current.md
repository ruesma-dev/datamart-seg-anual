<!-- progress/current.md -->
# Estado actual · 2026-09-01

## F-052 · FASE 2 EJECUTADA — el arreglo está PUBLICADO en la base

**La 0599 ya no miente.** Cierre de 2022-12, contra lo que publicaba ayer:

| Concepto | Antes | Ahora |
|---|---|---|
| **DIRECTOS** | **0,00 €** | **2.624.793 €** |
| GASTOS totales | 1.369.593 € | **3.994.386 €** |
| VENTA | 4.066.989 € | 4.066.989 € |
| **BENEFICIO** | 2.697.396 € | **72.603 €** |
| **Margen** | **66,3 %** | **1,8 %** |

Los tres números que se predijeron el 2026-08-31 —coste 3.994.386,39, beneficio
72.602,84, margen 1,8 %— **han salido exactos**. La obra de control **0628
LEGAZPI no se mueve ni un céntimo**.

**Lo ejecutado el 2026-09-01, desde el puesto y contra producción:**

| Paso | Resultado |
|---|---|
| `stage` | SUCCESS, **8 h 15** (la misma tarea dentro de Azure: 1 h 37) |
| `build-mart` | SUCCESS, 2 h 31 · el fact gana **55.165 filas, todas de la 0599** |
| `build-cierre` | SUCCESS, 2 h 02 · 16.928 filas, las mismas de siempre |
| `publicar-diccionario` | versión **12**, biyección 103/103, `_meta` ya sirve lo del árbol |

**Las cuatro huellas, capturadas antes y después sobre el MISMO `raw`:**

| Huella | Veredicto | Obras que se mueven |
|---|---|---|
| dimension | **OK** | solo 0599 (117 → 1.440) |
| cierre | **OK** | solo 0599 |
| mart | KO por master | **solo 0599**, 144 diferencias |
| stg | KO por master | **solo 0599**, 70 diferencias |

### El KO de master: FALSO POSITIVO, aceptado por el humano el 2026-09-02

`comparar-huellas` arrastra de **F-042** la regla «cualquier cambio en los ámbitos
master 8 u 11 es desbordamiento». **F-052 exige lo contrario y está escrito en
R9**: «deben aparecer las combinaciones 0599 × ámbito 7 y 0599 × ámbito 11, hoy
inexistentes». La herramienta marca como error justo lo que la spec pide.

Comprobado antes de aceptarlo: **las 214 diferencias de las dos huellas son todas
de la 0599**; ninguna otra obra aparece en ninguna. Palabras del humano: «si la
única diferencia es la 599 es lo esperado, está bien».

**Deuda que deja abierta**: `comparar-huellas` debería aceptar cambios en master
**para las obras esperadas**, en vez de rechazarlos siempre. Mientras no se
arregle, cualquier feature futura que toque master se encontrará el mismo KO y
tendrá que volver a razonarlo a mano.

### NOCTURNA DESACTIVADA — hay que revertirlo

El cron del job está en **`0 2 1 1 *`** (no dispara) desde el 2026-09-01 22:00.
Se desactivó porque la imagen del job es **`r20260830-0924`, anterior a F-052**:
a las 02:00 habría reconstruido con el SQL viejo, deshaciendo 12 h 48 de trabajo,
y su `ingest` habría cambiado `raw`, invalidando la comparación.

**Se revierte al desplegar la imagen nueva:**
`az containerapp job update -g rg-datamart-seg-dev -n caj-datamart-seg-dev --cron-expression "0 2 * * *"`

Red de seguridad si se olvida: la alerta de frescura salta a las **30 h** sin
`build_mart` y avisa a los dos buzones del grupo de acción.

### La alerta de cobertura, desplegada

`alert-caj-datamart-seg-dev-cobertura`, severidad 2, ventana de 24 h evaluada
cada hora, dispara por **presencia** del marcador `[F052-COBERTURA-KO]`. El grupo
de acción tiene ya **dos destinatarios**. **Sigue sin verificarse de extremo a
extremo**: no ha llegado ningún correo todavía, y no llegará hasta que el job
corra con la imagen nueva.

## F-052 · FASE 1 IMPLEMENTADA Y REVISADA

**Reviewer: FASE 1 APROBADA, ningún cambio requerido** →
`progress/review_F-052.md`. El cierre queda pendiente de la fase 2: **C5 no se
puede marcar** porque T13, T14 y T15 están sin hacer a propósito.

**La condición de DA-2, verificada por TERCERA vez y por otro camino.** El
reviewer ejecutó el CTE nuevo entero contra **todas las obras** y comparó el
`md5` del sitio de cada partida contra `stg.partidas` de hoy: **cambia UNA sola
obra, la 0599** (117 → 1.440); **las otras 734 salen idénticas al byte**. Es R6
cumplido y la huella 3 pre-validada en solo lectura.

**Dos cosas que el reviewer encontró en la huella 3 y que conviene no perder:**
lleva `ORDER BY p.partida_id` **dentro** del `string_agg` y `COALESCE` en las seis
columnas. Sin lo primero el `md5` bailaría solo; sin lo segundo, un
`capitulo_padre_id` NULL haría NULL el resumen entero de cualquier obra con raíz
y **la comparación parecería verde**. Es el modo de fallo más peligroso que tiene
esta feature: una verificación que miente en verde.

**Tres observaciones que NO bloquean, anotadas para la fase 2:**

1. `check-cobertura` **da verde sobre cero filas**. Hoy cero filas es el estado
   sano, pero un fallo que dejara las dos consultas sin resultados (tabla
   renombrada, esquema vacío) se leería como OK. Con la línea base de **T15** cabe
   añadir el denominador: combinaciones (obra × ámbito) vistas en `stg`.
2. Hay una **décima excepción que T10 no pedía**, la 0606 PUY DU FOU. Justificada
   y marcada `feature: F-053`, pero debía haberse declarado.
3. Un CSV de huella de F-042 anterior a T27 (8 columnas) ya no lo reconoce
   `comparar-huellas` y muere con un mensaje confuso. Hoy no existe ninguno.

**Desviación 4, aceptada CON SEGUIMIENTO:** no hay tope de filas por excepción,
así que la de 0565, 0630 y 0686 tapa **cualquier** número de huérfanas en esas
obras. **T15 fija la línea base y ahí se afina.**

**Automejora propuesta por el reviewer, sin aplicar:** `.claude/agents/reviewer.md`
obliga a un veredicto binario, y una feature partida en dos fases por diseño no es
ni APPROVED ni CHANGES_REQUESTED. Propone un tercero, `APPROVED_FASE_1`, que
obligue a enumerar los checkpoints pendientes. **Decisión del humano.**

### Lo entregado en la fase 1

**Informe completo: `progress/impl_F-052.md`.** Hechas T1-T12, T16-T19 y
T22-T30; T20 ya venía hecha y **T21 (mutación) está exenta** por decisión del
humano del 2026-08-31. `bash harness/init.sh` en verde, cobertura de las líneas
cambiadas al 100 %.

**Pendiente del humano, y es lo que falta para cerrar:** T13, T14, T15 y los diez
pasos de cierre de `tasks.md`. Son escrituras contra el Postgres compartido en
producción o lecturas de varios GB, y desde el puesto **no hay conexión directa**
(`connection timeout expired` contra `psql-albaranes-rs9k2`). Dos de ellos no son
opcionales:

* **el aviso a Negocio (R27) es BLOQUEANTE**: sin él no se publica;
* **desplegar `infra/96_create_alert_cobertura.ps1`** y añadir el buzón al grupo
  de acción. Sin ese paso el guardián nuevo **es mudo**, porque al no bloquear el
  job la alerta de fallo no se dispara.

**Hoy la 0599 sigue publicando las cifras de siempre**: el arreglo está escrito y
probado, no reconstruido.

### El riesgo (a) del informe queda ELIMINADO: el motor ya vio el SQL

El implementer dejó dicho que el `WITH RECURSIVE` con `visitados` estaba probado
en dominio y sobre el texto, **pero no contra Postgres** — porque yo le pasé
información desactualizada: la conexión se había restablecido antes de lanzarlo.
Validado por el líder el 2026-09-01 tomando el CTE **literal** del fichero, sin
`TRUNCATE` ni `INSERT`, como `SELECT` de agregados en solo lectura:

| Comprobación | Resultado |
|---|---|
| El recursivo se ejecuta y **no se cuelga** | 390.508 nodos, **390.501 publicables** — R7 al nodo |
| La 0599 (R8) | **1.440 partidas**, de ellas **1.326 CD** (hoy son 3) |
| Invariante R4 (`cardinality(ruta) = nivel + 1`) | **0 filas lo rompen** |
| R3 (todo `capitulo_padre_id` apunta a fila publicada) | **0 padres colgados** |
| Tope de 40 del corta-ciclos | **0 nodos** por encima de 39: no trunca nada |

Sigue vivo el riesgo (b): la alerta solo está probada como texto, **no hay correo
recibido**. Y R11 sigue sin ejecutarse: esto valida el árbol, no el dinero
publicado.

## F-052 · spec aprobada — las 7 decisiones cerradas por el humano

`specs/F-052-partidas-huerfanas/`. Rama `feature/F-052-partidas-huerfanas`.
Línea base: `progress/explore_F-052.md`. **La causa quedó identificada y la
hipótesis previa desmentida**: la cadena de `padide` de la 0599 **sí llega a la
raíz `CD`**; lo que corta es el filtro `AND h.cod <> ''` de
`sql/stg/04_partidas.sql:78`, que impide **descender a través de** tres capítulos
intermedios con código vacío y amputa 1.323 partidas. Las otras 12 son ciclos.

### Las siete decisiones, cerradas el 2026-08-31

| | Decisión del humano |
|---|---|
| **DA-1** | Solo se relaja la rama de descenso (línea 78). La raíz **no se toca**: criterio de mínimo cambio, «ahora mismo estaba funcionando bien en general» |
| **DA-2** | **Colapsar**, y CONDICIONADO: si se mueve una cifra de una obra distinta de las seis afectadas, **se para y se consulta**. Palabras del humano: «si cambia algo, prefiero perder la 0599 porque no sigue el patrón correcto» |
| **DA-3** | Array de visitados **+** tope de profundidad |
| **DA-4** | **AVISA, NO BLOQUEA** — la nocturna termina en verde. Y **aviso por correo** al buzón de desarrollo |
| **DA-5** | Sí, se lleva a Sigrid sin esperar. Único caso prioritario: la **0686**, obra viva |
| **DA-6** | Avisar a Negocio **antes** de publicar, y nota en el diccionario |
| **DA-7** | Feature propia: **F-053**, prioridad 2 |

**Por qué DA-2 se puede dar por segura sin medirla contra la base**: cada partida
tiene **un solo padre**, luego un solo camino a la raíz. Una partida publicada hoy
tiene todo su camino con código, y el algoritmo nuevo recorre ese mismo camino con
idéntico resultado. **El cambio es estrictamente aditivo.** Datos que lo respaldan:
fuera de la 0599 el movimiento máximo posible son **226 filas de 183.756, a 0,00 €**;
y la profundidad máxima real de `stg.partidas` es de **7 niveles, con cero partidas
de nivel 8 o más sobre 389.178** (medido el 2026-08-31), lo que valida que el tope
de 40 del corta-ciclos no trunca nada legítimo.

**Y ya no hace falta el argumento: está MEDIDO contra `raw`** (2026-08-31, tras
restablecer el acceso). Simulado el árbol nuevo entero y cruzado con
`stg.partidas`: las partidas nuevas son **1.323 y TODAS de la 0599** —ni una en
las otras cinco obras—; **ninguna** partida ya publicada cambia ruta, nivel ni
padre; **ninguna** desaparece; la profundidad máxima es de 7 niveles. El árbol
alcanza 390.508 nodos, menos los 7 no publicables = **390.501, la cifra exacta
de R7**. La condición del humano está verificada **antes de tocar código**.

### El aviso por correo (DA-4) reutiliza lo que ya existe

**No se escribe código de correo.** El patrón ya está en el repositorio:
`infra/90_create_alert.ps1` crea el grupo de acción `ag-datamart-seg-dev` con
destinatarios pasados por `-AlertEmail`, y `infra/95_create_alert_frescura.ps1`
crea una regla de consulta programada sobre `log-datamart-seg-dev` que lo dispara.
`check-cobertura` escribirá un marcador estable en el log y un script nuevo
(`infra/96_create_alert_cobertura.ps1`) creará la regla que lo busca.

**Riesgo declarado**: al no bloquear, la alerta de fallo existente
(`alert-caj-datamart-seg-dev-failed`) **no se disparará**. Esa regla nueva es la
única vía por la que el guardián se hace oír; **si no se despliega, es mudo**.
Su despliegue es manual y lo ejecuta el humano.

**Los correos NO se versionan** — lo dice `infra/90_create_alert.ps1` y se respeta:
el destinatario se pasa con `-AlertEmail` en el despliegue.

### Documento para Negocio, listo

`specs/F-052-partidas-huerfanas/aviso_negocio.md`: qué se encontró, la tabla de
cifras antes/después (margen de la 0599 del **66,3 % al 1,8 %**), a quién afecta,
la pérdida del desglose por fases y lo que hay que pedirle a quien administra
Sigrid. **Es paso bloqueante previo a publicar.**

### BLOQUEO OPERATIVO para implementar

**No hay conexión directa a la base desde el puesto** (2026-08-31,
`connection timeout expired` contra `psql-albaranes-rs9k2`). La base está viva y
responde por la vía de solo lectura del MCP, pero **esa vía no expone `raw`**, que
es donde vive el árbol de partidas. Las verificaciones con huella antes/después no
se pueden ejecutar hasta restablecerlo — probablemente una regla de firewall, y
tocar ese servidor compartido lo autoriza el humano.

## F-042 · `done` — CERRADA, y con ella los 30,4 M€ que se publicaban de más

Rama `feature/F-042-clave-fact`, 27 commits (T1–T25) más el de cierre.
`bash harness/init.sh` en código 0 (2.802 tests). Reviewer **APROBADO** en la 2ª
pasada y **criterio 5 verificado** en una 3ª contra la base ya reconstruida.
Informes: `progress/impl_F-042.md`, `progress/review_F-042.md`,
`progress/explore_F-042.md`. El relato completo, en `progress/history.md`.

**La carga que la bloqueaba terminó.** Job `caj-datamart-seg-dev-d8y5q10`,
imagen **`r20260830-0924`** —la primera con F-042—, `run-all --full` con los diez
pasos: 08:06:36 → **11:38:00 UTC**, 3 h 31 min, `Succeeded`. Comprobada **la
imagen del job**, no solo su estado: es la lección de F-047.

**Los cuatro comandos de cierre, contra la base reconstruida:**

| Comando | Resultado |
|---|---|
| `check-unicidad --timeout 300` | `mart.fact_seguimiento_mensual` **OK**: de **8.778 combinaciones duplicadas a CERO** |
| `check-cierres` | **0 discrepancias** en 8.540 cierres de 679 pares obra/ámbito; telescopio R16: **0 sin cuadrar** de 254.189 |
| `check-diccionario` | Biyección exacta **103/103**; lo publicado es lo del árbol (versión 11, hash `68ecfd13f697`) |
| `bash harness/init.sh` | **Código 0**, 2.802 tests, 100 % de 656 líneas cambiadas |

**OJO CON EL TIMEOUT, y esto vale para cualquier sesión futura:** con los 30 s por
defecto, `check-unicidad` deja `mart.fact_seguimiento_mensual` en **NO
COMPROBADO**, que no es un OK. Hay que lanzarlo con **`--timeout 300`**. Con ese
timeout el cuadro completo es **44 sin contradicción · 1 con la clave rota · 1
sin comprobar**.

**El diccionario no cambia de tamaño con F-042**, que solo altera lo que dicen
seis fichas: sigue en **103 objetos**, **798 columnas** y **46 fichas de
consumo**, y la lista de pendientes declarados no crece.

**El quinto criterio —que `importe_origen` deja de venir doblado— lo verificó el
reviewer con un oráculo independiente del build:** recompone el acumulado desde
`stg.presupuesto ⨝ stg.fases ⨝ stg.partidas` (las tres intactas en F-042) y
valida el propio oráculo reproduciendo al céntimo los 18 importes publicados de
`explore_F-042.md`. Resultado: **17.289 celdas cruzadas, desvío máximo 0,00 €**;
cambian **35 celdas de 7 obras**, exactamente la línea base honesta, por
**30.424.662,34 €** retirados, y fuera de ellas **no se mueve ninguna otra
celda**. Los casos que decidían, medidos en la base y no en un fixture: **0606
PUY DU FOU** conserva la fase 14 y cambia **0,00 €**; **0462 RETAMAR**, cuyo mes
en conflicto era el ÚLTIMO de la obra, publica ya **197.654,80 €** de coste donde
publicaba 395.309,32; y la joroba de la 0246 desaparece.

---

## LO QUE F-042 DEJA ABIERTO (nada bloquea, todo está fichado o anotado)

1. **F-051 · nueva, prioridad 3, rigor crítico.** `nombre_mes` de las filas
   reales trae **la descripción del cierre** en vez del mes, y eso rompe la
   clave de `cierre.v_pbi_planif_vs_real`. Ver la sección de abajo.
2. **El diccionario publicado dice 30.425.881,56 € y lo retirado son
   30.424.662,34.** Celdas (35) y obras (7) son exactas; ese importe describe la
   regla **exploratoria**, no la implantada. Una línea a corregir en el próximo
   `publicar-diccionario`. **Sin fichar todavía.**
3. **F-052 · nueva, prioridad 2, rigor crítico.** La observación lateral de la
   3ª pasada —«1.152 filas de la obra 0599 no llegan al fact»— **resultó ser dos
   órdenes de magnitud mayor** al medirla: son **104.737 filas** de
   `stg.presupuesto` en 6 obras, y **la 0599 TANATORIO MAJADAHONDA se ha caído
   del datamart casi entera** (104.366 de sus 108.790 filas, el 96 %). Ver la
   sección de abajo.
4. **`mart.v_master_vigente_anual` no se puede comprobar.** `check-unicidad`
   agota **300 s** sin dar veredicto, así que su clave `(obra_id, anio,
   ambito_id)` es hoy un «no lo sabemos» **permanente**, no un OK. Ninguna otra
   de las 46 de la superficie de consumo se queda sin medir con ese timeout.

---

## F-051 · `pending` — el mes que enseña Power BI no es el mes de la fila

Descubierto el 2026-08-30 por `check-unicidad` sobre la base recién
reconstruida. **No lo introducen F-042 ni F-047**: es preexistente y sale ahora
porque F-047 hizo que la vista se construya cada noche en vez de destruirse, y
por eso entra por primera vez en el alcance del check.

**El síntoma:** `cierre.v_pbi_planif_vs_real` no cumple su clave —**204
combinaciones repetidas, 472 filas**, siempre en el renglón **BENEFICIO** y hasta
cuatro filas por combinación—. Quien sume ese renglón ahí recibe hasta el
cuádruple.

**La causa, localizada en el código:** en `mart/02_build_fact.sql`, las ramas
**COSTE REAL (línea 218, ámbito 3)** y **VENTA REAL (línea 248, ámbito 7)**
rellenan `nombre_mes` con **`pm.version_descripcion`** —el texto que alguien
tecleó al cerrar en Sigrid— en vez de derivarlo de `anio_mes`, que es lo que sí
hacen las dos ramas planificadas (líneas 275 y 305). Y como el CTE `beneficio`
de la vista une `producc` con `total_costes` **solo por `(obra_id, anio_mes)`**
mientras ambos agrupan incluyendo `nombre_mes`, cada etiqueta distinta multiplica
las filas en producto cartesiano.

**El alcance, medido en la base en solo lectura:**

| Tabla | Filas REAL | Con `nombre_mes` que no es su mes | PLANIFICADO |
|---|---|---|---|
| `mart.fact_seguimiento_mensual` | 3.332.312 | **566.504 (17,0 %)** | **0** de 1.965.029 |
| `mart.fact_seguimiento_categoria` | 17.289 | **3.226 (18,7 %)** | **0** de 7.395 |

**36 pares (obra, mes)** tienen más de una etiqueta distinta, y esos 36 son los
que producen el fan-out. Ejemplos reales: la obra **0571** tiene 2020-05-01
etiquetado a la vez «Mayo 2020» y «Agosto 2020»; 186 filas de 2024 en adelante
dicen «Diciembre 2025»; 61 filas de jun-2010 dicen «DICIEMBRE 2010», en
mayúsculas, porque es texto libre.

Comparte raíz de negocio con el **patrón 2 de F-050** (la fase abarca varios
meses y Sigrid la archiva en el de arranque), pero **el arreglo no depende de esa
investigación**: aquí la decisión es de qué columna se deriva `nombre_mes`.

---

## F-052 · `pending` — una obra entera que el datamart no ve

Medido el **2026-08-31** contra la base, en solo lectura, al ir a fichar la
observación lateral del reviewer. **La observación se quedaba muy corta.**

| | Filas |
|---|---|
| `stg.presupuesto` con `partida_id` **sin ficha** en `stg.partidas` | **104.737** en 6 obras y 1.215 partidas |
| De la 0599 · `stg.presupuesto` sin ficha | **104.366** de 108.790 (**96 %**) |
| De la 0599 · `stg.plan_mensual` → `mart.fact_seguimiento_mensual` | 197.846 → **3.150** |
| Comparación: 0613 RICHMOND PARK, de tamaño parecido | 217.230 → **62.568** |

**El dato no se pierde en la ingesta, lo pierde nuestro ETL.** Las 1.215
partidas huérfanas están **las 1.215** en `raw.obrparpar`, todas con `cod` no
nulo y ninguna con `padide = 0`: Sigrid las tiene y la ingesta las trae.

**Causa probable, a confirmar:** `stg/04_partidas.sql` construye `stg.partidas`
con un recorrido **recursivo** que arranca en las raíces (`COALESCE(padide,0)=0`,
línea 56) y baja por `padide` (línea 76). Una partida cuya cadena de ancestros no
llegue a una raíz queda fuera del árbol, y entonces el **`INNER JOIN`** del build
del fact la borra del datamart **sin decir nada**.

**Lo que lo hace grave no es el importe, es el silencio.** Una obra que no está
no produce un número raro: produce respuestas como si casi no existiera. Y
ninguna comprobación de hoy lo caza —`check-unicidad` mira claves,
`check-cierres` mira la regla de F-042, `check-diccionario` mira el catálogo—:
**nadie mira que lo que entra en `stg` salga en `mart`**.

---

## F-047 · CERRADA el 2026-08-28 (absorbió F-044)

La nocturna no dejaba de crear `cierre.v_pbi_planif_vs_real`, **la destruía**
(`mart/03_agg_categoria.sql` dropea con `CASCADE` la tabla de la que cuelga).
Detalle en `progress/explore_F-047.md`, `impl_F-047.md` y `review_F-047.md`.

**La lección que vale para cualquier feature futura: el repositorio en verde no
es producción.** El despliegue llevaba congelado desde el 18 de agosto, diez
noches terminando `Succeeded` con código de hace diez días.

**F-044**, que absorbió, quedó cerrada el 2026-08-30 con las dos mediciones que
faltaban: la nocturna completa tarda **3 h 45** y termina a las 05:45 UTC (07:45
locales), aceptado por el humano; y el pico de disco fue **89,25 %** sobre los 32
GB de entonces —a 5,75 puntos del bloqueo por solo lectura—, lo que motivó la
ampliación a 64 GB del 29 por la tarde. Con 64 GB ese mismo pico sería 44,6 %.

### Lo que sigue abierto de aquella tanda

- **F-041**: el `__pycache__` opera también en serie, y es bidireccional.
- **F-049**: `mutacion.py` deja el sello `PENDIENTE` puesto tras resolverse.
- **F-048**: el guardián de secretos decide por el primer carácter del valor.
- **F-012**: siete reglas de firewall de puestos sueltos acumuladas.

---

## LO SIGUIENTE

**Ninguna feature `in_progress`.** El backlog tiene 31 abiertas; por prioridad,
las de nivel 2 son **F-036** (clasificación por oficio), **F-041** (la campaña de
mutación miente) y **F-045** (retenciones sin obra), y en el 3 entra ya
**F-051**.

### La cola de trabajo, fijada por el humano el 2026-08-31

**F-052 → F-053 → F-045 → F-051 → F-050**, con las prioridades 1 a 5 puestas en
`features.json` y la razón anotada en cada ficha. Salió de preguntarse qué falta
para que **negocio pueda usar el datamart a través del MCP**; **F-053 se insertó
en el 2 el 2026-08-31**, al aparecer en la exploración de F-052.

1. **F-052** — una obra que no está en el datamart no produce un número raro,
   produce respuestas como si casi no existiera. No hay nada que chirríe, así
   que envenena la confianza en todo lo demás.
2. **F-053** — la hermana de F-052: otras tres obras invisibles (0517, 0252,
   0720) por una causa distinta, el desempate `rn = 1` de `stg/03_obras.sql:125`
   que elige la ficha vacía. ~10,65 M€ de coste y 10,94 M€ de venta. **Pero
   primero hay que analizar si de verdad es un error**: la ficha llena puede ser
   una versión jubilada a propósito, y publicarla sería resucitar datos retirados
   o doblarlos. Es resultado válido cerrarla sin tocar código. **No se mezcla con
   F-052**: la verificación de las dos es la misma huella antes/después, y tocar
   dos causas a la vez impide saber cuál movió qué.
3. **F-045** — el caso de uso 3 del humano, las retenciones de los proveedores
   de una obra, hoy **no tiene respuesta**: `retenciones.movimientos.obra_id` no
   une con `maestro.obras`, 0 de 261 valores casan.
4. **F-051** — con el diagnóstico ya hecho y medido.
5. **F-050** — los meses que faltan, que es la raíz de negocio compartida.

**Lo demás espera**, incluidas las de prioridad 2 que había antes (F-036, F-041).

### Lo que no es una feature y decide el humano

Antes de dar el conector del MCP a la primera persona de negocio hay dos cosas
que no se resuelven con código: si se compra **Entra ID P1** —sin él entra
cualquier cuenta del tenant, y eso se aceptó por escrito cuando detrás había un
`pong`, no el seguimiento económico real— y si se encienden los **`REVOKE` de
F-034**, sabiendo que hacerlo sin verificar antes qué lee Power BI le rompe los
informes. El rol `mcp_sigrid_dm_ro` lo comparten hoy el MCP y Power BI, y ve
`raw` y `stg`.

Queda **una** cosa sin fichar, a propósito: la línea del diccionario que dice
30.425.881,56 € cuando lo retirado son 30.424.662,34. Es una línea de YAML y se
corrige **dentro de F-051**, que ya toca el diccionario y obliga a republicar;
una feature para una línea es papeleo por papeleo.
