<!-- specs/F-011-carga-incremental/requirements.md -->
# F-011 · Carga incremental del datamart — Requisitos (EARS)

> Rama: `feature/F-011-carga-incremental`. Rigor: la entrada de
> `harness/features.json` **no declara `rigor`**, así que aplica `critico`
> (CHECKPOINTS.md: «si una feature no declara nivel se le aplica el más
> exigente»).

## 0 · Qué persigue esta feature y en qué orden

La descripción de la feature ordena una cosa antes que ninguna otra: **medir,
no optimizar**. Estos requisitos están agrupados en tres bloques y **el orden
es normativo**:

| Bloque | Requisitos | Naturaleza |
|---|---|---|
| **A · Medición** | R1–R8 | Se implementa **siempre**. Herramientas de solo lectura + informe. |
| **B · Ingesta incremental** | R9–R19 | Se implementa **solo si la puerta de decisión de R8 lo justifica** y con las decisiones abiertas cerradas. |
| **C · Ventana de negocio y build** | R20–R22 | En F-011 **solo se mide y se acota el alcance**. La implementación va a feature propia (ver DA-5). |

**Ningún requisito del bloque B o C puede implementarse antes de que el humano
firme la puerta de R8.** Es literalmente lo que pide la feature, y hay una
razón dura además de la formal: los números que ya existen (§0.1) apuntan a
que el cuello de botella **no** está donde la sospecha decía.

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
--paginas 1000,5000,10000`, el sistema debe medir contra sigrid-api, **en solo
lectura y sin escribir nada en Postgres**, el tiempo de respuesta y las filas
por segundo de cada tamaño de página, y emitir el resumen por consola y a un
CSV opcional (`--out`).

**R5.** SI sigrid-api rechaza un tamaño de página por exceder su
`MAX_ALLOWED_ROWS`, ENTONCES `bench-sigrid` debe registrar el cap real que la
API devuelve en el cuerpo del 400, continuar con los tamaños admitidos y
**no** abortar la medición.

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
medidas y **una recomendación firmada de SÍ o NO implementar el bloque B**.
MIENTRAS ese informe no exista y el humano no lo apruebe, ningún requisito del
bloque B puede darse por iniciado.

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

**R12.** SI han pasado más de `INGESTA_FULL_CADA_DIAS` días desde la última
recarga completa, ENTONCES `run-all` debe hacer recarga completa **de todas
las tablas** esa noche, no solo de la que va atrasada.

> Recargar solo la atrasada dejaría `raw` con una tabla de hoy y treinta de
> antes de ayer: coherente para la puerta (mismo batch, porque R9 escribe
> fila para todas) pero **incoherente en el dato**. La recarga completa es
> todo o nada.

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

## Bloque C · Ventana de negocio y build (solo medición en F-011)

**R20.** CUANDO el usuario ejecuta `python main.py perfil-ventana`, el sistema
debe informar, en solo lectura sobre el datamart, qué porcentaje de las filas
de `stg.plan_mensual` y de `mart.fact_seguimiento_mensual` pertenecen a obras
que cumplen el predicado de «obra abierta» declarado en
`config/business_rules.yaml`, y qué porcentaje pertenecen al ejercicio en
curso.

**R21.** SI `config/business_rules.yaml` no declara el predicado de «obra
abierta», ENTONCES `perfil-ventana` debe fallar con un mensaje que diga que es
una **decisión de Negocio pendiente** (DA-1) y no inventar un criterio por
defecto.

**R22.** El sistema **no** debe acotar el build de `stg` ni el de `mart` a la
ventana de negocio dentro de F-011. La decisión y la implementación van a
feature propia (DA-5), porque cambian **qué datos ve Power BI**, no solo
cuánto tarda en calcularlos.

---

## Requisitos transversales (aplican a todo lo anterior)

**R23.** El sistema **no** debe ejecutar contra Sigrid ninguna sentencia que
no sea de lectura. Todo SQL que los comandos nuevos envíen a `/api/sql/read`
debe pasar por un validador que rechace cualquier sentencia que no empiece por
`SELECT`.

**R24.** SI un comando nuevo de esta feature necesita credenciales, ENTONCES
debe obtenerlas de `config/settings.py` como el resto: ni un secreto en la
spec, ni en el código, ni en los tests, ni en `progress/`.

**R25.** Los comandos nuevos de solo lectura (`perfil-carga`,
`diagnostico-tiemod`, `perfil-ventana`, `bench-sigrid`) **no** deben generar
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
| R6 | `test_f011_tiemod.py::test_f011_r6_diagnostico_por_tabla` | sí |
| R7 | `test_f011_tiemod.py::test_f011_r7_veredicto_sirve_no_sirve_sin_evidencia` | sí |
| R8 | **MANUAL (humano)** · el reviewer comprueba `progress/medicion_F-011.md` | n/a |
| R9 | `test_f011_ingesta.py::test_f011_r9_fila_por_cada_tabla_declarada` | sí |
| R10 | `test_f011_ingesta.py::test_f011_r10_metadata_de_la_fila_de_tabla` | sí |
| R11 | `test_f011_watermark.py::test_f011_r11_ddl_idempotente_y_en_bootstrap` | sí (lee el .sql) |
| R12 | `test_f011_watermark.py::test_f011_r12_full_semanal_es_de_todas_las_tablas` | sí (función pura) |
| R13 | `test_f011_coherencia.py::test_f011_r13_la_puerta_de_raw_no_cambia` | sí |
| R14 | `test_f011_coherencia.py::test_f011_r14_tabla_no_exitosa_sigue_frenando_stg` | sí |
| R15 | `test_f011_ingesta.py::test_f011_r15_tabla_sin_cursor_va_completa` | sí |
| R16 | `test_f011_cli.py::test_f011_r16_ingest_sin_full_se_niega` | sí |
| R17 | `test_f011_ingesta.py::test_f011_r17_deriva_de_recuento_fuerza_full` | sí |
| R18 | `test_f011_cli.py::test_f011_r18_apagado_por_defecto_no_cambia_nada` | sí |
| R19 | `test_f011_cli.py::test_f011_r19_modo_tiemod_sin_validacion_aborta` | sí |
| R20 | `test_f011_ventana.py::test_f011_r20_porcentajes_de_la_ventana` | sí |
| R21 | `test_f011_ventana.py::test_f011_r21_sin_predicado_falla_y_lo_dice` | sí |
| R22 | `test_f011_alcance.py::test_f011_r22_el_sql_de_stg_y_mart_no_se_toca` | sí (diff de ficheros) |
| R23 | `test_f011_bench.py::test_f011_r23_solo_select_contra_sigrid` | sí |
| R24 | `test_f011_alcance.py::test_f011_r24_sin_secretos_en_lo_nuevo` | sí |
| R25 | `test_f011_cli.py::test_f011_r25_comandos_de_lectura_no_escriben_en_meta` | sí |

**Verificaciones MANUAL (humano)**, con su comando exacto en `tasks.md`:
R8 (informe de medición firmado), la ejecución real de `bench-sigrid` contra
sigrid-api, la de `diagnostico-tiemod` sobre dos cargas completas
consecutivas, y —si el bloque B se implementa— la primera carga incremental
real en Azure contrastada con una `--full` inmediatamente posterior.

---

## Decisiones abiertas (NO las cierra el spec-author)

**DA-1 · ¿Qué es una «obra abierta»?**
Opciones: (a) obra cuyo contrato en `raw.obrctr` no tiene `fecreafin`
informada; (b) obra con movimiento (albarán, factura o parte) en los últimos
N meses; (c) una marca explícita de Sigrid que Negocio identifique.
**Recomendación**: (a) como definición primaria y (b) con N=12 como red, ambas
declaradas como predicado SQL en `config/business_rules.yaml` para poder
cambiarlas sin tocar código. **Requiere confirmación de Negocio**: de esta
definición depende qué obras dejarían de refrescarse a diario.

**DA-2 · Cadencia de la recarga completa.**
Opciones: (a) semanal, en el hueco de menor uso; (b) cada 3 días; (c) diaria
(es decir, no hacer incremental). **Recomendación**: (a) semanal, sábado o
domingo por la noche, con `INGESTA_FULL_CADA_DIAS=7`, **solo si** la puerta de
R8 aprueba el bloque B. El día concreto lo elige el humano: la ventana la
comparte con `albaranes` y `partes` en el mismo servidor.

**DA-3 · ¿Se acepta perder las bajas de Sigrid entre recargas completas?**
Un `DELETE` en Sigrid no lo ve ningún cursor. **Recomendación**: aceptarlo con
la guardia de recuento de R17, que fuerza la recarga completa de la tabla en
cuanto los recuentos divergen. Alternativa cara: comparar el conjunto completo
de `ide` por tabla en cada carga (31 tablas × millones de ids a 10.000 filas
por petición: no compensa).

**DA-4 · Si `tiemod` resulta NO fiable (veredicto de R7), ¿qué se hace?**
Opciones: (a) renunciar a la ingesta incremental y llevar el esfuerzo al build
(bloque C); (b) filtrar la extracción por ventana de negocio usando el campo
`where` que `config/tables_sigrid.yaml` **ya soporta** por tabla; (c) construir
un watermark propio en `_meta` a base de recuentos y sumas de control por
tabla y obra. **Recomendación**: (a) + (b). La (c) es un sistema de detección
de cambios casero sobre 20 M de filas: mucho código nuevo para ahorrar 33 min.

**DA-5 · ¿Se abre una feature propia para acotar el build (el 67 % del
tiempo)?** **Recomendación**: sí, y con prioridad **por encima** del bloque B
de esta feature si R8 confirma los números de §0.1. Cambia qué ve Power BI, así
que necesita su propia spec, su decisión de Negocio (DA-1) y su verificación
de equivalencia, igual que hizo F-019.

**DA-6 · La documentación de `sigrid-api` no cuadra con la instancia
desplegada.** `azure-apps/sigrid_api.md` documenta `MAX_ALLOWED_ROWS = 1000` y
`MAX_QUERY_TIMEOUT_SECONDS = 120`; este ETL trabaja con `page_size = 10000` y
`timeout_s = 230` y funciona. **Recomendación**: medir el cap real con
`bench-sigrid` (R5) y **avisar al dueño de `sigrid-api` para que actualice su
documento**; el dueño de ese documento es ese proyecto, no este
(`CLAUDE.md` § ecosistema). **Este proyecto no edita `azure-apps/sigrid_api.md`.**

**DA-7 · ¿Qué mejora mínima justifica implementar el bloque B?**
**Recomendación**: implementarlo solo si `perfil-carga` demuestra un ahorro
estimado **≥ 20 minutos** o si la ingesta pasa a ser **≥ 40 %** del tiempo
total. Por debajo de eso, el bloque B añade una máquina de estados nueva
(watermark, deriva, modos) a un ETL que hoy es reproducible y aburrido, a
cambio de calderilla.
