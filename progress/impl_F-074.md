<!-- progress/impl_F-074.md -->
# F-074 · La ingesta que destapa el censo — informe de implementacion

Rigor `estandar`, `sdd=false`: los nueve criterios `acceptance`. Rama
`feature/F-074-ingesta-tablas-del-censo`, seis commits. **No se ha ejecutado
ningun comando que escriba contra Sigrid ni contra el Postgres de Azure**;
tampoco `ingest`, `stage`, `build-mart`, `run-all` ni `bootstrap`.

## 1 · Lo que cambio

**Ingesta**: `config/tables_sigrid.yaml`, de 56 a **65 tablas**, con los dos
arreglos y el motivo escrito de `obrprv`. **Diccionario**: nueve fichas nuevas,
la de `prvcer` corregida, `version` 17, y el recuento al dia en los cinco
documentos que lo citaban (130 -> **139** objetos). **MCP**: la lista de
exclusion, de dos tablas a **cuatro**, en `config/settings.py`,
`infra/sql/02_roles.sql` y `.env.example`. **Tests**: `test_f074_ingesta_censo.py`
(nuevo, 119), mas `TOTAL_TABLAS` y la excepcion de `prvcer` en
`test_f066_ingesta_raw.py` y la lista de cuatro en
`test_f068_exclusion_lectura_mcp.py`. **Rastro**: `progress/current.md`.

**Ni una linea de codigo de produccion nueva**: el unico `.py` tocado es
`config/settings.py`, y solo esa constante.

## 2 · La decision de fondo, y por que NO es la que traia la propuesta

La propuesta que llego era **recarga completa nocturna de las cuatro pequeñas**
(`cet`, `pro`, `reshor`, `emphis`) y **carga por `ide` para las dos grandes**,
porque solo 3 de las 9 tienen `tiemod` y las otras seis «cargarian por `MAX(ide)`
y una fila modificada no volveria a bajar nunca». La instruccion decia mirar el
mecanismo actual antes de inventar nada. **Lo que se encontro mirando desmiente
la premisa entera:**

`Dockerfile`: `CMD ["run-all", "--full"]` («El job nocturno SIEMPRE full (el
incremental pierde UPDATEs)»). `main.py` propaga `full_refresh` a
`IngestRawStep`, y `ingest_raw_step.py:271-275` hace `truncate_table` con el
cursor a 0: **TRUNCATE y recarga entera de TODAS las tablas.** Y
`incremental_column` **no es un interruptor de modo de carga**: su unico uso es
la linea 279, que decide si `copy_rows` rellena `_source_tiemod`.

O sea: **el agujero no existe en la nocturna**. Existe solo lanzando `ingest` a
mano sin `--full`. No hay recarga completa por tabla que expresar: la nocturna
ya recarga todo, y por eso el ETL nunca necesito ese mecanismo.

**Y no es interpretacion mia**: el docstring de `tests/test_f006_raw_ingesta.py`
cuenta que F-006 se equivoco DOS VECES en esta misma afirmacion, y que por eso
nacio `tests/test_f006_fuente_que_gobierna.py`, que ancla el hecho al
`Dockerfile`. El riesgo 1 de `explore_F-074_las_nueve.md` lo repite por tercera
vez. **No se hereda en silencio: se corrige por escrito** en el YAML, en
`ARCHITECTURE.md` y en `current.md`.

**Lo implementado**: las seis sin `tiemod` quedan con `incremental_column: null`
**declarado, con la palabra VERIFICADO y la fecha de la medicion al lado**, y la
cabecera del modulo explica el mecanismo. (Si la nocturna dejara de pasar
`--full` —lo que persigue F-011— esas seis SI se congelarian, y lo denunciaria
`test_f006_r13_el_job_nocturno_hace_recarga_completa`.)

## 3 · Las nueve, medidas y anotadas

Con el recuento medido escrito en el YAML **y** en su ficha; `ide` es `int` y
unico en las nueve. Con `tiemod`: `auxdpt` (7 filas), `auxhor` (60) y `auxrestip`
(37). Sin `tiemod`: `cet` (40, excluye 7), `pro` (55.179, excluye 4), `reshor`
(8.949), `emphis` (1.633, excluye 1), `dcaprodes` (850.985) y `ctrprodes`
(424.475). Por que entra cada una: `config/tables_sigrid.yaml` y
`docs/ARCHITECTURE.md`.

**Ninguna fija `page_size`**, y es deliberado: el global ya vale 10.000, justo lo
que la exploracion proponia escribir a mano; fijarlo las dejaria pinchadas el dia
que haya que bajar el global. **Una correccion a la exploracion**: el total de
filas nuevas son **1.341.365**, no 1.341.469 (error aritmetico mio, cazado por el
test de control de la propia feature).

## 4 · Los dos arreglos y la limpieza

1. **`com`, `comlin` y `comprv` dejan de declarar `tiemod`.** **Medido y
   respondido**: ninguna tiene otra columna utilizable como corte, asi que no hay
   sustituto y quedan en `null` con el motivo escrito. El comportamiento no
   cambia —nunca cambio—: lo que cambia es que ahora se ve.
