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

## Bloque A · Andamiaje

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

---

## Bloque C · Fichas de `mart`

### T12 · Las dos tablas de hecho

```
$ python -m pytest tests/test_f006_cobertura.py tests/test_f006_fichas.py -q
FAILED tests/test_f006_cobertura.py::test_f006_r25_puerta_todo_objeto_publicado_tiene_ficha_o_esta_pendiente
FAILED tests/test_f006_cobertura.py::test_f006_r27_puerta_el_trinquete_solo_baja
FAILED tests/test_f006_cobertura.py::test_f006_r27_puerta_el_trinquete_no_esta_holgado
FAILED tests/test_f006_fichas.py::test_f006_r26_mart_las_tablas_documentan_exactamente_sus_columnas[fact_seguimiento_categoria-mart/03_agg_categoria.sql]
FAILED tests/test_f006_fichas.py::test_f006_r26_mart_las_tablas_documentan_exactamente_sus_columnas[fact_seguimiento_mensual-mart/01_ddl.sql]
FAILED tests/test_f006_fichas.py::test_f006_r2_mart_la_clave_de_negocio_es_el_grano_declarado[fact_seguimiento_categoria-mart/03_agg_categoria.sql]
FAILED tests/test_f006_fichas.py::test_f006_r2_mart_la_clave_de_negocio_es_el_grano_declarado[fact_seguimiento_mensual-mart/01_ddl.sql]
FAILED tests/test_f006_fichas.py::test_f006_r7_mart_importe_origen_no_se_declara_sumable
FAILED tests/test_f006_fichas.py::test_f006_r7_mart_las_claves_sustitutas_estan_marcadas
FAILED tests/test_f006_fichas.py::test_f006_r12_mart_las_tablas_de_hecho_heredan_sus_avisos
FAILED tests/test_f006_fichas.py::test_f006_r7_mart_el_escenario_declara_sus_cuatro_valores
12 failed, 35 passed in 0.46s
```

Verde tras escribir `config/diccionario/mart.yaml`: `185 passed` en F-006.
`PENDIENTES_MAX` baja de **98 a 96**.

**Fichero nuevo: `tests/test_f006_fichas.py`.** No lo pedía la spec y es la
pieza que más protege del encargo. La puerta de cobertura comprueba que cada
objeto TIENE ficha; esto comprueba que la ficha **dice la verdad**: parsea el
`CREATE TABLE` real y exige que las columnas documentadas sean exactamente las
que existen, ni una de menos ni una de más. Para las tablas la comprobación es
exacta; para las vistas se hará más débil (que el nombre aparezca en el SQL que
las crea) y el docstring lo declara.

El parser de DDL se prueba a sí mismo antes de que nadie se fíe de él
(`test_f006_r26_el_parser_de_ddl_no_se_corta_dentro_de_un_numeric`), y aun así
falló en el primer intento con un caso real: `unidad_medida VARCHAR(16), -- m3,
m2, ud, kg... (de obrparpar.unimed)`. La coma **dentro del comentario** partía
la definición en dos. Se corrigió quitando comentarios antes de contar comas y
paréntesis, y queda anotado en el propio código.

**Correcciones a `design.md` §3.3 obligadas por el SQL** (manda el SQL):

| `design.md` decía | El SQL dice |
|---|---|
| `obra_codigo`, `partida_codigo`, `mes` | `codigo_obra`, `codigo_partida`, `anio_mes` |
| `escenario: [COSTE_REAL, COSTE_PLAN, VENTA_REAL, VENTA_PLAN]` | `Coste Real`, `Coste Planificado`, `Venta Real`, `Venta Planificada` |
| `clave_negocio: [obra_codigo, partida_codigo, mes, escenario]` | se usa `[obra_id, partida_id, anio_mes, escenario]`: `obra_id` es `con.ide`, estable entre builds, y `codigo_partida` es anulable |

### T13 · Las once vistas de `mart`

```
$ python -m pytest tests/test_f006_cobertura.py -q -k puerta
tests\test_f006_cobertura.py:461: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_f006_cobertura.py::test_f006_r25_puerta_todo_objeto_publicado_tiene_ficha_o_esta_pendiente
1 failed, 10 passed, 27 deselected in 0.38s
```

