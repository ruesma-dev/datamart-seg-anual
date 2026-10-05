<!-- progress/impl_F-038.md -->
# F-038 · Informe del implementer · Fase 2 (T11-T19)

Implementer, 2026-10-05. Rama `feature/F-038-comparativos` desde `main` `e9c5507`
(la Fase 1 ya mergeada y desplegada). Abierta por el humano el 2026-10-05; D3
(firmas aquí) y D4 (la base del objetivo) decididas el 2026-10-04. **El informe
de la Fase 1, íntegro, está en `progress/impl_F-038_fase1.md`** (movido para que
este quepa en su tope; sus decisiones siguen valiendo). Ni un SQL contra ninguna
base: los tests leen el texto del SQL. T20-T25 son MANUAL del humano (§5).

## 1 · Qué cambió

| Fichero | Qué |
|---|---|
| `etl_sigrid/domain/comparativos.py` | + `PATRON_DTO`, `TOLERANCIA_ABS`/`_REL`, `ORIGENES_ESTUDIOS`, `ORIGENES_ANTERIORES_ABC`; `parse_porcentaje_dto`, `casa_con_base`, `base_regla` |
| `sql/compras/00_setup.sql` | + `compras.fn_porcentaje_dto` al final (patrón del dominio, sin `EXCEPTION` ni `ELSE`) |
| `sql/compras/09_comparativos_detalle.sql` (nuevo) | `comparativo_lineas` (11 col.), temporal `_f038_obra_abc`, `comparativo_oferta_lineas` (18 col., la base de D4), `comparativo_objetivo` (7 col.), `comparativo_firmas` (10 col.) |
| `application/steps/build_compras_step.py` | `SUB_PASOS` + `comparativos_detalle` (`09`, cuenta `comparativo_oferta_lineas`); docstring |
| `config/diccionario/compras.yaml` | Cuatro fichas de tabla y la de `fn_porcentaje_dto`; relaciones de `comparativos` y `comparativo_ofertas` hacia el detalle; `aprobado_por` remite a las firmas |
| `config/diccionario/00_global.yaml` | `version` 43 con su changelog; `esquemas.compras`; `R-SIGRID-CON` punto 3 gana `confir.cod` y `dcopro.res` |
| `docs/ARCHITECTURE.md` | Un párrafo en «Semántica Sigrid»: `dto` texto, lector cruzado de `descompuestos`, D4 |
| `azure-apps/datamart_seg_anual.md` | Fase 1 desplegada y Fase 2 (commit `f3dca46` en ESE repositorio, sin push) |
| Tests | `test_f038_dominio.py` (+54 → 123), `test_f038_sql.py` (+32 → 68), `test_f038_diccionario.py` (+51 → 116); `test_f047_steps.py` (+1) |
| Tests de otras features (§2.6) | `test_f073_pipeline.py`, `test_f080_pipeline.py`, `test_f079_stg_consultable.py`, `test_f123_origenes.py` |
| Otros | `specs/F-006-mcp-azure/design_detalle.md` (enmienda: 199 objetos); `progress/current.md`; `progress/mutacion_F-038.md`; `progress/mutacion_sql_F-038_fase2.py` |

## 2 · Decisiones y desviaciones

1. **La tolerancia relativa se mide sobre el PRECIO de la oferta**:
   `|precio − base × (1 − %/100)| ≤ 0,011 + 0,002 × |precio|`. La spec da
   «0,011 € + 0,2 %» sin decir de qué; el precio es el dato que se intenta
   reproducir y la diferencia con medirla sobre el esperado es de segundo orden.
2. **Lo ANTERIOR a la ABC es Estudios en sus dos formas y `MASTER_PRE_ABC`**
   (`ORIGENES_ANTERIORES_ABC`). F-123 hizo de `MASTER_ESTUDIO` y `ESTUDIO` dos
   formas de lo mismo (Estudios, versión 0); dejar fuera `ESTUDIO` en una obra
   con ABC y sin master 0 sería tratar Estudios como posterior. Nunca entran
   `MASTER_PLANIF_JO` (salvo la propia ABC) ni `PLANIF_JO`; además
   `fase_num <= fase_abc`.
