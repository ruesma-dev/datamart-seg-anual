<!-- progress/impl_F-019.md -->
# F-019 · Build de `stg.plan_mensual` por tramos — Informe del implementer

Rama `feature/F-019-plan-mensual-por-tramos`. Rigor **`critico`**.
Spec: `specs/F-019-plan-mensual-por-tramos/` (requirements R1–R17, design con
DA-1..DA-4 aprobadas por el humano el 2026-08-10 tal cual se proponían).

> Este informe se escribe **según avanza el trabajo**, no al final.

## Regla de entorno que condiciona todo el trabajo

`.env` apunta a **`psql-albaranes-rs9k2`** (producción compartida). Este agente
**no ha abierto ninguna conexión** a BBDD ni a la API: ni `python main.py` en
ninguna forma, ni `psql`. Todos los requisitos `[MANUAL-local]` y
`[MANUAL-Azure]` (R1, R2, R13, R14, R15, R16) quedan **preparados como texto
ejecutable** y los lanza el humano. El guion está en `progress/current.md`
§F-019 y los comandos exactos, en `requirements.md`.

## Orden de tareas: desviación declarada (T1/T2 antes que T3)

`tasks.md` pone T1 (mediciones en local) y T2 (confirmar constantes) **antes**
que el código, y son tareas del **humano**: exigen un PostgreSQL con la carga
completa. No se han ejecutado todavía.

Se implementa T3–T10 con los **defaults propuestos y aprobados en la spec**
(`PG_TRAMO_MAX_FILAS=1_000_000`, `PG_DISCO_TOTAL_GB=32`,
`PG_DISCO_LIMITE_PCT=80`). La implementación **no depende de esos números**:
los tres son *settings* con default, cambiables por variable de entorno sin
tocar código ni tests (hay un test que lo demuestra,
`test_f019_r4_maximo_configurable_desde_settings`). Lo que T1/T2 pueden cambiar
es el **valor**, nunca el diseño.

**Condición de cierre que hereda el humano**: T1 y T2 deben ejecutarse y
anotarse **antes de T12** (la verificación contra Azure). Si T1 revelara una
obra con peso > `PG_TRAMO_MAX_FILAS` que domine el reparto (riesgo 3 del
design), hay que revisar la constante antes de lanzar nada contra el servidor
compartido.

---

# Fase RED (obligatoria en rigor `critico`)

Cada bloque trae el **comando exacto** y la **salida real** del fallo antes de
que existiera el código. No hay resúmenes: son las trazas pegadas.

## RED de T3 · `etl_sigrid/domain/tramos.py` (R3, R4, R5)

**Paso 1 — el módulo no existe todavía.** Los tests se escribieron primero:

```
$ python -m pytest tests/test_f019_tramos.py -q --tb=short
=================================== ERRORS ====================================
_________________ ERROR collecting tests/test_f019_tramos.py __________________
ImportError while importing test module 'C:\...\tests\test_f019_tramos.py'.
Traceback:
tests\test_f019_tramos.py:16: in <module>
    from etl_sigrid.domain.tramos import (
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.tramos'
=========================== short test summary info ===========================
ERROR tests/test_f019_tramos.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.15s
```

**Paso 2 — con las firmas puestas y SIN lógica** (`planificar_tramos` devuelve
`[]`), que es la RED que de verdad interesa: enseña que los tests miden el
comportamiento, no la existencia del import.

```
$ python -m pytest tests/test_f019_tramos.py -q --tb=line
     +    where [] = planificar_tramos({101: 900000, 102: 420000, 103: 380000, 104: 250000, ...}, 1000000)
tests\test_f019_tramos.py:75: assert 0 > 0
E   assert [] == [Tramo(indice...2), peso=100)]
      Right contains one more item: Tramo(indice=1, obras=(1, 2), peso=100)
tests\test_f019_tramos.py:83: assert [] == [Tramo(indice...2), peso=100)]
E   assert 0 == 1
     +  where 0 = len([])
tests\test_f019_tramos.py:93: assert 0 == 1
E   Failed: DID NOT RAISE ValueError
tests\test_f019_tramos.py:103: Failed: DID NOT RAISE ValueError
E   assert [] == [Tramo(indice...1), peso=900)]
      Right contains one more item: Tramo(indice=1, obras=(2, 3, 4, 1), peso=900)
tests\test_f019_tramos.py:123: assert [] == [Tramo(indice...1), peso=900)]
=========================== short test summary info ===========================
FAILED tests/test_f019_tramos.py::test_f019_r3_plan_de_tramos_particiona_las_obras
FAILED tests/test_f019_tramos.py::test_f019_r4_un_maximo_pequeno_produce_mas_tramos_igual_de_acotados
FAILED tests/test_f019_tramos.py::test_f019_r4_un_tramo_que_da_justo_el_maximo_no_se_parte
FAILED tests/test_f019_tramos.py::test_f019_r4_obra_gigante_va_en_tramo_unitario_con_warning
FAILED tests/test_f019_tramos.py::test_f019_r4_un_maximo_no_positivo_es_un_error_de_configuracion
FAILED tests/test_f019_tramos.py::test_f019_r5_las_obras_se_empaquetan_de_mayor_a_menor_peso
6 failed, 4 passed in 0.03s
```

