<!-- progress/impl_F-150.md -->
# F-150 · Informe del implementer · la receta de la caja (fase 1)

Fecha: 2026-10-28. Rama `feature/F-150-receta-caja`. **Estado: T1-T14 y T16 hechas**; T15 es
MANUAL (humano). T11 paró por R29 (el hueco de H26, 15,60 M EUR, fuera de 15,26-15,55) y el
humano aprobó la opción (b): R29 relativo a los datos del día (§4). `bash harness/init.sh` en
verde con todo dentro (Evidencias).

El informe de la PARADA del 2026-10-27 (las mediciones que la spec cita como «`impl_F-150.md`
§1-§3»: formas reales de `coestr`, lo que casaba con §8, lo medido en Sigrid para T1) se ha
movido tal cual a `progress/impl_F-150_parada_T11.md`.

## 1. Qué cambió (por tarea, un commit cada una)

| Tarea | Commit | Qué |
|---|---|---|
| T1 | `5a3b1d2` | `TableSpec.include_columns` (lista blanca) e `IngestRawStep._columnas_a_traer`: solo esas columnas, en el orden de Sigrid; con `exclude_columns` a la vez o una inexistente, falla antes de crear nada |
| T2 | `d463341` | `iva` (entera) y `dvf` (9 de 151 columnas) en `config/tables_sigrid.yaml`; fichas en `raw.yaml`; censo 78 -> 80 en los tests que lo fijan, `ARCHITECTURE.md`, `00_global.yaml` y la enmienda del inventario de F-006 |
| T3 | `9ef99af` | Unidad `PERFIL_MESES` (`MAX_MESES_PERFIL` 120): un error por cada fallo, suma exacta en `Decimal` |
| T4 | `1aab362` | `PASOS_RECETA` (siete pasos), `paso_receta` obligatorio y último campo de `Hipotesis` |
| T5 | `2d9a426` | `leer_coeficientes_contrato` (líneas, por código, `CLASE_POR_CODIGO`), `factor_coeficientes` (cascada de `COEF_DESADJ`), `porcentaje_iva`, `coeficiente_venta`, `importe_con_coeficiente`, `importe_por_porcentaje`, `hueco_facturacion`, `coeficiente_medio`, `FUENTE_MEDIA_OBRA`, `MOTIVO_H12_FICHA` |
| T6 | `1d8c876` | `config/hipotesis_caja.yaml` a 27 (H24-H27; H03/H08 a perfil; H14 `MENSUAL`; H20 `FIN_MES_ALBARAN`; textos de §6), `paso_receta` en lector y carga; `unidad` a `VARCHAR(20)` |
| T7 | `abfb787` | `00_setup.sql`: `fn_coeficientes`, `fn_coeficientes_reconocidos` y las columnas nuevas por `ALTER ... ADD COLUMN IF NOT EXISTS`; fichas de todas |
| T8 | `6da3271` | `06`: `coestr` leído una vez (`CROSS JOIN LATERAL`), clases, factor e IVA del contrato (`raw.iva`) |
| T9 | `1812dbe` | `07`: `_dev_coef` (master 9/11 de V), `_dev_contrato`, columnas de la partida, guarda D6, reparto con coeficientes, IVA/retención de la obra-mes, `_dev_hueco` neto por obra con `MEDIA_OBRA` |
| T10 | `6ba7839` | `08`: H12 SIGRID desde la ficha de la obra con `MOTIVO_H12_FICHA`; `COMMENT` a 27 |
| T13 | `886c9da` | `CONVENTIONS.md` (excepción acotada D1), `ARCHITECTURE.md` (la receta), `CLAUDE.md` (mapa, 27); `azure-apps` commit local `044beef` |
| — | `e85a3d8` | Los cuatro huecos que destapó la línea base de la campaña (§2, D-5) |
| T14 | `db6553a` | Campaña de mutación (`progress/mutacion_F-150.md`) y el test que cierra su superviviente |

