<!-- specs/F-097-descompuestos-partidas/design.md -->
# F-097 · Diseño

Un esquema módulo nuevo, **`descompuestos`**, con dos pasos propios:
`ingest_descompuestos` (trae el texto `des` de Sigrid, el master **incremental
por versión**) y `build_descompuestos` (lo trocea y publica). `raw.dncpro` ya se
ingiere (F-066). Cifras: `progress/spec_F-097.md`; decisiones D1-D15, ahí.

## Lo que el dato es (medido el 2026-09-27)

- **Las pestañas son dos tablas.** «Descomposición» (COSTE y MASTER COSTE) es
  `obrparpre.des`; «Planificación compras» es **`dncpro`** de la necesidad de la
  obra (`obr.dncide`): 287.282 líneas, 110.146 partidas, 245 obras. `obrparaux`
  y el módulo de presupuestos de Estudios (`ppo*`) están vacíos.
- **El `des` se reescribe con la planificación**: campo 36 = `dncpro.ide`. En
  ámbito 3 fase 0 (42.958 partidas; solo existe en la fase 0), 7.866 son copia de
  la planificación (D1). En el master, desde la primera ABC el 98,6 % de las
  partidas está enlazado; antes, el 35,6 %: eso es «del ABC en adelante».
- **El master**: 3.023 versiones, 1.616.461 filas con `des`, 2,14 GB de texto,
  ~4,5 M registros. Reparto por origen (D13): `MASTER_INICIAL` 169 versiones /
  11 MB; `MASTER_PRE_ABC` 1.664 / 887 MB; `MASTER_PLANIF_JO` 1.190 / 1.244 MB.
- **No hay `tiemod` en `obrparpre`, ni marca de cierre útil** en `obrfasamb`:
  `est = 2` y `feccie = 0` en casi todas las versiones, vigente o no. Hay 357
  versiones POSTERIORES a la vigente (trabajo en curso).
- **Evidencia de inmutabilidad, parcial**: 155 filas se insertaron en 80
  versiones anteriores a la vigente después de crearse la siguiente, y las 155
  van sin `des`, `can = 0` y `pre = 0` (partidas nuevas de la obra que Sigrid da
  de alta en todas las versiones). Una inserción nunca ha traído `des` a una
  versión cerrada. Un `UPDATE` en sitio no deja rastro sin `tiemod`: lo decide
  la segunda toma de huellas (T0, R1).
- **Ritmo**: 21-43 versiones nuevas al mes (sep-2025 a sep-2026), 27-62 MB/mes.
- **El caso de Juan**: D05DF210 no existe en Sigrid (D11); es la 04.02 de la 0726,
  10 registros, Σ = 134,35, cuadra; sin planificación todavía.

## Por qué el master no va en `tables_sigrid.yaml` (D12, sustituye a D7)

La nocturna es `run-all --full` y trunca todo `raw`: una entrada del YAML
relee los 2,14 GB cada noche (65-94 min a 0,38-0,55 MB/s). El texto vive en
tablas del propio esquema, que nadie trunca, y lo mantiene un paso propio. El
ámbito 3 (21,5 MB, 26 s) va en el mismo paso por simplicidad: así no hace falta
tocar la identidad de la ingesta ni la puerta de F-024. `TOTAL_TABLAS` sigue en 71.

## El incremental

**Estado** (esquema `descompuestos`, no publicado, prefijo `_`):

- `_des_texto` — PK `presupuesto_id` (`obrparpre.ide`); `obra_id, partida_id,
  ambito_id, fase_num, cantidad, precio, haydes, des, batch_id`. Índice
  `(obra_id, ambito_id, fase_num)`.
- `_versiones_cargadas` — PK `(obra_id, fase_num)`; `filas, bytes, huella`
  (las de Sigrid al cargar), `batch_id`, `cargada_at`, `sello_troceado`,
  `troceada_at`.

**Cada noche**, `ingest_descompuestos`:

