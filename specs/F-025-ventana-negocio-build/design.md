<!-- specs/F-025-ventana-negocio-build/design.md -->
# F-025 · Diseño · Acotar el build a lo que se mueve, sin borrar lo demás

> Se lee **después** de `requirements.md`. Mediciones y consultas exactas en
> `mediciones.md`; **decisiones del humano, cerradas el 2026-09-02**, en
> `decisiones.md`. Sustituye al diseño del 2026-08-28 (commit `1f01718`).

## 1 · La idea, y lo que de verdad cuesta

**La maquinaria de construir por subconjunto de obras YA EXISTE.** F-019 la puso en
producción hace un mes: el marcador `/*F019_FILTRO_OBRAS*/` está en las líneas
**211 y 372** de `08_plan_mensual.sql`, `build_stg_step.py:54` lo sustituye por las
obras del tramo, y la equivalencia por obra es **estructural**: ninguna ventana del
fichero cruza obras. **Acotar es darle otro conjunto de obras, no escribir SQL
nuevo.** El trabajo real son otras tres cosas:

| | Qué | Dónde vive hoy |
|---|---|---|
| **(a)** Elegir el conjunto que se reconstruye | no existe |
| **(b)** Escribir **sin borrar lo que no se reconstruye** | `TRUNCATE` global en `build_stg_step._build_plan_mensual_por_tramos`, vía `postgres_client.truncate_table` |
| **(c)** Llevar el troceado a `06_presupuesto.sql` | solo `08_plan_mensual.sql` lo tiene |

**(b) es el corazón.** El `TRUNCATE` de `plan_mensual` **no está dentro del SQL
troceado**: se lanza **una vez, antes de los 60 tramos** (en el log del job
fallido, `table_truncated` a las 03:23). Pasarle solo las obras vivas al troceado
de hoy **vaciaría la tabla y dejaría 40 obras**, que es lo que el humano prohíbe.

## 2 · Cómo se escribe: el borrado se DERIVA de lo que se escribe

Propuesta del humano (2026-09-02) y **recomendación de este diseño**: *«en lugar
de borrar la BBDD que hay cuando se lanza el proceso, se pisa solo lo que se ha
generado nuevo»*. Por tramo, dentro de **la misma transacción** que ya existe:

```sql
DELETE FROM stg.plan_mensual WHERE obra_id = ANY (ARRAY[...]::BIGINT[]);
INSERT INTO stg.plan_mensual ... AND pp.obra_id = ANY (ARRAY[...]::BIGINT[]);
```

y **desaparece el `TRUNCATE` global** para esta tabla. Tres propiedades, y ninguna
es cosmética:

1. **Autoconsistencia.** El conjunto que se borra **es** el que se va a escribir:
   no hay dos listas que puedan desincronizarse, y es imposible borrar una obra que
   luego no se reescriba.
2. **Cada tramo queda atómico e idempotente.** Si el proceso muere, los hechos están
   al día y **los que faltan conservan el dato de anoche**: coherente, no truncada.
3. **Repara de paso la avería**: la nocturna del 02-sep habría acabado con 5 obras
   al día y el resto con el dato de ayer, en vez de al 21,6 %. **Vale por sí solo
   aunque el acotado no ahorrase nada.**

**El `DELETE` va por índice**: `idx_plan_mensual_obra_amb (obra_id, ambito_id)` y
`idx_pres_obra_amb` empiezan por `obra_id`, así que no barren la tabla. No hay
índices que crear.

**Y lo mismo en `06_presupuesto.sql`** (DA-2): se le añade el marcador
`/*F025_FILTRO_OBRAS*/` en su `WHERE`, se sustituye su `TRUNCATE` por el `DELETE`
derivado y se ejecuta en una pasada con las obras vivas —no necesita tramos: no
tiene ventanas ni explosión, y el volumen filtrado es pequeño—. Su `DISTINCT ON
(obride, paride, amb, fas)` empieza por la obra, así que **el corte por obra es
igual de seguro** que en `plan_mensual`.

### Alternativas descartadas

| | Alternativa | Por qué no |
|---|---|---|
| (b) | Tabla de trabajo nueva + intercambio | Copiar las ~22 M filas conservadas cuesta en I/O casi lo que reconstruirlas y **duplica el disco** del servidor donde ya hubo un incidente (F-019) |
| (c) | Particionar `plan_mensual` por obra (687 particiones) | Evitaría el bloat con `TRUNCATE` de partición, pero exige recrear la tabla y todas sus vistas y `GRANT`, y 687 particiones en un `B1ms` encarecen la planificación. **Anotada como salida** si el bloat resulta insostenible |
| (d) | Partición `viva`/`cerrada`, o borrar el histórico fuera de la ventana | La primera hace caro el caso frecuente (mover filas al cambiar de estado); la segunda le quita informes a Power BI y el humano la **prohibió** |