**Honestidad sobre los 4 «passed»**: con la lista vacía, cuatro tests pasan
por vacuidad (recorren cero tramos). El plan de tramos real los pone a
trabajar; los seis que fallan son los que fijan el comportamiento. Se anota
porque un «4 passed» sin explicar induce a error.

**Verde tras implementar**: `10 passed in 0.06s`.


## RED de T4 · settings `PG_TRAMO_MAX_FILAS` / `PG_DISCO_TOTAL_GB` / `PG_DISCO_LIMITE_PCT`

```
$ python -m pytest tests/test_f019_tramos.py -q -k "r4_maximo_configurable" --tb=short
F                                                                        [100%]
_______________ test_f019_r4_maximo_configurable_desde_settings _______________
tests\test_f019_tramos.py:132: in test_f019_r4_maximo_configurable_desde_settings
    assert por_defecto.tramo_max_filas == 1_000_000
.venv\Lib\site-packages\pydantic\main.py:1042: in __getattr__
    raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
E   AttributeError: 'PostgresSettings' object has no attribute 'tramo_max_filas'
=========================== short test summary info ===========================
FAILED tests/test_f019_tramos.py::test_f019_r4_maximo_configurable_desde_settings
1 failed, 10 deselected in 0.56s
```

**Verde tras implementar**: `11 passed in 0.47s`.

## RED de T5 · el SQL filtra por obra en las dos ramas (R6)

Los tests estáticos existían antes de tocar el `.sql` (primero se añadieron
las constantes `MARCADOR_FILTRO_OBRAS` y `RAMAS_CON_FILTRO` al step, para que
el test lea el mismo contrato que usa el código):

```
$ python -m pytest tests/test_f019_tramos.py -q -k f019_r6 --tb=short
________________ test_f019_r6_marcador_presente_en_ambas_ramas ________________
tests\test_f019_tramos.py:175: in test_f019_r6_marcador_presente_en_ambas_ramas
    assert MARCADOR_FILTRO_OBRAS in rama_master, "rama master sin filtro de tramo"
E   AssertionError: rama master sin filtro de tramo
E   assert '/*F019_FILTRO_OBRAS*/' in 'master_planif AS (\n    SELECT\n ...'
_________________ test_f019_r6_el_sql_ya_no_contiene_truncate _________________
tests\test_f019_tramos.py:186: in test_f019_r6_el_sql_ya_no_contiene_truncate
    assert "TRUNCATE" not in _sql_plan_mensual().upper()
E   AssertionError: assert 'TRUNCATE' not in '-- ETL_SIGR...S_CON_LAG;\n'
E     'TRUNCATE' is contained here:
E       TRUNCATE TABLE STG.PLAN_MENSUAL;
=========================== short test summary info ===========================
FAILED tests/test_f019_tramos.py::test_f019_r6_marcador_presente_en_ambas_ramas
FAILED tests/test_f019_tramos.py::test_f019_r6_el_sql_ya_no_contiene_truncate
2 failed, 1 passed, 11 deselected in 0.82s
```

**Verde tras cambiar el SQL**: `14 passed in 0.59s`.

**Diff del `.sql`, verificado línea a línea** (`git diff --stat`: 20 inserciones,
2 borrados; de las inserciones, 18 son comentario de cabecera):

- `- TRUNCATE TABLE stg.plan_mensual;` (y su línea en blanco) — se va al step.
- `+ AND pp.obra_id = ANY (/*F019_FILTRO_OBRAS*/)` en el `WHERE` de
  `master_planif`.