Verde tras escribir las once vistas: `211 passed` en F-006, `1009 passed` en
`bash harness/init.sh`. `PENDIENTES_MAX` baja de **96 a 85**.

El test genérico nuevo —«ninguna columna documentada está inventada»— falló en
su primera versión **por un fallo del propio test**: el `\b` del regex se
escribió como carácter de retroceso en vez de como frontera de palabra, y
marcaba TODAS las columnas como inventadas. Se corrigió; el test ahora distingue
`mes` de `anio_mes`, que era el motivo de usar frontera de palabra.

Decisión editorial que conviene revisar: **`mart.v_fact_periodificado` se declara
`consumo_recomendado: false`**, con su `motivo_no_consumo` escrito. No es para
esquivar la puerta —sus columnas están documentadas igual— sino porque **hoy no
periodifica nada**: `aux.periodificacion_partida` se crea vacía por diseño, así
que la vista devuelve lo mismo que la tabla de hecho más dos columnas, y todas
sus filas salen marcadas `NO_PERIODIFICADO`. Recomendarla sería mandar al agente
por el camino largo. La ficha dice qué cambiaría el día que se carguen reglas.

Ruff quedó en cero avisos nuevos: los 9 que introdujo el bloque se cerraron
(orden de imports, `B023` en un cierre sobre variable de bucle y un `noqa`
razonado en `DiccionarioIlegible`, que en español no admite el sufijo `Error`).

---

## Bloque D · Fichas de `cierre`

### T14 · La tabla de hecho, las ocho vistas y las tres funciones

```
$ python -m pytest tests/test_f006_cobertura.py tests/test_f006_fichas.py -q
tests\test_f006_fichas.py:335: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_f006_cobertura.py::test_f006_r25_puerta_todo_objeto_publicado_tiene_ficha_o_esta_pendiente
FAILED tests/test_f006_fichas.py::test_f006_r14_cierre_entero_se_declara_de_refresco_manual
FAILED tests/test_f006_fichas.py::test_f006_r26_cierre_la_tabla_de_hecho_documenta_sus_columnas
FAILED tests/test_f006_fichas.py::test_f006_r2_cierre_las_tres_funciones_estan_documentadas
4 failed, 73 passed in 4.16s
```

Verde tras escribir `config/diccionario/cierre.yaml`. `PENDIENTES_MAX` baja de
**85 a 73**.

**`tasks.md` T14 dice «`fact_cierre_mensual`, las 6 vistas y las 3 funciones».
Son OCHO vistas**, no seis: además de `v_pbi_cierre_resumen`,
`v_pbi_dim_concepto`, `v_pbi_cierre_cabecera`, `v_pbi_cierre_indirectos_detalle`,
`v_pbi_cierre_generales_detalle` y `v_pbi_planif_vs_real`, están
`v_pbi_dim_subcategoria_ci` y `v_pbi_dim_tipologia_cp`. Las doce fichas están
escritas.

Tres tests propios de este bloque, que son los que impiden la mentira concreta
de `cierre`:

- **todas sus fichas declaran `refresco: manual` y `paso_etl: build_cierre`**.
  Una sola que dijera `nocturno` bastaría para que el agente diera un dato de
  hace semanas sin advertirlo;
- **todas heredan el aviso `R-FRESCURA-MANUAL`** por derivación, no a mano;
- la tabla de hecho documenta **exactamente** las columnas de su `CREATE TABLE`.

Contenido que costó verificar y que no estaba en ningún informe:

- **`presupuesto_aprobado_venta` es hoy una COPIA literal del inicial**
  (`sql/cierre/05_views_cabecera.sql`: `vi.presupuesto_inicial_venta AS
  presupuesto_aprobado_venta`). La ficha lo dice, porque es el divisor del
  `final_pct` de la VENTA y alguien podría creer que es un dato propio.
- **El `final_pct` de la fila VENTA es la única excepción del cuadro**: va
  contra `presupuesto_aprobado_venta`, no contra la venta final. El resto de
  porcentajes van contra la VENTA de su misma columna y su mismo mes.
- **`ejecutado_mes_periodif` no resta el periodificado del mes anterior, resta
  el INCURRIDO**. Está en el comentario del SQL y es contraintuitivo; la ficha
  lo advierte.
- **`ratio_lineal` no tiene tope en el 100 %**: una obra que se alarga da más
  de 1. También queda dicho.
