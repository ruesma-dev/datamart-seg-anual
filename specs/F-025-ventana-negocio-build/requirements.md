<!-- specs/F-025-ventana-negocio-build/requirements.md -->
# F-025 · Acotar el build por ventana de negocio — Requisitos (EARS)

> Rama prevista: `feature/F-025-ventana-negocio-build`. Rigor: **crítico**.
> No por defecto heredado, sino porque esta feature **cambia qué datos ve
> Power BI**: la misma razón por la que F-019 exigió prueba de equivalencia.

## 0 · De dónde viene esta feature

### 0.1 · Procedencia: el bloque C de F-011

Esta feature **no es nueva**: es el **bloque C de F-011** («Ventana de negocio
y build»), extraído el **2026-08-18** por decisión del humano. F-011 tenía
siete decisiones abiertas; el humano cerró seis y dejó **DA-1 —qué es una
«obra abierta»— sin decidir**, y ordenó sacar de F-011 todo lo que dependiera
de ella.

Lo que llega aquí desde `specs/F-011-carga-incremental/`:

| Venía de F-011 | Aquí es |
|---|---|
| R20 · `perfil-ventana` informa el peso de la ventana | **R1, R2, R4** |
| R21 · sin predicado declarado, `perfil-ventana` falla y lo dice | **R3** |
| El bloque `ventana:` de `config/business_rules.yaml` | **R3, R6** |
| `fetch_peso_ventana` en `postgres_client.py` | **R1** (diseño en `design.md` §3) |
| DA-1 · ¿qué es una obra abierta? | **DA-1, y sigue ABIERTA** |
| R22 de F-011 · «F-011 no acota el build» | La contrapartida positiva: **R8–R12** |

F-011 conserva R22 como barrera: mientras esta feature no exista en verde,
ninguna rama de F-011 puede tocar el SQL de `stg` ni de `mart`.

### 0.2 · Por qué esta feature va por delante del bloque B de F-011

El humano lo dejó escrito al cerrar DA-5 de F-011: **F-025 tiene prioridad
sobre el bloque B de F-011 si los números de la medición lo confirman.** Los
números de partida (carga completa en Azure del 2026-08-18,
`caj-datamart-seg-dev-6a95hln`, 165 min):

| Paso | Duración | % del total |
|---|---|---|
| `ingest_raw` | 33 min | 20 % |
| **`build_stg`** | **111 min** | **67 %** |
| `build_mart` | 21 min | 13 % |

Y dentro de `build_stg`, el desglose real medido en Azure (T12 de F-019):
**`build_plan_mensual` se lleva ~100 min de los 111**, repartidos en **60
tramos** (máximo 293 s el tramo 2), sobre 29,4 M de filas de salida.
`build_presupuesto` son otros ~23 min. En `build_mart`, `build_fact` son
~19 de los 21 min.

Traducido: **la ingesta entera (33 min) cuesta menos de un tercio de lo que
cuesta `build_plan_mensual`**. Si el 70 % de las filas pertenece a obras que
llevan años cerradas y se recalculan enteras cada noche, ahí está el dinero.
**Cuánto exactamente es lo que mide el bloque A de esta spec, y sin ese número
no se toca el build.**

### 0.3 · Relación con F-019: el build por tramos NO se toca sin prueba

F-019 (cerrada) reescribió el build de `stg.plan_mensual` **por tramos de
obras** para que cupiera en el `Standard_B1ms` de 2 GB tras el incidente del
2026-08-09, en el que el disco compartido de 32 GB llegó al 93,4 % y puso el
servidor en solo-lectura diez minutos, afectando potencialmente a `albaranes`
y `partes`.

Dos hechos de F-019 que **mandan sobre el diseño de esta feature**:

1. **El corte legítimo es por obra, no por mes ni por ejercicio.** Ninguna
   ventana del SQL de `08_plan_mensual.sql` cruza obras (particionan por
   `presupuesto_id` o por `(obra_id, partida_id, ambito_id)`), y por eso N
   pasadas con filtros de obra disjuntos dan exactamente las mismas filas. En
   cambio **el `ffill` y el `LAG` necesitan la serie mensual completa de la
   obra**: cortar por «ejercicio en curso» rompería el cálculo. La ventana de
   negocio, por tanto, **solo puede ser un conjunto de obras**.
2. **El troceo ya está construido y probado**, con su marcador
   `/*F019_FILTRO_OBRAS*/` en las dos ramas del SQL, su planificador puro
   `etl_sigrid/domain/tramos.py` y su puerta de disco. Esta feature **se
   apoya en él y no lo modifica**: la ventana decide *qué obras entran*, el
   planificador sigue decidiendo *cómo se empaquetan*.

