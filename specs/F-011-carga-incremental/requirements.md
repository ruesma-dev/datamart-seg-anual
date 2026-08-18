<!-- specs/F-011-carga-incremental/requirements.md -->
# F-011 · Carga incremental del datamart — Requisitos (EARS)

> Rama: `feature/F-011-carga-incremental`. Rigor: la entrada de
> `harness/features.json` **no declara `rigor`**, así que aplica `critico`
> (CHECKPOINTS.md: «si una feature no declara nivel se le aplica el más
> exigente»).

## 0 · Qué persigue esta feature y en qué orden

La descripción de la feature ordena una cosa antes que ninguna otra: **medir,
no optimizar**. Estos requisitos están agrupados en dos bloques y **el orden
es normativo**:

| Bloque | Requisitos | Naturaleza |
|---|---|---|
| **A · Medición** | R1–R8 | Se implementa **siempre**. Herramientas de solo lectura + informe. |
| **B · Ingesta incremental** | R9–R19 | Se implementa **solo si la puerta de decisión de R8 lo justifica**, contrastada contra el umbral de DA-7 (ahorro estimado ≥ 20 min **o** ingesta ≥ 40 % del tiempo total). |

**Ningún requisito del bloque B puede implementarse antes de que el humano
firme la puerta de R8.** Es literalmente lo que pide la feature, y hay una
razón dura además de la formal: los números que ya existen (§0.1) apuntan a
que el cuello de botella **no** está donde la sospecha decía.

### 0.0 · Lo que esta feature YA NO contiene (bloque C, extraído el 2026-08-18)

La versión original de esta spec tenía un tercer bloque —**C · Ventana de
negocio y build** (R20, R21, R22)— que dependía de una definición de «obra
abierta» que Negocio **no ha decidido** (DA-1). El humano, el 2026-08-18,
dejó DA-1 sin decidir y ordenó **sacar el bloque C de F-011**.

Todo el bloque C vive ahora en **`specs/F-025-ventana-negocio-build/`**:
el comando `perfil-ventana`, el bloque `ventana:` de
`config/business_rules.yaml`, `fetch_peso_ventana` y el acotado del build.

**Huecos de numeración deliberados: R20 y R21 ya no existen en F-011.** No se
renumera nada: R1–R19 y R22–R25 conservan su identificador para que la
trazabilidad requisito→test, las tareas y los mensajes de commit sigan
apuntando a lo mismo. La tabla de trazabilidad deja constancia explícita del
hueco.

| Requisito retirado de F-011 | Dónde vive ahora |
|---|---|
| R20 (`perfil-ventana` informa el peso de la ventana) | F-025 · R1, R2, R4 |
| R21 (sin predicado declarado, `perfil-ventana` falla y lo dice) | F-025 · R3 |
| R22 (F-011 **no** acota el build) | **Se queda en F-011** como requisito de alcance (ver «Requisitos transversales»); su contrapartida positiva —acotar el build de verdad— es F-025 · R6–R18 |

### 0.1 · Lo que ya se sabe antes de escribir una línea de código

Medición real de la primera carga completa del job en Azure
(`caj-datamart-seg-dev-6a95hln`, 2026-08-18, imagen `r20260818-1003`,
`Succeeded` en **2 h 45 min = 165 min**, `progress/current.md`):

| Paso | Duración | % del total | Volumen |
|---|---|---|---|
| `ingest_raw` | 33 min | **20 %** | 20,05 M filas, 31 tablas |
| `build_stg` | 1 h 51 min | **67 %** | 29,59 M filas, 60 tramos |
| `build_mart` | 21 min | **13 %** | 5,29 M filas |

Consecuencia aritmética, no opinión: **una ingesta instantánea deja la carga
en 132 min (−20 %)**. La sospecha que abre la feature —«el cuello de botella
puede estar en la extracción»— **no se sostiene contra este dato agregado**, y
por eso R1–R3 la desmenuzan antes de decidir nada: el agregado puede esconder
que dos o tres tablas se lleven casi los 33 min, o que la ingesta sea el
riesgo (donde murió el intento de abril) aunque no sea el coste.