- `+ AND pp.obra_id = ANY (/*F019_FILTRO_OBRAS*/)` en el `WHERE` de
  `reales_base`.

**Cero líneas de lógica de negocio cambiadas**: ni una expresión, ni un
`ROUND`, ni una ventana, ni un comentario de la interpretación del planif. Lo
vigila además `test_f019_r6_la_logica_de_negocio_del_planif_sigue_intacta`.

**Decisión menor tomada aquí** (el design la dejaba abierta): NO se añade el
filtro sobre `fa.obride` en la subconsulta de `raw.obrfasamb`. El design lo
permitía «si el implementer lo decide midiendo», y **medir exige BBDD**, que
este agente tiene prohibida. Añadirlo a ciegas cambiaría el plan de ejecución
de un SQL validado al céntimo sin ninguna evidencia a favor. Queda anotado
como palanca disponible si T12 midiera un coste feo en el join.

**Consecuencia de forma**: en el fichero ya no aparece la palabra TRUNCATE ni
el marcador entre barras fuera de las dos ramas, porque los tests estáticos
son deliberadamente literales (`"TRUNCATE" not in sql.upper()`,
`sql.count(MARCADOR) == 2`). Un test tonto y fuerte se prefirió a uno listo
que hubiera que mantener; el precio es redactar los comentarios sin esas dos
cadenas.

## RED de T6 · composición segura del filtro y métodos nuevos del cliente (R7, R8, R10, R11)

Con las firmas puestas y **sin lógica** (`componer_sql_tramo` devolvía el SQL
tal cual; `BYTES_POR_GB = 0`; los tres métodos devolvían vacío):

```
$ python -m pytest tests/test_f019_tramos.py -q --tb=line
............FFFFFFFFFF...                                                [100%]
E   AssertionError: assert 'A /*F019_FIL...TRO_OBRAS*/ C' == 'A ARRAY[10, ...]::BIGINT[] C'
      - A ARRAY[10, 20, 30]::BIGINT[] B ARRAY[10, 20, 30]::BIGINT[] C
      + A /*F019_FILTRO_OBRAS*/ B /*F019_FILTRO_OBRAS*/ C
tests\test_f019_tramos.py:223: AssertionError
E   Failed: DID NOT RAISE ValueError
tests\test_f019_tramos.py:239: Failed: DID NOT RAISE ValueError
E   Failed: DID NOT RAISE ValueError
tests\test_f019_tramos.py:249: Failed: DID NOT RAISE ValueError
E   AssertionError: assert '/*F019_FILTRO_OBRAS*/' not in '-- etl_sigr...s_con_lag;\n'
      '/*F019_FILTRO_OBRAS*/' is contained here:
        id = ANY (/*F019_FILTRO_OBRAS*/)   -- tramo (F-019)
tests\test_f019_tramos.py:255: AssertionError
E   assert 0 == 1073741824
tests\test_f019_tramos.py:326: assert 0 == 1073741824
E   Failed: DID NOT RAISE ValueError
tests\test_f019_tramos.py:333: Failed: DID NOT RAISE ValueError
E   assert 0.0 == 50.0
     +  where 0.0 = medir_ocupacion_disco_pct(32)
tests\test_f019_tramos.py:342: assert 0.0 == 50.0
E   assert {} == {101: 900000, 102: 420000}
      Right contains 2 more items: {101: 900000, 102: 420000}
tests\test_f019_tramos.py:363: assert {} == {101: 900000, 102: 420000}
E   AssertionError: assert 0 == 4321
     +  where 0 = execute_sql_text('INSERT INTO stg.plan_mensual ...')
tests\test_f019_tramos.py:378: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_f019_tramos.py::test_f019_r7_solo_enteros_en_el_filtro
FAILED tests/test_f019_tramos.py::test_f019_r7_sin_marcador_falla_antes_de_ejecutar
FAILED tests/test_f019_tramos.py::test_f019_r7_un_tramo_sin_obras_no_compone_nada
FAILED tests/test_f019_tramos.py::test_f019_r7_el_sql_real_compuesto_queda_sin_marcadores
FAILED tests/test_f019_tramos.py::test_f019_r8_el_porcentaje_de_ocupacion_va_en_gigabytes_binarios
FAILED tests/test_f019_tramos.py::test_f019_r8_un_disco_total_no_positivo_es_un_error_de_configuracion
FAILED tests/test_f019_tramos.py::test_f019_r8_medir_ocupacion_suma_todas_las_bases_del_servidor
FAILED tests/test_f019_tramos.py::test_f019_r10_una_medicion_vacia_o_nula_no_se_toma_por_cero
FAILED tests/test_f019_tramos.py::test_f019_r3_los_pesos_por_obra_llegan_como_diccionario
FAILED tests/test_f019_tramos.py::test_f019_r11_execute_sql_text_abre_una_conexion_por_llamada
10 failed, 15 passed in 0.62s
```

