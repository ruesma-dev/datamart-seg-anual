<!-- specs/F-080-vencimientos-forma-pago-y-texto-factura/tasks.md -->
# F-080 · Tareas

> **Reescrito el 2026-09-11** para cuadrar con `requirements.md` y `design.md`
> corregidos, y **revisado el mismo día con la CUARTA MEDICION**: la anulación es
> `con.fecbaj <> 0` (medida, 8 de 8 contra la captura), `pag.padide` y `con.serie`
> están a 0 en los 255.074 efectos, y la serie sale de `compras.fn_serie`. Titular
> de fondo: **el efecto de pago ES un documento** (`raw.pag` son «Propiedades de
> `con`», `tip = 25`), así que su código, su descripción y su estado se **leen** de
> `raw.con` / `raw.conest`; no se derivan. Cada tarea que cambia de sentido lleva
> su línea *Corrige:*.

Rigor `estandar`: **fase RED obligatoria** en los requisitos centrales (R1–R3,
R7–R12, R16–R19, R22–R26, R38–R41) con la traza real pegada en
`progress/impl_F-080.md`, más cobertura de las líneas cambiadas y campaña de
mutación muestreada. Rama `feature/F-080-vencimientos-forma-pago-y-texto-factura`.
Un commit por tarea (`F-080 Tn: ...`). `git add` de ficheros concretos, nunca `-A`.

**PRECONDICIÓN DURA DEL IMPLEMENTER (R20).** Antes de T1, comprobar que existe
`sql/compras/04_formas_pago.sql` en el árbol y que `BuildComprasStep` lo declara
como sub-paso. Si falta, F-080 se marca `blocked` y se para: no se duplica la
dimensión desde `raw.auxpag`. **Que `compras.formas_pago` esté construida en la
base NO bloquea al implementer**: es verificación MANUAL del humano (T0 bis),
exigible antes de las verificaciones contra la base y no antes de escribir
código. F-073 está cerrada pero **no desplegada** —esa vista no existe en Azure
hasta que corra una nocturna con la imagen nueva— y todos los tests de F-080 son
sobre el **texto** del SQL: ningún agente ejecuta SQL contra la base.

## Medir antes de escribir nada (todo solo lectura)

- [x] T0: Verificar la precondición DURA de F-073 en el árbol: que `sql/compras/04_formas_pago.sql` existe y que `etl_sigrid/application/steps/build_compras_step.py` lo declara como sub-paso; anotar el resultado en `progress/impl_F-080.md`  |  Verificación: `ls etl_sigrid/infrastructure/postgres/sql/compras/04_formas_pago.sql` y `grep -n formas_pago etl_sigrid/application/steps/build_compras_step.py` devuelven resultado; si falta cualquiera de las dos, `blocked` en `progress/current.md` y parada
  - *Corrige:* antes T0 exigía además que `compras.formas_pago` estuviera **construida en la base** y bloqueaba si no; era falso que hiciera falta para implementar (F-073 está cerrada pero no desplegada, y los tests de F-080 leen el TEXTO del SQL), así que esa mitad pasa a T0 bis.
- [ ] T0 bis: Comprobar que `compras.formas_pago` está construida en la base, **antes de las verificaciones contra la base** (T7 y T26) y no antes de escribir código  |  Verificación: MANUAL (humano) — `SELECT count(*) FROM compras.formas_pago;`; si no existe, las verificaciones contra la base esperan a la primera nocturna con la imagen nueva, pero el desarrollo sigue
- [x] T1: Medir en SOLO LECTURA (cliente del ETL, no el MCP: `raw` y Sigrid no son consultables por él) los nombres y tipos exactos de columna de `raw.pag`, `raw.con` (`cod`, `res`, `est` y **`fecbaj`**, la marca de anulación de R40), `raw.conest` (la clave por la que se une con `con.est` filtrando `tip = 25`), `raw.rpa` (`fecrem`, `imptot`, banco), `auxnap`, `auxban` —y **por qué clave se une** `banban`/`bansuc`, que es jerárquica y no consta—, `cua` y los campos de pago de `dcf`; anotarlos en `progress/impl_F-080.md`  |  Verificación: MANUAL (humano) — la tabla de nombres medidos consta en el informe antes de existir ningún SQL nuevo
  - *Corrige (2026-09-10):* antes solo medía `raw.pag` y los catálogos, y daba por inexistentes el código y el estado del efecto; era falso, viven en `raw.con` / `raw.conest` (DA-9).
  - *Corrige (2026-09-11):* antes medía además «la columna de serie» de `raw.con` para R38 y `pag.padide` para R40; los dos están a 0 en los 255.074 efectos, así que ahí no queda nada que medir: la serie sale de `compras.fn_serie` y la anulación de `con.fecbaj`.
