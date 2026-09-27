<!-- specs/F-097-descompuestos-partidas/design.md -->
# F-097 · Diseño

Un esquema módulo nuevo, **`descompuestos`**, construido por un paso propio
`build_descompuestos` que lee solo `raw`. Una ingesta nueva y acotada,
`raw.obrparpre_des` (el texto `des` de Sigrid que hoy se excluye), más
`raw.dncpro`, que ya se ingiere desde F-066. Cifras y consultas:
`progress/spec_F-097.md`. Decisiones abiertas: D1-D11 del mismo fichero.

## Lo que el dato es (medido el 2026-09-27, y corrige en parte a la ficha)

- **Las tres pestañas son dos tablas.** «Descomposición» (COSTE y MASTER COSTE)
  es `obrparpre.des`, texto por (obra, partida, ámbito, fase). «Planificación
  compras» es **`dncpro`**, las líneas del documento de necesidades de la obra
  (`obr.dncide`): 287.282 líneas con partida, 110.146 partidas, 245 obras. No hay
  tabla de líneas de descompuesto: `obrparaux` tiene 0 filas y el módulo de
  presupuestos de Estudios (`ppo`, `ppopro`, `ppoest`) está vacío.
- **El `des` se reescribe con la planificación.** Cada registro sincronizado
  lleva en el campo 36 el `dncpro.ide` del que viene, con el mismo código, precio
  y rendimiento. En ámbito 3 fase 0 hay 42.958 partidas con `des`: **7.866 (18 %)
  son copia de la planificación** y el resto conserva el de Estudios. Por eso la
  pestaña «Descomposición» de COSTE **no es siempre** la referencia de Estudios
  (D1). En ámbito 3 solo hay `des` en la fase 0.
- **«Del ABC en adelante» es medible.** En las 59 obras con versión ABC, el
  98,6 % de las partidas de las versiones ≥ ABC están enlazadas a la
  planificación; antes de la ABC, el 35,6 %. La versión 0 es la foto inicial
  («CIERRE INICIAL_ESTUDIO» en 104 obras, «O.T.» en unas 30).
- **Volumen del master**: 1.616.461 filas con `des`, **2,14 GB** de texto, 196
  obras, 3.023 versiones; desde la ABC, 1,24 GB. Lo que se ingiere aquí (D4):
  versión 0 + primera ABC + vigente ≥ ABC, **unos 105 MB**; más 21,5 MB de
  ámbito 3. Lectura medida: 0,38-0,55 MB/s por la pasarela → **4-6 min** por noche.
- **El cuadre**: Σ `ROUND(precio × rendimiento, 2)` = precio de la partida en el
  36,3 % de las partidas de `ESTUDIO` con precio, y `PLANIF_JO` cuadra con el
  precio de ámbito 3 en el 76,8 %: **el Previsto se construye desde la
  planificación**. Los porcentajes (tipos 4 y 13) llevan en `precio` la base
  acumulada y en `rendimiento` el tanto por uno, así que la fórmula vale igual.
- **Anidamiento: prácticamente no existe.** El `des` es de un nivel;
  `dncpro.niv`/`nivpad` distintos de 0 en 23/21 líneas de 287.282 (D6).
- **`dncpro.pre` no es el precio planificado**: Sigrid lo sobreescribe al
  adjudicar (F-038, 98,2 % igual al contrato). `dncpro.fec` informado en 5
  líneas: el «mes previsto de compra» no existe en la práctica (D10).
- **El caso de Juan.** D05DF210 no existe en Sigrid por ninguna vía (D11); la
  partida es la **04.02** de la 0726 (`partida_id` 419079), la única de Sigrid con
  esa descripción: 10 registros, Σ = 134,35, cuadra; sin planificación todavía.

## Ficheros a crear

- `etl_sigrid/infrastructure/postgres/sql/descompuestos/00_setup.sql` —
  `CREATE SCHEMA IF NOT EXISTS descompuestos`; función
  `descompuestos.fn_num(TEXT) RETURNS NUMERIC` (vacío o no numérico → NULL, sin
  excepción: R14) y `descompuestos.fn_fecha(BIGINT)` (0 → NULL, como
  `retenciones.fn_sigrid_date`).
