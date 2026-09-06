<!-- specs/F-025-ventana-negocio-build/mediciones.md -->
# F-025 · Mediciones · La línea base, con sus fuentes

Todo lo de aquí está **medido el 2026-09-02**, en **solo lectura** y con
consultas ligeras: `stg.obras` (583 filas), `stg.fases` (4.551), `stg.partidas`
(390.501), `maestro.obras` (919), `cierre.v_pbi_cierre_cabecera` (583) y
`_meta.etl_runs` (2.303). **No se ha contado `stg.plan_mensual`, `stg.presupuesto`
ni el fact**: son millones de filas y el servidor está recuperándose sin créditos.
Las cifras de esas tres vienen de `_meta.etl_runs` y de `progress/current.md`.

## 1 · La avería, tramo a tramo (`_meta.etl_runs`)

| Ejecución | Tramos | Filas | Min/tramo (media) | Máx |
|---|---|---|---|---|
| 15 nocturnas del 19-ago al 01-sep | 60/60 | 29,6-29,8 M | **1,55-1,59** | ~5 |
| 2026-09-01 08:20 (stage manual de F-052) | 60/60 | 29.762.403 | **7,91** | 18,03 |
| **2026-09-02 02:00 (la que murió)** | **5 de 60 OK** | **6.436.281** | **40,77** | **49,21** |

Lecturas que importan:

- La nocturna sana cuesta **~94 min** solo en `plan_mensual` (60 × 1,57).
- El día 01 el servidor **ya venía castigado** (7,91 min/tramo): las 8 h 15 del
  stage manual de F-052 dejaron la hucha de créditos vacía y la nocturna del 02
  arrancó sin ella. La avería tiene dos causas, no una: **trabajo de más** y
  **hucha vacía**.
- 40,77 / 1,57 ≈ **26 veces más lento**, coherente con un `B1ms` capado al 20 %
  de un núcleo más la contención de `albaranes` y `partes`.

## 2 · El censo de obras

Dos universos y dos definiciones de actividad conviven en esta sección. **Manda
la de «El criterio decidido (DA-1) y su censo»**, que es la del código (universo
`raw.obr ⨝ raw.con`, 920). Lo que viene justo debajo es el sondeo previo sobre
`stg.obras` (583), que sirvió para elegir criterio y **no** para censarlo.

### Sondeo previo (universo `stg.obras`, 583)

Actividad = mes más reciente con fase cerrada (`stg.fases.anio`/`mes`).

| Antigüedad de la última fase | Obras |
|---|---|
| ≤ 3 meses | 33 |
| ≤ 6 meses | 38 |
| **≤ 12 meses** | **44** |
| ≤ 18 meses | 59 |
| ≤ 24 meses | 77 |
| ≤ 36 meses | 89 |
| **Sin ninguna fase** | **217** |

### El criterio decidido (DA-1) y su censo — REMEDIDO EL 2026-09-03

**Esta es la tabla que manda.** Está medida con la definición **que implementa el
código**: universo `raw.obr JOIN raw.con` y actividad =
`MAX(make_date(f.anio, GREATEST(f.mes,1), 1))` sobre `stg.fases`, o sea
literalmente `postgres_client.SQL_ESTADO_OBRAS`, la consulta que el guardán corre
cada noche. El corte de los 12 meses es el de `_meses_entre` en
`domain/ventana.py`: se congela cuando la antigüedad en meses es **> 12**, lo que
con `hoy = 2026-09-03` deja dentro todo lo que sea `>= 2025-09-01`.

| | Obras | Fuente |
|---|---|---|
| **Universo** (`raw.obr ⨝ raw.con`) | **920** | `SQL_ESTADO_OBRAS` |
| Regla 1 · estado **EN ESTUDIO (1), NO PRESENTADA (11) o CERRADA (25)** | 693 | `raw.con.est` |
| Regla 2 · código de **seis dígitos** | **226**, y **ninguna llega al fact** (0 de 226 están en `stg.obras`) | `raw.con.cod` ⨝ `stg.obras` |
| Regla 3 · **sin actividad** en 12 meses | 872 | `stg.fases` |
| **Congeladas (unión de las tres)** | **880** | — |
| **Actualización diaria (vivas)** | **40**, de ellas **38** publican en el fact | — |
| Con actividad en 12 meses | 48 | `stg.fases` |
| Con actividad en 12 meses **pero congeladas** | **8**: **7** CERRADAS (estado 25) y **1** de seis dígitos (`180501`). Últimas actividades: 2026-07, 2026-04, 2026-01 (×2), 2025-11, 2025-10 (×2), 2025-09 | — |

40 vivas + 8 congeladas = las 48 con actividad: la tabla cierra por sí sola.

