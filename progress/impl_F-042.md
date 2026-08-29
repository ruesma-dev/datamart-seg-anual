<!-- progress/impl_F-042.md -->
# F-042 · Implementación · Un solo cierre por mes en los ámbitos reales

Rama `feature/F-042-clave-fact`, 16 commits (T1–T13, T18–T23).
**T14–T17 son MANUAL y las lanza el humano**: falta su resultado para cerrar.

## 1. Qué cambió

| Fichero | Qué |
|---|---|
| `sql/stg/08_plan_mensual.sql` | Tres CTE en la rama de reales, el `LAG` mirando `orden_fase`, dos marcadores que acotan el bloque reutilizable. **La rama master no cambia ni un byte.** |
| `etl_sigrid/domain/cierres.py` | NUEVO. La regla y el contraste de R17, puros. |
| `etl_sigrid/domain/huella.py` | NUEVO. `FilaHuella`, `comparar_huellas()`, `veredicto()`. |
| `etl_sigrid/infrastructure/postgres/cierres_sql.py` | NUEVO. Las tres consultas de `check-cierres`. Solo texto. |
| `etl_sigrid/infrastructure/postgres/huella_obras.py` | NUEVO. Las tres consultas de la huella, la ejecución por tramos y el CSV. |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | `filas_solo_lectura()`. |
| `main.py` | `check-cierres`, `huella-obras`, `comparar-huellas`. Los tres de solo lectura. |
| `config/diccionario/{stg,mart,cierre,00_global}.yaml` | La regla, el aviso retirado, versión 11. |
| `etl_sigrid/domain/diccionario.py` | `_validar_cardinalidad` declara su premisa (R20). |
| `docs/ARCHITECTURE.md` | La regla en «Semántica Sigrid imprescindible». |
| `tests/test_f042_{regla,sql,check_cierres,huella}.py` | NUEVOS, 194 tests. |
| `tests/test_f006_{stg_trampas,relaciones,contexto}.py` | Guardianes revisados (§4). |

**Lo que NO se tocó, y es deliberado:** `mart/03_agg_categoria.sql` —su `SUM`
doblaba porque veía dos filas gemelas; con una sola sale bien sin cambiar una
letra—, `mart/01_ddl.sql`, `05_views_powerbi.sql`, los seis `JOIN` de `cierre/`
(siguen valiendo **precisamente porque `version` no se renumera**), `stg/05_fases.sql`
—la fase descartada sigue ahí: ese es el rastro—, `raw/` y `build_stg_step.py`.

## 2. Decisiones de diseño

**El desplazamiento, no `dense_rank()`.** `orden_fase = numero_fase − descartes
por debajo`. `dense_rank()` cerraría también los huecos que Sigrid ya trae y
cambiaría `importe_mes` en obras que hoy están bien.

**`version` publica el número original.** Seis `JOIN` de `cierre/` lo cruzan
contra `stg.fases.numero_fase`. Consecuencia aceptada y fichada: huecos en 9
obras. El orden renumerado vive dentro del build y muere ahí.

**El SQL de la huella propuesta se RECORTA del fichero del build**, entre
`/*F042_INICIO_REALES*/` y `/*F042_FIN_REALES*/`, y se envuelve en su propio
`WITH`. Si fuera una copia, la prueba que decide mediría un texto distinto del
que va a correr esa noche.

**El oráculo es independiente del SQL que audita.** `check-cierres` recompone
los candidatos desde `stg.presupuesto ⨝ stg.fases`, no desde `stg.plan_mensual`.
Si salieran de ahí, la comprobación se preguntaría a sí misma.

**Desviaciones respecto al diseño, las tres justificadas:**

1. `Cierre` lleva `anio_mes` (el diseño escribía `Cierre(numero_fase, acumulado)`):
   sin el mes no se puede agrupar por mes, que es lo que hace la regla.
2. `FilaHuella` lleva `versiones` y `codigo_obra` además de los seis campos del
   diseño. `versiones` es lo que hace **observable** la parte (a) de R23 —las
   obras cuya numeración cambia—; `codigo_obra` es lo que hace utilizable
   `--obras-esperadas 0246,0310,…`, que el humano escribió con códigos.
3. `PostgresClient.filas_solo_lectura()` no estaba en el diseño. Es lo que evita
   que `check-cierres` y `huella-obras` tengan cada uno su copia del
   `SET LOCAL transaction_read_only`. Ahí es donde una de las dos se lo deja.

## 3. Fase RED · las cuatro trazas

Rigor `critico`. Cada bloque empezó con su test en rojo, ejecutado y pegado.

**T1 · la regla** (`pytest tests/test_f042_regla.py`):