Ficheros de producción: `etl_sigrid/domain/entities.py`, `domain/proyeccion_caja.py`,
`application/steps/ingest_raw_step.py`, `infrastructure/config/hipotesis_caja_yaml.py`,
`infrastructure/postgres/hipotesis_caja_sql.py`, `sql/tesoreria/00`, `06`, `07`, `08`. Config:
`tables_sigrid.yaml`, `hipotesis_caja.yaml`, `diccionario/{raw,tesoreria,00_global}.yaml`. Tests
nuevos: `tests/test_f150_{ingesta,perfil,receta,contrato,coeficiente,hueco,sql,diccionario}.py`.

## 2. Decisiones y desviaciones respecto a la spec

- **D-1** `_errores_de_perfil` devuelve una LISTA (el design decía `_error_de_perfil`): R25 pide un
  error por cada fallo, y con una cadena solo saldría el primero.
- **D-2** `CODIGOS_SIGRID` pasa a `("H09", "H10", "H11", "H12")` (el design solo nombra
  `MOTIVO_H12_FICHA`): la constante ya era «los códigos que `08` resuelve como SIGRID» y el test
  de F-140 la cruza con el SQL; tener H12 fuera habría dejado el cruce mintiendo.
- **D-3** `test_f140_sql` r6 («`08` no hace aritmética») tolera UNA cuenta, la del cambio de unidad
  del IVA de la ficha (`ROUND((i.iva * 100)::NUMERIC, 4)`, que pide §5.6): no aplica ninguna
  hipótesis. `test_f140_sql` r13: `07` lee también `stg.presupuesto` (R10).
- **D-4** T13 se hizo antes que T12: T12 va «tras T11 en verde» y T11 estuvo bloqueada (Azure)
  y luego en PARADA; T13 no depende de cifras de T11.
- **D-6** T12: la pregunta nueva va primera en `hipotesis_caja` y la del plazo de cobro pasa a
  tercera (F-147: se reordena, no se borra); `test_f140` r22 pasa de `== 2` a `>= 2`. Presupuesto
  F-147: **30.864**. El guardián de cifras de F-006 (`_cifras`) ignora los códigos `H22`. Si T11 obliga a cambiar algo, se revisan los textos de T13.
- **D-5** La línea base de la campaña de mutación salió ROJA y destapó cuatro fallos reales que
  las suites parciales no veían (arreglados en `e85a3d8`): `coeficientes_texto` declaraba
  `nulo_significa` pero `raw` trae cadena vacía (ahora `NULLIF(o.coestr, '')`; el guardián de
  F-006); `dvf` no cuelga de `con` en ningún SQL y `R-SIGRID-CON` no lo decía (punto 4); las dos
  funciones nuevas faltaban en el inventario de `test_f079`; y `current.md` no tenía los recuentos
  de hoy del diccionario (252 objetos, 2.178 columnas, 122 de consumo).
- Literales del dominio = SQL (patrón F-135): los tests de `test_f150_sql.py` comparan el texto.

## 3. Verificación semántica del SQL (Postgres 16 desechable, datos sintéticos)

Contenedor `postgres:16` local en `127.0.0.1:55432` (precedente F-135), destruido al terminar; ni
Azure ni Sigrid. Script `sandbox_f150.py` (scratchpad): ejecuta `00` (dos veces: idempotente),
`06`, `07` y `08` como el paso (cada fichero en una transacción) y compara con el dominio.
Resultado: **66 comprobaciones OK, 0 fallos**. Cubre: las clases y el factor de cada forma de
`coestr` (con `\r\n`, base `TOTAL EJECUCION CONTRATA`, `COEF_DESADJ` en cascada, `RETN`, vacío,
código desconocido); IVA del contrato (0 es 0); coeficiente y fuente por partida (contrato >
master 9 > master 11; contrato de otra obra NO se casa); pendiente con coeficientes al céntimo
(HALF_UP); sumas de la obra-mes, IVA/retención y cociente; hueco por obra (obra 1: real 2.323,07,
parte a media 285,70, facturado 800, hueco 1.523,07, IVA 196,61, base sin IVA 586,83; obra 2:
facturado por delante 451,87); `08` con H12 SIGRID 21 y su motivo, MANUAL manda, 27 códigos por
obra; y la guarda D6 salta con una partida de venta con pendiente y sin coeficiente.

## 4. T11 (R29): PARADA por 0,05 M EUR en el hueco

