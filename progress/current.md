<!-- progress/current.md -->
# Estado actual · 2026-08-30

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

**F-052 → F-045 → F-051 → F-050**, con las prioridades 1, 2, 3 y 4 puestas en
`features.json` y la razón anotada en cada ficha. Salió de preguntarse qué falta
para que **negocio pueda usar el datamart a través del MCP**:

1. **F-052** — una obra que no está en el datamart no produce un número raro,
   produce respuestas como si casi no existiera. No hay nada que chirríe, así
   que envenena la confianza en todo lo demás.
2. **F-045** — el caso de uso 3 del humano, las retenciones de los proveedores
   de una obra, hoy **no tiene respuesta**: `retenciones.movimientos.obra_id` no
   une con `maestro.obras`, 0 de 261 valores casan.
3. **F-051** — con el diagnóstico ya hecho y medido.
4. **F-050** — los meses que faltan, que es la raíz de negocio compartida.

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