### 0.2 · Corrección del hallazgo heredado de F-009

La descripción de F-011 afirma: «`fecalt` aparece en 16 tablas, `fecmod` en 3
y `sello` en 2». **Verificado el 2026-08-18 contra
`C:\Users\pgris\PycharmProjects\azure-apps\sigrid_tablas.md`** (22 KLoC, la
única copia del diccionario). Los números no cuadran y, sobre todo, **falta el
dato que importa**:

| Columna | Filas del diccionario con ese nombre exacto | Lo que decía F-009 |
|---|---|---|
| `fecalt` | **18** (más `fecalta` y `fecaltbaj`, que son otros nombres) | 16 |
| `fecmod` | **6** | 3 |
| `sello` | **2** (`licmod`, `wsses`) | 2 ✔ |
| **`tiemod`** | **232 filas, ~190 tablas distintas** | **no se menciona** |

`tiemod` está descrito en el diccionario como «Tiempo modificación», tipo
«Real tiempo», y **está en todas las tablas de negocio que ingerimos**.
Además, `config/tables_sigrid.yaml` **ya lo declara** como
`incremental_column` en 17 de las 31 tablas, y `ingest_raw_step` **ya lo
copia** a la columna `_source_tiemod` de cada tabla de `raw` en cada carga.

Por tanto la premisa «Sigrid no tiene marca de última modificación» hay que
reformularla con precisión, y así es como la tratan estos requisitos:

> **Existe una columna candidata (`tiemod`) en casi todas las tablas, y sus
> valores ya están dentro del datamart. Lo que NO está acreditado es que
> Sigrid la mantenga: que avance en toda fila modificada y no cambie en las
> que no se tocan. Eso es medible SIN volver a leer Sigrid (R6, R7).**

Mandar el `--full` de siempre porque «no hay watermark» sin haber mirado los
`_source_tiemod` que ya tenemos guardados sería exactamente el error que esta
feature quiere evitar.

Comando exacto para reproducir el recuento (el reviewer debe poder repetirlo):

```bash
cd /c/Users/pgris/PycharmProjects/azure-apps
grep -c '^| fecalt  *|' sigrid_tablas.md   # 18
grep -c '^| fecmod  *|' sigrid_tablas.md   # 6
grep -c '^| sello  *|'  sigrid_tablas.md   # 2
grep -c '^| tiemod  *|' sigrid_tablas.md   # 232
```

### 0.3 · Lo que esta feature NO puede romper

F-024 (cerrada el 2026-08-18) construyó la coherencia del datamart sobre una
invariante: **todas las tablas declaradas en `config/tables_sigrid.yaml`
provienen del MISMO `batch_id` y todas terminaron en `SUCCESS`**
(`etl_sigrid/domain/coherencia.py::evaluar_coherencia_raw`). Una carga
incremental ingenua —que solo toque las tablas que cambiaron— deja `raw` con
tablas de batches distintos y **la puerta declararía incoherente un `raw` que
en realidad está perfecto**. R9 y R13–R15 existen para eso.

---

## Bloque A · Medición (se implementa siempre)

**R1.** CUANDO el usuario ejecuta `python main.py perfil-carga`, el sistema
debe leer **solo** `_meta.etl_runs` y mostrar el desglose de la última carga
completa: una línea por paso de pipeline y una línea por **tabla** de la
ingesta (`ingest_raw.<tabla>`), con duración en segundos, filas procesadas,
filas por segundo y porcentaje del tiempo total de la carga.

**R2.** CUANDO `perfil-carga` termina, el sistema debe imprimir el **techo de
mejora por paso**: para cada paso, la duración total que tendría la carga si
ese paso costase cero, y el ahorro en minutos y en porcentaje. Ese número, y
no una intuición, es lo que decide si el bloque B se implementa.

**R3.** CUANDO `perfil-carga` desglosa la ingesta, el sistema debe ordenar las
tablas por duración descendente y marcar cuántas tablas acumulan el 80 % del
tiempo de ingesta. (Si son dos, atacar las 31 es trabajo tirado.)