#### La medición vieja, y por qué NO vale

La primera versión de esta sección (2026-09-02) medía sobre **`maestro.obras`** con
`coalesce(fecha_fin, fecha_inicio)` como actividad, y su detalle obra a obra vivía
en **`obras_candidatas_a_congelar.csv`** / `obras_congeladas_F025.csv` (en la raíz,
**no versionados**: `.gitignore` excluye `obras_*.csv`). Decía **222** de seis
dígitos, **840** sin actividad y **40** congeladas pese a tener actividad, 39 de
ellas CERRADAS y 36 con última actividad en 2025-12.

**Ninguna de esas cuatro cifras reproduce con la definición del código**, y el CSV
es la raíz del error: da a 36 obras un `2025-12` que `stg.fases` no confirma —la
`0620` la tiene en `2024-01`, y `raw.obrfas` igual—. **El código va bien; lo que
no reproduce es el CSV.** Se conservan aquí los números viejos solo para que
quien los vea citados en un documento anterior sepa que están muertos. Las que
SÍ cuadran, y por eso el titular de la decisión se sostiene, son **880 / 40**.

### El catálogo de estados, verificado el 2026-09-02

Vive en **`conest`**, tipo **42**, y se llega por `con.est` (confirmado contra
Sigrid por `sigrid-api`, en solo lectura): 1 EN ESTUDIO (226 obras), 3 PRESENTADA
(0), 5 PRESENTADA CON ACLARACIONES (0), 7 ADJUDICADA PROVISIONAL (0), 9 ADJUDICADA
DEFINITIVAMENTE (33), 11 NO PRESENTADA (2), 13 NO ADJUDICADA (0), 15 EN CURSO (176),
17 PARADA (7), 19 TERMINADA (2), 21 RECIBIDA PROVISIONAL (3), 23 RECIBIDA
DEFINITIVAMENTE (4), **25 CERRADA (465)**, 999 PLANTILLA (1).

### Los censos que se compararon antes de decidir

Sobre el universo más estrecho de `stg.obras` (583), que es el del seguimiento. Se
conservan porque son los que sostienen por qué la marca de Sigrid sola no bastaba:

| Criterio | Congela | Falsos positivos (congelaría algo vivo) |
|---|---|---|
| Sin fase en **12 meses** | **322** | 0 (por construcción) |
| Sin fase en **24 meses** | 289 | 0 |
| `maestro.obras.estado_id = 25` | 462 | **7** obras con fase en los últimos 12 meses |
| **Fecha real de fin informada** (`cierre.v_pbi_cierre_cabecera.fecha_fin_real`) | 247 | **6**; y deja **298** obras paradas >12 m sin congelar |
| 12 meses **+ veto de `estado_id = 15`** | **319** | 0; el veto rescata 3 obras |

Reparto por estado de Sigrid (583 obras de `stg.obras`):

| `estado_id` | Obras | Sin fases | Con fase ≤12 m |
|---|---|---|---|
| 25 | 462 | 140 | **7** |
| 15 (EN CURSO) | 98 | 64 | 31 |
| resto (9 valores) | 23 | 12 | 6 |

**Conclusión de negocio:** ninguna marca de Sigrid es fiable por sí sola. `25`
congelaría 7 obras que siguen cerrando meses y la fecha de fin real falla en los
dos sentidos. La actividad medida es objetiva y se equivoca solo por exceso de
trabajo, nunca por dato viejo.

## 3 · El peso, estimado (no medido) — MEDIDO el 2026-09-05 en la Fase 7 (T1): ahorro real 59,2 %

`stg.plan_mensual` no se puede contar hoy. **Estimación** con el proxy
`partidas × fases` por obra, que aproxima el peso de los ámbitos reales (3 y 7):

| Grupo | Obras | Partidas | Proxy de peso | % |
|---|---|---|---|---|
| Con fase ≤ 12 m | 44 | 52.279 | 1.122.729 | **26,2 %** |
| Entre 12 y 24 m | 33 | 34.990 | 940.108 | 21,9 % |
| Más de 24 m | 289 | 146.578 | 2.203.926 | 51,4 % |
| Sin fases | 217 | 25.231 | 25.231 | 0,6 % |

Con el criterio de 12 meses se congela el **73,3 %** del proxy. **Es una cota, no
una medición**: el proxy no cubre los ámbitos master (8 y 11), cuyo peso depende
de `cardinality(planif)` y se concentra en obras vivas, así que **el ahorro real
será menor**. Medirlo de verdad es **T1**, con la consulta de pesos que la
nocturna ya ejecuta cada noche (`SQL_PESOS_PLAN_MENSUAL`).

## 4 · Dos cifras que salen de restar, y hay que confirmar

