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

## Evidencias (primera entrega, antes de la review)

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

## Defecto 9 · `design.md` senalado y no corregido

```
$ python -m pytest tests/test_f006_fichas.py -q -k "contrato or recuento_real"
FAILED tests/test_f006_fichas.py::test_f006_r2_el_ejemplo_del_contrato_no_usa_nombres_que_no_existen[obra_codigo]
FAILED tests/test_f006_fichas.py::test_f006_r2_el_ejemplo_del_contrato_no_usa_nombres_que_no_existen[partida_codigo]
FAILED tests/test_f006_fichas.py::test_f006_r2_el_ejemplo_del_contrato_no_usa_nombres_que_no_existen[COSTE_REAL]
FAILED tests/test_f006_fichas.py::test_f006_r2_el_ejemplo_del_contrato_no_usa_nombres_que_no_existen[VENTA_PLAN]
FAILED tests/test_f006_fichas.py::test_f006_r2_el_ejemplo_del_contrato_no_usa_nombres_que_no_existen[COSTE_PLAN]
FAILED tests/test_f006_fichas.py::test_f006_r2_el_ejemplo_del_contrato_usa_los_nombres_reales
FAILED tests/test_f006_fichas.py::test_f006_r24_el_diseno_declara_el_recuento_real_de_objetos
7 failed, 81 deselected in 0.55s
```

Corregido en `specs/F-006-mcp-azure/design.md`, con una **nota de enmienda
fechada** al principio de §3 que dice que se cambio y por que —el ejemplo es lo
que copia quien escriba las 73 fichas que faltan—:

- §3.3: `obra_codigo` -> `codigo_obra`, `partida_codigo` -> `codigo_partida`,
  `mes` -> `anio_mes`, los cuatro literales de escenario a
  `Coste Real / Coste Planificado / Venta Real / Venta Planificada`, y la
  relacion a `maestro.obras.obra_id`, que es la columna que esa vista expone.
- El ejemplo **documenta ahora las columnas de su propia clave de negocio**
  (`obra_id`, `partida_id`, `anio_mes`): antes la clave nombraba columnas que la
  ficha de ejemplo no traia, asi que el propio ejemplo no habria pasado el
  validador que el documento especifica.
- §5.1: `mart` **13 objetos (2 + 11 vistas)** y `cierre` **12 (1 + 8 vistas + 3
  funciones)**; §14.1 pasa de «mas de 80 objetos» a **98**.

**Endurecimiento**: tres tests vigilan el documento. Dos se acotan a los bloques
YAML —la prosa puede y debe citar los nombres equivocados para explicar la
enmienda— y el tercero compara el recuento del documento contra el inventario
real, asi que si manana se publica un objeto nuevo, el documento se queda en
rojo hasta que alguien lo actualice.

## Defecto 10 · Las defensas de la puerta

Decision del lider: entra en esta entrega. Las cuatro defensas, con la evidencia
de que cada una caza el experimento que el reviewer hizo pasar en verde.

### (a) Minimos de contenido

Fase RED:

```
$ python -m pytest tests/test_f006_formato.py -q -k "esqueletica or relleno or minimos"
FAILED tests/test_f006_formato.py::test_f006_r2_una_ficha_esqueletica_no_pasa[descripcion-x]
FAILED tests/test_f006_formato.py::test_f006_r2_una_ficha_esqueletica_no_pasa[grano-x]
FAILED tests/test_f006_formato.py::test_f006_r3_un_motivo_no_consumo_de_relleno_no_pasa
FAILED tests/test_f006_formato.py::test_f006_r6_un_significado_de_relleno_no_pasa
FAILED tests/test_f006_formato.py::test_f006_r40_un_ejemplo_de_pregunta_de_relleno_no_pasa
5 failed, 1 passed, 103 deselected in 1.06s
```

`MINIMOS_TEXTO` en el dominio: `descripcion >= 40`, `grano >= 20`,
`motivo_no_consumo >= 30`, `significado >= 15`, cada `ejemplos_preguntas >= 20`.
Los numeros no son arbitrarios: son los que **ya se exigian en el bloque global
desde el principio**, extendidos a las fichas, que es donde esta el volumen.
Medir caracteres no garantiza que el texto sea bueno; garantiza que alguien se
ha parado a escribirlo, que es todo lo que un test puede comprobar. El mensaje
de error distingue «falta» de «esta de relleno», porque se arreglan distinto.

De las 25 fichas entregadas, **cuatro textos** no llegaban: `grano` de
`v_pbi_dim_fecha` y tres `significado` de `anio`/`mes`. Se reescribieron; no se
bajo ningun umbral.

### (b) y (c) Las vistas, tan exactas como las tablas

Los dos huecos eran de vistas, y se cerraron leyendo **la proyeccion del
`SELECT` final de cada vista concreta**, sin comentarios (mas un caso propio
para los catalogos `SELECT * FROM (VALUES ...) AS t(a, b, c)`). Las **19 vistas
documentadas se parsean**, y hay un test de control que lo exige: si algun dia
una deja de parsearse, se pone en rojo en vez de dejar de comprobar en silencio.

Evidencia, reproduciendo los dos experimentos de la review a la vez —borrar
`can_mes` de `mart.v_pbi_fact` y colarle `obra_label`, que es de otra vista del
mismo fichero—:

```
=== EL TEST VIEJO (busca en el fichero entero) ===
22 passed in 3.52s
=== EL TEST NUEVO (proyeccion de la vista) ===
E       AssertionError: faltan: ['can_mes']; sobran: ['obra_label']
FAILED tests/test_f006_fichas.py::test_f006_r26_las_vistas_documentan_exactamente_su_proyeccion[mart.v_pbi_fact]
1 failed, 18 passed in 3.09s
```

**El contraste generico viejo se retira**, no se deja al lado: quedaba subsumido
por las dos comprobaciones exactas y un test debil que da falsa confianza es
peor que ninguno. En su lugar queda un meta-test que exige que **toda ficha con
columnas este cubierta por una comprobacion exacta**, para que el hueco no
vuelva por la puerta de atras.

### (d) El trinquete, anclado a algo que no es la linea que se edita

Dos anclajes:

- **Al inventario**: `pendientes` tiene que ser EXACTAMENTE lo que falta por
  documentar. Inflar el trinquete exige ahora borrar una ficha.
- **Al historial de git** del propio fichero: cada revision tiene que caber en
  la anterior, **empezando por el arbol de trabajo**. Un objeto que ya tuvo
  ficha no puede volver a `pendientes`.

Reproduciendo el experimento del reviewer —desdocumentar
`mart.v_pbi_dim_escenario`, devolverlo a `pendientes` y subir el tope a 74—:

```
=== LOS DOS TESTS QUE YA HABIA ===
3 passed, 41 deselected in 0.84s          <- pasaba en verde
=== LA DEFENSA NUEVA ===
E           assert not ['mart.v_pbi_dim_escenario']
FAILED tests/test_f006_cobertura.py::test_f006_r27_el_trinquete_solo_baja_a_lo_largo_del_historial
```

**Un fallo propio, encontrado por el experimento y no por el test**: la primera
version comparaba solo commits ya hechos entre si y **dejaba pasar el arbol de
trabajo**, es decir, exactamente lo que venia a impedir. Se corrigio metiendo el
arbol de trabajo como primer eslabon de la cadena, y queda escrito en el propio
codigo para que nadie lo quite creyendo que sobra.

### (e) Retirada la promesa de `check-diccionario`

Se cita en cuatro sitios como la defensa que cubre lo que la puerta offline no
ve, y **no existe**. Los cuatro textos dicen ahora que es R28, que llega en el
bloque H y que **mientras tanto no hay red de seguridad detras**; y dicen
tambien lo que la puerta SI garantiza hoy, que despues de (b) y (c) es bastante
mas que antes.

El test que rozaba la circularidad —comprobaba que la cadena
`check-diccionario` estuviera escrita en el docstring, o sea, verificaba la
promesa— se sustituye por uno que comprueba **un hecho sobre `main.py`**: que el
comando no exista mientras los docstrings lo den por futuro. El dia que alguien
implemente R28, ese test se pone en rojo y obliga a corregir los textos.

## Hallazgos menores de la review (1 a 6), tambien corregidos

No bloqueaban, pero son texto que un agente lee para decidir y estaba
equivocado. Fase RED:

```
$ python -m pytest tests/test_f006_fichas.py -q -k "fila_anterior or final_anterior_es_cero or periodificacion_no_anula or dos_plazos or catalogos_estaticos"
FAILED tests/test_f006_fichas.py::test_f006_r2_el_anterior_es_la_fila_anterior_no_el_mes_anterior
FAILED tests/test_f006_fichas.py::test_f006_r2_final_anterior_es_cero_y_no_nulo_cuando_no_hubo_prevision
FAILED tests/test_f006_fichas.py::test_f006_r2_la_periodificacion_no_anula_todas_sus_columnas
FAILED tests/test_f006_fichas.py::test_f006_r2_los_dos_plazos_se_advierten_entre_si
FAILED tests/test_f006_fichas.py::test_f006_r2_los_catalogos_estaticos_no_se_contradicen_con_su_refresco
5 failed, 89 deselected in 1.27s
```

| # | Corregido |
|---|---|
| 1 | Fuera de INFRA no son nulas «todas las columnas de periodificacion»: **`importe_fase0` y `plazo_total_meses` traen valor siempre**, porque son las ENTRADAS del calculo, no su resultado. Corregido en el `grano`, en `es_infraestructura` y en las dos columnas |
| 2 | `final_anterior` vale **0, no nulo**, cuando no hubo prevision: el importe del que se copia es un `COALESCE(..., 0)`. Solo es nulo en la PRIMERA fila de la particion. Buscar «sin prevision anterior» con `IS NULL` perdia todas esas filas |
| 3 | «al cierre del mes anterior» significa **la fila anterior**, no el mes de calendario anterior: el `LAG` salta los meses sin fase. Corregido en las **cuatro** fichas que usaban la frase |
| 4 | `v_pbi_cierre_cabecera.plazo_meses` y `v_pbi_cierre_indirectos_detalle.plazo_total_meses` **dan numeros distintos para la misma obra**. Ahora cada una advierte de la otra por su nombre |
| 5 | `final_pct` no era «la unica excepcion del cuadro»: en la fila VENTA los cinco porcentajes cambian de divisor. Lo propio de `final_pct` es que su divisor sale **de otra vista** |
| 6 | «catalogo ESTATICO» junto a `refresco: manual` se leia como un error. Las dos cosas son ciertas —el contenido esta escrito en la vista y la vista se recrea con `build-cierre`— y ahora la ficha lo dice, en vez de dejar al lector resolviendo la aparente contradiccion |

El hallazgo 7 —tres comentarios del SQL que mienten: el tope del `ratio_lineal`,
un fallback inexistente y un JOIN muerto con `raw.cen`— **se anota y no se
toca**: es deuda del SQL de negocio, y la regla de hierro 3 de `tasks.md` dice
que no se arregla aqui. Candidato a una feature de limpieza, y conviene, porque
engañaran a quien lea el SQL creyendo que el YAML es el que se equivoca.

---

## Evidencias tras la review

Numeros medidos de nuevo, no arrastrados de la entrega anterior.

| Evidencia | Antes de la review | Ahora |
|---|---|---|
| **Tests que pasan** | 1052 | **1133** (340 de F-006) |
| **Tests que fallan** | 0 | **0** |
| **Tiempo de la suite** | 16,9 s | **25,6 s** sin cobertura; ~76 s dentro de `init.sh` |
| **Cobertura de las lineas cambiadas** | 98,8 % (493/499) | **98,7 % (550/557)**, umbral 80 %, nivel `critico` |
| **Mutantes / supervivientes** | 112 / 0 | **132 / 0**, 0 timeouts, 352,3 s (recontada tras los arrastres) |
| **Objetos documentados** | 25 de 98 | 25 de 98 |
| **Columnas descritas** | 332 | 332, ahora **exactas contra la proyeccion de cada vista** |
| **Relaciones publicadas** | 42, con 8 rotas y 10 mintiendo | **42, las 42 validadas**: vocabulario cerrado y unicidad derivada de la clave |
| **Trinquete `pendientes`** | 73, editable | 73, **anclado al inventario y al historial de git** |

**Analisis de supervivientes: no hay ninguno.** 132 mutantes sobre los tres
modulos nuevos, todos muertos. Detalle en `progress/mutacion_F-006.md`.

### Los diez defectos, y lo que se encontro de mas al arreglarlos

En cinco de los diez, corregir el caso concreto habria dejado el mecanismo
intacto. Se corrigio el mecanismo, y el mecanismo encontro mas casos:

| Defecto | Pedido | Encontrado y corregido |
|---|---|---|
| 1 · `cardinalidad: 61` | 8 comillas | 8 comillas **+ vocabulario cerrado validado**, con el mensaje que explica el caso del 61 |
| 2 · fan-out | 6 relaciones | **10**, por comprobacion derivada de la clave de negocio |
| 3 · `orden_concepto` | 1 ficha | **3 fichas y una relacion** |
| 4 · ordenes de magnitud | anadir «vivos» | `criterio` explicito, fuente **comprobada por un test** y recuentos por sentido |
| 8 · `R-IMPORTE-MES` | 2 objetos al ambito | **4**, por el mismo criterio derivado |

Los cinco restantes (5, 6, 7, 9, 10) se corrigieron como pedia el informe, cada
uno con su test y, donde era derivable, con la comprobacion que impide que
vuelva a pasar en las 73 fichas que faltan.

### Que sigue sin cubrir la puerta, dicho sin adornos

- Un objeto que exista en la base y **no** en el repositorio. Lo dira
  `check-diccionario` (R28, bloque H), que **no existe todavia**, y los cuatro
  docstrings que antes lo daban por cubierto ahora dicen exactamente eso.
- Que el TEXTO de una ficha sea cierto. Los minimos garantizan que alguien lo
  escribio; que diga la verdad la garantizan la revision humana y la bateria de
  aceptacion (T39). **Ver la seccion siguiente, que lo desglosa sin adornos.**

---

# Correcciones tras el APROBADO (arrastres del propio informe)

Cuatro cosas que el informe anterior dejaba «para antes de que el bloque E
publique». Se cierran ahora: son mentiras en fichas, y el bloque E las
publicaria a `_meta` tal cual.

## Arrastre 1 y 2 · Dos claves de JOIN citadas y no existentes

Las dos las introdujo **mi propia correccion del fan-out**, al anadir a cada
`porque` la clave por la que hay que agregar antes de unir. Antes de tocar nada
se busco el patron en **las 42 relaciones**, no solo en la senalada:

```
$ python - <<'EOF'   (barrido de todas las tuplas `(a, b, c)` de los `porque`)
cierre.v_pbi_planif_vs_real -> mart.fact_seguimiento_categoria.obra_id: ['categoria'] NO son columnas de cierre.v_pbi_planif_vs_real
mart.v_pbi_cp_tipologia   -> mart.v_master_vigente_anual.obra_id:      ['ambito_id'] NO son columnas de mart.v_pbi_cp_tipologia
```

**Son exactamente dos**, las dos que senalo el reviewer. Fase RED:

```
$ python -m pytest tests/test_f006_formato.py -q -k "clave_de_join or sin_columnas_no_se_juzga"
FAILED tests/test_f006_formato.py::test_f006_r5_una_clave_de_join_inventada_en_el_porque_falla
FAILED tests/test_f006_formato.py::test_f006_r5_una_ficha_sin_columnas_no_se_juzga
2 failed, 2 passed, 109 deselected in 1.17s
```

- **`cierre.v_pbi_planif_vs_real`**: la vista **ya colapso** la `categoria` del
  origen dentro de `concepto_cuadro`, y ademas **tres de sus seis renglones no
  corresponden a ninguna categoria** (PRODUCCION es la venta entera; TOTAL
  COSTES y BENEFICIO son sumas). La ficha lo dice asi ahora, en vez de dar una
  clave que no se puede escribir.
- **`mart.v_pbi_cp_tipologia`**: `ambito_id` no es dimension de esa union.
  `sql/mart/06_views_cp_tipologia.sql:231` fija `va.ambito_id = 8` como **filtro
  constante** sobre el destino, y la vista ni siquiera proyecta la columna. El
  JOIN va por `(obra_id, anio)`, y la ficha explica el filtro.

**Endurecimiento**: R5 comprueba ahora que toda columna citada como clave de
JOIN dentro de un `porque` sea una columna documentada de la propia ficha. El
`porque` es lo que un agente copia para escribir el JOIN, asi que sus nombres
son tan verificables como los de `de` y `a`. Si hace falta nombrar la clave del
otro extremo, se escribe cualificada y el patron no la reclama.

## Arrastre 3 · `final_pct` se contaba dentro de la excepcion de la que se excluye

```
$ python -m pytest tests/test_f006_fichas.py -q -k "final_pct or variacion_pct or reparto_de_divisores"
tests\test_f006_fichas.py:773: AssertionError
FAILED tests/test_f006_fichas.py::test_f006_r2_final_pct_dice_cuantos_porcentajes_cambian_y_cuales
1 failed, 2 passed, 94 deselected in 0.95s
```

El texto decia «en la fila VENTA los cinco porcentajes usan un divisor propio,
la venta final», y `final_pct` es precisamente el que NO usa la venta final.
Contado contra `sql/cierre/03_views.sql`, el reparto real de la fila VENTA es:
**cuatro** porcentajes cambian su divisor a la venta final, **`final_pct`** lo
cambia al presupuesto aprobado —que ademas sale de otra vista— y
**`variacion_pct` no cambia nada**, porque su divisor es siempre la prevision
anterior, sin mirar el concepto.

La ficha da ahora el mapa entero. Y hay un **test de control contra el SQL**:
cuenta los cinco `WHEN t.concepto = 'VENTA' THEN` de la vista, asi que si manana
alguien anade o quita una excepcion, la ficha se pone en rojo en vez de quedarse
mintiendo en silencio.

## Arrastre 4 · Seis residuos de «mes anterior»

```
$ python -m pytest tests/test_f006_fichas.py -q -k "residuo"
tests\test_f006_fichas.py:824: AssertionError
1 failed, 97 deselected in 0.51s
```

