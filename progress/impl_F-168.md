# F-168 · Informe del implementer (`estandar`)

Rama `feature/F-168-texto-largo-flujo-obra`, worktree `.claude/worktrees/f168`, base `5566284`.
D1-D8 = (a), D9 = (a): solo el texto vigente de la partida, sin tabla de historia.

## Hecho

1. **Ingesta.** Seis tablas que ya se ingerían traen ahora su `tex`, recortado en origen a 16.000
   caracteres y sin NUL. Las seis son `obrparpar`, `dncpro`, `dcopro`, `ctrpro`, `dcapro` y
   `dcfpro`. El recorte lo pide la clave nueva `recortar_columnas` del YAML.
2. **Publicación.** Hay una limpieza y una identidad para todo el datamart (`stg/11`), que alimentan:
   - `stg.partida_texto`;
   - `compras.linea_texto`, `compras.textos` y `compras.v_linea_texto`;
   - el memo de ofertas (12) y comparativos (46) en `compras.documento_texto` y `documento_comentarios`;
   - `descompuestos.lineas.texto_id` con su catálogo `descompuestos.textos`.
3. **Diccionario.** Sube a la v82, con las fichas y la documentación al día.

## Commits (uno por tarea)

| Tarea | Commit | Qué |
|---|---|---|
| T1 | `f428ee5` | `domain/texto_largo.py`: TOPE, patrón de control, `limpiar`, `texto_id`, `es_recortado`, `expresion_recorte` |
| T2 | `5822d06` | `TableSpec.recortar_columnas`, `_validar_recortes` (R4) y `stream_table(recortes=)` (R3) |
| T3 | `4b31950` | `tables_sigrid.yaml` (R1, R2) y las fichas de `raw` de las seis tablas |
| T4 | `e5926b3` | `stg/11_texto_largo.sql` (3 funciones), `stg/12_partida_texto.sql`, dos `_SubStep` y el preflight de `obrparpar.tex` |
| T5 | `3166edd` | `compras/16_textos_linea.sql` (`linea_texto`, `textos`, `v_linea_texto`) y su `_SubStep`, que va el último |
| T6 | `14e2ede` | `compras/07_texto.sql` pasa a `tip IN (12, 15, 44, 46)` (R18) |
| T7 | `de19e98` | Campo 9 (`texto_largo`) en `fn_trocear`, `POSICIONES` y `trocear_des` (R19) |
| T8 | `65a759e` | `texto_id` y `descompuestos.textos` en `02` y `03` (R20, R21); `../stg/11_texto_largo.sql` en el sello (R22) |
| T9 | `3aaed87` | `tests/test_f168_sandbox.py` (13 casos de design §6); se salta si falta `F168_SANDBOX_DSN` |
| T10 | `e1079c1` | Diccionario v82 y `tests/test_f168_diccionario.py` (R24, R25) |
| T11 | `091a58f` | `docs/ARCHITECTURE.md` (las dos secciones) y el mapa de `CLAUDE.md` |
| T17 | `8c2e670` | Las comprobaciones de F-047, F-066, F-073, F-080 y F-138 que sacó la suite entera |
| T12 | `azure-apps` `2f4d08c` | `datamart_seg_anual.md` con `pull --rebase` antes (ya estaba al día). Commit aparte, **sin push** |

## Ficheros

- **Nuevos**:
  - `etl_sigrid/domain/texto_largo.py`
  - `sql/stg/11_texto_largo.sql`, `sql/stg/12_partida_texto.sql`
  - `sql/compras/16_textos_linea.sql`
  - `tests/test_f168_{dominio,ingesta,sql,descompuestos,diccionario,sandbox}.py`
- **Código cambiado**:
  - `domain/entities.py`, `domain/descompuestos.py`
  - `steps/ingest_raw_step.py`, `steps/build_stg_step.py`, `steps/build_compras_step.py`,
    `steps/build_descompuestos_step.py`
  - `sigrid/sigrid_api_client.py`
  - `sql/compras/07_texto.sql`
  - `sql/descompuestos/01_troceado.sql`, `02_lineas_coste.sql`, `03_lineas_master.sql`
- **Configuración**: `config/tables_sigrid.yaml` y los YAML de diccionario `00_global` (v82), `raw`,
  `stg`, `compras` y `descompuestos`.
- **Documentación**:
  - `docs/ARCHITECTURE.md`, `CLAUDE.md`
  - `specs/F-006-mcp-azure/design_detalle.md` (enmienda: 339 objetos)
  - `azure-apps/datamart_seg_anual.md`

## Decisiones de diseño y desviaciones (justificadas)