**R4.** CUANDO el usuario ejecuta `python main.py bench-sigrid --tabla <t>
--paginas 1000,5000,10000,20000`, el sistema debe medir contra sigrid-api, **en
solo lectura y sin escribir nada en Postgres**, el tiempo de respuesta y las
filas por segundo de cada tamaño de página, y emitir el resumen por consola y a
un CSV opcional (`--out`).

> El 20.000 no es decorativo: el cap real de `sigrid-api` son **20.000 filas
> por petición** (DA-6, confirmado por el humano el 2026-08-18), y este ETL
> trabaja hoy a 10.000. Medir el doble es lo único que dice si subir el
> `page_size` compra algo o si el coste está en el SQL Server y no en el
> transporte.

**R5.** SI sigrid-api rechaza un tamaño de página por exceder su
`MAX_ALLOWED_ROWS`, ENTONCES `bench-sigrid` debe registrar el cap real que la
API devuelve en el cuerpo del 400, continuar con los tamaños admitidos y
**no** abortar la medición.

**R5-bis.** CUANDO `bench-sigrid` mide, el sistema debe registrar además el
**tiempo de respuesta máximo observado** por tamaño de página y compararlo con
el `timeout_s` configurado, para acreditar cuál es el corte real del
balanceador (documentado 120 s, en uso 230 s: la divergencia sigue **sin
acreditar** tras DA-6 y es lo que queda por medir aquí).

> Identificador con sufijo, no un `R26` al final: este requisito nace de una
> decisión cerrada sobre R5 y tiene que leerse pegado a él. No hay
> renumeración en esta spec (§0.0).

**R6.** El sistema debe ofrecer `python main.py diagnostico-tiemod`, de solo
lectura sobre el datamart, que para cada tabla de `raw` con columna
`_source_tiemod` informe: filas totales, filas con `_source_tiemod` nulo,
mínimo, máximo, número de valores distintos y porcentaje de nulos.

**R7.** CUANDO `diagnostico-tiemod` se ejecuta con `--comparar-con <fichero>`,
donde el fichero es la salida de una ejecución anterior, el sistema debe
mostrar, por tabla, cuántas filas cambiaron de `_source_tiemod` entre las dos
cargas y **emitir un veredicto explícito por tabla**: `SIRVE` (hubo filas cuyo
`_source_tiemod` avanzó y el máximo global creció), `NO SIRVE` (ninguna fila
cambió pese a que la tabla sí cambió de contenido, o la columna es toda nula)
o `SIN EVIDENCIA` (no hay dos cargas comparables).

**R8.** El sistema debe dejar el resultado de R1–R7 escrito en
`progress/medicion_F-011.md` con la fecha, el `batch_id` de las cargas
medidas y **una recomendación firmada de SÍ o NO implementar el bloque B**,
contrastada **explícitamente contra el umbral cerrado en DA-7**: el bloque B
se implementa solo si el ahorro estimado es **≥ 20 minutos** o si la ingesta
pasa a ser **≥ 40 % del tiempo total** de la carga. El informe debe escribir
los dos números medidos al lado de los dos umbrales, no una valoración
cualitativa. MIENTRAS ese informe no exista y el humano no lo apruebe, ningún
requisito del bloque B puede darse por iniciado.

> Verificación de R8: es una **puerta de proceso**, no de código. El reviewer
> comprueba que el fichero existe, que sus números salen de `_meta.etl_runs` y
> no de una estimación, y que el humano lo firmó en `progress/current.md`.

---

## Bloque B · Ingesta incremental (condicionado a la puerta de R8)

**R9.** DONDE la ingesta se ejecute en modo incremental, el sistema debe
escribir en `_meta.etl_runs` una fila `ingest_raw.<tabla>` para **TODAS** las
tablas declaradas en `config/tables_sigrid.yaml`, incluso para aquellas de las
que no traiga ninguna fila nueva, con el `batch_id` de la ejecución en curso.