Los seis estaban en `variacion_importe` (dos fichas, significado y nulo),
`ejecutado_anterior_pct` y `variacion_pct`. Todos pasan a **«la fila anterior de
esa obra y ese concepto»**, que es lo que hace el `LAG`. La diferencia no es de
estilo: en una obra que no cerro marzo, «el mes anterior» de abril es febrero, y
quien reste un mes de calendario para reproducir la cifra no la reproduce.

Queda **una sola** mencion a «mes anterior» en el fichero, y es correcta: la de
`ejecutado_mes_periodif`, que describe contra que resta el SQL el incurrido. El
test la excluye por nombre y explica por que.

---

## Que comprueba la puerta y que NO, sin sobrevender

La version anterior de este informe decia que quedaban cubiertos «nombres de
columna, granos declarados, claves de negocio, cardinalidades...». **Es falso de
tres de esos cinco** y el reviewer tenia razon en senalarlo: un informe que
promete de mas es el mismo problema que una ficha que miente, solo que apuntando
hacia dentro. Lo que hay, exactamente:

### Se comprueba (falla la puerta)

| Qué | Cómo |
|---|---|
| Que todo objeto publicado tenga ficha, o este declarado en `pendientes` | inventario de `sql/**` + `tables_sigrid.yaml` |
| Que `pendientes` no crezca ni recupere un objeto ya documentado | anclado al inventario y al historial de git, arbol de trabajo incluido |
| Que las columnas documentadas de una **tabla** sean EXACTAMENTE las de su `CREATE TABLE` | parseo del DDL |
| Que las de una **vista** sean EXACTAMENTE las de su proyeccion final | lectura del `SELECT` de esa vista, sin comentarios |
| Que `tipo`, `capa`, `refresco`, `agregacion`, `cardinalidad` y `severidad` esten en su vocabulario cerrado | R2, R7, R5, R9 |
| Que las dos puntas de cada relacion existan, objeto y columna | R5, en cuanto el destino tiene ficha |
| Que la cardinalidad no prometa una unicidad que la clave declarada no da | derivado de `clave_negocio` |
| Que la clave de JOIN citada en un `porque` nombre columnas de la ficha | R5 |
| Que las columnas de `clave_negocio` **existan** en la ficha | R2 |
| Que `refresco` no mienta sobre el pipeline real | R14, leyendo `build_pipeline_steps` |
| Que un `nulo_significa` en un `*_ide` tenga su `NULLIF` en el SQL | contraste con la proyeccion |
| Que las doce reglas esten, con ambito resoluble, y que su prosa no cite objetos inexistentes | R9, R11 |
| Que ningun texto este de relleno | `MINIMOS_TEXTO` |

### NO se comprueba (pasa en verde)

Comprobado por mi, no supuesto. Reduje `clave_negocio` de
`mart.fact_seguimiento_mensual` a `[obra_id]` y cambie su `grano` a «una fila
por obra y mes, con el importe total de la obra en ese mes»:

```
$ python -m pytest tests/ -q -k f006
335 passed, 798 deselected in 21.42s
```

- **Que el `grano` sea cierto.** Es texto libre y nada lo contrasta.
- **Que `clave_negocio` sea la clave de verdad.** Solo se exige que sus columnas
  existan. Y hay un efecto de segundo orden que conviene ver: **la comprobacion
  de fan-out DERIVA la unicidad de la clave declarada**, asi que una clave
  reducida no solo pasa desapercibida, sino que **desarma esa comprobacion** y
  deja valida una cardinalidad `N:1` que antes se cazaba. Es la limitacion que
  mas vigilancia pide en las 73 fichas restantes.
- **Que el `significado` de una columna sea cierto.** El caso limite sigue
  siendo el de la review: `importe_mes` descrito como «importe ACUMULADO desde
  el inicio», que es la trampa numero uno del datamart escrita al reves. La
  `agregacion` sigue siendo `suma_solo_dentro_del_mes` y nadie cruza las dos
  cosas.
- **Un objeto que exista en la base y no en el repositorio.** Es
  `check-diccionario` (R28, bloque H), que no existe todavia.

Las tres primeras solo las cazan hoy **la revision humana y la bateria de
aceptacion** (T39), y por eso cuatro de sus dieciocho preguntas son trampas
deliberadas sobre exactamente estos puntos. Queda escrito aqui, y no descubierto
dentro de 73 fichas.

---

# Bloque E · La publicacion en `_meta` (el contrato con `mcp-bbdd`)

## T15 · El DDL del contrato

```
$ python -m pytest tests/test_f006_publicacion.py -q
FAILED tests/test_f006_publicacion.py::test_f006_r22_ddl_el_contrato_de_columnas_es_exacto[_meta.diccionario-columnas0]
FAILED tests/test_f006_publicacion.py::test_f006_r22_ddl_el_contrato_de_columnas_es_exacto[_meta.diccionario_reglas-columnas1]
FAILED tests/test_f006_publicacion.py::test_f006_r22_ddl_el_contrato_de_columnas_es_exacto[_meta.diccionario_publicacion-columnas2]
FAILED tests/test_f006_publicacion.py::test_f006_r22_ddl_los_tipos_del_contrato_no_se_improvisan
FAILED tests/test_f006_publicacion.py::test_f006_r22_ddl_publicado_en_es_timestamp_sin_zona
FAILED tests/test_f006_publicacion.py::test_f006_r15_ddl_la_vista_expone_significado_y_frescura_de_una_vez
FAILED tests/test_f006_publicacion.py::test_f006_r23_ddl_advierte_de_lo_que_cuesta_cambiar_la_vista
15 failed in 1.09s
```

`sql/ddl/01_diccionario.sql`: las tres tablas y `_meta.v_diccionario`, con el
contrato de `design.md` §4.1 **columna a columna**, comprobado con el mismo
parser de DDL que valida las fichas. Los tests son deliberadamente literales:
`mcp-bbdd` va a programar contra esto sin poder preguntar.

Lo que queda blindado por un test, no por buena voluntad:

- **Ni un `DROP` ni un `TRUNCATE` en todo el fichero.** Un `DROP` se lleva los
  `GRANT` y dejaria al MCP ciego hasta el `apply-grants` siguiente. El test mira
  el VERBO de cada sentencia, no el texto, porque la cabecera menciona
  `DROP VIEW` a proposito para advertir de lo que cuesta.
- **Los dos JOIN de la vista son LEFT**, y cada uno por su motivo, escrito en el
  fichero: el de `v_frescura` para que un objeto cuyo paso nunca termino bien
  siga saliendo, y el de `diccionario_publicacion` porque un `CROSS JOIN` con la
  tabla vacia devolveria cero filas y la vista mentiria diciendo que no hay
  diccionario.
- **`publicado_en` es `TIMESTAMP` sin zona** y no hay ni un `TIMESTAMPTZ`:
  mezclarlos haria incomparables la fecha del diccionario y la de `v_frescura`,
  que es justo lo que la vista cruza.
- **El singleton**: `id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1)`.

### El trinquete SUBE de 73 a 77, y por que eso esta bien

El DDL anade cuatro objetos NUEVOS al repositorio, asi que el inventario pasa de
98 a **102** y `pendientes` de 73 a 77. La comparacion cruda de listas entre
commits lo daba por regresion:

```
$ python -m pytest tests/test_f006_cobertura.py -q
FAILED tests/test_f006_cobertura.py::test_f006_r27_el_trinquete_solo_baja_a_lo_largo_del_historial
FAILED tests/test_f006_cobertura.py::test_f006_r27_el_trinquete_de_hoy_cabe_en_el_de_la_primera_revision
2 failed, 43 passed in 1.76s
```

**Era el test el que estaba mal planteado, no el cambio.** Lo que hay que
prohibir no es que la lista crezca —el repositorio publica cosas nuevas— sino
que **un objeto que YA tuvo ficha vuelva a la lista de deberes**. El trinquete
se reescribe asi: se barre el historial de git de los ficheros de esquema, se
reune todo lo que alguna vez tuvo ficha, y se exige que la interseccion con
`pendientes` sea vacia. Con su test de control, para que un barrido que
devolviera un conjunto vacio no lo haga pasar en falso.

Las fichas de esos cuatro objetos van en T24, con el resto de `_meta`.
`design.md` §5.1 queda actualizado: `_meta.yaml` pasa de 6 a **7 objetos**.

## T16 · Los constructores puros y los dos metodos del cliente

```
$ python -m pytest tests/test_f006_publicacion.py -q
FAILED tests/test_f006_publicacion.py::test_f006_r22_filas_la_ficha_jsonb_es_determinista_y_completa
FAILED tests/test_f006_publicacion.py::test_f006_r22_filas_el_jsonb_no_arrastra_claves_vacias
FAILED tests/test_f006_publicacion.py::test_f006_r9_filas_de_reglas_van_las_doce_en_su_orden
FAILED tests/test_f006_publicacion.py::test_f006_r22_fila_de_publicacion_lleva_los_recuentos_reales
FAILED tests/test_f006_publicacion.py::test_f006_r22_la_cobertura_publicada_baja_si_falta_un_significado
9 failed, 15 passed in 0.62s
...
$ (tras los constructores, la tanda del cliente)
FAILED tests/test_f006_publicacion.py::test_f006_r17_publicar_escribe_las_tres_tablas
FAILED tests/test_f006_publicacion.py::test_f006_r18_publicar_va_en_UNA_sola_transaccion
FAILED tests/test_f006_publicacion.py::test_f006_r18_publicar_no_hace_drop_ni_truncate
FAILED tests/test_f006_publicacion.py::test_f006_r18_publicar_borra_antes_de_insertar
FAILED tests/test_f006_publicacion.py::test_f006_r17_publicar_manda_las_filas_reales_no_un_ejemplo
FAILED tests/test_f006_publicacion.py::test_f006_r22_publicar_registra_la_version_y_el_hash
FAILED tests/test_f006_publicacion.py::test_f006_r28_list_objetos_catalogo_pregunta_por_los_esquemas_pedidos
7 failed, 24 passed in 3.25s
```

`diccionario_sql.py` sigue el patron de `grants.py`: **no toca ninguna
conexion**, solo produce texto SQL y tuplas. Y
`PostgresClient.publicar_diccionario` mete los tres `DELETE`, los dos
`executemany` y el `INSERT` de publicacion **dentro de un solo `with
self.connection()`**, que es una sola transaccion.

**Todo se prueba con las 25 fichas reales, no con un ejemplo de juguete**, como
pedia el encargo. Salida real del doble:

```
[info] diccionario_publicado  filas=38 hash_fuente=a1656adbc71d objetos=25 reglas=12 version=1
```

38 filas = 25 fichas + 12 reglas + 1 publicacion. Los recuentos que se publican
son **25 objetos, 12 reglas, 332 columnas, cobertura 100,00 %**.

Cuatro decisiones que merecen quedar escritas:

- **El JSONB omite las claves sin valor.** Publicar `"unidad": null` en cada una
  de las 332 columnas es ruido que el consumidor tendria que filtrar. Hay un
  test que lo exige.
- **`sort_keys=True` pero las listas conservan su orden.** El orden de las
  columnas del YAML es editorial —primero las claves, luego los importes— y el
  MCP lo sirve tal cual; lo que se ordena son las claves de cada objeto, para
  que dos publicaciones del mismo YAML den el mismo texto y un `diff` sobre la
  tabla sea legible.
- **Las filas salen ordenadas** por `esquema.objeto` y las reglas por su
  `orden`: sin eso, dos publicaciones del mismo diccionario escribirian lo mismo
  en distinto orden y comparar entornos seria ruido.
- **`list_objetos_catalogo` incluye las FUNCIONES**, no solo tablas y vistas: el
  diccionario documenta doce funciones y `check-diccionario` tiene que verlas.

**Ningun test abre conexion**: el doble registra un diario de llamadas y sobre
el se comprueba que hay UNA transaccion, que el `DELETE` precede al `INSERT` y
que no aparece ni un `DROP` ni un `TRUNCATE`.

## T17 · El paso y su sitio en el pipeline

```
$ python -m pytest tests/test_f006_publicacion.py -q
FAILED tests/test_f006_publicacion.py::test_f006_r20_pipeline_publicar_va_entre_build_mart_y_apply_grants
FAILED tests/test_f006_publicacion.py::test_f006_r14_pipeline_los_pasos_nocturnos_se_inyectan_desde_la_composicion
FAILED tests/test_f006_publicacion.py::test_f006_r17_paso_publica_el_diccionario_real_y_lo_cuenta
FAILED tests/test_f006_publicacion.py::test_f006_r19_paso_con_diccionario_invalido_no_escribe_nada
FAILED tests/test_f006_publicacion.py::test_f006_r19_paso_con_yaml_ilegible_da_failed_legible
FAILED tests/test_f006_publicacion.py::test_f006_r21_paso_si_la_base_falla_no_deshace_el_build
FAILED tests/test_f006_publicacion.py::test_f006_r25_paso_con_cobertura_rota_no_publica
7 failed, 31 passed in 5.78s
```

El pipeline queda: `ingest_raw -> load_excel_aux -> build_stg -> build_mart ->
**publicar_diccionario** -> apply_grants`. El orden esta comprobado dos veces:
por la lista y por el orden topologico que resuelve el orquestador.

**R19 tiene un espia por cliente**, no una comprobacion de buena fe: el doble
lanza `AssertionError` si alguien le pide una conexion, y los tests de
diccionario invalido, YAML ilegible y cobertura rota exigen que **la lista de
llamadas quede vacia**. Publicar un diccionario a medias dejaria al MCP
inventandose significados; que se quede el de ayer es mucho mejor.

### `pasos_nocturnos` sin lista copiada, y sin default peligroso

El paso EXIGE `pasos_nocturnos` en el constructor, sin valor por defecto, y
`build_pipeline_steps` **lo inyecta despues de componer la lista**: es la unica
forma de que salga de la propia composicion, porque cuando el paso se construye
todavia se esta construyendo el pipeline que lo contiene. Un default vacio
habria hecho que R14 diera por mentirosa cualquier ficha `nocturno`; uno con la
lista escrita a mano se habria desincronizado a la primera.

### Tres efectos colaterales que hubo que atender

1. **`run-all` reusa su cliente.** `build_pipeline_steps` acepta ahora el `pg`
   ya abierto y se lo pasa al paso, en vez de que este abra una segunda
   conexion contra un servidor que es compartido.
2. **El doble `PgFalso` de F-024** no sabia responder a `execute_sql_file` ni a
   `publicar_diccionario`. Se le anaden como no-op, con el comentario de por
   que: alli se prueba la propagacion del `batch_id`, no la publicacion.
3. **Dos tests ajenos afirmaban «cinco pasos»** y ahora son seis. Se actualizan
   con el motivo escrito en el propio mensaje del assert, para que quien lo lea
   dentro de un ano sepa que cambio y por que.

`bash harness/init.sh`: **1171 tests**, cobertura de lineas cambiadas **98,9 %**.

## T18 · El comando `python main.py publicar-diccionario`

```
$ python -m pytest tests/test_f006_publicacion.py -q -k cli
FAILED tests/test_f006_publicacion.py::test_f006_r17_cli_el_comando_publica_y_sale_con_cero
FAILED tests/test_f006_publicacion.py::test_f006_r24_cli_marca_huerfanas_antes_de_escribir
FAILED tests/test_f006_publicacion.py::test_f006_r17_cli_registra_el_paso_en_meta
FAILED tests/test_f006_publicacion.py::test_f006_r21_cli_si_falla_sale_con_uno
FAILED tests/test_f006_publicacion.py::test_f006_r14_cli_usa_los_pasos_nocturnos_del_pipeline_real
5 failed, 40 deselected in 1.10s
```

Por los helpers de F-024, como el resto de comandos que escriben: marca las
huerfanas antes de actuar, registra el paso en `_meta.etl_runs` y sale con 1 si
falla. Probado con `CliRunner` y un doble; **ninguna conexion real**.

Dos cosas que no eran obvias y quedan cerradas por un test:

- **El comando suelto valida con el MISMO criterio que la noche**: los pasos
  nocturnos salen de `build_pipeline_steps`, no de una lista escrita en el
  comando. Si usara otra, un diccionario podria publicarse a mano y que
  `run-all` lo rechazase despues, que es peor que rechazarlo ya.
- **DA-1 comprobada por inspeccion del propio `main.py`**: los cuatro builds
  manuales (`build-cierre`, `build-compras`, `build-maestros`,
  `build-retenciones`) NO republican. El diccionario no depende de los datos.

`CLAUDE.md` lista ahora el comando y documenta `config/diccionario/` en el mapa
del repositorio, con la regla de que quien anade un objeto actualiza su ficha en
el mismo trabajo.

## T19 · PENDIENTE, verificacion `MANUAL (humano)`

**No se ha ejecutado y no se puede ejecutar desde aqui**: exige conexion a
`psql-albaranes-rs9k2`, el servidor compartido con `albaranes` y `partes` en
produccion. Queda para el humano, con estos comandos exactos:

```bash
python main.py publicar-diccionario
```

y despues, con `psql`:

```sql
SELECT esquema, objeto, refresco, avisos FROM _meta.diccionario ORDER BY 1, 2;
SELECT * FROM _meta.diccionario_publicacion;
SELECT objeto, ultimo_ok_finished_at FROM _meta.v_diccionario WHERE esquema = 'cierre';
```

Lo que hay que comprobar en esa salida, mas alla de que no reviente:

1. **una fila por ficha en `_meta.diccionario`** —hoy **49**— y **12 en
   `_meta.diccionario_reglas`**. El paso imprime los recuentos, y son los que
   hay que comparar: cualquier cifra escrita aquí envejece a la siguiente tanda
   de fichas;
2. `hash_fuente` **coincide** con el que imprime el paso, o el diccionario
   publicado no es el del repositorio;
3. las filas de `cierre` traen `ultimo_ok_finished_at` **de `build_cierre`**, y
   las de `compras` y `retenciones` lo traeran **a NULO** cuando se documenten,
   porque esos dos comandos no registran paso: es el limite conocido, no un
   fallo de la vista;