- El build reconstruye **687 obras** (universo de `stg.presupuesto`), y `stg.obras`
  tiene **583**: hay del orden de **104 obras** que se construyen en
  `stg.plan_mensual` y que **el fact descarta** con su `INNER JOIN stg.obras`
  (`mart/02_build_fact.sql:232`). La regla de los seis dígitos (DA-3) congela **226**
  de las 920 del universo y **ninguna de ellas llega al fact** —recomprobado el
  2026-09-03: 0 de esas 226 están en `stg.obras`, que es el `INNER JOIN` del fact—:
  son presupuestos y estudios de 2009-2015. Cuánto pesan lo dará T1.
- `stg.plan_mensual` completa son **29.762.403** filas (01-sep). La avería la dejó
  en 6.436.281, el **21,6 %**.

## 5 · Las consultas exactas

Todas por el MCP de solo lectura (`mcp-bbdd`, rol `mcp_sigrid_dm_ro`), **salvo la
del censo remedido**: el MCP no autoriza el esquema `raw`, así que esa se lanzó
en solo lectura por `psycopg` con la conexión del `.env`, `read_only = True` y
`statement_timeout = 120s`. Respondió en segundos.

```sql
-- Censo de actividad
WITH ult AS (
  SELECT o.obra_id,
         MAX(make_date(f.anio, GREATEST(f.mes,1), 1)) AS ultimo_mes_fase,
         COUNT(f.fase_id) AS n_fases
  FROM stg.obras o
  LEFT JOIN stg.fases f ON f.obra_id = o.obra_id AND f.anio BETWEEN 1990 AND 2100
  GROUP BY o.obra_id)
SELECT COUNT(*),
       COUNT(*) FILTER (WHERE n_fases = 0),
       COUNT(*) FILTER (WHERE ultimo_mes_fase >= date '2026-09-01' - INTERVAL '12 months')
FROM ult;

-- CENSO DEL CRITERIO, REMEDIDO EL 2026-09-03 con la definicion DEL CODIGO.
-- Es el que produce la tabla de arriba. Ligero: raw.obr/raw.con (920),
-- stg.fases (4.551) y stg.obras (583). No toca el fact ni plan_mensual.
WITH universo AS (
  SELECT c.ide AS obra_id, COALESCE(TRIM(c.cod),'') AS codigo_obra, c.est AS estado_id,
         ult.ultima_actividad
  FROM raw.obr o
  JOIN raw.con c ON c.ide = o.ide
  LEFT JOIN LATERAL (
      SELECT MAX(make_date(f.anio, GREATEST(f.mes, 1), 1)) AS ultima_actividad
      FROM stg.fases f WHERE f.obra_id = c.ide AND f.anio BETWEEN 1990 AND 2100
  ) ult ON TRUE
), clas AS (
  SELECT u.*,
         (u.estado_id IS NOT NULL AND u.estado_id IN (1,11,25))            AS r1,
         (u.codigo_obra ~ '^[0-9]{6}$')                                    AS r2,
         (u.ultima_actividad IS NULL OR u.ultima_actividad < date '2025-09-01') AS r3,
         (u.ultima_actividad >= date '2025-09-01')                         AS con_act,
         EXISTS (SELECT 1 FROM stg.obras s WHERE s.obra_id = u.obra_id)    AS en_stg
  FROM universo u)
SELECT count(*)                                                            AS universo,
       count(*) FILTER (WHERE r1 OR r2 OR r3)                              AS congeladas,
       count(*) FILTER (WHERE NOT (r1 OR r2 OR r3))                        AS vivas,
       count(*) FILTER (WHERE NOT (r1 OR r2 OR r3) AND en_stg)             AS vivas_en_fact,
       count(*) FILTER (WHERE r1)                                          AS regla1,
       count(*) FILTER (WHERE r2)                                          AS regla2,
       count(*) FILTER (WHERE r2 AND en_stg)                               AS regla2_en_fact,
       count(*) FILTER (WHERE r3)                                          AS regla3,
       count(*) FILTER (WHERE con_act)                                     AS con_actividad,
       count(*) FILTER (WHERE con_act AND (r1 OR r2 OR r3))                AS congeladas_con_actividad
FROM clas;
-- Resultado 2026-09-03: 920 | 880 | 40 | 38 | 693 | 226 | 0 | 872 | 48 | 8

-- Peso proxy por grupo: partidas x fases (ver §3)
-- Estado de Sigrid: maestro.obras.estado_id LEFT JOIN stg.obras
-- Tramos de la avería: _meta.etl_runs, step LIKE 'build_stg.build_plan_mensual.tramo%'
```

## 6 · Lo que queda por medir (y bloquea decisiones)

