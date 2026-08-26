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

> **AVISO (16ª pasada): los números de mutación de este informe NO son evidencia.** La campaña corría en un worktree con HEAD detached, donde `test_f015_r12` falla siempre; con `-x` la suite paraba ahí y `harness/mutacion.py` contaba cualquier `returncode != 0` como mutante muerto. Se conservan como registro de lo que se declaró en cada tanda, no como prueba. Pendiente de **F-041**.

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

---

# Décima pasada · seis defectos, y por fin son finos

## Los dos que bloqueaban

### 1 · `entidad_cif` publicaba un mecanismo falso, y lo publicaba cuatro veces

`retenciones.movimientos` tiene **dos mitades** y cada una calcula el CIF de una
forma distinta:

```sql
-- PROVEEDOR (FROM raw.pag)
prv.cif                   AS entidad_cif      -- crudo, LEFT JOIN raw.prv
-- CLIENTE (FROM raw.cob)
NULL::VARCHAR(24)         AS entidad_cif      -- literal, SIEMPRE nulo
```

Mi corrección de la 9ª explicaba **solo la mitad PROVEEDOR** —«el `LEFT JOIN` no
casa»— y la aplicó a las cuatro fichas. En `CLIENTE` no hay join que no case:
hay una constante. Así que corregí cuatro copias de una explicación equivocada,
que es el patrón de la copia funcionando **a mi favor y en mi contra a la vez**:
la escribí una vez y se publicó cuatro.

Las cuatro dicen ya los dos mecanismos, y el `significado` avisa de que la
columna **solo existe en la mitad PROVEEDOR**.

### 2 · La hermana, octavo caso, entre dos fichas tocadas el mismo día

`maestro.proveedores_obra.razon_social` decía «la entidad no tiene ficha de
proveedor, **o no tiene razón social**». La segunda mitad es falsa: `pv.raz` va
en crudo, así que una razón social vacía llega como **cadena vacía**.

Y su hermana `maestro.proveedores.razon_social` **se corrigió en la tanda
anterior**, con esa misma explicación. Las dos fichas se tocaron el mismo día y
una se quedó atrás.

### Lo que las une, y es lo que se deriva

Las dos publican la misma clase de error, y no es «el NULL no puede ocurrir»
—ahí el guardián ya llegaba— sino **el NULL ocurre por otra razón**:

> sin `NULLIF`, un valor vacío del origen llega como **cadena vacía** (o como
> **0** en los enteros), nunca como NULL. Así que una ficha no puede atribuir su
> NULL a que el dato esté en blanco.

Acotado a columnas que vienen de un alias de `raw`: una que sale de otro objeto
del datamart puede haberse normalizado aguas arriba —`compras.fact_compras_linea`
toma `proveedor_cif` de `compras.contratos`, que ya aplica `NULLIF(TRIM(...))`,
y era un falso positivo—. Con su control.

## 3 · Un punto ciego por construcción, cerrado en parte y declarado

`pct_acumulado` no lo veía **nadie**: ni la lista a mano ni la derivación. La
comprobación cruzada compara la misma columna **entre objetos** del ámbito, y
`pct_acumulado` existe en uno solo. Sin pareja no hay comparación, y marcarla
`clave_sustituta` habría dejado la batería entera en verde.

**Medido: 32** de las columnas con `agregacion` del ámbito de `R-IMPORTE-MES`
aparecen en un único objeto. No es un caso raro; es un tercio largo.

Se cierra la parte derivable con una comprobación **por columna**, que alcanza a
las solitarias: *un porcentaje no se suma, ni entre partidas ni entre meses*.
Cazó `pct_acumulado` y su hermana `pct_mes`; los siete `*_pct` de `cierre` ya
estaban en `promedio`. Y **el resto del hueco queda declarado** en un test que
salta si cambia de tamaño: un hueco escrito vale más que uno que parece
cubierto.

## 4 · La defensa contra el patrón se saltaba por un salto de línea

El reviewer plantó dos frases rechazadas **plegadas** como las pliega un bloque
`>-` y el barrido pasó en verde, mientras `yaml.safe_load` las publica enteras.

Ahora se barre el fichero **crudo y** el YAML **cargado**, y hacen falta los dos
por motivos opuestos: el crudo conserva los comentarios —que `safe_load`
descarta, y donde se escondió la copia del quinto caso— y el cargado conserva
las frases plegadas. El experimento queda como control permanente.

## 5 · Dos recuentos escritos a mano, ya desfasados

«Seis casos» donde la enumeración lista dos, y «tres tablas» donde son **cinco**
—omitiendo `stg.obras`, que aportó dos de los hallazgos, y `stg.presupuesto`—.

No los he corregido: los he **sacado de la prosa**. El alcance del guardián y las
tablas pobladas fuera del DDL se **miden** en dos controles, y el número vive en
un solo sitio. Un recuento a mano en un docstring es otra afirmación que
envejece, y estas dos ya lo habían hecho en una sola tanda.

## 6 · Un ejemplo que el SQL no soporta

La ficha decía que una fase con `anio = 0` «entra igual». La conclusión —el
filtro `IS NOT NULL` es inerte— **se sostiene**, pero el ejemplo no:
`make_date(f.anio, f.mes, 1)` **aborta el build** con año 0.

Cambia el ejemplo, no la conclusión: se nombra la guarda que **sí** actúa y se
dice lo accionable, que es comparar contra `0` y no contra NULL. Un ejemplo
inejecutable es una afirmación falsa aunque la conclusión sea cierta.

## Evidencias tras la décima review

| Evidencia | Valor | Como se obtiene |
|---|---|---|
| **Tests ejecutados** | **1895 pasan, 0 fallan**, 122 saltados (1096 de F-006) | `bash harness/init.sh` |
| **Cobertura de las lineas cambiadas** | **99,0 %** (715 de 722; umbral 80 %, nivel `critico`) | linea `PUERTA COBERTURA` |
| **Mutantes / supervivientes** | **166 generados, 166 muertos, 0 supervivientes, 0 timeouts** en 738,8 s | `python -m harness.mutacion --feature F-006 --timeout 300` |
| **Objetos documentados** | **102 de 102**, `pendientes` en 0 | `config/diccionario/` |

Campana lanzada **borrando `__pycache__` a mano antes**: `harness/mutacion.py`
sigue intacto —su arreglo es **F-041**—.

### Comprobaciones anadidas, todas con control

| Comprobacion | Que caza | Su control |
|---|---|---|
| NULL atribuido a un valor vacio sin `NULLIF` | los defectos 1 y 2, que el guardian anterior no veia porque ahi el NULL **si** ocurre | el caso real (`pv.raz`), fijado |
| un porcentaje no se declara sumable | `pct_acumulado` y `pct_mes`, invisibles para la comprobacion cruzada | que haya al menos ocho porcentajes que mirar |
| barrido sobre el YAML **cargado** | frases rechazadas **plegadas**, que el barrido crudo no ve | el experimento del reviewer, plantado y comprobado |
| alcance del guardian de nulos | que un detector se degrade en silencio | mide y fija el numero |
| tablas pobladas fuera del DDL | idem, y sustituye a una lista a mano que decia tres de cinco | las deriva |

### Limites declarados, con su numero

- **La comprobacion cruzada de `agregacion` es ciega para las columnas unicas.**
  Medido: **32** de las columnas con `agregacion` del ambito de `R-IMPORTE-MES`
  aparecen en un solo objeto. Se cierra la parte derivable (porcentajes) y el
  resto queda **declarado en un test que salta si el hueco cambia de tamano**.
- El detector de atribucion solo mira **proyecciones desnudas desde `raw`**: una
  columna que sale de otro objeto del datamart puede haberse normalizado aguas
  arriba, y exigirlo alli marcaria de mas.
- `azure-apps/sigrid_tablas.md` sigue **fuera** de las fuentes de las que se
  deriva.
- Sigue sin ejecutarse la **bateria de 18 preguntas** (T39) ni
  `check-diccionario` (T26): que una ficha sea correcta no demuestra que sea
  suficiente.
- Los **comentarios de `06_presupuesto.sql`** siguen mintiendo; corregirlos es de
  F-025 y el guardian de F-011 lo impide con razon.

---

# T26 cerrado, y la tanda contra Azure BLOQUEADA en el primer paso

## T26 · la comprobación de unicidad, generada y sin ejecutar

Cierra la mitad del problema que la puerta offline no puede cubrir: sabe si la
clave nombra columnas de más, **no si es demasiado corta**. Y esa mitad se
propaga, porque la detección de fan-out **deriva** la unicidad de la clave
declarada: una clave reducida además desarma la comprobación de cardinalidades.

`etl_sigrid/infrastructure/postgres/unicidad_sql.py` + `main.py check-unicidad`.

**Alcance, derivado del diccionario y no de una lista:**

| | |
|---|---|
| Objetos de consumo (por defecto) | **47** |
| Con `--todos` | **56** |
| De ellos, con **clave compuesta** | **26** — ahí vive el riesgo |
| Saltados | 55, cada uno con su motivo |

**Qué se salta y por qué**: las funciones (no tienen filas), las fichas sin
clave, las claves sustitutas (BIGSERIAL o PK: únicas por construcción) y **las
31 de `raw`**, que se ingieren con `ensure_raw_table(..., primary_key=id_column)`
y por tanto tienen `ide` como PRIMARY KEY. Comprobarlas sería pagar un escaneo
completo por lo que el motor ya impide, y varias son de las tablas más grandes.

**Decisión de coste, que es lo que pediste justificar.** Esto corre contra
`psql-albaranes-rs9k2`, compartido con `albaranes` y `partes` **en producción**:

- **Por defecto, solo la superficie de consumo.** Es donde una clave corta
  produce un número falso en una respuesta; fuera de ahí el objeto no debería
  consultarse y su propia ficha dice a dónde ir. `--todos` es la pasada
  completa, para una ventana tranquila: `stg.plan_mensual` ronda los **29
  millones de filas** y esto es una agregación sobre cinco columnas.
- **`SET LOCAL statement_timeout` por consulta** (30 s por defecto) y
  transacción **`READ ONLY`**. `SET LOCAL` no toca la configuración del
  servidor, así que no afecta a los otros dos proyectos.
- **Nada de muestreo, y es deliberado.** Una muestra limpia **no prueba**
  unicidad, así que muestrear debilitaría la única comprobación que cierra este
  hueco. En su lugar, si el tiempo salta, el objeto se reporta **NO
  COMPROBADO** —nunca como correcto—: contar un timeout como OK convertiría el
  límite que protege el servidor en una forma de aprobar sin mirar.

**Cómo se lee un resultado vacío**, y está en el mensaje, no solo en el
docstring:

> `OK  <objeto>: los datos de hoy no contradicen la clave (…). No prueba que sea
> correcta; prueba que aun no ha colisionado.`

Una clave puede ser insuficiente y no haber colisionado todavía: basta con que
ninguna obra haya repetido aún esa combinación.

**Un duplicado dice objeto, clave, cuántas combinaciones se repiten, cuántas
filas afectan, el efecto de segundo orden sobre el fan-out y la consulta para
ver cuáles son.**

**No se ha ejecutado ninguna**: `--dry-run` imprime y no conecta, y el cliente
se prueba con dobles, como el bloque E. 15 tests.

## El bloqueo: `az` exige MFA para escribir

Con la firma del humano intenté el paso 2 (el firewall) y **paré**.