- `v_pbi_dim_subcategoria_ci` resuelve los nombres **por obra y no globalmente**,
  a propósito: el mismo código de subcapítulo se llama distinto en cada obra.

### Cobertura de las líneas cambiadas

Tras T14 la puerta daba `92.6 %`. Se añadieron tests para las ramas defensivas
que quedaban sin ejercitar —vocabularios mal escritos en el bloque global,
formas de YAML que no se pueden convertir en entidades, y el **informe que se
lee cuando la puerta se pone en rojo**— y quedó en:

```
[OK] PUERTA COBERTURA: 98.8% de 499 líneas cambiadas cubiertas (493/499, umbral 80%, nivel critico)
```

No es cosmética: esas ramas son manejo de errores, y un manejo de errores que
nadie ha ejecutado nunca es el que falla el día que hace falta.

---

## Lo que se dejó anotado y NO se arregló

Regla de hierro 3 de `tasks.md`: escribir las fichas obliga a leer las vistas y
va a destapar cosas. Se anotan, no se tocan.

| Hallazgo | Dónde | Qué feature lo recoge |
|---|---|---|
| **`build-compras` y `build-retenciones` no registran paso en `_meta.etl_runs`.** Ejecutan SQL en línea, sin step, así que **no aparecen en `_meta.v_frescura` y su fecha de build no se puede consultar por SQL**. `cierre` y `maestro` sí registran. | `main.py`, comandos `build-compras` y `build-retenciones` | Afecta a T20 y T21 (bloque F) y al valor real de `_meta.v_diccionario` (bloque E): el `LEFT JOIN` por `paso_etl` dará frescura nula para esos dos esquemas. Queda dicho dentro de `R-FRESCURA-MANUAL` para que el agente no prometa una fecha que no puede obtener. Convertirlos en step es feature propia |
| `cierre.v_pbi_cierre_cabecera.presupuesto_aprobado_venta` **es una copia literal del inicial**; no hay dato propio de aprobación | `sql/cierre/05_views_cabecera.sql` | Anotado en la ficha. Si negocio quiere un aprobado real, es feature de modelo |
| `mart.v_fact_periodificado` **no periodifica nada** hoy y devuelve lo mismo que la tabla de hecho | `aux.periodificacion_partida` se crea vacía | Anotado en la ficha, con `consumo_recomendado: false` y motivo |
| El inventario real son **98 objetos**, no los «más de 80» que estimaba la spec; `cierre` tiene **8 vistas**, no 6 | `sql/**` + `config/tables_sigrid.yaml` | Corregido aquí; conviene enmendarlo en `design.md` §5.1 |
| El ejemplo de ficha de `design.md` §3.3 usa **nombres de columna y literales de escenario que no existen** | `design.md` §3.3 | Corregido en las fichas. La enmienda del documento es del spec-author |

---

## Qué queda fuera de este encargo

Los bloques **E a K** de `tasks.md` (T15 a T42): la publicación en `_meta`, las
fichas de `compras`, `retenciones`, `maestro`, `stg`, `aux`, `_meta` y `raw`, el
comando `check-diccionario`, la documentación, **los permisos y los `REVOKE`**,
la conectividad y la batería de aceptación contra la base real.

**No se ha tocado nada de permisos, `REVOKE`, firewall ni Azure, y no se ha
abierto ninguna conexión a la base.** Tampoco se ha modificado `main.py`,
`config/settings.py`, `grants.py`, `postgres_client.py` ni ningún SQL de
negocio: este encargo solo **añade** ficheros y no cambia el comportamiento de
ningún comando existente.

Verificaciones `MANUAL (humano)` pendientes, todas de bloques posteriores: T19
(publicar contra la BBDD real), T27 (`check-diccionario`), T32 a T34 (los 🔏 de
permisos), T37 (`azure-apps`), T38 (firewall) y T39 (la batería).

---

## Evidencias

Números medidos, no estimados.

