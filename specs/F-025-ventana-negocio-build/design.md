<!-- specs/F-025-ventana-negocio-build/design.md -->
# F-025 · Diseño · Acotar el build a lo que se mueve, sin borrar lo demás

> Se lee **después** de `requirements.md`. Mediciones y consultas exactas en
> `mediciones.md`; opciones abiertas y recomendaciones en `decisiones.md`.
> Sustituye al diseño del 2026-08-28 (commit `1f01718`), anterior a la decisión
> del humano y a la avería del 2026-09-02.

## 1 · La idea, y lo que de verdad cuesta

**La maquinaria de construir por subconjunto de obras YA EXISTE.** F-019 la puso
en producción hace un mes: el marcador `/*F019_FILTRO_OBRAS*/` está en las líneas
**211 y 372** de `08_plan_mensual.sql`, `build_stg_step.py:54` lo sustituye por
las obras del tramo, `huella_obras.py:129` hace lo mismo para las huellas, y la
equivalencia por obra es **estructural**: ninguna ventana del fichero cruza obras.
**Acotar el build es darle otro conjunto de obras, no escribir SQL nuevo.** Es lo
que hace esta feature abordable.

El trabajo real son otras tres cosas:

| | Qué | Dónde vive hoy |
|---|---|---|
| **(a)** Elegir el conjunto que se reconstruye | no existe |
| **(b)** Escribir **sin borrar lo que no se reconstruye** | `TRUNCATE` global en `build_stg_step._build_plan_mensual_por_tramos`, vía `postgres_client.truncate_table` |
| **(c)** Decidir hasta dónde llega el troceado | solo `08_plan_mensual.sql` lo tiene |

**(b) es el corazón.** El `TRUNCATE` **no está dentro del SQL troceado**: se
lanza **una vez, antes de los 60 tramos** (en el log del job fallido,
`table_truncated` a las 03:23 y los tramos después). Pasarle solo las obras vivas
al troceado de hoy **vaciaría la tabla y dejaría 44 obras**, que es exactamente lo
que el humano prohíbe.

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

1. **Autoconsistencia.** No hay dos listas que puedan desincronizarse: el conjunto
   que se borra **es** el que se va a escribir. Es imposible borrar una obra que
   luego no se reescriba, que es el fallo que hay que hacer imposible.
2. **Cada tramo queda atómico e idempotente.** Si el proceso muere, los tramos
   hechos están al día y **los que faltan conservan el dato de la noche anterior**:
   la tabla queda coherente y consultable, no truncada.
3. **Repara de paso la avería.** Con este esquema, la nocturna del 2026-09-02
   habría acabado con 5 obras al día y 682 con el dato de ayer, en vez de al
   21,6 %. **Este beneficio vale por sí solo aunque el acotado no ahorrase nada**,
   y abre la puerta a reanudar una carga interrumpida, hoy imposible.

**El `DELETE` va por índice**: `idx_plan_mensual_obra_amb (obra_id, ambito_id)`
(`sql/stg/01_ddl.sql:227`) empieza por `obra_id`, así que no barre la tabla. No
hay índices que crear.

### Alternativas descartadas

| | Alternativa | Por qué no |
|---|---|---|
| (b) | Tabla de trabajo nueva + intercambio | Copiar las ~22 M filas conservadas cuesta en I/O casi lo que reconstruirlas y **duplica el disco** del servidor donde ya hubo un incidente (F-019) |
| (c) | Particionar `plan_mensual` por obra (687 particiones) | Evitaría el bloat con `TRUNCATE` de partición, pero exige recrear la tabla y todas sus vistas y `GRANT`, y 687 particiones en un `B1ms` encarecen la planificación. **Anotada como salida** si el bloat resulta insostenible |
| (d) | Partición `viva`/`cerrada` | Cada obra que cambia de estado obliga a mover sus filas de partición: el caso frecuente es el caro |
| (e) | Borrar el histórico fuera de la ventana | Es la opción «contenido» de la spec vieja: Power BI pierde informes. **Prohibida** por el humano |