**Lo que SÍ funciona** — lectura contra Azure con el token en caché:

```
$ az account show --query "{sub:name, user:user.name}" -o tsv
Ruesma	<usuario>

$ az postgres flexible-server firewall-rule list -g rg-albaranes-dev \
    --server-name psql-albaranes-rs9k2 -o table
EndIpAddress    Name                                    StartIpAddress
--------------  --------------------------------------  ----------------
0.0.0.0         AllowAzureServices                      0.0.0.0
31.4.242.255    datamart-puesto-pgris-2026-08-17-rango  31.4.242.0
80.28.223.30    FirewallIPAddress_2026-6-16_16-42-54    80.28.223.30
68.221.221.85   caj-datamart-seg-dev                    68.221.221.85
88.26.46.154    datamart-puesto-pgris                   88.26.46.154
188.87.59.11    ClientPgris                             188.87.59.11
90.160.92.88    datamart-puesto-pgris-2026-08-18        90.160.92.88
77.211.5.255    datamart-puesto-pgris-2026-08-19        77.211.5.0
176.80.159.179  datamart-puesto-pgris-2026-08-20        176.80.159.179
```

**Lo que NO** — la escritura, que es justo la que la firma autoriza:

```
$ IP=$(curl -s https://api.ipify.org)   # 88.26.22.183
$ az postgres flexible-server firewall-rule update -g rg-albaranes-dev \
    -s psql-albaranes-rs9k2 -n datamart-puesto-pgris \
    --start-ip-address "$IP" --end-ip-address "$IP"

ERROR: SubError: basic_action V2Error: invalid_grant AADSTS50076: Due to a
configuration change made by your administrator, or because you moved to a new
location, you must use multi-factor authentication to access
'<GUID-REDACTADO>'.
    az logout
    az login --tenant "…" --scope "https://management.core.windows.net//.default"
```

**`az login` es interactivo y exige MFA**, así que no lo puede hacer un agente.
No he improvisado ninguna vía alternativa: la regla dice parar, y además esto va
contra un servidor compartido en producción.

**Y el bloqueo alcanza a toda la tanda**, no solo al firewall. La regla sigue
apuntando a `88.26.46.154` y la IP de este puesto es ahora `88.26.22.183`, que
no está en ninguna regla. Comprobado:

```
$ python -c "socket … connect(('psql-albaranes-rs9k2.postgres.database.azure.com', 5432))"
puerto cerrado: TimeoutError timed out
```

Así que **T19, el bloque H y la ejecución de T26 quedan detrás de ese `az
login`**: sin abrir el firewall no hay conexión a la base.

### Lo que hace falta para desbloquear

Una sola acción del humano, en una terminal suya:

```
az login
```

Y después, o bien la ejecuta él, o me deja seguir a mí:

```
IP=$(curl -s https://api.ipify.org)
az postgres flexible-server firewall-rule update -g rg-albaranes-dev \
  -s psql-albaranes-rs9k2 -n datamart-puesto-pgris \
  --start-ip-address "$IP" --end-ip-address "$IP"
```

**Ojo con el parámetro**: es `-n / --name`, no `--rule-name`; con `--rule-name`
falla con «unrecognized arguments», que fue mi primer intento.

### Hallazgo de paso: la deuda D11 sigue ahí, y ha crecido

El listado confirma **cuatro reglas fechadas e inútiles** en un servidor
compartido —`…-2026-08-17-rango`, `…-2026-08-18`, `…-2026-08-19`,
`…-2026-08-20`— más `ClientPgris` y `FirewallIPAddress_2026-6-16_16-42-54`, que
también son IPs de puesto caducadas. Son **seis** entradas abiertas de más.

**No las he tocado**: la firma autoriza *reescribir* la regla única, no borrar
reglas de un servidor que comparten otros dos proyectos. Queda propuesto al
humano; el runbook ya documenta el `firewall-rule delete`.

### Dos cosas que salieron al cerrar, y conviene que consten

**1. La guarda de secretos me cazó, y tenía razón.** Al pegar la salida real de
`az` en `progress/` metí el **GUID de tenant**, el GUID de aplicacion de ARM del
mensaje de error y el **correo del puesto**. `init.sh` se puso en rojo:

```
E   AssertionError: el repositorio contiene datos que no deben versionarse:
E     progress/current.md: GUID (suscripcion o tenant) -> '…'
E     progress/impl_F-006.md: direccion de correo -> '…'
FAILED tests/test_f003_infra.py::test_f003_r4_sin_secretos_ni_identificadores_en_infra_y_spec
```

Es exactamente el riesgo de «pegar la salida real», que es lo que se pide hacer.
Redactado, y **el commit reescrito con `--amend`** en vez de arreglarlo en uno
nuevo: la regla dice que el historial de git no suelta lo que entra, así que lo
que toca es que no entre. Nada estaba pusheado. Verificado: `git show HEAD` ya no
contiene ningún GUID.

**2. La cobertura de líneas cambiadas baja de 99,0 % a 94,2 %** (795 de 844), y
el motivo es sano: T26 añade ~120 líneas de producción y **el camino de
ejecución del comando no se puede cubrir sin conexión**. Lo cubierto es todo lo
derivable —la generación de las consultas, el alcance, la interpretación del
resultado y el método del cliente con dobles—; lo que falta es el bucle del CLI
que llama a la base, y esa cobertura llega con T27. Sigue muy por encima del
umbral del 80 %.

---

# Contra Azure, de verdad · 2026-08-21

Qué se ejecutó, qué devolvió y qué encontró. Salidas reales, redactadas de
identificadores.

## 0 · Firewall

`az login` lo hizo el humano. La regla **única** `datamart-puesto-pgris` se
reescribió midiendo la IP justo antes, y **cinco veces más** a lo largo de la
tanda porque rota cada pocos minutos (pauta de D11). **No se creó ninguna regla
nueva y no se tocó ninguna de las seis caducadas.**

```
$ az postgres flexible-server firewall-rule update -g rg-albaranes-dev \
    -s psql-albaranes-rs9k2 -n datamart-puesto-pgris \
    --start-ip-address "$IP" --end-ip-address "$IP"
datamart-puesto-pgris   <IP-del-puesto>   <IP-del-puesto>

$ python -m main check-pg
✓ Postgres OK. PostgreSQL 16.14 on x86_64-pc-linux-gnu
```

## 1 · T19 · el contrato en `_meta`, publicado

```
$ python -m main publicar-diccionario
[info] diccionario_publicado_ok  cobertura_cols=100.0 filas=116 n_columnas=793
                                 n_objetos=102 n_reglas=13 version=1
[SUCCESS] publicar_diccionario    rows=116 duration=0.8s
```

**Las cuatro comprobaciones, sobre la salida real:**

1. **Los objetos del contrato existen**: `diccionario`, `diccionario_reglas` y
   `diccionario_publicacion` como `BASE TABLE`, y `v_diccionario` como `VIEW`,
   junto a `etl_runs`, `v_frescura` y `v_raw_state`, que ya estaban.
2. **`v_diccionario` tiene 19 columnas y en el orden del contrato**, con
   `motivo_no_consumo` **la última**, que es la única forma compatible de
   crecer:
   `esquema, objeto, tipo, capa, consumo_recomendado, descripcion, grano,
   clave_negocio, refresco, avisos, n_columnas, ficha, paso_etl,
   ultimo_ok_finished_at, horas_desde_ultimo_ok, ultimo_intento_status,
   diccionario_version, diccionario_publicado_en, motivo_no_consumo`
3. **El singleton es singleton**: `count(*) = 1`, `id = 1`, y los recuentos
   cuadran con el repositorio (102 / 13 / 793 / 100.00).
4. **Los dos `LEFT JOIN` hacen lo que prometían**: 102 filas en
   `v_diccionario`, de las que **4 no tienen `paso_etl`** —los `estatico`— y
   **siguen saliendo**; 58 traen frescura resuelta.

## 2 · Bloque H · el diccionario contra `information_schema`

```
objetos en el catalogo real: 101
objetos fichados           : 102

SIN FICHA (0)
HUERFANAS (1)   cierre.v_pbi_planif_vs_real | vista
TIPO DISTINTO (0)
```

**Cero objetos publicados sin documentar y cero tipos mal.** La biyección que la
puerta offline daba por buena se sostiene contra el catálogo real, con **una
excepción que es el hallazgo**:

**`cierre.v_pbi_planif_vs_real` está fichada y no existe en la base.** No es que
la ficha sobre: `cierre/06_views_planif_vs_real.sql` la crea, y `cierre` tiene
en la base 8 objetos de los 12 fichados. La causa está localizada: **`build_cierre`
no aparece en `_meta.v_frescura`** —no registra paso, que es la deuda conocida de
`R-FRESCURA-MANUAL`—, así que nunca se ha vuelto a lanzar desde que ese fichero
entró. **La base va por detrás del repositorio**, y la puerta offline no podía
verlo porque lee el SQL, no el catálogo. Es justo lo que R28 existe para
descubrir.

## 3 · T26 · la unicidad de la clave, ejecutada

Primera pasada, alcance por defecto (superficie de consumo, `statement_timeout`
30 s):

```
Resumen: 39 sin contradiccion, 0 con la clave rota, 7 sin comprobar,
         1 fichados que no existen en la base.
```

Segunda pasada con `--timeout 180`, decidida **porque el servidor había
aguantado la primera sin incidencias y era fuera de horario**. Ahí saltó lo
importante:

```
KO   mart.fact_seguimiento_mensual: la clave declarada
     (obra_id, partida_id, anio_mes, escenario) NO identifica una fila.
     8778 combinacion(es) se repiten, afectando a 17556 filas.
```

### El hallazgo, caracterizado hasta la causa

**La tabla central del datamart tiene la clave rota.** Es exactamente el hueco
que T26 se escribió para cerrar, y ha aparecido en el objeto más consultado.

- **Siempre exactamente dos filas** por clave duplicada: 8.778 claves, 17.556
  filas. Ni una con tres.
- **Reparto**: `Coste Real` 4.754 y `Venta Real` 4.024. Los ámbitos master (8 y
  11) **no** están afectados, coherente con que allí se elige la versión vigente.
- **Qué distingue a las dos filas**: solo `nombre_mes`, `version_descripcion` y
  `total_incurrido`. Todo lo demás —incluido `importe_origen`— es idéntico.
- **Causa raíz**: el fact se construye por FASE, y hay **22 obras con dos fases
  que Sigrid tiene con el mismo `ano` y `mes`. Ejemplo verificado, obra 584748:

  ```
  fase_id  numero_fase  anio  mes  nombre_mes     fecha_inicio
  124      12           2010  6    Junio 2010     2010-06-01
  150      13           2010  6    AGOSTO 2010    2010-06-16
  ```

  La fase 13 se llama «AGOSTO» y lleva `mes = 6`. **Es la trampa que la ficha de
  `stg.fases` ya documentaba** —`anio` y `mes` se copian en crudo de
  `raw.obrfas`, independientes del nombre y de `fecha_inicio`— mordiendo aguas
  abajo.

**Consecuencias, y son de número**: `SUM(importe_origen)` agrupando por la clave
declarada **cuenta dos veces** (27.850,08 en las dos filas del ejemplo), y un
`JOIN` por esa clave produce fan-out. Y el efecto de segundo orden que ya estaba
escrito: **la detección de cardinalidades deriva la unicidad de esta clave**, así
que todas las relaciones que apuntan a este fact se validaron contra una premisa
falsa.

