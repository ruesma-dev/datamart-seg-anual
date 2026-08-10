<!-- specs/F-019-plan-mensual-por-tramos/design.md -->
# F-019 · Build de stg.plan_mensual por tramos — Diseño técnico

## 1 · Contexto y causa raíz (por qué existe esta feature)

`stg/08_plan_mensual.sql` es un único statement `WITH ... INSERT` que:

1. junta `stg.presupuesto` (amb 8/11) con `raw.obrparpre` (13,76 M filas) y
   explota `planif` con `CROSS JOIN LATERAL unnest(string_to_array(...))`;
2. encadena CINCO ventanas (`MAX/COUNT/LAG OVER PARTITION BY
   presupuesto_id`) sobre el resultado explosionado;
3. añade la rama de reales (amb 3/7) con ventanas por
   `(obra_id, partida_id, ambito_id)`.

En el `Standard_B1ms` (2 GB RAM, 1 vCPU, disco de 32 GB compartido con
`albaranes` y `partes` en producción), los sorts de esas ventanas derramaron
**16+ GB de temporales/WAL** en 103 min sin terminar, el disco llegó al
**93,4 %** y Azure puso el servidor en solo-lectura 10 minutos
(2026-08-09). En local no pasa porque sobra RAM.

**Observación estructural que hace posible el troceo**: ninguna ventana del
SQL cruza obras. Todas particionan por `presupuesto_id` (que pertenece a una
única obra) o por `(obra_id, partida_id, ambito_id)`. Por tanto, ejecutar el
mismo statement N veces con un filtro `obra_id = ANY (...)` disjunto y
completo produce, por construcción, **exactamente las mismas filas** que una
pasada única — y el pico de temporales de cada pasada es proporcional al
peso del tramo, no al total.

## 2 · Mediciones

Estimaciones del líder (columna «estimado») a partir del incidente; el
implementer rellena «medido» en T1 con los comandos de R1 y, si la
diferencia cambia alguna constante, lo anota aquí y en el informe.

| Magnitud | Estimado | Medido (T1) |
|---|---|---|
| Filas `raw.obrparpre` | 13,76 M (dato duro) | |
| Filas finales `stg.plan_mensual` | desconocido (medir) | |
| Filas explosionadas rama master | desconocido (medir) | |
| Tamaño físico `stg.plan_mensual` | desconocido (medir) | |
| Derrame del build actual (temp_bytes, local) | ≥16 GB en Azure (cota inferior: no terminó) | |
| Coeficiente derrame/fila | ≥ 16 GB / 13,76 M ≈ **1,2 KB/fila** | |
| Peso de la obra más pesada | desconocido (medir) | |
| Disco Azure: total / usado hoy | 32 GB / 13,5 GB (42,3 %); libres ≈ 18,5 GB | |

### Derivación de las constantes propuestas (a confirmar con «medido»)

- **`PG_TRAMO_MAX_FILAS = 1_000_000`** (peso en filas de `raw.obrparpre`
  atribuibles a las obras del tramo). Con 1,2 KB/fila ⇒ pico transitorio
  estimado **~1,2–2 GB por tramo** y **~14 tramos**. Un pico de 2 GB sobre
  los 18,5 GB libres deja margen ~9×.
- **`PG_DISCO_TOTAL_GB = 32`**, **`PG_DISCO_LIMITE_PCT = 80`** ⇒ techo de
  ocupación **comprometida** 25,6 GB. Encaje con lo que ya existe: la
  puerta de `infra/05_check_prereqs.ps1` aborta el DESPLIEGUE por encima
  del 60 %; esta puerta frena DURANTE el build al 80 %; la protección de
  Azure salta hacia el ~95 % (el incidente tocó 93,4 %). 80 % + pico
  transitorio de ~2 GB ≈ 86 % en el peor caso: por debajo del incidente y
  de la protección, con las otras dos apps aún operativas.