3. **El elemento de una versión es el de igual `dncpro_id` AUNQUE NO CASE**
   (R29 literal: «el de igual `dncpro_id` y, si no lo hay, el que cumpla…»).
   Solo sin él se busca por precio. Si la cifra de «casa con la ABC» sale muy
   por debajo de 11.409 en la verificación MANUAL, esta es la causa candidata
   (la medición de la spec pudo buscar por precio en toda la partida): se avisa,
   no se cambia sin decisión.
4. **`casa_base`**: cierto si la versión elegida casa; falso si la partida
   tiene descompuesto en alguna versión que la regla admite y ninguna casa;
   NULL si no lo tiene («sin descompuesto: NULL», R30). Si nada casa, la base
   publicada es el elemento de la versión de la REGLA (la ABC, o Estudios), y
   `precio_base`/`origen_base` quedan NULL si en ella no se identifica elemento.
   `base_regla` = `ABC`/`ESTUDIOS` por la obra, el mismo `CASE` que
   `base_regla()` del dominio (una obra sin obra_id cae en ESTUDIOS).
5. **La primera ABC por obra va a una tabla TEMPORAL** (`_f038_obra_abc`,
   `ON COMMIT DROP`, como `_lote` de `descompuestos/03`): la usan las líneas y
   el objetivo, y así `descompuestos.lineas` se recorre una vez para ese
   cálculo. `09` es UNA transacción: si falla, lo de anoche sigue publicado.
6. **Tests de otras features tocados, todos por consecuencia directa de la
   spec**: `test_f123_origenes.py::r1` decía «nadie fuera de
   `sql/descompuestos/` lo lee» (design §8 lo anticipa: «F-123 R1 lo daba por
   hecho»); ahora exige que el conjunto de lectores sea EXACTAMENTE
   `{09_comparativos_detalle.sql}`. Las listas de ficheros de `build_compras`
   (`f073`, `f080`), el inventario de funciones (`f079`) y la regla
   `R-SIGRID-CON`, que el test de F-006 deriva del SQL (09 lee `confir.cod` y
   `dcopro.res` sin pasar por `con`).
7. **Fichas sin `nulo_significa` donde el SQL proyecta texto crudo** de `raw`
   (`usuario`, `hora`, `descripcion`, `unidad_medida`, `descuento_texto`): la
   puerta de F-006 lo exige, porque Sigrid guarda cadena vacía, no NULL.
8. **`docs/ARCHITECTURE.md`** no estaba en las tareas de la Fase 2; se le
   añade un párrafo porque leer `descompuestos` desde `compras`, antes de que se
   construya, es un hecho de arquitectura que de otro modo solo diría el SQL.
9. **El paso NO declara `build_descompuestos` en `depends_on`**: lo dice la
   spec (lee la noche anterior). En una base recién creada sin `descompuestos`,
   el sub-paso `09` fallaría con su nombre, igual que fallaría `03_views.sql`
   sin `maestro.v_obra_fichas` (design §8); 00-08 quedan publicados.
10. Proceso: escribí tests con `python -` y heredocs, y dos veces se colaron
    caracteres (`\b` como retroceso, CRLF): corregidos antes de su commit y
    verificados con `git diff`. Lección: ficheros de test por Write/Edit.

## 3 · Fase RED (rigor `estandar`)

Requisitos centrales de design §7 de la Fase 2: R27, R29, R32 (y R25, R26, R30,
R31, R33 con su tarea). Trazas reales, recortadas a sus líneas de resultado.

**T11 · R27, R29** — `python -m pytest tests/test_f038_dominio.py -q --tb=line`
contra un esqueleto (constantes vacías, funciones en `raise NotImplementedError`):
```
E   AssertionError: assert '' == '^-?[0-9]+(,[0-9]+)?%$'
E   NotImplementedError
FAILED tests/test_f038_dominio.py::test_f038_r27_el_patron_del_dto_es_el_medido
FAILED tests/test_f038_dominio.py::test_f038_r27_parse_porcentaje_dto_de_los_textos_medidos[15%-esperado0]
FAILED tests/test_f038_dominio.py::test_f038_r27_lo_que_no_casa_es_none_y_no_cero[None]
FAILED tests/test_f038_dominio.py::test_f038_r29_las_tolerancias_de_la_medicion
FAILED tests/test_f038_dominio.py::test_f038_r29_casa_con_base_en_los_bordes_de_la_tolerancia[0-0.011-True]
FAILED tests/test_f038_dominio.py::test_f038_r29_base_regla - NotImplementedE...
54 failed, 69 passed in 0.22s
```
Verde: `123 passed in 0.21s`. Los 16 casos de `casa_con_base` son las tres
líneas de la 0696 y los seis ejemplos de `explore_F-038_ejemplos_objetivo.md`.

