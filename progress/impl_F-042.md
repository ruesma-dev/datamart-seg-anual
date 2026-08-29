<!-- progress/impl_F-042.md -->
# F-042 · Implementación · Un solo cierre por mes en los ámbitos reales

Rama `feature/F-042-clave-fact`. **T1–T25 completas**; T14–T17 las lanzó el
humano y sus resultados están en §5. `bash harness/init.sh` en verde.

**El veredicto:** `comparar-huellas` sale con **código 0** — *«cambian
exactamente las obras previstas y solo en lo previsto; el resto, ni un
céntimo»*—, con **0 cambios en los ámbitos master 8 y 11**.

## 1. Qué cambió

| Fichero | Qué |
|---|---|
| `sql/stg/08_plan_mensual.sql` | Tres CTE en la rama de reales, el `LAG` mirando `orden_fase`, dos marcadores que acotan el bloque reutilizable. **La rama master no cambia ni un byte**, y lo fija un hash. |
| `domain/{cierres,huella}.py` | NUEVOS. La regla y el contraste de R17; `FilaHuella`, `comparar_huellas()`, `veredicto()`. Puros. |
| `…/postgres/{cierres_sql,huella_obras}.py` | NUEVOS. Las consultas de `check-cierres` y de la huella, la ejecución por tramos y el CSV. |
| `…/postgres/postgres_client.py`, `main.py` | `filas_solo_lectura()`; `check-cierres`, `huella-obras` y `comparar-huellas`, los tres de solo lectura. |
| `config/diccionario/*.yaml`, `docs/ARCHITECTURE.md` | La regla, el aviso retirado, versión 11. |
| `domain/diccionario.py`, `specs/…/design.md` | `_validar_cardinalidad` declara su premisa (R20); §5 corregido (§6). |
| `tests/test_f042_*.py` (4 NUEVOS, 196 tests) y 4 ficheros de guardianes | §4. |

**Lo que NO se tocó, y es deliberado:** `mart/03_agg_categoria.sql` —su `SUM`
doblaba porque veía dos filas gemelas; con una sola sale bien—, el resto de
`mart/`, los seis `JOIN` de `cierre/` (siguen valiendo **precisamente porque
`version` no se renumera**), `stg/05_fases.sql` —la fase descartada sigue ahí:
ese es el rastro—, `raw/` y `build_stg_step.py`.

## 2. Decisiones de diseño

**El desplazamiento, no `dense_rank()`.** `orden_fase = numero_fase − descartes
por debajo`. `dense_rank()` cerraría también los huecos que Sigrid ya trae y
cambiaría `importe_mes` en obras que hoy están bien.

**`version` publica el número original**: seis `JOIN` de `cierre/` lo cruzan
contra `stg.fases.numero_fase`. Consecuencia aceptada: huecos en 9 obras.

**El SQL de la huella propuesta se RECORTA del fichero del build**, entre sus dos
marcadores. Si fuera una copia, la prueba que decide mediría un texto distinto
del que va a correr. Y **el oráculo es independiente del SQL que audita**:
`check-cierres` recompone los candidatos desde `stg.presupuesto ⨝ stg.fases`.

**Desviaciones del diseño, las tres justificadas:** `Cierre` lleva `anio_mes`
(sin el mes no se agrupa por mes); `FilaHuella` lleva `versiones` y `codigo_obra`
—lo primero hace **observable** la parte (a) de R23, lo segundo hace utilizable
`--obras-esperadas 0246,…`—; y `filas_solo_lectura()` evita que los dos comandos
tengan cada uno su copia del `SET LOCAL transaction_read_only`.

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
FAILED …::test_f042_r1_existen_las_tres_cte_de_la_regla[reales_vigente]
FAILED …::test_f042_r1_existen_las_tres_cte_de_la_regla[reales_orden]
FAILED …::test_f042_r1_el_vigente_prefiere_el_acumulado_con_dato_y_luego_el_mas_moderno
FAILED …::test_f042_r11_el_acumulado_del_mes_no_puede_ser_nulo
FAILED …::test_f042_r5_el_orden_se_desplaza_por_descartes_y_nunca_con_dense_rank
FAILED …::test_f042_r5_la_ventana_del_desplazamiento_particiona_por_obra_y_ambito
FAILED …::test_f042_r5_los_cuatro_case_del_lag_comparan_orden_fase
FAILED …::test_f042_r5_la_ventana_del_lag_ordena_por_orden_fase
FAILED …::test_f042_r1_reales_con_lag_lee_solo_los_cierres_que_viven
FAILED …::test_f042_r9_el_bloque_de_reales_no_menciona_ninguna_cte_del_master
FAILED …::test_f042_el_filtro_de_tramos_esta_dentro_del_bloque_de_reales
FAILED …::test_f042_r22_los_marcadores_delimitan_el_bloque_de_reales
FAILED …::test_f042_r22_el_bloque_reutilizable_no_arrastra_el_insert
14 failed, 5 passed in 1.32s
```

**T8 · la comprobación de solo lectura** (`pytest tests/test_f042_check_cierres.py`):

```
tests\test_f042_check_cierres.py:30: in <module>
    from etl_sigrid.domain.cierres import Cierre, agrupar, contrastar