1. **`stg.fn_texto_recortado(t)`**: una función más de las que nombra el design, que escribía
   `char_length(o.tex) >= TOPE` dentro de cada SQL. Así el 16000 vive en un solo sitio de SQL. Es el
   mismo que `TOPE_CARACTERES`, y lo comprueba `test_f168_r7_el_sql_usa_los_literales_del_dominio`.
   Usan la función `stg/12` y `compras/16`.
2. **`compras/16` usa una temporal `_f168_fuentes ON COMMIT DROP`.** Contiene las cinco fuentes
   limpiadas una sola vez. De ella salen `textos` (con `DISTINCT ON`) y `linea_texto`, con las dos
   igualdades por `CASE` (NULL si falta uno de los dos textos). El cero pasa a NULL en la proyección
   final, porque la puerta de F-006 lo exige ahí.
3. **`compras/07` y los tipos 12 y 46.** `fn_tipo_documento` no conoce el 12 ni el 46 y daría `OTRO`.
   Por eso un `CASE` local los nombra `OFERTA` y `COMPARATIVO`, sin tocar la función, que comparten
   otras tablas.
4. **`descompuestos`**:
   - **Dónde se escriben los textos.** En ESTUDIO y en el master, los textos se insertan desde un CTE
     que modifica datos, en la MISMA sentencia que las líneas (`ON CONFLICT DO NOTHING`). En
     PLANIF_JO va una sentencia aparte en el mismo fichero, dentro de la misma transacción de
     `execute_sql_file`.
   - **`textos` nunca se vacía.** No hay `DELETE` ni `TRUNCATE`, y se lee uniendo desde `lineas`.
   - **`texto_id` en el `CREATE TABLE`.** Va también ahí, y no solo en el `ALTER`, para que una base
     nueva quede igual que una migrada.
   - **Lectura de `stg`.** Es la única de este esquema fuera de `raw`, y son dos FUNCIONES, no tablas.
5. **El recuento del inventario.** La puerta de F-006 lee `design_detalle.md`, no `design.md`, así
   que el recuento va como enmienda allí (339). La fila que T4 había puesto en `design.md` se
   retiró en T5.
6. **`PRESUPUESTO_MAX` sube de 38.519 a 38.739 (+220).** El motivo está anotado al lado, en
   `test_f147`. Son dos fichas recomendadas nuevas (`stg.partida_texto` y `compras.v_linea_texto`),
   con dos preguntas cortas cada una. `linea_texto`, `compras.textos` y `descompuestos.textos` se
   publican como NO recomendadas, con su `motivo_no_consumo`, así que no suman.
7. **Tests anteriores adaptados.** En cada caso F-168 cambia a propósito la forma que el test
   fijaba, y cada cambio lleva su comentario `F-168` en el propio test:

   | Test | Qué fijaba y cómo queda |
   |---|---|
   | `test_f080_sql` (R22) | Fijaba `tip IN (15, 44)`; ahora fija la lista nueva |
   | `test_f097_planificador` (R13) | `POSICIONES` incluye el 9 |
   | `test_f097_descompuestos` (R11, R12, R21, R26, R27) | Sello de 4 ficheros; columnas de `lineas` con `texto_id`; el INSERT del master dentro de `WITH troceado`; R26 admite solo `stg.fn_texto_largo` y `stg.fn_texto_id`; el objeto `textos` |
   | `test_f120_factor` (R17, R19, R21, R24, R27) | `texto_id` va DETRÁS de `factor`, que no se mueve; sello de 4 ficheros; texto del sello en ARCHITECTURE |
   | `test_f123_origenes` (R1, R3, R8, R12) | Huellas nuevas de los bloques de `02`, con las de F-123 anotadas al lado; el objeto `textos`; el COMMENT de `stg/11` ya no nombra `descompuestos.` (no es un lector) |
   | `test_f079_stg_consultable` | Inventario `GRUPO_I_F168`: las 3 funciones y las 3 tablas no recomendadas |
   | `test_f127_mayor_analitico` | Pasa a fijar que la v81 fue la de F-127, no que sea la última |
   | `test_f150_ingesta` | Su `stream_table` falso acepta `recortes=` |
   | `test_f157_step`, `test_f161_sql` | El orden de los sub-pasos de `stg` |
| `test_f080_pipeline`, `test_f073_pipeline`, `test_f047_steps`, `test_f138_ingesta_sql` | La lista de SQL de `build_compras`: `16_textos_linea.sql` va el último, y el 15 queda el penúltimo |
| `test_f066_ingesta_raw` (R7) | `dcopro` y `dncpro` pasan a excepción de la lista estándar (traen `tex`), como `prvcer` |