| Evidencia | Valor | Cómo se obtiene |
|---|---|---|
| **Tests ejecutados** | **1052 pasan, 0 fallan** (254 de ellos son de F-006) | `bash harness/init.sh` |
| **Tiempo de la suite** | **16,9 s** sin medición de cobertura; **≈46 s** dentro de `init.sh`, que la ejecuta bajo `coverage` | salida de pytest |
| **Cobertura de las líneas cambiadas** | **98,8 %** (493 de 499; umbral 80 %, nivel `critico`) | línea `PUERTA COBERTURA` de `bash harness/init.sh` |
| **Mutantes generados / supervivientes** | **112 generados, 112 muertos, 0 supervivientes, 0 timeouts** en 202,6 s | `python -m harness.mutacion --feature F-006` → `progress/mutacion_F-006.md` |
| **Objetos documentados** | **25 de 98** (`mart` 13, `cierre` 12) | `config/diccionario/` |
| **Columnas descritas** | **332**, todas con significado de negocio | ídem |
| **Trinquete `pendientes`** | **73**, bajando desde 98 | `PENDIENTES_MAX` en `tests/test_f006_cobertura.py` |
| **Reglas duras publicadas** | **12 de 12**, todas con ámbito resoluble y motivo | `00_global.yaml` |
| **Batería de aceptación** | **18 preguntas**: 13 respondibles, 3 parciales, 2 imposibles | ídem |

**Análisis de supervivientes: no hay ninguno.** La campaña cubrió los tres
módulos nuevos (`domain/diccionario.py`, `domain/inventario.py` y
`infrastructure/diccionario/cargador_yaml.py`, 1.523 líneas en alcance) y cada
mutación aplicada la cazó al menos un test. Detalle en
`progress/mutacion_F-006.md`.

Las seis líneas cambiadas sin cubrir son ramas de guarda redundantes con otras
ya ejercitadas (comprobaciones de tipo encadenadas dentro del cargador); ninguna
sobrevivió a la mutación, que es la comprobación que de verdad importa.

---

# Correcciones tras la review (RECHAZADO, `progress/review_F-006.md`)

Diez defectos, en el orden de gravedad del informe. Cada uno con su fase RED.

## Defecto 1 · `cardinalidad: 1:1` publicada como el entero `61`

Confirmado antes de tocar nada, ejecutando el cargador real:

```
$ python -c "... cargar_diccionario('config/diccionario') ..."
Counter({'N:1': 31, '61': 8, '1:N': 3})
```

Ocho relaciones publicaban `61`. YAML lee `1:1` sin comillas como sexagesimal
(1x60+1). Fase RED:

```
$ python -m pytest tests/test_f006_formato.py -q -k "cardinalidad or 61 or valida_entero"
E       ImportError: cannot import name 'CARDINALIDADES' from 'etl_sigrid.domain.diccionario'
FAILED tests/test_f006_formato.py::test_f006_r5_el_vocabulario_de_cardinalidad_es_exactamente_este
FAILED tests/test_f006_formato.py::test_f006_r5_el_61_de_yaml_se_caza_como_cardinalidad_invalida
FAILED tests/test_f006_formato.py::test_f006_r5_una_cardinalidad_vacia_falla
FAILED tests/test_f006_formato.py::test_f006_r5_ninguna_relacion_real_publica_una_cardinalidad_de_yaml
4 failed, 5 passed, 88 deselected in 1.22s
```

**Se corrigen las dos cosas, como pedia el reviewer**: las ocho comillas y el
hueco que las permitio. `CARDINALIDADES = ("1:1", "1:N", "N:1", "N:N")` es ahora
vocabulario cerrado validado en R5, igual que `agregacion` en R7, y **el mensaje
de error dice como se arregla**: «si querias `1:1`, escribelo ENTRE COMILLAS:
YAML lee `1:1` sin comillas como el numero 61». Sin eso el mismo fallo entraria
otra vez en las 73 fichas que faltan.

Verde: `Counter({'N:1': 31, '1:1': 8, '1:N': 3})`.

## Defecto 2 · Cardinalidades que prometen una unicidad que no existe

El reviewer encontro **seis** a mano. En vez de corregir esas seis, se hizo la
comprobacion **derivable**, porque el diccionario ya declara la clave de negocio
de cada objeto: **un lado `1` de la cardinalidad promete que esa columna
identifica una fila**, y eso se puede comprobar solo. Un lado es unico si la
columna es ella sola la `clave_negocio`, o si esta marcada
`agregacion: clave_sustituta` (que se deja fuera de la clave a proposito y aun
asi identifica la fila dentro de un build; sin esa excepcion las relaciones
`1:1` legitimas entre una tabla de hecho y su vista aligerada saldrian marcadas
como falsas).