| Qué | Cuándo | Decide |
|---|---|---|
| Peso real por obra (`SQL_PESOS_PLAN_MENSUAL`) | T1 | Si la feature merece la pena |
| Tamaño y tuplas muertas de las dos tablas acotadas | T2 y T33 | Si el `DELETE` selectivo aguanta o hay que particionar |
| Coste del scan de la firma sobre `raw.obrparpre`, con y sin `planif` | **T3** | La forma final de la firma y la laguna de R20 |
| Créditos de CPU al terminar la nocturna acotada | T34 | R29, el criterio de aceptación |

## 7 · T2 · La línea base del bloat, medida el 2026-09-02

Medido por el MCP de solo lectura sobre el **catálogo** (`pg_class`,
`pg_stat_user_tables`): no barre ni una fila de las dos tablas, así que se pudo
hacer con el servidor sin créditos. Es la línea contra la que T33 comparará
después de una semana acotada.

| Tabla | Total | Solo datos | Filas vivas | Tuplas muertas | Último autovacuum |
|---|---|---|---|---|---|
| `stg.presupuesto` | **2.893.283.328 B** (2.759 MB) | 1.589.837.824 B | 13.862.725 | **0** | 2026-09-02 03:17 |
| `stg.plan_mensual` | **1.813.725.184 B** (1.730 MB) | 1.297.457.152 B | 6.438.486 | **0** | 2026-09-02 07:25 |

**Cuidado al leer `plan_mensual`: son las cifras de la tabla TRUNCADA por la
avería** (6,4 M de 29,8 M filas, el 21,6 %). A tabla llena el total sería del
orden de **8 GB**, sobre un disco de 32 GB compartido con `albaranes` y
`partes`. Es la cota que hace del bloat un riesgo real y no teórico (§9.1 de
`design.md`), y la razón de que T33 no sea opcional.

Las dos tablas están hoy con **cero tuplas muertas** y autovacuum recién pasado:
la línea base es limpia, así que cualquier crecimiento sostenido que T33 mida
será atribuible al `DELETE` por obra y no a deuda anterior.

### Los índices que hacen barato el `DELETE` (verificado, no supuesto)

`design.md` §2 afirma que el `DELETE ... WHERE obra_id = ANY (...)` va por
índice. Comprobado contra `pg_indexes` el 2026-09-02:

- `idx_plan_mensual_obra_amb` → `btree (obra_id, ambito_id)`
- `idx_pres_obra_amb` → `btree (obra_id, ambito_id)`

Las dos **empiezan por `obra_id`**, así que el borrado derivado no barre la
tabla. **No hay ningún índice que crear.**

### Lo que NO se ha medido, y por qué

**T1** (peso real por obra con `SQL_PESOS_PLAN_MENSUAL`) y **T2b** (coste del
scan de la firma sobre `raw.obrparpre`) siguen **pendientes del humano**: las
dos barren tablas de millones de filas y el servidor está recuperando créditos
de CPU tras la avería. Lanzarlas ahora volvería a vaciar la hucha, que es
exactamente lo que esta feature existe para evitar. La cota estimada del §3
(73,3 % del proxy) sigue siendo lo único que hay sobre el ahorro.

---

## Fase 7 · Lo medido de verdad (bitácora, 2026-09-04 y 05)

### T27 · Las cinco huellas del ANTES — HECHA el 2026-09-04

Sobre el datamart que dejó la nocturna del 04, en `huellas/antes_*.csv` (fuera
de git). Son la línea base contra la que T30 compara **con tolerancia cero**:

| capa | celdas | obras |
|---|---|---|
| `stg` | 12.407 | 349 |
| `mart` | 24.775 | 349 |
| `cierre` | 16.948 | 330 |
| `dimension` | 735 | 504 |
| `plan_obra` | 938 | 350 |

La huella de `stg` **hubo que lanzarla tres veces**: dos caídas de la conexión
del puesto —una con la IP rotando a mitad de consulta— y a la tercera, 15 min.
No fue culpa del servidor: tenía 60 créditos y la CPU al 12 %.

### T35 · La alerta de la ventana — HECHA el 2026-09-04

`alert-caj-datamart-seg-dev-ventana`, desplegada, **activa**, severidad 2. Sin
ella el guardián es mudo (DA-5).

### T29 · La primera reconstrucción acotada

**Intento 1 · 2026-09-05 02:00 UTC · `caj-datamart-seg-dev-29809560` · FALLÓ.**
`AttributeError: 'PostgresClient' object has no attribute 'fetch_filas_por_obra'`
en `build_stg_step.py:628`, dos veces. Detalle en
`progress/incidencia_F-025_nocturna_20260905.md`. Lo que sí dejó medido:

| paso | resultado |
|---|---|
| `ingest_raw` | SUCCESS · 20.147.626 filas · 2.206 s y 1.782 s |
| `build_stg` | **FAILED** · 395.929 filas · 1.299,7 s y 1.463,7 s |
| `build_compras` | SUCCESS · 2.500.592 · 488 s |
| `build_maestros` / `build_retenciones` | SUCCESS · 26.170 / 29.966 |
| `mart` · `cierre` · `diccionario` · `grants` | SKIPPED |

**Coste en créditos de CPU**: 78 a las 02:03 → 53 a las 09:03. Las 2 h 19 de job
se llevaron **unos 40 créditos** de los 288 del tope (ver `progress/current.md`:
el tope de 144 que este proyecto asumía era falso).

**Intento 2 · 2026-09-05 10:44 UTC · `caj-datamart-seg-dev-kcb9n2r`**, lanzado a
mano con `az containerapp job start` sobre la imagen `r20260905-1237`, la del
arreglo. Saldo al arrancar: **57 créditos**, subiendo ~4/h. Duración esperada
4-5 h por las nocturnas completas del 03 (4 h 18) y del 04 (4 h 50).
**Resultado: FALLÓ por `replicaTimeout` (5 h), con el código ya bien.**
`build_presupuesto` pasó (13.874.194 filas, 1.438,6 s) **y el registro en
`_meta.obra_build` también**: el arreglo funciona. Murió en `plan_mensual`,
tramo **35/60**, con los créditos **a 1 desde antes de las 15:01**: los tramos
33-35 tardaron **788 / 728 / 539 s** frente a los ~120 s a ritmo normal. Se
paró el reintento, se quitó la nocturna y el timeout pasó a **7 h**. Relanzar
el domingo con la hucha llena (288).

**Intento 3 · 2026-09-05 17:30 UTC · `caj-datamart-seg-dev-hamsh8o` · SUCCEEDED
en 4 h 52 (17:30:12 → 22:22:37).** Lanzado a mano nueve minutos después de
escalar el servidor a **`Standard_B2s`** (el humano autorizó subir unos días y
bajar cuando esté estable; ver `progress/current.md`). Saldo al arrancar: **60**,
los créditos iniciales que Azure da al escalar (el reseteo está medido: de 6 a
60 en el reinicio). **T29 cumplida**: `_meta.obra_build` tiene **920 filas, 920
obras** (construidas entre las 18:18 y las 20:23), `stg.plan_mensual`
**29.772.701 filas**, `check-ventana` **OK** (920 miradas, 0 hallazgos),
`check-cobertura` en el **KO conocido** de F-052 (20 obras invisibles, 294
huérfanas: esta rama no lleva sus excepciones), diccionario publicado en
**versión 13**.

| paso | resultado |
|---|---|
| `ingest_raw` | SUCCESS · 20.147.626 filas · **1.832 s** (2.206 y 1.782 el día antes estrangulado) |
| `build_stg` | SUCCESS · 44.042.947 · **9.527 s** (2 h 39; `plan_mensual` 60/60, tramos de 47 a 220 s) |
| `build_mart` | SUCCESS · 5.384.370 · 2.840 s (47 min) |
| `build_maestros` / `build_compras` / `build_retenciones` | SUCCESS · 4 / 456 / 53 s |
| `build_cierre` | SUCCESS · 16.952 · **2.665 s** (44 min, casi todo `build_fact`) |
| `publicar_diccionario` · `apply_grants` | SUCCESS · 0,6 / 0,3 s |

**Coste en créditos, curva medida a un minuto (B2s: 24/h de recarga, base 0,8
vCPU)**: 60 (17:40) → 50 (18:10) → 31 (19:05) → 15 (19:40) → **mínimo 6 a las
20:05**, al final de `plan_mensual` → **sube** durante `mart` y `cierre` (13 a
las 21:00, 17 a las 21:55) → 14 al terminar. Dos lecturas: (1) el gasto neto de
la completa es **~54 créditos más lo recargado en 4 h 52 (~117)**, o sea del
orden de **170 créditos**, y por eso no cabía en los 57 de la mañana ni en un
B1ms a medias; (2) `mart` y `cierre` **no consumen créditos** en el B2s: su CPU
media queda por debajo del 40 % de base, son pasos de E/S. Todo el gasto está
en `ingest_raw` y `build_stg`. Nota: aun con la hucha casi a cero el B2s no se
estranguló (los últimos tramos iban a 47-57 s), que era el argumento para
subirlo.

