<!-- progress/impl_F-066_reconciliar_columnas.md -->
# F-066 · Arreglo del defecto que tumbaba la nocturna (T17-T18)

Rigor **crítico**. Rama `feature/F-066-ingesta-raw-pendientes`, commits
`1d9a075` (el arreglo) y `592e370` (lo que pidió la mutación). Requisitos
nuevos **R25-R28** (`requirements.md` §F), decisiones **DA-8/9/10**
(`design.md` §8).

## 1 · Qué estaba roto

Las ejecuciones `k251zrq` (2026-09-07 16:02 UTC) y `29813760` (2026-09-08
00:00 UTC, la del cron) fallaron las dos en `ingest_raw`:

```
psycopg.errors.UndefinedColumn: column "pagtex" of relation "dcf" does not exist
  File "/app/etl_sigrid/application/steps/ingest_raw_step.py", line 292, in _ingest_one_table
  File "/app/etl_sigrid/infrastructure/postgres/postgres_client.py", line 1605, in copy_rows
```

**La causa.** T7 de esta misma feature quitó `pagfor` y `pagtex` de
`exclude_columns` de `dcf`, pero `raw.dcf` llevaba meses creada en Azure sin
esas dos columnas. `ensure_raw_table` emitía `CREATE TABLE IF NOT EXISTS` y
**nada más**: sobre una tabla que ya está, esa sentencia no hace nada. El
`COPY` posterior nombraba dos columnas inexistentes y reventaba.

Las 25 tablas nuevas no dieron problema porque nacen de cero. **El fallo solo
aparece cuando cambian las columnas de una tabla preexistente**, que es justo
lo que no se ve en local contra una base vacía. Es un agujero del cliente
Postgres, no de la configuración: le pasaría a cualquier feature futura que
recupere una columna excluida.

## 2 · Qué se ha hecho

`ensure_raw_table` gana `_reconciliar_columnas_raw(cur, tabla, columnas)`,
que corre **en la misma transacción** que el `CREATE TABLE IF NOT EXISTS`:
o la tabla queda con el esquema completo, o no cambia nada.

La regla, tal y como la aprobó el humano y sin margen:

| Situación | Acción |
|---|---|
| Columna esperada que **no está** | `ADD COLUMN ... NULL` + una línea de log por columna |
| Columna del destino que el origen **ya no trae** | `warning` con tabla y columna. **No se borra** |
| Columna cuyo **tipo ya no casa** | `warning` con los dos tipos. **No se altera** |
| `_ingested_at`, `_source_tiemod` | fuera de la comparación |

**Ficheros tocados**: `etl_sigrid/infrastructure/postgres/postgres_client.py`
(+180 líneas: `COLUMNAS_TECNICAS_RAW`, `_ALIAS_TIPOS_PG`,
`_SQL_COLUMNAS_REALES`, `_tipo_normalizado`, `_reconciliar_columnas_raw` y su
llamada), `tests/test_f066_reconciliar_columnas.py` (nuevo, **28 tests**, sin
red ni BBDD) y la spec: `requirements.md` §F (R25-R28), `design.md` §8
(DA-8/9/10) y `tasks.md` (T17, T18).

### Las tres decisiones de diseño

- **DA-8 · la reconciliación va ANTES del `TRUNCATE`.** El orden ya era ése
  en el step (`ensure` es el punto 2, `truncate` el 3) y ahora un test lo fija.
  Si el DDL fallara **después** de vaciar, la tabla quedaría sin dato **y** sin
  la columna: se habría destruido la carga de ayer sin poder cargar la de hoy.
  Al revés, un DDL que falla deja intacta la carga anterior. Y no cuesta nada:
  `ADD COLUMN` sin `DEFAULT` es metadato puro en Postgres, no reescribe la
  tabla, ni siquiera en `apu` con 2,1 M de filas.
- **DA-9 · varias columnas que faltan, un solo `ALTER TABLE`.** Un bloqueo y
  un cambio atómico. `dcf` es exactamente ese caso: necesita las dos a la vez.
- **DA-10 · comparar tipos exige normalizarlos.** El ETL escribe
  `VARCHAR(30)` y el catálogo devuelve `character varying(30)`. Sin
  `_tipo_normalizado` saltaría un aviso falso en cada columna de cada tabla
  todas las noches, y el log dejaría de servir para ver los cambios de verdad.
  Las columnas reales se leen de `pg_attribute` + `format_type`, no de
  `information_schema.columns`, porque hace falta el tipo **con** su precisión.

## 3 · QUÉ VA A PASAR LA PRÓXIMA NOCHE (para verificar en la traza)

