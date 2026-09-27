<!-- specs/F-097-descompuestos-partidas/requirements.md -->
# F-097 · Requisitos

Los descompuestos de las partidas, publicados con su origen separado. Las cifras
que sostienen cada requisito son del 2026-09-27, medidas en solo lectura, y están
en `progress/spec_F-097.md`. **Las decisiones D1-D11 de ese fichero condicionan
esta spec**: los valores de aquí son los que se recomiendan.

## Glosario

- **des**: `obrparpre.des`, texto ilimitado de Sigrid con el descompuesto de una
  fila (obra, partida, ámbito, fase). Un **registro** empieza por `~D|` y trae
  campos separados por `|`; el texto largo puede llevar saltos de línea dentro.
- **Enlazado**: registro cuyo campo 36 (base 0) es un `dncpro.ide` distinto de 0,
  es decir, que viene de la planificación de compras del jefe de obra.
- **Primera ABC**: la versión master (ámbito 8) más baja cuyo `obrfasamb.tex`
  contiene `ABC`, la misma regla que `mart/02_build_fact.sql`.
- **Orígenes**: `ESTUDIO`, `PLANIF_JO`, `MASTER_INICIAL`, `MASTER_PLANIF_JO` (D2).

## Ingesta

- **R1.** El sistema debe declarar en `config/tables_sigrid.yaml` una entrada con
  `source_table: obrparpre` y `target_table: obrparpre_des` que solo conserve las
  columnas `ide, obride, paride, amb, fas, can, pre, haydes, des` y lleve
  `page_size` de 2000 como máximo.
- **R2.** El `where` de esa entrada debe traer solo filas con `DATALENGTH(des) > 0`
  y de uno de estos grupos: ámbito 3 fase 0; ámbito 8 fase 0; ámbito 8 primera
  ABC; ámbito 8 versión vigente cuando sea mayor o igual que la primera ABC (D4).
- **R3.** El código del campo extendido de versión vigente que use ese `where`
  debe ser el de `business_rules.yaml` (`cod_version_master_vigente`), y el
  patrón de ABC el mismo `'%ABC%'` que `mart/02_build_fact.sql`.
- **R4.** La identidad de una entrada de ingesta debe ser su `target_table` (D7):
  el nombre del paso en `_meta.etl_runs`, el filtro `--table`, las tablas
  requeridas por la puerta de F-024 y las claves de `check-raw-recuentos`.
- **R5.** MIENTRAS `source_table == target_table`, que es el caso de las 71
  entradas actuales, el nombre de paso, la puerta y los recuentos deben quedar
  exactamente como hoy.
- **R6.** SI dos entradas del YAML declaran el mismo `target_table`, ENTONCES el
  test de unicidad debe fallar (sustituye al de `source_table` de F-066).
- **R7.** `check-raw-recuentos` debe contar en Sigrid con `source_table` + `where`
  y en `raw` con `target_table`.

## Paso y esquema

- **R8.** El sistema debe crear el esquema `descompuestos` (D3) con un paso propio
  `build_descompuestos`, con `depends_on = ["ingest_raw"]`, dentro de `run-all`
  después de `build_contabilidad` y antes de `build_cierre`, y un comando suelto
  `python main.py build-descompuestos`.
- **R9.** El SQL de `descompuestos` debe leer solo del esquema `raw`: ni `stg`,
  ni `mart`, ni otro módulo (un `DROP ... CASCADE` ajeno no puede destruirlo).
- **R10.** SI un sub-paso falla, ENTONCES el paso debe terminar `FAILED` con el
  nombre del sub-paso y no ejecutar los siguientes.

## Líneas de descompuesto (`descompuestos.lineas`)

- **R11.** El sistema debe publicar una fila por registro de `des` y una por
  línea de `dncpro`, con `origen` NOT NULL restringido a los cuatro orígenes.
- **R12.** El troceado debe partir por salto de línea seguido de `~<letra>|` y no
  por cualquier salto: un salto dentro del texto largo no crea registro.
- **R13.** Cada registro debe mapear por posición (base 0): 1 código, 2
  descripción, 3 precio, 4 cantidad total, 5 unidad, 7 código alternativo, 11
  código de naturaleza, 14 rendimiento, 16 tipo de elemento, 17 naturaleza, 36
  enlace a `dncpro`. Un campo ausente o vacío es NULL.
- **R14.** SI un campo numérico no es un número, ENTONCES la fila se publica con
  ese valor NULL y el build no falla.
- **R15.** `ESTUDIO`: ámbito 3 fase 0, solo de las partidas cuyo `des` no tiene
  ningún registro enlazado (D1). Las que sí lo tienen no se publican como
  `ESTUDIO`: su texto es copia de `PLANIF_JO`.