**Ojo con la comparación de duraciones**: 4 h 52 es lo mismo que la completa
del 04 en B1ms con créditos (4 h 50). El B2s no acelera un build en serie de
una sola conexión; lo que hace es **no morir** cuando la hucha se vacía. Esta
es la primera pasada y reconstruye las 920 por R18; la acotada de verdad es la
siguiente nocturna, y esa es la que T33/T34 y F-065 tienen que medir.

### T28 · El plan en seco — HECHO el 2026-09-05, 22:50 UTC, tras la completa

Ojo con el entorno: el `.env` del puesto **no lleva `PG_VENTANA_ACTIVA`** (la
ventana se encendió en Azure, no en local), así que `ventana-plan` a secas dice
`completa: True (la ventana esta DESACTIVADA)` y 920/0. Se lanzó con la variable
puesta en la shell, sin tocar `.env`:

```
PG_VENTANA_ACTIVA=true python main.py ventana-plan --detalle
```

**Resultado: 920 censadas, 592 se reconstruirían, 328 se quedarían.** Por
motivo: `sin_filas` 552, `ventana` 368. **Cuadra con el censo de §2, pero no
como lo dice la tarea** («40 a reconstruir y 880 congeladas»):

- **368 obras tienen filas en `stg.plan_mensual`** (medido: `count(distinct
  obra_id)` = 368). De ellas **40 son vivas** (592 − 552) y **328 se congelan**.
  Esas son las cifras del censo.
- **Las otras 552 no tienen ni una fila en `plan_mensual`**, y R18 manda
  reconstruirlas siempre («completar no es actualizar»). En `plan_mensual` no
  cuesta nada, pero **319 de ellas sí tienen filas en `stg.presupuesto`** y
  327 en `stg.partidas`: ese presupuesto se rehace cada noche. Cuánto pesa lo
  dirá T1; si es poco, R18 se queda como está; si no, habría que distinguir
  «sin filas porque no las tiene» de «sin filas porque no se ha construido».

### T30 · Las cinco huellas del DESPUÉS — HECHAS el 2026-09-05, 22:44-23:00 UTC

Capturadas desde el puesto, con el B2s: `dimension` 5 s, `plan_obra` 3 min,
`cierre` 7 s, `mart` 4 s (el día 4, en el B1ms, `stg` tardó 15 min y se cayó
dos veces). Mismos recuentos que el ANTES en las cuatro: 735/504, 937/350
(938 el día 4), 16.952/330, 24.779/349 (24.775 el día 4).

**Las cuatro comparaciones salen KO a tolerancia cero**, y **las diferencias
NO son del ETL**: son cambios en Sigrid entre la ingesta del 04 y la del 05.
Las pruebas, una a una:

| capa | obras que se mueven | qué cambia |
|---|---|---|
| `dimension` | 0678, 0696, 0699, 0712, 0722, 0724, 180501, POSTV2 | número de partidas (p. ej. 0722: 362 → 372; 180501: 175 → 168) |
| `plan_obra` | 0678, 0709, 0712, 0722, 180501 | filas e `importe_origen` de los ámbitos 3, 7, 8 y 11 |
| `mart` | 0678, 0709, 0712 | `importe_mes` de **2026-08** en ámbitos 3 y 7; **master 8 y 11: 0 cambios** |
| `cierre` | 0678, 0696, 0697, 0699, 0707, 0709, 0711, 0712, 0722, 0723, 0724 | `final_importe` y `pendiente_importe` del mes **2026-08-01** |

1. **`stg.partidas` = `raw.obrparpar` en las ocho obras de `dimension`**, fila a
   fila en el recuento (0722: 372 y 372; 180501: 168 y 168). El ETL reproduce
   exactamente lo que trae el `raw` de hoy; lo que difiere del día 4 es el
   `raw`.
2. **El SQL que construye `stg.partidas` no lo ha tocado F-025**: su último
   commit es `a470ebf` (F-052, 2026-09-01), anterior a la imagen del 02-sep con
   la que se hizo el ANTES. Mismo SQL, distinto `raw`.
3. **Las once obras con código son todas `obra viva`** en el plan de T28
   («no cumple ninguna de las tres reglas»): 0678, 0696, 0697, 0699, 0707,
   0709, 0711, 0712, 0722, 0723, 0724. Las dos sin código —180501
   (administrativa, seis dígitos) y POSTV2 (postventa)— son `sin_filas`. Ni
   una congelada se mueve.
4. **Lo que cambia es actividad de agosto**: en `mart` solo se mueven los
   ámbitos 3 y 7 (coste y venta real) del mes 2026-08, y los master 8 y 11 dan
   0 cambios. Es la forma exacta de un día de trabajo en Sigrid: partes y
   facturas de agosto que entran en septiembre.