Comprobado **hoy contra la base de Azure** por el MCP de solo lectura:
`raw.dcf` tiene **134 columnas y ninguna de las dos**.

**Se añadirán exactamente dos columnas, y a una sola tabla:**

**`raw.dcf`** ← `pagtex` («Con.Pago») y `pagfor` («Fórmula Pago»), las dos
`TEXT NULL`: figuran como *Texto ilimitado* en `azure-apps/sigrid_tablas.md` y
`ColumnSpec.postgres_type` mapea ese tipo a `TEXT`. Una sola sentencia:

```sql
ALTER TABLE raw."dcf" ADD COLUMN IF NOT EXISTS "pagtex" TEXT NULL,
                      ADD COLUMN IF NOT EXISTS "pagfor" TEXT NULL
```

**Ninguna otra tabla preexistente cambia.** El diff de
`config/tables_sigrid.yaml` contra `main` toca `exclude_columns` de una sola
tabla ya existente —`dcf`—; el resto del diff son las 25 altas nuevas.

**Estado de esas 25 en Azure**, medido hoy: **17 ya creadas** (las crearon los
intentos fallidos, que siguen con las demás tablas porque `stop_on_error` es
`False`) y **8 todavía sin crear**: `apa`, `apu`, `asi`, `confir`, `dco`,
`dcopro`, `dncpro`, `hmores` — las grandes. Esas 8 nacerán del `CREATE TABLE`,
**no** de la reconciliación: no deben aparecer en el log de `ADD COLUMN`.

**Qué buscar en la traza de la nocturna:**

| Evento | Qué significa |
|---|---|
| `raw_columna_anadida` | una columna añadida. Deben salir **dos**, las de `dcf` |
| `raw_tabla_reconciliada` | resumen por tabla: `table=raw.dcf`, `columnas_anadidas=2` |
| `raw_columna_sobrante_en_destino` | `warning`: el origen dejó de traer una columna |
| `raw_columna_cambia_de_tipo` | `warning`: un tipo cambió en Sigrid |

**La salvedad honesta:** si Sigrid ha ganado por su cuenta alguna columna en
alguna de las 31 tablas antiguas, el arreglo también la añadirá. Eso **no se
puede enumerar sin conectar a la vez a Sigrid y a Postgres**, y no se ha hecho.
Un `raw_columna_anadida` de más no sería un error del arreglo: sería una
columna que Sigrid añadió y el ETL no había recogido nunca.

## 4 · Fase RED (obligatoria en rigor crítico)

Los 13 tests se escribieron **antes** que el código. Traza real:

```
$ python -m pytest tests/test_f066_reconciliar_columnas.py -q
FF..FFFF.F.F.                                                            [100%]
================================== FAILURES ===================================
___ test_f066_r25_una_tabla_preexistente_recibe_las_columnas_que_le_faltan ____
        alters = [s for s in cursor.ejecutadas if "ALTER TABLE" in s]
>       assert len(alters) == 1, (
E       AssertionError: se esperaba UNA sola sentencia ALTER TABLE; se emitieron 0:
E       ['CREATE TABLE IF NOT EXISTS raw."dcf" ("ide" INTEGER NOT NULL, "cod"
E        VARCHAR(30) NULL, "pagfor" INTEGER NULL, "pagtex" VARCHAR(50) NULL,
E        _ingested_at TIMESTAMP NOT NULL DEFAULT NOW(), _source_tiemod DOUBLE
E        PRECISION NULL, PRIMARY KEY ("ide"))']
E       assert 0 == 1
E        +  where 0 = len([])
_________ test_f066_r25_la_columna_que_ya_esta_no_se_vuelve_a_anadir __________
>       alter = next(s for s in cursor.ejecutadas if "ALTER TABLE" in s)
E       StopIteration
____________ test_f066_r28_cada_add_column_deja_su_linea_en_el_log ____________
>       assert {"pagfor", "pagtex"} <= nombradas, (
E       AssertionError: cada columna añadida deja su propia línea de log:
E       [('raw_table_ready', {'table': 'raw.dcf', 'columns': 4, 'pk': 'ide'})]
E       assert {'pagfor', 'pagtex'} <= set()
=========================== short test summary info ===========================
FAILED ...r25_una_tabla_preexistente_recibe_las_columnas_que_le_faltan
FAILED ...r25_la_columna_que_ya_esta_no_se_vuelve_a_anadir
FAILED ...r26_la_columna_anadida_nace_null_aunque_el_origen_la_declare_not_null
FAILED ...r26_la_columna_anadida_lleva_su_tipo_postgres
FAILED ...r27_una_columna_que_el_origen_ya_no_trae_se_avisa_y_no_se_borra
FAILED ...r27_un_tipo_que_cambia_se_avisa_y_no_se_altera
FAILED ...r27_la_reconciliacion_solo_emite_add_column
FAILED ...r28_cada_add_column_deja_su_linea_en_el_log
8 failed, 5 passed in 1.61s
```