2. **`prvcer` deja de excluir `tex`.** De 13 exclusiones a 12. Su ficha lo dice y
   explica que estaba fuera por el automatismo de la lista estandar del modulo
   COMPRAS, no por una decision sobre esa tabla.
3. **`obrprv` SE QUEDA**, con el motivo en el YAML. Cuesta una peticion HTTP que
   devuelve cero filas; a cambio, `sql/maestro/02_proveedores.sql` y
   `03_proveedores_obra.sql` construyen el vinculo obra-proveedor POR OTRA VIA
   precisamente porque esta vacia, y `check-raw-recuentos` es lo unico que diria
   que ha dejado de estarlo. Un test fija esos dos SQL.

## 5 · Los datos de nomina, verificados y no supuestos

Entran en `DEFAULT_EXCLUDED_TABLES` por los **tres** sitios que exige F-068
—`config/settings.py`, `infra/sql/02_roles.sql` y `.env.example`— y se comprueba
**con las sentencias en la mano**, no por la lista:
`test_f074_r3_el_revoke_se_emite_de_verdad_para_esa_tabla` verifica que el
`REVOKE` va DESPUES del `GRANT SELECT ON ALL TABLES IN SCHEMA raw` y que el
`ALTER DEFAULT PRIVILEGES ... GRANT` de `raw` no vuelve. **Y el caso que de
verdad aplica aqui**: las dos tablas **todavia no existen** en Azure, y
`test_f074_r3_el_revoke_sobrevive_a_que_la_tabla_no_exista_aun` comprueba con
`missing_tables` que la regla del catalogo se sigue revocando —el agujero de la
pasada 1 de F-068—. La verificacion **contra la base** es MANUAL (§7).

## 6 · Fase RED — la traza, no el relato

**T1 escribio los tests antes de tocar configuracion.** Salida real:

```
$ python -m pytest tests/test_f074_ingesta_censo.py -q -p no:cacheprovider
105 failed, 13 passed in 3.01s
```

Los cuatro requisitos centrales:
```
$ python -m pytest tests/test_f074_ingesta_censo.py -k "r1_las_nueve_tablas" --tb=short
tests\test_f074_ingesta_censo.py:118: in test_f074_r1_las_nueve_tablas_estan_dadas_de_alta
    assert faltan == [], f"no se ingieren todavia: {faltan}"
E   AssertionError: no se ingieren todavia: ['auxdpt', 'auxhor', 'auxrestip',
    'cet', 'ctrprodes', 'dcaprodes', 'emphis', 'pro', 'reshor']

$ python -m pytest tests/test_f074_ingesta_censo.py \
    -k "r3_la_lista_de_exclusion or r6_ya_no_declaran or r7_prvcer_ya_no" --tb=line
tests\test_f074_ingesta_censo.py:243: AssertionError:
    assert ['raw.emp', 'raw.res'] == ['raw.emp', '... 'raw.emphis']
tests\test_f074_ingesta_censo.py:385: AssertionError: `com` sigue declarando una
    columna de corte que Sigrid no tiene; el paso la degrada en silencio y la
    mentira sobrevive
    assert 'tiemod' is None          [idem para `comlin` y `comprv`]
tests\test_f074_ingesta_censo.py:429: AssertionError:
    assert 'tex' not in ['tex', 'med', 'des', 'obs', 'ima', 'emptex', ...]
```

Y los heredados, tambien en rojo antes de implementar:
```
$ python -m pytest tests/test_f066_ingesta_raw.py tests/test_f068_exclusion_lectura_mcp.py --tb=line
FAILED test_f066_r1_la_ingesta_declara_las_tablas_que_dice_la_constante
FAILED test_f066_r7_cada_tabla_nueva_excluye_lo_que_le_toca[prvcer]
FAILED test_f068_r6_el_defecto_excluye_emp_y_res        [y tres mas]
6 failed, 339 passed, 2 warnings in 1.37s
```

Tras T2, T3 y T4: **119 passed** y los seis heredados en verde. La leccion de los
17 duplicados de F-066 sigue cubierta con nueve entradas mas:
`test_f074_r1_ninguna_tabla_esta_declarada_dos_veces` lee la **lista**, no el
`dict`.

## 7 · Verificaciones MANUAL (humano) pendientes

Con su comando exacto en `progress/current.md`, en este orden. **Todas escriben
contra Azure o dependen de que la imagen se haya desplegado y la nocturna haya
corrido**, asi que ninguna la puede ejecutar un agente.

1. Desplegar la imagen y dejar correr **una** nocturna, comprobando el tag del
   job y no solo que el repositorio este en verde.
2. `python main.py check-raw-recuentos` -> **codigo 0** (criterio 4). Antes del
   paso 1 sale con codigo 1, y es correcto: las nueve todavia no existen en `raw`
   y «no he podido mirar» no es «esta bien».