Fase RED, primero sobre fixtures:

```
$ python -m pytest tests/test_f006_formato.py -q -k "fan_out or unicidad or sustituta or ..."
FAILED tests/test_f006_formato.py::test_f006_r5_un_lado_uno_sobre_una_clave_parcial_es_fan_out
FAILED tests/test_f006_formato.py::test_f006_r5_el_lado_izquierdo_tambien_se_comprueba
2 failed, 5 passed, 96 deselected in 1.01s
```

y despues, con la comprobacion ya implementada, sobre el diccionario real:

```
E         Left contains 10 more items, first extra item: ErrorValidacion(fichero='cierre.yaml', objeto='cierre.fact_cierre_mensual', regla='R5', ...)
```

**Son DIEZ, no seis.** La comprobacion derivada encontro cuatro que la auditoria
manual no vio:

| Relacion | Decia |
|---|---|
| `mart.fact_seguimiento_categoria` -> `mart.fact_seguimiento_mensual.obra_id` | `1:N` |
| `mart.fact_seguimiento_mensual` -> `cierre.fact_cierre_mensual.obra_id` | `N:1` |
| `mart.v_master_vigente_anual` -> `mart.v_master_versiones_tipadas.obra_id` | `N:1` |
| `mart.v_pbi_cp_tipologia` -> `mart.v_master_vigente_anual.obra_id` | `N:1` |

Las diez pasan a `N:N` **y su `porque` dice ahora por que clave hay que agregar
antes de unir**, que es la informacion que de verdad evita el fan-out:
`(obra_id, anio_mes)`, `(obra_id, anio_mes, concepto)`,
`(obra_id, grupo_cod, subcategoria_cod)`, `(obra_id, ambito_id, version)`...

Reparto final: `N:1` 23, `N:N` 10, `1:1` 8, `1:N` 1.

## Defecto 3 · `orden_concepto` declaraba un rango falso

```
$ python -m pytest tests/test_f006_fichas.py -q -k "orden"
tests\test_f006_fichas.py:394: AssertionError
FAILED tests/test_f006_fichas.py::test_f006_r7_cierre_el_orden_del_resumen_declara_sus_valores_reales
FAILED tests/test_f006_fichas.py::test_f006_r7_cierre_el_orden_del_resumen_avisa_del_empate
FAILED tests/test_f006_fichas.py::test_f006_r7_cierre_el_orden_de_la_tabla_base_solo_llega_a_cuatro
FAILED tests/test_f006_fichas.py::test_f006_r7_cierre_el_dim_de_concepto_si_ordena_de_uno_a_seis
4 failed, 57 deselected in 1.17s
```

Verificado en el SQL: `02_build_fact.sql:290-297` da 1, 2, 3 y 4 a los cuatro
conceptos base; `03_views.sql:56` le da **2** a GASTOS y `:85` le da **6** a
BENEFICIO. Valores reales `{1, 2, 2, 3, 4, 6}`: **el 2 repetido y ningun 5**.

Se corrigen **tres fichas y una relacion**, no solo la que senalaba el informe:

- `v_pbi_cierre_resumen.orden_concepto` declara sus cinco valores distintos, dice
  que el 2 lo comparten INDIRECTOS y GASTOS y **manda ordenar por
  `cierre.v_pbi_dim_concepto.orden`**.
- `fact_cierre_mensual.orden_concepto` declara `1..4`: esa tabla solo tiene los
  cuatro conceptos base.
- `v_pbi_dim_concepto.orden` declara `1..6` y dice que es el unico orden fiable.
- La relacion con el dim pasa de «aporta el orden» a «el orden del dim es el
  bueno, no el `orden_concepto` de esta vista».

## Defecto 4 · Los ordenes de magnitud mezclaban dos criterios

```
$ python -m pytest tests/test_f006_reglas.py -q -k "magnitud or retencion_son or fuente_es or recuentos"
tests\test_f006_reglas.py:598: AssertionError
FAILED tests/test_f006_reglas.py::test_f006_r10_cada_orden_de_magnitud_declara_su_criterio
FAILED tests/test_f006_reglas.py::test_f006_r10_las_cifras_de_retencion_son_de_saldo_vivo_y_lo_dicen
FAILED tests/test_f006_reglas.py::test_f006_r10_la_fuente_es_un_documento_que_existe_en_el_repositorio
FAILED tests/test_f006_reglas.py::test_f006_r10_los_recuentos_de_efectos_van_por_sentido
4 failed, 1 passed, 51 deselected in 0.78s
```

