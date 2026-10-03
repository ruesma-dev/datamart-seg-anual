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

## T6 · Documentación (R14-R15)

`stg.yaml` (nota 4 de cabecera, `partidas.capitulo_raiz_cod` y `partidas.categoria`),
`mart.yaml` (las seis `categoria`), `raw.yaml` (`obrparpar` y `auxobrtca`, con
`tcaide` = 0 y los tres oficios), `00_global.yaml` (`version` 40 → **41**, con su
nota de versión), `config/tables_sigrid.yaml` (comentario de `auxobrtca`) y
`README.md` §5.3.1 y §6.3. `pytest tests/ -k "f006"` → **2097 passed, 218
skipped en 169 s**; `grep -n -i "heuristica" config/diccionario/*.yaml` deja solo
menciones ajenas a la categoría (oficio en `compras`/`stg.v_*`, `es_hoja`, P3).

## T7 · Mutación (rigor crítico: 0 supervivientes) → `progress/mutacion_F-113.md`

- **Arnés** (`python -m harness.mutacion --feature F-113`, SHA `140758b`, 1 worker
  efectivo): 104 líneas de producción en alcance (`categoria_partida.py` 83,
  `arbol_partidas.py` 21) y **1 mutante generado, 1 muerto, 0 supervivientes**
  (`and` → `or` en la regla numérica), 1.349 s con una línea base de 465 s. Su
  juego de operadores no ve el resto (tuplas, `startswith`, `in`, retornos).
- La primera tentativa (SHA `9d7c13c`) abortó con **línea base en rojo**:
  `test_f123_r18_diccionario_version_40` fijaba `version == 40` y T6 la sube a
  41. Arreglado en `140758b` como hizo F-123 con el de F-120 (`e138fcb`):
  `>= 40, "F-113 la sube a 41"`. Ver «Desviaciones».
- **Manual** (script versionado `progress/mediciones/F-113_mutacion_sql.py`,
  SHA `8ecea16`, 1 worker, en serie, sin `-x`): **47 generados, 47 muertos, 0
  supervivientes** en 323 s — M01-M27 sobre `04_partidas.sql` (el CASE de la
  raíz, el de la recursiva y el INSERT) y D01-D20 sobre el dominio. Tabla con
  `fichero:línea`, texto exacto original → mutado y nº de fallos en el informe.
  M08 y M09 (orden de `WHEN` excluyentes) son **equivalentes**; los mata el test
  textual que exige el orden del dominio (falso positivo, no falso verde).

## Ficheros tocados

- Nuevos: `etl_sigrid/domain/categoria_partida.py` (regla, constantes),
  `tests/test_f113_categoria.py` (110 casos), `tests/test_f113_sql.py` (11),
  `progress/mediciones/F-113_mutacion_sql.py`, `progress/mutacion_F-113.md`.
- `sql/stg/04_partidas.sql`: `categoria` como 15ª columna de las dos ramas del
  recursivo, fuera `arbol_categorizado`, cabecera reescrita (R16).
- `domain/arbol_partidas.py`: `categoria` en `Partida` (último campo) y `_Paso`.
- `tests/test_f052_sql.py` (`_rama_recursiva()` corta en el `INSERT`; 14 → 15
  columnas) y `tests/test_f123_origenes.py` (`== 40` → `>= 40`).
- Documentación: `config/diccionario/{stg,mart,raw,00_global}.yaml` (v41),
  `config/tables_sigrid.yaml`, `README.md` §5.3.1 y §6.3.

## Decisiones de diseño

- Constante extra `CATEGORIA_DE_RAIZ_NUMERICA = "CD"` (el diseño no la listaba):
  así el test textual cruza también el `THEN 'CD'` de la regla numérica.
- Los tests del SQL **construyen** el `CASE` esperado desde las tuplas del
  dominio, en su orden: si una orilla cambia sin la otra, cae (R10).
- La categoría la decide el **propio nodo** si su código es exacto, también una
  hoja (no solo los capítulos): es lo que dice R4 y lo que midió la spec.

## Desviaciones respecto a la spec (justificadas)