> Este es el requisito que salva la puerta de F-024 sin tocarla: si cada
> ejecución deja constancia de haber **revisado** todas las tablas, todas
> comparten batch y `evaluar_coherencia_raw` sigue diciendo OK sin cambiar ni
> una línea de `domain/coherencia.py`.

**R10.** CUANDO la ingesta termina una tabla, el sistema debe guardar en el
campo `metadata` de su fila de `_meta.etl_runs`: `modo` (`full` o
`incremental`), `cursor_desde`, `cursor_hasta`, `filas_nuevas` y
`filas_en_tabla` (el `COUNT(*)` de `raw.<tabla>` al terminar).

> `rows_processed` sigue significando lo mismo que hoy —filas escritas en esa
> ejecución—, así que en incremental **deja de coincidir** con el tamaño de la
> tabla. `filas_en_tabla` existe para que nadie confunda las dos cosas.

**R11.** El sistema debe mantener la tabla `_meta.ingesta_watermark`, con una
fila por tabla declarada y, como mínimo: `tabla`, `modo_ultimo`,
`cursor_valor`, `batch_id_ultima_full`, `fecha_ultima_full`,
`batch_id_ultimo`, `filas_en_tabla`, `actualizado_en`. Su creación debe ser
idempotente y ejecutarse en el bootstrap, como la de `_meta.etl_runs`.

**R12.** SI hoy es el día de la semana configurado en
`INGESTA_FULL_DIA_SEMANA` (**domingo** por defecto, DA-2) y todavía no se ha
hecho una recarga completa hoy, **O** han pasado `INGESTA_FULL_CADA_DIAS` días
o más desde la última recarga completa, ENTONCES `run-all` debe hacer recarga
completa **de todas las tablas** esa noche, no solo de la que va atrasada.

> Las dos condiciones van en **OR** y no significan lo mismo. El día de la
> semana es la **regla**: la recarga completa se hace los domingos, que es lo
> que el humano decidió el 2026-08-18 y lo que permite coordinar la ventana
> con `albaranes` y `partes` en el mismo servidor. Los días transcurridos son
> la **red de seguridad**: si el domingo el job no corrió o murió, al séptimo
> día se recarga completa aunque sea martes, en vez de esperar otra semana.
> Con solo la segunda condición la recarga completa iría derivando de día
> (domingo, lunes, martes…) hasta caer en horario de trabajo.

**R12-bis.** CUANDO el sistema decide el modo de carga, debe hacerlo con esta
regla exacta, sin ninguna otra fuente de verdad:

```
FULL  si  forzar_full (--full explícito)
      o   modo_configurado == "full"            (apagado por defecto, R18)
      o   no hay ninguna recarga completa previa registrada
      o   (hoy.weekday() == INGESTA_FULL_DIA_SEMANA  Y  fecha(ultima_full) < fecha(hoy))
      o   (hoy - ultima_full).days >= INGESTA_FULL_CADA_DIAS
INCREMENTAL  en cualquier otro caso
```

`weekday()` es el de la librería estándar (0 = lunes … **6 = domingo**), y la
comparación del día ya hecho es **por fecha, no por marca de tiempo**: dos
ejecuciones el mismo domingo hacen **una** recarga completa, no dos. La marca
de tiempo es la misma que el ETL ya usa para `started_at` (UTC); a las 02:00
de la ventana nocturna la fecha UTC y la peninsular coinciden, tanto en
horario de invierno como de verano, así que no se introduce ninguna
conversión de zona horaria.

**R13.** MIENTRAS exista una carga incremental, la puerta de coherencia de
`raw` debe seguir exigiendo exactamente lo mismo que hoy: todas las tablas
declaradas, mismo `batch_id`, todas en `SUCCESS`. El comportamiento de
`etl_sigrid/domain/coherencia.py::evaluar_coherencia_raw` **no cambia**.

**R14.** SI una ingesta incremental deja alguna tabla en un estado distinto de
`SUCCESS`, ENTONCES `build_stg` debe negarse igual que hoy, con el mismo
mensaje y las mismas dos salidas (`ingest --full` o `stage --sin-puerta`).