- [x] T2: Medir y anotar: efectos cuyo `conide` es factura de compra (el recuento de `compras.vencimientos`), reparto de `con.est` de esos efectos contra los 10 estados de `raw.conest` (R10), efectos con `remide <> 0` (R41), documentos con `con.tex` por tipo 15 y 44, facturas que no cuelgan de ningún contrato (R30) y el `incremental_column` real de `auxnap`, `auxban` y `rpa` en `INFORMATION_SCHEMA` (R3)  |  Verificación: MANUAL (humano) — cifras en el informe, base de las fichas de R11, R30 y R41
- [x] T3: Medición A del coste de ventana (R4a): cronometrar páginas de `con` con y sin `tex`, a `page_size` 10.000 y 5.000, en solo lectura contra Sigrid, anotando segundos y bytes por página  |  Verificación: MANUAL (humano) — tabla de cuatro combinaciones en `progress/impl_F-080.md`
- [x] T4: **Verificar** el hecho ya medido de la anulación (R39, R40), no investigarlo: (a) sobre `FR25/04222`, que los efectos con `con.fecbaj <> 0` son exactamente los tres que la captura pinta en rojo con aspa y que los cinco vivos suman 87.854,56, más la retención viva 92.478,49 —los dos números de la cabecera—; (b) que el recuento de baja sigue siendo ~89.095 de 255.074 (34,9 %); (c) que `pag.padide` sigue a 0 en toda la tabla, que es lo que deja `efecto_origen_id` sin publicar  |  Verificación: MANUAL (humano) — las tres comprobaciones, con su SQL y su resultado, en `progress/impl_F-080.md`; si alguna NO sale, se para y se avisa antes de escribir T10, porque el filtro de importes depende de ella
  - *Corrige (2026-09-10):* antes T4 comprobaba si `row_number()` reproducía los códigos `_01`, `_02` de la captura; falso, `con.cod` los almacena literales (R12).
  - *Corrige (2026-09-11):* antes T4 era una **investigación** con tres candidatos (un estado de `raw.conest`, un campo de `raw.con`, `pag.padide`) y su veredicto decidía qué publicar; ya está medido: la marca es `con.fecbaj` y el enlace al origen no existe. Queda verificar, no descubrir.

## La ingesta

- [x] T5: Escribir `tests/test_f080_ingesta.py` con los asserts de R1 (`con` deja una sola exclusión, `ima`), R2 (`dcf`, `dca` y `ctr` no cambian), R3 (**tres** altas: `auxnap`, `auxban` y `rpa`, con el `incremental_column` medido en T2) y R6 (fichas de `raw` para las tres)  |  Verificación: `pytest tests/test_f080_ingesta.py` en ROJO; traza pegada
  - *Corrige:* antes eran dos altas y la tabla de remesas se daba por no identificada; era falso, está medida y es `raw.rpa` (3.909 remesas de pago), a la que apunta `pag.remide`.
- [ ] T6: Modificar `config/tables_sigrid.yaml`: sacar `tex` de `con` y dar de alta `auxnap`, `auxban` y `rpa` con su comentario de por qué entran; actualizar `config/diccionario/raw.yaml` (recuento de exclusiones de `con` de 2 a 1 y **tres** fichas nuevas); subir `TOTAL_TABLAS` de 65 a **68** en `tests/test_f074_ingesta_censo.py`  |  Verificación: `pytest tests/test_f080_ingesta.py tests/test_f074_ingesta_censo.py tests/test_f006_raw_ingesta.py` en verde
  - *Corrige:* antes subía `TOTAL_TABLAS` a 67 porque contaba dos altas; son tres.
- [ ] T7: Medición B del coste de ventana (R4b): `python main.py ingest --table con --full` contra el Postgres de dev y comparar la duración de la fila `ingest_raw.con` de `_meta.etl_runs` con la de las noches anteriores  |  Verificación: MANUAL (humano) — es una ESCRITURA; ningún agente la ejecuta
- [ ] T8: Contrastar la medición B con el presupuesto de referencia de `design.md` §6 (**4 h**) y anotar el delta; SI lo supera, dejar **aviso por escrito** en `progress/impl_F-080.md` y en `progress/current.md`, y seguir adelante (R5, DA-5)  |  Verificación: MANUAL (humano) — el delta y el aviso constan en el informe; **no es una puerta**: no se marca `blocked`, no se para el despliegue y no se baja `page_size`, que lo decide el humano con el dato delante
  - *Corrige:* antes obligaba a bajar `page_size` de `con` a 5.000 y a repetir T7 antes de desplegar; era falso que fuese una puerta, el humano lo zanjó: «puedes poner 4h, pero que no pare nada».

