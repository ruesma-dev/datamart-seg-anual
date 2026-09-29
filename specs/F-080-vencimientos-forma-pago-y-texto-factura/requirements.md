<!-- specs/F-080-vencimientos-forma-pago-y-texto-factura/requirements.md -->
# F-080 · Requisitos (EARS)

**Alcance.** La **factura de compra**: sus efectos, su forma de pago, su texto y el control contra el
contrato. NO la cartera de cobros y pagos (F-037 fase 1) ni comparativos, ofertas o estados (F-067).
**Consume** `compras.formas_pago` (F-073); no la duplica. Alternativas descartadas, en `design.md`.

**Corregida el 2026-09-10** (2.ª y 3.ª medición) y el **2026-09-11** (4.ª: la anulación es `con.fecbaj`; `pag.padide` y `con.serie` están a
0), con la exploración delante. Cada requisito tocado lleva su línea *Corrige:*; los retirados van al final y **el resto no se renumera**.

## A · La ingesta: `con.tex`, los catálogos y las remesas (criterio 1)

- **R1.** Debe ingerir `con.tex`: la columna sale de `exclude_columns` de `con`, que
  queda con **una sola exclusión, `ima`** (patrón `prvcer.tex`, F-074).
- **R2.** NO debe tocar las exclusiones de `dcf`, `dca` ni `ctr`: la pestaña
  «Texto» sale de `con.tex` (65,5 % de las facturas), no de `dcf.tex` (0,3 %).
- **R3.** Debe ingerir `raw.auxnap` (3 filas), `raw.auxban` (1.666) y **`raw.rpa`**
  (3.909 remesas, a la que apunta `pag.remide`), con `incremental_column` **medido** en
  `INFORMATION_SCHEMA`, nunca por analogía (F-074 declaró tres `tiemod` inexistentes).
  *Corrige:* antes daba la tabla de remesas por no identificada; está medida y es `rpa`.
- **R4.** CUANDO se cambie la ingesta de `con`, debe dejar en `progress/impl_F-080.md` **antes
  de desplegar**: (a) segundos y bytes por página leyendo `con` con y sin `tex`, a `page_size`
  10.000 y 5.000, en solo lectura; (b) la duración de `ingest_raw.con` en `_meta.etl_runs`
  antes y después.
- **R5.** CUANDO la medición esté hecha, debe compararla con el presupuesto de ventana de
  `design.md` §6 (**4 h**) y, SI lo supera, avisar **por escrito** en el informe y en
  `progress/current.md`. Es **referencia para juzgar, no una puerta**: no se marca `blocked`,
  no se para nada, no se baja `page_size`. *Corrige:* antes obligaba a bajarlo a 5.000.
- **R6.** La ficha de `raw.con` debe decir que **falta 1 sola columna, `ima`**, y
  `raw.auxnap`, `raw.auxban` y `raw.rpa` deben tener la suya.

## B · Los efectos de pago de la factura (criterios 2 y 3)

**El efecto ES un documento**: `raw.pag` son «Propiedades de `con`» y cada efecto tiene
su fila en `raw.con` con `tip = 25`. Código, descripción y estado **se leen**.

- **R7.** Debe publicar `compras.vencimientos` con **una fila por fila de `raw.pag` cuyo
  `conide` sea factura de compra** (`raw.dcf`) y `vencimiento_id` (= `pag.ide`) como
  **clave primaria declarada en la tabla**.
- **R8.** Debe exponer, **por efecto**: tipo, fecha de emisión, código, descripción,
  vencimiento, fecha real, importe, medio de pago, estado, cuenta contable, banco y
  **remesa**; más la factura (id y código) y la retención. Catálogos **a nombre**.
- **R9.** Debe tipar toda fecha entera con `compras.fn_sigrid_date`, que devuelve
  NULL cuando el entero es 0.
- **R10.** `estado_pago` debe **leerse**: `con.est` del efecto contra **`raw.conest` con
  `tip = 25`**, con código y nombre. Son **10 estados medidos** (1 Pendiente, 2 Aprobado, 3
  Emitido, 5 En cartera, 7 Remesado, 10 Pagado, 12 Devuelto, 14 Agrupados, 15 Divididos, 20
  Anticipado); PDT/APR/CAR/PAG son abreviaturas suyas y **el estado NO marca la anulación**
  (R40). *Corrige:* antes salía de `fecrea`; los dos efectos de `FR26/06051` lo tienen a 0.