## 3 · Quién decide qué se reconstruye

**El criterio lo fijó el humano** (DA-1, tres reglas en unión: estado **EN ESTUDIO
(1), NO PRESENTADA (11) o CERRADA (25)**, código de seis dígitos, o sin actividad en
12 meses → **880 congeladas, 40 vivas**). Los estados salen de `conest` tipo 42, ya
verificado. Es regla de negocio: va en `config/business_rules.yaml` y se evalúa en
dominio puro. Por encima, dos mecanismos que **solo añaden obras** a la lista:

1. **Sello del SQL** (R17): `sha256` de `08_plan_mensual.sql`, `06_presupuesto.sql`
   y los parámetros del build. Si el sello registrado de una obra no es el vigente,
   entra. Un arreglo de SQL como el de F-052 reconstruye **todas**, y por eso ningún
   cambio de código se queda a medio aplicar.
2. **Obra sin construir** (R18): sin filas en `stg.plan_mensual` o
   `stg.presupuesto`, o sin registro. Completar no es actualizar.

### 3.1 · La firma del origen: DENUNCIA, no rescate

La decisión del humano congela **40 obras con actividad reciente** (39 CERRADAS —36 de
ellas por el cierre anual de 2025-12— y 1 por código) y acepta hasta **6 días** de
antigüedad. Por eso la firma no puede reconstruirlas por su cuenta: **rescatarlas
contradiría la decisión**. Su papel es que **eso no pase en silencio** —el modo de
fallo de F-052—: detecta que una obra congelada cambió en el origen y **la nombra**
(R26); el domingo la pone al día. El interruptor `PG_VENTANA_RESCATE` (default
**off**) convierte la denuncia en reconstrucción si el humano cambia de idea.

### 3.2 · De dónde sale la señal, ahora que `stg.presupuesto` se acota

DA-2 rompe el plan original: `stg.presupuesto` era la fuente barata de la señal y
deja de reconstruirse entera. Alternativas evaluadas:

| | Alternativa | Veredicto |
|---|---|---|
| **(A)** | **Agregados por obra sobre `raw`**, en un sub-paso propio de solo lectura **después de `ingest_raw`** | **Elegida.** `raw` es lo único que la ingesta sigue trayendo completo cada noche (`--full`, `TRUNCATE` + `COPY`). Es una agregación por hash, sin ventanas: **no derrama a temporales**, que es lo que reventó el disco en F-019 |
| (B) | Hashear cada fila **en la ingesta**, en memoria | No añade E/S, pero gasta **CPU en Python sobre 13,8 M filas**, y la CPU es justo el recurso agotado. Descartada salvo que (A) se mida cara |
| (C) | `tiemod` como watermark | **Imposible**: F-011 lo midió contra el catálogo de Sigrid — no existe en 24 de las 31 tablas, `obrparpre` incluida, y las fechas que hay son de negocio |
| (D) | Tabla de firmas mantenida aparte | No resuelve nada: sigue faltando de dónde sale el valor |

**La firma (A), en concreto:** por `obride`, sobre `raw.obrparpre` (`count(*)`,
`sum(can)`, `sum(pre)`, `sum(impcoe)`, `max(fas)`), `raw.obrparpar` y `raw.obrfas`
(recuentos y máximos). Las dos últimas son pequeñas; la primera es el coste.

**Lo que hay que medir antes de fijarla (T2b):** el scan agregado de `raw.obrparpre`.
Es de solo lectura, sin temporales, y sustituye a un paso que hoy lee esa misma tabla
**y además escribe 13,8 M filas**. Dos variantes: sin `planif` (barata, deja fuera
los cambios de planificación pura) o con `md5(planif)` (cubre el master, pero
detoasta un texto largo). **Se implementa la barata y se mide la cara.** La laguna
que quede se declara en el diccionario y la cierra el domingo (R25).

## 4 · Dónde se guarda lo que se sabe de cada obra

**Tabla nueva `_meta.obra_build`** (una fila por obra) en `sql/ddl/00_meta.sql`,
que ya se ejecuta en el bootstrap de la conexión:

| Columna | Para qué |
|---|---|
| `obra_id`, `codigo_obra` | identidad |
| `firma_origen`, `sello_sql` | lo comparado en §3 |
| `batch_id`, `construido_at`, `filas` | de qué ejecución viene lo construido |
| `motivo` | `sello`, `firma`, `ventana`, `sin_filas`, `completa` |