Hasta las 09:46 UTC Azure no se alcanzaba (la IP pública del puesto no estaba entre las 19 reglas
del firewall); el líder lo confirmó alcanzable y T11 se corrió tras el `init.sh`, a las 10:43 UTC. Todo SOLO LECTURA: Azure con
`filas_solo_lectura` (nocturna del 28-10: `mes_ultimo_cierre` máximo 2026-10-01), `iva` y `dvf`
de Sigrid con `truncated` = False, y el dominio de T5. Scripts (scratchpad): `t11_r29.py` y
`t11_r29b.py`; salidas `t11_r29.out` y `t11_r29b.out`.

| Medida (21 obras) | Hoy | Spec | ¿Casa? |
|---|---|---|---|
| Contratos con `coestr` no vacío y NO reconocido | **0** (36 en el resto de obras) | 0 | sí |
| Partidas con contrato de OTRA obra | **0** | 0 | sí |
| Contrato ≠ master 11 en > 0,005, pendiente > 0 | **5** (0696 ×3, 0724, 0676-B) | ≤ 6 (medidas 5) | sí |
| Partida de venta con pendiente y sin coeficiente (guarda D6) | 0 | 0 | sí |
| Partidas VENTA / pendiente / con coeficientes | 19.005 / 132,14 / 142,94 M EUR | ~18.997 / ~132,4 / ~143,3 (R30) | sí (−0,2 %: otra nocturna) |
| Fuentes: CONTRATO / MASTER_CERT / MASTER_VENTA / SIN | 54,44 / 76,94 / 0,76 / 0 M EUR (SIN: 860 partidas con pendiente 0) | — | — |
| IVA y retención del contrato | ≥ 96 % en 19 obras (0711, 96,0 %); 0608 y 0715, 0 % | ídem | sí |
| **Σ (real × coef − facturado), con `MEDIA_OBRA`** | **15,60 M EUR** | **15,26-15,55** | **NO (+0,05)** |
| Suelo de R29 hoy (sin coeficiente a factor 1) | 15,50 (real sin coeficiente 0,97) | 15,26 el 27-10 | — |
| `venta_pendiente_facturar` (suelo 0 por obra) / facturado por delante | 15,69 / 0,09 (solo 0711) | — | — |
| Albaranes sin facturar / de más de 6 meses | 56,83 / 22,91 M EUR | 56,9 / 22,9 | sí |

Por obra (M EUR, hueco): 0676-B 4,85 · 0696 3,13 · 0702 1,49 · 0678 1,43 · 0686 1,30 · 0713 0,83
· 0710 0,79 · 0694 0,51 · 0693 0,46 · 0697 0,34 · 0707 0,29 · resto ≤ 0,13; 0711, 0,09 por delante.

**DECISIÓN DEL HUMANO (2026-10-28, opción b)**: el método no se apartaba, se movió el dato (del
27-10 al 28-10 el suelo a factor 1 sube 0,24 M EUR). R29 deja las cifras fijas y pasa a ser
relativo al día con la misma regla: suelo = el hueco con la venta real sin coeficiente a factor 1;
techo = suelo + 0,26 × esa venta. Con la nocturna del 28-10, **15,50-15,75 y el hueco 15,60:
pasa**. Cambiado en `requirements.md` (R29), `tasks.md` (T11) y la `acceptance` de
`features.json` (commit `0be8eab`).

## 5. Fase RED (comando exacto y salida real del fallo)

**R17 (T1) · `.venv/Scripts/python -m pytest tests/test_f150_ingesta.py -k r17 -q`**
```
E       AttributeError: 'TableSpec' object has no attribute 'include_columns'. Did you mean: 'exclude_columns'?
E       TypeError: TableSpec.__init__() got an unexpected keyword argument 'include_columns'
E       TypeError: TableSpec.__init__() got an unexpected keyword argument 'include_columns'
E       TypeError: TableSpec.__init__() got an unexpected keyword argument 'include_columns'
E       AttributeError: 'TableSpec' object has no attribute 'include_columns'. Did you mean: 'exclude_columns'?
FAILED tests/test_f150_ingesta.py::test_f150_r17_table_spec_tiene_include_columns_vacio_por_defecto
FAILED tests/test_f150_ingesta.py::test_f150_r17_la_ingesta_trae_solo_las_incluidas_en_el_orden_de_sigrid
FAILED tests/test_f150_ingesta.py::test_f150_r17_incluir_y_excluir_a_la_vez_falla_antes_de_crear_nada
```