## 3 · Decisiones abiertas (validar el humano ANTES de implementar)

### DA-1 · Corte de troceo: por obra, empaquetado por peso — RECOMENDADO

- **Recomendación**: cortar por `obra_id`, agrupando obras en tramos por
  peso hasta `PG_TRAMO_MAX_FILAS`. Peso de una obra = filas de
  `raw.obrparpre` de sus presupuestos amb 3/7/8/11, ponderando la rama
  master por la longitud del `planif` (nº de posiciones), que es lo que de
  verdad explota. La consulta de pesos es una pasada de agregación sin
  ventanas (derrame despreciable frente al build).
- **Alternativa descartada — por ejercicio**: el horizonte del `planif` de
  una versión master cruza ejercicios (posición 1..N desde `mes_ancla`);
  cortar por ejercicio partiría las particiones de ventana y **rompería la
  equivalencia** (el ffill y el LAG necesitan la serie completa de la
  partida). Inviable, no solo peor.
- **Alternativa descartada — hash de `presupuesto_id`**: equivalente para
  la rama master pero rompería las ventanas de reales, que particionan por
  `(obra_id, partida_id, ambito_id)` agrupando varios `presupuesto_id`
  (uno por fase). Además, ilegible en logs.
- **Variante a decidir dentro de DA-1**: si T1 muestra poca asimetría entre
  obras, el peso puede simplificarse a `COUNT(*)` sin ponderar por longitud
  de planif (consulta más barata cada noche). Default propuesto: ponderado.

### DA-2 · Límite de seguridad de disco y mecánica de medición

- **Recomendación**: medir con
  `SELECT SUM(pg_database_size(datname)) FROM pg_database` y comparar
  contra `PG_DISCO_TOTAL_GB` (32, configurable para no cablear el tamaño
  del servidor). Límite `PG_DISCO_LIMITE_PCT = 80`. Fail-safe: si la
  consulta falla o devuelve NULL ⇒ abortar (R10).
- **Limitación asumida**: `pg_database_size` no cuenta WAL ni logs del
  servidor; el margen 80 %→95 % (≈4,8 GB) los absorbe. La alternativa
  exacta (métrica `storage_percent` vía Azure Monitor) exigiría dar a la
  identidad del job un rol más (`Monitoring Reader`) y credenciales Azure
  en el camino del build: descartada por ampliar superficie; la métrica la
  vigila el humano en R14.
- **Riesgo verificado a favor**: `pg_database_size` sobre otra base exige
  privilegio CONNECT; la frontera medida en F-005 confirma que los roles
  del datamart pueden conectar a `albaranes` (riesgo aceptado entonces,
  ventaja ahora). El pre-check 0 de R14 lo comprueba con el rol real antes
  de lanzar nada.

### DA-3 · Dónde vive la orquestación del troceo — RECOMENDADO: Python

- **Recomendación**: en `build_stg_step.py` (capa application), con el
  planificador como **función pura** en `etl_sigrid/domain/tramos.py`
  (testeable sin BBDD, cero imports de infraestructura) y dos métodos
  nuevos en `PostgresClient` (infra). Cada tramo usa
  `PostgresClient.connection()` ⇒ una transacción por tramo, y entre
  tramos el step ejecuta la puerta de disco.
- **Alternativa descartada — bucle plpgsql (`DO $$`)**: correría todo en
  UNA transacción (el pico y el WAL se apilan, que es el incidente),
  impediría la puerta de disco entre tramos desde fuera, y además
  `postgres_client.py` no sabe trocear bloques `$$` (documentado en
  ARCHITECTURE.md a raíz de `infra/sql/`).
- **Alternativa descartada — script externo**: el build debe seguir siendo
  un sub-paso del pipeline (`run-all` nocturno del job de F-003).

### DA-4 · ¿Sustituye al build actual o convive tras un flag? — RECOMENDADO: sustituye