5. **La reconstrucción de hoy fue completa por R18** (`obra_build` estaba
   vacía), así que ninguna obra se congeló: esta comparación no prueba nada
   sobre congelar, prueba que el build nuevo sobre el `raw` nuevo da lo que
   trae Sigrid. La equivalencia que T30 quiere —«sobre el mismo `raw`»— exige
   otra captura: **huellas ahora (sobre el `raw` del 05) y las mismas huellas
   tras un build acotado sin volver a ingerir**.

Un dato que Negocio puede querer saber, aunque no sea del ETL: la obra
**180501** perdió 7 partidas y su ámbito 7 entero en `plan_obra` (853.790 €
que ya no están en el origen), y el ámbito 3 pasó de 835.621 € a 90.079 €.

**La huella de `stg`** (9 min desde el puesto, 12.409 celdas de 349 obras;
12.407 el día 4) sale **KO con dos avisos**: 3 obras fuera de la lista (0678,
0709, 0712) y **66 cambios en los ámbitos master 8 y 11**, todos de la 0712, que
el comparador da por intocables. **Tampoco es del ETL, y aquí la prueba es
directa**: `raw.obrfasamb` tiene para la 0712 **doce versiones** del master
(0-11) en los dos ámbitos, y la **versión 11, «CIERRE AGOSTO-26», se creó en
Sigrid el 2026-09-04** (`fec = 20260904`), *después* de la nocturna de las
02:00 de ese día que sirvió de ANTES. `stg.presupuesto` reproduce `raw.obrparpre`
**fila a fila en las 24 combinaciones (ámbito × versión)** de la obra —444/444
… 465/465 en el 8, 378/378 … 399/399 en el 11—, y de los nueve SQL de `stg`,
F-025 solo tocó `06_presupuesto.sql`. `mart` no se movió en master porque su
versión vigente por mes se fija por fecha efectiva y el cierre nuevo aún no
manda. Es, otra vez, Sigrid trabajando entre las dos capturas.

**Veredicto de T30 tal como está definida: KO en las cinco capas, todas las
diferencias explicadas por el origen y ninguna en una obra congelada.** La
tarea dice que cualquier diferencia PARA la feature y se consulta al humano;
consultado el 2026-09-05 a las 23:05 UTC. **DECISIÓN DEL HUMANO (2026-09-06,
01:10 local): T30 se da por buena** —«parecen cambios de obras vivas, es
normal»—, con la confirmación de que el origen de cada diferencia es que se
ingirieron dos volcados de Sigrid distintos en días distintos. La propuesta
de repetirla sobre el mismo `raw` queda como opción, no como obligación: la
prueba de que congelar no cambia una celda la dará T31b en la primera
nocturna acotada. Lo que sigue era la propuesta antes de la decisión: dar
esta T30 por **no concluyente** por diseño (dos `raw` distintos y ninguna obra congelada
en la primera pasada) y sustituirla por la captura sobre el mismo `raw`:
huellas del datamart actual, un build acotado **sin ingesta**
(`PG_VENTANA_ACTIVA=true`, `stage` + `build-mart` + los de negocio + `cierre`
desde el puesto, o el job con la ingesta saltada) y las mismas huellas
después. Con el B2s cada huella cuesta segundos, salvo `stg` (9 min) y
`plan_obra` (3).

### T31 · La 0599 — HECHA el 2026-09-05, 23:07 UTC

`python main.py inspect-cierre --codigo 0599` (obra 1442383, TANATORIO
MAJADAHONDA), último mes Diciembre 2022, fase 28: **DIRECTOS 2.624.793,46 €**,
BENEFICIO 72.603,10 € sobre 4.066.989,23 € de venta = **1,79 %**. Las mismas
cifras de F-052.

### T32 · Los cinco `check-*` — 2026-09-05/06, tras `hamsh8o`

| check | veredicto | igual que antes del cambio |
|---|---|---|
| `check-ventana` (en `run-all`) | **OK**, 920 miradas, 0 hallazgos | primera vez que corre |
| `check-declarados` (en `run-all`) | OK (el job salió en `Succeeded`, y este es el que tumba) | sí |
| `check-cobertura` (en `run-all`) | **KO conocido de F-052**: 20 invisibles, 294 huérfanas (esta rama no lleva sus excepciones) | sí, 04-sep |
| `check-unicidad --timeout 300` (11 min) | **KO conocido de F-051**: `cierre.v_pbi_planif_vs_real`, 204 combinaciones / 472 filas, renglón BENEFICIO; 43 sin contradicción | sí, 30-ago, mismas cifras |
| `check-cierres --timeout 1800` (20 min, solo) | **0 discrepancias** en 8.552 cierres candidatos / 8.531 publicados de 679 pares obra/ámbito; telescopio R16: 254.388 series, **0 sin cuadrar**, 18.592 apartadas por hueco de origen. (El primer intento con 900 s murió por `QueryCanceled` porque corría a la vez que `check-unicidad`: culpa del guion, no de la base) | sí: el 04-sep dio 0 y 0 sobre 8.540 / 254.236 |

