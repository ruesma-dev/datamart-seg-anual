<!-- specs/F-080-vencimientos-forma-pago-y-texto-factura/design.md -->
# F-080 · Diseño técnico

> **Corregido el 2026-09-10** (2.ª y 3.ª medición) y el **2026-09-11** (4.ª). Lo tocado lleva
> su línea *Corrige:*. Dos titulares. Uno: **el efecto de pago ES un documento** (`raw.pag` son
> «Propiedades de `con`», `tip = 25`), así que código, descripción y estado se **leen** de
> `raw.con` / `raw.conest`. Dos: el efecto tiene **ciclo de vida** (división, agrupación,
> anulación); su marca es **`con.fecbaj <> 0`**, medida, y el enlace hijo → origen **no
> existe**, porque `pag.padide` está a 0 en toda la tabla.

## 1 · La frontera, y el orden con F-073

| Pieza | Quién la hace | Por qué |
|---|---|---|
| Dimensión `compras.formas_pago` (`auxpag`+`auxefp`) | **F-073** | Es una dimensión transversal; F-073 ya la tiene especificada |
| Cableado de la forma de pago a la **factura** | **F-080** | Ningún criterio de F-067 lo promete: su criterio 1 nombra solo `compras.contratos` y el 5 no menciona forma de pago |
| Cableado a `compras.contratos` y el estado de documentos | F-067 | Su criterio 1, y toca `01_documentos.sql`, que F-067 reescribe |
| Cartera completa de cobros y pagos (`cob` + `pag` sin filtro) | F-037 fase 1 | F-080 solo toma los efectos **de la factura de compra** |
| Comparativos, ofertas, actividades, foto diaria de estados | F-067 | Fuera de esta petición |

**F-080 va DETRÁS de F-073, y la precondición tiene dos niveles** (R20). **Dura, para el
implementer**: que `sql/compras/04_formas_pago.sql` exista en el árbol y que
`BuildComprasStep` lo declare como sub-paso; si no, `blocked`, porque levantar una segunda
copia de la dimensión desde `raw.auxpag` es la duplicación que F-073 viene a evitar.
**MANUAL (humano)**: que `compras.formas_pago` esté **construida en la base**, exigible antes
de las verificaciones contra la base y no antes de escribir código.
*Corrige:* antes bastaba con que la vista no estuviera construida para bloquear la feature, que
habría muerto el primer día; el implementer no la necesita —sus tests son sobre el **texto** del
SQL y ningún agente ejecuta SQL contra un Postgres compartido con producción— y F-073 está
cerrada pero **no desplegada**: en Azure no existe hasta la nocturna con la imagen nueva.

F-073 reserva la **versión 19** del diccionario y **F-081 ya gastó la 20** al
corregir la mentira de `auxefp` (cerrada el 2026-09-11), así que a F-080 le toca
la **21** (R32), comprobando siempre el valor real del fichero.
*Corrige:* antes decía 20; era cierto cuando se escribió y dejó de serlo.

**Deuda declarada con F-037 (R35).** `compras.vencimientos` es la pata de compra de lo que
F-037 hará entero: cuando llegue, se decide si lo absorbe o lo deja como vista suya, y eso
consta en las fichas de las **dos** features.

**Límite de microservicio.** Nada se sale del ETL: se lee de Sigrid por `sigrid-api` y de
`raw`, y se escribe en esta misma base.

## 2 · Ficheros a crear

- `etl_sigrid/infrastructure/postgres/sql/compras/05_vencimientos.sql`
  → tabla `compras.vencimientos` (R7–R12, R38–R41).
- `etl_sigrid/infrastructure/postgres/sql/compras/06_pago_factura.sql`
  → vistas `compras.v_facturas_pago` (R16–R19) y `compras.v_control_forma_pago` (R28–R30).
- `etl_sigrid/infrastructure/postgres/sql/compras/07_texto.sql`
  → **dos tablas**: `compras.documento_texto` (el memo íntegro) y
  `compras.documento_comentarios` (partido, un comentario por fila) (R22–R26).
- `etl_sigrid/domain/texto_comentarios.py` — **capa domain, sin imports de infraestructura**.
  Contiene los dos literales medidos (`SEPARADOR_BLOQUES`, `SELLO_COMENTARIO`) y la función
  pura `partir_memo(texto) -> list[Bloque]`, oráculo ejecutable del parseo (R24–R26).