**R25 (T3) · `python -m pytest -q -p no:warnings tests/test_f150_perfil.py -k r25`**
```
E       AssertionError: assert 'PERFIL_MESES' in ('DIAS', 'MESES', 'PORCENTAJE', 'BOOLEANO', 'OPCION', 'MAPA_DIAS')
E         Left contains one more item: "H03: unidad 'PERFIL_MESES' fuera de ['DIAS', 'MESES', 'PORCENTAJE', 'BOOLEANO', 'OPCION', 'MAPA_DIAS']"
FAILED tests/test_f150_perfil.py::test_f150_r25_un_error_por_cada_fallo - Ass...
FAILED tests/test_f150_perfil.py::test_f150_r25_la_suma_es_exacta_en_decimal_no_en_float
63 failed in 1.25s
```

**R1 (T4) · `python -m pytest -q -p no:warnings tests/test_f150_receta.py -k r1`**
```
E       AssertionError: assert () == ('DEVENGO', '...', 'IVA', ...)
E         Left contains one more item: 'H01: campo desconocido paso_receta'
E       assert [] == ['H01: falta ... paso_receta']
E         Right contains one more item: 'H01: falta el campo paso_receta'
14 failed, 1 skipped in 0.50s   (el skip: el parametrize sobre PASOS_RECETA vacío)
```

**R7, R9, R14, R22 (T5) · `python -m pytest -q -p no:warnings tests/test_f150_contrato.py tests/test_f150_coeficiente.py tests/test_f150_hueco.py -k "r7 or r9 or r14 or r22"`**
(con los nombres del dominio declarados como esbozos que lanzan `NotImplementedError` o valen vacío)
```
E       AssertionError: assert '' == '\r?\n'
E       AssertionError: assert () == ('CONTRATO', ...VENTA', 'SIN')
E       AssertionError: assert '' == 'MEDIA_OBRA'
E   NotImplementedError        (x57: leer_coeficientes_contrato, factor_coeficientes, coeficiente_venta, hueco_facturacion, coeficiente_medio...)
60 failed, 9 deselected in 3.09s
```

**R12, R14, R20, R23 (T9, SQL de `07`) · `python -m pytest -q -p no:warnings tests/test_f150_sql.py -k "r10 or r11 or r12 or r13 or r14 or r19 or r20 or r23 or r9"`**
```
E       ValueError: substring not found          (r12: la guarda de D6 no existe)
E       assert 'ROUND(d.pendiente_con_coeficientes * pr.importe_mes / d.total_perfil, 2) AS parte_con_coef' in " DO $$ BEGIN IF to_regclass('mart.fact_seguimiento_mensual') ...
E           assert "SUM(r.importe_con_coef * r.iva_porcentaje) FILTER (WHERE r.fuente_iva = 'CONTRATO') AS iva_bruto" in " DO $$ BEGIN ...
E       assert 'GREATEST(0, h.venta_real_origen_con_coeficientes - h.facturado_origen) AS venta_pendiente_facturar' in " DO $$ BEGIN ...
19 failed, 44 passed, 21 deselected in 0.67s
```

**R21 (T10, `08`) · `python -m pytest tests/test_f150_sql.py -k r21 -q -p no:cacheprovider`**
```
>       assert dom.CODIGOS_SIGRID == ("H09", "H10", "H11", "H12")
E       AssertionError: assert ('H09', 'H10', 'H11') == ('H09', 'H10', 'H11', 'H12')
E         
E         Right contains one more item: 'H12'
E         Use -v to get more diff
>       rama = texto[texto.index("'H12'::VARCHAR(3) AS codigo"):]
E       ValueError: substring not found
>       assert "las 27 hipotesis" in comment
E       assert 'las 27 hipotesis' in "COMMENT ON TABLE tesoreria.hipotesis_caja_obra IS\n'F-140. El valor de las 23 hipotesis de caja (catalogo tesoreria.h... DEFECTO. Nada se aplica: es el valor que quien consulta debe declarar (R-CAJA-HIPOTESIS). Clave: obra_id, codigo.';\n"
FAILED tests/test_f150_sql.py::test_f150_r21_h12_es_codigo_sigrid - Assertion...
FAILED tests/test_f150_sql.py::test_f150_r21_h12_sale_de_la_ficha_de_la_obra_por_cien
FAILED tests/test_f150_sql.py::test_f150_r21_el_comment_dice_27_y_h12 - asser...
3 failed, 1 passed, 84 deselected in 0.39s
```