**Qué he hecho y qué no.** He corregido **la ficha**, que es F-006: dice el
número medido, la causa, el ejemplo y qué hacer mientras tanto (agregar también
por `nombre_mes`). **No he tocado el build**: `mart` es de otra feature y el
límite de esta tanda era `_meta`. Y **no se puede alargar la clave con lo que hay
publicado**, porque ninguna columna del fact identifica la fase: eso es un cambio
de esquema o de agregación, y necesita su propia feature.

### Dos defectos de mi propio código que solo la ejecución real destapó

1. **`conn.autocommit = False` reventaba**: `self.connection()` devuelve una
   conexión que **ya viene en transacción**.

   ```
   psycopg.ProgrammingError: can't change 'autocommit' now:
   connection in transaction status INTRANS
   ```

   El doble no lo reprodujo —ahí `autocommit` es un atributo normal—. **Es
   exactamente lo que un doble no puede garantizar**: prueba que llamas a lo que
   crees, no que el otro extremo se comporte como crees. Tiene ya su test.

2. **El comando moría con `UndefinedTable`** al llegar a la huérfana de H, y se
   llevaba por delante las comprobaciones que faltaban. Ahora «fichado y no
   existe» es **un veredicto más**, y de los valiosos: dice que la base va por
   detrás del repositorio.

### Los 7 sin comprobar

Con 30 s saltaron 7; con 180 s la lista bajó y quedó al menos
`cierre.v_pbi_cierre_indirectos_detalle`. **Van como NO COMPROBADO, nunca como
OK**: contar un timeout como correcto convertiría el límite que protege un
servidor compartido en una forma de aprobar sin mirar. La segunda pasada no
terminó dentro de mi ventana de ejecución, así que el recuento final de esa
pasada queda incompleto y **eso también se dice**.

### Y lo que un verde NO significa

Los 39 «sin contradicción» **no tienen la clave demostrada**. Los datos de hoy no
la contradicen, que es otra cosa: una clave puede ser insuficiente y no haber
colisionado todavía. `mart.fact_seguimiento_mensual` llevaba meses sin
colisionar y colisionaba desde 2010.

---

# Duodécima pasada · tres graves, y las evidencias que faltaban

## GRAVE 1 · El `READ ONLY` era mentira, y la mentira iba impresa

`main.py` imprimía «transaccion READ ONLY» antes de lanzar contra el servidor
compartido con producción, y `comprobar_unicidad` emitía **solo** el
`statement_timeout`. El constructor que sí fabricaba `BEGIN READ ONLY … COMMIT`
**lo llamaba únicamente el test**.

El riesgo material era bajo —son `SELECT count(*)`— pero **la garantía era falsa
y estaba anunciada**, que es peor que no anunciarla: quien lea esa línea deja de
preguntarse si el comando puede escribir.

**Aplicado de verdad.** No con `BEGIN READ ONLY`, que no vale aquí:
`PostgresClient.connection()` devuelve la conexión **ya en transacción**
(`INTRANS`), que es lo mismo que ya rompió el `autocommit`. Se emite
`SET LOCAL transaction_read_only = on` junto al `statement_timeout`: misma
garantía, aplicable a una transacción abierta, y acotada a ella.

Y el test ya no comprueba el constructor sino **lo que el cliente ejecuta**:

```python
assert cursor.ejecutadas[:2] == list(previas)
assert "GROUP BY" in cursor.ejecutadas[2]
```

### El barrido de constructores muertos

Pediste mirar si había más. Lo hice a máquina sobre `unicidad_sql` y
`diccionario_sql`, contando usos fuera de tests y fuera del propio módulo:

```
unicidad_sql.consultas_de_unicidad          -> 2
unicidad_sql.objetos_saltados               -> 2
unicidad_sql.sentencias_de_la_transaccion   -> 0     <<<
unicidad_sql.interpretar_resultado          -> 2
unicidad_sql.veredicto_no_comprobado        -> 2
unicidad_sql.veredicto_no_existe            -> 2
diccionario_sql.filas_diccionario           -> 2
diccionario_sql.filas_reglas                -> 2
diccionario_sql.cobertura_columnas          -> 0     (la usa `fila_publicacion`)
diccionario_sql.fila_publicacion            -> 4
diccionario_sql.resumen_publicacion         -> 2
```

**Uno, y era ese.** `cobertura_columnas` sale a 0 porque la consume otra función
de su mismo módulo, no porque esté muerta. Queda un control permanente que barre
las funciones públicas de `unicidad_sql` y falla si alguna solo la usa su test.

## GRAVE 2 · Lo publicado no era lo del repositorio, y mentía donde más dolía

El commit `726e009` publicaba **y además** editaba `mart.yaml` con el aviso del
duplicado. No republiqué. Resultado: durante unas horas `_meta` sirvió el grano
que decía que la clave del fact identifica una fila —**justo lo que T26 acababa
de demostrar falso**— con `hash_fuente` obsoleto y `version` en 1.

**Corregido en tres pasos.**

**1. El aviso, propagado a las tres fichas que lo heredan**, derivadas de quién
lee el fact en `sql/mart/`:

| Ficha | Cómo le llega |
|---|---|
| `mart.v_pbi_fact` | `SELECT … FROM mart.fact_seguimiento_mensual` sin filtro: **el duplicado llega intacto a Power BI** |
| `mart.v_fact_periodificado` | pasarela mientras `aux.periodificacion_partida` esté vacía: llega tal cual |
| `mart.fact_seguimiento_categoria` | **AGREGA**, así que la clave NO duplica —T26 la dio sin contradicción— pero **las dos filas se suman: el importe viene inflado** |

El tercero es el importante y no estaba dicho en ningún sitio: **un duplicado
que se ve se corrige; uno que se suma no se nota.**

**2. `version` sube a 2 y se republica**:

```
[info] diccionario_publicado     filas=116 hash_fuente=a7584ee84391 objetos=102
                                 reglas=13 version=2
[info] diccionario_publicado_ok  cobertura_cols=100.0 filas=116
                                 hash_fuente=a7584ee8439110237b9a625e98a32c714b3903b05fcf43a37f379700cc0b7399
                                 n_columnas=793 n_objetos=102 n_reglas=13 version=2
[SUCCESS] publicar_diccionario   rows=116 duration=0.7s
```

Verificado en la base que las cuatro fichas avisan ya:

```
mart.fact_seguimiento_categoria -> avisa del duplicado: True
mart.fact_seguimiento_mensual   -> avisa del duplicado: True
mart.v_fact_periodificado       -> avisa del duplicado: True
mart.v_pbi_fact                 -> avisa del duplicado: True
publicado: ('2', 'a7584ee84391')
```

**3. El mecanismo detecta ahora esta situación por sí solo**, que era la parte
que pedías. `check-diccionario` compara el `hash_fuente` de `_meta` con el de los
YAML del árbol. Ejecutado **antes** de republicar, con el desfase todavía vivo:

```
KO   LO PUBLICADO NO ES LO DEL ARBOL. `_meta` sirve el hash 3339c397f39f
     (version 1) y los YAML dan 9f5d5f2f5df4. Alguien edito una ficha y no
     republico, asi que el MCP esta leyendo una version anterior. Se arregla con
     `python main.py publicar-diccionario`, subiendo `version` si el cambio hay
     que comunicarlo.
```

Y después:

```
OK   lo publicado ES lo del arbol (version 2, hash a7584ee84391)
```

## GRAVE 3 · El «bloque H» no lo producía ningún comando

Cierto: `check-diccionario` no existía. La huérfana salió **de rebote**, de un
`except UndefinedTable` del chequeo de unicidad, que recorre la superficie de
consumo —**47 de 102**— y solo puede ver una de las tres clases de discrepancia.

Implementado de frente en `etl_sigrid/infrastructure/postgres/catalogo.py` +
`main.py check-diccionario`: los **102**, en las **tres** direcciones —publicado
sin ficha, fichado que no existe, tipo que no casa—. Salida real:

```
Diccionario contra el catalogo real de Postgres
  fichas: 102   objetos en la base: 101

FICHADO Y NO EXISTE (1):
  - cierre.v_pbi_planif_vs_real: fichado como vista y NO existe en la base. O
    falta lanzar el build de `cierre` —la base va por detras del repositorio— o
    la ficha sobra

1 discrepancia(s). La puerta offline no puede verlas: lee el SQL del
repositorio, no el catalogo.
```

**Cero publicados sin ficha y cero tipos mal, ahora sí sobre los 102.** Con su
control: comparar contra un catálogo vacío tiene que dar 102 huérfanas, o el
comparador no está comparando.

**Un guardián propio hizo su trabajo.** El test que escribí diciendo «R28 no
existe» se puso en rojo al implementarlo y **obligó a corregir los tres
docstrings** que lo daban por futuro. Ahora comprueba la dirección contraria:
que nadie lo siga dando por pendiente.

## Las evidencias que faltaban

### La salida de T19, completa

Tenías razón en que la recorté donde dolía. El evento `diccionario_publicado_ok`
lleva siempre `hash_fuente` y yo pegué la línea sin él. Va entera:

```
[info] diccionario_publicado     filas=116 hash_fuente=a6da19bac1e8 objetos=102
                                 reglas=13 version=1
[info] diccionario_publicado_ok  cobertura_cols=100.0 filas=116
                                 hash_fuente=a6da19bac1e87c2289be6c04b2fe52a98b710746514568b5aa6973898dc6a99a
                                 n_columnas=793 n_objetos=102 n_reglas=13 version=1
[SUCCESS] publicar_diccionario   rows=116 duration=0.8s
```

### Las cuatro comprobaciones, con su salida

**1 · Los objetos del contrato existen** (`information_schema.tables`,
esquema `_meta`):

```
   diccionario             | BASE TABLE
   diccionario_publicacion | BASE TABLE
   diccionario_reglas      | BASE TABLE
   etl_runs                | BASE TABLE
   v_diccionario           | VIEW
   v_frescura              | VIEW
   v_raw_state             | VIEW
```

**2 · `v_diccionario`: 19 columnas y en el orden del contrato**:

```
   total: 19
   ['esquema', 'objeto', 'tipo', 'capa', 'consumo_recomendado', 'descripcion',
    'grano', 'clave_negocio', 'refresco', 'avisos', 'n_columnas', 'ficha',
    'paso_etl', 'ultimo_ok_finished_at', 'horas_desde_ultimo_ok',
    'ultimo_intento_status', 'diccionario_version', 'diccionario_publicado_en',
    'motivo_no_consumo']
```

Las 18 del contrato en orden y `motivo_no_consumo` **la última**, que es la
única forma compatible de crecer.

**3 · El singleton**:

```
   (1, '1', 'a6da19bac1e8', datetime.datetime(2026, 8, 21, 19, 2, 43, 383050),
    102, 13, 793, Decimal('100.00'))
   filas: 1
```

**4 · Los dos `LEFT JOIN`**:

```
   total en v_diccionario: 102
   sin paso_etl         : 4
   con frescura resuelta: 58
   reglas publicadas    : 13
```

Los 4 sin paso son los `refresco: estatico` —`aux.periodificacion_partida` y los
tres de instrumentación de `_meta`— y **siguen saliendo**, que es lo que el
`LEFT JOIN` prometía.

### La causa raíz del duplicado, con su salida