- `tests/test_f080_texto.py` — la función pura sobre fixtures: memo de tres comentarios, memo
  con un bloque sin sello, memo con la línea automática, memo vacío y memo de un solo bloque.
- `tests/test_f080_sql.py` — asserts sobre el **texto** de los tres SQL nuevos. El SQL no se
  ejecuta en los tests: escribe en un Postgres compartido con producción. Patrón de
  `tests/test_f052_sql.py` y `tests/test_f042_sql.py`.
- `tests/test_f080_ingesta.py` — `con.tex` fuera de exclusiones, `dcf`/`dca`/`ctr` intactas,
  las **tres** altas (`auxnap`, `auxban`, `rpa`) y sus fichas.
- `tests/test_f080_diccionario.py` — fichas, claves declaradas y versión.

## 3 · Ficheros a modificar

- `config/tables_sigrid.yaml` — `tex` sale de `exclude_columns` de `con` (queda `ima`); altas
  de `auxnap`, `auxban` y **`rpa`**; `page_size` de `con` **solo si el humano lo decide con la
  medición delante** (R5). *Corrige:* antes eran dos altas y el `page_size` bajaba por regla.
- `etl_sigrid/application/steps/build_compras_step.py` — tres sub-pasos nuevos en `SUB_PASOS`,
  en orden: `vencimientos`, `pago_factura`, `texto`. **Los tres** construyen tabla y declaran
  `target_schema`/`target_table` (el de texto construye dos, R22 y R23).
- `config/diccionario/raw.yaml` — recuento de exclusiones de `con` (2 → 1) y fichas nuevas de
  `auxnap`, `auxban` y `rpa`.
- `config/diccionario/compras.yaml` — cinco fichas nuevas.
- `config/diccionario/00_global.yaml` — `version` 19 → **20** y su nota.
- `tests/test_f074_ingesta_censo.py` — `TOTAL_TABLAS` 65 → **68**. Es el contador de tablas
  ingeridas y esta feature añade tres.
- `harness/features.json` — la nota recíproca de la deuda en la ficha de F-037.

## 4 · Ficheros que NO se tocan (los que tientan)

- `sql/compras/01_documentos.sql`, `02_fact_linea.sql`, `03_views.sql` — son de F-067 (R21).
  La forma de pago de la factura se publica en una vista propia, no como columnas nuevas de
  `compras.facturas`.
- `sql/compras/00_setup.sql` — se **usa** (`fn_sigrid_date`, `fn_serie`), no se amplía: la
  serie ya tiene función y R38 la reutiliza.
- `sql/compras/04_formas_pago.sql` — lo crea F-073. F-080 **lee** su vista.
- `sql/stg/06_presupuesto.sql` y `sql/stg/08_plan_mensual.sql` — el SELLO (R36): tocarlos
  fuerza la reconstrucción de las 921 obras la noche siguiente.
- `exclude_columns` de `dcf`, `dca` y `ctr` (R2), y `raw.cob` (R15).
- `etl_sigrid/application/steps/ingest_raw_step.py` — la ingesta ya filtra por **nombre de
  columna** y ya soporta `page_size` por tabla. No hay mecanismo nuevo que escribir: solo
  configuración.

## 5 · El SQL, objeto por objeto

Todo en el esquema `compras`, numerado detrás de `04_formas_pago` (F-073).

### `compras.vencimientos` (05) — TABLA

Base: `raw.pag p JOIN raw.dcf f ON f.ide = p.conide` (el filtro a factura de compra, R7)
`JOIN raw.con c ON c.ide = p.ide` —**`c` es el documento DEL EFECTO** (`tip = 25`), no el de
la factura— y `LEFT JOIN raw.con cf ON cf.ide = f.ide` para el código de la factura, más
`LEFT JOIN` a los catálogos. *Corrige:* el diseño anterior unía `raw.con` por `f.ide` y se
quedaba solo con la cabecera; por eso creía que el efecto no tenía identidad propia (DA-9).

**Tabla y no vista**, con `ALTER TABLE ... ADD PRIMARY KEY (vencimiento_id)`: mismo patrón que
`compras.facturas` y, sobre todo, **la clave primaria hace fallar el build la noche en que el
grano se rompa**, en vez de dejar que lo descubra `check-unicidad` un mes después.