E   ImportError: cannot import name 'agrupar' from 'etl_sigrid.domain.cierres'
ERROR tests/test_f042_check_cierres.py — 1 error in 1.99s
```

**T11 · la huella** (`pytest tests/test_f042_huella.py`):

```
tests\test_f042_huella.py:28: in <module>
    from etl_sigrid.domain.huella import (
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.huella'
1 error in 0.24s
```

## 4. Guardianes de otras features que había que revisar

**F-006 · diez tests escritos para un defecto ABIERTO.** No se desactivó
ninguno: `la_columna_sana_dice_que_lo_es` exigía la frase «NO esta afectada»,
que con el defecto corregido describe algo inexistente; ahora exige lo
permanente —que `importe_mes` **telescopea**—. Los demás muerden igual.

**F-011 · una barrera que estaba mintiendo.** `test_f011_r22_el_sql_de_stg_y_
mart_no_se_toca` mira el diff de **la rama actual**, no el de F-011, que está
`done`: fuera de su rama decía «NADIE toca nunca el SQL de `stg` ni de `mart`»,
falso —F-025 existe para eso—. Se acota a su rama y **se salta con motivo**.

**R20 · la detección de fan-out.** Deriva la unicidad de la clave **declarada**,
y durante ocho días dio por única una que se repetía en 8.778 casos. Ahora
declara su límite y nombra su complemento (`check-unicidad`), y un guardián
nuevo exige que **todo objeto del que se derive un lado `1` esté dentro del
alcance de `check-unicidad`**: hoy son 31, los 31 cubiertos.

## 5. T14–T17 · La prueba que decide, ejecutada

| Tarea | Resultado |
|---|---|
| **T14** (humano) | `huella_f042_stg_antes.csv` **12.356 celdas / 348 obras**; `huella_f042_mart_antes.csv` **11.883 / 348**. Los cuatro ámbitos en las dos. |
| **T15** (líder) | Código 0, **sin escribir**. Ocupación de disco **58,06 % constante en los 60 tramos**. |
| **T16** | **Código 0.** `OK cambian exactamente las obras previstas y solo en lo previsto; el resto, ni un céntimo`. **Ámbitos 8 y 11: 0 cambios.** 19 cambios de importe, **variación neta del acumulado a origen −30.424.662,34**, todos a la baja y todos en las 9 obras esperadas. Renumeraciones del tipo `[20|21] -> [21]`. |

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
| Ámbitos 8 y 11 | — | **0 cambios** | ✔ |

**El total no cuadra con la línea base, y es correcto que no cuadre.** Allí:
**30.425.881,56 €** con la regla «manda la fase que TERMINA dentro del mes».
Ahora: **30.424.662,34 €** con la del humano, «manda el cierre más moderno».
**Diferencia: 1.219,22 €**, y es casi toda la **0246**: su fase 13 se llama
«AGOSTO 2010» y acaba el 31-ago, así que la línea base se quedaba con la 12
(753.433,05) y la regla que manda se queda con la 13 (754.631,04) —
**1.197,99 €**—; los 21,23 restantes son céntimos de redondeo. No es un fallo:
son **dos reglas distintas**. *(Corrigió el fixture de `test_f042_regla.py`, que
tenía los dos importes de la 0246 intercambiados.)*

**El matiz de PUY DU FOU funcionó, y es la prueba de R2 y R11.** `0606 · ámbito
3 · 2021-02: [14|16] -> [14]`: se queda con el cierre que tiene dato y **no
aparece en la lista de importes** (0 € de cambio). Sin el matiz, la regla ingenua
habría metido ahí **−18,24 M€ que no existen**.

**El único `importe_mes` que se mueve, y se mueve para bien.** `0471 · ámbito 7
· 2016-03: 485.843,69 → 481.305,60 (−4.538,09)`. Comprobado contra el origen: el
cierre descartado (fase 5) traía **acumulado 377.479,52 frente a los 386.314,93
de febrero**, o sea **menos que el mes anterior**, y el movimiento arrastraba ese
tramo negativo espurio. Ahora es la diferencia limpia entre dos cierres
consecutivos: **el arreglo lo corrige de paso.**

## 6. La afirmación del diseño que la medición desmintió

El §5 del diseño decía que «el agregado de `stg` es exactamente el que
`mart.fact_seguimiento_categoria` publicaría». Comparadas las dos huellas de T14
celda a celda:

| Ámbito | Comunes | Difieren en origen |
|---|---:|---:|
| 3 · COSTE | 4.251 | **0** |
| 7 · VENTA | 3.992 | **0** |
| 8 · MASTER COSTE | 1.832 | 1.766 |
| 11 · MASTER VENTA | 1.808 | 1.738 |

**Cierto en los reales** —desviación 0 en 8.243 celdas, que valida la premisa
justo donde importa— y **falso en los master**: allí `stg` guarda todas las
versiones (`versiones` trae `1|2|3|…|28`) y `mart` publica solo la vigente, de
donde salen 473 celdas de más e importes disparados (0644: **43,6 M€ en `stg`
frente a 1,3 M€ en `mart`**). **No invalida nada** —T16 compara `stg` contra
`stg`—, pero la frase habría hecho creer a alguien que encontró un defecto de 40
millones. Corregida en `design.md`.

**Los CSV no se versionan**, siguiendo el precedente de F-019: `.gitignore:27`
ya trae `huella_*.csv`. Son evidencia de una ejecución, no fuente; lo versionado
es **cómo reproducirlos** (§5 y `tasks.md`).

## 7. Evidencias

| Evidencia | Valor |
|---|---|
| **Tests ejecutados** | **2.791 pasados, 130 saltados, 0 fallos** (`bash harness/init.sh`, código 0) |
| **Cobertura de las líneas cambiadas** | **100,0 % de 649** (649/649, umbral 80 %, nivel `critico`) |
| **Mutantes y supervivientes** | **N/A por decisión del humano** (ver abajo) |
| **Tiempo de la suite** | **6 min 15 s** (375,39 s) |
| **Prueba antes/después (R22–R25)** | Código **0**; 19 cambios de importe, **−30.424.662,34 €**, todos en las 9 obras esperadas; **0 en los ámbitos 8 y 11** |
| Tests propios de F-042 | 196 (`regla` 96, `sql` 20, `check_cierres` 29, `huella` 51) |
| Avisos de `ruff` | **238**, los mismos de antes de la feature: cero deuda nueva |

**SIN CAMPAÑA DE MUTACIÓN, y el reviewer tiene que saberlo.** Decisión del
humano del **2026-08-29**: «no me hacen falta mutation test». `CHECKPOINTS.md`
la exige en **C4 bis** para rigor `critico`, así que **debe declararse N/A
citando esta decisión**; sin ese motivo escrito, un checkbox vacío ahí es
CHANGES_REQUESTED con razón. La sustituye la prueba antes/después, ya ejecutada
y en verde: para un cambio que reescribe datos la garantía pertinente no es «mis
tests detectan cambios en el código» sino **«no cambian datos que no deberían
cambiar»**. **Fase RED y cobertura sí se exigen y están cumplidas.**

## 8. Lo que queda fuera del alcance

- **El patrón 2 sigue abierto.** En 8 obras la fase abarca varios meses y Sigrid
  la archiva en su mes de arranque: **faltan meses enteros** (jul y ago 2010 en
  la 0246; jun–ago 2020 en la 0571). F-042 arregla el doblado del acumulado, no
  el eje temporal. Fichado como **F-050**.
- **`cierre` no se mide en el nivel 1**: agrega por su propio `mes_canonico`, no
  por `anio_mes`. Se comprueba en el nivel 2, y por eso `build-cierre` está en
  los pasos de cierre.
- **La base todavía tiene el defecto.** Nada ha escrito en `sigrid_dm`: hasta que
  el humano lance `stage` + `build-mart` + `build-cierre`, `check-unicidad`
  seguirá dando 8.778, y por eso `publicar-diccionario` va **después** del build.