**Verde tras implementar**: `25 passed in 0.53s`.

**Decisiones de T6**:

- La composición es **textual**, no `%(param)s`. El fichero está lleno de
  porcentajes literales en los comentarios («llega al 93 %») y psycopg los
  leería como marcadores de parámetro. Por eso el blindaje es tan estricto:
  `type(obra) is not int` (y no `isinstance`, porque `bool` es subclase de
  `int` y `ARRAY[True]` no es una lista de obras).
- `medir_ocupacion_disco_pct` **propaga** la excepción; no devuelve 0 ni None.
  Un cero «por si acaso» sería seguir a ciegas, que es lo que hacía el build
  que llenó el disco.
- `execute_sql_text` devuelve el `rowcount` del cursor, no un `COUNT(*)`: un
  seq-scan por tramo sobre millones de filas en 1 vCPU sería castigo gratuito.

## RED de T7 · orquestación por tramos en `build_stg_step` (R8, R9, R10, R11, R12)

Con `_build_plan_mensual_por_tramos` devolviendo `0` sin hacer nada:

```
$ python -m pytest tests/test_f019_tramos.py -q --tb=line -p no:warnings
.......................FFFFFFFFFF..                                      [100%]
E   AssertionError: assert [] == ['pesos', 'tr...icion', 'sql']
      Right contains 6 more items, first extra item: 'pesos'
tests\test_f019_tramos.py:540: AssertionError
E   Failed: DID NOT RAISE PlanMensualAbortado
tests\test_f019_tramos.py:556: Failed: DID NOT RAISE PlanMensualAbortado
E   assert 0 == 2
     +  where 0 = len([])
     +    where [] = <tests.test_f019_tramos.PgFalso object at ...>.sql_ejecutado
tests\test_f019_tramos.py:575: assert 0 == 2
E   AssertionError: assert <StepStatus.SUCCESS: 'SUCCESS'> is <StepStatus.FAILED: 'FAILED'>
=========================== short test summary info ===========================
FAILED tests/test_f019_tramos.py::test_f019_r8_mide_ocupacion_antes_de_cada_tramo
FAILED tests/test_f019_tramos.py::test_f019_r9_supera_limite_aborta_sin_ejecutar_el_tramo
FAILED tests/test_f019_tramos.py::test_f019_r9_una_ocupacion_justo_en_el_limite_no_aborta
FAILED tests/test_f019_tramos.py::test_f019_r9_aborto_deja_la_tabla_vacia_y_failed_en_meta
FAILED tests/test_f019_tramos.py::test_f019_r10_medicion_fallida_aborta_no_continua
FAILED tests/test_f019_tramos.py::test_f019_r11_cada_tramo_en_su_transaccion
FAILED tests/test_f019_tramos.py::test_f019_r11_fallo_de_tramo_limpia_y_para
FAILED tests/test_f019_tramos.py::test_f019_r12_log_por_tramo_con_campos_obligatorios
FAILED tests/test_f019_tramos.py::test_f019_r12_registro_en_meta_por_tramo
FAILED tests/test_f019_tramos.py::test_f019_r4_el_step_avisa_de_la_obra_sobredimensionada
10 failed, 25 passed, 20 warnings in 0.56s
```

**Verde tras implementar**: `35 passed` en el fichero y `377 passed` en la
suite completa.

**Cómo se comprueba el orden, que es lo que importa aquí**: el doble
`PgFalso` deja una **traza cronológica** de todo lo que le piden, y el test de
R8 la compara entera:

```
["pesos", "truncate", "medicion", "sql", "medicion", "sql"]
```

Un vaciado por tramo, una medición después del tramo, o un tramo ejecutado
tras superar el límite cambian esa lista y ponen el test en rojo. Los abortos
la dejan terminada en `"truncate"` y sin el `"sql"` del tramo que no llegó a
ejecutarse.