4. `avisos` NO esta vacio en `mart.fact_seguimiento_mensual`: si lo estuviera,
   la derivacion de R12 no habria llegado a la base.

Lo unico que este puesto puede garantizar es que el mecanismo traga **el
contenido real**: los tests publican las 25 fichas de verdad contra un doble y
cuentan 38 filas, 332 columnas y cobertura 100 %.

---

# Bloque F parcial · Fichas de `compras` y `retenciones`

Fase RED, la puerta con los 24 objetos fuera de `pendientes`:

```
$ python -m pytest tests/test_f006_cobertura.py -q -k puerta
tests\test_f006_cobertura.py:500: AssertionError
FAILED tests/test_f006_cobertura.py::test_f006_r25_puerta_todo_objeto_publicado_tiene_ficha_o_esta_pendiente
1 failed, 10 passed, 34 deselected in 0.81s
```

**14 fichas de `compras` y 10 de `retenciones`**, con sus 261 columnas nuevas.
El diccionario pasa de 25 a **49 objetos y 593 columnas**, y el trinquete de 77
a **53**.

## Lo que hubo que ampliar en la puerta antes de escribir nada

Las siete tablas de `compras` y las dos de `retenciones` **no tienen lista de
columnas en su DDL**: se crean con `CREATE TABLE ... AS SELECT`. El parser de
DDL no las ve y el contraste de vistas tampoco las miraba, asi que habrian
entrado 155 columnas sin comprobar ni una.

La solucion resulto obvia una vez vista: **una tabla creada con `AS SELECT`
tiene una proyeccion, exactamente igual que una vista**, asi que se lee con el
mismo mecanismo. Las 46 fichas con columnas se contrastan ahora una a una,
tabla o vista, y el meta-test exige que ninguna quede sin cubrir.

**La unica excepcion, y se declara**: `retenciones.v_src_lineas_compra` y
`v_src_lineas_venta` se crean con SQL DINAMICO dentro de un `DO $$`, segun
exista o no la tabla de origen en `raw`. Su `SELECT` va dentro de una cadena y
ningun parser razonable lo alcanza. Sus dos columnas las comprueba un test
escrito a mano, que ademas exige que las **dos variantes** —la real y la
vacia— sigan estando en el SQL.

## Las trampas, cada una con su test contra el SQL

| Trampa | Como queda cerrada |
|---|---|
| **`linea_id` NO es unico** en `fact_compras_linea` | `clave_negocio: [tipo_doc, linea_id]`, la columna lo dice, y un test comprueba que la tabla **sigue sin PK declarada**: el dia que se la pongan, la ficha hay que reescribirla |
| **Los abonos ya vienen en negativo** | Dicho en la ficha y contrastado contra el «signo natural» del propio SQL |
| **Importes SIN IVA** | Exigido en las cuatro fichas de consumo, y ademas que digan **contra que NO se comparan**: `maestro.proveedores_obra.importe_contratado` lleva IVA |
| **NUNCA unir un efecto a las lineas de su factura** | En el `grano` de `movimientos`, con los 38,9 M€, y en el `porque` de la relacion hacia `compras.facturas`, que dice explicitamente que no se siga hasta `factura_lineas` |
| **La cascada de atribucion a obra** | `cenide` primero (~98 % en Ruesma), luego las lineas del documento **solo si todas apuntan a la misma obra**; y `num_obras_documento > 1` con obra nula explicado en el `nulo_significa` |
| **Las dos lecturas del saldo** | `saldo_vivo` marcada como LA DE POR DEFECTO y `neto_practicado` diciendo que **NO es lo mismo**; exigido en las dos vistas que las exponen |
| **No filtran por `stg.obras`** | Dicho en las fichas, con la palabra «administrativas» |
| **`v_src_lineas_venta` esta SIEMPRE vacia** | En su descripcion, con el motivo (`dvfpro` no se ingiere) y `consumo_recomendado: false` |

## Tres correcciones que aparecieron al escribir

1. **El aviso de frescura no llegaba al agente.** La advertencia de que
   `build-compras` y `build-retenciones` no registran paso estaba en la
   **cabecera del YAML**, y los comentarios del fichero **no se publican**: el
   MCP nunca los ve. Se resolvio por el mecanismo que existe para esto —la
   regla `R-FRESCURA-MANUAL` alcanza a los dos esquemas y su texto lo dice— y
   hay un test que lo exige **derivando del codigo** que pasos dejan fila en
   `_meta.etl_runs` y cuales no. Repetir la advertencia en las 24 fichas la
   habria diluido.
2. **La comprobacion aplazada de fan-out se disparo, como estaba disenada.**
   `mart.fact_seguimiento_mensual -> compras.v_pbi_partida_coste.partida_id`
   declaraba `N:1`; en cuanto el destino tuvo ficha, el validador vio que su
   clave es `(obra_id, partida_id)` y lo marco. Es `N:N`, y su `porque` dice
   ahora por que par hay que agregar.
3. **Dos relaciones `1:1` de retenciones eran `N:N`.** `movimiento_id` solo es
   unico DENTRO de su sentido: unir por el a secas **cruza retenciones de
   proveedor con retenciones de cliente**. Las fichas lo dicen ahora.

Un detalle de formato que costo un rato y conviene recordar: **un escalar YAML
sin comillas no puede contener `": "`**. Cinco textos de `compras.yaml` lo
tenian y el fichero no parseaba; se pasaron a bloque `>-`.

---

## Evidencias tras el bloque E y el bloque F parcial

| Evidencia | Bloques A-D | Ahora |
|---|---|---|
| **Tests que pasan** | 1133 | **1242** (444 de F-006), 2 saltados con motivo |
| **Tests que fallan** | 0 | **0** |
| **Tiempo de la suite** | 25,6 s | **31,8 s** sin cobertura |
| **Cobertura de las lineas cambiadas** | 98,7 % (550/557) | **98,9 % (710/718)**, umbral 80 %, nivel `critico` |
| **Mutantes / supervivientes** | 132 / 0 | **160 / 0**, 0 timeouts, 386,3 s |
| **Objetos documentados** | 25 de 98 | **49 de 102** |
| **Columnas descritas** | 332 | **593**, todas contrastadas contra el SQL |
| **Trinquete `pendientes`** | 73 | **53** |

**Analisis de supervivientes: no hay ninguno.** La campana cubre ahora tambien
`diccionario_sql.py`, `publicar_diccionario_step.py` y las lineas nuevas de
`postgres_client.py` y `main.py`.

Un apunte sobre el tiempo: al entrar las 24 fichas nuevas la suite se fue a
**seis minutos**, porque `tests/test_f006_fichas.py` recargaba los 49 YAML en
cada uno de sus ~160 tests. Se cachearon la carga del diccionario y el
inventario —son de solo lectura y las entidades son inmutables— y volvio a
**32 s**. Estaba en la evidencia y por eso se miro.

## Lo que queda para la tanda siguiente

- **Bloque F, el resto**: `maestro` (4 objetos), y despues el bloque G con
  `stg` (10), `aux` (1), `_meta` (7, incluidos los cuatro que anadio el DDL del
  contrato) y `raw` (31 a nivel de objeto). Son los 53 que faltan.
- **Bloque H**: `check-diccionario` (R28), que hoy **no existe** y que los
  docstrings no dan por existente.
- **Bloques I y J**: permisos, `REVOKE`, firewall y documentacion del
  ecosistema. Necesitan firma del humano y **no se ha tocado nada de eso**.
- **T19, T27, T39 y T40**: verificaciones `MANUAL (humano)`, con sus comandos en
  este informe.

---

# Correcciones de la tercera review

## Defecto 6 y 7 · La vista del contrato se desviaba, y sin test que la fijara

```
$ python -m pytest tests/test_f006_publicacion.py -q -k "orden or dieciocho or columna_anadida"
FAILED tests/test_f006_publicacion.py::test_f006_r15_ddl_la_vista_proyecta_estas_columnas_y_en_este_orden
FAILED tests/test_f006_publicacion.py::test_f006_r15_las_dieciocho_del_diseno_conservan_su_posicion
FAILED tests/test_f006_publicacion.py::test_f006_r23_el_diseno_documenta_la_columna_anadida
3 failed, 4 passed, 41 deselected in 1.10s
```

**Decision, con su motivo: manda la implementacion en el QUE y el diseno en el
DONDE.** La columna `motivo_no_consumo` es una buena idea y se queda —un MCP que
ve un objeto con `consumo_recomendado: false` necesita poder decir por que sin
abrir el JSONB ni hacer un segundo viaje—, pero **estaba en la posicion 6**, que
es exactamente lo que la cabecera del propio fichero prohibe cuatro lineas mas
arriba: correr de posicion a las trece columnas que van detras. Quien
desempaquete por indice se habria encontrado los campos cambiados **sin que nada
fallase**.

Se mueve **al final**, que es la unica forma compatible de crecer, y se enmienda
`design.md` §4.2 con una nota fechada que explica por que no esta en su sitio
natural. Las 18 del contrato original conservan su posicion exacta.

Y se le pone **el test que le faltaba**, que es lo que permitio que esto pasara:
era la unica de las cuatro estructuras del contrato sin contraste exacto —solo
se comprobaba por subcadena que 15 de sus nombres aparecieran, y omitia justo
`tipo`, `capa`, `consumo_recomendado` y `motivo_no_consumo`—. Ahora hay tres:
la lista completa **en orden**, que el diseno y la vista real proyecten lo mismo,
y que `design.md` documente la columna anadida.

## El mecanismo · contrastar `agregacion` y `clave_negocio` contra el SQL

Es la causa de fondo que el reviewer llevaba senalando desde la segunda pasada y
que ya habia costado dos rechazos. Fase RED, con el mecanismo recien escrito
sobre las fichas tal y como estaban:

```
$ python -m pytest tests/test_f006_fichas.py -q -k "agregacion_declarada or clave_de_negocio_cabe or ..."
E       AssertionError: ['anio'] están en `clave_negocio` y no en el `GROUP BY`
FAILED tests/test_f006_fichas.py::test_f006_r7_la_agregacion_declarada_case_con_la_funcion_del_sql[compras.v_pbi_proveedor_obra]
FAILED tests/test_f006_fichas.py::test_f006_r7_la_agregacion_declarada_case_con_la_funcion_del_sql[retenciones.v_pbi_retencion_resumen]
FAILED tests/test_f006_fichas.py::test_f006_r2_la_clave_de_negocio_cabe_en_el_group_by[compras.v_pbi_proveedor_obra]
3 failed, 48 passed, 38 skipped, 164 deselected in 0.96s
```

**El defecto 2 eran TRES columnas y son CINCO.** La comprobacion encontro dos
mas que la auditoria manual no vio: `num_entidades` y `num_obras` de
`retenciones.v_pbi_retencion_resumen`, tambien `COUNT(DISTINCT)` marcados
`suma`. Las cinco pasan a `no_sumable` **y su texto explica por que**, que es lo
que el agente lee: una factura repartida entre tres obras aparece en las tres
con valor 1.

El tercer fallo era **del propio detector, y lo delato el control**: el lector
del `GROUP BY` cortaba al final de la primera linea, asi que en un `GROUP BY` de
seis columnas partido en dos lineas se perdia la ultima. Corregido a leer hasta
el `;`.

### Que comprueba, y que NO, dicho antes de que se de por cubierto

**Derivable y sonido, implementado:**

| Comprobacion | Que caza |
|---|---|
| `agregacion` contra la funcion que envuelve la columna | `COUNT(DISTINCT)`, `MIN`, `MAX` y `AVG` no pueden ser `suma`. `SUM` y `COUNT` sin DISTINCT **si** se pueden seguir sumando entre grupos disjuntos, y por eso no se restringen |
| `clave_negocio` contenida en el `GROUP BY` | Una columna de la clave por la que la vista no agrupa puede repetirse, y el JOIN por ella multiplica |
| `clave_negocio` frente a la PK del DDL | Si el `ALTER TABLE ... ADD PRIMARY KEY` declara una clave, la de negocio tiene que ser esa. Se exceptuan las PK marcadas `clave_sustituta`, donde la de negocio es otra cosa a proposito |

**NO derivable, y por eso NO se implementa:** la direccion contraria, «la clave
es demasiado corta». Decidir si una columna del `GROUP BY` puede omitirse exige
saber si depende funcionalmente de otra, y eso no se lee del texto:
`codigo_obra` SI depende de `obra_id` y `proveedor_cif` NO depende de
`proveedor_id` —sale del CIF del documento— y las dos se escriben igual. Exigir
la igualdad con el `GROUP BY` marcaria como falsas fichas correctas:
`mart.fact_seguimiento_categoria` agrupa por nueve columnas de las que cinco se
derivan de otras dos. **Esa mitad se queda en revision humana**, esta escrito en
el docstring del modulo y es exactamente el defecto 5, que se corrige a mano.

Cada comprobacion lleva **su test de control**: que el detector de funciones
distinga los cinco casos, que el `GROUP BY` se lea donde se puede y **no** donde
no —`mart.v_fact_periodificado` tiene `UNION` y su `GROUP BY` es de una rama—, y
que existan tablas con PK declarada. Sin ellos, un detector que devolviera
siempre vacio haria pasar todo en falso.

## Defectos 1, 3, 4, 5 y los medios · las mentiras que ninguna comprobacion caza

```
$ python -m pytest tests/test_f006_fichas.py -q -k "nota_se_acota or no_anuncia_negativos or clave_falsa or ..."
FAILED tests/test_f006_fichas.py::test_f006_r2_la_regla_de_la_nota_se_acota_a_donde_es_cierta
FAILED tests/test_f006_fichas.py::test_f006_r2_la_vista_de_sin_facturar_no_anuncia_negativos
FAILED tests/test_f006_fichas.py::test_f006_r2_las_dos_vistas_fuente_de_retenciones_no_declaran_clave_falsa
FAILED tests/test_f006_fichas.py::test_f006_r2_la_clave_de_proveedor_obra_es_la_del_group_by
FAILED tests/test_f006_fichas.py::test_f006_r2_los_filtros_que_pierden_filas_se_declaran
FAILED tests/test_f006_fichas.py::test_f006_r2_las_medidas_sin_coalesce_declaran_su_nulo[compras.v_pbi_proveedor_obra-columnas0]
FAILED tests/test_f006_fichas.py::test_f006_r2_las_medidas_sin_coalesce_declaran_su_nulo[compras.v_pbi_partida_coste-columnas1]
FAILED tests/test_f006_fichas.py::test_f006_r2_lo_vencido_se_congela_en_el_build_y_se_dice
8 failed, 253 deselected in 0.67s
```

| Defecto | Corregido |
|---|---|
| **1** · la regla de la NOTA | Estaba enunciada como general y es **falsa en `v_pbi_contrato_consumo`**, donde `SUM(pendiente_facturar)` es el unico agregado sin `FILTER`. Ahora la ficha de `tipo_documento` dice **donde vale y donde no**, y la columna del pendiente advierte de que incluye NOTA y OTRO y de que las dos cifras pueden no coincidir. Con un test que exige que el SQL siga sin `FILTER`: el dia que se lo pongan, estas dos fichas hay que reescribirlas |
| **3** · clave que contradice el grano | Las dos vistas fuente de `retenciones` declaraban `[docide, obride]`, que es **el par del fan-out** ofrecido como clave. Ahora declaran que **no tienen clave** y su `grano` dice que son una fila por LINEA |
| **4** · negativos imposibles | `v_pbi_albaranes_sin_facturar` filtra `> 0`: ahi no hay sobrefacturacion. El texto —copiado de `albaran_lineas`, donde SI es cierto— dice ahora que las sobrefacturadas **no aparecen** y donde ir a verlas |
| **5** · clave demasiado corta | `v_pbi_proveedor_obra` pasa a las **seis** columnas de su `GROUP BY`. `proveedor_cif` no depende de `proveedor_id`: sale del CIF del documento, como la propia ficha admitia |
| **8, 9** · nulos imposibles | Dos `nulo_significa` que un filtro de la vista impide. Y, mas importante, **el filtro que los impide se declara**: `WHERE proveedor_id IS NOT NULL` saca filas de la vista, y eso no lo decia nadie |
| **10** · ocho medidas sin `COALESCE` | Devuelven NULL y no cero. Lo delata el contraste: `v_pbi_contrato_consumo` si envuelve. Un `WHERE facturado > 0` perdia filas en silencio |
| **11** · lo vencido, congelado | `vencida_sin_liquidar` y `dias_desde_vencimiento` se calculan con `CURRENT_DATE` **en el build** de un `CREATE TABLE AS`. En un esquema manual cuya frescura ni siquiera es consultable, esa lista puede llevar semanas parada. Las fichas lo dicen y mandan recalcular sobre `fecha_prevista_devolucion` |

Y los menores 12, 13, 14, 16, 17, 18, 19 y 20, cada uno contra su linea de SQL.

### Un cambio de contrato que hizo falta, con su motivo

Al quitar la clave falsa de las dos vistas fuente, R2 las rechazo: exigia
`clave_negocio` a toda tabla o vista. **Exigir una clave siempre obliga a
inventarsela**, que es exactamente lo que produjo el defecto 3.

R2 admite ahora declararla **vacia**, pero solo **fuera de la superficie de
consumo**: si un objeto se recomienda para consultar, quien lo consulte necesita
saber que identifica una fila, y R3 ya obliga a escribir por que no se
recomienda. El hueco declarado es mejor que la clave inventada; el hueco
silencioso, no.

## Los menores que quedaban, y dos tests que no arreglan nada