**R2-R5, R15, R32 (T12, diccionario) · `python -m pytest tests/test_f150_diccionario.py -q -p no:cacheprovider`**
```
E       AssertionError: assert 'LA RECETA: DE DEVENGO A CAJA, EN ESTE ORDEN' in '**No disponible para el perfil restringido** ...
E       AssertionError: assert {'tesoreria.d...ente_partida'} <= {'cierre.fact....presupuesto'}
E       AssertionError: assert 'las 27 hipotesis (H01-H27)' in '**No disponible para el perfil restringido** ...
7 failed, 3 passed in 1.05s   (r2, r3 x2, r4, r5, r15, r32; los 3 de docs de T13 ya pasaban)
```

Tras cada código, las mismas órdenes en verde (salida en los commits de cada tarea).

## 6. Verificaciones MANUAL pendientes (T15, del humano)

1. Imagen nueva y tag del job (comprobar que el job corre ESA imagen).
2. `ingest` de `iva` y `dvf` antes del primer `build-tesoreria`.
3. `build-tesoreria`: duración y contraste R30 (18.997 partidas, ~132,4 y ~143,3 M EUR, fuentes,
   IVA y retención ≥ 96 % del pendiente en 19 obras, 0 fallos de guardas).
4. `publicar-diccionario` (v63) con la imagen ya en el job; `check-diccionario`,
   `check-declarados`, `check-unicidad`; reiniciar `mcp-bbdd`.
5. R31 en conversación nueva: una obra a 1,19 y otra mixta (siete pasos, coeficientes, IVA y
   retención del contrato, hueco de H26, albaranes de H20/H27, avisos de R4, 27 hipótesis).

## 7. Qué falta para cerrar

El review (reviewer contra `CHECKPOINTS.md`) y T15 (MANUAL, humano). Nada de despliegue hecho.

## Evidencias

| Evidencia | Valor real |
|---|---|
| `bash harness/init.sh` (sobre `db6553a`, 2026-10-28) | **verde**, código 0, «ENTORNO LISTO»: 9.638 passed, 266 skipped, 2.504 warnings |
| Tiempo de la suite | 4.013,93 s (1:06:53), con medición de cobertura |
| Tests de F-150 (`tests/test_f150_*.py`) | 274 passed en 5,23 s; con los de F-140 y `test_f066`: 1.015 passed |
| Cobertura de las líneas cambiadas | `PUERTA COBERTURA`: **100,0 %** (143/143, umbral 80 %, `estandar`) |
| Tamaño | `PUERTA TAMAÑO`: requirements 148/150, design 249/250, impl 174/220 (antes de §4 y esta tabla) |
| Mutación (`python -m harness.mutacion --feature F-150 --workers 2 --timeout 2400`) | 95 generados, 20 evaluados (muestreo `estandar`, semilla 20260820): 17 muertos, 1 superviviente, 2 timeouts; tras reevaluar en serie, **19 muertos y 1 superviviente, cerrado con un test** (`progress/mutacion_F-150.md`, 15.325,8 s) |
| Verificación semántica del SQL | 66 comprobaciones en Postgres 16 desechable, 0 fallos (§3) |
| `ruff` | sin avisos nuevos en los ficheros de F-150 (el único, `UP042` de `StepStatus`, es previo) |

Dos lanzamientos previos de la campaña no cuentan: uno abortó porque la línea base con 4 workers
no cabía en 600 s; el siguiente, porque la línea base salió ROJA, y eso destapó los cuatro huecos
de D-5. El SQL no entra en la campaña (solo muta Python); lo cubren los tests de texto de
`test_f150_sql.py` y la verificación del §3.