3. La consulta a `information_schema.table_privileges` -> **cero filas** para `emp`, `res`, `reshor` y `emphis` (criterio 3).
4. `check-diccionario`, y luego `publicar-diccionario` (v17): una escritura.

## 8 · Que queda fuera y que falta

* **Nada se construye encima**: ni `stg`, ni mart, ni SQL; eso es F-073.
* **El coste de ventana es una estimacion, no una medicion**: +3 a 6 min sobre
  las 3 h 45 y **+155 MB** sobre 25 GB en un disco de 64, derivado de los 0,7 s y
  0,5 s por pagina de 10.000 filas que midio la exploracion. **La cifra real solo
  la da la primera nocturna**, y el margen antes de la jornada ya era minimo.
  Criterio 9 cerrado con la estimacion escrita; confirmarlo es del humano.
* **`obrprv` conserva un comentario heredado** con `cod` y `res`: con
  0 filas no se puede comprobar. Y **el MCP no lee `raw`**: las nueve fichas no
  cambian ninguna respuesta de la IA hoy. Y los **ocho supervivientes, de
  F-025**, quedan aceptados y fichados (§9).

## 9 · Evidencias

| Evidencia | Valor |
|---|---|
| Tests ejecutados | **4.162 passed, 168 skipped**, **0 fallos** |
| Tiempo de la suite | **360,6 s** (con medicion de cobertura) |
| Cobertura de lineas cambiadas | **93,6 %** (788/842 lineas, umbral 80 %) |
| Mutantes generados / evaluados | 288 / **20** (muestreo `estandar`, semilla `20260820`) |
| Muertos / supervivientes / timeouts / sin veredicto | 12 / **8** / 0 / **0** |
| **Workers de la campaña** | **4** |
| Tiempo total de la campaña | 1.563,8 s · linea base (peor worker) 236,4 s · timeout efectivo 473 s |
| SHA de HEAD medido | `08832c42a8e6c5b53fb50acd47ed306b140d2f4d` |
| `bash harness/init.sh` | **verde, exit code 0** (2026-09-09, con este informe ya en el arbol) |

**RM2, corregida por workers**: media 78,2 s × 4 = **312,8 s por mutante**, por
encima de la linea base de 232-236 s (la campaña evalua con `-x`, y los muertos
abortan la suite en el primer fallo). Sin «CAMPAÑA NO VALIDA» ni «Sin veredicto».
**RM1**: el alcance declarado —14 ficheros, 3.527 lineas— es el del `merge-base`
con `dev` (`cd18e096`), que arrastra F-025, F-066 y F-068, **no** lo que toca
F-074: **una constante de `config/settings.py`**.

### Supervivientes: 8, ninguno en `PENDIENTE`

> **CORREGIDO TRAS EL REVIEW (pasada 1).** Este bloque decia que el octavo
> superviviente era el `is_flag` de `--full` y que F-074 lo habia cerrado. **Era
> falso**: la 539 es `--full` y la **543 es `--reconstruir-todo`**. Reproduje la
> muestra con la semilla declarada y **la 539 no esta en ella**; los 20 con su
> veredicto quedan listados en `progress/mutacion_F-074.md`. **Los ocho viven.**

Analisis completo, uno a uno, en **`progress/mutacion_F-074.md`**:

* **Los ocho son de F-025** y **ninguno se tapa aqui**: esta feature no toca
  `main.py` ni `PostgresClient`, y entran en el alcance por el `merge-base`.
  Siete —seis en `PostgresClient`, uno en `ventana_sql.py`— sobreviven por la
  misma razon estructural: son el cuerpo de metodos que abren cursor, y la suite
  **no toca red ni BBDD** por convencion, asi que esas lineas no se ejecutan ni
  una vez. Taparlos exige tests de integracion contra un Postgres real.
* **El octavo, `main.py:543`, es el `is_flag` de `--reconstruir-todo`**, la
  bandera de F-025 que fuerza a mano el rebuild de la ventana. **No es
  equivalente y esta medido**: sin `is_flag`, click infiere `BOOL` y
  `run-all --reconstruir-todo` sale con **exit 2**; `run-all --full` y `run-all` a
  secas no cambian, asi que **la nocturna no se entera**. Lo dejan vivo sus
  propios tests (T15 de `tests/test_f025_cli.py`): comprueban que la cadena salga
  en `--help` —y sale, ahora con `BOOLEAN` detras— y que el callback la cablee,
  pero **nadie invoca la opcion por el parser de click**. **Superviviente
  ACEPTADO y fichado**: fallo ruidoso, via manual, y el arreglo es endurecer T15
  en el fichero de F-025, no meter una asercion sobre la ventana en un test de
  F-074. El bloque exacto esta escrito en `progress/mutacion_F-074.md`; **la
  frontera la decide el lider.**
* **El test que F-074 escribio se queda**, y el review lo confirma: mata un
  mutante real, el de la **539**, que el muestreo nunca eligio.