```
=== fases de la obra 584748 con anio=2010 mes=6 ===
   (124, 12, 2010, 6, 'Junio 2010',  2010-06-01)
   (150, 13, 2010, 6, 'AGOSTO 2010', 2010-06-16)

=== cuantas obras tienen dos fases con el mismo (anio,mes) ===
   22 obras

=== escenarios afectados ===
   ('Coste Real', 4754)
   ('Venta Real', 4024)

=== siempre 2 filas, o mas? ===
   filas por clave: 2 -> claves: 8778
```

Y la comparación fila a fila de una clave duplicada, que es lo que demuestra que
**ninguna columna publicada distingue las dos**:

```
      partida_id            31783                 31783
      anio_mes              2010-06-01            2010-06-01
      escenario             Coste Real            Coste Real
      importe_origen        27850.08              27850.08
  >>> nombre_mes            Junio 2010            AGOSTO 2010
  >>> version_descripcion   Junio 2010            AGOSTO 2010
  >>> total_incurrido       0.00                  27850.09
  >>> total_incurrido_mes   0.00                  27850.09
```

`importe_origen` **idéntico en las dos**: por eso un `SUM` cuenta dos veces.

### Los siete NO COMPROBADO, con nombre

Los perdí en el informe anterior y tenías razón en que se deducía de mis propios
números que uno era el fact. Pasada completa con `--timeout 60`:

```
?  cierre.v_pbi_cierre_indirectos_detalle  (obra_id, anio_mes, grupo_cod, subcategoria_cod)
?  compras.v_pbi_partida_coste             (obra_id, codigo_obra, partida_id, codigo_partida, …)
?  mart.fact_seguimiento_mensual           (obra_id, partida_id, anio_mes, escenario)
?  mart.v_master_versiones_tipadas         (obra_id, ambito_id, version)
?  mart.v_master_vigente_anual             (obra_id, anio, ambito_id)
?  mart.v_pbi_cp_tipologia                 (obra_id, anio, tipologia)
?  mart.v_pbi_fact                         (obra_id, partida_id, anio_mes, escenario)

!  cierre.v_pbi_planif_vs_real             FICHADO Y NO EXISTE

Resumen: 39 sin contradiccion, 0 con la clave rota, 7 sin comprobar,
         1 fichados que no existen en la base.
```

**Y esto es la demostración de por qué un timeout no puede contarse como OK.**
`mart.fact_seguimiento_mensual` sale NO COMPROBADO con 30 s y con 60 s. Solo con
**180 s** reveló que su clave está rota en 8.778 casos. Si el diseño hubiera
tratado el timeout como «sin problemas», el defecto más grave de la feature
—en la tabla central— habría quedado enterrado bajo un verde, y encima con la
excusa de proteger un servidor compartido.

Nota sobre el séptimo: **`mart.v_pbi_fact` es la pasarela literal del fact**, así
que está roto con toda seguridad —mismas 8.778 combinaciones— aunque **no se ha
medido**. Se dice como lo que es: no verificado, no «probablemente bien».

---

# Decimotercera pasada · cuatro defectos, y dos son reincidencias mías

## GRAVE 1 · El plegado, tercera vez, y dentro del dispositivo que lo vigilaba

`inventario.py` afirmaba que `check-diccionario` «está sin implementar: llega en
el bloque H» **del comando que existe desde ese mismo commit**. Y el guardián de
R28 estaba **verde**, porque busca la subcadena literal y el ajuste de línea
partía la frase:

```
"sin implementar" in envuelto   -> False
contiene(envuelto, "sin implementar") -> True
```

Lo que lo hace grave no es la frase: es **dónde ocurrió**. Dentro del mecanismo
escrito para impedir exactamente esto, y sobre la función cuya única red de
seguridad *es* R28.

**Y ya lo había arreglado una vez.** En la 10ª pasada, para el barrido de YAML, y
**solo ahí**. Arreglar el caso y no la clase es lo que garantiza la tercera
aparición.

Ahora hay `tests/_texto.py` con `normalizado()` y `contiene()`, aplicado a las
guardas de prosa, y **dos controles**: el caso exacto que estuvo mintiendo, y uno
que exige que esas guardas usen `contiene` y no `in` a pelo. La frase de
`inventario.py` dice ya lo que es cierto.

## GRAVE 2 · Código muerto nuevo, en la tanda que decía haberlo barrido

`list_objetos_catalogo` y mi `fetch_catalogo_objetos` ejecutaban **el mismo
SQL**, y el consumidor del primero era un test. Eliminado **el mío**: el comando
usa el que ya existía y ya tenía prueba.

**Pero el defecto de fondo era otro, y lo señalaste exacto**: «era el único» era
cierto **dentro de un alcance que no declaré**. Mi barrido miraba
`unicidad_sql.py` y nada más, y presenté la conclusión como si fuera general.

El barrido cubre ahora cinco módulos y **declara sobre cuáles concluye** en una
constante comprobada, más un test que vigila que no vuelva a haber dos métodos
con el mismo SQL:

```
MODULOS_BARRIDOS = (unicidad_sql, catalogo, diccionario_sql,
                    inventario, cargador_yaml)
```

Una afirmación de completitud sin su alcance es de la misma familia que las que
esta feature lleva trece pasadas corrigiendo.

## DEFECTO 3 · El aviso estaba INVERTIDO, y es lo peor para el usuario

Decía «el importe viene inflado» en bloque. **Medido contra la base**, sobre 200
series afectadas:

```
importe_mes          telescopea en 200/200   -> SUMAR ES CORRECTO
importe_mes_raw      telescopea en 200/200   -> SUMAR ES CORRECTO
can_mes              telescopea en 200/200   -> SUMAR ES CORRECTO
total_incurrido_mes  telescopea en 200/200   -> SUMAR ES CORRECTO

SUM(importe_origen) == ultimo valor   solo en 28/200   -> SUMAR ESTA MAL
```

La prueba decisiva fue comprobar que `SUM(importe_mes)` iguala al último
`importe_origen`: si telescopea, sumar todas las filas del mes es correcto **aun
con el duplicado delante**, porque el `LAG` particionado hace que la segunda fila
aporte la diferencia y no un valor repetido.

**Así que el aviso alarmaba sobre la medida sana y callaba sobre la enferma.** Un
agente que lo leyera evitaría `importe_mes`, que está bien, y sumaría
`importe_origen`, que está mal. Es el reverso exacto de para lo que se escribió.

Los cinco avisos lo dicen ya **columna a columna**, con una conclusión que antes
no estaba: **el duplicado no rompe ninguna suma que ya estuviera bien
planteada**. Rompe el `count(*)`, rompe cualquier `JOIN` por la clave declarada
—fan-out— y rompe a quien sume una columna `_origen`, que ya estaba mal antes.

**Nota de método que me llevo**: llegué a esa conclusión midiendo primero si los
dos valores eran iguales, y esa medida **no zanjaba nada** —1.440 de 8.778 claves
tienen `importe_mes` distinto en las dos filas, y aun así la suma es correcta—.
La pregunta buena no era «¿se repite el valor?» sino «¿la suma da lo que debe?».

## DEFECTO 4 · Cuarta hermana olvidada, y la lista deja de ser una lista

`mart.v_pbi_fact_categoria` sirve `importe_origen` **a las tarjetas de KPI de
Power BI** y se quedó sin una palabra del problema.

Van **cuatro** propagaciones que dejan fuera a una hermana, siempre por el mismo
motivo: corrijo donde me señalan y mantengo a mano la lista de quién más está
afectado. Así que **la lista deja de mantenerse a mano**: se deriva de quién lee
la familia del fact **y publica alguna de sus medidas**. Las dimensiones
(`v_pbi_dim_*`) leen del fact para el calendario y el catálogo, no publican
medidas, y por eso no entran —comprobado en el propio test—.

## La cobertura, cerrada en vez de explicada

Tenías razón en las tres cosas. **64 de las 85 líneas sin cubrir eran el cuerpo
entero de los dos comandos**, y no hacía falta ninguna conexión: hacía falta el
`CliRunner` que este repositorio ya usa en seis sitios.

Doce tests que ejercitan los dos comandos completos —dry-run, clave rota,
timeout, objeto inexistente, `--todos`, la bandera de timeout, la biyección, la
huérfana, el hash desfasado, el «nada publicado» y el objeto sin ficha— con
dobles **solo** del cliente de Postgres: el diccionario que cargan es el real y
las consultas que generan son las reales.

**90,9 % → 97,8 %** de 942 líneas, por encima del 93,4 % que estimaba la review, y
sin abrir una sola conexión. Llevaba tres tandas explicando esa laguna, que es
más caro que cerrarla y además la convierte en paisaje.

## Lo que sigue fuera, por la firma

`build_cierre` no se ha lanzado: escribe en un esquema de negocio del servidor
compartido y la autorización está acotada a `_meta`. La huérfana
`cierre.v_pbi_planif_vs_real` sigue apareciendo en `check-diccionario`, que es
donde tiene que aparecer.

---

# El contrato crece · `_meta.diccionario_contexto` (2026-08-22)

## Nota sobre el historial: dónde empezó de verdad este cambio

**La ampliación del contrato empieza en `909cd79`**, un commit del líder titulado
«F-044: script temporal para lanzar los cuatro build a mano, medidos». No es lo
que parece: el líder hizo `git add -A` mientras yo tenía trabajo sin commitear y
se llevó dentro seis ficheros míos —el DDL de la tabla nueva, la clasificación
del dominio, `filas_contexto`, la escritura en el cliente, la ficha de `_meta` y
dos tests—.

No se reescribe el historial: hacerlo con dos agentes sobre el mismo árbol es
peor remedio que la enfermedad. Queda escrito aquí porque **un historial que
engaña sobre dónde empezó un cambio cuesta media hora dentro de tres meses**.

## Por qué crece

Al implementar en `mcp-bbdd` el proveedor que lee el diccionario de `_meta` en
vez del YAML salió un hueco que **no vimos ninguno de los tres**: `_meta`
publicaba los objetos y las reglas, pero **no el resto del bloque global**. El
prototipo local servía `convenciones` y `ordenes_de_magnitud` enteros, así que
con el origen en base **se perdían**, y el MCP en cloud habría respondido *peor*
que el prototipo local.

Los **órdenes de magnitud** son los que hacen que una cifra absurda se note
—existen para que no se repita lo de los 38,9 M€ en una sola obra— y las
**convenciones** hacen falta para interpretar cualquier importe. Sin ellos el
contrato no cumple su propósito.

## La forma: filas, nunca columnas

```sql
CREATE TABLE IF NOT EXISTS _meta.diccionario_contexto (
    bloque  TEXT    NOT NULL,
    clave   TEXT    NOT NULL,
    orden   INTEGER NOT NULL DEFAULT 0,
    texto   TEXT    NOT NULL,
    datos   JSONB   NOT NULL,
    PRIMARY KEY (bloque, clave)
);
```

Mismo criterio que puso `motivo_no_consumo` al final de la vista: **crecer sin
romper**. Un bloque nuevo mañana son filas, no un `ALTER TABLE` ni una vista
recreada —y recrear una vista exige `DROP`, que se lleva los `GRANT`—.

`texto` se genera **aquí** a propósito: si cada consumidor compusiera su propio
renderizado acabarían divergiendo, que es justo lo que pasó con el resumen por
esquema del prototipo. `datos` lleva la entrada entera para quien necesite el
valor numérico sin parsear prosa.