## Los vencimientos

- [ ] T9: Escribir en `tests/test_f080_sql.py` los asserts de R7 (filtro por `raw.dcf` y `ADD PRIMARY KEY (vencimiento_id)`), R8 (catálogos resueltos a nombre), R9 (`fn_sigrid_date` en las tres fechas), R10 (`estado_pago` sale de `LEFT JOIN raw.conest` con `tip = 25` sobre `c.est`; ni un `CASE` sobre `fecrea`), R12 (`codigo_efecto` es `c.cod` y `descripcion_efecto` es `c.res`, **sin** `row_number()`, sin `lpad` y sin `ordinal_efecto`), R38 (`serie_efecto` sale de `compras.fn_serie(c.cod)`: el test exige esa llamada y **prohíbe** un `substring`/`left` propio que la duplique) y R41 (`LEFT JOIN raw.rpa` por `p.remide`)  |  Verificación: `pytest tests/test_f080_sql.py` en ROJO (el fichero SQL no existe); traza pegada
  - *Corrige (2026-09-10):* antes este test exigía `row_number()` con `ORDER BY p.ide` y admitía un `estado_pago` derivado de `fecrea`; ahora **prohíbe** las dos derivaciones (DA-8).
  - *Corrige (2026-09-11):* antes el assert de R38 prohibía «parsear el código» y exigía una columna de serie; era falso que esa columna sirviera (`con.serie` está a 0), y la derivación correcta ya existe en el repositorio: `compras.fn_serie`, en `sql/compras/00_setup.sql`, usada por `01_documentos.sql`. Se reutiliza, no se escribe otra.
- [ ] T10: Crear `sql/compras/05_vencimientos.sql` con la tabla `compras.vencimientos` usando los nombres medidos en T1: `JOIN raw.con c ON c.ide = p.ide` (el documento DEL EFECTO, DA-9), `LEFT JOIN raw.con cf` para el código de la factura, `LEFT JOIN raw.conest` para el estado y `LEFT JOIN raw.rpa` para la remesa; `codigo_efecto = c.cod` literal  |  Verificación: `pytest tests/test_f080_sql.py` en verde
  - *Corrige:* antes `codigo_efecto` quedaba condicionado al «veredicto de T4»; era falso que dependiera de nada, está almacenado en `con.cod`.
- [ ] T11: **Camino A, ya decidido** (R39, R40): añadir a `compras.vencimientos` las columnas `efecto_anulado` (`c.fecbaj <> 0`) y `fecha_anulacion` (`compras.fn_sigrid_date(c.fecbaj)`), con su assert en `tests/test_f080_sql.py`, y **NO** publicar `efecto_origen_id` —el test debe prohibir esa columna y cualquier autojoin que intente deducir el origen por importes—  |  Verificación: `pytest tests/test_f080_sql.py` en verde, con el assert de las dos columnas nuevas y el de ausencia de `efecto_origen_id`
  - *Corrige:* antes T11 era una bifurcación («SI T4 identifica… SI NO, sin agregar importes») que dejaba el camino sin decidir hasta la implementación; la 4.ª medición lo cerró el 2026-09-11 en el camino A: `con.fecbaj` marca la anulación (8 de 8 contra la captura) y `pag.padide` está a 0, así que no hay enlace al origen que publicar.

## La forma de pago y el control

- [ ] T12: Ampliar `tests/test_f080_sql.py` con los asserts de R16 (lee de `compras.formas_pago`), R17 (`plazo_formula` verbatim, ningún `dias_pago`), R18 (naturaleza, medio de pago, cuenta y banco resueltos a nombre), R19 (el resumen de efectos agrega ANTES de unir y **sus importes agregados filtran los efectos de baja**: el test exige el `WHERE NOT efecto_anulado` —o el `filter` equivalente— en el CTE, y falla si hay un `SUM` sin ese filtro), R28 (la misma expresión `COALESCE(...contrato_id_directo...)` que `03_views.sql`), R29 (sin filtro de discrepancias) y R21 (`01_documentos.sql`, `02_fact_linea.sql` y `03_views.sql` no cambian)  |  Verificación: `pytest tests/test_f080_sql.py` en ROJO; traza pegada
  - *Corrige:* antes el assert de R19 **prohibía** cualquier importe agregado «mientras R40 siga sin resolverse»; R40 quedó resuelto el 2026-09-11, así que lo que se exige ya no es la ausencia de importes sino el filtro que los hace ciertos (sin él, uno de cada tres efectos es un fantasma).