- **Fechas** (R9): `compras.fn_sigrid_date(p.fecven)`, `...(p.fecrea)`, `...(p.fecreaemi)`.
- **`codigo_efecto` = `c.cod` literal** (`FR26/06051_01`) y **`descripcion_efecto` = `c.res`**
  («Pago 1 de 2 …»), que es la columna «Descripción» de la rejilla (R12). Nada se deriva: ni
  `ordinal_efecto` con `row_number()` ni `lpad` sobre el código de la factura.
- **`serie_efecto`** (R38): se deriva de `c.cod` con **`compras.fn_serie`**, la función que ya
  existe en `00_setup.sql` y que usa `01_documentos.sql`; no se escribe otra ni se repite su
  `substring`. Devuelve el prefijo alfabético completo (`FR`, `NO`, `AGR`, `DIV`). Reparto
  medido por los dos primeros caracteres: `FR` 192.356 (efecto inicial), `NO` 35.846, `AG`
  21.992 (agrupación al remesar), `DI` 3.587 (división), 1.071 residuales. *Corrige:* antes
  salía de «la columna de serie del documento, sin parsear `cod`»; esa columna existe y está
  vacía: **`con.serie` vale 0 en los 255.074 efectos** (DA-10).
- **`estado_pago_codigo` = `c.est`** y **`estado_pago`** = su nombre resuelto con `LEFT JOIN
  raw.conest ce ON ce.tip = 25 AND ce.<clave> = c.est` (R10); la clave exacta la mide T1.
  `LEFT JOIN` y no `JOIN`: un estado fuera de catálogo no puede hacer desaparecer un efecto.
  Son 10 estados medidos (1 Pendiente, 2 Aprobado, 3 Emitido, 5 En cartera, 7 Remesado, 10
  Pagado, 12 Devuelto, 14 Agrupados, 15 Divididos, 20 Anticipado) y PDT/APR/CAR/PAG son sus
  abreviaturas. *Corrige:* antes salía de `fecrea`; falso. NO se publica `p.pun`: vale 0.
- **`fecha_real`** (`p.fecrea`) se publica **como fecha, no como estado**: la ficha declara
  que `fecrea = 0` NO significa «vivo» (158.503 efectos, 62 %, R11).
- **La remesa** (R41): `LEFT JOIN raw.rpa r ON r.ide = p.remide` con `p.remide` distinto de 0
  → código, `compras.fn_sigrid_date(r.fecrem)`, `r.imptot` y el banco. 77.576 efectos están en
  una remesa; el resto sale a NULL. `raw.rco` (remesas de cobro) no se toca: es F-037.
- **La anulación** (R39, R40): **`efecto_anulado` = `c.fecbaj <> 0`** y **`fecha_anulacion` =
  `compras.fn_sigrid_date(c.fecbaj)`**. Medido el 2026-09-11 sobre `FR25/04222`, la factura de
  ocho efectos del correo: los **tres** que la pantalla pinta en rojo con aspa son exactamente
  los tres con `fecbaj <> 0`, y el **estado no los distingue** (los tres, «Aprobado»). La
  prueba que lo cierra son los importes: los cinco vivos suman **87.854,56** y con la retención
  viva **92.478,49**, **los dos números que la propia captura enseña en la cabecera**.
  Cobertura: **89.095 de 255.074 efectos de baja (34,9 %)**; sin ese filtro, uno de cada tres
  es un fantasma. **`efecto_origen_id` NO se publica**: `pag.padide` vale 0 en los 255.074
  efectos, así que el enlace hijo → origen no está en el origen y la relación solo se deduce
  por importes y fechas, una reconstrucción que no se publica como dato. *Corrige:* antes las
  dos columnas quedaban condicionadas al veredicto de T4, que ya está medido.

### `compras.v_facturas_pago` (06) — VISTA, una fila por factura

`compras.facturas` + `raw.dcf` + `compras.formas_pago` + catálogos de medio, naturaleza, cuenta
y banco. El resumen de efectos entra por un CTE **agregado por `factura_id`** y unido con un
`LEFT JOIN` (R19): agregar antes de unir impide el fan-out. Trae cuántos efectos, primer y
último vencimiento **y los importes agregados filtrando los efectos de baja** (`WHERE NOT
efecto_anulado`), que es lo que reproduce el número de la cabecera de Sigrid. `plazo_formula`
sale de `compras.formas_pago` tal cual (R17). *Corrige:* antes prohibía todo importe agregado
«mientras R40 siga sin resolverse»; R40 está resuelto y lo que hace falta es el filtro.