| # | Corregido |
|---|---|
| **15** | `v_pbi_albaranes_sin_facturar`: `contrato_id` sale de la cabecera y `codigo_contrato` de una cascada mas amplia, asi que **pueden salir juntos nulo e informado**. No es una incoherencia y ahora lo dicen las dos fichas |
| **21** | El comentario de `diccionario_sql.py` justificaba `DELETE` frente a `TRUNCATE` diciendo que este «no es transaccional». **Es falso**: en PostgreSQL lo es. El motivo bueno, y es mejor, es que `TRUNCATE` toma un `ACCESS EXCLUSIVE` que **bloquea a los lectores** hasta el commit, que es justo lo que este diseno evita. La decision era correcta; el motivo escrito, no |
| **22** | `CLAUDE.md` decia que la puerta exige actualizar la ficha «en el mismo trabajo». Lo que exige es **ficha O pendiente declarado**. Rebajada la frase a lo que de verdad hace, anadiendo que la lista solo baja |
| **24** | `n_columnas` (todas las fichas) y `cobertura_cols` (solo la superficie de consumo) **no comparten denominador**, asi que multiplicarlos no da columnas descritas. Dicho con `COMMENT ON COLUMN` en el propio contrato, que es donde lo va a leer quien consulte |
| **26** | `version` es manual y `hash_fuente` es la identidad. Documentado tambien con `COMMENT ON COLUMN`: **para invalidar una cache hay que mirar el hash**, no el numero |
| **27** | La verificacion manual de T19 daba cifras que ya estaban viejas. Ahora remite a los recuentos que imprime el propio paso, en vez de fijar un numero que envejece cada tanda |

**Dos tests nuevos que no corrigen nada, y por eso no tienen fase RED**: pasaron
en verde desde el primer momento. Estan porque lo que fijan no estaba fijado por
nada:

- **`apply_grants` no depende de `publicar_diccionario`.** Hoy es cierto, pero
  el dia que alguien anada esa dependencia «para que quede ordenado», una noche
  con el diccionario invalido dejaria al MCP sin permisos de lectura: el fallo
  exacto que R20 existe para evitar.
- **El `rollback` real del cliente.** Los demas tests sustituyen `connection()`
  entera, asi que el `commit`/`rollback` de `postgres_client.py` **no se
  ejecutaba en ningun test del repositorio**: la garantia que sostiene todo el
  contrato estaba probada de lejos. Ahora se usa el `connection()` de verdad
  con una conexion falsa, y hay un control que comprueba que sin excepcion si
  hace `commit` —si nunca lo hiciera, el otro pasaria en falso—.

## Evidencias tras la tercera review

| Evidencia | Antes | Ahora |
|---|---|---|
| **Tests que pasan** | 1242 | **1310** (521 de F-006), 40 saltados con motivo |
| **Tests que fallan** | 0 | **0** |
| **Tiempo de la suite** | 31,8 s | **27,2 s** sin cobertura |
| **Cobertura de las lineas cambiadas** | 98,9 % (710/718) | **98,9 % (710/718)**, umbral 80 %, nivel `critico` |
| **Mutantes / supervivientes** | 160 / 0 | **161 / 0**, 0 timeouts, 377,8 s |
| **Objetos documentados** | 49 de 102 | 49 de 102 |
| **Columnas descritas** | 593 | 593 |

**Analisis de supervivientes: no hay ninguno.**

Los 40 tests saltados no son un descuido: son el alcance declarado del
mecanismo. Cada `skip` lleva su motivo —«el `GROUP BY` de este objeto no es
derivable», «el DDL no declara clave primaria», «se crea con SQL dinamico»— y
hay tests de control que exigen que el salto **no sea universal**: si el lector
del `GROUP BY` dejara de leer ninguno, o los leyera todos, saltarian.

### Recuento honesto de lo que encontro cada cosa

| Quien lo encontro | Defectos |
|---|---|
| El reviewer, a mano | 6 graves, 4 medios, 11 menores |
| **El mecanismo nuevo, al escribirlo** | **2 `COUNT(DISTINCT)` mas** que la auditoria manual no vio, y **un fallo del propio detector** (el `GROUP BY` multilinea) que delato su test de control |

Es el argumento a favor de la comprobacion derivable en una linea: la auditoria
manual encontro tres de cinco; el test encuentra los cinco y seguira
encontrandolos en los 53 objetos que faltan.

---

# Correcciones de la cuarta review

## La clase, cerrada · coherencia interna entre campos de la misma ficha

El reviewer no rechaza por cuatro casos, rechaza por **un patron**: una
afirmacion corregida en un campo y viva en el de al lado. Ya habia pasado tres
veces —con el ejemplo de `design.md`, con «mes anterior» y ahora con los
granos—. Fase RED de la comprobacion que lo cierra:

```
$ python -m pytest tests/test_f006_fichas.py -q -k "grano_nombra or claves_compuestas"
FAILED tests/test_f006_fichas.py::test_f006_r2_el_grano_nombra_todas_las_columnas_de_la_clave[retenciones.v_pbi_retencion_obra]
FAILED tests/test_f006_fichas.py::test_f006_r2_el_grano_nombra_todas_las_columnas_de_la_clave[retenciones.v_pbi_retenciones_vencidas]
FAILED tests/test_f006_fichas.py::test_f006_r2_el_grano_nombra_todas_las_columnas_de_la_clave[retenciones.v_pbi_retenciones_vivas]
28 failed, 13 passed, 261 deselected in 1.04s
```

**28 de 41 fichas fallaban**, no las dos senaladas. La regla es de una linea y
no admite interpretacion: **el `grano` tiene que nombrar todas las columnas de
su `clave_negocio`**. Da igual como lo redacte —enumeracion entre parentesis o
prosa— mientras las nombre, asi que el grano no puede prometer menos
dimensiones de las que la clave declara.

Se descartaron dos alternativas antes de elegirla. **Comparar la enumeracion del
grano con la clave** no funciona: los granos escriben conceptos de negocio
(«obra», «mes») y las claves, columnas (`obra_id`, `anio_mes`); casarlos exige
un emparejamiento difuso que marcaria de mas. **Contar dimensiones** tampoco:
las seis columnas de `v_pbi_proveedor_obra` son tres conceptos, asi que el
recuento no delata nada. Exigir que los NOMBRES aparezcan es exacto, no admite
interpretacion y ademas mejora la ficha: el grano pasa a decir literalmente por
que columnas hay que unir.

Los 28 granos reescritos, con el resultado a la vista en los dos casos que
motivaron el rechazo:

- `v_pbi_proveedor_obra`: «Una fila por (`obra_id`, `codigo_obra`,
  `proveedor_id`, `proveedor_nombre`, `proveedor_cif`, `anio`), que es su clave
  de negocio y son **SEIS columnas, no tres**. No basta con (obra, proveedor,
  ano): `proveedor_cif` sale del CIF que traia cada documento y NO depende de
  `proveedor_id`, asi que dos facturas del mismo proveedor con CIF distinto dan
  DOS filas. Unir por tres columnas duplica.»
- `v_pbi_partida_coste`: la clave son **cinco** columnas y el grano lo dice, con
  el motivo —el `GROUP BY` incluye los textos y `codigo_obra` se resuelve por
  otra cascada—.

## Defecto 3 · la regla de la NOTA, tambien en el grano

Sobrevivia en el `grano` de `v_pbi_albaranes_sin_facturar` con la formulacion
general. Ahora dice **lo que esa vista hace** —«esta vista SI filtra por tipo»—
y advierte de no generalizar, nombrando la vista donde es falso.

## Defecto 4 · el congelado, en las dos vistas donde aterriza la pregunta

El aviso estaba solo en la tabla base. `v_pbi_retenciones_vivas` y `_vencidas`
son **las que responden P13 de la bateria**: quien pregunta «que vence este
trimestre» aterriza ahi. Las tres columnas afectadas dicen ahora que el calculo
se congelo **el dia del build** y que para el vencimiento de hoy hay que
recalcular sobre `fecha_prevista_devolucion`. El test cubre las cinco columnas,
no las dos que se senalaron.

## Menor 7 · la misma clase, buscada entera

- Las **tres** medidas de `v_pbi_retencion_resumen` sin `COALESCE` que faltaban
  por declarar su nulo, mientras sus hermanas del mismo fichero si lo hacian.
- El pendiente **no era «el unico agregado sin filtrar»**: `importe_facturado`
  tampoco filtra, y la propia ficha lo admitia dos columnas mas arriba.
- `fact_compras_linea.proveedor_id` sale de un `NULLIF(entide, 0)` y no
  declaraba su nulo, siendo la tabla a la que la ficha vecina manda «para no
  perder las lineas sin proveedor». Ahora lo dice y explica esa conexion.

## Los menores 4, 5 y 6

- **El detector de PK tenia un punto ciego y su mensaje mentia.** Solo veia
  `ALTER TABLE … ADD PRIMARY KEY`, no la forma **inline** `col TIPO PRIMARY
  KEY`, asi que decia «el DDL no declara clave primaria» de tres tablas que si
  la declaran. Hoy no cambiaba ningun veredicto —esas tres saltaban igual por la
  rama de la clave sustituta— pero el dia que alguien declarase una PK de
  negocio inline la habria saltado en silencio. Corregido, y el control prueba
  ahora **las dos formas** y el caso negativo.
- **Un aserto rompia el crecimiento que el propio contrato declara compatible.**
  Fijaba que la ultima columna de `_meta.v_diccionario` fuese
  `motivo_no_consumo`, asi que anadir otra AL FINAL —lo unico que la cabecera
  del DDL permite sin romper a nadie— lo ponia en rojo aunque se actualizasen
  SQL, `design.md` y la lista. El invariante correcto es **el prefijo de 18**,
  que ya estaba en la linea siguiente.
- **Dos docstrings afirmaban de mas**, que es la misma sobreventa corregida ya
  dos veces. El del `rollback` decia que ni el `commit` ni el `rollback` se
  ejecutaban en ningun test: **el `commit` si** —`test_f005_conexion.py` usa el
  `connection()` real—; lo que no se ejercitaba era la rama del `rollback`, que
  necesita que algo falle dentro del `with`. Y el de `apply_grants` se declara
  ahora **estructural**: comprueba `depends_on`, protege del escenario que
  nombra y no de un cambio en la logica de salto del orquestador.

## Las dos vias del reviewer, valoradas

### (a) El `GROUP BY` de las tablas agregadas · **implementada**

`mart.fact_seguimiento_categoria` se llena con `INSERT … SELECT … GROUP BY` y no
la miraba nadie: el contraste de `GROUP BY` solo veia vistas y el de PK la
saltaba por clave sustituta. Es el mismo parser sobre otra sentencia. Ahora se
le aplican **las dos** comprobaciones, la de clave y la de agregacion, con su
test de control.

Comprobado que no pasa en vacio: poniendo `agregacion: suma` en
`num_partidas` —que es un `COUNT(DISTINCT)`— el test se pone en rojo:

```
E  AssertionError: mart.fact_seguimiento_categoria.num_partidas: el SQL es COUNT DISTINCT y la ficha dice `suma`
```

### (b) La consulta de unicidad en T27 · **viable, y declarada**

**Es viable y liquida el problema entero**, incluidas las dependencias
funcionales que ninguna lectura del texto puede resolver. Queda escrita en
`tasks.md` T26 como parte del comando, con la consulta exacta:

```sql
SELECT count(*) FROM (
    SELECT <clave_negocio> FROM <esquema>.<objeto>
    GROUP BY <clave_negocio> HAVING count(*) > 1
) AS duplicadas;
```

Se prefiere esta forma a `count(*) - count(DISTINCT (...))` por dos motivos:
**agrupa los NULOS como un valor mas**, que es como se comportan en un JOIN, y
devuelve **cuantas** claves estan duplicadas, que es lo accionable. Es una
agregacion por objeto sobre tablas ya construidas: unas decenas de consultas
baratas. `design.md` §10 queda enmendado con el reparto entre lo que la puerta
offline puede y lo que se traslada a T26.

**No se implementa ahora** porque exige conexion a la base y este encargo no la
tiene: T26 y T27 son del bloque H.

## El barrido de copias, convertido en mecanismo

La leccion que el propio reviewer extrae —«cuando se corrige una afirmacion hay
que buscar sus copias en el mismo fichero»— se aplico al terminar, y **encontro
dos supervivientes mas** que nadie habia senalado:

1. **La regla falsa de la NOTA seguia viva en la bateria de aceptacion**, en la
   respuesta correcta de P12 (`00_global.yaml`). Corregida igual que en las
   fichas: dice que vale en la vista que filtra y no en la que no.
2. **El aviso de congelado faltaba en SEIS medidas agregadas mas**
   —`v_pbi_retencion_entidad.importe_vencido` y `.num_vencidas`,
   `v_pbi_retencion_obra.vencido_proveedores` y `.vencido_cliente`,
   `v_pbi_retencion_resumen.importe_vencido` y `.num_vencidas`— mas
   `v_pbi_retenciones_vencidas.antiguedad` e `.importe`. Todas se calculan
   **filtrando por `vencida_sin_liquidar`**, asi que el conjunto de filas que
   suman se decidio en el build.

En vez de corregir la tercera tanda a mano, se derivo: **`CURRENT_DATE` dentro
de un `CREATE TABLE AS` congela; dentro de una vista, no** —la distincion es
exacta y se lee del SQL—, **y una columna cuya expresion referencia una columna
congelada hereda el congelado y tiene que advertirlo**. Fase RED:

```
E  assert not ['retenciones.v_pbi_retencion_entidad.importe_vencido',
    'retenciones.v_pbi_retencion_entidad.num_vencidas',
    'retenciones.v_pbi_retencion_obra.vencido_proveedores', ...]
```

Con su control, que exige que se detecten exactamente las dos columnas
congeladas de `retenciones` **y que `compras.dias_desde_albaran` NO cuente**,
porque vive en una vista y se recalcula en cada consulta.

Es el mismo patron de esta pasada: donde el reviewer senala un caso, se busca la
clase; y donde la clase es derivable, se deriva en vez de revisarla a ojo.

## Evidencias tras la cuarta review

| Evidencia | Antes | Ahora |
|---|---|---|
| **Tests que pasan** | 1310 | **1359** (561 de F-006), 40 saltados con motivo |
| **Tests que fallan** | 0 | **0** |
| **Cobertura de las lineas cambiadas** | 98,9 % (710/718) | **98,9 % (710/718)**, umbral 80 %, nivel `critico` |
| **Mutantes / supervivientes** | 161 / 0 | **161 / 0**, 0 timeouts, 399,5 s |
| **Objetos documentados** | 49 de 102 | 49 de 102 |
| **Granos reescritos** | — | **28**, para que nombren su clave |

### Comprobaciones derivables que tiene ya la puerta

| Contra el SQL | Entre campos de la misma ficha |
|---|---|
| columnas exactas de tablas y vistas | `clave_negocio` ⊆ columnas documentadas |
| `agregacion` vs la funcion que envuelve la columna | **`grano` nombra toda la `clave_negocio`** |
| `clave_negocio` ⊆ `GROUP BY` de vista o de `INSERT … SELECT` | cardinalidad vs unicidad de la clave declarada |
| `clave_negocio` = PK del DDL (aparte **o inline**) | clave de JOIN citada en `porque` vs columnas propias |
| `nulo_significa` en `*_ide` vs `NULLIF` | avisos derivados del ambito de las reglas |
| **congelado en el build, y su propagacion** | minimos de contenido |

Lo que sigue **sin** ser derivable y por que, dicho una vez mas para que no se
de por cubierto: **si la clave es demasiado corta**. Exige dependencias
funcionales que el texto no da. Se traslada a T26 como consulta de unicidad
contra la base real, ya escrita en `tasks.md` con su SQL exacto.

### Lo que encontro cada cosa, en esta pasada

| Quien | Que |
|---|---|
| El reviewer | 4 defectos de campo vecino y 4 menores |
| **La comprobacion grano↔clave** | **28 fichas**, no las dos senaladas |
| **El barrido de copias** | la regla falsa de la NOTA **en la bateria** y **8 columnas** mas sin el aviso de congelado |
| **La deteccion de PK inline** | 3 tablas cuyo motivo de salto era falso |

---

# Correcciones de la quinta review

## El barrido, esta vez exhaustivo y ANTES de tocar nada

La leccion de la pasada anterior era buscar las copias. Esta vez el barrido fue
lo primero, y automatizado: se listaron **todas** las vistas y tablas agregadas
cuya clave esta estrictamente contenida en su `GROUP BY`. Salieron **tres**
candidatos, no el que senalaba el informe:

```
REVISAR mart.fact_seguimiento_categoria    | GROUP BY de mas=['ambito_id','anio','concepto','mes','tipo_dato']
REVISAR retenciones.v_pbi_retencion_entidad| GROUP BY de mas=['entidad_cif','entidad_nombre']
REVISAR retenciones.v_pbi_retencion_obra   | GROUP BY de mas=['codigo_obra','nombre_obra']
```

De los tres, **solo uno miente**, y el criterio que los separa se verifico
contra el SQL:

| Ficha | Columnas omitidas | Veredicto |
|---|---|---|
| `fact_seguimiento_categoria` | `anio`, `mes` salen de `anio_mes`; `tipo_dato`, `concepto`, `ambito_id` salen de `escenario` | **clave correcta**, son derivadas |
| `v_pbi_retencion_entidad` | `ent.res` y `prv.cif`, los dos por `LEFT JOIN … ON ide = entide` | **clave correcta**, un solo lookup por la propia clave |
| `v_pbi_retencion_obra` | `COALESCE(cen_con.cod, obr_con.cod)` sobre **dos JOIN distintos** | **MIENTE** |

## Defecto 1 · `v_pbi_retencion_obra`, y el estrechamiento que lo caza

La clave pasa a las tres columnas y el grano explica el porque: en
`retenciones.movimientos`, `obra_id` sale del centro de coste del efecto y
`codigo_obra`/`nombre_obra` de un `COALESCE` sobre dos JOIN distintos, asi que
**un `obra_id` cuyo centro de coste no exista en el maestro puede aparecer con
dos codigos**. La relacion hacia `maestro.obras` explica ahora por que es `N:1`
y no `1:1` (menor 4, que se resolvia solo).

**Y se estrecha el subconjunto, que era lo que se pedia valorar.** Hay un
criterio barato y exacto que separa los tres casos de arriba sin marcar de mas:
**una columna agrupada puede omitirse de la clave si se resuelve por UNA sola
fuente, y no puede si sale de un `COALESCE` de dos fuentes distintas**. Cuando
la vista la proyecta desnuda, se resuelve aguas arriba, en la tabla de la que
selecciona. Fase RED:

```
$ python -m pytest tests/test_f006_fichas.py -q -k "multifuente or no_es_derivable"
tests\test_f006_fichas.py:2011: AssertionError
FAILED tests/test_f006_fichas.py::test_f006_r2_la_clave_cubre_lo_del_group_by_que_no_es_derivable
1 failed, 1 passed, 310 deselected in 0.52s
```

Marca `codigo_obra` y `nombre_obra`, y **no marca** ni las cinco derivadas de
`fact_seguimiento_categoria` ni las dos de `v_pbi_retencion_entidad`. Su control
prueba las dos direcciones del detector.

Lo que sigue fuera: la clave corta cuya dependencia falla por otro motivo. Eso
es la consulta de unicidad de T26, ya escrita.

## Defecto 2 · el grano que se contradecia consigo mismo

`v_pbi_cierre_indirectos_detalle` decia que `importe_fase0` y
`plazo_total_meses` «traen valor siempre» y cincuenta lineas mas abajo declaraba
el nulo de las dos. **Manda el SQL**, que las deja nulas por `LEFT JOIN` y con
guardas explicitas. El grano dice ahora lo que se queria decir —traen valor se
periodifique el grupo o no— y remite a su `nulo_significa` para lo demas.

## Defecto 3 · la premisa falsa que sostenia el limite

El comentario que justifica por que «la clave demasiado corta» no es derivable
usaba como ejemplo que «`codigo_obra` si depende de `obra_id`». **Es falso**, y
lo desmiente el propio SQL de `retenciones` y la ficha de
`compras.v_pbi_partida_coste`. Corregido: el limite sigue siendo real —lo
sostiene `proveedor_cif`— pero el ejemplo que lo ilustraba era justo un caso en
el que la dependencia NO existe, y **un ejemplo equivocado dentro de la
justificacion de un limite hace creer que la linea esta en otro sitio**.

**Para el reviewer**: la frase salio de su informe de la cuarta pasada y sigue
ahi. Conviene corregirla tambien en `progress/review_F-006.md`, porque el
proximo que lea el limite partira de ese texto.

## Deuda anotada, no tocada (menores 5, 6 y 7)

Por decision del lider viajan con los bloques que faltan:

| # | Que |
|---|---|
| 5 | `compras.yaml`: la analogia «`importe_facturado` tampoco filtra» compara cosas distintas —alli no filtrar da el neto correcto sobre `factura_lineas`; en el pendiente arrastra NOTA y OTRO sobre `albaran_lineas`— y suaviza un aviso que no conviene suavizar |
| 6 | `v_pbi_retencion_entidad.primera_devolucion_prevista` y `.ultima_devolucion_prevista` son `MIN`/`MAX` sobre TODOS los efectos, liquidados incluidos, en una vista cuyo titular es `saldo_vivo`. Preexistente |
| 7 | La justificacion del SQL de unicidad de T26 dice que agrupar los NULOS es «como se comportan en un JOIN»: es al reves, en un JOIN los NULL no casan. Agruparlos es MAS estricto, que es lo que conviene; el SQL es correcto y el motivo escrito no |

## Evidencias tras la quinta review

| Evidencia | Antes | Ahora |
|---|---|---|
| **Tests que pasan** | 1359 | **1361** (563 de F-006), 40 saltados con motivo |
| **Tests que fallan** | 0 | **0** |
| **Cobertura de las lineas cambiadas** | 98,9 % (710/718) | **98,9 % (710/718)**, umbral 80 %, nivel `critico` |
| **Mutantes / supervivientes** | 161 / 0 | **161 / 0**, 0 timeouts, 404,7 s |

**El limite del contraste de clave, actualizado.** Ya no es «la clave corta no
es derivable»: la familia en la que se resuelve por varias fuentes **si lo es** y
se comprueba. Lo que queda fuera es la clave corta cuya dependencia falla por un
motivo que el texto no expone, y eso lo cierra la consulta de unicidad de T26.

---

# Bloque F (resto) y bloque G · los 53 objetos que faltaban

## T22 · `maestro` (4 objetos)

Fase RED, la puerta con los cuatro fuera de `pendientes`:

```
$ python -m pytest tests/test_f006_cobertura.py -q -k puerta
tests\test_f006_cobertura.py:501: AssertionError
FAILED tests/test_f006_cobertura.py::test_f006_r25_puerta_todo_objeto_publicado_tiene_ficha_o_esta_pendiente
1 failed, 10 passed, 34 deselected in 1.13s
```

Las cuatro trampas del encargo, escritas y contrastadas contra el SQL:

- **`maestro.obras` no filtra nada** y su grano lo dice: es superconjunto de
  `stg.obras`, y contar en una o en otra da distinto **a proposito**. La
  relacion hacia `stg.obras` explica que unir por ahi equivale a filtrar.
- **`es_activa` es la columna buena** para saber si una obra vive, y la ficha
  lo contrasta con la `activa` de `stg.obras`, cableada a TRUE.
- **`proveedores` no expone oficio ni naturaleza** aunque `raw.prv` los traiga
  cargados. Dicho con su motivo: es F-036, y es la razon de que la pregunta del
  fontanero solo se pueda responder hoy por texto libre.
- **`importe_contratado` lleva IVA** y no es comparable con el de `compras`. La
  ficha dice ademas **como** compararlos: sumando aparte la `cuota_iva` de
  `compras.contrato_lineas`.
- **`raw.obrprv` esta vacia en Ruesma**, y por eso el vinculo obra-proveedor se
  reconstruye desde los contratos. Esta en la descripcion, que es donde el
  agente se pregunta de donde sale la vista.

### Un arreglo de mantenimiento, hecho aqui porque tocaba

Cinco tests de publicacion fijaban los recuentos **como literales** —49 objetos,
593 columnas, 62 filas—, asi que cada esquema documentado los rompia. No es un
fallo de contenido, es una trampa de mantenimiento que iba a repetirse cinco
veces mas en esta misma tanda. Pasan a **derivarse del propio diccionario**, con
un suelo (`>= 49`, `>= 593`) para que no puedan quedarse en vacio si alguien
vacia una ficha.

## T23 · `stg` (10 objetos), el esquema con las peores trampas

Todas las fichas van `consumo_recomendado: false` con su motivo: **lo que se
pregunta esta en `mart` y en `cierre`**, y estas existen para que un agente
entienda de donde sale aquello y por que no debe consultar esto.

Las seis trampas del encargo, escritas y contrastadas contra el SQL:

- **`plan_mensual`**: su clave son CINCO columnas e incluye `version`. El grano
  dice literalmente que omitirla «es exactamente lo que multiplica los
  importes», y el `motivo_no_consumo` manda a `mart`.
- **`presupuesto`**: es el importe TOTAL sin distribucion mensual, con la regla
  de `importe` para coste (ambitos 3 y 8) e `importe_oficial` para venta (7 y
  11). La ficha explica **por que confundirlas pasa desapercibido**: sin
  coeficiente las dos valen lo mismo, asi que el error solo se ve en venta. Y la
  cantidad se guarda **sin redondear** porque en las partidas de tipo porcentaje
  el redondeo infla el importe.
- **`obras.activa`**: «NO SIGNIFICA NADA», con la alternativa buena al lado.
- **`partidas.categoria`**: heuristica sobre el codigo del capitulo raiz, y la
  ficha dice ademas que el catalogo oficial esta ingerido y sin usar, y que una
  obra que no siga la convencion **se clasifica mal y nada lo delata**.
- **`fases.numero_fase`** y la ambiguedad de `fas`, con sus tres nombres segun
  la capa.
- **`ambitos.uso_seguimiento` DESFASADO**: la ficha dice que marca solo 8 y 11,
  que `mart` ya construye tambien 3 y 7, y que **quien filtre por esa columna se
  dejara fuera la mitad**. Su `nulo_significa` lo repite, porque es el valor que
  se lee.

### Lo que cazaron los mecanismos, sin revisarlo a ojo

Al escribir el esquema saltaron tres cosas, y las tres eran reales:

1. **`stg.presupuesto` y `stg.fases` declaraban una clave distinta de su PK.**
   La PK viene de Sigrid y no es sustituta, asi que identifica la fila igual de
   bien y ademas **es la que usan los JOIN** —`plan_mensual` referencia
   `presupuesto_id`—. Se declara esa como clave y el grano conserva la
   combinacion conceptual de cuatro columnas.
2. **`mart.v_master_versiones_tipadas -> stg.plan_mensual` prometia `N:1`.** Es
   la comprobacion aplazada disparandose otra vez: en cuanto `plan_mensual` tuvo
   ficha, el validador vio que hay muchas filas por obra. Es `N:N`, y su
   `porque` dice por que trio hay que unir.
3. Los recuentos de los tests de publicacion **ya no rompieron**, porque se
   derivaron en T22.

### Un refactor de mantenimiento, por la misma razon

`TABLAS_CON_DDL_EXPLICITO` era un conjunto de tres nombres escrito a mano. Al
llegar `stg` con sus seis tablas se habria quedado corto **en silencio**: las
nuevas habrian caido en el grupo de «proyeccion» y el control las habria dado
por ilegibles. Pasa a derivarse del SQL, y los dos tests exactos de tablas se
parametrizan sobre el resultado en vez de sobre una lista de `mart`.

## T24 (1 de 2) · `aux` (1 objeto), y el estado real dicho sin rodeos

`aux.periodificacion_partida` guarda las reglas con las que Negocio reparte un
coste puntual a lo largo de varios meses. **Hoy esta vacia**, y la ficha lo dice
en mayusculas junto con la consecuencia comprobable: sin filas aqui,
**`mart.v_fact_periodificado` es un paso a traves** y devuelve exactamente lo
mismo que `mart.fact_seguimiento_mensual`. Quien la eligio esperando numeros
distintos no los vera.

Se documentan tambien los dos tipos de regla —especifica por obra+partida, o
generica por patron `LIKE`— que un CHECK impide mezclar, y que la especifica
gana cuando ambas casan.

### Dos cosas que el validador corrigio, y tenia razon en las dos

Escribi la ficha con `capa: auxiliar` y `paso_etl: build_mart` /
`refresco: manual`. Saltaron R2 y R14:

- `auxiliar` no esta en el vocabulario cerrado. La capa honesta es
  `preparacion`: es material que alimenta la capa de consumo sin ser consumido.
- **R14 caza una mentira de verdad**: `build_mart` SI corre cada noche, asi que
  declarar `manual` con ese paso no cuadra. Pero es que el paso tampoco era
  cierto: `build_mart` **crea** la tabla con `IF NOT EXISTS` y no la toca. No
  hay ningun paso del ETL que escriba aqui. Queda `refresco: estatico`, que es
  el unico valor que no promete un build detras, y la ficha explica por que.

### Un test que habia dejado de comprobar nada

`test_f006_r22_la_cobertura_publicada_baja_si_falta_un_significado` inyectaba
una columna sin significado en `fichas[0]` y esperaba ver bajar la cobertura.
Funciono mientras la primera ficha por orden de fichero fue de `mart`; al entrar
`aux.yaml` —alfabeticamente antes, y **fuera** del consumo recomendado, que es
lo unico que `cobertura_columnas` mide— la columna muda dejo de contar.

Tuvo la suerte de romper en vez de pasar en verde comprobando nada. La victima
pasa a **derivarse** (primera ficha con `consumo_recomendado: true` y columnas)
y un aserto explicito impide que vuelva a caer en una que no se mide.

### `aux.yaml` no se podia versionar, y los tests no se enteraron

Al hacer el `git add` de la ficha:

```
$ git add -A
error: open("config/diccionario/aux.yaml"): No such file or directory
error: unable to index file 'config/diccionario/aux.yaml'
fatal: adding files failed
```

Sobre un fichero que `ls -la` enseña con sus 6.308 bytes y que Python abre sin
pestanear. **`AUX` es un nombre de dispositivo reservado de MS-DOS** que Windows
sigue honrando, y git no puede indexarlo.

Lo grave es lo que no paso: **los 618 tests estaban en verde con la ficha
dentro**. El fichero funcionaba en este puesto y no habria llegado a ningun
otro; el fallo lo dio el control de versiones, no la suite.

Fase RED (`tests/test_f006_nombres_fichero.py`, 3 tests, 2 en rojo):

```
$ python -m pytest tests/test_f006_nombres_fichero.py -q
E  AssertionError: ['aux.yaml'] usa un nombre de dispositivo reservado de
   Windows: git no puede indexar el fichero aunque Python lo lea...
E  DiccionarioIlegible: aux_.yaml: el fichero `aux_.yaml` declara `esquema: aux`.
   El nombre del fichero manda: tiene que ser `aux_`
2 failed, 1 passed
```

El arreglo no lista `aux`: barre **la familia entera** —`con`, `prn`, `nul`,
`com1`..`lpt9`—, porque `con` es ademas el nombre de la tabla central de Sigrid
y habria mordido igual. `nombre_de_fichero(esquema)` en el cargador es la unica
definicion de la convencion, el fichero pasa a `aux_.yaml` con el `_` final que
Python usa para las palabras reservadas, y el tercer test comprueba que el
escape **no vale para los esquemas normales**: sin eso, `mart.yaml` y
`mart_.yaml` podrian coexistir cargando fichas del mismo esquema en silencio.

## T24 (2 de 2) · `_meta` (7 objetos), donde la precision importa el doble

Es el esquema que se cita cuando hay que decir DE CUANDO ES un dato. Una ficha
imprecisa aqui hace que un agente cite mal la fecha, o que no la cite, con
aplomo: el fallo que F-024 vino a eliminar. Las tres cosas del encargo van en la
cabecera del fichero y repetidas en la columna que toca:

- **`batch_id` se ordena como TEXTO.** El formato `YYYYMMDDTHHMMSSZ-xxxxxx` se
  eligio para eso, y la ficha lo dice donde se lee: en `etl_runs.batch_id` y en
  `v_raw_state.batch_id`, esta ultima con el uso que le da valor —comprobar si
  dos tablas de `raw` vienen de la misma noche—.
- **UTC sin zona.** Dicho en cada marca de tiempo, y con el numero:
  `horas_desde_ultimo_ok` explica que se calcula contra
  `now() AT TIME ZONE 'UTC'` porque restarle un `now()` local daria el desfase
  horario de Espana, **dos horas en verano**, como antiguedad.
- **`v_frescura` filtra tramos y hace `LEFT JOIN` a proposito.** El grano dice
  el filtro exacto (`position('.' IN step) = 0`) y lo que pasaria sin el; el
  `nulo_significa` de `ultimo_ok_finished_at` dice que un paso que no termino
  bien nunca **sigue saliendo**, y que un `INNER JOIN` seria el silencio que
  F-024 elimino.

Se documenta ademas la separacion ULTIMO OK / ULTIMO INTENTO, que es lo que
permite citar bien un `build_mart` que fallo anoche: el dato es de ayer y ademas
hay que decir que lo ultimo fallo. Citar solo una de las dos miente en los dos
sentidos.

En las tres tablas del diccionario queda escrito lo que no se puede deducir
mirando: que `hash_fuente` es la identidad y `version` solo comunicacion, que el
`CHECK (id = 1)` hace singleton la publicacion, que `cobertura_cols` **no
comparte denominador** con `n_columnas`, y por que `motivo_no_consumo` va la
ultima en `v_diccionario` en vez de donde se leeria mejor.

### El parser de DDL no veia las columnas de las migraciones

Al escribir la ficha de `etl_runs` salto la comprobacion de exactitud:

```
E  AssertionError: faltan: []; sobran: ['batch_id']
```

Y `batch_id` existe. Lo anadio F-024 con `ALTER TABLE ... ADD COLUMN IF NOT
EXISTS`, **fuera del `CREATE TABLE` a proposito**: el historico de `etl_runs` es
el unico sitio donde consta que paso las noches que fallaron, y recrear la tabla
lo perderia.

La salida obvia —borrar `batch_id` de la ficha— habria dejado el diccionario
mintiendo justo sobre el campo que responde «de que carga viene esta tabla».
Fase RED, dos tests nuevos:

```
$ python -m pytest tests/test_f006_fichas.py -q -k alter_table
E  AssertionError: assert ['id', 'step'] == ['id', 'step', 'batch_id']
E  AssertionError: assert ['id'] == ['id', 'solo_de_b']
2 failed
```

El segundo esta para que el `ADD COLUMN` se atribuya a SU tabla y no a la que se
esta leyendo. El parser pasa a recogerlas, al final, que es su orden real en el
catalogo.

### Y dos cosas mas que cazaron los mecanismos

- **R40** reclamo `ejemplos_preguntas` en los cuatro objetos de consumo. Es la
  regla que enruta de la pregunta al objeto, y sin ella `v_frescura` habria
  quedado documentada pero inalcanzable desde «de cuando es este dato».
- **R5**: declare `v_frescura -> etl_runs.step` como `N:1` y es `N:N`.
  `etl_runs` tiene una fila por VEZ que el paso corrio. El `porque` corregido
  explica que unir por `step` sin agregar devuelve el historico entero, que es
  exactamente la razon por la que la vista existe.

Trinquete: 38 -> **31**, que son las 31 tablas de `raw`.

## T25 · `raw` (31 tablas) y la regla de oro publicada

DA-2: **nivel de objeto, no de columna**. Son 31 tablas con cientos de campos de
cuatro letras cuyo diccionario completo —tipos, indices y referencias— ya existe
y esta mantenido en `azure-apps/sigrid_tablas.md`. Copiarlo aqui crearia una
segunda version que divergiria, que es exactamente lo que ya paso con
`sigrid_api.md`. Cada ficha apunta alli.

Lo que si documentan las fichas es **lo que ese documento no puede decir**:
quien consume cada tabla dentro del datamart, cual esta vacia y cual se ingiere
sin que la lea nadie.

### La regla de oro, y por que no basta con contarla

Los cinco puntos —`ide` como clave universal; las tablas "Propiedades de `con`"
en 1:1; `cod`, `res` y `fec` viviendo en `con`; **`con.nom` no existe**; y las
fechas como enteros `YYYYMMDD` con el `0` haciendo de NULL— estan verificados
**en la fuente**, no de memoria: la entidad `con` de `sigrid_tablas.md`, pagina
94, donde aparecen `ide`, `cod`, `res`, `fec`, `est` y `fecbaj` y no hay ningun
`nom`; y las cabeceras que dicen literalmente «Propiedades de con» en `obr`,
`prv`, `cen`, `ctr`, `com`, `dca`, `dcf`, `cob`, `pag` y `rec`.