**R15.** DONDE una tabla declarada no tenga columna de cursor utilizable
—`incremental_column` a `null` en el YAML, o la columna no exista en el
esquema que devuelve Sigrid—, el sistema debe **recargarla completa dentro del
mismo batch** y registrarlo con `modo: "full"` en su metadata.

**R16.** SI se ejecuta `python main.py ingest` **sin** `--full` y sin un modo
incremental validado y configurado, ENTONCES el sistema debe **negarse** y
explicar que el cursor por `ide` solo ve altas y pierde modificaciones y
bajas, ofreciendo las dos salidas: `--full` o `--solo-altas` (que asume
explícitamente esa pérdida).

> Hoy `python main.py ingest` a secas hace justo eso en silencio
> (`ingest_raw_step.py`, rama `full_refresh=False` → cursor `MAX(ide)`), y
> `docs/ARCHITECTURE.md` avisa de que por eso la nocturna va siempre `--full`.
> Un aviso en un documento no impide teclear el comando.

**R17.** CUANDO la ingesta corre en modo incremental, el sistema debe
comparar, por tabla, el `COUNT(*)` de `raw.<tabla>` con el `COUNT(*)` de la
tabla en Sigrid (una consulta de lectura por tabla), y SI la diferencia supera
`INGESTA_DERIVA_MAX_FILAS`, ENTONCES debe recargar esa tabla completa en la
misma ejecución y dejarlo escrito en su metadata (`motivo_full: "deriva"`).

> Es la red contra las **bajas**: ni el cursor por `ide` ni el watermark por
> `tiemod` ven un `DELETE` en Sigrid. Un recuento por tabla sí.

**R18.** MIENTRAS `INGESTA_MODO` no se fije explícitamente, el sistema debe
comportarse **exactamente como hoy**: `run-all --full` recarga todo y
`run-all` sin `--full` mantiene su comportamiento actual. La feature entra
apagada por defecto.

**R19.** SI se configura `INGESTA_MODO=tiemod` sin que `_meta` contenga el
registro de validación de R7 para todas las tablas afectadas, ENTONCES el ETL
debe abortar la ingesta antes de leer una sola fila, indicando qué tablas
faltan por validar y con qué comando se validan.

---

## ~~Bloque C · Ventana de negocio y build~~ — EXTRAÍDO A F-025 (2026-08-18)

R20 y R21 ya no forman parte de esta feature: viven en
`specs/F-025-ventana-negocio-build/`. Ver §0.0 para el mapeo completo y el
motivo (DA-1 sigue sin decidir). **R22 se queda aquí**, reformulado como
requisito de alcance en la sección siguiente: es la barrera que impide que
F-011 se meta en el terreno de F-025.

---

## Requisitos transversales (aplican a todo lo anterior)

**R22.** El sistema **no** debe acotar el build de `stg` ni el de `mart` a
ninguna ventana de negocio dentro de F-011, ni añadir el bloque `ventana:` a
`config/business_rules.yaml`, ni el comando `perfil-ventana`, ni
`fetch_peso_ventana`. Todo eso es **F-025**, que cambia **qué datos ve Power
BI** y por tanto necesita su propia decisión de Negocio (DA-1) y su propia
prueba de equivalencia, igual que hizo F-019.

**R23.** El sistema **no** debe ejecutar contra Sigrid ninguna sentencia que
no sea de lectura. Todo SQL que los comandos nuevos envíen a `/api/sql/read`
debe pasar por un validador que rechace cualquier sentencia que no empiece por
`SELECT`.

**R24.** SI un comando nuevo de esta feature necesita credenciales, ENTONCES
debe obtenerlas de `config/settings.py` como el resto: ni un secreto en la
spec, ni en el código, ni en los tests, ni en `progress/`.

**R25.** Los comandos nuevos de solo lectura (`perfil-carga`,
`diagnostico-tiemod`, `bench-sigrid`) **no** deben generar
`batch_id` ni escribir filas en `_meta.etl_runs`, igual que hoy hacen
`check-coherencia`, `check-frescura` y `timings`.

