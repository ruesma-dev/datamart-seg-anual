<!-- progress/impl_F-042.md -->
# F-042 · Implementación · Un solo cierre por mes en los ámbitos reales

Rama `feature/F-042-clave-fact`. **T1–T25 completas**; T14–T17 las lanzó el
humano (§5). `bash harness/init.sh` en verde. **`comparar-huellas` sale con
código 0**: *«cambian exactamente las obras previstas y solo en lo previsto; el
resto, ni un céntimo»*.

## 1. Qué cambió

| Fichero | Qué |
|---|---|
| `sql/stg/08_plan_mensual.sql` | Tres CTE en la rama de reales, el `LAG` mirando `orden_fase`, dos marcadores que acotan el bloque reutilizable. **La rama master no cambia ni un byte**, y lo fija un hash. |
| `domain/{cierres,huella}.py` | NUEVOS. La regla y el contraste de R17; `FilaHuella`, `comparar_huellas()`, `veredicto()`. Puros. |
| `…/postgres/{cierres_sql,huella_obras}.py` | NUEVOS. Las consultas de `check-cierres` y de la huella, la ejecución por tramos y el CSV. |
| `…/postgres/postgres_client.py`, `main.py` | `filas_solo_lectura()`; `check-cierres`, `huella-obras` y `comparar-huellas`, los tres de solo lectura. |
| `config/diccionario/*.yaml`, `docs/ARCHITECTURE.md`, `domain/diccionario.py`, `specs/…/design.md` | La regla, el aviso retirado, versión 11; `_validar_cardinalidad` declara su premisa (R20); §5 y §6 corregidos. |
| `tests/test_f042_*.py` (4 NUEVOS, 204 tests) y 4 ficheros de guardianes | §4. |

**Lo que NO se tocó, y es deliberado:** `mart/03_agg_categoria.sql` —su `SUM`
doblaba por ver dos filas gemelas; con una sola sale bien—, el resto de `mart/`,
los seis `JOIN` de `cierre/` (valen **porque `version` no se renumera**),
`stg/05_fases.sql` —la fase descartada sigue ahí: ese es el rastro—, `raw/` y
`build_stg_step.py`.

## 2. Decisiones de diseño

**El desplazamiento, no `dense_rank()`.** `orden_fase = numero_fase − descartes
por debajo`; `dense_rank()` cerraría los huecos que Sigrid ya trae y movería
obras que hoy están bien. **`version` publica el número original**: seis `JOIN`
de `cierre/` lo cruzan contra `stg.fases.numero_fase`; consecuencia aceptada,
huecos en 9 obras. **El SQL de la huella propuesta se RECORTA del fichero del
build**: si fuera una copia, la prueba que decide mediría otro texto. Y **el
oráculo es independiente del SQL que audita** — `check-cierres` recompone los
candidatos desde `stg.presupuesto ⨝ stg.fases`.

**Desviaciones del diseño, justificadas:** `Cierre` lleva `anio_mes` (sin el mes
no se agrupa por mes); `FilaHuella` lleva `versiones` y `codigo_obra` —lo primero
hace **observable** la parte (a) de R23, lo segundo hace utilizable
`--obras-esperadas 0246,…`—; `filas_solo_lectura()` evita dos copias del
`SET LOCAL transaction_read_only`; y **R8 no se cumple en una celda** (§5).

## 3. Fase RED · las cuatro trazas (rigor `critico`)

**T1 · la regla** (`pytest tests/test_f042_regla.py`):

```
tests\test_f042_regla.py:40: in <module>
    from etl_sigrid.domain.cierres import Cierre, plan_de_cierres
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.cierres'
============================== 1 error in 0.27s ===============================
```

**T4 · el SQL** (`pytest tests/test_f042_sql.py`). El rojo más informativo:
**14 rojos y 5 verdes**, y los 5 verdes son justo los guardianes de «esto no
cambia» (los dos hashes del master, el doble marcador de F-019, y que
`orden_fase` no aparece en el `INSERT`).