1. **`tests/test_f052_sql.py`: además de `_rama_recursiva()`, el recuento 14 →
   15** de `test_f052_las_dos_ramas_...`. El diseño decía «nada más cambia en los
   tests de F-052», pero R7 añade una columna a las dos ramas y ese test cuenta
   las columnas: es consecuencia directa de R7, no una decisión nueva.
2. **`tests/test_f123_origenes.py`: `== 40` → `>= 40`.** R14 sube la `version`
   a 41 y el test de F-123 la fijaba exacta (rompía la línea base de la
   mutación). Mismo arreglo que F-123 hizo al de F-120 (`e138fcb`).
3. **Campaña manual también sobre el dominio** (D01-D20): el arnés genera un
   solo mutante en 104 líneas; con rigor crítico eso no es evidencia suficiente.

## Fuera del alcance

T13-T15 (D2 = contraste ligero). Las raíces OTRO (`PD`, `MP`, `LEV`, `GG`,
`MC`, posventas): no se tocan, y T5 mide 0 partidas de ellas que cambien
(hallazgo H1 de la spec, sin fichar). La dimensión CI del cierre de 0462, 0500
y 229 enseñará como grupo el segundo escalón (`CI`, `C.I.`): declarado en la
spec (§6), materia de F-111, que deberá remedir su dimensión CI.

## Verificaciones MANUAL pendientes (humano), en orden

- **T9** · merge a `main`, imagen con tag fechado desde `main`
  (`infra/70_build_image.ps1`) y job apuntando a ella (`infra/85_update_job.ps1
  -Tag rYYYYMMDD-HHmm`). Debe salir el tag nuevo en
  `az containerapp job show -g rg-datamart-seg-dev -n caj-datamart-seg-dev --query "properties.template.containers[0].image" -o tsv`.
- **T10** · dejar correr la nocturna (00:00 UTC); `python main.py status` con
  `run-all` SUCCESS de esa noche.
- **T11** · `python main.py publicar-diccionario` (debe publicar la **v41**),
  reiniciar el MCP y `python main.py check-diccionario` OK.
- **T12** · solo lectura, las consultas de `progress/spec_F-113.md` §4. Debe
  salir: por obra, la tabla de T5 (0229: 95 CI; 229: 9 CI; 0462: 10 CI; 0500:
  11 CI; 596085 y 998691: 0 CI; 1734235: 99 CI y 13 CP más los que ya lo eran);
  0 partidas CI con raíz `AVDA_FRANCIA`/`P1414_PCI`/`P1414_PISCIN`; recuento
  global ≈ CD 287.734 / CI 64.307 / CP 8.421 / OTRO 34.745 (salvo partidas
  nuevas de esa ingesta); 229 en `cierre.fact_cierre_mensual` 2011-01..03 con
  INDIRECTOS hasta +8.121 EUR y BENEFICIO lo mismo a la baja; 0462 en
  `mart.fact_seguimiento_categoria` con 25.002 EUR de Venta Real en CI (antes CD).

## T8 y Evidencias (medidas, 2026-10-03, HEAD `1757f33`)

`bash harness/init.sh` → **ENTORNO LISTO, código 0** (ruff: 236 avisos de deuda
previa, ninguno en los ficheros de F-113: `ruff check` sobre ellos, «All checks passed»).

| Evidencia | Valor real |
|---|---|
| Tests ejecutados | **6.406 passed, 221 skipped**, 0 fallos (suite completa con cobertura) |
| Cobertura de líneas cambiadas | **100,0 %** (29/29, umbral 80 %, nivel crítico) |
| Mutación, arnés | 1 generado, 1 muerto, **0 supervivientes** (SHA `140758b`) |
| Mutación, manual SQL + dominio | 47 generados, 47 muertos, **0 supervivientes** (SHA `8ecea16`, 1 worker) |
| Tiempo de la suite | **1.498,98 s** (24 min 59 s) |
| Tests propios de F-113 | 121 (`test_f113_categoria.py` 110, `test_f113_sql.py` 11), 0,7 s |
| Contraste T5 (Azure, solo lectura) | tabla de la spec exacta; 0 diferencias en otras columnas |
| Puerta de tamaño | impl dentro del tope de 220 (195 antes de esta sección) |