`check-unicidad` dejó **dos** vistas sin comprobar por timeout
(`mart.v_master_vigente_anual`, que ya era un «no lo sabemos» permanente, y
`mart.v_master_versiones_tipadas`, que esta vez corría en paralelo con
`check-cierres`).

### T1 · El peso real — MEDIDO el 2026-09-05, 23:40-23:47 UTC (7 min en B2s)

Sobre `_meta.obra_build` ya poblada por `hamsh8o` (la del 04 no valía: R18
mandaba reconstruir las 920). Con `PG_VENTANA_ACTIVA=true` en la shell y
`completa=False`:

| conjunto | obras | peso (`SQL_PESOS_PLAN_MENSUAL`) |
|---|---|---|
| a reconstruir | 592 (40 `ventana` + 552 `sin_filas`) | **30.534.657** |
| de ellas, las 552 `sin_filas` | 552 | **24.697** (el 0,08 %) |
| congeladas | 328 | **44.395.641** |
| **AHORRO** | | **59,2 %** (criterio de parada: < 40 %) |

Dos lecturas. (1) **No hay que parar**: el ahorro medido es del 59,2 %, por
debajo del 73,3 % que estimaba §3 —el proxy no cubría los ámbitos master 8 y
11, y las obras vivas tienen mucho master— pero muy por encima del umbral. (2)
**Las 552 obras `sin_filas` no pesan nada** (24.697 de 74,9 M): R18 se queda
como está, no hace falta distinguir «sin filas porque no las tiene» de «sin
construir». La duda que dejó T28 queda cerrada.

### T2b · Cuánto cuesta la firma — MEDIDO el 2026-09-05, 23:47-23:52 UTC (B2s)

| variante | tiempo | obras |
|---|---|---|
| barata, `SQL_FIRMA_ORIGEN` (la que corre cada noche) | **110,7 s** | 920 (sale de `raw.obr`) |
| cara, `SQL_FIRMA_ORIGEN_CON_PLANIF` (`md5(string_agg(planif))`) | **186,1 s** | 728 (solo las que tienen filas en `obrparpre`) |

Ojo con la lectura: la cara **no sustituye** a la barata, **se le añade**. Solo
agrega `raw.obrparpre` (por eso 728 obras y no 920): en producción sería la
barata más un `LEFT JOIN` con este hash por `obra_id`, y su precio es **~3
minutos más por noche en el B2s**; en el B1ms, con 10 MiB/s de techo, cabe
esperar el doble o el triple. Sobre unas 4 h de nocturna es asumible en
tiempo; lo que compra es cerrar la laguna de R20 (un cambio de planificación
pura, sin mover cantidades ni precios, hoy no cambia la firma y espera al
domingo). **Decisión pendiente del humano**: implantarla es código (sumar
`pre_planif` a `COLUMNAS_FIRMA_ORIGEN` y al SQL, con su test), y cambiar la
firma provoca una reconstrucción completa la primera noche, como avisa el
propio código. Si se implanta, va como tarea nueva con su spec, no en la
fase 7.

### Sigue sin medirse

**T31b, T33 y T34**: las tres necesitan nocturnas acotadas, y la primera será
la del lunes 07 (el domingo toca completa por R25). T1 y T2b, medidas arriba
el 05-sep.

### Cinco tests que dependían del día real — arreglados el 2026-09-06

Los domingos `bash harness/init.sh` salía en rojo: cinco tests de
`tests/test_f025_build.py` (`r9_sin_obras_que_reconstruir_no_se_toca_nada`,
`r9_con_el_conjunto_vacio_las_congeladas_igual_se_registran`,
`r6_el_presupuesto_tambien_se_acota`,
`r30_el_paso_registra_cuantas_reconstruye_y_cuantas_congela` y
`r10_las_sobrantes_solo_se_miran_en_la_reconstruccion_completa`) daban por
hecho un día laborable y no fijaban la fecha, así que R25 les mandaba
reconstrucción completa y las cuentas de obras reconstruidas/congeladas no
cuadraban. Arreglado **en los tests**: el auxiliar `ejecutar` congela ahora la
fecha en el jueves 2026-09-03 mediante una subclase de `datetime`, con un
parámetro `ahora` para pedir otro día, y se añadió
`test_f025_r25_el_domingo_se_reconstruye_todo` que ejercita el domingo a
propósito. **El step no cambia**: sigue tomando la fecha real con
`datetime.utcnow()`, que es lo correcto en producción.
