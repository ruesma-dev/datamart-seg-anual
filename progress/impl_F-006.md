<!-- progress/impl_F-006.md -->
# F-006 · Informe de implementación — bloques A, B, C y D

> Rama `feature/F-006-mcp-azure`. Alcance de este encargo: **Fase 0 (comprobar)
> y bloques A, B, C y D** de `specs/F-006-mcp-azure/tasks.md` (T3 a T14).
> Los bloques E a K **no** entran, y en particular **no se ha tocado nada de
> permisos, `REVOKE`, firewall ni Azure**, ni se ha abierto ninguna conexión a
> la base: el `.env` de este puesto apunta a `psql-albaranes-rs9k2`, servidor
> compartido con `albaranes` y `partes` en producción.

Este fichero se va escribiendo **a medida que avanza el trabajo**, no al final:
es la memoria que sobrevive a un corte de sesión.

---

## Fase 0 · Comprobación (T1, T2)

| Tarea | Estado | Comprobación |
|---|---|---|
| **T1** · DA-1 a DA-6 cerradas | ✅ ya hecha | `specs/F-006-mcp-azure/requirements.md` §12: las seis con su resolución, todas con la recomendación de la spec. Commit `962fb52` |
| **T2** · `"rigor": "critico"` en la ficha | ✅ ya hecha | Commit `cab50ab`. `bash harness/init.sh` imprime `niveles: critico, ...` y `BACKLOG.md` está al día |

`bash harness/init.sh` de partida: **verde**, 798 tests, rama
`feature/F-006-mcp-azure`.

---

## Fase RED (rigor `critico`)

Las trazas reales del fallo **antes** de existir el código, con el comando
exacto. No hay resúmenes: va la salida pegada.

### T3 · `etl_sigrid/domain/diccionario.py` — entidades y `validar()` (R2–R8)

```
$ python -m pytest tests/test_f006_formato.py -q
=================================== ERRORS ====================================
_________________ ERROR collecting tests/test_f006_formato.py _________________
ImportError while importing test module 'C:\Users\pgris\PycharmProjects\datamart-seg-anual\tests\test_f006_formato.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
..\..\AppData\Local\Programs\Python\Python312\Lib\importlib\__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\test_f006_formato.py:20: in <module>
    from etl_sigrid.domain.diccionario import (
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.diccionario'
=========================== short test summary info ===========================
ERROR tests/test_f006_formato.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.15s
```

---

## Evidencias

*(se completa al terminar los cuatro bloques)*

### T4 · `derivar_avisos()` y las validaciones R9 / R11 / R12

```
$ python -m pytest tests/test_f006_reglas.py tests/test_f006_formato.py -q
=================================== ERRORS ====================================
_________________ ERROR collecting tests/test_f006_reglas.py __________________
ImportError while importing test module 'C:\Users\pgris\PycharmProjects\datamart-seg-anual\tests\test_f006_reglas.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
..\..\AppData\Local\Programs\Python\Python312\Lib\importlib\__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\test_f006_reglas.py:19: in <module>
    from etl_sigrid.domain.diccionario import (
E   ImportError: cannot import name 'CODIGOS_REGLAS_OBLIGATORIAS' from 'etl_sigrid.domain.diccionario'
=========================== short test summary info ===========================
ERROR tests/test_f006_reglas.py
ERROR tests/test_f006_formato.py
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!
2 errors in 0.18s
```

Verde tras el código: `78 passed in 0.12s`.

### T5 · Frescura: R13 y R14 contra la composición REAL del pipeline

