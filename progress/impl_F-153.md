<!-- progress/impl_F-153.md -->
# F-153 · El estado de cada albarán (con proformas y notas)

Implementer, 2026-11-02. Rama `feature/F-153-estado-albaranes`, rigor `estandar`. D1=A, D2=A, D3=A, D4=A.
Commits `cb75ca3` (T1) a `1eee185` (T8), `ddb84fc` (ajustes), `19297b0` (mutación) y el de este
informe. `azure-apps` `076f669`, local, sin push. **T10 (despliegue) NO ejecutada**: es del humano.

## 1. Qué cambió

| Fichero | Cambio |
|---|---|
| `sql/compras/01_documentos.sql` | `estado_id`, `estado_codigo`, `estado` al final de `compras.albaranes`; lateral `fn_estado_documento(14, con.est)`; `idx_com_alb_est` |
| `sql/compras/13_estado_documentos.sql` | Cuarto bloque (tipo 14), cinco orígenes, `tipo_documento` del 14 = el de la cabecera; misma forma de 15 columnas |
| `domain/estado_documentos.py` | Constantes del tipo 14, `ORIGENES_FECHA` con cinco, `fecha_estado(..., fecha_facturacion=None)` en el orden de R7 |
| `application/steps/build_compras_step.py` | Solo comentarios |
| `config/diccionario/compras.yaml`, `00_global.yaml` | Fichas de R11-R13; versión **70** (256 objetos, 2243 columnas), sin publicar |
| `docs/ARCHITECTURE.md`, `azure-apps/datamart_seg_anual.md` | La vista con albaranes; sección nueva F-153 |
| `tests/` | `test_f153_{dominio,sql,diccionario}.py` nuevos; `test_f132_*`, `test_f128_sql` y `test_f073_sql` al día |

**NO se toca:** `tables_sigrid.yaml`, `00_setup.sql`, `12_documento_procesos.sql`, `grants.py`, `mcp-bbdd`
ni `raw.yaml`: `conest` dice «las cabeceras de `compras`», que sigue siendo cierto (comprobado, T7).

## 2. Decisiones y desviaciones

- **`HASH_01_DOCUMENTOS` recalculado en `test_f073_sql.py`.** El design §2 no lo listaba; el propio test
  pide recalcularlo, y F-128 hizo lo mismo. Fuera de la lista de ficheros de la spec, justificado.
- **`para_que_sirve` de `compras` reescrito para caber en 350 caracteres** (estaba a 350 justos). El T7
  subió `PRESUPUESTO_MAX` a 31.321; al acortar la frase dejó de hacer falta y `ddb84fc` lo devolvió a
  31.287: el fichero queda igual que antes de F-153. El mensaje del commit T7 ya no describe el final.
- **Ejemplo de `codigo_documento`**: `PROF25/00055`; `AC22/01874` disparaba `test_f006_r10` por el 22.
- **Dominio y orden:** `FACTURACION` se decide antes que `ALTA`, también con último paso a otro estado:
  es el caso normal de los FAC. Tras `PASO`, un paso restante da `FUERA_DE_PROCESO` con cota (design §3).
- **Trabajo con `init.sh` en marcha.** La línea base tarda 1 h 08 min. Mientras corría cambié solo Python,
  ya cargado por pytest, y dejé SQL y YAML para después. Por eso esa primera pasada acabó con pytest en verde
  (10.042 passed) y **KO en PUERTA COBERTURA** (33,3 %, 5/15): medía código anterior a mis commits. Causado por
  mí, no por el repositorio; la pasada final está en verde.
- **Lo que cacé tarde:** la primera campaña abortó con la línea base en rojo (26 tests): el `para_que_sirve`
  invalidaba el diccionario y arrastraba al resto, más hash, recuento de `current.md` y el 22. No había corrido
  la suite completa tras T7. Corregido en `ddb84fc`; 723 passed en los ficheros afectados y suite entera verde.

## 3. Verificación real

**Prototipo contra Azure, solo lectura, 2026-11-02 13:15 UTC** (el SQL real del árbol, con `compras.albaranes`
sustituida por una subconsulta que añade las tres columnas; sin escrituras). Coincide con design §1:

| Comprobación | Resultado | Esperado |
|---|---|---|
| `estado_codigo` de la SELECT de `01` | FAC 270.177, CON 37.598, PDT 7.689, COM 410, NULL 10 | igual |
| `FACTURACION` tipo 14, todas con fecha y días | 235.254 | 235.254 |
| `ALTA` tipo 14, todas con fecha | 7.689 | 7.689 |
| `SIN_HISTORIAL`, 0 con fecha, días o cota | 72.941 | 72.941 |
| `PASO` y `FUERA_DE_PROCESO` tipo 14 | 0 | 0 |
| Tipos 15, 44 y 46 | PASO 206.740, ALTA 1.239, FUERA 74 | no cambian de lógica |

**La vista real no existe aún en Azure:** esto valida su texto, no el despliegue. El coste (R19) no se midió.

## 4. Fase RED

Comando: `.venv/Scripts/python.exe -m pytest tests/test_f153_dominio.py tests/test_f153_sql.py -q --tb=line`
(antes de T2, exit 2):

```
E   ImportError: cannot import name 'ESTADO_FACTURADO_ALBARAN' from 'etl_sigrid.domain.estado_documentos' (C:\Users\pgris\PycharmProjects\da
2 errors in 1.11s
```

Con el dominio hecho y el SQL sin tocar, añadiendo `tests/test_f132_dominio.py`:

```
E   AssertionError: ESCE(rec.fiscal, 0)::NUMERIC(18, 2) AS importe_retencion_fiscal, COALESCE(a.totpag, 0)::NUMERIC(18, 2) AS total_a_pagar, compras.fn_sigrid_date(a.fecd
E   assert 'LEFT JOIN LATERAL compras.fn_estado_documento(14, con.est) est ON TRUE' in "CREATE TABLE compras.albaranes AS SELECT a.ide AS albaran_id, con.cod AS codigo_al
E   assert 'CREATE INDEX idx_com_alb_est ON compras.albaranes (estado_id);' in "DROP TABLE IF EXISTS compras.contratos CASCADE; CREATE TABLE compras.contratos AS SELECT c
E   AssertionError: assert 'F-153' in '-- etl_sigrid/infrastructure/postgres/sql/compras/01_documentos.sql\n-- =============================================...===========
C:\Users\pgris\PycharmProjects\datamart-seg-anual\tests\test_f153_sql.py:209: assert ('albaran' in "
=========================== short test summary info ===========================
FAILED tests/test_f153_sql.py::test_f153_r1_las_tres_columnas_al_final_y_en_orden
FAILED tests/test_f153_sql.py::test_f153_r2_la_traduccion_va_por_la_pareja_con_el_tipo_14
FAILED tests/test_f153_sql.py::test_f153_r2_el_lateral_va_tras_prv_con_y_antes_de_los_joins_de_f128
FAILED tests/test_f153_sql.py::test_f153_r4_indice_por_estado - assert 'CREAT...
FAILED tests/test_f153_sql.py::test_f153_la_cabecera_del_sql_cuenta_f153 - As...
FAILED tests/test_f153_sql.py::test_f153_r5_cuatro_bloques_y_el_ultimo_lee_la_cabecera_de_albaranes
FAILED tests/test_f153_sql.py::test_f153_r5_los_otros_tres_bloques_rellenan_las_dos_columnas_nuevas
FAILED tests/test_f153_sql.py::test_f153_r6_tipo_documento_del_14_es_el_de_la_cabecera
FAILED tests/test_f153_sql.py::test_f153_r7_origen_fecha_en_el_orden_del_dominio
FAILED tests/test_f153_sql.py::test_f153_r7_facturacion_es_ese_dia_a_las_cero
FAILED tests/test_f153_sql.py::test_f153_r10_los_literales_de_la_vista_son_los_del_dominio
FAILED tests/test_f153_sql.py::test_f153_las_tres_sentencias_y_la_cabecera_dice_el_tipo_14
FAILED tests/test_f153_sql.py::test_f153_el_comment_nombra_los_albaranes_y_los_cinco_origenes
13 failed, 57 passed in 0.74s
```

Fichas, `pytest tests/test_f153_diccionario.py -q --tb=line`, antes de T6:

```
=========================== short test summary info ===========================
FAILED tests/test_f153_diccionario.py::test_f153_r11_las_tres_columnas_al_final_de_la_ficha
FAILED tests/test_f153_diccionario.py::test_f153_r11_los_cuatro_estados_del_tipo_14
FAILED tests/test_f153_diccionario.py::test_f153_r11_declara_reparto_fuera_de_catalogo_y_facturado_s
FAILED tests/test_f153_diccionario.py::test_f153_r11_el_estado_no_dice_desde_cuando
FAILED tests/test_f153_diccionario.py::test_f153_r11_relacion_y_ejemplo - Key...
FAILED tests/test_f153_diccionario.py::test_f153_r11_fn_estado_documento_nombra_albaranes
FAILED tests/test_f153_diccionario.py::test_f153_r12_los_cinco_origenes - Ass...
FAILED tests/test_f153_diccionario.py::test_f153_r12_tipo_14_se_filtra_por_codigo
FAILED tests/test_f153_diccionario.py::test_f153_r12_valores_contra_el_dominio
FAILED tests/test_f153_diccionario.py::test_f153_r12_que_parte_tiene_fecha_y_cual_no
FAILED tests/test_f153_diccionario.py::test_f153_r12_facturado_no_sale_de_rac_y_es_de_dia
FAILED tests/test_f153_diccionario.py::test_f153_r12_el_tamano_y_la_relacion_con_la_cabecera
FAILED tests/test_f153_diccionario.py::test_f153_r12_los_nulos_nombran_los_origenes_nuevos
FAILED tests/test_f153_diccionario.py::test_f153_r12_el_ejemplo_va_detras_de_los_actuales
FAILED tests/test_f153_diccionario.py::test_f153_r13_la_vista_ya_no_son_tres_familias
FAILED tests/test_f153_diccionario.py::test_f153_r13_global_y_architecture_nombran_los_albaranes
FAILED tests/test_f153_diccionario.py::test_f153_r14_la_version_sube_a_70_con_su_nota
FAILED tests/test_f153_diccionario.py::test_f153_r14_ningun_objeto_nuevo_y_tres_columnas_mas
FAILED tests/test_f153_diccionario.py::test_f153_r15_azure_apps_recoge_el_cambio
19 failed in 2.47s
```

## 5. Verificaciones MANUAL pendientes (T10, design §9)

Tras APROBADO y merge: imagen, job, `build-compras`, cifras reales, `publicar-diccionario` v70, checks,
reinicio del MCP, **R16-R18** por el MCP, **R19** (paso 4 bis) e `init.sh` sobre `main`. Tras la review,
§9 lleva `apply-grants` fijo (ida y vuelta, 49 y 46 columnas para los dos lectores), `7e755b3` como
vuelta atrás con merge `--no-ff`, y la medida de R19. Solo cambió `design.md` §8-§9; ni código ni tests. **Power BI** no se pudo
inspeccionar. Hasta el paso 5, `check-diccionario` devuelve 1: es lo esperado.

## 6. Fuera de alcance

F-133 (su criterio «igual antes y después» deja de valer para el tipo 14; anotado en `current.md`), F-134,
F-105 y corregir en Sigrid los 10 sin estado o los 185 con `estfac` distinto.

## Evidencias

| Evidencia | Valor |
|---|---|
| Tests | **10.103 passed, 274 skipped, 0 failed** (`bash harness/init.sh` final, sobre `19297b0`) |
| Cobertura de líneas cambiadas | **100,0 %** (15/15; PUERTA COBERTURA) |
| Mutantes | **9 generados, 9 muertos, 0 supervivientes**, 0 timeouts (`progress/mutacion_F-153.md`) |
| Tiempo de la suite | 4.031,96 s (1 h 07 min) con cobertura; 1.793-1.828 s por worker en la línea base de mutación |
| `init.sh` | **ENTORNO LISTO**; PUERTA TAMAÑO en verde |

La mutación solo alcanza Python (2 ficheros): el SQL lo cubren los tests de texto y el prototipo, no los
mutantes. Corrió con `--workers 3 --timeout 3000`, y el modo paralelo puede dar falsos muertos. Este informe y
`tasks.md` se escribieron después del verde; solo tocan `progress/` y `specs/`.