Los escribi primero en la cabecera de `raw.yaml`. **Y una cabecera YAML es un
comentario: no la lee el cargador, no entra en `_meta.diccionario_reglas` y el
MCP no la ve nunca.** El agente habria seguido escribiendo `con.nom`.

Fase RED:

```
$ python -m pytest tests/test_f006_reglas.py -q -k regla_de_oro
E  AssertionError: la regla de oro de Sigrid está explicada en la cabecera de
   raw.yaml, que es un comentario y no se publica en _meta.diccionario_reglas
1 failed
```

El test no comprueba que exista una regla: comprueba **los cinco puntos, uno a
uno**, sobre el texto publicado. `R-SIGRID-CON` pasa a ser la decimotercera
regla obligatoria del dominio, con alcance `raw` y severidad bloqueante. Ninguno
de los cinco falla con un dato raro que invite a mirar: `con.nom` falla con
"columna inexistente", `obr` sin unir devuelve una obra sin nombre y un
`MIN(fecha)` sin excluir el cero devuelve cero, que parece un dato.

### Seis tablas que se cargan cada noche y no lee nadie

Sale del cruce entre `config/tables_sigrid.yaml` y quien las referencia en
`sql/`. Cada una lo dice en su ficha, porque una tabla ingerida sin consumidor
gasta ventana nocturna y **hace creer que existe una funcionalidad que no
existe**:

- **`auxobrtca`** (tipos de capitulo) es el catalogo OFICIAL que
  `stg.partidas.categoria` NO usa: aquello es una heuristica sobre el codigo del
  capitulo raiz. Que el catalogo bueno este ingerido y sin usar es lo que hace
  creer que la clasificacion viene de Sigrid.
- **`obrprv`** esta **VACIA en Ruesma**. Por eso `maestro.proveedores_obra` sale
  de `raw.ctr` —el proveedor de una obra se deduce de haberle contratado algo— y
  por eso su `importe_contratado` es `SUM(ctr.totdoc)`, **total del documento
  CON IVA**, y no una suma de lineas sin IVA como en `compras`. Las dos cosas
  quedan escritas en su ficha.
- **`com`, `comlin` y `comprv`**: el comparativo de ofertas. El datamart no
  cubre hoy el proceso de compra anterior al contrato.
- **`dcfprodes`**: el reparto de una linea de factura entre varios destinos, que
  no esta modelado aguas abajo.

El barrido de esa afirmacion **encontro un matiz que la habria dejado falsa**.
`auxobrtca` no la lee ningun SQL, cierto, pero `build_stg_step.py` la incluye en
su comprobacion de precondiciones: **aborta el paso si a la tabla le faltan
`ide`, `cod` o `res`**. Dejar de ingerirla no es gratis. La ficha lo dice, y la
cabecera del fichero tambien, porque "no la lee nadie" invita justo a la accion
equivocada.

Y sale de ahi un dato mejor sobre la heuristica de categorias: `raw.obrparpar`
trae la columna `tcaide`, que **apunta a `auxobrtca`**. La relacion existe en el
dato y ningun SQL la recorre; la clasificacion se deduce del codigo del capitulo
raiz teniendo el catalogo bueno enlazado al lado.

Se anota ademas en `raw.prv` que **`ofcide` se ingiere y no se expone**:
`maestro.proveedores` no publica oficio ni naturaleza. Es F-036, no un olvido.

### Y la ingesta tambien se contrasta, no se escribe a mano

Cada ficha de `raw` afirma dos cosas que no estan en el SQL sino en
`config/tables_sigrid.yaml`: si la carga es **incremental por `tiemod`** o
completa, y **que columnas no se traen**. Escribiendo 31 fichas a mano se me
quedaron dos sin decir —`raw.con` es incremental y `raw.conext` se recarga
entera— y ninguna comprobacion existente lo habria notado.

`tests/test_f006_raw_ingesta.py` deriva las dos afirmaciones (63 tests). Fase
RED:

```
$ python -m pytest tests/test_f006_raw_ingesta.py -q
E  AssertionError: la ficha de raw.con tiene que decir UNA de las dos cosas: que
   la carga es «incremental por `tiemod`» o que se «recarga entera» cada noche
E  AssertionError: la ficha de raw.conext tiene que decir UNA de las dos cosas...
2 failed, 61 passed
```

Comprueba tres cosas: que haya **exactamente** una ficha por tabla ingerida —ni
de mas ni de menos—, que cada una diga **una** de las dos formas de carga y que
sea la cierta, y que **toda columna que una ficha cite como no traida lo este de
verdad**. Esto ultimo importa mas de lo que parece: preguntar en `raw` por una
columna excluida no devuelve nulo, devuelve "columna inexistente". No se exige
listarlas todas —hay tablas con veinticinco exclusiones—, solo que lo citado sea
cierto.

### Y otro recuento cableado

Anadir la regla numero trece rompio tres asertos con el `12` escrito a mano. Es
la tercera vez que aparece el mismo patron en esta feature —los objetos, las
tablas con DDL explicito y ahora las reglas—, asi que los tres se derivan de
`len(dicc.reglas)`. La lista de codigos obligatorios sigue siendo explicita a
proposito: es la que hace que anadir una regla se vea en el diff.

**Trinquete: 31 -> 0.** No queda ningun objeto del datamart sin ficha.

## Nota de numeración (para leer el historial sin tropezar)

Los mensajes de commit de esta tanda numeran `_meta` como T25 y `raw` como T26.
`tasks.md` los agrupa distinto: **T24 son `aux` y `_meta` juntos, y `raw` es
T25**. Las secciones de este informe siguen la numeración de `tasks.md`, que es
la que manda; los mensajes de commit ya están en el historial y no se reescriben.

## Barrido de copias antes de cerrar la tanda

Tres rechazos vinieron de una afirmacion corregida en un sitio y viva en el
campo vecino, asi que el barrido se hace **derivando**, no releyendo. La consulta
busca toda relacion `N:1` o `1:1` que apunte a una columna que **no es** la clave
declarada del objeto destino, que es el patron de los dos defectos de esta
tanda:

```
mart.v_pbi_fact          -> mart.fact_seguimiento_mensual.fact_id      1:1
mart.v_pbi_fact_categoria-> mart.fact_seguimiento_categoria.fact_cat_id 1:1
mart.v_fact_periodificado-> mart.fact_seguimiento_mensual.fact_id      1:1
```

**Las tres son ciertas** y conviene dejar dicho por que, porque parecen el mismo
caso que `stg.presupuesto` y no lo son:

- En `mart`, `fact_id` y `fact_cat_id` son BIGSERIAL que **cambian en cada
  build** (es lo que dice `R-CLAVE-SUSTITUTA`). Son unicos, asi que el `1:1` de
  una vista pasarela es cierto; pero no pueden ser la clave de negocio, que es
  la combinacion estable.
- En `stg`, `presupuesto_id` y `fase_id` **vienen de Sigrid** y son estables
  entre builds, ademas de ser la columna por la que unen los JOIN. Ahi la clave
  de negocio SI es la PK, y el grano conserva la combinacion conceptual.

La distincion no es de estilo: de un lado hay un numero que sobrevive a la noche
y del otro uno que no.

## Estado del diccionario al cerrar esta tanda

| | |
|---|---|
| Objetos con ficha | **102** (`raw` 31, `compras` 14, `mart` 13, `cierre` 12, `stg` 10, `retenciones` 10, `_meta` 7, `maestro` 4, `aux` 1) |
| Pendientes declarados | **0** |
| Reglas duras publicadas | **13** |
| Columnas documentadas | **793** |
| Objetos en superficie de consumo | 47 de 102 |
| Cobertura de significados en esa superficie | **100 %** |

El trinquete (`PENDIENTES_MAX`) recorrio 98 -> 96 -> 85 -> 73 -> 77 -> 53 -> 49
-> 39 -> 38 -> 31 -> **0**. No queda ningun objeto del datamart sin ficha, asi
que **no hay nada que declarar como excepcion**.

## Lo que NO entra en esta tanda

Para que el resumen al humano no prometa de mas:

- **T26 (`check-diccionario`) no esta hecho.** La cobertura que se comprueba hoy
  sigue siendo la heuristica **offline** sobre `sql/**` y
  `config/tables_sigrid.yaml`. El contraste contra `information_schema` de la
  base real es esa tarea, y hace falta conexion.
- **La consulta de unicidad por objeto sigue planteada, no ejecutada.** Es lo
  unico que cierra el hueco conocido de "la clave declarada es demasiado corta"
  cuando la dependencia funcional no se ve en el texto. Esta escrita en T27 y es
  `MANUAL (humano)`: ningun agente abre la base.
- Las fichas de `raw` **no verifican que los nombres de tabla existan en el
  origen**: se contrastan contra `config/tables_sigrid.yaml`, que es lo que el
  ETL ingiere. Si Sigrid renombrase una tabla, la ingesta fallaria antes que el
  diccionario.
- **Las 18 preguntas de `requirements.md` §9 (T39) no se han pasado.** Hasta
  entonces, que una ficha sea correcta no demuestra todavia que sea *suficiente*
  para responder la pregunta a la que apunta.

## Los cuatro «timeouts» de la mutacion eran cuatro supervivientes

La campana cerro asi:

```
166 mutantes evaluados, 162 muertos, 0 supervivientes, 4 timeouts en 633.2 s
```

Leido deprisa es una campana limpia. **No lo era.** Los cuatro timeouts fueron
consecutivos (17 a 20) y coincidieron con otra suite corriendo en la misma
maquina, asi que en vez de darlos por ruido los reevalue **de uno en uno**,
aplicando la mutacion a mano y lanzando la suite:

```
--- linea 173: frozen=True -> frozen=False              =>  SUPERVIVIENTE
--- linea 140: "ejemplo_pregunta": 20 -> 21             =>  SUPERVIVIENTE
--- linea 189: frozen=True -> frozen=False              =>  SUPERVIVIENTE
--- linea 137: "grano": 20 -> 21                        =>  SUPERVIVIENTE
    (752 passed, 82 skipped en cada uno)
```

**Los cuatro.** La leccion vale mas que los cuatro tests: un timeout **no es un
mutante muerto, es un mutante sin evaluar**, y un informe que los cuenta en una
fila aparte de «supervivientes: 0» invita a leerlos como ruido de maquina.

### Que eran, y por que ninguno es equivalente

- **`frozen=True` -> `frozen=False` en `Columna` y `Relacion`.** Nada rompia al
  volverlas mutables. La inmutabilidad no es decoracion: estas entidades se
  comparten entre el validador, el cargador y los constructores de SQL, y se
  publican tal cual; si una `Columna` puede cambiarse entre que se valida y que
  se publica, **lo publicado no es lo validado**. La hermana `Ficha` (linea 277)
  si tenia quien la cazara; estas dos no.
- **Los minimos de longitud subidos en uno** (`grano` y `ejemplo_pregunta`, de
  20 a 21). Sobrevivian porque **ningun caso ejercita el borde**: si ninguna
  ficha ni ningun test tiene un texto de exactamente 20 caracteres, mover el
  umbral no cambia ningun veredicto.

### El primer arreglo tampoco valia, y es el error interesante

Escribi los tests de borde leyendo el minimo de la propia constante
(`MINIMOS_TEXTO[campo]`). Resultado: al subir la constante, el texto de prueba
subia con ella y el borde seguia pasando. **Los dos mutantes sobrevivieron al
test escrito para matarlos**:

```
173: frozen -> MUERTO
140: "ejemplo_pregunta": 20 -> 21  =>  SUPERVIVIENTE
189: frozen -> MUERTO
137: "grano": 20 -> 21             =>  SUPERVIVIENTE
```

**Un test que se mueve con lo que vigila no vigila.** Los numeros pasan a estar
escritos en `MINIMOS_FIJADOS`, con un test que los une a `MINIMOS_TEXTO`: mover
el umbral obliga a tocar las dos y se ve en el diff. Con eso, los cuatro mueren:

```
173: frozen=True -> frozen=False          =>  MUERTO
140: "ejemplo_pregunta": 20 -> 21         =>  MUERTO
189: frozen=True -> frozen=False          =>  MUERTO
137: "grano": 20 -> 21                    =>  MUERTO
```

### Segundo hallazgo del arnes: la campana deja mutantes vivos en el bytecode

Tras la campana, `bash harness/init.sh` salio **en rojo** con un test que
acababa de pasar:

```
E  AssertionError: `MINIMOS_TEXTO['grano']` vale 21 y este fichero fija 20
```

El fuente decia 20. El commit no habia tocado ese fichero. Y aun asi:

```
$ python -c "from etl_sigrid.domain.diccionario import MINIMOS_TEXTO; print(MINIMOS_TEXTO['grano'])"
21
desde: ...\etl_sigrid\domain\diccionario.py
```

Era el **`.pyc`**. La campana restaura el fuente pero no invalida el bytecode, y
la comprobacion de Python (tamano y fecha) no vio el cambio, asi que siguio
ejecutando el mutante. Borrar `__pycache__` lo arreglo al instante.

**Esta vez dio un falso ROJO y por eso se investigo. Al reves da un falso
VERDE**, que es el caso que no se investiga: una suite que pasa ejecutando
codigo que no es el del repositorio. Es el mismo problema de fondo que el
`aux.yaml` inversionable —lo que se prueba no es lo que se guarda—, y ninguno de
los dos lo delata la propia suite.

La campana dejo ademas **16 worktrees huerfanos** en `Temp`, que se supone que
se limpian solos.

Los dos son del arnes, no de esta feature, asi que **no los he tocado**: van con
la propuesta de abajo.

### Propuesta para el lider: el informe de mutacion invita al error

**No la he aplicado**: toca `harness/mutacion.py`, que es del arnes y no de esta
feature, y cambiar como cuenta afectaria al veredicto de features ya cerradas.
La dejo escrita porque acaba de costarnos cuatro supervivientes.

La linea de cierre es:

```
166 mutantes evaluados, 162 muertos, 0 supervivientes, 4 timeouts
```

«0 supervivientes» y «4 timeouts» en la misma frase se leen como «limpio, con
algo de ruido». Pero un timeout **no se ha evaluado**: puede ser un mutante que
la suite no caza y que ademas la cuelga. Contarlo aparte del recuento que decide
el veredicto convierte el numero que se mira en optimista.

Cuatro cambios, los cuatro baratos:

1. Que el veredicto sea **`muertos == total`**, no `supervivientes == 0`. Un
   timeout deja la campana en rojo hasta que alguien lo explique.
2. Que la linea diga **«4 SIN EVALUAR (timeout)»** en vez de «4 timeouts».
3. Que al restaurar el fuente **se borre `__pycache__`**, para que la siguiente
   ejecucion no corra sobre un mutante compilado.
4. Que los worktrees se limpien tambien cuando la campana termina bien; hoy
   quedaron dieciseis.

Si vale para cualquier proyecto —y vale—, la regla de propagacion obliga a
portarlo a `arnes-base` en el mismo trabajo.

## Evidencias tras la sexta review (bloques F y G completos)

Numeros medidos, no estimados.

| Evidencia | Valor | Como se obtiene |
|---|---|---|
| **Tests ejecutados** | **1496 pasan, 0 fallan**, 82 saltados (759 de ellos son de F-006) | `bash harness/init.sh` |
| **Tiempo de la suite** | **~45 s** el subconjunto de F-006; **144,5 s** la suite entera dentro de `init.sh`, que corre bajo `coverage` | salida de pytest |
| **Cobertura de las lineas cambiadas** | **99,0 %** (715 de 722; umbral 80 %, nivel `critico`) | linea `PUERTA COBERTURA` de `bash harness/init.sh` |
| **Mutantes generados / supervivientes** | **166 generados, 166 muertos, 0 supervivientes, 0 timeouts** en 658,6 s | `python -m harness.mutacion --feature F-006 --timeout 300` -> `progress/mutacion_F-006.md` |
| **Objetos documentados** | **102 de 102** | `config/diccionario/` |
| **Columnas descritas** | **793** | idem |
| **Trinquete `pendientes`** | **0**, desde 98 | `PENDIENTES_MAX` en `tests/test_f006_cobertura.py` |
| **Reglas duras publicadas** | **13 de 13** | `00_global.yaml` |
| **Superficie de consumo** | 47 de 102 objetos, con el **100 %** de sus columnas con significado | `cobertura_columnas` |

**Analisis de supervivientes: no queda ninguno, y esta vez el numero significa
lo que dice.** La primera tirada cerro con «162 muertos, 0 supervivientes, 4
timeouts» y **los cuatro timeouts eran supervivientes**: reevaluados de uno en
uno sobrevivieron los cuatro, estan analizados en la seccion anterior y se
cerraron con `tests/test_f006_supervivientes.py`. La segunda tirada, con
`--timeout 300` y sin nada mas corriendo en la maquina, evalua los 166 y los
mata todos.

Las siete lineas cambiadas sin cubrir son ramas de guarda redundantes con otras
ya ejercitadas dentro del cargador; ninguna sobrevivio a la mutacion.

### Verificaciones `MANUAL (humano)` pendientes

Ninguna de esta tanda se puede hacer desde aqui, y ninguna se ha intentado:
**ningun agente ha abierto conexion a la base ni a Azure**, porque el `.env` de
este puesto apunta a `psql-albaranes-rs9k2`, el servidor compartido con
`albaranes` y `partes` en produccion.

| Tarea | Que hay que hacer |
|---|---|
| **T19** | `python main.py publicar-diccionario` contra la BBDD real y comprobar el contrato de `_meta` |
| **T27** | `check-diccionario` contra el catalogo real, y la consulta de unicidad por objeto |
| **T32**–**T34**, **T38** | Los bloques de permisos y firewall, que necesitan firma |
| **T37** | Actualizar `azure-apps/datamart_seg_anual.md` |
| **T39** | Pasar las 18 preguntas de la bateria contra el diccionario publicado |

---