```
$ python -m pytest tests/test_f006_frescura.py -q
>       assert errores
E       assert []

tests\test_f006_frescura.py:143: AssertionError
____ test_f006_r14_el_veredicto_sigue_al_pipeline_y_no_a_una_lista_copiada ____
>       assert validar(dicc, PASOS_NOCTURNOS), "hoy build_cierre no corre de noche"
E       AssertionError: hoy build_cierre no corre de noche
E       assert []
=========================== short test summary info ===========================
FAILED tests/test_f006_frescura.py::test_f006_r14_los_cuatro_esquemas_manuales_no_pueden_ser_nocturnos[cierre]
FAILED tests/test_f006_frescura.py::test_f006_r14_los_cuatro_esquemas_manuales_no_pueden_ser_nocturnos[compras]
FAILED tests/test_f006_frescura.py::test_f006_r14_los_cuatro_esquemas_manuales_no_pueden_ser_nocturnos[maestro]
FAILED tests/test_f006_frescura.py::test_f006_r14_los_cuatro_esquemas_manuales_no_pueden_ser_nocturnos[retenciones]
FAILED tests/test_f006_frescura.py::test_f006_r14_declararse_manual_con_un_paso_nocturno_tambien_falla
FAILED tests/test_f006_frescura.py::test_f006_r14_el_veredicto_sigue_al_pipeline_y_no_a_una_lista_copiada
6 failed, 7 passed in 0.96s
```

Verde tras el código: `91 passed in 0.87s` (los tres ficheros de F-006).

### T6 · `etl_sigrid/domain/inventario.py` — inventario y cobertura

```
$ python -m pytest tests/test_f006_cobertura.py -q -k dominio
=================================== ERRORS ====================================
________________ ERROR collecting tests/test_f006_cobertura.py ________________
ImportError while importing test module '...\tests\test_f006_cobertura.py'.
Traceback:
tests\test_f006_cobertura.py:25: in <module>
    from etl_sigrid.domain.inventario import (
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.inventario'
=========================== short test summary info ===========================
ERROR tests/test_f006_cobertura.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.15s
```

Verde tras el código: `33 passed in 0.07s`.

### T7 · `cargador_yaml.py` — lectura de los YAML y `hash_fuente`

```
$ python -m pytest tests/test_f006_formato.py -q -k cargador
FAILED tests/test_f006_formato.py::test_f006_r22_cargador_el_hash_no_depende_del_fin_de_linea
FAILED tests/test_f006_formato.py::test_f006_r22_cargador_el_hash_cambia_si_se_renombra_un_fichero
FAILED tests/test_f006_formato.py::test_f006_r8_cargador_un_yaml_roto_no_devuelve_una_traza_de_yaml
FAILED tests/test_f006_formato.py::test_f006_r6_cargador_rechaza_una_clave_desconocida_en_una_columna
FAILED tests/test_f006_formato.py::test_f006_r2_cargador_rechaza_una_clave_desconocida_en_una_ficha
FAILED tests/test_f006_formato.py::test_f006_r1_cargador_exige_que_el_nombre_del_fichero_sea_el_esquema
FAILED tests/test_f006_formato.py::test_f006_r1_cargador_ignora_lo_que_no_sea_yaml
FAILED tests/test_f006_formato.py::test_f006_r1_cargador_sin_global_no_hay_diccionario
FAILED tests/test_f006_formato.py::test_f006_r12_cargador_pasa_los_avisos_escritos_a_mano_al_validador
FAILED tests/test_f006_formato.py::test_f006_r1_cargador_lee_las_relaciones
FAILED tests/test_f006_formato.py::test_f006_r1_cargador_una_ficha_sin_cuerpo_es_un_error
17 failed, 45 deselected in 0.51s
```

Verde tras el código: `141 passed in 1.16s` (los cuatro ficheros de F-006).

Un test de la tanda RED se reescribió al implementar: `..._el_hash_cambia_si_se_
renombra_un_fichero` era imposible de satisfacer sin violar la regla «el nombre
del fichero manda sobre el campo `esquema`», que el propio cargador impone. Se
sustituyó por `..._el_hash_cubre_el_conjunto_de_ficheros`, que comprueba la
propiedad que de verdad importa: **añadir un fichero cambia el hash aunque
ninguno de los viejos cambie**.

### T8 · La puerta real sobre el repositorio

