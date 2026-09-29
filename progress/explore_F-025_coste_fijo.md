<!-- progress/explore_F-025_coste_fijo.md -->
# La ventana SÍ funciona: el 9 % era el paso equivocado

Investigación del 2026-09-07, pedida por el humano tras la primera nocturna
acotada (`swtg78p`). Pregunta de partida: «la ventana se saltó el 61 % de las
filas y solo ahorró el 9 % del tiempo, ¿por qué?».

**La pregunta estaba mal planteada, y el error es del líder.** Se comparó
`build_mart`, que F-025 **nunca tocó**. Comparado el paso que la feature sí
acota, el ahorro es del **71,2 %**.

## La cifra buena

| paso | completa `hamsh8o` (05-sep) | acotada `swtg78p` (07-sep) | diferencia |
|---|---|---|---|
| `ingest_raw` | 1.832 s | 2.256 s | +23 % (fuera de alcance) |
| **`build_stg`** | **9.527 s** | **2.740 s** | **−71,2 %** |
| `build_mart` | 2.840 s | 2.512 s | −11,6 % (ruido) |
| `build_cierre` | 2.665 s | 2.842 s | +6,6 % (ruido) |
| **noche entera** | **4 h 52** | **3 h 00** | **−38,3 %** |

`build_stg` baja **1 h 53**. El umbral de parada de la fase era el 40 % y se
supera con holgura.

## Por qué el mart no ahorra, y por qué está bien que no lo haga

**Es una decisión de diseño escrita, no un olvido.** `design.md:162-163`:
«**`build_mart` no cambia**: sigue exigiendo que la última fila de `build_stg%`
sea el paso completo, y **construye desde un `stg` completo**». Y `design.md:235`
deja `sql/mart/**` y `sql/cierre/**` explícitamente fuera de alcance.

El acotado vive solo en dos tablas: `postgres_client.py:333`,
`TABLAS_ACOTADAS = ("plan_mensual", "presupuesto")`. `build_mart_step.py` no
recibe el plan ni la lista de obras, y `mart/02_build_fact.sql` no tiene ni un
`WHERE` por obra: hace `TRUNCATE` de la tabla entera y relee
`stg.plan_mensual` completa cuatro veces. `build_cierre` igual, con cinco
lecturas.

**La prueba de una línea**: la ejecución acotada produjo **más** filas que la
completa (5.361.017 frente a 5.359.591). Si el mart estuviera acotado habría
producido una fracción. Los 233 s de diferencia son ruido entre dos noches.

**Y el motivo de fondo por el que da igual**: `mediciones.md:347-349` ya lo
había medido: «`mart` y `cierre` **no consumen créditos**: su CPU media queda
por debajo del 40 % de base, son pasos de E/S. Todo el gasto está en
`ingest_raw` y `build_stg`». F-025 nació para salvar la hucha de créditos, y
atacó exactamente donde se gasta.

## Qué midió T1, y por qué no era comparable con segundos

`mediciones.md:484-502`. T1 **no midió tiempo**: es un cociente de volumen
estimado con `SQL_PESOS_PLAN_MENSUAL` (`postgres_client.py:95-114`), que estima
las filas que `build_stg` escribiría. Su 59,2 % es el techo de ahorro **de
`build_stg`**, y en producción se ha quedado corto: el real ha sido 71,2 %.

El tropiezo tiene nombre: **hay dos ficheros llamados `02_build_fact.sql`**, uno
en `sql/stg/` y otro en `sql/mart/`. El que la ventana acota es el primero; el
que se cronometró al analizar, el segundo.

## El defecto que esto SÍ ha destapado: 552 obras de ruido en el censo

Medido en la base tras la nocturna:

| grupo | obras | filas de `stg.plan_mensual` |
|---|---|---|
| congeladas (motivo `ventana`) | 328 | 18.153.844 |
| vivas (motivo `ventana`) | 40 | — |
| **motivo `sin_filas`** | **552** | — |

De las 552, **512 siguen con cero filas después de reconstruirlas**. El censo
sale de `SQL_ESTADO_OBRAS` (`postgres_client.py:144`), que lo toma de
`raw.obr ⨝ raw.con`: **920 fichas del maestro crudo de Sigrid**, frente a las
583 de `stg.obras` y las **368 con datos reales** (= 328 + 40, cuadra exacto).

Qué son esas fichas: `0000` es «PLANTILLA DE OBRA»; el código `0001` aparece
**ocho veces** con el nombre en blanco, el `0002` cinco veces; 58 códigos tienen
más de un `obra_id`; 294 no llegan a `stg.obras`.

`domain/ventana.py:472` las clasifica con «no tiene filas construidas: completar
no es actualizar». Para una obra a medio construir es correcto; para una plantilla
sin presupuesto ni planificación, no: **no hay nada que completar y volverá cada
noche**. El coste por obra vacía es bajo —el ahorro ya es del 71 %— pero es
trabajo inútil perpetuo y ensucia el veredicto de la ventana.

Conecta con **F-053** (el desempate de `stg.obras` elige la ficha vacía), que ya
está en el backlog.

## Lo que queda sin determinar

* Los planes de ejecución reales: no se lanzó `EXPLAIN`. El reparto interno de
  los 2.740 s es deducción del texto SQL.
* Si acotar también el mart valdría la pena. **Hipótesis**: el `DELETE ... WHERE
  obra_id = ANY` sería barato porque existe `idx_fact_obra_mes`
  (`mart/01_ddl.sql:88`), pero habría que quitar el `DROP TABLE` y el `TRUNCATE`
  y filtrar el CTE `meses_partida_master` en origen. Es una feature nueva con su
  spec, no un ajuste. Y el premio sería tiempo de reloj, no créditos.

## La lección, para que no se repita

Antes de comparar dos tiempos, **verificar qué paso ataca la feature**. Aquí
había dos pasos con el mismo nombre de fichero y se cronometró el que no era, se
dio por fallida una feature que cumplía, y se llevó al humano a decidir sobre una
cifra falsa.