## 3 · Cómo se elige el conjunto: criterio, firma y sello

Tres filtros, evaluados en este orden. **Cualquiera de los tres puede meter una
obra en la lista de reconstruir; ninguno la puede sacar.** La duda siempre se
resuelve reconstruyendo (R19).

1. **Sello del SQL** (R17). `sha256` del texto de `08_plan_mensual.sql` más los
   parámetros del build. Si el sello registrado de una obra no es el vigente, esa
   obra entra. Un cambio de SQL como el de F-052 reconstruye **las 687**.
2. **Firma del origen** (R16). Por obra, agregados de `stg.presupuesto` y
   `stg.fases` —las dos se reconstruyen enteras cada noche, antes que
   `plan_mensual`: `count(*)`, `sum(importe)`, `sum(cantidad)`, `max(fase_num)`,
   `count` y `max(numero_fase)` de fases. Si no coincide con la registrada, entra.
3. **Criterio de ventana** (R2–R4). Última fase cerrada y veto por estado de
   Sigrid. Es una **heurística de ahorro**, no la garantía de corrección: la
   garantía es la firma.

**Por qué la firma y no `tiemod`:** F-011 midió que `tiemod` **no existe** en 24 de
las 31 tablas de Sigrid, `obrparpre` incluida, y las fechas que sí hay son de
negocio, no de modificación. La firma se calcula sobre datos que el ETL ya
reconstruye esa misma noche, así que **no añade lectura de `raw`**.

**Laguna declarada (R20):** la firma no cubre `raw.obrparpre.planif`, la cadena que
explotan los ámbitos master. Hashearla obliga a leer un texto largo de 13,8 M filas
—lo que se quiere ahorrar—. Un cambio de planificación en una obra congelada sin
tocar cantidades ni precios tarda como mucho una cadencia en verse (R25).

## 4 · Dónde se guarda lo que se sabe de cada obra

**Tabla nueva `_meta.obra_build`** (una fila por obra), creada en
`sql/ddl/00_meta.sql`, que ya se ejecuta en el bootstrap de la conexión:

| Columna | Para qué |
|---|---|
| `obra_id`, `codigo_obra` | identidad |
| `firma_origen`, `sello_sql` | lo comparado en §3 |
| `batch_id`, `construido_at`, `filas` | de qué ejecución viene lo construido |
| `motivo` | `sello`, `firma`, `ventana`, `sin_filas`, `completa` |

Y la vista **`_meta.v_frescura_obra`**, hermana de `v_frescura`: obra, fecha de su
última construcción, si está congelada y por qué. Es la respuesta consultable a
«¿de cuándo es el dato de esta obra?» (R14), y la lee igual el MCP que Power BI.
`_meta.etl_runs` sigue registrando el paso; lo nuevo es el detalle por obra.

## 5 · Reparto por capas

| Capa | Qué se añade |
|---|---|
| `domain/ventana.py` | `clasificar_obras(estados, criterio, hoy) -> Plan` — **función pura**, sin conexión. Devuelve obras a reconstruir, obras congeladas y **el motivo de cada una** |
| `domain/ventana.py` | `firma_de_obra(...)` y `sello_sql(texto, params)`: cálculo determinista, testable con fixtures |
| `application/steps/build_stg_step.py` | Compone el plan, borra+inserta por tramo, escribe `_meta.obra_build` y registra recuentos en `_meta.etl_runs` |
| `infrastructure/postgres/postgres_client.py` | `fetch_estado_obras()` (una consulta agregada), `borrar_obras_de_plan_mensual()` y el upsert del registro. Todo SQL como constante de módulo, al estilo de `SQL_PESOS_PLAN_MENSUAL` |
| `infrastructure/postgres/ventana_sql.py` | Texto de las consultas del guardián, **sin abrir conexión** (patrón de `unicidad_sql.py` y `cobertura`) |
| `main.py` | `ventana-plan` (dry-run: qué se reconstruiría y qué se congelaría, con peso), `check-ventana` y el flag `--reconstruir-todo` de `run-all` y `stage` |