```
$ python -m pytest tests/test_f006_cobertura.py -q -k puerta
E           etl_sigrid.infrastructure.diccionario.cargador_yaml.DiccionarioIlegible: 00_global.yaml: no existe 00_global.yaml en ...\config\diccionario: sin bloque global no hay reglas, ni esquemas, ni pendientes

etl_sigrid\infrastructure\diccionario\cargador_yaml.py:149: DiccionarioIlegible
=========================== short test summary info ===========================
FAILED tests/test_f006_cobertura.py::test_f006_r1_puerta_el_diccionario_real_se_carga
FAILED tests/test_f006_cobertura.py::test_f006_r25_puerta_todo_objeto_publicado_tiene_ficha_o_esta_pendiente
FAILED tests/test_f006_cobertura.py::test_f006_r27_puerta_el_trinquete_solo_baja
FAILED tests/test_f006_cobertura.py::test_f006_r27_puerta_el_trinquete_no_esta_holgado
4 failed, 7 passed, 27 deselected in 0.21s
```

Verde tras crear `config/diccionario/00_global.yaml`: `11 passed`, y
`bash harness/init.sh` en verde con **944 tests** y
`PUERTA COBERTURA: 92.8% de 498 lineas cambiadas cubiertas (462/498, umbral 80%, nivel critico)`.

**El inventario real del repositorio son 98 objetos publicados**, no los ~80 que
estimaba la spec:

| esquema | objetos |
|---|---|
| `raw` | 31 (de `config/tables_sigrid.yaml`) |
| `compras` | 14 |
| `mart` | 13 |
| `cierre` | 12 |
| `retenciones` | 10 |
| `stg` | 10 |
| `maestro` | 4 |
| `_meta` | 3 |
| `aux` | 1 |

`PENDIENTES_MAX` arranca en **98** y solo baja.

---

## Bloque B · Reglas duras y bloque global

### T9 · Las doce reglas de R9 en `00_global.yaml`

```
$ python -m pytest tests/test_f006_reglas.py -q
E         Left contains one more item: ErrorValidacion(fichero='00_global.yaml', objeto='R-ABONO-NEGATIVO', regla='R11', detalle='la regla `R-ABONO-NEGATIVO`...to `compras.fact_compras_linea`, que no tiene ficha en el diccionario. Una regla que apunta a la nada no protege nada')
tests\test_f006_reglas.py:419: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_f006_reglas.py::test_f006_r9_el_global_real_declara_las_doce_reglas
FAILED tests/test_f006_reglas.py::test_f006_r9_las_reglas_reales_son_bloqueantes_salvo_las_que_avisan
FAILED tests/test_f006_reglas.py::test_f006_r10_el_global_real_trae_ordenes_de_magnitud
FAILED tests/test_f006_reglas.py::test_f006_r9_importe_mes_dice_lo_que_no_se_puede_hacer
FAILED tests/test_f006_reglas.py::test_f006_r9_retencion_no_join_lineas_cita_el_incidente
FAILED tests/test_f006_reglas.py::test_f006_r9_frescura_manual_nombra_los_cuatro_esquemas
FAILED tests/test_f006_reglas.py::test_f006_r11_un_ambito_declarado_pendiente_se_tolera
7 failed, 36 passed in 0.25s
```

Verde tras escribir las reglas: `43 passed`, y `156 passed` en todo F-006.

**Las doce reglas, verificadas una a una contra el SQL** (no contra los
informes). Lo que se comprobó de cada una:

