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

---

# T8 · Documentación (en el mismo trabajo, no después)

- **`docs/ARCHITECTURE.md`**, nueva sección «El build de `stg.plan_mensual` va
  por tramos (F-019)» dentro de §El datamart en Azure: el incidente con su
  fecha, por qué el corte por obra es estructuralmente equivalente, quién hace
  qué (dominio / step / cliente), transacción por tramo, puerta de disco y los
  tres settings con sus defaults.
- **`azure-apps/datamart_seg_anual.md`** (repositorio `azure-apps`, commit
  local `df5000e`): el aviso del incidente en §Dónde vive el dato y, en §Qué
  rompe este proyecto a otros, qué significa la protección **para quien
  mantiene `albaranes` o `partes`**: que la puerta mira el disco del SERVIDOR
  entero (si lo llena otro proyecto, el que deja de escribir es el datamart),
  que **si alguien hace crecer el disco hay que actualizar
  `PG_DISCO_TOTAL_GB`**, y que quitarle al ETL el `CONNECT` que necesita para
  medir no lo hace más seguro: lo deja ciego y lo para.

Barrido de secretos de F-005 (`test_f005_r21_...`) ejecutado tras escribir la
documentación: **17 passed**, sin falsos positivos de rutas largas (el defecto
conocido que ya mordió en F-004).

---

# T9 · Campaña de mutación (rigor `critico`: cero supervivientes)

**Primera pasada**: 41 mutantes, 37 muertos, **4 supervivientes**. Ninguno se
justificó como equivalente sin pelearlo antes; los cuatro se cazaron con tests
nuevos, y esto es lo que enseñaba cada uno:

| Superviviente | Qué destapaba | Cómo se cazó |
|---|---|---|
| `tramos.py:29` `frozen=True` → `False` | Nadie comprobaba que un `Tramo` sea inmutable: el bucle del step podría reescribir uno a medias y nadie se enteraría | `test_f019_r5_un_tramo_es_un_valor_inmutable_y_cerrado` (asignar `peso` tiene que fallar) |
| `tramos.py:29` `slots=True` → `False` | Ni que sea un valor cerrado: un campo mal escrito se habría creado en silencio | el mismo test: `not hasattr(tramo, "__dict__")` |
| `tramos.py:77` `max_filas <= 0` → `<= 1` | Solo se probaba el 0. Un máximo de 1 fila es raro pero **legítimo** (trocear al extremo) y el mutante lo prohibía | `test_f019_r4_un_maximo_de_una_sola_fila_sigue_siendo_valido` |
| `postgres_client.py:97` `total_bytes <= 0` → `<= 1` | **Este era equivalente de verdad**, y por una mala decisión mía: validar los bytes ya multiplicados hace inalcanzable el valor 1 (son múltiplos de 1 GiB). En vez de justificarlo, se corrigió el código para validar `total_gb`, que es el valor que configura el humano — y entonces el mutante SÍ es distinguible | validación movida a `total_gb <= 0` + caso `porcentaje_ocupacion(536_870_912, 1) == 50.0` |

El cuarto caso merece subrayarse: un mutante equivalente suele ser la señal de
que la comprobación está puesta sobre la variable equivocada. El mensaje de
error también mejoró: ahora nombra `PG_DISCO_TOTAL_GB`, que es lo que hay que
corregir, en vez de hablar de bytes.

**Segunda pasada, con los tests nuevos**:

```
$ python -m harness.mutacion --feature F-019
41 mutantes evaluados, 41 muertos, 0 supervivientes, 0 timeouts en 145.1 s
Informe: progress/mutacion_F-019.md
```

`progress/mutacion_F-019.md` lo confirma: **41 generados, 41 evaluados, 41
muertos, 0 supervivientes, 0 timeouts**, campaña completa (sin muestreo).
Ninguna sección de análisis queda en `PENDIENTE`: no hay supervivientes que
analizar.

---

# T10 · `bash harness/init.sh`