Comprobado en la fuente primaria del repositorio, `LEEME_RETENCIONES_R1.md`:
son **«34,7 M€ vivos»** (25.124 efectos) y **«21,9 M€ vivos»** (2.219 efectos).
El bloque decia «total de la empresa» de las dos.

Se corrige mas de lo pedido, porque el problema de fondo era la mezcla de
criterios:

- Cada entrada declara ahora **`criterio: saldo_vivo | total`**, y el propio
  `concepto` dice «VIVO» donde lo es: un campo que solo esta en el YAML no lo
  lee el agente, el texto si.
- La **`fuente` cita el documento del repositorio** que trae la medicion, con la
  condicion exacta (`retide <> 0` y `fecrea = 0`), no la nota de segunda mano
  del prototipo. **Hay un test que comprueba que ese fichero existe**: una
  medicion sin fuente comprobable envejece sin que nadie lo note.
- Los ~27.300 efectos, que eran el unico dato agregado de los dos sentidos, se
  parten en **25.124 de proveedor y 2.219 de cliente**, para que cada importe
  tenga su recuento del mismo lado y se puedan contrastar entre si.
- La cabecera del bloque explica la diferencia entre los dos criterios y por que
  compararlos lleva a dar por malo un numero correcto.

Un fallo del test, no del contenido, se corrigio al implementar: la extraccion
del nombre del fichero miraba `endswith('.md')` **antes** de quitar la coma
final, asi que no encontraba `LEEME_RETENCIONES_R1.md,`.

## Defecto 5 · `cliente_ide` declaraba un nulo que no existe

```
$ python -m pytest tests/test_f006_fichas.py -q -k "nulo or cliente_ide"
E       AssertionError: assert 'La obra no tiene cliente asignado.' is None
FAILED tests/test_f006_fichas.py::test_f006_r2_un_nulo_declarado_en_un_ide_tiene_que_ser_posible[cierre.v_pbi_cierre_cabecera]
FAILED tests/test_f006_fichas.py::test_f006_r2_cliente_ide_avisa_de_que_el_cero_es_el_sin_cliente
2 failed, 18 passed, 61 deselected in 3.31s
```

`sql/cierre/05_views_cabecera.sql:71` proyecta `obr.entide AS cliente_ide` **sin
`NULLIF(..., 0)`**, y es el unico `*_ide` de la vista que no lo lleva. Una obra
sin cliente trae 0, y `WHERE cliente_ide IS NULL` no devuelve nada nunca.

Corregido, y **con la salida buena escrita**: la ficha dice que se filtra
`cliente_ide = 0`, o `cliente_nombre IS NULL`, que ese si es nulo de verdad
—porque el `LEFT JOIN` no encuentra el concepto—. Se le anadio a
`cliente_nombre` su `nulo_significa`, que faltaba.

**Endurecimiento**: hay un test parametrizado sobre todas las vistas que, para
cada columna `*_ide` que declare `nulo_significa`, exige que su proyeccion en el
SQL lleve `NULLIF`. Declarar un nulo imposible manda al agente a escribir un
filtro que siempre sale vacio, y ahora eso no pasa de la puerta.

## Defecto 6 · Una regla mandaba consultar una vista que no existe

```
$ python -m pytest tests/test_f006_reglas.py -q -k "no_citan or tampoco_cita or si_existe_hoy"
E           tica, en `_meta.v_diccionario`). Ojo: `build-compras` y `build-retenciones` no registran paso propio...
tests\test_f006_reglas.py:651: AssertionError
FAILED tests/test_f006_reglas.py::test_f006_r9_las_reglas_no_citan_objetos_que_no_existen
FAILED tests/test_f006_reglas.py::test_f006_r16_frescura_manual_cita_la_vista_que_si_existe_hoy
2 failed, 1 passed, 56 deselected in 0.55s
```