```
FAILED …::test_f042_r1_existen_las_tres_cte_de_la_regla[reales_cierres]
FAILED …::test_f042_r1_el_vigente_prefiere_el_acumulado_con_dato_y_luego_el_mas_moderno
FAILED …::test_f042_r5_los_cuatro_case_del_lag_comparan_orden_fase
FAILED …::test_f042_r22_los_marcadores_delimitan_el_bloque_de_reales
… y 10 más (lista entera en el commit a6db0e1)
14 failed, 5 passed in 1.32s
```

**T8 · la comprobación de solo lectura** y **T11 · la huella**:

```
tests\test_f042_check_cierres.py:30: from etl_sigrid.domain.cierres import ...
E   ImportError: cannot import name 'agrupar' from 'etl_sigrid.domain.cierres'
ERROR tests/test_f042_check_cierres.py — 1 error in 1.99s

tests\test_f042_huella.py:28: from etl_sigrid.domain.huella import (
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.huella'
1 error in 0.24s
```

## 4. Guardianes revisados, y uno que impedía cumplir R18

**El telescopio contra la base estaba CIEGO justo en las 9 obras** (lo cazó el
reviewer). `sql_telescopio` clasificaba «hueco de origen» mirando si `version`
era consecutiva, y `version` lleva **los huecos que crea esta feature**: la 0499
publica 17, 19, 21, 22, así que se habría apartado y habría quedado **fuera** del
recuento de series rotas — un «0 rotas» que no las había mirado. Ahora
reconstruye el `orden_fase` desde los **descartes**, observados como «candidato
que no llegó a `plan_mensual`»: un hecho, no la regla repetida. La comparte con
`domain.cierres.hay_hueco_de_origen`, donde se prueba sin base.

**F-006 · R18 lo incumplía un guardián.** Exigía la palabra **DOBLADO** en cada
columna acumulada, así que mientras existiera el aviso **no se podía retirar**:
un guardián decidiendo lo que la ficha puede decir. Se retira la palabra de
`mart.yaml` (de 6 apariciones a **0**) y el guardián pasa a exigir lo que no
caduca —que la columna cuente **qué pasó** y que es un **acumulado**—; uno nuevo
prohíbe describir el doblado **en presente**, con su control de que reconoce la
redacción vieja. Igual con `la_columna_sana_dice_que_lo_es`, que exigía «NO esta
afectada» y ahora exige que `importe_mes` **telescopea**.

**F-011 · una barrera que mentía.** `test_f011_r22_el_sql_de_stg_y_mart_no_se_
toca` mira el diff de **la rama actual**, no el de F-011, que está `done`: fuera
de su rama decía «NADIE toca nunca el SQL de `stg` ni de `mart`», falso —F-025
existe para eso—. Se acota a su rama y **se salta con motivo**.

**R19 y R20.** R19 tenía texto y **ningún guardián**:
`_objetos_que_agregan_el_fact()` filtra `esquema != "mart"` y
`cierre.v_pbi_planif_vs_real` se le escapaba; ahora hay un derivador para los
consumidores del fact **de otros esquemas**. R20: el fan-out deriva la unicidad
de la clave **declarada** —dio por única una que se repetía en 8.778 casos—, así
que declara su límite, nombra `check-unicidad`, y un guardián exige que **todo
lado `1` derivado entre en su alcance**: 31 de 31.

## 5. T14–T17 · La prueba que decide, ejecutada

| Tarea | Resultado |
|---|---|
| **T14**·**T15** | `huella_f042_stg_antes.csv` **12.356 celdas / 348 obras**; `..._mart_antes.csv` **11.883 / 348**, los cuatro ámbitos en las dos. La propuesta: código 0, **sin escribir**, disco **58,06 % constante en los 60 tramos**. |
| **T16** | **Código 0.** `OK cambian exactamente las obras previstas y solo en lo previsto; el resto, ni un céntimo`. 19 cambios de importe, **variación neta del acumulado a origen −30.424.662,34**, todos a la baja y todos en las 9 obras esperadas. Renumeraciones del tipo `[20|21] -> [21]`. **Ámbitos 8 y 11: 0 cambios** — leer la nota de abajo antes de citarlo. |