- **R16.** `PLANIF_JO`: `raw.dncpro` de la necesidad de la propia obra
  (`obr.dncide = dnc.ide`) con `paride <> 0`; ámbito 3, fase 0, orden por
  `pos, ide`; con proveedor recomendado, contrato y línea de contrato
  adjudicados, fecha máxima, grupo de planificación, naturaleza, nivel y marca de
  nivel padre, y `producto_id`.
- **R17.** `MASTER_INICIAL`: ámbito 8 fase 0. `MASTER_PLANIF_JO`: ámbito 8,
  versiones mayores o iguales que la primera ABC, con `tipo_version` (`ABC` o
  `VIGENTE`, o las dos) y el texto de la versión.
- **R18.** Cada fila debe llevar `obra_id`, `partida_id`, `presupuesto_id` (NULL
  en `PLANIF_JO`), `ambito_id`, `fase_num`, `orden` (desde 1, dentro de la
  partida y el origen), `dncpro_id` (enlace; en `PLANIF_JO` su propio id) y
  `producto_id` (el de `dncpro`, si hay enlace).
- **R19.** Valores: `rendimiento`, `precio`, `importe_unitario =
  ROUND(precio × rendimiento, 2)`, `cantidad_total` e `importe_total =
  ROUND(cantidad_total × precio, 2)`.
- **R20.** `tipo_elemento_codigo` en crudo y `tipo_elemento` traducido por
  `CASE` con rama `ELSE 'DESCONOCIDO'` (D8); `es_porcentaje` para los tipos 4 y
  13, con `porcentaje = rendimiento × 100` y `base_porcentaje = precio`.
- **R21.** La clave de negocio debe ser `(origen, partida_id, ambito_id,
  fase_num, orden)` y ser única.

## Catálogo de elementos (`descompuestos.elementos`)

- **R22.** Una fila por `(obra_id, codigo_elemento)` con código no vacío: la
  descripción y la unidad más frecuentes, el tipo, las líneas por origen y
  `producto_id` si alguna línea enlaza a `dncpro` o el código es el de un
  producto de la empresa de la obra (D9).

## Controles (`descompuestos.cuadre_partida`)

- **R23.** Una fila por (origen, partida, ámbito, fase) para cada partida hoja
  con precio distinto de 0 en ámbito 3 fase 0 y en las versiones master
  ingeridas, con `precio_partida` de `raw.obrparpre` (el mismo que
  `stg.presupuesto.precio`), `suma_descompuesto`, `diferencia` y `estado`.
- **R24.** `estado` ∈ `CUADRA` (|diferencia| ≤ 0,01), `NO_CUADRA`,
  `SIN_DESCOMPUESTO` (el tanto alzado) y `SUSTITUIDO_POR_PLANIFICACION` (el
  `des` de ámbito 3 es copia de `PLANIF_JO`). `PLANIF_JO` se cuadra contra el
  precio de ámbito 3 fase 0.
- **R25.** Tres vistas `v_pbi_estudio`, `v_pbi_planif_jo` y
  `v_pbi_master_planif_jo`, cada una con un solo origen cableado, para Power BI.

## Diccionario y documentación

- **R26.** `config/diccionario/descompuestos.yaml` con ficha de cada tabla y
  vista, la clave, las relaciones y las advertencias con cifra; ficha de
  `raw.obrparpre_des` en `raw.yaml`; regla dura `R-DESCOMPUESTO-ORIGEN` en
  `00_global.yaml` («nunca sumar sin fijar `origen`») y `version` + 1.
- **R27.** `descompuestos` debe entrar en `ESQUEMAS_DEL_DATAMART` y en
  `DEFAULT_CONSUMPTION_SCHEMAS`.
- **R28.** `docs/ARCHITECTURE.md` (72 tablas, el esquema y la trampa del
  `des`), `CLAUDE.md` (mapa) y `azure-apps/datamart_seg_anual.md`, en el mismo
  trabajo.

## Verificación manual (humano, contra Azure)

- **R29.** La partida 04.02 «FORJ. RETICULAR 35+10» de la 0726 (`partida_id`
  419079) debe dar 10 líneas `ESTUDIO` que suman 134,35 y `CUADRA`, las mismas 10
  en `MASTER_INICIAL`, y 0 en `PLANIF_JO`.
- **R30.** La 03.05.02 de la 0695 (`partida_id` 377070) debe dar 26 líneas
  `PLANIF_JO` y estado `CUADRA` frente a 177,95, y `SUSTITUIDO_POR_PLANIFICACION`
  en `ESTUDIO`.
- **R31.** Coste medido: minutos de ingesta de `obrparpre_des` (estimado 4-6) y
  del build, filas y MB de las tablas nuevas, y ocupación del disco antes y
  después.