Y la vista **`_meta.v_frescura_obra`**, hermana de `v_frescura`: obra, fecha de su
última construcción, si está congelada y por qué. Es la respuesta consultable a «¿de
cuándo es el dato de esta obra?» (R14), y la leen igual el MCP y Power BI.

## 5 · Reparto por capas

| Capa | Qué se añade |
|---|---|
| `domain/ventana.py` | `clasificar_obras(estados, criterio, hoy) -> Plan` — **función pura**, sin conexión. Devuelve obras a reconstruir, obras congeladas y **el motivo de cada una** |
| `domain/ventana.py` | `firma_de_obra(...)` y `sello_sql(textos, params)`: cálculo determinista, testable con fixtures |
| `application/steps/ingest_raw_step.py` | Sub-paso `firma_origen`: calcula la firma sobre `raw` recién cargado y la guarda (§3.2) |
| `application/steps/build_stg_step.py` | Compone el plan, borra+inserta por obra en `06` y por tramo en `08`, escribe `_meta.obra_build` y los recuentos de `_meta.etl_runs` |
| `infrastructure/postgres/postgres_client.py` | `fetch_estado_obras()`, `fetch_firma_origen()`, `borrar_obras_de()` y el upsert del registro. SQL como constante de módulo, al estilo de `SQL_PESOS_PLAN_MENSUAL` |
| `infrastructure/postgres/ventana_sql.py` | Texto de las consultas del guardián, **sin abrir conexión** (patrón de `unicidad_sql.py` y `cobertura`) |
| `main.py` | `ventana-plan` (dry-run: qué se reconstruiría y qué se congelaría, con peso), `check-ventana` y el flag `--reconstruir-todo` de `run-all` y `stage` |

**Configuración** (`config/settings.py`, sin secretos): `PG_VENTANA_ACTIVA`
(default **false**, R5), `PG_VENTANA_MESES` (12), `PG_VENTANA_DIA_COMPLETA`
(domingo) y `PG_VENTANA_RESCATE` (default **off**, §3.1). Las tres reglas de DA-1
—estados que congelan, patrón de código, meses— se declaran en
`config/business_rules.yaml`: cambiarlas no debe tocar código.

## 6 · Orden de operaciones y puertas existentes

- **La puerta de coherencia de `raw` (F-024) sigue siendo lo primero**, antes de
  pre-flight y de cualquier escritura. Su razón de ser era que un `TRUNCATE` ya
  ejecutado no se deshace; con §2 el daño posible es menor, pero la puerta no se
  toca.
- **La puerta de disco de F-019 se mantiene delante de cada tramo**, y ahora vigila
  además el crecimiento por tuplas muertas (§9).
- **La firma se calcula tras `ingest_raw`**, sobre `raw` recién cargado, y **el
  plan de obras antes de `06_presupuesto.sql`**, que es el primer sub-paso acotado.
- **`build_mart` no cambia**: sigue exigiendo que la última fila de `build_stg%`
  sea el paso completo, y construye desde un `stg` completo.

## 7 · La prueba de equivalencia

Las **cuatro huellas de F-052** (`stg`, `mart`, `dimension`, `cierre`), antes y
después **sobre el mismo `raw`**. La diferencia con F-052 es que aquí **no hay obras
esperadas**: si la exclusión es correcta salen **idénticas al byte** en todas las
obras, y cualquier diferencia detiene la feature.

**Quinta huella nueva (R22)**, en `huella_ampliada.py`: `plan_obra` = filas y
`sum(importe_origen)` por **obra × ámbito**. Demuestra obra a obra que lo congelado
no se ha movido, que es literalmente lo que pidió el humano.

**Prueba de negocio obligatoria (R12):** `cierre.v_pbi_cierre_resumen` de la
**0599**, obra congelada por el criterio, debe seguir publicando DIRECTOS
**2.624.793 €**, coste **3.994.386 €** y margen **1,8 %** —las cifras que F-052
acaba de dejar buenas—.

## 8 · La red de seguridad

- **Reconstrucción completa semanal, los DOMINGOS (R25, DA-4).** `run-all` mira la
  última reconstrucción completa registrada y, si toca, rehace **todas** las obras
  esa noche. **No hace falta un job nuevo ni tocar el cron**, que es lo que lo hace
  difícil de olvidar. Contrapartida: esa noche cuesta lo que cuesta hoy.
- **`check-ventana` (R26, R27).** Solo lectura, al final de `run-all`, **avisa y no
  bloquea**, marcador `[F025-VENTANA-KO]`, `SET LOCAL statement_timeout` en cada
  consulta. A mano devuelve código distinto de 0.