# Septima pasada · los trece defectos

RECHAZADO por **trece afirmaciones publicadas que el SQL o el origen
desmienten**. Corregidas las trece, y con ellas cinco cosas mas que salieron al
derivar.

## 1. `R-SIGRID-CON` negaba un campo que existe

La regla decia que `cod`, `res` y `fec` viven en `con` «**no en la tabla
especifica**». Eso es un **patron dominante, no una ley**, y la regla es
`bloqueante` y va adjunta a las 31 fichas de `raw`.

Verificado en la fuente, no de memoria:

- `sigrid_tablas.md:16542` da **`obr.res = "Nombre completo"`**, y `raw.obr` se
  ingiere con `exclude_columns: []`: la columna esta cargada en Postgres.
- **`prv.cif` = "CIF/NIF"** y `prv.raz` = "Razon social", con **doble
  verificacion**: el PDF y nuestro propio SQL, que en
  `maestro/02_proveedores.sql:28` toma `p.cif` y `p.raz` **de `raw.prv`** y de
  `raw.con` solo `cod` y `res`.
- **`cen.res` = "Reparto nombre"**, que ademas **no** es el nombre del centro:
  el que publica `cierre` sale de `con.res` por un alias distinto.

Barri las filas de entidad de `sigrid_tablas.md` y las tablas «Propiedades de
`con`» con campos propios son **siete**: `obr`, `prv`, `cen`, `ctr`, `com`,
`dca` y `dcf`. La regla las nombra ahora una a una, y las fichas de `obr`, `prv`
y `cen` lo repiten, **porque quien lee solo la ficha tambien se estrella**.

**Lo que NO se pudo derivar, y se dice en vez de fingirlo.** Intente extraer esa
lista en tiempo de test y `sigrid_tablas.md` **no se deja parsear de forma
fiable**: es la conversion literal de un PDF de 380 paginas, y el segmentador
daba resultados distintos segun como se detectara la fila de entidad —llegaba a
mezclar campos de entidades vecinas, que es como aparecieron unos `res`/`fec`
atribuidos a `prv` que en realidad son de `prvblo` y `prvces`—. La lista queda
escrita en `tests/test_f006_regla_de_oro.py` con el motivo al lado. Una
derivacion que no se sostiene es peor que una constante revisable.

## 2. Las 31 fichas describian una carga que no ocurre

18 decian «incremental por `tiemod`» y 13 «se recarga entera». **Ninguna de las
dos pasa.** `ingest_raw_step.py`:

```python
if self._full_refresh:
    pg.truncate_table("raw", spec.target_table)
    last_id_already = 0
else:
    last_id_already = pg.get_max_id("raw", spec.target_table, spec.id_column)
...
tiemod_col = spec.incremental_column if spec.incremental_column in col_names else None
```

Es **append por `MAX(ide)`** para las 31, y `incremental_column` **no gobierna la
carga**: solo vuelca `_source_tiemod`, y solo si la columna existe. La
consecuencia, que es lo que hay que saber al usar el dato: **una fila modificada
en Sigrid no se refresca nunca**, y una borrada alli se queda aqui. El `TRUNCATE`
solo con `--full-refresh`, que `run-all` no pasa.

**La causa de fondo es mia y es la peor de la tanda**: yo *si* derive esto, pero
**de la fuente equivocada**. Contraste contra `config/tables_sigrid.yaml`, que es
justamente el documento que miente —declara `incremental_column: tiemod` en
tablas que ni la tienen—, y me lleve 31 fichas en verde afirmando algo falso. La
leccion: **derivar de la fuente equivocada es tan malo como no derivar**. La
fuente de «como se carga» es el codigo que carga, y ahi se contrasta ahora, con
un test que se pone en rojo si el paso cambia de estrategia.

No documento **que tablas tienen `tiemod`**, y tampoco lo finjo: esa pregunta
solo la responde el catalogo de Sigrid, que no es parseable, o la base, que no
se toca.

## 3. Veinticuatro punteros a objetos que no existen

`compras.documentos` y `compras.fact_linea` no aparecen en ningun SQL. Los
reales son `compras.contratos`, `compras.albaranes`, `compras.facturas` y
`compras.fact_compras_linea`. Como **todo el argumento de DA-2** es «no
consultes `raw`, ve aguas abajo y la ficha te dice donde», el puntero roto vacia
de contenido el `motivo_no_consumo`.

Se **deriva**: ningun texto publicable puede citar un `esquema.objeto` que el
diccionario no fiche. El detector encontro **24, once mas que la review**, porque
tambien mira `descripcion`; y uno que la review no vio, en `retenciones`, de una
tanda ya aprobada. Dos falsos positivos suyos —una ruta de fichero y un comodin
`compras.v_*`— se acotaron con su test.

## 4 a 7. Las trampas de `stg`

- **`stg.presupuesto` es ACUMULADO A ORIGEN en los ambitos reales**, y marcaba
  sus tres medidas `agregacion: suma`. Confirmado en `08_plan_mensual.sql`, que
  desacumula por diferencia con la fase anterior
  (`cantidad - COALESCE(LAG(cantidad), 0)` bajo `ambito_id IN (3, 7)`). Pasan a
  `ultimo_valor`, con el aviso en cada medida, en la descripcion y **en el
  grano**, que es donde se mira antes de escribir un `SUM`.
- **Las versiones master no estaban** en esa ficha, aplicando igual que en
  `plan_mensual`: en los ambitos 8 y 11 hay una fila por version.
- **`stg.fases.anio`/`.mes`** decian derivarse de la fecha de inicio y
  `05_fases.sql` los copia de `f.ano`/`f.mes`, campos **independientes**. Y no
  es cosmetico: `08_plan_mensual.sql` exige que no sean nulos, asi que una fase
  sin ellos **no aparece** en el seguimiento. La ficha lo dice ahora.
- **`stg.partidas.capitulo_raiz_id`** tenia el nulo invertido: en la raiz
  `p.ide AS capitulo_raiz_id`, asi que nunca es NULL y
  `WHERE capitulo_raiz_id IS NULL` devuelve cero filas. Se dice como preguntarlo
  bien.

## 8. La reincidencia, y el filtro que la dejo pasar

`maestro.obras.cliente_id` declaraba un nulo imposible —`o.entide AS cliente_id`
sin `NULLIF`—, **el mismo defecto de la tercera pasada**. El guardian escrito
entonces filtraba por `endswith("_ide")` y `maestro` usa `_id`.

**Se arregla el filtro, no el caso.** Al ampliarlo a los dos sufijos y a todas
las fichas —no solo vistas— marcaba **seis**, y solo **dos** eran ciertos. Las
dos derivaciones que lo acotan:

- Un alias que llega por **`LEFT JOIN`** puede ser NULL sin `NULLIF`: lo produce
  el join. Se leen los alias y se distingue.
- **`_proyeccion_de` buscaba en todo el fichero**, y `compras/01_documentos.sql`
  construye **seis objetos seguidos**: acusaba a `compras.albaranes.contrato_id`
  leyendo el `c.ide AS contrato_id` de `compras.contratos`, cuando la linea de
  `albaranes` es `NULLIF(a.ctride, 0)` y esta bien. Ese fallo estaba debilitando
  otras comprobaciones que comparten el ayudante.

Queda `retenciones.movimientos.documento_id`, que **no** se marca: sale de una
vista, no de un alias de `raw`. El limite esta escrito junto al codigo.

## 9. El puntero de DA-2, donde el MCP lo lee

La contrapartida de documentar `raw` solo a nivel de objeto era remitir al
diccionario de campos. El puntero estaba en la entrada de **esquema**, y
`describir_tabla('raw.dca')` devuelve **la ficha**. Va en las 31, con el `grep`
exacto del bloque.

**Es la tercera vez en esta feature que algo cierto esta escrito donde no
llega**: dos veces en comentarios YAML y ahora en el bloque equivocado. El test
lo comprueba en la ficha.

## 10 a 13. Pipeline, no-vacuidad y deuda

- **`R-FRESCURA-MANUAL`** citaba un pipeline sin `publicar_diccionario`. En vez
  de arreglar la lista, **se ancla** a `main.build_pipeline_steps`, y de paso
  pasa a nombrar los pasos como se llaman en `_meta.v_frescura.paso`.
- **La comprobacion de columnas excluidas pasaba en vacio en 11 fichas**
  (`citadas <= excluidas` se cumple sola con `citadas` vacio). Ahora cada ficha
  dice **el numero exacto**, que no se puede escribir en vacio.
- La deuda «que puede viajar», las seis: la guarda de los meses oficiales en
  `fn_master_fecha_efectiva` —que es media regla: solo corrige con **doble
  evidencia**—, la cardinalidad `1:N` de `version_master_vigente`,
  `total_incurrido` llegando **tambien en el ambito 7**, `dec_cantidades`
  gobernando el redondeo **del importe** y no de `cantidad`, las **referencias
  polimorficas** (`docoriide` + `docoritip`) como sexto punto de la regla de oro,
  y el comentario que seguia diciendo «las DOCE reglas».

## El barrido, que ya no se hace leyendo

Tres rechazos han venido de una afirmacion corregida en un campo y viva en el de
al lado, asi que el barrido se hizo **a maquina** sobre las 102 fichas. Cazo
**la hermana exacta del defecto 7**: `stg.partidas.capitulo_raiz_cod` repetia la
mitad falsa («La propia fila es el capitulo raiz»). Tiene ya su test.

Cazo tambien una ambiguedad en `mart.v_pbi_cp_tipologia.cp_real`, que decia
«acumulado» queriendo decir «sumado sobre la ventana»: no es el acumulado a
origen de `stg.presupuesto`, y ahora lo distingue explicitamente.

Las tres relaciones `1:1` hacia una clave sustituta que el barrido senala siguen
siendo **ciertas**, por el motivo ya escrito en la tanda anterior: en `mart` esas
claves son BIGSERIAL que cambian en cada build, la vista es una pasarela fila a
fila, y el `1:1` es cierto aunque la clave de negocio sea la combinacion estable.

## Evidencias tras la septima review

Numeros medidos, no estimados.

| Evidencia | Valor | Como se obtiene |
|---|---|---|
| **Tests ejecutados** | **1758 pasan, 0 fallan**, 127 saltados (960 de ellos son de F-006) | `bash harness/init.sh` |
| **Tiempo de la suite** | **~48 s** el subconjunto de F-006; **~150 s** la suite entera dentro de `init.sh`, que corre bajo `coverage` | salida de pytest |
| **Cobertura de las lineas cambiadas** | **99,0 %** (715 de 722; umbral 80 %, nivel `critico`) | linea `PUERTA COBERTURA` de `bash harness/init.sh` |
| **Mutantes generados / supervivientes** | **166 generados, 166 muertos, 0 supervivientes, 0 timeouts** en 711,3 s | `python -m harness.mutacion --feature F-006 --timeout 300` |
| **Objetos documentados** | **102 de 102** | `config/diccionario/` |
| **Columnas descritas** | **793** | idem |
| **Trinquete `pendientes`** | **0** | `PENDIENTES_MAX` en `tests/test_f006_cobertura.py` |
| **Reglas duras publicadas** | **13 de 13** | `00_global.yaml` |

**Analisis de supervivientes: ninguno.** La campana se lanzo **borrando
`__pycache__` a mano antes**, como pidio el lider: `harness/mutacion.py` no se ha
tocado —el defecto es **F-041** y se arregla fuera de esta feature—, asi que sin
esa limpieza previa el numero se mide con un mutante potencialmente vivo en el
bytecode. Es una salvedad de la herramienta, no del resultado, y queda dicha.

Los siete tests nuevos de la tanda anterior (`test_f006_supervivientes.py`) matan
los cuatro mutantes que en su dia se contaron como «timeout»; esta campana los
evalua y los mata, ya sin margen de duda.

Las siete lineas cambiadas sin cubrir son ramas de guarda redundantes dentro del
cargador; ninguna sobrevivio a la mutacion.

### Comprobaciones derivables anadidas en esta pasada

Cinco, y las cinco existen porque el defecto que cerraban estaba **declarado a
mano donde habia una fuente comprobable**:

| Comprobacion | Contra que deriva | Que caza |
|---|---|---|
| `test_f006_punteros.py` | el propio diccionario | citar un `esquema.objeto` que no existe (**24** encontrados) |
| `test_f006_raw_ingesta.py` | `ingest_raw_step.py` | describir una carga que el paso no hace, y callar las columnas excluidas |
| `test_f006_regla_de_oro.py` | `maestro/02_proveedores.sql` | que la regla afirme en absoluto un patron, y que no ubique el CIF |
| `test_f006_stg_trampas.py` | `sql/stg/*.sql` | acumulado a origen, origen de `anio`/`mes`, nulos invertidos |
| guardian de nulos ampliado | los alias de `raw` del SQL | un `nulo_significa` imposible, en **las dos** convenciones de sufijo |

Y la del pipeline citado, dentro de `test_f006_reglas.py`, que ancla la evidencia
de `R-FRESCURA-MANUAL` a `main.build_pipeline_steps` en vez de a una lista
escrita a mano.

### Limites declarados, no descubiertos luego

- **`sigrid_tablas.md` no es parseable de forma fiable**, asi que la lista de
  tablas con campos propios y la pregunta «que tablas tienen `tiemod`» no se
  derivan: la primera queda como constante revisable con su motivo, y la segunda
  **no se documenta en ninguna ficha**.
- El guardian de nulos **no analiza expresiones compuestas** (`COALESCE`,
  `CASE`): pueden producir NULL por muchas vias y decidirlo desde el texto
  marcaria de mas.
- El guardian **no se aplica fuera de los alias directos de `raw`**, asi que un
  objeto que reexporte una columna de Sigrid a traves de `stg` no se comprueba
  ahi. `stg` aplica el `NULLIF` en el punto de entrada, que es donde toca.
- Sigue **sin ejecutarse la bateria de 18 preguntas** (T39) ni
  `check-diccionario` (T26): que una ficha sea correcta no demuestra todavia que
  sea suficiente.

---

# Octava pasada · el criterio nuevo, y lo que hubo que recortar

RECHAZADO porque **las dos correcciones centrales de la tanda anterior
sustituyeron una afirmacion falsa por otra**. No fue descuido: las dos estaban
escritas **por reconstruccion** y contrastadas despues contra una fuente que
habla de otra cosa. El lider fijo el criterio y este informe lo aplica.

## El criterio, y lo que cambia

> **Si una afirmacion no es derivable de la fuente que gobierna el hecho, no se
> escribe.** Ni reformulada ni matizada. Se omite, y si el hueco importa se
> declara como hueco.

Lo importante es la segunda mitad —**la fuente que gobierna**—, porque yo si
derivaba, y aun asi acerte dos veces mal:

| Pasada | De donde derive | Que gobierna esa fuente | Resultado |
|---|---|---|---|
| 7ª | `config/tables_sigrid.yaml` | que columna se vuelca a `_source_tiemod` | «incremental por `tiemod`». **Falso** |
| 8ª | `ingest_raw_step.py` | como carga el comando segun la bandera | «append; lo modificado no vuelve». **Falso** |
| ahora | `Dockerfile` | **que se ejecuta de noche** | recarga entera |

La tabla de fuentes queda escrita en `tests/test_f006_fuente_que_gobierna.py` y
en la cabecera de `raw.yaml`, para que la proxima afirmacion empiece por elegir
la fuente y no por escribir la frase.

## A · La carga de `raw`

El `Dockerfile` arranca `CMD ["run-all", "--full"]`, con el comentario «el job
nocturno SIEMPRE full (el incremental pierde UPDATEs)». Y
`infra/80_create_job.ps1` avisa de que **el alcance de la carga nocturna esta ahi
y en ningun sitio mas**. Asi que:

- **de noche la tabla se recarga entera** (`TRUNCATE` y todo de nuevo), y un
  cambio hecho ayer en Sigrid esta aqui esta manana;
- **sin `--full`** —el valor por defecto, tipico al lanzar `ingest` a mano— la
  carga es append por `MAX(ide)` y lo modificado no vuelve a leerse.

Las 31 fichas dicen las dos cosas y en ese orden. El test se ancla al `CMD`: si
la imagen deja de pasar `--full`, se pone en rojo.

**Y la bandera.** Las fichas citaban `--full-refresh` **31 veces** y esa opcion
no existe: la real es `--full`. Ahora las banderas que cita una ficha se
contrastan contra los `click.option` de `main.py`, con su test de control.

## B · La regla de oro: de siete excepciones, una

`cen.res` **no existe**. El «Reparto nombre» es de `cenrep`, tabla que ni se
ingiere. Es el mismo defecto por el que se rechazo la septima pasada, movido de
tabla, y lo cometi **con el mismo metodo**: segmentar el PDF.

Lo medi, y el metodo es indefendible: mi segmentador da a `obr` un bloque de
**1252 lineas** con once `cod` y veintiun `res` dentro, porque se traga las
entidades intermedias; y mete `cenrep` dentro de `cen`. **`azure-apps/sigrid_tablas.md`
no es una fuente de la que derivar.** Queda dicho en la regla, en la cabecera de
`raw.yaml` y en el docstring del test.

Habia una fuente derivable **sin usar: nuestro propio SQL**, que no correria
contra una columna inexistente. El barrido da **once tablas** cuyos campos
propios el ETL lee sin pasar por `con`:

```
auxmun(res)  auxobramb(cod,res)  auxobrcla(res)  auxobrtip(res)  auxpro(res)
conext(cod)  dcfpro(res)  obrfas(res)  obrfasamb(fec,res)
obrparpar(cod,res)  prv(cif,raz)
```

`obrparpar.cod` y `.res` son el codigo y la descripcion de la partida: se leian
a diario y la regla decia que estaban en `con`. Y cuatro tablas
—`auxobramb`, `obrfas`, `obrfasamb`, `obrparpre`— **no se unen a `raw.con` en
ningun SQL**, asi que el JOIN que la regla sugeria no existe para ellas.

La lista la **genera** un test comparando el punto 3 de la regla con el barrido:
si divergen, rojo. Escrita a mano acerto 1 de 7 y se dejo 16.

## Lo que se ha RECORTADO, y por que