- **R11.** La ficha debe declarar que **`fecrea = 0` NO significa «vivo»** (158.503 efectos,
  62 %, sin puntear, frente a los 10.607 de cartera viva de F-037): avisa de la fecha real,
  no del estado (R10).
- **R12.** `codigo_efecto` debe ser `con.cod` del efecto **literal** (`FR26/06051_01`) y
  `descripcion_efecto`, `con.res` («Pago 1 de 2 …»). NO se deriva, ni con `row_number()` ni
  con `lpad`. *Corrige:* antes lo componía como «factura + ordinal»; falso, está almacenado.
- **R15.** NO debe publicar `raw.cob` ni efectos de documentos que no sean factura
  de compra: eso es F-037 fase 1.
- **R38.** Debe publicar la **serie** del efecto derivándola de `con.cod` con
  **`compras.fn_serie`** (`sql/compras/00_setup.sql`, ya usada por `01_documentos.sql`), sin
  escribir otra función. Reparto medido por prefijo: `FR` 192.356 (efecto inicial), `NO`
  35.846, `AG` 21.992 (agrupación), `DI` 3.587 (división), 1.071 residuales. *Corrige:* antes
  exigía leerla «de la columna de serie, sin parsear `cod`»; **`con.serie` vale 0 en los
  255.074 efectos**.
- **R39.** La ficha debe declarar que **sumar los importes de todos los efectos de una factura
  DUPLICA**: nace con `_01` (pago) y `_02` (retención); al dividir, los hijos van en serie
  `DIV` y **el original queda anulado**; al remesar se agrupan en `AGR`. **89.095 de 255.074
  efectos (34,9 %) están de baja**: sin filtrar, uno de cada tres es un fantasma. La tabla
  debe permitir **excluir los anulados sin borrarlos** (R40).
- **R40.** Debe publicar **`efecto_anulado`** (verdadero cuando `con.fecbaj <> 0`) y
  **`fecha_anulacion`** (`fn_sigrid_date(con.fecbaj)`), y **NO** `efecto_origen_id`:
  `pag.padide` vale 0 en los 255.074 efectos, así que el enlace hijo → origen no existe y
  deducirlo por importes no es un dato publicable. *Corrige:* antes mandaba **medir** la marca
  de anulación y condicionaba lo publicado; medido el 2026-09-11 (evidencia en `design.md` §5).
- **R41.** Debe exponer la remesa resolviendo `pag.remide` contra `raw.rpa` (77.576
  efectos en remesa): código, fecha (`fecrem`), importe total y banco. `rco` no (F-037).

## C · La forma de pago de la factura (criterio 4)

- **R16.** Debe publicar `compras.v_facturas_pago` con **una fila por factura** y su
  forma de pago (`dcf.pagide`) resuelta a nombre contra **`compras.formas_pago`**.
- **R17.** Debe exponer `plazo_formula` **verbatim** como lo publica F-073, sin
  derivar ningún `dias_pago` numérico (`30 450R` es un valor real).
- **R18.** Debe exponer, **por factura**: forma de pago con su descripción, fórmula (`pagfor`) y
  condiciones (`pagtex`, ya ingeridas por F-066), naturaleza (`cypnatide` → `auxnap`), medio de
  pago con descripción (`efeide` → `auxefp`) y cuenta de transferencia (`banide`/`ban` + `auxban`).
- **R19.** Debe traer el resumen de efectos (cuántos, primer y último vencimiento) **sin
  romper el grano**, y **puede publicar importes agregados filtrando los efectos de baja**
  (`efecto_anulado` falso, R40). *Corrige:* antes los dejaba «sujetos a R40»; R40 quedó
  resuelto el 2026-09-11 y sumar con ese filtro reproduce lo que Sigrid enseña.
