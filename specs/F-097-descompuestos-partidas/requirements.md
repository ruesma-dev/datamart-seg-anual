<!-- specs/F-097-descompuestos-partidas/requirements.md -->
# F-097 · Requisitos

Los descompuestos de las partidas, publicados con su origen separado y con el
master ENTERO cargado de forma incremental por versión. Cifras (2026-09-27, solo
lectura) y decisiones: `progress/spec_F-097.md` (D1-D11 aprobadas, D5 y D4
cambiadas por el humano, D12-D15 nuevas con su recomendación).

## Glosario

- **des**: `obrparpre.des`, texto de Sigrid con el descompuesto de una fila
  (obra, partida, ámbito, fase). Un **registro** empieza por `~D|`, con campos
  separados por `|`; el texto largo puede llevar saltos de línea dentro.
- **Enlazado**: registro cuyo campo 36 (base 0) es un `dncpro.ide` distinto de 0.
- **Versión**: una fase del ámbito 8 (master) de una obra, `(obra_id, fas)`.
- **Vigente**: `MAX(conext.valn)` con `cod` = `cod_version_master_vigente` de
  `business_rules.yaml`. **Primera ABC**: la versión más baja cuyo
  `obrfasamb.tex` contiene `ABC` (regla de `mart/02_build_fact.sql`).
- **Huella de versión**: `(filas, bytes, huella)` que devuelve la SQL de
  `progress/mediciones/F-097_huella_master.sql` para cada versión.

## Precondición bloqueante

- **R1.** El incremental (R5-R11) no se implementa sin la segunda toma de huellas
  de T0: SI alguna versión anterior a la vigente, que no sea la última de su obra,
  tiene huella distinta de la de `F-097_huella_master_2026-09-27.csv`, ENTONCES
  se para y se vuelve al humano.

## Ingesta del descompuesto (paso `ingest_descompuestos`, D12)

- **R2.** El sistema debe tener un paso `ingest_descompuestos` fuera de
  `tables_sigrid.yaml`, que lee Sigrid con `SigridApiClient.leer_sql` (solo
  `SELECT`) y escribe en `descompuestos._des_texto` y
  `descompuestos._versiones_cargadas`, tablas que `--full` no trunca.
- **R3.** CADA noche el paso debe releer entero el ámbito 3 fase 0 con `des`
  (borrado e inserción en la misma transacción).
- **R4.** El paso debe pedir a Sigrid la huella de todas las versiones del master
  en una sola consulta y guardarla en `_versiones_cargadas`.
- **R5.** Una función pura de dominio `planificar_relectura` debe decidir qué
  versiones releer: las que no están cargadas (nuevas), la vigente de cada obra,
  y las que tienen huella distinta de la guardada; y qué versiones borrar: las
  cargadas que ya no existen en Sigrid.
- **R6.** CUANDO el total a releer supere `DESCOMPUESTOS_PRESUPUESTO_MB`
  (defecto 300), el plan debe tomar primero ámbito 3, vigentes y cambiadas, y
  después nuevas por orden de `(obra_id, fas)` hasta el tope; lo que no quepa se
  deja para la noche siguiente y se registra.
- **R7.** DONDE se ejecute `python main.py ingest-descompuestos --sin-tope`, el
  paso debe ignorar el presupuesto (primera carga, MANUAL).
- **R8.** Cada versión se sustituye en UNA transacción: `DELETE` de sus filas en
  `_des_texto`, `INSERT` de lo leído y actualización de su fila de control; sus
  líneas y su cuadre, igual en el build (R21). Nunca hay dos copias de una versión.
- **R9.** SI las filas leídas de una versión no coinciden con las de su huella,
  ENTONCES esa versión se revierte, se registra y el paso termina `FAILED` al
  final sin dejar de procesar las demás.
- **R10.** La lectura de una versión va por `obride`, `amb = 8` y `fas` (índice
  `oaf` de Sigrid), paginada por `ide` con 1.000 filas como máximo.
- **R11.** Cada versión cargada guarda el `batch_id` y el sello del SQL de
  troceado con que se trocearon sus líneas.

## Troceado y líneas (`descompuestos.lineas`)

- **R12.** Una fila por registro de `des` y una por línea de `dncpro`, con
  `origen` NOT NULL restringido a `ESTUDIO`, `PLANIF_JO`, `MASTER_INICIAL`,
  `MASTER_PRE_ABC` y `MASTER_PLANIF_JO` (D13).
- **R13.** El troceado parte por salto de línea seguido de `~<letra>|`, nunca por
  cualquier salto, y mapea por posición: 1 código, 2 descripción, 3 precio, 4
  cantidad total, 5 unidad, 7 código alternativo, 11 código de naturaleza, 14
  rendimiento, 16 tipo, 17 naturaleza, 36 enlace. Ausente o vacío es NULL.
- **R14.** SI un campo numérico no es un número, ENTONCES se publica NULL y el
  build no falla.
- **R15.** `ESTUDIO`: ámbito 3 fase 0 de las partidas sin ningún registro
  enlazado (D1).