```
tests\test_f042_regla.py:40: in <module>
    from etl_sigrid.domain.cierres import Cierre, plan_de_cierres
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.cierres'
============================== 1 error in 0.27s ===============================
```

**T4 · el SQL** (`pytest tests/test_f042_sql.py`). El rojo más informativo de
los cuatro: **14 rojos y 5 verdes**, y los 5 verdes son justo los guardianes de
«esto no cambia» (los dos hashes del master, el doble marcador de F-019, y que
`orden_fase` no aparece en el `INSERT`).

```
FAILED tests/test_f042_sql.py::test_f042_r1_existen_las_tres_cte_de_la_regla[reales_cierres]
FAILED tests/test_f042_sql.py::test_f042_r1_existen_las_tres_cte_de_la_regla[reales_vigente]
FAILED tests/test_f042_sql.py::test_f042_r1_existen_las_tres_cte_de_la_regla[reales_orden]
FAILED tests/test_f042_sql.py::test_f042_r1_el_vigente_prefiere_el_acumulado_con_dato_y_luego_el_mas_moderno
FAILED tests/test_f042_sql.py::test_f042_r11_el_acumulado_del_mes_no_puede_ser_nulo
FAILED tests/test_f042_sql.py::test_f042_r5_el_orden_se_desplaza_por_descartes_y_nunca_con_dense_rank
FAILED tests/test_f042_sql.py::test_f042_r5_la_ventana_del_desplazamiento_particiona_por_obra_y_ambito
FAILED tests/test_f042_sql.py::test_f042_r5_los_cuatro_case_del_lag_comparan_orden_fase
FAILED tests/test_f042_sql.py::test_f042_r5_la_ventana_del_lag_ordena_por_orden_fase
FAILED tests/test_f042_sql.py::test_f042_r1_reales_con_lag_lee_solo_los_cierres_que_viven
FAILED tests/test_f042_sql.py::test_f042_r9_el_bloque_de_reales_no_menciona_ninguna_cte_del_master
FAILED tests/test_f042_sql.py::test_f042_el_filtro_de_tramos_esta_dentro_del_bloque_de_reales
FAILED tests/test_f042_sql.py::test_f042_r22_los_marcadores_delimitan_el_bloque_de_reales
FAILED tests/test_f042_sql.py::test_f042_r22_el_bloque_reutilizable_no_arrastra_el_insert
14 failed, 5 passed in 1.32s
```

**T8 · la comprobación de solo lectura** (`pytest tests/test_f042_check_cierres.py`):

```
tests\test_f042_check_cierres.py:30: in <module>
    from etl_sigrid.domain.cierres import Cierre, agrupar, contrastar
E   ImportError: cannot import name 'agrupar' from 'etl_sigrid.domain.cierres'
=========================== short test summary info ===========================
ERROR tests/test_f042_check_cierres.py
1 error in 1.99s
```

**T11 · la huella** (`pytest tests/test_f042_huella.py`):

```
tests\test_f042_huella.py:28: in <module>
    from etl_sigrid.domain.huella import (
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.huella'
1 error in 0.24s
```

Un rojo intermedio que conviene contar porque cambió el código: en T2 falló
`test_f042_r4_con_cuatro_cierres_y_los_dos_modernos_a_cero_gana_el_ultimo_con_dato`
con `mappingproxy({2: 1}) == {2: 2}`. **La equivocada era la expectativa del
test**, no el código: con la fase 1 descartada, la 2 baja a orden 1 —pasa a ser
la primera de la serie, con `LAG` nulo—, que es lo que hace el
`ROWS … AND 1 PRECEDING` del SQL. Se corrigió el test y se dejó escrito el
porqué.

## 4. Los guardianes de F-006 que había que revisar

Diez tests de `test_f006_stg_trampas.py` estaban escritos para un defecto
**abierto** y con el arreglo se quedaban en falso. No se desactivó ninguno:

- `la_columna_sana_dice_que_lo_es` exigía la frase «NO esta afectada». Con el
  defecto corregido eso describe algo que no existe y convierte la ficha en un
  museo. Ahora exige lo permanente: que `importe_mes` diga que **telescopea**,
  que es la propiedad medida 200/200 y la razón de que F-042 renumere.
- Los demás siguen mordiendo **tal cual**, y las fichas se escribieron para
  cumplirlos: la consulta de unicidad vuelve publicada con su resultado de hoy
  (**0**) y el de antes (**8.778**); donde se nombra el 22 se nombra el 9; y
  donde una columna cuenta que estuvo DOBLADA, la cabecera lo cuenta y la nombra.