## Fase RED (trazas reales, tests escritos antes del código)

```
$ python -m pytest tests/test_f168_dominio.py -q          # T1: el módulo no existía
ERROR tests/test_f168_dominio.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.77s

$ python -m pytest tests/test_f168_ingesta.py -q          # T2/T3
FAILED tests/test_f168_ingesta.py::test_f168_r1_las_seis_tablas_ingieren_tex_recortado[obrparpar]
...
FAILED tests/test_f168_ingesta.py::test_f168_r3_stream_table_pide_la_columna_recortada
FAILED tests/test_f168_ingesta.py::test_f168_r3_recorte_de_una_columna_que_no_se_pide_falla
20 failed, 14 passed in 9.97s

$ python -m pytest tests/test_f168_sql.py -q              # T4: stg/11 y stg/12
FAILED tests/test_f168_sql.py::test_f168_r7_cabecera_con_la_ruta - FileNotFou...
FAILED tests/test_f168_sql.py::test_f168_r5_el_orden_de_la_limpieza - FileNot...
FAILED tests/test_f168_sql.py::test_f168_r8_recortado_es_mayor_o_igual_que_el_tope
...
FAILED tests/test_f168_sql.py::test_f168_el_preflight_exige_tex_en_obrparpar
11 failed, 1 passed in 2.84s

$ python -m pytest tests/test_f168_sql.py -q              # T5: compras/16
FAILED tests/test_f168_sql.py::test_f168_r13_las_cinco_fuentes_y_sus_enlaces
FAILED tests/test_f168_sql.py::test_f168_r14_igualdades_con_case_y_nulo - Fil...
...
FAILED tests/test_f168_sql.py::test_f168_el_sub_paso_de_compras_es_el_ultimo_y_cuenta_linea_texto
11 failed, 12 passed in 3.66s

$ python -m pytest tests/test_f168_sql.py -q -k r18       # T6
E       assert 'WHERE c.tip IN (12, 15, 44, 46)' in "DROP TABLE IF EXISTS compras.documento_texto CASCADE; ...
E       assert [15, 44] == [12, 15, 44, 46]
3 failed, 1 passed, 23 deselected in 2.14s

$ python -m pytest tests/test_f168_descompuestos.py -q    # T7 y T8
FAILED tests/test_f168_descompuestos.py::test_f168_r19_posiciones_incluye_el_campo_9
FAILED tests/test_f168_descompuestos.py::test_f168_r21_ddl_de_textos_y_alter_de_lineas
FAILED tests/test_f168_descompuestos.py::test_f168_r20_solo_las_funciones_de_stg
FAILED tests/test_f168_descompuestos.py::test_f168_r22_stg_11_entra_en_el_sello
12 failed in 2.83s

$ python -m pytest tests/test_f168_diccionario.py -q      # T10
E       assert 81 == (81 + 1)
E       assert 'texto limpio' in 'Verdadero si el texto es el de su partida (`stg.partida_texto`), ...'
2 failed, 17 passed in 2.20s
```

Lo que ya pasaba en RED son guardas de «no cambia» o requisitos de una tarea anterior.
**R17 (review)**: el código existía, así que su RED es una mutación a mano (OFERTA con
`o.dncproide` en vez de `o.ide` en `16`), revertida después:
`pytest tests/test_f168_sql.py -k r17` → `E assert ('o.ide::BIGINT AS linea_id' in "'OFERTA'::TEXT
AS tipo_linea, o.dncproide::BIGINT AS linea_id, ...` · `1 failed`.

## Salida de `init.sh`

`bash harness/init.sh` en el worktree (2026-11-23), salida `exit=1` con **3 KO, los tres de entorno
y anteriores a F-168** (ya estaban en la precondición):

```
[KO] Falta .env — copiar de .env.example
[KO] pytest en rojo  -> 1 failed, 143 passed in 98.09s (-x: para en el primero)
     FAILED tests/test_base_de_la_puerta.py::test_en_este_repositorio_la_base_no_esta_rezagada
[KO] PUERTA COBERTURA: la base «main» se ha quedado por detrás: ... 34 de los 47 ya están en «dev»
[OK] PUERTA TAMAÑO: F-168 dentro de los topes (requirements 124/150, design 205/250, impl 194/220)
[OK] PUERTA CARRIL: N/A (F-168 es de nivel estandar: no declara límites)
[OK] CAPA E2E: N/A
[AVISO] F-168 ... sin spec_aprobada: anota en harness/features.json el día (lo escribe el líder)
[AVISO] ruff: 437 avisos (deuda previa, no bloquea)
```