---

## Trazabilidad requisito → test

Todos los tests viven en `tests/` y **ninguno abre red ni BBDD**: los clientes
de Sigrid y de Postgres van mockeados y los cálculos son funciones puras sobre
fixtures. Lo que no se puede probar así está marcado `MANUAL (humano)` y su
comando exacto está en `tasks.md`.

| Req | Test (fichero::nombre) | Sin red/BBDD |
|---|---|---|
| R1 | `test_f011_perfil.py::test_f011_r1_desglosa_pasos_y_tablas` | sí |
| R2 | `test_f011_perfil.py::test_f011_r2_techo_de_mejora_por_paso` | sí |
| R3 | `test_f011_perfil.py::test_f011_r3_tablas_que_acumulan_el_80_pct` | sí |
| R4 | `test_f011_bench.py::test_f011_r4_bench_no_escribe_en_postgres` | sí (cliente HTTP mockeado) |
| R5 | `test_f011_bench.py::test_f011_r5_cap_rechazado_no_aborta_el_bench` | sí |
| R5-bis | `test_f011_bench.py::test_f011_r5bis_registra_latencia_maxima_por_pagina` | sí |
| R6 | `test_f011_tiemod.py::test_f011_r6_diagnostico_por_tabla` | sí |
| R7 | `test_f011_tiemod.py::test_f011_r7_veredicto_sirve_no_sirve_sin_evidencia` | sí |
| R8 | **MANUAL (humano)** · el reviewer comprueba `progress/medicion_F-011.md` | n/a |
| R9 | `test_f011_ingesta.py::test_f011_r9_fila_por_cada_tabla_declarada` | sí |
| R10 | `test_f011_ingesta.py::test_f011_r10_metadata_de_la_fila_de_tabla` | sí |
| R11 | `test_f011_watermark.py::test_f011_r11_ddl_idempotente_y_en_bootstrap` | sí (lee el .sql) |
| R12 | `test_f011_watermark.py::test_f011_r12_full_semanal_es_de_todas_las_tablas` | sí (función pura) |
| R12-bis | `test_f011_watermark.py::test_f011_r12bis_el_domingo_manda_y_los_dias_son_la_red` | sí (función pura; casos: domingo con full de ayer → FULL, domingo con full de hoy → INCREMENTAL, martes con full de hace 6 días → INCREMENTAL, martes con full de hace 7 → FULL, sin full previa → FULL) |
| R13 | `test_f011_coherencia.py::test_f011_r13_la_puerta_de_raw_no_cambia` | sí |
| R14 | `test_f011_coherencia.py::test_f011_r14_tabla_no_exitosa_sigue_frenando_stg` | sí |
| R15 | `test_f011_ingesta.py::test_f011_r15_tabla_sin_cursor_va_completa` | sí |
| R16 | `test_f011_cli.py::test_f011_r16_ingest_sin_full_se_niega` | sí |
| R17 | `test_f011_ingesta.py::test_f011_r17_deriva_de_recuento_fuerza_full` | sí |
| R18 | `test_f011_cli.py::test_f011_r18_apagado_por_defecto_no_cambia_nada` | sí |
| R19 | `test_f011_cli.py::test_f011_r19_modo_tiemod_sin_validacion_aborta` | sí |
| ~~R20~~ | **HUECO DELIBERADO** · extraído a F-025 (§0.0). No existe `tests/test_f011_ventana.py` | n/a |
| ~~R21~~ | **HUECO DELIBERADO** · extraído a F-025 (§0.0) | n/a |
| R22 | `test_f011_alcance.py::test_f011_r22_el_sql_de_stg_y_mart_no_se_toca` + `::test_f011_r22_sin_bloque_ventana_ni_perfil_ventana` | sí (diff de ficheros + barrido del árbol) |
| R23 | `test_f011_bench.py::test_f011_r23_solo_select_contra_sigrid` | sí |
| R24 | `test_f011_alcance.py::test_f011_r24_sin_secretos_en_lo_nuevo` | sí |
| R25 | `test_f011_cli.py::test_f011_r25_comandos_de_lectura_no_escriben_en_meta` | sí |