`_meta.v_diccionario` la crea T15, en el bloque E. La regla la citaba en
presente. **Se opta por condicionar el texto**, no por atar el bloque E: la
regla cita ahora solo `_meta.v_frescura`, con el `WHERE paso = ...` incluido
para que la consulta sea ejecutable tal cual. Cuando el bloque E cree la vista,
anadirla a la regla es una linea. La mencion condicionada («cuando exista
`_meta.v_diccionario`») sigue donde correspondia desde el principio: en la nota
de la pregunta P15.

De paso, la regla dice ahora que de `compras` y `retenciones` **hay que advertir
que la antiguedad se desconoce**, en vez de solo constatar que no se puede
consultar.

**Endurecimiento**: dos tests barren el texto de las doce reglas y de las 18
respuestas de la bateria buscando cualquier `esquema.objeto` de los nueve
esquemas y exigen que exista en el inventario. Es la misma clase de defensa que
R11 aplicaba al `ambito`, extendida a la prosa, que es la parte que el agente
lee de verdad.

## Defecto 7 · `R-CLAVE-SUSTITUTA` marcaba como inestable una clave estable

```
$ python -m pytest tests/test_f006_reglas.py -q -k "reconstruye or control_del_detector"
E       AssertionError: ['aux.periodificacion_partida'] no se reconstruyen en ningún build: su clave es estable y la regla miente al meterlos en su ámbito
tests\test_f006_reglas.py:706: AssertionError
1 failed, 1 passed, 59 deselected in 0.46s
```

`sql/mart/04_view_periodificado.sql:14` crea esa tabla con `CREATE TABLE IF NOT
EXISTS` y ningun build la reconstruye: `regla_id` es estable.

Corregido en los dos sitios: sale del ambito de la regla, y **la regla declara
la excepcion explicitamente** en vez de callarla, para que quien lea el listado
de claves BIGSERIAL no la aplique de mas. La ficha de
`mart.v_fact_periodificado.regla_id_aplicada` tambien lo dice.

**Endurecimiento**: un test comprueba que **todo objeto del ambito de esa regla
se reconstruye de verdad**, buscando su `DROP`, su `TRUNCATE` o su
`truncate_table(...)` en el SQL y en los steps. Y lleva su propio test de
control —`mart.fact_seguimiento_mensual` True, `stg.plan_mensual` True (se
trunca desde Python, no desde SQL), `aux.periodificacion_partida` False—, porque
un detector que devolviera siempre `True` haria pasar el test en falso.

## Defecto 8 · `R-IMPORTE-MES` no cubria `cierre`, que es donde ocurrio el bug

```
$ python -m pytest tests/test_f006_reglas.py -q -k "trampa or detector_del_par or columnas_del_cierre"
E       AssertionError: assert 'ejecutado_origen' in 'Para una serie temporal se suma `importe_mes`...'
FAILED tests/test_f006_reglas.py::test_f006_r9_importe_mes_alcanza_a_todo_lo_que_tiene_la_trampa
FAILED tests/test_f006_reglas.py::test_f006_r9_importe_mes_nombra_las_columnas_del_cierre
2 failed, 3 passed, 59 deselected in 1.30s
```

El encargo pedia anadir dos objetos. **Se anaden cuatro**, porque la
comprobacion derivada encontro dos mas con exactamente la misma trampa:
`cierre.v_pbi_cierre_indirectos_detalle` y
`cierre.v_pbi_cierre_generales_detalle` tambien tienen su `ejecutado_mes` y su
`ejecutado_origen`.

El criterio, que no exige auditar nada: **un objeto que documente a la vez una
columna en euros `suma_solo_dentro_del_mes` y otra en euros `ultimo_valor` tiene
por definicion el par parcial/acumulado**, y la regla debe alcanzarlo. El test
lleva su control (que el detector encuentre al menos ocho objetos y en concreto
los dos cabeza de serie), porque un detector que no encontrase nada haria pasar
el test en falso.

El texto de la regla se reescribio para que hable de **la pareja**, no de dos
nombres concretos, y diga que en `cierre` se llaman `ejecutado_mes` y
`ejecutado_origen`: el agente busca por nombre de columna, y `importe_mes` no le
dice nada cuando esta mirando el cierre. El `motivo` explica ahora por que la
regla se redacto mirando a `mart` cuando el bug ocurrio en `cierre`.