**T12 · R27 (SQL = dominio)** — `python -m pytest tests/test_f038_sql.py -q --tb=line -k dto`:
```
E   AssertionError: `compras.fn_porcentaje_dto` tiene que estar definida exactamente UNA vez en `compras/00_setup.sql`
FAILED tests/test_f038_sql.py::test_f038_r27_dto_la_funcion_usa_el_patron_del_dominio
FAILED tests/test_f038_sql.py::test_f038_r27_dto_sin_exception_ni_cero_ni_else
2 failed, 36 deselected in 0.20s
```

**T13 · R25, R26, R29, R30, R32** —
`python -m pytest tests/test_f038_sql.py -q --tb=line -k "lineas or base"`:
```
E   AssertionError: SQL no encontrado: ...\sql\compras\09_comparativos_detalle.sql
FAILED tests/test_f038_sql.py::test_f038_r25_lineas_columnas_en_su_orden - As...
FAILED tests/test_f038_sql.py::test_f038_r29_base_primera_abc_de_la_obra_por_es_primera_abc
FAILED tests/test_f038_sql.py::test_f038_r29_base_casa_con_la_tolerancia_del_dominio
FAILED tests/test_f038_sql.py::test_f038_r30_base_nunca_una_version_posterior_a_la_abc
FAILED tests/test_f038_sql.py::test_f038_r30_base_d4_la_abc_si_casa_si_no_la_anterior_mas_reciente
FAILED tests/test_f038_sql.py::test_f038_r32_lineas_el_detalle_no_cuenta_ofertantes_minima_ni_ahorro
18 failed, 1 passed, 37 deselected in 1.13s
```
Primer verde con el fichero: `2 failed, 17 passed` (el marcador de la
proyección final también abría la CTE `objetivo`; el helper pasó a `rindex`).
Que los vetos muerden con el fichero presente (nunca una posterior, el filtro
OBJETIVO, la tolerancia) lo prueba la campaña SQL (§4): M32-M35, M38, M31.

**T14 · R31** — `python -m pytest tests/test_f038_sql.py -q --tb=line -k objetivo`:
```
E   ValueError: substring not found
FAILED tests/test_f038_sql.py::test_f038_r31_objetivo_columnas_en_su_orden - ...
FAILED tests/test_f038_sql.py::test_f038_r31_objetivo_la_mas_reciente_por_fecha_y_luego_ide
FAILED tests/test_f038_sql.py::test_f038_r31_objetivo_importe_y_porcentaje_solo_si_es_unico
6 failed, 1 passed, 57 deselected in 0.71s
```

**T15 · R33** — `python -m pytest tests/test_f038_sql.py -q --tb=line -k firmas`:
```
E   AssertionError: assert 'ALTER TABLE compras.comparativo_firmas ADD PRIMARY KEY (firma_id)' in ' DROP TABLE ...
FAILED tests/test_f038_sql.py::test_f038_r33_firmas_columnas_en_su_orden - Va...
FAILED tests/test_f038_sql.py::test_f038_r33_firmas_grano_una_fila_por_confir_de_un_comparativo
4 failed, 1 passed, 63 deselected in 0.66s
```

**T16** — `python -m pytest tests/test_f047_steps.py tests/test_f073_pipeline.py tests/test_f080_pipeline.py -q --tb=line`:
`FAILED ...test_f047_r4_encadena_sus_sql_en_orden[build_compras]`,
`FAILED ...test_f038_r26_build_compras_cuenta_las_lineas_de_oferta_al_final`, `6 failed, 40 passed`.

**T17 · R28, R31, R34, R35** — `python -m pytest tests/test_f038_diccionario.py -q --tb=line`:
`FAILED ...test_f038_r24_la_version_sube`, `FAILED ...test_f038_r35_ficha_con_grano_clave_y_todas_sus_columnas[compras.comparativo_lineas-...]`,
`FAILED ...test_f038_r34_la_ficha_de_firmas_lo_dice[5.375]`, `52 failed, 64 passed in 6.43s`.

