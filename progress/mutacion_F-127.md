<!-- progress/mutacion_F-127.md -->
# F-127 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-127 --base main --workers 3 --con-seleccion` el 2026-11-22 03:04.

## Alcance

Origen del diff: **rama** (`90d1bfd552d7f1157f4e9f23c5842a461a641213` .. `puerta/F-127`).

| Fichero | Líneas en alcance | Mutantes generados |
|---|---|---|
| `config/settings.py` | 10 | 0 — sin mutantes |
| `etl_sigrid/application/steps/build_contabilidad_step.py` | 50 | 0 — sin mutantes |
| `etl_sigrid/domain/restriccion_personal.py` | 137 | 30 |
| **Total** | **197** | **30** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 30 |
| Mutantes evaluados | 19 |
| Muertos | 19 |
| Supervivientes | 0 (0 podados sin ejecutar, 0 medidos) |
| Timeouts | 0 |
| Indeterminados | 0 |
| Timeouts repasados en serie | 0: ningún mutante agotó el reloj |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 8636.9 s |
| SHA de HEAD medido | `b45f5acc14e0161d97a1a0350cbaf10442e9a0dd` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-127_29k8p6hf/wk_0` | 1862.1 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-127_29k8p6hf/wk_1` | 1896.9 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-127_29k8p6hf/wk_2` | 1923.8 |
| Media por mutante evaluado (s) | 454.6 |
| Timeout efectivo por mutante (s) | 2400 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 2400 |
| Workers | 3 |
| Un mutante por línea | sí — 30 generados → 19 candidatos, uno por línea |
| Muestreo | no: campaña completa (19 candidatos ≤ tope 100 del nivel `critico`) |
| Selección de tests | activa — mapa línea -> tests, poda y subconjuntos validados |
| SHA del mapa | `b45f5acc14e0161d97a1a0350cbaf10442e9a0dd` |
| Medición del mapa (s) | `.`: 2662.5 |
| Tests en la suite | `.`: 16408 |
| Tamaño medio del subconjunto | 8.5 tests (15 mutantes) |
| Revalidados con la suite entera | 0 (0 murieron al revalidar) |
| Subconjuntos descartados | 0 |
| Podados (sin ejecutar) | 0 |
| Tiempo ahorrado por la poda (s) — derivado: podados × línea base | 0.0 |
| Media por mutante juzgado con la suite entera (s) | 1139.5 (4 mutantes) |

## Cómo se juzgó

- **PODADO**: ningún proceso medido ejecuta la sentencia del mutante, así que no puede cambiar ninguna ejecución; es superviviente sin escribirlo ni correr nada. Un PODADO necesita la misma justificación escrita que uno medido. Riesgo residual: un subproceso que no hereda el entorno o usa otro intérprete no se mide, y sus líneas parecerían no ejecutadas; `--sin-seleccion` lo descarta.
- El **muerto** del subconjunto **no se revalida**: ese subconjunto se corrió antes SIN mutar y salió verde, así que el test que cae lo hace por el mutante, y ese test también está en la suite entera.
- Lo que el subconjunto no mata (superviviente, timeout, indeterminado) **sí se revalida** con la suite entera y el mutante aún aplicado: que no caiga ninguno de sus tests no prueba que no caiga ninguno de la suite, y el veredicto que cuenta es el de la suite entera.
- El **timeout** por mutante sigue saliendo de la **línea base** de la suite entera: es la única medida tomada con la contención de los W workers; un subconjunto no tiene base propia, medirla costaría más de lo que ahorra, y un mutante que cuelga cuelga igual con dos tests que con doscientos.


## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.

## Análisis (implementer, 2026-11-22)

**Cómo se lanzó.** El **líder** la lanzó en el checkout principal (con `.env`) sobre `b45f5ac`, el APPROVED de la review en su pasada 2, y tardó 8.637 s:

```
python -m harness.mutacion --feature F-127 --base main --rama puerta/F-127 --workers 3 --timeout 2400 --con-seleccion
```

**Los 11 generados que no se evaluaron (30 -> 19).**
- El nivel `critico` deja **uno por línea** (`reducir_por_linea`). Las líneas 209, 249, 251, 253, 265, 283 y 284 tenían más de un mutante, y se sorteó uno de cada una.
- Regenerados con `generar_mutantes` sobre el fichero de `b45f5ac` y las líneas del diff, salen exactamente los 30.
- Los 11 de fuera **los pasé también en serie**, con la batería de abajo más el barrido de F-006. Resultado: 8 muertos y 3 vivos.

| Línea · operador | Mutación | En serie |
|---|---|---|
| 209 · booleano | `frozen=True` -> `frozen=False` | muerto (`test_f006_toda_dataclass_del_paquete_es_inmutable[...FilaAnalitica]`) |
| 249 · veracidad | `if cuenta_id is None` -> `if not cuenta_id` | **vivo** |
| 251 · negacion | `if not (cuenta_id in ... or en_centro_contrapartida)` | muerto (`r7_c3_la_cp_actual_del_recurso`) |
| 251 · logico | `or` -> `and` | muerto (`r7_c3_la_cp_actual_del_recurso`) |
| 253 · comparacion | `in centros_contrapartida` -> `not in` | muerto (`r7_c3_d7_cuenta_antigua_del_centro_de_cp_con_abono_analitico`) |
| 265 · veracidad | `fila.apunte_id is not None` -> `fila.apunte_id` | **vivo** |
| 265 · comparacion | `is not None` -> `is None` | muerto (`r7_una_fila_sin_nada_es_visible`) |
| 265 · logico | `and` -> `or` | muerto (`r7_una_fila_sin_nada_es_visible`) |
| 265 · not | quita el `not` de `apunte_resuelto` | muerto (`r7_una_fila_sin_nada_es_visible`) |
| 283 · veracidad | `if obra is not None` -> `if obra` | **vivo** |
| 284 · comparacion | `== 1` -> `!= 1` | muerto (`r6_la_unica_obra_de_cargo[una]`) |

**Los 3 vivos no evaluados.**
- No son supervivientes de la campaña, porque la campaña no los midió.
- NO los he arreglado, como pidió el líder.
- Los tres cambian `is None` por la veracidad, así que solo difieren cuando el identificador vale **0**.
- En el dato el 0 nunca llega:
  - la cuenta y el apunte, porque el SQL los pasa por `NULLIF(a.cueide, 0)` y `NULLIF(a.apuide, 0)`;
  - la obra, porque sale de `maestro.centros_coste`, que no tiene obras con identificador 0.
- Son equivalentes para todo valor real, y ningún test pasa un 0.
- Un test con `cuenta_id=0`, `apunte_id=0` y la obra 0 los mataría. El oráculo hoy no fija qué hacer con un 0; si se quiere, va en otra feature.

**Reverificación EN SERIE de los 19 muertos.** Es la regla del nivel crítico mientras F-041 siga pendiente.
- Cada mutante se aplicó a mano, uno a uno, con `aplicar_mutante` sobre `etl_sigrid/domain/restriccion_personal.py`. La copia de seguridad estaba fuera del repositorio y se restauró tras cada mutante.
- La batería son los cuatro ficheros que importan el módulo:

  ```
  python -m pytest -q -x -p no:cacheprovider tests/test_f127_mayor_analitico.py tests/test_f135_dominio.py tests/test_f135_sql.py tests/test_f037_dominio.py
  ```

  Sin mutar: `409 passed, 4 skipped in 5.55s`.
- Resultado: **18 muertos y 1 vivo**, el 209 `slots=True` -> `slots=False`.
- A ese lo mata el barrido de F-006, que recorre todas las dataclasses del paquete sin importar el módulo por nombre. Con `tests/test_f006_dataclasses_inmutables.py` añadido (`618 passed, 7 skipped` sin mutar) cae en `test_f006_toda_dataclass_del_paquete_usa_slots[...FilaAnalitica]`: **muerto en serie**.
- Al terminar, `git diff --quiet -- etl_sigrid/` -> rc 0: no queda ningún mutante en disco.

| # | Línea · operador | Mutación | Primer test que cae (`-x`) | Muerto en serie |
|---|---|---|---|---|
| 1 | 180 · entero | `TIPO_CON_ASIENTO` 20 -> 21 | `r3_los_literales_de_con_tip` | sí |
| 2 | 181 · entero | `TIPO_CON_ASIENTO_ANALITICO` 32 -> 33 | `r3_los_literales_de_con_tip` | sí |
| 3 | 202 · comparacion | `tip == 20` -> `!=` | `r3_tipo_de_asiento[20-CONTABLE]` | sí |
| 4 | 204 · comparacion | `tip == 32` -> `!=` | `r3_tipo_de_asiento[32-ANALITICO]` | sí |
| 5 | 209 · booleano | `slots=True` -> `slots=False` | `test_f006_toda_dataclass_del_paquete_usa_slots[...FilaAnalitica]` | sí (con el barrido de F-006) |
| 6 | 233 · comparacion | `is not None` -> `is None` | `r7_c3_los_centros_de_cp_son_los_de_las_cp_actuales` | sí |
| 7 | 244 · booleano | `en_centro_contrapartida` por defecto `True` | `r7_c3_d7_no_alcanza_a_otras_cuentas[centro-cp-sin-abono]` | sí |
| 8 | 249 · comparacion | `cuenta_id is None` -> `is not None` | `r7_c3_la_cp_actual_del_recurso` | sí |
| 9 | 250 · booleano | `return False` -> `True` | `r7_c3_d9_sin_cuenta_no_es_cp_ni_en_el_centro_cp` | sí |
| 10 | 251 · comparacion | `in contrapartidas` -> `not in` | `r7_c3_la_cp_actual_del_recurso` | sí |
| 11 | 252 · booleano | `return True` -> `False` | `r7_c3_la_cp_actual_del_recurso` | sí |
| 12 | 253 · logico | `and` -> `or` | `r7_c3_d7_no_alcanza_a_otras_cuentas[centro-cp-sin-abono]` | sí |
| 13 | 263 · negacion | `if not fila.cuenta_es_contrapartida` | `r7_una_fila_sin_nada_es_visible` | sí |
| 14 | 265 · negacion | `if not (apunte sin resolver)` | `r7_una_fila_sin_nada_es_visible` | sí |
| 15 | 267 · negacion | `if not fila.apunte_restringido` | `r7_una_fila_sin_nada_es_visible` | sí |
| 16 | 269 · negacion | `if not fila.asiento_personal` | `r7_una_fila_sin_nada_es_visible` | sí |
| 17 | 276 · comparacion | `is not None` -> `is None` | `r7_una_fila_sin_nada_es_visible` | sí |
| 18 | 283 · comparacion | `obra is not None` -> `is None` | `r6_la_unica_obra_de_cargo[una]` | sí |
| 19 | 284 · entero | `== 1` -> `== 2` | `r6_la_unica_obra_de_cargo[una]` | sí |

Salvo el 5, todos caen en `tests/test_f127_mayor_analitico.py`.

**Conclusión frente a C4 bis.**
- En la campaña: 19 evaluados y 19 muertos en paralelo, y los 19 confirmados en serie. Cero supervivientes, cero timeouts y ningún falso muerto.
- Fuera de la campaña: 3 mutantes no evaluados siguen vivos. Son equivalentes para el dato real (solo difieren con el valor 0), no los he arreglado y están avisados al líder.

## Ficheros sin mutantes

Cada uno tiene líneas en alcance y el generador no ha sacado de ellas ni un mutante: la campaña no las ha juzgado. Declara por qué no hay nada que mutar (solo declaraciones, cadenas, imports) o qué test de la fase RED cubre el cambio. El reviewer hace la prueba de control (`generar_mutantes` sin exclusión de alcance) y ninguna declaración puede quedarse en `PENDIENTE` al cerrar la feature.

### `config/settings.py` — 10 líneas en alcance, 0 mutantes

#### Declaración (implementer, 2026-11-22)

> Por qué no hay nada que mutar: las 10 líneas son **solo comentarios**, el bloque del perfil restringido de D3
> («F-127 nació en `contabilidad`»). Ningún valor cambia: en `git diff -U0 90d1bfd b45f5ac -- config/settings.py`
> todas las líneas añadidas empiezan por `#`.
>
> Que no cambie nada lo fija `test_f127_r19_*`: ni `contabilidad` ni `contabilidad_restringida` están en las listas
> del restringido y del postventa, y la de excluidas sigue vacía. Su fase RED está en T7.

### `etl_sigrid/application/steps/build_contabilidad_step.py` — 50 líneas en alcance, 0 mutantes

#### Declaración (implementer, 2026-11-22)

> Por qué no hay nada que mutar: las 50 líneas son el **docstring** de los ficheros 08-12, **comentarios** y **cinco
> `_SubStep(...)`** de cuatro cadenas cada uno (nombre, fichero, esquema y tabla). No hay lógica, ni comparaciones,
> ni enteros ni booleanos, y el generador no muta cadenas.
>
> Lo cubren dos tests, con su fase RED en T6 (`assert [] == [('mayor_anal...ingidos_mes')]`, 3 failed):
> - `test_f127_r18_*`: los ocho sub-pasos de antes siguen intactos, los cinco nuevos van al final y en orden con su
>   esquema y su tabla, `depends_on` no cambia y el recuento da los trece.
> - `test_f056_r1`: la lista entera.
>
> Además, mover 10 delante de 08 pone en rojo F-127 y F-056 (RM7 del reviewer).