```
[OK] features.json válido
[OK] harness/rigor.json y niveles declarados: válidos
[AVISO] Hay features en estado blocked: revisa progress/current.md   (F-003, que espera a esta feature)
[OK] compileall: sin errores de sintaxis
[AVISO] ruff: 127 avisos (deuda previa, no bloquea)
379 passed, 72 warnings in 4.88s
[OK] pytest en verde (con medición de cobertura)
[OK] PUERTA COBERTURA: 100.0% de 120 líneas cambiadas cubiertas (120/120, umbral 80%, nivel critico)
[OK] Rama actual: feature/F-019-plan-mensual-por-tramos
----------------------------------------
ENTORNO LISTO. Puedes trabajar.
```

Los 127 avisos de `ruff` son **deuda previa del repositorio**: los cinco
ficheros que toca F-019 pasan `ruff check` limpios (`All checks passed!`).

---

# Qué cambió, fichero a fichero

| Fichero | Qué |
|---|---|
| `etl_sigrid/domain/tramos.py` (**nuevo**) | `Tramo` (valor inmutable) y `planificar_tramos` (empaquetado voraz determinista), más `tramos_sobredimensionados`. Cero imports de infraestructura y cero logging: el aviso lo emite quien llama |
| `etl_sigrid/application/steps/build_stg_step.py` | `componer_sql_tramo` (composición blindada del filtro), `PlanMensualAbortado`, `_build_plan_mensual_por_tramos`, `_abortar_plan_mensual`, la marca `por_tramos` del sub-paso y la constante `DIRECTORIO_SQL_STG` |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | `BYTES_POR_GB`, `porcentaje_ocupacion`, las consultas `SQL_OCUPACION_DISCO` y `SQL_PESOS_PLAN_MENSUAL`, y los métodos `fetch_pesos_plan_mensual`, `medir_ocupacion_disco_pct` y `execute_sql_text` |
| `08_plan_mensual.sql` (capa stg) | El marcador de filtro en las dos ramas y el vaciado fuera. **Cero líneas de lógica de negocio** |
| `config/settings.py` | Los tres settings nuevos, con default y descripción |
| `tests/test_f019_tramos.py` (**nuevo**) | 37 tests, todos con nombre trazable `test_f019_rN_*` |
| `docs/ARCHITECTURE.md` | Sección nueva del build por tramos |
| `azure-apps/datamart_seg_anual.md` | Qué significa la protección para `albaranes` y `partes` (commit local `df5000e` en ese repositorio) |

**Ni una dependencia nueva** en `requirements.txt`: todo con lo que ya había.

## Decisiones de diseño (y por qué)

1. **El corte es por obra y la equivalencia es estructural.** Ninguna ventana
   del SQL cruza obras. No es «probablemente equivalente»: lo es por
   construcción. Aun así, el humano lo comprueba al céntimo en R13.
2. **La composición del filtro es textual, no `%(param)s`.** Los comentarios
   del fichero están llenos de porcentajes literales y psycopg los leería como
   marcadores de parámetro. De ahí que la entrada se blinde con
   `type(obra) is not int`, que además rechaza `bool` (cosa que `isinstance`
   no haría, porque `bool` es subclase de `int`).
3. **El sub-paso se marca con un dato (`por_tramos=True`), no con un
   `if sub.name == "build_plan_mensual"`.** Comparar por nombre reparte una
   cadena mágica por el módulo; el flag lo declara la propia lista de
   sub-pasos.
4. **La duración y la ocupación se loguean SIN redondear.** Un `round(x, 2)`
   habría metido una constante que ningún test puede distinguir de
   `round(x, 3)`: un superviviente garantizado y sin ningún valor. Los números
   crudos son además lo que quiere el formato JSON de producción.
5. **El aborto usa una excepción propia** (`PlanMensualAbortado`): al leer el
   fallo se distingue una parada deliberada del guardián de un error
   inesperado. El `except` que ya existía en el bucle de sub-pasos la recoge y
   la convierte en `StepStatus.FAILED`, así que `build_mart` no llega a
   ejecutarse.