1. Lee de Sigrid, en una consulta, la huella de todas las versiones (la SQL de
   `progress/mediciones/F-097_huella_master.sql`, 24 s medidos), la vigente
   (`conext`) y la primera ABC (`obrfasamb.tex`) de cada obra.
2. `planificar_relectura` (dominio puro) compara con `_versiones_cargadas`:
   **releer** = no cargadas + vigente de cada obra + huella distinta;
   **borrar** = cargadas que Sigrid ya no tiene; ordena y corta por presupuesto
   (R6). La vigente se relee siempre aunque su huella no cambie: la huella es
   ciega a cambios en mitad de un `des` de más de 16.000 bytes (9.541 filas,
   0,6 %) y es un `CHECKSUM` de 32 bits.
3. Ámbito 3 fase 0: `DELETE` + lectura paginada + `INSERT` en una transacción.
4. Por versión: lectura `WHERE obride = ? AND amb = 8 AND fas = ? AND
   DATALENGTH(des) > 0 AND ide > ?`, 1.000 filas por página; si el recuento no
   es el de la huella, se revierte (R9); si sí, `DELETE` + `INSERT` +
   `UPSERT` de control en una transacción (R8).
5. Registra en `_meta.etl_runs` versiones releídas, borradas, aplazadas y MB.

**Detectar lo nuevo sin `tiemod`**: una versión nueva es un `(obra, fas)` con
`des` en Sigrid que no está en `_versiones_cargadas`. La vigente la dice
`conext`, no el orden. Lo que cambia se ve por huella.

**Primera carga** (MANUAL, D15): `python main.py ingest-descompuestos
--sin-tope` y después `python main.py build-descompuestos --sin-tope`. Estimado:
65-94 min de lectura más ~4.700 llamadas (3.023 versiones y páginas) → **1,5-2 h**;
el troceado inicial de 2,14 GB en Postgres, 20-40 min (no medido). Sin la
primera carga, la nocturna también converge sola, a 300 MB por noche (8 noches).

**Coste por noche** (estimado): huella 24 s + ámbito 3 26 s + vigentes 105 MB
(123 versiones, 3,2-4,6 min) + nuevas ~1,3 MB/día + cambiadas (T0) → **4-6 min**
de ingesta; build ~2-4 min (troceo de ~110 MB, ámbito 3, `PLANIF_JO`, catálogo).

**Espacio** (27 de 64 GB ocupados el 26-09): texto 1,0-2,2 GB (TOAST comprime;
sin medir), líneas ~4,9 M × 250-350 B con índices = 1,2-1,7 GB, cuadre ~2 M filas
~0,3 GB → **2,5-4,2 GB**; el disco quedaría en ~30-31 GB (47-49 %), lejos del 80 %.

## Ficheros a crear

- `etl_sigrid/domain/descompuestos.py` — `VersionSigrid`, `VersionCargada`,
  `PlanRelectura` (dataclasses inmutables) y `planificar_relectura(sigrid,
  cargadas, vigentes, presupuesto_mb, sin_tope) -> PlanRelectura` (R5, R6).
- `etl_sigrid/application/steps/ingest_descompuestos_step.py` —
  `IngestDescompuestosStep`, `depends_on = []`; orquesta 1-5 de arriba.
- `etl_sigrid/application/steps/build_descompuestos_step.py` —
  `BuildDescompuestosStep`, `depends_on = ["ingest_raw", "ingest_descompuestos"]`,
  `SUB_PASOS` a nivel de módulo, parada con el nombre del sub-paso; molde de
  `build_contabilidad_step.py`. Sustituye el marcador de versiones en
  `03_lineas_master.sql` (patrón de F-019) por las pendientes (R21).
- `sql/descompuestos/00_setup.sql` — esquema, `_des_texto`,
  `_versiones_cargadas` (`CREATE ... IF NOT EXISTS`: nunca `DROP`), `fn_num`
  (no numérico → NULL) y `fn_fecha`.