## El barrido del punto 3: nada se queda fuera sin decirlo

Recorrí **las once claves** del bloque global y las clasifiqué. La decisión vive
en `CONTEXTO_PUBLICADO` / `CONTEXTO_NO_PUBLICADO` y **un test exige que ninguna
quede sin decidir**: si alguien añade una clave nueva y no decide, salta.

| Viaja | Filas | Por qué |
|---|---|---|
| `convenciones` | 5 | sin moneda/IVA/fecha no se interpreta ningún importe |
| `ordenes_de_magnitud` | 4 | hacen que una cifra absurda se note |
| `ejes` | 3 | los literales EXACTOS de `escenario` |
| `esquemas` | 9 | enruta una pregunta antes de mirar objeto por objeto |

| No viaja | Por qué |
|---|---|
| `reglas`, `version` | ya viajan, en sus propias tablas |
| `base`, `titulo` | el MCP ya está conectado; el título no ayuda a responder |
| `preguntas_aceptacion`, `pendientes` | instrumentación nuestra, no contexto |
| `ocultar` | ver abajo |

**`ocultar` se queda fuera a propósito**, y está escrito y fechado para que nadie
lo añada por su cuenta: `mcp-bbdd` lo resuelve anteponiendo `[NO RECOMENDADO
PARA CONSULTA: …]` con el `motivo_no_consumo` que sí viaja. Resuelve el problema
sin ampliar superficie que mantener sincronizada entre dos repositorios.

Es la **tercera vez** que información importante no llega —la regla de oro en un
comentario, el aviso de frescura en una cabecera, y ahora esto— y las tres
salieron por casualidad. Por eso la decisión deja de ser implícita.

## Publicado y verificado

```
[info] diccionario_publicado     contexto=21 filas=138 hash_fuente=44e091eb215c
                                 objetos=103 reglas=13 version=4
[SUCCESS] publicar_diccionario   rows=138 duration=0.7s
```

Contra la base:

```
=== contexto publicado ===
   convenciones           5
   ejes                   3
   esquemas               9
   ordenes_de_magnitud    4

=== lo que vera el agente ===
   Retenido VIVO a proveedores, pendiente de devolver, en toda la empresa:
       del orden de 34.700.000 EUR (criterio: saldo_vivo)
   Retenido VIVO por clientes, pendiente de cobrar, en toda la empresa:
       del orden de 21.900.000 EUR (criterio: saldo_vivo)
   moneda: EUR

OK   lo publicado ES lo del arbol (version 4, hash 44e091eb215c)
```

Las cuatro tablas se vacían y se reescriben **en la misma transacción**, con su
test. `design.md` lleva la enmienda fechada en §4.4, que es lo que implementa el
otro repositorio.

---

# Decimocuarta pasada · el valor doblado, y dos razones falsas

## GRAVE 1 · Un valor doblado en la base, con el diccionario respaldándolo

`mart.fact_seguimiento_categoria.importe_origen` **está doblado en el valor
almacenado**. El build hace `SUM(importe_origen)` sobre las filas duplicadas del
fact, y ahí el acumulado es **idéntico en las dos**, así que sumarlas da el
doble. Medido contra la base el 2026-08-22:

```
   celdas de categoria afectadas: 37   obras: 8   sobran: 39.07 M EUR
```

**39,07 M€ de más.** Es el mismo orden de magnitud que el «38,9 M€ en una sola
obra» que motivó los órdenes de magnitud — el error que esta feature nació para
impedir, reproducido dentro de ella.

Y la ficha de columna decía «ya es acumulado» con `agregacion: ultimo_valor`, o
sea **tómalo tal cual**. Alguien pregunta cuánto lleva a origen una obra, lee una
fila y **recibe el doble con el diccionario respaldándolo**, que es peor que no
documentar nada.

### Por qué se coló, que es lo que hay que arreglar

El derivador exigía el aviso en `descripcion` o `grano`: **a nivel de objeto**. Y
quien consulta una columna concreta recibe **su ficha de columna**, donde no
había nada.

El reviewer lo dio por cerrado media hora antes porque verificó `descripcion` y
`grano` —justo donde el derivador exigía— y no abrió las fichas de columna:
**heredó el punto ciego del guardián que estaba verificando**. Es la misma
lección de siempre: una comprobación no solo deja pasar defectos, además **enseña
a mirar donde ella mira**.

Ahora el aviso baja a la columna y el derivador lo exige ahí. Con dos matices que
no estaban:

- las **acumuladas** (`importe_origen`, `importe_origen_raw`) dicen que el valor
  está doblado, cuánto, por qué, y cómo obtener un acumulado fiable;
- las **sanas** (`importe_mes`) dicen **que lo son**, para no repetir el error de
  la pasada anterior de alarmar en bloque sobre la medida buena.

Al derivar quién agrega volvió a aparecer **el punto ciego del bloque**: mirar el
fichero entero metía a `mart.v_pbi_fact` —que es pasarela y no dobla nada— por el
`FROM` de su vecina en `05_views_powerbi.sql`. Acotado a su bloque, como ya hubo
que hacer con `_proyeccion_de` y con el derivador de alias. **Tercera vez.**

El build no se toca: es `mart`, de otra feature, y la firma está acotada a
`_meta`.

## GRAVE 2 · La razón para excluir `ocultar` era falsa, y mi test la respaldaba

Escribí que `motivo_no_consumo` lo sustituía. **No puede**: `motivo_no_consumo`
es de **objeto** y `ocultar` son **columnas**.

Verificado en `mcp-bbdd`: el único gancho es
`esta_oculta(tabla.nombre_completo)` (`application/services/servicio_catalogo.py:49`),
que recibe un nombre de **tabla**. Ninguna tabla se llama `_built_at`, así que
esa lista **nunca ocultó nada, ni con el YAML ni con la base**.

Lo peor no es la razón: es que **mi test la respaldaba**. Comprobaba que la
cadena `motivo_no_consumo` apareciese en el motivo, así que dio por buena una
justificación inventada. Un test que verifica que una explicación *existe* no
verifica que sea *cierta* — exactamente el fallo que esta feature persigue,
cometido dentro de ella.

**Decidido de nuevo con el dato correcto delante**: sigue fuera, pero por otra
razón. La necesidad **es real** —el agente ve esas columnas en la `ficha` y puede
ofrecerlas como si fueran de negocio— y el hueco se cierra en `mcp-bbdd`
añadiendo un gancho de **columna**; publicar la lista antes solo movería el
problema de sitio. Queda escrito así, fechado, y el test comprueba ahora los
hechos verificables: que cite el gancho real, que diga que es de tabla, que
reconozca el hueco, y **que no vuelva la justificación falsa**.

## GRAVE 3 · Recuentos caducados

Son **103 objetos, 798 columnas y 48 de consumo**. Estaban mal en la ayuda de
`main.py`, en el «tres tablas» del DDL que define cuatro, y en `current.md`.

Aplicado el remedio de siempre donde se puede: la ayuda de `main.py` **ya no da
la cifra** —la imprime el propio comando, que la cuenta—, y el DDL dice «cuatro».
Lo que no se puede derivar, un documento en prosa, **se comprueba**: hay un test
que contrasta los recuentos de `current.md` contra el diccionario y falla si
caducan. Ya lo hicieron dos veces, y la segunda el propio reviewer copió las
cifras viejas **en el informe donde reprochaba justo eso**.

## R38 · El documento del ecosistema

`azure-apps/datamart_seg_anual.md` describía el MCP como «cliente de escritorio»
y no decía que este proyecto **publica su propia semántica en la base**. Añadido:
qué se publica (las cuatro tablas y la vista), quién lo consume, dónde está el
contrato completo, cómo se publica, y las **reglas de compatibilidad** que rompen
si se ignoran —columnas solo al final de `v_diccionario`, el contexto crece por
filas, nunca `DROP` ni `TRUNCATE`, y `hash_fuente` es la identidad, no
`version`—.

Publicado en **versión 5**.

---

# Decimoquinta pasada · la cabecera decía lo contrario que las columnas

## Lo que lo destapó, y es el mérito de la pasada

El reviewer fue a mirar **cómo llega el diccionario al agente**, que es lo que
ninguno de los tres habíamos hecho en quince pasadas:

- `listar_tablas` entrega **descripción y grano, sin columnas**.
- `describir_tabla` entrega las dos cosas.

Así que el aviso que en la 14ª bajé a las columnas **no llegaba** por la primera
vía, y por la segunda llegaba **acompañado de su contrario**: el `grano` decía
«como esta tabla agrega, las dos filas se funden y **la clave no duplica
—comprobado—**», que es cierto y suena a que todo está bien, mientras la columna
decía que el importe está doblado.

Las dos frases juntas se anulan. Y por `listar_tablas`, el agente solo veía la
tranquilizadora.

## El patrón, ya con nombre: «el guardián enseña a mirar donde él mira»

Van **tres**, y las tres son la misma:

| Pasada | Dónde exigía el guardián | Dónde estaba el defecto |
|---|---|---|
| 13ª | `descripcion` / `grano` | en las fichas de columna |
| 14ª | en la columna | en la cabecera |
| 15ª | — | en **cómo se entrega**, que nadie miraba |

Mover la exigencia de sitio no cierra nada: solo cambia dónde aparecerá la
próxima. Lo que la cierra es **exigir que las dos partes digan lo mismo**, y eso
es lo que se ha derivado:

- si una columna lleva el aviso, la cabecera **tiene que llevarlo**;
- y no puede **afirmar a la vez lo contrario** sin aclarar que una fila única no
  dice nada de si su importe es correcto.

Con su control, para que no pase en vacío si el derivador se queda sin objetos.

## Los tres números, cada uno con su consulta

Tenías razón en que «37 celdas / 8 obras» aparecía sin consulta y contradecía al
«8.778 / 22» de la misma ficha. Medidos los tres, y **son legítimamente
distintos porque miden cosas distintas**:

| Número | Qué mide |
|---|---|
| **22 obras** | tienen dos fases con el mismo `ano` y `mes` en `stg.fases` — **la causa** |
| **8.778 claves / 9 obras** | combinaciones duplicadas en `mart.fact_seguimiento_mensual`, grano partida |
| **37 celdas / 8 obras** | celdas con importe doblado en `mart.fact_seguimiento_categoria`, grano categoría |

```sql
-- las 8.778
SELECT count(*), count(DISTINCT obra_id) FROM (
  SELECT obra_id, partida_id, anio_mes, escenario
  FROM mart.fact_seguimiento_mensual GROUP BY 1,2,3,4 HAVING count(*) > 1) d;
```

**Y salió un error de paso: en el fact son 9 obras, no 22.** Las 22 son las que
tienen fases duplicadas; solo 9 llegan a producir filas duplicadas, porque las
demás no tienen presupuesto en esos meses. Estaba mal atribuido y ya no lo está.

## `ocultar` entra al contrato, y el argumento es el bueno

Tercera decisión sobre la misma clave. Las dos anteriores la dejaban fuera:

1. Con una razón **falsa** —«`motivo_no_consumo` lo sustituye»—, imposible
   porque uno es de objeto y la otra son columnas.
2. Con una razón **cierta pero incompleta**: el gancho de `mcp-bbdd` recibe
   tabla, así que publicarla no ocultaría nada todavía.