6. **No se añadió el filtro sobre `fa.obride`** en la subconsulta de
   `raw.obrfasamb`: el design lo permitía «midiendo», y medir exige BBDD.

## Desviaciones respecto a la spec

1. **T1 y T2 no están hechas** (son del humano y exigen BBDD). Justificado
   arriba, en §Orden de tareas; la implementación no depende de sus números.
2. **`_build_plan_mensual_por_tramos(pg, sql_path)`** recibe la ruta del SQL,
   mientras que el design escribía `(pg)`. Se pasa desde el bucle de sub-pasos
   para no repetir el nombre del fichero en dos sitios.
3. **Todos los tests viven en `tests/test_f019_tramos.py`**, como decía el
   design, incluidos los del step y los del cliente. El fichero es largo; se
   respeta la spec en vez de partirlo por gusto.

## Lo que queda FUERA de lo hecho aquí

- Cualquier ejecución contra una BBDD: R1, R2, R13, R14, R15 y R16 son del
  humano (T1, T2, T11, T12, T13, T14). Sin ellas, **la equivalencia funcional
  está razonada y probada con dobles, pero no comprobada contra datos
  reales**.
- Tocar `infra/env/dev.json` o el `jobProgramable` de F-003 (lo prohíbe R16).
- Optimizar el SQL de la explosión: fuera de alcance por la spec.

---

# Evidencias

| Evidencia | Valor real | De dónde sale |
|---|---|---|
| **Tests ejecutados y resultado** | **379 passed**, 0 failed (37 de ellos `test_f019_*`) | `bash harness/init.sh` → pytest |
| **Cobertura de las líneas cambiadas** | **100,0 %** (120 de 120 líneas; umbral 80 %, nivel `critico`) | línea `PUERTA COBERTURA` de `init.sh` |
| **Mutantes generados y supervivientes** | **41 generados, 41 evaluados, 41 muertos, 0 supervivientes, 0 timeouts** (campaña completa, sin muestreo) | `python -m harness.mutacion --feature F-019` → `progress/mutacion_F-019.md` |
| **Tiempo de ejecución de la suite** | **4,88 s** (la campaña de mutación entera: 145,1 s) | salida de pytest en `init.sh` |

Ninguna de estas cuatro cifras es estimada: todas están copiadas de la salida
de la herramienta que las produce.

---

# Verificaciones MANUAL pendientes (las ejecuta el humano)

Con el comando exacto en `progress/current.md` §F-019 y en
`specs/F-019-plan-mensual-por-tramos/requirements.md`. Resumen:

| Tarea | Requisito | Qué hace el humano | Por qué importa |
|---|---|---|---|
| **T1** | R1 | Cuatro mediciones contra el PostgreSQL **local** | Confirmar o corregir `PG_TRAMO_MAX_FILAS`; detectar una obra que no quepa ni sola |
| **T2** | — | Anotar los números en `design.md` §Mediciones | Que las constantes queden justificadas con datos, no con estimaciones |
| **T11** | R13 | `stage` en local, checksum idéntico y `compare-fingerprints` | **Es la prueba de la equivalencia funcional.** Cualquier diferencia es FALLO |
| **T12** | R14 | Pre-check de la medición con el rol real y, después, `stage` + `build-mart` + `apply-grants` contra Azure vigilando `storage_percent` | Cierra el paso 8 de F-005 y mide el paso 9 |
| **T13** | R15 | Huella de vistas, local contra Azure | Cierra el paso 10 de F-005 |
| **T14** | R16 | `jobProgramable: true` y tanda 2 de F-003 | Es lo que esta feature desbloquea |

**Orden que no se puede invertir**: T1 y T2 antes de T12, y T11 antes de T12.
Lanzar contra Azure sin haber comprobado la equivalencia en local sería
estrenar el troceo directamente sobre el servidor compartido de producción.