| Regla | Comprobado en |
|---|---|
| `R-FRESCURA-MANUAL` | `main.build_pipeline_steps` construido de verdad: `ingest_raw, load_excel_aux, build_stg, build_mart, apply_grants` |
| `R-IMPORTE-MES` | `sql/mart/01_ddl.sql` (columnas `importe_mes` / `importe_origen`) |
| `R-UNIVERSO-OBRA` | `sql/stg/03_obras.sql` (filtros y dedup por `conext.cod='15'`) vs `sql/maestro/01_obras.sql` (sin filtro) |
| `R-OBRA-ACTIVA` | `sql/stg/03_obras.sql:123` → `TRUE AS activa`, literal |
| `R-VERSION-MASTER` | `sql/mart/06_views_cp_tipologia.sql` (tipado de versión y elección de vigente) |
| `R-FAS-AMBIGUO` | `sql/stg/01_ddl.sql`: `fase_num` en `presupuesto`, `version` en `plan_mensual` |
| `R-CLAVE-SUSTITUTA` | los siete `BIGSERIAL` del árbol SQL, con sus `DROP TABLE` |
| `R-ABONO-NEGATIVO` | `sql/compras/03_views.sql:10` «los ABONOS restan (signo natural)» |
| `R-LINEA-ID-NO-UNICA` | `sql/compras/02_fact_linea.sql`: `CREATE TABLE ... AS` de tres orígenes, sin PK |
| `R-RETENCION-NO-JOIN-LINEAS` | `sql/retenciones/01_movimientos.sql` (un registro por efecto) |
| `R-COMPRAS-SIN-IVA` | `sql/compras/02_fact_linea.sql` (sin IVA) vs `sql/maestro/03_proveedores_obra.sql` (`SUM(t.totdoc)`) |
| `R-COMPRAS-TIPO-DOC` | `compras.fn_tipo_documento`: CONTRATO, ALBARAN, PROFORMA, NOTA, FACTURA, ABONO, OTRO |

**Cambio de diseño hecho aquí, con su motivo.** `validar` tolera ahora que el
`ambito` de una regla —y el destino de una `relacion`— apunte a un objeto
declarado en `pendientes`. Sin eso, las doce reglas no se podían escribir hasta
tener las noventa y ocho fichas, que es el orden equivocado: las reglas son la
pieza de más valor por línea. **La comprobación no se salta, se aplaza**: en
cuanto el objeto tiene ficha, se verifica (y en el caso de las relaciones,
también su columna), y al cerrar F-006 `pendientes` está vacía y vuelve a ser
estricta.

**Hallazgo, para T20/T21 (bloque F, fuera de este encargo):** `build-compras` y
`build-retenciones` **no registran paso en `_meta.etl_runs`** —ejecutan SQL en
línea sin step (`main.py`, comentario «no registra paso ... queda fuera de
`v_frescura`»)—, así que **su frescura no es consultable por SQL**. `cierre` y
`maestro` sí registran (`build_cierre`, `build_maestros`). Queda dicho dentro de
la propia regla `R-FRESCURA-MANUAL` para que el agente no prometa una fecha que
no puede obtener. Convertirlos en step es otra feature.

### T10 · Convenciones, ejes, `ocultar` y las nueve entradas de `esquemas`

```
$ python -m pytest tests/test_f006_formato.py -q -k global
E       assert [ErrorValidac... | stg'), ...] == []
E         Left contains 9 more items, first extra item: ErrorValidacion(fichero='00_global.yaml', objeto=None, regla='R4', detalle='el esquema `_meta` no tiene entrada en `esquemas`. El diccionario debe cubrir los nueve: _meta | aux | cierre | compras | maestro | mart | raw | retenciones | stg')
tests\test_f006_formato.py:1061: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_f006_formato.py::test_f006_r4_el_global_real_declara_los_nueve_esquemas
FAILED tests/test_f006_formato.py::test_f006_r4_los_cuatro_esquemas_manuales_lo_declaran_en_el_global
FAILED tests/test_f006_formato.py::test_f006_r4_el_global_real_trae_las_convenciones_que_mas_confunden
FAILED tests/test_f006_formato.py::test_f006_r4_el_global_real_declara_los_ejes_del_modelo
FAILED tests/test_f006_formato.py::test_f006_r4_el_global_real_oculta_las_columnas_tecnicas
FAILED tests/test_f006_formato.py::test_f006_r2_el_diccionario_global_real_valida_entero
6 failed, 3 passed, 62 deselected in 1.17s
```