Lo que faltaba en las dos: **si no viaja, `mcp-bbdd` tiene que cablear la
lista**, y eso es una **segunda copia de la semántica de este repositorio** —
justo lo que F-006 nació para terminar, y la misma regla que rige `azure-apps`:
se enlaza, no se duplica. Que el consumidor no pueda usarla hoy no es motivo para
no publicarla; es motivo para que la tenga cuando la use.

Publica **una fila por columna, con la columna como `clave`**:

```sql
SELECT clave FROM _meta.diccionario_contexto WHERE bloque = 'ocultar';
--  _ingested_at / _source_tiemod / _built_at
```

La primera versión las publicaba con la **posición** como clave (`0`, `1`, `2`),
que no le habría servido de nada a quien tiene que comparar contra nombres de
columna. Corregido.

`design.md` §4.4 avisa de lo que hizo falsas a las dos razones anteriores —la
lista es de **columnas** y el gancho recibe **tabla**— y dice que si el
consumidor necesita otra forma **se cambia el contrato**, que para eso crece por
filas, en vez de dejar que lo adivine.

## `_ACUMULADAS`: la afirmación falsa más barata de toda la feature

Era una tupla escrita a mano bajo un comentario que decía «**Se derivan**». Un
texto describiendo un mecanismo que no existía, del mismo tipo que las que
llevamos quince pasadas corrigiendo, y en el fichero que las corrige.

Ahora se deriva del propio diccionario, con un criterio que ya estaba escrito:
una columna es acumulada a origen si se declara `ultimo_valor` —que es
literalmente lo que esa agregación significa— y tiene unidad, o sea es medida y
no clave. Con su control, usando los nombres que traía la lista a mano.

## Evidencias tras la 15ª review

| Evidencia | Valor | Cómo se obtiene |
|---|---|---|
| **Mutantes / supervivientes** | **254 generados, 254 muertos, 0 supervivientes, 0 timeouts** en 658,8 s | `python -m harness.mutacion --feature F-006 --timeout 300` |
| **Objetos documentados** | **103**, biyección exacta 103/103 contra la base | `python main.py check-diccionario` |
| **Columnas** | **798**, cobertura 100 % en la superficie de consumo (48 objetos) | `_meta.diccionario_publicacion` |
| **Publicado** | **versión 6**, hash `52f107235bc6`, **141 filas** | idem |
| **Filas de contexto** | **24** (convenciones 5, órdenes de magnitud 4, ejes 3, esquemas 9, **ocultar 3**) | `_meta.diccionario_contexto` |

**La campaña llevaba tres tandas sin relanzarse**: declaraba 166 mutantes cuando
el alcance ya eran **254**. Un número de mutación que no se recalcula envejece
igual que un recuento escrito a mano, y con el agravante de que **parece
evidencia**. Relanzada con el `__pycache__` borrado a mano (F-041 sigue sin
arreglar).

**Cero supervivientes sobre los 254**, incluidos los ~88 mutantes nuevos que
generan `catalogo.py`, `unicidad_sql.py` y el contexto — código escrito en las
tres últimas tandas y que hasta ahora no se había mutado nunca.

---

# Decimosexta pasada · instrumentos rotos

## La puerta de mutación no comprobaba nada, y mis números eran humo

El reviewer lo demostró: la campaña corre en un `git worktree` con **HEAD
detached**, y ahí `test_f015_r12_la_rama_actual_se_lee_de_git` **falla siempre**.
Como la suite va con `-x`, para en ese test; y `harness/mutacion.py` cuenta
**cualquier `returncode != 0` como mutante muerto**. La suite estaba roja antes
de mutar nada, así que **todos los mutantes se declaraban muertos sin comprobar
nada**. Su control: el mismo worktree **sin mutar** da el mismo fallo.

Eso invalida las campañas que he ido declarando: los «166/166» y el «254/254» de
la tanda anterior **no son evidencia de nada**. Y es peor que no tener número,
porque parece evidencia y se lee como tal — lo dije de los recuentos a mano y me
lo aplico aquí.

**Decisión, y es una regla para mí, no un apaño**: hasta que F-041 esté hecho,
**no vuelvo a declarar un número de mutación**. En su lugar, «no verificable, ver
F-041». `harness/mutacion.py` es del arnés y no lo toco.

### El superviviente real, muerto

Encontró uno que las **dos** campañas —la mía y la suya, independientes— dieron
por muerto: `and`→`or` en `diccionario_sql.py:297`.

La diferencia está en la **cadena vacía**: con `and` devuelve la posición, con
`or` cortocircuita y devuelve la cadena vacía. Ningún test lo tocaba. El control
nuevo `_clave_de("", 2) == "2"` lo caza, verificado aplicando el mutante a mano:

```
MUTANTE and->or => MUERTO
   FAILED test_f006_r28_control_toda_entrada_de_lista_de_texto_se_identifica_sola
```

## La regresión de `ocultar`: el estado no, el hueco sí

**La regresión no está en el árbol.** Verificado en los tres sitios: árbol, `HEAD`
y la base publican `_ingested_at` / `_source_tiemod` / `_built_at`, no `0/1/2`.

**Pero el hueco del test es real y lo he reproducido.** Revirtiendo el arreglo a
mano:

```
claves con el arreglo revertido: ['0', '1', '2']
19 passed
```

El test viejo comprobaba `columna in str(f[3]) or columna in str(f[1])` —el
nombre en la clave **o en el texto**— y el texto lo lleva siempre. Un falso verde
sobre el contrato publicado. Ya está el test que sí lo caza, escrito en RED con
el arreglo revertido.

## El guardián de coherencia: las tres vías, y la lección

Le pediste que lo atacara y entró por tres a la vez. Reproducidas las tres antes
de tocar nada:

```
VIA 3 · el salvoconducto:  frases marcadas: []   <- lista INERTE
VIA 1 · otra redaccion:    marcadas: []          <- 'sale unica' no estaba
VIA 2 · frase partida:     marcadas: []          <- el salto la parte
         normalizando:     ['la clave no duplica']
```

La tercera es la peor y es mía de cabo a rabo: `"el numero de dentro" not in
cabecera` se evaluaba sobre **todo el texto**, y esa frase es la formulación
nueva —está siempre—, así que **apagaba la lista entera**. Un guardián verde que
no miraba nada, dentro del fichero que existe para cazar exactamente eso.

**El arreglo no es ampliar la lista: es dejar de comparar frases.** Enumerar
redacciones a mano no puede funcionar, porque el idioma tiene infinitas — y
además es lo que invita al salvoconducto.

Lo que sí es derivable, sin listas y sin juzgar prosa: **la cabecera tiene que
NOMBRAR cada columna afectada**. Una cabecera que solo tranquiliza no pasa,
porque no las nombra; y quien lea únicamente `listar_tablas` sabe de cuáles
desconfiar. Comprobado que **sigue cortando el caso real** de la 15ª: la cabecera
antigua cae por cuatro tests.

**Límite declarado**: decidir si un texto «tranquiliza» no es derivable, así que
no se intenta. Se comprueba lo objetivo —el marcador y los nombres— y lo demás
queda en revisión humana. Es preferible a una comprobación que aparenta cubrirlo
y no cubre.

Las tres vías quedan como **control permanente**, incluida la de la constante,
cuyo nombre se compone en tiempo de ejecución: escribirlo entero hacía que el
control **se cazara a sí mismo**, que fue el primer intento.

## El 22→9, en las fichas de columna

Las cabeceras ya lo decían y las tres fichas de columna no. Corregido: la causa
son **22 obras** con dos fases, de las que **9** llegan a duplicar filas en el
fact. Las cabeceras remitían a «la consulta que da ese número» y esa consulta
devuelve 9.

Publicado en **versión 7**, biyección exacta 103/103 y lo publicado casa con el
árbol.

---

# T40 · Corregir lo que la batería delató (2026-08-25)

Retomada tras la parada por límite de gasto del 2026-08-22
(`progress/parada_2026-08-22_limite_gasto.md`). Cinco encargos por gravedad,
más tres cosas que llegaron del agente de `mcp-bbdd`
(`progress/impl_F-006_mcp_bbdd.md`, que **no es mío**).

**El diff preservado (`progress/pendiente_T40_retenciones.diff`) NO se aplicó**,
y con razón: proponía `codigo_obra -> maestro.obras.codigo_obra` como «la vía
buena». Medido, ese JOIN convierte las 261 filas de `v_pbi_retencion_obra` en
**329**, porque el maestro repite código. Habría cambiado un JOIN vacío por uno
que multiplica importes, que es peor. Se reaprovechó su diagnóstico —el centro
de coste— y se descartó su conclusión.

## 1 · La relación que devolvía cero filas — y eran TRES, no una

Lo primero fue **derivar la comprobación**, no arreglar la ficha a mano: nuevo
comando `python main.py check-relaciones`, que ejecuta el JOIN de cada relación
declarada y falla si devuelve cero casos. Se derivan del diccionario, así que
una relación nueva entra sola.

La puerta encontró **tres relaciones rotas**; la batería había visto una:

```
KO   retenciones.movimientos.obra_id -> maestro.obras.obra_id: 0 de 261
KO   retenciones.v_pbi_retencion_obra.obra_id -> maestro.obras.obra_id: 0 de 261
KO   retenciones.v_pbi_retencion_obra.obra_id -> cierre.v_pbi_cierre_cabecera.obra_id: 0 de 261
```

**La causa, y el camino real.** `obra_id` en `retenciones` sale de
`COALESCE(NULLIF(p.cenide,0), ...)` en `sql/retenciones/01_movimientos.sql`:
es el `ide` del **centro de coste**, una entidad `raw.con` con `tip = 21`,
distinta y contigua a la de la obra (`tip = 42`). La obra 0655 es `1990273`
como obra y `1990274` como centro de coste.

El puente existe y está publicado: **`raw.obr.cenide`** enlaza obra → centro de
coste, y eso ya está expuesto en
**`cierre.v_pbi_cierre_cabecera.centro_coste_ide`**. Medido el 2026-08-25:

| Camino | Casan | Efecto en filas |
|---|---|---|
| `obra_id -> maestro.obras.obra_id` | **0 de 261** | cero filas, en silencio |
| `codigo_obra -> maestro.obras.codigo_obra` | 257 de 257 | 261 filas → **329** (fan-out) |
| `obra_id -> cierre...centro_coste_ide` | **249 de 261 (95 %)** | 261 filas → 251 |

Se declara el tercero, `N:N` (dos `centro_coste_ide` se repiten, 4 filas) y
diciendo que los 12 que no casan son centros de coste de obras sin cabecera de
cierre, que **se pierden en un INNER JOIN**.

**Y el defecto vivía en el campo de al lado, otra vez.** Un barrido sobre el
diccionario **cargado** (nunca sobre el YAML crudo: el plegado ya rompió cuatro
barridos de esta feature) encontró la misma afirmación falsa —«el centro de
coste coincide con la obra»— en tres fichas más, las tres de `compras`:

| Columna | Casan como obra | Casan como centro de coste |
|---|---|---|
| `compras.contrato_lineas.centro_coste_id` | **0 de 447** | 432 |
| `compras.albaran_lineas.centro_coste_id` | **0 de 519** | 484 |
| `compras.factura_lineas.centro_coste_id` | **0 de 611** | 526 |

**Un test verde sostenía la mentira.**
`test_f006_r2_retenciones_explica_la_cascada_de_atribucion_a_obra` exigía
literalmente `assert "98" in obra.significado`, o sea la frase «coincide con la
obra en torno al 98 % de los casos». Sustituido por una guarda de los hechos
medidos más un barrido que impide que la frase vuelva a ninguna ficha.