Cualquier cambio que rozara el troceo exigiría rehacer la prueba de
equivalencia de F-019 desde cero. No se hace.

### 0.4 · Lo que esta feature NO puede romper

- **La coherencia de `raw` de F-024**: la puerta que exige mismo `batch_id` y
  todas las tablas en `SUCCESS` sigue igual (R16).
- **La huella de las vistas de consumo**: `mart.v_pbi_*`, `mart.v_fact_*`,
  `mart.v_master_*` y `cierre.v_pbi_*` son lo que consume Power BI. La prueba
  de equivalencia de R12 usa el mismo instrumento que F-019
  (`fingerprint-views` / `compare-fingerprints`).
- **El techo de disco del servidor compartido**: la puerta de ocupación de
  F-019 sigue armada y esta feature **no puede subir el pico** (R11).

---

## Bloque A · Medir el peso de la ventana (se implementa siempre)

> Este bloque **no depende de DA-1**. Es al revés: existe para que Negocio
> decida DA-1 con números delante. Por eso mide **candidatos**, en plural.

**R1.** CUANDO el usuario ejecuta `python main.py perfil-ventana`, el sistema
debe informar, en **solo lectura** sobre el datamart, y **para cada predicado
candidato** declarado en `config/business_rules.yaml` bajo `ventana.candidatos`:
número de obras dentro y fuera de la ventana, y el porcentaje de filas de
`stg.plan_mensual`, de `mart.fact_seguimiento_mensual` y de `raw.obrparpre`
que pertenecen a obras **dentro**.

**R2.** CUANDO `perfil-ventana` termina, el sistema debe estimar, por
candidato, el **ahorro en minutos**: el tiempo de `build_stg.build_plan_mensual`
(sumando sus filas `tramo_NN` de `_meta.etl_runs`) y el de
`build_mart.build_fact` atribuibles a las obras que quedan **fuera**,
prorrateados por el peso por obra que ya calcula
`SQL_PESOS_PLAN_MENSUAL`. Ese número, y no una intuición, es lo que decide si
el bloque B se implementa.

**R3.** SI `config/business_rules.yaml` no declara ningún candidato en
`ventana.candidatos`, ENTONCES `perfil-ventana` debe fallar con un mensaje que
diga que es una **decisión de Negocio pendiente (DA-1)** y **no** inventar un
criterio por defecto.

**R4.** CUANDO `perfil-ventana` se ejecuta con `--detalle` (y opcionalmente
`--out <csv>`), el sistema debe listar las obras que cada candidato deja
**fuera**, con su código y su descripción (`con.res`; recordar que `con.nom`
no existe), para que Negocio pueda mirar nombres concretos antes de firmar
DA-1.

**R5.** El sistema debe dejar el resultado de R1–R4 escrito en
`progress/ventana_F-025.md`, con la fecha, el `batch_id` de la carga medida y
una **recomendación** de qué candidato adoptar. MIENTRAS ese informe no exista
y **Negocio no haya firmado DA-1 sobre él**, ningún requisito del bloque B
puede darse por iniciado.

> Verificación de R5: **puerta de proceso**, no de código. El reviewer
> comprueba que el fichero existe, que sus números salen de `_meta.etl_runs` y
> de consultas al datamart —no de estimaciones— y que la firma de DA-1 está en
> `progress/current.md`.

---

## Bloque B · Acotar el refresco del build (solo tras la puerta de R5)

**R6.** El predicado de la ventana vigente debe declararse en
`config/business_rules.yaml` bajo `ventana.vigente`, como **SQL que devuelva
un conjunto de `obra_id`**. Cambiar la definición de «obra abierta» no debe
exigir tocar ni código Python ni ningún fichero `.sql`.

**R7.** MIENTRAS la ventana no se active explícitamente (`VENTANA_ACTIVA` a
falso, que es el valor por defecto), el build debe comportarse **exactamente
como hoy**: reconstrucción completa de `stg.plan_mensual` y de
`mart.fact_seguimiento_mensual`. La feature entra **apagada**.

**R8.** DONDE la ventana esté activa, `build_stg` debe recalcular
`stg.plan_mensual` **solo para las obras dentro de la ventana** y **conservar
intactas** las filas de las obras que quedan fuera.

> Este es el corazón de la feature y merece decirse en voz alta: **se acota el
> refresco, no el contenido.** Power BI sigue viendo el histórico completo; lo
> que se deja de hacer es recalcular cada noche lo que no ha cambiado. La
> alternativa —que fuera de la ventana el dato deje de existir— es DA-2, y no
> es la recomendada.