**Verificaciones MANUAL (humano)**, con su comando exacto en `tasks.md`:
R8 (informe de medición firmado), la ejecución real de `bench-sigrid` contra
sigrid-api, la de `diagnostico-tiemod` sobre dos cargas completas
consecutivas, y —si el bloque B se implementa— la primera carga incremental
real en Azure contrastada con una `--full` inmediatamente posterior.

---

## Decisiones cerradas (2026-08-18, por el humano)

Esta sección sustituye a la de «Decisiones abiertas» de la primera versión de
la spec. El humano respondió a las siete el 2026-08-18: **seis quedan
cerradas** y su efecto en el diseño está escrito aquí; **DA-1 no se cierra y
sale de la feature**.

### DA-1 · ¿Qué es una «obra abierta»? — **SIN DECIDIR · SALE DE F-011**

El humano **no** decide todavía qué es una obra abierta. En consecuencia, todo
lo que dependía de esa definición **se extrae de F-011** y pasa a
`specs/F-025-ventana-negocio-build/`, donde DA-1 es la **primera decisión
abierta** y sigue sin cerrar.

**Efecto concreto en esta spec:**

- R20 y R21 desaparecen (§0.0). Se dejan como **huecos de numeración**; no se
  renumera nada.
- **No** se añade el bloque `ventana:` a `config/business_rules.yaml`.
- **No** se implementa el comando `perfil-ventana`.
- **No** se implementa `fetch_peso_ventana` en `postgres_client.py`.
- R22 se queda, convertido en requisito de alcance: F-011 **no** toca el SQL
  de `stg` ni de `mart` ni crea nada de la ventana, y hay test que lo fija.
- La tarea T20 del bloque C desaparece de `tasks.md` (hueco deliberado).

### DA-2 · Cadencia de la recarga completa — **SEMANAL, LOS DOMINGOS**

**Efecto concreto en el diseño**, y aquí está la parte que no puede quedar
ambigua: **`INGESTA_FULL_CADA_DIAS=7` por sí solo NO implementa «los
domingos»**. Contar días desde la última recarga completa hace que el día vaya
derivando —si un domingo el job falla y la siguiente completa cae el lunes, la
próxima cae el lunes, y así hasta meterse en horario de trabajo—. La decisión
de modo, por tanto, **mira el día de la semana**, y los días transcurridos
quedan como red de seguridad:

- Ajuste nuevo **`INGESTA_FULL_DIA_SEMANA: int = 6`** (0 = lunes … 6 = domingo,
  el convenio de `datetime.weekday()`). Es la **regla**.
- Ajuste **`INGESTA_FULL_CADA_DIAS: int = 7`**. Es la **red de seguridad**: si
  el domingo no hubo carga (job caído, ventana perdida), al séptimo día se
  recarga completa aunque sea martes.
- Las dos condiciones se combinan en **OR**, con la regla exacta escrita en
  **R12-bis**, y viven en `decidir_modo_de_carga(...)`, dominio puro, con un
  test por caso.
- La comparación «¿ya se hizo la completa hoy?» es **por fecha**, no por marca
  de tiempo: dos ejecuciones el mismo domingo hacen **una** recarga completa.
- La marca de tiempo es la que el ETL ya usa (UTC). A las 02:00 de la ventana
  nocturna la fecha UTC coincide con la peninsular en invierno y en verano, así
  que **no se introduce ninguna conversión de zona horaria** (y se documenta
  que si la ventana se moviera a antes de la medianoche, esto habría que
  revisarlo).

### DA-3 · Perder las bajas de Sigrid entre recargas completas — **ACEPTADO**

Se acepta la recomendación: se asume que un `DELETE` en Sigrid no lo ve ningún
cursor entre recargas completas, con dos redes.