- `.../01_troceado.sql` — función SQL `descompuestos.fn_trocear(des TEXT)`:
  `regexp_split_to_table(replace(des, E'\r', ''), E'\n(?=~[A-Z]\\|)') WITH
  ORDINALITY` y `split_part(reg, '|', n + 1)` (R13). Una sola definición para
  ámbito 3 y master; su texto es el sello de troceado (R11).
- `.../02_lineas_coste.sql` — `lineas` (`CREATE IF NOT EXISTS`, `CHECK` de
  origen, PK de negocio, índices) y reconstrucción de `ESTUDIO` y `PLANIF_JO`
  (`DELETE WHERE origen IN (...)` + `INSERT`, R15, R16).
- `.../03_lineas_master.sql` — por lote de versiones: `DELETE` de sus líneas y de
  su cuadre + `INSERT` troceado con flags y origen (R17), y actualización del
  sello; borra también las líneas de versiones que ya no están cargadas.
- `.../04_elementos.sql` (R22, `DROP` + `CREATE AS`), `.../05_cuadre.sql` (R23:
  ámbito 3 y `PLANIF_JO` enteros; master solo del lote), `.../06_views.sql` (R24).
- `config/diccionario/descompuestos.yaml`; `progress/mediciones/` ya tiene la SQL
  y la primera toma de huellas.
- Tests: `tests/test_f097_planificador.py` (dominio, con fixtures),
  `tests/test_f097_ingesta_descompuestos.py` (paso con dobles de Sigrid y
  Postgres), `tests/test_f097_descompuestos.py` (SQL, cableado, YAML,
  diccionario), `tests/test_f097_tiemod_obrparpre.py` (R29). Todos sin red ni BBDD.

## Ficheros a modificar

- `etl_sigrid/infrastructure/postgres/postgres_client.py` — un método
  `reemplazar_filas(schema, tabla, filtro, filas, control)` que hace `DELETE` +
  `COPY` + control en UNA conexión y transacción (`copy_rows` abre una por
  página y no sirve para R8).
- `main.py` — comandos `ingest-descompuestos [--sin-tope]` y
  `build-descompuestos [--sin-tope]`; los dos pasos en `build_pipeline_steps`
  tras `BuildContabilidadStep`; docstrings de `run-all`.
- `config/settings.py` — `DESCOMPUESTOS_PRESUPUESTO_MB` (300) y
  `DEFAULT_CONSUMPTION_SCHEMAS`; `etl_sigrid/domain/diccionario.py`
  (`ESQUEMAS_DEL_DATAMART`); `.env.example`.
- `config/tables_sigrid.yaml` — **solo** `obrparpre`: `incremental_column:
  null` con el comentario medido (R29). Nada más en el YAML.
- `config/diccionario/00_global.yaml` (esquema, `R-DESCOMPUESTO-ORIGEN`,
  `version` + 1, pendientes de las tablas `_`), `config/objetos_pendientes.yaml`
  si `check-declarados` lo pide.
- Listas cerradas de pasos: `test_f024_cli.py`, `test_f047_nocturna.py`,
  `test_f006_publicacion.py`, `test_f079_stg_consultable.py` y las que destape
  `pytest`.
- `docs/ARCHITECTURE.md` (sección del incremental, qué es cada pestaña, formato
  del `des`, el `tiemod` de `obrparpre`), `CLAUDE.md`, `azure-apps/datamart_seg_anual.md`.

## Ficheros que NO se tocan

- `ingest_raw_step.py`, la puerta de F-024, `check-raw-recuentos`: el texto no
  pasa por `raw`. La entrada `obrparpre` sigue excluyendo `des`.
- `sql/stg/*`, `sql/mart/*`, `sql/cierre/*`, `sql/compras/*` (F-038 y F-092
  consumen las llaves `dncpro_id`, `producto_id`, `contrato_id`).