- **Recomendación**: el camino por tramos es el ÚNICO camino, también en
  local. Motivos: (1) dos caminos divergen (la lección de `sigrid_api.md`
  duplicado); (2) el modo antiguo es exactamente el que tumbó el servidor:
  conservarlo tras un flag es conservar el arma cargada; (3) en local el
  troceo solo añade segundos de overhead; (4) `PG_TRAMO_MAX_FILAS` muy
  grande reproduce el comportamiento antiguo si alguna vez hiciera falta
  diagnosticar, sin rama de código aparte.
- **Alternativa descartada — flag `PG_BUILD_PLAN_TRAMOS`**: añade una
  combinación no probada por noche y un camino sin puerta de disco.

## 4 · Ficheros a crear

| Fichero | Contenido |
|---|---|
| `etl_sigrid/domain/tramos.py` | Función pura `planificar_tramos(pesos_por_obra: dict[int, int], max_filas: int) -> list[Tramo]` + dataclass `Tramo(indice: int, obras: tuple[int, ...], peso: int)`. Empaquetado greedy determinista: obras ordenadas por peso desc y, a igual peso, por `obra_id`; obra > máximo ⇒ tramo unitario (el WARNING lo emite quien llama: domain no loguea). Capa **domain**: cero imports de infraestructura. |
| `tests/test_f019_tramos.py` | Tests R3–R12 y R17 (sin red ni BBDD). |

## 5 · Ficheros a modificar

| Fichero | Qué cambia |
|---|---|
| `etl_sigrid/infrastructure/postgres/sql/stg/08_plan_mensual.sql` | (1) Se ELIMINA el `TRUNCATE` (pasa al step). (2) Se añade el marcador `/*F019_FILTRO_OBRAS*/` como condición en las DOS ramas: en `master_planif` → `AND pp.obra_id = ANY (/*F019_FILTRO_OBRAS*/)` y en `reales_base` → ídem. Opcionalmente el mismo filtro sobre `fa.obride` en la subquery de `raw.obrfasamb` (reduce el join; el implementer decide midiendo, sin obligación). (3) **Ni una línea de la lógica de negocio se toca**: la interpretación del planif está validada al céntimo contra Sigrid y sus comentarios son parte del contrato. |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | Dos métodos nuevos: `fetch_pesos_plan_mensual() -> dict[int, int]` (consulta de pesos por obra, según DA-1) y `medir_ocupacion_disco_pct(total_gb: int) -> float` (según DA-2; propaga excepciones, no las tapa). Y un ejecutor para SQL ya compuesto: `execute_sql_text(sql_text: str) -> int` (una conexión = una transacción, devuelve `cursor.rowcount` del INSERT). |
| `etl_sigrid/application/steps/build_stg_step.py` | El sub-paso `build_plan_mensual` deja de ser un `_SubStep` plano: método `_build_plan_mensual_por_tramos(pg)` que (1) obtiene pesos, (2) llama a `planificar_tramos`, (3) TRUNCATE inicial, (4) por tramo: puerta de disco → componer SQL (sustituir marcador con enteros validados) → `execute_sql_text` → `record_run_start/end` con nombre `build_stg.build_plan_mensual.tramo_NN` → log estructurado R12, (5) ante límite/fallo: TRUNCATE de limpieza + FAILED (R9/R11). La composición del filtro valida `isinstance(o, int)` sobre cada obra y falla si el marcador no aparece exactamente una vez por rama (R7). **No se usan placeholders pyformat**: los comentarios del SQL contienen `%` literales y psycopg los interpretaría como placeholders; la sustitución textual de un marcador único con enteros validados evita ese campo de minas (el precedente parametrizado, `07_*.sql` con `%(cod)s`, funciona porque ese fichero no tiene `%` sueltos). |
| `config/settings.py` | Tres settings nuevos con default: `PG_TRAMO_MAX_FILAS` (1_000_000), `PG_DISCO_TOTAL_GB` (32), `PG_DISCO_LIMITE_PCT` (80). Sin secretos, sin tocar `.env`. |
| `docs/ARCHITECTURE.md` | §«El datamart en Azure»: el build de `plan_mensual` va por tramos con puerta de disco; los tres settings y el porqué (incidente 2026-08-09). Frases sin cadenas largas con `/` (el barrido de secretos de F-005 da falso positivo con rutas largas, ya mordió en F-004). |
| `azure-apps/datamart_seg_anual.md` (repo `azure-apps`) | Nota en lo que consumimos de `psql-albaranes-rs9k2`: el build pesado va troceado y aborta por encima del 80 % de disco — es la protección de las otras apps y deben saber que existe. |