**La puerta completa, con `.env` y la base bien puesta, la pasa el líder en el checkout principal.**
Como `init.sh` para en el primer fallo, la suite entera se lanzó aparte; su resultado está en
«Evidencias».

## Verificaciones MANUAL pendientes (no ejecutadas: son del humano o del líder)

- **T9 · sandbox: HECHA.** El puesto sí tiene PostgreSQL 16 (`C:\Program Files\PostgreSQL\16\bin`,
  con `initdb`; yo solo había mirado el PATH). Clúster desechable en el scratchpad (`initdb -A trust`,
  `pg_ctl -p 54398`, borrado al acabar): `tests/test_f168_sandbox.py` → **14 passed en 7,90 s**.
- **T13 · lectura de prueba.** Solo lectura y sin escribir en ningún Postgres, desde un script del
  scratchpad con `api.leer_sql`. Es una página de 5.000 filas de cada una de las seis tablas, con la
  expresión de recorte de `expresion_recorte('tex', 16000)`. Hay que anotar tiempo y bytes.
- **T14 · tras desplegar la imagen.**
  1. `python main.py ingest --full --table <t>` para cada una de las seis. Sin `--full` es
     incremental (`max(ide)`) y las filas ya cargadas se quedan con `tex` NULL. O la nocturna.
  2. `stage` y `build-compras` (decía `build-stg`, que no existe).
  3. `build-descompuestos --sin-tope` + `apply-grants`. Cambia el sello: retroceso del master
     entero, SIEMPRE después de la imagen.
  4. `check-diccionario` y publicar la v82 CON LA IMAGEN.
  5. Comprobar `SELECT texto FROM stg.partida_texto WHERE partida_id = 419079` (R11).
  6. `SELECT tipo_linea, count(*) FROM compras.linea_texto GROUP BY 1` frente a M2: NECESIDAD
     ~164.000, OFERTA ~487.800, CONTRATO ~132.900, ALBARAN ~305.900 y FACTURA ~229.100, menos las
     que se quedan vacías al limpiar.
- **T15 · coste real.** `_meta.etl_runs` de los seis `ingest_raw.*` y `pg_database_size`. El límite
  es ingesta ≤ 558 s + 600 s y base ≤ 40,7 GB + 2 GB (R27); si se pasa, parar y replantear D1.
- **T16 · las dos consultas de `tasks.md`**, las dos deben dar 0 (R20, R21). Después, reiniciar
  `mcp-bbdd` y hacer la pregunta de la 0726.
- **Push (humano).** La rama de la feature, y `azure-apps` `2f4d08c` con `pull` antes del `push`.

## Qué queda fuera

- Historia (D9), pedidos (D8), `tex` de cabeceras, máscara (D6, vigilada por `r24_*`) y mutación (pasada de campaña).

## Evidencias

| Evidencia | Valor real |
|---|---|
| Tests de F-168 | **122 pasan y 14 se saltan** sin DSN (la sandbox), 16,66 s; con DSN la sandbox, 14/14. Por fichero: dominio 29, ingesta 34, sql 28, descompuestos 12, diccionario 19, sandbox 14 |
| Suite entera (`python -m pytest -q`, sin `-x`) | **13.856 pasan, 127 fallan y 2.605 se saltan**, en **4.166,75 s (1 h 09 min)** |
| Los 127 fallos | 11 eran de F-168 (F-047, F-066, F-073, F-080 y F-138) y se arreglaron en `8c2e670`: los 5 ficheros, ya en verde (403 pasan) |
| | Los otros 116 son de entorno. 115 fallan **idénticos** en la base `5566284`, en un worktree desechable, con `diff` vacío. Son `SigridApiSettings` sin `.env` (CLI de check-*, f025, f078 y f118, entre otros) y la base rezagada |
| | El último es `test_f059_r7_...TIMEOUT`, un test de tiempos que falló bajo carga. Relanzado solo: 3 de 3 pasan |
| Puertas del diccionario (f006 fichas, cobertura y formato; f147; f149) | 1.512 pasan y 360 se saltan, en 388,54 s. `PRESUPUESTO_MAX` 38.739 |
| Cobertura de las líneas cambiadas | **No medible en el worktree**: `PUERTA COBERTURA` da KO de entorno (la base `main` va 34 commits por detrás de `dev`). La da el líder con `RAMA_BASE` bien puesta |
| Mutantes | **Pendiente de la pasada de campaña**: `python -m harness.mutacion --feature F-168` sobre código aprobado, como manda el protocolo |
| Capa e2e | N/A (`CAPA E2E: N/A`, sin `harness/servicios.json`) |
| Sandbox SQL (T9) | **14/14 pasan** (7,90 s) contra un PostgreSQL 16 desechable del puesto |