**Configuración** (`config/settings.py`, sin secretos): `PG_VENTANA_ACTIVA`
(default **false**, R5), `PG_VENTANA_MESES` (12), `PG_VENTANA_DIAS_COMPLETA` (7).
El criterio de negocio —meses y estados con veto— se declara en
`config/business_rules.yaml`, como preveía la spec del 2026-08-28: cambiarlo no
debe tocar código.

## 6 · Orden de operaciones y puertas existentes

- **La puerta de coherencia de `raw` (F-024) sigue siendo lo primero**, antes de
  pre-flight y de cualquier escritura. Su razón de ser era que un `TRUNCATE` ya
  ejecutado no se deshace; con §2 el daño posible es menor, pero la puerta no se
  toca.
- **La puerta de disco de F-019 se mantiene delante de cada tramo**, y ahora vigila
  además el crecimiento por tuplas muertas (§9).
- **El plan de obras se calcula después de los sub-pasos `00`–`07`**: la firma se
  lee de `stg.presupuesto` y `stg.fases` **ya reconstruidas esa noche**.
- **`build_mart` no cambia**: sigue exigiendo que la última fila de `build_stg%`
  sea el paso completo, y construye desde una `stg.plan_mensual` completa.

## 7 · La prueba de equivalencia

Las **cuatro huellas de F-052** (`stg`, `mart`, `dimension`, `cierre`), capturadas
antes y después **sobre el mismo `raw`** y comparadas con `comparar-huellas`. La
diferencia con F-052 es que aquí **no hay obras esperadas**: si la exclusión es
correcta, las cuatro salen **idénticas al byte**, en todas las obras. Cualquier
diferencia detiene la feature.

**Quinta huella nueva (R22)**, en `huella_ampliada.py` con el patrón ya existente:
`plan_obra` = filas y `sum(importe_origen)` por **obra × ámbito** de
`stg.plan_mensual` completa. Es la que demuestra obra a obra que lo congelado no se
ha movido, y la que responde literalmente al criterio del humano: *el recuento de
filas por obra de las obras excluidas debe ser idéntico*.

**Prueba de negocio obligatoria (R12):** `cierre.v_pbi_cierre_resumen` de la
**0599**, obra congelada por el criterio, debe seguir publicando DIRECTOS
**2.624.793 €**, coste **3.994.386 €** y margen **1,8 %** —las cifras que F-052
acaba de dejar buenas—.

## 8 · La red de seguridad

- **Reconstrucción completa periódica (R25).** `run-all` mira la última
  reconstrucción completa registrada; si es más vieja que `PG_VENTANA_DIAS_COMPLETA`
  reconstruye las 687 obras esa noche. **No hace falta un job nuevo ni tocar el
  cron**, que es lo que lo hace difícil de olvidar. Contrapartida: esa noche cuesta
  lo que cuesta hoy, así que la cadencia y el día son decisión del humano (DA-4).
- **`check-ventana` (R26, R27).** Solo lectura, al final de `run-all`, **avisa y no
  bloquea**, marcador `[F025-VENTANA-KO]`, `SET LOCAL statement_timeout` en cada
  consulta. A mano devuelve código distinto de 0.
- **La alerta.** `infra/97_create_alert_ventana.ps1`, hermano del
  `96_create_alert_cobertura.ps1` de F-052, sobre `log-datamart-seg-dev` y el grupo
  de acción `ag-datamart-seg-dev`. **Ninguna dirección de correo entra en el
  repositorio.** Despliegue manual del humano; sin él, el guardián es mudo.

## 9 · Riesgos