**R20, la detección de fan-out.** `_validar_cardinalidad` deriva la unicidad de
la clave **declarada**, y durante ocho días dio por única una clave que se
repetía en 8.778 casos. Dos cambios: el detector declara su límite y nombra su
complemento (`check-unicidad`), con un test que lo comprueba; y un guardián
nuevo exige que **todo objeto del que se derive un lado `1` esté dentro del
alcance de `check-unicidad`**. Hoy son 31 objetos, los 31 cubiertos, y
`check-unicidad --todos` alcanza 57 de 103 fichas: el guardián discrimina.

## 5. Verificaciones MANUAL pendientes (T14–T17), y quién las lanza

**El humano.** T14–T16 en `progress/current.md` con los comandos exactos.
**Orden crítico**: la huella de ANTES antes de reconstruir nada.
Verificado en seco: los tres comandos existen, `--help` responde, `--dry-run` de
`check-cierres` imprime sus tres consultas sin abrir conexión.

### T17 · Contraste contra la línea base — **PENDIENTE DEL HUMANO**

| Obra · mes · escenario | Hoy (medido 2026-08-28) | Debe quedar | Resultado real |
|---|---:|---:|---|
| 0499 feb-2018 Coste | 10.753.384,34 | 5.688.073,92 | _(T17)_ |
| 0571 may-2020 Coste | 9.182.732,45 | 4.591.393,06 | _(T17)_ |
| 0471 abr-2016 Venta | 1.917.453,12 | 1.049.832,59 | _(T17)_ |
| 0246 jun-2010 Venta | 1.226.105,88 | 613.052,94 | _(T17)_ |
| 0462 dic-2015 Coste | 395.309,32 | 197.654,52 | _(T17)_ |
| 0545 dic-2017 Coste | 308.951,40 | 156.704,75 | _(T17)_ |
| 0310 may-2011 Venta | 116.072,72 | 58.036,36 | _(T17)_ |
| 0433 nov-2014 · 0606 feb-2021 | filas duplicadas | **0 € de cambio** | _(T17)_ |
| Ámbitos 8 y 11 | — | **0 cambios** | _(T17)_ |

Después, los pasos de cierre de `tasks.md` (escrituras en producción, también
del humano): `stage` + `build-mart` + `build-cierre` sin `ingest`, la huella del
después ya materializada, `check-unicidad` (0), `check-cierres`,
`check-diccionario`, `publicar-diccionario` y `timings`.

## 6. Evidencias

| Evidencia | Valor |
|---|---|
| **Tests ejecutados** | _(init.sh)_ |
| **Cobertura de las líneas cambiadas** | _(init.sh)_ |
| **Mutantes y supervivientes** | **N/A por decisión del humano** (ver abajo) |
| **Tiempo de la suite** | _(init.sh)_ |
| Tests propios de F-042 | 194 (`test_f042_regla` 96, `sql` 20, `check_cierres` 29, `huella` 49) |
| Avisos de `ruff` | **238**, exactamente los de antes de la feature: cero deuda nueva |

**SIN CAMPAÑA DE MUTACIÓN, y el reviewer tiene que saberlo.** Decisión del
humano del **2026-08-29**: «no me hacen falta mutation test». `CHECKPOINTS.md`
la exige en **C4 bis** para rigor `critico`, así que **debe declararse N/A
citando esta decisión**; sin ese motivo por escrito, un checkbox vacío ahí es
CHANGES_REQUESTED con razón. La evidencia que la sustituye es la prueba
antes/después (R22–R25, T14–T17), y el argumento es bueno: para un cambio que
reescribe datos, la garantía pertinente no es «mis tests detectan cambios en el
código» sino **«no cambian datos que no deberían cambiar»**. **Fase RED y
cobertura sí se exigen y están cumplidas** (§3 y esta tabla).

## 7. Lo que queda fuera del alcance

- **El patrón 2 sigue abierto.** En 8 obras la fase abarca varios meses y Sigrid
  la archiva en su mes de arranque, así que **faltan meses enteros** en el
  datamart (jul y ago 2010 en la 0246; jun, jul y ago 2020 en la 0571). F-042
  arregla el doblado del acumulado, no el eje temporal. La investigación de por
  qué Sigrid tiene esas obras así está fichada como **F-050**.
- **`cierre` no se mide en el nivel 1.** Agrega por su propio `mes_canonico`
  (`cierre.fn_mes_de_fase`) y no por `anio_mes`, así que la huella de `stg` no
  predice sus números. Se comprueba en el nivel 2, y por eso `build-cierre` está
  en los pasos de cierre.
- **La base todavía tiene el defecto.** Nada de esto ha corrido contra
  `sigrid_dm`: hasta que el humano lance la reconstrucción, `check-unicidad`
  seguirá dando 8.778. El diccionario ya describe el estado posterior, y por eso
  `publicar-diccionario` va **después** del build en la lista de cierre.