**Resultado de la puerta tras la corrección**: `0 que NO unen`.

## 2 · «`contratos.descripcion` suele nombrar el oficio»: falso, medido

De los 18.879 contratos, **5 (0,03 %)** contienen «fontan» y **17.372 (92 %)**
repiten el nombre del proveedor. La heurística que sí funciona es
`compras.fact_compras_linea.descripcion`: **4.506 líneas en 293 obras y 227
proveedores**. Las dos fichas se contradecían y la equivocada era la que la
batería designaba como objeto esperado; ahora la de contratos manda a la otra, y
la pregunta del oficio vive en la ficha que puede contestarla.

De paso, **H-9**: la descripción de `compras.contratos` prometía «a quién, para
qué obra, **por cuánto**» y la tabla no tiene ninguna columna de dinero. Eso es
lo que hizo escribir `importe_contrato`, que no existe.

## 3 · `es_activa` miente igual que la columna de la que aparta

`maestro.obras.es_activa` es TRUE en **919 de 919** porque `fecha_baja` está a
NULL en las 919. `R-OBRA-ACTIVA` apartaba de `stg.obras.activa` (literal TRUE,
583 de 583) para empujar a la gemela.

La regla ahora dice que **«cuántas obras activas tenemos» no se puede responder
con el datamart**, y da los dos criterios que sí discriminan con su alcance:
`estado_id` (once valores: 465 en el `25`, 226 en el `1`, 175 en el `15` = EN
CURSO, sin catálogo de nombres) y las fechas reales de la cabecera de cierre
(**107 obras con inicio real y sin fin real**, sobre 583 de las 919).

El defecto vivía en **cinco sitios**: la regla, la descripción de
`maestro.obras`, sus columnas `es_activa`/`fecha_baja`/`estado_id`,
`stg.obras.activa` —que seguía mandando a la gemela rota— y
`cierre...fecha_fin_real`. Y dos `ejemplos_preguntas` anunciaban preguntas que
la ficha responde mal.

## 4 · El coste de consulta, que no existía — y son CUATRO vistas

Medido el 2026-08-25 con `SELECT * ... LIMIT 5`:

| Objeto | Sin filtro | Filtrado por obra |
|---|---|---|
| `mart.v_pbi_cp_tipologia` | >40 s | **>60 s** |
| `mart.v_fact_periodificado` | >40 s | **>60 s** |
| `cierre.v_pbi_cierre_indirectos_detalle` | >40 s | **>60 s** |
| `mart.v_master_vigente_anual` | >40 s | **20 s** |
| `mart.v_master_versiones_tipadas` | 16 s | — |
| `count(*)` de `stg.plan_mensual` | 25 s | — |
| `count(*)` de `compras.fact_compras_linea` | 10 s | — |
| `maestro.obras`, `v_pbi_cierre_resumen`, `v_pbi_proveedor_obra`, `v_pbi_partida_coste` | <5 s | — |

**Cómo llega al agente sin tocar el contrato de `_meta`**: como regla dura
`R-COSTE-CONSULTA` cuyo `ambito` son los objetos caros. `derivar_avisos` cuelga
su código de cada ficha alcanzada, así que aparece en `describir_tabla` sin
haber leído el bloque global. Se descartó añadir una columna a
`_meta.diccionario` justamente para no romper a `mcp-bbdd`, que ya cerró.

**Y las dos que no devuelven ni una fila dejan de ser superficie de consumo.**
`consumo_recomendado: false` con su `motivo_no_consumo`: recomendar para
consulta algo que no se puede consultar es la misma clase de defecto que una
relación que no une. La superficie de consumo pasa de **48 a 46**.

## 5 · El dato absurdo, ahora avisado — y la barrera no cubría donde falló

Los órdenes de magnitud eran **cuatro, las cuatro de `retenciones`**. En
`compras` salieron 68,7 billones de euros y ninguna barrera saltó porque para
ese esquema no había ninguna.

**Cinco magnitudes nuevas**, medidas contra la base: facturado neto anual
(113,6 M€ en 2025; 53,0/70,9/91,2 en 2022-2024, con banda de cordura 40-150 M€),
entregado y no facturado (260,6 M€ saneado), coste real anual del seguimiento
(105,9 M€ en 2024, con los cuatro escenarios en el mismo orden), **techo por
obra (32,7 M€**, que es como se caza un fan-out en una sola obra) y venta
ejecutada del cierre (110,0 M€, que tiene que parecerse a los 110,1 del
seguimiento).

**`R-ALBARAN-ABSURDO`** deja la anomalía con nombre y apellidos: dos líneas del
albarán `AC21/03345` (2021-02-28, obra 0609, líneas **588705** y **588733**,
«SUMINISTRO PLATO DUCHA ACRÍLICO») con `cantidad = 184.493.959.731` e
`importe_pendiente_facturar = 34.361.999.999.898,80 €` cada una. Inflan la vista
de **260,6 M€** a **68.724.260,6 millones**. La regla y la descripción del
objeto llevan el aviso: los dos canales que un agente lee.

**Dos tests sostenían el hueco** y hubo que ampliarlos: el vocabulario de
`criterio` no admitía `anual` ni `maximo`, y la fuente exigía un `.md`, lo que
prohibía declarar una medición contra la base. Ahora vale la medición **si lleva
su fecha**, que es lo que evita que envejezca en silencio.

## Lo que llegó del consumidor (`mcp-bbdd`)

- **Erratas de `_meta.diccionario_contexto`**: el valor `ocultar` **faltaba** en
  los `valores posibles` de su columna `bloque` llevándose publicado desde el
  principio. Corregido. La otra errata («~21 filas») **ya no está en el árbol**:
  el barrido sobre el diccionario cargado no la encuentra, así que el consumidor
  la leyó de una versión publicada anterior. Hoy son **29 filas** y el recuento
  no se escribe en la ficha a propósito, porque caduca: se cuenta con SQL.
- **Intragrupo**: `R-PROVEEDOR-INTRAGRUPO`. El nº 1 del ranking de facturado es
  `CONSTRUCCIONES RUESMA, S.A.` con **23,8 M€**, más del doble que el segundo, y
  detrás hay UTEs (`UTE VALDEBEBAS VI` 9,7 M€, `UTE JARAS BOADILLA` 8,1 M€) que
  son coinversiones. **Resolverlo bien exige modelar el intragrupo** —marcar las
  sociedades del grupo y decidir qué se hace con las UTE— y eso **no es de esta
  feature**: va al backlog. Aquí solo se declara la trampa.

## Los dos AVISO de la puerta, declarados en su `porque`

`check-relaciones` avisa (sin fallar) cuando una relación une por debajo del
50 %. Los dos casos son huecos legítimos y ahora están medidos en la ficha:

- `retenciones.tipos -> movimientos`: de los **2.177** tipos del catálogo solo
  **15** se han aplicado alguna vez.
- `maestro.proveedores -> movimientos.entidad_id`: solo **1.269 de los 9.545**
  proveedores tienen alguna retención; con `INNER JOIN` desaparecen 8.276.

## Lo que queda sin comprobar, y por qué

Tras la corrección, `check-relaciones --todos` da **77 que unen, 2 con cobertura
escasa, 0 que NO unen, 17 sin comprobar, 2 con un extremo que no existe**. Sale
con código 1 por los dos últimos grupos, y las causas están todas declaradas:

- **2 no existen**: las dos relaciones de `cierre.v_pbi_planif_vs_real`, que el
  repositorio crea y la base no tiene porque `build-cierre` no se ha vuelto a
  lanzar. **Deuda anterior**, ya documentada en este mismo informe.
- **2 con muestra vacía**: `aux.periodificacion_partida`, que se crea vacía por
  diseño (lo dice su propia ficha y la de `mart.v_fact_periodificado`).
- **13 por timeout**: todas sobre los objetos que `R-COSTE-CONSULTA` declara
  caros. Se reintentaron a 90 s y **tres pasaron a verde**
  (`v_pbi_cierre_generales_detalle.tipologia` 100 %,
  `v_pbi_partida_coste.partida_id -> fact_seguimiento_mensual` 95 %,
  `proveedores_obra.obra_id -> maestro.obras` 100 %); **cuatro siguen sin
  comprobar a 90 s** y quedan como deuda declarada:
  `proveedores_obra.obra_id -> v_pbi_proveedor_obra`,
  las dos de `v_master_versiones_tipadas.obra_id` y
  `stg.ambitos.ambito_id -> stg.plan_mensual.ambito_id`.

No se cuentan como OK: un timeout es «no lo sabemos», y contarlo como correcto
convertiría el límite de tiempo en una forma de aprobar sin mirar.

## Fase RED (nivel `critico`)

El módulo de la puerta se escribió **después** de sus tests. Traza real del
fallo, con el comando exacto:

```
$ python -m pytest tests/test_f006_relaciones.py -x -q
ImportError while importing test module 'tests\test_f006_relaciones.py'.
Traceback:
tests\test_f006_relaciones.py:34: in <module>
    from etl_sigrid.infrastructure.postgres.relaciones_sql import (
E   ModuleNotFoundError: No module named 'etl_sigrid.infrastructure.postgres.relaciones_sql'
=========================== short test summary info ===========================
ERROR tests/test_f006_relaciones.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.54s
```

Escrito el módulo, la misma orden da `23 passed in 0.72s`.

Las correcciones de fichas siguieron el mismo orden en el punto que más importa:
el test que sostenía la afirmación del 98 % **falló primero** al corregir la
ficha, y esa es la evidencia de que guardaba la mentira:

```
$ python -m pytest tests/ -q -k "f006"
FAILED tests/test_f006_fichas.py::test_f006_r2_retenciones_explica_la_cascada_de_atribucion_a_obra
    assert "98" in obra.significado, "la cascada acierta en torno al 98 % por cenide"
1 failed, 1218 passed, 124 skipped, 798 deselected
```

## Publicado

```
diccionario_publicado_ok  version=8  n_objetos=103  n_reglas=16  n_columnas=798
                          cobertura_cols=100.0  contexto=29  hash=86651c493cb7
[SUCCESS] publicar_diccionario   rows=149   duration=1.2s
```

`python main.py check-diccionario`: **`OK lo publicado ES lo del árbol`**
(versión 8). La biyección es **102 de 103**, con la única huérfana
`cierre.v_pbi_planif_vs_real` — la deuda anterior de `build-cierre`, no algo que
introduzca T40. El árbol estaba **commiteado antes de publicar**.

## Verificaciones MANUAL pendientes

- **Relanzar la batería de 18 preguntas** contra la versión 8 publicada. T40
  corrige lo que la batería delató, pero **no vuelve a ejecutarla**: que las
  fichas ya no mientan no demuestra que las respuestas salgan bien.
- **`build-cierre`** para que `cierre.v_pbi_planif_vs_real` exista y sus dos
  relaciones se puedan comprobar.
- Decidir con el humano si el **intragrupo** entra al backlog como feature.

## Evidencias

| Evidencia | Valor |
|---|---|
| **Tests ejecutados** | **2025 pasados**, 124 saltados, 0 fallos (`bash harness/init.sh`) |
| **Cobertura de las líneas cambiadas** | **98,0 %** — 1117/1140, umbral 80 %, nivel `critico` |
| **Tiempo de la suite** | **347,32 s** (5 min 47 s) |
| **Mutantes generados y supervivientes** | **NO MEDIDO, y a propósito** |