- **La alerta.** `infra/97_create_alert_ventana.ps1`, hermano del
  `96_create_alert_cobertura.ps1` de F-052, sobre `log-datamart-seg-dev` y el grupo
  de acción `ag-datamart-seg-dev`. **Ninguna dirección de correo entra en el
  repositorio.** Despliegue manual del humano; sin él, el guardián es mudo.

## 9 · Riesgos

1. **Bloat y `autovacuum`.** El `DELETE` deja tuplas muertas cada noche en un
   `B1ms` sin créditos. Mitigación: `VACUUM (ANALYZE)` de las dos tablas al terminar
   —fuera de transacción, en autocommit— y medir `pg_total_relation_size` durante la
   primera semana. **Si crece de forma sostenida, la salida es el particionado
   (§2c).** Es un riesgo a **medir**: la puerta de disco de F-019 cubre entretanto.
2. **Transacciones grandes por tramo.** Ya hay tramos por encima del millón de filas
   y el `DELETE` añade WAL. Mitigación: bajar `PG_TRAMO_MAX_FILAS`, que el
   planificador ya admite sin tocar código.
3. **40 obras vivas congeladas** (R3). Es la decisión del humano, no un defecto,
   pero su dato puede llevar hasta 6 días de retraso. Mitigación: la firma las
   **nombra** cada noche (§3.1) y el domingo las pone al día.
4. **Que la ventana esconda un fallo del build.** Una obra congelada no vuelve a
   pasar por el SQL, así que un error nuevo solo se vería en las vivas. Lo cubre el
   sello del SQL (R17): cambiar el fichero reconstruye todo.
5. **Coste de la firma sobre `raw`** (§3.2): un scan de 13,8 M filas cada noche. Se
   mide en T3 antes de fijarla; si sale cara, se recorta y la laguna se declara.
6. **Créditos de CPU.** La nocturna acotada debe dejar crédito (R29). El domingo
   **volverá a consumirlos**, y por eso la reconstrucción completa va en domingo.

## 10 · Ficheros

**Se crean:** `etl_sigrid/domain/ventana.py`,
`etl_sigrid/infrastructure/postgres/ventana_sql.py`,
`infra/97_create_alert_ventana.ps1`, `tests/test_f025_*.py`.

**Se modifican:** `sql/ddl/00_meta.sql` (tabla y vista), `build_stg_step.py` (plan,
borrado derivado, registro, aborto), `ingest_raw_step.py` (firma),
`postgres_client.py` (consultas nuevas; `truncate_table` deja de usarse para las dos
tablas), `huella_ampliada.py` (quinta huella), `main.py` (dos comandos y un flag),
`config/settings.py`, `config/business_rules.yaml`,
`config/diccionario/{_meta,stg,maestro}.yaml` —en `maestro`, los catorce estados de
`conest` con su nombre (R4, enlaza con F-054)— y `00_global.yaml`,
`docs/ARCHITECTURE.md` y `azure-apps/datamart_seg_anual.md`.

También `sql/stg/06_presupuesto.sql`: marcador de filtro nuevo y `TRUNCATE`
sustituido por el `DELETE` derivado (DA-2). Ni una línea de su lógica cambia.

**Que NO se tocan:** la **lógica** de `08_plan_mensual.sql` —su marcador ya está—;
`sql/stg/00..05` y `07`; `sql/mart/**` y `sql/cierre/**`; `domain/tramos.py`; la
puerta de coherencia de F-024; y `stg.obras.activa`, que llega a Power BI.

## 11 · Decisiones, cerradas por el humano el 2026-09-02

Detalle y censo en **`decisiones.md`**.

| | Decisión |
|---|---|
| **DA-1** | Criterio: **estado 1, 11 o 25 · código de seis dígitos · sin actividad en 12 meses**, en unión. **880 congeladas, 40 vivas.** El humano **rechazó** el veto de actividad y la formulación en positivo, las dos con el dato y la ventaja delante |
| **DA-1 bis** | Catálogo de estados **verificado** (`conest`, tipo 42): «25 = CERRADA» es un hecho. Queda documentarlo en el diccionario |
| **DA-2** | **Sí** se acota `build_presupuesto`. Obliga a mover la firma a `raw` (§3.2) |
| **DA-3** | **Sí** se congelan las administrativas: **222 obras de seis dígitos, 0 llegan al fact** |
| **DA-4** | Reconstrucción completa **semanal, los domingos**, disparada desde `run-all` |
| **DA-5** | *(Sin pronunciamiento; recomendación no contradicha.)* El guardián **avisa y no bloquea** |
| **DA-6** | *(Sin pronunciamiento; recomendación no contradicha.)* Campaña de mutación sobre `domain/ventana.py` **además** de las cinco huellas |