Aplicar el criterio obliga a borrar contenido publicado. Se recorta y se dice:

| Recortado | Motivo |
|---|---|
| «`cen` tiene un `res` propio, Reparto nombre» | **inventado**: es de `cenrep` |
| «`obr.res` es "Nombre completo"» | solo lo dice el PDF, y el PDF no es derivable |
| `ctr`, `com`, `dca`, `dcf` como excepciones | falsos positivos del mismo metodo |
| `ctr.entcif` / `dca.entcif` / `dcf.entcif` (que la review sugeria anadir) | **no se anade**: misma fuente, mismo riesgo |
| «lo modificado en Sigrid no se refresca nunca» | cierto solo sin `--full`, y de noche va con `--full` |

Las fichas de `obr` y `cen` dicen ahora **lo que el SQL demuestra** —de donde
toma el datamart cada campo— y declaran el hueco: que exista o no un campo con
ese nombre en Sigrid no se afirma aqui, y para eso esta el puntero al catalogo.
El diccionario es mas pequeno y no miente.

## C · El quinto y el sexto caso del patron de la copia

**Quinto**: la cabecera de `raw.yaml` conservaba intacta la frase que la septima
pasada rechazo, y ocho lineas despues declaraba ser «la misma regla» que
`R-SIGRID-CON`. Los barridos anteriores no podian verla: miran el contenido
publicable, y `yaml.safe_load` **descarta los comentarios**.
`tests/test_f006_copias.py` mira el **texto crudo** de los diez ficheros, con la
lista de frases rechazadas y la pasada que rechazo cada una.

**Sexto, cazado por mi antes de publicarlo**: al recortar la regla, las fichas de
`obr` y `cen` seguian diciendo lo mismo **con otras palabras** —«tiene un `res`
propio»—, asi que el barrido de frases literales no las veia. El detector nuevo
no busca una frase: comprueba **la afirmacion**, y exige que el barrido del SQL
respalde cualquier campo propio que una ficha se atribuya.

## D · Lo demas

- **`_source_tiemod`** (`stg.yaml`) conservaba «que usa la ingesta incremental».
  Ademas de retirarlo, se dice lo que importa y nadie decia: es el `tiemod` que
  la fila tenia **al entrar**, no una marca de modificacion vigente.
- **`dec_cantidades`** afirmaba gobernar `ROUND(ROUND(can, decc) * ...)`. El SQL
  real es `ROUND(can * ROUND(pre, decp), deci)`: **`decc` no interviene**. El
  origen del error es reconocible y lo arreglo tambien: los **comentarios de
  `06_presupuesto.sql`** repetian la formula con `decc` y la NOTA de cuatro
  lineas despues los desmentia. Copie el comentario en vez de leer el codigo.
  Es la deuda «comentarios del SQL que mienten» mordiendo por primera vez.

  **Intente corregir esos comentarios y no debo**: el guardian de F-011 salto
  —«F-006 ha tocado SQL de negocio»— y tiene razon, porque acotar ese fichero es
  F-025 y exige su prueba de equivalencia antes de cambiar lo que ve Power BI.
  Revertido. **No se debilita un guardian para dejar pasar un cambio propio**;
  queda propuesto al lider. La ficha si avisa de que algun comentario del SQL
  repite una formula que el codigo no ejecuta, y de que manda el codigo.
- **Cuatro `nulo_significa` imposibles en `stg.partidas`**, incluido el que se
  acababa de «corregir»: la rama raiz filtra `p.cod IS NOT NULL AND p.cod <> ''`,
  asi que ni `codigo_partida` ni `capitulo_raiz_cod` ni `ruta_capitulos` ni
  `nivel` pueden ser nulos. Los cuatro pasan a decirlo.
- **La plantilla de exclusiones era falsa en 19 fichas** —«textos largos,
  observaciones e imagenes» aplicado a todas, cuando en `pag` la unica es
  `blores`—, y en `dca`/`dcf` sustituyo un texto que **era exacto**. La
  caracterizacion se **genera** ahora de las columnas concretas.
- **`stg.presupuesto`: me pase corrigiendo.** Bajar las tres medidas a
  `ultimo_valor` contradecia el uso real —`cierre/02_build_fact.sql` hace
  `SUM(importe_oficial)` con la fase fija— y sus propios ejemplos. Lo no sumable
  es **la dimension `fase_num`**, no la columna: quedan en
  `suma_solo_dentro_del_mes`, que en los ambitos reales es literalmente el mes.
  Se anade que **`fase_num = 0` es el "Previsto" vivo**, no un mes, de donde sale
  el fallback del cierre.
- **La receta `grep`** de las 31 fichas prometia aislar el bloque y no lo hace;
  ahora dice que devuelve tambien filas de otras tablas y como reconocer la de
  entidad.
- **La regla decia «cinco cosas» y numeraba seis.** Hay un test que compara el
  anuncio con los puntos numerados.

## E · El guardian de nulos, el unico detector sin control

Rectificacion del reviewer que hago mia: el guardian ampliado evalua 15 fichas y
**30 columnas candidatas de las que ninguna llega al `assert`**. No es inutil
—es la alarma para el dia que alguien publique un `nulo_significa` sobre una
columna que trae 0— pero **un detector en cero sin control es indistinguible de
uno roto**, y ya nos paso con la comprobacion de exclusiones, que pasaba en
vacio en once fichas.

Tiene ya su `test_..._control_...`, como los otros seis del fichero: ejercita el
caso en el que debe morder (`o.entide AS cliente_id` desde `FROM raw.obr o`) y
los dos recortes que hoy lo dejan en cero —el alias de `LEFT JOIN` y la
expresion compuesta—.

## Evidencias tras la octava review

Numeros medidos, no estimados.

| Evidencia | Valor | Como se obtiene |
|---|---|---|
| **Tests ejecutados** | **1809 pasan, 0 fallan**, 127 saltados (1011 de ellos son de F-006) | `bash harness/init.sh` |
| **Tiempo de la suite** | **~45 s** el subconjunto de F-006; **~155 s** la suite entera bajo `coverage` | salida de pytest |
| **Cobertura de las lineas cambiadas** | **99,0 %** (715 de 722; umbral 80 %, nivel `critico`) | linea `PUERTA COBERTURA` |
| **Mutantes / supervivientes** | **166 generados, 166 muertos, 0 supervivientes, 0 timeouts** en 741,5 s | `python -m harness.mutacion --feature F-006 --timeout 300` |
| **Objetos documentados** | **102 de 102** | `config/diccionario/` |
| **Trinquete `pendientes`** | **0** | `PENDIENTES_MAX` |
| **Reglas duras publicadas** | **13 de 13** | `00_global.yaml` |

Campana lanzada **borrando `__pycache__` a mano antes**, como en la tanda
anterior: `harness/mutacion.py` sigue intacto —su arreglo es **F-041**— y sin esa
limpieza previa el numero se mide con un mutante potencialmente vivo en el
bytecode.

### Comprobaciones derivables anadidas en esta pasada

Todas contra **la fuente que gobierna el hecho**, que es la leccion de la tanda:

| Comprobacion | Fuente que gobierna | Que caza |
|---|---|---|
| el job nocturno recarga entera | `Dockerfile` (`CMD`) | describir una carga que no es la que corre de noche |
| `--full` trunca y recarga | `ingest_raw_step.py` | que cambie el significado de la bandera |
| las banderas citadas existen | `click.option` de `main.py` | publicar un comando inejecutable (pasaba 31 veces) |
| la regla declara los campos derivados | barrido de `sql/**` | una lista de excepciones escrita a mano (acerto 1 de 7) |
| las tablas que no cuelgan de `con` | idem | sugerir un JOIN que no existe |
| ninguna ficha se atribuye un campo no derivado | idem | la misma afirmacion dicha con otras palabras |
| frases rechazadas, **texto crudo** | las propias revisiones | la copia escondida en una cabecera |
| control del guardian de nulos | — | un detector en cero indistinguible de uno roto |

Cinco de las ocho llevan su **test de control**, y el guardian de nulos ya tiene
el suyo: era el unico detector del fichero sin el, y ademas estaba en cero.

### Limites declarados, no descubiertos luego

- **`azure-apps/sigrid_tablas.md` no es una fuente de la que derivar.** Lo que
  solo dice ese documento **no se afirma en ninguna ficha ni en la regla**. La
  regla lo declara como hueco y remite alli para consultar a mano.
- El guardian de nulos **no analiza expresiones compuestas** ni sale de los
  alias directos de `raw`, y **hoy no llega ninguna columna a su `assert`**: es
  una alarma para el futuro, no una comprobacion activa. Dicho en su test.
- La caracterizacion de las columnas excluidas agrupa por familias deducidas del
  **nombre** de la columna; lo que no encaja se cuenta como «sueltas entre
  textos y campos auxiliares» en vez de inventarle categoria.
- Sigue **sin ejecutarse la bateria de 18 preguntas** (T39) ni
  `check-diccionario` (T26). Que una ficha sea correcta no demuestra todavia que
  sea suficiente.
- **Los comentarios de `06_presupuesto.sql` siguen mintiendo**: corregirlos es de
  F-025 y el guardian de F-011 lo impide con razon. Propuesto al lider.

---

# Novena pasada · dos derivaciones con el mismo error no son una comprobación

RECHAZADO. Y el aviso que abre la review nos afecta a los dos: la verificación
«independiente» del reviewer **no lo era**. Reprodujo mi lista «con su propio
derivador» y coincidía **porque su script tenía mi mismo bug**.

## El bug, y el vicio que lo dejó pasar

El derivador mapeaba alias→tabla con un `dict` **por fichero**. En
`compras/01_documentos.sql` las tres tablas de línea comparten el alias `l`:

```
FROM raw.ctrpro l    (61)     l.res AS descripcion
FROM raw.dcapro l    (126)    l.res AS descripcion
FROM raw.dcfpro l    (179)    l.res AS descripcion
```

El `dict` se quedaba con la última, así que **`ctrpro.res` y `dcapro.res`
desaparecían** de la derivación y de la regla que la copia. El alias es local a
la **sentencia**, no al fichero. Mismo vicio que ya apareció en
`_proyeccion_de`, que leía el fichero entero cuando ese fichero construye
**seis** objetos.

**Pero el bug no es lo grave. Lo grave es que mis pruebas no podían verlo.**
Fijaban la coherencia **regla↔derivador**, no la **corrección del derivador**:
si el derivador se equivoca, la regla copia el error y el test sale verde por
construcción. Ahora hay tres controles que **no llaman al derivador sobre el
repositorio**: uno con SQL fabricado y la respuesta calculada a mano, otro que
contrasta el fichero real **por otra vía** —líneas y `FROM`, sin usar
`alias_de_raw` ni `sentencias`— y otro sobre el troceo.

## GRAVE 1 · La copia, séptima vez, y publicada

`00_global.yaml` → `convenciones.identidad_sigrid` conservaba la frase rechazada
en la 7ª pasada —«el código, el nombre y la fecha viven en `con`, no en la
extensión»— **doce líneas por encima del punto 3 de la regla que la corrige**, y
con lista divergente: ocho tablas frente a diez.

No es un comentario: `convenciones` entra en `global_raw`, que el dominio
describe como «lo que se sirve tal cual». **Se publica.** Mis barridos miraban
fichas y reglas; `convenciones` no es ninguna de las dos.

La convención pasa a **remitir a la regla en vez de repetirla**, y el barrido
cubre ya **toda la superficie publicable**. La regla de mantenimiento que ya
escribí en la cabecera de `raw.yaml` y no apliqué aquí: *un texto que repite una
afirmación publicada es una copia esperando a divergir*.

## La superficie de consumo

- **`es_hoja`** se calcula `nivel >= 2 OR codigo_partida LIKE '%.%'` y la ficha
  prometía «para no sumar dos veces al agregar por la jerarquía». Un capítulo de
  nivel 2 con descendientes —`CI.2`, con `CI.2.1` debajo— sale marcado como
  hoja, así que fiarse produce **justo el doble conteo que decía evitar**. Las
  **dos** vistas que la publican dicen ya lo que la heurística hace, para qué
  sirve de verdad y qué hacer para agregar sin duplicar.
- **`entidad_cif`**, en cuatro fichas de `retenciones`: decían «la entidad no
  tiene CIF», y `retenciones/01_movimientos.sql:59` proyecta `prv.cif` **en
  crudo**, sin el `NULLIF(TRIM(...))` de los dos maestros. Un proveedor con el
  CIF en blanco trae **cadena vacía**; el NULL solo aparece cuando el
  `LEFT JOIN` no casa, o sea cuando la entidad no es proveedor. Las cuatro dicen
  ya cómo distinguir los dos casos.
- **`stg.plan_mensual`** marcaba sumables cuatro columnas acumuladas a origen
  mientras sus doce gemelas de `mart` estaban en `ultimo_valor`, y
  `R-IMPORTE-MES` es **bloqueante** y la incluye en su ámbito. Que una regla
  bloqueante conviva con fichas que la contradicen es lo peor que puede pasarle
  a este diccionario. No se corrigió por lista: **se deriva la coherencia** —la
  misma columna, en dos objetos del ámbito de una regla, es el mismo número y se
  declara igual—, con su control para que un ámbito encogido no deje la
  comprobación en vacío.

## El guardián deja de perseguir sufijos

Tres casos de la misma familia, cada uno escapado por el nombre:
`cliente_ide` (3ª), `cliente_id` (7ª), `entidad_cif` (9ª). Ampliar la lista de
sufijos era perseguir el caso: **mientras el guardián mire nombres, habrá un
cuarto**.

Ahora comprueba la afirmación real, y ya no hay lista que mantener:

> una columna proyectada **en crudo** desde `raw` que declara `nulo_significa`

Al quitar el filtro aparecieron **cuatro** casos que ningún sufijo habría
cazado: `maestro.proveedores.razon_social` y las tres de `stg.ambitos`
(`codigo`, `descripcion`, `clase_sigrid`).

## Y un punto ciego que el propio mensaje del guardián ocultaba

El guardián resolvía el origen por el `CREATE`, y `stg.partidas`, `stg.fases` y
`stg.plan_mensual` se declaran en `stg/01_ddl.sql` —tipos, ni un `raw.` a la
vista— y se pueblan con `INSERT ... SELECT` en otro fichero. **Las saltaba con
el mensaje «no lee directamente de `raw`», que era falso.** Tres de los objetos
más grandes de `stg` sin comprobar, y el motivo publicado en el `-rs` era otro.

Dos arreglos: se localiza también el fichero que **puebla** cada objeto, y el
bloque arranca al principio de la **sentencia**, porque en `04_partidas.sql` el
`WITH RECURSIVE` con las proyecciones va **antes** del `INSERT`.

Aparecieron seis nulos imposibles más, y uno obliga a corregir un test **mío**
de la 7ª pasada, escrito con la premisa al revés: `stg.fases.anio` y `.mes` son
enteros de Sigrid proyectados en crudo, **nunca son NULL** y «sin informar»
llega como **0**. La consecuencia es la contraria de la que publiqué: el filtro
`f.anio IS NOT NULL` de `08_plan_mensual.sql` **no descarta nada**, y una fase
con `anio = 0` entra igual. La ficha lo dice, porque quien lea ese `WHERE` va a
suponer lo contrario.

Saltados: de **45 a 40**, y los que quedan por un motivo que ahora es cierto.

## Evidencias tras la novena review

| Evidencia | Valor | Como se obtiene |
|---|---|---|
| **Tests ejecutados** | **1828 pasan, 0 fallan**, 122 saltados (1030 de F-006) | `bash harness/init.sh` |
| **Cobertura de las lineas cambiadas** | **99,0 %** (715 de 722; umbral 80 %, nivel `critico`) | linea `PUERTA COBERTURA` |
| **Mutantes / supervivientes** | **166 generados, 166 muertos, 0 supervivientes, 0 timeouts** en 812,1 s | `python -m harness.mutacion --feature F-006 --timeout 300` |
| **Saltados del guardian de nulos** | **de 45 a 40** | el punto ciego de `stg` cubierto |
| **Objetos documentados** | **102 de 102**, `pendientes` en 0 | `config/diccionario/` |

Campana lanzada **borrando `__pycache__` a mano antes**: `harness/mutacion.py`
sigue intacto —su arreglo es **F-041**— y sin esa limpieza el numero se mide con
un mutante potencialmente vivo en el bytecode.

### Comprobaciones anadidas, y esta vez con control propio

La leccion de la pasada es que **una comprobacion sin control independiente no
comprueba nada**, asi que cada derivador nuevo lleva el suyo:

| Comprobacion | Su control |
|---|---|
| derivador de campos propios de `raw` | SQL fabricado con alias repetido y respuesta calculada a mano; y contraste del fichero real **por otra via** (lineas y `FROM`, sin usar el derivador) |
| troceo en sentencias | dos sentencias con el mismo alias apuntando a tablas distintas |
| coherencia de `agregacion` en el ambito de una regla | que el ambito siga cubriendo `stg` y `mart`, para que no pase en vacio |
| `es_hoja` es una heuristica | que el SQL siga calculandola asi, para poder devolver la promesa si cambia |
| localizador del fichero que **puebla** cada tabla | las tres tablas de `stg` que el guardian se saltaba |
| barrido de frases rechazadas | ahora sobre **toda la superficie publicable**, incluidas `convenciones` y los comentarios |

### Limites declarados

- **`azure-apps/sigrid_tablas.md` sigue fuera** de las fuentes de las que se
  deriva. Lo que solo dice ese documento no se afirma en ninguna ficha.
- El guardian de nulos **no analiza expresiones compuestas** (`COALESCE`,
  `CASE`) ni columnas que llegan por `LEFT JOIN`, donde el NULL es real.
- La coherencia de `agregacion` se comprueba **dentro del ambito de cada regla**;
  dos objetos que no compartan regla pueden declarar distinto sin que salte.
- Sigue sin ejecutarse la **bateria de 18 preguntas** (T39) ni
  `check-diccionario` (T26).
- Los **comentarios de `06_presupuesto.sql`** siguen mintiendo: corregirlos es de
  F-025 y el guardian de F-011 lo impide con razon. Propuesto al lider.