- `.../descompuestos/01_registros.sql` — `DROP TABLE IF EXISTS
  descompuestos._registros` + `CREATE TABLE ... AS`: trocea
  `raw.obrparpre_des.des` con `regexp_split_to_table(replace(des, E'\r', ''),
  E'\n(?=~[A-Z]\\|)') WITH ORDINALITY` (R12) y proyecta los campos con
  `split_part(reg, '|', n + 1)` (R13). Marca por fila de `obrparpre_des` si
  algún registro está enlazado (`enlazada_planificacion`). Tabla de trabajo con
  prefijo `_`: no se publica y lleva pendiente declarado.
- `.../descompuestos/02_lineas.sql` — `DROP ... CASCADE` + `CREATE TABLE
  descompuestos.lineas`: `UNION ALL` de las ramas `ESTUDIO` (R15),
  `MASTER_INICIAL` y `MASTER_PLANIF_JO` (R17) desde `_registros`, y `PLANIF_JO`
  desde `raw.dncpro` ⨝ `raw.dnc` ⨝ `raw.obr` (R16). Tipo de elemento por `CASE`
  (R20), valores (R19), `CHECK` de `origen`, PK de negocio (R21) e índices por
  `(obra_id, partida_id)` y `producto_id`.
- `.../descompuestos/03_elementos.sql` — `descompuestos.elementos` (R22), desde
  `lineas` y `raw.pro` ⨝ `raw.con` (código del producto por empresa de la obra).
- `.../descompuestos/04_cuadre.sql` — `descompuestos.cuadre_partida` (R23-R24):
  universo = filas de `raw.obrparpre` hoja (sin hijos en `raw.obrparpar`) con
  `pre <> 0` en ámbito 3 fase 0 y en las (obra, versión) de `obrparpre_des`
  ámbito 8; `LEFT JOIN` a la suma por partida de `lineas`.
- `.../descompuestos/05_views.sql` — las tres `v_pbi_*` (R25), `CREATE OR
  REPLACE VIEW` con el origen cableado en el `WHERE`.
- `etl_sigrid/application/steps/build_descompuestos_step.py` — clase
  `BuildDescompuestosStep(PipelineStep)`, `name = "build_descompuestos"`,
  `depends_on = ["ingest_raw"]`, `SUB_PASOS` a nivel de módulo (setup,
  registros, lineas, elementos, cuadre, views) y parada con el nombre del
  sub-paso (R10). Mismo molde que `build_contabilidad_step.py`. Capa
  application.
- `config/diccionario/descompuestos.yaml` — fichas de `lineas`, `elementos`,
  `cuadre_partida` y las tres vistas (R26).
- `tests/test_f097_descompuestos.py` — offline: YAML, texto del SQL sin
  comentarios, cableado del step y de `main.py`, diccionario.
- `tests/test_f097_identidad_ingesta.py` — offline: R4-R7 con dobles del cliente
  y de Postgres (sin red ni BBDD).

## Ficheros a modificar

- `config/tables_sigrid.yaml` — entrada nueva (R1-R3). `exclude_columns`: `med,
  haymed, tex, planif, totinc, totinc2, coepas, varest, tipdes, marseg, canedi,
  impcoe, impOcoe` (las 22 columnas de Sigrid menos las 9 que se quedan).
  `id_column: ide`, `incremental_column: null`, `page_size: 2000`. El `where`:

  ```sql
  DATALENGTH(des) > 0 AND ((amb = 3 AND fas = 0) OR (amb = 8 AND (fas = 0
   OR fas = (SELECT MIN(a.fas) FROM obrfasamb a WHERE a.obride = obrparpre.obride
             AND a.amb = 8 AND UPPER(CAST(a.tex AS nvarchar(4000))) LIKE '%ABC%')
   OR (fas = (SELECT MAX(e.valn) FROM conext e WHERE e.conide = obrparpre.obride
              AND e.cod = '15')
       AND fas >= (SELECT MIN(a.fas) FROM obrfasamb a WHERE ... '%ABC%')))))
  ```

  La referencia correlada `obrparpre.obride` funciona porque `stream_table`
  compone `FROM [dbo].[obrparpre]` sin alias (verificado leyendo el cliente).