## 4 · Verificaciones

- Subconjuntos por tarea, verdes tras cada commit (§3).
- Suite entera sin cobertura antes de mutar (`python -m pytest tests -q -p no:cacheprovider`):
  primero `3 failed, 6783 passed` (las tres consecuencias de §2.6:
  `test_f123_origenes` r1, `R-SIGRID-CON` y los recuentos de `current.md`),
  arregladas en `656e202` y `d2d1d34`; después, verde (ver «Evidencias»).
- Campaña del arnés: dos intentos ABORTADOS por la propia herramienta antes de
  evaluar nada («LÍNEA BASE SIN TERMINAR»: la suite limpia pasó de 600 s con 4 y
  con 2 workers; la máquina estaba cargada por campañas de otros proyectos). La
  válida es la tercera, en serie (`--workers 1`), sobre `d2d1d34`.
- NO verificado (no se puede sin base): que `09` corra en Postgres, su tiempo y
  sus cifras. Riesgos a mirar en la MANUAL: tipos de `raw` (`dcopro.dto` texto,
  `confir.hor`), el coste de leer `descompuestos.lineas` (~4,5 M filas; la
  temporal y `candidatas` lo recorren), y la cifra de D4 (§2.3).

## 5 · MANUAL del humano, en orden, tras el APROBADO del reviewer

Copiadas con su comando exacto y lo que debe salir en `progress/current.md`
(sección F-038, «Implementer · Fase 2»): **T20** merge e imagen; **T21** nocturna
o `build-compras` + `apply-grants` + `publicar-diccionario` a mano, con
`timings` (+2-3 min); **T22** las cuatro puertas `check-*` (R36); **cifras de
D4** (recuentos de las cuatro tablas y el reparto de `casa_base`: ≈ 24.263 de
83.329 casan); **T25** la 0696 (comparativo 2754136, oferta 2754139); y
reiniciar el MCP tras publicar la v43.

## 6 · Fuera de alcance / lo que falta

- Vistas por actividad y proveedor (F-067); circuito entre familias, `deffir`
  y `dbo.log` (F-085); `comlinpar` (0 filas); ingesta nueva; ampliar D4 a la
  versión vigente a la fecha del comparativo (Negocio).
- Para cerrar: review de la Fase 2, y después las MANUAL del humano.

## Evidencias

| Evidencia | Valor real |
|---|---|
| Tests ejecutados (`init.sh`) | **6786 passed, 227 skipped**, 0 failed (de ellos 307 de F-038: 123 + 68 + 116) |
| Cobertura de líneas cambiadas | `PUERTA COBERTURA: 100.0% de 14 líneas cambiadas cubiertas (14/14, umbral 80%, nivel estandar; diff desde e9c5507390, merge-base con main)` |
| Mutación (`harness.mutacion`, **1 worker**, HEAD `d2d1d34d94a1d344c0015033b3fa5dd023fbc9a2`) | Alcance 84 líneas (dominio 65, step 19). **13 generados, 13 muertos, 0 supervivientes**, 0 timeouts, 0 sin veredicto; 3665,0 s; línea base 419,4 s, media 281,9 s/mutante. Ningún superviviente que analizar. Detalle: `progress/mutacion_F-038.md` |
| Mutación SQL manual (1 worker, `d2d1d34d94a1d344c0015033b3fa5dd023fbc9a2`) | **25 mutantes (M25-M49), 25 muertos**; tabla `fichero:línea`, original -> mutado y nº de fallos en el anexo de `progress/mutacion_F-038.md`; script `progress/mutacion_sql_F-038_fase2.py`. Línea base 0 fallos antes y después (1073 passed) |
| Tiempo de la suite | 2434,06 s con cobertura dentro de `init.sh` (0:40:34, máquina cargada); 1001,17 s sin cobertura |
| `bash harness/init.sh` | **ENTORNO LISTO**, exit 0, sobre HEAD `5bcb2e8` (todas OK; `PUERTA TAMAÑO`: requirements 144/150, design 249/250, impl 180/220). El commit posterior solo rellena esta tabla y marca T19 |