### T17 · Contraste contra la línea base, obra a obra

| Obra · mes · escenario | Hoy | Debe quedar | Resultado |
|---|---:|---:|---|
| 0499 feb-2018 Coste | 10.753.384,34 | 5.688.073,92 | ✔ |
| 0571 may-2020 Coste | 9.182.732,45 | 4.591.393,06 | ✔ |
| 0471 abr-2016 Venta | 1.917.453,12 | 1.049.832,59 | ✔ |
| 0246 jun-2010 Venta | 1.226.105,88 | 613.052,94 | ✔ (ver nota) |
| 0462 dic-2015 Coste | 395.309,32 | 197.654,52 | ✔ |
| 0545 dic-2017 Coste | 308.951,40 | 156.704,75 | ✔ |
| 0310 may-2011 Venta | 116.072,72 | 58.036,36 | ✔ |
| 0433 nov-2014 · 0606 feb-2021 | filas duplicadas | **0 €** | ✔ no aparecen en importes |

**El total no cuadra con la línea base, y es correcto que no cuadre.** Allí,
**30.425.881,56 €** con la regla «manda la fase que TERMINA dentro del mes»;
ahora, **30.424.662,34 €** con la del humano. **Diferencia: 1.219,22 €**, casi
toda la **0246**: su fase 13 se llama «AGOSTO 2010» y acaba el 31-ago, así que la
línea base se quedaba con la 12 (753.433,05) y la regla que manda con la 13 —
**1.197,99 €**—. Los 21,23 restantes **no son redondeo, son la 0462**: Venta
214.678,67 vs 214.657,72 = **20,95**, Coste 197.654,80 vs 197.654,52 = **0,28**.
Las dos obras suman los 1.219,22 exactos. No es un fallo: son **dos reglas
distintas**. *(Corrigió el fixture de `test_f042_regla.py`, que tenía los dos
importes de la 0246 intercambiados.)*

**El matiz de PUY DU FOU funcionó, y es la prueba de R2 y R11.** `0606 · ámbito
3 · 2021-02: [14|16] -> [14]`: se queda con el cierre que tiene dato y **no
aparece en la lista de importes** (0 € de cambio). Sin el matiz, la regla ingenua
habría metido ahí **−18,24 M€ que no existen**.

**Los «0 cambios en los ámbitos 8 y 11» NO son una medición, y hay que decirlo.**
Con `--propuesta`, `huella_obras.py` **copia** esas filas de la huella actual en
vez de reejecutar la rama master, así que el cero es cierto **por
construcción**. R24 los llama «la prueba de que el arreglo no se desborda» y
esta ejecución no lo prueba: **lo prueba que la rama master del SQL sea byte a
byte la misma**, fijada por hash en `tests/test_f042_sql.py`. El cero pasará a
ser una medición de verdad cuando el «después» salga de la reconstrucción real
(nivel 2). Igual de importante: **`veredicto()` demuestra el «y solo», no el
«exactamente lo previsto»** — comprueba que las obras movidas sean un
**subconjunto** de las esperadas, no que las 9 se hayan movido ni que lo hayan
hecho según R14. Eso lo demuestra esta tabla, a mano.

**El único `importe_mes` que se mueve — y R8 NO se cumple ahí.** `0471 · ámbito
7 · 2016-03: 485.843,69 → 481.305,60 (−4.538,09)`. **La causa, medida:** una
partida tiene fila en las fases **4 y 6** y **no en la 5**, con `importe_origen`
de 4.538,09 € en la 4 — exactamente el delta. Antes, su fila de la 6 no tenía
`LAG` consecutivo y publicaba **el acumulado entero**; con la 5 descartada,
`orden_fase(6) = 5` y pasa a publicar la diferencia. **El valor nuevo es el
correcto y repara el telescopio de R16**, que ahí estaba roto por +4.538,09.