- **R20.** Precondición dura del implementer: que `sql/compras/04_formas_pago.sql` exista en
  el árbol y que `BuildComprasStep` lo declare como sub-paso; SI no, `blocked`. Que
  `compras.formas_pago` esté **construida en la base** es verificación **MANUAL (humano)**,
  exigible antes de las verificaciones contra la base y no antes de escribir código. NO se
  duplica la dimensión desde `raw.auxpag`. *Corrige:* antes bloqueaba la feature si la vista
  no estaba construida; el implementer no la necesita (sus tests son sobre el TEXTO del SQL)
  y F-073 está cerrada pero **no desplegada**: la vista no existe hasta la primera nocturna.
- **R21.** NO debe modificar `compras.facturas`, `compras.contratos`,
  `sql/compras/01_documentos.sql`, `02_fact_linea.sql` ni `03_views.sql` (F-067).

## D · El texto del documento (criterio 5)

- **R22.** Debe publicar `compras.documento_texto` con **el memo íntegro tal y como
  llega**, una fila por documento con texto, para facturas (`tip = 15`) y contratos
  (`tip = 44`). `documento_id` es clave primaria.
- **R23.** Debe publicar **además** `compras.documento_comentarios` como **TABLA de la carga
  nocturna** —no vista—: un comentario por fila con documento, `orden` (1 = el más reciente,
  como Sigrid los apila), fecha, hora, usuario y cuerpo, y clave (`documento_id`, `orden`)
  **declarada en la tabla**. *Corrige:* antes era una vista materializable (R27, retirado).
- **R24.** El separador de bloques y el sello `[dd/mm/aaaa hh:mm:ss Usuario:
  <login>]` deben estar escritos **una sola vez**, en un módulo de dominio, y el
  SQL debe usar esos mismos literales.
- **R25.** SI un bloque no casa con el sello —texto a mano, o la línea automática que
  la aplicación añade al último bloque—, se publica igual con fecha y usuario a NULL,
  `sello_reconocido` en falso y **el bloque entero** como cuerpo.
- **R26.** Recomponer los bloques en su orden debe reproducir el memo original:
  **ni un carácter perdido** fuera de los separadores.

## E · El control contra el contrato (criterio 6)

- **R28.** Debe publicar `compras.v_control_forma_pago` con **una fila por par
  (factura, contrato)**, con la **misma regla de enlace que
  `v_pbi_contrato_consumo`** (línea directa, o vía albarán), no con una nueva.
- **R29.** Debe enfrentar la forma de pago de factura y contrato y marcar la
  coincidencia **sin filtrar**: las que cuadran también salen.
- **R30.** La ficha debe declarar cuántas facturas quedan fuera por no colgar de
  ningún contrato, medido en esta feature.

## F · El papeleo y las puertas (criterios 7 y 8)

- **R31.** Cada objeto nuevo debe llevar su ficha en `config/diccionario/` con
  grano, clave declarada y significado de cada columna.
- **R32.** `00_global.yaml` sube a **versión 21** (F-073 reserva la 19 y **F-081
  gastó la 20**). SI no estuviera en la 20, se sube al siguiente número real:
  manda el valor del fichero, no este número.
  *Corrige:* antes decía 20, reservada mientras F-081 no existía.
- **R33.** `check-unicidad`, `check-declarados`, `check-diccionario` y `bash harness/init.sh`
  deben terminar en verde (R37 se funde aquí).
- **R34.** El MCP debe responder **sin explicarle nada en el prompt** a las tres
  preguntas del criterio 8: cuándo vence una factura y si está pagada, qué dice el
  texto de una retenida, y qué facturas no cuadran con la forma de pago del contrato.
- **R35.** La deuda con F-037 debe constar en las fichas de **las dos** features: al
  llegar F-037 se decide si absorbe `compras.vencimientos`.
- **R36.** NO se modifican `sql/stg/06_presupuesto.sql` ni `08_plan_mensual.sql`:
  son el SELLO.

## Requisitos retirados el 2026-09-10 (el resto NO se renumera)

- **R13** (ordinal derivado si fallaba la verificación de códigos): el código está en `con.cod`
  (R12). **R14** (parar si `pag.pun` resultaba ser el estado): `pun` vale 0 y el estado es
  `con.est` (R10). **R27** (materializar los comentarios a 30 s): ya decidido, es tabla.