- **R16.** `PLANIF_JO`: `raw.dncpro` de la necesidad de su obra (`obr.dncide`),
  `paride <> 0`, ámbito 3, fase 0, orden por `pos, ide`, con proveedor
  recomendado, contrato y línea adjudicados, fecha máxima, grupo, naturaleza,
  nivel y marca de nivel padre (D6, D10).
- **R17.** Master: `MASTER_INICIAL` la versión 0; `MASTER_PLANIF_JO` las
  versiones ≥ primera ABC; `MASTER_PRE_ABC` el resto. Todas llevan
  `es_version_inicial`, `es_primera_abc`, `es_vigente`, `es_ultima`,
  `tipo_version` (la regla de `mart`) y `texto_version`.
- **R18.** Cada fila lleva `obra_id`, `partida_id`, `presupuesto_id` (NULL en
  `PLANIF_JO`), `ambito_id`, `fase_num`, `orden` (desde 1), `dncpro_id` y
  `producto_id`.
- **R19.** `rendimiento`, `precio`, `importe_unitario = ROUND(precio ×
  rendimiento, 2)`, `cantidad_total`, `importe_total = ROUND(cantidad_total ×
  precio, 2)`; `tipo_elemento_codigo` y `tipo_elemento` por `CASE` con `ELSE
  'DESCONOCIDO'` (D8); `es_porcentaje`, `porcentaje` y `base_porcentaje` para los
  tipos 4 y 13.
- **R20.** Clave de negocio única `(origen, partida_id, ambito_id, fase_num,
  orden)`.
- **R21.** Las líneas del master solo se retrocean para las versiones releídas
  esa noche o cuyo sello de troceado no es el vigente, dentro del presupuesto
  (R6); ámbito 3 y `PLANIF_JO` se reconstruyen enteros cada noche.

## Catálogo, controles y vistas

- **R22.** `descompuestos.elementos`: una fila por `(obra_id, codigo_elemento)`
  con descripción y unidad más frecuentes, tipo, líneas por origen y
  `producto_id` si hay enlace o el código es de un producto de la empresa (D9).
- **R23.** `descompuestos.cuadre_partida`: una fila por (origen, partida, ámbito,
  fase) de cada partida hoja con precio distinto de 0 en ámbito 3 fase 0 y en
  todas las versiones cargadas, con `precio_partida` de `raw.obrparpre`,
  `suma_descompuesto`, `diferencia` y `estado` ∈ `CUADRA` (≤ 0,01), `NO_CUADRA`,
  `SIN_DESCOMPUESTO` y `SUSTITUIDO_POR_PLANIFICACION`.
- **R24.** `v_pbi_estudio`, `v_pbi_planif_jo` y `v_pbi_master_planif_jo`, cada
  una con un origen cableado.

## Paso de build, esquema y documentación

- **R25.** Paso `build_descompuestos` con `depends_on = ["ingest_raw",
  "ingest_descompuestos"]`; los dos en `run-all` tras `build_contabilidad` y
  antes de `build_cierre`; comandos sueltos `ingest-descompuestos` y
  `build-descompuestos`. SI un sub-paso falla, ENTONCES `FAILED` con su nombre.
- **R26.** El SQL de `descompuestos` lee solo `raw` y su propio esquema.
- **R27.** `descompuestos` en `ESQUEMAS_DEL_DATAMART` y
  `DEFAULT_CONSUMPTION_SCHEMAS`; fichas en `config/diccionario/descompuestos.yaml`
  (las tablas `_` como pendientes o no publicadas); regla dura
  `R-DESCOMPUESTO-ORIGEN` y `version` + 1 en `00_global.yaml`.
- **R28.** `docs/ARCHITECTURE.md`, `CLAUDE.md` y `azure-apps/datamart_seg_anual.md`
  en el mismo trabajo.

## El `tiemod` que no existe (hallazgo de la spec)

- **R29.** La entrada `obrparpre` de `tables_sigrid.yaml` debe declarar
  `incremental_column: null`, con el comentario de lo medido (22 columnas en
  Sigrid, sin `tiemod`; `_source_tiemod` a NULL, degradado en silencio en
  `ingest_raw_step.py:279`), y un test offline debe exigirlo.

## Verificación manual (humano, contra Azure)

- **R30.** 0726 04.02 (`partida_id` 419079): 10 líneas `ESTUDIO` = 134,35
  `CUADRA`, las mismas 10 en `MASTER_INICIAL` (v0) y en `MASTER_PRE_ABC` (v1), 0
  en `PLANIF_JO`. 0695 03.05.02 (377070): 26 líneas `PLANIF_JO` que cuadran con
  177,95 y `ESTUDIO` `SUSTITUIDO_POR_PLANIFICACION`.
- **R31.** Primera carga: 3.023 versiones y 1.616.461 filas de texto, tiempo
  (estimado 65-94 min) y MB. Noche siguiente: minutos de `ingest_descompuestos`
  (estimado 4-6) y de `build_descompuestos`, y disco antes y después.