- [ ] T13: Crear `sql/compras/06_pago_factura.sql` con `compras.v_facturas_pago` y `compras.v_control_forma_pago`  |  Verificación: `pytest tests/test_f080_sql.py` en verde

## El texto

- [ ] T14: Escribir `tests/test_f080_texto.py` sobre la función pura de parseo: memo de tres comentarios en orden descendente, memo con un bloque sin sello, memo con la línea automática de la aplicación, memo de un solo bloque, memo vacío, y el invariante de reconstrucción de R26  |  Verificación: `pytest tests/test_f080_texto.py` en ROJO (el módulo no existe); traza pegada
- [ ] T15: Crear `etl_sigrid/domain/texto_comentarios.py` con `SEPARADOR_BLOQUES`, `SELLO_COMENTARIO` y `partir_memo()`, sin un solo import de infraestructura  |  Verificación: `pytest tests/test_f080_texto.py` en verde
- [ ] T16: Ampliar `tests/test_f080_sql.py` con los asserts de R22 (`compras.documento_texto`, filtro `tip IN (15, 44)` y PK `documento_id`), R23 (`compras.documento_comentarios` es **TABLA** —`CREATE TABLE ... AS SELECT` en el build nocturno—, con `WITH ORDINALITY` para `orden`, `orden` 1 = el más reciente y `ADD PRIMARY KEY (documento_id, orden)` declarada), R24 (el SQL usa los literales del módulo de dominio, comparados contra la constante importada) y R25 (rama de bloque sin sello con `sello_reconocido` en falso y el bloque entero como cuerpo)  |  Verificación: `pytest tests/test_f080_sql.py` en ROJO; traza pegada
  - *Corrige:* antes el objeto era la vista `compras.v_documento_comentarios`; era falso que quedara por decidir, el humano lo zanjó («guárdala como tabla y como texto») y R27, el cronómetro de 30 s que condicionaba la materialización, está retirado (DA-6).
- [ ] T17: Crear `sql/compras/07_texto.sql` con **las dos tablas**: `compras.documento_texto` y `compras.documento_comentarios`, ambas con su PK declarada  |  Verificación: `pytest tests/test_f080_sql.py` en verde

## El cableado del step

- [ ] T18: Escribir en `tests/test_f080_sql.py` (o fichero de pipeline propio) el assert de que `BuildComprasStep.SUB_PASOS` declara `vencimientos`, `pago_factura` y `texto` en el orden de sus ficheros, y que **los tres** construyen tabla y declaran `target_schema`/`target_table` (el de texto construye dos)  |  Verificación: `pytest` del fichero en ROJO; traza pegada
  - *Corrige:* antes decía «los dos que construyen tabla»; era falso, son los tres, porque los comentarios ya no son una vista.
- [ ] T19: Añadir los tres sub-pasos a `etl_sigrid/application/steps/build_compras_step.py`  |  Verificación: `pytest` del fichero en verde

## El diccionario y el cierre

- [ ] T20: Escribir `tests/test_f080_diccionario.py`: ficha con `clave_negocio` declarada para los **cinco** objetos de `compras` y las **tres** tablas nuevas de `raw`; la de `compras.vencimientos` dice que `estado_pago` **se lee** de `raw.conest` con `tip = 25` (R10), que `fecrea = 0` no significa «vivo» con las dos cifras (R11), que **sumar los importes de todos los efectos de una factura duplica** y que se filtra con `efecto_anulado` (R39: 89.095 de 255.074, 34,9 %), y que **`efecto_origen_id` no se publica** porque `pag.padide` está a 0 (R40); la de `v_control_forma_pago` declara el grano por par y las facturas fuera (R28, R30); la de `documento_comentarios` declara que es tabla materializada y qué pasa con lo que no casa (R23, R25); `00_global.yaml` en versión 21 (R32)  |  Verificación: `pytest tests/test_f080_diccionario.py` en ROJO; traza pegada
- [ ] T21: Escribir las cinco fichas de `config/diccionario/compras.yaml` con grano, clave y trampas, y la nota de deuda con F-037 (R35)  |  Verificación: `pytest tests/test_f080_diccionario.py` en verde
- [ ] T22: Subir `version` a 21 en `config/diccionario/00_global.yaml` con su nota de qué cambia, tras comprobar que el fichero está en 20 (R32); si no estuviera en 20, subir al siguiente número real y decirlo en el informe
  - *Corrige:* antes subía a 20 desde la 19; F-081 gastó la 20 el 2026-09-11 al corregir la mentira de `auxefp`.  |  Verificación: `pytest tests/test_f006_publicacion.py tests/test_f080_diccionario.py` en verde
