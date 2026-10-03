<!-- progress/impl_F-113.md -->
# F-113 · Informe del implementer · la categoría sale del capítulo

Rama `feature/F-113-categoria-capitulo-por-prefijo`. Spec aprobada el
2026-10-03: **D1 = A** (raíz por prefijo + intermedio de código exacto, manda el
más cercano), **D2 = contraste ligero** (T13-T15 fuera). Rigor `critico`.

## Fase RED

### T1 · dominio (R1-R6, R9), antes de que exista `categoria_partida.py`

```
$ python -m pytest tests/test_f113_categoria.py -q -p no:cacheprovider
________________ ERROR collecting tests/test_f113_categoria.py ________________
ImportError while importing test module 'C:\Users\pgris\PycharmProjects\datamart-seg-anual\tests\test_f113_categoria.py'.
tests\test_f113_categoria.py:25: in <module>
    from etl_sigrid.domain.categoria_partida import (
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.categoria_partida'
ERROR tests/test_f113_categoria.py
1 error in 0.44s
```

### T2 · R9 (el árbol publica `categoria`), con el módulo ya creado y `arbol_partidas.py` sin tocar

```
$ python -m pytest tests/test_f113_categoria.py -q -p no:cacheprovider
FAILED tests/test_f113_categoria.py::test_f113_r3_r4_r5_r9_construir_arbol_publica_la_categoria[codigos0-esperadas0]
...(20 parametrizaciones de ese test)...
FAILED tests/test_f113_categoria.py::test_f113_r6_el_colapsado_pasa_la_categoria_sin_cambiarla
FAILED tests/test_f113_categoria.py::test_f113_r4_r6_intermedio_exacto_tras_un_colapsado
FAILED tests/test_f113_categoria.py::test_f113_r4_hermanos_no_se_contagian - ...
23 failed, 87 passed in 0.66s
$ python -m pytest tests/test_f113_categoria.py -q -p no:cacheprovider -k hermanos
E       AttributeError: 'Partida' object has no attribute 'categoria'
1 failed, 109 deselected in 0.25s
```

Tras T2: `pytest tests/test_f113_categoria.py tests/test_f052_arbol.py` → **135 passed in 0,42 s**.

### T3 · R7, R10, R11, R16 (texto del SQL) contra el `04_partidas.sql` de `main`

```
$ python -m pytest tests/test_f113_sql.py -q -p no:cacheprovider --tb=line
E   AssertionError: el INSERT tiene que leer del CTE recursivo, sin CTE intermedio
    ...'CASE WHEN tipdes_raw = 0 THEN TRUE ELSE FALSE END AS activa\nFROM arbol_categorizado\n\nWHERE publicable;\n')
E   AssertionError: assert 'prefijo' in 'etl_sigrid/infrastructure/postgres/sql/stg/04_partidas.sql materializa stg.partidas ...'
FAILED tests/test_f113_sql.py::test_f113_r11_ningun_like_con_comodin_delante
FAILED tests/test_f113_sql.py::test_f113_r10_la_raiz_prueba_cada_prefijo_con_su_categoria
FAILED tests/test_f113_sql.py::test_f113_r10_la_raiz_numerica_con_las_excepciones_del_dominio
FAILED tests/test_f113_sql.py::test_f113_r10_la_raiz_completa_y_en_el_orden_del_dominio
FAILED tests/test_f113_sql.py::test_f113_r10_el_intermedio_compara_el_codigo_limpio_con_la_lista_exacta
FAILED tests/test_f113_sql.py::test_f113_r10_un_replace_por_cada_caracter_ignorado
FAILED tests/test_f113_sql.py::test_f113_r5_el_intermedio_no_usa_prefijo - As...
FAILED tests/test_f113_sql.py::test_f113_r7_categoria_en_las_dos_ramas_y_en_la_misma_posicion
FAILED tests/test_f113_sql.py::test_f113_r7_el_insert_toma_la_categoria_del_recursivo
FAILED tests/test_f113_sql.py::test_f113_r16_la_cabecera_explica_la_regla_y_el_porque
10 failed, 1 passed in 1.32s
```

El que pasa es `test_f113_r7_el_tope_y_el_corta_ciclos_no_cambian` (guarda de no
regresión de F-052, verde antes y después a propósito).

Tras T4: `pytest tests/test_f113_sql.py tests/test_f052_sql.py tests/test_f006_stg_trampas.py tests/test_f113_categoria.py tests/test_f052_arbol.py` → **226 passed in 6,65 s**.

## T5 · Contraste de la propuesta en SOLO LECTURA contra Azure (R12)

2026-10-03 11:30 UTC, tras la nocturna. Script en el scratchpad (`f113_t5_contraste.py`,
fuera del repo): recorta de `04_partidas.sql` **tal cual** el texto entre
`WITH RECURSIVE` y el `INSERT` (sin `TRUNCATE` ni `INSERT`; lo comprueba con un
`assert`), lo cierra con `SELECT … FROM arbol_partidas WHERE publicable` y lo
cruza con `FULL JOIN stg.partidas` por `partida_id`. Conexión con
`conn.read_only = True`; el script exige `SHOW transaction_read_only = on`
antes de consultar (salió `on`) y termina con `ROLLBACK`. **11,5 s** de consulta.

| Comprobación | Resultado |
|---|---|
| Filas propuesta / `stg.partidas` | 395.207 / 395.207; 0 solo en una de las dos |
| Otras columnas distintas (`obra_id`, `codigo_partida`, `capitulo_padre_id`, `descripcion_corta`, `unidad_medida`, `capitulo_raiz_id`, `capitulo_raiz_cod`, `ruta_capitulos`, `nivel`, `activa`) | **0 en las diez** |
| Cambian con A / con B (raíz de la propia propuesta) | **490 partidas, 7 obras / 253, 2** |
| Raíces hoy en OTRO que cambian | solo `99` (0229) y `TN` (229), las de la spec |
| Partidas con raíz `PD…`, `MP…`, `LEV…`, `GG…`, `MC…`, `POS…` que cambian | **0** (límite del humano respetado) |

| Obra | Seg | Capítulo que decide | Partidas | Hoy → B | Hoy → A |
|---|---|---|---|---|---|
| 596085 (sin código) | no | raíz `AVDA_FRANCIA` | 221 | CI → OTRO | CI → OTRO |
| 998691 (sin código) | no | raíces `P1414_PCI`, `P1414_PISCIN` | 32 | CI → OTRO | CI → OTRO |
| 0229 (537441) | sí | `99 > CI` | 95 | = | OTRO → CI |
| 229 (546432) | sí | `TN > CI` | 9 | = | OTRO → CI |
| 0462 (950302) | sí | `CD > C.I.` | 10 | = | CD → CI |
| 0500 (1025342) | sí | `CD > CI` | 11 | = | CD → CI |
| 1734235 (sin código) | no | `CD > CI`, `CD > CP` | 99 + 13 | = | CD → CI / CP |

**Igual a la tabla de `progress/spec_F-113.md` §2, celda a celda.** Previsión de
`SELECT categoria, count(*) FROM stg.partidas GROUP BY 1` para T12:

| Categoría | Hoy | Tras F-113 (A) |
|---|---|---|
| CD | 287.867 | **287.734** |
| CI | 64.336 | **64.307** |
| CP | 8.408 | **8.421** |
| OTRO | 34.596 | **34.745** |

(Cuadra: CI −253 +224, OTRO +253 −104, CD −133, CP +13.) Si la ingesta de la
noche del despliegue trae partidas nuevas, los totales se moverán con ellas; las
siete obras de la tabla, no.