1. **Bloat y `autovacuum`.** El `DELETE` deja tuplas muertas: con ~26 % del peso
   reconstruido son del orden de 7-8 M filas muertas por noche en un `B1ms` sin
   créditos. Mitigación: `VACUUM (ANALYZE) stg.plan_mensual` al terminar el
   sub-paso —fuera de transacción, con conexión en autocommit— y medición de
   `pg_total_relation_size` antes y después durante la primera semana. **Si el
   tamaño crece de forma sostenida, la salida es el particionado (§2c).** Es un
   riesgo a **medir**, no a suponer: la puerta de disco de F-019 lo cubre mientras
   tanto.
2. **Transacciones grandes por tramo.** Ya hay tramos que superan el millón de
   filas (`plan_mensual_tramo_sobredimensionado` en el log). El `DELETE` añade WAL
   a esa transacción. Mitigación: bajar `PG_TRAMO_MAX_FILAS` si la primera medición
   lo pide; el planificador de tramos ya lo admite sin tocar código.
3. **Congelar una obra que sí se movía.** Lo cubre la firma (§3), y su peor caso es
   reconstruir de más. El caso que la firma no ve es `planif` (R20).
4. **Que la ventana esconda un fallo del build.** Una obra congelada no vuelve a
   pasar por el SQL, así que un error nuevo solo se vería en las vivas. Lo cubre el
   sello del SQL (R17): cambiar el fichero reconstruye todo.
5. **Créditos de CPU.** La nocturna acotada debe dejar crédito (R29). La noche de
   la reconstrucción completa **volverá a consumirlos**, y por eso su día importa.

## 10 · Ficheros

**Se crean:** `etl_sigrid/domain/ventana.py`,
`etl_sigrid/infrastructure/postgres/ventana_sql.py`,
`infra/97_create_alert_ventana.ps1`, `tests/test_f025_*.py`.

**Se modifican:** `sql/ddl/00_meta.sql` (tabla y vista nuevas),
`application/steps/build_stg_step.py` (plan, borrado por tramo, registro, aborto),
`infrastructure/postgres/postgres_client.py` (consultas nuevas; `truncate_table`
**no** se usa ya para `plan_mensual`),
`infrastructure/postgres/huella_ampliada.py` (quinta huella), `main.py` (dos
comandos y un flag), `config/settings.py`, `config/business_rules.yaml`,
`config/diccionario/{_meta,stg}.yaml` y `00_global.yaml`, `docs/ARCHITECTURE.md`,
`azure-apps/datamart_seg_anual.md`.

**Que NO se tocan:** `sql/stg/08_plan_mensual.sql` —ni una línea de lógica: el
marcador de F-019 ya está—; `sql/stg/03..07` y `sql/mart/**` y `sql/cierre/**`;
`domain/tramos.py`; la puerta de coherencia de F-024; y `stg.obras.activa`, que
llega a Power BI y hoy es `TRUE` para todas (DA-5 de la spec vieja: no se toca).

## 11 · Decisiones abiertas (las cierra el humano)

Detalle, opciones y censo medido en **`decisiones.md`**. Resumen:

| | Decisión | Recomendación |
|---|---|---|
| **DA-1** | Criterio de obra cerrada | Actividad a **12 meses** + veto de EN CURSO; la marca de Sigrid sola falla en los dos sentidos |
| **DA-2** | ¿Se acota `build_presupuesto` (13,8 M filas)? | **No**: es la fuente de la firma |
| **DA-3** | ¿Se congelan también las ~104 obras del build que no llegan al fact? | **Sí**, como congeladas permanentes: mismo mecanismo, sin borrar nada |
| **DA-4** | Cadencia y día de la reconstrucción completa | **Semanal**, sábado; revisable a mensual con el guardián en verde |
| **DA-5** | ¿Bloqueo o aviso si el guardián encuentra algo? | **Avisa**, como F-052 |
| **DA-6** | ¿Se exime la campaña de mutación a cambio de las cinco huellas? | Decisión del humano; el dominio nuevo **sí** es mutable y conviene cubrirlo |