## 6 · Ficheros que NO se tocan

- `06_presupuesto.sql`, `07_version_master_vigente.sql`, `01_ddl.sql`,
  `00_functions.sql` y todo `mart/`, `cierre/`, `compras/`, `maestro/`,
  `retenciones/`, `auxiliar/`: la reescritura es solo del build de
  `plan_mensual`.
- `etl_sigrid/infrastructure/postgres/fingerprint.py` y los comandos
  `fingerprint-views`/`compare-fingerprints`: se USAN como verificación, no
  se modifican (si se tocaran, dejarían de ser un árbitro independiente).
- Todo `infra/` (incluido `infra/env/dev.json` y su `jobProgramable`):
  pertenecen a F-003; esta feature solo cumple las condiciones para que el
  humano lo cambie (R16).
- `.env`, `.env.local.bak`: solo el humano.
- `harness/`, `CHECKPOINTS.md`.

## 7 · Riesgos y decisiones técnicas menores

1. **Tabla visible a medias durante el build**. Entre el TRUNCATE inicial y
   el último tramo, `stg.plan_mensual` está incompleta para otros lectores.
   Es el comportamiento actual (TRUNCATE + INSERT único no era atómico
   entre pasos del pipeline tampoco: `build_mart` corre después y en
   secuencia). Se mantiene: el único consumidor es el propio pipeline y el
   aborto limpia a vacío, que es un estado inequívoco. La alternativa
   (construir en tabla sombra y `ALTER TABLE RENAME`) duplicaría el disco
   de la tabla final en el servidor que intentamos no llenar. Descartada.
2. **`rowcount` como filas del tramo**: se toma del cursor del INSERT, no
   de `COUNT(*)` sobre la tabla creciente (un seq-scan por tramo sobre
   millones de filas en 1 vCPU sería castigo gratuito). El recuento total
   final sí puede ser el `count_rows` que el step ya hace una vez.
3. **Obra gigante**: si T1 revela una obra con peso > `PG_TRAMO_MAX_FILAS`,
   el tramo unitario puede seguir derramando más que el objetivo. El
   WARNING de R4 lo hace visible; si el pico medido de esa obra en T7 se
   acercara al margen, la constante o el corte se revisan ANTES de R14 (y
   se anota aquí).
4. **Consulta de pesos cada noche**: una agregación extra sobre
   `raw.obrparpre` (~minutos en B1ms, sin ventanas ⇒ sin derrame
   relevante). Coste aceptado a cambio de tramos equilibrados; la variante
   `COUNT(*)` simple queda como palanca si T9 mide un coste feo.
5. **`_meta.etl_runs` crece ~14 filas más por noche**: irrelevante, y es
   justo lo que hace útil a `timings` para el paso 9 de F-005.
6. **Los tests estáticos del SQL** (R6) leen el fichero y comprueban
   marcadores/ausencia de TRUNCATE con regex simples: no validan SQL
   completo (eso solo lo hace la BBDD en R13/R14), pero convierten la
   regresión silenciosa más probable (alguien borra un filtro al editar) en
   rojo inmediato de la suite.