Salida literal de la puerta:

```
[OK] pytest en verde (con medición de cobertura)
[OK] PUERTA COBERTURA: 98.0% de 1140 líneas cambiadas cubiertas (1117/1140, umbral 80%, nivel critico)
[OK] Rama actual: feature/F-006-mcp-azure
ENTORNO LISTO. Puedes trabajar.
```

La suite pasa de **1985 a 2025** tests (+40).

**Sobre la mutación.** No se lanzó campaña y **no se aporta ningún número**,
porque en este repositorio no serían evidencia: **F-041** tiene registrado que
la puerta de mutación cuenta cualquier `returncode != 0` como mutante muerto,
sobre una suite ya rota en el worktree. Dar un porcentaje de aquí sería
exactamente el tipo de cifra plausible y falsa que toda esta feature existe para
evitar. Queda como deuda de F-041, con su superviviente real conocido
(`and`→`or` en `diccionario_sql.py:297`).

## Comandos que lo verifican

```
bash harness/init.sh                              # 2025 tests, cobertura 98,0 %
python main.py check-relaciones --todos           # 0 que NO unen
python main.py check-diccionario                  # publicado == árbol, versión 8
python -m pytest tests/test_f006_relaciones.py    # 23 tests de la puerta nueva
```

---

# 17ª pasada · los cuatro hallazgos abiertos del review (2026-08-26)

Encargo del líder: cerrar H2, H3, H4 y H5. H1 (puerta de mutación) viene arreglado
río arriba en el arnés 1.7.4 y no se toca `harness/`. El bloque de Power BI (T32–T34)
está entregado a F-034. La campaña de mutación **no se relanza** (regla RM1: la lanza
el humano con el árbol quieto).

**Aviso importante sobre el estado del review.** `progress/review_F-006.md` es el
resumen escrito el 2026-08-25 al partir el papeleo, y su tabla de «hallazgos abiertos»
copia el veredicto de la 16ª pasada **sin reverificar el árbol**. La 16ª pasada y sus
arreglos viajan en **el mismo commit** (`3ec962c`, 2026-08-22): el reviewer escribió el
informe, el implementer arregló y se comitearon juntos. Resultado: H2, H3 y H4 ya
estaban cerrados en el árbol cuando el resumen los listó como abiertos. Verificado uno
a uno, no dado por bueno.

## H2 · El mutante vivo de `_clave_de` — YA MUERTO, y ahora por tres vías

Fase RED, mutante aplicado a mano sobre
`etl_sigrid/infrastructure/postgres/diccionario_sql.py:297`
(`isinstance(entrada, str) and entrada.strip()` → `or`):

```
$ .venv/Scripts/python.exe -m pytest tests/test_f006_contexto.py -q -p no:cacheprovider
....................F                                                    [100%]
___ test_f006_r28_control_toda_entrada_de_lista_de_texto_se_identifica_sola ___
>       assert _clave_de("", 2) == "2"
E       AssertionError: assert '' == '2'
tests\test_f006_contexto.py:267: AssertionError
1 failed, 20 passed in 1.00s
```

O sea: **el mutante ya moría** con el test que la 16ª pasada añadió. Lo que faltaba era
lo que el líder pide explícitamente: los tres casos de cadena con su valor devuelto
comprobado. Medido bajo el mutante, importando la función directamente:

```
MUTANTE and->or aplicado:
'   '       -> '   '       (el original devuelve '4')
'\n\t '     -> '\n\t '     (el original devuelve '6')
'_built_at' -> '_built_at'
```

Los tres casos entran al test (cadena normal, vacía y de solo espacios), así que
**cualquiera de ellos mata el mutante por su cuenta** y el arreglo no depende de que
nadie borre una línea. Mutante revertido y el fichero comprobado idéntico a HEAD antes
de comitear.

## H3 · El guardián de coherencia — las tres vías cerradas; la CLASE, no

Las tres evasiones que el reviewer consiguió están cerradas desde `3ec962c`: no hay
salvoconducto, se compara con `tests/_texto.py::contiene()` y la lista
`_TRANQUILIZADORAS` se sustituyó por un criterio (**la cabecera tiene que NOMBRAR cada
columna afectada**). El control permanente
`test_f006_r10_control_el_guardian_de_coherencia_muerde` recorre las tres y sigue verde.

**Lo que seguía abierto es la clase.** El guardián que vigilaba el plegado
(`test_f006_r26_ninguna_guarda_de_prosa_compara_subcadenas_crudas`) era una **lista de
dos ficheros escrita a mano** que solo comprobaba si importaban `contiene` —ni una
comparación— y dejaba fuera `test_f006_stg_trampas.py`, donde
`"NO esta afectada" in mes.significado` seguía cruda **dentro del propio dispositivo
escrito para evitar eso**. Es la vía 2 del reviewer, viva en el guardián de al lado.

Sustituida por un criterio derivado: los campos de prosa salen de las dataclases
`Columna`/`Ficha`/`Regla` con `dataclasses.fields`, y un barrido `ast` recorre todo
módulo de tests que cargue el diccionario buscando `"varias palabras" in <campo>`.

Fase RED (22 sitios en 4 ficheros):

```
E       AssertionError: estas comparaciones son ciegas a una frase partida por una
        línea en blanco del plegado YAML; usa `tests._texto.contiene`:
E           test_f006_fichas.py:1055: «todas las columnas de periodificacion son nulas» in grano
E           test_f006_fichas.py:1112: «cinco porcentajes» in significado
E           test_f006_fichas.py:1307: «NUNCA SE CONSULTA SIN FILTRAR POR OBRA» in descripcion
E           test_f006_fichas.py:1337: «NO se puede responder» in regla
E           ... (22 en total)
E           test_f006_regla_de_oro.py:127: «no se deja segmentar» in motivo
E           test_f006_reglas.py:614: «68,7 BILLONES» in descripcion
E           test_f006_stg_trampas.py:702: «NO esta afectada» in significado
1 failed, 1 passed
```

Las 22 reescritas a `contiene(...)`. Ninguna de las que eran `not in` se puso roja al
endurecerse, así que **no había ninguna afirmación falsa escondida** tras ellas.
`NUMEROS_DEL_DEFECTO` (que compara contra una variable local, fuera del alcance del
barrido `ast`) se corrigió a mano, y el caso quedó como cuarta vía del control
permanente.

**Límite declarado en el docstring**: el barrido reconoce la prosa por el nombre del
campo, así que no ve un texto que pasó antes por una variable local
(`texto = f"{ficha.descripcion} {ficha.grano}"`). Seguir el flujo de datos no se
intenta; esos sitios se corrigen a mano y se dicen, en vez de fingir cobertura.

## H4 · El 22 → 9 — ya viajó; lo que faltaba era la guarda

Barrido del diccionario **cargado** (no del YAML crudo, que no ve las frases plegadas),
campo a campo, cabecera y columnas, sobre el 22 suelto y sin fechas ISO. **Siete
apariciones, las siete bien atribuidas**:

| Dónde | Qué dice |
|---|---|
| `mart.fact_seguimiento_mensual.grano` (×2) | «22 obras tienen dos fases… —eso es la CAUSA—, pero solo 9 llegan a producir filas duplicadas aquí» |
| `mart.fact_seguimiento_categoria::importe_origen.significado` | «la causa son 22 obras…, de las que **9** llegan a duplicar filas en el fact» |
| `…::importe_origen_raw.significado` | ídem |
| `mart.v_pbi_fact_categoria::importe_origen.significado` | ídem |
| `mart.fact_seguimiento_categoria.grano` y `mart.v_pbi_fact_categoria.descripcion` | eran la remisión falsa de H5; corregidas ahí |

Las tres fichas de columna que el reviewer citaba **ya llevaban la corrección**
(`3ec962c`). Lo que no había era guarda, así que se añade el criterio: **un párrafo que
nombre el 22 tiene que nombrar el 9**, porque el 22 mide la causa en `stg.fases` y el 9
el efecto en el fact.

Fase RED, inyectando la regresión (quitando «de las que 9 llegan a duplicar filas en el
fact» de `importe_origen`):

```
E  AssertionError: mart.fact_seguimiento_categoria::importe_origen.significado#1 nombra
   las 22 obras sin decir que solo 9 duplican filas aquí. El 22 mide la CAUSA en
   `stg.fases`; atribuirlo al duplicado del fact es la cifra mal atribuida que ya se
   publicó.
1 failed, 7 passed
```

Regresión revertida y verde.

## H5 · La remisión falsa — ABIERTA de verdad, y corregida

Las dos fichas del preagregado decían:

> «La consulta que da ese numero esta en el grano de `mart.fact_seguimiento_mensual`,
> junto a la explicacion de por que 8.778, 37 y 22 son numeros distintos…»

Y la consulta publicada allí devuelve **8.778 y 9 obras**, no las 37 celdas ni los
39,07 M€. Texto nuevo, en `mart.fact_seguimiento_categoria.grano` y en
`mart.v_pbi_fact_categoria.descripcion`:

> «La consulta publicada en el grano de `mart.fact_seguimiento_mensual` devuelve 8.778
> combinaciones con dos filas, en 9 obras: esa es la CAUSA de este defecto, no su
> medida. Las 37 celdas y los 39,07 M EUR se midieron aparte el 2026-08-22 y su consulta
> NO esta publicada todavia. Alli esta ademas por que 8.778, 37 y 22 miden cosas
> distintas.»

Se dice el número correcto **y** se declara el hueco (h6 sigue abierto: la consulta del
37 / 39,07 M€ no se puede medir sin base).

Guardián derivado, sin listas de frases: se detectan las remisiones a la consulta de
otro objeto y se exige que **los números que le atribuyen estén declarados junto a esa
consulta** —el párrafo del `SELECT` y el que lo presenta—. Una remisión sin ningún
número tampoco pasa: es la formulación vaga con la que entró el defecto.

Fase RED, los dos sitios:

```
E  AssertionError: mart.v_pbi_fact_categoria.descripcion atribuye ['22', '37'] a la
   consulta de `mart.fact_seguimiento_mensual`, y allí no está declarado que la consulta
   dé eso. Quien la ejecute para comprobar el aviso obtendrá otro número y desconfiará
   del aviso entero.
     frase: La consulta que da ese numero esta en el grano de
     `mart.fact_seguimiento_mensual`, junto a la explicacion de por que 8.778, 37 y 22
     son numeros distintos que miden cosas distintas.
2 failed, 2 passed
```

## Diccionario a versión 9 — NO publicado

`config/diccionario/00_global.yaml` pasa de 8 a 9 porque el contenido cambió. **No se ha
ejecutado `publicar-diccionario`**: escribe en Azure y esa autorización es del humano.
Mientras tanto `_meta` sirve la **versión 8**, con la remisión falsa dentro. Tampoco se
han podido ejecutar `check-diccionario` ni `check-relaciones`, que exigen base.

## Lo que NO se ha hecho, y por qué

- **H1 / T41 · campaña de mutación**: no se relanza (RM1). Sin número de mutación.
- **h6 · publicar la consulta del 37 celdas / 39,07 M€ y la del 22 obras**: exige medir
  contra la base. Se ha declarado el hueco en la ficha en vez de inventar una consulta.
- **h7 a h10** (higiene del review): fuera del encargo de esta sesión.
- **Republicar en `_meta`**: parado a la espera del humano.