Verde tras escribir el bloque: `9 passed` en `-k global`, `167 passed` en F-006.

Decisiones de contenido que conviene dejar por escrito:

- **Los cuatro literales de `escenario`** se declaran como eje propio y hay un
  test que los contrasta **contra el SQL de `mart.v_pbi_dim_escenario`**: son
  `Coste Real`, `Coste Planificado`, `Venta Real`, `Venta Planificada`. El
  ejemplo de `design.md` §3.3 usa `COSTE_REAL`, `VENTA_PLAN`… y **está mal**;
  manda el SQL.
- **`aux` se declara `refresco: estatico`.** Se comprobó que `LoadExcelAuxStep`
  **no escribe en `aux`** (su propio docstring: «aquí se LEE y se VALIDA, no se
  carga nada a `aux.*`»), así que la tabla se crea vacía y nada la rellena.
- **`_meta` entra en la superficie de consumo** (`consumo_recomendado: true`):
  es lo que responde P15, «¿de cuándo es el dato que me estás dando?».
- **`raw` y `stg` quedan fuera** (`false`), coherente con lo que R30 hará con
  `PG_CONSUMPTION_SCHEMAS` en el bloque I. Aquí es solo una recomendación
  editorial: **no se ha tocado ningún permiso**.
- Se añadió un test que cruza `esquemas[*].pasos_etl` contra el pipeline real:
  un esquema que se declare `nocturno` citando un paso que no corre de noche
  deja `init.sh` en rojo.

### T11 · Las 18 preguntas de la batería de aceptación

```
$ python -m pytest tests/test_f006_reglas.py -q -k bateria
tests\test_f006_reglas.py:440: KeyError
=========================== short test summary info ===========================
FAILED tests/test_f006_reglas.py::test_f006_r39_bateria_estan_las_dieciocho_preguntas
FAILED tests/test_f006_reglas.py::test_f006_r39_bateria_cada_pregunta_dice_que_seria_correcto
FAILED tests/test_f006_reglas.py::test_f006_r41_bateria_el_recuento_honesto_es_trece_tres_y_dos
FAILED tests/test_f006_reglas.py::test_f006_r41_bateria_lo_no_respondible_dice_que_feature_lo_desbloquea
FAILED tests/test_f006_reglas.py::test_f006_r41_bateria_las_features_que_bloquean_existen_de_verdad
FAILED tests/test_f006_reglas.py::test_f006_r39_bateria_los_objetos_esperados_existen_en_el_repositorio
FAILED tests/test_f006_reglas.py::test_f006_r41_bateria_las_imposibles_no_esperan_ningun_objeto
FAILED tests/test_f006_reglas.py::test_f006_r39_bateria_las_cuatro_trampas_estan_marcadas
FAILED tests/test_f006_reglas.py::test_f006_r39_bateria_cada_trampa_nombra_la_regla_que_la_evita
9 failed, 43 deselected in 0.44s
```

Verde tras escribir la batería: `9 passed`.

Tres tests que no pedía la spec y que se añadieron porque protegen algo real:

- **`objetos_esperados` se contrasta contra el inventario del repositorio.**
  Enrutar la pregunta a un objeto que no existe manda al agente a inventarse el
  SQL, que es justo lo que la feature evita.
- **Las dos imposibles (P4, P17) no pueden declarar ningún objeto.** Si la
  batería les diera objetos, el agente buscaría ahí y acabaría dando una cifra
  parecida a la pedida pero de otra cosa.
- **Cada pregunta trampa nombra la regla que la evita** (`reglas_implicadas`).
  Es lo que permitirá, al ejecutar la batería en T39, distinguir si falló el
  agente o si la ficha estaba mal escrita.

Los `bloqueada_por` se comprueban contra `harness/features.json`: F-036 a F-040
existen.