**R9.** DONDE la ventana esté activa, `build_mart` debe rehacer
`mart.fact_seguimiento_mensual` **solo para las obras dentro de la ventana**,
conservando las filas del resto, y `mart.agg_categoria` debe quedar coherente
con el hecho resultante.

**R10.** El troceo por tramos de F-019 **no cambia**. La ventana solo decide
qué obras se le pasan al planificador; `etl_sigrid/domain/tramos.py`
(`planificar_tramos`, `Tramo`, `tramos_sobredimensionados`) **no se modifica**,
y el marcador `/*F019_FILTRO_OBRAS*/` sigue siendo el único punto de inyección
de obras en el SQL.

**R11.** MIENTRAS la ventana esté activa, la ocupación de disco debe seguir
vigilada por la misma puerta de F-019 (`PG_DISCO_LIMITE_PCT`, 80 % por
defecto, sobre `PG_DISCO_TOTAL_GB`), y el **pico de ocupación de un build
acotado no puede superar el de un build completo**.

**R12.** CUANDO un build acotado termina, la huella de las vistas de consumo
debe ser **idéntica** a la de un build completo ejecutado sobre el mismo
`raw`, en los bloques `estructura` y `cerrado` de `fingerprint-views`.
Cualquier diferencia es **FALLO**: se marca la feature `blocked` y no se
racionaliza (precedente de F-019 T11).

> El bloque `vivo` de la huella puede diferir sin ser fallo: incluye
> `mart.v_pbi_dim_fecha`, que se genera con `CURRENT_DATE`. Eso ya está
> contemplado en `fingerprint.py` y no se toca.

**R13.** SI el predicado vigente devuelve **cero obras**, o deja fuera más del
`VENTANA_MAX_PCT_FUERA` por ciento de las obras, ENTONCES el build debe
**abortar antes de borrar o modificar una sola fila**, con el mismo patrón de
aborto que ya usa el plan por tramos (`PlanMensualAbortado`).

> Es la red contra un predicado mal escrito. Un `WHERE` que no case ningún
> `obra_id` no debe vaciar el datamart en silencio a las 02:00.

**R14.** CUANDO el build corre acotado, el sistema debe registrar en el
`metadata` de sus filas de `_meta.etl_runs`: el nombre del predicado aplicado,
el número de obras dentro, el número de obras recalculadas y el número de
filas conservadas sin recalcular.

**R15.** SI se ejecuta `run-all --full` o `stage --full`, ENTONCES el build
debe reconstruirse **completo desde cero** aunque la ventana esté activa; y el
sistema debe hacer esa reconstrucción completa **al menos una vez por semana**,
el mismo día que la recarga completa de la ingesta (**domingo**, DA-2 de
F-011), para que un cambio en una obra fuera de la ventana no pueda quedar
invisible más de siete días.

**R16.** MIENTRAS exista la ventana, la puerta de coherencia de `raw` de F-024
debe seguir exigiendo exactamente lo mismo que hoy: todas las tablas
declaradas, mismo `batch_id`, todas en `SUCCESS`. Un build acotado **no** es
excusa para relajarla.

**R17.** CUANDO una obra entra en la ventana o sale de ella entre dos cargas,
sus filas deben quedar consistentes: ni duplicadas ni huérfanas. En concreto,
el borrado y la reinserción de una obra deben ocurrir **dentro de la misma
transacción del tramo**, como ya hace F-019.

**R18.** El sistema **no** debe cambiar el significado de `stg.obras.activa`
—hoy cableado a `TRUE` para todas las obras en `sql/stg/03_obras.sql`— sin una
decisión explícita registrada. Si la ventana pasara a rellenar ese flag,
cambiaría lo que ve Power BI en `mart.v_pbi_dim_obra` (DA-5).

---

## Requisitos transversales

**R19.** Los comandos nuevos de solo lectura (`perfil-ventana`) **no** deben
generar `batch_id` ni escribir filas en `_meta.etl_runs`, igual que
`timings`, `status` o `fingerprint-views`.

**R20.** El sistema no debe leer ni escribir nada en Sigrid dentro de esta
feature: todo ocurre dentro del datamart. Si el predicado de DA-1 necesitara
una tabla de Sigrid que hoy **no se ingiere** —caso de `auxobrcts`, el
catálogo de situaciones de contrato al que apunta `obrctr.sitide`—, ENTONCES
debe declararse en `config/tables_sigrid.yaml` como una tabla más y ingerirse
por el camino normal, no consultarse al vuelo.