- [ ] T23: Anotar la deuda recíproca en la ficha de F-037 de `harness/features.json`: cuando llegue, decide si absorbe `compras.vencimientos` o lo deja como vista suya (R35)  |  Verificación: `bash harness/init.sh` en verde (valida el JSON) y la frase consta en la ficha
- [ ] T24: Ejecutar la suite completa y la puerta de cobertura de las líneas cambiadas  |  Verificación: `bash harness/init.sh` en verde
- [ ] T25: Campaña de mutación y análisis de supervivientes sobre `domain/texto_comentarios.py` y el step  |  Verificación: `python -m harness.mutacion --feature F-080`; si genera 0 mutantes, campaña MANUAL con la tabla fila a fila (fichero, línea, texto exacto original → mutado, resultado y nº de fallos) que exige `CHECKPOINTS.md` C4 bis
- [ ] T26: Dejar en `progress/current.md` las verificaciones MANUAL con su comando exacto: recuentos de los cinco objetos de `compras` y de las tres tablas nuevas de `raw`, reparto de `estado_pago` contra los 10 estados, recuento de `efecto_anulado` contra los 89.095 medidos (R40), efectos en remesa (R41), prueba reconstructiva del memo (R26) sobre una muestra y sobre el total, `check-unicidad`, `check-declarados`, `check-diccionario` y la publicación del diccionario  |  Verificación: MANUAL (humano) — las ejecuta el humano; ningún agente escribe contra Azure
  - *Corrige:* antes pedía cronometrar `compras.v_documento_comentarios` (R27); era falso que hiciera falta, ese requisito está retirado y el objeto es una tabla materializada en la nocturna.
- [ ] T27: Dejar anotada, también como MANUAL, la batería de tres preguntas al MCP sin explicarle nada en el prompt (R34): cuándo vence una factura y si está pagada, qué dice el texto de una factura retenida, y qué facturas no cuadran con la forma de pago del contrato  |  Verificación: MANUAL (humano) — respuestas pegadas en `progress/current.md`
- [ ] T28: Escribir `progress/impl_F-080.md` (≤ 220 líneas) con las trazas RED, las mediciones de T1–T4 y T7–T8, las tres verificaciones de la anulación (T4) y el camino A aplicado en T11, y la sección «Evidencias» con los cuatro números y el nº de workers de la campaña  |  Verificación: `python -m harness.tamano --feature F-080` en verde
- [ ] T29: Ejecutar `bash harness/init.sh` en verde  |  Verificación: `bash harness/init.sh` termina con exit code 0

## Decisiones abiertas que necesitan al humano

1. **El orden con F-073 (§1).** F-080 va detrás. Si el humano quisiera
   adelantarla, hay que reabrir R20 y R32: la dimensión `compras.formas_pago`
   y la versión 19 del diccionario cambian de dueño.

Es la única que queda.

*Resueltas y retiradas de esta lista el 2026-09-11:* el presupuesto de ventana
nocturna (pasa a ser referencia de 4 h, no puerta), el corte de 30 s de la
vista de comentarios (es tabla), `codigo_efecto` (es `con.cod` literal) y la
tabla de remesas bancarias (es `raw.rpa`, y entra en la ingesta por R3).

*Resueltas por la CUARTA MEDICION, también el 2026-09-11:*

- **`serie_efecto`** (era la 2): la columna de serie de `raw.con` existe y está
  **vacía** (`con.serie` a 0 en los 255.074 efectos), así que no hay nada que
  consultar al humano: la serie se deriva de `con.cod` con `compras.fn_serie`,
  la función que ya vive en `sql/compras/00_setup.sql` (R38, T9).
- **El ciclo de vida del efecto** (era la 3): **camino A**. La anulación es
  `con.fecbaj <> 0` —tres de tres contra la captura de `FR25/04222`, y los
  vivos suman los 87.854,56 / 92.478,49 de la cabecera—, se publica como
  `efecto_anulado` con su fecha, y los importes agregados de `v_facturas_pago`
  salen filtrando por ella (R19, R40, T11). `efecto_origen_id` no se publica:
  `pag.padide` está a 0 y el enlace hijo → origen no existe en el origen.