- `etl_sigrid/application/steps/ingest_raw_step.py` — la identidad pasa a
  `target_table` (R4): nombre del paso `ingest_raw.<target_table>`,
  `per_table_stats`, `failed_tables`, mensajes y el filtro `only_table` (acepta
  el destino). `fetch_table_schema` y `stream_table` siguen con `source_table`.
- `main.py` — `check-coherencia` y `check-raw-recuentos` por `target_table`
  (R4, R7); comando `build-descompuestos`; `BuildDescompuestosStep` en
  `build_pipeline_steps` tras `BuildContabilidadStep`; docstrings de `run-all`.
- `etl_sigrid/application/steps/build_stg_step.py` — `requeridas` de la puerta
  de F-024 por `target_table` (R4).
- `tests/test_f066_ingesta_raw.py`, `tests/test_f006_raw_ingesta.py`,
  `tests/test_f074_ingesta_censo.py` — `_ingesta()` indexado por `target_table`,
  unicidad por `target_table` (R6) y `TOTAL_TABLAS = 72`. Más las listas
  cerradas de pasos (`test_f024_cli.py`, `test_f047_nocturna.py`,
  `test_f006_publicacion.py`, `test_f079_stg_consultable.py`) y cualquiera que
  destape `pytest` completo.
- `etl_sigrid/domain/diccionario.py` (`ESQUEMAS_DEL_DATAMART`),
  `config/settings.py` (`DEFAULT_CONSUMPTION_SCHEMAS`), `.env.example` (R27).
- `config/diccionario/00_global.yaml` (esquema, regla `R-DESCOMPUESTO-ORIGEN`,
  `version` + 1, pendiente de `descompuestos._registros`), `raw.yaml` (ficha de
  `obrparpre_des`), `config/objetos_pendientes.yaml` si `check-declarados` lo
  pide para `_registros`.
- `docs/ARCHITECTURE.md`, `CLAUDE.md`, `azure-apps/datamart_seg_anual.md` (R28).

## Ficheros que NO se tocan

- `sql/stg/*`, `sql/mart/*`, `sql/cierre/*`: el descompuesto no entra en el
  seguimiento ni en `stg.presupuesto`. La entrada `obrparpre` existente sigue
  excluyendo `des` (traerlo entero serían 2,19 GB por noche).
- `sigrid_api_client.py`: la paginación keyset y el `where` ya bastan.
- `sql/compras/*`: el cruce con comparativos y compras es de F-038 y F-092; aquí
  se dejan las llaves (`dncpro_id`, `producto_id`, `contrato_id`,
  `contrato_linea_id`).
- `mcp-bbdd`: su lista blanca la cambia el humano (T-manual), como en F-056.

## Esquema de `descompuestos.lineas`

| Columna | Origen |
|---|---|
| `origen` | literal por rama; `CHECK` en los cuatro valores |
| `obra_id`, `partida_id`, `ambito_id`, `fase_num` | `obrparpre_des` / `dnc.obride`, `dncpro.paride`, 3, 0 |
| `presupuesto_id` | `obrparpre_des.ide`; NULL en `PLANIF_JO` |
| `orden` | ordinal del registro; en `PLANIF_JO`, `row_number()` por `pos, ide` |
| `codigo_elemento`, `descripcion`, `unidad` | campos 1, 2, 5 / `con.cod` de `proide`, `dncpro.res`, `unimed` |
| `codigo_alternativo` | campo 7 / `dncpro.cod2` |
| `tipo_elemento_codigo`, `tipo_elemento` | campo 16 y su `CASE` (D8) / NULL y `'SIN_TIPO'` |
| `naturaleza_codigo`, `naturaleza` | campos 11, 17 / `dncpro.natide` (id; el texto lo da `auxpronat`) |
| `rendimiento`, `precio`, `cantidad_total` | campos 14, 3, 4 / `canren`, `pre`, `can` |
| `importe_unitario`, `importe_total` | R19 |
| `es_porcentaje`, `porcentaje`, `base_porcentaje` | R20 |
| `dncpro_id`, `producto_id` | campo 36 y su `proide` / `dncpro.ide`, `proide` |
| `proveedor_recomendado_id`, `contrato_id`, `contrato_linea_id`, `fecha_maxima`, `grupo_planificacion_id`, `nivel`, `es_nivel_padre` | solo `PLANIF_JO`: `entide`, `adjctride`, `adjctrlin`, `fec`, `gpcide`, `niv`, `nivpad` |
| `tipo_version`, `texto_version` | solo master: `ABC`/`VIGENTE`/`ABC+VIGENTE`/`INICIAL`, `obrfasamb.tex` |