### `compras.v_control_forma_pago` (06) — VISTA, una fila por (factura, contrato)

El enlace factura → contrato **no se inventa**: es el mismo
`COALESCE(fl.contrato_id_directo, alb.contrato_id, alb_l.contrato_id_linea)` que ya usa
`compras.v_pbi_contrato_consumo` sobre `compras.factura_lineas` (R28). El grano no puede ser
«una fila por factura» porque una factura puede tener líneas de varios contratos: la clave es
el **par**, y la ficha lo dice. La forma de pago del contrato se lee de `raw.ctr.pagide` contra
`compras.formas_pago`, **no** de `compras.contratos`, que la publicará F-067 (R21).

### `compras.documento_texto` (07) — TABLA

`raw.con` filtrado a `tip IN (15, 44)` y `tex` no vacío. Columnas: `documento_id`,
`tipo_documento`, `codigo_documento`, `texto`, `bytes`, `num_comentarios`. PK `documento_id`
(R22). Tabla y no vista porque el memo se lee muchas veces y filtrar `raw.con` (2,18 M filas)
en cada consulta es caro.

### `compras.documento_comentarios` (07) — TABLA

`CREATE TABLE ... AS SELECT` en el mismo build, sobre `compras.documento_texto`:
`regexp_split_to_table(t.texto, SEPARADOR) WITH ORDINALITY` para `orden`, y
`regexp_match(bloque, SELLO)` para fecha, hora y usuario. `orden` = 1 es el más reciente porque
**Sigrid concatena en descendente** y el split conserva ese orden; PK `(documento_id, orden)`
declarada (R23). Cuando `regexp_match` devuelve NULL: `sello_reconocido = false`, fecha y
usuario a NULL, `comentario` = el bloque entero (R25). *Corrige:* antes era una vista (R27).

## 6 · Riesgos y decisiones

- **DA-1 · El parseo va en SQL, no en Python.** El memo ya está en Postgres: llevárselo a
  Python y devolverlo son 30,6 MB de ida y vuelta por nada, y `regexp_split_to_table` y
  `regexp_match` bastan (no hacen falta lookarounds, que POSIX no tiene). **Y aun así el
  oráculo es Python**: los literales y la semántica viven en `domain/texto_comentarios.py`, se
  prueban ahí sobre fixtures y `test_f080_sql.py` comprueba que el SQL usa esos mismos
  literales. Es el patrón F-052, y da a la mutación código Python real que morder.
- **DA-2 · Nada de lo que no casa se pierde (R25, R26).** El memo íntegro está en
  `compras.documento_texto` **y además** cada bloque sale entero en la tabla de comentarios,
  case o no el sello: el sello solo **añade** columnas, no recorta. La verificación es
  reconstructiva: los bloques unidos por el separador dan el memo original.
- **DA-3 · El separador se reconoce con tolerancia.** Lo medido es
  `\n --------------------------------- \n`, pero nada garantiza esa longitud. Se escribe como
  una línea de **tres o más guiones** con espacios opcionales; parta de más o de menos, el
  bloque se publica entero (DA-2). Los bloques sin sello se cuentan y se declaran en la ficha.
- **DA-4 · El coste de la ventana se mide en dos tiempos, y ninguno se supone (R4).** `con`
  tiene 2.185.737 filas y hoy va a `page_size` 10.000; el memo son 33,7 MB en 120.649
  documentos, ~280 bytes de media **pero con máximos de 11.580 bytes en facturas y 28.154 en
  comparativos**: la media dice que no pasa nada y el máximo, que una página de 10.000
  documentos habladores puede pesar cientos de MB en memoria del contenedor. **Medición A**:
  solo lectura contra Sigrid con el cliente del ETL, cronometrando páginas de `con` con y sin
  `tex` a 10.000 y a 5.000 filas. **Medición B**: `python main.py ingest --table con --full`
  contra el Postgres de dev, comparando `ingest_raw.con` en `_meta.etl_runs` con las noches
  anteriores. B es una escritura: va como MANUAL.