**R21.** SI un comando nuevo necesita credenciales, ENTONCES debe obtenerlas
de `config/settings.py` como el resto: ni un secreto en la spec, ni en el
código, ni en los tests, ni en `progress/`.

---

## Trazabilidad requisito → test

Todos los tests viven en `tests/` y **ninguno abre red ni BBDD**: el
`PostgresClient` va mockeado y los cálculos son funciones puras sobre
fixtures. Lo que no se puede probar así está marcado `MANUAL (humano)` y su
comando exacto está en `tasks.md`.

| Req | Test (fichero::nombre) | Sin red/BBDD |
|---|---|---|
| R1 | `test_f025_ventana.py::test_f025_r1_peso_por_candidato` | sí |
| R2 | `test_f025_ventana.py::test_f025_r2_ahorro_estimado_por_candidato` | sí (función pura sobre filas de `_meta.etl_runs` de fixture) |
| R3 | `test_f025_ventana.py::test_f025_r3_sin_candidatos_falla_y_lo_dice` | sí |
| R4 | `test_f025_ventana.py::test_f025_r4_detalle_lista_obras_fuera` | sí |
| R5 | **MANUAL (humano)** · el reviewer comprueba `progress/ventana_F-025.md` y la firma de DA-1 | n/a |
| R6 | `test_f025_config.py::test_f025_r6_predicado_vigente_se_lee_del_yaml` | sí |
| R7 | `test_f025_apagado.py::test_f025_r7_sin_ventana_el_build_es_el_de_hoy` | sí |
| R8 | `test_f025_build.py::test_f025_r8_solo_se_recalculan_las_obras_dentro` | sí (SQL compuesto + cliente mockeado) |
| R9 | `test_f025_build.py::test_f025_r9_mart_acotado_conserva_el_resto` | sí |
| R10 | `test_f025_build.py::test_f025_r10_tramos_py_no_cambia` + `pytest tests/test_f019_*.py` sin modificar | sí |
| R11 | `test_f025_build.py::test_f025_r11_puerta_de_disco_sigue_armada` | sí |
| R12 | **MANUAL (humano)** · `fingerprint-views` + `compare-fingerprints` (comando exacto en `tasks.md`) | no |
| R13 | `test_f025_guardias.py::test_f025_r13_predicado_vacio_o_excesivo_aborta` | sí |
| R14 | `test_f025_build.py::test_f025_r14_metadata_de_la_ventana` | sí |
| R15 | `test_f025_guardias.py::test_f025_r15_full_reconstruye_todo` | sí |
| R16 | `test_f025_guardias.py::test_f025_r16_la_puerta_de_raw_no_cambia` | sí |
| R17 | `test_f025_build.py::test_f025_r17_borrado_y_alta_en_la_misma_transaccion` | sí |
| R18 | `test_f025_alcance.py::test_f025_r18_obras_activa_sigue_cableada_a_true` | sí (lee el `.sql`) |
| R19 | `test_f025_ventana.py::test_f025_r19_perfil_ventana_no_escribe_en_meta` | sí |
| R20 | `test_f025_alcance.py::test_f025_r20_sin_lecturas_a_sigrid` | sí (barrido de imports) |
| R21 | `test_f025_alcance.py::test_f025_r21_sin_secretos_en_lo_nuevo` | sí |

**Verificaciones MANUAL (humano)**: R5 (informe firmado por Negocio), R12 (la
prueba de equivalencia contra Azure), y la primera noche real con la ventana
activa contrastada con un `run-all --full` inmediatamente posterior.

---

## Decisiones abiertas (NO las cierra el spec-author)

### DA-1 · ¿Qué es una «obra abierta»? — **LA PRIMERA, Y SIGUE ABIERTA**

Es la decisión que hizo que esta feature exista. El humano la dejó **sin
decidir el 2026-08-18** y es de **Negocio**, no técnica: de ella depende qué
obras dejan de recalcularse cada noche.

Lo que el código y el diccionario de Sigrid ofrecen hoy, con nombres exactos:

| Candidato | Fuente | Qué implica |
|---|---|---|
| **(a) Sin fecha real de fin** | `raw.obrctr.fecreafin` (Fecha real fin obra), con `raw.obr.fecfinrea` como respaldo | Es la **definición de facto que ya usa el proyecto**: `sql/cierre/05_views_cabecera.sql` agrega las fechas de `obrctr` y su comentario dice literalmente «Fin real: obrctr → obr (las obras vivas no lo tendrán)». Barata y ya probada. |
| **(b) Con movimiento reciente** | albaranes / facturas / partes de los últimos N meses | Más fiel a «viva de verdad», pero necesita definir N y cruzar varias tablas. |
| **(c) Situación explícita del contrato** | `raw.obrctr.sitide` → catálogo `auxobrcts` | El estado que Sigrid mantiene de verdad. **`auxobrcts` NO está declarada hoy en `config/tables_sigrid.yaml`**: adoptarla exige ingerirla (R20). |
| **(d) Fecha de cierre** | `raw.obr.fecfincie` (Fecha fin cierre), `obr.fecciepre` | Alineado con el módulo `cierre`; hay que verificar cómo está mantenido en Ruesma. |

**Recomendación del spec-author**: **(a) como definición primaria**, por ser
la que el proyecto ya usa y la que no exige ingerir nada nuevo, **+ (b) con
N = 12 meses como red** para no congelar una obra que sigue moviéndose aunque
tenga fecha de fin puesta. Ambas declaradas como predicado SQL en
`config/business_rules.yaml`, de modo que cambiarlas no toque código. **Y con
los tres candidatos medidos por el bloque A antes de firmar**: puede que la
diferencia entre (a) y (c) sean cuatro obras y la discusión sobre cuál elegir
valga menos que la medición.

**Requiere confirmación de Negocio.** Recordar que las fechas de Sigrid son
enteros `YYYYMMDD` con `0` en lugar de NULL, y que el proyecto ya tiene
`stg.fn_sigrid_date_to_date` para eso.

### DA-2 · ¿La ventana acota el REFRESCO o el CONTENIDO?

(a) **Refresco**: se deja de recalcular lo cerrado, pero el dato sigue en el
datamart y Power BI ve el histórico completo. (b) **Contenido**: fuera de la
ventana el dato no existe; el datamart adelgaza y el build es aún más barato,
pero **Power BI pierde informes**. **Recomendación: (a)**, y toda esta spec
está escrita sobre esa hipótesis (R8, R9, R12). Con (a) la equivalencia es
demostrable con el instrumento que ya existe; con (b) no hay equivalencia que
demostrar, solo una pérdida que Negocio tendría que aceptar por escrito.

### DA-3 · ¿Cómo se sustituyen las filas de una obra recalculada?

(a) `DELETE FROM stg.plan_mensual WHERE obra_id = ANY(...)` + `INSERT`, dentro
de la transacción del tramo, con índice por `obra_id`. (b) Construir en una
tabla nueva y copiar las filas conservadas. **Recomendación: (a)**, porque (b)
copia ~24 M de filas cada noche y **duplica temporalmente la ocupación de
disco** justo en el servidor donde ya hubo un incidente. El riesgo de (a) es
el *bloat* y el WAL del borrado repetido: hay que **medirlo** en el bloque A y
vigilarlo con la puerta de disco de F-019 (R11).

### DA-4 · ¿Se acota también `build_presupuesto` (~23 min)?

`stg.presupuesto` (13,76 M filas) es la entrada de `plan_mensual`. Acotarlo
multiplica el ahorro, pero añade una dependencia más entre sub-pasos.
**Recomendación**: **no en la primera entrega**. Primero `plan_mensual` (~100
min) y `fact` (~19 min), que son el 80 % del problema; `presupuesto` se
reevalúa con los números reales de la primera noche acotada.

### DA-5 · ¿`stg.obras.activa` pasa a reflejar la ventana?

Hoy es un `TRUE` literal en `sql/stg/03_obras.sql` y llega a Power BI por
`mart.v_pbi_dim_obra`. Rellenarlo con el predicado de la ventana sería
gratis técnicamente y **cambiaría un dato que alguien puede estar filtrando**.
**Recomendación**: **no tocarlo** en esta feature (R18) y, si Negocio lo
quiere, hacerlo en un cambio propio con su aviso.

### DA-6 · Cadencia de la reconstrucción completa del build

**Recomendación**: **el mismo domingo** que la recarga completa de la ingesta
(DA-2 de F-011), y por la misma razón: un solo día «caro» a la semana, en la
ventana que se comparte con `albaranes` y `partes`. Queda por confirmar que
las dos cosas caben la misma noche —una completa de ingesta (33 min) más un
build completo (~132 min) son ~2 h 45— o si conviene separarlas.

### DA-7 · Prioridad frente al bloque B de F-011

El humano ya dijo que **F-025 va por encima del bloque B de F-011 si los
números lo confirman**. Lo que queda es confirmarlo: si el bloque A de esta
spec (R2) demuestra un ahorro claramente mayor que los 33 min que como mucho
puede ahorrar la ingesta, esta feature se implementa antes.