`CASE` propuesto (D8, a validar por Negocio): `8` MANO_OBRA, `9` MAQUINARIA,
`10` MATERIAL, `11` SUBCONTRATA, `3` OTROS, `4` PORCENTAJE, `13`
MEDIOS_AUXILIARES, vacío SIN_TIPO (las líneas sincronizadas desde la
planificación: se clasifican por naturaleza), `ELSE 'DESCONOCIDO'`.

`partida_codigo` y `ruta_capitulos` NO se copian: la relación con
`stg.partidas` va por `partida_id` en el diccionario (N:1), sin vista que
dependa de `stg` (R9).

## Encaje en la arquitectura

- Esquema módulo como `contabilidad` y `personal`: permisos por esquema y un
  fallo no bloquea (`build_descompuestos` solo depende de `ingest_raw` y nadie
  depende de él). `apply_grants` sigue último y lo cubre al entrar en
  `DEFAULT_CONSUMPTION_SCHEMAS`.
- **Límite de microservicio**: es presupuesto de obra del mismo Sigrid, leído y
  publicado para el seguimiento de coste. Cabe aquí. Cruzar lo planificado con
  lo comprado es consumo (F-038/F-092), no lógica nueva de otro dominio.
- La ventana de negocio (F-025) no aplica: el paso reconstruye todo desde `raw`
  cada noche; el coste está en la lectura, no en el build.

## Riesgos y decisiones

- **Tocar la identidad de la ingesta (D7)** roza la puerta de F-024. Se mitiga
  con R5 (test de equivalencia sobre las 71 entradas) y porque la vista
  `_meta.v_raw_state` ya deriva la tabla del nombre del paso. Alternativa
  descartada salvo que el humano la prefiera: un paso de ingesta propio fuera
  del YAML, que deja `obrparpre_des` sin `check-raw-recuentos` ni puerta.
- **El `where` correlado** se evalúa en cada página. La agregación equivalente
  tardó 71 s en Sigrid; con `page_size` 2000 ninguna página debería acercarse a
  230 s, pero se mide en la primera ingesta (R31). Si una página pasa de 120 s,
  se para y se vuelve a proponer (partir la entrada en ámbito 3 y ámbito 8).
- **El formato del `des` no está documentado.** El mapeo sale de leer registros
  y cruzarlos con `dncpro` (campo 7 = `cod2`, 36 = `ide`) y con el cuadre. Hay
  variantes de 19, 29, 35, 37 y 38 campos; los más cortos solo pierden la cola.
  Un `|` dentro del texto largo (campo 9) desplazaría los campos siguientes: el
  test offline incluye ese caso y el build lo deja visible (tipos `DESCONOCIDO`).
- **Mezclar orígenes** es el error que la feature debe impedir: `CHECK` de
  origen, regla dura, vistas por origen y `ESTUDIO` sin las copias de la
  planificación (R15).
- **Alternativa descartada**: parsear en Python durante la ingesta. `planif`,
  el otro texto de `obrparpre`, se trocea en SQL (`stg/08_plan_mensual.sql`); se
  sigue ese precedente.
- **Fuera, propuesto como F-097b (D5)**: el histórico completo del master desde
  la ABC (1,24 GB; 38-55 min de lectura), con ingesta incremental por versión.