Así que **R8, redactado como «el superviviente iguala la suma de lo que hoy
publican los dos cierres», no se cumple en esa celda**, porque lo que hoy se
publica ya venía mal. **Desviación aceptada y declarada** —corrige, no rompe—,
también en `design.md` §6. *(La primera versión de este informe daba otra causa
—«un tramo negativo espurio»— que es **falsa**: un tramo negativo seguido del
positivo telescopa y no deja diferencia. La cazó el reviewer midiendo.)*

## 6. La afirmación del diseño que la medición desmintió

El §5 del diseño decía que «el agregado de `stg` es exactamente el que
`mart.fact_seguimiento_categoria` publicaría». Comparadas las dos huellas de T14
celda a celda: **cierto en los reales** —desviación **0 en 8.243 celdas**— y **falso en los
master**, donde `stg` guarda todas las versiones y `mart` solo la vigente:
**3.504 celdas difieren** y en la 0644 son **43,6 M€ frente a 1,3 M€**. **No
invalida nada** —T16 compara `stg` contra `stg`—, pero habría hecho creer a
alguien que encontró un defecto de 40 millones. Corregida en `design.md` §5 **y
en el docstring de `huella_obras.py`**, donde la frase seguía viva.

**Los CSV no se versionan** (precedente de F-019: `.gitignore:27` ya trae
`huella_*.csv`). Son evidencia de una ejecución, no fuente; lo versionado es
**cómo reproducirlos**.

## 7. Evidencias

| Evidencia | Valor |
|---|---|
| **Tests ejecutados** | **2.802 pasados, 130 saltados, 0 fallos** (`bash harness/init.sh`, código 0) |
| **Cobertura de las líneas cambiadas** | **100,0 % de 631** (631/631, umbral 80 %, nivel `critico`) |
| **Mutantes y supervivientes** | **N/A por decisión del humano** (ver abajo) |
| **Tiempo de la suite** | **7 min 47 s** (467,33 s) |
| **Prueba antes/después (R22–R25)** | Código **0**; 19 cambios de importe, **−30.424.662,34 €**, todos en las 9 obras esperadas. Los master, sin cambios **por construcción** (§5) |
| Tests propios de F-042 | 204 (`regla` 98, `sql` 20, `check_cierres` 35, `huella` 51) |
| Avisos de `ruff` | **237**, uno MENOS que antes de la feature: cero deuda nueva |

**SIN CAMPAÑA DE MUTACIÓN.** Decisión del humano del **2026-08-29**: «no me
hacen falta mutation test». `CHECKPOINTS.md` la exige en **C4 bis** para rigor
`critico`, así que **debe declararse N/A citando esta decisión**. La sustituye la
prueba antes/después, ya ejecutada: para un cambio que reescribe datos la
garantía pertinente no es «mis tests detectan cambios en el código» sino **«no
cambian datos que no deberían cambiar»**. **Fase RED y cobertura sí se exigen y
están cumplidas.**

## 8. Lo que queda fuera del alcance

- **El patrón 2 sigue abierto.** En 8 obras la fase abarca varios meses y Sigrid
  la archiva en su mes de arranque: **faltan meses enteros** (jul y ago 2010 en la
  0246). F-042 arregla el doblado, no el eje temporal. Fichado como **F-050**.
- **`cierre` no se mide en el nivel 1**: agrega por su propio `mes_canonico`. Se
  comprueba en el nivel 2, y por eso `build-cierre` está en los pasos de cierre.
- **La base todavía tiene el defecto.** Nada ha escrito en `sigrid_dm`: hasta el
  build, `check-unicidad` seguirá dando 8.778, y por eso `publicar-diccionario`
  va **después**. Las fichas ya hablan en pasado y serían falsas hasta entonces.