- **DA-5 · El presupuesto de ventana es una referencia, no una puerta.** Hoy la nocturna tarda
  **3 h 25 min** (antes de F-025 eran 4 h 52) y no había número escrito en ningún sitio. F-080
  fija **4 h** como referencia para juzgar R5: si la medición B lo supera, se **avisa por
  escrito** en `progress/impl_F-080.md` y en `progress/current.md`, y ahí acaba la obligación
  del agente. *Corrige:* antes era una puerta que obligaba a bajar `page_size` a 5.000.
- **DA-6 · Los comentarios se guardan como tabla, sin cronómetro de por medio.** Son ~110.000
  memos: partirlos en cada lectura es trabajo repetido para siempre, y el humano lo zanjó
  («guárdala como tabla y como texto»). Se materializa en la nocturna con su PK declarada.
  *Corrige:* antes era una vista con plan B condicionado a un corte de 30 s (R27, retirado).
- **DA-7 · Alternativa descartada: añadir columnas a `compras.facturas`.** Sería más cómodo
  para el MCP, pero mete a F-080 dentro de `01_documentos.sql`, que es de F-067 y que F-067
  reescribe entera (R21). Una vista propia cuesta un `JOIN` al consumidor y no colisiona.
- **DA-8 · Alternativa descartada: derivar el código y el estado del efecto.** El diseño
  anterior componía el código (el de la factura + un ordinal de `row_number()`) y derivaba el
  estado de `fecrea`. Las dos cosas eran falsas: el código es `con.cod` y el estado es
  `con.est` contra `raw.conest` (R10, R12). Se retira la derivación entera, no se «ajusta».
- **DA-9 · El `JOIN` a `raw.con` es obligatorio, no un adorno.** Sin él
  `compras.vencimientos` **no tiene código, ni descripción, ni estado, ni marca de anulación**:
  `raw.pag` no los guarda. `pag` son «Propiedades de `con`» —el efecto ES un documento con
  `tip = 25`— y esas columnas viven en la superclase. En una sola exploración se concluyó dos
  veces «ese campo no existe» mirando solo la tabla de propiedades, y las dos veces era falso.
  **Regla: en Sigrid, antes de dar por inexistente un campo de un documento, se mira `con`**
  (`tests/test_f006_fuente_que_gobierna.py`); quitar ese `JOIN` devuelve la tabla a las
  derivaciones que esta corrección retira.
- **DA-10 · Tres campos que prometen y no cumplen.** `cen.obride` (F-073), `pag.padide` y
  `con.serie` existen en el diccionario de Sigrid, encajan por nombre y **valen 0 en toda la
  tabla**. Regla que deja esta feature: antes de diseñar sobre un campo del origen se mide su
  cobertura. La serie sale de `fn_serie` (R38) y la anulación de `con.fecbaj` (R40); al enlace
  hijo → origen no lo sustituye nada, y por eso no se publica en vez de deducirse a ojo.
- **Riesgo · Multiplicación de filas.** El grano se puede romper por cinco sitios: los
  `LEFT JOIN` a catálogos y a `raw.rpa` de `compras.vencimientos`, el CTE de resumen de
  `v_facturas_pago`, el `WITH ORDINALITY` de los comentarios y el enlace factura→contrato. Los
  blindan la PK de cada tabla, el agregado previo y `check-unicidad`. Aparte queda la
  duplicación **de importe, no de fila** (R39), que solo frena el filtro `efecto_anulado`.
- **Riesgo · Nombres de columna no medidos.** De `raw.pag`, `raw.conest`, `raw.rpa`,
  `raw.auxnap`, `raw.auxban` y `raw.cua` solo tenemos documentación, no medición —y `auxban` es
  jerárquico (banco↔sucursal), así que **no consta** por qué clave se une `banban`/`bansuc`—.
  T1 los mide en solo lectura y los deja escritos **antes** de que exista una línea de SQL.

## 7 · Verificaciones que solo puede hacer el humano

Van en `tasks.md` como `MANUAL (humano)` y en `progress/current.md` con su comando exacto: que
`compras.formas_pago` esté construida en la base (R20, antes de lo que toque la base y no antes
de escribir código), las mediciones de T1–T4, la medición B de la ventana, los recuentos de los
objetos nuevos, el reparto de `estado_pago`, el recuento de anulados (R40), la prueba
reconstructiva del memo, los tres `check-*`, la publicación del diccionario y la batería de
tres preguntas al MCP (R34).