**Efecto concreto:** R17 (guardia de deriva por recuento de filas) se mantiene
tal cual y es **obligatoria** en el bloque B, no opcional;
`INGESTA_DERIVA_MAX_FILAS` entra con default `0` (cualquier divergencia fuerza
la recarga completa de esa tabla). La recarga completa semanal de DA-2 es la
segunda red. Queda **descartada** la comparación del conjunto completo de `ide`
por tabla.

### DA-4 · Si `tiemod` resulta NO fiable — **ACEPTADO (a) + (b)**

Se acepta la recomendación: si el veredicto de R7 es `NO SIRVE`, (a) se
renuncia a la ingesta incremental por watermark y el esfuerzo se lleva al
build —que ahora es **F-025**— y (b) se puede acotar la extracción con el campo
`where` que `config/tables_sigrid.yaml` **ya soporta** por tabla.

**Efecto concreto:** la opción (c) —watermark propio a base de sumas de control
sobre 20 M de filas— queda **descartada y no se diseña**; R19 sigue vigente
(sin veredicto registrado, el modo `tiemod` aborta antes de leer una fila); y
si R7 dice `NO SIRVE`, el bloque B se cierra sin implementar y F-011 entrega
solo el bloque A.

### DA-5 · Feature propia para acotar el build — **ACEPTADO: es F-025**

Se acepta la recomendación. **Efecto concreto:**
`specs/F-025-ventana-negocio-build/` existe y recoge todo el bloque C. Y con la
prioridad que el humano ya fijó: **F-025 va por encima del bloque B de F-011**
si los números de la medición (R8) lo confirman, porque el build es el **67 %**
del tiempo y la ingesta el 20 %. F-025 cambia qué ve Power BI, así que exige
prueba de equivalencia como hizo F-019.

### DA-6 · El cap real de `sigrid-api` son 20.000 filas, no 1.000 — **DATO DEL HUMANO**

**Confirmado por el humano el 2026-08-18: el cap real de `sigrid-api` es de
20.000 filas por petición.** `azure-apps/sigrid_api.md` documenta 1.000
(`MAX_ALLOWED_ROWS`): **el documento está mal**. Este ETL usa `page_size =
10000`, o sea que **trabaja por debajo del límite real** y le sobra margen.

**Efecto concreto en el diseño:**

1. **Cae la premisa de la feature.** «sigrid-api limita a 1.000 filas por
   petición» era una de las dos patas de la sospecha original; queda refutada.
   La otra pata —el corte del balanceador— **sigue sin acreditar**: documentado
   120 s, en uso 230 s. Eso es lo que mide **R5-bis**.
2. `bench-sigrid` incluye el tamaño **20.000** en su barrido (R4) para saber si
   subir el `page_size` compra algo o si el coste está en el SQL Server.
3. **Este proyecto NO edita `azure-apps/sigrid_api.md`.** El dueño de ese
   documento es el proyecto `sigrid-api` (`CLAUDE.md` § ecosistema). El dato se
   registra aquí y **se avisa a su dueño**: tarea **T8-bis** de `tasks.md`,
   MANUAL del humano.

### DA-7 · Umbral que justifica implementar el bloque B — **ACEPTADO**

Se acepta la recomendación. **Efecto concreto:** el bloque B se implementa
**solo si** `perfil-carga` demuestra un ahorro estimado **≥ 20 minutos** **o**
la ingesta pasa a ser **≥ 40 % del tiempo total**. El umbral está escrito en
R8, en la tabla de bloques de §0 y en la verificación de T8/T9: el informe de
medición tiene que poner los dos números medidos al lado de los dos umbrales.
Por debajo de eso, el bloque B añade una máquina de estados nueva a un ETL hoy
reproducible y aburrido a cambio de calderilla, y F-011 se cierra entregando
solo el bloque A.

---

## Decisiones que siguen abiertas en F-011

**Ninguna.** DA-1 salió a F-025, donde sigue abierta. Lo que queda por resolver
en F-011 no son decisiones sino **mediciones**: el veredicto de `tiemod` (R7),
el reparto del tiempo de ingesta por tabla (R3) y el corte real del balanceador
(R5-bis). Las tres tienen su tarea MANUAL en `tasks.md` y su puerta en R8.