Los 5 verdes en rojo afirman lo que el ETL **no** debe hacer (ningún `DROP`,
ningún `ALTER COLUMN`, ningún DDL con el esquema al día): pasaban sin código
porque antes no se hacía nada, y siguen haciendo falta porque son los que
impiden que el arreglo se pase de frenada. Después del código, mismo comando:
`.............  13 passed in 1.14s` (y 28 tras los 15 de la mutación).

## 5 · Evidencias

| Evidencia | Valor |
|---|---|
| Tests ejecutados (suite completa) | **3.924 pasan, 159 saltados, 0 fallos** |
| Tiempo de la suite | **531,50 s** dentro de `init.sh`, con medición de cobertura |
| Tests nuevos | **29**, todos verdes; 8 con fase RED documentada |
| Cobertura de las líneas cambiadas | **93,2 %** (736/790), umbral 80 %, nivel crítico |
| Mutantes generados / evaluados | **6 / 6** (campaña completa, sin muestreo) |
| Muertos / supervivientes / timeouts | **6 / 0 / 0** en 2.091,5 s sobre `ca1d6b9` |
| `bash harness/init.sh` | **verde, código 0**; puertas de cobertura, tamaño y rama OK |

### La campaña de mutación

Acotada con `--base 79059f8`: **180 líneas de `postgres_client.py`**, sin
repetir la campaña de F-066 que el humano firmó en T12. El relato completo de
los **cuatro lanzamientos** —con las trazas— está en
**`progress/mutacion_F-066_reconciliar_columnas.md`**, § «Nota del implementer».

En corto: la 1.ª (sobre `1d9a075`) dio **3 supervivientes**, los tres en la
aritmética de índices de `_tipo_normalizado`; la 2.ª se abortó con **línea base
roja** por un error mío —un `git worktree` no tiene `.env`, y la campaña no lo
copia a propósito—; la 3.ª (sobre `592e370`, en serie) dio **6 mutantes, 5
muertos, 1 vivo** en 1.972,7 s; la 4.ª (sobre `ca1d6b9`) es la que cuenta.

**Ningún superviviente se ha eximido: los cuatro se han cerrado.** Los tres de
la 1.ª se hicieron *desaparecer* cambiando `str.find` por `str.partition`: el
«no lo encontré» pasa a ser la cadena vacía del separador y **no queda un solo
literal entero en la función**, así que los 16 mutantes bajan a 6. Matarlos con
tests habría exigido afirmar sobre cadenas que `format_type` no puede devolver
—un tipo con `)` y sin `(`—, es decir sobre basura y no sobre comportamiento.
El de la 3.ª, `nullable=True -> nullable=False` en el log `raw_columna_anadida`,
se mató con un test que **ata lo que se ejecuta a lo que se cuenta que se
ejecutó**: si el `ADD COLUMN` pasara a `NOT NULL` y el log siguiera diciendo
`nullable=True`, salta. Una traza que miente sobre un cambio de esquema en
producción es peor que no tener traza.

## 6 · Lo que queda fuera y lo que falta

- **No se ha lanzado ni un `ALTER TABLE` a mano contra Azure**, a propósito:
  lo que hay que comprobar es que el arreglo funciona solo en la nocturna.
  Contra la base solo se han hecho lecturas del catálogo por el MCP.
- **T13 y T14 siguen abiertas** y son del humano: desplegar la imagen y
  dejar correr la nocturna, y después `check-raw-recuentos` y
  `check-diccionario`. Con este arreglo dentro, C4 y C5 del review pueden
  cerrarse por fin.
- **Nada que tocar en el diccionario**: el arreglo no publica ningún objeto
  nuevo. `dcf` ya tenía su ficha corregida en T7.
- **Tres ficheros quedan modificados y sin commitear, y no son míos**:
  `harness/features.json`, `BACKLOG.md` y `progress/review_F-025.md`, del
  líder. Entraron por error en el primer intento de commit y se sacaron de él
  (`git reset --soft`) para que el commit del arreglo lleve solo el arreglo.
  Por no tocarlos, la campaña tuvo que ir en serie: la paralela exige árbol
  limpio.