- `sigrid_api_client.py`: `leer_sql` ya valida que es lectura.
- Las otras 13 tablas que declaran `tiemod` sin tenerlo (D14).

## `descompuestos.lineas` (columnas)

| Columna | ESTUDIO / MASTER_* (registro del `des`) | PLANIF_JO (`dncpro`) |
|---|---|---|
| `origen`, `obra_id`, `partida_id`, `ambito_id`, `fase_num` | de `_des_texto` | `dnc.obride`, `paride`, 3, 0 |
| `presupuesto_id`, `orden` | `_des_texto`, ordinal | NULL, `row_number()` por `pos, ide` |
| `codigo_elemento`, `descripcion`, `unidad`, `codigo_alternativo` | campos 1, 2, 5, 7 | `con.cod` de `proide`, `res`, `unimed`, `cod2` |
| `tipo_elemento_codigo`, `tipo_elemento` | campo 16 y `CASE` | NULL, `SIN_TIPO` |
| `naturaleza_codigo`, `naturaleza` | campos 11, 17 | `natide` |
| `rendimiento`, `precio`, `cantidad_total` | campos 14, 3, 4 | `canren`, `pre`, `can` |
| `importe_unitario`, `importe_total`, `es_porcentaje`, `porcentaje`, `base_porcentaje` | R19 | R19 |
| `dncpro_id`, `producto_id` | campo 36 y su `proide` | `ide`, `proide` |
| `proveedor_recomendado_id`, `contrato_id`, `contrato_linea_id`, `fecha_maxima`, `grupo_planificacion_id`, `nivel`, `es_nivel_padre` | NULL | `entide`, `adjctride`, `adjctrlin`, `fec`, `gpcide`, `niv`, `nivpad` |
| `es_version_inicial`, `es_primera_abc`, `es_vigente`, `es_ultima`, `tipo_version`, `texto_version` | solo master | NULL |

`CASE` de tipo (D8): `8` MANO_OBRA, `9` MAQUINARIA, `10` MATERIAL, `11`
SUBCONTRATA, `3` OTROS, `4` PORCENTAJE, `13` MEDIOS_AUXILIARES, vacío SIN_TIPO,
`ELSE 'DESCONOCIDO'`. Los flags de versión se recalculan cada noche con un
`UPDATE` barato: la vigente y la última cambian sin que cambie el texto.

## Encaje y límite

- Módulo como `contabilidad`: permisos por esquema, nadie depende de él, un fallo
  no bloquea `mart`. No lee `stg` (un `DROP ... CASCADE` ajeno no lo rompe).
- Es presupuesto de obra del mismo Sigrid para el seguimiento de coste: cabe en
  este servicio. El cruce planificado-comprado lo hacen F-038/F-092 con las llaves.

## Riesgos y decisiones

- **Inmutabilidad no demostrada del todo** (R1): si T0 ve versiones cerradas que
  cambian, el diseño sigue siendo correcto (las relee por huella) pero su coste y
  su ceguera parcial hay que volver a ponerlos delante del humano.
- **Estado persistente fuera de `--full`**: por primera vez una tabla del
  datamart no se reconstruye de cero. Si se corrompe, `ingest-descompuestos
  --sin-tope` tras vaciar `_versiones_cargadas` la rehace (1,5-2 h). Se documenta.
- **CPU del servidor compartido**: la primera carga y el primer troceado gastan
  créditos del burstable (hoy B2s, bajada pendiente). Se lanzan fuera de la
  nocturna y del horario de oficina (D15).
- **Formato no documentado**: variantes de 19-38 campos; un `|` dentro del texto
  largo desplaza campos: queda visible como `DESCONOCIDO`, con test.
- **Descartado**: segunda entrada del YAML (truncada por `--full`); parsear en
  Python (el precedente es `planif`, en SQL); releer todas las versiones
  posteriores a la vigente (552 versiones, 440 MB, 13-19 min).
